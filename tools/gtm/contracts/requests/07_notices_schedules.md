# Change requests from `07_notices_schedules.md` (§7) to other contract files

Raised while resolving the §7 findings in `OPEN_FINDINGS.md`. Each names the target file, section,
and the exact change. §7 already relies on the behaviour below; until it lands the two files disagree.

## R1 — `02_act.md` §2.4 `ingest-findings` row (FID-10: sign-in notices)

Add, after the `runaway_spend` sentence:

> **For each `kind: "signin_missing"` finding** (its `system` must be a tier system of the pack's
> `scope.channels_in_scope`; any other value → the finding is skipped and listed in
> `result.signin_skipped`), it writes, in-process via `notices.write_notice`, a `signin_missing`
> notice (`severity` `warn`, `push=True`, `system=<system>`, `dedupe_key`
> `signin_missing:<system>`, `created_by` `act`, body = `run <run_id>: <finding text>`).
> **Resolution:** when the agent's final `gtm-result.status == "ok"` and it was the
> `bound_agent_id` of a `read` ticket (any status) naming systems T, every open `signin_missing`
> notice of the company whose `system` ∈ T and which this result did **not** report is resolved
> (`resolution: "read ok <run_id> by <agent_id>"`). Prints `signin_notices` and `signin_resolved`
> (notice ids) alongside the existing keys. Tests (A1): a fixture analyst result with one
> `signin_missing` finding → one open pushed notice with `system` set; a second ingest creates none;
> a later clean analyst result whose read ticket names that system resolves it, and one whose ticket
> does not name it leaves it open; falsified by removing the resolution branch.

§7.5 E2 now runs `ingest-findings` after **every** `gtm-analyst` dispatch (not only ones with
findings), so the resolution branch always gets its chance.

## R2 — `08_seats_wps.md` §8.1 `gtm-result` block (FID-10)

- `findings[].kind` enum: `general|runaway_spend|phi_encountered|signin_missing|other`.
- Every `findings[]` entry gains `"system": null` — required non-null (a tier system name) when
  `kind == "signin_missing"`; `extract_gtm_result` callers treat a `signin_missing` entry with a null
  `system` as skipped.
- The `gtm-analyst` and `gtm-operator` agent files / primers (H1/H2) carry the §7.5 "Sign-in
  detection" instruction, verbatim, so the rule holds in interactive dispatches too, not only in the
  scheduled prompts.

## R3 — `08_seats_wps.md` §9 WP table

- **D row (IMP-16):** add `hooks/heartbeat_audit.py` (three new status branches + docstring, §7.2
  "Watchdog coverage") and `hooks/tests/test_heartbeat_audit.py`. `hooks/` is a HIGH risk-tier path,
  so D's commit for these two files takes full Opus review.
- **D row (FID-10):** `notices.py` gains `card-draft` / `card-mark` and the notice keys `system`,
  `card_id` (§7.1); tests listed there.
- **K row (IMP-21, IMP-17):** the plist renderer's timezone conversion and refusal rules (§7.3
  "Timezones") with their K tests; `gtm_session.sh`'s `100 + min(n, 27)` exit mapping (§7.6).

## R4 — `08_seats_wps.md` Appendix B (new DECIDED HERE items from §7)

1. §7.1 — Sign-in and chain breaks each get one batched card (`notices.py card-draft`/`card-mark`,
   deduped by the notice's `card_id`); breaker trips get no card (plan §20.11 supersedes §6.8's
   "+ card"). **The chain card is a recorded deviation from plan §20.11** (which names only `$`,
   sign-in and Meta-portfolio cards) and needs ratification by the specialist panel: it exists
   because `chain-repair` (02_act.md §2.4) is built on an answered card with subject
   `chain_repair <slug>`, and the `S/operator_ok/` marker does not cover `chain-repair`. The chain
   card is posted with `--subject "chain_repair <slug>"`; after a `deny` answer a fresh card is
   drafted only 7 days after the denied card was posted (`card-mark --replaces`). If the panel picks
   the marker instead, 02_act.md §2.3/§2.4 must add `chain_repair` to the `operator_ok` commands and
   §7.1/§7.5 E1 drop the chain card.
2. §7.3 — Calendar entries are rendered in machine time, converted from the pack timezone; packs
   whose offset to the machine is not constant over 365 days, or whose day-of-month entry would cross
   midnight, are refused. **One plist per inbox slot** (`com.oversight.gtm.<slug>.inbox_<HHMM>`),
   each passing `--slot <HHMM>` to `run_gtm_job.sh`; the runner never derives the slot from the
   clock (IMP-21, matching 00_global_paths.md §0.3). Run times other than the inbox slots are the
   fixed company-local `RUN_TIMES` table of §7.3 (daily 10:00 Mon–Fri, monthly_load 12:30 Mon–Fri
   with the last-weekday guard, weekly 07:00 on `weekly_day`, monthly 05:00 on `monthly_day`), with
   per-kind alarms.
3. §7.2 — A duplicate `cycle.py open` for a scheduled run is an `ok` heartbeat with summary
   `skipped: duplicate_cycle`, not `failed`.
4. §7.6 — `gtm_session.sh` maps `claude`'s nonzero exit `n` to `100 + min(n, 27)`; 1 = its own
   internal failure before `claude` started.
5. §7.5 — **CSA operator tasks are `task` notices only** (pushed, on `GTM_Operator.html`, listed by
   every run's E6); nothing mirrors them to the tracking GitHub issue. This is a recorded deviation
   from plan §5 ("CSA: the tracking GitHub issue thread"), because no GTM session holds a GitHub
   write path and the pack names no tracking issue. Needs ratification; the overrule path is a
   non-GTM interactive step that files each open `task` notice through `gh_issue.sh` and resolves it.
6. §7.2 — Under a manual `ST/PAUSE`, `inbox`, `daily` and `weekly` scheduled runs start with
   `--paused` and run only their §7.5 "Paused runs" lists (inbox: reads, `ingest-findings`,
   `lead-append`, the lead-unanswered task; daily: the trust check and queue/budget reads; weekly:
   harvest/render/audit, the backup, the pending-commit list) — plan §6.8; F17 as corrected, **as
   amended by R23**. `monthly` and `monthly_load` write `skipped-paused`.
7. §7.6 — Scheduled sessions run `--permission-mode dontAsk` (never `acceptEdits`), pending probe f.
   Every session purges `.playwright-mcp/` on exit (and runs the full purge for hipaa packs).

Also correct the existing Appendix B item 59: "multi-time inbox uses a calendar array" is replaced
by "each inbox slot has its own plist passing `--slot <HHMM>`" (item 2 above).

## R5 — `04_hooks.md` §4.6 `ai_budget.py` (IMP-19)

- On the `# __main__` line: "`caps` prints exactly `effective_ai_caps(company, now)` as one JSON
  object `{"opus": {"usd": str|null, "source": str, "forged": bool}, "sonnet": {…}}` (both buckets
  always present)."
- In "Forged state": "a forged bucket reports `source: "forged"`, `usd: null`, `forged: true`."
- Add a B2 test that parses `caps` output for a signed, a `company_json`, a `report_only` and a
  forged fixture and asserts that shape. (§7.2 already refuses a bucket unless `source` starts with
  `signed:` **and** `forged` is false, so it is safe with either spelling of a forged `source`.)

## R6 — `04_hooks.md` §4 `gtm_hooklib.write_notice_file`

Notices written by hooks carry the two new §7.1 keys `"system": null, "card_id": null` (the
schema is shared; `card-draft` treats a missing `card_id` as null, but the writer should not rely on
that).

## R7 — `02_act.md` §2.9 / FID-11 (coordination, no text requested unless option B is chosen)

§7 assumes breaker trips post **no** card (plan §20.11). If FID-11 is resolved with option B
(breaker posts a lifting card), tell §7's owner: `notices.py card-draft` then needs a `--kind breaker`
branch and §7.5 an E-step for it.

## R8 — `03_schemas.md` §3.6 (IMP-13, dependency only)

§7.5 I3/W3 now state that `ticket --close` on an already-terminal ticket is an idempotent success
(exit 0, `result.already: <status>`). IMP-13 is also tagged to `03_schemas.md`; the §3.6 text (and
the `02_act.md` §2.4 `ticket` row's `--close` clause) must say the same.

## R9 — `00_global_paths.md` §0.3 cycle/run row (IMP-21) — **superseded**

The clock-derivation text this request asked for is withdrawn: §7.2/§7.3 now adopt 00's `--slot`
design (00_global_paths.md §0.3 and its request R8 to this file). No change to 00's slot text is
needed. Still optional: after the `--slot` sentence add "a second scheduled fire for an id already
opened is an `ok` no-op (07_notices_schedules.md §7.2)", and list the two card-id shapes
`signin_<slug>_<YYYYMMDDTHHMMSSZ>` and `chain_<slug>_<YYYYMMDDTHHMMSSZ>` (07 §7.1) in the id table;
both already match the card-id grammar. Also add the inbox label shape
`com.oversight.gtm.<slug>.inbox_<HHMM>` (07 §7.3) wherever 00 lists GTM job labels.

## R10 — `02_act.md` §2.3/§2.4 `ticket` (IMP-12, dependency only)

§7.5 now passes `--company <slug>` on every `ticket` call. If B-1/IMP-01's registry fix changes
`ticket`'s `company_from`, it must still accept a matching `--company` (dispatch refuses only a
mismatch).

## R11 — `02_act.md` §2.4 `card-post` / `chain-repair` (dependency only)

§7.5 E1 now posts the chain card with `--subject "chain_repair <slug>"`. No 02 text change is
needed (`CARD_SUBJECT_RE` already has `chain_repair <slug>`), but the A2 `cards.py` tests should
include the end-to-end case listed at the end of §7.1 "Card drafts": the E1 command + "Yes" lets
`chain-repair` succeed; "No" → `card_denied`; posted without `--subject` + "Yes" →
`card_subject_mismatch`.

## R12 — `03_schemas.md` §3.10 PAUSE row (≈L628) (F17 correction)

Replace the statement that a manual `ST/PAUSE` stops scheduled starts with: "A manual `ST/PAUSE`
blocks every T1+ action and write ticket; T0 reads, read tickets, `ingest-findings` and
`lead-append` stay allowed (plan §6.8). Scheduled runs of kinds other than `inbox` do not start
(`run_gtm_job.sh` heartbeat `skipped-paused`); `inbox` runs start with `--paused` and run only the
lead-capture steps (07_notices_schedules.md §7.2, §7.5 "Paused inbox run"). Only `DISABLED` stops
every scheduled start." Keep the table's `run_gtm_job.sh` reader column.

## R13 — `04_hooks.md` §4.6 `ai_budget.py` (one caps predicate) — **amended by R32** (output shape, zero cap)

Add `caps --company X --check`: exit 0 when both buckets of `effective_ai_caps(company, now)` have
`source` starting `signed:` **and** `forged == false`; exit 77 otherwise (a `company_json`,
`report_only` or forged bucket, a missing bucket or key); exit 1 on internal error. Both
`run_gtm_job.sh` (§7.2) and `gtm_session.sh --scheduled` (§7.6 step 1) call it and treat any
nonzero exit as a failure. B2 test: the IMP-19 fixture matrix (signed/`forged:false` → 0;
`company_json`, `report_only`, `forged:true` with a `signed:` source → 77), each falsified by
removing its clause.

## R14 — `03_schemas.md` §3.19 `missed_runs` (≈L1060)

"expected scheduled runs … from pack `cadence`" must also use the fixed company-local run times of
07_notices_schedules.md §7.3 `RUN_TIMES` (imported from `tools/gtm/render_plists.py`), since the
pack carries no times other than `inbox_checks`; inbox labels are per slot
(`com.oversight.gtm.<slug>.inbox_<HHMM>`).

## R15 — `02_act.md` §2.4 `read-run` and `ticket --write-batch`

- `read-run`: before running a collector, resolve its `network_hosts` (the `"@pack.domains"`
  sentinel expands to the pack's `brands[].domains` ∪ `identity_allowlist.domains`, with and
  without `www.`; any other `@…` token → exit 3) and refuse exit 3 `collector_host_denied` when a
  host equals or is a subdomain of an applicable `phi_denylist` host/suffix (03_schemas.md §3.20) or
  is `github.com` (agency-boundary). Add `collector_host_denied` to the §2.4 exit-3 reason list.
  Test: 07 §7.4's OtherCompany fixture.
- `ticket --write-batch`: refuse exit 3 (`batch_row_not_post_schedule`) when any named action's
  `row_id` does not end `.post_schedule` (07 §7.5 L1).
- `purge-untrusted` is now also run by `gtm_session.sh` after every session exits (07 §7.6 step
  4(d)) from inside the lease holder but outside `claude`; confirm it needs no GTM-session proof
  (it is `chain_policy: read`, §2.4) or add the §1.4 proof exemption for this caller.

## R16 — `00_global_paths.md` §0.1 / `company.py` / `harvest_tool_trail.py` (W2 dependency) — **amended below (r3)**

§7.5 W2 ships only after `company.py` adds `gtm_slugs()` (00 §0.1) and
`harvest_tool_trail._registered_homes()` (harvest_tool_trail.py:554) switches from
`company_mod.registered_slugs()` — which includes Agency — to `gtm_slugs()`. The owning WP adds a
test: a registry that holds `agency` produces no Agency project-dir glob. 08_seats_wps.md §9 should
list this as a prerequisite of K's weekly prompt.

**R16 amendment (r3 review; security).** `harvest_tool_trail.resolve_transcript_paths` gives
explicit argv paths priority ("Explicit paths always win", harvest_tool_trail.py ≈L726). Add: when
`CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is set in its environment, `harvest_tool_trail.py`
refuses any positional path argument (exit 2, one stderr line, nothing read or written). 07 §7.6
step 5 now grants only the exact no-argument command (no `:*`). Test: a session-env harvest given
an explicit transcript path (including an `~/.claude/projects/-Users-…-Agency/*.jsonl` fixture path)
exits 2 and writes no trail line; without the variables the same path is harvested (falsified by
removing the refusal).

## R17 — `04_hooks.md` §4.3 G-W (drafts-only write scope)

Add, in **GTM scope** (`CLAUDE_GTM_COMPANY` set or payload `agent_type ∈ GTM_SEATS`): deny
(`gtm-write-outside-drafts`) every Write/Edit/MultiEdit/NotebookEdit whose target is not under
`<H>/.claude/gtm/drafts/` of the session's company, with one carve-out for interactive sessions
only (no `CLAUDE_GTM_RUN` of a scheduled kind, i.e. a run id whose kind is `interactive`): the
pack's `marketing_paths` and the other editable paths §4.3's last sentence names (feature
inventories, shims, READMEs, snapshot `.md`). Scheduled runs are allowed no other path. Reason: 07
§7.6 step 5 — the session's working directory is the whole company home (the whole CSA repo), and
the permission mode alone is not a mechanical boundary. B1 tests: a scheduled-session Edit of a CSA
`modules/**` file is denied; a scheduled-session Write under drafts/ is allowed; an interactive
session's edit under a `marketing_paths` glob is allowed.

## R18 — `08_seats_wps.md` §9 WP table (new files from §7)

- **D row:** `tools/gtm/runner_probe.py` (python3 home reads for `run_gtm_job.sh`, TCC, §7.2);
  `notices.py` CLI restrictions (`resolve` kinds, `write --created-by`/`--kind`, `card-mark`
  posted-card check and `--replaces`, `resolved_by`), the chain post-deny rule, and the
  `GTM_Operator.html` escaping/CSP/field rules (§7.1), each with its D tests; the heartbeat
  `session_exit` field and carried `prior_status`/`prior_streak` (§7.2).
- **K row:** `tools/gtm/render_plists.py` (`RUN_TIMES`, per-slot inbox plists, `--check`,
  `--install-rows`, `test_render_plists.py`, §7.3); `tools/gtm/tcc_probe.py` (§7.6 step 3);
  `gtm_session.sh`'s `--paused`, lockf exit mapping, timeout marker, per-session purge and
  `dontAsk` mode (§7.6); the literal-command-form and no-`implement` checks in `test_k_prompts.py`
  (§7.5). The weekly prompt depends on R16.
- **F row:** `@pack.domains` sentinel in `collectors/registry.json` (§7.4).
- **B1 row:** R17's G-W rule.

## R19 — `04_hooks.md` §4.6 gate-gtm (non-roster dispatch in scheduled runs; r2 review A3)

Add a decision step before step 0: when `CLAUDE_GTM_RUN` is set and `CYCLE_ID_RE` gives it a kind
other than `interactive`, deny every `Agent`/`Task` dispatch whose `subagent_type` is not in
`system_names.GTM_SEATS ∪ DEPARTMENT_SEATS` (`gtm-nonroster-dispatch`, logged like the other gate-gtm
denies). Interactive GTM sessions keep today's "non-GTM agent types: untouched" rule. B2 tests: a
scheduled-run fixture dispatching `implement` and `general-purpose` → both denied; `gtm-analyst` and
`marketing-director` → allowed; the same `implement` dispatch in an interactive GTM session →
allowed; falsified by removing the step. 07 §7.6 step 5 installs no scheduled prompt until this and
R17 have landed.

## R20 — `02_act.md` §2.4 / §2.11 (who resolves a `card` notice)

`card` notices (written by `authorize` for `awaiting_card` and by `revert` step 1) are resolved
in-process by `act.py` — never from the `notices.py` CLI, which refuses kind `card` (07 §7.1) — in
the same command that records the card's answer: `record-external --kind approval` (any decision
other than `unclear`) and the approving `authorize`/`revert` step 2, via
`notices.resolve_by_dedupe_key(company, "card:<action_id>", "<decision> <card_id>", resolved_by="act")`.
So the `card` notice's `dedupe_key` must be `card:<action_id>` (state it in the `authorize` and
`revert` rows). A2 test: an `awaiting_card` action's notice is open until the card's answer is
recorded, then `resolved` with `resolved_by: act`; an `unclear` answer leaves it open.

## R21 — `02_act.md` §2.4 `chain-repair` and `gtmlib/chain` (r2 review A6)

- Add a read-only fold `gtmlib.chain.post_break_actions(ctx) -> list[str]`: the sorted ids of every
  action with at least one event after the last entry whose hash verifies. It never writes and is
  `read` chain policy (07 §7.1 `card-draft --kind chain` calls it for the card body).
- `chain-repair` carries every action in that list into the new genesis in state `proposed` (its
  approvals, tickets, holds and card records not carried), never `authorized`, `held`, `ticketed` or
  any other post-`proposed` state; actions whose events all precede the break carry their folded
  state as today.
- A1/A2 test (with 07's D test): a forged `authorized` event appended after the break point ends up
  `proposed` after a "Yes" repair, and `act.py execute` on it exits 3; falsified by carrying the
  folded state as-is.

## R22 — `00_global_paths.md` §0.1 `company.py` (GTM-company check for shell entry points)

Add the CLI `python3 <R>/tools/gtm/company.py is-gtm <slug>`: exit 0 when `slug ∈ gtm_slugs()`, 13
otherwise (incl. `agency` and `runtime`), 2 usage, 1 internal; it never stats a home path (it only
evaluates `gtm_slugs()`, which itself never stats before its Agency exclusion). Used first by
`run_gtm_job.sh` (07 §7.2) and `gtm_session.sh` (07 §7.6 step 1). Test: `is-gtm agency` exits 13
and the no-Agency-touch oracle records nothing.

## R23 — paused daily and weekly runs (r2 review A8; amends R12 and R4 item 6)

- **`03_schemas.md` §3.10 PAUSE row** — R12's replacement text becomes: "A manual `ST/PAUSE`
  blocks every T1+ action and write ticket; T0 reads, read tickets, `ingest-findings` and
  `lead-append` stay allowed (plan §6.8). Scheduled `monthly` and `monthly_load` runs do not start
  (`run_gtm_job.sh` heartbeat `skipped-paused`); `inbox`, `daily` and `weekly` runs start with
  `--paused` and run only their reduced lists (07_notices_schedules.md §7.2, §7.5 "Paused runs").
  Only `DISABLED` stops every scheduled start."
- **`08_seats_wps.md` Appendix B #83** — replace "scheduled runs of every kind **except `inbox`**
  skip with `skipped-paused`; an `inbox` run still starts …" with: "`monthly` and `monthly_load`
  skip with `skipped-paused`; `inbox`, `daily` and `weekly` runs start with `PAUSED=1` and run only
  their 07_notices_schedules.md §7.5 "Paused runs" lists (inbox: read ticket, analyst read,
  `ingest-findings`, `lead-append`; daily: trust check, queue and budget reads; weekly:
  harvest/render/audit, backup, pending-commit list; no `run-holds`, `propose`, `authorize`, write
  ticket or card)". The rest of #83 (reasons, test) stays. This supersedes `requests/08_seats_wps.md`
  item 18's "no text change".
- Reason: skipping every daily and weekly run for the length of a pause dropped the weekly backup
  (plan §3.2), the harvest/audit that detects outside changes, and the daily trust check — all local
  or read-only steps plan §6.8 allows under a pause.

## R24 — `05_approver.md` (signed `0.00` AI cap renders as NO CAP; r2 review A7) — **SUPERSEDED by R33** (a signed `0.00` is now a zero cap)

Already present (05_approver.md ≈L80: the dialog renders a `gtm_ai.weekly_cap_edit` whose new
value is `0.00` as `NO CAP — report only, unlimited AI spend`, with a WP-C test). No change needed;
listed so 07 §7.2's citation resolves.

## R25 — `04_hooks.md` §4.4 path gate (env canary; r2 review A10)

On the first GTM-scoped PreToolUse it sees in a session (`CLAUDE_GTM_COMPANY` and
`CLAUDE_GTM_SESSION` both set in the hook's environment), the path gate writes
`R/.gtm_state/env_canary/<CLAUDE_GTM_SESSION>.json` = `{"ts", "session_id", "company"}`
(create-exclusive; an existing file is left alone; a write failure logs `gate-fault` and never
changes the decision). It is written **before** the gate decides, so the §7.5 E0 Glob that triggers
it finds it. `act.py purge-untrusted` deletes canaries older than 7 days. `R/.gtm_state/env_canary/`
joins the 00_global_paths.md §1.2 `S` layout (writer: the path gate; readers: 07 §7.5 E0 and §7.6
step 4(d)). B1 tests: a Glob with both variables set writes the canary before the Glob runs; without
`CLAUDE_GTM_COMPANY` nothing is written; falsified by removing the write.

## R26 — `02_act.md` §2.4 `status` (day-after verification by state; r2 review A4)

Add two filters to `status`: `--unverified` (only actions with no `verify.status`) and
`--completed-before <UTC ISO>` (only actions whose `completed` event `ts` is before it); both combine
with `--state completed`. A1 test: of three completed actions (one verified, one completed 20 h ago,
one 2 h ago), `--state completed --unverified --completed-before <now − 18 h>` prints only the
20-hour one. 07 §7.5 D6 uses exactly this form.

## R27 — `02_act.md` §2.4 `read-run` and `08_seats_wps.md` §9 F row (collector traffic; r2 review A5)

- `read-run` (02): resolve hosts only through `collectors/hosts.allowed_hosts(slug, collector)`
  (WP-F); refuse exit 3 `collector_host_denied` for a literal `network_hosts` entry equal to, or a
  subdomain of, an identity value of another pack or of `other_businesses.json`
  (`identity_index.json`); accept only `--arg` keys the registry entry declares in its `"args"` map
  (else exit 2), `realpath` every `path` value and refuse exit 3 `collector_arg_denied` for one
  outside the company home, under `agency_root()`, or matching the `phi_denylist` path/ancestor rule
  (04_hooks.md §4.4 logic, imported); refuse exit 3 `collector_out_of_scope` when no `systems` entry
  equals `tier_system_of(c, pack)` for a channel in `scope.channels_in_scope`; map a collector exit 3
  to its own exit 3 `collector_host_denied`. Add the three new reason codes to the §2.4 exit-3 list.
  D tests as listed in 07 §7.4.
- F row (08 §9): `tools/gtm/collectors/hosts.py` (`allowed_hosts`), `tools/gtm/collectors/_http.py`
  (`fetch`, manual redirects ≤ 5, per-hop host check, `CollectorHostDenied`), the registry `"args"`
  map, and the F tests of 07 §7.4 (the redirect fixture; the no-direct-network-import test).

## R29 — `00_global_paths.md` / `08_seats_wps.md` Appendix C (pack schema): cadence value checks (r2 review B11)

`company.py validate` checks the `cadence` sub-keys exactly as 07 §7.3 "Cadence inputs" refuses them:
`inbox_checks` a non-empty list (≤ 6) of distinct `HH:MM`; `weekly_day` ∈ `MON TUE WED THU FRI SAT
SUN`; `monthly_day` an integer 1–28; `monthly_load_day` only `last_weekday`; no other `cadence` key.
Test: each invalid value → INVALID naming the key. (Today `validate` checks only top-level keys.)

## R30 — `02_act.md` §2.4 `card-post` (duplicate card id)

Give the "id already present anywhere in the file" refusal its own reason code, `card_id_exists`
(still exit 3), distinct from the other card-post refusals, so 07 §7.5 E4 can treat a re-posted card
as "already posted" and every other exit 3 as a failure. A1 test: posting the same `--card-id` twice
→ the second exits 3 with `error.code == "card_id_exists"` and the file unchanged.

## R31 — `08_seats_wps.md` §9 WP table (additions from the r2 fix of §7)

- **D row:** the interpreter check and `__PY_DIR__`-driven `PATH` rule in `run_gtm_job.sh` (§7.2
  "Interpreter pin", its D test).
- **K row:** `render_plists.py`'s interpreter resolution, cadence-value refusals and
  `StartCalendarInterval` form (§7.3); the `knowledge/oversight_install.md` §7 rewrite (§7.3);
  `gtm_session.sh`'s `CSA_DISABLE_HOOKS`, interpreter and `is-gtm` refusals, positional locked-child
  arguments, held-lease message and env-canary check (§7.6); the per-type `Agent(<type>)` and `//`
  drafts rules (§7.6 step 5); the E0/E4/E6/I6/D6/D9/W1/W2 and paused-run K checks (§7.5). K's
  scheduled prompts depend on R17 and R19 landing (§7.6 step 5).
- **F row:** R27.
- **B1 row:** R25; **B2 row:** R19.
- **Appendix B:** add "07 §7.5 E4 — cards are posted only after `act.py authorize`, keyed on its
  result state, always with `--action` and never a hand-written `--subject`" and "07 §7.4 — collector
  traffic is checked per request and per redirect hop through `collectors/_http.py`, not only on the
  declared hosts".

---
*Requests below come from the r3 review of §7 (2026-09-27).*

## R32 — `04_hooks.md` §4.6 `ai_budget.py` (signed `"0.00"` = zero cap; amends R13)

- Replace the sentence "`"0.00"` = report only — reachable after the first signed cap **only** by
  another signed approval …" (≈L796) with: "`"0.00"` = **a zero cap**: `budget_state` reports the
  bucket over its cap from the first dispatch, so every GTM dispatch is denied except the plan §6.8
  reserved lead-capture allowance, exactly as for any exceeded cap. Plan §20.13 ('a pause is amount
  0') and 03_schemas.md §3.7 (`new_absolute_value` `"0.00"` = pause/stop/remove) give it this
  reading. Turning enforcement off after sign-off is the separate signed report-only form (R34),
  never `0.00`." Keep the rule that `company.json`'s cap is ignored once a signed cap exists.
- `caps --company X --check` (R13) prints one JSON object `{"pass": bool, "reason":
  null|"unsigned"|"forged"|"malformed", "zero_cap": bool, "zero_cap_enforced": true,
  "report_only_signed": bool}` and exits 0 iff `pass`, 77 otherwise, 1 on internal error.
  `zero_cap_enforced` is the constant `true` in the version that implements the zero-cap reading;
  07 §7.2/§7.6 refuse to start a scheduled run under a signed zero cap unless that key is `true`
  (ship-ordering: an `ai_budget.py` without it fails closed).
- B2 tests (each falsified by removing its clause): a signed `"0.00"` opus bucket → `budget_state`
  over cap; a gate-gtm dispatch of a non-inbox `gtm-analyst` is denied and the reserved inbox
  lead-capture dispatch allowed; `caps --check` prints `zero_cap: true, zero_cap_enforced: true`,
  exit 0; the IMP-19 fixture matrix of R13 still decides as stated.
- Same change: 04 §4.6's `effective_ai_caps` docstring and any "report only" wording tied to `0.00`.

## R33 — `05_approver.md` §5.1 dialog (zero cap; supersedes R24)

The dialog renders a `gtm_ai.weekly_cap_edit` request whose `new_absolute_value` is `"0.00"` as
`$0.00 / week — ZERO CAP: every GTM AI dispatch stops except lead capture` (never as `NO CAP`), and
the reason string (the Touch ID prompt text, ≈L118) says the same. `NO CAP — report only, unlimited
AI spend` is used **only** for the R34 report-only form (`unit: "report_only"`,
`new_absolute_value: null`). WP-C tests on the rendered dialog text and reason string for both
cases, each falsified by swapping the two texts.

## R34 — `03_schemas.md` §3.4.4/§3.7, `05_approver.md`, `04_hooks.md` §4.6 (signed report-only form)

- 03 §3.4.4 `gtm_ai.weekly_cap_edit` row and §3.7 null rule: add case (iv) — `new_absolute_value:
  null` with `unit: "report_only"`, allowed only on `gtm_ai.weekly_cap_edit` (any other row →
  refused `unit_invalid`). Both values are already signed payload keys, so the 12-key payload set
  (05 §5.5 3a) does not change.
- 04 §4.6 `effective_ai_caps`: such a consumed, verified record gives `usd: null, source:
  "signed:<request_id>", forged: false` and `budget_state` never trips on that bucket;
  `caps --check` reports `report_only_signed: true` and passes.
- 05: dialog and reason text `NO CAP — report only, unlimited AI spend` for this form only (R33).
- Tests: A2 (request creation with the form), B2 (effective caps), WP-C (dialog text).

## R35 — `03_schemas.md` §3.12 `cycle.py close --if-running`

Add the flag `--if-running` to `cycle.py close`: when the record's `status` is not `running`, exit
0, change nothing, print `{"ok": true, "closed": false, "status": "<current>"}`; when it is
`running`, close as today and print `"closed": true`. Without the flag, behaviour is unchanged
(a closed record → exit 3 `closed_cycle`, stated as `error.code`). Used by 07 §7.2 after every
session. G test: close `--if-running` on a `missed` record → exit 0, record unchanged; on a
`running` record → closed.

## R36 — `02_act.md` §2.4 `authorize`, §2.6 rule 2, §2.11 (`card_on_refuse` card and its resolver)

- `authorize`'s printed result for a `refused` outcome carries `result.card_on_refuse: bool`,
  `result.row_id`, `result.system`, `result.reason` (the refusal code; never action text), so 07
  §7.5 E4 can post the informational card from ids alone.
- §2.6 rule 2: the `card` notice written for a `card_on_refuse: true` refusal uses `dedupe_key`
  `card:<action_id>` (the R20 key), `created_by: act`.
- §2.11 `record-external --kind approval --card <action_id> --action <action_id>` on an action in
  `refused` whose row has `card_on_refuse: true`: the card must be answered (else exit 3
  `card_unanswered`); its posted subject must be `null` or `authorize <action_id>` (else
  `card_subject_mismatch`); decision `approve` or `deny` → append `card_recorded` only (the action
  stays `refused`; NEVER is not operator-overridable), resolve `card:<action_id>` in-process
  (`resolved_by: act`, resolution `"<decision> <card_id>"`), exit 0; `unclear` → exit 3
  `card_answer_unclear`, nothing appended. Add `refused` (card_on_refuse rows only) to the
  `record-external --kind approval` state set in the §2.5 table.
- A2 tests: a `meta.business_portfolio_create` fixture → `authorize` refused with
  `card_on_refuse: true` and one open `card` notice; its card answered "Yes" → the notice
  resolved, the action still `refused`; answered "maybe" → exit 3, notice open.

## R37 — `03_schemas.md` §3.14, `08_seats_wps.md` Appendix C, R29 (new pack keys)

- `lead_sink.response_target_minutes`: required integer 5–10080 (the lead response target used by
  07 §7.4 `speed_to_lead` and §7.5 I6). `company.py validate` refuses a missing or out-of-range
  value (INVALID naming the key), as in R29.
- `budget.paid_daily_usd_alarm`: a money string `^(0|[1-9]\d*)\.\d{2}$` or `null` (null = only the
  per-object 1.5× rule of 07 §7.4 `ad_spend_pacing` applies); validate refuses any other value.
- 03 §3.14: state the lead-id grammar (07 §7.5 I6 skips an entry whose `lead_id` fails it).
- Appendix C adds both keys to the pack schema and to every fixture pack.

## R38 — `08_seats_wps.md` Appendix B (page vs plan §20.8; ratification)

Add: "07 §7.1 — `GTM_Operator.html` lists pending `$` requests by id, amount, unit and timestamps
only, **not** with the plan §20.8 current metrics / best-practice source / expected effect / risk
/ reversal, because that `money_brief` text is untrusted and on a hipaa pack may carry PHI, and the
Desktop page is outside every purge. The brief is shown in GTMApprover (03 §3.7 display rows,
05 §5.1), where the operator signs. Recorded deviation from plan §20.8, pending ratification by the
specialist panel; the overrule path is to render the five fields HTML-escaped on non-hipaa packs
only, ids-only on hipaa packs."

## R39 — `08_seats_wps.md` Appendix B + plan §20.13 text (per-slot inbox labels)

Add: "07 §7.3 — inbox runs use one plist per slot, `com.oversight.gtm.<slug>.inbox_<HHMM>`, not
the single `com.oversight.gtm.<slug>.inbox` that plan §20.13 names: one plist cannot pass a
per-slot `--slot`, and the runner never derives the slot from the clock (00 §0.3, IMP-21).
Recorded deviation; the plan text should be updated to the per-slot label." (R4 item 2 already
describes the design; this names it as a plan deviation.)

## R40 — `06_connectors.md` §6.3/§6.6, `05_approver.md`, `08_seats_wps.md` #133 (sign-in card inputs)

07 §7.1 "Card drafts" now defines every input of the one batched sign-in card. The producers
outside 07:
- **06 §6.6 `secret_sink.py`:** when its `--prompt <name>` fallback is the only capture path,
  write in-process a `task` notice `dedupe_key: signin_step:secret_prompt:<name>` (`created_by:
  secret_sink`, warn, push; title/body fixed, naming only `<name>`), and resolve it
  (`resolve_by_dedupe_key`, `resolved_by: secret_sink`) when `<name>` is stored. On ROTATE, also
  write `signin_step:revoke:<ticket_id>` (the platform revocation step "on the batched sign-in
  card"), resolved when the re-capture for that action succeeds.
- **06 §6.3 route `impersonate`:** on `CredentialUnavailable("token_mint_failed")` the
  credential getter writes in-process `signin_step:iam:<system>` (`created_by: act`, warn, push),
  resolved on the next successful mint for that system. (The line renders the SA email and
  `gcloud_account` from the committed `connectors.json`.)
- **05 ≈L852 ("the operator loads it via the batched sign-in card"):** no 05 change beyond noting
  that `notices.py card-draft --kind signin` itself produces the approver-not-running line
  (heartbeat older than 15 min + a pending request).
- **08 Appendix B #133:** list the five inputs (a)–(e) of 07 §7.1 and state that the card is posted
  every non-paused run (E3), not only after a ticket-holding dispatch.
- L/M tests: each producer writes its notice once (deduped) and resolves it on the stated event.

## R41 — `02_act.md` §2.4 `purge-untrusted --all --hipaa-only` (holds-job purge)

Add the form `purge-untrusted --all --hipaa-only`, admitted only under the `GTM_HOLDS_JOB=1`
not-GTM-session exception (the one `run-holds --all` uses, §2.3); it iterates `gtm_slugs()` and
runs the full purge for each pack with `regulated ∋ hipaa` only; allowed under `DISABLED` and every
pause (like `purge-untrusted` today, 03 §3.10); exit 0 when every company purged, 1 when any
failed (each failure one stderr line naming the slug). `--all` without `--hipaa-only`, or either
flag outside the holds-job exception → exit 2 / the existing `not_gtm_session` refusal. A1 test:
with `DISABLED` present, a hipaa fixture pack's 31-day-old `ST/untrusted/` file is deleted and a
non-hipaa pack's is not.

## R42 — `02_act.md` §2.4 `read-run`, `08_seats_wps.md` §8.1 and §9 F row (runaway detection path)

- **`read-run` run id:** `read-run` has no `--run` flag; it passes the session's `CLAUDE_GTM_RUN`
  to the collector as `--run` and refuses exit 3 `no_run_context` when it is unset or fails
  `CYCLE_ID_RE`. Add the code to the §2.4 exit-3 list. The output path is
  `ST/collectors/<run_id>/<collector>.json` (unchanged).
- **`"findings": true` collectors:** for a registry entry with `"findings": true`, after the
  collector exits 0, `read-run` passes `data.findings[]` through the same in-process branch as
  `ingest-findings` for `kind: "runaway_spend"` only (urgent pushed notice, dedupe
  `runaway_spend:collector:<collector>:<finding id>`, works under `PAUSE.chain`/`PAUSE.budget`),
  stores each finding's `stop` (a complete 03 §3.2 proposal) **under `ST/stops/<finding id>.json`
  with its sha256 in `ST/runaway_stops.jsonl`** (amended r5 by R62; the former `G/drafts/stop_…`
  location is withdrawn), and adds `result.runaway_spend: [{"finding_id", "has_stop", "stop_note"}]`
  (`has_stop: false` when `stop` is absent or fails 03 §3.2 stage-1 shape validation).
- **08 §8.1:** `findings[]` entries of kind `runaway_spend` may carry `"stop": <03 §3.2 proposal>`
  (collectors always do; seats may instead put the stopping proposal in `proposals[]` with
  `money_brief.urgency: "urgent"`, which 07 §7.5 E2b proposes with `--from-agent`).
- **F row:** `tools/gtm/collectors/ad_spend_pacing.py` (07 §7.4, **amended r5**: `evaluate(read_fn,
  pack, now)` with the `build_read_ctx` collector path and the in-process `_build_ctx` path of `act.py
  pacing`; the per-system delivery ceilings of 07 §7.4's `PACING_DOCTRINE` — Google > 2.0× average
  daily budget or month-to-date > 30.4×, Meta > 1.75× daily or lifetime spend > lifetime budget —
  and the `budget.paid_daily_usd_alarm` account rule; the pinned finding-id regex; the per-level
  `stop` table incl. `stop: null` notes; browser-only `data.skipped`) and the `speed_to_lead` changes (`inbox_class: false`, the exact `data`
  key set incl. `response_target_minutes` and `unresponded_past_target`, the no-lead-text F test).
- Tests: A1 — a `findings: true` fixture collector reporting one runaway → one urgent notice, one
  `stop_…json` under drafts/, `result.runaway_spend[0].stop_file` set; a second run the same day
  creates no second notice. F — the threshold tests are 07 §7.4's (Google 1.9×/2.1×, Meta 1.7×/1.8×,
  month-to-date 31×, account-local day); the former "2× budget emits one finding" test is **deleted**
  (superseded r5: 2× is not over Google's ceiling). Every emitted `stop` passes `propose` stage-1
  validation.

## R43 — `02_act.md` §2.4 (`lead-append --from-agent`, `queue` keys, briefs, card lookup, touch-id notice) and `backup_state.py`

- **`lead-append --from-agent <agent_id> --index <i>`** (in addition to `--file`): reads the i-th
  `leads[]` entry of that agent's own final `gtm-result` via the transcript index, with the same
  identity check as `propose --from-agent` (§2.7(a); the agent must be a `gtm-analyst` spend row);
  `--index` out of range → exit 3 `lead_index_out_of_range`, nothing appended. BAA gate, fallback
  and `lead_appended` event unchanged. A1 tests as in 07 §7.5 I5. 07 §7.5 I5 uses only this form in
  scheduled prompts.
- **`queue`** rows carry at least `action_id`, `state`, `row_id`, `system`, `request_id` (null
  unless `awaiting_approval`) and never action text.
- **`status --review-brief`** prints only `result.brief_path` on stdout for every pack (no brief
  content), as today; state it as a rule with an A1 test (a marker in the draft reply never
  appears on stdout).
- **`record-external --kind approval --card <id>`** for a card id with no block in the
  operator-input file and no `ST/cards_posted.jsonl` row → exit 3 `card_unanswered` (not a new
  code), so 07 §7.5 E1b treats "never posted" like "still open".
- **Mirror-card "Yes"** (§2.11): its `info` notice ("Approval needs Touch ID in GTMApprover") uses
  `dedupe_key` `touchid:<request_id>` so E1b re-recording the same answer every run creates no new
  notice; it is resolved when the request is decided.
- **`backup_state.py --restore`** (its owning WP per 08 §9) prints `result.counts` =
  `{"actions_jsonl_lines": int, "actions_chain_ok": bool, "files": int}` for the restored tree
  (07 §7.5 M1 reports these instead of Reading the restored files). Test: a fixture archive with a
  3-line chained `actions.jsonl` → `3`, `true`.

## R44 — `04_hooks.md` §4 `gtm_hooklib.write_notice_file`, `05_approver.md` `approval_sig.write_trust_notice` (dedupe key)

Both direct writers dedupe on the tuple `(company, dedupe_key, created_by)` — an open notice of the
same company with the same key **and** the same `created_by` — matching 07 §7.1, so a notice
planted by one writer can never absorb another writer's real notice. B1 / WP-C tests: an open
`created_by: notices` notice with the writer's key does not stop the writer creating its own.

## R45 — `02_act.md` §2.3 and `00_global_paths.md` §1.4 (operator marker for stuck notices)

Add `notice_resolve` to `OPERATOR_OK_COMMANDS` (target = the notice id, grammar 00 §0.3), created
only by `operator_ok.sh notice_resolve <slug> <notice_id>` in the operator's terminal, consumed
single-use by `notices.py resolve --operator` (07 §7.1) under `S/operator_ok.lock`. Rule k's
literal list is unchanged (`operator_ok` already covers the script name). A1/D test: `resolve
--operator` with no marker → exit 3 `operator_marker_missing`; with a marker → resolved,
`resolved_by: operator`, marker deleted, a second call → exit 3.

## R46 — `08_seats_wps.md` §9 WP table and ordering (r3 additions)

- **Ordering (hard prerequisites):** R22 (`company.gtm_slugs()` + `company.py is-gtm`) and R16 (as
  amended) land, with their tests, before WP-D's `run_gtm_job.sh`, WP-K's `gtm_session.sh`,
  `render_plists.py` and weekly prompt ship. R32 lands before any scheduled GTM plist is loaded
  (07 §7.2 fails closed without it).
- **D row:** `notices.py` CLI hardening (company binding, `created_by_in_session`, reserved dedupe
  prefixes, `kind_needs_reserved_key`, `(dedupe_key, created_by)` dedupe, `resolve --operator`),
  the writer-allowlist `push_text`, the `push_text` key on `list --json`, the sign-in card's five
  inputs and the approver-heartbeat branch; `run_gtm_job.sh` label check, argument-parse placement,
  holds-job hipaa purge, `--if-running` close (R35), session-64 token mapping, `started` stub status
  and streak reset, the zero-cap/`--check` JSON handling; `runner_probe.py`'s scheduled-fire-date
  `run_date` and `is_last_weekday`; `heartbeat_audit.py`'s `started` status. Each with its §7.1/§7.2
  D tests.
- **K row:** `render_plists.py`'s interpreter resolution (realpath, venv/shim/home refusal, fixed
  `PATH` template), per-entry DST sampling and ordinal rule, no `__COMPANY_HOME__`;
  `gtm_session.sh`'s nine positional parameters, literal run-constant substitution and stdin
  prompt, one-argv-element-per-rule `--allowedTools`, hipaa no-WebFetch/WebSearch, exact-command
  harvest grant, lease rule printed at start, `tcc:<grant>` keys and per-grant resolution, `env -u`
  on its own notice writes, exit-64 stderr tokens; the prompt steps E1b, E2b, D3b, the E3 "always"
  rule, the E4 `card_on_refuse` branch, the E7 push-all rule, I5 `--from-agent`, I6 via
  `speed_to_lead`, I8 brief-path rule, D6 budget-state branch, D7 read, W2 exit handling, W6
  non-roster rule, M1 counts, the paused lists (E1b, D3b, D9, D10; E1 report-only); their K tests.
- **F row:** R42 (`ad_spend_pacing`, `speed_to_lead` changes).
- **A1/A2 rows:** R36, R41, R42 (read-run), R43, R45.
- **B2 row:** R32, R34 (04 part). **WP-C:** R33, R34 (05 part), R44 (05 part). **B1:** R44 (04 part).
- **Appendix B:** R38, R39; replace R4 item 1's "sign-in … get one batched card" wording with "the
  sign-in card batches the five inputs of 07 §7.1"; add "07 §7.2 — a signed `0.00` AI cap is a zero
  cap (budget state), and report-only after sign-off is its own signed form (R34)".

## R47 — `02_act.md` §2.4 `ingest-findings` row (FID-10; wording alignment with §7.5 E2)

Replace "The session runs it after **every** dispatch whose result carries findings, in the same run
(K prompts)." with: "The session runs it after **every** dispatch whose result carries findings and
after **every** `gtm-analyst` dispatch whatever it carries, in the same run (07_notices_schedules.md
§7.5 E2) — a findings-free analyst result is how an open `signin_missing` notice gets resolved."
Also state, with an A1 test, that a result with an empty `findings[]` prints the empty lists and exits 0
(while still running the `signin_missing` resolution branch).

## R48 — `04_hooks.md` §4 `write_notice_file` (created_by enum, keyword parity)

- Drop the default `created_by: str = "hook"`: `created_by` becomes a **required** keyword whose value
  must be a member of 07 §7.1 `NOTICE_CREATED_BY` (`G-A`, `gate-gtm`, `secret_sink`, `approvals_verify`,
  … — there is no `hook` member); a non-member raises (the hook logs `gate-fault` and skips the notice,
  never blocks). Every call site passes its own enum name.
- Keyword set: state it as exactly `notices.write_notice`'s minus behaviour-only `task` (hooks never
  write operator tasks) — i.e. add `hold_until=None`; keep `card_id` only if 07 §7.1's `write_notice`
  gains it (it does not today; `card_id` is set only by `notices.py card-mark`), otherwise remove it from
  `write_notice_file`, so the "mirrors" comment is true.
- B1 parity test (`test_gtm_notice_parity.py`): add `write_notice_file(..., created_by="hook")` raises,
  and the two keyword sets compare equal after removing `task`.

## R49 — `02_act.md` §2.4 `purge-untrusted` (amends R41: `--age-only`, `--if-lease-free`, run logs)

- **`--age-only`** (valid with `--all --hipaa-only` and with `--company`): deletes exactly `ST/untrusted/**`
  files older than 30 days, `G/drafts/**` files older than 24 h on hipaa packs (00_global_paths.md §1.3),
  and transcript files older than 30 days — and **never** touches `H/.playwright-mcp/`. The holds job
  (07 §7.2) uses only this form, because it holds no company lease and the full purge's "delete
  `H/.playwright-mcp/` entirely" would delete a live session's Playwright output (acting-as screenshots
  `complete` relies on, in-flight snapshots, the 06 §6.6 setup-capture file). A1/D tests: a fresh
  `.playwright-mcp/page-x.yml` survives `--all --hipaa-only --age-only`; a 31-day-old untrusted file and
  a 25-h hipaa draft are deleted, a 23-h draft kept.
- **`--if-lease-free`** (valid with `--playwright-only`): take `R/.gtm_state/leases/<slug>.lock` with
  `fcntl.flock(LOCK_EX | LOCK_NB)` (the lock `/usr/bin/lockf` holds), hold it for the purge, release after;
  lock held → delete nothing, print `result.skipped: "lease_held"`, exit 0. Used by the runner's
  post-session backstop (07 §7.2). A1/D tests: lease held by another process → file kept, `skipped`;
  free → deleted.
- **Run logs:** `ST/untrusted/run_logs/<run_id>.log` (written by 07 §7.2's `run_log_sink.py` for hipaa
  packs) is ordinary `ST/untrusted/**` content for the 30-day age rule; state in 00_global_paths.md §1.3
  that `backup_state.py` excludes `ST/untrusted/**` (including `run_logs/`) — if it does not today, add the
  exclusion with a test.
- The holds job **honours `DISABLED`** (07 §7.2, DECIDED): delete the R41 sentence that places the purge
  before the `DISABLED` check; `purge-untrusted` stays *allowed* under `DISABLED` (03_schemas.md §3.10)
  for interactive or operator use.

## R50 — `02_act.md` §2.4 new read command `pending-commits`; `00_global_paths.md` §1.3 `pending_commit.txt`

- `act.py pending-commits --company <slug> [--older-than-days N]` (read policy; works under every pause
  and `PAUSE.chain`): reads `ST/pending_commit.txt` under `ST/pending_commit.lock`; groups lines by path;
  keeps a path only when `git -C <home> diff --quiet HEAD -- <path>` exits nonzero or the path is
  untracked (`git ls-files --error-unmatch` fails) and exists; prints `result.pending: [{"path",
  "first_ts", "writers"}]` and `result.stale` (the subset whose earliest line is older than N days, N
  default 14). Paths that fail `^[A-Za-z0-9._/-]{1,200}$` or resolve outside the home are omitted and
  counted in `result.skipped`. It never rewrites the file.
- 00 §1.3: add "read by `act.py pending-commits`, which drops committed paths; the file itself is never
  pruned (append-only audit), so staleness is judged only through that command".
- A1 tests: a path listed 20 days ago and since committed → absent from `pending`; uncommitted → in
  `stale`; a `../` path → skipped.

## R51 — `company.py resolve` (amends R22; `00_global_paths.md` §0.1)

`company.py resolve <slug>` distinguishes a TCC/permission fault from an unknown company: a
`PermissionError` (or `EPERM`/`EACCES` `OSError`) while reading the registry entry's pack → exit 1 with
`{"ok": false, "error": {"code": "home_unreadable", …}}`; a slug with no pack → exit 13 `unknown_company`.
07 §7.2 maps exit 1 `home_unreadable` → heartbeat `failed`/`tcc`, and 07 §7.6 step 1 → `gtm_session.sh`
exit 1. Test: with the pack made unreadable (`chmod 000`) → exit 1 `home_unreadable`, not 13.

## R52 — `02_act.md` §2.4/§2.5/§2.11, `03_schemas.md` §3.7, `05_approver.md`, `08_seats_wps.md` Appendix B (card-decided `$` denials; signed stops under a manual PAUSE)

Two recorded deviations for ratification (Appendix B):
1. **Plan §20.8** ("`record-external` kind (b) never applies to `$`"): E1b records a mirror-card "No" on a
   `$` request as a denial (prevent-only). Hardening: `record-external --kind approval --card <request_id>`
   (a) records on the request `decided_via: "card"` and `card_written_by_agent: <bool from the card
   answer's provenance, 02_act.md §2.11>` and prints both as `result.decided_via` /
   `result.card_written_by_agent` (a signed decision records `decided_via: "signed"`); (b) on a card
   denial writes one in-process `info` notice (severity `warn`, `push=True`, `created_by: act`,
   `dedupe_key: card_deny:<request_id>`, `request_id` set; title/body fixed text naming only the ids);
   (c) for a request whose `money_brief.urgency` is `urgent`, a card "No" is **not** a denial: it records
   a re-show request (GTMApprover shows the request again), the request stays `awaiting_approval`, no
   `card_deny` notice, and `result.decision` is `reshow`; only a signed GTMApprover Deny denies it.
   A2 tests: non-urgent card "No" → `denied`, `decided_via: card`, one pushed `card_deny` notice; urgent
   card "No" → still `awaiting_approval`, `result.decision: "reshow"`, no notice.
2. **Plan §6.8** (manual PAUSE blocks T1+): a spend-**reducing** runaway stop (one of the five stopping
   rows, `after.new_absolute_value` `"0.00"`) with a valid **signed** approval executes under a manual
   `ST/PAUSE` (the same exception class as `revert` step 2). `PAUSE.chain`, `PAUSE.trust`, `PAUSE.budget`
   (for browser rows) and `DISABLED` still block it. Add `act.py queue --kind authorized --stops-only`
   (only such authorized, signed stops). A2 tests: under `ST/PAUSE`, `execute` of a signed stop succeeds
   and `execute` of any other authorized action exits 5; `--stops-only` lists only the stop.
- 03 §3.7: add `decided_via` (`signed`|`card`|null) and `card_written_by_agent` (bool|null) to the request
  record; 05_approver.md shows a re-show-requested urgent request at the top of its list.

## R53 — `04_hooks.md` G-B (output redirection in GTM scope)

In GTM scope (every Bash command is already forwarded to G-B, plan §20.13), deny any command carrying an
output redirection — `>`, `>>`, `&>`, `&>>`, `>|`, or `N>`/`N>>` with a file target — whose target, after
`realpath` of its parent, is not `/dev/null` and not equal to or under `<home>/.claude/gtm/drafts/`. Parse
with the same tokenizer G-B already uses; an unparseable command in GTM scope is denied (fail closed), as
for G-B's existing rules. Reason: the `Bash(python3 …/tools/gtm/<tool>:*)` allowlist is a prefix match,
and whether Claude Code's `:*` matcher refuses a trailing redirection is unverified (07 §7.6 step 5,
probe f); a CSA session's cwd is the whole application repo. B tests: `python3
/Users/x/.claude/tools/gtm/notices.py list --json > <home>/modules/billing/x.py` → denied,
no file; `… 2>/dev/null` → allowed; `… > <home>/.claude/gtm/drafts/out.json` → allowed; `… >> ../x` →
denied. 07 §7.6 gates K's scheduled prompts on this rule.

## R54 — `03_schemas.md` §3.12 `cycle.py sync --if-running` (amends R35)

`cycle.py sync --cycle <id> --if-running`: when the record's status is not `running` (closed `failed` by
`gtm_session.sh` after a 142 timeout, `missed` after a 75, or any closed state), exit 0 with `{"ok": true,
"synced": false, "status": <current>}` and change nothing — mirroring `close --if-running`; without the
flag the existing "closed cycle → exit 3 `closed_cycle`" refusal is unchanged. G tests: `sync
--if-running` on a `failed` record → exit 0, record byte-identical; on a `running` record → synced.

## R55 — `00_global_paths.md` / `08_seats_wps.md` Appendix C, `company.py validate` (amends R29)

`cadence.inbox_checks`: at most **2** entries (was 6), because plan §6.8 reserves at most 2 lead-capture
dispatches per day under budget state (07 §7.3). `company.py validate` refuses a third entry naming the
key. Test: a three-slot pack → validation error.

## R56 — `02_act.md` §2.3/§2.4 (amends R42): hourly pacing from the holds job, `runaway-stops`

- New subcommand `act.py pacing --all` (allowed only under the `GTM_HOLDS_JOB=1` not-GTM-session
  exception, like `run-holds --all`): for each `gtm_slugs()` company with a paid system in scope and no
  `ST/collectors/pacing/<UTC YYYYMMDDTHH>.json` yet, run the `ad_spend_pacing` collector exactly as
  `read-run` does (same registry, host checks incl. 07 §7.4's positive literal-host rule, `--run pacing`
  literal, `--out ST/collectors/pacing/<UTC YYYYMMDDTHH>.json`), and pass its findings through the same
  in-process runaway branch (notice dedupe `runaway_spend:collector:ad_spend_pacing:<finding id>`, stop
  file `G/drafts/stop_<finding id>.json`). Per-company collector timeout = the registry `timeout_s` (120).
  Allowed under a manual `ST/PAUSE` (T0 reads); not run under `DISABLED` (the holds job does nothing).
- `ST/runaway_stops.jsonl` (+ `.lock`): `read-run` and `pacing` append `{"ts", "finding_id",
  "stop_file", "action_id": null}` for each stop; `propose --file <stop_file>` stamps `action_id`; a
  `propose --file` of a stop whose entry already has an `action_id` → exit 3 `stop_already_proposed`,
  nothing proposed. `read-run`'s `result.runaway_spend` lists only unproposed stops.
- New read command `act.py runaway-stops --company <slug>` → `result.runaway_spend: [{"finding_id",
  "stop_file"}]` for entries with `action_id: null` whose stop file exists.
- 07 §7.4's thresholds (Google 2× average daily budget or MTD > 30.4×; Meta 1.75× daily, lifetime >
  lifetime budget) and account-local "today" are WP-F's (08 §9 F row), with the KB citations.
- A1/F/D tests: 07 §7.4's seven-day detection tests.

## R57 — `02_act.md` §2.4 `status` (amends R26) and `03_schemas.md` §3.19 `validate_run.py`

- `status --state completed --unverified --completed-before-hours <N>`: `completed_at <= now − N h`
  computed by act.py; replaces the `--completed-before <ISO>` form R26 asked for (no model date
  arithmetic in prompts). A1 test: a completion 17 h old is excluded, 19 h old included.
- `validate_run.py --company <slug> --since-last-daily` (G): lists `ST/cycles/cyc_<slug>_*.json`, takes
  `P` = the latest company-local date (pack `timezone`) of a `daily` record before today (none →
  yesterday; floor 14 days back), validates every cycle whose id date is in `[P, yesterday]`, prints
  `{"ok", "window": [first, last], "runs": [{"run_id", "ok", "errors"}]}`; exit 0 when every run
  validates, 1 when any fails (listed), 2 usage. G tests: 07 §7.5 D9's Monday and 20-day-gap fixtures.

## R58 — `activity_log.py audit --ids-only` (`08_seats_wps.md` §9, owning WP of `activity_log.py`)

Add `--ids-only`: print, instead of offserver URLs and `sample_detail()` text, one line per finding
cluster `audit found <cluster_id> <kind> <count>` (the existing `audit found ` prefix and exit-1 rule
kept, so 07 §7.5 W2's exit handling is unchanged). The weekly prompt uses it for packs with `regulated ∋
hipaa`. Test: a fixture whose records carry a URL and detail marker → neither marker in `--ids-only`
output; exit code identical to the plain form.

## R59 — `00_global_paths.md` §1.3, `08_seats_wps.md` §9 D row: `weekly_report.py` and `ST/reports/`

- 00 §1.3: add `ST/reports/` — `weekly_<YYYY_MM_DD>.md` written by `weekly_report.py`; **ignored**
  class (plan §3.2; never committed; included in the weekly backup; on hipaa packs it holds ids and
  counts only by construction, 07 §7.5 W10).
- 08 §9 D row: `tools/gtm/weekly_report.py` (07 §7.5 W10: sections, field allowlist, `weekly_report:`
  notice) and its D tests; `tools/gtm/run_log_sink.py` (07 §7.2 session output routing).
- Plan §0 P7 ("weekly report + perf report rendered for 2 consecutive weeks") is satisfied by W10 + W7.

## R60 — `backup_state.py` (amends R43): `--restore --latest --company <slug>`

`--latest` (with `--restore` and `--company`, instead of an archive path): picks the newest archive under
`/Users/x/Backups/gtm/<slug>/*.tgz` by the timestamp in its name (mtime as tie-break), prints
it as `result.archive`; none → exit 3 `no_archive`. The restore prints R43's JSON `result.counts`
(including the restored `actions.jsonl` line count and `chain_ok`). 07 §7.5 M1 ships only after this and
R43's JSON output land. Test: two fixture archives → the newer one is restored; empty dir → exit 3
`no_archive`.

## R61 — `08_seats_wps.md` §9 WP table, ordering and Appendix B (r4 additions from 07's review round)

- **Ordering:** the scheduled prompt files ship only after R17, R19, R20, R36, R50, R52, R53, R56, R57 and
  R59 have landed with their tests (07 §7.6 step 5 is the one list); M1 additionally waits for R43 + R60.
  **Superseded (wave1c):** this list is replaced by R62's and R64's; **R52 is not a prompt
  prerequisite** (07 §7.6 step 5), and M1 is no longer optional — `gtm_monthly.txt` itself waits for
  R43 + R60 (R64).
- **D row:** `NOTICE_KIND_LABEL`; `list` company binding + title/body redaction + `label` key; the exit-3
  code list and JSON error shape; `runtime_has_no_home`; the `chain`/`signin_step:approver` notice
  templates; `card_deny:`/`tz_drift:`/`weekly_report:` reserved prefixes; the holds job's order,
  `DISABLED` honouring, `--age-only` purge, deadline watchdog and `pacing` step; `runner_probe.py`'s
  `hipaa`, `tz_drift`/`render_tz`/`machine_tz` keys and exits 4/5; the runner's hipaa output routing,
  `sync --if-running`, lease-probing backstop, `tz_drift` notice; `heartbeat_audit.py`'s
  `consecutive_duplicate_skips` streak; `weekly_report.py`, `run_log_sink.py`.
- **K row:** `render_plists.py`'s `machine_tz()` + `--machine-tz` (test-only), `GTM_RENDER_TZ`, pinned log
  paths, `--install-rows` column format, removed-label printing, stale-extra `--check`, inbox cap 2;
  `gtm_session.sh`'s permission-mode allowlist, enumerated playwright tools, `weekly_report.py` grant,
  run_id-before-holder-info, `home_unreadable` → exit 1, the shared caps command form; prompts: the
  final-message rule, E1b urgent/`decided_via` line, E2b in paused runs + `runaway-stops`, S1, E4
  reason-branched refusal bodies, D6 `--completed-before-hours`, D9 `--since-last-daily`, W2 `--ids-only`
  on hipaa, W9 `pending-commits`, W10, M1 `--latest`, the four paused lists.
- **F row:** `PACING_DOCTRINE` (cited, account-local day), positive literal-host allowlist, `by_who`
  fixed keys.
- **Appendix B:** add R52's two deviations (plan §20.8 card-decided `$` denials with the urgent-stop
  carve-out; plan §6.8 signed-stop execution under a manual PAUSE). Note that 07 §7.2 now **honours**
  `DISABLED` for the holds job (no deviation from plan §6.8/runtime §13; stated retention lag while
  `DISABLED` is set).

## R62 — r5 bundle from 07's fifth review round (02, 03, 04, 05, 06, 00, 08, `backup_state.py`, tool owners; amends R36, R42, R52, R56, R57, R61)

Each item names its target. 07 already relies on every one; until it lands the files disagree, and
07 §7.6 step 5's prerequisite lists hold the dependent WPs back.

**02_act.md**
- **`act.py pacing --all` (amends R56; the blocker):** it runs `collectors/ad_spend_pacing.evaluate(read_fn,
  pack, now)` **in-process**, with `read_fn` built on `connector_dispatch._build_ctx` under the
  `prove_holds_job` admission it already passed (the `run-holds --all` path) — never `build_read_ctx`
  and never a collector subprocess. Same registry/scope/host checks as `read-run` before reading; per
  company a wall-clock budget of the entry's `timeout_s` checked before each connector read; output
  `ST/collectors/pacing/<UTC YYYYMMDDTHH>.json`; deletes pacing outputs older than 30 days; prints
  `{"ok", "result": {"companies": [{"slug", "status": "read"|"skipped_hour"|"no_paid_system"|"failed",
  "code", "findings"}]}}`; exit 0 when no company `failed`, else 1. A1/L test: a holds-context run with
  no `CLAUDE_GTM_COMPANY` reads and finds (RED when routed through `build_read_ctx`).
- **Stored stops (amends R42/R56):** `read-run` and `pacing` store each finding's `stop` as
  `ST/stops/<finding id>.json` (atomic, 0600) and append `{"ts", "finding_id", "stop_sha256"|null,
  "action_id": null}` to `ST/runaway_stops.jsonl`; `result.runaway_spend` / `runaway-stops` entries are
  `{"finding_id", "has_stop", "stop_note"}`. New `propose --company <slug> --stop <finding_id>`: reads the
  stored stop, exit 3 `stop_file_modified` on a sha mismatch, exit 3 `stop_already_proposed` when the
  ledger entry has an `action_id`, else proposes it (urgent-stop exception, `drafted_by.agent_id:
  "collector:<name>"`) and stamps `action_id`. `propose --file` of a runaway stopping row → exit 3
  `stop_requires_store` when `CLAUDE_GTM_RUN` parses to a scheduled kind. A1 tests for each code.
- **Stopping rows (§2.4 `--file`/stop set):** add `meta.campaign_pause` (CBO campaigns; and
  `meta.campaign_budget_edit` when lowering) to {`google_ads.campaign_budget_edit`,
  `google_ads.campaign_pause`, `meta.adset_budget_edit`, `meta.adset_pause`, `meta.spending_limit_edit`};
  for `meta.spending_limit_edit` an unset current cap (`before.value.current_absolute_value: null`)
  counts as above any new value, so capping at current spend is "lower".
- **`card_on_refuse` (amends R36):** set **only** for a `meta.business_portfolio_*` row refused on a
  non-hipaa pack for a reason other than `cross_company`, `unlisted_target`, `phi_target`; those three
  reasons (and every hipaa-pack refusal) write no `card` notice — their pushed `isolation_hit` notice
  carries `reason_code: <reason>` (07 §7.1 notice field; the page renders a fixed text per code).
- **R52 (amends):** until 08 Appendix B records ratification, `record-external --kind approval --card
  <request_id>` on a `$` request is not called by any scheduled prompt (07 ships plan-conformant). When
  ratified, a card "No" is a re-show request (never a denial) for **every spend-reducing** `$` request
  (new value below current, or pause/stop/remove), not only `urgency: urgent`; `card_deny` applies only
  to spend-increasing requests. `queue --kind authorized --stops-only` excludes a stop whose own system
  has a breaker `PAUSE.<system>`; under `PAUSE.budget` browser stops are excluded (unchanged).
- **`status` rows (amends R57):** every row carries `route` ∈ {`api`, `browser`} (browser = `verify
  --auto` would refuse `verify_auto_unsupported`).
- **`queue --kind approval --owner-executable`** (07 §7.5 D6b; `requests/05_approver.md` R48/R55): returns
  rows only while HEAD's `tools/gtm/approver_probe_p.json` (`git show HEAD:…` in the runtime repo, never
  the working tree) says `"probe_p": "fail"` and HEAD has no `tools/gtm/approver_pubkey.pem`; else
  `result.rows: []` with `result.probe_p`. A1 test: working-tree `fail` with HEAD `pass` → no rows.
- **`cancel_too_late` resolver:** `complete` of an action with an open `cancel_late:<action_id>` notice
  resolves it in-process (`resolved_by: act`) when it records the outcome (03 §3.11's writer is act.py).
- Notice kinds: `cancel_too_late` and `spool_dropped` stay their own kinds (07 §7.1 now lists both in
  `NOTICE_KINDS`, 17 kinds).

**03_schemas.md §3.12 `cycle.py`**
- `open` of an existing id → exit 3 with `error.code` **`duplicate_cycle`** (add to the exit-3 list), so
  callers can tell it from a mismatch, `bad_cycle_id_hhmm` or `test_mode_real_state`.
- Session binding: when `CLAUDE_GTM_COMPANY` is set, any `--cycle` whose slug differs → exit 3
  `company_mismatch`; when `CLAUDE_GTM_SESSION` is set, `open`, `missed`, `sync` and `close` → exit 3
  `cycle_lifecycle_in_session` (only `add-*` annotation remains for a session). `gtm_session.sh` and
  `run_gtm_job.sh` call the lifecycle subcommands through `env -u CLAUDE_GTM_SESSION -u
  CLAUDE_GTM_COMPANY -u CLAUDE_GTM_RUN` (07 §7.6 step 4(a)). G tests for both codes.

**04_hooks.md**
- Confirm (text, B test) that G-W's GTM-scope write denial covers `<home>/.claude/gtm/state/stops/**`
  and G-B's `redirect_targets` rule covers a redirection into it.
- `heartbeat_audit.py` (owned by WP-D, 07 §7.2): flag `consecutive_pacing_failures ≥ 4`; its
  `timestamp-divergence` check is satisfied by 07's `RUNNER:` stdout line and no-stderr-after-START rule.

**05_approver.md**
- `approval_sig.write_urgent_notice`: its literal `NOTICE_KINDS` copy equals 07's 17-kind tuple (D test
  compares them); the `lead_capture_stopped:<slug>:<UTC date>` task notice is written with `created_by:
  approvals_verify` (a fixed, slug-only template, so `GTM_Operator.html` renders its title). 07 applies
  `requests/05_approver.md` R48/R55 (D6b), R54(c) (I1b `notices.py task --template lead_capture_window`)
  and (d) (named stdlib writer), and R65 (Revoked approvals block and W10 section 9).

**06_connectors.md §6.3**
- Name `act.py pacing` (holds job, `prove_holds_job`) beside `run-holds` among the admitted in-process
  callers that use `_build_ctx`; `build_read_ctx`'s "no exception for any other caller" is unchanged.

**00_global_paths.md**
- `R/.gtm_state/session_tokens/<session uuid>.token` (0700 dir; one line, the `gtm_session.sh` exit-64
  token; written only by `gtm_session.sh`, read and deleted by `run_gtm_job.sh`); `ST/stops/<finding
  id>.json`; the notice timestamp form `YYYY-MM-DDTHH:MM:SSZ`.

**`backup_state.py`** (amends R43/R60)
- In session env (`CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` set): `--restore` refuses (exit 3
  `restore_target_denied`, nothing written) unless both `--to` and `--runtime-state-to` resolve (after
  `realpath`) inside `<home>/.claude/gtm/drafts/restore_check/`; `--company` must equal
  `CLAUDE_GTM_COMPANY`. Test: `--runtime-state-to /Users/x/.claude/.gtm_state` from session
  env → exit 3 and the live state unchanged.

**Owners of `metrics.py`, `experiments.py`, `mission_record.py`**
- State each tool's subcommands and which of them write; confirm none has an admin, registry or
  cross-company subcommand reachable in session env (07 §7.6 step 5 grants them whole-tool only until
  this is stated).

**08_seats_wps.md** (amends R61)
- **Ordering:** replace R61's prompt-prerequisite list with 07 §7.6 step 5's two lists — prompts: R17,
  R19, R20, R21, R25, R36, R42, R50, R53, R57, R58, R59, R62 and `notices.py task` (**R52 removed**:
  the prompts ship plan-conformant); holds job and backstop: R35/R54, R41, R49, R56, R62,
  `notices.py prune`.
- **D row:** `notices.py task` (four templates, `created_by: session`), `prune`, push retry cap,
  `origin_company`/`reason_code`, `REFUSAL_REASON_TEXT`, `PAGE_TEXT_WRITERS`, `NOTICE_KINDS` (17),
  `write_in_session`/`runtime_in_session`/`resolve_not_session_owned`, the exit-code table, the Revoked
  approvals block; runner: token file, `RUNNER:` line, exact heartbeat objects, `duplicate_cycle`
  branch, `purge_failed:`/`pacing_down:` notices, `consecutive_pacing_failures`, holds `prune` step;
  `runner_probe.py --kind interactive --offset-minutes`, `--session-tool-calls`, exit mapping, hourly
  tz sampling; `heartbeat_audit.py` pacing streak.
- **K row:** subcommand-prefix allowlist (no `company.py`, `secret_sink.py`, whole-tool `act.py` etc.),
  no `PushNotification` for hipaa, `hipaa=` in RUN CONTEXT, `--print` path check, leases `mkdir`,
  step 4(a) probe retries, env-canary tool-call rule, stdout-only after `claude`, playwright pin
  `0.0.76`; prompts: I1b, I2a, I3b, D6b, E3 in paused lists, paused daily D2/D6/D6b/D7, E7 `--since
  <start>`, E4 Meta-only card, E2b `--stop`, [R52] lines withheld, `notices.py task` in I6/W9/M1, W2
  `harvest exit <n>`, W10 section 9.
- **F row:** full registry schema and three entries, finding-id regex, per-level stop table, Meta CBO
  and account stops, browser-only skip note.
- **Appendix B:** remove the E4 cross_company/unlisted_target/phi informational-card deviation (07 now
  posts no card for them, plan §20.11 conformant) and D6's "accepted limitation" (07 now verifies under
  budget state through I2a/I3b, plan §6.8 conformant); R52's two deviations stay pending, now with the
  stated plan-conformant default shipped until ratification and the widened re-show rule.

## R63 — r6 bundle from 07's sixth review round (02, 04, 00, 05, 08, `company.py`, `harvest_tool_trail.py`, WP-K; amends R16, R45, R52, R61/R62's prerequisite lists)

**02_act.md**
- **§2.1 "Interpreter" item (3)** — replace "`run_gtm_job.sh` puts `__PY_DIR__`, a ≥ 3.11 interpreter's
  directory resolved at install, first in `PATH`" with: every scheduled invocation names
  `gtm_env.TRUSTED_PYTHON` (`/opt/homebrew/opt/python@3.13/bin/python3.13`) by full path — the runner,
  `gtm_session.sh`, the prompt files and the `--allowedTools`/settings rules (07 §7.2 "Interpreter
  pin", applying `requests/05_approver.md` R59); the plist `PATH` is a non-Python fallback only. Land it
  in the same change as 07's r6 so 02, 05 and 07 agree.
- **§2.11 `record-external --kind approval` (amends R52):** until 08 Appendix B records R52's
  ratification, refuse exit 3 `money_card_path_struck` (nothing recorded, no notice) whenever `--card`
  names the request id of an undecided (`awaiting_approval`) `$` request, whatever the card's answer.
  (R66(b)'s branch for a request that already has an approval record is unaffected: no state change,
  `card_deny_after_approval` notice.) After ratification, R52's card-deny branch applies **only to a
  request with no approval record** (R66). A2 test, run directly (not through a prompt): a pending `$`
  request whose mirror card is archived "No" (and, separately, "Yes") → exit 3 `money_card_path_struck`,
  request still `awaiting_approval`.
- **§2.4 `status --review-brief --lane-variant` (07 §7.5 I8 route (a)):** for an action of a pack with
  `regulated ∋ hipaa`, write `ST/review_briefs/<action_id>.lane.json` = the full brief with every quoted
  inbound text (the review/DM/Q&A body a reply answers, and every other `after` field 02 marks inbound)
  replaced by `{"sha256": <hex of the UTF-8 text>, "len": <chars>}`, the draft reply kept; record its
  `brief_sha256` in `ST/review_briefs.jsonl` with `"variant": "lane"`; print `result.brief_path`. `act.py
  review` accepts a lane seat's verdict only when the reviewer's transcript Read the lane brief whose
  recorded hash matches (the `review_brief_unbound` rule, §8.4), and for a hipaa pack refuses a lane
  seat's verdict bound to the full brief. A1 test: a marker in the fixture review body is absent from
  the lane brief and present in the full one.
- **§2.3 / R45 (amends R45):** the marker is the **signed** form of 00 §1.4 (`gtm.operator_ok.v1`), not
  R45's original unsigned wording: add `notice_resolve` to `OPERATOR_OK_COMMANDS` and to the signed
  payload's `command` set, `target` = the notice id (grammar 00 §0.3), `company` = the notice's own
  `company` field **including `runtime`**; validated and consumed by `session.consume_operator_ok(ctx,
  "notice_resolve", <notice_id>)` (checks (1)–(5), 15-minute expiry, nonce, delete under
  `S/operator_ok.lock`); state how a `runtime`-company ctx is built for it. `notices.py resolve
  --operator` (07 §7.1) ships only after this lands.

**04_hooks.md**
- **§4.2 G-B, new rule `gtm-scheduled-bash-unlisted`** (07 §7.6 step 5 (2)): in GTM scope with
  `CLAUDE_GTM_RUN` of a scheduled kind, read `R/.gtm_state/scheduled_settings.<CLAUDE_GTM_SESSION>.json`;
  deny every Bash command that is not one simple command (no `;`, `&`, `|`, newline, backtick, `$(`,
  `<(`, `>(`) whose text, leading whitespace stripped, equals an exact `Bash(<cmd>)` rule's command or
  starts with a `Bash(<prefix>:*)` rule's prefix followed by end of text or a space; file missing or
  unparseable → deny every Bash command (scheduled scope only). Confirm G-W denies GTM-scope writes
  to that file. B tests with the operator's real settings files in place: `PY …/company.py unregister
  x`, `gh issue list`, `rm -rf <home>/x` → denied; a listed `notices.py list` prefix → allowed.
- **§4.6 gate-gtm, new rule `gtm-hipaa-brief-egress`** (07 §7.5 I8): for a pack with `regulated ∋
  hipaa`, deny an `Agent`/`Task` dispatch whose prompt names a full review-brief path
  (`review_briefs/<action_id>.json`, not `.lane.json`) when the target seat's agent-file `tools:`
  include `WebFetch`, `WebSearch` or `Bash`. B test: `content-strategist` denied, `gtm-checker` allowed.
- **GitHub in GTM scope** (07 §7.5 "Operator tasks"): state whether GTM scope (interactive included)
  denies `gh` writes (issue/PR creation, comments) against the example-org organization, which
  also holds the OtherApp repo (plan §20.9a); if not, add that denial or record why it is not needed.
- `write_notice_file` (amends R44/R48): apply 07 §7.1's `origin_company`/`reason_code` rules
  (`origin_company` forced to `company` for a non-runtime company, a `gtm_slugs()` member or null for
  `runtime`; `reason_code` only with `kind: isolation_hit`, stored null when it fails the grammar).

**05_approver.md**
- `approval_sig.write_trust_notice` / `write_urgent_notice`: the same two field rules as above (they
  write `reason_code: null` always).

**00_global_paths.md §0.1 / `company.py`**
- `register`, `unregister` and `index` refuse exit 3 `registry_in_session` (nothing written) whenever
  `CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` is present in the environment (07 §7.6 step 5 (3)). Test:
  in session env `company.py unregister othercompany` → exit 3 and `gtm_slugs()` unchanged.
- §1.2 layout: `R/.gtm_state/scheduled_settings.<session uuid>.json` (0600; written by
  `scheduled_settings.py` for one scheduled session, deleted when it exits; read by G-B).

**`harvest_tool_trail.py` owner (amends R16; 07 §7.5 W2)**
- For every record attributed to a pack with `regulated ∋ hipaa`, store `{"sha256": <hex>, "len": <n>}`
  in place of `detail.text`, `detail.value`, `detail.element`, `result_excerpt` and `prompt_excerpt`;
  if the full record is kept, write it only to that home's `ST/untrusted/trail/` (0600; 30-day age
  purge; excluded from backups). Test: a OtherCompany fixture transcript whose `browser_type` text, tool
  result and dispatch prompt hold a marker yields a `TOOL_TRAIL.jsonl` line without it.

**WP-K (new file)**
- `tools/gtm/scheduled_settings.py` (07 §7.6 step 5 (1)): writes the per-session settings file from
  HEAD's `settings.json` `hooks` and `env` blocks verbatim plus `permissions` = the rendered rules and
  mode; exit 1 on a git failure or a HEAD with no `hooks` object.

**Probe f (plan §17)** — additionally record: (a) the effective permission set of a `-p` session
started with the operator's real user/project/local settings and only `--allowedTools`; (b) the same
with 07 §7.6 step 5's exact argv; (c) the `--setting-sources` form that loads no source; (d) whether
subagents inherit the parent's `--allowedTools`; (e) `~/Desktop` read access under launchd for
`TRUSTED_PYTHON`'s realpath.

**08_seats_wps.md** (amends R61/R62's lists)
- **Prompt prerequisites** gain: `scheduled_settings.py` and probe f (a)–(c) recorded; G-B
  `gtm-scheduled-bash-unlisted`; `company.py` `registry_in_session`; the harvest hipaa hashing; act.py
  `money_card_path_struck`. **Hipaa packs additionally:** probe f (d), probe o's osascript-from-launchd
  PASS, and — for lane dispatches — the lane-brief variant, its review binding and gate-gtm
  `gtm-hipaa-brief-egress` (else the prompts ship in 07 §7.5 I8's route-(b) form).
- **Holds job** gains: probe o's osascript-from-launchd PASS while any hipaa pack is registered.
- **D row** gains: `resolve --operator` gated on R45 (as amended here); `list --company runtime`
  session-env filter; `bad_resolution`; `label`/`reason_text`; exact success objects (`push` from
  `push_pending() -> (pushed, failed)`); `write_notice(origin_company=, reason_code=)`; the
  `card_deny_after_approval:` reserved prefix and resolver row; the signed-approvals page block;
  `runner_probe.py --render-tz` optional and `--session-tool-calls` argv/exit set; the runner's
  render-tz and session-script checks; `speed_to_lead` `received_at` normalization and
  `skipped_received_at` (F row); `ad_spend_pacing` account isolation (F row).
- **K row** gains: `PY` literal everywhere (no `__PY_DIR__`, fixed plist `PATH`), `render_plists.py`
  interpreter refusal, `scheduled_settings.py`, the `row needs flip` page line (flip done by a non-GTM
  session).
- **Appendix B — new recorded deviations for ratification, with R4, R39 and R52:**
  1. 07 §7.2 — **hipaa retention lag under `DISABLED`**: while `DISABLED` is set or the holds job is
     unloaded, OtherCompany's 30-day (transcripts, `ST/untrusted/**`) and 24-hour (`drafts/`) deletions do
     not run from any schedule; they resume on the first holds run after, and interactive sessions
     still purge at exit. Deviation from plan §20.13's 30-day deletion; chosen so `DISABLED` freezes
     evidence during an incident (runtime §13 "stops everything").
  2. 07 §7.1 / §7.5 E7 — **no `PushNotification` for hipaa packs**: plan §20.8 says urgent
     runaway-spend cards "notify through every channel"; hipaa packs get the osascript fixed pair and
     the page only. Compensating precondition: a recorded probe o PASS for osascript from a
     launchd-spawned process before any hipaa pack's schedules, or the holds job while a hipaa pack is
     registered, are loaded.
  3. 07 §7.5 I8/W6 — **plan §20.13 amendment, hipaa reply lanes**: plan §20.13 keeps OtherCompany
     DM/review bodies in the analyst/drafter/checker dispatches only, while plan §20.5 makes
     local-presence-architect (Bash/WebFetch/WebSearch) the hipaa content reviewer. Resolution: lane
     seats receive lane briefs (draft reply + digest pointer in place of the quoted review; route (a));
     until that lands, hipaa reply lane reviews run only in interactive sessions (route (b)).

## R64 — wave1c bundle from 07's r7 review (02, 03, 04, 05, 06, 08, `company.py`, `harvest_tool_trail.py`, `heartbeat_audit.py`, WP-K; amends R16, R43, R51, R56, R61, R62, R63)

Each item names its target; 07 already relies on it, and 07 §7.6 step 5's lists hold the dependent WPs
back until it lands.

**08_seats_wps.md §9 ordering (amends R61/R62/R63's lists)**
- **Prompt prerequisites** gain: R26 as amended by R57 (`status --unverified`); R43 (queue row keys,
  `status --review-brief` path-only stdout, `card_unanswered` for a never-posted card, `touchid:` dedupe);
  the harvest session-env output narrowing (below); the `ticket --read --inbox`/`--plus-verify-rows`/
  `--all-in-scope` forms and `system_names.inbox_systems`/`read_systems` (below).
- **Per file:** `gtm_inbox.txt` also requires R43's `lead-append --from-agent --index` with its A1 tests;
  `gtm_monthly.txt` also requires R43's `backup_state.py --restore` JSON `result.counts` and R60's
  `--latest`, and ships only with M1 in it — until both land, `gtm_monthly.txt` is not installed and
  no `monthly` plist is loaded (07 §7.5 M1, §7.6 step 5).
- **Holds job** gains: R56 as amended below (in-process propose/authorize of stored stops).
- R61's inclusion of R52 is superseded (R61 now carries that note); R52 stays off every prerequisite list.

**02_act.md §2.4**
- **`act.py pacing --all` (amends R56/R62):** after storing each stop, in-process under the same
  `prove_holds_job` admission, run the `propose --stop <finding_id>` code (same checks and refusal codes,
  `drafted_by.agent_id: "collector:ad_spend_pacing"`) and then `authorize` on the new action, so it reaches
  `awaiting_approval` (the urgent request GTMApprover lists); stamp the `ST/runaway_stops.jsonl` entry
  with `action_id` and `proposed_by: "holds"`; any refusal (exit 10 `PAUSE.chain`, exit 5, any exit 3)
  leaves the entry unchanged beyond what `propose` already stamped. Each printed company entry gains
  `"requests": n`. A1/D test: a Saturday holds fixture finding yields an `awaiting_approval` request
  before any session runs (RED when the in-process propose/authorize is removed).
- **`runaway-stops`** additionally prints `result.holds_proposed: [{"finding_id", "action_id"}]` = ledger
  entries with `proposed_by: "holds"` whose action is `reviewed` or `awaiting_approval` and whose mirror
  card (card id = the request id) has no `ST/cards_posted.jsonl` row. A1 test: listed once until
  `card-post` of the mirror card, then absent.
- **`ticket --read`**: add `--inbox` (systems = `system_names.inbox_systems(pack)`), `--plus-verify-rows
  <N>` (only with `--inbox`; adds the systems of the rows `status --state completed --unverified
  --completed-before-hours N` returns with `route: browser`) and `--all-in-scope` (systems =
  `system_names.read_systems(pack)`); exactly one of `--systems`, `--inbox`, `--all-in-scope`; prints the
  final set as `result.systems`; an empty set → exit 3 `no_systems`, no ticket. A1 tests for each form.

**03_schemas.md §3.22 `system_names`**
- `inbox_systems(pack) -> list[str]`: sorted tier systems of `scope.channels_in_scope` that are `crm` or
  `call_tracking`, or whose connector manifest (06_connectors.md §6.3) lists a non-empty
  `inbox_class_ops`. `read_systems(pack) -> list[str]`: sorted tier systems of `scope.channels_in_scope`
  with a read connector. Used by act.py (`ticket --inbox`/`--all-in-scope`) and notices.py
  (`lead_capture_window` body, 07 §7.1). A1 test on a fixture pack with `gbp`, `crm`, `google_ads`
  (`gbp` manifest listing a review op) → `["crm", "gbp"]` and `["crm", "gbp", "google_ads"]`.
- **06_connectors.md §6.3:** name those two functions as readers of the manifest's `inbox_class_ops`/read
  ops (no behaviour change).

**`company.py resolve` (amends R51)**
- The failure JSON `{"ok": false, "error": {"code", …}}` (both `home_unreadable` exit 1 and
  `unknown_company` exit 13) goes to **stdout**, nothing else on stdout; human text to stderr only; on
  exit 0 stdout stays the bare home path. Test: the `chmod 000` fixture → stdout parses as JSON with
  `error.code == "home_unreadable"` (07 §7.2 "Error-code extraction").

**`harvest_tool_trail.py` owner (amends R16/R63)**
- In session env (`CLAUDE_GTM_SESSION` or `CLAUDE_GTM_COMPANY` set), `main` prints only `scanned <n>
  transcript file(s)`, `new records: <total>`, `this company: <n>` (for `CLAUDE_GTM_COMPANY`) and the
  slug-free unattributed line — never `by company:` or any other slug. Outside session env, unchanged.
  Test: a OtherCompanyB-env harvest over fixture transcripts with OtherCompany records prints no `othercompany`
  (RED with the `by company:` block restored).

**`heartbeat_audit.py` (WP-D) and 04_hooks.md (amends R62's 04 bullet)**
- R62's sentence "its `timestamp-divergence` check is satisfied by 07's `RUNNER:` stdout line and
  no-stderr-after-START rule" becomes: "… by 07's `RUNNER:` stdout line, its `RUNNER: START <label>`
  stderr line written at every spawn, and its helper-stderr redirection (07 §7.2 "Log files" (2), (4))".
- `_log_times`'s docstring claim that launchd's reopen refreshes `.err.log`'s mtime is wrong for an
  append-open with no write; correct it to say the start proxy depends on a write at spawn (the csa jobs'
  TCC `getcwd` error; GTM's fixed line). D test: 07 §7.2's 1-hour-old `.err.log` fixture.

**WP-K `scheduled_settings.py` (amends R63's WP-K item)**
- `permissions.deny` = HEAD's `permissions.deny` verbatim and in order, plus a `//` twin of every
  single-`/` `Read`/`Edit`/`Write` rule, plus the GTM additions of 07 §7.6 step 5 (1); never `[]`; HEAD
  with no `permissions.deny` array → exit 1. K test: superset of HEAD's list; a scheduled fixture
  session's Read of the gcloud ADC path is denied (RED with `deny: []`).
- **Note for the runtime settings owner (no 07 dependency):** HEAD `settings.json`'s own `Read(/Users/…)`
  deny rules use a single leading `/`, which Claude Code's permission syntax reads as relative to the
  settings file, not the filesystem root; probe f should record whether they deny the absolute paths
  today, and if not, `//` twins belong in `settings.json` too.

**notices.py (WP-D, 08 §9 D row)**
- Test seams `GTM_OPERATOR_PAGE` and `GTM_OSASCRIPT`, honoured only with `GTM_TEST=1` (CLI exit 2
  `usage` otherwise; in-process ignored); in test mode no real page render and no real push without
  them (07 §7.1 "Test seams"). D test: the real Desktop page's mtime is unchanged by the full D suite.

**08_seats_wps.md Appendix B — new recorded deviation for ratification**
- 07 §7.4 / §7.5 E2b — **runaway mirror-card lag**: the holds job makes a runaway stop signable in
  GTMApprover within the hour and pushes the urgent notice, but the E4 mirror card in the
  operator-input file is posted only by the next session run (weekend: up to the next weekly, monthly or
  Monday run). Deviation from plan §20.6's "urgent `$` card" timing; the signable request and push are
  not delayed.
