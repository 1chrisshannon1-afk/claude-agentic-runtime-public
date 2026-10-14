# Requests from `03_schemas.md` (§3 owner) to other section files

Each request names the target file, section and exact change needed for the §3 fixes to hold end to
end. §3 now uses the names given here. Items marked **CONFLICT** are cases where two other section
owners already chose different names for the same thing; the coordinator picks one and §3 follows.

Requests from other owners that targeted `03_schemas.md` were applied in §3 in round 1:
`requests/02_act.md` items 4–15, `requests/04_hooks.md` R11 and R13, `requests/05_approver.md` R1, R2 and R5,
`requests/06_connectors.md` R1 and R4, `requests/07_notices_schedules.md` R8,
`requests/08_seats_wps.md` §3, and `requests/00_global_paths.md` R4 (by section reference; see C1).

**Round 2 (this round) applied in §3:** `requests/02_act.md` items 36–41 (43 needs no text: §3
names no marker path); `requests/05_approver.md` R9, R10 (a)–(e) (`display_sha256` stays plain hex,
as 05 §5.5 3b now compares it), R18 and R21; `requests/06_connectors.md` R1 items 1–3 and 5–7 (plus
the `account_keys`, `CSA_SLUG`/`CSA_GSM_PROJECT`, `site_host` and `listing_url` names 06 §6.2/§6.3
cite as R1 items 8–9), R3 (codes and snapshot rule; **not** the `ceiling_enable` rename — 06 itself
now uses `commits_on_enable`) and R5; `requests/07_notices_schedules.md` R12 and R14;
`requests/00_global_paths.md` R11 and R17; `requests/08_seats_wps.md` §16. `fallback_reason:
"sink"` (06 §6.2 "Lead sink") is added to §3.14's enum. §3.2 no longer refreshes the current value
of non-enable money actions at `authorize` (it is bound at execution instead; plan §20.13 signs the
absolute value), so the R24 that round 1 cited is **withdrawn**.

**Landed — other owners may drop their "requested"/"pending" markers:** 03_schemas.md §3.16
`files_modified_between` (02 §2.11); §3.22 `NON_INBOX_SNAPSHOTS`, `INBOX_CLASS_RE` (02 §2.4
`snapshot`); §3.22 `target_ref` grammar, `target_ids` (dict), `normalize_account_id`,
`identity_bucket`, `account_keys`, `CSA_SLUG`, `CSA_GSM_PROJECT`; §3.4.1 `object_scope` and the
`identity_for:<key>` kind (06 §6.2 "Status" paragraph); §3.20 `agency_app`/`agency_gsm_projects`
(06 §6.3/§6.5b).

**Round-1 requests still not landed (verified this round):** R14 (00 §1.2 `untrusted/<unt_id>.lead.json`),
R17, R19 and R21 (08). Every other R1–R21 item appears in its target file (R2 is superseded by
R26).

## Conflicts for the coordinator

- **C1 · IMP-03 · operator marker path (narrowed).** All files now use the `operator_ok` name, but
  `00_global_paths.md` §1.2/§1.4 still spell the file `S/operator_ok/<command>.<slug>.json`, while
  `02_act.md` §2.3/§2.4 use `S/operator_ok/<command>.<slug>.<target>.json` (keyed by target, so
  several lifts can be pending; requests/02_act.md item 34). §3 names no path — it refers to "the
  operator's single-use marker (02_act.md §2.3 exception 2 / 00_global_paths.md §1.4)" and records
  `decided_by: "operator_ok"` (§3.17) — so it follows whichever form the coordinator picks.
- **C2 · FID-03 — resolved.** 02, 05 and 06 all use `commits_on_enable`, `enable_value_mismatch`
  and `ceiling_unreadable`; §3.2 now uses the same codes. Only the scope wording of 02 §2.6 rule 5a
  is still wider (R23).
- **C3 · FID-02 — superseded by R26.** 02 §2.8 check 1(d) now judges `id_fields` by kind, but knows
  four kinds; §3.4.1 defines seven.

## To `02_act.md`

- **R1 · FID-03 · §2.6 `authorize` (and §2.4 exit-code list).** For a row with
  `commits_on_enable: true` (03_schemas.md §3.4.1), `authorize` fills
  `before.value.current_absolute_value` from a fresh read, overwriting any value the proposer
  supplied. API accounts use connector read op `committed_ceiling` (06_connectors.md §6.2). Browser
  accounts use the proposal's `before.evidence_ref` snapshot. `authorize` refuses exit 3
  `enable_value_mismatch`, with no approval request, when the value or unit differs from
  `after.new_absolute_value`/`after.unit`. A2 copies the row flag into the request's
  `display.commits_on_enable` (03_schemas.md §3.7).
- **R2 · FID-02 · §2.8 check 1(d)/(e).** Apply (d) per `id_fields` kind (03_schemas.md §3.4.1):
  - `identity`: the value must be in `OWN`.
  - `email`: the whole address is in `OWN`, or its domain is in `identity_allowlist.domains` ∪
    `brands[].domains`. This replaces (e).
  - `listing`: the value exactly equals an `identity_allowlist.listing_urls` entry.
  - `in_account`: the value must carry no host or URL and must equal no sibling-pack or
    `other_businesses` value. It is **not** tested for membership of `OWN`. It is bound by
    06_connectors.md §6.2's `not_owned` resolution.

  A `shared_identifiers` value still gives class `shared`. For `target_ids`, use
  `system_names.target_ids(system, target_ref) -> dict[str, str]` (03_schemas.md §3.22, now
  specified) and test its values. `checks.target_ids`, as 06_connectors.md §6.2 names it, is that
  function re-exported. Values are compared after the per-system normalization stated in §3.22.
  `platform_hosts` is in §3.22 too.
- **R3 · IMP-02 · §2.2b `tiers.py` API.** Add
  `def row_triple(row_id: str) -> tuple[str, str, str]` and
  `def row_id(system: str, object_class: str, action: str, when_suffix: str | None = None) -> str`.
  They implement 03_schemas.md §3.4.1's split rule and its two exceptions (`any.object_read`,
  `website_wordpress.page_unpublish_with_301`). §2.10's verb map derives the action with
  `row_triple`.
- **R4 · FID-05 · §2.7 first bullet and the §2.6 runaway-spend paragraph.**
  - `_nomatch` resolves `row_lanes.nomatch` (`brand`, `claims_voice`), and gets `cta_link` on a
    link. Delete "the row is not `_nomatch` (whose gate is the signature, 03_schemas.md §3.4.2),".
  - Add: "a `class: money` row whose proposal has a non-empty `assets[]` also gets the `nomatch`
    lanes."
  - In "exactly as for `_nomatch` — a claims review of a number checks nothing", drop "exactly as
    for `_nomatch`" (`_nomatch` now has lanes).
- **R5 · FID-01 · §2.6 card rule `CARD_SUBJECT_RE`.** It must admit the subjects §3 uses:
  - `resume <exact pause file name>` (§3.10)
  - `autonomy <slug> autonomous` (§3.17)
  - `classify <activity-log entry id> owner|co:<co_system>` (§3.23)
- **R6 · FID-24 + FID-13 · §2.4 `ticket` and `execute` rows (and the exit-3 code list).**
  - For every row with `recipient_required` or `list_send: true`, `ticket --write`/`--write-batch`
    mint and `execute` re-run the quiet-hours and SMS send-window checks (03_schemas.md §3.11
    "Send-time re-check"). If they fail: exit 3 `quiet_hours` / `sms_window_closed`, no ticket, and
    the action stays `authorized`.
  - For `sms.list_send`, the executor sends only to members whose lead-sink `sms_consent` is
    complete. The result is `{"members", "sent", "excluded_no_consent"}`, and an unresolvable list
    gives `failed` / `list_unresolvable` (03_schemas.md §3.11 "List sends").
- **R7 · IMP-13 · §2.4 `ticket` row, `--close` clause.** `--close` on a `closed`, `consumed`,
  `abandoned` or `expired` ticket is an idempotent success: exit 0, `result.already: "<status>"`,
  nothing written. `stopped` is not terminal (03_schemas.md §3.6).
- **R8 · IMP-24 · §2.4 `propose` row.** Refuse the matched row `crm.lead_append` with exit 3
  `use_lead_append`, next to `read_action_not_proposable`, and add the code to the exit-3 list.
- **R9 · FID-19 · §2.4 `lead-append` row and §2.8 check 5.**
  - Name the held row `ST/untrusted/<unt_id>.lead.json`, not `<unt_id>.json`. The `.json` name is
    already the inbox-snapshot form (03_schemas.md §3.15).
  - The first `lead-append` after `lead_sink.baa_ref` appears forwards every held `.lead.json` row
    still present, then deletes it.
  - Check 5 (hipaa packs) refuses `baa_missing` for every `call_tracking.*` action unless the pack's
    `accounts[]` entry for `call_tracking` has a non-empty `baa_ref`.
- **R10 · FID-10 · §2.4 `ingest-findings`.** A `findings[]` entry of kind `signin_missing` with a
  `system` writes a `signin_missing` notice (push; `system` set, per 07_notices_schedules.md §7.1).
  This is the producer that 03_schemas.md §3.19 `expired_signins` now names. Skip this if §2.4
  already says it.

## To `06_connectors.md`

- **R11 · FID-03 (C2) · §6.2 "Enable binds the signed amount" and §6.4 "Enable rows".** Key on the
  row flag `commits_on_enable: true` (03_schemas.md §3.4.1), not on `action == "enable"`. Today the
  flag is set on `google_ads.campaign_enable`, `lsa.account_enable` and the eight `L.paid_enable`
  rows. `google_ads.auto_apply_enable` and `paid_api.usage_enable` also split to action `enable`
  (IMP-02 rule) but carry no pre-configured ceiling. The runbook validator's
  `ceiling_check_missing` applies to flagged rows only.
- **R12 · FID-13 · `lead_sink` connector (§6.1/§6.2 read ops).** Add read op `list_members`
  (`params` = `{"list_id"}`, `data` = the member lead rows, or `not_found` when the list does not
  resolve to lead-sink rows). `sms.list_send` execution uses it (03_schemas.md §3.11).

## To `04_hooks.md`

- **R13 · IMP-05 · §4.6 (`ai_budget.week_to_date_usd` and gate-gtm).** When
  `gtm_pricing.pricing_status()["ccdash"] != "pinned"` (03_schemas.md §3.19), label the bucket
  `exactness: "best_effort"` and record the note `ccdash_unpinned`: a `notes` list in the
  `week_to_date_usd` result, or one enforcement-log row per process.

## To `00_global_paths.md`

- **R14 · FID-19 · §1.2 `ST` layout, `untrusted/` entry.** Add
  `untrusted/<unt_id>.lead.json`: a hipaa pack's lead row held while `lead_sink.baa_ref` is empty
  (03_schemas.md §3.14/§3.15).
- **R15 · IMP-09 · §1.2 `S` layout.** Add `transcript_index_oi.jsonl`, the operator-input side
  index (03_schemas.md §3.16; it shares `S/transcript_index.lock`).

## To `07_notices_schedules.md`

- **R16 · FID-19 · §7.1 notice kinds / dedupe keys.** List the `task` notice `baa:<slug>:lead_sink`
  ("lead sink has no BAA on record", `created_by: act`) among the act-written notices.

## To `08_seats_wps.md`

- **R17 · FID-09 · Appendix B #96.** Replace "`listing_cta` and `ads_internal_cta` lane keys added"
  with "`listing_cta` lane key added; the `google_ads.*@paused` ad/asset rows are `public: true` with
  `lanes_key: public_post` (FID-09), so `ads_internal_cta` is removed".
- **R18 · FID-19 · Appendix C (pack-schema follow-up) and Appendix A.** In `company_schema.json`,
  add `lead_sink.baa_ref` (string; required non-empty for `regulated ∋ hipaa` before any sink
  write) and optional `accounts[].baa_ref` (string; required for `call_tracking` on hipaa packs).
  `company.py validate` checks both.
- **R19 · IMP-02 · §9 H2/L rows and §8 drafter primer requirements.** Drafter `proposals[]` and L
  runbook `writes[...]` keys use `(system, object_class, action)` as `tiers.row_triple` returns it
  (03_schemas.md §3.4.1). L tests assert that every `writes` key is a tier-table row id.
- **R20 · FID-01 / IMP-03 · Appendix B #92.** Replace "an operator terminal, or an answered card"
  with "the single-use operator marker (02_act.md §2.3), or a card passing
  `cards.require_approved(…, "autonomy <slug> autonomous")`".
- **R21 · FID-13 · KB WP (compliance).** The CAN-SPAM file under
  `knowledge/marketing_kb/compliance/` carries cited claims for the unsubscribe mechanism and the
  physical postal address. The `compliance` lane checklist for `email.list_send` cites them
  (03_schemas.md §3.11).

## Round 2 — requests cited by 03_schemas.md §3 (R22–R32)

§3 already names each of these by number; until one lands, the §3 rule it supports is the one the
WP builds and the named test stays RED against the other file's current text.

### To `02_act.md`

- **R22 · F-PHI (§3.1) · §2.2b "HIPAA side-store form".** In the "It applies to:" list, after
  `proposed.rationale` and `proposed.undo`, add: "every string value of `proposed.money_brief`
  (each of its seven keys), and `why.plan_ref`/`why.metric_id` are refused `hipaa_free_text` (exit 3)
  unless they match `^[A-Za-z0-9_.:§#/ -]{1,120}$` (03_schemas.md §3.1)". Add `hipaa_free_text` to
  §2.4's exit-3 list. Test: 03_schemas.md §3.1's P2 test (goes RED when `money_brief` routing is
  reverted).
- **R23 · FID-03 · §2.6 rule 5a (scope).** Replace "**or** whose `action` is `enable`, `resume` or
  `unpause` (`_nomatch` included, 05 R9)" with "**or** that matched **no** row (`_nomatch`) and whose
  `action` is `enable`, `resume` or `unpause`". A table row whose verb is `enable` but carries no
  `commits_on_enable` flag (`google_ads.auto_apply_enable`, `paid_api.usage_enable`) is not
  enable-bound; this is the scope 03_schemas.md §3.2 "Enable actions", 05_approver.md §5.5 3b and
  06_connectors.md §6.2 use. A1 test: `google_ads.auto_apply_enable` and `paid_api.usage_enable`
  authorize with no ceiling read and no `ceiling_unreadable`.
- **R25 · §3.4.1 effective `data_flow` · §2.2b and §2.7 rules 4/"Allowed reviewer seats".**
  (a) §2.2b `checks.py`: add `def content_data_flow(action: dict) -> bool` and the constant
  `TRACKER_HOSTS: frozenset[str]`, both exactly as 03_schemas.md §3.4.1 defines them (for
  `website_static`, the stored patch's added lines count as `after`, its removed lines as
  `before`). (b) §2.7: wherever `row.data_flow` is read — rule 4 (`hipaa`) and the `hipaa`
  reviewer line ("`trust-architect` when `row.data_flow`") — read **effective** `data_flow` =
  `row.data_flow or checks.content_data_flow(action)`, and add rule 6: "`measurement` when
  effective `data_flow` is true and the lane set lacks it". Test: 03_schemas.md §3.4.1's P2 test (a
  OtherCompany pixel `<script>` patch and a booking `<iframe>` page edit each need `measurement` and a
  trust-architect `hipaa` review; RED when reverted to the row flag).
- **R26 · FID-02 · §2.8 check 1 (supersedes R2).**
  (b) Append: "A `target_ref` in a host-less form of the 03_schemas.md §3.22 grammar (e.g.
  `customers/<cid>/campaigns/<id>`, `locations/<id>`, `act_<id>`) satisfies (b) by its full grammar
  match; the host test applies to URL forms only."
  (c) Replace the parenthetical "(e.g. the browser-only listing platforms `yelp`, `angi`, …)" with
  "(the `target_ref: null ok` systems, 03_schemas.md §3.22)", and add: "Listing systems and `lsa`
  have a grammar row: `target_ids` yields `listing_url`, which must equal an
  `identity_allowlist.listing_urls` entry."
  (d) Replace the kind list and "a kind outside these four" with: "each value is judged by its
  kind exactly as 03_schemas.md §3.4.1 'Kinds — the one definition' states — `identity`,
  `identity_for:<key>`, `email`, `listing`, `destination`, `own_domain`, `in_account`; a key the row
  declares with no kind, or any other kind, fails". Delete (e) (the `email` kind replaces it,
  including its `PUBLIC_MAIL_DOMAINS` exclusion).
  In (a) and wherever ids are compared, compare through `system_names.normalize_account_id`.
  `checks.identity_result` records `shared_hits` by 03_schemas.md §3.4.3's closed test (values (a)–(d)
  there, exact equality after normalization).
  Tests: 03_schemas.md §3.4.1/§3.4.4's FID-02 assertions (an `asset_link` with `target_system: "ga4"` and
  the pack's own Ads customer id as `target_id` computes `never`; an off-pack `final_url`, `cta_url`
  and `to_url` each compute `never` with a card).
- **R31 · §3.4.1 `outward` · §2.7.** (a) "Allowed reviewer seats per lane": `public_reviewers` when
  `row.public or row.outward` (not `row.public` alone). (b) Rule 4: `hipaa` when regulated and
  (`row.public or row.outward` or effective `data_flow`, R25). (c) Rule 5 (`cta_link`): fire on
  `row.public or row.outward`. The flag is a tier-table row field (03_schemas.md §3.4.1; the §3.4.4
  Flags cells marked **`outward`**; `_nomatch` is `outward: true`). Test: 03_schemas.md §3.4.4's
  "outward" assertions (a `gbp.name_edit` and an `email.inquiry_reply_send` reviewed only by
  gtm-checker are refused `review_missing` at `authorize`; a OtherCompany `email.message_send` needs
  `hipaa`).
- **R32 · §3.10 `requested_via` · §2.4 `pause`/`resume` rows and §2.2b `pauses.py`.**
  (a) `pause`: add `[--self --run <cycle id>]`; write `requested_via: "skill"` by default and
  `"self"` (with `run_id`) only under `--self --run`; breakers, gate-gtm and the migration write
  `null` (03_schemas.md §3.10). (b) `pauses.write_pause(...)`: add keyword arguments
  `requested_via: str | None` and `run_id: str | None`. (c) `pauses.lift_requirement`: return
  `"always"` only for `created_by: "act"` **and** `requested_via: "self"` with a null `ruling_ref`;
  every other pause (a skill-requested `created_by: "act"` pause included) is
  `"operator_or_card"`. In the `resume` row, replace "**`created_by: "act"` with no `ruling_ref` →
  always**" accordingly. A1 test (03_schemas.md §3.10): a `/gtm-pause` pause is refused by a later
  session's `resume` with no marker or card (exit 3); a `pause --self --run <id>` pause is resumable
  by it.

### To `05_approver.md`

- No new request. §3.6/§3.7/§3.9 now follow §5.5 step 5 (`MINT_MARGIN` = `WRITE_TICKET_TTL` + 5
  min, exit 7 `approval_expiring`, `nonce_held` — round 3 applied requests/05_approver.md R34 — the
  `complete` reserve-`ts` rule) and §5.5 3b's enable scope.

### To `06_connectors.md`

- **R28 · FID-02 (`in_account`, part 2) · §6.4 runbook `writes[<row>]` schema and §6.4b validator
  codes.** Add a mandatory before-check step type `account_breadcrumb` for every `writes` entry
  whose row has any `id_fields` key of kind `in_account` (03_schemas.md §3.4.1): before the first
  mutating call it asserts the object's page URL or its account breadcrumb/header contains the
  action's `account_id` (and, when `target_ids` captured an account-level id, that id) and aborts
  `before_mismatch` with no write otherwise. The runbook validator refuses such an entry without the
  step: problem code `in_account_check_missing`. L test (fake browser): a `L.object_delete` whose
  breadcrumb shows another business's account id fails `before_mismatch` with zero mutating calls.
- **R29 · §3.6 setup tickets · §6.6 "Ticket validation".** Replace "It is open, neither closed nor
  abandoned. It is unexpired." with "Its status is `pending` or `bound` (03_schemas.md §3.6) and it is
  unexpired; a `stopped`, `closed`, `consumed`, `abandoned` or `expired` setup ticket is refused
  (exit 7)". A `stopped` setup ticket's operator has already exited, so no capture may arrive after
  it (03_schemas.md §3.6 setup state machine).
- **R33 · FID-02 · §6.2 "Status" paragraph (after target resolution step 6).** The names it lists
  as pending — `system_names.target_ids` (dict form), `normalize_account_id`, `account_keys`,
  `identity_bucket`, `object_scope`, and the `identity_for` kind — are now defined in 03_schemas.md
  §3.22 and §3.4.1; `CSA_SLUG`/`CSA_GSM_PROJECT` in §3.22; `agency_app`/`agency_gsm_projects` in
  §3.20. Drop "pending" for those. `object_scope` is computed by one rule (03_schemas.md §3.4.1),
  not a per-row column: `lsa.budget_edit`, the `L.paid_*` rows and `meta.spending_limit_edit` are
  `account` rows (the lsa/listing grammar yields only the account-level `listing_url`); only the
  `google_ads` campaign money rows and the `meta` campaign/ad-set money rows are `object` without an
  `in_account` id. The pack fields `accounts[].site_host` (`website_wordpress`) and
  `accounts[].listing_url` (listing systems, `lsa`) that `account_keys` reads remain 06's
  pack-schema request to 08 (06 cites it as R1 item 8).

### To `04_hooks.md`

- **R30 · §3.6 Release · §4.5 first paragraph.** Replace "(write/batch → `stopped`, read/setup →
  `closed`)" with "(write/batch/setup → `stopped` with `stopped_at`; read → `closed`; a setup ticket
  is never closed by SubagentStop, 03_schemas.md §3.6)", and add: "The hook never touches
  `actions.jsonl` or the nonce ledger (`S/approval_nonces.jsonl`): outcomes are recorded by
  `complete`/`ticket --close`/reconcile only." B1 test: a SubagentStop for a bound setup ticket
  leaves it `stopped` (RED when setup is closed).

### To `08_seats_wps.md`

- **R27 · §3.4.1 `email` kind · Appendix C (pack-schema follow-up, next to item 29).** `company.py
  validate` refuses an `identity_allowlist.domains` entry that is in
  `system_names.PUBLIC_MAIL_DOMAINS` (03_schemas.md §3.22) — a public-webmail domain may appear only
  as a whole address. Test: a pack listing `gmail.com` in `identity_allowlist.domains` is invalid;
  `owner@gmail.com` as a listed address is valid.

## Round 3 — requests cited by 03_schemas.md §3 (R34–R49)

**Applied in §3 this round:** requests/05_approver.md **R34** (§3.9 refusal renamed `nonce_held`;
holders are full prefixed strings) and **R45** (§3.7 `expires` bullet: the effective AI-spend cap is
the latest by the signed payload's `expires`, then `card_id`, among verified records whose nonce is
consumed — the ledger-order rule is gone). §3.9 ledger lines now also carry `system`/`account_id`
(04_hooks.md §4.6's ledger cross-check reads them) and admit the `trust-edit:<abs path>` holder
(none → consume) that 04_hooks.md §4.3 G-W writes.

**Mint threshold (the round-3 CROSS blocker) — resolved, verified against the current files:**
05_approver.md's "Formats" header defines `MINT_MARGIN = WRITE_TICKET_TTL + 5 min` (= 35 min), its
§5.5 step 5 `mint` row refuses below it with `raise ActError(EXIT_APPROVAL, "approval_expiring")`
(exit 7), and its test uses `MINT_MARGIN − 1 min` → exit 7 / `MINT_MARGIN + 1 min` → minted. §3.6
now names `MINT_MARGIN` and its test uses the same two thresholds. The "≥ 60 min / exit 3" text the
reviewer saw in 05 no longer exists (05 was mid-edit during that review). **Coordinator:** no
choice left to make; if 05 is edited again, §3.6's table row and test and §3.7's `expires` bullet
must move with it.

### To `02_act.md`

- **R34 · §2.8 check 1(a) · `brand_mismatch` (03_schemas.md §3.2 "Brand binding").** When (a)
  fails **only** because an `accounts[]` entry with the same normalized tier system and normalized
  `account_id` exists under a **different** brand, report code `brand_mismatch` (class `never`,
  `card_on_refuse` false — no card) instead of `unlisted_target`; every other (a) failure stays
  `unlisted_target` with its card. Add `brand_mismatch` to the check-1 code list. `propose` does
  **not** exit 3 on it (it is a `refused` event). Also adopt §3.2's two validation stages: stage 1
  (shape, `tier_supplied` tested before `proposal_key_unknown`) before matching; stage 2
  (`money_brief` against the prospective class — NEVER row → `never`; row `money` / non-zero
  `spend_delta_monthly` / no match → `money`) after matching and before any check. A1 test: a
  money-row proposal whose target fails check 1 is recorded `refused` (class `never`, card) with
  its `money_brief` accepted, not exit 3 `money_brief_unexpected`.
- **R37 · §2.4 `snapshot` and §2.6 rule 5a · `committed_ceiling` snapshot contract (03_schemas.md
  §3.2).** `snapshot` writes a `committed_ceiling` entry as
  `<system>_committed_ceiling_<object key>.json` (object key = the non-account-level `target_ids`
  pairs `<key>-<value>` joined by `_`, sorted; `account` for an account-level object) with exactly
  the keys `account_id, target_ids, new_absolute_value, unit, currency, status, budget_owner,
  read_at`; rule 5a admits it only when its `account_id` equals the action's normalized
  `account_id` and its `target_ids` equals `system_names.target_ids(system, target_ref)`. A1 test:
  two snapshots for two campaigns in one run each admit only their own enable.
- **R39 · §2.7 lane verdict · `patient_content_confirmed` (03_schemas.md §3.2
  `contains_patient_content`).** A `hipaa` review passes only when it carries a line
  `{check: "patient_content_confirmed", result, note: "<true|false>"}` whose judged value equals the
  action's `contains_patient_content`; a missing line or a mismatch makes the lane `fail`. Also
  §2.7's `required_lanes`: effective `data_flow` now includes `row.data_flow_on_hipaa and
  pack.regulated ∋ "hipaa"` (03_schemas.md §3.4.1) — the WordPress plugin/theme install/update rows.
  A1 tests as §3.2 and §3.4.4 state.
- **R40 · §2.4 `propose` `--file` restriction.** Extend the runaway-spend stopping set to every
  §3.4.4 stop row: {`google_ads.campaign_budget_edit`, `google_ads.campaign_pause`,
  `meta.campaign_budget_edit`, `meta.campaign_pause`, `meta.adset_budget_edit`, `meta.adset_pause`,
  `meta.spending_limit_edit`, `lsa.budget_edit`, `lsa.account_pause`, `L.paid_budget_edit`,
  `L.paid_pause`, `facebook.boost_stop`, `instagram.boost_stop`, `thumbtack.lead_pause`,
  `angi.lead_pause`} (with the existing `urgency == "urgent"` and lower-value conditions; a pause
  row's `"0.00"` is always lower). P2 test: each is admitted by `--file` with `urgency: urgent`
  under `PAUSE.budget`, and `_nomatch` still is not.
- **R41 · §2.8 check 1 · slug-account purchase systems (03_schemas.md §3.4.4 "Purchase rows").**
  Add, next to the `gtm_ai` exception: systems `vendor`, `domain_registrar`, `stock_media`,
  `paid_api` require `account_id == ctx.company` (the pack slug) instead of (a)–(c); (d) still
  applies to their `id_fields` (`catalog_item`, `own_domain`). `call_tracking` and `sms_provider`
  keep (a) unchanged (a pack `accounts[]` entry is required). P2 test: a first-time
  `vendor.trial_start` with `account_id` = the slug computes `money`; with another string it computes
  `never`.
- **R43 · §2.4 `execute` (CROSS nit).** Pass the full holder string `execute:<action_id>` to
  `reserve`/`consume`/`release` (today the row says `holder=<action_id>`); 03_schemas.md §3.9 and
  05_approver.md §5.5 step 5 both require the prefixed form.
- **R44 · §2.4 `pause` · carry-in pauses are unconditional (03_schemas.md §3.10).** `pause
  --created-by migration` does **not** require an approved card: `pause_carry_in.py` writes every
  listed pause first, then posts the one carry-in card and records its id in each file's
  `card_id`. An `approve` answer changes nothing; a `deny` triggers a list correction that can only
  add pauses. (Also 08_seats_wps.md WP-M row, R49.)
- **R45 · §2.8 check 11 and §2.9 · create rows (03_schemas.md §3.2 "Paused creates").** Check 11:
  for a create row whose `cs` names the object being created (`google_ads.campaign_create`,
  `meta.campaign_create`), `campaign_state: "paused"` means "will be created paused" and the check is
  met by the row's fixed PAUSED status (no re-read, never `before_mismatch` for absence); for
  `meta.adset_create` the parent campaign is re-read as for any `cs` row. §2.9: a `verify_failed`
  whose reason is `created_not_paused` (verify observed a created campaign/ad set as anything but
  `paused`) writes the breaker `PAUSE.<system>` **at once** (not after two failures) and an
  `urgent` `runaway_spend` notice (push). A2 test: a fake connector that creates ENABLED yields
  `verify_failed`, the breaker file and the notice after one occurrence.
- **R46 · §2.8 check 1(d) and §2.4 `propose` · new kinds, nested ids, new refusal codes.** (a) Check
  1(d) applies, from 03_schemas.md §3.4.1, the new kinds `identity_in:<system>` and `catalog_item`,
  the per-row `nested_id_paths`, and the tag-id scan (`checks.TAG_ID_PATTERNS`, on rows whose
  effective `data_flow` is true and on `_nomatch`), with the same `never`/`shared`/card outcomes as
  `id_fields`; `checks.identity_result` reports their `shared_hits`. (b) `propose` exit-3 codes to
  list: `nested_ids_undeclared`, `enable_no_budget_object`, `lead_key_unknown`,
  `lead_key_reserved`, `lead_state_invalid`, `lead_phi_field` (the last four on `lead-append`).
  (c) The hidden-amount guard is a token match (03_schemas.md §3.2), never a regex search. (d) The
  `identity` kind normalizes each allowlist value with its bucket's system (03_schemas.md §3.4.1).

### To `06_connectors.md`

- **R36 · §6.2 "Fresh read at authorize" · Meta ABO campaigns (03_schemas.md §3.2 "Enable
  actions").** A Meta campaign with no budget of its own (ABO) no longer raises `no_budget_object`:
  its `committed_ceiling` is the sum of the configured budgets of its ad sets whose own configured
  `status` is `ACTIVE`, returned with `"budget_owner": "adsets:<id>,<id>,…"` (sorted); mixed units
  → the read returns them and `authorize` refuses `enable_value_mismatch`. The enable before-check
  (API re-read, §6.4 browser before-check) compares the same sum. `no_budget_object` stays for
  object kinds with no budget and no budget-owning parent or children. L test (meta): an ABO
  campaign with active ad sets at 20.00 and 25.00 USD/day reads 45.00 USD/day; RED when it raises
  `no_budget_object`.
- **R38 · §6.2 Execute / before re-check / `verify_read`, §6.4 runbook `writes`, §6.4b validator ·
  paused creates, Meta rows, stop rows, call reporting.** (a) `google_ads.campaign_create`,
  `meta.campaign_create` and `meta.adset_create` always send status PAUSED on the create call (a
  constant of the row, never read from `after`); `verify_read` must observe `paused` and otherwise
  returns `ok: false` with reason `created_not_paused` (02 R45 then breaks at once). (b) Each
  runbook `writes[<those rows>]` entry carries a mandatory `set_status_paused` step before the save
  and a post-save status read; the validator refuses an entry without both
  (`create_status_unpinned`). (c) Replace the "**Money create rows** (a money row with `self_id`,
  e.g. `meta.campaign_create`/`meta.adset_create` …)" bullet: there are no money create rows any
  more; the create rows are T1 `money: false`, `apply` writes `after.value.budget_amount` (converted
  per the unit table) as the paused object's budget, and the create before-check is the absence
  check only. (d) Serve the new rows: `google_ads.{ad,ad_group,keyword}_enable`, `meta.ad_create`,
  `meta.ad_edit` (+ `@paused`; the connector builds the creative from the row's fields and never
  accepts an existing creative id), `meta.ad_pause`, `meta.ad_enable`, `meta.adset_targeting_edit`,
  `meta.adset_bid_edit`, the stop rows `meta.campaign_pause`, `meta.campaign_budget_edit`,
  `lsa.account_pause`, `L.paid_pause`, `{facebook,instagram}.boost_stop`, `{thumbtack,angi}.lead_pause`
  (status rows: committed amount `"0.00"` after the call, like the existing pause rows, and a runbook
  carrying one also carries the `committed_ceiling` read path) and `{thumbtack,angi}.lead_enable`
  (`commits_on_enable`), and `google_ads.call_reporting_edit` (split out of
  `account_settings_edit`). (e) §6.2 "campaign_state" rule: for `google_ads.campaign_create` and
  `meta.campaign_create` there is no campaign to re-read — the row's fixed PAUSED status satisfies
  it; for `meta.adset_create` re-read the parent campaign. L tests as 03_schemas.md §3.2 "Paused
  creates" states.
- **R49b · §6.3/§6.5b `phi_denylist` readers.** No reader change; note that `applies_to` now
  appears only on `agency_app: true` host entries (03_schemas.md §3.20), so every Open Dental entry
  applies to every company.

### To `05_approver.md`

- **R42 · §5.1 rendering and §5.5 3b `build_display` · `display.shared_warning` (03_schemas.md
  §3.7).** Add the optional display key `shared_warning` = `{"hits": [{"where", "value",
  "relationship", "ruling_ref"}]}` (sorted by `(where, value)`), present only on a money action with
  non-empty `check1.shared_hits`, absent (never null) otherwise. The app renders it first, above the
  title ("This change touches a shared or other-company system"); 3b's recompute of
  `build_display` includes it, so a request whose display omits a required warning fails. Update
  §5.1's display key list and any key-set check.

### To `04_hooks.md` (§4.6) and `08_seats_wps.md` (WP-B2, WP-G)

- **R47 · spend rows (03_schemas.md §3.13, §3.19).** (a) `ai_budget.dedup_spend_rows(rows)` is the
  one dedupe over the three-part key, selecting within a key per `churn_report.dedup_spend_lines`'
  rule (non-`unreleased` preferred, last wins; all-`unreleased` → last); §4.6 cites it. (b)
  `agent_budget.py` builders use the transcript's `agent-<id>.meta.json` `toolUseId` as the join key
  for a null-`tool_use_id` row before `TAG_RE`. (c) Builders and `record-session` carry
  `cache_creation_5m`/`cache_creation_1h` from `message.usage.cache_creation` when present. (d)
  `gtm_pricing.model_bucket` is a case-insensitive substring match; null/`<synthetic>`/unknown →
  `opus`, unpriced, note `model_unknown` — §4.6's cap attribution uses it unchanged.

### To `07_notices_schedules.md`

- **R48 · §7.1 notices and the `GTM_Operator.html` page.** (a) `pauses.blocking` writes a `pause`
  notice, severity `warn`, push, for a `PAUSE.*` file that normalizes to no canonical system (after
  case-folding and `-`→`_`), dedupe key `pause_unrecognized:<slug>:<file name>` — reserve the
  `pause_unrecognized:` prefix for in-process writers; the page lists such files as
  "unrecognized — blocks nothing" and lists `PAUSE.csa_scout` as record-only. (b) The `runaway_spend`
  kind is also written by act.py for a `created_not_paused` verify failure (02 R45).

### To `08_seats_wps.md`

- **R35 · Appendix C / `company_schema.json` / `company.py validate` · pack fields.** (a)
  `accounts[].brand`: required on a pack with more than one brand (must reference `brands[].id`; an
  account both brands use is listed once per brand with the same `account_id`), optional on a
  single-brand pack; `company.py validate` enforces both and the schema doc says so (today it says
  "required" unconditionally and the code enforces nothing). (b) Optional
  `identity_allowlist.ga4_measurement_ids`, `.ads_conversion_ids` (`AW-<digits>`) and
  `.meta_pixel_ids` (03_schemas.md §3.4.1 `identity_in`). (c) Optional `accounts[].login_identity`
  (the address a company's browser profile is signed in as; 03_schemas.md §3.23 step 1).
- **R49 · WP-M row, Appendix C item 27 and the coordinator's harvester.** (a) WP-M seeds
  `phi_denylist.json` `agency_gsm_projects` from plan §17 d (`otherapp`) plus operator-supplied
  values (OPERATOR-ONLY card when unknown) and the Agency app hosts from public facts or the
  operator only; no WP lists, reads or greps `~/Desktop/OtherApp` or its GitHub repo (03_schemas.md
  §3.20). `gtm_lists.py` refuses `applies_to` on a non-`agency_app` host entry and on any suffix
  entry (`phi_denylist_scope_invalid`). (b) `pause_carry_in.py` writes the carry-in pauses before
  posting its card (02 R44) and records the carried-in list so `autonomy_ladder.shadow_exit` can
  test "carry-in complete" (03_schemas.md §3.17). (c) Item 27's harvester uses the per-tool keep
  list of 03_schemas.md §3.15 on hipaa packs (Bash: `argv[0]` plus the act.py subcommand and
  `--action`/`--ticket`/`--company` values; never `detail.command` or `detail.file_path`).

## Round 4 — resume after the interrupted round-3 fix (status only, no new request)

Re-verified against the current `03_schemas.md`: all 19 `OPEN_FINDINGS.md` items tagged for §3 and
all 43 round-3 (r1 review) findings are resolved in §3. One wording gap closed this round: §3.2
"Paused creates" now names the `verify_read` reason **`created_not_paused`**, the code R38 (06) and
R45 (02) already use. Still open in other files (unchanged, not re-filed): R14, R17, R19, R21 and
R22–R49 wherever the target file has not landed them.

## Round 5 — incoming requests applied in §3, new requests R50–R55 (2026-09-27)

**Applied in `03_schemas.md` this round** (each was an open request from another owner that the
round-4 status note had not covered):
- `requests/00_global_paths.md` **R22** (§3 intro: every §3 writer calls `gtm_env.refuse_real_state`,
  exit 3 `test_mode_real_state`; §3.11 flat `_all*` markers keyed `flat:<name>:<st_ino>:<st_mtime_ns>`
  + A2 test; §3.20 phi1 listing never descends into a denylisted path; §3.22 `HOLDS_RUNNER_RELPATH` and
  the §1.4 shared-literal constants), **R29** (IMP-03: §3.9 `operator-ok:<command>:<target>` holder,
  none → consume; §3.10/§3.17 signed `gtm.operator_ok.v1` marker; a `lift_card` pause is never lifted
  by any marker — the "or the operator's marker" wording on A0022/C7 is gone), **R32** (§3.16 second
  accepted residual + the no-transcript-text binding rule).
- `requests/02_act.md` items **66** (the three stale "02 does not yet…" notes removed), **75** (§3.11
  "Late cancels", `cancel_late` in the §3.3 fold, send-time re-check also re-reads SMS consent and
  applies the `responded_by` auto-cancel), **80** (§3.14 `lead_invalid` validation list), **83** (=
  00 R29 above). Item **72** is **not** applied — see C4. Item **73** (`rate_caps`) targets the pack
  schema, which 03 does not own (08 Appendix C).
- `requests/04_hooks.md` **R16** (§3.6 batch `money: false`, `batch_money_row`), **R19** (write ticket
  `action_class`/`card_id`/`shared_values`, `card_not_approved`), **R20** (`target_ids`, `self_id_key`,
  `created_ids`; setup `target_ids: {}`; §3.22 `ACCOUNT_LEVEL_KEYS`, `IDENTITY_KEYS`), **R21**
  (`dispatch_brief.steps[].value`/`value_kind`, `signed_amount`, `amount_mismatch`).
- `requests/05_approver.md` **R35 (a)** (`card_deny` in `CANCEL_WHO`), **R44** (§3.7 display source of
  `new_absolute_value`/`unit` = `action.after`; 3b unit equalities), **R50** (§3.6 "release or
  quarantine" everywhere a nonce was released unconditionally).
- `requests/06_connectors.md` **R13** (§3.14 `sink` replay wording, `lead_sink.kind: none`), **R14**
  (§3.22 `target_ids` comment: account-level keys vs object-level `in_account`, 02 already landed it).
- `requests/07_notices_schedules.md` **R34** (§3.2 report-only exception, §3.4.4 row note, §3.7 null
  case iv), **R35** (§3.12 `cycle.py close --if-running`), **R37** (§3.14 lead-id grammar; the pack
  keys are named there and belong to 08 Appendix C).
- `requests/08_seats_wps.md` items **21** (§3.19 hipaa reports quote no `gtm-result` free text),
  **23** (§3.21 `secret_sink`/`act_complete` `acting_as` triggers; §3.6 setup ticket
  `acting_as_expected`), **24** (§3.19 `audit_disagreement_rate` source), **26** (§3.4.1
  `content_data_flow` scans removed patch lines too).

**The 19 `OPEN_FINDINGS.md` items tagged for §3** stay resolved; IMP-03 now uses the signed-marker
design end to end in §3.9/§3.10/§3.17, and FID-24 carries the consent/`responded_by` re-read.

### Conflicts for the coordinator

- **C4 · `approval_expiring` exit code.** 05_approver.md (header "Formats", §5.5 step 5 `mint` row
  and its test) raises `ActError(EXIT_APPROVAL, "approval_expiring")` = **exit 7**; §3.6/§3.7 follow
  05 (exit 7, thresholds `MINT_MARGIN ± 1 min`). 02_act.md §2.4 `ticket` row and its exit map say
  **exit 3** "per 05 §5.5 step 5", and requests/02_act.md item 72 asks 03 to change to 3 — but 05
  does not say 3. Pick one; if 3, 05 changes first and 03 follows (§3.6 table row + test, §3.7
  `expires` bullet).
- **C5 · `marketing_code_paths`.** requests/00_global_paths.md R25 withdraws the key everywhere;
  requests/02_act.md item 74 and requests/08_seats_wps.md item 26 still define exemptions through it.
  03 names neither (it owns no pack schema); 08 Appendix C item 13 follows the coordinator's pick.

### To `08_seats_wps.md` (Appendix C — `company_schema.json` / `company.validate_company`)

- **R50 · pack-schema requests addressed to "03 pack schema".** 03 defines no pack schema; these
  land in Appendix C (the one definition): 00 R25 (`pricing_source_ref` =
  `{"path", "key"}`, refused when `path` matches a `marketing_paths` glob), 04 R26
  (`editable_path_in_state`, `machine_path_not_forwarded`, editable `paths.*` overlapping
  `marketing_paths`), 07 R37 (`lead_sink.response_target_minutes` required int 5–10080 — §3.14 now
  reads it; `budget.paid_daily_usd_alarm`), 08 item 26 (`marketing_paths` entry under the Agency
  root refused), 08 item 27 (`inbox` sentence), 02 item 73 (`rate_caps`). Each with its validator
  test and fixture-pack update.

### To `02_act.md`

- **R51 · §2.4 `ticket --write`/`--write-batch` and the exit-code map · new §3.6 mint refusals.**
  Emit and list exit 3 `card_not_approved` (shared-class write ticket whose card fails
  `cards.require_approved`), `amount_mismatch` (a money ticket's `amount` step ≠ `signed_amount`; no
  ticket, no reserve line) and `batch_money_row` (a batch item whose `money` is not exactly `false`);
  copy `action_class`/`card_id`/`shared_values`, `target_ids`/`self_id_key`/`created_ids`,
  `signed_amount` and `dispatch_brief.steps[].value`/`value_kind` into the minted ticket exactly as
  03_schemas.md §3.6 "Binding fields" states; the setup ticket also carries `acting_as_expected`.
- **R52 · §2.4 `lead-append` · `sink` fallback (requests/06_connectors.md R13, still not in 02).**
  03_schemas.md §3.14 now states `fallback_reason: "sink"` for a `validation`/`auth` sink failure or
  `lead_sink.kind: none`, replayed by the next successful `lead-append`; 02's `lead-append` row names
  only the chain/trust/BAA paths.

### To `04_hooks.md`

- **R53 · §4.6 `effective_ai_caps` (≈ "`"0.00"` = report only").** A signed `"0.00"` `USD/week` is a
  **zero** cap (05_approver.md §5.1 "ZERO CAP", requests/07_notices_schedules.md R32/R33,
  03_schemas.md §3.2); the signed report-only form is `new_absolute_value: null` + `unit:
  "report_only"` on `gtm_ai.weekly_cap_edit` (03_schemas.md §3.7 null case iv), giving `usd: null,
  source: "signed:<request_id>"` (07 R34). Replace the sentence; keep "`company.json` `0` =
  `report_only`" for the unsigned pack value only if 07 R32 still says so.

### To `07_notices_schedules.md` and `05_approver.md`

- **R54 · refusal code for a misplaced `report_only` unit.** 03_schemas.md §3.2 keeps its existing
  code **`money_unit_invalid`** (not `unit_invalid`, as 07 R34 wrote) for `report_only` on any row
  other than `gtm_ai.weekly_cap_edit` or with a non-null value; cite that name.

### To `06_connectors.md`

- **R55 · §6.6 setup-ticket `acting_as_expected` (requests/08_seats_wps.md item 23).** It is now a
  field of the setup ticket itself (03_schemas.md §3.6 `setup` row); `secret_sink.py serve` reads it
  from the ticket file, never from the POST body.

## Round 6 — finishing the interrupted round, requests R56–R63 (2026-09-28)

**Status of the 19 `OPEN_FINDINGS.md` items tagged for §3:** all resolved in `03_schemas.md`.
The interrupted round-6 edit had cited R56–R62 without writing them; they are written below, and
three dangling in-file references were closed: §3.10 now states the "stop-row exemption" that §3.2
"Paused creates" cites; §3.22 now defines `system_names.most_specific_key` (cited by §3.2) and
lists `ad_content` in `NON_INBOX_SNAPSHOTS` (cited by §3.4.4 "Enabling ads").

**Applied in `03_schemas.md` this round** (open requests from other owners that bear on the §3
findings):
- `requests/04_hooks.md` **R32** (§3.6 `card_subject`, `cards.require_approved(..., f"authorize
  {action_id}")`, `card_subject_mismatch`), **R33** (FID-03: §3.6 `commits_on_enable` +
  `budget_readback` on every write ticket, mint refusals `enable_budget_mismatch` /
  `enable_not_agent_executable`; §3.2 and §3.7 now name G-A rule 9d as the browser-path binding —
  the read op is 06's existing **`committed_ceiling`**, which R33 called `configured_budget`),
  **R34** (FID-24: §3.6 `send_bound`/`send_not_after`; §3.11's 19:59 sentence cites it), **R39**
  (§3.6 batch-row wording).
- `requests/05_approver.md` **R47** (§3.6 names the `approval_expiring` raiser), **R56** (§3.2
  `enable_no_budget_object` narrowed to the known within-ceiling child keys; every other non-budget
  `_nomatch` enable takes the ordinary `$` path; A1 tests updated), **R64** (§3.9 cites 05 §5.5's
  reason table).
- `requests/00_global_paths.md` **R39** (§3.17: `autonomy --card` withdrawn, `decided_by` loses
  `card:<id>`; FID-01/IMP-03), **R40** (§3.12 `cycle_id_ok` / `bad_cycle_id_hhmm` in `cycle.py
  open` and `validate_run.py --run`).
- `requests/07_notices_schedules.md` **R54** (§3.12 `cycle.py sync --if-running`), **R57**
  (§3.19 `validate_run.py --since-last-daily`; see the exit-code note under "To
  `07_notices_schedules.md`").
- `requests/06_connectors.md` **R21** item 2 (§3.22 gbp grammar returns only `location_id`; items 1
  and 3 were already in §3.22), **R25** (every real OtherCompanyB id in §3 replaced by the committed
  fixture's synthetic values: Ads `100-200-3000`/`1002003000`, `properties/100000004`, campaign
  `20000000001`).
- `requests/02_act.md` items **85(b)** (§3.6 `upload_assets` = the bound copies under
  `ST/assets/<action_id>/<sha256>`, re-verified by `checks.rebind_assets` at mint; the path stays
  absolute because G-A reads it), **90** (§3.22 `ALLOWLIST_KEY_SYSTEM`), **91(a)(b)** (§3.10
  `PAUSE.chain` `chain_evidence`; `ts` always written by `pauses.write_pause`).
- `requests/08_seats_wps.md` item **38** (§3.20 `url_prefixes`, its match rule, `add_phi_url`).

### Conflicts for the coordinator

- **C4 · `approval_expiring` exit code** — unchanged from round 5; 03 follows 05 (exit 7).
- **C6 · `autonomy --card`.** 00_global_paths.md §1.4 withdrew it (DECIDED there; R39) and §3.17 now
  follows 00; 02_act.md §2.2b (`cards.require_approved` user list, `autonomy_level` event
  `decided_by: "card:<id>"`), §2.3 (L634 "the card routes of §2.4 (`resume --card`, `autonomy
  --card`) still…") and the §2.4 `autonomy` row still carry it. R63 asks 02 to follow 00.

### Not applied (deferred, with reason)

- `requests/08_seats_wps.md` item **40** (§3.7 amount-less request for a revert child under a
  pause): 05_approver.md §5.5 3b still lists four null cases and 02_act.md §2.4 `revert` still uses
  `awaiting_card` under a pause. §3.7 adds case (v) in the same change that 02 and 05 adopt it, so the
  three files never disagree on the null rule.
- `requests/08_seats_wps.md` item **41** (§3.5 `pricing` lane): 00_global_paths.md §0.1 "The
  source" (requests/00_global_paths.md R35, which replaces R25's price bullet) now handles prices
  by `pricing_source_ref` slots with no review lane. 08 and 00 settle which design stands; 03 adds
  the lane only if 08's stands.
- `requests/05_approver.md` **R55 (b)** (`verifications[].observed.status`): the `gtm-result`
  schema is 08_seats_wps.md §8.1, not §3 — forwarded as R62 (c) below.
- `requests/07_notices_schedules.md` **R52** asks for `decided_via`/`card_written_by_agent` on the
  §3.7 request: no §3 change is needed. `decided_via` already exists on the §3.8 approval record
  (values `"app"|"card"`, the names 02 §2.2b and 05 §5.1 use); `card_written_by_agent` is on the
  02 §2.2b `card_recorded` event. See the note to 07 below.

### To `02_act.md`

- **R56 · §2.6 rule 5a, §2.8 check 8 · one enable predicate.** Decide enable scope only through
  `tiers.is_enable_action(ctx, action, row)` (03_schemas.md §3.2 "Enable actions": a
  `commits_on_enable` row, or a `_nomatch` action on a budget object whose `action` tokens contain
  an enable token — `enable`, `enabled`, `resume`, `unpause`, `activate`, `reactivate`, `start`,
  `restart`, `launch`, `unarchive`, `on`), with the budget object decided by
  `system_names.most_specific_key` (§3.22). Add to §2.3's refusal list, from `propose`:
  `enable_no_budget_object` (only for the known within-ceiling child keys),
  `paid_object_use_money_row`, `status_change_use_money_row` (§3.2 status guard).
- **R57 · §2.2b `pauses.blocking` · the stop-row exemption.** `blocking` gains the action (e.g.
  `blocking(ctx, system, cls, op, brand=None, action=None)`): a pause file reading `created_by:
  "breaker"` with null `ruling_ref` and null `lift_card` does not block a **stop action** (03 §3.10:
  matched `class: money` row, `lanes_key: none`, `after.new_absolute_value` `"0.00"` or
  `Decimal`-lower than `before.value.current_absolute_value`, `money_brief.urgency: "urgent"`) at
  `authorize`, `ticket --write`, `execute` and `run-holds`; every other pause still blocks it.
  `ticket --write` sets the §3.6 `stop_exempt: true` exactly when it admitted the mint through this
  exemption. Replace the §2.4 runaway-spend text "under a blocking pause `authorize` exits 5" with
  the exemption for breaker pauses. A1 tests as 03 §3.2 "Paused creates" lists (urgent `"0.00"`
  pause under a breaker `PAUSE.google_ads` → awaiting_approval; a raise and a non-urgent pause →
  exit 5; the urgent pause under a `created_by: "migration"` pause → exit 5).
- **R58 · §2.7 `required_lanes` · the hipaa and reviewer-audience rule.** Take `public_reviewers`
  when `row.public or row.outward`; add `hipaa` when `row.public or row.outward or data_flow or
  (row.hipaa_on_regulated and pack.regulated ∋ "hipaa")`, `data_flow` being the effective one
  (content-derived included, 03 §3.4.1); for a `hipaa_on_regulated` row the hipaa reviewer is
  local-presence-architect, or trust-architect when `after.value` names a list audience (§3.4.1
  `nested_id_paths` custom-audience paths, or `google_ads.audience_list_create`). The hipaa lane's
  `reviews[].lines` must carry `{check: "healthcare_ads_policy", result, note}` on those rows
  (missing or `fail` → lane `fail`).
- **R60 · §2.4 `propose`/`execute`/`ticket --write` · the `home_data` kind (03 §3.4.1).** At
  `propose`: check the four rules (a failure of (1) → exit 3 `source_ref_invalid`; of (2)–(3) →
  class `never` + card, reason `source_outside_home_data`) and set `after.value.source_sha256` and
  `row_count` from the file (a supplied differing value → exit 3 `source_mismatch`). Re-run the
  kind and re-hash/recount immediately before the upload in `execute` and at `ticket --write` mint
  for a browser upload row, failing `before_mismatch` with no upload. Add `source_ref_invalid`,
  `source_mismatch` to §2.3's list.
- **R61 · §2.8 check 1(d) (with R46) · nested ids and tracker tags.** Apply 03 §3.4.1
  `nested_id_paths` closure (exit 3 `nested_path_unlisted`, `nested_ids_undeclared`), the
  `opaque` rule, and the tag-id scan over `checks.TAG_ID_PATTERNS` (kinds `identity_in:<sys>` and
  `tag_bucket:<bucket>`) on every effective-`data_flow` row and on `_nomatch`, with the fail-closed
  `tracker_id_unparsed` (class `never` + card) for a unit naming a `checks.TRACKER_ID_HOSTS` host or
  init token from which no pattern extracted a value. Add the codes to §2.3.
- **R62 · §2.9 `verified` event · `content_digest` (03 §3.4.4 "Enabling ads").** (a) For every
  `google_ads.ad_create*`/`ad_text_edit*` and `meta.ad_create*`/`meta.ad_edit*` action, the
  `verified` event's data carries `content_digest` computed by `verify_read` over the §3.4.4 content
  key set. (b) `authorize` of `google_ads.ad_enable`/`ad_group_enable`/`meta.ad_enable` reads each
  enabled ad's content (connector op `ad_content`, or this run's `ad_content` snapshot) and adds the
  `public_post` lane set unless every ad is content-bound; a failed read → exit 3
  `ad_content_unreadable` (retryable, no event); add the code to §2.3.
- **R63 · §2.2b, §2.3, §2.4 `autonomy` · withdraw `autonomy --card` (00_global_paths.md §1.4, R39;
  C6).** Remove `autonomy --card` from the `cards.require_approved` user list (L277), from L634's
  card routes, and from the §2.4 `autonomy` row; drop `"card:<id>"` from the `autonomy_level`
  event's `decided_by`. `--level autonomous` = criteria met or a consumed signed operator marker;
  A1 test per 00 §1.4 (an approved card with criteria unmet and no marker → exit 3
  `shadow_criteria_unmet`).
- **R64 · §2.3 refusal list · codes defined in 03 this round.** `card_subject_mismatch` at shared
  write-ticket mint; `enable_budget_mismatch`, `enable_not_agent_executable` (`ticket --write`,
  requests/04_hooks.md R33); `approval_expiring` stays exit 7 (C4).

### To `04_hooks.md`

- **R57 (b) · §4.1 rule 6b / `ticket_paused`.** Skip a breaker-written `PAUSE.<system>` or
  `PAUSE.<system>@<brand>` (content `created_by: "breaker"`, null `ruling_ref`, null `lift_card`)
  only for a write ticket whose `stop_exempt` is exactly `true` (03 §3.6); a missing field reads
  false. B1 test: with a breaker `PAUSE.google_ads`, a `stop_exempt: true` ticket's click is
  allowed and a `stop_exempt: false` one is denied; RED when the field test is removed.
- **R65 · §4.1 `phi-host` rule · `url_prefixes` (03 §3.20).** Deny a navigate whose URL matches a
  `url_prefixes` entry (host equal, path equal or continued at a `/` boundary), as
  requests/08_seats_wps.md item 38 asks; nothing in 03 changes 04's host rules.

### To `05_approver.md`

- **R56 (b) · §5.5 3b "Enable binding" (ii).** Replace "action verb is `enable`, `resume` or
  `unpause`" with "`tiers.is_enable_action` (03 §3.2) — the enable-token set, decided on `_`
  tokens", so 3b and 03 decide scope with one predicate.

### To `06_connectors.md`

- **R60 (b) · §6.2 execute steps.** For every `*_upload` row the connector uploads only after
  act.py's `home_data` re-check and re-hash (03 §3.4.1); it never reopens `source_ref` itself.
- **R61 (b) · §6.2 target resolution.** Resolve **each** `in_account` id found through
  `nested_id_paths` under `ctx.account` before the write (a Meta audience id: read the audience's
  `account_id`, which must equal the action's ad account, else `not_owned`, no write); the browser
  runbook's `account_breadcrumb` step covers each.
- **R62 (b) · §6.2 read ops.** Add `ad_content(target_ref)` for `google_ads` and `meta` returning the
  03 §3.4.4 content key set of one ad (Google: headlines, descriptions, final_url, path1, path2;
  Meta: primary_text, headline, description, link_url, call_to_action_type, page_id, creative image
  hash) and its status, and have `verify_read` of the ad create/edit rows return `content_digest`
  over the same set.
- **Note (R33).** 03 §3.6 `budget_readback` is filled from the existing `committed_ceiling` read op;
  no second op named `configured_budget` is needed.

### To `07_notices_schedules.md`

- **Note (R52).** Read `decided_via` from the 03 §3.8 approval record (stored values `"app"` |
  `"card"`; render `"app"` as "signed" if that is the page's label) and `card_written_by_agent` from
  02 §2.2b's `card_recorded` event; no §3.7 field is added.
- **Note (R57).** `validate_run.py --since-last-daily` exits 3 (not 1) when any run fails: IMP-17
  keeps exit 1 for internal errors in every §3 CLI. D9 branches on the JSON `runs[].ok`, which is
  unchanged.

### To `08_seats_wps.md`

- **R58 (b) · KB owner WP (Appendix C).** `knowledge/marketing_kb/compliance/hipaa-marketing-for-practices.md`
  must carry citable entries for Google Ads' "health in personalized advertising" policy and
  Meta's health-targeting restrictions before P2 (UNVERIFIED today); the `healthcare_ads_policy`
  check cites them.
- **R59 · Appendix C (`company_schema.json` / `company.validate_company`).** Define the optional
  `identity_allowlist.{bing_uet_tag_ids, linkedin_partner_ids, tiktok_pixel_ids}` lists (03 §3.4.1
  `tag_bucket:<b>`; cross-pack uniqueness like the other identity buckets) and confirm the phone
  keys 02 §2.2's KEY → KIND table reads (`brands[].nap.phone`, `brands[].phones[]`,
  `identity_allowlist` keys ending `phones`), which 03's `pack_phone` and `destination` `tel:` test
  use. Also state whether `legal_name` and `brands[].display_names` exist
  (requests/02_act.md item 90's question).
- **R62 (c) · §8.1 `gtm-result`.** `verifications[].observed` gains `status` (string), required
  for an action with `display.commits_on_enable: true` and for a pause/stop action
  (requests/05_approver.md R55 (b), misaddressed to 03).
- **R66 · pack-schema requests forwarded (03 owns no pack schema; R50 rule).**
  requests/04_hooks.md **R31** (`company.mirror_files`, `mirror_dir_not_absolute`),
  requests/06_connectors.md **R23** (`identity_allowlist.meta_business_ids`) and **R27** (slug bound
  for `google_sa` companies), requests/00_global_paths.md **R35**/**R36** (the pack parts).

## Round 7 — review-finding fixes in §3, requests R67–R77 (2026-09-28)

**Applied in `03_schemas.md` this round** (the 26 review findings on §3): the content binding of
every delivering action (§3.4.4 "Enabling ads" — campaign, ad-set, ad-group and ad enables, LSA
and listing paid enables, `{thumbtack,angi}.lead_enable`, boosts; `+CD` field), the WordPress
`wp_gtm_user` kind, the boost's signed targeting/duration/post, LinkedIn and YouTube rows and
namespaces, hook-side `phi_denylist` fail-closed, `unmapped` rows in `platform_changes_unlogged_7d`,
least-privilege `scopes` enums, the one `hipaa` lane formula (`makerchecker.needs_hipaa`), the
carry-in card subject and precedence, isolation-hit breaker pauses excluded from ladder lifts,
`after.value.lead_id` binding, `trail_audit.py` (grouped system equality, machine interface,
explain marker, one offserver source), §3.13 claim-copy relabelled as new B2 work with every
builder named, the `gtm_untagged` writer, the system_names seat/`cycle_id_ok` declarations,
`backup_set`'s return-shape change, the hipaa trail record, the `A→T` dedupe merge, the
`test_mode_real_state` exit lists, `proposal_company_mismatch`, the `home_data` registry rule,
`phone` keys, the row-list order wording, compiled `*_RE`, activity-log presence, the pause-name
fold and the display `title` derivation.

### Conflicts for the coordinator

- **C7 · when carried-in pauses are written.** 03 §3.10 (write every listed pause first; the
  `pause_carry_in <slug>` card only confirms the list; `act.py pause --created-by migration` needs
  no approved card, R44) vs 08_seats_wps.md WP-M `pause_carry_in.py apply` (writes only after an
  APPROVE, `act.py pause … --card <id>` per entry, and its test "card answered No → **no** pause
  file written") and 02_act.md §2.2b (the carry-in card consumed per pause name). 03 states its
  text takes precedence (a pause only prevents; waiting on the card is the unsafe direction). R73
  asks 08 to follow; 02's per-name consumption becomes moot for writing and stays only as the
  record that the list was confirmed.
- **C8 · `gtm_untagged` writer.** 04_hooks.md §4 L471 says "`agent_budget.py`'s `gtm_untagged`
  rule"; 04 §4.6 "Not enforced" has gate-gtm log it. 03 §3.13 now names gate-gtm's `apply_t1b` as
  the only writer (R74).
- **C9 · `seat_sets()` shape.** The review suggested `seat_sets() -> dict[str, frozenset]`; 04_hooks.md
  §4 "Seat constants" already defines `seat_sets(*, log=None) -> tuple[set, set, set]` and tuple
  constants. 03 §3.22 declares exactly 04's shape (no change requested).

### To `02_act.md`

- **R67 (a) · §2.4 `propose`/`authorize`/`ticket --write`/`execute`, §2.7, §2.8 check 10 · the
  content binding (03 §3.4.4 "Enabling ads"; supersedes R62 (b), widens R62 (a)).** For every
  delivering row (`google_ads.{ad,ad_group,campaign}_enable`, `meta.{ad,adset,campaign}_enable`,
  `lsa.account_enable`, `L.paid_enable`, `{thumbtack,angi}.lead_enable`,
  `{facebook,instagram}.post_boost`): at `propose` read the item set (connector `ad_content` /
  `profile_content` / `post_content`, or this run's same-named snapshot under the
  `committed_ceiling` admission rules; act.py records an API read as that snapshot and puts its path
  in `before.evidence_ref`), set `after.content_digest` (a supplied differing value → exit 3
  `content_mismatch`), and — unless every item is content-bound — have `required_lanes` add
  `row_lanes["public_post"]` with `public_reviewers` (new rule 7; rule 4's `hipaa` via R68); at
  `authorize` re-read and refuse exit 3 `content_changed` (no event) on a different digest; at
  `ticket --write` mint and `execute` re-read and fail `before_mismatch` (no ticket, no write). A
  failed read at propose/authorize → exit 3 `ad_content_unreadable` (retryable, no event). Check 10
  admits the top-level `after.content_digest` on `+CD` rows. **(b) · §2.9 `verified` event:** every
  `google_ads.asset_create*`/`asset_edit*`, `lsa`/`<L>.profile_text_edit`/`.photo_upload` and
  `{facebook,instagram}.post_publish`/`post_schedule` `verified` event carries the `item_digest`
  its `verify_read` computed (the ad rows already, R62 (a); profile rows digest the whole profile
  after the write).
- **R68 · §2.7 rules 4 and 6 · one `hipaa` formula (supersedes R58's formula; R58's reviewer choice
  and `healthcare_ads_policy` line stand).** Replace rule 4 with a call to
  `makerchecker.needs_hipaa(ctx, row, action)` = `pack.regulated ∋ "hipaa" and (row.public or
  row.outward or effective_data_flow or row.hipaa_on_regulated or content_bound_lanes_added)`, and
  make `checks.effective_data_flow` = `row.data_flow or (row.data_flow_on_hipaa and pack.regulated
  ∋ "hipaa") or checks.content_data_flow(action)` for rules 4 and 6 (03 §3.4.1); no second copy.
- **R72 · §2.9 breakers, §2.2b `pauses.write_pause`.** `write_pause` gains `cause: str | None`;
  every breaker writes its trigger (`verify_failed`, `created_not_paused`, `isolation_hit`, …),
  the isolation-hit breaker (`isolation_hit_ingested`) writes `cause: "isolation_hit"`, and every
  other writer writes null (03 §3.10, §3.17 "Isolation-hit pauses").
- **R77 · §2.3 refusal list, §2.2b `pauses.blocking` (amends R57).** Add, from `propose`:
  `proposal_company_mismatch` (exit 3; the body `company` check — 02's exit-13 `company_mismatch`
  stays the id-argument check), `boost_post_required`, `content_mismatch`, and the stage-1
  `after.value.lead_id` rule under `lead_id_invalid` (03 §3.2 `recipient`); from `authorize`:
  `content_changed`, `ad_content_unreadable`. The stop-row exemption never covers an enable action
  (`tiers.is_enable_action`) or a `current_value: zero` row (03 §3.10).

### To `04_hooks.md`

- **R74 · §4 "Seat constants" L471.** Reword "`agent_budget.py`'s `gtm_untagged` rule" to
  "`agent_budget.py`'s seat-set use"; the only `gtm_untagged` writer is gate-gtm's `apply_t1b`
  (`_lib.log("gtm_task_gate", "gtm_untagged", tool_use_id=…, agent_type=…, session=…)`, 03 §3.13).
- **R76 · §4.1 G-A, §4.4 path gate, G-B · `phi_denylist.json` unreadable (03 §3.20).** In a GTM
  session or for a GTM seat, an unreadable, unparseable or schema-invalid file (and an absent one
  for a `regulated ∋ hipaa` or `otherapp` pack) fails closed: G-A denies navigation and ticketed
  calls to hosts outside the pack's domains and its channels' runbook read/login hosts; the path
  gate and G-B deny Read/Grep/Glob/Bash targets outside `H`, `R/tools/gtm`, `R/knowledge/marketing_kb`;
  each deny logs `phi-denylist-unreadable`; the first per session writes the urgent `trust` notice
  (`dedupe_key` `phi_denylist_unreadable:<slug>`). G tests as 03 §3.20 lists.

### To `06_connectors.md`

- **R67 (c) · §6.2 read ops (widens R62 (b)).** `ad_content(target_ref)` for `google_ads`/`meta`
  also accepts a campaign, ad-group or ad-set target and returns every item of 03 §3.4.4's content
  set (ads and, for Google, the assets that would serve) with its status and content keys;
  add `profile_content(target_ref)` (`lsa`, `L` systems: business name, profile text, services,
  website/CTA URL, phone, photo hashes — never reviews) and `post_content(target_ref)`
  (`facebook`, `instagram`). The enable/boost `before` re-check re-reads the set and fails
  `before_mismatch` on a different `content_digest`.
- **R70 (b) · §6.6 capture script.** For `website_wordpress.application_password_create`, read the
  `user_login` user's roles before creating/reading the application password; anything but
  exactly `["editor"]` → abort `before_mismatch`, no password created, no GSM write (03 §3.4.1
  `wp_gtm_user`).
- **R71 · §6.2 `post_boost`.** Apply sends exactly the signed `targeting`, `duration_days`, amount
  and unit for the post in `target_ref` (post-level form only); resolve every `in_account` audience
  id under the brand's `meta` ad account (the pack entry with `system: "meta"` and the action's
  `brand`), else `not_owned`, no write.

### To `07_notices_schedules.md`

- **R75 (a) · §7.5 W2.** Every `activity_log.py explain` call a GTM run makes passes `--notes
  explain:<cluster id>`; the weekly program metrics and the `unexplained_changes_attributed` field
  come from `trail_audit.audit` (03 §3.19), never from parsing `activity_log.py audit` output.

### To `08_seats_wps.md`

- **R69 · Appendix C (`company_schema.json`, `company._ACCOUNT_ID_ALLOWLIST_KEYS`) + coordinator
  harvester item.** Add optional `identity_allowlist.linkedin_page_ids` and
  `identity_allowlist.youtube_channel_ids` (cross-pack uniqueness like the other buckets) and admit
  `accounts[].system` `linkedin`/`youtube`. Harvester (`harvest_tool_trail.DEFAULT_HOST_SYSTEMS`):
  `linkedin.com` → `linkedin`, `studio.youtube.com`/`youtube.com` → `youtube`. WP-L: runbook stems
  `linkedin`/`youtube` whose hosts ⊆ 03 §3.22 `platform_hosts`.
- **R70 (a) · Appendix C.** Every `website_wordpress` `accounts[]` entry requires `gtm_user_login`
  (the dedicated Editor user, plan §17 j); `company.py validate` refuses an entry without it.
- **R73 · WP-M `pause_carry_in.py apply` (C7).** Write every listed pause first (`act.py pause
  --created-by migration`, card id recorded when known) and let the `pause_carry_in <slug>` card
  confirm the list; "No" triggers a list correction that may only add pauses. Change the M test
  "answered No → no pause file written" to "answered No → the files stay".
- **R75 (b) · §9 `/gtm-audit`.** Its `explain` step passes `--notes explain:<cluster id>`.
- **Note · WP-B2 file set.** 03 §3.13's claim copy is new work in `b2_task_wiring.patch`
  (`_build_claim_record` and the seven spend-line shapes), and `ai_budget.dedup_spend_rows` gains the
  `A→T` sidecar/claim merge; WP-G gains `tools/gtm/trail_audit.py` (03 §3.19).

## Round 8 — review-finding fixes in §3, requests R78–R91 (2026-09-28)

**Applied in `03_schemas.md` this round** (the 31 review findings on §3): one hipaa rule for
`money_brief` (side-stored, never refused) and a closed `why` grammar (§3.1); `drafted_by` derived,
never supplied (§3.2); the three-step 1a/1b/2 validation order (§3.2); browser paused creates as
detect-after until a P0 probe passes (§3.2); hipaa message rows template-only (§3.2); keyword and
targeting coverage of enables on hipaa packs (§3.4.1, §3.4.4); the `home_data` enumerator over
both registries unfiltered (§3.4.1); the disclosed `system_unknown` / `gtm_template_unlisted` /
`nested_path_unlisted` deviations with an operator-visible `table_gap` notice and the
`vendor.subscription_create` route for a new paid channel (§3.4.2); `url_prefixes` at propose
(§3.4.4 NEVER); `channel_type: [SEARCH]` on `google_ads.campaign_create`, the fail-closed content
reader with a `serving` inventory, Meta video creatives, and `gtm.version_publish` `+CD` (§3.4.4);
late-cancel ticket transitions (§3.6, §3.11); hipaa display values (§3.7); `PAUSE.<system>`
command list and `PAUSE.csa_scout` as a shared-identifier pause (§3.10); `missed` trigger (§3.12);
sidecar back-fill scoped to GTM/department seats (§3.13); `LEAD_ID_RE` slug group (§3.14); hipaa
trail record keys, order and unattributed sink (§3.15); `metrics.json` `schema` key (§3.18);
distinct-event isolation metric, `trail_audit` interval and cluster id (§3.19); `phi_adjacent`,
`agency_app` browser rule, directories-only PHI1 listing (§3.20); `tool_use_id` on isolation hits
(§3.21); `website` alias, `site_url` source, `normalize_interface` (§3.22); reconcile
`activity_log_id`, object fallback and the explained join (§3.23).

### Conflicts for the coordinator

- **C10 · `money_brief` on hipaa packs (supersedes R22's `money_brief` half).** 02_act.md §2.2b
  (L459-462, landed from R22) refuses every `money_brief` string that fails
  `^[A-Za-z0-9_.:§#/ -]{1,120}$` and says they are "never side-stored"; 03 §3.1 now side-stores the
  six free-text keys and never refuses them for their characters, which is what 05_approver.md
  §5.1 step 1 already assumes (it renders `money_brief` display keys by pointer). 03 states its
  text takes precedence (the refusal form made OtherCompany `$` cards unable to carry `$`, `%` or `,`,
  plan §20.8). R78 asks 02 to follow.
- **C11 · hipaa `title`.** 05_approver.md §5.1 step 1 lists `title` among the pointer-form display
  keys ("title and `object` via `object_display`"); 03 §3.7 "Regulated packs" makes `title` the
  bare label string (no `object_display` operand) so `title` stays a string and the recompute is
  byte-stable. R90 asks 05 to follow.

### To `00_global_paths.md`

- **R91 · §1.2 "Listing shapes" (`othercompany_listing.json`).** Adopt 03 §3.20's directories-only
  shape: no file entries or file names anywhere; depth-1 directories by path; deeper directories
  as `{parent_depth1, depth, name_sha256, files, bytes, ext_histogram}`. Add: the PHI1 review
  dispatch runs with cwd under the OtherCompany home (transcripts inside `purge-untrusted`'s scope).

### To `02_act.md`

- **R78 · §2.2b "HIPAA side-store form" (replaces R22's refusal text, C10), §2.4 `propose`.** In
  the "It applies to:" list add the six free-text `money_brief` keys (`object_display`,
  `metrics_summary`, `best_practice_source`, `expected_effect`, `risk`, `reversal`) to the
  side-stored fields; `urgency` stays inline (enum). Delete "**Refused, not stored (R22):** every
  string value of `proposed.money_brief` … never side-stored" and replace the `why` half with 03
  §3.1's closed grammar: `why.plan_ref` full-matches
  `^(SP-[A-Za-z0-9-]{1,40}|MASTER|PLAN|exp_<ctx.company>_\d{4})( §[0-9]+(\.[0-9]+)*)?$` and a
  non-null `why.metric_id` is a registered `metrics.json` id, and an `SP-…` plan_ref's plan id (the
  whole `SP-…` token before any ` §`) names an existing plan — `<plan id>.md` (e.g. `SP-GBP.md`), exact case-sensitive name from `os.listdir`,
  a regular non-symlink file directly in `<home>/<paths.plans_dir>/` (03 §3.1, DECIDED (wave1c):
  on-disk listing, not HEAD) — else `hipaa_free_text`. In §2.4
  `propose`, "on a hipaa pack `money_brief`/`why` are checked per §2.2b" becomes "`why` is checked
  per §2.2b and `money_brief`'s free-text keys are side-stored". Notices, cards and the activity log
  never render `money_brief` text on a hipaa pack (05 §5.1 already; §2.10 hipaa rule). Test: 03
  §3.1 P2 tests (a) and (b).
- **R79 (a) · §2.3 refusal list / §2.4 `propose`.** Add `drafted_by_supplied` (exit 3, stage 1a,
  before `proposal_key_unknown`); `drafted_by` stays derived as §2.4 already states.
- **R80 (a) · §2.4 `ticket --write`.** For a row in `connectors.PAUSED_CREATE_ROWS` on the browser
  path, refuse exit 3 `create_not_agent_executable` (no ticket, no reservation, action stays
  `authorized`) unless the runbook's `writes[<row>].paused_create_probe` is a non-empty string.
- **R81 · §2.2b `hipaa_redact` (c), `checks.hipaa_inbox_shape`, §2.8 check 5.** Extend the
  template rule from `inbox_reply` rows to every `recipient_required` row on a hipaa pack
  (`{email,sms}.message_send`): `after.value.template_id` required, `after.text` byte-equal to the
  template, `after.value.subject` null or byte-equal to the template subject, `before.text`/`value`
  null; same codes; `hipaa_redact` admits the proven `text`/`subject`/`template_id` inline.
- **R83 (a) · §2.4 `propose`.** On `system_unknown`, `gtm_template_unlisted` and
  `nested_path_unlisted`, write the `table_gap` notice of 03 §3.4.2 (validated tokens only; never
  `rationale` or `money_brief`) before exiting 3.
- **R84 · §2.8 check 1 (PHI clause).** Add `url_prefixes` matching (03 §3.20 match rule) of
  `target_ref` and of every `destination`/`listing`/`own_domain` value and every absolute `https`
  URL in an `opaque`/`destination` nested leaf → class `never` with a card.
- **R85 (a) · §2.4/§2.7/§2.9 (widens R67 (a)).** `gtm.version_publish` joins the `+CD` rows:
  read `workspace_content`, set `after.content_digest`, run check 1's `gtm.workspace_edit`
  `nested_id_paths` closure and tag-id scan over the read bodies (failure → class `never` + card),
  review the `tracking` lane over the snapshot; `authorize`/`execute` re-read. Every read refuses
  `ad_content_unreadable` per 03 §3.4.4 "The reader fails closed" (unmodelled `serving` type,
  missing inventory, empty ad list on a campaign/ad-group/ad-set enable). On hipaa packs add
  `targeting` items (keywords, audiences, criteria, ad-set targeting) to the campaign/ad-group/
  ad-set enable reads; a non-content-bound targeting item adds `hipaa` only.
  **(b) · §2.9 `verified`:** `gtm.workspace_edit` records one `item_digest` per entity it wrote;
  `google_ads.keyword_add`, `google_ads.campaign_create`, `meta.adset_create` and
  `meta.adset_targeting_edit` record the `item_digest` of the targeting items they wrote (hipaa
  packs).
- **R88 (a) · §2.4 `ticket`.** `ticket --read/--write/--write-batch/--setup` refuse any host equal
  to or under a `phi_denylist.json` `agency_app` host (exit 3 `ticket_host_agency_app`).
- **R89 (a) · §2.2b `pauses.blocking`.** Block (exit 5) every action whose `check1.shared_hits`
  value equals a `shared_identifiers[]` entry's normalized `value` when that entry's `pause_names`
  names a present pause file; such names are never "unrecognized"; the shared card's machine block
  gets `**Paused by:** <name>`.

### To `04_hooks.md`

- **R86 · §4.1 G-A, §4.2 G-B, §4.4 path gate (log fields) and `append_isolation_hit`.** Every deny
  row these three hooks log carries `company` (the GTM company, or null), `session` and
  `tool_use_id`; `append_isolation_hit` writes the payload's `tool_use_id` (03 §3.21).
- **R88 (b) · §4.1 G-A.** For a non-`othercompany` company, an `agency_app` host admits only
  ticketless non-mutating calls; every mutating call and every call under any ticket there is
  denied `agency-app-write` (unconditional in GTM scope, no isolation hit).
- **R89 (b) · §4.1 rule 6b.** Deny a shared write ticket's mutating call when any of its
  `shared_values` equals a `shared_identifiers[]` value whose `pause_names` names a present pause.

### To `05_approver.md`

- **R90 · §5.1 step 1 (C11).** On a hipaa pack `title` is the bare row label (03 §3.7 "Regulated
  packs"), never a pointer; `object` and the five other `money_brief`-derived keys are the stored
  `{digest, pointer}` objects; `after_summary`/`after_full` come from `hipaa_redact`ed `after`.
  3b's `build_display` recompute uses exactly these values.

### To `06_connectors.md`

- **R80 (b) · §6.4b runbook validator.** Admit `writes[<row>].paused_create_probe` (non-empty
  string: the plan §17 probe record id) only on `connectors.PAUSED_CREATE_ROWS`; define
  `PAUSED_CREATE_ROWS`.
- **R85 (c) · §6.2 read ops.** Every `ad_content`/`profile_content`/`post_content` result carries
  a `serving` inventory (03 §3.4.4: Google channel type, ad types, asset/field types, asset groups;
  Meta creative forms); Meta ad items carry `image_hash` or `video_id`; on hipaa packs the Google
  and Meta enable reads return `targeting` items. Add `workspace_content(target_ref)` for `gtm`
  (workspace status against the live version, each changed entity's full resource minus
  `fingerprint`, `path`, `tagManagerUrl`, `workspaceId`); the publish `before` re-check re-reads it.
- **R88 (c) · §6.4b runbook validator.** Refuse `read_hosts`, `login_hosts` or
  `writes[].allowed_hosts` naming a host equal to or under an `agency_app` host
  (`runbook_agency_app_host`).

### To `07_notices_schedules.md`

- **R83 (b) · §7.1.** Register the `table_gap` notice (kind `task`, `warn`, push, `dedupe_key`
  `table_gap:<slug>:<code>:<system>:<row id>:<12-hex>`), rendered only from validated tokens.

### To `08_seats_wps.md`

- **R79 (b) · H2 primers.** Drafter primers must not emit `drafted_by` in `proposals[]` (it is
  refused `drafted_by_supplied`; act.py derives it).
- **R80 (c) · P0 list.** Add probe `paused_create_ui` per system (Google Ads, Meta): can the UI
  save a new campaign / ad set paused before any serving state; record the result in plan §17.
- **R82 · Appendix C (`company.py`).** Add `all_registered_roots() -> list[tuple[str, str, str]]`
  = `(slug, "gtm"|"repo", normpath(expanded root))` for every entry of `_gtm_registry_companies()`
  and of the **unfiltered** `_repo_registry_repos()` — no allowlist, no name exclusion, no duplicate
  removal, no `resolve()`/`realpath`/`stat`; a malformed entry or a present-but-unreadable registry
  raises `CompanyError`. Test: a slug in both registries with two roots yields both.
- **R87 · Appendix C (`company_schema.json`).** Add optional `phi_adjacent: bool` ("markets or
  operates an integration with a PHI-bearing system"); WP-M sets it on the OtherApp pack; `validate`
  refuses `phi_adjacent: false` with a non-empty `regulated`. No code tests the slug `otherapp`
  (amends R76: 04_hooks.md's absent-file fail-closed branch keys on `regulated ∋ hipaa` or
  `phi_adjacent: true`, never on the `otherapp` slug).
- **R89 (c) · Appendix C (`shared_identifiers[]`).** Add optional `pause_names: list[str]` (each a
  `PAUSE.<x>` file name); WP-M writes `["PAUSE.csa_scout"]` on every OtherCompanyB Scout entry the R12
  ruling covers.

## Round 9 — wave1c review-finding fixes in §3, requests R92–R94 (2026-09-28)

**Applied in `03_schemas.md` this round:** the hipaa trail shaping's placement (a `hipaa_shape`
helper inside `try_classify_call`, after `finalize_record`, before each branch's `return`; a
slug whose pack failed to load counts as hipaa) and a Bash fixture the committed attribution
actually harvests (§3.15); a `validate_company` guard so no `paths.*` value re-admits
`ST/untrusted/` or `lead_fallback*.jsonl` into the backup set, plus a `backup_set` realpath drop
(§3.1); the cache-creation split moved into §3.13 as an explicit B2 change scoped to GTM lines,
with `sum_transcript_tokens` and `tokens_total` unchanged (§3.13, §3.19). Findings r2 (1)–(4)
were already applied in Round 8 (R78, R80, R85; C10).

### To `08_seats_wps.md`

- **R92 · Appendix C item 27 (`harvest_tool_trail.py`).** Replace "for a record attributed to a
  hipaa pack the harvester writes …" with: "a new pure helper `hipaa_shape(record, name,
  tool_input, home) -> dict` in `harvest_tool_trail.py` is called inside `try_classify_call`, in
  every branch, immediately after `finalize_record` and before that branch's `return`; the
  return shape `(company, record)` and both call sites are unchanged. A browser record is shaped
  when `company is None` or `packs.get(company)`/`packs.get(identity_hit)` has `regulated ∋
  hipaa`; a `Write`/`Edit`/`NotebookEdit`/`Bash`/`Agent` record when `packs.get(company)` does;
  a slug in `homes` absent from `packs` (pack failed to load) counts as hipaa. The shaped record
  is exactly 03_schemas.md §3.15 'The exact trail record on hipaa packs'." Add to its test: the
  three §3.15 attribution tests (unattributed with a OtherCompany `identity_hit`; non-hipaa
  `company` with a OtherCompany `identity_hit`; unloadable OtherCompany pack). No new Bash attribution
  rule: an `act.py` command is harvested only when its text contains a registered home path (the
  committed `str(home) in command` rule), and the §3.15 Bash fixture is `python3
  /abs/tools/gtm/act.py lead-append --company othercompany --file <PHI1 fixture
  home>/.claude/gtm/drafts/lead.json`.
- **R93 · Appendix C item 5 (`company.py`).** Add: "`validate_company` refuses, on every pack,
  any `paths.*` value (every key but `mission_records`) whose `os.path.normpath` text is equal to
  or an ancestor of `.claude/gtm/state`, or equal to or under `.claude/gtm/state/untrusted`, or a
  `.claude/gtm/state/lead_fallback*.jsonl` file (reason `paths.<key> must not contain the GTM
  state directory or its untrusted store`); descendants of the state directory stay legal.
  `backup_set` drops any `paths.*` entry whose `os.path.realpath` is equal to or an ancestor of
  `realpath(<home>/.claude/gtm/state)` or equal to or under its `untrusted/`." Test: 03_schemas.md
  §3.1 (a `data_dir: ".claude/gtm"` pack fails validate; with validate bypassed the expanded
  `backup_set` omits `ST/untrusted/u1.txt` and `ST/lead_fallback.jsonl`; each RED when its guard
  is removed).
- **R94 · §9 B2 row and Appendix B item 173.** Add "03_schemas.md §3.13 'Cache-creation split on
  GTM lines' (`sum_transcript_cache_split` in `agent_budget.py`; split keys only on lines whose
  `gtm` is non-null; `sum_transcript_tokens` and `tokens_total` unchanged)" to B2's owned list,
  and to the `b2_task_wiring.patch` contents named in the B2 row and item 173 (it edits
  `hooks/agent_budget.py`, which is never saved live during Wave 2). B2 owns the §3.13 tests
  (byte-identical `code-reviewer` line, `churn_report` metric 5 and `record_review.py` model join;
  split sums to `cache_creation`; missing split → both `null`). WP-G's `record-session` keeps its
  own split per §3.19.
