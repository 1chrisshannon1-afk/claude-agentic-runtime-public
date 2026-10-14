# Agent Pacer — cross-session parallel-agent admission control

A machine-wide controller that **staggers sub-agent launches** and **caps concurrency
across all sessions**, so a wide fan-out (or several sessions fanning out at once)
ramps up smoothly instead of hitting Anthropic's per-minute rate limits (chiefly
**ITPM** — input tokens/min) in the first second.

It lives in `~/.claude/hooks/agent_budget.py`'s `gate` subcommand and a shared
machine-wide ledger (`~/.claude/.agent_budget/`), so every session sees the same live
count and the same launch-token bucket. **Wiring note (2026-09-01, model-pin-enforcement
build; STATUS: WIRED LIVE 2026-09-03):** `settings.json`'s `PreToolUse:Task` hook now runs
`~/.claude/hooks/pretooluse_task.py`. History: the 2026-09-01 build's adversarial review
(six blockers, B1–B6) found the original cut agent-self-serve in practice, so the wiring
was reverted to `agent_budget.py gate` directly until the fix round was itself reviewed
clean — that review completed 2026-09-03 (and caught + fixed a fix-round method-polarity
regression in `block_prod_mutations.py` along the way), and the re-wire landed with it.
Live behavior: `pretooluse_task.py` runs `model_pin_gate.py` (gate T1: enforces
`knowledge/model_policy.json`'s `agent_pins`) first, then calls `agent_budget.py`'s
`gate` subcommand (T2, this pacer) UNCHANGED, only when T1 allows — a T1 deny means the
pacer never sees the dispatch at all. See `pretooluse_task.py`'s own module docstring for
the mechanics. Nothing else in this doc (the ledger schema, the pacer's own
config/safety properties, or its `gate`/`release_hook` subcommand behavior) is affected.

## The problem it solves

On Max 20×, firing 15+ agents simultaneously (or 3 sessions × 15) trips **per-minute**
rate limits instantly — every agent request carries a big context, so the synchronized
burst dumps millions of input tokens into one second → `429` storm → throughput
collapses, *even with plenty of 5-hour/weekly budget left*. The limit is a token
**arrival rate**, not an agent headcount. The pacer smooths the arrival rate.

## How it works

Two independent, machine-wide knobs, enforced atomically under a bounded lock:

- **Concurrency cap `C`** (`CSA_ANTHROPIC_CEILING`) — max simultaneous live agents across
  *all* sessions. A lease is claimed per spawn (keyed on `tool_use_id`) and released on
  finish; a second session's fan-out sees the first's leases and waits.
- **Launch-rate limiter** — a token bucket, `CSA_LAUNCH_RATE` tokens/sec with capacity
  `CSA_LAUNCH_BURST`. A 15-wide burst drains as: `BURST` admitted immediately, the rest
  gated ~1 per `1/RATE` seconds. That is the anti-ITPM-spike stagger.

When blocked, the hook waits (releasing the lock, sleeping with jitter) up to
`CSA_ADMIT_MAX_WAIT_SEC`, then denies with a "reduce fan-out" message. **Everything fails
open**: a wedged lock, a missing bucket, or any error admits the spawn rather than
freezing a session.

## Configuration

| Env var | Default (code) | Recommended for Max 20× | Meaning |
|---|---|---|---|
| `CSA_PACER` | *(off)* | `1` | Master enable. OFF = legacy read-only advisory count. |
| `CSA_SPEND_LEDGER` | *(on)* | *(on)* | Independent of `CSA_PACER` (never affects admission). Governs whether `gate`/`release_hook` read stdin at all (see "Reading stdin by hand" below) AND the real spend ledger itself (Phase 0 step 2, `~/.claude/plans/churn_phase0_measure.md`): `gate`'s claims.jsonl claim recording, `release_hook`'s claim/pending-stop/spend.jsonl three-event join, and the `spend` subcommand's reap pass. Set to the literal `0` to turn all of it off. |
| `CSA_CLAIM_TTL_SEC` | `21600` (6h) | `21600` | Claim/pending-stop reap window — a claims.jsonl/stops.jsonl row older than this with no matching release is written to spend.jsonl flagged `unreleased: true` and removed. Distinct from `CSA_LEASE_TTL_SEC` below (the PACER's own, much shorter, lease staleness). |
| `CSA_ANTHROPIC_CEILING` | `8` | **`24`** | Machine-wide concurrent-agent cap `C`. |
| `CSA_LAUNCH_RATE` | `2.0` | `2.0` | Launch tokens/sec (the ramp slope). |
| `CSA_LAUNCH_BURST` | `4.0` | `5.0` | Immediate burst before staggering kicks in. |
| `CSA_ADMIT_MAX_WAIT_SEC` | `30.0` | `30.0` | Max wait for a slot before denying (keep ≪ hook timeout). |
| `CSA_ADMIT_POLL_SEC` | `0.25` | `0.25` | Poll interval while waiting at the cap. |
| `CSA_LOCK_TIMEOUT_SEC` | `2.0` | `2.0` | Max wait for the admission lock, then fail open. |
| `CSA_FANOUT_THRESHOLD` | `40` | `40` | WS2.2 fan-out observer: a session REACHING this many admitted dispatches (fires at `count == threshold`, not above it) logs ONE `fanout-session-high` line to `.enforcement/log.jsonl`. **Pure observer — never denies, never delays.** Its own lock wait is capped at `FANOUT_LOCK_TIMEOUT` (0.1s), deliberately far below `CSA_LOCK_TIMEOUT_SEC`: it is the third lock acquisition on the admitted path with the pacer ON (the second with it off), and at the full budget it stacked onto the others for a measured 4.01s → 6.01s (+50%) worst-case stall on every dispatch (2.00s → 4.02s with the pacer off). Under contention it SKIPS the count (logging `spend_ledger_lock_timeout`) rather than wait. Reported as churn metric 8. |
| `CSA_LEASE_TTL_SEC` | `3600` | `900` | Stale-lease reap age (crash safety net). Lower = leaked leases free sooner; a genuinely >TTL agent may be mildly over-admitted. |

The code defaults stay conservative on purpose. The Max-20× column is the **starting
point** — calibrate against your real limits (below), then set the values you land on.

## Enabling (needs a fresh session + opt-in)

The pacer only *acts* when both are true:

1. **`CSA_PACER=1`** is in the hook's environment, and
2. **`_lib.enforcing()`** is true — i.e. `CSA_ENFORCE=1`, or the global marker
   `~/.claude/.enforce` exists, or the project has `.claude/.csa-enforce`.

Recommended one-time enable (governs every project/session):

```sh
# 1. Turn enforcement on globally (or rely on a per-project .claude/.csa-enforce)
touch ~/.claude/.enforce
# 2. Set the pacer env for your shell / launch profile (persist in your shell rc)
export CSA_PACER=1
export CSA_ANTHROPIC_CEILING=24
export CSA_LAUNCH_RATE=2.0
export CSA_LAUNCH_BURST=5.0
```

Alternative (the route actually used since 2026-08-31): set the same variables in
`~/.claude/settings.json`'s top-level `"env"` block — `{"CSA_PACER": "1",
"CSA_ANTHROPIC_CEILING": "24"}` — which applies to every session without shell-rc edits.
Settings-env changes take effect in NEW sessions only; verify from a fresh session with
`python3 ~/.claude/hooks/agent_budget.py status` (expect `pacer_enabled: true`, `ceiling: 24`).
Never enable the pacer without also setting the ceiling: the default ceiling of 8 against this
machine's measured peak concurrency (~23-25) would hard-deny roughly 1 in 7 dispatches on
saturation timeout rather than stagger them.

**Release hooks** (so claimed leases free on finish) must be wired in
`~/.claude/settings.json` alongside the existing `PreToolUse:Task` gate — merge these
into the `PostToolUse` and `SubagentStop` arrays:

```json
{ "matcher": "Task", "hooks": [
  { "type": "command",
    "command": "[ \"${CSA_DISABLE_HOOKS:-0}\" = \"1\" ] && exit 0; python3 ~/.claude/hooks/agent_budget.py release_hook" } ] }
```

(`PostToolUse` takes the `"matcher": "Task"` form above; `SubagentStop` takes the same
`hooks` entry with no matcher.) Both fire for the same call as belt-and-suspenders —
releasing a lease twice is idempotent, and a lease that never releases (crash) is reaped
by `CSA_LEASE_TTL_SEC`. `release_hook`'s **pacer-lease release** (the thing this section
is about) is a no-op unless `CSA_PACER=1`, so wiring it is safe even before you enable —
but `release_hook` is NOT a full no-op with the pacer off: it still reads stdin by
default (`CSA_SPEND_LEDGER` defaults ON, decoupled from the pacer — see the
Configuration table) and, as of Phase 0 step 2, drives the real spend ledger's
claim/pending-stop/spend.jsonl join from that same read. That write touches only
claims.jsonl/stops.jsonl/spend.jsonl — never a lease and never admission.

Settings changes and env take effect in **new** sessions (hooks read env per spawn, but
`settings.json` hook wiring is read at session start). Start a fresh session to activate.
To turn it off instantly anywhere: `export CSA_PACER=` (unset) or `CSA_DISABLE_HOOKS=1`.

## Calibrating to your real limits

There is no published ITPM number for a Max 20× subscription, so calibrate empirically —
the onset of throttling is the signal:

1. Enable the pacer with the Max-20× starting values above.
2. Run progressively wider fan-outs (10 → 15 → 20 → 30 agents at once) on real work.
3. Watch for the harness backing off / `429`s (agents stall and retry). The concurrency
   just **below** where backoff starts is your true `C`.
4. Cross-check token throughput with `ccdash` — the shared usage DB
   (`~/.claude/usage-dashboard/data/dashboard.db`) records per-message input/output
   tokens with timestamps. Minute-bucket `usage_events` (same shape as
   `trends.hourly_totals()`, floored to the minute) to see your sustained input
   tokens/min; set `C` so concurrent big-context agents stay under it, and `RATE`/`BURST`
   so a burst's instantaneous input-token arrival stays under it.
5. Set `CSA_ANTHROPIC_CEILING` (and `RATE`/`BURST` if needed) to the values you land on.

Note: `ccdash` captures token counts, **not** `429`s — the throttle onset is observed
from harness backoff during the ramp, not from the DB.

## Observability

```sh
python3 ~/.claude/hooks/agent_budget.py status   # JSON: live_leases (all sessions),
                                                 # launch_tokens_available, pacer_enabled, …
python3 ~/.claude/hooks/agent_budget.py doctor   # human-readable health + config
python3 ~/.claude/hooks/agent_budget.py reset    # clear stale/corrupt leases + markers
python3 ~/.claude/hooks/agent_budget.py spend --by agent|model|day [--since YYYY-MM-DD]
                                                 # reap stale claims/pending-stops, then
                                                 # print a quick spend table from
                                                 # spend.jsonl (churn_report.py's spend
                                                 # metrics are the rigorous, dedup-aware
                                                 # version of this same ledger)
```

`live_leases` is the machine-wide count across every session — the number to watch when
several sessions run at once.

### `.agent_budget/` contents

- `lease-*` — one file per live pacer lease (only written when `CSA_PACER=1` admits a
  spawn); `bucket.json`/`admission.lock` — the pacer's shared token-bucket state and its
  bounded, non-blocking lock. As of 08-25 round 5 (R11) a lease file also gains a
  `dispatch_agent_id=` line once `PostToolUse(async_launched)` resolves the real subagent
  `agent_id` for it — independent of `CSA_SPEND_LEDGER` (see "Safety properties" below) —
  so a later `SubagentStop` (which never carries `tool_use_id`) can resolve and release
  the correct lease from the lease files alone, never claims.jsonl.
- `pacer-pending-stop-*` — a PACER-only marker (never a spend-ledger table), written when
  a `SubagentStop` arrives before its own `async_launched` has annotated a lease yet (the
  C -> S -> A ordering). Lets the eventual `async_launched` call release the lease
  immediately once it learns the mapping, instead of leaking it. Self-heals on the same
  `CSA_LEASE_TTL_SEC` schedule as a stale lease (`prune_and_count`); an operator-invoked
  `reset` also sweeps every marker unconditionally, regardless of age (N3, 08-25 round 5)
  — markers are pure housekeeping, so a hard reset clears them all, not just the stale ones.
- `claims.jsonl` — one row per OPEN spend-ledger claim (appended at `gate`, annotated
  with `agent_id`/`model` at `PostToolUse(async_launched)`, removed on release or reap).
  Real and written by default (`CSA_SPEND_LEDGER` on) as of Phase 0 step 2. `record_claim`
  upserts on `tool_use_id` (08-25 round 4) — a duplicate gate firing for the same call
  replaces the existing row rather than appending a phantom second one.
- `stops.jsonl` — one row per OPEN pending record, `kind`-discriminated (08-25 round 4,
  B1): `kind: "stop"` (the original shape — also the default for any legacy on-disk row
  with no `kind` field at all) is always persisted by `SubagentStop`; `kind: "completed"`
  is persisted by `PostToolUse(completed)` when SubagentStop hasn't arrived YET (the
  "gate -> completed -> stop" ordering) instead of writing a spend line with no
  transcript. Both kinds share this one table so `reap_stale`'s existing sweep covers
  either without a fourth reap stage; both consume on join.
- `spend.jsonl` — append-only, one line per dispatch, the canonical schema from
  `~/.claude/plans/churn_phase0_measure.md` step 2 (plus an additive `join_state` field,
  08-25 round 4 — see the module docstring; a stale claims.jsonl row reaped with no
  stop/completed ever joining it reads `join_state: "claim-only"`, renamed 08-25 round 5
  (N8) from the ambiguous "claim-consumed" still used elsewhere in the schema for a
  genuinely different case — see `reap_stale`'s own docstring for the full distinction).
  Read by `churn_report.py`'s spend metrics (step 5) and by this module's own `spend`
  subcommand. N9 (08-25 round 5): for a `join_state: "no-claim"` line, `duration_ms` is
  measured from that event's own `async_launched` annotation time (never a real gate-time
  claim, which never existed) to the stop — an UNDER-report of the true end-to-end
  duration; filter on `join_state == "no-claim"` before trusting that field at face value.
  **WS2.1 step 4 (2026-09-20, #5828):** a still-null `model` at SubagentStop join time
  (every Workflow-tool leg's shape, since no `PreToolUse:Task` claim is ever taken for one)
  is filled from the agent transcript's own `message.model` field (`model_from_transcript`,
  **regular files only** — bounded to `MODEL_TRANSCRIPT_MAX_BYTES` = 2MB, tail-read only,
  never the whole file; a non-regular path (FIFO, device, directory) is refused via
  `os.stat`/`stat.S_ISREG` before any `open()` call, fixed 2026-09-20 after a review found the
  original `os.path.getsize`-based check silently unbounded on a character device), and the
  line carries `"model_source": "transcript"` when it does. A row whose model came from the
  normal dispatch-time path is untouched (no `model_source` key added at all) — see
  `docs/subsystems/telemetry-and-spend.md`'s own "Observed-model recovery" section for the
  full mechanics, join-site list, and exception posture.
- `spike_payload.jsonl` — a leftover Phase 0 step-1 spike artifact (the throwaway
  `CSA_SPIKE_DUMP=1` capture that verified the real hook payload shapes before step 2's
  claims/stops/spend join was built against them). No longer written by anything in this
  module; kept on disk only as the historical record those shapes were verified against.
- `release_hook` runs a reap pass (`reap_stale`, gated on `CSA_SPEND_LEDGER` — see D11
  below) on EVERY invocation, before its own event join — so a stale claim/pending-stop
  is swept as a side effect of ordinary traffic, not only via the `spend` subcommand.
  (08-25 round 4: the `spend` subcommand's own reap pass is now ALSO gated on
  `CSA_SPEND_LEDGER` — it silently ran unconditionally before, contradicting this same
  doc's own claim above.)

### Reading stdin by hand

Both `gate` and `release_hook` now read stdin whenever `CSA_PACER=1` **or**
`CSA_SPEND_LEDGER` is on (the latter defaults ON, decoupled from the pacer — see the
Configuration table). Running either subcommand by hand at a terminal, with no piped
input, therefore **blocks waiting on stdin** unless you explicitly close it:

```sh
python3 ~/.claude/hooks/agent_budget.py gate < /dev/null
python3 ~/.claude/hooks/agent_budget.py release_hook < /dev/null
```

`status`/`doctor`/`reset`/`claim`/`release`/`browser_pool` never read stdin and are
unaffected.

## Safety properties

- **Fails open everywhere.** Lock unacquirable → admit. Missing/garbage bucket → treat as
  full → admit. Any exception → exit 0 → spawn proceeds. A pacer outage never wedges a
  session; the 600s-ish hook timeout is a second net (a killed hook proceeds).
- **OFF by default (admission).** With `CSA_PACER` unset, `gate` is the legacy read-only
  advisory count and nothing is claimed/admitted for the PACER's own lease/concurrency
  cap. The DEFAULT-ON `CSA_SPEND_LEDGER` is a SEPARATE, decoupled system: it still makes
  both `gate` and `release_hook` read stdin regardless of `CSA_PACER` (see "Reading stdin
  by hand") and, as of Phase 0 step 2, writes real claims.jsonl/stops.jsonl/spend.jsonl
  rows from that read — but that write never claims a pacer lease, never consults the
  concurrency cap, and never affects admission either way.
- **Unique per-invocation keys.** Leases key on `tool_use_id`, so two concurrent
  same-type agents never collapse onto one lease (the concurrency cap stays correct).
- **Lock is never held across a sleep** — waiters release before sleeping, so one waiter
  can't block the machine.
- **The lease releases ONLY on a REAL finish — `PostToolUse(completed)` or
  `SubagentStop` — never on `PostToolUse(async_launched)`** (08-25 round 4, R9). The
  original spike-era code released unconditionally on any `release_hook` firing that
  carried a `tool_use_id`; for a background dispatch that firing is
  `async_launched`, which fires the instant the Task launches — so the lease (and the
  concurrency slot it represents) freed within milliseconds of dispatch, not when the
  subagent actually finished minutes later. That silently defeated the whole point of
  `CSA_ANTHROPIC_CEILING` for every background dispatch: the ledger always showed
  near-zero `live_leases` no matter how many agents were genuinely still running.
- **Lease<->dispatch resolution never reads the spend ledger** (08-25 round 5, R11,
  replacing R9's own claims.jsonl-based lookup, which turned out to leak). `SubagentStop`
  never carries `tool_use_id` (see the module's own `classify_release_event` docstring),
  so releasing it needs a resolved mapping from the real dispatch `agent_id` back to the
  lease's own key (its `tool_use_id`). R9 resolved that by scanning the still-open
  spend-ledger claim's `agent_id` in `claims.jsonl` — which leaked EVERY background lease
  whenever `CSA_SPEND_LEDGER=0` (that table is simply never written in that mode) and
  ALSO leaked under the C -> S -> A ordering (a fast subagent's `SubagentStop` arriving
  before its own `async_launched` had annotated the claim yet — proven live, not
  hypothetical). Fixed at the root: `PostToolUse(async_launched)` now writes a
  `dispatch_agent_id=` line directly into the pacer's OWN lease file (independent of
  `CSA_SPEND_LEDGER`); `SubagentStop` resolves its lease by scanning those lease files for
  a match, never claims.jsonl. For the C -> S -> A ordering specifically, it instead
  leaves a small pacer-only `pacer-pending-stop-*` marker file (also independent of the
  spend ledger); the eventual `async_launched` call finds that marker and releases the
  lease immediately instead of merely annotating it. Both the lease annotation and the
  marker self-heal via the SAME `CSA_LEASE_TTL_SEC`-scale sweep `prune_and_count` already
  performs for stale leases — a leftover of either kind ages out on its own, never
  immortal.
