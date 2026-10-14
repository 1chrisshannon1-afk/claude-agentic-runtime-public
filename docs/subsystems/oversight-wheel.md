# The Oversight Wheel

*Summary/orienting doc. The canonical operational reference is
[`~/.claude/knowledge/oversight_install.md`](../../knowledge/oversight_install.md) — read that for
exact schedules, install steps, and troubleshooting. This page explains the concept and points you
there.*

## What it is

The oversight wheel is fifteen runtime-level agents that watch **any app on this machine**, triggered
by scheduled jobs or dispatched by name rather than "called" directly (`~/.claude/CLAUDE.md` §13). A
session doesn't invoke the oversight system as a unit — launchd fires a scheduled job on a cadence
(eight of the fifteen), or a session dispatches one of the seven dispatch-only seats by name when a
task calls for it, and findings flow back through the normal issue-tracker rules (`board-steward`'s
dedup/disposition rules).

The eight scheduled agents, each with a runtime primer (portable discipline) plus a repo-local
dossier (app-specific facts) — see `knowledge-and-primers.md` for that distinction:

| agent | lane |
|---|---|
| launch-director (opus) | ranks all work against the app's one goal; kills gold-plating |
| board-steward (sonnet) | tracker truth: dedup, honest closes, fields-over-labels |
| sentinel (sonnet) | discovery sweeps + the daily heartbeat audit of every scheduled job |
| consistency-auditor (sonnet) | cross-surface contradictions (docs vs. code vs. marketing) |
| test-architect (opus) | test-net + observability architecture |
| trust-architect (opus) | security/tenancy/money + agentic security; reviewer-of-record on trust-surface commits |
| product-qa (sonnet) | staging browser walkthroughs as a customer persona |
| agentic-systems-architect (opus) | audits agent/system design, feedback loops, delivery flow |

Seven more seats round out the fifteen, dispatch-only with no schedule of their own — triggered by
name when a task calls for them, same judge-never-edit posture as the eight above:

| agent | lane |
|---|---|
| code-quality-architect (opus) | code structure/coupling/complexity + debt trend; a schedule is deliberately deferred until enough audits show it's worth automating |
| admin-portal-architect (opus) | admin-console / back-office visibility and operability audit; same deliberately schedule-less posture |
| research-scout (sonnet) | technical prior-art / OSS discovery |
| market-analyst (opus) | per-industry competitor / market-facts intel |
| cost-strategist (sonnet) | FinOps: vendor spend tally, waste classes, keep/kill/downgrade framing |
| observability-architect (opus) | logging and observability architecture audit; same deliberately schedule-less posture |
| devops-architect (opus) | delivery and infrastructure architecture audit (IaC drift, release/rollback engineering); same deliberately schedule-less posture |

A further surface, `dev-runtime.md`, is not an oversight agent — it's the shared grounding dossier
the generic dev agents (`implement`, `test-writer`, `test-runner`, `git-ops`, `ci-monitor`,
`explore`) read for this repo's commands/layout/branch model.

## The `com.oversight.csa.*` launchd jobs

An install keeps one `com.oversight.*` plist per scheduled job in `~/.claude/schedules/`; see
`oversight_install.md` §0 for how an install's inventory is recorded and checked. **The `.plist` files
themselves are deployment-specific (absolute paths, one machine's GitHub org/project numbers, one
operator's repo layout) and are never shipped or shared as-is** — `schedules/example.oversight.plist`
and `schedules/example.wheel.plist` are the portable artifact: annotated templates showing the exact
CLI/env-var contract, meant to be copied and filled in per-machine, per-repo. What genuinely is
shared, portable code: the wrapper script every job launches through
(`schedules/run_oversight_job.sh`, plus `run_watchdog.sh` for the watchdog below) and the job prompts
(`schedules/prompts/`) — those carry no machine-specific literals and are the same content on any
install.

Each real, installed job is a standard launchd agent: `ProgramArguments` runs
`run_oversight_job.sh <job-label> <prompt-file> <cadence-text> [alarm-seconds]` (see that script's own
header comment, or either example plist's inline comments, for the full contract), `WorkingDirectory`
is the target repo, and `StartCalendarInterval` sets the cadence (never `RunAtLoad` for a standing
job). Prompt text lives separately under `schedules/prompts/`, one `.txt` file per job
(`daily_sweep.txt`, `weekly_report.txt`, `walkthrough.txt`, `test_audit.txt`, `trust_audit.txt`,
`agentarch_audit.txt`, `issue_wheel.txt`), plus a shared `_preamble.txt` (kill-switch check,
budget-status note, and the START heartbeat write) that every one of those job prompts begins with
rather than duplicating those steps inline. The standing job labels are
`com.oversight.csa.daily`, `.launchdir`, `.productqa`, `.testarch`, `.trustarch` and `.agentarch`,
plus the two wheel labels and the watchdog; an install also carries other `com.oversight.*` jobs
(for example the disk janitor), and `knowledge/oversight_install.md` §0/§2 is the full inventory.
`com.oversight.csa.steward` no longer exists: its
board-steward sweep was superseded by THE ISSUE WHEEL's own P3 close phase. Which labels are loaded
on a given machine is per-install state that changes, so this page never states it: the declaration
is `oversight_install.md` §2's `expected_state` column (an intent, not a live reading; see "The
watchdog" below), and the fact is `launchctl list`.

Notably, `com.oversight.wheel.csa` (THE ISSUE WHEEL) is not a watcher like the other six — it's a
bounded worker that triages, fixes, and closes GitHub issues, building each fix in an isolated git
worktree and integrating a reviewed, tested patch into the shared tree. It shares the
`com.oversight.*` naming and schedule infrastructure but is a different kind of job. It supersedes
the former nightly finishing loop (`com.oversight.csa.loop`, removed 2026-09-08 — its plist and
prompt are deleted; git history is the only remaining record of either).

## Heartbeats

Every job writes a heartbeat file **twice**: a START write immediately after its budget pre-flight
(`{"job", "started_at", "finished_at": null, "exit": 1, "cadence", "summary": "STARTED ..."}`), then
an END write that overwrites the same file with the completed shape
(`{"job", "started_at", "finished_at", "exit": 0, "cadence", "summary"}`). Files live at
`~/.claude/schedules/heartbeats/<job>.json`, one per job label, all timestamps UTC ISO-8601 with a
literal `Z` suffix. A session killed mid-run leaves the START shape behind instead of vanishing —
that's what lets a crash self-record rather than disappear silently. **For the two wheel jobs
(GH #4767) the WRAPPER writes START**, before launching claude, and the session writes END only
through `hooks/wheel_sink.py`, which stamps `finished_at` itself and marks the file
`"written_via": "wheel_sink"` (see "The wheel launcher" below); every other job's session still
writes both. A heartbeat file holds only the LAST run; the per-run history the wrapper appends
(`heartbeats/history/<label>.jsonl`, see "The wheel launcher", step 7) is what green-night counting
reads.

**`status` (added THE ISSUE WHEEL plan, WS1-B.1 / Phase B item 1).** `run_oversight_job.sh` now
writes a structured `"status": "ok" | "failed" | "skipped-quota" | "skipped-disabled" | "skipped-throttle"`
into the heartbeat on every
WRAPPER-owned exit path — including its own `WRAPPER: ...` fail-fast diagnostic write (the shape
that motivated this field: exit 0 and a fresh `finished_at`, which every other liveness check reads
as healthy, with only the free-text `summary` naming the real failure). A session-authored END
heartbeat predating this field (or one written by a job prompt that hasn't adopted it) simply omits
`status` — `heartbeat_audit.py`'s `job-failed` check (below) treats that absence as inconclusive on
its own and falls back to `exit`/`summary` shape, never as an automatic pass or fail. A quota
pre-flight skip (see "Quota pre-flight" below) additionally stamps a `"consecutive_quota_skips"`
integer into a `status: "skipped-quota"` heartbeat, or a `"consecutive_throttle_skips"` integer into
a `status: "skipped-throttle"` heartbeat (#5922: these are two INDEPENDENT counters — a
server-side throttle is not quota exhaustion, so a throttle skip never carries the quota streak
forward and vice versa) — each carried forward across consecutive skips of its OWN kind and reset to
1 on the first skip of a fresh streak (a skip of the other kind, in between, also resets it).
`skipped-disabled` is not flagged by the job-failed check (its status is neither `failed` nor
absent). It also raises no `timestamp-divergence`, because the wrapper prints its `WRAPPER:` line to
the job's out.log, the audit's finish proxy, at the moment it stamps `finished_at`. Every
wrapper-owned early exit does the same. Launch-context refusal heartbeats (the wheel launcher,
below) carry `exit: 79` and a typed `hard_stop` key, with `status: "failed"`.

`~/.claude/hooks/heartbeat_audit.py` is the mechanical, non-LLM auditor: it diffs expected jobs
against `oversight_install.md`'s own job table, validates the typed-key/UTC format, and flags a
`stale-start` (a START heartbeat older than its own cadence+grace, meaning a crash) or a job that's
loaded in launchd but never actually fired. It runs as a pre-step of the daily job and of `/sweep` —
so, on its own, it can't detect the wheel going *fully* dark (every job silently failing to fire),
only a job that fired and then died or drifted, since nothing would ever invoke it in the first
failure mode. The watchdog (below) is what closes that specific gap by running the same audit on its
own independent schedule.

**Two new finding classes (THE ISSUE WHEEL plan, WS1-B.1/B.3 / Phase B items 1 and 3), both now in
the watchdog's own escalation set (see "The watchdog" below):**
- **`job-failed`** — a FINISHED heartbeat whose `status` is exactly `"failed"`, OR whose `status` is
  absent AND (`exit` is a non-zero int OR `summary` starts with the wrapper's own `"WRAPPER:"`
  prefix). This is the fix for the exact gap the plan's F3 finding named: a real Agency heartbeat
  carried `exit: 0` and a fresh `finished_at` (reading as healthy to every prior check) while only its
  `summary` said the session died without a truthful END write. `status: "ok"`/`"skipped-quota"`/
  `"skipped-disabled"`/`"skipped-throttle"` are never flagged BY THEMSELVES regardless of
  `exit`/`summary` — but `"skipped-quota"` and `"skipped-throttle"` each have their own separate
  STREAK check, below. Three or more CONSECUTIVE `status: "skipped-quota"`
  heartbeats for one label also flag `job-failed` (read directly off the current heartbeat's own
  `consecutive_quota_skips` counter, described above — no separate state file) — the account's quota
  exhaustion has outlasted the job's own same-night retry slot and needs a human to look; one or two
  skips in a row is ordinary and not flagged. **#5922 fix round, BLOCKER 1: the identical
  three-or-more rule applies to `status: "skipped-throttle"`'s own `consecutive_throttle_skips`
  counter**, with a different reason string ("server-side throttle, not quota; check concurrent
  load, runtime CLAUDE.md §9") — a long, unbroken throttle streak is evidence of sustained
  concurrent load against the account (another session, or a runaway fan-out sharing the same
  rate limit), not quota exhaustion, and previously alerted nobody at any length.
- **`unexpected-loaded`** — the MIRROR of the pre-existing `expected-but-unloaded` check in the
  opposite direction: a label present in `launchctl list` right now whose §2 table `expected_state`
  column is present but is NOT `"loaded"` (e.g. a not-yet-activated wheel plist that was
  `launchctl load`ed by hand without the table ever being updated to match). A label whose
  `expected_state` is missing/unparseable is never flagged either direction, same convention as
  every sibling check.

**A third finding class (WS14-S1 item 1c, GH #4767), wheel labels only, REPORT-ONLY — never added
to the watchdog's escalation set:** `wheel-grant-contradiction`. It fires when a wheel job's
`degraded_reason` — read from its LIVE heartbeat, or from any of its history lines from the last
48 hours — matches `<tool>-tool-unavailable` for a `<tool>` that IS present (case-insensitively) in
`wheel_launch_context.TOOLS` (read fresh in `_gather`, inside a try/except that never raises). This
is the exact 09-27 root-cause shape: a session probed a genuinely GRANTED tool with ToolSearch,
found nothing (because it's a DIRECT grant, never deferred), and reported it "unavailable" — a
contradiction between what was granted and what the session claimed, worth a human's later look, not
a job that stopped running. The last-48h history scan exists because the 03:30 retry slot overwrites
the primary slot's own live heartbeat file before the 05:10 daily audit ever runs, so a primary-slot
contradiction would otherwise be invisible to a same-morning audit.

## Concurrency guard (the wheel's own lock)

THE ISSUE WHEEL is the one job on this shared wrapper that can genuinely collide with itself: a
nightly `com.oversight.wheel.<slug>` fire and an on-demand `/wheel <slug>` invocation both build,
commit, and close against the *same* repo, and running two at once risks leaving an
applied-but-uncommitted patch mid-lane. `run_oversight_job.sh` (THE ISSUE WHEEL hardening plan, H3)
closes this with a **refuse-don't-replace** lock, scoped by repo slug (`~/.claude/schedules/locks/
<slug>.lock`), not by job label — the nightly and on-demand paths write different labels but the same
repo, so the lock has to cover both. It is a complete no-op for every one of the other jobs sharing
this wrapper: only an invocation that exports `WHEEL_SLUG` (the wheel's own plists, and `/wheel`)
takes the lock at all.

**The lock is a DIRECTORY, not a file** (`<slug>.lock/`, containing an `owner.json` payload) — a
round-2 hardening fix, replacing an earlier file-based write-then-link design whose STALE-RECLAIM
branch was a genuine TOCTOU race (falsified live: 0/150 clean trials with 3 real, distinct-PID
contenders racing a stale lock — two contenders could each independently decide "stale," and the
second's unconditional unlink could delete the first's freshly-reclaimed, live, valid lock).
`os.mkdir` is the sole primitive this design trusts for exclusivity (atomic even across NFS, unlike
file-creation edge cases): the initial acquisition attempt is a bare `os.mkdir(lockdir)`, with the
owner payload written *inside* the directory only after the mkdir itself succeeds, so nothing is
ever observable at the lock's name except a directory whose creator has already won.

The stale-reclaim branch is where the real fix lives. A contender that finds an existing, stale lock
does **not** unlink or rename it directly — it first contends for a **separate, exclusive
`<slug>.lock.reclaiming` marker** (via the identical `os.mkdir` test-and-set). A contender that loses
this marker race never touches the lock directory at all; it refuses, reporting that another process
is actively handling reclaim. Only the marker-winner re-verifies staleness (the original lock may
have been released cleanly in the meantime) and then performs `os.rename(lockdir, quarantine)` —
atomic, and by construction the *sole* process that can ever be attempting **this rename**, since
every other *reclaimer* is blocked behind the marker. This does not extend to the recreate that
follows: a *fresh* acquirer (one that never needed to reclaim anything, so never contended for the
marker at all) can win that recreate's own `os.mkdir` the instant the name is freed — a real,
reproduced race (confirmed at ~1/6 trials under N=8 contention), closed by treating that
`FileExistsError` as ordinary held-lock contention rather than a real I/O error, exactly like every
other acquisition attempt. The marker itself carries its own owner pid, so a marker-holder that
dies (SIGKILL) mid-reclaim doesn't leak a
*permanent* block on all future reclaims for the slug: a later contender that loses the marker's own
mkdir race checks whether the marker's recorded owner is dead and, if so, reclaims the marker itself
the same test-and-set way — a second, smaller instance of the identical pattern, bounded by "however
long one reclaim sequence takes," never by the lock's own alarm ceiling. Verified by direct execution
(3 distinct-PID contenders unless noted): 150/150 clean trials at N=3, 100/100 clean at N=8, 30/30
clean at N=12 — exactly one acquisition every time, racing from cold against a genuinely stale lock.

A held, live lock refuses the new run outright: fail-fast heartbeat, `exit: 75` (EX_TEMPFAIL), naming
the holding pid — never killed-and-replaced, since killing a run mid-lane is exactly what risks an
orphaned patch. A lock whose recorded pid is dead, or whose age exceeds its own recorded alarm
ceiling (a parent-SIGKILL can orphan a still-live child, so "pid exists" alone isn't proof of a
genuinely progressing run), is reclaimed via the marker-gated sequence above. A named, explicit
override (`CSA_WHEEL_FORCE_UNLOCK=1`) lets the operator skip the TTL wait after killing a hung run by
hand; the reclaim is recorded (`lock_force_reclaimed: true`) rather than silent.

**A refused run's heartbeat is loud, not merely fresh.** Its `exit: 75` still needs a well-formed,
fresh `finished_at` (every heartbeat does), which on its own would read as an ordinary clean finish
to every liveness check in `heartbeat_audit.py` — none of them reads `exit`. `heartbeat_audit.py`'s
own `lock-refused` check closes that: it flags any finished heartbeat carrying `exit: 75` by name, so
a lock that's silently starving a slug (a dead holder, or a genuinely stuck run) doesn't hide behind
a heartbeat that merely looks recent.

## The wheel launcher (GH #4767)

A headless `claude -p --permission-mode acceptEdits` session could not do what the wheel prompt
asked of it: it could not read `~/.claude` without a grant, could not read its own env in Agency,
could not run the `Workflow` tool in Agency, and nearly every ordinary write under a `.claude`
directory is refused by the CLI as a "sensitive file" whatever the grants (the full permission
model, including the two exceptions, the CLI's own auto-memory dir and CSA's heredoc gap, is in
[`knowledge/oversight_install.md`](../../knowledge/oversight_install.md) §1). So, for the two wheel
jobs — identified by a **label guard**, not bare `WHEEL_SLUG` presence: a job label matching
`com.oversight.wheel.*`/`manual-wheel-*`, or a prompt file named `issue_wheel.txt`, that reaches the
wrapper with `WHEEL_SLUG` unset or empty refuses outright (`hard_stop: "wheel-slug-missing"`, exit
79, claude never launched) instead of silently taking the unrestricted non-wheel branch below — a
genuinely non-wheel job (any other label, any other prompt file) still takes that branch exactly as
before, unaffected by this guard — `run_oversight_job.sh` now owns everything decidable before
launch:

1. **Wheel-label guard, first of all.** Refuses before the kill switch, the lock, the prompt load
   or any `claude` call when the label or prompt file looks like a wheel job but `WHEEL_SLUG` is
   missing (`hard_stop: "wheel-slug-missing"`, exit 79) — see above.
2. **Kill switch.** Bash `[ -e ]` on `~/.claude/schedules/DISABLED` (appends the shared
   `_disabled_window.jsonl` line) and `DISABLED.wheel.<slug>`, before the lock, the prompt load, the
   quota pre-flight or any `claude` call. A hit writes `status: "skipped-disabled"` (`hard_stop` `"1"`
   or `"2"`), exit 0.
3. Lock, prompt load, browser-pool prime and second-slot skip, unchanged.
4. **`hooks/wheel_launch_context.py`** (python3, TCC-safe under launchd) runs HARD STOPs 3/4/4b, the
   settings checks and the python3 precondition, and reads HARD STOPs 6/7, `wheel_repos.json` and
   the env. A failure writes `status: "failed"`, `exit: 79`, a typed `hard_stop`, and nothing is
   launched; a helper crash or silence fails closed (`hard_stop: "launch-context-error"`). On success
   it writes a nonce-delimited WRAPPER CONTEXT block (with PREAMBLE OVERRIDES) followed by
   `_preamble.txt`, which the wrapper prepends to the prompt, and the wheel's exact CLI flag tail —
   read into `"$@"` immediately after the helper's non-empty check passes, validated as a non-empty
   token list starting with `--add-dir`, and re-asserted at the exec site (BLOCKER B1 fix): a
   missing/emptied/malformed `argv.txt` between the check and the exec fails closed
   (`hard_stop: "launch-context-error"`) instead of exec'ing `claude` with an unrestricted flag
   tail. One of the 4-env-adjacent checks refuses outright (`hard_stop: "fix-close-not-granted"`)
   when `WHEEL_FIX_ENABLED` or `WHEEL_CLOSE_ENABLED` is not `"0"`: this launcher's grant set below
   is triage-only, so a plist flip to `1`/`1` ahead of a matching launcher change would otherwise
   park a session's fix/close lanes mid-run instead of failing before any API call.
5. Quota pre-flight, unchanged.
6. **START heartbeat**, written by the wrapper; then `claude -p` with the flag tail.
7. Post-run END verification and stamps, unchanged; the EXIT trap removes the private context dir
   and the run scratch dir, and appends the run's history line (below).

**Per-night history (WS14-S1 1b, GH #4767, 2026-09-27).** Every job that runs through the wrapper
gets one line per exit in `schedules/heartbeats/history/<label>.jsonl` (gitignored), not only the
wheel.

How it is written:
- The one `_wrapper_exit_cleanup` trap does it, never a second trap (`trap` replaces rather than
  stacks). The order is: stamp `lock_force_reclaimed`, run `hooks/wheel_history.py append`
  (time-bounded, never-raise, `|| true`), then release the lock. So no later run can overwrite the
  heartbeat before it is read, and a failed append never changes the job's exit code.
- The appender is found relative to the wrapper's own location (`WHEEL_HISTORY_PY`). A copy of the
  wrapper moved somewhere without `../hooks/wheel_history.py` beside it writes no history, silently.

When there is no line, or a stub line:
- The early `${1:?}`/`${2:?}` argument aborts and a SIGKILL write none.
- A SIGTERM mid-run writes the START stub.
- The kill-switch, lock-refused, wheel-slug-missing and second-slot-skip exits each write one line.
- A `/wheel` run writes `manual-wheel-<slug>.jsonl`, which never counts as a scheduled night.

The line is the heartbeat plus these wrapper fields:
- `launch`: `manual` or `scheduled`, from the label.
- `stale`: wheel labels only; true when the heartbeat's `started_at` is not this run's own start.
- `ready_json_mtime`: from `telemetry/wheel/$WHEEL_SLUG/ready.json`.
- `slot` and `night`: scheduled `com.oversight.wheel.*` labels only, by local wall-clock time at the
  run's start. [20:00, 24:00) is `primary` for that date; [00:00, 08:00) is `retry` for the
  previous date; anything else is `offschedule` with a null `night`. Other jobs get null slot and
  night.

Also:
- The wrapper never writes `trigger`; the session owns it.
- A failed append's stderr lands after the main run, so `.err.log`'s mtime moves. That is the same
  effect as the fail-fast step already has.
- There is no rotation. A line is about 1-3 KB per run.

**Green nights and the streak CLI (WS14-S1 1c, GH #4767).** `hooks/wheel_history.py`'s
`green_nights(job, since, ...)` evaluates every scheduled night for a job from `since` through the
most recent scheduled night that is due to be evaluated, and
`python3 ~/.claude/hooks/wheel_history.py streak --job com.oversight.wheel.csa --since 2026-09-28`
(the first scheduled night is Monday — the CSA plist has no Sunday rule) prints the same evaluation
from the CLI. A `(job, night)` is **green** when the history holds a record for that night with
`launch == "scheduled"`, no `wrapper_skip`, not `stale`, `status == "ok"` and `exit == 0`, and
**triage ran** — the one definition used everywhere: the heartbeat's `triage` is an object, its
`status` key (if present at all; a real run's `triage` is the Workflow's own `totals`, which never
carries a `status` key) is never the literal `"not-run"`, and `triage.triage_batches.total >= 1`
and `.ok >= 1`. A retry-slot record counts too, labelled `slot: retry`; a `manual-*` history file is
never read for streak purposes. The **scheduled nights** a streak walks are the calendar dates whose
PRIMARY-slot rule (`Hour` in `[20, 24)`) fires, read straight from the job's own installed plist
(`heartbeat_audit._read_plist_calendar_interval`, the calendar-exact ground truth, never the §2
table's cadence text) — so Friday to Monday is consecutive for the Mon-Fri CSA wheel, since Saturday
and Sunday were never scheduled nights in the first place. A scheduled night with no line breaks the
streak. Reported problems: a malformed history line, a scheduled night with no line at all, and a
green-looking record (status ok, exit 0, no skip, not stale) that carries no `triage` key whatsoever.

**Pending nights (B1 fix round, WS14-S1 1c).** A night is not judged final the instant its
calendar date arrives — its own RETRY window (00:00-08:00 local the following calendar day) has to
close first, since a primary-slot failure can still be rescued by that night's retry. A scheduled
night is **PENDING** until `night + 1 day` at **08:00 local** `<= now` (`green_nights`'s own `now`
parameter, a naive local `datetime`, defaults to the real local clock and is overridable for tests).
A pending night is reported as pending — never green, never a "no history line" problem (there may
genuinely be no line yet), and it is **excluded from the streak walk entirely**: it neither breaks
nor extends the streak. Before this fix, `green_nights` evaluated straight through "today" with no
completeness notion at all, so tonight's own scheduled night read as "missing" — breaking the
streak to 0 — from midnight until its 03:30 retry actually closed it out, for most of every day.

**What the session can reach (in short; residuals included).** The launcher can only subtract from
what the user and repo settings already allow:
- removed outright: every MCP server (`--strict-mcp-config` with an empty `--mcp-config`) and every
  built-in tool except `Bash, Read, Write, Workflow, TaskOutput, TaskStop, PushNotification,
  ToolSearch` (`--tools`);
- denied by `//` Edit/Write rules over `~/.claude/**`, the WHOLE of `~/` (BLOCKER B2, fix round),
  the repo and every other `additionalDirectories` entry: Write-tool writes and plain redirects
  there (in Agency, which has no bare `Bash` allow, the heredoc form below is refused as well). The
  `~/.claude/**` rule is whole-tree on purpose: it is the only thing stopping the
  session writing its cwd's live auto-memory (`~/.claude/projects/<cwd-slug>/memory/`), which the
  CLI otherwise lets the Write tool and redirects write with no grant. Never narrow it to
  per-subtree denies. The whole-`~/` pair (B2) closes the Write tool's reach to anything under
  `$HOME` that no `//` deny names — the round-3 probe measured this open in CSA before the fix
  (`<HOME>/.ssh/authorized_keys`, a new repo elsewhere under `<HOME>/Desktop`,
  `<HOME>/.config/gh/hosts.yml`, a new `~/Library/LaunchAgents` plist). **It does NOT narrow the
  Write tool's reach OUTSIDE `$HOME` (trust re-review round 4, R4Xc): the Write tool still creates
  and overwrites files in the `TMPDIR` siblings of RUN_SCRATCH, and the same rule, not yet probed,
  applies to `/opt/homebrew`, `/Applications`, `/Users/Shared`, `/private/tmp` — a real, named
  subset of the python3/bare-Bash residual (#5902), not closed here.** Fourteen `Read(//...)`
  denies (`~/.claude/gate-secrets/**`, `~/.ssh/**`, `~/.config/**`, plus eleven more added round 4
  as defense in depth: `~/.aws/**`, `~/.netrc`, `~/.docker/**`, `~/.gnupg/**`, `~/.kube/**`,
  `~/.npmrc`, `~/.pypirc`, `~/.git-credentials`, `~/.claude.json`, `~/Library/Keychains/**`,
  `~/.claude/.model_exceptions/**`) close those specific paths — the same probe's Read tool had
  opened `gate-secrets/hmac.key`; other gate ledgers (`.review_state/last_reviewed`,
  `.file_claims`, `.enforcement/log.jsonl`, `.agent_budget/spend.jsonl`, `.last_code_review`) and
  other home dotfiles stay readable in CSA unless listed above;
- allowed on top: one fresh scratch `--add-dir` (outside any `.claude` dir, removed at exit),
  `Workflow(issue-wheel-triage)`, `gh issue list/view`, `git -C <repo> status/rev-parse`,
  `git rev-parse/log/show`, and the sink by exact path;
  **`Workflow` is a DIRECT tool here, not a deferred one, so it never appears in a ToolSearch
  result; the prompt tells the session to call it directly and never to gate P1 on ToolSearch. A
  failed direct call (one corrected retry only when the error is the script's own `args`
  validation; a task stopped under RULE G4 follows G4 instead) writes the
  END heartbeat with `degraded_reason: "workflow-call-error"` and the error text in
  `workflow_error`, then STOPS (P4, P2 and P3 never run, so no second heartbeat can make the night
  look clean) (GH #4767, 2026-09-27: the 09-26 run misread an empty ToolSearch result as a missing
  tool and stopped before P1; a reduced-argv headless probe using the wheel's own
  `Workflow(issue-wheel-triage)` allow rule invoked the real script, and the attended run, WS14-S1
  acceptance S1-A1, is the pending end-to-end proof);**
  **the script itself (`workflows/issue-wheel-triage.js`) bounds a rate-limit storm inside a
  single Triage/Verify/Screen phase (GH #4767, WS14-S1 item 1d, 2026-09-27: S1-A1's attended run
  lost 23 of 25 batches — 24 Triage batches plus 1 Screen batch, not a single 25-batch Triage
  fan-out — to transient server-side 429s, tripping RULE G-BATCH-LOSS —
  `schedules/prompts/issue_wheel.txt`, not this doc): after a phase's first `parallel(...)`
  fan-out, ONLY the batches that came back null/malformed WITH NO THROWN ERROR are re-run ONCE, in
  waves of at most 4 concurrent — never a second full burst, and never a batch whose call actually
  THREW (a host stall or a missing-StructuredOutput error is a distinct failure mode from a 429,
  and retrying it would turn a slow failure into a compounding one instead of fixing a fast
  transient one). A batch failing both the first pass and its retry keeps BOTH reasons (joined by
  " | retry: "), with `(after retry)` appended once at the end — this applies uniformly to
  Triage/Verify/Screen; Screen's own `SCREEN_ERROR:` reason text is unchanged otherwise.
  `totals.triage_batches` gains two new additive keys, `retried` and `recovered` (batches re-run /
  batches that came back genuinely clean on retry — a Screen retry that returns a valid-but-empty
  `items: []` does NOT count as recovered, since Screen's own downstream loop still treats that as
  a failure) — `total`/`ok`/`failed`/`reasons` are unchanged in name and mean the state AFTER the
  retry. This bounds the retry's OWN contribution to wall-clock time (at most one extra attempt
  per null/malformed batch, at most 4 in flight); it does NOT by itself guarantee RULE G4's
  45-minute P1 budget is never approached — a 429 storm hitting both Triage and Verify in the same
  run can still consume a large share of that budget, and RULE G4 applies exactly as before if it
  does. Code review round 2 also fixed a pre-existing bug while touching this code:
  `dispatchScreenBatch` had no `.catch` (unlike Triage/Verify), so a thrown Screen agent() call
  reached the host's real `parallel()` as a rejected promise instead of a settled
  `{result: null, error}` value, which would have crashed all of P1 the first time a Screen call
  threw;**
- denied best-effort: 87 Bash families (widened from 51 by N1, fix round: `rm`, `cp`, `mkdir`,
  `git commit/push/worktree/config/remote/pull/fetch/merge/rebase/...`, `git log/show --output`,
  destructive `gh` verbs including `gh issue comment` and `gh ssh-key/config/...`, `gcloud`,
  `launchctl`, `curl`, ...);
- **not removable by flags**: **python3 is arbitrary code execution, not merely "writes anywhere"
  (N3, fix round)** — network egress and the operator's ambient credentials (`gh`/`security`
  subprocess calls, gcloud ADC) are in scope, and the wheel reads collaborator/agent-authored
  issue text unattended, so this is the residual that governs the wheel's real unattended-run risk
  (#5902; the narrower fix is F9, not yet built); in CSA the bare `Bash` allow still
  permits any un-denied command and evasion forms (absolute paths, `bash -c`, `git -C <repo>
  commit`), and a heredoc redirect whose body the CLI's analyzer bails on (JSON `{"`, `$(...)`)
  writes into `~/.claude` and the repo despite the `//` denies (measured 2026-09-24); in CSA, the
  bare Write/Read tool allows reach anything the `//` Edit/Write/Read denies above do not name (the
  same class of gap as bare Bash and python3 — B2 narrowed this to that same reach, it did not
  remove it); reads of every granted directory are not denied. The user-level PreToolUse gates
  remain the commit backstop.

**The sink** (`python3 ~/.claude/hooks/wheel_sink.py <kind>`) is the session's only sanctioned write
channel into `~/.claude`: `heartbeat --from F` (refuses `status`, a foreign `job`/`started_at`/
`cadence` and a caller-supplied `finished_at`; stamps `finished_at` for `"now"`, `written_via` and
`sink_version`), `patch`/`plan --name N --from F` (create-only), `patches-due`, `reap-patches
--closed N,...` (21-day floor) and `now` (the clock). `--from` files must live in the run scratch
dir. Every write appends to `telemetry/wheel/<slug>/sink_audit.jsonl`.

Non-wheel jobs are unchanged (argv, prompt, env), except that the empty-prompt exit now also prints
its `WRAPPER:` line.

## wheel_repos.json fields

THE ISSUE WHEEL per-slug config. Holds what a prose dossier cannot express mechanically. Read by
`~/.claude/schedules/prompts/issue_wheel.txt` (keyed by `WHEEL_SLUG`) and by
`~/.claude/commands/wheel.md`'s on-demand env-export step. Per-slug blocks are generated from each
repo's own `.claude/oversight/manifest.json` (`repo_manifest.py register`, `wheel_repos.json`'s
own `_comment` field points back here) — edit the manifest, not this file, and re-run `register`.

- **`tier0_statuses` / `tier1_statuses` — RETIRED (THE ISSUE WHEEL plan, Phase C item 4).** These
  fields, and the `--tracker-rel` CLI flag / `WHEEL_TRACKER_REL` plist env var they were meant to be
  wired against, pointed at a repo's launch-readiness/QA tracker HTML (`launch_readiness.html` for
  CSA, `launch-plan.html` for Agency). Both files were deleted 2026-09-16 when launch readiness moved
  to GitHub issues, and `hooks/issue_wheel_queue.py`'s `load_tracker_tiers()` was already failing soft
  to `{}` on every real run before that — the FIX-Q1 wiring described in the paragraph this replaced
  was never completed and is now moot. `--tracker-rel` is OPTIONAL on the CLI as of this commit
  (omitting it logs `tracker-disabled` once per run); `issue_wheel.txt`'s P4 command no longer passes
  it, and neither wheel plist carries `WHEEL_TRACKER_REL` any more. Every item now defaults to tier 2
  — the pre-FIX-Q4 behavior — with tiering left to a future feature if a tracker-equivalent signal
  ever returns.
- **`estimate_loop_exclusive_prefixes`** — FIX-Q1's per-slug `ESTIMATE_LOOP_EXCLUSIVE` prefixes;
  same **NOT-YET-WIRED** status — `issue_wheel_queue.py` still hardcodes the CSA-shaped prefix list
  directly (`ESTIMATE_LOOP_EXCLUSIVE`), per its own commit-2 scope note; CSA's value here is
  byte-identical to that hardcoded tuple so a future wiring commit changes nothing; empty for a
  repo with no such carve-out, e.g. Agency.
- **`trust_surface_prefixes`** — path prefixes that route lane review to `trust-architect` instead
  of `code-reviewer`, substitution not stacking; CSA's list is `CLAUDE.md`'s own quoted
  trust-surface paragraph, Agency's is the proposed-scope list in
  `.claude/oversight/trust-architect.md`, both verified to exist on disk as of the commit that
  wrote this field — Agency's is markedly wider because that dossier documents PHI/tenant-isolation
  surfaces the CSA `CLAUDE.md` paragraph's shorter money/auth framing does not enumerate. **THIS
  field IS read directly** by `issue_wheel.txt`'s own LANE RECIPE step (e).8.
- **`mandatory_registration_paths`** — LANE RECIPE (e).1's fourth IN-SCOPE UNION member — a path a
  new test dir must ALSO be registered into or nothing collects it; read directly by
  `issue_wheel.txt`.
- **`venv_python`** — the interpreter LANE RECIPE (d).5 uses, main-tree venv with the worktree as
  cwd/`PYTHONPATH`; read directly by `issue_wheel.txt`.
- **`board_regen_command`** — null when the tracker is hand-edited HTML with no regen script, as
  both CSA's `launch_readiness.html` and Agency's `launch-plan.html` are as of this writing; not
  yet consumed anywhere — reserved for when either tracker gains a regen script.

## The queue mechanism

Some jobs pass state to the *next* run of themselves rather than re-deriving it live. The clearest
example: `~/.claude/schedules/queue/product_qa.jsonl` — one line per detected staging deploy
(`{"revision": "...", "detected_at": "..."}`), appended by a deploy-drift watcher. The weekly
`com.oversight.csa.productqa` job drains this file down to the newest revision (and prunes entries
older than 30 days — it owns queue retention), then walks that revision as a customer persona via
`product-qa`. Without the queue, the weekly job would have no record of what revisions shipped
between its own runs.

## The watchdog

`com.oversight.watchdog` (THE ISSUE WHEEL hardening plan, H1) is a pure Python/shell liveness
supervisor — `~/.claude/schedules/run_watchdog.sh`, no `claude` CLI invocation anywhere in it, no LLM
session in the loop at all. It exists because every job above (`heartbeat_audit.py` included) only
ever *runs* as a pre-step inside a session that is already firing: if every launchd job silently
failed to load or fire, no session would ever run the audit in the first place, and nothing would
notice. The watchdog is the process outside that failure domain — it runs on its own launchd
schedule (08:10 daily), invokes `heartbeat_audit.py` directly, and escalates via a local `osascript`
alert (not `PushNotification`, which has no LLM-free call path) on exactly the finding classes that
mean "a job is not alive": `silent-job`, `loaded-never-fired`, `expected-but-unloaded`, `job-failed`,
and `unexpected-loaded` (the last two added THE ISSUE WHEEL plan, WS1-B.2 / Phase B item 2 — see
"Heartbeats" above for what each means) — plus its
own `watchdog-audit-failed` class when `heartbeat_audit.py` fails to run to completion at all (a
non-zero exit, distinct from the audit running cleanly and finding nothing). It writes its own
heartbeat (`com.oversight.watchdog.json`) so it's visible to the same liveness contract it enforces
on every other job, and honors the kill-switch (below) exactly like every other job.

**`expected_state` means intent, not observation.** `oversight_install.md` §2's job table column
`expected_state` records what a job's plist *should* be doing per the current rollout decision
(`loaded` or `unloaded`) — it is a declared target, set by whoever last made that rollout call, not a
live reading of `launchctl list`. `expected-but-unloaded` is precisely the mismatch between the two:
a row the table says should be `loaded` that `launchctl list` doesn't actually show.
`unexpected-loaded` is the mirror mismatch in the other direction: a row the table says should NOT be
`loaded` that `launchctl list` shows loaded anyway. Reading the
table alone never tells you the current real state — only the watchdog (or a live `launchctl list`)
does.

## Quota pre-flight and the second nightly slot

**THE ISSUE WHEEL plan, WS1-C.1 / Phase C item 1.** `run_oversight_job.sh`'s own out-logs showed
three distinct quota-exhaustion messages killing the wheel's nightly run mid-flight: a session-limit
message, a weekly-limit message, and a server-side rate-limiting message — so a fixed-time schedule
move alone would not have closed this (the account's quota state at 22:10 is not knowable from the
clock). Before the main `claude -p` invocation, the wrapper now makes one minimal, bounded
`claude -p` call using the SAME `--model` the main run uses, bounded to 60s with the wrapper's own
`perl -e 'alarm shift; exec @ARGV'` idiom (overridable via `CSA_WHEEL_PREFLIGHT_ALARM_SECONDS`,
tests-only). The probe's output is inspected when it exits 0, 1 or 142 (0 clean; 1 is the real CLI's
exit on a session limit, measured by the pre-flight on 2026-09-24 as `PREFLIGHT_DIAG exit=1`, and on a weekly
limit per the main-run logs; 142 the alarm kill). **A session/weekly-limit match and the server-side
throttle message (`Server is temporarily limiting requests (not your usage limit)`) are checked as two
SEPARATE patterns and get two SEPARATE statuses (#5922, follow-up to F6):** a session/weekly-limit
match writes `status: "skipped-quota"`; a throttle-only match (no session/weekly-limit text present)
writes `status: "skipped-throttle"` instead — both exit **70** and both skip the main run this slot, but
they carry independent streak counters (`consecutive_quota_skips` vs `consecutive_throttle_skips`) so a
run of server-side throttles can never inflate the quota streak `heartbeat_audit.py` check #9 reads. This
was a deliberate fix, not the original design: F6 originally folded the throttle message into the same
`skipped-quota` status because it also exits 1 and matches a limit-shaped pattern, but a throttle is not
quota exhaustion — the account's own usage limit is fine, the server is momentarily rate-limiting
requests — and three throttled nights in a row wrongly tripped check #9's "quota exhaustion has outlasted
this job's own retry slot" alert. **#5922 fix round, BLOCKER 1: `skipped-throttle` is
informational ONLY BELOW a streak of 3 — three or more consecutive `skipped-throttle` heartbeats
flag `job-failed` too, on `consecutive_throttle_skips` reaching the same threshold as the quota
streak, with the reason string "server-side throttle, not quota; check concurrent load" (see
`heartbeat_audit.py`'s own check #9 docstring) — a long, unbroken throttle streak is evidence of
sustained concurrent load against the account, not quota exhaustion, and previously alerted nobody
at any length.**
Deliberately never exit 75, which is this wrapper's
own `EX_TEMPFAIL`/lock-refused convention and would make `heartbeat_audit.py` flag a skip as a
stuck lock by name. A pre-flight that exits 1 WITHOUT a limit-text match (a network or auth error),
or that errors, times out, or exits non-zero for any other reason, FAILS OPEN — it proceeds to the main run exactly as if the pre-flight did not exist; only an
explicit limit-text match causes a skip. Skippable entirely via `CSA_WHEEL_SKIP_PREFLIGHT=1`
(tests-only, never a standing production posture).

**Output capture uses a temp FILE, never a pipe/`$(...)` command substitution** — found during this
commit's own falsifiability testing: when the probed `claude` binary (or a test double standing in
for it) forks a child before the alarm fires, SIGALRM kills only the directly-exec'd process; an
already-forked grandchild is orphaned and, if its output were captured via a pipe, would keep that
pipe's write end open indefinitely, defeating the alarm bound entirely (reproduced directly: a
`$(...)`-captured call hung for the child's full sleep duration, not the alarm's bound). Writing to a
regular file sidesteps this — a file write is never blocked by a lingering descendant holding it
open.

**Each wheel plist now carries a SECOND `StartCalendarInterval` slot** at 03:30 the following
calendar night (e.g. CSA's Mon-Fri 22:10 primary slot pairs with a Tue-Sat 03:30 retry slot) as a
same-night retry for a quota-exhausted primary run. The wrapper skips the second slot's main run
entirely — writing `status: "ok"`, `"wrapper_skip": "second-slot"` (WS14-S1 1b: the typed marker
green-night counting keys on, never the summary text) and a summary naming the skip, no CLI
invocation — when the
label's own existing heartbeat already shows `finished_at` on the same UTC calendar date with
`status: "ok"`; this degrades to "do not skip" (proceed normally) on any read/parse failure, since a
skip must never be inferred from data the wrapper cannot positively confirm. The pre-second-slot
plists are kept at `~/.claude/schedules/rollback/<label>.2026-09-20.plist` for rollback.

**Second-slot behavior, and what this page does not assert.** The 03:30 retry slot is an ordinary
`StartCalendarInterval` entry; whether an install has loaded it is per-install state and is not
stated here. A fire that finds a kill switch present (`~/.claude/schedules/DISABLED`, or the
per-job `DISABLED.wheel.<slug>`) takes a different code path entirely: the wrapper writes
`status: "skipped-disabled"` and never launches claude, so such a fire exercises none of the
second-slot skip logic above (the "does the earlier slot already show `status: "ok"` today" check)
and says nothing about it. Load state is never read from prose in this doc: §2's `expected_state`
column in `knowledge/oversight_install.md` is the declaration, `launchctl list` is the fact, and
`heartbeat_audit.py` diffs the two in both directions.

## Manual fallback

When schedules are down (kill-switch on, or you're troubleshooting), `/sweep` (the
`~/.claude/commands/sweep.md` slash command) runs the same fixed pre-steps plus one chosen dimension
by hand: `/sweep health|logs|cost|consistency|all`. It writes a `manual-*` heartbeat (`cadence:
"manual"`, exempt from cadence-staleness auditing) and files findings through the same board-steward
rules as a scheduled run. The wheel-wide kill-switch is `touch ~/.claude/schedules/DISABLED` — every
job, including the watchdog, checks it first and exits silently (appending a shared marker line to
`heartbeats/_disabled_window.jsonl` rather than writing its own heartbeat for that run); remove the
file to resume. The two wheel jobs' wrapper enforces it before launching claude and, in addition,
writes a `skipped-disabled` heartbeat and a `WRAPPER:` log line (GH #4767).

---

For full operational detail (exact schedules, install procedure, troubleshooting, the current
loaded/paused status of every job) see
[`knowledge/oversight_install.md`](../../knowledge/oversight_install.md).
