# Change requests from `08_seats_wps.md` (§8, §9, Appendices A–C) to other contract files

Each request names the target file, section and exact change. They keep the other files consistent
with fixes already made in `08_seats_wps.md` this round. If a target file already resolved the same
finding differently, the coordinator reconciles to one shape (the 08 text names its source).

## 1. `02_act.md` §2.7 (c) and §2.1 — FID-08 (attestation) — **superseded by §10 below** (the row key, extractor signature and refusal codes changed in round 5)

- §2.7 bullet "A review for lane L counts iff", item (c): after "the verdict comes from that agent's
  **own** transcript's final `gtm-result` (`gtm_result.py`)", add: "**and** that block is attested
  per 08_seats_wps.md §8.1 (its canonical hash equals the agent's last `S/agent_results.jsonl`
  line, written by the SubagentStop hook from `last_assistant_message`; `extract_gtm_result`
  returns `None` otherwise, so an appended forged transcript record never counts)".
- §2.7 "Standalone reviewer check" and "Standalone verifier check": after "final block via
  `extract_gtm_result`", add "(attested, 08_seats_wps.md §8.1)".
- §2.1 module list, the `gtm_result.py` line: add `parse_block(text)` (the one block parser, shared
  with B1's SubagentStop hook) and "attestation check against `S/agent_results.jsonl`".

## 2. `02_act.md` §2.7 first bullet — FID-05 (`_nomatch` lanes)

- In "plus `cta_link` when `row.public`, the row is not `_nomatch` (whose gate is the signature,
  03_schemas.md §3.4.2), and any string …", delete "the row is not `_nomatch` (whose gate is the
  signature, 03_schemas.md §3.4.2)," — `_nomatch` now takes the public lane set before `authorize`
  (08_seats_wps.md Appendix B #99), so it gets `cta_link` on a link like any public row.

## 3. `03_schemas.md` §3.4.2 and §3.4.4 — FID-05

- §3.4.2 `_nomatch`: replace "and its `public: true` needs no lanes (the operator's signature is its
  gate); the §3.4.4 lanes test covers table rows only" with: its `lanes_key` names the public lane
  set (`brand`, `claims_voice`; `cta_link` and `video`/`hipaa` added by 02_act.md §2.7 as usual),
  required before `authorize` creates the approval request; the lanes test covers `_nomatch` too.
  Pick one `lanes_key` name for that set (e.g. `money_public`) and add it to §3.5 `review_lanes.json`.
- §3.4.4 "Every class: money row has `lanes_key: none`": restrict to amount-only money rows
  (`after_fields` ⊆ {`new_absolute_value`, `unit`}); a money row whose `after` can carry text or
  assets uses the same public lane set. This matches 08_seats_wps.md Appendix B #49/#99 as amended.

## 4. `00_global_paths.md` §1.2, §0.3 — FID-08, IMP-08

- §1.2 `S` layout: add `agent_results.jsonl` and `agent_results.lock` (08_seats_wps.md §8.1;
  written only by `hooks/gtm_ticket_release.py`).
- §0.3 "Backup and restore carry the anchor with the log": append "`backup_company` captures
  `ST/actions.jsonl` and the anchor under `ST/actions.lock` (30 s), so a concurrent append cannot
  split the pair; exit codes stated in 08_seats_wps.md Appendix C item 7 (IMP-08, IMP-17)".

## 5. `04_hooks.md` §4.2 rule c, §4.3, §4.5, §4.8 item 6 — FID-08 (the §4.8 command below stands; the §4.5 row definition is **superseded by §11**)

- §4.3 G-W deny set and §4.2 rule c: in GTM scope, deny writes to `R/projects/**/*.jsonl`
  (transcripts) and, in every scope, to `S/agent_results.jsonl`/`.lock` (hook-written only).
- §4.5: add "Also appends the 08_seats_wps.md §8.1 attestation line to `S/agent_results.jsonl` for
  every stop whose `last_assistant_message` contains a ```` ```gtm-result ```` fence, **in any
  session** (the ticket-release half still acts only on GTM tickets); imports
  `tools/gtm/gtm_result.py` (`parse_block`) — a standalone module (Appendix B #9)".
- §4.8 item 6: change the SubagentStop command so non-GTM sessions still reach python when the
  payload carries a result block:
  `payload=$(cat); if [ -z "${CLAUDE_GTM_COMPANY:-}" ] && ! printf '%s' "$payload" | grep -q 'gtm-result'; then exit 0; fi; printf '%s' "$payload" | python3 ~/.claude/hooks/gtm_ticket_release.py`
  (with the standard `CSA_DISABLE_HOOKS` prefix).

## 6. `04_hooks.md` §4.7, §4.9, §4.2 rule k — IMP-04

- §4.7 opening and §4.9's `pretooluse_bash.py: G-B wiring (§4.2)` line: state that during Wave 2
  B2 does **not** save these edits into the live `hooks/bash_gate.sh`/`hooks/pretooluse_bash.py`;
  it delivers them as `tools/gtm/wave2_pending/b2_gb_wiring.patch`, its end-to-end tests run a
  patched copy under the §1.5 tmp `CLAUDE_DIR/hooks/`, and the coordinator applies the patch in the
  same post-Wave-2 step as G-W registration (08_seats_wps.md §9 B2 row, Appendix C item 19).
- Recommended (IMP-04's second fix, compatible with the above): allow rule k's literals as
  arguments to `grep`/`rg`, and exempt a protected path used only as a `cp` **source** with a
  destination outside every protected path, so post-Wave-2 reviewers can take single-file backups.

## 7. `04_hooks.md` §4 intro — IMP-22

- Drop `tools/gtm/gtm_pricing.py` from `gtm_hooklib`'s allowed imports (nothing in its API needs
  it). 08_seats_wps.md §9 B1 now lists `approval_sig` (A2) under Consumes. For `write_notice_file`
  vs `notices.py`: either one shared stdlib helper both import, or a B1 parity test — decide in §4.

## 8. `06_connectors.md` §6.2, §6.4, §6.5 — IMP-10 — **WITHDRAWN (round 5)**

The direction is reversed: 06_connectors.md §6.4b/§6.5b is now the one specification and 08_seats_wps.md §9
carries only a pointer to it (see §13 below). Do not apply the bullets that follow.


- §6.4, the sentence naming `tools/gtm/runbook_validate.py`: append "API, problem codes and exit
  codes: 08_seats_wps.md §9 (`runbook_validate.py` and `connectors/testkit.py` API)".
- §6.5: append "API and fixture naming: 08_seats_wps.md §9. Connectors make HTTP calls only as
  `urllib.request.urlopen(...)` (module attribute), so `testkit.FakeHTTP.install` catches every call."
- §6.2 (optional, same rule): note the `urlopen`-only HTTP rule next to the entry points.

## 9. `07_notices_schedules.md` §7 intro or §7.6 — FID-18

- Add one pointer line: "The plan §10 skills (args, commands, refusals, `test_k_skills.py`) are
  contracted in 08_seats_wps.md §9 'Skill contracts'; `/gtm-cycle <kind>` runs §7.5's checklist
  for that kind inside an interactive cycle."

## 10. `02_act.md` §2.7 (c), §2.1, §2.3 refusal list — FID-08, one definition (round 5)

Copy 08_seats_wps.md §8.1 "Fence grammar and parser" and "Attestation" word for word:
- §2.7 (c): replace "`block_sha256` the SubagentStop hook recorded … appends `{agent_id, agent_type,
  block_sha256 | null, ts}` from `last_assistant_message` via `gtm_result.extract_gtm_result`" with:
  the last `S/agent_results.jsonl` row for that `agent_id` has `result_sha256` equal to
  `gtm_result.result_sha256(block)`; the hook writes `{"ts", "session_id", "agent_id", "agent_type",
  "result_sha256"}` with `result_sha256 = result_sha256(parse_block(last_assistant_message))` or null,
  on every SubagentStop whose message holds an opening-fence line, in any session. (`block_sha256`
  stays the name of the **card** block hash in `ST/cards_posted.jsonl`; the attestation key is
  `result_sha256`, so the two never collide.)
- §2.7 (c): `extract_gtm_result(agent_id, …)` → `extract_gtm_result(agent_id: str, transcript_path:
  Path) -> ExtractResult(block, reason)` with reason ∈ {`ok`, `unreadable`, `unrecorded`,
  `mismatch`}, mapped to `gtm_result_unreadable`, `agent_result_unrecorded` (retryable),
  `agent_result_mismatch`.
- §2.3/§2.4 refusal-code list: add `gtm_result_unreadable` (exit 3) beside `agent_result_unrecorded`
  and `agent_result_mismatch`.
- §2.1 module list, `gtm_result.py` line: `parse_block(text)`, `result_sha256(block)`,
  `extract_gtm_result(agent_id, transcript_path)` (typed result).
- §2.4 `ingest-findings`: add to its printed JSON `"malformed_findings": [<finding id or index>]` — a
  finding missing its kind's required keys (08_seats_wps.md §8.1 "Findings by kind") is acted on by
  no branch and listed there; a `signin_missing` finding without `system` is malformed.

## 11. `04_hooks.md` §4.5 — FID-08, one definition (round 5)

- Replace the "Result record" row: `{"ts", "session_id", "agent_id", "agent_type", "result_sha256"}`,
  `result_sha256 = gtm_result.result_sha256(gtm_result.parse_block(last_assistant_message))` (the
  parsed block's canonical hash, **not** a hash of the raw message), `null` when `parse_block` returns
  None; written only when `last_assistant_message` contains a line exactly ```` ```gtm-result ````, in
  any session.
- Replace "Registered behind the `CLAUDE_GTM_COMPANY` shell fast path (tickets exist only in GTM
  sessions)" with: registered with no `CLAUDE_GTM_COMPANY` gate; the shell fast path skips only a
  payload that does not contain the text `gtm-result` (the §4.8 item 6 command of §5 above); the
  ticket-release half acts only on GTM tickets.
- B1 tests: use the shared fixture `tools/gtm/tests/fixtures/attestation/` (08_seats_wps.md §8.1;
  Appendix C item 28): the hook fed `subagent_stop.json` with `CLAUDE_GTM_COMPANY` unset writes exactly
  `expected_row.json` (+ `ts`); a payload whose message has no opening-fence line writes no row.

## 12. `04_hooks.md` §4.2 rule k and §4.7 fast path — operator-marker literal (round 5)

- Rule k's literal list and the §4.7 `case` token `*operator_ack*`: replace `operator_ack` with
  `operator_ok`, matching `system_names.RULE_K_LITERALS` (00_global_paths.md §1.4 "Shared literals",
  which retires `operator_ack`) and 02_act.md §2.3 "Operator marker" (08_seats_wps.md Appendix B #128).

## 13. `06_connectors.md` §6.4b/§6.5b — IMP-10 (round 5)

- The "R6 replaces that copy with a pointer" / "08_seats_wps.md §9's older copy of this API is
  superseded (R6)" notes are now done: 08_seats_wps.md §9 carries only a pointer (Appendix B #117).
  §6.4's sentence "(§6.4b; WP-L3, used by every L sub-WP's P2 tests; 08_seats_wps.md §9)" may drop the
  08 reference. §6.3 "GSM project value": "08_seats_wps.md Appendix C coordinator follow-up" →
  "08_seats_wps.md Appendix C item 30".

## 14. `04_hooks.md` §4.9 (and §4.6 "How `pretooluse_task.py` learns that T2 denied") — B2 Task wiring (round 5)

- State that during Wave 2 B2 does not save its `hooks/pretooluse_task.py` and `hooks/agent_budget.py`
  edits (T1b gate-gtm call, T2-deny `outcome`, `release_admission`, the 03_schemas.md §3.13
  transcript-tag fallback) or their updates to existing hook tests into the live files; it delivers
  them as `tools/gtm/wave2_pending/b2_task_wiring.patch`, tested on tmp copies, applied and deleted by
  the coordinator in the 08_seats_wps.md Appendix C item 19 step (Appendix B #173).

## 15. `02_act.md` §2.8 check 9 and §2.4 `complete --commit` — marketing never-list (round 5)

- Check 9 and the commit form of `complete` also refuse `non_marketing_path` for any path matching
  `gtmlib.checks.MARKETING_PATH_NEVER` (08_seats_wps.md Appendix C item 13, with its matching rule)
  whatever `pack.marketing_paths` says, and refuse `tracking_change_not_static` for a patch whose added
  lines contain `<script`, `<iframe`, `gtag(`, `fbq(`, `dataLayer` or an inline `on[a-z]+=` handler;
  add both codes to the refusal-code list and the tests named in item 13.

## 16. `03_schemas.md` §3.14 — FID-19 pack field (round 5)

- "a pack-schema addition, 08_seats_wps.md Appendix C" → "08_seats_wps.md Appendix C item 29".

## 17. `CONTRACTS.md` line 8 (round 5)

- No change needed if the coordinator's Appendix C item 31 check passes: Appendix B is now intended
  to be complete, with the cited section normative. If the check ever finds an unindexed hit that
  cannot be added at once, change "indexed in `contracts/08_seats_wps.md` Appendix B" to "indexed
  (completeness checked by Appendix C item 31) in …".

## 18. `07_notices_schedules.md` §7.2 — Appendix B #83 (round 5)

- No text change: §7.2's paused-inbox rule (inbox starts with `PAUSED=1`, every other kind
  `skipped-paused`) is the normative form; 08_seats_wps.md Appendix B #83 now indexes it as such.


## 19. `00_global_paths.md` §1.4 "Operator authority is never read from the environment" and §1.5 — operator-marker file name (round 6)

- 02_act.md §2.3 "Operator marker" (the owner) names the marker `S/operator_ok/<command>.<slug>.<target>.json`
  (keyed by target so several lifts can be pending). §1.4 still says `S/operator_ok/<command>.<slug>.json`,
  e.g. `S/operator_ok/resume.other-company.json`, and §1.5's test item writes
  `<tmp S>/operator_ok/<command>.<slug>.json`. Replace both with `<command>.<slug>.<target>.json`, the
  example with `S/operator_ok/resume.other-company.PAUSE.website_wordpress@remodeling.json`.
  (§1.2's layout row is already requested by `requests/02_act.md` item 34.) 08_seats_wps.md Appendix B
  #128 now uses the target-keyed name.

## 20. Appendix C item 31 check — lead-ins not yet indexed in Appendix B (round 6; for the coordinator)

A text scan of `**<lead-in> (… DECIDED HERE …)**` forms found these lead-ins with no Appendix B entry
naming them. Some are covered in substance by an older entry (noted); the rest need an entry, written
from the cited section, in the item 31 pass (the files were still being edited, so line numbers drift):
- Covered in substance, lead-in not named: 00 "Agency Claude-session transcripts are skipped too" (#86),
  "Interim deny" (#44), "Counter source" (#87), "Shared literals" (#159); 02 "Test files" (#88),
  "`--file` restriction" (#11), "Field allowlist" (#69); 03 "one state machine per class" (#22, #73),
  "Attribution never depends on the pacer claim" (#76), "Cache split" (#28), "OtherCompany read
  allowlist" and its fail-closed rule (#29), "Hidden-amount guard" (#50).
- No entry: 02 §2.4 `card-post` "Subject/action binding" and "Machine block", "`company_from` and
  `id_args` — exhaustive", §2.8 "Asset path containment"; 03 "Money value strings", "Brand binding",
  "Current-value refresh", "`shared_hits` — the closed test", "outward" (§3.4), "Reviewer
  audience", "`requested_via`", "Brand coverage"; 06 "`execute` and `verify` re-check executability
  themselves", "Account keys", "Money binding", "Committed amount of a status row", "Auth scheme per
  connector", "`google_sa` token minting", "Lead sink"; 07 "A signed `"0.00"`". Unbolded
  `DECIDED HERE` hits (several already indexed, e.g. #30, #31, #33, #42) were not scanned this way and
  still need the grep of item 31.

## Round 7 — requests from the 08 review-fix pass (2026-09-27)

Each item keeps another file consistent with a fix made in `08_seats_wps.md` this round. The 08
section named in each item is the source text.

## 21. `02_act.md` §2.4 (`ingest-findings`, `review`, `snapshot`), `03_schemas.md` §3.19, `07_notices_schedules.md` §7.1 — HIPAA free text in `gtm-result` (08 §8.1 "HIPAA free text")

- For a `regulated ∋ hipaa` company, every consumer that persists a free-text string from a
  `gtm-result` block (`findings[].text`, `reviews[].lines[].note`, `audit_sample[].note`,
  `scoreboard[].note`, platform strings inside `snapshots[].data`/`change_history[]`) applies the
  02_act.md §2.2b "HIPAA side-store form" (digest + pointer into `ST/untrusted/`) before the string
  reaches `actions.jsonl`, a notice body, a scoreboard row or a report. `perf_report.py`'s quality
  block (03 §3.19) and `notices.write_notice` bodies built from findings (07 §7.1) quote no such
  string. Tests: a hipaa fixture finding whose `text` holds a sentinel string → the sentinel appears
  in no event, notice, scoreboard row or report, only in `ST/untrusted/`.

## 22. `02_act.md` §2.4 `status`/`review`, §2.7 `verify_reviewer`, §2.3 refusal list; `00_global_paths.md` §1.2 — review-brief binding (08 §8.4, Appendix B #213)

- `status --review-brief` also appends `{"ts", "action_id", "after_digest", "brief_sha256"}` to
  `ST/review_briefs.jsonl` under `ST/review_briefs.lock` (5 s); `status` stays read-only on
  `actions.jsonl`.
- `act.py review` and `gtm_result.verify_reviewer` refuse exit 3 `review_brief_unbound` unless the
  reviewer's own transcript holds a `Read` `tool_use` whose `input.file_path` (after
  `os.path.normpath`) equals `<company.py resolve(slug)>/.claude/gtm/state/review_briefs/<action_id>.json`
  and the brief file's current sha256 equals the last `brief_sha256` recorded for that `action_id`
  with the same `after_digest`. Add `review_brief_unbound` to the exit-code map. A1 tests as listed
  in 08 §8.4.
- 00 §1.2 `ST` layout: add `review_briefs.jsonl`, `review_briefs.lock` (act.py-written; G-W/rule c
  deny agent writes like the rest of `state/`).

## 23. `06_connectors.md` §6.6, `03_schemas.md` §3.6 and §3.21, `02_act.md` §2.4 `ticket --setup`/`ticket --close` — gtm-credential-setup `acting_as` (08 §8.5 items 1 and 11, option (a))

- 06 §6.6: every capture script reads the page's signed-in account label (the runbook's `acting_as`
  element) **before** reading the token, POSTs `{"ticket_id", "secret_name", "value",
  "acting_as_label"}`, and returns exactly `{"acting_as_label": "<text>", "stored":
  "stored:<name>:<sha8>" | null, "sink": "<ok|refusal code>"}` (replacing the current "returns only
  the sink's reply `stored:<name>:<sha8>`"). `secret_sink.py serve` compares `acting_as_label`
  (exact string equality after whitespace collapse) with the setup ticket's `acting_as_expected`
  **before** step 1 of the GSM write: a mismatch writes nothing to GSM, replies `409
  acting_as_mismatch`, appends an isolation hit (`source: "secret_sink"`, `detail:
  "acting_as_mismatch"`), and when the script's `regenerates` is true runs the ROTATE path's
  notice + revocation-card step (there is no GSM version to disable). Tests: a POST with a
  different label → 409, no gcloud call, one isolation-hit line; the same POST with the expected
  label → stored.
- 03 §3.21: add to the `secret_sink` trigger "or the capture's `acting_as_label` ≠ the setup
  ticket's `acting_as_expected`".
- 02 §2.4 `ticket --setup`: `result` also carries `setup_brief` = `{"ticket_id", "action_id",
  "system", "script_id", "script_function" (the exact text of the allowlisted `.js` file at HEAD),
  "target_url" (the URL of the first `navigate` step of the runbook's `writes[<row>]`),
  "acting_as_expected"}` — the session pastes it verbatim into the seat's ```` ```gtm-setup ````
  prompt fence, because the seat holds no `Read` (08 §8.5 item 1). `ticket --close` on a setup
  ticket, given `--from-agent <credential-setup agent_id>`, compares the seat's
  `operations[].acting_as_after` with `acting_as_expected` and appends an isolation hit
  (`source: "act_complete"`) on a difference.
- 04 §4.1 rule 12 and plan §20.10: **no change** — one allowlisted script per setup ticket; no
  second `acting_as` script and no free-form evaluate (08 §8.5 item 11 records the choice).

## 24. `02_act.md` §2.4 `status`, `07_notices_schedules.md` §7.5 W5, `03_schemas.md` §3.19, `00_global_paths.md` §1.2 — weekly audit sample producer (08 §8.5 item 9, Appendix B #215)

- 02 §2.4 `status`: add `--audit-sample --lane <lane> --days <N>` (read-only on `actions.jsonl`):
  population = the latest `review` event per `action_id` in the N company-local days ending now whose
  reviewer `agent_type` is `gtm-checker` and lane is `<lane>`, sorted by `action_id`;
  `k = ceil(0.2 × N_pop)` (≥ 1 when `N_pop ≥ 1`); `seed = int(sha256("<run_id>:<lane>").hexdigest()[:16], 16)`
  with `run_id` = `$CLAUDE_GTM_RUN`; sample = `random.Random(seed).sample(population, k)`; writes one
  review brief per sampled action (as `--review-brief`) and `ST/audit_samples/<run_id>_<lane>.json` =
  `{"run_id", "lane", "population", "seed", "action_ids", "brief_paths"}`; prints its home-relative
  path; `N_pop = 0` → no file, `result.population: 0`. Tests: same run + lane → same sample; 7 items
  → k = 2; 1 item → k = 1.
- 07 §7.5 W5: before the director dispatch, for each lane with a checker verdict in the window run
  `act.py status --company <slug> --audit-sample --lane <lane> --days 7`; the director dispatches
  the lane's first `public_reviewers` seat with the §8.2 tag and a ```` ```gtm-audit-sample ````
  fence `{"lane", "sample_path", "brief_paths"}` (absolute); `test_k_prompts.py` asserts the
  command string.
- 03 §3.19 `audit_disagreement_rate`: source = the `audit_sample[]` entries of those dispatches.
- 00 §1.2: add `ST/audit_samples/` (act.py-written).

## 25. `02_act.md` §2.4 `pause`/`resume` and §2.2b `pauses.write_pause`/`lift_requirement` — `requested_via` (08 Appendix B #46; same change as requests/03_schemas.md R32)

- Adopt 03_schemas.md §3.10 "`requested_via`": `pause` writes `requested_via: "skill"` by default
  and `"self"` (with `run_id`) only under `--self --run <cycle id>`; `lift_requirement` returns
  `"always"` only for `created_by: "act"` **and** `requested_via: "self"` with a null `ruling_ref`.
  Replace §2.4 `resume`'s "`created_by: "act"` with no `ruling_ref` → always". A1 test: a pause
  written by `act.py pause --reason x` then a bare `act.py resume` in a GTM session → exit 3
  `resume_card_required`, file intact; the same with `--self --run <id>` → removed; RED when
  `lift_requirement` tests `created_by` alone.

## 26. `00_global_paths.md` §0.1 "The `marketing_paths` guardrail"; `02_act.md` §2.8 check 9 and §2.4 `complete --commit`; `03_schemas.md` pack schema and §3.4.1 — one never-list (08 Appendix C item 13)

- 00 §0.1: replace the guardrail's own code/build basename list with a pointer to 08 Appendix C
  item 13's `MARKETING_PATH_NEVER` (two classes); state that `marketing_code_paths` exempts only a
  path whose sole match is the code class, never a tracking, consent, build, deploy, test, script,
  config or lock entry. Its A1 test "the same path (`marketing/website/build.mjs`) listed in
  `marketing_code_paths` → allowed" contradicts that and becomes: `build.mjs` listed → still
  `non_marketing_path`; a code-class-only path listed (e.g. `marketing/website/js/faq.js` whose
  pre- and post-image hold no tracking token) → allowed. The price rule stays (08 item 13 restates
  it, same regex and code).
- 02 §2.8 check 9 / §2.4 `complete --commit` (amends item 15 of this file): the tracking-content
  rule scans **added and removed** lines and adds the include-directive, `<noscript`, off-pack
  `<img`, off-pack `<link rel=preconnect|dns-prefetch|preload|prefetch|modulepreload>`, `<form`/`<input`
  patterns; the whole-file tracking-token check on exempted code files; `price_source_missing`;
  `agency_boundary`; the tests listed in 08 item 13 (deleting `templates/index.html` L17 → refused;
  a noscript-img pixel → refused).
- 03 pack schema: `validate_company` refuses a `marketing_code_paths` entry that matches any
  never-exemptable pattern, and a `marketing_paths` entry equal to or under the Agency root.
- 03 §3.4.1 `content_data_flow`: consider applying it to removed patch lines too (a removed consent
  include is a data-flow change); at minimum it must not contradict item 13.

## 27. `03_schemas.md` pack schema (`inbox`) — OtherApp inbox (08 Appendix C item 33)

- `company_schema.json` doc sentence for `inbox`: "`github_label` only for a
  `repo_registry_slugs` home (today CSA); every other home is `local_jsonl`". The check itself is
  the coordinator's `company.py` change (08 Appendix C item 33).

## 28. `02_act.md` §2.7 (c) and `04_hooks.md` §4.5 — word-for-word copies of 08 §8.1 (round 7)

- `extract_gtm_result(agent_id: str, transcript_path: Path | None)`: `None` → `unreadable`; the
  final-turn text definition (text blocks of the `assistant` records after the last `user` record,
  joined with `"\n"`); `parse_block` also returns `None` for `schema != "gtm.result.v1"` or `status ∉
  {ok, partial, failed}`. The attestation row sentence now reads "hook-written; agent writes are
  denied by G-W and rule c (a confused-agent control; interpreter writes are the accepted residual
  of 04 §4.2)". Copy these where 02 §2.7(c) and 04 §4.5 restate §8.1.

## 29. `04_hooks.md` §4.9 — B2 patch hand-off (08 §9 B2 row, Appendix B #218)

- State that both `tools/gtm/wave2_pending/*.patch` files are committed in B2's train (untracked
  files under `tools/gtm/` trip the trust-root check), carry `# base <path> <blob sha>` header lines,
  are checked with `git apply --check` at Appendix C item 19 and regenerated by B2 on failure (never
  fuzz-applied), and are deleted in the item 19 commit. `ai_budget.py` is live code from its first
  commit (A1 imports it).

## 30. `06_connectors.md` §6.6 CLI block — fallback B not built (requests/06_connectors.md R7, applied in 08)

- Mark the `ingest-file` CLI line "(fallback B — not built until 08 Appendix C item 32 records
  trust-architect's ruling in plan §17)". 08 has applied R7 (E row, #57, #85, #39, M row, new
  Appendix C item 32).

## 31. `07_notices_schedules.md` §7.5 "Operator tasks for homes without a `local_jsonl` inbox" — ratified

- 08 Appendix B #208 now indexes and ratifies the deviation; the "carried to 08 Appendix B for
  ratification (R4)" sentence may read "indexed in 08 Appendix B #208".

## 32. `05_approver.md` — R8 and R24 applied

- 08 Appendix B now carries 05 R8 (#37 adds `telemetry/pricing.json`; #135 adds the
  `model_policy.json`/`seat_sets()` sentence; #124 cites 05 §5.1/§5.5 3b "Enable binding") and 05
  R24 (#209–#212). The plan §17 manual check of R24 ("one Approve = exactly one prompt showing the
  amount; reuse duration 0") is the coordinator's, not 08's.

## 33. `03_schemas.md` — R17 applied

- 08 §9 A1 row and Appendix B #96 no longer name `ads_internal_cta`; the `google_ads.*@paused`
  ad/asset rows are `public: true` with `lanes_key: public_post` (FID-09).

## 34. Plan `~/.claude/plans/gtm_autonomous_department_plan.md` (coordinator)

- §20.x (new, e.g. §20.18): the OtherApp `website_static` interim of 08 Appendix C item 15, citing
  the card once posted — before P1b enables any OtherApp `website_static` row. §20.9c's verbatim
  text is never edited.
- §17: the fallback B ruling (08 Appendix C item 32) with probe `l2`; probe `l` part 2's answer on
  whether `browser_navigate` inlines page text (08 §8.5 item 11's navigate-time `acting_as` read).
- Ratification list: the carry-in card (08 §9, #174) and the chain card (07 §7.1, #133) as
  deviations from §20.11's touchpoints; the `/gtm-onboard` `pack_value_unknown` rule (#219) as
  stricter than §20.9a's OPERATOR-ONLY marking; `lsa.lead_dispute_submit` T3 vs §6.3 T2 (#99).

## Round 8 — OPEN_FINDINGS re-check of the 08-tagged findings (2026-09-27)

## 35. `04_hooks.md` — R1 applied (IMP-22)

- 08 §9 B1 row: "05_approver.md §5.5 `approval_sig` (A2; `gtm_hooklib` imports it, IMP-22)" removed
  from Consumes; `07_notices_schedules.md §7.1 notices.write_notice` (parity test only) added;
  Implements gains `hooks/tests/test_gtm_notice_parity.py`, G-W's `pack-edit-in-gtm-session` /
  `transcript-write` denials and the §4.8 item 6 SubagentStop command test; Must-NOT-touch now
  states B1 never imports `approval_sig`, `gtm_pricing` or `ai_budget`. No change requested of 04.

## 36. `03_schemas.md` — FID-05 wording aligned in 08 (no change requested)

- 08 Appendix B #99 and the §9 A1 row now read as 03_schemas.md §3.4.4 does: every `class: money`
  **table** row has `lanes_key: none`; `_nomatch` takes the `nomatch` public lane set; a money-row
  proposal with non-empty `assets[]` gets that set from `required_lanes` (02_act.md §2.7). The
  earlier 08 wording ("every money row whose `after` can carry text … requires the public lane
  set") implied non-`none` money table rows and is withdrawn.

## 37. `OPEN_FINDINGS.md` (coordinator)

- Every finding tagged for 08 (IMP-04, IMP-08, IMP-10, FID-05, FID-08, FID-16, FID-17, FID-18,
  IMP-17, FID-22, IMP-22) has its 08 side written: §8.1 attestation, §9 B1/B2/H1/H2/J/K/L3/M rows,
  "Skill contracts", MIG, Appendix B #99/#114–#119/#139/#140/#173/#218, Appendix C items 7, 16, 19.
  The coordinator may mark the 08 entries resolved once the cross-file pointers above are applied.

## Round 9 — requests from the 08 review-fix pass (2026-09-27)

Each item below keeps another file consistent with a round-9 fix already made in `08_seats_wps.md`.
Where an item supersedes part of an earlier request, it says so.

## 38. `03_schemas.md` §3.20, `02_act.md` §2.4 `ingest-findings`, `04_hooks.md` §4.1, `06_connectors.md` §6.5b — PHI pages (08 §8.1 "URL evidence", Appendix B #221)

- 03 §3.20: add `"url_prefixes": [{"url_prefix": "https://<host><path>"}]` to the `phi_denylist.json`
  shape (host lowercase, no query or fragment, path `/` when empty; never `applies_to`, so it binds
  every company); `gtm_lists.py` validation refuses a non-`https` prefix, a query/fragment, or an
  `applies_to` key on it; add the in-process function `add_phi_url(url: str, *, why: str, source:
  str) -> bool` (add-only, under `S/lists.lock`, False when already present) beside
  `add_phi_path`, and a CLI `phi-denylist add --url <url>`. Matching rule: denied when the URL's host
  equals the entry's host and its path equals the entry's path or continues it at a `/` boundary.
- 02 §2.4 `ingest-findings`: a `phi_encountered` `evidence[]` entry that is an `https://` URL goes to
  `gtm_lists.add_phi_url(url, why="phi_encountered:<run_id>", source="act ingest-findings")`; output
  gains `"phi_urls_added": [...]`; the malformed-finding rule reads "an evidence entry that is neither
  an absolute path nor an `https://` URL". Add 08's A1 test (URL evidence → `url_prefixes` entry; RED
  when the URL branch is removed). Also add `gtm_lists.add_phi_url` to §2.1's `gtm_lists` import line
  and to the A1 row's Consumes (08 already lists it as M's).
- 04 §4.1 G-A `phi-host` rule: also deny a navigate whose URL matches a `url_prefixes` entry; B1
  test: with `{"url_prefix": "https://forms.example.test/r/abc"}`, a GTM-session navigate to
  `…/r/abc/page2` is denied `phi-host` and one to `…/r/abcd` is allowed.
- 06 §6.5b `connectors.http_request` host guard: apply `url_prefixes` the same way (L3 test).

## 39. `07_notices_schedules.md` §7.5 (every seat-dispatch template) and `test_k_prompts.py` — the home fence (08 §8.2 "The home fence", Appendix B #223)

- Every dispatch template in the I/D/W/M/L checklists that dispatches a seat of `GTM_SEATS ∪
  DEPARTMENT_SEATS` other than `gtm-credential-setup` gains a preceding `company.py resolve <slug>`
  step and, on the line after the §8.2 tag, the ```` ```gtm-home ```` fence `{"home": "<that
  output>"}`. The gtm-operator template is exactly tag + home fence + `gtm-ticket` fence.
- `test_k_prompts.py`: assert the fence is present, directly after the tag, in every such template;
  removing it from any one template fails the test. No change to 03 §3.6 `dispatch_brief` (option
  (a) was chosen, not (b)).

## 40. `02_act.md` §2.4 `revert`, `03_schemas.md` §3.7, `05_approver.md` §5.1/§5.5 — reverts under a pause need the signature (08 Appendix B #47, #65; Appendix C item 18)

- 02 §2.4 `revert`: replace "non-money under `DISABLED`/`PAUSE` → the child stops at `awaiting_card`
  + a `card` notice" with: non-money under `DISABLED`/`PAUSE` (any recomputed class, check failures
  included, never-class still `refused`) → step 1 creates an **amount-less approval request bound to
  the child's `after_digest`** (the #50 `_nomatch` mechanism; display lists the failing checks, if
  any) + a `money_card`-style notice, child → `awaiting_approval`; step 2 under `DISABLED`/`PAUSE`
  requires `--approval <request_id>` verified by 05 §5.5 over that request, and never accepts a card
  id. Outside a pause the card path stays for `awaiting_card` children. Add A2 test: under `PAUSE`, a
  child whose `revert <child>` card is answered APPROVE and whose request is unsigned is not executed;
  it executes once signed (RED when the pause branch is replaced by the card check). Plan §20.8/§6.8
  is the source.
- 03 §3.7: admit an amount-less request whose `action_id` is a revert child (`revert_of` set),
  `new_absolute_value: null`, signed over `after_digest`, beside the `_nomatch` case.
- 05 §5.1: display such a request as "Undo <parent action> on <system> (no amount)" with the failing
  checks listed; §5.5: verify it over `after_digest` exactly as for amount-less `_nomatch`.

## 41. `02_act.md` §2.7 `required_lanes` and §2.8 check 9, `03_schemas.md` §3.5 and pack schema, `00_global_paths.md` §0.1 — content rule, structured data, prices (08 Appendix C item 13, #226–#228)

- 02 §2.8 check 9: (a) replace the handler pattern `on[a-z]+=` with
  `(?:<[a-z][^<>]*[\s"'/]|^\s*)on[a-z]+\s*=` (casefolded line); (b) add the structured-data
  exception exactly as 08 Appendix C item 13 states it, with refusal `structured_data_invalid`;
  (c) replace the currency regex with
  `(?i)(?:\$|usd\s?)\s?\d[\d,]*(?:\.\d+)?(?!\d|[,.]\d|\s?(?:[kmb]\b|mm\b|bn\b|million|billion|thousand))`;
  (d) add `price_not_in_source` (a normalized new amount absent from the HEAD blob of the tracked
  file `pricing_source_ref`; `price_source_missing` when that file is not tracked). Add every new
  code to §2.3's refusal list and 08's A1/A2 tests.
- 02 §2.7 `required_lanes`: add `seo` when a patch touches structured data (08 Appendix C item 13's
  definition: a JSON-LD tag line, or any changed line inside a JSON-LD element, body-only edits
  included — which also triggers the post-image JSON-LD tests), and
  `pricing` when a patch changes a currency amount.
- 03 §3.5 `review_lanes.json`: add lane `pricing` with `public_reviewers: ["pricing-economist"]` and no
  gtm-checker entry (so no weekly audit sample); its `reviews[].lines[]` shape: one line per changed
  amount, `check: "price <old>→<new>"`, `note` = `<pricing_source_ref>:<line>`.
- Pack schema (with requests/00_global_paths.md R24): `pricing_source_ref` is a repo-relative path
  (no `..`, not absolute, no wildcard); CSA's `marketing_paths` gains
  `marketing/website/partials/schema-org.html`.
- 00 §0.1 "The `marketing_paths` guardrail": cite 08 Appendix C item 13 for all three (as §26 asks).

## 42. `00_global_paths.md` §0.1 "§20.9c and §20.9a"/"Interim deny" and requests/00_global_paths.md R24 — the OtherApp card (08 Appendix C item 15, #44)

- Treat §20.9c as already ruled; the interim deny is "awaiting the OtherApp path list", not
  "awaiting a YES/NO". The card text is only: "Which OtherApp site paths in the OtherApp repo may the
  GTM team edit?" The deny stays until the paths are named and the gate carve-out lands as its own
  reviewed change (trust-architect review).

## 43. `07_notices_schedules.md` §7.5 W5, `02_act.md` §2.4 `status` — audit sample argv and dispatch (08 §8.5 item 9, #215; **supersedes the argv and dispatch wording of §24 above**)

- 02 §2.4 `status --audit-sample`: argv `--company <slug> --run <cycle id> --audit-sample --lane <lane>
  --days 7`; window end = the cycle record's `started_at` (03 §3.12); `--run` naming no
  `ST/cycles/<id>.json` → exit 3 `cycle_unknown`; N = 0 → exit 0
  `{"result": {"population": 0, "sample_path": null}}`, no file; seed
  `int(hashlib.sha256(f"{run_id}:{lane}".encode("utf-8")).hexdigest()[:16], 16)`.
- 07 §7.5 W5: the `gtm-audit-sample` fence is appended to the lane seat's W5 proposal dispatch; when
  that seat has no W5 dispatch that week, one audit-only dispatch is allowed and counts against
  `budget.dispatch_caps_per_run["weekly"]`; a null `sample_path` is "nothing to sample", not a
  failed step.

## 44. `02_act.md` §2.7 (c) and `04_hooks.md` §4.5 — word-for-word copies of 08 §8.1 (round 9; extends §28)

- Copy 08 §8.1's new "Bounded wait for the row" bullet and the changed `unrecorded` step and refusal
  line (`agent_result_unrecorded` is final after the bounded wait; no caller retries).

## 45. `07_notices_schedules.md` §7.5 "Operator tasks …" and §7.1 chain card; plan (coordinator) — ratification (08 #133, #174, #208, #219, #99, #225; **supersedes §31 above**, which recorded #208 as ratified)

- 07 §7.5: #208 is **pending ratification**, not ratified: ratifier = the next plan-review round,
  required before K's prompts ship; because it also departs from CSA CLAUDE.md's "Operator TASKS …
  go on the relevant tracking GitHub issue's own thread", that round ratifies it only by citing an
  operator ruling on that rule, otherwise K builds the fallback (a non-GTM step filing each open
  `task` notice through `gh_issue.sh`) before its prompts ship.
- 07 §7.1 chain card: name the ratifier (the next plan-review round), required before P1.
- Plan (coordinator, extends §34's ratification list): each item with its ratifier and deadline —
  carry-in card (#174, before MIG), chain card (#133, before P1), `/gtm-onboard`
  `pack_value_unknown` (#219, before P1), `lsa.lead_dispute_submit` T3 (#99, before P1), operator
  tasks as notices (#208, before K's prompts ship), landing-train commit 1 at 14 paths (#225, before
  the train lands).
- Plan §17 (coordinator): record trust-architect's decision on G-B rule a vs CSA's ad-build scripts
  (08 Appendix C item 24 — now a specialist decision plus an `info` notice, not an operator card).

## 46. `02_act.md` §2.4 "`website_static` executor" and `docs/subsystems/gtm.md` (K) — announce and stage-by-name (08 #91)

- Name, in the executor step: `ListAgents` → `SendMessage` every live peer in the home repo (paths,
  rough duration, a window for objections) → `git add -- <every currently-unstaged tracked path>`
  (add only) → gate 3b review/record as its own call → `git -C <H toplevel> commit -F <msgfile> --
  <literal paths>` → announce clear → `complete --commit <sha>`.

## 47. `04_hooks.md` §4 intro/§4.3 — no change requested (08 §9 B1 row, round 9)

- 08's B1 row now says G-W verifies the trust-edit marker only through the `approval_sig.py
  --verify-trust-edit` subprocess (05 §5.5 R38) and lists it in B1's Consumes; the earlier
  `cryptography` wording in 08 is gone. If 04 §4 intro or §4.3 still names `cryptography`, R38 of
  requests/05_approver.md already asks for its removal.

## 48. `OPEN_FINDINGS.md` (coordinator)

- The round-9 08 findings are written in 08: §8.1 (URL evidence, bounded wait), §8.2 home fence,
  §8.3 gtm-operator prompt, §8.4 `resolve_home`, §8.5 items 1/7/8/8a/9, §8.6 (operator tools line,
  top-level policy keys, J's test file), §9 B1/J/K rows, landing train, `pause_carry_in.py` CLI, MIG
  `SRC`, skill rows, Appendix B #44/#47/#65/#91/#99/#123/#133/#172/#174/#177/#205/#208/#213/#215/#219
  and #221–#228, Appendix C items 5, 13, 14, 15, 16, 18, 22, 24, 31. Mark them resolved once §38–§46
  are applied.

## Round 10 — requests from the 08 review-fix pass (2026-09-28)

Applied in 08 this round (no request needed for the text itself): requests/00_global_paths.md R25
(never-list, no pack override, `javascript:`), R26 (OtherApp card on the OtherApp home; carve-out as
a tracked trust-architect issue), R29/R39 (signed operator marker; no marker lifts a `lift_card`
pause; `autonomy --card` withdrawn) and R35 (slot-bound prices) to 08 App C items 13/15/18, #44, #46,
#92, #128, #177, #228 and the §9 rows; requests/07_notices_schedules.md R55 to #206. The requests
below are what other files must change to match.

## 49. `02_act.md` §2.4 (`verify --from-agent`/`--verify-from-agent`, `complete`, `ticket --close`), §2.2b side-store form; `03_schemas.md` §3.19; `07_notices_schedules.md` §7.1 — HIPAA free text, widened (08 §8.1; extends §21)

- For a `regulated ∋ hipaa` company, the §2.2b "HIPAA side-store form" also covers every string
  anywhere inside `verifications[].observed` and `operations[].acting_as_before`/`acting_as_after`
  (and a non-enum `operations[].reason`, which is also malformed). The consumers `verify
  --from-agent`, every `--verify-from-agent`, `complete` and `ticket --close` apply it before
  anything reaches `actions.jsonl`, a notice or a report.
- A1 test (08 §8.1): a 40-character sentence copied from a live `ST/untrusted/` fixture file, placed
  in `verifications[0].observed` and `operations[0].acting_as_after`, leaves no 20-character
  substring in `ST/actions.jsonl` or any notice; RED when either field is dropped from the set.

## 50. `06_connectors.md` §6.4b (`runbook_validate`) and §6.6 (setup scripts) — `target_url` is a pre-token page (08 §8.5 item 11, #232)

- Each `setup_capture` runbook entry's `target_url` is the page before the token is created or
  revealed; the capture script reveals it by an in-script click. New entry field
  `token_rendered_on_load` (bool); a `regenerates: false` script requires it `false`.
- `setup_scripts/<script_id>.navigate_fixture.yml` (WP-E, recorded during probe l, identifiers
  redacted, every `token_pattern` match replaced by `<<TOKEN>>`). `runbook_validate` problems:
  `token_on_navigate_page` (fixture holds `<<TOKEN>>` or a `token_pattern` match),
  `token_rendered_on_load` (`regenerates: false` without `token_rendered_on_load: false`), and a
  missing fixture for a `setup_capture` row → `navigate_fixture_missing`.
- L3 tests as listed in 08 §8.5 item 11.

## 51. `03_schemas.md` §3.4.4 (row table), `02_act.md` §2.8, `05_approver.md` §5.1 display — every plugin install is `$` (08 #53)

- `website_wordpress.plugin_install` becomes `class: money` like `plugin_purchase`, with
  `new_absolute_value` = the listed price read fresh (`"0.00"` for a free wordpress.org listing),
  the one-time-charge `unit`, and a `money_brief` citing the read; a listing that cannot be read →
  exit 3 `plugin_price_unreadable` (retryable). The identity-class free install is withdrawn.
- 05: the approver displays a `"0.00"` plugin install with the plugin name and listing URL.
- A1 test: a free-plugin install proposal reaches `awaiting_approval`, never the identity route
  (RED when the row is left `identity`).

## 52. `07_notices_schedules.md` §7.2 and §7.5 — `daily` under `ST/PAUSE` runs read-only (08 #83)

- §7.2: under `ST/PAUSE`, `daily` starts with `PAUSED=1` (not `skipped-paused`); `weekly`,
  `monthly`, `monthly_load` still skip `skipped-paused` (a recorded deviation from plan §6.8, 08 #83,
  pending ratification — §59).
- §7.5: a "Paused daily run" checklist: read tickets + `verify --from-agent` for already-published
  items, the speed-to-lead and health collectors, the daily trust check, `ingest-findings`; no
  `run-holds`, `propose`, `authorize`, write or setup ticket, or card. `test_k_prompts.py` asserts it.
- D test: a PAUSE fixture's daily run records one `verified` event and mints no write ticket; RED
  when daily is skipped under PAUSE.

## 53. `02_act.md` §2.4 "`website_static` executor" and `complete` — pre-commit staged-blob check (08 #91, #122; extends §46)

- New A2 mode `act.py complete --precommit-check <action_id>` (read-only): for every `after.paths`
  entry, the staged blob (`git -C <H toplevel> rev-parse :<path>`, or absence for a `null`
  post-image) must equal `after.post_image[path]`; else exit 3 `patch_mismatch`, nothing written.
- Executor step order: `apply --index` → announce → stage-by-name → gate 3b review/record →
  `complete --precommit-check` → on refusal `git apply -R --index <stored patch>`, fail the action
  `patch_mismatch`, `SendMessage` the colliding peer; on success `git commit -F … -- <paths>` →
  announce clear → `complete --commit <sha>` (backstop unchanged). K's `docs/subsystems/gtm.md`
  executor step follows.
- A2 test as in 08 #91.

## 54. `02_act.md` §2.9, §2.4 (new `isolation-review`), §2.2b events; `03_schemas.md` §3.10, §3.17, §3.21; WP-G `autonomy_ladder.py` — isolation-hit breakers need a review (08 #121)

- Breaker pause JSON gains `breaker_cause` ∈ {`verify_failure`, `isolation_hit`} and, for the
  latter, `isolation_hit_ids` (03 §3.21 ids). Pre-change breaker files: treated as `isolation_hit`
  when an isolation hit for the company falls in the 7 days before their `ts`.
- New A1 subcommand `act.py isolation-review --company X --hit <hit id> --from-agent <agent id>`
  (write chain policy): §8.1 attestation; `agent_type` `trust-architect` from `spend.jsonl`; exactly
  one `reviews[]` entry with `action_id: "isolation_hit:<hit id>"`, `verdict` pass/fail and ≥ 1
  `lines[]`; appends `isolation_hit_reviewed {hit_id, agent_id, verdict}`. Refusals:
  `unknown_isolation_hit`, `reviewer_not_trust_architect`, the §8.1 attestation codes.
- 03 §3.17 / G `promote`: an `isolation_hit` breaker lifts only when every listed hit has a later
  `pass` review event, besides the 7 clean days. A recorded narrowing of plan §20.6 (§59).
- WP-G test as in 08 #121.

## 55. `02_act.md` §2.7(c) and `04_hooks.md` §4.5 — bounded wait widened (08 §8.1, #222; extends §44)

- The copies say: re-read up to 3 times, 2 s apart (1 initial + 3 re-reads, no fifth read), when
  there is no row **or** the last row's hash differs; a trailing non-JSON line is ignored; then
  `unrecorded`/`mismatch`, both final, no caller retries. Signature `transcript_path: Path | None`;
  the joined final-turn text (not "the last assistant record carrying an opening-fence line").
- Coordinator: 08 Appendix C item 34's three-copy check must pass before A1/B1/K dispatch.

## 56. `00_global_paths.md` §0.3 (slug grammar); `03_schemas.md` pack schema (`identity_provenance`) — (08 App C items 35, 36)

- 00 §0.3: narrow the slug grammar to company.py's committed `SLUG_RE` `^[a-z][a-z0-9-]{1,31}$`
  (and `CYCLE_ID_RE`'s slug part to match); add a contract-literals test that the two strings are
  equal. Until applied, `/gtm-onboard` requires both.
- 03 pack schema: `identity_provenance` keyed `"<list key>:<value>"` → `{source, retrieved_at,
  evidence_ref}`, one per `identity_allowlist.*` value and per `accounts[].account_id`; trust-architect
  reviewer-of-record for a new pack's first commit and every change to `identity_allowlist`,
  `accounts[]`, `brands[].domains` or `identity_provenance`.

## 57. `04_hooks.md` §4.1 (`phi-host`), `06_connectors.md` §6.5b host guard, `03_schemas.md` §3.20 — one PHI URL normalizer (08 §8.1, #231)

- G-A and the connector host guard match `url_prefixes` only through `gtm_lists.phi_url_key(url)`
  (hostname lowercased, userinfo and port dropped; path `""` → `/`, one trailing `/` stripped;
  boundary match `p == e or p.startswith(e + "/")`; a `/` entry denies only the root). B1 test: an
  entry `https://forms.example.test/r/abc` denies `https://forms.example.test:8443/r/abc/`.

## 58. `02_act.md` §2.8 check 9 and §2.4 `complete --commit`; `00_global_paths.md` §0.1 guardrail — extension allowlist, third-party URL rule, `*gtm*` (08 App C item 13, #236)

- Check 9 and `complete --commit` cite App C item 13 for: `MARKETING_EXT_ALLOW`
  (`non_marketing_path` otherwise); the third-party resource URL rule, `<meta http-equiv=refresh>` and
  `<base>` (`tracking_change_not_static`); the `*gtm*` entry narrowed to `gtm-noscript*`, `gtm.js`,
  `gtm-*.js`. 00 §0.1's guardrail header may note the allowlist as a further derived narrowing (it
  restates no pattern).
- 02 §2.8 check 9 and 03 pack schema drop every `marketing_code_paths` mention (R25), if any remain.

### 58a. `02_act.md` §2.11 trail check — `harvest_paths` exit 1 (08 App C item 14)

- `harvest_paths` returns `main`'s codes, including 1 for `had_unresolvable_company`. On any 1,
  `record-external` refuses exit 3 `trail_harvest_failed` (state unchanged, retryable) rather than
  treating the harvest as clean. A2 test: a fixture trail record attributed to a registered slug
  with no trail path → `trail_harvest_failed`; RED when the exit code is ignored.

## 59. Plan `~/.claude/plans/gtm_autonomous_department_plan.md` (coordinator) — round-10 ratification list (extends §45)

Each with ratifier = the next plan-review round:
- #83: `weekly`/`monthly`/`monthly_load` skip under `ST/PAUSE` (daily runs read-only) — before K's
  prompts ship.
- #121: isolation-hit breakers lift only after a recorded trust-architect review (narrows §20.6's
  automatic re-promotion) — before P1.
- §9 `pause_carry_in.py` / MIG: the MIG `ST/PAUSE` operator lift, recorded with the carry-in card
  (#174) — before MIG posts the card.
- App C item 16: plan §0 P1's credential_ref assertion narrowed to `gsm:` refs, as a plan §20.x
  amendment (not a direct edit of §0 P1) — before Wave 2.
- #53 is **not** a deviation (every plugin install is `$`, as plan §20.6 lists it); no ratification.
- Plan §17 (coordinator): record the `playwright-gtm` ToolSearch result (08 §8.6), trust-architect's
  App C item 18 design decision, and the App C item 15 issue number.

## 60. `OPEN_FINDINGS.md` (coordinator)

- The round-10 08 findings are written in 08: §8.1 (HIPAA set, PHI URL normalizer, bounded wait,
  stale-copy note), §8.5 items 8, 8a, 9, 11, 13, §8.6 (tool-name check, J's test source), §9 rows
  A1/A2/B1/G/J/K/L3/E/M, landing train reviewer, `pause_carry_in.py` CLI, MIG, `/gtm-onboard`,
  Appendix A price fixture, Appendix B #44/#46/#53/#83/#91/#92/#114/#120/#121/#122/#128/#174/#177/
  #206/#215/#222/#228 and #229–#237, Appendix C items 13, 14, 15, 16, 18, 19, 28, 34–37. Mark them
  resolved once §49–§58a are applied and item 34's check passes.

## Round 11 — requests from the 08 review-fix pass (2026-09-28)

Applied in 08 this round (no request needed for the text itself): §8.1 (PHI URL normalizer widened
and applied by every consumer; torn/corrupt-line reader rule; hex-shaped fixture agent id), §8.5
items 8, 8a, 9, 11, 13, §8.6 (gtm-analyst grant, J's test sources and rule subset, model_pin_parity
materialization), §9 B1/J/M rows, the seat landing train (1a/1b split, trust-architect for commits
0/1a/1b/2a, the commit-0 `check_consistency` read), `pause_carry_in.py` (per-entry `state`, legacy
`lift_card` refusal, `answered_card` error map, ctx seams, `not_carried`), MIG (legacy operator
queue, failure branch, minimum set, marker-only lift, per-subcommand args), `/gtm-onboard`'s precheck
test, Appendix A (`other-company` second brand, item 16 status), Appendix B #11, #46, #100, #123, #172,
#174, #175, #222, #224–#226, #231, #233, #234 and #238–#244, Appendix C items 5, 13, 14, 16, 27–29,
31, 38, 39. The requests below are what other files must change to match.

## 61. `04_hooks.md` §4 (`gtm_hooklib.phi_url_hit`), §4.1 rule 3, §4.2 rule j, §4.4 rule 2; `06_connectors.md` §6.5b host guard — one PHI URL normalizer, every consumer (08 §8.1, #231; extends §57)

- `phi_url_hit` (2) matches `url_prefixes` **only** through `gtm_lists.phi_url_key(url)` (08 §8.1:
  hostname lowercased, one trailing `.` stripped, IDNA-encoded, port/userinfo dropped; path `""` →
  `/`, `urllib.parse.unquote`, runs of `/` collapsed, RFC 3986 §5.2.4 dot segments removed,
  casefolded, one trailing `/` stripped except the root; match `U == P or U.startswith(P + "/")`).
  Remove 04's own inline normalization so there is one implementation. **Reconcile one difference
  in 08's favour:** 04 today matches every URL on the host when `P == "/"`; 08 (round 10, kept) makes
  a `/` entry deny **only the root page** — denying a whole host is the reviewed
  `gtm_lists.py phi-denylist add --host` entry. A `ValueError` from `phi_url_key` on a URL being
  **matched** is a hit (deny), not `None`.
- The same predicate is applied, in GTM scope, by G-A rule 3 (browser tools), the path gate's
  WebFetch rule 2, G-B rule j for the URL operands of `curl`, `wget` and interpreter fetches
  (`python3 -c`/`-m` with an `http(s)://` literal), and the connector host guard (06 §6.5b).
- B1 tests: a GTM-session `WebFetch` of `https://forms.example.test/r/abc/page2` with the entry
  `https://forms.example.test/r/abc` present → denied `phi-host` by path-gate rule 2; `curl -s
  https://forms.example.test/r/%61bc` → denied by G-B; `browser_navigate` to
  `https://forms.example.test./x/../r/abc` → denied by G-A; each RED when that consumer matches hosts
  only or uses its own normalization.

## 62. `04_hooks.md` §4.5 (`gtm_ticket_release.py`) and `02_act.md` §2.7(c) — torn and corrupt `agent_results.jsonl` lines (08 §8.1 "Bounded wait", #222; extends §44/§55)

- Writer: under `S/agent_results.lock`, when the file is non-empty and does not end in `\n`, the hook
  writes `"\n" + row + "\n"`, else `row + "\n"`. B1 test as in 08 §8.1 (torn tail `{"ts": "2026`, then
  the fixture payload → the last line is exactly the expected row).
- Reader copies (02 §2.7(c), 04 §4.5): `extract_gtm_result` skips **every** line that does not parse
  as a JSON object, wherever it is; the round-10 wording "a non-JSON line anywhere else makes the read
  `unrecorded`" is withdrawn. Appendix C item 34's three-copy check covers this sentence too.

## 63. `04_hooks.md` §4.1 (G-A) — `browser_network_request` and `filename` arguments on `playwright-gtm` (08 §8.5 item 11, §8.6, #241)

- G-A always denies `mcp__playwright-gtm__browser_network_request` (any seat, any ticket), with a new
  reason `network-request-detail` (the tool returns full request headers and body, plan §20.6 NEVER
  "any secret in a tool call/transcript"). Remove it from §4.1's ticketless-read list (lines listing
  it next to `browser_network_requests`).
- **(Revised round 12.)** G-A denies any `playwright-gtm` tool call whose input has a non-null
  `filename` key (`filename-arg`), on every tool (`browser_network_requests`, `browser_snapshot`,
  `browser_console_messages`, `browser_take_screenshot`, …). The round-11 `/`/`..`/absolute-only rule
  (`filename-path`) is withdrawn: the installed playwright-core resolves `filename` against the client
  workspace and accepts any path inside either the output dir or that workspace, so a bare name such
  as `"OPERATOR_DECISIONS.md"`, `"CLAUDE.md"` or `".gitignore"` writes page-controlled text into the
  home root, where G-W cannot see it. No seat needs `filename`; screenshots and snapshots default to
  the output dir. A bare file name is **not** allowed.
- B1 tests: `browser_network_request` from gtm-analyst under a read ticket → denied; `browser_snapshot`
  with `filename: "OPERATOR_DECISIONS.md"` → denied `filename-arg` (RED under the round-11
  `/`/`..`/absolute-only rule), and with `"../x.yml"`, `"/tmp/x.yml"`, `"a/b.yml"` and `"snap.yml"` →
  each denied; `browser_snapshot` with no `filename` key (or `filename: null`) → allowed; each RED
  when its clause is removed. If request detail is ever needed, a
  G-A-enforced `part` allowlist excluding headers, cookies and body comes with its own B1 test first.

## 64. `03_schemas.md` pack schema and §3.4.1 kinds — `identity_allowlist.user_emails` (08 §8.5 item 8a, App C item 38, #242)

- Add the optional list `identity_allowlist.user_emails` (whole addresses, casefolded,
  `^[^@\s]+@[^@\s]+\.[^@\s]+$`, no duplicates), each value requiring an `identity_provenance` record
  `"user_emails:<address>"` (App C item 35); trust-architect reviewer-of-record for any change.
- §3.4.1 `email` kind: name `user_emails` as the list the "whole address" branch reads (it is part of
  the `identity_allowlist.*` union already); a public mail domain stays refused in
  `identity_allowlist.domains`, and a provider domain such as `iam.gserviceaccount.com` is never a
  pack domain. The `identity` bucket normalization compares `user_emails` casefolded.
- `system_names.identity_bucket` needs no entry (no tier system's ids live there).

## 65. `02_act.md` §2.1 file table (`project_dirs.py` row) — cross-reference (08 App C item 14(a))

- Replace "the coordinator's relocation (08_seats_wps.md Appendix C item 33)" with "the coordinator's
  relocation (08_seats_wps.md Appendix C item 14(a))". Item 33 is "Inbox kind per home"; item 14(a)
  now creates `tools/gtm/project_dirs.py` and makes `harvest_tool_trail` import and re-export from
  it, exactly as 02 §2.1 decided. 04_hooks.md already cites item 14.

## 66. `02_act.md` §2.8 check 9 and §2.4 `complete --commit`; `00_global_paths.md` §0.1 guardrail — the inline-handler rule is parsed (08 App C item 13, #226)

- Check 9 and `complete --commit` cite App C item 13's round-11 rule: parse the post-image (and, for
  `−` lines, the pre-image) with stdlib `html.parser.HTMLParser`; refuse any start tag whose source
  span touches a changed line and carries an attribute name matching `^on[a-z]+$`
  (`tracking_change_not_static`); a parser exception or non-UTF-8 file refuses the same way. Drop any
  copy of the round-9 regex `(?:<[a-z][^<>]*[\s"'/]|^\s*)on[a-z]+\s*=`.
- A1/A2 tests: `  alt="x" onload="x()">` added inside an existing multi-line `<img` tag and
  `<a href="#" title="a>b" onclick="x()">` are each refused; the `content=` and `aria-controls=`
  pass tests stay.

## 67. Plan `~/.claude/plans/gtm_autonomous_department_plan.md` (coordinator) — round-11 ratification list (extends §45, §59; gated by 08 App C item 39)

Each with ratifier = the next plan-review round, as a plan §20.x entry naming the 08 entry:
- #11 (round 11): the orchestrating session may draft `website_static.page_edit` as an unverified
  drafter (`propose --file`/`--patch`), departing from plan §6.5 and §4.3 — **before P1**. If
  refused: `website_static.page_edit` leaves `FILE_PROPOSE_ROWS` and a 02 change requires
  `--from-agent` naming an `implement`/`gtm-drafter` agent whose attested `gtm-result` carries the
  patch.
- #225 is **withdrawn**: the seat landing train is ≤10 paths per commit (1a/1b split); remove it from
  §45's list.
- #238 (not a deviation, recorded for the owner's view): OtherCompanyB's C7 scoped lift is carried in
  as a `remaining_pause`, which holds the reversible work C7 allowed until the operator lifts the
  pause. **Future, not required:** a row-scoped pause exemption (a pause-file key such as
  `exempt_rows` with the `class_o_batches`-style bound, 03 §3.10, `pauses.blocking`) would carry a
  scoped lift faithfully; it is a design item for trust-architect, not a card.
- App C item 39: the coordinator checks each listed deviation's §20.x entry before its gated step and
  records the check in `OPEN_FINDINGS.md`.

## 68. `02_act.md` §2.4 `pause`/`resume` tests — C7 as fixture text only (08 §9 `pause_carry_in.py`, #46)

- 02's two-pause `pause --lift-card` test may keep `C7` as a **fixture** card id (a card posted through
  `card-post` in the test). For the real OtherCompanyB carry-in, C7 is an already-answered legacy card
  and is never a `lift_card` (08 #238); where 02's prose uses "A0022 … lifts only by C7" as the
  OtherCompanyB example, reword it to "a migration pause naming a posted, unanswered `lift_card`".

## 69. `OPEN_FINDINGS.md` (coordinator)

- The round-11 08 findings are written in 08 (list at the top of this round). Mark them resolved once
  §61–§68 are applied and App C item 34's three-copy check (now including §62's reader sentence)
  passes; record App C item 39's per-step ratification checks there as each gated step comes up.

## Round 12 — requests from the 08 review-fix pass (2026-09-28)

Applied in 08 this round: §8.5 item 11, §9 B1 row and Appendix B #241 (any non-null `filename` on a
`playwright-gtm` tool is denied; §63 above revised in place); Appendix C item 13 inline-handler rule,
its A1/A2 test and Appendix B #226 (whole-file handler multiset). The request below is what other
files must change to match.

## 70. `02_act.md` §2.8 check 9 and §2.4 `complete --commit`; `00_global_paths.md` §0.1 guardrail — whole-file handler multiset (08 App C item 13, #226; extends §66)

- Alongside §66's span test, check 9 and `complete --commit` parse the **full pre-image and full
  post-image** of every patched content file with the same `html.parser.HTMLParser` and collect the
  multiset of `(tag, sorted tuple of (name, value) for every attribute matching ^on[a-z]+$)` over
  every start tag (`handle_starttag`/`handle_startendtag`) carrying at least one such attribute; when
  the two multisets differ, refuse `tracking_change_not_static`. A new file's pre-image and a deleted
  file's post-image are empty. Reason: removing a `<!--`/`-->` pair or a raw-text wrapper
  (`<textarea>`, `<noscript>`, `<script>`, `<style>`) around an untouched `<img src=x onerror=…>` line
  brings the handler to life without any `+`/`−` line in its span.
- A1/A2 test: pre-image lines `<!--`, `<img src=x onerror="x()">`, `-->`; a patch removing only the
  `<!--` and `-->` lines is refused `tracking_change_not_static` (RED under the span-only rule); same
  with `<textarea>`/`</textarea>` as the removed wrapper.
