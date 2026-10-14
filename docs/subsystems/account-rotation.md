# Account Rotation

*Summary/orienting doc for `~/.claude/account_rotation/`. This file is mirrored — it carries no
email addresses or account aliases; every account is referred to only by its LABEL (`1`-`5`, `I`).*

## What this is

A tool that switches Claude Code between the operator's own paid accounts as each one approaches its
usage limit or subscription end date, so the operator never has to switch by hand or sit idle waiting
for a reset. **This is opt-in, not automatic by default** — see the `check` section below for exactly
what gates it. Full build spec: `~/.claude/plans/account_rotation_2026_09_24.md` (read the **v5.1**,
then **v5 BUILD SPEC FIXES**, then **v4 SCOPE DECISION** sections first — later sections win on any
conflict with earlier ones, exactly as the plan states its own precedence).

**Current status: PHASE 1, `threshold_only` strategy, and `switch`/`verify` are REAL — they drive a
real headed Chrome and a real `claude auth login`.** This is not a stub: `rotate.py switch [--to
LABEL]` runs the full switch flow end to end (sign-out/sign-in, Gmail magic-link lookup, billing
classification, live eligibility, then the CLI login step against the resolved `claude` binary), and
`rotate.py verify LABEL` drives a real web-only magic-link sign-in to read the billing page. Neither
has yet been run for real against a live account — that happens in the operator's attended first run
— but the code path is live, not a placeholder. The plan's phase-2 machinery (`use_it_or_lose_it`,
`drain_expiring_first`, automated verify/lapse loops, the anchoring measurement, a `SessionStart`
alert hook) is still designed-but-inert (e.g. `burn.py`'s gain formula computes correctly but nothing
calls it) — none of it is wired into any command's default path.

**`check` (the unattended interval job) only switches when the operator has explicitly enabled it,
and defaults OFF.** It reads live usage, updates state, detects external switches, and evaluates the
STAY rule; when a hard trigger fires, what happens next depends on accounts.json's
`unattended_switch_enabled` flag (operator-owned, absent/`false` by default).

**[#5017 B2/M-b] Switching is enabled ONLY by the literal JSON boolean `true`.** The check is
`accounts_doc.get("unattended_switch_enabled") is True` — an `is` identity check against the
Python singleton `json.loads()` produces for a genuine `"unattended_switch_enabled": true`, never a
`bool(...)` truthiness check. Every other value — the key being ABSENT, `false`, the STRING `"true"`
or `"false"` or `"no"` (a config typo, e.g. quoting the value), the integer `1` or `0`, `null` — means
OFF. This matters because `bool()` would treat the string `"false"` as truthy: a quoting mistake in
accounts.json must never silently arm unattended switching.

- **Flag absent, `false`, or any non-`true` value (the default, and every fresh install's state):**
  `check` only raises an alert (`hard_trigger_switch_needed`) and returns 0 — it never opens a
  browser. This is the ONLY behavior until the operator explicitly sets the flag to the literal
  boolean `true`.
- **Flag `true` (and ONLY the literal boolean `true`):** `check` invokes a REAL `switch` (the same
  `_switch_impl` machinery `rotate.py switch` itself uses — auto-selecting the target, never a
  separate implementation)
  immediately after its own `check` pass finishes and its own `state.lock` hold has released (the
  switch takes its own lock on the same file; nesting the two would deadlock the flock, in-process).
  `check`'s own exit code and heartbeat then reflect the SWITCH attempt's outcome, not just "a switch
  is due" — a switch failure (exit 6/7/8/9) is `check`'s own outcome for that invocation.

**Setting `unattended_switch_enabled: true` is an operator action, never something this tool sets for
itself, and it should be set ONLY once the plan's A4 acceptance criterion has actually passed** — "the
first LIVE switch is watched by the operator... launchd is loaded only after A1-A3 pass and that
watched switch succeeds." Every OTHER precondition the plan names for check-to-switch (the circuit
breaker, `browser_held`, `schedules/DISABLED`, and `check`'s own `state.lock`) is enforced regardless
of this flag, before the hard-trigger branch is ever reached — the flag is additive on top of those,
never a replacement for any of them. Driving the browser automatically from a 120-second unattended
loop, before the operator has watched it succeed even once, is exactly the risk the plan's "first
switch is attended" rule guards against — this flag exists so that risk is closed by an explicit,
recorded operator decision, not by code alone.

## Layout

- **Code (tracked)**: `~/.claude/account_rotation/rotate.py` plus its sibling modules
  (`resolver.py`, `stay.py`, `state_store.py`, `burn.py`, `credential.py`, `usage.py`, `alerts.py`,
  `browser.py`, `page_driver.py`, `page_selectors.py`, `cli_login.py`, `probe_step0.py`, `seed.py`,
  `heartbeat.py`, `orchestrator.py`, `logging_utils.py`) and `~/.claude/account_rotation/tests/`.
  Re-included in `.gitignore` following the `telemetry/` precedent — this directory is NOT part of
  the mirror include list, so it is runtime-local only.
- **Operator data (untracked, 0600)**: `accounts.json` (operator-owned; the tool never writes an
  email anywhere else) and `state.json`, plus `rotation.log` (rotated at 1&nbsp;MB, 3 kept) and
  `alerts.jsonl`. All four are created/rewritten with explicit 0600 permissions. None of these are
  committed.
- **Browser profile**: `~/Library/Application Support/claude-rotation/profile/`, 0700, outside
  `~/.claude` entirely — the persistent Chrome profile `switch`/`verify` launch into (real Chrome
  channel, `--disable-features=FedCm,FedCmIdpSigninStatus`), holding the signed-in Gmail session the
  Gmail-lookup step (c) reads from. **[Important 5, #5017 — risk this profile carries:** the profile
  is protected from Playwright's own tooling only by `--use-mock-keychain` (a fixed, non-secret,
  non-operator-controlled per-machine key, never rotated) — it holds the live Gmail session for the
  magic-link inbox used by EVERY account this tool switches into, so anything that can read this
  directory's files can potentially replay that session. Run `rotate.py protect-profile` once at
  install time (idempotent; safe to re-run any time to re-verify) to `tmutil addexclusion` it from
  Time Machine, closing the specific exposure of that session cookie ending up in an unencrypted or
  improperly-secured backup. This does not protect against local-account or root-level filesystem
  access to the live profile itself — only against it leaving the machine via a Time Machine backup.**

## Commands (`rotate.py`)

`status` · `plan` · `check [--dry-run]` · `switch [--to LABEL] [--config-dir DIR] [--attended]` ·
`verify LABEL [--config-dir DIR]` · `record-date LABEL --renews|--ends DATE [--source ...]` ·
`enable LABEL` · `clear-circuit` · `release-browser` · `protect-profile [--profile-dir DIR]` ·
`alerts [--ack ID|--all|--session-start]` · `seed --from-snapshot` ·
`probe-step0 --step {0.1,0.2a,0.3,b1}` (attended-run-only measurement probes — never called
automatically, never called by any test).

### `protect-profile` — Time Machine exclusion for the browser profile [Important 5, #5017]

`rotate.py protect-profile [--profile-dir DIR]` runs `tmutil addexclusion` against the persistent
browser profile directory (default: `_default_profile_dir()`, the same path `switch`/`verify` use).
**Idempotent**: it checks the current state via `tmutil isexcluded` first, and skips `addexclusion`
entirely when the profile is already excluded (running it repeatedly — at install time, or any time
later to re-verify — is always safe and cheap). Refuses (exit 1) if the profile directory does not
exist yet (no `switch`/`verify` has run there), or if `tmutil` itself fails, times out
([#5017 M4] a `subprocess.TimeoutExpired` — NOT an `OSError` subclass, so it needed its own handler
alongside the pre-existing `OSError` catch — from the real runner's own 15s timeout), or is
unavailable. Never touches `state.json`/`accounts.json`/`state.lock` — this is a
machine/filesystem-level operation, entirely orthogonal to this tool's own operational state. This
step is NOT run automatically by `switch`/`verify`/`check`; it is the operator's own install-time (or
any-time-later) action — run it once after the profile directory first exists, and optionally again
any time to re-verify.

**Plainly: the mock keychain used in this build's Playwright launch (`--use-mock-keychain`) means the
browser profile's cookies are effectively stored in PLAINTEXT on disk** — it is a fixed,
non-secret, per-machine key, never rotated or operator-controlled, so it provides no real
confidentiality against anyone with filesystem access to the profile directory. `protect-profile`'s
Time Machine exclusion is the mitigation for the ONE exposure vector it can actually close (the
session cookie ending up in an unencrypted or improperly-secured backup) — it does **not** make the
live, on-disk profile itself confidential. **If the profile directory is ever deleted and
recreated** (a fresh `switch`/`verify` run against a wiped profile, a manual `rm -rf` recovery, a
migration to a new profile path), `protect-profile` must be RE-RUN — the Time Machine exclusion is a
property of the specific directory `tmutil addexclusion` was pointed at, not of "the account-rotation
tool" in the abstract, and a freshly-created directory starts with no exclusion at all until this
command runs against it again.

Every subcommand that touches state accepts `--config-dir`. It always serves purpose (a) below;
purpose (b) — binding the flag to `CLAUDE_CONFIG_DIR` for a real `claude` child process — is
**switch- and verify-only**, corrected here per the round-2 review (an earlier version of this
paragraph claimed it applied to "every subcommand," which was never true for `check` or the
`probe-step0` probes):

- (a) account_rotation's own base directory (where that invocation's
  `accounts.json`/`state.json`/`rotation.log`/`alerts.jsonl` live — this is how the test suite
  isolates itself from the real `~/.claude/account_rotation/`). **Every** subcommand's `--config-dir`
  does this, `check` included.
- (b) the `CLAUDE_CONFIG_DIR` a sandboxed run targets for the `claude` CLI child process and every
  `auth status` read. **Only `switch` and `verify` bind `--config-dir` to `CLAUDE_CONFIG_DIR`** (via
  `credential.ConfigDirBoundAuthStatusReader`, and `cli_login.run_cli_login`'s own `config_dir`
  parameter). `check`'s `--config-dir` is base-directory-only — its `auth_reader.read()` call
  (`rotate.py`'s `_run_check`) always targets the LIVE `claude auth status`, regardless of
  `--config-dir`; there is no sandboxed `check`. `probe-step0`'s functions take an explicit
  `sandbox_config_dir` PARAMETER of their own (not `rotate.py`'s `--config-dir` flag) and pass it
  directly to each `RealAuthStatusReader(...).read(config_dir=...)` call they make.

A `switch --config-dir <sandbox>` REFUSES outright if `<sandbox>` resolves (after following symlinks
and `..`) to the live default (`~/.claude`) — the sandbox isolation is enforced, not just documented.
`verify --config-dir <sandbox>` refuses the same way.

### Exit codes (v5.1, final — supersedes earlier plan sections' numbering)

| code | meaning |
|---|---|
| 0 | ok (no-op / clean check / record-date) |
| 2 | usage unreadable |
| 3 | none eligible |
| 4 | locked or held |
| 5 | circuit open |
| 6 | switch failed, old credential intact (includes a successful rollback) |
| 7 | rollback failed, or its outcome couldn't be confirmed live |
| 8 | binary guard refused |
| 9 | attended timeout / refusal without `--attended` |
| 10 | switched |
| 11 | verified (renews/ends) |
| 12 | verified no_active_plan |
| 13 | verify's own unreadable result (failed, counts toward the circuit breaker) — also verify's own uncaught-exception exit code |
| 14 | unknown/unresolvable active identity (failed, alert) |

Heartbeat status is `"ok"` for `{0, 2, 3, 4, 10, 11, 12}` and `"failed"` for everything else,
including exit 13 (which still counts toward the breaker despite mapping from `verify`, not
`check`).

**Exit 14 covers two DISTINCT conditions, with two distinct alert kinds, per [Minor, #5017]:** a
genuinely unreadable `claude auth status` read (the read itself failed) raises
`auth_status_unreadable` (message: `"could not read \`claude auth status\` for the active
account"`), while a readable status whose email just isn't in `accounts.json` raises
`unknown_active_email` (message: `"active account email not in accounts.json"`). Both exit 14 —
there is no behavior change to the exit code itself — but collapsing them into one alert kind
misled whoever read the alert into troubleshooting the wrong thing (checking `accounts.json` for a
missing entry when the actual problem was the CLI/auth-status read itself failing, or vice versa).
The same split applies during `switch` (message prefixed `"switch: "`), not just `check`.

## Design points worth knowing before touching this code

- **One date resolver.** `resolver.resolve_effective_record()` is the single place that decides
  whether a label's `(renews_at, sub_end_at, disabled_reason)` comes from `state.json`'s latest
  VERIFIED tuple (taken whole, explicit nulls included) or falls back to `accounts.json`'s
  operator-provided (conservative, unverified) values. It also normalizes both possible on-disk date
  shapes to an epoch float — `accounts.json` stores ISO-8601 strings, `state.json` stores UTC epoch
  seconds — so every downstream eligibility/staleness function only ever sees a float.
- **STAY leaves on BOTH verified and unverified end dates; only ELIGIBILITY has the verified-only
  carve-out.** `stay.should_leave_active()` fires a hard trigger at (end date − margin) regardless of
  whether that date came from a verified billing-page read or the operator's own conservative
  estimate in `accounts.json` — per the v4 scope decision. `resolver.is_eligible()`'s own sub-end
  check is the ONLY place an unverified date is ignored (an account past its unverified date stays a
  valid switch TARGET — "due for verify" — rather than being excluded).
- **Percentages go stale and become "unknown" (eligible), not "0%."** A stored weekly/session
  percentage is dropped once its own reset time passes, or — when the reset time is itself null —
  once the observation is older than 7 days (weekly) or 5 hours (session).
- **A scale-ambiguous or out-of-range usage reading invalidates the WHOLE response, never one
  field.** The live binary's own `utilization` field is a 0-1 fraction internally; the endpoint's
  `used_percentage` field is always 0-100. `usage.parse_usage_response()` runs a RESPONSE-WIDE vote
  over the four scale-relevant windows (`five_hour`/session, `seven_day`/weekly, `seven_day_sonnet`,
  `seven_day_opus` — `extra_usage` is excluded from this vote, though its own `> 100`/`< 0` check
  still applies): collect every non-null `utilization`-sourced value, EXCLUDE any that are exactly
  `0` (a `0` reads identically on either scale, so it is never treated as evidence either way, in
  either direction), and if what remains is non-empty and every one of those values lands in
  `(0, 1]`, the whole response is ambiguous (indistinguishable from a low single-digit percentage).
  The *only* thing that disambiguates a low `utilization` reading is another scale-relevant window's
  `utilization` value that is `> 1` in that same response — establishing the response is on the
  0-100 scale, so every `(0, 1]` value elsewhere is then read literally as a low percentage.
  **`used_percentage` is NEVER scale-establishing evidence, on its own field or for a sibling
  window's separate `utilization` field** — a prior version of this guard treated any
  `used_percentage` reading anywhere in the response as proof of the 0-100 scale, but the two fields
  are independent inputs and one window reporting `used_percentage` says nothing about how a
  *different* window's `utilization` field is scaled; when unsure, the result is ambiguous
  (fail-closed). Separately, ANY value over 100 (or under 0) on either field, on any window
  including `extra_usage`, is unconditionally invalid on any scale and immediately invalidates the
  whole response. Either condition returns `None` for the *entire* response (usage unreadable,
  `check` exits 2), never a `ParsedUsage` with just that one field set to `None` — a per-field
  `None` reads as "unknown" everywhere else in this codebase, and unknown usage is treated as
  ELIGIBLE (fail-open); silently mapping a misread 97 to 0.97 that way would make the account look
  safe to keep using. `_run_check` also raises a dedicated `usage_scale_ambiguous` alert immediately
  on this specific condition, distinct from (and not gated behind) the ordinary
  30-consecutive-minutes `usage_unreadable_30min` debounce below, since a scale mismatch is a
  data-integrity problem worth surfacing on the first occurrence.
- **No lapse-signal machinery in phase 1.** An unreadable usage endpoint (including an expired-token
  401) is always treated as "unreadable," never as evidence the account itself has lapsed. 30
  consecutive minutes of unreadable usage raises one alert (suppressed while no `claude` process is
  running) and nothing more automated than that.
- **Billing-classifier abort is margin-gated, not any "ends."** During a switch, step d's billing
  classifier only ABORTS the attempt (exit 3, `disabled_reason`/end-date/live-% recorded, try the
  next eligible account) when the result is `no_active_plan` or an `ends` date that has already been
  REACHED (within the account's own margin). A future `ends` date does not abort — the account is
  switchable now, and that end date is simply recorded on the successful switch, exactly like a
  `renews` result.
- **Step d compares web identity to the target BEFORE recording any billing data.**
  `verify_signed_in_label()` reads the claude.ai account surface and compares it (in-process, never
  logged) against the target account's own email; a mismatch aborts the switch immediately, before
  the billing classifier or live-usage read ever runs, so a silent sign-in as the wrong account can
  never have its billing data attributed to the intended label.
- **External-switch detection, not enforcement.** Every `check`, and every `switch`'s own
  live-previous-account lookup, reads the currently signed-in account's email via `auth status
  --json` and maps it to a label — `switch` never trusts `state.json`'s stale `active_label` for this.
  If that resolved label differs from what `state.json` last recorded, it's logged as an external
  (operator-driven) switch, not a failure — and it never counts toward the loop backstop below.
- **Loop backstop counts forward switches only.** The same label re-entered within 2 hours, or more
  than 6 switches in 24 hours, opens the circuit breaker — but only for switches the tool itself
  initiates. Rollbacks and external switches are exempt, per plan v5.1.
- **The circuit also opens after 2 consecutive switch-attempt failures** (exit 6 or 7 — every failure
  reaching `rotate.py`'s outer exception classifier is CONVERTED into one of these two exit codes
  before the circuit check ever runs; see the exception-safety point below), independent of the loop
  backstop above — a successful switch resets the counter to zero. **Verify failures (exit 13) ALSO
  count toward this same breaker** [v5.1 R6-3] — `_verify_impl`'s own exception path additionally
  counts, corrected here (an earlier version of this line implied only `_run_check`-driven failures
  counted).
- **Rollback is a restricted flow**, not a second full switch: it re-drives the browser steps for
  the *previous* label only, skips step d's billing classifier/eligibility/try-next entirely (just
  the identity check), and is exempt from both the 10-minute switch-attempt spacing and the loop
  backstop above. A successful rollback still raises an alert (`rollback_succeeded`) — a rollback
  happening at all means the primary attempt failed badly enough to need one.
- **Google One Tap / FedCM is blocked at three layers**, not one: a Chrome launch flag
  (`--disable-features=FedCm,FedCmIdpSigninStatus`) for the browser-chrome-level prompt that no page
  route or DOM script can see at all; a Playwright route guard that aborts any
  `accounts.google.com/gsi/*` request regardless of frame (catches the One Tap iframe specifically,
  not just main-frame navigations); and an `add_init_script` that neuters `window.google.accounts.id`
  as belt-and-suspenders against a same-origin script the route pattern didn't anticipate. **The
  `window.google` neutering is SCOPED to claude.ai/claude.com only** (checked inside the injected
  script itself, via `window.location.hostname`) — an earlier version neutered it on every origin the
  browser context ever navigated to, which would ALSO have broken `accounts.google.com`'s own page (a
  real problem for `switch --to I --attended`, whose whole point is a real Google sign-in). **Both
  the gsi/* route block and the `window.google` neutering are DISABLED entirely for the attended `--to
  I` session** (`RealBrowserSession(..., allow_google_identity_services=True)`, used only by that one
  flow) — labels 1-5 keep the full block (they must never see any Google sign-in surface at all; see
  `NeverClickGoogleError`), but account I's sign-in genuinely IS Google OAuth, driven by the operator
  clicking a real Google Identity Services "Continue with Google" button, which this same block would
  otherwise disable.
- **The navigation allowlist requires https** (except `http://localhost`/`127.0.0.1` on any port, for
  the CLI's own local OAuth callback), compares hostnames with port and userinfo stripped, and never
  includes `www.google.com` as a navigable destination — Google's redirect wrapper is unwrapped
  in-process only, never itself an allowlisted host, since it is an open redirector.
- **The CLI-authorize step accepts only claude.ai/claude.com** (not the full navigation allowlist)
  and detects success by comparing the current URL's PARSED path against the known success path
  exactly, never a substring match anywhere in the URL.
- **Every production entry point is exception-safe [B1], and REAL browser failures never reach the
  exception path at all.** Every `RealBrowserSession` step method (`ensure_signed_out_if_other_account`,
  `start_email_signin`, `find_and_open_signin_email`, `verify_signed_in_label`,
  `read_billing_classification`, `read_live_usage_eligibility`, `open_and_authorize_cli_url`,
  `navigate_only`) is wrapped by its own decorator (`browser.py`'s `_exception_safe_step` and its two
  tuple-returning siblings) that converts ANY exception — a real Playwright timeout, a selector that
  doesn't match, a closed page — into the SAME `ok=False`/`"unreadable"`/fail-safe shape those methods
  already return on an ordinary failure. This means a genuine DOM/selector failure during the attended
  run (near-certain, since every selector here is a best guess pending step 0.3) drives the flow's
  NORMAL exit-6/rollback logic in `orchestrator.py`, not a separate, weaker exception path — there is
  effectively only one failure path to reason about, not two.
  <br><br>
  Only `cli_login.run_cli_login` itself (a real OS-level pty/subprocess bug) can still raise from
  inside `orchestrator.run_switch`. **[#5017 R4-I1, root-cause fix]: that exception is now caught,
  classified, and (when applicable) rolled back INSIDE the SAME `state.lock` hold the candidate loop
  already took for its own attempt — never by letting the exception unwind out of that `with
  state_store.state_lock(...)` block first.** A prior version of this fix (R2-B1/N1) classified from
  `_switch_impl`'s own OUTER exception handler, several stack frames up — but reaching that handler
  required the exception to first propagate through (and release) the candidate loop's own lock, and
  ONLY THEN did the outer handler re-acquire it for classification. In the gap between that release
  and re-acquisition, a concurrent `check` tick or a manually-invoked `verify` could win the lock and
  act on stale context — worst case, rolling back a switch that had ACTUALLY succeeded, if the
  concurrent actor's own live re-read happened to catch the target account signed in before this
  handler's own re-read did. Fixed: the SAME classification logic (via a small mutable
  `_SwitchExceptionContext` — previous/target label, previous/target account entry, and whether the
  CLI login step had actually STARTED, tracked via an `on_cli_start` callback `run_switch` fires
  right before invoking `cli_login_mod`) now runs via an `except BaseException` clause wrapped
  directly around the `run_switch`/`run_cli_login` call, still inside the candidate loop's own lock:
  if the CLI never started, the previous credential was never touched (exit 6, no live re-read
  needed, no rollback); if it had started, ONE live `auth status` re-read classifies it exactly like
  the normal post-login path — signed in as the previous account (exit 6), signed in as the target
  (exit 10, recorded as a real successful switch), or neither (a rollback is attempted; success is
  exit 6, failure sets `circuit_open`, `browser_held`, and raises an alert). `switch --to I
  --attended`'s own whole-flow lock hold gets the IDENTICAL fix around its own `run_cli_login` call
  (step e) — the same root cause existed there too, one function up.
  <br><br>
  **`_switch_impl`'s own outer exception handler is governed by ONE invariant, not a growing list of
  individually-guarded sites (rewritten [#5017 R6] — R5's two-shape description below was itself
  already an improvement over R2-R4's single LAST-RESORT shape, but every round from R2 through R5
  found ANOTHER post-outcome site (a save, a close, a factory call) that nobody had taught to set the
  round-du-jour's own "already handled" flag. R6 replaces per-site flag-setting with two OBJECTIVE,
  ONE-DIRECTION facts tracked on `ctx` — `_SwitchExceptionContext.lock_ever_held` and
  `.outcome_persisted` — that fully determine the outer handler's behavior with no other input, so a
  BRAND NEW fault-injection seam is automatically safe without needing its own guard):**
  <br><br>
  - **`ctx.lock_ever_held`** is set `True` the INSTANT `state.lock` is first acquired for this
    attempt (both `_switch_impl_unsafe`'s own candidate-loop lock and `_switch_to_I_attended`'s
    whole-flow lock set it immediately upon entering their `with state_store.state_lock(...)` block,
    before anything else in that block runs) and is NEVER reset to `False` for the attempt as a
    whole.
  - **`ctx.outcome_persisted`** is set `True` ONLY when `_guarded_post_outcome_save_state()` — the
    ONE function every outcome-persisting `save_state` call in this module routes through — actually
    completes a `save_state()` call successfully. It is NEVER set merely because classification
    DECIDED a value in memory; deciding and persisting are deliberately different facts. Per-candidate
    resets: the magic-link candidate loop resets it to `False` at the TOP of each new candidate's own
    iteration (a prior candidate's own persisted exit-3 abort must never make a LATER candidate's own
    unpersisted exception look safe to pass through).
  <br><br>
  The outer handler reduces to exactly three branches, checked in this order, with no other input:
  <br><br>
  **(a) `ctx.outcome_persisted` is `True` — pure passthrough.** The outcome already reached durable
     state (state.json) before this exception was raised — either the EXPECTED re-raise of a
     `KeyboardInterrupt` from the in-lock handler's own tail (the ordinary path for an operator's
     Ctrl-C), or a genuinely unexpected failure in a POST-persist step (e.g. a browser `close()` that
     cannot un-persist what is already durable). NEVER classifies, rolls back, or writes state again.
     Logs a label-free stderr line; raises an alert (`post_outcome_close_failed`) only if this
     specific re-entry represents a genuine post-persist failure, never for the ordinary interrupt
     re-raise; either re-raises (interrupt) or returns `ctx.decided_exit_code` (any other exception
     type, which this handler has no better value to return for).
  <br><br>
  **(b) `ctx.lock_ever_held` is `True` but `ctx.outcome_persisted` is `False` — fail closed,
     unconditionally, regardless of cause.** `state.lock` was held at some point for this attempt,
     but the outcome never reached durable state — this branch does NOT try to determine what
     happened in-lock (that per-cause investigation is exactly what made R2 through R5's own
     per-site patching an endless chase); it always responds the same way no matter which seam
     failed: write the fail-closed marker (`attempt_unrecorded_after_lock_held`), keep any live
     browser session held open (never close it further), raise a truthful `attempt_unrecorded_fail_
     closed` alert ("an outcome may not have been recorded; circuit is fail-closed..."), and exit 7
     (re-raising first, for an interrupt). This is what makes a BRAND NEW fault-injection seam safe
     by construction: whatever new site a future round finds, it is either (i) still guarded and
     sets `outcome_persisted` on success — branch (a) applies correctly next time — or (ii) an
     unguarded raise that reaches this branch, which fails closed regardless of which site it was.
  <br><br>
  **(c) `ctx.lock_ever_held` is `False` — the genuine pre-lock path, unchanged in spirit from R2-R5.**
     Nothing ran against the credential under this attempt's own control yet (a malformed
     accounts.json — `_load_accounts()` runs before the lock in the MAGIC-LINK path only; corrected
     [#5017 R7-M4], an earlier version of this line incorrectly claimed this held for attended-I too.
     `_switch_to_I_attended` loads accounts.json INSIDE its own whole-flow lock — see that function's
     dedicated doc bullet below for why — so a malformed-accounts.json fault there is genuinely a
     branch (b) case, `ctx.lock_ever_held` already `True`, not this branch (c)). The handler acquires
     `state.lock` itself (with its own long, 120s one-shot timeout —
     `_EXCEPTION_HANDLER_LOCK_TIMEOUT_S`), runs the SAME `_classify_and_attempt_rollback`/`_apply_
     switch_outcome_to_state` logic the in-lock handlers use, and persists the result through the
     SAME `_guarded_post_outcome_save_state()` (which also sets `ctx.outcome_persisted` here, same as
     every other call site). This classifies NORMALLY — if the CLI never started, exit 6 with the
     previous credential recorded as untouched and no rollback attempted; if it had started, a live
     re-read and possible rollback exactly as described above. The no-rollback/fail-closed-marker/
     exit-7 path applies ONLY as a FALLBACK on top of THIS branch, when even the 120s wait to acquire
     `state.lock` itself times out (a genuinely live, long-running flow — another `switch`, or
     `switch --to I --attended`'s own whole-flow lock hold — is still holding it) or is interrupted;
     it is never the normal outcome of a pre-lock exception whose lock attempt actually succeeds.
  <br><br>
  Once `state.lock` IS successfully held for a candidate/attended attempt, every in-lock exception
  path (the candidate loop's factory/run_switch/run_cli_login calls, the loop-backstop-tripped save,
  the loop's own finally-close, `_switch_to_I_attended`'s attended wait and its own run_cli_login
  call, and every post-outcome save/close in both flows) either persists through the shared guard
  (branch (a) applies next) or is caught and handled without escaping (never needing the outer
  handler at all) — and on the rare unguarded escape, branch (b) fails closed regardless. The browser
  is closed in every in-lock branch except the failed-rollback one (and the fail-closed-marker path
  below), where it is deliberately left open for the operator.
  **`_apply_switch_outcome_to_state`'s own `browser_held`/
  `browser_held_by` write is gated on ownership** [#5017 R4-I1; corrected R5-M2]: it only writes when
  this switch attempt's own token is the CURRENT recorded holder (`browser_held_by == token`), OR
  `state["browser_held"]` is itself falsy (genuinely unheld, nothing to conflict with) — a FOREIGN
  hold (a `verify` genuinely in progress) must never be silently wiped by a different switch
  attempt's own classification write. **The gate is keyed on whether a hold is ACTUALLY present
  (`not state.get("browser_held")`), never merely on whether `browser_held_by` happens to be `None`**
  — the pre-R5 gate (`current_holder is None or current_holder == token`) treated a TOKEN-LESS
  legacy hold (`browser_held=True` but `browser_held_by` never set, e.g. from before that field
  existed) as "unheld, safe to claim/wipe" purely because its holder field read `None` via `.get()`,
  which silently cleared a hold that was, in fact, still genuinely open. `browser_held` is set True
  in FOUR branches total, always
  alongside an alert, never as a silent default** — corrected here (an earlier version of this line
  said "only ever set True in that one branch," which was true for the magic_link candidate loop's
  own exception path but never accounted for `switch --to I --attended`'s own three distinct
  held-open cases: the attended timeout, the binary guard refusing after a confirmed Google sign-in,
  and step e's CLI login failing to confirm target I). **This FOUR count is for
  `_switch_impl_unsafe`/`_switch_to_I_attended`'s own branches specifically — the classification
  handler's fail-closed-marker path (below) is a FIFTH, separate place `browser_held` is set True,
  via a different mechanism (the marker, not a direct `state.json` write inside this handler's own
  lock, since that lock is exactly what's unavailable on
  that path).** **`check` alerts on a STALE hold** (`browser_held_stale`, past
  `_BROWSER_HELD_STALE_MINUTES` = 60) by comparing `time.time()` against `browser_held_since`, which
  every `browser_held=True` writer stamps alongside it — **except a hold with no `browser_held_since`
  at all (a legacy hold predating that field, or a token-less hold the ownership-gate fix above now
  correctly leaves un-wiped) was never checked for staleness at all** [#5017 R5-M3]: `check` now
  stamps `browser_held_since = now` under `state.lock` the FIRST time it observes such a hold, so
  staleness is measured from that observation point (the only time the hold is actually known to
  still exist) rather than silently never firing. `main()`, `verify`, and `cli_login`'s own child-process cleanup are
  wrapped the same way structurally (try/except or try/finally), and (a) never let `str(exception)`
  reach stdout/stderr — only `type(e).__name__` plus the step name — while (b) logging a full
  traceback to `rotation.log` (never stdout/stderr) run through `logging_utils.scrub_traceback_text()`,
  which strips URLs, emails, 6-digit codes, and the three specific message shapes Playwright's own
  error text is known to embed (`navigating to "<url>"`, `<error> at <url>`, `fill("<value>")`).
- **The keychain item is read under the real macOS username, never a rotation label** —
  `credential.CLAUDE_CLI_KEYCHAIN_ACCOUNT` — because the Claude CLI stores exactly one credential
  item per machine user, not one per rotation account. The raw value (a JSON blob) is parsed and only
  its access-token field is ever sent over the network (`credential.extract_access_token()`); an
  unrecognized shape fails closed (usage unreadable, no network call), never falling back to treating
  the raw blob itself as a bearer token.
- **Hygiene is structural, not just convention.** No source file in this package may contain the
  string "logout" (the flow never calls `claude auth logout`, checked directly in the test suite);
  the keychain token and the CLI's OAuth URL are read in-process only and never appear in a
  command-line argument, a print, a log line, `state.json`, or `alerts.jsonl`.
- **The fail-closed marker (`state.circuit_open.flag`) [#5017 R2-B1/R3-B1] — a SIDECAR file, not a
  `state.json` field, so it needs no `state.lock` to write or check.** Corrected [#5017 R8-M2] — an
  earlier version of this bullet claimed the marker is written "ONLY by the switch exception
  handler's classification wait, and ONLY on the one path where that wait cannot complete normally."
  That was true through round 5; it stopped being true once R6 introduced the `lock_ever_held`/
  `outcome_persisted` invariant and R7/R8 extended it. **Five distinct writers exist today**, all
  calling the same `_write_fail_closed_marker()` (`O_CREAT | O_EXCL`, mode 0600, JSON `{"reason":
  <sanitized string — see the marker-reason hygiene bullet below>, "t": <epoch>}`):
  1. **The genuine 120s-wait lock-acquisition timeout** (branch (c)'s own fallback, the ORIGINAL
     writer, described below) — the handler waits up to `_EXCEPTION_HANDLER_LOCK_TIMEOUT_S` (120s) to
     acquire `state.lock` for classification; the ONLY way that wait is exhausted is a genuinely live,
     long-running flow already holding the lock (another `switch`, or `switch --to I --attended`'s own
     whole-flow lock hold across its 10-minute attended wait) — not ordinary brief contention, which
     120s already absorbs. On that timeout, OR on a `KeyboardInterrupt` raised DURING the wait itself,
     the marker is written before the interrupt is re-raised.
  2. **`_guarded_post_outcome_save_state()`'s own `except OSError`** — the shared save-guard every
     `switch`-side outcome-persisting call site routes through; on a `save_state()` failure it writes
     the marker (reason `post_outcome_save_state_failed:<classify_reason>`) via the `held_state=`
     in-lock form (see the `held_state` bullet elsewhere in this doc) so it never re-locks against a
     lock the caller already holds.
  3. **`_switch_impl`'s outer-handler branch (b)** (`lock_ever_held=True`, `outcome_persisted=False`)
     — writes it unconditionally as part of failing closed, reason `attempt_unrecorded_after_lock_
     held`, regardless of which in-lock seam actually faulted.
  4. **Branch (c)'s own INNER fault** [#5017 R7-M2] — when branch (c)'s own classify/load/apply
     sequence (running with a freshly-acquired lock) itself faults a second time, it writes the
     marker directly (reason `branch_c_inner_fault_fail_closed`) rather than letting the fault escape
     `_switch_impl` entirely (there is no further outer handler above this function). [#5017 R8-M3]
     extends this same treatment to branch (c)'s own pre-lock `binary_resolver.resolve()` call
     (reason `branch_c_binary_resolver_fault_fail_closed` — the CLI never started at this point, so no
     rollback is attempted either).
  5. **The exit-3 bookkeeping handlers** [#5017 R7-M3] — a fault in the dict-mutation/save bookkeeping
     for a candidate whose CLI login step ALREADY completed normally (the exit-3 billing-abort or
     live-eligibility-abort branches) writes the marker directly (reason `exit3_bookkeeping_fault_
     fail_closed`) rather than routing through credential classification (which would be wrong here —
     the credential itself never failed). This holds on BOTH of the two ways this bookkeeping can fail,
     confirmed [#5017 R9-B1]: (a) [#5017 R8-B1] an EXCEPTION during the dict mutation/`set_account_
     state` call — this handler stops the candidate loop and returns exit 7 immediately after writing
     the marker, never `continue`s to drive a fresh live CLI login against the next candidate while
     this attempt is already marked fail-closed; and (b) [#5017 R9-B1] the bookkeeping's OWN
     `_guarded_post_outcome_save_state()` call returning `True` (a `save_state()` OSError, no
     exception raised — the guard swallows its own failure and already wrote the marker itself) — this
     was NOT covered by (a)'s fix (no exception means the `except` clause never runs at all) and
     previously fell through to `continue` unconditionally; both exit-3 branches now check this return
     value and `return 7` on `True`, exactly like case (a).
  - **Why NOT drive a rollback here instead.** An earlier version of this fix (N1) ran the SAME
    classification+rollback logic unlocked as a "best-effort" fallback on this exact timeout — but
    rollback drives a REAL `claude auth login` against the SAME Chrome profile and credential that
    whatever flow is holding the lock is ALREADY using, racing that flow's own login step. The fix
    (R2-B1) removed that entirely: on this path, NO rollback or login of any kind is attempted — only
    read-only classification — the browser is kept HELD OPEN (never closed) for the operator, and the
    handler reports **exit 7**.
  - **No-second-rollback rule** [#5017 R8-B1, `ctx.rollback_attempted`] — set `True` IMMEDIATELY
    before EVERY `run_rollback` call this attempt makes (both the normal, non-exception rollback call
    site AND `_classify_and_attempt_rollback`'s own call site). If `run_rollback` itself raises (a
    real, reachable shape: `run_switch` returns exit 7, the normal-path rollback call raises, and the
    in-lock exception handler's own re-read then sees NEITHER account confirmed live — which would
    otherwise conclude "needs_rollback" a SECOND time), `_classify_and_attempt_rollback` checks this
    flag FIRST and refuses to attempt another rollback, returning exit 7 with reason
    `exception_second_rollback_attempt_blocked_fail_closed` instead. A second rollback would drive a
    SECOND real, blocking `claude auth login` against the same credential the first (interrupted)
    rollback was already using.
  - **Final-save-failure reports exit 7, never the decided-but-unpersisted code** [#5017 R7-I1] — both
    the candidate loop's own final post-loop save (the `break` path's `outcome.exit_code`, e.g. a
    successful exit 10) and branch (c)'s own classify/persist save capture `_guarded_post_outcome_
    save_state()`'s return value; on a save failure, the function returns **7**, never the original
    decided exit code — reporting a switch as "succeeded" (exit 10) when `state.json` was never
    actually updated to reflect it would be a lie the caller has no way to detect otherwise.
  - **Every command refuses while it exists, with exit 5 (circuit-open semantics) and an alert —
    even though `state.json`'s own `circuit_open` field may still read `false`.** The marker and the
    `state.json` field are two INDEPENDENT signals for the same "don't touch this account
    unattended" condition; a caller checks BOTH. `check` (including a `--dry-run` invocation — the
    marker check runs before the dry-run branch, since a dry-run still must not report a
    misleadingly-clean picture while a real fail-closed event is unresolved), `switch` (both the
    ordinary label-target form AND `switch --to I --attended` — the marker check in
    `_switch_impl_unsafe` runs BEFORE the `--to I` dispatch, so it covers both), `verify`, and
    [#5017 M-5] `probe-step0 --step b1` (which drives a real, deliberately-killed `claude auth
    login` — exactly the kind of live-credential action every other browser-driving command already
    refuses on this same condition) all check `_fail_closed_marker_present()` up front (no lock
    needed) and refuse immediately, raising a `circuit_open_fail_closed_marker` alert, if it is
    present. `status` [#5017 R4-M2] also shows the marker explicitly (`fail_closed_marker: present
    (reason, t)` or `absent`) and reflects it in its own circuit-open summary line, since an operator
    reading only `circuit_open: False` there would otherwise have no way to know these commands are
    still refusing.
  - **Recovery is `clear-circuit`.** It removes the marker via `_clear_fail_closed_marker()`, under
    `state.lock`, in the SAME operation that resets `circuit_open`/`failures`/
    `consecutive_failure_count`/`corrupted_on_load` (see the corrupt-`state.json` recovery bullet
    above) — there is no separate command for the marker specifically. Leaving the marker after
    `clear-circuit` would keep every command refusing forever even though the circuit itself was
    just cleared, so this is not optional cleanup, it is part of what `clear-circuit` means.
    **[#5017 R4-M3]: `browser_held` is NOT set VIA the marker, and `clear-circuit` does not close a
    genuinely open Chrome window** — the lock-timeout fallback path always leaves the browser held
    open (a real, separate fact about the machine), and clearing the marker/circuit fields in
    `state.json` has no effect on that window. `clear-circuit` therefore PRINTS an explicit reminder
    to close it by hand whenever the marker was present for that invocation.
  - **The `exception_handler_lock_timeout_fallback` alert** is raised alongside the marker write, and
    [#5017 R6-M2] is now RESERVED EXCLUSIVELY for this genuine 120s-wait lock-ACQUISITION-timeout
    shape (branch (c)'s own fallback) — see the four distinct alert kinds below for why this
    narrowing matters. Its text does NOT claim any classification happened (an earlier version of
    both the code comment and this alert's own text incorrectly implied a "read-only classification"
    — the lock-timeout path performs NO live re-read and NO classification at all; `exit_code` is
    simply hardcoded to 7, unconditionally, since there is no way to determine the true account state
    without the lock this path doesn't have). The alert instead tells the operator plainly: close the
    held Chrome window, confirm account state by hand, then run `clear-circuit`. The
    `browser_held_after_exception` alert also fires on this path (the browser is genuinely held). A
    DIFFERENT alert, `circuit_open_fail_closed_marker`, is what `check`/`switch`/`verify`/
    `probe-step0 --step b1` each raise on their OWN refusal while the marker exists — the two alert
    kinds mark two different events (the marker being WRITTEN, vs. a later command being REFUSED
    because it already exists).
  - **Four DISTINCT post-outcome alert kinds [#5017 R6-M2], deliberately never conflated** (an
    earlier round reused `exception_handler_lock_timeout_fallback` for several of these, which made
    the alert log itself misleading about which of several very different failure modes had actually
    occurred):
    - `exception_handler_lock_timeout_fallback` — ONLY the genuine 120s-wait lock-acquisition
      timeout (branch (c)'s own fallback), described above.
    - `post_outcome_persist_failed` — a `save_state()` call for an already-classified/decided outcome
      raised `OSError` (disk full, permissions). Raised by `_guarded_post_outcome_save_state()`
      itself, from EVERY `switch`-side call site in the module (the candidate loop's per-candidate
      saves, the loop-backstop-tripped save, the final post-loop save, `_switch_to_I_attended`'s own
      saves) — the fail-closed marker (`post_outcome_save_state_failed:<reason>`) is written alongside
      it via that shared helper. **`check`'s own first-sight `browser_held_since` stamp save is a
      SEPARATE, narrower inline `try`/`except OSError`** (corrected [#5017 R7-M4] — it does NOT go
      through `_guarded_post_outcome_save_state`, since `_run_check` has no `_SwitchExceptionContext`
      to thread through it) that reuses the SAME `post_outcome_persist_failed` alert kind for
      consistency, but refuses with `check`'s own exit 4 (`browser_held; refusing`) rather than
      writing the fail-closed marker — the hold is still genuinely present either way, so the
      ordinary `browser_held` refusal is the correct, narrower response here, not a full circuit-open.
    - `post_outcome_close_failed` — a `browser_session.close()` call AFTER an outcome was already
      decided (or already persisted) raised an exception. Never fatal to the outcome itself (which is
      independent of whether the browser physically closed), but surfaced rather than silently
      swallowed.
    - `attempt_unrecorded_fail_closed` — branch (b)'s own alert: `state.lock` was held for this
      attempt but its outcome was never confirmed persisted before an exception reached the outer
      handler. This is the CATCH-ALL for any fault-injection seam not (yet) individually guarded —
      see the invariant description above for why this is always safe regardless of which seam
      failed. Its text is deliberately honest about the uncertainty ("an outcome may not have been
      recorded"), rather than claiming a specific cause.
- **`billing_selectors_confirmed` gates every lasting `no_active_plan` disable.** `accounts.json`'s
  top-level `billing_selectors_confirmed` field (default `false`/absent) is an OPERATOR STEP, done
  once page_selectors.py's billing-classifier phrases are confirmed against the real DOM during the
  attended run (step 0.3). Until it is set `true`, a `no_active_plan` reading (from either `switch` or
  `verify`) writes ONLY a dedicated `unconfirmed_no_active_plan_at` timestamp field — never
  `disabled_reason`, never touching `sub_end_at`/`renews_at`/`verified_at` — and raises an
  `unconfirmed_no_active_plan_selector` alert instead of disabling the account. This exists because
  `resolver.is_eligible()`'s own `disabled_reason` check is a bare truthiness test on ANY non-None
  string, so writing `disabled_reason="unconfirmed_no_active_plan"` (an earlier, now-fixed shape)
  disabled the account exactly like a real, confirmed `no_active_plan` reading would.
- **A corrupt `state.json` fails CLOSED, and recovery is two commands.** `state_store.load_state()`
  distinguishes a genuinely MISSING file (a fresh install — returns an empty skeleton, circuit
  closed) from an EXISTING file that fails to parse or isn't a JSON object (returns a skeleton with
  `circuit_open=True` and `corrupted_on_load=True`) — the two used to be indistinguishable, which
  meant disk corruption or a torn write could silently CLEAR a previously-open circuit. `check` alerts
  `state_json_corrupted` and then immediately refuses via the now-open circuit, same as any other
  circuit-open state. **To recover:** either delete the corrupt `state.json` (a fresh empty skeleton
  is the safe default — nothing in it is unrecoverable, it is derived state) or run
  `rotate.py clear-circuit` if the file is otherwise fine and only the circuit needs resetting.
  **`clear-circuit` resets FOUR things together, not just `circuit_open`** — corrected from an
  earlier "THREE things" count that predates the fail-closed marker below: `circuit_open=False`,
  `failures=[]`, [#5017 N3] `consecutive_failure_count=0` and `corrupted_on_load=False`, AND
  [#5017 R2-B1] the fail-closed marker file (`state.circuit_open.flag`) is removed via
  `_clear_fail_closed_marker()` — all under the SAME `state.lock` hold this command already takes.
  Clearing `failures` alone (the pre-fix behavior) left `consecutive_failure_count` at whatever
  value had tripped the circuit, so the very NEXT failure after an operator ran `clear-circuit`
  would immediately re-open it — the counter never got a fresh start alongside the circuit itself.
  `corrupted_on_load` is cleared here too, since nothing else in this tool ever writes it back to
  `False` once the operator has actually dealt with a corruption event (whether by running
  `clear-circuit`, as here, or by deleting the corrupt file and letting a fresh skeleton get
  seeded) — left set, a future diagnostic read of `state.json` would keep reporting a corruption
  event that was already resolved, indefinitely. The marker is removed for the identical reason —
  see "The fail-closed marker" bullet below for what writes it and why leaving it after
  `clear-circuit` would defeat the whole point of running the command.
  **The forensic backup of a corrupt `state.json` is named by CONTENT HASH, not timestamp**
  (`state.json.corrupted-<sha256[:16]>`, not the earlier `state.json.corrupted-<unix-epoch-int>`
  naming) — see the Recovery section below for the full mechanics and why this matters for repeated
  loads of the same corruption.
- **Every newly-raised alert also fires a local macOS notification** (`alerts.raise_alert()` calls
  `alerts.notify_osascript()`, LABEL-ONLY title/text — never `detail`, which callers are not required
  to keep label-only the way the alert `kind` string is) — a duplicate-suppressed
  (deduped-within-window) alert does NOT re-notify. Tests patch `alerts.notify_osascript` to a no-op
  recorder (`conftest.py`'s `_block_real_osascript_notifications` fixture) so no test run ever fires a
  real notification.
- **No alert is ever raised while `state.lock` is held.** `notify_osascript` is a real
  `subprocess.run(["osascript", ...])` call with up to a 10-second timeout — running it while holding
  `state.lock` would block every other process contending for the same lock (the scheduled `check` job
  fires every 120 seconds) for that long, for no reason. Every `check`/`switch`/`verify`/`switch --to I
  --attended` call site that both mutates state under the lock AND needs to raise an alert about that
  mutation defers the actual `alerts_mod.raise_alert()` call until after its own `with
  state_store.state_lock(...)` block (or, for `switch --to I --attended`, the whole-flow lock hold
  Important 5 requires) has exited — collected via a local `pending_alerts`/return-value pattern, never
  called from directly inside the lock. `_record_failure_and_maybe_open_circuit` itself only mutates
  state and reports whether the circuit newly opened; it never raises the alert itself, for the same
  reason.
- **`verify` refuses on the same three preflight conditions `switch` does, and now sets/clears
  `browser_held` around its own browser session too [#5017 M7].** Before driving any browser,
  `verify` checks (in order): an operator-set `schedules/DISABLED` marker present → exit 4; an open
  circuit (`state["circuit_open"]`) → exit 5; `browser_held` already `True` (left open by a prior
  failed `switch`/`verify`, or another `verify`/`switch --to I --attended` genuinely in progress) →
  exit 4. These mirror `switch`'s own preflight exactly, so a caller sees the same exit-code meaning
  across every command that can drive a browser. **Once past that preflight, `verify` sets
  `browser_held=True` itself (under `state.lock`) BEFORE opening its own browser**, and clears it
  back to `False` in a `finally` (also under the lock) once that browser closes — covering the
  browser-open call (`factory()`) itself, not just `orchestrator.run_verify()`, so a factory that
  raises before ever producing a session still clears the flag rather than leaving it stuck `True`
  forever. **[#5017 R2-I1/R3-I1 correction]: the clear is conditional on OWNERSHIP, not
  unconditional.** `verify` records an owner token (`state["browser_held_by"]`, a fresh `uuid.uuid4()`
  for THIS run) in the SAME locked block that sets `browser_held=True`, and the `finally`'s clear
  (`_clear_browser_held_if_owned()`) only flips `browser_held` back to `False` if
  `state["browser_held_by"]` STILL matches this run's own token at clear time — never
  unconditionally. Every OTHER writer of `browser_held=True` anywhere in this module also writes its
  own `browser_held_by` (or explicit `None`) in the same locked write, and `release-browser` sets
  `browser_held_by=None` alongside clearing the flag, so a stale token can never accidentally match a
  later holder's clear. Without this, a verify attempt whose own precheck never actually won
  ownership (or that raced a DIFFERENT command's own set/clear) could clear a `browser_held` flag a
  different, still-running attempt legitimately owns — clearing someone else's held browser out from
  under them. Before this fix, `verify` never touched `browser_held` at all: a `check`/`switch`
  invocation running WHILE a verify browser was genuinely open on screen had no way to know one was
  live, and could open a second one concurrently. With the fix, a concurrent check-to-switch attempt
  correctly refuses (exit 4) for the entire duration verify's own browser is open, exactly as if a
  `switch` had left the browser held.
- **`seed` refuses to overwrite an existing `accounts.json` without `--force`.** A real operator
  `accounts.json` carries real per-account tuning (`auto_rank`, `attended_only`, `sub_end_at`,
  `tier`, `weekly_reset_hint`, `billing_selectors_confirmed`) that `seed`'s allowlist-derived skeleton
  knows nothing about — running `seed` again by accident used to silently replace it with none of
  that tuning. `seed --from-snapshot` alone refuses (exit 1) whenever `accounts.json` already exists;
  `--force` opts into the overwrite explicitly.
- **`probe-step0 --step 0.2a` writes its live capture OUTSIDE the git-tracked tree by default.** The
  default output path is `<base_dir>/probe_0_2a_live_capture.json` (already gitignored, same as
  `state.json`/`accounts.json`) — a real live capture (even scrubbed of PII/secrets) landing directly
  in the tracked `tests/fixtures/` path by default risked it being picked up by a broad `git add`
  before anyone reviewed its content. `--commit-fixture` opts into the old, git-tracked destination
  (`tests/fixtures/usage_response_live_capture.json`) explicitly, for the one legitimate case
  (updating the checked-in fixture on purpose).
- **Burn samples are throttled to one per label per 5 minutes, regardless of `check`'s own
  interval.** `burn.record_sample()` (phase-1-active; the sample-recording half of `burn.py` — the
  gain-formula functions below it are designed for phase 2 and never called by any phase-1 path) is
  called on every `check` tick (every 120 seconds), but only actually APPENDS a new sample for a
  label when at least `_MIN_SAMPLE_SPACING_SECONDS` (5 minutes) has passed since that label's most
  recent existing sample — a same-label sample younger than the spacing window is skipped entirely,
  never replacing the prior one. Without this, 8 days of retention at a 120-second interval
  accumulates roughly 5,760 samples (measured at ~0.9 MB of JSON), rewritten in FULL on every single
  `check` invocation (`state_store.save_state()` always writes the whole `state.json`, never an
  append) — pure storage/write-amplification cost, since the phase-2 gain formula this data exists
  for buckets samples into 1-hour buckets, so anything finer than a few minutes between samples adds
  no bucketing-fidelity benefit. **[#5017 M-a]** The throttle caps the sample count at roughly
  `_RETENTION_SECONDS / _MIN_SAMPLE_SPACING_SECONDS` — at 1 sample per 5 minutes, that is **288 per
  label per day** (24×3600 ÷ 300), i.e. roughly **2,304 total per label** over the full 8-day
  retention window ([#5017 M-4] about **2.5x below** the unthrottled ~5,760 figure above — corrected
  from an earlier, wrong "two orders of magnitude" claim; 5760 ÷ 2304 = 2.5) — while still comfortably
  exceeding the 6-active-hours floor-rate requirement many times over. Pruning of samples
  older than the 8-day
  retention window still runs on every call regardless of the throttle, so stale-data cleanup is
  never delayed by it.
- **An overflowing usage value invalidates the WHOLE response, never just one field** [#5017 R7-I2] —
  `usage.py`'s `_raw_value()` raises `_AmbiguousScale` (not a per-field `None`) when a value is too
  extreme to represent as a `float` (`OverflowError` on conversion — e.g. a corrupted or malicious
  `10**400` in the response body). `parse_usage_response()`'s own `except _AmbiguousScale: return None`
  then invalidates the ENTIRE response. A per-field `None` would have been WRONG here: "unknown usage"
  is treated as ELIGIBLE elsewhere in this codebase, so a corrupted `seven_day_opus` reading sitting
  alongside a genuinely healthy `five_hour` reading must never look like "healthy account, opus usage
  merely unknown" — the whole response is untrustworthy once any one field is this malformed.

## Trigger

`schedules/com.oversight.account-rotation.plist` — `StartInterval` 120 seconds, runs
`rotate.py check`. `check` alerts on a hard trigger by default, and only opens a browser/switches once
the operator has set accounts.json's `unattended_switch_enabled` to `true` (see the `check` section
above) — that flag itself should stay `false` until the plan's A4 acceptance criterion (the attended
first switch) has actually passed. Listed `unloaded` in `knowledge/oversight_install.md` §2 until the
attended first switch (plan acceptance criterion A4) succeeds and the operator explicitly loads it.
