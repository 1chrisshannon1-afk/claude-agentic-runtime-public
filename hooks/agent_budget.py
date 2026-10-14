"""agent_budget — machine-wide concurrency accounting for parallel sub-agents.

Ported from ~/.claude/scripts/agent_budget.sh. Leases are files under
~/.claude/.agent_budget/ keyed by a sanitized agent_id. The ledger is a
COOPERATIVE advisory accounting: it FAILS OPEN on any unreadable/corrupt state,
self-heals (prunes stale/malformed leases), and NEVER blocks a tool call via an
exit code — a deny is only ever expressed as a JSON object on stdout.

Subcommands:
  status              cores, 1-min load, ceiling, live lease count, recommended
                      additional slots (default when no subcommand). Emits JSON.
  claim <agent_id>    create/refresh a lease for agent_id (idempotent). Prints OK.
  release <agent_id>  remove that agent's lease.
  release_hook        PostToolUse (payload tool_name "Agent"; matcher "Task") /
                      SubagentStop: release the pacer lease for this tool call
                      (reads tool_use_id from stdin; a no-op unless CSA_PACER=1)
                      AND, when CSA_SPEND_LEDGER is on (default), drive the
                      spend ledger's three-event join (churn_phase0_measure.md
                      step 2): annotate/join/release claims.jsonl <->
                      stops.jsonl <-> spend.jsonl, plus a reap pass over
                      claims/pending-stops older than CSA_CLAIM_TTL_SEC.
                      N15: CSA_DISABLE_HOOKS=1 short-circuits BEFORE either
                      effect, so a lease or claim recorded while hooks were on
                      then leaks until its own TTL self-heal reaps it, not
                      released here.
  reset               clear stale/malformed leases + all pending-stop markers.
  doctor              print health of the ledger.
  gate                PreToolUse:Task admission gate. With CSA_PACER=1 it claims a
                      lease under the admission lock (count-then-claim, keyed on
                      tool_use_id) and, when enforcing(), denies over cap; without
                      it, the legacy LOG-ONLY read-only count. Fails open always.
                      On an ADMITTED (non-denied) gate, when CSA_SPEND_LEDGER is
                      on (default) and the real tool_use_id is present, also
                      records a spend-ledger claim to claims.jsonl (never on a
                      denied gate -- a denied dispatch never ran).
                      Also on an ADMITTED gate only: WS2.2's fan-out
                      session-high PURE OBSERVER (never denies/delays/raises)
                      folds this dispatch into session_counts.json under the
                      SAME admission lock and logs one `fanout-session-high`
                      line to the enforcement log the first time a session's
                      admitted-dispatch count reaches CSA_FANOUT_THRESHOLD
                      (default 40). See record_fanout_dispatch/
                      note_fanout_dispatch below.
  spend --by agent|model|day [--since YYYY-MM-DD]
                      reap stale claims/pending-stops, then print a
                      spend-by-X table read from spend.jsonl. The rigorous,
                      dedup-aware analysis lives in churn_report.py (step 5);
                      this is a quick human-facing glance at the same ledger.
  browser_pool        PreToolUse:mcp__playwright advisory pool check. LOG-ONLY,
                      never blocks; delegates to the vendored pool if present.

Config env:
  CSA_PACER=1            enable the launch pacer (claim-on-gate + token bucket).
                        OFF by default: without it `gate` is the legacy read-only
                        advisory count and NOTHING is claimed.
  CSA_SPEND_LEDGER       gates the decoupled stdin read (both `gate` and
                        `release_hook` read stdin when this OR CSA_PACER is on)
                        AND the spend ledger itself (churn_phase0_measure.md
                        step 2): gate's claim recording, release_hook's
                        claim/pending-stop/spend.jsonl join, and the `spend`
                        subcommand's reap pass. ON by default; OFF only when
                        set to the literal "0". Fully DECOUPLED from CSA_PACER
                        — it never claims a pacer lease or affects admission.
  CSA_CLAIM_TTL_SEC      claim/pending-stop reap window in seconds (default
                        21600 = 6h). A claims.jsonl or stops.jsonl row older
                        than this with no matching release is written to
                        spend.jsonl flagged unreleased: true and removed, by
                        the next `release_hook` or `spend` invocation — never
                        silently dropped. Distinct from CSA_LEASE_TTL_SEC,
                        which governs the PACER's own lease staleness on a
                        much shorter horizon.
  CSA_ANTHROPIC_CEILING  machine-wide concurrent-agent ceiling (default 8).
  CSA_FANOUT_THRESHOLD   WS2.2's fan-out session-high observer threshold --
                        admitted Task dispatches in one session before it
                        logs one `fanout-session-high` line (default 40).
  CSA_LAUNCH_RATE        launch tokens per second — anti-burst stagger rate
                        (default 2.0; used when CSA_PACER=1).
  CSA_LAUNCH_BURST       token-bucket capacity / max instantaneous burst (default 4.0).
  CSA_LOCK_TIMEOUT_SEC   max wait for the admission lock before failing OPEN
                        (default 2.0; must stay well under the hook timeout).
  CSA_ADMIT_MAX_WAIT_SEC max seconds a spawn waits for a slot before denying
                        (default 30.0; keep well under the hook timeout).
  CSA_ADMIT_POLL_SEC    poll interval while waiting at the concurrency cap
                        (default 0.25).
  CSA_LEASE_TTL_SEC      lease staleness threshold in seconds (default 3600).
  CSA_DISABLE_HOOKS=1    master OFF: gate/browser_pool short-circuit to exit 0.

recommended additional slots = max(0, cap(ceiling) - live); cap(ceiling) = max(1, ceiling)
(CPU cores are NOT a concurrency factor — sub-agents are network/token-bound.)

Structure: PURE decision helpers (trivially unit-testable) + a thin main() that
reads argv/env, decides, emits/logs, and always exits 0.

Observed-model recovery (WS2.1 step 4, plan_lane_control_adoption_master_2026_09_20.md
§2.1 item 4, #5828): a spend row whose `model` is still null at SubagentStop join
time — every Workflow-tool leg, whose PreToolUse never fires per-leg (see
docs/subsystems/telemetry-and-spend.md's 2026-09-20 probe section), is the measured
case — has it filled from the agent transcript's own `message.model` field
(`model_from_transcript`, consulted via `_resolve_model_and_source` at every join site
that already reads `agent_transcript_path`: `_release_line_from_join`,
`_release_line_from_completed_join`, and `reap_stale`'s `stopped-unjoined` stage). A
row this fills carries `model_source: "transcript"`; a row whose model came from the
normal dispatch-time path is untouched (no `model_source` key added). Exception-wrapped
end to end and, for a REGULAR FILE, bounded to `MODEL_TRANSCRIPT_MAX_BYTES` (a tail read,
never the whole file) so this can never stall the stop path or the pacer lease release it
shares a hook invocation with. A non-regular path (FIFO, character/block device,
directory, socket) is refused via `os.stat`/`stat.S_ISREG` BEFORE any `open()` call
(2026-09-20 fix round, BLOCKER: the original `os.path.getsize`-based check read `0` for a
character device and never bounded the read at all — a symlink to `/dev/zero` grew
unbounded toward OOM, and a FIFO with no writer blocked forever inside `open()`).
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from contextlib import contextmanager

# Import the shared hook library regardless of the pytest rootdir / cwd.
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

DEFAULT_CEILING = 8
DEFAULT_TTL = 3600
DEFAULT_CORES = 4  # conservative fallback when the OS won't report core count.
DEFAULT_LOAD = "0.00"

LEASE_PREFIX = "lease-"

# R11 (08-25 round 5): a PACER-only marker prefix (never a spend-ledger
# table) recording that a SubagentStop already searched for a lease before
# its own PostToolUse(async_launched) ever annotated one -- the C -> S -> A
# ordering. Lets the eventual async_launched call release the lease itself
# the instant it learns the tool_use_id <-> agent_id mapping, without ever
# touching claims.jsonl (see _release_pacer_lease_for_stop/
# _annotate_pacer_lease_and_maybe_release below). Self-heals via the same
# CSA_LEASE_TTL_SEC-scale housekeeping prune_and_count already performs for
# stale leases -- a marker whose own SubagentStop's async_launched never
# arrives is swept the same way a leaked lease is.
#
# N4 (08-25 round 5): round-4 dismissed a theoretical risk here -- an orphan
# marker could free a LATER lease early only if its agent_id were REUSED
# within CSA_LEASE_TTL_SEC (see _annotate_pacer_lease_and_maybe_release's
# marker-present branch, which trusts the marker's agent_id at face value).
# Real agent_ids are unique 17-char per-dispatch tokens -- 9/9 distinct in
# the live ledger sample -- so this is ACCEPTED, not hardened against.
PENDING_STOP_PREFIX = "pacer-pending-stop-"

# Spend-ledger table/artifact names (Phase 0 step 2, churn_phase0_measure.md):
# claims.jsonl / stops.jsonl are small "tables" (every mutation is a locked
# full-file read + atomic rewrite, see _read_table/_write_table); spend.jsonl
# is a pure append-only log (never rewritten). All three live directly under
# AGENT_BUDGET_DIR alongside the pacer's own lease-*/bucket.json/admission.lock.
CLAIMS_NAME = "claims.jsonl"
STOPS_NAME = "stops.jsonl"
SPEND_NAME = "spend.jsonl"
DEFAULT_CLAIM_TTL = 21600  # 6h (CSA_CLAIM_TTL_SEC) — the plan's own reap window.

# WS2.2 (plan_lane_control_adoption_master_2026_09_20.md §2.2) — fan-out
# session-high OBSERVER. A small on-disk table, session_counts.json, keyed
# by session id, tracking how many Task dispatches have been ADMITTED (never
# denied ones — see record_fanout_dispatch's docstring) in that session so
# far, plus a per-agent-type tally used only to name the top three when the
# threshold line is logged. PURE OBSERVER: it never denies, delays, or
# raises — see that function's own docstring and the module's fail-open
# contract. Default threshold matches the plan's own worked example (40
# dispatches/session) — chosen because the plan's own measured baseline
# (566 dispatches/day machine-wide, 2026-09-20) makes 40 in ONE session a
# real outlier worth a single flagged line, not a number every ordinary
# multi-agent session would cross by accident.
SESSION_COUNTS_NAME = "session_counts.json"
DEFAULT_FANOUT_THRESHOLD = 40
FANOUT_TOP_N = 3

# A PURE OBSERVER must never lengthen the dispatch hot path. `paced_admit`
# and `record_claim` already spend up to DEFAULT_LOCK_TIMEOUT each on a
# contended lock; a third full-budget acquisition for TELEMETRY stacked on
# top of them, measured by execution: 4.02s at HEAD -> 6.01s with the
# counter, a 50% increase in the worst-case stall of every admitted dispatch
# on the machine. This counter therefore gets its own short budget and
# simply SKIPS the count when the lock is busy -- the fail-open branch the
# function already has. The cost is an occasional missed increment, never a
# missed threshold CROSSING in practice, and never a delay.
FANOUT_LOCK_TIMEOUT = 0.1

# Launch-rate limiter (token bucket) + admission lock — the pacer's shared state.
DEFAULT_LAUNCH_RATE = 2.0  # launch tokens per second (CSA_LAUNCH_RATE)
DEFAULT_LAUNCH_BURST = 4.0  # bucket capacity / max simultaneous burst (CSA_LAUNCH_BURST)
DEFAULT_LOCK_TIMEOUT = 2.0  # max seconds to wait for the admission lock (<< hook timeout)
DEFAULT_ADMIT_MAX_WAIT = 30.0  # max seconds a spawn waits for a slot (CSA_ADMIT_MAX_WAIT_SEC)
DEFAULT_ADMIT_POLL = 0.25  # poll interval while waiting at the concurrency cap (CSA_ADMIT_POLL_SEC)
BUCKET_NAME = "bucket.json"
LOCK_NAME = "admission.lock"


# ---------------------------------------------------------------------------
# PURE helpers — no I/O, exhaustively testable.
# ---------------------------------------------------------------------------


def parse_int_config(raw: object, default: int) -> int:
    """Validate a numeric config value; fall back to `default` on garbage.

    Mirrors the bash `case "$X" in ''|*[!0-9]*) X=default`: only a non-empty
    run of ASCII digits is accepted (no sign, no whitespace, no float).
    """
    if raw is None:
        return default
    s = str(raw)
    if s and s.isdigit():
        return int(s)
    return default


def parse_float_config(raw: object, default: float) -> float:
    """Validate a non-negative finite float config value; fall back on garbage.

    Accepts ints/floats/numeric strings; rejects None, non-numeric, negative,
    NaN, and infinity (all -> default). Mirrors parse_int_config's fail-open.
    """
    if raw is None:
        return default
    try:
        v = float(str(raw).strip())
    except Exception:
        return default
    import math

    if not math.isfinite(v) or v < 0:
        return default
    return v


def ceiling_from_env(environ: dict | None = None) -> int:
    """Resolve CSA_ANTHROPIC_CEILING (default 8) with numeric validation."""
    env = os.environ if environ is None else environ
    return parse_int_config(env.get("CSA_ANTHROPIC_CEILING"), DEFAULT_CEILING)


def ttl_from_env(environ: dict | None = None) -> int:
    """Resolve CSA_LEASE_TTL_SEC (default 3600) with numeric validation."""
    env = os.environ if environ is None else environ
    return parse_int_config(env.get("CSA_LEASE_TTL_SEC"), DEFAULT_TTL)


def claim_ttl_from_env(environ: dict | None = None) -> int:
    """Resolve CSA_CLAIM_TTL_SEC (spend-ledger claim/pending-stop reap
    window, default 21600 = 6h) with numeric validation. Deliberately a
    SEPARATE knob from CSA_LEASE_TTL_SEC/ttl_from_env: the pacer's lease
    staleness (default 1h) and the spend ledger's claim reap window
    (default 6h, per churn_phase0_measure.md step 2) are different
    concepts on different horizons that happen to share this module."""
    env = os.environ if environ is None else environ
    return parse_int_config(env.get("CSA_CLAIM_TTL_SEC"), DEFAULT_CLAIM_TTL)


def launch_rate_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_LAUNCH_RATE (launch tokens/sec, default 2.0)."""
    env = os.environ if environ is None else environ
    return parse_float_config(env.get("CSA_LAUNCH_RATE"), DEFAULT_LAUNCH_RATE)


def launch_burst_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_LAUNCH_BURST (bucket capacity / max burst, default 4.0)."""
    env = os.environ if environ is None else environ
    return parse_float_config(env.get("CSA_LAUNCH_BURST"), DEFAULT_LAUNCH_BURST)


def lock_timeout_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_LOCK_TIMEOUT_SEC (admission-lock max wait, default 2.0)."""
    env = os.environ if environ is None else environ
    return parse_float_config(env.get("CSA_LOCK_TIMEOUT_SEC"), DEFAULT_LOCK_TIMEOUT)


def admit_max_wait_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_ADMIT_MAX_WAIT_SEC (max wait for a slot, default 30.0).

    Bounded well under the Claude Code hook timeout so a saturated pacer denies
    (model reduces fan-out) rather than risking a hook kill.
    """
    env = os.environ if environ is None else environ
    return parse_float_config(env.get("CSA_ADMIT_MAX_WAIT_SEC"), DEFAULT_ADMIT_MAX_WAIT)


def admit_poll_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_ADMIT_POLL_SEC (cap-wait poll interval, default 0.25)."""
    env = os.environ if environ is None else environ
    return parse_float_config(env.get("CSA_ADMIT_POLL_SEC"), DEFAULT_ADMIT_POLL)


def fanout_threshold_from_env(environ: dict | None = None) -> int:
    """Resolve CSA_FANOUT_THRESHOLD (WS2.2's fan-out session-high threshold,
    default 40) with numeric validation. Garbage/absent -> the default,
    same fail-open convention as every other *_from_env resolver here."""
    env = os.environ if environ is None else environ
    return parse_int_config(env.get("CSA_FANOUT_THRESHOLD"), DEFAULT_FANOUT_THRESHOLD)


def pacer_enabled(environ: dict | None = None) -> bool:
    """True when the launch pacer is explicitly enabled (CSA_PACER=1).

    OFF by default: the claim-on-gate + token-bucket admission path only runs when
    this is set, so the ledger/bucket machinery cannot affect a session that has
    not opted in. Independent of enforcing() (which additionally gates deny/sleep).
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_PACER", "") == "1"


def spend_ledger_enabled(environ: dict | None = None) -> bool:
    """True unless CSA_SPEND_LEDGER is explicitly the literal "0". ON by default.

    Gates TWO things now (Phase 0 step 2, churn_phase0_measure.md): (1)
    whether `gate` and `release_hook` read their stdin payload at all (see
    main()'s `read_stdin`) when the launch pacer (CSA_PACER) is OFF — with
    the pacer ON, stdin is read regardless of this flag; (2) the real spend
    ledger itself — gate's claims.jsonl claim recording, release_hook's
    claim/pending-stop/spend.jsonl join, and the `spend` subcommand's reap
    pass. It is completely decoupled from pacer_enabled(): turning this
    on/off never claims a pacer lease and never affects admission (see
    pacer_enabled's own docstring for the symmetric guarantee in the other
    direction).

    R11 (08-25 round 5): this decoupling is now ALSO true of
    release_hook's pacer-lease RELEASE/ANNOTATE path specifically (R9 had
    quietly broken it -- see `_release_pacer_lease_for_stop`'s own
    docstring -- by resolving a SubagentStop's lease via claims.jsonl, a
    table this flag's OFF setting leaves entirely unwritten). The pacer's
    own identity resolution (lease files + a pacer-only pending-stop
    marker) never reads claims.jsonl/stops.jsonl/spend.jsonl at all, so a
    dispatch's concurrency lease releases correctly whether or not this
    flag is on.

    Any value other than "0" (including unset) is ON, so a stray typo in
    the env var never silently turns the ledger off.
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_SPEND_LEDGER", "") != "0"


def cap(ceiling: int) -> int:
    """Concurrency cap = max(1, ceiling).

    CPU cores are intentionally NOT a factor: parallel sub-agents are network /
    token-bound (they spend against Anthropic per-minute rate limits, chiefly
    ITPM), not CPU-bound, so the machine-wide concurrency ceiling is purely the
    operator-calibrated `CSA_ANTHROPIC_CEILING`. Floored at 1 so a misconfigured
    ceiling of 0/garbage still admits one agent (fail toward progress). cores()
    and load1() remain in status/doctor output as info only.
    """
    return ceiling if ceiling > 1 else 1


def recommend(ceiling: int, live: int) -> int:
    """recommended additional slots = max(0, cap(ceiling) - live)."""
    rec = cap(ceiling) - live
    return rec if rec > 0 else 0


def refill(tokens: float, rate: float, capacity: float, elapsed: float) -> float:
    """Token-bucket refill: new = clamp(tokens + rate*elapsed, 0, capacity).

    Pure. `rate` is tokens/second, `capacity` is the burst size (bucket max),
    `elapsed` is seconds since the last refill. Negative `elapsed` (clock skew /
    a non-monotonic wall clock) is treated as 0 so the bucket never loses tokens
    on a backwards clock. The result is clamped into [0, capacity].
    """
    if elapsed < 0:
        elapsed = 0.0
    new = tokens + rate * elapsed
    if new > capacity:
        new = capacity
    if new < 0:
        new = 0.0
    return new


def admit(tokens: float, cost: float = 1.0) -> tuple[bool, float]:
    """Consume `cost` launch tokens if available. Returns (allowed, remaining).

    Pure. On success the caller persists `remaining`; on failure the bucket is
    left unchanged and the caller waits or denies. `cost` defaults to one launch.
    """
    if tokens >= cost:
        return True, tokens - cost
    return False, tokens


def plan_admission(live: int, capacity: int, tokens: float, cost: float = 1.0) -> tuple[bool, float, str]:
    """Decide admission from a locked snapshot. Returns (admit, new_tokens, reason).

    Admit only when BOTH a concurrency slot (live < capacity) AND a launch token
    (tokens >= cost) are available; then new_tokens = tokens - cost. Otherwise the
    bucket is unchanged and `reason` says which limit blocked: "cap" (concurrency)
    takes priority over "rate" (bucket) when both bind. Pure.
    """
    under_cap = live < capacity
    has_token = tokens >= cost
    if under_cap and has_token:
        return True, tokens - cost, "ok"
    reason = "cap" if not under_cap else "rate"
    return False, tokens, reason


def wait_hint(reason: str, tokens: float, rate: float, poll: float, cost: float = 1.0) -> float:
    """Seconds to wait before retrying admission (computed under the lock).

    Rate-limited: exactly the time for the bucket to refill one token,
    (cost - tokens)/rate. At the concurrency cap (or rate==0): the poll interval,
    since a slot frees on another agent's completion at an unknown future time.
    Pure; never negative.
    """
    if reason == "rate" and rate > 0:
        need = cost - tokens
        return need / rate if need > 0 else 0.0
    return poll if poll > 0 else 0.0


def safe_id(agent_id: str) -> str:
    """Sanitize an agent_id into a safe filename token.

    Ports `tr -c 'A-Za-z0-9._-' '_'`: every character outside that class becomes
    '_'. An empty id yields "unknown" so a lease file is never named "lease-".
    """
    if not agent_id:
        return "unknown"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    return "".join(ch if ch in allowed else "_" for ch in agent_id)


def lease_path(budget_dir: str, agent_id: str) -> str:
    """Absolute path of the lease file for `agent_id` under `budget_dir`."""
    return os.path.join(budget_dir, LEASE_PREFIX + safe_id(agent_id))


# ---------------------------------------------------------------------------
# System introspection — Python stdlib (no shell-out; hermetic under tmp HOME).
# ---------------------------------------------------------------------------


def cores() -> int:
    """CPU core count, or a conservative default of 4 on any failure.

    Replaces `sysctl -n hw.ncpu` with os.cpu_count(); the None/garbage fallback
    matches the bash `case ''|*[!0-9]*) c=4`.
    """
    try:
        c = os.cpu_count()
    except Exception:  # pragma: no cover - cpu_count doesn't raise in practice
        c = None
    if not isinstance(c, int) or c <= 0:
        return DEFAULT_CORES
    return c


def load1() -> str:
    """1-minute load average as a string, "0.00" on any failure.

    Replaces `sysctl -n vm.loadavg | awk '{print $2}'` with os.getloadavg()[0].
    getloadavg raises OSError on platforms without load data — we fall open.
    """
    try:
        val = os.getloadavg()[0]
    except Exception:
        return DEFAULT_LOAD
    try:
        return f"{float(val):.2f}"
    except Exception:  # pragma: no cover - getloadavg returns floats
        return DEFAULT_LOAD


# ---------------------------------------------------------------------------
# Ledger operations — self-healing prune + count.
# ---------------------------------------------------------------------------


def _lease_mtime(path: str) -> int:
    """mtime of a lease file as an int, 0 on any failure (treated as stale)."""
    try:
        return int(os.stat(path).st_mtime)
    except Exception:
        return 0


def prune_and_count(budget_dir: str, ttl: int, now: int | None = None) -> int:
    """Count live (non-stale, well-formed) leases; prune stale/corrupt ones.

    A lease is stale when its mtime is 0 (unreadable/corrupt) or older than
    `ttl` seconds. Stale leases are removed as a side effect (self-heal). If
    `budget_dir` is missing or unreadable, fail open and report 0 live.

    R11 (08-25 round 5): also self-heals stale PENDING_STOP_PREFIX markers
    (see that constant's own docstring) on the SAME ttl/mtime rule -- never
    counted toward the returned live-lease number (they aren't leases), a
    pure housekeeping side effect piggybacked onto the pass this function
    already makes over every call site (gate/paced_admit/status/doctor all
    call this).

    Ports `_prune_and_count`. Never raises.
    """
    if now is None:
        now = _now_epoch()
    try:
        if not os.path.isdir(budget_dir) or not os.access(budget_dir, os.R_OK):
            return 0
        entries = os.listdir(budget_dir)
    except Exception:
        return 0
    count = 0
    for name in entries:
        if name.startswith(PENDING_STOP_PREFIX):
            path = os.path.join(budget_dir, name)
            if not os.path.exists(path):
                continue
            mtime = _lease_mtime(path)
            if mtime == 0 or (now - mtime) > ttl:
                _remove(path)
            continue
        if not name.startswith(LEASE_PREFIX):
            continue
        path = os.path.join(budget_dir, name)
        if not os.path.exists(path):
            continue
        mtime = _lease_mtime(path)
        age = now - mtime
        if mtime == 0 or age > ttl:
            _remove(path)  # stale/corrupt → self-heal
            continue
        count += 1
    return count


def _lease_has_agent_id(path: str) -> bool:
    """True iff the lease file contains an `agent_id=` line (well-formed)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("agent_id="):
                    return True
    except Exception:
        return False
    return False


def reset_ledger(budget_dir: str, ttl: int, now: int | None = None) -> int:
    """Remove stale OR malformed (no `agent_id=` line) leases, and every
    PENDING_STOP_PREFIX marker unconditionally (N3, 08-25 round 5) --
    markers are pure housekeeping (see that constant's own docstring), so an
    operator-invoked hard reset clears them all regardless of age, matching
    agent_pacer.md's own `.agent_budget/` contents bullet for this prefix.
    Returns the total removed count (leases + markers).

    Ports `cmd_reset`. Never raises; a missing dir removes nothing.
    """
    if now is None:
        now = _now_epoch()
    removed = 0
    try:
        if not os.path.isdir(budget_dir):
            return 0
        entries = os.listdir(budget_dir)
    except Exception:
        return 0
    for name in entries:
        if name.startswith(PENDING_STOP_PREFIX):
            path = os.path.join(budget_dir, name)
            if os.path.exists(path) and _remove(path):
                removed += 1
            continue
        if not name.startswith(LEASE_PREFIX):
            continue
        path = os.path.join(budget_dir, name)
        if not os.path.exists(path):
            continue
        mtime = _lease_mtime(path)
        age = now - mtime
        stale = mtime == 0 or age > ttl
        if stale or not _lease_has_agent_id(path):
            if _remove(path):
                removed += 1
    return removed


def status_payload(budget_dir: str, ceiling: int, ttl: int, environ: dict | None = None) -> dict:
    """Build the status JSON payload over the injected config/dir/env.

    Includes the pacer state + live launch-token bucket level so leaks / throttle
    pressure are observable machine-wide (live_leases counts leases across ALL
    sessions, since the ledger dir is shared).
    """
    env = os.environ if environ is None else environ
    c = cores()
    live = prune_and_count(budget_dir, ttl)
    rate = launch_rate_from_env(env)
    burst = launch_burst_from_env(env)
    return {
        "cpu_cores": c,
        "load_1min": load1(),
        "pacer_enabled": pacer_enabled(env),
        "ceiling": ceiling,
        "live_leases": live,
        "recommended_additional_slots": recommend(ceiling, live),
        "launch_rate_per_sec": rate,
        "launch_burst": burst,
        "launch_tokens_available": round(_current_bucket_tokens(budget_dir, rate, burst), 3),
    }


# ---------------------------------------------------------------------------
# Tiny I/O primitives kept thin so the pure layer above stays testable.
# ---------------------------------------------------------------------------


def _now_epoch() -> int:
    try:
        import time

        return int(time.time())
    except Exception:  # pragma: no cover - time.time doesn't raise
        return 0


def _now_epoch_f() -> float:
    """Float wall-clock epoch (sub-second precision) for the spend ledger's
    own row timestamps (claim `ts_epoch`, pending-stop/pending-completed
    `stop_ts_epoch`) -- distinct from `_now_epoch()`'s whole-second int,
    which the PACER's lease/bucket/admission-lock code and reap_stale's
    `now` default still use unchanged. B3 (08-25 round 4): whole-second
    truncation quantised any sub-second background dispatch's duration_ms
    (stop_epoch - claim_epoch, in `_release_line_from_join`) to 0 even when
    the real gap was, say, 400ms -- both epochs landed in the same
    truncated second. Never raises; 0.0 on any failure, matching
    `_now_epoch()`'s own zero fallback.
    """
    try:
        import time

        return time.time()
    except Exception:  # pragma: no cover - time.time doesn't raise
        return 0.0


def _mono() -> float:
    """Monotonic clock for loop deadlines (immune to wall-clock jumps)."""
    try:
        import time

        return time.monotonic()
    except Exception:  # pragma: no cover
        return 0.0


def _sleep(seconds: float) -> None:
    """Sleep for `seconds` (no-op on non-positive input). Never raises."""
    if seconds <= 0:
        return
    try:
        import time

        time.sleep(seconds)
    except Exception:  # pragma: no cover
        return


def _jitter(base: float) -> float:
    """Add up to +50% randomized jitter to a wait, to desync contending waiters."""
    if base <= 0:
        return 0.0
    try:
        import random

        return base * (1.0 + 0.5 * random.random())
    except Exception:  # pragma: no cover
        return base


def _remove(path: str) -> bool:
    """rm -f; True if the file is gone afterwards. Never raises."""
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return


def write_lease(budget_dir: str, agent_id: str) -> None:
    """Create/refresh a lease file (idempotent). Best-effort; never raises."""
    _ensure_dir(budget_dir)
    path = lease_path(budget_dir, agent_id)
    body = f"agent_id={agent_id}\npid={os.getpid()}\nclaimed_at={_lib._now()}\n"
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    except Exception:
        return


# ---------------------------------------------------------------------------
# Claim / pending-stop / spend ledger — Phase 0 step 2 (churn_phase0_measure.md).
#
# Three small on-disk tables under AGENT_BUDGET_DIR:
#   claims.jsonl — one row per open claim, appended at `gate`, annotated with
#     agent_id/model at PostToolUse(async_launched), consumed (removed) at
#     release. EVERY mutation (append, annotate, pop, reap) takes the SAME
#     admission_lock this module already uses for the pacer's bucket/lease
#     state (record_review.py's lock_timeout_from_env is the in-tree
#     precedent for serializing a read-modify-write ledger this way) — a
#     lost annotation is an orphaned claim that can only ever be TTL-reaped.
#   stops.jsonl — one row per open pending-stop record, always persisted by
#     SubagentStop regardless of whether a matching claim exists yet (never
#     a no-op — this is what makes the join order-independent: a fast
#     subagent's SubagentStop beating the launch hook still leaves a record
#     for that hook to find when it arrives).
#   spend.jsonl — append-only (via _append_jsonl below), one line per
#     dispatch, the canonical schema from the plan's step 2 section. Never
#     rewritten; a reap or a `late` release just appends another line.
#
# R7 (08-25 round 4) — WRITE ORDERING within every release/reap path below:
# the spend.jsonl append always lands BEFORE the claims.jsonl/stops.jsonl
# table(s) it was derived from are pruned/rewritten. The pre-R7 order was the
# other way round (prune the table, THEN append the spend line), which meant
# a crash between the two writes silently erased a real dispatch: its claim/
# stop row was already gone from its table, and the spend line that would
# have recorded it never landed either -- a vanished dispatch, unrecoverable
# by any later reap or join. With the append-first order, the same crash
# leaves a row still sitting in its table (un-pruned) instead -- at worst
# re-processed later, producing a DUPLICATE spend line for the same
# tool_use_id, which `churn_report.dedup_spend_lines` already collapses to
# one by design (preferring the non-`unreleased` line). A duplicate that
# gets deduped away is always the safer failure mode than a dispatch that
# never gets recorded at all.
#
# See classify_release_event/handle_async_launched/handle_subagent_stop/
# handle_completed/reap_stale below for the actual three-event join.
# ---------------------------------------------------------------------------


def claims_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, CLAIMS_NAME)


def stops_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, STOPS_NAME)


def spend_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, SPEND_NAME)


def session_counts_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, SESSION_COUNTS_NAME)


# ---------------------------------------------------------------------------
# WS2.2 — fan-out session-high OBSERVER. See SESSION_COUNTS_NAME's own
# comment above for what this tracks and why. Two layers, same shape as the
# rest of this module: a PURE transform (record_fanout_dispatch) the tests
# drive directly, and a thin impure wrapper (note_fanout_dispatch) that
# reads/writes the JSON table under the CALLER's already-held admission
# lock — this module invents no second lock for it, per the spec.
# ---------------------------------------------------------------------------


def _read_session_counts(path: str) -> dict:
    """Read session_counts.json into a dict, or {} on ANY failure — missing
    file, unreadable, truncated/corrupt JSON, or a top-level value that
    isn't even a dict. A corrupt counter file therefore RESETS every
    session's count rather than raising or wedging the dispatch hot path
    this sits on (WS2.2's own requirement). Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_session_counts(path: str, counts: dict) -> None:
    """Atomically REPLACE `path` with `counts` (temp file + os.replace),
    mirroring `_write_table`'s own crash-safety convention. Best-effort;
    never raises — a failed write just means the next dispatch re-reads
    whatever is on disk (at worst {} again), which is the same fail-open
    shape as every other write in this module."""
    _ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(counts, fh)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def record_fanout_dispatch(
    counts: dict,
    session: str,
    agent_type: str | None,
    threshold: int,
) -> tuple[dict, bool, dict | None]:
    """PURE: fold one more ADMITTED dispatch into `counts` for `session`.

    Returns `(new_counts, should_log, log_fields)`. `new_counts` is a NEW
    dict (never mutates the caller's `counts` in place, matching every
    other pure table transform in this module — see `annotate_claim`'s own
    convention). `should_log` is True EXACTLY ONCE per session: on the
    dispatch whose count first reaches `threshold` (never on every
    dispatch after it, and never a second time on a later one — a
    session's row in `counts` carries `logged: true` once it has fired, so
    a corrupt-counter reset that later replays the same session back up to
    `threshold` logs again, which is the correct fail-open behavior for a
    PURE OBSERVER that must never lose a real crossing, not a bug to guard
    against). `log_fields` is `None` unless `should_log` is True, in which
    case it carries `{session, count, top_agent_types}` ready to hand to
    `_lib.log(**log_fields)` — `top_agent_types` is the (at most)
    `FANOUT_TOP_N` agent types with the highest per-session dispatch count
    so far, ties broken by agent-type name for determinism, each as
    `{"agent_type": <str-or-null>, "count": <int>}`.

    A missing/falsy `session` is a no-op: `counts` is returned unchanged,
    `should_log` is False. This mirrors every other per-agent_id pure
    helper in this module (`pop_claim_by_agent_id`, `pop_stop_by_agent_id`)
    refusing to key off a falsy identity — there is no real session to
    attribute the count to. `agent_type` may be None (a payload that
    genuinely carries none): it is folded into the tally under the literal
    key `"unknown"` rather than dropped, so a fan-out of un-typed dispatches
    still shows up in `top_agent_types` instead of silently vanishing from
    the count that drives it.
    """
    if not session:
        return counts, False, None
    new_counts = {k: dict(v) for k, v in counts.items() if isinstance(v, dict)}
    row = new_counts.get(session)
    if not isinstance(row, dict):
        row = {"count": 0, "by_agent_type": {}, "logged": False}
    else:
        row = {
            "count": row.get("count", 0) if isinstance(row.get("count"), int) else 0,
            "by_agent_type": dict(row.get("by_agent_type") or {}),
            "logged": bool(row.get("logged")),
        }
    row["count"] += 1
    type_key = agent_type if isinstance(agent_type, str) and agent_type else "unknown"
    row["by_agent_type"][type_key] = row["by_agent_type"].get(type_key, 0) + 1

    should_log = False
    log_fields: dict | None = None
    if row["count"] >= threshold and not row["logged"]:
        should_log = True
        row["logged"] = True
        top = sorted(row["by_agent_type"].items(), key=lambda kv: (-kv[1], kv[0]))[:FANOUT_TOP_N]
        log_fields = {
            "session": session,
            "count": row["count"],
            "top_agent_types": [{"agent_type": t, "count": c} for t, c in top],
        }
    new_counts[session] = row
    return new_counts, should_log, log_fields


def note_fanout_dispatch(
    budget_dir: str,
    session: str | None,
    agent_type: str | None,
    threshold: int,
    lock_timeout: float,
) -> None:
    """Impure wrapper: read-modify-write session_counts.json under the
    SAME shared `admission_lock` this module already uses for the pacer's
    lease/bucket state and the spend ledger's claims/stops tables — WS2.2
    explicitly forbids inventing a second lock for this counter, and this
    is the one lock every other read-modify-write table in this module
    already serializes through. Logs the `fanout-session-high` line via
    `_lib.log` OUTSIDE the lock (matching this module's existing convention
    of never holding the lock across a log write) once `should_log` is True.

    Exception-wrapped end to end: this sits on the dispatch hot path
    (`gate`'s admitted branch), and per the module's own fail-open contract
    a failure here must never affect admission or raise out to the caller.
    A lock that cannot be acquired within `lock_timeout` is itself just
    another form of "no-op this time" — the same fail-open shape
    `record_claim`/`handle_async_launched` already use for a lock timeout
    (logged, then skipped) — never a denial and never a retry loop.
    """
    if not session:
        return
    try:
        path = session_counts_path(budget_dir)
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="note_fanout_dispatch",
                    tool_use_id=None,
                )
                return
            counts = _read_session_counts(path)
            new_counts, should_log, log_fields = record_fanout_dispatch(
                counts, session, agent_type, threshold
            )
            _write_session_counts(path, new_counts)
        if should_log and log_fields is not None:
            _lib.log("agent_budget", "fanout-session-high", **log_fields)
    except Exception:
        return


def _read_table(path: str) -> list[dict]:
    """Read a small JSONL table file into a list of dicts.

    Missing file -> []. A line that fails to parse as a JSON object is
    DROPPED, never raised — this is a self-healing advisory table, matching
    prune_and_count's fail-open convention for the lease ledger. Never
    raises: any I/O error (unreadable dir, permission) also degrades to [].
    """
    try:
        if not os.path.isfile(path):
            return []
        rows: list[dict] = []
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
        return rows
    except Exception:
        return []


def _write_table(path: str, rows: list[dict]) -> None:
    """Atomically REPLACE `path` with `rows` (temp file in the same dir +
    os.replace), mirroring record_review._update_entry's convention so a
    crash mid-write can never corrupt/truncate the table. Best-effort;
    never raises. The CALLER must hold the admission lock across its own
    read-mutate-write window — this function only performs the write half,
    exactly like write_bucket does for the pacer's own bucket.json.
    """
    _ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, default=str) + "\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


# --- PURE table transforms (no I/O; the locked handlers below are the only
# callers, and each holds admission_lock across its own read/transform/write
# so two of these transforms are never interleaved on the same table). -----


def pop_claim_by_tool_use_id(rows: list[dict], tool_use_id: str) -> tuple[list[dict], dict | None]:
    """Remove and return the claim row matching `tool_use_id`, or (rows
    unchanged, None) when absent. Pure: returns a NEW list, never mutates
    `rows` in place."""
    for i, row in enumerate(rows):
        if row.get("tool_use_id") == tool_use_id:
            return rows[:i] + rows[i + 1 :], row
    return rows, None


def pop_claim_by_agent_id(rows: list[dict], agent_id: str) -> tuple[list[dict], dict | None]:
    """Remove and return the claim row matching `agent_id` (only ever set on
    a claim that has already been annotated by PostToolUse(async_launched)
    — an un-annotated claim has agent_id=None and can never match here, by
    design: SubagentStop can only join a BACKGROUND dispatch this way).
    Pure.

    N15 (08-25 round 4): a falsy `agent_id` (None/"") is NEVER a valid
    lookup key and returns early WITHOUT scanning -- every un-annotated
    claim in the table has `agent_id=None` too (the normal in-flight state
    between gate and PostToolUse(async_launched)), so without this guard a
    caller that (by a bug) ever passed a falsy `agent_id` here would
    silently "match" and consume the FIRST un-annotated claim in the whole
    table. Real callers already guard this at the call site
    (handle_subagent_stop returns before ever reaching here on a falsy
    agent_id) -- this is defense in depth, not a behavior any caller
    currently relies on.
    """
    if not agent_id:
        return rows, None
    for i, row in enumerate(rows):
        if row.get("agent_id") == agent_id:
            return rows[:i] + rows[i + 1 :], row
    return rows, None


def annotate_claim(
    rows: list[dict], tool_use_id: str, agent_id: str, model: str | None
) -> tuple[list[dict], dict | None]:
    """Set agent_id/model on the claim row matching `tool_use_id`. Returns
    (new_rows, the_updated_row_or_None — None when no claim matched, e.g.
    the ledger was off at gate time or the claim was already reaped). Pure:
    copies the matched row rather than mutating the caller's dict."""
    new_rows: list[dict] = []
    updated: dict | None = None
    for row in rows:
        if updated is None and row.get("tool_use_id") == tool_use_id:
            row = dict(row)
            row["agent_id"] = agent_id
            row["model"] = model
            updated = row
        new_rows.append(row)
    return new_rows, updated


def pop_stop_by_agent_id(rows: list[dict], agent_id: str) -> tuple[list[dict], dict | None]:
    """Remove and return the PENDING-STOP row (`kind == "stop"`, the
    default for any row with no `kind` field at all -- the pre-B1-fix
    on-disk shape, and every row this function wrote before B1) matching
    `agent_id`. Never matches a PENDING-COMPLETED row (`kind ==
    "completed"`, see `pop_pending_completed_by_agent_id`) even though both
    now share this same physical table (stops.jsonl) -- see the B1 fix note
    in `handle_completed`'s docstring. N15: a falsy `agent_id` never matches
    (see `pop_claim_by_agent_id`'s docstring for why). Pure."""
    if not agent_id:
        return rows, None
    for i, row in enumerate(rows):
        if row.get("agent_id") == agent_id and row.get("kind", "stop") == "stop":
            return rows[:i] + rows[i + 1 :], row
    return rows, None


def pop_pending_completed_by_agent_id(
    rows: list[dict], agent_id: str
) -> tuple[list[dict], dict | None]:
    """Remove and return the PENDING-COMPLETED row (`kind == "completed"`)
    matching `agent_id` -- the B1 fix's record of a PostToolUse(completed)
    event that arrived before its SubagentStop (the "gate -> completed ->
    stop" ordering; see `handle_completed`). Lives in the SAME physical
    table (stops.jsonl) as the traditional pending-stop rows so
    `reap_stale`'s existing sweep covers both kinds without a fourth reap
    stage. N15: a falsy `agent_id` never matches. Pure."""
    if not agent_id:
        return rows, None
    for i, row in enumerate(rows):
        if row.get("agent_id") == agent_id and row.get("kind") == "completed":
            return rows[:i] + rows[i + 1 :], row
    return rows, None


def _usage_int(value: object) -> int:
    """Coerce one usage sub-field to a plain int; 0 for anything that isn't
    a real int/float (never raises, never guesses a nonzero value)."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


# A synthetic (never a raised exception's class name) tokens_error sentinel
# for a line where this module KNOWS a dispatch really finished (it has
# real duration_ms/payload data) but genuinely never learned its transcript
# path -- distinct from `sum_transcript_tokens(None)`'s legitimate, silent
# (tokens_error=None) "we never got as far as having a path at all" case.
# See reap_stale's "completed, unjoined" branch (B1, 08-25 round 4).
NO_TRANSCRIPT_RECORDED_ERROR = "NoTranscriptRecorded"


def _is_number(v: object) -> bool:
    """True for a real int/float epoch value, excluding bool (a bool is an
    int subclass in Python but must never be treated as a numeric
    timestamp). Shared by every claim/stop/completed-row staleness and
    duration calculation in this module: R8 (08-25 round 4) -- a missing or
    garbage `ts_epoch`/`stop_ts_epoch` must be reaped as stale, never treated
    as fresh/immortal, which a bare `isinstance(epoch, int)` check silently
    did (both a float epoch -- B3 -- and any non-numeric garbage fell into
    the untouched "fresh" branch forever)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sum_transcript_tokens(path: str | None) -> tuple[dict[str, int] | None, int | None, str | None]:
    """Sum per-message `message.usage` over an agent transcript JSONL file.

    Returns (tokens, tokens_total, tokens_error). `tokens` is
    {input, output, cache_read, cache_creation}; `tokens_total` is their
    sum. Both are None together, with `tokens_error` set to the failing
    exception's class name, when `path` cannot be opened or parsed — never
    a silent zero (churn_phase0_measure.md step 2's TOKENS invariant). A
    falsy `path` (no transcript was ever recorded for this dispatch, e.g. a
    reaped `claimed`/`launched` claim) returns (None, None, None) WITHOUT
    attempting to open anything — that is a different, non-error case ("we
    never got as far as having a path") from "we had a path and reading it
    failed," so it must not report the same tokens_error class.

    A transcript that opens and parses fine but has zero usage-bearing
    lines returns an all-zero `tokens` dict with tokens_error=None — a
    legitimately empty transcript is not a read failure.

    Deliberately NEVER reads `tool_response.usage` / `tool_response.
    totalTokens`: the spike result (churn_phase0_measure.md step 1) proved
    those are per-FINAL-message only and under-count real spend by ~3x
    (18,507 vs a real transcript sum of 55,359 for the same dispatch). Every
    `type == "assistant"` line's `message.usage` is summed here (N16, 08-25
    round 4: the code used to sum ANY line carrying a `message.usage` dict
    regardless of `type`, silently diverging from this exact docstring
    claim — the existing test fixture for "ignores non-assistant" happened
    to never give its non-assistant line a `usage` field, so it could never
    have caught the missing filter), no de-duplication — a flat per-message
    sum over the whole transcript is the plan's own spec.

    N17 (08-25 round 4): a single malformed/unparseable JSON LINE is
    SKIPPED, matching `_read_table`'s established self-healing convention
    elsewhere in this module — it must never abort the whole sum (the prior
    behavior threw away every already-summed valid line in the same file
    the instant ONE line failed to parse). `tokens_error` is reserved for a
    genuine FILE-level failure (the path can't be opened/read at all), never
    a per-line parse failure — a file containing nothing but bad lines reads
    as a legitimately empty transcript (all-zero, no error), same as a
    truly-empty file.
    """
    if not path:
        return None, None, None
    try:
        totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue  # N17: one bad line is skipped, never aborts the sum
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") != "assistant":
                    continue
                message = obj.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                totals["input"] += _usage_int(usage.get("input_tokens"))
                totals["output"] += _usage_int(usage.get("output_tokens"))
                totals["cache_read"] += _usage_int(usage.get("cache_read_input_tokens"))
                totals["cache_creation"] += _usage_int(usage.get("cache_creation_input_tokens"))
        total = totals["input"] + totals["output"] + totals["cache_read"] + totals["cache_creation"]
        return totals, total, None
    except Exception as exc:
        return None, None, type(exc).__name__


# WS2.1 step 4 (plan_lane_control_adoption_master_2026_09_20.md §2.1 item 4,
# #5828): observed-model recovery for a spend row whose `model` came back
# null from the normal dispatch-time path (every Workflow-tool leg, whose
# PreToolUse never fires per-leg -- see the runtime probe cited in
# docs/subsystems/telemetry-and-spend.md's 2026-09-20 section -- lands here
# exactly like a genuinely un-annotated background claim does).
MODEL_TRANSCRIPT_MAX_BYTES = 2_000_000  # 2MB tail read cap, see model_from_transcript.


def model_from_transcript(path: str | None, max_bytes: int = MODEL_TRANSCRIPT_MAX_BYTES) -> tuple[str | None, str | None]:
    """Recover the real model string from an agent transcript's OWN
    `message.model` field (assistant-role lines only), never a guess.

    Returns (model, error). `model` is the LAST assistant line's
    `message.model` seen within the read window -- every real transcript
    sampled while building this (agent-level and Workflow-leg-level alike,
    both `~/.claude/projects/*/subagents/*.jsonl` and `.../subagents/
    workflows/<run>/agent-*.jsonl`) carried exactly ONE model string across
    every assistant line, so "last seen" and "most common" coincide in
    every observed case; LAST is chosen over FIRST because a live model
    escalation/downgrade mid-dispatch (never observed, but not structurally
    impossible) would make the tail of the transcript -- the model that
    actually produced the dispatch's final output -- the more representative
    single value to attribute the whole row to.

    Bounded read (N per module docstring's exception-wrapped end-to-end
    requirement): only the LAST `max_bytes` bytes of a REGULAR FILE are
    read (a plain `seek()` from the end), never the whole file -- real
    transcripts on this machine run up to ~39MB, and reading one in full on
    every SubagentStop join would risk stalling the hook. Reading from the
    tail is also the cheapest-correct strategy given the "last assistant
    line wins" rule above: the answer is almost always near the end of the
    file. The first (possibly partial) line inside the read window is
    discarded -- `seek()` lands mid-line in the common case, and a partial
    line can never parse as valid JSON, so `json.loads` failing on it and
    being skipped by the same per-line self-healing convention as
    `sum_transcript_tokens` already produces the right behavior for free;
    if EVERY line in the window is discarded/unparseable (a transcript with
    a single assistant message larger than `max_bytes`, or windows landing
    entirely inside non-assistant content), `model` is None with no error
    -- a genuinely unrecoverable-within-budget case, not a failure.

    NON-REGULAR FILES ARE REFUSED BEFORE ANY READ (fix round, 2026-09-20
    trust-architect review, BLOCKER): `os.path.getsize` returns 0 for a
    character device or FIFO, which defeats the `size > max_bytes` seek
    decision entirely -- a symlink to `/dev/zero` made the old code's bare
    `fh.read()` genuinely unbounded (executed: 8.8GB RSS in 13s, OOM-killed)
    and a FIFO blocks in `open()` forever, a hang `except Exception` can
    never catch. Since this runs under the caller's `admission_lock`, that
    hang would hold the shared ledger lock indefinitely and every
    concurrent `release_hook` on the machine would time out and drop its
    spend row. Fixed at the root: `os.stat(path)` (follows symlinks, same
    as `getsize`) is checked with `stat.S_ISREG` BEFORE any `open()` --
    anything that is not a plain regular file (FIFO, char/block device,
    directory, socket) returns `(None, "NotARegularFile")` immediately,
    never attempting to read it. `size = st.st_size` from that same `stat()`
    call for a real regular file (not a second `os.path.getsize` call) is
    then used exactly as before. The `fh.read()` call is additionally
    changed to `fh.read(max_bytes)` (a belt-and-braces bounded read) so
    even a regular file that somehow reports fewer bytes via `stat` than it
    actually contains (a rare TOCTOU race, not the FIFO/device case above,
    which `S_ISREG` already excludes) can never read past `max_bytes` from
    the post-seek position.

    A falsy `path` returns (None, None) without attempting to open
    anything -- same "no path was ever recorded" contract as
    `sum_transcript_tokens(None)`. Any file-level failure (missing,
    unreadable, permission, or a non-regular-file refusal) returns (None,
    <exception class name> or "NotARegularFile"). A malformed individual
    line is skipped, never raised. Never raises.
    """
    if not path:
        return None, None
    try:
        st = os.stat(path)  # follows symlinks, like the old getsize did
        if not stat.S_ISREG(st.st_mode):
            return None, "NotARegularFile"
        size = st.st_size
        with open(path, encoding="utf-8", errors="replace") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            chunk = fh.read(max_bytes)  # belt-and-braces bounded read
        lines = chunk.split("\n")
        # The first element is very likely a partial line when we seeked
        # into the middle of the file; drop it unconditionally when a seek
        # happened (size > max_bytes) since it can never be a complete,
        # parseable JSON line in that case, and leaving it in costs nothing
        # (json.loads would fail on it anyway) but this is the documented,
        # deliberate behavior rather than an incidental one.
        if size > max_bytes and lines:
            lines = lines[1:]
        model: str | None = None
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant":
                continue
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            candidate = message.get("model")
            if isinstance(candidate, str) and candidate:
                model = candidate  # last-seen wins; see docstring.
        return model, None
    except Exception as exc:
        return None, type(exc).__name__


def _build_claim_record(payload: dict) -> dict | None:
    """Pure: build the gate-time claim record from a PreToolUse:Task
    payload, or None when it carries no real `tool_use_id`. A minted
    fallback id (see `_gate_agent_id`) only ever keys the PACER's own
    lease — it is never releasable by a real PostToolUse/SubagentStop event
    (which always carries the true id, per the spike artifact), so a claim
    keyed on one would sit forever un-joinable; better to record nothing
    than a claim that can only ever be TTL-reaped. `agent_type` comes from
    `tool_input.subagent_type` and `model_requested` from `tool_input.model`
    — the SAME tool_input the PostToolUse payload mirrors back (verified
    against the spike artifact's own PostToolUse.tool_input), since gate
    never sees tool_response.resolvedModel (that only exists once the Task
    has actually launched).
    """
    tool_use_id = _lib.tool_use_id(payload)
    if not tool_use_id:
        return None
    ti = payload.get("tool_input")
    ti = ti if isinstance(ti, dict) else {}
    agent_type = ti.get("subagent_type")
    model_requested = ti.get("model")
    return {
        "tool_use_id": tool_use_id,
        "ts": _lib._now(),
        "ts_epoch": _now_epoch_f(),
        "agent_type": agent_type if isinstance(agent_type, str) else None,
        "model_requested": model_requested if isinstance(model_requested, str) else None,
        "session": _lib.session_id(payload),
        "agent_id": None,
        "model": None,
    }


def classify_release_event(payload: dict) -> dict | None:
    """Pure: classify a release_hook payload into one of three spend-ledger
    events, or None when it matches neither known shape.

    Field names/paths verified against the real spike artifact (churn_
    phase0_measure.md step 1, recorded 2026-08-25): SubagentStop carries
    top-level agent_id/agent_type/agent_transcript_path and NEVER
    tool_use_id; PostToolUse carries top-level tool_use_id and duration_ms,
    with tool_response.{status, agentId, resolvedModel, totalTokens}
    nested — `tool_name` is the literal string "Agent" on both PostToolUse
    branches (never "Task"; the "Task" name only ever appears as the hook
    MATCHER in settings.json, not in the payload). Never raises: `payload`
    is whatever `_lib.read_event()` produced, itself never-raising, so
    every field access here is defensively typed rather than assumed
    present.
    """
    try:
        hook_event = payload.get("hook_event_name")
    except Exception:
        return None
    if hook_event == "SubagentStop":
        agent_id = payload.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            return None  # nothing to key a pending-stop record on
        agent_type = payload.get("agent_type")
        transcript = payload.get("agent_transcript_path")
        has_transcript = isinstance(transcript, str) and transcript
        return {
            "kind": "subagent_stop",
            "agent_id": agent_id,
            "agent_type": agent_type if isinstance(agent_type, str) else None,
            "agent_transcript_path": transcript if has_transcript else None,
        }
    if hook_event == "PostToolUse" and payload.get("tool_name") == "Agent":
        tr = payload.get("tool_response")
        tr = tr if isinstance(tr, dict) else {}
        status = tr.get("status")
        tool_use_id = payload.get("tool_use_id")
        tool_use_id = tool_use_id if isinstance(tool_use_id, str) and tool_use_id else None
        agent_id = tr.get("agentId")
        agent_id = agent_id if isinstance(agent_id, str) and agent_id else None
        model = tr.get("resolvedModel")
        model = model if isinstance(model, str) and model else None
        if status == "async_launched":
            return {
                "kind": "post_tool_use_async_launched",
                "tool_use_id": tool_use_id,
                "agent_id": agent_id,
                "model": model,
            }
        if status == "completed":
            duration = payload.get("duration_ms")
            duration = (
                duration if isinstance(duration, int) and not isinstance(duration, bool) else None
            )
            total_tokens = tr.get("totalTokens")
            total_tokens = (
                total_tokens
                if isinstance(total_tokens, int) and not isinstance(total_tokens, bool)
                else None
            )
            return {
                "kind": "post_tool_use_completed",
                "tool_use_id": tool_use_id,
                "agent_id": agent_id,
                "model": model,
                "duration_ms": duration,
                "payload_total_tokens": total_tokens,
            }
    return None


def _resolve_model_and_source(
    existing_model: str | None, transcript_path: str | None
) -> tuple[str | None, str | None]:
    """WS2.1 step 4: fill a still-null `model` from the transcript's own
    `message.model`, tagging provenance so an existing dispatch-derived
    value is NEVER overwritten and NEVER silently reattributed.

    Returns (model, model_source). When `existing_model` is already a real
    non-empty string, it is returned unchanged with `model_source: None` --
    this module never stamps a provenance tag on a value it didn't itself
    derive (a value from the dispatch-time path -- `model_requested`/
    `resolvedModel` -- keeps whatever, if anything, a caller already set
    for it; this function only ever ADDS a source for the null case it
    fills). When `existing_model` is null/missing and a transcript path is
    known, `model_from_transcript` is consulted; a recovered value is
    tagged `model_source: "transcript"`. When nothing is recoverable
    either way (no existing model, no transcript, or the transcript read
    failed/found nothing), `model` is None and `model_source: "unavailable"`
    -- mirroring the existing AA-0053 `stopped-unjoined` convention (see
    `reap_stale`'s own docstring) that a bare null must be distinguishable
    from "never looked" versus "looked and found nothing."

    Exception-wrapped end to end (module docstring's own requirement for
    this WS2.1 step 4 addition): any failure inside `model_from_transcript`
    itself already degrades to (None, <exc class>) rather than raising (see
    that function's own contract), and a transcript-level read error is
    logged once here (`_lib.log`, itself best-effort/never-raising) rather
    than surfaced to the caller -- this function itself has no code path
    that can raise, so no caller needs its own try/except around it, but it
    is still wrapped for defense in depth against a future edit that adds
    one.
    """
    try:
        if isinstance(existing_model, str) and existing_model:
            return existing_model, None
        if not transcript_path:
            return None, "unavailable"
        recovered, error = model_from_transcript(transcript_path)
        if error is not None:
            _lib.log(
                "agent_budget",
                "model_from_transcript_error",
                transcript_path=transcript_path,
                error=error,
            )
        if isinstance(recovered, str) and recovered:
            return recovered, "transcript"
        return None, "unavailable"
    except Exception:
        return None, "unavailable"


def _release_line_from_join(claim: dict, stop: dict) -> dict:
    """Assemble a released spend.jsonl line from a matched (claim,
    pending-stop) pair — the BACKGROUND release shape (SubagentStop found
    an already-annotated claim, or an async_launched annotation found a
    waiting pending-stop record). `duration_ms` = stop_ts - claim_ts in
    milliseconds per the plan's background rule (never the payload's own
    ~3ms launch-event duration_ms, which is meaningless for a background
    dispatch). Clamped to >= 0 as a defensive guard against clock skew
    between the two epoch reads. `tokens` always comes from the pending-
    stop's own recorded `agent_transcript_path` — never derived.

    B3 (08-25 round 4): both epochs are now the FLOAT, sub-second-precision
    `_now_epoch_f()` (see that function's docstring for why a whole-second
    int quantised a fast dispatch's duration to 0), rounded to the nearest
    millisecond rather than truncated. `_is_number` (not a bare
    `isinstance(..., int)`) validates both fields so a float epoch is
    actually accepted, not silently treated as missing.

    R5 (08-25 round 4): `claim` may be a SYNTHETIC row `handle_async_
    launched` fabricated (marked `claim["synthetic"] = True`) when no real
    gate-time claim was ever found — it carries only tool_use_id/agent_id/
    model (ts/session/agent_type are genuinely unknown, never guessed).
    The resulting line is flagged `late: True` in that case (there was no
    real claim, exactly like `handle_completed`'s own `late` semantics for
    the identical "no claim" situation) and `join_state: "no-claim"` (a
    real STOP fed this line, but no real CLAIM ever did).

    F7 (08-25 round 5): `ts` falls back to the stop's own `stop_ts` when
    the claim never carried one (a synthetic claim's `ts` is always None,
    per R5 above) -- the pre-fix `claim.get("ts")` alone wrote a literal
    JSON null for every `no-claim` line, making it invisible to the
    `spend --since` filter (a plain string comparison against `ts`) and
    grouping into an `"unknown"` day bucket in `spend --by day`, even
    though a real timestamp (the SubagentStop's own) was sitting right
    there in `stop`.

    N9: for a `no-claim` (synthetic) line, `duration_ms` is necessarily
    measured from THIS event's own annotation time (`ts_epoch`, set at
    `PostToolUse(async_launched)`, since no real gate-time claim ever
    existed to time the dispatch from its true start) to the stop -- an
    UNDER-report of the real end-to-end duration by however long the Task
    call spent between PreToolUse:Task and its own async_launched event.
    Any consumer that needs the precise figure should filter on
    `join_state == "no-claim"` rather than trust `duration_ms` at face
    value for those rows.
    """
    transcript_path = stop.get("agent_transcript_path")
    tokens, tokens_total, tokens_error = sum_transcript_tokens(transcript_path)
    duration_ms = None
    claim_epoch = claim.get("ts_epoch")
    stop_epoch = stop.get("stop_ts_epoch")
    if _is_number(claim_epoch) and _is_number(stop_epoch):
        duration_ms = max(0, round((stop_epoch - claim_epoch) * 1000))
    synthetic = bool(claim.get("synthetic"))
    # WS2.1 step 4: a claim's own `model` field is only ever set at
    # PostToolUse(async_launched) (see annotate_claim) -- for a Workflow
    # leg that never happens (no PreToolUse:Task fires per-leg, so no claim
    # is ever annotated with a model), so this is precisely the join site
    # that needs the transcript fallback. Never touches a real dispatch-
    # supplied model.
    model, model_source = _resolve_model_and_source(claim.get("model"), transcript_path)
    line = {
        "ts": claim.get("ts") or stop.get("stop_ts"),
        "session": claim.get("session"),
        "agent_type": claim.get("agent_type") or stop.get("agent_type"),
        "model": model,
        "tool_use_id": claim.get("tool_use_id"),
        "agent_id": claim.get("agent_id") or stop.get("agent_id"),
        "duration_ms": duration_ms,
        "tokens": tokens,
        "tokens_total": tokens_total,
        "tokens_error": tokens_error,
        "late": synthetic,
        "unreleased": False,
        "reaped": None,
        # R4 (08-25 round 4): additive field -- "joined" when both a REAL
        # claim AND a stop/transcript fed this line (the healthy common
        # case); "no-claim" when the claim was synthetic (R5) -- a real
        # stop fed it, but no real claim ever did. churn_report ignores
        # unknown fields, so this never affects an existing consumer.
        "join_state": "no-claim" if synthetic else "joined",
    }
    if model_source is not None:
        line["model_source"] = model_source
    return line


def _release_line_from_completed_join(
    pending_completed: dict, stop_row: dict, transcript_path: str | None
) -> dict:
    """B1 fix (08-25 round 4): assemble the spend line for the "gate ->
    completed -> stop" ordering once the delayed SubagentStop finally
    arrives and joins with the pending-completed record `handle_completed`
    persisted (see `pop_pending_completed_by_agent_id`). Mirrors
    `handle_completed`'s own "stop found" line shape and SOURCE REJECTION
    invariant check exactly -- the only thing that changed between "the
    join happened synchronously inside handle_completed" and "the join
    happened here, one event later" is WHEN the transcript became
    available, never the shape of the resulting line. B2: `agent_type`
    falls back claim -> stop, matching `_release_line_from_join`'s own
    fallback (the live bug this fixes: a foreground line with no matching
    claim reading `agent_type: null` despite SubagentStop's own payload
    carrying a real one).
    """
    claim = pending_completed.get("claim")
    tokens, tokens_total, tokens_error = sum_transcript_tokens(transcript_path)
    payload_total_tokens = pending_completed.get("payload_total_tokens")
    tool_use_id = pending_completed.get("tool_use_id")
    agent_id = pending_completed.get("agent_id")
    if (
        tokens_total is not None
        and payload_total_tokens is not None
        and tokens_total < payload_total_tokens
    ):
        _lib.log(
            "agent_budget",
            "token_invariant_violation",
            tool_use_id=tool_use_id,
            agent_id=agent_id,
            transcript_total=tokens_total,
            payload_total=payload_total_tokens,
        )
    late = claim is None
    # WS2.1 step 4: same transcript fallback as _release_line_from_join --
    # this join site's `model` is otherwise only ever the payload's own
    # `resolvedModel` (pending_completed.get("model")) or the claim's
    # gate-time `model_requested`; a Workflow leg supplies neither.
    existing_model = pending_completed.get("model") or (
        claim.get("model_requested") if claim else None
    )
    model, model_source = _resolve_model_and_source(existing_model, transcript_path)
    line = {
        "ts": claim.get("ts") if claim else pending_completed.get("completed_ts"),
        "session": claim.get("session") if claim else None,
        "agent_type": (claim.get("agent_type") if claim else None) or stop_row.get("agent_type"),
        "model": model,
        "tool_use_id": tool_use_id,
        "agent_id": agent_id or stop_row.get("agent_id"),
        "duration_ms": pending_completed.get("duration_ms"),
        "tokens": tokens,
        "tokens_total": tokens_total,
        "tokens_error": tokens_error,
        "late": late,
        "unreleased": False,
        "reaped": None,
        # R4: a real stop/transcript always fed this line (that's what
        # triggered this join at all); join_state distinguishes whether the
        # CLAIM side was also real ("joined") or was never found ("no-claim"
        # — matches handle_completed's own vocabulary for the identical
        # distinction on its own "stop found" branch).
        "join_state": "joined" if claim is not None else "no-claim",
    }
    if model_source is not None:
        line["model_source"] = model_source
    return line


def record_claim(budget_dir: str, claim: dict, lock_timeout: float) -> None:
    """gate: append a new claim row under the shared admission lock.

    Fail-open: any error (including a failed lock acquisition) is
    swallowed — a lost claim degrades to a missing/late spend line later,
    never a wedged dispatch. Called ONLY on an admitted gate (see decide()'s
    gate branch and _apply_pacer_gate) — a denied dispatch never ran, so it
    must never get a claim recorded.

    N18 (08-25 round 4): upserts on `tool_use_id` -- a duplicate gate firing
    for the SAME tool_use_id (e.g. a retried/duplicated PreToolUse:Task hook
    call) replaces the existing claim row rather than appending a second
    one, which would otherwise sit as a permanent phantom (only whichever
    row a later join actually matches ever gets consumed; the duplicate can
    only ever be TTL-reaped as a spurious second spend line for the same
    dispatch).
    """
    tool_use_id = claim.get("tool_use_id")
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="record_claim",
                    tool_use_id=tool_use_id,
                )
                return
            rows = _read_table(claims_path(budget_dir))
            if tool_use_id:
                rows, _existing = pop_claim_by_tool_use_id(rows, tool_use_id)
            rows.append(claim)
            _write_table(claims_path(budget_dir), rows)
    except Exception:
        return


def handle_async_launched(
    budget_dir: str,
    lock_timeout: float,
    tool_use_id: str | None,
    agent_id: str | None,
    model: str | None,
) -> None:
    """PostToolUse(async_launched): annotate the claim with agent_id/model;
    if a pending-stop record for that agent_id already exists (a fast
    subagent beat this hook — separate OS processes), join and release now.
    Otherwise just persist the annotation for SubagentStop to find later.

    R5 (08-25 round 4): when NO claim is on record at all (the ledger was
    off at gate time, or the claim was already reaped) this used to be a
    genuine no-op — annotate_claim() has nothing to annotate, so nothing
    was ever persisted, leaving the LATER SubagentStop with no claim to
    join either (its only recourse: persist an unmatched pending-stop that
    can only ever be TTL-reaped as a "stopped-unjoined" finding, never a
    real dispatch line). Fixed: write a SYNTHETIC claim row instead,
    carrying only what THIS event actually knows (tool_use_id/agent_id/
    model — never a guessed ts/session/agent_type), marked
    `claim["synthetic"] = True` so `_release_line_from_join` flags the
    eventual release line `late: True` (see that function's own docstring).
    If a pending-stop ALREADY exists at this point (mirroring the annotated
    branch's own "fast subagent beat this hook" case below), join and
    release immediately using the synthetic claim rather than persisting it
    for later.

    Fail-open; never raises.
    """
    if not tool_use_id or not agent_id:
        return
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="handle_async_launched",
                    tool_use_id=tool_use_id,
                )
                return
            claim_rows = _read_table(claims_path(budget_dir))
            claim_rows, updated = annotate_claim(claim_rows, tool_use_id, agent_id, model)
            if updated is None:
                # R5: no claim on record -- synthesize one so the stop can
                # still join, rather than a silent no-op.
                synthetic_claim = {
                    "tool_use_id": tool_use_id,
                    "ts": None,
                    "ts_epoch": _now_epoch_f(),
                    "agent_type": None,
                    "model_requested": None,
                    "session": None,
                    "agent_id": agent_id,
                    "model": model,
                    "synthetic": True,
                }
                stop_rows = _read_table(stops_path(budget_dir))
                stop_rows, stop = pop_stop_by_agent_id(stop_rows, agent_id)
                claim_rows.append(synthetic_claim)
                if stop is None:
                    _write_table(claims_path(budget_dir), claim_rows)
                    return
                # A pending-stop already exists -- join and release now,
                # same as the annotated branch's own "fast subagent" case.
                # R7 (08-25 round 4): append the spend line BEFORE writing
                # the pruned tables back — see this module's own R7 note
                # (search "R7") for why the ordering matters: a crash
                # between the two writes must degrade to, at worst, a
                # RE-PROCESSABLE (later deduped) claim/stop, never a
                # dispatch that's gone from every table with no spend line
                # ever written for it.
                claim_rows, _ = pop_claim_by_tool_use_id(claim_rows, tool_use_id)
                line = _release_line_from_join(synthetic_claim, stop)
                _append_jsonl(spend_path(budget_dir), line)
                _write_table(claims_path(budget_dir), claim_rows)
                _write_table(stops_path(budget_dir), stop_rows)
                return
            stop_rows = _read_table(stops_path(budget_dir))
            stop_rows, stop = pop_stop_by_agent_id(stop_rows, agent_id)
            if stop is None:
                # Normal ordering: no stop yet — persist the annotation only.
                _write_table(claims_path(budget_dir), claim_rows)
                return
            # Fast subagent beat this hook — join and release now. R7: spend
            # line appended before the pruned tables are written back.
            claim_rows, _ = pop_claim_by_tool_use_id(claim_rows, tool_use_id)
            _append_jsonl(spend_path(budget_dir), _release_line_from_join(updated, stop))
            _write_table(claims_path(budget_dir), claim_rows)
            _write_table(stops_path(budget_dir), stop_rows)
    except Exception:
        return


def handle_subagent_stop(
    budget_dir: str,
    lock_timeout: float,
    agent_id: str | None,
    agent_type: str | None,
    agent_transcript_path: str | None,
) -> None:
    """SubagentStop. Three possible joins, checked in order, then a
    fall-through that ALWAYS persists a pending-stop record (never a
    no-op — this is what makes the join order-independent):

      1. B1 (08-25 round 4): a PENDING-COMPLETED record already exists for
         this agent_id (`handle_completed` saw PostToolUse(completed)
         arrive FIRST, before this SubagentStop -- the "gate -> completed
         -> stop" ordering -- and deferred instead of writing a line with
         no transcript). Join with it now that the transcript is finally
         known (`_release_line_from_completed_join`) and consume it. Must
         be checked BEFORE the claim-based join below: `handle_completed`
         already popped the claim by tool_use_id in this case, so the
         claim-based join would never match it anyway, but checking
         pending-completed first keeps the two joins from ever racing on
         the same agent_id.
      2. A claim is already annotated with this agent_id (background,
         PostToolUse(async_launched) already ran) — join and release now,
         duration_ms = stop_ts - claim_ts.
      3. Neither (foreground before its PostToolUse(completed), or a
         background launch hook that hasn't annotated yet) — leave a fresh
         pending-stop record (`kind: "stop"`) for whichever event arrives
         next to find.

    Fail-open; never raises.
    """
    if not agent_id:
        return
    try:
        stop_row = {
            "kind": "stop",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "agent_transcript_path": agent_transcript_path,
            "stop_ts": _lib._now(),
            "stop_ts_epoch": _now_epoch_f(),
        }
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="handle_subagent_stop",
                    tool_use_id=None,
                    agent_id=agent_id,
                )
                return
            stop_rows = _read_table(stops_path(budget_dir))
            # Drop any stale duplicate pending-STOP for this agent_id first
            # (overwrite) — never touches a pending-COMPLETED row (kind
            # filtered, see pop_stop_by_agent_id).
            stop_rows, _existing = pop_stop_by_agent_id(stop_rows, agent_id)

            # R7 (08-25 round 4): in BOTH join branches below, the spend
            # line is appended BEFORE the pruned table(s) are written back
            # — see the module header's "R7" note. A crash between the two
            # writes then degrades to a re-processable row still sitting in
            # its table (later deduped by tool_use_id, per churn_report's
            # own dedup rule), never a dispatch that vanishes from every
            # table with no spend line ever written for it.
            stop_rows, pending_completed = pop_pending_completed_by_agent_id(stop_rows, agent_id)
            if pending_completed is not None:
                line = _release_line_from_completed_join(
                    pending_completed, stop_row, agent_transcript_path
                )
                _append_jsonl(spend_path(budget_dir), line)
                _write_table(stops_path(budget_dir), stop_rows)
                return

            claim_rows = _read_table(claims_path(budget_dir))
            claim_rows, claim = pop_claim_by_agent_id(claim_rows, agent_id)
            if claim is None:
                stop_rows.append(stop_row)
                _write_table(stops_path(budget_dir), stop_rows)
                return
            # Background, already annotated — join and release now. The stop
            # record is consumed immediately (never persisted), since we just
            # released using it.
            _append_jsonl(spend_path(budget_dir), _release_line_from_join(claim, stop_row))
            _write_table(claims_path(budget_dir), claim_rows)
            _write_table(stops_path(budget_dir), stop_rows)
    except Exception:
        return


def handle_completed(
    budget_dir: str,
    lock_timeout: float,
    tool_use_id: str | None,
    agent_id: str | None,
    model: str | None,
    duration_ms: int | None,
    payload_total_tokens: int | None = None,
) -> None:
    """PostToolUse(completed) — the foreground release: join on agentId to
    the pending-stop record SubagentStop left (for its recorded transcript
    path), then release BY tool_use_id (never by agent_id — foreground
    claims are never annotated, since async_launched only ever fires for a
    background dispatch). `duration_ms` is the payload's OWN field (the
    harness's real measurement of the blocking call), never derived from
    claim/stop timestamps. A claim that can't be found (already reaped) still
    produces a spend line, flagged `late: true`, rather than losing the
    dispatch entirely — `ts`/`session`/`agent_type` fall back to None/now()
    in that case since the claim (their only source) is gone.

    B1 (08-25 round 4) — the fourth ordering, "gate -> completed -> stop":
    when NO pending-stop exists yet for this agent_id (SubagentStop hasn't
    fired), this used to write a spend line immediately anyway, with
    `tokens: null` (no transcript path known yet). The LATER SubagentStop
    would then find its claim already consumed and could only ever persist
    a fresh, unmatched pending-stop — eventually reaped as a phantom
    "stopped-unjoined" finding: TWO lines for one dispatch, and the real
    line's tokens permanently null even though the real transcript existed
    all along. Fixed symmetrically with SubagentStop's own "no claim yet"
    branch: persist a PENDING-COMPLETED record (`kind: "completed"`, same
    physical table as pending-stop rows) instead of writing a line now, and
    let `handle_subagent_stop`'s join (see its docstring) complete it once
    the transcript is known. Only when `agent_id` itself is falsy (so no
    later SubagentStop could ever be matched to this dispatch anyway) does
    this still write immediately, same as before.

    Also enforces the SOURCE REJECTION invariant (churn_phase0_measure.md
    step 2): if the transcript-derived total is LESS than the payload's own
    (rejected) `tool_response.totalTokens`, that is a real anomaly — the
    transcript should always be a superset of the final message it derives
    from — and gets logged via `_lib.log` as `token_invariant_violation`
    (this module's existing structured-decision-log mechanism is the
    established convention for a persisted, auditable WARNING here; nothing
    in this codebase uses Python's `logging` module). It is never raised and
    never changes which total is written — the transcript total is ALWAYS
    what's recorded, win or lose the comparison.
    """
    if not tool_use_id:
        return
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="handle_completed",
                    tool_use_id=tool_use_id,
                )
                return
            # R7 (08-25 round 4): every write below is deferred until AFTER
            # whichever "risky" write actually matters has landed (the
            # deferred pending-completed row, or the final spend line) —
            # see the module header's own "R7" note. Popping claim_rows/
            # stop_rows here is purely IN-MEMORY; `_write_table` is never
            # called until the corresponding spend.jsonl/stops.jsonl write
            # that depends on it has already succeeded, so a crash between
            # the two can only ever leave a RE-PROCESSABLE row sitting in
            # its original table (later deduped by tool_use_id), never
            # erase all evidence of a dispatch that never got recorded.
            transcript_path = None
            stop = None
            stop_rows = None
            if agent_id:
                stop_rows = _read_table(stops_path(budget_dir))
                stop_rows, stop = pop_stop_by_agent_id(stop_rows, agent_id)
                if stop is not None:
                    transcript_path = stop.get("agent_transcript_path")

            claim_rows = _read_table(claims_path(budget_dir))
            claim_rows, claim = pop_claim_by_tool_use_id(claim_rows, tool_use_id)

            if stop is None and agent_id:
                # B1: no pending-stop yet -- defer instead of writing a
                # tokenless line now (see docstring above). Never a no-op:
                # overwrite any stale duplicate pending-completed first.
                # `stop_rows` here is the SAME table already read+popped
                # above (unchanged, since nothing matched) — reused rather
                # than re-read.
                stop_rows, _existing = pop_pending_completed_by_agent_id(stop_rows, agent_id)
                # R2 (08-25 round 5) regression fix: a DUPLICATE
                # PostToolUse(completed) firing for the same tool_use_id
                # (before its own SubagentStop ever arrives) finds
                # claims.jsonl already emptied by the FIRST firing (which
                # already consumed the claim into `_existing`'s own `claim`
                # field) -- so `claim` here is None on the repeat, even
                # though real attribution (session/agent_type/
                # model_requested) was already recorded once. Overwriting
                # unconditionally with this firing's own (now-empty) claim
                # silently discarded that attribution; carry the PRIOR
                # row's claim forward whenever this firing didn't find one
                # of its own.
                effective_claim = (
                    claim if claim is not None else (_existing.get("claim") if _existing else None)
                )
                stop_rows.append(
                    {
                        "kind": "completed",
                        "agent_id": agent_id,
                        "tool_use_id": tool_use_id,
                        "model": model,
                        "duration_ms": duration_ms,
                        "payload_total_tokens": payload_total_tokens,
                        "claim": effective_claim,
                        "completed_ts": _lib._now(),
                        "stop_ts_epoch": _now_epoch_f(),
                    }
                )
                # R7: the pending-completed row (the thing a LATER
                # SubagentStop needs to find) is written FIRST; the claim's
                # removal from claims.jsonl is written second and only
                # matters for cleanliness (see the module's R7 note — the
                # claim is now fully embedded inside the pending-completed
                # row itself, so losing this second write to a crash costs
                # nothing beyond a stale, separately-reapable claim row that
                # dedup_spend_lines collapses away later).
                _write_table(stops_path(budget_dir), stop_rows)
                if claim is not None:
                    _write_table(claims_path(budget_dir), claim_rows)
                return

            tokens, tokens_total, tokens_error = sum_transcript_tokens(transcript_path)
            if (
                tokens_total is not None
                and payload_total_tokens is not None
                and tokens_total < payload_total_tokens
            ):
                _lib.log(
                    "agent_budget",
                    "token_invariant_violation",
                    tool_use_id=tool_use_id,
                    agent_id=agent_id,
                    transcript_total=tokens_total,
                    payload_total=payload_total_tokens,
                )
            late = claim is None
            # R4: additive join_state -- "joined" when both a claim AND a
            # stop/transcript fed this line, "claim-consumed" when a claim
            # was found but no stop ever will be (agent_id was falsy, so no
            # SubagentStop could ever match), "no-claim" when the claim was
            # never found either (the pre-existing `late` case).
            if claim is not None and stop is not None:
                join_state = "joined"
            elif claim is not None:
                join_state = "claim-consumed"
            else:
                join_state = "no-claim"
            line = {
                "ts": claim.get("ts") if claim else _lib._now(),
                "session": claim.get("session") if claim else None,
                # B2 (08-25 round 4): fall back to the STOP's own agent_type
                # when the claim never carried one (or was never found) --
                # the live bug this fixes produced a real 25.9M-token Opus
                # spend line with agent_type: null despite SubagentStop's
                # own payload carrying the real value.
                "agent_type": (claim.get("agent_type") if claim else None)
                or (stop.get("agent_type") if stop else None),
                # B2: model falls back to the claim's OWN `model_requested`
                # (set at gate time from tool_input.model) -- `claim.get(
                # "model")` is ALWAYS None for a foreground claim, since
                # only handle_async_launched (background-only) ever
                # annotates that field; falling back to it here was a bug,
                # never a legitimate source for a foreground dispatch.
                "model": model or (claim.get("model_requested") if claim else None),
                "tool_use_id": tool_use_id,
                "agent_id": agent_id or (claim.get("agent_id") if claim else None),
                "duration_ms": duration_ms,
                "tokens": tokens,
                "tokens_total": tokens_total,
                "tokens_error": tokens_error,
                "late": late,
                "unreleased": False,
                "reaped": None,
                "join_state": join_state,
            }
            # R7: the spend line lands BEFORE the pruned claim/stop tables
            # are written back (see this function's opening R7 note).
            _append_jsonl(spend_path(budget_dir), line)
            if stop is not None:
                _write_table(stops_path(budget_dir), stop_rows)
            if claim is not None:
                _write_table(claims_path(budget_dir), claim_rows)
    except Exception:
        return


def _pending_stop_marker_path(budget_dir: str, agent_id: str) -> str:
    """Absolute path of the PACER's own pending-stop marker for `agent_id`
    (see PENDING_STOP_PREFIX's own docstring)."""
    return os.path.join(budget_dir, PENDING_STOP_PREFIX + safe_id(agent_id))


def _write_pending_stop_marker(budget_dir: str, agent_id: str) -> None:
    """Best-effort: persist a pending-stop marker for `agent_id`. Caller
    holds admission_lock. Never raises."""
    _ensure_dir(budget_dir)
    path = _pending_stop_marker_path(budget_dir, agent_id)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"agent_id={agent_id}\nstopped_at={_lib._now()}\n")
    except Exception:
        return


def _has_pending_stop_marker(budget_dir: str, agent_id: str) -> bool:
    """True iff a pending-stop marker is on disk for `agent_id`. Never
    raises."""
    try:
        return os.path.isfile(_pending_stop_marker_path(budget_dir, agent_id))
    except Exception:
        return False


def _lease_dispatch_agent_id(path: str) -> str | None:
    """Read the `dispatch_agent_id=` line from a lease file, or None if
    absent/unreadable. See `annotate_lease_dispatch_agent_id`'s docstring
    for what writes this field. Never raises."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("dispatch_agent_id="):
                    value = line[len("dispatch_agent_id=") :].rstrip("\n")
                    return value or None
    except Exception:
        return None
    return None


def annotate_lease_dispatch_agent_id(
    budget_dir: str, lease_key: str, dispatch_agent_id: str
) -> None:
    """R11 fix (08-25 round 5): append a `dispatch_agent_id=<...>` line to
    the lease file for `lease_key` (its tool_use_id under the pacer) once
    PostToolUse(async_launched) resolves the real dispatch agent_id --
    independent of CSA_SPEND_LEDGER (the pacer must be able to resolve its
    own lease<->dispatch mapping without the spend ledger's claims.jsonl,
    which may be entirely unwritten when CSA_SPEND_LEDGER=0 -- the R9
    leak this fixes). `_release_pacer_lease_for_stop` later scans every
    live lease file for this field. No-op if the lease file doesn't exist
    (already released, TTL-reaped, or never claimed under the pacer) or
    already carries this exact `dispatch_agent_id` (idempotent against a
    retried/duplicated async_launched firing for the same tool_use_id).
    Best-effort; never raises. Caller holds admission_lock.
    """
    path = lease_path(budget_dir, lease_key)
    if not os.path.isfile(path):
        return
    if _lease_dispatch_agent_id(path) == dispatch_agent_id:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"dispatch_agent_id={dispatch_agent_id}\n")
    except Exception:
        return


def _find_lease_by_dispatch_agent_id(budget_dir: str, dispatch_agent_id: str) -> str | None:
    """Scan every lease-* file under `budget_dir` for one annotated (by
    `annotate_lease_dispatch_agent_id`) with this `dispatch_agent_id`.
    Returns its path, or None. O(live leases) -- the ledger dir only ever
    holds live agents' concurrency leases (the default cap is ~8), so this
    is cheap. Never raises."""
    try:
        if not os.path.isdir(budget_dir):
            return None
        entries = os.listdir(budget_dir)
    except Exception:
        return None
    for name in entries:
        if not name.startswith(LEASE_PREFIX):
            continue
        path = os.path.join(budget_dir, name)
        if _lease_dispatch_agent_id(path) == dispatch_agent_id:
            return path
    return None


def _release_pacer_lease_for_stop(
    budget_dir: str,
    lock_timeout: float,
    stop_agent_id: str,
    *,
    tool_use_id: str | None = None,
) -> None:
    """R11 fix (08-25 round 5, replacing R9's claims.jsonl-only lookup):
    resolve and release the PACER's own concurrency lease for a
    SubagentStop event using the pacer's OWN state (lease files + the
    pending-stop marker below) -- never claims.jsonl. The R9 version
    leaked EVERY background lease whenever CSA_SPEND_LEDGER=0 (claims.jsonl
    is never written in that mode) and ALSO leaked under the C -> S -> A
    ordering (a fast subagent's SubagentStop beating its own
    PostToolUse(async_launched), so the claim was never annotated yet at
    the moment this ran) -- see agent_pacer.md's own "Safety properties"
    section for the pre-fix failure mode this replaces.

    Two ways to resolve the lease:
      1. `tool_use_id` given directly -- release lease_path(tool_use_id)
         with no scan. N2 (08-25 round 5): unreachable via decide() given
         classify_release_event's fixed output shape (a real SubagentStop
         payload never carries tool_use_id today); kept for direct
         callers.
      2. Otherwise scan every live lease file for one already annotated
         (by `annotate_lease_dispatch_agent_id`, at PostToolUse(
         async_launched)) with `dispatch_agent_id == stop_agent_id`.

    When NEITHER resolves anything -- the C -> S -> A ordering: THIS
    SubagentStop arrived before its own async_launched ever annotated a
    lease -- the dispatch is known finished but the lease can't be found
    yet. Persist a pending-stop MARKER (independent of the spend ledger's
    own stops.jsonl) so the eventual async_launched call releases the
    lease itself the instant it learns the tool_use_id <-> agent_id
    mapping (see `_annotate_pacer_lease_and_maybe_release`). A marker for
    a dispatch that has no lease at all (pacer was off at gate time) or
    whose matching async_launched genuinely never arrives self-heals via
    `prune_and_count`'s own TTL sweep (see PENDING_STOP_PREFIX).

    Fail-open; never raises.
    """
    if not stop_agent_id:
        return
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="release_pacer_lease_for_stop",
                    tool_use_id=tool_use_id,
                    agent_id=stop_agent_id,
                )
                return
            if tool_use_id:
                _remove(lease_path(budget_dir, tool_use_id))
                _remove(_pending_stop_marker_path(budget_dir, stop_agent_id))
                return
            found = _find_lease_by_dispatch_agent_id(budget_dir, stop_agent_id)
            if found:
                _remove(found)
                _remove(_pending_stop_marker_path(budget_dir, stop_agent_id))
                return
            # C -> S -> A: not annotated yet -- leave a marker for the
            # eventual async_launched to find and release immediately.
            _write_pending_stop_marker(budget_dir, stop_agent_id)
    except Exception:
        return


def _annotate_pacer_lease_and_maybe_release(
    budget_dir: str, lock_timeout: float, tool_use_id: str, dispatch_agent_id: str
) -> None:
    """R11 fix (08-25 round 5): PostToolUse(async_launched), PACER path --
    independent of CSA_SPEND_LEDGER, mirroring `annotate_lease_dispatch_
    agent_id`'s own decoupling. Resolves the lease<->dispatch mapping the
    instant it becomes known, so a later SubagentStop can find it purely
    from the lease files.

    If a pending-stop MARKER already exists for `dispatch_agent_id` -- the
    C -> S -> A ordering, a fast subagent's SubagentStop already searched
    for (and failed to find) this lease before this call ever annotated it
    -- the dispatch is ALREADY finished: release the lease right now
    instead of merely annotating it. Annotating-then-waiting-for-a-stop-
    that-already-happened would leak the lease exactly like R9 did (the
    stop event that would have released it already came and went).
    Otherwise just annotate, for the normal A -> S ordering (a later
    SubagentStop will find and release it).

    Fail-open; never raises.
    """
    if not tool_use_id or not dispatch_agent_id:
        return
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log(
                    "agent_budget",
                    "spend_ledger_lock_timeout",
                    op="annotate_pacer_lease",
                    tool_use_id=tool_use_id,
                    agent_id=dispatch_agent_id,
                )
                return
            if _has_pending_stop_marker(budget_dir, dispatch_agent_id):
                _remove(lease_path(budget_dir, tool_use_id))
                _remove(_pending_stop_marker_path(budget_dir, dispatch_agent_id))
                return
            annotate_lease_dispatch_agent_id(budget_dir, tool_use_id, dispatch_agent_id)
    except Exception:
        return


def _apply_spend_event(event: dict, budget_dir: str, lock_timeout: float) -> None:
    """Dispatch one classify_release_event() result to its handler.

    An unrecognized `event["kind"]` is a no-op (should be unreachable given
    classify_release_event's own contract, but fail-open rather than raise).
    """
    kind = event.get("kind")
    if kind == "subagent_stop":
        handle_subagent_stop(
            budget_dir,
            lock_timeout,
            event.get("agent_id"),
            event.get("agent_type"),
            event.get("agent_transcript_path"),
        )
    elif kind == "post_tool_use_async_launched":
        handle_async_launched(
            budget_dir,
            lock_timeout,
            event.get("tool_use_id"),
            event.get("agent_id"),
            event.get("model"),
        )
    elif kind == "post_tool_use_completed":
        handle_completed(
            budget_dir,
            lock_timeout,
            event.get("tool_use_id"),
            event.get("agent_id"),
            event.get("model"),
            event.get("duration_ms"),
            event.get("payload_total_tokens"),
        )


def _model_from_claims_by_agent_id(claims: list[dict], agent_id: str | None) -> str | None:
    """Pure, READ-ONLY lookup (never pops/consumes): the model recorded on
    a still-live claims.jsonl row matching `agent_id`, preferring the
    annotated `model` (set at PostToolUse(async_launched)) and falling
    back to gate-time `model_requested` — mirroring the SAME fallback
    `reap_stale`'s own stale-claims branch already applies to a claim
    reaped by itself (`row.get("model") or row.get("model_requested")`).

    AA-0053: a PENDING-STOP row (`kind: "stop"` in stops.jsonl) never
    carries model info by payload design — the real SubagentStop hook
    event itself has no model field (see `classify_release_event`'s
    `subagent_stop` branch: only agent_id/agent_type/
    agent_transcript_path). When such a row goes stale and is reaped as
    "stopped-unjoined" with no claim ever having joined it in real time
    (`handle_subagent_stop`'s own join already tried and failed), its
    matching claim — if one is STILL live in claims.jsonl at the exact
    moment of this reap pass — is the only other place the model could
    possibly be recovered from. A falsy `agent_id` never matches (an
    un-annotated claim's own `agent_id` is always None too, so a bare
    lookup on a falsy key would wrongly "match" the first un-annotated
    row — same guard `pop_claim_by_agent_id` already applies). Returns
    None (never a guess) when no live claim matches. Pure: `claims` is
    read, never mutated — a matched row is left in place for its OWN
    independent join/reap to consume normally.

    Fail-open: a malformed entry in `claims` (not a dict — should be
    unreachable given `_read_table`'s own dict-only contract, but this is
    called from inside `reap_stale`'s single fail-open `try` block, so a
    non-dict row here must degrade to "no match for that row" rather than
    raise and abort the whole reap pass) is skipped, matching
    `_read_table`'s established self-healing convention elsewhere in this
    module.
    """
    if not agent_id:
        return None
    for row in claims:
        if not isinstance(row, dict):
            continue
        if row.get("agent_id") == agent_id:
            model = row.get("model") or row.get("model_requested")
            return model if isinstance(model, str) and model else None
    return None


def reap_stale(budget_dir: str, ttl: int, lock_timeout: float, now: float | None = None) -> int:
    """Sweep claims.jsonl and stops.jsonl for rows older than `ttl` seconds
    (by claim/stop timestamp, NEVER reap time — see the plan's schema),
    writing a flagged spend.jsonl line for each and removing it from its
    table. Returns the count reaped (0 on any failure — fail open, matching
    this ledger's philosophy: a reaper bug must never wedge a dispatch, it
    just means a stale row sits a while longer).

    Only THREE `reaped` stage labels exist (unchanged by the B1 fix below —
    see R4/join_state for the finer distinction):
      * "claimed"          — the claim has no agent_id at all: the Task
        call itself failed/was denied and never launched (or, for a
        foreground dispatch, its PostToolUse(completed) event never
        arrived — this module has no other evidence either way, so both
        degrade to the same bucket). `join_state` is always "claim-only"
        (08-25 round 5, N8, renamed from the ambiguous "claim-consumed" --
        see the "launched" bullet below for the OTHER, genuinely distinct
        meaning that name still carries elsewhere): only a claims.jsonl
        row ever fed this line, nothing else.
      * "launched"          — the claim HAS an agent_id (PostToolUse(async_
        launched) ran) but no SubagentStop ever joined it — the subagent
        died or was killed. `join_state` is likewise "claim-only" for THIS
        source (a stale claims.jsonl row). ALSO reused (08-25 round 4, B1)
        for a stale PENDING-COMPLETED row (`kind: "completed"` in
        stops.jsonl): `handle_completed` saw the dispatch actually finish
        (it has real duration_ms/payload data, unlike the plain "launched"
        case above) but its SubagentStop -- the only carrier of the
        transcript path -- never arrived either. Conceptually the closest
        existing fit (something ran; its finish/transcript join never
        completed); for THIS source `join_state` is "claim-consumed" (a
        real claim was embedded in the pending-completed row) or
        "no-claim" (it never was) -- distinguishing the two "launched"
        sources from each other via `join_state` instead of a fourth stage
        label.
      * "stopped-unjoined"   — a PENDING-STOP record (`kind: "stop"`,
        including any legacy on-disk row with no `kind` field at all)
        exists with no matching claim ever appearing — a join bug in this
        code, not a dispatch failure (see the plan). Reaped separately, by
        its OWN stop_ts, and — since its `agent_transcript_path` IS known —
        `tokens` is computed from it rather than left null: the done-
        criteria only accept null tokens when no transcript path exists at
        all, and here one does. AA-0053 (08-31): `model` for this stage is
        RECOVERED from a still-live claims.jsonl row matching the same
        agent_id, if one exists at the exact moment of this reap pass
        (`_model_from_claims_by_agent_id` — read-only, never consumes the
        claim) — this was the source of ~44% of all spend rows carrying
        `model: null` (every one of them this exact stage, confirmed by a
        full-ledger audit: 1217/1217 null-model rows were `reaped:
        "stopped-unjoined"`), since a bare PENDING-STOP row's own payload
        (a real SubagentStop event) never carries model info at all. WS2.1
        step 4 (2026-09-20, #5828): when that claims-based lookup ALSO
        comes up empty (the real Workflow-leg shape — no `PreToolUse:Task`
        claim was ever taken for one, so it can never match here either),
        `model` is recovered a SECOND way, from the transcript's own
        `message.model` field (`_resolve_model_and_source` ->
        `model_from_transcript`, the same fallback used at every other
        join site in this module) before finally giving up. Only when
        NEITHER source recovers anything does `model` stay null (never
        fabricated) and the line carry `model_source: "unavailable"`, so a
        future audit can tell "we looked (twice) and there truly was
        nothing" apart from "nothing here ever looked."
    `duration_ms` is null on every stage EXCEPT the completed-kind
    "launched" reap above, where the payload's own duration_ms IS known.

    R8/B3 (08-25 round 4): staleness is decided by `_is_number` (never a
    bare `isinstance(epoch, int)`), which accepts the FLOAT epochs
    `_now_epoch_f()` now writes (B3) and — critically — treats a
    missing/garbage (non-numeric) epoch as immediately stale rather than
    silently "fresh forever" (R8: a garbage timestamp must be reaped, never
    immortal).
    """
    if now is None:
        now = _now_epoch()
    try:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            if not locked:
                _lib.log("agent_budget", "spend_ledger_lock_timeout", op="reap_stale")
                return 0
            claim_rows = _read_table(claims_path(budget_dir))
            fresh_claims: list[dict] = []
            stale_claims: list[dict] = []
            for row in claim_rows:
                epoch = row.get("ts_epoch")
                if not _is_number(epoch) or now - epoch > ttl:
                    stale_claims.append(row)
                else:
                    fresh_claims.append(row)
            stop_rows = _read_table(stops_path(budget_dir))
            fresh_stops: list[dict] = []
            stale_stop_kind: list[dict] = []
            stale_completed_kind: list[dict] = []
            for row in stop_rows:
                epoch = row.get("stop_ts_epoch")
                stale = not _is_number(epoch) or now - epoch > ttl
                if not stale:
                    fresh_stops.append(row)
                elif row.get("kind") == "completed":
                    stale_completed_kind.append(row)
                else:
                    stale_stop_kind.append(row)
            if not stale_claims and not stale_stop_kind and not stale_completed_kind:
                return 0
            # R7 (08-25 round 4): every reaped row's spend line is appended
            # BELOW, BEFORE the pruned (fresh_*) tables are written back —
            # see handle_completed's own R7 note for the identical
            # rationale. Writing the tables first (the old order) meant a
            # crash mid-reap could silently drop a stale row from its table
            # with NO spend line ever recorded for it — a vanished
            # dispatch. With this order, the worst a crash can do is leave
            # a row un-pruned, so it just gets reaped again next time
            # (dedup_spend_lines collapses the resulting duplicate line).
            reaped = 0
            for row in stale_claims:
                stage = "launched" if row.get("agent_id") else "claimed"
                _append_jsonl(
                    spend_path(budget_dir),
                    {
                        "ts": row.get("ts"),
                        "session": row.get("session"),
                        "agent_type": row.get("agent_type"),
                        # F6 (08-25 round 5): a never-annotated claim's own
                        # `model` field is always None (only
                        # PostToolUse(async_launched) ever sets it) -- fall
                        # back to the gate-time `model_requested` (set from
                        # tool_input.model) rather than reap a claim that
                        # DID request a real model as `model: null`.
                        "model": row.get("model") or row.get("model_requested"),
                        "tool_use_id": row.get("tool_use_id"),
                        "agent_id": row.get("agent_id"),
                        "duration_ms": None,
                        "tokens": None,
                        "tokens_total": None,
                        "tokens_error": None,
                        "late": False,
                        "unreleased": True,
                        "reaped": stage,
                        # N8 (08-25 round 5): renamed from "claim-consumed"
                        # -- that label is still used elsewhere (the stale
                        # PENDING-COMPLETED reap below, and handle_completed's
                        # own synchronous no-stop-will-ever-arrive case) for
                        # a genuinely different situation (a claim that WAS
                        # joined into something else). A bare stale
                        # claims.jsonl row was never joined into anything;
                        # "claim-only" says so unambiguously.
                        "join_state": "claim-only",
                    },
                )
                reaped += 1
            for row in stale_stop_kind:
                tokens, tokens_total, tokens_error = sum_transcript_tokens(
                    row.get("agent_transcript_path")
                )
                # AA-0053: a bare PENDING-STOP row never carries model info
                # itself (the real SubagentStop payload has none — see
                # _model_from_claims_by_agent_id's own docstring). Before
                # giving up, check whether a matching claim is STILL live in
                # claims.jsonl at this exact reap pass (read-only — never
                # consumed here, so its own independent join/reap is
                # unaffected).
                recovered_model = _model_from_claims_by_agent_id(fresh_claims, row.get("agent_id"))
                model_source: str | None = None
                # WS2.1 step 4: this is the EXACT write site the measured
                # fact behind the plan cites -- every `workflow-subagent`
                # row lands here (no PreToolUse:Task claim was ever taken
                # for a Workflow leg, so it can never match the claims-based
                # recovery above either). Only reached when the cheap,
                # I/O-free claims lookup above came up empty -- the
                # transcript read is strictly the last resort.
                if recovered_model is None:
                    recovered_model, model_source = _resolve_model_and_source(
                        None, row.get("agent_transcript_path")
                    )
                line: dict = {
                    "ts": row.get("stop_ts"),
                    "session": None,
                    "agent_type": row.get("agent_type"),
                    "model": recovered_model,
                    "tool_use_id": None,
                    "agent_id": row.get("agent_id"),
                    "duration_ms": None,
                    "tokens": tokens,
                    "tokens_total": tokens_total,
                    "tokens_error": tokens_error,
                    "late": False,
                    "unreleased": True,
                    "reaped": "stopped-unjoined",
                    "join_state": "no-claim",
                }
                if model_source is not None:
                    line["model_source"] = model_source
                _append_jsonl(spend_path(budget_dir), line)
                reaped += 1
            for row in stale_completed_kind:
                # B1: the "gate -> completed -> stop" ordering's SubagentStop
                # never arrived within the TTL window -- see the docstring's
                # "launched" bullet above for why this reuses that label.
                claim = row.get("claim")
                _append_jsonl(
                    spend_path(budget_dir),
                    {
                        "ts": claim.get("ts") if claim else row.get("completed_ts"),
                        "session": claim.get("session") if claim else None,
                        "agent_type": claim.get("agent_type") if claim else None,
                        "model": row.get("model")
                        or (claim.get("model_requested") if claim else None),
                        "tool_use_id": row.get("tool_use_id"),
                        "agent_id": row.get("agent_id"),
                        "duration_ms": row.get("duration_ms"),
                        "tokens": None,
                        "tokens_total": None,
                        "tokens_error": NO_TRANSCRIPT_RECORDED_ERROR,
                        "late": claim is None,
                        "unreleased": True,
                        "reaped": "launched",
                        "join_state": "claim-consumed" if claim is not None else "no-claim",
                    },
                )
                reaped += 1
            # R7: prune the tables only now that every reaped row's spend
            # line has actually landed.
            if stale_claims:
                _write_table(claims_path(budget_dir), fresh_claims)
            if stale_stop_kind or stale_completed_kind:
                _write_table(stops_path(budget_dir), fresh_stops)
            return reaped
    except Exception:
        return 0


# N20 (08-25 round 4): --since must at least LOOK like an ISO date
# (YYYY-MM-DD, optionally followed by a fuller ISO timestamp suffix) --
# matched as a PREFIX so a full `YYYY-MM-DDTHH:MM:SSZ` value (what spend.jsonl
# rows themselves carry) is also accepted, not just a bare date.
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def parse_spend_args(args: list[str]) -> tuple[str, str | None, str | None]:
    """Pure: parse the `spend` subcommand's `--by <agent|model|day>` /
    `--since <date>` args. Returns (by, since, error) — `error` is a
    human-readable message when `--since` fails to look like an ISO date,
    None otherwise. Shared by `decide()` (which validates eagerly and turns
    a bad value into a usage-error decision, exit 2) and `_emit_spend_table`
    (the actual filter), so the two can never drift apart.
    """
    by = "agent"
    since: str | None = None
    i = 0
    while i < len(args):
        if args[i] == "--by" and i + 1 < len(args):
            by = args[i + 1]
            i += 2
            continue
        if args[i] == "--since" and i + 1 < len(args):
            since = args[i + 1]
            i += 2
            continue
        i += 1
    if since is not None and not _SINCE_RE.match(since):
        return by, since, f"agent_budget: --since must look like YYYY-MM-DD, got {since!r}"
    return by, since, None


def _emit_spend_table(args: list[str], budget_dir: str, out) -> None:
    """Print a minimal spend-by-{agent|model|day} table read from
    spend.jsonl (the `spend` subcommand's own output — reap_stale is run by
    the caller BEFORE this, so a stale claim/stop shows up here too).

    This is a quick human-facing glance, deliberately small: the rigorous,
    dedup-aware, malformed-field-tracking analysis is churn_report.py
    (churn_phase0_measure.md step 5), which reads this same spend.jsonl and
    is the canonical report — this function does not attempt to duplicate
    its SPEND DEDUP RULE.
    """
    by, since, _error = parse_spend_args(args)  # already validated by decide()
    rows = _read_table(spend_path(budget_dir))
    if since:
        rows = [r for r in rows if isinstance(r.get("ts"), str) and r["ts"] >= since]
    key_fns = {
        "agent": lambda r: r.get("agent_type") or "unknown",
        "model": lambda r: r.get("model") or "unknown",
        "day": lambda r: (r.get("ts") or "unknown")[:10],
    }
    key_fn = key_fns.get(by, key_fns["agent"])
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        key = key_fn(row)
        bucket = buckets.setdefault(key, {"dispatches": 0, "tokens_total": 0})
        bucket["dispatches"] += 1
        tt = row.get("tokens_total")
        if isinstance(tt, int) and not isinstance(tt, bool):
            bucket["tokens_total"] += tt
    print(f"agent_budget spend --by {by}" + (f" --since {since}" if since else ""), file=out)
    if not buckets:
        print("  (no spend recorded)", file=out)
        return
    for key in sorted(buckets):
        b = buckets[key]
        line = f"  {key:30s} dispatches={b['dispatches']:5d} tokens_total={b['tokens_total']}"
        print(line, file=out)


def _append_jsonl(path: str, record: dict, *, mode: int = 0o644) -> None:
    """Append one JSON line to `path`, mkdir -p'ing its parent first.

    Uses a raw O_APPEND file descriptor, looping `os.write` until the full
    encoded line is written (N11, 08-25 round 3, fixing an over-claim in the
    prior docstring here): a single `os.write()` call is permitted by POSIX
    to return a SHORT count — fewer bytes than requested, e.g. past a
    resource limit, on a full disk, or interrupted by a signal — so "one
    os.write() call" was never actually a guarantee the whole record lands;
    looping until every byte is written is. What O_APPEND actually
    guarantees for a REGULAR file is the ATOMIC OFFSET update: the kernel
    sets a write's start position to the current end-of-file as one
    indivisible step with the write itself, so two processes appending
    concurrently (this can be written from multiple hook invocations across
    parallel sub-agents) can never have their writes land at the same offset
    and stomp on each other the way two buffered text-mode calls (the
    previous `open(path, "a")` + `.write(line + "\\n")`) could. `PIPE_BUF`'s
    atomicity guarantee, by contrast, is specific to pipes/FIFOs — an
    unrelated guarantee about a different kind of file descriptor, not one
    that applies to a regular file opened with O_APPEND, and the prior
    version of this docstring conflated the two. Best-effort: any error
    (unwritable dir, unencodable field, out of disk, a write that never
    drains) is swallowed — an advisory ledger must never raise out of a
    hook. `mode` defaults to 0o644; a caller writing anything secret-
    adjacent would pass a tighter 0o600 (no current caller does — every
    spend.jsonl line here is derived from already-scoped hook fields, never
    a raw request/response body).
    """
    try:
        _ensure_dir(os.path.dirname(path))
        line = (json.dumps(record, default=str) + "\n").encode("utf-8")
    except Exception:
        return
    fd = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, mode)
        view = memoryview(line)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
    except Exception:
        return
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Launch-token bucket + admission lock — the concurrency-safe pacer state.
#
# EVERY path here fails OPEN: a missing/garbage bucket reads as "full" (admit),
# and the lock is bounded + non-blocking so a wedged holder (or missing fcntl)
# can never freeze a Task spawn — it just degrades to unsynchronized admission.
# ---------------------------------------------------------------------------


def _bucket_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, BUCKET_NAME)


def _lock_path(budget_dir: str) -> str:
    return os.path.join(budget_dir, LOCK_NAME)


def read_bucket(budget_dir: str) -> dict | None:
    """Read launch-bucket state {tokens, last_refill}, or None on any problem.

    Fail OPEN: missing file, garbage JSON, non-dict, wrong/negative fields all
    return None — and the caller MUST treat None as "bucket full" (admit), never
    as "no tokens". Never raises.
    """
    try:
        with open(_bucket_path(budget_dir), encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        tokens = float(data["tokens"])
        last_refill = float(data["last_refill"])
    except Exception:
        return None
    import math

    if not (math.isfinite(tokens) and math.isfinite(last_refill)):
        return None
    if tokens < 0 or last_refill < 0:
        return None
    return {"tokens": tokens, "last_refill": last_refill}


def write_bucket(budget_dir: str, tokens: float, last_refill: float) -> None:
    """Atomically persist bucket state (temp file in the SAME dir + os.replace).

    The temp file lives inside budget_dir so the rename is same-filesystem (atomic).
    Best-effort; never raises; cleans up the temp file on failure.
    """
    _ensure_dir(budget_dir)
    path = _bucket_path(budget_dir)
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"tokens": tokens, "last_refill": last_refill}, fh)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _current_bucket_tokens(budget_dir: str, rate: float, burst: float) -> float:
    """Launch tokens available right now (bucket refilled to the current time).

    A missing/garbage bucket reads as FULL (burst) — the same fail-open rule the
    admission path uses. Read-only; never raises.
    """
    st = read_bucket(budget_dir)
    if st is None:
        return burst
    return refill(st["tokens"], rate, burst, _now_epoch() - st["last_refill"])


@contextmanager
def admission_lock(budget_dir: str, timeout_s: float = DEFAULT_LOCK_TIMEOUT, poll_s: float = 0.01):
    """Bounded, NON-BLOCKING exclusive lock over the admission critical section.

    Yields True if the lock was acquired within `timeout_s`, else False. It NEVER
    blocks indefinitely: flock is called with LOCK_EX|LOCK_NB in a bounded poll
    loop, so a wedged holder — or a platform without fcntl — makes us fail OPEN
    (yield False, caller admits) instead of hanging every session on the machine.
    Always releases + closes the fd in `finally`.
    """
    acquired = False
    fd = None
    try:
        import fcntl
        import time

        _ensure_dir(budget_dir)
        fd = os.open(_lock_path(budget_dir), os.O_CREAT | os.O_RDWR, 0o644)
        deadline = time.time() + (timeout_s if timeout_s > 0 else 0.0)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.time() >= deadline:
                    break
                time.sleep(poll_s)
    except Exception:
        acquired = False
    try:
        yield acquired
    finally:
        if fd is not None:
            try:
                if acquired:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(fd)
            except Exception:
                pass


def paced_admit(
    budget_dir: str,
    ceiling: int,
    ttl: int,
    agent_id: str,
    rate: float,
    burst: float,
    lock_timeout: float,
    max_wait: float,
    poll: float,
    *,
    wall_now=None,
    mono_now=None,
    sleep_fn=None,
    jitter_fn=None,
) -> dict:
    """Cross-session admission with launch pacing — the pacer's heart.

    Under the bounded, non-blocking admission lock it takes a consistent snapshot
    of (live leases across ALL sessions, the launch-token bucket) and admits only
    when a concurrency slot AND a launch token are both free — consuming one token
    and claiming a lease keyed on agent_id. If blocked it RELEASES the lock, sleeps
    a bounded+jittered interval (NEVER under the lock), and retries until a
    slot/token frees or `max_wait` elapses, then denies (caller -> reduce-fan-out).

    A synchronized burst therefore drains as: `burst` admitted immediately, the
    rest gated ~1 per (1/rate)s — a staggered ramp instead of one ITPM spike.

    FAIL OPEN throughout: lock unacquirable -> admit untracked; missing/garbage
    bucket -> full. Clocks/sleep are injectable for hermetic tests.

    Returns: admitted, claimed, reason ("ok"|"cap"|"rate"|"lock"), live, cap[, tokens].
    """
    wall_now = _now_epoch if wall_now is None else wall_now
    mono_now = _mono if mono_now is None else mono_now
    sleep_fn = _sleep if sleep_fn is None else sleep_fn
    jitter_fn = _jitter if jitter_fn is None else jitter_fn

    deadline = mono_now() + (max_wait if max_wait > 0 else 0.0)
    live = 0
    capacity = cap(ceiling)
    reason = "cap"
    while True:
        with admission_lock(budget_dir, timeout_s=lock_timeout) as locked:
            capacity = cap(ceiling)
            if not locked:
                return {"admitted": True, "claimed": False, "reason": "lock",
                        "live": -1, "cap": capacity}
            live = prune_and_count(budget_dir, ttl)
            wnow = wall_now()
            st = read_bucket(budget_dir)
            tokens = burst if st is None else refill(st["tokens"], rate, burst, wnow - st["last_refill"])
            ok, new_tokens, reason = plan_admission(live, capacity, tokens)
            if ok:
                write_bucket(budget_dir, new_tokens, wnow)
                write_lease(budget_dir, agent_id)
                return {"admitted": True, "claimed": True, "reason": "ok",
                        "live": live, "cap": capacity, "tokens": round(new_tokens, 3)}
            # Not admitted: persist the refilled bucket (advance refill clock) but
            # do NOT consume — tokens accrue toward `burst` while we wait.
            write_bucket(budget_dir, tokens, wnow)
            wait = wait_hint(reason, tokens, rate, poll)
        # Lock released here (context exit). Sleep OUTSIDE the lock — never under it.
        remaining = deadline - mono_now()
        if remaining <= 0:
            return {"admitted": False, "claimed": False, "reason": reason,
                    "live": live, "cap": capacity}
        sleep_fn(min(jitter_fn(wait), remaining))


# ---------------------------------------------------------------------------
# PURE decision function — maps (argv, env, budget_dir) -> a decision dict.
#
# The decision dict describes WHAT to do; main() performs the effects. This keeps
# every branch coverable without spawning a process or touching stdout.
#
# decision keys:
#   action: one of status|claim|release|reset|doctor|gate|browser_pool|usage
#   exit:   process exit code (always 0 for advisory paths; 2 for a usage error
#           on claim/release with no id, matching the bash `return 2`).
#   deny:   optional str — a canonical PreToolUse deny message to emit (gate).
#   log:    optional (event, fields) tuple to append to the decision log.
#   ... plus action-specific payload fields consumed by main().
# ---------------------------------------------------------------------------


def decide(
    argv: list[str],
    environ: dict,
    budget_dir: str,
    agent_id: str = "",
    *,
    payload: dict | None = None,
) -> dict:
    """Pure router: resolve the subcommand into a decision dict (no I/O).

    `agent_id` is the lease key (tool_use_id, possibly minted) for the
    PACER-ON gate path and the EXACT tool_use_id for release_hook; unused on
    every other path. `payload` is the raw PreToolUse:Task / PostToolUse /
    SubagentStop event — since Phase 0 step 2 it feeds the real spend-ledger
    claim recording (gate) and three-event join (release_hook), gated on
    `spend_ledger_enabled(environ)`; both are extracted directly from
    `payload` here (`_build_claim_record`/`classify_release_event`) rather
    than via separate threaded kwargs, since decide() already receives the
    full event.
    """
    sub = argv[0] if argv else "status"
    rest = argv[1:]
    ceiling = ceiling_from_env(environ)
    ttl = ttl_from_env(environ)
    claim_ttl = claim_ttl_from_env(environ)
    payload = payload if isinstance(payload, dict) else {}

    if sub == "status":
        return {"action": "status", "exit": 0, "ceiling": ceiling, "ttl": ttl}

    if sub == "claim":
        agent_id = rest[0] if rest else ""
        if not agent_id:
            return {
                "action": "claim",
                "exit": 2,
                "error": "agent_budget: claim requires <agent_id>",
            }
        return {"action": "claim", "exit": 0, "agent_id": agent_id}

    if sub == "release":
        agent_id = rest[0] if rest else ""
        if not agent_id:
            return {
                "action": "release",
                "exit": 2,
                "error": "agent_budget: release requires <agent_id>",
            }
        return {"action": "release", "exit": 0, "agent_id": agent_id}

    if sub == "reset":
        return {"action": "reset", "exit": 0, "ttl": ttl}

    if sub == "doctor":
        return {"action": "doctor", "exit": 0, "ceiling": ceiling, "ttl": ttl}

    if sub == "gate":
        # Master OFF short-circuits before any ledger work (fail open).
        if _disabled(environ):
            return {"action": "gate", "exit": 0}
        # Spend-ledger claim: built from the REAL tool_use_id only (never a
        # minted fallback — see _build_claim_record), recorded ONLY on an
        # admitted gate (a denied dispatch never ran). For the pacer-off
        # legacy path we know admission synchronously below; for the
        # pacer-on path admission is an EFFECT (paced_admit, under the
        # lock), so _apply_pacer_gate records it only if actually admitted.
        claim_record = _build_claim_record(payload) if spend_ledger_enabled(environ) else None
        lock_timeout = lock_timeout_from_env(environ)
        # WS2.2 — fan-out session-high observer. Built here (pure, from the
        # payload alone) regardless of pacer on/off, exactly like
        # claim_record above; carried in the decision dict and applied ONLY
        # on the admitted path in apply_decision/_apply_pacer_gate — a
        # denied dispatch never ran, so it must never count toward a
        # session's fan-out either (same "admitted only" rule claim_record
        # already follows, for the same reason).
        gate_session = _lib.session_id(payload)
        fanout = {
            # NO_SESSION_SENTINEL ("nosession", e.g. both CSA_PACER and
            # CSA_SPEND_LEDGER off so main() never read stdin at all, or a
            # payload that genuinely carries no session) must never be
            # treated as a real session identity here — mirrors _lib.log's
            # own "nosession" omission rule (_identity_fields) rather than
            # reimplementing it, since identity_or_none() alone does not
            # strip that sentinel (it only maps "" and non-str to None).
            "session": _lib.identity_or_none(gate_session)
            if gate_session != _lib.NO_SESSION_SENTINEL
            else None,
            "agent_type": _lib.identity_or_none(_lib.subagent_type(payload)),
            "threshold": fanout_threshold_from_env(environ),
        }
        if pacer_enabled(environ):
            # PACER ON: the admission decision is an EFFECT (count-then-claim under
            # the lock), so it runs in apply_decision. Carry the params it needs.
            return {
                "action": "gate",
                "exit": 0,
                "pacer": True,
                "agent_id": agent_id,
                "ceiling": ceiling,
                "ttl": ttl,
                "lock_timeout": lock_timeout,
                "rate": launch_rate_from_env(environ),
                "burst": launch_burst_from_env(environ),
                "max_wait": admit_max_wait_from_env(environ),
                "poll": admit_poll_from_env(environ),
                "enforce": _lib.enforcing(),
                "claim": claim_record,
                "fanout": fanout,
            }
        # PACER OFF (default): legacy read-only advisory count — behavior unchanged.
        live = prune_and_count(budget_dir, ttl)
        capacity = cap(ceiling)
        decision: dict = {
            "action": "gate",
            "exit": 0,
            "live": live,
            "cap": capacity,
            "log": ("task_gate", {"live": live, "cap": capacity}),
            "lock_timeout": lock_timeout,
        }
        # LOG-ONLY unless enforcing(). Deny only when at/over capacity.
        if _lib.enforcing() and live >= capacity:
            decision["deny"] = (
                f"agent_budget: {live} live agents >= cap {capacity}; "
                "wait for a slot or raise CSA_ANTHROPIC_CEILING."
            )
        else:
            # Admitted (not denied) — record the claim, if any, and note
            # the dispatch for the fan-out observer (WS2.2).
            decision["claim"] = claim_record
            decision["fanout"] = fanout
        return decision

    if sub == "release_hook":
        # PostToolUse (payload tool_name "Agent"; matcher "Task") / SubagentStop.
        # Master OFF short-circuits before any ledger work, same as gate.
        # Two INDEPENDENT toggles below, each inert unless its own env
        # condition holds: pacer release and the spend ledger's three-event
        # join (spend_ledger_enabled — fully decoupled from the pacer; see
        # that function's own docstring). N15 (08-25 round 3): CSA_DISABLE_
        # HOOKS=1 short-circuits BEFORE either effect below runs, so a
        # lease/claim recorded while hooks were on and the master switch is
        # then flipped off never gets released here — it leaks until its
        # own TTL self-heal reaps it, not immediately on this call.
        #
        # R9 (08-25 round 4): the pacer's own lease releases ONLY on an
        # actual finish -- PostToolUse(completed) or SubagentStop -- NEVER
        # on PostToolUse(async_launched). The prior code released
        # unconditionally on ANY release_hook firing carrying a tool_use_id,
        # which for a background dispatch meant the lease (and the
        # concurrency slot it represents) freed the instant the Task
        # async-launched, not when the subagent actually finished minutes
        # later -- defeating the whole point of the concurrency cap for
        # every background dispatch (the spike's own bug; see
        # agent_pacer.md). `classify_release_event` is the single source of
        # truth for which kind this firing actually is.
        # R11 (08-25 round 5): the pacer's OWN identity resolution (lease
        # files, never claims.jsonl -- see `_release_pacer_lease_for_stop`/
        # `_annotate_pacer_lease_and_maybe_release`) is entirely independent
        # of `ledger_on` below -- unlike R9's version, which silently relied
        # on claims.jsonl and leaked every background lease whenever
        # CSA_SPEND_LEDGER=0. `pacer_annotate_async_launched` is the missing
        # third case R9 never set a decision field for at all: async_
        # launched must still ANNOTATE the lease (or release it immediately,
        # for the C -> S -> A ordering) even though it never releases via
        # `pacer_release_tool_use_id`.
        if _disabled(environ):
            return {"action": "release_hook", "exit": 0}
        decision: dict = {"action": "release_hook", "exit": 0}
        pacer_on = pacer_enabled(environ)
        ledger_on = spend_ledger_enabled(environ)
        event = classify_release_event(payload) if (pacer_on or ledger_on) else None
        if pacer_on:
            # R11: lock_timeout for the pacer's OWN release/annotate paths,
            # independent of whether `ledger_on` ever populates its own
            # separate `spend_ledger.lock_timeout` below.
            decision["lock_timeout"] = lock_timeout_from_env(environ)
            if event is not None:
                kind = event.get("kind")
                if kind == "post_tool_use_completed":
                    tuid = event.get("tool_use_id") or agent_id
                    if tuid:
                        decision["pacer_release_tool_use_id"] = tuid
                elif kind == "subagent_stop":
                    stop_agent_id = event.get("agent_id")
                    if stop_agent_id:
                        decision["pacer_release_stop_agent_id"] = stop_agent_id
                        # N2: unreachable via decide() given classify_
                        # release_event's fixed output shape (see
                        # _release_pacer_lease_for_stop's own docstring) --
                        # kept only so a future/direct caller with a real
                        # tool_use_id still takes the direct-release path.
                        stop_tuid = event.get("tool_use_id")
                        if isinstance(stop_tuid, str) and stop_tuid:
                            decision["pacer_release_stop_tool_use_id"] = stop_tuid
                elif kind == "post_tool_use_async_launched":
                    tuid = event.get("tool_use_id")
                    aid = event.get("agent_id")
                    if tuid and aid:
                        decision["pacer_annotate_async_launched"] = {
                            "tool_use_id": tuid,
                            "agent_id": aid,
                        }
        if ledger_on:
            decision["spend_ledger"] = {
                "event": event,
                "lock_timeout": lock_timeout_from_env(environ),
                "ttl": claim_ttl,
            }
        return decision

    if sub == "spend":
        # Manual CLI glance at spend.jsonl — never gated on CSA_DISABLE_HOOKS
        # (matches status/doctor/reset: those are operator-invoked reads,
        # not hook-fired effects, so the master hook switch doesn't apply).
        # N20 (08-25 round 4): validate --since eagerly, mirroring claim/
        # release's own usage-error (exit 2) pattern -- a malformed value
        # used to silently string-compare against every row's ISO ts (since
        # almost any garbage lexicographically sorts above a leading digit)
        # and filter out EVERYTHING with no visible error, indistinguishable
        # from "you really have no spend."
        _by, _since, since_error = parse_spend_args(rest)
        if since_error:
            return {"action": "spend", "exit": 2, "error": since_error}
        return {
            "action": "spend",
            "exit": 0,
            "ttl": claim_ttl,
            "lock_timeout": lock_timeout_from_env(environ),
            "args": rest,
            # D11: the reap pass is part of the spend ledger, gated on the
            # SAME toggle as gate's claim recording / release_hook's join —
            # three doc sites already documented this; the code never
            # actually enforced it until now.
            "reap": spend_ledger_enabled(environ),
        }

    if sub == "browser_pool":
        if _disabled(environ):
            return {"action": "browser_pool", "exit": 0}
        return {
            "action": "browser_pool",
            "exit": 0,
            "pool_args": rest,
            "log": ("browser_pool", {"live": 0, "cap": 0}),
        }

    # Unknown subcommand: fail OPEN (advisory ledger must never block).
    return {
        "action": "usage",
        "exit": 0,
        "error": (
            "usage: agent_budget {status|claim <id>|release <id>|reset|doctor|"
            "gate|release_hook|spend|browser_pool}"
        ),
    }


def _disabled(environ: dict) -> bool:
    """CSA_DISABLE_HOOKS=1 master-off, read from the provided env mapping."""
    return environ.get("CSA_DISABLE_HOOKS", "") == "1"


# ---------------------------------------------------------------------------
# Thin main — reads argv/env, applies the decision's effects, always exits 0
# for advisory paths (deny is JSON, never an exit code).
# ---------------------------------------------------------------------------


def _run_browser_pool(pool_args: list[str]) -> None:
    """Best-effort delegate to the vendored browser pool if present.

    Mirrors the bash: run `python3 browser_pool.py <args>` for a status read,
    discarding output; any failure is swallowed. Never raises.
    """
    pool = os.path.join(_lib.CLAUDE_DIR, "live-testing", "browser_pool.py")
    if not os.path.isfile(pool):
        return
    try:
        import subprocess

        subprocess.run(
            [sys.executable, pool, *pool_args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return


def apply_decision(decision: dict, budget_dir: str, out, err) -> int:
    """Perform the effects for a decision dict; return the exit code.

    Split from main() so tests can drive effects with in-memory streams and a
    sandboxed budget_dir, without a subprocess.
    """
    action = decision.get("action")

    # Emit the structured decision log first (gate/browser_pool carry a `log`).
    log_spec = decision.get("log")
    if log_spec is not None:
        event, fields = log_spec
        _lib.log("agent_budget", event, **fields)

    if action == "status":
        payload = status_payload(budget_dir, decision["ceiling"], decision["ttl"])
        import json

        print(json.dumps(payload, indent=2), file=out)
        return 0

    if action == "claim":
        if decision["exit"] == 2:
            print(decision["error"], file=err)
            return 2
        write_lease(budget_dir, decision["agent_id"])
        print(f"OK claimed {decision['agent_id']}", file=out)
        return 0

    if action == "release":
        if decision["exit"] == 2:
            print(decision["error"], file=err)
            return 2
        _remove(lease_path(budget_dir, decision["agent_id"]))
        print(f"OK released {decision['agent_id']}", file=out)
        return 0

    if action == "reset":
        removed = reset_ledger(budget_dir, decision["ttl"])
        print(f"OK reset (removed {removed} stale/corrupt lease(s))", file=out)
        return 0

    if action == "doctor":
        _emit_doctor(decision, budget_dir, out)
        return 0

    if action == "gate":
        if decision.get("pacer"):
            return _apply_pacer_gate(decision, budget_dir)
        deny = decision.get("deny")
        if deny is not None:
            _lib.emit_pretooluse_deny(deny)
        else:
            claim = decision.get("claim")
            if claim is not None:
                record_claim(budget_dir, claim, decision.get("lock_timeout", DEFAULT_LOCK_TIMEOUT))
            # WS2.2 — admitted only (never on a denied gate, mirroring the
            # claim-recording rule immediately above).
            fanout = decision.get("fanout")
            if fanout is not None:
                note_fanout_dispatch(
                    budget_dir,
                    fanout.get("session"),
                    fanout.get("agent_type"),
                    fanout.get("threshold", DEFAULT_FANOUT_THRESHOLD),
                    min(decision.get("lock_timeout", DEFAULT_LOCK_TIMEOUT), FANOUT_LOCK_TIMEOUT),
                )
        return 0

    if action == "release_hook":
        # R9: a "completed" event carries its own tool_use_id directly.
        tuid = decision.get("pacer_release_tool_use_id")
        if tuid:
            _remove(lease_path(budget_dir, tuid))
        # R11 (08-25 round 5): the pacer's OWN lock_timeout, decoupled from
        # the spend ledger's own (possibly absent, when CSA_SPEND_LEDGER=0)
        # `spend_ledger.lock_timeout` below -- see decide()'s own R11 note.
        lock_timeout = decision.get("lock_timeout", DEFAULT_LOCK_TIMEOUT)
        # R11: async_launched must still ANNOTATE the pacer's lease (or
        # release it immediately, for the C -> S -> A ordering) even though
        # it never itself sets `pacer_release_tool_use_id` (R9's own rule:
        # the lease only ever releases on a REAL finish). Runs BEFORE the
        # SubagentStop handling below so the two effects can never race each
        # other within one call.
        annotate = decision.get("pacer_annotate_async_launched")
        if annotate:
            _annotate_pacer_lease_and_maybe_release(
                budget_dir, lock_timeout, annotate["tool_use_id"], annotate["agent_id"]
            )
        # R9/R11: a "subagent_stop" event never carries tool_use_id -- it is
        # resolved from the pacer's OWN lease files (R11, never
        # claims.jsonl). Still run before the spend-ledger's own SubagentStop
        # handling below pops (consumes) its claim, for ordering hygiene --
        # though R11 no longer actually depends on that claim surviving.
        stop_agent_id = decision.get("pacer_release_stop_agent_id")
        if stop_agent_id:
            _release_pacer_lease_for_stop(
                budget_dir,
                lock_timeout,
                stop_agent_id,
                tool_use_id=decision.get("pacer_release_stop_tool_use_id"),
            )
        spend = decision.get("spend_ledger")
        if spend is not None:
            reap_stale(budget_dir, spend["ttl"], spend["lock_timeout"])
            event = spend.get("event")
            if event is not None:
                _apply_spend_event(event, budget_dir, spend["lock_timeout"])
        return 0

    if action == "spend":
        if decision.get("exit") == 2:
            print(decision["error"], file=err)
            return 2
        if decision.get("reap", True):  # D11: gated on CSA_SPEND_LEDGER
            reap_stale(budget_dir, decision["ttl"], decision["lock_timeout"])
        _emit_spend_table(decision.get("args", []), budget_dir, out)
        return 0

    if action == "browser_pool":
        _run_browser_pool(decision.get("pool_args", []))
        return 0

    # usage / unknown: advisory fail-open.
    print(decision.get("error", ""), file=err)
    return 0


def _emit_doctor(decision: dict, budget_dir: str, out) -> None:
    ceiling = decision["ceiling"]
    ttl = decision["ttl"]
    c = cores()
    live = prune_and_count(budget_dir, ttl)
    rec = recommend(ceiling, live)
    writable = "yes" if _dir_writable(budget_dir) else "no"
    rate = launch_rate_from_env()
    burst = launch_burst_from_env()
    tokens = round(_current_bucket_tokens(budget_dir, rate, burst), 3)
    lines = [
        "agent_budget doctor",
        f"  budget_dir      : {budget_dir} (writable={writable})",
        f"  cpu_cores       : {c}",
        f"  load_1min       : {load1()}",
        f"  pacer_enabled   : {pacer_enabled()}",
        f"  ceiling         : {ceiling} (CSA_ANTHROPIC_CEILING)",
        f"  lease_ttl_sec   : {ttl} (CSA_LEASE_TTL_SEC)",
        f"  live_leases     : {live}",
        f"  recommend_slots : {rec}",
        f"  launch_rate     : {rate}/s (CSA_LAUNCH_RATE)",
        f"  launch_burst    : {burst} (CSA_LAUNCH_BURST)",
        f"  launch_tokens   : {tokens}",
        f"  lock_timeout    : {lock_timeout_from_env()}s (CSA_LOCK_TIMEOUT_SEC)",
        "  fail_mode       : OPEN (advisory ledger; corrupt state self-heals)",
    ]
    print("\n".join(lines), file=out)


def _dir_writable(path: str) -> bool:
    try:
        return os.path.isdir(path) and os.access(path, os.W_OK)
    except Exception:  # pragma: no cover
        return False


def _apply_pacer_gate(decision: dict, budget_dir: str) -> int:
    """Effect for the PACER-ON gate: staggered admit + claim; deny on saturation.

    Always returns exit 0 — a deny is JSON, never an exit code. Fails open on the
    lock (see paced_admit). The spend-ledger claim (if any — see decide()'s
    gate branch) is recorded whenever the dispatch actually RUNS: either
    `result["admitted"]` is True, OR admission was refused but enforcement is
    off, in which case the caller still lets the dispatch through (LOG-ONLY
    at-cap, matching the pacer-off gate's own "log but never deny" behavior
    below) — a denied-but-still-running dispatch that skipped this would
    otherwise complete with no matching claim, showing up later as a
    permanently `late`/orphaned spend line (R10, 08-25 round 4: the prior
    `if result["admitted"]:` guard alone missed exactly this case). Only a
    TRUE deny (enforcing AND not admitted) skips the claim, since that
    dispatch genuinely never runs.
    """
    result = paced_admit(
        budget_dir,
        decision["ceiling"],
        decision["ttl"],
        decision["agent_id"],
        decision["rate"],
        decision["burst"],
        decision["lock_timeout"],
        decision["max_wait"],
        decision["poll"],
    )
    _lib.log(
        "agent_budget",
        "task_gate",
        live=result["live"],
        cap=result["cap"],
        admitted=result["admitted"],
        claimed=result["claimed"],
        reason=result.get("reason"),
        pacer=True,
    )
    dispatch_proceeds = result["admitted"] or not decision.get("enforce")
    if dispatch_proceeds:
        claim = decision.get("claim")
        if claim is not None:
            record_claim(budget_dir, claim, decision.get("lock_timeout", DEFAULT_LOCK_TIMEOUT))
        # WS2.2 — same "dispatch actually runs" gate as the claim recording
        # immediately above (never on a true deny — that dispatch never ran).
        fanout = decision.get("fanout")
        if fanout is not None:
            note_fanout_dispatch(
                budget_dir,
                fanout.get("session"),
                fanout.get("agent_type"),
                fanout.get("threshold", DEFAULT_FANOUT_THRESHOLD),
                min(decision.get("lock_timeout", DEFAULT_LOCK_TIMEOUT), FANOUT_LOCK_TIMEOUT),
            )
    if decision.get("enforce") and not result["admitted"]:
        _lib.emit_pretooluse_deny(_pacing_deny_message(result))
    return 0


def _pacing_deny_message(result: dict) -> str:
    """A denial message tuned to WHY admission was refused (finding 9)."""
    if result.get("reason") == "rate":
        return (
            "agent_budget: launch-rate limited — this fan-out is arriving faster "
            "than the pacer allows. Spawn fewer agents at once (narrower fan-out) "
            "or wait a moment before retrying; the limit is the per-minute token "
            "rate, not total budget."
        )
    return (
        f"agent_budget: {result.get('live')} live agents at the concurrency cap "
        f"{result.get('cap')} after waiting for a slot. Reduce fan-out width, or "
        "raise CSA_ANTHROPIC_CEILING if your rate limits allow more concurrency."
    )


def _gate_agent_id(ev: dict) -> str:
    """Lease key for a Task spawn: its tool_use_id, or a minted unique id.

    tool_use_id is unique per invocation and correlates claim<->release. When it's
    absent we mint a unique id so two concurrent same-type agents never collide on
    one lease (correctness), accepting that such a lease is only TTL-reaped (no
    correlated release).
    """
    tid = _lib.tool_use_id(ev)
    if tid:
        return tid
    import uuid

    return "auto-" + uuid.uuid4().hex


def main(argv: list[str] | None = None) -> int:
    """Entry point. Route argv -> decision -> effects; always fail open."""
    if argv is None:
        argv = sys.argv[1:]
    try:
        environ = dict(os.environ)
        agent_id = ""
        payload: dict = {}
        sub0 = argv[0] if argv else ""
        # Read stdin on EITHER the pacer's opt-in OR the (default-ON) spend
        # ledger's toggle, so the pacer's own lease/admission behavior stays
        # gated on pacer_enabled ALONE — decoupling the READ must never turn
        # the pacer on (see pacer_enabled/spend_ledger_enabled's docstrings
        # and churn_phase0_measure.md step 1). Master OFF skips the read
        # entirely, same "before any ledger work" short-circuit decide()'s
        # gate/release_hook branches already apply.
        read_stdin = not _disabled(environ) and (
            pacer_enabled(environ) or spend_ledger_enabled(environ)
        )
        # Gate mints a fallback id when tool_use_id is absent (so the PACER's
        # own lease always has SOME key); release uses the EXACT tool_use_id
        # — a minted id was never releasable, it only ever TTL-reaps. The
        # spend-ledger claim, by contrast, is built by decide() itself
        # straight from `payload` (_build_claim_record reads tool_use_id/
        # tool_input/session_id directly) — a minted `agent_id` here is
        # never used for that; see _build_claim_record's own docstring for
        # why a minted id is deliberately never worth a claim.
        if sub0 == "gate" and read_stdin:
            payload = _lib.read_event()
            agent_id = _gate_agent_id(payload)
        elif sub0 == "release_hook" and read_stdin:
            payload = _lib.read_event()
            agent_id = _lib.tool_use_id(payload)
        decision = decide(argv, environ, _lib.AGENT_BUDGET_DIR, agent_id, payload=payload)
        return apply_decision(decision, _lib.AGENT_BUDGET_DIR, sys.stdout, sys.stderr)
    except Exception:
        # Absolute last resort: an advisory ledger must never crash a tool call.
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
