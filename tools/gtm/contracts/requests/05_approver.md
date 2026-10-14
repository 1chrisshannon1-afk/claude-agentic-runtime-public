# Requests from `05_approver.md` (§5 owner) to other section files

Each request is needed so that the §5 fixes for FID-03, IMP-05 and FID-07 hold end to end. §5 now
references every item below by the exact name given here.

## R1 · FID-03 · `03_schemas.md` §3.4.1 + §3.4.4 (row flag)
Add the row field `commits_on_enable` (bool, money rows only, default `false`). Set it to `true` on
`google_ads.campaign_enable`, `lsa.account_enable` and `L.paid_enable`, and on any other money
`enable` row that commits a configured ceiling (not on `amount_required: false` rows such as
`google_ads.auto_apply_enable`). Normative text for those rows: `after.new_absolute_value` = the
object's configured committed ceiling (daily/lifetime budget or pay-per-lead cap) and `after.unit` =
its period (plan §20.13: a paused object's budget is committed only at enable).

## R2 · FID-03 · `03_schemas.md` §3.7 (approval request `display`)
Add `display.commits_on_enable` (bool). A2 copies it from the matched row's flag (R1), never from
`money_brief`. For such rows, `display.current_value` is the ceiling that `authorize` read fresh
(R3). `05_approver.md` §5.1 step 3 uses the flag for the "Enable and commit …" reason string and
refuses Approve when `current_value` ≠ the payload value. The signed payload key set is unchanged.

## R3 · FID-03 · `02_act.md` §2.6 (`authorize`) and §2.8 check 8
For a row with `commits_on_enable: true`, `authorize` fills `before.value.current_absolute_value`
from a fresh read of the object's configured ceiling before it creates the approval request. The
read is the connector read for API systems, or a snapshot taken in the same run for browser
systems. `authorize` refuses (suggested code `enable_value_mismatch`) when that value ≠
`after.new_absolute_value`. `05_approver.md` §5.5 step 3b re-checks this equality at every
`verify` stage.

## R4 · FID-03 · `06_connectors.md` §6.2 (before re-check) and §6.4 (mandatory before-check list)
For `commits_on_enable` rows, `plan()`/`apply()` (API) and the runbook before-check (browser)
re-read the object's configured ceiling (budget/cap amount and period) immediately before the
enabling call. They fail `before_mismatch`, with no write, when it differs from the expected value
act.py passes, which is the verified payload's `new_absolute_value`/`unit` (`05_approver.md` §5.5
step 3b, "Enable binding"). The runbook validator should refuse an enable write runbook that has no
before-check on the configured ceiling.

## R5 · IMP-05 · `03_schemas.md` §3.19 (`gtm_pricing`)
Amend `price_usd`:
(a) Read `telemetry/pricing.json` directly with `json`, never via `hooks/cycle_telemetry.py`.
(b) Carry the constant `CCDASH_PRICING_SHA256`. Read `usage-dashboard/ccdash/pricing.py`'s bytes
    and sha256 them before importing. Load the module from those same bytes only when the hash
    equals the pin; otherwise use `telemetry/pricing.json` alone.
(c) Return or record the note `ccdash_unpinned` in that case, so `week_to_date_usd` and perf report
    callers can surface it.
Reason: the ccdash file is git-ignored, so the §5.5 HEAD check cannot cover it (§5.5 step 2).

## R6 · IMP-05 · `04_hooks.md` §4 ("Seat constants — defined once …" paragraph) and §4.6 F-trust
(a) Change `seat_sets()`'s rule from "reads `model_policy.json` … else the constants" to: per set,
    the union of the `system_names` constant and the policy list. The policy can add seats, never
    remove one. When the policy lacks a constant seat, log `gtm-seats-policy-narrower` through the
    caller-supplied logger. `knowledge/model_policy.json` is deliberately not a TRUST_PATH
    (`05_approver.md` §5.5 step 2).
(b) In the F-trust paragraph, extend the B2 falsification test:
    - an uncommitted edit to `telemetry/pricing.json` puts the company in budget state;
    - an edit to the ignored ccdash file that returns 0 does not lower week-to-date USD below the
      `telemetry/pricing.json` price.

## R7 · FID-07 · `02_act.md` §2.3 (dispatch order / `make_ctx`)
§5.5 step 2 now names the pack-from-HEAD rule as `02_act.md` §2.3, refusal `pack_uncommitted`.
Please use that section and that refusal name when landing FID-07's fix (pack loaded via
`git -C <H> show HEAD:.claude/gtm/company.json`, exit 13 on working-tree difference), or tell the
coordinator the final name so §5.5 can match it.

## R8 · `08_seats_wps.md` Appendix B (DECIDED HERE index)
Add entries:
- "05_approver.md §5.5 — `telemetry/pricing.json` joins TRUST_PATHS. The git-ignored ccdash pricing
  file is instead hash-pinned in `gtm_pricing.py` (checked before import; fallback
  `telemetry/pricing.json`). `model_policy.json` is not a TRUST_PATH; `seat_sets()` takes the union
  with the constants (IMP-05)."
- "05_approver.md §5.1/§5.5 — enable rows (`commits_on_enable`): the signed value must equal the
  configured ceiling that authorize read fresh, and execute/runbook re-read it before enabling
  (FID-03)."
Also amend item 37 to add `telemetry/pricing.json` to its list.

---

# Revision 2 (2026-09-27): requests from the §5 review-finding fixes

**Name note on R1/R2.** `03_schemas.md` now uses `commits_on_enable` for the row flag (§3.4.1, rows
at §3.4.4). §5 uses the same name. The `display.commits_on_enable` key R2 asks for is still missing
from §3.7's example and field list, and the approver app keys its enable check on it. If 03 ever
settles on another name, rename it in 05 in the same commit.

## R9 · FID-03 · `02_act.md` §2.6 (`authorize`), §2.8 check 8 · `03_schemas.md` §3.2 "Enable rows"
The enable binding applies to every money-class action whose action verb is `enable`, `resume` or
`unpause`, `_nomatch` included (e.g. a Meta ad set enable), not only to `commits_on_enable` rows.
Such an action must carry `after.new_absolute_value`/`unit` (its configured ceiling). An amount-less
one is refused at `propose` and `authorize` with exit 3 `enable_amount_required`. `authorize` fills
`before.value.current_absolute_value` exactly as for `commits_on_enable` rows (API: connector op
`committed_ceiling`; browser: the `before.evidence_ref` snapshot). Also state in §3.2 that for
browser rows the value is a snapshot, and that the runbook's ceiling before-check (06 §6.4) is the
binding control.

## R10 · `03_schemas.md` §3.7 (approval request) and §3.8
(a) Add request field `display_b64` = base64 of `canon(display)`, built by
`approvals_verify.build_display(ctx, action)` (deterministic). The app renders only from it.
(b) Add a 12th signed payload key `display_sha256` = `"sha256:" + hex(sha256(decoded display_b64))`.
Update "Signed payload keys are exactly …" to list it.
(c) Add display fields: `commits_on_enable` (bool, from the row, R2); `object_ref` (the action's
`target_ref` verbatim, plus its verified `id_fields` values, never from `money_brief`); `after_full`
(the untruncated `canon(after)` text; untrusted text as §3.15 pointers); `spend_delta_monthly` when
set. Keep `after_summary` (≤ 400 chars) as a heading only.
(d) §3.8: approval and denial records are published create-exclusive (temp file + `link()`;
`EEXIST` = the earlier decision stands). Directory mode 0700. Optional field
`"decided_via": "app"|"card"` (a card only ever denies, 05 §5.1 step 5).
(e) The `commits_on_enable` bullet in §3.7: for browser rows `current_value` is the snapshot value,
not a fresh platform read.

## R11 · `02_act.md` §2.3 (dispatch order, trust root) and §2.9 (`PAUSE.trust`)
(a) act.py imports `approval_sig` and calls `trust_root_ok(R, require_key=False)` **before**
importing gtmlib or any other `tools/gtm` module, for **every** subcommand. On failure it imports
nothing further and exits 11 for every subcommand, read-policy ones included.
(b) The only exception is `lead-append`, which writes its raw input stdlib-only to
`S/lead_spool/<ts>_<hex>.json` (0600) and exits 0 with `result.fallback: "trust"`. The first
trusted `lead-append` replays the spool into the company's lead fallback path. This replaces the
current "writes its row to `ST/lead_fallback.jsonl`" wording for the trust case, which needs gtmlib
to resolve `ST`.
(c) A dispatch-time failure writes the trust notice but **never** `S/PAUSE.trust`. Only the daily
`trust_check` writes `PAUSE.trust`, after its settle re-check (05 §5.6). Update §2.9's "and by
act.py whenever the trust-root check fails at dispatch" accordingly.
(d) Trust notice dedupe key: replace `trust:<sorted-paths sha8>` with a citation of 05 §5.6's
formula `trust:` + sha256(canon(sorted entries))[:8], and the title formula given there.
(e) The refusal reason is the failing kind from `approval_sig.TRUST_KINDS`
(`trust_root_mismatch`, `trust_paths_modified`, `trust_paths_untracked`, `trust_interpreter`,
`trust_git_error`), not always `trust_root_mismatch`. `trust_git_error` exits 11 and writes no
`PAUSE.trust`. Also add `key_not_installed` (exit 11, no pause, no notice).
(f) act.py's first statements re-exec it under `python3 -I -S -B -X pycache_prefix=<fresh P>` and
append (never prepend) `R/tools/gtm` to `sys.path` (05 §5.5 step 0). The ≤ 60-line limit on act.py
needs to leave room for this.
(g) §2.1 layout: add `tools/gtm/ed25519_verify.py` (A2, stdlib-only RFC 8032 verifier). Change
`approval_sig.py`'s description to "stdlib only; trust root, `verify_raw`, `verify_signature`,
`trust_check`, canonical CLI `--trust-check`/`--self-test`".

## R12 · `00_global_paths.md` §0 (stdlib-only rule) and the env-var table
Remove the `cryptography` exception: `approval_sig.py` is stdlib-only. ECDSA is verified with
`/usr/bin/openssl`, Ed25519 with `tools/gtm/ed25519_verify.py`. Remove `GTM_VERIFY_BACKEND` (there is
no backend choice left).

## R13 · `04_hooks.md` §4.6 (`effective_ai_caps`, forged state)
(a) The effective cap is the verified, consumed record whose `consume` line comes **last in
`S/approval_nonces.jsonl`**, per `(company, account_id)`, never the latest by `signed_at`
(`signed_at` is unsigned). Add B2 test: rewriting `signed_at` on an older consumed higher-cap record
does not change the effective cap.
(b) `verify_signature` reason `key_not_installed` is "not verifiable, not forged": fall back to
`company.json` caps, with no `forged` state and no trust notice. Add a B2 test.
(c) A record signed by a retired key (05 §5.6 rotation) that verifies is not `forged`.
(d) `trust_root_ok` now returns `(bool, list[dict])`. Use the cached `approval_sig.trust_result(R)`
so one `decide` spawns git at most once.
(e) Extend the B2 F-trust falsification list: an uncommitted `tools/gtm/project_dirs.py` edit that
makes `matches_project_dir_prefix` return False puts the company in budget state.

## R14 · `04_hooks.md` (gate-gtm and any hook importing `approval_sig`/`ai_budget`) · `07_notices_schedules.md` §7.2 (`run_gtm_job.sh` unsigned-caps check)
Launch these Python processes as `python3 -I -S -B -X pycache_prefix=$HOME/.claude/.gtm_state/pycache`
(or have the entry file re-exec itself under those flags before any non-stdlib import). Append
`R/tools/gtm` to `sys.path`, never prepend. Import `approval_sig` and call `trust_root_ok` before
importing `company`, `system_names`, `ai_budget` or any other `tools/gtm` module.

## R15 · `04_hooks.md` §4.2/§4.3 (G-B, G-W)
(a) Extend G-W and G-B rule c to deny writes to the whole live-tree `R/tools/gtm/` subtree (except
`tests/`, `connectors/*/tests/`, `contracts/` and top-level `*.md`) and to `R/telemetry/pricing.json`.
Worktree and lane copies stay writable. At minimum `tools/gtm/approval_sig.py` and
`tools/gtm/ed25519_verify.py` must be denied: they run before and as the trust check, so they cannot
be detect-after.
(b) New G-B rule: deny a Bash command that invokes `tools/gtm/act.py`, `approval_sig.py` or
`approvals_verify.py` when it carries any `PYTHON[A-Z_]*=` assignment, `env` with such an
assignment, or `export PYTHON…`. Also deny writes (redirect, `cp`, `mv`, `tee`, `pip install
--user`, `pip install --target`) to any `site-packages` directory, any `*.pth` file, and any
`sitecustomize.py`/`usercustomize.py`.
(c) Deny `git update-index --skip-worktree|--assume-unchanged` on a TRUST_PATH. This is defence in
depth only; 05 §5.5 step 2 no longer reads the index.

## R16 · `02_act.md` §2.4 (`purge-untrusted`) · `07_notices_schedules.md` §7.1
(a) For `regulated ∋ hipaa` packs, `purge-untrusted` redacts `display`/`display_b64` of terminal
approval requests older than N days (replaced by `{"redacted": true}`), keeping `payload_b64`,
`status` and the approval record.
(b) `money_card`/`runaway_spend` notices for such packs carry only company display name, system and
amount in `title`/`body`/push text.

## R17 · `02_act.md` §2.4 (`record-external --kind approval`), §2.6 decision grammar
A card whose id is an approval `request_id` (subject token `approval <request_id>`) is a mirrored
`$` card. `deny` → set the request `denied`, the action `denied`, and publish a create-exclusive
denial record (`decided_via: "card"`). `approve` → never approves: write
`S/approver_inbox/show.<request_id>` and an `info` notice "Approval needs Touch ID in GTMApprover".
`unclear` → no change. Add A2 tests for all three.

## R18 · `03_schemas.md` §3.7 null rule and §3.4.3 · `02_act.md` §2.8 check 8/10
Add the third null case: an action that is class `money` only because `spend_delta_monthly ≠ 0` on a
`money: false` row has `new_absolute_value`/`unit` null and is signed over `after_digest`. Its
display shows `spend_delta_monthly`. Add an A2 test that such an action reaches a decision (verify
passes with a valid signature), not `awaiting_approval` forever.

## R19 · `07_notices_schedules.md` §7.1
`approval_sig.write_trust_notice` writes the §7.1 notice record directly (stdlib only, no import of
`notices.py`, which is gtmlib-adjacent code that may not load before the trust check). §7.1 should
name it as a second sanctioned writer of `kind: trust` records, with the same schema, id scheme and
dedupe semantics.

## R20 · `07_notices_schedules.md` (WP-K daily prompt) · `08_seats_wps.md` Appendix B item 81, WP-A2 row
The canonical CLI is `python3 <R>/tools/gtm/approval_sig.py --trust-check | --self-test`.
`gtmlib/approvals_verify.py`'s `__main__` re-execs it, so the old path still works, but prompts
should name the canonical one. Item 81: `trust_check` lives in `approval_sig` (re-exported by
`approvals_verify`), returns a dict, and the CLI exits 0/11/1. It writes `PAUSE.trust` only after a
settle re-check; dispatch never writes it.

## R21 · `03_schemas.md` §3.6 and §3.9
(a) Name the write-ticket TTL constant `WRITE_TICKET_TTL`, which 05 §5.5 step 5 uses for the mint
margin (refusal `approval_expiring`, exit 7).
(b) §3.9: add refusal `nonce_reserved` (exit 7) for a reserve while another holder holds the nonce.
State that at `complete` the expiry test is replaced by "reserved by `ticket:<id>` with reserve `ts <
expires`". Name the stages `authorize|mint|execute|complete|run_holds|revert` and give the holder per
stage, as in 05's table.
(c) §3.7 `expires` bullet: the effective-cap ordering is by `consume` line order (R13), not
`signed_at`. `create_request` supersedes older pending `gtm_ai` requests for the same
`(company, account_id)`.

## R22 · `00_global_paths.md` §1.2 (`S` layout)
Add `S/lead_spool/` (act.py, trust-failure lead spool, R11), `S/pycache/` (hook bytecode prefix,
R14), `S/approver_pubkey.pem` (the app's default export), `S/approver_fingerprint.json`,
`S/approver_selftest.json` and `S/approver_inbox/`, if not already listed. Add
`R/tools/gtm/approver_fingerprint.txt` and `R/tools/gtm/approver_pubkeys/` (tracked) to the tree
listing.

## R23 · `06_connectors.md` §6.2 and §6.4
Key the enable before re-check on the 05 §5.5 step-3b enable binding set: `commits_on_enable` rows
**and** any money-class action with verb `enable`/`resume`/`unpause`, `_nomatch` included. A
connector with no `committed_ceiling` read op cannot execute such an action; it is browser-only,
with the mandatory ceiling before-check. This replaces keying only on `action == "enable"`.

## R24 · `08_seats_wps.md` Appendix B (DECIDED HERE index) and the plan §17 probe list
Add entries:
- "05 §5.5 — TRUST_PATHS = all of `tools/gtm/` (named exclusions) + `telemetry/pricing.json`. Checked
  by blob-sha walk with scrubbed `/usr/bin/git`, not the index. Every entry point runs isolated
  (`-I -S -B`, `pycache_prefix`) and checks before importing. No `cryptography`."
- "05 §5.6 — `PAUSE.trust` only from the daily check after a 300 s settle re-check. Dispatch refuses
  and notifies. The fingerprint anchor is `tools/gtm/approver_fingerprint.txt` (a stated deviation
  from 'install card'). Rotation uses `approver_pubkeys/` with consume-time validity."
- "05 §5.1 — the app binds display to the signature (`display_sha256`) and publishes decisions
  create-exclusive; card answers only deny."
- "05 §5.8 — probe-p-failed mode: no pem, the owner executes, closed only by `owner_executed`."
Plan §17: add the manual check "one Approve = exactly one prompt showing the amount; reuse duration
0".

---

# Revision 3 (2026-09-27): alignment with the other files' current text

Status of earlier requests, as read from the other files today: R1, R2, R5, R10 (display fields and
`display_sha256`) and R18 landed in 03. R3, R9 and R11 (c)–(e) landed in 02 (`requests/02_act.md`
item 47); R11 (a), (b), (f) are still open against 02. R12 (00), R14 and R15 (04) are still open.
**Withdrawn:** R13 (a) (04_hooks.md §4.6 orders effective caps by signed payload fields, and §5.5 step 5
now follows 04), R21 (a) (§5.5 step 5 now uses 03 §3.6's 60-minute mint margin and exit 3
`approval_expiring`; no `WRITE_TICKET_TTL` constant is needed) and R21 (b)'s refusal name
`nonce_reserved` (renamed `nonce_held`, below).

## R25 · FID-03 · `02_act.md` §2.6 rule 5a · `06_connectors.md` §6.2 "Enable-bound actions", §6.1 `read_ops` row, §6.4
Narrow the enable scope to the one 03_schemas.md §3.2 "Enable actions" and 05 §5.5 step 3b now use:
(i) rows with `commits_on_enable: true`, and (ii) **`_nomatch`** actions whose verb is `enable`,
`resume` or `unpause`. Replace "or whose `action` is `enable`, `resume` or `unpause` (`_nomatch`
included, 05 R9)" (02 rule 5a) and "(ii) its `action` verb is `enable`, `resume` or `unpause`,
`_nomatch` included" (06 §6.2) with that wording. This supersedes R9's and R23's wider scope, and
settles the consequence 06 §6.2 flags: `google_ads.auto_apply_enable` (`amount_required: false`) and
`paid_api.usage_enable` (`current_value: zero`) are not enable actions. A1 test: both authorize
with no ceiling read and no `enable_amount_required`.

## R26 · `03_schemas.md` §3.9 (nonce ledger)
Name the refusal for a `reserve` while another holder holds the nonce: `nonce_held` (exit 7), as
05 §5.5 step 5 does. Keep `nonce_reserved` only as the ticket field (§3.6) and the `ticketed` event
field (02_act.md §2.2b).

## R27 · `04_hooks.md` §4.3 G-W "Trust roots" item 1, and §4.9 (the `gtm_task_gate` import list, "`approval_sig`/`cryptography`")
(a) Replace "verification uses the `cryptography` package directly inside the hook" with 05 §5.5
    step 4's backends: ECDSA P-256 via `/usr/bin/openssl dgst -sha256 -verify` (scrubbed env, no
    `OPENSSL_*`); Ed25519 via `ed25519_verify.py` loaded from
    `/usr/bin/git -C <T> show HEAD:tools/gtm/ed25519_verify.py` into a fresh module (never the
    working-tree file). Reasons: `cryptography` is user-installable and a stub can fake success
    (the R12 reason), and under R14's `-S` flag it does not import at all, so every trust edit
    would be denied. B1 test: a stub `cryptography` package returning success on `sys.path` leaves
    a forged marker refused.
(b) Read `approver_pubkey.pem` from `T` = `gtm_env.real_root()` outside test mode (00 §1.1
    consequence 1), not from `R`.
(c) The marker's producer is 05 §5.3 `--sign-trust-edit <absolute path>`, run by
    `scripts/gtm_approve.sh trust-edit <absolute path>` (05 §5.4). The payload is exactly the
    five keys 04 §4.3 names. Point the "`requests/05_approver.md`" citation at 05 §5.3/§5.4.
(d) §4.6: `effective_ai_caps`/`budget_state` call `approval_sig.trust_root_ok(R,
    require_key=False)` (or the cached `trust_result`), so a not-yet-installed key falls back to
    `company.json` caps instead of marking every bucket forged. R13 (b)/(c) are decided in 05
    §5.5 (after the API block) and §5.6: `key_not_installed` → `company.json` caps, no `forged`
    state, no trust notice; a retired-key record that verifies under the §5.6 rule is not forged.
    §4.6's "not decided here" sentence can cite those.

## R28 · `04_hooks.md` §4.2/§4.3 (R15 amendment)
Add `R/tools/gtm/gtm_env.py` to R15 (a)'s minimum must-deny set, beside `approval_sig.py`.
`approval_sig` imports it before the trust check (05 §5.5 step 0), so the check cannot detect an
edit to it. `ed25519_verify.py` leaves the minimum set: it is imported only after the check, which
covers it. It stays covered by the whole-subtree denial R15 (a) asks for.

## R29 · `00_global_paths.md` §1.1 ("Real root and test mode") and §1.2 (`S` layout)
(a) §1.1: state that `gtm_env` imports only the stdlib (never another `tools/gtm` module), because
    `approval_sig` imports it before the trust check (05 §5.5 step 0). Name
    `approval_sig.trust_root(R)` as the one function that returns `T` and raises the
    `root_mismatch` refusal (exit 3), so act.py, gate-gtm and G-W share it.
(b) §1.2 row `trust_edit_allow.json`: writer = "GTMApprover `--sign-trust-edit` (via the operator's
    `gtm_approve.sh trust-edit`)", section = "05_approver.md §5.3/§5.4; 04_hooks.md §4.3", not
    "operator (terminal only)".

## R30 · `07_notices_schedules.md` §7.2 citation of "R24 to 05_approver.md"
No change needed in 05's requests file: 05 §5.1 step 3 now renders a `gtm_ai` request whose value
is `0.00` as `NO CAP — report only, unlimited AI spend` (reason string included) and carries the
WP-C test. 07 can cite "05_approver.md §5.1 step 3" instead of the request number.

---

# Revision 4 (2026-09-27): requests from the second §5 review round

**Status corrections to revision 3.** R21 (a)'s withdrawal is itself withdrawn: §5 now uses 03 §3.6's
threshold (`WRITE_TICKET_TTL` + 5 min, exit 7 `approval_expiring`), not a 60-minute margin with exit
3 — see R47. R14's `S/pycache/` hook prefix is withdrawn (R41). R29 (a)'s single `trust_root(R)`
function stands.

## R31 · `00_global_paths.md` §1.1 (`gtm_env`) and §1.2 (tree and `S` layout)
(a) `gtm_env` gains two constants/functions (it stays stdlib-only and in the pre-check set):
`TRUSTED_PYTHON = "/opt/homebrew/opt/python@3.13/bin/python3.13"` and `approver_app_path() -> Path`
(`~/Applications/GTMApprover.app` outside test mode, `R/test_fixtures/GTMApprover.app` in test mode)
(05 §5.3, §5.5 step 0).
(b) Tree listing: add `R/tools/gtm/approver/` (Swift source, `build.sh`, entitlements, Info.plist),
`R/tools/gtm/approver_cdhash.txt` (`cdhash:<40 hex>\n`) and `R/tools/gtm/approver_probe_p.json`
(machine-readable probe-p record, 05 §5.3), all tracked TRUST_PATHS.
(c) `S` layout: add `S/trust_tree_seen.json` (writer `approval_sig.trust_check`, 05 §5.6 step 3).
Remove `S/pycache/` if R22 added it (no persistent bytecode prefix exists, 05 §5.5 step 0).

## R32 · `08_seats_wps.md` Appendix B (DECIDED HERE index) and the WP-C/WP-A2 rows
Add entries:
- "05 §5.6 install step (0) — no pem is committed (so no `$` can execute) until 04's G-W/G-B denials
  for `tools/gtm/approval_sig.py` and `tools/gtm/gtm_env.py` (R15 (a)/R28) have landed and a P2
  test shows an agent Write, Edit and Bash write to each is denied."
- "05 §5.3 — approver source in `tools/gtm/approver/` (TRUST_PATH); `build.sh` builds only from
  `git archive HEAD`; the installed cdhash is anchored in `tools/gtm/approver_cdhash.txt` and checked
  at every money verify stage and daily (`approver_vs_anchor`)."
- "05 §5.5 step 5 — release a nonce only on a proven no-write failure or an idempotent absolute set;
  otherwise quarantine (the operator re-approves)."
- "05 §5.1 step 5 — a card deny after an app approval revokes it until consumption."
- "05 §5.5 step 0 — trust code runs only in isolated entry points on `TRUSTED_PYTHON` with a fresh
  empty `pycache_prefix`; gate-gtm reads it from a subprocess."
WP-C row: add `tools/gtm/approver/` (source + `build.sh`). Amend the R24 entry that says the
fingerprint anchor is set by the operator's commit: the operator answers the install card; an agent
lands the anchors under trust-architect review (05 §5.6 install step 4).

## R33 · `04_hooks.md` §4.2 (G-B) — trust-code commits from GTM scope
New G-B rule: in GTM scope (`CLAUDE_GTM_COMPANY` set or `agent_type ∈ GTM_SEATS`), deny `git
commit`, `git apply`, `git am`, `git merge`, `git cherry-pick`, `git revert` and `git
update-index` whose pathspec, patch or index change touches a TRUST_PATH (the live `R/tools/gtm/`
subtree minus 05 §5.5 step 2's exclusions, and `R/telemetry/pricing.json`). Reason: HEAD is the trust
root, and local commits need no permission (05 §5.6 "What the HEAD trust root does and does not
guarantee"). B1 test: `git -C ~/.claude commit -F m -- tools/gtm/tier_table.json` from a GTM seat is
denied; the same from a non-GTM session is allowed (not judged by this rule).

## R34 · `03_schemas.md` §3.9 · `02_act.md` §2.4 (`ticket`, `complete`, `execute`, `run-holds` rows)
(a) 03 §3.9: rename the competing-reserve refusal from `nonce_reserved` to `nonce_held` (R26,
still open). Keep `nonce_reserved` only as the ticket field.
(b) 02 §2.4: `reserve`/`consume`/`release` take the **full** holder string — call
`approvals_verify.reserve(ctx, action, holder="ticket:" + ticket_id)` (not `holder=<ticket_id>`),
likewise `consume` in `complete`, and `"execute:<action_id>"` / `"run-holds:<action_id>"`. The
functions never add a prefix (05 §5.5 API).

## R35 · `03_schemas.md` §3.11 (`CANCEL_WHO`) · `02_act.md` §2.11 (`record-external --kind approval` on a mirrored `$` card)
(a) 03: add `card_deny` to `CANCEL_WHO` (written by act.py when a card deny revokes an approval whose
nonce is reserved, 05 §5.1 step 5).
(b) 02 §2.11: replace "`EEXIST` = an earlier decision stands, nothing appended" for the deny branch
with 05 §5.1 step 5's four cases: no record → denial record; denial exists → no change; approval
exists and nonce unreserved/released → revoke (request `denied`, action `denied`, event
`approval_revoked {request_id, decided_via: "card"}`); nonce reserved → revoke plus cancel marker
`who: "card_deny"`; nonce consumed → event `card_deny_after_consume` + urgent notice, no state
change. Every branch (approve and unclear included) requires subject `approval <request_id>`, else
`card_subject_mismatch` with no change. Add `approval_revoked` and `card_deny_after_consume` to
02 §2.2b's event list. A2 tests as listed in 05 §5.1 step 5.

## R36 · `04_hooks.md` §4.2 (G-B) — approver rebuilds
Deny, for every agent session, a Bash command that runs `tools/gtm/approver/build.sh`, or `swiftc`,
`codesign` or `ditto`/`cp`/`mv`/`rsync` with a destination or operand under
`~/Applications/GTMApprover.app` or naming `GTMApprover`. A rebuild is an operator act in his own
terminal (05 §5.3 "Binary integrity"). B1 test per verb.

## R37 · `00_global_paths.md` §1.1 — see R31 (a) (`gtm_env.approver_app_path()`)
Listed separately because 05 §5.3 cites it by this number.

## R38 · `04_hooks.md` §4.3 G-W "Trust roots" item 1 (extends R27)
Replace in-hook verification entirely: G-W runs
`gtm_env.TRUSTED_PYTHON -I -S -B -X pycache_prefix=<fresh P> <T>/tools/gtm/approval_sig.py
--verify-trust-edit <canon target>` (5 s timeout) and proceeds to its item 4 (nonce consumption)
only on exit 0; any other exit, timeout or unparsable output denies. This makes 05 §5.5 step 4 the
single backend definition for the approver key and removes the `cryptography` dependency, the `R`
(not `T`) read and the unscrubbed `git show`. Note in 04: the helper runs steps 0–2 first, so a marker
admits an edit only on a clean tree (one admitted edit, then its commit). B1 test: a stub
`cryptography` returning success on `sys.path` leaves a forged marker denied.

## R39 · `02_act.md` §2.3 · `04_hooks.md` §4.6 — `require_key`
`approval_sig.trust_root_ok`'s `require_key` argument is now accepted and ignored (05 §5.5 API):
`key_not_installed` is decided only by `verify_signature` at key lookup. Drop the argument from the
call sites (`trust_root_ok(R)`), and cite `key_not_installed` as a `verify_signature` reason, not a
trust-check result.

## R40 · `02_act.md` §2.3 (dispatch trust failure) and §2.9
`trust_git_error` at dispatch: exit 11, **no** `write_trust_notice`, no `PAUSE.trust`; call
`approval_sig.write_trust_git_notice(S, created_by="act", now=…)` (warn, `push: false`, dedupe
`trust_git:<UTC YYYY-MM-DD>`, 05 §5.5 "Error mapping"). Every other TRUST_KINDS failure keeps the
urgent `write_trust_notice`. `error.code` = the first kind present in `TRUST_KINDS` order. A2 test:
act.py against a fixture `T` that is not a git repository exits 11 with a `trust_git:` warn notice
and no urgent trust notice.

## R41 · `04_hooks.md` §4.6 (gate-gtm, `ai_budget`) · supersedes R14's hook form
(a) gate-gtm never imports `approval_sig` or `ai_budget` in the hook process (`pretooluse_task.py`
runs non-isolated under `settings.json`). It runs `gtm_env.TRUSTED_PYTHON -I -S -B -X
pycache_prefix=<fresh P> <T>/tools/gtm/ai_budget.py <subcommand> --company <slug> --json`
and reads per-bucket `forged`/caps from its stdout. Please name the subcommand and its JSON in §4.6;
05 cites it only as "04's". Any nonzero exit, timeout or unparsable output = `forged`.
(b) Withdraw R14's `pycache_prefix=$HOME/.claude/.gtm_state/pycache`: every prefix is a fresh
0700 `gtm_pyc_<hex>` directory created directly under `gtm_env.gtm_tmp_root()`, removed at exit (05 §5.5 step 0; wording aligned wave1e).
(c) Re-measure the §4.6 gate-gtm p95 (300 ms on 20,000 `spend.jsonl` lines) with the subprocess on
the path and no bytecode cache; record the figure in §4.6. If it exceeds the budget, raise it in 04,
not by weakening 05's isolation.
(d) B2 test: gate-gtm invoked through the real `settings.json` dispatcher command line on a clean
committed fixture tree is not forged; with an untracked `tools/gtm/json.py` it is forged.

## R42 · `00_global_paths.md` §1.5 "Import rule"
Record that an isolated entry point **appends** `os.path.dirname(os.path.abspath(__file__))` (no
symlink resolution) to `sys.path`, never `R/tools/gtm`, and that `trust_root_ok` reports
`trust_root_mismatch` when that directory is not `T/tools/gtm`. The committed import-time
`sys.path.insert(0, …)` in `company.py`, `activity_log.py`, `harvest_tool_trail.py` and
`backup_state.py` should be retrofitted to append (only when absent); until then 05 §5.5 step 0
relies on the static "no stdlib module name" test.

## R43 · `07_notices_schedules.md` §7.2 "Interpreter pin" / §7.3 · `04_hooks.md` §4.2 (G-B)
(a) 07: `__PY_DIR__` = `dirname(gtm_env.TRUSTED_PYTHON)`, not `shutil.which("python3")` of the
operator's shell (that is the CSA `.venv` symlink in CSA sessions).
(b) 04: deny agent writes (rule c write and removal classes) under `/opt/homebrew/opt/python@3.13/`
and `/opt/homebrew/Cellar/python@3.13/`, and agent `brew` commands whose operands include
`python@3.13` (install/uninstall/upgrade/reinstall/link/unlink).

## R44 · `03_schemas.md` §3.7 (`display` sources table)
Change the source of `new_absolute_value`, `unit` from "the payload values" to
`action.after.new_absolute_value` / `action.after.unit`. `build_display(ctx, action)` never reads a
payload, so 05 §5.5 step 3b's `display_sha256` recomputation is independent. Also add to §3.7's
3b description: `payload.unit == action.after.unit`, and for enable actions `payload.unit ==
action.before.value.unit`.

## R45 · `03_schemas.md` §3.7 `expires` bullet (supersedes R21 (c))
Replace "the effective cap for a `(company, account_id)` is the one whose `consume` line comes
**last** in §3.9's ledger" with: "among verified, consumed records, the latest by the payload's
signed `expires`, then `card_id` (05_approver.md §5.5 step 5; 04_hooks.md §4.6)".

## R46 · `06_connectors.md` §6.2 (connector result)
Add `side_effect: "none" | "unknown"` to a failed (`ok: false`) connector result. `"none"` only when
the failure was raised before the first mutating HTTP call, or on a platform response the
connector's own spec documents as "nothing applied"; everything else (timeouts, 5xx, transport
errors) is `"unknown"`. act.py releases a nonce only on `"none"` (05 §5.5 step 5 "Release or
quarantine"). L test per connector: a timeout after the mutating call → `"unknown"`.

## R47 · `03_schemas.md` §3.6 (write-ticket mint) and §3.7
Name the threshold `MINT_MARGIN = WRITE_TICKET_TTL + 5 min` and cite it instead of the raw
"`WRITE_TICKET_TTL` + 5 min" text, and say the refusal is raised as
`ActError(EXIT_APPROVAL, "approval_expiring")` by `approvals_verify.verify(stage="mint")`. The
value, exit code (7) and 03's existing test thresholds (+4 min refused, +6 min mints) are unchanged;
05 §5.5 step 5 now states the same.

## R48 · `07_notices_schedules.md` §7.5 daily D-list (probe-p-failed closing trigger)
Add a step after D6, "D6b owner-executed changes": only while HEAD has no
`tools/gtm/approver_pubkey.pem` and `tools/gtm/approver_probe_p.json` says `"probe_p": "fail"`:
`act.py queue --company <slug> --kind approval` → for those actions' systems one `act.py ticket
--read` + one gtm-analyst verify-read → for each action whose verification shows the requested value,
`act.py record-external --company <slug> --kind owner_executed --card <request_id> --action <id>
--verify-from-agent <analyst id>`. No operator reply is involved (05 §5.8 no longer asks for
`done <request_id>`).

## R49 · plan §17 (probe list) · `08_seats_wps.md` WP-C
Add to probe p: "record `se_key` pass/fail as `SecKeyCreateRandomKey`'s actual status; a copy of the
app rebuilt with a new cdhash tries one signature: refused / OS consent prompt / signs after Touch
ID". Land the result as `tools/gtm/approver_probe_p.json` (05 §5.3). Add the manual check "a rebuilt
app cannot sign unnoticed: `trust_check` reports `approver_vs_anchor`" (05 §5.7 check (2)).

## R50 · `02_act.md` §2.4 (`execute`, `run-holds`, `complete --failed`, `ticket --close`) · `03_schemas.md` §3.6 (reconcile)
Replace every unconditional "release on failure" / "nonce released" with 05 §5.5 step 5's "release
or quarantine": release only on a proven no-write failure (connector `side_effect: "none"`; ticket
`mutating_calls_used == 0`) or when the payload has a non-null `new_absolute_value` and the row's
`current_value` is not `zero`; otherwise `approvals_verify.quarantine(ctx, action, holder,
reason=…)` (a `consume` line + `nonce_quarantined`), action `failed`, urgent notice. Add
`nonce_quarantined` to 02 §2.2b's events and 03 §3.9's description. A2 tests as in 05 §5.5 step 5.
Also in 02: `verify` at every stage but `complete` refuses a request whose `status` is `denied`,
`superseded` or `expired` (reasons `request_denied`/`request_superseded`/`request_expired`, exit
7), and money `verify` at `mint`/`execute`/`run_holds`/`revert` can raise
`ActError(EXIT_TRUST, "approver_vs_anchor")` (05 §5.3).

---

# Revision 5 (2026-09-27): open-findings pass (FID-03, IMP-05, FID-07)

FID-03, IMP-05 and FID-07 are resolved in §5 against the current 02/03/04/06 text. The earlier
requests they depend on (R1–R7, R9, R25) have landed in their target files; §5 now cites
03_schemas.md §3.7 for `display.commits_on_enable` and adopts 03 §3.2's budget-object test
(`enable_no_budget_object`) for the enable-binding scope. One request was cited in §5 but never
written:

## R51 · `04_hooks.md` §4.2 (G-B rule g)
§5's header says agents cannot run `scripts/gtm_approve.sh` at all. Rule g today denies only
`gtm_cancel.sh`, and rule k does not match `gtm_approve.sh trust-edit` / `operator-ok` (hyphenated,
not the `trust_edit_allow` / `operator_ok` literals). Extend rule g: running `gtm_approve.sh` in any
mode (re-show, `trust-edit`, `operator-ok`) → deny, code `agent-approver-script`. Reason: act.py
writes `S/approver_inbox/show.<request_id>` itself (05 §5.1 step 5), so agents never need the
script, and an agent-triggered Touch ID prompt for a trust-edit or operator marker is exactly the
reflexive-consent path §5.3/§5.4 exist to keep in the operator's own terminal. B2 falsification
tests: `bash ~/.claude/scripts/gtm_approve.sh trust-edit /x` and `gtm_approve.sh apr_x_1_ab` are
each denied with `agent-approver-script`, and each goes RED when the clause is removed.

---

# Revision 6 (2026-09-27): review-findings pass

§5 was revised against a 33-item review (2 blockers). The requests below are the cross-file halves.
Each names the §5 text it depends on; nothing here is decided in the target file until it lands.

## R52 · `00_global_paths.md` §1.4 "Operator authority" and "Shared literals" (blocker: revert under a stop)
Add `"revert"` to `system_names.OPERATOR_OK_COMMANDS` → `("resume", "autonomy", "pause", "revert")`.
For `command == "revert"`, `<target>` is the revert child's `action_id` (`act_<slug>_…`, already
inside 05 §5.3's `<target>` grammar), and the marker file is
`S/operator_ok/revert.<slug>.<child action_id>.json`. Validation is 00 §1.4 (1)–(5) unchanged, with
holder `operator-ok:revert:<child action_id>`. `tools/gtm/operator_ok.sh revert <slug> <child>`
execs `gtm_approve.sh operator-ok revert <slug> <child>`. The GTMApprover app's compiled-in copy of
`OPERATOR_OK_COMMANDS` follows (05 §5.3; its C test asserting equality with
`system_names.OPERATOR_OK_COMMANDS` fails until it does), and the coordinator's
`test_contract_literals.py` literal row changes in the same commit. Reason: plan §20.8 "`revert
--approval <card id>` (§6.8) means 'a signed approval for that revert action'" has no money
qualifier; archive text must never unlock the one mutation allowed under a stop (05 §5.5 step 5
"Revert under `DISABLED`/`PAUSE`").

## R53 · `02_act.md` §2.4 `revert` row (step 1 and step 2) and §2.4 id-first registration
Step 2, **non-money child while `R/schedules/DISABLED` exists or a manual `PAUSE`/`PAUSE.<system>[@<brand>]`
covers the child**: replace `cards.require_approved(ctx, card_id, "revert <child action_id>")` with
the signed operator marker of R52 (found by the child id; `--approval` must equal the child id,
else exit 3 `revert_approval_mismatch`; no marker → exit 3 `operator_ok_required`; invalid marker
left in place; no HEAD pem → exit 11 `approver_not_installed`); checks 1 and 5 re-run as on the card
path. Outside a stop the card path is unchanged. Step 1's `awaiting_card` notice for a non-money
child under a stop names the command `tools/gtm/operator_ok.sh revert <slug> <child action_id>`
instead of a card. The `revert` id-first row (02 §2.4 table, "`--approval` only when it is an `apr_`
id") also accepts an `act_` id in this form. A2 tests as in 05 §5.5 step 5 "Revert": a forged
archive answer `revert <child>` under `PAUSE` leaves the child at `awaiting_card` (exit 3
`operator_ok_required`); a valid marker executes; a marker for another child is refused and left
in place.

## R54 · `02_act.md` §2.3 (step-0 failure) · `04_hooks.md` §4.6 · `07_notices_schedules.md` inbox prompt and §7.1
(a) 02 §2.3: under a step-0 trust failure, `ticket --read --company <slug>` (slug grammar-checked
only) writes, via `approval_sig.write_urgent_notice(S, <slug>, "task", "GTM inbox check could not
run — check <company>'s inboxes by hand today", <body>, "lead_capture_stopped:<slug>:<UTC date>")`,
one urgent pushed task notice, then exits 11 as today (it is **not** a fifth fallback: no ticket is
minted). State in 02 §2.3 that this is 05 §5.5 step 0's stated deviation from plan §20.8 (refusal
wider than `$`) and that lead capture stops for every company while the tree differs from HEAD.
(b) 04 §4.6: replace "only the lead-capture analyst allowance runs" with "the lead-capture analyst
allowance is still admitted, but with no read ticket (`ticket --read` exits 11) it reads nothing".
(c) 07 inbox prompt (`schedules/prompts/gtm_inbox.txt`): the first trusted inbox run after
`lead_capture_stopped` notices exist writes, on each affected home's operator task surface, the
same-day task "GTM lead capture was stopped from <first notice ts> to <now>; check <inboxes> for that
window" and resolves those notices (`notices.py resolve`). (d) 07 §7.1: add
`approval_sig.write_urgent_notice` as a stdlib writer beside `write_trust_notice` (same id scheme,
locks and dedupe). A2/B2 test as in 05 §5.5 step 0.

## R55 · `02_act.md` §2.11 (`owner_executed`) · `03_schemas.md` gtm-result `verifications[].observed` · `07_notices_schedules.md` §7.5 D6b (amends R48)
(a) 02 §2.11 `owner_executed`: for an action with `display.commits_on_enable: true` the verify-read
must show `observed.status == "enabled"` **and** `observed.new_absolute_value`/`unit` equal to the
signed value; for a pause/stop action (amount 0, plan §20.13) it must show `observed.status ==
"paused"` (`"removed"` for a remove-verb stop row), budget ignored; otherwise exit 3
`owner_observation_mismatch`. (b) 03: `verifications[].observed` gains `status` (string; required
for those two classes). (c) 07 §7.5 D6b runs only while HEAD's `tools/gtm/approver_probe_p.json`
says `"probe_p": "fail"`, never merely because HEAD has no pem. A2 tests as in 05 §5.8.

## R56 · `03_schemas.md` §3.2 "Enable actions"
Narrow the `enable_no_budget_object` refusal to `_nomatch` enables whose most specific
`target_ids` key is a known within-ceiling child (`ad_group_id`, `ad_id`, `keyword`, `asset_id`,
`post_id`, `media_id`). Every other non-budget `_nomatch` enable (empty `target_ids`, or an
unrecognized key such as a lead-marketplace `category_id` or a paid add-on) goes to the ordinary
amount-bearing `_nomatch` `$` path, or null rule case (i) with no amount (plan §20.6: no tier-table
match → `$` item; a proposal is never silently refused). A1 test: a `_nomatch` `enable` on an `L`
system with only `category_id` reaches `awaiting_approval`.

## R57 · `04_hooks.md` §4.2 G-B rule g (extends R51)
Deny, in every session, any command whose argv (after `bash_gate`'s tokenization, incl. `env`/`exec`
prefixes and `bash -c` text) names the GTMApprover **binary** or **bundle**: a path whose `canon`
ends in `GTMApprover.app/Contents/MacOS/GTMApprover` or is equal to or under a `GTMApprover.app`
directory, any token equal (casefolded) to `GTMApprover` or `GTMApprover.app`, and `open` with
`-a GTMApprover`, `-a <…>/GTMApprover.app`, `-b <bundle id>` or `--args` after such a target; code
`agent-approver-binary`. Reason: the signing, key-generation and rotation modes are reachable by
running the binary directly, bypassing R51's script denial; an agent-triggered Touch ID prompt is
the reflexive-consent hazard, and `--generate-key --rotate` could destroy the key. B2 tests (each
RED when the clause is removed): `~/Applications/GTMApprover.app/Contents/MacOS/GTMApprover
--sign-trust-edit /x`, `open -a GTMApprover --args --sign-operator-ok resume x autonomous`, and
`env X=1 ~/Applications/GTMApprover.app/Contents/MacOS/GTMApprover --generate-key --rotate` each
denied with `agent-approver-binary`; `ls ~/Applications` allowed.

## R58 · `04_hooks.md` §4.7 (`bash_gate.sh` fast path) — tokens for R36, R43, R57
Add fast-path tokens `*gtmapprover*`, `*codesign*`, `*swiftc*`, `*python@3.13*`,
`*homebrew/cellar/python*`, `*homebrew/opt/python*` (casefolded, as the existing tokens), so
`codesign --force --sign - ~/Applications/GTMApprover.app`, `brew upgrade python@3.13` and a direct
GTMApprover exec reach the G-B dispatcher; without them R36/R43/R57 can never fire. End-to-end B2
test through `bash_gate.sh` for each denied verb (RED when the token is removed). **Flag to 04's
reviewer:** the existing `*.jsonl*` token matches every PreToolUse payload's `transcript_path`,
which disables the fast path for every command; that hides this gap only by accident and is 04's
defect to fix.

## R59 · `07_notices_schedules.md` §7.2 "Interpreter pin" / §7.3 · `08_seats_wps.md` WP-K prompt and Appendix B (replaces R43's `__PY_DIR__` half)
`dirname(TRUSTED_PYTHON)` (`/opt/homebrew/opt/python@3.13/bin`) holds only `python3.13` (measured: no
`python3`), so setting `__PY_DIR__` to it does not make a bare `python3` resolve to the pin. Every
command 07 renders (plists, `run_gtm_job.sh`) and 08 documents (WP-K daily prompt, install steps)
for a GTM entry point (`act.py`, `approval_sig.py`, `approvals_verify.py`, `ai_budget.py`) names
`/opt/homebrew/opt/python@3.13/bin/python3.13` by full path. (05 §5.5 step 0 also makes every
entry-point file parse under `/usr/bin/python3` 3.9, so a stray bare `python3` re-execs instead of
failing with a `SyntaxError`.)

## R60 · `00_global_paths.md` §1.2 (`S` layout) and §1.4 (`operator_ok.sh`)
(a) `S/approver_inbox/show.<request_id>`: writers are `gtm_approve.sh` **and** act.py
(`record-external --kind approval`, 05 §5.1 step 5); `S/approver_inbox/` is created mode 0700 by
whichever writer comes first; markers 0600. (b) `S/approver_fingerprint.json` has one writer, the
app's `--export-pubkey` (`--generate-key` writes nothing in `S`). (c) `operator_ok.sh` passes the
app's exit code through, where exit 5 means `root_mismatch` and nothing else (05 header), and
documents the stderr tokens 05 §5.4 lists.

## R61 · `00_global_paths.md` §1.5 "Import rule" (extends R42)
Correct the description: `activity_log.py:53`, `harvest_tool_trail.py:45` and `backup_state.py:26`
run `sys.path.insert(0, str(Path(__file__).resolve().parent))` at import time; `company.py:894` does
it only lazily, inside the function that imports `activity_log`. All four insert the **resolved**
directory, which in §1.5's symlinked test trees is the real tree. Retrofit all four to **append**
`os.path.dirname(os.path.abspath(__file__))` (no `.resolve()`), matching 05 §5.5 step 0's code-root
rule, and when not already present. A1 test: in a symlinked tmp tree, importing each leaves no
entry under the real `tools/gtm` on `sys.path`.

## R62 · plan §17 probe p · `08_seats_wps.md` WP-C · `00_global_paths.md` §1.1 (`approver_probe_p.json`, R31) (amends R49)
Probe p also measures, in the exact ad-hoc configuration of 05 §5.3 (empty entitlements), a
CryptoKit Ed25519 key stored (1) as a data-protection keychain item with `kSecAttrAccessControl`
`.userPresence` (does `SecItemAdd` succeed; does a read without an evaluated context fail?) and (2)
as a legacy login-keychain item whose `SecAccess` trusted-application list is only the app (does
`SecItemAdd` succeed; does a different binary get an OS consent prompt?). It records
`"fallback_store": "dp_userpresence" | "legacy_acl" | "none"` in `tools/gtm/approver_probe_p.json`
whenever `se_key` is `fail` (else `null`). 05 §5.3 "Fallback key store" defines each branch;
`"none"` is probe-p-failed mode (§5.8). 00's listing of the file adds the key.

## R63 · `02_act.md` §2.4 (`execute`, `run-holds`, `revert`, `complete`, `record-external --kind approval`) and §2.2b events
(a) At a **success** `consume` (never a quarantine consume) act.py sets the request's `status` to
`approved` inside the nonce-ledger lock, in the same critical section (05 §5.5 3b; the `pending →
approved` transition 03 §3.7 allows). (b) `record-external --kind approval` deny branches (05 §5.1
step 5): both revoke branches write the revocation notice (kind `agent_cancel`, push, `urgent` for
an `urgency: urgent` request else `warn`, dedupe `approval_revoked:<request_id>`); a deny on a
**quarantined** nonce (ledger `consume` plus a `nonce_quarantined` event for the request) sets the
request `denied`, appends `card_deny_after_quarantine {request_id}` (add to §2.2b's event table)
and writes the "outcome is unknown — check <system> before reverting" urgent notice, never the
"use revert" one.

## R64 · `02_act.md` §2.3 (error codes) · `03_schemas.md` §3.9
Cite 05 §5.5's "Reason → exit code → `error.code`" table as the one list for approval/trust
reasons, including the names it fixes: `approval_missing`, `approval_expired`,
`nonce_not_reserved`, `reserved_after_expiry` (exit 7) and `approver_vs_anchor`,
`approver_not_installed` (exit 11).

## R65 · `07_notices_schedules.md` §7.1 (GTM_Operator.html) and the weekly report
List every open `agent_cancel` notice whose `dedupe_key` starts `approval_revoked:` in a
"Revoked approvals" block on `GTM_Operator.html` and in the weekly report (request id, amount or "no
amount", account, revoking card), so a forged card deny that revoked an operator-signed approval is
never silently lost (plan §20.7).

---

# Revision 7 (2026-09-28): review-findings pass (card revocation, trust fallback, export binding)

§5 was revised against a further review (2 blockers). The requests below are the cross-file halves.
Each names the §5 text it depends on; nothing here is decided in the target file until it lands.

## R66 · plan §20 · `02_act.md` §2.4/§2.11 · `03_schemas.md` §3.7 and §3.11 · `07_notices_schedules.md` §7.1 (supersedes R35 and R63 (b); amends R65)
05 §5.1 step 5 now reads: **a card "No" decides only an undecided request; it never revokes an
approval the operator signed.** (a) **Plan:** record this as a plan §20 amendment — plan §20.7's
"cancel from any channel" is scoped, for a Touch-ID-signed `$` request, to the operator's non-agent
channels (menu-bar Revoke, `gtm_cancel.sh`, a hand-made `S/cancels/<slug>/<action_id>`), because plan
§20.8 strikes the archive-answer path for money and §20.6 makes stopping spend an operator-only
decision. (b) **02 §2.11** `record-external --kind approval` deny branches: no record → denial
record (`decided_via: "card"`), request and action `denied`; denial exists → no change; **approval
exists and nonce not consumed → no state change**, event `card_deny_after_approval {request_id}`,
notice kind `agent_cancel`, push, `urgent` for an `urgency: urgent` request else `warn`, dedupe
`card_deny_after_approval:<request_id>`; nonce consumed by quarantine → request `denied`,
`card_deny_after_quarantine`; nonce consumed by success → `card_deny_after_consume`. R35 (b)'s
"revoke" and "revoke plus cancel marker `who: card_deny`" branches and R63 (b)'s revocation notice
are withdrawn. (c) **02 §2.4 / 03 §3.11 cancel ingest:** a marker with `who` ∈ {`operator_script`,
`approver_menu`, `hand_made_file`} for an action whose request has an approval record and an
unconsumed nonce sets the request `denied`, the action `cancelled`, and appends `approval_revoked
{request_id, who}`; `act.py cancel` (`who: "agent"`) of such an action refuses exit 3
`approval_stands`, nothing written. R35 (a)'s `card_deny` member of `CANCEL_WHO` is withdrawn (no
writer remains). Add `card_deny_after_approval` and `approval_revoked {request_id, who}` to 02
§2.2b's event table. (d) **07 §7.1:** R65's "Revoked approvals" block lists open `agent_cancel`
notices whose `dedupe_key` starts `card_deny_after_approval:` (a card said No to a signed request)
and `approval_revoked` events (operator revocations). (e) **[superseded wave1e by `display.resulting_status`, R76 (b)]** **03 §3.7:** add `display.change_kind`
(`"pause"` for a matched row or `_nomatch` verb `pause`/`stop`/`disable`, `"remove"` for
`remove`/`delete`, absent otherwise; set by A2 from the row verb, never from `money_brief`) — the app
selects the "Pause (stop spend)" / "Remove (stop spend)" reason strings from it (05 §5.1 step 3).
A2 test: a forged card "No" against a signed urgent stop (campaign pause, `"0.00"`) leaves it
executable.

## R67 · `02_act.md` §2.3 "Stdlib spool exceptions" · `06_connectors.md` §6.4 · `04_hooks.md` §4.6 (amends R54) · `08_seats_wps.md` coordinator landing · plan §20
(a) **02 §2.3:** add `ticket --read --company <slug> --systems a,b[,…] [--run <id>]` and `ticket
--close <read ticket id>` as stdlib fallbacks served by `act_fallback` under a step-0 failure,
exactly as 05 §5.5 step 0 "Read-ticket fallback" specifies (HEAD runbooks via the step-2
`/usr/bin/git` invocation, never the working tree; the 03 §3.6 read-ticket record plus
`"minted_by": "trust_fallback"`; refusal → exit 11 plus the `lead_capture_stopped` task notice).
Confirm that the ordinary read-ticket mint has no pack-dependent check beyond host validation; if
it has one, name it, and the fallback refuses that company instead. Use the same `session_id`
source as the ordinary mint. (b) **06 §6.4:** confirm that `system_names.runbook_stem(s) == s` for
every tier system with a runbook (so a runbook's `system` equals the name `--systems` passes), or
add a `tier_systems` list to each runbook that the fallback can match. (c) **04 §4.6:** R54's
wording changes to "the lead-capture analyst allowance is admitted and reads with the fallback read
ticket". (d) **Plan §20 amendment:** record that during any trust drift (a TRUST_PATH differing
from HEAD) `read-run`, `verify`, `snapshot`, non-money `authorize`/`execute` and non-money `revert`
are refused for every company, which is wider than plan §20.8's "`$` refused" and than plan §6.8's
guarantees under stops; inbox lead capture continues through the fallback. The operator-facing
note is the trust notice's last line (05 §5.6). (e) **08 (coordinator landing):** give the
TRUST_PATH landing step one command that refuses, with nothing applied, unless
`R/schedules/DISABLED` exists or `launchctl list` shows no `com.oversight.gtm.*` label loaded, and
that never removes `DISABLED` itself. B-test: with a `com.oversight.gtm.*` label loaded (fixture
`launchctl` stub) and no `DISABLED`, the landing command exits nonzero and changes no file.

## R68 · `03_schemas.md` §3.2 "Enable actions" and §3.4.4 (supersedes R56)
05 §5.5 step 3b "Enable binding" withdraws the `enable_no_budget_object` refusal: a `_nomatch`
enable/resume/unpause of an object with no budget of its own (a within-ceiling child or anything
else outside the budget-object set) takes the ordinary `_nomatch` `$` path (amount-less → null case
(i)). (a) 03 §3.2: drop `enable_no_budget_object` and state this routing. (b) 03 §3.4.4: add
explicit `money: false` rows for within-ceiling child `enable`/`resume` (and `pause`) per system —
at least `google_ads` ad group, ad, keyword and asset; `meta_ads` ad; organic post/media rows where
a pause/resume verb exists — so plan §20.13's "within-ceiling child pause/resume is autonomous"
applies through the table and these actions never reach `_nomatch`.

## R69 · `04_hooks.md` §4.6 (gate-gtm)
State that gate-gtm catches every exception of its own (subprocess spawn, JSON parse, timeout,
unexpected shape) and returns `forged`, because the T dispatcher's outer `except Exception: return
0` fails open. B2 test (05 §5.5 step 0): with the fixture `ai_budget.py` replaced by a script that
raises, gate-gtm's decision is `forged`, observed as the deny JSON on stdout and the tmp
`.enforcement/log.jsonl` row, under `CSA_ENFORCE=1` with a fixture `agents/<seat>.md` and
`knowledge/model_policy.json`.

## R70 · `00_global_paths.md` §1.1 / `company.claude_dir()` · R42 and R61 citations
(a) `company.claude_dir()` resolves only its `CLAUDE_DIR`-set branch; the unset branch returns
`Path.home() / ".claude"` unresolved. Either resolve both branches, or state that callers compare
it with `gtm_env.same_root`. 05's A2 equality test is restricted to the set branch until then.
(b) R42 and R61 cite `company.py:894`; the lazy `sys.path.insert` is inside
`company._pack_system_set` (today at company.py:915). Cite the function by name, not a line number.

## R71 · plan §6.8 · `02_act.md` §2.4 `revert` · `03_schemas.md` §3.10 (pause-scope table)
05 §5.5 step 5 "Revert under `DISABLED`/`PAUSE`" now splits `PAUSE.<system>[@<brand>]` by the §3.10
stop-row predicate: a breaker pause (`created_by: "breaker"`, null `ruling_ref` and `lift_card`)
lets a revert of that system's child through with a signed approval (money) or a signed `revert`
operator marker (non-money); every other `PAUSE.<system>[@<brand>]` (owner, ruled, hand-made)
blocks revert step 1 and step 2 with exit 5. (a) Plan: confirm reading (a) in §6.8, or strike it
so every `PAUSE.<system>` blocks revert. (b) 02 §2.4 `revert` row and 03 §3.10's `PAUSE.<system>`
row: state both halves. A2 test: an owner-ruled `PAUSE.website_remodeling` (`ruling_ref: "A0022"`)
blocks a signed revert with exit 5, marker left in place.

## R72 · `02_act.md` §2.4 `ticket --write`, `execute`, `complete` rows and §2.3 (extends R34)
(a) `ticket --write` mint inside `MINT_MARGIN` exits **7** `approval_expiring` (raised by
`approvals_verify.verify(stage="mint")` as `ActError(EXIT_APPROVAL, …)`), not exit 3; fix the row
and the §2.3 code lists that call it exit 3 (the "settled exit" is 7, matching 03 §3.6/§3.9 and 05
§5.5 step 5). (b) R34 (b) unchanged: `reserve`/`consume`/`release` take the full holder strings
`"ticket:" + ticket_id`, `"execute:" + action_id`, `"run-holds:" + action_id` — not bare ids.
(c) `complete`: the holder is `"ticket:" + action.ticket_id` (read from the action); refuse a
`--ticket` that differs from `action.ticket_id` before calling `verify`.

## R73 · `02_act.md` §2.3 (error codes) · `03_schemas.md` §3.9 (extends R64)
Add `pubkey_vs_export` (exit 11; 05 §5.5 step 3a "Export binding": at `mint`, `execute`,
`run_holds` and `revert` the HEAD current key's fingerprint must equal
`S/approver_fingerprint.json`'s, a missing export refusing too) and `request_missing` (exit 7; no
request file for the action's `request_id`) to the code list, citing 05's reason table.

## R74 · `08_seats_wps.md` Appendix B and WP-C · `00_global_paths.md` §1.1 (`approver_probe_p.json`, R31/R62)
Add install step (0b) (05 §5.6): `tools/gtm/approver_probe_p.json` is committed through the reviewed
landing path (trust-architect, HIGH tier) before the operator runs `--generate-key`; a missing or
malformed file when the fallback branch is needed exits 7 `fallback_store_unmeasured` with no key.

## R75 · `02_act.md` §2.3, §2.4 (`cancel`, `queue`, `record-external`), §2.5, §2.11 (revision 8)
05 §5.1 step 5 now adopts 02 §2.11's "a mirrored `$` card answer decides nothing" verbatim
(requests/02_act.md item 87 is done on 05's side). Please: (a) name the reshow notice exactly as 05
§5.1 step 5 specifies it (kind `info`, severity `info`, `push: false`, title `"Approve or deny
<request_id> in GTMApprover on the Mac (Touch ID)"`, `dedupe_key "approval_reshow:<request_id>"`,
`created_by: "act"`), so the two files carry one text; (b) cancel-marker ingest for a `$` action:
a marker whose `who` ∈ {`agent`, `card_deny`, `hand_made_file`, `system:responded_by`} **never**
cancels an action whose request has an approval record with an unconsumed nonce (recorded and
deleted, nothing else), `act.py cancel` of such an action refuses exit 3 `approval_stands` with
nothing written, and a `who` ∈ {`operator_script`, `approver_menu`} marker revokes it (request
`denied`, action `cancelled`, `approval_revoked {request_id, who}`, and the always-pushed
`approval_revoked:<request_id>` notice of 05 §5.1 step 5); (c) any cancel of an **unsigned** `$`
action also sets its request `status: "denied"` and appends `request_cancelled {request_id, who}`
plus the same pushed notice; (d) §2.3 "Stdlib spool exceptions": the fallback `cancel` performs the
same `approval_stands` check with stdlib only (05 §5.5 step 0; fail closed on any unreadable file);
(e) §2.3: give the fixed literal stdout line an entry point prints when its step-0 **pre-import
block** refuses `trust_interpreter` (05 §5.5 step 0 (3)) — it cannot import `json`, so the bytes are a
constant; (f) `queue --kind approval --owner-executable` (R62) returns, besides the probe-p-failed
rows, every `awaiting_approval`/`authorized` action in **every** mode whose request is `pending`,
signed (approval record accepted by `verify(stage="authorize")`) and `display.operator_executes:
true`, and writes the `owner_exec_due:<request_id>` warn notice for such a row within 24 h of
`expires` (05 §5.5 step 3b); (g) `record-external --kind owner_executed` accepts an `authorized`
action as well as `awaiting_approval`, in probe-pass mode for `operator_executes` requests; (h)
§2.4 `ticket --write`: `enable_budget_mismatch` and `enable_not_agent_executable` are raised after
`verify(stage="mint")` succeeds and before any reservation (05 reason table). A2 tests as in 05 §5.1
step 5, §5.5 step 0 and §5.5 step 3b.

## R76 · `03_schemas.md` §3.2, §3.4.4, §3.7, §3.8, §3.11 (supersedes R68 (a); R68 (b) is already met)
(a) **Enable scope:** 05 §5.5 3b now calls `tiers.is_enable_action(ctx, action, row)` and restates
no verb list; it **adopts** 03 §3.2's `enable_no_budget_object` refusal for a `_nomatch` enable
whose most specific key is a within-ceiling child (05's contrary "withdrawn" text and its A2 test
expecting `keyword`/`resume` to reach `awaiting_approval` are deleted). R68 (a) is withdrawn; R68
(b) is satisfied by the committed auto rows `google_ads.{ad,ad_group,keyword}_enable` and
`meta.ad_enable`. One test set (03's) now governs. (b) **Change kind — WITHDRAWN (wave1e), finding
wave1d-B3/M3.** A verb-token `tiers.change_kind` shows a `remove_end_date`-shaped row (which
resumes spend) as "Remove (stop spend)". Replaced by `display.resulting_status` = the matched row's
authored `resulting_status` (03 §3.4.1/§3.7, landed wave1e); 05 §5.1 step 3 and §5.8 read it.
(Supersedes this item's former `tiers.change_kind`/`display.change_kind` ask and R66 (e).) (c) Add **`display.operator_executes`**
(bool, present on every `$` request) = `connector_dispatch.owner_execution_reason(actx, action) is
not None` (R78) to §3.7's table. (d) §3.7/§3.8: there is no `decided_via: "card"` denial; a
denial record is only the app's (`decided_via: "app"`); drop "a card only ever denies". (e) §3.11:
act.py never writes a `who: "card_deny"` marker (05 and 02 removed the card-deny path); state that a
marker with `who` ∈ {`agent`, `card_deny`, `hand_made_file`, `system:responded_by`} never cancels a
signed, unconsumed `$` approval. (f) §3.7: the shared-warning heading text is "This change touches
a shared or other-company system" in both files (05 aligned to 03).

## R77 · `04_hooks.md` §4.1 (G-A rule 6b), §4.2 (G-B), §4.6 (gate-gtm), `trust_root_path()` (extends R69)
(a) G-A rule 6b stops an in-flight write ticket on a per-action marker **only** when the marker's
`who` ∈ {`operator_script`, `approver_menu`} or the action's request has no approval record with an
unconsumed nonce; an `agent`/`card_deny`/`hand_made_file`/`system:responded_by` marker for a signed
action's ticket is ignored (05 §5.1 step 5). B1 test: an agent marker leaves a signed pause ticket's
next call allowed; an `operator_script` marker denies it. (b) G-B: deny agent commands that pass
`-X pycache_prefix`, `-Xpycache_prefix`, `-X frozen_modules` or a `PYTHONPYCACHEPREFIX` assignment to
any GTM entry point (the start-up-import residual of 05 §5.5 step 0). (c) gate-gtm creates the
prefix it passes to the `ai_budget.py`/`approval_sig.py` subprocess by 05 §5.5 step 0 (1)'s rule
(`gtm_pyc_` + random hex under `gtm_env.gtm_tmp_root()`, mode 0700, empty) or the child refuses it
`trust_interpreter`. (d) R69's B2 oracle: the forged row is `hook "pretooluse_task"`, `decision
"would-block"`, `gate "gtm_task_gate"`, `reason` = the forged deny code, `enforce true`; the
non-forged oracle is "no such row"; if 04 adds an allow row, name its `decision` string. (e)
State beside `trust_root_path()` that prevention is deliberately broader than 05's detection
exclusions (`gtmlib/tests/`, `wave2_pending/`, `.DS_Store`, `__pycache__/` are prevented but not
detected), and never narrow prevention below detection.

## R78 · `06_connectors.md` §6.2 / §6.3 API
Add `connector_dispatch.owner_execution_reason(actx, action) -> str | None`: `"not_agent_executable"`
for §6.2 "Never agent-executable" (every `_nomatch`, every money row with no `write_rows` entry and
no runbook `writes[<row>]` entry), `"enable_not_agent_executable"` for an enable-bound row whose tier
system has no `access: api` account serving `committed_ceiling` (§6.2 "Agent-executable enables"),
`None` otherwise and for `gtm_ai`; never a transient code (`manifest_*`, credential problems). It is
the one predicate behind 05's `display.operator_executes`, and `execute`/`ticket --write` refuse on
the same facts. A2 test: one action per branch; `api_executable_reason` and this helper agree on
`not_agent_executable`.

## R79 · `07_notices_schedules.md` §7.1, §7.5 (D6b), `knowledge/oversight_install.md` row (amends R48/R55)
(a) D6b runs in **every** mode for the rows `queue --owner-executable` returns (R75 (f)): signed
`operator_executes` requests besides the probe-p-failed set; update its gate text and the D/A2 test
("HEAD probe_p `pass` → no rows" holds only for agent-executable requests). (b) Reserve, for
in-process writers, the dedupe prefixes `approval_reshow:`, `nonce_quarantined:`, `revoked_late:`
and `owner_exec_due:` (05 §5.1 step 5, §5.5 step 3b/step 5). (c) 05 writes no `card_deny:` notice:
the `card_deny:` resolver row and any expectation that a 05 card deny writes one stay only as 07's
own ratification-gated R52 branch; 02 §2.11 and 05 do not write it. (d) The `approval_revoked:`
row: severity `urgent` for an `urgency: urgent` request else `warn`, `push: true`, written on
**every** revocation and on every cancel of an unsigned `$` request (05 §5.1 step 5). (e) The
approver's `oversight_install.md` §2 row cadence cell is exactly `every 5 min`.

## R80 · `00_global_paths.md` §0.1, §0.3, §1.1, §1.5 (withdraws R42's "append")
(a) 05 now uses the §0.3 slug grammar `^[a-z][a-z0-9-]{1,31}$` everywhere (app, scripts, pointer
and `apr_`/`act_`/`unt_` ids) with a C test against `system_names.SLUG_RE.pattern`. (b) 05 adopts
§1.5's remove-then-insert-at-0 rule for the four import-time `sys.path` inserts; R42's "append"
wording is withdrawn. (c) 05 maps `RealStateRefused` to exit 3 `test_mode_real_state` and states the
Python-vs-scripts difference for a `CLAUDE_DIR` naming the real root. (d) Add
`gtm_env.gtm_tmp_root() -> str` = `os.path.realpath(os.environ.get("TMPDIR") or "/tmp")` (with
`/tmp` when that is not an existing directory), the literal copy each entry point's pre-import block
carries (05 §5.5 step 0). (e) R37 (`gtm_env.approver_app_path()`) is still missing from 00 and is a
WP-C/WP-A2 prerequisite (05 §5.9 p3). (f) §1.5's B2 tree recipe: state that any fixture a test
**edits** must be a real copy (the symlinked-module recipe would write through into the live tree),
as 05 §5.5 step 2 now requires for every trust-root fixture. (g) Add root `/` and `//` to the
`is_ancestor` unit cases shared with 05's Swift parity list.

## R81 · plan (planner), `08_seats_wps.md` §9 / Appendix B (coordinator) — Deviation register gate
05 §5.9 lists five unratified deviations (V1 signed-`$` cancel channels, V2 trust drift stops
verify/read-run/non-money revert globally, V3 `complete` expiry, V4 release-or-quarantine, V5
fingerprint anchor); V-R71 (breaker pause admits revert) is conformed and removed. (a) Planner: for
each, land a plan §20.x amendment (plan-review round) citing the entry id, or tell 05 to conform;
V2 needs an explicit operator-facing ratification that verify, read-run and non-money revert stop
for every company during every landing and in-tree edit (05 §5.9 names a candidate narrowing). (b)
Coordinator: before any WP-A2 dispatch, file **one** tracked issue with a checklist of V1–V5 and the
§5.9 cross-file prerequisites p1–p6 (runtime CLAUDE.md §8 batch rule), ticking an item only with
the ratifying plan commit or the conforming 05 commit. (c) 08 Appendix B / WP table: WP-A2 does not
start while any §5.9 row reads UNRATIFIED; add the K-style check 05 §5.9 describes.

## R82 · `OPEN_FINDINGS.md` (index maintainer)
FID-03's 05 portion is resolved by 05 §5.5 step 3b ("Enable binding" via `tiers.is_enable_action`
and "Freshness of the bound value": mint API read-back → `budget_readback`, `enable_budget_mismatch`,
`enable_not_agent_executable`, G-A rule 9d, runbook before-check as the second check) together with
its A2 mint test. Mark the 05 row's FID-03 entry resolved citing §5.5 3b and update the 05 row's
counts (L22); FID-03's 03/06 portions stay as their own sections record.

---

# Revision 8 (2026-09-28): wave1c review-findings pass

§5 was revised against six wave1c findings (impl r3 1–5, fid r3 6). The requests below are the
cross-file halves. Each names the §5 text it depends on.

## R83 · `00_global_paths.md` §1.4 "Operator authority", "Validation" item (2)
Split (2) into two ordered checks with named reasons, matching 05 §5 header "Swift canonical JSON":
(2a) the decoded payload bytes equal `canon(json.loads(bytes))`, else refuse `non_canonical`; then
(2b) exactly the seven keys and `kind == "operator_ok"`, else refuse `bad_keys`. Canonical is always
checked before the key set, as in 05 §5.5 step 3a, `approval_sig.py --verify-trust-edit` and
`approval_sig.py --self-test`. Reason: the Swift app builds these bytes itself, and a naive encoder
(`\/` escapes, its own key order) must be reported as `non_canonical`, never masked as `bad_keys`.
A2 test: a marker whose payload has `"\/"` in `target` is refused `non_canonical`.

## R84 · `03_schemas.md` §3.2 "Enable actions" / §3.6 `enable_not_agent_executable` · `06_connectors.md` §6.2 "Agent-executable enables" and `owner_execution_reason` (R78) · `04_hooks.md` §4.1 rule 9d
**(Amended wave1e, finding wave1d-M3: a stop is defined by the matched row's authored
`resulting_status`, never by verb tokens or `display.change_kind`, which is withdrawn.)** State
that a stop action — one whose matched tier row has `resulting_status` ∈ {`paused`, `removed`}
(03_schemas.md §3.4.1, the field every row with `money: true` or `commits_on_enable: true` must
carry, else the tier table is refused at load `resulting_status_missing`) — is never enable-bound: `tiers.is_enable_action` is false for it, `owner_execution_reason` never returns
`enable_not_agent_executable` for it, and G-A rule 9d does not apply to its write ticket. A signed
stop whose row has a connector `write_rows` or runbook `writes[<row>]` entry is agent-executable
under an ordinary signed write ticket; it is operator-executed only through
`not_agent_executable` (a `_nomatch` stop, or a stop row with no write entry). Reason: a stop commits
no ceiling, so FID-03's API read-back has nothing to bind (05 §5.5 step 3b "Stops are never in the
enable group", DECIDED wave1c). A2/L test as in 05 §5.5 step 3b: a signed urgent pause on a
browser-only `L` system with a `writes[<pause row>]` entry mints a write ticket with no
`budget_readback`.

## R85 · plan (planner) · `08_seats_wps.md` §9 / Appendix B (coordinator) — extends R81 to V6
05 §5.9 now lists a sixth unratified deviation, **V6**: operator-executed `$` actions in every mode
(every `_nomatch` action, every money row with no write entry, every enable-bound action on a system
with no API `committed_ceiling` read — e.g. OtherCompanyB's browser-only Meta enables and `L`
lead-marketplace actions), where plan §20.8/§6.1 allow `owner_executed` only as the
probe-p-failed fallback. (a) Planner: ratify V6 by a plan §20.x amendment citing "05 §5.9 V6", or
tell 05 to conform (05 §5.9 names the candidate: browser-only enables under a signed write ticket
with the runbook's ceiling re-read immediately before the click plus a G-A-checked browser read-back;
that needs 03 §3.6, 04 rule 9d and 06 §6.2 changed together). (b) Coordinator: the single tracked
issue of R81 (b) carries V1–V6, not V1–V5; the WP-A2 dispatch checklist line of R81 (c) refuses to
start while V6 reads UNRATIFIED.

## R86 · `02_act.md` §2.5 (cancel-marker ingest) and §2.4 `cancel` · `03_schemas.md` §3.11 (`CANCEL_WHO`)
Adopt 05 §5.1 step 5's full ingest table for a `pending` `$` request (DECIDED wave1c):
`who` class *operator* = {`operator_script`, `approver_menu`}; *agent-class* = every other value,
including one outside `CANCEL_WHO` (unknown, misspelled, absent). Record state from
`S/approvals/<slug>/<request_id>.json` and the nonce ledger: *none*, *denial* (`decision ==
"denied"`, not yet ingested), *approved-unconsumed* (no `consume` line; an unparsable record counts
here), *approved-consumed* (a `consume` line; while `pending` this is a quarantine). Outcomes:
operator × approved-unconsumed → revoke; any × none → cancel; agent-class × approved-unconsumed →
record `who`, delete marker, no change; any × denial and any × approved-consumed → record `who`,
delete marker, request/action/ledger unchanged, no event, no notice. 03 §3.11: state that an ingest
never rejects an unknown `who` as a parse error for a pending `$` request; it is agent-class. A2
tests as listed at the end of 05 §5.1 step 5 ("new cells (wave1c)").

## R87 · `03_schemas.md` §3.9 (nonce ledger line) — a lock-free bash reader exists
05 §5.4 `gtm_cancel.sh` now reads `S/approval_nonces.jsonl` without the lock, matching lines by
`nonce` and `op == "consume"` with `/usr/bin/plutil` (05 §5.4 "Signed-request test in bash").
Add to §3.9: the ledger line field names `nonce` and `op` and the literal `consume` are read by that
script; renaming any of them changes 05 §5.4 in the same commit. Lines are appended whole (one
`write` of the full line plus `\n`), so a lock-free reader sees either the whole line or none of it;
a torn or malformed line is skipped by that reader.

## R88 · `00_global_paths.md` §1.5 (test tree rules) · every section file's "nothing under the real root" tests
05 now defines one **test-footprint oracle** (05 header, "Test-footprint oracle", DECIDED wave1c):
a per-run marker `m` and fixture slug `gtmt-<8 hex>`, checked as (i) no appended line of the real
`.enforcement/log.jsonl` or `.agent_budget/*` containing them, (ii) no real `S`/`tools/gtm` path
named with them, (iii) **(amended wave1e, finding wave1d-M6; the wave1d text dropped (iii) and
called (ii) sufficient, which is false for fixed-name files)** no fixed-name real file the approver
code writes — exactly `S/trust_edit_allow.json` today — carries them in its content (its decoded
payload `path`; an unparseable file only when its sha256 changed during the run). Tests use the
fixture slug for every slug argument, never a real slug. Mtime compares are never used. Whole-root
or whole-directory mtime compares are never used, because the test session's own transcript and
every live session write `~/.claude` continuously. Please state the same rule in 00 §1.5 so 02, 04
and 07 tests that assert "the real root is untouched" use it too (05 §5.5 step 0's gate-gtm B2 test
already does).
