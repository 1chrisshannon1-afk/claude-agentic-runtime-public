# GTM Wave-2 interface contracts — §6 Connector interface

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md). Text this file needs in
> another contract file is listed as change requests in [`requests/06_connectors.md`](requests/06_connectors.md)
> (cited below as "R<n>"). Until a request lands, the name it defines is **pending**: WPs code against
> the name exactly as written here and the tests that need it stay red. They never guess a substitute.

## 6. Connector interface (WP-L ↔ WP-A2)

### 6.1 Package layout and manifest

```
tools/gtm/connectors/__init__.py               (L3; every package-root name: http_request, _transport, HostNotAllowed,
                                                TestModeNoLive, MutationOutsideApply, RedirectRefused (§6.5b),
                                                _run, GCLOUD_SEARCH_PATH, gcloud_path, OPENSSL (§6.5b "Subprocess seam"),
                                                CredentialUnavailable, auth_headers, mint_google_token (§6.3),
                                                idempotent_apply, redact_content, redact_key, _canon, error_for_status,
                                                PAUSED_CREATE_ROWS, is_create_row, ConnectorCtx, make_log, _REDACT_RE (§6.2))
tools/gtm/connectors/testkit.py                (L3; FakeHTTP, FakeProc, load_fixture, make_ctx — §6.5b)
tools/gtm/gtmlib/connector_dispatch.py         (A2; §6.3 — imported as `from gtmlib import connector_dispatch`)
tools/gtm/secret_sink.py                       (E; §6.6)
tools/gtm/runbooks/<stem>.runbook.json         (WP-L; machine browser runbooks, §6.4 — under TRUST_PATHS)
tools/gtm/connectors/<connector>/__init__.py   (empty)
tools/gtm/connectors/<connector>/manifest.json
tools/gtm/connectors/<connector>/read.py
tools/gtm/connectors/<connector>/write.py      (absent for read-only connectors, e.g. call_tracking)
tools/gtm/connectors/<connector>/tests/…       (fixtures; no network)
```
Connectors: `google_ads, ga4, search_console, gtm_api, gbp, meta, wordpress, listings, lead_sink,
call_tracking`. **Import root (DECIDED HERE):** `tools/gtm` is on `sys.path` and code imports
`connectors`, `connectors.<name>.write`, `system_names`, etc. The `tools.gtm.` prefix is never used
in code or tests, so exactly one module object exists per connector and one monkeypatch covers
every caller.

**Systems no connector serves (DECIDED HERE).** Two tier systems are never passed to
`connector_dispatch.execute`/`verify`: `gtm_ai` (internal; act.py handles it, §6.3
`is_api_executable`) and `website_static` (patch-bound; executed by the act.py/`implement` path and
landed by `complete --commit`, 02_act.md §2.4 FID-04). If either is passed anyway, `execute` and
`verify` refuse before the op binding and before `api_executable_reason`: `gtm_ai` →
`validation` `internal_system_no_connector`; `website_static` → `validation` `static_not_connector`;
`retryable: false`, `side_effect: "none"`, zero connector calls. A2 test: a `website_static.page_edit`
action passed to `execute` → `static_not_connector`, zero `FakeHTTP.calls`; RED when it falls
through to `no_connector` or to `match_account`.

**Import rules (DECIDED HERE).** Code on the connector paths — `read()`, `write.py` (`plan`,
`apply`, `verify_read`, `dedupe_probe`) and everything they call — imports only `connectors`,
`system_names`, `gtm_env` and the stdlib, never `gtmlib`. The one exception is `read.py main()`
(§6.3), the CLI entry: it imports `connector_dispatch` (gtmlib) **inside `main()`**, never at module
top, spelled exactly `from gtmlib import connector_dispatch`, so importing `connectors.<c>.read` for its `read()` function (A2 does, §6.3 "Lead sink") pulls
in no gtmlib. `connector_dispatch` imports a connector's modules by name with
`importlib.import_module("connectors.<name>.write")` / `("connectors.<name>.read")`; `connector_for`
(§6.3) returns the package `connectors.<name>`, and its callers take `.read`/`.write` through
`importlib`, never through attribute access on the empty package `__init__`. L3 test: importing
`connectors.<c>.read` for every connector adds no `gtmlib*` key to `sys.modules`.

**Manifest load source (DECIDED HERE).** `connector_dispatch.load_manifest(R: Path, connector: str)
-> dict` reads `tools/gtm/connectors/<connector>/manifest.json` exactly as `runbook_validate.load_head`
reads a runbook (§6.4 "Trust root"): the HEAD bytes, refused unless byte-identical to the working
tree. It raises `ManifestUnavailable(<code>)` with code `manifest_not_at_head`, `manifest_dirty` or
`manifest_unreadable` (fail closed on every error). It is the only reader: `api_executable_reason`
(§6.3) returns that code and `is_api_executable` is therefore False; `execute`/`verify` return `validation` with that code as message and no
connector call; `read_committed_ceiling` raises `CeilingUnreadable("no_connector")`;
`build_read_ctx` lets it propagate and `read.py main` maps it to exit 3 with
`{"ok": false, "data": null, "errors": [{"code": "<code>", "message": ""}]}` on stdout and nothing
at `--out`. So `api_hosts`, `write_rows`, `access` and `credential` can never be widened by a
working-tree edit on any path, signed, tier-admitted or read. A2 test: a working-tree manifest that
adds a host to `api_hosts` → `execute` validation `manifest_dirty` and `read.py main` exit 3, zero
`FakeHTTP.calls`; RED when the working-tree file is read.

**Tier system ↔ connector mapping.** The one source is `03_schemas.md §3.22` (the
"Connector" column), read in code only through `system_names.connector_system(tier_system)`. This
file does not restate it. `connector_for` (§6.3) calls `system_names.connector_system`. A manifest's
`tier_systems` is a checked copy: an L3 test asserts, for every manifest, that `set(tier_systems)`
equals `{t for t in system_names.CANONICAL_SYSTEMS if system_names.connector_system(t) == manifest.connector}`.

`manifest.json` (every key required unless marked optional):
```json
{"connector": "google_ads", "tier_systems": ["google_ads"], "access": ["api", "browser"],
 "write_rows": ["google_ads.keyword_add", "google_ads.campaign_budget_edit", "google_ads.campaign_enable"],
 "dedupe": {"google_ads.keyword_add": "state_equals_before", "google_ads.campaign_budget_edit": "state_equals_before",
            "google_ads.campaign_enable": "state_equals_before"},
 "read_ops": ["ad_content", "campaigns", "change_events", "committed_ceiling", "owns"],
 "inbox_class_ops": [],
 "credential": {"kind": "gsm", "auth": "google_sa",
                "fields": ["auth_route", "service_account_email", "developer_token", "login_customer_id"],
                "scan_fields": ["developer_token", "private_key"],
                "scopes": ["https://www.googleapis.com/auth/adwords"],
                "secret_template_doc": "gtm-{slug}-google"},
 "api_hosts": ["googleads.googleapis.com"],
 "runbooks": {"google_ads": "tools/gtm/runbooks/google_ads.runbook.json"}}
```

| Key | Consumer | Meaning |
|---|---|---|
| `connector` | L3 manifest test | equals the directory name |
| `tier_systems` | L3 manifest test only | checked copy of 03 §3.22 (above); never read for dispatch |
| `access` | `connector_dispatch.api_executable_reason` (hence `is_api_executable`; a manifest whose `access` lacks `"api"` → `not_api_executable`, §6.3), `read_committed_ceiling` (`not_api_account`) | the `accounts[].access` values this connector can serve. `api` means the connector can serve that account over its API: for **reads** a read-only connector (no `write.py`, e.g. `call_tracking`) may list `api`; only **writes** additionally need `write.py` and the row in `write_rows`, which `is_api_executable` checks separately (§6.3). `read_committed_ceiling`'s `not_api_account` refusal is judged on the account (`access: api` with a `gsm:` ref), never on `write.py`. L3 manifest test: a manifest listing a non-empty `write_rows` has a `write.py`; a manifest with no `write.py` has `write_rows: []` and `dedupe: {}` |
| `write_rows` | `is_api_executable`, L3 manifest test | tier-table row ids `apply` implements. Each must exist in `tier_table.json`, and its system's `connector_system` must be this connector |
| `dedupe` | `connectors.idempotent_apply` (§6.2) | one entry per `write_rows` id: `client_tag`, `state_equals_before` or `none` (§6.2 Idempotency) |
| `read_ops` | `read.py main`, `build_read_ctx` callers | the ops `read()` accepts. A connector serving a tier system that has a `commits_on_enable: true` row (03_schemas.md §3.4.1) **or** any budgeted object that can be enabled, resumed or unpaused (§6.2 "Enable-bound actions"; today `google_ads`, `meta`, `listings`) must list `committed_ceiling`. A connector that is a `target_system` of any `*.asset_link` row must list `owns`. The `google_ads` and `meta` connectors must list `ad_content` (§6.2 "Ad content read and verify"; 03_schemas.md §3.4.4 "Enabling ads") |
| `inbox_class_ops` | `read.py main` (hipaa routing, §6.3) | subset of `read_ops` that return reviews, messages, DMs, Q&A, comments, form submissions, calls or leads. The L3 test asserts that every `read_ops` entry matching 02_act.md §2.4 `INBOX_CLASS_RE` is listed, and that **every** read op of the `lead_sink` and `call_tracking` connectors (tier systems `crm`, `call_tracking`) is listed |
| `credential.kind` | `credential_getter` | `gsm` (the only kind) |
| `credential.auth` | `connectors.auth_headers` (§6.3 "Auth scheme per connector") | `google_sa` \| `meta_bearer` \| `wp_app_password` \| `bearer`; for `lead_sink` only, an object keyed by the pack's `lead_sink.kind` (`{"google_sheet": "google_sa", "app_crm": "bearer"}`). Fixed per connector by the §6.3 table; the L3 manifest test asserts the table value |
| `credential.scopes` (required when `auth` is or contains `google_sa`) | `google_sa` token minting (§6.3) | OAuth scopes the connector's token carries. **Keyed form** exactly as `fields` (same keys as `auth`), selected by `pack.lead_sink.kind`; the entry of a non-`google_sa` kind is `[]`: `{"google_sheet": ["https://www.googleapis.com/auth/spreadsheets"], "app_crm": []}` |
| `credential.header` (optional, `bearer` only) | `connectors.auth_headers` | header name when the vendor does not take `Authorization: Bearer` |
| `credential.fields` | `credential_getter`, `secret_sink` (§6.6) | keys every GSM JSON payload must carry (§6.3); `google_sa` adds its route-specific keys (§6.3). **Keyed form:** whenever `credential.auth` is an object keyed by `lead_sink.kind`, `fields` is an object with the **same keys** (`{"google_sheet": ["auth_route", "service_account_email"], "app_crm": ["token"]}`), and every consumer selects the entry by `pack.lead_sink.kind`; a kind with no entry (or `none`) → `CredentialUnavailable("payload_invalid")` / `secret_sink` exit 6 `payload_invalid` (§6.6) |
| `credential.scan_fields` | `secret_sink` leak scan (§6.6) | the subset of payload keys that are secret (tokens, passwords, private keys), e.g. `["access_token"]` (meta), `["token"]` (bearer), `["application_password"]` (wordpress), `["developer_token", "private_key"]` (google_ads; `private_key` only present on the `key` route). Identifiers that legitimately appear on platform pages (`client_id`, `login_customer_id`, `service_account_email`, account ids) are never listed. Each must be a key of `fields` or a `google_sa` route key (every `google_sa` manifest lists `private_key`); a listed key absent from a given payload (a route key of the other route) is skipped, so an `impersonate`-route payload of ga4/search_console/gtm_api carries no secret and records `needles: []`, while every **present** listed value yields at least one scan needle (§6.6 "Scan needles"; the raw value itself is always one). **Keyed form** exactly as `fields` (same keys as `auth`), selected by `pack.lead_sink.kind`: `{"google_sheet": ["private_key"], "app_crm": ["token"]}` |
| `api_version` (required for `meta`; optional elsewhere) | `connector_dispatch`'s `meta_bearer` identity check (§6.3), the meta connector's URLs | the pinned vendor API version string, e.g. `"v21.0"` (the value is UNVERIFIED; the L1 meta connector's first recorded fixture pins it). It must fullmatch `v[0-9]+\.[0-9]+` |
| `credential.secret_template_doc` (optional) | nobody | naming convention, documentation only |
| `api_hosts` | `connector_dispatch` → `ctx.allowed_hosts` / `ctx.allowed_host_suffixes` (§6.5b) | exact hosts the connector may call. Two tokens: `{pack_domains}` (wordpress only) expands to the domains of **`ctx.account`'s effective brand only** (`brands[id == ctx.brand].domains`, where `ctx.brand` is the effective brand of §6.3 "Account matching" — the account's `brand` field, else its system suffix's brand — never the raw `account.brand` field, so a suffix-only account such as `system: "website_remodeling"` with no `brand` key expands its own brand's domains), each matched exactly or as a subdomain: each domain `d` (lowercased) goes into `allowed_hosts` as `d` **and** into `allowed_host_suffixes` as `"." + d`; nothing else ever fills `allowed_host_suffixes`. **Shared-hosting parents (DECIDED HERE; plan §20.2 positive allowlist).** A domain `d` that has fewer than two dot-separated labels, or that equals an entry of `system_names.SHARED_HOST_PARENTS` (pending, requests/06_connectors.md R35: a pinned literal frozenset of platform and shared-hosting parent domains and multi-label public suffixes, e.g. `wpengine.com`, `wordpress.com`, `wpcomstaging.com`, `kinsta.cloud`, `pantheonsite.io`, `netlify.app`, `vercel.app`, `github.io`, `herokuapp.com`, `web.app`, `firebaseapp.com`, `appspot.com`, `azurewebsites.net`, `cloudfront.net`, `squarespace.com`, `wixsite.com`, `godaddysites.com`, `co.uk`, `com.au`), contributes **nothing** to `allowed_hosts` or `allowed_host_suffixes` (fail closed: every request to it or under it is `host_not_allowed`); a tenant subdomain such as `acme.wpengine.com` is an ordinary domain and is admitted exact and as a suffix. `company.py validate` also refuses such a `brands[].domains` entry (R35), so the build-time drop is the backstop. A2/L3 test (wordpress): a fixture brand whose `domains` is `["wpengine.com"]` → `allowed_hosts` and `allowed_host_suffixes` hold nothing from it and a request to `https://other.wpengine.com/wp-json/x` → `host_not_allowed`, zero transport calls; RED when the drop is removed. A2 test: a suffix-only `system: "website_remodeling"` wordpress account (no `brand` key) → `allowed_hosts` holds the remodeling brand's domains and none of the restoration brand's; RED when expansion reads `account.brand`. `{lead_sink_host}` (lead_sink only) expands to the host of that pack's own `lead_sink.ref` when `kind == app_crm` (§6.3 "Lead sink"), exact only; it is refused only at config time (`company.py validate`, §6.3 "Config-time refusal", R1 item 10) and at request time by the `phi_denylist` host guard (§6.5b). It expands to **nothing** for every other kind (google_sheet reaches only its literal `sheets.googleapis.com` + the token host) and for CSA's own pack (`ctx.company == system_names.CSA_SLUG`), whose `app_crm` sink is not served in Wave 2 (§6.3 "CSA's own `app_crm` sink"). `allowlist.json` `read_only_hosts` is never consulted by the connector host guard. The OAuth token host `oauth2.googleapis.com` is added implicitly (exact) for the **Google connectors**, enumerated exactly: `google_ads, ga4, search_console, gtm_api, gbp`, and `lead_sink` only when the pack's `lead_sink.kind == google_sheet`. **G-B parity (04_hooks.md §4.2 rule b):** every **literal** `api_hosts` entry — read-only hosts included (e.g. the GA4 Data API host) and each vendor host a `listings`/`call_tracking` manifest names — must be in 04 §4.2 rule b's host-pattern list and in the §4.7 `bash_gate.sh` token set (R17). **During Wave 2 an L WP never edits the live `hooks/bash_gate.sh`, `gtm_bash_gate.py` or B2's `tools/gtm/wave2_pending/b2_gb_wiring.patch`** (04 §4.7 keeps the live hook unchanged until the activation train): it files a request against 04 (host pattern + `bash_gate.sh` token) in the same change that adds the host to a manifest, and B2 folds it into the patch. The parity test is 04's P2 G-B host-parity test, **owned by B2**; it runs against the patch (the rule-b list and token set the patch will install), not the live hook, and gates the activation train. **Literal hosts the Wave-2 manifests declare** (pre-populated in R36 so B2 can carry them now): `googleads.googleapis.com` (google_ads), `analyticsadmin.googleapis.com` and `analyticsdata.googleapis.com` (ga4), `searchconsole.googleapis.com` (search_console), `tagmanager.googleapis.com` (gtm_api), `mybusinessbusinessinformation.googleapis.com` and `mybusinessaccountmanagement.googleapis.com` (gbp; read only until the SA probe of §6.3), `graph.facebook.com` (meta), `sheets.googleapis.com` (lead_sink), and the implicit `oauth2.googleapis.com`; the `listings` and `call_tracking` vendor hosts are UNVERIFIED and are added by request when their manifests are written. A host outside this list needs its own request. The two tokens are exempt from that parity test by name: `{pack_domains}` is covered by rule b's `/wp-json/` path rule, and `{lead_sink_host}` has no static value to list (its host is the pack's own `lead_sink.ref`, refused at config time when it is a shared or Agency host, §6.3) |
| `runbooks` | `ticket --write`/`--write-batch`/`--read` (02_act.md §2.4), G-A `runbook_hosts` (04_hooks.md), L3 manifest test | `{"<tier system>": "tools/gtm/runbooks/<stem>.runbook.json"}` (R-relative), one per tier system with any browser row. The file stem must equal `system_names.runbook_stem(tier_system)`. The path is always under `tools/gtm/runbooks/` (TRUST_PATHS, 05_approver.md §5.5); any other path fails the L3 manifest test. Consumers read it **only from HEAD** (§6.4 "Trust root") |

**The secret name has one source (I25):** the pack account's `credential_ref` (`gsm:<name>`). The
manifest's `secret_template_doc` documents the naming convention and is never read by code.

### 6.2 Entry points

```python
# connector context: DEFINED in the connectors package root (tools/gtm/connectors/__init__.py, L3), so connector
# code and L1/L2 fixture tests import it without gtmlib; BUILT only by connector_dispatch._build_ctx (A2, §6.3) in
# production and by testkit.make_ctx (L3, §6.5b) in tests
@dataclass
class ConnectorCtx:
    company: str; home: Path; state_dir: Path                # state_dir = ST = home/.claude/gtm/state
    R: Path                                                   # the runtime root, = actx.R (02_act.md §2.2 Ctx), set by _build_ctx; read by
                                                              # idempotent_apply's gtm_env.refuse_real_state(R, home) (§6.2) and load_manifest
    pack: dict; account: dict                                 # the matched pack account (§6.3 account matching)
    tier_system: str; brand: str | None                       # canonical tier system (03 §3.22) and the account's EFFECTIVE brand id (§6.3
                                                              # "Account matching": the account's `brand` field, else its system suffix's brand;
                                                              # None for a brandless account); {pack_domains} and {brand_display_name} read this,
                                                              # never account["brand"]
    row: dict                                                 # the tiers.match_row(actx, action) result (02_act.md §2.2b; the synthetic _nomatch row
                                                              # included), set by _build_ctx when it is given an action; {} when action is None (read
                                                              # contexts: build_read_ctx, read_committed_ceiling's read ctx, §6.2 step 6's ctx_t)
    manifest: dict                                            # connector_dispatch.load_manifest(R, <connector>) result (§6.1 "Manifest load source",
                                                              # HEAD bytes only), set by _build_ctx on every builder path
    dry_run: bool
    now: Callable[[], datetime]                               # gtmlib clock: tz-aware UTC; GTM_FAKE_NOW when GTM_TEST=1
    credential: Callable[[], dict[str, str]]                  # lazy; the parsed GSM JSON payload (§6.3); never logged/printed/returned
    evidence_dir: Path                                        # §6.3 "Evidence directories"; contents: §6.2 "Evidence files"
    log: Callable[[str], None]                                # stderr; ALWAYS connectors.make_log(ctx._secrets) (below), a closure over that
                                                              # same mutable set: every member is replaced by "<redacted>" (longest first), then
                                                              # the package-root _REDACT_RE substitution (below) is applied;
                                                              # it NEVER calls ctx.credential() (so it cannot trigger a GSM fetch, raise under
                                                              # test mode, or recurse inside credential step 7); content rule below
    _secrets: set[str]                                        # filled by credential_getter right after its step-5 parse with every non-empty
                                                              # string value of the payload's `fields` and `scan_fields` keys (both route keys
                                                              # included), and by mint_google_token with each minted token; empty until then
    target_ids: dict[str, str]                                # execute/verify: resolved object ids (§6.2 target resolution); {} in read contexts.
                                                              # _build_ctx starts it {} (or the `target_ids` argument); execute/verify ASSIGN
                                                              # ctx.target_ids after target resolution succeeds, before plan()/verify_read
    bound_assets: dict[str, Path]                             # sha256 hex → ABSOLUTE path of the bound copy ST/assets/<action_id>/<sha256>
                                                              # (02_act.md §2.8 check 4 "Asset binding"), one entry per action["assets"][i];
                                                              # {} in read contexts and for an action with no assets (§6.2 "Asset and upload bytes")
    upload_source: Path | None                                # *_upload rows only: the absolute realpath of source_ref that act.py re-checked
                                                              # under home_data immediately before the call (the `upload_source` argument of
                                                              # execute, §6.3); None for every other row and in read contexts
    approved: dict | None                                     # effective-money actions only: {"new_absolute_value", "unit"} taken from the payload that
                                                              # connector_dispatch.execute RE-VERIFIED itself (§6.2 "Money binding"); never copied from a caller's dict; else None
    allowed_hosts: frozenset[str]                             # exact hosts (lowercased), built by connector_dispatch from the manifest (§6.1 api_hosts); http_request enforces it
    allowed_host_suffixes: frozenset[str]                     # leading-dot suffixes (".example.com"), filled ONLY from {pack_domains} (§6.1); frozenset() otherwise
    mutation_hook: Callable[[], None] | None                  # set only by connectors.idempotent_apply, immediately before body() and cleared to None in the
                                                              # finally that writes the terminal line (§6.2 Idempotency); None while probe() runs;
                                                              # http_request calls it before a mutating request, and refuses a mutating request when it is
                                                              # None (§6.5b MutationOutsideApply)
    snapshots_dir: Path                                       # = the act Ctx's paths.snapshots_dir, resolved by _build_ctx (every builder, build_read_ctx included)
    gcloud_account: str | None; gsm_project: str | None       # non-secret, from connectors.json at HEAD (§6.3 credential step 1); set by credential_getter's
                                                              # first call before minting; None until then; read by connectors.mint_google_token only
    _token_cache: dict                                        # {"token": str, "expires_at": datetime} or {}; in memory only, owned by connectors.mint_google_token (§6.3)
```

**The log closure (DECIDED HERE).** `connectors.make_log(secrets: set[str]) -> Callable[[str], None]`
(L3, package root) is the ONE builder of `ctx.log`; `connector_dispatch._build_ctx` and
`testkit.make_ctx` both call it with the very set object they store as `ctx._secrets`, so members
added later (credential step 5, `mint_google_token`) are redacted. The closure replaces every member
of `secrets` by `"<redacted>"` (longest first), then applies
`_REDACT_RE.sub(lambda m: f"{m.group(1)}=<redacted>", line)`, and writes the line plus `"\n"` to
`sys.stderr`; it never calls `ctx.credential()`. DECIDED (wave1c): `_REDACT_RE` is a package-root
inline copy of `activity_log.REDACT_RE` (`activity_log.py:141`, same pattern and `re.IGNORECASE`),
not an import of `activity_log` — importing it would break the §6.1 closed import list (its import
runs `sys.path.insert` and `import company`); the `_canon` parity pattern contains the drift. L3
tests: (a) on a fixed corpus (`password=x`, `API-Key: y`, `token = z`, `Secret:w`, a line with no
key) the closure's output with `secrets=set()` equals `activity_log.redact(line)` for every line
(RED when either regex drifts; this test file, not connector code, imports `activity_log`); (b) a
secret added to the set AFTER `make_log` returned is redacted (RED when the closure copies the set);
(c) for a ctx from `_build_ctx` and one from `make_ctx`, adding `"s3cr3t"` to `ctx._secrets` after
construction makes `ctx.log("x s3cr3t")` write `x <redacted>` (RED when either builder passes a
different set or builds its own closure).

**Row and manifest reach connector code only through the ctx (DECIDED HERE).** Connector-side code
(the `connectors` package root, every `read.py`/`write.py`, and everything they call) reads the
matched tier-table row only as `ctx.row` and the manifest only as `ctx.manifest`: `idempotent_apply`
takes `ctx.manifest["dedupe"][ctx.row["id"]]`; `auth_headers` and `mint_google_token` take
`ctx.manifest["credential"]` (`auth`, `scopes`, `header`, keyed forms selected by
`ctx.pack["lead_sink"]["kind"]`); the meta connector takes `ctx.manifest["api_version"]`; `plan`/`apply`
take `after_fields`, `after_value_fields`, `id_fields` and `when.campaign_state` from `ctx.row`, and
call `is_create_row(ctx.row)`. Connector code never opens `manifest.json` or `tier_table.json` and
never imports `tiers` or `connector_dispatch` (§6.1 import rules), so the §6.1 HEAD-only guarantee
holds on every path. A read context has `row == {}`; a read op that needs a row field is a contract
violation. L3 test: with a tmp HEAD holding a committed manifest, build a ctx through `_build_ctx`
(clean tree), then edit the working-tree `manifest.json` (a changed `dedupe` entry and an added
`credential.header`) and call `idempotent_apply` and `auth_headers` on that ctx → both observe the
HEAD values (the dedupe mode and headers of the committed manifest); RED when either reads the
working-tree file.

```python

# write.py
def plan(ctx, action) -> dict                    # no network writes (a mutating http_request raises MutationOutsideApply, §6.5b); {"ops": [op], "requires_before": {...}}
def apply(ctx, action, *, idempotency_key: str) -> dict   # WriteResult; body is connectors.idempotent_apply(...) (below)
def verify_read(ctx, action) -> dict             # VerifyResult
def dedupe_probe(ctx, action) -> str             # "absent" | "present" | "unknown"; platform reads only (§6.2 Idempotency)

# read.py
def read(ctx, op: str, params: dict) -> dict     # {"ok": bool, "data": object, "errors": [{"code": str, "message": str}]};
                                                 # addresses only objects under ctx.account (§6.3 "Account scope of every read")
def main(argv) -> int                            # CLI, §6.3 "read.py main"
```

**Log and error content (every pack; binding for `regulated ∋ "hipaa"`, plan §20.4/§20.13).** A
connector's `ctx.log` lines, `WriteResult.error.message`, `VerifyResult.error.message`, `read()`
`errors[].message` and any exception text it raises carry only: the HTTP status code, the
contract's error/reason code, the connector's own fixed text, and object ids from `ctx.target_ids`.
They never include a platform response body, a request body, or any inbox-class content (review,
message, DM, Q&A, comment, form, call or lead text, caller numbers, names). Response content reaches
the caller only through `read()`'s `data`, which `read.py main` writes to the routed `--out` file
(§6.3), never to stdout/stderr. L test (per connector, on a hipaa fixture pack): a fixture error
reply whose body holds a marker string and a `read()` of an inbox-class op whose data holds another
marker → neither marker appears in captured stderr, stdout, `error.message` or `errors[].message`;
RED when a connector echoes the body.

**Persisted and printed content (every pack; plan §20.4).** Two more surfaces carry write content and
are held to the same rule by one package-root helper, `connectors.redact_content(result: dict, *,
key: bytes | None = None) -> dict` (L3). It accepts a WriteResult, a VerifyResult or a `plan()` dict (told apart by keys: `applied_ops`
→ WriteResult, `diff` → VerifyResult, `ops` → plan dict; anything else → `ValueError`) and returns a
**new dict built only from the keys named below** — an input key not named is dropped, never copied.
`D(v)` is `{"digest": "sha256:<hex of sha256(_canon(v))>"}` when `key` is None, and
`{"digest": "hmac-sha256:<hex of hmac.new(key, _canon(v), sha256)>"}` when `key` is given
(`_canon` below), applied **per key** (never once over a whole dict), so two results that differ in
one field differ in exactly that digest. **`_canon(obj) -> bytes`** is a private package-root
function implementing 00_global_paths.md §0.3's canonical-JSON formula verbatim
(`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`; 00
is the source): the connector import rules (§6.1) forbid importing
gtmlib's copy, so the package root inlines it, and an L3 test asserts it equals `gtmlib`'s
`canon` on a fixed corpus (RED when either drifts).
**Keyed digests on hipaa packs (DECIDED HERE; plan §20.4/§20.13).** Lead rows, review text, names and
10-digit phone numbers are low-entropy, so a plain `sha256(_canon(v))` kept in the never-purged,
backed-up ledger can be reversed by enumeration. So every caller passes
`key = connectors.redact_key(state_dir, pack)`: `None` unless `"hipaa" in pack.get("regulated", [])`;
otherwise the 32 bytes of `state_dir/"untrusted"/"redact_key"`, created on first use and
**published atomically**: `ST/untrusted/` is created if absent with `mkdir(parents=True, mode=0o700)`;
`os.urandom(32)` is written to a unique temp file in that same directory (`O_CREAT | O_EXCL`, mode
`0600`), fsynced, then `os.link(tmp, redact_key)`; `FileExistsError` (another process won) → read
the winner's file; in every case the temp file is unlinked. So a reader never sees a partly written
key (a loser that read a half-written file would refuse a valid write). L3 test: two threads racing
the first use both obtain the same 32 bytes and neither raises; RED when the key is written in place
under `O_EXCL`. A file that is unreadable or not exactly 32 bytes → `ValueError("redact_key_unavailable")`
(fail closed; `idempotent_apply` maps it below). The key lives in `ST/untrusted/`, so
`purge-untrusted` deletes it by age like every other untrusted file (its mtime is its creation
time, so it rotates at least every 30 days) and it is excluded from backups (08_seats_wps.md
Appendix C item 5); after a purge the next use mints a new key, and every earlier ledger digest is
unlinkable to any value. Digests are compared by nothing (act.py reads only `platform_refs` from a
replay), so rotation breaks no reader. Non-hipaa packs keep the plain `sha256` form. L3 test (hipaa
fixture pack): a `lead_sink` append whose lead row holds the phone `5551234567` → no
`ST/connector_idem/*.jsonl` line contains `sha256(_canon("5551234567"))`'s hex, and deleting
`redact_key` then redacting the same value yields a different digest; RED under plain sha256. act.py
persists connector results with the same `key` (requests/06_connectors.md R16, R28):
- **WriteResult** → `ok`, `idempotency_key`, `platform_refs`, `retryable`, `evidence`,
  `side_effect` (when present) verbatim; `applied_ops` → each op as `{"op", "object", "id",
  "fields": {k: D(v) for k, v in fields.items()}}`; `before_observed` → `{k: D(v)}`; `error` → null,
  or `{"code": <verbatim>, "message": <verbatim>}` (`error.message` is content-free by the rule
  above, and is kept so a replayed refusal still names its reason).
- **VerifyResult** → `ok`, `retryable`, `evidence`, `checked_at` verbatim; `observed` → `{k: D(v)}`;
  `expected` → `{k: D(v)}`; `diff` → each entry as `{"field": <verbatim>, "expected": D(expected),
  "observed": D(observed)}`; `error` as above.
- **plan dict** → `ops` as `applied_ops` above; `requires_before` → `{k: D(v)}`.
Example: `{"ok": true, "idempotency_key": "a-17", "platform_refs": {"row_id": "42"}, "applied_ops":
[{"op": "create", "object": "row", "id": null, "fields": {"name": "Jane Roe", "phone": "5551234"}}],
"before_observed": {}, "error": null, "retryable": false, "evidence": [], "debug": "x"}` →
`{"ok": true, "idempotency_key": "a-17", "platform_refs": {"row_id": "42"}, "applied_ops": [{"op":
"create", "object": "row", "id": null, "fields": {"name": {"digest": "sha256:…"}, "phone": {"digest":
"sha256:…"}}}], "before_observed": {}, "error": null, "retryable": false, "evidence": []}` (`debug`
dropped). L3 test: this example, a VerifyResult whose `observed`/`diff` hold a marker string (absent
from the output), and an unknown extra key (dropped); RED when any content key is copied verbatim.
- **The idempotency ledger** (§6.2 Idempotency) stores `redact_content(result, key=redact_key(ctx.state_dir,
  ctx.pack))` in every line's `result`, for **every** pack. `ST/connector_idem/` is in `backup_set()` and never purged
  (00_global_paths.md §1.3), so a lead row (`lead_sink` append), a review-reply `before_observed`, a
  CRM status change or any recipient-bearing write would otherwise sit there, backed up forever,
  against plan §20.4 (OtherCompany inbound content lives only in the purgeable `ST/untrusted/` store). A
  replay returns the redacted result: `platform_refs` + digests are all act.py reads from a
  replay (02_act.md §2.4 `execute`). act.py stores the same redacted form wherever it persists a
  connector result (R16), and 00_global_paths.md §1.3's ledger row records it (R20).
- **The dry-run plan.** `connector_dispatch.execute(..., dry_run=True)` returns `plan()`'s dict, which
  act.py prints. For a pack with `regulated ∋ "hipaa"` it returns `redact_content(plan_dict,
  key=redact_key(...))` (op `fields` and `requires_before` values as keyed digests); other packs get
  the dict unchanged.
L test (L3, on a hipaa fixture pack): a `lead_sink` append whose lead row holds a marker string, run
to `ok: true` and then replayed → the marker appears in no `ST/connector_idem/*.jsonl` line, in no
member of the backup tar that `backup_state.py` builds from the paths `company.backup_set(slug, pack)`
returns (a `list[Path]`), and not in the dry-run output; the replay returns the same
`platform_refs`. RED when `idempotent_apply` writes the unredacted result. **Dependency:** the
committed `backup_set(slug, pack)` archives all of `home/.claude/gtm/state`, `ST/untrusted/`
included, so the backup clause of this test stays RED until 08_seats_wps.md Appendix C item 5
(excluding `ST/untrusted/` from `backup_set()`) lands; the ledger and dry-run clauses do not depend
on it.

**Data shapes (DECIDED HERE).**
- `op = {"op": "create|update|remove|enable|pause|link|upload|publish", "object": "<platform object kind>", "id": str | null, "fields": {}}`.
  `plan().ops` and `WriteResult.applied_ops` hold `op`s. `applied_ops` lists only ops the platform
  confirmed.
- `plan().requires_before = {"<field>": <current platform value>}`: the values the before re-check
  (below) compares, as read by `plan()`.
- `WriteResult = {"ok": bool, "idempotency_key": str, "platform_refs": {"<id_field>": "<id>"}, "applied_ops": [op],
  "before_observed": {}, "error": null | {"code": "before_mismatch|auth|rate_limited|not_found|validation|partial_prior_attempt|lock_timeout|unknown", "message": str},
  "retryable": bool, "evidence": [<home-relative path>], "side_effect"?: "none" | "unknown"}`. `platform_refs` keys are `id_fields` names
  (03_schemas.md §3.4.1) or the created object's kind + `_id` (e.g. `campaign_id`).
  A refusal WriteResult that `connector_dispatch.execute` builds itself, before `idempotent_apply`
  runs, carries `idempotency_key = action["action_id"]` (the same key `apply` would use), empty
  `platform_refs`/`applied_ops`/`before_observed`/`evidence`, and `retryable: false`.
  **`side_effect` (R46 of requests/05_approver.md; 05_approver.md §5.5 step 5 "Release or
  quarantine" releases a `$` nonce only on `"none"`).** Present on every `ok: false` WriteResult,
  absent on `ok: true`. It says whether **this** call may have changed platform state, derived by
  one rule from the same facts as the ledger's `side_effects` (below), so the two never disagree:
  `"none"` iff the result is (i) a refusal returned by `connector_dispatch.execute` before `apply`
  was called — exactly these, all `error.code = "validation"`, by message:
  `internal_system_no_connector`, `static_not_connector` (§6.1 "Systems no connector serves");
  `bad_op` and every other op-binding message (§6.3 "Op binding");
  `paused:<pause name>` (§6.3 "The pause step of `execute`"); every class-step message
  (`card_not_approved`, `card_subject_mismatch`, `card_predates_event`, `hold_pending`, `cancelled`,
  `not_authorized`, `baa_missing`, `hipaa_prohibited`; §6.3 "The class step of `execute`");
  `not_agent_executable`, `not_api_executable`, `no_connector` and every `manifest_*` code
  (`api_executable_reason`, §6.1/§6.3); `approval_missing` and `approved_mismatch` (the approval
  binding, §6.2 "Money binding"); `account_missing`, `account_ambiguous`; every target-resolution
  message (`identity_recheck_failed` — also the money binding's and class step 0's never-class
  refusal — `target_account_mismatch`, `account_key_missing`, `target_id_conflict`,
  `target_missing`, `link_target_not_in_pack`); `upload_source_missing` (§6.2 "Asset and upload
  bytes"); `shared_budget` (§6.2 "Shared budgets"). Also
  `"none"`: `error.code = "not_found"`, message `not_owned`, from the step-6 `owns` read; and a
  `plan()` exception that `execute` maps by the §6.3 exception table (`auth` or `validation`;
  `plan()` can make no mutating request, §6.5b step 2, so none of these follows a sent write); or (ii) an
  `idempotent_apply` result that wrote **no** `started` line in this call (`lock_timeout`,
  `test_mode_real_state`, `redact_key_unavailable`, a before-send refusal of `body` — e.g.
  `before_mismatch`, `currency_mismatch`, `not_owned` from a parent or in-account ownership read,
  `asset_unbound`, `asset_sha_mismatch`, `source_mismatch`), or (iii) an `outcome` whose ledger
  `side_effects` is `false`. Every other failure is `"unknown"` — including an `outcome` with
  `side_effects` `"unknown"` or `true`, and a `refused` `partial_prior_attempt` (this call wrote
  nothing, but an earlier attempt of the same action may have, so the approval must not be
  re-used). `redact_content` keeps it verbatim. L tests (per connector with a `write.py`): a
  `FakeHTTP.raise_after(<the write POST>, ConnectionError())` → `side_effect: "unknown"`; a 400
  reply to the write POST → `"none"`; a `target_account_mismatch` refusal → `"none"`; a
  `partial_prior_attempt` → `"unknown"`; each RED when `side_effect` is derived otherwise.
- `VerifyResult = {"ok": bool, "observed": {}, "expected": {}, "diff": [{"field", "expected", "observed"}],
  "error": null | {"code": "auth|rate_limited|not_found|validation|unknown", "message": str}, "retryable": bool,
  "evidence": [paths], "checked_at": "<00_global_paths.md §0.3 UTC timestamp, Z, second precision>"}`.
  `validation` carries every refusal `verify` makes before or inside `verify_read` (`not_api_executable`,
  `not_agent_executable`, `no_connector`, `account_missing`/`account_ambiguous`, every target-resolution
  message, `currency_mismatch`, `host_not_allowed`, `redirect_refused`, `test_mode_no_live`); it is a
  non-null `error`, so it never counts toward the breaker (below).
  `expected` holds the `after` values of the row's allowed fields (money rows:
  `{"new_absolute_value", "unit"}`; status rows add `configured_ceiling`, §6.2 "Committed amount of
  a status row"). For money rows `observed.new_absolute_value` is the platform's
  current absolute value, **except** for status rows (pause and enable-bound rows, §6.2 "Committed
  amount of a status row": pause, remove and enable-bound rows), where it is the object's committed amount: the configured ceiling when the
  mapped status is `live`, `"0.00"` when it is `paused`, `removed` or deleted. So a signed pause
  (`after.new_absolute_value: "0.00"`) of a campaign whose budget stays configured at `45.00` verifies
  `ok: true` with `observed.new_absolute_value == "0.00"`. **A2 counts a verify failure toward the breaker
  (`breakers.record_verify_failure`) only when `ok` is false and `error` is null.** A non-null `error`
  is a failed read, not a mismatch. It leaves the action `completed` for a later `verify`.

**Evidence files (DECIDED HERE; plan §20.4).** `WriteResult.evidence`/`VerifyResult.evidence` list
the home-relative paths of files the connector wrote under `ctx.evidence_dir` (§6.3 "Evidence
directories") during that call, and nothing else. One file per platform request the call made,
named `<nn>_<METHOD>_<slug>.json` (`<nn>` = two-digit order within the call, `<slug>` = the URL path's
last segment, `[a-z0-9_]` only), holding exactly `{"method", "url_path", "status", "request":
<redact_content-style digests>, "response": <see below>}`: `url_path` is the URL without query
string; `request` holds `{k: D(v)}` for each `json_body`/form key (never a value; §6.2 "Persisted and
printed content", same `key` as the ledger); `response` holds, on a non-hipaa pack, `{k: D(v)}` for
each top-level key of the reply's `json` (never the raw body), and on a `regulated ∋ "hipaa"` pack
nothing but `{"digest": D(<the whole json>)}`. A raw platform response body is never stored in an
evidence file on any pack. Files are mode `0600`; the directory is created `mkdir(parents=True,
mode=0o700)`. On a hipaa pack the directory is under `ST/untrusted/` (§6.3), so it is purged and
never backed up. L3 test (hipaa fixture pack): an apply whose reply body holds a marker string → no
file under `ctx.evidence_dir` contains the marker, and each listed path exists; RED when a raw body
is written.

**Asset and upload bytes (DECIDED HERE; plan §6.5/§6.6, §20.3, §20.5.4; 02_act.md §2.8 check 4
"Asset binding", requests/02_act.md item 85 (a); requests/03_schemas.md R60 (b)).** A connector
never opens `action["assets"][i]["path"]`, `after.value.source_ref`, or any other path under `H`.
- **Assets.** Every byte a connector uploads for an action asset (an image for a Meta ad or post, a
  WordPress media item, a GBP post photo) is read **only** from `ctx.bound_assets[<sha256>]`, the
  bound copy `ST/assets/<action_id>/<sha256>` that act.py re-hashed and re-scanned with
  `checks.rebind_assets` as its last step before calling `connector_dispatch.execute`. `_build_ctx`
  sets `bound_assets = {a["sha256"]: (ctx.state_dir / "assets" / action_id / a["sha256"]).resolve()
  for a in action.get("assets", [])}` (paths only; it reads no file). In `apply`, before the first
  mutating request of the call: an asset the op needs whose `sha256` is not a key of
  `ctx.bound_assets` → `validation`, message `asset_unbound`; then each file it will send is opened
  with `O_NOFOLLOW`, read once into memory, and re-hashed; a digest ≠ its key → `validation`, message
  `asset_sha_mismatch`; both with **zero** mutating calls. The in-memory bytes are what is sent.
- **Upload rows (`*_upload`, 03_schemas.md §3.4.1 `home_data`).** The data file is read **only**
  from `ctx.upload_source`, the path act.py's `execute` passed after its own `home_data` re-check
  (the `upload_source` argument, §6.3; requests/06_connectors.md R37). A `*_upload` row with
  `ctx.upload_source` None → `connector_dispatch.execute` refuses `validation`
  `upload_source_missing` before `_build_ctx`, zero calls. In `apply`, before the first mutating
  request: the file is opened with `O_NOFOLLOW`, read once into memory and hashed; a digest ≠
  `after.value.source_sha256` → `validation`, message `source_mismatch`, zero mutating calls. The
  connector never re-opens `source_ref`.
L tests (meta, wordpress; each RED when its clause is reverted): a fixture action whose
`assets[0].path` points at bytes different from its bound copy → the upload body recorded in
`FakeHTTP.calls` equals the bound copy's bytes (RED when `assets[].path` is read); a bound copy
altered after `_build_ctx` → `asset_sha_mismatch`, zero write calls; an asset sha absent from
`bound_assets` → `asset_unbound`. L test (google_ads `customer_match_upload`, or the first `*_upload`
row served): the FakeHTTP upload body equals `upload_source`'s bytes, and a spy on `builtins.open`/
`os.open` records zero opens of the `source_ref` path; a changed `upload_source` → `source_mismatch`.

**HTTP status → `error.code` (DECIDED HERE; one table for every connector).** No connector maps a
status itself: every platform reply that is not a success goes through the package-root helper
`connectors.error_for_status(status: int) -> tuple[str, bool]` (L3), which returns `(code,
retryable_hint)`:

| status | `error.code` | `retryable_hint` |
|---|---|---|
| 400, 422 | `validation` | false |
| 401, 403 | `auth` | false |
| 404 | `not_found` | false |
| 429 | `rate_limited` | true |
| any other 4xx (409 included), any 5xx, any other non-2xx | `unknown` | true |

An unparseable success body is `unknown` too. The codes `validation`, `auth`, `not_found` and
`rate_limited` are the **definitive rejections** the ledger's `side_effects` rule relies on (below);
each is a whole-request refusal on the platforms served here, and a connector whose platform can
partially apply a request answered with one of those statuses (e.g. a partial-failure mode) must
not turn that mode on, or maps that reply to `unknown` in its module docstring and tests it.
**`retryable` (DECIDED HERE; one formula).** On a VerifyResult and a `read()` error it is the
`retryable_hint` (or the exception table's value, §6.3). On every result `idempotent_apply` returns
from an **outcome** (the body's result, or the result it builds when `body` raises) it is exactly
`retryable = hint and (side_effects is False)` — a conjunction, never a replacement. **`hint` is
exactly the `retryable` value in the result `body` returned** (so `idempotent_apply`, which never
sees an HTTP status, never calls `error_for_status`): `idempotent_apply` overwrites it with
`body_result["retryable"] and side_effects is False`. `body` (`_apply_body`) sets that value as
follows: `error_for_status`'s hint for a status reply; the §6.3 exception table's value for a mapped
exception (`CredentialUnavailable`, `HostNotAllowed`, … are `false`); `true` for a `transport`
`ConnectionError`; and **`false` for every refusal the connector builds itself** — `before_mismatch`,
`before_missing`, `currency_mismatch`, `approved_mismatch`, `shared_budget`, `not_found`/`not_owned`
(parent, in-account or addressed-object ownership reads), the F4 row-field `validation`,
`asset_unbound`, `asset_sha_mismatch`, `source_mismatch` and every other connector-built
`validation`. When `body` raises, `idempotent_apply` builds the result with `hint = true`. `ok: true`
results carry `false`. L3 test: an `apply` whose before re-check fails `before_mismatch` →
`retryable: false`; RED when a connector-built refusal carries `true`. So a 400 reply is `false` (hint false; side effects `false`), a 429 reply is `true` (a
definitive rejection, so side effects `false`, and hint true), and a 500 after `started` is `false`
(side effects `"unknown"`). Results `idempotent_apply` builds
without an outcome keep their literal values: `partial_prior_attempt` `false`, `lock_timeout`
`true`, `test_mode_real_state` and `redact_key_unavailable` `false`, and a replay copies the recorded
result. L3 tests: a 400 reply to the write POST after its `started` line → `retryable: false`; a
429 reply → `retryable: true`; a 500 after `started` → `false`; each RED under the replacement
reading `retryable = (side_effects is False)`. **Transport
failures:** a `ConnectionError` raised by `_transport` (§6.5b) is caught where it surfaces —
`read()` returns `ok: false`, `errors[0] = {"code": "unknown", "message": "transport"}`;
`verify_read` returns `error.code = "unknown"`, `retryable: true`; `dedupe_probe` returns
`"unknown"`; inside `_apply_body` it maps to `error.code = "unknown"`, message `transport` (and
`idempotent_apply`'s own catch covers any escape, below). L3 tests: `error_for_status` over each
row of the table; a 500 reply to the write POST after its `started` line → `side_effects:
"unknown"`, and the retry (a `none`-dedupe row) is refused `partial_prior_attempt`; a
`ConnectionError` inside `read()` and inside `verify_read` → the mapped result, no exception
escapes; each RED when its connector maps the status itself.

**Row field set (F4).** `plan`/`apply` consider **only** the keys in the matched row's
`after_fields`/`after_value_fields` (03_schemas.md §3.4.1, 02_act.md §2.8 check 10). Any other key
in `after` is a contract violation: `error.code = "validation"`, message `after_field_not_allowed`
(02_act.md §2.8 check 10's code), no write. act.py already refused
it at propose/authorize, so this is the connector-side backstop. A connector never maps an arbitrary
`after` key onto a platform field. **One named exception: the forced PAUSED status of paused-create
rows** (next paragraph), a row constant the connector sends although it is not an `after` field.

**Create rows and paused creates (DECIDED HERE; 03_schemas.md §3.2 "Paused creates"; plan §20.13
"a paused campaign's budget is committed only at enable", §20.6).** 
- **Create row.** `connectors.is_create_row(row: object) -> bool` (L3, package root; also imported by
  `runbook_validate`) is `isinstance(row, dict)` **and** (`row.get("self_id")` is a non-empty `str`
  **or** `row.get("action")` ∈ `{"create", "add"}`) (03_schemas.md §3.4.1 `self_id`, "create rows only"; `add` covers
  `google_ads.keyword_add`, which has no own-object id). It **never raises**: a read context's
  `row == {}`, a malformed validator input, or a non-dict → `False`. It is the one test; §6.2's "Create rows"
  re-check, `dedupe_probe` and §6.4's before-check all use it. L3 test: `is_create_row({})`,
  `is_create_row({"self_id": 3})` and `is_create_row(None)` → `False`, no exception.
- **Paused-create rows.** `connectors.PAUSED_CREATE_ROWS = frozenset({"google_ads.campaign_create",
  "meta.campaign_create", "meta.adset_create"})` — every create row whose object can carry a budget
  or deliver paid traffic, as 03_schemas.md §3.2 enumerates them. L3 test: every id exists in
  `tier_table.json` and `is_create_row` holds for it; and every create row of `google_ads`/`meta`
  whose `after_value_fields` contains a budget key (`budget_amount`, `budget_type`) is in the set
  (RED when a new budget-carrying create row is added without joining it).
- **API.** `apply` of a paused-create row **always** sends the platform's paused status on the
  create call as a row constant (google_ads `campaign.status = PAUSED`; meta `status = PAUSED`), the
  one field a connector sends that is not in `after_fields`/`after_value_fields`; an `after.value`
  that names a status is already an F4 violation. Relying on a platform default is forbidden (the
  Google Ads API's default status for a created campaign is UNVERIFIED here and irrelevant, since the
  status is always sent). `plan()` lists it in the op's `fields` (`"status": "PAUSED"`), so the
  dry-run shows it.
- **Verify.** `verify_read` of a paused-create row reads the created object's configured status
  and maps it by the committed-status table (§6.2 "Committed amount of a status row"). Anything but
  `paused` — `live`, `removed`, unmapped, or the status field absent — is a **failed verify**:
  `ok: false`, `error: null`, `diff` naming `status`. What A2's `verify` does next is specified by
  03_schemas.md §3.2 (fail-verify rule for paused creates) and plan §20.6 (an urgent `$` card
  proposing the pause, with a push notification), not here; this contract only guarantees the
  `ok: false`, `error: null` shape that triggers it.
- **Browser:** §6.4 "Mandatory paused status (paused-create rows)" and validator code
  `create_status_unpinned` (§6.4b).
L tests (google_ads, meta): the create request body recorded in `FakeHTTP.calls` carries status
`PAUSED` (RED when the constant is removed); a create whose fixture read-back reports `ENABLED`
(meta `ACTIVE`) → `verify_read` `ok: false`, `error: null`, `diff` on `status` (RED when
`verify_read` does not read the status). A2 test: that verify failure writes `PAUSE.<system>` on the
first failure.

**Never agent-executable (DECIDED HERE; plan §20.6/§20.8).** A `_nomatch` action (03_schemas.md
§3.4.2), and any money row that is in no connector's `write_rows` and has no `writes[<row>]` entry in
its runbook, is never executed by an agent. `is_api_executable` is false for it. `execute` refuses it
with `error.code = "validation"`, message `not_agent_executable`, and no connector call.
**`execute` and `verify` re-check executability themselves (DECIDED HERE):** before
building `target_ids` or making any connector call (for `execute`, after the `gtm_ai` refusal, the
op binding and the pause step, §6.3; for `verify`, right after the `gtm_ai` refusal), each runs `r = api_executable_reason(actx, action)`
(§6.3); `r is not None` → `error.code = "validation"`, message `r` exactly, `retryable: false`:
`not_agent_executable` for a `_nomatch`/never-executable action as above, a `manifest_*` code,
`no_connector` (`connector_for` returned None), else `not_api_executable` (browser `access`, a
non-`gsm:` ref, a row outside `write_rows`, no `write.py`). The message is the helper's return
value, never re-derived by the caller. No act.py caller is trusted to have checked first.
`ticket --write` refuses it with exit 3 `not_agent_executable` (R9). No generic executor exists that
maps free `after` keys. After signature the **operator** makes the change, and it is recorded with
`record-external --kind owner_executed` plus a verify read (02_act.md §2.11).

**Idempotency (IMP-11; DECIDED HERE).** Key = `action_id`. The ledger is implemented once, by
`connectors.idempotent_apply` (L3, package root). Every `write.py` `apply` is exactly
`return connectors.idempotent_apply(ctx, action, idempotency_key, body=_apply_body, probe=dedupe_probe)`,
and no connector writes its own ledger.
```python
def idempotent_apply(ctx, action, key, *, body, probe) -> dict   # WriteResult
```
- `ctx.dry_run` true → `ValueError` before any lock or line (dry runs call `plan` only; act.py
  `--dry-run` never reaches `apply`).
- **Test mode (00_global_paths.md §1.1 (3)).** Before any lock or line, `idempotent_apply` calls
  `gtm_env.refuse_real_state(ctx.R, ctx.home)` — the one choke point 00 defines (same_root/samefile,
  casefolded compare, `real_expand`, registry rules; a no-op outside test mode) — and never
  re-implements the comparison. `gtm_env.RealStateRefused` → `ok: false`, `error.code =
  "validation"`, message `test_mode_real_state`, `retryable: false`, `side_effect: "none"`, no
  ledger line and no `body` call. act.py maps it to exit 3 `test_mode_real_state`. L3 test (test
  mode on, `gtm_env.real_root` monkeypatched to a tmp dir): a ctx whose `R` names that dir with a
  case-variant spelling → refused, no ledger file created; RED when a `normpath` comparison replaces
  the `refuse_real_state` call.
- Ledger `ST/connector_idem/<connector>.jsonl` under `fcntl.flock(LOCK_EX | LOCK_NB)` on
  `ST/connector_idem/<connector>.lock`, retried every 0.1 s for up to 30 s. `<connector>` is exactly
  `ctx.manifest["connector"]` (the connector name, §6.1), not the tier system. The directory is
  created on first use with `mkdir(parents=True, mode=0o700)`; the `.jsonl` and `.lock` files are
  created with mode `0600` (`os.open(..., O_CREAT | O_APPEND | O_WRONLY, 0o600)`; 00_global_paths.md §1.3
  still says `<system>`; R12 aligns it). On timeout the result is `error.code = "lock_timeout"`, `retryable: true`,
  and no line is appended. The lock is held from the decision below through the terminal line.
- **Result fields the wrapper owns:** `idempotency_key` is set by `idempotent_apply` on every result
  it returns (replay, refusal, outcome); `body` never sets it. `before_observed` is set by `body`
  (the values its before re-check read; `{}` when it read none) and is copied unchanged.
- Line: `{"ts", "idempotency_key", "attempt", "kind": "started|outcome|replay|refused", "ok": bool|null, "side_effects": true|false|"unknown", "result": WriteResult|null}`.
  `ts` is the 00_global_paths.md §0.3 UTC timestamp (Z, second precision) from `ctx.now()`.
  `attempt` = 1 + the number of earlier `outcome` lines for the key (`null` on `replay`/`refused`).
  `replay` and `refused` lines carry `side_effects: false` (the call they record made no platform
  request; a refusal's reason about **earlier** attempts lives in its `result.error` and in the
  WriteResult's `side_effect`, above).
  A `started` line is exactly `ok: null`, `result: null`, `side_effects: "unknown"`, with `attempt`
  from the same formula (so it equals the attempt of the `outcome` line that follows it).
  `result` on `outcome`/`replay`/`refused` lines is always `connectors.redact_content(result,
  key=connectors.redact_key(ctx.state_dir, ctx.pack))` ("Persisted and printed content" above),
  never the raw WriteResult. The key is obtained **before** the lock and before any line: its
  `ValueError("redact_key_unavailable")` → `ok: false`, `error.code = "validation"`, message
  `redact_key_unavailable`, `retryable: false`, `side_effect: "none"`, no ledger line, no `body` call.
- **Every `apply` call that gets the lock appends exactly one terminal line** (`outcome`, `replay`
  or `refused`), written in a `finally`. A replay copies `ok: true`, and a refusal records `ok: false`.
- **`started` line.** `http_request` calls `ctx.mutation_hook()` before sending any request with
  `mutating=True` (§6.5b). On its first call in an attempt, the hook appends and `fsync`s a
  `started` line (`side_effects: "unknown"`) before the request leaves the process.
- **Hook lifecycle.** `idempotent_apply` sets `ctx.mutation_hook` **immediately before** calling
  `body(ctx, action)` and resets it to `None` in the same `finally` that writes the terminal line.
  It is `None` on entry (a ctx arriving with a hook already set → `ValueError`, no line), while
  `probe(ctx, action)` runs (so a mutating request from a probe raises `MutationOutsideApply`, which
  the probe maps to `"unknown"`), and after `apply` returns or raises (so a reused ctx is never
  mutation-capable). L3 test: a probe that issues a `mutating=True` request → `"unknown"` →
  `partial_prior_attempt`, zero transport calls; after `apply` returns, `ctx.mutation_hook is None`;
  each RED when the hook is set earlier or never cleared.
- **Decision**, over the earlier lines for the key:
  (a) an `outcome` line with `ok: true` → return its recorded result and append `replay`. No platform call.
  (b) otherwise, an `outcome` line with `side_effects: true` → `partial_prior_attempt`, `retryable:
  false`, append `refused`. No probe and no write.
  (c) otherwise, an `outcome` line with `side_effects: "unknown"`, or a `started` line with no
  `outcome` line of the same attempt (the process died mid-attempt) → call `probe(ctx, action)`.
  `"absent"` (the platform provably does not hold the change) → continue as (d). `"present"`,
  `"unknown"`, or a manifest `dedupe` of `none` → `partial_prior_attempt`, `retryable: false`,
  append `refused`, no write.
  (d) otherwise (no earlier line, or only `side_effects: false` failures) → a normal attempt: call
  `body(ctx, action)`. **A recorded failure is never replayed**, so an action re-authorized from
  `failed` (02_act.md §2.4 `AUTHORIZE_FROM`) really retries.
- **Outcome `side_effects`:** `true` when the result's `applied_ops` or `platform_refs` is non-empty.
  Otherwise `"unknown"` when this attempt wrote a `started` line **and** either `body` raised, or
  `error.code` ∉ {`rate_limited`, `auth`, `validation`, `before_mismatch`, `not_found`} (the
  platform's definitive rejections, produced only by `error_for_status` from a reply status or by a
  refusal raised before the request left the process). This covers a transport error, a timeout, a
  5xx, a 409, an unparseable reply after a mutating request, and a **3xx reply to a mutating
  request** (`RedirectRefused` with `sent=True` maps to `error.code = "unknown"`, message
  `redirect_refused`, never `validation`: §6.3 exception table; only `sent=False` maps to
  `validation`). Otherwise `false` — including an `ok: true` result
  with empty `applied_ops` and `platform_refs` (a no-op; `side_effects` is never null). If `body` raises, the result is
  `ok: false`, `error.code = "unknown"` (message = the exception class name), and `retryable` follows
  the §6.2 formula (hint `true`, so `true` exactly when `side_effects` is `false`).
- **Dedupe probes (manifest `dedupe`, one per write row).** `client_tag`: the create call embeds
  `gtm:<action_id>` in a non-public name, label or internal-note field, and `dedupe_probe` searches
  for it. `state_equals_before`: `dedupe_probe` re-reads the fields the row changes and returns
  `"absent"` only when they all equal `action.before` under the before re-check rules below. For a
  **create row** (`connectors.is_create_row(row)`, above; `before: {}`, e.g. `google_ads.keyword_add`) it is an absence check: `"absent"`
  only when a platform read shows no object matching the row's `after` identifying fields under
  `ctx.account` (e.g. no keyword with the same text and match type in the ad group), `"present"` when
  one exists, `"unknown"` on a read error. For a **status row** (§6.2 "Committed amount of a status
  row") it compares the mapped status and configured ceiling as that paragraph defines.
  `none`: no probe, so an unknown prior attempt always blocks. A public item with no hidden field
  (e.g. a GBP or Facebook post) never carries a visible marker. Its row uses `none`. Recovery is a
  read followed by `revert` or a new action, never a blind re-apply.

**Target resolution (FID-02; plan §6.3/§7).** `plan`/`apply`/`verify_read` address a platform
object **only** from `ctx.account` (its account keys, below) plus `ctx.target_ids`. A connector never parses
`target_ref` and never reads an `after.value` key outside the row's `id_fields` to find an object.
Create rows create only under `ctx.account`. `connector_dispatch.execute`/`verify` build
`ctx.target_ids` as follows, and any failure is `error.code = "validation"` with the named message
and **no connector call**:
1. **Re-run check 1.** `checks.identity_check(actx, action)` (A1, 02_act.md §2.2b): check 1 of 02_act.md §2.8
   alone, re-run at execute time against the pack at HEAD. Any failure → `identity_recheck_failed`.
2. **Ids from `target_ref`:** `system_names.target_ids(tier_system, action.target_ref) -> dict[str, str]`
   (03_schemas.md §3.22; its per-system grammar table is R1 item 1; the same function check 1(c)
   uses on its values). **Account keys (DECIDED HERE; R1 item 8):** the platform-native account
   identifiers of `ctx.account` come from `system_names.account_keys(tier_system, account) -> dict[str, str]`
   (R1), never from `account_id` blindly, because real packs store a display id there (the
   committed OtherCompanyB fixture, which holds synthetic stand-ins only, has ga4 `account_id:
   "G-ABCD123456"`, a measurement id, with the property in `ga4_property_id: "100000004"`; gtm
   `account_id: "GTM-ABCD1234"`, the public tag, with the container in `gtm_container_id:
   "100000002"` and `gtm_account_id: "1000000001"`). **No contract file carries a real account id**
   (`tools/` is in the mirror publish set): examples and test targets name the committed fixture's
   values, read from the fixture, never a literal real value. Every
   account-level key that `target_ids` yields (`system_names.ACCOUNT_LEVEL_KEYS`, R1 item 1: `customer_id`, `ad_account_id`,
   `page_id`, `ig_user_id`, `location_id`, `property_id`, `gtm_account_id`, `container_id`,
   `site_url`, `site_host`, `listing_url`) must be present in `account_keys(...)` and equal it after
   `system_names.normalize_account_id(tier_system, …)` on both sides (e.g. google_ads strips dashes,
   so the fixture's pack value `100-200-3000` equals `customers/1002003000`), else `target_account_mismatch`. A key the
   account cannot supply (e.g. a ga4 account without `ga4_property_id`) → `account_key_missing`
   (and `company.py validate` refuses such a pack, R1 item 8). **Brand-scoped systems:** for
   `website_wordpress` the grammar yields `site_host` (the URL's host) plus `page_ref`, and
   `account_keys` yields the account's `site_host` (a required account field for that system, R1);
   for listing systems and `lsa` the grammar yields `listing_url` and `account_keys` yields the
   account's own `listing_url`. So a remodeling-brand account can never address the restoration
   brand's site or listing: the host or URL differs → `target_account_mismatch`.
   **`gbp_account_id` (DECIDED HERE).** 03_schemas.md §3.22's `accounts/<a>/locations/<id>` form
   also yields `gbp_account_id`, which is not an account-level key, names no object below the
   location, and is bound by no pack value. `connector_dispatch` deletes it from the step-2 dict, so
   it never reaches `ctx.target_ids`, never satisfies step 5, and no connector addresses by it (a
   GBP location is addressed by `location_id` under `ctx.account` only). R21 asks 03 to stop yielding
   it, as R1 item 1 specified. A2 test: `accounts/999/locations/<own location id>` resolves with
   `target_ids == {"location_id": "<own location id>"}`; RED when `gbp_account_id` is kept.
3. **Ids from `after.value`:** for each key `k` of the row's `id_fields` map (03_schemas.md §3.4.1)
   present in `after.value` (or, when absent there, in `before.value`), `target_ids[k] = value`.
4. **Collision:** a key produced by both step 2 and step 3 with different values → `target_id_conflict`.
4b. **Account-level allowlist, whatever the source (dispatch-level).** After steps 2–4, every key
   of the final `target_ids` that is in `system_names.ACCOUNT_LEVEL_KEYS` — including one that
   arrived only through step 3 (an `after.value`/`before.value` `id_fields` key such as
   `property_id`, `customer_id` or `page_id`) — must be present in `account_keys(tier_system,
   ctx.account)` and equal it after `normalize_account_id` on both sides, else
   `target_account_mismatch`, no connector call. The per-connector ownership read below is a second
   layer, never the only one. A2 test: an action whose `after.value` carries another property's
   `property_id` (no step-2 value for it) → `target_account_mismatch`, zero `FakeHTTP.calls`; RED when
   step 4b is removed.
5. **Scope:** a row with `object_scope: "object"` (03_schemas.md §3.4.1, R1) must end with at least
   one key in `target_ids` besides the account-level keys, else `target_missing`. Money rows whose
   `after` carries no id (e.g. `google_ads.campaign_budget_edit`, `campaign_enable`, `campaign_pause`)
   are `object` rows, and their object comes only from step 2 (e.g. `customers/<cid>/campaigns/<id>`).
6. **Cross-system links (`*.asset_link`, `V(target_system, target_id, link_type)`).**
   `after.value.target_id` must be in the pack's identity bucket for `after.value.target_system`:
   `system_names.identity_bucket(target_system)` names the `identity_allowlist` key (e.g. `ga4` →
   `ga4_property_ids`), together with the `account_keys` values of accounts whose normalized system
   is `target_system` (R1). A value outside the bucket → `link_target_not_in_pack`. check 1 already
   made such an action class `never` with a card (03_schemas.md §3.4.4 validator rule), so this is
   the execute-time backstop. The connector then confirms ownership **through the target system's
   own connector**. **Only a target that is one of the pack's own `accounts[]` entries can be
   linked by an agent (DECIDED HERE; plan §6.3/§7 positive allowlist):** `connector_dispatch` picks
   `account_t` = the unique `accounts[]` entry `a` whose normalized tier system is `target_system`
   and whose `system_names.account_keys(target_system, a)[k_t]` equals
   `normalize_account_id(target_system, target_id)`, where `k_t` is the one account-level key
   naming that system's account (google_ads `customer_id`, meta `ad_account_id`, facebook `page_id`,
   instagram `ig_user_id`, gbp `location_id`, ga4 `property_id`, gtm `container_id`,
   search_console `site_url`; any other `target_system` → `not_owned`). Zero or several such
   entries → `not_owned` (an id listed in the `identity_allowlist` bucket but registered as no
   `accounts[]` entry passes check 1, but is never linked by an agent: the operator links it, or the
   pack registers the account first). `connector_dispatch` builds `ctx_t` with the **same internal builder
   `execute`/`verify` use** (`_build_ctx`, §6.3): `account = account_t`,
   `credential = credential_getter(ctx_t, account)`, `target_ids = {}`, under whichever
   admission the calling act.py command already passed (the GTM-session proof, or the holds-job
   proof `prove_holds_job` for `act.py run-holds` in the `com.oversight.gtm.holds` job,
   07_notices_schedules.md §7.2). It never calls `build_read_ctx`, which is the collector/CLI entry
   only (§6.3) and would refuse `not_gtm_session` in the holds job. It then calls
   `read(ctx_t, "owns", {"target_ids": {k_t: normalize_account_id(target_system, target_id)}})` —
   the account-level key in its **normalized** form, which the read-scope rule (§6.3 "Account scope
   of every read") admits because it equals `account_keys(target_system, ctx_t.account)[k_t]` by
   construction (a bare id is never passed as a free `"id"`). The `owns` op returns
   `{"owned": true}` iff that key equals `ctx_t.account`'s key **and** a platform read of that
   object with `ctx_t`'s credential succeeds (the credential can reach it: e.g. GA4
   `properties/<id>` metadata, Ads `customers/<id>`); a platform `not_found`/`auth` → `{"owned":
   false}`. Anything but `{"ok": true, "data": {"owned": true}}` → `error.code = "not_found"`,
   message `not_owned`, and zero write calls. A2 tests (a pack DERIVED from the OtherCompanyB fixture
   in the test, never the committed file edited: its `ga4` account changed to `access: api` with
   `credential_ref: gsm:gtm-other-company-ga4`; test mode on, the §6.3 "A2 test seam" (a) and (b)): a
   `ga4` asset link to the fixture's `ga4_property_id` (`100000004`) resolves `ctx_t` to that
   account and, with a fixture `owns` reply, is owned (RED when `owns` is called with the bare
   `{"id": …}` form, which the read-scope rule refuses); an in-bucket id that is no `accounts[]`
   entry → `not_owned`, zero write calls; and, negative case, the COMMITTED fixture (its `ga4`
   account `access: browser`, `credential_ref: browser:playwright-gtm`) with the real
   `credential_getter` (seam (a) unset) → `not_owned`, zero write calls; plus a direct
   `credential_getter` test on that committed account (step 0's direct-call rule) → `not_gsm_ref`.
7. **In-account ids (DECIDED HERE; 03_schemas.md §3.4.1 `in_account` part (2) "positive binding at
   execution", `nested_id_paths`; requests/03_schemas.md R61 (b); plan §6.3/§7 "create/modify
   anything whose account_id/page/location/domain fails §7 → NEVER", §20.2).** Check 1 admits an
   `in_account` id only syntactically; this step is its positive binding, and it is the
   connector's, run in `plan()` and again in `apply` **before any mutating request** (never left to
   the platform to reject). The set `IA` of ids to bind is: every key `k` of the row's `id_fields`
   whose kind is `in_account` and that is present in `after.value` (or, when absent there,
   `before.value`), **except** the row's `self_id` on a create row (the object being created has no
   owner yet); plus every leaf of `after.value`/`before.value` matched by a `nested_id_paths`
   pattern (03 §3.4.1) whose kind is `in_account` (e.g. `targeting.custom_audiences[*].id`,
   `targeting.excluded_custom_audiences[*].id`, `targeting.exclusions.custom_audiences[*].id` on
   meta, `tags[*].blockingTriggerId[*]` on gtm_api), and every `in_account` id reached through the
   §3.4.1 tag-id scan. Ids already ownership-read by the addressed-object or create-parent rule below
   need not be read twice. For each id in `IA` the connector performs an **ownership read under
   `ctx.account`** with `ctx`'s credential and `connectors.http_request(..., mutating=False)`: the
   platform must report the object under `ctx.account`'s account keys — google_ads: the object's
   resource name reads as `customers/<account_keys.customer_id>/…` (a `googleAds:search` for that
   resource under that customer returns exactly one row); meta: a read of the object's
   `account_id` (a custom audience, ad creative, pixel or ad-set-level object) equals
   `account_keys.ad_account_id` after `normalize_account_id`, or, for a page-owned object, its
   owning page equals `account_keys.page_id`; ga4: the parent is `properties/<account_keys.property_id>`;
   gtm_api: the parent is `accounts/<gtm_account_id>/containers/<container_id>/…`; any other
   connector names its read per id kind in its module docstring and tests it. A read that reports
   another account, does not resolve, or errors → `error.code = "not_found"`, message `not_owned`,
   `retryable: false`, **zero write calls**, `side_effect: "none"` (no `started` line: the read is
   not mutating). Each connector's module docstring lists, per `in_account` id kind it can meet
   (top-level and nested), the exact ownership read it uses. L tests (google_ads, meta; each RED
   when the nested resolution is removed): a `meta.adset_create` whose
   `after.value.targeting.custom_audiences[0].id` fixture read reports another ad account's
   `account_id` → `not_owned`, zero write calls in `FakeHTTP.calls`; a `meta.adset_targeting_edit`
   whose `excluded_custom_audiences[0].id` read fails → `not_owned`; a google_ads edit that attaches
   an asset or conversion-action id whose resource resolves under another `customers/<id>` →
   `not_owned`, zero write calls. **Browser twin:** the runbook's `account_breadcrumb` step (§6.4).

**Status:** the §6 side of FID-02 is complete (step 7 lands requests/03_schemas.md R61 (b) and the
§6.4 `account_breadcrumb` step lands R28). The finding stays open in OPEN_FINDINGS.md only
until the last outside pieces land. **Landed (verified 2026-09-27 in the target files):**
`id_fields` (key→kind map), `object_scope`, `commits_on_enable` and the `identity_for:target_system`
kind (03_schemas.md §3.4.1/§3.4.4); the `target_ref` grammar table, the account-level key list,
`target_ids`, `normalize_account_id`, `identity_bucket`, `account_keys`, `CSA_GSM_PROJECT` and
`CSA_SLUG` (03_schemas.md §3.22); `checks.identity_check` (02_act.md §2.2b); check 1's positive
allowlist with the account-level/object-level split, `normalize_account_id` on both sides and
`card_on_refuse` (02_act.md §2.8 check 1; R2, R14); the named module constant
`system_names.ACCOUNT_LEVEL_KEYS` in 03_schemas.md §3.22's code block (R21 item 1); and the §3.22
`target_ids` comment on check 1(c) (R14 / R21 item 3; landed in different wording, which states
the same rule). **Pending:** dropping `gbp_account_id` from the gbp grammar row (R21 item 2; §3.22
still yields it, and `IDENTITY_KEYS` includes it), and the `company.py validate` requirements of
R1 items 8 and 11 (`site_host`, `listing_url`, `ga4_property_id`, `gtm_account_id` +
`gtm_container_id` on the accounts that need them; the brand-suffix conflict). Until they land, the
`account_key_missing` refusal of step 2 is the runtime guard for an account that lacks a key.

Before any write to an addressed object, `apply` reads it and confirms the platform reports it under
`ctx.account`'s account keys (e.g. the Ads `customers/<customer_id>/…` resource name; for a GA4
object, the parent `properties/<account_keys.property_id>`; for GTM, `accounts/<gtm_account_id>/containers/<container_id>`;
the GBP location's account). An object that does not resolve there → `error.code = "not_found"`,
message `not_owned`, `retryable: false`, no write. A2 test against the committed OtherCompanyB pack
fixture (`tests/test_other-company_pack_fixture.py`, synthetic ids): a ga4 action on
`properties/<the fixture's ga4_property_id>` (`properties/100000004`) and a gtm action on
`accounts/<gtm_account_id>/containers/<gtm_container_id>` (`accounts/1000000001/containers/100000002`)
resolve with no `target_account_mismatch`; the same actions with `account_keys` reverted to
`account_id` go RED. The test reads those three values from the fixture, never from a literal.

**Parents of a create are ownership-read too (DECIDED HERE).** For a create row
(`is_create_row(ctx.row)`), every object-level key of `ctx.target_ids` that names the created
object's parent — the row's `id_fields` keys, i.e. its required ids (e.g. `meta.adset_create`'s
`campaign_id`, a google_ads keyword or ad create's `ad_group_id`, taken from `after.value` by target
resolution step 3) — is ownership-read under `ctx.account` by the rule above **before** the create
call, in `apply` (and already in `plan()`). A parent the platform reports under another account, or
that does not resolve → `error.code = "not_found"`, message `not_owned`, `retryable: false`, zero
write calls. Isolation never depends on the platform rejecting the create. L tests (google_ads,
meta): a `meta.adset_create` whose `campaign_id` fixture read reports a different `account_id`, and
a google_ads keyword create whose `ad_group_id` resolves under another `customers/<id>` →
`not_owned`, zero write calls in `FakeHTTP.calls`; RED when the parent read is removed.

**Money binding (every effective-money action; DECIDED HERE; plan §20.8 "its `new_absolute_value`
must equal the action's").** An action is **effective-money** when
`tiers.effective_class(actx, action, row, check_failures) == "money"` (03_schemas.md §3.4.3: a
`money` row, **or** `spend_delta_monthly ≠ 0` on a `money: false` row, or no row match), called with
exactly `row = tiers.match_row(actx, action)` (02_act.md §2.2b; the matched row or the synthetic
`_nomatch` row) and `check_failures = checks.identity_check(actx, action)` (the same list target
resolution step 1 computes; call it once and reuse it). Why that list and never `[]`: 03 §3.4.3's
rule depends on check 1 alone (`never` iff the row is NEVER or check 1 failed; it reads
`checks.identity_result` for `shared`), so check 1 is the only check that can move the class, and
the other checks are authorize-time policy that act.py already recorded. A class of `never` is
refused for **every** action, money or not, by class-step clause 0 (§6.3 "The class step of
`execute`"): `validation`, message `identity_recheck_failed`, no connector call (the same code as
target-resolution step 1).

**Signed revert children (DECIDED HERE; plan §20.8 "`revert --approval <card id>` (§6.8) means a
signed approval for that revert action"; 02_act.md §2.4 `revert` routing (2)/(3) and step 2 (a);
02 §2.2b `pauses.blocking` rule (3)).** A **signed revert child** is an action whose folded record
`rec = store.fold(actx).get(action["action_id"])` has a non-null `revert_of` and whose `authorized`
event (the one 02 §2.2b's signed-revert exemption reads; the folded record's spelling of that event and
of the last `failed` event's `ts` is pending, requests/06_connectors.md R38) carries a non-null
`approval_request_id`.
The approval binding below runs for every effective-money action **and** every signed revert child
(money or not), so the one exemption `pauses.blocking` grants a signed child is never taken on a
caller's word: for a non-money child the signature is the amount-less request over the child's
`after_digest` (03_schemas.md §3.7 case (v), 05_approver.md §5.5 step 3b), and steps 1–3 below bind
it exactly as they bind a money payload. For a non-money signed child step 4 leaves `ctx.approved`
None (no amount exists to write; the row's `after` fields are written as for any non-money row).

**The connector layer verifies the approval itself (plan §20.8 "only the operator can produce
it").** `connector_dispatch.execute(actx, action, *, dry_run=False, approval=None, op="execute")` takes the
**full verified approval payload** (the 12-key dict `approvals_verify.verify` returned to act.py,
05_approver.md §5.5 step 3a), never a bare amount. For an effective-money action, or a signed revert
child (above), with `dry_run` false, its money step (the **approval binding**) (after the op binding, the pause step and `api_executable_reason`, §6.3; before the class step, `_build_ctx`, target resolution or any
connector call) is:
1. `approval is None` → `error.code = "validation"`, message `approval_missing`, `retryable: false`.
2. `payload = approvals_verify.verify(actx, action, stage="execute")` — run **here**, against the
   HEAD public key and the approval record on disk for this action, whoever the caller is. `verify`
   performs no nonce operation (05 §5.5 step 5: `reserve`/`consume`/`release` are separate calls, so
   act.py's own verify → reserve → execute → consume sequence is unchanged, and `run-holds`/`revert`
   use the same stage-`execute` expiry rule; R19 asks 05 to state both in its API block). An `ActError` whose `exit_code` is `EXIT_TRUST`
   propagates unchanged (act.py maps it to exit 11); any other `ActError` →
   `validation`, message `approval_missing`.
3. `canon(payload) != canon(approval)`, or `payload["action_id"] != action["action_id"]`, or
   `payload["system"] != action["system"]`, or `normalize_account_id(tier_system,
   payload["account_id"]) != normalize_account_id(tier_system, action["account_id"])` →
   `validation`, message `approved_mismatch`.
4. Only then, for an effective-money action, `ctx.approved = {"new_absolute_value":
   payload["new_absolute_value"], "unit": payload["unit"]}` (a non-money signed revert child keeps
   `ctx.approved` None). `_build_ctx` accepts `approved` only from this step; no caller-supplied dict
   ever reaches `ctx.approved`.
A2 tests (signed revert children; each with a real test key pair at the tmp HEAD, zero
`FakeHTTP.calls` on every refusal): a non-money signed child under a breaker `PAUSE.gbp` with
`approval=None` → `approval_missing`; with another action's valid payload → `approved_mismatch`;
with its own valid amount-less payload → executes with exactly one connector write call. Each RED
when the approval binding is skipped for non-money signed children.
Every refusal above has **no connector call** (not even `plan`). A collector, a `/tmp` wrapper
script or any other in-process importer of `gtmlib.connector_dispatch` therefore cannot make a `$`
write with a hand-built amount (04_hooks.md §4.2 rule a is a speed bump, not the control), and an
act.py bug that passes another action's payload is caught.
- **Missing approval:** covered by steps 1–2 above.
- **Equality (every row whose after keys are `new_absolute_value`, `unit`).** Before any mutating
  call `apply` fails `error.code = "validation"`, message `approved_mismatch`, no write, unless
  `ctx.approved.new_absolute_value == after.new_absolute_value` (two-decimal strings) and
  `ctx.approved.unit == after.unit`. What `apply` then sends depends on the row kind, (a) or (b);
  the two are disjoint, and every such row is exactly one of them.
- **(a) Amount rows** — rows with those after keys that are **not** status rows (below): the budget
  and limit edits (`google_ads.campaign_budget_edit`, `meta.campaign_budget_edit`,
  `meta.adset_budget_edit`, `meta.spending_limit_edit`, `lsa.budget_edit`, `L.paid_budget_edit`,
  the `{thumbtack,angi}` lead-cap edits, …). `apply` writes exactly
  `ctx.approved.new_absolute_value` / `ctx.approved.unit` (converted per the connector's unit table,
  below) into the object's budget/limit field and never `after`.
- **(b) Status rows** (§6.2 "Committed amount of a status row": pause, stop, remove and
  enable-bound rows). The signed amount is **not** a value to write: a pause's `"0.00"` is the
  committed amount after the pause (plan §20.13 "a pause is amount 0"), and an enable's value is the
  configured ceiling already on the platform. `apply` sends **only** the platform status change and
  never writes any budget, amount, limit or bid field: google_ads `campaign.status` = `PAUSED`
  (pause/stop), `ENABLED` (enable-bound), `REMOVED` (remove, via the documented remove operation);
  meta `status` = `PAUSED` (pause/stop), `ACTIVE` (enable-bound), `DELETED` (remove, or the
  documented delete verb); any other connector names its status field and values in its module
  docstring and tests them. The signed amount is used only for the equality check above and the
  status-row before re-check (§6.2 "Committed amount of a status row" and the Execute bullet of
  "Enable-bound actions").
- L tests (google_ads, meta; and every other connector with a status row): the `FakeHTTP.calls`
  body of the mutating request of a signed pause holds the status field (`PAUSED`) and **no** budget,
  amount or limit field (`amount_micros`, `daily_budget`, `lifetime_budget`, `spend_cap`, …); the
  same for a signed enable (`ENABLED`/`ACTIVE`) and a signed remove. Each goes RED when `apply`
  writes `ctx.approved.new_absolute_value` on a status row (a pause would write a `$0.00` budget, an
  enable would rewrite the budget).
- **Amount-less effective-money actions** (05_approver.md §5.5 null rule (ii)/(iii): an
  `amount_required: false` row, or `spend_delta_monthly ≠ 0` on a `money: false` row): `approval`
  must still pass steps 1–3 (the signature over `after_digest`), `ctx.approved` is set, and its
  `new_absolute_value`/`unit` are `null`; `apply` writes only the row's `after` fields.
- A2 falsification tests (each with a real test key pair installed at the tmp HEAD, 05 §5.7): (a) an
  effective-money `google_ads.campaign_budget_edit` with `approval=None` → `approval_missing`, zero
  `FakeHTTP.calls`; (b) a hand-built `approval={"new_absolute_value": "500.00", "unit": "USD/day",
  …}` with no signed record on disk for the action → `approval_missing`, zero `FakeHTTP.calls`, RED
  when the in-connector `approvals_verify.verify` (step 2) is removed; (c) a validly signed payload of
  **another** action passed while executing an action that holds its own valid approval →
  `approved_mismatch`, zero calls, RED when step 3 is removed; (d) with `approvals_verify.verify`
  monkeypatched to return a payload of `"40.00"` for an action whose `after.new_absolute_value` is
  `"45.00"` → `apply`'s `approved_mismatch`, zero write calls (the connector backstop); (e) a
  `money: false` row with `spend_delta_monthly = 20` and `approval=None` → `approval_missing`. Each
  goes RED when its check is reverted.

**Enable-bound actions (FID-03; plan §20.13 "committed only at enable").** The scope is
03_schemas.md §3.2 "Enable actions" (the schema owner's definition; 05_approver.md §5.5 step 3b
uses the same scope; R15 asks 02_act.md §2.6 rule 5a and §2.8 check 8 to narrow to it). An action is **enable-bound** when it is
effective-money **and** either (i) its matched row carries **`commits_on_enable: true`**
(03_schemas.md §3.4.1 — the flag name 03 defines and 05 pins; today `google_ads.campaign_enable`,
`lsa.account_enable`, `meta.campaign_enable`, `meta.adset_enable`, `{thumbtack,angi}.lead_enable`
and the `L.paid_enable` rows), or
(ii) it is a **`_nomatch`** action whose `action` verb is `enable`, `resume` or `unpause`. A table
row whose verb is `enable` but which has no `commits_on_enable` flag is **not** enable-bound: today
`google_ads.auto_apply_enable` (`amount_required: false`) and `paid_api.usage_enable`
(`current_value: zero`) carry no pre-configured ceiling and are governed by their own row flags
(03_schemas.md §3.2). Code reads the flag only as `row.get("commits_on_enable") is True`; no other
spelling exists. For an enable-bound action, `after.new_absolute_value`/`after.unit` are the object's
**configured committed ceiling** and its period. Period → `unit`: daily budget `USD/day`, weekly
`USD/week`, monthly `USD/month`, lifetime or total budget `USD/once`, per-lead cap `USD/lead`. A
ceiling with none of these periods → `validation`, no write. An enable-bound action without an
amount is refused by act.py (`enable_amount_required`, 02_act.md rule 5a) before any 06 code runs.
- **Currency (every money row, not only enable rows).** A connector serving any money row reads the
  platform account's currency code (e.g. Ads `customer.currency_code`, Meta `account.currency`) in
  `plan()` and again in `apply`. Unless it equals the pack's `spend.currency`, and that equals
  `USD`, the result is `validation`, message `currency_mismatch`, no write.
- **Fresh read at authorize (API accounts), keyed by tier system, not row.** Every connector that
  lists `committed_ceiling` (§6.1) exposes it for **every budgeted object kind its tier systems'
  `target_ids` grammar can address** (google_ads campaign/campaign budget/account; meta account, campaign,
  ad set; listings/lsa account), not only for objects of a `commits_on_enable` row
  (`params` = `{"target_ids": {...}}`; `data` =
  `{"new_absolute_value": "45.00", "unit": "USD/day", "currency": "USD", "status": "paused|live|removed", "budget_owner": null}`
  (`budget_owner` below; the same keys as 03_schemas.md §3.2's `committed_ceiling` snapshot contract),
  where `new_absolute_value`/`unit` are the **configured** ceiling whatever the status). `authorize`
  (A1, 02_act.md rule 5a) calls `connector_dispatch.read_committed_ceiling(actx, action)` (A2), which
  works for any enable-bound action, `_nomatch` included: it resolves `connector_for(tier_system)`
  from the action's system and `target_ids` by steps 1, 2 and 4 of target resolution (steps 3/5/6
  need a row and are skipped when there is none), matches the account with `match_account(pack,
  tier_system, brand, action.account_id)` (tier system and brand derived as in §6.3 "Account
  matching"), and calls `read(ctx, "committed_ceiling", …)`. It raises `CeilingUnreadable(<code>)`,
  the message being exactly one of this closed set: `no_connector` (no connector),
  `op_not_listed` (the connector does not list the op), `not_api_account` (the account is not
  `access: api` with a `gsm:` ref), `account_unmatched` (`match_account` raised), `target_unresolved`
  (a target-resolution step failed), `no_budget_object` (the object kind has no budget of its own,
  no budget-owning parent and no budget-owning children, below), `shared_budget` (the object's
  budget is a Google Ads shared budget, §6.2 "Shared budgets"), `read_failed` (the read returned
  `ok: false` or raised), or `currency_not_usd`. `data` always carries `budget_owner`: `null` for an
  object that owns its budget, else one of the two forms below. **Meta CBO ad set (campaign budget
  optimization):** an ad set with no budget of its own takes its committed ceiling from its
  **parent campaign's** budget and period; the `committed_ceiling` read returns that campaign's
  `new_absolute_value`/`unit` with `"budget_owner": "campaign:<campaign_id>"`. **Meta ABO campaign
  (ad-set budgets; 03_schemas.md §3.2 "Enable actions", requests/03_schemas.md R36):** a campaign
  with no budget of its own takes as its committed ceiling the **sum** of the configured budgets of
  its ad sets whose own configured `status` is `ACTIVE` (the committed-status table below), with
  `"budget_owner": "adsets:<id>,<id>,…"` (ids sorted ascending as decimal strings); zero such ad
  sets → `"0.00"`. Ad sets of differing periods are not summed: the read returns `ok: true` with
  `unit: null` and `"units": [<each distinct unit, sorted>]` in `data`, and `authorize` refuses
  `enable_value_mismatch` (03_schemas.md §3.2; the operator enables per ad set instead). The API
  enable before-check (§6.2 Execute bullet) recomputes the same parent budget or the same sum over
  the same rule and compares it. No enable-bound action on a Meta system without an API account
  serving `committed_ceiling` is agent-executed at all (§6.2 "Agent-executable enables" below): the
  operator enables it (`record-external --kind owner_executed`), whether the campaign is CBO or ABO.
  (Meta CBO/ABO semantics UNVERIFIED against current Graph API docs — the
  L1 meta connector's first fixture capture confirms the field names before `meta.campaign_enable`
  or `meta.adset_enable` is served.) The result
  **overwrites** `before.value.current_absolute_value`/`unit` before the approval request is created
  (02_act.md rule 5a, `ceiling_read` event). So a `_nomatch` enable-bound action on an API account
  gets its signable value from this read.
  `authorize` calls `read_committed_ceiling` **only while no approval request exists for the
  action** (02_act.md rule 5a); once a request exists the signature binds the value and the Execute
  re-read below is the guard. `read_committed_ceiling` itself creates nothing and appends no event.
- **Fresh read at authorize (browser accounts).** Each runbook of a system with a
  `commits_on_enable: true` row, or with any budgeted object that can be enabled (§6.1 `read_ops`
  rule), has a mandatory `read_paths[]` entry with id `committed_ceiling` (§6.4). gtm-analyst walks
  it under a read ticket, and `act.py snapshot` records it as a snapshot named `committed_ceiling`,
  carrying the same `data` keys, for the action's object. `authorize` uses that record through
  `before.evidence_ref` exactly as 02_act.md rule 5a defines: listed in a `snapshot_recorded` event
  whose `run_id` equals the authorizing run's `ctx.run_id` (never a hand-placed file), for this
  account and object, ≤ 24 h old. **This snapshot serves `authorize` (and the signing of a
  `_nomatch` enable-bound action) only; it never makes a browser enable agent-executable.**
- **Agent-executable enables (DECIDED HERE; 03_schemas.md §3.6 `enable_not_agent_executable`,
  04_hooks.md §4.1 rule 9d).** An enable-bound row is agent-executable — by API or by a browser
  write ticket — **only when its tier system also has an `access: api` account (with a `gsm:` ref)
  whose connector serves `committed_ceiling`**, because the write ticket's enable binding needs an
  API read-back of the committed ceiling, which a browser snapshot cannot give. Otherwise (e.g.
  OtherCompanyB's browser-only Meta) the operator performs the enable after signature and it is
  recorded with `record-external --kind owner_executed` plus a verify read (02_act.md §2.11). The
  §6.4 "Ceiling rows" runbook entries exist for the systems that have that API read-back; a runbook
  may carry them on a browser-only system, but `ticket --write` refuses such a row
  (`enable_not_agent_executable`, 03 §3.6), so no worker builds a browser enable flow expecting it
  to be ticketed there.
  **Stops are never enable-bound (`requests/05_approver.md` R84, amended wave1e):** a row whose
  authored `resulting_status` ∈ {`paused`, `removed`} (03_schemas.md §3.4.1 — never decided by verb
  tokens) cannot carry `commits_on_enable`, so it never meets this rule: a signed stop with a
  connector `write_rows` or runbook `writes[<row>]` entry is agent-executable under an ordinary
  signed write ticket, and it is operator-executed only as `not_agent_executable` (no write entry).
- **No signable value.** If neither source yields a value (no connector op, no qualifying snapshot, a
  read error, or currency ≠ USD), `authorize` refuses `ceiling_unreadable` and creates no approval
  request (02_act.md rule 5a). **Mismatch:** when the read value or period differs from
  `after.new_absolute_value`/`after.unit`, `authorize` refuses **`enable_value_mismatch`** (the one
  code; 02_act.md rule 5a and 03_schemas.md §3.2 use it) and creates no approval request. The
  operator is never asked to sign a value the platform was not just seen to hold.
- **Execute.** `plan()` performs the same read and returns it in `requires_before`. `apply`
  re-reads it immediately before the enable call and fails `before_mismatch` (no write) unless all
  three agree: the configured value equals `after.new_absolute_value`, equals `ctx.approved.new_absolute_value`,
  and equals `before.value.current_absolute_value` (compared as two-decimal strings, below); its unit
  equals `after.unit`; and its currency is `USD`. (`ctx.approved` None is already refused
  `approval_missing` by the money binding above.) The browser equivalent is §6.4's ceiling
  before-check. A `_nomatch` enable-bound action is never agent-executed (above): after signature
  the operator performs it (`record-external --kind owner_executed`), so only authorize's read binds it.

**Shared budgets (DECIDED HERE; plan §20.6/§20.8 "sign exactly what is committed").** A Google Ads
campaign budget with `campaign_budget.explicitly_shared = true` is drawn on by every campaign
attached to it, so a signed change addressed to one campaign (`customers/<cid>/campaigns/<id>`)
would change what other, possibly live, campaigns can spend, and the operator's signed display names
only one. This contract does not serve shared budgets:
- `google_ads.campaign_budget_edit` and every google_ads enable-bound row: `plan()` and `apply`
  read the campaign's `campaign_budget` (`explicitly_shared`); `true` → `error.code = "validation"`,
  message `shared_budget`, `retryable: false`, zero write calls. The operator edits a shared budget
  directly (recorded with `record-external --kind owner_executed`, 02_act.md §2.11).
- `read(ctx, "committed_ceiling", …)` on a campaign with a shared budget returns `ok: false`,
  `errors[0] = {"code": "validation", "message": "shared_budget"}`, and `read_committed_ceiling`
  raises `CeilingUnreadable("shared_budget")`, so `authorize` refuses `ceiling_unreadable` and no
  approval request is created.
- Pause, stop and remove rows are **not** refused on a shared budget: they change only the one
  campaign's status and write no budget field ("Money binding" (b)), and their committed amount
  rule is unchanged.
L tests (google_ads): with a fixture campaign whose budget reads `explicitly_shared: true`, a signed
`campaign_budget_edit` and a signed `campaign_enable` → `validation` `shared_budget`, zero write
calls; the `committed_ceiling` read → `ok: false` `shared_budget`; a signed `campaign_pause` of the
same campaign makes the status call only; each RED when the `explicitly_shared` check is removed.

**Committed amount of a status row (DECIDED HERE; plan §20.13 "a pause is amount 0").** A **status
row** is any money row whose `action` verb is `pause`, `stop` or `remove` (signed amount `"0.00"`,
03_schemas.md §3.4.4: `google_ads.campaign_pause`, `meta.adset_pause`, and the **stop rows** of
03_schemas.md §3.4.4 — `meta.campaign_pause`, `lsa.account_pause`, `L.paid_pause`,
`{facebook,instagram}.boost_stop`, `{thumbtack,angi}.lead_pause` — whose `stop` verb is a pause for
every rule below; and the paid-object remove rows `google_ads.campaign_remove`,
`meta.campaign_remove`, `meta.adset_remove`, `lsa.account_remove`, `L.paid_remove`, which implement
plan §20.6 "removing a paid campaign"), or an enable-bound row (`{thumbtack,angi}.lead_enable`
included, by its `commits_on_enable` flag). `meta.campaign_budget_edit` is an ordinary amount row,
never a status row. Its
status is mapped by the connector's **committed-status table** (below; `REMOVED`/`DELETED`/`ARCHIVED`
→ `removed`). The object's **committed amount** is
`committed_amount(status, configured) = configured if status == "live" else "0.00"`. Uses:
- **Pause, before re-check:** mapped status must be `live` and the configured ceiling must equal
  `before.value.current_absolute_value` (the amount being stopped), else `before_mismatch`.
- **Remove, before re-check:** mapped status ∈ {`live`, `paused`} and the configured ceiling equals
  `before.value.current_absolute_value`, else `before_mismatch` (an already-removed object is never
  re-removed blindly).
- **Enable-bound, before re-check:** the Execute bullet above (configured ceiling, status not
  consulted for the amount; a `live` object is already enabled → `before_mismatch`).
- **`verify_read` (all three):** `observed.new_absolute_value = committed_amount(status, configured)`,
  so a completed pause or remove observes `"0.00"` and a completed enable observes the configured
  ceiling. For a remove, a platform `not_found` on the object read counts as status `removed`
  (observed `"0.00"`, `ok: true`), never as a read error. **The configured ceiling is verified
  too (DECIDED HERE):** a status row writes no amount ("Money binding" (b)), so `verify_read`
  also reads the configured ceiling into `observed.configured_ceiling` and puts
  `expected.configured_ceiling = before.value.current_absolute_value` (a two-decimal string); any
  difference → `ok: false`, `error: null`, `diff` naming `configured_ceiling`. The one exception is a
  remove whose object read is `not_found` (nothing left to read). So a "pause" that instead zeroed
  the budget (status still `live`, or `paused` with ceiling `0.00`) fails verify on the API path;
  the browser path verifies the same way through the `committed_ceiling` read path (§6.4
  `status_unpinned`). L tests (every connector with a status row): a fixture whose post-pause read
  shows status `PAUSED` and a configured budget changed from `45.00` to `0.00` → `ok: false`, `diff`
  on `configured_ceiling`; RED when `verify_read` compares only the committed amount.
- **`dedupe_probe` (`state_equals_before`):** pause → `"absent"` iff the status is still `live` and
  the configured ceiling still equals `before.value.current_absolute_value`; remove → `"absent"` iff
  the status is **not** `removed` (and the object still resolves) and the configured ceiling still
  equals it, `"present"` when `removed` or `not_found`; enable → `"absent"` iff the status is still
  `paused` and the configured ceiling equals it; else `"present"`; a read error → `"unknown"`.
- **Committed-status table (per connector; tested).** google_ads `campaign.status` `ENABLED`→`live`,
  `PAUSED`→`paused`, `REMOVED`→`removed`. **meta reads the configured `status`, never
  `effective_status`, for committed amount, `verify_read` and `dedupe_probe`:** `ACTIVE`→`live`,
  `PAUSED`→`paused`, `DELETED`/`ARCHIVED`→`removed`. For an ad set it is the ad set's own configured
  `status` that commits its ceiling, whatever its parent's state. Meta's transient **effective**
  states right after an enable (`IN_PROCESS`, `PENDING_REVIEW`, `WITH_ISSUES`, `CAMPAIGN_PAUSED`,
  `ADSET_PAUSED`, `PREAPPROVED`) are therefore never consulted here: a configured `ACTIVE` object is
  `live` for committed-amount purposes whatever its effective status. (The meta status lists are
  UNVERIFIED against current Graph API docs; the L1 meta connector's recorded fixtures pin them.)
  `effective_status` is used **only** by the `campaign_state` rule below (a row's `when` condition).
  Any other connector documents its table in its module docstring.
- **Browser remove rows (§6.4):** the before-check carries the amount, period and currency entries
  like every money amount row, plus a status entry whose value is a JSON array of the literal live
  and paused labels (`"<status field>": ["<live label>", "<paused label>"]`), satisfied when the
  on-page label equals one of them (the only place an `expect.before` value may be an array). A
  runbook carrying a remove row also carries the `committed_ceiling` read path
  (`ceiling_read_missing`, §6.4b, covers remove rows as status rows).
L tests (every connector with a pause or remove row): a signed pause of a live campaign configured
at `45.00` → `apply` makes the pause call, then `verify_read` returns `ok: true`,
`observed.new_absolute_value == "0.00"`, and A2's `verify` does **not** call
`breakers.record_verify_failure`; RED when `observed` reports the configured budget instead. A
signed remove of a live campaign at `45.00` → `verify_read` `ok: true`, observed `"0.00"`, no
`record_verify_failure`; RED when remove rows are not status rows. (meta) a signed
`meta.adset_enable` whose ad set then reads configured `ACTIVE`, effective `PENDING_REVIEW` →
`verify_read` `ok: true` at the configured ceiling; RED when committed amount reads
`effective_status`. (meta) a CBO ad set's `committed_ceiling` read returns the parent campaign's
budget; RED when it raises `no_budget_object`. (meta) an ABO campaign whose `ACTIVE` ad sets carry
`20.00` and `25.00` USD/day (a third, `PAUSED`, at `99.00`) reads `45.00` USD/day with
`budget_owner: "adsets:<a>,<b>"`, and its enable before-check fails `before_mismatch` when one
active ad set's budget changes before the call; RED when the read raises `no_budget_object` or sums
the paused ad set. One whose active ad sets mix USD/day and USD/once → `unit: null`, `units` listing
both.

**Ad content read and verify (DECIDED HERE; 03_schemas.md §3.4.4 "Enabling ads", §3.22
`NON_INBOX_SNAPSHOTS`; requests/03_schemas.md R62 (b); plan §5 day-after verification).** FID-09 ad
copy goes public at enable with no further content gate, so the connector proves the published ad
equals the reviewed `after`.
- **Read op `ad_content`** (`google_ads`, `meta`; listed in both manifests' `read_ops`, not in
  `inbox_class_ops`). `params = {"target_ids": {...}}` (§6.3 "Account scope of every read": the
  campaign, ad-group/ad-set or ad id under `ctx.account`). `data = {"items": [{"kind": "ad" |
  "asset", "id": str, "status": "<platform configured status, verbatim>", "content": {<exactly the 03
  §3.4.4 item content keys of that kind>}, "item_digest": "sha256:<hex>"}], "content_digest":
  "sha256:<hex>"}`, where the item set is 03 §3.4.4's table for the target's object kind (an ad
  target → that ad only), the content keys are exactly 03's closed sets (Google ad: `headlines`,
  `descriptions`, `final_url`, `path1`, `path2`; Meta ad: `primary_text`, `headline`, `description`,
  `link_url`, `call_to_action_type`, `page_id`, `image_hash`; asset: `asset_type`, `text`,
  `final_urls`, `phone_number`, `image_hash`), a key the platform does not return is present with
  value `null`, `item_digest = "sha256:" + sha256(_canon({"kind", "id", **content}))` and
  `content_digest = "sha256:" + sha256(_canon(sorted([{"kind", "id", "item_digest"}], key=(kind,
  id))))` — 03 §3.4.4's formulas verbatim (03 is the source; an L3 test asserts both equal gtmlib's
  implementation on a fixed corpus). Items sort by `(kind, id)`; `items` is `[]` when the target
  delivers nothing.
- **`verify_read` of every ad create/edit row** (`google_ads.ad_create*`/`ad_text_edit*`,
  `meta.ad_create*`/`meta.ad_edit*`, and `google_ads.asset_create*`/`asset_edit*` for kind `asset`)
  reads the written object with the same code path as `ad_content` and returns
  `observed.content_digest` = that object's `item_digest` and `expected.content_digest` = the same
  formula over `{"kind", "id": <the object's id from platform_refs or ctx.target_ids>, **E}`, where
  `E` holds each content key with the value it must have after the write: `after.value[k]` when `k`
  is an `after_value_fields` key of the row, else `before.value[k]` (an edit leaves other keys as
  they were), else `null`. Any difference → `ok: false`, `error: null`, `diff` naming
  `content_digest` (so A2 counts it toward the breaker like any verify mismatch). 02_act.md §2.9
  records `observed.content_digest` as the item's `item_digest` in the `verified` event (03 §3.4.4
  "Content-bound").
L tests (google_ads, meta; each RED when `verify_read` stops comparing content): a fixture ad whose
read-back headline differs from `after.value.headlines[0]` → `verify_read` `ok: false`, `error:
null`, `diff` on `content_digest`; an identical read-back → `ok: true`. L test: `read(ctx,
"ad_content", …)` on a fixture campaign holding two ads returns both items sorted and a
`content_digest` equal to the formula; RED when the digest is taken over the raw reply.

**Before re-check (DECIDED HERE).** `apply` reads the current state of every field it will change
and fails `before_mismatch` (no write; this also covers §20.9 Agency collisions) on any difference,
under these rules:
- **Money rows:** the platform's current amount equals `before.value.current_absolute_value`
  (status rows: per "Committed amount of a status row" above). **Unit conversion is per connector**
  and part of its tested code: google_ads micros → `Decimal(micros) / 10**6`; meta minor units
  (cents for USD, as its budget fields return them) → `Decimal(minor) / 100`; any other connector
  documents its conversion in its module docstring and tests it. If the converted value has a
  non-zero remainder below a cent, the result is `before_mismatch`. Otherwise it is quantized to
  `0.01` (ROUND_HALF_UP) and compared as a two-decimal string. The same conversion runs in reverse
  when `apply` writes `ctx.approved.new_absolute_value` (amount rows only; a status row writes no
  amount, "Money binding" (b) above).
- **`V` rows:** for each `k` in `after.value` that is not an `id_fields` key, `current[k] == before.value[k]`.
  A `k` present in `after.value` but missing from `before.value` → `error.code = "validation"`,
  message `before_missing`, no write (never treated as "nothing to compare").
- **`TXT` rows:** `current text == before.text` after whitespace normalization (strip, then collapse
  runs of whitespace to one space). The comparison is case-sensitive.
- **Create rows** (`before: {}`): absence check only (the object to create does not already exist).
  There are **no money create rows** (03_schemas.md §3.4.4 "`meta.campaign_create` and
  `meta.adset_create` are not money rows"; requests/03_schemas.md R38 (c)): the paused-create rows
  (§6.2 "Create rows and paused creates") are T1 `money: false`, so `ctx.approved` is None for them
  and the money binding does not run. `apply` writes `after.value.budget_amount` (a two-decimal
  string, converted per the unit table of the money-row rule above) as the **paused** object's
  budget, and its before re-check is the absence check only. That budget commits nothing until the
  signed enable, whose ceiling read (§6.2 "Enable-bound actions") re-reads exactly what was
  created.
- **Lists:** targeting fields (`geo_targets`, `language_targets`, keyword lists, `recommendation_types`)
  compare as sets. Every other list or dict compares exactly after canonical JSON (00_global_paths.md §0.3).
- **`campaign_state`:** for a row whose `when` names `campaign_state` (02_act.md §2.8 check 11), the
  real status is re-read and mapped. google_ads `campaign.status` `ENABLED`→`live`, `PAUSED`→`paused`;
  meta **`effective_status`** (here only — not for committed amount, which reads the configured
  `status`, "Committed amount of a status row" above — so a campaign paused at a parent level reads
  paused) `ACTIVE`→`live`, `PAUSED`/`CAMPAIGN_PAUSED`/`ADSET_PAUSED`→`paused`. `REMOVED`,
  `DELETED`, `ARCHIVED`, the transient states (`IN_PROCESS`, `PENDING_REVIEW`, `WITH_ISSUES`) or any
  unmapped status → `before_mismatch`. The mapped value must be in the row's `when.campaign_state`.
  Each connector's status table is part of its code and tested. **Paused-create rows
  (03_schemas.md §3.2 "Paused creates"; requests/03_schemas.md R38 (e)):** for
  `google_ads.campaign_create` and `meta.campaign_create` there is no campaign to re-read; the
  row's fixed PAUSED status (§6.2 "Create rows and paused creates") satisfies `campaign_state:
  paused`, so the connector neither re-reads nor fails on the object's absence. For
  `meta.adset_create`, whose `campaign_state` names the **parent** campaign, the connector re-reads
  that parent (its `campaign_id` from `ctx.target_ids`, target resolution step 3) and applies the
  rule above; the ad set itself is created PAUSED whatever the parent's state. L test (meta): an
  `meta.adset_create` under a parent whose `effective_status` is `DELETED` → `before_mismatch`, zero
  write calls; a `meta.campaign_create` makes no status read before its create call.

### 6.3 Dispatch, account matching and credentials (A2 `connector_dispatch.py`)

```python
from connectors import CredentialUnavailable      # DEFINED in the connectors package root (L3): the same shape as its siblings,
                                                  #   class CredentialUnavailable(Exception):
                                                  #       def __init__(self, code: str): super().__init__(code); self.code = code
                                                  # (message = .code = the reason code; mapping code reads .code, never str(e));
                                                  # connector_dispatch re-exports it, so connectors never import gtmlib (no cycle)
class ReadCtxCompanyError(Exception):             # named so it never collides with the committed company.CompanyError (no .code)
    def __init__(self, code: str, message: str = ""):
        super().__init__(code if not message else f"{code}: {message}"); self.code = code
    # read.py maps it to exit 13. read.py main's imports, complete: sys, json, pathlib, argparse and os (stdlib),
    # connectors (the package root: CredentialUnavailable), gtm_env (BadFakeNow, RealStateRefused), system_names,
    # and — inside main() only — `from gtmlib import connector_dispatch` (§6.1 import rules)
class ReadCtxAccountError(Exception):             # build_read_ctx's match_account failure; .code ∈ {"account_missing","account_ambiguous"}
    def __init__(self, code: str): super().__init__(code); self.code = code   # read.py maps it to exit 3, nothing written to --out
class CeilingUnreadable(Exception):               # message = .code = exactly one reason code of §6.2 "Fresh read at authorize (API accounts)"
    def __init__(self, code: str): super().__init__(code); self.code = code
class ManifestUnavailable(Exception):             # §6.1 "Manifest load source"; .code ∈ {"manifest_not_at_head","manifest_dirty","manifest_unreadable"}
    def __init__(self, code: str): super().__init__(code); self.code = code   # read.py maps it to exit 3 (order below)
ERROR_KINDS: frozenset[str]                       # (requests/02_act.md item 92) every `error.code` a WriteResult/VerifyResult can carry
                                                  # and every read() errors[].code: {"before_mismatch", "auth", "rate_limited",
                                                  # "not_found", "validation", "partial_prior_attempt", "lock_timeout", "unknown",
                                                  # "credential_unavailable"}
VALIDATION_MESSAGES: frozenset[str]               # every `error.message` that accompanies code "validation" (plus the prefix
                                                  # "paused:" of the pause step, matched by startswith, never listed per name):
                                                  # internal_system_no_connector, static_not_connector, bad_op, card_not_approved,
                                                  # card_subject_mismatch, card_predates_event, hold_pending, cancelled,
                                                  # not_authorized, baa_missing, hipaa_prohibited, not_agent_executable,
                                                  # not_api_executable, no_connector, manifest_not_at_head, manifest_dirty,
                                                  # manifest_unreadable, approval_missing, approved_mismatch, account_missing,
                                                  # account_ambiguous, identity_recheck_failed, target_account_mismatch,
                                                  # account_key_missing, target_id_conflict, target_missing, link_target_not_in_pack,
                                                  # upload_source_missing, shared_budget, currency_mismatch, before_missing,
                                                  # after_field_not_allowed, asset_unbound, asset_sha_mismatch, source_mismatch,
                                                  # test_mode_no_live, test_mode_real_state, redact_key_unavailable,
                                                  # host_not_allowed, redirect_refused, mutation_outside_apply, out_not_allowed,
                                                  # bad_params.
                                                  # A2 test: every message a refusal path in this file names is a member (a static
                                                  # scan of connector_dispatch.py and the connectors package for "validation" results);
                                                  # RED when a new message is added without joining the set.
def load_manifest(R: Path, connector: str) -> dict                 # §6.1; HEAD bytes only; raises ManifestUnavailable; never returns a partial dict
def check_secret_target(R: Path, H: Path, company: str, name: str) -> tuple[str, str]
    # credential steps 1-3 below, factored as the ONE refusal helper shared by credential_getter and
    # secret_sink (§6.6): reads H/.claude/gtm/connectors.json at HEAD (`git -C <H> show HEAD:./.claude/gtm/connectors.json`,
    # the home-relative `./` form, §6.3 credential step 1). `name` is the BARE secret name (the
    # credential_ref with its "gsm:" prefix removed, §6.3 credential step 2 "Secret name form"); it
    # refuses a name that does not fullmatch gtm-<company>-[a-z0-9-]+ (a still-prefixed "gsm:…" name
    # therefore fails as secret_not_per_company), matches oauth-google-*, or lives in an agency /
    # cross-company / unreadable-denylist project. Returns (gsm_project, gcloud_account); raises
    # CredentialUnavailable(<reason>) with the step-1..3 reason codes. No gcloud call, no network.

# In every signature below, `actx` is act.py's Ctx (02_act.md §2.2, from make_ctx); `ctx` is a ConnectorCtx.
def connector_for(tier_system: str) -> ModuleType | None
    # None when system_names.connector_system(tier_system) returns None OR its value is not one of the ten
    # §6.1 connector names (checked against that list, never by catching ImportError); else import connectors.<name>
def match_account(pack, tier_system, brand, account_id=None) -> dict   # below; raises LookupError("account_missing"|"account_ambiguous")
def api_executable_reason(actx, action) -> str | None
    # None = API-executable. Otherwise the ONE refusal message, by this precedence (the first that applies):
    # "gtm_ai" system → "internal_system_no_connector" (see below); "website_static" → "static_not_connector" (§6.1
    # "Systems no connector serves"); load_manifest(actx.R, <the connector name>)
    # raised → its manifest_* code (reachable only when connector_for names a connector); connector_for(...) is
    # None → "no_connector" (so the two are mutually exclusive); the action is "never agent-executable" (§6.2) → "not_agent_executable";
    # else any of: the manifest's `access` lacks "api", matched account.access != "api", its credential_ref does not
    # start "gsm:", no write.py, the row id not in manifest write_rows, match_account raised → "not_api_executable".
    # Never raises.
def is_api_executable(actx, action) -> bool
    # exactly api_executable_reason(actx, action) is None — except system "gtm_ai" → True: it is API-path (no ticket,
    # no browser) but INTERNAL — act.py's `execute` handles it
    # itself (verify, reserve, consume, record completed; 05_approver.md §5.5 "AI-spend cap") and never calls
    # connector_dispatch.execute/verify for it. If either is called for system gtm_ai anyway → validation,
    # message "internal_system_no_connector", no connector call (A2 test; RED when it falls through to match_account).
    # A2 test: one action per reason → execute's message equals api_executable_reason's value (a manifest_dirty
    # manifest yields "manifest_dirty", not "not_api_executable"; a manifest whose access is ["browser"] yields
    # "not_api_executable" even for an access-api account); RED when execute re-derives the message.
def execute(actx, action, *, dry_run: bool = False, approval: dict | None = None, op: str = "execute",
            card_id: str | None = None, upload_source: Path | None = None) -> dict
    # approval: the full 12-key payload act.py's approvals_verify.verify returned (05_approver.md §5.5 step 3a);
    # execute RE-VERIFIES it itself (§6.2 "Money binding", for effective-money actions and signed revert children).
    # op: the op of the calling act.py command — "execute" (execute), "run_holds" (run-holds), "revert" (revert
    # step 2), "lead_append" (lead-append); BOUND to the action by "Op binding" below (a value outside those four, or
    # one the action does not qualify for → validation "bad_op", no connector call). card_id: optional; the card the
    # connector verifies is ALWAYS the one recorded on the action's folded `authorized` event (never the caller's
    # word); a non-None card_id that differs from it → validation "card_not_approved", no connector call.
    # upload_source: *_upload rows only — the absolute realpath of source_ref that act.py's execute re-checked under
    # 03_schemas.md §3.4.1 home_data immediately before this call (requests/06_connectors.md R37); None otherwise.
    # Order: gtm_ai / website_static refusal → OP BINDING → PAUSE STEP (below) → api_executable_reason (§6.2) →
    # approval binding (§6.2 "Money binding" steps 1-4, for effective-money actions and signed revert children) →
    # CLASS STEP (below) → upload_source check (§6.2 "Asset and upload bytes") →
    # _build_ctx (account = match_account(...) as in "Account matching"; LookupError →
    # WriteResult validation "account_missing"/"account_ambiguous", no connector call) → target_ids (§6.2) → plan.
    # dry_run=True → returns plan()'s dict {"ops", "requires_before"} (redacted on a hipaa pack, §6.2 "Persisted and
    # printed content"; not a WriteResult) and never calls apply; the approval binding is skipped on a dry run (no write).
    # A refusal before plan returns the refusal WriteResult. dry_run=False → apply(...) and returns its WriteResult.
def verify(actx, action) -> dict                            # VerifyResult; same gtm_ai/website_static/api_executable_reason/_build_ctx/target_ids
                                                            # steps, then verify_read (no op binding, pause step, approval binding or class
                                                            # step: a verify is a read)
def read_committed_ceiling(actx, action) -> dict            # §6.2 "Enable-bound actions". Returns the read's `data` EXACTLY (the §6.2 keys
                                                            # new_absolute_value, unit, currency, status, budget_owner, plus `units` on
                                                            # the ABO mixed-units reply, where `unit` is null — returned as is, so authorize
                                                            # refuses enable_value_mismatch); never the whole read() result. Raises
                                                            # CeilingUnreadable(<code>) on every listed code, never returns a partial dict
def credential_getter(ctx, account) -> Callable[[], dict[str, str]]
def build_read_ctx(slug: str, tier_system: str, brand: str | None, account_id: str | None = None) -> ConnectorCtx
def _build_ctx(actx, tier_system, account, *, action: dict | None = None, dry_run=False, approved=None,
               target_ids=None, upload_source: Path | None = None) -> ConnectorCtx
    # internal; the ONE ConnectorCtx builder behind execute, verify, read_committed_ceiling, §6.2 step 6's ctx_t
    # and build_read_ctx. It performs no admission check of its own: its callers run inside an act.py command
    # that already passed its admission (GTM-session proof or prove_holds_job), except build_read_ctx (below).
    # `approved` is passed only by execute's approval-binding step 4 (§6.2); `upload_source` only by execute.
    # FIELD-BY-FIELD (every field, in this order):
    #   company = actx.company; home = actx.H; R = actx.R; state_dir = actx.H / ".claude" / "gtm" / "state" (= ST);
    #   pack = actx.pack (the HEAD pack make_ctx loaded); account = the `account` argument;
    #   tier_system = the `tier_system` argument;
    #   brand = account.get("brand") or system_names.tier_system_and_brand(account["system"], actx.pack)[1]
    #     (the effective brand of "Account matching"; None for the synthetic crm account);
    #   row = tiers.match_row(actx, action) if action is not None else {};
    #   manifest = load_manifest(actx.R, <connector name>);
    #   dry_run = the `dry_run` argument;
    #   now = lambda: gtm_env.now(os.environ) (tz-aware UTC; GTM_FAKE_NOW under GTM_TEST=1 — the same clock the class
    #     step uses);
    #   credential = _no_credential (placeholder, below), replaced after construction;
    #   evidence_dir = the execute/verify form from action["action_id"] when action is given, else the read form
    #     (<tier_system>/<UTC ts>) — §6.3 "Evidence directories" (hipaa packs: under ST/untrusted/);
    #   _secrets = set(); log = connectors.make_log(<that same set object>) (writes to sys.stderr);
    #   target_ids = dict(target_ids or {}) — execute/verify ASSIGN ctx.target_ids after target resolution;
    #   approved = the `approved` argument;
    #   allowed_hosts / allowed_host_suffixes = the §6.1 api_hosts expansion for this ctx (tokens expanded from
    #     ctx.brand and the pack's lead_sink, shared-host parents dropped);
    #   mutation_hook = None; snapshots_dir = actx.paths.snapshots_dir; gcloud_account = gsm_project = None;
    #   _token_cache = {} (or dict(_TEST_TOKEN_CACHE) under test mode only — credential step 0 "A2 test seam" (b));
    #   bound_assets = {a["sha256"]: (state_dir / "assets" / action["action_id"] / a["sha256"]).resolve()
    #     for a in action.get("assets", [])} when action is given, else {};
    #   upload_source = the `upload_source` argument.
    # Callers: execute and verify pass action=<the action>; read_committed_ceiling, build_read_ctx and §6.2 step 6's
    # ctx_t pass action=None (row {}, a read context: ctx_t only calls read(ctx_t, "owns", …)).
    # CONSTRUCT-THEN-ASSIGN: it builds the dataclass with credential = _no_credential (a placeholder that raises
    # CredentialUnavailable("credential_not_bound")), then sets ctx.credential = credential_getter(ctx, account)
    # on the built object, so credential_getter receives a complete ctx (and can fill ctx._secrets). The same order
    # holds for step 6's ctx_t and for build_read_ctx.
```

**Op binding (DECIDED HERE).** The pause step and the class step below read `op`, so `execute`
never takes `op` on the caller's word: right after the `gtm_ai`/`website_static` refusal, for every
call (dry run included), it binds `op` to the action. Any failure → `error.code = "validation"`,
message `bad_op`, `retryable: false`, `side_effect: "none"`, no connector call.
- `op` ∉ {`execute`, `run_holds`, `revert`, `lead_append`} → `bad_op`.
- `lead_append` is valid only when the tier system (derived as in "Arguments from an action") is
  `crm` **and** `tiers.match_row(actx, action)["id"] == "crm.lead_append"`. A `gbp`, `meta`,
  `website_wordpress` or any other action passed with `op="lead_append"` → `bad_op`.
- `revert` is valid only for a **revert child**: the folded store record
  `rec = store.fold(actx).get(action["action_id"])` (02_act.md §2.2b; the same re-read the class step
  uses) exists and has a non-null `revert_of` (03_schemas.md §3.3).
- `run_holds` is valid only for an action that came from a hold: `rec` exists and `rec["hold"]` is
  non-null.
- `execute` is valid for any action (it carries no carve-out).

**The pause step of `execute` (DECIDED HERE; plan §6.4 "a PAUSE file beats any standing approval",
§6.8, §20.8; 03_schemas.md §3.10; 02_act.md §2.2b `pauses.blocking`, §2.4 `revert`).** `execute`
re-checks pauses itself, like the money binding, so an in-process importer of `connector_dispatch`
cannot write to a paused system (04_hooks.md §4.2 rule a is a speed bump, not the control). Right
after the op binding and before `api_executable_reason`, for every call with `dry_run` false:
1. `tier_system, brand` are derived as in "Arguments from an action" below; `cls =
   tiers.effective_class(actx, action, tiers.match_row(actx, action), checks.identity_check(actx,
   action))` (the same call the money binding makes; computed once and reused there and in the class
   step). `signed_child` is true iff the action is a signed revert child (§6.2 "Signed revert
   children": non-null `revert_of` and a non-null `approval_request_id` on its folded `authorized`
   event).
2. `op_b = "execute" if op == "revert" else op`; `p = pauses.blocking(actx, action["system"], cls,
   op_b, brand, action=action)` (02_act.md §2.2b; `action=` is the landed keyword, R29). **`blocking`
   owns every carve-out and every exemption; the connector re-derives none of them:** its scope
   table, brand coverage and resolution order; `lead_append` allowed under `DISABLED`, `PAUSE` and
   `PAUSE.<system>`; **the stop-row exemption** — exactly 02 §2.2b `blocking` rule (2),
   `tiers.is_stop_action(actx, action, row)` over `tiers.STOP_ROWS` read from `tier_table.json`, for
   a breaker-written pause only; and **the signed-revert exemption** — exactly rule (3): for op
   `execute`, a signed revert child is not blocked by `DISABLED`, `PAUSE` or
   `PAUSE.<system>[@<brand>]`. The connector passes `"execute"` for a revert child because 02 says
   op `"revert"` itself never exempts (it is `revert`'s step-1/step-2 routing test); so an
   **unsigned** revert child — one unlocked by an archive card — is refused under **every** pause,
   `DISABLED` and `PAUSE` included (02 §2.4 `revert`: "every revert that executes under `DISABLED`,
   `PAUSE` or `PAUSE.<system>[@<brand>]` is signed"; plan §20.8). Non-`None` → `error.code =
   "validation"`, message `paused:<p>`. An exempted stop is still `money` and an exempted revert
   child is still signed, so the approval binding (§6.2 "Money binding") re-verifies the operator's
   signature for both, and the status-row before re-check still binds
   `before.value.current_absolute_value`.
3. (`cls == "money"` **or** `signed_child`) and `pauses.trust_paused(actx)` → `validation`, message
   `paused:PAUSE.trust` (02 §2.2b: callers check `trust_paused` "for money and for signed revert
   children").
4. `pauses.chain_paused(actx)` (pending, R24: true iff `ST/PAUSE.chain` exists; the dispatcher's
   chain-policy check, 02_act.md §2.3, is not reached by an in-process importer) → `validation`,
   message `paused:PAUSE.chain` — **for every op, `lead_append` included**. A lead that arrives under
   `PAUSE.chain` is written by act.py's `lead-append` to `ST/lead_fallback.jsonl` and replayed into the
   sink by `chain-repair --replay` (plan §6.8; 02_act.md `lead-append`), never sent by the connector.
There is **no card path under a pause**: a card-unlocked revert child reaches the connector only with
no pause covering it (02 §2.4 routing (4)/(5), step 2 (b)), and its card is verified by the class
step (clause 2). Every pause refusal has `retryable: false`, `side_effect: "none"` and **no
connector call** (not even `plan`). `verify` runs no pause step (a verify is a read, and reads are
allowed under every pause). A dry run skips it (no write), exactly as it skips the approval binding.
A2 tests, each RED when the pause step is removed (every refusal with zero `FakeHTTP.calls`):
`PAUSE.gbp` present → a `gbp.hours_edit` `execute` refused `paused:PAUSE.gbp`; the P1 carry-in
`PAUSE.website_wordpress@remodeling` (A0022), and separately a hand-made legacy
`PAUSE.website_remodeling` → a remodeling-site edit refused, a restoration-site edit not; manual
`PAUSE` → refused; `R/schedules/DISABLED` → refused, while a `lead_append` of a `crm.lead_append`
action under `DISABLED` is **not** refused; `S/PAUSE.trust` → a money action refused
`paused:PAUSE.trust`, a non-money one not, **and a signed non-money revert child refused
`paused:PAUSE.trust`** (RED when step 3 checks money only); `ST/PAUSE.chain` → refused, **and** a
`lead_append` refused `paused:PAUSE.chain` (RED when the old carve-out is restored);
`PAUSE.csa_scout` → blocks nothing (record-only).
Revert A2 tests (each with a real test key pair at the tmp HEAD, 05 §5.7): (r1) `op="revert"` of a
**non-money** child unlocked by an approved `revert <child id>` card, under manual `PAUSE` →
refused `paused:PAUSE`, zero calls (RED when the card path under a pause returns); (r2) under a
breaker `PAUSE.gbp`, a signed non-money child (the 02 §2.4 `gbp.hours_edit` revert, amount-less
request over its `after_digest`) → **executes** with exactly one connector write call (RED when the
signed-revert exemption is removed, or when the connector calls `blocking` with op `"revert"`);
(r3) an unsigned child with an approved card under `DISABLED` → refused `paused:DISABLED`, zero
calls (RED when a card admits it); (r4) `op="revert"` of a money revert child under manual `PAUSE`
with its signed approval → not refused, and the approval binding runs.
Op-binding A2 tests (zero `FakeHTTP.calls`, each RED when its binding is removed): `op="lead_append"`
on a `gbp.hours_edit` action under `PAUSE.gbp` → `bad_op`; `op="revert"` on an action with
`revert_of: null` → `bad_op`; `op="run_holds"` on an action with `hold: null` → `bad_op`.
Stop-row A2 tests (mirroring 03 §3.2; each with a real test key pair at the tmp HEAD, 05 §5.7): with
a breaker-written `ST/PAUSE.google_ads` (`created_by: "breaker"`, `ruling_ref: null`) present, (i) the
urgent, signed `google_ads.campaign_pause` (`after.new_absolute_value: "0.00"`) **executes** (the
pause call is in `FakeHTTP.calls`); (ii) a signed `google_ads.campaign_budget_edit` that **raises** the
budget, and (iii) a signed `"0.00"` pause whose `money_brief.urgency` is `normal`, are refused
`paused:PAUSE.google_ads` with zero calls; (iv) the same urgent pause under a `PAUSE.google_ads` with
`created_by: "migration"`, and one with `created_by: "operator"`, is refused; (v) with a fixture tier
table holding a `google_ads` money row with `lanes_key: "none"` whose id is **not** in
`tiers.STOP_ROWS`, an urgent signed lowering on that row under the same breaker pause → refused
`paused:PAUSE.google_ads`, zero calls. (i) goes RED when the exemption is removed; (ii)–(iv) go RED
when it is widened (to non-urgent, raising, or non-breaker); (v) goes RED when the predicate is keyed
on `class`/`lanes_key` instead of `STOP_ROWS`.

**The class step of `execute` (DECIDED HERE; plan §20.2, §20.5.4, §20.5.6, §20.6, §20.7).** The
approval binding re-checks the `$` class inside the connector; the operator-gated classes and the
two prohibitions below get the same treatment, so an in-process importer or an act.py bug cannot
execute them without the operator's decision or the hold. After the approval binding and before
`_build_ctx`, for every call with `dry_run` false (`cls` from the pause step), each refusal
`error.code = "validation"`, `retryable: false`, `side_effect: "none"`, **no connector call**:
0. **Never.** `cls == "never"` (a NEVER-tier row, or check 1 failing at execute time, 03_schemas.md
   §3.4.3) → `identity_recheck_failed`, for **every** op and every class of row, money or not. The
   L3 manifest test additionally asserts that no `write_rows` id of any manifest is a NEVER-tier
   row of `tier_table.json` (RED when one is added), so the refusal is a backstop, never the only
   bar.
1. **Store state.** `rec = store.fold(actx).get(action["action_id"])`. Missing, or any of
   `system`, `account_id`, `target_ref`, `row_id`, `after_digest` differing between `rec` and the
   caller's `action`, or `rec["state"]` ∉ {`authorized`, `executing`} → `not_authorized` (so a
   `cancelled`, `denied`, `refused`, `held` or `failed` action's payload is never executed; act.py's
   `execute`, `run-holds` and `revert` step 2 each record the action `authorized`/`executing` before
   calling, requests/06_connectors.md R30). `op == "lead_append"` skips this clause: `lead-append`
   records no action (03_schemas.md §3.2, `crm.lead_append` is never a proposal).
2. **Cards** — (a) `cls == "shared"` (plan §20.2 "cards, never autonomous"), or (b) `op == "revert"`
   for a child that is **not** a signed revert child and whose folded `authorized` event carries a
   non-null `card_id` (02 §2.4 `revert` step 2 (b): a non-money child unlocked by a card with no
   pause; the pause step has already refused it under any pause). The card is `c` = that
   `authorized` event's `card_id` when `op == "revert"`, else `(rec.get("card") or {}).get("card_id")`;
   the subject is `s = f"revert {action_id}"` when `op == "revert"`, else `f"authorize {action_id}"`.
   A non-None `card_id` argument of `execute` that differs from `c` → `card_not_approved`. Then
   `cards.require_approved(actx, c, s, not_before=t)` (02_act.md §2.2b), where `t` is the `ts` of the
   action's last `failed` event when it has one, else None — the occurrence binding 02 §2.4
   `authorize` applies (after a `failed` event only a card posted strictly later counts, so an act.py
   bug that reuses the old answer is caught here). `c` None, or an `ActError` →
   `card_subject_mismatch` / `card_predates_event` when its code is that, else `card_not_approved`
   (a `deny`, an `unclear` answer, an unanswered card, a consumed card).
3. **`identity`** (`cls == "identity"`; plan §20.7 notify-then-execute). `rec["hold"]` non-null and
   `hold_until` ≤ `gtm_env.now(os.environ)` (so `GTM_FAKE_NOW` applies in tests), else `hold_pending`;
   and `holds.cancel_pending(actx, action_id)` (pending, R30: true iff `S/cancels/<slug>/<action_id>`
   or an `_all.<UTC ts>` marker newer than the last ingest exists, 03_schemas.md §3.11) → `cancelled`.
4. **BAA** (plan §20.5.6). Tier system `crm`, `"hipaa" in pack.get("regulated", [])` and
   `pack["lead_sink"].get("baa_ref")` empty or absent → `baa_missing` (every op, `lead_append`
   included; the 02 `lead-append` gate is not the only one).
5. **HIPAA-prohibited rows** (plan §20.5.4/§20.6; 02_act.md §2.8 check 5). The matched row carries
   `hipaa_prohibited: true` and `"hipaa" in pack.get("regulated", [])` → `hipaa_prohibited`, every op.
**Not re-checked here (stated, so the backstop claim is exact).** The send-time gates of
`recipient_required`/`list_send` rows — quiet hours (pack `timezone`), the `gtm-send-windows` SMS
window, the lead's `sms_consent` and `responded_by` auto-cancel (plan §20.7, 03_schemas.md §3.11
FID-24) — and autonomy demotion are enforced **only** by act.py (02_act.md §2.4 `execute` and
`ticket --write` send-time re-check). The connector does not claim them; an in-process importer that
bypasses act.py and holds a valid authorized record could send outside those windows, a residual
bounded by clauses 1–3 (the action must be authorized and, for identity sends, held and due).
A2 falsification tests, one per clause, each with zero `FakeHTTP.calls` and RED when its clause is
removed: (0) a non-money action whose row is a NEVER-tier row with check 1 passing (fixture tier
table), and one whose check 1 fails at execute time → `identity_recheck_failed`; (1) a `cancelled`
action's payload passed with `op="execute"` → `not_authorized`; (2) a `shared`-class action (e.g. a
GBP phone edit to a declared shared phone) whose `card` was answered `deny` (and one whose card
subject is `authorize <another id>`) → `card_not_approved` (`card_subject_mismatch`); a `shared`
action approved, then `failed`, then executed with the same card → `card_predates_event` (RED when
`not_before` is not passed); a non-money revert child unlocked by a card with no pause: answered
`deny` → `card_not_approved`, subject `revert <another id>` → `card_subject_mismatch`, an approved
`revert <child id>` card → executes with one connector call, and `execute(card_id=<another card>)`
→ `card_not_approved`; (3) an `identity` action with `hold_until` one hour after `GTM_FAKE_NOW` →
`hold_pending`, and one due but with a `S/cancels/<slug>/<action_id>` marker → `cancelled`; (4) a
hipaa fixture pack with `lead_sink.baa_ref` empty and a `crm.lead_append` → `baa_missing`; (5) a
hipaa fixture pack and a `hipaa_prohibited` row (e.g. `google_ads.customer_match_upload`) with an
authorized record → `hipaa_prohibited`.

**Where exceptions become results (DECIDED HERE; one mapping point per entry).** `CredentialUnavailable`,
`HostNotAllowed`, `TestModeNoLive`, `MutationOutsideApply` and `RedirectRefused` (all defined in the
`connectors` package root, §6.5b) are mapped **inside the connector**, because the connector imports
only `connectors`, never `gtmlib`: `read()`, `_apply_body` and `verify_read` each catch all five and
return the mapped result (table below); `dedupe_probe` returns `"unknown"` for any of them. Letting
one escape from `_apply_body` is a contract violation (it would be recorded as `unknown` with
`side_effects` possibly `"unknown"`); the L3 test below catches it. `plan()` may let them propagate:
`connector_dispatch.execute` wraps its `plan` call (and only that call) and maps them the same way.

| exception | WriteResult / VerifyResult `error` | `read()` |
|---|---|---|
| `CredentialUnavailable("test_mode_no_live")` | `validation`, `test_mode_no_live`, `retryable: false` (the same shape as `TestModeNoLive`: one shape for the condition, so act.py reaches exit 3 `test_mode_no_live` from `error.message` alone, never by parsing a prefix) | `ok: false`, `{"code": "validation", "message": "test_mode_no_live"}` |
| `CredentialUnavailable(r)`, any other `r` | `auth`, message `credential_unavailable:<r>`, `retryable: false` | `ok: false`, `{"code": "credential_unavailable", "message": "<r>"}` |
| `HostNotAllowed` | `validation`, `host_not_allowed`, `retryable: false` | `ok: false`, `{"code": "validation", "message": "host_not_allowed"}` |
| `RedirectRefused`, `sent=False` (no mutating request left the process) | `validation`, `redirect_refused`, `retryable: false` | `ok: false`, `{"code": "validation", "message": "redirect_refused"}` |
| `RedirectRefused`, `sent=True` (a 3xx reply to a sent mutating request) | `unknown`, `redirect_refused`, `retryable: false` (so the ledger records `side_effects: "unknown"` and the WriteResult `side_effect: "unknown"`, §6.2) | not reachable (`read()` sends no mutating request) |
| `MutationOutsideApply` | `validation`, `mutation_outside_apply`, `retryable: false` | `ok: false`, `{"code": "validation", "message": "mutation_outside_apply"}` |
| `TestModeNoLive` | `validation`, `test_mode_no_live`, `retryable: false` | `ok: false`, `{"code": "validation", "message": "test_mode_no_live"}` |

L3 test (per connector with a `write.py`): with `ctx.credential` raising `CredentialUnavailable("x")`,
`read()`, `apply()` and `verify_read()` each return the mapped result and no exception escapes; the
`apply` ledger line has `side_effects: false`; RED when `_apply_body`'s catch is removed. L3 test
(per connector with a `write.py`): a fixture answering the write POST with `302` → WriteResult
`error.code = "unknown"`, message `redirect_refused`, ledger `side_effects: "unknown"`,
`side_effect: "unknown"`, and a retry of the same action is refused `partial_prior_attempt` (for a
`none`-dedupe row); RED under a table that maps every `RedirectRefused` to `validation`. A
`CredentialUnavailable("test_mode_no_live")` from `ctx.credential` → `validation`
`test_mode_no_live` in all three; RED when it maps to `auth`.

**Account matching (DECIDED HERE).** Pack accounts carry a **bare** tier system plus a `brand`
field (the committed OtherCompanyB fixture, `tests/test_other-company_pack_fixture.py`: `system: "gbp"` /
`"facebook"` with `brand: "remodeling"`); suffixed names such as `gbp_remodeling`,
`facebook_remodeling` and `website_remodeling` appear in the pack's systems list and `host_systems`,
and are **also accepted** as an `accounts[].system` value. `match_account` normalizes every
`pack.accounts[].system` with `system_names.tier_system_and_brand(name, pack)` (03_schemas.md §3.22)
→ `(tier, suffix_brand)`. An account's effective brand is its `brand` field when present, else
`suffix_brand`; when both are present and differ, the account is **ambiguous by construction**:
`match_account` raises `account_ambiguous` for any lookup that reaches it (and `company.py validate`
refuses such a pack, R1 item 11). Candidates are accounts whose normalized tier system equals
`tier_system`, then those whose effective brand equals `brand` when `brand` is not None, then those
whose `normalize_account_id` equals the normalized `account_id` when it is given. Exactly one → it.
Zero → `account_missing`. More than one → `account_ambiguous`. `brand=None` therefore matches only
when the tier system has exactly one account, or when `account_id` picks one.
**Arguments from an action (DECIDED HERE; `execute`, `verify`, `api_executable_reason`,
`is_api_executable`, `read_committed_ceiling`):** `tier_system, sfx_brand = system_names.tier_system_and_brand(action.system,
pack)`; `brand = action.get("brand") or sfx_brand`; `match_account(pack, tier_system, brand,
action.account_id)` — the same `(system, brand)` pair 02_act.md's `ticket --setup` uses. That
`tier_system` is also the one `_build_ctx` receives, and the matched account's effective brand is
`ctx.brand` (§6.2 ConnectorCtx; `_build_ctx` computes it from the account, so a suffix-only account
such as `system: "website_remodeling"` with no `brand` key gets `ctx.brand == "remodeling"`).
**Tier system `crm` is the exception:** it never reads `accounts[]`; it returns the synthetic
lead-sink account (below "Lead sink"), whose `ctx.brand` is None.

**`build_read_ctx` (F-cli).** This is the one way a collector (07_notices_schedules.md §7.4) or
`read.py main` gets a read context. Collectors import it (the only gtmlib import allowed to them,
02_act.md §2.1), and nobody re-implements the GSM fetch. It raises `ReadCtxCompanyError("company_mismatch")`
unless `CLAUDE_GTM_COMPANY` is set **and** equals `slug`, and `ReadCtxCompanyError("not_gtm_session",
<reason>)` unless `gtmlib.session.prove_gtm_session(slug, os.environ)` returns ok (00_global_paths.md
"GTM-session proof"). It then calls `actx = make_ctx(slug)` **once**; an `ActError` whose `exit_code == EXIT_COMPANY`
becomes `ReadCtxCompanyError(e.code)`, and a `company.CompanyError` becomes
`ReadCtxCompanyError("company_unresolvable")`; any other exception propagates. Collectors pass the
proof because `read-run` starts them as subprocesses of the GTM session, which inherit its env and
lease ancestry. No exception exists for any other caller: in-process callers inside an admitted
act.py command (§6.2 step 6, `read_committed_ceiling`) use `_build_ctx` instead. It then calls
`match_account(pack, tier_system, brand, account_id)`; its `LookupError` becomes
`ReadCtxAccountError(<"account_missing"|"account_ambiguous">)` (never a bare `LookupError`, so it
cannot fall into exit 1). It then returns `_build_ctx(actx, tier_system, account)` with that same
`actx` (never a second `make_ctx`): the context carries that `account`, the same lazy
`credential_getter`, `dry_run=False`, `target_ids={}`, `approved=None` and `snapshots_dir =
actx.paths.snapshots_dir`.
**Account scope of every read (DECIDED HERE; plan §7.6/§20.9).** A `read()` op addresses platform
objects **only** through `ctx.account`'s `system_names.account_keys(ctx.tier_system, ctx.account)`
plus ids that enter through the **one params grammar** below. It is checked by the connector's
`read()` before any `http_request`:
- **`params["target_ids"]`** (a `dict[str, str]`, optional) is the **only** place an account-level or
  grammar-form object id enters a read. Each key must be a key the tier system's
  `system_names.target_ids` grammar can yield (03_schemas.md §3.22), else `validation`
  `bad_params`; each key in `system_names.ACCOUNT_LEVEL_KEYS` must equal
  `account_keys(ctx.tier_system, ctx.account)[key]` after `normalize_account_id` on both sides (the
  same test as target-resolution step 4b), else `target_account_mismatch`; an account-level key the
  account cannot supply → `account_key_missing`. Object-level keys are addressed only under
  `ctx.account` (the URL is built from `account_keys` plus the object id, never from a free
  parent). §6.2 step 6's `{"target_ids": {k_t: <normalized id>}}` is exactly this form.
- **Per-op object ids** — the fixed params each op declares in the connector's module docstring and
  nothing else: `lead_get` `{"lead_id"}`, `list_members` `{"list_id"}` (lead_sink), `committed_ceiling`
  and `ad_content` `{"target_ids"}`, `owns` `{"target_ids"}`, and any other op's named object keys.
  Each is an **object-level** id, used only in a URL built under `ctx.account` (e.g.
  `customers/<account_keys.customer_id>/…/<id>`, the pack's own sheet `ref` for a lead id); it is
  never parsed as an account id, and a value carrying `/`, `:`, a scheme or a host → `bad_params`.
- **Any other params key** → `validation` `bad_params` (never parsed as an id, never sent).
- **Global-id platforms (meta, and any platform whose object ids are unique across accounts).** An
  object-level id there does not name its account, so a per-op object id is admitted only through
  one of two rules, which the connector's module docstring names per op: (i) an **ownership read
  under `ctx.account`** before the content read (the §6.2 step-7 read: the object's `account_id` or
  owning page equals `ctx.account`'s key), `not_found` → `ok: false`, `{"code": "not_found",
  "message": "not_owned"}`; or (ii) **reliance on the per-company token scope** — the meta token
  passed the `debug_token` identity check (§6.3), whose `granular_scopes` bound every target to this
  pack, so a foreign object is unreachable with it and the platform answers `not_found`/`auth`.
  Rule (ii) is only as strong as that token check and is stated as the residual for ops that use it.
Any failure → `ok: false`, `errors[0] = {"code": "validation", "message": <the code>}` (or the
`not_found` form of rule (i)), zero `http_request` calls for the `validation` refusals. L tests (per
connector): a `read()` whose `params.target_ids` names another business's account-level id (e.g. a
OtherCompany `page_id` from a OtherCompanyB ctx) → `target_account_mismatch`, zero `FakeHTTP.calls`; a
bare `{"id": "<page id>"}` → `bad_params`; RED when either check is removed. L test (meta): a read
of a foreign ad id → `ok: false` with `target_account_mismatch` (when passed as an account-level
key) or `not_found` (object-level, by rule (i) or the platform under rule (ii)), never `ok: true`.

**`read.py main` CLI.** Invocation: `python3 <R>/tools/gtm/connectors/<c>/read.py --company <slug>
--system <tier system> [--brand <brand id>] [--account-id <id>] --op <read_op> [--params-json '<json>']
--out <abs path>`. Run that way, Python puts the connector directory, not `tools/gtm`, on `sys.path`,
so each `read.py`'s first statement (before any `connectors`/`gtmlib` import) is
`sys.path.insert(0, str(Path(__file__).resolve().parents[2]))` (= `tools/gtm`; the same pattern as
the hooks rule of 00_global_paths.md §1.1). `python3 -m connectors.<c>.read` with cwd `tools/gtm`
also works and needs no insert. Steps and exits, in order:
Every exit that writes nothing to `--out` prints exactly one line to stdout, `{"ok": false, "data":
null, "errors": [{"code": "<code>", "message": ""}]}`, with the code named below.
- 2 usage: bad arguments (code `usage`), or `--system` whose `system_names.connector_system` is
  not this connector (code `system_not_served`). Nothing is written to `--out`.
- 2 `gtm_env.BadFakeNow` raised anywhere below (code `bad_fake_now`, 00_global_paths.md's mapping
  for every tool): nothing is written to `--out`.
- 3 `gtm_env.RealStateRefused` raised anywhere below (code `test_mode_real_state`): nothing is
  written to `--out`.
- 13 `ReadCtxCompanyError` from `build_read_ctx` (code = its `.code`: `company_mismatch`,
  `not_gtm_session`, `company_unresolvable` or the `make_ctx` company code). Nothing is written to
  `--out`.
- 3 `ReadCtxAccountError` from `build_read_ctx` (`account_missing`/`account_ambiguous`): **nothing is
  written to `--out`** (it has not been validated yet), code = its `.code`.
- 3 `ManifestUnavailable` from `build_read_ctx` (raised by its `_build_ctx` after `match_account`,
  so an account failure is reported first): nothing is written to `--out`, code = its `.code`
  (`manifest_not_at_head`, `manifest_dirty`, `manifest_unreadable`).
- `--out` validation (next paragraph), which needs the built context (`ctx.snapshots_dir`). On `out_not_allowed`: exit 3, **nothing is written to
  `--out`** (the path was just judged not allowed), code `out_not_allowed` on stdout.
- 3 refused **after** `--out` was validated, with `{"ok": false, "data": null, "errors": [...]}`
  written to `--out`: an op not in the manifest's `read_ops` (code `op_not_listed`, message `""`),
  `credential_unavailable`, or `read()` returned `ok: false` (a
  platform error, `target_account_mismatch`, or any row of the exception table above).
- 0 ok (result written to `--out`). 1 an uncaught exception (nothing guaranteed at `--out`).
Exit 8 (02_act.md §2.3) is act.py's connector-failure code and is not used here (08_seats_wps.md
item 109). stdout/stderr never carry `data` (§6.2 "Log and error content").

**`--out` roots (DECIDED HERE).** `out = Path(--out).resolve()` (symlinks followed; a non-absolute
`--out` is `usage`), and a root `r` admits it iff `out.is_relative_to(r.resolve())`. The allowed
root set depends on the case, and exactly one case applies:
- **Non-hipaa pack, or a hipaa pack and an op that is not inbox-class:** {`ST/reads/`,
  `ctx.snapshots_dir`}.
- **Hipaa pack (`regulated ∋ "hipaa"`) and an inbox-class op:** {`ST/untrusted/`} **only** — this
  replaces the base set, it does not add to it (plan §20.4). An op is **inbox-class** when it is in
  the manifest's `inbox_class_ops` **or** the tier system is `crm` or `call_tracking` (the same rule
  as 02_act.md §2.4 `snapshot`; call records carry caller numbers and recordings).
Any other location is `out_not_allowed`. (`ST/reads/` is registered in 00_global_paths.md §1.3 by
R12.) A2 tests: on a hipaa fixture pack, an inbox-class `leads` read with `--out` under
`ST/untrusted/` → exit 0, and the same with `--out` under `ST/reads/` → exit 3 `out_not_allowed`
(RED when the base set is added to the hipaa case); on a non-hipaa pack, `--out` under
`ST/untrusted/` → `out_not_allowed` and under `ST/reads/` → exit 0; a `--out` symlink under
`ST/reads/` pointing outside → `out_not_allowed` (RED when `resolve` is dropped).

**Evidence directories.** Execute/verify: `ctx.snapshots_dir/act/<action_id>/` (= `actx.paths.snapshots_dir`,
copied by `_build_ctx`). Read: `ctx.snapshots_dir/read/<tier_system>/<UTC ts, §0.3 compact form>/`. **hipaa packs:**
`ST/untrusted/act_<action_id>/` and `ST/untrusted/read_<tier_system>_<UTC ts>/` respectively. These
are purged by `purge-untrusted` and excluded from backups (02_act.md §2.4; R4 asks 02 to state that
the purge is recursive). Result paths are home-relative. What a connector writes there, and
with which modes: §6.2 "Evidence files".

**Credentials (DECIDED HERE).** `credential_getter` returns a lazy callable. On first call it:
0. **Test mode (00_global_paths.md §1.1 (2)).** `gtm_env.test_mode(os.environ)[0]` true →
   `CredentialUnavailable("test_mode_no_live")`, before any file, git or gcloud call (mapped to
   `validation` `test_mode_no_live`, the same shape as `TestModeNoLive`, by the exception table
   above). Tests of the
   steps below call `credential_getter` directly (never through `execute`/`verify`/`build_read_ctx`/
   step 6's `ctx_t`), monkeypatch `gtm_env.test_mode` to return `(False, [])` **and** install
   `testkit.FakeProc` (§6.5b) so no real gcloud or openssl runs; the fixture transport
   (§6.5b) is unaffected because it never calls `credential_getter` (tests inject `ctx.credential`).
   **A2 test seam (DECIDED HERE).** A2 tests that reach a ctx built inside `connector_dispatch`
   (`execute`, `verify`, `build_read_ctx`, `read_committed_ceiling`, step 6's `ctx_t`) keep test mode
   ON (so `refuse_real_state` and the `GTM_FAKE_NOW` clock stay live) and use two seams instead:
   (a) every builder calls `credential_getter` through the module global at call time (never an
   alias bound at import or a default argument), so a test does
   `monkeypatch.setattr(connector_dispatch, "credential_getter", lambda ctx, acct: (lambda: <dummy
   payload with the manifest's credential.fields>))`; (b) the module attribute
   `connector_dispatch._TEST_TOKEN_CACHE: dict | None = None` — when it is not None **and**
   `gtm_env.test_mode(os.environ)[0]` is true, `_build_ctx` sets `ctx._token_cache =
   dict(_TEST_TOKEN_CACHE)` (tests set `{"token": "fake-token", "expires_at": <far future>}`);
   outside test mode it is ignored, so production can never be pre-filled. Monkeypatching
   `gtm_env.test_mode` (or `gtm_env.refuse_real_state`) in any test that reaches `idempotent_apply`
   is forbidden; a static A2 test scans the A2 test files and fails on a `test_mode` monkeypatch in a
   file that calls `execute`/`verify`. A2 tests: with test mode on and seam (b) unset, a `ga4`
   `execute` through `_build_ctx` gets an empty `_token_cache`; with test mode off and seam (b) set,
   `_token_cache` is still `{}` (RED when the test-mode condition is dropped).
1. Reads `H/.claude/gtm/connectors.json` **from HEAD** (`git -C <H> show HEAD:./.claude/gtm/connectors.json`
   — the `HEAD:./` form 02_act.md §2.2 requires for every home-relative HEAD read, because a home
   nested below its repo toplevel resolves a bare `HEAD:.claude/…` from the toplevel and would fail
   closed; requests/02_act.md item 96). A2 test: a home nested one directory below its repo toplevel
   with a committed `connectors.json` → steps 1–3 pass; RED under the bare `HEAD:.claude/…` form. Shape: `{"schema": 1, "gsm_project": "<project id>", "gcloud_account": "<account email>"}`
   (tracked and secret-free). Absent, malformed, or a missing key → `CredentialUnavailable("connectors_json_unavailable")`.
   **Steps 1 and 3, and step 2's per-company name check, are `check_secret_target(ctx.R, ctx.home,
   ctx.company, <name>)` (API block above); `credential_getter` calls it after step 2's `gsm:`
   prefix check, and `secret_sink` calls the same function before any gcloud call (§6.6), so the
   refusals exist once.**
2. Requires `account.credential_ref` to match `gsm:<name>`. `none`, a `browser:` ref, or anything
   else on an account used for API access → `CredentialUnavailable("not_gsm_ref")`. **Secret name
   form (DECIDED HERE).** `<name>` is the BARE name: `credential_ref` with its `gsm:` prefix removed.
   The bare form, never the prefixed one, is what every consumer carries: the setup ticket's
   `secret_name` (02_act.md §2.4 `ticket --setup`, 03_schemas.md §3.6), `secret_sink.py
   --secret-name`, the capture POST's `secret_name` (§6.6), the `name` argument of
   `check_secret_target`, and every gcloud `secrets …` `<name>`; only a pack account's
   `credential_ref` carries `gsm:`. **Per-company
   name (plan §17 d "a new per-company secret prefix"):** `<name>` must fullmatch
   `gtm-<ctx.company>-[a-z0-9-]+` (the slug inserted literally, `re.escape`d), else
   `CredentialUnavailable("secret_not_per_company")`. So a OtherCompanyB pack can never name a
   `gtm-othercompany-…` secret, even while no other pack lists it and even when several non-CSA
   companies share one GSM project (FID-23). CSA's own secrets follow the same rule with CSA's slug.
   **Slug prefix collisions (DECIDED HERE).** The pattern (and the SA pattern of step 6) would let
   slug `acme` match `gtm-acme-west-google`, a secret of a company `acme-west`. So `company.py
   validate` refuses a slug that equals another registered slug followed by `-` and more
   characters, in either direction (pending, requests/06_connectors.md R31); with that rule no two
   companies' `gtm-<slug>-` prefixes can overlap. A1 validate test: registering `acme-west` while
   `acme` exists, and `acme` while `acme-west` exists → refused; RED when the check is removed.
3. **Refuses** (plan §20.9/§20.9a):
   - a `<name>` matching `oauth-google-*` → `CredentialUnavailable("agency_secret_name")`.
   - a `gsm_project` listed in `phi_denylist.json` `agency_gsm_projects` (03_schemas.md §3.20, R5)
     → `CredentialUnavailable("agency_gsm_project")`. An unreadable **or absent** denylist →
     `CredentialUnavailable("phi_denylist_unreadable")`.
   - `gsm_project == system_names.CSA_GSM_PROJECT` (the pinned literal `"example-org"`, plan
     §17 d; R1 item 9) while `ctx.company != system_names.CSA_SLUG` →
     `CredentialUnavailable("gsm_project_cross_company")`. No file of CSA's is read, so there is no
     "CSA file unreadable" case; while `CSA_SLUG` is unset (empty), every company naming that
     project is refused.
4. Runs `[connectors.gcloud_path(), "secrets", "versions", "access", "latest", "--secret=<name>",
   "--project=<gsm_project>", "--account=<gcloud_account>"]` **in-process** through the one
   subprocess seam `connectors._run` (§6.5b "Subprocess seam"; never through the Bash tool). stdout
   is captured and never logged. gcloud missing, a non-zero exit, or empty output →
   `CredentialUnavailable("gsm_access_failed")`.
5. Parses stdout as a JSON object. Every `manifest.credential.fields` key must be present with a
   non-empty string value, and for `google_sa` `auth_route` must be exactly `impersonate` or `key`;
   the `google_sa` route keys `private_key_id` and `private_key` are required **iff `auth_route ==
   "key"`** (the `impersonate` route has no route keys, and carries none). Any failure →
   `CredentialUnavailable("payload_invalid")`. On success it adds every non-empty string value of the
   payload's `fields` and `scan_fields` keys to `ctx._secrets` (so `ctx.log` redacts them without ever
   calling `ctx.credential()`, §6.2). The keyed
   forms of `credential.fields` (and `scopes`, `scan_fields`) are selected by `pack.lead_sink.kind`
   (§6.1). The payload (one JSON object per secret) is written by
   `secret_sink` (§6.6) or the operator's `secret_sink.py prompt` (§6.6). It is the only format.
6. `google_sa` only: the service-account identity check below; failure →
   `CredentialUnavailable("sa_not_per_company")`. It also sets `ctx.gsm_project` and
   `ctx.gcloud_account` from step 1 (non-secret) for `connectors.mint_google_token`.
7. `meta_bearer` only: the token identity check (below "`meta_bearer` identity check"); failure →
   `CredentialUnavailable("token_not_per_company")`.

`CredentialUnavailable` maps as the exception table above states (WriteResult `auth`,
`credential_unavailable:<reason>`; `read()` `credential_unavailable`; `test_mode_no_live` alone maps
to `validation` `test_mode_no_live`), to `read.py main` exit 3, and (for `test_mode_no_live`) to
act.py exit 3 `test_mode_no_live` (00_global_paths.md §1.1 (2)).
L tests (A2): a `gsm:gtm-othercompany-meta` ref on a OtherCompanyB account → `secret_not_per_company`,
zero gcloud calls; RED when step 2's name check is removed.

**Auth scheme per connector (DECIDED HERE; plan §17 j, §20.9).** `connectors.auth_headers(ctx) ->
dict[str, str]` (L3, package root) builds the request headers from `ctx.credential()` by the
manifest's `credential.auth`; connectors never build auth headers themselves. For `google_sa` it
obtains the bearer from **`connectors.mint_google_token(ctx, payload, scopes) -> str`** (L3, package
root; the one owner of minting, both routes below), which reads `ctx.gcloud_account` (set by
credential step 6) and caches in `ctx._token_cache`. The L3 manifest test asserts each manifest's
value against this table.

| connector | `credential.auth` | payload keys (`credential.fields` + route keys) | header |
|---|---|---|---|
| `google_ads`, `ga4`, `search_console`, `gtm_api` | `google_sa` | `auth_route`, `service_account_email` (+ google_ads: `developer_token`, `login_customer_id`; + `key` route: `private_key_id`, `private_key`) | `Authorization: Bearer <minted SA token>` (+ google_ads `developer-token`, `login-customer-id`) |
| `gbp` | `google_sa` | as above | as above — **but** a service-account route for the Business Profile APIs is UNVERIFIED (plan §17 j names only Ads/GA4/GTM). Until a probe recorded in plan §17 shows an SA can manage a location, the `gbp` manifest `access` is `["browser"]` and it has no `write.py` rows served by API |
| `lead_sink` | `{"google_sheet": "google_sa", "app_crm": "bearer"}` (by the pack's `lead_sink.kind`) | google_sheet: as `google_sa`; app_crm: `token` | google_sheet: Bearer SA token (the sheet is shared with the SA email); app_crm: `Authorization: Bearer <token>` |
| `meta` | `meta_bearer` | `access_token` (a long-lived Page or system-user token; there is no refresh grant; never a user token — identity check below) | `Authorization: Bearer <access_token>`. An expired or revoked token is `auth` → `credential_unavailable` handling via a re-capture (§6.6), never a refresh |
| `wordpress` | `wp_app_password` | `username`, `application_password` | `Authorization: Basic base64(username:application_password)` |
| `listings`, `call_tracking` | `bearer` | `token` | `Authorization: Bearer <token>` (a vendor whose API wants another header name records it in its manifest `credential.header`, optional) |

No connector uses a user OAuth refresh token. A user refresh token belongs to a Google login, and the
obvious login for these systems is the operator's personal identity, which administers every
business (plan §3.4 cross-connection hazard); plan §17 j chose per-company service accounts to remove
exactly that. Adding a user-OAuth route to any connector is a plan deviation that needs an Appendix B
entry and a trust-architect ruling first, and that ruling must require a dedicated per-company
Google user that is never the operator's personal login, enforced by a check in this section.

**`meta_bearer` identity check (DECIDED HERE; plan §3.4, §7.6, §17 d, §20.6).** A user token from
the operator's personal Facebook login administers every business he runs — the same §3.4
cross-connection hazard that rules out Google user OAuth above. So on the credential's first use
(credential step 7), before any other Meta call, the connector-independent helper
**`connector_dispatch._check_meta_token(ctx, payload: dict) -> None`** (raises
`CredentialUnavailable("token_not_per_company")`; the payload is the one just parsed in step 5) calls `connectors.http_request(ctx, "GET", "https://graph.facebook.com/<v>/debug_token",
mutating=False, params={"input_token": <access_token>}, headers={"Authorization": "Bearer " +
<access_token>})` authenticated with the same token (`<v>` = the pinned Graph API version,
`ctx.manifest["api_version"]`). The `Authorization` header is built **directly from the payload
just parsed in credential step 5**, never through `auth_headers(ctx)`: `auth_headers` calls
`ctx.credential()`, which is still inside its own first call here, so going through it would
recurse. It refuses
`CredentialUnavailable("token_not_per_company")` unless **all** hold: `data.is_valid` is true;
`data.type` is `PAGE` or `SYSTEM_USER` (never `USER`); and every `granular_scopes[].target_ids` value
is within this pack's `identity_allowlist.facebook_page_ids ∪ instagram_ids ∪ meta_ad_account_ids ∪
meta_business_ids` (after `normalize_account_id`), with a scope that has no `target_ids` (an
all-assets grant) counting as outside. **Business ids (DECIDED HERE):** a system-user token's
`business_management` scope (and possibly others) targets the owning **business** id, which is no
page, IG user or ad account. Such a target is admitted only through the pack bucket
`identity_allowlist.meta_business_ids` (pending, R23: added to 03_schemas.md §3.3, and `company.py
validate` refuses a value that appears in another pack's bucket, the same rule as the other
identity buckets, so the bucket can only name the pack's own business). No scope is excluded from
the target check. Until R23 lands, a token with any business-id target is refused
`token_not_per_company` (fail closed). A reply that lacks any of these fields also refuses (fail
closed). **`SYSTEM_USER` is a recorded plan deviation (DECIDED HERE; plan §17 j).** Plan §17 j
records that system users need a Business Portfolio and are "not available to us". Admitting a
`SYSTEM_USER` token therefore needs an Appendix B entry and a trust-architect ruling recorded in plan
§17 (pending, requests/06_connectors.md R32). Code reads the ruling only through the module
constant `connector_dispatch.META_SYSTEM_USER_RULING: str | None = None`, set to the ruling's plan
§17 reference in the same change that records it (under TRUST_PATHS, so it is signed like any other
trust edit); while it is None, `data.type == "SYSTEM_USER"` is refused `token_not_per_company`
(fail closed), and only `PAGE` tokens pass. Once admitted, the
**portfolio contents check** runs too, because a portfolio that also holds another business's
assets is exactly the forbidden cross-connection (CSA CLAUDE.md "NEVER CROSS-CONNECT"; plan §3.4),
and `granular_scopes` bounds only what the token targets, not what the portfolio contains: for the
business id `b` the token targets, `_check_meta_token` reads, with the same token and through
`connectors.http_request(..., mutating=False)`, `/<v>/<b>/owned_pages`, `/<v>/<b>/client_pages`,
`/<v>/<b>/owned_ad_accounts`, `/<v>/<b>/client_ad_accounts` and `/<v>/<b>/owned_instagram_accounts`
(edge names UNVERIFIED; the L1 meta connector's first recorded fixture pins them), following each
`paging.next` URL through `http_request` (so the host guard judges it) to the end. Every returned id,
after `normalize_account_id`, must be in the pack's matching bucket (`facebook_page_ids`,
`meta_ad_account_ids`, `instagram_ids`); any id outside it, any read that is not `ok`, or a missing
edge → `CredentialUnavailable("token_not_per_company")` **and** an isolation hit
(`breakers.append_isolation_hit({"source": "connector_dispatch", "kind": "meta_portfolio_foreign_asset",
"company": ctx.company, …})`, 02_act.md §2.2b; ids are recorded, never the token). The token value is
never logged (the `params` value and the header are redacted by `ctx.log` and by `FakeHTTP.calls`,
whose redaction also covers a `params` key named `input_token`). **UNVERIFIED, pinned by the L1
meta connector's first recorded fixture before any meta row is served:** (a) the field names
`type`, `granular_scopes`, `target_ids`; (b) whether `debug_token` accepts the inspected token
itself as its access token, or requires an app token (`<app_id>|<app_secret>`) or an admin's
token — this contract fetches no app secret, so if an app token is required, no meta account is
API-served; (c) which scopes of a system-user token carry the business id as a target. **Fallback
(named):** if (b) requires an app token, or a CSA system-user token cannot pass the check once R23
lands, every meta account of that pack stays `access: browser` — the same browser path as
OtherCompanyB's — until a contract change defines the app-token route with its own trust-architect
ruling (plan §8's CSA Graph API path is then not served in Wave 2). **Ad-account rows** (`meta.campaign_enable`,
`meta.adset_budget_edit`, `meta.campaign_remove`, …) cannot be served by a Page token; they need a
system-user (or app) token scoped to the pack's ad account, and **creating** that token is an
identity-class setup action. If Meta requires a Business Portfolio to issue it, it becomes the plan
§20.6 portfolio card (NEVER create or join a portfolio autonomously; operator directive in CSA
CLAUDE.md "NEVER CROSS-CONNECT"), and until the operator decides, the meta ad-account rows stay not
API-executable (the account's `access` stays `browser`). L tests (meta): a `debug_token` fixture
with `type: USER` → `token_not_per_company`, zero further calls; one whose `granular_scopes` include
a page id outside the pack → refused; with `META_SYSTEM_USER_RULING` monkeypatched to a reference, a `SYSTEM_USER`
token whose `business_management` scope targets a business id listed in the fixture pack's
`meta_business_ids`, and whose portfolio edges list only the pack's own page, ad account and IG
account → accepted, one naming an unlisted business id → refused, and one whose `owned_pages` (or
`client_pages`) also lists another business's page → `token_not_per_company` plus one isolation-hit
line (RED when the portfolio contents check is removed); with it None, any `SYSTEM_USER`
token → refused; the `debug_token` request carries an `Authorization` header while
`ctx.credential` is a counting stub called exactly once (RED when the header comes from
`auth_headers`, which re-enters it); each RED when its clause is removed.

**`google_sa` token minting (DECIDED HERE; plan §17 j, §20.9 `gtm-<slug>-google` service accounts).**
- **Identity check (step 6 above).** `service_account_email` must fullmatch
  `gtm-<slug>-[a-z0-9-]+@<gsm_project>.iam.gserviceaccount.com`, where `<slug>` is `ctx.company`
  and `<gsm_project>` is that company's `connectors.json` value (the per-company SA lives in the
  per-company project, so step 3's project refusals cover it too). Any other SA — another
  company's, a default compute SA, an Agency one — is refused before a token is minted.
  **Slug bound (UNVERIFIED against current GCP docs: service-account ids are 6–30 characters of
  `[a-z0-9-]`, starting with a letter):** `company.SLUG_RE` (`^[a-z][a-z0-9-]{1,31}$`, committed)
  already forbids `_`, so the live constraint is length: a company served by a `google_sa` account
  must have `len("gtm-" + slug + "-x") <= 30` (slug ≤ 24 characters; `SLUG_RE` admits up to 32), or
  no valid SA id can match the pattern. `company.py validate` refuses a pack that has a `google_sa` account
  (tier systems `google_ads`, `ga4`, `search_console`, `gtm`, `gbp`, or `lead_sink.kind:
  google_sheet`) and a slug outside that bound (pending, R27).
- **Test mode first.** `mint_google_token` first returns a cached token when `ctx._token_cache`
  holds one more than 60 s from `expires_at` (no process, nothing live — `make_ctx`'s L3
  `auth_headers` test and the §6.3 A2 test seam depend on this); its next statement is
  `gtm_env.test_mode(os.environ)[0]`
  true → `CredentialUnavailable("test_mode_no_live")`, before `connectors.gcloud_path()` or any other
  call (so the L3 mint test's result never depends on whether gcloud is installed on the machine;
  `gcloud_path()` would otherwise raise `gcloud_missing` first). `secret_sink` does the same before
  its first `gcloud_path()` call (§6.6).
- **Route `impersonate` (preferred; no key material exists anywhere).** `ctx.gcloud_account is
  None` (credential step 6 has not run — e.g. a test that injected `ctx.credential`) →
  `CredentialUnavailable("token_mint_failed")` before any subprocess. Otherwise, through the seam
  `connectors._run` (§6.5b "Subprocess seam"):
  `[gcloud_path(), "auth", "print-access-token", "--impersonate-service-account=<service_account_email>",
  "--account=<ctx.gcloud_account>", "--scopes=<comma-joined credential.scopes>"]` (exact flag set UNVERIFIED —
  probe `j2`, recorded in plan §17 by the coordinator, confirms it before L1 relies on it). The
  `gcloud_account` needs `roles/iam.serviceAccountTokenCreator` on that one SA only (a grant made
  on the sign-in card). stdout (the token) is captured, never logged; a non-zero exit or empty
  output → `CredentialUnavailable("token_mint_failed")`.
- **Route `key` (fallback).** The payload carries `private_key_id` and `private_key` (PEM, PKCS#8
  RSA). The JWT is `base64url(header).base64url(claims)` with header
  `{"alg": "RS256", "typ": "JWT", "kid": <private_key_id>}` and claims `{"iss": <sa>, "scope":
  <space-joined credential.scopes>, "aud": "https://oauth2.googleapis.com/token", "iat": <now>,
  "exp": <now + 3600>}` (real clock). It is signed through the seam,
  `connectors._run([connectors.OPENSSL, "dgst", "-sha256", "-sign", f"/dev/fd/{r}"], input=<signing
  input>, pass_fds=(r,))`, by the SIP-protected system binary
  **`/usr/bin/openssl dgst -sha256 -sign /dev/fd/<r>`** (`OPENSSL = "/usr/bin/openssl"`, a literal; the same system-binary precedent as
  05_approver.md), where `r` is the read end of an `os.pipe()` passed with `pass_fds=(r,)` — the
  child sees it under the same number `r`, so argv names that number; never a `dup2` onto a fixed
  fd — the key written to the write end and closed, the signing input on stdin and
  the signature on stdout — never a temporary file, never on argv. The assertion is exchanged by
  `connectors.http_request(ctx, "POST", "https://oauth2.googleapis.com/token", mutating=False,
  data=urllib.parse.urlencode([("grant_type", "urn:ietf:params:oauth:grant-type:jwt-bearer"),
  ("assertion", <jwt>)]).encode("ascii"), headers={"Content-Type":
  "application/x-www-form-urlencoded"})` (every form body in this contract is built this way).
  openssl failure or a non-200 reply → `CredentialUnavailable("token_mint_failed")`.
- `credential.scopes` (manifest, `google_sa` connectors only; required there): the OAuth scopes the
  connector needs (e.g. google_ads `https://www.googleapis.com/auth/adwords`). The minted token is
  cached in `ctx._token_cache` (`{"token", "expires_at"}`; in memory only, never written; the token
  is also added to `ctx._secrets`) and re-minted by `mint_google_token` once `ctx.now()` is within
  60 s of `expires_at`. **One clock (DECIDED HERE):** the cache deliberately follows `ctx.now()`
  (fake under `GTM_TEST`) for both the mint time and the comparison, so cache tests are
  deterministic; only the JWT's `iat`/`exp` claims use the real clock (the platform validates them).
  Expiry: `impersonate` route = `ctx.now()` at mint + 3600 s (gcloud prints only the token); `key`
  route = `ctx.now()` at mint + the reply's `expires_in` seconds.
- **Tests and the token cache.** Every FakeHTTP-driven test of a `google_sa` connector that is not
  about minting pre-fills `ctx._token_cache = {"token": "fake-token", "expires_at": <a far-future
  tz-aware datetime>}`, so `auth_headers` never reaches `mint_google_token`'s subprocess path; a test
  about minting installs `testkit.FakeProc` (§6.5b) instead.
- L tests (google connectors): an SA email `gtm-otherco-google@…` or one in a different project →
  `credential_unavailable:sa_not_per_company` with zero `FakeHTTP.calls` and zero `FakeProc.calls`; the
  `impersonate` route calls the fake gcloud (`FakeProc`, argv[0] == `gcloud_path()`) with exactly
  `--impersonate-service-account` and `--account`; with `ctx.gcloud_account is None` it raises
  `token_mint_failed` with zero `FakeProc.calls`; the `key` route calls a fake openssl whose argv
  names `/dev/fd/<n>`, and the fake reads the key from exactly that fd `n` (also in `pass_fds`), and
  it never writes a file under the tmp home. Each goes RED when its check is reverted. L3 test:
  with `GTM_TEST=1`, no `FakeProc` installed and `subprocess.run`/`subprocess.Popen` monkeypatched
  to record calls, `mint_google_token` on the `impersonate` route (with `ctx.gcloud_account` set and
  an empty `ctx._token_cache`) raises
  `CredentialUnavailable("test_mode_no_live")` and zero subprocess calls are recorded, with
  `shutil.which` monkeypatched to return None (no gcloud on the machine) so the result cannot be
  `gcloud_missing`; RED when mint's first statement is removed. A second L3 test calls
  `connectors._run([connectors.OPENSSL, "version"])` directly under `GTM_TEST=1` → `test_mode_no_live`,
  zero subprocess calls; RED when `_run`'s first statement is removed or a mint route calls
  `subprocess` directly.

**GSM project value (FID-23).** The file and its shape are DECIDED HERE, but the **project value** is
not. CSA's is `example-org` (plan §17 d). For OtherCompanyB, OtherApp and OtherCompany, plan §17 d
leaves it to **trust-architect** (an operator-controlled project not tied to the main product). The same
goes for `gcloud_account`, the identity that performs non-CSA GSM access. The coordinator obtains
both decisions and records them in plan §17 d before WP-M writes those three `connectors.json` files
(08_seats_wps.md Appendix C item 30; R8). Until then those files stay absent, and
every GSM credential for those companies fails closed. Agency's `otherapp` project is never
eligible (plan §20.9/§20.9a, which supersede the earlier §17 d text: the GTM department reuses
nothing of Agency's, and the only shared surface is `~/.claude`); it stays in
`agency_gsm_projects` (R5). R7 and R8 carry the same line.

**MCP read servers — none in Wave 2 (DECIDED HERE; a deviation from plan §8, recorded as
requests/06_connectors.md R22 → 08_seats_wps.md Appendix B).** Plan §8 names the official
`googleads/google-ads-mcp` and `googleanalytics/google-analytics-mcp` servers as a read path. Those
servers take their credentials from Application Default Credentials or from environment-configured
values (e.g. a developer token in an env var); UNVERIFIED for these two packages, and not verified
by this contract. **Wave 2 ships no MCP read server, no `tools/gtm/mcp_launch/` launcher and no
`launch.py`.** Every platform read goes through the connector's own `read.py` (§6.3 "`read.py main`
CLI"), started by `act.py read-run` or a collector (07_notices_schedules.md §7.4), which already
carries the credential refusals, the test-mode check, the account-scope rule and the hipaa
routing. The WP rows' `tools/gtm/mcp_launch/<connector>.sh` entries are conditional ("only if that
connector has an MCP read server", 08_seats_wps.md §9) and are therefore empty in Wave 2.

**Credential channel rule (binding on any later MCP server; DECIDED HERE).** The rule is about the
secret **value**: it must never be in any process environment, on argv, or on disk. So:
- **Permitted:** the value on the child's stdin, or on an inherited pipe fd `r` (`pass_fds`), and an
  environment variable whose value is only the **path of that inherited fd**, `/dev/fd/<r>` (e.g.
  `GOOGLE_APPLICATION_CREDENTIALS=/dev/fd/<r>`): the environment then holds a path, not a secret,
  and another process of the same user cannot open another process's `/dev/fd/<r>`.
- **Refused:** any environment variable whose value is, contains or encodes the secret (a token, a
  key, a password, a key file's content), and any path to a file on disk that holds it.
Adding an MCP read server is a contract change, not a WP task: it must add
`tools/gtm/mcp_launch/servers.json` (read from HEAD like a runbook, under TRUST_PATHS) with, per
server, `{"argv": [...], "credential_channel": "stdin" | "fd" | "fd_path_env", "env_name":
<name, fd_path_env only>, "connector": <§6.1 connector name>, "tier_system": <canonical tier
system>}`; a `launch.py` CLI with its exits (0 started via `execv`, 2 usage, 3 refused with the
reason code on stdout, 13 company) that obtains the secret only through
`connector_dispatch.credential_getter` from a `build_read_ctx` context and refuses any server
declaring another channel (`env_credential_unsanctioned`); and an L3 test per channel. A server
that can take its secret only as an environment value additionally needs an Appendix B entry plus a
trust-architect ruling recorded in plan §17 (the same route as fallback B, R7) **and** the G-B rule
of R18 (deny `ps` with `e`/`-E`/`eww`-style flags and `launchctl procinfo` in GTM scope). (Whether
macOS `ps` shows another process's environment to the same non-root user is UNVERIFIED; the
coordinator probes it before any such ruling, R8.)
`browser:playwright-gtm` accounts are never
API-executable. Every browser account in every pack uses the same ref `browser:playwright-gtm` (one
server name, a per-home `mcp.json`). 08_seats_wps.md Appendix C item 16 (exempt `browser:` refs from
the cross-pack reuse check) has **landed**: the committed `company.py` `_credential_refs` collects
only `gsm:` refs (its "Blocker fix" docstring), so a shared `browser:` ref is not a reuse error.

**Lead sink (plan §5, §20.9; DECIDED HERE).** The pack's sink is `pack.lead_sink {kind:
google_sheet|app_crm|none, ref, credential_ref, baa_ref?}`, not an `accounts[]` entry. The committed
`company_schema.json` has only `kind` and `ref`: `credential_ref` is **pending** (R1 item 10) and
`baa_ref` is **pending** (its source is 03_schemas.md §3.14, FID-19; R1 item 10 asks for it in the
schema too).
- **Account.** For tier system `crm`, `match_account` returns the synthetic account
  `{"system": "crm", "brand": null, "account_id": pack.lead_sink.ref, "access": "api" if kind !=
  "none" and not (kind == "app_crm" and company == system_names.CSA_SLUG) else "browser",
  "credential_ref": pack.lead_sink.credential_ref}` (the CSA branch: "CSA's own `app_crm` sink"
  below). `kind: none` → no
  connector call (`is_api_executable` is false); R13 asks 02_act.md §2.4 to route such a lead to the
  fallback below.
- **Hosts.** google_sheet: manifest `api_hosts` contains `sheets.googleapis.com` (+ the implicit
  token host, §6.1); the sheet id is `ref`. app_crm: the manifest `api_hosts` contains the token
  `{lead_sink_host}`, which `connector_dispatch` expands to **exactly the host of that pack's own
  `lead_sink.ref`**, for that pack's ctx only; no app host is ever listed statically, so no
  company's lead_sink can reach another company's (or CSA's) app.
- **CSA's own `app_crm` sink — not served in Wave 2 (DECIDED HERE; plan §3.3, §20.2).** Plan §8
  names the CSA app API as CSA's lead sink, but plan §3.3 makes anything against CSA production obey
  CSA's WHERE TO TEST rule and `allowlist.json` `read_only_hosts`, and plan §20.2 touches CSA
  production only on explicit operator instruction; CSA's live beta testers make "never break
  production" CSA's top constraint. An autonomous T1 `lead-append` into CSA production is therefore
  **not** sanctioned by this contract. While `ctx.company == system_names.CSA_SLUG` and
  `pack.lead_sink.kind == "app_crm"`: the synthetic `crm` account (above) has `access: "browser"`
  (so `is_api_executable` is false and no connector call is made, exactly as for `kind: none`), and
  `{lead_sink_host}` expands to **nothing** (§6.1), so even a direct `connectors.http_request` to
  the CSA app host is `host_not_allowed`. The lead goes to `ST/lead_fallback.jsonl` by the same
  routing as `kind: none` (R13; R22 item 5), and WP-M writes CSA's pack with `lead_sink.kind: google_sheet` or
  `none` until the ruling below lands (R22). Serving it needs a contract change carrying an
  Appendix B entry, a trust-architect ruling on the production blast radius (the exact endpoint, a
  scoped non-interactive credential that can append a lead row and nothing else, a server-side rate
  limit, an idempotency key, and a statement that it touches no tenant data beyond the lead row),
  and the operator's answer relaxing plan §20.2's "explicit operator instruction" for this one
  write (R22). Tests of any `crm` connector code run only against FakeHTTP (§6.5b), never against
  CSA staging or production. A2 tests: a CSA fixture pack with `lead_sink.kind: app_crm` → the
  synthetic account has `access: "browser"`, `is_api_executable` is false for a `crm` action, and
  `allowed_hosts` holds no app host; a non-CSA fixture pack with `app_crm` → `access: "api"` and
  exactly its own sink host; each RED when the CSA branch is removed.
- **Read ops (manifest `read_ops`, all inbox-class, §6.1).** `lead_get` (`params` = `{"lead_id"}`;
  `data` = that lead row, 03_schemas.md §3.14; used by the 03_schemas.md §3.11 hold-release
  auto-cancel) and `list_members` (`params` = `{"list_id"}`; `data` = `{"members": [<lead row>]}`;
  `ok: false` with `errors[0].code = "not_found"` when the list does not resolve to lead-sink rows;
  used by `sms.list_send`/`email.list_send` execution, 03_schemas.md §3.11 FID-13, which maps
  `not_found` to `list_unresolvable`). A2 calls both in-process: `_build_ctx(actx, "crm",
  match_account(pack, "crm", None))`, then `connectors.lead_sink.read.read(ctx, op, params)` (module
  imported as `connectors.lead_sink.read`); the
  rows stay in memory and are never logged (§6.2 "Log and error content").
- **Config-time refusal.** `company.py validate` refuses (R1 item 10) a pack whose `app_crm`
  `lead_sink.ref` host is a `phi_denylist.json` `agency_app` host or a host whose `applies_to`
  includes this pack, a host in another pack's `brands[].domains` or `lead_sink.ref`, or a
  `shared_identifiers` system host — **including a host that this same pack declares in its own
  `shared_identifiers`** (a system the pack shares with another business is by definition not the
  pack's own sink; this is what refuses a OtherCompanyB or CSA pack naming the CSA–OtherCompanyB Scout
  host, plan §3.3). The rule has no CSA exception: whether CSA's app host is itself a
  `shared_identifiers` host of CSA's pack is UNVERIFIED (it depends on how the CSA pack declares
  `csa_scout`), and the ruling that serves CSA's `app_crm` sink (above) must amend this rule if it
  is. The request-time host guard (§6.5b) refuses the `phi_denylist` hosts again as a backstop; the
  other cases need no request-time rule because `{lead_sink_host}` only ever expands to the pack's
  own validated `lead_sink.ref` host. A2 validate tests: a CSA fixture pack whose `app_crm`
  `lead_sink.ref` host equals a host it declares in its own `shared_identifiers` → refused; the same
  pack with `lead_sink.kind: google_sheet` → valid; a OtherCompanyB fixture pack whose `lead_sink.ref`
  host is another pack's `lead_sink.ref` host → refused; each RED when its clause is removed.
- **Request-time failure.** A lead-sink `validation` (incl. `host_not_allowed`, `redirect_refused`)
  or `auth` failure never loses the lead: act.py writes the row to `ST/lead_fallback.jsonl` with
  `fallback_reason: "sink"` and exits 0 with `result.fallback: "sink"` (plan §5 "never lets a lead
  sit unlogged"). This routing is **pending** (R13 asks 02_act.md §2.4 `lead-append` and 03_schemas.md
  §3.14 for it); until it lands the lead-append fails and the lead is not in the fallback.
- A1 test (after R13): an app_crm sink on a fixture pack whose sink host answers `host_not_allowed`
  → a `lead_fallback.jsonl` row with `fallback_reason: "sink"`, exit 0. A2 test: a pack whose
  `lead_sink.ref` host is an `agency_app` host fails `company.py validate`.

### 6.4 Browser runbooks (WP-L writes; A2 tickets and G-A read)

Machine source `tools/gtm/runbooks/<stem>.runbook.json`, where `<stem>` =
`system_names.runbook_stem(tier_system)` (03_schemas.md §3.22; e.g. `meta_ads` for tier `meta`),
with the prose twin `knowledge/marketing_kb/runbooks/<stem>.md` (prose only; no code reads it).
**DECIDED HERE:** a JSON sidecar, so hooks never parse markdown.

**Trust root (DECIDED HERE; plan §20.8 N1, §7.1).** A runbook sets a browser write's
`allowed_hosts`, `allowed_tools`, `max_mutating_calls`, its acting-as check, its before-check and,
for every browser `$` row, its ceiling and currency checks; its `read_hosts`/`login_hosts` feed G-A's
ticketless navigate allowlist. So the machine runbooks live under `tools/gtm/` (05_approver.md
§5.5 TRUST_PATHS: the whole `tools/gtm/` subtree, so a working-tree change fails
`approval_sig.trust_root_ok` and refuses every signed path), and **every consumer reads the HEAD
bytes**, never the working tree:
- **One loader.** `runbook_validate.load_head(R: Path, stem: str) -> tuple[dict | None, str]`
  (§6.4b): `git -C <R> show HEAD:tools/gtm/runbooks/<stem>.runbook.json`, then compares those bytes
  with the working-tree file; returns `(parsed, "")` only when they are byte-identical, else
  `(None, <code>)` with code `runbook_not_at_head` (absent at HEAD), `runbook_dirty` (working tree
  differs from HEAD, or is missing while HEAD has it) or `runbook_unreadable` (git error, bad JSON).
  Fails closed on every error.
- **`ticket --write` / `--write-batch` / `--read` (02_act.md §2.4; R16).** Load through `load_head`
  (any non-empty code → exit 3 with that code, no ticket), then run `runbook_validate.validate_obj`
  on the **HEAD** object against the HEAD tier table (`git show HEAD:tools/gtm/tier_table.json`);
  any problem → exit 3 `runbook_invalid`, no ticket. The ticket's `allowed_hosts`,
  `allowed_tools`, `max_mutating_calls`, steps and before-check values are copied from that HEAD
  object only.
- **Runbook placeholder filling** (the brief a write ticket carries) uses the same HEAD object.
- **G-A `runbook_hosts` (04_hooks.md §4.1 helper; R17).** Reads `git show HEAD:` at the new path;
  a working tree that differs, or any error, contributes **no** hosts for that system (fail closed:
  a dirty runbook can only narrow the allowlist, never widen it).
- **G-W (04_hooks.md §4.3; R17)** adds `R/tools/gtm/runbooks/` to the GTM-scope trust roots (like
  `setup_scripts/`), so a GTM session cannot Write/Edit a runbook without the operator-signed marker.
A2/B tests (each RED when its check is reverted): a working-tree edit to a committed runbook that
removes a `currency_check` entry → `ticket --write` exit 3 `runbook_dirty` (and, with the edit
committed to a tmp HEAD, `runbook_invalid` / `currency_check_missing`); a working-tree edit adding a
host to `allowed_hosts` of a `$` browser row → mint refused, and a mint from the clean tree carries
exactly the HEAD `allowed_hosts`; G-A `runbook_hosts` with a working-tree runbook that adds a
`read_hosts` entry → that host is not in the navigate allowlist.
```json
{"schema": "gtm.runbook.v1", "system": "gbp", "login_hosts": ["accounts.google.com"],
 "read_hosts": ["business.google.com", "www.google.com"],
 "read_paths": [
   {"id": "reviews_list", "start_url": "https://business.google.com/reviews", "clicks": ["Reviews tab"], "expect": {"title_contains": "Reviews"}},
   {"id": "profile_hours", "start_url": "https://business.google.com/n/{account_id}/profile", "clicks": ["Hours"],
    "expect": {"acting_as": "{brand_display_name}", "title_contains": "Business Profile"}}],
 "writes": {"gbp.hours_edit": {
    "allowed_hosts": ["business.google.com"],
    "allowed_tools": ["browser_navigate", "browser_snapshot", "browser_take_screenshot", "browser_wait_for", "browser_click", "browser_type"],
    "max_mutating_calls": 12,
    "steps": [{"n": 1, "do": "navigate", "target": "https://business.google.com/n/{account_id}/profile",
               "expect": {"acting_as": "{brand_display_name}", "title_contains": "Business Profile"}},
              {"n": 2, "do": "click", "target": "Edit hours", "opens_editor": true, "expect": {"dialog": "Hours"}},
              {"n": 3, "do": "snapshot", "expect": {"before": {
                  "Monday": "{before.mon}", "Tuesday": "{before.tue}", "Wednesday": "{before.wed}", "Thursday": "{before.thu}",
                  "Friday": "{before.fri}", "Saturday": "{before.sat}", "Sunday": "{before.sun}", "Special hours": "{before.special_hours}"}}},
              {"n": 4, "do": "type", "target": "Monday", "value": "{after.value.mon}"},
              {"n": 5, "do": "click", "target": "Save"},
              {"n": 6, "do": "snapshot", "expect": {"acting_as": "{brand_display_name}"}}],
    "verify": {"read_path": "profile_hours", "field": "hours"}}},
 "change_history": {"kind": "snapshot_diff", "notes": "…"}}
```
(The example types only Monday, to stay short. A real `hours_edit` runbook has one `type` step per
day, and its before-check already covers all eight keys, as the validator requires.)

**Required keys.** Top level: `schema`, `system` (= the file stem), `login_hosts`, `read_hosts`,
`read_paths`, `writes`, `change_history` (`kind` ∈ `snapshot_diff|api|ui`, `notes`); **optional**
`identity_in_url` (bool, default `true`) and `acting_as_step` (a step `id`, below) — the two keys
04_hooks.md §4.1 rule 7b "Target proof on id-less URLs" reads from the committed runbook
(requests/04_hooks.md R41). `read_paths[]`: `id`, `start_url`, `expect` (`clicks` optional).
`writes[<row>]`: `allowed_hosts`, `allowed_tools`, `max_mutating_calls`, `steps`, `verify`
(`read_path`, `field`). `steps[]`: `n`, `do`; `id` (optional string, `[a-z0-9_]{1,40}`, **unique
across every `steps[]` of the whole runbook** — the name `acting_as_step` refers to; `n` is only an
order within one row); `target` for every `do` except `snapshot`, `screenshot` and `wait_for`;
`value` for `type`, `fill_form` and `select_option`; `expect` for `snapshot` and `wait_for`;
`opens_editor` (optional bool); `sets_status` (optional; one of the literals `"paused"`, `"live"`,
`"removed"`) and `saves` (optional bool), both used only by §6.4 "Mandatory paused status" and
"Mandatory status change (status rows)". `expect` keys: `acting_as`, `title_contains`, `dialog`,
`before`, `status`, `account_breadcrumb` (below).

**Id-less URLs (DECIDED HERE; 04_hooks.md §4.1 rule 7b; plan §6.3/§7/§18 top risk).** A system whose
write-flow pages do not carry the proving id in their URL (GBP from Google Search or
`business.google.com` overviews, Meta Business Suite pages without `asset_id`, wp-admin) declares
`"identity_in_url": false` **and** `"acting_as_step": "<step id>"`; `acting_as_step` must name the
`id` of a `writes[*].steps[]` step whose `expect.acting_as` is present. G-A then admits that system's
mutating calls without the URL proof and logs `target-unproven-admitted` (04 rule 7b), so the
acting-as check and the `account_breadcrumb` step below are the browser path's prevention there. A
runbook that omits `identity_in_url` (or sets it `true`) is judged by the URL proof, and any
`acting_as_step` it carries is still validated.

**Placeholder grammar (closed; DECIDED HERE).** Only these forms, filled only from structured fields
and never from untrusted inputs:
- `{account_id}`: `ctx.account.account_id` (often a display id, §6.2 target resolution step 2).
- `{account_keys.<k>}`: `system_names.account_keys(tier_system, ctx.account)[<k>]`, `<k>` ∈
  `system_names.ACCOUNT_LEVEL_KEYS` (e.g. `{account_keys.property_id}` for a GA4 property URL,
  `{account_keys.container_id}` for a GTM container URL). A `<k>` outside that set is
  `bad_placeholder`; a `<k>` the account cannot supply refuses the ticket (`account_key_missing`).
- `{brand_display_name}`: the `brands[].display_name` whose `id` equals the account's **effective
  brand** (`ctx.brand`, §6.2; on the browser side the ticket's effective brand, the `brand` 02_act.md
  §2.4 derives from `(action.system, action.brand)` exactly as §6.3 "Arguments from an action" does),
  never the raw `account.brand` field, so a suffix-only account fills it. A2 test: a suffix-only
  `system: "website_remodeling"` account fills `{brand_display_name}` with the remodeling brand's
  display name; RED when it reads `account.brand` (a `KeyError` or an empty value).
- `{after.text}`, `{before.text}`: TXT rows only.
- `{after.value.<k>}`, `{before.<k>}`: `<k>` ∈ the row's `after_value_fields`. `{after.value.<k>}`
  resolves to `action.after.value[k]` and `{before.<k>}` to `action.before.value[k]`. This is the
  only form restricted to row keys (F4).
- `{target_ids.<k>}`: `ticket.target_ids[<k>]` — the check-1-verified ids the write ticket carries
  (03_schemas.md §3.6), for an **object-level** key only: `<k>` ∉ `system_names.ACCOUNT_LEVEL_KEYS`
  and `<k>` is a key of the row's `id_fields` or a key `system_names.target_ids` yields for the
  row's system (03 §3.22 grammar table). An account-level `<k>` (use `{account_keys.<k>}`) or any
  other key is `bad_placeholder`; a `<k>` the ticket does not carry refuses the ticket
  (`target_missing`). `target_ref` itself is never a placeholder. This is how a runbook reaches the
  one object the action addresses (e.g. `meta.campaign_pause` navigating to
  `…/campaigns?selected_campaign_ids={target_ids.campaign_id}`, a GBP review reply to
  `…/reviews/{target_ids.review_id}`); a runbook never selects its object by name from page state.
  Filling this form in `dispatch_brief.steps` from the ticket's `target_ids` is pending
  (requests/06_connectors.md R33 → 03_schemas.md §3.6). In a `read_paths[]` entry (e.g. the
  object-scoped `committed_ceiling` read path) it is filled from the **read** ticket's `target_ids`,
  which R33 asks 03 §3.6 to carry for a read naming one object; a read ticket without them refuses a
  read path that uses the form (`target_missing`).
- `{after.new_absolute_value}`, `{after.unit}`: **amount rows only** (§6.2 "Money binding" (a):
  rows whose `after_fields` are `[new_absolute_value, unit]` and that are **not** status rows), in
  any step. The one other use is the ceiling entries of a `commits_on_enable: true` row's
  `expect.before` (§6.4 "Ceiling rows"), never a step `value`. On every other status row (pause,
  stop, remove) the form is `bad_placeholder`, and a status row's mutating step carrying it is also
  `status_row_writes_amount` (§6.4b).
- `{before.current_absolute_value}`, `{before.unit}`: money rows (amount and status rows); on a
  status row only inside `expect.before`.
  `{before.current_absolute_value}` resolves to `action.before.value.current_absolute_value` (for a
  status row, the committed amount of §6.2 "Committed amount of a status row");
  `{before.unit}` to `action.before.value.unit` when present (every enable-bound action has it after
  02_act.md rule 5a), else to `action.after.unit` (an amount row never changes the period; a
  period change is a different row).

**No placeholder in a host position (DECIDED HERE).** A placeholder anywhere in the scheme or
authority (host, port, userinfo) of a `navigate` target or a `read_paths[].start_url` is
`bad_placeholder`: `host_not_allowed` compares a literal host with the row's literal
`allowed_hosts`/`read_hosts`, and runbooks are per system, shared by every company, so a
per-company host could never be listed. No Wave-2 browser runbook needs one (a brand's own site is
served by the wordpress connector's API, `{pack_domains}`, §6.1); adding a `{brand_host}` token is
a contract change that must also define how ticket minting and G-A expand `allowed_hosts` for it.
L3 test: `"target": "https://{account_keys.site_host}/wp-admin"` → `bad_placeholder`; RED when
host placeholders are accepted.

`target_ref` is never a placeholder (FID-02). A write row with no `writes[<row id>]` entry in its
system's runbook cannot be ticketed (`ticket --write` exit 3 `runbook_row_missing`, 02_act.md §2.4).

**`steps[].do` → MCP tool (DECIDED HERE; the validator and G-A use this table):**

| do | tool | do | tool |
|---|---|---|---|
| `navigate` | `browser_navigate` | `file_upload` | `browser_file_upload` |
| `click` | `browser_click` | `handle_dialog` | `browser_handle_dialog` |
| `type` | `browser_type` | `wait_for` | `browser_wait_for` |
| `fill_form` | `browser_fill_form` | `snapshot` | `browser_snapshot` |
| `select_option` | `browser_select_option` | `screenshot` | `browser_take_screenshot` |
| `press_key` | `browser_press_key` | | |

Mutating steps: `click, type, fill_form, select_option, press_key, file_upload, handle_dialog`.

**Mandatory acting-as check (plan §3.4/§7.5).** Every `writes[<row>]` has an
`expect.acting_as: "{brand_display_name}"` on a step at or before its first mutating step. An
`opens_editor` click may come before it only when an earlier `navigate` step already carried the
page-level `acting_as`. The row also has a final `snapshot` step with the same expectation, which
serves as the after snapshot. The gtm-operator aborts with `reason: acting_as_mismatch` (no further
mutating call) on any difference.

**Mandatory account breadcrumb (DECIDED HERE; 03_schemas.md §3.4.1 `in_account` part (2), the
browser twin of §6.2 target-resolution step 7; requests/03_schemas.md R28, R61 (b)).** Every
`writes[<row>]` whose row has any `id_fields` key of kind `in_account` (03 §3.4.1), or any
`nested_id_paths` pattern of kind `in_account`, carries, **before its first mutating step** (an
`opens_editor: true` click excepted, as for the before-check), a `snapshot` or `wait_for` step whose
`expect.account_breadcrumb` is an object holding `"account_id": "{account_id}"` and, when the row's
system has an account-level key in `system_names.ACCOUNT_LEVEL_KEYS` that the object's page shows
(e.g. google_ads `customer_id`, meta `ad_account_id`), `"<k>": "{account_keys.<k>}"` for it. The
gtm-operator confirms that the page URL or the page's account breadcrumb/header shows each value
(after `normalize_account_id` on both sides) and otherwise aborts with `reason: before_mismatch`,
before any mutating call. The one step covers every `in_account` id the row carries, top-level and
nested (each object selected on that page belongs to the account shown). Validator code
`in_account_check_missing` (§6.4b). P2 test (L, fake browser; 03 §3.4.1): an `L.object_delete` whose
page breadcrumb shows another business's account id → the gtm-operator aborts `before_mismatch`
with zero mutating calls.

**Mandatory before-check (§20.7/§20.9).** Before its first mutating step (an `opens_editor: true`
click excepted), every `writes[<row>]` has a `snapshot`/`wait_for` step whose `expect.before`
contains `"{before.<k>}"` for **every** `<k>` in the row's `after_value_fields` (or `"{before.text}"`
for a TXT row). **Money amount rows** (every browser `$` row: `lsa.budget_edit`, `L.paid_budget_edit`,
`meta.spending_limit_edit`, `meta.adset_budget_edit`, `google_ads.campaign_budget_edit`, the
`{thumbtack,angi}` amount rows, pause, stop and remove rows, …) have no `after_value_fields`, so for them the
before-check carries instead `{"<budget field>": "{before.current_absolute_value}", "<budget period
field>": "{before.unit}", "<currency field>": "USD"}` (on a `commits_on_enable: true` row the
ceiling entries of "Ceiling rows" below take the place of the first two), compared exactly as the ceiling rows below
(thousands separators ignored, period mapped per §6.2's period → `unit` list, the currency must
read the code `USD`). A **status row** (§6.2: pause, stop, remove, or enable-bound) additionally carries
`"<status field>": "<literal platform status label>"` — the live label for a pause, the paused label
for an enable, and for a remove the array of the live and paused labels (§6.2 "Browser remove
rows"). So a browser budget edit never writes the signed amount without first confirming the
amount, period and currency the operator saw (plan §20.9 "never overwrites blindly"). The coverage is static: the validator checks the row's key list, not the keys a
given action sets. The gtm-operator compares the on-page values and aborts with
`reason: before_mismatch` on any difference, before any mutating call. Create rows with no prior
object state use `"before": {"absent": "<selector text>"}`.

**Ceiling rows (FID-03).** A browser enable is ticketed only when the row's tier system also has
an API account serving `committed_ceiling` (§6.2 "Agent-executable enables"; 03_schemas.md §3.6
`enable_not_agent_executable`); on a browser-only system the operator performs the enable and the
`committed_ceiling` read path serves `authorize` (and `_nomatch` signing) only. For a row with `commits_on_enable: true` (§6.2 "Enable-bound actions"):
- that before-check's `expect.before` carries `{"<budget field>": "{after.new_absolute_value}",
  "<budget period field>": "{after.unit}", "<currency field>": "USD"}` **in place of** the money
  amount row entries `"{before.current_absolute_value}"`/`"{before.unit}"` for the same two keys (a
  JSON object cannot hold one key twice, and `json.loads` keeps the last). No check is lost:
  authorize's ceiling read (02_act.md rule 5a) overwrites `before.value.current_absolute_value`/`unit`
  with the platform value and refuses `enable_value_mismatch` unless it equals
  `after.new_absolute_value`/`after.unit`, and the approval signs that value, so both placeholders
  resolve to the same strings at mint time. On such a row `before_check_missing` does **not**
  require the `{before.current_absolute_value}`/`{before.unit}` entries (it still requires the
  status entry), and `ceiling_check_missing` requires the `{after.…}` ones. The amount is compared
  with thousands separators ignored. The period is mapped per §6.2's period → `unit` list. The
  currency code must read `USD`: a bare `$` is not accepted as proof of currency, and `CA$`, `A$`,
  `€` and every other code fail. Any difference → `before_mismatch`, no mutating call.
- the runbook has a `read_paths[]` entry with id `committed_ceiling` (§6.2 browser fresh read). The
  same read path is mandatory in every runbook whose `writes` carry any status row (pause, stop, remove or
  enable-bound), so a browser `_nomatch` enable-bound action on that system also has a snapshot
  source for `authorize`.

**Mandatory paused status (paused-create rows; 03_schemas.md §3.2 "Paused creates";
requests/03_schemas.md R38 (b)).** For every row in `connectors.PAUSED_CREATE_ROWS` (§6.2), the
runbook's `writes[<row>]` carries, in step order:
- exactly one step with `"saves": true` — the mutating step that submits the create (e.g. the
  final "Publish"/"Save" click);
- before it, at least one mutating step (`click`, `select_option` or `fill_form`) with
  `"sets_status": "paused"`, which sets the platform's own status control to its paused state (the
  status is a row constant, so its `value`/`target` is a literal, never a placeholder);
- after it, a `snapshot` or `wait_for` step whose `expect` carries `"status": "<literal paused
  label>"` — the post-save status read.
The gtm-operator aborts with `reason: created_not_paused` (no further mutating call) when the
post-save read shows any other label; A2's `verify` of the created object then applies 03_schemas.md
§3.2's fail-verify rule and plan §20.6 (an urgent `$` card proposing the pause, with a push
notification; this file does not restate either). The
browser twin of the API's forced PAUSED status (§6.2), and validator code `create_status_unpinned`
(§6.4b).

**Mandatory status change (status rows; DECIDED HERE; the browser twin of §6.2 "Money binding"
(b)).** A status row (pause, stop, remove or enable-bound, §6.2) changes **only** the object's
status and never writes an amount, exactly as on the API. Its `writes[<row>]` carries, in step order:
- exactly one step with `"saves": true` (the mutating step that commits the change);
- at or before it, a mutating step (`click`, `select_option` or `fill_form`) with `sets_status` equal
  to the row's target status — `"paused"` for a pause or stop row, `"live"` for an enable-bound row,
  `"removed"` for a remove row — whose `value`/`target` is a literal label, never a placeholder;
- after it, a `snapshot` or `wait_for` step whose `expect` carries `"status": "<literal label of that
  target status>"` (the post-save status read);
- `verify.read_path == "committed_ceiling"`, so the browser verify reads the configured ceiling and
  status together and applies §6.2's status-row `verify_read` rule (committed amount **and**
  `configured_ceiling == before.value.current_absolute_value`);
- **no** mutating step whose `value` holds an amount placeholder (`{after.new_absolute_value}`,
  `{after.unit}`, `{before.current_absolute_value}`, `{before.unit}`) or whose `target` equals the
  budget-field or period-field key of the row's before-check (the keys whose `expect.before` values
  are those placeholders, or the ceiling entries of a `commits_on_enable` row).
So a pause runbook can never type the signed `"0.00"` into the budget field: the validator refuses
it (`status_row_writes_amount`), and if the page were zeroed anyway, verify fails on
`configured_ceiling`. **Amount rows** ((a) in §6.2) are the mirror image: every mutating step whose
`target` is the before-check's budget-field key has `value` exactly `"{after.new_absolute_value}"`
(nothing else, no literal, no concatenation), at least one such step exists, and a step targeting
the period-field key has `value` exactly `"{after.unit}"` (`amount_step_unbound`, §6.4b).

**Object addressing (DECIDED HERE; FID-02, 04_hooks.md §4.1 rule 7b).** Every row with
`object_scope: "object"` (03_schemas.md §3.4.1) reaches its object through a `navigate` step, before
its first mutating step, whose `target` URL embeds `{target_ids.<k>}` for at least one object-level
key, so G-A rule 7b judges the verified id in the URL; a row that reaches its object only by
clicking a name on a list page is refused (`object_unaddressed`, §6.4b). (A create row's parent id,
e.g. `meta.adset_create`'s `campaign_id`, counts: it is object-level.)

The validator `tools/gtm/runbook_validate.py` (§6.4b; WP-L3) refuses a write runbook that lacks any
of these. It runs in every L sub-WP's P2 tests **and** at mint time: `ticket --write`/`--write-batch`/
`--read` run `validate_obj` on the HEAD bytes and refuse exit 3 `runbook_invalid` on any problem
(§6.4 "Trust root").

### 6.4b Runbook validator API (WP-L3; IMP-10)

```python
# tools/gtm/runbook_validate.py — stdlib only; imports only system_names and the connectors package root
# (is_create_row, PAUSED_CREATE_ROWS; §6.2), never gtmlib
def validate(path: Path, *, tier_table: dict) -> list[str]
    # problems, [] = ok; each "<file name>:<JSON pointer>: <code>: <detail>"; never raises on bad
    # runbook content (unreadable file / bad JSON → one "schema" problem). = validate_obj on the parsed file.
def validate_obj(obj: object, stem: str, *, tier_table: dict) -> list[str]
    # the same checks on an already-parsed object (the HEAD bytes load_head returned); file name in problems = <stem>.runbook.json
def load_head(R: Path, stem: str) -> tuple[dict | None, str]
    # §6.4 "Trust root": HEAD bytes via `git -C R show HEAD:tools/gtm/runbooks/<stem>.runbook.json`, refused unless
    # byte-identical to the working tree; codes runbook_not_at_head | runbook_dirty | runbook_unreadable; never raises
def main(argv) -> int
    # CLI: runbook_validate.py [--tier-table <abs path>] <file>...   (default R/tools/gtm/tier_table.json)
    # prints every problem to stdout, one per line; exit 0 all clean, 3 any problem, 2 usage, 1 internal
```
`tier_table` is the parsed `tier_table.json` (03_schemas.md §3.4). This section is the one
specification; 08_seats_wps.md §9 carries only a pointer to it (Appendix B #117). Problem codes (tests
assert on the code, never the detail; L3 has one test per code):
- `schema`: not `gtm.runbook.v1`, a required key (§6.4) missing, or a wrong type.
- `system_mismatch`: `system` ≠ the file stem.
- `unknown_row`: a `writes` key that is not a tier-table row `id`.
- `row_system_mismatch`: a `writes` row whose `system_names.runbook_stem(row.system)` ≠ the file
  stem. `L.*` rows are allowed in any runbook whose stem's tier system has `connector_system` = `listings`.
- `bad_do`: a `steps[].do` outside the §6.4 table.
- `bad_placeholder`: a placeholder outside the §6.4 grammar for that row, including any `target_ref`,
  a `{target_ids.<k>}` with an account-level or unknown `<k>`, an amount form on a row the grammar
  excludes it from, and any placeholder in the scheme/authority of a `navigate` target or
  `read_paths[].start_url` (§6.4 "No placeholder in a host position").
- `tool_not_allowed`: an `allowed_tools` entry outside the G-A write-ticket set (04_hooks.md §4.1),
  or a step whose mapped tool is not in its row's `allowed_tools`.
- `host_not_allowed`: a `navigate` target host outside the row's `allowed_hosts`, or a
  `read_paths[].start_url` host outside `read_hosts`.
- `mutating_over_cap`: the row has more mutating steps than `max_mutating_calls`.
- `acting_as_missing`: §6.4 mandatory acting-as check absent (before the first mutating step, or
  the final snapshot).
- `before_check_missing`: §6.4 mandatory before-check absent, incomplete for the row's key list, or
  after the first mutating step without `opens_editor`. For a money amount row that is not a
  `commits_on_enable: true` row: the before-check lacks the `{before.current_absolute_value}` or
  `{before.unit}` entry. For every status row (pause, stop, remove or enable-bound, §6.2): it lacks
  the status entry.
- `ceiling_check_missing`: a `commits_on_enable: true` row whose before-check lacks the ceiling
  amount/period entries (`{after.new_absolute_value}`/`{after.unit}`), which replace the
  `{before.…}` amount/period entries on that row (§6.4 "Ceiling rows"). L3 test: a valid
  `writes["google_ads.campaign_enable"]` fixture whose before-check is `{"<budget field>":
  "{after.new_absolute_value}", "<period field>": "{after.unit}", "<currency field>": "USD",
  "<status field>": "<paused label>"}`, with the `committed_ceiling` read path, a `navigate` to a
  `{target_ids.campaign_id}` URL, a `sets_status: "live"` save step, a post-save status read and
  `verify.read_path: "committed_ceiling"`, validates with `[]`;
  RED when `before_check_missing` still demands the `{before.…}` amount entries on a ceiling row.
- `currency_check_missing`: **any** money amount row (not only `commits_on_enable` rows) whose
  before-check lacks the `USD` currency expectation.
- `ceiling_read_missing`: a runbook carrying a `commits_on_enable: true` row or any other status row
  (pause, stop or remove verb, §6.2) with no `committed_ceiling` read path. L3 test: a runbook with
  only a remove row (and one with only a `{facebook,instagram}.boost_stop` row) and no
  `committed_ceiling` read path → `ceiling_read_missing`; RED when remove or stop rows are not
  treated as status rows.
The validator reads the flag only as `row.get("commits_on_enable") is True` (the 03_schemas.md
§3.4.1 name). L3 falsification test: a tier-table fixture whose enable row carries only
`commits_on_enable: true` and a runbook lacking the ceiling check → `ceiling_check_missing`; the test
goes RED when the validator reads the flag under any other name (e.g. `row.get("ceiling_enable")`).
Further L3 tests, one per code as above, include: an `lsa.budget_edit` runbook whose before-check
lacks `{before.current_absolute_value}` → `before_check_missing`; one lacking `USD` →
`currency_check_missing`.
- `verify_path_missing`: `writes[*].verify.read_path` is not a `read_paths[].id`.
- `create_status_unpinned`: a `writes[<row>]` entry of a `connectors.PAUSED_CREATE_ROWS` row
  (imported from the package root, §6.2) without all three of §6.4 "Mandatory paused status" — no
  `saves: true` step or more than one, no `sets_status: "paused"` mutating step before it, or no
  post-save `snapshot`/`wait_for` whose `expect` has a `status` key. Also: a `sets_status` or `saves`
  key on a row that is neither in that set nor a status row, or a `sets_status` value other than
  `"paused"` on a paused-create row. L3 test: a
  `writes["google_ads.campaign_create"]` entry without the `sets_status: "paused"` step, and one
  without the post-save status read → `create_status_unpinned` each; RED when the check is removed.
- `status_unpinned`: a status row (pause, stop, remove or enable-bound, §6.2) without all of §6.4
  "Mandatory status change" — no `saves: true` step or more than one; no mutating step at or before
  it whose `sets_status` equals the row's target status (`paused`/`live`/`removed`), or one whose
  `value`/`target` holds a placeholder; no post-save `snapshot`/`wait_for` whose `expect` has a
  `status` key; or `verify.read_path` ≠ `"committed_ceiling"`. L3 tests: a
  `writes["google_ads.campaign_pause"]` without the `sets_status: "paused"` step, one without the
  post-save status read, and one whose `verify.read_path` is not `committed_ceiling` →
  `status_unpinned` each; RED when the check is removed.
- `status_row_writes_amount`: a status row with a mutating step whose `value` contains
  `{after.new_absolute_value}`, `{after.unit}`, `{before.current_absolute_value}` or `{before.unit}`,
  or whose `target` equals the budget-field or period-field key of the row's before-check (§6.4
  "Mandatory status change"). L3 test: a `google_ads.campaign_pause` runbook with a `type` step
  `{"target": "<budget field>", "value": "{after.new_absolute_value}"}` (and one typing the literal
  `"0.00"` into the budget field) → `status_row_writes_amount`; RED when the check is removed.
- `amount_step_unbound`: an amount row (§6.2 "Money binding" (a)) with no mutating step targeting
  its before-check's budget-field key, or one whose `value` is not exactly
  `"{after.new_absolute_value}"`, or a step targeting the period-field key whose `value` is not
  exactly `"{after.unit}"`. L3 test: an `lsa.budget_edit` runbook whose budget `type` step has the
  literal value `"45.00"` → `amount_step_unbound`; RED when the check is removed.
- `in_account_check_missing`: a `writes[<row>]` whose row has an `in_account` `id_fields` key or an
  `in_account` `nested_id_paths` pattern, with no `snapshot`/`wait_for` step before its first
  mutating step (an `opens_editor` click excepted) whose `expect.account_breadcrumb` holds
  `"account_id": "{account_id}"` (§6.4 "Mandatory account breadcrumb"). L3 tests: a
  `meta.adset_targeting_edit` runbook without the step → `in_account_check_missing`, the same with
  the step placed after the first mutating step → `in_account_check_missing`, and with it before →
  no such problem; RED when the check is removed.
- `acting_as_step_invalid`: `identity_in_url` is `false` and `acting_as_step` is absent, or names no
  step `id` of this runbook, or names a step whose `expect` has no `acting_as`; also an
  `acting_as_step` that names no step `id` when `identity_in_url` is absent/`true`, a duplicate step
  `id`, an `id` outside `[a-z0-9_]{1,40}`, or an `identity_in_url` that is not a bool (§6.4 "Id-less
  URLs"). L3 tests: `identity_in_url: false` with no `acting_as_step`; with one naming a missing id;
  with one naming a step without `expect.acting_as`; and two steps sharing an `id` →
  `acting_as_step_invalid` each; `identity_in_url: false` with `acting_as_step` naming a step whose
  `expect.acting_as` is `"{brand_display_name}"` → no such problem; RED when the check is removed.
- `object_unaddressed`: a row with `object_scope: "object"` whose steps have no `navigate`, before
  the first mutating step, with a `target` URL embedding `{target_ids.<k>}` for an object-level
  `<k>` (§6.4 "Object addressing"). L3 test: a `meta.campaign_pause` runbook that navigates to the
  campaign list and clicks the campaign by name → `object_unaddressed`, and the same runbook
  navigating to a URL with `{target_ids.campaign_id}` validates; RED when the check is removed.

### 6.5 Connector tests

Recorded JSON fixtures under the connector's `tests/fixtures/` and the injected fake transport (§6.5b).
The fake HTTP layer and fixture loader are one shared module, `tools/gtm/connectors/testkit.py`,
owned by **L3** (08_seats_wps.md §9). L1 and L2 import it and never write their own copy.
**Test-module layout (DECIDED HERE).** Connector tests live in
`tools/gtm/connectors/<c>/tests/test_<c>_<topic>.py` (the connector name in every file name, so
no two connectors' test files share a basename), and `tests/` directories carry **no**
`__init__.py`. Each test file's first statement is `sys.path.insert(0,
str(Path(__file__).resolve().parents[3]))` (= `tools/gtm`, the §6.1 import root), and tests import
`connectors`, `connectors.<c>.write` etc. by that root only. So pytest's default `prepend` import
mode imports each file under its unique basename, never as `gtm.connectors.<c>.tests.*`, and exactly
one `connectors` module object exists (§6.1). L3 test: collecting every connector's tests in one
pytest run yields one `sys.modules["connectors"]` and no `gtm.connectors` key; RED when a
`tests/__init__.py` is added.

**Test** that `write.py` cannot be run outside act.py: each L connector test calls
`gtm_bash_gate.decision(<command text>, environ, cwd)` (04_hooks.md §4.2: `decision(command,
environ, cwd, agent_type=None) -> tuple[bool, str, str, bool]`, i.e. `(block, reason, message,
unconditional)`) directly for each of its own `write.py` command forms (`python3
<R>/tools/gtm/connectors/<c>/write.py`, and `python3 -m connectors.<c>.write` with `cwd =
<R>/tools/gtm`), with `environ` carrying `CLAUDE_GTM_COMPANY`, and asserts `result[0] is True and
result[1] == "connector-write-outside-act"`. (`decide(ev, environ)` is `gtm_task_gate`'s API, 04 §4.6,
not G-B's.) The end-to-end variant through `bash_gate.sh` is
written by B2 and runs only at the post-Wave-2 activation train (04_hooks.md §4.7), not in Wave 2.

### 6.5b Network seam and testkit API (WP-L3; IMP-10)

**One network seam (DECIDED HERE).** Every connector's platform I/O, including the OAuth
JWT-bearer token POST (§6.3 `key` route; no refresh token exists, §6.3), goes through `connectors.http_request` in the package root
`tools/gtm/connectors/__init__.py` (L3). It is always called through the package
(`connectors.http_request(...)`, never `from … import http_request`). The host guard runs inside
`http_request`, and only the transport below it is replaceable, so tests exercise the guard too.
Stdlib only (00_global_paths.md §0.2), so no vendor SDK is used.
```python
class HostNotAllowed(Exception): ...
class MutationOutsideApply(Exception): ...             # mapped to validation "mutation_outside_apply" (§6.3 exception table)
class RedirectRefused(Exception):                      # mapped by .sent (§6.3 exception table): False → validation, True → unknown
    def __init__(self, code: str, *, sent: bool): super().__init__(code); self.sent = sent
def http_request(ctx, method: str, url: str, *, mutating: bool, params: dict | None = None,
                 json_body: object = None, data: bytes | None = None, headers: dict | None = None,
                 timeout: float = 30.0) -> dict
    # 1. host guard (below), before any I/O;
    # 2. mutating is true and (ctx.mutation_hook is None or ctx.dry_run) → raise MutationOutsideApply("mutation_outside_apply"),
    #    before any I/O: a mutating request is legal ONLY inside connectors.idempotent_apply (plan(), verify_read,
    #    dedupe_probe, read(), a build_read_ctx context and every dry-run ctx have no hook);
    # 3. if mutating: ctx.mutation_hook();
    # 4. r = _transport(method, url, params=..., json_body=..., data=..., headers=..., timeout=...);
    # 5. 300 <= r["status"] < 400 → raise RedirectRefused("redirect_refused", sent=mutating) (never retryable; below):
    #    sent=True means a mutating request left the process before the 3xx came back (§6.3 exception table)
    # 6. return r
    # data: form bodies only, always urllib.parse.urlencode(pairs).encode("ascii") with header
    # Content-Type: application/x-www-form-urlencoded (the caller sets it); json_body and data are never both set.
    # params: encoded by _transport (never by the caller) as
    #   full_url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)   when params is truthy,
    #   else url unchanged; the host guard judges `url` before encoding (params cannot change the host).
    # FakeHTTP receives the un-encoded `params` dict and compares it as a dict (below), never the encoded string.
class TestModeNoLive(Exception): ...                   # not a ConnectionError: a definitive refusal, never a transport failure
def _transport(method, url, *, params, json_body, data, headers, timeout) -> dict
    # the LIVE transport. First statement (00_global_paths.md §1.1 (2)): gtm_env.test_mode(os.environ)[0] true →
    # raise TestModeNoLive("test_mode_no_live") before any socket; connectors map it to error.code "validation",
    # message test_mode_no_live (read(): ok false), act.py to exit 3 test_mode_no_live. FakeHTTP replaces
    # _transport, so fixture tests never reach this check.
    # urllib: an opener built with urllib.request.build_opener(_NoRedirect) (called as module attributes), where
    # _NoRedirect(urllib.request.HTTPRedirectHandler).redirect_request returns None — so NO 3xx is ever followed
    # (the default opener follows 301/302/303/307/308 and copies every header except content-length/content-type,
    # Authorization included, to the new URL, which may be http:// or any host). Returns
    # {"status": int, "headers": dict, "json": object | None, "text": str}; never raises on an HTTP status
    # (the connector maps status → error.code). EXCEPTION ORDER (binding; urllib.error.HTTPError is a subclass of
    # URLError and so of OSError, and with _NoRedirect urllib raises HTTPError for EVERY 3xx/4xx/5xx):
    #   1. `except urllib.error.HTTPError as e:` FIRST → status = e.code, headers = dict(e.headers);
    #      a 3xx returns {"status": <3xx>, "headers": ..., "json": None, "text": ""} without reading the body
    #      (the Location body is never read); any other status reads e.read() and builds text/json as below;
    #   2. only then every other OSError / urllib.error.URLError / ssl.SSLError / TimeoutError → raise
    #      ConnectionError(str(e)).
    # A 2xx reply (no exception) builds text/json the same way. text = body.decode("utf-8", errors="replace")
    # ("" for an empty body). json is None when the body is empty, when the Content-Type's media type is neither
    # application/json nor ends with "+json", or when json.loads(text) raises; else the parsed value. A 2xx whose
    # connector expects JSON and gets json None is the "unparseable success body" of §6.2 (→ unknown).
```
**Redirects (DECIDED HERE; plan §20.3/§20.9a fail-closed host denial, §20.6 "any secret in a tool
call").** The host guard judges only the URL it is given, so the transport never follows a redirect
and `http_request` refuses every 3xx (`RedirectRefused` → `validation`, message `redirect_refused`,
`retryable: false`). A connector that genuinely needs to follow one re-issues the request itself
through `connectors.http_request` with the `Location` URL, so the host guard runs on the new host,
and it sends `Authorization` (and every header `FakeHTTP.calls` would redact) only when the new
host equals the original host exactly. A redirect on a mutating request is never re-issued.
L3 falsification test (FakeHTTP cannot exercise urllib, so it tests `_transport` directly): with
`gtm_env.test_mode` monkeypatched to `(False, [])` and `urllib.request.build_opener` monkeypatched
to wrap the real `_NoRedirect` opener around a stub `HTTPHandler`/`HTTPSHandler` that answers the
first URL with `302 Location: https://evil.example/x` and records every request → `_transport`
returns status 302 and `http_request` raises `RedirectRefused`; the stub recorded **zero** requests
to `evil.example`; RED when the default opener (`urllib.request.urlopen`) is restored. A second L3
test: a `mutating=True` `http_request` on a `build_read_ctx`-shaped ctx (no hook) and on a
`dry_run=True` ctx → `MutationOutsideApply`, zero `_transport` calls; RED when step 2 is removed.
A third L3 test, beside the redirect test and built the same way: the stub handler answers `400`
with `Content-Type: application/json` and body `{"error": "x"}` → `_transport` returns
`{"status": 400, "json": {"error": "x"}, …}` and raises nothing; a `401` with a `text/html` body →
status 401, `json` None; RED when `HTTPError` falls into the `ConnectionError` branch (the 400 would
become a transport failure).
`mutating` is required on every call. It is true for any request that can change platform state,
including POST endpoints used for writes. It is false for reads, even POST-shaped reads such as
Ads `googleAds:search`, and for the OAuth token POST.

**Host guard (plan §20.3, §20.9, §20.9a).** Parse the URL. The request is refused with
`HostNotAllowed` (the connector maps it to `error.code = "validation"`, message `host_not_allowed`,
and `read()` maps it to `ok: false`) when any of these holds:
- the scheme is not `https`.
- the lowercased host is neither in `ctx.allowed_hosts` nor matched by a `ctx.allowed_host_suffixes`
  entry `s` (`host.endswith(s)`, `s` always starting with `.`, so `evil-example.com` never matches
  `.example.com`). `connector_dispatch` builds `allowed_hosts` from the manifest `api_hosts`, the
  Google token host for Google connectors, and the exact `{pack_domains}`/`{lead_sink_host}`
  expansions; `allowed_host_suffixes` only from `{pack_domains}` (§6.1). L3 test (wordpress, brand
  domain `example.com`): `https://example.com/wp-json/x` and `https://blog.example.com/wp-json/x`
  allowed; `https://evil-example.com/…`, `https://example.com.evil.net/…` and the restoration
  brand's domain refused `host_not_allowed`; RED when suffix matching is replaced by a substring or
  unanchored `endswith(d)`.
- the host is a literal IP or a loopback name, **judged by text only, with no DNS resolution**:
  `ipaddress.ip_address(host.strip("[]"))` succeeds (any family, bracketed IPv6 included); or every
  dot-separated label is a decimal or `0x`-hex integer,
  `re.fullmatch(r"(?:0[xX][0-9a-fA-F]*|[0-9]+)(?:\.(?:0[xX][0-9a-fA-F]*|[0-9]+))*", host)` (the
  integer and hex spellings a resolver may accept); or the host is `localhost` or ends with
  `.localhost`. A hostname that resolves to a private, loopback or link-local address is **not**
  judged here (resolved-address checks are out of scope for Wave 2): the exact-host allowlist above
  admits only vendor hosts and the pack's own validated domains, so such a name can arise only from
  a vendor's or the pack's own DNS, a residual accepted in the same terms as plan §20.9a's host
  denial. L3 test: `https://10.0.0.1/`, `https://[::1]/`, `https://2130706433/`, `https://0x7f.1/`
  and `https://api.localhost/` → `HostNotAllowed` with zero DNS lookups (`socket.getaddrinfo`
  monkeypatched to record) and zero `_transport` calls; RED when the text check is removed.
- the host equals, or ends with, a `phi_denylist.json` `hosts[].host` / `host_suffixes[].suffix`
  whose `applies_to` is absent or contains `ctx.company`.
- the host is a `phi_denylist.json` host carrying `agency_app: true`, for every company (R5).
- `phi_denylist.json` is unreadable. The guard fails closed.
The guard runs before the mutation hook, so a refused request never writes a `started` line.
**Denylist path (DECIDED HERE):** `ctx.R / ".gtm_state" / "phi_denylist.json"` (00_global_paths.md
§1.2: `S = R/.gtm_state`), loaded with stdlib `json` by the connectors package root on every
`http_request` call (no cache; it is small). Connector code never imports `gtm_hooklib` or
`company` to find it, and test mode needs no special case: a test's ctx has a tmp `R`. Every L3
test that reaches the host guard (the host-guard tests, the test-mode test, every FakeHTTP-driven
connector test) sets up **a readable empty denylist fixture** at `<tmp R>/.gtm_state/phi_denylist.json`
(the 03_schemas.md §3.20 shape with empty lists) unless the test is about the denylist; without it
every request fails closed with `HostNotAllowed`.

**Subprocess seam (DECIDED HERE; 00_global_paths.md §1.1 consequence 2).** Every child process the
connector layer starts — credential step 4's `gcloud secrets versions access`, both `google_sa` mint
routes (`gcloud auth print-access-token`, `openssl dgst`), and every `secret_sink` gcloud call
(§6.6: `describe`, `versions add`, `create`, `versions disable`) — goes through one package-root function,
always called as `connectors._run(...)` (never `from … import`), so one monkeypatch covers every
caller:
```python
OPENSSL = "/usr/bin/openssl"                            # SIP-protected system binary, a literal
GCLOUD_SEARCH_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"   # fixed; never os.environ["PATH"]
def gcloud_path() -> str
    # resolved ONCE per process and cached: shutil.which("gcloud", path=GCLOUD_SEARCH_PATH), then os.path.realpath;
    # None → CredentialUnavailable("gcloud_missing"). The process PATH is never consulted, so a gcloud planted in
    # a directory an agent can write (a PATH entry under the home) is never run. (UNVERIFIED: that the operator's
    # SDK install lives in one of these directories; the coordinator confirms it with probe j2, and a different
    # location is a contract change to GCLOUD_SEARCH_PATH, never an environment override.)
def _run(argv: list[str], *, input: bytes | None = None, pass_fds: tuple[int, ...] = (),
         timeout: float = 60.0) -> tuple[int, bytes]
    # First statement: gtm_env.test_mode(os.environ)[0] true → raise CredentialUnavailable("test_mode_no_live"),
    # before any process starts. argv[0] must equal OPENSSL or gcloud_path() (else ValueError; no other binary is
    # ever run). Then subprocess.run(argv, input=input, stdout=PIPE, stderr=DEVNULL, pass_fds=pass_fds,
    # timeout=timeout, check=False, close_fds=True) → (returncode, stdout). stderr is discarded (it can echo
    # arguments); stdout is never logged. A TimeoutExpired or OSError → (-1, b"").
```
`CredentialUnavailable("gcloud_missing")` joins the step-4 and mint failure reasons (callers treat it
like `gsm_access_failed`/`token_mint_failed`; `secret_sink` exits 8). Test mode therefore can never
reach a live platform or secret through a child process either: `credential_getter` refuses at step
0, `_transport` refuses at its first statement, and `_run` refuses at its first statement for every
path that reaches it without going through `credential_getter` (a test that injected
`ctx.credential` and reached `mint_google_token`).

**Deviation from plan §8 (recorded here; 08_seats_wps.md Appendix B #141).** Plan §8 says to
generalize the CSA Google Ads builder into the runtime connector, keeping a thin CSA wrapper. This
contract does not. The `google_ads` connector is a fresh stdlib REST client, because the CSA builder
depends on the vendor gRPC SDK, which 00_global_paths.md §0.2 excludes. CSA's
`repo_tooling/google_ads/` builder is left as is and is not wrapped. It stays G-B-denied outside
act.py (04_hooks.md §4.2 rule a), so CSA ad-account writes also go through `act.py execute` and
this connector.

```python
# tools/gtm/connectors/testkit.py
class UnmatchedRequest(AssertionError): ...
class FakeHTTP:
    def __init__(self, fixtures_dir: Path): ...          # loads every *.json directly in fixtures_dir, in file-name order
    def install(self, monkeypatch) -> "FakeHTTP"
        # monkeypatch.setattr(connectors, "_transport", self.request), and as a backstop patches
        # urllib.request.build_opener, urllib.request.OpenerDirector.open and socket.create_connection to raise
        # UnmatchedRequest (the live _transport uses build_opener(_NoRedirect).open, never urlopen, so a urlopen
        # patch would be inert)
    def request(self, method, url, **kw) -> dict         # same signature/return as _transport
    def raise_after(self, fixture_name: str, exc: Exception) -> None   # consume that fixture, then raise exc (transport-failure tests)
    calls: list[dict]                                    # in order: {"method", "url", "params", "json_body", "data", "headers"};
                                                         # Authorization and any header, params key or form key whose lowercased
                                                         # name contains "token"/"key"/"assertion"/"password" → "<redacted>"
    def assert_all_consumed(self) -> None                # AssertionError naming each unused non-repeat fixture
def load_fixture(fixtures_dir: Path, name: str) -> dict  # one fixture file, parsed
def make_ctx(tmp_R: Path, *, manifest: dict, pack: dict, account: dict, tier_system: str,
             row: dict | None = None, **overrides) -> "connectors.ConnectorCtx"
    # the ONE test builder of a ConnectorCtx (L1/L2 fixture tests cannot import gtmlib or wait on A2's _build_ctx).
    # Defaults: company = pack["slug"]; home = tmp_R / "home"; R = tmp_R; state_dir = home/.claude/gtm/state
    # (created, 0700); brand = account.get("brand") or the suffix brand (system_names.tier_system_and_brand);
    # row = row or {}; manifest = the given dict (never read from disk); dry_run = False; now = a fixed tz-aware UTC
    # datetime (2026-01-01T00:00:00Z) lambda; credential = lambda: {k: "dummy-" + k for k in <the manifest's
    # credential.fields, keyed form selected by pack.lead_sink.kind>}; evidence_dir = state_dir/"evidence"/"test";
    # _secrets = set(); log = connectors.make_log(<that same set object>) (writes to sys.stderr); target_ids = {}; approved = None;
    # allowed_hosts / allowed_host_suffixes = the §6.1 expansion of manifest["api_hosts"] (+ the Google token host
    # for Google connectors); mutation_hook = None; snapshots_dir = state_dir/"snapshots"; gcloud_account =
    # gsm_project = None; _token_cache = {"token": "fake-token", "expires_at": <2100-01-01T00:00:00Z>} when
    # credential.auth is (or selects) google_sa, else {}; bound_assets = {}; upload_source = None. It also writes
    # the readable empty denylist fixture at tmp_R/.gtm_state/phi_denylist.json (§6.5b "Denylist path") unless it
    # exists. **overrides replace any field by name (e.g. target_ids=..., approved=..., _token_cache={} for a mint
    # test); an unknown name → TypeError. L3 test: make_ctx builds a ctx whose every field is set, and
    # connectors.auth_headers on a google_ads make_ctx ctx returns the fake bearer without a FakeProc call.
class FakeProc:                                          # the subprocess twin of FakeHTTP (§6.5b "Subprocess seam")
    def __init__(self): ...
    def on(self, argv_prefix: list[str], *, rc: int = 0, stdout: bytes = b"",
           reader: Callable[[list[str], bytes | None, tuple[int, ...]], None] | None = None) -> "FakeProc"
        # the first registered handler whose argv_prefix is a prefix of the call's argv answers it; reader (optional)
        # runs first and may os.read() an fd named in pass_fds (the openssl key-pipe test)
    def install(self, monkeypatch) -> "FakeProc"
        # monkeypatch.setattr(connectors, "_run", self.run), and as a backstop patches subprocess.run and
        # subprocess.Popen to raise UnmatchedRequest
    def run(self, argv, *, input=None, pass_fds=(), timeout=60.0) -> tuple[int, bytes]   # same signature/return as _run
    calls: list[dict]                                    # {"argv", "pass_fds", "input_len"}; never the input bytes (they can hold a key)
```
No handler matching → `UnmatchedRequest`, never a real process. `FakeProc` applies `_run`'s argv[0]
rule (`OPENSSL` or `gcloud_path()`, the latter monkeypatchable to a fixed string in tests) so a test
cannot pass with a binary the real seam would refuse.
Every `fixture_name`/`name` argument is the fixture **file stem without `.json`**, relative to the
`fixtures_dir` the FakeHTTP was built with (e.g. `raise_after("02_POST_campaigns_mutate", …)`); a
name ending in `.json`, or one that names no loaded fixture, raises `ValueError`.
Fixture files: `tests/fixtures/<case>/<nn>_<METHOD>_<slug>.json` (`<case>` = one test scenario,
`<nn>` = two-digit order). Content:
`{"request": {"method", "url", "params"?: {}, "json_body"?: {}, "data"?: "<form-encoded string>"}, "response": {"status", "headers"?: {}, "json"?: {}, "text"?: ""}, "repeat"?: false}`.
`request` returns the response of the **first unconsumed** fixture whose method and URL match (the
query string excluded) and whose `params`/`json_body`/`data`, when present, equal the call's
(`params` compared as dicts against the call's un-encoded `params`, never as an encoded string) (`data`
is compared after form-decoding both: the call's bytes with `urllib.parse.parse_qsl(data.decode("ascii"),
keep_blank_values=True)`, the fixture's string with the same `parse_qsl`, compared as lists of
pairs). `calls[].data` records the decoded pair list, with each redacted form key's value replaced
by `"<redacted>"`. The fixture is then consumed unless `repeat: true`. No
match → `UnmatchedRequest`, never a real network call. Fixtures hold no real token or secret. In
tests, `ctx.credential` is a lambda returning a fixed dummy dict with the manifest's `credential.fields`,
and a `google_sa` connector's ctx has `_token_cache` pre-filled with a far-future `expires_at`
unless the test is about minting (§6.3 "Tests and the token cache").
L1/L2 code against these signatures and stub them only until L3 lands them.

**Required connector tests.** Each connector with a `write.py` has all of these. Each is a
falsification test: it must go RED when the guard it names is reverted, and the WP's P2 evidence
shows that red run.
- (IMP-11) A `rate_limited` failure, then a retry of the same action → the retry makes the platform
  call and returns `ok: true`. A third `apply` returns the recorded success with **zero** new
  `FakeHTTP.calls`. A failure whose result has non-empty `applied_ops`, then a retry →
  `partial_prior_attempt` with zero write calls. **Transport:** `FakeHTTP.raise_after(<the write
  POST>, ConnectionError())`, then a retry → `partial_prior_attempt` with zero new write calls when
  the row's probe is `none` or returns `present`. With a `state_equals_before` probe whose read
  shows the before state, the retry proceeds. A ledger holding only a `started` line (simulated
  crash) is treated the same way. A `dry_run` ctx → `ValueError`, no ledger line.
- (FID-02) An action whose `target_ref` also carries a URL or host outside the parsed ids → every
  write call in `FakeHTTP.calls` addresses only the resolved-id object under `ctx.account`. A
  resolved object the platform reports under another account → `not_found` (`not_owned`), zero write
  calls. `target_id_conflict` and `target_missing` → `validation` with zero calls. For a connector
  with an `asset_link` row: a link to a GA4 property (or other `target_system` id) not in the pack's
  bucket is refused `link_target_not_in_pack` before any connector call, and one in the bucket that
  the target system's `owns` read reports as not owned → `not_owned` with zero write calls. For a
  connector with any `in_account` id kind (top-level or nested, §6.2 target-resolution step 7): an
  id whose ownership read reports another account → `not_owned`, zero write calls.
- (FID-03, connectors with a `commits_on_enable: true` row) A paused object whose configured ceiling differs
  from the signed `after.new_absolute_value` or `ctx.approved` → `before_mismatch` with zero write
  calls. Equal → the enable call is made. An account currency of `CAD` → `validation`
  `currency_mismatch`, zero write calls. `read(ctx, "committed_ceiling", …)` returns the
  §6.2 `data` shape. A2 test: `google_ads.auto_apply_enable` and `paid_api.usage_enable` are **not**
  enable-bound (§6.2: no `commits_on_enable` flag, not `_nomatch`) — no `committed_ceiling` read, no
  `ceiling_unreadable`; RED when enable-bound is keyed on the verb `enable` alone. Runbook side:
  `runbook_validate` returns `ceiling_check_missing`, `currency_check_missing` and
  `ceiling_read_missing` for the respective omissions.
- (F4 row-field backstop) An extra key in `after` → `validation`, zero write calls.
- (Before re-check) A platform value ≠ `before.value` for a changed field → `before_mismatch`, zero
  write calls, and the same per rule of §6.2 (money micros rounding, TXT whitespace, set-compared
  lists).
- (`campaign_state`) A `live` campaign behind a `@paused` row → `before_mismatch`, zero write calls.
  A `REMOVED` status → `before_mismatch`.
- (Credential fail-closed) `connectors.json` absent at HEAD, malformed, or with a payload missing a
  `credential.fields` key → `auth` / `credential_unavailable:<reason>`, and **zero** `FakeHTTP.calls`.
  An `oauth-google-x` secret name, an `agency_gsm_projects` project and a `gsm:` name outside
  `gtm-<company>-…` (`secret_not_per_company`) are refused the same way.
- (Host guard) A request to a host outside `api_hosts`, to a `phi_denylist` host applicable to the
  company, to an `agency_app: true` host (for every company), to `http://`, or to `127.0.0.1` →
  `HostNotAllowed` → `validation` `host_not_allowed`, and no `started` line. A 3xx reply from an
  allowed host → `validation` `redirect_refused`, zero requests to the `Location` host (§6.5b
  "Redirects"). A `mutating=True` request outside `idempotent_apply` → `mutation_outside_apply`.
- (Test mode, L3; 00_global_paths.md §1.1 (2)) With `GTM_TEST=1`, a readable empty denylist
  fixture (§6.5b "Denylist path") and **no** FakeHTTP installed, a
  `connectors.http_request` to an allowed host raises `TestModeNoLive` with
  `urllib.request.build_opener`, `urllib.request.OpenerDirector.open` and `socket.create_connection`
  monkeypatched to record calls → zero recorded calls; RED when the first statement of `_transport`
  is removed.
- (`is_api_executable`) False for a row not in `write_rows`, for `access` ≠ `api`, for a non-`gsm:`
  ref, and for `_nomatch`. `execute` of `_nomatch` → `validation` `not_agent_executable`, zero calls.
- (Account matching, A2) Against the committed fixture (accounts `system: "gbp"` + `brand:
  "remodeling"`), an action with system `gbp_remodeling` and one with system `gbp` + `brand:
  "remodeling"` both resolve the same account. An account written `system: "gbp_restoration"`,
  `brand: "remodeling"` → `account_ambiguous`. Two `gbp` accounts with `brand=None` and no
  `account_id` → `account_ambiguous`. `build_read_ctx` for an unmatched account →
  `ReadCtxAccountError` → `read.py main` exit 3 with nothing at `--out`.
- (Read isolation, A2) `build_read_ctx` with `CLAUDE_GTM_COMPANY` unset or naming another slug →
  `ReadCtxCompanyError` (`code` `company_mismatch`) → `read.py main` exit 13. A hipaa pack reading an `inbox_class_ops` op with `--out`
  outside `ST/untrusted/` → exit 3 `out_not_allowed`.
- (Manifest, L3) `tier_systems` equals the inverse of `system_names.connector_system`. Every
  `write_rows` id has a `dedupe` entry, and **no** `write_rows` id is a NEVER-tier row of
  `tier_table.json` (§6.3 class step clause 0). `google_ads` and `meta` list `ad_content`. Every `INBOX_CLASS_RE` read op is in `inbox_class_ops`.
  Every `google_sa` manifest carries a non-empty `credential.scopes`. Every `runbooks` path is
  `tools/gtm/runbooks/<runbook_stem(tier_system)>.runbook.json`.
- (Status rows) Every connector with a pause or remove row: the §6.2 "Committed amount of a status
  row" L tests.

### 6.6 Secret capture (WP-E ↔ WP-B1 ↔ WP-A2)

- `tools/gtm/setup_scripts/allowlist.json`:
  `{"schema": 1, "scripts": {"<script_id>": {"file": "setup_scripts/<file>.js", "sha256": "<hex of the exact function text passed to browser_evaluate>", "system": "meta", "secret_name_template_doc": "gtm-{slug}-meta-page-token", "target_hosts": ["developers.facebook.com"], "regenerates": true}}}`.
  The `.js` file content is exactly the `function` string the seat passes (G-A hashes it).
  `secret_name_template_doc` is **documentation only** (like the connector manifest's
  `secret_template_doc`, §6.1): no code reads it. The setup ticket's `secret_name` comes only from
  the target pack account's `credential_ref` (02_act.md §2.4 `ticket --setup`, I25). `system` must
  equal the setup row's tier system (03_schemas.md §3.4.4 `setup_capture` rows). `regenerates`
  (required) is true when the script issues a **new** platform token rather than reading an existing
  one.
- The captured value is the connector's credential payload (§6.3): one JSON object with the
  manifest's `credential.fields`. The capture script assembles it.
- Each capture script reads the token element, **blanks it before returning**, reads the page's
  acting-as label (the account/page/business name the platform shows as the signed-in actor), POSTs
  `{"ticket_id", "secret_name", "acting_as_label", "value"}` to
  `http://127.0.0.1:47823/capture` — the port is the literal `system_names.SECRET_SINK_PORT = 47823`
  (00_global_paths.md §1.4; a page script cannot read an environment variable and its allowlisted
  sha256 fixes its text, so the literal is in the script) — and returns only the sink's reply
  (below), never the value. `GTM_SECRET_SINK_PORT` changes only the port `serve` binds, and only
  under test mode (00 §1.4); test capture scripts are fixtures, not allowlisted production scripts.
- **WordPress capture role check (DECIDED HERE; plan §17 j "a dedicated per-site user at Editor
  level … never an Administrator's"; 03_schemas.md §3.4.1 `wp_gtm_user`, requests/03_schemas.md R70).**
  A `website_wordpress` application-password capture script, signed in as the target user, first
  reads that user's roles (`GET /wp-json/wp/v2/users/me?context=edit`, field `roles`; or the
  `/wp-admin/profile.php` role display when the REST route is disabled) **before** it creates or
  reads any application password. Unless `roles` is exactly `["editor"]` it returns
  `before_mismatch` to the seat, creates no application password and makes **no** POST to the sink,
  so nothing reaches GSM. The wordpress connector re-checks on the credential's first use: before
  its first other request in a ctx, `GET /wp-json/wp/v2/users/me?context=edit` with the captured
  credential; `roles != ["editor"]` → `CredentialUnavailable("wp_role_not_editor")` (mapped by the
  §6.3 exception table: `auth`, `credential_unavailable:wp_role_not_editor`; zero write calls). E
  test (fake WordPress): a capture whose role read returns `["administrator"]` aborts
  `before_mismatch` with zero sink POSTs and zero GSM writes; RED when the role read is removed. L
  test (wordpress): a fixture `users/me` reply with `roles: ["administrator"]` → every `apply` returns
  `credential_unavailable:wp_role_not_editor` with zero write calls; `["editor"]` → proceeds; RED when
  the connector check is removed.

**CLI (every mode takes `--company <slug>`; exit 13 when it is not a registered GTM company, or by
the per-mode company rule below):**
```
secret_sink.py serve       --company <slug> --ticket <ticket_id> --secret-name <name> [--timeout 600]   # one capture, then exits; <name> is BARE (no gsm:, §6.3 step 2)
secret_sink.py ingest-file --company <slug> --ticket <ticket_id> --secret-name <name>                   # fallback B
secret_sink.py prompt      --company <slug> --action <action_id>                                         # fallback C, operator's terminal, no-echo TTY
secret_sink.py scan        --company <slug> --ticket <ticket_id>                                         # second scan at ticket close
```
**Company rule, by mode (DECIDED HERE).** `serve`, `ingest-file` and `scan` run inside the GTM
session (or as act.py's subprocess): `CLAUDE_GTM_COMPANY` must be **set and equal** to `--company`
(the `build_read_ctx` rule), else exit 13. `prompt` runs in the operator's own terminal, where the
variable is normally unset: it must be **unset or equal** to `--company`; set to another slug →
exit 13. Its admission is the operator marker below, never the variable.

Every mode holds `S/secret_sink.lock` (non-blocking `flock`); busy → exit 12. That is the only
exit-12 check before ticket validation: `serve` binds its port **after** ticket validation (exit 7,
which includes the `script_id` check below), and a bind failure → exit 12.

**Ticket validation (`serve`, `ingest-file`, `scan`; exit 7 on any failure).** The ticket is class `setup`.
Its company equals `--company`. Its `secret_name` equals `--secret-name` (not checked by `scan`, which
takes none). **Status (requests/03_schemas.md R29; 03_schemas.md §3.6 setup state machine):** for the
storing modes (`serve`, `ingest-file`) its status is `pending` or `bound` and it is unexpired; any
other status — `stopped` (the operator seat has already exited, so no capture may arrive after it),
`closed`, `consumed`, `abandoned`, `expired` — → exit 7. `scan` is the close-time scan that
`ticket --close` and reconcile run on a `pending`, `bound`, `stopped` or `expired` setup ticket (03
§3.6), so it accepts those four statuses whatever the expiry and refuses only `closed`, `consumed`
and `abandoned` (exit 7). E tests: `serve` on a `stopped` ticket and on a `consumed` ticket → exit 7
(RED when the old "open, not closed or abandoned" wording is restored); `scan` on a `stopped` ticket
runs the scan (exit 0 when clean).
**Acting-as binding (requests/03_schemas.md R55, 03 §3.6 `setup` row, §3.21).** `serve` (and
`ingest-file`, once fallback B is sanctioned) reads `acting_as_expected` **from the setup ticket file** (never from the POST body or
any argument). A capture whose `acting_as_label` is absent, or differs from it after whitespace
collapse (exact string equality otherwise) → the value is discarded unstored, an isolation hit is
appended (`source: "secret_sink"`, `detail: "acting_as_mismatch"`, 03 §3.21), and `serve` replies
403 `refused:acting_as_mismatch` and exits 7. E test: a POST whose `acting_as_label` names another
business → 403, exit 7, zero gcloud calls, one isolation-hit line; a POST that also carries an
`acting_as_expected` field naming that other business is still refused (RED when the body's value is
read).

**`prompt` admission (fallback C; DECIDED HERE; plan §20.10).** The sign-in card is answered
asynchronously, often hours after any 15-minute setup ticket would have expired, so `prompt` takes
the **action**, not a live ticket, and mints its own:
1. Company rule above (exit 13).
2. `os.isatty(0)` must be true (the value is read with `getpass`, no echo); a non-TTY stdin — any
   agent's Bash tool call — → exit 7, stdout `prompt_refused not_a_tty`.
3. The operator marker: `gtmlib.session.consume_operator_ok(actx, "secret_sink_prompt", <action_id>)`
   (`actx = make_ctx(<slug>)`, 02_act.md §2.2)
   (02_act.md §2.2b; a GTMApprover-signed, Touch-ID `gtm.operator_ok.v1` record, 00_global_paths.md
   §1.4 "Operator authority"; command `secret_sink_prompt` is **pending** in `OPERATOR_OK_COMMANDS`,
   requests/06_connectors.md R34) returns a payload, else exit 7, stdout `prompt_refused
   operator_marker_invalid`. The nonce is consumed here, so one marker admits one run.
4. The folded action (`store.fold(actx)[action_id]`) exists, belongs to `--company`, is in state
   `authorized`, and its matched row is a `setup_capture` row (03_schemas.md §3.4.4); its account
   (matched as in §6.3 "Arguments from an action") has `credential_ref` `gsm:<name>`, and `<name>` is
   the secret this run stores. Any failure → exit 7, stdout `prompt_refused action_invalid`.
5. The sink then mints its own setup ticket through the same writer `ticket --setup` uses
   (`tickets.mint_setup(actx, action, script_id=None, created_by="secret_sink_prompt")`, pending,
   R34), with `secret_name = <name>`, the 03_schemas.md §3.6 15-minute expiry starting **now**, and
   `session_id` = the `session_id` of the action's latest `authorize` event (so the leak scan below
   covers the session that set the capture up, where a value pasted by mistake would sit). Every
   later step (payload validation, exit 10/8/9, GSM write, leak scan, the ticket's close) uses that
   ticket exactly as the other modes use theirs.
E tests: an operator-terminal run (TTY stdin via a pty, `CLAUDE_GTM_COMPANY` unset, a valid test
marker for `secret_sink_prompt` + the action, no pre-minted ticket) stores the value, runs the leak
scan and exits 0; the same run with no marker → exit 7 `operator_marker_invalid`; with a non-TTY
stdin → exit 7 `not_a_tty`; with `CLAUDE_GTM_COMPANY` naming another slug → exit 13; `serve` with
`CLAUDE_GTM_COMPANY` unset → exit 13; each RED when its check is removed.

**Payload validation (every mode that stores; exit 6 `payload_invalid`).** The connector is
`system_names.connector_system(<the setup script's allowlist system>)` (for `prompt`, whose ticket
has no script: `connector_system` of the action's tier system), and its manifest comes from
`connector_dispatch.load_manifest(R, <connector>)` (HEAD bytes only, §6.1; `ManifestUnavailable` →
exit 6 with its code). The value must parse as one JSON object carrying every
`credential.fields` key (keyed form selected by the target pack's `lead_sink.kind`, §6.1) plus the
`google_sa` route keys (§6.3 "Auth scheme per connector"), each a non-empty string, and for
`google_sa` an `auth_route` of exactly `impersonate` or `key` — the same rules as credential step 5
(§6.3). Any failure → exit 6, stdout `payload_invalid <reason>` (reason: `not_json`,
`missing:<key>`, `bad_auth_route`, `no_keyed_entry`, or the `manifest_*` code), no gcloud call, and
the value is discarded.

**Secret-target refusal (every mode that stores; exit 10 `secret_target_refused`).** Before any
gcloud call the sink calls `connector_dispatch.check_secret_target(R, H, <slug>, <secret name>)`
(§6.3 API block: credential steps 1–3, the one shared helper). `CredentialUnavailable
("connectors_json_unavailable")` → exit 8 (as below). Any other reason — `secret_not_per_company`
(the name is not `gtm-<slug>-…`), `agency_secret_name` (`oauth-google-*`), `agency_gsm_project`,
`phi_denylist_unreadable`, `gsm_project_cross_company` → exit 10, stdout
`secret_target_refused <reason>`, zero gcloud calls. So a OtherCompanyB setup ticket naming
`gtm-othercompany-meta`, an `oauth-google-*` secret or an Agency project can never receive a
captured value.

**GSM write (exact commands; `gsm_project`/`gcloud_account` as returned by `check_secret_target`,
from that company's `connectors.json` at HEAD, §6.3).** `connectors.json` absent or malformed →
exit 8 with **no** gcloud call. Every gcloud call below (and ROTATE's `disable`) runs through
`connectors._run([connectors.gcloud_path(), …])` (§6.5b "Subprocess seam"; the value goes on
`input`, never argv), so the E tests' "fake gcloud" is a `testkit.FakeProc` and a `GTM_TEST=1` run
with no fake starts no process (`test_mode_no_live` → exit 8). Then:
`_run` discards stderr and returns only `(returncode, stdout)` (§6.5b), so the sink never tries to
recognise gcloud's `NOT_FOUND` text; it asks first (DECIDED HERE):
1. `gcloud secrets describe <name> --project=<gsm_project> --account=<gcloud_account> --format=value(name)`.
   rc 0 → the secret exists; go to step 3.
2. Any non-zero rc → create it **once**:
   `gcloud secrets create <name> --project=<gsm_project> --account=<gcloud_account> --replication-policy=automatic`;
   a non-zero rc → exit 8. (A describe that failed for another reason, e.g. a permission error, makes
   `create` fail too, which is exit 8; a create that races another creator fails and is exit 8, and
   the operator re-runs the capture.)
3. `gcloud secrets versions add <name> --data-file=- --project=<gsm_project> --account=<gcloud_account> --format=value(name)`,
   with the value on stdin. The version is the final `/`-separated segment of stdout. A non-zero rc
   or empty stdout → exit 8.
Before its first `connectors.gcloud_path()` call the sink checks `gtm_env.test_mode(os.environ)[0]`
itself (true and no `FakeProc` installed → exit 8 `test_mode_no_live`, zero processes), so the result
never depends on whether gcloud is installed (§6.3 "Test mode first").
Before step 1, the sink refuses (exit 9 `leaked_value_recaptured`, no gcloud call) any value whose
sha256 appears in `S/leaked_secret_hashes.jsonl`. A re-capture therefore counts as rotation only when
the platform issued a new value. After storing, it appends
`{"ts", "company", "ticket_id", "secret_name", "version", "sha256", "length", "needles": [{"sha256",
"length", "rk"}]}` to `S/secret_capture_hashes.jsonl` (`sha256`/`length` of the whole value, used by
the exit-9 refusal and ROTATE step 1; `needles` below). That record holds hashes and lengths, never
the value.

**Scan needles (DECIDED HERE).** A transcript never holds the payload as captured: it holds pieces
of it (one field's value), JSON-escaped once (a string inside a JSON line) or twice (a tool result
that is itself JSON text, inside a JSON line). So the scan never looks for the whole payload. For
each `credential.scan_fields` key (keyed form selected by `pack.lead_sink.kind`) that is present in
the payload, with value `v`, the needles are the **distinct** strings among:
1. `v` itself;
2. its JSON-string-escaped form `json.dumps(v)[1:-1]` and `json.dumps(v, ensure_ascii=False)[1:-1]`;
3. its doubly escaped form `json.dumps(json.dumps(v)[1:-1])[1:-1]`;
4. when `v` contains `-----BEGIN` (a PEM): every base64 body line of `v` of 40 characters or more
   (so a key that was re-wrapped, partly shown or rendered in a snapshot is still found).
Each needle is recorded as `{"sha256": <hex of sha256 of its UTF-8 bytes>, "length": <byte length>,
"rk": <its Rabin–Karp fingerprint>}`, where `rk(b) = (Σ b[i]·257^(n-1-i)) mod (2^31 − 1)` over the
UTF-8 bytes (it reveals nothing that the sha256 of the same bytes does not). A payload with no
present `scan_fields` key records `needles: []` (§6.1) and its scans are no-ops.

**Leak scan (`serve`/`ingest-file`/`prompt`, right after storing; and again by `scan`).** The
**file set** is defined by path, never by file name: for `P = project_dirs.project_dir_name(H)` (the
public spelling, 00_global_paths.md; never the private `harvest_tool_trail._project_dir_name`
alias) and `sid` = the setup ticket's `session_id`, the project dirs are found by the one
enumeration 00_global_paths.md §0.1 "Agency Claude-session transcripts are skipped too (F9)"
prescribes for every `R/projects/` consumer, `secret_sink` scans named among them — **never** by
copying `harvest_tool_trail._matching_project_dirs` (its `iterdir()` then `is_dir()` form violates
that rule): one `os.scandir(R/projects)`; for each entry, **first** drop it when
`project_dirs.is_agency_project_dir(entry.name)` is true, before any `entry.is_dir()`, `stat()` or
`Path` call on it (a skipped entry is never opened, listed or stat'd); then keep it only when
`entry.name == P` or `project_dirs.matches_project_dir_prefix(entry.name, P)` (the shared,
separator-bounded helper, 04_hooks.md; never used for the Agency filter), and only then
`entry.is_dir(follow_symlinks=False)`. For **each** kept dir `D`:
(a) the file `D/<sid>.jsonl`, **plus every regular file under `D/<sid>/`, recursively** — this is
where sub-agent transcripts (`D/<sid>/subagents/agent-<id>.jsonl`, verified on this machine), their
workflow transcripts (`D/<sid>/subagents/workflows/**`) and spilled tool results
(`D/<sid>/tool-results/**`) live, and the `gtm-credential-setup` seat is a sub-agent, so its
`browser_evaluate` result lands there, in a file **not** named `<sid>*`. Siblings are included
because a setup session whose cwd is a subfolder of H lands in a `<P>-…` dir (the
harvest_tool_trail #26 fix); a
sibling that belongs to another home holds no `<sid>` path, so it contributes nothing. And
(b) every file under `H/.playwright-mcp/**` (probe l: `browser_navigate` writes `page-*.yml`
snapshots there). Symlinks are not followed.
**Matching (both passes, one algorithm):** for each distinct needle length `L`, roll the `rk`
fingerprint over every `L`-byte window of each file's bytes; a window whose `rk` equals a needle's
is confirmed by sha256, and a confirmed window is a hit. The first pass computes the needles from
the in-memory value; `scan` reads them from `S/secret_capture_hashes.jsonl` (every record of the
ticket), so the value itself is never re-read or stored. After either pass, it **deletes** every
`H/.playwright-mcp/**` file modified since the setup ticket's `created_at`.

**Second scan (mandatory).** The first pass runs before the transcript holds the `browser_evaluate`
tool result and before any later snapshot. So a setup ticket's close runs `secret_sink.py scan`
(R4: `ticket --close` of a setup ticket runs it **as a subprocess of act.py**, 02_act.md §2.4, and
refuses to close on exit 3 until the ROTATE path below has run; the subprocess form keeps the CLI
exit-3 contract). The WP-K setup prompt carries the same step (R10).

**On a hit (either pass): ROTATE (F20; plan §20.10).**
1. The sink appends the leaked **whole value's** sha256 (the capture record's `sha256`, whichever needle hit) to `S/leaked_secret_hashes.jsonl`
   (`{"ts", "company", "secret_name", "version", "sha256"}`).
2. It disables the leaked version in-process: `gcloud secrets versions disable <version> --secret=<name>
   --project=<gsm_project> --account=<gcloud_account>`.
3. It appends an isolation hit (`source: "secret_sink"`).
4. It prints exactly one line, `ROTATE <name> <version> disabled` or `ROTATE <name> <version> disable_failed`,
   and exits 3. `disable_failed` also writes an urgent `trust` notice (`created_by: secret_sink`).

Disabling a GSM version does **not** revoke the platform token. So the session (WP-K setup prompt)
then acts on the script's `regenerates` flag:
- **`regenerates: true`:** mint a **new** setup ticket for the same action (`ticket --setup`) and
  re-run the capture once. **At most one re-capture per action.** A second hit, or exit 9, stops.
  The platform issued a new token, so the old leaked one is superseded on the platform side as well.
- **`regenerates: false`, or the one re-capture is spent:** do **not** re-run capture (it would read
  the same exposed value, which exit 9 refuses anyway). Write an urgent `trust` notice (push) that
  names the platform's revocation or regeneration step. Add that step to the batched **sign-in**
  card, the sanctioned card type that fits (plan §20.11). No new card type is opened. The account
  stays without a live credential (`credential_unavailable`, fail closed) until the operator has
  regenerated the token and a fresh capture stores a value not in the leaked list.

Tests (E):
- A fixture transcript containing the captured value → exit 3, `ROTATE <name> <v> disabled`. The
  fake gcloud records a `disable` for the added version, and an isolation hit and a leaked-hash line
  are appended.
- A fixture secret placed **only** in `<P>/<sid>/subagents/agent-x.jsonl` (no file named `<sid>*`
  holds it) → `scan` exit 3 ROTATE; RED when only `<sid>*`-named files are scanned. The same for a
  file under `<P>-sub/<sid>/tool-results/`.
- A `key`-route `google_sa` payload whose `private_key` appears in a fixture transcript only in its
  JSON-escaped form (`\n` for each newline), and another only doubly escaped → exit 3 ROTATE each;
  one where only a single PEM body line appears → exit 3; each RED under whole-payload hashing
  (the pre-fix algorithm), which can never match.
- A `meta_bearer` payload whose `access_token` appears inside a longer run of token characters in
  the transcript → exit 3 (windows are found at any offset).
- `check_secret_target` refusals: a OtherCompanyB ticket whose secret name is `gtm-othercompany-meta`, an
  `oauth-google-x` name, and a `connectors.json` naming an `agency_gsm_projects` project → exit 10
  `secret_target_refused` each, with **zero** gcloud calls; RED when the sink skips the helper.
- A value that is not JSON, or lacks a `credential.fields` key, or carries `auth_route: "user"` →
  exit 6 `payload_invalid`, zero gcloud calls.
- Re-capturing an identical leaked value → exit 9, no gcloud call. A regenerated (different) value is
  stored clean.
- A transcript line appended after `serve` exits is caught by `scan` (exit 3).
- An Agency-named project dir (`is_agency_project_dir` true, e.g. `P_A` and `P_A + "-wt"`) holding
  `<sid>.jsonl` with the needle → `scan` exits 0 (no ROTATE), and an `os.scandir` spy wrapping the
  `DirEntry` objects records no `is_dir()`/`stat()` call and no open of that entry; RED when the
  Agency filter is applied after `is_dir()` or omitted.
- The fake gcloud asserts `--project` and `--account` on `describe`, `add`, `create`, `access` and `disable`.
- `connectors.json` absent → exit 8 with zero gcloud calls.
- `describe` answering rc 1 (FakeProc `on([gcloud, "secrets", "describe"], rc=1)`) → exactly one
  `create`, then one `versions add`; `describe` rc 0 → no `create`, one `versions add`; `create` rc 1 →
  exit 8 with no `versions add`. Each RED when the sink adds before describing or creates twice.
- A ticket for another company, or a closed ticket → exit 7.

**`serve` request handling and replies (DECIDED HERE).** `serve` accepts exactly one `POST /capture`
(plus any `OPTIONS /capture` preflights, below) and then exits. The POST body must be a JSON object
with exactly the keys `ticket_id`, `secret_name`, `acting_as_label`, `value`; its `ticket_id` must
equal `--ticket` and its `secret_name` must equal `--secret-name` (so page-side script text can never
name a different secret than the ticket authorizes), else 403 `refused:ticket_mismatch`, nothing
stored, exit 7. The reply body is plain text and **never echoes the value** (nor any part of it):

| outcome | HTTP status | body | exit |
|---|---|---|---|
| stored and first leak pass clean | 200 | `stored:<name>:<sha8>` | 0 |
| stored, first leak pass hit (ROTATE) | 200 | `stored:<name>:<sha8>` (the page learns nothing of the scan) | 3 |
| body not a JSON object / wrong key set | 400 | `refused:bad_request` | 6 |
| `ticket_id`/`secret_name` ≠ the CLI's | 403 | `refused:ticket_mismatch` | 7 |
| acting-as mismatch | 403 | `refused:acting_as_mismatch` | 7 |
| payload invalid | 422 | `refused:payload_invalid:<reason>` | 6 |
| secret target refused | 403 | `refused:secret_target_refused:<reason>` | 10 |
| leaked value re-captured | 409 | `refused:leaked_value_recaptured` | 9 |
| GSM write failed / `connectors.json` unavailable | 502 | `refused:gsm_write_failed` | 8 |
| origin not a `target_hosts` origin | 403 | `refused:origin` (nothing read) | — (keeps waiting) |
| any other path or method | 404 | `refused:not_found` | — (keeps waiting) |

`--timeout 600` (seconds, default 600) expiring with no accepted POST → exit 7 `ticket_expired`
(stdout), nothing stored. E tests: a POST whose `secret_name` differs from `--secret-name` → 403
`refused:ticket_mismatch`, exit 7, zero gcloud calls (RED when the match is removed); each other
refusal row → its status and body, and a spy asserts the value's bytes appear in no reply body; a
`serve --timeout 1` with no POST → exit 7 `ticket_expired`.

**Exit codes (I15), every `secret_sink.py` mode:** 0 stored and clean (`scan`: clean); 1 internal;
2 usage; 3 `ROTATE`; 6 `payload_invalid` (payload fails the manifest rules, or the manifest is
unavailable, or `serve`'s body is malformed); 7 ticket invalid (class, company, secret name, status,
expiry, `serve`'s `ticket_mismatch`/`acting_as_mismatch`, or `serve`'s `--timeout` expiring with no
capture: `ticket_expired`); 8 GSM write
failed or `connectors.json` unavailable; 9 `leaked_value_recaptured`; 10 `secret_target_refused`
(`check_secret_target`, §6.3); 12 lock busy, or (`serve`) the port bind failed; 13 company. Order
for a storing mode: 13 → 12 (lock) → 7 (ticket, incl. `serve`'s `script_id` check; for `prompt`, its
admission steps 2–5) → `serve` binds its port (failure 12) and receives the value (a malformed body
→ 6 `bad_request`) → 7 (`ticket_mismatch`, then `acting_as_mismatch`; fallback B's `ingest-file`
is not sanctioned, R7, and its sanctioning must define where its file carries the label) → 6 → 10/8 → 9 → GSM write →
leak scan.

**Which script's origins (DECIDED HERE).** `serve` reads `script_id` from the setup ticket file (02_act.md
§2.4 `ticket --setup --script <script_id>` records it) and looks up
`allowlist.json[scripts][script_id].target_hosts`, reading `allowlist.json` from HEAD (`git -C <R> show
HEAD:tools/gtm/setup_scripts/allowlist.json`, as G-A does). A ticket without `script_id`, an unknown
id, or an unreadable allowlist → exit 7; this check is part of ticket validation, so it runs before
the port is bound (exit order above).

**CORS / Private Network Access (UNVERIFIED feasibility → probe first).** The capture JS runs in the
platform page (e.g. `developers.facebook.com`) and POSTs to loopback, which page CSP `connect-src`
and Chrome's Private Network Access preflight may block. **WP-E does not build the POST flow until
probe `l2` (recorded in plan §17 by the coordinator) shows it works on each target platform.** The
sink answers `OPTIONS /capture` with `204` and these headers:
- `Access-Control-Allow-Origin: <origin>`, where `<origin>` = `https://<h>` for the
  `target_hosts[i]` that exactly equals the request's `Origin` header.
- `Access-Control-Allow-Methods: POST`
- `Access-Control-Allow-Headers: content-type`
- `Access-Control-Allow-Private-Network: true`

It adds the same `Allow-Origin` to the POST reply. Any other origin → 403.

**Fallback B (download file; NOT sanctioned until trust-architect reviews it, recorded in plan §17;
R7).** Plan §20.10 names only the operator's no-echo prompt as the fallback, and B puts a plaintext
token on disk where the orchestrating session can Read it. If sanctioned, it is built with all of
these:
- The capture script names the file `gtm-capture-<ticket_id>-<32 hex random nonce>.txt`.
- The session's **next tool call** after the capture is `secret_sink.py ingest-file`, which globs
  `H/.playwright-mcp/gtm-capture-<ticket_id>-*.txt`, requires exactly one match, reads it, writes GSM,
  overwrites the file with zeros, unlinks it, and then runs the leak scan.
- G-A/the path gate denies Read of `**/.playwright-mcp/gtm-capture-*` in GTM scope (R11).

Until B is sanctioned, the only paths are the POST flow and C.

**Fallback C** (always available, including hours after the sign-in card was posted):
`secret_sink.py prompt --company <slug> --action <action_id>` in the operator's own terminal (no-echo
TTY), after he signs the `secret_sink_prompt <action_id>` operator marker with Touch ID
(`operator_ok.sh`); admission as "`prompt` admission" above, then the same payload validation,
secret-target refusal, leaked-hash refusal, GSM write and leak scan. The batched sign-in card and
the WP-K setup prompt list both commands for the operator (requests/06_connectors.md R34).
