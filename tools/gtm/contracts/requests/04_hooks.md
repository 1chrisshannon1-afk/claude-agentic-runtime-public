# Change requests from `04_hooks.md` (§4 Hook contracts)

Each request names the target file, section and exact change. They follow from fixes applied in
`04_hooks.md` for the findings named. Skip any request the target file's owner has already made.

## R1 — 08_seats_wps.md §9, WP table row "B1 new hooks" (IMP-22) — revised round 5
- **Consumes column:** remove "05_approver.md §5.5 `approval_sig` (A2; `gtm_hooklib` imports it,
  IMP-22)". `04_hooks.md §4` intro decides that `gtm_hooklib` imports neither `approval_sig` nor
  `gtm_pricing` (nothing in its API uses them), and G-W verifies the trust-edit marker with
  `cryptography` and the HEAD key directly, never `approval_sig` from the working tree (04_hooks.md
  §4.3 check 1). Append `07_notices_schedules.md §7.1 notices.write_notice (D) — parity test only`.
  Keep "§8.1 `gtm_result.parse_block` (A1)" (04_hooks.md §4.5 imports `gtm_result`).
- **Implements column:** append `hooks/tests/test_gtm_notice_parity.py` (04_hooks.md §4 "One notice
  format, two writers"); G-W's GTM-scope `pack-edit-in-gtm-session` and `transcript-write` denials
  (04_hooks.md §4.3, FID-07/FID-08); the §4.8 item 6 SubagentStop command test (04_hooks.md §4.8).

## R2 — 08_seats_wps.md §9, WP table row "B2 hook wiring" (IMP-06, IMP-19, FID-15) — revised round 5
- **Implements column:** append `agent_budget.apply_decision`/`_apply_pacer_gate` keyword-only
  `outcome` and `pretooluse_task.apply_t2 -> (exit, denied)` (04_hooks.md §4.6, IMP-06); `ai_budget.py
  caps|state|usd` exact stdout shapes and `caps --check` (04_hooks.md §4.6, IMP-19; 07 R13);
  gate-gtm's `PAUSE.budget` + `budget`/`trust` notice writes (04_hooks.md §4.6 step 3 (a)/(b), FID-15).
- The former Wave-2-posture note of this request is **withdrawn**: 08's own B2 row (the two
  `tools/gtm/wave2_pending/*.patch` files) is now the decision, and 04_hooks.md §4.2, §4.6
  "Delivery", §4.7, §4.8 and §4.9 were aligned to it.

## R3 — 08_seats_wps.md Appendix C item 19 (IMP-04) — **WITHDRAWN (round 5)**
Already covered by item 19's current text (G-B and Task-wiring patches applied in the same step).

## R4 — 08_seats_wps.md Appendix C item 14 (IMP-15)
Replace the harvester addition (a) with: "(a) a new stdlib-only module `tools/gtm/project_dirs.py`
holding `project_dir_name(home: Path) -> str` (moved from `harvest_tool_trail._project_dir_name`),
`project_dir_name_text(path_str: str) -> str` (the pure-text helper, no filesystem call) and
`matches_project_dir_prefix(dir_name: str, prefix: str) -> bool` (moved from
`harvest_tool_trail._matches_project_dir_prefix`, separator-bounded); `harvest_tool_trail` imports
them and keeps `_project_dir_name`/`_matches_project_dir_prefix`/`project_dir_name_text` as
re-exported names so its existing tests pass unchanged. `ai_budget`, `transcript_index`,
`act.py purge-untrusted` and `secret_sink` import `project_dirs`, never `harvest_tool_trail` (which
imports `activity_log` at load)." Keep the existing test `project_dir_name_text("~/Desktop/OtherApp")
performs no filesystem call`, now against `project_dirs`.

## R5 — 00_global_paths.md §0.1 (Agency project-dir prefix paragraph) (IMP-15)
Change `P_A = harvest_tool_trail.project_dir_name_text(A)` to `P_A =
project_dirs.project_dir_name_text(A)` and "a new pure-text helper `project_dir_name_text…`" to
"the pure-text helper in `tools/gtm/project_dirs.py` (08_seats_wps.md Appendix C item 14)".

## R6 — 00_global_paths.md §1.2 `S` layout table (FID-08) — **WITHDRAWN (round 5):** 00 already carries the row with `result_sha256` (08_seats_wps.md §8.1 one definition); the text below is superseded
Add rows:
`agent_results.jsonl   gtm_ticket_release (SubagentStop hook)   04_hooks.md §4.5   {"ts","session_id","agent_id","agent_type","sha256"} of each GTM-session subagent's last_assistant_message (+ agent_results.lock)`.

## R7 — 00_global_paths.md §1.5 item 7 (IMP-04) — **WITHDRAWN (round 5):** 00's stricter current text (never copy a protected file from Bash) is compatible with 04_hooks.md §4.2; no change needed
Append: "For a file G-B protects (`act.py`, `gtmlib/`, `approver_pubkey.pem`), back up and revert
exactly as 04_hooks.md §4.2 'Backing up and reverting a protected file' says (`cp` to scratch is
allowed; restore with Edit/Write or `git apply`, never `cp`/`mv` back). During Wave 2 G-B is not yet
active (04_hooks.md §4.2 activation)."

## R8 — 02_act.md §2.1 file table, `tools/gtm/ai_budget.py` row (IMP-15)
Change "Standalone (stdlib + company, system_names, approval_sig, gtm_pricing)" to "Standalone
(stdlib + company, system_names, approval_sig, gtm_pricing, project_dirs)".

## R9 — 02_act.md §2.4 `purge-untrusted` row (IMP-15)
Replace "transcripts under `R/projects/<_project_dir_name(H)>/**`" with "transcripts under every
`R/projects/<d>/` whose name satisfies `project_dirs.matches_project_dir_prefix(d,
project_dirs.project_dir_name(H))` (worktree and subfolder dirs included), deleting a transcript only
when its own recorded `cwd` is equal to or under H (the harvester's `_transcript_cwd_is_under_home`
rule — a same-prefix sibling folder's transcripts are never deleted)". Test: a worktree-dir
transcript with `cwd` under H older than N days is deleted; a sibling-prefix dir's transcript is not.

## R10 — 02_act.md §2.7(c) and 08_seats_wps.md §8.1 extractor (FID-08) — **WITHDRAWN (round 5):** superseded by 08_seats_wps.md §8.1 "Attestation" (`result_sha256`, `agent_result_unrecorded`/`agent_result_mismatch`), which 04_hooks.md §4.5 now copies
`gtm_result.extract_gtm_result` (and every consumer of a seat's final `gtm-result`: `review`,
`verify`, operations, proposals) reads `S/agent_results.jsonl` (written by the SubagentStop hook,
04_hooks.md §4.5) for the `agent_id`, and refuses: `result_hash_mismatch` when the row's `sha256`
differs from the sha256 of the UTF-8 final assistant message it parsed from the transcript;
`result_unrecorded` when no row exists for that `agent_id`. Test (A1): appending a forged
`gtm-result` message to a real fixture transcript whose `agent_id` has a recorded hash makes
`review` refuse `result_hash_mismatch`; falsified by skipping the comparison.

## R11 — 03_schemas.md §3.16 transcript index (IMP-15)
Change "Project dir name = `harvest_tool_trail._project_dir_name(home)` for GTM homes; the Agency
prefix is `project_dir_name_text(A)`" to "Project dir name = `project_dirs.project_dir_name(home)`
for GTM homes; the Agency prefix is `project_dirs.project_dir_name_text(A)`"; and in the `agent_transcript_path`
fast path comment, `project_dir_name(cwd)` → `project_dirs.project_dir_name(cwd)`.

## R12 — 05_approver.md §5.5 step 2 `TRUST_PATHS` (IMP-15 consequence of IMP-05's reasoning)
Add `tools/gtm/project_dirs.py` to `TRUST_PATHS`: it decides AI-spend attribution step 4
(04_hooks.md §4.6), so an uncommitted edit could move GTM-seat spend to `unattributed` and out of a
company's cap, exactly the class `gtm_pricing.py` is listed for. (04_hooks.md §4.9 already adds
`"tools/gtm/project_dirs"` to the HIGH-tier keywords.)

## R13 — 03_schemas.md §3.6 ticket mint (IMP-07 consequence; recommended)
`act.py ticket --read|--write|--write-batch` refuses (exit 3 `ticket_host_read_only`) when any
`allowed_hosts` entry equals or is a subdomain of an entry in `live-testing/allowlist.json`'s
`read_only_hosts`, because `block_prod_mutations.py` R5 denies every click/type on those hosts for
`playwright-gtm` by design (04_hooks.md §4.9) — so the failure surfaces at mint, not mid-run.
Ticketless reads of those hosts are unaffected.

## R14 — 02_act.md §2.3 "Operator marker" (round 5, rule k)
04_hooks.md §4.2 rule k now uses `operator_ok` (from `system_names.RULE_K_LITERALS`) and §4.7 the
`*operator_ok*` token. Drop the parenthetical "(04's rule k currently lists `operator_ack` instead;
the correction to `operator_ok` is requested in `requests/02_act.md`, and until it lands agents can
forge the marker by running `operator_ok.sh` or a `python3 -c "open('…/operator_ok/…','w')"`)" —
it would also trip the retired-spelling check of 00_global_paths.md §1.4 (its line lacks "retired").

---

# Round 6 (2026-09-27): requests from the review-finding fixes in `04_hooks.md`

Status of requests other files made of 04, applied in this round: `requests/00_global_paths.md`
R12, R13 and R20 (rules l and m, the `_Block.unconditional` mechanism, the §0.4 emit test in G-A,
G-B, G-W, the path gate and gate-gtm, parsed `<UTCts>` comparison); `requests/05_approver.md` R14
(trust check first and alone, isolated subprocesses, `sys.path` append), R15 (a) (the whole live
`R/tools/gtm/` subtree and `R/telemetry/pricing.json` are G-W `trust-root` and rule-c protected in
every session), R15 (b) (rule m covers `PYTHON*`; rule c protects `site-packages`/`*.pth`/
`sitecustomize.py`/`usercustomize.py`; `pip install --user/--target` denied in GTM scope) and R28
(`gtm_env.py`); `requests/07_notices_schedules.md` R17 (G-W `gtm-write-outside-drafts`) and R19
(gate-gtm step −1 `gtm-nonroster-dispatch`). **Still open against 04:** `requests/05_approver.md`
R15 (c) (`git update-index --skip-worktree` on a TRUST_PATH — round 8: G-B rule n now denies every `git update-index` in GTM scope; outside GTM scope it stays open) and R27/R38 (G-W trust-edit
verification through `approval_sig.py --verify-trust-edit` instead of `cryptography`), which no
finding of this round covered.

## R15 — 00_global_paths.md §0.4 (status + two wording alignments)
- R12, R13 and R20 are applied in 04_hooks.md §4.1/§4.2/§4.3/§4.4/§4.6/§4.9; mark them landed.
- §0.4's rule-l wording "in a segment naming act.py" → "in a command any segment of which names
  act.py (`(?<![\w.-])act\.py(?![\w])`, or an operand resolving to `R/tools/gtm/act.py`)", and add
  "a `pytest`/`python[3] -m pytest` segment is exempt" (04 §4.2 rule l; without it
  `CLAUDE_GTM_COMPANY=x python3 -m pytest tools/gtm/tests/test_act.py` would be denied).
- §0.4's rule-m description: append "and `PYTHON[A-Z0-9_]*` (05 R15 (b))".

## R16 — 03_schemas.md §3.6 `batch` ticket row (nit)
Add `money: false` to the batch ticket's extra fields, and state that `ticket --write-batch`
refuses any row whose `money` is not exactly `false` (exit 3 `batch_money_row`). 04_hooks.md §4
`ticket_is_money` already treats class `batch` as non-money, so `S/PAUSE.trust` (plan §20.8: `$`
only) never blocks a batch load.

## R17 — 07_notices_schedules.md (the `playwright-gtm` launch arguments)
Change the `@playwright/mcp@0.0.70` pin to `@playwright/mcp@0.0.76`, the version
`live-testing/browser_pool.py` `_DEFAULT_MCP_VERSION` and `.mcp.json` already pin and the one whose
tool names 04_hooks.md §4.1 classifies (`browser_run_code_unsafe`, `browser_network_request` and
`browser_drop` do not exist in 0.0.70). 04's P2 test asserts the three version strings are equal.

## R18 — 06_connectors.md runbook schema and validator; plan §17 (coordinator)
- Runbook field `money_ui_hosts: [host…]` — hosts whose UI offers money flows regardless of tier
  rows (at least `business.google.com` in the gbp runbook, `business.facebook.com` in meta,
  `biz.yelp.com` in yelp, the Angi and Thumbtack pro consoles). Validator: each entry ⊆
  `system_names.platform_hosts(system)`; a P2 parity test against `platform_hosts`.
- Runbook field `read_click_targets: [{"host", "url_re", "why"}]` (04_hooks.md §4.1 rule 9b
  exception). Validator: for every `inbox`-class read path whose host is a money host (04
  `money_hosts()`), the runbook lists either a clickless `start_url` sequence (navigate + snapshot
  only) or at least one `read_click_targets` entry for that host; neither → refuse
  (`inbox_read_needs_click_on_money_host`). `url_re` must be anchored (`^/…`) and must not match the
  runbook's own write URLs.
- Coordinator: add one plan §17 probe row per inbox platform (Meta Business Suite, Yelp for
  Business, Angi, Thumbtack, GBP) recording whether its conversations/reviews/Q&A can be read
  clicklessly, and if not the `url_re` of pages with no money control, before P6 enables the inbox
  run.
- Also add plan §17 **probe r** (04 §4.1 "Page-URL refresh"): a real `PostToolUse` payload for
  `browser_click` and `browser_snapshot` on the pinned 0.0.76 server, vendored as
  `hooks/tests/fixtures/posttool_playwright_{click,snapshot}.json`.

## R19 — 03_schemas.md §3.6 write ticket mint, and 02_act.md §2.2b/§2.6 (shared-class actions on browser systems)
04_hooks.md §4.1 rule 4s now admits a card-approved shared action (option (a) of the finding;
plan §20.2 "cards, never autonomous" — they execute once the card is approved, 02_act.md's
`awaiting_card` → `authorized` path). 03 §3.6: a write ticket carries `action_class` (the action's
class) and, when it is `shared`, `card_id` (the approving card, verified at mint through
`cards.require_approved`; failure → exit 3 `card_not_approved`, no ticket) and `shared_values` (the
normalized values of the action's `check1.shared_hits`). A non-shared ticket carries
`action_class` only. 02 needs no state change; its §2.6 rule 7 text should cite 04 §4.1 rule 4s as
the browser-side counterpart.

## R20 — 03_schemas.md §3.6 write/batch tickets and §3.22 `system_names`
- Write ticket: `target_ids: {key: value}` = `system_names.target_ids(system, target_ref)` plus the
  check-1-verified `id_fields` values of the action (02_act.md §2.8 check 1), normalized with
  `normalize_account_id`; for a create row also `self_id_key` (the row's `self_id`) and
  `created_ids: {}` (G-A fills it, 04 §4.1 "Rule 7b key classes"). Batch ticket: the union over its
  items (and the union of their `self_id_key`s as a list). Setup ticket: `target_ids: {}`.
- `system_names.IDENTITY_KEYS: frozenset[str]` = `ACCOUNT_LEVEL_KEYS` ∪ the `target_ref` grammar
  keys naming an identity object (business page, location, property, container, site). A1 test:
  every grammar key is in exactly one of `IDENTITY_KEYS` or the in-account set.

## R21 — 03_schemas.md §3.6 `dispatch_brief.steps` and money write tickets (blocker fix)
- Every `dispatch_brief.steps[]` entry carries `value` (the filled string, or null for a step that
  enters nothing) and `value_kind ∈ {"text", "amount"}` (`amount` exactly when the placeholder is a
  money field of the row: `new_absolute_value`, a budget or bid field).
- A money write ticket carries `signed_amount` (the decimal string of the verified signed payload's
  `after.new_absolute_value`, copied at stage `mint`). Mint refuses exit 3 `amount_mismatch` (no
  ticket, no nonce reservation) when any `amount` step's value is not `Decimal`-equal to it.
- 06_connectors.md §6.4: runbook steps that type into a field name the after-field they are filled
  from, so `value_kind` is derivable. 04_hooks.md §4.1 rule 9c binds every typed/filled/selected
  value to these.

## R22 — plan (`gtm_autonomous_department_plan.md`) §20 and 08_seats_wps.md Appendix B (coordinator)
Record the browser `$` residual (04_hooks.md §4.1 "The `$` residual") as a plan amendment — a new
§20.x plus an Appendix B entry — so the operator-facing `$` rule states it: a write/batch ticket for
a non-money row on a money host can click a money control, and a click on a page-suggested amount
types nothing; both are detect-after (change-history reconcile, day-after verify). Until the
operator's ruling is recorded, this is a deviation from plan §20.6's absolute rule and the
coordinator lists it as open.

## R23 — 00_global_paths.md §0.4 (G-A on `playwright-gtm`)
Add to the "in every session" list: "every G-A deny on the `playwright-gtm` server (a server that
exists only for GTM work, 04_hooks.md §4.1 emit test)".

## R24 — 05_approver.md §5.5 `TRUST_PATHS` and step 0; 08_seats_wps.md §9 B2 row; 02_act.md
- New module `tools/gtm/dispatch_tags.py` (B2): `count_dispatches`, `admit_and_record`,
  `release_admission` moved from `ai_budget` (which re-exports them unchanged), stdlib + `company` +
  `system_names` only, so gate-gtm can import it in-process without importing `ai_budget` (05 §5.5
  step 0 "a hook never imports `approval_sig` or `ai_budget` in-process"). Add it to `TRUST_PATHS`
  and to 08's B2 row (Implements). 02 call sites of `ai_budget.release_admission`/`count_dispatches`
  keep working through the re-export.
- 05 §5.5 step 0: gate-gtm now runs `approval_sig.py --trust-result` **first** as its own isolated
  subprocess and runs `ai_budget.py state --company X` only when it passes (04_hooks.md §4.6
  F-trust); please name `--trust-result`'s JSON shape (04 reads `ok`).

## R25 — 02_act.md `validate_run` (detect-after for direct marketing commits)
Add a `validate_run` check: every commit in the run window (the GTM home's toplevel, `git log
--since=<run open ts>`) touching a path matched by the company's committed `marketing_paths`, for
which no `website_static` action with state `completed` has `after.paths` equal to the commit's
path set, is reported (`marketing_commit_without_action`, severity urgent). A2 test: a fixture
commit of `marketing/website/index.html` with no action is reported; one matching a completed
action is not.

## R26 — 03_schemas.md pack schema / `company.py` validator (FID-07 hooks consequences)
- Refuse a pack whose `paths.feature_inventory_dir`, `paths.plans_dir` or `paths.metrics` is equal
  to or under `.claude/gtm/state/` (`editable_path_in_state`); activity_log.py's default
  `feature_inventory_dir` must move out of `state/` (04_hooks.md §4.3 makes `state/`
  machine-written in every session).
- Refuse a pack whose machine-written `paths.*` values (`activity_log_dir`, `scoreboard`,
  `snapshots_dir`, `missions_dir`, the mirror render) contain, in their repo-relative text, none of
  the 04_hooks.md §4.7 tokens (`activity_log`, `.jsonl`, `scoreboard`, `snapshots`, `missions`,
  `.claude/gtm`) (`machine_path_not_forwarded`), so a shell redirect into them from a non-GTM
  session always reaches G-B.
- Refuse a pack whose `paths.*` editable entries overlap a `marketing_paths` glob (04 §4.3: GTM
  sessions never tool-edit marketing source, but may edit pack-declared paths in interactive runs).

## R27 — 07_notices_schedules.md §7.6 step 5 and 08_seats_wps.md (status and registration)
- 07's R17 and R19 are applied (04_hooks.md §4.3 `gtm-write-outside-drafts`, §4.6 step −1); §7.6
  step 5's "installs no scheduled prompt until R17 and R19 land" can now point at those sections.
  Scheduled runs are recognised by `CLAUDE_GTM_RUN` (a non-`interactive` `CYCLE_ID_RE` kind, or
  absent — fail closed), so `run_gtm_job.sh`/`gtm_session.sh` must always export it.
- 08 Appendix C item 19 / §4.8: the coordinator also registers 04_hooks.md §4.8 **item 8** (G-A's
  `PostToolUse` entry on `mcp__playwright-gtm__.*`) in B1's train, with item 3.
- 08 §9 B1 row (Implements): G-B rules l and m; `gtm_hooklib.machine_written`,
  `trust_root_path`, `gtm_session_write_verdict`, `money_hosts`, `redirect_targets`,
  `ticket_is_money`; G-A rules 9c and 7b key classes, the isolation-stop, the tickets-lock critical
  section and the PostToolUse refresh; G-W `runtime-write-in-gtm-session`,
  `marketing-path-via-patch-only`, `gtm-write-outside-drafts`.

---

# Round 7 (2026-09-27): verification pass over OPEN_FINDINGS.md's `04_hooks.md` section

All 13 findings tagged for `04_hooks.md` (IMP-04, IMP-05, IMP-06, IMP-07, FID-07, FID-08, FID-15,
IMP-14, IMP-15, IMP-19, IMP-22, IMP-23, IMP-25) are resolved in `04_hooks.md` (§4 intro and seat
constants; §4.2 rules a/c/k, "Activation", "Backing up and reverting a protected file"; §4.3
`trust-root`, `pack-edit-in-gtm-session`, `transcript-write`; §4.5 result record; §4.6 module
dependencies, `caps`/`state`/`usd` shapes, F-trust inputs outside TRUST_PATHS, step 3 (a)/(b),
T2-deny `outcome`; §4.9 R5). One cross-file inconsistency remains, in 00:

## R28 — 00_global_paths.md §1.5 item 7 "Protected files (IMP-04)" (supersedes the R7 withdrawal note)
The sentence "for `gtmlib/**`, back up with the Read tool and a Write to the scratchpad, revert
and restore with Edit/Write (G-W does not protect `gtmlib/`)" is now false: 04_hooks.md §4.3
`trust-root` (applied from `requests/05_approver.md` R15 (a)) protects the **whole** live
`R/tools/gtm/` subtree — `gtmlib/` included — except `tests/`, `connectors/*/tests/`, `contracts/`
and top-level `*.md`, and G-B rule c protects the same set from shell writes. Replace the text from
"After it:" to the end of the paragraph with:
"After it: back up with the Read tool and a Write to the scratchpad, or `cp <protected file>
<scratch>/` (a `cp` source is a read, 04_hooks.md §4.2 rule c exception); revert and restore either
with `git diff HEAD -- <file> > <scratch>/x.patch` and `git apply [-R] <scratch>/x.patch` (git
subcommands are never rule-c writes), or with Edit/Write under a fresh single-use GTMApprover-signed
`S/trust_edit_allow.json` per file (04_hooks.md §4.3) — or, preferably, do the falsification in a
lane/worktree copy (`R/.claude/worktrees/…`, not under the live `R/tools/gtm/`, so neither gate
applies). Where that is impractical, the falsification test monkeypatches the guard function to its
reverted behavior in-process and asserts the paired test's assertion fails. Never restore a
protected file with `cp`/`mv` from Bash (denied)." This matches 04_hooks.md §4.2 "Backing up and
reverting a protected file once G-B is live" word for word in substance.

---

# Round 8 (2026-09-27): requests from the review-finding fixes in `04_hooks.md`

Applied in `04_hooks.md` this round, from other files' requests: `requests/05_approver.md` R33
(G-B rule n, widened to default-deny git writes in GTM scope), R43 (b) (rule c protects the pinned
interpreter's tree and `brew … python@3.13`) and R51 (rule g denies running `gtm_approve.sh` in
any mode); `requests/07_notices_schedules.md` R32 (signed `"0.00"` = zero cap; `caps --check`
keys) and R34 (signed report-only form); `requests/02_act.md` item 69 (G-A rule 6b reads
`S/pause_spool/`); 00_global_paths.md §0.4's DECIDED department-seat Agency arm
(`gtm_hooklib.agency_scope`, `requests/00_global_paths.md` R27). R16 (below) is confirmed landed in
03_schemas.md §3.6 and 04 now relies on it (no `batch` special case in `ticket_is_money`).

## R29 — 00_global_paths.md §1.1 "Import rule" (hook import rule)
Replace "inserting, at call time and only when absent, `str(Path(__file__).resolve().parent.parent /
"tools" / "gtm")` at `sys.path[0]`" with "appending, at call time and only when absent, `str(Path(
__file__).resolve().parent.parent / "tools" / "gtm")` to `sys.path` (never prepending), after setting
`sys.dont_write_bytecode = True` and `sys.pycache_prefix = str(S / "pycache")`; a hook never makes
`R/tools/gtm` (the `CLAUDE_DIR`-derived state root) importable". This is 04_hooks.md §4 "The hook
import rule", cited by every hook-side import in 04 (it also satisfies `requests/05_approver.md`
R42's "append").

## R30 — 00_global_paths.md §1.1 `gtm_env` API (A1) and 05_approver.md §5.5 step 2
Add `gtm_env.git_show_head(root: str | Path, relpath: str, *, timeout: float = 5.0) -> bytes | None`:
runs `/usr/bin/git --no-replace-objects -c core.fsmonitor=false -c core.untrackedCache=false -C
<root> show HEAD:./<relpath>` with 05 §5.5's scrubbed environment (`PATH=/usr/bin:/bin`, `HOME`,
`LANG=C`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_NO_REPLACE_OBJECTS=1`, no
other `GIT_*`), returning the blob bytes or `None` on non-zero exit/timeout. Stdlib-only (it stays
in the preventive pre-check set). 04 routes every committed read through it (`load_pack_safe`,
`money_capable_systems`, `setup_script_allowlist`, `activation_state`, G-W's pubkey read,
`ai_budget`'s company_json caps, `dispatch_tags`' committed pack); 05's own `approver_pubkey.pem`
read (§5.5 step 1) should call it too so there is one argv. A1 test: after `git replace` of a
committed blob in a tmp repo, `git_show_head` returns the original bytes (RED without
`--no-replace-objects`).

## R31 — 03_schemas.md pack schema / `company.py` (A1) and `activity_log.py` (mirror path)
- Add `company.mirror_files(slug: str, pack: dict, home: Path) -> list[Path]` — pure, env-free: for
  a pack with a TOP-LEVEL `mirror_dir`, `[Path(expanduser(mirror_dir)) / f"{b}.md", … / f"{b}.html"]`
  with `b = pack.get("mirror_basename") or default_mirror_basename(slug, pack)` (move
  `activity_log._default_mirror_basename` into `company` and re-export it from activity_log); `[]`
  without `mirror_dir`. `activity_log.resolve_paths`/`render_mirrors` call it (keeping their
  `TS_ACTIVITY_MIRROR_DIR` test override on top), so hooks (04 §4 `mirror_files`) and the writer
  cannot drift. A1 test: activity_log's rendered files equal `company.mirror_files(...)` for a
  fixture pack with and without `mirror_basename`.
- Extend R26: refuse a pack whose `mirror_dir` is not absolute after `expanduser`
  (`mirror_dir_not_absolute`) — activity_log resolves a relative one against its process cwd, which
  no hook can predict.

## R32 — 03_schemas.md §3.6 write ticket (shared class) and 02_act.md `ticket --write` (amends R19)
Mint of a `shared`-class write ticket calls exactly `cards.require_approved(ctx, card_id,
f"authorize {action_id}")` — the subject `card-post --action` binds (02 §2.4) — and records
`card_subject: "authorize <action_id>"` on the ticket. G-A rule 4s additionally requires
`ticket.card_subject == "authorize " + ticket.action_id` (04_hooks.md §4.1). A2 test: a card
approved under subject `authorize act_x_2` does not mint a shared ticket for `act_x_1` (exit 3
`card_subject_mismatch`).

## R33 — 02_act.md §2.4 `ticket --write`, 03_schemas.md §3.6, 06_connectors.md §6.2/§6.4 (enable binding on the browser path, FID-03)
- 06: every connector whose system has a row with `commits_on_enable: true` exposes a read method
  `configured_budget(target_ref) -> {"value": "<decimal str>", "unit"}` through the API (never the
  browser).
- 02 `ticket --write` for such a row: immediately before minting, call it; refuse exit 3
  `enable_budget_mismatch` when the value is not `Decimal`-equal to the signed `new_absolute_value`
  (or the unit differs); when the system has no such read method, refuse exit 3
  `enable_not_agent_executable` — the operator performs the change and it is recorded with
  `record-external --kind owner_executed` (plan §20.8 fallback).
- 03 §3.6: every write ticket carries `commits_on_enable` (bool, from the row) and, when true,
  `budget_readback: {"value", "unit", "read_at", "via": "api", "target_ref"}` copied at mint.
  G-A rule 9d (04_hooks.md §4.1) denies every mutating call on an enable-bound ticket whose
  read-back is absent, not `via: "api"`, stale (outside `[created_at − 5 min, created_at]`) or not
  equal to `signed_amount`.

## R34 — 03_schemas.md §3.6 and 02_act.md `ticket --write`/`--write-batch` (send window, FID-24)
Every write and batch ticket carries `send_bound` (bool: the row, or any batch item's row, has
`recipient_required` or `list_send`) and, when true, `send_not_after` (UTC ISO) = min(`expires`,
the next quiet-hours start for a named-person recipient in pack time, the end of the current SMS
send window for an SMS row — every item's for a batch), computed at mint from the same inputs as
§3.11's send-time re-check. G-A rule 6b denies every mutating call at or after it
(`outside-send-window`), and treats a missing `send_bound` as true and a missing/unparsable
`send_not_after` on a send-bound ticket as expired. Also correct 03 §3.11's sentence "a browser hold
released at 19:59 cannot then be executed inside quiet hours" to cite this field as the browser-path
mechanism.

## R35 — 02_act.md `ticket --write`/`--write-batch`; 08_seats_wps.md Appendix C item 19; plan §20 (coordinator) — money-host activation precondition
- New committed trust-root file `tools/gtm/activation.json` `{"r22_money_residual_ruling": null}`
  (A1 creates it with `null`; under the live `R/tools/gtm/` subtree, so G-W `trust-root` and
  TRUST_PATHS cover it — 05 please confirm the TRUST_PATHS directory entry includes it).
- 02: `ticket --write`/`--write-batch` refuse exit 3 `money_residual_unratified` when any
  `allowed_hosts` entry is in `money_hosts()` (04_hooks.md §4 — the runbook read/login hosts of
  every money-capable system plus every runbook's `money_ui_hosts`) and the HEAD
  `activation.json` has no non-empty `r22_money_residual_ruling`. G-A rule 6c enforces the same at
  the click.
- 08 Appendix C item 19, coordinator checklist line (verbatim from 04_hooks.md §4.8): "Before
  committing `tools/gtm/activation.json` with `r22_money_residual_ruling`: the plan §20.x amendment
  for the browser `$` residual (04_hooks.md §4.1) and its Appendix B entry are recorded with the
  operator's verbatim ruling and its id; the commit is HIGH-tier reviewed; until then, money-host
  write tickets stay refused at mint and at G-A (rule 6c)."
- R22's operator-facing amendment text must also state the enable case: an enable is executed on
  the browser only after an API read-back equals the signed amount (rule 9d), otherwise by the
  operator; a page-suggested amount clicked between that read-back and the enable click is
  detect-after.

## R36 — 05_approver.md §5.5/§5.6 (backstop for a HEAD moved by interpreter-issued git)
04_hooks.md §4.2 rule n now denies every git write in GTM scope, but an interpreter that builds the
command name from pieces (`subprocess.run(["g"+"it", "commit", …])`) is a stated gap, and a HEAD
moved that way passes `trust_root_ok` (working tree = HEAD). Please add a backstop: an
operator-signed (GTMApprover) anchor of the TRUST_PATHS tree — e.g. `S/trust_anchor.json` holding
the signed `git ls-tree` digest of HEAD's TRUST_PATHS, re-signed through `gtm_approve.sh
trust-anchor` from the operator's terminal after a reviewed runtime commit — and have
`trust_root_ok` fail `trust_anchor_mismatch` when HEAD's digest differs. Until it lands, 04 states
the gap (rule n cell) and R37's `validate_run` report is the detect-after.

## R37 — 02_act.md `validate_run` (widens R25)
Replace R25's check with: every commit in a GTM run's window (the GTM home's toplevel **and** `R`,
`git log --since=<run open ts>`, read with `--no-replace-objects`) whose path set matches neither a
completed `website_static` action's `after.paths` nor a set of `ST/pending_commit.txt` entries is
reported `gtm_commit_unexplained`, severity urgent — on any path, not only `marketing_paths`. A2
tests: a fixture commit of `modules/a.py` in the window is reported; a commit of `marketing/website/
index.html` matching a completed action is not; a commit of a pending-commit path is not; a commit
under `R` in the window is reported.

## R38 — 00_global_paths.md §0.4 (unconditional list) and 08_seats_wps.md §9 B1 row
- §0.4 "In GTM scope": add G-B rule n (`gtm-git-write`) by name. Mark R27 (department-seat Agency
  arm) applied in 04_hooks.md (`gtm_hooklib.agency_scope`; G-A 3b, G-B rule i, path-gate rule 1;
  `bash_gate.sh` arm 2b and the §4.8 item 3/5 department globs).
- 08 §9 B1 row (Implements): G-B rule n and the rule-g `gtm_approve.sh` clause; rule c's
  interpreter-tree clause; `gtm_hooklib.agency_scope`, `mirror_files`, `activation_state`,
  `git_show_head` (re-export), `OPERATOR_RE`; G-A rules 6c and 9d, the send-window check of 6b, the
  pause-spool read, the rule 7b identity-by-brand clauses and the §4.8 item 3 shell prefix.
  B2 row: `ai_budget` zero-cap/report-only reading, `caps --check` R32 keys, `--json` accepted,
  `dispatch_tags.AdmissionInputUnreadable`, `pretooluse_task._TRUSTED_PYTHON`, `bash_gate.sh` arm 2b
  and the widened `sed|perl` arm.
- Preconditions of B1 (08 §9): R16 (landed), R30 (`gtm_env.git_show_head`), R31
  (`company.mirror_files`), R32–R35 ticket fields (G-A fails closed without them, so B1 may land
  first, but no write ticket admits a mutating call until they do).

## R39 — 03_schemas.md §3.6 batch row (wording, after R16)
Change "(so 04_hooks.md §4 `ticket_is_money` may treat class `batch` as non-money and
`S/PAUSE.trust` never blocks a batch; requests/04_hooks.md R16)" to "(so `ticket_is_money`, which
applies the plan §20.6 'money unless `money` is exactly `false`' rule to every class including
`batch`, reads a batch ticket as non-money and `S/PAUSE.trust` never blocks a batch; 04_hooks.md §4)".

## R40 — 07_notices_schedules.md §7.2/§7.6 and 05_approver.md §5.5 (status)
- 07 R32/R34 are applied in 04_hooks.md §4.6: `caps --check` prints exactly `{"pass", "reason",
  "zero_cap", "zero_cap_enforced", "report_only_signed"}`; 07's scheduled-start refusal can read
  those keys.
- 05 §5.5's `ai_budget.py <subcommand> --json`: 04 accepts and ignores `--json` on every
  subcommand, so 05 need not change; gate-gtm runs `… ai_budget.py state --company X --json`.
- 05 §5.5 R41 (p95 re-measure through both isolated subprocesses) stays as stated in 04 §4.6.

## R41 — 03_schemas.md §3.22 `system_names` (A1), 06_connectors.md runbook schema/validator, plan §17 (coordinator) — target proof on id-less URLs
04_hooks.md §4.1 rule 7b now requires, for every **mutating** call on a write/batch ticket that
carries a value for its system's proving key, that the page URL carry that key with the ticket's
value (deny `target-unproven`), because on id-less URLs (GBP from Google Search or
`business.google.com` overviews, Meta Business Suite pages without `asset_id`, WordPress admin)
nothing else stops a write landing on another business's object (plan §18's top risk).
- 03 §3.22 / A1: add `system_names.proving_key(system: str) -> str | None` — per system, the most
  specific identity key that identifies the object a write lands on (e.g. gbp `location_id`, meta
  `page_id`, google_ads `customer_id`; A1's table is binding), `None` for a system whose grammar has
  no identity key. A1 test: every non-None value is in `IDENTITY_KEYS` and in that system's grammar.
- 06 runbook schema + validator: two optional keys, `"identity_in_url": false` and
  `"acting_as_step": "<step id>"`. The validator refuses `identity_in_url: false` unless
  `acting_as_step` names a step of the same runbook that carries an `expect` check of the acting-as
  identity (the brand/page/location name the step expects on screen). G-A reads both from the
  COMMITTED runbook only (04 §4 `read_runbook`).
- Coordinator, plan §17: one probe row per system whose runbook declares `identity_in_url: false`
  ("does any page of the write flow carry the proving id in its URL? if yes, drop the declaration"),
  recorded before P6 relies on it; and the residual (prevention = acting-as `expect` step + acting-as
  prose; detection = change-history reconcile + day-after verify) added to the plan §20.x amendment
  R22 requests, next to the browser `$` residual.

## R42 — 02_act.md §2.4 `status` and the `website_static` executor (A1) — authorized-patch binding for G-B rule n
04_hooks.md §4.2 rule n's exceptions (the `git apply --index ST/patches/<id>.patch` and the
pack-scoped commit) are now admitted only for an action the hash-chained fold reports `authorized`,
because `propose` writes `ST/patches/<action_id>.patch` before any review (02 §2.4), so the file's
existence proved nothing. G-B learns the state by running, from the hook process of a GTM session,
`<TRUSTED_PYTHON> -I -S -B -X pycache_prefix=<fresh P> <T>/tools/gtm/act.py status --action
<id>` and `… status --state authorized`. Please fix, in 02 §2.4 `status`:
- **Result shape:** `result.actions` is a list of fold records (03_schemas.md §3.3, the fields
  `action_id`, `state`, `row_id`, `after` at least); `--action <id>` returns exactly one element;
  `--state authorized` returns every authorized action of the company (no default `--limit` cap
  applies when `--state` is given, or state the cap and 04 will pass `--limit 1000`).
- **Callable from a hook:** `status` succeeds when started as a subprocess of a PreToolUse hook in
  a GTM session (the hook's environment unchanged: `CLAUDE_GTM_COMPANY`, `CLAUDE_GTM_SESSION`,
  `CLAUDE_GTM_RUN`), i.e. the GTM-session proof of §2.3 accepts it, or `status` is exempt from the
  proof as a read-policy command; exit non-zero on a trust-root failure or a broken chain (as today).
- **Path sets:** `after.paths` of a `website_static` action equals the union of the `a/` and `b/`
  paths of the stored patch's `diff --git` headers (`/dev/null` excluded), so a rename lists both
  names — G-B compares exactly that union (04 §4.2 `patch_paths`).
- **Executor text:** the `website_static` executor paragraph should say that G-B rule n admits the
  apply and the commit only for an `authorized` action whose stored patch still hashes to
  `after.patch_sha256`, and the commit only in an interactive run with a pathspec equal to
  `after.paths` (so a `proposed`, `changes_requested` or `superseded` action's patch is never
  applicable). Optional hardening (not required by 04): keep proposed patches under
  `ST/proposed_patches/` and copy to `ST/patches/` only at `authorize`, deleting the copy on
  supersede/cancel/complete/fail.
- A1 end-to-end test (04 names it): G-B's `authorized_static_action` against the real `act.py
  status` for a fixture action in `proposed`, then `authorized`, state.

## R43 — 00_global_paths.md §1.2 S layout and 05_approver.md §5.5 step 0 (hook bytecode)
04_hooks.md §4's hook import rule no longer uses `S/pycache`: hooks set `sys.dont_write_bytecode =
True` and `sys.pycache_prefix = "/dev/null/gtm-hook-no-pycache"` (a path that can never exist), so
no cached bytecode is read from anywhere. Reason: S sits under `claude_dir()`, which honors
`CLAUDE_DIR`, and agents can write S through shell forms rule c does not parse; `-B`/
`dont_write_bytecode` stops writes, not reads, so a planted `.pyc` there would run inside every
GTM hook (05 §5.5 step 0 already withdrew `S/pycache/` for entry points for the same reason).
- 00 §1.2: remove the `pycache/` row (L1121 "hook entry points (`pycache_prefix`, 0700)") and the
  `S/pycache/` bullet (L1162), or mark both withdrawn.
- 05 §5.5 step 0: add one sentence — "in-process hook imports (04_hooks.md §4 hook import rule) set
  `sys.pycache_prefix` to a path under `/dev/null`, never `S/pycache`".
- This supersedes the pycache half of R29 ("after setting … `sys.pycache_prefix = str(S /
  "pycache")`").

## R44 — 02_act.md §2.8 check 9, 08_seats_wps.md Appendix C item 13, 00_global_paths.md §0.1 (A1) — one never-list, hook-importable
G-B rule n now rejects a commit pathspec containing any `MARKETING_PATH_NEVER` path (e.g.
`marketing/website/build.mjs`, the CSA AI-provenance publish gate) even when it matches the pack's
`marketing_paths`. Hooks may import only `company`, `system_names`, `gtm_env` (04 §4), never
`gtmlib`. Please move the one definition: `MARKETING_PATH_NEVER` and `glob_full_match` live in
`tools/gtm/system_names.py` (stdlib-only, A1), and `gtmlib.checks` re-exports them (never a copy).
00 §0.1's "The single definition is `gtmlib.checks.MARKETING_PATH_NEVER`" becomes
"`system_names.MARKETING_PATH_NEVER`, re-exported as `gtmlib.checks.MARKETING_PATH_NEVER`". A1 test:
`gtmlib.checks.MARKETING_PATH_NEVER is system_names.MARKETING_PATH_NEVER`.

## R45 — 05_approver.md §5.3/§5.4, 03_schemas.md, 02_act.md (R35), 08 Appendix C item 19 — operator-signed activation (supersedes R35's file shape)
04_hooks.md §4 `activation_state()` now accepts the R22 ruling only from a GTMApprover-signed
record, because a bare id in a committed file is agent-supplyable (a non-GTM session can `git
apply` and commit under `R`; the gate-3b record is self-recordable), while plan §20.8 reserves the
ruling to the operator.
- 03: schema `gtm.activation.v1` — `tools/gtm/activation.json` = `{"schema", "payload_b64",
  "signature_b64", "alg", "key_fingerprint", "signed_at"}`, payload the canonical JSON `{"v": 1,
  "kind": "activation", "ruling_id": "<operator ruling id>", "nonce": "<32 hex>"}` with exactly
  those keys. Not single-use (the nonce is never consumed).
- 05: a new app mode `--sign-activation <ruling_id>` (Touch ID, fresh LAContext, reason "Activate
  browser money-host writes under ruling <ruling_id>") and `gtm_approve.sh activation <ruling_id>`
  that writes the signed record to `S/activation_signed.json`; the coordinator copies it to
  `tools/gtm/activation.json` and commits it (HIGH tier). G-B rule g already denies every agent
  run of `gtm_approve.sh`. The `kind` differs from `trust_edit` and from every `$` payload, so none
  can pass as another.
- 02 (amends R35): `ticket --write`/`--write-batch`'s `money_residual_unratified` refusal verifies
  the same signature against HEAD's `approver_pubkey.pem` (through `approval_sig`, act.py's own
  trusted path) and treats an unsigned, legacy-shaped or unverifiable file as no ruling. A1 creates
  no placeholder file (or keeps `{"r22_money_residual_ruling": null}`, which reads as no ruling).
- 08 Appendix C item 19: replace R35's checklist line with 04 §4.8's new line (the record must be
  the operator's own `gtm_approve.sh activation` output, never hand-written).

## R46 — 00_global_paths.md §1.2 `other_businesses.json`, WP-M, 08 Appendix C item 19 (coordinator)
04 §4 `identity_hosts_other_than`/`account_ids_other_than` now read `S/other_businesses.json`
directly (plan §7.6) and treat an **absent** file as unreadable (fail closed: G-A denies ticketed
tools `gate-fault`). So: WP-M's `gtm_lists.py` must create it seeded with plan §2's cross-connected
Meta ad account `12864445` (and the known OtherCompany / non-GTM business domains and addresses) as
part of P1, and the coordinator's Appendix C item 19 checklist gains: "Before registering G-A
(§4.8 item 3): `S/other_businesses.json` exists, parses, and contains `12864445`." 00 §1.2 may add
that hooks read the file directly (not only `identity_index.json`).

## R47 — 08_seats_wps.md Appendix B (coordinator) — unsigned company_json AI cap is enforced
04 §4.6 "Effective AI caps" records a deliberate fail-safe narrowing of plan §20.6/§20.13: with no
signed cap, a non-zero unsigned `company.json` `budget.weekly_usd_cap_<b>` is enforced (crossing it
writes `PAUSE.budget` and stops AI dispatches), although §20.13 reconciles automatic enforcement
only for an operator-approved cap. It only stops spend earlier, never raises or removes a cap.
Please add it to Appendix B as a DECIDED HERE item citing 04 §4.6.

## R48 — 00_global_paths.md §1.1 "Import rule" vs 04_hooks.md §4 "The hook import rule" (coordinator: CONFLICT, blocking B1/B2)
The two contracts now disagree, both marked DECIDED: 00 §1.1 (as edited 2026-09-28) says a hook
inserts the **unresolved** code root at `sys.path[0]` (remove-then-insert, "never appended") so
site-packages cannot shadow `gtm_env`/`approval_sig`, and so B2's symlinked tmp tree keeps the tmp
modules first; 04 §4 says the code root (`Path(__file__).resolve()…`) is **appended** only when
absent, "never prepended, so a planted module cannot shadow the stdlib or `_lib`", and R29 asked 00
to adopt that. An implementer cannot satisfy both. The coordinator picks one; 04's author notes that
00's two reasons are real (a `.resolve()` breaks the symlinked B2 harness; appending lets a
site-packages `gtm_env` shadow ours), and 04's reason is real too (prepending lets a module in the
code root shadow a stdlib name). A combined rule that meets all three: insert the unresolved code
root at index 0 **and** keep B2's `test_no_module_name_collision` extended to stdlib names
(`sys.stdlib_module_names`) and `_lib`. 04 §4 will be aligned to the coordinator's ruling; until
then B1/B2 must not start the import-path code.

## R49 — 00_global_paths.md §1.1 "Import rule" (supersedes R29; resolves R48) — A1 `company.py`
04_hooks.md §4 "The hook import rule" is rewritten and no longer uses `sys.path` at all: every
hook-side `tools/gtm` import goes through the new stdlib-only library `hooks/gtm_import.py`
(WP-B1), which installs, at `sys.meta_path[0]`, a finder that serves **only** the names in
`GTM_HOOK_MODULES = {"company", "system_names", "gtm_env", "dispatch_tags", "gtm_result"}` from
the **unresolved** code root `Path(os.path.abspath(__file__)).parent.parent / "tools" / "gtm"`
(raising `ModuleNotFoundError` rather than falling through to `sys.path` for a missing one), and
returns `None` for every other name. This meets all three reasons R48 lists: a site-packages
`company`/`gtm_env` can never shadow the GTM module (the finder answers first), a code-root
`json.py` can never shadow the stdlib (the finder never serves it), and the symlinked B2 harness
keeps the tmp modules (no `.resolve()`). Please (a) replace 00 §1.1's "insert at `sys.path[0]`,
remove-then-insert" text with a pointer to 04 §4's rule for hooks (tools and entry points keep
00's own rule), keeping `test_no_module_name_collision` and extending it with
`sys.stdlib_module_names` and `_lib` as R48 proposed; (b) withdraw R29's "append" wording; (c)
A1: `company._pack_system_set`'s lazy `sys.path.insert(0, this_dir)` before `import activity_log`
(`requests/05_approver.md` R70 (b)) must not run on any path a hook reaches — either import
`activity_log` by file path there, or document the function as tool-only; 04's B1 test asserts
`sys.path` is unchanged after every hooklib helper runs.

## R50 — 05_approver.md §5.5 canonical CLI (`approval_sig.py`); 02_act.md R35/R45 (activation)
04_hooks.md §4 `activation_state` no longer verifies in-process (00_global_paths.md §0.2 forbids
the third-party package it used). Add the mode `approval_sig.py --verify-activation`: runs steps
0–2; reads `tools/gtm/activation.json` and `approver_pubkey.pem` at `T` through the step-2
`git show HEAD:` read; verifies with step 4's backends; requires canonical payload bytes with
exactly `{"v", "kind", "ruling_id", "nonce"}`, `kind == "activation"`, `v == 1`, `ruling_id` a
non-empty string; prints exactly one JSON object `{"ok": bool, "reason": str|null, "ruling_id":
str|null}`; exits 0 valid, 7 invalid (unsigned, legacy-shaped, wrong key, wrong kind, bad bytes),
4 not committed, 11 trust failure, 3/2/1 root mismatch/usage/internal. It never consumes the nonce
(activation is a standing state). A2 tests: the 04 §4.1 rule-6c cases (unsigned legacy file,
wrong key, `kind: "trust_edit"`, a `git replace`d pem) each exit 7; a valid record exits 0. act.py's
mint refusal (02, R35/R45) should call the same verification in-process through `approval_sig` so
the two readers cannot drift.

## R51 — 03_schemas.md §3.20 "Hook readers — fail closed" vs 00_global_paths.md §1.2 (coordinator: align)
The two files now state different fail-closed rules for an unreadable `phi_denylist.json`. 04
follows 00 §1.2 (DECIDED there, and the review's instruction): path gate and G-B deny every
GTM-scope/GTM-seat read target outside the session company's `H`, **`R`** and the temp roots
(`phi-denylist-unreadable`); G-A denies **every** `browser_navigate` (and every call whose rule 3
runs) as `phi-host`. 03 §3.20 says `H`, `R/tools/gtm`, `R/knowledge/marketing_kb` for paths and
"any host not in the identity allowlist or runbook hosts" for G-A. For the **absent**-file case 04
takes the union of the two triggers (any registered pack `regulated ∋ hipaa`, **or** the slug
`otherapp` registered; a pack that does not load counts as hipaa); unreadable, unparseable or
schema-invalid is always `PHI_UNREADABLE`. Please rewrite 03 §3.20's hook-reader paragraph to cite
00 §1.2 and 04 §4 `phi_denylist` (the sentinel `PHI_UNREADABLE`), or have 00 §1.2 adopt 03's
narrower roots — one rule, stated once. 04 also adds `url_prefixes` enforcement in all three hook
readers (`gtm_hooklib.phi_url_hit`), as R65 of `requests/03_schemas.md` and item 38 of
`requests/08_seats_wps.md` asked; 03's "G-A's `phi-host` rule … deny a match exactly as a host hit"
can now also name the path gate (WebFetch) and G-B rule j (URL tokens).

## R52 — 03_schemas.md §3.22 `system_names` (A1) and 05_approver.md §5.6
Add `APPROVER_KEYCHAIN_LITERALS: tuple[str, ...] = ("com.oversight.gtm.approver",
"signing-key-ed25519", "com.oversight.gtm.approver.signing")` — the fallback key's service and
account and the Secure Enclave key's application tag, exactly as 05 §5.6 names them — and have 05
cite it as the one definition. G-B rule f (04 §4.2) matches any `security` argv token containing a
member, so `security find-generic-password -a signing-key-ed25519 -w` is caught.

## R53 — 06_connectors.md runbook schema/validator; 03_schemas.md §3.6 and §3.21; plan §20 / 08 Appendix B (coordinator: amends R22)
04 §4.1 adds rule 7c ("NEVER and identity surfaces"). (a) 06: add the optional runbook key
`never_url_re: [{"host", "url_re", "surface", "identity_row": <row id>|null, "why"}]`; the
validator refuses a `host` outside `platform_hosts(system)`, an invalid `url_re`, an
`identity_row` that is not an identity-class row of the tier table, and — **required** — a runbook
for a system whose hosts offer business-portfolio, people/role, partner or asset-sharing screens
(at least `business.facebook.com`, `business.google.com`, `ads.google.com`, `analytics.google.com`,
`tagmanager.google.com`) that declares none; the committed entries are a plan §17 probe row. (b)
03 §3.6: copy the action's `row_id` onto every write ticket at mint (rule 7c's `identity_row`
comparison; a ticket without it never matches). (c) 03 §3.21: add isolation kind `never_surface`
and have `breakers.ingest_isolation_hits` treat it like `identity_other_company`. (d) Coordinator:
the R22 plan amendment and its Appendix B entry also state the NEVER/identity click residual 04
§4.1 names (a portfolio/people/asset-sharing control reachable by a click under a non-identity write
ticket on a page no `never_url_re` lists), so the operator's signed activation ruling covers both
residuals.

## R54 — 08_seats_wps.md §9 B1 and B2 rows (supersedes R1's G-W note)
(a) B1 row: `gtm_hooklib` imports stdlib, `_lib`, `company`, `system_names` **and `gtm_env`**
(00_global_paths.md §0.1/§1.1: hooks take the clock, the Agency root, `norm_text` and the
real-state refusal from it); B1 also delivers the library `hooks/gtm_import.py` (04 §4 hook import
rule). (b) R1's sentence "G-W verifies the trust-edit marker with `cryptography` and the HEAD key
directly" is withdrawn: G-W runs the isolated `approval_sig.py --verify-trust-edit` (04 §4.3,
`requests/05_approver.md` R38), and `activation_state` runs `approval_sig.py --verify-activation`
(R50); B1's G-W verification tests run against the real `approval_sig.py` once A2 has landed. (c)
Test labelling (04 §4.2 "Test labelling"): every G-B test that runs through `pretooluse_bash.py`
or `bash_gate.sh` is a **B2** test (after `b2_gb_wiring.patch` exists); B1 asserts the same cases
at `gtm_bash_gate.decision()` level (the full `(block, reason, message, unconditional)` tuple).
Please state this in both rows so B1 never needs the dispatcher.

## R55 — 02_act.md `purge-untrusted`; 07_notices_schedules.md §7.6 `gtm_session.sh`; 06_connectors.md runbook validator (HIPAA redaction)
04 §4.1 "HIPAA packs: no raw page text in G-A records" stores a HIPAA pack's G-A `element` and
URLs only as digests plus host and a path template in logs and audit rows, but must keep the
current page's path (redacted query and fragment) in `S/browser_hosts/<session>.json` for its rules.
(a) 02/07: add `S/browser_hosts/` files of a HIPAA-pack session and that home's
`ST/read_clicks.jsonl` to `purge-untrusted`'s scope and the plan §20.4 30-day purge. (b) 07:
`gtm_session.sh` deletes `S/browser_hosts/<its session id>.json` when `claude` exits (any exit
status). (c) 06: for a system in a HIPAA pack's `scope.channels_in_scope`, the validator refuses a
`read_click_targets[].url_re` or `never_url_re[].url_re` that depends on a non-id query value (G-A
matches the redacted form, in which such a value is a digest).

## R56 — 03_schemas.md §3.22 `system_names.TAG_RE`
Change the company group to `(?P<company>[a-z][a-z0-9-]{1,31})` — exactly `company.SLUG_RE`'s
grammar (00_global_paths.md §0.3) — instead of `[a-z0-9][a-z0-9-]{1,39}`. gate-gtm re-checks the
slug against `gtm_slugs()` either way; the alignment removes a divergence the reviewers flagged and
makes the hooks-local `_TAG_RE` copy in `pretooluse_task.py` (04 §4.6) exact.

## R57 — 03_schemas.md §3.22 `system_names` (A1); `harvest_tool_trail.py` owner
Add `PAGE_URL_RE = re.compile(r"-\s*Page URL:\s*(\S+)")` and `extract_page_url(text) -> str | None`
returning the **last** match (several `Page URL:` lines occur when a call changes pages; the last is
the current page). G-A's PostToolUse refresh (04 §4.1) uses it through `gtm_hooklib.page_url`.
`harvest_tool_trail.extract_page_url` today returns the **first** match; please make it import
`system_names.extract_page_url` (or add a parity test and switch it to last-match), so the
activity log and G-A never record different URLs for the same result.

## R58 — 02_act.md §2.4 `ticket` vs 03_schemas.md §3.6 (`upload_assets[].path` form)
02 §2.4 calls the bound copy "home-relative" (`ST/assets/<action_id>/<sha256>`); 03 §3.6 says
`path` = `realpath(ST/assets/<action_id>/<sha256>)` (absolute). 04 §4.1 rule 11 accepts both
(`canon(e.path, H)`) and additionally requires the entry to be directly under
`ST/assets/<ticket action id>/` with basename `e.sha256`. Please make 02 and 03 say the same form
(03's absolute form is what the gtm-operator passes to `browser_file_upload`).

## R59 — 03_schemas.md §3.13 admission row; 05_approver.md §5.5 step 0; 07_notices_schedules.md (trust-failure lead capture)
04 §4.6 now admits the plan §6.8 lead-capture allowance on gate-gtm's trust-failure path with
stdlib code only (as 05 §5.5 step 0 and R54/R67 ask). (a) 03 §3.13: the admission row gains
`seat_row` (bool; 04 §4.6 "Counting" already requires it) and the optional `trust_fallback` (bool,
true only for a row written by that stdlib path); `dispatch_tags.count_dispatches` counts both
kinds alike. (b) 05 §5.5 step 0 / its trust-drift list: gate-gtm writes **no** `PAUSE.budget`,
`budget` or `trust` notice on the trust-failure path (it imports nothing there); the operator
signal is act.py's step-0 trust notice plus the daily check's `S/PAUSE.trust`. Please make 05's
"gate-gtm puts every company in forged budget state" read "gate-gtm denies every enforced dispatch
except the lead-capture allowance, and writes nothing". (c) 07: any notice text that promises a
`PAUSE.budget` after a trust drift should instead say dispatches resume when the tree matches HEAD.

## R60 — 00_global_paths.md §0.4 unconditional list and §1.2 "OtherCompany read scope"
(a) §0.4: list the new unconditional GTM-scope denials — path gate `phi-scope-outside-allowed` and
`phi-denylist-unreadable`, G-B rule j's clauses of the same names, G-A rule 7c `never-surface`. (b)
§1.2 "OtherCompany read scope" says G-B rule j uses "the same operand grammar as rule j": 04 §4.2 rule
j now defines that grammar ("Operands", items (i)–(vi) plus URL tokens); please cite it there.

## R64 — 05_approver.md §5.5 step 0 (3) and §5.1 step 5 (applies open request R77, wave1d fixes)
Filed while resolving wave1d finding r3(8), which found `05_approver.md` open request R77 neither
applied nor rejected and `04_hooks.md` contradicting it in three places. `04_hooks.md`'s side is now
fixed (§4 "Isolated subprocesses", rule m, `ticket_cancelled`); this request asks 05 to match:
(a) **Shared tmp root — WITHDRAWN (wave1e), finding wave1d-B2.** The `Path(tempfile.gettempdir()).resolve()
/ "gtm_isolated"` root this item asked 05 to adopt was wrong: 05 §5.5 step 0 (3) requires
`realpath(dirname(P)) == _gtm_tmp_root()` = `realpath(TMPDIR or "/tmp")` (R80 (d), R77 (c)), so a
prefix one level down under `gtm_isolated/` fails that check and every isolated child exits 11
`trust_interpreter`. 04 now adopts 05's body exactly: `gtm_env.gtm_tmp_root()` = 05's
`_gtm_tmp_root()` body (exported by 00 §1.1), and every `<fresh P>` is created **directly** under
it (04 §4 "Isolated subprocesses"). 05 needs no change for this item; its "same defined quantity"
requirement is met from 04's side.
(b) **Cancel marker `who` exclusion (rewritten wave1e, finding wave1d-M4).** `04_hooks.md`'s
`ticket_cancelled` now applies R77 (a) exactly: for a ticket whose pre-lock rule-7a verification
reports `signed_required: true` (a money row or signed-revert child), only a marker whose parsed
`who` is exactly `operator_script` or `approver_menu` cancels it; every other `who` — `agent`,
`card_deny`, `hand_made_file` (incl. an empty file, 03 §3.11), `system:responded_by`, and any
unknown, misspelled, absent or unparseable value (05 §5.1 step 5's *agent-class*, R86) — does not.
G-A runs that pre-lock verification also for a non-mutating call of a bound ticket whenever a
cancel marker (per-action or `_all.*`) could apply to the candidate, so the result exists whenever
the filter matters; `ticket_cancelled` never calls `verify_ticket` itself (it runs under
`tickets_lock`). When `verify_ticket` raised, or the ticket re-selected under the lock is not the
one verified, the filter is not applied (every marker cancels: fail closed toward "cancelled"; a raising verification is
also a rule-7a deny for a mutating call). 05 §5.1 step 5 already states the same classes on the
ingest side; no 05 change is asked beyond confirming it cites 04's ticket-side rule.
