# GTM Wave-2 interface contracts — §4 Hook contracts

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md).

## 4. Hook contracts

Shared helper: **`hooks/gtm_hooklib.py`** (WP-B1 owns; B2's `gtm_task_gate.py` imports it). It is a
library (never calls `emit_pretooluse_deny`), stdlib + `_lib` + `tools/gtm/company.py`,
`tools/gtm/system_names.py` and **`tools/gtm/gtm_env.py`** only (IMP-22: nothing in the API below needs `approval_sig` or
`gtm_pricing`, so hooklib imports neither; `gtm_env` is stdlib-only and in 05_approver.md §5.5's
preventive, write-protected pre-check set, and 00_global_paths.md §0.1/§1.1 require hooks to take
the clock, the Agency root and the real-state refusal from it) — **not** `ai_budget` (none of its functions need it;
no hook imports `ai_budget` or `approval_sig` in-process at all: gate-gtm, B2, runs both as isolated
subprocesses and imports only `dispatch_tags` in-process, §4.6 F-trust, 05_approver.md §5.5 step 0,
so B1's library and tests never depend on a B2 file). Every
"every pack"/"other packs" helper enumerates `company.gtm_slugs()` (00_global_paths.md §0.1), never
`registered_slugs()`. hooklib loads those three modules only through `hooks/gtm_import.py` (the
hook import rule below). **The path helpers are re-exports, never copies** (00_global_paths.md
§0.1 "The one path-compare implementation"): `gtm_hooklib.norm_text = gtm_env.norm_text`,
`gtm_hooklib.is_under = gtm_env.is_under`, `gtm_hooklib.agency_root() = gtm_env.agency_root(os.environ)`
and `gtm_hooklib.norm(s) = gtm_env.norm(s, test=gtm_env.test_mode(os.environ)[0])` — so every
Agency and root compare in this file canonicalizes every kernel alias exactly as 00 does
(`canon_aliases`: the `//`, `/.nofollow`, `/.resolve/<n>` and `/System/Volumes/Data` firmlink forms,
and the terminal `/.vol` arm returning `gtm_env.VOLFS_SENTINEL`, which every compare here treats as
an Agency match — `canon` step (2b), `path_is_or_under`; wave1e) (`requests/04_hooks.md` R54 asks 08 to list `gtm_env` in the B1 row's import set).

**Residual: in-process `tools/gtm` imports without a trust check (stated).** gate-gtm keeps every
`tools/gtm` import behind its isolated trust check (§4.6 F-trust). G-A, G-B, G-W and the path gate
do not: they load `company`, `system_names` and `gtm_env` in-process on every call, so an
uncommitted edit to one of them — e.g. `gtm_slugs()` returning `[]`, a raising `mirror_files`, a
`MARKETING_PATH_NEVER` of `()` — narrows those hooks' deny sets while it stands. Such an edit is
possible only through the paths the trust root already names as residual: a non-GTM session before
G-W is registered, or a shell form rule c does not parse (§4.2 rule c "Known shell-write reach");
after activation G-W denies every tool edit under `R/tools/gtm/` without a signed marker. The
detect-after controls are the ones every TRUST_PATH has: the first `act.py` call of any session
runs the step-0 trust check (05_approver.md §5.5; exit 11 on every command plus a trust notice),
gate-gtm denies every enforced dispatch (§4.6), and the daily trust check escalates a standing
difference to `S/PAUSE.trust` (05_approver.md §5.6). A per-call HEAD comparison inside these hooks
is **not** adopted: it would cost one `git` subprocess per imported module on every tool call
machine-wide, against a window those controls already close within one act.py call.

**Preconditions of B1/B2 (none of these exist in today's code; each lands in the WP named, and B1
or B2 does not start the dependent part until it has).** Checked against the tree on 2026-09-28:
`tools/gtm/company.py` has `registered_slugs()` only.
- `company.gtm_slugs()` — A1 (00_global_paths.md §0.1). Precondition of B1 (every "other packs"
  helper, G-W, rule d1) and B2.
- `company.mirror_files(slug, pack, H)` — A1 (`requests/04_hooks.md` R31). Precondition of B1
  (`gtm_hooklib.mirror_files`, `machine_written`).
- `tools/gtm/gtm_env.py` with `git_show_head`, `real_root`, `real_home`, `real_agency_root`,
  `TRUSTED_PYTHON`, `now`, `test_mode`, `refuse_real_state`, `gtm_tmp_root` and `VOLFS_SENTINEL`
  — A1 (00_global_paths.md §1.1 "`gtm_env` exports", which now lists every one of these names;
  `requests/04_hooks.md` R30; `requests/05_approver.md` R80 (d)). `gtm_tmp_root()` is the temp root
  (`realpath(TMPDIR or "/tmp")`, 00 §1.1) every isolated-subprocess pycache prefix is created
  **directly** under (§4 "Isolated subprocesses"), the same body 05_approver.md §5.5 step 0 (3)'s
  `_gtm_tmp_root()` checks `dirname(P)` against (DECIDED (wave1e); R64 (a) withdrawn).
  Precondition of B1 and B2; until it lands, the Isolated subprocesses rule creates no prefix and
  every hook that starts a `tools/gtm` entry point denies `gate-fault` (fail closed).
- `tools/gtm/system_names.py` with the seat constants, `seat_sets`, `target_ids`, `IDENTITY_KEYS`,
  `normalize_account_id`, `runbook_stem`, `tier_system_of`, `platform_hosts`, `RULE_K_LITERALS`,
  and (this round) `proving_key`, `MARKETING_PATH_NEVER`, `glob_full_match`, `url_target_ids` (§4.1
  "URL ids") — A1 (03_schemas.md §3.22; `requests/04_hooks.md` R20, R41, R44, R63). Precondition of
  B1 and B2.
- `system_names.ticket_mint_digest`/`TICKET_RUNTIME_FIELDS` (A1), the chained ticket-mint event and
  `act.py status --ticket <ticket_id>` (A2), and 05's read-only signed re-verification
  (`requests/04_hooks.md` R62). Precondition of G-A rule 7a admitting anything; until they land,
  rule 7a denies every mutating write/batch/setup-ticketed call (fail closed).
- `act.py status --action <id>` with the result shape R42 fixes — A1. Precondition of G-B rule n's
  exceptions (§4.2); until it lands, both exceptions deny (fail closed), so no GTM session can
  apply or commit a patch.
- The signed `activation.json` format, `gtm_approve.sh activation` and `approval_sig.py
  --verify-activation` — 05 (`requests/04_hooks.md` R45, R50). Precondition of rule 6c admitting
  anything; until they land, rule 6c denies (fail closed).
- `approval_sig.py --verify-trust-edit` — 05 (05_approver.md §5.5 canonical CLI; R38).
  Precondition of G-W admitting any trust-root edit; until it lands, every trust-root edit is
  denied (fail closed).
- The committed runbooks directory `knowledge/marketing_kb/runbooks/` at `T` — the WP that owns
  06_connectors.md's runbooks (verified 2026-09-28: it does not exist at `T` today). Precondition
  of every G-A rule that reads a runbook (allowed read hosts, rules 6c, 7b, 7c, 9b). Until it is
  committed, `read_runbook` and `money_hosts()` raise, so every ticketed G-A call denies and every
  ticketless navigate is judged against the identity domains alone (§4 `read_runbook` fallback) —
  fail closed, no GTM browser work beyond the company's own sites.
- `system_names.APPROVER_KEYCHAIN_LITERALS`, `system_names.PAGE_URL_RE`/`extract_page_url` — A1
  (`requests/04_hooks.md` R52, R57). Precondition of rule f's account/tag arms and of G-A's
  PostToolUse refresh; until they land those parts use the literals stated in this file.
B1/B2 unit tests may run against fixture stand-ins for these, but no B1/B2 commit lands a caller of
one of them before the WP that provides it has landed (08_seats_wps.md §9 order).

**The hook import rule (ONE rule, DECIDED HERE; supersedes the former append rule and resolves the
R48 conflict — `requests/04_hooks.md` R49 asks 00_global_paths.md §1.1 to adopt it; cited by every
hook-side `tools/gtm` import in this file — `gtm_hooklib`, gate-gtm's `apply_t1b`, the T2-deny
release, `agent_budget.py`'s spend-line builder and `release_failure`, `gtm_ticket_release`,
`workflow_model_gate`).** No hook puts `tools/gtm` on `sys.path` at all — neither appended (a
site-packages module named `company`, `system_names`, `dispatch_tags` or `gtm_env` would then shadow
the GTM module inside every hook; `company` is a generic name, and a non-GTM session's tool write
into site-packages is a stated G-W gap, §4.2 rule c) nor prepended (a module in the code root named
like a stdlib module, e.g. `json.py`, would then shadow the stdlib inside every hook). Instead every
hook-side GTM import goes through **`hooks/gtm_import.py`** (WP-B1; a stdlib-only library that
imports nothing from `tools/gtm` and never calls `emit_pretooluse_deny`):
```python
NO_PYCACHE = "/dev/null/gtm-hook-no-pycache"
GTM_HOOK_MODULES = frozenset({"company", "system_names", "gtm_env", "dispatch_tags", "gtm_result"})
def code_root(hook_file: str) -> Path   # Path(os.path.abspath(hook_file)).parent.parent / "tools" / "gtm" — UNRESOLVED
def install(hook_file: str) -> Path     # idempotent; returns code_root(hook_file)
def load(name: str, hook_file: str) -> ModuleType   # install(), importlib.import_module(name), then provenance check
```
- **The code root** is `Path(os.path.abspath(__file__)).parent.parent / "tools" / "gtm"` of the
  calling hook file — the hook's own `hooks/` sibling, **unresolved** (never `.resolve()` or
  `realpath`: B2's end-to-end harness symlinks the other hook modules beside the patched copies
  under the tmp `CLAUDE_DIR/hooks/`, §4.2, and a resolved `__file__` would send a symlinked module
  back to the real `~/.claude/tools/gtm`), and never `R/tools/gtm` with `R = company.claude_dir()`
  (the **state** root, which honors `CLAUDE_DIR`, so an env var could otherwise pick the code a hook
  executes).
- **`install`** sets `sys.dont_write_bytecode = True` and `sys.pycache_prefix = NO_PYCACHE` (a path
  under `/dev/null` can never exist and never be created, `ENOTDIR`, so Python looks for cached
  bytecode only there — never in S, never in an in-tree `__pycache__/` — and every import compiles
  from source), then inserts at `sys.meta_path[0]` one `_GTMFinder(code_root)` unless a finder for
  the same code root is already there. **`_GTMFinder.find_spec(name, path, target=None)`** answers
  only a top-level request (`path is None`) for a name in `GTM_HOOK_MODULES`: it returns
  `importlib.util.spec_from_file_location(name, code_root / f"{name}.py")` when that file exists and
  raises `ModuleNotFoundError(name)` when it does not (never falls through to `sys.path`, so a
  site-packages module of that name is never found); for every other name it returns `None`, so the
  stdlib, `_lib` and every hooks module resolve exactly as today. The modules are registered under
  their real names because they import each other by top-level name (`dispatch_tags` imports
  `company`); a private alias would load a second copy. `sys.path` is never modified.
- **`load`** returns the module only when `os.path.abspath(module.__file__) == str(code_root /
  f"{name}.py")`; otherwise (a same-named module already in `sys.modules` from elsewhere) it raises
  `ImportError`, which each caller handles under its own fail mode.
- **Not S:** `S = company.gtm_state_dir()` sits under `claude_dir()`, which honors `CLAUDE_DIR`, and
  agents can write S through shell forms rule c does not parse (§4.3 "Trust roots");
  `dont_write_bytecode` stops writes, not reads, so a planted unchecked-hash `.pyc` there would run
  inside every GTM hook. (Same reason 05_approver.md §5.5 step 0 withdrew `S/pycache/` for entry
  points; `requests/04_hooks.md` R43 asks 00 to drop `pycache/` from the S layout.) Every state path
  is still resolved from `company.claude_dir()` at call time.
- **`GTM_HOOK_MODULES` is the closure of every hook-side import** (gtm_hooklib: `company`,
  `system_names`, `gtm_env`; gate-gtm: `dispatch_tags`; `gtm_ticket_release`: `gtm_result`), never
  `ai_budget`, `approval_sig` or `activity_log`. A module in that set must not modify `sys.path` on
  any path a hook reaches (today `company`'s lazy `activity_log` import inserts its own directory,
  `requests/05_approver.md` R70 (b); hooks never call that function, and `requests/04_hooks.md` R49
  asks A1 to route it through the same finder).
B1 tests (each RED when its clause is removed): (1) with a tmp directory holding a stub
`company.py` (marker side effect) inserted at `sys.path[0]`, `gtm_import.load("company", <hook>)`
returns the code-root module and the marker is not written (RED with an append or a plain import);
(2) with a code-root `json.py` carrying a marker side effect, importing `gtm_hooklib` leaves
`json.__file__` in the stdlib and the marker unwritten (RED with a `sys.path[0]` insert); (3) with
`CLAUDE_DIR=<tmp>` holding a `tools/gtm/system_names.py` that raises on import, a hook still imports
the code-root module (RED when the rule uses `R`); (4) a crafted `system_names.cpython-313.pyc`
(header matching the source mtime and size, body with a marker side effect) planted under
`S/pycache/`, under `<CLAUDE_DIR>/.gtm_state/pycache/` and in the code root's `__pycache__/` is not
executed by `gtm_hooklib`'s import (RED when `pycache_prefix` is `S/pycache`); (5) a hook file
symlinked into a tmp `hooks/` beside a tmp `tools/gtm/` loads the tmp modules (RED with
`.resolve()`); (6) `sys.path` is identical before and after importing `gtm_hooklib` and calling
every hooklib helper on the fixtures; (7) the closure test: an import recorder around every
hook-side GTM import sees only names in `GTM_HOOK_MODULES` resolve to the code root, and
`GTM_HOOK_MODULES` is disjoint from `sys.stdlib_module_names`, from `{"_lib"}` and from every
`hooks/*.py` stem (B2's `test_no_module_name_collision`, 00_global_paths.md §1.1, keeps its
tools/gtm-vs-hooks check). The `settings.json` commands stay plain `python3 …`; nothing here
depends on how the hook process was started.

**The one hardened committed-read (DECIDED HERE; closes the `refs/replace/` forgery).** Every read
of committed content in this file — `load_pack_safe`, `sibling_packs`, `money_capable_systems`,
`read_runbook` (every runbook read: `runbook_hosts`, `money_hosts`, G-A's allowed read hosts, rule
7b's `identity_in_url`, rule 7c's `never_url_re`, rule 9b's `read_click_targets`),
`setup_script_allowlist`, `ai_budget`'s `company_json` caps and `dispatch_tags`' committed-pack
read — goes through **one** function (the `activation.json` and `approver_pubkey.pem` reads of
`activation_state` and G-W happen inside the isolated `approval_sig.py` subprocess, whose own step-2
read is the same argv and environment, 05_approver.md §5.5),
`gtm_env.git_show_head(root: str | Path, relpath: str, *, timeout: float = 5.0) -> bytes | None`
(`requests/04_hooks.md` R30 asks A1 to add it to `gtm_env`; `gtm_hooklib.git_show_head` is a
re-export, never a copy), which runs exactly 05_approver.md §5.5's argv
`/usr/bin/git --no-replace-objects -c core.fsmonitor=false -c core.untrackedCache=false -C <root>
show HEAD:./<relpath>` with 05's scrubbed environment (`PATH=/usr/bin:/bin`, `HOME`, `LANG=C`,
`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_NO_REPLACE_OBJECTS=1`; every other
`GIT_*` — `GIT_DIR`, `GIT_WORK_TREE`, `GIT_REPLACE_REF_BASE`, `GIT_INDEX_FILE`, … — dropped) and
returns the blob bytes, or `None` on a non-zero exit or timeout. Committed **runtime** content
(`tools/gtm/…`) is read at `T` — the trust root as 05_approver.md's header defines it: `T =
gtm_env.real_root()` outside test mode, `T = R` (resolved) only in test mode — never at a
`CLAUDE_DIR`-derived `R` in production; a pack is read at its home `H`. By default `git show` honors
`refs/replace/`, so without `--no-replace-objects` any session could `git replace` the committed
`approver_pubkey.pem` blob (or a pack, the tier table, the setup-script allowlist) and every "HEAD"
read here would return the attacker's bytes. B1 test: in a tmp `R`, after `git replace <committed
pack blob> <edited pack blob>`, `load_pack_safe` returns the committed pack, not the replaced one,
and after `git replace` of the committed gbp runbook blob `read_runbook("gbp")` returns the committed
runbook (each RED without `--no-replace-objects`; the test runs `git replace` only inside its tmp
repo). The pem case (a trust-edit marker signed with a replaced key is refused) is §4.3's
verification test against the real `approval_sig.py`.

**Isolated subprocesses (DECIDED HERE; one rule for every hook that starts a `tools/gtm` entry
point — gate-gtm's `approval_sig.py --trust-result` and `ai_budget.py state`, `activation_state`'s
`approval_sig.py --verify-activation`, G-W's `approval_sig.py --verify-trust-edit`, rule n's
`act.py status`, G-A rule 7a's `act.py status --ticket`).** The argv is `[<TRUSTED_PYTHON>, "-I", "-S", "-B", "-X",
f"pycache_prefix={P}", <T>/tools/gtm/<entry>.py, …]` with `P = gtm_env.gtm_tmp_root() + "/gtm_pyc_"
+ secrets.token_hex(8)` — **directly** under the temp root, no intermediate directory; `<fresh P>`
in any argv in this file names exactly this prefix — created by
the hook with `os.mkdir(P, 0o700)` for that one child (a new random name on `FileExistsError`, at
most 100 tries, else deny `gate-fault`). **DECIDED (wave1e), finding wave1d-B2, superseding the
wave1d `gettempdir()/"gtm_isolated"` form:** `gtm_env.gtm_tmp_root()` has exactly the body
05_approver.md §5.5 step 0 carries as `_gtm_tmp_root()` and `requests/05_approver.md` R80 (d) asks
00 to export — `os.path.realpath(os.environ.get("TMPDIR") or "/tmp")`, with `/tmp` (realpath'd)
when that value is not an existing directory (00_global_paths.md §1.1 "`gtm_env` exports") — and
the child's step 0 (3) requires `os.path.realpath(os.path.dirname(<P>)) == _gtm_tmp_root()`. The
wave1d form put `P` one level lower (`<tmp>/gtm_isolated/gtm_pyc_…`), so every isolated child's
`dirname(P)` was `<tmp>/gtm_isolated`, never the temp root, and every child exited 11
(`trust_interpreter`), cascading into gate-gtm's trust-failure path; it also used
`tempfile.gettempdir()`, which falls back to other directories (`TEMP`, `TMP`, `/var/tmp`, cwd)
that step 0's body never considers. The hook and the child evaluate the same body in the same
environment (the child inherits the hook's environment, `TMPDIR` included), so the two roots agree
by construction; the A2 parity test of 05 §5.5 step 0 covers this function too.
`tempfile.mkdtemp()` is never used (unpinned placement). The child is run with stdlib `subprocess.run(…,
capture_output=True, timeout=…)`, and the hook's own environment. The hook is `P`'s creator, so it
removes it (05_approver.md §5.5 "Cleanup": a child started without the re-exec sentinel never
removes a prefix it did not create): in a `finally` after the child exits or times out, `os.rmdir(P)`
with `OSError` ignored — never `shutil.rmtree` (an empty 0700 leaf is all `-B` leaves; `rmdir` fails
harmlessly on anything else). A B1/B2 test counts `gtm_pyc_*` entries under `gtm_env.gtm_tmp_root()`
(never `tempfile.gettempdir()` directly — the root the prefixes actually land under) before and
after 20 calls of each helper (success, non-zero exit and timeout paths) and finds no growth (RED
when the `finally` is removed), and asserts every created prefix's `os.path.dirname(realpath(P))`
equals `gtm_env.gtm_tmp_root()` (RED under the wave1d `gtm_isolated` subdirectory, and under a
`tempfile.mkdtemp()` call in an environment with a non-default `TMPDIR`), and one end-to-end B1
test runs the real `approval_sig.py --trust-result` isolated child through the helper and gets exit
0, not 11 `trust_interpreter` (RED under the wave1d `gtm_isolated` form).

```python
def runtime_root() -> Path                      # company.claude_dir()
def state_dir() -> Path                         # company.gtm_state_dir()
def gtm_company(environ=os.environ) -> str | None
def gtm_session(environ=os.environ) -> str | None
now_utc = gtm_env.now                           # THE one clock (00_global_paths.md §1.1: "gtmlib clock and hooks clock both call it");
                                                #   aware UTC; GTM_FAKE_NOW honored only under GTM_TEST=1; hooks fall back to the real clock
                                                #   on an unparseable honored value (00 §1.1). Never a hooklib-local reimplementation
def git_show_head(root, relpath, *, timeout=5.0) -> bytes | None   # re-export of gtm_env.git_show_head (above: the one hardened committed read)
def load_pack_safe(slug) -> dict | None           # the COMMITTED pack (FID-07): json.loads of `git_show_head(H, ".claude/gtm/company.json")`
                                                #   (5 s timeout; `./` makes the path relative to H, not to the repo toplevel, so a home that is a
                                                #   subfolder of a repo resolves); None when H is unresolvable, git fails, the pack is not committed
                                                #   yet or the JSON is invalid. An uncommitted working-tree edit is never in effect for any hook
                                                #   (gate-gtm's dispatch caps included). Callers that need OTHER companies' packs never treat
                                                #   None as "no data" — see sibling_packs() below
def sibling_packs(slug) -> dict[str, dict]      # load_pack_safe for every company.gtm_slugs() entry except slug; raises SiblingPackUnreadable(bad_slugs)
                                                #   when any of them is None (an unresolvable home, a git failure, a new P1/P1b home before its first
                                                #   commit). Every "other company" helper below goes through it, so an unreadable sibling can never
                                                #   silently drop its domains, account ids or secrets out of a deny set (fail closed; callers below)
def pause_present(slug, name) -> bool           # ST/<name> exists
def ticket_paused(slug, ticket: dict) -> str | None   # G-A rule 6b: R/schedules/DISABLED, ST/PAUSE, ST/PAUSE.chain (plan §6.1/§6.8: broken chain =
                                                #   tampering suspected; act.py refuses every write, so the browser must stop too), any ST/PAUSE.*
                                                #   whose name normalizes (system_names.tier_system_and_brand) to ticket["system"] with brand None or
                                                #   == ticket["brand"] — and, when ticket["brand"] is None, ANY brand-scoped PAUSE.<system>@<b>
                                                #   (a null-brand ticket on a multi-brand system is blocked by every brand pause) — or S/PAUSE.trust
                                                #   when ticket_is_money(ticket) — or the **step-0 pause spool** (02_act.md §2.3; requests/02_act.md
                                                #   item 69): any `S/pause_spool/*.json` whose `company` field == slug is a company-wide PAUSE
                                                #   (returned as "pause_spool:<file name>"), because while the trust root is failing act.py's
                                                #   `pause` can only spool and every act.py command exits 11, so the browser is the one path that
                                                #   can still mutate (plan §6.8: a manual PAUSE blocks "all T1+ actions and write tickets"). An
                                                #   unreadable or unparsable spool file, or a listing error of `S/pause_spool/`, raises (rule 6b
                                                #   then denies `gate-fault`: fail closed); an absent directory is no spool. Returns the pause
                                                #   name or None; raises on I/O error. B1 test: a spool file `{"company": "x", …}` makes x's bound
                                                #   write ticket's next `browser_click` deny `paused` and leaves company y's allowed (RED when the
                                                #   spool read is removed); an unparsable spool file denies `gate-fault`.
                                                # **Ticket exemptions (binding; 03_schemas.md §3.6 `stop_exempt`/`revert_exempt`; requests/03_schemas.md
                                                #   R57 (b), requests/02_act.md item 101 (b)).** Each flag counts only when `ticket.get(flag) is True`
                                                #   (missing, null or non-bool reads false):
                                                #   - `revert_exempt` (a revert child authorized at `revert` step 2 by a verified signed approval,
                                                #     02_act.md §2.4; plan §6.8 "revert only with --approval", §20.8 "a signed approval for that
                                                #     revert action"): skip `R/schedules/DISABLED`, `ST/PAUSE` and every `ST/PAUSE.<system>` /
                                                #     `ST/PAUSE.<system>@<brand>` match (whoever created it), and apply `S/PAUSE.trust` to the ticket
                                                #     exactly as to a money ticket (it is signed), whatever `ticket_is_money` returns;
                                                #   - `stop_exempt` (a stop action admitted at mint under a breaker pause by 03 §3.10's stop-row
                                                #     exemption; plan §20.6 runaway-spend stop): skip only a `ST/PAUSE.<system>` /
                                                #     `ST/PAUSE.<system>@<brand>` match whose content is **breaker-written** — the file parses as a
                                                #     03_schemas.md §3.10 pause record with `created_by == "breaker"`, `ruling_ref` null and
                                                #     `lift_card` null; a file that does not parse, or any other creator, is never skipped (fail
                                                #     closed). `DISABLED`, `ST/PAUSE` and `S/PAUSE.trust` still apply;
                                                #   - neither flag ever skips `ST/PAUSE.chain`, a pause-spool file or a cancel marker
                                                #     (`ticket_cancelled`), and neither affects rules 6c, 7b, 9c, 9d or the send window.
                                                #   B1 tests (each RED when its clause is removed): with a breaker-written `ST/PAUSE.google_ads`, a
                                                #   `stop_exempt: true` ticket's `browser_click` passes rule 6b and a `stop_exempt: false` one (and one
                                                #   with the field missing, and one with `"true"`) is denied `paused`; the same `stop_exempt: true`
                                                #   ticket under an operator-written `ST/PAUSE.google_ads` (`created_by: "operator"`) and under
                                                #   `ST/PAUSE` is denied; a `revert_exempt: true` ticket passes rule 6b under `ST/PAUSE`, under
                                                #   `R/schedules/DISABLED` and under `ST/PAUSE.gbp`, and is still denied under `ST/PAUSE.chain`,
                                                #   under a pause-spool file for the company, under a cancel marker for its action, and under
                                                #   `S/PAUSE.trust` although its `money` field is `false`
def ticket_is_money(ticket: dict) -> bool       # class "read" → False; EVERY other class, `batch` included → ticket.get("money") is not exactly
                                                #   False (plan §20.6: absence of `money: false` means money; missing/non-bool → money). A batch
                                                #   ticket is non-money only because act.py writes `money: false` on it and refuses a money row at
                                                #   batch mint (03_schemas.md §3.6 batch row, exit 3 `batch_money_row` — requests/04_hooks.md R16,
                                                #   LANDED in 03 and a B1 precondition, 08_seats_wps.md §9); no class special case exists here
def ticket_cancelled(slug, ticket: dict, *, verified: dict | None) -> str | None  # G-A rule 6b: S/cancels/<slug>/<action_id> exists for the
                                                #   ticket's action_id or any batch items[].action_id, or an S/cancels/<slug>/_all.<UTCts> marker whose <UTCts> is ≥ ticket["created_at"],
                                                #   compared as PARSED aware UTC datetimes (00_global_paths.md §0.3: `<UTCts>` parsed with
                                                #   "%Y%m%dT%H%M%SZ" as UTC, `created_at` with the §0.3 ISO parser), never as strings; an `_all.*`
                                                #   marker whose timestamp does not parse, or a ticket whose `created_at` does not parse, counts as
                                                #   a cancel (fail closed); returns the marker name or None; raises on I/O error (G-A: `gate-fault`)
                                                #   (plan §20.7: a cancel from any channel prevents). **`who` filter, applying
                                                #   `requests/05_approver.md` R77 (a) exactly (DECIDED (wave1d); who-set and lock placement
                                                #   corrected (wave1e), finding wave1d-M4):** `verified` is the result rule 7a's **pre-lock**
                                                #   `verify_ticket(slug, candidate)` call already produced for this same candidate (§4.1 "Ticket
                                                #   authenticity" "When, and the lock"), or `None` when that call raised, or when the ticket
                                                #   re-selected under `tickets_lock` is not the verified one (different `ticket_id`, or
                                                #   `ticket_mint_digest` ≠ the verified `mint_sha256`). `ticket_cancelled` **never calls
                                                #   `verify_ticket` itself** — it runs inside `tickets_lock` (rule 6b is in the critical section,
                                                #   "One critical section per ticketed call" below), and `verify_ticket` is a ≤ 10 s subprocess that
                                                #   must never run under that lock. When `verified` is a dict whose `signed_required` is exactly
                                                #   `true` (a money row or a signed-revert child), a marker counts as a cancel **only** when its
                                                #   parsed JSON `who` is exactly `"operator_script"` or `"approver_menu"` (the *operator* class of
                                                #   05_approver.md §5.1 step 5 and R86); every other value — `"agent"`, `"card_deny"`,
                                                #   `"hand_made_file"` (an empty marker file is `hand_made_file`, 03_schemas.md §3.11),
                                                #   `"system:responded_by"`, and any unknown, misspelled or absent `who` or a body that is not a
                                                #   JSON object (the *agent-class*) — does NOT cancel that ticket: an agent-class marker cannot undo an
                                                #   approval only the operator's Touch ID released (every script and app marker carries a well-formed
                                                #   operator `who`, 05 §5.4, so the operator's `gtm_cancel.sh all` `_all.<UTCts>` marker still stops
                                                #   it). When `verified` is `None` (verification raised or does not match the re-selected ticket) the
                                                #   filter is **not** applied and every marker cancels (fail closed toward "cancelled"; a raising
                                                #   verification is also rule 7a's `ticket-unverified` deny for a mutating call). For a ticket whose
                                                #   `verified.signed_required` is `false`, every marker cancels, as before. A marker body that cannot
                                                #   be read (an `OSError`) raises (G-A: `gate-fault`), never "absent `who`".
def tickets_lock(slug)                          # context manager, flock, 5 s timeout -> TimeoutError; G-A holds it for one ticketed call
                                                #   from candidate selection through rule 13's persist (§4.1 "One critical section")
def read_tickets(slug) -> list[dict]; def write_ticket(slug, ticket: dict) -> None
ticket_mint_digest = system_names.ticket_mint_digest   # G-A rule 7a (§4.1 "Ticket authenticity"): sha256 of the ticket's canonical JSON
                                                #   minus system_names.TICKET_RUNTIME_FIELDS; the one digest act.py writes at mint (R62)
def verify_ticket(slug, ticket: dict) -> dict   # G-A rule 7a: the isolated `act.py status --ticket <ticket_id>` subprocess (the
                                                #   Isolated subprocesses rule, 10 s); returns result.ticket = {ticket_id, class, mint_sha256,
                                                #   state, signed_required, signed_ok} (R62); raises TicketUnverified on a non-zero exit, a
                                                #   timeout, output that is not one JSON object, a missing record or any exception (callers
                                                #   DENY `ticket-unverified`, never allow). Never called while tickets_lock is held
PHI_UNREADABLE: Final[object]                    # the unreadable-denylist sentinel (never None, never an empty dict/list)
def phi_denylist() -> dict | object             # `S/phi_denylist.json` parsed and validated with the rules `gtm_lists.py` validation
                                                #   applies (03_schemas.md §3.20: paths, hosts, host_suffixes, url_prefixes, applies_to only on
                                                #   `agency_app: true` host entries). Returns the dict when it reads, parses and validates. Returns
                                                #   **PHI_UNREADABLE** (00_global_paths.md §1.2 "`phi_denylist.json` missing or unparseable",
                                                #   DECIDED there; 03_schemas.md §3.20 "Hook readers — fail closed") when the file is unreadable,
                                                #   unparseable or schema-invalid (always), or ABSENT while any `company.gtm_slugs()` pack is
                                                #   `regulated ∋ "hipaa"` or the slug `otherapp` is registered (a pack that does not load counts as
                                                #   hipaa — fail closed). Absent with neither → the empty denylist `{"paths": [], "hosts": [],
                                                #   "host_suffixes": [], "url_prefixes": []}` and one `phi-denylist-absent` log row per process.
                                                #   It never returns None and never raises for a file problem (only for a bug); every caller
                                                #   compares `is PHI_UNREADABLE` before using the dict. Consequences (binding, §4.1 rule 3, §4.2
                                                #   rule j, §4.4 rule 0): in GTM scope, G-A denies every `browser_navigate` and every call whose
                                                #   rule 3 runs as `phi-host`; the path gate and G-B deny every read target outside the session
                                                #   company's H, R and the temp roots as `phi-denylist-unreadable`. Each denial logs
                                                #   `phi-denylist-unreadable` (hook, session, host or path class — never file content), and the
                                                #   first per process writes 03 §3.20's urgent pushed `trust` notice (`dedupe_key`
                                                #   `phi_denylist_unreadable:<slug>`) in its own `try` after the decision; the daily run's
                                                #   `phi_denylist_missing` notice (00 §1.2) is the second signal
def phi_url_hit(url: str, company: str | None) -> str | None
                                                # THE one PHI URL predicate (G-A rule 3 and the PostToolUse refresh, path-gate rule 2, G-B rule j).
                                                #   Raises PhiDenylistUnreadable when phi_denylist() is PHI_UNREADABLE (callers apply the
                                                #   consequences above). Otherwise returns a match label or None:
                                                #   (1) "host:<h>" / "suffix:<s>" — host_of(url) matches a `hosts` entry (host_matches) or a
                                                #       `host_suffixes` entry whose `applies_to` is absent or contains `company` (company None or
                                                #       "*" → every entry; 03 §3.20: only `agency_app` host entries carry `applies_to`);
                                                #   (2) "url_prefix:<p>" — a `url_prefixes` entry (never filtered by company; 03 §3.20: it binds
                                                #       every company) whose host equals host_of(url) and whose path P matches the URL's path U:
                                                #       both normalized as `urllib.parse.unquote`, RFC 3986 §5.2.4 dot-segment removal, runs of
                                                #       `/` collapsed to one, casefolded (only widens the match), and a trailing `/` stripped
                                                #       except for the root; match iff P == "/" or U == P or U starts with P + "/". The scheme,
                                                #       port, query and fragment are ignored (an `http://` or `:443` spelling of a denylisted
                                                #       page is still a hit). A URL that does not parse, or has no host, returns None for (1)/(2)
                                                #       — it is not a PHI URL; G-A and the path gate judge an unparseable navigate target
                                                #       separately (`host-unknown` / `gate-fault`).
                                                #   B1 tests (each RED when (2) is removed or uses a plain string prefix): with a url_prefix
                                                #   `https://x.example/r/abc`, `https://x.example/r/abc/page2`, `http://X.EXAMPLE:443/r/abc`,
                                                #   `https://x.example/r/%61bc` and `https://x.example/r/q/../abc?t=1#f` hit, `https://x.example/r/abcd`
                                                #   and `https://x.example/r` do not, and a OtherCompanyB and a OtherApp company both hit (no
                                                #   applies_to)
def redact_url(url: str) -> dict; def redact_text(s: str) -> str
                                                # HIPAA redaction (§4.1 "HIPAA packs: no raw page text in G-A records"). redact_text(s) =
                                                #   "sha256:" + sha256(s.encode()).hexdigest(). redact_url(url) = {"host": host_of(url),
                                                #   "path_template": the path with every segment that does not match `^[a-z_-]{1,24}$`
                                                #   (casefolded) replaced by "*", "url_sha256": redact_text(url)}. Both pure
def page_url(result_text: str) -> str | None    # the LAST match of system_names.PAGE_URL_RE (`-\\s*Page URL:\\s*(\\S+)`) — the one parser
                                                #   (system_names.extract_page_url, requests/04_hooks.md R57; harvest_tool_trail's copy is
                                                #   parity-tested against it until it imports it); None when no line matches
def activation_state() -> dict                  # the committed trust-root file `tools/gtm/activation.json` at T (§4.3; read by the subprocess below), a
                                                #   GTMApprover-SIGNED record (schema `gtm.activation.v1`, `requests/04_hooks.md` R45):
                                                #   {"schema", "payload_b64", "signature_b64", "alg", "key_fingerprint", "signed_at"}, the payload
                                                #   the canonical JSON {"v": 1, "kind": "activation", "ruling_id": "<operator ruling id>",
                                                #   "nonce": "<32 hex>"} with exactly those keys, produced only by the operator's
                                                #   `gtm_approve.sh activation <ruling_id>` → Touch ID (rule g denies every agent run of that
                                                #   script). Verification is **never in-process** (00_global_paths.md §0.2: no GTM tool or hook
                                                #   imports a third-party crypto package; 05_approver.md §5.5 step 4 is the one backend
                                                #   definition): activation_state runs `<gtm_env.TRUSTED_PYTHON> -I -S -B -X
                                                #   pycache_prefix=<fresh P> <T>/tools/gtm/approval_sig.py --verify-activation` (stdlib
                                                #   `subprocess`, 5 s timeout; the mode `requests/04_hooks.md` R50 asks 05 to add: it runs steps
                                                #   0–2, reads `tools/gtm/activation.json` and `approver_pubkey.pem` at T through the hardened
                                                #   `git show HEAD:` read, verifies the signature with step 4's backends (`/usr/bin/openssl` for
                                                #   ECDSA P-256, the stdlib `ed25519_verify.py` for Ed25519), checks canonical payload bytes with
                                                #   exactly the key set above, `kind == "activation"`, `v == 1` and a non-empty string
                                                #   `ruling_id`, prints exactly one JSON object `{"ok": bool, "reason": str|null, "ruling_id":
                                                #   str|null}` and exits 0 valid, 7 invalid (unsigned, legacy-shaped, wrong key, wrong kind, bad
                                                #   bytes), 4 not committed, 11 trust failure, 3/2/1 root mismatch/usage/internal). Returns
                                                #   {"r22_money_residual_ruling": <ruling_id>} only when the process exits 0 within the timeout
                                                #   and its stdout is exactly one JSON object with `ok is True` and `ruling_id` a non-empty
                                                #   string; `{}` on exit 4 or 7 (logged `activation-unverified` with `reason`); raises
                                                #   ActivationUnavailable on every other outcome (exit 11/3/2/1, timeout, spawn error, extra or
                                                #   non-JSON output) — callers fail closed exactly as for `{}`. The pycache prefix is removed by
                                                #   this helper after the child exits (§4 "Isolated subprocesses"). Cost, stated: one
                                                #   subprocess per rule-6c evaluation (a mutating write/batch call on a money host), never
                                                #   cached (a cache in S would be agent-writable). Why signed: the id alone is agent-supplyable —
                                                #   a non-GTM session can `git apply` and commit under `R` (§4.2 "Backing up and reverting"),
                                                #   and the gate-3b review record is self-recordable — while plan §20.8 reserves the ruling to
                                                #   the operator. The nonce is not consumed (activation is a standing state, not a single-use
                                                #   marker); it only makes each signed record unique. Read by G-A's rule 6c (§4.1 "Money-host
                                                #   activation precondition") and by act.py's mint refusal (R35, verified the same way,
                                                #   `requests/04_hooks.md` R45); only a non-GTM session commits the file, under full review
                                                #   (HIGH tier, §4.9), after the operator's R22 ruling is recorded
def canon(p: str, base: str | None = None) -> str # THE canonical path form (F-case). Order (binding):
                                                #   (1) expand on p FIRST: a leading `~`/`~user` (expanduser) and a leading `$HOME`/`${HOME}`;
                                                #   (2) t = norm(os.path.abspath(os.path.join(base or os.getcwd(), p_expanded))) — text only;
                                                #   (2b) `/.vol` (DECIDED (wave1e), `requests/00_global_paths.md` R44): if t == gtm_env.VOLFS_SENTINEL
                                                #        (00 §0.1 arm (e): `norm_text` of any `/.vol/…` spelling), return it with NO filesystem call —
                                                #        a device/inode path has no recoverable text, so it is never walked, never stat'd;
                                                #   (3) Agency short-circuit (00_global_paths.md §0.1 I14): if t is equal to or under
                                                #       norm(agency_root()) OR norm(str(gtm_env.real_agency_root())) (both roots, 00 §0.1),
                                                #       return t with NO filesystem call;
                                                #   (4) else resolve symlinks with 00_global_paths.md §0.1 register (b)'s component walk
                                                #       (`os.path.islink` only while the accumulated prefix is not equal to/under either Agency root;
                                                #       `os.readlink` target joined + re-normed; a target that re-norms to VOLFS_SENTINEL returns the
                                                #       sentinel at once; a target equal to/under Agency returns
                                                #       norm(<target>/<rest>) at once, never stat'ing inside it; >40 links → raise), and
                                                #       return norm(<resolved>).
                                                #   Joining before expanding is WRONG (`join('/cwd', '~/.claude/x')` = '/cwd/~/.claude/x';
                                                #   expanduser only expands a leading `~`). norm in steps (2)–(4) = `gtm_env.norm_text` (00_global_paths.md §0.1:
                                                #   normpath + casefold + `canon_aliases`, incl. the `/.vol` → VOLFS_SENTINEL arm), re-exported, never copied.
                                                #   hooklib unit tests: canon('~/.claude/x', '/tmp') == canon('<HOME>/.claude/x') (RED with
                                                #   join-first); canon('$HOME/x', '/tmp') likewise; canon of a path under Agency and of a
                                                #   symlink whose target is under Agency run under the 00 §0.1 no-Agency-touch oracle with
                                                #   nothing recorded. This volume is case-INsensitive
                                                #   (`~/.CLAUDE/hooks` resolves; realpath keeps the caller's casing), so EVERY path comparison in
                                                #   G-A, G-B, G-W and the path gate — protected paths, phi_denylist, phi1_root, agency_root, rule-a
                                                #   globs, allowlist folders, activity-log paths — applies canon to BOTH sides; fnmatch-style globs
                                                #   are matched against canon'd text with casefolded patterns. Nothing compares raw path strings
def path_is_or_under(p: str, root: str) -> bool; def path_is_ancestor_of(p: str, target: str) -> bool   # both take canon() strings, separator-bounded
                                                #   **`/.vol` fails closed (DECIDED (wave1e), R44):** both raise `KernelPathAlias` when either argument is
                                                #   gtm_env.VOLFS_SENTINEL, so neither a deny arm nor an ALLOW arm (allowed roots, pack-declared editable paths,
                                                #   allowlist folders) can ever answer for a `/.vol` path; every rule that calls them maps that exception to a
                                                #   DENY with its own reason (the Agency rules: `agency-boundary`), and it is never caught by G-A's or G-B's
                                                #   allow-on-internal-exception path. The path gate rule 1, G-B rule i and G-A rule 3b's `file://` arm also test
                                                #   `canon(x) == VOLFS_SENTINEL` explicitly, first, and deny `agency-boundary` (00 §0.1: every consumer adds this
                                                #   line). B1 tests (each RED without it, under the no-Agency-touch oracle): with dev/ino of a tmp Agency dir, a
                                                #   GTM-scope `Read` of `/.vol/<dev>/<ino>/x`, a `cat /.vol/<dev>/<ino>/x` and a `browser_navigate` to
                                                #   `file:///.vol/<dev>/<ino>/x` are each denied `agency-boundary`; and a GTM-scope `Write` to
                                                #   `/.vol/<dev of R>/<ino of R>/tools/gtm/act.py` is denied (never admitted by an allow arm)
def host_of(url: str) -> str                    # lowercased host, port and trailing dot stripped (DNS ignores case)
def host_matches(host: str, rule: str) -> bool  # exact or subdomain, both sides lowercased
def is_agency_github_url(url: str) -> bool      # ONE implementation for G-A 3b, the path gate rule 1 and G-B rule i: host (lowercased) github.com
                                                #   or a subdomain / codeload.github.com with path matching (?i)^/[^/]+/agency([-_.][^/]*)?(/|$);
                                                #   raw.githubusercontent.com with the same path regex; api.github.com with path matching
                                                #   (?i)(^|/)repos/[^/]+/agency([-_.][^/]*)?(/|$); or file:// + a canon path that is gtm_env.VOLFS_SENTINEL (wave1e, R44) or equal to/under either Agency root (agency_root() or gtm_env.real_agency_root()).
                                                #   <org> is NOT bound: every repo named agency* (e.g. someone/agency-swarm) is blocked in GTM scope —
                                                #   accepted as fail-safe (GTM work never needs such a repo; binding <org> would need an unrecorded org name)
AGENCY_REPO_SLUG_RE = r"(?i)^[A-Za-z0-9_.-]+/agency([-_.][A-Za-z0-9_.-]*)?(\.git)?$"   # a WHOLE argv value `<owner>/Agency…` (G-B rule i: gh -R/--repo
                                                #   values and positional repo args only — never applied to free text, so `docs/agency_notes.md` is not a hit)
def identity_hosts_other_than(slug, *, exclude_shared: bool = False) -> dict[str, set[str]]
def account_ids_other_than(slug, *, exclude_shared: bool = False) -> dict[str, set[str]]
    # Both read sibling_packs(slug) and so RAISE SiblingPackUnreadable rather than return a partial set (callers: G-A rule 4, G-B d1).
    # Both ALSO union the operator's non-GTM business list (plan §7.6: "the identity index is the other packs plus
    #   other_businesses.json"; plan §2 seeds it with the cross-connected Meta ad account 12864445), returned under the key
    #   "other_businesses": the values of `S/other_businesses.json` (00_global_paths.md §1.2 shape `{"<label>": [values] |
    #   "<value>"}`, read as a plain file — it is add-only and machine-written, so it is always at least as fresh as
    #   `S/identity_index.json`), each classified by `classify_identity_value` below: "host" values go to the host set of
    #   identity_hosts_other_than, "account_id" values to the id set of account_ids_other_than, other values (names, street
    #   addresses) to neither. An absent, unreadable or unparsable file (or a top-level value that is not an object, or a
    #   label whose value is neither a string nor a list of strings) raises OtherBusinessesUnreadable, a subclass of
    #   SiblingPackUnreadable with bad_slugs == ["other_businesses"], so every caller's existing fail-closed handling
    #   applies unchanged (G-A rule 4: `gate-fault` for ticketed tools and for a navigate off this company's allowed read
    #   hosts; G-B d1 as for an unloadable pack). Absent counts as unreadable because plan §2's seed must exist before
    #   activation (coordinator checklist, `requests/04_hooks.md` R46). exclude_shared never drops an other_businesses
    #   value (no pack can declare one shared with a non-GTM business).
def classify_identity_value(v: str) -> tuple[str, str] | None
    # ONE rule, used by the two helpers above for other_businesses values and by the off-server check (§4.1 "Other
    #   playwright servers") for every identity_index value: strip; a value with a URL scheme → its host_of(); else a value
    #   matching (lowercased) `^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?$` → ("host", that value,
    #   lowercased, trailing dot stripped); else the account-id normalization below (system_names.normalize_account_id's
    #   fallback: strip `-`, spaces and the prefixes `act_`/`ocid=`) yields `^\d{6,}$` → ("account_id", the digits); else
    #   None. Stated: a phone number such as `303-555-1234` normalizes to 10 digits and is classed as an account id — the
    #   same shape as a Google Ads id, so the two cannot be told apart; the only effect is a wider deny set, never a narrower
    #   one.
    # Account ids are stored NORMALIZED: system_names.normalize_account_id when it knows the system, else strip `-`, spaces and the
    #   platform prefixes `act_`/`ocid=` to the digit string (`100-200-3000` -> `1002003000`, `act_12864445` -> `12864445`).
    # exclude_shared=True drops every value that BOTH `slug`'s pack and the other pack list in `shared_identifiers` (mutual declaration
    #   only; one-sided declarations stay in the deny set) — used only for non-mutating tools, G-A rule 4.
def url_has_account_id(url: str, ids: set[str]) -> str | None
    # Returns the matched id or None. Candidates = maximal digit runs (bounded by non-digits, so `123` never hits inside `9912345`)
    #   taken from each path segment and each query value of the URL, after stripping `act_` and `-` inside a segment/value
    #   (`ads.google.com/…?ocid=1002003000` matches stored `100-200-3000`). A stored id shorter than 6 digits matches only a whole
    #   path segment or whole query value equal to it (never a digit run inside a longer token), so short ids cannot false-trip a breaker.
def read_runbook(tier_system: str) -> dict | None   # THE one runbook read (binding): json of `git_show_head(T,
                                                #   f"knowledge/marketing_kb/runbooks/{system_names.runbook_stem(tier_system)}.runbook.json")`
                                                #   (5 s timeout) — the COMMITTED runbook at the trust root T (§4 hardened read; `T` =
                                                #   `gtm_env.real_root()` outside test mode, never a `CLAUDE_DIR`-derived `R`), never the
                                                #   working tree: `knowledge/` is editable from any non-GTM session and is not a trust root,
                                                #   so an uncommitted edit that drops `money_ui_hosts`, a read host or `read_click_targets`
                                                #   must never weaken rules 6c/7b/9b or the allowed-read-host set. A None stem → None ("no
                                                #   runbook"). `git_show_head` returning None is ambiguous (missing path or git failure), so
                                                #   read_runbook then reads the directory `git_show_head(T, "knowledge/marketing_kb/runbooks")`
                                                #   (a tree read; exit 0 with the listing when HEAD and the directory exist): bytes → the file
                                                #   is not committed → None; None again → raise. Invalid JSON raises. **Callers' fallback on a
                                                #   raise (binding):** rules 6c and 9b treat ANY host as a money host (so rule 6c denies every
                                                #   mutating write/batch call while no ruling is verified, and rule 9b denies every read-ticket
                                                #   click); the allowed-read-host set (rule 6) contains NO runbook read or login host (only the
                                                #   identity domains); rules 7b's `identity_in_url` exception and 7c deny `gate-fault`. Results are
                                                #   memoized per hook process only. B1 test: in a tmp `T`, an uncommitted working-tree edit
                                                #   of the gbp runbook that removes `business.google.com` from `money_ui_hosts` leaves
                                                #   `money_hosts()` unchanged (RED with a working-tree read)
def money_capable_systems() -> set[str]         # the union of (1) tier systems with any row for which `row.get("money", True) is not False`
                                                #   in `git_show_head(T, "tools/gtm/tier_table.json")` (5 s timeout) — a row with no `money`
                                                #   flag, or a non-bool one, counts as money (plan §20.6; 03_schemas.md §3.4.4; the same
                                                #   "not exactly False" rule as ticket_is_money) — and (2) every system that has NO tier row but
                                                #   has a committed runbook (`read_runbook(system)` is not None) or is named, after `tier_system_of`, in any GTM pack's
                                                #   `scope.channels_in_scope` (packs via load_pack_safe for every gtm_slugs() entry) — plan §20.6:
                                                #   an action with no tier-table match is `$` (`_nomatch`), so a runbook-only system such as
                                                #   `linkedin` or `youtube` (boost/promote flows, no rows) is money-capable, never non-money.
                                                #   git/JSON failure, or any pack loading None -> raises (callers treat every system as
                                                #   money-capable). Tests: a tier table whose only row for system X omits `money` puts X in the
                                                #   set (RED with `row.get("money") is True`); a runbook-only system Y (runbook, no rows) is in
                                                #   the set, its runbook read host is in money_hosts(), and a read ticket's `browser_click` there is
                                                #   denied `read-click-money-system` (RED when (2) is removed)
def money_hosts() -> set[str]                   # G-A rule 9b's host set: runbook_hosts(money_capable_systems()) read + login hosts ∪ every
                                                #   runbook's `money_ui_hosts` (a runbook-declared list of hosts whose UI offers money flows
                                                #   regardless of rows — at least business.google.com (GBP "Promote"), business.facebook.com,
                                                #   biz.yelp.com and the Angi/Thumbtack pro consoles; validated by 06 ⊆ platform_hosts(system),
                                                #   requests/04_hooks.md R18). "Every runbook" = every `*.runbook.json` name in the COMMITTED
                                                #   directory listing `git_show_head(T, "knowledge/marketing_kb/runbooks")`, each read from
                                                #   HEAD like read_runbook (never the working tree). Any read failure raises (callers treat
                                                #   ANY host as money: read_runbook's "Callers' fallback" above)
def setup_script_allowlist() -> dict            # json of `git_show_head(T, "tools/gtm/setup_scripts/allowlist.json")` (5 s timeout);
                                                #   raises when git fails OR the working-tree file's bytes differ from HEAD's (an uncommitted entry
                                                #   escapes plan §20.10's trust-architect review, so it is never in effect)
def split_with_joins(command: str) -> list[tuple[str, str | None, int]]   # F-cd; (segment, joiner-before ∈ {None,"&&","||",";","|","&"},
                                                #   subshell depth) parsed from the RAW text, quote- and heredoc-aware like _lib._split_segments,
                                                #   which discards joiners and so cannot drive cd tracking (_lib.py's own _LEADING_CD_RE comment).
                                                #   It splits on every CONTROL-OPERATOR boundary _split_segments splits on, mapped: an unquoted
                                                #   newline → ";", `|&` → ONE "|" joiner (its `&` is part of the pipe operator, never a second
                                                #   boundary), `&&`/`||`/`;`/`|`/`&` as themselves — **except** that an `&` which is part of a
                                                #   REDIRECT operator is never a boundary (a DELIBERATE divergence from _split_segments, which
                                                #   splits `2>&1` into `… 2>` + `1` — verified: `_split_segments('python3 -m pytest tools/gtm/tests
                                                #   2>&1 | tail')` → ['… 2>', '1', 'tail'], `'echo x >&2'` → ['echo x >', '2']): at each unquoted
                                                #   `&`, first try OPERATOR_RE (below) anchored at the start of the redirect that could contain it
                                                #   (a match beginning at this `&` — `&>`, `&>>` — or one beginning at the preceding digits/`>`
                                                #   that spans it — `>&N`, `N>&M`, `>&-`); if it matches, the whole operator stays inside the
                                                #   segment. A subshell or substitution opener (`(`, `$(`, `<(`, `>(`) starts a segment at
                                                #   depth+1 with joiner None and its closer returns to the outer depth (the next outer segment keeps
                                                #   the joiner that follows the closer); a **backtick toggles** depth (an unquoted backtick at
                                                #   depth d opens d+1 when no backtick is open, else closes to d−1); an unmatched `)` — a `case`
                                                #   arm `x)`, `esac`-style shapes — is a boundary whose depth is **clamped at 0** (depth never goes
                                                #   negative, and an unmatched closer never changes cd handling: it is a plain boundary with joiner
                                                #   None for the next segment; verified shape `case x in x) rm act.py;; esac` → ['case x in x',
                                                #   'rm act.py', 'esac']). **Heredocs:** a QUOTED delimiter (`<<'EOF'`, `<<"EOF"`) drops the body
                                                #   from segments exactly as _split_segments does (verified: "cat <<'EOF'⏎line1⏎rm act.py⏎EOF"
                                                #   → ["cat <<'EOF'"]); its body is inert input. An UNQUOTED delimiter (`<<EOF`, `<<-EOF`) is
                                                #   different, and here split_with_joins DELIBERATELY DIVERGES from _split_segments. What
                                                #   _split_segments does (verified 2026-09-28, and stated in its own docstring's round-3
                                                #   correction): it runs an unquoted body through its normal character walk, so body newlines
                                                #   become boundaries — 'cat <<EOF\nline1\nrm act.py\nEOF' → ['cat <<EOF\nline1', 'rm act.py',
                                                #   'EOF'] (the first body line glued to the opener, each later line its own segment, the
                                                #   terminator a segment) — and a substitution inside the body opens a real segment
                                                #   ('cat <<EOF\n$(rm act.py)\nEOF' → ['cat <<EOF', 'rm act.py', 'EOF']). What
                                                #   split_with_joins does: the plain body text of an unquoted heredoc (every character from the
                                                #   end of the opener's line through the terminator line, excluding the substitutions below)
                                                #   stays with the opener's segment and is EXCLUDED from verb/argv/operand classification —
                                                #   it is data to the shell, so `rm act.py` on a body line is never a command, and the
                                                #   unquoted-newline → ";" mapping never applies inside a body; **but** bash expands `$(…)`,
                                                #   backticks and `${…}` inside an unquoted body (the verified _split_segments finding), so
                                                #   inside an unquoted body every `$(`, backtick and `<(`/`>(` opener still opens an inspected
                                                #   depth+1 segment with joiner None, exactly as outside a heredoc, and its closer returns to
                                                #   the body; `${…}` is not a segment (it runs no command except through a nested `$(`/backtick,
                                                #   which is itself inspected). Rules a and k re-read the raw command text for heredoc bodies of
                                                #   both kinds. B1 tests:
                                                #   `cd /tmp⏎rm act.py` (cwd tools/gtm) → segments [("cd /tmp", None, 0), ("rm act.py", ";", 0)]
                                                #   and G-B denies `protected-state-write`; `python3 -m pytest tools/gtm/tests -q 2>&1 | tail` →
                                                #   two segments (`… 2>&1`, `tail`), `echo x >&2` → one; `case x in x) rm act.py;; esac` (cwd
                                                #   `~/.claude/tools/gtm`) → `rm act.py` at depth 0, denied; `cat <<EOF⏎rm act.py⏎EOF` → one
                                                #   segment whose body tokens are not operands (allowed); `python3 <<EOF⏎from
                                                #   tools.gtm.connectors.meta import write⏎EOF` denied by rule a from the raw text; a multi-line
                                                #   unquoted body `cat <<EOF⏎line1⏎rm act.py⏎line3⏎EOF` (cwd `~/.claude/tools/gtm`) is allowed
                                                #   (RED when body lines become segments, as in _split_segments); `cat <<EOF⏎$(rm act.py)⏎EOF`
                                                #   and `cat <<EOF⏎x `rm act.py` y⏎EOF` (same cwd) are denied `protected-state-write` (RED when
                                                #   the whole unquoted body, substitutions included, is excluded); `cat <<'EOF'⏎$(rm
                                                #   act.py)⏎EOF` (quoted delimiter, same cwd) is allowed (each RED when its clause is removed)
OPERATOR_RE = r"(?:\d+|&)?(?:>\||>>?|<<<|<<?)(?:&(?:\d+|-))?"   # the redirect OPERATOR alone (no target): exactly the operator
                                                #   prefix of pretooluse_bash._REDIRECT_INLINE_RE (`(?:\d+|&)?(?:>\||>>?|<<<|<<?)` + its
                                                #   `&(?:\d+|-)` descriptor alternative), whose own match also swallows the target word
                                                #   (`\s*[^\s|]+`) and has no capture groups. P2 parity test: `_REDIRECT_INLINE_RE.pattern`
                                                #   begins with OPERATOR_RE's two leading groups and every operator OPERATOR_RE matches is matched
                                                #   by _REDIRECT_INLINE_RE at the same start
REDIRECT_RE = <copy of pretooluse_bash._REDIRECT_INLINE_RE>   # redirect FINDER for rule c; a P2 parity test asserts the pattern
                                                #   equals pretooluse_bash's (hooklib never imports pretooluse_bash, which imports G-B).
                                                #   Use (binding): `redirect_targets(segment_raw) -> list[str]` iterates REDIRECT_RE matches on
                                                #   the raw segment text and (1) drops a match that starts inside a quoted span (the same
                                                #   `_quoted_positions` logic pretooluse_bash filters with, copied and parity-tested); (2)
                                                #   re-derives the operator's end with the COMPILED pattern `_OPERATOR_RX = re.compile(OPERATOR_RE)`
                                                #   as `_OPERATOR_RX.match(segment_raw, match.start())` — never `re.match(OPERATOR_RE,
                                                #   segment_raw, match.start())`, whose third positional parameter is `flags`, not `pos`
                                                #   (verified: offset 7 raises `ValueError: cannot use LOCALE flag with a str pattern`, other
                                                #   offsets silently set IGNORECASE/VERBOSE/…, and inside G-B an exception is allow + `gate-fault`,
                                                #   so rule c's redirect protection would fail open) (REDIRECT_RE's match end is past the
                                                #   target and it has no group to read); (3) keeps only
                                                #   operators containing `>` that are not a descriptor duplication/close (`>&N`, `N>&M`, `>&-`);
                                                #   `<`, `<<`, `<<<` are dropped; (4) takes the target as the NEXT shlex word after that operator
                                                #   end (quotes stripped; `> "a b"` → `a b`, `echo x>f y` → `f`) — **except** the bash form
                                                #   `>&word` / `N>&word`: when the operator is `>` or `N>` and the character right after it is `&`
                                                #   followed by something other than a digit or `-` (so OPERATOR_RE's descriptor alternative did
                                                #   not match), the `&` is skipped and the rest is the target, with the same effect as `&>word`
                                                #   (bash sends stdout and stderr to the file `word`). An operator followed by no word
                                                #   → the segment is untokenizable (rule c: `untokenizable-gtm-command` when the command carries
                                                #   an `UNTOKENIZABLE_DENY_TOKENS` hit, §4.2 "Fail mode"). B1 tests: `echo x > "gtm/state/a b"`
                                                #   denied with target `gtm/state/a b`; a redirect whose operator starts at offset 7 (bit 2,
                                                #   `re.LOCALE`, set: `echo x > "gtm/state/a b"`), at offset 2 (`re.IGNORECASE`) and at offset 64
                                                #   (`re.VERBOSE`) each yield the right target and no exception (RED with `re.match(…, pos)`);
                                                #   `echo x >&gtm/state/y` (cwd `H/.claude`) denied with target `gtm/state/y` (RED when the
                                                #   `&` is kept in the target); `cat
                                                #   <gtm/state/x`, `cmd 2>&1` and `echo x >&2` yield no write target and no untokenizable verdict;
                                                #   `echo x &> gtm/state/y` (cwd `H/.claude`) denied. **End to end (B2, through the patched
                                                #   `bash_gate.sh` + `pretooluse_bash.py` copies, non-GTM session; B1 asserts the same two
                                                #   commands at `decision()` level as `(False, …)`):** `python3 -m pytest
                                                #   tools/gtm/tests -q 2>&1 | tail` (it names the deny token `tools/gtm`) and `echo x >&2`
                                                #   run with cwd `~/.claude/tools/gtm` (the deny-token cwd arm, §4.2 "Fail mode") are ALLOWED
                                                #   (each RED when `&` splits them, because rule c's `untokenizable-gtm-command` is
                                                #   unconditional in every session for a deny-token command)
def runbook_hosts(tier_systems: Iterable[str]) -> tuple[set[str], set[str]]   # (read_hosts, login_hosts) from
                                                #   `read_runbook(s)` (the committed runbook, above) for each ALREADY-TIERED
                                                #   system s (runbook_hosts never re-tiers; a None runbook contributes nothing; a raise
                                                #   propagates). Callers tier channel
                                                #   names first with `system_names.tier_system_of(name: str, pack: dict | None = None) -> str`
                                                #   (03_schemas.md §3.22 API)
def write_notice_file(slug, kind, severity, title, body, *, push: bool = False, dedupe_key: str | None = None,
                      created_by: str = "hook", action_id=None, request_id=None, system=None, card_id=None) -> str
                                                #   07_notices_schedules.md §7.1 schema, atomic; the keyword set mirrors notices.write_notice's
                                                #   (07 §7.1 API). `push` is BEHAVIOUR ONLY and is not a record key except as §7.1's own `push`
                                                #   field (written exactly as notices.write_notice writes it); `dedupe_key`, `created_by`,
                                                #   `action_id`, `request_id`, `system`, `card_id` are §7.1 record fields (null when not passed);
                                                #   no other keyword is accepted (TypeError, so an unknown kwarg can never become a record key).
                                                #   slug may be "runtime"; dedupe check + create under S/notices/<slug>/.lock; push=True →
                                                #   best-effort osascript (2 s timeout) + pushed.jsonl row under S/notices/pushed.lock; never
                                                #   renders GTM_Operator.html (hook latency). The IMP-22 parity test passes each of these keywords
                                                #   to both writers and compares the records. **Test-mode guard (00_global_paths.md §1.1
                                                #   consequence 3):** it calls `gtm_env.refuse_real_state(R, None)` before any write, exactly as
                                                #   notices.write_notice does; `RealStateRefused` propagates to the caller, which logs
                                                #   `gate-fault` and writes nothing (a notice write never changes a decision). B1 test: with
                                                #   `GTM_TEST=1` and `R` resolving to the real root, the call raises and nothing is written
def browser_host_get(session_id, server) -> dict | None; def browser_host_set(session_id, server, host, url) -> None; def browser_host_clear(session_id, server) -> None
                                                #   S/browser_hosts/<session_id>.json, atomic replace (I17). `session_id` must match
                                                #   `^[A-Za-z0-9_-]{1,128}$`, else ValueError (callers: gate-fault) — it names a file
def append_isolation_hit(row: dict) -> None                # under S/isolation_hits.lock
def machine_written(target_canon: str) -> str | None       # THE one predicate for G-W `machine-written-path` AND G-B rule c's machine-written arm
                                                #   (§4.3 list: S; every GTM home's .claude/gtm/state/; activity-log files incl. `*.jsonl.ids.*.tmp`
                                                #   staging files and the owner-facing mirror files (`mirror_files()` below); H/paths.scoreboard;
                                                #   non-`.md` under snapshots_dir;
                                                #   mission `*.json`/`*.jsonl`; <H>/.playwright-mcp/) — returns the matching class name or None;
                                                #   raises SiblingPackUnreadable when any GTM home's pack is uncommitted (it must enumerate every
                                                #   home's paths.* to answer). DECIDED (wave1d): callers' fallback on that raise mirrors rule d1's
                                                #   own pattern, not a blanket allow — **in GTM scope, deny every target** (`gate-fault`; a
                                                #   machine-written class this session's own company cannot enumerate must not be judged "not
                                                #   machine-written"); **outside GTM scope, deny only when the target is under `S` or under any
                                                #   registered GTM home's toplevel** (`company.gtm_slugs()` resolved to each home's `H` — a
                                                #   registry read, never `git`; **but `gtm_slugs()` and `resolve_home()` CAN raise
                                                #   `CompanyError`** (an unreadable or non-object registry, a `~user`/relative root, an
                                                #   Agency-rooted entry, 00_global_paths.md §0.1 input rules; corrected (wave1e), finding
                                                #   wave1d-n2 — the wave1d text said this read "cannot itself raise"). **Fallback (DECIDED
                                                #   (wave1e)):** when `gtm_slugs()` raises, deny only a target equal to or under `S` (computable
                                                #   from `company.claude_dir()` alone) and log `gtm-slugs-unreadable`; when `resolve_home()`
                                                #   raises for one slug, that slug contributes no home root and is logged the same way; in GTM
                                                #   scope every target is still denied (above). **Stated residuals:** (1) while the registry is
                                                #   unreadable, a non-GTM session's write under a home's `.claude/gtm/state/` outside `S` is not
                                                #   prevented (the hook cannot name the home); (2) **mirror files of an unreadable pack**: the
                                                #   owner-facing mirror (`mirror_files()` below) lives at the pack's TOP-LEVEL `mirror_dir`,
                                                #   which may be anywhere on disk (not under `H`), and its path is known only from the pack
                                                #   itself — so while that pack is uncommitted/unreadable a non-GTM session's write to its
                                                #   mirror `.md`/`.html` is allowed; the detect-after is `activity_log.render_mirrors`, which
                                                #   rewrites both files from the company's activity-log JSONL on its next run, `activity_log.py`
                                                #   `render_mirrors`) — a target elsewhere on disk is
                                                #   allowed (log `sibling-pack-unreadable` with the bad slugs either way; DECIDED (wave1d): the
                                                #   safest option that keeps non-GTM tool-writing sessions elsewhere on the machine from being
                                                #   blocked by an unrelated company's uncommitted pack, while never admitting a target this session
                                                #   cannot rule out). `load_pack_safe`/`sibling_packs` are memoized per hook process (§4.2), so a
                                                #   raise costs at most one `git show` per home per G-W invocation, same budget as rule c. P2 parity test: for a
                                                #   fixture of every class, G-W and rule c both deny (neither keeps its own list)
def mirror_files(slug, pack) -> list[str]                 # the owner-facing activity-log mirror, EXACTLY as activity_log.render_mirrors writes it:
                                                #   for a pack with a TOP-LEVEL `mirror_dir` key (activity_log.resolve_paths reads
                                                #   `pack.get("mirror_dir")`, not `paths.mirror_dir`), the TWO files
                                                #   `canon(expanduser(mirror_dir)) / f"{basename}.md"` and `… .html`, where basename =
                                                #   `pack.get("mirror_basename") or _default_mirror_basename(slug, pack)`; [] when the pack has
                                                #   no `mirror_dir`. A relative `mirror_dir` (activity_log resolves it against its process cwd)
                                                #   is judged H-relative here AND refused by the pack validator (`requests/04_hooks.md` R31,
                                                #   `mirror_dir_not_absolute`), so it never occurs in a committed pack. Env
                                                #   `TS_ACTIVITY_MIRROR_DIR` (activity_log's test override) is IGNORED by hooks — they read the
                                                #   committed pack only. Implemented by calling `company.mirror_files(slug, pack, H)` — a pure,
                                                #   env-free helper that activity_log.resolve_paths/render_mirrors also call, so the two cannot
                                                #   drift (`requests/04_hooks.md` R31; hooklib never imports activity_log). B1 test: a pack with
                                                #   `mirror_dir: "~/Desktop/TS_Mirror"` and no `mirror_basename` → both `.md` and `.html` under
                                                #   that dir are machine-written (G-W Edit and a rule-c `echo x >` denied), and setting
                                                #   `TS_ACTIVITY_MIRROR_DIR` changes nothing (each RED when `paths.mirror_dir` or one file is used)
def trust_root_path(target_canon: str) -> bool             # G-W `trust-root` AND rule c: the live R/tools/gtm/ subtree (§4.3 "Trust roots") and
                                                #   R/telemetry/pricing.json; pure text test on canon strings
def authorized_static_action(slug: str, action_id: str) -> dict   # G-B rule n (§4.2): the fold record of an AUTHORIZED website_static
                                                #   action via the isolated `act.py status --action <id>` subprocess (10 s); raises
                                                #   ActionNotAuthorized on any other outcome (callers DENY with reason `gtm-git-write:patch-not-authorized`, never allow)
def authorized_static_actions(slug: str) -> list[dict]   # the same, `act.py status --state authorized`, filtered to website_static rows
def patch_paths(patch_bytes: bytes) -> set[str]            # union of the a/ and b/ paths of every `diff --git` header (§4.2 rule n); raises on none
UNTOKENIZABLE_DENY_TOKENS: frozenset[str]                  # §4.2 "Fail mode": the narrow deny set (NOT the §4.7 forwarding list)
PHI_READ_VERBS: frozenset[str]                             # §4.2 rule j operand (v): the file-reading verbs whose bare operands are judged
OFFSERVER_MUTATING_NAMES: tuple[str, ...]; OFFSERVER_MUTATING_GLOBS: tuple[str, ...]   # §4.1 "Other playwright servers";
                                                #   OFFSERVER_MUTATING = (names, globs); §4.8 item 3's shell globs are parity-tested against it
def gtm_session_write_verdict(target_canon: str, environ, payload) -> str | None
                                                #   THE GTM-scope write-scope predicate (§4.3 "GTM-scope clauses"), shared by G-W and G-B rule c's
                                                #   GTM-scope arm; returns the deny reason or None (parity test: same verdict on every fixture)
def gtm_scope(environ, payload: dict) -> str | None       # the company slug when CLAUDE_GTM_COMPANY is set, "*" when payload.agent_type ∈ GTM_SEATS without it, else None (payload arm UNVERIFIED for Bash/Read/Grep/Glob payloads — probe q, §4.4)
def agency_scope(environ, payload: dict, cwd: str) -> bool   # THE Agency-boundary scope (00_global_paths.md §0.4 "The Agency boundary outside GTM scope",
                                                          #   DECIDED there, binding on B1/B2; plan §20.9a binds "every phase and every agent"; plan §7.4
                                                          #   lets `/gtm` missions run from ordinary sessions): True when gtm_scope(environ, payload) is not
                                                          #   None, OR payload `agent_type ∈ DEPARTMENT_SEATS` (seat_sets()) and norm(cwd) is NOT equal to or
                                                          #   under norm(agency_root()) or norm(str(gtm_env.real_agency_root())) (text only, no filesystem
                                                          #   call) — so Agency's own repo-local agents working inside Agency are unaffected. Used ONLY by
                                                          #   G-A rule 3b, G-B rule i and the path gate's rule 1 (`agency-boundary`); PHI rules stay on
                                                          #   gtm_scope. Every deny it scopes is unconditional (00 §0.4). The payload arm is UNVERIFIED for
                                                          #   Bash/Read/Grep/Glob payloads (probe q, §4.2; same fallback: inert when absent)
def agency_root() -> Path                                 # = gtm_env.agency_root(os.environ) (re-export, never a copy) = Path(A), 00_global_paths.md §0.1 "The Agency root `A`": `Path(gtm_env.real_home())/"Desktop"/"Agency"`
                                                          #   outside test mode (the passwd home, NEVER `HOME`), `Path.home()/"Desktop"/"Agency"` in test mode
                                                          #   (gtm_env.test_mode; resolved at call time; tests set HOME). Every Agency comparison and
                                                          #   short-circuit in this file — canon step (3), canon step (4)'s walk stop, the §4.2 copy-walk
                                                          #   skip, `is_agency_github_url`'s `file://` arm, agency_scope's cwd test — compares against
                                                          #   BOTH norm(agency_root()) and norm(str(gtm_env.real_agency_root())) (00 §0.1: "compares against
                                                          #   both `A` and `real_agency_root()`"), so a tmp-HOME test run never stats the real Agency tree.
                                                          #   The ROOT side of every comparison is
                                                          #   norm() text only (00_global_paths.md §0.1 I14: no filesystem call on Agency), the TARGET side is canon(),
                                                          #   whose step (3) returns an Agency-bound path as text before any filesystem call and whose step (4)
                                                          #   stops a symlink walk at the first Agency-bound target — so `~/Desktop/AGENCY/x` and a symlink into
                                                          #   Agency are both caught and nothing inside Agency is ever stat'd, read or listed (G-W runs in Agency's
                                                          #   own development sessions too). Agency itself being a symlink is 00_global_paths.md §0.1's readlink
                                                          #   rule, not this helper's. Every recursive enumeration a hook performs (rule c's copy walk, §4.2)
                                                          #   skips a directory whose text path is equal to or under either Agency root without entering it
def phi1_root() -> Path                                    # the same rule as agency_root(): `Path(gtm_env.real_home())/"Desktop"/"OtherCompany Files"` outside test
                                                          #   mode (never `HOME`, so `HOME=/tmp/h` in a command cannot move the PHI root), `Path.home()/…` in
                                                          #   test mode; rule j and path-gate rule 4 also treat `Path(real_home())/…` as a phi1 root in test
                                                          #   mode (compare against both, as for Agency)
def phi1_allowlist() -> dict | None                        # S/othercompany_read_allowlist.json, None when absent/unreadable (03_schemas.md §3.20)
def hipaa_scope(company: str) -> bool                     # the committed pack (load_pack_safe) has `regulated ∋ "hipaa"`; a pack that loads None → True
                                                          #   (fail closed); company "*" (seat-only scope) → True when any gtm_slugs() pack is hipaa or loads None
def temp_roots(payload: dict) -> list[str]                # canon of: os.path.realpath(tempfile.gettempdir()), "/private/tmp", and payload
                                                          #   `scratchpad_dir` when it is a non-empty string (00_global_paths.md §1.2 "OtherCompany read scope")
def phi_allowed_roots(company: str, payload: dict) -> list[str]
                                                          # 00_global_paths.md §1.2 "OtherCompany read scope" (DECIDED there): canon of the session company's
                                                          #   home H (seat-only scope "*": every gtm_slugs() home), every `othercompany_read_allowlist.json`
                                                          #   folder, R, and temp_roots(payload). `phi_denylist` path entries still win inside them (rule
                                                          #   order: the denylist rules run first). An unresolvable H → that root is omitted (fail closed)
def phi_unreadable_roots(company: str, payload: dict) -> list[str]
                                                          # the roots left open while phi_denylist() is PHI_UNREADABLE (00 §1.2): canon of H (seat-only
                                                          #   scope: every gtm_slugs() home), R and temp_roots(payload) — the allowlist folders are NOT
                                                          #   included (a Desktop path entry could have named any of them)
from system_names import GTM_SEATS, DEPARTMENT_SEATS, BROWSER_SEATS, seat_sets   # re-exported, never redefined here
```

**One notice format, two writers (IMP-22).** Hooks write notices with `write_notice_file` (no
render, 2 s push timeout) and act.py/tools with `notices.write_notice` (WP-D, 07_notices_schedules.md
§7.1). B1 adds a parity test, `hooks/tests/test_gtm_notice_parity.py`, which imports both and
asserts, for the same inputs: identical record keys and values except `notice_id`'s random suffix and
`created_at`; the same `notice_id` grammar; that a notice created by either writer suppresses the
other's creation for the same open `dedupe_key` (same `S/notices/<slug>/.lock`); and one
`pushed.jsonl` row per successful push from either (osascript shimmed). It runs once both WPs
have landed (B1 consumes `notices`, 08_seats_wps.md §9).

**Seat constants — defined once, in `tools/gtm/system_names.py` (A1; F-seats).** `system_names`
holds `GTM_SEATS`, `DEPARTMENT_SEATS`, `BROWSER_SEATS` (tuples) and
`seat_sets(*, log: Callable[[str, dict], None] | None = None) -> tuple[set[str], set[str], set[str]]`
(IMP-14). Each returned set is the **union** of its committed constant and `model_policy.json`'s
`gtm_seats`/`gtm_department_seats`/`gtm_browser_seats` list (IMP-05; 05_approver.md §5.5):
the policy can add a seat, never remove one, so an uncommitted `model_policy.json` edit cannot take
a seat out of gate-gtm's enforcement, budget counting or sequential-browser rule, and
`model_policy.json` need not be a TRUST_PATH. When the policy file or a list is missing or
unreadable, the constants alone are returned and `log("gtm-seats-from-default", {"missing":
[<list names>]})` is called; when a list omits a constant seat, `log("gtm-seats-policy-drift",
{"list": <name>, "missing": [<seats>]})`. `log=None` logs nothing; hook callers pass
`lambda d, f: _lib.log("gtm_hooklib", d, **f)`, tools pass their own logger. A1 tests: a policy
list missing `gtm-analyst` still returns it (falsified by returning the policy list alone); an
extra policy seat is included; an absent policy file returns the constants and calls `log` once
with `gtm-seats-from-default`. Every consumer — `gtm_hooklib` (re-export), `ai_budget.attribute_row`,
`agent_budget.py`'s `gtm_untagged` rule (03_schemas.md §3.13), `perf_report`, `validate_run` — imports them from
`system_names`; nobody keeps a copy. The copies that cannot import Python (`bash_gate.sh`'s
`GTM_SEAT_RE`, §4.7; the `settings.json` path-gate command, §4.8 item 5) and WP-J's
`model_policy.json` lists are checked by P2 parity tests **against `system_names`**.

Seat constants (also WP-J's `model_policy.json` values):
- `GTM_SEATS` (new, enforced everywhere): `local-presence-architect, social-media-strategist,
  measurement-architect, revenue-ops-architect, gtm-analyst, gtm-drafter, gtm-checker, gtm-operator,
  gtm-credential-setup`.
- `DEPARTMENT_SEATS` (existing, enforced only inside a GTM session): `marketing-director,
  conversion-architect, brand-architect, content-strategist, seo-architect,
  paid-acquisition-strategist, pricing-economist, video-producer, market-analyst`.
- `BROWSER_SEATS`: `gtm-analyst, gtm-operator, gtm-credential-setup`.

### 4.1 G-A `hooks/gtm_browser_gate.py` (WP-B1) — PreToolUse `mcp__playwright.*`

Inputs: `tool_name` (`mcp__<server>__<tool>`), `tool_input`, `session_id`, `agent_id`, `agent_type`,
`cwd`; env `CLAUDE_GTM_COMPANY`, `CLAUDE_GTM_SESSION`.

**Tool classes on `playwright-gtm`** (bare tool name after `mcp__playwright-gtm__`):
- ticketless read: `browser_snapshot, browser_take_screenshot, browser_console_messages,
  browser_network_requests, browser_network_request, browser_wait_for`; `browser_tabs` with
  `tool_input.action ∈ {list, select}` (**`select` clears the recorded host**, below);
  `browser_navigate` to an allowed read host (below).
- read-ticket: `browser_navigate` (to ticket `allowed_hosts`), `browser_click`, `browser_navigate_back`
  — exactly the read ticket's `allowed_tools` (03_schemas.md §3.6) — except that `browser_click` is
  refused on a money-capable system's hosts (rule 9b).
- write/batch ticket: exactly the ticket's `allowed_tools` ⊆ `{browser_navigate, browser_snapshot,
  browser_take_screenshot, browser_wait_for, browser_click, browser_type, browser_fill_form,
  browser_select_option, browser_press_key, browser_check, browser_uncheck, browser_file_upload,
  browser_handle_dialog, browser_navigate_back}`.
- setup ticket: `browser_navigate`, `browser_evaluate` (allowlisted script only).
- **always deny**: `browser_run_code_unsafe` and its older spelling `browser_run_code`,
  `browser_evaluate` outside a setup ticket, `browser_close` (persistent profile; memory rule "keep
  tabs open"), `browser_tabs` new/close, `browser_drag, browser_drop, browser_hover, browser_resize,
  browser_install`, `browser_press_sequentially` (typing goes through `browser_type`, the one form
  rule 9c binds), `browser_keydown`/`browser_keyup` and every `browser_mouse_*` tool (raw input that
  bypasses rule 9c), `browser_navigate_forward` and `browser_reload` (a page change with no host
  check; reload can resubmit a form), every cookie/localstorage/sessionstorage tool and
  `browser_storage_state`/`browser_set_storage_state` (they read or plant session credentials),
  `browser_route*`/`browser_unroute`/`browser_network_state_set`, and **any tool name not listed
  above** (default deny).
- mutating (decrement `max_mutating_calls`): `browser_click, browser_type, browser_fill_form,
  browser_select_option, browser_press_key, browser_check, browser_uncheck, browser_file_upload,
  browser_handle_dialog`.

**Pinned package version (DECIDED HERE).** The classes above are written against
`@playwright/mcp` **0.0.76** — the version the runtime pool already pins
(`live-testing/browser_pool.py` `_DEFAULT_MCP_VERSION`, `.mcp.json`) and the one whose tool names
this section uses (`browser_run_code_unsafe`, `browser_network_request`, `browser_drop` do not exist
in 0.0.70). `playwright-gtm`'s launch arguments pin the same version
(`requests/04_hooks.md` R17 asks 07 §7.x to change its `@playwright/mcp@0.0.70` pin). P2 test: the
tool list of the pinned package is vendored as `hooks/tests/fixtures/playwright_mcp_tools.txt`
(regenerated from the package, never hand-edited) and every name in it is classified by exactly one
of: ticketless read, read-ticket, write/batch-ticket, setup, always-deny-by-name, or default-deny;
the test also asserts the pinned version string equals `_DEFAULT_MCP_VERSION` and the `playwright-gtm`
launch argument, so a version bump that adds a tool fails until the tool is classified.

**Allowed read hosts (ticketless navigate)** = company identity domains (`identity_allowlist.domains`
∪ `brands[].domains`) ∪ `runbook_hosts({tier_system_of(c, pack) for c in scope.channels_in_scope})`
read + login hosts (03_schemas.md §3.22). Host match = `host_matches` (exact or subdomain, lowercased).

**Host tracking (every admitted navigate).** Whichever rule admits a `browser_navigate` (6 or 13),
G-A writes `S/browser_hosts/<session_id>.json["playwright-gtm"] = {"host", "url", "ts"}` (atomic
replace; one file per session, so concurrent sessions of different companies never read-modify-write
one shared file) before returning. For every other ticketed tool, rules 3, 4s, 7b, 7c, 8 and 9b
read that entry; a **missing entry or one older than 60 min → deny `host-unknown`**. **Tab switching
(F-tabs):** `browser_tabs` with `action: "select"` changes the active page without a navigate call,
so before allowing it G-A **deletes** the session's `playwright-gtm` entry; the next ticketed tool
then denies `host-unknown` until a `browser_navigate` re-records the host. **HIPAA packs** (§4.1
"HIPAA packs: no raw page text in G-A records"): the entry's `url` is the redacted form stored
there, never the raw URL. B1 test: with a bound
write ticket, navigate to an allowed host → `browser_tabs` select → `browser_click` is denied
`host-unknown` (goes RED when the delete is removed); a following navigate to an allowed host
re-admits the click. **Page-URL refresh (required; was a "follow-up").** Navigation caused by a
click, a form submit, `navigate_back`, or a `target=_blank` click that opens (and may activate) a
tab on another host issues no navigate call, so the pre-call record can lag the real page. G-A
therefore also runs as a **`PostToolUse` hook on `mcp__playwright-gtm__.*`** (same module, entry
`gtm_browser_gate.py post`, §4.8 item 8): it reads the tool result's `Page URL: <url>` line with
`gtm_hooklib.page_url` (the one parser, §4: the last match of `system_names.PAGE_URL_RE`) and (1)
replaces the session's recorded entry with that URL's host and URL; (2) when that URL fails rule 3
(`gtm_hooklib.phi_url_hit(url, company)` returns a label — a host, host-suffix **or `url_prefixes`**
hit — or raises `PhiDenylistUnreadable`), rule 3b, or rule 4 for this company, it appends an isolation hit (`kind` `phi_page` / `agency_page` / `identity_other_company`,
03_schemas.md §3.21), sets the bound write/batch/setup ticket (if any) to `stopped` exactly as the
rule-4/7b isolation outcome below does, writes an urgent `isolation_hit` notice, and deletes every
file the result names under `<home>/.playwright-mcp/` (a snapshot or screenshot of that page), then
returns a PostToolUse `decision: "block"` with a reason naming the host (Claude Code feeds it back to
the agent; the result text itself was already delivered — this is detect-after for that one call,
and every later call is judged on the refreshed host, so a second read of the page is denied); (3) a
result with no `Page URL:` line leaves the record unchanged. A result whose `Page URL:` line cannot
be parsed deletes the record (the next call that needs it denies `host-unknown`). Fail mode:
any exception deletes the session's record and logs `gate-fault` (fail closed for the next call),
never raises. **Probe r** (coordinator, plan §17, before B1 relies on it): capture a real
`PostToolUse` payload for `browser_click` and `browser_snapshot` on the pinned 0.0.76 server and
vendor it as `hooks/tests/fixtures/posttool_playwright_{click,snapshot}.json`, recording the field
that carries the result text and the exact `Page URL:` line shape; until probe r is recorded, the
PostToolUse half is built against the fixture and the pre-call rules below stand alone. B1 tests: a
click whose result reports a PHI host writes an isolation hit, deletes the named
`.playwright-mcp/` file and makes the next `browser_snapshot` deny `phi-host` (RED when the refresh
is removed); a click whose result's `Page URL:` is `https://x.example/r/abc/page2` under a
`url_prefixes` entry `https://x.example/r/abc` (host `x.example` not denylisted) records a `phi_page`
isolation hit and blocks, while one reporting `https://x.example/r/abcd` does not (RED when the
refresh checks hosts only); a result whose text carries two `Page URL:` lines is judged on the
last (RED with first-match); a result reporting an allowed host updates the record. Remaining gap (stated): the one
result that first revealed the page is in the transcript before the PostToolUse hook runs; the
ticket's `allowed_hosts`, the runbook `expect` checks, rule 7b and the gtm-operator's acting-as
checks remain the prevention for write tickets.

**Ticketless reads on a PHI-scoped company (rule 6, F-phi-read).** When the committed pack has
`regulated ∋ hipaa`, or any `phi_denylist` entry applies to `CLAUDE_GTM_COMPANY` (its `applies_to` is
absent or names the company) — and also when `phi_denylist()` is `PHI_UNREADABLE` or the pack does
not load (fail closed) — the
ticketless reads `browser_snapshot`, `browser_take_screenshot`, `browser_console_messages`,
`browser_network_requests`, `browser_network_request` and `browser_wait_for` need a **fresh**
recorded host (missing, cleared by a tabs `select`, or older than 60 min → deny `host-unknown`), and
rules 3, 3b and 4 are applied to that recorded host/URL before rule 6 admits them (deny `phi-host` /
`agency-boundary` / `identity-other-company`). For every other company rule 6 is unchanged. B1
tests: in a OtherCompany session, a `browser_snapshot` after a tabs `select` is denied `host-unknown`;
after a navigate that the PostToolUse refresh re-recorded as a PHI host it is denied `phi-host`; in
a OtherCompanyB session (no applicable entry) a snapshot after a tabs `select` is allowed (each RED
when its clause is removed).

**Decision table on `playwright-gtm`** (first match wins; "host"/"URL" = the navigate target for
`browser_navigate`, else the recorded entry above):

| # | Condition | Decision / reason |
|---|---|---|
| 1 | `CLAUDE_GTM_COMPANY` unset | deny `no-gtm-session` |
| 2 | `CLAUDE_GTM_SESSION` set and `payload.session_id` ≠ it, and tool not ticketless-read | deny `session-mismatch` |
| 3 | `gtm_hooklib.phi_url_hit(url, CLAUDE_GTM_COMPANY)` (§4; the one PHI URL predicate) returns a label — a `hosts`/`host_suffixes` entry whose `applies_to` is absent or contains the company (no company set → every entry), or **any `url_prefixes` entry** (03_schemas.md §3.20: same host, path equal to the prefix's or continuing it at a `/` boundary; never filtered by company) — or raises `PhiDenylistUnreadable` (`phi_denylist()` is `PHI_UNREADABLE`, §4: every URL counts as a hit, 00_global_paths.md §1.2). `url` = the navigate target for `browser_navigate`; for every other tool whose decision reads the recorded entry (every ticketed tool, and the PHI-scoped ticketless reads above) the recorded URL, when an entry exists (a missing one is left to `host-unknown` below). B1 tests (each RED when its clause is removed): with a `url_prefixes` entry `https://x.example/r/abc`, a ticketless `browser_navigate` to `https://x.example/r/abc/page2` is denied `phi-host` and to `https://x.example/r/abcd` is allowed (when `x.example` is an allowed read host); a write ticket's `browser_click` whose recorded URL is under that prefix is denied `phi-host`; with `phi_denylist.json` deleted while a hipaa pack is registered, a OtherCompanyB `browser_navigate` to its own domain is denied `phi-host` (RED when the missing-file branch returns an empty denylist) | deny `phi-host` (the unreadable case also logs `phi-denylist-unreadable`) |
| 3b | navigate URL satisfies `is_agency_github_url` (github.com and subdomains, codeload.github.com, raw.githubusercontent.com, api.github.com `/repos/<org>/agency…`, `file://` + either Agency root) | deny `agency-boundary` (00_global_paths.md §0.1); on servers other than `playwright-gtm` this row is scoped by `gtm_hooklib.agency_scope` (below "Other playwright servers") |
| 4 | navigate URL host matches another company's domains / other_businesses (`identity_hosts_other_than`), or `url_has_account_id(url, account_ids_other_than(company))` hits; for **non-mutating** tools (ticketless reads, read-ticket `browser_navigate`/`browser_navigate_back`) both helpers run with `exclude_shared=True` (plan §6.3: reads of a system both packs declare shared are T0). **When either helper raises `SiblingPackUnreadable`:** deny `gate-fault` for every write/batch/setup-ticketed tool and for any `browser_navigate` whose host is not an allowed read host of this company; other tools continue; always log `sibling-pack-unreadable` with the slugs (fail closed — an uncommitted sibling pack never opens rule 4) | deny `identity-other-company` + isolation hit |
| 4s | tool is mutating, or needs a write/batch/setup ticket, and the host or URL hits a value that BOTH packs declare in `shared_identifiers` (the values rule 4's `exclude_shared` dropped) — **unless** the candidate ticket (read without binding, as rule 6b) is a card-approved shared ticket: `action_class == "shared"`, a non-null `card_id` verified at mint by `cards.require_approved(ctx, card_id, f"authorize {action_id}")` — the subject `card-post --action` binds (02_act.md §2.4 `card-post`), so an approved card about any other subject cannot satisfy mint (`requests/04_hooks.md` R19, R32) — with the ticket's `card_subject` (recorded at mint) exactly equal to `"authorize " + ticket.action_id`, and every hit value, normalized, is in the ticket's `shared_values` (the action's `check1.shared_hits` values, copied at mint) — which falls through to the later rules (R5 and `read_only_hosts` still apply: `block_prod_mutations.py` runs beside G-A, §4.9). **A shared-system write on a host in `live-testing/allowlist.json`'s `read_only_hosts`** (e.g. the Scout host `app.example.com`) **stays R5-denied even with an approved card:** GTM browser clicks and writes there are out of scope (§4.9 IMP-07; plan §20.2; CSA CLAUDE.md "WHERE TO TEST"), so no browser ticket can execute such an action; the operator makes it himself (`act.py record-external --kind owner_executed`, 02_act.md §2.11) | deny `shared-system-write` — **not** an isolation hit, no breaker, no demotion (plan §20.2: an action on a shared system is a card, and executes only once that card is approved) |
| 5 | tool in always-deny set | deny `tool-forbidden` |
| 6 | ticketless read tool (incl. navigate to an allowed read host); for a PHI-scoped company the non-navigate reads first pass "Ticketless reads on a PHI-scoped company" above | allow (no log); a navigate records its host, a tabs `select` deletes it (above) |
| 6b | tool needs a **write, batch or setup** ticket (payload `agent_type` `gtm-operator` or `gtm-credential-setup`, 03_schemas.md §3.6 binding) and either `gtm_hooklib.ticket_paused(company, candidate)` returns a pause — `R/schedules/DISABLED`, `ST/PAUSE`, `ST/PAUSE.chain`, `ST/PAUSE.<ticket.system>`, `ST/PAUSE.<ticket.system>@<ticket.brand>` (or, for a `brand: null` ticket, any `ST/PAUSE.<ticket.system>@<b>`) (legacy names normalized, 03_schemas.md §3.10), or `S/PAUSE.trust` when `ticket_is_money(ticket)` (§4: money unless `money` is exactly `false`, which act.py writes on every batch ticket), or a step-0 pause-spool file naming the company (§4 `ticket_paused`; 02_act.md §2.3) — **except** that a ticket whose `revert_exempt` is exactly `true` skips `DISABLED`, `ST/PAUSE` and `ST/PAUSE.<system>[@<brand>]` and meets `S/PAUSE.trust` as a money ticket, and a ticket whose `stop_exempt` is exactly `true` skips only a breaker-written `ST/PAUSE.<system>[@<brand>]` (§4 `ticket_paused` "Ticket exemptions"; neither ever skips `PAUSE.chain`, a spool file or a cancel) — or `gtm_hooklib.ticket_cancelled(company, candidate, verified=<rule 7a's pre-lock `verify_ticket` result for this candidate, or None>)` returns a marker (evaluated inside `tickets_lock`; §4.1 "Ticket authenticity" "When, and the lock") — or, for a **mutating** tool on a **send-bound** write/batch ticket, now ≥ the ticket's `send_not_after` (below "Send window"); candidate = the ticket rule 7 would select, re-selected under `tickets_lock` without binding. With no candidate, only the `DISABLED`/`ST/PAUSE`/`ST/PAUSE.chain`/pause-spool part is checked (rule 7 then denies `no-ticket` anyway) | deny `paused` / `cancelled` / `outside-send-window` (F-pause: plan §6.8 — manual `PAUSE`/`DISABLED` block "all T1+ actions and write tickets", `PAUSE.<system>` that system's write tickets, and a broken chain refuses every act.py write, so a live ticket that kept clicking would produce exactly the unlogged platform change the §0 assertion `platform_changes_unlogged_7d = 0` forbids; plan §20.7 — a cancel from any channel prevents the action; a ticket minted before any of these must not keep the browser writing for up to 30 min). Read tickets are never checked here (reads stay allowed under every pause). Any error reading pause or cancel files → deny `gate-fault` for these ticketed tools (fail closed) |
| 6c | tool is **mutating** (the §4.1 mutating list) under a write or batch ticket, the host (navigate target, else the recorded host) is in `gtm_hooklib.money_hosts()` (`money_hosts()` raising → **any** host counts as a money host, §4 `read_runbook` "Callers' fallback"), and `gtm_hooklib.activation_state().get("r22_money_residual_ruling")` is not a non-empty string — `activation_state()` returns it only from an operator-signed record it verified (§4), so an unsigned or unverifiable file counts as absent (`activation_state()` raising → the same) | deny `money-residual-unratified` (below "Money-host activation precondition"; no isolation hit) |
| 7 | needs a ticket; no admissible ticket (03_schemas.md §3.6 binding) | deny `no-ticket` / `ticket-bound-to-other-agent` / `ticket-expired` |
| 7a | the candidate is a write, batch or setup ticket, and the call is **mutating** or binds a `pending` ticket; and `gtm_hooklib.verify_ticket(company, candidate)` raises, or its result's `mint_sha256` ≠ `ticket_mint_digest(candidate)`, or its chain `state` is not live (`closed`, `consumed`, `abandoned`, `expired`, `stopped` past grace), or `signed_required` is true and `signed_ok` is not exactly `true` (below "Ticket authenticity") | deny `ticket-unverified` (no isolation hit, no breaker; logged with `ticket_id` and the failing clause) |
| 7b | write/batch/setup ticket: judge every `(key, id)` in `system_names.url_target_ids(ticket.system, url)` (below "URL ids"; URL = navigate target, else the recorded URL), ids normalized with `normalize_account_id`, **by key class** (below "Rule 7b key classes"). **Identity class** (`key ∈ system_names.IDENTITY_KEYS`, which contains `ACCOUNT_LEVEL_KEYS`), in this order: (i) the id is in none of this pack's `identity_allowlist.*` ∪ `accounts[].account_id` and is not the ticket's `target_ids[key]` → deny `target-not-allowlisted` + isolation hit; (ii) the ticket carries a value for `key` and the id differs from it → deny `target-not-in-ticket` (no isolation hit, no breaker: an allowlisted object of this company, e.g. the other brand's GBP location); (iii) the ticket carries no value for `key` → admit only when the id is **attributable to `ticket.brand`** (below "Rule 7b key classes"), else deny `target-not-in-ticket`. **In-account class** (every other key): the id differs from the ticket's `target_ids[key]` (or the ticket has no value for `key`) and is not admitted as a created object (below) → deny `target-not-in-ticket` — **no** isolation hit, no breaker. **Positive proof (mutating calls only; below "Target proof on id-less URLs"):** on a write or batch ticket whose system has a proving key `pk = system_names.proving_key(ticket.system)` (not None), a **mutating** call is admitted only when the URL's `url_target_ids` contain `(pk, v)` with `v` equal (normalized) to the ticket's `target_ids[pk]` (for a batch ticket, to one of its items' values); a ticket that carries no value for `pk` (`target_ids` of `{}`, no `target_ids` field, a batch ticket any item of which lacks it) proves nothing — otherwise, and in that case, deny `target-unproven` (no isolation hit, no breaker) — unless the system's committed runbook declares `identity_in_url: false` with a named acting-as step (then admit and log `target-unproven-admitted`) | deny `target-not-allowlisted` + isolation hit / `target-not-in-ticket` / `target-unproven` (FID-02's positive allowlist on the browser path, bound to the ticket's own target and brand so a ticket for one brand never writes to the other brand's objects on a shared host: plan §6.3 "create/modify anything whose account_id/page/location/domain fails §7 → NEVER" is no longer enforced only by the operator seat's acting-as prose **for every mutating call on a system whose URLs carry its proving id**; the runbook-declared `identity_in_url: false` systems keep the residual stated under "Target proof on id-less URLs") |
| 7c | write/batch ticket, tool **mutating**, and the URL (navigate target, else the recorded URL) matches a **`never_url_re`** entry of any committed runbook (`read_runbook`, §4; HEAD at `T`) whose `host` matches the URL's host (`host_matches`) — the runbook-declared identity/NEVER surfaces of that host (below "NEVER and identity surfaces") — **unless** the entry's `identity_row` is non-null and equals the ticket's `row_id` (for a batch ticket, never: batch rows are `*.post_schedule` only). A runbook read that raises → deny `gate-fault` for every mutating write/batch call | deny `never-surface` + isolation hit (kind `never_surface`, `requests/04_hooks.md` R53) |
| 8 | host check: host ∉ ticket `allowed_hosts` | deny `host-not-allowed` |
| 9 | tool ∉ ticket's allowed set | deny `tool-not-in-ticket` |
| 9b | read ticket, `browser_click`, and the host matches a host in `gtm_hooklib.money_hosts()` (runbook read/login hosts of every money-capable system, plus every runbook's `money_ui_hosts`; a host shared by a money and a non-money system counts as money; `money_hosts()` raising → **any** host counts) — **unless** the recorded URL matches one of that host's runbook-declared `read_click_targets[].url_re` for a system in the read ticket's `systems` (a clickless-read exception for inbox pages, "Inbox reads on money hosts" below), in which case G-A appends an audit row `{"ts","session_id","ticket_id","host","url","element"}` to `ST/read_clicks.jsonl` (for a HIPAA pack `url` and `element` are the redacted forms, "HIPAA packs: no raw page text in G-A records" below) and falls through | deny `read-click-money-system` |
| 9c | write/batch ticket and the tool carries input text: `browser_type.text`, each `browser_fill_form` `fields[].value`, each `browser_select_option` `values[]` entry, `browser_handle_dialog.promptText`; or `browser_press_key` whose `key` is not a named navigation key (`Enter, Tab, Escape, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, PageUp, PageDown`, optionally with a `Shift+` prefix) — any such value that is not admitted by "Input binding" below | deny `input-not-in-ticket` |
| 9d | write ticket, tool mutating, and the ticket is **enable-bound** (`commits_on_enable` is true, or `ticket_is_money(ticket)` and `commits_on_enable` is not exactly `false`) and its `budget_readback` does not prove the configured budget equals the signed amount (below "Enable binding on the browser path") | deny `enable-budget-unverified` |
| 10 | write/batch: mutating and `mutating_calls_used >= max_mutating_calls`; read/setup: `calls_used >= max_calls` | deny `ticket-exhausted` |
| 11 | `browser_file_upload`: any `tool_input.paths[i]` whose `canon` does not equal `canon(e.path, H)` for some entry `e` of the ticket's `upload_assets` — `H` = the ticket company's home; `e.path` is the **bound copy** act.py wrote at mint (03_schemas.md §3.6: absolute, `realpath(ST/assets/<action_id>/<sha256>)`; a home-relative value, as 02_act.md §2.4 `ticket` words it, is joined to `H`; `requests/02_act.md` item 85 (c), `requests/04_hooks.md` R58) — **and** that entry itself must be directly under `canon(ST/assets/<a>/)` for an action id `a` of the ticket (`action_id`, or a batch ticket's `action_ids`) with basename equal to `e.sha256` (a ticket naming any other file admits nothing) (`upload-path-not-in-ticket`), or whose **file bytes**, read by G-A, hash (sha256, bare lowercase hex) to anything other than **that same entry's** `sha256` (`upload-hash-mismatch`); a ticket with no `upload_assets` admits no upload | deny with that reason |
| 12 | `browser_evaluate` on setup ticket: `setup_script_allowlist()` raises (git failure, or the working-tree allowlist differs from HEAD), or sha256(UTF-8 `tool_input.function`) ≠ its `[ticket.script_id].sha256` | deny `script-not-allowlisted` |
| 13 | otherwise | allow: bind if pending, increment counters, persist ticket; on navigate update `S/browser_hosts/<session>.json`; log `allow-ticket` |

Rule 8's host for a non-navigate tool is the `S/browser_hosts/<session>.json` entry; missing/stale → `host-unknown`
(above). Tickets in status `stopped`, `consumed`, `closed`, `abandoned`, `expired` are never
admissible (rule 7).

**Ticket authenticity (rule 7a; plan §20.8 — approval is a signature only the operator's Touch ID
releases, verified at execute, and the browser call is the execute moment; plan header "every
external change still goes through act.py"; DECIDED (wave1c): verify against the chain on every
mutating call, not only at bind).** G-A decides a browser write from fields of the ticket file
under `S/tickets/` — `money`, `signed_amount`, `budget_readback`, `revert_exempt`, `stop_exempt`,
`action_class`/`card_id`/`card_subject`/`shared_values`, `target_ids`, `row_id`, `upload_assets`,
`dispatch_brief` — and `S/tickets/` is not a trust root (an interpreter write there is a stated
rule-c gap, §4.2), so a ticket file's presence proves nothing (the reason §4.3 rejects
presence-of-a-file for the trust-edit marker). So:
- **Digest.** `system_names.ticket_mint_digest(ticket) -> str` (A1, 03_schemas.md §3.22/§3.6;
  `requests/04_hooks.md` R62) = sha256 hex of the canonical JSON (`sort_keys=True`, separators
  `(",", ":")`, `ensure_ascii=False`) of the ticket with `system_names.TICKET_RUNTIME_FIELDS` removed
  — the fields G-A, ticket-release and act.py's close/reconcile change after mint (`status`,
  `bound_agent_id`, `bound_agent_type`, `bound_at`, `calls_used`, `mutating_calls_used`,
  `created_ids`, `stopped_at`, `closed_at`, `close_reason`, `reconciled`, each batch
  `items[].status`; A1's tuple is binding). act.py computes it at mint and G-A here; neither keeps
  its own copy.
- **Chain record.** `ticket --write`/`--write-batch`/`--setup` appends, in the same locked append
  that moves the action(s) to `ticketed`, a chained event carrying `{ticket_id, class,
  mint_sha256}` (R62 asks 02 §2.4).
- **Verification.** `gtm_hooklib.verify_ticket` runs `act.py status --ticket <ticket_id>` (§4
  "Isolated subprocesses", 10 s): act.py runs step 0 and `verify_chain` first, finds the chained
  mint event, and returns `mint_sha256`, `state` (from the chain: a ticket act.py closed,
  consumed, abandoned or expired is not live), `signed_required` (derived from the **action
  records**, never from the ticket file: a money row, or a revert child authorized by a signed
  approval) and `signed_ok` (a read-only re-verification by 05's `approvals_verify` — signature,
  its binding to `action_id`/`system`/`account_id` and `new_absolute_value` equal to the minted
  `signed_amount`, and the nonce reserved to holder `ticket:<ticket_id>` — reserving and consuming
  nothing; R62). Any failure → deny `ticket-unverified` (fail closed; never G-A's
  allow-on-internal-error path).
- **When, and the lock.** On every **mutating** call under a write, batch or setup ticket and on the
  call that binds a `pending` one; a non-mutating call of an already-bound ticket skips the
  subprocess (it changes nothing outside; rules 3–4, 7b and 8 still judge it). The subprocess runs
  **before** `tickets_lock` is taken (it may take up to 10 s; the lock's waiters time out at 5 s):
  G-A reads the candidate unlocked (a peek only — no rule decides on this unlocked read), verifies
  it, then takes the lock, re-selects, and requires the same `ticket_id` and
  `ticket_mint_digest(candidate)` equal to the verified `mint_sha256` — else `ticket-unverified`.
  **The same pre-lock call also runs, on a non-mutating call of an already-bound write, batch or
  setup ticket, whenever a cancel marker (`S/cancels/<slug>/<action_id>` for the candidate's action
  or a batch item's, or any `S/cancels/<slug>/_all.*`) exists** — its result feeds only rule 6b's
  `who` filter (§4 `ticket_cancelled`, `verified=`), never admits the call, and its failure on
  such a call is not a 7a deny (the filter is then simply not applied). **Rule 6b runs inside
  `tickets_lock`, on the re-selected candidate (DECIDED (wave1e), finding wave1d-M4, reconciling
  this bullet with "One critical section per ticketed call" below, which holds the lock from
  candidate selection):** its pause and cancel reads are the locked, authoritative check, and its
  `who` filter consumes the pre-lock verification result — no subprocess ever runs under the lock. The digest excludes the runtime fields, so G-A's own
  counter writes never invalidate it. Rules 4s and 6b read candidate fields before rule 7a, but a
  forged field there can only suppress a deny (only rule 13 allows), so the call still meets 7a.
- **Read tickets** are not verified (`ticket --read` appends no chain event, 02_act.md §2.4): a
  forged read ticket admits only reads — rule 9b denies its clicks on money hosts and rules 3/3b/4
  judge every navigate (stated).
- **Stated residual.** (1) A forger who also appends a well-formed chained mint event (and the
  action events it presupposes) to `actions.jsonl` through an unparsed shell form defeats the
  digest — the ledger's own residual, shared by every act.py decision — except on money and
  signed-revert tickets, where `signed_ok` still requires the operator's signature. (2) The runtime
  fields are only as strong as the file: a reset `mutating_calls_used`, or a rewritten
  `bound_agent_id`, on a ticket the chain still reports live is bounded by the digest-covered
  `expires` (≤ 30 min), not by the call cap. Both are listed in "The `$` residual" below.
B1 tests (each RED when rule 7a is removed or its clause dropped): a hand-written write-ticket file
of valid shape with no chained mint event (fixture `act.py status --ticket` exits 4) → its
`browser_click` denied `ticket-unverified`; a minted ticket whose `signed_amount` is edited
afterwards → denied `ticket-unverified` (digest mismatch), and one whose `revert_exempt` is flipped
to `true`, and one whose `money` is flipped to `false`, likewise; a minted, unedited ticket → allowed,
and after rule 13's counter write its next mutating call is still allowed (RED when the digest
covers runtime fields); `act.py status --ticket` timing out → denied; a money ticket whose
`signed_ok` is `false` → denied; a ticket the chain reports `closed` while its file says `bound` →
denied; with the verification subprocess shimmed to sleep 4 s, a read-ticketed `browser_navigate`
of the same company issued meanwhile from another process is decided without a `gate-fault` lock
timeout (RED when the verification runs inside `tickets_lock`). **`ticket_cancelled` `who` filter
(rule 6b; each RED when the filter is removed):** for a money ticket (`signed_required` true) with a
`S/cancels/<slug>/<action_id>` marker `{"who": "agent", …}`, `ticket_cancelled` returns `None` and
its `browser_click` is allowed (through DISABLED/PAUSE/PAUSE.trust/etc. as normal — the marker does
not stop it); the same marker with `{"who": "operator_script", …}` returns the marker name and the
call is denied `cancelled`; for a non-money ticket, a `{"who": "agent", …}` marker still returns the
marker name and denies `cancelled` (the filter narrows only signed-required tickets); a `_all.*`
marker on a money ticket with `{"who": "agent", …}` does not cancel it, while the same `_all.*`
marker still cancels a concurrently-pending non-money ticket of the same company; **(wave1e,
aligned with R77 (a) and 05 §5.1 step 5's agent-class)** for the money ticket, a per-action marker
with each of `{"who": "card_deny"}`, `{"who": "hand_made_file"}`, `{"who": "system:responded_by"}`,
`{"who": "bogus"}`, an empty file, and a `_all.*` marker whose body is not valid JSON each return
`None` (RED when any of them is left out of the excluded set), while `{"who": "approver_menu"}`
returns the marker name; with the fixture `verify_ticket` raising, an `{"who": "agent"}` marker on
that money ticket returns the marker name (filter not applied, fail closed); on a **non-mutating**
`browser_navigate` of a bound money ticket with an `{"who": "agent"}` marker present, the pre-lock
verification runs and the call is not denied `cancelled` (RED when verification is skipped for
non-mutating calls, which would deny it); and with the verification shimmed to record whether
`tickets_lock` is held, it is never called with the lock held (RED when `ticket_cancelled` calls
`verify_ticket`).

**One critical section per ticketed call (I25 for the browser).** Claude Code can issue parallel
MCP calls in one message, and G-A runs one process per call. For every tool that needs a ticket
(and for rules 4s/6b/6c/7b/9d, which read the candidate), G-A acquires `gtm_hooklib.tickets_lock(company)`
**before** candidate selection and holds it through rule 13's persist (or through the deny/stop
write of an isolation outcome); every read of `calls_used`/`mutating_calls_used`/`status`/
`bound_agent_id` and every write of them happens inside it. A lock timeout (5 s) → deny
`gate-fault`. Ticketless reads never take the lock. B1 test: two concurrent `browser_click` calls
(two processes released by a barrier) against a bound write ticket with one mutating call left →
exactly one allowed, the other denied `ticket-exhausted` (RED without the lock); two concurrent
first calls from two agent ids against one `pending` ticket bind it to exactly one agent.

**Isolation-hit outcome (plan §6.8 "any isolation hit → PAUSE.<system>").** Whenever rule 4, rule
7b's identity class, rule 7c or the PostToolUse refresh records an isolation hit while the call's
candidate is a write, batch or setup ticket, G-A — inside the same `tickets_lock` critical section —
also sets that ticket's `status` to `stopped` with `close_reason: "isolation_hit"` and `stopped_at`
and persists it; then it **releases the lock** and only afterwards writes the urgent pushed
`isolation_hit` notice for the company (`dedupe_key` `"isolation:<ticket_id>"`; `write_notice_file`
with `push=True` takes the notice and pushed locks and runs `osascript` for up to 2 s, which must
never hold `tickets_lock` against parallel MCP calls of the same company, whose 5 s lock timeout
would otherwise deny them `gate-fault`). A notice write failure logs `gate-fault` and changes no
decision (the stop is already persisted; the dedupe key covers repeats). B1 test: with
`osascript` shimmed to sleep 4 s, a read-ticketed `browser_navigate` of the same company issued
from another process while an isolation hit's notice is pushing is decided without a `gate-fault`
lock timeout (RED when the notice is written inside the lock). Every later call on that ticket is then inadmissible (rule 7), so the
ticket cannot keep admitting calls on other targets until `act.py` next runs
`breakers.ingest_isolation_hits` (02_act.md), which still writes `PAUSE.<system>` and handles the
demotion; the stopped ticket reconciles as any `stopped` one (03_schemas.md §3.6). A failure to
write the stop → the call is still denied and `gate-fault` is logged. B1 test: after a denied
navigate to another company's domain under a bound write ticket, the next click on an allowed host
on the same ticket is denied `no-ticket` (RED when the stop write is removed).

**Rule 7b key classes (FID-02; DECIDED HERE).** `system_names.IDENTITY_KEYS` (A1; requested,
`requests/04_hooks.md` R20) = `ACCOUNT_LEVEL_KEYS` (06_connectors.md §6.2: `customer_id`,
`ad_account_id`, …) plus the `target_ref` grammar keys that name an identity object — the business
page, location, property, container and site keys (03_schemas.md §3.22 grammar table); every other
grammar key is in-account (campaign, ad group, ad, asset, post, list, …: 03_schemas.md §3.4.1 kind
`in_account`, which no pack can enumerate, 03_schemas.md §3.4.1). The ticket's `target_ids` is the
`{key: value}` map act.py copies at mint — `system_names.target_ids(system, target_ref)` plus the
check-1-verified `id_fields` values of the action (02_act.md §2.8 check 1); a batch ticket carries
the union over its items; a setup ticket `{}` — and a create row's ticket also carries
`self_id_key` (the row's `self_id`, 03_schemas.md §3.4.1), both requested of 03 §3.6
(`requests/04_hooks.md` R20). A ticket **without** a `target_ids` field (a ticket minted before the
field lands) is treated as `{}` and every in-account id then denies `target-not-in-ticket` (never a
crash, never an isolation hit for in-account ids); on a system with a proving key, every mutating
call of such a write or batch ticket also denies `target-unproven` (below "Target proof on id-less
URLs": missing data never admits). **Created-object admission:** an in-account id
whose key equals the ticket's `self_id_key` is admitted when the URL's account-level id equals the
ticket's `account_id` (normalized), or the URL carries no account-level id and its host is in
`system_names.platform_hosts(ticket.system)`; G-A then records it in the ticket's `created_ids`
(persisted with rule 13) so later calls on the same new object are judged against it.
**Identity ids and brands (DECIDED HERE).** A company-level positive allowlist is not enough on a
multi-brand company: OtherCompanyB's two brands share hosts (both GBP locations are on
`business.google.com`) and both are in its allowlist, so admitting "any allowlisted id" would let a
restoration-brand ticket write to the remodeling location — bypassing brand-scoped owner pauses
(`PAUSE.gbp@remodeling`; A0022's `PAUSE.website_remodeling`, lifted only by card C7, plan §6.4),
which rule 6b checks against `ticket.brand` only, and landing content reviewed for one target on
another (plan §6.5 binds reviews to `target_ref` and `after`). So an identity id that differs from
the ticket's own `target_ids[key]` is always denied (clause (ii)), and when the ticket has no value
for the key (clause (iii)) the id must be **attributable to `ticket.brand`**: some
`accounts[]` entry with that normalized `account_id` has `brand == ticket.brand`, or the id is a
domain/host in `brands[b].domains` for the brand `b == ticket.brand`. A `brand: null` ticket
attributes an id only when the pack declares exactly one brand (and the id is attributable to it)
or the id is attributable to **no** brand (an `accounts[]` entry without `brand`, a domain in no
`brands[].domains`) — so a null-brand ticket never reaches a branded object whose id it does not
carry. The pack is the committed one (`load_pack_safe`); it loading None → deny `gate-fault`.
B1 tests (each RED when its clause is removed): a gbp write ticket on a URL with an unknown location id →
`target-not-allowlisted` + isolation hit; a **restoration**-brand gbp write ticket (its
`target_ids.location_id` = the restoration location) navigating to the **remodeling** location's URL
→ `target-not-in-ticket`, no isolation hit, both while `ST/PAUSE.gbp@remodeling` exists and when it
does not (RED when clause (ii) is removed); the same ticket with no `location_id` value → still
`target-not-in-ticket` (clause (iii): not attributable to `restoration`); a **remodeling**-brand
ticket on its own location → allowed; a `brand: null` gbp ticket with no location value on either
brand's location of a two-brand pack → `target-not-in-ticket`; a `google_ads` campaign-create ticket navigating to the
new campaign's URL in the same customer → allowed; a different, existing campaign id in the same
customer → `target-not-in-ticket` with no isolation hit and no ticket stop; the ticket's own
verified ids → allowed; a ticket with no `target_ids` field → no exception.

**Target proof on id-less URLs (rule 7b positive proof; plan §18's top risk; DECIDED HERE).** Rule
7b's clauses (i)–(iii) judge only the ids `system_names.url_target_ids(ticket.system, url)` finds, so a
URL that carries **no** identity id is judged by nothing — and that is the common case exactly where
the operator's one personal login administers every business: GBP managed from Google Search or the
`business.google.com` overview pages, Meta Business Suite pages without `asset_id`, WordPress admin
screens. There a write ticket for one company could click and type on another business's Page or
location (OtherCompany, an unmanaged business) with no deny and no isolation hit. So:
- **Proving key.** `system_names.proving_key(system) -> str | None` (A1, 03_schemas.md §3.22;
  `requests/04_hooks.md` R41) names, per system, the most specific identity key whose value
  identifies the object a write lands on (e.g. `gbp` → `location_id`, `meta` → `page_id`,
  `google_ads` → `customer_id`, and the property/container/site key for the analytics, tag and
  WordPress systems — illustrative; A1's table in `system_names` is binding), `None` for a system whose grammar defines no identity key. It must
  be a member of `IDENTITY_KEYS` (A1 test).
- **URL ids (DECIDED (wave1c): a dedicated URL extractor — `target_ids` parses the `target_ref`
  grammar only and returns `{}` for a URL, so reusing it would deny every mutating call).**
  `system_names.url_target_ids(tier_system, url) -> dict[str, str]` (A1, 03_schemas.md §3.22;
  `requests/04_hooks.md` R63) is the one URL extractor G-A uses (rule 7b clauses (i)–(iii), created-
  object admission and this check): a static per-system table of URL path patterns (e.g. gbp
  `…/locations/<id>/…` → `location_id`; google_ads `…/customers/<cid>/…` → `customer_id`) and
  query keys (e.g. google_ads `ocid`/`__c`, meta `asset_id`/`business_id`/`act`) — illustrative;
  A1's table is binding, and each pattern carries a URL fixture captured by the plan §17 probes —
  applied to the parsed URL, each value then normalized with `normalize_account_id`. It reads path
  segments and only **id-shaped** query values (`^(act_)?[0-9-]{1,40}$`), so it returns the same
  dict on a HIPAA pack's redacted-in-place URL (§4.1 "HIPAA packs"); a URL no pattern matches → `{}`.
  `system_names.target_ids(system, target_ref)` stays **mint-time only** (act.py's copy into the
  ticket, above); G-A never calls it on a URL. B1 tests use the URL fixtures of A1's table.
- **The check.** On a write or batch ticket whose system has a proving key `pk =
  proving_key(ticket.system)` (not None; a setup ticket is exempt — it carries `{}` by design and its
  one mutating tool, `browser_evaluate`, is bound by rule 12's script allowlist), every
  **mutating** call (§4.1 mutating list) requires the URL (the recorded URL; rule 7b runs after the
  PostToolUse refresh has replaced it with the page's real URL, §4.1 "Page-URL refresh") to carry
  `(pk, v)` among its `url_target_ids` with `normalize_account_id(v)` equal to the ticket's value (for a
  batch, one of the items' values). Otherwise deny **`target-unproven`** — not an isolation hit, no
  breaker, no ticket stop: an id-less URL is unknown, not proven foreign. **A ticket that carries no
  value for `pk`** — `target_ids` of `{}`, no `target_ids` field (read as `{}`, above), or a batch
  ticket any item of which lacks it — **proves nothing, so every mutating call under it is denied
  `target-unproven`** (DECIDED (wave1c): fail closed — missing data on the one check that closes
  plan §18's top risk must never admit; `requests/04_hooks.md` R61 asks 02/03 to refuse minting such
  a ticket, so this deny is the backstop, not the normal path). Non-mutating calls
  (navigate, snapshot, screenshot, wait) are unaffected, so the operator seat can still navigate to
  the object's own id-bearing URL and then act. Clauses (i)–(iii) still judge every id the URL does
  carry, before this check.
- **Runbook exception.** A system whose **committed** runbook (`read_runbook`, §4 — HEAD at `T`,
  never the working tree) declares `"identity_in_url": false` **and** `"acting_as_step": "<step
  id>"` naming a step of that runbook that carries an `expect` check of the acting-as identity is
  admitted without the proof; G-A logs `target-unproven-admitted` with `system`, `ticket_id`, `url`
  and the step id (the 06 runbook validator refuses `identity_in_url: false` without a valid
  `acting_as_step`, `requests/04_hooks.md` R41). A runbook read that raises → deny `gate-fault`.
- **The residual for `identity_in_url: false` systems (stated, in "The `$` residual" style).**
  Prevention = the runbook's acting-as `expect` step, the ticket's `allowed_hosts` (rule 8) and the
  gtm-operator's acting-as prose; detection = the change-history reconcile (06_connectors.md §6.4
  `change_history`: any platform change with no matching logged action) and the day-after verify.
  It is not a claim that the browser cannot reach another business's object on such a system. The
  coordinator lists every `identity_in_url: false` system as a plan §17 probe row (does any page of
  the write flow carry the id? if yes, the runbook drops the declaration) before P6 relies on it
  (`requests/04_hooks.md` R41).
B1 tests (each RED when the check is removed): a gbp write ticket with `target_ids.location_id` set,
recorded URL `https://www.google.com/search?q=other-company` (in its `allowed_hosts`), has its
`browser_click` denied `target-unproven` with no isolation hit and the ticket not `stopped`; the
same ticket's `browser_snapshot` there is allowed; its click on `business.google.com/…/locations/<its
id>/…` is allowed; a system whose committed runbook declares `identity_in_url: false` with a valid
`acting_as_step` is admitted and logs `target-unproven-admitted` (RED when the runbook exception
reads the working tree: an uncommitted `identity_in_url: false` does not admit); a gbp write ticket
with `target_ids: {}`, and one with no `target_ids` field at all, each has its `browser_click` on
`https://www.google.com/search?q=other-company` denied `target-unproven` (RED under the earlier "a
ticket with no value for its proving key is not judged" clause) while its `browser_snapshot` there
is allowed; a batch ticket one of whose items lacks the proving key is denied the same way; a setup
ticket (`target_ids: {}`) is not judged by this check.

**Input binding (rule 9c; plan §6.5 "any change to after invalidates reviews", §6.6, §20.6/§20.8).**
The gtm-operator reads untrusted page text (including platform "recommended budget" prompts), so
the text it enters is bound to the reviewed, and for `$` signed, values at the moment of commitment,
not only at mint and complete. Admissible set V = the `value`s of the ticket's `dispatch_brief.steps`
(03_schemas.md §3.6; filled only from structured before/after/account fields, 06_connectors.md
§6.4), each step carrying `value` (the filled string, or null) and `value_kind ∈ {text, amount}`
(requested of 03, `requests/04_hooks.md` R21). A candidate value c is admitted iff:
- **text:** `ws(c) == ws(v)` for some `text` step value v, where `ws` = Unicode NFC, strip, and
  collapse every whitespace run to one space (case-sensitive);
- **amount:** c matches `^\s*\$?\s*(\d{1,3}(,\d{3})+|\d+)(\.\d{1,2})?\s*$` and
  `Decimal(c without "$", "," and spaces) == Decimal(v)` for some `amount` step value v — so `45`,
  `45.00` and `$45.00` are the same amount and `450` is not;
- **money ticket** (`ticket_is_money`): every `amount` step's value must also equal the ticket's
  `signed_amount` (the verified signed payload's `after.new_absolute_value`, copied at mint,
  requested of 03 §3.6, R21) — checked again here, and a money ticket with no `signed_amount` admits
  no amount at all (deny). **On a money ticket, a candidate that matches the amount regex above is
  judged ONLY as an amount** — it is admitted only when `Decimal`-equal to `signed_amount` (and to an
  `amount` step value), never through text equality with a `text` step — so a `text` step whose
  value happens to be `450` cannot admit typing `450` on a ticket signed at `45.00`.
A checkbox/radio `fields[].value` of `"true"`/`"false"` is judged as text like any other value.
Named navigation keys pass `browser_press_key`; any other key (a printable character, `Backspace`,
`Delete`, a `Control+`/`Meta+` chord) denies. `browser_click`/`browser_check`/`browser_uncheck`
carry no value and are not judged by 9c (a click on a page-suggested amount is the stated residual
below). B1 tests (each RED when rule 9c is removed): on a money write ticket signed at `45.00`,
`browser_type` `450` → denied, `45.00`, `45` and `$45.00` → allowed, `browser_press_key` `4` →
denied, and with an added `text` step whose value is `450` a `browser_type` of `450` is still
denied (RED when amount-shaped candidates may match a text step); on a `gbp.description_edit` ticket, `browser_type` of text other than `after.text` → denied
and of `after.text` with collapsed whitespace → allowed; a `browser_fill_form` with one unlisted
field value → denied.

**Enable binding on the browser path (rule 9d; plan §20.13 "committed only at enable", FID-03;
DECIDED HERE — option (a)).** A paused campaign's (or a lead-enable object's) configured budget is
committed only when it is enabled, and on the browser path enabling is a **click**, which rule 9c
cannot bind (it binds only typed/filled values). The operator could sign "$45/day" while the object
is configured at $1,000/day, and the only prevention would be the gtm-operator's runbook
before-check — agent prose. So for every row with `commits_on_enable: true` (03_schemas.md §3.4.1 —
never a stop: a row whose authored `resulting_status` ∈ {`paused`, `removed`} cannot carry it, so rule
9d never applies to a stop's write ticket, `requests/05_approver.md` R84 amended wave1e;
05_approver.md §5.5 "Enable binding" (i)) browser execution is **`not_agent_executable` unless**
act.py, immediately before minting the write ticket, re-reads the object's configured budget
through the platform **API** (the connector's read path, never the browser) and it is
`Decimal`-equal to the signed `new_absolute_value`; mint then copies onto the ticket
`commits_on_enable: true` and `budget_readback: {"value": "<decimal str>", "unit", "read_at": "<UTC
ISO>", "via": "api", "target_ref"}` (`requests/04_hooks.md` R33 asks 02 §2.4 `ticket --write`, 03
§3.6 and 06 §6.x for the read method and the fields; a system with no API budget read — e.g. the
Angi/Thumbtack `lead_enable` rows until a read exists — refuses the browser ticket, exit 3
`enable_not_agent_executable`, and the operator makes the change himself, recorded with
`act.py record-external --kind owner_executed`, the plan §20.8 fallback). G-A's rule 9d is the
mechanical check at the moment of the click: on an enable-bound write ticket every mutating call is
denied `enable-budget-unverified` unless `budget_readback` is present, `via == "api"`,
`Decimal(value) == Decimal(ticket.signed_amount)`, `unit` equals the signed unit, `target_ref`
equals the ticket's action target, `read_at` parses and lies within `[created_at − 5 min,
created_at]`, **and now (`gtm_hooklib.now_utc`) is before `enable_not_after` = `read_at + 5 min`**
(derived here from `read_at`, not a separate ticket field; so an enable-bound ticket's mutating
calls stop 5 minutes after the read-back even though the ticket itself lives 30 minutes — the
window in which an out-of-band budget change can go unseen is bounded to 5 minutes; a later enable
needs a fresh ticket, and so a fresh read-back). A money write ticket that lacks `commits_on_enable` altogether is treated as
enable-bound (fail closed; 03 writes the field on every write ticket). Remaining (stated, added to
"The `$` residual"): the configured budget could be changed between the read-back and the enable
click — on the page by a click (a click on a suggested amount types nothing), or **out of band** by
another actor in that ≤ 5-minute window (the co-managing Agency SaaS identity of plan §20.9
`co_managing_systems`, or the operator in another tab) — which is residual (2) below. B1 tests
(each RED when rule 9d is removed): an enable-bound ticket signed at `45.00` whose
`budget_readback.value` is `1000.00` cannot `browser_click` (`enable-budget-unverified`); one with
no `budget_readback` cannot; one with `via: "browser"` cannot; one whose read-back equals `45.00`
and is fresh can; a money ticket without the `commits_on_enable` field and without a read-back
cannot; the fresh ticket's click at `read_at + 5 min + 1 s` is denied `enable-budget-unverified`
while its click at `read_at + 4 min` is allowed (RED when the `enable_not_after` check is removed).

**Inbox reads on money hosts (plan §5 inbox loop; rule 9b's exception).** The inbox run reads
Business Suite, Yelp for Business, Angi and Thumbtack consoles, which are also ad and pay-per-lead
consoles, so rule 9b would otherwise stop every read click there. For every `inbox`-class read path
on a money host, the runbook must either list a clickless `start_url` sequence (navigate + snapshot
only) or declare `read_click_targets: [{"host", "url_re", "why"}]` — URL patterns of pages that show
conversations/reviews and no money control — and the runbook validator (06, `requests/04_hooks.md`
R18) refuses an inbox read path on a money host that has neither. Where neither is possible, that
system's inbox read is an operator task (07's operator task list), never a wider exception. Read
clicks admitted by the exception are audited (rule 9b's row) and `validate_run` reports them. Each
platform's clickless-or-`read_click_targets` answer is a plan §17 probe row the coordinator records
before P6 enables the inbox run (`requests/04_hooks.md` R18). B1 test: with a runbook declaring
`read_click_targets` `^/inbox/` for `business.facebook.com`, a read ticket's click on
`https://business.facebook.com/inbox/x` is allowed and audited, and on
`https://business.facebook.com/adsmanager/x` is denied `read-click-money-system`.

**NEVER and identity surfaces (rule 7c; plan §6.3 "create/modify anything whose account_id/page/
location/domain fails §7 → NEVER", plan §20.6 NEVER class; the CSA operator directive "NEVER
CROSS-CONNECT THE OPERATOR'S OTHER BUSINESSES" — never create or join a Meta Business Portfolio,
never link/share an asset, pixel or dataset, a Page-switcher or asset picker is the most likely
failure mode; DECIDED HERE).** On the operator's one personal login, a write ticket for a
non-money, non-identity row (a post, a reply) on a host such as `business.facebook.com` can click
through to the same host's portfolio, people, partner and asset-sharing screens, and rule 7b cannot
tell those clicks apart on an id-bearing URL of the company's own Page. So every runbook may
declare, and the runbook of every system whose hosts offer such screens **must** declare (06
validator, `requests/04_hooks.md` R53), `never_url_re: [{"host", "url_re", "surface",
"identity_row": "<row id>" | null, "why"}]` — URL patterns (matched with `re.search` against the
URL's path plus `?query`, case-insensitive) of pages whose controls create or join a business
portfolio, add or remove people or roles, add partners, or share, link or claim assets, pixels,
datasets, catalogs or ad accounts (e.g. for `business.facebook.com`: portfolio creation,
`settings/people`, `settings/partners`, `settings/ad-accounts`, `settings/pages`, asset-sharing and
"request access" flows; illustrative — the committed runbook is binding). `surface` names the class;
`identity_row` names the one tier-table identity row (03_schemas.md §3.4.4) whose ticket may act
there (e.g. a reviewed role change the operator approved), or null for a pure NEVER surface that no
ticket may ever act on. Rule 7c denies every **mutating** write/batch call whose URL matches, with an
isolation hit and the ticket stop above, unless the ticket's `row_id` (`requests/04_hooks.md` R53
asks 03 §3.6 to copy it onto every write ticket; a ticket without it never matches) equals the
entry's non-null `identity_row`. Non-mutating calls are not judged (the operator seat may still
navigate and read). B1 tests (each RED when rule 7c is removed): with a committed meta runbook
declaring `{"host": "business.facebook.com", "url_re": "^/settings/people", "surface": "people",
"identity_row": null}`, a `meta.post_create` write ticket's `browser_click` on
`https://business.facebook.com/settings/people?business_id=<its own id>` is denied `never-surface`
with an isolation hit and the ticket stopped, and its `browser_snapshot` there is allowed; with
`identity_row: "meta.page_role_edit"`, a ticket whose `row_id` is `meta.page_role_edit` passes rule
7c and one whose `row_id` is missing does not; an uncommitted working-tree runbook edit that removes
the entry changes nothing (HEAD read).
**The click residual for NEVER and identity classes (stated, as for `$` below).** Rule 7c covers
only the URLs a runbook enumerates. A click on the same page that opens a portfolio or
asset-picker dialog **without** a URL change (a modal on an allowed page), a surface no runbook
listed yet, or an asset picker whose pre-checked entry is another business, is not seen by G-A:
the prevention is the runbook `expect` checks, the gtm-operator's acting-as prose (screenshot before
and after every linking or identity step, name every entity on screen) and rule 7b on id-bearing
URLs; the detection is the change-history reconcile (06_connectors.md §6.4) and the day-after
verify. It is not a claim that the browser cannot cross-connect a business. This residual is part
of the R22 ruling text (`requests/04_hooks.md` R22, amended by R53), so the operator ratifies it
together with the `$` residual before rule 6c admits any money-host write.

**HIPAA packs: no raw page text in G-A records (plan §20.4/§20.13; DECIDED HERE).** A named
reviewer of a dental practice, or a DM thread URL, implies patient status, and plan §20.4/§20.13 say
OtherCompany inbox content is never quoted into logs or reports. So when `gtm_hooklib.hipaa_scope(
CLAUDE_GTM_COMPANY)` holds (a pack that does not load counts, fail closed), G-A never writes a raw
`element` or a raw URL anywhere: in `ST/read_clicks.jsonl` (rule 9b), in every `.enforcement/log.jsonl`
row it writes (`target-unproven-admitted`, `would-block`, `allow-ticket`, `gate-fault`,
`phi-denylist-unreadable`, …), in isolation-hit rows (03_schemas.md §3.21) and in notices, the
`element` is `redact_text(element)` and every URL is `redact_url(url)` (§4: host, a path template
with every non-word segment starred, and the URL's sha256). The host-tracking entry
`S/browser_hosts/<session>.json` must keep what rules 3, 4, 7b, 7c and 9b match against, so for a
HIPAA pack its `url` is stored **redacted in place**: scheme, host and path kept, every query value
not matching `^(act_)?[0-9-]{1,40}$` (an id shape — the only query values `url_target_ids` and
`url_has_account_id` read) replaced by `redact_text(value)`, the fragment replaced by
`redact_text(fragment)`. **Stated residual:** the page's path is kept (the rules need its ids), so
a profile URL whose path names a person stays in the session's host file until the next navigate,
`browser_host_clear` or purge; `requests/04_hooks.md` R55 asks 07 to delete the session's
`S/browser_hosts/<session>.json` when `gtm_session.sh` exits and 02/07 to add `S/browser_hosts/`
and `ST/read_clicks.jsonl` of a HIPAA pack to `purge-untrusted`'s scope and 30-day purge, and asks 06
that a runbook `url_re`/`never_url_re` for a system in a HIPAA pack's scope never depend on a
non-id query value (it could not match the redacted form). B1 tests (each RED when the redaction is
removed): in a OtherCompany session, a read-ticket click admitted by rule 9b's exception with
`element: "reply to review by Jane Doe"` on `https://business.facebook.com/inbox/x?thread=Jane` writes
a `read_clicks.jsonl` row and a log row containing neither `Jane` nor `thread=Jane`, and a host
file whose `url` query value is a `sha256:` digest; the same click in a OtherCompanyB session writes
the raw values.

P2/B1 tests, each falsified by removing its clause:
- rule 6b: with a bound write ticket, writing `ST/PAUSE` makes the next `browser_click` deny
  `paused`; so does `ST/PAUSE.chain`; `ST/PAUSE.gbp@remodeling` denies a remodeling-brand gbp write
  ticket's click but not a restoration-brand one, and denies a `brand: null` gbp ticket's click;
  `S/PAUSE.trust` denies a money write ticket's click, a ticket **without** a `money` field and one
  with `money: "no"`, but not a `money: false` one; a `batch` ticket **without** a `money` field
  is blocked by `S/PAUSE.trust` and a batch ticket with `money: false` is not (RED with a class
  special case; precondition: R16, landed in 03_schemas.md §3.6); a step-0 pause-spool file for the
  company denies `paused` (§4 `ticket_paused`); `S/cancels/<slug>/<action_id>` for the ticket's
  action (and for one batch item) denies `cancelled`, as does an `_all.<ts>` marker newer than the
  ticket's `created_at` while an older one does not, and an `_all.<garbage>` marker whose timestamp
  does not parse (fail closed; RED with string comparison); a read ticket's `browser_click` under
  `ST/PAUSE` is still allowed.
- rule 4s (shared cards): with a fixture host `shared-fixture.example` declared shared in both
  packs and **not** in `read_only_hosts`, a `shared` write ticket with an approved `card_id` whose
  `shared_values` hold that host clicks there → passes G-A with no isolation hit; the same ticket
  clicking a shared value not in its `shared_values`, a ticket with `card_id: null`, or a ticket whose
  `card_subject` names another action (`"authorize act_x_2"` on `act_x_1`) or is absent, →
  `shared-system-write` (the last RED when the `card_subject` comparison is removed); and a
  card-approved shared ticket's click on the Scout host `app.example.com` (a
  `read_only_hosts` entry) passes G-A's rule 4s but is denied by `block_prod_mutations.py` R5 (the
  B2 test of §4.9 asserts that end to end: the Scout path is not browser-executable).
- rule 6b ticket exemptions (`stop_exempt`, `revert_exempt`): see §4 `ticket_paused` "Ticket
  exemptions".
- rule 7c: see "NEVER and identity surfaces" above.
- rule 6b send window: see "Send window" below.
- rule 6c: see "Money-host activation precondition" below.
- rule 9d: see "Enable binding on the browser path" above.
- rule 4: an uncommitted sibling pack (fixture home with no commit) makes a write ticket's click and
  a navigate to that sibling's domain deny `gate-fault` and logs `sibling-pack-unreadable` (RED when
  the helper returns the readable packs only); `…?ocid=1002003000` matches the stored
  `100-200-3000`; a stored `123` does not hit inside `9912345`; with OtherCompanyB↔CSA Scout declared
  in both packs, a OtherCompanyB ticketless navigate to the Scout host is allowed with no isolation
  hit, while a write-ticketed click there denies `shared-system-write` with no isolation hit and no
  breaker; declared in one pack only → `identity-other-company`; with `S/other_businesses.json`
  holding `{"meta_cross_connect": ["12864445"], "othercompany": ["othercompany-fixture.example"]}`, a
  OtherCompanyB ticketless navigate to
  `https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=12864445` (a runbook read host)
  is denied `identity-other-company` with an isolation hit, and so is a navigate to
  `https://othercompany-fixture.example/` (each RED when the other_businesses union is removed); with
  that file absent or unparsable, a write ticket's click denies `gate-fault` and logs
  `sibling-pack-unreadable` with `["other_businesses"]`.
- rule 7b: see "Rule 7b key classes" above.
- rule 9b: a read ticket's `browser_click` after navigating to an `ads.google.com` read URL is denied;
  on a non-money system's read host it is allowed; on `business.google.com` (a GBP host with no money
  row but listed in the gbp runbook's `money_ui_hosts`) it is denied (RED when `money_hosts()` omits
  `money_ui_hosts`).
- rule 11: with a write ticket whose `upload_assets` names the bound copy
  `ST/assets/<action_id>/<sha256>` (absolute, as 03 §3.6 writes it), a `browser_file_upload` of that
  copy is allowed; of the source file the action's `assets[]` named (outside `ST/assets/`) it is
  denied `upload-path-not-in-ticket`; of a bound copy of another action (`ST/assets/<other>/<sha>`)
  it is denied `upload-path-not-in-ticket`; the bound copy whose bytes changed after mint is denied
  `upload-hash-mismatch`; an entry written home-relative resolves against `H` and is allowed (each
  RED when its clause is removed).
- rule 12: an allowlist entry added in the working tree but not committed does not admit its script.

**Send window (rule 6b; plan §20.7; 03_schemas.md §3.11 FID-24 send-time re-check; TCPA).** Messages
to named people execute only outside quiet hours, and SMS only inside the TCPA send windows. act.py
re-checks both at `ticket --write` mint, but a write ticket lives 30 minutes, so a ticket minted at
19:59 could otherwise send at 20:20 — and on the browser path the send happens in G-A's hands, not
act.py's. So a write or batch ticket carries `send_bound` (bool) and, when true, `send_not_after`
(UTC ISO) = the minimum of `expires`, the next quiet-hours start for a `recipient_required` named
person, and the end of the current SMS send window for an SMS row (every item's window for a batch)
— computed by act.py at mint from the same inputs as the §3.11 re-check (`requests/04_hooks.md`
R34 asks 03 §3.6 and 02 `ticket --write`/`--write-batch` for both fields). G-A: a ticket whose
`send_bound` is missing or not exactly `false` is send-bound (fail closed); on a send-bound ticket
every **mutating** call at or after `send_not_after`, and every mutating call when `send_not_after`
is missing or does not parse (00_global_paths.md §0.3 ISO parser), is denied `outside-send-window`
(clock: `gtm_hooklib.now_utc`). Non-mutating calls are unaffected. B1 tests (each RED when the check
is removed): a ticket minted at 19:59 with quiet hours starting 20:00 (`send_not_after` 20:00) has
its 20:01 `browser_click` denied; its 19:59:30 click is allowed; a send-bound ticket with no
`send_not_after` is denied; a ticket with `send_bound: false` and no `send_not_after` is allowed.

**Money-host activation precondition (rule 6c; plan §20.6; `requests/04_hooks.md` R22).** The
browser `$` residual below is a disclosed deviation from plan §20.6's absolute "`$` always goes to
the operator", and it must not go live before the operator has accepted it. G-A itself cannot be
held back (it is `playwright-gtm`'s default-deny, §4.8 item 3), so the gate is inside it: until the
committed, trust-root file `tools/gtm/activation.json` is an **operator-signed** activation record
that `gtm_hooklib.activation_state()` verifies (§4: GTMApprover signature over `{v, kind:
"activation", ruling_id, nonce}` verified by the isolated `approval_sig.py --verify-activation`
against HEAD's `approver_pubkey.pem` with 05_approver.md §5.5 step 4's backends — the same single
backend definition G-W's trust-edit check uses, never an in-process verifier)
and whose `ruling_id` is non-empty (the operator's ruling id for the plan §20.x amendment R22
requests), every mutating call under a write or batch ticket on a `money_hosts()` host is denied
`money-residual-unratified` — money and non-money tickets alike, since both residual cases occur
there. act.py refuses such tickets at mint as well (`requests/04_hooks.md` R35). Writes on non-money
hosts, reads everywhere and setup tickets are unaffected. The file is committed from a non-GTM
session under full review, only after the ruling is recorded in the plan and in 08_seats_wps.md
Appendix B (coordinator checklist, R35). **Why signed, not just committed:** a bare id in a
committed file is agent-supplyable — a non-GTM session can `git apply` and commit under `R` (§4.2
"Backing up and reverting"), and the gate-3b review record is self-recordable — so an id with no
operator proof would let an agent make the ruling plan §20.8 reserves to the operator. B1 tests
(each RED when rule 6c is removed): with `activation.json` absent, or committed with `null`, a write
ticket's `browser_click` on `ads.google.com` is denied `money-residual-unratified` and on a
non-money host is allowed; with it committed as a record signed by the tmp HEAD key carrying a
ruling id the same click passes rule 6c; an uncommitted working-tree edit adding a ruling id does
not (HEAD read); a committed **unsigned** legacy-shaped file `{"r22_money_residual_ruling":
"R22-x"}`, a committed record signed by a key other than HEAD's, and one whose payload `kind` is
`trust_edit` each still deny `money-residual-unratified` (RED when `activation_state` accepts an
unverified id).

**The `$` residual on the browser path (plan §20.6/§20.8, which supersede the plan header's earlier
acceptance).** Read tickets cannot click on any money host (rule 9b; money hosts include every
runbook's `money_ui_hosts`, so a GBP "Promote" flow counts): reads there are navigation by URL plus
snapshot, or clicks confined to runbook-declared inbox pages ("Inbox reads on money hosts"). On a
money write ticket the amount entered is bound to the signed amount (rule 9c). What remains is
(1) a **write or batch ticket for a non-money row on a money host** (e.g. a `google_ads` T1
non-money row, or a GBP post edit on business.google.com) **clicking** a money button on the same
page — G-A cannot tell a money button from any other click; and (2) a click on a page-suggested
amount (a "recommended budget" chip) on a money ticket, which types nothing — including a chip
that changes an object's configured budget between rule 9d's API read-back and the enable click —
and, in the same ≤ 5-minute window (rule 9d's `enable_not_after`), an **out-of-band** change to the
configured budget by a co-actor: the co-managing Agency SaaS identity (plan §20.9
`co_managing_systems`) or the operator in another tab; its detection is the same day-after verify
(committed amount vs signed amount) and `change_event`/`change_history` reconcile, which attributes
the change to the other actor (rule 9d closes the case where the budget was already different
before the ticket; a `commits_on_enable` row with no API read is not agent-executable at all). Both
are **detect-after**:
the change-history reconcile (06_connectors.md §6.4 `change_history`) flags any platform change with
no matching logged action, the day-after verify compares the committed amount with the signed one,
and the runbook `expect` checks and acting-as prose are the prevention. It is not a claim that only
the operator can produce such a change. **Forged tickets are not part of (1)–(2):** rule 7a
verifies every write, batch and setup ticket's minted content against the chain on every mutating
call and, for money and signed-revert tickets, re-verifies the operator's signature, so a
hand-written or edited ticket file (`money: false`, an unsigned amount, `revert_exempt` walking
through `DISABLED`/`PAUSE`, a fake card-approved shared write) is denied `ticket-unverified`; what
remains is rule 7a's stated residual (a chain-append forgery of an unsigned ticket; runtime-field
resets within a ticket's ≤ 30-minute life), and `requests/04_hooks.md` R62 asks the coordinator
to name it in the R22 ruling text. **This residual is a deviation from plan §20.6's absolute
"`$` always goes to the operator" and is not yet recorded in the plan:** `requests/04_hooks.md` R22
asks the coordinator to add it as a plan amendment (a new §20.x plus an Appendix B entry) so the
operator-facing `$` rule states it, and rule 6c keeps every write on a money host denied until that
ruling is committed in `tools/gtm/activation.json` as an operator-signed record (rule 6c,
`activation_state`). **The same click residual for NEVER and identity classes** (a portfolio,
people, partner or asset-sharing control clicked under a non-identity write ticket where no
runbook `never_url_re` names the page) is stated under "NEVER and identity surfaces" (rule 7c) and
belongs to the same R22 ruling. **Not adopted (stated):** matching `browser_click.element`
against a runbook step `target` — `element` is free text the agent writes, so it would be a speed
bump that reads as a control.

**Parallel hook execution (stated, accepted).** Claude Code runs the matching PreToolUse hooks in
parallel (per its hooks documentation; not verified here), so rule 13 can bind the ticket, spend a
counter and record the host for a call that `block_prod_mutations.py` R5 denies (§4.9's
`example.com` click). The effect only ever consumes budget — the ticket runs out sooner,
never later — so it is accepted rather than moved to a PostToolUse hook.

**Other playwright servers:** no new denials, except rule 3 (`phi-host`) when `gtm_scope(environ,
payload)` is not None (`CLAUDE_GTM_COMPANY` set or `agent_type ∈ GTM_SEATS`) and rule 3b
(`agency-boundary`) when `gtm_hooklib.agency_scope(environ, payload, payload cwd)` holds — i.e.
also for a `DEPARTMENT_SEATS` agent (a `/gtm` mission's director or specialist) outside a GTM
session whose cwd is not under Agency (00_global_paths.md §0.4; unconditional). B1 test: a
`marketing-director` `browser_navigate` to `https://github.com/org/Agency` on `playwright-03` from a
non-GTM session with cwd the CSA root is denied `agency-boundary`, and with cwd inside the (tmp)
Agency root is allowed (RED when rule 3b uses `gtm_scope`). A tool in the **off-server mutating
set** — the named constant `gtm_hooklib.OFFSERVER_MUTATING`, defined once as
`OFFSERVER_MUTATING_NAMES` = the §4.1 mutating list (`browser_click, browser_type,
browser_fill_form, browser_select_option, browser_press_key, browser_check, browser_uncheck,
browser_file_upload, browser_handle_dialog`) plus `browser_evaluate, browser_run_code,
browser_run_code_unsafe, browser_press_sequentially, browser_keydown, browser_keyup, browser_drag,
browser_drop` (drag and drop move page content — a reorder, a file drop — so they are **included**)
and `OFFSERVER_MUTATING_GLOBS` = `browser_mouse_*`, `browser_cookie*`, `browser_set_storage*`,
`browser_localstorage*`, `browser_sessionstorage*` (the storage globs over-match getters, which
only forwards more) — whose slot's last host (read from `.enforcement/slot_hosts.json`, the R5
state, for that slot/key) is an identity host of any GTM company or of `other_businesses` → log
`gtm-offserver` (detect-after, never deny). Every other vendored 0.0.76 tool (`browser_pdf_save`,
`browser_generate_locator`, `browser_verify_*`, `browser_start_tracing`/`browser_stop_tracing`,
`browser_*video*`, `browser_highlight`, `browser_resume`, `browser_annotate`, `browser_get_config`,
`browser_console_clear`, `browser_network_clear`, `browser_hover`, …) is **not** in the set (it
changes no remote state). **The off-server identity check reads the precomputed
`S/identity_index.json`** (company.write_identity_index, 00_global_paths.md §1.2 — `{slug: [values],
"other_businesses": [...]}`), never `sibling_packs`/git, so it costs no `git show` per GTM home.
**Host extraction from the index (binding):** only the index keys in `company.gtm_slugs()` ∪
`{"other_businesses"}` are read — `company.build_identity_index()` enumerates
`registered_slugs()`, which includes Agency, and those entries are **ignored** here (§4 preamble:
never `registered_slugs()`; an Agency session clicking its own site on a `playwright-NN` slot is
not a GTM cross-company event) — and of their values only those `classify_identity_value` (§4)
classes `"host"` are compared, with `host_matches(slot_host, value)`; phones, NAP strings and
account-id values are dropped. An unreadable or unparsable index (or any other error on
this detect-only path, `SiblingPackUnreadable` included) logs `gate-fault` and **allows**. B1 tests:
an index whose registered-but-not-GTM fixture slug (the Agency home's) lists `agency-fixture.example`
logs nothing for a `browser_click` on a slot whose last host is `agency-fixture.example` (RED when
every index key is read); an index value
`"(303) 555-1234"` never matches a host; a `browser_drag` on a slot whose last host is a OtherCompanyB
domain logs `gtm-offserver` (RED when drag is left out of the set). The
§4.8 item 3 shell prefix forwards a non-`playwright-gtm` call to python only when a GTM-scope or
Agency-scope arm is present or the tool is in that mutating list, so reads and snapshots of other
servers cost no spawn. **Outside GTM scope and Agency scope, on any server other than
`playwright-gtm`, G-A never denies** — its fail mode there is allow + log `gate-fault`, so a G-A
bug cannot break existing Playwright work.

**Fail mode:** any exception → deny for everything except the ticketless-read set, logged
`gate-fault`. Within the ticketless-read set: `browser_navigate` is allowed on an exception **only**
when, before the exception, its host was positively classified as an allowed read host **and**
rules 3, 3b and 4 completed for it (G-A tracks this with a local `navigate_checked` flag); an
exception earlier than that (e.g. `phi_denylist()` raising while rule 3 runs) denies `gate-fault`.
For a PHI-scoped company the non-navigate ticketless reads follow the same rule (allowed on an
exception only after the recorded-host checks above completed). B1 test: with `phi_denylist()`
made to raise, a ticketless `browser_navigate` to an allowed read host is denied `gate-fault`
(RED with allow-on-exception), and a `browser_snapshot` in a non-PHI company is allowed.
**Emit test (00_global_paths.md §0.4 mechanism):** on `playwright-gtm` in any session, on any
server in GTM scope, and for rule 3b under `agency_scope`'s department-seat arm, every G-A deny is **unconditional** — emitted when `unconditional or
_lib.enforcing(where)` with `unconditional = True` — so removing the global `.enforce` marker never
turns `playwright-gtm`'s default-deny into a log (this is stricter than §0.4's "GTM scope" wording
for the one server that exists only for GTM work; `requests/04_hooks.md` R23 asks 00 to list it).
Outside GTM scope on other servers G-A never denies except rule 3b under `agency_scope` (above). Logs via `_lib.log("gtm_browser_gate", decision, reason=…, server=…, tool=…,
ticket_id=…, company=…, agent_id=…, agent_type=…)`; decisions `would-block`, `allow-ticket`,
`gtm-offserver`, `gate-fault`, `sibling-pack-unreadable`. **G-A is the fail-closed backstop only
while it runs:** under `CSA_DISABLE_HOOKS=1` it returns allow before parsing (00_global_paths.md
§0.4), and `playwright-gtm`'s default-deny disappears. So `gtm_session.sh` **refuses to start** when
`CSA_DISABLE_HOOKS=1` is set in its environment (07_notices_schedules.md §7.6 step 1;
`requests/07_notices_schedules.md`). `_lib.enforcing()` needs no such check: every G-A deny on
`playwright-gtm` and in GTM scope is unconditional (above), so a non-enforcing machine does not
weaken it. B1 test (00 §0.4 style): in a tmp `HOME` with no enforce markers, a `playwright-gtm`
`browser_click` with no ticket is denied `no-ticket` (RED when the emit test is `_lib.enforcing` alone).

### 4.2 G-B `hooks/gtm_bash_gate.py` (WP-B1) — gate in the `pretooluse_bash.py` chain

API. `decision()` is not pure; its I/O surface (binding, so B2's latency expectations are
derivable) is: plain file reads (`phi_denylist`, `phi1_allowlist`, `S/other_businesses.json`,
`ST/pending_commit.txt`, a patch file's bytes, an rsync `--exclude-from` file ≤ 1 000 lines);
`os.stat`/`os.readlink` in `canon` step (4) (never inside Agency, §4); the rule-c copy walk
(`os.walk`, ≤ 20 000 entries and ≤ 2 s, only when a recursive copy's root is a strict ancestor of a
protected path); `git` subprocesses, each with a 5 s timeout and the hardened env of
`git_show_head` — `git show` for committed packs (`load_pack_safe`/`sibling_packs`, once per GTM
home per process, memoized; rules c, d1, j and n) and, for rule n's exceptions only, one `rev-parse
--show-toplevel`, for exception (i) two `diff --quiet` (its clean-against-HEAD check (e)), for exception (ii) arm (a) one
`apply --cached --reverse --check`, one `ls-files --stage` and one `hash-object` (its post-image check); and, for rule n's exceptions only, one
isolated `act.py status` subprocess (10 s timeout, §4.2 rule n). Worst case for a command that is
not a rule-n exception candidate: one 2 s walk plus one 5 s `git show` per GTM home; for a rule-n
exception candidate add ≤ 4 × 5 s of git and ≤ 10 s of `act.py status`. A command with no
write-class or removal-class target, no rule-d1 `gcloud secrets` segment and no `git` segment in
GTM scope does no subprocess and no walk (the pack reads happen only when a target must be judged
by `machine_written()`/`gtm_session_write_verdict()`).

```python
HOOK_NAME = "gtm_bash_gate"
def decision(command: str, environ: Mapping[str, str], cwd: str, agent_type: str | None = None) -> tuple[bool, str, str, bool]
    # (block, reason, message, unconditional). unconditional is True for a block by rule c, k, l or m in ANY session, for a
    # block by rule i under agency_scope's department-seat arm, and for a block by ANY rule in GTM scope (rule n included)
    # (00_global_paths.md §0.4); False otherwise (and on no block). The caller passes it to
    # `_Block(..., unconditional=...)`, whose `_finish` emits when `enforcing(where) or block.unconditional` (§4.9).
    # `cwd` is the payload cwd (agency_scope's cwd test and the candidate-base start).
    # `reason` is EXACTLY the rule's code as the table below names it (e.g. "protected-state-write", "phi-path"), with ONE
    # composite form: every rule-n denial caused by the authorization binding (`authorized_static_action` failing, a hash or
    # path-set mismatch, a patch not applied, an index or working-tree blob differing from `after.post_image`, a patched
    # path not clean against HEAD before the apply, a patch outside `marketing_paths`) is
    # reason == "gtm-git-write:patch-not-authorized"; every other rule-n denial is reason == "gtm-git-write". `message` is
    # free text for the agent and is never asserted by tests beyond being non-empty.
def decision_payload(command: str, environ, cwd: str, payload: dict) -> tuple[bool, str, str, bool]
    # the same, taking the whole PreToolUse payload (agent_type = payload.get("agent_type"); scratchpad_dir for temp_roots,
    # §4); decision() is decision_payload with payload {"agent_type": agent_type}. `_gtm_bash_block` calls decision_payload.
```
**Test labelling (binding; 08_seats_wps.md §9: B1 does not touch `pretooluse_bash.py`, and B2's
`b2_gb_wiring.patch` delivers `_Block.unconditional`, `_finish`'s emit test and `_gtm_bash_block`).**
Every G-B test in this file that is written "through `pretooluse_bash.py`", "through the patched
dispatcher", "end to end" or "with no enforce marker" is a **B2** test, run after
`b2_gb_wiring.patch` exists, against the patched tmp copies (§4.2 "Activation"). B1 writes the
**same cases** at the `gtm_bash_gate.decision()` / `decision_payload()` level and asserts the whole
returned tuple — `block`, the exact `reason` string, and `unconditional` — so every B1 case that a
B2 case later runs through the dispatcher already fixes the decision and its emit flag; B1 needs no
shim of the dispatcher. Where a test below says "B1" and "through the dispatcher" together, the
decision-level assertion is B1's and the dispatcher run is B2's.
**Emit test (00_global_paths.md §0.4).** The per-rule "Scope" column below says where a rule fires;
whether its deny is emitted is the 4th return value. B1 asserts each case below as
`decision(...) == (True, <reason>, <any>, True)` (and case (d) as `(True, <rule-a reason>, <any>,
False)`); B2 runs the same cases (00 §0.4 (a)–(d), in a tmp `HOME` with **no** `~/.claude/.enforce`
and no `.csa-enforce` anywhere) through the patched `pretooluse_bash.py` copy: (b) a non-GTM `cp x <S>/tickets/…` is denied (rule c); a non-GTM
`CLAUDE_GTM_COMPANY=x python3 ~/.claude/tools/gtm/act.py propose` is denied (rule l); a non-GTM
`CLAUDE_DIR=/tmp/x python3 ~/.claude/tools/gtm/act.py status --company x` is denied (rule m); a
GTM-scope `ls ~/Desktop/OtherApp` is denied (rule i); a non-GTM `marketing-director` `ls ~/Desktop/OtherApp`
(cwd the CSA root) is denied (rule i, agency_scope); a GTM-scope `git apply /tmp/x.patch` is denied
(rule n); a GTM-scope `bash ~/.claude/scripts/gtm_approve.sh trust-edit /x` is denied (rule g); (d) a non-GTM rule-a command only logs
`would-block` with `enforce=false`. Each of the denials goes RED when its `unconditional` is left
`False` (B1: the tuple's 4th element; B2: the emitted deny).
Tokenizes with `gtm_hooklib.split_with_joins` (segments **with** their joiners and subshell depth,
§4) + `_lib._tokenize` + `_lib._strip_prefix`; the `NAME=` assignments `_strip_prefix` removed from a
segment are `tokens[:len(tokens) - len(_lib._strip_prefix(tokens))]` (it returns only the remaining
tokens). **"GTM scope"** below = `CLAUDE_GTM_COMPANY` set **or** `agent_type ∈ GTM_SEATS` (payload
`agent_type`, passed by `_gtm_bash_block`) — plan §20.3 scopes PHI and boundary enforcement to both
arms. **"Agency scope"** (rule i only) = `gtm_hooklib.agency_scope(environ, {"agent_type":
agent_type}, cwd)`: GTM scope, or a `DEPARTMENT_SEATS` agent whose payload cwd is not under Agency
(00_global_paths.md §0.4, plan §20.9a). Every path a rule compares is `gtm_hooklib.canon(target, base)` (§4: `~`/`$HOME` expanded on
the operand **before** it is joined to the base; Agency paths short-circuited as text; symlinks
resolved **and casefold**, F-case), compared against `canon` of the protected/listed path, so a
relative target (`rm act.py` with cwd `~/.claude/tools/gtm`) is judged by where it lands and
`rm ~/.CLAUDE/.gtm_state/x` or `python3 ~/.claude/Tools/Gtm/Connectors/Meta/Write.py` is judged
like its lowercase spelling. (Correction: `_lib._leading_cd_dir`/`effective_git_cwd` apply only
`expanduser` + `os.path.join`, no realpath; G-B does not reuse them for path judgment.)

**`base` tracks `cd` (F-cd), operator-aware.** `_lib._split_segments` discards the joining
operators — `(cd /tmp) && rm act.py`, `cd /tmp | rm act.py` and `cd /nonexistent; rm act.py` all
yield the same segments as `cd /tmp && rm act.py` (verified; `_lib.py`'s own `_LEADING_CD_RE`
comment) — so G-B walks `split_with_joins` instead and keeps a **set** of candidate bases, starting
as `{payload cwd}`:
- a depth-0 segment `cd <literal dir>` whose **next** segment is joined by `&&` replaces every
  candidate `b` with `canon(dir, b)` (if the `cd` fails, the shell runs nothing after it);
- a literal `cd` joined by `;`, `||`, `|` or `&`, or at subshell depth > 0 (`( … )`, `$( … )`,
  backticks), **adds** `canon(dir, b)` for every candidate and keeps the old ones — every later
  operand is judged against **every** candidate base and a hit on any denies;
- a `cd` whose operand is not a literal path — `$VAR`, `$(…)`, backticks, `-`, a bare `cd` — in a
  command that carries a deny token (`UNTOKENIZABLE_DENY_TOKENS`, "Fail mode" below) denies
  `untokenizable-gtm-command`; without one it is allowed and logged.
B1 tests, each falsified by dropping its clause: `cd ~/.claude/tools/gtm && rm act.py` (payload cwd
`~`) and `cd H/.claude/gtm && rm -rf state` (payload cwd `H`) are denied `protected-state-write`;
with cwd `~/.claude/tools/gtm`, `(cd /tmp) && rm act.py`, `cd /nonexistent; rm act.py` and
`cd /tmp || rm act.py` are each denied `protected-state-write`; `cd "$D" && rm act.py` is denied
`untokenizable-gtm-command`; `cd /tmp && rm act.py` (cwd `~/.claude/tools/gtm`) is allowed.

**Command grammar (rules a–c, k, l, m).** A segment's verb is `os.path.basename(argv0)` after stripping a
leading `\` and unwrapping, repeatedly, the shell reserved words and grouping tokens that
`_lib._split_segments` leaves at the head of a segment — `!`, `{`, `}`, `then`, `do`, `else`,
`elif`, `if`, `while`, `until`, `time` — and a `case` pattern arm (a leading token ending in an
unquoted `)` such as `pat)` or `a|b)`, and a leading `;;`/`;&`), then the wrappers `command`, `builtin`, `exec`, `env` (with its
options and `NAME=` args), `sudo` (with its options), `nice`, `nohup`, `time`, `timeout <dur>`,
`stdbuf …`, `caffeinate`, and `xargs` (whose argv tail is the verb; its operands come from stdin, so
a removal or write verb under `xargs` in a command carrying a deny token — `UNTOKENIZABLE_DENY_TOKENS`,
"Fail mode" below — denies `untokenizable-gtm-command`). `bash|sh|zsh|dash -c <text>` and `eval <args>` **recurse**: the text is
decided as its own command with the current candidate bases. Redirect targets are
`gtm_hooklib.redirect_targets(raw segment text)` (§4 `REDIRECT_RE`: writing operators `>`, `>>`,
`>|`, `&>`, `&>>`, `N>`, `N>>`, including one glued to a word such as `x>file`; matches starting
inside a quoted span dropped; `<`, `<<`, `<<<`, `>&N`, `N>&M`, `>&-` dropped; the target is the next
shlex word after the operator, quotes stripped). B1 tests (each denied `protected-state-write`, cwd
`~/.claude/tools/gtm`, RED when the reserved-word unwrap is removed): `if true; then rm act.py; fi`,
`for f in a; do rm act.py; done`, `{ rm act.py; }`, `! rm act.py`, `while false; do :; done; until
true; do rm act.py; done` and `case x in x) rm act.py;; esac`.

| Rule | Scope | Denies (reason) |
|---|---|---|
| a | all sessions (**intended**, plan §7.3 (a): one write path; blast radius below) | running a file matching `tools/gtm/connectors/*/write*.py`, `tools/gtm/gtmlib/connector_dispatch.py`, `repo_tooling/google_ads/build_*.py`, `repo_tooling/google_ads/reauthorize.py`, `repo_tooling/meta_ads/execute_build.py`, `repo_tooling/meta_ads/probe_and_build.py` (as `python[3] <path>`, `./<path>`, or `uv run <path>`; globs matched casefolded against `canon`), or a dotted module `M` matching (casefolded) `(tools\.gtm\.)?connectors\.[a-z_]+\.write[a-z_]*`, `(tools\.gtm\.)?gtmlib\.connector_dispatch`, `repo_tooling\.google_ads\.(build_[a-z_]+\|reauthorize)`, `repo_tooling\.meta_ads\.(execute_build\|probe_and_build)` — **anchored** (`^…$`) for a `python[3] -m <M>` operand; **unanchored and word-bounded** (`(?<![\w.])…(?![\w])`) inside `python[3] -c <text>` text, which also matches `from <P> import <N>[, <N2>…]` whenever some `<P>.<N>` matches (`from tools.gtm.connectors.meta import write`, `from gtmlib import connector_dispatch`, `from repo_tooling.google_ads import build_x`), and `importlib.import_module('<M>')`/`__import__('<M>')`; and the same text scan applied to the **raw command text** (including the heredoc body `_split_segments` drops) of a python segment fed from stdin (script operand `-` or none: `python3 - <<'EOF' … EOF`, `python3 <<EOF`) (`connector-write-outside-act`). **Rule a is a speed bump, stated plainly:** a wrapper script in `/tmp` that imports a connector, `exec(open(…).read())`, stdin piped from a file, and string-built module names are known, accepted gaps; the real control is **credential custody** (rule d1, GSM, `secret_sink`: a write path without the company's credential cannot write). No exception is needed for `python3 /Users/x/.claude/tools/gtm/act.py execute <action_id>` (02_act.md §2.4): it names none of these files or modules (act.py imports connectors in-process), so plan §7.3 (a)'s "unless the command is exactly `act.py execute`" holds by construction, and each segment is judged on its own — `python3 …/act.py execute x && python3 tools/gtm/connectors/meta/write.py` is denied on its second segment (B1 test; IMP-25). **Not matched:** `pytest`/`python -m pytest` runs (they import but do not run the modules as scripts), `git` subcommands, and reading the files. B1 tests: `python3 -c "from tools.gtm.connectors.meta import write; write.main()"`, `python3 -c "import importlib; importlib.import_module('gtmlib.connector_dispatch')"`, `python3 - <<'EOF'\nfrom repo_tooling.google_ads import build_x\nEOF` and `python3 ~/.claude/Tools/GTM/connectors/meta/write.py` are denied; `python3 -c "print('connectors')"` is allowed. **Blast radius (I23):** CSA's own development sessions can no longer run `repo_tooling/google_ads/build_*.py` (incl. `build_validate_batched.py`), `reauthorize.py` or the two `meta_ads` scripts directly — CSA ad-account writes go through `act.py execute` like every company's; this changes an existing CSA workflow, so the coordinator posts it as a card before B1 lands (08_seats_wps.md Appendix C item 24) |
| b | all | `curl`/`wget`/`http`/`https`/`python -c` with a write method or body to a host (lowercased) matching `graph.facebook.com`, `graph.instagram.com`, `googleads.googleapis.com`, `*mybusiness*.googleapis.com`, `*businessprofile*`, `analyticsadmin.googleapis.com`, `tagmanager.googleapis.com`, `searchconsole.googleapis.com`, `www.googleapis.com/webmasters`, `sheets.googleapis.com`, `api.linkedin.com`, `youtube.googleapis.com`, `www.googleapis.com/youtube`, `www.googleapis.com/upload/youtube`, or a URL path containing `/wp-json/` (`api-write-outside-act`). **Option parsing:** a write method is `-X`/`--request` with value `POST\|PUT\|PATCH\|DELETE` in any spelling — separate (`-X POST`), glued (`-XPOST`), inside a short-option cluster (`-sSXPOST`: an `X` in a cluster takes the rest of the cluster as its value), or `=` form (`--request=POST`); a body is any of `-d`/`--data`/`--data-raw`/`--data-binary`/`--data-urlencode`/`--json`/`-F`/`--form`/`--form-string`/`-T`/`--upload-file`, separate, glued (`-dbody`, `-Fx=@f`) or `=` form (`--data=…`); wget `--method=…`/`--method …`, `--post-data`, `--post-file`, `--body-data`, `--body-file`; httpie `POST/PUT/PATCH/DELETE` or a `key=value`/`key:=value` body item; python `requests.(post\|put\|patch\|delete)` or `urlopen(` with `data=`. **Parity (P2 test):** every `api_hosts` entry of every connector manifest (06_connectors.md §6.1) is matched by one of these host patterns **and** by a §4.7 `bash_gate.sh` token, so a new connector cannot land with a write host only one of the two lists knows. B1 tests: `curl -XPOST https://graph.facebook.com/x`, `curl -sSXPOST …`, `curl --request=PATCH …`, `curl -dbody https://GRAPH.FACEBOOK.COM/x` and `curl -F a=@f https://graph.instagram.com/x` denied; `curl https://graph.facebook.com/x` (GET) allowed |
| c | all (additions marked "GTM scope" only in GTM scope) | a write to, or removal of, a protected path (`protected-state-write`), judged **per verb class** (command grammar above; operands are `canon(operand, b)` for every candidate base `b`; a glob operand is judged by its longest literal prefix directory): **Removal class — equals, under, or ancestor** (removing an ancestor removes the protected path): `rm`, `rmdir`, `unlink`, `shred`; the SOURCE operands of `mv` and of `rsync --remove-source-files`; the DESTINATION of `rsync --delete*`; `tar --remove-files` operands; the root of `find … -delete` or `-exec`/`-execdir` running `rm`/`rmdir`/`unlink`/`shred` — where a find root that is only an **ancestor** counts only when the expression has no `-name`/`-iname`/`-path`/`-ipath`/`-regex`/`-iregex` test or some such test's pattern matches (casefolded `fnmatch`; for `-path`/`-regex` the candidate protected path's text) a component of a protected path under that root (`find . -name '*.pyc' -delete` and `find . -name __pycache__ -exec rm -rf {} +` at the CSA root are allowed; `find . -name state -exec rm -rf {} +` there is denied). **Write class — equals or under the effective target only:** redirect targets; `tee` operands; `sed -i`/`--in-place` and `perl -i`/`-pi`/`-i.bak` file operands; `truncate`, `touch`, `chmod`, `chflags`, `chown` operands; `dd of=<p>`; `patch` (its `-o` output, else the named file); and the DESTINATION of `cp`, `mv`, `ln`, `install`, `ditto`, `rsync` (without `--delete*`). The effective target of a destination that is an existing directory, ends in `/`, or receives several sources is `dest/basename(src)` per source; for a **recursive** copy (`cp -r`/`-R`/`-a`, `ditto`, `rsync -r`/`-a`) the effective target ROOT is judged first, by text only: when that root is neither equal to, under, nor an **ancestor** of some canon'd protected path (the protected set below, plus the machine-written and trust-root predicates' roots), the copy is **allowed without walking** (so `cp -R node_modules /tmp/x`, `rsync -a src/ /tmp/dst/` and runtime CLAUDE.md §2's rsync-with-exclusions recipe cost nothing and never deny); when the root is equal to or under a protected path the copy is denied without walking; only when the root is a strict **ancestor** of a protected path is the source tree walked (`os.walk`, bounded to 20 000 entries and 2 s, never entering a directory whose text path is equal to or under `agency_root()`, §4), each relative path joined to the root and judged, and a tree that cannot be enumerated within the bound denies. rsync `--exclude=<pat>`/`--exclude <pat>`/`--exclude-from=<file>` (the file read, ≤ 1 000 lines) prune the walk with rsync's own anchored/unanchored glob meaning, casefolded; `--include`/`--filter` rules are **ignored** (stated: a copy relying on them is judged as if they were absent, which can only deny more). B1 tests: `cp -R <25 000-entry tree> /tmp/x` allowed with no `os.walk` call (RED when the pre-check is removed: it would deny on the bound); `cp -R <25 000-entry tree> ~/` denied; `cp -R d/ ~/` where `d` contains `.claude/.gtm_state/y` denied; `rsync -a --exclude .claude d/ ~/` where only `d/.claude/.gtm_state/y` would hit → allowed. **Links:** `ln` and `cp -l`/`--link`/`-s`/`--symbolic-link` also judge the SOURCE by equals/under (a link is a write path to its target). **Exception (IMP-04):** the source operands of `cp`, `ditto` and `rsync` (without `--remove-source-files`) are reads and are not judged (so `cp gtmlib/store.py <scratch>/` — the single-file backup of runtime CLAUDE.md §2/§6 — is allowed). **Protected paths (every session):** every `actions.jsonl`, `lead_fallback*.jsonl`, `ACTIVITY_LOG.jsonl`, `TOOL_TRAIL.jsonl`; **every path `gtm_hooklib.machine_written()` classifies** — the one predicate G-W's `machine-written-path` uses (§4.3), so the two lists cannot drift: `R/.gtm_state/` (`S`, incl. `chain_anchors/`), every `<H>/.claude/gtm/state/`, the activity-log files in every GTM home's `H / paths.activity_log_dir` (`*.jsonl`, `*.jsonl.ids` — activity_log.py's `TOOL_TRAIL.jsonl.ids` membership sidecar, where an inserted id makes the harvester treat an unrecorded call as recorded — its `*.jsonl.ids.*.tmp` staging files, `.activity_log.lock`, the machine-rendered `ACTIVITY_LOG.md`, and the owner-facing mirror's two files `gtm_hooklib.mirror_files(slug, pack)` names — `<expanduser(top-level mirror_dir)>/<mirror_basename>.{md,html}`, §4), `H / paths.scoreboard` (so `echo x >> tracking/scoreboard.csv` from any session is denied — scoreboard values feed the plan §0 assertions and the weekly decision table), non-`.md` files under `H / paths.snapshots_dir`, mission `*.json`/`*.jsonl`, and `<H>/.playwright-mcp/` (now every session, like G-W: shell cleanup of a GTM home's `.playwright-mcp/` is done by the operator or `disk_janitor.sh`, which runs outside the hooks); **every path `gtm_hooklib.trust_root_path()` accepts** — the whole live `R/tools/gtm/` subtree except `tests/`, `connectors/*/tests/`, `contracts/` and top-level `*.md` (so `act.py`, `approver_pubkey.pem`, `gtmlib/`, `approval_sig.py`, `gtm_env.py`, `ed25519_verify.py`, `ai_budget.py`, `gtm_pricing.py`, `company.py`, `system_names.py`, `project_dirs.py`, `setup_scripts/`, `connectors/*` sources, `tier_table.json`, …), plus `R/telemetry/pricing.json` (`requests/05_approver.md` R15 (a)/R28; `approval_sig.py` and `gtm_env.py` run **before and as** the trust-root check, so an edit to them could never be detected after the fact, 05_approver.md §5.5 step 0); worktree and lane copies (`R/.claude/worktrees/…`) are not under `R/tools/gtm/` and stay writable; **Python start-up hooks (write class, every session; `requests/05_approver.md` R15 (b)):** any effective target under a directory named `site-packages` or `dist-packages`, any `*.pth` file, and any file named `sitecustomize.py` or `usercustomize.py` (an interpreter start-up hook would run inside act.py before its own trust check); **the pinned interpreter's own tree (write and removal class, every session; `requests/05_approver.md` R43 (b); 05_approver.md §5.5 "Interpreter pin"):** any effective target equal to or under `dirname(dirname(realpath(gtm_env.TRUSTED_PYTHON)))` (today `/opt/homebrew/Cellar/python@3.13/3.13.14_1/Frameworks/Python.framework/Versions/3.13`, whose `lib/python3.13/` stdlib — e.g. `json/__init__.py` — `-I -S` still loads, so an edit there runs inside the trust check before it can detect anything, plan §20.8 N1), `/opt/homebrew/opt/python@3.13/` or `/opt/homebrew/Cellar/python@3.13/` (the realpath is computed at call time, so a `brew upgrade` within 3.13 moves the protected tree with it; a `realpath` failure denies), and a `brew` command whose verb is `install\|uninstall\|remove\|rm\|upgrade\|reinstall\|link\|unlink\|pin\|unpin\|switch` with an operand matching `(?i)^python(@3(\.13)?)?$` or `(?i)python@3\.13` (`protected-state-write`) — in GTM scope also `brew upgrade`/`brew reinstall` with no formula operand (they upgrade every formula, the pinned one included). Tool writes (Edit/Write) into the interpreter tree or a `site-packages` directory from a **non-GTM** session are not denied by G-W (stated gap; in GTM scope `gtm-write-outside-drafts` denies them); **`R/schedules/DISABLED` — removal class only** (equals or ancestor: plan §6.8's global kill switch is lifted only from the operator's own terminal, outside every hook, like the trust-edit marker; outside GTM scope creating or writing it is the safe direction and stays allowed, and nothing else under `R/schedules/` is protected by this entry; **in GTM scope creating it is denied too** (DECIDED HERE): `gtm_session_write_verdict` denies every target under `R/schedules/**` (`runtime-write-in-gtm-session`, §4.3; rule c reports it as `protected-state-write`), and no exemption is made for `DISABLED` — it stops every scheduled job on the machine, GTM and non-GTM alike (runtime CLAUDE.md §13), while a GTM session stops its own company's work with `act.py pause` (02_act.md §2.4), so an agent-created global stop is an outward act the operator reserves; G-W's `runtime-write-in-gtm-session` gives tool writes the same answer); **in GTM scope also** every write-class and removal-class effective target for which `gtm_hooklib.gtm_session_write_verdict()` returns a reason — the one predicate G-W's GTM-scope clauses use (§4.3), parity-tested, so shell writes never reach further than tool writes: every GTM home's pack files `<H>/.claude/gtm/company.json`, `review_lanes.local.json` and `connectors.json` (FID-07), every GTM home's operator-input file (02_act.md §2.6 card rule path — a GTM session never writes an answer, by tool or by `sed -i`/`tee -a`/`>>`), `R/projects/` transcripts (FID-08), everything under `R` except `R/projects/*/memory/` in interactive runs (`R/hooks/**`, `R/settings*.json`, `R/agents/**`, `R/schedules/**`, `R/knowledge/**` …), every source file matching the company's `marketing_paths` (which change only through `git apply` of an **authorized** action's `ST/patches/<id>.patch`, rule n exception (i), 02_act.md `website_static` executor), and every other target outside the company's `<H>/.claude/gtm/drafts/`, the system temp roots and — in interactive runs only — the pack-declared editable `paths.*` entries and `R/projects/*/memory/` (§4.3 `gtm-write-outside-drafts`); plus `pip install` with `--user`, `--target`, `--prefix` or `--root` (`protected-state-write`; outside GTM scope `pip` is not judged — the gate's own processes run with the start-up-hook paths above protected, stated). The removal-class ancestor rule applies only to the fixed every-session set above, never to this GTM-scope predicate. So `rm -rf H/.claude/gtm/state`, `rm -r ~/.claude/tools/gtm`, `mv state x` (cwd `H/.claude/gtm`), `rm -rf gtm` (cwd `H/.claude`), `cp forged.json gtm/state/autonomy_state.json` / `tee gtm/state/x` / `ln -sf x gtm/state/y` / `sed -i s/a/b/ gtm/state/y` / `echo x > gtm/state/y` / `echo x>gtm/state/y` / `/bin/rm gtm/state/y` / `\rm gtm/state/y` / `env X=1 rm gtm/state/y` / `bash -c "rm gtm/state/y"` (cwd `H/.claude`), `rm ~/.claude/schedules/DISABLED`, `rm -rf ~/.claude` and `rm ~/.CLAUDE/.gtm_state/x` are all denied (I9). **Blast radius (every session):** removing an **ancestor** of a protected path (`rm -rf ~/.claude/tools`, `rsync --delete src/ ./` at a GTM home root, an unfiltered `find <ancestor> -delete`) is denied; copies, links and writes into an ancestor directory are judged by their effective target and are allowed when it is not protected. B1 tests, each falsified by removing its clause: `cp ~/.claude/tools/gtm/gtmlib/store.py /tmp/x/` allowed, `cp /tmp/x/store.py ~/.claude/tools/gtm/gtmlib/` and `cp -l ~/.claude/tools/gtm/act.py /tmp/x/` denied; `cp x .` at the CSA root, `cp x ~/.claude/`, `cp x ~/.claude/tools/`, `cp report.pdf ~/Desktop/` and `mv x ~/` allowed; `cp -R d/ ~/` where `d` contains `.claude/.gtm_state/y` denied; `find . -name '*.pyc' -delete` (cwd the CSA root) allowed; `sed -i s/1/2/ H/<activity_log_dir>/TOOL_TRAIL.jsonl.ids` denied; `rm ~/.claude/schedules/DISABLED` denied from a GTM session and from a non-GTM session, `touch ~/.claude/schedules/DISABLED` allowed from a **non-GTM** session and denied `protected-state-write` from a **GTM** session (RED when a GTM-scope exemption for `DISABLED` is added); from a GTM session `sed -i s/hipaa// H/.claude/gtm/company.json`, `echo approve >> H/<operator-input file>` and `rm R/projects/<p>/<s>/subagents/agent-x.jsonl` denied, `rm R/projects/<p>/memory/x.md` allowed (interactive run); the same three denied commands from a non-GTM, non-seat session allowed; `echo x >> H/<paths.scoreboard>` denied from a non-GTM session (RED when rule c keeps its own list instead of `machine_written()`); an Edit-equivalent `sed -i s/a/b/ ~/.claude/tools/gtm/approval_sig.py` and `echo x > ~/.claude/tools/gtm/gtm_env.py` denied from a non-GTM session (RED when `trust_root_path()` omits them), `echo x > ~/.claude/tools/gtm/tests/t.py` and `echo x > ~/.claude/tools/gtm/README.md` allowed; `echo 'import x' > /tmp/v/lib/python3.13/site-packages/evil.pth` and `cp x ~/Library/Python/3.13/lib/python/site-packages/sitecustomize.py` denied; with `gtm_env.TRUSTED_PYTHON` monkeypatched to a tmp `…/Versions/3.13/bin/python3.13`, `echo x > <that>/Versions/3.13/lib/python3.13/json/__init__.py` and `rm -rf <that>/Versions/3.13/lib` denied from a non-GTM session, and `brew reinstall python@3.13`, `brew unlink python@3.13` denied while `brew install jq` is allowed (each RED when the interpreter-tree clause is removed); from a GTM session `echo x > ~/.claude/hooks/gtm_browser_gate.py`, `sed -i s/a/b/ ~/.claude/settings.json` and `echo x > H/marketing/website/index.html` denied, the same three from a non-GTM session allowed. (act.py's own in-process writes — `pause`, `resume`, reconcile — are not shell writes and are unaffected.) **Known shell-write reach, stated:** rule c is a parser over shell text, not a sandbox. Interpreter code that writes files (`python3 -c` with a string-built path, `python3 - <<EOF`, `node -e`, `perl -e` without `-i`), `git` subcommands that write the tree (`git apply`, `git am` — git subcommands are never judged, below), and paths built by command substitution are known, **accepted** gaps for every protected path that is not a trust root — `S/tickets/` included, which is why G-A never trusts a ticket file's content: rule 7a verifies it against the chain (§4.1 "Ticket authenticity"). **`git` subcommands that write the tree or move HEAD** (`git apply`, `git am`, `git commit`, …) are not judged by rule c in any session; **in GTM scope rule n judges them** (default-deny except the reviewed-patch apply and the pack-scoped commit), so a GTM session can neither `git apply` a patch into application code or the trust root nor commit one; outside GTM scope they remain the development path (a non-GTM session is where tools and hooks are built and reviewed). Trust roots are not protected by rule c alone: every tool edit under the live `R/tools/gtm/` subtree needs a GTMApprover-signed single-use marker (§4.3), and any shell change to a TRUST_PATH makes `approval_sig.trust_root_ok` fail (05_approver.md §5.5), which refuses every signed path and marks every AI-spend bucket forged (§4.6). The two files the trust check itself runs — `approval_sig.py` and `gtm_env.py` — cannot be detected after the fact by that check, so for them the residual is exactly this list of unparsed shell forms; 05_approver.md §5.5's HEAD-hash comparison of those two files (`requests/05_approver.md` R15/R28) is the backstop the coordinator must confirm before activation. The hash-chained ledgers (`actions.jsonl`, `chain_anchors/`) detect after the fact the state edits that slip past |
| d1 | all | `gcloud secrets versions access` naming a secret that appears in any GTM pack's `credential_ref` (`gsm:<name>`, packs from `company.gtm_slugs()`) (`gtm-secret-read`). **When any pack loads None** (`load_pack_safe`): in GTM scope, deny **every** `gcloud secrets versions access` (`gate-fault`) — an unreadable pack's secrets cannot be known, so none may be read; outside GTM scope, judge the readable packs only; either way log `sibling-pack-unreadable` with the slugs. B1 test: with one GTM home uncommitted, a GTM-session `gcloud secrets versions access latest --secret=anything` is denied, a non-GTM one naming a secret no readable pack lists is allowed |
| d2 | GTM scope only | `gcloud secrets versions access` naming a secret matching `oauth-google-*` (`gtm-secret-read`; §20.9 "in GTM sessions" — Agency/OtherApp's own sessions read their tokens legitimately, so no denial outside GTM scope; P2 test: a non-GTM, non-seat command reading `oauth-google-x` is allowed, the same command in a GTM session or from a GTM seat is denied) |
| e | all | `launchctl bootstrap\|bootout\|kickstart\|load\|unload\|enable\|disable\|submit\|remove\|stop\|kill\|bsexec\|asuser` naming a `com.oversight.gtm.` label or plist (`gtm-launchd`) |
| f | all; the second clause GTM scope only | `security find-generic-password\|find-key\|export\|dump-keychain\|delete-generic-password\|set-generic-password-partition-list\|set-key-partition-list` with any argv token (option values included: `-s`, `-a`, `-l`, `-D`, `-j` and positional) that contains, casefolded, any member of `system_names.APPROVER_KEYCHAIN_LITERALS` — the one constant shared with 05_approver.md §5.6 (`requests/04_hooks.md` R52): the service `com.oversight.gtm.approver`, the fallback key's account `signing-key-ed25519` and the Secure Enclave key's application tag `com.oversight.gtm.approver.signing` — so `security find-generic-password -a signing-key-ed25519 -w` (account only) is caught; until R52 lands the hook uses exactly those three literals, and a B1 test asserts its set equals `set(system_names.APPROVER_KEYCHAIN_LITERALS)` once it exists (the OS consent prompt remains the real control; this is friction); **in GTM scope** also `security dump-keychain` and `security export` with no item named (they dump every item without naming one) (`approver-keychain`; plan §20.13 N6 says "naming" — the GTM-scope clause is hardening beyond it) |
| g | all | `osascript` text containing `GTMApprover` or (`System Events` and `click`/`keystroke`) (`ui-automation`); running `gtm_cancel.sh` (`agent-cancel-forgery` — agents use `act.py cancel`); running `gtm_approve.sh` in **any** mode — the re-show form `gtm_approve.sh <request_id>`, `trust-edit <path>`, `operator-ok …`, `activation <ruling_id>` (§4 `activation_state`; `requests/04_hooks.md` R45) (`agent-approver-script`; `requests/05_approver.md` R51 applied): plan §20.8 says the script "only asks the app to re-show" and approval comes from the operator; act.py writes `S/approver_inbox/show.<request_id>` itself (05_approver.md §5.1 step 5), so agents never need it, and an agent-raised Touch-ID prompt for a trust edit or an operator marker is exactly the reflexive-consent path §20.8 avoids (rule k's literals do not match the hyphenated `trust-edit`/`operator-ok` modes). "Running" = the verb or the script operand of `bash\|sh\|zsh <script>` (after unwrapping) has basename `gtm_approve.sh` (casefolded), or `source`/`.` of it; reading it (`cat`, `grep`, `git diff`) is not judged. The §4.7 token `*gtm_approve*` already forwards it. Tests (B1 at `decision()` level, B2 through the patched dispatcher; each RED when the clause is removed): `bash ~/.claude/scripts/gtm_approve.sh trust-edit /x`, `gtm_approve.sh apr_x_1_ab` and `~/.claude/scripts/gtm_approve.sh operator-ok resume x PAUSE` denied `agent-approver-script`; `cat ~/.claude/scripts/gtm_approve.sh` allowed. **Running the GTMApprover binary or bundle** (`agent-approver-binary`, every session; `requests/05_approver.md` R57 applied — its signing, key-generation and `--generate-key --rotate` modes are reachable without the script, and an agent-raised Touch-ID prompt is the reflexive-consent hazard): a segment whose verb or script operand (after the §4.2 unwrapping, incl. `env`/`exec` prefixes and recursing into `bash -c` text) has a `canon` ending in `GTMApprover.app/Contents/MacOS/GTMApprover` or equal to or under a directory named `GTMApprover.app` (casefolded; `gtm_env.approver_app_path()` and any other copy alike), or is a token equal (casefolded) to `GTMApprover` or `GTMApprover.app`; and `open` with `-a <v>` where `v` casefolded is `gtmapprover`, `gtmapprover.app` or a path ending in `gtmapprover.app`, with `-b <v>` where `v` casefolded contains `gtmapprover` or `com.oversight.gtm.approver`, or with a `GTMApprover.app` path operand (with or without `--args`). **Rebuilding the approver** (`agent-approver-rebuild`, every session; `requests/05_approver.md` R36 applied — a rebuild is an operator act in his own terminal, 05_approver.md §5.3 "Binary integrity"): running `tools/gtm/approver/build.sh` (verb or script operand, any spelling whose `canon` ends in `tools/gtm/approver/build.sh`); any `swiftc` or `codesign` segment whose argv carries a token containing `gtmapprover` (casefolded) or an operand under a `GTMApprover.app` directory; and `ditto`/`cp`/`mv`/`rsync`/`install`/`ln` with a destination (or, for `mv`, a source) equal to or under a `GTMApprover.app` directory or naming `GTMApprover` (casefolded). Reading (`ls ~/Applications`, `codesign -dv` of another app, `cat`) is not judged. B2 tests through `bash_gate.sh` (each RED when its clause is removed; B1 asserts the same at `decision()` level): `~/Applications/GTMApprover.app/Contents/MacOS/GTMApprover --sign-trust-edit /x`, `open -a GTMApprover --args --sign-operator-ok resume x autonomous` and `env X=1 ~/Applications/GTMApprover.app/Contents/MacOS/GTMApprover --generate-key --rotate` denied `agent-approver-binary`; `bash ~/.claude/tools/gtm/approver/build.sh`, `swiftc -o /tmp/GTMApprover main.swift`, `codesign --force --sign - ~/Applications/GTMApprover.app` and `ditto /tmp/x.app ~/Applications/GTMApprover.app` denied `agent-approver-rebuild`; `ls ~/Applications` and `codesign -dv /Applications/Safari.app` allowed |
| h | GTM scope | any `screencapture`; any `osascript` other than a single `display notification` form (`ui-automation`) |
| i | Agency scope (§4.2: GTM scope, or a `DEPARTMENT_SEATS` agent whose cwd is not under Agency; unconditional, 00_global_paths.md §0.4) | commands naming `departments/marketing/`, a path whose `canon` is `gtm_env.VOLFS_SENTINEL` (any `/.vol` spelling; wave1e, R44) or is equal to or under `agency_root()` (after `base` resolution, incl. a preceding `cd`), `/Desktop/OtherApp` (casefolded), `oauth-google-`, any URL-shaped token for which `is_agency_github_url` holds (§4: github.com and subdomains, codeload.github.com, raw.githubusercontent.com, api.github.com `/repos/<org>/agency…`), the scp form `(?i)github\.com:[^/\s]+/agency([-_.][^/\s]*)?`, and in a `gh` command: a `-R`/`--repo` value (`-R x`, `-Rx`, `--repo x`, `--repo=x`) or a positional repo argument of `gh repo <sub>` / `gh issue` / `gh pr` matching `AGENCY_REPO_SLUG_RE`, or a `gh api` path matching `(?i)(^\|/)repos/[^/]+/agency([-_.][^/]*)?(/\|$)` (`agency-boundary`, 00_global_paths.md §0.1/§20.9a — which forbids opening, listing, grepping or **filing against** the OtherApp repo), **or a recursive search/copy rooted at an ANCESTOR of either Agency root** (the same ancestor treatment path-gate rule 1 gives Grep/Glob, §4.4): `grep`/`egrep`/`fgrep` with `-r`/`-R`/`--recursive`/`-d recurse` (in any cluster), `rg`, `ag`, `ack`, `find`, `fd`, `ls` with `-R` (in any cluster), `tree`, `du`, `tar`, `zip` with `-r`/`-R`, `rsync`, `cp` with `-r`/`-R`/`-a` (in any cluster), `ditto`, and `mdfind` with an `-onlyin` operand equal to or an ancestor of either Agency root **or no `-onlyin` at all** (it searches every volume), where a search root is each path operand (`canon`'d against every candidate base; a verb with no path operand — `rg foo`, `find`, `grep -r x` — is rooted at each candidate base) and it counts when it is **equal to or an ancestor of** `norm(agency_root())` or `norm(str(gtm_env.real_agency_root()))`, judged by **text only** (canon step (3) returns before any filesystem call for Agency-bound text, and the ancestor test compares normed strings, so nothing inside Agency is stat'd — the no-Agency-touch oracle of 00 §0.1 applies). In GTM scope rule j's `phi1_root()` ancestor clause coincidentally catches most of these (OtherCompany Files is also under `~/Desktop`); this clause makes rule i catch them on its own, including for the department-seat arm outside GTM scope where rule j does not run. `<org>` is unbound, so every repo named `agency*` is blocked in GTM scope (accepted fail-safe, §4 `is_agency_github_url`). B1 tests, each denied from a GTM session: `gh issue create -R org/Agency -t x`, `gh issue create --repo=org/Agency -t x`, `gh api repos/org/Agency/issues`, `gh repo clone org/Agency`, `git clone git@github.com:org/Agency.git`, `curl https://api.github.com/repos/org/Agency/contents`, `curl https://raw.githubusercontent.com/org/Agency/main/x`, `ls ~/Desktop/AGENCY`; `cat docs/agency_notes.md` allowed; from a **non-GTM** session with payload `agent_type: "marketing-director"` and cwd the CSA root, `ls ~/Desktop/OtherApp` and `gh issue create -R org/Agency -t x` denied, and the same with cwd inside the (tmp) Agency root allowed (each RED when rule i uses `gtm_scope` instead of `agency_scope`); from a non-GTM session with payload `agent_type: "marketing-director"` and cwd the CSA root, under the no-Agency-touch oracle, `grep -rn x ~/Desktop`, `rg foo ~`, `find ~ -name '*.md'`, `ls -R ~/Desktop` and `mdfind term` are denied `agency-boundary` (each RED without the ancestor clause) while `grep -rn x .` and `mdfind -onlyin . term` are allowed |
| j | GTM scope (`gtm_scope`: `CLAUDE_GTM_COMPANY` set or payload `agent_type ∈ GTM_SEATS`; `company` below = the slug, or `"*"` for a seat-only scope) | **Operands (binding for every clause of rule j):** after the §4.2 unwrapping, for every segment and every candidate base `b`: (i) every non-option argv token that starts with `/`, `~`, `$HOME`, `${HOME}`, `./` or `../`, or contains `/` and no `://`; (ii) the value of an option given as `--opt=<v>` or as the next token after an option, when `v` has the shape of (i); (iii) every redirect target, reading (`<`, `<<<` excluded: a here-string is data) and writing alike; (iv) every `cd` operand; (v) when `b` itself is outside the roots a clause allows, every bare non-option operand of a verb in `gtm_hooklib.PHI_READ_VERBS` (`cat`, `head`, `tail`, `less`, `more`, `grep`, `egrep`, `fgrep`, `rg`, `ag`, `ack`, `sed`, `awk`, `cut`, `sort`, `uniq`, `wc`, `strings`, `xxd`, `od`, `hexdump`, `file`, `stat`, `ls`, `find`, `fd`, `tree`, `du`, `cp`, `rsync`, `ditto`, `tar`, `zip`, `unzip`, `open`, `qlmanage`, `mdls`, `textutil`, `pdftotext`, `python`, `python3`, `node`, `perl`, `ruby`) joined to `b`; (vi) for a recursive/search verb (the list below) with no path operand, `b` itself (rule i's treatment) — each `canon(·, b)`; and every **URL token**: an argv token or an interpreter-code substring (rule k (2)'s set) matching `(?i)\b[a-z][a-z0-9+.-]*://[^\s'"<>]+`, plus, for the verbs `curl`, `wget`, `http`, `https`, `xh`, every non-option operand without a scheme, read as `https://<operand>`. Tokens inside interpreter code text are never path operands (a stated gap, as for rule a). **Clauses, first match wins:** (1) **`phi-denylist-unreadable`** — `phi_denylist()` is `PHI_UNREADABLE` (§4; 00_global_paths.md §1.2): any path operand whose `canon` is not equal to or under a root of `gtm_hooklib.phi_unreadable_roots(company, payload)` (the session company's `H`, `R`, the temp roots), and any URL token at all; (2) **`phi-host`** — any URL token for which `gtm_hooklib.phi_url_hit(url, company)` returns a label (a denylisted host or suffix, filtered by `applies_to`, **or a `url_prefixes` entry**, 03_schemas.md §3.20); (3) **`phi-path`** — a path operand equal to or under a `phi_denylist` `paths` entry, a bare host token (no scheme, no `/`) equal to an applicable `hosts` entry or ending in an applicable `host_suffixes` entry, or any path whose `canon` is under `phi1_root()` — **`phi1_root()` itself counts as "under" for a non-recursive command** — not equal to or inside a `othercompany_read_allowlist.json` folder (default-deny while that file is absent, 03_schemas.md §3.20); or a **recursive** search/copy rooted at an **ancestor** of a listed path or of `phi1_root()` (`phi1_root()` itself counts as an ancestor here): `grep`/`egrep`/`fgrep` with `-r`/`-R`/`--recursive`/`-d recurse` (in any cluster), `rg`, `ag`, `ack`, `find`, `fd`, `ls` with `-R` (in any cluster), `tree`, `du`, `tar`, `zip` with `-r`/`-R`, `rsync`, `cp` with `-r`/`-R`/`-a` (in any cluster), `ditto`, and `mdfind` (an `-onlyin` operand equal to, under or an ancestor of a listed path or `phi1_root()`, **or no `-onlyin` at all**, which searches every volume); (4) **`phi-scope-outside-allowed`** (00_global_paths.md §1.2 "OtherCompany read scope", DECIDED there; unconditional in GTM scope, §0.4) — when `gtm_hooklib.hipaa_scope(company)` holds (a pack that does not load counts): any path operand whose `canon` is not equal to or under a root of `gtm_hooklib.phi_allowed_roots(company, payload)` (`H`, each allowlisted OtherCompany folder, `R`, the temp roots — clause (3) already denied a denylisted path inside them, so denylist `path` entries win), and `mdfind` with no `-onlyin`. **Fail mode of rule j (a stated exception to G-B's allow-on-exception):** an internal exception while evaluating rule j in GTM scope denies `gate-fault` when any operand, by text alone (`norm_text(abspath(join(b, expanduser(t))))`, no filesystem call), is equal to, under or an ancestor of `phi1_root()`, or — under `hipaa_scope` — is outside `phi_allowed_roots`, or when the command carries any URL token; otherwise allow + `gate-fault`. B1 tests (decision level; each RED when its clause is removed): `mdfind -onlyin ~ term`, `mdfind term`, `cp -a ~/Desktop /tmp/y`, `cp -R ~ /tmp/y`, `ls "~/Desktop/OtherCompany Files"` and `grep -Rn x ~/Desktop` denied from a GTM session; with a `url_prefixes` entry `https://x.example/r/abc`, from a OtherCompanyB GTM session `curl https://x.example/r/abc/page2`, `curl -s x.example/r/abc`, `wget -qO- http://X.example/r/abc` and `python3 -c "import urllib.request as u; u.urlopen('https://x.example/r/abc')"` are denied `phi-host` while `curl https://x.example/r/abcd` is allowed (RED when rule j checks hosts only); from a **OtherCompany** GTM session (`regulated ∋ hipaa`) `cat <tmp HOME>/Documents/x.pdf`, `cp ~/Documents/x.pdf /tmp/` and `cd ~/Documents && cat x.pdf` are denied `phi-scope-outside-allowed` while `cat <H>/notes.md`, `ls /tmp` and `cat ~/.claude/tools/gtm/README.md` are allowed, and the same `cat <tmp HOME>/Documents/x.pdf` from a **OtherCompanyB** GTM session is allowed (RED when clause (4) ignores `hipaa_scope`); with `phi_denylist.json` deleted while the OtherCompany pack is registered, `cat <tmp HOME>/Desktop/<a formerly denylisted file>` is denied `phi-denylist-unreadable` from both a OtherCompany and a OtherCompanyB GTM session, and `cat <H>/x` is allowed (RED when `phi_denylist()` returns an empty denylist on a missing file); with `phi_denylist()` made to raise a bug exception, a GTM-session `cat ~/Desktop/Practice\ 32\ Files/x` is denied `gate-fault` and `echo ok` is allowed |
| k | all | the literals of `system_names.RULE_K_LITERALS` — `GTM_ALLOW_TRUST_EDIT`, `GTM_HOLDS_JOB`, `trust_edit_allow`, `operator_ok` (00_global_paths.md §1.4 "Shared literals"; imported, never restated in the hook) — **where a literal can take effect** (`inline-trust-escape-forbidden`; the holds-job marker, the trust-edit marker, the operator-marker directory `S/operator_ok/` and its creator script `operator_ok.sh` are operator/launchd-only, 00_global_paths.md §1.4, 02_act.md §2.3, §4.3): (1) a `NAME=` assignment at any position whose text contains a literal — the `_strip_prefix` prefix, `env` arguments, `export`/`declare`/`typeset`/`local`/`readonly` operands; (2) interpreter code text — `python[3] -c`, `node -e`, `perl -e`, `ruby -e`, `bash\|sh\|zsh -c` — and the raw heredoc/stdin body of a stdin-fed interpreter (`python3 - <<EOF`); (3) a write target of rule c's write class whose text contains a literal; (4) an executed program — the verb (after unwrapping) or the script operand of `bash\|sh\|zsh\|python[3]\|perl\|node <script>` — whose basename contains a literal (running a marker-minting script, e.g. `tools/gtm/operator_ok.sh`). **Everything else is not judged** — `git` subcommands (`git add`/`commit`/`diff`/`show -- …/test_trust_edit_allow.py`), `grep`/`rg`, `cat`, `sed -n`, `head`, `ls`, `ruff check`, `pytest` and the like read or name such files legitimately (IMP-04, widened). Rule k is a speed bump: the trust-edit marker is GTMApprover-signed (§4.3) and so not trusted on presence; the operator marker is single-use and short-lived, with its residual stated in 02_act.md §2.3. B1 tests: `grep -rn GTM_HOLDS_JOB tools/gtm`, `python3 -m pytest -k trust_edit_allow`, `git commit -F m -- tools/gtm/tests/test_trust_edit_allow.py` (from a **non-GTM** session; in GTM scope rule n denies a commit under `R`), `grep -rn operator_ok tools/gtm` and `cat tools/gtm/docs/operator_ok.md` allowed; `GTM_HOLDS_JOB=1 python3 act.py run-holds --all`, `env GTM_HOLDS_JOB=1 python3 act.py run-holds --all`, `export GTM_HOLDS_JOB=1`, `python3 -c "open('<S>/operator_ok/resume.x.PAUSE.json','w')"`, `bash <R>/tools/gtm/operator_ok.sh resume x PAUSE`, `env -u CLAUDECODE bash ~/.claude/tools/gtm/operator_ok.sh resume other-company PAUSE.website_wordpress@remodeling`, `echo {} > /tmp/trust_edit_allow.json` and `grep x f; GTM_HOLDS_JOB=1 python3 act.py run-holds --all` denied; the two `operator_ok` denials go RED when `operator_ok` is dropped from the list; and the hook's literal set `==` `set(system_names.RULE_K_LITERALS)` with `system_names.OPERATOR_OK_DIRNAME in RULE_K_LITERALS` (02_act.md §2.3, 00_global_paths.md §1.4) |
| l | all sessions; **unconditional** (00_global_paths.md §0.4) | `gtm-identity-forge` (02_act.md §2.3; `requests/00_global_paths.md` R20): in a command any segment of which **names act.py** (below), any assignment of a variable matching `CLAUDE_GTM_[A-Z0-9_]*` — a `NAME=value` prefix (the `_strip_prefix` assignments), an `env [-i] NAME=value` argument, `env -u NAME`/`--unset=NAME`, `unset NAME`, `export NAME[=…]`, `declare -x`/`typeset -x`/`local -x NAME[=…]`, `readonly -x` — judged on the parsed assignments **and** on the raw command text (casefolded regex `(?<![\w])(env\s+(-[a-z]+\s+)*)?(export\s+\|declare\s+-x\s+\|typeset\s+-x\s+\|unset\s+\|-u\s*)?claude_gtm_[a-z0-9_]*\s*(=\|\s\|$)`, after removing quote characters, so `"CLAUDE_GTM_COM""PANY=x"` is caught). **Names act.py** = the raw segment text, casefolded, matches `(?<![\w.-])act\.py(?![\w])` (so `contract.py` and `test_act.py` do not), or an operand's `canon` against any candidate base equals `R/tools/gtm/act.py`. **Exempt:** a segment whose command word is `pytest` or `python[3] -m pytest` (the rule-m shape), and only that segment. The hook-set session variables in the process environment are not judged (only command text). Tests (B1: `decision()` returns `(True, "gtm-identity-forge", …, True)`; B2: the same commands denied through the patched dispatcher with **no** enforce marker in the tmp `HOME`; RED when the rule is removed or left conditional): `CLAUDE_GTM_COMPANY=x python3 ~/.claude/tools/gtm/act.py propose …`, `env CLAUDE_GTM_SESSION=y python3 act.py status` (cwd `~/.claude/tools/gtm`), `export CLAUDE_GTM_COMPANY=x; python3 ~/.claude/tools/gtm/act.py status`, `unset CLAUDE_GTM_COMPANY && python3 …/act.py pause`; allowed: `grep -rn CLAUDE_GTM_COMPANY tools/gtm` (no segment names act.py), `CLAUDE_GTM_COMPANY=x python3 -m pytest tools/gtm/tests/test_act.py` (exempt pytest segment) and `CLAUDE_GTM_COMPANY=x python3 tools/gtm/contract.py` (not act.py) |
| m | all sessions; **unconditional** (00_global_paths.md §0.4) | `gtm-env-override` (the 00_global_paths.md §1.1/§1.4 test-override arm; `requests/00_global_paths.md` R12/R20; extended by `requests/05_approver.md` R15 (b)): in a command any segment of which **names tools/gtm** — its raw text, casefolded, contains `tools/gtm`, `approval_sig` or `approvals_verify`, or names act.py (rule l's test), or an operand's `canon` against any candidate base is under `R/tools/gtm/` (so `GTM_TEST=1 python3 ai_budget.py …` with cwd `R/tools/gtm` counts) — any assignment (the same forms as rule l: prefix, `env [-i] NAME=`, `env -u`, `unset`, `export`, `declare -x`/`typeset -x`/`local -x`) of a `NAME` in {`CLAUDE_DIR`, `GTM_TEST`, `GTM_FAKE_NOW`, `HOME`} or matching `PYTHON[A-Z0-9_]*` (`PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `PYTHONSAFEPATH`, …), plus an `env -i` of any such segment (it drops `HOME` and the hook-trusted environment); judged on parsed assignments **and** raw text like rule l. **`-X` argv clause (DECIDED (wave1d), applying `requests/05_approver.md` R77 (b)):** on the same "names tools/gtm" segments, also deny a `python[3]` invocation carrying `-X pycache_prefix[=…]`/`-Xpycache_prefix[=…]` (any value — the isolated-subprocess rule above, §4, is the ONLY sanctioned source of that flag, and it always pairs it with `-I -S -B`; an agent-supplied one is a forgery attempt at the same argv shape) or `-X frozen_modules[=…]`/`-Xfrozen_modules[=…]` (can mask a source edit behind a stale compiled module) — as a literal `-X <name>` token pair or a combined `-X<name>=…`/`-X<name>` token, wherever it appears in the segment's argv, not only immediately after the interpreter name (`python3 tools/gtm/act.py -X pycache_prefix=/tmp/x status` counts too). **That over-denial is intended (DECIDED (wave1e), finding wave1d-n3):** after the script path, `-X …` is an argument to the script, not an interpreter option, so it cannot set the prefix — but no GTM entry point takes an `-X` argument, the argv-position parse needed to tell the two apart is the kind of shell-grammar judgement G-B avoids, and denying a meaningless argument costs nothing an automated path uses. **Exempt:** the same `pytest`/`python[3] -m pytest` segments rule m already exempts above. **Exempt:** a `-I -S -B -X pycache_prefix=<path under gtm_env.gtm_tmp_root()>` triple issued by a hook's own isolated-subprocess call is not a Bash-tool command at all (hooks spawn via `subprocess.run`, never a shell `python3 …` Bash call), so this clause never fires on the mechanism it is protecting. **Exempt:** a segment whose command word after `_strip_prefix` and the §4.2 unwrapping is `pytest` or `python[3] -m pytest` (the rule-k IMP-04 shape: tests set `GTM_TEST`/`CLAUDE_DIR` legitimately), and only that segment. Shell state does not persist between Bash tool calls (a separate earlier `export` cannot reach a later call). Tests (B1: `decision()` returns `(True, "gtm-env-override", …, True)`; B2: the same commands denied through the patched dispatcher with no enforce marker; RED when removed or conditional): `CLAUDE_DIR=/tmp/x python3 ~/.claude/tools/gtm/act.py status --company x`, `GTM_TEST=1 GTM_FAKE_NOW=2030-01-01T00:00:00Z python3 …/act.py run-holds --company x`, `HOME=/tmp/h python3 …/act.py status`, `PYTHONPATH=/tmp/evil python3 ~/.claude/tools/gtm/act.py status`, `export PYTHONSTARTUP=/tmp/x.py; python3 …/approval_sig.py --trust-check`, `env PYTHONHOME=/tmp python3 …/act.py status`, `python3 ~/.claude/tools/gtm/act.py -X pycache_prefix=/tmp/evil status`, `python3 -Xfrozen_modules=on ~/.claude/tools/gtm/act.py status`; allowed: `GTM_TEST=1 python3 -m pytest tools/gtm/tests/…` and `CLAUDE_DIR=/tmp/x pytest tools/gtm/tests` |

| n | GTM scope; **unconditional** (00_global_paths.md §0.4; `requests/05_approver.md` R33 applied, widened) | `gtm-git-write`: a segment whose verb (after the §4.2 unwrapping, plus `xcrun`) is `git` is judged on its parsed global options and subcommand. **Denied global forms:** `-C <dir>` / `--git-dir[=]` / `--work-tree[=]` / `--namespace` naming anything but the exception's toplevel (below), every `-c <k>=<v>` and `--config-env` (an inline `alias.*`, `core.hooksPath`, `core.fsmonitor`, … can rename or re-route any subcommand), and any `GIT_[A-Z0-9_]*=` assignment on the segment other than `GIT_PAGER`/`GIT_TERMINAL_PROMPT` (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_REPLACE_REF_BASE`, …). **Denied subcommands:** everything except the read set and the two exceptions below — explicitly `apply`, `am`, `merge`, `cherry-pick`, `revert`, `pull`, `rebase`, `update-index`, `read-tree`, `checkout-index`, `rm`, `mv`, `stash`, `restore`, `commit`, and (default-deny) `replace`, `update-ref`, `symbolic-ref`, `commit-tree`, `hash-object`, `fast-import`, `filter-branch`, `filter-repo`, `notes`, `config` (other than `--get`/`--get-all`/`--list`/`-l`), `worktree` (other than `list`), `submodule`, `checkout`, `switch`, `reset`, `clean`, `branch` (other than listing: no operand, `--show-current`, `--list`, `-a`, `-r`, `-v`), `tag`, `push`, `fetch`, `clone`, `init`, `gc`, and any **unknown** word (an alias). **Read set (allowed, unjudged):** `status`, `diff`, `log`, `show`, `ls-files`, `ls-tree`, `rev-parse`, `rev-list`, `blame`, `grep`, `cat-file`, `describe`, `shortlog`, `merge-base`, `name-rev`, `for-each-ref`, `show-ref`, `diff-tree`, `diff-index`, `diff-files`, `check-ignore`, `var`, `version`, `help` — each denied when it carries `--output[=]`/`--output-directory` (a file write rule c does not see) — and `add -- <literal paths>` (staging only; no `-A`/`.`/`-u`/`-p`/`--chmod`, gates 1–2 already refuse bulk forms; a path equal to or under `R` or `real_root()` denies; a path that, relative to H and casefolded, matches a glob of the committed pack's `marketing_paths` under `system_names.glob_full_match` denies `gtm-git-write` — exception (i)'s `apply --index` already stages the reviewed bytes, so a hand `git add` of a marketing path can only stage unreviewed ones). **Both exceptions are bound to an AUTHORIZED action (plan §6.5/§20.9c: a `website_static` review binds the exact patch before execution).** `ST/patches/<action_id>.patch` exists from `propose` on (02_act.md §2.4: `propose` copies the `--patch` file there), i.e. before any lane review and before authorize — so the file's existence proves nothing, and an action that is `proposed`, `changes_requested`, `superseded`, `cancelled` or `failed` must not be applicable. The one authority is the hash-chained fold, read through **`gtm_hooklib.authorized_static_action(slug, action_id) -> dict`**: it runs `<gtm_env.TRUSTED_PYTHON> -I -S -B -X pycache_prefix=<fresh P> <T>/tools/gtm/act.py status --action <action_id>` (the isolated form of 05_approver.md §5.5 step 0; stdlib `subprocess`, the hook's own environment unchanged — the session's `CLAUDE_GTM_*` variables included — 10 s timeout), requires exit 0 and exactly one JSON object on stdout (02_act.md §2.3 "Output"), and returns the action's fold record from `result.actions[0]` (the shape `requests/04_hooks.md` R42 asks 02 to fix) — act.py itself runs the trust-root check (step 0) and `store.verify_chain` before it folds (02_act.md §2.3 read-policy pipeline), so a tampered `act.py`, a broken chain or an edited `actions.jsonl` makes it exit non-zero. It raises `ActionNotAuthorized(detail)` on a non-zero exit, a timeout, output that is not one JSON object, a missing record, `record.state != "authorized"`, or a record whose row is not a `website_static` row (`record.row_id` does not start with `website_static.`) — every such case, and any exception inside the helper, is a **deny** with reason `gtm-git-write:patch-not-authorized` (the composite reason string, §4.2 `decision()`; fail closed; this helper never takes G-B's allow-on-internal-exception path). `patch_paths(patch_bytes) -> set[str]` = the union of the `a/<p>` and `b/<p>` paths of every `diff --git a/<p> b/<q>` header line (git's own path source for a patch; `/dev/null` excluded; C-quoted names unquoted per git's rules; a patch with no such header, or a header that does not parse, → raise → deny). **Exception (i) — the reviewed patch:** `git [-C <tl>] apply [--check] --index <p>` with exactly those options, run **in an interactive run** (§4.3 "Interactive run"), where `<tl>` — the `-C` value, else every candidate base — canon-equals the toplevel of the session company's home (`/usr/bin/git -C H rev-parse --show-toplevel`, hardened env as `git_show_head`), and `canon(p)` is directly under that company's `ST/patches/` (`<H>/.claude/gtm/state/patches/`), named `<action_id>.patch` with `action_id` matching the 00_global_paths.md §0.3 action-id regex for this slug, the file exists (02_act.md `website_static` executor), **and** all of: (a) `record = authorized_static_action(slug, action_id)` succeeds (state `authorized`, a `website_static` row); (b) `hashlib.sha256(<the patch file's bytes, read once by the hook>).hexdigest() == record.after.patch_sha256` (bare lowercase hex, 03_schemas.md §3.4 `website_static` `after`); (c) `patch_paths(<those bytes>) == set(record.after.paths)` (home-relative, compared after `canon(·, tl)` on both sides); (d) every path of `patch_paths(<those bytes>)`, relative to H and casefolded, matches some glob of the **committed** pack's `marketing_paths` under `system_names.glob_full_match` and matches **no** `system_names.MARKETING_PATH_NEVER` entry — the hook's own check, independent of act.py's check 9 (02_act.md §2.8), so a wrong authorized record (a bug, or one authorized before a pack narrowing) can never put application code or `marketing/website/build.mjs` into the working tree, where a non-GTM peer could commit it (plan §20.9c); (e) every path of `patch_paths(<those bytes>)` is clean against HEAD in both the working tree and the index before the apply — `/usr/bin/git -C <tl> diff --quiet HEAD -- <paths>` (working tree = HEAD) and `/usr/bin/git -C <tl> diff --cached --quiet HEAD -- <paths>` (index = HEAD), hardened env, 5 s each, both exit 0 — so the reviewed patch applies onto clean state and no peer's staged or unstaged edit of those files is carried into the arm-(a) commit (exit 1, any other exit or a timeout fails (e)). Otherwise deny with reason `gtm-git-write:patch-not-authorized`. **Exception (ii) — the pack-scoped commit:** `git [-C <tl>] commit -F <f> -- <p1> [<p2>…]` (or `--file=<f>`/`--file <f>`; no other option: `-a`, `-m`, `--amend`, `-n`/`--no-verify`, `--allow-empty`, `-C`, `--fixup`, `--pathspec-from-file` all deny), run **in an interactive run only** (every arm below; 02_act.md: `complete --commit` and the `website_static` executor are interactive-only, and scheduled sessions never execute it), `<tl>` as in (i), at least one path, every path a literal (no `:(` magic, no `*?[`, no unexpanded `$`/backtick/`~`), **no** path matching `system_names.MARKETING_PATH_NEVER` under `system_names.glob_full_match` (the one never-list of 08_seats_wps.md Appendix C item 13 and 02_act.md §2.8 check 9 — e.g. `marketing/website/build.mjs`, the CSA AI-provenance publish gate — defined once in the hook-importable `system_names` and re-exported by `gtmlib.checks`, `requests/04_hooks.md` R44; no pack key re-admits it, 00_global_paths.md §0.1), and **either** the whole pathspec satisfies arm (a) **or** every `canon(p, tl)` satisfies one of arms (b)–(d): (a) **the reviewed-patch commit** — the pathspec set, relative to H and casefolded, equals `set(record.after.paths)` of an action `A` for which `authorized_static_action(slug, A)` succeeds and whose stored patch is applied in the index (`/usr/bin/git -C <tl> apply --cached --reverse --check <H>/.claude/gtm/state/patches/<A>.patch`, hardened env, 5 s, exits 0) **and whose index and working tree hold exactly the reviewed post-image for every pathspec path**: for each path `p`, the index blob (`/usr/bin/git --literal-pathspecs -C <tl> ls-files --stage -z -- <p1> [<p2>…]`, one call, the entry whose path equals `p`) equals `record.after.post_image[p]` (03_schemas.md §3.4 `website_static` `after`), and the working-tree blob (`/usr/bin/git -C <tl> hash-object -- <every p whose post_image is not null>`, one call, no `-w`, so git applies the same clean filters `commit` would) equals the same blob; for a `post_image[p]` of null (a deletion) `p` has no index entry and `os.path.lexists(<tl>/<p>)` is false; hardened env, 5 s each. `git commit -F f -- <paths>` is git's `--only` form, which commits the **working-tree** contents of those paths, and `apply --cached --reverse --check` proves only that the patch's hunks are present, not that nothing else is — so without the blob equality an interpreter write after `apply --index` (a stated rule-c gap) or a peer's edit of the same file staged under CSA's announce rule (step 3: every committing peer stages every unstaged tracked path by name) would land bytes no lane reviewed (plan §6.5/§20.9c). Any blob mismatch, a pathspec path with no `post_image` key, a non-zero exit or a timeout → deny with reason `gtm-git-write:patch-not-authorized`; where `A` is found by `act.py status --state authorized` (same isolated form) filtered to `website_static` rows whose `after.paths` set equals the pathspec set — none, or more than one, → deny with reason `gtm-git-write:patch-not-authorized`; or (b) equal to or under a pack-declared editable `H / paths.<key>` entry that `gtm_session_write_verdict` admits (§4.3 clause (3)); or (c) the company's operator-input file (the path rule c's GTM-scope arm uses); or (d) a home-relative path listed in `ST/pending_commit.txt` (plan §3.2 weekly commit step; 00_global_paths.md §1.2) **that is also** equal to or under an `H / paths.<key>` entry of the committed pack (any key — the queue file, CHANGELOG, feature inventories and the METRICS render plan §3.2 names are all pack-declared; machine-written ones included, which arm (b) excludes) or is the company's operator-input file — so a `pending_commit.txt` line naming CSA `modules/**` or any other undeclared path admits nothing (plan §20.9c); a path matched by the committed pack's `marketing_paths` is admitted **only** through arm (a) (so a pathspec mixing an arm-(a) set with other paths fails arm (a)'s equality and, holding a marketing path, fails (b)–(d) too, and denies); and **no** path is a `trust_root_path()` target or equal to or under `R` or `real_root()`. A seat-only scope (`"*"`, no company) admits neither exception. **Stated residual (TOCTOU):** the hook hashes the patch file, then `git` reads it; a parallel Bash call that rewrites `ST/patches/<id>.patch` through a shell form rule c does not parse, inside that window, is not prevented — `complete --commit`'s `patch_mismatch` (every committed blob must equal `after.post_image`, 02_act.md) and `validate_run`'s `gtm_commit_unexplained` (R37) are the detect-after. **Interpreter-issued git (stated speed bump):** in GTM scope, interpreter code text of rule k (2)'s set (`python[3] -c`, `node -e`, `perl -e`, `ruby -e`, a stdin-fed interpreter's raw body) that contains the word `git` together with `subprocess`, `os.system`, `os.exec`, `os.popen`, `spawn`, `child_process` or `execSync` is also denied `gtm-git-write`; a string-built command name remains a known gap, and a HEAD moved that way is backstopped only by `requests/04_hooks.md` R36 (05: an operator-signed anchor of HEAD's TRUST_PATHS tree). **Why:** plan §20.9c ("not allowed to … start changing features") — without this a GTM session can write a patch to `/tmp` (G-W clause (2)) and `git apply` it into CSA `modules/**`, and R25's detect-after covered marketing paths only; plan §20.8 N1 ("the trust root is not agent-editable") — `git -C ~/.claude apply` of a patch replacing `tools/gtm/approver_pubkey.pem` (or `act.py`) then `git commit` moves HEAD, and act.py and G-W both trust HEAD's key (§4.3 step 2), so non-operator signatures would verify. The gate-3b review record is self-recordable, so it is not a control here. B1 tests at `decision()` level (reason strings exact) and B2 tests through `pretooluse_bash.py` with no enforce marker (§4.2 "Test labelling"), each RED when the rule is removed: from a GTM session, `git apply /tmp/x.patch` (touching `modules/a.py`) is denied; from a GTM seat, `git -C ~/.claude commit -F m -- tools/gtm/approver_pubkey.pem` is denied; `git -c alias.x=apply x /tmp/p` and `GIT_DIR=/x git status` are denied; `python3 -c "import subprocess; subprocess.run(['git','apply','/tmp/p'])"` is denied; in an interactive run at the home toplevel, with a fixture `act.py status` reporting action `<id>` `authorized`, row `website_static.page_edit`, `after.paths == ["marketing/website/index.html"]` and `after.patch_sha256` equal to the stored patch's hash, `git apply --index <H>/.claude/gtm/state/patches/<id>.patch` is allowed and, once that patch is applied in the index (fixture `after.post_image` = the applied blob, working tree equal to index), `git commit -F m -- marketing/website/index.html` is allowed; `git commit -F m -- modules/a.py` is denied, and the same `git apply --index` in a scheduled run is denied. **Authorization binding (each RED when its clause is removed; every denial below has reason exactly `gtm-git-write:patch-not-authorized`, and the unauthorized-verb denials above exactly `gtm-git-write`):** the same apply is denied when the fold reports the action `proposed`, and when it reports `changes_requested`; when the stored patch's bytes no longer hash to `after.patch_sha256`; when the patch touches a path not in `after.paths`; when `act.py status` exits non-zero (a broken chain) or times out; and a commit of `marketing/website/index.html` with no authorized action whose `after.paths` equals the pathspec, or whose patch is not applied in the index, is denied; `git commit -F m -- marketing/website/build.mjs` is denied even though it matches `marketing/website/**` and even when an authorized action lists it (RED when the never-list is not subtracted); a **scheduled**-run `git commit -F m -- marketing/website/index.html` is denied (RED when arm (a) stays "any run kind"); after the allowed `git apply --index`, appending a line to `marketing/website/index.html` in the working tree (index unchanged) makes `git commit -F m -- marketing/website/index.html` denied (RED without the working-tree blob comparison); **the same append, then staged** (index and working tree both holding the appended bytes — the state any session's `git add` leaves) makes that commit denied (RED without the index-blob comparison against `after.post_image`: the earlier `apply --reverse --check` + `diff --quiet` pair passes it); a **peer-staged non-overlapping edit** of the same file (a line outside the patch's hunk context, present in index and working tree after the apply, as CSA's announce rule step 3 leaves it) makes that commit denied (RED without the post-image comparison); from a GTM session `git add -- marketing/website/index.html` is denied `gtm-git-write` while `git add -- <the pack's paths.changelog file>` is allowed (RED when the `marketing_paths` clause of `add` is removed); with a peer's unstaged edit of `marketing/website/index.html` present before the apply, the exception-(i) `git apply --index` is denied, and with that edit staged instead likewise (RED without check (e)); an authorized record whose `after.paths` and stored patch name `modules/a.py` (or `marketing/website/build.mjs`) makes the exception-(i) `git apply --index` denied although hash and path set match (RED without check (d)); with `ST/pending_commit.txt` listing `modules/a.py`, `git commit -F m -- modules/a.py` is denied, while a listed pack `paths.changelog` file is allowed (RED when arm (d) admits any listed path). One end-to-end B1 test runs the real `act.py status` once A1 has landed (§4 preconditions); the others stub the helper's subprocess; `git status`, `git diff HEAD -- x` and `git log -1` are allowed; every one of these commands from a non-GTM, non-seat session is **not judged** by rule n |

(`\|` in the table is the markdown escape for a literal `|`.)

**Activation is a post-Wave-2 step, not part of B2's Wave-2 commits (IMP-04; delivery per
08_seats_wps.md §9 B2 row, Appendix B #115).** Hooks run from the live `~/.claude/hooks/` files, so
G-B would go live the moment its wiring is saved there and would then block the Wave-2
implementers' own `rm`/`mv` of `gtmlib`/`act.py` files. Therefore, during Wave 2: B1 lands
`gtm_bash_gate.py` with its unit tests (nothing calls it); B2 does **not** save any edit into the
live `hooks/pretooluse_bash.py` or `hooks/bash_gate.sh`. B2 delivers the **G-B activation train** —
`_gtm_bash_block` and its one `resolve_block` call line in `pretooluse_bash.py`, and every
`bash_gate.sh` addition of §4.7 — as one unified diff, `tools/gtm/wave2_pending/b2_gb_wiring.patch`
(paths relative to `R`). B2's unit and §4.7 end-to-end tests apply that patch to copies of the two
files under the 00_global_paths.md §1.5 tmp `CLAUDE_DIR/hooks/` (the hook modules they import
symlinked beside them) and run the copied `bash_gate.sh` with `HOME=<tmp>/home`. **For every
end-to-end test through `bash_gate.sh` the tmp `CLAUDE_DIR` must be exactly `<tmp>/home/.claude`**:
`bash_gate.sh` runs `python3 "$HOME/.claude/hooks/pretooluse_bash.py"`, so the patched copies must
sit at `<tmp>/home/.claude/hooks/`; a tmp `CLAUDE_DIR` elsewhere would make the script run the
real, unpatched hooks (or none). A B2 fixture assertion checks `CLAUDE_DIR ==
os.path.join(HOME, ".claude")` before any end-to-end case runs. The coordinator
applies the patch, and deletes it, in the same post-Wave-2 step as G-W's registration (§4.8 item 4,
08_seats_wps.md Appendix C item 19), after every Wave-2 WP has landed, as one reviewed change (HIGH
tier: `hooks/`). Until then no G-B rule is in force anywhere; the Wave-2 posture is unchanged from
today.

**Backing up and reverting a protected file once G-B is live** (runtime CLAUDE.md §6
revert-and-rerun; 00_global_paths.md §1.5 item 7): back up with `cp <protected file> <scratch>/`
(allowed: `cp` sources are reads, rule c exception); revert and restore with the Edit/Write tool
(every file under the live `R/tools/gtm/` subtree except `tests/`, `connectors/*/tests/`,
`contracts/` and top-level `*.md` needs a fresh single-use, GTMApprover-signed
`S/trust_edit_allow.json` per file, §4.3), or with `git diff HEAD -- <file> >
<scratch>/x.patch` and `git apply [-R] <scratch>/x.patch` from a **non-GTM** session (git subcommands are never rule-c writes, and rule n judges git only in GTM scope;
a `git apply` that changes a TRUST_PATH leaves the working tree ≠ HEAD, so
`trust_root_ok` fails closed until it is restored — which is the point of the check, §4.2 rule c
"Known shell-write reach"). Restoring with `cp <scratch>/x <protected>` or `mv` is denied. GTM tool development normally happens in a lane or
worktree (05_approver.md §5.6), whose paths are not `R/tools/gtm/…` and so are not protected.

**The GTM-seat arm on Bash payloads is UNVERIFIED (I24).** Probe a verified `agent_id`/`agent_type`
only on MCP tool payloads, and `pretooluse_bash.py`'s own `_identity` docstring states a Bash payload
carries no agent type. New **probe q** (coordinator records it in plan §17 before B1 relies on the
arm): capture a real `PreToolUse` payload for a Bash call and for a Read call made **by a
subagent**, and record whether `agent_type`/`agent_id` are present, as vendored fixtures
`hooks/tests/fixtures/payload_subagent_{bash,read}.json`. **Fallback when absent:** the seat arm is
inert for that tool (it simply never matches), and the relied-on controls are the env arm (a
subagent's Bash runs in its parent's process env, so `CLAUDE_GTM_COMPANY` reaches it — probe f)
plus gate-gtm step 0 (a GTM seat cannot be dispatched outside a GTM session). Stated plainly:
gate-gtm fails open on a fault, so in that fallback a GTM seat dispatched during a gate-gtm fault
from a non-GTM session would run its Bash/Read without the PHI/Agency arms; the B1 tests assert the
arm's behavior against the recorded fixtures, whichever way probe q comes out. The same probe
decides `agency_scope`'s department-seat arm (rule i, G-A 3b, path-gate rule 1): when Bash/Read
payloads carry no `agent_type`, that arm is inert too, and a department seat dispatched from an
ordinary session is then covered only by prose and code review (00_global_paths.md §0.4's stated
residual) — the fallback is the same, and the tests run against the recorded fixtures.

Fail mode: a command that cannot be tokenized (or that one of the clauses above sends to
`untokenizable-gtm-command`: a non-literal `cd` operand, a removal or write verb under `xargs`, a
redirect operator followed by no word) is **denied** `untokenizable-gtm-command` only when it
carries a **deny token**, and is otherwise allowed and logged (`untokenizable-allowed`, with the
command's sha256 and length — never its text, which may carry a secret); any internal exception → allow + log `gate-fault` (the stated
exceptions are rule n's `authorized_static_action`, which denies, the GTM-scope fail-closed cases
of rules d1 and c, and rule j's own fail mode, which denies `gate-fault` when an operand can reach
PHI by text, §4.2 rule j; an unreadable `phi_denylist.json` is not an exception at all —
`phi_denylist()` returns `PHI_UNREADABLE` and rule j clause (1) denies). **Deny tokens (`gtm_hooklib.UNTOKENIZABLE_DENY_TOKENS`, DECIDED HERE — deliberately
NOT the §4.7 forwarding list):** the §4.7 list was built for forwarding, where over-breadth only
costs a spawn ("forwards more, never less"); reused as an unconditional deny trigger it would deny
any unbalanced-quote command in any session that merely mentions `youtube`, `connectors`,
`missions`, `approvals` or `.jsonl`. The deny set is only the names whose parse failure could hide a
trust-root, state-dir or act.py write, or a rule k/l/m literal — matched casefolded as substrings of
the **raw command text** (never the rest of the payload): `tools/gtm`, `act.py`, `approver_pubkey`,
`approval_sig`, `approvals_verify`, `gtm_env`, `telemetry/pricing`, `.gtm_state`, `.claude/gtm`,
`gtm/state`, `actions.jsonl`, `tool_trail.jsonl`, `activity_log`, `lead_fallback`,
`schedules/disabled`, `claude_gtm_`, and every `system_names.RULE_K_LITERALS` member, lowercased;
**plus** the payload-cwd arm: the command is also a deny-token command when a candidate base (the
payload cwd or a `cd` target) is equal to or under `R/tools/gtm/` (`trust_root_path` or its root) or
is classified by `machine_written()` (a relative target from there is protected without naming
any token). A P2 test asserts the set is exactly this list plus `RULE_K_LITERALS` and that every
member is also matched by a §4.7 forwarding token (so a deny-token command always reaches G-B).
B1 tests: an untokenizable `echo "it's > log.jsonl` from a non-GTM session with no enforce marker
and cwd the CSA root is **allowed** and logged `untokenizable-allowed` (RED when the §4.7 list is
the deny set); `echo "it's > act.py` from the same session is denied `untokenizable-gtm-command`;
`echo "it's > x` with cwd `H/.claude/gtm/state` is denied (cwd arm); `cd "$D" && rm x` with cwd the
CSA root and no deny token is allowed and logged.
Wiring (WP-B2, `pretooluse_bash.py`): new `_gtm_bash_block(command, where, ev)` that
unpacks `(block, reason, message, unconditional) = gtm_bash_gate.decision_payload(command,
os.environ, <payload cwd>, ev)` and returns
`_Block("gtm_bash_gate", reason, message, git_state=False, unconditional=unconditional)` (not
escapable); `_Block`'s new `unconditional` field and `_finish`'s emit test are §4.9's
`pretooluse_bash` bullet (00_global_paths.md §0.4 mechanism). **`agent_type` =
`ev.get("agent_type")`, the payload's top-level field (IMP-23)** — never `_lib.subagent_type(ev)`,
which reads `tool_input.subagent_type`, a field Bash payloads do not have; whether the top-level
field is present on a subagent's Bash payload is probe q (above); absent → `None` and the seat arm
is inert. `_gtm_bash_block` imports `gtm_bash_gate` lazily inside a `try`, so an import error is an
internal exception (allow + `gate-fault`), never a crash of the Bash dispatcher. It is called in
`resolve_block` **immediately after `_gcloud_identity_block`** and before `_unscoped_commit_block`,
**and additionally whenever an earlier gate (1, 1b or 1c) returns a block whose `unconditional` is
False** — the shadowing rule 00_global_paths.md §0.4 DECIDES (`requests/00_global_paths.md` R38,
corrected by R41), restated here because rule n depends on it: `resolve_block` returns the first
gate that blocks, and gate 1 blocks `stash`/`reset`/`checkout`/`restore`/`clean`/`switch`/
`rebase`/`branch -d` with `git_state=True, unconditional=False`; without the rule, G-B would never
run for those commands, `_finish` would only log them with no enforce marker, and with `CSA_ALLOW_GIT_STATE_OPS=1` in
the hook's own environment it would escape-allow them — so rule n's unconditional GTM-scope deny of
every git state move would not happen. With the rule, whatever `_lib.enforcing(where)` returns,
`resolve_block` still calls `_gtm_bash_block` after such an earlier block; a G-B block with
`unconditional` True wins (the earlier block goes on the same log row as `shadowed_block`:
`resolve_block` sets `gtm_block.shadowed_block = f"{earlier.hook}:{earlier.reason}"` — a new
`_Block` slot, default `None`, §4.9 — and `_finish` writes it as that log row's `shadowed_block`
field when not `None`), and it
is built with `git_state=False`, so the escape hatch never applies to it; otherwise the earlier
block is returned as today (non-GTM behavior unchanged — rule n judges git only in GTM scope). B2
tests (through the patched `pretooluse_bash.py` copy, each RED under plain first-block-wins): in GTM
scope with no enforce marker, `git reset --hard` and `git stash` are denied `gtm-git-write`; with the
global enforce marker present and `CSA_ALLOW_GIT_STATE_OPS=1` set in the hook process's own environment (by the test
harness, never inline in a command), they are still denied `gtm-git-write`, and the log row of the `git stash` deny carries
`shadowed_block == "block_branch_ops:" + <gate 1's own reason for it>` (RED when the field is not
written); from a non-GTM session, `git stash` is still decided by gate 1 alone, unchanged. Both the function and the call reach the
live file only through the G-B activation train's patch (above).
Rules (a), (c) and (k) never fire on `git` subcommands (`git add/commit/show/diff -- tools/gtm/...`
are not writes by these rules; outside GTM scope the accepted consequence is stated in rule c's
"Known shell-write reach"). **In GTM scope rule n judges every `git` segment** (prevention, not
detect-after): a GTM session changes `marketing_paths` source files only, in an interactive run, by
`git apply --index` of `ST/patches/<action_id>.patch` for an action the hash-chained fold reports
`authorized` whose `after.patch_sha256` and `after.paths` match the file (exception (i) — so a
`proposed`, `changes_requested` or `superseded` action's stored patch is never applicable, and the
lane reviews that authorize binds are the reviews of exactly these bytes, plan §6.5/§20.9c),
followed by the `-F … -- <literal paths>` commit of exception (ii) arm (a), whose pathspec must
equal that authorized action's `after.paths`, whose index and working-tree blob of every pathspec
path must equal `after.post_image` (so neither an interpreter write after the apply nor a peer's
staged edit of the same file can ride along — the apply itself runs only onto paths clean against
HEAD, check (e)), and which must contain no `MARKETING_PATH_NEVER` path, and then `complete --commit` (02_act.md `website_static` executor;
G-W and rule c's GTM-scope arm deny every tool and shell write to those files); it cannot `git
apply` any other patch, commit application code (CSA `modules/**`), commit a never-listed path such
as `marketing/website/build.mjs`, commit marketing bytes other than the reviewed post-image, or
commit anything under `R` — the trust root included. **Detect-after backstop (widened R25, `requests/04_hooks.md` R37):**
`validate_run` reports every commit in a GTM run's window, on any path, that matches neither a
completed `website_static` action (its `after.paths` equal to the commit's path set) nor a
`pending_commit.txt` entry (`gtm_commit_unexplained`, severity urgent) — so a commit made through a
gap rule n does not parse (an interpreter-issued `git` with a string-built name) is still
reported; and `complete --commit` refuses `patch_mismatch` for its own action. These are
detect-after for the rule-n gaps only (an interpreter-issued `git` with a string-built name, the
stated TOCTOU on the patch file) — never the control for an unauthorized apply, which exception (i)
now prevents.

### 4.3 G-W `hooks/gtm_state_write_gate.py` (WP-B1) — PreToolUse `Write|Edit|MultiEdit|NotebookEdit`

Target = `canon` of `tool_input.file_path` (Write/Edit/MultiEdit) or `tool_input.notebook_path`
(realpath + casefold, §4 — `/Users/x/.claude/Tools/GTM/act.py` is `act.py`). Pack `paths.*` values
are relative to H (company.py `_rel`), so every one below is `H / paths.<key>`, canon'd.
Deny (`machine-written-path`, every session, unconditional — 00_global_paths.md §0.4) when
`gtm_hooklib.machine_written(target)` returns a class (§4; the same predicate G-B rule c uses, so
the two lists cannot drift): target is under `S`; or for **every GTM company**
(`company.gtm_slugs()`, 00_global_paths.md §0.1 — never an Agency home): under `<H>/.claude/gtm/state/`;
directly in `H / paths.activity_log_dir` and named `*.jsonl`, `*.jsonl.ids` (activity_log.py's
`TOOL_TRAIL.jsonl.ids` membership sidecar), `*.jsonl.ids.*.tmp` (activity_log's
`_write_sidecar_with_header` staging file), `.activity_log.lock` or `ACTIVITY_LOG.md` (machine-rendered;
company.py's generated gitignore lists it); equal to either owner-facing mirror file
(`gtm_hooklib.mirror_files(slug, pack)`, §4: `<expanduser(pack["mirror_dir"])>/<mirror_basename>.md`
and `.html` — `mirror_dir` is a TOP-LEVEL pack key, not under `paths`, and hooks ignore
`TS_ACTIVITY_MIRROR_DIR`); equal to `H / paths.scoreboard`; under
`H / paths.snapshots_dir` and not `*.md`; `*.json`/`*.jsonl` directly in `H / paths.missions_dir`
(writers use `mission_record.py`, 03_schemas.md §3.19); under `<H>/.playwright-mcp/`. **Pack
validator requirement (`requests/04_hooks.md` R26):** company.py rejects a pack whose
`feature_inventory_dir`, `plans_dir` or `metrics` path is under `.claude/gtm/state/` (today
activity_log.py defaults `feature_inventory_dir` there, which this list would make uneditable,
contradicting "feature inventories stay editable" below).

**Trust roots (`trust-root`; every session, unconditional — 00_global_paths.md §0.4).** Deny when
`gtm_hooklib.trust_root_path(target)` holds: the target is anywhere in the **live** `R/tools/gtm/`
subtree except `R/tools/gtm/tests/`, `R/tools/gtm/connectors/*/tests/`, `R/tools/gtm/contracts/` and
top-level `R/tools/gtm/*.md` — so `act.py`, `approver_pubkey.pem`, **`approval_sig.py` and
`gtm_env.py`** (which run before and as the trust-root check, 05_approver.md §5.5 step 0 — "this
pre-check set must be preventive", so an edit to them can never be left to detect-after; plan §20.8
N1 "the trust root is not agent-editable"; `requests/05_approver.md` R15 (a), R28), `gtmlib/`,
`setup_scripts/` (plan §20.10: the only `browser_evaluate` grant is bounded by a
trust-architect-reviewed allowlist; G-A reads it from HEAD anyway, §4.1 rule 12), `connectors/`,
`ai_budget.py`, `dispatch_tags.py`, `gtm_pricing.py`, `company.py`, `system_names.py`,
`project_dirs.py`, `tier_table.json`, … — or equal to `R/telemetry/pricing.json` — unless a
**single-use, operator-signed marker** admits it (F16;
replaces the former session-wide `GTM_ALLOW_TRUST_EDIT` env var, which was a standing per-session
bypass that runtime CLAUDE.md §7 forbids). Presence of a file can never be the control: agents can
write `S` through shell forms rule c does not parse (§4.2 rule c "Known shell-write reach": a
split-literal `python3 -c`, a heredoc-fed interpreter, `git apply`, `perl -pi`, `dd of=`, …), and a
marker's own `created_at` is agent-writable. So `S/trust_edit_allow.json` is a **GTMApprover-signed
record** (schema `gtm.trust_edit.v1`, `requests/03_schemas.md`, produced only by the operator's
`gtm_approve.sh trust-edit <absolute path>` → Touch ID, `requests/05_approver.md`):
`{"schema", "payload_b64", "signature_b64", "alg", "key_fingerprint", "signed_at"}`, where the
payload is the canonical JSON `{"v": 1, "kind": "trust_edit", "path": "<absolute target>", "nonce":
"<32 hex>", "expires": "<UTC, at most 15 min after signing>"}` with exactly those keys.
**Verification is never in-process** (00_global_paths.md §0.2: no GTM tool or hook imports a
third-party crypto package — a stub earlier on `sys.path` could return success; 05_approver.md §5.5
step 4 is the one backend definition for every approver-key signature; `requests/05_approver.md`
R38, extending R27). G-W admits the edit only through this exact sequence, holding
`S/trust_edit_allow.lock` (5 s timeout → deny) from step 1 through step 5:
1. read the marker's bytes `m0` from `S/trust_edit_allow.json` (absent or unreadable → deny);
2. run `<gtm_env.TRUSTED_PYTHON> -I -S -B -X pycache_prefix=<fresh P>
   <T>/tools/gtm/approval_sig.py --verify-trust-edit <target>` (§4 "Isolated subprocesses"; 5 s
   timeout). That mode (05_approver.md §5.5 canonical CLI) runs steps 0–2 first — so a marker admits
   an edit only while the trust tree is otherwise clean (one admitted edit, then its commit) — then
   verifies the marker with step 4's backends (`/usr/bin/openssl` for ECDSA P-256, the stdlib
   `ed25519_verify.py` for Ed25519) against `approver_pubkey.pem` read at `T` through the hardened
   `git show HEAD:` (the **committed** key, never the working tree — the file being edited may be
   the key — and never a `refs/replace/` substitute, §4), requires exactly the five payload keys,
   `kind == "trust_edit"`, `canon(payload.path) == canon(target)` and `expires > now` (`signed_at`
   is not signed and is never read), prints `{"ok", "reason", "nonce", "expires"}`, and **never
   consumes the marker**. G-W continues only when the process exits 0 within the timeout and its
   stdout is exactly one JSON object with `ok is True` and `nonce` matching `^[0-9a-f]{32}$`; exit
   7 (invalid), 11 (trust failure), 4 (no marker), 3/2/1, a timeout, a spawn error or any other
   output → deny;
3. re-read the marker's bytes `m1`; require `m1 == m0` (a marker swapped while the check ran
   denies), decode `payload_b64` from them with stdlib `base64`/`json` only, and require
   `payload.nonce` equal to the subprocess's `nonce` and `canon(payload.path) == target` (a
   belt-and-braces restatement of step 2 on the bytes G-W is about to spend);
4. **consume (G-W, never the subprocess):** under `S/approval_nonces.lock`,
   `S/approval_nonces.jsonl` holds no line for that nonce; G-W appends `{"ts", "company":
   "runtime", "request_id": null, "action_id": null, "nonce", "op": "consume", "holder":
   "trust-edit:<target>"}` (a trust-edit nonce goes straight from none to `consume`,
   `requests/03_schemas.md` §3.9);
5. **delete the marker (G-W)**, log `trust-edit-escape` with the target, and allow.
Single use is G-W's alone: the `consume` line makes a restored copy of the same marker fail step 4,
and the delete in step 5 removes it. Any failed step, and **any exception** on this path, denies
`trust-root` (it never admits on error). A second edit needs a new marker. **Blast radius (stated):** after activation, every
tool edit of a live `~/.claude/tools/gtm/` source file — from any session — needs one Touch-ID
marker per file; GTM tool development happens in a lane or worktree copy (`R/.claude/worktrees/…`,
05_approver.md §5.6), which is not under `R/tools/gtm/` and stays writable, and lands by `git
apply`/merge **from a non-GTM session** (git subcommands are never judged there; in GTM scope rule
n denies every git write under `R`, so a GTM session can neither apply nor commit a trust-root
change, plan §20.8 N1). During Wave 2, G-W is not registered (§4.8 item 4),
so Wave-2 implementers are unaffected. B1 tests, each falsified by dropping its check: an Edit of
`R/tools/gtm/approval_sig.py` and a Write of `R/tools/gtm/gtm_env.py` from a **non-GTM** session are
denied `trust-root` (RED when either is removed from `trust_root_path`); a Write of
`R/tools/gtm/tests/test_x.py`, of `R/tools/gtm/README.md` and of
`R/.claude/worktrees/w/tools/gtm/approval_sig.py` is allowed; a Write of `R/telemetry/pricing.json`
is denied. **G-W's own sequence** (the subprocess stubbed by a script in the tmp `T` that prints a
chosen JSON and exits with a chosen code): exit 0 with `{"ok": "true", …}`, exit 0 with two JSON
lines, and exit 7 each deny (RED with a truthiness or exit-code-only test); a marker whose bytes
the stub rewrites before exiting 0 is denied (RED without step 3's `m1 == m0`); a stub nonce that
differs from the marker's payload nonce is denied; a valid run admits exactly one edit, appends one
`consume` line and deletes the marker, and a copy of the marker restored afterwards (same nonce) is
refused (RED without step 4); the tmp `gtm_pyc_*` prefix is gone afterwards. **Verification**
(against the real `approval_sig.py` once 05's A2 has landed — §4 preconditions): an unsigned
marker with the right path and a fresh `created_at` is refused; one signed by a key other than
HEAD's is refused, including after `git replace` of HEAD's pem blob by that key's blob in the tmp
`R` (RED without `--no-replace-objects`, §4); one whose working-tree `approver_pubkey.pem` was
swapped to the signer's key is still refused (HEAD key); a stub package named `cryptography` that
returns success, placed first on `sys.path` of the hook process, leaves a forged marker refused
(`requests/05_approver.md` R38; RED with in-process verification); an expired marker is refused; a
valid marker is refused while another TRUST_PATH differs from HEAD (steps 0–2); a mixed-case
target spelling of `act.py` is treated as `act.py`.

**GTM-scope clauses** (`CLAUDE_GTM_COMPANY` set or payload `agent_type ∈ GTM_SEATS`):
- `operator-input-via-card-post` (F5): target is any GTM home's operator-input file (02_act.md §2.6
  card rule path): GTM sessions post cards only with `act.py card-post` and never write answers;
  non-GTM sessions are unaffected (they archive the operator's answers, 02_act.md §2.11). G-B rule
  c protects the same files from shell writes in GTM scope.
- `pack-edit-in-gtm-session` (FID-07): target is any GTM home's `<H>/.claude/gtm/company.json`,
  `review_lanes.local.json` or `connectors.json` — the pack decides isolation, HIPAA routing and
  marketing paths, so it changes only in a non-GTM session through that home's review gates (act.py
  refuses an uncommitted pack, 02_act.md §2.3; the hooks read the committed pack, §4
  `load_pack_safe`).
- `transcript-write` (FID-08): target is under `R/projects/` and not under `R/projects/*/memory/`
  (subagent transcripts are the maker-checker and verifier ground truth, 02_act.md §2.7(c); Claude
  Code writes them itself, never through these tools).
- `runtime-write-in-gtm-session`: target is under `R` — `R/hooks/**` (hook scripts are read on
  every invocation, so an edit disables the fail-closed backstops at once), `R/settings*.json`,
  `R/agents/**`, `R/schedules/**`, `R/knowledge/**` (incl. `model_policy.json`), `R/tools/**`
  (the live `R/tools/gtm/` subtree is already a trust root in every session) — except, in an
  **interactive** run only, `R/projects/*/memory/` (the transcript clause above keeps the rest of
  `R/projects/`). Non-GTM sessions are unaffected (runtime development stays possible there).
- `marketing-path-via-patch-only` (plan §6.5/§6.6; 02_act.md `website_static` executor, where the
  main session "writes nothing of its own"): target, relative to its GTM home, matches one of that
  home's committed pack `marketing_paths` globs (casefolded, against the canon'd target) — in
  **every** GTM run, interactive included. Marketing source files change only through `git apply
  --index` of the reviewed `ST/patches/<action_id>.patch`, never by a tool edit; so neither a broad
  glob such as `marketing/website/**` nor a GTM session can reach `marketing/website/build.mjs` (the
  AI-provenance publish gate, `checks.MARKETING_PATH_NEVER`, 00_global_paths.md) or any other code
  file under a marketing glob.
- `gtm-write-outside-drafts` (plan §20.9c "not allowed to … start changing features"; 07's R17 —
  07 §7.6 step 5 installs no scheduled prompt until this lands): every other target is denied
  unless it is (1) under the session company's `<H>/.claude/gtm/drafts/` (for a seat-only scope
  `"*"`, under any GTM home's drafts), (2) under a system temp root (`/tmp`, `/private/tmp`,
  `/private/var/folders`, `$TMPDIR` — outside every repo and every import path; stated deviation
  from R17's drafts-only wording, so scratch files stay possible), or (3) in an **interactive** run
  only, equal to or under an `H / paths.<key>` entry of the session company that is neither
  machine-written (above) nor matched by `marketing_paths` — the feature inventories, shims,
  READMEs, snapshot `.md` files and `plans_dir` that pack declares — or under
  `R/projects/*/memory/`. **Interactive run** = `CLAUDE_GTM_RUN` matches `CYCLE_ID_RE` with `slug ==
  CLAUDE_GTM_COMPANY` and `kind == "interactive"`; anything else (a scheduled kind, absent,
  unparsable, other company, or a seat-only scope with no company) is scheduled (fail closed;
  `CLAUDE_GTM_RUN` only tightens, 00_global_paths.md §1.4). The committed pack loading None, or the
  `H` resolution failing, denies `gate-fault` for every target not admitted by (1)–(2) (fail
  closed). **Blast radius:** a GTM session writes only drafts, temp files and (interactive)
  pack-declared editable paths and memory; application code, marketing source, dossiers, hooks,
  agents and settings are edited from a non-GTM session, where act.py (02_act.md check 9,
  `complete --commit`) and review remain the controls.
G-B rule c's GTM-scope arm calls the same `gtm_hooklib.gtm_session_write_verdict()` these clauses
are built from (§4), so shell writes never reach further than tool writes (parity test).
P2 tests (B1), each falsified by removing its clause: a GTM-session Edit of `company.json` and a
GTM-seat Write to `R/projects/<p>/<s>/subagents/agent-x.jsonl` are denied; the same edits from a
non-GTM, non-seat session are allowed; an interactive GTM-session Write to `R/projects/<p>/memory/x.md`
is allowed and a scheduled one is denied; a GTM-session Edit of `R/hooks/gtm_browser_gate.py`, of
`R/settings.json` and of `R/agents/gtm-operator.md` is denied `runtime-write-in-gtm-session`, and the
same Edit of `R/hooks/gtm_browser_gate.py` from a non-GTM session is allowed; an **interactive**
GTM-session Edit of a file under `marketing_paths` (e.g. `marketing/website/index.html`) and of
`marketing/website/build.mjs` are denied `marketing-path-via-patch-only`; a scheduled-session Edit of
a CSA `modules/**` file is denied `gtm-write-outside-drafts`, a scheduled-session Write under
`<H>/.claude/gtm/drafts/` is allowed, and an interactive session's Edit of a feature-inventory file
under `H / paths.feature_inventory_dir` is allowed while a scheduled session's is denied; a
GTM-session Write to `/tmp/x.txt` is allowed; the same `modules/**` edit from a non-GTM session is
allowed; a GTM-session Edit of `<H>/<activity_log_dir>/TOOL_TRAIL.jsonl.ids`, of
`TOOL_TRAIL.jsonl.ids.ab12.tmp` and of `ACTIVITY_LOG.md` is denied `machine-written-path` (in any
session); a GTM-session Write under `R/tools/gtm/setup_scripts/` is denied `trust-root`.
`company.json`'s `budget.*` caps are editable (from a non-GTM session) but not trusted: gate-gtm
enforces the signed cap (§4.6 step 3), so editing them cannot raise an enforced cap. Scope: all
sessions (GTM-scope clauses as marked). **Emit test (00_global_paths.md §0.4):** `machine-written-path`
and `trust-root` deny unconditionally in every session, and every GTM-scope clause denies
unconditionally (it only fires in GTM scope) — i.e. every G-W deny is emitted whether or not
`_lib.enforcing(where)` holds. B1 test (00 §0.4 (c)): in a tmp `HOME` with no enforce markers, a
non-GTM `Write` of a file under `S` is denied `machine-written-path` (RED when the emit test is
`_lib.enforcing` alone). Fails closed on a path match, on any trust-root verification error,
(GTM scope) on the fail-closed cases above, and on `machine_written()` raising `SiblingPackUnreadable`
per its own DECIDED (wave1d) fallback above (§4 `machine_written`: deny in GTM scope, deny outside
GTM scope only for a target under `S` or a registered GTM home, else allow); otherwise open (allow +
`gate-fault` log) on internal error. B1 test: with one GTM home's pack uncommitted, a **non-GTM**
session's Edit of an unrelated file outside every registered GTM home is allowed, and a non-GTM
session's Edit under `S` (or under the uncommitted home itself) is denied `gate-fault`; the same
uncommitted-pack state denies **every** Edit from a **GTM** session, including one targeting a file
outside every home (RED when the GTM-scope arm is removed).

### 4.4 Path gate `hooks/gtm_phi_path_gate.py` (WP-B1) — PreToolUse `Read|Grep|Glob|Edit|MultiEdit|Write|NotebookEdit|WebFetch`

Scope: **GTM scope** = `CLAUDE_GTM_COMPANY` set **or** `payload.agent_type ∈ GTM_SEATS`
(`gtm_hooklib.gtm_scope`; plan §20.3's two arms) for rules 1b–5; rule 1 (`agency-boundary`) uses
**Agency scope** (`gtm_hooklib.agency_scope(environ, payload, payload cwd)`: GTM scope, or
`payload.agent_type ∈ DEPARTMENT_SEATS` with the payload cwd not under either Agency root —
00_global_paths.md §0.4, DECIDED there and binding here; plan §20.9a binds "every phase and every
agent", and plan §7.4 lets `/gtm` missions run from ordinary sessions). Outside GTM scope, a
department seat is judged by rule 1 only. The shell fast path (§4.8 item 5) exits early only
when the env arm, the GTM-seat arm and the department-seat arm are all absent. **DECIDED HERE (revised):** the agent_type arm is kept even though
gate-gtm denies GTM seats outside a GTM session (§4.6 step 0), because gate-gtm fails open on any
fault and Workflow-spawned legs were never probed (§17 i; §4.10 now denies GTM seats in `Workflow`
scripts, but that gate fails open outside GTM scope) — the three PHI gates (G-A rule 3, G-B
rule j, this gate) now share one scope. Whether Read/Grep/Glob payloads from a subagent carry
`agent_type` is UNVERIFIED (probe q, §4.2); the same fallback applies. Target root (canon'd, §4):
`file_path`/`notebook_path`; Grep `path` (default cwd); Glob `path` (default cwd; an absolute
`pattern` prefix is also a root); WebFetch `url`. Rules, first match wins:

1. `agency-boundary`: the root's `canon` is `gtm_env.VOLFS_SENTINEL` (any `/.vol` spelling, 00_global_paths.md §0.1 arm (e);
   checked first, wave1e, R44), or is equal to or under `agency_root()` (either Agency root, §4), or (Grep/Glob) an
   **ancestor** of it (a search rooted at `~/Desktop` or `~` would recurse into Agency); or a WebFetch
   URL for which `is_agency_github_url` holds (§4 — the same helper as G-A rule 3b and G-B rule i:
   github.com and subdomains, codeload.github.com, raw.githubusercontent.com, api.github.com
   `/repos/<org>/agency…`).
1b. `phi-denylist-unreadable` (00_global_paths.md §1.2 "`phi_denylist.json` missing or
   unparseable", DECIDED there; it supersedes 03_schemas.md §3.20's former "fail closed under
   OtherCompany Files only" rule, `requests/04_hooks.md` R51): `gtm_hooklib.phi_denylist()` is
   `PHI_UNREADABLE` (§4 — never None or an empty list while a hipaa pack is registered) and the tool
   is Read, Grep or Glob whose root is not equal to or under a root of
   `gtm_hooklib.phi_unreadable_roots(company, payload)` (the session company's `H`, `R`, the temp
   roots), or the tool is WebFetch (every URL counts as a PHI hit, as for G-A rule 3).
2. `phi-host` (WebFetch): `gtm_hooklib.phi_url_hit(url, company)` returns a label — a
   `phi_denylist` host or host suffix whose `applies_to` is absent or contains `gtm_scope()`'s
   company (`"*"` → every entry), **or any `url_prefixes` entry** (same host; path equal to the
   prefix's or continuing it at a `/` boundary; never filtered by company; 03_schemas.md §3.20) —
   the one predicate G-A rule 3 and G-B rule j use, so plan §20.3's ban on OtherCompany's Open Dental
   server hosts, its eServices / web-sched tenant (a tenant page on a shared vendor host is
   banned by URL prefix only) and the Agency app hosts reaches the director's and specialists'
   WebFetch too (plan §2), and the three PHI gates really share one scope.
3. `phi-path`: the root is a `phi_denylist` path, inside one, or (Grep/Glob) an ancestor of one.
4. `phi-path` (OtherCompany allowlist, 03_schemas.md §3.20): the root is under `phi1_root()` (the root
   itself counts as under) and not equal to or inside an allowlisted folder (default-deny while
   `othercompany_read_allowlist.json` is absent); or (Grep/Glob) an ancestor of `phi1_root()`.
5. `phi-scope-outside-allowed` (00_global_paths.md §1.2 "OtherCompany read scope", DECIDED there;
   plan §20.3 "any export, report or file derived from it" — enumeration can miss a folder nobody
   named): `gtm_hooklib.hipaa_scope(company)` holds (a pack that does not load counts), the tool is
   Read, Grep or Glob, and the root is not equal to or under a root of
   `gtm_hooklib.phi_allowed_roots(company, payload)` — the session company's `H`, an allowlisted
   OtherCompany folder, `R`, the temp roots (`tempfile.gettempdir()` realpath, `/private/tmp`, the
   payload's `scratchpad_dir`). A Grep/Glob rooted at an **ancestor** of an allowed root is not
   "under" it and is denied. Denylist `path` entries still win inside allowed folders (rule 3 runs
   first). Unconditional in GTM scope (00 §0.4).

Fails closed on a match (rules 1b–5 need no further read). **Fail mode on an internal
exception** (a raising `realpath`/`canon`, a malformed payload, a `phi_denylist()` or
`phi1_allowlist()` parse error, any other bug), in GTM scope: deny `gate-fault` when the root — by
text alone, `norm(abspath(join(cwd, expanduser(root))))` (expand first, §4 `canon` order) with no filesystem call — is equal to, under, or an
ancestor of `phi1_root()` or `agency_root()`, or — under `hipaa_scope` — is not equal to or under a
root of `phi_allowed_roots` (text only), and for every WebFetch; otherwise allow + log
`gate-fault` (plan §20.3 wants these checks closed where PHI or Agency can be reached; everything
else in a GTM session stays usable); for a department seat outside GTM scope the same text test
applies to `agency_root()` only. Outside GTM and Agency scope the gate is not reached (§4.8 item 5),
and a payload that reaches it but is in neither scope is allowed with no log. P2
tests: Read, Grep and Glob of an Agency path from a GTM session → deny; a `marketing-director`
(`agent_type`) Read of `~/Desktop/OtherApp/x` from a **non-GTM** session with cwd the CSA root → deny
`agency-boundary`, and with cwd inside the (tmp) Agency root → allow; the same director's Read of a
`phi_denylist` path from a non-GTM session → allow (PHI stays on GTM scope) (each RED when rule 1
uses `gtm_scope`, and the first also RED when the §4.8 item 5 department-seat globs are removed); `~/Desktop/AGENCY/x` (mixed
case) → deny; Grep rooted at `~/Desktop` from a GTM session → deny; a GTM-seat (`agent_type:
"gtm-analyst"`) Read of a denylisted path from a **non-GTM** session → deny; a non-GTM, non-seat Read
of an Agency path → allow (no new denial for Agency's own sessions); OtherCompany file outside the
allowlist → deny, inside → allow, allowlist absent → deny; a GTM-session WebFetch of a denylisted
host → deny `phi-host`, and the same fetch from a non-GTM, non-seat session → allow; a GTM-session
WebFetch of `https://api.github.com/repos/org/Agency/contents` → deny; with `phi_denylist()` made
to raise a bug exception, a GTM-session Grep rooted at `~/Desktop` → deny `gate-fault` while a
Read of `/tmp/x` → allow (falsified by allow-on-exception). **URL prefixes, read scope and the
unreadable file (B1; each RED when its rule is removed):** with a `url_prefixes` entry
`https://x.example/r/abc`, a OtherCompanyB GTM-session WebFetch of `https://x.example/r/abc/page2` →
deny `phi-host`, of `https://x.example/r/abcd` → allow (RED when rule 2 checks hosts only); a
**OtherCompany** GTM-session Read of `<tmp HOME>/Documents/x.pdf` (in no listing) → deny
`phi-scope-outside-allowed`, while a **OtherCompanyB** GTM-session Read of it → allow, a OtherCompany Read
of a file in `H`, of `R/tools/gtm/README.md` and of `/tmp/x` → allow, and a OtherCompany Grep rooted at
`~` → deny (RED when rule 5 is removed or ignores `hipaa_scope`); with `phi_denylist.json` deleted
while the OtherCompany pack is registered, a OtherCompany **and** a OtherCompanyB GTM-session Read of a
formerly denylisted Desktop path → deny `phi-denylist-unreadable`, a Read of a file in `H` → allow,
and any WebFetch → deny (RED when `phi_denylist()` returns an empty denylist, or None treated as
empty, on the missing-file branch); with no hipaa pack and no `otherapp` registered, the same
deletion leaves a OtherCompanyB Read of `~/Desktop/x` judged by rules 3–4 only (absent → empty). **Emit test (00_global_paths.md §0.4):** the path
gate is reached only in GTM or Agency scope (§4.8 item 5), so every deny it makes is unconditional (emitted
whether or not `_lib.enforcing(where)` holds); B1 test (00 §0.4 (a)): with no enforce markers in the
tmp `HOME`, a GTM-scope `Grep` of a `phi_denylist` path is denied (RED when the emit test is
`_lib.enforcing` alone). **No-Agency-touch oracle consumers (00_global_paths.md §0.1):** the
oracle's consumer list includes this gate (Read/Grep/Glob/Write rooted at, under and above
`~/Desktop/OtherApp`, and at a symlink into it), G-W (an Edit of an Agency file from a **non-GTM**
session — the case Agency's own development sessions hit — and from a GTM session), G-B rules c
(an `rm`, a redirect and a `cp -R ~/Desktop /tmp/y` walk), i and j, d1, and G-A rule 3b (a
`file://` URL under Agency); each case runs inside the oracle with nothing recorded, and each goes
RED when `canon`'s Agency short-circuit (§4) or the walk's Agency skip is removed.

### 4.5 Ticket release `hooks/gtm_ticket_release.py` (WP-B1) — SubagentStop

Reads `agent_id`, `agent_type`, `session_id`. Behavior per 03_schemas.md §3.6 Release (write/batch → `stopped`,
read/setup → `closed`). **Result record (FID-08; the one definition is 08_seats_wps.md §8.1 "Attestation", copied here).**
It also appends `{"ts", "session_id", "agent_id", "agent_type", "result_sha256"}` to
`S/agent_results.jsonl` under `S/agent_results.lock` (5 s; timeout → log `gate-fault`, write
nothing), where `result_sha256 = gtm_result.result_sha256(gtm_result.parse_block(
last_assistant_message))` — the parsed block's canonical hash (`"sha256:" + sha256(canon(block))`),
**not** a hash of the raw message — or `null` when `parse_block` returns `None`. **When:** on every
SubagentStop whose `last_assistant_message` contains an opening-fence line (a line exactly
```` ```gtm-result ````, 08_seats_wps.md §8.1 grammar), in **any** session, GTM or not; a stop
without one writes no row. The ticket-release half still acts only on GTM tickets. The hook imports
`tools/gtm/gtm_result.py` (standalone, 08_seats_wps.md Appendix B #9; never `gtmlib`) lazily inside
its `try`, through §4's hook import rule (`gtm_import.load("gtm_result", __file__)`): an import failure logs `gate-fault` and writes no row, so every consumer then refuses
`agent_result_unrecorded` (fail closed). The file is hook-written and agent-unwritable (G-W and G-B
rule c protect `S`); `gtm_result.extract_gtm_result` checks the transcript's final block against the
last row for that `agent_id` (02_act.md §2.7(c), 08_seats_wps.md §8.1), so an appended forged
`gtm-result` no longer counts. Never denies/blocks (prints nothing), never raises; logs
`ticket-released` and `result-recorded` rows. **Registration:** not behind a `CLAUDE_GTM_COMPANY`
gate — the §4.8 item 6 shell fast path skips only a payload that is outside a GTM session **and**
does not contain the text `gtm-result`, so reviews run in non-GTM sessions (trust-architect, WP-M)
are attested. B1 tests, against the shared fixture `tools/gtm/tests/fixtures/attestation/`
(08_seats_wps.md §8.1, Appendix C item 28): the hook fed `subagent_stop.json` with
`CLAUDE_GTM_COMPANY` unset writes exactly `expected_row.json` plus `ts` (falsified by hashing the raw
message, or by gating on `CLAUDE_GTM_COMPANY`); a payload whose message has no opening-fence line
writes no row; a lock timeout writes nothing and raises nothing.

### 4.6 gate-gtm `hooks/gtm_task_gate.py` (WP-B2; **DECIDED HERE:** new module, since the plan names the
gate but no file) — called by `pretooluse_task.py` as **T1b** (after T1 allows, before T2)

```python
# hooks/gtm_task_gate.py (WP-B2)
HOOK_NAME = "gtm_task_gate"
def parse_gtm_tag(prompt: str) -> dict | None          # first line only, system_names.TAG_RE -> {"company", "run_id", "run_kind"}
def run_kind(company: str, run_id: str) -> str | None   # CYCLE_ID_RE (00_global_paths.md §0.3) match with slug == company -> kind (incl. "interactive"); gtm_… -> "mission"; else None
def decide(ev: dict, environ: Mapping[str, str], *, budget: dict | None) -> tuple[bool, str, dict]   # the ONE signature (F-t1b below);
                                                        #   budget = the parsed isolated `ai_budget.py state` JSON, or None when apply_t1b did not obtain one
def message_for(reason: str, detail: dict) -> str

# tools/gtm/ai_budget.py (WP-B2; standalone; the ONE implementation — I5)
TAG_RE = system_names.TAG_RE   # r"^\[gtm company=(?P<company>[a-z][a-z0-9-]{1,31}) run=(?P<run>(?:cyc|gtm)_[A-Za-z0-9_-]{1,120})\]\s*$"
                               #   the company group is exactly company.SLUG_RE's grammar (00_global_paths.md §0.3; `requests/04_hooks.md`
                               #   R56 asks 03 §3.22 to align its TAG_RE); step 1 still re-checks the slug against gtm_slugs()
def effective_ai_caps(company: str, now: datetime) -> dict
    # {"opus": {"usd": "40.00"|"0.00"|None, "source": "signed:<request_id>"|"company_json"|"report_only"|"forged", "forged": bool}, "sonnet": {...}}
    # exactly these two keys and three fields per bucket; a forged bucket (below) is {"usd": None, "source": "forged", "forged": True} (IMP-19);
    # a signed "0.00" is a ZERO CAP {"usd": "0.00", "source": "signed:<id>", "forged": False}; the signed REPORT-ONLY form
    # (unit "report_only", new_absolute_value null; requests/07_notices_schedules.md R34) is {"usd": None, "source": "signed:<id>", "forged": False}
    # company_json caps come from the COMMITTED pack: `gtm_env.git_show_head(H, ".claude/gtm/company.json")` (§4 hardened read; FID-07; the same
    # read as gtm_hooklib.load_pack_safe; `./` = relative to H)
@dataclass(frozen=True)
class AttributionCtx:                                   # F-attr: everything the §4.6 precedence reads, loaded ONCE per call site
    now: datetime; window_start: datetime
    tags_by_tool_use: dict[str, dict]                   # S/dispatch_tags.jsonl admission rows in the window, keyed by tool_use_id (minus released ones)
    agent_sessions: dict[str, dict]                     # S/transcript_index.json "agents" entries: agent_id -> {session_id, project_dir, cwd} (03_schemas.md §3.16)
    runs_by_session: dict[str, tuple[str, str]]         # session_id -> (company, run_id), from every GTM home's ST/cycles/*.json and mission records' session_id
    homes_by_slug: dict[str, tuple[str, str]]           # slug -> (project_dirs.project_dir_name(H), norm(realpath(H))) for company.gtm_slugs() (Agency never included, 00_global_paths.md §0.1; IMP-15)
    seats: tuple[set, set, set]                         # system_names.seat_sets()
def load_attribution_ctx(now: datetime, window_start: datetime) -> AttributionCtx   # reads the files above as plain files (never refreshes the index); tail-first where §4.6 says so
def attribute_row(row: dict, *, ctx: AttributionCtx) -> dict                   # pure (no I/O): {"company": slug|None, "run_id": str|None, "via": "tag|dispatch_tag|transcript_session|project_dir|unattributed"}
def week_to_date_usd(company: str, now: datetime) -> dict                      # {"opus": {"usd": float, "exactness": "exact|best_effort", "unpriced_rows": N}, "sonnet": {...}, "unattributed_gtm_usd": float, "notes": [str]}
    # exactness is "best_effort" whenever gtm_pricing.pricing_status()["ccdash"] != "pinned", and then notes contains "ccdash_unpinned"
    # (03_schemas.md §3.19; IMP-05); notes is [] otherwise
# --- dispatch admission: tools/gtm/dispatch_tags.py (WP-B2; stdlib + company + system_names + gtm_env ONLY — never approval_sig,
#     gtm_pricing or ai_budget, so a hook may import it in-process; ai_budget re-exports these three names unchanged for
#     every other caller; it is under the write-protected live R/tools/gtm/ subtree, §4.3, and joins TRUST_PATHS,
#     requests/04_hooks.md R24) ---
def count_dispatches(company: str, *, run_id: str | None = None, since: datetime | None = None, budget_admission: bool | None = None) -> int
    # counts only admission rows with seat_row: true (a GTM_SEATS or in-session DEPARTMENT_SEATS dispatch), minus released ones;
    # with run_id, `since` defaults to the run's open ts (the cycle record's / mission record's created ts), never None (never a whole-file read);
    # a missing or unparsable run record raises AdmissionInputUnreadable (below)
def admit_and_record(tag_row: dict, *, cap: int | None, budget_admission_limit: int | None) -> tuple[bool, str]   # count + append under S/dispatch_tags.lock (one critical section)
    # returns (True, "admitted") | (True, "duplicate") — a tool_use_id already admitted and not released: nothing appended, idempotent |
    #   (False, "dispatch-cap") | (False, "budget-admission-exhausted"); lock timeout (5 s) raises TimeoutError (a gate fault)
    # Inputs it reads, named (binding): the run's open ts from the cycle record `ST/cycles/<run_id>.json` or the mission record
    #   (03_schemas.md §3.12/§3.19), and company-local midnight from the COMMITTED pack's `timezone`, read with
    #   `gtm_env.git_show_head(H, ".claude/gtm/company.json")` (§4 hardened read; H via company's home lookup, as load_pack_safe) —
    #   NEVER company.load_pack, which reads the working tree (FID-07). A missing/unparsable run record, a pack that is not committed
    #   or does not parse, or an invalid `timezone` raises `dispatch_tags.AdmissionInputUnreadable(what)`, which apply_t1b treats
    #   exactly like the second lock timeout: deny `gate-fault` for an enforced dispatch (never the fail-open path, which would run the
    #   dispatch uncapped). B2 test: with the run's cycle record deleted, an enforced GTM-seat dispatch is denied `gate-fault` and no
    #   admission row is written (RED when the exception falls into apply_t1b's generic fail-open)
def release_admission(tool_use_id: str, reason: str) -> None   # appends {"ts","tool_use_id","released": true,"reason"} under S/dispatch_tags.lock (F-overcount)
# --- back in tools/gtm/ai_budget.py ---
def budget_state(company: str, now: datetime) -> dict
    # {"over": [bucket...], "forged": [bucket...], "pause_present": bool, "unattributed_gtm_usd": "<2dp str>",
    #  "buckets": {"opus": {"usd": "12.34", "cap": "40.00"|None, "source": <effective_ai_caps source>}, "sonnet": {...}}}
    # unattributed_gtm_usd = week_to_date_usd(...)["unattributed_gtm_usd"] from the SAME call, quantized like `usd` (runtime-wide:
    # the week's GTM-seat spend attributed to no company; the same value for every company's call)
    # computed from ONE effective_ai_caps + ONE week_to_date_usd call (one attribution load), so gate-gtm's PAUSE.budget reason and
    # budget notice need no second load. `usd` = the week-to-date float quantized to a 2-dp string (Decimal, ROUND_HALF_UP) —
    # present for every source, report_only and forged included; `cap` = the effective cap string ("0.00" for a zero cap), None for
    # report_only (unsigned or signed) and forged.
    # "over": a bucket whose cap is Decimal 0 (a signed "0.00" ZERO CAP — plan §20.13 "a pause is amount 0"; 03_schemas.md §3.7
    # "0.00" = pause/stop; requests/07_notices_schedules.md R32) is listed in "over" ALWAYS, from the first dispatch of the week
    # (usd "0.00" included), so only the plan §6.8 lead-capture allowance is admitted (step 3); any other cap is over when
    # Decimal(usd) > Decimal(cap); "over" never fires for cap None (report_only, unsigned or signed) or forged (listed in "forged");
    # a pack without `budget.weekly_usd_cap_<b>` (and no signed cap) reads as report_only, source "report_only" 
# __main__: python3 <T>/tools/gtm/ai_budget.py caps --company X | state --company X | usd --company X [--json]  -> one JSON object; exit 0 ok, 1 internal, 2 usage, 13 company
#   `--json` is ACCEPTED AND IGNORED on every subcommand (output is always JSON) — 05_approver.md §5.5 names the isolated subprocess as
#   `ai_budget.py <subcommand> --json`, and an argparse that rejected it would exit 2 and put every company in forged budget state
#   stdout (IMP-19), with now = the current UTC time (GTM_FAKE_NOW under GTM_TEST=1):
#   caps  -> exactly json.dumps(effective_ai_caps(X, now))   state -> exactly json.dumps(budget_state(X, now)) (incl. `buckets`)
#   usd   -> exactly json.dumps(week_to_date_usd(X, now)); no other keys, no wrapper object
#   caps --check (IMP-19 as amended by requests/07_notices_schedules.md R32/R34; the ONE unsigned-caps predicate for run_gtm_job.sh and
#     gtm_session.sh --scheduled, 07_notices_schedules.md §7.2/§7.6): prints exactly one JSON object
#     {"pass": bool, "reason": null|"unsigned"|"forged"|"malformed", "zero_cap": bool, "zero_cap_enforced": true, "report_only_signed": bool}
#     — pass = both buckets have `source` starting "signed:" AND `forged` false (a signed zero cap and a signed report-only bucket both
#     pass); reason = "forged" when any bucket is forged, else "unsigned" when any bucket is company_json/report_only (unsigned), else
#     "malformed" for a missing bucket or key, else null; zero_cap = some bucket is a signed "0.00"; zero_cap_enforced is the constant
#     `true` in every version that implements the zero-cap reading (07 refuses a scheduled start under a signed zero cap unless it is
#     `true` — ship-ordering, fail closed); report_only_signed = some bucket is the signed report-only form. Exit 0 iff pass, 77
#     otherwise, 1 internal, 13 company
```
**Module dependencies (IMP-15).** `ai_budget` is stdlib + `company`, `system_names`, `gtm_env`,
`approval_sig`, `gtm_pricing` and **`project_dirs`** — a new stdlib-only module
`tools/gtm/project_dirs.py` (coordinator follow-up, 08_seats_wps.md Appendix C item 14) holding
`project_dir_name(home: Path) -> str` (today's `harvest_tool_trail._project_dir_name`),
`project_dir_name_text(path_str: str) -> str` and `matches_project_dir_prefix(dir_name: str,
prefix: str) -> bool` (today's separator-bounded `_matches_project_dir_prefix`);
`harvest_tool_trail` re-exports them under its existing names. `ai_budget` never imports
`harvest_tool_trail`, which loads `activity_log` at import time. B2 tests: `ai_budget.py caps` output
parses to exactly two buckets with exactly `usd`/`source`/`forged` (falsified by adding a wrapper
key); with the ccdash file unpinned, `usd` prints both buckets `best_effort` and `notes:
["ccdash_unpinned"]`; a forged bucket prints `"source": "forged"`; `state` and `usd` print the function results
unchanged; `state` for a fixture over its opus cap prints `buckets.opus` with `usd` "41.00", `cap` "40.00" and the
signed source, and a report-only bucket prints `cap: null` (falsified by dropping `buckets`); `caps --check` prints
exactly the five `requests/07_notices_schedules.md` R32 keys, exits 0 with `reason: null` for both buckets `signed:*`/`forged: false`, and 77 with `reason`
`unsigned` for a `company_json` and an unsigned `report_only` bucket and `forged` for a forged bucket; a signed `"0.00"` opus
bucket prints `zero_cap: true, zero_cap_enforced: true` and exits 0; a signed report-only bucket prints
`report_only_signed: true` and exits 0 (each falsified by removing its clause). **05's exact command line:** B2 runs
`<TRUSTED_PYTHON> -I -S -B -X pycache_prefix=<tmp> <T>/tools/gtm/ai_budget.py state --company X --json` and parses the same
object `state` prints without `--json` (RED when `--json` exits 2).
Every function resolves `R` at call time via `company.claude_dir()` (never `_lib.AGENT_BUDGET_DIR`
captured at import) and reads `R/.agent_budget/{claims,stops,spend}.jsonl`, `S/dispatch_tags.jsonl`,
`S/transcript_index.json` (as a file; never refreshed from a hook), `ST/cycles/*.json`, mission
records, `ST/session_spend.jsonl`, `S/approvals/<company>/`, `S/approval_requests/<company>/`,
`S/approval_nonces.jsonl`. `ai_budget.py` joins `TRUST_PATHS` (05_approver.md §5.5) and `review_risk_tier.py`'s
HIGH-tier keywords (§4.9). Callers: gate-gtm (step 3, only through the isolated `ai_budget.py state` subprocess; step 4 uses
`dispatch_tags`), `act.py resume --name PAUSE.budget`
(02_act.md §2.4), `run_gtm_job.sh` (07_notices_schedules.md §7.2 unsigned-caps check), `perf_report` and `validate_run` (attribution).
**Every caller attributes the same way (F-attr):** build one `ctx = load_attribution_ctx(now,
window_start)` per invocation and pass it to every `attribute_row` call — `perf_report`/
`validate_run` with the report window's start; gate-gtm does not build its own: its one load per
`decide` is the one `week_to_date_usd` builds (window start = Monday 00:00 company-local). No caller reads the attribution sources itself, so latency is
bounded by one load per call (the §4.6 p95 budget covers it). **Trust root on the budget path
(F-trust):** `effective_ai_caps` and `budget_state` call `approval_sig.trust_root_ok(R)` first,
unconditionally (it returns `(ok, entries)`, 05_approver.md §5.5; its `require_key` argument is
accepted and ignored, `requests/05_approver.md` R39, so no call site passes it); `ok` False marks
**every** bucket `forged` (budget state + `PAUSE.budget` + trust notice, step 3) — so an uncommitted edit to `gtm_pricing.py` (e.g. `price_usd` returning 0), to
`telemetry/pricing.json` or to `ai_budget.py` itself (all TRUST_PATHS, 05_approver.md §5.5) cannot
silently disable the AI-spend cap — **provided the check runs before any edited module's code
runs.** A module-level body executes at import, so an in-process `import ai_budget` (which imports
`company`, `system_names`, `gtm_pricing`, `project_dirs` first) would let an edited module replace
`approval_sig.trust_root_ok` with `lambda *a, **k: (True, [])` before `effective_ai_caps` ever
calls it. Therefore (binding, with 05_approver.md §5.5 step 0 "a hook never imports `approval_sig`
or `ai_budget` in-process" and `requests/05_approver.md` R14): gate-gtm (1) runs the trust check
**first and alone**, as `_TRUSTED_PYTHON -I -S -B -X pycache_prefix=<fresh P>
<_trust_root()>/tools/gtm/approval_sig.py --trust-result` (05 §5.5; `approval_sig` imports only
`gtm_env`, and both are in the preventive, write-protected set, §4.3), (2) on a failed, timed-out,
non-zero or unparsable result — or any exception while obtaining or interpreting it — takes the
**trust-failure path** of "T1b wiring" below (forged state: every enforced dispatch is denied
`gtm-budget` except the plan §6.8 lead-capture allowance, decided with stdlib code only; no
`ai_budget` process is started and **no `tools/gtm` module is imported**), and (3) only on success
runs `… <_trust_root()>/tools/gtm/ai_budget.py state --company <CLAUDE_GTM_COMPANY> --json`
(05_approver.md §5.5's form; `--json` is accepted and ignored) in the same isolated form and parses
its JSON (which re-runs the trust check itself). **Hooks-local definitions in `pretooluse_task.py`
(binding; stdlib only, so the trust check and the trust-failure path need no `tools/gtm` import;
each has a P2 parity test against the `tools/gtm` original over 00_global_paths.md §1.1's unit
cases, RED when the copy drifts):**
- `_TRUSTED_PYTHON = "/opt/homebrew/opt/python@3.13/bin/python3.13"` — equal to
  `gtm_env.TRUSTED_PYTHON`;
- `_real_home() = pwd.getpwuid(os.getuid()).pw_dir`, `_real_root() = Path(_real_home()) /
  ".claude"` — equal to `gtm_env.real_home()`/`real_root()` (never `HOME`, never `CLAUDE_DIR`);
- `_gtm_tmp_root()` — the literal body of `gtm_env.gtm_tmp_root()` (00_global_paths.md §1.1;
  05_approver.md §5.5 step 0's `_gtm_tmp_root()`), under which gate-gtm creates each `<fresh P>`
  directly (§4 "Isolated subprocesses"; DECIDED (wave1e));
- `_norm_text(s)` = `_canon_aliases(os.path.normpath(s).casefold())`, where `_canon_aliases` is
  the full 00_global_paths.md §0.1 loop — leading-`/` collapse, `/.nofollow` strip,
  `/.resolve/<digits>` strip, `/system/volumes/data` firmlink strip, repeated until a pass changes
  nothing, plus the terminal `/.vol` arm returning the literal `_VOLFS_SENTINEL` (= 
  `gtm_env.VOLFS_SENTINEL`) — and `_same_root(a, b)` = `os.path.samefile(a, b)` when both exist,
  else `_norm_text(a) == _norm_text(b)` — equal to `gtm_env.norm_text`/`same_root` (corrected
  (wave1e): the former copy stripped only the firmlink, so the P2 parity test over 00 §0.1's
  alias unit cases would have failed; `_test_mode` treats a `HOME` whose `_norm_text` is
  `_VOLFS_SENTINEL` as under the real Agency root, i.e. test mode);
- `_test_mode(environ) -> tuple[bool, list[str]]` — exactly `gtm_env.test_mode`'s predicate
  (00_global_paths.md §1.1): True with reasons, in the order `CLAUDE_DIR`, `GTM_TEST`,
  `GTM_FAKE_NOW`, `HOME`, when `CLAUDE_DIR`, `GTM_TEST` or `GTM_FAKE_NOW` is non-empty, or `h =
  environ.get("HOME") or _real_home()` is under the real Agency root by `_norm_text` alone or is
  not `_same_root(h, _real_home())`; an empty value counts as unset;
- `_claude_dir(environ) -> Path` — exactly `company.claude_dir()` (00_global_paths.md §1.1),
  **including both branches' text-only Agency refusals** (the `CLAUDE_DIR` branch before its
  `.resolve()`; the `HOME` branch on the candidate `HOME + "/.claude"` against
  `_real_home() + "/Desktop/OtherApp"` only, DECIDED (wave1e)): `Path(v).expanduser().resolve()` when
  `CLAUDE_DIR` = `v` is non-empty, else `Path.home() / ".claude"`; a refusal raises, and gate-gtm
  treats that raise as a failed trust check (the trust-failure path; fail closed);
- `_trust_root(environ) -> Path` = `_real_root()` when `_test_mode(environ)[0]` is False, else
  `_claude_dir(environ).resolve()` — 05_approver.md's `T` ("Names used here"), so a
  `CLAUDE_DIR`-redirected tree is never the trust root outside test mode;
- `_GTM_SEAT_NAMES` (the `GTM_SEATS` and `DEPARTMENT_SEATS` halves kept apart), `_SLUG_RE` (=
  `company.SLUG_RE`), `_CYCLE_ID_RE` (= 00_global_paths.md §0.3 `CYCLE_ID_RE`) and `_TAG_RE` (=
  `system_names.TAG_RE`).
The in-process `tools/gtm` imports a hook makes for gate-gtm — `dispatch_tags` (above) and
`gtm_hooklib`'s `company`/`system_names`/`gtm_env` — happen only **after** step (1) succeeded,
through §4's hook import rule (`hooks/gtm_import.py`: the unresolved code root, a meta-path finder
serving only `GTM_HOOK_MODULES`, `sys.path` untouched, `sys.dont_write_bytecode = True`,
`sys.pycache_prefix = NO_PYCACHE`, never `R/tools/gtm`, never `S/pycache`). B2
test (RED when the trust check is moved after an in-process import): an uncommitted
`tools/gtm/gtm_pricing.py` whose module body sets `approval_sig.trust_root_ok = lambda *a, **k:
(True, [])` still puts the company in forged budget state and denies `gtm-budget`; an uncommitted
`tools/gtm/company.py` with the same body is never imported when the trust check fails (the
no-import assertion uses a module-import recorder on the tmp tree). **Inputs outside TRUST_PATHS (IMP-05):** the git-ignored
`usage-dashboard/ccdash/pricing.py` is used only when its bytes hash to `gtm_pricing`'s pinned
`CCDASH_PRICING_SHA256`, else prices come from `telemetry/pricing.json` alone (05_approver.md §5.5,
03_schemas.md §3.19); and `knowledge/model_policy.json` can only add seats to enforcement, never
remove one (`seat_sets()` union, §4). B2 falsification tests: an uncommitted edit to
`tools/gtm/gtm_pricing.py` puts the company in budget state; so does one to `telemetry/pricing.json`,
and one to `tools/gtm/project_dirs.py` that makes `matches_project_dir_prefix` return False (IMP-15;
05_approver.md §5.5);
an edit to the tmp tree's `usage-dashboard/ccdash/pricing.py` that makes `compute_cost_usd` return
0 leaves `week_to_date_usd` unchanged (the unpinned file is not loaded; falsified by dropping the
hash check); removing `gtm-analyst` from the fixture `model_policy.json`'s `gtm_seats` still counts
its spend rows and still denies it outside a GTM session (step 0; falsified by returning the policy
list alone).

Inputs to `decide`: `tool_input.subagent_type`, `tool_input.prompt`, `tool_use_id`, `session_id`;
env; packs; tickets; pause files; the `budget` state `apply_t1b` passes in (from the isolated
`ai_budget.py state` subprocess, F-trust); `dispatch_tags` reads for the caps.

**Company attribution precedence (`attribute_row`; plan §7.4 "Company $ attribution"; F1).** Only
GTM-seat rows count (`ctx.seats`' `GTM_SEATS`, plus `DEPARTMENT_SEATS` rows that attribute to a GTM
run). For a spend row, first match wins (each step reads only `ctx`):
1. **tag** — the row's `gtm` field (claim copy or transcript tag, 03_schemas.md §3.13);
2. **dispatch tag** — a `S/dispatch_tags.jsonl` row with the same non-null `tool_use_id`;
3. **transcript session** — `agent_id` → `S/transcript_index.json` `agents[agent_id].session_id`
   (covers `subagents/workflows/wf_*/` legs) → the cycle record (`ST/cycles/*.json`, any GTM home)
   or mission record whose `session_id` equals it → that record's company and run id;
4. **project dir** — only for rows whose `agent_type ∈ GTM_SEATS` (which can only run in GTM
   sessions, step 0): the GTM home H for which the agent's index entry satisfies **both**
   `project_dirs.matches_project_dir_prefix(entry.project_dir, project_dir_name(H))` (exact, or
   followed by `-` — covers worktree and subfolder project dirs, IMP-15) **and** `norm(realpath(entry.cwd))`
   equal to or under `norm(realpath(H))` (separator-bounded, 00_global_paths.md §0.1 `norm`; both
   sides resolved, as `project_dir_name(H)` and `harvest_tool_trail._transcript_cwd_is_under_home`'s
   `Path.resolve().is_relative_to` do, so a home registered through a symlink or `/var` vs
   `/private/var` matches; GTM homes may be stat'd, 00 §0.1, and `homes_by_slug` stores the resolved
   `norm(realpath(H))`; an `entry.cwd` equal to or under Agency by text is never resolved and never
   matches; B2 test: a home registered as a symlink path attributes a GTM-seat row whose `cwd` is the
   resolved path, RED with text-only comparison; the name match
   alone is lossy and would admit a same-prefix sibling folder, as `harvest_tool_trail`'s own
   per-transcript cwd check already decides). More than one H (nested homes) → the longest `norm(H)`;
   an entry without `cwd` → no match — **deliberately stricter** than `harvest_tool_trail`'s
   `_transcript_cwd_is_under_home`, which keeps a transcript with no cwd: the harvester only records
   calls, while this step charges money to a company, so an unprovable home is `unattributed`
   (Agency project dirs are never consulted, 00_global_paths.md §0.1);
5. else `unattributed` — never charged to a guessed company. gate-gtm writes a `budget` notice
   (severity `warn`, dedupe key `unattributed:<ISO week>`, runtime-wide slug `runtime`) when the
   week's `unattributed_gtm_usd` > 0: `decide` returns `detail["unattributed_usd"]` (from
   `budget_state(...)["unattributed_gtm_usd"]`, the same single load) for **every** enforced
   dispatch, and `apply_t1b` writes the notice on **both** allow and block when it is > 0 (its own
   `try`; a failure logs `gate-fault` and changes no decision; the dedupe key covers repeats).
   `perf_report` lists every such row. B2 test (RED when the write is removed): an enforced,
   admitted dispatch with a fixture week holding one unattributed GTM-seat row writes exactly one open
   `runtime` `budget` notice, and a second dispatch writes none.

A CSA-directory transcript whose session is a OtherCompanyB GTM session therefore attributes to
OtherCompanyB at step 3, never to CSA at step 4. **B2 fixtures (P2/P3; each with a falsification
twin):** (a) a `no-claim` GTM-seat row (`tool_use_id: null`, `session: null`, `gtm` from the
transcript tag) counts toward OtherCompanyB's weekly `$` cap — reverting 03_schemas.md §3.13's transcript-tag path
**and** precedence steps 2–4 makes the gate admit a dispatch it must deny; (b) a synthetic-claim
background dispatch with a `dispatch_tags.jsonl` row; (c) a workflow-path row
(`subagents/workflows/wf_x/agent-<id>.jsonl`) attributed via its session's cycle record; (d) a
CSA-dir row belonging to a OtherCompanyB session → OtherCompanyB; (e) a row matching nothing →
`unattributed`, not charged; (f) a GTM-seat row whose project dir is the OtherCompanyB home's worktree
dir (`<name(H)>--claude-worktrees-x`, `cwd` under H) → OtherCompanyB at step 4, while a same-prefix
sibling dir whose `cwd` is outside H → `unattributed` (IMP-15; falsified by exact-equality matching
and by dropping the `cwd` check respectively).

**Counting (`count_dispatches`, dispatch caps).** The authoritative dispatch record is
`S/dispatch_tags.jsonl` (03_schemas.md §3.13), written by gate-gtm at admission — so per-run caps never depend on
a pacer claim. It is append-ordered by admission `ts` and read **tail-first**, stopping at the first
row older than the window start. `admit_and_record` performs "count matching rows → compare with the
cap (and, under budget state, the lead-capture allowance) → append this dispatch's row" in **one
`S/dispatch_tags.lock` critical section** (5 s timeout = gate fault), so N dispatches issued in one
message are serialized and cannot all read the same count (I25). Rows dedupe by `tool_use_id`: a
second admission of an already-admitted, unreleased `tool_use_id` returns `(True, "duplicate")` and
appends nothing. **What counts (stated):** every admission row carries `seat_row` — `true` for a
`GTM_SEATS` dispatch or a `DEPARTMENT_SEATS` dispatch inside a GTM session, `false` for a tagged
non-GTM dispatch (e.g. `implement` inside a cycle). Only `seat_row: true` rows count toward
`dispatch_caps_per_run` and the lead-capture allowance, and only GTM-seat spend counts toward the
AI-spend cap (attribution precedence above); a tagged non-GTM dispatch is recorded (its row lets
`perf_report` attribute it) but neither counted nor charged. **Windows:** a per-run count uses
`since` = the run's open ts (cycle or mission record), a per-day count company-local midnight;
neither ever reads the whole file. **Rotation:** under the lock, when the first row appended in a
new UTC month is written, `dispatch_tags.jsonl` is renamed to `dispatch_tags.<YYYY-MM>.jsonl` first;
a reader whose window start precedes the current file's first row also reads the previous month's
file (only that one — runs and weeks never span more), and `act.py` retention (02_act.md) deletes
rotated files older than 90 days.
**Admissions that never run (F-overcount).** gate-gtm (T1b) appends the admission row **before**
T2 runs, so a T2 pacer deny would otherwise still consume a dispatch-cap slot or one of the 2 daily
lead-capture admissions. `pretooluse_task.py` (B2 wiring) therefore calls
`dispatch_tags.release_admission(tool_use_id, "t2_deny")` whenever T2 denies a dispatch for which
T1b **appended** a row in this call (`ev["_gtm"]["appended"]` is True — `admit_and_record` returned
`(True, "admitted")`; a `(True, "duplicate")` result appended nothing and sets `appended: False`, so
a T2 deny then never releases the ORIGINAL admission of that `tool_use_id`), and `count_dispatches`
ignores every admission row whose `tool_use_id` has a later `released` row. **Lock-timeout residual
(stated, with the I25 race):** a 5 s `dispatch_tags.lock` timeout is a gate fault; `apply_t1b`
retries `admit_and_record` once after 250 ms, and a second timeout is a gate-fault **deny**
(`gate-fault`) for an enforced GTM-seat dispatch in GTM scope (unconditional, 00 §0.4) — never an
allow with no admission row, so the dispatch caps are not bypassed under a parallel fan-out; outside
GTM scope (a department seat outside a session is not enforced) nothing is admitted anyway. B2 test:
with the lock held by another process for 6 s, an enforced GTM-seat dispatch is denied `gate-fault`
(RED with the fail-open allow). An Agent call that fails **after** PreToolUse allowed it is released by a new
**`PostToolUseFailure` hook on `Task|Agent`** (§4.8 item 7): `agent_budget.py release_failure`
(below "`release_failure` subcommand") calls `dispatch_tags.release_admission(tool_use_id,
"tool_error")` (lazy import inside a `try`; any failure logs `gate-fault` and exits 0). Whether
`PostToolUseFailure` fires for an Agent/Task call is UNVERIFIED (the runtime registers it only for
Bash today); if it never fires, the residual over-count is the accepted one — bounded by the per-run
cap, erring toward fewer dispatches, and the lead-capture allowance resets at company-local
midnight. B2 tests: a `PostToolUseFailure` payload for an admitted `tool_use_id` writes one
`released` row with reason `tool_error` and `count_dispatches` drops by one; a T2 deny after T1b admission leaves `count_dispatches` unchanged, and a
budget-state lead-capture admission denied by T2 does not consume one of the 2 slots; a second
dispatch with an already-admitted `tool_use_id` (`duplicate`) that T2 denies leaves the original
admission row unreleased (RED when the release ignores `appended`).

**`release_failure` subcommand (B2, `hooks/agent_budget.py`).** `agent_budget.main()` reads stdin
for `release_failure` **unconditionally** — not behind the pacer or spend-ledger toggles that gate
stdin for `gate`/`release_hook` — except that `agent_budget._disabled(environ)` (`CSA_DISABLE_HOOKS=1`,
read from the env mapping `main()` is given — the helper every other `agent_budget` subcommand
already uses, agent_budget.py L3124; never `_lib.disabled()`, which reads `os.environ` directly and
so would diverge from `main()`'s injected environ in tests) returns 0 before reading. `decide()` gains the branch `argv[0] == "release_failure"` → `{"action":
"release_failure", "tool_use_id": <payload tool_use_id or None>}`; `apply_decision` for that action
does, inside one `try`, the lazy `from dispatch_tags import release_admission` (under §4's hook
import rule: `gtm_import.load("dispatch_tags", __file__)` — the unresolved code root's finder, `sys.path` untouched, bytecode off, `pycache_prefix = NO_PYCACHE`) and `release_admission(tool_use_id, "tool_error")` when `tool_use_id` is a
non-empty string, logs `gate-fault` on any exception, prints nothing and returns 0 on every path.
B2 tests: with the pacer and spend ledger both off, a `release_failure` payload still writes the
`released` row (RED when stdin is read only under the toggles); a payload with no `tool_use_id`
writes nothing and returns 0.

**How `pretooluse_task.py` learns that T2 denied (IMP-06; B2 edits `hooks/agent_budget.py` and
`hooks/pretooluse_task.py`).** **Delivery (08_seats_wps.md §9 B2 row, Appendix B #173):** every B2
edit to these two live files — this `outcome` change, `apply_t1b` (F-t1b below), the T2-deny
release, `release_failure` (§4.8 item 7) and the 03_schemas.md §3.13 transcript-tag fallback (§4.9)
— is delivered as `tools/gtm/wave2_pending/b2_task_wiring.patch`, never saved into the live files
during Wave 2 (both run on every Task dispatch machine-wide); B2's tests, new and existing, run
against tmp copies with the patch applied, and the coordinator applies and deletes the patch in the
08_seats_wps.md Appendix C item 19 step, together with the G-B patch (§4.2). `hooks/gtm_task_gate.py`,
`tools/gtm/ai_budget.py` and `tools/gtm/dispatch_tags.py` are new files written live (nothing calls
them until the patch lands).
Today `apply_t2` returns `ab.apply_decision(...)`, which returns 0 on
every `gate` path and prints any deny straight to stdout, so the caller cannot tell. The change,
return values untouched:
- `agent_budget.apply_decision(decision, budget_dir, out, err, *, outcome: dict | None = None) -> int`
  and `_apply_pacer_gate(decision, budget_dir, *, outcome: dict | None = None) -> int` gain the
  keyword-only `outcome`. For `action == "gate"`, when `outcome` is a dict, they set
  `outcome["denied"]` to `True` exactly when this call emitted a PreToolUse deny — pacer on:
  `decision.get("enforce") and not result["admitted"]`; pacer off: `decision.get("deny") is not
  None` — and to `False` otherwise. Every other action leaves `outcome` untouched. Existing callers
  pass nothing and see no change.
- `pretooluse_task.apply_t2(ev) -> tuple[int, bool]` passes `outcome={}` and returns `(exit_code,
  outcome.get("denied", False))`. `main()` runs T1 → T1b → T2 and, when T2 reports `denied` **and**
  T1b appended an admission row for this `tool_use_id` in this call (`ev["_gtm"]` is not None
  **and** `ev["_gtm"]["appended"]` is True), calls
  `dispatch_tags.release_admission(tool_use_id, "t2_deny")` inside its own `try` — or, when
  `ev["_gtm"].get("trust_fallback")` is True, the hooks-local stdlib `_release_stdlib` (§4.6 "T1b
  wiring", the trust-failure path: no `tools/gtm` import while the trust root is failing) — (a
  failure logs `gate-fault`; the over-count is then the accepted one above), then returns the exit
  code. A T1b
  deny never reaches T2, so it never takes a pacer lease.
- Existing tests that must pass **unchanged**: `hooks/tests/test_agent_budget.py` (every
  `apply_decision(decision, budget_dir, out, err)` call site reads the `int` return),
  `hooks/tests/test_model_pin_gate.py` (its `pretooluse_task` T1→T2 section drives `ptt.main`),
  `hooks/tests/test_log_identity.py` (drives `ptt.apply_t1` and `ptt.main`) and
  `hooks/tests/test_check_safety_core_parity.py`. New B2 tests: `outcome["denied"]` is `True` for
  an enforced pacer-on saturation deny and a pacer-off `deny`, `False` for an admit and for a
  not-enforced would-deny (the dispatch runs); the release row is written only in the first two
  cases (falsified by releasing unconditionally and by never releasing).

**Week-to-date USD (`week_to_date_usd`, step 3).** Rows = `spend.jsonl` ∪ `stops.jsonl` rows with
`kind: "completed"` (their embedded claim) ∪ `claims.jsonl` claims (in flight; tokens 0 until
released), deduped with the 03_schemas.md §3.13 row key, attributed by precedence, filtered to this company and
the week (Monday 00:00 company-local), priced with `gtm_pricing.price_usd` per `model_bucket`, plus
`ST/session_spend.jsonl` rows in the week. **Tail read (I7):** `spend.jsonl` is appended at
release/reap time while a row's `ts` is its claim (or stop) time, so the file is **not** ts-ordered
(verified: consecutive real lines `14:46:38Z`, `21:04:11Z`, `20:24:30Z`). The reverse read therefore
stops only after passing a row with `ts < window_start − (claim_ttl + 3600 s)`, where `claim_ttl` =
env `CSA_CLAIM_TTL_SEC` parsed exactly as `agent_budget.claim_ttl_from_env()` does (default
21 600 s = `DEFAULT_CLAIM_TTL`, the reap window; `ai_budget` reads the same knob but does not import
`hooks/`) — no
in-window row can be appended later than that; a row with null `ts` is never a stop signal. Test:
a fixture with an old row followed by in-window rows appended after it counts every in-window row.
Latency budget: gate-gtm p95 ≤ 300 ms on a 20,000-line `spend.jsonl` (B2 test with a generated
fixture), **measured through the real dispatcher command line with both isolated subprocesses on
the path** (the `approval_sig.py --trust-result` and `ai_budget.py state` runs above;
05_approver.md §5.5 R41 — never assumed). If the measured p95 exceeds 300 ms, the B2 WP reports the
figure to the coordinator rather than removing a subprocess; the budget is revised only by a
recorded decision (Appendix B). **Race stated (I25):** USD is known only after a dispatch finishes, so parallel dispatches
admitted under the cap can together overshoot it by their own spend; the dispatch caps (serialized
above) bound that overshoot. **Blind spot stated (I8):** a running session's own top-level tokens
join only when it exits (03_schemas.md §3.19).

**Effective AI caps (`effective_ai_caps`; plan §20.6/§20.13 — the caps are `$`; I2).** Plan §20.8:
"the signature is the control" — so which records count, and which one is latest, is decided only
from **signed** bytes. For each bucket `b ∈ {opus, sonnet}`, the candidates are the approval records
in `S/approvals/<company>/` with **`decision == "approved"`** (a denial record is never evidence of
anything here) whose **own** `payload_b64` (the signed bytes, 03_schemas.md §3.8) decodes to
`system == "gtm_ai"`, `account_id == b`, and **either** `unit == "USD/week"` with a decimal
`new_absolute_value` **or** the signed report-only form `unit == "report_only"` with
`new_absolute_value` null (03_schemas.md §3.4.4/§3.7 null case (iv); `requests/07_notices_schedules.md`
R34) — never the request file's claim, which is not signed and can be deleted or rewritten (any
other `unit`, or a `USD/week` record with a null value, is a record that names this bucket and
fails the check, i.e. forged, below):
- the matching request `S/approval_requests/<company>/<request_id>.json` must exist and parse, and
  `approval_sig.verify_signature(R, record, request)` (05_approver.md §5.5: trust root, byte-equal
  payload, canonical bytes, exact key set, signature — **no** expiry, **no** action binding) must
  pass, which also makes the record's and the request's `system`/`account_id`/`unit` agree;
- its nonce must have a `consume` line in `S/approval_nonces.jsonl` (i.e. `act.py execute`
  completed the `gtm_ai.weekly_cap_edit` action). **Expiry applies only before consumption:** a
  consumed cap stays effective indefinitely (until a later signed cap supersedes it);
- the effective cap = the **latest by signed fields** among records passing both: order by the
  payload's `expires`, then its `card_id` (both inside the signature; `expires` = creation + 72 h for
  every request, 03_schemas.md §3.7, so it orders by creation, and `card_id` = the request id, which
  embeds the creation timestamp). **`signed_at` is never read** — it sits outside `payload_b64`, so
  editing it on an old, higher, consumed cap must not make that cap effective again. `source:
  "signed:<request_id>"`. **`"0.00"` = a ZERO CAP** (`requests/07_notices_schedules.md` R32 applied;
  plan §20.13 "a pause is amount 0", 03_schemas.md §3.7 `"0.00"` = pause/stop; the operator's
  Touch-ID dialog shows it as "$0.00 / week — ZERO CAP: every GTM AI dispatch stops except lead
  capture", 05_approver.md §5.1): `usd: "0.00"`, and `budget_state` lists the bucket in `over`
  from the first dispatch, so only the plan §6.8 lead-capture allowance is admitted (step 3).
  **The signed report-only form** (`unit: "report_only"`, value null; the dialog shows "NO CAP —
  report only, unlimited AI spend") gives `{usd: None, source: "signed:<request_id>", forged:
  false}` and never trips. Turning enforcement off after the first signed cap is therefore reachable
  **only** by that separate signed approval — itself `$` — never by `0.00`. Once any signed cap
  (zero, amount or report-only) is effective, `company.json`'s `budget.weekly_usd_cap_<b>` is
  **ignored** (the pack validator warns when it exceeds the signed value).
- **Ledger cross-check:** every `consume` line in `S/approval_nonces.jsonl` with `company == X` and
  `system == "gtm_ai"` (fields act.py copies from the verified signed payload onto every ledger line,
  `requests/03_schemas.md` §3.9) must have an approved record for its `request_id` whose signed
  payload carries that nonce and that passes the first bullet — **report-only records included**
  (they are candidates, so a report-only consume line is matched by its record, never marked
  forged) — so deleting an effective record, or flipping its unsigned `decision` to `"denied"`,
  cannot quietly fall back to an older cap.
- None passing and nothing forged: an approved-but-not-yet-consumed record is simply not yet
  effective; the `company.json` value applies (`source: "company_json"`, `0` = `"report_only"`).
  **Deliberate fail-safe narrowing (stated; `requests/04_hooks.md` R47 asks for its Appendix B
  entry):** a non-zero unsigned `company_json` cap is **enforced** — crossing it puts the bucket in
  `over`, and step 3 writes `PAUSE.budget` and stops AI dispatches — although plan §20.13
  reconciles automatic enforcement only for an "operator-approved AI-spend cap" and §20.6 treats
  the department's AI caps, and stopping spend, as `$` needing operator sign-off. The deviation only
  ever stops spend earlier (never raises or removes a cap: an unsigned value can never override a
  signed one, and `0` is report-only), so it narrows §20.6/§20.13 in the safe direction; the
  operator lifts it with `act.py resume --name PAUSE.budget` or a signed cap.
- **Forged state** (`forged: true`) when, for a bucket: an approved record whose signed payload names
  it (`gtm_ai`, that bucket) has a **missing or unparseable request**, or fails the signature,
  byte-equality, canonical-bytes or key-set check; or a `gtm_ai` consume line for that bucket (per
  the cross-check; an `account_id` outside `{opus, sonnet}` → every bucket) has no matching verified
  approved record; or the trust-root check fails (checked first and unconditionally, whether or not
  any record exists — then nothing can be verified, and every bucket is forged). A forged bucket is
  treated as **cap exceeded** (budget state) and a `trust` notice is written; nothing that breaks the
  signed chain ever falls back to an older signed cap or to the editable file. (How a
  `key_not_installed` or retired-key verification result is classified is `requests/05_approver.md`
  R13 (b)/(c), not decided here. R13 (a)'s "last `consume` line in the ledger" ordering is **not**
  adopted: the ledger is unsigned, so the order comes from the signed payload instead.)
- **Residual, stated:** deleting **both** an effective record and its consume line (possible only
  through a shell path G-B rule c does not parse, §4.2 "Known shell-write reach") reverts to the
  previous signed cap — itself an operator decision — or to `company.json`; the executed
  `gtm_ai.weekly_cap_edit` action stays in the hash-chained `actions.jsonl`, where `validate_run`
  reports a completed cap edit with no effective record (`requests/02_act.md`).
P2 tests (B2; each falsified): raising `company.json`'s cap while a signed cap exists does not change
the enforced cap; setting it to 0 does not disable enforcement; the signed cap is still enforced 4
days after approval (past the request's 72 h `expires`); a denial record does **not** create budget
state; a tampered approved record does; deleting the latest cap's **request** file → that bucket
forged, not a fallback (falsified by classifying from the request); rewriting its request's
`system` to `google_ads` → forged; editing an older, higher, consumed record's `signed_at` to a later
time leaves the effective cap unchanged (falsified by ordering on `signed_at`); deleting an approved
record whose nonce is consumed → forged (falsified by dropping the cross-check); flipping its
`decision` to `"denied"` → forged. Zero cap and report-only (`requests/07_notices_schedules.md`
R32/R34; each RED when reverted to the former "`0.00` = report only" reading or to the
`USD/week`-only candidate filter): a consumed signed `"0.00"` opus cap puts opus in `over` with
week-to-date `usd` `"0.00"`, and gate-gtm then denies a non-inbox `gtm-analyst` dispatch `gtm-budget`
while admitting the reserved inbox lead-capture one; a consumed signed report-only opus record gives
`{usd: null, source: "signed:<id>", forged: false}`, is not forged and never trips at any spend; a
report-only `consume` line whose record is present is not forged, and the same line with its record
deleted is.

**Workflow legs never reach this gate.** A GTM seat dispatched through the `Workflow` tool's
`agent()` bypasses PreToolUse:Task (runtime CLAUDE.md §7) — step 0, tag validation, the
sequential-browser rule, budget state and dispatch caps; §4.10 denies such scripts mechanically.

**Step −1 — non-roster dispatch in a scheduled run (07's R19; plan §20.9c "not allowed to … start
changing features").** Evaluated for **every** `Agent`/`Task` dispatch, before the "enforced
dispatch" test below: when `CLAUDE_GTM_COMPANY` is set and `CLAUDE_GTM_RUN` is **not** a
`CYCLE_ID_RE` match (00_global_paths.md §0.3) with `slug == CLAUDE_GTM_COMPANY` and `kind ==
"interactive"` — i.e. a scheduled kind, or an absent/unparsable/other-company value, which is
treated as scheduled (fail closed; `gtm_session.sh` always sets it for interactive sessions, 07
§7.6) — deny every dispatch whose `subagent_type` is not in `seat_sets()`'s `GTM_SEATS ∪
DEPARTMENT_SEATS` (`gtm-nonroster-dispatch`, unconditional in GTM scope, logged like every
gate-gtm deny). `CLAUDE_GTM_RUN` only **tightens** here (00_global_paths.md §1.4: no gate trusts it for
authorization; a forged `interactive` value can only re-enable today's interactive behaviour, and
rule l forbids setting `CLAUDE_GTM_*` in a command naming act.py). Interactive GTM sessions keep
the "non-GTM agent types: untouched" rule below. B2 tests (each RED when the step is removed): in a
scheduled-run fixture (`CLAUDE_GTM_RUN=cyc_other-company_daily_2026_09_27`), `implement` and
`general-purpose` → denied `gtm-nonroster-dispatch`; `gtm-analyst` and `marketing-director` →
not denied by this step; the same `implement` dispatch with
`CLAUDE_GTM_RUN=cyc_other-company_interactive_2026_09_27_0930` → allowed; with `CLAUDE_GTM_RUN` unset
in a GTM session → denied.

Decision order for an enforced dispatch (`subagent_type ∈ GTM_SEATS`, or `∈ DEPARTMENT_SEATS` while
`CLAUDE_GTM_COMPANY` is set); first match wins:

0. `subagent_type ∈ GTM_SEATS` and `CLAUDE_GTM_COMPANY` unset → deny `gtm-seat-outside-gtm-session`.
   **DECIDED HERE** (§3.4: GTM work runs only in `gtm_session.sh` sessions). Not relied on for PHI
   or Agency scoping (§4.4 keeps its own agent_type arm).
1. Tag missing/malformed, slug not in `company.gtm_slugs()`, `run_kind()` returns None, or
   `company ≠ CLAUDE_GTM_COMPANY` → deny `gtm-tag`.
2. `subagent_type ∈ BROWSER_SEATS` and any ticket in `S/tickets/<company>/` with `session_id ==
   payload.session_id` and `status == "bound"` → deny `gtm-sequential` (`stopped` tickets do not block).
3. Budget state = `ai_budget.budget_state(company, now)` — obtained as the isolated `ai_budget.py
   state --company <CLAUDE_GTM_COMPANY>` subprocess after the isolated trust check succeeded (F-trust
   above; a failed trust check never reaches `decide` — it takes "T1b wiring"'s trust-failure path;
   a budget result that cannot be obtained or interpreted is the constructed forged state, R69):
   `ST/PAUSE.budget` exists, or this
   company's week-to-date opus or sonnet USD exceeds that bucket's **effective** cap, or that cap is
   a signed `"0.00"` zero cap (over from the first dispatch; report-only caps, unsigned or signed,
   never trip), or a bucket is in the forged state. `budget_state` itself only reads (act.py
   `resume` calls it too), and so does `gtm_task_gate.decide`; the writes are made by the T1b
   wrapper `pretooluse_task.apply_t1b` (below) from `decide`'s returned `detail` (FID-15; plan
   §5/§7.4 — the operator is always told the department stopped). Bucket, USD, cap and source come
   from `budget_state(...)["buckets"]` — no second attribution load:
   - **(a) over cap** (`over` non-empty) and no `ST/PAUSE.budget` yet → create it exclusively
     (`O_EXCL`; a concurrent creator wins, no error) with `{"reason": "<bucket> week-to-date
     $<usd> over cap $<cap> (<source>)", "created_by": "gate-gtm", "ts"}` (03_schemas.md §3.10),
     and `write_notice_file(company, "budget", "urgent", …, push=True, dedupe_key=
     "budget:<slug>:<ISO week>", created_by="gate-gtm")` naming bucket, USD and cap (ISO week
     company-local, the week `week_to_date_usd` uses);
   - **(b) forged** (`forged` non-empty in the `state` result) → the same `PAUSE.budget` and
     `budget` notice, **plus** a `trust` notice (urgent, push, `created_by="gate-gtm"`): when every
     bucket is forged (the tree changed between the two subprocesses, or `ai_budget`'s own trust
     check failed) slug `runtime`, `dedupe_key="trust_root:<ISO week>"`; otherwise slug = company,
     `dedupe_key="forged:<slug>:<bucket>:<ISO week>"`. (A failed **first** trust check never reaches
     step 3: it takes the trust-failure path of "T1b wiring", which writes nothing, below.)
   The writes happen when `unconditional or _lib.enforcing(where)` is true, where `unconditional`
   is True in GTM scope (00_global_paths.md §0.4 — so every enforced dispatch, which by definition
   carries `CLAUDE_GTM_COMPANY` or is a GTM seat, writes them whether or not `~/.claude/.enforce`
   exists; a log-only would-block remains possible only for a non-GTM-scope caller, which step 0
   already denies), and never raise (a failure logs `gate-fault` and the deny stands). The
   `PAUSE.budget` file and the `budget` notice are skipped when `PAUSE.budget` already exists (the
   notice dedupe covers repeats); the (b) `trust` notice is **not** skipped — it is attempted on
   every enforced forged dispatch and its own dedupe key suppresses repeats, so tampering found
   after an earlier over-cap pause the same week still reaches the operator (FID-15). B2 tests, each falsified by
   removing its write: (a) an over-cap dispatch writes `PAUSE.budget` (`created_by: gate-gtm`,
   reason naming bucket, USD and cap) and exactly one open urgent pushed `budget` notice, and a
   second over-cap dispatch the same week writes neither again; (b) a tampered approved record
   writes the same plus one `trust` notice; a `state` result with every bucket forged writes one
   `runtime` `trust` notice; with `PAUSE.budget` already present from an over-cap dispatch the same week, a forged
   dispatch still writes exactly one `trust` notice (RED when the `PAUSE.budget` skip also covers
   it). Under budget state admit
   **only** `gtm-analyst` with `run_kind == "inbox"`, an **unbound** (`pending`) read ticket in this
   session, and fewer than 2 `budget_admission` rows for the company since company-local midnight
   (checked inside `admit_and_record`); that admission sets `budget_admission: true` and **falls
   through** to steps 4–5. Everything else → deny `gtm-budget`.
4. Dispatch cap: `admit_and_record` finds `count_dispatches(company, run_id=run_id)` ≥
   `budget.dispatch_caps_per_run[run_kind]` (`interactive` → the `interactive` key if present, else
   `mission`, 03_schemas.md §3.12) → deny `gtm-dispatch-cap`. (Dispatch caps stay pack values: they bound fan-out,
   not money.)
5. Allow: `decide` returns no block and `detail["admission"]`; `apply_t1b` then calls
   `admit_and_record`, and on `(True, "admitted")` or `(True, "duplicate")` **`apply_t1b`** sets
   `ev["_gtm"] = {company, run_id, run_kind, seat, in_gtm_session, budget_admission, source:
   "claim", appended}`, `appended` = True only for `"admitted"` (§ "Admissions that never run").
   `decide` itself writes nothing, sets nothing on `ev` and logs nothing.

Not enforced (department seat outside a GTM session): `decide` returns no block with
`detail["untagged"] = True`; `apply_t1b` allows, sets `ev["_gtm"] = None` and logs `gtm_untagged`. Non-GTM agent types: untouched (a tagged non-GTM dispatch inside a cycle, e.g.
`implement`, gets `ev["_gtm"]` from its tag with `seat` = its type and a `dispatch_tags.jsonl` row,
no denial; its row has `seat_row: false`, so it is recorded but never counted or charged — see
"Counting").

**T1b wiring and effects (F-t1b; B2 edits `hooks/pretooluse_task.py`).** `gtm_task_gate.decide(ev,
environ, *, budget: dict | None) -> (block, reason, detail)` is **effect-free**: it reads only (the
budget state is passed in by `apply_t1b`, which obtained it by subprocess, F-trust), and for a
dispatch it would admit it returns `detail["admission"] = {"tag_row", "cap",
"budget_admission_limit"}`, under budget state `detail["budget"] = <that budget state>`, and for
every enforced dispatch `detail["unattributed_usd"]` (step 5 of the attribution precedence).
**Reserved keys:** `detail` never uses `hook`, `decision`, `gate`, `reason`, `enforce`, `session`,
`agent_type`, `agent_id`, `repo`, `tool_use_id` or `error` (a B2 test asserts every `detail` key
`decide` can return is outside this set). All effects live in a new
**`pretooluse_task.apply_t1b(ev) -> bool`** (True = continue to T2, False = a deny was emitted),
with `where = _lib.cwd(ev)` exactly as `apply_t1` computes it:
- **pre-import short-circuit (no import, no subprocess):** unless `CLAUDE_GTM_COMPANY` is set, or
  `tool_input.subagent_type` is in `_GTM_SEAT_NAMES` (the hooks-local copy of `GTM_SEATS ∪
  DEPARTMENT_SEATS`, "Hooks-local definitions" above), or the prompt's first line starts with
  `[gtm `, set `ev["_gtm"] = None` and return True at once — so non-GTM work pays no import, no
  subprocess, no git and no `gate-fault` rows. Exceptions raised here fall to the fail mode below
  (fail open: nothing GTM is involved yet). B2 test: an `implement` dispatch with no GTM env and no
  tag spawns no subprocess and imports no `tools/gtm` module (import recorder);
- **trust first (F-trust):** run the isolated `approval_sig.py --trust-result` subprocess (§4
  "Isolated subprocesses"; `_TRUSTED_PYTHON`, `<_trust_root(os.environ)>/tools/gtm/approval_sig.py`,
  5 s timeout). **"Ok" (binding, 05_approver.md §5.5 `approval_sig.py` canonical CLI,
  `--trust-result` line):** `--trust-result` prints `{"ok": bool, "entries": [...]}` and exits 0
  when ok, 11 when not; the trust check counts as ok **only** when the process exits 0 within the
  5 s timeout **and** its stdout is exactly one JSON object whose `ok` is the boolean `true` (`is
  True`); every other outcome — exit 11, 3, 2 or 1, a timeout, extra output, non-JSON, `ok` missing
  or not exactly `true` — **and every exception while obtaining or interpreting it** (the
  prefix `os.mkdir`, a spawn `OSError` such as a missing `_TRUSTED_PYTHON` after a `brew` change, a decode
  or JSON error; `requests/05_approver.md` R69) is a failed check and takes the trust-failure path;
- **the trust-failure path (DECIDED HERE; stdlib only — no `tools/gtm` module is imported, before
  or after the emit, and nothing is written except the lead-capture admission row and the log
  row).** With `S = _claude_dir(os.environ) / ".gtm_state"`, `slug = CLAUDE_GTM_COMPANY`, and
  `now` the real UTC clock:
  (T1) **step −1** — `CLAUDE_GTM_COMPANY` set and `CLAUDE_GTM_RUN` not a `_CYCLE_ID_RE` match with
  `slug == CLAUDE_GTM_COMPANY` and `kind == "interactive"`, and `subagent_type ∉ _GTM_SEAT_NAMES`
  → deny `gtm-nonroster-dispatch`;
  (T2) **not enforced** (not a GTM seat, and not a department seat with `CLAUDE_GTM_COMPANY` set)
  → `ev["_gtm"] = None`, log `gtm-trust-root-failed`, return True (not admitted, not recorded);
  (T3) **step 0** — a GTM seat with `CLAUDE_GTM_COMPANY` unset → deny
  `gtm-seat-outside-gtm-session`;
  (T4) **the plan §6.8 lead-capture allowance** (plan §5: no lead sits unlogged under a stop;
  05_approver.md §5.5 step 0 and its trust-drift list: "the lead-capture analyst allowance is still
  admitted, and with the fallback read ticket it can read"; `requests/05_approver.md` R54 as
  amended by R67 (c)) — admitted **only** when all of: (a) `subagent_type == "gtm-analyst"`;
  (b) the prompt's first line matches `_TAG_RE`, its company equals `slug` and matches `_SLUG_RE`,
  and its run matches `_CYCLE_ID_RE` with that slug and `kind == "inbox"`; (c) **step 2, stdlib**:
  no `S/tickets/<slug>/*.json` parses to a ticket with `session_id == payload.session_id` and
  `status == "bound"` (else deny `gtm-sequential`); (d) some `S/tickets/<slug>/*.json` parses (plain
  `json.loads`) to a ticket with `class == "read"`, `status == "pending"`, `session_id ==
  payload.session_id` and an `expires` that parses (00_global_paths.md §0.3 ISO form) and is later
  than `now` — a `minted_by: "trust_fallback"` ticket (02_act.md §2.3 stdlib fallback, R67 (a))
  counts like any other; (e) under `S/dispatch_tags.lock` (`fcntl.flock`, 5 s; one retry after
  250 ms, then deny `gate-fault`), a tail read of `S/dispatch_tags.jsonl` — and of the one rotated
  `dispatch_tags.<YYYY-MM>.jsonl` of the previous UTC month when present — back to the first row
  older than `now − 48 h` finds **fewer than 2** admission rows with `company == slug`,
  `budget_admission is True`, and a `run_id` matching `_CYCLE_ID_RE` with `kind == "inbox"` and the
  same `date` group as this run, not counting a row whose `tool_use_id` has a later `released` row
  (else deny `gtm-budget`). The day is the run id's date: an inbox id's date is the company-local
  `run_date` (00_global_paths.md §0.3), so this is the normal path's "since company-local midnight"
  count without reading the pack's `timezone` (stated: a late fire keeps its occurrence's date on
  both paths). A row with the same, unreleased `tool_use_id` makes the call a duplicate: nothing is
  appended and the dispatch proceeds with `appended: False`. (f) In the same critical section it
  appends, with one `os.write` of the full line to a file opened `O_APPEND`, the 03_schemas.md
  §3.13 admission row `{"ts": <now, "%Y-%m-%dT%H:%M:%SZ">, "tool_use_id", "session_id", "company":
  slug, "run_id", "run_kind": "inbox", "seat": "gtm-analyst", "budget_admission": true,
  "seat_row": true, "trust_fallback": true}` (the last key requested of 03 §3.13,
  `requests/04_hooks.md` R59; the stdlib writer never rotates the file — the next `dispatch_tags`
  writer does, under the same lock), sets `ev["_gtm"] = {"company": slug, "run_id", "run_kind":
  "inbox", "seat": "gtm-analyst", "in_gtm_session": True, "budget_admission": True, "source":
  "claim", "appended": <bool>, "trust_fallback": True}`, logs `gtm-trust-fallback-admitted` and
  returns True (T2 runs; the analyst reads with the fallback read ticket);
  (T5) **every other enforced dispatch** → deny `gtm-budget` with `detail = {"forged":
  "trust_root"}`.
  Any exception inside (T1)–(T5) → deny `gate-fault` for an enforced dispatch, allow + log for a
  non-enforced one (the trust root failed, so nothing enforced is admitted on error). **The T2-deny
  release of a trust-fallback admission** (`ev["_gtm"]["trust_fallback"]` and `appended` True) is
  made by the hooks-local stdlib `_release_stdlib(S, tool_use_id, "t2_deny")` — the same
  `{"ts","tool_use_id","released": true,"reason"}` row `dispatch_tags.release_admission` writes,
  under the same lock — never by importing `dispatch_tags`. **No `PAUSE.budget`, `budget` notice
  or `trust` notice is written on this path** (design choice, stated): the operator's signals are
  the deny text; the step-0 trust notice that every `act.py` command writes while the tree differs
  from HEAD (02_act.md §2.3, 05_approver.md §5.5 step 0 — the GTM session's own act.py calls,
  including the inbox run's `ticket --read` fallback, write it); and the daily trust check, which
  turns a standing difference into `S/PAUSE.trust` (05_approver.md §5.6). Consequence (stated): a
  trust drift leaves no `PAUSE.budget` behind, so once the tree equals HEAD again dispatches resume
  without `act.py resume --name PAUSE.budget`; a genuine over-cap or forged-record state is then
  re-detected by the next `ai_budget.py state` run (step 3) and pauses as usual.
  **Messages and log row on this path (binding; no `tools/gtm` import):** the deny text comes from
  a hooks-local constant in `pretooluse_task.py`,
  ```python
  _TRUST_FAIL_MESSAGES = {
      "gtm-budget": "GTM dispatch refused: the GTM trust root failed its check (tools/gtm differs "
                    "from the committed, operator-reviewed HEAD), so every AI-spend bucket is "
                    "treated as forged and the department is stopped except inbox lead capture. "
                    "The operator restores the trust root; see the runtime trust notice.",
      "gtm-nonroster-dispatch": "GTM dispatch refused: a scheduled GTM run may dispatch only "
                    "GTM_SEATS or DEPARTMENT_SEATS agents (plan §20.9c).",
      "gtm-seat-outside-gtm-session": "GTM dispatch refused: a GTM seat runs only inside a "
                    "gtm_session.sh session.",
      "gtm-sequential": "GTM dispatch refused: this session already holds a bound browser ticket; "
                    "browser seats run one at a time.",
      "gate-fault": "GTM dispatch refused: gate-gtm could not decide safely (fail closed).",
  }
  ```
  emitted with `_lib.emit_pretooluse_deny(_TRUST_FAIL_MESSAGES[reason])`; a B2 P2 parity test
  asserts each value equals `gtm_task_gate.message_for(reason, detail)` for that reason's detail
  (`{"forged": "trust_root"}` for `gtm-budget`), so the two sources cannot drift (the test imports
  `gtm_task_gate`; the hook on this path never does). The log row is built as `fields =
  _log_fields(ev, where, {})`, then `fields.update(gate="gtm_task_gate", reason=<reason>,
  enforce=<emit>, forged="trust_root")`, then `_lib.log(HOOK_NAME, "would-block", **fields)` — the
  same shape as the block path below, never explicit keywords splatted beside a dict; a
  non-enforced dispatch that proceeds logs `fields = _log_fields(ev, where, {});
  fields.update(gate="gtm_task_gate"); _lib.log(HOOK_NAME, "gtm-trust-root-failed", **fields)`.
  B2 tests (trust subprocess stubbed; each RED when its clause is removed): printing `{"ok":
  "true", "entries": []}` with exit 0 → an enforced dispatch is denied `gtm-budget` (RED with a
  truthiness test); `_TRUSTED_PYTHON` pointing at a missing file → the trust-failure path, not an
  allow (RED when the spawn `OSError` falls into the fail-open mode); exit 11 → the emitted message
  equals `_TRUST_FAIL_MESSAGES["gtm-budget"]`, and an import recorder on the tmp tree — whose
  uncommitted `tools/gtm/company.py` and `gtm_hooklib.py`-reachable modules carry a marker side
  effect — shows **no** `tools/gtm` module imported at any point of the call (RED when the path
  imports anything, before or after the emit); exit 11 with an `inbox` `gtm-analyst` dispatch
  (tag `[gtm company=other-company run=cyc_other-company_inbox_2026_09_28_0900]`) whose session holds a
  `pending` read ticket with `minted_by: "trust_fallback"` → admitted twice (two admission rows with
  `trust_fallback: true`, `ev["_gtm"]["budget_admission"]` True) and denied `gtm-budget` the third
  time; the same dispatch with no pending read ticket, or tagged with a `daily` run, or a
  `gtm-drafter` seat → denied `gtm-budget`; with a `bound` ticket in the session → denied
  `gtm-sequential`; a T2 deny after a trust-fallback admission writes one `released` row through
  the stdlib writer, and the next inbox dispatch is admitted again;
- **Ok → imports and the budget subprocess:** load `gtm_task_gate` (and through it `gtm_hooklib`,
  `company`, `system_names`, `dispatch_tags` — never `ai_budget` or `approval_sig`) through §4's
  hook import rule (`gtm_import`) **lazily inside its own `try`**, never at `pretooluse_task.py`'s
  top level — so a broken GTM module can never crash the dispatcher on load and disable T1 (the
  model-pin gate) or T2 (the pacer) machine-wide. For an enforced dispatch **with
  `CLAUDE_GTM_COMPANY` set**, run the isolated `<_TRUSTED_PYTHON> -I -S -B -X pycache_prefix=<fresh
  P> <_trust_root()>/tools/gtm/ai_budget.py state --company <CLAUDE_GTM_COMPANY> --json`
  subprocess (the one exact command line, 05_approver.md §5.5; `X` is always
  `CLAUDE_GTM_COMPANY`, never the tag's company — step 1 denies a tag naming another company) and
  pass its JSON as `budget`; with `CLAUDE_GTM_COMPANY` unset no subprocess runs and `decide` gets
  `budget=None` (step 0 denies a GTM seat; a department seat is then not enforced). **Budget
  result (binding; `requests/05_approver.md` R69):** the result is accepted only when the process
  exits 0 within 10 s and stdout is exactly one JSON object with `over` and `forged` lists whose
  members are in `{"opus", "sonnet"}`, a bool `pause_present`, a string `unattributed_gtm_usd`, and
  `buckets` holding exactly `opus` and `sonnet`, each with a string `usd`, a string-or-null `cap`
  and a string `source`. Any other outcome — exit 13 (an unknown company), any non-zero exit, a
  timeout, extra output, non-JSON, a shape mismatch, and **every exception while obtaining or
  interpreting it** (the prefix `os.mkdir`, spawn `OSError`, decode) — makes `apply_t1b` pass the constructed
  forged state `{"over": [], "forged": ["opus", "sonnet"], "pause_present": <ST/PAUSE.budget
  exists, False when that stat itself fails>, "unattributed_gtm_usd": "0.00", "buckets": {b:
  {"usd": "0.00", "cap": None, "source": "forged"}}, "forged_cause":
  "budget_state_unavailable"}` — so `decide` never sees a malformed state, and step 3 denies
  `gtm-budget` (the lead-capture allowance still admits through `admit_and_record`) and writes
  step 3 (b)'s `PAUSE.budget`, `budget` notice and a company-slug `trust` notice whose body names
  the cause (`dedupe_key` `"budget_state_unavailable:<slug>:<ISO week>"`);
- **emit test (00_global_paths.md §0.4):** `unconditional` = `CLAUDE_GTM_COMPANY` is set, or
  `subagent_type ∈ GTM_SEATS`, or payload `agent_type ∈ GTM_SEATS`; a block is emitted when
  `unconditional or _lib.enforcing(where)`;
- on `block`: builds the log row as `fields = _log_fields(ev, where, detail)`, then
  `fields.update(gate="gtm_task_gate", reason=reason, enforce=emit)`, and calls
  `_lib.log(HOOK_NAME, "would-block", **fields)` — never splatting `detail` next to explicit
  keywords (a colliding key would raise `TypeError`, which the fail mode would turn into an allow;
  `_log_fields` is `pretooluse_task`'s own, so `gtm_task_gate` never imports `pretooluse_task` — no
  import cycle); performs step 3's `PAUSE.budget`/notice writes **only when `reason ==
  "gtm-budget"`** and `emit` (each in its own `try`; a failure logs `gate-fault` and the deny
  stands) — a `gtm-tag`, `gtm-sequential`, `gtm-dispatch-cap` or step −1/0 deny never writes
  `PAUSE.budget`, whatever `detail["budget"]` holds; emits `_lib.emit_pretooluse_deny(
  message_for(reason, detail))` when `emit` and returns False, else returns True (a would-block
  that is not emitted proceeds to T2 like T1's);
- on allow (no block) with `detail["admission"]`: calls `dispatch_tags.admit_and_record(...)` (one
  retry after 250 ms on `TimeoutError`, then deny `gate-fault` for an enforced dispatch — §
  "Admissions that never run"; `AdmissionInputUnreadable` → deny `gate-fault` at once for an
  enforced dispatch, no retry); `(False, "dispatch-cap")` → deny `gtm-dispatch-cap`, `(False,
  "budget-admission-exhausted")` → deny `gtm-budget` (same log/emit path); `(True, r)` → sets
  `ev["_gtm"]` (step 5, `appended = r == "admitted"`) and returns True; with `detail["untagged"]`
  → sets `ev["_gtm"] = None`, logs `gtm_untagged` and returns True;
- on both allow and block, when `detail.get("unattributed_usd")` parses > 0: writes the runtime
  `budget` notice of attribution step 5 (own `try`; failure logs `gate-fault`, no decision change);
- **fail mode:** any other exception anywhere in `apply_t1b` (the `gtm_task_gate` import included)
  → log `gate-fault` with `fields = _log_fields(ev, where, {}); fields.update(gate="gtm_task_gate",
  error=…); _lib.log(HOOK_NAME, "gate-fault", **fields)`, leave `ev["_gtm"] = None`, and return
  **True**, so T2 still runs and the pacer lease and spend-ledger claim are still taken — the GTM
  spend of a dispatch admitted during a gate-gtm fault is still counted by `agent_budget`. (This
  replaces "inherits `main()`'s degrade-to-allow": `main()`'s outer `except Exception: return 0`
  returns before `apply_t2`, which would skip the lease and the claim.) The stated exceptions to
  fail-open: the pre-import short-circuit and non-enforced dispatches are the only paths that fail
  open; for an enforced dispatch, a failed trust check (the trust-failure path), a budget result
  that cannot be obtained or interpreted (the forged state above, R69), the repeated admission-lock
  timeout (deny) and `AdmissionInputUnreadable` (deny) never allow — the last two because an
  enforced GTM-seat dispatch admitted with no admission row would run uncapped. G-A ticket binding
  stays the fail-closed backstop for browser writes. Every `gtm_pyc_*` prefix this function
  creates is removed per §4 "Isolated subprocesses".
`main()` becomes T1 → `apply_t1b` → T2 (+ the §4.6 release on a T2 deny). B2 tests: with
`gtm_task_gate` made unimportable (a syntax error in a tmp copy of the code root), a T1 pin
violation is still denied, and an allowed dispatch still gets a pacer claim recorded (falsified by a
top-level import); an exception inside `decide` logs `gate-fault` and T2 still runs; `decide` on an
over-cap fixture writes nothing (falsified by moving the writes into `decide`); a `detail` that
contains the key `reason` still denies (RED with the naive `**detail` splat beside `reason=`); with
no enforce markers in a tmp `HOME`, an over-cap GTM-seat dispatch in a GTM session is denied and
writes `PAUSE.budget` (RED when the emit test is `_lib.enforcing` alone); an over-cap fixture
dispatch whose tag names another company is denied `gtm-tag` and writes no `PAUSE.budget` and no
`budget` notice (RED when the writes are not limited to `gtm-budget`). **R69 (05_approver.md §5.5
step 0's test environment, exactly: `HOME=<tmp>/home` with `<tmp>/home/.claude` the fixture `R`,
`CLAUDE_DIR` the same path, `GTM_TEST=1`, `CSA_ENFORCE=1`, a fixture `agents/<seat>.md` and
`knowledge/model_policy.json` pinning the seat, run through `python3 <tmp R>/hooks/pretooluse_task.py`;
each RED when the exception escapes to the fail-open mode):** with the fixture tree's `ai_budget.py`
replaced by a script that raises, an enforced GTM-seat dispatch is decided `forged` — observed both
as the PreToolUse deny JSON on stdout naming `gtm-budget` and as the tmp
`<tmp>/home/.claude/.enforcement/log.jsonl` row for the call — and a `state` stub printing an
object without `buckets` is decided the same way.

### 4.7 `bash_gate.sh` fast path (WP-B2)

Every addition in this section lands only in the post-Wave-2 G-B activation train (§4.2, IMP-04):
B2 delivers it in `tools/gtm/wave2_pending/b2_gb_wiring.patch` and runs the tests below against a
patched tmp copy; during Wave 2 the live `bash_gate.sh` is unchanged. **No subprocess on the fast
path (cost).** `bash_gate.sh` is run by bash (its registered command invokes `bash`, never `sh`;
macOS `/bin/bash` 3.2 supports everything below), and the GTM arms use **bash built-ins only** — no
`tr`, `grep` or other process per Bash call — so an unrelated command still costs no spawn:
**Case (F-case):** paths and hosts on this machine are case-insensitive, so the GTM arms match with
`shopt -s nocasematch` set immediately before arm 2 and `shopt -u nocasematch` immediately after arm
4 (the existing, mixed-case `case` of `bash_gate.sh` then runs exactly as today). Tokens are written
lowercase; matching an uppercase literal such as `GTM_HOLDS_JOB` case-insensitively forwards more,
never less. Add **before** the existing `case`, in this order:
1. `[ -n "${CLAUDE_GTM_COMPANY:-}" ] && { printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"; exit 0; }`.
2. The GTM-seat arm (§4.2 "GTM scope"): `[[ $payload =~ $GTM_SEAT_RE ]] && { printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"; exit 0; }`
   with `GTM_SEAT_RE` below (the 9 fixed `GTM_SEATS`; a P2 test asserts the regex lists exactly
   `system_names.GTM_SEATS`), assigned once near the top of `bash_gate.sh`, before first use.
   **2b. The department-seat arm (Agency scope, §4.2 rule i; 00_global_paths.md §0.4):** `[[ $payload =~ $GTM_DEPT_SEAT_RE ]] && { printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"; exit 0; }`,
   with `GTM_DEPT_SEAT_RE` below (the 9 `DEPARTMENT_SEATS`; a P2 parity test asserts it lists
   exactly `system_names.DEPARTMENT_SEATS`), so a `/gtm` mission's director or specialist Bash call
   from an ordinary session reaches rule i at all. Tests (end to end, non-GTM session, each RED when
   the arm is removed): a `marketing-director` payload's `ls ~/Desktop/OtherApp` with cwd the CSA root
   is denied `agency-boundary`; the same with cwd inside the (tmp) Agency root is allowed; an
   unrelated `ls -la` from a department seat is allowed (all built on the realistic payload of the
   arm-4 "Fixed payload keys" test). Same probe-q fallback as the seat arm (§4.2).
3. **Destructive-verb arm (I9):** `[[ $payload =~ $GTM_DESTRUCTIVE_RE ]] && { printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"; exit 0; }`,
   with both regexes assigned verbatim (single-quoted) as:
   ```bash
   GTM_SEAT_RE='"agent_type"[[:space:]]*:[[:space:]]*"(local-presence-architect|social-media-strategist|measurement-architect|revenue-ops-architect|gtm-analyst|gtm-drafter|gtm-checker|gtm-operator|gtm-credential-setup)"'
   GTM_DEPT_SEAT_RE='"agent_type"[[:space:]]*:[[:space:]]*"(marketing-director|conversion-architect|brand-architect|content-strategist|seo-architect|paid-acquisition-strategist|pricing-economist|video-producer|market-analyst)"'
   GTM_DESTRUCTIVE_RE='(^|[;&|[:space:]"(`/\\]|\\[nt])(rm|rmdir|mv|cp|ln|tee|unlink|shred|truncate|rsync|tar|install|ditto|patch|dd|touch|chmod|chflags|chown|xargs|pip|pip3|brew)([[:space:]]|\\[nt])|(^|[;&|[:space:]"(`/\\]|\\[nt])(sed|perl)(([[:space:]]|\\[nt])+[^[:space:];&|]*)*([[:space:]]|\\[nt])+(-[a-z0-9]*i|--in-place)|-delete([[:space:]"]|\\[nt]|$)'
   ```
   (`pip`/`pip3` are forwarded so rule c's GTM-scope `pip install --user/--target` clause is
   reachable; outside GTM scope G-B allows them. `brew` is forwarded so rule c's interpreter-pin
   clause sees `brew upgrade`/`reinstall` with or without a formula. The `sed|perl` arm admits any
   intervening words before the in-place option — `sed -E -i …`, `sed -e x -i …`, `perl -0777 -pi …`
   — where the former `(-[a-z]*i|--in-place)`-immediately-after-the-verb arm missed them (verified
   under `/bin/bash` 3.2); a `;`, `&` or `|` ends the chain, so `sed -n p f | grep -ri x` is not
   forwarded by this arm.)
   The left context admits, besides `^`, `;&|`, whitespace, `"` and `(`: a backtick (`` `rm x` ``),
   `/` (`/bin/rm`), a backslash (`\rm`) and the JSON escapes `\n`/`\t` — the payload is JSON, so a
   command `true⏎rm -rf gtm` arrives as `"true\nrm -rf gtm"`, with an `n` directly before `rm`;
   the right context likewise admits `\n`/`\t`. Rule (c) covers **ancestors** of protected paths
   (`rm -rf gtm` with cwd `H/.claude`, `rm -rf ~/.claude`) and relative write targets
   (`cp forged.json gtm/state/autonomy_state.json`, `tee`, `ln`, `sed -i` with cwd `H/.claude`),
   which no path token can see, so every destructive, copying or permission verb (and `xargs`, whose
   verb is its argument) is forwarded to python in every session. A bare redirect (`> file`) is
   **not** in this arm (it would forward nearly every command); relative redirect targets are caught
   by the path tokens of arm 4. **Cost accepted:** one python spawn per `rm`/`mv`/`cp`/`chmod`/`touch`/…
   command, **and** per command whose `tool_input.description` contains a verb of this arm as a word
   (verified under `/bin/bash` 3.2: "Install package dependencies", "Show the install steps", "Copy
   the file then touch base" all match) — the regex scans the whole payload, and bash 3.2 ERE has no
   lookbehind to anchor it to the `"command":` value alone, so a description over-match only
   forwards more (a spawn, never a missed or wrong deny); G-B decides on `tool_input.command`
   alone. Tests: each of `"true\nrm -rf gtm"`, `"true\trm -rf gtm"`, `` `rm -rf gtm` ``,
   `/bin/rm -rf gtm`, `\rm -rf gtm`, `RM -rf gtm`, `perl -pi -e s/a/b/ gtm/state/y`, `sed -E -i
   s/a/b/ y`, `sed -e x -i y` and `perl -0777 -pi -e s/a/b/ y` (cwd `H/.claude/gtm/state`, the
   relative operand `y` carrying no §4.7 token) reaches python and is denied
   `protected-state-write` end to end; and, with arms 1, 2, 2b and 4 removed from the tmp copy so the
   cwd token cannot forward it, arm 3 alone still forwards the three new forms (RED under the former
   arm); `bash -n
   bash_gate.sh` passes; with `python3`, `grep` and `tr` shimmed on `PATH` to record invocations, an
   unrelated `ls -la` payload in a non-GTM session spawns no process beyond the script's existing
   `payload="$(cat)"` (RED when an arm pipes through `grep`/`tr`, and RED when `*.jsonl*` is a
   token) — the payload is the **realistic** one of the "Fixed payload keys" test (every fixed key
   present, including `transcript_path`, `scratchpad_dir` and `session_id`), never a hand-made
   payload with only `tool_input` and `cwd`.
4. **GTM token arm:** `case "$payload" in <tokens>) printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"; exit 0;; esac`
   with the union of §7.2 and §20.13 tokens (**DECIDED HERE:** union — §20.13 amended §7.2's
   mechanism, not its always-on rules (a)–(d1)), plus the relative-path tokens rule (c) needs when
   the Bash cwd is inside `tools/gtm` or a state dir, all lowercase:
`*tools/gtm* | *act.py* | *approver_pubkey* | *lead_fallback* | *.claude/gtm* | *.gtm_state* | *actions.jsonl* |
*activity_log* | *tool_trail.jsonl* | *schedules/disabled* | *repo_tooling/google_ads* | *repo_tooling/meta_ads* |
*graph.facebook.com* | *graph.instagram.com* | *api.linkedin.com* | *youtube* | *googleads.googleapis.com* |
*mybusiness* | *businessprofile* | *wp-json* | *analyticsadmin* | *tagmanager.googleapis* | *searchconsole* |
*webmasters* | *sheets.googleapis* | *osascript* | *screencapture* | *launchctl* | *"security "* | *gtm_approve* |
*gtm_cancel* | *approvals* | *departments/marketing* | *gtm_allow_trust_edit* | *gtm_holds_job* |
*trust_edit_allow* | *operator_ok* | *connectors* | *connector_dispatch* | *google_ads* | *meta_ads* |
*gtm/state* | *gtm/.* | *gtm//* |
*approval_sig* | *approvals_verify* | *gtm_env* | *claude_gtm_* | *site-packages* | *dist-packages* | *.pth* |
*sitecustomize* | *usercustomize* | *.jsonl.ids* | *scoreboard* | *snapshots* | *gtm_missions* | *.playwright-mcp* |
*telemetry/pricing* | *python@3* | *python@3.13* | *cellar* | *homebrew/cellar/python* | *homebrew/opt/python* |
*gtmapprover* | *codesign* | *swiftc*`
(`*gtmapprover*`, `*codesign*`, `*swiftc*` and the three interpreter-path tokens are
`requests/05_approver.md` R58: they make rule g's `agent-approver-binary`/`agent-approver-rebuild`
clauses and rule c's pinned-interpreter clause reachable from a non-GTM session — `codesign --force
--sign - ~/Applications/GTMApprover.app`, a direct `~/Applications/GTMApprover.app/Contents/MacOS/
GTMApprover` exec, `swiftc -o /tmp/GTMApprover main.swift`; `*python@3.13*` and
`*homebrew/cellar/python*` are already covered by `*python@3*`/`*cellar*` and are listed so the R58
parity test can name each. B2 end-to-end tests through the patched `bash_gate.sh` from a non-GTM
session: each of those three commands and `brew upgrade python@3.13` is denied (RED when its token
is removed from the tmp copy). **The state-dir token is `*gtm/state*`, not `*gtm/*`** (DECIDED
HERE, a correction): matched case-insensitively, `*gtm/*` also matched every project-dir name ending
in `gtm` — a session whose cwd is `~/.claude/tools/gtm` has `transcript_path`
`…/projects/-Users-<u>--claude-tools-gtm/<session>.jsonl`, and the planned OtherCompanyB home
`~/Desktop/OtherCompanyB/GTM` gives `…-OtherCompanyB-GTM/` in both `transcript_path` and `scratchpad_dir`
— so every Bash call of those sessions spawned python. `*gtm/state*` still forwards the relative
`gtm/state/…` targets of cwd `H/.claude` (and `GTM/State/…`, nocasematch); `*gtm/.*` and `*gtm//*`
forward the `gtm/./state`, `gtm/../gtm/state` and `gtm//state` spellings of the same target.)
(**No bare `*.jsonl*` token — DECIDED HERE, a correction.** Every real `PreToolUse` payload carries a
top-level `transcript_path` ending in `.jsonl` — verified from captured events in
`~/.claude/.enforcement/workflow_probe.jsonl`, whose `event_keys` are `cwd, effort,
hook_event_name, permission_mode, prompt_id, scratchpad_dir, session_id, tool_input, tool_name,
tool_use_id, transcript_path` — so `*.jsonl*` matched **every** Bash payload on the machine and
started python for every Bash call, breaking this section's no-spawn rule. The machine-written
`*.jsonl` files are reached instead by the specific tokens: `*actions.jsonl*`, `*tool_trail.jsonl*`,
`*.jsonl.ids*` (the sidecar and its `*.jsonl.ids.*.tmp` staging files), `*activity_log*`
(`ACTIVITY_LOG.jsonl` and the `activity_log_dir` files), `*lead_fallback*`, `*gtm_missions*` (every
pack's `paths.missions_dir` is a literal `gtm_missions` leaf — CSA's
`_Config_Project/docs/domain/gtm_missions/`, OtherApp's `plans/gtm_missions/` — chosen, not
`*missions*`, because `harvest_tool_trail._project_dir_name`'s `-`-for-`_`/`/` encoding never
produces the underscore this token requires, so it cannot match a `transcript_path` or
`scratchpad_dir`; see the P2 fixture below), and the state-dir tokens
`*.gtm_state*`/`*.claude/gtm*`/`*gtm/state*`, which match both a
command naming a state path and a payload whose `cwd` is inside one; a pack-configured
machine-written path is covered by R26's validator rule below.)
**Fixed payload keys (binding for every token here, and for `GTM_DESTRUCTIVE_RE`):** a token may
match text in `tool_input.command`, in `tool_input.description` (over-matching there only forwards
more) or in `cwd` (intended: a `cwd` inside `tools/gtm` or a state dir must forward relative
targets), but **no** token may match the text a normal session puts in the other fixed keys —
`transcript_path` (`<HOME>/.claude/projects/<project-dir>/<session>.jsonl`, and for a subagent
`…/<session>/subagents/agent-<id>.jsonl`), `scratchpad_dir` (`/private/tmp/claude-<uid>/<project-dir>/<session>/scratchpad`),
`session_id`, `prompt_id`, `tool_use_id`, `permission_mode`, `effort`, `hook_event_name`, `tool_name`.
B2 P2 test: for a realistic payload built from those keys (every key present; `transcript_path`
and `scratchpad_dir` derived from the project dir exactly as above, subagent form included; a
`tool_input` of `{"command": "ls -la", "description": "List files"}`), run once for **each** of
these session project dirs — the CSA root, `~/.claude`, `~/.claude/tools/gtm`,
`~/Desktop/OtherCompanyB/GTM`, `~/Desktop/OtherCompanyB`, a CSA worktree
(`<CSA>/.claude/worktrees/x`) and `_Config_Project/docs/domain/gtm_missions` under the CSA root —
with the `cwd` key set to a neutral `/tmp/x` so only the fixed keys are tested: no §4.7 token, no
arm-2/2b regex and `GTM_DESTRUCTIVE_RE` matches (RED with `*.jsonl*` or `*gtm/*` restored, RED when
a new token matches one of these fixed keys); the same payload with `cwd` `~/.claude/tools/gtm`
matches `*tools/gtm*` and with `cwd` `H/.claude` plus the command `echo x > gtm/state/y` matches
`*gtm/state*` (intended). **Stated:** a session whose own project-dir name contains another broad
token (e.g. a cwd folder literally named `gtm_missions` or `snapshots`) forwards every Bash call to
python — a cost, never a missed deny; the fixture list above is the set the no-spawn rule is held to.
(`*tools/gtm*` and `*.claude/gtm*` have **no** trailing slash so a payload whose `cwd` ends `tools/gtm"` or `.claude/gtm"` matches — the same defect class fixed for both, I9;
`*activity_log*` covers `ACTIVITY_LOG.jsonl`, `ACTIVITY_LOG.md` and the `activity_log_dir` sidecars;
`*connectors*`, `*connector_dispatch*`, `*google_ads*` and `*meta_ads*` catch rule (a)'s dotted
module forms run from `~/.claude` or the repo root — `python3 -m tools.gtm.connectors.meta.write`,
`python3 -m repo_tooling.google_ads.build_x` — which contain no slash-form token (F-fastpath);
`*gtm/state*` (with `*gtm/.*`, `*gtm//*`) catches relative `gtm/state/…` targets from cwd `H/.claude`;
`*approval_sig*`, `*approvals_verify*`, `*gtm_env*` and `*claude_gtm_*` reach rules l and m (every
rule-l/m form also names `act.py` or `tools/gtm`, or carries the cwd `tools/gtm` in the payload, so
these are belt and braces); the start-up-hook tokens reach rule c's `site-packages`/`*.pth`/
`sitecustomize` class, and `*python@3*`/`*cellar*` its pinned-interpreter class (a write under
`/opt/homebrew/Cellar/python@3.13/…` or `…/opt/python@3.13/…`, `brew … python@3.13`); `*.jsonl.ids*`, `*scoreboard*`, `*snapshots*`, `*gtm_missions*` and
`*.playwright-mcp*` reach the machine-written paths whose location is **pack-configurable**
(`paths.activity_log_dir`, `paths.scoreboard`, …), so a redirect into a relative
`tracking/scoreboard.csv` is forwarded; **stated gap:** a pack path whose text contains none of these
tokens would not be forwarded from a non-GTM session, so company.py's pack validator rejects a
machine-written `paths.*` value whose repo-relative text matches no §4.7 token
(`requests/04_hooks.md` R26), and a P2 test asserts every fixture pack's machine-written paths are
forwarded;
`*"security "*` must be quoted because of the space; gcloud is already covered by the existing
`case`). A P2 parity test asserts every connector manifest's `api_hosts` entry (06_connectors.md
§6.1) is matched by one of these tokens (§4.2 rule b), and a B2 test asserts every
`system_names.RULE_K_LITERALS` member, lowercased, appears as a `*<literal>*` token here (§4.2
rule k). Rule (c) itself resolves relative targets
against the `cd`-tracking candidate bases (payload `cwd` + preceding `cd`s, §4.2). Test: `bash -n bash_gate.sh` passes;
every G-B rule fires end-to-end through `bash_gate.sh`, including `rm act.py` and `>
approver_pubkey.pem` with `cwd` = `~/.claude/tools/gtm` in a **non-GTM** session, `rm -rf state`
with `cwd` = `H/.claude/gtm`, `rm -rf gtm` with `cwd` = `H/.claude`, `mv state x`, a GTM-seat
payload's `ls ~/Desktop/OtherApp` in a non-GTM session, and — each end to end in a **non-GTM**
session — `python3 -m tools.gtm.connectors.meta.write` (cwd `~/.claude`), `python3
~/.claude/Tools/GTM/connectors/meta/write.py` and `python3 -m repo_tooling.google_ads.build_x` (cwd
the CSA repo root) denied `connector-write-outside-act`; `cp forged.json gtm/state/autonomy_state.json`,
`tee gtm/state/x`, `ln -sf x gtm/state/y`, `sed -i s/a/b/ gtm/state/y`, `echo x > gtm/state/y` and
`echo x > GTM/State/y` (cwd `H/.claude`) denied `protected-state-write`; `rm ~/.claude/schedules/DISABLED`
denied; `cd ~/.claude/tools/gtm && rm act.py` (cwd `~`) and `(cd /tmp) && rm act.py` (cwd
`~/.claude/tools/gtm`) denied (§4.2 `base` tracking); `curl -XPOST https://GRAPH.FACEBOOK.COM/x`
denied `api-write-outside-act`; in a **non-GTM** session with no enforce markers,
`CLAUDE_GTM_COMPANY=x python3 ~/.claude/tools/gtm/act.py propose` denied `gtm-identity-forge` and
`PYTHONPATH=/tmp/e python3 approval_sig.py --trust-check` (cwd `~/.claude/tools/gtm`) denied
`gtm-env-override`; `echo 1 >> tracking/scoreboard.csv` (cwd a GTM home) denied
`protected-state-write`; `if true; then rm act.py; fi` (cwd `~/.claude/tools/gtm`) denied.

### 4.8 Exact `settings.json` changes (coordinator applies; not a WP)

Every command keeps the standard prefix `[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; `.

1. `PreToolUse` matcher **`Task` → `Task|Agent`**; command unchanged (`python3
   ~/.claude/hooks/pretooluse_task.py`). Rationale (restated): the existing `Task` matcher already
   fires on payloads whose `tool_name` is `Agent` (documented in `agent_budget.py`); probe i found the
   dispatch tool is named `Agent`, so naming both is defensive and harmless, not a behavior fix.
2. `PostToolUse` matcher **`Task` → `Task|Agent`**; command unchanged (`agent_budget.py release_hook`).
   Same rationale.
3. `PreToolUse` matcher `mcp__playwright.*`: **append** an entry whose full shell command (JSON-escaped
   in `settings.json` exactly as item 5's) is
   ```sh
   [ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; payload=$(cat); if [ -z "${CLAUDE_GTM_COMPANY:-}" ]; then case "$payload" in *'"mcp__playwright-gtm__'*|*'"agent_type"'*'"local-presence-architect"'*|*'"agent_type"'*'"social-media-strategist"'*|*'"agent_type"'*'"measurement-architect"'*|*'"agent_type"'*'"revenue-ops-architect"'*|*'"agent_type"'*'"gtm-analyst"'*|*'"agent_type"'*'"gtm-drafter"'*|*'"agent_type"'*'"gtm-checker"'*|*'"agent_type"'*'"gtm-operator"'*|*'"agent_type"'*'"gtm-credential-setup"'*|*'"agent_type"'*'"marketing-director"'*|*'"agent_type"'*'"conversion-architect"'*|*'"agent_type"'*'"brand-architect"'*|*'"agent_type"'*'"content-strategist"'*|*'"agent_type"'*'"seo-architect"'*|*'"agent_type"'*'"paid-acquisition-strategist"'*|*'"agent_type"'*'"pricing-economist"'*|*'"agent_type"'*'"video-producer"'*|*'"agent_type"'*'"market-analyst"'*|*'__browser_click"'*|*'__browser_type"'*|*'__browser_fill_form"'*|*'__browser_select_option"'*|*'__browser_press_key"'*|*'__browser_check"'*|*'__browser_uncheck"'*|*'__browser_file_upload"'*|*'__browser_handle_dialog"'*|*'__browser_evaluate"'*|*'__browser_run_code"'*|*'__browser_run_code_unsafe"'*|*'__browser_press_sequentially"'*|*'__browser_keydown"'*|*'__browser_keyup"'*|*'__browser_drag"'*|*'__browser_drop"'*|*'__browser_mouse_'*|*'__browser_cookie'*|*'__browser_set_storage'*|*'__browser_localstorage'*|*'__browser_sessionstorage'*) ;; *) exit 0;; esac; fi; printf '%s' "$payload" | python3 ~/.claude/hooks/gtm_browser_gate.py
   ```
   — so G-A spawns python only when `CLAUDE_GTM_COMPANY` is set, the tool is on `playwright-gtm`
   (whose default-deny must run in every session, §4.1), the payload's `agent_type` is a
   `GTM_SEATS` or `DEPARTMENT_SEATS` member (rules 3/3b, `agency_scope`), or the tool is in the
   other-server mutating list (the `gtm-offserver` detect-after, which reads
   `S/identity_index.json`, never git, §4.1 "Other playwright servers"). A snapshot, screenshot or
   navigate on `playwright-NN` in an ordinary CSA session spawns nothing. POSIX `case` globs only
   (no `grep`, no `[[ =~ ]]`: hook commands may run under `sh`). Tests (B1): run it with `sh -c` and
   `bash -c`, `python3` and `grep` shimmed — a non-GTM `mcp__playwright-03__browser_snapshot`
   payload spawns nothing; a `mcp__playwright-gtm__browser_snapshot` payload, a
   `mcp__playwright-03__browser_click` payload and a `marketing-director` `browser_navigate` payload
   each spawn python once, and so does a `mcp__playwright-03__browser_drag` payload; P2 parity tests
   assert the seat globs equal `system_names.GTM_SEATS ∪ DEPARTMENT_SEATS`, and that the tool
   globs of this command are exactly `gtm_hooklib.OFFSERVER_MUTATING` (§4.1 "Other playwright
   servers": one `*'__<name>"'*` glob per `OFFSERVER_MUTATING_NAMES` entry and one `*'__<prefix>'*`
   glob per `OFFSERVER_MUTATING_GLOBS` entry, no more, no fewer), and that for every name in the
   vendored `playwright_mcp_tools.txt` (§4.1) the shell globs match it **iff**
   `OFFSERVER_MUTATING` does (so `browser_drag`/`browser_drop` are in both and `browser_hover`,
   `browser_pdf_save`, `browser_verify_*` in neither; RED when a name is added to one side only).
4. New `PreToolUse` matcher `Write|Edit|MultiEdit|NotebookEdit`: `python3 ~/.claude/hooks/gtm_state_write_gate.py`.
   Registered only after WP-G's `mission_record.py` and WP-I's `MISSION_SCHEMA.md`/director update
   have landed (03_schemas.md §3.19), so `/gtm` missions never lose their writer. The coordinator
   applies it in the same post-Wave-2 step as the G-B activation train (§4.2, IMP-04).
5. New `PreToolUse` matcher `Read|Grep|Glob|Edit|MultiEdit|Write|NotebookEdit|WebFetch`. The
   exact `"command"` value in `settings.json` (JSON-escaped, prefix included; I11):
   ```json
   "[ \"${CSA_DISABLE_HOOKS:-0}\" = \"1\" ] && exit 0; payload=$(cat); if [ -z \"${CLAUDE_GTM_COMPANY:-}\" ]; then case \"$payload\" in *'\"agent_type\"'*'\"local-presence-architect\"'*|*'\"agent_type\"'*'\"social-media-strategist\"'*|*'\"agent_type\"'*'\"measurement-architect\"'*|*'\"agent_type\"'*'\"revenue-ops-architect\"'*|*'\"agent_type\"'*'\"gtm-analyst\"'*|*'\"agent_type\"'*'\"gtm-drafter\"'*|*'\"agent_type\"'*'\"gtm-checker\"'*|*'\"agent_type\"'*'\"gtm-operator\"'*|*'\"agent_type\"'*'\"gtm-credential-setup\"'*|*'\"agent_type\"'*'\"marketing-director\"'*|*'\"agent_type\"'*'\"conversion-architect\"'*|*'\"agent_type\"'*'\"brand-architect\"'*|*'\"agent_type\"'*'\"content-strategist\"'*|*'\"agent_type\"'*'\"seo-architect\"'*|*'\"agent_type\"'*'\"paid-acquisition-strategist\"'*|*'\"agent_type\"'*'\"pricing-economist\"'*|*'\"agent_type\"'*'\"video-producer\"'*|*'\"agent_type\"'*'\"market-analyst\"'*) ;; *) exit 0;; esac; fi; printf '%s' \"$payload\" | python3 ~/.claude/hooks/gtm_phi_path_gate.py"
   ```
   The seat test is a POSIX `case` glob per seat (`*'"agent_type"'*'"<seat>"'*`), so the shell
   fast path spawns **no** process beyond `cat` (hook commands may run under `sh`, so no `[[ =~ ]]`
   and no `grep`, §4.7 cost rule). The glob is looser than the former regex (the seat string may
   appear anywhere after an `"agent_type"` key), which can only forward more, never less. The glob
   list is the 9 `GTM_SEATS` **followed by the 9 `DEPARTMENT_SEATS`** (Agency scope, §4.4 rule 1;
   00_global_paths.md §0.4). Exits in shell only when the env arm and both seat arms are absent.
   Test (B2): load the post-change
   `settings.json`, take this entry's command, run it with `sh -c` **and** `bash -c` on a non-GTM,
   non-seat `Read` payload with `python3` and `grep` shimmed on `PATH` to record invocations —
   expect exit 0 and **no** python or grep spawn; with a `gtm-analyst` payload — expect one python
   spawn; with a `marketing-director` payload — expect one python spawn (RED when the department
   globs are removed); a P2 test asserts the inlined seat list equals `system_names.GTM_SEATS` ∪
   `system_names.DEPARTMENT_SEATS`, in that order.
6. `SubagentStop` (no matcher): **append** a second entry whose full command is
   `[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; payload=$(cat); case "$payload" in *gtm-result*) ;; *) [ -z "${CLAUDE_GTM_COMPANY:-}" ] && exit 0;; esac; printf '%s' "$payload" | python3 ~/.claude/hooks/gtm_ticket_release.py`
   (FID-08: non-GTM sessions still reach python when the payload carries a result fence, §4.5; a
   POSIX `case` glob, so a non-GTM SubagentStop spawns no `grep` — the item-5 cost rule).
   Test (B1): run with `sh -c` and `bash -c`, `python3` **and `grep`** shimmed — a non-GTM payload
   without `gtm-result` spawns nothing (RED with the former `grep -q` form); a non-GTM payload with
   a fence spawns python once; a GTM-session payload without a fence spawns python once.
7. New `PostToolUseFailure` matcher `Task|Agent` (§4.6 "Admissions that never run"), full command
   `[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; [ -z "${CLAUDE_GTM_COMPANY:-}" ] && exit 0; python3 ~/.claude/hooks/agent_budget.py release_failure`
   (admission rows exist only for dispatches made inside a GTM session). Whether this event fires
   for Agent/Task is UNVERIFIED; the coordinator records a probe (a deliberately failing Agent call
   in a scratch session) in plan §17 before relying on it.

8. New `PostToolUse` matcher `mcp__playwright-gtm__.*` (§4.1 "Page-URL refresh"), full command
   `[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; [ -z "${CLAUDE_GTM_COMPANY:-}" ] && exit 0; python3 ~/.claude/hooks/gtm_browser_gate.py post`
   (`playwright-gtm` is used only inside GTM sessions; rule 1 denies it elsewhere). Test (B1): run
   with `bash -c` and `python3` shimmed — a payload with `CLAUDE_GTM_COMPANY` unset spawns nothing.

**Registration timing (every item).** `hooks/tests/test_check_safety_core_parity.py::
test_real_runtime_has_no_guard_wiring_problems` runs `check()` against the live hooks directory and
the live `settings.json` and fails on any on-disk module containing `_lib.emit_pretooluse_deny(` that
settings does not reach, so no module may sit on disk unregistered between commits:
- items 1 and 2: behaviour-neutral; any time, at the latest in the Appendix C item 19 step that
  applies B2's `pretooluse_task.py` patch (§4.6).
- items 3 (G-A) and 5 (path gate), and item 8 (G-A's PostToolUse entry, same module): applied by
  the coordinator **in the same change that lands the module** (B1's train). Both are inert for
  existing work except where 00_global_paths.md §0.4 decided otherwise: G-A denies only on
  `playwright-gtm`, in GTM scope, or for rule 3b under `agency_scope` (a department seat outside
  Agency navigating to an Agency URL), and on any other server outside those scopes it allows even
  on an internal error (§4.1); item 3's prefix spawns python for other servers' mutating calls only
  (detect-after, never a deny); item 5's shell prefix exits unless the env arm or a GTM or
  department seat arm is present, and for a department seat outside GTM scope only rule 1 can deny.
- **Money-host activation precondition (G-A rule 6c; `requests/04_hooks.md` R22, R35).** Item 3
  may land before the operator's R22 ruling — G-A is `playwright-gtm`'s default-deny and must not be
  held back — because rule 6c denies every mutating write/batch-ticketed call on a `money_hosts()`
  host until the committed `tools/gtm/activation.json` is an operator-signed activation record
  naming the ruling id (`activation_state`, §4). The coordinator's checklist line for
  08_seats_wps.md Appendix C item 19: "Before committing `tools/gtm/activation.json`: the plan §20.x
  amendment for the browser `$` residual and the NEVER/identity click residual (04_hooks.md §4.1,
rules 6c and 7c) and its Appendix B entry are recorded
  with the operator's verbatim ruling and its id; the file is the record the operator's own
  `gtm_approve.sh activation <ruling_id>` (Touch ID) produced — never hand-written, never produced by
  an agent — and `activation_state()` run against the staged commit's key verifies it; the commit is
  HIGH-tier reviewed; until then, money-host write tickets stay refused at mint (02, R35/R45) and at
  G-A (rule 6c)." (`requests/04_hooks.md` R45 replaces R35's checklist line with this one.)
- item 6: with its module (`gtm_ticket_release.py`, B1); item 7: in the Appendix C item 19 step,
  in the same change that applies `b2_task_wiring.patch` (which adds `agent_budget.py
  release_failure`, §4.6). Neither ever denies; item 7 exits in shell outside a GTM session, and
  item 6 exits in shell unless the payload carries a GTM session or a `gtm-result` fence (§4.5).
- item 4 (G-W): its module lands in Wave 2 but its registration waits for `mission_record.py` (above),
  so B1 adds `gtm_state_write_gate` to `check_safety_core_parity.STANDALONE_GUARD_MODULES` with the
  documented reason "registration deferred to the GTM activation train (04_hooks.md §4.8 item 4)";
  the activation train removes that entry **in the same change** as item 4's registration, and a
  B2 test run in that train asserts no `gtm_*` module remains in `STANDALONE_GUARD_MODULES`
  (falsified by leaving the entry).
- `gtm_bash_gate.py` and `gtm_task_gate.py` never call `emit_pretooluse_deny` (their callers,
  `pretooluse_bash.py` and `pretooluse_task.apply_t1b`, emit), and `gtm_hooklib.py` and
  `gtm_import.py` are libraries; a B1 test asserts none of the four contains
  `emit_pretooluse_deny(`, so none needs an entry.
- §4.10 edits the already-registered `workflow_model_gate.py`; no settings change.

`Bash` stays on `bash_gate.sh` (G-B rides `pretooluse_bash.py`). `check_safety_core_parity.py`
already derives reachability from settings + imports; WP-B2 adds a test asserting `check()` reports
zero problems for the post-change settings above with exactly these **six** new hook modules on
disk — `gtm_browser_gate.py`, `gtm_bash_gate.py`, `gtm_state_write_gate.py`, `gtm_phi_path_gate.py`,
`gtm_ticket_release.py`, `gtm_task_gate.py` — and adds `gtm_hooklib.py` and `gtm_import.py`
nowhere (they are libraries, not guards).

### 4.9 Other existing-hook edits (WP-B2)

- `block_prod_mutations.py` R5: state key for server `playwright-gtm` becomes
  `f"playwright-gtm@{session_id}"` (payload `session_id`); every other slot keeps its bare name.
  `record_navigate_host(slot, url, session_id=None)`, `clear_slot_host(slot, session_id=None)`, and
  `r5_decision(tool_name, slot_hosts, allowlist, now=None, session_id=None)` gain the optional
  parameter, and so do their real callers: `decide_event(ev, allowlist, slot_hosts)` passes
  `session_id=_lib.session_id(ev)` to `r5_decision`, and `_main_impl(ev)` (the caller that records and clears slot hosts; `main()`
  only reads stdin and calls it) passes the same value to
  `record_navigate_host`/`clear_slot_host` (it is `None` — the bare slot key — for every server
  other than `playwright-gtm`). Test: two concurrent sessions on `playwright-gtm` do not see each
  other's host (RED when `decide_event` or `_main_impl` drops `session_id`).
  **R5's deny policy is unchanged for `playwright-gtm` (IMP-07; DECIDED HERE).** R5 denies
  interaction tools (`browser_click/type/fill_form/…`) whenever the slot's recorded host is in
  `live-testing/allowlist.json`'s `read_only_hosts`, which lists `example.com`,
  `app.example.com`, `otherapp.example`, `app.otherapp.example` and their API/admin hosts — two
  GTM companies' own sites. `playwright-gtm` gets **no** exemption: plan §7.1 rules out a bypass of
  the existing hooks, those hosts carry live beta testers (CSA CLAUDE.md "never break production";
  production is touched only on explicit operator instruction), `app.*` is a shared system under
  plan §20.2 (a card, never autonomous), and CSA/OtherApp website changes go through the repo
  (`website_static`), never the browser. So **GTM browser clicks and writes on any
  `read_only_hosts` entry are out of scope**: on those hosts GTM seats use only ticketless reads
  (`browser_navigate` — which R5 never denies — plus `browser_snapshot`/`browser_take_screenshot`,
  which R5 does not class as interaction). Widening this later is a trust-architect-reviewed edit
  to `allowlist.json` (plan §7.1), never a code exemption. B2 tests against the real
  `block_prod_mutations.py` with a `playwright-gtm` payload and a valid G-A read ticket: after a
  navigate to `https://example.com/pricing`, `browser_click` is **denied** by R5 (the
  intended behavior; falsified by exempting `playwright-gtm`) while `browser_snapshot` is allowed;
  after a navigate to `https://business.google.com/`, `browser_click` is allowed by R5 (probe g).
- `agent_budget.py`: 03_schemas.md §3.13 (claim copy **and** the transcript-tag fallback on every spend-line
  builder, using `tools/gtm/system_names.py` for `TAG_RE` and `seat_sets()`); `apply_decision`/
  `_apply_pacer_gate`'s keyword-only `outcome` (§4.6 "How `pretooluse_task.py` learns that T2
  denied", IMP-06); the new `release_failure` subcommand (§4.6, §4.8 item 7). **`system_names` is
  imported lazily, inside the spend-line builder's own `try`, never at module top level, under §4's
  hook import rule** (`gtm_import.load("system_names", __file__)`: the unresolved code root served by
  the meta-path finder, `sys.path` untouched, never `R/tools/gtm`; `sys.dont_write_bytecode = True`;
  `sys.pycache_prefix = NO_PYCACHE`;
  `agent_budget` keeps resolving its own ledger root as today, and every GTM state path comes from
  `company.claude_dir()` at call time): on any
  import or call failure the line is written without a `gtm` field and `gate-fault` is logged, so a
  broken GTM module can never crash `agent_budget.py` on load and take T2 (the pacer) and the spend
  ledger down machine-wide. B2 tests: with `system_names` unimportable, `agent_budget.py gate` still
  admits/denies as today and `release_hook` still writes a spend line (without `gtm`); with
  `gtm_task_gate` unimportable, `pretooluse_task.main` still runs T1 and T2 and a claim is recorded
  (§4.6 F-t1b).
- `workflow_model_gate.py`: the two GTM checks of §4.10.
- `review_risk_tier.py` `_HIGH_RISK_KEYWORDS` += `"tools/gtm/act.py"`, `"tools/gtm/gtmlib/"`,
  `"tools/gtm/connectors/"`, `"tools/gtm/approver"`, `"approver_pubkey"`, `"tools/gtm/tier_table.json"`,
  `"tools/gtm/review_lanes.json"`, `"tools/gtm/secret_sink"`, `"tools/gtm/setup_scripts/"`,
  `"tools/gtm/mcp_launch/"`, `"tools/gtm/system_names"`, `"tools/gtm/approval_sig"`,
  `"tools/gtm/ai_budget"`, `"tools/gtm/gtm_lists"`, `"tools/gtm/gtm_pricing"`, `"tools/gtm/company.py"`,
  `"tools/gtm/project_dirs"`, `"tools/gtm/dispatch_tags"`, `"tools/gtm/gtm_env"`, `"tools/gtm/activation.json"`,
  `"telemetry/pricing.json"`, `"scripts/gtm_"`, `"gtm_session"`
  (`gtm_pricing`, `company.py` and `telemetry/pricing.json` joined `TRUST_PATHS`, 05_approver.md
  §5.5, and `project_dirs` decides spend attribution, §4.6, so their commits get full review too).
  **Redundancy, deliberate:** `"gtm_session"`, `"tools/gtm/gtm_pricing"` and
  `"telemetry/pricing.json"` are already matched by the existing `session`/`pricing` keywords; they
  are listed anyway so a future narrowing of those broad keywords cannot silently drop a GTM trust
  path to a lower tier (a test asserts each listed keyword classifies HIGH on its own).
- `pretooluse_task.py`: T1b wiring via `apply_t1b` with the pre-import short-circuit, the isolated
  trust-check and `ai_budget.py state` subprocesses and a lazy `gtm_task_gate` import after them
  (§4.6 F-trust, F-t1b), including `dispatch_tags.release_admission(tool_use_id, "t2_deny")` when
  `apply_t2` reports a deny for a dispatch T1b appended a row for (§4.6 "Admissions that never run"
  and "How `pretooluse_task.py` learns that T2 denied");
  `pretooluse_bash.py`: G-B wiring (§4.2) **and the §0.4 unconditional-deny mechanism**
  (00_global_paths.md §0.4, `requests/00_global_paths.md` R20): `_Block.__slots__` gains
  `"unconditional"` and `"shadowed_block"` (the latter set only by the §4.2 shadowing rule,
  `None` by default, logged by `_finish` when set); `_Block.__init__(self, hook, reason, message, *, git_state: bool,
  unconditional: bool = False)` — `git_state` stays keyword-only and required, as today — stores it
  (every existing call site is unchanged and keeps `False`); `_finish`
  computes `enforce = enforcing(where) or block.unconditional`, emits the deny when `enforce`, and
  logs `enforce=<that value>`. Existing tests pass unchanged (`hooks/tests/test_pretooluse_bash*.py`,
  `test_check_safety_core_parity.py`); new B2 test: a `_Block(..., unconditional=True)` returned by
  a stub gate is emitted with no enforce marker present, and one with the default `False` is only
  logged (RED when `_finish` ignores the field). **Neither live file is edited during Wave 2:** the
  `pretooluse_task.py` and `agent_budget.py` edits above ship in `b2_task_wiring.patch` (§4.6
  "Delivery"), the `pretooluse_bash.py` and `bash_gate.sh` edits in `b2_gb_wiring.patch` (§4.2,
  IMP-04); the coordinator applies both in the 08_seats_wps.md Appendix C item 19 step.

### 4.10 Workflow GTM-seat gate — extends `hooks/workflow_model_gate.py` (WP-B2)

A GTM seat dispatched through a `Workflow` script's `agent()` never reaches PreToolUse:Task, so it
skips everything in §4.6; 08_seats_wps.md §8 item 6 ("never dispatch GTM seats inside a `Workflow`")
was prose only. `workflow_model_gate.py` (already registered on the `Workflow` tool) gains two
checks. **Placement (binding):** check 1 runs **immediately after** the `CSA_DISABLE_HOOKS` test and
**before** any payload parsing, `script`/`scriptPath` loading or other early return of `main()`
(today `main()` returns 0 on a JSON parse failure, a missing `script`, or an unreadable
`scriptPath`); it needs only the environment and, for the seat arm, the payload's top-level
`agent_type`. **Order within check 1 (binding):** the env arm (`CLAUDE_GTM_COMPANY` set) is
evaluated **first, before any parsing** — set → deny `gtm-no-workflow` whatever the payload is (a
payload whose JSON does not parse included). Only when the env arm is unset is the payload parsed
for the seat arm; if it does not parse, the seat arm is **unknown** and the call is **allowed**
with `gate-fault` logged (outside the env arm this gate follows the non-GTM fail-open posture, and
the existing model check's own parse-failure return then applies). A Workflow call in GTM scope
whose `scriptPath` does not exist is denied `gtm-no-workflow`. B2 tests (each RED when its clause
is reordered): with `CLAUDE_GTM_COMPANY` set, a non-JSON payload is denied `gtm-no-workflow`; with
it unset, a non-JSON payload is allowed and logs `gate-fault`; with it unset and a parseable payload
whose `agent_type` is `gtm-operator`, the call is denied `gtm-no-workflow`. The two checks, each
with its own placement (the order between them is the placement, not a "first match" rule):
- **Check 1 (pre-parse; placement above) — GTM scope** (`CLAUDE_GTM_COMPANY` set in the hook's
  environment, or payload `agent_type ∈ GTM_SEATS`): deny every `Workflow` call (`gtm-no-workflow`)
  — GTM sessions dispatch seats only by direct top-level `Agent` calls. It runs before any
  `script`/`scriptPath` loading, so a GTM-scope call is never judged by check 2.
- **Check 2 (post-load) — all sessions:** runs after the script source is loaded, before the
  existing model-named check, on the same source it already reads: deny (`gtm-seat-in-workflow`)
  when any `agent()` site returned by
  `check_workflow_agent_purity.find_agent_call_sites()` names an agent type in `seat_sets()`'s
  GTM_SEATS, **or** when any GTM_SEATS name appears anywhere in the script as a complete quoted
  string literal (`'gtm-operator'`, `"gtm-operator"`, `` `gtm-operator` ``) — which also catches a
  non-literal options object (`agent(opts)`, `agent({...base})`) whose agent type was set elsewhere
  in the script. An agent type assembled from non-literal pieces is not caught (accepted, stated;
  gate-gtm step 0 cannot help there either).
Imports: `system_names` (for `seat_sets`) lazily inside a `try`, through §4's hook import rule (`gtm_import.load("system_names", __file__)`). Enforcement: check 1 denies
unconditionally (00_global_paths.md §0.4 GTM scope); check 2 follows `_lib.enforcing` like every
other GTM rule outside GTM scope. Fail mode for the two new checks: an exception denies `gate-fault`
in GTM scope and otherwise allows + logs `gate-fault`; the existing model check keeps its own
fail-open posture; `CSA_DISABLE_HOOKS=1` allows before parsing. Tests (B2), each falsified by
removing its check: a Workflow call from a GTM session is denied; from a non-GTM session, a script
with `agent(p, {agentType: 'gtm-operator', model: 'sonnet'})` is denied, one with `const o =
{agentType: "gtm-analyst", model: "sonnet"}; agent(p, o)` is denied, and one dispatching only
`implement` is allowed; a GTM-scope Workflow call whose `scriptPath` does not exist is denied
(RED when check 1 runs after the early returns) and a payload that is not valid JSON is denied
`gtm-no-workflow` when `CLAUDE_GTM_COMPANY` is set and allowed + `gate-fault` logged when it is not; the existing `workflow_model_gate` tests pass unchanged.
