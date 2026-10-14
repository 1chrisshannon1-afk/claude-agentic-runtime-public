> **STATUS 2026-09-28 (updated after wave1e): this list is superseded and the contracts are NOT frozen.**

**Freeze record (2026-09-28, after the wave1e final verification):** the one blocker it found
(07's caps-check command carried the withdrawn `-X pycache_prefix=S/pycache` token, which 05 §5.5
step 0 (3) refuses, so no scheduled session could start) is FIXED in 07 (three sites) and 00's
`S/pycache/` row is withdrawn; 08's stale `<fresh mkdtemp>` token is fixed. Still open, for the work
packages to settle in code and tests (contract text updated in the same change):
- R43 asks 02 to map a `claude_dir()` refusal to exit 3 `claude_dir_in_agency`; 02 has no such code yet.
- 08's M5 K test ("precheck passes on the real tree") fails until H2 lands the gtm-operator /
  gtm-credential-setup templates — K must be ordered after H2.
- `gtm_tmp_root()` realpaths `TMPDIR` with no Agency refusal; add a text refusal falling back to
  `/tmp`, or add `TMPDIR` to G-B rule m.
- The JSON file `~/.claude/plans/gtm_contracts_open_findings_2026_09_28.json` is a HISTORICAL
  snapshot (written before wave1d/wave1e), not the list of record; this status block is the record.
> Later review rounds (wave1b–wave1e) resolved many of the items below and found new ones. The
> open list of record is kept privately at `~/.claude/plans/gtm_contracts_open_findings_2026_09_28.json`
> (keyed by section file; it names real companies, so it stays out of this folder); the per-finding
> bodies below this block are the older round-4 list, kept for reference.
>
> **Wave1d fixed (applied across sections; its own fixes were then reviewed, and wave1e fixed the
> defects that review found):** the `/.vol` kernel-alias arm of `canon_aliases` and the
> `VOLFS_SENTINEL` fail-closed rule (00 §0.1); `resolve_home()`/`_entry_root_path()` running
> `register`'s symlink walk (00 §0.1); `claude_dir()` refusing an Agency result on both branches
> (00 §1.1); R77 applied in 04 (isolated-subprocess temp root, rule m's `-X` clause, the
> `ticket_cancelled` `who` filter); the authored `resulting_status` field as the enable-binding stop
> exemption (05 §5.5 step 3b); 05's test-footprint oracle narrowed; 08's WP table and seat landing
> train corrected against the real tree.
>
> **Wave1e fixed (this pass; every change was propagated to the other contract files and
> `requests/*.md` that use the same term):**
> - B1 `claude_dir()`'s HOME branch was a tautology (checked `HOME` against its own `Desktop/OtherApp`,
>   so it raised on every production call). It now checks the candidate `HOME/.claude` against
>   `real_agency_root()` only, with a "HOME == real_home() does not raise" control test (00 §1.1;
>   R43 amended; 04's stdlib `_claude_dir` copy; 08 App. C item 14).
> - B2 the isolated-subprocess temp root disagreed between 04 (`gettempdir()/gtm_isolated`) and 05
>   step 0 (3) (`realpath(TMPDIR or /tmp)`), so every isolated child would exit 11. 04 now uses 05's
>   body with each prefix directly under it; R64 (a) withdrawn; 00's export table lists
>   `gtm_tmp_root` and `git_show_head`; every `<fresh mkdtemp>` became `<fresh P>`; 02's act.py
>   re-exec text aligned with 05 (`os.mkdir`/`os.rmdir`, no `tempfile`).
> - B3 the approver dialog variant and §5.8's close rule used verb tokens (`change_kind`). Both now
>   read `display.resulting_status` (the row's authored field); any value other than
>   `paused`/`removed` never shows "stop spend". `change_kind` withdrawn (R76 (b)); 03 §3.7 carries
>   the key; A2 tests with a `remove_end_date`-shaped row.
> - M1 the `resolve_home` `.nofollow` expectation corrected to `kernel_path_alias` (00; R43).
> - M2 R43 amended (`.vol`, the walk, the HOME branch); R44 filed and applied: 04's `canon`,
>   `path_is_or_under` and the three Agency rules fail closed on `VOLFS_SENTINEL`; 08 App. C item 14
>   lists the wave1c–wave1e additions.
> - M3 `resulting_status` added to 03's tier-row schema (required on every `money: true` or
>   `commits_on_enable: true` row, else refused at load); R84 redefined by it; 04 rule 9d and 06 §6.2
>   state stops are never enable-bound.
> - M4 `ticket_cancelled` excludes every agent-class `who` (R77 (a) and 05's classes), reuses rule
>   7a's pre-lock verification (never calls `verify_ticket` under `tickets_lock`), treats a raising
>   verification as "filter not applied" (cancel); rule 6b runs inside the lock (04 "Ticket
>   authenticity" reconciled with "One critical section"); 03 §3.11 states the `who` classes.
> - M5 the three sonnet seats' missing templates are by design (their agent files opt out of
>   dossiers); `/gtm-onboard` exempts them via `NO_DOSSIER_SEATS`; H2 is 8 files, not 11;
>   PLACEHOLDERS.md already has a GTM section.
> - M6 the test-footprint oracle gained clause (iii) (content check of the fixed-name
>   `S/trust_edit_allow.json`); oracle tests use the fixture slug, never a real slug; 05's trust-edit
>   mtime assertion reconciled; R88 amended.
> - n1 `VOLFS_SENTINEL` and the `.vol` arm are in 00's export table. n2 04 `machine_written` states
>   the `gtm_slugs()`-raises fallback (deny under `S`) and the unreadable-pack mirror residual. n3 rule
>   m's `-X`-after-script over-denial is stated as intended.
>
> **Still open (known, not fixed in wave1e):**
> - 05 §5.9 deviations V1–V6 are UNRATIFIED and block WP-A2 (R81/R85 — planner/operator ruling needed).
> - `gtm_env.approver_app_path()` (R37) is still absent from 00 (WP-C/WP-A2 prerequisite).
> - 03 §3.7 has no `display.operator_executes` key yet (R76 (c)); 06 has no
>   `connector_dispatch.owner_execution_reason` (R78).
> - 03 §3.11 still says act.py writes a `card_deny` marker, contradicting R76 (e) (harmless to the
>   `who` filter — `card_deny` is agent-class either way — but the writer statement is stale).
> - 02 §2.11 does not yet compare `observed.status` for pause/remove closes (R55 via 05 §5.8).
> - 00 §1.5 has not adopted 05's test-footprint oracle for 02/04/07 tests (R88).
> - The committed tier table's rows must each be authored with `resulting_status` (A1); until then
>   the new load-time refusal refuses the table.
> - No wave1e fix has had an independent review yet; the next step is one review pass over the
>   wave1e edits, then freeze.

# Open findings — GTM Wave-2 contracts (last review round)

Every finding from the last contracts review round (round 4 of 4: `fidelity` lens 4 blockers / 12 majors, `implementability` lens 3 blockers / 9 majors; 49 findings in all). None is resolved by the split: splitting `CONTRACTS.md` changed no meaning, so the findings below are the round-4 historical list; most were resolved in wave1b–wave1e (see the status block above).

Source: the review workflow output `result.contracts.lastReviews[*].findings` (`/private/tmp/claude-501/-Users-x-Desktop-ExampleApp/aadd7f25-c07e-448d-9b62-e0ea6822ac8b/tasks/wm643g4sc.output`). The `Where`, `Issue` and `Fix` texts are copied verbatim from the reviewers.

## How to read this

- **IDs:** `FID-nn` = fidelity lens (against the plan and committed code), `IMP-nn` = implementability lens (can parallel WPs build from it). The number is the finding's position in that reviewer's list.
- **Tagging:** each finding is listed under every section file its `Where` names. A finding that spans files is marked **CROSS** and names the other files; its full text appears once, under its first-named file, and every other file carries a short pointer entry.
- **Section numbers did not change in the split.** "CONTRACTS.md §3.4.4" in a finding is now `03_schemas.md §3.4.4`. A bare `§N` numbering follows the same file map: §0–§1 → `00_global_paths.md`, §2 → `02_act.md`, §3 → `03_schemas.md`, §4 → `04_hooks.md`, §5 → `05_approver.md`, §6 → `06_connectors.md`, §7 → `07_notices_schedules.md`, §8, §9 and Appendices A–C → `08_seats_wps.md`. "plan §N" is the plan, not a contract file.
- **`L<n>` line numbers** refer to the pre-split 3,870-line `CONTRACTS.md` (some predate its final edits and are approximate). Original line ranges per file: `00_global_paths.md` L1–L338; `02_act.md` L339–L1081; `03_schemas.md` L1082–L2174; `04_hooks.md` L2175–L2705; `05_approver.md` L2706–L2878; `06_connectors.md` L2879–L3071; `07_notices_schedules.md` L3072–L3398; `08_seats_wps.md` L3399–L3870 (L1–L2 was the old title).

## Count by file

| File | Covers | Blockers | Other | Total (CROSS included) |
|---|---|---|---|---|
| [`00_global_paths.md`](00_global_paths.md) | §0–§1 global rules, paths, environment, test isolation | 1 | 4 | 5 |
| [`02_act.md`](02_act.md) | §2 act package | 6 | 15 | 21 |
| [`03_schemas.md`](03_schemas.md) | §3 data schemas | 6 | 13 | 19 |
| [`04_hooks.md`](04_hooks.md) | §4 hook contracts | 0 | 13 | 13 |
| [`05_approver.md`](05_approver.md) | §5 approver protocol | 1 | 2 | 3 |
| [`06_connectors.md`](06_connectors.md) | §6 connector interface | 2 | 3 | 5 |
| [`07_notices_schedules.md`](07_notices_schedules.md) | §7 notices, runners, schedules | 0 | 8 | 8 |
| [`08_seats_wps.md`](08_seats_wps.md) | §8 seats, §9 WP table, Appendices A–C | 0 | 11 | 11 |

## 00_global_paths.md — §0–§1 global rules, paths, environment, test isolation

### IMP-03 · blocker — **CROSS** (also `02_act.md`, `03_schemas.md`)

- **Where:** §2.3 exception (2) 'operator terminal = env CLAUDECODE unset and sys.stdin.isatty()' (L522-524); used by `resume` (§2.4, §3.10) and `autonomy` (§2.4, §3.17); also the CLAUDE_GTM_COMPANY env identity (§1.4)
- **Issue (first sentence):** B-3: The 'operator terminal' test is the only thing, besides a lifting card, that lets `resume` remove an operator, breaker or migration pause, and that lets `autonomy --level autonomous` leave shadow.
- **Full text (issue and fix):** under IMP-03 in the `02_act.md` section of this document.

### IMP-04 · regression — **CROSS** (also `04_hooks.md`, `08_seats_wps.md`)

- **Where:** §4.2 G-B rules c/k (scope 'all'); B2 wiring in §4.7/§4.9; §1.5 item 7; Appendix C item 19
- **Issue (first sentence):** M-1: G-B goes live mid-Wave-2 and blocks the implementers themselves.
- **Full text (issue and fix):** under IMP-04 in the `04_hooks.md` section of this document.

### IMP-08 · regression — **CROSS** (also `08_seats_wps.md`)

- **Where:** §0.3 chain anchor (L166-181) + Appendix C item 7 vs `tools/gtm/backup_state.py backup_company` (tars `backup_set()` in order, home `.claude/gtm/state` first, runtime state after, without any lock)
- **Issue:** M-5: A backup can capture the log and its anchor at different moments. `store.append` rewrites `S/chain_anchors/<slug>.json` under the actions lock, but a backup tars `ST/actions.jsonl` and then the anchor without taking that lock. If an append lands between the two (W8 runs weekly inside a session while the 15-minute holds job runs `run-holds --all`), the archive holds an older log beside a newer anchor. Restoring it reads as `chain_truncated`, so the restore writes a false PAUSE.chain — exactly what item 7's test is meant to rule out.
- **Fix:** In App. C item 7, require `backup_state.py` to take `ST/actions.lock` (same timeout as act.py) while it copies `actions.jsonl` and the anchor together, or snapshot both under the lock before tarring. Add a test that injects an append between the two members.

### IMP-17 · missing-docs — **CROSS** (also `03_schemas.md`, `07_notices_schedules.md`, `08_seats_wps.md`)

- **Where:** Exit-code tables: §3.12 cycle.py, §1.2 gtm_lists.py, §3.19 validate_run.py, §3.23 outside_actor.py, §3.17 autonomy_ladder.py, App. C 7 vs backup_state.py, §7.6 gtm_session.sh
- **Issue (first sentence):** m-5: Several tools are missing standard exit codes.
- **Full text (issue and fix):** under IMP-17 in the `03_schemas.md` section of this document.

### IMP-21 · missing-docs — **CROSS** (also `07_notices_schedules.md`)

- **Where:** §7.3 plist calendar vs §0.3 company-local HHMM
- **Issue (first sentence):** m-9: Plist times and company times can differ.
- **Full text (issue and fix):** under IMP-21 in the `07_notices_schedules.md` section of this document.

## 02_act.md — §2 act package

### FID-01 · blocker — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §2.6 'Card rule' (L767-783), §2.5 awaiting_card row (L663), §2.11 'approval' kind (L1040-1043), §2.4 resume (L594) and autonomy (L603), §3.17 (L1862-1863)
- **Issue:** A card only has to be answered. The contract never reads what the answer says. `cards.answered_card` accepts any `**Operator answer (verbatim…):** "…"` line. `record-external --kind approval` then re-runs the checks and appends `authorized`, so an operator answer of "No, don't do this" authorizes a shared-system action, and the same holds for owner-listen, a non-money revert, a migration pause and chain-repair. `resume` without a `lift_card` passes when the card's archived block (which includes the question text) contains the pause file name. `autonomy --card` passes when the block contains the word `autonomous`. So a card asking "Should OtherCompanyB go autonomous?" and answered "No" ends shadow, and a card saying "keep PAUSE.gbp in place" lifts that pause. Plan §6.1(b) requires a *go-ahead*. This mechanism records refusals as approvals.
- **Fix:** `card-post` should write every card that gates something with a fixed decision grammar: a required `Decision options: APPROVE | DENY` line plus a machine token naming the subject (e.g. `subject: resume PAUSE.gbp@remodeling` or `subject: autonomy other-company autonomous`). `cards.answered_card` returns `decision ∈ {approve, deny, unclear}`, parsed only from the operator-answer line: it starts with an approve token (`yes`, `approve`, `approved`, `go`), case-insensitive, with no negation token. Every consumer (record-external approval/owner_listen, resume, autonomy, chain-repair, non-money revert, migration pause, outside_actor classify) proceeds only on `approve` whose card subject token equals the requested subject. `deny` moves `awaiting_card` to `denied`; `unclear` leaves the state unchanged. Add A2 falsification tests: a 'No' answer, and a 'Yes' on a card about a different pause, both refuse.

### FID-02 · blocker — **CROSS** (also `03_schemas.md`, `06_connectors.md`)

- **Where:** CONTRACTS.md §2.8 check 1 (L836-844), check 2 (L845-847), §3.4.4 rows `*.asset_link` (L1388), `*.user_add/user_role_edit` (L1386), `L.claim_submit` (L1362); §6.2/§6.3 (connector target selection)
- **Issue:** Isolation is weaker than plan §6.3/§7 ("create/modify anything whose account_id/page/location/domain fails §7 → NEVER"; "link/claim/share/connect … NEVER if cross-company"). Check 1 matches only `account_id` against the pack's own identity values. `target_ref` is checked only negatively (not another pack's domain or id), so an unlisted third-party page, location or property passes. Structured targets are not checked at all: `asset_link` `after.value.target_id`, `user_add` `after.value.email` and `claim_submit` `listing_url`. Check 2 scans only 'after text'. Since card O2 exists because identifier lists are known to be incomplete, linking this company's Ads account to an unknown other business's GA4 property, or adding an outside user, is classed `identity` and executes autonomously after a 24 h hold. §6.2 also never says a connector must derive its target from the pack account rather than from the proposal's `target_ref`.
- **Fix:** Make check 1 a positive allowlist. Every platform object id embedded in `target_ref` (parsed per system) and every id-typed `after.value` key (`target_id`, `list_id`, `level_id`, `campaign_id`, `ad_group_id`, `listing_url`, `page_ref`; email domains for `user_*`) must be one of this pack's identity or account values, or a value declared in `shared_identifiers` (then class `shared`). Anything else is class `never` with `card_on_refuse: true`, so the operator can add it to the allowlist through a reviewed pack change. Add a per-row `id_fields` list to the tier table so the validator knows which keys to check. State in §6.2 that `apply()` resolves the platform object from `ctx.account` plus these verified ids, never from free `target_ref` text. P2 falsification tests: `asset_link` with an unknown `target_id` is refused; `user_add` with a non-company email domain is refused unless listed.

### FID-04 · blocker — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §2.4 `website_static` executor (L624-642), §3.2 (L1155-1156: `after.paths` + `summary`), §3.4.4 row `website_static.page_edit` (P fields), §2.4 `propose --file` (FILE_PROPOSE_ROWS), §2.8 checks 2–4/9
- **Issue:** For `website_static`, maker-checker and the content checks bind nothing. The reviewed `after` is only `{paths, summary}`, so the specialist lanes (brand, claims_voice, cta_link, seo) review a summary and the §2.7 digest covers the summary. Checks 2–4 (other-business NAP, claims policy, AI provenance) run on the summary. Then the main session writes the actual content after review. That session is an unverified `--file` drafter that reads untrusted text. `complete --commit` checks only that the paths are a subset of `after.paths`. A new banned claim ('licensed and bonded') or another company's address can land on a public site with every lane 'passed'. This contradicts plan §6.5 ('any change to after … invalidates all reviews') and §6.6 ('checks computed by act.py, not by reviewers alone'). The contract's reason, that repo gate 3b reviews the diff, substitutes a code-reviewer for the MASTER §6.1 specialist lanes. It also diverges from plan §4.3 (dispatch `implement` from an approved proposal). The deploy ask-gate is never addressed: the action is marked `completed` at commit, before anything is live, so the day-after verify fails and trips a breaker.
- **Fix:** Make the reviewed object the exact change. `after` carries `{paths, summary, patch_sha256}` plus the unified diff stored at `ST/review_briefs/<id>.patch`, and specialists review that brief. `checks.run_all` runs checks 2–4 over the added lines (and any asset files) of the patch. `complete --commit` requires `git diff <sha>^ <sha> -- <paths>` to hash to `patch_sha256`, else it refuses `patch_mismatch`. Either make the edit an `implement` dispatch that applies exactly the reviewed patch (plan §4.3), or keep the main session but require that it only `git apply`s the stored patch. Add a state or verify rule for deploy: `completed` = committed, and the day-after verify for `website_static` is skipped until a recorded deploy event, so the deploy ask-gate (an operator go-ahead) is explicit and the breaker is not tripped by an undeployed commit.

### IMP-01 · blocker

- **Where:** CONTRACTS.md §2.3 Command dataclass (L501-515) vs §2.4 `ticket`/`run-holds` rows and the chain_policy list (L607-613)
- **Issue:** B-1: The command registry can't describe two of A2's commands. `Command.chain_policy` and `Command.company_from` are fixed per command, but the contract makes both depend on flags. `ticket --read/--show/--close <read ticket>` is `read` policy, while `ticket --write/--write-batch/--setup/--close <write ticket>` is `write` policy. That policy also decides the not_gtm_session rule and whether dispatch runs reconcile/ingest. `run-holds` is `flag` with `--company` but `none` with `--all`. With `none` there is no slug, so `make_ctx`, the trust-root check, `verify_chain`, reconcile and `run(args, ctx)` have no Ctx. A2 cannot register `ticket` or `run-holds` correctly against A1's API, and A1 cannot write dispatch without knowing how.
- **Fix:** In §2.3 let `chain_policy` and `company_from` be either a string or a `Callable[[argparse.Namespace], str]` that dispatch calls after parsing. For `run-holds --all`, say that dispatch loops over `gtm_slugs()` and runs the whole per-company pipeline (make_ctx → trust root → verify_chain → ingest → run) once per company, then prints one JSON object whose `result` is keyed by slug. Also say how an exit code is chosen when companies differ. Add an A1 test for each variable-policy command.

### IMP-02 · blocker — **CROSS** (also `03_schemas.md`)

- **Where:** §3.4.1 row-id grammar (L1205) and the §3.4.4 row table (L1309-1390); consumed by H2 drafter primers, L runbooks/manifests `write_rows`, the §2.10 verb map, and §2.4's `action ∈ {read, export, snapshot}` refusal
- **Issue (first sentence):** B-2: A row id is `<system>.<object_class>_<action>`, but object classes and actions both contain underscores, so an id doesn't say how to split it.
- **Full text (issue and fix):** under IMP-02 in the `03_schemas.md` section of this document.

### IMP-03 · blocker — **CROSS** (also `03_schemas.md`, `00_global_paths.md`)

- **Where:** §2.3 exception (2) 'operator terminal = env CLAUDECODE unset and sys.stdin.isatty()' (L522-524); used by `resume` (§2.4, §3.10) and `autonomy` (§2.4, §3.17); also the CLAUDE_GTM_COMPANY env identity (§1.4)
- **Issue:** B-3: The 'operator terminal' test is the only thing, besides a lifting card, that lets `resume` remove an operator, breaker or migration pause, and that lets `autonomy --level autonomous` leave shadow. Any agent with Bash can fake it: `env -u CLAUDECODE script -q /dev/null python3 …/act.py resume --company X …` (or `python3 -c 'import pty; pty.spawn(...)'`) gives it an unset CLAUDECODE and a pty. No G-B rule denies `script`, `env -u CLAUDECODE`, `unset CLAUDECODE` or pty spawning, and a denylist of spellings can't close the hole anyway. This defeats the plan §6.4 rule that 'a PAUSE file beats any standing approval'. The GTM-session identity (`CLAUDE_GTM_COMPANY=… python3 act.py …`) can be forged inline the same way. This is security design, so trust-architect should review it; I'm reporting it here.
- **Fix:** Replace the TTY/env test with a single-use, operator-created marker, the same pattern §4.3 uses for `trust_edit_allow.json`. Example: `S/operator_ack.json` `{"command", "company", "target", "created_at"}`, under 15 minutes old, deleted on use, which G-W, G-B rule c and G-B rule k already stop agents from creating. Or route owner-pause lifts and leaving shadow through GTMApprover, which is Appendix C item 18's question. Add a P2 falsification test that the `script`/`env -u` spelling is refused.

### IMP-09 · regression

- **Where:** §2.11 card-authorship scan (L1047-1053); used by record-external, chain-repair, resume --card, autonomy --card, outside_actor classify
- **Issue:** M-6: The card-authorship scan is too large. When no posting record exists it scans every transcript whose mtime falls in the trailing 30 days; otherwise it scans from post time to now. Measured on this machine today: `~/.claude/projects` is 21 GB with 19,947 transcript files modified in the last 30 days. Each card-gated command would read gigabytes, run in-process inside act.py and under the actions lock, which risks the 30 s lock timeout (exit 12). This does not scale.
- **Fix:** Have `transcript_index.refresh()` record, per file, the byte offsets or tool_use lines of Write/Edit/MultiEdit/NotebookEdit/Bash calls that name any operator-input file (an incremental side index). The authorship scan then reads only those lines. Or bound the scan to GTM-home project dirs plus the session that archived the card. State a latency budget and test it on a generated corpus.

### IMP-11 · regression — **CROSS** (also `06_connectors.md`)

- **Where:** §6.2 idempotency (L2932-2935) vs §2.4/§2.5 (`failed` ∈ AUTHORIZE_FROM, re-execution)
- **Issue (first sentence):** M-8: A failed connector write can never be retried.
- **Full text (issue and fix):** under IMP-11 in the `06_connectors.md` section of this document.

### IMP-12 · regression — **CROSS** (also `07_notices_schedules.md`)

- **Where:** §7.5 checklists I3, I9, W3, D5, D6, L2 vs §2.4 `company_from` (L607)
- **Issue (first sentence):** M-9: Several of K's required commands will exit 2.
- **Full text (issue and fix):** under IMP-12 in the `07_notices_schedules.md` section of this document.

### FID-06 · risk

- **Where:** CONTRACTS.md §2.3 'operator terminal = CLAUDECODE unset and sys.stdin.isatty()' (L522-524); used by resume (L594), autonomy (L603), pause created_by operator
- **Issue:** Any agent with Bash (orchestrating session, director, specialists) can satisfy the 'operator terminal' test: `env -u CLAUDECODE script -q /dev/null python3 …/act.py resume …` gives a pty with the variable unset. That lifts the owner A0022 website pause (plan §6.4: 'lifted only by card C7's answer'), breaker pauses and shadow, all without a card. G-B has no rule for it. For the trust-file edit the contract rejected an equally weak mechanism (F16) and used an operator-created marker under `S`.
- **Fix:** Replace the TTY heuristic with the same pattern as `trust_edit_allow.json`: a single-use, action-bound marker `S/operator_ok/<verb>.<target>.json`, created only in the operator's terminal and consumed on use (agents cannot write `S`: G-W and G-B rule c). Alternatively route these through GTMApprover's Touch ID. At minimum, add G-B rules denying `script`/`expect`/`unbuffer`/`env -u CLAUDECODE`/`unset CLAUDECODE` in any command that also names `act.py`, with falsification tests.

### FID-07 · risk — **CROSS** (also `05_approver.md`, `03_schemas.md`, `04_hooks.md`)

- **Where:** CONTRACTS.md §2.3/§5.5 TRUST_PATHS (L2785-2787); §3.3 pack consumers; §4.3 G-W
- **Issue:** The HEAD-integrity check covers runtime files but not the pack, even though the pack now decides safety: `regulated` (all HIPAA routing, redaction and lanes), `identity_allowlist` and `accounts` (check 1), `marketing_paths` (check 9), `claims_policy`, `ai_content_policy`, `shared_identifiers`, `class_o_batches`. act.py loads the working-tree `company.json`. An interactive GTM session (full Write, reads untrusted text) can therefore drop `regulated: ["hipaa"]` from OtherCompany or widen `marketing_paths`, and the next `authorize` uses it. Plan §3.2 makes the pack tracked so that changes are reviewed.
- **Fix:** act.py (`make_ctx`), gate-gtm and the hooks load the pack via `git -C <H> show HEAD:.claude/gtm/company.json` (and `review_lanes.local.json`, `connectors.json`) and refuse `pack_uncommitted` (exit 13) when the working tree differs, as for TRUST_PATHS. Also add the pack path to G-W's GTM-scope deny so edits happen in a non-GTM, reviewed session. P2 test: an uncommitted removal of `regulated` makes the next write-policy command refuse.

### FID-08 · risk — **CROSS** (also `08_seats_wps.md`, `04_hooks.md`)

- **Where:** CONTRACTS.md §2.7(c) and §8.1 extractor (L1429-1432); §4.3 G-W deny set
- **Issue:** All the maker-checker and verifier ground truth (reviews, verifications, operations, proposals) is read from `~/.claude/projects/**/subagents/agent-<id>.jsonl`. Those files are not write-protected: G-W and G-B rule c do not cover `R/projects/`. A session with Write (interactive GTM sessions have it) can append a forged `gtm-result` to a real gtm-checker transcript whose `agent_id` is already in `spend.jsonl`, and `review` then records a pass. Plan §6.5(c) exists so that 'the director's or session's retelling never counts'.
- **Fix:** In GTM scope, add G-W and G-B rule c denials for `R/projects/**/*.jsonl` writes. As defense in depth, have the `gtm_ticket_release`/SubagentStop hook record `{agent_id, sha256(last_assistant_message)}` to `S/agent_results.jsonl` (hook-written, agent-unwritable). `gtm_result.extract_gtm_result` then refuses a final block whose hash differs from the SubagentStop record (plan §17 notes SubagentStop carries `last_assistant_message`).
- **Tagging note:** The anchor line L1429-1432 predates the current text; the finding concerns §2.7(c), §8.1 and §4.3, so it is not listed under 03_schemas.md.

### FID-09 · risk — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §3.4.4 `google_ads.ad_create@paused`/`ad_text_edit@paused`/`asset_*@paused` (L1314-1315, internal reviewers incl. gtm-checker) vs `*.post_schedule` treatment (L1335, §2.7)
- **Issue (first sentence):** The contract applies plan §6.5's reasoning ('reversible until live, but goes public without a further gate → takes the public-item lane set') to scheduled posts but not to ads authored in a paused campaign.
- **Full text (issue and fix):** under FID-09 in the `03_schemas.md` section of this document.

### FID-11 · gap — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §2.4 resume (L594), §2.9 (L932-936), §3.17 `promote` (L1845-1846) vs plan §20.6 ('automatic re-promotion after 7 clean days') and §20.11 (breakers are not cards)
- **Issue:** The contract contradicts §20.6 without saying so. A breaker writes `PAUSE.<system>` (`created_by: breaker`), which only an operator terminal or a lifting card can remove. `autonomy_ladder.py promote` restores the system level after 7 days, but the pause file still blocks every non-T0 action, and 'clean days' accrue trivially while the system is blocked. No card is posted either (§20.11), so the system stays stopped until the operator happens to see the HTML page. The result is stricter than the plan, but it is undecided, and two implementers would diverge.
- **Fix:** Decide explicitly and add an Appendix B entry. Option A (plan §20.6): `promote` also removes the breaker's `PAUSE.<system>` (created_by breaker, no ruling_ref), clean days count only days with ≥1 successful verify on that system, and the promotion writes an info notice with push. Option B (operator-gated): the breaker posts a card via `card-post` naming the pause as its `lift_card` subject, and §20.6's auto re-promotion is recorded as amended (plan edit plus an Appendix C entry).

### FID-14 · gap

- **Where:** CONTRACTS.md §2.4 revert step 1 (L599)
- **Issue:** Revert children get `lanes = []` and 'class recomputed', but the contract never says whether `checks.run_all` runs. A revert can autonomously re-publish content that a forward action removed: 4100 Example, a banned claim, an AI image without disclosure. That is exactly what plan §6.6's act.py-computed checks exist to stop.
- **Fix:** State that revert step 1 runs `checks.run_all` on the child (the restored `before` as `after`). A failure moves the child to `awaiting_card` with the failing checks listed, so the operator decides, instead of executing. Add an A2 test: reverting a 4100-Example removal does not auto-execute.

### FID-19 · gap — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §3.14 lead sink (L1774-1775), §2.4 lead-append; plan §20.5.6, §20.13
- **Issue (first sentence):** For OtherCompany, `lead-append` sends prospective-patient contact data (name, phone, email) to whatever `lead_sink` the pack names (e.g.
- **Full text (issue and fix):** under FID-19 in the `03_schemas.md` section of this document.

### IMP-15 · missing-docs — **CROSS** (also `04_hooks.md`)

- **Where:** §4.6 AttributionCtx.slug_by_project_dir and precedence step 4; §2.1 ai_budget deps; §2.4 purge-untrusted hipaa transcripts
- **Issue (first sentence):** m-3: `ai_budget` is declared standalone (stdlib + company, system_names, approval_sig, gtm_pricing), but it needs `_project_dir_name`, which lives in `harvest_tool_trail` (that module pulls in activity_log at import time).
- **Full text (issue and fix):** under IMP-15 in the `04_hooks.md` section of this document.

### IMP-18 · missing-docs

- **Where:** §2.10 activity-log call hygiene vs real `activity_log.cmd_add` (append, then `render_all`) and argparse
- **Issue:** m-6: Two ways the in-process activity-log call can mislead. (1) `cmd_add` appends the line and only then calls `render_all(paths)`. If rendering raises, A2 records `activity_log_error` and no `activity_log_id` even though the line was written, so validate_run then reports a false `activity_log_failed`. (2) argparse reads a `--why`/`--before` value that starts with `-` (for example a rationale beginning '- ') as a flag and exits 2.
- **Fix:** Parse the `logged A…` id before treating an exception as a failure, or say that a render error after a successful append is recorded as `activity_log_render_error`, not a failure. Require the `--flag=value` argv form for every free-text argument.

### IMP-20 · missing-docs

- **Where:** §2.4 revert step 2 (L599)
- **Issue:** m-8: The contract says step 2 'verifies and executes the child' but only says how an API system executes it. For a browser-only system (most listings, GBP writes), a money or card-approved revert child needs a ticket and a gtm-operator dispatch, and no transition covers that.
- **Fix:** For browser systems, say that step 2 moves the child to `authorized` (after verifying the approval or card), and that the normal `ticket --write` → gtm-operator → `complete` path runs it.

### FID-20 · nit

- **Where:** CONTRACTS.md §2.6 rule 6 F-caps rationale (L714-724)
- **Issue:** The rationale says schedules exist to exercise 'the whole shadow period'. Plan §14 P7 runs shadow by hand via `/gtm-cycle`, and plan §5 sets caps from the measured shadow-week $ (1.25×) at the end of shadow. The mechanism is fine; the stated premise misreads the plan, and the money brief does not require the measured basis.
- **Fix:** Correct the rationale. Require the `gtm_ai.weekly_cap_edit` `money_brief.metrics_summary` to cite the measured shadow-week USD from `ai_budget.py usd`.

### FID-21 · nit

- **Where:** CONTRACTS.md §2.8 check 5 (hipaa_prohibited rows, L864-871)
- **Issue:** Plan §20.5.4 says 'prohibited … until the KB verifies the rules and a card approves it'. The contract makes these permanently `never` with no re-enable path.
- **Fix:** Note in Appendix B that re-enabling requires a reviewed tier-table/pack change citing the KB and an answered operator card. Or add a pack key `hipaa_exceptions: [{row_id, card_id, kb_claim}]` that check 5 honors.

## 03_schemas.md — §3 data schemas

### FID-01 · blocker — **CROSS** (also `02_act.md`)

- **Where:** CONTRACTS.md §2.6 'Card rule' (L767-783), §2.5 awaiting_card row (L663), §2.11 'approval' kind (L1040-1043), §2.4 resume (L594) and autonomy (L603), §3.17 (L1862-1863)
- **Issue (first sentence):** A card only has to be answered.
- **Full text (issue and fix):** under FID-01 in the `02_act.md` section of this document.

### FID-02 · blocker — **CROSS** (also `02_act.md`, `06_connectors.md`)

- **Where:** CONTRACTS.md §2.8 check 1 (L836-844), check 2 (L845-847), §3.4.4 rows `*.asset_link` (L1388), `*.user_add/user_role_edit` (L1386), `L.claim_submit` (L1362); §6.2/§6.3 (connector target selection)
- **Issue (first sentence):** Isolation is weaker than plan §6.3/§7 ("create/modify anything whose account_id/page/location/domain fails §7 → NEVER"; "link/claim/share/connect … NEVER if cross-company").
- **Full text (issue and fix):** under FID-02 in the `02_act.md` section of this document.

### FID-03 · blocker — **CROSS** (also `05_approver.md`, `06_connectors.md`)

- **Where:** CONTRACTS.md §3.4.4 rows `google_ads.campaign_create` (L1312, `budget_amount` allowed, class auto), `google_ads.campaign_enable` (L1322), `lsa.account_enable` (L1333), `L.paid_enable` (L1360); §3.2 money shape; §5.5 step 3b (L2797-2804); §6.2 before re-check (L2941-2944)
- **Issue:** The `$` signature is not bound to the money actually committed at enable. Plan §20.13 says a paused campaign's budget 'is committed only at enable'. An agent creates a paused campaign with any `budget_amount` (T1, auto, no signature). The operator then signs `campaign_enable` with a `new_absolute_value` that §5.5 compares only to the action's own `after.new_absolute_value`, i.e. the agent's claim. Nothing requires the connector or runbook to read the campaign's configured budget and refuse when it differs from the signed amount. Signing "$45.00/day" can therefore enable a $1,000/day campaign. The only detection is the post-hoc `verify_read`, after the money is committed. That breaks the core rule that `$` is signed off only via the approver.
- **Fix:** Define enable semantics normatively. For every `*_enable` money row, `new_absolute_value` = the object's configured committed ceiling (daily/lifetime budget or pay-per-lead cap) and `unit` = its period. `authorize` fills `before.value.current_absolute_value` from a fresh connector read (API) or snapshot, and the approval display shows it. `plan()`/`apply()` (API) and the runbook's mandatory before-check (browser) re-read the configured budget immediately before enabling and fail `before_mismatch` if it differs from the signed value. Add this to §6.2's before re-check and §6.4's before-check list. P2 test: a paused campaign whose budget differs from the signed enable amount is refused at execute with no platform write.

### FID-04 · blocker — **CROSS** (also `02_act.md`)

- **Where:** CONTRACTS.md §2.4 `website_static` executor (L624-642), §3.2 (L1155-1156: `after.paths` + `summary`), §3.4.4 row `website_static.page_edit` (P fields), §2.4 `propose --file` (FILE_PROPOSE_ROWS), §2.8 checks 2–4/9
- **Issue (first sentence):** For `website_static`, maker-checker and the content checks bind nothing.
- **Full text (issue and fix):** under FID-04 in the `02_act.md` section of this document.

### IMP-02 · blocker — **CROSS** (also `02_act.md`)

- **Where:** §3.4.1 row-id grammar (L1205) and the §3.4.4 row table (L1309-1390); consumed by H2 drafter primers, L runbooks/manifests `write_rows`, the §2.10 verb map, and §2.4's `action ∈ {read, export, snapshot}` refusal
- **Issue:** B-2: A row id is `<system>.<object_class>_<action>`, but object classes and actions both contain underscores, so an id doesn't say how to split it. Examples: `gbp.qa_answer_publish`, `website_wordpress.page_unpublish_with_301`, `lsa.lead_dispute_submit`, `email.inquiry_reply_send`, `*.user_role_edit`, `google_ads.enhanced_conversions_leads_enable`, `sms_provider.a2p_10dlc_registration_create`. Matching (§3.4.2) compares the proposal's exact `object_class` and `action` strings. The table gives only ids, so the drafter seats (H2), the tier table (A1) and the §2.10 verb map (A2) will each guess a split. Any mismatch silently falls to `_nomatch` (a `$` action). That floods the approver and makes every `auto` row unreachable.
- **Fix:** Add explicit `object_class` and `action` columns to the normative §3.4.4 table for every row, or state one mechanical rule and list every exception. Require the tier-table validator to check `id == f"{system}.{object_class}_{action}"` (plus any `@when` suffix). Have H2 primers and L manifests reference `(system, object_class, action)` triples, not ids.

### IMP-03 · blocker — **CROSS** (also `02_act.md`, `00_global_paths.md`)

- **Where:** §2.3 exception (2) 'operator terminal = env CLAUDECODE unset and sys.stdin.isatty()' (L522-524); used by `resume` (§2.4, §3.10) and `autonomy` (§2.4, §3.17); also the CLAUDE_GTM_COMPANY env identity (§1.4)
- **Issue (first sentence):** B-3: The 'operator terminal' test is the only thing, besides a lifting card, that lets `resume` remove an operator, breaker or migration pause, and that lets `autonomy --level autonomous` leave shadow.
- **Full text (issue and fix):** under IMP-03 in the `02_act.md` section of this document.

### IMP-05 · regression — **CROSS** (also `05_approver.md`, `04_hooks.md`)

- **Where:** §5.5 step 2 TRUST_PATHS (L2785-2790) and §4.6 F-trust (L2470-2475); §3.19 gtm_pricing (L1970-1977); §4 seat_sets()
- **Issue (first sentence):** M-2: The trust-root check doesn't cover everything that decides the AI-spend cap.
- **Full text (issue and fix):** under IMP-05 in the `05_approver.md` section of this document.

### FID-05 · risk — **CROSS** (also `08_seats_wps.md`)

- **Where:** CONTRACTS.md §3.4.2 `_nomatch` (L1231-1236) and §3.4.4 'Every class: money row has lanes_key: none' (L1265-1269); Appendix B #49, #99
- **Issue:** Plan §6.5 requires specialist lanes on every public item. The contract drops all lanes for `_nomatch` too, and `_nomatch` is marked `public: true`. So any unlisted public content, including all Meta ad copy (explicitly left `_nomatch`, L1392), a new platform's posts or listing text, goes live on a Touch ID signature over a ≤400-char `after_summary`, with no brand, claims or CTA review. The stated reason (a review would block an urgent runaway stop behind a checker dispatch under budget state) applies to amount-only money rows, not to `_nomatch` text.
- **Fix:** Keep `lanes_key: none` for amount-only money rows and urgent stops. For `_nomatch` (and any money row whose `after` carries text or assets), require the public lane set (`brand`, `claims_voice`, plus `cta_link` when a link is present, plus `video`/`hipaa` as usual) before `authorize` creates the approval request. Budget-state admission is not needed because these are not urgent.

### FID-07 · risk — **CROSS** (also `02_act.md`, `05_approver.md`, `04_hooks.md`)

- **Where:** CONTRACTS.md §2.3/§5.5 TRUST_PATHS (L2785-2787); §3.3 pack consumers; §4.3 G-W
- **Issue (first sentence):** The HEAD-integrity check covers runtime files but not the pack, even though the pack now decides safety: `regulated` (all HIPAA routing, redaction and lanes), `identity_allowlist` and `accounts` (check 1), `marketing_paths` (check 9), `claims_policy`, `ai_content_policy`, `shared_identifiers`, `class_o_batches`.
- **Full text (issue and fix):** under FID-07 in the `02_act.md` section of this document.

### FID-09 · risk — **CROSS** (also `02_act.md`)

- **Where:** CONTRACTS.md §3.4.4 `google_ads.ad_create@paused`/`ad_text_edit@paused`/`asset_*@paused` (L1314-1315, internal reviewers incl. gtm-checker) vs `*.post_schedule` treatment (L1335, §2.7)
- **Issue:** The contract applies plan §6.5's reasoning ('reversible until live, but goes public without a further gate → takes the public-item lane set') to scheduled posts but not to ads authored in a paused campaign. Those ads go public the moment `campaign_enable` is signed, and the operator's approval display shows only the budget. Ad copy can therefore reach the public reviewed only by gtm-checker.
- **Fix:** Either mark the `@paused` ad/asset rows `public: true` for lane purposes (specialist reviewers), or make `authorize` of `google_ads.campaign_enable` refuse `unreviewed_public_assets` unless every ad and asset action completed under that campaign carries passing specialist public lanes on its current digest. Add a P2 test.

### FID-10 · gap — **CROSS** (also `07_notices_schedules.md`)

- **Where:** CONTRACTS.md §7.1 notice kinds (`signin_missing`, L3088) and §3.19 `expired_signins`; §7.5 prompt checklists I1–I9, D1–D10
- **Issue (first sentence):** Plan §18 ('inbox/daily runs raise same-day sign-in card') and §20.11 (sign-in is one of only three card types) require sign-in expiry detection.
- **Full text (issue and fix):** under FID-10 in the `07_notices_schedules.md` section of this document.

### FID-11 · gap — **CROSS** (also `02_act.md`)

- **Where:** CONTRACTS.md §2.4 resume (L594), §2.9 (L932-936), §3.17 `promote` (L1845-1846) vs plan §20.6 ('automatic re-promotion after 7 clean days') and §20.11 (breakers are not cards)
- **Issue (first sentence):** The contract contradicts §20.6 without saying so.
- **Full text (issue and fix):** under FID-11 in the `02_act.md` section of this document.

### FID-12 · gap — **CROSS** (also `07_notices_schedules.md`)

- **Where:** CONTRACTS.md §5 inbox row / §7.5 I8 (L3268: 'gtm-checker (or the O6 lane-review seats)'); §3.4.4 `*.review_reply_publish` public rows
- **Issue (first sentence):** Under §20.6, O6 is superseded: review replies are autonomous after required reviews.
- **Full text (issue and fix):** under FID-12 in the `07_notices_schedules.md` section of this document.
- **Tagging note:** The `§5 inbox row` in the anchor is plan §5 (the plan's inbox row that §7.5 I8 cites), not contract §5.

### FID-13 · gap

- **Where:** CONTRACTS.md §3.4.4 `{email,sms}.list_send` (L1382); §3.11 release re-checks (L1653-1672)
- **Issue:** List sends are under-specified for non-hipaa packs. They carry no `recipient`/`lead_id`, so quiet hours ('messages to named people only outside quiet_hours', plan §20.7) never apply to `email.list_send`. `sms.list_send`'s consent rule reads 'the lead's sms_consent', which does not exist for a list. One implementer blocks it forever, another sends to the whole list with no per-member consent check (TCPA, plan §20.6 'SMS only with consent recorded').
- **Fix:** State the rules: list sends apply quiet hours and SMS send windows at the send time. `sms.list_send` resolves the list to lead-sink rows and sends only to members whose `sms_consent` is complete (value, source, ts), with the excluded count in the result. An unresolvable list refuses `list_unresolvable`. `email.list_send` requires an unsubscribe and physical-address check in the compliance lane checklist (CAN-SPAM KB).

### FID-19 · gap — **CROSS** (also `02_act.md`)

- **Where:** CONTRACTS.md §3.14 lead sink (L1774-1775), §2.4 lead-append; plan §20.5.6, §20.13
- **Issue:** For OtherCompany, `lead-append` sends prospective-patient contact data (name, phone, email) to whatever `lead_sink` the pack names (e.g. a Google Sheet), with no BAA check. Plan §20.5.6 requires a BAA on record before a vendor receives PHI, and §20.13 makes BAA a hipaa-lane check that stays UNVERIFIED per vendor until the KB lands.
- **Fix:** For `regulated ∋ hipaa` packs, require `lead_sink.baa_ref` (non-empty; schema follow-up in Appendix C). Until it is present, `lead-append` writes only to `ST/untrusted/` (purged at 30 days) and raises a `task` notice. Record the same rule for call_tracking and other `data_flow` vendors.

### IMP-13 · missing-docs — **CROSS** (also `07_notices_schedules.md`)

- **Where:** §3.6 Release vs §7.5 I3/W3 ('`Agent` gtm-analyst, then `act.py ticket --close <ticket_id>`')
- **Issue:** m-1: The prompts close tickets that the SubagentStop hook has usually already closed. By the time the session runs `ticket --close`, the read ticket is typically already `closed`, but the contract doesn't say what `ticket --close` does on a closed, expired or consumed ticket (idempotent exit 0, or exit 4). Every inbox and weekly run hits this.
- **Fix:** Say that `ticket --close` on a ticket that is already terminal is an idempotent success (exit 0, `result.already: <status>`).

### IMP-17 · missing-docs — **CROSS** (also `00_global_paths.md`, `07_notices_schedules.md`, `08_seats_wps.md`)

- **Where:** Exit-code tables: §3.12 cycle.py, §1.2 gtm_lists.py, §3.19 validate_run.py, §3.23 outside_actor.py, §3.17 autonomy_ladder.py, App. C 7 vs backup_state.py, §7.6 gtm_session.sh
- **Issue:** m-5: Several tools are missing standard exit codes. cycle.py, outside_actor.py and autonomy_ladder.py define no exit 1 (internal); gtm_lists.py has no 1 or 13; validate_run.py has no 2. App. C 7's `anchor_not_in_archive` exit 3 conflicts with backup_state.py's existing convention (every refusal exits 1). gtm_session.sh passes `claude`'s own exit code through, which can collide with the reserved 13/64/75/77/142 that run_gtm_job.sh maps.
- **Fix:** Give every CLI the full common set (0/1/2/3/12/13 where relevant). State backup_state's new exit mapping explicitly. Have gtm_session.sh map any non-reserved nonzero `claude` exit into one range (for example 100+n capped) so the runner's table is unambiguous.

### FID-24 · nit

- **Where:** CONTRACTS.md §3.11 / §3.6 ticket mint
- **Issue:** Quiet hours and SMS windows are checked only when a hold is released. A browser hold released at 19:59 can be executed later by an interactive session inside quiet hours.
- **Fix:** Re-run the quiet-hours and send-window checks at `ticket --write` and `execute` for `recipient_required` rows.

### IMP-24 · nit

- **Where:** §3.4.4 `crm.lead_append` (no `after_fields`)
- **Issue:** n-3: The row has no `after_fields`, so `propose` of `crm.lead_append` (instead of `lead-append`) has undefined check-10 behaviour.
- **Fix:** Have `propose` refuse `crm.lead_append` (exit 3 `use_lead_append`), the same way it refuses read actions.

## 04_hooks.md — §4 hook contracts

### IMP-04 · regression — **CROSS** (also `00_global_paths.md`, `08_seats_wps.md`)

- **Where:** §4.2 G-B rules c/k (scope 'all'); B2 wiring in §4.7/§4.9; §1.5 item 7; Appendix C item 19
- **Issue:** M-1: G-B goes live mid-Wave-2 and blocks the implementers themselves. G-W's registration is explicitly deferred until after Wave 2 (§4.8 item 4, App. C 19). G-B is not deferred: it goes live the moment B2 commits the `pretooluse_bash.py` and `bash_gate.sh` edits. Rule c then denies, in every session, `cp`/`mv`/`rm`/`tee`/`sed -i` whose source or destination is `R/tools/gtm/act.py` or under `R/tools/gtm/gtmlib/`. That includes the single-file backup `cp gtmlib/store.py <scratch>/`, which runtime CLAUDE.md §2/§6 requires for revert-and-rerun. So A1/A2 implementers and code-reviewers can't do the §1.5 item 7 falsification checks. Rule k (the literals `GTM_HOLDS_JOB`, `trust_edit_allow`) also denies ordinary `grep` or pytest command lines that mention those names during D/B1 development.
- **Fix:** State that B2's G-B wiring (the `_gtm_bash_block` call in `resolve_block` plus the new `bash_gate.sh` arms) lands behind the same post-Wave-2 coordinator step as G-W. If it must land earlier, exempt source operands that are only read (`cp <protected> <elsewhere>`) and document how to back up and revert a protected file. Allow rule k's literals inside `grep`/`rg` arguments.

### IMP-05 · regression — **CROSS** (also `05_approver.md`, `03_schemas.md`)

- **Where:** §5.5 step 2 TRUST_PATHS (L2785-2790) and §4.6 F-trust (L2470-2475); §3.19 gtm_pricing (L1970-1977); §4 seat_sets()
- **Issue (first sentence):** M-2: The trust-root check doesn't cover everything that decides the AI-spend cap.
- **Full text (issue and fix):** under IMP-05 in the `05_approver.md` section of this document.

### IMP-06 · regression

- **Where:** §4.6 'Admissions that never run' (L2512-2521) and §4.9 pretooluse_task bullet vs the real `hooks/pretooluse_task.py:apply_t2` and `agent_budget.apply_decision`/`_apply_pacer_gate`
- **Issue:** M-3: The release-on-T2-deny wiring can't be built against the real hook code as specified. `pretooluse_task.py` is to call `ai_budget.release_admission(tool_use_id, "t2_deny")` 'whenever T2 denies'. In the real code, `apply_t2` returns `ab.apply_decision(...)`, which returns 0 on every gate path. The pacer's admit/deny outcome is computed inside `_apply_pacer_gate` (`paced_admit`), and the deny is printed straight to stdout. Nothing is returned that says T2 denied, so B2 has no way to know when to release.
- **Fix:** Specify the agent_budget change: `_apply_pacer_gate`/`apply_decision` return or expose a result flag (for example a `decision["_denied"]` set in place, or a new `gate_outcome()` helper), and `apply_t2` returns `(exit, denied)`. List the existing agent_budget/pretooluse_task tests that must still pass unchanged.

### IMP-07 · regression

- **Where:** §4.8 item 3 / §4.9 (block_prod_mutations) vs the real `hooks/block_prod_mutations.py` R5 and `live-testing/allowlist.json`
- **Issue:** M-4: An existing hook will block GTM browser clicks on two GTM companies' own sites. `block_prod_mutations.py` (enforcing) matches every `mcp__playwright[...]__*` tool, including `playwright-gtm`. Its R5 denies interaction tools (`browser_click/type/fill_form/...`) when the recorded host is in `read_only_hosts`. That list contains `example.com`, `app.example.com`, `otherapp.example` and `app.otherapp.example`, which are two GTM companies' own identity domains. A gtm-analyst read-ticket `browser_click` or a gtm-operator write on those hosts is denied by R5 even when G-A admits it. §4.9 only changes R5's state key and never addresses the deny policy.
- **Fix:** In §4.9, decide explicitly: either exempt `playwright-gtm` from R5's read_only_hosts rule (G-A ticket binding becomes the control there), or state that GTM browser writes and clicks on CSA/OtherApp hosts are out of scope. Add a B2 test for a `playwright-gtm` click on `example.com` with a valid ticket.

### FID-07 · risk — **CROSS** (also `02_act.md`, `05_approver.md`, `03_schemas.md`)

- **Where:** CONTRACTS.md §2.3/§5.5 TRUST_PATHS (L2785-2787); §3.3 pack consumers; §4.3 G-W
- **Issue (first sentence):** The HEAD-integrity check covers runtime files but not the pack, even though the pack now decides safety: `regulated` (all HIPAA routing, redaction and lanes), `identity_allowlist` and `accounts` (check 1), `marketing_paths` (check 9), `claims_policy`, `ai_content_policy`, `shared_identifiers`, `class_o_batches`.
- **Full text (issue and fix):** under FID-07 in the `02_act.md` section of this document.

### FID-08 · risk — **CROSS** (also `02_act.md`, `08_seats_wps.md`)

- **Where:** CONTRACTS.md §2.7(c) and §8.1 extractor (L1429-1432); §4.3 G-W deny set
- **Issue (first sentence):** All the maker-checker and verifier ground truth (reviews, verifications, operations, proposals) is read from `~/.claude/projects/**/subagents/agent-<id>.jsonl`.
- **Full text (issue and fix):** under FID-08 in the `02_act.md` section of this document.
- **Tagging note:** The anchor line L1429-1432 predates the current text; the finding concerns §2.7(c), §8.1 and §4.3, so it is not listed under 03_schemas.md.

### FID-15 · gap

- **Where:** CONTRACTS.md §4.6 step 3 (L2579-2586)
- **Issue:** The contract is ambiguous about the over-cap path. The parenthetical '(then also write PAUSE.budget … + a budget notice, urgent, push)' reads as attached only to the forged state. Plan §5 and §7.4 require that over cap writes `PAUSE.budget` plus an operator signal (a card, now a GTM_Operator.html item per §20.11). As written, crossing a signed cap silently denies dispatches, and the operator is never told the department stopped.
- **Fix:** Split step 3: (a) over cap → write `ST/PAUSE.budget` (`created_by: gate-gtm`, reason naming bucket, USD and cap) plus a `budget` notice (urgent, push, dedupe `budget:<slug>:<ISO week>`); (b) forged → the same plus a `trust` notice. Add a B2 test for each.

### IMP-14 · missing-docs

- **Where:** §4 seat constants (L2213-2217)
- **Issue:** m-2: `seat_sets() -> tuple[set,set,set]` is described as logging `gtm-seats-from-default` 'through a caller-supplied logger', but the signature has no logger parameter. A1, B1, B2 and G will call it differently.
- **Fix:** Fix the signature, for example `seat_sets(*, log: Callable[[str, dict], None] | None = None)`.

### IMP-15 · missing-docs — **CROSS** (also `02_act.md`)

- **Where:** §4.6 AttributionCtx.slug_by_project_dir and precedence step 4; §2.1 ai_budget deps; §2.4 purge-untrusted hipaa transcripts
- **Issue:** m-3: `ai_budget` is declared standalone (stdlib + company, system_names, approval_sig, gtm_pricing), but it needs `_project_dir_name`, which lives in `harvest_tool_trail` (that module pulls in activity_log at import time). Step 4's exact-equality match also misses worktree and subfolder project dirs, which the real `_matches_project_dir_prefix` includes. The HIPAA transcript purge has the same gap: it only deletes `R/projects/<_project_dir_name(H)>/**`.
- **Fix:** Move `_project_dir_name`, `project_dir_name_text` and the prefix matcher into a tiny stdlib module (for example `tools/gtm/project_dirs.py`) that everything imports. Use the separator-bounded prefix match in step 4 and in purge-untrusted.

### IMP-19 · missing-docs — **CROSS** (also `07_notices_schedules.md`)

- **Where:** §7.2/§7.6 `ai_budget.py caps` consumption; §4.6 forged state
- **Issue (first sentence):** m-7: The runner and gtm_session.sh branch on each bucket's `source`, but the output of the `caps`/`state`/`usd` CLIs is only described as 'one JSON object'.
- **Full text (issue and fix):** under IMP-19 in the `07_notices_schedules.md` section of this document.

### IMP-22 · nit — **CROSS** (also `08_seats_wps.md`)

- **Where:** §4 gtm_hooklib intro (L2177-2181) and §9 B1 consumes
- **Issue:** n-1: gtm_hooklib is said to import `approval_sig` (A2) and `gtm_pricing` (G), but B1's consumes column lists neither, and nothing in hooklib's listed API needs `gtm_pricing`. `write_notice_file` also re-implements `notices.py`'s writer (id format, dedupe, locks), which risks drift.
- **Fix:** Drop `gtm_pricing` from hooklib's imports and add `approval_sig` to B1's consumes. Share one notice-writing helper (a stdlib module both D and B1 import), or add a parity test between the two writers.

### IMP-23 · nit

- **Where:** §4.2 wiring `_gtm_bash_block(command, where, agent_type)`
- **Issue:** n-2: The only accessor `_lib` has, `_lib.subagent_type(ev)`, reads `tool_input.subagent_type`, which a Bash payload does not have. An implementer could wire the wrong field.
- **Fix:** Name the source explicitly: `ev.get("agent_type")` (top level), subject to probe q.

### IMP-25 · nit

- **Where:** §4.2 rule a exception (L2331)
- **Issue:** n-4: The `act.py execute` exception is vacuous: that command never matches rule a's patterns, so the exception reads as if something needed exempting.
- **Fix:** Drop it, or explain what it guards.

## 05_approver.md — §5 approver protocol

### FID-03 · blocker — **CROSS** (also `03_schemas.md`, `06_connectors.md`)

- **Where:** CONTRACTS.md §3.4.4 rows `google_ads.campaign_create` (L1312, `budget_amount` allowed, class auto), `google_ads.campaign_enable` (L1322), `lsa.account_enable` (L1333), `L.paid_enable` (L1360); §3.2 money shape; §5.5 step 3b (L2797-2804); §6.2 before re-check (L2941-2944)
- **Issue (first sentence):** The `$` signature is not bound to the money actually committed at enable.
- **Full text (issue and fix):** under FID-03 in the `03_schemas.md` section of this document.

### IMP-05 · regression — **CROSS** (also `04_hooks.md`, `03_schemas.md`)

- **Where:** §5.5 step 2 TRUST_PATHS (L2785-2790) and §4.6 F-trust (L2470-2475); §3.19 gtm_pricing (L1970-1977); §4 seat_sets()
- **Issue:** M-2: The trust-root check doesn't cover everything that decides the AI-spend cap. F-trust says an uncommitted edit to `gtm_pricing.py` 'can never silently disable the AI-spend cap'. But `gtm_pricing.price_usd` delegates to `~/.claude/usage-dashboard/ccdash/pricing.compute_cost_usd`, with `telemetry/pricing.json` as the fallback. Neither is in TRUST_PATHS, so an uncommitted edit there that returns 0 disables the cap undetected. Similarly, `system_names.seat_sets()` reads `knowledge/model_policy.json` (not in TRUST_PATHS) to decide which agent types gate-gtm enforces. Deleting a seat from `gtm_seats` there removes that seat from budget and dispatch-cap enforcement.
- **Fix:** Add `usage-dashboard/ccdash/pricing.py`, `telemetry/pricing.json` and `knowledge/model_policy.json` to TRUST_PATHS. Alternatively, make gtm_pricing self-contained with a committed price table and make `seat_sets()` fall back to the constants whenever the policy lists fewer seats than `GTM_SEATS`. Extend the B2 falsification test to an uncommitted ccdash edit.

### FID-07 · risk — **CROSS** (also `02_act.md`, `03_schemas.md`, `04_hooks.md`)

- **Where:** CONTRACTS.md §2.3/§5.5 TRUST_PATHS (L2785-2787); §3.3 pack consumers; §4.3 G-W
- **Issue (first sentence):** The HEAD-integrity check covers runtime files but not the pack, even though the pack now decides safety: `regulated` (all HIPAA routing, redaction and lanes), `identity_allowlist` and `accounts` (check 1), `marketing_paths` (check 9), `claims_policy`, `ai_content_policy`, `shared_identifiers`, `class_o_batches`.
- **Full text (issue and fix):** under FID-07 in the `02_act.md` section of this document.

## 06_connectors.md — §6 connector interface

### FID-02 · blocker — **CROSS** (also `02_act.md`, `03_schemas.md`)

- **Where:** CONTRACTS.md §2.8 check 1 (L836-844), check 2 (L845-847), §3.4.4 rows `*.asset_link` (L1388), `*.user_add/user_role_edit` (L1386), `L.claim_submit` (L1362); §6.2/§6.3 (connector target selection)
- **Issue (first sentence):** Isolation is weaker than plan §6.3/§7 ("create/modify anything whose account_id/page/location/domain fails §7 → NEVER"; "link/claim/share/connect … NEVER if cross-company").
- **Full text (issue and fix):** under FID-02 in the `02_act.md` section of this document.

### FID-03 · blocker — **CROSS** (also `03_schemas.md`, `05_approver.md`)

- **Where:** CONTRACTS.md §3.4.4 rows `google_ads.campaign_create` (L1312, `budget_amount` allowed, class auto), `google_ads.campaign_enable` (L1322), `lsa.account_enable` (L1333), `L.paid_enable` (L1360); §3.2 money shape; §5.5 step 3b (L2797-2804); §6.2 before re-check (L2941-2944)
- **Issue (first sentence):** The `$` signature is not bound to the money actually committed at enable.
- **Full text (issue and fix):** under FID-03 in the `03_schemas.md` section of this document.

### IMP-10 · regression — **CROSS** (also `08_seats_wps.md`)

- **Where:** §9 L3 row + §6.4/§6.5 (`tools/gtm/runbook_validate.py`, `tools/gtm/connectors/testkit.py`)
- **Issue (first sentence):** M-7: L1 and L2 are told to 'stub them until then' and to call L3's runbook validator and fake-HTTP testkit in their own P2 tests.
- **Full text (issue and fix):** under IMP-10 in the `08_seats_wps.md` section of this document.

### IMP-11 · regression — **CROSS** (also `02_act.md`)

- **Where:** §6.2 idempotency (L2932-2935) vs §2.4/§2.5 (`failed` ∈ AUTHORIZE_FROM, re-execution)
- **Issue:** M-8: A failed connector write can never be retried. `apply` records `{idempotency_key, result}` with key = `action_id` and 'returns the recorded result on a repeat'. The contract doesn't limit recording to successful writes. So an action that failed with a retryable error (`rate_limited`, `auth`), then re-authorized and re-executed, gets its old failure replayed and stays stuck.
- **Fix:** State that only `ok: true` results (or results with platform side effects) are recorded. Alternatively, key on `action_id` plus attempt number and record every attempt, with the replay returning only a prior success. Add an L test: a retryable failure followed by a successful retry.

### FID-23 · nit

- **Where:** CONTRACTS.md §6.3 connectors.json gsm_project (L2962-2964); plan §17 d
- **Issue:** Plan §17 leaves the non-CSA GSM project (not tied to the main product) for trust-architect to decide. The contract has no owner or timing for that decision, and M writes `connectors.json`.
- **Fix:** Add a coordinator item: get the trust-architect decision before M writes OtherCompanyB/OtherApp/OtherCompany `connectors.json`. Record it in plan §17.

## 07_notices_schedules.md — §7 notices, runners, schedules

### IMP-12 · regression — **CROSS** (also `02_act.md`)

- **Where:** §7.5 checklists I3, I9, W3, D5, D6, L2 vs §2.4 `company_from` (L607)
- **Issue:** M-9: Several of K's required commands will exit 2. The checklists give 'exact command shown' strings `act.py ticket --close <ticket_id>`, `act.py ticket --write <id>` and `act.py ticket --write-batch <id,…>` with no `--company`. §2.4 lists `ticket` under `company_from: flag`, so `--company` is required and these exit 2. K is told to implement the commands verbatim.
- **Fix:** Add `--company <slug>` to every `ticket` command in §7.5, or give `ticket` `company_from="action_id"`/ticket-id parsing (this depends on B-1). Make `test_k_prompts.py` also check for `--company` on these commands.

### FID-10 · gap — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §7.1 notice kinds (`signin_missing`, L3088) and §3.19 `expired_signins`; §7.5 prompt checklists I1–I9, D1–D10
- **Issue:** Plan §18 ('inbox/daily runs raise same-day sign-in card') and §20.11 (sign-in is one of only three card types) require sign-in expiry detection. No component produces `signin_missing` notices or the sign-in card, and no prompt step checks login state. The page, the perf metric and the approver all read a notice nothing writes. Chain-repair has the same hole: it needs an answered card, but §20.11 makes `PAUSE.chain` a notice and nothing posts the chain-repair card. The same applies to the breaker card of plan §6.8.
- **Fix:** Add an inbox/daily step I0/D0: the analyst reports `findings[].kind: "signin_missing"` per system when a runbook read path lands on a `login_hosts` page. `ingest-findings` writes a `signin_missing` notice with push, and the session posts or updates the one batched sign-in card through `card-post` (dedupe per company). Add a mandatory prompt step: when `PAUSE.chain` is present, `card-post` the chain-repair card (template text in the contract). Say whether breaker trips get a card (see the breaker finding).

### FID-12 · gap — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §5 inbox row / §7.5 I8 (L3268: 'gtm-checker (or the O6 lane-review seats)'); §3.4.4 `*.review_reply_publish` public rows
- **Issue:** Under §20.6, O6 is superseded: review replies are autonomous after required reviews. `review_reply` is a public row whose `public_reviewers` are content-strategist and local-presence-architect only. I8 still dispatches only gtm-checker, 'or the O6 lane-review seats', with no rule for when. Taken literally, inbox replies never pass maker-checker, or implementers invent their own dispatch rule and budget (plan §4.2: judgment seats never run in the daily cycle except that lane slot).
- **Fix:** Rewrite I8 so that after the checker pre-screen, one content-strategist dispatch (claims_voice, non-drafting) and one local-presence-architect dispatch (compliance, plus hipaa for OtherCompany) review the whole batch through review briefs, counted within `dispatch_caps_per_run.inbox`. Raise the cap if 8 is too low (analyst 1 + drafter 1 + checker 1 + 2 lanes + operator ≤3 = 8). Drop the O6 wording and the now-superseded I7 semi path or mark it legacy.
- **Tagging note:** The `§5 inbox row` in the anchor is plan §5 (the plan's inbox row that §7.5 I8 cites), not contract §5.

### IMP-13 · missing-docs — **CROSS** (also `03_schemas.md`)

- **Where:** §3.6 Release vs §7.5 I3/W3 ('`Agent` gtm-analyst, then `act.py ticket --close <ticket_id>`')
- **Issue (first sentence):** m-1: The prompts close tickets that the SubagentStop hook has usually already closed.
- **Full text (issue and fix):** under IMP-13 in the `03_schemas.md` section of this document.

### IMP-16 · missing-docs

- **Where:** §7.2 heartbeat statuses vs `hooks/heartbeat_audit.py` (only `status == "failed"` is flagged; sanctioned list is ok/skipped-quota/skipped-disabled/skipped-throttle)
- **Issue:** m-4: The watchdog won't see the new heartbeat statuses. `missed`, `skipped-paused` and `skipped-unsigned-caps` are never flagged, so a GTM schedule stuck on unsigned caps or a held lease stays silent to the watchdog. No WP owns the heartbeat_audit change or its docstring.
- **Fix:** Assign heartbeat_audit edits to D or K: flag `missed`, and flag a streak of N consecutive `skipped-unsigned-caps`/`skipped-paused` heartbeats like the existing quota streak. Update its sanctioned-status docstring.

### IMP-17 · missing-docs — **CROSS** (also `03_schemas.md`, `00_global_paths.md`, `08_seats_wps.md`)

- **Where:** Exit-code tables: §3.12 cycle.py, §1.2 gtm_lists.py, §3.19 validate_run.py, §3.23 outside_actor.py, §3.17 autonomy_ladder.py, App. C 7 vs backup_state.py, §7.6 gtm_session.sh
- **Issue (first sentence):** m-5: Several tools are missing standard exit codes.
- **Full text (issue and fix):** under IMP-17 in the `03_schemas.md` section of this document.

### IMP-19 · missing-docs — **CROSS** (also `04_hooks.md`)

- **Where:** §7.2/§7.6 `ai_budget.py caps` consumption; §4.6 forged state
- **Issue:** m-7: The runner and gtm_session.sh branch on each bucket's `source`, but the output of the `caps`/`state`/`usd` CLIs is only described as 'one JSON object'. The `source` value of a forged bucket is also undefined.
- **Fix:** State that `caps` prints exactly `effective_ai_caps(company, now)`, and that a forged bucket has `source: "forged"`. Add a D test that parses that shape.

### IMP-21 · missing-docs — **CROSS** (also `00_global_paths.md`)

- **Where:** §7.3 plist calendar vs §0.3 company-local HHMM
- **Issue:** m-9: Plist times and company times can differ. `StartCalendarInterval` fires in the machine's local timezone, but `cadence.inbox_checks` and weekly/monthly days are company-local (pack `timezone`). K isn't told to convert times for a company in another timezone, nor what happens when a delayed 09:00 fire computes HHMM=1500 and then collides with the real 15:00 run (a duplicate cycle, heard as a `failed` heartbeat).
- **Fix:** Tell K to render calendar entries converted from pack timezone to machine timezone, and make `run_gtm_job.sh` use the slot the plist fired for (passed as an argument), not the one computed from the clock.

## 08_seats_wps.md — §8 seats, §9 WP table, Appendices A–C

### IMP-04 · regression — **CROSS** (also `04_hooks.md`, `00_global_paths.md`)

- **Where:** §4.2 G-B rules c/k (scope 'all'); B2 wiring in §4.7/§4.9; §1.5 item 7; Appendix C item 19
- **Issue (first sentence):** M-1: G-B goes live mid-Wave-2 and blocks the implementers themselves.
- **Full text (issue and fix):** under IMP-04 in the `04_hooks.md` section of this document.

### IMP-08 · regression — **CROSS** (also `00_global_paths.md`)

- **Where:** §0.3 chain anchor (L166-181) + Appendix C item 7 vs `tools/gtm/backup_state.py backup_company` (tars `backup_set()` in order, home `.claude/gtm/state` first, runtime state after, without any lock)
- **Issue (first sentence):** M-5: A backup can capture the log and its anchor at different moments.
- **Full text (issue and fix):** under IMP-08 in the `00_global_paths.md` section of this document.

### IMP-10 · regression — **CROSS** (also `06_connectors.md`)

- **Where:** §9 L3 row + §6.4/§6.5 (`tools/gtm/runbook_validate.py`, `tools/gtm/connectors/testkit.py`)
- **Issue:** M-7: L1 and L2 are told to 'stub them until then' and to call L3's runbook validator and fake-HTTP testkit in their own P2 tests. But the contract defines no API for either: no function names, signatures, return shape or CLI exit codes. Three parallel WPs will each invent different ones.
- **Fix:** Add a §6.4b/§6.5b spec, for example `runbook_validate.validate(path: Path, *, tier_table: dict) -> list[str]` (problems, [] = ok) plus CLI `runbook_validate.py <file>...` with exit 0/3, and `testkit.FakeHTTP(fixtures_dir)` with `.install(monkeypatch)`, `.calls`, and a fixture file naming convention.

### FID-05 · risk — **CROSS** (also `03_schemas.md`)

- **Where:** CONTRACTS.md §3.4.2 `_nomatch` (L1231-1236) and §3.4.4 'Every class: money row has lanes_key: none' (L1265-1269); Appendix B #49, #99
- **Issue (first sentence):** Plan §6.5 requires specialist lanes on every public item.
- **Full text (issue and fix):** under FID-05 in the `03_schemas.md` section of this document.

### FID-08 · risk — **CROSS** (also `02_act.md`, `04_hooks.md`)

- **Where:** CONTRACTS.md §2.7(c) and §8.1 extractor (L1429-1432); §4.3 G-W deny set
- **Issue (first sentence):** All the maker-checker and verifier ground truth (reviews, verifications, operations, proposals) is read from `~/.claude/projects/**/subagents/agent-<id>.jsonl`.
- **Full text (issue and fix):** under FID-08 in the `02_act.md` section of this document.
- **Tagging note:** The anchor line L1429-1432 predates the current text; the finding concerns §2.7(c), §8.1 and §4.3, so it is not listed under 03_schemas.md.

### FID-16 · gap

- **Where:** CONTRACTS.md §9 WP table (H1/H2 'exactly … 12/15 files'; J)
- **Issue:** Plan §4.4 and the P4 assertion ('bundle_parity rules (a)–(d), (f), (g) green') need `docs/agents/<seat>.md` for all 9 new seats. `hooks/bundle_parity.py:57` rule (c) doc-present checks for it, and `~/.claude/docs/agents/` holds one file per existing agent. No WP owns these docs: H1 and H2 are 'exactly' agent + primer + template. The mirror README agent count (rule f) is also unassigned. P4 will fail as contracted.
- **Fix:** Add `docs/agents/{9 seats}.md` to H1/H2 (or J), and the mirror README count to J, with the bundle_parity check listed in J's tests.

### FID-17 · gap

- **Where:** CONTRACTS.md whole document vs plan §0 P1 / §14 P1 migration; §9 M row; pause_carry_in.py (L3558-3570 reads MASTER in 'the OtherCompanyB home')
- **Issue:** The OtherCompanyB migration has no owner or ordering: freeze window with peers, `rsync --checksum` plus sha256 manifest, relative-link check, absolute-path rewrite of 22 files, the `log_action.py`/`harvest_tool_trail.py` shims, `MOVED.md`, the old tool refusing writes, and the memory-rule update. `~/Desktop/OtherCompanyB/GTM` does not exist today (verified: `ls` fails). WP-M's `pause_carry_in.py` and the OtherCompanyB pack paths depend on it.
- **Fix:** Either add a WP (or a coordinator step) owning the §14 P1 migration with its §0 P1 assertions as tests, ordered before M's carry-in, or state explicitly that Wave 2 builds against fixtures only and the migration is a named later step with its dependency on M, A1 and G.
- **Tagging note:** Scope: whole document (no WP owns the OtherCompanyB migration); anchored at the §9 M row, so listed under 08_seats_wps.md.

### FID-18 · gap

- **Where:** CONTRACTS.md §9 K row ('skills'); plan §10
- **Issue:** Plan §10 skills have no contracted interface or owner detail except `/gtm-pause` and `/gtm-resume`. Missing: `/gtm <company>` (company-parameterized; refuses unknown), `/gtm-onboard`, `/gtm-cycle` (must refuse outside `gtm_session.sh`), `/gtm-report`, `/gtm-audit`, `/gtm-signin` (navigate-only; relies on G-A's login-host allowlist).
- **Fix:** Add a §7.7 with each skill's args, the exact commands it runs, its refusal conditions, and its tests, owned by K.

### IMP-17 · missing-docs — **CROSS** (also `03_schemas.md`, `00_global_paths.md`, `07_notices_schedules.md`)

- **Where:** Exit-code tables: §3.12 cycle.py, §1.2 gtm_lists.py, §3.19 validate_run.py, §3.23 outside_actor.py, §3.17 autonomy_ladder.py, App. C 7 vs backup_state.py, §7.6 gtm_session.sh
- **Issue (first sentence):** m-5: Several tools are missing standard exit codes.
- **Full text (issue and fix):** under IMP-17 in the `03_schemas.md` section of this document.

### FID-22 · nit

- **Where:** Appendix C item 16 vs plan §0 P1 assertion
- **Issue:** Exempting `browser:` refs from the cross-pack `credential_ref` reuse check changes a written plan acceptance assertion ('credential_ref shared with another company → INVALID').
- **Fix:** Have the coordinator amend plan §0 P1's assertion text to 'gsm: credential_ref shared …' in the same change as item 16.

### IMP-22 · nit — **CROSS** (also `04_hooks.md`)

- **Where:** §4 gtm_hooklib intro (L2177-2181) and §9 B1 consumes
- **Issue (first sentence):** n-1: gtm_hooklib is said to import `approval_sig` (A2) and `gtm_pricing` (G), but B1's consumes column lists neither, and nothing in hooklib's listed API needs `gtm_pricing`.
- **Full text (issue and fix):** under IMP-22 in the `04_hooks.md` section of this document.

## Reviewer summaries (verbatim)

### `fidelity` lens — 4 blockers, 12 majors

I read both inputs in full: /Users/x/.claude/plans/gtm_autonomous_department_plan.md (v15, §20 treated as superseding) and /Users/x/.claude/tools/gtm/CONTRACTS.md. I checked claims against the committed code in ~/.claude/tools/gtm (company.py, activity_log.py, harvest_tool_trail.py), hooks/bundle_parity.py, spend.jsonl and the filesystem. I did not open, list or grep ~/Desktop/OtherApp. Nothing is missing, so this is a real verdict.

Verdict: not safe to execute literally. There are 4 blockers.

What holds up: the Agency separation is faithful and stricter than the plan. It covers gtm_slugs(), the transcript-directory skip, G-B rule i, the path gate and G-A rule 3b. It also correctly cards the §20.9c/§20.9a conflict and applies the stricter reading meanwhile. Also sound:
- The signed-approver design: HEAD trust root, a signature and nonce ledger checked at mint, execute and complete, and no card path for money.
- No match classes as `$`.
- Open Dental and PHI scoping, with a GTM-session arm and a seat arm, plus probe q with a stated fallback.
- Maker-checker read from each agent's own transcript, with reviewer ≠ drafter.
- The pause-scope table and the pause check inside the browser gate while a ticket is live.
- HIPAA routing into the untrusted side store.

Blockers:
1. A card only has to be answered; the answer's content is never read. An operator "No" still authorizes shared-system actions, owner-listen, reverts and chain-repair. `resume` and `autonomy` match a pause name or the word "autonomous" anywhere in the card block, question included.
2. Isolation matches only `account_id` against the company's own identity values. The target URL is checked only against other companies, and link and user targets are not checked at all. Linking to an unknown other business passes as a notify-then-execute action.
3. For `*_enable` money rows, the signed amount is never compared with the budget actually configured on the platform. A paused campaign can be created with any budget and enabled on a smaller signature.
4. For `website_static`, reviews and content checks cover only paths plus a summary. The session writes the real content afterwards, so a banned claim can land with every lane passed, and the deploy gate is not handled.

Main risks and gaps:
- `_nomatch` public content (including all Meta ad copy) skips the specialist lanes.
- The "operator terminal" test can be faked by an agent (pty plus unset CLAUDECODE).
- The pack (`company.json`) is read from the working tree, not HEAD.
- Transcripts, the ground truth for maker-checker, are not write-protected.
- Nothing produces sign-in or chain-repair cards.
- Breaker pauses contradict §20.6's automatic re-promotion.
- The inbox review-reply reviewers are under-specified now that O6 is superseded.
- List-send quiet hours and SMS consent are undefined.
- Revert children skip the content checks.
- The over-cap path is ambiguous about writing PAUSE.budget.
- No work package owns `docs/agents` for the 9 new seats, the OtherCompanyB migration, or the plan §10 skills.
- There is no BAA gate on OtherCompany's lead sink.

Record with: `python3 ~/.claude/hooks/record_plan_review.py <repo> --blockers 4 --plan /Users/x/.claude/tools/gtm/CONTRACTS.md`. Any finding deferred rather than fixed must be filed as a tracked issue before Wave 2 starts.

### `implementability` lens — 3 blockers, 9 majors

VERDICT: blockers=3

I reviewed `/Users/x/.claude/tools/gtm/CONTRACTS.md` (untracked, 3,870 lines) for whether ~15 parallel implementers can build from it. Its risk tier is `trivial` (docs-only), but several findings are about gate and security design, so trust-architect should also review B-3 and M-2.

**Blockers (the implementers would produce incompatible or unsafe code):**
- **B-1:** A1's command registry can't express A2's `ticket` and `run-holds` commands, whose policy depends on flags, and `run-holds --all` has no per-company context.
- **B-2:** Row ids can't be split into `object_class`/`action`. The drafters, tier table, runbooks and verb map will guess differently, and mismatches silently become `$` (`_nomatch`) actions.
- **B-3:** Any agent can fake the "operator terminal" test (`env -u CLAUDECODE script …`) and so lift an owner pause or leave shadow.

**Majors (9), each checked against the real code:**
- **M-1:** The Bash gate goes live mid-Wave-2 and blocks the implementers' own `cp`/`rm` of `gtmlib` and `act.py`, including the single-file backup the falsification checks need.
- **M-2:** The trust check (TRUST_PATHS) misses the pricing sources `gtm_pricing` delegates to (the dashboard's `pricing.py`, `telemetry/pricing.json`) and `model_policy.json`. An uncommitted edit to any of them can disable the AI-spend cap.
- **M-3:** `pretooluse_task.py` can't tell when the pacer denies: `apply_decision` returns 0 on every path.
- **M-4:** The existing `block_prod_mutations` hook's R5 rule denies GTM browser clicks on `example.com` and `otherapp.example`, two GTM companies' own sites.
- **M-5:** A backup can capture the action log and its chain anchor at different moments; restoring it writes a false `PAUSE.chain`.
- **M-6:** The card-authorship scan covers up to 30 days of transcripts (measured: 21 GB, 19,947 files).
- **M-7:** L3's `runbook_validate.py` and `testkit.py` have no defined API, so L1/L2 can't stub them.
- **M-8:** Recording failed connector writes under the action id makes retries replay the old failure forever.
- **M-9:** K's required `ticket` commands omit `--company`, which dispatch requires, so they exit 2.

Nine minors and four nits cover exit-code gaps, the heartbeat watchdog missing the new statuses, the `seat_sets` signature, activity-log call hygiene and timezone handling.

**What I verified:**
- I ran `validate_company` in a scratch tree on the Appendix A fixture: it returns `(True, [])`. The `zeta` copy fails on `credential_ref` reuse and identity overlap, as the contract says. `interactive` is already accepted as a dispatch-cap key, so the Appendix A hedge is unneeded.
- I confirmed against real code: the `_lib` helpers named in §4.2, the `resolve_block` gate order, `claim_ttl_from_env`/`DEFAULT_CLAIM_TTL`, the spend/claim/stop row shapes, `backup_state` flags and restore behaviour, `activity_log` ACTIONS/actor rules/`cmd_add` ordering, the operator-input card format in CSA `OPERATOR_DECISIONS.md` ([120]–[125] match §2.6's regexes), the settings.json hook shape, and the `review_risk_tier`/`check_safety_core_parity` names.
- The coordinator prerequisites (`gtm_slugs`, `harvest_paths`, `project_dir_name_text`, the `browser:` credential exemption) are not yet in the working tree, which matches Appendix C.

**No tests exist to run for a contract document.** Every behavioural claim about code that isn't written yet is UNVERIFIED by design.

**Not covered:**
- `~/.claude` has no `.claude/oversight/dev-runtime.md` dossier, so I judged against runtime CLAUDE.md and the real module code.
- I read only the relevant parts of §3.4.4, Appendix B and the approver Swift details (§5.2–5.3).
- Not checked: `model_pin_gate`/`sync_agent_rules` internals for the new seats; the `exit_contract.py` and `MISSION_SCHEMA.md` interplay; the Playwright MCP 0.0.70 tool list; probes f, i, l2 and q.

Per the operator directive, I never opened, listed or read anything under `~/Desktop/OtherApp`.
