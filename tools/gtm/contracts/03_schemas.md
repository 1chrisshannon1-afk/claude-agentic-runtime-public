# GTM Wave-2 interface contracts — §3 Data schemas

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md).

## 3. Data schemas

**Test mode never writes real state (00_global_paths.md §1.1 consequence 3; requests/00_global_paths.md
R22).** Every writer this section defines that does not write through the shared `gtmlib` helpers —
`cycle.py` (§3.12), `autonomy_ladder.py` incl. `promote` (§3.17), `metrics.py` (§3.18),
`perf_report.py` incl. `record-session` (§3.19), `mission_record.py` (§3.19), `transcript_index.py`
(§3.16), `outside_actor.py` (§3.23), `scoreboard.py` and `experiments.py` — calls
`gtm_env.refuse_real_state(ctx.R, ctx.home)` before its first write; `RealStateRefused` maps to exit 3
`test_mode_real_state` in each of their exit-code lists. G test: 00_global_paths.md §1.1 test (d)
(`autonomy_ladder.py promote` under a fake clock leaves the breaker pause).

### 3.1 `actions.jsonl` event line

```json
{"seq": 17, "ts": "2026-09-27T15:04:05Z", "event": "authorized", "action_id": "act_other-company_20260927_0003",
 "actor": "main-session", "session_id": "3f0c…", "run_id": "cyc_other-company_weekly_2026_09_27",
 "data": {"class": "auto", "tier": "T2", "row_id": "gbp.hours_edit"}, "prev_hash": "9b1e…"}
```
- `seq` contiguous from 0; line 0 is `{"seq":0,"event":"genesis","company":"<slug>","ts":…,
  "data":{"schema":"gtm.actions.v1","carry":null,"broken_sha256":null,"card_id":null},"prev_hash":null}`.
- Event names = the Event column of 02_act.md §2.5 plus `genesis, lead_appended, review, owner_listen,
  breaker, approval_request, notice, isolation_hit_ingested, cancel_all_ingested, pause, resume,
  autonomy_level, snapshot_recorded, card_denied, deployed, ceiling_read` (`card_denied`: FID-01;
  `deployed`: FID-04; `ceiling_read`: FID-03, 02_act.md §2.6 rule 5a); every event's `data` shape is the 02_act.md §2.2b table. (Card posting is recorded in
  `ST/cards_posted.jsonl`, not here, so it works under `PAUSE.chain`.)
- `proposed.data` = the full stored proposal (§3.2) + `tier, row_id, class, money, lanes_required,
  after_digest, drafted_by` (the last derived by act.py, never supplied — §3.2 "`drafted_by`"). Leads are stored as `{lead_id, sink_ref, digest}` only — **never PII**.
  **Regulated `hipaa` packs (plan §20.4 "OtherCompany untrusted inputs are not quoted into
  actions.jsonl"; DECIDED HERE — the one rule; it supersedes the refusal form R22 asked 02_act.md
  for, requests/03_schemas.md R78):** "the full stored proposal" means the proposal **after** the
  side-store routing of 02_act.md §2.2b ("HIPAA side-store form"), which this file extends to every
  free-text field a seat writes. **Side-stored** — each stored as `{"digest": "sha256:<hex of the
  text's UTF-8 bytes>", "pointer": ".claude/gtm/state/untrusted/<unt_id>.txt"}` (§3.15 — purged at
  30 days, never backed up), the side-store file holding the text: `rationale`; `undo` (a string,
  or each string leaf of a dict); and the **six free-text keys of `money_brief`** —
  `object_display`, `metrics_summary`, `best_practice_source`, `expected_effect`, `risk`,
  `reversal` — whatever characters they hold (so a OtherCompany `$` card keeps its `$`, `%` and `,`
  figures, plan §20.8 "each with current metrics…"). `money_brief.urgency` is an enum
  (`normal|urgent`), validated as such and stored inline. `money_brief` strings are **never
  refused** for their characters on a hipaa pack; the approver already renders pointer-form
  display text read-only (05_approver.md §5.1 step 1), and §3.7 "Regulated packs" defines the
  display values built from them. **Closed, not side-stored — `why`** (it is an index into the
  plan and the metrics registry, never prose): on a hipaa pack `why.plan_ref` must full-match
  `^(SP-[A-Za-z0-9-]{1,40}|MASTER|PLAN|exp_<ctx.company>_\d{4})( §[0-9]+(\.[0-9]+)*)?$` (a
  strategy-plan id, the master plan, the plan, or one of this company's experiment ids, §3.18,
  optionally followed by one section reference — e.g. `SP-GBP §3`, `exp_othercompany_0002`), and a
  non-null `why.metric_id` must equal the `id` of an entry in this company's `metrics.json`
  (§3.18). **The `SP-` branch is closed against a registry too, exactly as `metric_id` is**
  (the grammar alone admits `SP-Jane-Doe-crown-review §3`): on a hipaa pack an `SP-…` plan_ref's
  plan id (the whole `SP-…` token before any ` §`) must name an existing strategy plan —
  `<plan id>.md` (e.g. `SP-GBP.md`) with that exact name
  (case-sensitive, compared against `os.listdir` of the directory, so a case-insensitive
  filesystem cannot widen it) present as a regular, non-symlink file directly in
  `<home>/<paths.plans_dir>/` (DECIDED (wave1c): the on-disk plans_dir listing, not "present at
  HEAD" — a pack home need not be a git repo, and plans_dir is the tracked, human-authored plan
  class, so the listing is the registry). Any failure — grammar, missing plan file, or
  unregistered `metric_id` → exit 3 **`hipaa_free_text`** (stage 1a, §3.2), no event. So `why`
  holds only a registered plan reference (`MASTER`, `PLAN`, a digit-only experiment id, or an
  existing plan file's id) and a registered metric id — a string such as `"Jane Doe crown"`
  fails the grammar as a `plan_ref`, `"SP-Jane-Doe §3"` fails the plan registry, and either fails
  the registry test as a `metric_id`. Non-regulated packs keep the §3.2 table's plain `why` rule. `untrusted_inputs[].quoted_text`,
  `before.text`, inbox-row `after`, and the `after` of `recipient_required` message rows (template-only,
  §3.2 "HIPAA message rows") follow §3.2/§3.15. Non-regulated packs store every one of these inline.
  P2 tests (A1): (a) a OtherCompany-fixture proposal whose `rationale`, `undo`, `money_brief.risk` and
  `money_brief.metrics_summary` each contain a fixture review sentence (the last also `$1,200` and
  `35%`) is **accepted**, leaves no byte-for-byte copy of that sentence in `actions.jsonl` or in any
  file of the expanded `company.backup_set(slug, pack)`, and the side-store files hold it; RED when
  the routing of any one of those fields is reverted; (b) on the OtherCompany fixture a proposal with
  `why.plan_ref: "Jane Doe crown"` is refused `hipaa_free_text`, one with `why.metric_id` not in the
  fixture `metrics.json` is refused `hipaa_free_text`, one with `why.plan_ref: "SP-Jane-Doe §3"`
  (grammar-valid) and no `SP-Jane-Doe.md` in the fixture `plans_dir` is refused `hipaa_free_text`
  (also refused when only `sp-jane-doe.md` exists), and `plan_ref: "SP-GBP §3"` with the fixture's
  `SP-GBP.md` present and a registered `metric_id` passes; each RED when its clause is removed
  (the `SP-Jane-Doe` case RED when the plan-registry check is removed) (requests/03_schemas.md R78 → 02_act.md
  §2.2b/§2.4).
- **`company.backup_set(slug, pack) -> list[Path]`** (the committed signature, `tools/gtm/company.py`;
  never a no-argument call) returns absolute paths, some of them directories. **"Expanded" (the one
  definition, used by every test in this file):** each returned directory is walked with
  `os.walk(followlinks=False)` and contributes every regular file under it; each returned file path
  contributes itself; a returned path that does not exist contributes nothing. The expanded list is
  the set of those files' absolute paths. **The exclusion lives in `backup_set`'s return value, not
  in this rule (DECIDED HERE; 08_seats_wps.md Appendix C item 5).** The committed `backup_set`
  (company.py) returns the whole `<home>/.claude/gtm/state` directory, so under this rule the
  expanded list holds `ST/untrusted/**` and `ST/lead_fallback*.jsonl`. Appendix C item 5 therefore
  changes `backup_set`'s **return shape**: instead of the `state` directory it returns each direct
  child of `<home>/.claude/gtm/state/` individually (directories and files alike), **except**
  `untrusted/` and every `lead_fallback*.jsonl`, and it adds no filter parameter. **The other
  entries cannot re-admit them (DECIDED (wave1c): refuse at `validate`, on every pack — a
  `paths.*` value naming an ancestor of the state directory would otherwise put `ST/untrusted/`
  back into the expanded list, and the committed `validate_company` refuses only absolute and `..`
  paths):** item 5 also makes `company.py validate_company` refuse any `paths.*` value (every key
  but `mission_records`) whose `os.path.normpath` text (home-relative) is equal to or an ancestor
  of `.claude/gtm/state` (so `""`, `"."`, `".claude"`, `".claude/gtm"`, `".claude/gtm/state"`), or
  equal to or under `.claude/gtm/state/untrusted`, or a `.claude/gtm/state/lead_fallback*.jsonl`
  file — reason `paths.<key> must not contain the GTM state directory or its untrusted store`.
  Descendants of the state directory stay legal (Appendix A's `activity_log_dir`, `scoreboard` and
  `snapshots_dir` live under it). As defense in depth `backup_set` drops (never follows) any
  `paths.*` entry whose `os.path.realpath` is equal to or an ancestor of
  `realpath(<home>/.claude/gtm/state)` or equal to or under its `untrusted/` (so a symlinked
  `data_dir` cannot re-admit it either). Test (coordinator, with item 5): a fixture pack with
  `data_dir: ".claude/gtm"` fails `validate` with that reason, and with `validate` bypassed (the
  pack dict passed straight to `backup_set`) the expanded list still holds `ST/actions.jsonl` and
  not `ST/untrusted/u1.txt` or `ST/lead_fallback.jsonl`; each RED when its guard is removed. This
  rule stays exclusion-free. Every test in this file that asserts a file is absent from the expanded list
  (this section's PHI test and the §3.15 tests) is **gated on item 5**: it is RED against the
  committed `backup_set` until item 5 lands, which is the intended ordering (item 5 lands before
  P1b and before any hipaa pack is registered). Test (coordinator, with item 5): on a fixture home
  with `ST/untrusted/u1.txt`, `ST/lead_fallback.jsonl` and `ST/actions.jsonl`, the expanded list
  holds `actions.jsonl` and neither of the other two (RED when `backup_set` returns the `state`
  directory again).
- The fold (`store.fold(ctx, *, virtual_reconcile=False) -> dict[action_id, dict]`, 02_act.md §2.2b)
  produces the record in §3.3.

### 3.2 Proposal (input to `propose`; §6.2 + §20)

All keys required (null allowed where noted in the field table below). `tier` and `drafted_by`
are never supplied (refused if present, below).

**`drafted_by` (DECIDED HERE; a stated deviation from plan §6.2, which lists `drafted_by {seat,
agent_id}` among the proposal's fields).** The key is **never supplied**: act.py derives it — for
`propose --from-agent <id>`, `{"seat": <that agent's agent_type from its spend row>, "agent_id":
<id>, "verified": true}`; for `propose --file`, `{"seat": "session", "agent_id": "main-session",
"verified": false}` (02_act.md §2.4 `propose`) — and stores it in `proposed.data` (§3.1). A
supplied `drafted_by` key is refused exit 3 **`drafted_by_supplied`** (stage 1a, tested before
`proposal_key_unknown`, like `tier_supplied`), because a drafter-chosen value could claim another
seat's authorship and so satisfy maker-checker (plan §6.5) by assertion. H2 primers written from
plan §6.2 must not emit it (requests/03_schemas.md R79 → 08_seats_wps.md H2). A1 test: a
`gtm-result` proposal carrying `"drafted_by": {"seat": "local-presence-architect", "agent_id":
"a0"}` is refused `drafted_by_supplied` (RED when the key is merely ignored or reaches
`proposal_key_unknown`), and the same proposal without it is stored with the spend-row seat.

```json
{
  "company": "other-company", "brand": "remodeling",
  "system": "gbp", "object_class": "hours", "action": "edit",
  "account_id": "1000000000000000001",
  "target_ref": "locations/1000000000000000001",
  "campaign_state": "n/a",
  "before": {"evidence_ref": ".claude/gtm/state/snapshots/2026-09-27_cyc_other-company_weekly_2026_09_27/gbp_profile.json", "text": null, "value": {"mon": "08:00-16:00"}},
  "after": {"value": {"mon": "08:00-17:00"}},
  "rationale": "Calls cluster 16:00-17:00 (see scoreboard).",
  "why": {"plan_ref": "SP-GBP §3", "metric_id": "gbp_calls_28d"},
  "undo": "restore hours to before.value",
  "spend_delta_monthly": 0,
  "assets": [],
  "untrusted_inputs": [],
  "lead_id": null,
  "recipient": null,
  "money_brief": null,
  "contains_patient_content": false,
  "hipaa_authorization_ref": null
}
```
**Field table (normative; A1 `propose` validates in three steps — 1a, matching + 1b, 2 — and stops
at the first failure: exit 3 with the named code, no event; DECIDED HERE; the complete ordered
list, so the first-failure code a caller sees is fixed).**
**Stage 1a (row-independent; before matching), in this order:** (1) `tier` present →
`tier_supplied`; (2) `drafted_by` present → `drafted_by_supplied` (both **before** the unknown-key
test, so they can fire); (3) a key not in this table → `proposal_key_unknown`; (4) a key absent
from the proposal → `proposal_key_missing` (detail names the key); (5) the table's rows in table
order, each judged **only** on what needs no row: `company`; `brand` (`brand_required` /
`brand_unknown`); `system` (`system_unknown`, §3.4.2 "Unknown systems"); `object_class`/`action`
pattern (`proposal_triple_invalid`); `account_id` (type, emptiness, and the slug-account systems'
`account_id == ctx.company` form); `target_ref` (type/emptiness; nullability is per **system**,
§3.22, so row-independent); `campaign_state`; `before` shape; `after` is an object (else
`after_shape_invalid`) — its keys are 1b's; `rationale`; `why` (shape, and on a hipaa pack the §3.1
grammar and metric-registry test → `hipaa_free_text`); `undo`; `spend_delta_monthly`; `assets`;
`untrusted_inputs`; `lead_id` and `recipient` when **non-null** (shape, `LEAD_ID_RE`, own slug —
`recipient_shape_invalid` / `lead_id_invalid`; their null acceptance is 1b's); `money_brief` type
only (null or an object, else `money_brief_invalid`; its content is stage 2's);
`contains_patient_content`; `hipaa_authorization_ref`. "Nullable" lists the only cases null is
accepted; a null anywhere else → `proposal_null_invalid`. A wrong type or pattern → the code in the
last column.
**Matching** (§3.4.2) then runs on the 1a-valid proposal.
**Stage 1b (row-dependent; after matching), in this order:** (1) `after` top-level keys ⊆ the
matched row's `after_fields` and `after.value` keys ⊆ its `after_value_fields` (`_nomatch`: no key
test) → `after_shape_invalid` (02_act.md §2.8 check 10 re-asserts it at `authorize`); (2) money
value and unit strings — `money_value_invalid` / `money_unit_invalid` ("Money value strings"
below, incl. the `current_value: zero` `"0.00"` rule and `report_only`); (3) the row's typed-key
rules (§3.4.4 Fields/Flags: `asset_type` keys, `api_access_create` scope kinds, `duration_days`,
`area_code`/`number`, `abo` budget keys) → `after_shape_invalid`; (4) the `after.value.lead_id`
rule (§3.2 `recipient`) → `lead_id_invalid`; (5) null `lead_id` on a `lead_id_required` row →
`lead_id_missing`, null `recipient` on a `recipient_required` row → `recipient_missing`
(02_act.md §2.8 check 8 re-asserts both at `authorize`); (6) `id_fields` presence —
`id_field_missing` / `id_field_null` (§3.4.1 `required_ids`/`optional_ids`); (7) `home_data` rule
(1) → `source_ref_invalid`; (8) structured values — `nested_ids_undeclared`, then
`gtm_template_unlisted`, then `nested_path_unlisted` (§3.4.1); (9) on a hipaa pack, the
`recipient_required` message-row template rule ("HIPAA message rows" below) →
`hipaa_inbox_free_text` / `hipaa_template_missing`.
**Stage 2 (after 1b, before any 02_act.md §2.8 check), in this order:** (1)
`boost_post_required` (§3.4.1 `object_scope`); (2) the budget-object guards of "Enable actions"
below — `enable_no_budget_object`, then `enable_amount_required`, then
`paid_object_use_money_row`, then `status_change_use_money_row`; (3) `money_amount_hidden`
("Hidden-amount guard"); (4) `money_brief` — `money_brief_required` / `money_brief_unexpected`
against the **prospective class**, then its shape (the seven keys, six non-empty strings,
`urgency` ∈ `normal|urgent`) → `money_brief_invalid`; (5) the act.py-set bindings —
`content_mismatch` / `ad_content_unreadable` (+CD, §3.4.4 "Enabling ads"), `source_mismatch`
(`home_data`), `patch_mismatch` (`website_static`). The **prospective class** is `never` when the
matched row's class or tier is NEVER; else `money` when the matched row's `money` is true (absence =
true), or `spend_delta_monthly != 0`, or there is no match; else non-money. It never depends on
check 1, so a money-row proposal whose target later fails check 1 still carries its `money_brief`
through stage 2 and is then recorded as a `refused` event with class `never` (and its card, when
check 1 cards). 02_act.md §2.4's own `propose` refusals (`read_action_not_proposable`,
`use_lead_append`, `unverified_drafter`, the path and hipaa gates) keep the places 02 gives them;
this list orders 03's codes. **`brand_mismatch` is not a stage refusal:** it is a check-1 result
(below, "Brand binding") recorded as a `refused` event with class `never`. A1 test: a proposal that
carries both `tier` and an unknown key is refused `tier_supplied`; one whose `system` is unknown
**and** whose `after` carries an unlisted key is refused `system_unknown` (RED when the after-key
test moves into 1a); one on a `lead_id_required` row with a null `lead_id` **and** an empty
`money_brief` object is refused `lead_id_missing` (RED when money_brief is judged first).

| Key | Type / rule | Nullable | Refusal on violation |
|---|---|---|---|
| `company` | slug; equals the ctx company | never | `proposal_company_mismatch` (exit 3, stage 1 — a distinct code from 02_act.md §2.3's exit-13 `company_mismatch`, which is the id-argument / `--company` dispatch check; DECIDED HERE so one `error.code` never carries two exit codes) |
| `brand` | a `brands[].id` of this pack | only when the pack has exactly one brand (see "Brand binding" below) | `brand_required` / `brand_unknown` (stage 1); `brand_mismatch` is a check-1 `refused` event, not an exit 3 |
| `system` | a `CANONICAL_SYSTEMS` member (§3.22) | never | `system_unknown` |
| `object_class`, `action` | non-empty `^[a-z0-9_]+$`; with `system` the triple matched in §3.4.2 | never | `proposal_triple_invalid` |
| `account_id` | non-empty string, stored in the §3.22 per-system normalized form (e.g. Ads ids digits only). **Which value (DECIDED HERE):** the normalized form of the pack `accounts[].account_id` of the account the action runs under, whatever form the pack stores for that system — so for OtherCompanyB a `google_ads` action carries `1002003000` (pack `100-200-3000`), and a `ga4` or `gtm` action carries the pack's `G-…` / `GTM-…` value unchanged; the platform ids the `target_ref` grammar yields are matched through `account_keys` (02_act.md §2.8 check 1(c)), never by putting them in `account_id`. Exceptions: `gtm_ai` (`opus`/`sonnet`), `website_static` (a brand domain), and the slug-account systems `vendor`, `domain_registrar`, `stock_media`, `paid_api` (the pack slug, §3.4.4 "Purchase rows") | never | `account_id_invalid` |
| `target_ref` | non-empty string: a form the §3.22 `target_ref` grammar accepts for the system (e.g. `customers/<cid>/campaigns/<id>`, `locations/<id>`, a listing URL) — any other string yields no ids and fails 02_act.md §2.8 check 1(c) (class `never`, card) — or exactly `repo:<toplevel>` for `website_static` | only for systems that grammar marks `target_ref: null ok` (`gtm_ai`, `crm`, `email`, `sms`, and the money-only systems) | `target_ref_invalid` (type/emptiness only) |
| `campaign_state` | `paused` \| `live` \| `n/a` | never | `campaign_state_invalid` |
| `before` | object with exactly the keys `evidence_ref`, `text`, `value` | never (each sub-key nullable) | `before_shape_invalid` |
| `after` | object; shape per the matched row (below, §3.4.4) | never | `after_shape_invalid` / check 10 |
| `rationale` | non-empty string ≤ 2000 chars | never | `rationale_invalid` |
| `why` | object `{"plan_ref": str, "metric_id": str \| null}`, `plan_ref` a string; on a `regulated ∋ hipaa` pack the §3.1 closed grammar for `plan_ref` and a registered `metrics.json` id for a non-null `metric_id` | `metric_id` only | `why_invalid` / `hipaa_free_text` (stage 1a) |
| `undo` | non-empty string, or an object of strings | never | `undo_invalid` |
| `spend_delta_monthly` | number (int or float, finite) | never | `spend_delta_invalid` |
| `assets` | list (possibly empty) of the `assets[]` shape below | never | `asset_shape_invalid` |
| `untrusted_inputs` | list (possibly empty) | never | `untrusted_shape_invalid` |
| `lead_id` | lead id string matching `system_names.LEAD_ID_RE` (§3.14) whose `slug` group equals the ctx company | when the row has no `lead_id_required` | `lead_id_invalid` (stage 1: pattern or slug); `lead_id_missing` (check 8) |
| `recipient` | the shape below; its `lead_id` obeys the same `LEAD_ID_RE` + slug rule as the `lead_id` row | when the row has no `recipient_required` | `recipient_shape_invalid` / `lead_id_invalid` (stage 1); `recipient_missing` (check 8) |
| `money_brief` | the shape below | exactly when the stage-2 prospective class is not `money` | `money_brief_invalid` (1a: not null or an object; stage 2: key set, empty string, `urgency` enum); `money_brief_required` / `money_brief_unexpected` (stage 2) |
| `contains_patient_content` | bool | never | `patient_flag_invalid` |
| `hipaa_authorization_ref` | non-empty string | yes | `hipaa_ref_invalid` |

**Money value strings (DECIDED HERE; the §3.7 rule applied at propose).** Every
`after.new_absolute_value` and `before.value.current_absolute_value` is a **string** matching
`^(0|[1-9]\d*)\.\d{2}$` — never a number — else `money_value_invalid`. `after.unit` ∈ the closed
enum **`USD/day | USD/week | USD/month | USD/once | USD/lead`** (the 06_connectors.md §6.2 period →
unit list; `USD/once` = a lifetime/total budget or a one-time purchase, `USD/lead` = a pay-per-lead
cap), else `money_unit_invalid`. **One exception — the signed report-only AI-spend form
(requests/07_notices_schedules.md R34; 05_approver.md §5.5 3b null case (iv)):** on
`gtm_ai.weekly_cap_edit` only, `after.new_absolute_value: null` with `after.unit: "report_only"`
is valid (the operator signs "no cap, report only"); `"report_only"` on any other row, or with a
non-null value, → `money_unit_invalid`. A signed `"0.00"` `USD/week` is a **zero** cap, never
report-only (05_approver.md §5.1 "ZERO CAP"; requests/07_notices_schedules.md R32/R33).

**Brand binding (DECIDED HERE; plan §6.4 "a PAUSE file beats any standing approval").** When the
pack declares more than one brand, `brand` is required non-null (`brand_required`, stage 1). Check 1
then additionally refuses `brand_mismatch` — a `refused` event, class `never`, **no card** (the
value is the pack's own, so a card would ask the operator to add nothing) — unless `account_id`
equals an `accounts[]` entry whose `brand` equals the proposal's `brand`, **or** `target_ref`'s
host is equal to, or a subdomain of, one of that brand's `domains`. Both comparisons normalize:
`account_id` and every `accounts[].account_id` go through `system_names.normalize_account_id(<the
action's tier system>, …)` (§3.22) before equality, and hosts are lowercased. When 02_act.md §2.8
check 1(a) fails **only** because an entry with the same normalized system and account id exists
under a different brand, check 1 reports `brand_mismatch` instead of `unlisted_target` (and does
not card); any other (a) failure stays `unlisted_target` with its card (requests/03_schemas.md
R34). **No company-wide accounts on multi-brand packs (DECIDED HERE; resolves the
company_schema.json disagreement):** on a pack with more than one brand every `accounts[]` entry
carries a `brand` that references a `brands[].id`; an account both brands use (e.g. one Meta ad
account) is listed once per brand, with the same `account_id`. On a single-brand pack `brand` is
optional and an entry without it means the one brand. `company.py validate` enforces both
(requests/03_schemas.md R35 against 08_seats_wps.md Appendix C). This matches 02_act.md §2.8 check
1(a) ("an entry with no `brand` matches only an action with none"), and `pauses.blocking` then
covers a shared account from either brand's pause (§3.10). P2 tests (A1): on the OtherCompanyB
fixture, a remodeling-site `website_wordpress.page_edit` proposed with `brand: null` is refused
`brand_required`, and with `brand: "restoration"` is refused `brand_mismatch`; on the committed
OtherCompanyB pack fixture (`tests/test_other-company_pack_fixture.py`), a remodeling
`google_ads.campaign_budget_edit` whose `account_id` is the fixture's dashed Ads id with the dashes
stripped passes brand binding and check 1(a), and a `ga4.key_event_edit` whose `account_id` is the
fixture's remodeling `ga4` `account_id` (a `G-` measurement id) binds to `remodeling`; each goes RED when its clause (or the normalization) is reverted.

- `campaign_state`: `paused | live | n/a`.
- `before.evidence_ref`: **home-relative** path (e.g. a path printed by `act.py snapshot` or
  `read-run`, under `paths.snapshots_dir` — or, for a hipaa inbox-class snapshot, the
  `.claude/gtm/state/untrusted/<unt_id>.json` pointer, 02_act.md §2.4), or null. Every file reference in actions, notices
  and results (evidence, untrusted pointers, brief paths) is home-relative.
- `after` shapes: text → `{"text": "..."}` (+ optional `"caption"`); structured → `{"value": {...}}`;
  money → `{"new_absolute_value": "45.00", "unit": "USD/day"}` with `before.value.current_absolute_value`.
  **Enable actions (FID-03; plan §20.13 "a paused campaign's budget is committed only at enable";
  DECIDED HERE; aligned with 05_approver.md §5.5 3b "Enable binding").** **Decided by effect, never by
  verb alone.** The rule below applies to (i) every row with `commits_on_enable: true` (§3.4.1) and
  (ii) every **`_nomatch`** action on a **budget object** whose `action`, split into tokens on `_`
  (casefolded), contains an **enable token** ∈ {`enable`, `enabled`, `resume`, `unpause`,
  `activate`, `reactivate`, `start`, `restart`, `launch`, `unarchive`, `on`} — together, the
  **enable actions** (never a row whose `resulting_status` ∈ {`paused`, `removed`}, §3.4.1: such a row can never
  carry `commits_on_enable: true` and is never `_nomatch`, so a stop is never enable-bound — R84, wave1e),
  decided by the one predicate `tiers.is_enable_action(ctx, action, row) -> bool`
  (A1; used by `propose`, `authorize`, §3.7 `display.commits_on_enable`, 02_act.md §2.6 rule 5a and
  05_approver.md §5.5 3b — requests/03_schemas.md R56). **Budget object (the one definition):** the target's **most specific key** is
  `campaign_id`, `campaign_budget_id` or `adset_id`, or the target is account-level only (no
  non-account key, §3.22) on `google_ads`, `meta`, `lsa` or an `L` system (a campaign, campaign
  budget, ad set, paid account or paid listing — the object kinds 06_connectors.md §6.2's
  `committed_ceiling` read serves). **Most specific key (DECIDED HERE):** the **last key** of the
  §3.22 grammar form that `target_ref` matched, in the order that form lists its keys (e.g.
  `customers/<cid>/adGroupAds/<ag>~<ad>` → `ad_id`; `act_<id>/adsets/<id>` → `adset_id`;
  `customers/<cid>` → `customer_id`, account-level); `target_ids` stays an unordered dict and
  `system_names.most_specific_key(tier_system, target_ref) -> str | None` (A1, §3.22) is the one
  implementation. Any other most-specific key (`ad_group_id`, `ad_id`, `post_id`, `media_id`, …)
  or an empty `target_ids` is not a budget object.
  **Every other `_nomatch` proposal on a budget object (DECIDED HERE; the status guard):** refused at
  `propose` exit 3, no event, pointing to the table's enable/pause/budget/remove rows —
  **`paid_object_use_money_row`** when its `action` tokens contain a stop token ∈ {`pause`,
  `paused`, `stop`, `end`, `disable`, `remove`, `delete`, `archive`, `off`} or its `after.value` is
  absent or empty (a verb-only change on a paid object has no reviewable content); and
  **`status_change_use_money_row`** when `after`, at any depth, carries a **status key** — a key whose
  tokens (the money-key tokenizer below) contain any of {`status`, `state`, `enabled`, `active`,
  `paused`, `serving`, `delivery`, `effective`, `configured`, `run`, `running`, `live`, `on`,
  `off`} — or a string leaf whose casefolded value ∈ {`enabled`, `enable`, `active`, `activate`,
  `live`, `on`, `running`, `serving`, `resume`, `resumed`, `unpaused`, `paused`, `pause`,
  `removed`, `archived`, `deleted`}. So a `_nomatch` `campaign`/`activate` is an enable action (ceiling
  read, amount-bound signature, execution re-check), and a `campaign`/`status_edit` or
  `campaign`/`edit` carrying `{"value": {"status": "ENABLED"}}` is refused — neither is ever signed
  as "Approve change (no amount)" over a digest. A `_nomatch` on a budget object that passes both
  (e.g. a Meta campaign objective change, §3.4.4) stays an ordinary `_nomatch` (`$`, digest-signed,
  `nomatch` lanes). P2 tests (A1): a `_nomatch` google_ads `campaign`/`activate` proposal with an
  amount-less `after` is refused `enable_amount_required` (with the `$` shape it takes the ceiling
  read); a `campaign`/`status_edit` `{"value": {"status": "ENABLED"}}` and a `campaign`/`edit`
  `{"value": {"state": "live"}}` are refused `status_change_use_money_row`; a `campaign`/`toggle`
  with an empty `after.value` is refused `paid_object_use_money_row`; a Meta `campaign`/`objective_edit`
  `{"value": {"objective": "OUTCOME_LEADS"}}` stays `_nomatch` `money`; each goes RED when the guard
  is reverted to the verb list {`enable`, `resume`, `unpause`}.
  A `_nomatch` action with an enable token whose most specific key is a **known within-ceiling
  child** — `ad_group_id`, `ad_id`, `keyword`, `asset_id`, `post_id`, `media_id` (the same set as
  05_approver.md §5.5 3b; a keyword or asset addressed through its ad group or ad lands on
  `ad_group_id`/`ad_id`) — is refused at `propose` exit 3 **`enable_no_budget_object`** (no event):
  re-enabling such an object is within the ceiling its campaign already commits, and goes through
  the auto rows `google_ads.{ad,ad_group,keyword}_enable` and `meta.ad_enable` (§3.4.4), never
  through `_nomatch` (whose ceiling read would refuse `ceiling_unreadable` forever). **Every other
  non-budget `_nomatch` enable** (empty `target_ids`, or a most specific key in neither the
  budget-object set nor that child set — a paid add-on, a lead-marketplace category on an `L`
  system, an unknown paid feature) is **not** refused: plan §20.6 makes every action with no
  tier-table match a `$` item, so it takes the ordinary amount-bearing `_nomatch` `$` path, or with
  no amount §3.7 null case (i) (requests/05_approver.md R56). **Parent whose budget lives in its
  children (DECIDED HERE):** for a Meta ABO campaign (ad-set budgets; the campaign has no budget of
  its own) the committed ceiling of `meta.campaign_enable` is the **sum of the configured budgets
  of its ad sets whose own configured `status` is active** — all of one `unit` (else
  `enable_value_mismatch`, exit 3, no approval request; the operator enables per ad set instead);
  zero such ad sets sum to `"0.00"` (the enable commits nothing today; each later `meta.adset_enable`
  is its own `$` action), compared like any other value. The connector read returns that sum with `"budget_owner": "adsets:<id>,<id>,…"` (sorted)
  and the enable before-check compares the same sum (requests/03_schemas.md R36 → 06_connectors.md
  §6.2). A CBO campaign's ceiling is its own budget; a CBO ad set's is its parent campaign's
  (06_connectors.md §6.2, unchanged). P2/L tests: an ABO `meta.campaign_enable` whose two active
  ad sets carry `20.00` and `25.00` USD/day reads and signs `45.00` (RED when the read raises
  `no_budget_object`), and one whose active ad sets mix USD/day and USD/once is refused
  `enable_value_mismatch`; a `google_ads.keyword_enable` of a keyword an agent paused computes
  `auto` with no approval request, and a `_nomatch` `google_ads` `keyword`/`resume` proposal whose
  `target_ref` is `customers/<cid>/adGroups/<id>` is refused `enable_no_budget_object` (RED when the
  budget-object clause is removed); a `_nomatch` `enable` on an `L` system whose target carries only a
  `category_id` reaches `awaiting_approval` (RED when the refusal is widened back to every non-budget
  enable). Table rows whose action splits to `enable` but carry
  no pre-configured ceiling (`google_ads.auto_apply_enable`, `amount_required: false`;
  `paid_api.usage_enable`, `current_value: zero`) are **not** enable actions in this sense — they
  are governed by their own flags (05_approver.md §5.5 3b, 06_connectors.md §6.2 and 02_act.md
  §2.6 rule 5a / §2.8 check 8 use this scope). For an enable action the money shape is the object's **configured
  committed ceiling**, never a new value — `after.new_absolute_value`/`after.unit` = the budget, cap
  or pay-per-lead ceiling the not-yet-enabled object already carries and its period (period →
  `unit` per 06_connectors.md §6.2); an amount-less enable action is refused
  `enable_amount_required` (exit 3) at `propose` and `authorize`. **Fresh read (02_act.md §2.6
  rule 5a is the procedure; this is its data contract):** while no approval request exists for the
  action, `authorize` reads the configured ceiling — **API** accounts through the connector read op
  `committed_ceiling` (06_connectors.md §6.2); **browser** accounts from the snapshot at
  `before.evidence_ref`, admitted only when it is a snapshot named `committed_ceiling` recorded by
  `act.py snapshot` in a `snapshot_recorded` event of this company's chain whose `run_id` equals the
  current run and whose `ts` (never the file mtime) is ≤ 24 h old, for this action's `account_id`
  and object (**the snapshot contract below**) — and appends a `ceiling_read` event; the fold (§3.3) overwrites
  `before.value.current_absolute_value` and sets `before.value.unit` from the latest one, so a
  proposer's own figure is never shown or signed. No qualifying source, a read error or a currency
  other than `USD` → exit 3 `ceiling_unreadable` (no event, no approval request; retryable). A read
  value or unit that differs from `after.new_absolute_value`/`after.unit` → exit 3
  `enable_value_mismatch` (no approval request). So the approval display (§3.7 `current_value`) and
  the signed amount are the amount the enable commits. Execution re-reads it immediately before
  enabling and fails `before_mismatch` with no write on any difference (06_connectors.md §6.2 API
  re-check, §6.4 ceiling before-check, 05_approver.md §5.5 3b). For browser rows the mechanical
  binding is the API read-back that `ticket --write` copies onto the write ticket and G-A rule 9d
  checks at the enable click (§3.6 `budget_readback`; a `commits_on_enable` system with no API
  `committed_ceiling` read refuses the browser ticket `enable_not_agent_executable`, 04_hooks.md
  §4.1; requests/04_hooks.md R33); the runbook before-check stays as the second check. Changing the
  amount is a separate budget-edit `$` action first.
  **`committed_ceiling` snapshot contract (DECIDED HERE; browser accounts).** `act.py snapshot`
  records one file per object at `<paths.snapshots_dir>/<run dir>/<system>_committed_ceiling_<object
  key>.json`, where `<object key>` = the `target_ids` pairs of the object (§3.22) other than the
  account-level keys, as `<key>-<value>` joined by `_` in sorted key order (e.g.
  `google_ads_committed_ceiling_campaign_id-20000000001.json`); an account-level object (an lsa or
  listing paid account) uses `account`. The JSON keys are exactly `{"account_id", "target_ids",
  "new_absolute_value", "unit", "currency", "status", "budget_owner", "read_at"}` — `account_id` in
  the §3.22 normalized form, `target_ids` the full dict (account-level keys included),
  `new_absolute_value`/`unit` per §3.2 money strings, `currency` (must be `USD`), `status` ∈
  `paused|live|removed`, `budget_owner` (null, `campaign:<id>` or `adsets:<ids>`, above), `read_at`
  UTC. `authorize` admits the snapshot only when its `account_id` equals the action's normalized
  `account_id` **and** its `target_ids` equals `system_names.target_ids(system, target_ref)`
  exactly; the file name alone never admits it. Two enables in one run therefore read two files.
  `NON_INBOX_SNAPSHOTS` (§3.22) matches the name by its `committed_ceiling` stem. A1 test: two
  `committed_ceiling` snapshots for two campaigns in one run each admit only their own enable, and a
  snapshot whose `target_ids` names the other campaign is refused `ceiling_unreadable`
  (requests/03_schemas.md R37 → 02_act.md §2.4 `snapshot`).
  **Paused creates (DECIDED HERE; plan §20.13 "creating a paused campaign with a budget stays T1
  (money: false)", "a paused campaign's budget is committed only at enable").** Every create row
  whose object can carry a budget or deliver paid traffic — `google_ads.campaign_create`,
  `meta.campaign_create` and `meta.adset_create` — **always** creates the object with status
  **PAUSED** (ads and assets created under a campaign keep the platform default: the paused
  campaign or ad set above them is what stops delivery). The status is a constant of the row, not an `after`
  field and not proposer-settable: the connector's `apply` sends it on the create call, and the
  runbook's `writes[<row>]` carries a mandatory `set_status_paused` step before the save plus a
  post-save status read (the runbook validator refuses an entry without both,
  `create_status_unpinned`; requests/03_schemas.md R38 → 06_connectors.md §6.4/§6.4b). **Browser
path — detect-after until proven (DECIDED HERE; ruling [122] / plan §20.6 "every budget is the
operator's signature").** On the API path the PAUSED status travels **in** the create call, so no
serving state ever exists: prevent-before. On the browser path the `set_status_paused` runbook step
is prevent-before **only if** the platform's UI lets a new campaign or ad set be saved paused
before it enters any serving state; that is **UNVERIFIED** for every platform (06_connectors.md
§6.2 marks the platform default UNVERIFIED too). If a UI publishes live first, an unsigned
`budget_amount` spends until `verify_read` sees `live` and the operator signs a pause — a
detect-after control. So: **P0 probe `paused_create_ui` (per system; requests/03_schemas.md R80 →
08_seats_wps.md P0 list):** on a test object in the company's own account, the UI's create flow is
driven to save with status paused, and the probe records whether any serving/"eligible"/"active"
state was shown or read back at any point before the paused status held; it passes only when none
was. **Until the probe passes for a system**, `ticket --write` refuses every row in
**`connectors.PAUSED_CREATE_ROWS`** (= `google_ads.campaign_create`, `meta.campaign_create`,
`meta.adset_create`) on that system with exit 3 **`create_not_agent_executable`** (no ticket, no
event; the action stays `authorized`): the create goes through the API connector or the operator
makes it (`record-external --kind owner_executed`). The pass is admitted only as a reviewed runbook
field `writes[<row>].paused_create_probe: "<plan §17 probe record id>"`; the runbook validator
refuses the field on any other row, and `ticket --write` treats a missing or empty field as "not
passed" (requests/03_schemas.md R80 → 02_act.md §2.4 `ticket`, 06_connectors.md §6.4b). A2 tests: a
browser `google_ads.campaign_create` mint on a system whose runbook lacks `paused_create_probe` is
refused `create_not_agent_executable` with no ticket file (RED when the refusal is removed), and
the same mint with the field present proceeds to the ordinary checks; an API-executed create is
unaffected. On these
  rows `campaign_state: "paused"` means **"will be created paused"**, and 02_act.md §2.8 check 11 is
  met by that fixed status — for a create row there is no campaign to re-read, so check 11 neither
  re-reads nor fails on absence (requests/03_schemas.md R45 → 02_act.md §2.8 check 11/§2.9; for `meta.adset_create`, whose `cs` names the **parent**
  campaign, check 11 re-reads that parent as for any other `cs` row; the ad set itself is created
  paused whatever the parent's state). `verify_read` must
  observe the created object's status as `paused`; a created object read back as `live` (or any
  status other than `paused`) **fails verify**: `verify_read` returns `ok: false` with reason
  **`created_not_paused`** (the exact code 02_act.md §2.9 and 06_connectors.md §6.2 key on,
  requests/03_schemas.md R45/R38), act.py appends `verify_failed`, a breaker `PAUSE.<system>` written
  at once (not after two failures — money may already be committing), and an `urgent`
  `runaway_spend` notice (push) naming the object and asking the operator to pause it; the agent
  then proposes the matching `*_pause` money row with `urgency: urgent`. **That stop can proceed
  under the breaker pause (DECIDED HERE; the §3.10 "stop-row exemption"):** a breaker-written
  `PAUSE.<system>` (`created_by: "breaker"`, `ruling_ref: null`) does not block a **stop action** of
  that system — a matched §3.4.4 `class: money` row with `lanes_key: none` whose
  `after.new_absolute_value` is `"0.00"`, or is `Decimal`-lower than `before.value.current_absolute_value`
  (the proposer's figure, bound at execution by the before re-check), and whose
  `money_brief.urgency` is `urgent`, never an enable action or a `current_value: zero` row (§3.10) — at `authorize`, `ticket --write`, `execute`, G-A rule 6b or
  `run-holds`, because a signed stop moves in the same direction as the pause. Owner, migration,
  operator, act, skill-requested and ruled pauses (any non-null `ruling_ref` or `lift_card`), `PAUSE`,
  `DISABLED`, `PAUSE.trust` and `PAUSE.chain` still block it; the stop still needs the operator's
  Touch ID signature (it is `money`). P2/L tests: a fake Google
  Ads API (and a fake browser) whose create would leave the campaign ENABLED — the connector call
  carries status PAUSED, and a fake that ignores it and reports ENABLED fails verify with the
  breaker pause and the `runaway_spend` notice; with that breaker pause present, the urgent
  `google_ads.campaign_pause` (`"0.00"`) for the object is authorized into an approval request and,
  once signed, executes, while a `google_ads.campaign_budget_edit` that **raises** the budget and a
  non-urgent `"0.00"` pause are refused exit 5, and the same urgent pause under an owner-carried
  `PAUSE.google_ads` (`created_by: "migration"`) is refused exit 5 (RED when the exemption is
  removed, or widened to non-breaker pauses); a runbook `writes["google_ads.campaign_create"]`
  without the `set_status_paused` step is refused by the validator; each goes RED when the
  forced-PAUSED clause is removed (requests/03_schemas.md R57 → 02_act.md `pauses.blocking`,
  04_hooks.md §4.1 rule 6b).
  **Current value of other money actions (DECIDED HERE).** For a row whose `current_value` flag
  (§3.4.1) is `zero` (nothing is committed before this action — a purchase, subscription, trial,
  registration, boost or usage start), `propose` requires
  `before.value.current_absolute_value == "0.00"` (else `money_value_invalid`). For every other
  amount-carrying money action that is not an enable action, the value is the proposer's figure:
  the approver shows it as `current_value`, and it is bound at execution, where the connector
  `before` re-check (06_connectors.md §6.2) and the runbook before-check (06_connectors.md §6.4,
  §3.6 `dispatch_brief.before`) fail `before_mismatch` with no write when the platform's value
  differs. The signed amount is always the absolute `after.new_absolute_value` (plan §20.13), never a
  delta, so a wrong current figure cannot commit money the operator did not sign.
- `assets[]`: `{"path": "<home-relative>", "sha256": "<hex>", "class": "real_photo|graphic|ai_image|ai_video|screenshot"}`.
- `untrusted_inputs[]` as supplied: `{"source": "gbp_review:<id>", "quoted_text": "..."}`. Stored form for
  `regulated ∋ hipaa` (§20.4): `{"source", "digest": "sha256:…", "pointer": ".claude/gtm/state/untrusted/<unt_id>.txt"}`
  — `quoted_text` never reaches `actions.jsonl`. Non-regulated packs store `quoted_text` inline.
- `recipient`: null, or `{"kind": "named_person", "lead_id": "...", "channel": "sms|email|dm"}` for
  message rows (drives quiet hours and `sms_consent`). Its `lead_id` (and the top-level `lead_id`)
  must match `LEAD_ID_RE` with `slug == ctx.company`, else `lead_id_invalid` (stage 1), so a
  proposal can never name another company's lead. A1 test: a OtherCompanyB proposal whose `lead_id` is
  `lead_othercompany_20260927_0001` is refused `lead_id_invalid` (RED when the slug test is removed).
  **A lead id inside `after.value` (DECIDED HERE; `crm.status_update`):** `after.value.lead_id` is
  exempt from `id_fields` kinds (§3.4.1) but not from this rule — stage 1 applies the same
  `LEAD_ID_RE` + `slug == ctx.company` test to it, and additionally requires it to equal the
  top-level `lead_id` (the row carries `lead_id_required: true`, so that one is non-null), else
  exit 3 `lead_id_invalid`. A1 tests: a OtherCompanyB `crm.status_update` whose `after.value.lead_id`
  is `lead_othercompany_20260927_0001` (with a valid top-level OtherCompanyB `lead_id`) is refused
  `lead_id_invalid`, and one whose two lead ids are both valid OtherCompanyB ids but differ is refused
  too; each RED when its clause is removed.
- `spend_delta_monthly`: number; change to the committed ceiling (§20.13), not expected delivery.
- `money_brief`: **required (non-null) when the stage-2 prospective class (field table above) is
  `money`** (refused `money_brief_required` otherwise) and must be null for every other prospective
  class (refused `money_brief_unexpected`) — never judged against the effective class, so a
  money-row proposal that later fails check 1 still carries its `money_brief`. Plan §20.8 "each with current metrics, best-practice source, expected
  effect, risk, reversal"; §20.6 urgent runaway-spend cards:
  `{"object_display": "Campaign 'Remodel – Search'", "metrics_summary": "…", "best_practice_source":
  "knowledge/marketing_kb/…md#claim-12", "expected_effect": "…", "risk": "…", "reversal": "…",
  "urgency": "normal|urgent"}` — all seven keys required, strings non-empty. Mapped 1:1 into the
  approval request (§3.7): `object_display → display.object` (shown **only** as the proposer's
  description; the object the signature binds is `display.object_ref`, built by act.py from
  `target_ref` and the verified `id_fields`, §3.7), the next five keys to the same-named `display`
  keys, `urgency → request.urgency` (on a `regulated ∋ hipaa` pack the six free-text keys are
  side-stored, §3.1, and mapped as §3.7 "Regulated packs" states).
- **Hidden-amount guard (DECIDED HERE).** An amount-less `_nomatch` proposal (no
  `after.new_absolute_value`) whose `after` contains, at any depth, a **money key** is refused
  exit 3 `money_amount_hidden`. **Money key (token match, never a substring or regex search):** the
  key is split into tokens on `_`, `-`, `.`, spaces and camelCase boundaries
  (`dailyBudget` → `daily`, `budget`), each token casefolded; the key is a money key when any token
  ∈ {`budget`, `budgets`, `bid`, `bids`, `bidding`, `spend`, `spending`, `amount`, `amounts`,
  `limit`, `limits`, `cap`, `caps`, `cpc`, `cpm`, `cpa`, `cpv`, `roas`, `price`, `cost`}. So
  `daily_budget`, `budget_amount`, `spend_cap` and `maxCpc` are money keys while `caption`,
  `capacity`, `escape` and `forbid` are not. P2 test (A1): a `_nomatch` proposal whose `after`
  carries `caption` passes the guard, and one carrying `daily_budget` (or `dailyBudget`) is refused
  `money_amount_hidden`; each goes RED when the matcher is changed to a substring search. A change that
  names money must be signed over an amount (a table row, or `_nomatch` with the `$` shape), never
  over a digest the operator may not read to the end. The approver renders the full canonical
  `after` (`display.after_full`, §3.7) for every amount-less action. **Status guard (beside this
  one; defined in "Enable actions" above):** on a budget object, a status key or status value
  anywhere in `after` refuses `status_change_use_money_row` — `status` is not a money token, so
  without it an enable written as an edit would pass this guard. Order at `propose` stage 2: the
  budget-object guards of "Enable actions" first, then this money-key guard.
- `contains_patient_content`: bool — true when `after` text or any asset carries a patient's name,
  face, photo, before/after or testimonial (§20.5.2). `hipaa_authorization_ref`: null, or a
  non-empty string naming the documented HIPAA authorization (file path or record id). Check 5
  refuses a regulated public item with `contains_patient_content: true` and no reference. **The
  flag is not trusted on the proposer's word (DECIDED HERE):** the `hipaa` lane checklist
  (`knowledge/marketing_kb/compliance/hipaa-marketing-for-practices.md`, §3.5) carries the item
  `patient_content_confirmed` — the reviewer independently judges whether `after` and every asset
  carry a patient's name, face, photo, before/after or testimonial and records a review line
  `{check: "patient_content_confirmed", result: "pass"|"fail", note: "<true|false>"}`; the lane
  verdict is `fail` when the line is missing or its judged value differs from
  `contains_patient_content` (so a wrong `false` fails the lane and never reaches check 5 as a
  pass). A1 test: a OtherCompany `gbp.post_publish` with `contains_patient_content: false` whose
  `hipaa` review line judges `true` leaves the lane failed and `authorize` refused `review_missing`
  (requests/03_schemas.md R39 → 02_act.md §2.7 lane verdict rule). **The reference is not trusted on
  its word either (DECIDED HERE; plan §20.5.2 "documented authorization"):** when
  `hipaa_authorization_ref` is non-null, the same checklist carries the item
  `authorization_ref_verified` — the reviewer opens the named file or record and confirms it is a
  signed HIPAA authorization covering this patient content and this use, recording `{check:
  "authorization_ref_verified", result: "pass"|"fail", note: "<ref>"}`; the lane verdict is `fail`
  when that line is missing or `fail`, so check 5 never admits a dangling or unrelated reference. A1
  test: a OtherCompany `gbp.post_publish` with `contains_patient_content: true`, a non-null ref and no
  `authorization_ref_verified` line is refused `review_missing` (RED when the line is not required).
- `website_static` rows only (FID-04): `after` = `{"paths": [...], "summary": "...", "patch_sha256":
  "<hex>", "post_image": {"<path>": "<git blob sha>" | null}}`. `paths` = the repo-relative paths
  the change touches (02_act.md §2.8 check 9) and must equal the patch's path set; `summary` is
  reviewer context only. `patch_sha256` (sha256 of the exact unified diff that `propose --patch`
  stores at `ST/patches/<action_id>.patch`) and `post_image` (each touched path's resulting blob;
  null = deletion) are set by act.py (02_act.md §2.4 `propose`; a supplied differing value →
  `patch_mismatch`). Both sit inside `after`, so the 02_act.md §2.7 digest and every lane review bind the
  exact bytes: specialists review the patch, checks 2–4 run over its added lines and assets, and
  `complete --commit` refuses a commit whose content differs (02_act.md §2.4).
- Every `after`/`after.value` key must be in the matched row's `after_fields`/`after_value_fields`
  (02_act.md §2.8 check 10). `action` ∈ {`read`, `export`, `snapshot`} is never a proposal (02_act.md §2.4),
  and neither is `crm.lead_append` (exit 3 `use_lead_append`; leads go through `lead-append`, IMP-24).
- HIPAA inbox replies (`inbox_reply` rows on a `regulated ∋ hipaa` pack): `after = {"text",
  "template_id"}`, `before.text`/`before.value` null (02_act.md §2.8 check 5).
- **HIPAA message rows (DECIDED HERE; plan §20.4/§20.13 — message content to a named prospective
  patient stays out of durable logs):** on a `regulated ∋ hipaa` pack, every `recipient_required`
  row that is not `inbox_reply` — today `{email,sms}.message_send` — is **template-only** exactly
  like an inbox reply: `after.value.template_id` is non-null and names a KB template, `after.text`
  is byte-equal to that template's text, `after.value.subject` (email) is null or byte-equal to the
  template's subject, and `before.text`/`before.value` are null; any other form → exit 3
  `hipaa_template_missing` (template absent or unknown) or `hipaa_inbox_free_text` (text or subject
  not the template) at stage 1b, re-asserted by 02_act.md §2.8 check 5 at `authorize`. So the
  stored `after` is a fixed KB text and nothing is side-stored for these rows (the `list_send` rows
  are `hipaa_prohibited`, and `inbox_reply` rows already follow the rule above). `hipaa_redact`
  admits the proven template `text`/`subject`/`template_id` inline exactly as for `inbox_reply`
  (requests/03_schemas.md R81 → 02_act.md §2.2b `hipaa_redact` (c), `hipaa_inbox_shape`, §2.8
  check 5). A1 byte-search test: on the OtherCompany fixture an `email.message_send` whose
  `after.text` is a follow-up naming a fixture inquiry is refused `hipaa_inbox_free_text` and
  `actions.jsonl` and the expanded `company.backup_set(slug, pack)` hold no copy of it; the same row
  with the fixture template's exact text and `template_id` is admitted; a OtherCompanyB one with free
  text is admitted; each RED when the rule is removed.

### 3.3 Folded action record (`status` output)

```json
{"action_id": "...", "company": "...", "state": "held", "class": "identity", "tier": "T4", "row_id": "gbp.name_edit",
 "money": false, "system": "gbp", "brand": "remodeling", "object_class": "name", "action": "edit",
 "account_id": "...", "target_ref": "...", "campaign_state": "n/a", "before": {}, "after": {},
 "after_digest": "sha256:...", "rationale": "...", "why": {}, "undo": "...", "spend_delta_monthly": 0,
 "assets": [], "untrusted_inputs": [], "recipient": null, "lead_id": null,
 "drafted_by": {"seat": "local-presence-architect", "agent_id": "a1b2c3d4e5f6", "verified": true},
 "run_id": "...", "created_at": "...", "updated_at": "...",
 "lanes_required": ["brand", "claims_voice"],
 "reviews": {"brand": {"verdict": "pass", "reviewer_seat": "brand-architect", "reviewer_agent_id": "...", "after_digest": "...", "ts": "...", "lines": []}},
 "autonomy_level_applied": "autonomous", "would_gate": null,
 "hold": {"notice_id": "ntc_...", "hold_until": "...", "renotified": 0} ,
 "approval": {"request_id": "apr_...", "status": "pending|approved|denied|expired|superseded", "nonce": "...", "urgency": "normal|urgent"},
 "money_brief": null, "contains_patient_content": false, "hipaa_authorization_ref": null,
 "card": {"card_id": "126", "verbatim": "...", "decision": "approve|deny|unclear", "subject": "authorize act_…", "card_written_by_agent": false},
 "deployed": null, "cancel_late": null,
 "ticket_id": null, "execution": {"started_at": null, "finished_at": null, "result": null},
 "executed_by": "agent|owner", "verify": {"status": "pass|fail", "at": "...", "evidence": []},
 "supersedes": null, "superseded_by": null, "revert_of": null, "reverted_by": null,
 "history": [{"seq": 12, "event": "proposed", "ts": "..."}]}
```
`card.decision`/`card.subject` come from the 02_act.md §2.6 decision grammar (FID-01; a `deny`
answer records `card_denied`); `deployed` = `{"commit", "at"}` once a `website_static` action's
`deployed` event is recorded, else null (FID-04; 02_act.md §2.4 `record-external --kind deployed`);
`cancel_late` = `{"who", "ticket_id", "calls_used", "ts"}` from the latest `cancel_late` event (a
cancel marker ingested for a `ticketed` action, §3.11 "Late cancels"), else null.
`would_gate` is null, or `none|hold|card` from the latest `would_execute` event (never set for
`money`, 02_act.md §2.6 rule 6). The latest `ceiling_read` event overwrites
`before.value.current_absolute_value` and sets `before.value.unit` (FID-03, §3.2 "Enable actions").

### 3.4 `tier_table.json` (A1 authors; read by A1, A2, G, K)

Shape example only — **non-normative, and not in file order**; the row set, the row order and every
row's field values are fixed by §3.4.4's complete row list (file order decides matching, §3.4.2).
```json
{"schema": "gtm.tier_table.v1", "version": "2026-09-27",
 "rows": [
  {"id": "any.object_read", "system": "*", "object_class": "*", "action": "read", "when": {},
   "tier": "T0", "class": "auto", "money": false, "public": false, "outward": false, "lanes_key": "none"},
  {"id": "gbp.hours_edit", "system": "gbp", "object_class": "hours", "action": "edit", "when": {},
   "tier": "T2", "class": "auto", "money": false, "public": true, "outward": true, "lanes_key": "listing_text",
   "after_fields": ["value"], "after_value_fields": ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "special_hours"],
   "runbook_write": "gbp.hours_edit", "sms": false, "data_flow": false, "hipaa_prohibited": false},
  {"id": "google_ads.campaign_create", "system": "google_ads", "object_class": "campaign", "action": "create",
   "when": {"campaign_state": ["paused"]}, "tier": "T1", "class": "auto", "money": false, "public": false, "outward": false, "lanes_key": "ads_internal",
   "after_fields": ["value"], "after_value_fields": ["campaign_id", "name", "channel_type", "budget_amount", "bidding_strategy_type", "geo_targets", "language_targets", "network_settings", "start_date", "end_date"],
   "id_fields": {"campaign_id": "in_account"}, "self_id": "campaign_id", "hipaa_on_regulated": true},
  {"id": "google_ads.campaign_enable", "system": "google_ads", "object_class": "campaign", "action": "enable",
   "when": {}, "tier": "T4", "class": "money", "money": true, "public": false, "outward": false, "lanes_key": "none",
   "after_fields": ["new_absolute_value", "unit"], "commits_on_enable": true, "resulting_status": "active"}
 ]}
```

3.4.1 **Row fields.** `id` (`<system>.<object_class>_<action>`, `any.` for `system: "*"`; unique;
`system` exactly the tier-table system name — one per listing platform, never an umbrella; when
rows share `(system, object_class, action)` and differ only in `when`, all but one carry the id
suffix `@<when value>` — the §3.4.4 table names which, e.g. `google_ads.ad_text_edit@paused` beside
the live `google_ads.ad_text_edit` — **DECIDED HERE**);
**row-id split (IMP-02; DECIDED HERE — the one mechanical rule):** for an id
`<system>.<local>[@<when value>]`, `action` = the last `_`-separated token of `<local>` and
`object_class` = everything before it — `gbp.qa_answer_publish` → (`gbp`, `qa_answer`, `publish`),
`lsa.lead_dispute_submit` → (`lsa`, `lead_dispute`, `submit`),
`google_ads.enhanced_conversions_leads_enable` → (`google_ads`, `enhanced_conversions_leads`,
`enable`), `sms_provider.a2p_10dlc_registration_create` → (`sms_provider`,
`a2p_10dlc_registration`, `create`), `email.inquiry_reply_send` → (`email`, `inquiry_reply`,
`send`), `gbp.user_role_edit` → (`gbp`, `user_role`, `edit`), `google_ads.ad_text_edit@paused` →
(`google_ads`, `ad_text`, `edit`). **Exceptions (the complete list):** `any.object_read` → (`*`,
`*`, `read`); `website_wordpress.page_unpublish_with_301` → (`website_wordpress`, `page`,
`unpublish_with_301`). A1 implements the rule once as `tiers.row_triple(row_id) -> (system,
object_class, action)` and its inverse `tiers.row_id(system, object_class, action, when_suffix=None)`;
the tier-table validator (A1, P2 test) refuses any row whose `id` ≠ `tiers.row_id(row.system,
row.object_class, row.action)` (+ `@<when value>` when present), and any non-exception row whose
`action` contains `_`. Drafter primers (H2), runbook `writes[...]` keys and L manifests, and the
02_act.md §2.10 verb map obtain the triple from `tiers.row_triple`, never by a split of their own;
proposals carry the triple (§3.2) and matching (§3.4.2) compares the triple, never the id string;
`system`, `object_class`, `action` (exact strings). **`"*"` is allowed only on the single T0 row
`any.object_read`** (`system: "*", object_class: "*", action: "read"`); the tier-table validator
(A1, P2 test) refuses `"*"` in any other row, so no wildcard row can match an enumerated `$` item
before the no-match fallback. `when` (AND of `{proposal_field: [allowed values]}`; `{}` = always);
`tier` ∈ `T0 T1 T2 T2-review T3 T4 NEVER`; `class` ∈ `auto identity money shared never`; `money`
(bool — **absence = true**, §20.6); `public` (bool; **required on every row**; true for T2, T2-review, every
`*.post_schedule`, the four `google_ads.*@paused` ad/asset rows and the two `meta.*@paused` ad rows — both kinds are not live yet
but go public as soon as the object above them is enabled, so they take the public lane set when
written, FID-09; the enable itself re-checks the content, §3.4.4 "Enabling ads"); **`outward`** (bool; **DECIDED HERE**, plan
§6.5 "gtm-checker is the reviewer of record only for T1/internal items"; **required on every row
— the tier-table validator refuses a row without the key, so no reader ever relies on a default;
a reader that nevertheless meets an absent key treats it as `false`**) — the **lane-audience
flag**, separate from tier: true on every row whose content reaches anyone outside the company —
every `public: true` row, plus the T4 rows that publish or send content: `gbp.name_edit`,
`gbp.address_edit`, `gbp.phone_edit`, `gbp.additional_category_edit`, `gbp.primary_category_edit`,
`L.nap_edit`, `facebook.page_name_edit`, `instagram.profile_name_edit`,
`{facebook,instagram}.dm_reply_send`, `email.inquiry_reply_send`, `{email,sms}.message_send`,
`{email,sms}.list_send` (the rows whose §3.4.4 Flags cell says **`outward`** are the complete
list); false on every
other row, `class: money` rows included (their gate is the signature). `required_lanes` and the
reviewer-seat choice (§3.5; 02_act.md §2.7) take `public_reviewers` when `row.public or
row.outward`. **The `hipaa` lane — the one definition (DECIDED HERE; 02_act.md §2.7 rules 4 and 6
import it and keep no second copy; requests/03_schemas.md R68 supersedes R58's formula):**
```
needs_hipaa = pack.regulated ∋ "hipaa" and (row.public or row.outward
              or effective_data_flow or row.hipaa_on_regulated or content_bound_lanes_added)
effective_data_flow = row.data_flow or (row.data_flow_on_hipaa and pack.regulated ∋ "hipaa")
                      or checks.content_data_flow(action)
```
— the regulated-pack guard covers **every** disjunct, so no CSA or OtherCompanyB action ever takes
the lane; `content_bound_lanes_added` is true when §3.4.4 "Enabling ads" added the `public_post`
set to this action; and 02_act.md §2.7 rule 6 (`measurement`) uses this same `effective_data_flow`
(so `data_flow_on_hipaa` rows get `measurement` on a hipaa pack). A1 implements it once as
`makerchecker.needs_hipaa(ctx, row, action) -> bool` beside `checks.effective_data_flow(ctx, row,
action)`. A1 tests: a OtherCompanyB `gbp.post_publish` and a OtherCompanyB `website_wordpress.page_edit`
adding a booking `<iframe>` do **not** require `hipaa`; the OtherCompany versions do; a OtherCompany
`website_wordpress.plugin_install` requires `hipaa` and `measurement`; each RED when the guard is
moved back onto the last disjunct only. The synthetic `_nomatch` row is `outward: true`.
**`hipaa_on_regulated` (bool; DECIDED HERE; plan §20.5 item 3 "healthcare personalized-ads policies
(Google, Meta) respected")** marks the ad **targeting, audience, keyword and campaign/ad-set create**
rows — `google_ads.campaign_create`, `google_ads.keyword_add`, `google_ads.keyword_enable` (it
re-enables a keyword that an owner or outside actor may have written, and that nothing else
re-reviews; DECIDED HERE), `google_ads.audience_list_create`,
`meta.campaign_create`, `meta.adset_create`, `meta.adset_targeting_edit`,
`facebook.post_boost`, `instagram.post_boost` (§3.4.4 Flags; the
tier-table validator refuses the flag on any other row, and its absence on these) — whose content is neither public
nor a data flow but can target a health condition. On a `regulated ∋ hipaa` pack they take the
`hipaa` lane (internal audience, so from its `internal_reviewers`): **local-presence-architect**,
or **trust-architect** when `after.value` names a list audience (any `custom_audiences`,
`excluded_custom_audiences` or `exclusions.custom_audiences` path of §3.4.1 `nested_id_paths`, or
the row is `google_ads.audience_list_create`). The hipaa checklist carries the item
`healthcare_ads_policy` — the reviewer confirms the keywords, interests, audiences and targeting
comply with Google Ads' "Personalized advertising — health in personalized advertising" policy and
Meta's restrictions on health-related targeting (special ad categories / sensitive health
interests), citing the policy entries in
`knowledge/marketing_kb/compliance/hipaa-marketing-for-practices.md` (UNVERIFIED whether that file
carries them today — it must before P2; requests/03_schemas.md R58), and records `{check:
"healthcare_ads_policy", result, note}`; missing or `fail` → lane `fail`. P2 test (A1): a OtherCompany
`meta.adset_targeting_edit` requires `hipaa` reviewed by local-presence-architect, and one whose
`targeting.custom_audiences` is non-empty requires trust-architect; a OtherCompanyB one does not
require `hipaa`; each goes RED when the flag clause is removed. **Enables on a hipaa pack
(DECIDED HERE):** the keyword, audience and targeting state an enable re-activates is covered too —
on a `regulated ∋ hipaa` pack the §3.4.4 "Enabling ads" content set of `google_ads.ad_group_enable`,
`google_ads.campaign_enable`, `meta.adset_enable` and `meta.campaign_enable` also holds their
**targeting items** (§3.4.4 "Targeting items on hipaa packs"), and a targeting item that is not
content-bound adds the `hipaa` lane (with the `healthcare_ads_policy` line, reviewer chosen as
above), while `google_ads.keyword_enable` carries `hipaa_on_regulated` itself. P2 tests (A1): a
OtherCompany `google_ads.keyword_enable` of a keyword whose last change is an `outside:unknown`
activity-log entry requires the `hipaa` lane reviewed by local-presence-architect; a OtherCompany
`google_ads.campaign_enable` whose campaign serves one GTM-verified ad and one outside-added
keyword requires `hipaa` (and not `public_post`, since every ad is content-bound); a OtherCompanyB
campaign enable with the same keyword requires neither; each RED when its clause is removed. The tier-table
validator (A1, P2 test) refuses a `public: true` row with `outward` false and any listed row
without `outward: true`; `lanes_key` (key into `review_lanes.json`); optional `runbook_write`,
`hold_minutes` (int; absent = 1440; 30 for inbound-inquiry replies), `sms`, `data_flow`
(tracking/pixel/form/call-recording/chat/booking — hipaa reviewer = trust-architect; a **static**
row flag, widened per action by content and pack: **effective `data_flow`** = `row.data_flow or
(row.data_flow_on_hipaa and pack.regulated ∋ "hipaa") or checks.content_data_flow(action)` —
`data_flow_on_hipaa` (bool, DECIDED HERE) marks rows whose flow is invisible in their fields (a
WordPress plugin/theme install or update names only a slug), so on a hipaa pack they always take
the `measurement` + `hipaa` lanes with trust-architect as `hipaa` reviewer (A1, DECIDED HERE; plan §20.5 "any tracking, pixel,
conversion-upload, form, call-recording, chat or booking-widget change"), where
`content_data_flow` is true when any string anywhere in `after` — or, for `website_static`, any
added **or removed** line of the stored patch (a removed tracking or consent include is a data-flow
change too; consistent with 08_seats_wps.md Appendix C item 13's check-9 content rule) — matches (case-insensitive) `<script`, `<iframe`, `<form`,
`<noscript`, or a host in `checks.TRACKER_HOSTS` (at least `googletagmanager.com`,
`google-analytics.com`, `analytics.google.com`, `googleadservices.com`, `doubleclick.net`,
`connect.facebook.net`, `facebook.com/tr`, `bat.bing.com`, `snap.licdn.com`,
`analytics.tiktok.com`, `static.hotjar.com`, `cdn.callrail.com`, `calendly.com`, `acuityscheduling.com`,
`widget.intercom.io`; subdomains included), or introduces an absolute `http(s)` URL whose host is
not in `brands[].domains` and does not already appear in `before.text`/`before.value` (or the
patch's removed lines). Effective `data_flow` adds the `measurement` lane and makes trust-architect
the `hipaa` reviewer of record on a hipaa pack (02_act.md §2.7, requests/03_schemas.md R25).
**Tracking never lands through `website_static`:** 02_act.md §2.8 check 9 and 08_seats_wps.md
Appendix C item 13 refuse tracking content in a `website_static` patch (`tracking_change_not_static`),
so for that row the lane computation below is exercised only as a **computation** — the proposal
itself is refused. P2 tests (A1): `makerchecker.required_lanes` over a OtherCompany
`website_static.page_edit` patch adding a Meta pixel `<script>` returns a set containing
`measurement` and `hipaa` with trust-architect as `hipaa` reviewer (lane computation only), and
`propose` of that same patch is refused `tracking_change_not_static`; a
`website_wordpress.page_edit` adding a booking `<iframe>` requires `measurement` and a `hipaa`
review by trust-architect at `authorize`; each goes RED when `content_data_flow` is reverted to the
row flag; a `website_static.page_edit` patch that only **removes** a `googletagmanager.com`
`<script>` line yields `measurement` in `required_lanes` too, RED when removed lines are not
scanned),
`hipaa_prohibited` (enforced only for `regulated ∋ hipaa` packs, 02_act.md §2.8 check 5), `card_on_refuse`
(bool; a NEVER row whose refusal must still reach the operator as a `card` notice, 02_act.md §2.6 rule 2),
`inbox_reply` (bool; a reply to an inbound review/comment/DM/Q&A/email inquiry — the 02_act.md §2.8 check 5
template rule for hipaa packs; a **held** `inbox_reply` action with a non-null `lead_id` is the one
the §3.11 `responded_by` auto-cancel applies to), `amount_required` (bool, money rows only; default
true; false = a non-numeric `$` change signed over `after_digest`, 02_act.md §2.8 check 8),
`recipient_required` / `lead_id_required` (bool; 02_act.md §2.8 check 8 refuses `recipient_missing` /
`lead_id_missing`), `setup_capture` (bool; the only rows `ticket --setup` accepts, 02_act.md §2.4/§3.6),
`commits_on_enable` (bool, money rows only; the row enables an object whose committed ceiling was
configured by an earlier action — `google_ads.campaign_enable`, `lsa.account_enable`,
`L.paid_enable`, `meta.campaign_enable`, `meta.adset_enable`, `{thumbtack,angi}.lead_enable`; its `$` amount is that configured
ceiling, §3.2 "Enable actions", FID-03),
`resulting_status` (**DECIDED (wave1e), finding wave1d-M3**, applying 05_approver.md §5.5 step 3b
"Stops are never in the enable group" and `requests/05_approver.md` R84: an **authored** enum
`"paused" | "removed" | "active" | "unbounded" | "unchanged"` — the serving state the row leaves its
object in: `paused` stops serving/spend while the object remains; `removed` deletes, archives or
removes it; `active` leaves it serving within a configured ceiling; `unbounded` leaves it serving
with a ceiling or end date lifted (e.g. a `remove_end_date`/`delete_spend_limit` shape); `unchanged`
does not change its serving state (a budget edit, a purchase, a subscription). **Which rows must
carry it:** every row with `money: true` **or** `commits_on_enable: true` (the `_nomatch` pseudo-row
excepted: it has no authored effect and is never a stop); the tier-table validator
refuses the table at load with `resulting_status_missing: <row id>` when such a row lacks it,
`resulting_status_invalid: <row id>` for a value outside the enum, and
`commits_on_enable_and_resulting_status_conflict: <row id>` for a row with `commits_on_enable: true`
and `resulting_status` ∈ {`paused`, `removed`} — never defaulted, never derived from the row's verb
tokens (a verb such as `remove_end_date` tokenizes to `remove` while resuming spend). Other rows
may omit it (absent = not a stop). **The stop group is exactly the rows whose `resulting_status` ∈
{`paused`, `removed`}** — the one predicate 05_approver.md §5.1 step 3 (dialog variant), §5.5 step
3b (enable-binding exemption), §5.8 (requested state) and 06_connectors.md §6.2 read; §3.2's
stop-token set stays only the `_nomatch` budget-object guard (`paid_object_use_money_row`) and is
never read for this. In the committed table: `google_ads.campaign_pause`, `meta.campaign_pause`,
`meta.adset_pause`, `lsa.account_pause`, `L.paid_pause`, `{facebook,instagram}.boost_stop`,
`{thumbtack,angi}.lead_pause` carry `paused`; `google_ads.campaign_remove`, `meta.campaign_remove`,
`meta.adset_remove`, `lsa.account_remove`, `L.paid_remove` carry `removed`; every
`commits_on_enable` row carries `active`; every other money row (budget edits incl.
`meta.campaign_budget_edit`, purchases, subscriptions, trials, registrations, boosts, usage starts)
carries `unchanged` (or `active` where it starts serving). P2 tests (A1), each RED when its refusal
is removed: a money row with no `resulting_status` → `resulting_status_missing`; `"stopped"` →
`resulting_status_invalid`; `commits_on_enable: true` with `"paused"` → the conflict code; and the
set of committed rows with `resulting_status` ∈ {`paused`, `removed`} equals the list above exactly),
`list_send` (bool; `email.list_send`/`sms.list_send`, the §3.11 list-send rules, FID-13),
`current_value` (`read` | `zero`, money rows only; absent = `read`; `zero` = nothing is committed
before this action, so `before.value.current_absolute_value` must be `"0.00"` — the purchase,
subscription, trial, registration, boost and usage-start money rows, as the §3.4.4
table marks (no campaign or ad-set create row is a money row: they are T1, created paused, §3.2
"Paused creates" — the `*_create` money rows that remain, `sms_provider.a2p_10dlc_registration_create`
and `vendor.subscription_create`, carry `current_value: zero`); §3.2 "Current value of other money
actions"),
`object_scope` (`account` | `object`, **required on every write row**; FID-02, 06_connectors.md
§6.2 target resolution step 5 — an `object` row must resolve at least one non-account-level id, else
`target_missing`, no write). **The one rule (DECIDED HERE; computed from the row, not a §3.4.4 table column):** `object` for (a)
every row with an `id_fields` key of kind `in_account` that is neither its `self_id` nor in its
`optional_ids`, and (b) the `google_ads`/`meta` money rows whose object is named only by
`target_ref` — `google_ads.campaign_budget_edit`, `.campaign_enable`, `.campaign_pause`,
`.campaign_remove`, `meta.adset_budget_edit`, `.adset_pause`, `.adset_enable`, `.adset_remove`,
`.campaign_enable`, `.campaign_remove`, `.campaign_pause`, `.campaign_budget_edit`, and
`{facebook,instagram}.boost_stop` and `{facebook,instagram}.post_boost` (the boosted post — a
boost's `target_ref` must be the post-level form, `page/<id>/posts/<id>` or `ig/<id>/media/<id>`;
`propose` refuses any other form exit 3 **`boost_post_required`**, so which post receives paid
distribution is fixed in the signed `display.object_ref`, never chosen at execution);
`account` for every other row (profile, listing and page-level
edits whose object is the location, page, property or listing itself — an account-level key —
account settings, users, links, setup rows, creates without a required parent, and every other
money row). A1 writes the computed value into each row; the tier-table validator recomputes it and
refuses a mismatch, and refuses an `object` row with no qualifying `id_fields` key whose system's
§3.22 grammar yields no non-account-level key,
`after_value_enums` (map `{<after.value key>: [allowed values]}`; **part of matching**, §3.4.2: a
row whose enum is not satisfied by the proposal does not match, so the proposal falls through to
later rows and, finally, to `_nomatch` (`$`); check 10 re-asserts it for the matched row — **every
`*settings_edit` row carries one for `setting`**, DECIDED HERE, so an unlisted account, billing,
budget-type or auto-apply setting can never ride an identity row; **a list-valued key** (e.g.
`scopes`) satisfies its enum only when it is a non-empty list and **every** element is in the
allowed list — one unlisted element and the row does not match (DECIDED HERE)),
`self_id` (create rows only: the `id_fields` key naming the object being created — it must be
absent or null in the proposal and is exempt from kind resolution, since the object does not exist
yet; the same key on the paired edit row is an ordinary required `in_account` id),
`required_ids` (list of `id_fields` keys that must be present and non-null — `id_field_missing`,
exit 3, at `propose`; parent ids of create rows are listed here; absent = every `id_fields` key
except `self_id` and the row's `optional_ids`), `optional_ids` (list of `id_fields` keys that may be
absent; a present key is always checked, and a present null is refused `id_field_null` except a
create row's `self_id`),
`id_fields` (FID-02; map `{<after.value key>: <kind>}` — **required** for every `after_value_fields`
key that names another object: any key ending `_id` or `_ref` except `template_id` and `lead_id`
(`source_ref` is **not** exempt — its kind is `home_data`, below), plus `listing_url`, `email` and
`phone_number`, **plus `phone` and any key ending `_phone`** (DECIDED HERE: a number written into
a public phone field is judged by `pack_phone`, not only by check 2), **plus every key naming a
user account: `username`, `user_login` and any key ending `_login`** (DECIDED HERE: a login names
another object — the user whose rights a credential carries), **and every destination key: any key
ending `_url` or `_urls`, plus `to_url`, `redirect_to`, `url`**; the tier-table validator refuses a
row that lacks one). An `address` value (`gbp.address_edit`, `L.nap_edit`) is a **string**: a
dict there is refused `nested_ids_undeclared` (§3.4.1 closure rule; `address` is not a structured
key). **A list-valued key**
(e.g. `final_urls`) maps to the kind of its elements: every element is judged, and a non-list value
is refused `after_shape_invalid`.
**Kinds — the one definition (02_act.md §2.8 check 1(d)/(e) apply these and define no variant of
their own, requests/03_schemas.md R26):**
- `identity` — the value is one of this pack's identity values (`identity_allowlist.*` ∪
  `accounts[].account_id`), or a `shared_identifiers` value (class then `shared`). **Normalization
  (DECIDED HERE):** each allowlist value is normalized with the system its bucket belongs to (the
  inverse of `system_names.identity_bucket`: `ads_customer_ids` → `google_ads`,
  `meta_ad_account_ids` → `meta`, `facebook_page_ids` → `facebook`, `instagram_ids` → `instagram`,
  `gbp_location_ids` → `gbp`, `ga4_property_ids` → `ga4`, `gtm_container_ids` → `gtm`, `domains`
  → lowercased host; any other bucket unchanged), each `accounts[].account_id` with
  `tier_system_of(entry.system)`; the candidate is normalized with the **action's** tier system;
  the test is membership in the union. So `100-200-3000` in `ads_customer_ids` admits
  `1002003000` on a google_ads row, and a gbp-row candidate is never compared as if it were an Ads
  id.
- `identity_in:<tier system>` (DECIDED HERE; the fixed-system form of `identity_for`, used by
  `nested_id_paths` below and by keys whose system is known from the row) — exactly the
  `identity_for` test with `t` fixed to `<tier system>`, plus the tag-id lists
  `identity_allowlist.ga4_measurement_ids` (for `ga4`), `identity_allowlist.ads_conversion_ids`
  (`AW-<digits>`, for `google_ads`) and `identity_allowlist.meta_pixel_ids` (for `meta`) and the
  `account_id` of every `accounts[]` entry whose `system` is `<tier system>` or, for `meta`,
  `meta_pixel` (requests/03_schemas.md R35 adds the three optional lists to the pack schema). These
  tag ids are compared casefolded, whole value. An id missing from the pack fails closed (class
  `never` + card) and is added through a reviewed pack change.
- `identity_for:<key>` (FID-02; 06_connectors.md §6.2 step 6) — the stricter form used where the
  row names the target's system in another `after.value` key (today `ids(target_id:identity_for:target_system)`
  on `*.asset_link`): with `t = tier_system_of(after.value[<key>])`, the value must be in
  `identity_allowlist[system_names.identity_bucket(t)]` ∪ the `system_names.account_keys(t, a)`
  values of every `accounts[]` entry `a` whose normalized system is `t` (both sides normalized with
  `normalize_account_id(t, …)`), or be a `shared_identifiers` value (class `shared`). Being some
  other identity value of the pack does **not** satisfy it (a GA4 id cannot be linked as a Meta
  object), and a `t` whose `identity_bucket` is None fails.
- `email` — the whole address (casefolded) is one of those values, **or** its domain is in
  `brands[].domains` ∪ `identity_allowlist.domains` and is **not** in
  `system_names.PUBLIC_MAIL_DOMAINS` (gmail.com, googlemail.com, outlook.com, hotmail.com, live.com,
  msn.com, yahoo.com, ymail.com, aol.com, icloud.com, me.com, mac.com, proton.me, protonmail.com,
  gmx.com, zoho.com — a public-webmail domain admits only a whole listed address; `company.py
  validate` also refuses such a domain in `identity_allowlist.domains`, requests/03_schemas.md R27),
  or it is a `shared_identifiers` value (class `shared`).
- `listing` — exactly equal to an `identity_allowlist.listing_urls` entry.
- `destination` (DECIDED HERE; plan §6.3/§7 "create/modify anything whose … domain fails §7 →
  NEVER") — a link written into public content: a site-relative path (starts with `/`, not `//`,
  no scheme) is admitted; an absolute `http(s)` URL is admitted only when its host is equal to, or a
  subdomain of, an entry of `brands[].domains` ∪ {host of each `brands[].booking_url`} ∪
  `identity_allowlist.domains`; `tel:<n>` only when `<n>` (digits only) equals a pack phone value;
  `mailto:<a>` by the `email` kind; a `shared_identifiers` host → class `shared`; anything else
  (another scheme, an off-pack host) fails.
- `own_domain` — an absolute URL (or `sc-domain:<host>`, or a bare lowercase host) whose host is
  equal to, or a subdomain of, a `brands[].domains` entry only (the object acted on is the
  company's own site: `sitemap_url`, the `url` of a removal request, the `domain` of a renewal).
- `catalog_item` (DECIDED HERE; purchase rows only) — an id in a vendor's **public** catalog (a
  stock asset, a plugin or plan product): nothing is linked to or granted by it, so it has only
  the syntactic part of `in_account` (no host, no URL scheme, equal to no sibling-pack,
  `other_businesses` or `shared_identifiers` value; failure → `unlisted_target`, class `never`).
  It is kind-checked so the signed `after_digest` and `display.object_ref` name exactly what is
  bought.
- `in_account` — an object under the action's own `account_id` (campaign, ad group, ad, asset,
  list, page, workspace…), which no pack can enumerate. Admission has **two parts, both required**:
  (1) syntactic, at `propose`/check 1 — the value carries no host, no URL scheme and equals no
  sibling-pack, `other_businesses` or `shared_identifiers` value (failure → `unlisted_target`, class
  `never`); it is **not** tested for membership of `OWN`; (2) **positive binding at execution** —
  for an API-executed action the connector resolves the id only under `ctx.account`
  (06_connectors.md §6.2 target resolution; `not_owned` → no write); for a browser-executed action
  the runbook's `writes[<row>]` carries an **`account_breadcrumb` before-check step** that asserts
  the object's page URL or its account breadcrumb/header contains the action's `account_id` (and,
  when `target_ids` captured an account-level id, that id) before the first mutating call, failing
  `before_mismatch` with no write. The runbook validator (L) refuses a runbook whose `writes` entry
  for a row with any `in_account` id field lacks that step (`in_account_check_missing`,
  requests/03_schemas.md R28). P2 test (L, fake browser): a `L.object_delete` whose page breadcrumb
  shows another business's account id fails `before_mismatch` with zero mutating calls.
- `pack_phone` (DECIDED HERE; a phone number written into public content or an ad asset) — the value
  reduced to digits (a leading `+1` / `1` dropped for a 10-digit US number) equals a pack phone
  value (the same set the `destination` kind's `tel:` test uses: every value of this pack that
  02_act.md §2.2's KEY → KIND table classes as `phone` — `brands[].nap.phone`, `brands[].phones[]`
  and `identity_allowlist` keys ending `phones` — each reduced the same way; requests/03_schemas.md
  R59 asks 08 Appendix C to define those keys), or is a `shared_identifiers` value (class `shared`);
  anything else fails.
- `wp_gtm_user` (DECIDED HERE; plan §17 j "a dedicated per-site user at Editor level with its own
  application password, never an Administrator's") — the WordPress user a captured application
  password belongs to. The value, casefolded, must equal the casefolded
  `accounts[].gtm_user_login` of the pack's `website_wordpress` account the action runs under (the
  entry check 1(a) matched; a **required** field of every `website_wordpress` account —
  requests/03_schemas.md R70 → 08_seats_wps.md Appendix C `company_schema.json`); nothing else
  admits it — no `shared_identifiers` class, no other account's login. Failure (including an
  account with no `gtm_user_login`) → class `never` with a `card` notice, like any failed kind. The
  kind is paired with a **role check at capture** (requests/03_schemas.md R70 → 06_connectors.md
  §6.6): the allowlisted capture script, before it creates or reads the application password, reads
  that user's role (`/wp-admin/user-edit.php` for the user, or the REST `users/me?context=edit`
  `roles` value once signed in as that user) and aborts with `before_mismatch` — no application
  password created, nothing written to GSM — unless the roles are exactly `["editor"]`. P2 tests:
  (A1) a `website_wordpress.application_password_create` with `user_login: "admin"` on the
  OtherCompanyB fixture (whose `gtm_user_login` is `gtm-editor`) computes class `never` with a card,
  and `user_login: "GTM-Editor"` passes; (E/L, fake WordPress) a capture whose role read returns
  `["administrator"]` aborts `before_mismatch` with zero GSM writes; each RED when its clause is
  removed.
- `platform_catalog` (DECIDED HERE; ids in a platform's **public taxonomy** — a Meta interest, geo or
  locale key, a Google geo/language target constant, a GBP category or `serviceTypeId`) — nothing
  is linked to or granted by it, so it has only the syntactic part of `in_account` (no host, no URL
  scheme, equal to no sibling-pack, `other_businesses` or `shared_identifiers` value; failure →
  `unlisted_target`, class `never`). `catalog_item` is the same test restricted to purchase rows.
- `tag_id` (DECIDED HERE; a tracking id whose system is known only from its shape, e.g. a GTM
  Google-tag `tagId` that may be `G-…` or `AW-…`) — the value must match exactly one
  `checks.TAG_ID_PATTERNS` entry (below) and is then judged by that entry's kind; a value matching
  none fails (class `never` + card, reason `tracker_id_unparsed`).
- `home_data` (DECIDED HERE; plan §20.2 isolation, §20.3 "Banned: … any export, report or file derived
  from it … enforcement scoped to GTM sessions and GTM seats") — the data file an upload row sends to
  an ad or messaging platform (`source_ref` of every `*_upload` row). Rules, all required: (1) a
  **home-relative** path (no leading `/` or `~`, no `..` segment, no NUL); (2) `realpath(H / value)`
  is a regular file equal to or under `realpath(H / pack.paths.data_dir)` (a symlink whose target
  leaves it fails); (3) that realpath is not equal to or under any `phi_denylist.json` `paths` entry
  (§3.20, every company — `applies_to` never narrows a path entry),
  `realpath("~/Desktop/OtherCompany Files")`, the Agency root, or the root of **any other**
  registered entry. **Enumerator (DECIDED HERE; never `company.registered_slugs()` or
  `resolve_home`, which drop a slug registered in both registries and every slug in
  `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` — exactly the entries this rule must still exclude):**
  `company.all_registered_roots() -> list[tuple[str, str, str]]` (new, requests/03_schemas.md R82 →
  08_seats_wps.md Appendix C) returns one `(slug, registry, root_text)` per entry of
  `_gtm_registry_companies()` **and** per entry of the **unfiltered** `_repo_registry_repos()`
  (`registry` ∈ `gtm|repo`), reading each entry's `root` string directly (`~`/`~/` expanded exactly as
  00_global_paths.md §0.1 expands registry roots, test-mode split included, then `os.path.normpath`; **no** `resolve()`, `realpath` or `stat` inside the
  function), with no allowlist, no name exclusion and no duplicate removal — so a slug present in
  both registries contributes **both** roots. An entry that is not an object, or has no non-empty
  string `root`, raises `CompanyError`. The excluded set is every returned root except those of
  entries whose slug equals `ctx.company` **and** whose root, realpath'd, equals `realpath(H)`
  (the company's own home; a second, different root registered under the same slug is still
  excluded). Each root that is equal to, under, or an ancestor of either Agency root (text compare,
  `gtm_env.norm_text`/`is_under`/`is_ancestor`) is compared as normalized path **text** and never
  `realpath`ed or stat'd (00_global_paths.md §0.1 no-Agency-touch); every other root is compared by
  `realpath`. A `CompanyError` from `all_registered_roots()` (a present-but-unreadable registry, a
  malformed entry) **fails closed**: class `never`, reason `source_outside_home_data`, with the
  card. A1 tests (each RED when the enumerator is `registered_slugs()`): a fixture slug registered
  in both registries with two different roots, and a `source_ref` whose realpath lies under either
  root, is refused `source_outside_home_data`; a `source_ref` under a repo-registry-only fixture
  root is refused; a corrupt fixture repo registry refuses every upload;
  (4) for a `regulated ∋ hipaa` pack the row is `hipaa_prohibited` anyway (check 5). Failure of (1)
  → `source_ref_invalid` (exit 3, stage 1); failure of (2)–(3) → class `never` with a `card` notice
  (reason `source_outside_home_data`), like any failed kind. **Checked twice:** at `propose`/check 1
  and again by `execute` (and by `ticket --write` mint for a browser upload) immediately before the
  file is opened — act.py reads it in-process during `execute`, where no G-B, G-W or path-gate hook
  runs (those gate tool calls, not Python `open()`), so this kind is the only control there.
  **Byte binding (DECIDED HERE):** every upload row's `after.value` also carries `source_sha256`
  (hex sha256 of the file's bytes) and `row_count` (the number of data rows, header excluded, per the
  upload's declared format), **both set by act.py at `propose`** from the file (a supplied differing
  value → exit 3 `source_mismatch`; a supplied equal value is accepted), so `after_digest`, every lane
  review, any card and the §3.7 signature bind the exact bytes. `execute` (and the browser
  gtm-operator's runbook before-check, from `dispatch_brief.after`) re-hashes the file and recounts
  its rows immediately before the upload and fails `before_mismatch`, no upload, on any difference.
  P2 tests (A1): a OtherApp `google_ads.customer_match_upload` whose `source_ref` is a fixture file
  under a `phi_denylist` path (reached through a symlink inside `data_dir`, and directly) computes
  class `never` with a card; one whose `source_ref` names a file under another registered company's
  home computes `never`; one whose file changes after `authorize` fails `before_mismatch` at
  `execute` with zero upload calls; a supplied `row_count` that differs from the file is refused
  `source_mismatch`; each goes RED when the kind (or the re-hash) is removed (requests/03_schemas.md
  R60 → 02_act.md §2.4 `propose`/`execute`, 06_connectors.md §6.2).

**`nested_id_paths` (DECIDED HERE; a CLOSED path schema for every structured value — never a list
of the paths that happen to get checked).** `id_fields` covers top-level `after.value` keys only; a
structured value (a GTM tag list, Meta targeting, a promoted object, GBP services) carries platform
ids and hosts of its own, and a platform can add id-bearing subkeys at any time. So every row whose
`after_value_fields` contains a **structured key** (the closed list below) carries
`nested_id_paths`: a map `{<path pattern>: <kind> | "none" | "opaque"}`.
- **Pattern syntax.** A pattern starts with the top-level key and continues with `.<name>` (a dict
  key), `[*]` (every list element), or `[<field>=<a>|<b>…]` (every list element whose `<field>`
  value is one of the names, e.g. `[key=conversionId]`, `[type=awct]`; the pattern then continues
  from that element). In this section `.{a|b|c}` is prose shorthand for one pattern per name; the
  JSON lists each pattern separately. There is no recursive wildcard.
- **Leaves and closure.** At `propose` the value of each structured key is walked; a **leaf** is
  every scalar (string, number, bool, null) it contains, with its concrete path. **Every leaf must
  match at least one pattern** — a leaf path that matches none is refused exit 3
  **`nested_path_unlisted`** (no event; `detail` names the path; the `table_gap` notice of §3.4.2
  "Unknown systems, templates and paths"), never passed. A leaf matched by
  several patterns must pass every one of their kinds. An empty dict or list has no leaves.
  `before.value` leaves are judged by the same patterns when they match one (so a shared value in
  the current state still counts, §3.4.3); unmatched `before.value` leaves are ignored (the platform's
  current state is not something GTM writes).
- **`"none"`** = "reviewed: this leaf carries no id" (a number, enum, label or date); the leaf still
  goes through check 2 and the tag-id scan below like every string in `after`.
- **`"opaque"`** (DECIDED HERE; allowed only on the keys marked *opaque-allowed* below, never on
  `tags`, `targeting`, `promoted_object` or `services`) = a reviewed subtree of free-form strings
  whose ids cannot be enumerated: the value at that path and every leaf under it is judged by (a)
  the tag-id scan (every match judged by its pattern's kind), (b) the `destination` kind for every
  absolute `http(s)` URL or bare host it contains whose host is not in `checks.TRACKER_HOSTS` (below),
  and (c) the syntactic part of `in_account` for the whole leaf (equal to no sibling-pack,
  `other_businesses` or `shared_identifiers` value). An opaque path covers every leaf below it.
- **Kinds** are judged **exactly as check 1(d) judges `id_fields`** (same kinds, same
  `never`/`shared`/card outcome). An `in_account` nested id additionally gets the §3.4.1 positive
  binding at execution: the connector resolves **each** such id under `ctx.account` before the
  write (for a Meta audience id: a read of the audience's `account_id`, which must equal the action's
  ad account, else `not_owned`, no write; for a browser row the runbook `account_breadcrumb` step
  covers each), requests/03_schemas.md R61 → 06_connectors.md §6.2.
- **Structured keys (the closed list; the tier-table validator refuses a row naming one in
  `after_value_fields` without patterns rooted at it):** `tags`, `triggers`, `variables`,
  `targeting`, `promoted_object`, `value_settings`, `criteria`, `network_settings`, `geo_targets`,
  `language_targets`, `special_hours`, `services`. A structured key's value is **always** walked,
  whatever its type (a list of strings included). Enforcement is two-place: (1) that validator
  (A1, P2 test) also refuses `opaque` outside the opaque-allowed keys and a pattern whose kind is
  unknown; (2) at `propose`, an `after.value[k]` that is a dict, or a list with any dict element,
  where `k` is not a declared structured key of the row is refused exit 3 `nested_ids_undeclared`
  (unchanged), and every leaf of a declared key is checked for closure as above.

**Tag-id scan (backstop, now fail-closed).** On every row whose effective `data_flow` is true, and
on `_nomatch`, every string leaf anywhere in `after` (for `website_static`, the added lines of each
patch hunk, concatenated per hunk) is scanned with `checks.TAG_ID_PATTERNS`, and every match is
judged by that pattern's kind (requests/03_schemas.md R46/R61 → 02_act.md §2.8 check 1(d)):

| Pattern (`re`, case-sensitive unless noted) | Kind |
|---|---|
| `\bG-[A-Z0-9]{6,}\b`, `\bUA-\d+-\d+\b` | `identity_in:ga4` |
| `\bAW-\d{6,}\b` | `identity_in:google_ads` |
| `\bGTM-[A-Z0-9]{4,}\b` | `identity_in:gtm` |
| `fbq\(\s*['"]init['"]\s*,\s*['"](\d{6,})`, `facebook\.com/tr/?\?[^"'\s]*\bid=(\d{6,})` | `identity_in:meta` |
| `bat\.bing\.com/action/0\?[^"'\s]*\bti=(\d{4,})`; `\bti\s*:\s*['"]?(\d{4,})` only in a unit that also contains `bat.bing.com` or `uetq` | `tag_bucket:bing_uet_tag_ids` |
| `_linkedin_partner_id\s*=\s*['"]?(\d{3,})`, `px\.ads\.linkedin\.com/collect/?\?[^"'\s]*\bpid=(\d{3,})` | `tag_bucket:linkedin_partner_ids` |
| `ttq\.load\(\s*['"]([A-Z0-9]{15,25})['"]`, `analytics\.tiktok\.com/i18n/pixel/events\.js\?[^"'\s]*\bsdkid=([A-Z0-9]{15,25})` | `tag_bucket:tiktok_pixel_ids` |

(With a capture group, the group is the judged value; otherwise the whole match.) **`tag_bucket:<b>`**
(DECIDED HERE) = the value, casefolded, is in `identity_allowlist.<b>` (an optional pack list;
absent = empty — requests/03_schemas.md R59 adds `bing_uet_tag_ids`, `linkedin_partner_ids` and
`tiktok_pixel_ids` to the pack schema), or is a `shared_identifiers` value (class `shared`).
**Unparsed tracker (DECIDED HERE; fail closed):** a scanned unit that contains a host of
`checks.TRACKER_ID_HOSTS` (`googletagmanager.com`, `google-analytics.com`, `analytics.google.com`,
`googleadservices.com`, `doubleclick.net`, `connect.facebook.net`, `facebook.com/tr`,
`bat.bing.com`, `snap.licdn.com`, `px.ads.linkedin.com`, `analytics.tiktok.com`; subdomains
included) or an init token (`fbq(`, `gtag(`, `uetq`, `_linkedin_partner_id`, `ttq.`) and from which
no `TAG_ID_PATTERNS` entry extracted any value makes the action class `never` with a `card` notice,
reason **`tracker_id_unparsed`** — an ad or analytics tag whose account id we cannot read is never
admitted. `checks.TRACKER_HOSTS` (§3.4.1 `content_data_flow`) keeps its wider list: the chat,
booking and session-recording hosts in it (`static.hotjar.com`, `cdn.callrail.com`, `calendly.com`,
`acuityscheduling.com`, `widget.intercom.io`) trigger the `measurement` + `hipaa` lanes, not this
refusal.

**The rows' maps (normative).**
- `gtm.workspace_edit` — **`tags` (closed per template).** Tag-level leaves of every tag:
  `tags[*].{name|type|tagFiringOption|paused|notes}` → `none`; `tags[*].{accountId|containerId}` →
  `identity_in:gtm`; `tags[*].{workspaceId|tagId|parentFolderId}`, `tags[*].firingTriggerId[*]`,
  `tags[*].blockingTriggerId[*]` → `in_account`; `tags[*].priority.{type|key|value}` → `none`;
  `tags[*].consentSettings.consentStatus`, `tags[*].consentSettings.consentType.{type|key|value}`,
  `tags[*].consentSettings.consentType.list[*].{type|key|value}` → `none`; parameter framing
  `tags[*].parameter[*].{type|key}` → `none`. **Template set (closed):** `tags[*].type` ∈
  {`googtag`, `gaawc`, `gaawe`, `awct`, `awcc`, `sp`, `gclidw`, `html`, `img`}; any other `type`
  (every community-gallery `cvt_…` template, Floodlight `flc`/`fls`, Universal Analytics `ua`) is
  refused exit 3 **`gtm_template_unlisted`** (with the §3.4.2 `table_gap` notice) until a reviewed tier-table change adds it. Per
  template, the only admitted parameter values (a `parameter[key=<other>]` of that template leaves
  its `.value` unmatched → `nested_path_unlisted`):
  `[type=googtag]`: `tagId` → `tag_id`; `configSettingsTable` / `eventSettingsTable`
  `.list[*].map[*].{type|key}` → `none`, `.list[*].map[*].value` → `opaque`.
  `[type=gaawc]`: `measurementId` → `identity_in:ga4`; `sendPageView` → `none`; `fieldsToSet`
  `.list[*].map[*].{type|key}` → `none`, `.value` → `opaque`.
  `[type=gaawe]`: `measurementIdOverride`, `measurementId` → `identity_in:ga4`; `eventName`,
  `sendEcommerceData` → `none`; `eventParameters` / `userProperties` / `eventSettingsTable`
  `.list[*].map[*].{type|key}` → `none`, `.value` → `opaque`.
  `[type=awct]`: `conversionId` → `identity_in:google_ads`; `conversionLabel`, `conversionValue`,
  `currencyCode`, `orderId`, `conversionCookiePrefix` → `none`.
  `[type=awcc]`: `conversionId` → `identity_in:google_ads`; `conversionLabel` → `none`;
  `phoneConversionNumber` → `pack_phone`.
  `[type=sp]`: `conversionId` → `identity_in:google_ads`; `conversionLabel` → `none`;
  `customParams` `.list[*].map[*].{type|key}` → `none`, `.value` → `opaque`.
  `[type=gclidw]`: `enableCrossDomain`, `enableUrlPassthrough`, `enableCookieOverrides`,
  `acceptIncoming`, `formDecoration` → `none`; `linkerDomains` → `own_domain` (comma-separated:
  each item judged).
  `[type=html]`: `html` → `opaque`; `supportDocumentWrite` → `none`.
  `[type=img]`: `url` → `destination`; `useCacheBuster`, `cacheBusterQueryParam` → `none`.
  A Google Ads `conversionId` written as digits only (the GTM template form) is compared as
  `AW-<digits>` against `identity_allowlist.ads_conversion_ids` and as-is against the Ads account
  keys. Parameter key names other than `awcc`'s (verified live 2026-09-26) are **UNVERIFIED**
  against the current GTM template reference: WP-A1 checks each against an exported container of
  the OtherCompanyB fixture before P2 and corrects this list through a reviewed change — a mis-named
  key fails closed (`nested_path_unlisted`), never open. **`triggers`** and **`variables`**
  (opaque-allowed): `triggers` → `opaque`, `variables` → `opaque` (a constant variable holding an id
  is judged by the tag-id scan; a URL by `destination`).
- `meta.adset_create`, `meta.adset_targeting_edit` and `{facebook,instagram}.post_boost` (a boost
  carries the same Marketing API targeting spec; its `in_account` audience ids resolve under the
  brand's `meta` ad account — the pack `accounts[]` entry with `system: "meta"` and the action's
  `brand`, which the boost is billed to; with no such entry check 1 fails `unlisted_target`, class
  `never`; requests/03_schemas.md R71 → 06_connectors.md §6.2) — **`targeting` (closed):**
  `targeting.geo_locations.{countries|location_types}[*]` → `none`;
  `targeting.geo_locations.{regions|cities|zips|geo_markets|electoral_districts}[*].key` →
  `platform_catalog`; `….{regions|cities|zips|geo_markets|electoral_districts}[*].{name|radius|distance_unit|country}`
  → `none`; `targeting.geo_locations.custom_locations[*].{latitude|longitude|radius|distance_unit|address_string|country}`
  → `none`; the same set under `targeting.excluded_geo_locations`;
  `targeting.{age_min|age_max}` and `targeting.{genders|locales}[*]` → `none`;
  `targeting.interests[*].id` and `targeting.flexible_spec[*].interests[*].id` → `platform_catalog`,
  their `.name` → `none`; `targeting.custom_audiences[*].id`,
  `targeting.excluded_custom_audiences[*].id`, `targeting.flexible_spec[*].custom_audiences[*].id`
  and `targeting.exclusions.custom_audiences[*].id` → `in_account` (with the execution-time
  resolution above), their `.name` → `none`;
  `targeting.{publisher_platforms|facebook_positions|instagram_positions|device_platforms|audience_network_positions|messenger_positions}[*]`
  → `none`; `targeting.targeting_automation.advantage_audience` → `none`. **Everything else under
  `targeting` is refused** `nested_path_unlisted` — in particular `connections`,
  `excluded_connections` and `friends_of_connections` (Page/app ids; UNVERIFIED whether still
  current in the Marketing API — refused either way), `geo_locations.places` (place Page ids),
  `behaviors`, `work_employers`, `flexible_spec[*]` keys other than `interests` and
  `custom_audiences`, and `exclusions` keys other than `custom_audiences`.
  `meta.adset_create` only — **`promoted_object` (closed):** `promoted_object.pixel_id` →
  `identity_in:meta`; `promoted_object.page_id` → `identity_in:facebook`;
  `promoted_object.custom_event_type` → `none`; every other key (`product_catalog_id`,
  `product_set_id`, `offline_conversion_data_set_id`, `application_id`, `object_store_url`,
  `custom_conversion_id`, …) → `nested_path_unlisted`. (`meta.campaign_create` carries neither key.)
- `google_ads.campaign_create` — `network_settings.{target_google_search|target_search_network|target_content_network|target_partner_search_network|target_youtube|target_google_tv_network}`
  → `none`; `geo_targets[*]` and `language_targets[*]` (resource names `geoTargetConstants/<id>` /
  `languageConstants/<id>`) → `platform_catalog`.
- `google_ads.conversion_action_create` / `_edit` —
  `value_settings.{default_value|default_currency_code|always_use_default_value}` → `none`.
- `ga4.key_event_edit` / `ga4.data_filter_edit` / `ga4.custom_dimension_edit` — `criteria` →
  `opaque` (opaque-allowed; these rows are `data_flow: true`, so the scan runs too).
- `gbp.hours_edit` — `special_hours[*].{startDate|endDate}.{year|month|day}`,
  `special_hours[*].{openTime|closeTime}.{hours|minutes|seconds|nanos}`, `special_hours[*].closed`
  → `none` (a dated entry carries no id).
- `gbp.services_edit` — `services[*].structuredServiceItem.serviceTypeId` → `platform_catalog`;
  `services[*].structuredServiceItem.description` → `none`;
  `services[*].freeFormServiceItem.category` → `platform_catalog`;
  `services[*].freeFormServiceItem.label.{displayName|description|languageCode}` → `none`;
  `services[*].price.{currencyCode|units|nanos}` → `none` (a listed service price, not ad spend).
  Both GBP maps' field names follow the Business Profile API `SpecialHourPeriod` / `ServiceItem`
  shapes (UNVERIFIED against the current API version — corrected by the same A1 check as above).
- `website_wordpress.page_edit` / `post_edit` / `page_publish` / `post_publish`: `schema_jsonld` is a
  **string**, not a structured key (its URLs go through check 2 and `content_data_flow`); a dict
  there is refused `nested_ids_undeclared`.
P2 tests (A1; each RED when its pattern, the closure, or the scan is removed): a `gtm.workspace_edit`
whose `gaawe` tag's `measurementIdOverride` is an off-pack `G-` id, one whose `awct` `conversionId`
is an off-pack `AW-` id, and one whose `html` tag text contains an off-pack `fbq('init','…')` pixel
each compute class `never` with a card notice, and the same proposals with the pack's own ids pass;
an `html` tag loading `bat.bing.com` with a `ti` not in `bing_uet_tag_ids`, one with a LinkedIn
partner id, and one with a TikTok `ttq.load('…')` id each compute `never`; an `html` tag containing
`connect.facebook.net/en_US/fbevents.js` and no parseable pixel id computes `never` with reason
`tracker_id_unparsed`; a tag of type `cvt_12345` is refused `gtm_template_unlisted`, and an `awct`
tag carrying an extra parameter `foo` is refused `nested_path_unlisted`; a `meta.adset_create` whose
`promoted_object.pixel_id` is another business's pixel computes `never`, and one carrying
`promoted_object.product_catalog_id` is refused `nested_path_unlisted`; a
`meta.adset_targeting_edit` carrying `targeting.connections` (and one carrying
`targeting.behaviors`) is refused `nested_path_unlisted`; a `meta.adset_create` whose
`targeting.flexible_spec[0].custom_audiences[0].id` equals a fixture `other_businesses` audience id
computes `never` at `propose`, and (L, fake Meta API) one whose id is unknown to the pack but whose
fake audience read reports another ad account fails `not_owned` at `execute` with zero writes; an
`after.value.targeting` dict on a row that does not declare `targeting` is refused
`nested_ids_undeclared`; a `gbp.hours_edit` with a `special_hours` entry and a `gbp.services_edit`
with a structured and a free-form service item pass the closure.

An `identity`/`identity_for`/`identity_in`/`tag_bucket`/`tag_id`/`email`/`listing`/`destination`/`own_domain`/`pack_phone`/`home_data`/`wp_gtm_user`
value that fails its kind (after stage-1 shape checks) makes the action class `never` and, like a `card_on_refuse: true` row, writes a `card` notice, so the
operator can add the value through a reviewed pack change (02_act.md §2.8 check 1). P2 test (A1):
a live `google_ads.ad_text_edit` whose `final_url` is `https://example-competitor.com/x`, a
`facebook.page_about_edit` whose `cta_url` is off-pack, and a `website_wordpress.redirect_add` whose
`to_url` is off-pack each compute class `never` with a card notice, and each passes once the host is
added to `identity_allowlist.domains`. **Required on every row except `any.object_read`,
NEVER rows and `crm.lead_append` (whose input is the §3.14 lead row, validated there):** `after_fields` (list of allowed top-level `after` keys) and, when it contains
`"value"`, `after_value_fields` (list of allowed `after.value` keys) — 02_act.md §2.8 check 10; the
tier-table validator (A1, P2 test) refuses a write row without them.

3.4.2 **Matching.** A row matches when its `(system, object_class, action)` triple equals the
proposal's, every `when` clause holds, and every `after_value_enums` clause holds (the proposal's
`after.value[<key>]` is present and in the list). First match in file order wins. **No match →
synthetic row**
`{"id": "_nomatch", "tier": "T4", "class": "money", "money": true, "public": true, "outward": true, "lanes_key": "nomatch"}`
(§20.6: no match is `$`). A `_nomatch` action without `new_absolute_value` is signed over its
`after_digest` (02_act.md §2.8 check 8, §3.7) — never refused for lacking an amount. `_nomatch` carries no
`after_fields` (check 10 does not apply: the whole `after` is signed). **Its `public: true` takes
the public lane set (FID-05; plan §6.5 "specialist lanes on every public item"; DECIDED HERE):**
`_nomatch` covers **unlisted actions on canonical systems** (e.g. a Meta campaign objective change,
an unlisted listing-text field) — content the operator's signature over a ≤ 400-char
`after_summary` does not review. **Unknown systems, templates and paths — three disclosed,
fail-closed deviations from plan §20.6 "no match → `$`" and ruling [122] "present for approval"
(DECIDED HERE; each names how the need still reaches the operator).** (a) **`system_unknown`**
(stage 1a): a system not in `CANONICAL_SYSTEMS` is never `_nomatch` — it has no grammar, connector,
runbook or pause namespace, so nothing could bind, execute or stop it. (b) **`gtm_template_unlisted`**
and (c) **`nested_path_unlisted`** (stage 1b, §3.4.1): a GTM tag template or a structured-value
path the tier table does not list carries ids no kind judges. Each is exit 3 with no event, **and
each writes one operator-visible notice** (never a silent exit 3): kind `task`, severity `warn`,
push, `dedupe_key` `table_gap:<slug>:<code>:<system>:<row id or "-">:<sha256 of the path or type,
first 12 hex>`, title "GTM proposal refused — the tier table has no row for it", whose body is
built by act.py only from validated tokens — the code, the proposal's `system` (rendered only when
it matches `^[a-z0-9_]{1,40}$`, else `(unrecognized)`), `object_class`/`action` (same test), the
matched row id, the unlisted template `type` or path pattern (same test per segment), the
`drafted_by` seat, and — when `after.new_absolute_value`/`after.unit` pass the §3.2 money-string
tests — the amount and unit; **never** `rationale`, `money_brief` or any other free text, so it is
safe on a hipaa pack. The notice states the two sanctioned routes: **a new paid channel** (e.g.
Microsoft Advertising, Nextdoor Ads, TikTok Ads) is re-proposed as **`vendor.subscription_create`**
(or `vendor.trial_start`) — slug account, `$`, operator-executed (§3.4.4 "Purchase rows") — with
`after.value.vendor` naming the platform, `plan` naming the budget line (e.g.
`"microsoft_ads:search_budget"`), and the proposed monthly ceiling as `USD/month`, so the channel-mix
budget proposal ruling [122] asks for is signed by the operator; and **a missing row, template or
path** is filed by the drafter as a `dept:marketing` finding asking for a reviewed tier-table change
(08_seats_wps.md findings route). An unknown system therefore never removes a planned channel
either: every channel plan §4.2/§11.2 names has at least one row, so its system is canonical and its
unlisted actions reach the operator as `_nomatch` `$` — in particular `linkedin` and `youtube`
(organic LinkedIn and YouTube Shorts, plan §4.2; activity-log systems, plan §11.2) carry the §3.4.4
rows, so e.g. a LinkedIn paid campaign action is `_nomatch`, never `system_unknown`. P2 tests (A1):
a OtherCompanyB proposal with `system: "microsoft_ads"` and a `$` budget shape exits 3
`system_unknown`, appends no event, and writes exactly one `task` notice naming `microsoft_ads`,
the amount and the `vendor.subscription_create` route (RED when the notice is removed); the same
budget as `vendor.subscription_create` with `vendor: "microsoft_ads"` reaches
`awaiting_approval`; a `cvt_12345` GTM tag writes the `table_gap` notice for
`gtm_template_unlisted`; a OtherCompany `system_unknown` notice contains none of the fixture's
`rationale` text (requests/03_schemas.md R83 → 02_act.md §2.4 `propose`, 07_notices_schedules.md
§7.1). For `_nomatch` content, `row_lanes.nomatch` =
`brand`, `claims_voice` (§3.5), plus `cta_link` when `after` carries a link, `video` by asset class
and `hipaa` on a hipaa pack (02_act.md §2.7), each by its lane's `public_reviewers`, all passing on
the current digest before `authorize` creates the approval request. `_nomatch` is never an urgent
runaway-spend stop, because **every** way of stopping or lowering paid delivery the department can
reach has an amount-only money row with `lanes_key: none` (§3.4.4 "Stop rows": Google Ads campaign
pause/budget, Meta campaign and ad-set pause/budget and the account spending limit, LSA account
pause/budget, listing paid pause/budget, boost stop, Thumbtack/Angi lead pause), so this review
needs no budget-state admission. A stop the table does not name is a table defect, fixed by a
reviewed tier-table change — never routed through `_nomatch` (and §3.2 "Enable actions" refuses a
`_nomatch` stop or status change on a budget object, `paid_object_use_money_row` /
`status_change_use_money_row`).
The §3.4.4 lanes test covers `_nomatch` as well as the table rows. 02_act.md §2.7 rules 1, 2 and 5
implement this paragraph (`makerchecker.required_lanes`; requests/03_schemas.md R4, landed).

3.4.3 **Effective class** (A1 `tiers.effective_class(ctx, action, row, check_failures) -> str`,
02_act.md §2.2b, which reads `check1` = `checks.identity_result(ctx, action)`, the structured result
of 02_act.md §2.8 check 1 — `{"failed": bool, "shared_hits": [{"where", "value"}]}` — never a
second, independent test): `never` if row class/tier is NEVER or
`check1.failed`; else `money` if `row.get("money", True)` is true or `spend_delta_monthly != 0` or
no match; else **`shared` iff `check1.shared_hits` is non-empty**; else `identity` if row class is
`identity`; else `auto`. **DECIDED HERE:** money outranks shared (the signature is the stronger
operator gate) — but the context a shared-system card exists to give is carried into the signature:
a money action with non-empty `check1.shared_hits` gets `display.shared_warning` (§3.7), which the
approver renders first and which `display_sha256` binds. **`shared_hits` — the closed test (DECIDED HERE):** check 1 records a hit for each
of these values that is not in `OWN` but **equals** a `shared_identifiers[].value` after the §3.22
per-system normalization (exact equality; hosts compared lowercased, equal or subdomain of a shared
host value; never a substring test): (a) `account_id`; (b) `target_ref`'s host; (c) every value of
`system_names.target_ids(system, target_ref)`; (d) every `id_fields` value of kind `identity`,
`identity_for:<key>`, `identity_in:<system>`, `tag_bucket:<b>`, `email`, `listing`, `destination`,
`own_domain` or `pack_phone`, looked up in `after.value` **and**
`before.value`, plus every value a `nested_id_paths` pattern or the tag-id scan (§3.4.1) judges by one of those kinds (so an `asset_link.target_id`, a `user_add.email` or an ad `final_url` naming a
shared value all count). A value that matches neither `OWN` nor `shared_identifiers` fails check 1
(class `never`), so a shared value can never be admitted silently as `auto`/`identity`. P2 tests
(A1): an `asset_link` whose `after.value.target_id` is a shared identifier (the CSA-production
Scout asset of the fixture) ends `awaiting_card`, not `held`/`authorized`; a `user_add` whose email
is a shared identifier computes `shared`; each goes RED when `effective_class` is reverted to
testing only `system`/`account_id`/`target_ref`.

3.4.4 **Required ids** (P2 test: each exists and has ≥ 1 test computing its tier/class). All §6.4 R9 ids
(`gbp.hours_edit, gbp.description_edit, gbp.services_edit, yelp.profile_text_edit,
angi.profile_text_edit, thumbtack.profile_text_edit, houzz.profile_text_edit,
nextdoor.profile_text_edit, bbb.profile_text_edit, apple.profile_text_edit, bing.profile_text_edit,
facebook.page_about_edit, instagram.page_about_edit, lsa.profile_text_edit,
website_wordpress.page_edit, website_wordpress.redirect_add,
website_wordpress.page_unpublish_with_301, gtm.workspace_edit, gtm.version_publish,
ga4.key_event_edit, ga4.data_filter_edit, search_console.sitemap_submit`), the reviewed-post ids
(`gbp.post_publish, facebook.post_publish, instagram.post_publish`), the schedule ids
(`gbp.post_schedule, facebook.post_schedule, instagram.post_schedule`), `crm.lead_append`,
`crm.status_update`, `website_static.page_edit` (T2, `lanes_key: web_page`, marketing paths only),
and these **explicit money rows** (`class: money`, `money: true`) enumerating §20.6's `$` list:
`gtm_ai.weekly_cap_edit` (unit `USD/week`, `account_id` ∈ {`opus`,`sonnet`} — the department's own
AI-spend caps, 04_hooks.md §4.6 step 3), `google_ads.auto_apply_enable`, `google_ads.campaign_budget_edit`,
`google_ads.campaign_enable`, `google_ads.campaign_pause`, `meta.spending_limit_edit`,
`meta.billing_edit`, `meta.payment_method_edit`, `meta.adset_budget_edit`,
`thumbtack.lead_area_edit`, `thumbtack.lead_category_edit`, `angi.lead_area_edit`,
`angi.lead_category_edit`, `call_tracking.number_purchase`, `sms_provider.a2p_10dlc_registration_create`,
`sms_provider.fee_plan_edit`, `domain_registrar.domain_purchase`, `domain_registrar.renewal_edit`,
`website_wordpress.plugin_purchase`, `stock_media.asset_purchase`, `vendor.trial_start` (any
card-required trial), `vendor.subscription_create`, `paid_api.usage_enable`, and — **removing or
stopping paid delivery** (plan §20.6 "enabling/pausing/**removing** a paid campaign or ad set";
DECIDED HERE) — `google_ads.campaign_remove`, `meta.campaign_remove`, `meta.adset_remove`,
`lsa.account_remove`, `L.paid_remove` (fields `$`, `after.new_absolute_value` = `"0.00"`, unit =
the object's budget period), plus `meta.campaign_enable`, `meta.adset_enable`,
`{thumbtack,angi}.lead_enable` (`commits_on_enable: true`), and the **stop rows** (DECIDED HERE;
plan §20.6 urgent runaway-spend cards — every stop reachable as an amount-only `$` row, never
`_nomatch`): `meta.campaign_pause`, `meta.campaign_budget_edit` (a CBO campaign's own budget),
`lsa.account_pause`, `L.paid_pause`, `{facebook,instagram}.boost_stop`,
`{thumbtack,angi}.lead_pause` (status rows: `after.new_absolute_value` = `"0.00"`, unit = the
object's budget period; `meta.campaign_budget_edit` is an ordinary amount row). **`meta.campaign_create`
and `meta.adset_create` are not money rows** (DECIDED HERE, following plan §20.13 "creating a
paused campaign with a budget stays T1 (money: false)"): they are T1 `auto`, created PAUSED (§3.2
"Paused creates"), and their budget is committed and signed only at `meta.campaign_enable` /
`meta.adset_enable`. Each money row above has a P2 test proving it computes `money` and is not
matched earlier by any other row; each stop row also has a P2 test proving it computes `money`
with an **empty** lane set and can be proposed with `money_brief.urgency: "urgent"` while
`PAUSE.budget` is present (no specialist dispatch needed) and through `propose --file`
(requests/03_schemas.md R40 adds the stop rows to 02_act.md §2.4's runaway-stop `--file` set). **Paid objects never go
through `object_delete` (DECIDED HERE):** the `{google_ads,meta,lsa}.object_delete` and
`L.object_delete` rows carry `after_value_fields [object_ref, object_type]` and
`after_value_enums: {"object_type": <the non-paid types for that system, §3.4.4 table>}`, so a
proposal naming `campaign`, `ad_set`/`adset`, `ad_account`, `account`, `paid_listing` or any
unlisted type does not match and falls to `_nomatch` (`$`); in addition `propose` refuses exit 3
`paid_object_use_money_row` when `system_names.target_ids(system, target_ref)` or `object_ref`
parses to a campaign, ad-set or account id, and the connector read / runbook before-check reads the
object's actual type immediately before the delete and fails `before_mismatch` (no write) when it
is not `after.value.object_type`. P2 tests (A1): a `google_ads.object_delete` with `object_type:
"campaign"` and a `meta.object_delete` with `object_type: "ad_set"` both compute `money`
(`_nomatch`); a `google_ads.account_settings_edit` with `setting: "auto_apply_recommendations"` and
one with `setting: "billing_setup"` both compute `money` (`_nomatch`), while `setting:
"auto_tagging_enabled"` computes `identity`; each goes RED when `after_value_enums` is dropped
from matching. **Every `class: money`
table row has `lanes_key: none`** (F-runaway; DECIDED HERE): its fields are an amount, a setting or a
signed list, the operator's signature over `after_digest` is the gate, and a
claims review of a number checks nothing — while a required review would leave an urgent
runaway-spend stop in `proposed` behind a checker dispatch that budget state denies (02_act.md §2.6).
This covers amount-only rows only (FID-05): the synthetic `_nomatch` row, whose `after` is
arbitrary content, takes the `nomatch` public lane set (§3.4.2), and a money-row proposal whose
`assets[]` is non-empty gets that same set added by `required_lanes` (02_act.md §2.7) — neither is
an urgent stop. **`lanes_key: none` is the static set, not always the effective one (DECIDED
HERE):** three per-action additions can give a money row lanes — (i)
the **content binding** of an enable that starts delivering ads or a paid profile, and of a boost
(§3.4.4 "Enabling ads"), which adds the `public_post` set when the delivered content is not
content-bound; (ii) `hipaa_on_regulated` on `{facebook,instagram}.post_boost` (§3.4.1), on a hipaa
pack; (iii) the asset rule above. (i) and (ii) never apply to a stop row (`"0.00"` or lowering,
`lanes_key: none`, no `hipaa_on_regulated`, never an enable), so a stop proposed with an empty
`assets[]` — as every urgent stop is — keeps an empty lane set, which is what the urgent-stop test
asserts.
Also required (F-setup; plan §20.6 "creating that company's own apps/API access" = identity,
§20.10 setup): the **account-setup rows** `meta.app_create`, `gbp.api_access_request`,
`google_ads.api_access_request` (non-secret steps, gtm-operator under write tickets) and
`meta.api_access_create`, `google_ads.api_access_create`, `website_wordpress.application_password_create`
(token capture, `setup_capture: true`, gtm-credential-setup under setup tickets), plus the inbound
email reply row `email.inquiry_reply_send` (plan §20.7), plus the **organic LinkedIn and YouTube
rows** (plan §4.2 social-media-strategist lane, §11.2 activity-log systems; DECIDED HERE):
`{linkedin,youtube}.post_schedule`, `{linkedin,youtube}.post_publish`,
`{linkedin,youtube}.comment_reply_publish`, `linkedin.page_about_edit`,
`youtube.channel_about_edit`, and their `user_add`/`user_role_edit`/`user_remove`/`object_delete`
identity rows (set rows below).

Conversion of the §6.3 lines per §20.6 (A1): budgets/enable/pause-campaign/raise/purchases →
`class: money`; keywords, negatives, ad copy/assets, audiences, bid targets inside the ceiling →
`class: auto, money: false`; deletions/name/primary category/NAP/roles/linking within the
company/messages to named people/app creation → `class: identity, money: false`. **T4 rows §20.6's
identity list does not name — conversion actions (`google_ads.conversion_action_*`),
`google_ads.account_settings_edit`, `website_wordpress.settings_edit`, `ga4.property_settings_edit`
/ `ga4.retention_edit`, plugin/theme install/update/remove, `search_console.removal_request_submit`
— are also `class: identity` (DECIDED HERE, F-identity):** each is either not trivially reversible
(a retention or removal request, a plugin install) or changes tracking integrity or account-wide
behaviour, which is exactly the "irreversible" half of §20.6's identity class; notify-then-execute
lets the operator cancel before it lands, while `auto` would not. **NEVER** rows
(`class: never`): cross-company linking (computed by check 1, not a row), Meta Business Portfolio
create/join (`meta.business_portfolio_create`, `meta.business_portfolio_join`, both
`card_on_refuse: true`), and Open Dental (§20.3; not a row — enforced by 02_act.md §2.8 check 1: a
`target_ref` host matching an applicable `phi_denylist` host/suffix is class `never`, so no system
name can route an Open Dental action to `_nomatch`; **and, DECIDED HERE, a `target_ref` — or any
`after.value`/`before.value` value of kind `destination`, `listing` or `own_domain`, or any
absolute `https` URL a `nested_id_paths` `opaque` leaf or `destination` leaf holds — that matches a
`phi_denylist.json` `url_prefixes` entry by the §3.20 match rule is class `never` with a card at
`propose` too**, so a PHI page on a host that is not itself denylisted is refused before
authorization rather than first at G-A or `connectors.http_request`; requests/03_schemas.md R84 →
02_act.md §2.8 check 1. P2 test (A1): a `website_wordpress.redirect_add` whose `to_url` continues a
fixture `url_prefixes` entry at a `/` boundary computes `never` with a card, and one whose path only
shares a prefix without the boundary does not; RED when the prefix clause is removed). **OtherCompany-only prohibitions are not NEVER rows** — rows are company-agnostic: the
`hipaa_prohibited` rows below keep their normal class for other packs, and 02_act.md §2.8 check 5 refuses
them only for `regulated ∋ hipaa` packs.

**The complete row list (F11; normative — `tier_table.json` holds exactly the rows of the table
below and no others; every money row named in the prose above is already one of its rows, at the
position the table gives it; file order = table order, first match wins, §3.4.2).** A set
`{a,b}.x` expands to one row per member (`a.x`, `b.x`), in the listed member order, at the set's
position; a cell naming several ids (`a.x`, `a.y`) expands in the order written. `L` = the eight listing systems `yelp,
angi, thumbtack, houzz, nextdoor, bbb, apple, bing`. Tier is informational under §20.6 except that
it fixes `public` (true for every T2, T2-review and `*.post_schedule` row, the four
`google_ads.*@paused` ad/asset rows and the two `meta.*@paused` ad rows, FID-09, and only those). **Outward** (§3.4.1) equals Public on
every row, except the rows whose Flags cell says **`outward`** — Public false, `outward: true` (the
complete list in §3.4.1); tier never decides `outward`. Class
`money` rows have `money: true`; every other row `money: false`. `when` is `{}` unless shown
(`cs` = `campaign_state`). Field shorthands: `TXT` = `after_fields ["text"]`; `TXTC` = `["text",
"caption"]`; `CAP` = `["caption"]` (the photo itself is an `assets[]` entry); `$` = `["new_absolute_value",
"unit"]`; `V(k,…)` = `after_fields ["value"]`, `after_value_fields [k,…]`; `TV(k,…)` = `["text",
"value"]` with value keys `[k,…]`; `P` = `["paths", "summary", "patch_sha256", "post_image"]`
(§3.2, FID-04); `R` = the inbox-reply form
`after_fields ["text", "template_id"]` (`template_id` is required — and `text` must equal the
template — only for hipaa packs, 02_act.md §2.8 check 5; other packs may omit `template_id`).
`ids(k, …)` = the row's `id_fields` (§3.4.1), each key of kind `in_account` unless written
`k:<kind>` (FID-02). `+CD` = the row's `after_fields` also hold the top-level key
`content_digest` (`"sha256:<hex>"`), **set by act.py at `propose`** from a content read and
never proposer-chosen (§3.4.4 "Enabling ads"; a supplied differing value → exit 3
`content_mismatch`, a supplied equal value is accepted, like `home_data`'s `source_sha256`), so
`after_digest`, every lane review and the §3.7 signature bind the content the action delivers.

| Row id(s) | Tier | Class | Public | lanes_key | when | Fields | Flags |
|---|---|---|---|---|---|---|---|
| `any.object_read` | T0 | auto | false | none | — (`action: read`) | — | the only `"*"` row |
| `google_ads.campaign_create` | T1 | auto | false | ads_internal | cs ∈ [paused] (= "will be created paused", §3.2 "Paused creates") | V(campaign_id, name, channel_type, budget_amount, bidding_strategy_type, geo_targets, language_targets, network_settings, start_date, end_date) | ids(campaign_id), `self_id: campaign_id` (absent/null in the proposal; G-A rule 7b learns the created id, mirroring `meta.campaign_create`); `hipaa_on_regulated: true` (§3.4.1); **`after_value_enums: {channel_type: [SEARCH]}`** (DECIDED HERE: the only campaign type whose serving content §3.4.4 "Enabling ads" models — Performance Max, Display, Demand Gen, Video and every other type does not match and falls to `_nomatch` `$` until the reader models it by a reviewed change); **always created with status PAUSED** — a row constant, not an `after` field: the connector `apply` sends it and the runbook `writes[...]` sets and re-reads it (§3.2 "Paused creates"); check 11 is met by that fixed status (no campaign exists to re-read); `verify_read` must observe `paused`, and a created campaign read back `live` fails verify with an immediate breaker `PAUSE.google_ads` and an `urgent` `runaway_spend` notice. Budget committed only at enable (§20.13): `budget_amount` is re-read and bound to the signed amount at `campaign_enable` (§3.2 "Enable actions", 06_connectors.md §6.2/§6.4); `nested_id_paths` for `network_settings`, `geo_targets`, `language_targets` as §3.4.1 |
| `google_ads.ad_group_create`, `google_ads.ad_group_edit` | T1 | auto | false | ads_internal | cs ∈ [paused] | V(campaign_id, name, default_cpc_bid) | ids(campaign_id) |
| `google_ads.ad_create@paused`, `google_ads.ad_text_edit@paused` | T1 | auto | **true** | **public_post** | cs ∈ [paused] | V(ad_group_id, ad_id, headlines, descriptions, final_url, path1, path2) | goes public as soon as its campaign (or ad group) is enabled, so it takes the public-item lane set when written, like `*.post_schedule` (FID-09; plan §6.5); `verify_read` records its `item_digest` so a later enable is content-bound only while the live content still equals what these lanes reviewed (§3.4.4 "Enabling ads"); `final_url` → CTA/link lane (F-cta); ids(ad_group_id, ad_id, final_url:destination); `ad_create*`: `self_id: ad_id`, `required_ids: [ad_group_id]` |
| `google_ads.asset_create@paused`, `google_ads.asset_edit@paused` | T1 | auto | **true** | **public_post** | cs ∈ [paused] | V(asset_id, asset_type, text, final_urls, phone_number, campaign_id) | image assets via `assets[]`; public-item lanes as above (FID-09); ids(asset_id, campaign_id, final_urls:destination, phone_number:pack_phone); `optional_ids: [campaign_id, final_urls, phone_number]`; `asset_create*`: `self_id: asset_id`; `after_value_enums: {asset_type: [headline, description, sitelink, callout, structured_snippet, call, business_name, image, logo]}` (any other type falls to `_nomatch`); **typed-key rule (DECIDED HERE):** `sitelink` requires non-empty `final_urls` and `call` requires `phone_number` (else `after_shape_invalid`, exit 3), and a URL or phone may ride only in those keys — `final_urls`/`phone_number` on any other type → `after_shape_invalid`, and check 2 still scans `text`. P2 test (A1): a sitelink asset whose `final_urls[0]` is off-pack computes `never` with a card; a call asset whose `phone_number` is not a pack phone computes `never`; a sitelink without `final_urls` is refused `after_shape_invalid`; each RED when its key or kind is removed |
| `google_ads.ad_create`, `google_ads.ad_text_edit`, `google_ads.asset_create`, `google_ads.asset_edit` | **T2** | auto | **true** | **public_post** | cs ∈ [live] | same as the `@paused` rows | live ad/asset text is public (plan §6.5 specialist lanes); ids as the `@paused` rows |
| `google_ads.keyword_add`, `google_ads.keyword_remove`, `google_ads.keyword_pause`, `google_ads.keyword_enable` | T3 | auto | false | ads_internal | cs ∈ [paused, live] | V(ad_group_id, keyword, match_type, cpc_bid) (`cpc_bid` only on `keyword_add`) | ids(ad_group_id); `keyword_add` and `keyword_enable`: `hipaa_on_regulated: true` (§3.4.1); `keyword_enable` re-enables a paused keyword within the campaign's signed ceiling (§20.13; never `_nomatch`, §3.2 "Enable actions") |
| `google_ads.negative_keyword_add`, `google_ads.negative_keyword_remove` | T3 | auto | false | ads_internal | cs ∈ [paused, live] | V(level, level_id, keyword, match_type) | ids(level_id) |
| `google_ads.bid_target_edit`, `google_ads.bid_strategy_edit` | T3 | auto | false | ads_internal | cs ∈ [paused, live] | V(campaign_id, bidding_strategy_type, target_type, target_value) | inside the signed ceiling; ids(campaign_id) |
| `google_ads.ad_pause`, `google_ads.ad_group_pause` | T3 | auto | false | ads_internal | cs ∈ [live] | V(ad_id, ad_group_id) | within-ceiling (§20.13); ids(ad_id, ad_group_id); `ad_group_pause`: `optional_ids: [ad_id]` (and `ad_id` must be absent) |
| `google_ads.ad_enable`, `google_ads.ad_group_enable` | T3 | auto | false | ads_internal | cs ∈ [paused, live] | V(ad_id, ad_group_id) +CD | the enable counterparts of the pause rows: within the campaign's signed ceiling (§20.13), `money: false`; ids and `optional_ids` exactly as the pause rows; **content binding (§3.4.4 "Enabling ads", below)** — autonomous only when the ad's current content is content a GTM action put there and verified, else the `public_post` lanes over the read content |
| `google_ads.audience_list_create` | T1 | auto | false | ads_internal | — | V(name, description, membership_days) | empty list only; `hipaa_on_regulated: true` (§3.4.1; trust-architect reviews on a hipaa pack — a list audience) |
| `google_ads.campaign_budget_edit`, `google_ads.campaign_enable`, `google_ads.campaign_pause`, `google_ads.campaign_remove` | T4 | money | false | none | — | $ (`campaign_enable`: $ +CD) | pause and remove = `"0.00"`; `campaign_enable`: `commits_on_enable: true` (FID-03) and **content binding** (§3.4.4 "Enabling ads") over every ad and asset the enabled campaign would serve — the `public_post` lanes (+ `hipaa` on a hipaa pack) whenever any of it is not content-bound |
| `google_ads.auto_apply_enable` | T4 | money | false | none | — | V(recommendation_types) | `amount_required: false` |
| `google_ads.conversion_action_create`, `google_ads.conversion_action_edit` | T4 | identity | false | tracking | — | V(conversion_action_id, name, category, counting, primary, value_settings) | `data_flow: true`; ids(conversion_action_id); `conversion_action_create`: `self_id: conversion_action_id` |
| `google_ads.account_settings_edit` | T4 | identity | false | none | — | V(setting, value) | `after_value_enums: {setting: [auto_tagging_enabled, descriptive_name, final_url_suffix]}` — call reporting has its own row (`google_ads.call_reporting_edit`, below); every other setting (auto-apply, billing, budget type, payments, tracking template, …) falls to `_nomatch` (`$`) |
| `google_ads.api_access_request` | T4 | identity | false | none | — | V(manager_customer_id, access_level) | `hold_minutes: 1440`; developer-token application (non-secret; runbook `writes[...]`); ids(manager_customer_id:identity) |
| `google_ads.api_access_create` | T4 | identity | false | none | — | V(app_name, scopes) | `hold_minutes: 1440`, `setup_capture: true` (OAuth client / developer token capture); `after_value_enums: {scopes: ["https://www.googleapis.com/auth/adwords"]}` (list-valued, judged per element, §3.4.1 — the one Google Ads API scope; any other scope, e.g. `cloud-platform` or a Drive/Gmail scope, does not match and falls to `_nomatch` `$`) |
| `google_ads.call_reporting_edit` | T4 | identity | false | tracking | — | V(setting, value) | `data_flow: true` (call reporting forwards calls through Google forwarding numbers and records call data — plan §20.5 "call-recording"; on a hipaa pack the `hipaa` lane with trust-architect as reviewer, who must cite the vendor's `baa_ref` or record that no PHI flows, §3.14); `after_value_enums: {setting: [call_reporting_enabled, call_conversion_reporting_enabled]}` |
| `google_ads.customer_match_upload`, `google_ads.audience_list_upload` | T4 | identity | false | tracking | — | V(list_id, source_ref, source_sha256, row_count) | `data_flow`, `hipaa_prohibited`; ids(list_id, source_ref:home_data); `source_sha256`/`row_count` set by act.py (§3.4.1 `home_data` "Byte binding") |
| `google_ads.offline_conversion_upload` | T4 | identity | false | tracking | — | V(conversion_action_id, source_ref, source_sha256, row_count) | `data_flow`, `hipaa_prohibited`; ids(conversion_action_id, source_ref:home_data); `source_sha256`/`row_count` set by act.py (§3.4.1 `home_data`) |
| `google_ads.enhanced_conversions_leads_enable` | T4 | identity | false | tracking | — | V(enabled) | `data_flow`, `hipaa_prohibited` |
| `lsa.profile_text_edit` | T2 | auto | true | listing_text | — | TXT | |
| `lsa.photo_upload` | T2 | auto | true | public_photo | — | CAP | |
| `lsa.lead_dispute_submit` | **T3** | auto | **false** | ads_internal | — | TV(lead_ref, reason_code) | a dispute is seen only by Google, not published (F-lsa); ids(lead_ref) |
| `lsa.budget_edit`, `lsa.account_enable`, `lsa.account_pause`, `lsa.account_remove` | T4 | money | false | none | — | $ (`account_enable`: $ +CD) | `account_enable`: `commits_on_enable: true` (FID-03) and **content binding** over the LSA profile content its ads are built from (§3.4.4 "Enabling ads"); `account_pause` and `account_remove` = `"0.00"` (stop rows) |
| `gbp.post_draft_create` | T1 | auto | false | public_post | — | TXTC | internal reviewers (not live) |
| `{gbp,facebook,instagram}.post_schedule` | T1 | auto | **true** | public_post | — | TXTC | native scheduler; check 4b at scheduling |
| `{gbp,facebook,instagram}.post_publish` | T2 | auto | true | public_post | — | TXTC | C1 rows |
| `gbp.photo_upload` | T2 | auto | true | public_photo | — | CAP | |
| `gbp.hours_edit` | T2 | auto | true | listing_text | — | V(mon, tue, wed, thu, fri, sat, sun, special_hours) | R9; `nested_id_paths` for `special_hours` as §3.4.1 |
| `gbp.description_edit` | T2 | auto | true | listing_text | — | TXT | R9 |
| `gbp.services_edit` | T2 | auto | true | listing_text | — | V(services) | R9; `nested_id_paths` for `services` as §3.4.1 |
| `gbp.qa_answer_publish` | T2 | auto | true | review_reply | — | R | `inbox_reply` |
| `gbp.review_reply_publish` | T2-review | auto | true | review_reply | — | R | `inbox_reply` |
| `gbp.additional_category_edit`, `gbp.primary_category_edit` | T4 | identity | false | listing_text | — | V(categories) | **`outward`** |
| `gbp.name_edit`, `gbp.address_edit`, `gbp.phone_edit` | T4 | identity | false | listing_text | — | V(name, address, phone) (the one key the row names) | **`outward`**; `gbp.phone_edit`: ids(phone:pack_phone); `address` a string (§3.4.1) |
| `gbp.api_access_request` | T4 | identity | false | none | — | V(gcp_project_id, use_case) | `hold_minutes: 1440`; Business Profile API application (non-secret; runbook `writes[...]`); ids(gcp_project_id:identity) |
| `{facebook,instagram}.comment_reply_publish` | T2 | auto | true | review_reply | — | R | `inbox_reply` |
| `{facebook,instagram}.page_about_edit` | T2 | auto | true | **listing_cta** | — | TV(cta_type, cta_url) | R9; CTA/link lane (F-cta); ids(cta_url:destination) |
| `{facebook,instagram}.dm_reply_send` | T4 | identity | false | email_sms | — | R | **`outward`**; `inbox_reply`, `hold_minutes: 30`, `recipient_required`, `lead_id_required` |
| `facebook.page_name_edit`, `instagram.profile_name_edit` | T4 | identity | false | listing_text | — | V(name) | **`outward`** |
| `{linkedin,youtube}.post_schedule` | T1 | auto | **true** | public_post | — | TXTC | native scheduler (LinkedIn Page scheduled post, YouTube scheduled publish); check 4b at scheduling; organic only (plan §4.2) |
| `{linkedin,youtube}.post_publish` | T2 | auto | true | public_post | — | TXTC | a LinkedIn Page post / a YouTube video or Short (the video is an `assets[]` entry, so 02_act.md §2.7 rule 3 adds the `video` lane by asset class) |
| `{linkedin,youtube}.comment_reply_publish` | T2 | auto | true | review_reply | — | R | `inbox_reply` |
| `linkedin.page_about_edit` | T2 | auto | true | **listing_cta** | — | TV(cta_type, cta_url) | the Page's about text and custom button; CTA/link lane (F-cta); ids(cta_url:destination) |
| `youtube.channel_about_edit` | T2 | auto | true | **listing_cta** | — | TV(link_urls) | channel description and links; ids(link_urls:destination) (list-valued) |
| `{facebook,instagram}.post_boost` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[targeting, duration_days]` +CD | a boost is paid distribution of an existing post; `current_value: zero`; `unit` ∈ {`USD/day`, `USD/once`}; `duration_days` an int 1–90 (else `after_shape_invalid`); `targeting` is the closed Meta targeting map of §3.4.1 `nested_id_paths` (so the audience is signed and reviewed, never picked at execution); `hipaa_on_regulated: true` (§3.4.1 — `healthcare_ads_policy` review on a hipaa pack); `object_scope: object` with a post-level `target_ref` only (`boost_post_required`, §3.4.1); **content binding** over the boosted post (§3.4.4 "Enabling ads") — a post not published by a verified GTM action with an equal `content_digest`, or edited since by an owner or outside actor, takes the `public_post` lanes (+ `hipaa` on a hipaa pack) |
| `{facebook,instagram}.boost_stop` | T4 | money | false | none | — | $ | stop row: `"0.00"`, unit = the boost's budget period; the boosted post is named by `target_ref` (`page/<id>/posts/<id>`, `ig/<id>/media/<id>`) |
| `meta.spending_limit_edit`, `meta.campaign_budget_edit`, `meta.adset_budget_edit`, `meta.campaign_pause`, `meta.adset_pause`, `meta.campaign_remove`, `meta.adset_remove` | T4 | money | false | none | — | $ | pause and remove = `"0.00"` (stop rows, with `meta.spending_limit_edit` and the two budget rows when lowering); `meta.campaign_budget_edit` is a CBO campaign's own budget |
| `meta.campaign_create` | T1 | auto | false | ads_internal | cs ∈ [paused] (= "will be created paused") | V(campaign_id, name, objective, special_ad_categories, budget_type, budget_amount, budget_period, bid_strategy, start_time, end_time) | **always created PAUSED** (§3.2 "Paused creates"; plan §20.13 — `money: false`, the budget is bound and signed at `meta.campaign_enable`); ids(campaign_id), `self_id: campaign_id`; `hipaa_on_regulated: true` (§3.4.1); `after_value_enums: {budget_type: [cbo, abo]}` (`budget_amount`/`budget_period` absent for `abo`, whose budgets live on its ad sets) |
| `meta.adset_create` | T1 | auto | false | ads_internal | cs ∈ [paused, live] (the **parent** campaign; the ad set itself is always created paused) | V(adset_id, campaign_id, name, optimization_goal, billing_event, bid_strategy, budget_amount, budget_period, targeting, promoted_object, start_time, end_time) | **always created PAUSED** (§3.2 "Paused creates"); budget signed at `meta.adset_enable`; ids(adset_id, campaign_id), `self_id: adset_id`, `required_ids: [campaign_id]`; `nested_id_paths` as §3.4.1 (`targeting`, `promoted_object` — both closed); `hipaa_on_regulated: true` (§3.4.1) |
| `meta.campaign_enable`, `meta.adset_enable` | T4 | money | false | none | — | $ +CD | `commits_on_enable: true` (FID-03) — the ceiling the created object carries (an ABO campaign: the sum of its active ad sets' budgets, §3.2 "Enable actions"); **content binding** (§3.4.4 "Enabling ads") over every active ad the enable would deliver |
| `meta.ad_create@paused`, `meta.ad_edit@paused` | T1 | auto | **true** | **public_post** | cs ∈ [paused] | V(adset_id, ad_id, name, page_id, primary_text, headline, description, link_url, call_to_action_type) | goes public when its ad set or campaign is enabled, so it takes the public lane set when written (FID-09, as the Google `@paused` rows), and `verify_read` records its `item_digest` for the enable's content binding (§3.4.4 "Enabling ads"); image via `assets[]`; the connector builds the creative from these fields — an existing creative id is never accepted, so every Meta ad's text is reviewed; ids(adset_id, ad_id, page_id:identity_in:facebook, link_url:destination); `ad_create*`: `self_id: ad_id`, `required_ids: [adset_id, page_id]`; `ad_edit*` replaces the ad's creative |
| `meta.ad_create`, `meta.ad_edit` | **T2** | auto | **true** | **public_post** | cs ∈ [live] | same as the `@paused` rows | live Meta ad text is public (plan §6.5 specialist lanes); ids as the `@paused` rows |
| `meta.ad_pause`, `meta.ad_enable` | T3 | auto | false | ads_internal | cs ∈ [paused, live] (`ad_pause`: [live]) | V(ad_id, adset_id) (`ad_enable`: +CD) | within the ad set's signed ceiling (§20.13), `money: false`; ids(ad_id, adset_id); `ad_enable`: **content binding** (§3.4.4 "Enabling ads", below) |
| `meta.adset_targeting_edit`, `meta.adset_bid_edit` | T3 | auto | false | ads_internal | cs ∈ [paused, live] | V(adset_id, targeting) / V(adset_id, bid_strategy, bid_amount) | audiences and bid targets inside the signed ceiling (§20.6 conversion); ids(adset_id); `nested_id_paths` for `targeting` as §3.4.1 (closed); `adset_targeting_edit`: `hipaa_on_regulated: true` (§3.4.1) |
| `meta.billing_edit`, `meta.payment_method_edit` | T4 | money | false | none | — | V(setting) | `amount_required: false` |
| `meta.custom_audience_list_upload` | T4 | identity | false | tracking | — | V(list_id, source_ref, source_sha256, row_count) | `data_flow`, `hipaa_prohibited`; ids(list_id, source_ref:home_data); `source_sha256`/`row_count` set by act.py (§3.4.1 `home_data`) |
| `meta.business_portfolio_create`, `meta.business_portfolio_join` | NEVER | never | false | none | — | — | `card_on_refuse: true` |
| `meta.app_create` | T4 | identity | false | none | — | V(app_name, app_type, use_cases) | `hold_minutes: 1440`; Meta app creation for this company only (non-secret; runbook `writes[...]`; never inside a Business Portfolio) |
| `meta.api_access_create` | T4 | identity | false | none | — | V(app_name, credential_kind, scopes) | `hold_minutes: 1440`, `setup_capture: true` (Page / system-user access-token capture); **least-privilege scopes (DECIDED HERE; plan §17 j, §20.10):** `after_value_enums: {credential_kind: [page_token, ads_system_user], scopes: [pages_show_list, pages_read_engagement, pages_manage_posts, pages_manage_engagement, pages_read_user_content, pages_manage_metadata, pages_messaging, instagram_basic, instagram_content_publish, instagram_manage_comments, instagram_manage_messages, ads_read, ads_management]}` (list-valued, per element); **typed-key rule:** `page_token` admits only the `pages_*`/`instagram_*` scopes and `ads_system_user` only `ads_read`/`ads_management` (a cross-kind scope → exit 3 `after_shape_invalid`); `business_management`, `catalog_management`, `leads_retrieval`, `whatsapp_*` and every other unlisted permission do not match the row and fall to `_nomatch` `$`. The permission names are **UNVERIFIED** against the current Graph API permissions reference: WP-A1 checks each before P2 and corrects the list by a reviewed tier-table change (a mis-named scope fails closed to `_nomatch`, never open) |
| `L.profile_text_edit` | T2 | auto | true | listing_text | — | TXT | R9 |
| `L.photo_upload` | T2 | auto | true | public_photo | — | CAP | |
| `L.review_reply_publish` | T2-review | auto | true | review_reply | — | R | `inbox_reply` |
| `L.paid_budget_edit`, `L.paid_enable`, `L.paid_pause`, `L.paid_remove` | T4 | money | false | none | — | $ (`paid_enable`: $ +CD) | `paid_enable`: `commits_on_enable: true` (FID-03) and **content binding** over the listing profile the paid placement shows (§3.4.4 "Enabling ads"); `paid_pause` and `paid_remove` = `"0.00"` (stop rows) |
| `{thumbtack,angi}.lead_area_edit`, `{thumbtack,angi}.lead_category_edit` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[areas]` / `[categories]` | the amount is the resulting pay-per-lead ceiling; the list is bound by the signed `after_digest` |
| `{thumbtack,angi}.lead_pause`, `{thumbtack,angi}.lead_enable` | T4 | money | false | none | — | $ (`lead_enable`: $ +CD) | `lead_pause` = `"0.00"` (stop row; unit = the account's pay-per-lead or budget period); `lead_enable`: `commits_on_enable: true` (the configured lead budget/cap) and **content binding** over the listing profile leads are bought through (§3.4.4 "Enabling ads"; DECIDED HERE — the same content as `L.paid_enable`) |
| `L.claim_submit` | T4 | identity | false | none | — | V(listing_url) | ids(listing_url:listing) (FID-02) |
| `L.nap_edit` | T4 | identity | false | listing_text | — | V(name, address, phone) | **`outward`**; ids(phone:pack_phone), `optional_ids: [phone]`; `address` a string (§3.4.1) |
| `website_wordpress.draft_create` | T1 | auto | false | web_page | — | TV(title, slug, post_type) | |
| `website_wordpress.page_edit`, `website_wordpress.post_edit`, `website_wordpress.page_publish`, `website_wordpress.post_publish` | T2 | auto | true | web_page | — | TV(page_ref, title, meta_title, meta_description, schema_jsonld) | safe-change protocol; `page_edit` is R9; ids(page_ref) |
| `website_wordpress.redirect_add` | T2 | auto | true | web_page | — | V(from_path, to_url, status_code) | R9; ids(to_url:destination) |
| `website_wordpress.page_unpublish_with_301` | T2 | auto | true | web_page | — | V(page_ref, redirect_to) | check 7 (Class O); ids(page_ref, redirect_to:destination) |
| `website_wordpress.plugin_install`, `website_wordpress.plugin_update`, `website_wordpress.plugin_remove`, `website_wordpress.theme_install`, `website_wordpress.theme_update`, `website_wordpress.theme_remove` | T4 | identity | false | none | — | V(slug, version) | `data_flow_on_hipaa: true` on the four install/update rows (§3.4.1): on a `regulated ∋ hipaa` pack every plugin/theme install or update — a pixel, chat, forms or booking plugin is invisible in a slug — requires the `measurement` and `hipaa` lanes with trust-architect as `hipaa` reviewer, who cites the vendor's `baa_ref` or records that no PHI flows (§3.14) |
| `website_wordpress.settings_edit` | T4 | identity | false | none | — | V(setting, value) | `after_value_enums: {setting: [blogname, blogdescription, timezone_string, date_format, time_format, permalink_structure, default_comment_status, blog_public]}` — `siteurl`, `home`, `admin_email`, `users_can_register`, `default_role` and every other option fall to `_nomatch` (`$`) |
| `website_wordpress.application_password_create` | T4 | identity | false | none | — | V(app_name, user_login) | `hold_minutes: 1440`, `setup_capture: true` (WordPress shows the password once); ids(user_login:wp_gtm_user) — only the pack's dedicated Editor user (§3.4.1), and the capture script aborts `before_mismatch` unless that user's role reads `editor` |
| `website_wordpress.plugin_purchase` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[plugin_slug, vendor, plan, product_id]` | purchase row (below); `current_value: zero`; ids(product_id:catalog_item); `optional_ids: [product_id]` |
| `website_static.page_edit` | T2 | auto | true | web_page | — | P | marketing paths only (check 9) |
| `gtm.workspace_edit` | T1 | auto | false | tracking | — | V(tags, triggers, variables) | `data_flow: true`; R9 |
| `gtm.version_publish` | T2 | auto | true | tracking | — | V(workspace_id, version_name) +CD | `data_flow: true`; R9; ids(workspace_id); **content binding** over every pending workspace change (§3.4.4 "Enabling ads" — `gtm.version_publish`): the `tracking` lane's `public_reviewers` (+ `hipaa` with trust-architect on a hipaa pack) review the read snapshot, and check 1's closure and tag-id scan run over it (a failure → class `never` with a card) |
| `ga4.key_event_edit`, `ga4.data_filter_edit`, `ga4.custom_dimension_edit` | T2 | auto | true | tracking | — | V(name, event_name, counting_method, is_key_event, filter_type, state, criteria, parameter_name, scope) | `data_flow: true`; first two are R9 |
| `ga4.property_settings_edit`, `ga4.retention_edit` | T4 | identity | false | tracking | — | V(setting, value) | `data_flow: true`; `after_value_enums: {setting: [display_name, time_zone, currency_code, industry_category]}` on `property_settings_edit`, `{setting: [event_data_retention, reset_user_data_on_new_activity]}` on `retention_edit` — every other setting (data sharing, Google signals, links, billing) falls to `_nomatch` (`$`) |
| `search_console.sitemap_submit` | T1 | auto | false | seo_internal | — | V(sitemap_url) | R9; ids(sitemap_url:own_domain) |
| `search_console.removal_request_submit` | T4 | identity | false | seo_internal | — | V(url, removal_type) | ids(url:own_domain) |
| `{email,sms}.template_edit` | T1 | auto | false | email_sms | — | TV(template_id, subject) (`subject` email only) | |
| `email.inquiry_reply_send` | T4 | identity | false | email_sms | — | `["text", "template_id", "subject"]` (hipaa packs: check 5 still admits only `text` + `template_id`) | **`outward`**; `inbox_reply`, `hold_minutes: 30`, `recipient_required`, `lead_id_required` — an email reply to an inbound inquiry (plan §20.7; F-email) |
| `{email,sms}.message_send` | T4 | identity | false | email_sms | — | TV(template_id, subject) | **`outward`**; `recipient_required`; `sms: true` on the sms row; on a `regulated ∋ hipaa` pack template-only (§3.2 "HIPAA message rows") |
| `{email,sms}.list_send` | T4 | identity | false | email_sms | — | V(list_id, template_id, send_at) | **`outward`**; `list_send: true` (quiet hours, SMS windows, per-member SMS consent and the CAN-SPAM checklist, §3.11, FID-13); `hipaa_prohibited`; `sms: true` on the sms row; ids(list_id) |
| `{email,sms}.audience_list_upload` | T4 | identity | false | tracking | — | V(list_id, source_ref, source_sha256, row_count) | `data_flow`, `hipaa_prohibited`; ids(list_id, source_ref:home_data); `source_sha256`/`row_count` set by act.py (§3.4.1 `home_data`) |
| `crm.lead_append` | T1 | auto | false | none | — | — (the §3.14 row, via `lead-append` only) | `propose` of this row is refused exit 3 `use_lead_append` (IMP-24), like read actions |
| `crm.status_update` | T1 | auto | false | none | — | V(lead_id, status) | `lead_id_required: true`; `after.value.lead_id` obeys the `LEAD_ID_RE` + own-slug rule and equals the top-level `lead_id` (§3.2 `recipient`) |
| `{google_ads,meta,gbp,facebook,instagram,ga4,gtm,search_console,website_wordpress,lsa,linkedin,youtube}.user_add`, `.user_role_edit` | T4 | identity | false | none | — | V(email, role) | cross-company → check 1/2; ids(email:email) (FID-02) |
| `{same set}.user_remove` | T4 | identity | false | none | — | V(email) | ids(email:email) — removing an address outside the pack's domains goes to the operator as a card (FID-02) |
| `{google_ads,meta,gbp,ga4,gtm,search_console}.asset_link` | T4 | identity | false | tracking | — | V(target_system, target_id, link_type) | `data_flow: true`; within the company only (check 1); ids(target_id:identity_for:target_system) (FID-02; 06_connectors.md §6.2 step 6) |
| `{gbp,facebook,instagram,website_wordpress,gtm,ga4,email,sms,linkedin,youtube}.object_delete` | T4 | identity | false | none | — | V(object_ref) | WordPress delete-without-redirect lands here; ids(object_ref) |
| `{google_ads,meta,lsa}.object_delete`, `L.object_delete` | T4 | identity | false | none | — | V(object_ref, object_type) | ids(object_ref); `after_value_enums: {object_type: …}` = `google_ads` [`ad`, `ad_group`, `asset`, `keyword`, `negative_keyword`, `audience_list`, `conversion_action`], `meta` [`ad`, `ad_creative`, `custom_audience`], `lsa` [`photo`, `review_request`], `L` [`photo`, `post`, `offer`, `project`] — a campaign, ad set, account or paid product never matches (falls to `_nomatch` `$`) and `propose` refuses `paid_object_use_money_row` when the target parses to one; the connector/runbook before-check re-reads the actual type (`before_mismatch` on any difference) |
| `gtm_ai.weekly_cap_edit` | T4 | money | false | none | — | $ | unit `USD/week`; `account_id` ∈ {`opus`, `sonnet`}; the only row admitting the signed report-only form `new_absolute_value: null` + `unit: "report_only"` (§3.2 "Money value strings", §3.7 null case iv; requests/07_notices_schedules.md R34) |
| `call_tracking.number_purchase` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[number_type, area_code, number]` | purchase row; `current_value: zero`; `area_code` or `number` required (one of them non-null, else `after_shape_invalid`) |
| `sms_provider.a2p_10dlc_registration_create` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[brand_name, use_case, plan]` | purchase row; `current_value: zero` |
| `sms_provider.fee_plan_edit` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[plan]` | purchase row |
| `domain_registrar.domain_purchase` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[domain, years]` | purchase row; `current_value: zero`; `domain` a lowercase bare host (not yet the company's, so no `own_domain` kind — check 2 still refuses another business's name in it) |
| `domain_registrar.renewal_edit` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[domain, auto_renew, years]` | purchase row; ids(domain:own_domain) |
| `stock_media.asset_purchase` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[provider, asset_id, license]` | purchase row; `current_value: zero`; ids(asset_id:catalog_item) |
| `vendor.trial_start`, `vendor.subscription_create` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[vendor, plan, product_id]` | purchase rows; `current_value: zero`; ids(product_id:catalog_item); `optional_ids: [product_id]` |
| `paid_api.usage_enable` | T4 | money | false | none | — | `["new_absolute_value", "unit", "value"]` with value keys `[api, plan]` | purchase row; `current_value: zero` |

Anything not listed — e.g. a Meta campaign objective change, a Meta ad-set schedule edit, or any
other structure edit the Meta rows above (campaign/ad-set create, enable, pause, remove, budget,
targeting and bid; ad create, edit, pause and enable) do not name — is `_nomatch` (`$`) until a
reviewed tier-table change adds a row; that is the plan's "no match → T4" rule, not an omission.
**Deviation check (stated):** Meta ad copy, audiences and bid targets inside the signed ceiling are
autonomous (`auto`, `money: false`), and a paused Meta campaign/ad set is created T1 with its
budget bound at enable — exactly plan §20.6/§20.13, mirroring Google Ads; no Meta work that the
plan makes autonomous is routed to `_nomatch`. P2 tests: every row id above
exists (incl. the six account-setup rows and `email.inquiry_reply_send`); every `public: true` **or
`outward: true`** row's lanes resolve (via `required_lanes`) to **at least one** lane,
and every such lane's `public_reviewers` are specialists only (no `gtm-checker`, plan §6.5);
**outward (DECIDED HERE, §3.4.1):** a `gbp.name_edit` and an `email.inquiry_reply_send` whose every
lane was reviewed only by gtm-checker are refused at `authorize` (`review_missing`), and pass once
the specialists review; a OtherCompany `email.message_send` (and `sms.message_send`) requires the
`hipaa` lane; each goes RED when the reviewer choice is reverted to `row.public` alone;
**self ids:** a `google_ads.ad_create` with `ad_id` absent and a valid `ad_group_id` passes check 1
with no `not_owned` resolution of `ad_id`, the same proposal with `ad_group_id` absent is refused
`id_field_missing`, and a `google_ads.ad_text_edit` with `ad_id` absent is refused
`id_field_missing`; every write row
carries `after_fields`; `google_ads.ad_text_edit` with `campaign_state: "live"` **and**
`google_ads.ad_text_edit@paused` with `campaign_state: "paused"` require the
`brand`, `claims_voice` and `cta_link` specialist lanes (FID-09); `_nomatch` resolves to at least
`brand` and `claims_voice`, reviewed by specialists (FID-05); **named assertion
`lanes_nomatch_link_includes_cta_link`:** a `_nomatch` action whose `after` carries
`https://…` resolves to a set that includes `cta_link` (public reviewer conversion-architect);
**named assertion `lanes_money_row_with_asset_gets_nomatch_set`:** a `class: money` table row whose
proposal has a non-empty `assets[]` resolves to at least `brand` + `claims_voice` (each goes RED
when 02_act.md §2.7 rule 5's `_nomatch` clause or rule 2 is reverted); every
`*settings_edit` row carries `after_value_enums` for `setting`; every row's `id` equals
`tiers.row_id` of its triple and `tiers.row_triple` inverts it, including both exceptions (IMP-02);
every id-typed `after_value_fields` key is in the row's `id_fields` (FID-02); an `asset_link` whose
`target_id` is not a pack identity value, one with `target_system: "ga4"` whose `target_id` is the
pack's own Google Ads customer id (an identity value, but not a `ga4` one — RED when
`identity_for` is reverted to `identity`), and a `user_add` whose email domain is not the pack's,
compute class `never` (FID-02); every write row carries `object_scope` equal to the §3.4.1 rule's
value (FID-02); every `commits_on_enable` row is `class: money`, action `enable`,
fields `$` +CD (FID-03; `+CD` on every one of them, §3.4.4 "Enabling ads"); a
`linkedin.post_publish` and a `youtube.post_publish` require the `public_post` specialist lanes (a
OtherCompany one also `hipaa`), and a `linkedin` `ad_campaign`/`create` proposal computes `money`
through `_nomatch` — neither is refused `system_unknown` (RED when the rows are removed); **every row whose `after_value_fields`
contains a `cta_*` key or a `*_url` key resolves to a lane set that includes `cta_link`** (F-cta),
except the identifier fields `listing_url` (`L.claim_submit`) and `sitemap_url`
(`search_console.sitemap_submit`), which name the object acted on rather than a destination link;
every `*_url`, `to_url`, `redirect_to` and `url` key has an `id_fields` kind of `destination`,
`own_domain` or `listing`; every create row with an own-object id key names it in `self_id`;
every `class: money` row has `lanes_key: none`; every row with `setup_capture: true` is `class:
identity`, `money: false`, and has an `allowlist.json` script whose `system` equals the row's
system (E, checked once E lands).

**Account-setup rows (F-setup; plan §20.6, §20.10).** The non-secret rows (`meta.app_create`,
`gbp.api_access_request`, `google_ads.api_access_request`) execute like any identity row: hold →
run-holds releases to `authorized` → `ticket --write` → gtm-operator. WP-L authors their runbook
entries: `writes["meta.app_create"]` in `meta_ads.runbook.json` (L2), `writes["gbp.api_access_request"]`
in `gbp.runbook.json` (L2), `writes["google_ads.api_access_request"]` in `google_ads.runbook.json`
(L1), and — for service-account grants on GA4, GTM and Search Console, which use the existing
`{ga4,gtm,search_console}.user_add` rows — `writes["ga4.user_add"]`, `writes["gtm.user_add"]`,
`writes["search_console.user_add"]` (L1). The capture rows (`setup_capture: true`) are never
ticketed with `--write`; `ticket --setup` (02_act.md §2.4) accepts only them, and their browser steps are
the allowlisted capture script (06_connectors.md §6.6), not runbook `writes`. `account_id` on every setup row is the
pack account or identity value the access is created for (check 1 applies unchanged).

**Purchase rows (DECIDED HERE; the rows the table marks "purchase row").** (1) **The object is
signed.** Each carries `["new_absolute_value", "unit", "value"]` with value keys naming what is
bought (domain, plugin, number, asset, plan, vendor, API), so the signed `after_digest` binds the
object, `dispatch_brief.steps` can be filled from those keys, and §3.7 `display.object_ref`
lists every value key of a purchase row (`key=value`), so `display_sha256` binds them too; check 2
runs over every value. (2) **`account_id` (requests/03_schemas.md R41 → 02_act.md §2.8 check 1):**
`call_tracking` and `sms_provider` rows need a pack `accounts[]` entry for that system (the vendor
account the number or registration lives in), and check 1(a) applies unchanged. `vendor`,
`domain_registrar`, `stock_media` and `paid_api` rows — where the first purchase precedes any
account — carry **`account_id` = the pack slug**, and check 1 replaces (a)–(c) for them with
"`account_id` equals `ctx.company`" (like `gtm_ai`'s exception), while (d) still judges their
`id_fields`; brand binding is satisfied by a valid `brand` alone for these systems, and
`PAUSE.<system>@<b>` covers them by `brand` (or a null brand). (3) **Never agent-executed yet:**
no connector or runbook serves a purchase row today, so `execute` and `ticket --write` refuse them
`not_agent_executable` (02_act.md §2.4) and the operator executes them (`record-external --kind
owner_executed`). A later runbook `writes[<purchase row>]` entry is admitted only by a reviewed
tier-table revision that keeps (1) — the runbook validator refuses a `writes` entry whose
placeholders use a key outside the row's value keys. P2 tests (A1): each purchase row computes
`money` (the slug-account rows with `account_id` = the pack slug; a `call_tracking.number_purchase`
with no `call_tracking` account computes `never`); a `stock_media.asset_purchase` whose
`display.object_ref` omits `asset_id` fails the §3.7 display test; each goes RED when its clause is
reverted.

**Plugins (DECIDED HERE):** a paid plugin (any price, or a card required) is
`website_wordpress.plugin_purchase` (`$`, §20.6); a free plugin install is
`website_wordpress.plugin_install`, `class: identity` (T4 per §6.3/§17 — an install changes site
code and is not trivially reversible). A "free" install whose proposal carries
`spend_delta_monthly ≠ 0` is `money` anyway (§3.4.3).

**Enabling ads — the content binding (DECIDED HERE; plan §6.5 "specialist lanes on every public
item", §20.5 `hipaa` on every OtherCompany public item, §20.9/§20.13 outside actors).** A signature
over an amount, or an autonomous within-ceiling enable, reviews no ad text — yet enabling a paused
campaign publishes every ad under it, including ads GTM never wrote (e.g. the paused CSA Google Ads
campaigns an earlier builder made) and ads an owner or Agency edited after GTM's review. So every
**delivering action** — one that starts showing ad or profile content to the public — is bound to
the content it delivers, and is autonomous (or lane-free under its signature) **only** when every
piece of that content is exactly what a GTM specialist review passed.

| Delivering row(s) (each `+CD`) | Content set read (the **items**) |
|---|---|
| `google_ads.ad_enable` | the ad |
| `google_ads.ad_group_enable` | every ad of the group whose own status is enabled, and every enabled asset linked at the ad-group level |
| `google_ads.campaign_enable` | every ad whose own status **and** whose ad group's status are enabled, and every enabled asset the campaign would serve (linked at the account, campaign or one of those ad groups) |
| `meta.ad_enable` | the ad |
| `meta.adset_enable` | every ad of the ad set whose own status is active |
| `meta.campaign_enable` | every active ad of every ad set of the campaign whose own status is active |
| `lsa.account_enable` | the LSA profile the ads are built from |
| `L.paid_enable`, `{thumbtack,angi}.lead_enable` | that account's listing profile |
| `{facebook,instagram}.post_boost` | the boosted post |
| `gtm.version_publish` | every pending change of the workspace against the container's live version (tags, triggers, variables — added, updated and deleted) |

**Item content keys** (the closed sets `canon` is taken over): **ad** — Google (type
`RESPONSIVE_SEARCH_AD` only): `headlines`, `descriptions`, `final_url`, `path1`, `path2`; Meta
(creative forms: single image or single video link ad built from the §3.4.4 `meta.ad_*` fields):
`primary_text`, `headline`, `description`, `link_url`, `call_to_action_type`, `page_id`, and the
creative's `image_hash` or `video_id` (whichever the creative carries; the other key null);
**asset** (Google, `asset_type` ∈ the `google_ads.asset_create` enum only) — `asset_type`, `text`,
`final_urls`, `phone_number`, the image hash; **profile** — business name, profile / description
text, service list, website or CTA URL, phone, photo hashes (never reviews, ratings or messages);
**post** — text or caption, link URL, media hashes; **gtm entity** (`gtm.version_publish`) —
`entity_type` (`tag|trigger|variable`), `change_status` (`added|updated|deleted`) and `body` = the
entity resource as the GTM API returns it minus the volatile keys `fingerprint`, `path`,
`tagManagerUrl`, `workspaceId` (null for a deletion); **targeting** (hipaa packs only, below) —
`criterion_type` and `criterion` as read. `item_digest = "sha256:" + sha256(canon({"kind", "id",
<the content keys>}))`; the action's **`content_digest`** = `"sha256:" + sha256(canon(<the list of
{kind, id, item_digest}, sorted by (kind, id)>))` — the `after.content_digest` of `+CD`.

**The reader fails closed (DECIDED HERE; plan §6.5 specialist lanes on every public item, §20.5
`hipaa` on every OtherCompany public item).** Each read op returns, beside the items, a
**`serving` inventory**: every ad, asset, asset group, creative and asset container the enabled
object would serve, each with its **type** (for Google: the campaign's `advertising_channel_type`,
every ad's `ad.type`, every linked asset's `asset.type` and field type, and every asset group; for
Meta: every active ad's creative form — single image, single video, carousel, dynamic/Advantage+
creative, catalog, instant experience). act.py then refuses exit 3 **`ad_content_unreadable`**
(retryable in form, no event) — never an empty or partial item list — when (i) any inventory entry's
type is outside the modelled set above (a Google campaign whose channel type is not `SEARCH`, a
Performance Max asset group, a responsive display, Demand Gen, video, call or app ad, an asset type
outside the enum, e.g. `LONG_HEADLINE`, video, lead form, price, promotion; a Meta carousel,
dynamic, catalog or instant-experience creative), (ii) the inventory is absent from the read
result, or (iii) the item list is **empty** while the target is a campaign, ad group or ad set (an
enable that would deliver ads must show at least one ad; "hashes the empty list and is
content-bound" applies only to `gtm.version_publish` with no pending change, where publishing
changes nothing live). The operator (or a reviewed reader extension) handles an unmodelled type;
the enable is never content-bound over content GTM did not read (requests/03_schemas.md R85 →
06_connectors.md §6.2, 02_act.md §2.4).

**Targeting items on hipaa packs (DECIDED HERE; §3.4.1 `hipaa_on_regulated` "Enables on a hipaa
pack").** On a `regulated ∋ hipaa` pack the read of `google_ads.ad_group_enable` /
`.campaign_enable` also returns, as items of kind `targeting`, every enabled keyword
(`criterion_type: keyword`, `criterion: {text, match_type}`) and every enabled audience, user-list,
demographic and location criterion at the campaign and ad-group levels the enable re-activates; for
`meta.adset_enable` / `meta.campaign_enable`, one item per ad set that would deliver
(`criterion_type: adset_targeting`, `criterion` = its full targeting spec). A targeting item is
content-bound under the same rule as an ad (below), its writers being `google_ads.keyword_add`
(keyword), `google_ads.campaign_create` (its `geo_targets`/`language_targets`) and
`meta.adset_create` / `meta.adset_targeting_edit` (ad-set targeting). A targeting item that is not
content-bound adds **only** the `hipaa` lane (reviewer: trust-architect when the item is a user list
or custom audience, else local-presence-architect; checklist line `healthcare_ads_policy`) — never
the `public_post` set, since targeting is not public content. On other packs targeting items are
not read. **Reads:** API accounts through the connector read ops `ad_content(target_ref)`
(`google_ads`, `meta`; for a campaign, ad-group or ad-set target it returns every item of the set
above with its status), `profile_content(target_ref)` (`lsa`, `L` systems) and
`post_content(target_ref)` (`facebook`, `instagram`) and `workspace_content(target_ref)` (`gtm`:
the GTM API workspace status — the workspace's changes against the live version — with each
changed entity's full resource; requests/03_schemas.md R85) — requests/03_schemas.md R67 →
06_connectors.md §6.2; each returns the `serving` inventory above; browser accounts from a snapshot
named `ad_content`, `profile_content`, `post_content` or `workspace_content`, admitted by exactly
the §3.2 `committed_ceiling` snapshot contract (per-object file
name, this run's `snapshot_recorded` event, `ts` ≤ 24 h, `account_id` and `target_ids` equal). For
an API read act.py itself records the read result as that snapshot, so the review subject is always
a file; its home-relative path goes in `before.evidence_ref`.

**Content-bound.** An item is content-bound when the newest `verified` event of a GTM action that
wrote it — an ad: `google_ads.ad_create*`/`ad_text_edit*`, `meta.ad_create*`/`meta.ad_edit*`; an
asset: `google_ads.asset_create*`/`asset_edit*`; a profile: that account's
`lsa`/`<L>.profile_text_edit` or `.photo_upload` (whose `verify_read` digests the **whole** profile
after its write); a post: `{facebook,instagram}.post_publish`/`post_schedule` (verified once
published) — carries an equal `item_digest` in its data (`verify_read` computes it over the same
key set and 02_act.md §2.9 records it — requests/03_schemas.md R62 (a), widened by R67) **and** no
activity-log entry whose actor starts `outside:` or `owner`, and no action with `executed_by:
"owner"`, on that item's object (for a profile: on that account's system) is newer than that event.
The action is content-bound when every item is.

**`gtm.version_publish` (DECIDED HERE; plan §6.3 "version publish T2 (measurement lane
required)", §6.5 reviews bind the exact change, §20.9 co-managing Agency SaaS).** Publishing puts
the **whole** workspace live, including tags an owner or the co-managing Agency SaaS added, which
`gtm.workspace_edit` (T1, internal) never reviewed. So for this row: (1) `propose` reads
`workspace_content`, records the snapshot in `before.evidence_ref` and sets `after.content_digest`
over the pending-change items; (2) act.py runs check 1's **§3.4.1 `nested_id_paths` closure** —
the `gtm.workspace_edit` row's maps for `tags`, `triggers`, `variables` — and the **tag-id scan**
over every item's `body` (a deleted entity's `body` is null and is not scanned); any failure
(`gtm_template_unlisted`, `nested_path_unlisted`, an off-pack id, `tracker_id_unparsed`) makes the
action class **`never` with a card** (not an exit-3 refusal: the content is already in the
operator's workspace, so the operator must learn of it); (3) the row's `tracking` lane is reviewed
by its **`public_reviewers`** (the row is `public: true`) — plus `hipaa` with trust-architect on a
hipaa pack (`effective_data_flow`) — **over the snapshot**, never over `{workspace_id,
version_name}` alone, so the review binds the tags that will go live; an item whose `item_digest`
equals the `item_digest` recorded by a verified GTM `gtm.workspace_edit` (02_act.md §2.9 records
one per entity it wrote) and that no newer `outside:`/`owner` activity-log entry on the container
touches is marked content-bound in the review brief, so reviewers see which changes GTM's own
reviewed edits made and which it did not; (4) `authorize` re-reads (`content_changed` on a
difference) and `execute` re-reads immediately before the publish call (`before_mismatch`, no
publish). P2 tests (A1, fake GTM API; each RED when the binding is removed): a workspace holding an
outside-added custom-HTML tag `fbq('init','<other business pixel>')` makes `gtm.version_publish`
class `never` with a card; a workspace holding an outside-added `awct` tag with the pack's own
conversion id requires the `tracking` lane from measurement-architect and `authorize` refuses
`review_missing` until it passes over the snapshot; a tag added between `authorize` and `execute`
fails `before_mismatch` with zero publish calls; a workspace whose read reports an entity type
outside tag/trigger/variable (e.g. a custom template or a zone) is refused `ad_content_unreadable`.

**When and what (the one procedure; requests/03_schemas.md R67 → 02_act.md §2.4/§2.7, supersedes
R62 (b); `gtm.version_publish` follows its own paragraph above, and targeting items the "Targeting
items on hipaa packs" rule).** (1) **`propose`** reads the items (refusing `ad_content_unreadable`
per "The reader fails closed"), sets `after.content_digest`, and decides the lanes:
content-bound → the row's own lanes (`ads_internal` for the three auto rows, none for the money
rows); otherwise `required_lanes` adds the **`public_post`** set (`brand`, `claims_voice`,
`cta_link`), each taking its `public_reviewers`, reviewed over the snapshot, **plus `hipaa` on a
hipaa pack** (§3.4.1 `needs_hipaa`, `content_bound_lanes_added`) — stored in `lanes_required`, so
`authorize` refuses `review_missing` and creates **no approval request** until they pass on the
current digest. (2) **`authorize`** re-reads; a different `content_digest` → exit 3
**`content_changed`** (no event; the proposer supersedes with a fresh proposal, whose lanes are
decided again). (3) **`ticket --write` mint and `execute`** re-read immediately before the enable
(API accounts in the connector's `before` re-check; a browser mint through the API read when the
system has one, else a snapshot recorded after the action's `authorized` event) and fail
`before_mismatch` with no ticket and no write on any difference. A read that fails at (1) or (2) →
exit 3 **`ad_content_unreadable`** (retryable, no event); at (3) → `before_mismatch`. **Residual
(stated):** for a browser-executed enable, an owner edit between mint and the enable click is not
re-checked at the click (G-A rule 9d re-checks the ceiling only); it is bounded by the ticket's
lifetime and caught afterwards by the §3.23 reconcile.

P2 tests (A1, fake connector; each RED when the binding — or the named clause — is removed): a
paused `google_ads.campaign_enable` whose campaign holds one GTM-verified ad and one ad no GTM action
ever wrote requires `brand`, `claims_voice` and `cta_link` from specialists, and its `authorize`
refuses `review_missing` with no approval request written; the same with the second ad instead
GTM-verified but followed by a newer `owner…` activity-log entry on it requires the same lanes; the
same campaign with both ads GTM-verified and unchanged has `lanes_required == []` and `authorize`
creates the approval request; a OtherCompany `meta.adset_enable` holding one unbound ad also requires
`hipaa`; a content change between `propose` and `authorize` is refused `content_changed`, and one
between `authorize` and `execute` fails `before_mismatch` with zero enable calls; a supplied
`after.content_digest` that differs from the read is refused `content_mismatch`; an
`lsa.account_enable` whose profile text was last changed by an `outside:unknown` entry requires the
`public_post` lanes; a `facebook.post_boost` of an owner-published post requires them and one of a
GTM-verified post with an equal digest does not (on OtherCompanyB); enabling a paused ad whose last
change was an owner edit logged `outside:unknown` requires the specialist lanes; enabling one whose
content equals the `item_digest` of a verified GTM `ad_create@paused` stays `ads_internal`; an
`ad_group_enable` whose group holds one GTM-verified ad and one Agency-edited ad requires the
specialist lanes. **Fail-closed reader (each RED when the inventory test is removed):** a
`google_ads.campaign_enable` of a Performance Max campaign (fake read: channel type
`PERFORMANCE_MAX`, one asset group, zero ads) is refused `ad_content_unreadable` with no approval
request; a Search campaign whose read also lists one `RESPONSIVE_DISPLAY_AD` is refused the same
way; a campaign enable whose read returns no ads and no inventory is refused (never content-bound
over an empty list); a OtherCompanyB `meta.adset_enable` holding one single-video ad whose creative an
owner edited (`outside:unknown` entry newer than GTM's verify) requires the `public_post` lanes; a
Meta carousel creative in the ad set is refused `ad_content_unreadable`.

### 3.5 `review_lanes.json` (A1)

```json
{"schema": "gtm.review_lanes.v1",
 "lanes": {
  "brand":        {"public_reviewers": ["brand-architect"],   "internal_reviewers": ["gtm-checker", "brand-architect"], "checklist_ref": "knowledge/marketing_kb/brand/INDEX.md"},
  "claims_voice": {"public_reviewers": ["content-strategist"],"internal_reviewers": ["gtm-checker", "content-strategist"], "checklist_ref": "..."},
  "cta_link":     {"public_reviewers": ["conversion-architect"], "internal_reviewers": ["gtm-checker", "conversion-architect"], "checklist_ref": "..."},
  "seo":          {"public_reviewers": ["seo-architect"],     "internal_reviewers": ["gtm-checker", "seo-architect"], "checklist_ref": "..."},
  "video":        {"public_reviewers": ["video-producer"],    "internal_reviewers": ["gtm-checker", "video-producer"], "checklist_ref": "..."},
  "measurement":  {"public_reviewers": ["measurement-architect"], "internal_reviewers": ["gtm-checker", "measurement-architect"], "checklist_ref": "..."},
  "compliance":   {"public_reviewers": ["local-presence-architect", "revenue-ops-architect"], "internal_reviewers": ["gtm-checker", "local-presence-architect", "revenue-ops-architect"], "checklist_ref": "knowledge/marketing_kb/compliance/INDEX.md"},
  "hipaa":        {"public_reviewers": ["local-presence-architect", "trust-architect"], "internal_reviewers": ["local-presence-architect", "trust-architect"], "checklist_ref": "knowledge/marketing_kb/compliance/hipaa-marketing-for-practices.md"}
 },
 "row_lanes": {
  "none": [], "nomatch": ["brand", "claims_voice"], "ads_internal": ["claims_voice"],
  "listing_text": ["brand", "claims_voice"], "listing_cta": ["brand", "claims_voice", "cta_link"],
  "public_post": ["brand", "claims_voice", "cta_link"], "public_photo": ["brand", "claims_voice"],
  "review_reply": ["claims_voice", "compliance"],
  "tracking": ["measurement"], "email_sms": ["claims_voice", "compliance"], "web_page": ["brand", "claims_voice", "cta_link", "seo"],
  "seo_internal": ["seo"]
 }}
```
`review_lanes.local.json` has the same shape; lanes and row_lanes entries are unioned (add-only).
It is a pack file: read from the home's `HEAD`, never the working tree, and an uncommitted edit
refuses `pack_uncommitted` (02_act.md §2.2b `PACK_FILES`, §2.3; FID-07).
(The former `blog` key is dropped: no row used it; the P2 lanes test asserts every `row_lanes` key
other than `none` is used by at least one row or by `_nomatch`.) **Reviewer audience (DECIDED HERE,
§3.4.1 `outward`):** the allowed seats for a lane are its `public_reviewers` when `row.public or
row.outward`, else its `internal_reviewers` — so gtm-checker is a reviewer of record only on rows
that are neither public nor outward (plan §6.5), and every T4 name/NAP/category, DM/inquiry reply,
`message_send` and `list_send` action is reviewed by specialists. The `video` lane is never a
`row_lanes` entry: `required_lanes` adds it by asset class (02_act.md §2.7), and
adds `cta_link` to any public or outward row — `_nomatch` included (FID-05) — whose `after` text
carries a link (02_act.md §2.7 rule 5). It adds
`measurement` whenever the action's **effective** `data_flow` (§3.4.1) is true and the row's lane
set lacks it. No `class: money` table row uses a lane key other than `none` (§3.4.4); `nomatch`
is used only by the synthetic `_nomatch` row and by `required_lanes` for a money proposal carrying
assets (§3.4.2, FID-05); `required_lanes` also adds the `public_post` set to a delivering action
whose content is not content-bound (§3.4.4 "Enabling ads" — money enables and boosts included). (The former `ads_internal_cta` key is gone: the `@paused` ad rows now use
`public_post`, FID-09.)
**`review_reply` (FID-12; plan §20.6 supersedes O6):** `claims_voice` + `compliance` (+ `hipaa` on a
hipaa pack). On these public rows the reviewers are content-strategist (claims_voice, in a
dispatch separate from any drafting, 02_act.md §2.7(d)) and local-presence-architect (compliance,
and hipaa for content rows) — one dispatch per lane covering a whole inbox batch after the
gtm-checker pre-screen (07_notices_schedules.md §7.5 I8); gtm-checker alone never passes a reply.
The same holds for replies that go through `email_sms` (`{facebook,instagram}.dm_reply_send`,
`email.inquiry_reply_send`): those rows are `outward: true`, so their `claims_voice` and
`compliance` lanes take `public_reviewers` too.
A `public: true` or `outward: true` row whose `lanes_key` resolves to no lane would get no reviewer
at all; the §3.4.4 table has none, `_nomatch` has two, and the P2 lanes test (§3.4.4) fails on one.

### 3.6 Tickets (A2 writes/mints; G-A binds/decrements; ticket-release closes)

**Store protocol (every writer):** file `S/tickets/<slug>/<ticket_id>.json`; every read-modify-write
holds `fcntl.flock(LOCK_EX)` on `S/tickets/<slug>/.lock` (timeout 5 s; a hook that times out treats
it as a gate fault → deny for ticketed tools); writes are atomic replace. **Expiry (DECIDED HERE;
the one rule):** a ticket with `status ∈ {pending, bound}` whose `expires` has passed is treated as
`expired` by every reader, and the first writer under the lock persists `status: "expired"`. A
`stopped` ticket never expires by `expires`: it expires only at `stopped_at + 30 min` (the stop
grace, below), and readers then report it as `stopped-expired` (the persisted status stays
`stopped` until reconcile rewrites it). **Terminal statuses — `consumed`, `closed`, `abandoned`,
`expired` — are never rewritten by any writer** (a writer that finds one leaves the file
untouched; `--close` on one is the idempotent no-op below; reconcile only adds `reconciled: true`).
**`ticket --close` reconciles in-process (DECIDED HERE; no double outcome):** a `--close` that moves
a write/batch ticket to `abandoned` performs the reconcile steps itself in the same critical
section — appends `ticket_abandoned`, fails the action, releases or quarantines the nonce
(05_approver.md §5.5 step 5 "Release or quarantine") — and writes `reconciled: true`, so reconcile
never sees it again. Independently, reconcile skips every append whose effect is already recorded:
no `ticket_abandoned`/`failed` for an action whose folded state is already `failed`,
`completed`, `verified`, `verify_failed`, `reverted` or **`cancelled`** (a late cancel, §3.11), and no nonce op when the nonce's ledger
state is already `release` or `consume` (it then only sets `reconciled: true`). A2 test: `ticket
--close` on a stopped write ticket with `mutating_calls_used == 0` followed by a reconcile run yields exactly one
`ticket_abandoned`, one `failed` and one `release` line (with one mutating call and a `current_value:
zero` row: one `consume` line and one `nonce_quarantined` event instead) (RED when `--close` leaves `reconciled`
false and reconcile's skip is removed).

Common fields:
```json
{"schema": "gtm.ticket.v1", "ticket_id": "tkt_other-company_20260927T150405Z_a1b2c3", "class": "write",
 "company": "other-company", "session_id": "3f0c…", "run_id": "cyc_other-company_inbox_2026_09_27_1500",
 "status": "pending", "created_at": "…", "expires": "…", "bound_agent_id": null, "bound_agent_type": null,
 "bound_at": null, "allowed_hosts": ["business.google.com"], "allowed_tools": ["browser_navigate", "browser_click"],
 "calls_used": 0, "stopped_at": null, "closed_at": null, "close_reason": null, "reconciled": false}
```
**Counters (DECIDED HERE).** `calls_used` counts every tool call G-A admits under the ticket
(navigation included) and enforces `max_calls` on `read` and `setup` tickets. `mutating_calls_used`
counts only the calls G-A classifies as mutating (04_hooks.md §4.1) and enforces
`max_mutating_calls` on `write` and `batch` tickets; write/batch tickets carry no `max_calls` (their
non-mutating calls are bounded by the ticket's 30-minute life). `stopped_at` is set by the
SubagentStop release; `reconciled` by reconcile.
`status` — **one state machine per class (DECIDED HERE):**
- **read:** `pending` → `bound` → `closed` (SubagentStop release, or `ticket --close`) | `expired`.
- **write/batch:** `pending` → `bound` → `stopped` (the bound gtm-operator finished — SubagentStop
  fires **before** the parent session receives the Agent result — outcome not yet recorded) →
  `consumed` (via `complete`, from `bound` or `stopped`; action `completed`/`failed` per the
  outcome) | `abandoned` (`ticket --close` while `pending`/`bound`/`stopped`, or reconcile of a
  `stopped-expired` ticket; action `failed`, nonce released or quarantined) | `expired` (from
  `pending`/`bound` only; reconcile → action `failed`, nonce released or quarantined). **Late-cancel
  transitions (DECIDED HERE; §3.11 "Late cancels"):** a **write** ticket whose action's cancel
  marker is ingested goes `pending|bound → abandoned` when its `mutating_calls_used == 0` — in one
  critical section under the ticket lock: `status: "abandoned"`, `closed_at` = now, `close_reason:
  "late_cancel"`, `reconciled: true`, the nonce reservation released (a zero-call ticket is a proven
  no-write) with the release line written in that same section, and the action `cancelled` — and
  `bound → stopped` (`stopped_at` = now, `close_reason: "late_cancel"`) when it is ≥ 1, the outcome
  then recorded by `complete` (or by reconcile after the stop grace). A **batch** ticket always goes
  `pending|bound → stopped` with `stopped_at` = now (its other items still need `complete`), the
  cancelled item alone moving to `cancelled` when the ticket's `mutating_calls_used == 0`. A2 test:
  a late cancel on a `bound` write ticket with zero mutating calls, followed by a reconcile run
  after the 30-minute grace, yields the action `cancelled`, one `release` line and **no**
  `ticket_abandoned`/`failed` event (RED when the ticket is left `stopped` with `reconciled:
  false`, or when `cancelled` is missing from reconcile's skip list). **Release or
  quarantine (05_approver.md §5.5 step 5, the one rule; requests/05_approver.md R50):** the nonce is
  released only on a proven no-write failure (the ticket's `mutating_calls_used == 0`) or when the
  payload has a non-null `new_absolute_value` and the row's `current_value` is not `zero`; otherwise
  it is quarantined (`approvals_verify.quarantine`: a `consume` line plus a `nonce_quarantined` event,
  §3.9) and an urgent notice is written.
- **setup:** `pending` → `bound` → `stopped` (SubagentStop, exactly as write — a setup ticket is
  **never** closed by SubagentStop) → on `ticket --close` (which first runs the mandatory
  `secret_sink.py scan`, 06_connectors.md §6.6; a scan hit refuses the close and leaves the ticket
  `stopped` until the ROTATE path has run) → `consumed` when `S/secret_capture_hashes.jsonl` holds
  a row with this `ticket_id` (the action gets a `completed` event with `result: {"secret_name",
  "version"}`), else `abandoned` (action `failed`, reason `setup_not_captured`). `ticket --close`
  on a `pending`/`bound` setup ticket follows the same capture test. A setup ticket that reaches
  `expired` (from `pending`/`bound`) or `stopped-expired` is closed by reconcile running this same
  `--close` procedure in-process (scan included; a scan hit leaves it for the session and writes a
  `trust` notice). `secret_sink.py` stores only while the setup ticket is `pending` or `bound`
  (06_connectors.md §6.6 "open"; requests/03_schemas.md R29).

A `stopped` ticket is admissible **only** to `complete` (write/batch) or `ticket --close` (every
class) — never to G-A binding or tool admission — keeps its nonce reservation, and has its own
**stop grace** of `stopped_at + 30 min` (I18; independent of `expires`, so an operator that stops
at minute 29 still leaves the session 30 minutes to run `complete`); reconcile treats it as
abandoned only once that grace has passed (`ticket_status: "stopped-expired"`). A `stopped` ticket
**counts** toward the one-active-write-or-setup-ticket-per-company limit (it still holds a nonce
reservation and an unrecorded outcome), so the next write ticket waits for `complete` or the
grace. Every reader of ticket status (G-A, gate-gtm step 2, reconcile, `complete`, `ticket --show`,
GTM_Operator.html) handles `stopped`; gate-gtm's sequential rule counts only `bound`.
**`ticket --close` on a terminal ticket (IMP-13; DECIDED HERE; plan §6.7 "closing an
already-closed ticket is a no-op"):** a ticket already `closed`, `consumed`, `abandoned` or
`expired` → idempotent success, exit 0, `result: {"ticket_id", "already": "<status>"}`, nothing
written — the normal case for a read ticket the SubagentStop hook closed before the session's
`--close`. `stopped` is not terminal: `--close` on a write/batch one marks it `abandoned` and its
action `failed` (as above), so a session runs `complete` for an operator dispatch before any
`--close`; on a setup one it runs the setup close procedure above.

| Class | Extra fields | Minted by | Limits |
|---|---|---|---|
| `write` | `action_id, system, brand (the action's brand, or null), account_id, max_mutating_calls` (runbook step count, default 25), `mutating_calls_used, upload_assets [{path (absolute), sha256}], money (bool), nonce_reserved (str\|null), dispatch_brief` | `ticket --write <id>`; action must be `authorized`, not `held`/`cancelled`; PAUSE scope allows; every `upload_assets` entry is the **bound copy** of an action `assets[]` entry — `path` = `realpath(ST/assets/<action_id>/<sha256>)` (absolute, as G-A reads it), never the source `a.path` — re-verified at mint by `checks.rebind_assets` (02_act.md §2.8 check 4 "Asset binding": path containment, hash and provenance re-run on the copy; a failure → exit 3 `asset_path_forbidden` / `asset_sha_mismatch` / its provenance code, no ticket; requests/02_act.md item 85); money → signature verified at stage `mint` + nonce reserved (`ticket:<ticket_id>`), which requires the approval request's `expires − now` ≥ `MINT_MARGIN` (= `WRITE_TICKET_TTL` + 5 min = 35 min — the one named constant, defined in 05_approver.md's "Formats" header and used by its §5.5 step 5 `mint` row; verified to agree with this table, exit code included), else exit 7 `approval_expiring` (raised as `ActError(EXIT_APPROVAL, "approval_expiring")` by `approvals_verify.verify(stage="mint")`; requests/05_approver.md R47) with no ticket and no reservation (the operator re-approves a fresh request); `recipient_required`/`list_send` rows → the §3.11 send-time re-check passes (FID-24) | expires `WRITE_TICKET_TTL` = 30 min (the constant 05_approver.md §5.5 step 5 uses); **one active write-or-setup ticket per company** |
| `batch` | `action_ids [...], items [{action_id, status: pending\|completed\|failed}], system, brand, account_id, money: false, max_mutating_calls = steps × N, mutating_calls_used, upload_assets, dispatch_brief` | `ticket --write-batch a,b` — T1 `*.post_schedule`-class rows only, all `authorized`, same system+account; any named action whose `money` is not exactly `false` → exit 3 `batch_money_row`, no ticket (so `ticket_is_money`, which applies the plan §20.6 'money unless `money` is exactly `false`' rule to every class including `batch`, reads a batch ticket as non-money and `S/PAUSE.trust` never blocks a batch; 04_hooks.md §4; requests/04_hooks.md R16, R39) | same as write |
| `read` | `systems [...], max_calls (60 × len(systems))` ; `allowed_tools = ["browser_navigate", "browser_click", "browser_navigate_back"]` | `ticket --read --systems a,b` (T0, no authorize) | expires 10 min × systems, max 60 min; **one active read ticket per session** |
| `setup` | `action_id, system, brand, money: false, target_ids: {}, acting_as_expected` (the §3.6 `dispatch_brief` value for the action's brand; compared by `secret_sink.py` and `ticket --close --from-agent`, §3.21), `script_id, secret_name` (from the pack account's `credential_ref`, 02_act.md §2.4 — never from the allowlist), `max_calls 10`; `allowed_tools = ["browser_navigate", "browser_evaluate"]` | `ticket --setup --action <id> --script <script_id>`; the action is `authorized` and its row carries `setup_capture: true` (one of `meta.api_access_create`, `google_ads.api_access_create`, `website_wordpress.application_password_create`, §3.4.4 — identity class, plan §20.6 "creating that company's own apps/API access"), and the script's allowlist `system` equals the action's system | expires 15 min; counts as the company's write ticket |

**Binding fields of write/batch tickets (DECIDED HERE; requests/04_hooks.md R19–R21 — read by G-A,
04_hooks.md §4.1 rules 4s, 6b, 7b, 9c and 9d).** Every write ticket also carries:
- `action_class` — the action's class; when it is `shared` (a card-approved shared action, 02_act.md
  §2.6 rule 7), also `card_id` (the approving card, verified at mint through exactly
  `cards.require_approved(ctx, card_id, f"authorize {action_id}")` — the subject `card-post --action`
  binds, 02_act.md §2.4; a card answered under another subject → exit 3 `card_subject_mismatch`, any
  other failure → exit 3 `card_not_approved`, no ticket either way), `card_subject` (= `"authorize
  <action_id>"`, recorded at mint; G-A rule 4s requires `card_subject == "authorize " +
  ticket.action_id`, 04_hooks.md §4.1; requests/04_hooks.md R32) and `shared_values` (the
  normalized values of the action's `check1.shared_hits`, sorted). A non-shared ticket carries
  `action_class` only.
- `target_ids: {key: value}` = `system_names.target_ids(system, target_ref)` plus the check-1-verified
  `id_fields` values of the action (02_act.md §2.8 check 1), each normalized with
  `normalize_account_id`; for a create row also `self_id_key` (the row's `self_id`, §3.4.1) and
  `created_ids: {}` (G-A fills it, 04_hooks.md §4.1 "Rule 7b key classes"); `self_id_key: null`
  otherwise. A batch ticket carries the union of its items' `target_ids` and `self_id_keys` (a sorted
  list); a setup ticket `target_ids: {}`.
- `signed_amount` — on a **money** write ticket, the decimal string of the verified signed payload's
  `after.new_absolute_value`, copied at stage `mint`; null otherwise.
- `stop_exempt` (bool; written on every write ticket, true only when mint admitted a **stop action**
  under a breaker pause by the §3.10 stop-row exemption) — G-A rule 6b skips a breaker-written
  `PAUSE.<system>`/`PAUSE.<system>@<brand>` for a ticket with `stop_exempt: true` and for nothing
  else, and reads a missing field as false (requests/03_schemas.md R57).
- `commits_on_enable` (bool; the row's §3.4.1 flag, written on **every** write ticket — G-A treats a
  money ticket without it as enable-bound) and, when true, `budget_readback: {"value": "<decimal
  str>", "unit", "read_at": "<UTC ISO>", "via": "api", "target_ref"}` — the object's configured
  ceiling read by act.py immediately before minting through the connector read op
  `committed_ceiling` (06_connectors.md §6.2; the API, never the browser). Mint refuses exit 3
  `enable_budget_mismatch` (no ticket, no reservation) when the read value is not `Decimal`-equal to
  `signed_amount` or its unit differs from the signed unit, and exit 3 `enable_not_agent_executable`
  when the system has no API `committed_ceiling` read (the operator makes the change, recorded with
  `record-external --kind owner_executed`, plan §20.8). G-A rule 9d denies every mutating call on an
  enable-bound ticket whose read-back is absent, not `via: "api"`, outside `[created_at − 5 min,
  created_at]`, or unequal to `signed_amount`/unit (FID-03; requests/04_hooks.md R33, 04_hooks.md
  §4.1 "Enable binding on the browser path").
- `send_bound` (bool; true when the row — for a batch, any item's row — has `recipient_required` or
  `list_send`) and, when true, `send_not_after` (UTC ISO) = the minimum of `expires`, the next
  quiet-hours start for a named-person recipient (pack time) and the end of the current SMS send
  window for an SMS row (every item's, for a batch), computed at mint from the same inputs as the
  §3.11 send-time re-check. G-A rule 6b denies every mutating call at or after it
  (`outside-send-window`), reading a missing `send_bound` as true and a missing or unparsable
  `send_not_after` on a send-bound ticket as already passed, i.e. denied (FID-24; requests/04_hooks.md R34).
- `dispatch_brief.steps[]` entries each carry `value` (the filled string, or null for a step that
  enters nothing) and `value_kind ∈ {"text", "amount"}` — `amount` exactly when the step's
  placeholder is a money field of the row (`new_absolute_value`, a budget or bid field; the runbook
  step names the after-field it fills from, 06_connectors.md §6.4). Mint refuses exit 3
  `amount_mismatch` (no ticket, no nonce reservation) when any `amount` step's `value` is not
  `Decimal`-equal to `signed_amount`.
A2 tests: a shared action minted with an unapproved card → `card_not_approved`; a money
`campaign_budget_edit` whose runbook step would type `450.00` against a signed `45.00` →
`amount_mismatch` with no reserve line; a `google_ads.campaign_create` ticket carries `self_id_key:
"campaign_id"` and `created_ids: {}`; a card approved under subject `authorize act_x_2` does not mint
a shared ticket for `act_x_1` (`card_subject_mismatch`); a browser `google_ads.campaign_enable` signed
at `45.00` whose fake-API `committed_ceiling` reads `1000.00` → `enable_budget_mismatch` with no
reserve line; an `sms.message_send` ticket minted at 19:59 with quiet hours from 20:00 carries
`send_bound: true`, `send_not_after` 20:00; each RED when its clause is removed.

`allowed_hosts` = the runbook's `writes[<row>].allowed_hosts` (write/batch), union of the systems'
`read_hosts ∪ login_hosts` (read), the setup script's `target_hosts` (setup). `allowed_tools`
(write/batch) = the runbook's `writes[<row>].allowed_tools` (for a batch: the union over its rows,
all of which share one system), which the runbook validator (L) requires to be non-empty and ⊆ the
04_hooks.md §4.1 ticketed-tool set, and which `ticket --write` re-checks against that set (exit 3
`runbook_tools_invalid`); read and setup use the fixed lists in the table. `ticket
--read|--write|--write-batch` refuses (exit 3 `ticket_host_read_only`) when any `allowed_hosts`
entry equals, or is a subdomain of, an entry in `~/.claude/live-testing/allowlist.json`
`read_only_hosts` — `block_prod_mutations.py` R5 denies every click/type there for
`playwright-gtm` by design (04_hooks.md §4.9), so the failure surfaces at mint, not mid-run;
ticketless reads of those hosts are unaffected.
`dispatch_brief` (what the session pastes into the gtm-operator prompt, 08_seats_wps.md §8.3):
`{"ticket_id", "action_id" (write) | "action_ids" (batch, a list), "system", "account_id", "acting_as_expected", "before": <the action's before.value/before.text restricted to the row's field set (never evidence contents, never untrusted text)>, "steps": [...runbook steps with {placeholders} filled from the action's structured before/after/account fields — only keys in the row's after_fields/after_value_fields, 02_act.md §2.8 check 10], "after": <the action's after, restricted to the row's field set>, "upload_assets": [...], "verify": {...}}`.
For a batch, `before` is a map `{action_id: before}`. `acting_as_expected` (F-acting) = the pack's
`brands[<action.brand>].display_name` (the brand entry whose `id` equals the action's `brand`);
when the action's `brand` is null (single-brand packs only, §3.2 "Brand binding"),
`pack.display_names[0]`, or `pack.legal_name` when `display_names` is empty (company_schema.json
allows an empty list). It is the same string the runbook's
`{brand_display_name}` placeholder is filled with (06_connectors.md §6.4), so the `acting_as` expectation and the
isolation-hit comparison (§3.21 `act_complete`) use one value. The gtm-operator executes the runbook's
before-check step (06_connectors.md §6.4) and aborts with `reason: before_mismatch` when the on-page value differs —
the browser counterpart of the connector `before` re-check (06_connectors.md §6.2), so an owner or Agency change made
between propose and execution fails the action instead of being overwritten (§20.9).

**Binding (G-A):** a tool call that needs a ticket selects the candidate by the payload's
`agent_type`: `gtm-analyst` → `read`; `gtm-operator` → `write`/`batch`; `gtm-credential-setup` →
`setup`; any other agent type, or a payload with no `agent_id` (top-level session), gets **no**
ticket admission. Candidate = the single non-expired ticket of that class in
`S/tickets/<CLAUDE_GTM_COMPANY>/` with `session_id == payload.session_id` and status `pending` or
`bound`. `pending` → set `bound_agent_id/agent_type/bound_at`, `status: "bound"`; `bound` to a
different agent → deny `ticket-bound-to-other-agent`.

**Release (`gtm_ticket_release.py`, SubagentStop):** every ticket in `S/tickets/*/` with
`bound_agent_id == payload.agent_id` and status `bound`: read → `closed`
(`close_reason: "subagent_stop"`); write/batch/setup → `stopped` (`close_reason: "subagent_stop"`,
`stopped_at`). The hook never touches `actions.jsonl` or the nonce ledger (04_hooks.md §4.5,
requests/03_schemas.md R30).

**Reconcile (A2 `tickets.reconcile(ctx)`, run by `write`/`lead`/`repair` commands when the chain
verifies, 02_act.md §2.3):** for each write/batch ticket with `reconciled` not true whose status is
`abandoned`, `expired`, or `stopped` with `stopped_at + 30 min` in the past: append
`ticket_abandoned` → action `failed` (unless the action already has a terminal outcome recorded by
`complete`); release or quarantine its nonce reservation (§3.9; the rule above); set `reconciled: true` (and `status: "abandoned"`
for a stopped-expired one — the only rewrite of a non-terminal status reconcile performs). Setup
tickets are reconciled by the setup `--close` procedure above. A `stopped` ticket inside its window
is left alone.

Tests (A2 + B1): operator stops → `complete --ticket` succeeds (action `completed`, nonce consumed);
operator stops at minute 29 → `complete` at minute 45 still succeeds (and a reader at minute 45 sees
`stopped`, not `expired` — RED under a store rule that expires every status by `expires`); a
`consumed` ticket read after its `expires` stays `consumed`; setup: SubagentStop → `stopped`, then
`--close` with a capture row → `consumed` and the action `completed`, without one → `abandoned` and
the action `failed`; operator stops (no mutating call) → stop grace
passes → next write-policy command reconciles the action to `failed` and releases the nonce; a
second `ticket --write` while a `stopped` ticket is inside its grace → refused; `complete` with a
`--from-agent` other than `bound_agent_id` → exit 3; a money `ticket --write` at `expires −
(MINT_MARGIN − 1 min)` (= 34 min) → exit 7 `approval_expiring`, and at `expires − (MINT_MARGIN + 1
min)` (= 36 min) it mints (the same thresholds and exit code as 05_approver.md §5.5 step 5's test) — and that ticket, stopped at its minute 30 and completed at its minute 45 (after
`expires`), still completes, because stage `complete` tests the reserve line's `ts < expires`
instead of `expires > now` (05_approver.md §5.5 step 5; RED when `complete` tests `expires > now`).

### 3.7 Approval request (A2 writes `S/approval_requests/<slug>/<request_id>.json`)

Aligned with 05_approver.md §5.1/§5.5 (R10, R18; the app renders and verifies exactly this shape).
```json
{"schema": "gtm.approval_request.v1", "request_id": "apr_other-company_20260927T150405Z_9f8e7d",
 "company": "other-company", "action_id": "act_other-company_20260927_0007", "status": "pending",
 "urgency": "normal", "created_at": "2026-09-27T15:04:05Z",
 "display": {"title": "Raise Remodeling Search budget", "company_display": "OtherCompanyB Remodeling",
   "system": "google_ads", "account_id": "1002003000", "object": "Campaign 'Remodel – Search'",
   "object_ref": "customers/1002003000/campaigns/20000000001 (campaign_id=20000000001, customer_id=1002003000)",
   "current_value": "30.00", "new_absolute_value": "45.00", "unit": "USD/day",
   "spend_delta_monthly": null, "commits_on_enable": false,
   "metrics_summary": "...", "best_practice_source": "knowledge/marketing_kb/paid_acquisition/....md#claim-12",
   "expected_effect": "...", "risk": "...", "reversal": "set back to 30.00 (a new $ approval)",
   "after_summary": "{\"new_absolute_value\": \"45.00\", \"unit\": \"USD/day\"}",
   "after_full": "{\"new_absolute_value\":\"45.00\",\"unit\":\"USD/day\"}"},
 "display_b64": "<base64 of canon(display)>",
 "payload": {"v": 1, "company": "other-company", "card_id": "apr_other-company_20260927T150405Z_9f8e7d",
   "action_id": "act_other-company_20260927_0007", "system": "google_ads", "account_id": "1002003000",
   "new_absolute_value": "45.00", "unit": "USD/day", "after_digest": "sha256:…",
   "display_sha256": "<hex sha256 of the display_b64 decoded bytes>",
   "nonce": "6c1f…(32 hex)", "expires": "2026-09-30T15:04:05Z"},
 "payload_b64": "<base64 of canon(payload)>"}
```
- `card_id` = `request_id` (the approver list IS the card). **DECIDED HERE.** **Mirror card
  (aligned with 05_approver.md §5.1 step 5):** the session mirrors each request as a human card on
  the operator surface under the same id, posted with the subject `approval <request_id>`. Its
  answer is **informational for `$`**: an `approve` there never approves (act.py writes
  `S/approver_inbox/show.<request_id>` and an `info` notice "Approval needs Touch ID in
  GTMApprover"); a `deny` denies the request (a denial only prevents, `record-external --kind
  approval`); `unclear` changes nothing. Whether a `$` action may execute is decided **solely** by
  the §3.8 approval record and §3.9 nonce ledger.
- **Signed payload keys are exactly these 12** (05_approver.md §5.5 step 3a; the app refuses any
  other key set): `v, company, card_id, action_id, system, account_id, new_absolute_value, unit,
  after_digest, display_sha256, nonce, expires` — the plan's seven (`card_id, action_id, system,
  account_id, new_absolute_value, nonce, expires`) **plus** `v`, `company`, `unit`, `after_digest`,
  `display_sha256`. **DECIDED HERE:** `unit` prevents a daily/monthly confusion; `company`/`v` make
  the bytes self-describing; `after_digest` (the action's 02_act.md §2.7 digest) binds the
  signature to the exact change and is what an amount-less `$` action is signed over;
  `display_sha256` = `sha256(canon(display))` (hex) binds **what the operator saw** — including
  `display.object_ref`, the structured target — so a proposer's mislabelled `object` description
  cannot move the signature to another object: 3b recomputes `build_display(ctx, action)` and
  refuses any difference. `target_ref` therefore needs no separate payload key. 3b also requires
  `payload.new_absolute_value == action.after.new_absolute_value`, `payload.unit ==
  action.after.unit` and, for an enable action (§3.2 "Enable actions"), `payload.unit ==
  action.before.value.unit` (requests/05_approver.md R44).
- `display_b64` = base64 of `canon(display)`; the app decodes it, checks `sha256(decoded) ==
  payload.display_sha256`, and renders only from the decoded bytes (the plain `display` object is
  for `GTM_Operator.html`). For a regulated pack, untrusted-derived text in `display` is the §3.15
  pointer (05_approver.md §5.1 step 1).
- **`display` keys and their sources (every key; built only by
  `approvals_verify.build_display(ctx, action)`, deterministic):**

  | Key | Source |
  |---|---|
  | `title` | **The one derivation (DECIDED HERE; every renderer and 3b's recompute use it, since `display_sha256` binds it):** `label + " " + money_brief.object_display`, where `label` = `action.replace("_", " ").capitalize()` of the matched row's `tiers.row_triple(row_id)[2]` (`edit` → "Edit", `unpublish_with_301` → "Unpublish with 301"), and for `_nomatch` — which has no row — the fixed label "Change (no table row)" (an enable-type `_nomatch` included); the result is then cut to its first **120 Unicode code points** (a hard cut, no ellipsis, no whitespace trimming). A1 test: a `google_ads.campaign_budget_edit` with `object_display` "Campaign 'Remodel – Search'" yields "Edit Campaign 'Remodel – Search'", and a 200-character `object_display` yields exactly 120 code points |
  | `company_display` | `brands[<action.brand>].display_name`, else `pack.display_names[0]`, else `pack.legal_name` (the §3.6 `acting_as_expected` value) |
  | `system`, `account_id` | the action's `system` and `account_id`, **normalized** with `system_names.normalize_account_id` (§3.22; e.g. Ads customer ids digits only — never `100-200-3000`), equal to the payload values |
  | `object` | `money_brief.object_display` verbatim — labelled "description" by the app, never the binding identity |
  | `object_ref` | act.py-built: the action's `target_ref` followed by ` (` + each `system_names.target_ids(system, target_ref)` pair and each verified `id_fields` value of `after.value` — and, for a purchase row (§3.4.4 "Purchase rows"), every `after.value` key — as `key=value`, comma-separated, sorted + `)`; for a `target_ref: null` system, only the id list |
  | `current_value` | the folded `before.value.current_absolute_value` — for an enable action the value of the latest `ceiling_read` (§3.2 "Enable actions"), for a `current_value: zero` row `"0.00"`, otherwise the proposer's figure, bound at execution (§3.2 "Current value of other money actions") — or null for an amount-less action |
  | `new_absolute_value`, `unit` | `action.after.new_absolute_value` / `action.after.unit` — never the payload, so 05_approver.md §5.5 3b's `display_sha256` recompute is independent of the payload it checks (requests/05_approver.md R44) |
  | `spend_delta_monthly` | the proposal's `spend_delta_monthly` when the action is `money` **only** because it is non-zero on a `money: false` row (null case iii below), else null |
  | `resulting_status` | the matched tier row's authored `resulting_status` (§3.4.1) copied verbatim; **absent** for `_nomatch` and for a row that carries none (never `null`, never derived from verb tokens or `money_brief`). The approver's dialog variant (05_approver.md §5.1 step 3) and §5.8's requested state read it; added (wave1e) in place of the withdrawn `display.change_kind` (`requests/05_approver.md` R76 (b)) |
  | `commits_on_enable` | true for an enable action (§3.2 "Enable actions": a `commits_on_enable` row, or a `_nomatch` action on a budget object whose `action` tokens contain an enable token — the one predicate `tiers.is_enable_action(ctx, action, row)`); else false. Computed by A2 from the row flag / that predicate, never from `money_brief` |
  | `metrics_summary`, `best_practice_source`, `expected_effect`, `risk`, `reversal` | the same-named `money_brief` keys |
  | `after_summary` | `canon(after)` truncated to 400 chars (a heading only) |
  | `after_full` | the untruncated `canon(after)` text (05_approver.md §5.1 step 3) |
  | `shared_warning` | **present only** when the action is class `money` and `checks.identity_result(ctx, action).shared_hits` is non-empty (§3.4.3): `{"hits": [{"where", "value", "relationship", "ruling_ref", "paused_by"?}]}` — each hit with the `relationship` and `ruling_ref` of the matching `shared_identifiers[]` entry, and `paused_by` (the pause file name) only when that entry's `pause_names` names a present pause (§3.10), sorted by `(where, value)`; absent otherwise (never `null`). The approver renders it **first**, above the title, as "This change touches a shared or other-company system"; it is inside `display`, so `display_sha256` binds it (requests/03_schemas.md R42 → 05_approver.md §5.1/§5.5 3b) |

  **Regulated packs (`regulated ∋ hipaa`; DECIDED HERE — the values the table above yields there,
  byte-stable because `build_display` only copies stored values and never reads the side store):**
  the six free-text `money_brief` keys are stored in the action as `{digest, pointer}` objects
  (§3.1), so `object`, `metrics_summary`, `best_practice_source`, `expected_effect`, `risk` and
  `reversal` are each **that stored `{"digest", "pointer"}` object, copied verbatim** (never the
  text read back from the pointer, never the digest alone); `title` is **`label` alone** (the
  row-triple label or "Change (no table row)", cut to 120 code points) — the `object_display`
  operand is dropped, since it is a pointer; `after_summary` and `after_full` are built from
  `checks.hipaa_redact(ctx, row, after, root="after")` (02_act.md §2.2b), not from raw `after`;
  every other key is as in the table. The approver resolves the pointer objects in its alert body
  only (05_approver.md §5.1 step 1), so the signed display quotes no free text, while
  `display_sha256` still binds each field's digest. A2 test: a OtherCompany money request built twice
  from the same folded action yields byte-identical `display_b64`, its decoded display contains no
  substring of the fixture's `money_brief.risk` text, `title` equals the bare label, and 3b's
  `build_display` recompute accepts it (RED when `title` concatenates the pointer or a key holds
  resolved text) (requests/03_schemas.md R90 → 05_approver.md §5.1 step 1, which today names
  `title` among the pointer-form keys).

  `urgency` = `money_brief.urgency`. An `urgent` request writes a `runaway_spend` notice (severity
  `urgent`, push) instead of `money_card` (02_act.md §2.6). A2 test: a `google_ads.campaign_budget_edit`
  whose `target_ref` customer id is a fixture `shared_identifiers` value computes `money` and its
  request's `display` carries `shared_warning` with that hit's `relationship`/`ruling_ref`; the same
  action without the shared hit has no `shared_warning` key; a request whose decoded display lacks a
  required `shared_warning` fails 3b's `build_display` recompute (RED when the key is dropped).
- `new_absolute_value` is a string `^(0|[1-9]\d*)\.\d{2}$` (pause/stop/remove = `"0.00"`) — never a
  float. **Null rule (the four cases of 05_approver.md §5.5 3b):** `new_absolute_value` and
  `unit` are both `null` only for (i) an amount-less `_nomatch` action (never an enable action, and
  never one refused `money_amount_hidden`, §3.2), (ii) a money row with `amount_required: false`,
  or (iii) an action that is class `money` **only** because `spend_delta_monthly ≠ 0` on a `money:
  false` row (check 10 forbids amount keys there; `display.spend_delta_monthly` shows the change);
  and (iv) the signed report-only AI-spend form — `new_absolute_value: null` with `unit:
  "report_only"` (not null), on `gtm_ai.weekly_cap_edit` only (§3.2 "Money value strings";
  requests/07_notices_schedules.md R34) — both values are already signed payload keys, so the
  12-key set is unchanged. Any other null (or `report_only` on another row) is refused. For (i)–(iii) the approver shows "Approve change (no amount)" with
  `display.after_summary` as a heading and `display.after_full` in full; for (iv) it shows `NO CAP —
  report only, unlimited AI spend` (05_approver.md §5.1).
- `account_id` is stored in actions, requests and payloads in its §3.22 normalized form, so 3b's
  equality is exact.
- `expires` = created + 72 h. It bounds **use before consumption** only: a nonce consumed before
  `expires` stays valid as a record of what the operator signed (this is what makes a signed
  `gtm_ai.weekly_cap_edit` an indefinitely effective cap, 04_hooks.md §4.6; the effective cap for a
  `(company, account_id)` is the **latest by the signed payload's `expires`, then its `card_id`**,
  among records that pass signature verification and whose nonce is consumed — 04_hooks.md §4.6 /
  05_approver.md §5.5; never ordered by `signed_at` or by ledger line order, both of which sit
  outside the signature — and `create_request` supersedes every older pending `gtm_ai` request for the
  same `(company, account_id)`, 05_approver.md §5.5). A browser write ticket is minted only with ≥
  `MINT_MARGIN` (35 min) of validity left (§3.6 `approval_expiring`, exit 7), and its
  `complete` needs no unexpired request — only the ticket's own reserve line with `ts < expires`
  (§3.9; 05_approver.md §5.5 step 5), so an outcome is recorded even when the operator finishes
  after `expires`.
- For an enable action `current_value` is the freshly read configured ceiling `authorize` wrote
  and equals `new_absolute_value` (§3.2 "Enable actions"), so the operator sees — and
  05_approver.md §5.1 labels — the money the enable commits. For a browser account it is the value
  of this run's `committed_ceiling` snapshot (≤ 24 h), not a live platform read; the binding
  controls there are the API read-back at `ticket --write` mint checked by G-A rule 9d (§3.6
  `budget_readback`) and the runbook's ceiling before-check at execution (06_connectors.md §6.4).
- A request is never rewritten except `status` (A2 sets `approved|denied|expired|superseded`) and,
  for a regulated pack's terminal request after 30 days, the `display`/`display_b64` redaction of
  05_approver.md §5.1 step 1.

### 3.8 Approval record (GTMApprover writes `S/approvals/<slug>/<request_id>.json`, mode 0600)

```json
{"schema": "gtm.approval.v1", "request_id": "apr_…", "decision": "approved",
 "payload_b64": "<byte-identical copy of the request's payload_b64>",
 "signature_b64": "<base64 signature over the decoded payload bytes>",
 "alg": "ecdsa-p256-sha256", "key_fingerprint": "sha256:<hex>", "signed_at": "2026-09-27T15:10:00Z",
 "app_version": "1.0.0"}
```
`alg` ∈ {`ecdsa-p256-sha256`, `ed25519`} and must match the type of the key the fingerprint
selects (HEAD's current key, or a retired key under 05_approver.md §5.6's rotation rule;
`alg_mismatch` otherwise). Signature encoding and the fingerprint are defined once in
05_approver.md §5.5 step 4 / §5.6: ECDSA = DER X9.62 over SHA-256 of the decoded payload bytes;
Ed25519 = the raw 64-byte signature; `key_fingerprint` = `"sha256:" + sha256(SPKI DER)`.
Denied: same file with `"decision": "denied"` and no `signature_b64` (unsigned; a denial only
prevents). Optional `"decided_via": "app"|"card"` (a card only ever denies, §3.7 mirror card). Every
record — approval or denial — is published **create-exclusive** (temp file + `link()`; `EEXIST` =
the earlier decision stands, never overwritten) into a directory of mode 0700 (05_approver.md §5.1).

### 3.9 Nonce ledger (`S/approval_nonces.jsonl`, lock `S/approval_nonces.lock`)

Line: `{"ts", "company", "request_id", "action_id", "system", "account_id", "nonce", "op": "reserve|release|consume", "holder": "ticket:<ticket_id>|execute:<action_id>|run-holds:<action_id>|trust-edit:<abs path>|operator-ok:<command>:<target>"}`
— `system` and `account_id` copied by act.py from the **verified signed payload** (04_hooks.md
§4.6's ledger cross-check reads them for `gtm_ai`); both null on a `trust-edit:` or `operator-ok:`
line.
**Holder is always the full prefixed string** (`ticket:…`, `execute:…`, `run-holds:…`,
`trust-edit:…`, `operator-ok:…`) as written in the ledger and passed to `reserve`/`consume`/`release`;
a bare id is never a holder (02_act.md §2.4 `execute` still passes a bare `<action_id>` —
requests/03_schemas.md R43). State per
nonce = last op. `reserve` allowed iff state ∈ {none, `release`}; `consume` allowed iff state
`reserve` with the same holder — **except two single-use marker holders**, whose nonce goes straight
from none to `consume` (there is no reservation because each marker is single-use and consumed at
the one admitting check): a `trust-edit:<abs path>` holder (04_hooks.md §4.3 G-W; `company:
"runtime"`, `request_id`/`action_id`/`system`/`account_id` null) and an
`operator-ok:<command>:<target>` holder — the signed operator marker `gtm.operator_ok.v1` of
00_global_paths.md §1.4 "Operator authority" (IMP-03; `command` ∈ `OPERATOR_OK_COMMANDS`, `target`
= the pause file name or `autonomous`; `company` = the slug, `request_id`/`action_id`/`system`/
`account_id` null; requests/00_global_paths.md R29); `release` allowed iff state `reserve`. A
`reserve` while another holder holds the nonce refuses **`nonce_held`** (exit 7; the name
05_approver.md §5.5 step 5 uses — `nonce_reserved` is only the §3.6 ticket field). `consume` is
terminal — any later op refuses `nonce_replay` (exit 7); a **quarantine** (05_approver.md §5.5 step
5) is a `consume` by the reserving holder plus a `nonce_quarantined` event, so it is terminal too.
Plain JSON lines, not hash-chained. A1/A2 test (shared ledger library): a trust-edit `consume`
from state none with holder `trust-edit:/…/act.py` succeeds and a second one refuses
`nonce_replay`; an `operator-ok:resume:PAUSE.gbp` consume from state none succeeds and a replay of
the same nonce refuses `nonce_replay`; a `ticket:` consume from state none refuses; a second
holder's reserve refuses `nonce_held`. Which stage
(`authorize|mint|execute|complete|run_holds|revert`) performs which op under which holder, and each
stage's expiry test (at `complete`: the nonce is reserved by `ticket:<ticket_id>` with that reserve
line's `ts < expires`, instead of `expires > now`), is 05_approver.md §5.5 step 5's table — the one
definition. The exit code and `error.code` of every nonce and approval reason (`nonce_held`,
`nonce_replay`, `nonce_not_reserved`, `reserved_after_expiry`, `approval_missing`,
`approval_expired`, … exit 7; `approver_vs_anchor`, `approver_not_installed` exit 11) are
05_approver.md §5.5's "Reason → exit code → `error.code`" table — the one list
(requests/05_approver.md R64).

### 3.10 Pause files and scope (A1 `pauses.py` writes/reads; G-A, gate-gtm and `run_gtm_job.sh` read)

File content: optional JSON `{"reason", "ruling_ref", "card_id", "lift_card", "created_by": "operator|breaker|gate-gtm|act|migration", "requested_via": "skill|self|null", "run_id": "<cycle id>|null", "cause": "verify_failed|created_not_paused|isolation_hit|<other breaker cause>|null", "ts"}`
(`cause` is written by breakers only — the 02_act.md §2.9 trigger that wrote the pause; every other
writer writes null; a breaker pause **without** a readable `cause` is treated as `isolation_hit` by
the §3.17 ladder, fail-safe; requests/03_schemas.md R72 → 02_act.md §2.9/§2.2b `write_pause`)
(`card_id` = the card that authorized writing it, e.g. the carry-in card; `lift_card` = the card
whose answer lifts it, e.g. `C7`); an empty or non-JSON file is a valid pause (hand-made) and reads
as `created_by: "operator"`. `ts` (UTC ISO) is **always** written by `pauses.write_pause` — it is the
occurrence time a `resume <pause>` card is bound to (02_act.md §2.6 "Single use"). `ST/PAUSE.chain` additionally carries
`chain_evidence: {"reason", "log_size", "log_sha256", "anchor_seq", "anchor_hash"}`, written by
dispatch under `actions.lock` (02_act.md §2.3; the evidence `resume --name PAUSE.chain` with
`lifted_via: "false_break"` compares, 02_act.md §2.4; requests/02_act.md item 91). `act.py pause` writes `created_by: "operator"` only when it consumes a
valid **signed** operator marker for that pause (00_global_paths.md §1.4 "Operator authority":
`gtm.operator_ok.v1`, verified against HEAD's approver key, nonce consumed with holder
`operator-ok:pause:<pause file name>`, §3.9; 02_act.md §2.3/§2.4, IMP-03), else `"act"` (or
`"migration"`).
**`requested_via` (DECIDED HERE):** `act.py pause` writes `requested_via: "skill"` **by default** —
the form `/gtm-pause` (WP-K) uses, i.e. any pause the operator asked for in chat — and writes
`requested_via: "self"` (with `run_id` = the caller's own cycle id) only under `act.py pause --self
--run <cycle id>`, which a session uses to pause its **own** run; breakers, gate-gtm and the
migration write `null` (02_act.md §2.4 `pause`/`resume`, §2.2b `pauses.write_pause`/`lift_requirement`).
Presence is what counts for blocking; `created_by`, `requested_via`,
`ruling_ref` and `lift_card` decide who may remove it (`act.py resume`, 02_act.md §2.4: only a
`created_by: "act"`, **`requested_via: "self"`** pause with no `ruling_ref` is removable without the
operator's single-use **signed** marker — a skill-requested pause lifts only by the marker or an
approving `resume <pause>` card, because resuming permits action while pausing only prevents — what
"operator terminal" means throughout, 00_global_paths.md §1.4 "Operator authority" / 02_act.md §2.3
"Operator marker": a GTMApprover-signed `gtm.operator_ok.v1` record (Touch ID), never a TTY or
environment test and never an unsigned file (IMP-03; requests/00_global_paths.md R29) — or an
approving lifting card; **a pause with a non-null `lift_card` is lifted only by that card's
`approve` answer — never by any marker** (`resume_card_required`, marker left in place); a `created_by: "breaker"` pause with no `ruling_ref`
is additionally lifted by `autonomy_ladder.py promote`, §3.17, FID-11 — **except** one whose `cause` is
`isolation_hit` (or unreadable), which lifts only by the signed marker or an approving `resume
<pause>` card, §3.17 "Isolation-hit pauses"). **Enforcement points:**
act.py (`pauses.blocking`, at authorize/ticket mint/execute/run-holds) **and** G-A at every browser
tool call that needs a write/batch/setup ticket (04_hooks.md §4.1 rule 6b), so a pause written while a ticket is
live stops the browser at its next call instead of when the ticket expires.

| Pause | Location | Blocks | Still allowed |
|---|---|---|---|
| `DISABLED` | `R/schedules/DISABLED` | scheduled starts (run_gtm_job.sh exits `skipped-disabled`); run-holds; every T1+ `authorize`, `ticket --write/--write-batch/--setup`, `execute` | T0 reads, `read-run`, `snapshot`, `ticket --read`, `lead-append`, `complete` (recording an in-flight outcome), `status`, `queue`, `purge-untrusted`, `pause`, `resume`, `revert` step 1 and step 2 with `--approval` (money: signed request of the child; non-money: a card answered `approve` with subject `revert <child action_id>`, `cards.require_approved`, 02_act.md §2.4) |
| `PAUSE` (manual) | `ST/PAUSE` | this company only: run-holds and every T1+ `authorize`, `ticket --write/--write-batch/--setup`, `execute`. Scheduled starts exactly as 07_notices_schedules.md §7.2 decides (F17 as corrected there): `monthly`/`monthly_load` write heartbeat `skipped-paused` and start nothing; `inbox`, `daily` and `weekly` start with `--paused` and run only their reduced paused lists (07_notices_schedules.md §7.5 "Paused runs"). Only `DISABLED` stops every scheduled start | same as DISABLED, plus `ingest-findings` (plan §6.8: T0 reads, read tickets and `lead-append` stay allowed) |
| `PAUSE.<system>` | `ST/PAUSE.<system>` (breakers; owner pauses carried in at P1) | for that system, all brands: every T1+ `authorize`, `ticket --write/--write-batch/--setup`, `execute` and `run-holds` (its holds stay `held`) — the same command list as the `DISABLED`/`PAUSE` rows, scoped to the system (a `setup` ticket for a `setup_capture` row of that system included) | everything else, read tickets naming it, `lead-append`; under a **breaker** pause only, that system's urgent signed stop actions (the stop-row exemption, below) |
| `PAUSE.<system>@<brand>` | `ST/PAUSE.<system>@<brand id>` (owner pauses scoped to one brand, e.g. OtherCompanyB A0022 website pause per brand) | the same commands — `authorize`, `ticket --write/--write-batch/--setup`, `execute`, `run-holds` — for every action of that system that is **covered** by `<brand id>` (`pauses.blocking(..., brand)`, below) | other brands' actions of that system, when provably theirs; as above |
| `PAUSE.budget` | `ST/PAUSE.budget` | **GTM-seat dispatches only** (gate-gtm, 04_hooks.md §4.6) | every act.py command; the reserved lead-capture analyst allowance |
| `PAUSE.chain` | `ST/PAUSE.chain` | every act.py command with `chain_policy: write` | `read`/`lead`/`repair` policies (02_act.md §2.4) |
| `PAUSE.trust` | `S/PAUSE.trust` (global) | every money-class authorize/ticket/execute/complete/revert (exit 11, never 5) | all non-money work |

**Brand coverage (DECIDED HERE; plan §6.4 "a PAUSE file beats any standing approval").** An action
is covered by `PAUSE.<system>@<b>` when its `system` normalizes to `<system>` and **any** of: its
`brand` is `b`; its `brand` is null; its `account_id` equals the `account_id` of an `accounts[]`
entry whose `brand` is `b` (both sides through `system_names.normalize_account_id(<tier system>,
…)`, §3.22 — so `100-200-3000` in the pack covers a stored `1002003000`); or its `target_ref` host
(lowercased) is equal to, or a subdomain of, one of brand `b`'s `domains`. So a
remodeling-site edit proposed with `brand: null` or with a wrong brand is still blocked by
`PAUSE.website_wordpress@remodeling`, independent of the §3.2 brand-binding refusal (defence in
depth: G-A applies the same coverage to a ticket's `brand`/`account_id`/`allowed_hosts`, and 04 rule
6b already blocks a `brand: null` ticket on any `@<b>` pause). P2 test (A1): with
`PAUSE.website_wordpress@remodeling` present, a remodeling-site `page_edit` with `brand: null` and
one with `brand: "restoration"` (the brand-binding check reverted, so only the pause is under test)
are both refused exit 5 at `authorize`, and a genuine restoration-site edit is not.

**Stop-row exemption (defined in §3.2 "Paused creates"; FID-03 runaway spend).** A `PAUSE.<system>`
(or `PAUSE.<system>@<brand>`) whose content reads `created_by: "breaker"` with null `ruling_ref`
and null `lift_card` does not block a **stop action** of that system — a matched §3.4.4 `class:
money` row with `lanes_key: none`, `after.new_absolute_value` `"0.00"` or `Decimal`-lower than
`before.value.current_absolute_value`, and `money_brief.urgency: "urgent"`, and **never** an enable
action (`tiers.is_enable_action`, §3.2) or a `current_value: zero` row (a purchase or boost starts
spend, however small; DECIDED HERE) — at `authorize`, `ticket
--write`, `execute`, `run-holds` or G-A rule 6b; every other pause in the table still blocks it, and
the stop still needs the operator's signature. `pauses.blocking` therefore takes the action (not
only system/class/brand) to decide it (requests/03_schemas.md R57 → 02_act.md §2.2b
`pauses.blocking`, 04_hooks.md §4.1 rule 6b / `ticket_paused`).

System names in `PAUSE.<system>` are tier-table system names **or** activity-log system names
(`website_remodeling`); `pauses.blocking` normalizes them with `system_names.tier_system_and_brand`
(§3.22): a legacy brand-form name becomes the brand-scoped pause it always meant
(`PAUSE.website_remodeling` → `website_wordpress@remodeling`, `PAUSE.gbp_restoration` →
`gbp@restoration`), so a per-brand owner pause lifts per brand (F10, I13), never over-blocks the
other brand. `act.py pause` always writes the canonical form (`PAUSE.<tier system>[@<brand>]`).
The P1 carry-in (WP-M `pause_carry_in.py`) writes OtherCompanyB A0022 as `PAUSE.website_wordpress@remodeling`
and `PAUSE.website_wordpress@restoration` (`ruling_ref: "A0022"`, **`lift_card: "C7"`** — lifted
only by card C7's answer, plan §6.4), and R12 as `PAUSE.csa_scout` (`ruling_ref: "R12"`,
`lift_card: null`), each with `created_by: "migration"`. **The carry-in pauses are written
unconditionally (DECIDED HERE; a pause only prevents, so gating its creation on an approval would
fail in the unsafe direction):** `pause_carry_in.py` writes every listed pause file first, then
posts the one carry-in card via `card-post` listing every entry and its ruling id (plan §0 P1
"reviewed"), **with subject `pause_carry_in <slug>`** (`card-post --subject "pause_carry_in
<slug>"`, the token 08_seats_wps.md's `pause_carry_in.py post` and 02_act.md §2.6's decision grammar
use), and records that card's id in each file's `card_id`. **Precedence (DECIDED HERE):** on
*when* carried-in pauses are written, this section wins over 08_seats_wps.md's WP-M `apply` text
("once it is answered APPROVE, `act.py pause --created-by migration --card <id>` per entry"),
which would leave A0022/R12 unenforced by their own files while the card waits — the unsafe
direction; requests/03_schemas.md R73 asks 08 to change `apply` to "write first, card confirms"
(and its "No → no pause file written" test to "No → files stay, list correction may only add"). The card **confirms the list
only**: an `approve` answer changes nothing; a `deny` (or a later correction) triggers a list
correction that may **add** pauses but never removes one — a carried-in pause is lifted only by its
own `lift_card`'s approve answer when it names one (A0022/C7), else by the operator's signed marker
or an approving `resume <pause>` card (below). `act.py pause --created-by migration` therefore
does not require an approved card (requests/03_schemas.md R44 → 02_act.md §2.4 `pause`). A1 test:
with the carry-in card unanswered, both A0022 pause files exist and `authorize` of a remodeling
`website_wordpress.page_edit` exits 5; a `deny` on the card leaves both files in place; RED when the
pauses are written only after an approve.
Because A0022 is carried in with no autonomy demotion and names `lift_card: "C7"`, only an
`approve` answer on C7 can lift it — a `resume` without it, with C7 answered `deny` or unclear, or
with a valid signed operator marker (refused `resume_card_required`, marker left in place;
00_global_paths.md §1.4), exits 3 (02_act.md §2.4). **`PAUSE.csa_scout`
is a shared-identifier pause (F-scout; DECIDED HERE — replaces the former "record-only" rule,
whose premise "no GTM row acts on Scout" was false: any action whose check-1 `shared_hits` include
a Scout/CSA shared identifier — e.g. a OtherCompanyB GBP phone edit writing the shared Scout number,
plan §3.3/§6.3 — acts on Scout, and plan §6.4 "a PAUSE file beats any standing approval" carries
R12 in to take effect).** `csa_scout` has no tier-table row, so it can never match by system;
instead it blocks **by shared identifier**: a `shared_identifiers[]` entry may carry the optional
key **`pause_names`** (a list of pause file names, e.g. `["PAUSE.csa_scout"]`; requests/03_schemas.md
R89 → 08_seats_wps.md Appendix C, which also has WP-M write it on every OtherCompanyB Scout entry the
R12 ruling covers), and `pauses.blocking(ctx, action, …)` blocks (exit 5, at `authorize`, `ticket
--write/--write-batch`, `execute`, `run-holds`) every action one of whose `check1.shared_hits`
values equals the (§3.22-normalized) `value` of an entry whose `pause_names` names a pause file that
is present. A pause file named in some entry's `pause_names` is therefore never "unrecognized" in
step (4) below, even though it names no canonical system. G-A rule 6b applies the same test to a
shared write ticket's `shared_values` (requests/03_schemas.md R89 → 04_hooks.md §4.1). **While such a
pause is present,** the shared-class card of an action it would block is still posted, and every
shared card and every `display.shared_warning` hit whose entry names a present pause carries
`"paused_by": "<pause file name>"` (in `shared_warning.hits[]`, bound by `display_sha256`) and the
card's machine block the line `**Paused by:** <name>`, so the operator sees the R12 gate before
answering. It is listed on `GTM_Operator.html`. A1 tests (each RED when its clause is removed): with
`PAUSE.csa_scout` present and the fixture OtherCompanyB Scout entry carrying `pause_names:
["PAUSE.csa_scout"]`, a OtherCompanyB `gbp.phone_edit` whose `phone` is the shared Scout number is
refused exit 5 at `authorize`, and its shared card carries `**Paused by:** PAUSE.csa_scout`; without
the pause file the same action reaches `awaiting_card`; a OtherCompanyB `gbp.hours_edit` (no shared
hit) is not blocked; and (the `PAUSE.<system>` row's setup coverage) with `PAUSE.meta` present, a
`ticket --setup` for an authorized `meta.api_access_create` is refused exit 5 with no ticket file. **Pause-name resolution (DECIDED HERE; the one order):** (1) the special names `PAUSE`,
`PAUSE.budget`, `PAUSE.chain`, `PAUSE.trust` and `DISABLED` are matched first, exactly, and follow
the table above; (2) for any other `PAUSE.<x>`, `<x>` is split at its first `@` into a system part
and an optional brand part; **only the system part** is case-folded and has every `-` mapped to `_`
— the brand part is kept exactly as written and compared exactly with the pack's `brands[].id`
(a brand id may contain `-`) — before `tier_system_and_brand` normalizes `<system part>[@<brand
part>]` (so a hand-made `PAUSE.GBP` or `PAUSE.google-ads` blocks `gbp` / `google_ads`, and
`PAUSE.GBP@north-side` blocks brand `north-side`; A1 test, RED when the fold is applied to the
brand part); (3) a name listed in any pack `shared_identifiers[].pause_names` (e.g.
`PAUSE.csa_scout`) is a **shared-identifier pause**: it blocks exactly the actions the paragraph
above names and nothing by system, and is shown on `GTM_Operator.html`; (4) any other name that
still does not normalize to a `CANONICAL_SYSTEMS` member blocks nothing **and** writes a `pause` notice, severity `warn`, push,
title "unrecognized pause file — blocks nothing", naming the file (`dedupe_key`
`pause_unrecognized:<slug>:<file name>`), and is listed on `GTM_Operator.html` as unrecognized — so
an operator who believes a system is paused learns at the next command that it is not
(requests/03_schemas.md R48 → 07_notices_schedules.md §7.1). A1 tests:
`PAUSE.GBP` blocks a `gbp.hours_edit` at `authorize` (exit 5); `PAUSE.csa_scout` (named in a
fixture entry's `pause_names`) writes no notice and blocks no action without a matching shared hit; `PAUSE.gpb` blocks nothing and writes the `warn` notice; D test: all three appear
on `GTM_Operator.html`. `/gtm-pause` / `/gtm-resume` (WP-K)
call **`act.py pause` / `act.py resume`** (02_act.md §2.4) — never Write/Edit or shell writes, which G-W and
G-B deny under `.claude/gtm/state/`. Resume refuses `PAUSE.chain`/`PAUSE.budget` until the cause is
cleared, refuses an owner/migration/breaker/ruled pause **and every `requested_via: "skill"`
pause** without the operator's signed marker or an approving lifting card (a `lift_card` pause: the
card only), and always refuses
`PAUSE.trust` (operator-only, by hand). A1 test: a pause written by `/gtm-pause` (default
`requested_via: "skill"`) is refused by a later session's `resume` with no marker/card (exit 3),
and a `pause --self --run <id>` pause is resumable by it. **Lifting card
(FID-01):** answering a card is not approving it — `resume` proceeds only through
`cards.require_approved` (02_act.md §2.2b/§2.6): decision `approve`, and either the card id equals
the pause's `lift_card` (the id is the binding; e.g. C7) or, for a pause with no `lift_card`, the
card's posted subject equals `resume <exact pause file name>` (e.g. `resume
PAUSE.gbp@restoration`). A `deny` or unclear answer, or an approve on a card whose subject names
another pause, refuses and leaves the pause.

### 3.11 Holds, cancels, release checks (A2 `holds.py`)

- A hold is the action's `hold` block (§3.3) + a `hold` notice. `hold_until` = placement +
  `hold_minutes`.
- **Cancel marker** `S/cancels/<slug>/<action_id>`: JSON `{"who": "operator_script|approver_menu|hand_made_file|agent|system:responded_by|card_deny", "ts", "reason"}`
  (`CANCEL_WHO`, the one enum; the fold's `cancelled.data.who` and `cancel_late.data.who` use it);
  an empty file = `hand_made_file`. **`who` classes (one definition for every reader; 05_approver.md
  §5.1 step 5, `requests/05_approver.md` R76 (e)/R77 (a)/R86; stated here wave1e):** *operator* =
  exactly {`operator_script`, `approver_menu`}; *agent-class* = every other value, including an
  empty file, an unknown, misspelled or absent `who` and a body that is not a JSON object — never a
  parse error for a pending `$` request. An agent-class marker never revokes a signed, unconsumed
  `$` approval (ingest, 05 §5.1 step 5) and never stops a write ticket whose rule-7a verification
  reports `signed_required: true` (04_hooks.md `ticket_cancelled`, G-A rule 6b); it still cancels
  holds, unsigned actions and every other ticket. `act.py cancel` writes `who: "agent"` only (no flag can change it);
  `gtm_cancel.sh` writes `operator_script`; GTMApprover writes `approver_menu`; the release re-check
  writes `system:responded_by` (below); act.py writes `card_deny` when a mirror-card deny revokes an
  approval whose nonce is reserved (05_approver.md §5.1 step 5; requests/05_approver.md R35). `gtm_cancel.sh all <slug>` writes one marker per pending
  hold plus `S/cancels/<slug>/_all.<UTCts>`, which ingest records as the breaker-style event
  `cancel_all_ingested {marker, cancelled}` (02_act.md §2.2b) plus an `agent_cancel`-style notice (kind `info`,
  title "all holds cancelled"). act.py ingests markers at the start of every `write`/`lead`/
  `repair`-policy command whose chain verifies (02_act.md §2.3) and immediately before any execution;
  agent-made cancels get a notice (`agent_cancel`) and appear in the weekly report. **Flat markers
  (plan §20.7's hand-made path):** ingest also honors the flat `S/cancels/<action_id>`,
  `S/cancels/_all.<slug>` and `S/cancels/_all` forms, and warns on any other flat file, exactly as
  00_global_paths.md §1.2 "Cancels: two accepted layouts" defines (a flat `<action_id>` records
  `who: "hand_made_file"`; a flat `_all`/`_all.<slug>` marker records `cancel_all_ingested {marker:
  "flat:<name>:<st_ino>:<st_mtime_ns>", …}` once per company per that key, from one `os.stat` at
  ingest — so a re-created or re-touched marker cancels again; requests/00_global_paths.md R22). A2
  tests: a flat hand-made `S/cancels/<action_id>` cancels that hold; RED when flat ingest is removed;
  ingest `_all`, place a new hold, `touch _all` → the new hold is cancelled; RED when the key is the
  name alone.
- **Hold notice lifecycle (A2 owns, I16):** the `hold` notice is resolved with
  `notices.resolve_notice(company, notice_id, resolution)` when the hold is released
  (`resolution: "released"`), cancelled (`"cancelled:<who>"`), executed (`"executed"`), or its
  action fails (`"failed:<reason>"`), so the approver's menu never lists a stale hold; a renotified
  hold resolves its old notice (`"renotified"`) and opens a new one.
- **Release re-checks** (run-holds; also before a browser hold is released): cancel marker; §3.10
  pauses incl. `DISABLED`; current effective autonomy (demoted → stays `held`, re-notified with a
  fresh 24 h window); `before` still matches (API: connector read; browser: re-checked by the
  gtm-operator from `dispatch_brief.before` at the runbook's mandatory before-check step, §3.6/06_connectors.md §6.4,
  aborting `before_mismatch` → `complete --failed` → action `failed`); **quiet hours** for
  `recipient.kind == named_person` (outside `pack.quiet_hours` in pack timezone; **a pack with
  no `quiet_hours` uses the default `20:00-08:00` pack-local** — DECIDED HERE, never "no quiet
  hours" — and the same default applies to list sends below); **SMS rows** execute only when
  `knowledge/marketing_kb/compliance/tcpa-a2p-10dlc.md` contains a fenced ```` ```gtm-send-windows ````
  JSON block (`{"<state>": {"start": "HH:MM", "end": "HH:MM"}}`) and the lead's `sms_consent.value`
  is true **and** `sms_consent.source` is a non-empty string **and** `sms_consent.ts` is a valid UTC
  timestamp not in the future (plan §20.6 "consent recorded … with source + timestamp"; F18 — any
  missing piece → the hold stays `held` with reason `sms_consent_incomplete`) **and the send time
  falls inside the applicable window (DECIDED HERE; TCPA state send windows):** when the lead row
  carries `state` (§3.14, a 2-letter US code), the window of that state; a `state` with no entry in
  the block → refused `sms_window_closed` (never "no window, so allowed"); when the lead has no
  `state`, the send time must be inside **every** window in the block (the list-send rule below).
  Outside the window → the hold stays `held` with reason `sms_window_closed` and is retried at the
  next run; until that block
  exists SMS holds never execute (**DECIDED HERE**, mechanizing §20.7's
  "until then SMS holds do not execute"); inbound-inquiry replies are auto-cancelled
  (`who: "system:responded_by"`, written as a marker by run-holds/act.py itself) when the lead's
  `responded_by.who` ∈ {`scout`, `owner`}. **Scope (F-email):** the auto-cancel applies to every
  held action whose row carries `inbox_reply: true` **and** whose proposal `lead_id` is non-null —
  today `{facebook,instagram}.dm_reply_send` and `email.inquiry_reply_send` (both `hold_minutes:
  30`, `lead_id_required`); the lead is read from the lead sink (`lead_sink` connector read) at
  release time. A2 test: a held `email.inquiry_reply_send` whose lead shows `responded_by.who:
  "scout"` is cancelled at release with that `who`; a `dm_reply_send` whose lead shows `none` runs.
- **List sends (FID-13; plan §20.6 "SMS only with consent recorded", §20.7; DECIDED HERE)** — rows
  with `list_send: true` (`email.list_send`, `sms.list_send`) carry no `recipient`, so the named-person
  rules above are restated for them: **quiet hours** apply to the send time (`after.value.send_at`
  when set, else the execution time) in pack timezone, for both rows; `sms.list_send` also needs
  the `gtm-send-windows` block and a send time inside **every** state window in it (members' states
  are not known), and at execution resolves `list_id` to lead-sink rows through the `lead_sink`
  connector, sending **only** to members whose `sms_consent` is complete (value true, non-empty
  source, valid non-future UTC ts — the same three-part test as above); the execution result
  carries `{"members": N, "sent": M, "excluded_no_consent": K}`. A list that does not resolve to
  lead-sink rows → no send, action `failed` with reason `list_unresolvable`. `email.list_send`: the
  `compliance` lane checklist for this row includes an unsubscribe-mechanism check and a
  physical-postal-address check, each cited to the CAN-SPAM file under
  `knowledge/marketing_kb/compliance/`.
- **Send-time re-check (FID-24; DECIDED HERE):** the quiet-hours and SMS send-window checks (named
  person — the lead's `state` window, or every window when it has none, above — or list) run again at `ticket --write` mint and at `execute` for every
  `recipient_required` or `list_send` row, not only at hold release; on the browser path the write or
  batch ticket then carries `send_not_after` (§3.6), which G-A rule 6b enforces at every mutating
  call — so a browser hold released at 19:59 cannot then be executed inside quiet hours, even by a
  ticket minted at 19:59 (requests/04_hooks.md R34). Outside the allowed time → exit 3
  (`quiet_hours` / `sms_window_closed`), no ticket, action stays `authorized`, retried by the next
  run (02_act.md §2.4). The same re-check also re-reads the lead: for an SMS row its `sms_consent`
  must still be complete (the three-part test above), else exit 3 `sms_consent_incomplete`, no
  ticket, no event (new consent is needed — do not retry blindly); and for an `inbox_reply` row
  with a non-null `lead_id` whose lead now carries `responded_by.who` ∈ {`scout`, `owner`}, the
  action is cancelled on the spot (`who: "system:responded_by"`, exit 0, no ticket) — a STOP reply
  or a Scout response can land between hold release and mint (02_act.md §2.4 `ticket`/`execute`). A2 tests: with a block holding `{"CO": {"start": "08:00", "end": "21:00"},
  "FL": {"start": "08:00", "end": "20:00"}}`, an `sms.message_send` to a lead with `state: "FL"` at
  20:30 FL-local is refused `sms_window_closed` and at 19:30 admitted; a lead with no `state` at
  20:30 is refused (outside FL's window); a lead with `state: "TX"` (no entry) is refused; each goes
  RED when the window test is removed.
- **Late cancels (plan §20.7; 02_act.md §2.4 `cancel`, §2.5).** A cancel marker ingested for a
  `ticketed` action appends `cancel_late {who, ticket_id, calls_used}` (`calls_used` = the ticket's
  `mutating_calls_used`) and moves the ticket by the §3.6 late-cancel transitions (either way G-A
  rule 6b denies the operator's next call — neither `abandoned` nor `stopped` admits a tool call):
  `calls_used == 0` on a write ticket → ticket `abandoned` with `reconciled: true` and the nonce
  released in the same critical section, and the action `cancelled` in the same step, so reconcile
  never later appends `ticket_abandoned`/`failed` for it; otherwise the ticket is `stopped` with
  `stopped_at` = now and the action stays `ticketed` until `complete` records what was actually
  done (or reconcile fails it after the stop grace), and a `cancel_too_late` notice (warn, push;
  `dedupe_key` `cancel_late:<action_id>`) is written. `execute` and `run-holds` re-ingest the action's marker immediately before each connector
  call. A marker for any other non-cancellable state is recorded and deleted.
- A hold that comes due during a pause stays `held`; when the pause lifts it re-notifies with a fresh
  24 h window.

### 3.12 Cycle record (`ST/cycles/<cycle_id>.json`; schema doc `CYCLE_SCHEMA.md` by WP-G; writer `cycle.py` by WP-G)

```json
{"schema": "gtm.cycle.v1", "cycle_id": "cyc_other-company_inbox_2026_09_27_1500", "company": "other-company",
 "kind": "inbox", "session_id": "3f0c…", "started_at": "…", "finished_at": null, "status": "running|completed|missed|failed",
 "trigger": "schedule|interactive", "model": "sonnet",
 "dispatches": [{"agent_type": "gtm-analyst", "tool_use_id": "toolu_…", "agent_id": "a…", "phase": "read", "ticket_id": "tkt_…"}],
 "artifacts": [{"artifact_id": "…", "seat": "…", "kind": "FINDING", "file_paths": ["…"]}],
 "actions": ["act_…"], "metrics_read": ["crm_leads_logged_last_7d"],
 "missed_steps": [{"step": "lease", "reason": "lease_held", "ts": "…"}],
 "notes": []}
```
`dispatches[]`/`artifacts[]` follow `MISSION_SCHEMA.md`'s shapes (+ `agent_id`, `ticket_id`;
`tool_use_id` may be null for a dispatch known only from its spend row). Duplicate cycle id →
`cycle.py open` refuses (exit 3). Cycle ids parse only with `CYCLE_ID_RE` (00_global_paths.md §0.3); the date/HHMM are
company-local. `cycle.py` CLI (every mutator names its cycle explicitly):
`open --cycle <id> --company X [--trigger schedule|interactive] [--session <uuid>]` (**I3:** the
id is always supplied by the caller — `run_gtm_job.sh` or `gtm_session.sh` — and validated with
`CYCLE_ID_RE` and `system_names.cycle_id_ok` (00_global_paths.md §0.3: `inbox` and `interactive`
ids require the HHMM suffix, the other four kinds forbid it; a mismatch → exit 3
`bad_cycle_id_hhmm`, no state written; requests/00_global_paths.md R40); its slug must equal
`--company` and its kind must be `interactive` iff `--trigger interactive`; the kind and date are parsed from the id; prints the id; `open` never generates an
id), `add-dispatch --cycle <id> --agent-type T [--tool-use-id U] [--agent-id A] [--phase P]
[--ticket T]`, `add-artifact --cycle <id> --artifact-id I --seat S --kind K [--file <path> ...]`,
`add-action --cycle <id> --action <id>`, `add-metric --cycle <id> --metric <id>`,
`sync --cycle <id>` (**mechanical fill, I3:** appends to `dispatches[]` every
`S/dispatch_tags.jsonl` row with this `run_id` (tool_use_id, seat, admission ts) joined to its
spend row's `agent_id` when present, and to `actions[]` every action id whose `proposed` event in
`actions.jsonl` carries this `run_id`; idempotent; **`--if-running`** (requests/07_notices_schedules.md
R54): when the record's `status` is not `running` → exit 0, nothing changed, prints `{"ok": true,
"synced": false, "status": "<current>"}`; without the flag a record that is not `running` → exit 3
`closed_cycle`, unchanged),
`missed --cycle <id> --step S --reason R` (**creates** the record with `status: "missed"`,
company/kind parsed from the id and `trigger` derived from that kind — `interactive` for an
`interactive`-kind id, else `schedule`, the same kind↔trigger rule `open` enforces (DECIDED HERE; G
test: `missed` on a fresh `interactive` id writes `trigger: "interactive"`, RED when the trigger is
hardcoded) — when it does not exist; on an existing
`running` record appends to `missed_steps[]` and sets `status: "missed"` — e.g. a lease timeout
after `run_gtm_job.sh` opened it), `close --cycle <id> --status completed|failed|missed
[--if-running]` (**`--if-running`** (requests/07_notices_schedules.md R35): when the record's `status`
is not `running` → exit 0, nothing changed, prints `{"ok": true, "closed": false, "status":
"<current>"}`; when it is `running` → closed as without the flag, printing `"closed": true`; without
the flag a record that is not `running` → exit 3 `closed_cycle`).
**Who calls what:** `run_gtm_job.sh` calls `open` right after computing `run_id`/`SESSION` and
before `gtm_session.sh` (07_notices_schedules.md §7.2), then `sync` and — if the record is still `running` — `close`
(`completed` on session exit 0, else `failed`) after the session exits; `gtm_session.sh` opens
the `interactive` record for a session started without `--run` (07_notices_schedules.md §7.6) and runs `sync` + `close`
on exit; the session prompt (K) may call `add-artifact`/`add-metric`/`add-dispatch --phase`
for annotation only — no correctness depends on the model remembering a call. G test: `close
--if-running` on a `missed` record → exit 0, record byte-identical; on a `running` record → closed;
RED when the flag's status test is removed; `sync --if-running` on a `failed` record → exit 0, record
byte-identical, on a `running` record → synced; `open` of an `inbox` id without HHMM and of a
`weekly` id with HHMM → `bad_cycle_id_hhmm` (RED when `cycle_id_ok`'s kind check is removed).
Interactive runs
use `budget.dispatch_caps_per_run.get("interactive", budget.dispatch_caps_per_run["mission"])` as
their dispatch cap (04_hooks.md §4.6 step 4). Exit codes (IMP-17): 0 ok, 1 internal, 2 usage/bad id, 3 refused (duplicate open,
id/company/trigger mismatch, `bad_cycle_id_hhmm`, unknown cycle for a non-`missed` mutator, `closed_cycle`,
`test_mode_real_state`), 12 lock
timeout (`ST/cycles/.lock`), 13 company. **DECIDED HERE:** `cycle.py` is added to WP-G's file set
(the plan names the record and schema but no writer, and G-W denies Write/Edit on `state/**`).

### 3.13 Spend row `gtm` field (WP-B2, `agent_budget.py`)

**Attribution never depends on the pacer claim (F1, I6; DECIDED HERE).** Measured from
`R/.agent_budget/spend.jsonl` since 2026-09-20: the 9 `DEPARTMENT_SEATS` (the existing `/gtm` seats,
marketing-director … market-analyst — `GTM_SEATS` did not exist yet) have 405 `no-claim` rows
against 100 `joined`; all rows 2,964 `no-claim` against 1,392 `joined`. Two line shapes cause it
(`hooks/agent_budget.py`): a **synthetic-claim** line from `_release_line_from_join` (a real stop,
no real claim) is `join_state: "no-claim"`; and `reap_stale`'s **`stopped-unjoined`** line (a
PENDING-STOP row reaped with no claim ever joined) carries `tool_use_id: null`, `session: null`,
`unreleased: true` and **real** tokens. A tag copied only from the claim would leave the signed
AI-spend cap blind to most GTM dispatches. So the tag reaches the ledgers three independent ways:

1. **Admission record (gate-gtm, 04_hooks.md §4.6).** Every dispatch gate-gtm admits (enforced or merely
   tagged) is appended — under `S/dispatch_tags.lock`, in the same critical section as the
   dispatch-cap count (04_hooks.md §4.6 step 4) — to `S/dispatch_tags.jsonl`:
   `{"ts", "tool_use_id", "session_id", "company", "run_id", "run_kind", "seat", "budget_admission"}`.
   This file is the **authoritative dispatch count** (claim-independent) and the first join key for
   spend rows.
2. **Claim copy (NEW WP-B2 work — not existing behaviour; `agent_budget.py` has no `gtm` handling
   today).** gate-gtm sets `ev["_gtm"]` (04_hooks.md §4.6 step 5); B2 changes, in
   `hooks/agent_budget.py` (delivered in `b2_task_wiring.patch`, 08_seats_wps.md §9): (a)
   `_build_claim_record(payload)` copies `payload.get("_gtm")` into the claim as `"gtm"` (absent →
   `None`); (b) **every** spend-line builder writes `"gtm": claim.get("gtm") if claim else None` —
   `_release_line_from_join` (joined and synthetic-claim lines), `_release_line_from_completed_join`,
   the foreground release line built in `handle_completed`, and the three line shapes of
   `reap_stale`: the stale-claim line (`reaped: "claimed"|"launched"`, `join_state:
   "claim-only"`), the `stopped-unjoined` line, and the stale PENDING-COMPLETED line (`reaped:
   "launched"`, `join_state: "claim-consumed"|"no-claim"`, which reads `row["claim"]`). B2 test: one
   fixture dispatch per builder (seven line shapes) whose claim carries a `gtm` dict yields a spend
   line with that exact `gtm`, and a claim without one yields `gtm: null` (each RED when its
   builder's copy is removed).
3. **Transcript tag (new, WP-B2 in `agent_budget.py`).** Every spend-line builder above, when the
   claim carries no `gtm` (or there is no claim), reads the subagent transcript's **first
   user-prompt line** (the transcript `sum_transcript_tokens` already opens; 08_seats_wps.md §8.2
   requires the tag to be line 1), parses it with `system_names.TAG_RE`, and writes `gtm` from it
   with `seat` = the line's `agent_type`, `in_gtm_session: null` (unknown), `budget_admission` from
   the `dispatch_tags.jsonl` row with the same `tool_use_id` when present (else `false`), and
   `source: "transcript_tag"`. A malformed or absent tag leaves `gtm: null`. Parsing failures never
   break the release path (caught; logged). **Sidecar join (mandatory whenever the sidecar exists;
   DECIDED HERE):** each subagent transcript has a sibling `agent-<id>.meta.json` carrying
   `agentType` and `toolUseId` (present on disk today); a builder writing a line with a null
   `tool_use_id` reads it first and, **only when the sidecar's `agentType` is a member of the `gtm`
   or `department` set of `system_names.seat_sets()`** (DECIDED HERE — scoped so no non-GTM spend
   line changes shape), fills the line's `tool_use_id` from `toolUseId` (and joins the
   `dispatch_tags.jsonl` row by it) before falling back to `TAG_RE`; an absent or unreadable
   sidecar, or one whose `agentType` is outside those sets, leaves `tool_use_id` null exactly as
   today. So `churn_report.dedup_spend_lines` (which groups by `tool_use_id`) and
   `record_review.py`'s `--reviewer-tool-use-id` join see no new matches for reviewer, dev or
   oversight seats. B2 tests: a fixture `stopped-unjoined` + `claim-only` pair for a
   `code-reviewer` dispatch leaves `churn_report` metric 5's output and `record_review.py`'s model
   join byte-identical to the pre-change run (RED when the seat scope is removed), and the same pair
   for a `gtm-analyst` dispatch back-fills `tool_use_id`.

**Cache-creation split on GTM lines (NEW WP-B2 work; §3.19 "Cache split" reads it; DECIDED
(wave1c): GTM lines only, so no non-GTM spend line changes shape).** `sum_transcript_tokens`
is **unchanged** (it still returns exactly `{input, output, cache_read, cache_creation}` and
`tokens_total` = their sum). B2 adds `sum_transcript_cache_split(path: str | None) -> dict |
None` in `hooks/agent_budget.py` (delivered in `b2_task_wiring.patch` with item 2's changes, 08_seats_wps.md §9): over the same `type == "assistant"` lines, with the same
per-line skip rule, it sums `message.usage.cache_creation.ephemeral_5m_input_tokens` and
`…ephemeral_1h_input_tokens` into `{"cache_creation_5m": int, "cache_creation_1h": int}`; when
any such line has a non-zero `cache_creation_input_tokens` but no `cache_creation` dict carrying
both integer keys, both values are `null` (split absent — never a guessed share); a falsy path
or a file-level read failure returns `None`. Every spend-line builder of item 2 that has a
transcript path **and** whose line's final `gtm` (after items 2 and 3) is non-null adds the two
keys to that line's `tokens` dict (both `null` when the function returned `None`); a line whose
`gtm` is null gets no new key. `tokens.cache_creation` keeps the total and **`tokens_total`
stays `input + output + cache_read + cache_creation`** — the two split keys are a breakdown of
`cache_creation`, never added to the total (every consumer reads named keys; `churn_report`'s
summer reads `input`/`output`/`cache_read`/`cache_creation`/`tokens_total` only). B2 tests: a
fixture `code-reviewer` dispatch's spend line is byte-identical to the pre-change line, and
`churn_report` metric 5's output and `record_review.py`'s model join over it are byte-identical
to the pre-change run (RED when the `gtm`-non-null scope is removed); a `gtm-analyst` line whose
transcript carries the split gets `cache_creation_5m + cache_creation_1h == cache_creation` and
an unchanged `tokens_total` (RED when the split is added to the total); a transcript with one
message lacking the split gives both keys `null`.

Shape (`source` ∈ `claim|transcript_tag`):
```json
"gtm": {"company": "other-company", "run_id": "cyc_other-company_inbox_2026_09_27_1500", "run_kind": "inbox",
        "seat": "gtm-analyst", "in_gtm_session": true, "budget_admission": false, "source": "claim"}
```
**Untagged dispatches (DECIDED HERE; the seat sets are `system_names.seat_sets()` — `gtm, department,
browser = seat_sets(log=…)`, 04_hooks.md §4; never a local copy).** A `GTM_SEATS` (`gtm`) dispatch
is never untagged: outside a GTM session gate-gtm denies it (04_hooks.md §4.6 step 0), inside one
it is tagged. A `DEPARTMENT_SEATS` (`department`) dispatch outside a GTM session is allowed with
`ev["_gtm"] = None`, its spend lines carry `"gtm": null`, and **exactly one** enforcement-log row
records it, written by **gate-gtm only** — `hooks/gtm_task_gate.py`, in the T1b effects step
`apply_t1b` (04_hooks.md §4.6 "Not enforced" / "T1b wiring") — as `_lib.log("gtm_task_gate",
"gtm_untagged", tool_use_id=<tool_use_id>, agent_type=<seat>, session=<session_id>)` (the
`decision` field is `gtm_untagged`; there is no `reason`). `agent_budget.py` writes **no**
`gtm_untagged` row (it only leaves `gtm: null`), so gate and release never double-log and no
dedupe is needed; a retried Task call with the same `tool_use_id` may log twice, and consumers
count distinct `tool_use_id`s. (04_hooks.md §4 L471's "`agent_budget.py`'s `gtm_untagged` rule"
means this seat-set use, requests/03_schemas.md R74.) B2 test: a non-GTM-session
`marketing-director` dispatch writes one `gtm_untagged` row with those three fields and a spend
line with `gtm: null`; a `gtm-analyst` dispatch outside a GTM session is denied and writes none.

**Row identity (dedupe key, I6).** First, **merge by the claim's own pairing (DECIDED HERE):**
build `A→T` from every line (and every `agent-<id>.meta.json` sidecar) that carries both a
non-null `agent_id` A and a non-null `tool_use_id` T; a line whose `tool_use_id` is null and whose
`agent_id` is in `A→T` is keyed as if its `tool_use_id` were T. Then the key is `("tool",
tool_use_id)` when `tool_use_id` is non-null, else `("agent", agent_id)` when `agent_id` is
non-null, else `("line", sha256 of the raw line)` — never "all nulls collapse to one key". So a
`claim-only` placeholder (T, agent_id A when launched, `tokens: null`) and a `stopped-unjoined`
line (null T, A, real tokens) of one dispatch fall under one key. **Which line wins within a key:**
among the lines sharing a key, prefer the lines whose `unreleased` is false or absent and take the
**last** such line in file order; when every line is `unreleased: true`, prefer those whose
`tokens` is non-null and take the last of them; only when none has tokens take the last line.
(`unreleased: true` lines are the reaper's: the stale-claim `claim-only`/`launched` placeholders
carry `tokens: null`, while `stopped-unjoined` lines carry real tokens.) This extends
`churn_report.dedup_spend_lines`' selection rule (hooks/churn_report.py, which groups by
`tool_use_id` only); the one implementation over the full key is `ai_budget.dedup_spend_rows(rows,
*, sidecar_dir_for=None) -> list[dict]` (WP-B2), no other consumer writes its own
(requests/03_schemas.md R47). Tests (B2): a key whose `unreleased` placeholder precedes the real
release, and one where it follows it, both yield the real release's tokens (RED when the first line
wins); a `claim-only` line (T, A) plus a `stopped-unjoined` line (null, A, tokens 1,000) yields one
row with 1,000 tokens (RED when the `A→T` merge is removed — two rows); the same pair where only
the sidecar maps A to T yields one row too. Every consumer (`ai_budget`, `perf_report`,
`validate_run`) dedupes with this function and attributes rows with
`ai_budget.attribute_row(row, ctx=ai_budget.load_attribution_ctx(now, window_start))` (04_hooks.md §4.6 precedence); `validate_run.py` flags a GTM-seat row only when that
precedence yields `unattributed`. Precondition recorded, not relied on: probe i's map of which
dispatch paths produce `no-claim` rows is recorded in plan §17 before B2 ships; the design above is
correct whatever it finds.

### 3.14 Lead sink row (A1 builds; WP-L `lead_sink` connector writes)

```json
{"lead_id": "lead_other-company_20260927_0004", "company": "other-company", "brand": "remodeling",
 "received_at": "2026-09-27T14:55:00Z", "logged_at": "…", "source": "gbp_message|website_form|call|facebook_dm|angi|thumbtack|yelp|other",
 "source_detail": "…", "name": "…", "phone": "…", "email": "…", "state": "CO", "message": "…",
 "utm": {"source": null, "medium": null, "campaign": null},
 "responded_by": {"who": "scout|gtm|owner|none", "ts": null},
 "sms_consent": {"value": false, "source": null, "ts": null},
 "status": "new|contacted|qualified|booked|lost|spam", "run_id": "…", "logged_by": "gtm-analyst:a…", "notes": null}
```
- `lead-append` input = this object without `lead_id`, `logged_at`, `logged_by` and `run_id`: act.py
  assigns `lead_id`/`logged_at` and sets `logged_by` (`<seat>:<agent_id>` of the `--from-agent`
  analyst, or `main-session` for `--file`) and `run_id` (`ctx.run_id`) **from its own context,
  never from the input** — an input carrying any of the four is refused exit 3 `lead_key_reserved`.
  **Closed key set (DECIDED HERE):** the row is exactly the keys shown; any other key → exit 3
  `lead_key_unknown` (so no free-form treatment or insurance field can ride in). `state` is optional
  (null or a 2-letter uppercase US state code, else `lead_state_invalid`) and selects the SMS send
  window (§3.11). **Validation (the one list `lead-append` applies; 02_act.md §2.4):** the keys and
  types shown above (`received_at` a UTC ISO timestamp; `source`, `status` and `responded_by.who` in
  the enums shown; `sms_consent` exactly `{value: bool, source: str|null, ts: UTC ts|null}`; `utm`
  exactly its three nullable string keys) plus the four named codes above; any other failure →
  exit 3 `lead_invalid` with `error.data.errors` listing every failing key, nothing written.
- **Lead id grammar (00_global_paths.md §0.3):** `lead_<slug>_<YYYYMMDD>_<NNNN>` — regex
  `^lead_(?P<slug>[a-z][a-z0-9-]{1,31})_(?P<date>\d{8})_(?P<n>\d{4})$` (UTC date, `0001`–`9999`;
  the slug group is `company.SLUG_RE`'s body verbatim, the same slug grammar `CYCLE_ID_RE` uses,
  00_global_paths.md §0.3; A1 test: `LEAD_ID_RE.pattern` contains `company.SLUG_RE.pattern`
  stripped of its `^`/`$`, and `lead_9x_20260927_0001` fails). Consumers that iterate lead ids (07_notices_schedules.md §7.5 I6)
  skip an entry that fails it.
- **Pack `lead_sink` keys this section reads** (their schema is `company_schema.json`,
  08_seats_wps.md Appendix C): `kind` (`none` → every lead goes to `lead_fallback.jsonl` with
  `fallback_reason: "sink"`), `baa_ref` (below) and `response_target_minutes` (required int 5–10080;
  the lead response target of 07_notices_schedules.md §7.4 `speed_to_lead` and §7.5 I6;
  requests/07_notices_schedules.md R37).
- Regulated `hipaa` packs: `message` and `source_detail` must be absent/null (else exit 3
  `lead_phi_field`; both are free text that can carry a treatment or insurance detail, §20.3
  non-PHI proxy); the closed key set above means no treatment/insurance field can exist.
  **DECIDED HERE.**
- `digest` = `"sha256:" + sha256(canon(<the full stored row>))` (00_global_paths.md §0.3 `canon`,
  the row as sent to the sink, `lead_id`/`logged_at`/`logged_by`/`run_id` included).
- `actions.jsonl` records only `{lead_id, sink_ref, digest}`. `lead_fallback.jsonl` holds the full row
  (gitignored; `fallback_reason` ∈ `"chain" | "trust" | "pack" | "sink"`; `sink` = a lead-sink `validation`/`auth` failure or a pack `lead_sink.kind: none`, 06_connectors.md §6.2 "Lead sink"; `sink` rows are replayed by the next `lead-append` whose sink call succeeds, like `trust`/`pack` rows — requests/06_connectors.md R13 → 02_act.md §2.4 `lead-append`) until `chain-repair --replay` (or, for `fallback_reason: "trust"`/`"pack"` rows, the next trusted `lead-append`, 02_act.md §2.3) rotates it; its backup exclusion is 08_seats_wps.md Appendix C item 5.
- **Regulated `hipaa` packs — BAA before any vendor receives a lead (FID-19; plan §20.5.6, §20.13;
  DECIDED HERE):** the pack's `lead_sink` must carry a non-empty `baa_ref` (the BAA record for that
  sink's vendor; a pack-schema addition, 08_seats_wps.md Appendix C item 29). Until it does, `lead-append`
  sends nothing to the sink: it writes the full row to `ST/untrusted/<unt_id>.lead.json` (§3.15 —
  purged at 30 days, never backed up), records `lead_appended` with `sink_ref: "untrusted:<unt_id>"`,
  sets `result.baa_missing: true`, and writes one `task` notice "lead sink has no BAA on record"
  (push; `dedupe_key` `baa:<slug>:lead_sink`). The first `lead-append` after `baa_ref` appears forwards every such row
  still present to the sink and deletes it. The same rule binds call tracking (recordings): on a
  hipaa pack every `call_tracking.*` action is refused `baa_missing` unless the pack's `accounts[]`
  entry for `call_tracking` carries a non-empty `baa_ref`; for every other `data_flow: true` row the
  `hipaa` lane reviewer (trust-architect) must cite the vendor's `baa_ref` or record that the flow
  carries no PHI (02_act.md §2.8 check 5).

### 3.15 Untrusted side store (A1 `untrusted.py`, §20.4)

`ST/untrusted/<unt_id>.txt` — the raw quoted text of an `untrusted_inputs[]` entry, or any other
free-text field routed through 02_act.md §2.2b's "HIPAA side-store form" (`rationale`, `undo`, the
six free-text `money_brief` keys, §3.1; review `lines`; `verified`/`verify_failed` `observed`/`diff` of
`inbox_reply`/public text rows; a `failed` action's free-text `reason_detail`) — and
`ST/untrusted/<unt_id>.json` — a snapshot entry not on `system_names.NON_INBOX_SNAPSHOTS` (§3.22), or
inbox-class collector output (02_act.md §2.4 `snapshot`/`read-run`, F2) — and `ST/untrusted/<unt_id>.lead.json` — a lead row held because the
pack's `lead_sink` has no `baa_ref` (§3.14, FID-19); UTF-8, mode 0600. Only for packs with `regulated ∋ "hipaa"`. Deleted by
`purge-untrusted` after 30 days; excluded from `company.backup_set(slug, pack)` by 08_seats_wps.md Appendix C item 5 (which changes
`backup_set`'s return shape, §3.1, and lands before P1b / before any hipaa pack is registered). Seats read it with Read by pointer. For a
hipaa pack, **no** inbox or review content is written anywhere else under the home or `S`: not
`paths.snapshots_dir`, not `ST/collectors/`, not `actions.jsonl` (`before.text`/`after` of inbox
rows are template-only, 02_act.md §2.8 check 5, and every free-text field listed above is stored
as `{digest, pointer}`), not the activity log (02_act.md §2.10 hipaa rule: no rationale, free
text redacted), and not `TOOL_TRAIL.jsonl` — the committed harvester writes browser result
excerpts, typed `text`/`value` and Agent `prompt_excerpt`s into the trail, and `redact_text`
strips secrets, not PHI, so a OtherCompany analyst's review snapshot would land in a hash-chained,
weekly-backed-up log that G-B rule c makes uneditable. **08_seats_wps.md Appendix C item 27** (coordinator; lands
before P1b and before any `regulated ∋ hipaa` pack is registered, enforced exactly like item 5:
`company.py register` refuses such a pack until it lands) makes the harvester write, for hipaa
packs, `result_excerpt: null`, no `detail.text`/`detail.value`, no `prompt_excerpt`, keeping only
tool, URL host, mutating flag and ids, plus `phi_redacted: true`. **The exact trail record on hipaa
packs (DECIDED HERE; the one shape — every key not listed is absent).** The committed harvester
(`harvest_tool_trail.try_classify_call`) records only browser tools, `Write`/`Edit`/`NotebookEdit`,
`Bash` and `Agent`; it records **no** `Read`, `Grep`, `Glob` or `MultiEdit` call, so none of those
has a trail line and none needs a rule. Every hipaa-pack record keeps the base keys
`tool_use_id`, `ts`, `session_id`, `agent_id`, `actor_label`, `tool`, `transcript` (the transcript
**path**, needed by the 02_act.md §2.11 card scan; it holds no content), plus `system`,
`mutating`, `phi_redacted: true`, `result_excerpt: null`, and `prev_hash` (added by
`activity_log._append_chained` at append, never by the harvester; trail records carry no `id` —
`tool_use_id` is their identity), and then only the per-tool keys below. **Order and placement
(DECIDED (wave1c): inside `try_classify_call` — `identity_hit` is a local of its browser branch and
is never returned, so the shaping runs where that value is in scope; the return shape `(company,
record)` and both call sites stay unchanged):** a new pure helper `hipaa_shape(record: dict, name:
str, tool_input: dict, home: Path | None) -> dict` (in `harvest_tool_trail.py`; returns a new dict,
never mutates its argument; `home` = `homes.get(company)`, used only for the `Write`/`Edit`/
`NotebookEdit` `dir_class`) is called in every branch **immediately after `finalize_record` and
before that branch's `return`** — in the browser branch after `record = finalize_record(record)`
and before the `company is None` test, in the `Write`/`Edit`/`NotebookEdit`, `Bash` and `Agent`
branches as `record = finalize_record(record)` then the shaping then `return (company, record)`.
So `finalize_record` (its credential-marker replacement still sees the raw text) runs first and
the hipaa shape is final — `result_excerpt` is null and `detail` is the per-tool form below even
when `finalize_record` wrote `REDACT_CREDENTIAL_MARKER` into either. Nothing between the return
and the append (`harvest_transcript`, `main`/`_flush_locked`) reshapes a record. **Which records
take this shape (DECIDED HERE; the unattributed sink has no pack to consult):** in the browser
branch a record is shaped hipaa when `company is None`, or `packs.get(company)` or
`packs.get(identity_hit)` has `regulated ∋ hipaa`; in the other three branches (which return
`None` when `company` is None) when `packs.get(company)` has `regulated ∋ hipaa`. **A slug in
`homes` whose pack failed to load** (the committed `main` drops a `CompanyError` pack from `packs`)
counts as hipaa for this test (DECIDED (wave1c): fail closed — the harvester cannot tell a hipaa
pack it could not read from any other). So **every** record written to the cross-company
`S/unattributed_trail.jsonl` (`try_classify_call` returning `(None, record)`) takes the hipaa shape
unconditionally, whatever pack any hit names. Then only:
- **browser tools** — `url` **replaced by its host** (lowercase host only: no scheme, path, query
  or fragment, e.g. `"business.google.com"`), `server`, `offserver` (when set), and `detail:
  {"ref": <the element ref id>}` when `tool_input.ref` is a string, else `detail: {}` (never
  `element`, `selector`, `text`, `value` or `code`);
- **`Write`/`Edit`/`NotebookEdit`** — `url: null`, `detail: {"dir_class": "drafts"|"state"|"other",
  "action": "create"|"edit"}`, where `dir_class` is `drafts` when the file's realpath is equal to or
  under `H/.claude/gtm/drafts/`, `state` when under `H/.claude/gtm/state/` (= `ST`), else `other`
  (fixed home-relative paths, not pack keys); never `file_path`;
- **`Bash`** — `url: null`, `detail: {"argv0": <basename of the first token>, "act": <null or
  {"subcommand", "action", "ticket", "company"}>}`: the command is tokenized with `shlex.split`
  (a tokenizer error → `argv0: null`, `act: null`); the **act token** is the first token when its
  basename is `act.py`, or the second when the first token's basename matches
  `^python(3(\.\d+)?)?$`; with an act token, `subcommand` = the next token, and `action`,
  `ticket`, `company` = the values of `--action`, `--ticket`, `--company` when each matches
  `^[A-Za-z0-9_.:-]{1,80}$` (else null); `argv0` is then `"act.py"`. Never `command`;
- **`Agent`** — `url: null`, `detail: {"subagent_type"}` only (never `description` or
  `prompt_excerpt`; the record's own `agent_id` is the dispatching agent, and the harvester sees no
  dispatched-agent id).
The only remaining copies are the
session transcripts themselves, which `purge-untrusted` deletes after 30 days (02_act.md §2.4, plan §20.13).
P2 test (A1): on a hipaa fixture pack, `act.py snapshot` of
an analyst result holding `{"system": "gbp", "name": "reviews", …}` writes only
`ST/untrusted/<id>.json`; the path is absent from `company.backup_set(slug, pack)`'s expanded file list (§3.1; gated on Appendix C item 5); after
`purge-untrusted --older-than-days 30` with `GTM_FAKE_NOW` 31 days later it is gone; the same entry
on a non-hipaa pack lands under `paths.snapshots_dir`; a `review` whose `lines[]` and a
`verify_failed` whose `observed` quote a fixture review sentence leave no copy of it in
`actions.jsonl` (RED when either field's side-store routing is reverted; §3.1 covers
`rationale`/`undo`/`money_brief`). P2 test (coordinator, with item 27): a
fixture OtherCompany transcript holding a `browser_snapshot` of reviews and a `browser_type` of a
reply harvests to trail lines containing none of the review or reply text (`phi_redacted: true`),
and no file in the expanded `company.backup_set(slug, pack)` contains any of that text either; a
OtherCompany-host `browser_type` whose identity hit cannot be attributed to exactly one company lands
in `S/unattributed_trail.jsonl` with `phi_redacted: true`, `result_excerpt: null`, and none of the
fixture's typed text (RED when the unattributed sink keeps the committed shape); a OtherCompany record
whose `result_excerpt` trips `looks_like_credential_context` still ends with `result_excerpt: null`
(RED when the hipaa shaping runs before `finalize_record`); a
mutating OtherCompany-host browser call on `playwright-gtm` whose `attribute_company` result is
`None` but whose `identity_hit` is `othercompany` is hipaa-shaped in `S/unattributed_trail.jsonl`,
and one attributed to a non-hipaa fixture company whose `identity_hit` is `othercompany` is
hipaa-shaped in that company's trail (each RED when `hipaa_shape` is called only on
`packs.get(company)`); a OtherCompany record with the OtherCompany pack made unloadable is still
hipaa-shaped (RED when a missing pack counts as non-hipaa); a
`Bash` call `python3 /abs/tools/gtm/act.py lead-append --company othercompany --file
<PHI1 fixture home>/.claude/gtm/drafts/lead.json` (the absolute fixture home path, so the
committed Bash attribution — `str(home) in command` — attributes it; DECIDED (wave1c): no new
attribution rule, an `act.py` command whose text names no registered home is not harvested, as
today) harvests to `detail: {"argv0": "act.py", "act": {"subcommand": "lead-append", "action":
null, "ticket": null, "company": "othercompany"}}` (RED when `argv0` is read from the interpreter
token), and a browser record's `url` is exactly the host.

### 3.16 Transcript index (WP-G `transcript_index.py`; used by A1, A2, G)

`S/transcript_index.json`:
```json
{"schema": "gtm.transcript_index.v1", "built_at": "…", "projects_root": "/Users/…/.claude/projects",
 "files": {"<abs path>": {"mtime": 1727449445.1, "size": 12345, "oi_offset": 11800}},
 "agents": {"a0dfc0e0677bc8f1e": {"path": "…/subagents/agent-a0dfc0e0677bc8f1e.jsonl", "session_id": "…", "cwd": "…", "project_dir": "…", "workflow": false}},
 "sessions": {"<session_id>": {"path": "…/<session_id>.jsonl", "cwd": "…", "project_dir": "…"}}}
```
API (module-level functions):
```python
def refresh(*, full: bool = False) -> dict          # incremental by mtime; one walk of R/projects/**/*.jsonl, skipping by NAME (before descending) every top-level project dir equal to or prefixed by the Agency project-dir prefix (00_global_paths.md §0.1, F9)
def lookup_agent(agent_id: str, *, refresh_if_missing: bool = True) -> dict | None
def lookup_session(session_id: str) -> dict | None
def agent_transcript_path(agent_id: str, *, session_id: str | None = None, cwd: str | None = None) -> Path | None
    # fast path: R/projects/<project_dirs.project_dir_name(cwd)>/<session_id>/subagents/agent-<id>.jsonl; else lookup_agent
def operator_input_hits(since_ts: str) -> list[dict]   # side-index lines with ts >= since_ts (IMP-09, below)
def files_modified_between(t0: datetime, t1: datetime) -> list[Path]
    # paths from transcript_index.json["files"] with t0 <= mtime <= t1 (Agency dirs excluded exactly as refresh);
    # used by 02_act.md §2.11's trail harvest. The current session's transcript is lookup_session(session_id)["path"].
```
**Operator-input side index (IMP-09; used by the 02_act.md §2.11 card-authorship scan).**
`S/transcript_index_oi.jsonl` (under `S/transcript_index.lock`): `refresh()` appends, reading each
transcript only from its last indexed byte offset (kept per file in `transcript_index.json`
`files[<path>].oi_offset`), one line `{"file", "offset", "ts", "session_id", "agent_id", "tool",
"target_realpath"}` per `Write`/`Edit`/`MultiEdit`/`NotebookEdit`/`Bash` tool_use whose input text
names the basename or realpath of any GTM home's operator-input file (Agency project dirs skipped
exactly as above); `ts` is the tool call's own timestamp, never the operator-input file's mtime.
`--full` rebuilds it. Cost: incremental `refresh()` is proportional to bytes appended since its last
run; the one-time initial build runs outside every lock (never inside `actions.lock`) — G test on a
generated 20,000-file corpus: the initial build completes ≤ 10 min and a following incremental
refresh with ≈ 200 new lines ≤ 5 s, and a transcript that never names an operator-input file
contributes no line.
Transcript location (probe c): `R/projects/<project-dir>/<parent-session>/subagents/agent-<agentId>.jsonl`;
Workflow legs under `subagents/workflows/wf_*/`. Project dir name = `project_dirs.project_dir_name(home)`
for GTM homes; the Agency prefix is `project_dirs.project_dir_name_text(A)` (text only, 00_global_paths.md §0.1;
`tools/gtm/project_dirs.py`, IMP-15).
The index never contains a path under an Agency project dir; every consumer that scans transcripts
(02_act.md §2.11 harvest and card scan, `ai_budget` attribution, `secret_sink`) takes its file list from the
index or applies the same name filter. Test: a fixture `R/projects/<P_A>/…jsonl` and
`R/projects/<P_A>--claude-worktrees-x/…jsonl` are never opened (monkeypatched `open`/`os.scandir`
raise), while a sibling CSA project dir is indexed.
**Scope residual (stated; 00_global_paths.md §0.1 "Second accepted residual", requests/00_global_paths.md
R32):** the name filter sees only project dirs named after Agency, so Agency work done in a session
whose project dir is not `P_A`-prefixed (started in `~` or `~/Desktop`) is indexed like any other
dir. Accepted, not closed. **Binding rule:** every consumer of this index (the §2.11 harvest and card
scan, `ai_budget` attribution, `secret_sink`) keeps only the fields its own contract names (agent
ids, session ids, paths, Edit targets, secret-match locations, offsets) and never copies transcript
**text** from a dir that is not a GTM home's (or the OtherCompanyB legacy dir) into any GTM record; the
side index above stores no text either.
CLI: `python3 <R>/tools/gtm/transcript_index.py refresh [--full]` → prints `{"ok": true, "files":
N, "agents": N, "sessions": N, "changed": N}`; `lookup --agent <id> | --session <id>` → prints the
entry or `null`. Exit 0 ok, 1 internal, 2 usage, 3 `test_mode_real_state` (§3 intro), 12 lock
timeout (`S/transcript_index.lock`).

### 3.17 `ST/autonomy_state.json` (A1 writes demotions; WP-G `autonomy_ladder.py` writes re-promotions)

```json
{"schema": "gtm.autonomy_state.v1",
 "company": {"level": "shadow|autonomous", "since": "…", "decided_by": "criteria|operator_ok", "criteria": {…shadow-exit JSON…}|null},
 "systems": {"gbp": {"level": "shadow", "since": "…", "reason": "breaker:verify_failed x2",
  "clean_since": null, "demotions": 1, "pause_file": "PAUSE.gbp"}}}
```
Absent system = no demotion. Absent `company` key = company level `shadow`. Writers hold
`ST/autonomy_state.lock`. `pause_file` = the pause the breaker wrote with this demotion (null when
none, e.g. an isolation hit with no system). `autonomy_ladder.py promote` restores a **system's**
`level: "autonomous"` after 7 clean days (§20.6); never for money; it never touches the `company`
key. **Re-promotion lifts the breaker's pause (FID-11; plan §20.6 "automatic re-promotion after 7
clean days", §20.11 "breakers are not cards"; decided in 02_act.md §2.9, Option A):** a **clean day**
(company-local) counts only when that system has ≥ 1 successful observation that day — a
`verified` (pass) event on one of its actions, or a `snapshot_recorded` event whose paths include a
`<system>_*.json` snapshot — and no `verify_failed`, `breaker` or isolation hit on it; a day with no
observation is not clean, so days merely spent blocked never accrue. `clean_since` = the first day
of the current unbroken run of clean days (reset to null by any non-clean day). On promotion the
ladder also removes `pause_file` — only while that file still reads `created_by: "breaker"` with a
null `ruling_ref` (never an operator, migration, hand-made or ruled pause) — via
`pauses.remove_pause`, appends a `resume` event with `lifted_via: "ladder_promote"`, and writes an
`info` notice with push; any other pause on the system is left in place and reported.
**Isolation-hit pauses (DECIDED HERE; narrows plan §20.6 "automatic re-promotion after 7 clean days"
on the isolation path only, deliberately — the operator's rulings call a cross-business connection
not cleanly reversible, so a week of reads is no evidence its cause is gone).** The ladder never
lifts a breaker pause whose content `cause` is `isolation_hit` — or whose `cause` is absent or
unreadable (fail-safe, §3.10) — and never promotes that system while the pause stands: `promote`
lists it under `still_demoted` with `blocked_by` naming the pause and `"reason":
"isolation_hit_needs_operator"`. Such a pause lifts only by the operator's signed marker or an
approving `resume <pause file name>` card (§3.10 "Lifting card"), after which the system accrues
clean days and promotes normally. Plan §20.11 ("breakers are not cards") is unaffected: the
breaker still fires with no card; only its automatic **lift** is withdrawn. Breaker pauses for
every other cause (`verify_failed`, `created_not_paused`, …) keep FID-11's automatic lift. G test:
an isolation-hit breaker `PAUSE.meta` (`cause: "isolation_hit"`) with 7 clean observed days is not
removed and the system stays demoted (RED when the exclusion is removed); the same with `cause:
"verify_failed"` is lifted; a breaker pause with no `cause` key is not lifted.

**Leaving shadow (F-shadow; DECIDED HERE; plan §20.6 "14 days per company as gate verification
(operator may end early)", §0 P7).** The company level is written **only** by `act.py autonomy`
(02_act.md §2.4, A1), never by editing `company.json`: `effective_autonomy` treats the company as
`autonomous` only when `pack.autonomy.level == "autonomous"` **and** `company.level ==
"autonomous"` here (02_act.md §2.6 rule 6), so a pack edit alone (agent-editable, committed through ordinary
review) never starts autonomous execution, and a pack set back to `shadow` always wins. `act.py
autonomy --level autonomous` requires one of: (i) `autonomy_ladder.shadow_exit(ctx) -> dict`
(WP-G; CLI `autonomy_ladder.py shadow-exit --company X`) reporting `{"met": true, …}`, where met =
**all** of: ≥ 14 days between the company's first cycle record (`ST/cycles/`, any kind) and now;
`activity_log_unexplained_changes_7d == 0` and `isolation_guard_hits_28d == 0` computed over the
whole shadow window (§3.19 formulas, window widened — the unexplained count through
`trail_audit.audit(ctx, start=…, end=…)` with its grouped system equality, §3.19, never
`activity_log.py audit`'s exact-string match); every `would_execute` event in the window has
its action's `tier` and every required lane's `review` recorded on the current digest; and ≥ 2
consecutive completed `weekly` cycle records each with a rendered perf report
(`ST/reports/perf_<slug>_*`); and **carry-in complete** — every pause the company's P1 carry-in
lists (§3.10, `pause_carry_in.py`'s recorded list) is present as a pause file — each criterion reported as `{"name", "met", "value", "detail"}`;
(ii) a valid single-use **signed** operator marker `S/operator_ok/autonomy.<slug>.autonomous.json`
(00_global_paths.md §1.4 "Operator authority": a GTMApprover-signed `gtm.operator_ok.v1` record with
`command: "autonomy"`, `target: "autonomous"`, verified against HEAD's approver key, `now < expires ≤
now + 15 min`, nonce consumed with holder `operator-ok:autonomy:autonomous` (§3.9) and the file
deleted before the level changes; 02_act.md §2.3 "Operator marker" — never a TTY or environment test
and never an unsigned file, IMP-03; the operator ends shadow early; HEAD with no approver key →
exit 11 `approver_not_installed` for this route only). **There is no card route (DECIDED in
00_global_paths.md §1.4 "Operator authority"; requests/00_global_paths.md R39):** the plan ties no
lift card to leaving shadow ("operator may end early" is an operator act), and shadow is the safe
state, so `autonomy --card` is withdrawn — an approved card neither satisfies nor bypasses (i) or
(ii) (FID-01; requests/03_schemas.md R63 → 02_act.md §2.4/§2.2b). Before the approver is installed
the company stays in shadow until its criteria are met. The decision, its source and the
criteria JSON are written to `company` and appended as an `autonomy_level` event. `--level shadow`
is always allowed. A1 tests: `autonomy --level autonomous` from a GTM session exits 3
`shadow_criteria_unmet` when any criterion is unmet (one fixture per criterion, including one
where a carried-in `PAUSE.website_wordpress@remodeling` file is missing) and succeeds once
all are met; with `pack.autonomy.level: "shadow"` the company stays shadow even after a recorded
`autonomous`; editing only `company.json` to `autonomous` leaves `authorize` at `would_execute`;
`autonomy --level autonomous --card <a card approved with subject "autonomy <slug> autonomous">`
with criteria unmet and no marker (RED when `--card` is re-admitted), `env -u CLAUDECODE script -q /dev/null …act.py autonomy …` with no marker, and an
**unsigned** marker in the retired `{command, company, target, created_at}` form (left in place) all
exit 3 (13 when run outside a GTM session) and leave the company in shadow (FID-01, IMP-03); a valid
signed marker succeeds once, records `decided_by: "operator_ok"`, and a restored copy (same nonce) is
refused (RED when the signature or nonce check is removed).

CLI (WP-G): `python3 <R>/tools/gtm/autonomy_ladder.py promote --company X [--dry-run]` → for each
demoted system with ≥ 7 consecutive clean days (above), sets `level: "autonomous"`, lifts its
breaker pause as above, and writes the `info` notice; prints `{"ok": true, "promoted": [{"system",
"pause_lifted": "<name>|null"}], "still_demoted": [{"system", "clean_days", "blocked_by": ["<pause
name>", …], "reason": "isolation_hit_needs_operator"|null}]}`. G tests (FID-11): 7 clean days with a daily snapshot → promoted and the breaker
pause removed; 7 days with no observation → not promoted; an operator pause on the same system, and
a breaker-written pause whose `created_by` was changed to `operator`, are never removed. `status --company X`
prints the file. `shadow-exit --company X` prints the §3.17 criteria JSON (read-only; it never
writes the company level). All three build their context with `gtmlib.make_ctx`. Exit 0 ok (also
when nothing promoted, and for `shadow-exit` whether or not `met`), 1 internal, 2 usage, 12 lock
timeout, 13 company (IMP-17); exit 3 only for `test_mode_real_state` (§3 intro).

### 3.18 `metrics.json` (WP-F `metrics.py`; owner seat measurement-architect)

```json
{"schema": "gtm.metrics.v1", "metrics": [
  {"id": "crm_leads_logged_last_7d", "definition": "…", "instrument": "lead sink rows with received_at in trailing 7 days",
   "owner_seat": "measurement-architect", "direction": "up|down|range", "unit": "count",
   "target": {"value": 6, "by": "2026-11-01", "evidence": "tracking/METRICS.md §1"} , "guardrail": null,
   "brand": null, "added_ts": "2026-09-27T00:00:00Z", "exactness": "exact|best_effort"}]}
```
Top-level key `schema` = `"gtm.metrics.v1"` like every other file in this section (DECIDED HERE; the
former `schema_version: 1` spelling is not accepted — `metrics.py validate` refuses it, exit 3).
Ids are never redefined (validator refuses a changed `definition` for an existing id). Rendered to
`METRICS.md` next to it. Scoreboard (`paths.scoreboard`) keeps **exactly** the existing OtherCompanyB
columns `date,metric_id,value,unit,source,note` (append-only; **DECIDED HERE**: brand is encoded in
`metric_id`, as OtherCompanyB already does). `scoreboard.py add --company X --metric <id> --value <v>
--unit <u> --source <s> [--note N] [--date YYYY-MM-DD] | --from-agent <analyst agent_id>` (reads
`gtm-result.scoreboard[]`). Missing is never 0 (renders `missing`). `metrics.py` CLI:
`add --company X --file <metric.json>` (refuses a changed `definition` for an existing id),
`render --company X`, `validate --company X`; every pack's `metrics.json` is seeded (WP-F) with the
four §0 program metric ids defined in §3.19 (`activity_log_unexplained_changes_7d`,
`platform_changes_unlogged_7d`, `isolation_guard_hits_28d`, `recurring_ops_missed_7d`).
**Exit codes (I15):** `scoreboard.py`, `metrics.py`, `experiments.py` — 0 ok, 1 internal, 2 usage,
3 refused (unknown metric id, redefined metric, bad value/unit, unreadable `--from-agent`
result, `test_mode_real_state` — §3 intro), 12 lock timeout, 13 company.

`ST/experiments.jsonl` (WP-F `experiments.py`; appended under `ST/experiments.lock`, which also serializes `exp_<slug>_<NNNN>` allocation): `{"experiment_id", "ts", "event": "open|result|decision",
"hypothesis", "metric_id", "variants": [...], "window": {"start", "end"}, "min_sample", "result",
"decision", "action_ids": []}`. A "try X" proposal cites the experiment id in `why.plan_ref`
(`exp_<slug>_<NNNN>`).

### 3.19 Perf report + session spend (WP-G)

- `perf_report.py --company X|--all --days 28 [--open]` → `ST/reports/perf_<slug>_<YYYY-MM-DD>_<N>d.{md,html,json}`
  (`--all` → `S/reports/perf_all_<date>_<N>d.*`). JSON top keys: `cost` (per seat/run kind/model:
  dispatches, tokens by class, usd or `"unpriced"`), `quality`, `reliability`, `program` (the §0
  metrics, below), `outside_unknown` (the list below), `outcome_association` (suppressed below 20
  actions or 28 days), `unattributed`, `pricing` (`gtm_pricing.pricing_status()` plus any
  `ccdash_unpinned` note, below). Spend rows are deduped and attributed with
  `ai_budget.attribute_row` (04_hooks.md §4.6 precedence), the same function gate-gtm uses.
- `perf_report.py record-session --company X --run <run_id> --session <uuid>` (called by
  **`gtm_session.sh` itself after `claude` exits, for interactive and scheduled sessions alike**
  (I8, 07_notices_schedules.md §7.6; `run_gtm_job.sh` does not call it), with the session uuid and the run id — the
  scheduled `run_id`, or the interactive cycle id) appends to `ST/session_spend.jsonl` (under `ST/session_spend.lock`):
  `{"ts", "company", "run_id", "session_id", "model", "tokens": {input, output, cache_read, cache_creation, cache_creation_5m, cache_creation_1h}, "usd": <float|null>, "usd_exactness": "exact|best_effort|null"}` (`cache_creation_5m`/`_1h` null when the transcript lacks the split).
  Tokens are summed from the top-level session transcript's per-message usage. **Known blind spot
  (stated):** a session's own top-level tokens enter the weekly cap only after it exits; a running
  session's spend is invisible to gate-gtm until then (bounded by the 2 h alarm for scheduled runs;
  unbounded for a long interactive session — the weekly cap is detect-after for that part).
- **Exit codes (I15, IMP-17):** `perf_report.py` (report and `record-session`) 0 ok, 1 internal, 2 usage,
  3 unreadable input (transcript not found for `record-session`) or `test_mode_real_state` (§3 intro), 12 lock timeout
  (`ST/session_spend.lock`), 13 company.

**`quality` and `reliability` fields (F15; plan §12.2), per company and per seat, over the report
window.** Every field is `{"value", "numerator", "denominator", "source"}` (value `null` and
`"missing"` rendered when the denominator is 0 — never 0). **HIPAA free text (08_seats_wps.md §8.1
"HIPAA free text"; requests/08_seats_wps.md item 21):** for a `regulated ∋ hipaa` company the report
— every block, `quality` included — carries counts, codes, ids and digests only and quotes no
free-text string from a `gtm-result` (`findings[].text`, `reviews[].lines[].note`,
`audit_sample[].note`, `scoreboard[].note`, platform strings in `snapshots[]`/`change_history[]`); G
test: a hipaa fixture whose finding `text` and audit-sample `note` hold a sentinel string yields
report `.md`/`.html`/`.json` files without it (RED when the quote guard is removed):

| Field | Formula | Source ledger |
|---|---|---|
| `proposals` | count of `proposed` events | `actions.jsonl` |
| `first_pass_checker_rate` | actions whose **first** `review` event per lane (gtm-checker reviewer) was `pass` ÷ actions with ≥ 1 gtm-checker review | `actions.jsonl` `review` events |
| `audit_disagreement_rate` | `audit_sample[]` entries with `agrees_with_checker: false` ÷ all `audit_sample[]` entries | the final `gtm-result` (via transcript index) of the weekly W5 audit-sample dispatches — the seats dispatched with a ```` ```gtm-audit-sample ```` fence over `ST/audit_samples/<run_id>_<lane>.json` (02_act.md §2.4 `status --audit-sample`, 07_notices_schedules.md §7.5 W5; requests/08_seats_wps.md item 24) — for the window's weekly runs |
| `dissent` | given/received counts per seat | mission records' dissent ledger (`MISSION_SCHEMA.md`) |
| `refusals_by_reason` | `{code: count}` over `refused` events' `checks[].code` | `actions.jsonl` |
| `verify_failure_rate` | `verify_failed` ÷ (`verified` + `verify_failed`) | `actions.jsonl` |
| `reverts` | count of `reverted` events | `actions.jsonl` |
| `isolation_hits` | = `isolation_guard_hits_28d` (program block) over the window | §3.21 + enforcement log |
| `unexplained_changes_attributed` | clusters of `trail_audit.audit` (below) whose `explained_by` entry carries the explain marker (`notes` exactly `explain:<cluster id>`) ÷ all clusters of the window | `trail_audit.audit` (trail + activity log) |
| `missed_runs` | cycle records with `status ∈ {missed, failed}` + expected scheduled runs with no cycle record (from pack `cadence` and the fixed company-local `RUN_TIMES` imported from `tools/gtm/render_plists.py`, 07_notices_schedules.md §7.3 — inbox runs per slot, label `com.oversight.gtm.<slug>.inbox_<HHMM>` — only for labels whose `oversight_install.md` `expected_state` is `loaded`) | `ST/cycles/`, `oversight_install.md` §2 |
| `cycle_completion_rate` | cycle records `completed` ÷ all cycle records | `ST/cycles/` |
| `untagged_dispatches` | GTM-seat spend rows whose `gtm` is null **and** `attribute_row` yields `unattributed` | `spend.jsonl` |
| `unjoined_dispatches` | GTM-seat spend rows with `join_state ≠ "joined"` (informational: attribution no longer depends on it) | `spend.jsonl` |
| `expired_signins` | `signin_missing` notices opened in the window — produced by the inbox/daily sign-in step and `act.py ingest-findings` from an analyst `findings[]` entry of kind `signin_missing` (a runbook read path landing on a `login_hosts` page), 07_notices_schedules.md §7.1/§7.5 (FID-10) | `S/notices/<slug>/` |
| `skipped_runs` | heartbeats with `status ∈ {skipped-unsigned-caps, skipped-paused, skipped-disabled}` | `R/schedules/heartbeats/com.oversight.gtm.<slug>.*` |

**Program metrics (F7; plan §0 "gets results" bar).** Computed by `perf_report` and appended weekly
(by the weekly prompt, 07_notices_schedules.md §7.5) to the company's scoreboard with `scoreboard.py add --source
perf_report`; registered in every pack's `metrics.json` (§3.18). Each is per company, trailing
window ending at report time:

| Metric id | Definition | Source ledger | Window | Exactness |
|---|---|---|---|---|
| `activity_log_unexplained_changes_7d` | Σ `n_records` of the window's clusters with `explained: false` + the number of `offserver` tool_use_ids **not** among those clusters' records — both from `trail_audit.audit(ctx, start=end−7 d, end=now)` (below), so a record is never counted twice | `TOOL_TRAIL.jsonl` (its `offserver: true` flag is the **only** offserver source; the enforcement log's `gtm-offserver` rows are not read), activity log | 7 d | exact |
| `platform_changes_unlogged_7d` | platform change-history rows (§3.23 input) **not** explained, where explained = matched to a GTM `completed` action (§3.23 step 1), or identity **and** interface equal a declared `co_managing_systems[]` entry (step 2), or classified by `outside_actor.py classify` (§3.23 — joined through the row's `activity_log_id` and the decision entry's `notes == "classify:" + activity_log_id`, the one "Explained" rule there); every `outside:unknown` row counts here until classified, **and every `unmapped` row counts here always** (its system has no activity-log name, so it is unexplained by definition and can never be classified; DECIDED HERE, stated identically in §3.23) | `outside_actor` reconcile output (`ST/outside_actor/<run_id>.json`) + activity log | 7 d | `exact` per system where change history exposes identity + interface, else `best_effort`; a system with no change-history read in the window → `missing` for that system (never 0) |
| `isolation_guard_hits_28d` | **distinct events** (DECIDED HERE; one blocked call counts once, though G-A rule 4 both denies and writes an isolation hit): the union of (a) `S/isolation_hits.jsonl` rows with `company == slug` and `ts` in the window and (b) `R/.enforcement/log.jsonl` rows with `hook ∈ {gtm_browser_gate, gtm_bash_gate, gtm_phi_path_gate}`, `decision ∈ {deny, would-block}` (both: every GTM-scope deny of these hooks is unconditional, so a `would-block` row is a real block), `reason ∈ {agency-boundary, phi-host, phi-path, gtm-secret-read}` — **not** `identity-other-company`, `target-not-allowlisted` or `never-surface`, whose rule always writes the isolation hit counted in (a) — `company == slug` and `ts` in the window; deduplicated on `(session_id, tool_use_id)` when both are non-null (the log row's `session`/`tool_use_id` fields, the hit row's `session_id`/`tool_use_id`, §3.21), a row lacking either counting once on its own. G test: one rule-4 navigate that denies `identity-other-company` and writes one isolation hit counts **1** (RED when (a) and a log term for `identity-other-company` are summed); one phi-host navigate whose PreToolUse deny and PostToolUse isolation hit share a `tool_use_id` counts 1 (RED without the dedupe) | `S/isolation_hits.jsonl`, `R/.enforcement/log.jsonl` (those three hooks' deny rows carry `company`, `session` and `tool_use_id`, requests/03_schemas.md R86 → 04_hooks.md) | 28 d | exact |
| `recurring_ops_missed_7d` | = `missed_runs` above + heartbeats `skipped-unsigned-caps` (operator-chosen `skipped-disabled`/`skipped-paused` excluded) | `ST/cycles/`, heartbeats, `oversight_install.md` §2 | 7 d | exact; `missing` while no GTM job's `expected_state` is `loaded` |

The weekly report lists **every** `outside:unknown` row of the window (system, object, change, at,
identity, interface, source, `resolution: "unknown"`) under "needs owner classification"
(`outside_unknown` key), **and every `unmapped` row** in the same list with `resolution:
"unmapped"`, grouped per system (it needs a mapping, not a classification). G test: a fixture
change-history row on a system with no activity-log name makes `platform_changes_unlogged_7d` ≥ 1
and appears in `outside_unknown` with `resolution: "unmapped"` (RED when unmapped rows are excluded).

**`trail_audit.py` (WP-G; DECIDED HERE — the machine interface both program metrics above, the
`unexplained_changes_attributed` field and §3.17's shadow exit read; `activity_log.py audit` stays
the human report and is never parsed).** `tools/gtm/trail_audit.py` imports from `activity_log`
only `resolve_paths`, `read_jsonl`, `build_clusters`, `is_agent_actor`, `_parse_ts`,
`DEFAULT_AUDIT_EXCLUDED_SYSTEMS` and `CLUSTER_EXPLAIN_WINDOW_MINUTES`, and exposes:
```python
def audit(ctx, *, start: datetime, end: datetime | None = None) -> dict
# end defaults to gtm_env.now(os.environ) (never datetime.now(), so GTM_FAKE_NOW applies in tests); start is used as
# given — no clamp to the earliest manual entry (the caller picks the window). Returns
# {"window": [start, end],
#  "clusters": [{"id", "system", "group", "start", "end", "n_records", "explained": bool,
#                "explained_by": "<log entry id>"|null, "explain_marker": bool, "tool_use_ids": [...]}],
#  "offserver": ["<tool_use_id>", ...]}
```
`clusters[].id` is `Cluster.cluster_id` verbatim (`<YYYYmmddTHHMMSS of start>_<session_id[:8]>_<trail
system>`, `activity_log._make_cluster`) — the exact string `activity_log.py explain --cluster`
accepts and the explain marker `notes explain:<cluster id>` embeds; `trail_audit` never builds an id
of its own. Clusters are `build_clusters` over the company's mutating trail records minus
`DEFAULT_AUDIT_EXCLUDED_SYSTEMS`, kept when `end_c ≥ start` and `start_c ≤ end`. **Explanation
equality (the one rule; the same grouping 02_act.md §2.11 uses):** a cluster is explained by an
activity-log entry whose actor passes `is_agent_actor`, whose `ts` lies in the closed interval
`[cluster.start − W, cluster.end + W]` with `W = timedelta(minutes=CLUSTER_EXPLAIN_WINDOW_MINUTES)`
(15 today — `activity_log.cluster_is_explained`'s interval), and whose system satisfies
`trail_group(tier_system_of(trail.system, pack)) == trail_group(tier_system_of(entry.system, pack))`
(§3.22; brand ignored) — so a Meta Ads browser write the harvester files as `facebook_remodeling`
(or `facebook`) is explained by act.py's `meta_ads` entry, and a OtherCompanyB GBP edit filed as
`gbp_remodeling` by `gbp_restoration`'s entry. `explained_by` = the earliest such entry;
`explain_marker` = that entry's `notes` equals `explain:<cluster id>`. **Every GTM caller of
`activity_log.py explain` passes `--notes explain:<cluster id>`** (requests/03_schemas.md R75 →
07_notices_schedules.md §7.5 W2 and 08_seats_wps.md `/gtm-audit`). `offserver` = the
`tool_use_id`s of mutating trail records with `offserver: true` and `ts` in the window. P2 tests
(G): a verified GTM `meta.adset_budget_edit` executed through the browser (trail system
`facebook_remodeling` on the OtherCompanyB fixture) plus its act.py `meta_ads` log entry gives 0
unexplained records (RED when equality is the exact string); an owner-actor entry never explains; a
cluster closed by an `explain` entry with the marker counts in `unexplained_changes_attributed`'s
numerator and one closed by an ordinary agent entry does not; an offserver record inside an
unexplained cluster is counted once; under `GTM_FAKE_NOW` the window follows the fake clock.
- JSON also carries `co_actor_writes_7d: {"<tier system>": {"count": N, "exactness":
  "exact|best_effort"}}` — keyed by the activity-log entry's `system` normalized with
  `system_names.tier_system_of` (F-cosys) — count of `outside:<co_system>` activity-log entries (declared
  co-managing systems only; `outside:unknown` rows are counted in `platform_changes_unlogged_7d`,
  not here) in the trailing 7 days (§3.23); `exact` only where the platform change history exposes
  identity + interface (Google Ads `change_event`), else `best_effort` (snapshot diff).
- Pricing: **`knowledge/model_prices.json` is NOT created** (§17 build-time finding supersedes §12.2;
  WP-G's file list entry is void). **DECIDED HERE:** WP-G creates `tools/gtm/gtm_pricing.py`:
  `price_usd(model: str, tokens: dict, when: datetime) -> float | None` (ccdash
  `usage-dashboard/ccdash/pricing.compute_cost_usd` first, `telemetry/pricing.json` fallback; `None`
  = unpriced, never guessed), `pricing_status() -> {"ccdash": "pinned|unpinned|absent",
  "telemetry_version": str}` and `model_bucket(model) -> "opus" | "sonnet"` (DECIDED HERE: a
  case-insensitive **substring** test on the full model id — `opus` or `fable` anywhere →
  `opus`, e.g. `claude-opus-5-5[1m]`; `sonnet` or `haiku` anywhere → `sonnet`; **a null, empty,
  `<synthetic>` or unrecognized model → `opus`**, the conservative bucket, with `price_usd`
  returning `None` (`unpriced`) and the caller recording the note `model_unknown` — so an
  unknown-model row is never charged to the cheaper cap). G test: `claude-opus-5-5[1m]` and
  `claude-fable-5-1` → opus, `claude-haiku-4-5-20251001` → sonnet, `None` → opus + unpriced. gate-gtm and perf_report both use it. **Trust (IMP-05; decided in
  05_approver.md §5.5 step 2):** the ccdash file is git-ignored in `~/.claude`, so it cannot be a
  TRUST_PATH; `gtm_pricing.py` (a TRUST_PATH) pins `CCDASH_PRICING_SHA256`, hashes the ccdash
  file's bytes **before importing anything from it** and loads the module from those same bytes
  only on a match; otherwise it prices from `telemetry/pricing.json` alone (a TRUST_PATH, parsed
  with `json` by `gtm_pricing` itself, never through `hooks/cycle_telemetry.py`). While
  `pricing_status()["ccdash"] != "pinned"` every figure is labelled `best_effort` and the caller
  records the note `ccdash_unpinned` (perf_report: the `pricing` key; gate-gtm/`ai_budget`:
  04_hooks.md §4.6). `system_names.seat_sets()` (used by §3.13 and `validate_run`) is the union of the
  committed constants and `knowledge/model_policy.json` (04_hooks.md §4), so a policy edit can add a
  GTM seat but never drop one from cap or dispatch enforcement. **Cache split (DECIDED HERE):**
  transcripts carry `message.usage.cache_creation.{ephemeral_5m_input_tokens,
  ephemeral_1h_input_tokens}`; `record-session` sums them into `tokens.cache_creation_5m` /
  `tokens.cache_creation_1h` (alongside the total `cache_creation`), and GTM spend lines get the
  same two keys only through §3.13 "Cache-creation split on GTM lines" (a WP-B2 change, scoped to lines whose `gtm` is non-null;
  `sum_transcript_tokens` and every other spend line are unchanged; `tokens_total` stays the
  four-key sum), and `price_usd` prices each at its own rate — `exact` when the split is
  present for every message. Only when a row or message lacks the split does `price_usd` pass that
  part as `cache_creation_5m` (0 as `1h`) and the caller label the figure `best_effort`. It never
  invents a 1 h share.
- `validate_run.py` (WP-G): `python3 <R>/tools/gtm/validate_run.py --company X --run <run_id>`
  checks the run's cycle record against `S/dispatch_tags.jsonl` and spend rows (§3.13: every
  GTM-seat spend row of the run attributes — via `ai_budget.attribute_row` — to this `run_id`;
  dispatch count ≤ cap; a GTM-seat row is a problem only when its attribution is `unattributed`),
  the `actions.jsonl` chain (`store.verify_chain` semantics, 00_global_paths.md §0.3), and that every `completed`
  action has an activity-log entry — **except** (F-unlogged) actions of system `gtm_ai` and actions
  whose `completed` event carries `activity_log_error: "activity_system_unmapped"` (02_act.md §2.10: no
  activity-log system exists for them by design), which are listed separately under
  `unlogged_by_design` and never counted as problems; an `activity_log_error` starting
  `activity_log_render_error:` (the line was appended and an `activity_log_id` exists; only the
  render failed, 02_act.md §2.10, IMP-18) counts as logged; any other `activity_log_error` **is** a
  problem (`activity_log_failed`). Prints `{"ok": bool, "problems": [{"code", "detail"}],
  "unlogged_by_design": [{"action_id", "system", "reason"}]}`. Seat sets come from
  `system_names.seat_sets()`; spend rows are attributed with `ai_budget.attribute_row(row,
  ctx=ai_budget.load_attribution_ctx(now, window_start))`. A `--run` id that fails `CYCLE_ID_RE` →
  exit 2; one that fails `system_names.cycle_id_ok` → exit 3 `bad_cycle_id_hhmm`, nothing read
  (requests/00_global_paths.md R40). **`--since-last-daily`** (in place of `--run`;
  requests/07_notices_schedules.md R57, the 07_notices_schedules.md §7.5 D9 form): lists
  `ST/cycles/cyc_<slug>_*.json`, takes `P` = the latest company-local date (pack `timezone`) of a
  `daily` record before today (none → yesterday; never more than 14 days back), validates every
  cycle whose id date lies in `[P, yesterday]` exactly as `--run` does, and prints `{"ok",
  "window": [first, last], "runs": [{"run_id", "ok", "errors": <n>}]}`. Exit 0 no problems (every
  run, in either form), 1 internal, 2 usage, 3 problems found (any run, listed), 13 company
  (IMP-17; exit 1 stays internal-only, so a failing run is 3, not R57's 1). G tests: a completed
  `gtm_ai.weekly_cap_edit` and a completed `sms.message_send` with `activity_system_unmapped` yield
  exit 0 and two `unlogged_by_design` entries; a Monday fixture with Friday daily + inbox and
  Saturday weekly records under `--since-last-daily` (run on Monday) validates exactly the runs dated
  Friday through Sunday, and a 20-day gap validates 14 days.
- `kb_freshness.py` (WP-G): `python3 <R>/tools/gtm/kb_freshness.py [--max-age-days 180] [--json]`
  lists `knowledge/marketing_kb/**` claims whose `verified_at`/source date is older than the limit
  or marked UNVERIFIED. Prints `{"ok": bool, "stale": [{"path", "claim", "age_days"}],
  "unverified": [...]}`. Exit 0 none stale, 1 internal, 2 usage, 3 stale/unverified found (report,
  not failure) (IMP-17).
- `mission_record.py` (WP-G; **DECIDED HERE**, replaces Write-tool landing of mission JSON now that
  G-W denies `*.json`/`*.jsonl` directly in `paths.missions_dir`):
  `python3 <R>/tools/gtm/mission_record.py write --company X --mission <gtm_YYYY_MM_DD_slug> --file <json>`
  validates against `MISSION_SCHEMA.md` and writes atomically into `paths.missions_dir`;
  `append-dispatch|append-artifact --mission <id> --file <json>`. Exit 0 ok, 1 internal, 2 usage, 3 schema
  refusal or `test_mode_real_state` (§3 intro), 13 company (IMP-17). WP-I updates `MISSION_SCHEMA.md` (incl. a top-level `session_id` field, used
  by the 04_hooks.md §4.6 attribution precedence) and `agents/marketing-director.md` (landing agent runs this CLI
  instead of Write) in the same wave; G-W's missions clause is registered only after both land
  (04_hooks.md §4.8). Until WP-I lands, `mission_record.py` validates against the **current** `MISSION_SCHEMA.md`
  and treats `session_id` as optional (I19: G consumes I).

### 3.20 `phi_denylist.json` (WP-M seeds via `gtm_lists.py`; read by G-A, G-B, the path gate, `connectors.http_request`, `connector_dispatch.credential_getter`)

```json
{"schema": "gtm.phi_denylist.v1", "updated_at": "…",
 "paths": ["/Users/x/Desktop/OtherCompany Files/<listed folder>"],
 "hosts": [{"host": "<open dental server host>"}, {"host": "<agency app host>", "applies_to": ["othercompany"], "agency_app": true}, {"host": "<other>"}],
 "host_suffixes": [{"suffix": ".example-opendental-tenant.com"}],
 "url_prefixes": [{"url_prefix": "https://<host><path>"}],
 "agency_gsm_projects": ["<agency GCP project id>"],
 "notes": [{"entry": "…", "why": "…", "source": "listing only, trust-architect reviewed"}]}
```
Paths absolute (no `~`), hosts lowercase. **`applies_to` is allowed only on `agency_app: true`
host entries (DECIDED HERE; plan §20.3 bans OtherCompany's Open Dental instance and its data for
every GTM session and seat):** §20.3's Agency app hosts are entered with `applies_to:
["othercompany"]` so they never block OtherApp's own marketing hosts; every other entry — in
particular every Open Dental instance entry (server and database hosts, eServices / web-sched
tenant hosts and suffixes) and every `paths` entry — never carries `applies_to` and applies to
**every** company, OtherApp included (OtherApp markets its Open Dental integration, which makes it
the pack most likely to reach that host). `gtm_lists.py` validation refuses `applies_to` on a
host entry without `agency_app: true` and on any `host_suffixes` entry
(`phi_denylist_scope_invalid`). **`url_prefixes` (DECIDED HERE; 08_seats_wps.md §8.1 "URL evidence",
Appendix B #221; requests/08_seats_wps.md item 38)** lists single PHI-bearing pages on hosts that are
not themselves denylisted (e.g. a patient form link): each `url_prefix` is `https://`, host
lowercase, no query or fragment, path `/` when empty, and never carries `applies_to` (it binds every
company); `gtm_lists.py` refuses a non-`https` prefix, a query or fragment, or an `applies_to` key on
one (`phi_denylist_scope_invalid`). A URL matches when its host equals the entry's host and its path
equals the entry's path or continues it at a `/` boundary (`…/r/abc/page2` matches `…/r/abc`;
`…/r/abcd` does not); G-A's `phi-host` rule and `connectors.http_request`'s host guard deny a match
exactly as a host hit. G-A test: a OtherApp-session `browser_navigate` to the fixture
Open Dental host is denied (`phi-host`), and a `phi_denylist.json` whose Open Dental entry carries
`applies_to: ["othercompany"]` is refused by `gtm_lists.py`; each goes RED when its clause is
reverted. Paths always apply to every company. **Agency boundary (plan §20.9/§20.9a; 06_connectors.md §6.3/§6.5b):** a host entry may
carry `"agency_app": true` — such a host is denied to **every** company's connector
(`connectors.http_request`), independent of `applies_to`; the Agency/OtherApp app hosts entered with
`applies_to: ["othercompany"]` carry it. **Browser rule for `agency_app` hosts (DECIDED HERE; plan
§20.9, card [125] "never from here"):** for `othercompany`, G-A denies every call to such a host
(`applies_to` applies, `phi-host`). For **every other company** G-A admits only **ticketless,
non-mutating** reads there (a navigate, snapshot or screenshot — so OtherApp's marketing surface on a
shared host can be looked at) and denies every mutating call and every call under a write, batch,
setup **or read** ticket with reason `agency-app-write` (unconditional in GTM scope, no isolation hit —
it is not another company's asset); and the runbook validator (L) refuses any runbook whose
`read_hosts`, `login_hosts` or `writes[].allowed_hosts` names a host equal to or under an
`agency_app` host (`runbook_agency_app_host`), and `ticket --read/--write/--write-batch/--setup`
refuses such a host (exit 3 `ticket_host_agency_app`) — so no GTM runbook ever logs into, reads
through a ticket, or writes the Agency app (requests/03_schemas.md R88 → 04_hooks.md §4.1,
06_connectors.md §6.4b, 02_act.md §2.4). G-A test: a OtherApp-fixture ticketless `browser_navigate`
to the fixture `agency_app` host is allowed and a `browser_click` there is denied
`agency-app-write`; a OtherCompany navigate there is denied `phi-host`; a fixture runbook listing that
host in `read_hosts` is refused by the validator; each RED when its clause is removed. Top-level `agency_gsm_projects` lists GCP projects that
`connector_dispatch.credential_getter` refuses for every company. **Seeding (DECIDED HERE; plan
§20.9a "No GTM build step … ever opens, lists, greps … `~/Desktop/OtherApp`"):** WP-M seeds it from
plan §17 d's recorded fact (`otherapp`) plus any value the operator supplies (an OPERATOR-ONLY card
when a value is unknown); the Agency app hosts in `hosts[]` come from public facts (the apps'
public URLs) or the operator only. **No WP lists, reads, greps or otherwise opens
`~/Desktop/OtherApp`, its project dirs, or its GitHub repository to fill §3.20** — there is no
"Agency list-first procedure" (the §20.2 list-first procedure is for `~/Desktop/OtherCompany
Files/` only, below; requests/03_schemas.md R49 → 08_seats_wps.md WP-M). Both connector readers fail closed on an unreadable **or absent** file
(`phi_denylist_unreadable`). **Hook readers (G-A, G-B, the path gate) — fail closed (DECIDED HERE;
plan §20.3's host deny, path gate and G-B ancestor rules; replaces the former "OtherCompany folder
only" rule, which silently disabled every host, suffix, URL-prefix and non-OtherCompany path entry).**
In a GTM session, or for a GTM seat, a `phi_denylist.json` that is **unreadable, unparseable or
schema-invalid** (any key or entry that `gtm_lists.py` validation would refuse) is never read as an
empty list; while it stays that way: (1) **G-A** denies `browser_navigate`, and every ticketed call,
to any host that is not in the pack's identity allowlist (`brands[].domains` ∪
`identity_allowlist.domains`, subdomains included) or in the read/login hosts of the runbooks for
the pack's `scope.channels_in_scope` (`runbook_hosts`, §3.22); (2) the **path gate** and **G-B**
deny every Read/Grep/Glob/Bash target that is not equal to or under `H`, `R/tools/gtm` or
`R/knowledge/marketing_kb`; (3) each denial logs `phi-denylist-unreadable` (with the hook, the
session and the target host or path class — never file content), and the first one per session
writes an `urgent` `trust` notice with push, title "PHI denylist unreadable — GTM browsing and file
reads restricted" (`dedupe_key` `phi_denylist_unreadable:<slug>`). An **absent** file gets the same
fail-closed treatment for any session whose pack is `regulated ∋ "hipaa"` **or carries
`phi_adjacent: true`** — a pack flag, never a slug test (DECIDED HERE; the runtime is
company-agnostic): an optional boolean in `company_schema.json` meaning "this company markets or
operates an integration with a PHI-bearing system (e.g. Open Dental)", set on the OtherApp pack by
WP-M from plan §17 d and required by the pack review for any pack that declares such an
integration; `company.py validate` refuses `phi_adjacent: false` together with a non-empty
`regulated` (requests/03_schemas.md R87 → 08_seats_wps.md Appendix C). For other packs an absent file is
read as empty (it is created by WP-M at P1, before any GTM seat runs) and logs
`phi-denylist-absent` once per session. The OtherCompany read allowlist below still default-denies
under `~/Desktop/OtherCompany Files/` in every case. G tests (each RED when the fail-closed branch is
reverted to "empty list"): with a corrupt fixture file, a GTM-session `browser_navigate` to the
fixture Open Dental host is denied, and a Read of a fixture denylisted path outside the OtherCompany
folder is denied, each logging `phi-denylist-unreadable` and writing one `trust` notice; with the
file absent on a OtherCompany-fixture session the same navigate is denied, on a fixture pack with
`phi_adjacent: true` (slug `zeta`, no `regulated`) it is denied too (RED when the rule tests a slug),
and on a OtherCompanyB-fixture session a navigate to a pack domain is allowed (requests/03_schemas.md R76 → 04_hooks.md §4.1/§4.4).

**OtherCompany read allowlist (§20.2 list-first procedure; DECIDED HERE).** `S/othercompany_read_allowlist.json`:
```json
{"schema": "gtm.phi1_allowlist.v1", "reviewed_by": {"seat": "trust-architect", "agent_id": "a…"},
 "reviewed_at": "…", "listing_sha256": "<hex of othercompany_listing.json bytes>",
 "folders": ["/Users/x/Desktop/OtherCompany Files/<cleared folder>"]}
```
The path gate (04_hooks.md §4.4) and G-B rule (j) **deny** any Read/Grep/Glob/Bash target under
`~/Desktop/OtherCompany Files/` that is not equal to or inside an allowlisted folder — **default-deny
while the file is absent** — in GTM sessions and for GTM seats; the `phi_denylist` still wins inside
an allowlisted folder. WP-M procedure (a build agent, outside any GTM session, so the gate does not
bind it — this procedure does): (1) `gtm_lists.py phi1-listing --root "<path>"` walks names only
(`os.walk`, never opens a file) into `S/othercompany_listing.json` and prints its sha256 — it
**never descends** into a folder equal to or under a `phi_denylist.json` `paths` entry, recording
it once as `{path, kind: "dir", denylisted: true}` (requests/00_global_paths.md R22; G test: a
fixture denylisted folder's children are never listed, RED when the prune is removed). **The
listing carries directories only, and no name that can hold a patient's name (DECIDED HERE; plan
§20.4 "patient information encountered is not quoted"; 00_global_paths.md §1.2 concedes file names
"can carry patient names"):** `{listed_at, root, entries: [{path, depth, kind: "dir", files: <n
regular files directly inside>, bytes: <their total size>, ext_histogram: {"<lowercased extension
or '(none)'>": n}, denylisted?: true}]}` — **no file entries and no file names at all** (not
hashed, not written to any other file); a directory at **depth 1** (a direct child of `root`, the
granularity the review clears) appears by its absolute `path`; every directory **below** depth 1
appears only as `{"parent_depth1": "<its depth-1 ancestor's absolute path>", "depth", "name_sha256":
"<hex sha256 of its name>", files, bytes, ext_histogram}` (its name can be a patient's; its counts
still tell the reviewer what kind of content sits under the depth-1 folder). Allowlist entries (step
3) are depth-1 folders only. (2) dispatch trust-architect with the listing path (it Reads the
listing only). **Transcript home (DECIDED HERE):** the dispatching session runs with its cwd equal
to or under the OtherCompany GTM home `H` (so both its transcript and the subagent transcript live under
`R/projects/<project_dir_name(H)>/**` with a first `cwd` under `H`), which puts them inside
`purge-untrusted`'s 30-day hipaa transcript scope for `othercompany` (02_act.md §2.4); when the
OtherCompany home is not yet registered, the procedure waits — it never runs from the runtime or
another company's cwd. The only clear-text names the reviewer sees are depth-1 folder names, which
the 00_global_paths.md §1.2 top-level listing already exposes to review (requests/03_schemas.md R91
→ 00_global_paths.md §1.2 "Listing shapes"). Require a final ```` ```gtm-result ````
block whose
`reviews[]` holds one entry `{action_id: "phi1_listing:<sha256>", after_digest: "sha256:<sha256>",
lane: "hipaa", verdict: "pass", lines: [{check: "folder:<absolute folder>", result:
"pass|fail", note}]}` — one line per **depth-1** folder; folders named like `medical-analytics`,
`insurance`, `credentialing` fail unless the note clears them, and the note never quotes a name
(it cites counts and extensions only); G tests (RED when the clause is removed): a fixture root
holding `Clients/Jane Doe/xray.pdf` yields a listing containing neither `Jane Doe` nor `xray`, with
`Clients` at depth 1 and one `name_sha256` entry under it; the dispatch helper refuses to run when
its cwd is not under the OtherCompany home; (3) `gtm_lists.py phi1-allowlist --listing-sha256 <hex> --review-agent
<agent_id>` verifies the reviewer with `gtm_result.verify_reviewer(agent_id, {"trust-architect"},
"phi1_listing:<sha256>", "sha256:<sha256>")` (02_act.md §2.7: spend row `agent_type == "trust-architect"`, its
own transcript's final block, digest match) and writes the allowlist with the `pass` folders only.
WP-M never opens a OtherCompany file itself. `gtm_lists.py` also exposes the in-process function
`add_phi_path(path: str, *, why: str, source: str) -> bool` (add-only, under `S/lists.lock`;
returns False when already present) that `phi-denylist add --path` and `act.py ingest-findings`
(02_act.md §2.4) both call, and beside it `add_phi_url(url: str, *, why: str, source: str) -> bool`
(same lock and add-only rule; stores the URL normalized to the `url_prefix` form above — host
lowercased, query and fragment dropped, empty path `/`; a non-`https` URL is refused) that `phi-denylist add --url <url>` and `ingest-findings` (a `phi_encountered`
`evidence[]` entry that is an `https://` URL) call. G test: `add_phi_url` of a URL with a query
string stores the prefix without it, and a second call returns False (RED when the normalization is
removed).

### 3.21 Isolation hits (`S/isolation_hits.jsonl`)

`{"ts", "company", "session_id", "agent_id", "agent_type", "tool_use_id": "<the tool call's id>"|null, "source": "gtm_browser_gate|act_record_external|act_complete|secret_sink", "system": null|"<system>", "detail": "…", "matched_company": "<slug>|other_businesses|null", "matched_value": "…"}`
(`tool_use_id` is written by G-A — the payload's `tool_use_id` — and null for act.py and `secret_sink.py` rows; it is the §3.19 `isolation_guard_hits_28d` dedupe key; requests/03_schemas.md R86).
Every writer (G-A via `gtm_hooklib.append_isolation_hit`, act.py via `breakers.append_isolation_hit`,
`secret_sink.py`) appends under `fcntl.flock` on **`S/isolation_hits.lock`**. Triggers: G-A rule 4;
`record-external` confirmed trail conflict or agent-written card (02_act.md §2.11); `act_complete` = a
`complete --from-agent` whose `operations[]` entry reports `acting_as_after` ≠
`dispatch_brief.acting_as_expected` (the operator ended up acting as another entity), or a setup
`ticket --close --from-agent` whose `operations[].acting_as_after` ≠ the setup ticket's
`acting_as_expected`; `secret_sink` = captured value found in a transcript or snapshot file, **or** the
capture's `acting_as_label` ≠ the setup ticket's `acting_as_expected` (exact string equality after
whitespace collapse; `detail: "acting_as_mismatch"`, nothing written to GSM — 06_connectors.md §6.6;
requests/08_seats_wps.md item 23). Outside-actor rows (§3.23) are
never isolation hits.
A1 ingests new lines per company (offset in `ST/.isolation_offset`) → breaker (02_act.md §2.9) + `isolation_hit_ingested` event.

### 3.22 System namespaces (A1 `tools/gtm/system_names.py`; used by A1, A2, B1, F, G, K, L)

One normative table; every consumer resolves through it, never by string surgery of its own.

| Tier-table system (canonical) | Connector (06_connectors.md §6.1) | Runbook file stem | Activity-log candidates, first present wins |
|---|---|---|---|
| `gbp` | `gbp` | `gbp` | `gbp_{brand}`, `gbp` |
| `facebook` | `meta` | `facebook` | `facebook_{brand}`, `facebook` |
| `instagram` | `meta` | `instagram` | `instagram` |
| `meta` (ad account, billing, portfolio) | `meta` | `meta_ads` | `meta_ads` |
| `google_ads` | `google_ads` | `google_ads` | `google_ads` |
| `lsa` | `listings` | `lsa` | `lsa` |
| `ga4` / `search_console` | same name | same name | same name |
| `gtm` | `gtm_api` | `gtm` | `gtm` |
| `website_wordpress` | `wordpress` | `website_wordpress` | `website_wordpress_{brand}`, `website_{brand}`, `website_wordpress`, `website` |
| `website_static` | — (repo commit) | — | `website_static` |
| `yelp angi thumbtack houzz nextdoor bbb` | `listings` | same name | same name |
| `apple` | `listings` | `apple` | `apple_business` |
| `bing` | `listings` | `bing` | `bing_places` |
| `crm` | `lead_sink` | `crm` | `crm_tracker` |
| `call_tracking` | `call_tracking` | `call_tracking` | `call_tracking` |
| `gtm_ai` | — (internal, 04_hooks.md §4.6) | — | none (not activity-logged) |
| `linkedin`, `youtube` | — (browser runbook only until a connector WP adds one; 06_connectors.md §6.1 has none today) | same name | same name (both already in `activity_log._ADDED_SYSTEMS`) |
| any other | same name | same name | same name |

**Candidate order rule (I1; the one definition).** For a tier system `T` and brand `b`, the
candidates are tried in this order and the first one present in `systems` wins: (1) the
brand form `{base}_{b}` (`gbp_{b}`, `facebook_{b}`, `website_wordpress_{b}`);
(2) the legacy brand form (`website_{b}` — OtherCompanyB's historical log, pack `host_systems` and
`channels_in_scope` use it); (3) the generic form (`gbp`, `facebook`, `website_wordpress`,
`website`, or the table's single name). This order matters because `activity_log.resolve_paths()`
**always** includes the generics `website_wordpress`, `gbp`, `facebook`, `meta_ads`
(`_ADDED_SYSTEMS`), so a generic-before-brand order would never pick OtherCompanyB's
`website_remodeling`. The table's last column is already in this order. **"Present" means
membership of `activity_log.resolve_paths(slug).systems`, which is `_ORIGINAL_SYSTEMS ∪
_ADDED_SYSTEMS ∪ scope.channels_in_scope` — never the pack alone (DECIDED HERE).** Because
`_ORIGINAL_SYSTEMS` always carries OtherCompanyB's legacy names (`gbp_remodeling`, `gbp_restoration`,
`facebook_remodeling`, `facebook_restoration`, `website_remodeling`, `website_restoration`), **any**
pack whose brand id is `remodeling` or `restoration` resolves to those names whether or not it
declares them. That is accepted, not a defect: the activity log is per-company (each home has its
own), so the shared name only labels that company's own entries; and every GTM reader compares
systems through `tier_system_of` / `trail_group` (§3.19, 02_act.md §2.11), never by the brand-form
string. A1 test: a non-OtherCompanyB fixture pack (slug `zeta`) with one brand id `remodeling` and no
brand forms in `channels_in_scope` gives `activity_system(pack, "gbp", "remodeling", systems) ==
"gbp_remodeling"` and `tier_system_and_brand("gbp_remodeling", pack) == ("gbp", "remodeling")`
(RED when presence is read from the pack alone).

**`target_ref` grammar (FID-02; the one definition — `target_ids`, check 1(c), 06_connectors.md
§6.2 target resolution and §3.7 `object_ref` all use it).** Each form is a **full match**; `<id>`,
`<cid>`, `<a>`, `<c>`, `<w>`, `<ag>`, `<ad>` are digits only; hosts are compared lowercased. A
string that matches no form of its system yields `{}`.

| Tier system | Forms → `target_ids` keys |
|---|---|
| `google_ads` | `customers/<cid>` → customer_id; `customers/<cid>/campaigns/<id>` → customer_id, campaign_id; `customers/<cid>/adGroups/<id>` → customer_id, ad_group_id; `customers/<cid>/adGroupAds/<ag>~<ad>` → customer_id, ad_group_id, ad_id; `customers/<cid>/campaignBudgets/<id>` → customer_id, campaign_budget_id; `customers/<cid>/conversionActions/<id>` → customer_id, conversion_action_id (bare numeric ids are not accepted) |
| `gbp` | `locations/<id>` → location_id; `accounts/<a>/locations/<id>` → location_id (the `<a>` is matched, never returned: `gbp_account_id` is bound by no pack value, so it must never count as an object-level id; requests/06_connectors.md R21 item 2; A1 test: `target_ids("gbp", "accounts/9/locations/123") == {"location_id": "123"}`) |
| `meta` | `act_<id>` → ad_account_id; `act_<id>/campaigns/<id>`, `/adsets/<id>`, `/ads/<id>` → ad_account_id + campaign_id / adset_id / ad_id |
| `facebook` | `page/<id>` → page_id; `page/<id>/posts/<id>` → page_id, post_id |
| `instagram` | `ig/<id>` → ig_user_id; `ig/<id>/media/<id>` → ig_user_id, media_id |
| `linkedin` | `organization/<id>` → organization_id; `organization/<id>/posts/<id>` → organization_id, post_id (the post `<id>` = the digits of its `urn:li:share:`/`urn:li:ugcPost:` URN; shape **UNVERIFIED** against the current LinkedIn API — WP-A1 checks it before P2, a mis-shape yields `{}` and fails check 1(c), never open) |
| `youtube` | `channel/<ch>` → channel_id; `channel/<ch>/videos/<v>` → channel_id, video_id; `channel/<ch>/comments/<cm>` → channel_id, comment_id — `<ch>` = `UC[A-Za-z0-9_-]{22}`, `<v>` = `[A-Za-z0-9_-]{11}`, `<cm>` = `[A-Za-z0-9_.-]{1,100}` (the one non-digit id grammar; full match) |
| `ga4` | `properties/<id>` → property_id |
| `gtm` | `accounts/<a>/containers/<c>` → gtm_account_id, container_id; `…/workspaces/<w>` → + workspace_id |
| `search_console` | `sc-domain:<domain>` or `https://<host>/` → site_url |
| `website_wordpress` | `https://<host>/<path>` → site_host (= `<host>`), page_ref (= `/<path>`) |
| `L` systems, `lsa` | an `https` URL whose host is in `platform_hosts(system)` → listing_url (the whole URL; check 1(c) then requires it to equal an `identity_allowlist.listing_urls` entry) |
| `website_static` | `repo:<toplevel>` → `{}` (02_act.md §2.8 check 1 applies its own `website_static` rule) |
| `gtm_ai`, `crm`, `email`, `sms`, `call_tracking`, `sms_provider`, `domain_registrar`, `stock_media`, `vendor`, `paid_api` | **`target_ref: null ok`** — null or any string → `{}`; check 1(c)'s no-pattern branch applies to a non-null value |

**Account-level keys** (the ids that name the account itself, 06_connectors.md §6.2 step 2/5):
`customer_id`, `ad_account_id`, `page_id`, `ig_user_id`, `location_id`, `property_id`,
`gtm_account_id`, `container_id`, `site_url`, `site_host`, `listing_url`, `organization_id`,
`channel_id`. Every other key names an
object below the account (the §3.4.1 `object_scope: object` requirement). A form carrying no host
is admitted by check 1(b) through its full grammar match (the host test of 02_act.md §2.8 check 1(b)
applies to URL forms only; requests/03_schemas.md R26). The tier-table validator (A1) refuses a
system that has a write row with a non-null `target_ref` and no grammar row, other than
`website_static`.
**Account ids (06_connectors.md §6.2).** `accounts[].account_id` may be written in any display form
(e.g. `100-200-3000`, `act_123`, `properties/100000004`); every comparison — check 1(a), the
`identity` kinds, `account_keys`, §3.7 `display.account_id` and the stored proposal field — goes
through `normalize_account_id`.

```python
CYCLE_ID_RE: re.Pattern                                     # re.compile(<the 00_global_paths.md §0.3 pattern string>); callers use .fullmatch / .match (anchored)
LEAD_ID_RE: re.Pattern                                      # re.compile(<the §3.14 lead id pattern>), with named groups slug/date/n (§3.2 reads .group("slug"))
    # Every *_RE here is a COMPILED re.Pattern (DECIDED HERE); the source strings stay in 00_global_paths.md §0.3 / §3.14,
    # and the stdlib copies 04_hooks.md keeps are parity-tested on .pattern (and .flags).
def cycle_id_ok(cycle_id: str) -> bool
    # 00_global_paths.md §0.3 "HHMM per kind": CYCLE_ID_RE.fullmatch(cycle_id) is not None AND (hhmm group present
    # iff kind ∈ {"inbox", "interactive"}). False for a non-matching id (callers that need exit 2 for a grammar failure
    # test CYCLE_ID_RE first, §3.12/§3.19). A1 tests: 00's per-kind cases.
GTM_SEATS: tuple[str, ...]                                  # the 9 new GTM seats, values in 04_hooks.md §4 "Seat constants" (local-presence-architect … gtm-credential-setup)
DEPARTMENT_SEATS: tuple[str, ...]                           # the 9 existing /gtm department seats (marketing-director … market-analyst), 04_hooks.md §4
BROWSER_SEATS: tuple[str, ...]                              # gtm-analyst, gtm-operator, gtm-credential-setup (04_hooks.md §4)
def seat_sets(*, log: Callable[[str, dict], None] | None = None) -> tuple[set[str], set[str], set[str]]
    # (gtm, department, browser) — each the UNION of its constant and model_policy.json's gtm_seats /
    # gtm_department_seats / gtm_browser_seats list (a policy edit adds, never removes); the missing-file and drift
    # log calls exactly as 04_hooks.md §4 "Seat constants" defines them (that text is the one contract for this function).
OPERATOR_OK_DIRNAME, OPERATOR_OK_LOCK, OPERATOR_OK_COMMANDS, OPERATOR_OK_EVENT_VALUE, RULE_K_LITERALS  # values: 00_global_paths.md §1.4 "Shared literals" (the one table)
HOLDS_RUNNER_RELPATH: str                                   # "schedules/run_gtm_job.sh" (00_global_paths.md §1.4 "Holds-job proof"; 07_notices_schedules.md §7.3 renders real_root()/HOLDS_RUNNER_RELPATH)
ACCOUNT_LEVEL_KEYS: frozenset[str]                          # the "Account-level keys" list above
IDENTITY_KEYS: frozenset[str]                               # ACCOUNT_LEVEL_KEYS ∪ {"gbp_account_id"} (kept so a G-A key seen outside target_ids still classes as identity; the grammar no longer returns it) — the keys naming an identity object
    # (business page, location, property, container, site); every other grammar key (campaign_id, ad_group_id, ad_id,
    # campaign_budget_id, conversion_action_id, adset_id, post_id, media_id, video_id, comment_id, workspace_id, page_ref) is in-account
    # (04_hooks.md §4.1 "Rule 7b key classes"; requests/04_hooks.md R20). A1 test: every key of the grammar table is in
    # exactly one of IDENTITY_KEYS or the in-account set.
CSA_SLUG: str                                               # the CSA company slug; "" until the coordinator sets it (06_connectors.md §6.3: while "", every company naming CSA_GSM_PROJECT is refused)
CSA_GSM_PROJECT: str                                        # "example-org" (plan §17 d; 06_connectors.md §6.3 gsm_project_cross_company)
PUBLIC_MAIL_DOMAINS: frozenset[str]                         # the §3.4.1 `email`-kind list
INBOX_CLASS_RE: re.Pattern                                  # r"^(reviews?|messages?|dms?|inbox|q_?and_?a|qa|questions?|comments?|forms?|form_submissions?|leads?|conversations?)(_|$)", re.I — the 06_connectors.md §6.3 inbox_class_ops test (02_act.md §2.4 snapshot)
NON_INBOX_SNAPSHOTS: dict[str, frozenset[str]]              # hipaa packs: the ONLY (tier system → snapshot names) that may go to paths.snapshots_dir (02_act.md §2.4 snapshot):
    # gbp: hours, categories, services, attributes, committed_ceiling; google_ads / meta: metrics, campaigns, committed_ceiling, ad_content (§3.4.4 "Enabling ads");
    # lsa and every L system: committed_ceiling, profile_content; facebook / instagram: post_content (the three content reads of
    # §3.4.4 "Enabling ads" — profile/post content keys only, never reviews, ratings, comments or messages);
    # gtm: workspace_content (§3.4.4 "gtm.version_publish"); ga4: metrics; search_console: metrics, sitemaps. Never crm or call_tracking. A1 validator test: no entry matches INBOX_CLASS_RE.
TAG_RE: re.Pattern                                          # 04_hooks.md §4.6 dispatch tag (defined here so agent_budget, ai_budget and gate-gtm share it)
CANONICAL_SYSTEMS: frozenset[str]                           # every tier-table system name (§3.4.4) + "gtm_ai"
ALIASES: dict[str, str]                                     # apple_business→apple, bing_places→bing, crm_tracker→crm, meta_ads→meta, website→website_wordpress (gtm_browser has no tier system: it falls to step 5 unchanged)
    # `website` is the table's last activity-log candidate for website_wordpress, so a log entry, trail system or PAUSE.website
    # written under it groups with and blocks website_wordpress (DECIDED HERE). A1 test: tier_system_of("website") ==
    # "website_wordpress" and PAUSE.website blocks a website_wordpress.page_edit (RED when the alias is removed).
def tier_system_and_brand(name: str, pack: dict | None = None) -> tuple[str, str | None]:
    # I13: (1) name ∈ CANONICAL_SYSTEMS → (name, None) at once; (2) name ∈ ALIASES → (ALIASES[name], None);
    # (3) name == "<base>@<brand>" (pause-file form) → (base, brand) after normalizing base by (1)-(2);
    # (4) only then, for a pack brand id b: name == f"{base}_{b}" with base ∈ CANONICAL_SYSTEMS → (base, b),
    #     and name == f"website_{b}" → ("website_wordpress", b);
    # (5) else (name, None). A brand id equal to a canonical suffix ("ads", "ai", "console", "static",
    #     "places", "tracker") can therefore never corrupt "google_ads", "gtm_ai", "search_console",
    #     "website_static", "bing_places" or "crm_tracker".
def tier_system_of(name: str, pack: dict | None = None) -> str   # = tier_system_and_brand(name, pack)[0]
def trail_group(tier_system: str) -> str                        # "meta" for {facebook, instagram, meta}; else tier_system (02_act.md §2.11)
def connector_system(tier_system: str) -> str | None
def runbook_stem(tier_system: str) -> str | None
def platform_hosts(tier_system: str) -> frozenset[str]
    # FID-02: the platform's own console/API hosts (e.g. gbp → business.google.com; google_ads → ads.google.com,
    # googleads.googleapis.com; linkedin → www.linkedin.com, api.linkedin.com; youtube → studio.youtube.com, www.youtube.com,
    # youtube.googleapis.com), a static table in system_names; 02_act.md §2.8 check 1(b). P2 test (A1 + L): every
    # runbook's read_hosts/login_hosts/writes[].allowed_hosts ⊆ platform_hosts(system) ∪ that pack's brands[].domains.
def target_ids(tier_system: str, target_ref: str | None) -> dict[str, str]
    # FID-02: the ids of the `target_ref` grammar above (e.g. {"customer_id": "1002003000", "campaign_id": "…"});
    # {} when no form matches (or target_ref is None). Ids and pack values are compared after normalize_account_id.
    # Check 1(c) (02_act.md §2.8; requests/06_connectors.md R14) requires ≥ 1 id for a system with grammar rows,
    # requires every ACCOUNT_LEVEL_KEYS value to equal the matched account's account_keys value (both normalized),
    # and judges every other (object-level) value as kind in_account (§3.4.1) — never "in OWN", which no pack can list.
    # The connector addresses exactly these (06_connectors.md §6.2; `checks.target_ids` is this function, re-exported,
    # never a second parser). A1 test: google_ads.campaign_budget_edit on customers/<own cid>/campaigns/123 passes
    # check 1; customers/<other cid>/campaigns/123 fails it.
def most_specific_key(tier_system: str, target_ref: str | None) -> str | None
    # §3.2 "Most specific key": the LAST key of the grammar form target_ref matched, in the order the grammar table lists
    # that form's keys (customers/<cid>/adGroupAds/<ag>~<ad> → "ad_id"; act_<id>/adsets/<id> → "adset_id";
    # customers/<cid> → "customer_id"); None when no form matches. Used by tiers.is_enable_action and the §3.2 budget-object
    # and enable_no_budget_object tests. A1 test: those three examples, and None for a bare numeric id.
def normalize_account_id(tier_system: str, value: str) -> str
    # google_ads strips "-" (and spaces); meta strips a leading "act_"; gbp strips "locations/" and "accounts/<a>/";
    # ga4 strips "properties/"; search_console lowercases; linkedin strips a leading "urn:li:organization:";
    # every other system (youtube included) returns value unchanged.
def identity_bucket(tier_system: str) -> str | None
    # the identity_allowlist key holding that system's ids: google_ads→ads_customer_ids, meta→meta_ad_account_ids,
    # facebook→facebook_page_ids, instagram→instagram_ids, gbp→gbp_location_ids, ga4→ga4_property_ids,
    # gtm→gtm_container_ids, linkedin→linkedin_page_ids, youtube→youtube_channel_ids, search_console / website_wordpress→domains;
    # else None (the identity_for kind, §3.4.1). The two new buckets are optional pack lists (requests/03_schemas.md R69).
ALLOWLIST_KEY_SYSTEM: dict[str, str]                        # each company._ACCOUNT_ID_ALLOWLIST_KEYS key → its tier system, so
    # checks.sibling_values can call normalize_account_id (requests/02_act.md item 90): ads_customer_ids→google_ads,
    # meta_ad_account_ids→meta, gbp_location_ids→gbp, facebook_page_ids→facebook, instagram_ids→instagram,
    # ga4_property_ids→ga4, gtm_container_ids→gtm, linkedin_page_ids→linkedin, youtube_channel_ids→youtube. A1 test: it is
    # identity_bucket's inverse on those nine keys, and every _ACCOUNT_ID_ALLOWLIST_KEYS key is mapped (R69 adds the two).
def account_keys(tier_system: str, account: dict) -> dict[str, str]
    # the platform-native account-level keys of one accounts[] entry (06_connectors.md §6.2 step 2), never account_id
    # blindly: google_ads customer_id; meta ad_account_id; facebook page_id; instagram ig_user_id; gbp location_id —
    # each = normalize_account_id(account_id); ga4 property_id = account["ga4_property_id"]; gtm gtm_account_id /
    # container_id = account["gtm_account_id"] / account["gtm_container_id"]; search_console site_url =
    # normalize_account_id("search_console", account["account_id"]) — the account_id holds the property in one of the two
    # accepted forms `sc-domain:<host>` or `https://<host>/` (any other form → the key is absent, account_key_missing),
    # and the target_ref form must equal it after the same normalization;
    # website_wordpress site_host = account["site_host"]; L systems and lsa listing_url = account["listing_url"];
    # linkedin organization_id and youtube channel_id = normalize_account_id(account_id).
    # A field the account lacks is absent from the dict (the connector then refuses account_key_missing).
def normalize_interface(tier_system: str, raw: str | None) -> str
    # §3.23 (DECIDED HERE): the one vocabulary for change-history `interface` values, applied to BOTH the input row's
    # interface and the pack co_managing_systems[].interface (and to the GTM credential's interface in §3.23 step 1).
    # Closed per-system table: google_ads GOOGLE_ADS_API → "api", GOOGLE_ADS_WEB_CLIENT → "web_ui",
    # GOOGLE_ADS_EDITOR → "editor", GOOGLE_ADS_SCRIPTS → "scripts", GOOGLE_ADS_AUTOMATED_RULE → "automated_rule",
    # GOOGLE_ADS_RECOMMENDATIONS → "recommendations"; every system: the pack vocabulary values "api", "web_ui",
    # "editor", "scripts", "automated_rule", "recommendations" map to themselves (compared casefolded). Anything else —
    # an unlisted platform label, null, or a system with no table entry — → "unknown", and "unknown" never equals
    # anything (a row with it can match no co-managing entry and no GTM credential). Other systems' labels are added by a
    # reviewed change (their change-history interface fields are UNVERIFIED). A1 tests: ("google_ads", "GOOGLE_ADS_API")
    # → "api"; ("google_ads", "web_ui") → "web_ui"; ("meta", "GRAPH_API") → "unknown".
def activity_system(pack: dict, tier_system: str, brand: str | None, systems: tuple[str, ...]) -> str | None
    # the ONE signature (4 args) — every caller passes systems = activity_log.resolve_paths(slug).systems.
    # Callers are A2 (02_act.md §2.10) and WP-G outside_actor (§3.23), which import activity_log. Hooks never call it
    # (they cannot import activity_log), so no "pack-derived set" exists anywhere.
```
A1 tests: built on the real `activity_log.resolve_paths(slug).systems` of a OtherCompanyB-shaped
fixture pack — `activity_system(pack, "website_wordpress", "remodeling", systems) ==
"website_remodeling"`, `("gbp", "restoration") → "gbp_restoration"`, `("meta", None) → "meta_ads"`,
`("crm", None) → "crm_tracker"`, and with an 08_seats_wps.md Appendix A pack (no brand forms) `("website_wordpress",
"main") → "website_wordpress"`; `tier_system_of("google_ads", pack_with_brand_id_"ads") ==
"google_ads"`; `tier_system_and_brand("website_remodeling", ts_pack) == ("website_wordpress",
"remodeling")`; `tier_system_and_brand("gbp@restoration", ts_pack) == ("gbp", "restoration")`;
`target_ids("google_ads", "customers/1002003000/campaigns/20000000001") == {"customer_id":
"1002003000", "campaign_id": "20000000001"}` and `target_ids("google_ads", "20000000001") == {}`;
`normalize_account_id("google_ads", "100-200-3000") == "1002003000"`; on the committed OtherCompanyB
pack fixture `account_keys("ga4", <ga4 account>) == {"property_id": "100000004"}` (never its
`G-…` measurement `account_id`); `identity_bucket("ga4") == "ga4_property_ids"`.
`scope.channels_in_scope`, `accounts[].system` and `PAUSE.<system>` names may be written in either
namespace (OtherCompanyB's committed pack uses `gbp_remodeling`, `facebook_remodeling`,
`website_remodeling`); every reader normalizes with `tier_system_of` / `tier_system_and_brand`
(pauses keep the brand, §3.10) — e.g. G-A's read hosts are
`runbook_hosts({tier_system_of(c, pack) for c in scope.channels_in_scope})`. **DECIDED HERE:**
normalize in code rather than migrate the OtherCompanyB pack.

### 3.23 Outside-actor reconciliation (WP-G `outside_actor.py`; plan §20.9, §20.13)

Weekly (and on demand), after the analyst's change-history reads:
`python3 <R>/tools/gtm/outside_actor.py reconcile --company X --run <run_id> (--from-agent <analyst agent_id> | --from-collector <collector json path>)`.
Input rows: the analyst's `gtm-result.change_history[]` (08_seats_wps.md §8.1) or a collector's `data.changes[]`,
each `{system, object, change, at, identity, interface, source, exactness}`. **`<co_system>`
(F-cosys; the one definition)** = `co_managing_systems[i].system` of the matched pack entry — the
**co-actor's own name** (e.g. `agency_saas`), never the tier system it co-manages; it appears only
in the actor label `outside:<co_system>` and in `classify --as co:<co_system>` (which must name an
existing entry, else exit 3). The platform system an outside change touched is the input row's
`system` (normalized with `tier_system_and_brand`), which is what `--system`, the §3.19
`co_actor_writes_7d` key and every per-system count use. The context is built with
`gtmlib.make_ctx`. For each row:
(1) rows matching a GTM `completed` action are skipped (already logged). **Match (DECIDED HERE;
plan §20.13 keys outside-actor detection on identity + interface):** same tier system and
`target_ref`/object, `at` within ±2 h of its `execution.finished_at`, **and — wherever the row's
`exactness` is `exact` — `identity` and `interface` equal the GTM credential that executed the
action**: for an API-executed action the connector's service-account email or OAuth client
(`identity`) and the API client type (`interface`, e.g. Google Ads `change_event.client_type`
`GOOGLE_ADS_API`); for a browser-executed action the company profile's signed-in identity (the pack
account's `login_identity` — the address the company's browser profile is signed in as;
requests/03_schemas.md R35 adds this optional field, and while it is absent a browser-executed
action matches on object + time and its row counts as `best_effort`) and the UI interface
(`GOOGLE_ADS_WEB_CLIENT` or the platform's UI label). **Every `interface` comparison in steps (1)
and (2) compares `system_names.normalize_interface(<tier system>, value)` of both sides** (§3.22;
DECIDED HERE — the pack's `co_managing_systems[].interface` keeps its documented `'api' |
'web_ui'` vocabulary, and a platform label such as `GOOGLE_ADS_API` is normalized to it; an
`"unknown"` result never matches), while `identity` is compared casefolded. Only `best_effort` rows (snapshot diff, no identity exposed) fall back to object + time.
A row with the object and time of a GTM action but another identity or interface is **not**
skipped: it continues to (2)/(3); (2) rows whose `identity` **and**
`interface` both equal a pack `co_managing_systems[]` entry (interface normalized as above) → `activity_log add` with `--actor
outside:<co_system>` (e.g. `outside:agency_saas`); (3) every other row → `--actor outside:unknown`
(operator web-UI edits, unknown actors, off-server agent writes and cross-connections all land here,
§20.13). **Exact `activity_log add` argv (I10; in-process `activity_log.main`, same stdout/exception
hygiene as 02_act.md §2.10):** `--company <slug> --system <activity_system(pack, *tier_system_and_brand(row.system,
pack), activity_log.resolve_paths(slug).systems)>` (unmapped → the row gets `resolution:
"unmapped"`, is counted under `unmapped` in this output and never also under `unknown`, is not
logged, **and counts toward `platform_changes_unlogged_7d`** — it is unexplained by definition —
and is listed in the weekly report's `outside_unknown` list with `resolution: "unmapped"`; the
same rule, stated identically in §3.19) `--action <the 02_act.md §2.10 verb table applied to the first verb word of
row.change, default update>` `--object <row.object, or — when that is null, empty or whitespace
only — "<tier system>:<the row's target id when the collector reports one>", else "(unknown
object)"; DECIDED HERE, since `activity_log` refuses an empty object with exit 2 and one bad row
must never abort the run or be dropped>` `--why "outside actor change observed via
<row.source> (<row.exactness>)"` `--actor outside:<co_system>|outside:unknown` `--undo "n/a:
outside actor change — revert only via a new GTM proposal"` `--approval "outside actor §20.9"`
`--status done` `--ts <row.at>` `--after <json({"change": row.change, "identity": row.identity,
"interface": row.interface})>` `--notes outside_actor:<run_id>` `[--evidence <collector or snapshot
home-relative path>]`. **Entry id (DECIDED HERE):** reconcile runs `activity_log.main` with
stdout captured (the 02_act.md §2.10 hygiene) and takes the id from the captured line matching
`^logged (?P<id>A\d{4,}): ` (`cmd_add`'s own print); exit 0 with no such line → reconcile exit 1
(internal), the row written with `activity_log_id: null` and counted unexplained. Each output row
carries **`activity_log_id`** (the id; null for `gtm_action` skipped rows and `unmapped` rows). G
test: runs the real `activity_log.main` with these args for a Google Ads `change_event` row, a
snapshot-diff row and a row whose `object` is empty; all three log (the last as `google_ads:<id>` or
`(unknown object)`), each output row's `activity_log_id` equals the id the log holds, and `check`
stays OK (RED when the object fallback is removed — the run aborts). An Agency `change_event` whose
`client_type` is `GOOGLE_ADS_API` matches a pack entry declared `interface: "api"` and logs
`outside:agency_saas` (RED when the raw strings are compared).
These entries **never** feed `isolation_hits.jsonl` and never count as agent actors
(`activity_log.is_agent_actor` returns false for `outside:*`). **Accounting (F7):** declared
co-system rows count as `co_actor_writes_7d`; every `outside:unknown` row **and every
`unmapped` row** counts toward `platform_changes_unlogged_7d` (§3.19) and is listed in the weekly report for classification until
`outside_actor.py classify --company X --entry <activity-log id> --as owner|co:<co_system> --card
<card_id>` records the owner's answer (`cards.require_approved(ctx, card_id, "classify <entry id>
<as>")`, `<as>` = `owner` or `co:<co_system>`, 02_act.md §2.2b/§2.6 — an `approve` answer on a card
posted with `card-post --subject "classify <entry id> <as>"`, authorship-checked per 02_act.md §2.11; a "No" never classifies, FID-01) as an
activity-log `decision` entry — only then is it explained. **Explained (the one join, DECIDED
HERE):** a reconcile output row is explained when its `resolution` is `gtm_action` or `co:<name>`,
or when the activity log holds a `decision` entry whose `notes` equals `"classify:" +
row.activity_log_id`; `platform_changes_unlogged_7d` (§3.19) counts every other row of the window
(`unknown` rows until so classified, `unmapped` rows always, rows with a null `activity_log_id`). **Exact `classify` argv (in-process
`activity_log.main`, same hygiene as reconcile):** `--company <slug> --system <the classified
entry's own system> --action decision --object <the entry's object> --why "owner classified <entry
id> as <as> (card <card_id>)" --actor main-session --approval "card <card_id>" --status done
--notes classify:<entry id>`; `--undo` is omitted (optional for `decision`). `--actor main-session`
satisfies `activity_log.is_valid_new_actor_shape`. G tests: an Agency (`co_managing_systems`)
`change_event` on the same campaign 30 min after a GTM action's `finished_at`, with the Agency
identity and interface, is logged `outside:agency_saas` and not skipped (RED when step (1) matches
on object + time alone); the real `activity_log.main` accepts the `classify` argv above. Each
reconcile writes `ST/outside_actor/<run_id>.json` `{"rows": [...each input row plus "resolution": "gtm_action|co:<name>|unknown|unmapped" and "activity_log_id": "<id>"|null]}`
for `perf_report`. Output `{"ok", "logged": N, "skipped": N, "unknown": N, "unmapped": N}`; exit 0,
1 internal, 2 usage, 3 unreadable input, a card that is unanswered, not `approve`, or of another
subject, or `test_mode_real_state` (§3 intro), 13 company (IMP-17).
