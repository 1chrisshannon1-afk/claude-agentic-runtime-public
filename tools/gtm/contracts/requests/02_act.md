# Change requests from `02_act.md` (§2 act package) to other contract files

Raised while resolving the `02_act.md` findings in `OPEN_FINDINGS.md`. Each item names the target
file and section and the exact change. The `02_act.md` side of each is already written; the section
named there is cited in brackets.

## 00_global_paths.md

1. **§1.2 `S` layout** — add rows:
   - `operator_ok/<command>.<slug>.json` · operator (terminal only, `tools/gtm/operator_ok.sh`) · 02_act.md §2.3 · single-use operator marker for `resume`/`autonomy`/`pause` (IMP-03/FID-06)
   - `operator_ok.lock` · act.py · 02_act.md §2.3
   - `agent_results.jsonl` (+ `agent_results.lock`) · `hooks/gtm_ticket_release.py` (SubagentStop) · 02_act.md §2.7(c) · `{agent_id, agent_type, block_sha256|null, ts}` (FID-08)
   - `transcript_index_oi.jsonl` · WP-G `transcript_index.py` · 03_schemas.md §3.16 · operator-input side index (IMP-09)
2. **§1.3 per-home layout** — under `state/` add `patches/<action_id>.patch   act.py propose (website_static)   02_act.md §2.4` (FID-04).
3. **§1.4** — add one sentence: "No TTY or environment test means 'operator terminal' anywhere; the operator's authority for `resume`/`autonomy`/`pause` is the single-use `S/operator_ok/` marker (02_act.md §2.3). An inline `CLAUDE_GTM_*=` assignment in an agent command naming `act.py` is denied by G-B (04_hooks.md §4.2)." (IMP-03)

## 03_schemas.md

4. **§3.1 / §3.3 events and fold (FID-01, FID-04)** — event names gain `card_denied` and `deployed` (both already in the 02_act.md §2.2b event table and §2.5); `card_recorded.data` gains `decision` and `subject`; the folded record's `card` block gains `decision` and `subject`, and the record gains `deployed: {"commit", "at"} | null`.
5. **§3.2 proposal (FID-04)** — replace the `website_static` bullet with: "`website_static` rows only: `after` = `{paths, summary, patch_sha256, post_image}`; `paths` = the repo-relative paths the stored patch touches; `patch_sha256` and `post_image` (`{path: git blob sha | null}`) are computed by `propose` from `--patch` (02_act.md §2.4) and refused `patch_mismatch` when supplied and different."
6. **§3.4.1 / §3.4.4 (FID-02)** — add a per-row `id_fields` list (the `after.value`/`before.value` keys holding platform ids or URLs: `target_id`, `list_id`, `level_id`, `campaign_id`, `ad_group_id`, `listing_url`, `page_ref`, …) to the row schema and to every row that carries one (at least `*.asset_link`, `*.user_add`, `*.user_role_edit`, `L.claim_submit`, and every `google_ads` row naming a campaign/ad group); the tier-table validator refuses an `id_fields` entry not in `after_value_fields`.
7. **§3.4.4 `website_static.page_edit` (FID-04)** — `after_fields` = `paths, summary, patch_sha256, post_image`.
8. **§3.4.4 (FID-09)** — set `public: true` on `google_ads.ad_create@paused`, `google_ads.ad_text_edit@paused` and every `google_ads.asset_*@paused` row (public lane set; 02_act.md §2.7 names them). If the 03 owner chooses the alternative (authorize of `google_ads.campaign_enable` refuses `unreviewed_public_assets`), tell 02's owner so §2.7's parenthetical is changed instead.
9. **§3.10 (IMP-03, FID-11)** — replace every "operator terminal" with "a valid operator marker `S/operator_ok/…` (02_act.md §2.3)"; add: "a breaker pause (`created_by: breaker`, `ruling_ref: null`) is also removed by `autonomy_ladder.py promote` (02_act.md §2.9)"; `created_by: "operator"` is written only when a `pause` operator marker is consumed.
10. **§3.14 lead sink (FID-19, FID-07)** — pack key `lead_sink.baa_ref` (string, required non-empty for `regulated ∋ hipaa` packs before any sink write; schema follow-up in 08 Appendix C); without it `lead-append` writes only to `ST/untrusted/` (02_act.md §2.4). `fallback_reason` enum = `"trust" | "chain" | "pack"` (`pack` rows replay exactly like `trust` rows, 02_act.md §2.3).
11. **§3.16 transcript index (IMP-09)** — add the operator-input side index `S/transcript_index_oi.jsonl`: `refresh()` appends, incrementally from each file's last indexed byte offset, one line `{file, offset, ts, session_id, agent_id, tool, target_realpath}` per `Write`/`Edit`/`MultiEdit`/`NotebookEdit`/`Bash` tool_use whose input names the basename or realpath of any GTM home's operator-input file (Agency project dirs skipped); expose `operator_input_hits(since_ts) -> list[dict]`; state the incremental-cost budget and that the initial build runs outside every lock.
12. **§3.17 (IMP-03, FID-01, FID-11)** — `decided_by` enum `"criteria" | "operator_ok" | "card:<id>"`; (ii) "a valid `S/operator_ok/autonomy.<slug>.json` marker"; (iii) "a card passing `cards.require_approved(ctx, card_id, "autonomy <slug> autonomous")`" (not "contains `autonomous`"). `promote`: also removes the system's breaker pause (created_by `breaker`, `ruling_ref` null) via `gtmlib.pauses.remove_pause`, appends a `resume` event `lifted_via: "ladder_promote"`, writes the `info` notice **with push**; a clean day = ≥ 1 `verified` pass or a `snapshot_recorded` of that system and no `verify_failed`/isolation hit/breaker on it (02_act.md §2.9).
13. **§3.19 validate_run (IMP-18)** — `activity_log_error` values starting `activity_log_render_error:` count as logged (an `activity_log_id` exists), never as `activity_log_failed`.
14. **§3.22 system names (FID-02)** — add per-system `platform_hosts(system) -> set[str]` and `target_ids(system, target_ref) -> list[str]` (per-system capture regexes; a system with patterns must yield ≥ 1 id), both in `system_names.py`, used by 02_act.md §2.8 check 1(b)/(c).
15. **§3.23 outside_actor classify (FID-01)** — replace "answered card per 02_act.md §2.6" with "a card passing `cards.require_approved(ctx, card_id, "classify <entry id> <as>")`" (posted with `card-post --subject "classify <entry id> <as>"`).

## 04_hooks.md

16. **§4.2 G-B (IMP-03/FID-06)** — rule k: add the literal `operator_ok`. New rule (all sessions): a command naming `act.py` that contains an inline assignment of any `CLAUDE_GTM_*` variable, `env … CLAUDE_GTM_*=`, `env -u CLAUDE_GTM_*`, `export CLAUDE_GTM_*`, or `unset CLAUDE_GTM_*` → deny `gtm-identity-forgery`. B1 falsification test: `CLAUDE_GTM_COMPANY=x python3 …/act.py propose …` from a non-GTM session is denied.
17. **§4.2 rule c / §4.3 G-W (FID-08)** — in GTM scope add `R/projects/**/*.jsonl` (every transcript) to the protected/deny set (`machine-written-path`).
18. **§4.3 G-W (FID-07)** — in GTM scope deny Write/Edit on every GTM home's `.claude/gtm/company.json`, `review_lanes.local.json` and `connectors.json` (`pack-via-reviewed-session`); pack edits happen in a non-GTM, reviewed session.
19. **§4.5 ticket release (FID-08)** — on every SubagentStop, append `{agent_id, agent_type, block_sha256, ts}` to `S/agent_results.jsonl` under `S/agent_results.lock`, where `block_sha256 = sha256(canon(block))` of `gtm_result.extract_gtm_result`'s parse of `last_assistant_message` (null when it carries none). Hooks may import `gtm_result` (02_act.md §2.1).
20. **§4.6 gate-gtm and every hook reading a pack (FID-07)** — load the pack from `git -C <H> show HEAD:.claude/gtm/company.json`, never the working tree.
21. **§4.7 fast path** — add tokens `operator_ok` and `CLAUDE_GTM_`.

## 06_connectors.md

22. **§6.2 (FID-02)** — state: "`plan()`/`apply()` resolve the platform object only from `ctx.account` plus the ids check 1 verified (`id_fields` values and `system_names.target_ids`), never from free `target_ref` text."
23. **§6.2 idempotency (IMP-11)** — state: "Only results with `ok: true` (or a platform side effect) are recorded under `idempotency_key` (= `action_id`); a repeat returns a recorded success only, so an action that failed with a retryable error and is re-authorized makes a fresh platform call." L test: a retryable failure followed by a successful retry ends with one platform write.

## 07_notices_schedules.md

24. **§7.5 (IMP-12)** — no edit required for `ticket --close <ticket_id>`, `ticket --write <id>`, `ticket --write-batch <ids>`: `ticket` now resolves the company from the id (02_act.md §2.4 ticket row); `ticket --read` keeps `--company`. `test_k_prompts.py` should assert `--company` on `ticket --read` only.
25. **§7.5 / §7.6 card posting (FID-01)** — every gating card is posted with `card-post --subject <token>` (02_act.md §2.6 `CARD_SUBJECT_RE`): shared-class actions (`--action` sets `authorize <id>`), revert children (`revert <child id>`), chain-repair (`chain_repair <slug>`), owner-listen (`owner_listen <sha256>`).
26. **§7.5 / §7.6 `website_static` (FID-04)** — the interactive step applies only the stored patch (`git apply --index <path from status --review-brief>`), commits through the repo gates, runs `complete --commit`, and after the operator's deploy go-ahead and deploy runs `record-external --kind deployed --action <id>`. D6: `verify` on a `website_static` action without `deployed` exits 4 `not_deployed` — expected, not a failure.
27. **§7.6 `/gtm-resume`, `/gtm-pause`, ending shadow (IMP-03)** — the operator path is: run `tools/gtm/operator_ok.sh <command> <slug> <target>` in the operator's own terminal, then `act.py resume|autonomy|pause …`; no TTY path exists.

## 08_seats_wps.md

28. **§8.1 (FID-08)** — `extract_gtm_result(agent_id, …)` compares `sha256(canon(block))` with the agent's `S/agent_results.jsonl` record: none → `agent_result_unrecorded` (retryable), different → `agent_result_mismatch`.
29. **§8.4 (FID-04)** — the review brief carries `patch` (the stored patch text) for `website_static` actions; web_page lane reviewers review the patch, not the summary.
30. **§9 WP table** — A1 also owns `tools/gtm/operator_ok.sh`; the coordinator owns `tools/gtm/project_dirs.py` (item 33).
31. **Appendix B** — reword items 46, 61 and 92: "operator terminal" → "valid single-use `S/operator_ok/` marker (02_act.md §2.3)"; "an answered card" → "a card whose answer approves (decision grammar) and whose posted subject matches (02_act.md §2.6)". Add entries: (a) FID-01 card decision + subject grammar (02_act.md §2.6); (b) FID-02 check 1 positive allowlist with `card_on_refuse` (02_act.md §2.8); (c) FID-04 `website_static` patch binding, `post_image` check, `deployed` event (02_act.md §2.4); (d) FID-11 Option A: `promote` lifts breaker pauses after 7 clean days, clean day defined (02_act.md §2.9); (e) FID-21: `hipaa_prohibited` rows re-enable only by a reviewed `tier_table.json` change citing the KB claim and an approving operator card (02_act.md §2.8 check 5); (f) IMP-03: operator marker replaces the TTY test.
32. **Appendix C, new coordinator follow-up (FID-19)** — add optional `lead_sink.baa_ref` to `company_schema.json`/`company.py` (required non-empty when `regulated ∋ hipaa` and a sink is configured), with tests, before P1b.
33. **Appendix C, new coordinator follow-up (IMP-15)** — create `tools/gtm/project_dirs.py` (stdlib only: `_project_dir_name`, `project_dir_name_text`, `matches_project_dir_prefix`) and switch `harvest_tool_trail` to import from it, before Wave 2; test that `ai_budget` imports without pulling in `activity_log`.

## Round 2 — raised while resolving the second `02_act.md` review (2026-09-27)

Items below supersede the earlier item named in each, where they conflict.

### 00_global_paths.md

34. **§1.2 `S` layout (supersedes item 1's first and third rows).** The operator marker is
    `operator_ok/<command>.<slug>.<target>.json` (keyed by target so several lifts can be pending;
    02_act.md §2.3). The SubagentStop record `agent_results.jsonl` has the 08_seats_wps.md §8.1 shape
    `{ts, agent_id, agent_type, session_id, result_sha256}` (`result_sha256 = "sha256:" +
    sha256(canon(parse_block(last_assistant_message)))` or null), not `{…, block_sha256, …}`.
35. **§1.3 per-home `state/untrusted/`** — also holds `<unt_id>.txt` side-store texts for hipaa packs:
    `rationale`/`undo`, review `lines`, verify `observed`/`diff`, free-text failure reasons
    (02_act.md §2.2b "HIPAA side-store form"); same mode, purge and backup exclusion as today.

### 03_schemas.md

36. **§3.1 / §3.3 (FID-03)** — add event `ceiling_read` `{current_absolute_value, unit, currency,
    status, source: "api"|"snapshot", evidence_ref, read_at}` (02_act.md §2.2b, §2.6 rule 5a); the
    fold overwrites `before.value.current_absolute_value` and sets `before.value.unit` from the latest
    one. `would_execute.would_gate` enum becomes `none|hold|card` (money never enters shadow, 02 §2.6
    rule 6).
37. **§3.2 "Enable rows" (FID-03, 05 R9)** — state that the binding covers `commits_on_enable` rows
    **and** any effective-money action whose `action` ∈ {`enable`, `resume`, `unpause`}
    (`_nomatch` included); an amount-less one refuses `enable_amount_required`; the fresh read runs
    only while no approval request exists; the browser snapshot must be from this run (a
    `snapshot_recorded` event with the action's `run_id`) and ≤ 24 h old.
38. **§3.15 (F-PHI)** — the claim "nothing inbox-derived reaches actions.jsonl" now holds only with
    02_act.md §2.2b's side-store form: for hipaa packs `proposed.rationale`/`undo`, every
    `review.lines[]` entry, `verified`/`verify_failed` `observed`/`diff` on `inbox_reply`/`public`
    text rows, and `failed.reason` (a code; free text → `reason: "other"` + `reason_detail`
    `{digest, pointer}`) are stored as `{digest, pointer}`. Update §3.15's wording and its test.
39. **§3.16 transcript index (supersedes item 11, which 03 already implements)** — add
    `files_modified_between(t0: datetime, t1: datetime) -> list[Path]` (paths from
    `transcript_index.json["files"]` with `t0 ≤ mtime ≤ t1`, Agency dirs excluded as for `refresh`),
    used by 02_act.md §2.11's trail harvest; state that the current session's transcript is
    `lookup_session(session_id)["path"]`.
40. **§3.22 system names** — (a) add `NON_INBOX_SNAPSHOTS: dict[str, frozenset[str]]`, the fixed
    allowlist of `(tier system, snapshot name)` classes that may go to `paths.snapshots_dir` on a
    hipaa pack (02_act.md §2.4 `snapshot`; e.g. `gbp`: hours, categories, services, attributes,
    committed_ceiling; `google_ads`/`meta`: metrics, campaigns, committed_ceiling; `ga4`: metrics;
    `search_console`: metrics, sitemaps); an A1 validator test refuses an entry matching
    `INBOX_CLASS_RE`. (b) `INBOX_CLASS_RE` moves into `system_names` (06 §6.3 still uses it).
    (c) Check 1(c) (02_act.md §2.8) now requires, for a system with **no** target-id pattern, that
    `target_ref` exactly equal an `identity_allowlist.listing_urls` entry or be on a brand domain; say
    so beside `target_ids`, and add a tier-table validator note that every system with a write row
    either has id patterns or is a listing-only system whose packs list `listing_urls`.
41. **§3.6 write ticket `upload_assets`** — every entry must pass `checks.asset_path_ok`
    (02_act.md §2.8 check 4; refuse `asset_path_forbidden`) before the ticket is minted.
42. **§3.4.1 (supersedes item 6, which 03 already implements as the kind map)** — no change; 02 §2.8
    check 1(d) now judges `id_fields` by kind (`identity`/`email`/`listing`/`in_account`).
43. **§3.10 / §3.17** — "operator marker" paths use the `<command>.<slug>.<target>.json` naming
    (item 34).

### 04_hooks.md

44. **§4.2 rule k (supersedes the first half of item 16) — the literal is `operator_ok`, not
    `operator_ack`.** Replace `operator_ack` with `operator_ok` in rule k's literal list and in its
    B1 test (`python3 -c "open('…/operator_ok/resume.x.PAUSE.json','w')"` denied; `bash
    <R>/tools/gtm/operator_ok.sh resume x PAUSE` from an agent denied). Add a B1 falsification test
    that goes RED when `operator_ok` is dropped from the list. Until this lands, agents can forge the
    operator marker (02_act.md §2.3).
45. **§4.2 new rule l `gtm-identity-forge` (supersedes the second half of item 16; name aligned).**
    All sessions: a segment naming `act.py` with an inline `CLAUDE_GTM_*=` assignment (incl. one
    `_strip_prefix` removed), `env [-i] … CLAUDE_GTM_*=`, `env -u CLAUDE_GTM_*`, `export`/`unset`/
    `declare -x`/`typeset -x` of a `CLAUDE_GTM_*` variable → deny `gtm-identity-forge`. P2 test
    through `bash_gate.sh` → `pretooluse_bash.py`: `CLAUDE_GTM_COMPANY=x python3 …/act.py propose …`
    denied. Add `CLAUDE_GTM_` and `operator_ok` to the §4.7 fast-path tokens (item 21).
46. **§4.5 result record (supersedes item 19) — align with 08_seats_wps.md §8.1, the canonical
    definition.** Field `result_sha256` (not `sha256`) = `"sha256:" + sha256(canon(
    gtm_result.parse_block(last_assistant_message)))` — the parsed, canonicalized block, **not** the
    raw message bytes — or `null` when `parse_block` returns `None`; row `{"ts", "agent_id",
    "agent_type", "session_id", "result_sha256"}`; written on every stop whose message carries a
    ` ```gtm-result ` fence, in any session. The hook imports only `gtm_result.parse_block` and
    `gtm_result.canon`. Update the B1 tests accordingly.

### 05_approver.md

47. **No change requested; confirmation.** 02_act.md §2.3 now uses `trust_root_ok(...) -> (ok,
    entries)`, `write_trust_notice(S, entries, created_by="act")` (one dedupe formula), the failing
    `TRUST_KINDS` member as `error.code`, and never writes `PAUSE.trust` at dispatch (R11 (c)–(e)
    adopted); it cites TRUST_PATHS as the whole `tools/gtm/` subtree (covers `gtm_result.py`,
    `provenance.py`, `project_dirs.py`). §2.6 rule 5a implements R3 and R9 (`enable_value_mismatch`,
    `enable_amount_required`, `ceiling_unreadable`). R11 (a)/(b)/(f) (import order, lead spool,
    re-exec) are not yet reflected in 02 and remain open against it.

### 06_connectors.md

48. **§6.2 fresh read at authorize** — state that `authorize` calls `read_committed_ceiling` only
    while no approval request exists for the action (02_act.md §2.6 rule 5a), and that the browser
    snapshot must additionally be from the authorizing run (`snapshot_recorded.run_id == ctx.run_id`).

### 07_notices_schedules.md

49. **§7.2 interpreter pin (IMP; 02_act.md §2.1 "Interpreter")** — `run_gtm_job.sh` and every
    plist/job script invoke GTM tools with an absolute interpreter path ≥ 3.11 (resolved once at
    install, recorded in the job's config), never a bare `python3` that a minimal launchd `PATH`
    resolves to `/usr/bin/python3` (3.9.6). act.py exits 1 `python_too_old` otherwise.
50. **§7.5 / §7.6** — `ticket --write` and `execute` may exit 3 `quiet_hours`/`sms_window_closed`
    with the action still `authorized`; prompts treat it as "retry next run", not a failure
    (FID-24). `card-post --action` now renders a machine block and refuses a subject not equal to
    `authorize <action>`/`revert <action>` (`card_subject_action_mismatch`).

### 08_seats_wps.md

51. **§8.1 (supersedes item 28)** — no change: 02_act.md §2.7(c) now cites §8.1 as the one
    definition (`extract_gtm_result(transcript_path)`, `result_sha256`, `gtm_result_unreadable`).
    Add: `gtm_result` imports `transcript_index` lazily inside `verify_reviewer`/`verify_verifier`
    only.
52. **Item 33 (IMP-15) naming** — `project_dirs.py` exports the public `project_dir_name` (the name
    03 §3.16 and 04 use) plus `project_dir_name_text` and `matches_project_dir_prefix`; keep
    `_project_dir_name = project_dir_name` as an alias only for `harvest_tool_trail`.
53. **Appendix B — new DECIDED HERE entries (02_act.md):** (a) money never enters shadow — every
    `money` action goes to the approval path at every autonomy level, per plan §20.6 "never applies
    to `$`" and ruling [122] (§2.6 rule 6; replaces the earlier shadow suppression of non-urgent
    `$`); (b) §2.6 rule 5a enable-ceiling fresh read (FID-03); (c) `required_lanes` rules 2 and 5
    (`nomatch` set on asset-bearing money proposals; `cta_link` on `_nomatch`) (FID-05); (d) check 1
    fail-closed: `account_id` bound to system+brand, listing-only systems require exact
    `listing_urls`, `id_fields` judged by kind (FID-02); (e) asset path containment
    `asset_path_forbidden` (check 4); (f) hipaa snapshot routing inverted to a non-inbox allowlist;
    (g) HIPAA side-store form for `actions.jsonl` free text (§2.2b); (h) card-post subject/action
    binding and machine block; (i) `revert` of `website_static` refused `revert_not_supported`;
    (j) trail-conflict check limited to owner kinds; (k) interpreter floor 3.11 and portable
    `glob_full_match`; (l) exhaustive exit-code map (§2.4).
54. **Appendix C (coordinator)** — `tools/gtm/tests/gtm_fixtures.py` needs a fixture home nested one
    level below its repo toplevel (02_act.md §2.2 `HEAD:./` test) and sibling packs with committed
    identity values (check 2 HEAD-sibling test).

## Round 3 — incoming requests applied in `02_act.md` (2026-09-27)

Applied in 02 this round: `requests/00_global_paths.md` R9 and R11; `requests/03_schemas.md` R1, R2
(check 1(d) now defers to §3.4.1 "Kinds" in full), R3, R6 (list sends), R7, R8, R9, R10;
`requests/04_hooks.md` R8, R9; `requests/05_approver.md` R11 (a)–(g), R16, R17, R18;
`requests/06_connectors.md` R2, R4, R9; `requests/07_notices_schedules.md` R1, R10, R11, R15;
`requests/08_seats_wps.md` §10, §15. Items below supersede the earlier item named in each.

### 00_global_paths.md

55. **§1.4 (supersedes the name in item 45).** 02 §2.3 now adopts 00's `gtm-env-override` (R12) as
    the one G-B rule for inline `CLAUDE_GTM_*`/`CLAUDE_DIR`/`GTM_TEST`/`GTM_FAKE_NOW`/`HOME`
    overrides; the name `gtm-identity-forge` (item 45) is withdrawn. 02 states the proof does not
    rely on it.
56. **§1.4 "GTM-session proof" API.** Add the read-only
    `gtmlib.session.operator_ok_valid(slug, command, target) -> bool` beside `consume_operator_ok`
    (02 §2.2b): dispatch's exception (2) runs before `make_ctx`, so it needs a check that neither
    consumes nor needs a `Ctx`.
57. **§1.4 "Operator authority" marker path (repeats item 34, still open).** 02 §2.3 owns the
    design and keys the file by target: `S/operator_ok/<command>.<slug>.<target>.json`
    (e.g. `resume.other-company.PAUSE.website_wordpress@remodeling.json`). §1.4's
    `<command>.<slug>.json` and its example path must match.

### 03_schemas.md

58. **§3.4.1 "Kinds" heading.** "02_act.md §2.8 check 1(d)/(e)" → "02_act.md §2.8 check 1(d)"
    (02's (e) now only notes that `user_*` addresses are `email`-kind `id_fields`).
59. **§3.22 `account_keys(tier_system, account) -> dict[str, str]`** (06 R1 item 8) must be listed
    in the `system_names` API block: 02 §2.8 check 1(c) compares every account-level key of
    `target_ids` with it (the key set of 06 §6.2 step 2), and judges every other key as `in_account`
    — a campaign/ad-group id inside `target_ref` is not an `OWN` value and must not be tested as one.
60. **§3.14.** Trust-failure leads now go first to `S/lead_spool/<ts>_<hex>.json` (05 §5.5 step 0,
    02 §2.3); the first trusted `lead-append` moves them into `ST/lead_fallback.jsonl` with
    `fallback_reason: "trust"`. The BAA-held row is `ST/untrusted/<unt_id>.lead.json` (R9 applied).

### 04_hooks.md

61. **§4.5 result record (amends item 46).** The hook imports `gtm_result.parse_block` and
    `gtm_result.result_sha256` (08 §8.1), not `canon`; the row is written on every SubagentStop whose
    message holds an opening-fence line, in any session.

### 05_approver.md

62. **Confirmation.** 02 §2.3 "Step 0" restates §5.5 step 0 (isolated re-exec, `trust_root_ok`
    before any other `tools/gtm` import, every subcommand, exit 11, `lead-append` spool, never
    `PAUSE.trust`, `key_not_installed` exit 11 for `$` only); §2.11 implements §5.1 step 5 (mirrored
    `$` card: deny only; approve → `approver_inbox/show.<request_id>` + info notice); §2.4
    `purge-untrusted` implements R16(a); §2.6 rule 7 R16(b); §2.8 check 8 R18. Please state in §5.5
    step 0 which field of a spooled lead names its company (02 assumes the row's `company`).

### 08_seats_wps.md

63. **§9 A1 row** — add `tools/gtm/gtm_env.py` and `gtmlib/session.py` `operator_ok_valid`;
    **A2 row** — add `tools/gtm/ed25519_verify.py` and `approval_sig.py`'s step-0 CLI surface
    (05 R11(g)).
64. **Appendix B — new DECIDED HERE entries (02_act.md):** (a) §2.3 step 0: trust root before any
    gtmlib import, every subcommand, lead spool (replaces the write/lead/repair-only placement);
    (b) §2.3 admission by `prove_gtm_session`/`prove_holds_job`, never a bare env test; test-mode
    refusals `root_mismatch`/`test_mode_real_state` after `make_ctx`; (c) §2.8 check 1(c) splits
    `target_ids` into account-level keys (bound to the matched account) and `in_account` keys;
    check 1(d) defers to 03 §3.4.1 kinds; (d) §2.11 mirrored `$` card can only deny; (e) §2.4
    `ingest-findings` `signin_missing` notices + resolution and `malformed_findings`; (f)
    `not_agent_executable` at `ticket --write`/`execute`, `owner_executed` the only completion path;
    (g) hipaa `drafts/` delete-on-read and 24 h purge; `purge-untrusted` transcript `cwd` rule;
    (h) `ticket --close` idempotent on terminal tickets, setup-ticket close runs `secret_sink scan`.

## Round 4 — raised while resolving the fourth `02_act.md` review (2026-09-27)

Items below supersede the earlier item named in each, where they conflict. Item numbers 67–74 are
cited from `02_act.md` by number.

65. **Applied in 02 this round (confirmation to the requesting files).** `requests/03_schemas.md`
    R22 (§2.2b `hipaa_free_text` for `money_brief`/`why`), R23 (§2.6 rule 5a and §2.8 check 8 scope:
    `commits_on_enable` rows plus `_nomatch` enable/resume/unpause), R25 (effective `data_flow`,
    `checks.content_data_flow`, `TRACKER_HOSTS`, the `measurement` lane), R26 (b)/(c) (host-less
    grammar forms, `target_ref: null ok` systems), R31 (`outward`), R32 (`requested_via`,
    `pause --self --run`, the narrowed `lift_requirement`); `requests/00_global_paths.md` R24
    (`marketing_code_paths`, `price_source_missing`, `agency_boundary`); `requests/06_connectors.md`
    R15 (the enable scope); `requests/07_notices_schedules.md` R30 (`card_id_exists`).
66. **03_schemas.md — remove the "02 does not yet…" notes.** §3.2 "Enable actions" ("requests R23 asks
    02 … to narrow to it"), §3.4.1 `outward` ("02_act.md §2.7 still keys both on `row.public` alone —
    R31") and §3.10 `requested_via` ("02_act.md §2.4 … do not carry `requested_via` yet — R32") are
    now false; 02 implements all three. Also: 02 renames its rule-3 code `reviews_incomplete` to
    03's `review_missing` (§2.6 rule 3, exit 3), so §3.4.4/§3.5's tests need no change.
67. **04_hooks.md §4 `gtm_hooklib` and 00_global_paths.md §0.1 — `agency_root()`/`phi1_root()` live in
    `tools/gtm/gtm_env.py`.** gtmlib may not import hooks and hooks may not import gtmlib, and
    `company.py` has neither function, so 02 §2.1 makes `gtm_env` (stdlib only, importable by both)
    the one definition with 04's semantics (`Path.home()/"Desktop"/"Agency"` and
    `Path.home()/"Desktop"/"OtherCompany Files"`, resolved at call time, root side of 00 §0.1's
    `norm`, never stat'd). 04: `gtm_hooklib` re-exports them (`from gtm_env import agency_root,
    phi1_root`) instead of defining them; B1 parity test `gtm_hooklib.agency_root is
    gtm_env.agency_root` (and `phi1_root`). 00 §0.1 L80: "`agency_root()` (04_hooks.md §4)" →
    "`gtm_env.agency_root()` (02_act.md §2.1; re-exported by 04's `gtm_hooklib`)".
68. **05_approver.md §5.5/§5.6 — expose the stdlib notice writer.** Add
    `approval_sig.write_urgent_notice(S, slug, kind, title, body, dedupe_key) -> str` (the writer
    `write_trust_notice` is built on: create-exclusive, urgent, push, dedupe by key), so act.py's
    step-0 `ingest-findings` fallback (02 §2.3) can push `runaway_spend` / `phi_encountered` notices
    without importing gtmlib or `notices`. Also confirm the pre-check set is `approval_sig` +
    `gtm_env` (02 §2.3 step 0 (iii) now says so), and that 02 settles `approval_expiring` at exit 3
    (your §5.5 step 5).
69. **04_hooks.md §4.1 rule 6b — step-0 pause spool.** While any `S/pause_spool/*.json` names the
    ticket's company (field `company`), treat that company as under a company-wide `PAUSE` at every
    write/batch/setup-ticket tool call (fail closed: an unreadable spool file counts). act.py's
    stdlib `pause` fallback writes it while every act.py command exits 11 (02 §2.3), and the first
    trusted command replays it into `ST/PAUSE…` and deletes it. B1 test: a spool file for company x
    denies x's next write-ticket browser call and not y's.
70. **08_seats_wps.md Appendix C item 5 (backup exclusions) and 00_global_paths.md §1.2 `S` layout.**
    Add `S/lead_spool/`, `S/findings_spool/`, `S/pause_spool/` (writer: act.py step-0 fallback, mode
    0600; reader: `gtmlib.spools.replay`, own company only; purged by `purge-untrusted` after N days
    when unreplayable) to the `S` layout and to the backup exclusions.
71. **00_global_paths.md / 04_hooks.md §4.2 — rules l and m (supersedes item 55; restores item 45's
    name).** 02 §2.3 now adopts 00's split exactly: rule l `gtm-identity-forge` (`CLAUDE_GTM_*`,
    segments naming `act.py`) and rule m `gtm-env-override` (`CLAUDE_DIR`, `GTM_TEST`,
    `GTM_FAKE_NOW`, `HOME`, segments naming `tools/gtm/`, pytest exempt). The names
    `gtm-identity-forgery` (item 16) and item 55's single-rule `gtm-env-override` are retired.
72. **03_schemas.md §3.6 and §3.7 (L886, L974) — `approval_expiring` is exit 3,** not exit 7, per
    05_approver.md §5.5 step 5 (the approval is valid, only too near expiry); 02's exit map settles
    it there.
73. **03_schemas.md pack schema + 08_seats_wps.md Appendix C (coordinator follow-up) — optional
    `rate_caps`.** Plan §6.6 takes rate caps "per system from `company.json`". Add optional
    `rate_caps: {"gbp_posts_7d", "social_posts_7d", "website_batches_day"}` (positive ints; absent =
    02 §2.8 check 6's defaults 3 / 3 / 1) to `company_schema.json`/`company.validate_company`, with a
    test, before P1b.
74. **08_seats_wps.md Appendix C item 13 — split the never-list.** State that
    `MARKETING_PATH_NEVER` = `NEVER_CODE ∪ NEVER_FIXED` (02 §2.8 check 9): `NEVER_CODE` (`*.js`,
    `*.mjs`, `*.cjs`, `*.jsx`, `*.ts`, `*.tsx`, `*.py`, `*.sh`, `package*.json`, `build*`,
    `*.config.*`, plus 00 §0.1's lock/build files and `**/.github/**`) is lifted only by an exact
    `marketing_code_paths` entry (00 §0.1); `NEVER_FIXED` (`*tracking*`, `*pixel*`, `*consent*`,
    `*gtm*`, `*ga4*`, `*analytics*`, `head.html`, `*test*`, `*spec*`, `**/scripts/**`, `deploy*`)
    and the tracking-content rule are never lifted. Replace "whatever the pack says" with that
    sentence, and add the A1 tests `build.mjs` listed → allowed, `deploy.mjs`/`tracking.js` listed →
    still refused.
75. **03_schemas.md §3.11 — late cancels.** A cancel marker ingested for a `ticketed` action sets the
    ticket `stopped` and appends `cancel_late {who, ticket_id, calls_used}`; `calls_used == 0` →
    action `cancelled` (nonce released), else it stays `ticketed` until `complete` and a
    `cancel_too_late` notice is written (02 §2.4 `cancel`, §2.5). `execute` and `run-holds`
    re-ingest the action's marker immediately before each connector call (plan §20.7; 02 §2.4). Add
    `cancel_late` to §3.1's event list and the fold (§3.3). The send-time re-check (FID-24) now
    also re-reads SMS consent (`sms_consent_incomplete`, exit 3) and applies the `responded_by`
    auto-cancel at `ticket --write` and `execute`.
76. **07_notices_schedules.md §7.1 notice kinds and §7.5/§7.6 prompts.** (a) Add kinds
    `cancel_too_late` (warn, push) and `phi_encountered` (urgent, push; written only by act.py's
    step-0 fallback, dedupe `phi_fallback:<agent_id>:<finding id>`). (b) `/gtm-pause` runs `act.py
    pause` with **no** `--self` (it writes `requested_via: "skill"`, which a later session cannot
    lift without the operator marker or an approving `resume <pause>` card); a session pausing its
    own run uses `pause --self --run <its cycle id>`. (c) `ticket --write`/`execute` exit 3
    `sms_consent_incomplete` and `approval_expiring` are "do not retry blindly": the first needs new
    consent, the second a fresh approval. (d) Card answers: prompts ask the operator to answer
    gating cards with a plain "Yes" / "No" — any condition ("Yes except …", "Yes, after Friday")
    reads `unclear` under 02 §2.6's closed approve grammar; the session splits the action instead.
77. **08_seats_wps.md Appendix C item 33 (project_dirs).** Add
    `transcript_cwd_under(path, home) -> bool | None` (fail closed: None when no `cwd` is readable)
    to `project_dirs.py`; drop the `_project_dir_name` alias and instead rewrite
    `harvest_tool_trail` to import `project_dir_name`/`matches_project_dir_prefix` (keeping thin
    private wrappers or updating `test_project_dir_name.py`); the harvester keeps its own fail-open
    `_transcript_cwd_is_under_home` for discovery (supersedes item 52's alias sentence).
78. **08_seats_wps.md Appendix B — revise and add DECIDED HERE entries (02_act.md).** Revise 53(j):
    the trail-conflict check now runs for `--kind approval` too, with the narrowed conflict set
    (02 §2.11; plan §6.1). Add: (a) `complete` has no pause check (03 §3.10 "Still allowed");
    (b) closed approve grammar for card answers, NFKC + apostrophe normalization (02 §2.6);
    (c) a review `fail` is sticky on its digest (02 §2.4 `review`); (d) `PAUSE.chain` presence
    refuses write-policy commands exit 10 even on a verifying chain (02 §2.3); (e) step-0 stdlib
    spools for `ingest-findings`/`pause`/`cancel`, replay own company only (02 §2.3); (f)
    `purge-untrusted` window ≥ 30 days and fail-closed transcript cwd test; purged side-index
    offsets count as hits (02 §2.4, §2.11); (g) `website_static` is never `money`
    (`money_not_static`); (h) `operator_input.path` and all pack files read from HEAD with
    `/usr/bin/git` and a timeout (02 §2.2); (i) `checks.other_business_hits` matching rules (02 §2.8
    check 2); (j) `agency_root`/`phi1_root` live in `gtm_env` (item 67).
79. **05_approver.md R11 / §5.5 step 0 (answers item 62's question).** 02 now replays only spooled
    leads whose `company` equals the trusted process's own slug (after grammar and `gtm_slugs()`
    checks), through the live BAA branch; 05 need not name the field beyond "the row's `company`".
80. **03_schemas.md §3.14 lead row.** Name the validation `lead-append` applies (02 §2.4 refuses
    `lead_invalid`, exit 3, `error.data.errors`) — the §3.14 required keys and types.

## Round 5 — signed operator marker landed in `02_act.md` (2026-09-27)

81. **Confirmation to `00_global_paths.md` (R29 applied in 02).** 02 §2.3 "Operator marker" now
    carries the signed `gtm.operator_ok.v1` form, checks (1)–(5) of 00 §1.4 (HEAD pem via
    `approval_sig.verify_raw`, canonical keys, fields, `now < expires ≤ now + 15 min`, nonce unused),
    nonce consume with holder `operator-ok:<command>:<target>`, delete-before-acting, exit 11
    `approver_not_installed` for the marker route only, and the `lift_card` rule (a marker never lifts
    a pause naming a `lift_card`; `resume_card_required`, marker left in place). §2.2b
    `operator_ok_valid`/`consume_operator_ok`, the §2.1 `operator_ok.sh` row, the §2.4 `resume` row
    and the exit-11 list match. The unsigned `{command, company, target, created_at}` form and the
    "remaining hole" sentence are gone.
82. **`08_seats_wps.md` Appendix B #128 (IMP-03/FID-06).** Replace "`= {command ∈ {resume, autonomy,
    pause}, company, target, created_at}` … valid iff `created_at` and mtime are < 15 min old …" and
    "The trust-edit marker … is a separate marker and, unlike this one, GTMApprover-signed" with: the
    marker is a GTMApprover-signed `gtm.operator_ok.v1` record (payload `{v, kind: "operator_ok",
    command, company, target, nonce, expires}`), created only by `operator_ok.sh` → `gtm_approve.sh
    operator-ok` → `GTMApprover --sign-operator-ok` (Touch ID); valid per 00_global_paths.md §1.4
    checks (1)–(5); nonce consumed (holder `operator-ok:<command>:<target>`) and the file deleted
    before the command acts; no pem at HEAD → exit 11 `approver_not_installed` (card routes
    unaffected); a pause naming a `lift_card` is never lifted by a marker. §9 A1 row: `operator_ok.sh`
    is a wrapper that execs `gtm_approve.sh operator-ok`.
83. **`05_approver.md` §5.3/§5.4 and `03_schemas.md` §3.9** — unchanged from
    `requests/00_global_paths.md` R29 (still open there): `GTMApprover --sign-operator-ok <command>
    <slug> <target>`, `gtm_approve.sh operator-ok`, and the `operator-ok:<command>:<target>` nonce
    holder form. 02 §2.3 cites 00 §1.4 until they land.
84. **`07_notices_schedules.md` §7.1 `resolve --operator` / `requests/07_notices_schedules.md` R45
    (not applied in 02).** 02 §2.3 follows 00 §1.4's `OPERATOR_OK_COMMANDS` = (`resume`, `autonomy`,
    `pause`) and `operator_ok.sh`'s target grammar (`PAUSE…|autonomous`), which admits no notice id.
    07 §7.1 already cites "02_act.md §2.3" for a `notice_resolve.<slug>.<notice_id>.json` marker that
    02 does not define. Either 00 adds `notice_resolve` to `OPERATOR_OK_COMMANDS` and widens the
    target grammar (then 02 §2.3 adopts it in the next round and `notices.py resolve --operator`
    consumes it with the signed checks), or 07 re-cites 00 §1.4 only. Decision belongs to 00's owner.

## Round 6 — raised while resolving the sixth `02_act.md` review (2026-09-27)

85. **Asset binding — bound copies (02 §2.8 check 4 "Asset binding", §2.4 `execute`/`ticket`/`run-holds`/`revert`).**
    `authorize` now copies every asset into `ST/assets/<action_id>/<sha256>` (0600, content-addressed) and
    hashes/scans the copy; `checks.rebind_assets` re-hashes and re-scans it as the last step before every
    platform call (`asset_sha_mismatch` → action `failed`, zero calls). Asks: (a) **06_connectors.md** —
    connectors receive and upload only the bound copies' paths, never `assets[].path` (add to §6.2's
    execute steps next to the check-1 re-run at L420); (b) **03_schemas.md §3.6** — a write ticket's
    `upload_assets` entries are the home-relative bound-copy paths; (c) **04_hooks.md §4.1 G-A rule 11**
    (L342) — the upload byte check reads the bound copy named by the ticket; (d) **08_seats_wps.md
    Appendix C item 5 / 00_global_paths.md §1.2** — add `ST/assets/` to the `ST` layout and the backup
    exclusions (it holds unpublished creative, some AI-generated).
86. **05_approver.md §5.5 step 0 / §5.6 "Which TRUST_PATHS are prevented".** Add `tools/gtm/act_fallback.py`
    (stdlib + `gtm_env` only) to the pre-check set: it is the only other module act.py imports on a
    trust-root failure (02 §2.1/§2.3). Update step 0's "The only exception is `lead-append`" to the four
    fallbacks 02 §2.3 lists (`lead-append`, `ingest-findings`, `pause`, `cancel`). Item 68 (expose
    `approval_sig.write_urgent_notice`) is **withdrawn**: `act_fallback.write_urgent_notice` is the
    fallback's own stdlib writer of the 07 §7.1 record.
87. **05_approver.md §5.1 step 5 — mirrored `$` card never decides (plan §20.8/§20.6).** 02 §2.11 removed
    the card-deny branch: any answer on an `approval <request_id>` card only writes
    `S/approver_inbox/show.<request_id>` and an info notice; `approval_denied` is written only from an app
    denial record (`decided_via: "app"`). Please drop step 5's card-deny path (and any `decided_via: "card"`
    denial record form in §5.5/03 §3.7). If the owner of 05 instead wants a card deny, it needs a plan
    §20.x amendment citing an operator ruling first; 02 does not adopt it without one.
88. **08_seats_wps.md Appendix C / 00_global_paths.md §0.1 — `phi1_root()` follows the Agency-root rule.**
    02 §2.1: `agency_root()` returns 00 §0.1's `A` (passwd home outside test mode, `Path.home()` in test
    mode); `phi1_root()` is DECIDED to follow the same rule. Please record it where 00 §0.1 defines `A`
    (and add `real_phi1_root()` if 00 wants the both-roots compare for it too). 04 `gtm_hooklib`
    re-exports both unchanged (item 67).
89. **08_seats_wps.md Appendix C item 14(a) — `project_dir_name_text` has one home.** It lives in
    `tools/gtm/project_dirs.py` (02 §2.1); `harvest_tool_trail.project_dir_name_text` becomes
    `from project_dirs import project_dir_name_text` (a re-export), never a second implementation.
90. **03_schemas.md §3.22 — `system_names.ALLOWLIST_KEY_SYSTEM`.** A dict mapping each
    `company._ACCOUNT_ID_ALLOWLIST_KEYS` key to its tier system (`ads_customer_ids` → `google_ads`,
    `meta_ad_account_ids` → `meta`, `gbp_location_ids` → `gbp`, `facebook_page_ids` → `facebook`,
    `instagram_ids` → `instagram`, `ga4_property_ids` → `ga4`, `gtm_container_ids` → the tag-manager tier
    system name §3.22 uses), so `checks.sibling_values` (02 §2.2 key → kind table) can call
    `normalize_account_id` with a tier system. Also state whether `legal_name` and
    `brands[].display_names` exist in the pack schema (02 treats them as name-kind when present).
91. **03_schemas.md §3.10 / 00_global_paths.md §1.2 — pause and card ledgers.** (a) `PAUSE.chain` JSON
    gains `chain_evidence: {reason, log_size, log_sha256, anchor_seq, anchor_hash}` (written by dispatch
    under `actions.lock`, 02 §2.3); `resume`'s `lifted_via` gains `"false_break"` with `evidence` (02 §2.4).
    (b) The pause file's `ts` is the occurrence time `resume <pause>` cards are bound to (02 §2.6
    "Single use"); state that `ts` is always written by `pauses.write_pause`. (c) Add
    `ST/cards_consumed.jsonl` (`{ts, card_id, subject, target, command, session_id, run_id}`, under
    `ST/cards_posted.lock`) to the `ST` layout; **04_hooks.md** G-W/G-B protect it as part of `ST`.
    (d) `ST/cards_posted.jsonl` records gain `effect_block_sha256: null|str`. (e) `ST/review_briefs.jsonl`
    and `ST/audit_samples/` (08 §8.4/§8.5) in the `ST` layout if not already there.
92. **05_approver.md §5.5 and 06_connectors.md §6.2 — exported code sets for 02's static exit-map test.**
    05: export `approvals_verify.VERIFY_REASONS` (every reason `verify` can raise, incl. the
    `verify_signature` set). 06: export `connector_dispatch.ERROR_KINDS` (every connector result error
    kind). 02's A1/A2 static test imports both instead of listing examples (02 §2.4 exit map).
93. **08_seats_wps.md §8.1/§8.4 and WP-M — `verify_reviewer(..., require_brief=True)`.** 02 §2.7 applies
    the §8.4 brief binding inside `gtm_result.verify_reviewer` by default; WP-M's `gtm_lists.py
    phi1-allowlist` (no act.py action, no brief) passes `require_brief=False`, the only caller allowed to.
    Please state the keyword in §8.1's signature and M's row.
94. **08_seats_wps.md Appendix C item 13 + 03_schemas.md pack schema — reconcile with 00 §0.1 (supersedes
    item 74).** 02 §2.8 check 9 now cites 00 §0.1 / App C item 13 (as amended by
    `requests/00_global_paths.md` R25) as the one definition: `marketing_code_paths` is withdrawn (no pack
    key lifts a never-listed path; the NEVER_CODE/NEVER_FIXED split is gone), `pricing_source_ref` is the
    object `{"path", "key"}` with the committed value set `V` read at `HEAD`/`<sha>^1`, `why` is not read,
    and the refusal codes are `price_not_in_source`, `price_source_missing`, `price_source_in_patch`. Item 13
    still adds `marketing_code_paths` and a string `pricing_source_ref` to `company.py`/`company_schema.json`
    and still describes the `why`-verbatim price rule and its `$49`→`$59` test — please rewrite item 13
    (and its tests) to 00 §0.1's form in the same round, and have 03's pack schema carry
    `pricing_source_ref` as that object (neither key is in `company.ALL_TOP_KEYS` today).
95. **08_seats_wps.md Appendix C item 14(b) — `harvest_paths` return values.** Specify
    `harvest_paths(paths: list[Path], *, require_slug: str | None = None) -> int`: 0 = harvested, nothing
    rerouted; 1 = harvested, every rerouted record belongs to a slug other than `require_slug`; 2 =
    `_registered_homes()` raised `CompanyError`, or `require_slug`'s trail path did not resolve, or a
    record of `require_slug` was rerouted to `unattributed_trail.jsonl`. It must never exit via
    `SystemExit`. 02 §2.11 treats only 0 and 1 as success (else `trail_unavailable`). Tests: a
    `CompanyError` → 2; this-slug records rerouted → 2; other-slug records rerouted → 1.
96. **06_connectors.md §6.3 (L936) — nested homes.** Read `git -C <H> show HEAD:./.claude/gtm/connectors.json`
    (with `./`), as 02 §2.2 requires for every home-relative HEAD read; without it a home nested below its
    repo toplevel resolves the path from the toplevel and fails.
97. **07_notices_schedules.md §7.1 — notice kinds.** Add kind `spool_dropped` (warn, push; 02 §2.3
    Replay: a permanently failing step-0 spool file is deleted and named); state the mirrored-`$`-card info
    notice text "Approve or deny in GTMApprover on the Mac (Touch ID)" (02 §2.11). The 07 §7.1 "Card
    drafts" chain card (§7.5 E1) is now rendered with an act.py effect block and is single-use and bound
    to the current `PAUSE.chain` (02 §2.4 `card-post`, §2.6): E1 must post a fresh card per break.
98. **08_seats_wps.md Appendix B — new DECIDED HERE entries (02_act.md, round 6).** (a) asset bytes bound
    from `authorize` to upload via `ST/assets/` copies + `rebind_assets` (§2.8 check 4); (b) class-of-event
    card subjects are single use (`ST/cards_consumed.jsonl`) and occurrence-bound (`card_predates_event`);
    `pause_carry_in` consumed per pause name (§2.6); (c) every gating subject carries an act.py-built effect
    block, else `card_effect_missing` (§2.4 `card-post`); (d) mirrored `$` card answers decide nothing
    (§2.11); (e) `verify_chain` reads anchor before log and dispatch re-verifies under `actions.lock` before
    writing `PAUSE.chain`; `resume --name PAUSE.chain` needs marker, single-use card, or the false-break
    proof (§2.3/§2.4); (f) duplicate `### [<id>] RESOLVED` headings → `card_subject_ambiguous` (§2.6);
    (g) run-holds applies the full `authorize` decision to `awaiting_approval` (§2.4); (h) the input-path
    rule for every `--file`/`--patch` (§2.4); (i) stored-patch sha verified on every read (§2.4 `propose`);
    (j) `authorize` refuses revert children exit 4 (§2.4); (k) `pause --self` bound to env
    `CLAUDE_GTM_RUN` + the GTM-session proof, and spooled `--self` replays as `skill` (§2.3/§2.4); (l)
    spool replay failures split permanent/transient (§2.3); (m) step-0 fallbacks live in
    `act_fallback.py`; the launching interpreter is never version-gated, only re-exec'd onto
    `TRUSTED_PYTHON` (§2.1/§2.3); (n) activity-log approval keyed on the unlock method, log-before-event
    with notes-based dedupe, pack re-check before the call (§2.10).

## Round 7 — raised while resolving the seventh `02_act.md` review (2026-09-28)

99. **03_schemas.md §3.22 — `ALLOWLIST_KEY_SYSTEM` (amends item 90).** Name the tier system (or state
    "none") for the two `company._ACCOUNT_ID_ALLOWLIST_KEYS` members item 90 left out:
    `ga4_property_ids` and `gtm_container_ids`. Until 03 maps them, 02 §2.2 (key → kind table) tags
    their values kind `other` (check 2's plain-substring rule), never `account id:<system>`.
100. **03_schemas.md §3.4.1/§3.4.4, §3.2 "Paused creates", §3.10 "Stop-row exemption" — one stop-row
    set.** (a) Add a row flag `stop_row: true` on exactly the 15 R40 rows (`google_ads.campaign_budget_edit`,
    `google_ads.campaign_pause`, `meta.campaign_budget_edit`, `meta.campaign_pause`,
    `meta.adset_budget_edit`, `meta.adset_pause`, `meta.spending_limit_edit`, `lsa.budget_edit`,
    `lsa.account_pause`, `L.paid_budget_edit`, `L.paid_pause`, `facebook.boost_stop`,
    `instagram.boost_stop`, `thumbtack.lead_pause`, `angi.lead_pause`); the tier-table validator
    refuses the flag on a row that is not `class: money` with `lanes_key: none`. 02 loads it as
    `tiers.STOP_ROWS` and never restates the list (02 §2.2b). (b) Define a **stop action** in §3.2/§3.10
    as 02's `tiers.is_stop_action`: row ∈ `STOP_ROWS`, effective class `money`, `money_brief.urgency ==
    "urgent"`, and `after.new_absolute_value` `"0.00"` or lower than `before.value.current_absolute_value`
    — narrower than the current "any matched `class: money` row with `lanes_key: none`", so the
    breaker exemption never admits a non-stop amount-only money row (e.g. a `vendor` or `paid_api`
    row) lowered to a smaller non-zero amount. (c) R57 is applied in 02: `pauses.blocking(ctx, system,
    cls, op, brand=None, action=None)` implements §3.10 brand coverage and the stop-row exemption.
101. **Signed revert children under a pause — ticket flag, G-A, pause table, connector pause step
    (02 §2.2b signed-revert exemption, §2.4 `revert`/`ticket`).** (a) 03 §3.6: add `revert_exempt`
    (bool, written on every write ticket; true only when mint passed `DISABLED`, `PAUSE` or
    `PAUSE.<system>[@<brand>]` for a revert child authorized at `revert` step 2 by a verified signed
    approval; a missing field reads false), next to `stop_exempt`. (b) 04 §4.1 rule 6b /
    `ticket_paused`: skip `R/schedules/DISABLED`, `ST/PAUSE` and `ST/PAUSE.<system>[@<brand>]` for a
    ticket with `revert_exempt: true` and for nothing else; never skip `PAUSE.chain`, the pause spool
    or a cancel marker; apply the `S/PAUSE.trust` check to such a ticket as to a money ticket (it is
    signed). (c) 03 §3.10 "Still allowed" cells: the `DISABLED` and `PAUSE` rows change "non-money: a
    card answered `approve` with subject `revert <child action_id>`" to "non-money: the child's
    amount-less signed request (§3.7 case (v)); the card route runs only when no pause covers the
    child"; the `PAUSE.<system>`/`@<brand>` rows gain "`revert` step 1, and step 2 with a signed
    approval of the child". (d) 06 §6.2 "The pause step of `execute`": call `pauses.blocking(actx,
    action["system"], cls, op, brand, action=action)`; replace "`revert` step 2 is allowed under
    `DISABLED` and `PAUSE`" with "a revert child authorized at step 2 by a verified signed approval is
    exempt from `DISABLED`, `PAUSE` and `PAUSE.<system>[@<brand>]` (02 §2.2b); a card-unlocked child
    is not"; and run the money approval binding (verify at `execute`, reserve, consume) for a signed
    non-money revert child too, over its `after_digest` form.
102. **03_schemas.md §3.7 case (v), 05_approver.md §5.5 step 3b and §5.1 — amount-less request for a
    non-money revert child (resolves 08_seats_wps.md item 40 / Appendix B #47).** 02 §2.4 `revert` now
    routes every non-money revert child whose system is under `DISABLED`, `PAUSE` or a covering
    `PAUSE.<system>[@<brand>]` to `awaiting_approval` with a request signed over the child's
    `after_digest` (no amount; `new_absolute_value`/`unit` null), created by `revert` itself. §3.7
    adds case (v) to the null rule; the request `display` names the parent it reverts, the row, the
    target and the child's `failing_checks` (the step-1 failures the signature approves); 05 §5.5 3b
    verifies it over `after_digest` like the other null cases, with the nonce reserved/consumed as for
    money; GTMApprover shows it. Plan §20.8 "`revert --approval <card id>` means a signed approval for
    that revert action" is read as applying to every revert that executes during a stop.
103. **08_seats_wps.md Appendix C item 14(b) — `harvest_paths` (re-raises item 95).** 02 §2.11 now
    calls `harvest_paths(paths)` with no keyword and accepts **only 0** (any non-zero or raise →
    `trail_unavailable`), because 08's "1 = registry or internal error" collides with 02's former
    "1 = another slug rerouted". Settle before A2 builds: adopt `harvest_paths(paths, *,
    require_slug=None) -> int` with 0 = harvested, nothing rerouted; 1 = every rerouted record belongs
    to a slug other than `require_slug`; 2 = registry/homes failure, `require_slug`'s trail path
    unresolved, or a record of `require_slug` rerouted; never exits via `SystemExit`; tests: a
    `CompanyError` → 2, this-slug records rerouted → 2, other-slug records rerouted → 1. 02 switches
    to `require_slug=ctx.slug` and accepts 1 only in a reviewed change after 08 adopts it.
104. **08_seats_wps.md Appendix C items 14/27 and 06_connectors.md §6.4 — navigation-click labels
    for the §2.11 trail conflict.** 02 §2.11 no longer excludes read-ticket agents or the verifying
    agent from the conflict set; only a `browser_click` whose element label equals a committed
    runbook `read_paths[*].clicks` label, on a `read_hosts` host, by a read-ticket agent, is exempt.
    (a) The harvester records a `browser_click`'s element description (Playwright's `element`
    argument, `redact_text` applied) as `detail.element`; on hipaa-redacted lines (item 27) it is
    omitted, so no click on a hipaa pack is exempt (fail closed). (b) 06 §6.4: state that
    `read_paths[].clicks` entries are the exact element labels a gtm-analyst passes to
    `browser_click` on that read path (the validator may require them non-empty strings).
105. **08_seats_wps.md Appendix B — revise #20 and add DECIDED HERE entries (02_act.md, round 7).**
    Revise #20: "…system-level ±60 min over mutating agent calls, with no exclusion for the
    verifying agent or read-ticket agents; only runbook read-path navigation clicks are exempt; for
    `--kind approval` also calls under a write/batch/setup ticket for a different action." Add: (a)
    card-post validates `--title` (single line, no `RESOLVED`/`**Operator answer`/`#`/`[`/`]`,
    hipaa untrusted-substring scan) and the archive region is the one `## Archived` line's tail
    (more than one → `operator_input_malformed`); every card parse uses `splitlines()`; (b)
    `tiers.STOP_ROWS` + the breaker stop-row exemption in `pauses.blocking` (action argument, brand
    coverage); (c) `checks.recheck` at mint, `execute`, `run-holds` (each due hold) and `revert` step
    2 → `refused`; (d) a pause's `lift_card` is consumed per (card, pause name), bound by
    `lift_card_postdates_answer`/`lift_card_already_answered`, and `pause` never rewrites an existing
    pause file; (e) hipaa: verbatim card answers side-stored, `runaway_spend`/`signin_missing` notice
    bodies built from codes only, fallback runaway body never carries `text`; (f) every non-money
    revert under `DISABLED`/`PAUSE`/`PAUSE.<system>` is signed (item 102); (g) re-authorizing a failed
    shared action needs a card posted after the failure; (h) `record-external --kind approval
    --subject owner_listen` is its own company-level form; (i) `harvest_paths` interim: only 0 is
    success; (j) make_ctx/dispatch validate slugs with `company.SLUG_RE`, 00 §0.3's wider regex only
    for id shape and the step-0 fallback.
106. **07_notices_schedules.md §7.1 — notice kind `revert_approval`.** warn, push; written by `act.py
    revert` when a non-money revert child gets an amount-less signed request (02 §2.4 `revert`); title
    "Revert <parent action_id>: approve or deny in GTMApprover"; for a `regulated ∋ hipaa` pack the
    title/body/push text carry only the company display name, system and action ids (the 05 R16
    rule for `$` notices). Also: for hipaa packs the `runaway_spend` and `signin_missing` notices
    written by `ingest-findings` never carry the finding's `text` (02 §2.4), and the step-0 fallback's
    `runaway_spend` body never does for any pack (02 §2.3).
107. **00_global_paths.md §0.3 — slug grammar.** Either adopt `company.SLUG_RE`
    (`^[a-z][a-z0-9-]{1,31}$`) as the one slug grammar, or state (as 02 §2.2 now does) that the wider
    `^[a-z0-9][a-z0-9-]{1,39}$` is only the id-shape test and the step-0 fallback's check, and that
    every command resolves a slug against `SLUG_RE` + `company.gtm_slugs()`.

## Round 8 — raised while resolving the eighth `02_act.md` review (2026-09-28)

Item numbers 108–111 are cited from `02_act.md` by number.

108. **WP-M (`gtm_lists.py`) and 03_schemas.md §3.20 — `phi_encountered` URL evidence (02 §2.4
     `ingest-findings`, §2.8 check 1).** 02 now adopts 08_seats_wps.md §8.1's URL rule in full:
     `ingest-findings` adds an `https://` evidence entry through `gtm_lists.add_phi_url(url, *, why,
     source)` (add-only, under `S/lists.lock`) as a `phi_denylist.json` `url_prefixes` entry keyed by
     `gtm_lists.phi_url_key(url)`, writes a pushed `phi_encountered` notice per URL entry, and check 1
     refuses `phi_target` when `target_ref` (or a `destination`-kind `id_fields` value) matches a
     `url_prefixes` entry by that same function. Asks: (a) WP-M exports `add_phi_url` and
     `phi_url_key` exactly as 08 §8.1 defines them (02 imports only `add_phi_path`, `add_phi_url`,
     `phi_url_key` from `gtm_lists`); (b) 03 §3.20 adds `url_prefixes` (`[{"url_prefix": str}]`, no
     `applies_to`) to the `phi_denylist.json` schema and its matching rule.
109. **03_schemas.md §3.2 (`committed_ceiling` snapshot contract) / §3.7 (request `display`),
     05_approver.md (GTMApprover display), 08_seats_wps.md §8.1 (analyst `snapshots[]`) — browser
     ceiling evidence (02 §2.6 rule 5a, §2.4 `snapshot`).** A browser `committed_ceiling` value is an
     **attested analyst read**, not a platform read. (a) 08 §8.1 / 03 §3.2: a `committed_ceiling`
     snapshot entry carries `screenshot: {"path": <home-relative path of the analyst's screenshot of
     the platform budget screen>, "sha256": <hex>}`; `snapshot` refuses an entry without a valid one
     (exit 3 `ceiling_evidence_missing`) and copies it beside the JSON as
     `<system>_committed_ceiling.png`. (b) 03 §3.7: the request `display` gains `ceiling_evidence:
     {"source": "api"|"snapshot", "screenshot_sha256": str|null, "screenshot_path": str|null}`,
     inside `display_b64`, so it is signed. (c) 05: GTMApprover re-hashes the screenshot against
     `screenshot_sha256` and shows it beside the amount before Touch ID; a missing or different image
     → the request is shown as not approvable. (d) 02 relies on 06_connectors.md §6.4's "Ceiling rows"
     before-check at execute as the backstop (no change requested to 06).
110. **03_schemas.md §3.4.1 — the hipaa inline-key allowlist (02 §2.2b `checks.HIPAA_INLINE_KEYS`,
     `hipaa_redact`).** 02 replaced the five-key free-text deny-list with an allowlist: every string
     leaf of `after`/`before`/a failure result is redacted on a hipaa pack unless its key is in
     `HIPAA_INLINE_KEYS` (key → shape class) or an `id_fields` key, and it matches that shape. Please
     (a) state in §3.4.1 which `after_value_fields` keys are structured (amount/code/date/hours/url/
     id/sha/path) versus free text — ideally as a per-field type in the tier-table row schema from
     which `HIPAA_INLINE_KEYS` can be derived — and (b) add a tier-table validator test that every
     `after_value_fields` key of every row is either in `HIPAA_INLINE_KEYS`, an `id_fields` key, a
     structured key with `nested_id_paths`, or listed as free text. Until then 02's initial list
     stands and any unlisted key is redacted (fail closed).
111. **03_schemas.md §3.17 / §3.1 — `autonomy_level.decided_by` gains `"demotion"`.** `autonomy
     --level shadow` is admitted from any environment with no marker (02 §2.3 GTM-session rule
     exception (3): a demotion only restricts) and records `decided_by: "demotion"`, `criteria: null`.
     Add the value to the enum and the fold. 07_notices_schedules.md §7.6: an operator demotion may
     simply run `act.py autonomy --company <slug> --level shadow` from their own terminal.
112. **07_notices_schedules.md §7.1 — `phi_encountered` notice from the trusted path.** Item 76(a)
     says `phi_encountered` is "written only by act.py's step-0 fallback". The trusted
     `ingest-findings` now also writes one per `https://` URL evidence entry (urgent, push,
     `dedupe_key` `phi_url:<host><path>`, body = the prefix and finding id only). Please widen the
     kind's writer list.
113. **03_schemas.md §3.11 — cancel-marker ingest on hipaa packs (02 §2.2b "Operator-typed
     reasons").** The ingest writes `cancelled.reason` only when it matches `^[a-z][a-z0-9_]{0,63}$`,
     else `reason: "other"` + `reason_detail: {digest, pointer}` (side-stored under `ST/untrusted/`),
     for every marker source (the step-0 `cancel` fallback, `gtm_cancel.sh`, the approver menu).
     Please add `reason_detail` to the `cancelled` event data and state the rule in §3.11.
114. **00_global_paths.md §0.2/§0.3 — `actions.lock` discipline (02 §2.2b `store.locked`,
     "Transition discipline").** 02 now declares the one lock API (`store.locked(ctx)`, not
     reentrant, 30 s → `lock_timeout`), requires id allocation and the `proposed` append to share one
     hold, and fixes the lock order `actions.lock` before `S/approval_nonces.lock`. Please note in
     §0.3 that "1 + max over the log under the actions lock" means within the same hold as the first
     append, and add the order to §0.2's lock list.
115. **05_approver.md §5.5 — confirmation.** 02 §2.2b now restates the `approvals_verify` API block
     (stages incl. `run_holds`/`revert`, full-prefix holders `ticket:`/`execute:`/`run-holds:`,
     `nonce_held`/`nonce_replay`/`nonce_not_reserved`) and uses `stage="revert"` at `revert` step
     2(a). The one open difference is unchanged: 05 raises `approval_expiring` at `EXIT_APPROVAL`
     while 02's exit map settles it at exit 3 (item 72).
116. **Coordinator (company.py `validate_company` + company_schema.json) — compile `claims_policy`
     regexes (02 §2.8 check 3, wave1c).** `claims_policy.terms[].regex` is a regex compiled as written
     (`re.compile(regex, re.IGNORECASE)`, never `re.escape`d). In `validate_company`, beside the
     existing `rule` check, add: `regex` missing or not a string → reason
     `claims_policy.terms[<i>].regex must be a string`; `re.compile` raising `re.error` → reason
     `claims_policy.terms[<i>].regex does not compile: <error>`. Test with the OtherCompanyB fixture (all
     three terms compile) and a pack whose term is `licens(` (refused). Until it lands, 02's
     `make_ctx` refuses such a pack `pack_invalid` (`claims_regex_invalid`) itself. Also state in
     company_schema.json that `never_claim_file` holds literal lines (one claim per non-empty,
     non-`#` line, one leading `- `/`* ` marker stripped), not regexes.
117. **03_schemas.md §3.4.3 "`shared_hits` — the closed test" — drop "not in `OWN`" (02 §2.8
     check 1, fid r3).** Replace "check 1 records a hit for each of these values that is not in `OWN`
     but **equals** a `shared_identifiers[].value`" with "check 1 records a hit for each of these
     values that **equals** a `shared_identifiers[].value` … whether or not it is also in `OWN` (the
     declaration wins; plan §20.2, §3.3/§6.3)". Keep "A value that matches neither `OWN` nor
     `shared_identifiers` fails check 1". Add the A1 tests 02 now states: a OtherCompanyB pack listing the
     Scout number in `brands[].phones` and declaring it shared (`pause_names: ["PAUSE.csa_scout"]`) →
     a `gbp.phone_edit` writing it is class `shared` / `awaiting_card`, and exit 5 at `authorize`
     under `PAUSE.csa_scout`; a `*.user_add` of an email in `identity_allowlist` that is also declared
     shared → `shared`; each RED when "not in `OWN`" is restored. (The §3.10 `pause_names` test at the
     Scout entry already assumes this and passes only once the condition is dropped.)
118. **04_hooks.md §4.3 machine-written list / `hooklib.machine_written` — add `R/.agent_budget/`
     (02 §2.7(a), wave1c).** 02 now takes reviewer, verifier and drafter identity from
     `R/.agent_budget/stops.jsonl` pending-stop rows (`kind: "stop"` or no `kind`) as well as
     `R/.agent_budget/spend.jsonl` (spend rows are written only when `reap_stale` reaps an unjoined
     stop after `CSA_CLAIM_TTL_SEC`, 6 h by default — the common case in the live ledger). Neither file
     is in `machine_written` today, so a Write/Edit or rule-c shell write by an agent could forge a
     seat. Please add `R/.agent_budget/` (every file under it: `claims.jsonl`, `stops.jsonl`,
     `spend.jsonl`, their locks) to the §4.3 list with a B1 parity test (G-W Edit and a rule-c `echo x
     >>` to `R/.agent_budget/stops.jsonl` both denied). The hooks themselves (`agent_budget.py`) write
     through Python, unaffected.
119. **Coordinator — operator card to ratify 05_approver.md §5.9 V4 (release-or-quarantine).** 02
     §2.2b now restates and applies 05 §5.5 step 5 "Release or quarantine" on every path that ends a
     money/signed reservation without a consume (`ticket --close`, `tickets.reconcile`,
     `complete --failed`, the `execute`/`run-holds`/API `revert` failure branches): release only on a
     proven no-write (`mutating_calls_used == 0`, or connector `side_effect: "none"`) or an idempotent
     absolute-value repeat; otherwise `approvals_verify.quarantine` + the `nonce_quarantined` urgent
     notice. This deviates from plan §20.8's literal "a failed/abandoned ticket releases the
     reservation" (05 V4, UNRATIFIED, blocks WP-A2 start). Please post one card in
     `_Config_Project/docs/domain/OPERATOR_DECISIONS.md` `## Open`: title "Ratify approver deviation
     V4 (quarantine an ambiguous money attempt)"; body in plain language: if a paid change (purchase,
     fee, paid trial) fails after the browser may already have clicked "Buy", the system will NOT
     reuse your Touch ID approval to try again — you must approve a fresh request after checking the
     platform; this prevents a double charge; options Yes (ratify) / No (keep the plan's literal
     release-and-retry). 05_approver.md §5.9 V4 then moves to RATIFIED or CONFORMED per the answer.
