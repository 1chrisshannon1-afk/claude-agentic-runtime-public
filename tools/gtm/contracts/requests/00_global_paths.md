# Change requests from `00_global_paths.md` (§0–§1) to other contract files

Raised while resolving IMP-03, IMP-04, IMP-08, IMP-17 and IMP-21 in `00_global_paths.md`. Each
request names the target file, section and exact change. The `00_global_paths.md` text these
depend on is cited by its heading.

> **Superseded in part (round 2, below).** The operator marker is now 02_act.md §2.3's
> `S/operator_ok/<command>.<slug>.json` + `operator_ok.sh` design, not `S/operator_ack.json`, and the
> session-proof helper is `gtmlib.session.prove_gtm_session`. Where R1, R2, R3 or R5 name
> `operator_ack`, `consume_operator_ack`, `session_proven`, `"operator_terminal"` or the
> `CLAUDECODE`/TTY `pause` label, **R9–R11 win**. R4, R6, R7 and R8 stand unchanged.

## R1 — `02_act.md` §2.3 dispatch, GTM-session rule and exception (2) (IMP-03, blocker)

- Replace "every command whose `chain_policy` is `write`, `lead` or `repair`, plus `resume`, is
  refused with exit 13 `not_gtm_session` when `CLAUDE_GTM_COMPANY` is unset" with "… is refused
  with exit 13 `not_gtm_session` unless the GTM-session proof of 00_global_paths.md §1.4 holds
  (`CLAUDE_GTM_COMPANY` equals the company, the lease lock is held, the lease `session_id` equals
  `CLAUDE_GTM_SESSION`, and the lease `pid` is this process or an ancestor)".
- Replace exception (2) "`resume` and `autonomy` from an operator terminal = env `CLAUDECODE` unset
  **and** `sys.stdin.isatty()` (the same test is what "operator terminal" means everywhere in this
  document)" with "`resume` and `autonomy` from an operator terminal = the invocation consumes a
  valid single-use `S/operator_ack.json` (00_global_paths.md §1.4 "Operator authority is never
  read from the environment"; that definition is what "operator terminal" means everywhere)".
- Add the P2 falsification tests listed at the end of that §1.4 paragraph (the `env -u CLAUDECODE
  script -q /dev/null` spelling refused; wrong/stale marker refused and left; matching marker used
  once; inline-env `propose` from a non-descendant process exits 13).

## R2 — `02_act.md` §2.1 module layout (IMP-03)

Add one A1 module line, e.g. `tools/gtm/gtmlib/session.py  A1  GTM-session proof (lease lock + session id + pid ancestry) and operator_ack consume`, with signatures in §2.2b:
`def session_proven(slug: str) -> bool` and
`def consume_operator_ack(ctx: Ctx, command: str, target: str) -> dict | None` (deletes the marker
under `S/operator_ack.lock` before returning it; `None` when absent or not matching).

## R3 — `02_act.md` §2.4 `resume`, `autonomy`, `pause` rows (IMP-03)

- `resume` (i): "from an operator terminal (§2.3 exception 2)" → "with a matching
  `S/operator_ack.json` (`command: resume`, `target` = the exact pause file name; 00_global_paths.md
  §1.4), consumed before the file is removed; `lifted_via: "operator_terminal"`".
- `autonomy` (ii): same, with `command: autonomy`, `target: "autonomous"`;
  `decided_by: "operator_terminal"`.
- `pause`: state that its `created_by: "operator"` label may still use the `CLAUDECODE`-unset + TTY
  heuristic because a false positive only makes the pause harder to lift (00_global_paths.md §1.4).
- The `resume` falsification-test text "from a GTM session (`CLAUDE_GTM_COMPANY` set, no TTY)"
  should read "from a GTM session (proof of 00_global_paths.md §1.4 held, no `operator_ack.json`)".

## R4 — `03_schemas.md` §3.10 (≈L520, L558) and §3.17 (≈L789) (IMP-03)

Where these say "operator terminal", append "(= a consumed `S/operator_ack.json`, 00_global_paths.md
§1.4)" once per section, so no reader re-implements the retired `CLAUDECODE`/TTY test.

## R5 — `04_hooks.md` §4.2 G-B rule k (IMP-03, IMP-04)

- Add the literal `operator_ack` to rule k's list (`GTM_ALLOW_TRUST_EDIT`, `GTM_HOLDS_JOB`,
  `trust_edit_allow`, **`operator_ack`**) and to the §4.7 fast-path token list; reason text: the
  operator-authority marker is operator-only (00_global_paths.md §1.4).
- Per the IMP-04 fix: rule k does not fire when the literal appears only as an argument of
  `grep`/`rg` (read-only search).
- §4.3 G-W: no change needed (`S/operator_ack.json` is already under `S`, denied).

## R6 — `04_hooks.md` §4.2 wiring, §4.7/§4.9 and `08_seats_wps.md` Appendix C item 19 (IMP-04)

State that B2's G-B wiring (the `_gtm_bash_block` call in `resolve_block` plus the new
`bash_gate.sh` arms) is committed inert/unregistered and switched on by the coordinator in the same
post-Wave-2 step as G-W's registration; extend Appendix C item 19's text from "G-W" to "G-W and
B2's G-B wiring". 00_global_paths.md §1.5 item 7 now relies on this. (Alternative only if the
wiring must land earlier: exempt from rule c a source operand that is only read, e.g.
`cp <protected> <elsewhere>`, and document the backup/revert path.)

## R7 — `08_seats_wps.md` Appendix C item 7 (IMP-08, IMP-17)

Append: "`backup_state.py --company` takes `ST/actions.lock` (30 s) and snapshots `ST/actions.jsonl`
and `S/chain_anchors/<slug>.json` together before tarring them (00_global_paths.md §0.3). Exit
codes: committed 0/1/2 unchanged; new 3 `anchor_not_in_archive`, 12 actions-lock timeout. Test:
inject a real `store.append` between the two tar members → restore → `verify_chain` passes, no
`PAUSE.chain`."

## R8 — `07_notices_schedules.md` §7.2 `run_gtm_job.sh` and §7.3 plists (IMP-21)

- §7.3: calendar entries are rendered from the pack-timezone slots **converted to the machine's
  timezone** (launchd fires in machine-local time); re-render when the offset between the two zones
  changes (e.g. one zone without DST). Because launchd does not report which entry of a
  `StartCalendarInterval` array fired, each inbox slot needs its own plist (or another shape that
  puts the slot in `ProgramArguments`), with the company-local slot `HHMM` rendered into
  `ProgramArguments`.
- §7.2: add a `--slot <HHMM>` argument (required for `inbox`, refused for other kinds → exit 64
  `usage`); the `run_id` step reads "`_<HHMM>` = `--slot`; date = company-local date of the most
  recent occurrence of that slot at or before job start (00_global_paths.md §0.3)" instead of "the
  latest `cadence.inbox_checks` slot ≤ company-local job start; date company-local at job start".

---

# Round 2 (review findings on `00_global_paths.md`, 2026-09-27)

## R9 — `02_act.md` §2.1, §2.2b, §2.3 dispatch: name and call the GTM-session proof (blocker)

- §2.1: add `tools/gtm/gtmlib/session.py  A1  prove_gtm_session, prove_holds_job, operator-marker
  validate+consume (00_global_paths.md §1.4)` and `tools/gtm/gtm_env.py  A1  standalone stdlib-only:
  real_root(), test_mode(environ), now(environ) (00_global_paths.md §1.1)`.
- §2.2b signatures: `prove_gtm_session(slug: str, environ: Mapping[str, str]) -> tuple[bool, str]`
  (reasons `ok|company_unset|company_mismatch|lease_not_held|lease_unreadable|session_mismatch|not_descendant`);
  `prove_holds_job(environ: Mapping[str, str]) -> tuple[bool, str]`
  (reasons `ok|not_claimed|no_holds_runner_ancestor|runner_not_launchd_child`);
  `consume_operator_ok(ctx: Ctx, command: str, target: str) -> dict | None` (validates and deletes
  under `S/operator_ok.lock`; `None` when absent or not matching, marker left in place).
- §2.3 dispatch: replace "refused with exit 13 `not_gtm_session` when `CLAUDE_GTM_COMPANY` is
  unset" by "refused with exit 13 `not_gtm_session` (result `reason` = the proof's reason) unless
  `gtmlib.session.prove_gtm_session(slug, os.environ)` returns ok". Exception (1) becomes
  "`run-holds --all` when `prove_holds_job(os.environ)` returns ok". **Delete** the parenthetical
  that defends the inline `CLAUDE_GTM_COMPANY=…` spelling by a "requested" G-B rule — the proof does
  not rely on it (R12 adds that rule as defense in depth only).
- Move into §2.3's A1 P2 test list: inline `CLAUDE_GTM_COMPANY=x CLAUDE_GTM_SESSION=<lease id>
  python3 …/act.py propose …` from a process that does not descend from the lease holder → exit 13
  `not_descendant`; lease not held → `lease_not_held`; wrong session id → `session_mismatch`; the
  holds-job ancestry test of 00_global_paths.md §1.4; each RED when reverted to the env-only test.
- Add the §1.1 test-mode refusals to the dispatch order, right after `make_ctx`: outside test mode,
  `R ≠ gtm_env.real_root()` → exit 3 `root_mismatch`; in test mode, a write/lead/repair command
  against the real root or a home listed in the real registries → exit 3 `test_mode_real_state`.
  The dispatch-time trust-root check uses `gtm_env.real_root()` outside test mode.
- Add the §0.3 items: `id_space_exhausted` (exit 3) and `id_source_unreadable` (exit 1) to the
  exit-code list; the extended counter source list; chain-anchor case 2 (`anchor absent + log
  present → chain_truncated`) to `store.verify_chain`'s A1 tests.
- Add the hipaa `drafts/` rules of 00_global_paths.md §1.3 to `propose --file`, `lead-append
  --file`, `card-post --file` and `purge-untrusted` (§2.4), with the two A1 tests named there.

## R10 — `04_hooks.md` §4.2 rule k and §4.7 fast path: `operator_ok`, not `operator_ack` (blocker)

- Rule k: replace the literal `operator_ack` with `operator_ok`, and state that the literal set is
  imported from `system_names.RULE_K_LITERALS` (00_global_paths.md §1.4 "Shared literals"), never
  restated in the hook. Reason text: "the operator-marker directory and its creator script
  (`operator_ok.sh`) are operator-only".
- §4.7 fast-path token list: replace the token `*operator_ack*` with `*operator_ok*`.
- B1 test: `set(rule_k_literals) == set(system_names.RULE_K_LITERALS)` and
  `system_names.OPERATOR_OK_DIRNAME in system_names.RULE_K_LITERALS`; end-to-end:
  `env -u CLAUDECODE bash ~/.claude/tools/gtm/operator_ok.sh resume other-company PAUSE.website_wordpress@remodeling`
  is denied `inline-trust-escape-forbidden`. B2 test: every `RULE_K_LITERALS` member is a
  `*<literal>*` token in `bash_gate.sh`'s arm.

## R11 — `02_act.md` §2.1/§2.3, `03_schemas.md` §3.10/§3.17: shared literals and retired spellings

- `system_names.py` (A1, 02_act.md §2.1) additionally defines `OPERATOR_OK_DIRNAME`,
  `OPERATOR_OK_LOCK`, `OPERATOR_OK_COMMANDS`, `OPERATOR_OK_EVENT_VALUE`, `RULE_K_LITERALS` exactly as
  in 00_global_paths.md §1.4's table; `gtmlib.session` and `operator_ok.sh` (via `python3 -c`) use
  them.
- 03_schemas.md §3.10 / §3.17: wherever "operator terminal" appears, append "(= a consumed
  `S/operator_ok/<command>.<slug>.json`, 02_act.md §2.3)". Confirm no recorded value
  `"operator_terminal"` remains (03 §3.17 line ≈908 already reads `operator_ok`).
- Coordinator: add `tools/gtm/tests/test_contract_literals.py` — greps `tools/gtm/contracts/*.md`
  (not `requests/`, which records history) and fails on `operator_ack` or a recorded `"operator_terminal"` on a line that
  does not contain the word "retired".

## R12 — `04_hooks.md` §4.2 G-B (new arm) and §4.7: inline test overrides and `CLAUDE_GTM_*` (blocker)

- New rule (all sessions, unconditional per 00_global_paths.md §0.4): in any command segment that
  names `tools/gtm/` (or the `*tools/gtm*`/`*act.py*` fast-path tokens), deny
  (`gtm-env-override`) a `NAME=value` prefix, `env [-i] NAME=value …`, `env -u NAME`, `export NAME=…`
  or `declare -x NAME=…` for `NAME` ∈ {`CLAUDE_DIR`, `GTM_TEST`, `GTM_FAKE_NOW`, `HOME`} ∪
  {`CLAUDE_GTM_*`}. Exempt segments whose command word (after `_strip_prefix`) is `pytest` or
  `python[3] -m pytest` (the rule-k IMP-04 exemption shape). Evaluate on the `_strip_prefix`-removed
  assignments **and** on the raw segment text, so `"GTM_TE""ST=1"`-style splits are caught.
- This is defense in depth; 00_global_paths.md §1.1 test mode is the binding control.
- B1 tests: `CLAUDE_DIR=/tmp/x python3 ~/.claude/tools/gtm/act.py status --company x` denied;
  `GTM_TEST=1 GTM_FAKE_NOW=2030-01-01T00:00:00Z python3 …/act.py run-holds --company x` denied;
  `CLAUDE_GTM_COMPANY=x python3 …/act.py propose …` denied; `GTM_TEST=1 python3 -m pytest
  tools/gtm/tests/…` allowed; the same commands with the global enforce marker removed are still
  denied.

## R13 — `04_hooks.md` §4 intro / §4.8: GTM safety denies independent of `_lib.enforcing` (risk)

- State 00_global_paths.md §0.4's split: in GTM scope every GTM rule denies regardless of
  `_lib.enforcing`; in every session rules c, k, the R12 arm and G-W's protected files deny
  regardless; everything else keeps `_lib.enforcing`. `CSA_DISABLE_HOOKS=1` returns before parsing
  or logging.
- B1 test with no `~/.claude/.enforce` and no `.csa-enforce` in the tmp `HOME`: GTM-scope PHI
  `Grep` denied; non-GTM `cp x <R>/.gtm_state/tickets/…` denied; non-GTM rule-a command logged only.

## R14 — `04_hooks.md` §4.2 rule i and §4.1 G-A: the Agency GitHub repo in every spelling (gap)

- Rule i (GTM scope): add the slug forms `gh … -R <org>/Agency[…]`, `gh … --repo <org>/Agency[…]`,
  `gh … --repo=<org>/Agency[…]`, `gh api repos/<org>/Agency[/…]` (also `/repos/…`), and any
  `github.com/<org>/Agency…` / `api.github.com/repos/<org>/Agency…` URL; slug match case-insensitive
  `^[^/\s]+/agency([-_.][^/\s]*)?$`.
- B1 tests: each form denied in GTM scope; `gh issue list -R example-org/AgencyX` allowed
  (boundary); a non-GTM session's `gh issue list -R <org>/Agency` allowed (Agency's own sessions).

## R15 — `08_seats_wps.md` Appendix C item 15 (and the Wave-2 start checklist): hard entry gate (risk)

- Change "Coordinator actions, before Wave 2" to a **hard entry gate**: the coordinator checks,
  before any WP starts, that (a) the §20.9c card is posted in CSA `OPERATOR_DECISIONS.md` `## Open`
  and (b) plan §20.9c is amended to state the interim ruling and cite that card; Wave 2 does not
  start until both hold.
- Replace "re-issued as this run's request" with the verbatim quote in plan §20.9a, and note
  00_global_paths.md §0.1's explicit exception to CONTRACTS.md precedence item 1.

## R16 — `08_seats_wps.md` Appendix C item 14: coordinator additions (major/minor)

- `project_dirs.is_agency_project_dir(name) -> bool` (casefolded; 00_global_paths.md §0.1).
- Rewrite `harvest_tool_trail._matching_project_dirs` to `os.scandir(projects_root)` and test
  `entry.name` against the prefix (and skip `is_agency_project_dir` names) **before** any
  `is_dir`/stat; add `harvest_tool_trail.main([])` to the no-Agency-touch test.
- The no-Agency-touch oracle of 00_global_paths.md §0.1 (patched calls, `AgencyTouched(BaseException)`,
  recorded list, positive control) goes into `tools/gtm/tests/gtm_fixtures.py` (Appendix C item 28).
- `company.py register` refusals `agency_home` (a)/(b)/(c) of 00_global_paths.md §0.1, with the
  symlinked-home and `Agency_GTM` tests.
- Create `knowledge/gtm_company_registry.json` with `"repo_registry_slugs": ["exampleapp"]`
  by hand; make `register`/`unregister` preserve unknown top-level keys; `gtm_slugs()` behaviour for
  missing `repo_registry.json`, absent key, and duplicate slugs per §0.1 "Registry inputs", tested.

## R17 — `03_schemas.md` §3.11 and `07_notices_schedules.md` §7.1 / `GTM_Operator.html`: flat cancels (blocker)

- 03 §3.11: ingest also honors flat `S/cancels/<action_id>` (slug from the id; `who:
  "hand_made_file"`), flat `S/cancels/_all.<slug>`, flat `S/cancels/_all` (every company, once per
  marker name per company, recorded `marker: "flat:<name>"`), and warns on any other flat file —
  exactly as 00_global_paths.md §1.2 "Cancels: two accepted layouts". A2 test RED when flat ingest
  is removed.
- 07 §7.1: the `hold` notice body and each hold row on `GTM_Operator.html` show the exact hand-made
  cancel path `~/.claude/.gtm_state/cancels/<action_id>` (plus `gtm_cancel.sh <action_id>`).

## R18 — `08_seats_wps.md` Appendix C items 7 and 17: backup exclusion of `drafts/`

- Item 17 (gitignore `drafts/`): in the same change, make `company.backup_set()` explicitly exclude
  `<home>/.claude/gtm/drafts/` even if an ignored-class `paths.*` entry covers it; test.
- Item 7: `ST/patches/` and `ST/review_briefs/` are part of `ST` in `backup_set()` (no change;
  state it).

## R19 — `05_approver.md` §5.5 and `06_connectors.md` §6.3/§6.5: real root and test mode (blocker)

- 05 §5.5: the trust root is `gtm_env.real_root()` outside test mode (`git -C <real_root> show
  HEAD:tools/gtm/approver_pubkey.pem`), `R` only in test mode; `approval_sig` imports `gtm_env`.
  A2 test: a fake-root (`CLAUDE_DIR=<tmp>`) signed approval never reaches a connector.
- 06 §6.3/§6.5: in test mode `connector_dispatch.credential_getter`, the GSM fetch and every live
  transport refuse exit 3 `test_mode_no_live` before any network/GSM call; only fixture transports
  run. L test: a live transport constructed in test mode raises before its first request.
- 07 §7.2/§7.6: launcher refusal on non-empty `CLAUDE_DIR`/`GTM_TEST`/`GTM_FAKE_NOW` (empty =
  unset); launcher test recipe of 00_global_paths.md §1.5 item 9.

---

# Round 3 (second review of `00_global_paths.md`, 2026-09-27)

Supersessions: **R20** replaces R12's single "test-override arm" by two named rules (l, m); **R22**
amends R17's flat-cancel key; **R24** replaces R15's whole-Wave-2 entry gate. Where an earlier
request conflicts with one below, the one below wins.

## R20 — `04_hooks.md` §4.2 (rules l, m), §4.2 wiring / `_finish`, §4.6, §4.1 (blocker)

- **Unconditional-deny mechanism (00_global_paths.md §0.4 "Mechanism").** `pretooluse_bash._Block`
  gains keyword field `unconditional: bool = False` (in `__slots__` and `__init__`). Every `_Block`
  built by G-B rule c, k, l or m — in any session — and by any other GTM rule in GTM scope sets it
  `True`. `_finish` emits the deny when `enforcing(where) or block.unconditional` and logs
  `enforce=<that value>`. G-A, G-W, the path gate and gate-gtm apply the same test in their own emit
  step. §4.6 gate-gtm (≈L868-869 "emits … only when enforcing"): replace with "emits when
  `unconditional or _lib.enforcing(where)`, where `unconditional` is true in GTM scope". State that
  `CSA_DISABLE_HOOKS=1` alone overrides it. B1 tests per 00 §0.4 (a)–(d), incl. (c): a non-GTM
  `Write` under `S` with no enforce marker is denied `machine-written-path`.
- **Rule l** (`gtm-identity-forge`): exactly as 02_act.md §2.3 defines it (inline/`env`/`export`/
  `unset`/`declare -x` of any `CLAUDE_GTM_*` in a segment naming `act.py`), all sessions,
  unconditional.
- **Rule m** (`gtm-env-override`) — R12's arm minus `CLAUDE_GTM_*` (now rule l): in a segment
  naming `tools/gtm/`, deny a `NAME=value` prefix, `env [-i] NAME=value`, `env -u NAME`, `export`,
  `declare -x` for `NAME` ∈ {`CLAUDE_DIR`, `GTM_TEST`, `GTM_FAKE_NOW`, `HOME`}; exempt segments whose
  command word is `pytest` / `python[3] -m pytest`; evaluate on stripped assignments and raw text.
  All sessions, unconditional. B1 tests as in R12 (minus the `CLAUDE_GTM_COMPANY` case, which moves
  to rule l's tests).
- §4.1 (≈L44) `<UTCts> ≥ ticket["created_at"]`: compare parsed aware UTC datetimes, with `<UTCts>`
  as defined in 00_global_paths.md §0.3.

## R21 — `02_act.md` §2.1, §2.2b, §2.3, §2.4 exit codes and writers (blocker/major)

- §2.3 dispatch, before `make_ctx`: `CSA_DISABLE_HOOKS` non-empty and not `0` in act.py's own
  environment → every `write`/`lead`/`repair`-policy command (incl. the three exceptions) exits 3
  `hooks_disabled`. A1 test per 00 §0.4.
- Exit-code list: add `root_mismatch` (3; distinct from exit 11 `TRUST_KINDS`),
  `test_mode_no_live` (3), `test_mode_real_state` (3), `hooks_disabled` (3), `id_space_exhausted`
  (3), `id_source_unreadable` (1), `bad_fake_now` (2).
- §2.1/§2.2b `gtm_env` (with R9): add `real_home()`, `same_root(a, b)`, `real_expand(s)`,
  `refuse_real_state(R, H)` / `RealStateRefused`, and `now()` returning aware UTC in both branches
  (00_global_paths.md §1.1). `gtmlib.store.append`, the shared atomic-write helper, the pause-file
  writer, `gtmlib.leads` and the `approvals_verify` nonce-ledger writer call
  `refuse_real_state(ctx.R, ctx.home)` before writing; the §1.1 test (e) goes into A1's list.
- `store.next_id` sources: add `ST/connector_idem/*.jsonl` and `ST/cards_posted.jsonl` (contents)
  with the `_0020 → _0021` test; `store.verify_chain`: add case 5 (lagging anchor passes and is
  re-anchored under the lock), case 3 reason `chain_truncated`.
- §2.4 `propose --file`, `lead-append --file`, `card-post --file` hipaa delete: `os.path.realpath`
  containment in `realpath(G/drafts)`, with the `..` and symlink tests of 00_global_paths.md §1.3.
- Operator-marker restatement: 00_global_paths.md §1.4 now uses `<command>.<slug>.<target>.json`
  and `0 ≤ age < 15 min` (future-dated invalid); please add the future-dated case to §2.3's tests.

## R22 — `03_schemas.md` §3.11, §3.12/§3.17/§3.19/§3.23, §3.20, §3.22; `07_notices_schedules.md` §7.1, §7.3 (blocker/major)

- 03 §3.11 (amends R17): flat `_all`/`_all.<slug>`/`_all.<other>` markers are recorded once per
  `marker: "flat:<name>:<st_ino>:<st_mtime_ns>"` (one `os.stat` at ingest), so a re-created or
  re-touched marker cancels again. A2 test: ingest `_all`, place a hold, `touch _all` → the new hold
  is cancelled; RED when keyed by name only.
- 07 §7.1 (amends R17): `GTM_Operator.html` lists every flat `S/cancels/_all*` marker present with
  "remove this file when you no longer need it".
- 03 writers: `cycle.py`, `autonomy_ladder.py` (incl. `promote`), `scoreboard.py`,
  `outside_actor.py`, `experiments.py`, `transcript_index.py`, `mission_record.py`, `metrics.py`,
  `perf_report.py` call `gtm_env.refuse_real_state` before their first write (00_global_paths.md
  §1.1 (3)); G test (d) of §1.1 (autonomy_ladder under a fake clock leaves the breaker pause).
- 03 §3.20 phi1 listing procedure: never descend into a folder equal to or under a
  `phi_denylist.json` `path` entry; record it as `{path, kind: "dir", denylisted: true}`.
- 03 §3.22 `system_names.py`: add `HOLDS_RUNNER_RELPATH = "schedules/run_gtm_job.sh"` (and the
  operator-marker constants of R11).
- 07 §7.3: the holds plist renderer builds the runner path from
  `real_root()/system_names.HOLDS_RUNNER_RELPATH`; K test: the rendered holds plist's
  `ProgramArguments` names exactly that path (00_global_paths.md §1.4 "Holds-job proof").

## R23 — `05_approver.md`, `06_connectors.md` §6.2, `08_seats_wps.md` Appendix B #128/#156, Appendix C items 7, 14

- 06 §6.2 "Test mode" bullet: replace the restated compare (`normpath(R) == normpath(real_root())`
  …) by a call to `gtm_env.refuse_real_state(ctx.R, ctx.home)` (00_global_paths.md §1.1 (3); it
  covers case-variant roots and real-registry `~` expansion against the passwd home).
- 05: the `approvals_verify` nonce-ledger writer calls `refuse_real_state` (00 §1.1 (3)).
- 08 Appendix B #128: marker path `S/operator_ok/<command>.<slug>.<target>.json`, validity
  `0 ≤ age < 15 min`; #156: add `real_home`, `same_root`, `real_expand`, `refuse_real_state`, aware
  `now()`.
- 08 Appendix C item 7: backup exclusions are exactly 00_global_paths.md §1.3's list
  (`ST/untrusted/**`, `H/.playwright-mcp/**`, `ST/lead_fallback.replayed-*.jsonl`, `G/drafts/**`).
- 08 Appendix C item 14 (extends R16): `register` runs every refusal on the `abspath`-ed argument
  text before any `resolve()`/`exists()`; refusal (d) `ancestor_of_agency`; `symlink_limit` after
  40 links; stderr `error: agency_home: <reason>`, `error: reserved_slug: runtime`,
  `error: bad_slug: <slug>`, exit 1; `gtm_slugs()` registry-input cases (5)–(7) of
  00_global_paths.md §0.1, each with a test.

## R24 — `08_seats_wps.md` Appendix C item 15; `03_schemas.md` pack schema; `02_act.md` §2.4/§2.8 (risk; replaces R15)

- Appendix C item 15: **not** a whole-Wave-2 gate. Before P1b enables any OtherApp `website_static`
  row, the coordinator confirms (a) the §20.9c card is posted in CSA `OPERATOR_DECISIONS.md`
  `## Open`, and (b) the interim deny is recorded in the plan as a **new** §20.x entry (e.g. §20.18)
  citing the card. §20.9c's verbatim text is never edited. Correct the card draft so it no longer
  says the operator "later re-issued" anything; it states the facts of 00_global_paths.md §0.1
  "§20.9c and §20.9a" and asks yes/no on the OtherApp `website_static` carve-out.
- 03 pack schema (`company_schema.json` and §3 pack text): add `marketing_code_paths` (array of
  literal repo-relative paths, default `[]`) and `pricing_source_ref` (string, optional);
  `company.validate_company` refuses a `marketing_paths` entry equal to or under the Agency root
  (text-only `norm`, never stat'd).
- 02 §2.8 check 9 and §2.4 `complete --commit`: add refusals `non_marketing_path` (the code/build
  file rule of 00_global_paths.md §0.1, casefolded, lifted only by an exact `marketing_code_paths`
  entry) and `price_source_missing` (currency change without the pack's `pricing_source_ref`
  verbatim in `why`), plus `agency_boundary` for a `website_static` target repo under Agency; the
  A1 tests listed in 00 §0.1.

---

# Round 4 (third review of `00_global_paths.md`, 2026-09-27)

Applied in `00_global_paths.md` itself this round (no further request needed): `requests/05_approver.md`
R12 (stdlib only, `GTM_VERIFY_BACKEND` removed), R22 (missing `S` rows, tracked
`approver_fingerprint.txt`/`approver_pubkeys/`), R29 (`gtm_env` stdlib-only; `trust_edit_allow.json`
writer). Supersessions: **R25** replaces R24's `marketing_code_paths` and `price_source_missing`
text; **R26** replaces R24's card wording for Appendix C item 15; **R30** amends R11's test file set.
Where an earlier request conflicts with one below, the one below wins.

## R25 — `08_seats_wps.md` Appendix C item 13; `02_act.md` §2.4/§2.8 check 9; `03_schemas.md` pack schema (blocker/major; replaces R24's last two bullets)

- **Withdraw `marketing_code_paths`** everywhere (03 pack schema, 02 §2.8, the R24 text). No pack key
  re-admits a `checks.MARKETING_PATH_NEVER` path; App C item 13 stays the single definition.
- App C item 13 (the one definition): add to `MARKETING_PATH_NEVER` `.gitignore`, `*.toml`, `*.yml`,
  `*.yaml`, `.htaccess`, `_headers`, `_redirects`, `*.lock`, `Makefile`, `Dockerfile`,
  `tsconfig*.json`, `.pre-commit-config.yaml`, `**/.github/**`. The tracking-content rule applies to
  **added and removed** lines and also matches `javascript:`; `*.svg` stays content but is subject to
  the content rule. State "tracking snippets are out of scope for `website_static`". Apply before A1
  builds check 9. Tests (A1 check 9 and A2 `complete --commit`): with the pack glob
  `marketing/website/**`, an edit of `marketing/website/partials/tracking-inline.html` →
  `non_marketing_path`; removing a `gtag(` line → `tracking_change_not_static`; each RED when reverted.
- **Price rule (00_global_paths.md §0.1 guardrail bullet 2, the definition):** 03 pack schema:
  `pricing_source_ref` = object `{"path": <repo-relative JSON file>, "key": <RFC 6901 pointer>}`
  (optional); `company.validate_company` refuses a `path` matching any `marketing_paths` glob. 02 §2.8
  check 9 and §2.4 `complete --commit`: read the source with `git show <rev>:<path>` (`HEAD` at
  `propose`, `<sha>^1` at `complete --commit`), never the working tree; per-file multiset trigger over
  `-`/`+` lines with the `AMOUNTS` regexes of 00 §0.1; refusal codes `price_not_in_source`,
  `price_source_missing`, `price_source_in_patch` (exit 3), and the six A1 tests listed in 00 §0.1.
  No proposal field carries the ref; `why` keeps `{plan_ref, metric_id}`. A refusal is followed by an
  operator pricing card, never a reprice.

## R26 — `08_seats_wps.md` Appendix C item 15; plan §20.x entry (gap; replaces R24's card wording)

- §20.9c stands as ruled; do not card the question it answered. Split the follow-up: (1) file **one
  tracked issue** "Agency marketing-path carve-out for G-B rule i and the path gate's
  `agency-boundary` rule" with **trust-architect as reviewer-of-record, due before P1b**; (2) post one
  operator card asking only "Which OtherApp site and which repo paths may the GTM team edit?".
- Before P1b enables any OtherApp `website_static` row: (1) landed with a clean trust-architect
  review, (2) answered, and the interim recorded as a new plan §20.x entry citing both.

## R27 — `04_hooks.md` §4 (`agency_root()`), §4.2 rule i, §4.4 path gate `agency-boundary` (gap/nit)

- `agency_root()` cites 00_global_paths.md §0.1 "The Agency root": outside test mode
  `Path(gtm_env.real_home())/"Desktop"/"Agency"`, in test mode `Path.home()/"Desktop"/"Agency"`.
- Rule i and the `agency-boundary` path-gate rule also fire, unconditionally, when payload
  `agent_type ∈ DEPARTMENT_SEATS` and the call's cwd is not equal to or under the Agency root (text
  `norm`). State that other non-GTM sessions are covered by prose and code review only (accepted
  residual) with the no-Agency-touch oracle as backstop. B1 tests: a `marketing-director` payload
  (probe q fixture) with cwd in CSA running `rg x ~/Desktop/OtherApp` → denied; the same from a cwd under
  the Agency root → allowed; RED when the department-seat arm is removed.
- 04 §4.3 "Trust roots" item 1 and §4.9: the hook must not import `cryptography` (already
  `requests/05_approver.md` R27); the coordinator's §0.2 contract check fails until it is applied.

## R28 — `02_act.md` §2.3 step 0 / §2.4 `purge-untrusted`; `05_approver.md` §5.5; `08_seats_wps.md` Appendix C item 7 (major)

- The trust-failure spool path becomes `S/lead_spool/<slug>/<UTCts>_<8 hex>.json` (slug from act.py's
  own `--company` argument, grammar-checked with a stdlib regex before any `tools/gtm` import;
  invalid/absent → `_unknown`), created exclusively (00 §0.2).
- `purge-untrusted`: for `regulated ∋ hipaa` packs and `_unknown`, delete spool files older than
  `--older-than-days` (default 30) with one `warn` notice per deleted unreplayed file.
- App C item 7: `backup_set()` includes `S/lead_spool/<slug>/` for non-hipaa packs and excludes it for
  hipaa packs; the A1 tests of 00_global_paths.md §1.2 "Backup and purge".

## R29 — signed operator marker: `02_act.md` §2.3 "Operator marker" and §2.4; `05_approver.md` §5.3/§5.4; `04_hooks.md` §4.2 rule k; `03_schemas.md` §3.9/§3.10/§3.17; `08_seats_wps.md` Appendix B #128, Appendix C item 18 (major)

- Design (00_global_paths.md §1.4 "Operator authority"): `S/operator_ok/<command>.<slug>.<target>.json`
  is a GTMApprover-signed record `gtm.operator_ok.v1` over the canonical payload `{"v": 1, "kind":
  "operator_ok", "command", "company", "target", "nonce", "expires"}`; act.py verifies against the
  HEAD key via `approval_sig.verify_raw`, checks `now < expires ≤ now + 15 min`, consumes the nonce in
  `S/approval_nonces.jsonl` (holder `operator-ok:<command>:<target>`, `company` = slug), then deletes
  the marker. HEAD without a key → `approver_not_installed` (exit 11); card routes unaffected.
- 05: add `--sign-operator-ok <command> <slug> <target>` (reason string in 00 §1.4) and
  `gtm_approve.sh operator-ok`; `operator_ok.sh` execs it.
- 02 §2.4 `resume`: a pause with a non-null `lift_card` is never lifted by any marker
  (`resume_card_required`, marker left in place). 03 §3.9: the `operator-ok:` holder form.
- 08 Appendix C item 18: drop owner-pause lifts, shadow exit and `pause` labelling from the operator
  question (they are now signed); trust-architect is reviewer-of-record for landing this design (a
  design item, not a card). Appendix B #128: the signed form.
- A1 tests: the P2 list of 00 §1.4 (unsigned old-form marker refused, wrong key, working-tree key
  swap, expired/over-long `expires`, nonce replay, A0022 `lift_card` refusal).

## R30 — `tools/gtm/tests/test_contract_literals.py` (amends R11) (major)

- Read a literal file list — `contracts/00_global_paths.md`, `02_act.md`, `03_schemas.md`,
  `04_hooks.md`, `05_approver.md`, `06_connectors.md`, `07_notices_schedules.md`, `08_seats_wps.md`,
  and `tools/gtm/CONTRACTS.md` — never a glob; exclude `OPEN_FINDINGS.md` and `requests/**` by
  design (history). Also fail when `cryptography` appears on a line with none of "retired",
  "never imported", "stub" (00 §0.2).

## R31 — `08_seats_wps.md` Appendix C items 14 and 28 (coordinator additions; extends R16/R23) (major/minor)

- `register`: the raw-component walk of 00_global_paths.md §0.1 (no `abspath` first; `..` applied to
  the real prefix; final text path `F` passed to the committed code), (a)/(c)/(d) on `F` and on the
  argument text, `bad_home_chars` (`[A-Za-z0-9/_. -]` only), existing Agency-rooted registry entries
  never resolved (`register agency --root <ok>` → `registry_path_in_agency`); the tests listed there,
  each under the oracle with an empty record.
- `gtm_slugs()` case (5): a root that is not absolute after `expanduser` → `CompanyError`;
  `validate --all` re-runs the register walk on every registered home. Switch `company.py list` to
  `gtm_slugs()` too.
- Oracle (item 28): the full patch set of 00 §0.1 (mutations, `os.system`, `os.spawn*`, `pty.spawn`,
  `os.fork`), the argv forms (`expanduser`, `=` suffixes, `/` substrings), both Agency roots, the
  "first component after `R/projects/`" rule, the monkeypatch of each pack's `legacy_workdirs` (read by `harvest_tool_trail._legacy_workdirs`; the old hardcoded legacy-dir constant was removed 2026-09-28)
  and `DEFAULT_GLOBS_TEMPLATE`, and the four new positive controls.
- `gtm_env` (A1): `real_agency_root()`, the `same_root` `HOME` arm of `test_mode`, and
  `refuse_real_state`'s compare against both Agency roots, with the unit and A1 tests of 00 §1.1.

## R32 — `02_act.md` §2.2b/§2.4 exit codes; `03_schemas.md` §3.16 scope; `06_connectors.md` §6.6 (minor/nit)

- 02: add `id_collision` (exit 1) for the exclusive-create rule of 00 §0.2; parsers of `<UTCts>` file
  names accept the `-<n>` suffix (00 §0.3).
- 02 §2.4 / App C item 7: `backup_state.py --restore` check order unsafe member (1) → runtime-state
  refusal (1) → `anchor_not_in_archive` (3); chain-verify case 3 counts `actions.broken-*` as a
  reference.
- 03 §3.16 and 06 §6.6: state the second accepted residual of 00 §0.1 (Agency work in a session whose
  project dir is not `P_A`-prefixed) and the binding rule that no transcript text from a non-GTM-home
  dir is copied into any GTM record.

---

# Round 5 (resolving `OPEN_FINDINGS.md` entries tagged for `00_global_paths.md`, 2026-09-27)

Checked in this round: IMP-03, IMP-04, IMP-08, IMP-17 and IMP-21 are resolved in
`00_global_paths.md` (§0.3 "The backup captures the log and its anchor at one moment" and
"`backup_state.py` exit codes"; §0.3 cycle-id row; §1.2 `gtm_lists.py` exit codes; §1.4 "GTM-session
proof", "Holds-job proof", "Operator authority is never read from the environment"; §1.5 item 7),
and their requests R1–R11, R29 are applied in 02_act.md §2.3, 04_hooks.md §4.2 (activation note,
IMP-04), 07_notices_schedules.md §7.2/§7.3 (`--slot`, timezones) and 08_seats_wps.md Appendix C
item 7 / Appendix B #115, #128, #139. This round aligns the §0.3 cycle-id row with
07_notices_schedules.md §7.2's `run_date` ("scheduled occurrence on a scheduled day", every kind,
computed by `runner_probe.py`) — the old row's "most recent occurrence of that slot" gave a Sunday
date to a Monday wake-up fire, which 07 §7.2 correctly forbids.

## R33 — `../CONTRACTS.md` (index): record the baseline sha (coordinator gate; cited by 00_global_paths.md header "The baseline")

`00_global_paths.md`'s header cites this request and it did not exist. Add to `CONTRACTS.md`, next
to the precedence list, one line: "**Baseline:** Wave-2 WPs build on `~/.claude` commit `<sha>` —
commit `44b9bf5` plus the `company.py`/`company_schema.json`/`activity_log.py`/
`harvest_tool_trail.py`/`backup_state.py`/`README.md` follow-up (registry handling, `register|
unregister`, `_repo_registry_repos()`) and its tests. No WP starts until this sha is filled in." The
coordinator commits the follow-up (its own reviewed train), fills `<sha>`, and confirms every
"committed" fact in `00_global_paths.md` still holds at that sha before the first WP dispatch.

## R34 — `07_notices_schedules.md` §7.2 `runner_probe.py` (IMP-21 testability; cited by 00_global_paths.md §1.5 item 9)

`00_global_paths.md` §1.5 item 9 tests clock-dependent launcher behaviour on `runner_probe.py`
directly, never through the launcher's environment. §7.2 names the D tests but not the probe's
clock. Add to the `runner_probe.py` bullet: "Its clock is `gtm_env.now(os.environ)`
(00_global_paths.md §1.1), so a D test sets `GTM_TEST=1 GTM_FAKE_NOW=<UTC Z>` in the probe
subprocess's `env=`; the date/slot computation is a pure function
`runner_probe.compute(pack: dict, kind: str, slot: str | None, now: datetime) -> dict` returning
the printed object minus `paused`, which the D tests of company-local midnight, the weekend wake,
the late `monthly_load` and DST call in process with `now=`." (The function name is a proposal;
07 may choose another, and `00_global_paths.md` §1.5 item 9 names only `runner_probe.py`.)

## R35 — `03_schemas.md` pack schema; `02_act.md` §2.2 (`pricing_values`), §2.4 `complete --commit`, §2.8 check 9; `08_seats_wps.md` Appendix B, Appendix C items 13/14; CSA development item (major; amends R25's price bullet, which it replaces)

The price rule in `00_global_paths.md` §0.1 "The `marketing_paths` guardrail" bullet 2 is now
bound by **slot identity**, not by a flat value set (a `$49 Basic`/`$99 Pro` tier swap passed the
old check; `<td>59</td>`, `&#36;59` and split `<span>` forms were undetected; `plan` matched
`planning`). Apply:
- **03 pack schema:** `pricing_source_ref` = object `{"path": <repo-relative JSON file>, "slots":
  {<slot_id ^[a-z0-9][a-z0-9_]{0,63}$>: <RFC 6901 pointer>, …}}` (≥ 1 slot; the `key` form is
  withdrawn); new optional `price_display_paths` = list of exact repo-relative paths, each matching a
  `marketing_paths` glob and ending in `.html`/`.htm`/`.njk`/`.hbs`/`.md`. `company.validate_company`
  refuses a `path` matching `marketing_paths`, a bad slot id or pointer syntax, and a
  `price_display_paths` entry outside `marketing_paths` or with another extension.
- **02 §2.2:** replace `pricing_values(ctx, rev) -> set[Decimal]` with `pricing_slots(ctx, rev) ->
  dict[str, Decimal]` (each pointer must resolve to exactly one JSON number; else
  `price_source_missing`) and add `checks.decoded_text(image: str, path: str) -> str` (stdlib
  `HTMLParser(convert_charrefs=True)`, data + attribute values except `data-price-slot`, joined with
  no separator; non-HTML-family → `html.unescape`).
- **02 §2.8 check 9 and §2.4 `complete --commit`:** Rule A (declared price-display files: every
  slot's single amount equals `pricing_slots[slot_id]` at `<rev>`; unknown slot → `price_slot_unknown`;
  nested/zero/multiple amounts → `price_slot_malformed`; any change in the ordered unslotted price
  tokens → `price_unslotted`) and Rule B (other files: ordered whole-document `AMOUNTS` compare,
  word-bounded vocabulary line compare, currency-word flag → `price_outside_display_paths`), exactly
  as 00 §0.1 states them; refusal codes `price_not_in_source`, `price_source_missing`,
  `price_source_in_patch`, `price_unslotted`, `price_slot_malformed`, `price_slot_unknown`,
  `price_outside_display_paths` (exit 3, state unchanged); the A1/A2 test list of 00 §0.1 (tier swap
  in slots and in an undeclared file, `<td>59</td>`, `&#36;59`, split span, "planning 3→5 steps",
  "forty-nine dollars", working-tree-only source, source-in-patch). **Routing:** no card for the
  session-fixable codes; an operator pricing card only when the session's evidence is that the
  source itself is wrong. This replaces R25's "a refusal is followed by an operator pricing card".
- **08 Appendix B:** index the header's three derived narrowings of §20.9c (tracking snippets out of
  scope; the never-list with no pack override; slot-bound price corrections) as DECIDED HERE entries,
  and correct App C item 13 / #177 / the 08 text at L368-369 and L1187 that still say "a
  currency-amount change needs `pricing_source_ref` verbatim in `why`" (the proposal's `why` is never
  read by this rule).
- **CSA development item (coordinator files it as a CSA issue; not a GTM edit):** add a generated
  JSON projection `_Config_Project/docs/domain/opex_and_pricing.prices.json` of the ruled source
  `opex_and_pricing.html` (a CSA script reading `data-price-slot`-tagged cells, plus a CSA test that
  the two agree; a data projection, not a second pricing doc, so CSA `CLAUDE.md`'s "only cost or
  pricing analysis doc" rule holds). Until it lands the CSA pack carries no `pricing_source_ref`
  (every CSA price change refuses `price_source_missing`). `pricingRows.json` is never a ruled
  source. OtherCompanyB, OtherApp and OtherCompany carry none until a reviewed pack change names an
  operator-ruled source file.

## R36 — `08_seats_wps.md` Appendix C items 7 and 14; `03_schemas.md` `company.validate_company` `paths.*` (major/minor)

Coordinator additions to item 14 (on top of R16/R23/R31):
- `gtm_env.norm_text`/`norm`/`is_under`/`agency_root` (00 §0.1 "The one path-compare
  implementation", incl. the `/System/Volumes/Data` firmlink strip) are the only compare every
  `company.py` Agency check uses; the three firmlink unit tests of 00 §0.1.
- `gtm_slugs()` also excludes a slug whose home is an **ancestor** of `A` (or of
  `real_agency_root()`), reported by `validate --all` as `INVALID <slug>: agency_home:
  ancestor_of_agency`; coordinator test with registry root `~/Desktop` → excluded.
- `gtm_slugs() -> list[str]`, sorted, no duplicates; the new `company.py list` subcommand prints it
  one per line (it is **added**, not switched — the baseline has no `list`).
- `validate --all` prints `INVALID <registry path>: repo_registry_slugs_missing` and exits 1 when the
  GTM registry exists without a list-of-strings `repo_registry_slugs`; `company.py index` refuses
  with no rewrite in that state; coordinator test: key removed → validate exit 1, index exit 1, both
  index files byte-identical.
- `resolve_home()` and `_entry_root_path()` raise `CompanyError` for a root that is not absolute after
  `expanduser`, before any `resolve()`; `validate --all` reports case (5) as `INVALID <slug>:
  bad_registry_entry: <text>` and continues, exit 1.
- `harvest_tool_trail._transcript_cwd_is_under_home` (L171) compares the transcript's recorded
  `cwd` with `A`/`real_agency_root()` by text before `Path(cwd).resolve()`; the same binding rule
  for every transcript consumer (00 §0.1 oracle paragraph). Item 28's oracle fixture adds the
  non-Agency-dir transcripts whose `cwd` and a `tool_input` path lie under `A`, and the two new
  positive controls (firmlink `open`, `Path(cwd).resolve()`).
- **03 / `company.validate_company`:** refuse any `paths.*` value that is absolute, starts with `~`,
  has a `..` segment, or whose `norm(os.path.join(H, value))` is equal to or under `A` or
  `real_agency_root()`; one test per case. And refuse a `marketing_paths` glob by the same
  absolute/`~`/`..`/joined-literal-prefix rule (00 §0.1 "Interim deny"), with the tests for
  `../Agency/x/**`, `/Users/u/Desktop/OtherApp/**`, `~/Desktop/OtherApp/**`.
- **Item 7:** the `backup_state.py --restore` order is the committed one plus a new step (5)
  anchor pairing after `_validate_member` (00 §0.3), with the exact arcnames
  `.claude/gtm/state/actions.jsonl` and `_gtm_state/<slug>/chain_anchors/<slug>.json`; the backup
  side skips the two live files with `tar.add(..., filter=...)`. Item 7 also excludes
  `S/othercompany_listing.json`, `S/phi_denylist.json` and `S/othercompany_read_allowlist.json` from
  every `backup_set()` (00 §1.2), with the test that no company set holds them.

## R37 — `04_hooks.md` §4.2 rule i, §4.4 path gate `agency-boundary` (gap; widens R27)

Replace R27's `agent_type ∈ DEPARTMENT_SEATS` condition with **any non-empty top-level
`agent_type`** (every sub-agent: `research-scout`, `implement`, `explore`, `test-writer`, the
architects, and the catch-all `general-purpose`/`Explore`/`Plan`/`claude`), still only when the
call's cwd is not equal to or under the Agency root (text `gtm_env.norm`/`is_under`, against `A`
and `real_agency_root()`). A top-level session (no `agent_type`) stays prose-covered, with the
reason 00 §0.4 states (runtime-maintenance scans of Agency's `.claude/worktrees` and rosters). The
arm depends on probe q; record the probe result before B1. B1 tests: `research-scout` `Grep` of an
Agency path from a CSA cwd → denied, same from an Agency cwd → allowed; `implement` `Read` and
`general-purpose` `ls <A>` from `~/.claude` → denied; a payload with no `agent_type` → logged only;
each deny RED when narrowed back to `DEPARTMENT_SEATS`.

## R38 — `04_hooks.md` §4.2 wiring / §4.9 `pretooluse_bash` bullet; `02_act.md` §2.3 `hooks_disabled` (major/nit)

- **`resolve_block` (B2):** when an earlier gate returns a non-`unconditional` block and
  `not _lib.enforcing(where)`, still call `_gtm_bash_block`; an `unconditional` G-B block wins
  (the earlier one is logged as `shadowed_block`). Unchanged when enforcing. B1/B2 falsification test
  with no enforce marker: `cp x ~/.claude/.gtm_state/tickets/t/y.json; git stash` → denied
  `protected-state-write`; RED under plain first-block-wins. (R13's (a)–(d) used single-rule
  commands only and could not catch this.)
- **02 §2.3:** when `lead-append` refuses exit 3 `hooks_disabled`, it first spools the raw input to
  `S/lead_spool/<slug>/` (same writer and rules as the trust-root-failure path, R28) and writes one
  `warn` notice; result JSON carries `spooled`. A1 test per 00 §0.4.

## R39 — `04_hooks.md` §4.2 rule k, §4.7 fast path; `05_approver.md` §5.3/§5.4 (`--sign-operator-ok`, `--sign-trust-edit`, `gtm_approve.sh`); `02_act.md` §2.3/§2.4 `autonomy`; `03_schemas.md` §3.17 (major/risk)

- **Rule k / §4.7:** `RULE_K_LITERALS` gains `operator-ok`, `sign-operator-ok`, `trust-edit`,
  `sign-trust-edit` and `GTMApprover.app/Contents/MacOS/GTMApprover` (00 §1.4 "Shared literals"); the
  §4.7 fast-path token list and its B2 test follow. B1 tests: `env -u CLAUDECODE
  ~/.claude/scripts/gtm_approve.sh operator-ok resume other-company PAUSE.gbp`, `gtm_approve.sh
  trust-edit /x`, a direct binary run with `--sign-operator-ok`, and `open -a GTMApprover --args
  --sign-trust-edit /x` → each denied; each RED when its literal is removed. A non-signing
  `gtm_approve.sh` re-show is not denied.
- **05 §5.3/§5.4:** `--sign-operator-ok` and `--sign-trust-edit` show an in-app `NSAlert` with the
  request text and **Deny as the default** (Return and Escape deny) before the LAContext prompt,
  exactly as a `$` approval; C tests: dismiss-by-Return → exit 7 and no marker written.
- **02 §2.4 `autonomy` / §2.3 / 03 §3.17:** withdraw `autonomy --card` (00 §1.4: the plan names no
  lift card for leaving shadow; shadow is the safe state). `--level autonomous` is allowed only by
  met `shadow_exit` criteria or a consumed signed operator marker; A1 test: an approved card with
  criteria unmet and no marker → exit 3 `shadow_criteria_unmet`. `resume --card` and the other
  plan-named card routes stay, recorded in 00 §1.4 as an accepted detect-after residual with the
  §2.6 authorship scan's blind spots listed.
- **08 Appendix B #128 / Appendix C item 18:** note both changes; trust-architect remains
  reviewer-of-record for the marker design (R29).

## R40 — small shape alignments from the 00_global_paths.md round of 2026-09-27 (minor/nit)

- **03 §3.12 / 07 §7.2 `validate_run.py` / `cycle.py open`:** `system_names.cycle_id_ok()` — `inbox`
  and `interactive` require HHMM, the other four kinds forbid it; refusal exit 3 `bad_cycle_id_hhmm`;
  one test per kind (00 §0.3).
- **02 §2.1/§2.3, 04 §4 hooks clock:** `gtm_env.BadFakeNow(ValueError)` is what `now()` raises for an
  unparseable honored `GTM_FAKE_NOW`; tools map it to exit 2 `bad_fake_now`, hooks catch it and use
  the real clock. `gtm_env.refuse_real_state(R, H, environ=os.environ)` — act.py passes the same
  mapping it passed `test_mode` (00 §1.1).
- **02 §2.6 / 03 §3.17:** the lock files are exactly `ST/cards_posted.lock` and
  `ST/autonomy_state.lock` (00 §1.3).
- **02 §2.3 step 0 / 03 §3.14:** lead-spool file names are random-suffix class,
  `^(?P<ts>\d{8}T\d{6}Z)_(?P<rnd>[0-9a-f]{8})\.json$`, redraw the 8 hex on `EEXIST` (≤ 5, then
  `id_collision`), replay order `(ts, rnd)` (00 §0.2).
- **02 `gtmlib.store` id allocation:** the optional per-file mtime pre-filter (start of UTC day `D`
  minus 48 h; never on the three append-only logs) of 00 §0.3 "Cost bound".
- **04 §4.9 import rule:** `Path(os.path.abspath(__file__)).parent.parent / "tools" / "gtm"`
  (unresolved), inserted at `sys.path[0]`; B2 tests `test_no_module_name_collision` and the
  symlinked-hook import test (00 §1.1).
- **08 Appendix C item 15 / R26:** the OtherApp-site card goes on the OtherApp home's
  `operator_input` surface (`~/Desktop/OtherApp_GTM/.claude/oversight/manifest.json`); if asked
  before that home exists (P1b), it is posted on CSA's `OPERATOR_DECISIONS.md` and moved verbatim, with
  any answer, in the P1b change that creates the home (00 §0.1 "Scope of the gate" (b)).
- **02 §2.4:** the "reviewed patch cannot be swapped" guarantee is FID-04's `after.patch_sha256` /
  `post_image` re-check at `complete --commit`; cite that A2 test wherever rule c/G-W is named as
  the reason (00 §1.3).

---

# Round 6 (re-check of `OPEN_FINDINGS.md` entries tagged for `00_global_paths.md`, 2026-09-28)

I checked IMP-03, IMP-04, IMP-08, IMP-17 and IMP-21 again. All five are still resolved in
`00_global_paths.md`, and their cross-file requests are applied in 02_act.md, 04_hooks.md §4.2
(rule c IMP-04 exception, rule k, activation note), 07_notices_schedules.md §7.2/§7.3/§7.6
(`--slot`, `100 + min(n, 27)`) and 08_seats_wps.md Appendix B #139 / Appendix C item 7.
One stale sentence was fixed in this file only: §1.5 item 7 (IMP-04) said G-W does not protect `gtmlib/`
and that rule c denies every `cp` of a protected file. Both are now false. 04_hooks.md §4.3 "Trust
roots" covers the whole live `R/tools/gtm/` subtree, and rule c's IMP-04 exception allows
`cp <protected> <scratch>/`. The item now matches 04 and adds no new request.

---

# Round 7 (review findings of 2026-09-28 on `00_global_paths.md`)

## R41 — PHI enumeration, price slots, ruled-source protection, Agency arm scope, slug grammar, hook mechanics (blocker/major/minor/nit; amends R26, R35, R36, R37, R38, R39)

Everything below is stated in `00_global_paths.md` as of this round; each bullet names the file
that still has to change.

- **08 WP-M / 03 §3.20 (blocker; PHI file scope, plan §20.3):** `gtm_lists.py phi1-listing` takes
  repeated `--root`, and a new mode `phi1-listing --top-level <dir>` (repeatable) writes
  `S/phi_toplevel_listing.json` with the immediate child names only: one `os.scandir`, the Agency
  text compare on each `entry.name` **before** any `DirEntry` method (Agency entries skipped, not
  recorded), never descends, never opens. P1b runs it on `~/Desktop` and on every folder the
  operator names in WP-M's OtherCompany intake. New subcommand `gtm_lists.py phi-classify
  --listing-sha256 <hex> --review-agent <trust-architect id>`: a `gtm_result.verify_reviewer`-verified
  review bound to the listing sha adds every `denylist` **and** `unknown` entry to
  `phi_denylist.json` as a `path` entry (add-only). 03 §3.20: add the `phi_toplevel_listing.json`
  shape (`{path, kind, covered?}`); exclude it from every backup like `othercompany_listing.json`
  (08 Appendix C item 7). WP-M tests per 00 §1.2 (top-level never descends; Agency never stat'd,
  oracle; Desktop-level `denylist` file denied to a OtherCompany GTM `Read`, RED when the entry is
  removed; `unknown` added too).
- **04 §4.2 rule j / §4.4 path gate (blocker; "OtherCompany read scope"):** in GTM scope with
  `regulated` ∋ `hipaa`, deny (`phi-scope-outside-allowed`, unconditional) any Read/Grep/Glob or
  Bash path operand whose `canon` is not equal to or under `H`, an allowlisted phi1 folder
  (denylist `path` entries still win), `R`, or the system temp roots. B1 tests per 00 §1.2.
- **03 §3.20 / 04 `gtm_hooklib.phi_denylist()` / 07 §7.5 (gap; missing denylist):** replace
  03 §3.20's "fail-closed for paths under `~/Desktop/OtherCompany Files/` only": with any hipaa pack
  registered, a missing/unreadable/unparseable file is **unreadable** — path gate and G-B deny every
  GTM-scope and GTM-seat read target outside the company's `H`, `R` and the temp roots
  (`phi-denylist-unreadable`); G-A denies every GTM-scope `browser_navigate` as `phi-host`; the
  daily run raises one urgent runtime notice `phi_denylist_missing`. Recovery is the agent
  procedure of 00 §1.2 (re-list, trust-architect, `phi-classify`, `phi-denylist add`); no backup
  copy is kept. Test: file deleted with a hipaa pack registered → OtherCompany- and OtherCompanyB-scope
  `Read` of a previously denylisted Desktop path both denied; RED when the branch returns `[]`.
- **02 §2.3 (gap; `hooks_disabled` scope; amends R38):** the `hooks_disabled` refusal applies to
  `write`/`lead`/`repair`-policy commands only — the holds job and operator-marker
  `resume`/`autonomy` included — and **never** to `read`-policy commands (`pause`, `cancel`,
  `card-post`). A1 test: `CSA_DISABLE_HOOKS=1` → `cancel <held action>` succeeds and `pause --system
  gbp` writes its file; RED when the refusal is widened.
- **03 pack schema / 02 §2.4, §2.8 check 9 / 08 Appendix C item 13 (gap; price slots; amends
  R35):** `pricing_source_ref.slots.<id>` = `{pointer, period: "month"|"year"|"one_time", label}`
  and `pricing_source_ref.reviewed_commit` (40 hex); Rule A (4) `price_label_mismatch` (tier
  container = nearest `data-price-tier` ancestor must contain `label`), Rule A (5)
  `price_period_mismatch` (period tokens in the container map to the slot's `period`; a
  `month`/`year` slot needs one, a `one_time` slot none; two slots of different periods in one
  container → `price_slot_malformed`), Rule B (2b) ordered period-token sequence on `-`/`+` lines
  carrying an amount. A1 tests: `/mo`→`/yr` next to a slot; the label swap; `$49/mo`→`$49/yr` in an
  undeclared file → `price_outside_display_paths`; each RED when its check is removed.
- **03 pack schema / 04 §4.2 rules c, n / §4.3 G-W / §4.4 path gate / 02 §2.4, §2.8 (risk; ruled
  source):** new pack key `pricing_source_origin` (list of repo-relative paths; CSA
  `["_Config_Project/docs/domain/opex_and_pricing.html"]`, present before the projection lands).
  In GTM scope and for every GTM seat, deny (`pricing-source-write`, unconditional) Write/Edit,
  rule c write/removal class and rule n `git commit`/`git apply` pathspecs on every registered
  pack's `pricing_source_ref.path` and `pricing_source_origin` entries, whatever `paths.*` or
  `marketing_paths` say; `validate_company` refuses a pack whose `paths.*` or `marketing_paths`
  cover them. act.py at `propose` and `complete --commit`: `c = git log -1 --format=%H <rev> --
  <path> <origins…>` must equal the committed pack's `reviewed_commit`, else exit 3
  `price_source_recent_change`, state unchanged (the chosen check; transcript attribution was
  rejected as fail-open). B1/A1 tests per 00 §0.1.
- **04 §4.2 rule i / §4.4 `agency-boundary` / §4.7 (risk + minor; replaces R37's widening):** the
  sub-agent arm fires only for GTM work: GTM scope; `agent_type ∈ gtm_hooklib.gtm_seat_types()`
  (`DEPARTMENT_SEATS` ∪ every pack's `gtm_seats`); or a sub-agent whose `agent_id` is bound to a
  GTM-tagged `dispatch_tags.jsonl` row (binding key UNVERIFIED, added to probe q; inert until
  recorded). Other sub-agents stay prose-covered (runtime `CLAUDE.md` §1/§2 delegated maintenance).
  §4.7: add an arm forwarding any payload with a non-empty `agent_type` **and** an Agency token
  (`*desktop/agency*`, `*oauth-google-*`, `*/agency*`), casefolded. B1 tests run end-to-end
  through `bash_gate.sh`; an untagged `implement`/`general-purpose` Agency read from `~/.claude` is
  logged only (RED when widened back to every `agent_type`). **Coordinator:** file one tracked
  issue noting the arm's collateral was avoided by scoping, so the runtime owner sees the choice.
- **04 §4.2 wiring `resolve_block` (minor; amends R38):** call `_gtm_bash_block` whenever the
  earlier block is not `unconditional`, **regardless of `_lib.enforcing`**; the unconditional GTM
  block wins. B2 test with the global enforce marker present and the git-state escape variable set
  in the hook process's own environment: `git stash; cp x ~/.claude/.gtm_state/tickets/t/y.json`
  still denied `protected-state-write`.
- **04 §4.2 rule g / rule k / §4.7; 05 §5.3/§5.4 (major; supersedes R39's rule-k bullet):**
  `RULE_K_LITERALS` stays the four literals (`GTM_ALLOW_TRUST_EDIT`, `GTM_HOLDS_JOB`,
  `trust_edit_allow`, `operator_ok`); R39's five additions are withdrawn (argv arguments are not a
  rule-k position). Rule g (`agent-approver-script`) gains: a direct run of the app binary (verb
  path, casefolded, ending in `gtmapprover.app/contents/macos/gtmapprover`) and `open` with
  `-a GTMApprover`, `-b <bundle id>` or a `GTMApprover.app` operand; §4.7 forwards `*gtmapprover*`.
  04's parenthetical "rule k's literals do not match the hyphenated … modes" stays as written (it
  is now consistent with 00). The `gtm_approve.sh` re-show form stays denied to
  agents (rule g "any mode"; 00 §1.4 now says so). B1 tests per 00 §1.4, each RED when its rule-g
  clause is removed; `grep -rn operator-ok tools/gtm` and `grep -rn GTMApprover tools/gtm` allowed.
  R39's NSAlert bullet for 05 is unchanged.
- **04 §4.2 rule m / 06 §6.6 / 03 §3.22 (nit; secret sink port):** `system_names.SECRET_SINK_PORT
  = 47823`; `GTM_SECRET_SINK_PORT` honored only when `gtm_env.test_mode(environ)[0]`; rule m's
  denied inline assignments (commands naming `tools/gtm/`) add `GTM_SECRET_SINK_PORT`. Test:
  outside test mode the env value is ignored.
- **02 §2.4 `purge-untrusted` / 07 §7.5 (nit; `_unknown` spool):** stop deleting unattributable
  `S/lead_spool/_unknown/` files by age; add `--include-unknown` (explicit delete, one `warn`
  notice per file); the daily run and `purge-untrusted` raise one urgent runtime notice per
  `_unknown` file older than 24 h asking for `lead-append --company <slug> --file <it>`; a
  successful replay deletes the file. A1 tests per 00 §1.2.
- **02 §2.11 (nit; card route):** add the A2 test: an approved card with subject `authorize <money
  action id>` → `record-external --kind approval` exits 3 `card_approval_money_forbidden`, nothing
  appended (RED when the money check is removed). 00 §1.4 now enumerates every card-gated command
  (incl. `revert --child … --approval <card>` for non-money children and `record-external --kind
  approval` for `awaiting_card`) and states that a card never authorizes `$`.
- **07 §7.3 holds plist (minor):** `ProgramArguments` starts with exactly `["/bin/bash", "<real
  root>/" + HOLDS_RUNNER_RELPATH, "holds"]`; the K test asserts that full prefix.
- **08 Appendix C item 14 (coordinator; extends R16/R23/R31/R36):**
  - `system_names.SLUG_RE = ^[a-z][a-z0-9-]{1,31}$` (the committed grammar; 00 §0.3 narrowed to
    match, not widened); `company.py` imports it; `register`'s committed SLUG_RE refusal prints
    `error: bad_slug: <slug>`; coordinator test `scripts/repo_manifest.SLUG_RE.pattern ==
    system_names.SLUG_RE.pattern`. `CYCLE_ID_RE`, the flat-cancel regex and the card-id example
    (60 characters, 32-char slug) follow (03 §3.11/§3.12/§3.22, 07 §7.2 `validate_run.py`).
  - `~user` refusal: `gtm_env.real_expand` raises `TildeUserForm`; input rule (5),
    `resolve_home()`/`_entry_root_path()`, `register` (`agency_home: tilde_user_form`) and
    `validate_company` refuse a leading `~` that is neither `~` nor `~/…`. Coordinator test: a
    registry root `~<user>/Desktop/OtherApp` outside test mode (`real_home` monkeypatched) → refused,
    oracle record empty; RED without the fix.
  - `gtm_env.is_ancestor(a, b)` is the one ancestor test for `gtm_slugs()` and `register` (d);
    test `register x --root /` → `ancestor_of_agency`.
  - `company.write_identity_index()` itself raises `CompanyError("repo_registry_slugs_missing")`
    before writing; `company.py index` → exit 1; `gtm_lists.py` → exit 3, list file and both index
    files unchanged (WP-M test). `validate --all`'s line uses `str(company.gtm_registry_path())`.
  - Harvest (corrects R36's site): the Agency text compare goes into `_read_transcript_cwd` before
    L169 (sentinel `AGENCY_CWD` = drop, distinct from `None` = keep), before `attribute_company`
    L636, and before the Write/Edit attribution resolve at L1039 (relative `file_path` joined to the
    record's text cwd). Item 28's fixture adds a transcript with `cwd` under a GTM home and a
    `Write` `file_path` under `A` (no touch, no attribution; RED when the L1039 guard is removed),
    and the RED control targets `_read_transcript_cwd`.
  - The four resolved `sys.path` inserts (`activity_log.py` L53, `harvest_tool_trail.py` L45,
    `backup_state.py` L26, `company._pack_system_set` L913-915) become the unresolved
    `os.path.abspath(__file__)` form with remove-then-insert-at-0; B2's harness imports `company`,
    `gtm_env`, `system_names` first and asserts that order.
- **08 Appendix C item 7 (nit):** restore order is (1), (2), (3), the committed prefix strip,
  (3b) the runtime hardlink refusal (exit 1), (4), (5); (5) reads member names snapshotted before
  the strip. Tests per 00 §0.3.
- **R26 rescope (gap):** the P1b design issue's acceptance criteria name all five touchpoints of
  00 §0.1 "Follow-up" (1): (i) a `website_static` target-repo pack key distinct from `H`,
  validated text-only; (ii) act.py checks 1/9 for exactly that root and the listed paths; (iii)
  `validate_company`'s `marketing_paths` compare against `A` relaxed for that pack only; (iv) the
  rule i / path-gate carve-out (Read of listed paths + `git -C <A> add|commit -- <listed paths>`);
  (v) oracle positive controls proving nothing else under `A` is touched. 08 Appendix C item 15's
  condition (a) requires all five landed with a clean trust-architect review.
- **08 Appendix B:** index the DECIDED-HERE items now listed in the 00 header ((iv) `autonomy
  --card` withdrawal, (v) hipaa read scope and missing-denylist fail-closed, (vi) top-level PHI
  enumeration), plus the ruled-source write protection and `reviewed_commit` check, the `_unknown`
  spool rule and the secret-sink port constant.
- **§1.5 item 5 (test isolation, every WP):** git test env adds `GIT_CONFIG_GLOBAL=/dev/null` and
  removes `XDG_CONFIG_HOME`.

## R42 — Agency session files, narrowed PHI read roots, top-level PHI precondition, signed reverts, seat union, fast path, hook mechanics, registry API, backup details (blocker/major/gap/minor; amends R16, R41)

Everything below is already stated in `00_global_paths.md` as of this round; each bullet names the
file that still has to change and cites the `00` heading it depends on.

- **04 §4.2 rule i and §4.4 path gate `agency-boundary` (blocker; 00 §0.4 "Agency session
  files"):** for exactly the calls the §0.4 Agency arm covers (GTM scope; `agent_type` ∈
  `gtm_seat_types()`; a GTM-tagged dispatch once probe q passes) with a cwd not under `A`, deny
  unconditionally, reason `agency-boundary`, by text compare only (`gtm_env.norm`/`is_under`, no
  stat): (1) any Read/Grep/Glob/Edit/Write/WebFetch target or Bash path operand equal to or under
  `R/projects/<c>` or `T/claude-<x>/<c>` (`T` ∈ `/private/tmp`, `/tmp`,
  `norm_text(tempfile.gettempdir())`) with `project_dirs.is_agency_project_dir(c)`; (2) any
  Grep/Glob, and any Bash recursive search (`grep`/`egrep`/`fgrep` `-r|-R|--recursive|
  --dereference-recursive|-d recurse` incl. clusters, `rg`, `ag`, `find`, `fd`, `tree`, `du`,
  `ls -R`, `tar` create), whose root (Grep/Glob `path` or Bash operand, default the payload `cwd`)
  is equal to or an ancestor of `R/projects` or of a `T`, or is exactly `T/claude-<x>`. B1 tests
  per 00 §0.4 (OtherCompanyB-scope Read of `R/projects/<P_A>/x.jsonl` and of an Agency scratchpad
  file denied; OtherCompany-scope Grep with `path` `~/.claude` and a `gtm-analyst` `grep -r x
  ~/.claude/projects` outside GTM scope denied; a Read of the home's own project dir and a Grep of
  `R/tools/gtm` not denied by this arm), each RED when its clause is removed.
- **04 §4 `gtm_hooklib` (blocker/gap; 00 §1.2 "The fail-closed read roots", "Top-level PHI
  classification is a precondition"):** add `fail_closed_read_roots(payload, environ) ->
  list[str]` (= `H_eff` ∪ `R/tools/gtm`, `R/knowledge`, `R/skills/gtm`,
  `R/plans/gtm_autonomous_department_plan.md` ∪ the own-session roots: `R/projects/<c>` matched by
  `project_dirs.matches_project_dir_prefix(c, project_dir_name(H_eff))`, the payload
  `transcript_path`'s project dir, and the payload's own `scratchpad_dir` in its documented form —
  each non-Agency; `H_eff` = the session company's `H`, or for a GTM seat outside GTM scope the
  bound dispatch tag's company, else none) and `phi_toplevel_classified() -> bool`. Never `R`,
  `R/projects`, `S`, `R/.enforcement` or a temp root as a whole.
- **04 §4.2 rule j and §4.4 (blocker; 00 §1.2 "OtherCompany read scope"; replaces R41's allowed-root
  list):** hipaa GTM scope denies (`phi-scope-outside-allowed`) every target not under
  `fail_closed_read_roots` (with `H_eff = H`) or an allowlisted OtherCompany folder (denylist `path`
  entries still win). B1 tests per 00 §1.2 (Grep at `~/.claude` denied; another session's
  scratchpad denied, own scratchpad allowed; another non-GTM session's transcript denied).
- **04 §4.2 rule j, §4.4, §4.1 G-A (major/gap; 00 §1.2 "Top-level PHI classification is a
  precondition", "`phi_denylist.json` missing or unparseable"):** in **every** GTM scope and for
  every GTM seat, hipaa pack or not: while `phi_toplevel_classified()` is False, deny read targets
  outside `fail_closed_read_roots` (`phi-toplevel-unclassified`); while `phi_denylist.json` is
  absent, unreadable, unparseable or schema-invalid, deny them too (`phi-denylist-unreadable`), G-A
  restricts as 03 §3.20 "Hook readers" (1), and G-B denies any command naming a network host (the
  tokens rule j's host check extracts, through `host_of`) outside that same G-A allowed set
  (`phi-denylist-unreadable`). A GTM seat with no session company uses its bound dispatch tag's
  company, else no home and no allowed host. Tests per 00 §1.2, each RED when scoped back to hipaa
  packs.
- **03 §3.20 (major; 00 §1.2 "Listing shapes", `phi-denylist add`, `phi-classify`):** (a) replace
  `othercompany_listing.json`'s `{listed_at, root, entries: [{path, kind: dir|file, size}]}` and its
  `os.walk` wording with the `gtm.phi1_listing.v2` shape (`roots` list, recursive `os.scandir`,
  `kind` ∈ dir/file/symlink, `size` only on files via `stat(follow_symlinks=False)`, `denylisted`
  only when true); (b) add `S/phi_toplevel_listing.json` (`gtm.phi_toplevel_listing.v1`, `covered`
  only when true) and `S/phi_toplevel_classification.json` (`gtm.phi_toplevel_classification.v1`:
  `listing_sha256`, `classified_at`, `review_agent_id`, `counts`); (c) the `phi-classify` review
  block: `reviews[]` one entry `{action_id: "phi1_toplevel:<sha256>", after_digest:
  "sha256:<sha256>", lane: "hipaa", verdict: "pass", lines: [{check: "entry:<abs path>", result:
  "pass"|"denylist"|"unknown", note}]}`, verified with `verify_reviewer(agent_id,
  {"trust-architect"}, "phi1_toplevel:<sha>", "sha256:<sha>")`; a missing line = `unknown`; (d)
  record `gtm_lists.py`'s complete grammar — `phi-denylist add (--path | --host [--agency-app] |
  --host-suffix | --url) --why W [--applies-to …]` (`--applies-to` only with `--host --agency-app`,
  else `phi_denylist_scope_invalid`) and `agency-gsm-project add <id> --why W` — and the storage
  mapping of 00 §1.2 (paths as strings; `why` only in `notes[]` `{entry, why, source}`); (e) "Hook
  readers" item (2): use `fail_closed_read_roots` instead of `H`, `R/tools/gtm`,
  `R/knowledge/marketing_kb`; and replace "for other packs an absent file is read as empty" with
  "absent = unreadable for every pack" (the launchers refuse to start while it is).
- **07 §7.2 `run_gtm_job.sh` and §7.6 `gtm_session.sh` (major; 00 §1.2 "Top-level PHI
  classification is a precondition"):** refuse to start, exit 64, stderr `phi_toplevel_unclassified`
  while `gtm_hooklib.phi_toplevel_classified()` is False, and `phi_denylist_unreadable` while
  `phi_denylist.json` is absent/unreadable/schema-invalid — for every company. K tests: each state
  → 64 with that line (RED when the check is limited to hipaa packs); both good → not refused.
- **08 WP-M, P1 ordering, and plan §20.1 checklist (major):** `phi1-listing --top-level ~/Desktop`
  (plus every operator-named folder; WP-M's intake question moves to P1), trust-architect
  `phi-classify`, and `phi_denylist.json` seeding run at **P1, before the first GTM session of any
  company**; `--root` and `phi1-allowlist` stay at P1b. WP-M tests per 00 §1.2 (no hipaa pack, no
  classification → OtherCompanyB-scope Read of a Desktop fixture denied and `gtm_session.sh` exits 64).
- **04 §4.7 `bash_gate.sh` (major; 00 §0.4 "Fast path"; supersedes R41's Agency-token list):**
  describe the committed script accurately (one `case` arm: `*git*`, `*gcloud*`, the escape-var
  literal, the `gh issue close|create`, `gh_issue.sh create`, `gh project`/`--project` shapes). B2
  adds: (a) arm 2b's regex widened from `DEPARTMENT_SEATS` to every `gtm_seat_types()` member (the
  P2 parity test compares against that union); (b) one arm: `shopt -s nocasematch`; forward when
  the payload has a non-empty `"agent_type"` value **and** matches `*agency*` or
  `*oauth-google-*`; `shopt -u nocasematch` (bash 3.2-safe; no `${x,,}`). 04 §4.2 rule i: a glob
  operand whose literal prefix is an ancestor of `A` and whose next segment `fnmatchcase`-matches
  `agency` (casefolded) names `A`. B1 end-to-end tests: `cd ~/Desktop && ls Agency` and `ls
  ~/Desktop/Agen*` from a `gtm-analyst` payload denied; the same `cd … ls Agency` from an untagged
  `research-scout` payload reaches python (RED with `*desktop/agency*`) and is only logged.
- **04 §4 `gtm_hooklib.gtm_seat_types()` (major; 00 §0.4 test (2)):** = `GTM_SEATS ∪
  DEPARTMENT_SEATS` as returned by `system_names.seat_sets()` (08 Appendix C item 104's one
  definition); packs contribute nothing (they have no seat key). `research-scout` is covered only
  by a GTM dispatch tag (test (3)). B1 test: a `gtm-analyst` Read of `<A>/x` from a CSA cwd outside
  GTM scope denied `agency-boundary` end-to-end through the path gate (RED when the union omits
  `GTM_SEATS`).
- **04 §4.2 wiring / §4.9 `pretooluse_bash` bullet (major; 00 §0.4 "Mechanism"):** the
  `_gtm_bash_block` call made after an earlier non-unconditional block is wrapped in its own
  `try/except Exception` that logs `gate-fault` and returns the earlier block unchanged; with no
  earlier block, G-B runs after gates 1/1b/1c and **before gate 2** (so before 3/3b/3c/4's index
  reads and claims), and a G-B exception there is handled by G-B's own fail mode, never by the
  outer `except Exception: return None, {}`. B2 tests: `_gtm_bash_block` monkeypatched to raise →
  `git stash` still denied; a rule-n-denied GTM-scope commit leaves the file-claims ledger and the
  commit-mutex token untouched.
- **04 §4.2/§4.3 (minor; 00 §1.2 registry paragraph):** add `R/knowledge/gtm_company_registry.json`
  and `R/knowledge/repo_registry.json` to the path gate's and G-W's Write/Edit deny, rule c's
  write/removal targets and rule n's pathspec check, in GTM scope and for every GTM seat,
  unconditionally, reason `gtm-registry-write`. B1 tests: a GTM-scope `Edit` and a `sed -i` of
  the registry denied (RED when removed); the same from a non-GTM session not denied by this rule.
- **02 §2.1 `gtm_env` row (major; 00 §1.1 "`gtm_env` exports — the one table"):** replace the
  restated export list with a citation of that table; signatures are `agency_root(environ:
  Mapping[str, str] = os.environ) -> Path` and `phi1_root(environ: … = os.environ) -> Path`, test
  mode judged on `environ` and `HOME` read from `environ` (empty = unset → `real_home()`), never
  `Path.home()`; `TRUSTED_PYTHON`'s value stays decided by 05 §5.5 "Interpreter pin"; `gtm_env`
  defines `__all__` equal to the table.
- **02 §2.2b `store.verify_chain` (major/minor; 00 §0.3 cases 0 and 5):** add case 0 (anchor
  present but unreadable, not JSON, wrong shape — missing/extra key, non-int or negative `seq`,
  `line_sha256` not 64 lowercase hex, bad `ts` → `chain_truncated`, never absent); replace
  "read-only" with "read-only unless `locked=True`, where case 5 re-anchors to the last line";
  `locked=False` returns `(True, None)` without writing. A1 tests per 00 §0.3.
- **02 §2.4 `revert`, §2.5, §2.11; 03 §3.7 case (v); 05 §5.5 step 3b; 07 §7.1 (major; 00 §1.4
  "The card route"; header item (vii)):** routes (4) and (5)-`shared` of step 1 send a non-money
  child to `awaiting_approval` with the amount-less request signed over its `after_digest` (listing
  `failing_checks`, `revert_approval` notice) in every pause state, never `awaiting_card`; step 2
  form (b) (`--approval <card_id>`) is withdrawn — a card id → exit 3 `revert_approval_mismatch`;
  the `authorize` row's A1 example of a non-money `shared` revert child "parked in `awaiting_card`
  (no pause)" becomes "parked in `awaiting_approval`"; case (v) and step 3b cover every non-money
  revert child awaiting a decision, not only one under a pause. `OPERATOR_OK_COMMANDS` is
  unchanged. A2 tests per 00 §1.4.
- **08 Appendix C item 14 (blocker/major/minor; 00 §0.1 "Registry inputs" (2), "`register`
  refuses …", F9):** (a) add public `company.require_repo_registry_slugs() -> None` (raises
  `CompanyError("repo_registry_slugs_missing")` for a missing registry file or a missing/non-list
  key); `write_identity_index()` calls it first; `validate --all` reports a **missing** file the same
  way (the `INVALID <absolute registry path>: repo_registry_slugs_missing` line, a stated grammar
  exception); missing stays "no slugs" for `gtm_slugs()`/`resolve_home()` only; committed tests
  that index with no registry file create it. Coordinator test: delete the file → `company.py index`
  exits 1, both index files byte-identical. (b) `register` order: slug refusals → `tilde_user_form`
  on the raw arg → `real_expand` (`expanduser` in test mode) → charset → walk → checks;
  `cmd_register` prints the walked `F`. (c) R16's `_matching_project_dirs` rewrite also switches its
  root to `company.claude_dir() / "projects"`.
- **08 Appendix C item 7 (major/minor; 00 §0.3 IMP-08, §1.3 "The exclusion API"):** backup: log
  present + anchor absent → exit 3 `anchor_missing`, no archive; neither → skip both; snapshot
  `TarInfo` `size`, `mtime` = `st_mtime`, `mode` = `0o600` from an `fstat` under the lock. Restore:
  step (0) `--restore` without `--to` → exit 2 listed first; check (5) uses `effective_slug`, and a
  `None` `effective_slug` with the log arcname present → exit 3 `anchor_not_in_archive`. Add
  `company.backup_excludes(slug, pack) -> list[str]` and one combined `filter=` on every `tar.add`
  (exclusions + the two snapshot arcnames). Tests per 00 §0.3/§1.3.
- **Coordinator, before B1 (minor; 00 §0.2):** apply `requests/05_approver.md` R12 to 04_hooks.md
  (verification through `/usr/bin/openssl` and `ed25519_verify.py` only; no line naming the
  `cryptography` package without "retired", "never imported" or "stub") and run the §0.2
  contract-consistency check green.
- **B2 test harness (major; 00 §1.1 "Scripts are different"):** the tmp tree **copies** every
  `*.py` under `tools/gtm` (excluding `tests/`) and every `*.py` plus `bash_gate.sh` under
  `hooks/`, never symlinks; subprocess tests run `python3 -v <tmp>/tools/gtm/backup_state.py
  --help` and the path-gate entry point from the tmp tree and assert from the import trace that
  `company`, `gtm_env`, `system_names`, `gtm_hooklib` load from the tmp tree only; a guard test
  asserts no symlink under the tmp code dirs. Record this in 04 §4.2's B2 wiring text and 08 WP-B2.
- **02 §2.8 check 9 / 08 Appendix C item 13 (minor; 00 §0.1 price rules "Decoding", "Rule B"):**
  `gtmlib.checks.decoded_text(image: str, ext: str, *, attrs: bool) -> str`; HTML-family =
  `.html .htm .xhtml .njk .hbs .md .svg`; Rule A (1)/(4)/(5) use `attrs=False`, the outside-slot
  token compare and Rule B (1) `attrs=True`; Rule B applies to HTML-family ∪ `.txt .json .csv`
  only, created files have an empty pre-image and deleted files an empty post-image, a
  non-UTF-8 allowlisted file → `price_outside_display_paths`; prices inside images are a stated
  residual. A1 tests: `class="monthly-toggle"` on a `year` slot's container is not a
  `price_period_mismatch` (RED when attributes are included); a new undeclared page containing
  `$49` → `price_outside_display_paths`.
- **08 Appendix B (gap; 00 header):** index the header's items (v) (narrowed hipaa read roots;
  missing denylist fails closed for every GTM scope), (vi) (top-level classification as a P1
  launcher/hook precondition), (vii) (every `revert --approval` signed; a **narrowing**) and (viii)
  (`_unknown` spool never purged by age; a **loosening**, with its reason), plus the fail-closed
  read roots, the Agency session files arm, the copy-not-symlink test tree, the registry
  prose-only statement and the price-decoding scope.

## R43 — kernel path aliases (amended wave1d/wave1e: `.vol`, `resolve_home` walk, `claude_dir` HOME branch), `resolve_home`/`claude_dir` Agency binding, by-name denylist fate, test retrofit, `real_expand_raw`, "GTM seat" definition, `_unknown` purge, lead spool-before-delete, `phi-classify` refusals (blocker/major; wave1c; amends R41, R42)

Everything below is already stated in `00_global_paths.md` as of round wave1c; each bullet names the
file that still has to change and cites the `00` heading it depends on.

- **02 §2.1 `gtm_env` row and 08 Appendix C item 14 (blocker; 00 §0.1 "The one path-compare
  implementation", §1.1 "`gtm_env` exports"):** the export table gains `canon_aliases(t: str) ->
  str` and `real_expand_raw(s: str) -> str`; `norm_text(s)` = `canon_aliases(os.path.normpath(s).casefold())`,
  where `canon_aliases` repeats until a pass changes nothing: collapse a leading `/` run to one
  `/`; strip a leading `/.nofollow` component; strip a leading `/.resolve/<digits>`
  (`^/\.resolve/\d+(?=/|$)`); `strip_firmlink`; **and (amended wave1d/wave1e) the terminal arm (e):
  `t == "/.vol"` or `t.startswith("/.vol/")` returns `gtm_env.VOLFS_SENTINEL`** (a new export — the
  00 §1.1 table now lists `VOLFS_SENTINEL`, `gtm_tmp_root` and `git_show_head` too), which every
  consumer treats as an unconditional Agency match. 02 §2.1 cites the 00 §1.1 table instead of
  restating it (R42 already asks this; the table changed again — 02 §2.1 now says so, wave1e). A1
  tests per 00 §0.1: `//…`, `/.nofollow/…`, `/.resolve/1/…`, a stacked form, `/.nofollowx/a`
  unchanged, `/.vol/1/2/x` → the sentinel and `/.volx/a` unchanged; `gtm_slugs()` excludes each
  alias form of `A`, the `/.vol/<dev>/<ino>` form included.
- **08 Appendix C item 14, `register` (blocker/major; 00 §0.1 "`register` refuses a home…"):**
  step (3) uses `gtm_env.real_expand_raw` (tilde only, no `normpath`) outside test mode; the walk
  refuses a component `.nofollow`, `.resolve` or `.vol` (casefolded) taken while `P == "/"` with new
  reason `kernel_path_alias` (added to the stderr reason set `error: agency_home: <reason>`). Tests:
  `--root /.nofollow<tmp HOME>/Desktop/OtherApp` → **`kernel_path_alias`** (corrected wave1d, 00
  §0.1: the walk's per-component refusal fires on the first component, before `C` can be under
  `norm(A)`; the former `registry_path_in_agency` expectation was wrong) with an empty oracle
  record; `--root /.nofollow<tmp HOME>/Desktop/sub` → `kernel_path_alias`; `--root
  /.vol/<dev>/<ino of a tmp Agency dir>` → `kernel_path_alias`; outside test mode
  (`test_mode` monkeypatched to `(False, [])`) `<tmp>/link/../Agency` → `symlink_into_agency`
  (RED when step (3) normpaths).
- **08 Appendix C item 14, `resolve_home`/`_entry_root_path` (blocker; 00 §0.1 "`resolve_home()`
  is bound to the exclusion"):** after the (5) checks and before any `expanduser().resolve()`,
  **run `register`'s own component walk on `root` (amended wave1d: a bare text compare misses a
  symlink spelling such as `/Volumes/Macintosh HD/…`) and apply checks (a)–(d) to both the walked
  text and the argument text**, raising `CompanyError(f"… entry for {slug!r} agency_home:
  <reason>")` with the full `register` reason set (`registry_path_in_agency`,
  `symlink_into_agency`, `symlink_limit`, `agency_project_dir`, `ancestor_of_agency`,
  `kernel_path_alias`). Not narrowed to `gtm_slugs()` membership (reason in 00). Test under the
  oracle: GTM registry `foo` → `~/Desktop/OtherApp` (`registry_path_in_agency`), `~/Desktop`
  (`ancestor_of_agency`), `/.nofollow<tmp HOME>/Desktop/OtherApp` (**`kernel_path_alias`**, corrected
  wave1e), `/.vol/<dev>/<ino of tmp A>` (`kernel_path_alias`) and the tmp `Macintosh HD`-style
  symlink (`symlink_into_agency`) → `resolve_home("foo")` and `load_pack("foo")` raise, record
  empty; RED when removed.
- **08 Appendix C item 14, by-name denylist and caller switch (major; 00 §0.1 "Registered GTM
  company"):** keep `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` and `_gtm_eligible_repo_registry_repos()`
  as a second layer: `gtm_slugs()` reads allowlisted repo slugs through the eligible set and applies
  the text exclusion; `resolve_home()` keeps the eligible set plus the new text exclusion;
  `_register_gtm_company_locked` and the duplicate checks of `gtm_slugs()` (4), `validate --all`
  and `cmd_index` keep the unfiltered `_repo_registry_repos()` (keys and root text only). Switch
  `_all_packs`, `build_identity_index`, `build_account_id_index`, `cmd_validate --all`'s slug list
  and `harvest_tool_trail._registered_homes` from `registered_slugs()` to `gtm_slugs()`;
  `registered_slugs()` stays unchanged with no Wave-2 caller. Correct any text elsewhere that says
  `registered_slugs()` returns `agency` (it returns `['exampleapp']` on the baseline).
- **08 Appendix C items 14 and 28, test retrofit (major; 00 §0.1 "Registry inputs" (2) "Test
  retrofit"):** add `gtm_fixtures.write_gtm_registry(claude_dir: Path, *, repo_registry_slugs:
  list[str], companies: dict | None = None) -> Path` (item 28) and, in item 14's scope, give every
  test file that registers a company only through `repo_registry.json` and depends on enumeration
  or indexing a `gtm_company_registry.json` with `repo_registry_slugs` (or move its slug to the GTM
  registry). Known sites: `test_host_systems.py`, `test_host_systems_validation.py`,
  `test_company_pack.py` (incl. its `validate --all` subprocess), `test_flush_many_scalability.py`,
  `test_harvest_tool_trail.py` (two `write_identity_index()` sites), `test_lock_scope_not_blocking.py`,
  `test_harvest_multiprocess.py`, `test_nap_never_triggers_capture.py`,
  `test_gtm_company_registry.py` (`validate --all` subprocesses), `test_corrupt_registry_error_handling.py`;
  run the whole `tools/gtm/tests/` suite before and after and fix any further lost-company red the
  same way, never by weakening a refusal. Update company.py's comment above
  `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` in the same change with 00's recorded reason for adopting
  the opt-in allowlist.
- **08 Appendix C item 14, `claude_dir()` (major; 00 §1.1 "`claude_dir()` refuses an Agency
  `CLAUDE_DIR`"):** when `CLAUDE_DIR` is non-empty, `v = os.path.expanduser(value)`; before the
  `.resolve()` raise `CompanyError("CLAUDE_DIR agency_home: <reason>")` when `v` is not absolute
  (`claude_dir_not_absolute`), `norm_text(v)` is `VOLFS_SENTINEL` (`kernel_path_alias`), or
  `norm_text(v)` is equal to/under or a strict ancestor of the `HOME`-derived Agency root or
  `real_agency_root()`. **HOME branch (added wave1d, corrected wave1e — the wave1d form compared
  `HOME` itself and was a tautology, raising `ancestor_of_agency` on every production call):** when
  `CLAUDE_DIR` is empty/unset, `c = norm_text((HOME or real_home()) + "/.claude")` is refused
  before `Path.home()/.claude` is built — `VOLFS_SENTINEL` → `kernel_path_alias`, `is_under(c,
  norm_text(str(real_agency_root())))` → `registry_path_in_agency`, `is_ancestor(c, …)` →
  `ancestor_of_agency` — as `CompanyError("HOME agency_home: <reason>")`. 02 §2.3/§2.4 exit list: every tool maps it to
  exit 3 `claude_dir_in_agency`; 04 §4 fail-mode text: a hook that gets it applies its own fail
  mode. Oracle test: `CLAUDE_DIR=<tmp A>/x`, `/.nofollow<tmp A>/x`, `/.vol/<dev>/<ino of tmp A>/x`
  and `<tmp HOME>/Desktop` each raise with an empty record; with `CLAUDE_DIR` unset and
  `real_home()` monkeypatched to the tmp home, `HOME=<tmp A>` raises `registry_path_in_agency`, while
  `HOME` equal to `real_home()` (and `HOME` unset) returns `<tmp home>/.claude` without raising (the
  control that goes RED under the wave1d tautology). 04 §4's stdlib `_claude_dir` copy mirrors both
  refusals (wave1e).
- **04 §4 (seat constants / every PHI and write-protection rule) (blocker; 00 §0.4 "GTM seat"):**
  "GTM seat" = `system_names.GTM_SEATS` (∪ `model_policy.json` `gtm_seats`) only. The
  seat-conditioned arms of `pricing-source-write`, `gtm-registry-write` (R42),
  `phi-toplevel-unclassified`, `phi-denylist-unreadable` and the fail-closed read roots' `H_eff`
  rule test `agent_type in GTM_SEATS` outside GTM scope — never `gtm_seat_types()`; only the
  Agency arm (§0.4 test (2), rule i, path-gate `agency-boundary`, fast-path arm 2b) keeps
  `gtm_seat_types()`. B1 test: a `content-strategist` Read of a CSA-repo file from a non-GTM CSA
  session with no classification file (and, separately, with `phi_denylist.json` deleted) is not
  denied, while `gtm-analyst` is denied `phi-toplevel-unclassified` / `phi-denylist-unreadable`;
  RED when `DEPARTMENT_SEATS` leak into the PHI arms. 03 §3.20 "Hook readers" and 08 Appendix B
  use the same term.
- **02 §2.4 `purge-untrusted` and 07 §7.1/§7.5 (major; 00 §1.2 "`_unknown`"; withdraws R41's
  request that `purge-untrusted` stop deleting unattributable spool files by age, and R42's
  "loosening" wording for header item (viii)):** `S/lead_spool/_unknown/` files are purged on
  `--older-than-days` (default 30) exactly like hipaa slug spools, one `warn` notice per deleted
  unreplayed file; an urgent runtime notice per file from 24 hours onward (deduplicated per file
  name); earlier deletion only after a successful replay or `--include-unknown`. A1 test: a
  31-day-old `_unknown` file is purged with a notice (RED when it survives); a 25-hour-old one
  survives with one urgent notice. 08 Appendix B indexes header item (viii) as a **narrowing**; no
  loosening remains in 00's header.
- **02 §2.4 `lead-append` and 03 §3.14 (major; 00 §1.3 "`lead-append` deletes its input only once
  the lead is durably recorded"):** for a hipaa pack, `--file` input under `G/drafts/` is deleted
  only after a chain line, a `lead_fallback.jsonl` line, or a `S/lead_spool/<slug>/` file holds it.
  On any post-read refusal other than `hooks_disabled` (which already spools) — exit 12 lock
  timeout, exit 3 `id_space_exhausted`, every other — first spool the raw bytes (same stdlib
  writer, exclusive create, 0600, hipaa exclusion/purge), add `spooled: "<file name>"` to the result
  JSON (exit code unchanged), then delete the draft; if the spool write fails keep the draft and
  write one urgent notice (07 §7.1). A1 test: a forced `ST/actions.lock` timeout leaves exactly
  one spool file with the input bytes and no draft (RED when the draft is deleted without
  spooling). `propose --file` and `card-post --file` are unchanged.
- **03 §3.20 and 08 WP-M `phi-classify` (major; 00 §1.2 `gtm_lists.py phi-classify`):** an entry
  with no review line → exit 3 `review_incomplete` (nothing written; re-dispatch), never
  `unknown`; an entry equal to or an ancestor of any `gtm_slugs()` home root, `R` or `real_root()`
  (text compare) must carry an explicit `pass` line, else exit 3 `review_incomplete`, nothing
  written, plus one urgent runtime notice when its line was `denylist`; only explicit
  `denylist`/`unknown` lines add `path` entries. Add `review_incomplete` to the `gtm_lists.py` exit-3
  code list. WP-M tests per 00 §1.2 (CSA-home line omitted → refused, no write; `denylist` on a
  GTM-home ancestor → refused and noticed).
- **08 Appendix B (gap; 00 header and every "DECIDED (wave1c)" mark):** index `canon_aliases`,
  the `kernel_path_alias` walk refusal, `real_expand_raw`, the `resolve_home()` binding and its
  non-membership decision, the kept by-name layer, the test retrofit and its reason, the
  `claude_dir()` refusal, the "GTM seat" definition, header item (viii) as a narrowing, the lead
  spool-before-delete rule and the two `phi-classify` refusals.

## R44 — `04_hooks.md` §4 (`canon`, `path_is_or_under`, stdlib copies), §4.1 rule 3b, §4.2 rule i, §4.4 rule 1; `08_seats_wps.md` Appendix C item 14 (blocker/major; wave1e; extends R43)

Filed wave1e (finding wave1d-M2: the wave1d/wave1e changes to 00 were not propagated). **Applied
directly in 04 and 08 in the same pass** (every contract file was editable this round); this entry
records what changed so a later reviewer can check it.

- **04 §4 `canon` and every Agency compare (blocker; 00 §0.1 arm (e)):** `canon` returns
  `gtm_env.VOLFS_SENTINEL` for any `/.vol` spelling (step (2b), no filesystem call; a symlink target
  that re-norms to it returns it too); `path_is_or_under`/`path_is_ancestor_of` raise
  `KernelPathAlias` when either argument is the sentinel, and every rule maps that to a DENY with its
  own reason, never to the allow-on-internal-exception path (so no allow arm can admit a `/.vol`
  path); the path gate rule 1, G-B rule i and G-A rule 3b's `file://` arm test `canon(x) ==
  VOLFS_SENTINEL` first and deny `agency-boundary`. 04's gate-gtm stdlib copies: `_norm_text` now
  runs the full `canon_aliases` loop incl. `/.vol` (it stripped only the firmlink, so the P2 parity
  test over 00 §0.1's alias cases would have failed), `_gtm_tmp_root()` is added, and
  `_claude_dir` mirrors both of `claude_dir()`'s refusals. B1 tests as listed beside
  `path_is_or_under` in 04 §4.
- **08 Appendix C item 14 (major; 00 §0.1, §1.1):** the coordinator change also lands
  `canon_aliases` with arm (e) and `VOLFS_SENTINEL`; `register`'s walk refusing `.vol` as well as
  `.nofollow`/`.resolve` (`kernel_path_alias`); `resolve_home()`/`_entry_root_path()` running
  `register`'s walk (R43, amended); `claude_dir()`'s two text-only refusals (the `HOME` branch on the
  candidate `HOME/.claude` against `real_agency_root()` only, wave1e); and the `gtm_env` exports
  `gtm_tmp_root` and `git_show_head` (00 §1.1 table). Tests as in 00 §0.1/§1.1. 08 item 14 now
  carries a "wave1c–wave1e additions" paragraph listing exactly these.
