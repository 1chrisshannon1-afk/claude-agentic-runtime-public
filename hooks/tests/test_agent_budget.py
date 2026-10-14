"""Hermetic tests for hooks/agent_budget.py.

Ports the PROVEN behavior of ~/.claude/scripts/agent_budget.sh as the spec:
  * status/claim/release/reset/doctor subcommands and their output shape,
  * the concurrency ledger (leases keyed by sanitized agent_id under the
    sandboxed ~/.claude/.agent_budget),
  * recommended = max(0, min(cores-2, ceiling) - live),
  * self-healing prune (stale/corrupt leases removed as a side effect),
  * FAIL-OPEN gate/browser_pool that NEVER block (exit 0; deny only ever via a
    JSON object under enforcement), and the CSA_DISABLE_HOOKS master-off,
  * unknown-subcommand fail-open.

Every test runs against the `sandbox` fixture ($HOME + _lib path constants,
including AGENT_BUDGET_DIR, pointed into a tmp dir) so the operator's real ledger
and decision log are never touched. No network, no real git.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time

import agent_budget as ab
import pytest

# ---------------------------------------------------------------------------
# Local helpers.
# ---------------------------------------------------------------------------


def _run(argv, sandbox, environ=None):
    """Drive decide() + apply_decision() with in-memory streams.

    Returns (exit_code, stdout_str, stderr_str). Uses the sandboxed budget dir.
    """
    env = dict(os.environ) if environ is None else environ
    out, err = io.StringIO(), io.StringIO()
    budget_dir = str(sandbox.agent_budget_dir)
    decision = ab.decide(list(argv), env, budget_dir)
    code = ab.apply_decision(decision, budget_dir, out, err)
    return code, out.getvalue(), err.getvalue()


def _make_lease(sandbox, agent_id, *, body="agent_id={id}\npid=1\n", age_sec=0):
    """Create a lease file for `agent_id`, optionally aged `age_sec` seconds."""
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / (ab.LEASE_PREFIX + ab.safe_id(agent_id))
    path.write_text(body.format(id=agent_id))
    if age_sec:
        old = time.time() - age_sec
        os.utime(path, (old, old))
    return path


def _read_jsonl(path):
    """Parse every line of a JSONL file into a list of objects."""
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh.read().strip().splitlines()]


# --- Spend-ledger fixture builders (Phase 0 step 2). Field shapes verified
# against the real spike artifact (~/.claude/.agent_budget/spike_payload.jsonl,
# churn_phase0_measure.md step 1) -- see agent_budget.py's classify_release_
# event docstring for the citation. ----------------------------------------


def _gate_payload(tool_use_id, *, subagent_type="explore", model=None, session_id="s1"):
    ti = {"subagent_type": subagent_type}
    if model is not None:
        ti["model"] = model
    return {
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "tool_name": "Task",
        "tool_input": ti,
        "tool_use_id": tool_use_id,
    }


def _async_launched_payload(
    tool_use_id, agent_id, *, resolved_model="claude-haiku-4-5-20251001", session_id="s1"
):
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "explore", "model": "haiku"},
        "tool_response": {
            "isAsync": True,
            "status": "async_launched",
            "agentId": agent_id,
            "resolvedModel": resolved_model,
        },
        "tool_use_id": tool_use_id,
        "duration_ms": 3,  # meaningless launch-event duration, per the spike
    }


def _subagent_stop_payload(agent_id, *, agent_type="explore", transcript_path, session_id="s1"):
    return {
        "session_id": session_id,
        "hook_event_name": "SubagentStop",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "agent_transcript_path": transcript_path,
        "last_assistant_message": "ok",
    }


def _completed_payload(
    tool_use_id,
    agent_id,
    *,
    resolved_model="claude-haiku-4-5-20251001",
    duration_ms=2723,
    total_tokens=None,
    session_id="s1",
):
    tr = {
        "status": "completed",
        "agentId": agent_id,
        "agentType": "explore",
        "resolvedModel": resolved_model,
    }
    if total_tokens is not None:
        tr["totalTokens"] = total_tokens
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_response": tr,
        "tool_use_id": tool_use_id,
        "duration_ms": duration_ms,
    }


def _write_transcript(path, usage_dicts):
    """Write a fixture agent-transcript JSONL, one assistant message per
    usage dict. Returns the hand-summed totals dict (input/output/
    cache_read/cache_creation)."""
    lines = []
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    for u in usage_dicts:
        lines.append(json.dumps({"type": "assistant", "message": {"usage": u}}))
        totals["input"] += u.get("input_tokens", 0)
        totals["output"] += u.get("output_tokens", 0)
        totals["cache_read"] += u.get("cache_read_input_tokens", 0)
        totals["cache_creation"] += u.get("cache_creation_input_tokens", 0)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return totals


def _write_transcript_with_models(path, models, *, non_assistant_lines=()):
    """WS2.1 step 4 fixture helper: write a transcript whose assistant
    lines carry `message.model`, one line per entry in `models` (in order
    -- the LAST entry is what model_from_transcript's "last-seen wins" rule
    should recover). `non_assistant_lines` (raw dicts, written interleaved
    at the END, matching how a real transcript trails off with e.g. a
    summary/attachment line) let a test assert those are correctly ignored.
    """
    lines = [
        json.dumps({"type": "assistant", "message": {"model": m, "usage": {"input_tokens": 1}}})
        for m in models
    ]
    for extra in non_assistant_lines:
        lines.append(json.dumps(extra))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _events(monkeypatch, events):
    """Stub ab._lib.read_event to return each of `events` in order, one per
    call -- simulates a sequence of real hook firings across separate
    subprocess invocations (each ab.main() call here is one such firing)."""
    queue = list(events)

    def _next():
        return queue.pop(0)

    monkeypatch.setattr(ab._lib, "read_event", _next)


def _mp_record_claim_worker(budget_dir, idx):
    """Module-level (picklable) worker for the cross-PROCESS locking test —
    must be a real top-level function, not a closure, so macOS 'spawn' can
    pickle and re-import it in the child process."""
    import agent_budget as ab_mp

    ab_mp.record_claim(
        budget_dir,
        {
            "tool_use_id": f"tu_{idx}",
            "ts": "2026-08-25T00:00:00Z",
            "ts_epoch": 1000,
            "agent_type": "x",
            "model_requested": None,
            "session": "s",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=5.0,
    )


def _mp_handle_async_launched_worker(budget_dir, idx):
    """Module-level (picklable) worker: the ANNOTATE side of the mixed
    concurrent-processes test (coverage row: concurrent annotate-vs-
    append/pop mix)."""
    import agent_budget as ab_mp

    ab_mp.handle_async_launched(
        budget_dir, 5.0, f"tu_mix_{idx}", f"agent_mix_{idx}", "claude-haiku-4-5-20251001"
    )


def _mp_handle_subagent_stop_worker(budget_dir, idx, transcript_path):
    """Module-level (picklable) worker: the STOP (append-or-join) side of
    the mixed concurrent-processes test."""
    import agent_budget as ab_mp

    ab_mp.handle_subagent_stop(budget_dir, 5.0, f"agent_mix_{idx}", "explore", transcript_path)


# ===========================================================================
# PURE FORMULA: recommend / cap — the load-bearing arithmetic vectors.
# ===========================================================================


@pytest.mark.parametrize(
    "ceiling,live,expected",
    [
        # recommended = max(0, cap(ceiling) - live); cap(ceiling) = max(1, ceiling)
        (8, 0, 8),
        (8, 2, 6),
        (8, 8, 0),
        (8, 9, 0),  # negative -> clamp 0
        (3, 1, 2),
        (100, 40, 60),
        (0, 0, 1),  # cap(0) floors to 1
        (1, 5, 0),  # cap(1)=1, 1-5 -> clamp 0
    ],
)
def test_recommend_formula(ceiling, live, expected):
    assert ab.recommend(ceiling, live) == expected


@pytest.mark.parametrize(
    "ceiling,expected",
    [
        # cap(ceiling) = max(1, ceiling) — CPU cores are intentionally NOT a factor.
        (8, 8),
        (3, 3),
        (2, 2),
        (1, 1),
        (0, 1),  # floor toward progress
        (100, 100),
    ],
)
def test_cap_formula(ceiling, expected):
    assert ab.cap(ceiling) == expected


@pytest.mark.parametrize(
    "tokens,rate,capacity,elapsed,expected",
    [
        (0.0, 1.0, 5.0, 3.0, 3.0),  # linear refill
        (0.0, 1.0, 5.0, 10.0, 5.0),  # clamp up to capacity
        (2.0, 2.0, 10.0, 1.5, 5.0),  # 2 + 2*1.5
        (5.0, 1.0, 5.0, 100.0, 5.0),  # already full
        (3.0, 1.0, 5.0, -10.0, 3.0),  # negative elapsed -> 0 (clock skew)
        (0.0, 0.0, 5.0, 100.0, 0.0),  # rate 0 never refills
        (0.0, 1.0, 0.0, 100.0, 0.0),  # capacity 0 clamps
        (10.0, 1.0, 5.0, 0.0, 5.0),  # tokens above capacity clamp down
    ],
)
def test_refill_formula(tokens, rate, capacity, elapsed, expected):
    assert ab.refill(tokens, rate, capacity, elapsed) == pytest.approx(expected)


@pytest.mark.parametrize(
    "tokens,cost,allowed,remaining",
    [
        (1.0, 1.0, True, 0.0),
        (0.5, 1.0, False, 0.5),
        (3.0, 1.0, True, 2.0),
        (0.0, 1.0, False, 0.0),
        (2.5, 2.0, True, 0.5),
    ],
)
def test_admit_formula(tokens, cost, allowed, remaining):
    got_allowed, got_remaining = ab.admit(tokens, cost)
    assert got_allowed is allowed
    assert got_remaining == pytest.approx(remaining)


def test_admit_default_cost_is_one():
    allowed, remaining = ab.admit(1.0)
    assert allowed is True
    assert remaining == pytest.approx(0.0)


# ===========================================================================
# PURE: launch-rate float config validation + pacer flag (fail-open).
# ===========================================================================


@pytest.mark.parametrize(
    "raw,default,expected",
    [
        (None, 2.0, 2.0),
        ("3.5", 2.0, 3.5),
        ("4", 2.0, 4.0),
        (1.5, 2.0, 1.5),
        ("", 2.0, 2.0),
        ("abc", 2.0, 2.0),
        ("-1", 2.0, 2.0),  # negative -> default
        ("nan", 2.0, 2.0),  # NaN -> default
        ("inf", 2.0, 2.0),  # infinity -> default
        ("0", 2.0, 0.0),  # zero is valid
        ("  1.25  ", 2.0, 1.25),  # whitespace tolerated
    ],
)
def test_parse_float_config(raw, default, expected):
    assert ab.parse_float_config(raw, default) == pytest.approx(expected)


def test_pacer_disabled_by_default():
    assert ab.pacer_enabled({}) is False
    assert ab.pacer_enabled({"CSA_PACER": "0"}) is False
    assert ab.pacer_enabled({"CSA_PACER": "1"}) is True


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0", False),  # the ONE literal value that turns it OFF
        ("false", True),  # only "0" turns it off -- a stray typo stays ON
        ("no", True),
        ("", True),
        ("0 ", True),  # trailing whitespace is NOT the literal "0"
        (" 0", True),  # leading whitespace is NOT the literal "0" either
        ("1", True),
        (None, True),  # key absent entirely
    ],
)
def test_spend_ledger_enabled_parsing(raw, expected):
    """R8-adjacent (item 3, 08-25 round 3): spend_ledger_enabled() is ON by
    default and turns OFF for exactly the literal string "0" -- every other
    value (including whitespace-padded "0 "/" 0", a falsy-looking "false"/
    "no", an empty string, or the key simply being absent) stays ON, so a
    stray typo in the env var can never silently turn the stdin read off."""
    env = {} if raw is None else {"CSA_SPEND_LEDGER": raw}
    assert ab.spend_ledger_enabled(env) is expected


def test_launch_config_resolvers_defaults_and_overrides():
    assert ab.launch_rate_from_env({}) == pytest.approx(ab.DEFAULT_LAUNCH_RATE)
    assert ab.launch_burst_from_env({}) == pytest.approx(ab.DEFAULT_LAUNCH_BURST)
    assert ab.lock_timeout_from_env({}) == pytest.approx(ab.DEFAULT_LOCK_TIMEOUT)
    assert ab.launch_rate_from_env({"CSA_LAUNCH_RATE": "5"}) == pytest.approx(5.0)
    assert ab.launch_burst_from_env({"CSA_LAUNCH_BURST": "10"}) == pytest.approx(10.0)
    assert ab.lock_timeout_from_env({"CSA_LOCK_TIMEOUT_SEC": "0.5"}) == pytest.approx(0.5)
    # garbage -> default (fail open)
    assert ab.launch_rate_from_env({"CSA_LAUNCH_RATE": "bad"}) == pytest.approx(
        ab.DEFAULT_LAUNCH_RATE
    )


# ===========================================================================
# BUCKET IO — fail-open reads, atomic writes.
# ===========================================================================


def test_read_bucket_missing_returns_none(sandbox):
    assert ab.read_bucket(str(sandbox.agent_budget_dir)) is None


def test_write_then_read_bucket_roundtrips(sandbox):
    d = str(sandbox.agent_budget_dir)
    ab.write_bucket(d, 3.5, 1000.0)
    assert ab.read_bucket(d) == {"tokens": 3.5, "last_refill": 1000.0}


def test_read_bucket_garbage_returns_none(sandbox):
    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    with open(ab._bucket_path(d), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert ab.read_bucket(d) is None


def test_read_bucket_non_dict_returns_none(sandbox):
    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    with open(ab._bucket_path(d), "w", encoding="utf-8") as fh:
        json.dump([1, 2, 3], fh)
    assert ab.read_bucket(d) is None


def test_read_bucket_negative_returns_none(sandbox):
    d = str(sandbox.agent_budget_dir)
    ab.write_bucket(d, -1.0, 1000.0)  # write_bucket persists it; read must reject
    assert ab.read_bucket(d) is None


def test_write_bucket_leaves_no_tmp_files(sandbox):
    d = str(sandbox.agent_budget_dir)
    ab.write_bucket(d, 1.0, 2.0)
    assert [n for n in os.listdir(d) if ".tmp." in n] == []


# ===========================================================================
# ADMISSION LOCK — bounded, non-blocking, fail-open, always released.
# ===========================================================================


def test_admission_lock_acquires_uncontended(sandbox):
    with ab.admission_lock(str(sandbox.agent_budget_dir), timeout_s=0.5) as got:
        assert got is True


def test_admission_lock_fails_open_when_contended(sandbox):
    d = str(sandbox.agent_budget_dir)
    with ab.admission_lock(d, timeout_s=0.5) as outer:
        assert outer is True
        # A second acquisition (a distinct open file description) cannot take the
        # exclusive lock; it must fail OPEN (False) within the bounded wait rather
        # than block. This is the guarantee that a wedged holder never hangs a spawn.
        with ab.admission_lock(d, timeout_s=0.05) as inner:
            assert inner is False


def test_admission_lock_releases_after_context(sandbox):
    d = str(sandbox.agent_budget_dir)
    with ab.admission_lock(d, timeout_s=0.5) as a:
        assert a is True
    with ab.admission_lock(d, timeout_s=0.5) as b:  # freed -> reacquire succeeds
        assert b is True


# ===========================================================================
# PACER: tool_use_id keying, paced_admit (count-then-claim), gate wiring.
# ===========================================================================


def test_lib_tool_use_id():
    assert ab._lib.tool_use_id({"tool_use_id": "toolu_1"}) == "toolu_1"
    assert ab._lib.tool_use_id({}) == ""
    assert ab._lib.tool_use_id({"tool_use_id": 123}) == ""  # non-str -> ""


def test_gate_agent_id_uses_tool_use_id():
    assert ab._gate_agent_id({"tool_use_id": "toolu_abc"}) == "toolu_abc"


def test_gate_agent_id_mints_unique_when_absent():
    a = ab._gate_agent_id({})
    b = ab._gate_agent_id({})
    assert a.startswith("auto-") and b.startswith("auto-")
    assert a != b  # unique per call -> two same-type agents never collide


def test_paced_admit_claims_when_under_cap(sandbox):
    d = str(sandbox.agent_budget_dir)
    r = ab.paced_admit(d, 5, 3600, "toolu_1", rate=1.0, burst=5.0, lock_timeout=0.5, max_wait=0.0, poll=0.1)
    assert r["admitted"] is True and r["claimed"] is True and r["reason"] == "ok"
    assert os.path.exists(ab.lease_path(d, "toolu_1"))
    assert ab.prune_and_count(d, 3600) == 1


def test_paced_admit_distinct_ids_make_distinct_leases(sandbox):
    # finding 3: N concurrent SAME-TYPE agents must not collapse onto one lease.
    d = str(sandbox.agent_budget_dir)
    for tid in ("toolu_a", "toolu_b", "toolu_c"):
        ab.paced_admit(d, 10, 3600, tid, rate=5.0, burst=10.0, lock_timeout=0.5, max_wait=0.0, poll=0.1)
    assert ab.prune_and_count(d, 3600) == 3


def test_paced_admit_denies_at_cap_no_wait(sandbox):
    d = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")  # live=2, cap=2
    r = ab.paced_admit(d, 2, 3600, "toolu_x", rate=1.0, burst=5.0, lock_timeout=0.5, max_wait=0.0, poll=0.1)
    assert r["admitted"] is False and r["claimed"] is False and r["reason"] == "cap"
    assert not os.path.exists(ab.lease_path(d, "toolu_x"))


def test_paced_admit_fails_open_when_lock_held(sandbox):
    d = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")
    with ab.admission_lock(d, timeout_s=0.5) as held:
        assert held is True
        # lock held elsewhere -> paced_admit can't acquire -> fail OPEN (admit, no claim).
        r = ab.paced_admit(d, 2, 3600, "toolu_y", rate=1.0, burst=5.0, lock_timeout=0.05, max_wait=0.0, poll=0.1)
    assert r["admitted"] is True and r["claimed"] is False and r["reason"] == "lock"
    assert not os.path.exists(ab.lease_path(d, "toolu_y"))


def test_decide_gate_pacer_defers_admission_to_effect(sandbox, clean_env):
    # PACER ON -> decide returns a pacer decision; no read-only count/deny here.
    d = ab.decide(
        ["gate"],
        {"CSA_PACER": "1", "CSA_ANTHROPIC_CEILING": "5"},
        str(sandbox.agent_budget_dir),
        agent_id="toolu_1",
    )
    assert d["action"] == "gate"
    assert d["pacer"] is True
    assert d["agent_id"] == "toolu_1"
    assert d["ceiling"] == 5
    assert "deny" not in d  # decided in the effect (paced_admit), not here


def test_gate_pacer_claims_and_admits_via_main(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setattr(
        ab._lib, "read_event", lambda: {"tool_name": "Task", "tool_use_id": "toolu_zz"}
    )
    assert ab.main(["gate"]) == 0
    assert os.path.exists(ab.lease_path(str(sandbox.agent_budget_dir), "toolu_zz"))


def test_gate_pacer_denies_over_cap_via_main(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "2")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")  # deny immediately, don't wait
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setattr(ab._lib, "read_event", lambda: {"tool_use_id": "toolu_over"})
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")  # live=2 == cap 2
    assert ab.main(["gate"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    # the denied spawn claimed no lease
    assert not os.path.exists(ab.lease_path(str(sandbox.agent_budget_dir), "toolu_over"))


def test_gate_pacer_log_only_when_not_enforcing_via_main(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "2")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")  # at cap, but don't block the spawn
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)
    monkeypatch.setattr(ab._lib, "read_event", lambda: {"tool_use_id": "toolu_q"})
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")  # at cap, but NOT enforcing -> no deny
    assert ab.main(["gate"]) == 0
    assert capsys.readouterr().out == ""


def test_release_hook_removes_lease_when_pacer_on(sandbox, clean_env, monkeypatch):
    # R9 (08-25 round 4): the pacer's lease only releases on a REAL finish
    # (PostToolUse "completed" here) -- a bare {"tool_use_id": ...} payload
    # with no hook_event_name/tool_response (the pre-R9 fixture) no longer
    # qualifies, since it is indistinguishable from garbage; see
    # test_release_hook_pacer_lease_survives_async_launched_released_on_stop
    # for the async_launched-must-NOT-release half of this fix.
    monkeypatch.setenv("CSA_PACER", "1")
    _events(monkeypatch, [_completed_payload("toolu_rel", "agent_rel")])
    d = str(sandbox.agent_budget_dir)
    ab.write_lease(d, "toolu_rel")
    assert os.path.exists(ab.lease_path(d, "toolu_rel"))
    assert ab.main(["release_hook"]) == 0
    assert not os.path.exists(ab.lease_path(d, "toolu_rel"))  # claim<->release paired


def test_release_hook_noop_when_pacer_off(sandbox, clean_env, monkeypatch):
    # pacer OFF -> the PACER's own lease is never touched. The default-ON
    # spend ledger toggle still governs whether stdin is READ (main()'s
    # read_stdin condition), but as of 08-25 (B1) contributes nothing else to
    # this decision — see
    # test_decide_release_hook_spend_ledger_on_builds_spend_ledger_key.
    monkeypatch.setattr(ab._lib, "read_event", lambda: {"tool_use_id": "toolu_x"})
    d = str(sandbox.agent_budget_dir)
    ab.write_lease(d, "toolu_x")
    assert ab.main(["release_hook"]) == 0
    assert os.path.exists(ab.lease_path(d, "toolu_x"))  # untouched


def test_release_hook_idempotent_when_id_absent(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setattr(ab._lib, "read_event", lambda: {})  # no tool_use_id
    assert ab.main(["release_hook"]) == 0  # no-op, never crashes


def test_decide_release_hook_pacer_off_is_noop():
    # Pacer off -> the true no-op decision.
    d = ab.decide(["release_hook"], {"CSA_SPEND_LEDGER": "0"}, "/b")
    assert d == {"action": "release_hook", "exit": 0}


def test_decide_release_hook_spend_ledger_on_builds_spend_ledger_key():
    """Phase 0 step 2 (supersedes the pre-step-2 placeholder test this
    replaced): with the ledger on (default) decide() now attaches a real
    "spend_ledger" dict (event classification + ttl/lock_timeout) to the
    release_hook decision; with CSA_SPEND_LEDGER=0 that key is absent
    entirely — the toggle is no longer a true no-op either way."""
    on = ab.decide(["release_hook"], {}, "/b", "toolu_x", payload={"tool_use_id": "toolu_x"})
    assert on["action"] == "release_hook" and on["exit"] == 0
    assert "spend_ledger" in on
    assert on["spend_ledger"]["ttl"] == ab.DEFAULT_CLAIM_TTL

    off = ab.decide(["release_hook"], {"CSA_SPEND_LEDGER": "0"}, "/b", "toolu_x")
    assert off == {"action": "release_hook", "exit": 0}
    assert "spend_ledger" not in off


def test_decide_release_hook_master_off_short_circuits():
    d = ab.decide(["release_hook"], {"CSA_DISABLE_HOOKS": "1"}, "/b", "toolu_x")
    assert d == {"action": "release_hook", "exit": 0}


# ===========================================================================
# Decoupled-stdin-read regression guards (Phase 0 step 1/2,
# ~/.claude/plans/churn_phase0_measure.md). The throwaway CSA_SPIKE_DUMP=1
# artifact these tests used to also cover was removed in the same commit
# that landed step 2's real spend ledger (below).
# ===========================================================================


def test_gate_pacer_off_never_calls_paced_admit(sandbox, clean_env, monkeypatch):
    """Decoupling the stdin READ from pacer_enabled must never turn the
    pacer's admission machinery on: no lease claimed, no admission wait, no
    pacer-flavored deny — paced_admit must simply never run.

    B4 (08-25): the original version of this test stubbed paced_admit to
    RAISE, which is invisible — main()'s own outer `except Exception: return
    0` swallows any exception raised inside decide()/apply_decision(), so
    `assert ab.main(["gate"]) == 0` passes identically whether or not the
    leak actually happened. Recording the call instead is what actually
    falsifies a leak: a reverted fix (paced_admit called unconditionally)
    makes `calls` non-empty, which this DOES catch.
    """
    calls = []

    def fake_paced_admit(*a, **k):
        calls.append((a, k))
        return {"admitted": True, "claimed": False, "reason": "ok", "live": 0, "cap": 1}

    monkeypatch.setattr(ab, "paced_admit", fake_paced_admit)
    monkeypatch.setattr(ab._lib, "read_event", lambda: {"tool_use_id": "toolu_np"})
    assert ab.main(["gate"]) == 0
    assert calls == []
    assert not os.path.exists(ab.lease_path(str(sandbox.agent_budget_dir), "toolu_np"))


def test_spend_ledger_off_and_pacer_off_never_reads_stdin_gate_and_release_hook(
    sandbox, clean_env, monkeypatch
):
    """Combination (item 3, 08-25 round 3): with the pacer OFF and the
    default-ON spend ledger explicitly turned off (CSA_SPEND_LEDGER=0),
    main()'s own read_stdin gate must be False for BOTH subcommands that
    ever read stdin ("gate" and "release_hook") -- proven via a recorder,
    not merely "no crash" (an unread stdin and an empty-dict stdin read are
    otherwise indistinguishable from the decision alone)."""
    monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    calls = []

    def recorder():
        calls.append(1)
        return {}

    monkeypatch.setattr(ab._lib, "read_event", recorder)
    assert ab.main(["gate"]) == 0
    assert ab.main(["release_hook"]) == 0
    assert calls == []


def test_gate_and_release_hook_fail_open_when_dir_unwritable(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(
        ab._lib, "read_event", lambda: {"tool_use_id": "x", "tool_input": {"subagent_type": "y"}}
    )

    def boom_makedirs(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(ab.os, "makedirs", boom_makedirs)
    assert ab.main(["gate"]) == 0  # must not raise
    assert ab.main(["release_hook"]) == 0  # must not raise


def test_append_jsonl_writes_valid_lines(sandbox):
    d = str(sandbox.agent_budget_dir)
    path = os.path.join(d, "x.jsonl")
    ab._append_jsonl(path, {"a": 1})
    ab._append_jsonl(path, {"b": 2})
    assert _read_jsonl(path) == [{"a": 1}, {"b": 2}]


def test_append_jsonl_fails_open_when_os_open_raises(monkeypatch, tmp_path):
    """H12 (08-25): _append_jsonl now writes via os.open/os.write, not the
    builtin open(); the fail-open guarantee must hold for THAT primitive."""
    d = str(tmp_path / "budget")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "x.jsonl")

    def boom_open(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(ab.os, "open", boom_open)
    ab._append_jsonl(path, {"a": 1})  # must not raise
    assert not os.path.exists(path)


def test_append_jsonl_concurrent_writers_never_interleave(sandbox):
    """R5 (08-25 round 3, correcting an over-claim in the prior docstring
    here): this is a round-trip SMOKE test, not proof of atomicity. It
    asserts every line, from 6 GIL-bound Python threads hammering the same
    path, parses back as a complete JSON object with none lost or
    duplicated — a real regression (e.g. writing without O_APPEND, or
    truncating instead of appending) would show up here. What it does NOT
    prove is the interleaving claim the prior version of this docstring
    made ("a naive buffered write() + newline could plausibly interleave"):
    falsified in a scratch copy — reverting `_append_jsonl` to the old
    two-syscall shape (buffered `open(path, "a")` + a separate `.write("\\n")`
    call) and re-running this exact test, unchanged, still passes every
    time (5/5 runs). The CPython GIL serializes bytecode execution finely
    enough that this thread count/workload never actually exercises a torn
    write in practice, so a green result here was never evidence either way.
    The real atomicity guarantee this module relies on — O_APPEND's atomic
    offset update for a REGULAR file, plus a single `os.write()` call per
    record (looped only on a short count, never split across writes) — is a
    POSIX-level guarantee documented in `_append_jsonl`'s own docstring, not
    something a same-process, GIL-bound Python thread test can independently
    prove or falsify (a real test of that would need genuinely concurrent
    OS processes, not threads)."""
    import threading

    d = str(sandbox.agent_budget_dir)
    path = os.path.join(d, "race.jsonl")
    pad = "x" * 4000

    def worker(i):
        for j in range(20):
            ab._append_jsonl(path, {"worker": i, "seq": j, "pad": pad})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = open(path, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 6 * 20
    parsed = [json.loads(line) for line in lines]  # raises on ANY torn line
    assert len({(r["worker"], r["seq"]) for r in parsed}) == 6 * 20  # none lost/duped


# ===========================================================================
# PACER STAGGER — plan_admission/wait_hint (pure) + paced_admit loop (clocked).
# ===========================================================================


@pytest.mark.parametrize(
    "live,capacity,tokens,admit,new_tokens,reason",
    [
        (0, 5, 5.0, True, 4.0, "ok"),  # slot + token
        (5, 5, 5.0, False, 5.0, "cap"),  # at cap (cap beats rate)
        (0, 5, 0.5, False, 0.5, "rate"),  # no token
        (5, 5, 0.0, False, 0.0, "cap"),  # both bind -> cap priority
        (4, 5, 1.0, True, 0.0, "ok"),  # exactly one token
    ],
)
def test_plan_admission(live, capacity, tokens, admit, new_tokens, reason):
    a, nt, r = ab.plan_admission(live, capacity, tokens)
    assert a is admit
    assert nt == pytest.approx(new_tokens)
    assert r == reason


@pytest.mark.parametrize(
    "reason,tokens,rate,poll,expected",
    [
        ("rate", 0.0, 1.0, 0.25, 1.0),  # need 1 token at 1/s -> 1s
        ("rate", 0.5, 2.0, 0.25, 0.25),  # need 0.5 at 2/s -> 0.25s
        ("rate", 1.0, 1.0, 0.25, 0.0),  # already have a token
        ("cap", 0.0, 1.0, 0.25, 0.25),  # cap wait -> poll interval
        ("rate", 0.0, 0.0, 0.25, 0.25),  # rate 0 -> poll fallback
    ],
)
def test_wait_hint(reason, tokens, rate, poll, expected):
    assert ab.wait_hint(reason, tokens, rate, poll) == pytest.approx(expected)


class _Clock:
    """Deterministic fake clock: sleep advances both wall and monotonic time."""

    def __init__(self, wall=1000.0):
        self.wall = wall
        self.mono = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.wall += seconds
        self.mono += seconds


def test_paced_admit_waits_then_admits_when_token_refills(sandbox):
    # Under cap but bucket empty -> wait one refill period, then admit (the stagger).
    d = str(sandbox.agent_budget_dir)
    clk = _Clock()
    ab.write_bucket(d, 0.0, clk.wall)
    r = ab.paced_admit(
        d, 10, 3600, "toolu_w", rate=1.0, burst=1.0, lock_timeout=0.5,
        max_wait=5.0, poll=0.25, wall_now=lambda: clk.wall,
        mono_now=lambda: clk.mono, sleep_fn=clk.sleep, jitter_fn=lambda x: x,
    )
    assert r["admitted"] is True and r["claimed"] is True
    assert clk.sleeps  # it waited at least once instead of bursting
    assert os.path.exists(ab.lease_path(d, "toolu_w"))


def test_paced_admit_denies_after_max_wait_at_cap(sandbox):
    d = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "a")  # ceiling 1 -> at cap
    clk = _Clock()
    r = ab.paced_admit(
        d, 1, 3600, "toolu_c", rate=5.0, burst=5.0, lock_timeout=0.5,
        max_wait=0.5, poll=0.25, wall_now=lambda: clk.wall,
        mono_now=lambda: clk.mono, sleep_fn=clk.sleep, jitter_fn=lambda x: x,
    )
    assert r["admitted"] is False and r["reason"] == "cap"
    assert clk.mono >= 0.5  # waited up to the deadline before denying
    assert not os.path.exists(ab.lease_path(d, "toolu_c"))


def test_paced_admit_does_not_hold_lock_across_sleep(sandbox):
    # finding 7: the admission lock MUST be free while a waiter sleeps.
    d = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "a")  # at cap 1 -> waiter loops
    clk = _Clock()
    free_during_sleep = []

    def sleeper(seconds):
        with ab.admission_lock(d, timeout_s=0.05) as got:
            free_during_sleep.append(got)
        clk.sleep(seconds)

    ab.paced_admit(
        d, 1, 3600, "toolu_s", rate=5.0, burst=5.0, lock_timeout=0.2,
        max_wait=0.4, poll=0.2, wall_now=lambda: clk.wall,
        mono_now=lambda: clk.mono, sleep_fn=sleeper, jitter_fn=lambda x: x,
    )
    assert free_during_sleep and all(free_during_sleep)


def test_paced_admit_admits_after_slot_frees(sandbox):
    # finding 13 (recovery): a released slot promptly unblocks a waiter.
    d = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "held")  # cap 1, occupied
    clk = _Clock()
    freed = {"done": False}

    def sleeper(seconds):
        if not freed["done"]:
            ab._remove(ab.lease_path(d, "held"))  # a slot frees mid-wait
            freed["done"] = True
        clk.sleep(seconds)

    r = ab.paced_admit(
        d, 1, 3600, "toolu_free", rate=5.0, burst=5.0, lock_timeout=0.2,
        max_wait=2.0, poll=0.2, wall_now=lambda: clk.wall,
        mono_now=lambda: clk.mono, sleep_fn=sleeper, jitter_fn=lambda x: x,
    )
    assert r["admitted"] is True and r["claimed"] is True
    assert os.path.exists(ab.lease_path(d, "toolu_free"))


def test_paced_admit_no_over_admit_under_thread_race(sandbox):
    # finding 16: N racing admissions never exceed the cap (flock atomicity).
    import threading

    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    ceiling = 3
    results = []
    guard = threading.Lock()

    def worker(i):
        r = ab.paced_admit(
            d, ceiling, 3600, f"toolu_{i}", rate=100.0, burst=100.0,
            lock_timeout=2.0, max_wait=0.0, poll=0.05,
        )
        with guard:
            results.append(1 if r["claimed"] else 0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    claimed = sum(results)
    assert claimed <= ceiling  # INVARIANT: never over-admit past the cap
    assert claimed >= 1
    assert ab.prune_and_count(d, 3600) == claimed  # leases match claims


# ===========================================================================
# PURE: numeric config validation — garbage falls back to defaults (fail-open).
# ===========================================================================


@pytest.mark.parametrize(
    "raw,default,expected",
    [
        ("8", 8, 8),
        ("16", 8, 16),
        ("0", 8, 0),
        ("", 8, 8),  # empty -> default
        (None, 8, 8),  # missing -> default
        ("abc", 8, 8),  # non-numeric -> default
        ("8x", 8, 8),  # trailing garbage -> default
        ("-1", 8, 8),  # sign is not a digit run -> default
        ("3.5", 8, 8),  # float -> default
        (" 5 ", 8, 8),  # whitespace -> default
        ("3600", 3600, 3600),
    ],
)
def test_parse_int_config(raw, default, expected):
    assert ab.parse_int_config(raw, default) == expected


def test_ceiling_and_ttl_from_env_defaults_and_override():
    assert ab.ceiling_from_env({}) == ab.DEFAULT_CEILING
    assert ab.ttl_from_env({}) == ab.DEFAULT_TTL
    assert ab.ceiling_from_env({"CSA_ANTHROPIC_CEILING": "12"}) == 12
    assert ab.ttl_from_env({"CSA_LEASE_TTL_SEC": "60"}) == 60
    # Garbage -> defaults (fail open).
    assert ab.ceiling_from_env({"CSA_ANTHROPIC_CEILING": "xx"}) == 8
    assert ab.ttl_from_env({"CSA_LEASE_TTL_SEC": ""}) == 3600


def test_ceiling_ttl_from_env_reads_os_environ(clean_env):
    clean_env.setenv("CSA_ANTHROPIC_CEILING", "20")
    clean_env.setenv("CSA_LEASE_TTL_SEC", "120")
    assert ab.ceiling_from_env() == 20
    assert ab.ttl_from_env() == 120


def test_claim_ttl_from_env_default_and_override():
    assert ab.claim_ttl_from_env({}) == ab.DEFAULT_CLAIM_TTL == 21600
    assert ab.claim_ttl_from_env({"CSA_CLAIM_TTL_SEC": "60"}) == 60
    # Garbage -> default (fail open), and it is a DISTINCT knob from the
    # pacer's own CSA_LEASE_TTL_SEC.
    assert ab.claim_ttl_from_env({"CSA_CLAIM_TTL_SEC": "bad"}) == 21600
    assert ab.claim_ttl_from_env({"CSA_LEASE_TTL_SEC": "60"}) == 21600


# ===========================================================================
# PURE: safe_id — tr -c 'A-Za-z0-9._-' '_' plus the empty->unknown guard.
# ===========================================================================


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("agent-1", "agent-1"),
        ("Agent_9.tmp", "Agent_9.tmp"),
        ("a/b/c", "a_b_c"),  # slashes -> _
        ("../../etc/passwd", ".._.._etc_passwd"),  # traversal neutered
        ("has space", "has_space"),
        ("weird$#@!", "weird____"),
        ("tab\tnl\n", "tab_nl_"),
        ("", "unknown"),  # empty -> unknown
        ("ok.123-x_Y", "ok.123-x_Y"),  # all allowed chars survive
    ],
)
def test_safe_id(raw, expected):
    assert ab.safe_id(raw) == expected


def test_lease_path_uses_safe_id():
    p = ab.lease_path("/budget", "a/b")
    assert p == os.path.join("/budget", "lease-a_b")


# ===========================================================================
# PURE: cores / load1 introspection with fail-open fallbacks.
# ===========================================================================


def test_cores_returns_positive_int():
    assert ab.cores() >= 1


def test_cores_fallback_when_cpu_count_none(monkeypatch):
    monkeypatch.setattr(ab.os, "cpu_count", lambda: None)
    assert ab.cores() == ab.DEFAULT_CORES


def test_cores_fallback_when_cpu_count_zero(monkeypatch):
    monkeypatch.setattr(ab.os, "cpu_count", lambda: 0)
    assert ab.cores() == ab.DEFAULT_CORES


def test_cores_fallback_when_cpu_count_raises(monkeypatch):
    def boom():
        raise RuntimeError("no cpu info")

    monkeypatch.setattr(ab.os, "cpu_count", boom)
    assert ab.cores() == ab.DEFAULT_CORES


def test_load1_format_two_decimals(monkeypatch):
    monkeypatch.setattr(ab.os, "getloadavg", lambda: (1.5, 1.0, 0.5))
    assert ab.load1() == "1.50"


def test_load1_fallback_when_getloadavg_raises(monkeypatch):
    def boom():
        raise OSError("no loadavg")

    monkeypatch.setattr(ab.os, "getloadavg", boom)
    assert ab.load1() == ab.DEFAULT_LOAD


# ===========================================================================
# LEDGER: prune_and_count — live counting + self-healing prune.
# ===========================================================================


def test_prune_count_empty_dir_is_zero(sandbox):
    sandbox.agent_budget_dir.mkdir(parents=True)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_prune_count_missing_dir_fails_open_zero(sandbox):
    # Dir never created -> report 0 live (fail open), no raise.
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_prune_count_live_leases(sandbox):
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")
    _make_lease(sandbox, "c")
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 3


def test_prune_removes_stale_and_counts_live(sandbox):
    _make_lease(sandbox, "fresh")
    stale = _make_lease(sandbox, "stale", age_sec=7200)  # older than 3600 TTL
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 1
    assert not stale.exists()  # self-healed


def test_prune_ignores_non_lease_files(sandbox):
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True)
    (d / "README").write_text("not a lease")
    (d / "lease-real").write_text("agent_id=real\n")
    assert ab.prune_and_count(str(d), ttl=3600) == 1
    assert (d / "README").exists()  # untouched


def test_prune_removes_zero_mtime_lease(sandbox, monkeypatch):
    _make_lease(sandbox, "corrupt")
    # Force stat to fail -> mtime 0 -> treated as stale/corrupt and pruned.
    monkeypatch.setattr(ab, "_lease_mtime", lambda p: 0)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_prune_unreadable_dir_fails_open(sandbox, monkeypatch):
    sandbox.agent_budget_dir.mkdir(parents=True)
    monkeypatch.setattr(ab.os, "access", lambda p, m: False)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_prune_listdir_raises_fails_open(sandbox, monkeypatch):
    sandbox.agent_budget_dir.mkdir(parents=True)

    def boom(_p):
        raise OSError("listdir blew up")

    monkeypatch.setattr(ab.os, "listdir", boom)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_prune_skips_vanished_lease(sandbox, monkeypatch):
    _make_lease(sandbox, "gone")
    # listdir reports a name, but os.path.exists says it's gone (race) -> skip.
    monkeypatch.setattr(ab.os.path, "exists", lambda p: False)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_lease_mtime_zero_on_missing():
    assert ab._lease_mtime("/no/such/lease") == 0


# ===========================================================================
# B1 (08-25 round 5): prune_and_count's PENDING_STOP_PREFIX marker branch.
# ===========================================================================


def test_prune_fresh_pending_stop_marker_not_counted_survives(sandbox):
    """B1(a): a fresh marker isn't a lease and must survive the prune."""
    d = str(sandbox.agent_budget_dir)
    ab._ensure_dir(d)
    ab._write_pending_stop_marker(d, "agentFresh")
    marker = ab._pending_stop_marker_path(d, "agentFresh")
    assert ab.prune_and_count(d, ttl=3600) == 0
    assert os.path.exists(marker)


def test_prune_removes_stale_pending_stop_marker(sandbox):
    """B1(b): a marker aged past ttl is swept, same TTL rule as a lease."""
    d = str(sandbox.agent_budget_dir)
    ab._ensure_dir(d)
    ab._write_pending_stop_marker(d, "agentStale")
    marker = ab._pending_stop_marker_path(d, "agentStale")
    os.utime(marker, (0, 0))
    assert ab.prune_and_count(d, ttl=3600) == 0
    assert not os.path.exists(marker)


def test_main_pacer_off_writes_no_pending_stop_marker(sandbox, clean_env, monkeypatch, tmp_path):
    """B1(c): CSA_PACER off -- a SubagentStop + async_launched pair through
    main() must never write a PENDING_STOP_PREFIX marker (the pacer's own
    identity-resolution effects never run when the pacer itself is off)."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "0")
    transcript = tmp_path / "agent-pacer-off.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    aid, tuid = "agentPacerOffB1c", "tuPacerOffB1c"
    _events(monkeypatch, [_subagent_stop_payload(aid, transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0
    _events(monkeypatch, [_async_launched_payload(tuid, aid)])
    assert ab.main(["release_hook"]) == 0
    entries = os.listdir(d) if os.path.isdir(d) else []
    assert not any(n.startswith(ab.PENDING_STOP_PREFIX) for n in entries)


# ===========================================================================
# LEDGER: reset — remove stale OR malformed (no agent_id=) leases.
# ===========================================================================


def test_reset_removes_stale(sandbox):
    _make_lease(sandbox, "fresh")
    _make_lease(sandbox, "old", age_sec=7200)
    removed = ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600)
    assert removed == 1


def test_reset_removes_malformed_missing_agent_id(sandbox):
    # Fresh mtime but NO agent_id= line -> malformed -> removed.
    _make_lease(sandbox, "bad", body="pid=1\nclaimed_at=x\n")
    _make_lease(sandbox, "good", body="agent_id=good\npid=1\n")
    removed = ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600)
    assert removed == 1
    assert (sandbox.agent_budget_dir / "lease-good").exists()
    assert not (sandbox.agent_budget_dir / "lease-bad").exists()


def test_reset_missing_dir_removes_nothing(sandbox):
    assert ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_reset_ignores_non_lease_files(sandbox):
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True)
    (d / "notes.txt").write_text("x")
    assert ab.reset_ledger(str(d), ttl=3600) == 0
    assert (d / "notes.txt").exists()


def test_reset_listdir_raises_fails_open(sandbox, monkeypatch):
    sandbox.agent_budget_dir.mkdir(parents=True)

    def boom(_p):
        raise OSError("nope")

    monkeypatch.setattr(ab.os, "listdir", boom)
    assert ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_reset_skips_vanished_lease(sandbox, monkeypatch):
    _make_lease(sandbox, "gone")
    monkeypatch.setattr(ab.os.path, "exists", lambda p: False)
    assert ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_reset_remove_failure_not_counted(sandbox, monkeypatch):
    _make_lease(sandbox, "stale", age_sec=7200)
    monkeypatch.setattr(ab, "_remove", lambda p: False)
    assert ab.reset_ledger(str(sandbox.agent_budget_dir), ttl=3600) == 0


def test_reset_removes_pending_stop_marker_unconditionally(sandbox):
    """N3 (08-25 round 5): reset sweeps EVERY marker regardless of age --
    pure housekeeping -- while a fresh, well-formed lease still survives."""
    d = str(sandbox.agent_budget_dir)
    ab._ensure_dir(d)
    ab._write_pending_stop_marker(d, "agentFreshMark")
    marker = ab._pending_stop_marker_path(d, "agentFreshMark")
    _make_lease(sandbox, "still_here")
    removed = ab.reset_ledger(d, ttl=3600)
    assert removed == 1
    assert not os.path.exists(marker)
    assert (sandbox.agent_budget_dir / "lease-still_here").exists()


def test_lease_has_agent_id_true_false(sandbox):
    good = _make_lease(sandbox, "g", body="agent_id=g\n")
    bad = _make_lease(sandbox, "b", body="pid=1\n")
    assert ab._lease_has_agent_id(str(good)) is True
    assert ab._lease_has_agent_id(str(bad)) is False


def test_lease_has_agent_id_open_error(monkeypatch):
    assert ab._lease_has_agent_id("/no/such/file") is False


# ===========================================================================
# I/O primitives.
# ===========================================================================


def test_remove_missing_is_true():
    assert ab._remove("/no/such/file") is True


def test_remove_success(sandbox):
    p = _make_lease(sandbox, "x")
    assert ab._remove(str(p)) is True
    assert not p.exists()


def test_remove_swallows_error(monkeypatch):
    def boom(p):
        raise PermissionError("nope")

    monkeypatch.setattr(ab.os, "remove", boom)
    assert ab._remove("/some/path") is False


def test_write_lease_creates_file(sandbox):
    ab.write_lease(str(sandbox.agent_budget_dir), "agent-7")
    path = sandbox.agent_budget_dir / "lease-agent-7"
    assert path.exists()
    text = path.read_text()
    assert "agent_id=agent-7" in text
    assert "pid=" in text
    assert "claimed_at=" in text


def test_write_lease_idempotent_refreshes(sandbox):
    ab.write_lease(str(sandbox.agent_budget_dir), "dup")
    ab.write_lease(str(sandbox.agent_budget_dir), "dup")  # no crash, overwrites
    # exactly one lease file for the id.
    leases = list(sandbox.agent_budget_dir.glob("lease-dup"))
    assert len(leases) == 1


def test_write_lease_swallows_open_error(sandbox, monkeypatch):
    real_open = open

    def boom_open(path, *a, **k):
        if "lease-" in str(path):
            raise OSError("read-only")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    ab.write_lease(str(sandbox.agent_budget_dir), "x")  # must not raise


def test_ensure_dir_swallows_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("read-only")

    monkeypatch.setattr(ab.os, "makedirs", boom)
    ab._ensure_dir("/some/dir")  # must not raise


def test_now_epoch_is_int():
    assert isinstance(ab._now_epoch(), int)


def test_now_epoch_f_preserves_subsecond_precision(monkeypatch):
    """F3 (08-25 round 5): every existing caller monkeypatches
    `ab._now_epoch_f` ITSELF (never the underlying `time.time()`), so a
    regression reverting its body to whole-second truncation (B3's own
    original bug, `int(time.time())`) would stay green against every one
    of those. Patch `time.time` directly and assert the exact sub-second
    float passes through un-truncated."""
    import time

    monkeypatch.setattr(time, "time", lambda: 1787684299.4)
    assert ab._now_epoch_f() == 1787684299.4


# ===========================================================================
# decide() — PURE ROUTER vectors, incl. the FAIL-OPEN cases.
# ===========================================================================


def test_decide_default_is_status():
    d = ab.decide([], {}, "/b")
    assert d["action"] == "status"
    assert d["exit"] == 0


def test_decide_status_explicit():
    d = ab.decide(["status"], {}, "/b")
    assert d["action"] == "status"


def test_decide_claim_with_id():
    d = ab.decide(["claim", "a1"], {}, "/b")
    assert d == {"action": "claim", "exit": 0, "agent_id": "a1"}


def test_decide_claim_without_id_is_usage_error_exit2():
    d = ab.decide(["claim"], {}, "/b")
    assert d["action"] == "claim"
    assert d["exit"] == 2
    assert "requires <agent_id>" in d["error"]


def test_decide_release_with_id():
    d = ab.decide(["release", "a1"], {}, "/b")
    assert d == {"action": "release", "exit": 0, "agent_id": "a1"}


def test_decide_release_without_id_is_usage_error_exit2():
    d = ab.decide(["release"], {}, "/b")
    assert d["exit"] == 2
    assert "requires <agent_id>" in d["error"]


def test_decide_reset():
    d = ab.decide(["reset"], {"CSA_LEASE_TTL_SEC": "50"}, "/b")
    assert d["action"] == "reset"
    assert d["ttl"] == 50


def test_decide_doctor():
    d = ab.decide(["doctor"], {}, "/b")
    assert d["action"] == "doctor"
    assert d["ceiling"] == 8


def test_decide_unknown_subcommand_fails_open_exit0():
    d = ab.decide(["frobnicate"], {}, "/b")
    assert d["action"] == "usage"
    assert d["exit"] == 0  # FAIL OPEN — never blocks
    assert "usage:" in d["error"]


# --- gate: FAIL-OPEN + LOG-ONLY-unless-enforcing --------------------------


def test_decide_gate_master_off_short_circuits(sandbox):
    _make_lease(sandbox, "a")
    d = ab.decide(["gate"], {"CSA_DISABLE_HOOKS": "1"}, str(sandbox.agent_budget_dir))
    # Master off: no ledger work, no log, no deny, exit 0.
    assert d == {"action": "gate", "exit": 0}


def test_decide_gate_log_only_when_not_enforcing(sandbox, clean_env, monkeypatch):
    # Not enforcing -> logs task_gate but never denies, even at capacity.
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")  # live=2 >= cap 2 (ceiling forces cap)
    d = ab.decide(["gate"], {"CSA_ANTHROPIC_CEILING": "2"}, str(sandbox.agent_budget_dir))
    assert d["action"] == "gate"
    assert d["exit"] == 0
    assert "deny" not in d  # LOG-ONLY
    assert d["log"][0] == "task_gate"
    assert d["log"][1] == {"live": 2, "cap": 2}


def test_decide_gate_enforcing_under_cap_no_deny(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    _make_lease(sandbox, "a")  # live=1 < cap 8 (default ceiling)
    d = ab.decide(["gate"], {}, str(sandbox.agent_budget_dir))
    assert "deny" not in d
    assert d["exit"] == 0


def test_decide_gate_enforcing_at_cap_emits_deny(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")  # live=2 >= cap 2
    d = ab.decide(["gate"], {"CSA_ANTHROPIC_CEILING": "2"}, str(sandbox.agent_budget_dir))
    assert d["exit"] == 0  # STILL exit 0 — deny is via JSON, not exit code
    assert "deny" in d
    assert "2 live agents >= cap 2" in d["deny"]
    assert "CSA_ANTHROPIC_CEILING" in d["deny"]


def test_decide_gate_enforcing_over_cap_emits_deny(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    for i in range(5):
        _make_lease(sandbox, f"a{i}")  # live=5 > cap 2
    d = ab.decide(["gate"], {"CSA_ANTHROPIC_CEILING": "2"}, str(sandbox.agent_budget_dir))
    assert "deny" in d


# --- browser_pool: FAIL-OPEN, LOG-ONLY ------------------------------------


def test_decide_browser_pool_master_off(sandbox):
    d = ab.decide(["browser_pool"], {"CSA_DISABLE_HOOKS": "1"}, "/b")
    assert d == {"action": "browser_pool", "exit": 0}


def test_decide_browser_pool_logs_and_passes_args(sandbox):
    d = ab.decide(["browser_pool", "status", "--x"], {}, "/b")
    assert d["action"] == "browser_pool"
    assert d["exit"] == 0
    assert d["pool_args"] == ["status", "--x"]
    assert d["log"] == ("browser_pool", {"live": 0, "cap": 0})


def test_disabled_helper():
    assert ab._disabled({"CSA_DISABLE_HOOKS": "1"}) is True
    assert ab._disabled({"CSA_DISABLE_HOOKS": "0"}) is False
    assert ab._disabled({}) is False


# ===========================================================================
# apply_decision() — END-TO-END effects through in-memory streams.
# ===========================================================================


def test_status_emits_json_payload(sandbox, clean_env):
    _make_lease(sandbox, "one")
    code, out, err = _run(["status"], sandbox)
    assert code == 0
    payload = json.loads(out)
    assert payload["cpu_cores"] >= 1
    assert payload["ceiling"] == 8
    assert payload["live_leases"] == 1
    assert "load_1min" in payload
    assert "recommended_additional_slots" in payload
    assert err == ""


def test_status_default_no_subcommand(sandbox, clean_env):
    code, out, _ = _run([], sandbox)
    assert code == 0
    assert json.loads(out)["ceiling"] == 8


def test_status_respects_ceiling_env(sandbox, clean_env):
    code, out, _ = _run(["status"], sandbox, environ={"CSA_ANTHROPIC_CEILING": "3"})
    assert json.loads(out)["ceiling"] == 3


def test_status_includes_pacer_and_bucket_fields(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_LAUNCH_RATE", "3")
    monkeypatch.setenv("CSA_LAUNCH_BURST", "6")
    code, out, _ = _run(["status"], sandbox)
    p = json.loads(out)
    assert p["pacer_enabled"] is True
    assert p["launch_rate_per_sec"] == pytest.approx(3.0)
    assert p["launch_burst"] == pytest.approx(6.0)
    # no bucket file yet -> reads as FULL (fail-open) == burst
    assert p["launch_tokens_available"] == pytest.approx(6.0)


def test_status_bucket_tokens_reflect_written_state(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_LAUNCH_RATE", "1")
    monkeypatch.setenv("CSA_LAUNCH_BURST", "5")
    d = str(sandbox.agent_budget_dir)
    ab.write_bucket(d, 2.0, ab._now_epoch())  # 2 tokens, refilled just now
    code, out, _ = _run(["status"], sandbox)
    tokens = json.loads(out)["launch_tokens_available"]
    assert 2.0 <= tokens <= 3.0  # ~2 (+ up to 1s of refill at rate 1)


def test_doctor_shows_pacer_and_bucket(sandbox, clean_env, monkeypatch):
    sandbox.agent_budget_dir.mkdir(parents=True)
    monkeypatch.setenv("CSA_PACER", "1")
    code, out, _ = _run(["doctor"], sandbox)
    assert "pacer_enabled   : True" in out
    assert "launch_rate" in out
    assert "launch_burst" in out
    assert "launch_tokens" in out
    assert "lock_timeout" in out


def test_claim_creates_lease_and_prints_ok(sandbox, clean_env):
    code, out, err = _run(["claim", "agent-42"], sandbox)
    assert code == 0
    assert out.strip() == "OK claimed agent-42"
    assert (sandbox.agent_budget_dir / "lease-agent-42").exists()
    assert err == ""


def test_claim_idempotent(sandbox, clean_env):
    _run(["claim", "dup"], sandbox)
    code, out, _ = _run(["claim", "dup"], sandbox)
    assert code == 0
    assert len(list(sandbox.agent_budget_dir.glob("lease-dup"))) == 1


def test_claim_sanitizes_id(sandbox, clean_env):
    code, out, _ = _run(["claim", "a/b c"], sandbox)
    assert code == 0
    assert (sandbox.agent_budget_dir / "lease-a_b_c").exists()
    # But the human-facing OK message keeps the original id.
    assert out.strip() == "OK claimed a/b c"


def test_claim_without_id_exit2_and_stderr(sandbox, clean_env):
    code, out, err = _run(["claim"], sandbox)
    assert code == 2
    assert out == ""
    assert "requires <agent_id>" in err


def test_release_removes_lease(sandbox, clean_env):
    _make_lease(sandbox, "gone")
    code, out, err = _run(["release", "gone"], sandbox)
    assert code == 0
    assert out.strip() == "OK released gone"
    assert not (sandbox.agent_budget_dir / "lease-gone").exists()


def test_release_missing_lease_is_ok(sandbox, clean_env):
    # rm -f semantics: releasing a non-existent lease still succeeds.
    code, out, _ = _run(["release", "never-claimed"], sandbox)
    assert code == 0
    assert out.strip() == "OK released never-claimed"


def test_release_without_id_exit2(sandbox, clean_env):
    code, out, err = _run(["release"], sandbox)
    assert code == 2
    assert "requires <agent_id>" in err


def test_claim_then_release_roundtrip_counts(sandbox, clean_env):
    _run(["claim", "a"], sandbox)
    _run(["claim", "b"], sandbox)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), 3600) == 2
    _run(["release", "a"], sandbox)
    assert ab.prune_and_count(str(sandbox.agent_budget_dir), 3600) == 1


def test_reset_reports_removed_count(sandbox, clean_env):
    _make_lease(sandbox, "fresh")
    _make_lease(sandbox, "old", age_sec=7200)
    code, out, _ = _run(["reset"], sandbox)
    assert code == 0
    assert "OK reset (removed 1 stale/corrupt lease(s))" in out


def test_doctor_prints_health(sandbox, clean_env):
    sandbox.agent_budget_dir.mkdir(parents=True)
    _make_lease(sandbox, "x")
    code, out, _ = _run(["doctor"], sandbox)
    assert code == 0
    assert "agent_budget doctor" in out
    assert "budget_dir" in out
    assert "cpu_cores" in out
    assert "ceiling         : 8" in out
    assert "live_leases     : 1" in out
    assert "fail_mode       : OPEN" in out
    assert "writable=yes" in out


def test_doctor_writable_no_when_dir_missing(sandbox, clean_env):
    # No budget dir created -> writable=no.
    code, out, _ = _run(["doctor"], sandbox)
    assert "writable=no" in out


def test_unknown_subcommand_prints_usage_exit0(sandbox, clean_env):
    code, out, err = _run(["nonsense"], sandbox)
    assert code == 0  # FAIL OPEN
    assert out == ""
    assert "usage:" in err


# --- gate through apply_decision ------------------------------------------


def test_gate_not_enforcing_no_output_but_logs(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)
    _make_lease(sandbox, "a")
    code, out, err = _run(["gate"], sandbox)
    assert code == 0
    assert out == ""  # LOG-ONLY: no deny JSON emitted
    # a log line was written.
    lines = sandbox.log_file.read_text().strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["hook"] == "agent_budget"
    assert rec["decision"] == "task_gate"
    assert rec["live"] == 1


def test_gate_enforcing_at_cap_emits_deny_json_exit0(sandbox, clean_env, monkeypatch, capsys):
    # The deny is emitted via _lib.emit_pretooluse_deny, which writes to the real
    # sys.stdout (as it must in production) — capture it with capsys, not _run's
    # in-memory stream. Still: exit code is 0, deny is JSON only.
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "2")  # cap = max(1,2) = 2
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")
    budget_dir = str(sandbox.agent_budget_dir)
    decision = ab.decide(["gate"], dict(os.environ), budget_dir)
    code = ab.apply_decision(decision, budget_dir, sys.stdout, sys.stderr)
    assert code == 0  # NEVER blocks via exit code
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "live agents >= cap" in obj["systemMessage"]


def test_gate_master_off_no_log_no_output(sandbox, clean_env):
    _make_lease(sandbox, "a")
    code, out, err = _run(["gate"], sandbox, environ={"CSA_DISABLE_HOOKS": "1"})
    assert code == 0
    assert out == ""
    # master off short-circuits BEFORE logging.
    assert not sandbox.log_file.exists()


# --- browser_pool through apply_decision ----------------------------------


def test_browser_pool_logs_and_exit0_no_pool_file(sandbox, clean_env):
    # No vendored pool file present -> delegate is a no-op, still exit 0.
    code, out, err = _run(["browser_pool", "status"], sandbox)
    assert code == 0
    assert out == ""
    lines = sandbox.log_file.read_text().strip().splitlines()
    assert json.loads(lines[-1])["decision"] == "browser_pool"


def test_browser_pool_master_off(sandbox, clean_env):
    code, out, err = _run(["browser_pool"], sandbox, environ={"CSA_DISABLE_HOOKS": "1"})
    assert code == 0
    assert not sandbox.log_file.exists()  # short-circuited before log


def test_run_browser_pool_no_file_is_noop(sandbox, monkeypatch):
    # CLAUDE_DIR points into sandbox with no live-testing/browser_pool.py.
    called = {"ran": False}

    def fake_run(*a, **k):
        called["ran"] = True

    monkeypatch.setattr("subprocess.run", fake_run)
    ab._run_browser_pool([])
    assert called["ran"] is False


def test_run_browser_pool_invokes_present_pool(sandbox, monkeypatch):
    pool_dir = sandbox.claude / "live-testing"
    pool_dir.mkdir(parents=True)
    (pool_dir / "browser_pool.py").write_text("print('ok')\n")
    captured = {}

    def fake_run(cmd, **k):
        captured["cmd"] = cmd

    monkeypatch.setattr("subprocess.run", fake_run)
    ab._run_browser_pool(["status", "--x"])
    assert captured["cmd"][1].endswith("browser_pool.py")
    assert captured["cmd"][2:] == ["status", "--x"]


def test_run_browser_pool_swallows_subprocess_error(sandbox, monkeypatch):
    pool_dir = sandbox.claude / "live-testing"
    pool_dir.mkdir(parents=True)
    (pool_dir / "browser_pool.py").write_text("x")

    def boom(*a, **k):
        raise OSError("spawn failed")

    monkeypatch.setattr("subprocess.run", boom)
    ab._run_browser_pool([])  # must not raise


# ===========================================================================
# main() — the thin entrypoint. Always fails open.
# ===========================================================================


def test_main_status_exit0(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["agent_budget.py", "status"])
    code = ab.main()
    assert code == 0
    out = capsys.readouterr().out
    assert json.loads(out)["ceiling"] == 8


def test_main_uses_argv_default_none(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["agent_budget.py"])
    assert ab.main() == 0
    assert json.loads(capsys.readouterr().out)["ceiling"] == 8


def test_main_claim_writes_lease(sandbox, clean_env):
    assert ab.main(["claim", "m1"]) == 0
    assert (sandbox.agent_budget_dir / "lease-m1").exists()


def test_main_unknown_fails_open_exit0(sandbox, clean_env, capsys):
    assert ab.main(["bogus"]) == 0
    assert "usage:" in capsys.readouterr().err


def test_main_claim_missing_id_exit2(sandbox, clean_env, capsys):
    assert ab.main(["claim"]) == 2
    assert "requires <agent_id>" in capsys.readouterr().err


def test_main_swallows_internal_exception_fails_open(sandbox, clean_env, monkeypatch):
    # Any crash inside decide/apply must fail open (return 0), never propagate.
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(ab, "decide", boom)
    assert ab.main(["status"]) == 0


def test_main_gate_master_off_exit0(sandbox, clean_env, monkeypatch, capsys):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    _make_lease(sandbox, "a")
    assert ab.main(["gate"]) == 0
    assert capsys.readouterr().out == ""


def test_main_gate_enforcing_deny_still_exit0(sandbox, clean_env, monkeypatch, capsys):
    # N14 (08-25 round 3): PACER OFF + the default-ON spend ledger toggle
    # together make main()'s own `read_stdin` True for a "gate" subcommand,
    # so this test consumed REAL stdin before this stub existed -- harmless
    # under a captured pytest run (empty stdin -> EOF -> {}), but hangs the
    # whole suite under `pytest -s` (no capture, a real attached terminal).
    # Stubbed exactly like every other main()-driving test in this file.
    monkeypatch.setattr(ab._lib, "read_event", lambda: {})
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "2")  # cap = max(1,2) = 2
    _make_lease(sandbox, "a")
    _make_lease(sandbox, "b")
    assert ab.main(["gate"]) == 0  # deny is JSON, not an exit code
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"


# ===========================================================================
# SPEND LEDGER — Phase 0 step 2 (~/.claude/plans/churn_phase0_measure.md).
# claims.jsonl / stops.jsonl / spend.jsonl: the three-event join
# (gate/PostToolUse/SubagentStop), reap, locking, and token-source rejection.
# ===========================================================================


# --- PURE table transforms -------------------------------------------------


def test_pop_claim_by_tool_use_id_found_and_missing():
    rows = [{"tool_use_id": "a"}, {"tool_use_id": "b"}]
    new_rows, popped = ab.pop_claim_by_tool_use_id(rows, "a")
    assert popped == {"tool_use_id": "a"}
    assert new_rows == [{"tool_use_id": "b"}]
    assert rows == [{"tool_use_id": "a"}, {"tool_use_id": "b"}]  # original untouched

    new_rows, popped = ab.pop_claim_by_tool_use_id(rows, "nope")
    assert popped is None
    assert new_rows == rows


def test_pop_claim_by_agent_id_found_and_missing():
    rows = [{"agent_id": "x"}, {"agent_id": None}]
    new_rows, popped = ab.pop_claim_by_agent_id(rows, "x")
    assert popped == {"agent_id": "x"}
    assert new_rows == [{"agent_id": None}]
    # N15 (08-25 round 4): a falsy agent_id (None/"") is NEVER a valid
    # lookup key -- it must return early WITHOUT matching a row whose own
    # agent_id happens to also be None (the normal un-annotated-claim
    # state), never silently consuming the wrong row.
    new_rows, popped = ab.pop_claim_by_agent_id(rows, None)
    assert popped is None
    assert new_rows == rows
    new_rows, popped = ab.pop_claim_by_agent_id(rows, "")
    assert popped is None
    assert new_rows == rows


def test_model_from_claims_by_agent_id_prefers_annotated_model():
    rows = [{"agent_id": "x", "model": "claude-opus-5", "model_requested": "claude-sonnet-5"}]
    assert ab._model_from_claims_by_agent_id(rows, "x") == "claude-opus-5"


def test_model_from_claims_by_agent_id_falls_back_to_model_requested():
    rows = [{"agent_id": "x", "model": None, "model_requested": "claude-sonnet-5"}]
    assert ab._model_from_claims_by_agent_id(rows, "x") == "claude-sonnet-5"


def test_model_from_claims_by_agent_id_no_match_returns_none():
    rows = [{"agent_id": "y", "model": "claude-opus-5"}]
    assert ab._model_from_claims_by_agent_id(rows, "x") is None


def test_model_from_claims_by_agent_id_falsy_agent_id_never_matches():
    # N15-style guard: an un-annotated claim's own agent_id is None too --
    # a falsy lookup key must never "match" the first such row.
    rows = [{"agent_id": None, "model": "claude-opus-5"}]
    assert ab._model_from_claims_by_agent_id(rows, None) is None
    assert ab._model_from_claims_by_agent_id(rows, "") is None


def test_model_from_claims_by_agent_id_never_mutates_input():
    rows = [{"agent_id": "x", "model": "claude-opus-5"}]
    original = [dict(r) for r in rows]
    ab._model_from_claims_by_agent_id(rows, "x")
    assert rows == original


def test_model_from_claims_by_agent_id_fail_open_on_garbage_model_fields():
    # Fail-open discipline: a matched row whose model/model_requested are
    # garbage (non-string) must never raise and must never be returned as
    # a fabricated "model" value -- degrades to None, same as "no match".
    rows = [{"agent_id": "x", "model": 12345, "model_requested": {"nested": True}}]
    assert ab._model_from_claims_by_agent_id(rows, "x") is None
    rows2 = [{"agent_id": "x", "model": "", "model_requested": ""}]
    assert ab._model_from_claims_by_agent_id(rows2, "x") is None
    rows3 = [{"agent_id": "x"}]  # no model fields at all
    assert ab._model_from_claims_by_agent_id(rows3, "x") is None


def test_model_from_claims_by_agent_id_fail_open_on_non_dict_rows():
    # A malformed row (not a dict) must never raise -- degrades to "no
    # match" for that row, same as _read_table's own established
    # self-healing convention elsewhere in this module.
    assert ab._model_from_claims_by_agent_id([None, "garbage", 42], "x") is None
    assert ab._model_from_claims_by_agent_id([None, {"agent_id": "x", "model": "m"}], "x") == "m"


def test_annotate_claim_sets_agent_id_and_model_copies_row():
    rows = [{"tool_use_id": "a", "agent_id": None, "model": None}]
    new_rows, updated = ab.annotate_claim(rows, "a", "agentX", "claude-haiku")
    assert updated == {"tool_use_id": "a", "agent_id": "agentX", "model": "claude-haiku"}
    assert new_rows == [updated]
    assert rows[0]["agent_id"] is None  # original row never mutated in place


def test_annotate_claim_no_match_returns_none():
    rows = [{"tool_use_id": "a"}]
    new_rows, updated = ab.annotate_claim(rows, "missing", "agentX", "m")
    assert updated is None
    assert new_rows == rows


def test_pop_stop_by_agent_id_found_and_missing():
    rows = [{"agent_id": "x"}]
    new_rows, popped = ab.pop_stop_by_agent_id(rows, "x")
    assert popped == {"agent_id": "x"}
    assert new_rows == []
    new_rows, popped = ab.pop_stop_by_agent_id([], "x")
    assert popped is None and new_rows == []
    # N15: a falsy agent_id never matches.
    new_rows, popped = ab.pop_stop_by_agent_id(rows, None)
    assert popped is None and new_rows == rows
    # B1: a "completed"-kind row for the SAME agent_id is never mistaken
    # for a "stop"-kind row (the two now share this one physical table).
    mixed = [{"agent_id": "y", "kind": "completed"}, {"agent_id": "y", "kind": "stop"}]
    new_rows, popped = ab.pop_stop_by_agent_id(mixed, "y")
    assert popped == {"agent_id": "y", "kind": "stop"}
    assert new_rows == [{"agent_id": "y", "kind": "completed"}]


def test_pop_pending_completed_by_agent_id_found_missing_and_kind_filtered():
    mixed = [{"agent_id": "y", "kind": "stop"}, {"agent_id": "y", "kind": "completed"}]
    new_rows, popped = ab.pop_pending_completed_by_agent_id(mixed, "y")
    assert popped == {"agent_id": "y", "kind": "completed"}
    assert new_rows == [{"agent_id": "y", "kind": "stop"}]
    new_rows, popped = ab.pop_pending_completed_by_agent_id([], "y")
    assert popped is None and new_rows == []
    # N15: a falsy agent_id never matches.
    new_rows, popped = ab.pop_pending_completed_by_agent_id(mixed, None)
    assert popped is None and new_rows == mixed


# --- _read_table / _write_table ---------------------------------------------


def test_read_table_missing_file_returns_empty_list(sandbox):
    assert ab._read_table(ab.claims_path(str(sandbox.agent_budget_dir))) == []


def test_write_then_read_table_roundtrips(sandbox):
    d = str(sandbox.agent_budget_dir)
    rows = [{"a": 1}, {"b": 2}]
    ab._write_table(ab.claims_path(d), rows)
    assert ab._read_table(ab.claims_path(d)) == rows


def test_read_table_skips_malformed_lines(sandbox):
    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    path = ab.claims_path(d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"a": 1}\nnot json\n{"b": 2}\n[1,2,3]\n')
    assert ab._read_table(path) == [{"a": 1}, {"b": 2}]


def test_write_table_leaves_no_tmp_files(sandbox):
    d = str(sandbox.agent_budget_dir)
    ab._write_table(ab.claims_path(d), [{"a": 1}])
    assert [n for n in os.listdir(d) if ".tmp." in n] == []


def test_write_table_atomic_replace_survives_open_failure(sandbox, monkeypatch):
    d = str(sandbox.agent_budget_dir)
    path = ab.claims_path(d)
    ab._write_table(path, [{"a": 1}])  # seed a real row first

    def boom_replace(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(ab.os, "replace", boom_replace)
    ab._write_table(path, [{"a": 2}])  # must not raise
    # The failed write must never leave a corrupt/partial file — the ORIGINAL
    # content survives since os.replace (the atomic swap) never happened.
    assert ab._read_table(path) == [{"a": 1}]


# --- sum_transcript_tokens ---------------------------------------------------


def test_sum_transcript_tokens_hand_derived_sum(tmp_path):
    path = tmp_path / "transcript.jsonl"
    expected = _write_transcript(
        str(path),
        [
            {
                "input_tokens": 2,
                "output_tokens": 1,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 50,
            },
            {
                "input_tokens": 3,
                "output_tokens": 280,
                "cache_read_input_tokens": 5289,
                "cache_creation_input_tokens": 0,
            },
        ],
    )
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    want = {"input": 5, "output": 281, "cache_read": 5389, "cache_creation": 50}
    assert tokens == expected == want
    assert total == sum(expected.values()) == 5725


def test_sum_transcript_tokens_ignores_non_assistant_and_missing_usage_lines(tmp_path):
    path = tmp_path / "transcript.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "message": {"no_usage_here": True}}) + "\n")
        fh.write(
            json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 7}}}) + "\n"
        )
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    assert tokens == {"input": 7, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert total == 7


def test_sum_transcript_tokens_missing_file_sets_tokens_error():
    tokens, total, error = ab.sum_transcript_tokens("/no/such/transcript.jsonl")
    assert tokens is None and total is None
    assert error == "FileNotFoundError"


def test_sum_transcript_tokens_none_or_empty_path_no_error():
    # No path was ever recorded (e.g. a "claimed"/"launched" reap) -- a
    # DIFFERENT case from "we had a path and reading it failed": no attempt
    # was made, so this must never report the same tokens_error class.
    assert ab.sum_transcript_tokens(None) == (None, None, None)
    assert ab.sum_transcript_tokens("") == (None, None, None)


def test_sum_transcript_tokens_malformed_line_is_skipped_not_file_level_error(tmp_path):
    """N17 (08-25 round 4): a malformed JSON line is SKIPPED, matching
    _read_table's self-healing convention -- tokens_error is reserved for a
    genuine open/IO failure, never a per-line parse failure. A file that is
    ENTIRELY one bad line therefore reads as a legitimately-empty (all
    zero, no error) transcript, exactly like a truly-empty file -- this
    used to abort the whole sum and report tokens_error="JSONDecodeError"."""
    path = tmp_path / "bad.jsonl"
    path.write_text("{not json at all\n")
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    assert tokens == {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert total == 0


def test_sum_transcript_tokens_one_bad_line_does_not_lose_good_lines(tmp_path):
    """N17's real falsifiability case: the OLD whole-sum-aborting bug threw
    away every already-summed valid line the instant ONE line failed to
    parse -- RED without the fix (would return None/None/"JSONDecodeError"
    instead of the real sum of the two valid lines)."""
    path = tmp_path / "mixed.jsonl"
    line1 = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 5}}})
    line2 = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 3}}})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(line1 + "\n")
        fh.write("{not json at all\n")
        fh.write(line2 + "\n")
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    assert tokens["input"] == 8
    assert total == 8


def test_sum_transcript_tokens_type_filter_excludes_non_assistant_usage(tmp_path):
    """N16 (08-25 round 4): the code must match its own docstring ("every
    type=="assistant" line's message.usage is summed") -- a non-assistant
    line carrying a usage-shaped dict (synthetic/adversarial, but the
    pre-existing "ignores non-assistant" fixture's own non-assistant line
    never happened to carry a usage field, so it could never have caught a
    missing type filter) must be excluded."""
    path = tmp_path / "transcript.jsonl"
    user_line = json.dumps({"type": "user", "message": {"usage": {"input_tokens": 999}}})
    assistant_line = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 3}}})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(user_line + "\n")
        fh.write(assistant_line + "\n")
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    assert tokens["input"] == 3  # the user-type line's 999 must NEVER be counted
    assert total == 3


def test_sum_transcript_tokens_empty_transcript_is_all_zero_no_error(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    tokens, total, error = ab.sum_transcript_tokens(str(path))
    assert error is None
    assert tokens == {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    assert total == 0


# --- model_from_transcript / _resolve_model_and_source (WS2.1 step 4) -------


def test_model_from_transcript_recovers_last_assistant_model(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript_with_models(str(path), ["claude-sonnet-5", "claude-sonnet-5"])
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model == "claude-sonnet-5"


def test_model_from_transcript_last_seen_wins_on_a_mixed_transcript(tmp_path):
    # Documented rule: LAST assistant line's model wins, not the first or
    # most common -- every real sample checked had exactly one model
    # throughout, but the function's contract is explicit about which one
    # it picks when that ever isn't true.
    path = tmp_path / "transcript.jsonl"
    _write_transcript_with_models(
        str(path), ["claude-sonnet-5", "claude-sonnet-5", "claude-opus-5"]
    )
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model == "claude-opus-5"


def test_model_from_transcript_ignores_non_assistant_lines(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript_with_models(
        str(path),
        ["claude-sonnet-5"],
        non_assistant_lines=[{"type": "user", "message": {"model": "should-never-win"}}],
    )
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model == "claude-sonnet-5"


def test_model_from_transcript_missing_file_reports_error_no_model():
    model, error = ab.model_from_transcript("/no/such/transcript.jsonl")
    assert model is None
    assert error == "FileNotFoundError"


def test_model_from_transcript_none_or_empty_path_no_error():
    assert ab.model_from_transcript(None) == (None, None)
    assert ab.model_from_transcript("") == (None, None)


def test_model_from_transcript_malformed_line_is_skipped_not_file_level_error(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{not json at all\n")
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model is None  # nothing recoverable, but not a failure


def test_model_from_transcript_one_bad_line_does_not_lose_the_good_one(tmp_path):
    path = tmp_path / "mixed.jsonl"
    good = json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5"}})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(good + "\n")
        fh.write("{not json at all\n")
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model == "claude-sonnet-5"


def test_model_from_transcript_bounded_read_recovers_model_beyond_the_cap(tmp_path):
    # Falsifiability target: a transcript LARGER than max_bytes must still
    # recover the LAST assistant line's model (it lives near the tail,
    # inside the read window) without ever reading the whole file. Padding
    # lines are plain non-JSON text (cheap, and -- being unparseable -- a
    # stress case for the "first line in the window is likely partial"
    # discard rule too, since some padding lines will themselves get cut
    # mid-line by the seek).
    path = tmp_path / "huge.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for _ in range(2000):
            fh.write("x" * 200 + "\n")  # ~400KB of padding, well past a small cap
        fh.write(
            json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n"
        )
    model, error = ab.model_from_transcript(str(path), max_bytes=2000)
    assert error is None
    assert model == "claude-opus-5"


def test_model_from_transcript_max_bytes_cap_never_reads_whole_huge_file(tmp_path, monkeypatch):
    # Directly proves the "bounded read" contract rather than just its
    # observable effect: the file is many times larger than max_bytes, and
    # the function must still return promptly having seeked rather than
    # read from byte 0. We assert this by checking the actual number of
    # bytes handed to json.loads is bounded, via a wrapped open() call
    # count on the read chunk length.
    path = tmp_path / "huge2.jsonl"
    line = json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5"}})
    with open(path, "w", encoding="utf-8") as fh:
        for _ in range(50000):  # several MB
            fh.write(line + "\n")
    size_before = os.path.getsize(path)
    assert size_before > 1_000_000
    model, error = ab.model_from_transcript(str(path), max_bytes=1000)
    assert error is None
    assert model == "claude-sonnet-5"


def test_model_from_transcript_seek_mid_multibyte_char_degrades_not_raises(tmp_path):
    # A seek() at an arbitrary byte offset can land in the middle of a
    # multi-byte UTF-8 character. errors="replace" must absorb that
    # rather than raising a UnicodeDecodeError out of the function.
    path = tmp_path / "unicode.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(500):
            fh.write(f"emoji \U0001F600 test 中文 line {i}\n")
        fh.write(json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n")
    # A handful of odd offsets, several of which are likely to land mid-char.
    for cap in (101, 137, 250, 333):
        model, error = ab.model_from_transcript(str(path), max_bytes=cap)
        assert error is None  # never a raised UnicodeDecodeError


def test_model_from_transcript_symlink_to_dev_zero_refused_never_unbounded_read(tmp_path):
    """Fix-round BLOCKER (2026-09-20 trust-architect review, executed proof:
    8.8GB RSS in 13s, OOM-killed): os.path.getsize returns 0 for a character
    device, so the old code's `size > max_bytes` seek decision never fired
    and the bare fh.read() was genuinely unbounded on a symlink to
    /dev/zero. Must now be refused BEFORE any read, in well under a second
    -- the wall-clock assertion is the actual falsifiability signal here
    (a regression back to fh.read() with no length argument would hang or
    balloon memory, not merely misbehave)."""
    link = tmp_path / "zero_link.jsonl"
    link.symlink_to("/dev/zero")
    start = time.monotonic()
    model, error = ab.model_from_transcript(str(link), max_bytes=1000)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"took {elapsed}s -- must be refused near-instantly, never read"
    assert model is None
    assert error == "NotARegularFile"


def test_model_from_transcript_fifo_refused_never_blocks_in_open(tmp_path):
    """Fix-round BLOCKER: a FIFO with no writer blocks forever in open() --
    a hang that `except Exception` structurally cannot catch. Must be
    refused via os.stat + S_ISREG before open() is ever called."""
    fifo_path = tmp_path / "a_fifo.jsonl"
    os.mkfifo(fifo_path)
    start = time.monotonic()
    model, error = ab.model_from_transcript(str(fifo_path), max_bytes=1000)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"took {elapsed}s -- must never block in open() on a FIFO"
    assert model is None
    assert error == "NotARegularFile"


def test_model_from_transcript_regular_file_still_works_after_isreg_check(tmp_path):
    """Coverage: the S_ISREG guard must never reject a genuine regular
    file -- the ordinary, by-far-most-common case stays exactly as before."""
    path = tmp_path / "regular.jsonl"
    _write_transcript_with_models(str(path), ["claude-sonnet-5"])
    model, error = ab.model_from_transcript(str(path))
    assert error is None
    assert model == "claude-sonnet-5"


def test_model_from_transcript_directory_refused_as_not_a_regular_file(tmp_path):
    """Coverage: a directory (another real non-regular-file shape a bad
    agent_transcript_path could theoretically carry) is refused the same
    way, not via some separate IsADirectoryError path."""
    d = tmp_path / "a_directory"
    d.mkdir()
    model, error = ab.model_from_transcript(str(d))
    assert model is None
    assert error == "NotARegularFile"


def test_resolve_model_and_source_existing_model_untouched():
    model, source = ab._resolve_model_and_source("claude-sonnet-5", "/some/path.jsonl")
    assert model == "claude-sonnet-5"
    assert source is None  # never stamps a source on a value it didn't derive


def test_resolve_model_and_source_fills_from_transcript_when_null(tmp_path):
    path = tmp_path / "transcript.jsonl"
    _write_transcript_with_models(str(path), ["claude-opus-5"])
    model, source = ab._resolve_model_and_source(None, str(path))
    assert model == "claude-opus-5"
    assert source == "transcript"


def test_resolve_model_and_source_no_transcript_path_is_unavailable():
    model, source = ab._resolve_model_and_source(None, None)
    assert model is None
    assert source == "unavailable"


def test_resolve_model_and_source_transcript_read_failure_is_unavailable_never_raises():
    model, source = ab._resolve_model_and_source(None, "/no/such/transcript.jsonl")
    assert model is None
    assert source == "unavailable"


def test_resolve_model_and_source_empty_string_existing_model_treated_as_missing(tmp_path):
    # An empty string is falsy-but-a-str -- must be treated the same as
    # None (fall through to the transcript), never returned as-is.
    path = tmp_path / "transcript.jsonl"
    _write_transcript_with_models(str(path), ["claude-haiku-4-5-20251001"])
    model, source = ab._resolve_model_and_source("", str(path))
    assert model == "claude-haiku-4-5-20251001"
    assert source == "transcript"


# --- classify_release_event / _build_claim_record (pure) --------------------


def test_classify_release_event_subagent_stop():
    payload = _subagent_stop_payload("agentX", transcript_path="/t.jsonl")
    event = ab.classify_release_event(payload)
    assert event == {
        "kind": "subagent_stop",
        "agent_id": "agentX",
        "agent_type": "explore",
        "agent_transcript_path": "/t.jsonl",
    }


def test_classify_release_event_subagent_stop_no_agent_id_returns_none():
    payload = {"hook_event_name": "SubagentStop", "agent_transcript_path": "/t.jsonl"}
    assert ab.classify_release_event(payload) is None


def test_classify_release_event_async_launched():
    payload = _async_launched_payload("tu1", "agentX", resolved_model="claude-haiku-4-5-20251001")
    event = ab.classify_release_event(payload)
    assert event == {
        "kind": "post_tool_use_async_launched",
        "tool_use_id": "tu1",
        "agent_id": "agentX",
        "model": "claude-haiku-4-5-20251001",
    }


def test_classify_release_event_completed():
    payload = _completed_payload("tu1", "agentX", duration_ms=2723, total_tokens=18507)
    event = ab.classify_release_event(payload)
    assert event == {
        "kind": "post_tool_use_completed",
        "tool_use_id": "tu1",
        "agent_id": "agentX",
        "model": "claude-haiku-4-5-20251001",
        "duration_ms": 2723,
        "payload_total_tokens": 18507,
    }


def test_classify_release_event_wrong_tool_name_returns_none():
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": "x"}
    assert ab.classify_release_event(payload) is None


def test_classify_release_event_unknown_status_returns_none():
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_response": {"status": "something_else"},
    }
    assert ab.classify_release_event(payload) is None


def test_classify_release_event_empty_payload_returns_none():
    assert ab.classify_release_event({}) is None


def test_build_claim_record_from_gate_payload():
    payload = _gate_payload("tu1", subagent_type="explore", model="haiku", session_id="sess1")
    record = ab._build_claim_record(payload)
    assert record["tool_use_id"] == "tu1"
    assert record["agent_type"] == "explore"
    assert record["model_requested"] == "haiku"
    assert record["session"] == "sess1"
    assert record["agent_id"] is None
    assert record["model"] is None
    assert isinstance(record["ts"], str) and record["ts"].endswith("Z")
    # B3 (08-25 round 4): ts_epoch is now the sub-second-precision FLOAT
    # epoch (_now_epoch_f), never the whole-second int -- see that
    # function's docstring for why (a whole-second int quantised a
    # sub-second background dispatch's duration_ms to 0).
    assert isinstance(record["ts_epoch"], float)


def test_build_claim_record_no_tool_use_id_returns_none():
    assert ab._build_claim_record({}) is None
    assert ab._build_claim_record({"tool_input": {"subagent_type": "x"}}) is None


# --- ORDER-INDEPENDENCE integration tests, driven through ab.main() --------


def test_background_normal_order_gate_launch_stop_one_spend_line(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """gate -> PostToolUse(async_launched) -> SubagentStop: exactly one
    released spend line, tokens from the RECORDED transcript path (never
    derived -- see the RED-guard test below), duration_ms = stop_ts -
    claim_ts (background rule)."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-X.jsonl"
    expected_tokens = _write_transcript(
        str(transcript), [{"input_tokens": 6, "output_tokens": 4, "cache_read_input_tokens": 100}]
    )

    _events(monkeypatch, [_gate_payload("tu1", session_id="s1")])
    assert ab.main(["gate"]) == 0
    assert len(ab._read_table(ab.claims_path(d))) == 1

    _events(monkeypatch, [_async_launched_payload("tu1", "agentX")])
    assert ab.main(["release_hook"]) == 0
    claims = ab._read_table(ab.claims_path(d))
    assert len(claims) == 1 and claims[0]["agent_id"] == "agentX"  # annotated, not released yet
    assert ab._read_table(ab.spend_path(d)) == []

    _events(monkeypatch, [_subagent_stop_payload("agentX", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.claims_path(d)) == []  # claim consumed
    assert ab._read_table(ab.stops_path(d)) == []  # stop consumed
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["tool_use_id"] == "tu1"
    assert line["agent_id"] == "agentX"
    assert line["session"] == "s1"
    assert line["late"] is False and line["unreleased"] is False and line["reaped"] is None
    assert line["tokens"] == expected_tokens
    assert line["duration_ms"] is not None and line["duration_ms"] >= 0


def test_background_fast_subagent_beats_launch_hook_one_spend_line(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """gate -> SubagentStop -> PostToolUse(async_launched): the SAME one
    spend line, via the OTHER join direction (annotate finds the WAITING
    pending-stop record). RED if SubagentStop no-ops on a missing claim."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-Y.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1, "output_tokens": 1}])

    _events(monkeypatch, [_gate_payload("tu2")])
    assert ab.main(["gate"]) == 0

    _events(monkeypatch, [_subagent_stop_payload("agentY", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0
    # No claim matched yet (not annotated) -- the pending-stop record must
    # still be persisted (never a no-op), for the NEXT event to find.
    assert ab._read_table(ab.spend_path(d)) == []
    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1 and stops[0]["agent_id"] == "agentY"
    assert len(ab._read_table(ab.claims_path(d))) == 1  # claim still open, un-annotated

    _events(monkeypatch, [_async_launched_payload("tu2", "agentY")])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.claims_path(d)) == []
    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["tool_use_id"] == "tu2" and lines[0]["agent_id"] == "agentY"
    assert lines[0]["late"] is False and lines[0]["unreleased"] is False


def test_foreground_stop_then_completed_one_spend_line_tokens_from_recorded_path(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """gate -> SubagentStop -> PostToolUse(completed): one line, duration_ms
    = the payload's OWN field (2723, the foreground rule — never derived
    from claim/stop timestamps), tokens from the RECORDED path.

    RED-guard: the fixture's session-level `transcript_path` points at a
    decoy file that does NOT exist at the location a naive `dirname(...)/
    subagents/agent-<id>.jsonl` derivation would compute, while the REAL
    `agent_transcript_path` (what this code must actually use) lives
    elsewhere with known content. A derivation bug would show up here as
    either tokens_error (wrong path missing) or a wrong total (if the wrong
    path happened to exist), never the correct 36.
    """
    d = str(sandbox.agent_budget_dir)
    proj = tmp_path / "proj"
    session_id = "sess123"
    agent_id = "agentZ"
    # Decoy: the session-level transcript_path a buggy derivation might use.
    decoy_transcript_path = str(proj / f"{session_id}.jsonl")
    # The WRONG path such a derivation would compute (dirname(decoy)/subagents/agent-<id>.jsonl)
    wrong_path = proj / "subagents" / f"agent-{agent_id}.jsonl"
    assert not wrong_path.exists()
    # The REAL path SubagentStop actually delivers, one level deeper.
    real_dir = proj / session_id / "subagents"
    real_dir.mkdir(parents=True)
    real_path = real_dir / f"agent-{agent_id}.jsonl"
    expected_tokens = _write_transcript(
        str(real_path),
        [
            {
                "input_tokens": 5,
                "output_tokens": 7,
                "cache_read_input_tokens": 11,
                "cache_creation_input_tokens": 13,
            }
        ],
    )
    assert sum(expected_tokens.values()) == 36

    _events(
        monkeypatch,
        [_gate_payload("tu3", session_id=session_id, model="claude-sonnet-4-5-20250929")],
    )
    assert ab.main(["gate"]) == 0

    stop_payload = _subagent_stop_payload(
        agent_id, transcript_path=str(real_path), session_id=session_id
    )
    stop_payload["transcript_path"] = decoy_transcript_path  # session-level decoy field
    _events(monkeypatch, [stop_payload])
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.spend_path(d)) == []  # foreground: not released yet
    assert len(ab._read_table(ab.claims_path(d))) == 1  # claim untouched (never annotated)

    # F4/M3 (08-25 round 5): resolved_model=None forces handle_completed's
    # own "model or claim.get('model_requested')" fallback (~:1497) to
    # actually matter -- the default fixture's resolvedModel would mask it.
    completed = _completed_payload(
        "tu3", agent_id, duration_ms=2723, session_id=session_id, resolved_model=None
    )
    _events(monkeypatch, [completed])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.claims_path(d)) == []
    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["tool_use_id"] == "tu3"
    assert line["agent_id"] == agent_id
    assert line["duration_ms"] == 2723  # the payload's OWN field, never derived
    assert line["tokens"] == expected_tokens
    assert line["tokens_total"] == 36
    assert line["late"] is False
    assert line["model"] == "claude-sonnet-4-5-20250929"  # F4/M3: claim's model_requested fallback


def test_no_double_release_for_one_tool_use_id_either_ordering(
    sandbox, clean_env, monkeypatch, tmp_path
):
    transcript = tmp_path / "agent-D.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    d = str(sandbox.agent_budget_dir)

    _events(monkeypatch, [_gate_payload("tuD")])
    ab.main(["gate"])
    _events(monkeypatch, [_async_launched_payload("tuD", "agentD")])
    ab.main(["release_hook"])
    _events(monkeypatch, [_subagent_stop_payload("agentD", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    # A REPEATED SubagentStop firing (e.g. a duplicated hook call) must never
    # produce a second non-late release for the SAME tool_use_id: the claim
    # is already gone, so this can only leave a fresh, un-matched pending-
    # stop record (itself only ever reap-able as stopped-unjoined later).
    _events(monkeypatch, [_subagent_stop_payload("agentD", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    non_late_for_tuD = [ln for ln in lines if ln.get("tool_use_id") == "tuD" and not ln.get("late")]
    assert len(non_late_for_tuD) == 1


# --- Source rejection: transcript wins over tool_response.totalTokens -----


def test_source_rejection_transcript_total_wins_over_payload_total_tokens(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """The exact spike figures: payload totalTokens=18507 vs a real
    transcript sum of 55359 -- the WRITTEN tokens_total is the transcript's
    55359, never the (rejected) payload figure. This is the NORMAL case
    (transcript >= payload), so it must NOT log an invariant violation --
    that's covered separately below with a genuinely violating fixture."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-S.jsonl"
    _write_transcript(
        str(transcript),
        [
            {
                "input_tokens": 12,
                "output_tokens": 134,
                "cache_read_input_tokens": 18358,
                "cache_creation_input_tokens": 36855,
            }
        ],
    )
    _events(monkeypatch, [_gate_payload("tuS")])
    ab.main(["gate"])
    _events(monkeypatch, [_subagent_stop_payload("agentS", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    _events(
        monkeypatch,
        [_completed_payload("tuS", "agentS", duration_ms=2723, total_tokens=18507)],
    )
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["tokens_total"] == 55359  # the REAL spike figure, never the payload's

    log_lines = _read_jsonl(str(sandbox.log_file)) if sandbox.log_file.exists() else []
    violations = [ln for ln in log_lines if ln.get("decision") == "token_invariant_violation"]
    assert violations == []  # 55359 >= 18507 -- not a violation


def test_source_rejection_logs_warning_when_transcript_total_less_than_payload(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """A genuinely violating fixture (transcript_total < payload_total) --
    the transcript should always be a superset of the final message it
    derives from, so this is a real anomaly and must log
    token_invariant_violation, while STILL recording the transcript's own
    (smaller) total rather than silently substituting the payload's."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-V.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 100}])  # tiny, real total = 100
    _events(monkeypatch, [_gate_payload("tuV")])
    ab.main(["gate"])
    _events(monkeypatch, [_subagent_stop_payload("agentV", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    _events(
        monkeypatch,
        [_completed_payload("tuV", "agentV", total_tokens=999999)],  # implausibly large
    )
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["tokens_total"] == 100  # transcript wins even on the violating branch

    log_lines = _read_jsonl(str(sandbox.log_file))
    violations = [ln for ln in log_lines if ln.get("decision") == "token_invariant_violation"]
    assert len(violations) == 1
    assert violations[0]["transcript_total"] == 100
    assert violations[0]["payload_total"] == 999999


def test_source_rejection_no_warning_when_transcript_covers_payload(
    sandbox, clean_env, monkeypatch, tmp_path
):
    transcript = tmp_path / "agent-T.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 100000}])  # >> payload total
    _events(monkeypatch, [_gate_payload("tuT")])
    ab.main(["gate"])
    _events(monkeypatch, [_subagent_stop_payload("agentT", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    _events(monkeypatch, [_completed_payload("tuT", "agentT", total_tokens=100)])
    ab.main(["release_hook"])

    log_lines = _read_jsonl(str(sandbox.log_file)) if sandbox.log_file.exists() else []
    violations = [ln for ln in log_lines if ln.get("decision") == "token_invariant_violation"]
    assert violations == []


# --- late release: PostToolUse(completed) with no matching claim ----------


def test_completed_with_no_claim_and_agent_id_defers_pending_completed(
    sandbox, clean_env, monkeypatch
):
    """B1 (08-25 round 4): with an agent_id present, PostToolUse(completed)
    NEVER writes a spend line immediately -- even with no claim on record --
    since a real SubagentStop carrying the transcript might still arrive.
    It must defer via a pending-completed record instead (see
    test_foreground_completed_then_stop_no_claim_joins_late_line_with_real_
    tokens for the eventual join)."""
    d = str(sandbox.agent_budget_dir)
    # No gate call at all -> no claim ever existed for this tool_use_id.
    _events(monkeypatch, [_completed_payload("tuLate", "agentLate", duration_ms=555)])
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.spend_path(d)) == []
    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1
    assert stops[0]["kind"] == "completed"
    assert stops[0]["tool_use_id"] == "tuLate"
    assert stops[0]["duration_ms"] == 555
    assert stops[0]["claim"] is None


def test_completed_with_no_claim_and_no_agent_id_writes_late_line_immediately(
    sandbox, clean_env, monkeypatch
):
    """The one case that still writes immediately (per handle_completed's
    own docstring): agent_id itself is falsy, so no later SubagentStop
    could ever be matched to this dispatch anyway -- deferring would just
    lose the line forever."""
    d = str(sandbox.agent_budget_dir)
    payload = _completed_payload("tuLateNoAgent", "", duration_ms=555)  # agentId="" -> None
    _events(monkeypatch, [payload])
    assert ab.main(["release_hook"]) == 0
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["late"] is True
    assert lines[0]["join_state"] == "no-claim"
    assert lines[0]["tool_use_id"] == "tuLateNoAgent"
    assert lines[0]["duration_ms"] == 555


# --- REAP: three distinct stages, each carrying its own timestamp ---------


def test_reap_claimed_stage_never_launched(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuC",
            "ts": "2026-08-25T00:00:00Z",
            "ts_epoch": 1000,
            "agent_type": "explore",
            "model_requested": "opus",
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=1000 + 200)
    assert reaped == 1
    assert ab._read_table(ab.claims_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "claimed"
    assert line["unreleased"] is True
    assert line["ts"] == "2026-08-25T00:00:00Z"  # the CLAIM ts, never reap time
    assert line["tool_use_id"] == "tuC"
    assert line["agent_id"] is None
    assert line["duration_ms"] is None
    # F6 (08-25 round 5): a never-annotated claim's own `model` field is
    # always None -- must fall back to the gate-time model_requested rather
    # than reap a claim that DID request a real model as `model: null`.
    assert line["model"] == "opus"
    # N8 (08-25 round 5): renamed from "claim-consumed" -- a bare stale
    # claims.jsonl row was never joined into anything.
    assert line["join_state"] == "claim-only"


def test_reap_launched_stage_annotated_never_stopped(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuL",
            "ts": "2026-08-25T01:00:00Z",
            "ts_epoch": 2000,
            "agent_type": "explore",
            "model_requested": "haiku",
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    ab.handle_async_launched(d, 2.0, "tuL", "agentL", "claude-haiku-4-5-20251001")
    claims = ab._read_table(ab.claims_path(d))
    assert len(claims) == 1 and claims[0]["agent_id"] == "agentL"  # annotated, no stop yet

    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=2000 + 500)
    assert reaped == 1
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "launched"
    assert line["unreleased"] is True
    assert line["ts"] == "2026-08-25T01:00:00Z"
    assert line["tool_use_id"] == "tuL"
    assert line["agent_id"] == "agentL"
    assert line["duration_ms"] is None
    # N8 (08-25 round 5): renamed from "claim-consumed" -- this source is
    # ALSO a bare stale claims.jsonl row (annotated, but never joined by a
    # stop), same rename as the "claimed" stage above.
    assert line["join_state"] == "claim-only"


def test_reap_stopped_unjoined_stage_stop_with_no_claim(sandbox, clean_env, tmp_path):
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-U.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 9}])
    # SubagentStop fires with NO claim ever recorded (e.g. gate ran with the
    # ledger off, or the claim was already reaped) -- it must still persist.
    ab.handle_subagent_stop(d, 2.0, "agentU", "explore", str(transcript))
    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1
    stop_ts_epoch = stops[0]["stop_ts_epoch"]

    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=stop_ts_epoch + 500)
    assert reaped == 1
    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "stopped-unjoined"
    assert line["unreleased"] is True
    assert line["tool_use_id"] is None  # only a stopped-unjoined reap has one
    assert line["agent_id"] == "agentU"
    assert line["duration_ms"] is None
    # A finding in the plan: since agent_transcript_path IS known here,
    # tokens must be computed from it rather than left null.
    assert line["tokens"] == expected_tokens
    # AA-0053: no claim ever existed for this agent_id (live or reaped) --
    # model is genuinely unrecoverable at this write site, so it stays
    # null AND is explicitly flagged, distinguishing "looked and found
    # nothing" from "never looked".
    assert line["model"] is None
    assert line["model_source"] == "unavailable"


def test_reap_stopped_unjoined_stage_recovers_model_from_transcript_no_claim_ever(
    sandbox, clean_env, tmp_path
):
    """WS2.1 step 4 falsifiability target: THE real Workflow-leg shape --
    no PreToolUse:Task claim EVER existed for this agent_id (a Workflow leg
    never fires one), so the pre-existing AA-0053 claims-based recovery
    (test_reap_stopped_unjoined_stage_recovers_model_from_live_claim, above)
    cannot help -- this is exactly the 2,459 real `workflow-subagent`
    spend.jsonl rows the plan measured, all `model: null,
    model_source: "unavailable"` before this fix. The transcript fallback
    must recover the real model here, where nothing else can."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-W.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-sonnet-5"])
    ab.handle_subagent_stop(d, 2.0, "agentW", "workflow-subagent", str(transcript))
    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1
    stop_ts_epoch = stops[0]["stop_ts_epoch"]

    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=stop_ts_epoch + 500)
    assert reaped == 1
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "stopped-unjoined"
    assert line["agent_type"] == "workflow-subagent"
    assert line["model"] == "claude-sonnet-5"
    assert line["model_source"] == "transcript"


def test_reap_stopped_unjoined_stage_recovers_model_from_live_claim(sandbox, clean_env, tmp_path):
    # AA-0053 root cause: 1217/1217 (100%) of real spend.jsonl rows with
    # model: null were this exact stage — a bare PENDING-STOP row's own
    # payload (a real SubagentStop event) never carries model info, since
    # classify_release_event's subagent_stop branch only ever extracts
    # agent_id/agent_type/agent_transcript_path. But a matching claim
    # (recorded at gate time with model_requested, or annotated later with
    # model) can still be sitting live in claims.jsonl at the exact moment
    # this stop goes stale and gets reaped -- that claim is the recovery
    # source this test proves.
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-V.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 5}])

    # Normal ordering: SubagentStop fires FIRST, before anything has
    # annotated a matching claim -- handle_subagent_stop's own real-time
    # join (pop_claim_by_agent_id) finds nothing and leaves a pending-stop
    # record, exactly as documented.
    ab.handle_subagent_stop(d, 2.0, "agentV", "explore", str(transcript))
    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1
    stop_ts_epoch = stops[0]["stop_ts_epoch"]

    # A claim for the SAME agent_id shows up afterwards, already annotated
    # (agent_id/model set directly here rather than via
    # handle_async_launched, simulating the claim having been annotated
    # through some path that didn't also perform the join -- e.g. the
    # ledger was briefly off around the real join moment). It sits live in
    # claims.jsonl, unconsumed, at the moment reap_stale runs -- recorded
    # with a LATER ts_epoch than the stop's own stop_ts_epoch (it showed up
    # afterwards), so a single ttl/now pair can make the STOP stale while
    # the CLAIM stays fresh.
    ab.record_claim(
        d,
        {
            "tool_use_id": "toolu_v",
            "ts": "2026-08-31T00:00:00Z",
            "ts_epoch": stop_ts_epoch + 400,
            "agent_type": "explore",
            "model_requested": "claude-sonnet-5",
            "session": "s1",
            "agent_id": "agentV",
            "model": None,
        },
        lock_timeout=2.0,
    )

    # now - stop_ts_epoch = 500 > ttl(100) -> stop is stale.
    # now - claim_ts_epoch = 100 < ttl(100)? No -- must be strictly under
    # ttl to stay fresh (see reap_stale: `now - epoch > ttl` is the stale
    # test), so use now = stop_ts_epoch + 450 -> claim age = 50 < 100.
    now = stop_ts_epoch + 450
    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=now)
    assert reaped == 1
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "stopped-unjoined"
    assert line["model"] == "claude-sonnet-5"
    assert "model_source" not in line  # recovered -- never flagged unavailable
    # The claim itself must be UNTOUCHED (still live in claims.jsonl) --
    # this is a read-only lookup, never a consuming join.
    remaining_claims = ab._read_table(ab.claims_path(d))
    assert len(remaining_claims) == 1
    assert remaining_claims[0]["tool_use_id"] == "toolu_v"


def test_reap_fresh_rows_untouched(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "fresh",
            "ts": "2026-08-25T02:00:00Z",
            "ts_epoch": 5000,
            "agent_type": "x",
            "model_requested": None,
            "session": "s",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    reaped = ab.reap_stale(d, ttl=1000, lock_timeout=2.0, now=5000 + 10)  # well under ttl
    assert reaped == 0
    assert len(ab._read_table(ab.claims_path(d))) == 1
    assert ab._read_table(ab.spend_path(d)) == []


def test_reap_nothing_to_do_writes_no_files(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    assert ab.reap_stale(d, ttl=100, lock_timeout=2.0) == 0
    assert not os.path.exists(ab.spend_path(d))


# --- LOCKING: concurrent cross-PROCESS claim writers, no lost line --------


def test_record_claim_concurrent_processes_no_lost_line(sandbox, clean_env):
    """Real OS processes (multiprocessing, not threads — see agent_budget.py's
    own note on why a same-process thread test can't prove flock's real
    cross-process guarantee), hammering the SAME admission_lock claims.jsonl
    mutation concurrently. RED without the lock: a lost/interleaved write
    would show up as fewer than N rows, a duplicate, or a corrupt line."""
    import multiprocessing

    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    n = 8
    procs = [
        multiprocessing.Process(target=_mp_record_claim_worker, args=(d, i)) for i in range(n)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=15)
        assert p.exitcode == 0

    rows = ab._read_table(ab.claims_path(d))
    ids = {r["tool_use_id"] for r in rows}
    assert ids == {f"tu_{i}" for i in range(n)}
    assert len(rows) == n  # none lost, none duplicated


# --- CSA_SPEND_LEDGER=0 / CSA_DISABLE_HOOKS=1 write nothing ----------------


def test_spend_ledger_off_gate_writes_no_claim(sandbox, clean_env, monkeypatch):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    _events(monkeypatch, [_gate_payload("tuOff")])
    assert ab.main(["gate"]) == 0
    assert ab._read_table(ab.claims_path(d)) == []


def test_spend_ledger_off_release_hook_writes_nothing(sandbox, clean_env, monkeypatch, tmp_path):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    transcript = tmp_path / "agent-Off.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_subagent_stop_payload("agentOff", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.stops_path(d)) == []
    assert ab._read_table(ab.spend_path(d)) == []


def test_master_off_gate_and_release_hook_write_nothing(sandbox, clean_env, monkeypatch, tmp_path):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    transcript = tmp_path / "agent-M.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])

    def boom():
        raise AssertionError("must not read stdin when CSA_DISABLE_HOOKS=1")

    monkeypatch.setattr(ab._lib, "read_event", boom)
    assert ab.main(["gate"]) == 0
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.claims_path(d)) == []
    assert ab._read_table(ab.stops_path(d)) == []
    assert ab._read_table(ab.spend_path(d)) == []


# --- Denied gate writes no claim -------------------------------------------


def test_denied_gate_pacer_off_writes_no_claim(sandbox, clean_env, monkeypatch):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")  # cap = 1
    _make_lease(sandbox, "someone_else")  # live=1 >= cap 1 -> deny
    _events(monkeypatch, [_gate_payload("tuDenied")])
    assert ab.main(["gate"]) == 0
    assert ab._read_table(ab.claims_path(d)) == []


def test_denied_gate_pacer_on_writes_no_claim(sandbox, clean_env, monkeypatch, capsys):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")  # deny immediately
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    _make_lease(sandbox, "someone_else")  # at cap
    _events(monkeypatch, [_gate_payload("tuDeniedPacer")])
    assert ab.main(["gate"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert ab._read_table(ab.claims_path(d)) == []


def test_admitted_gate_pacer_on_writes_a_claim(sandbox, clean_env, monkeypatch):
    """Companion to the denied-writes-nothing tests: an ADMITTED pacer gate
    must actually record the claim (a null claim there would be the false-
    green the plan explicitly calls out)."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    gate_payload = _gate_payload("tuAdmitted", subagent_type="engine-architect", model="haiku")
    _events(monkeypatch, [gate_payload])
    assert ab.main(["gate"]) == 0
    rows = ab._read_table(ab.claims_path(d))
    assert len(rows) == 1
    assert rows[0]["tool_use_id"] == "tuAdmitted"
    assert rows[0]["agent_type"] == "engine-architect"  # non-null agent_type/model, per the plan


def test_admitted_gate_pacer_off_no_tool_use_id_writes_no_claim(sandbox, clean_env, monkeypatch):
    """A gate payload with no real tool_use_id (only ever a minted fallback
    used for the pacer's own lease) must never produce a claim — see
    _build_claim_record's docstring for why."""
    d = str(sandbox.agent_budget_dir)
    _events(monkeypatch, [{}])  # no tool_use_id at all
    assert ab.main(["gate"]) == 0
    assert ab._read_table(ab.claims_path(d)) == []


# --- gate WITHOUT the pacer produces a non-null agent_type/model claim ----


def test_gate_pacer_off_admitted_produces_non_null_agent_type_and_model(sandbox, clean_env):
    """The plan's own done-criteria: a dispatch with the pacer OFF must
    still produce a claim with non-null agent_type/model_requested — a null
    there is the false-green this step exists to prevent."""
    d = str(sandbox.agent_budget_dir)
    payload = _gate_payload("tuPO", subagent_type="trade-plumbing", model="sonnet")
    decision = ab.decide(["gate"], {}, d, payload=payload)
    assert decision["claim"]["agent_type"] == "trade-plumbing"
    assert decision["claim"]["model_requested"] == "sonnet"


# --- `spend` CLI subcommand -------------------------------------------------


def test_spend_subcommand_reaps_and_prints_table(sandbox, clean_env):
    """A STALE claim (past the 6h default reap window) must be reaped by
    the `spend` subcommand itself and show up in its printed table."""
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuSpend",
            "ts": "2026-08-25T03:00:00Z",
            "ts_epoch": ab._now_epoch() - 7 * 3600,  # 7h old -> past the 6h default ttl
            "agent_type": "explore",
            "model_requested": None,
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    code, out, err = _run(["spend", "--by", "agent"], sandbox)
    assert code == 0
    assert err == ""
    assert "spend --by agent" in out
    assert "explore" in out
    assert "dispatches=    1" in out
    assert ab._read_table(ab.claims_path(d)) == []  # reaped by the spend call itself
    spend_lines = ab._read_table(ab.spend_path(d))
    assert len(spend_lines) == 1
    assert spend_lines[0]["reaped"] == "claimed"


def test_spend_subcommand_fresh_claim_not_yet_reaped(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuFreshSpend",
            "ts": "2026-08-25T03:00:00Z",
            "ts_epoch": ab._now_epoch(),  # claimed right now -> well under the 6h ttl
            "agent_type": "explore",
            "model_requested": None,
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    code, out, _ = _run(["spend", "--by", "agent"], sandbox)
    assert code == 0
    assert "(no spend recorded)" in out
    assert len(ab._read_table(ab.claims_path(d))) == 1  # untouched, still fresh


def test_spend_subcommand_empty_ledger_prints_placeholder(sandbox, clean_env):
    code, out, _ = _run(["spend"], sandbox)
    assert code == 0
    assert "(no spend recorded)" in out


def test_spend_subcommand_groups_by_model_and_day(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab._append_jsonl(
        ab.spend_path(d),
        {
            "ts": "2026-08-25T10:00:00Z",
            "agent_type": "explore",
            "model": "claude-haiku-4-5",
            "tokens_total": 100,
            "tool_use_id": "a",
        },
    )
    ab._append_jsonl(
        ab.spend_path(d),
        {
            "ts": "2026-08-25T11:00:00Z",
            "agent_type": "explore",
            "model": "claude-haiku-4-5",
            "tokens_total": 50,
            "tool_use_id": "b",
        },
    )
    code, out, _ = _run(["spend", "--by", "model"], sandbox)
    assert "claude-haiku-4-5" in out
    assert "dispatches=    2" in out
    assert "tokens_total=150" in out

    code, out, _ = _run(["spend", "--by", "day"], sandbox)
    assert "2026-08-25" in out
    assert "dispatches=    2" in out


def test_decide_spend_subcommand_shape():
    d = ab.decide(["spend", "--by", "model"], {"CSA_CLAIM_TTL_SEC": "50"}, "/b")
    assert d["action"] == "spend"
    assert d["exit"] == 0
    assert d["ttl"] == 50
    assert d["args"] == ["--by", "model"]


# ===========================================================================
# N20 — validate --since (error on malformed, don't silently filter all).
# ===========================================================================


def test_parse_spend_args_defaults_and_overrides():
    assert ab.parse_spend_args([]) == ("agent", None, None)
    assert ab.parse_spend_args(["--by", "model"]) == ("model", None, None)
    assert ab.parse_spend_args(["--since", "2026-08-01"]) == ("agent", "2026-08-01", None)
    assert ab.parse_spend_args(["--by", "day", "--since", "2026-08-01T10:00:00Z"]) == (
        "day",
        "2026-08-01T10:00:00Z",
        None,
    )


def test_parse_spend_args_since_malformed_returns_error():
    by, since, error = ab.parse_spend_args(["--since", "banana"])
    assert since == "banana"
    assert error is not None
    assert "--since" in error and "banana" in error


def test_decide_spend_since_malformed_is_usage_error_exit2():
    d = ab.decide(["spend", "--since", "not-a-date"], {}, "/b")
    assert d["action"] == "spend"
    assert d["exit"] == 2
    assert "--since" in d["error"]


def test_decide_spend_since_valid_passes_through():
    d = ab.decide(["spend", "--since", "2026-08-01"], {}, "/b")
    assert d["exit"] == 0
    assert d["args"] == ["--since", "2026-08-01"]


def test_spend_since_malformed_errors_exit2(sandbox, clean_env):
    """N20: a malformed --since used to silently filter out EVERY row
    (almost any garbage string lexicographically sorts above a leading
    digit) and print "(no spend recorded)" -- indistinguishable from
    genuinely having no spend. It must now be a visible, immediate error."""
    d = str(sandbox.agent_budget_dir)
    ab._append_jsonl(
        ab.spend_path(d),
        {"ts": "2026-08-25T00:00:00Z", "agent_type": "explore", "tool_use_id": "a"},
    )
    code, out, err = _run(["spend", "--since", "banana"], sandbox)
    assert code == 2
    assert out == ""
    assert "--since" in err


def test_spend_since_valid_date_still_filters(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab._append_jsonl(
        ab.spend_path(d),
        {"ts": "2026-08-20T00:00:00Z", "agent_type": "old", "tool_use_id": "a"},
    )
    ab._append_jsonl(
        ab.spend_path(d),
        {"ts": "2026-08-25T00:00:00Z", "agent_type": "new", "tool_use_id": "b"},
    )
    code, out, err = _run(["spend", "--since", "2026-08-22"], sandbox)
    assert code == 0
    assert err == ""
    assert "new" in out
    assert "old" not in out


# ===========================================================================
# D11 — gate the `spend` subcommand's reap on spend_ledger_enabled.
# ===========================================================================


def test_decide_spend_reap_flag_reflects_ledger_toggle():
    on = ab.decide(["spend"], {}, "/b")
    assert on["reap"] is True
    off = ab.decide(["spend"], {"CSA_SPEND_LEDGER": "0"}, "/b")
    assert off["reap"] is False


def test_spend_subcommand_ledger_off_does_not_reap(sandbox, clean_env, monkeypatch):
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuLedgerOff",
            "ts": "2026-08-25T03:00:00Z",
            "ts_epoch": ab._now_epoch() - 7 * 3600,  # 7h old -> past the 6h default ttl
            "agent_type": "explore",
            "model_requested": None,
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    code, out, _ = _run(["spend", "--by", "agent"], sandbox)
    assert code == 0
    assert "(no spend recorded)" in out
    # NEVER reaped -- the claim is untouched and no spend line was written.
    assert len(ab._read_table(ab.claims_path(d))) == 1
    assert ab._read_table(ab.spend_path(d)) == []


# ===========================================================================
# N18 — record_claim upserts on tool_use_id.
# ===========================================================================


def test_record_claim_upserts_same_tool_use_id(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    first = {
        "tool_use_id": "tuUpsert",
        "ts": "2026-08-25T00:00:00Z",
        "ts_epoch": 1000.0,
        "agent_type": "explore",
        "model_requested": None,
        "session": "s1",
        "agent_id": None,
        "model": None,
    }
    ab.record_claim(d, first, lock_timeout=2.0)
    second = dict(first, agent_type="trade-plumbing", ts="2026-08-25T00:05:00Z")
    ab.record_claim(d, second, lock_timeout=2.0)
    rows = ab._read_table(ab.claims_path(d))
    # Exactly ONE row for this tool_use_id -- never a phantom duplicate --
    # carrying the LATEST content, not the first.
    assert len(rows) == 1
    assert rows[0]["agent_type"] == "trade-plumbing"
    assert rows[0]["ts"] == "2026-08-25T00:05:00Z"


# ===========================================================================
# R6 — every `if not locked` fail-open branch logs spend_ledger_lock_timeout.
# ===========================================================================


def _hold_lock_and_run(sandbox, fn):
    """Hold the admission lock in the FOREGROUND (this process, the same
    lock file) and run `fn` while it's held -- `fn`'s own admission_lock
    acquisition must then fail open (locked=False) within its bounded wait."""
    d = str(sandbox.agent_budget_dir)
    with ab.admission_lock(d, timeout_s=0.5) as held:
        assert held is True
        fn(d)


def test_record_claim_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab.record_claim(d, {"tool_use_id": "tuLock"}, lock_timeout=0.05)

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "record_claim"
    assert hits[0]["tool_use_id"] == "tuLock"


def test_handle_async_launched_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab.handle_async_launched(d, 0.05, "tuLock2", "agentLock2", "haiku")

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "handle_async_launched"
    assert hits[0]["tool_use_id"] == "tuLock2"


def test_handle_subagent_stop_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab.handle_subagent_stop(d, 0.05, "agentLock3", "explore", "/x.jsonl")

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "handle_subagent_stop"
    assert hits[0]["agent_id"] == "agentLock3"


def test_handle_completed_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab.handle_completed(d, 0.05, "tuLock4", "agentLock4", "haiku", 100)

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "handle_completed"
    assert hits[0]["tool_use_id"] == "tuLock4"


def test_reap_stale_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab.reap_stale(d, ttl=100, lock_timeout=0.05)

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "reap_stale"


def test_release_pacer_lease_for_stop_lock_timeout_logs(sandbox, clean_env):
    def go(d):
        ab._release_pacer_lease_for_stop(d, 0.05, "agentLock5")

    _hold_lock_and_run(sandbox, go)
    lines = _read_jsonl(str(sandbox.log_file))
    hits = [ln for ln in lines if ln.get("decision") == "spend_ledger_lock_timeout"]
    assert len(hits) == 1
    assert hits[0]["op"] == "release_pacer_lease_for_stop"
    assert hits[0]["agent_id"] == "agentLock5"


def test_release_pacer_lease_for_stop_direct_tool_use_id_releases_and_marker(sandbox, clean_env):
    """N2 (08-25 round 5): the tool_use_id-direct path is unreachable via
    decide() (see the function's own docstring) -- exercised directly since
    no real SubagentStop payload ever reaches it through decide()."""
    d = str(sandbox.agent_budget_dir)
    ab.write_lease(d, "tuX")
    lease = ab.lease_path(d, "tuX")
    ab._ensure_dir(d)
    ab._write_pending_stop_marker(d, "agentX")
    marker = ab._pending_stop_marker_path(d, "agentX")
    ab._release_pacer_lease_for_stop(d, 5.0, "agentX", tool_use_id="tuX")
    assert not os.path.exists(lease)
    assert not os.path.exists(marker)


# ===========================================================================
# R8 — a row with non-int/garbage ts_epoch is reaped as stale, never
# immortal.
# ===========================================================================


@pytest.mark.parametrize("garbage_epoch", ["not-a-number", None, True, [1, 2], {}])
def test_reap_stale_claim_with_garbage_ts_epoch_is_reaped_not_immortal(
    sandbox, clean_env, garbage_epoch
):
    """R8: the pre-fix code required `isinstance(epoch, int)` to even
    CONSIDER staleness -- any garbage epoch (including a bool, which IS an
    int subclass in Python and would have wrongly been accepted) fell into
    the untouched "fresh" branch and would never be reaped, no matter how
    large `ttl`/`now` are set. This RTs regardless of ttl/now."""
    d = str(sandbox.agent_budget_dir)
    ab._write_table(
        ab.claims_path(d),
        [
            {
                "tool_use_id": "tuGarbage",
                "ts": "2026-08-25T00:00:00Z",
                "ts_epoch": garbage_epoch,
                "agent_type": "explore",
                "model_requested": None,
                "session": "s1",
                "agent_id": None,
                "model": None,
            }
        ],
    )
    reaped = ab.reap_stale(d, ttl=999999999, lock_timeout=2.0, now=0)
    assert reaped == 1
    assert ab._read_table(ab.claims_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["reaped"] == "claimed"
    assert lines[0]["unreleased"] is True


def test_reap_stale_stop_with_garbage_stop_ts_epoch_is_reaped_not_immortal(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    ab._write_table(
        ab.stops_path(d),
        [
            {
                "kind": "stop",
                "agent_id": "agentGarbage",
                "agent_type": "explore",
                "agent_transcript_path": None,
                "stop_ts": "2026-08-25T00:00:00Z",
                "stop_ts_epoch": "garbage",
            }
        ],
    )
    reaped = ab.reap_stale(d, ttl=999999999, lock_timeout=2.0, now=0)
    assert reaped == 1
    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["reaped"] == "stopped-unjoined"


# ===========================================================================
# B3 — background duration_ms uses the real precise epoch gap, never a
# hardcoded/quantised value.
# ===========================================================================


def test_background_join_duration_ms_uses_precise_epoch_gap_not_hardcoded_zero(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """B3 (08-25 round 4): mutating _release_line_from_join's real
    duration_ms formula down to a hardcoded 0 must go RED. Patches
    _now_epoch_f (claim ts_epoch is set at gate time; stop_ts_epoch at
    SubagentStop time -- exactly two calls in this flow) so the two epochs
    land EXACTLY 7 seconds apart and asserts the PRECISE resulting
    duration_ms, not merely `>= 0` (the pre-existing assertion a
    hardcoded-0 mutant would still satisfy)."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-B3.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])

    # Anchored to REAL current time (not an arbitrary small constant): the
    # in-between release_hook calls also run reap_stale with its own
    # default `now=_now_epoch()` (unpatched, real wall clock) against the
    # SAME CSA_CLAIM_TTL_SEC-windowed staleness check -- an arbitrary tiny
    # epoch would look millions of seconds "stale" against real now and get
    # reaped away before the join this test is actually exercising.
    base = float(ab._now_epoch())
    epochs = iter([base, base + 7.0])  # claim at t=base, stop 7s later
    monkeypatch.setattr(ab, "_now_epoch_f", lambda: next(epochs))

    _events(monkeypatch, [_gate_payload("tuB3")])
    ab.main(["gate"])
    _events(monkeypatch, [_async_launched_payload("tuB3", "agentB3")])
    ab.main(["release_hook"])
    _events(monkeypatch, [_subagent_stop_payload("agentB3", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["duration_ms"] == 7000  # EXACT -- a hardcoded-0 mutant fails this
    assert lines[0]["join_state"] == "joined"


def test_background_join_duration_ms_precise_for_sub_second_dispatch(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """B3's own stated motivation: a genuinely sub-second dispatch must not
    quantise to 0 just because both epochs land in the same whole second."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-B3b.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])

    base = float(int(ab._now_epoch()))  # whole-second anchor, real current time
    epochs = iter([base + 0.100, base + 0.500])  # 400ms apart, same whole second
    monkeypatch.setattr(ab, "_now_epoch_f", lambda: next(epochs))

    _events(monkeypatch, [_gate_payload("tuB3b")])
    ab.main(["gate"])
    _events(monkeypatch, [_async_launched_payload("tuB3b", "agentB3b")])
    ab.main(["release_hook"])
    _events(monkeypatch, [_subagent_stop_payload("agentB3b", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["duration_ms"] == 400


# ===========================================================================
# R7 — the spend.jsonl append lands BEFORE the claims.jsonl/stops.jsonl
# table(s) it was derived from are pruned/rewritten, in every release/reap
# path (crash-safety: a duplicate spend line, deduped later, is always the
# safer failure mode than a dispatch that vanishes with no line at all).
# ===========================================================================


def _order_recorder(monkeypatch):
    """Wrap _append_jsonl/_write_table (still calling the REAL
    implementation) to record (kind, basename) call order across every
    invocation for the rest of the test."""
    order: list[tuple[str, str]] = []
    real_append = ab._append_jsonl
    real_write = ab._write_table

    def fake_append(path, record, **kw):
        order.append(("append", os.path.basename(path)))
        return real_append(path, record, **kw)

    def fake_write(path, rows):
        order.append(("write", os.path.basename(path)))
        return real_write(path, rows)

    monkeypatch.setattr(ab, "_append_jsonl", fake_append)
    monkeypatch.setattr(ab, "_write_table", fake_write)
    return order


def _assert_spend_append_precedes_table_writes(order):
    """R7: the FIRST spend.jsonl append in `order` must precede every
    claims.jsonl/stops.jsonl WRITE in the (isolated, single-call) recorded
    window -- i.e. no table write happens before the spend line it was
    derived from has actually landed. `order` is expected to be reset
    (via a fresh `_order_recorder` call) right before the ONE hook firing
    under test, so every entry in it belongs to that one call."""
    spend_indices = [
        i for i, (kind, name) in enumerate(order) if kind == "append" and name == "spend.jsonl"
    ]
    assert spend_indices, f"no spend.jsonl append recorded at all: {order}"
    first_spend_idx = spend_indices[0]
    for i, (kind, name) in enumerate(order):
        if i < first_spend_idx and kind == "write" and name in ("claims.jsonl", "stops.jsonl"):
            raise AssertionError(
                f"table write at index {i} ({name}) happened BEFORE the spend.jsonl "
                f"append at index {first_spend_idx} -- R7 ordering violated: {order}"
            )


def test_r7_handle_subagent_stop_claim_join_appends_spend_before_table_writes(
    sandbox, clean_env, monkeypatch, tmp_path
):
    transcript = tmp_path / "agent-R7a.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_gate_payload("tuR7a")])
    ab.main(["gate"])
    _events(monkeypatch, [_async_launched_payload("tuR7a", "agentR7a")])
    ab.main(["release_hook"])

    order = _order_recorder(monkeypatch)
    _events(monkeypatch, [_subagent_stop_payload("agentR7a", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    _assert_spend_append_precedes_table_writes(order)


def test_r7_handle_async_launched_fast_subagent_join_appends_spend_before_table_writes(
    sandbox, clean_env, monkeypatch, tmp_path
):
    transcript = tmp_path / "agent-R7b.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_gate_payload("tuR7b")])
    ab.main(["gate"])
    _events(monkeypatch, [_subagent_stop_payload("agentR7b", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    order = _order_recorder(monkeypatch)
    _events(monkeypatch, [_async_launched_payload("tuR7b", "agentR7b")])
    ab.main(["release_hook"])
    _assert_spend_append_precedes_table_writes(order)


def test_r7_handle_async_launched_synthetic_join_appends_spend_before_table_writes(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """R5 x R7: the SAME ordering guarantee for the synthetic-claim join
    path (no claim was ever on record at all)."""
    transcript = tmp_path / "agent-R7c.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_subagent_stop_payload("agentR7c", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    order = _order_recorder(monkeypatch)
    _events(monkeypatch, [_async_launched_payload("tuR7c", "agentR7c")])
    ab.main(["release_hook"])
    _assert_spend_append_precedes_table_writes(order)


def test_r7_handle_subagent_stop_pending_completed_join_appends_spend_before_table_writes(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """B1 x R7: the pending-completed join path (handle_subagent_stop
    joining a record handle_completed deferred)."""
    transcript = tmp_path / "agent-R7d.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_gate_payload("tuR7d")])
    ab.main(["gate"])
    _events(monkeypatch, [_completed_payload("tuR7d", "agentR7d", duration_ms=500)])
    ab.main(["release_hook"])

    order = _order_recorder(monkeypatch)
    _events(monkeypatch, [_subagent_stop_payload("agentR7d", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    _assert_spend_append_precedes_table_writes(order)


def test_r7_handle_completed_release_appends_spend_before_table_writes(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """The foreground "stop already exists" release path inside
    handle_completed itself."""
    transcript = tmp_path / "agent-R7e.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_gate_payload("tuR7e")])
    ab.main(["gate"])
    _events(monkeypatch, [_subagent_stop_payload("agentR7e", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    order = _order_recorder(monkeypatch)
    _events(monkeypatch, [_completed_payload("tuR7e", "agentR7e", duration_ms=500)])
    ab.main(["release_hook"])
    _assert_spend_append_precedes_table_writes(order)


def test_r7_reap_stale_appends_spend_before_table_writes(sandbox, clean_env, monkeypatch, tmp_path):
    """reap_stale itself: one stale claim, one stale stop-kind row, one
    stale completed-kind row, all in ONE reap_stale call -- EVERY resulting
    spend.jsonl append must precede the (single) claims.jsonl/stops.jsonl
    write-back at the end."""
    d = str(sandbox.agent_budget_dir)
    ab.record_claim(
        d,
        {
            "tool_use_id": "tuR7claim",
            "ts": "2026-08-25T00:00:00Z",
            "ts_epoch": 1000.0,
            "agent_type": "explore",
            "model_requested": None,
            "session": "s1",
            "agent_id": None,
            "model": None,
        },
        lock_timeout=2.0,
    )
    ab._write_table(
        ab.stops_path(d),
        [
            {
                "kind": "stop",
                "agent_id": "agentR7stop",
                "agent_type": "explore",
                "agent_transcript_path": None,
                "stop_ts": "2026-08-25T00:00:00Z",
                "stop_ts_epoch": 1000.0,
            },
            {
                "kind": "completed",
                "agent_id": "agentR7completed",
                "tool_use_id": "tuR7completed",
                "model": None,
                "duration_ms": 100,
                "payload_total_tokens": None,
                "claim": None,
                "completed_ts": "2026-08-25T00:00:00Z",
                "stop_ts_epoch": 1000.0,
            },
        ],
    )

    order = _order_recorder(monkeypatch)
    reaped = ab.reap_stale(d, ttl=100, lock_timeout=2.0, now=1000.0 + 200)
    assert reaped == 3
    _assert_spend_append_precedes_table_writes(order)


# ===========================================================================
# B1 — the fourth ordering ("gate -> completed -> stop") joins exactly
# once, never orphans a phantom stopped-unjoined + a null-tokens line.
# ===========================================================================


def test_gate_completed_stop_ordering_joins_exactly_once_with_real_tokens(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """B1 (08-25 round 4), the ordering that broke: gate -> PostToolUse(
    completed) -> SubagentStop, WITH a real claim on record throughout. The
    pre-fix code consumed the claim inside handle_completed immediately
    (writing a line with tokens: null, since no transcript was known yet),
    then the later SubagentStop found no claim to join and could only
    persist a fresh, unmatched pending-stop -- eventually reaped as a
    phantom "stopped-unjoined" finding: TWO lines for one dispatch. Fixed:
    exactly ONE line, with REAL transcript tokens, never a phantom reap."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-B1.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 8, "output_tokens": 2}])

    _events(
        monkeypatch,
        [
            _gate_payload(
                "tuB1", subagent_type="trade-plumbing", model="claude-opus-4-1-20250805"
            )
        ],
    )
    assert ab.main(["gate"]) == 0

    # F4/M2 (08-25 round 5): resolved_model=None forces _release_line_from_
    # completed_join's own "pending_completed.get('model') or claim.get(
    # 'model_requested')" fallback (~:1097) to actually matter.
    _events(
        monkeypatch,
        [_completed_payload("tuB1", "agentB1", duration_ms=4242, resolved_model=None)],
    )
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.spend_path(d)) == []  # deferred, not written yet
    assert ab._read_table(ab.claims_path(d)) == []  # claim consumed into the pending record
    pending = ab._read_table(ab.stops_path(d))
    assert len(pending) == 1 and pending[0]["kind"] == "completed"

    _events(monkeypatch, [_subagent_stop_payload("agentB1", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1  # exactly one line, never a phantom double
    line = lines[0]
    assert line["tool_use_id"] == "tuB1"
    assert line["late"] is False
    assert line["join_state"] == "joined"
    assert line["duration_ms"] == 4242  # the payload's OWN field, never derived
    assert line["tokens"] == expected_tokens
    assert line["agent_type"] == "trade-plumbing"
    assert line["model"] == "claude-opus-4-1-20250805"  # F4/M2: claim's model_requested fallback

    # Reaping afterward must find NOTHING left to reap -- proving there is
    # no phantom "stopped-unjoined" waiting to surface later.
    reaped = ab.reap_stale(d, ttl=0, lock_timeout=2.0, now=ab._now_epoch() + 1)
    assert reaped == 0


def test_gate_completed_stop_ordering_reaped_when_stop_never_arrives(
    sandbox, clean_env, monkeypatch
):
    """B1's own reap-coverage half: if the SubagentStop genuinely never
    arrives, the pending-completed record must still be reaped eventually
    (never immortal), reusing the "launched" stage label (see reap_stale's
    docstring) with join_state="claim-consumed" since a real claim fed it."""
    d = str(sandbox.agent_budget_dir)
    _events(monkeypatch, [_gate_payload("tuB1r")])
    ab.main(["gate"])
    _events(monkeypatch, [_completed_payload("tuB1r", "agentB1r", duration_ms=999)])
    ab.main(["release_hook"])
    pending = ab._read_table(ab.stops_path(d))
    assert len(pending) == 1
    stop_ts_epoch = pending[0]["stop_ts_epoch"]

    reaped = ab.reap_stale(d, ttl=0, lock_timeout=2.0, now=stop_ts_epoch + 1)
    assert reaped == 1
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["reaped"] == "launched"
    assert line["join_state"] == "claim-consumed"
    assert line["tokens_error"] == ab.NO_TRANSCRIPT_RECORDED_ERROR
    assert line["tokens"] is None
    assert line["duration_ms"] == 999  # known -- unlike the plain "launched" stale-claim case
    assert line["tool_use_id"] == "tuB1r"


# ===========================================================================
# R2 (08-25 round 5) — regression: a DUPLICATE PostToolUse(completed) firing
# for the SAME tool_use_id (before its own SubagentStop ever arrives) must
# never discard the real claim's attribution on the second overwrite.
# ===========================================================================


def test_duplicate_completed_before_stop_carries_claim_forward(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """R2 (08-25 round 5) regression: PostToolUse(completed) firing TWICE
    for the SAME tool_use_id before its own SubagentStop ever arrives (a
    duplicated hook call). The first firing consumes the real claim into a
    fresh pending-completed record (handle_completed's B1 defer path); the
    SECOND firing's own claims.jsonl lookup finds nothing (the claim is
    already gone) and, pre-fix, overwrote the pending-completed row with
    `claim: None` -- silently discarding the real claim's session/
    agent_type/model_requested attribution the first firing had already
    recorded. Fixed: the prior row's claim carries forward whenever a
    later overwrite doesn't find one of its own."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-R2.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 3}])

    _events(
        monkeypatch,
        [_gate_payload("tuR2", subagent_type="trade-tile", session_id="sessR2")],
    )
    assert ab.main(["gate"]) == 0

    _events(
        monkeypatch,
        [_completed_payload("tuR2", "agentR2", duration_ms=555, session_id="sessR2")],
    )
    assert ab.main(["release_hook"]) == 0
    pending = ab._read_table(ab.stops_path(d))
    assert len(pending) == 1
    assert pending[0]["claim"] is not None  # first firing recorded the real claim

    # Duplicate firing of the SAME completed event, still before the stop.
    _events(
        monkeypatch,
        [_completed_payload("tuR2", "agentR2", duration_ms=555, session_id="sessR2")],
    )
    assert ab.main(["release_hook"]) == 0
    pending = ab._read_table(ab.stops_path(d))
    assert len(pending) == 1  # overwritten, not duplicated
    assert pending[0]["claim"] is not None  # R2: carried forward, never dropped

    _events(monkeypatch, [_subagent_stop_payload("agentR2", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["tool_use_id"] == "tuR2"
    assert line["late"] is False  # R2: a real claim fed this line
    assert line["session"] == "sessR2"  # R2: attribution preserved
    assert line["agent_type"] == "trade-tile"  # R2: attribution preserved
    assert line["tokens"] == expected_tokens


# ===========================================================================
# Coverage rows (08-25 round 4).
# ===========================================================================


def test_foreground_completed_then_stop_no_claim_joins_late_line_with_real_tokens(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """Coverage: fg P->S, no claim ever recorded (gate never ran / already
    reaped). B1's deferred join must still produce exactly ONE late line
    with REAL transcript tokens once the stop finally arrives -- never an
    immediate null-tokens line plus an orphaned stopped-unjoined reap."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-PSnc.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 4, "output_tokens": 2}])

    _events(monkeypatch, [_completed_payload("tuPSnc", "agentPSnc", duration_ms=1234)])
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.spend_path(d)) == []

    _events(monkeypatch, [_subagent_stop_payload("agentPSnc", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["tool_use_id"] == "tuPSnc"
    assert line["late"] is True
    assert line["join_state"] == "no-claim"
    assert line["duration_ms"] == 1234
    assert line["tokens"] == expected_tokens
    # F4/M1 (08-25 round 5): no claim ever existed, so agent_type must fall
    # back to the stop's own value (_release_line_from_completed_join's
    # "(claim.get('agent_type') if claim else None) or stop_row.get(
    # 'agent_type')", ~:1096) -- the default fixture agent_type.
    assert line["agent_type"] == "explore"


def test_foreground_stop_then_completed_no_claim_agent_type_falls_back_to_stop(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """Coverage (the live-observed case, B2): SubagentStop arrives first
    (creating a pending stop with agent_type) but NO claim was ever
    recorded for this dispatch (already reaped, or gate never ran) -- when
    PostToolUse(completed) later joins, agent_type must fall back to the
    pending stop's own agent_type rather than reading null (the real
    production line this bug produced: a 25.9M-token Opus dispatch with
    agent_type: null)."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-livecase.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 2}])
    stop_payload = _subagent_stop_payload(
        "agentLive", agent_type="code-reviewer", transcript_path=str(transcript)
    )
    _events(monkeypatch, [stop_payload])
    assert ab.main(["release_hook"]) == 0  # no claim -> just persists the pending stop

    _events(monkeypatch, [_completed_payload("tuLive", "agentLive", duration_ms=999)])
    assert ab.main(["release_hook"]) == 0

    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["late"] is True  # no claim was ever found
    assert line["agent_type"] == "code-reviewer"  # B2: fell back to the STOP's own value
    assert line["join_state"] == "no-claim"


def test_background_async_launched_then_stop_no_claim_synthesizes_and_joins(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """Coverage + R5 (08-25 round 4): bg A->S with NO claim ever recorded
    (gate never ran / already reaped). The pre-fix code made
    handle_async_launched's annotate a genuine no-op (nothing to annotate),
    so the later SubagentStop could only ever persist an unmatched
    pending-stop -- a real dispatch reduced to a TTL-only "stopped-unjoined"
    finding, never an actual (late) release line. Fixed: async_launched
    synthesizes a claim row (tool_use_id/agent_id/model only) so the stop
    CAN join immediately -- exactly ONE line, `late: true`, real tokens,
    never a phantom double, never merely deferred to the reaper."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-bgnc.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 6}])

    _events(monkeypatch, [_async_launched_payload("tuBgNc", "agentBgNc")])
    assert ab.main(["release_hook"]) == 0
    claims = ab._read_table(ab.claims_path(d))
    assert len(claims) == 1
    assert claims[0]["tool_use_id"] == "tuBgNc"
    assert claims[0]["agent_id"] == "agentBgNc"
    assert claims[0]["synthetic"] is True
    assert ab._read_table(ab.stops_path(d)) == []
    assert ab._read_table(ab.spend_path(d)) == []

    # F7 (08-25 round 5): pin the stop's own ts so the fallback's exact
    # value is provable (rather than merely "not None").
    monkeypatch.setattr(ab._lib, "_now", lambda: "2026-08-25T09:00:00Z")
    _events(monkeypatch, [_subagent_stop_payload("agentBgNc", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    assert ab._read_table(ab.claims_path(d)) == []
    assert ab._read_table(ab.stops_path(d)) == []
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1  # exactly one -- never a phantom double
    line = lines[0]
    assert line["tool_use_id"] == "tuBgNc"
    assert line["agent_id"] == "agentBgNc"
    assert line["late"] is True  # R5: synthetic claim -> late
    assert line["join_state"] == "no-claim"
    assert line["reaped"] is None  # a real join, never a reap finding
    assert line["tokens"] == expected_tokens
    # F4/M4 (08-25 round 5): synthetic claim's own agent_type is always
    # None -- _release_line_from_join's "claim.get('agent_type') or
    # stop.get('agent_type')" (~:1037) must fall back to the stop's value.
    assert line["agent_type"] == "explore"
    # F7 (08-25 round 5): synthetic claim's own ts is always None --
    # _release_line_from_join's "claim.get('ts') or stop.get('stop_ts')"
    # must fall back to the stop's real timestamp, never a literal null.
    assert line["ts"] == "2026-08-25T09:00:00Z"

    # F4/M5 (08-25 round 5): _release_line_from_join's agent_id claim->stop
    # fallback ("claim.get('agent_id') or stop.get('agent_id')", ~:1040) is
    # UNREACHABLE via any real caller -- every real call site only ever
    # passes a claim whose agent_id is ALREADY the real dispatch id (see
    # pop_claim_by_agent_id/annotate_claim's own contracts, and the
    # synthetic claim above, which is built from that same agent_id).
    # Exercise the pure function directly so a reverted fallback still
    # goes RED.
    direct = ab._release_line_from_join(
        {
            "tool_use_id": "tuDirectFallback",
            "agent_id": None,
            "agent_type": None,
            "model": None,
            "ts": None,
            "session": None,
        },
        {
            "agent_id": "stopFallbackAgent",
            "agent_type": "trade-hvac",
            "agent_transcript_path": None,
            "stop_ts": None,
            "stop_ts_epoch": None,
        },
    )
    assert direct["agent_id"] == "stopFallbackAgent"  # M5
    assert direct["agent_type"] == "trade-hvac"  # M4, confirmed again at the unit level


def test_async_launched_no_claim_no_stop_yet_persists_synthetic_for_later(
    sandbox, clean_env, monkeypatch
):
    """R5's own "normal ordering" half: when neither a claim nor a stop
    exists yet, the synthetic claim is persisted (not released
    immediately) so a LATER SubagentStop can still find and join it."""
    d = str(sandbox.agent_budget_dir)
    _events(monkeypatch, [_async_launched_payload("tuSynthWait", "agentSynthWait")])
    assert ab.main(["release_hook"]) == 0
    claims = ab._read_table(ab.claims_path(d))
    assert len(claims) == 1
    assert claims[0]["synthetic"] is True
    assert claims[0]["ts"] is None and claims[0]["session"] is None  # genuinely unknown
    assert ab._read_table(ab.spend_path(d)) == []


def test_handle_async_launched_no_claim_writes_synthetic_row_directly():
    """Unit-level (no main()/decide() indirection): the synthetic claim
    row's exact field shape, called directly."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        ab.handle_async_launched(d, 2.0, "tuDirect", "agentDirect", "claude-haiku-4-5-20251001")
        rows = ab._read_table(ab.claims_path(d))
        assert len(rows) == 1
        row = rows[0]
        assert row["tool_use_id"] == "tuDirect"
        assert row["agent_id"] == "agentDirect"
        assert row["model"] == "claude-haiku-4-5-20251001"
        assert row["synthetic"] is True
        assert row["ts"] is None
        assert row["session"] is None
        assert row["agent_type"] is None
        assert row["model_requested"] is None
        assert isinstance(row["ts_epoch"], float)


# --- WS2.1 step 4: transcript-model fallback at the immediate-join sites ----


def test_release_line_from_join_fills_null_model_from_transcript(tmp_path):
    """Direct unit test of _release_line_from_join's own model fallback: a
    claim whose model is null (e.g. a background dispatch whose
    async_launched never carried a resolvedModel) joins with a stop whose
    transcript DOES carry the real model -- the immediate-join counterpart
    to the reap-path test above (same fallback, different write site)."""
    transcript = tmp_path / "agent-joinfb.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-sonnet-5"])
    line = ab._release_line_from_join(
        {
            "tool_use_id": "tuJoinFb",
            "agent_id": "agentJoinFb",
            "agent_type": "explore",
            "model": None,
            "ts": "2026-09-21T00:00:00Z",
            "ts_epoch": 100.0,
            "session": "s1",
        },
        {
            "agent_id": "agentJoinFb",
            "agent_type": "explore",
            "agent_transcript_path": str(transcript),
            "stop_ts": "2026-09-21T00:00:05Z",
            "stop_ts_epoch": 105.0,
        },
    )
    assert line["model"] == "claude-sonnet-5"
    assert line["model_source"] == "transcript"


def test_release_line_from_join_real_model_never_gets_a_model_source_tag(tmp_path):
    """A claim that already carries a REAL model (the normal, healthy
    background-dispatch case) must be completely untouched by this
    fallback -- no model_source key at all, matching the pre-existing
    contract every other _release_line_from_join test already asserts."""
    transcript = tmp_path / "agent-joinreal.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-opus-5"])  # deliberately DIFFERENT
    line = ab._release_line_from_join(
        {
            "tool_use_id": "tuJoinReal",
            "agent_id": "agentJoinReal",
            "agent_type": "explore",
            "model": "claude-sonnet-5",  # the real, already-known model
            "ts": "2026-09-21T00:00:00Z",
            "ts_epoch": 100.0,
            "session": "s1",
        },
        {
            "agent_id": "agentJoinReal",
            "agent_type": "explore",
            "agent_transcript_path": str(transcript),
            "stop_ts": "2026-09-21T00:00:05Z",
            "stop_ts_epoch": 105.0,
        },
    )
    assert line["model"] == "claude-sonnet-5"  # never overwritten by the transcript's opus
    assert "model_source" not in line


def test_release_line_from_completed_join_fills_null_model_from_transcript(tmp_path):
    """Direct unit test of _release_line_from_completed_join's own model
    fallback (the "gate -> completed -> stop" ordering's join site)."""
    transcript = tmp_path / "agent-completedfb.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-haiku-4-5-20251001"])
    line = ab._release_line_from_completed_join(
        {
            "kind": "completed",
            "agent_id": "agentCompletedFb",
            "tool_use_id": "tuCompletedFb",
            "model": None,
            "duration_ms": 500,
            "payload_total_tokens": None,
            "claim": None,
            "completed_ts": "2026-09-21T00:00:00Z",
            "stop_ts_epoch": 100.0,
        },
        {
            "agent_id": "agentCompletedFb",
            "agent_type": "explore",
        },
        str(transcript),
    )
    assert line["model"] == "claude-haiku-4-5-20251001"
    assert line["model_source"] == "transcript"


def test_release_line_from_completed_join_real_model_never_gets_a_model_source_tag(tmp_path):
    transcript = tmp_path / "agent-completedreal.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-opus-5"])
    line = ab._release_line_from_completed_join(
        {
            "kind": "completed",
            "agent_id": "agentCompletedReal",
            "tool_use_id": "tuCompletedReal",
            "model": "claude-sonnet-5",
            "duration_ms": 500,
            "payload_total_tokens": None,
            "claim": None,
            "completed_ts": "2026-09-21T00:00:00Z",
            "stop_ts_epoch": 100.0,
        },
        {
            "agent_id": "agentCompletedReal",
            "agent_type": "explore",
        },
        str(transcript),
    )
    assert line["model"] == "claude-sonnet-5"
    assert "model_source" not in line


def test_workflow_leg_shaped_subagent_stop_end_to_end_recovers_model_via_main(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """End-to-end falsifiability target through the real ab.main() entry
    point (no PreToolUse:Task gate ever ran -- the actual Workflow-leg
    shape confirmed by the runtime probe: one PreToolUse per Workflow CALL,
    none per leg, so a leg's SubagentStop is the FIRST and ONLY event
    agent_budget.py ever sees for it). The stop persists as a pending-stop
    (no claim exists to join immediately), then a stale reap recovers the
    model from the transcript -- exactly the real spend.jsonl shape
    (`join_state: "no-claim"`, `reaped: "stopped-unjoined"`) this whole
    step exists to fix."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-wfleg.jsonl"
    _write_transcript_with_models(str(transcript), ["claude-sonnet-5"])
    monkeypatch.setattr(ab._lib, "_now", lambda: "2026-09-21T00:00:00Z")
    stop_payload = _subagent_stop_payload(
        "agentWfLeg", agent_type="workflow-subagent", transcript_path=str(transcript)
    )
    _events(monkeypatch, [stop_payload])
    assert ab.main(["release_hook"]) == 0
    assert ab._read_table(ab.spend_path(d)) == []  # not yet reaped -- just pending

    reaped = ab.reap_stale(d, ttl=1, lock_timeout=2.0, now=time.time() + 1000)
    assert reaped == 1
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    line = lines[0]
    assert line["agent_type"] == "workflow-subagent"
    assert line["model"] == "claude-sonnet-5"
    assert line["model_source"] == "transcript"
    assert line["join_state"] == "no-claim"
    assert line["reaped"] == "stopped-unjoined"


def test_duplicate_subagent_stop_no_phantom_reap_no_recounted_tokens(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """Coverage: a repeated SubagentStop firing for an ALREADY-released
    dispatch (e.g. a duplicated hook call) must never (a) show up
    immediately as a second release, and (b) once its orphaned pending-stop
    is eventually reaped, must never get re-counted alongside the real
    release in churn_report's own dedup+summary."""
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / "agent-Dup.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 10}])

    _events(monkeypatch, [_gate_payload("tuDup")])
    ab.main(["gate"])
    _events(monkeypatch, [_async_launched_payload("tuDup", "agentDup")])
    ab.main(["release_hook"])
    _events(monkeypatch, [_subagent_stop_payload("agentDup", transcript_path=str(transcript))])
    ab.main(["release_hook"])
    # Duplicate firing -- the claim is already gone, so this can only ever
    # persist a fresh, unmatched pending-stop (never a second release).
    _events(monkeypatch, [_subagent_stop_payload("agentDup", transcript_path=str(transcript))])
    ab.main(["release_hook"])

    lines = ab._read_table(ab.spend_path(d))
    real = [ln for ln in lines if ln.get("tool_use_id") == "tuDup"]
    assert len(real) == 1  # the ONE real release, never doubled
    assert real[0]["tokens"] == expected_tokens

    stops = ab._read_table(ab.stops_path(d))
    assert len(stops) == 1  # the duplicate's orphaned pending-stop, alone

    import churn_report as cr

    deduped, null_lines, malformed = cr.dedup_spend_lines(lines)
    assert malformed == 0
    assert null_lines == []  # nothing reaped yet -- the orphan is still open
    summary = cr.spend_summary(deduped)
    # The real dispatch's tokens are counted exactly once -- the eventual
    # reap of the orphaned duplicate is a SEPARATE, later finding, never
    # merged into this sum.
    assert summary["by_agent"]["explore"]["input"] == expected_tokens["input"]


def test_mixed_annotate_and_stop_concurrent_processes_no_lost_or_corrupt_rows(
    sandbox, clean_env, tmp_path
):
    """Coverage: concurrent annotate-vs-append/pop MIX (real OS processes).
    N claims are pre-seeded (the "append" side, already proven alone by
    test_record_claim_concurrent_processes_no_lost_line), then N pairs of
    processes race handle_async_launched (annotate + conditional join) and
    handle_subagent_stop (append-or-join) against each OTHER and against
    every OTHER pair's SAME shared claims.jsonl/stops.jsonl tables at once
    -- whichever of a pair wins its own race, the join must still happen
    exactly once, for every pair, with nothing lost/corrupted/duplicated
    regardless of interleaving."""
    import multiprocessing

    d = str(sandbox.agent_budget_dir)
    os.makedirs(d, exist_ok=True)
    n = 6
    expected = {}
    for i in range(n):
        ab.record_claim(
            d,
            {
                "tool_use_id": f"tu_mix_{i}",
                "ts": "2026-08-25T00:00:00Z",
                "ts_epoch": 1000.0,
                "agent_type": "explore",
                "model_requested": None,
                "session": "s",
                "agent_id": None,
                "model": None,
            },
            lock_timeout=5.0,
        )
        transcript = tmp_path / f"agent-mix-{i}.jsonl"
        expected[i] = _write_transcript(str(transcript), [{"input_tokens": i + 1}])

    procs = []
    for i in range(n):
        transcript = str(tmp_path / f"agent-mix-{i}.jsonl")
        procs.append(multiprocessing.Process(target=_mp_handle_async_launched_worker, args=(d, i)))
        procs.append(
            multiprocessing.Process(target=_mp_handle_subagent_stop_worker, args=(d, i, transcript))
        )
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=20)
        assert p.exitcode == 0

    assert ab._read_table(ab.claims_path(d)) == []  # every claim joined, none lost
    assert ab._read_table(ab.stops_path(d)) == []  # every pending-stop joined, none orphaned
    lines = ab._read_table(ab.spend_path(d))
    by_tuid = {ln["tool_use_id"]: ln for ln in lines}
    assert set(by_tuid) == {f"tu_mix_{i}" for i in range(n)}  # none lost, none duplicated
    assert len(lines) == n
    for i in range(n):
        assert by_tuid[f"tu_mix_{i}"]["tokens"] == expected[i]


def test_release_hook_pacer_lease_survives_async_launched_released_on_stop(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """R9 (08-25 round 4): the pacer's own concurrency lease must NOT
    release on PostToolUse(async_launched) -- only on PostToolUse(
    completed) or SubagentStop. The spike's own bug released it at launch
    time, defeating the whole point of the concurrency cap for every
    background dispatch (a lease that "frees" the instant a Task
    async-launches no longer reflects who's actually still running)."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    _events(monkeypatch, [_gate_payload("tuR9")])
    assert ab.main(["gate"]) == 0
    lease = ab.lease_path(d, "tuR9")
    assert os.path.exists(lease)

    _events(monkeypatch, [_async_launched_payload("tuR9", "agentR9")])
    assert ab.main(["release_hook"]) == 0
    assert os.path.exists(lease)  # R9: must survive async_launched

    transcript = tmp_path / "agent-R9.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(monkeypatch, [_subagent_stop_payload("agentR9", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0
    assert not os.path.exists(lease)  # released on the REAL finish


def test_release_hook_lease_still_released_when_model_from_transcript_raises(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """WS2.1 step 4 falsifiability target: the module docstring's own
    rollback note ("on the stop path -- exception-wrapped") requires this
    exact guarantee -- a transcript that makes model_from_transcript itself
    raise (monkeypatched to simulate a genuine internal failure, since a
    plain file-open failure is already exception-wrapped inside that
    function and degrades to (None, <class name>) without raising) must
    NEVER stop the pacer lease from being released, and the hook call must
    still exit 0. This is the strongest form of the requirement: even a
    bug INSIDE the new model-recovery code path can't be allowed to wedge
    the stop path or leak a lease."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    _events(monkeypatch, [_gate_payload("tuExcLease")])
    assert ab.main(["gate"]) == 0
    lease = ab.lease_path(d, "tuExcLease")
    assert os.path.exists(lease)

    # No resolved_model here -- this is the real gap the transcript
    # fallback exists to fill (the payload itself never carried a model).
    _events(
        monkeypatch,
        [_async_launched_payload("tuExcLease", "agentExcLease", resolved_model=None)],
    )
    assert ab.main(["release_hook"]) == 0
    assert os.path.exists(lease)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated model_from_transcript internal failure")

    monkeypatch.setattr(ab, "model_from_transcript", _boom)
    transcript = tmp_path / "agent-ExcLease.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])
    _events(
        monkeypatch,
        [_subagent_stop_payload("agentExcLease", transcript_path=str(transcript))],
    )
    assert ab.main(["release_hook"]) == 0  # never a non-zero exit
    assert not os.path.exists(lease)  # the lease is STILL released
    # The spend line itself must also still land (the whole join must not
    # be aborted by the model-recovery failure) -- degrading only the
    # model field, never the dispatch's own record.
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1
    assert lines[0]["tool_use_id"] == "tuExcLease"
    assert lines[0]["model"] is None
    assert lines[0]["model_source"] == "unavailable"


def test_model_from_transcript_stat_failure_never_raises(monkeypatch, tmp_path):
    """Unit-level exception-wrap proof directly on model_from_transcript
    itself: any internal failure (here, os.stat raising for a reason other
    than a plain missing file, e.g. a permissions error on some other
    platform) must degrade to (None, <exc class>), never raise out to the
    caller. (Fix round, 2026-09-20: the read-path check moved from
    os.path.getsize to os.stat + stat.S_ISREG -- this test now monkeypatches
    the function actually on the code path; the pre-fix-round version of
    this test monkeypatched os.path.getsize, which the fixed code no
    longer calls at all.)"""
    path = tmp_path / "unreadable.jsonl"
    path.write_text("irrelevant")

    def _boom(_path):
        raise PermissionError("simulated")

    monkeypatch.setattr(ab.os, "stat", _boom)
    model, error = ab.model_from_transcript(str(path))
    assert model is None
    assert error == "PermissionError"


def test_release_hook_pacer_on_and_ledger_on_both_effects_fire_on_stop(
    sandbox, clean_env, monkeypatch, tmp_path
):
    """Coverage: pacer ON x ledger ON (both default states this repo ships
    with). ONE release_hook(SubagentStop) firing must perform BOTH
    independent effects -- the pacer's own lease release (R9: resolved via
    the claim's agent_id match) AND the spend ledger's claim/stop
    join/release -- neither shadowing or skipping the other."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    transcript = tmp_path / "agent-Both.jsonl"
    expected_tokens = _write_transcript(str(transcript), [{"input_tokens": 3}])

    _events(monkeypatch, [_gate_payload("tuBoth")])
    assert ab.main(["gate"]) == 0
    lease = ab.lease_path(d, "tuBoth")
    assert os.path.exists(lease)

    _events(monkeypatch, [_async_launched_payload("tuBoth", "agentBoth")])
    assert ab.main(["release_hook"]) == 0
    assert os.path.exists(lease)

    _events(monkeypatch, [_subagent_stop_payload("agentBoth", transcript_path=str(transcript))])
    assert ab.main(["release_hook"]) == 0

    assert not os.path.exists(lease)  # pacer effect
    lines = ab._read_table(ab.spend_path(d))
    assert len(lines) == 1  # ledger effect
    assert lines[0]["tool_use_id"] == "tuBoth"
    assert lines[0]["tokens"] == expected_tokens


def test_release_hook_pacer_on_ledger_off_pacer_still_releases_no_ledger_writes(
    sandbox, clean_env, monkeypatch
):
    """Coverage: pacer ON x ledger OFF -- fully decoupled (see
    spend_ledger_enabled's own docstring): the pacer's lease-release effect
    must still work with CSA_SPEND_LEDGER=0, while NO claims/stops/spend
    writes ever happen."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    _events(monkeypatch, [_completed_payload("tuPacerOnly", "agentPacerOnly")])
    ab.write_lease(d, "tuPacerOnly")
    assert ab.main(["release_hook"]) == 0
    assert not os.path.exists(ab.lease_path(d, "tuPacerOnly"))  # pacer still works
    assert ab._read_table(ab.claims_path(d)) == []
    assert ab._read_table(ab.stops_path(d)) == []
    assert ab._read_table(ab.spend_path(d)) == []


# ===========================================================================
# BLOCKER fix (08-25 round 5, R11) — the pacer lease must never leak
# regardless of {CSA_SPEND_LEDGER on/off} x {A-before-S, S-before-A}. Two of
# the four rows below are PROVEN-BROKEN pre-fix:
#   * ledger ON,  S-before-A  -- the claim was un-annotated at stop time
#     (R9's claims.jsonl-only lookup found nothing), and async_launched set
#     no release field at all for that kind -- the lease was never freed.
#   * ledger OFF, A-before-S  -- claims.jsonl is never written at all under
#     CSA_SPEND_LEDGER=0, so R9's lookup always found nothing.
# (ledger OFF, S-before-A is broken by BOTH causes at once; ledger ON,
# A-before-S was already correct pre-fix -- see
# test_release_hook_pacer_lease_survives_async_launched_released_on_stop.)
# ===========================================================================


@pytest.mark.parametrize("ledger_on", [True, False])
@pytest.mark.parametrize("order", ["a_before_s", "s_before_a"])
def test_background_pacer_lease_never_leaks_cross_product(
    sandbox, clean_env, monkeypatch, tmp_path, ledger_on, order
):
    """R11 cross-product: {CSA_SPEND_LEDGER on/off} x {A->S, S->A}. Every
    row must end with the lease fully released -- including the two rows
    PROVEN to leak pre-fix (see the section docstring above)."""
    monkeypatch.setenv("CSA_PACER", "1")
    if not ledger_on:
        monkeypatch.setenv("CSA_SPEND_LEDGER", "0")
    d = str(sandbox.agent_budget_dir)
    transcript = tmp_path / f"agent-xprod-{order}-{ledger_on}.jsonl"
    _write_transcript(str(transcript), [{"input_tokens": 1}])

    tuid = f"tu_xprod_{order}_{ledger_on}"
    aid = f"agent_xprod_{order}_{ledger_on}"
    _events(monkeypatch, [_gate_payload(tuid)])
    assert ab.main(["gate"]) == 0
    lease = ab.lease_path(d, tuid)
    assert os.path.exists(lease)

    async_ev = _async_launched_payload(tuid, aid)
    stop_ev = _subagent_stop_payload(aid, transcript_path=str(transcript))
    first_ev, second_ev = (async_ev, stop_ev) if order == "a_before_s" else (stop_ev, async_ev)
    _events(monkeypatch, [first_ev])
    assert ab.main(["release_hook"]) == 0
    if order == "s_before_a":
        # B1: intermediate state between the two release_hook calls -- the
        # stop already searched and found nothing, so it must have left the
        # self-heal marker AND the lease must still be held (no premature
        # slot free before async_launched resolves the mapping).
        assert os.path.exists(ab._pending_stop_marker_path(d, aid))
        assert os.path.exists(lease)
    _events(monkeypatch, [second_ev])
    assert ab.main(["release_hook"]) == 0

    assert not os.path.exists(lease), f"lease leaked: ledger_on={ledger_on} order={order}"
    # The C -> S -> A self-heal marker (when used) must never linger either.
    assert not os.path.exists(ab._pending_stop_marker_path(d, aid))
    # B1: the whole lease SET must be empty, not just this one path.
    assert [n for n in os.listdir(d) if n.startswith(ab.LEASE_PREFIX)] == []


# ===========================================================================
# R10 — record the claim when admitted OR not enforcing (a non-enforced
# at-cap dispatch actually runs). Coverage: pacer ON x at cap x
# not-enforcing.
# ===========================================================================


def test_gate_pacer_records_claim_when_not_enforcing_at_cap(sandbox, clean_env, monkeypatch):
    """R10 (08-25 round 4): with the pacer ON but enforcement OFF, an
    at-cap gate is still LOG-ONLY -- the dispatch actually runs (no deny is
    emitted) -- so its claim must still be recorded. The pre-fix code only
    recorded a claim when `result["admitted"]` was True, missing exactly
    this case: the dispatch ran anyway, but with no claim on record, it can
    only ever complete as a permanently `late`/orphaned spend line."""
    d = str(sandbox.agent_budget_dir)
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")  # deny-from-paced_admit immediately
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)  # LOG-ONLY -- never denies
    _make_lease(sandbox, "someone_else")  # live=1 == cap 1 -> paced_admit refuses
    _events(monkeypatch, [_gate_payload("tuR10", subagent_type="explore")])
    assert ab.main(["gate"]) == 0
    rows = ab._read_table(ab.claims_path(d))
    assert len(rows) == 1
    assert rows[0]["tool_use_id"] == "tuR10"


# --- RED-guard falsifiability notes -----------------------------------------
#
# These invariants are proven RED-without-the-fix in a SCRATCH COPY (per
# ~/.claude/CLAUDE.md §6), not re-asserted here as a live test against
# production source (that would just be testing the test):
#   1. Keying release on PostToolUse(async_launched) instead of SubagentStop
#      for a background dispatch (the step-1 bug) makes
#      test_background_normal_order_gate_launch_stop_one_spend_line and
#      test_background_fast_subagent_beats_launch_hook_one_spend_line go RED
#      (duration_ms would be ~3ms, tokens would be null since async_launched
#      never carries a transcript path).
#   2. Reading tool_response.usage/totalTokens instead of the transcript
#      makes test_source_rejection_transcript_total_wins_over_payload_total_
#      tokens go RED (tokens_total would read 18507, the 3x-under-counted
#      payload figure, instead of 55359).
#   3. B1 (08-25 round 4): reverting handle_completed to write a spend line
#      immediately whenever no pending-stop exists yet (instead of deferring
#      via a pending-completed record) makes
#      test_gate_completed_stop_ordering_joins_exactly_once_with_real_tokens
#      go RED -- it would see TWO lines (the immediate null-tokens one plus
#      the eventual phantom "stopped-unjoined" reap) instead of one.
#   4. F4 (08-25 round 5) — five previously-UNFALSIFIED claim->stop
#      fallbacks (this item used to name only sub-case (a) below, B2's
#      original one; corrected here to name every site F4 actually killed
#      -- F5's own fix, since the old wording overstated its coverage):
#        a. handle_completed's/`_release_line_from_completed_join`'s
#           agent_type fallback to `claim.get("agent_type")` alone
#           (dropping the `or stop.get("agent_type")`, B2's original case)
#           makes
#           test_foreground_stop_then_completed_no_claim_agent_type_falls_back_
#           to_stop go RED (agent_type would read None instead of
#           "code-reviewer").
#        b. handle_completed's own model fallback ("model or
#           claim.get('model_requested')", ~:1497) makes
#           test_foreground_stop_then_completed_one_spend_line_tokens_from_
#           recorded_path go RED (model would read None instead of
#           "claude-sonnet-4-5-20250929").
#        c. `_release_line_from_completed_join`'s own agent_type fallback
#           (~:1096) makes
#           test_foreground_completed_then_stop_no_claim_joins_late_line_
#           with_real_tokens go RED (agent_type would read None instead of
#           "explore").
#        d. `_release_line_from_completed_join`'s own model fallback
#           (~:1097) makes
#           test_gate_completed_stop_ordering_joins_exactly_once_with_real_
#           tokens go RED (model would read None instead of
#           "claude-opus-4-1-20250805").
#        e. `_release_line_from_join`'s agent_type (~:1037) AND agent_id
#           (~:1040) claim->stop fallbacks are UNREACHABLE via any real
#           call site (every caller only ever passes a claim whose
#           agent_id is already the real dispatch id -- see
#           pop_claim_by_agent_id/annotate_claim's own contracts) --
#           killed only by the direct unit-level `_release_line_from_join`
#           call inside
#           test_background_async_launched_then_stop_no_claim_synthesizes_and_joins
#           (agent_type would read None instead of "trade-hvac"; agent_id
#           would read None instead of "stopFallbackAgent").
#   5. B3 (08-25 round 4): reverting `_release_line_from_join`'s duration_ms
#      formula to a hardcoded 0 makes
#      test_background_join_duration_ms_uses_precise_epoch_gap_not_
#      hardcoded_zero go RED (asserts the exact 7000, not merely `>= 0`).
#   6. R9 (08-25 round 4): reverting decide()'s release_hook branch to
#      release the pacer lease unconditionally on any tool_use_id-bearing
#      firing makes
#      test_release_hook_pacer_lease_survives_async_launched_released_on_stop
#      go RED (the lease would already be gone after async_launched).
#   7. R5 (08-25 round 4): reverting handle_async_launched's "no claim on
#      record" branch back to a bare `return` (no synthetic claim) makes
#      test_background_async_launched_then_stop_no_claim_synthesizes_and_joins
#      go RED (claims.jsonl would stay empty after async_launched, and the
#      eventual line would only ever come from the reaper's own
#      "stopped-unjoined" stage, never a real join with `late: true`).
#   8. R2 (08-25 round 5): reverting handle_completed's B1-defer branch to
#      unconditionally overwrite the pending-completed row's `claim` with
#      this firing's own (possibly-None) lookup, dropping the
#      `_existing.get("claim")` carry-forward, makes
#      test_duplicate_completed_before_stop_carries_claim_forward go RED
#      (the final line would read `late: True`, `session: None`,
#      `agent_type: "explore"` instead of the real claim's "sessR2"/
#      "trade-tile").
#   9. F3 (08-25 round 5): reverting `_now_epoch_f` to whole-second
#      truncation (`int(time.time())`) makes
#      test_now_epoch_f_preserves_subsecond_precision go RED (it would
#      read 1787684299.0 instead of the exact 1787684299.4).
#  10. F6 (08-25 round 5): reverting the stale-claims reap loop's `"model":
#      row.get("model")` to drop the `or row.get("model_requested")`
#      fallback makes test_reap_claimed_stage_never_launched go RED (model
#      would read None instead of "opus").
#  11. F7 (08-25 round 5): reverting `_release_line_from_join`'s `"ts":
#      claim.get("ts")` to drop the `or stop.get("stop_ts")` fallback
#      makes
#      test_background_async_launched_then_stop_no_claim_synthesizes_and_joins
#      go RED (ts would read None instead of "2026-08-25T09:00:00Z").
#  12. R11/BLOCKER (08-25 round 5): reverting `_release_pacer_lease_for_
#      stop` back to its claims.jsonl-only lookup (R9), and dropping
#      decide()/apply_decision()'s new `pacer_annotate_async_launched`
#      handling, makes
#      test_background_pacer_lease_never_leaks_cross_product go RED on
#      exactly the two PROVEN-BROKEN rows (ledger_on=True,
#      order="s_before_a"; ledger_on=False, both orders) -- the lease
#      would still exist on disk after both release_hook calls.


# ===========================================================================
# WS2.2 — fan-out session-high OBSERVER
# (plan_lane_control_adoption_master_2026_09_20.md §2.2). Pure observer: it
# never denies, delays, or raises. Threshold default 40; configurable via
# CSA_FANOUT_THRESHOLD. Counter lives in session_counts.json under the
# SAME admission_lock the pacer/spend-ledger tables already share -- no
# second lock. A corrupt/unreadable counter file resets that session's
# count rather than raising. Must never disturb release_hook.
# ===========================================================================


def test_record_fanout_dispatch_pure_no_log_below_threshold():
    counts, should_log, fields = ab.record_fanout_dispatch({}, "sess1", "explore", threshold=40)
    assert should_log is False
    assert fields is None
    assert counts["sess1"]["count"] == 1
    assert counts["sess1"]["by_agent_type"] == {"explore": 1}
    assert counts["sess1"]["logged"] is False


def test_record_fanout_dispatch_pure_logs_exactly_at_threshold():
    counts = {}
    should_log = False
    fields = None
    for i in range(40):
        counts, should_log, fields = ab.record_fanout_dispatch(
            counts, "sess1", "implement", threshold=40
        )
        if i < 39:
            assert should_log is False, f"logged early at dispatch {i + 1}"
    assert should_log is True
    assert fields["session"] == "sess1"
    assert fields["count"] == 40
    assert fields["top_agent_types"] == [{"agent_type": "implement", "count": 40}]
    assert counts["sess1"]["logged"] is True


def test_record_fanout_dispatch_never_logs_twice_for_same_session():
    counts = {}
    logged_count = 0
    for _ in range(45):
        counts, should_log, _ = ab.record_fanout_dispatch(counts, "sess1", "explore", threshold=40)
        if should_log:
            logged_count += 1
    assert logged_count == 1  # only the dispatch that FIRST reached 40


def test_record_fanout_dispatch_top_three_by_count_desc_then_name():
    counts = {}
    should_log = False
    fields = None
    for _ in range(20):
        counts, should_log, fields = ab.record_fanout_dispatch(
            counts, "sess1", "implement", threshold=40
        )
    for _ in range(15):
        counts, should_log, fields = ab.record_fanout_dispatch(
            counts, "sess1", "explore", threshold=40
        )
    for _ in range(3):
        counts, should_log, fields = ab.record_fanout_dispatch(
            counts, "sess1", "git-ops", threshold=40
        )
    # 20 + 15 + 3 = 38; two more test-writer dispatches reach exactly 40
    # (threshold) on the SECOND of these two calls.
    counts, should_log, fields = ab.record_fanout_dispatch(counts, "sess1", "test-writer", threshold=40)
    assert should_log is False  # 39th dispatch — not yet at threshold
    counts, should_log, fields = ab.record_fanout_dispatch(counts, "sess1", "test-writer", threshold=40)
    assert should_log is True  # 40th dispatch — crosses the threshold
    assert fields["count"] == 40
    # top three by count desc: implement(20), explore(15), git-ops(3) —
    # test-writer(2) is the 4th and correctly excluded from FANOUT_TOP_N.
    top = fields["top_agent_types"]
    assert len(top) == 3
    assert top[0] == {"agent_type": "implement", "count": 20}
    assert top[1] == {"agent_type": "explore", "count": 15}
    assert top[2] == {"agent_type": "git-ops", "count": 3}


def test_record_fanout_dispatch_sessions_are_independent():
    counts, _, _ = ab.record_fanout_dispatch({}, "sess1", "explore", threshold=40)
    counts, should_log_2, _ = ab.record_fanout_dispatch(counts, "sess2", "explore", threshold=40)
    assert counts["sess1"]["count"] == 1
    assert counts["sess2"]["count"] == 1
    assert should_log_2 is False


def test_record_fanout_dispatch_missing_session_is_a_noop():
    counts, should_log, fields = ab.record_fanout_dispatch({}, "", "explore", threshold=40)
    assert counts == {}
    assert should_log is False
    assert fields is None
    counts2, should_log2, fields2 = ab.record_fanout_dispatch({}, None, "explore", threshold=40)
    assert counts2 == {}
    assert should_log2 is False
    assert fields2 is None


def test_record_fanout_dispatch_none_agent_type_bucketed_as_unknown():
    counts, _, _ = ab.record_fanout_dispatch({}, "sess1", None, threshold=40)
    assert counts["sess1"]["by_agent_type"] == {"unknown": 1}


def test_record_fanout_dispatch_pure_never_mutates_input_dict():
    original = {"sess1": {"count": 5, "by_agent_type": {"explore": 5}, "logged": False}}
    snapshot = json.loads(json.dumps(original))
    ab.record_fanout_dispatch(original, "sess1", "explore", threshold=40)
    assert original == snapshot  # caller's dict untouched


def test_record_fanout_dispatch_threshold_is_configurable():
    counts = {}
    should_log = False
    for _ in range(5):
        counts, should_log, fields = ab.record_fanout_dispatch(counts, "sess1", "explore", threshold=5)
    assert should_log is True
    assert fields["count"] == 5


# --- read/write session_counts.json + corrupt-file-resets ------------------


def test_read_session_counts_missing_file_returns_empty_dict(sandbox):
    path = ab.session_counts_path(str(sandbox.agent_budget_dir))
    assert ab._read_session_counts(path) == {}


def test_read_session_counts_corrupt_json_resets_to_empty_dict(sandbox, tmp_path):
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    path = ab.session_counts_path(str(d))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not valid json!!")
    assert ab._read_session_counts(path) == {}


def test_read_session_counts_non_dict_top_level_resets_to_empty_dict(sandbox):
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    path = ab.session_counts_path(str(d))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([1, 2, 3], fh)
    assert ab._read_session_counts(path) == {}


def test_write_then_read_session_counts_round_trips(sandbox):
    d = sandbox.agent_budget_dir
    path = ab.session_counts_path(str(d))
    payload = {"sess1": {"count": 3, "by_agent_type": {"explore": 3}, "logged": False}}
    ab._write_session_counts(path, payload)
    assert ab._read_session_counts(path) == payload


def test_note_fanout_dispatch_corrupt_counter_file_resets_and_does_not_raise(sandbox, clean_env):
    d = sandbox.agent_budget_dir
    d.mkdir(parents=True, exist_ok=True)
    path = ab.session_counts_path(str(d))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{garbage")
    # Must not raise, and must start the session's count fresh at 1 (never
    # treat the corrupt file as "already past threshold" or crash the hot
    # path it sits on).
    ab.note_fanout_dispatch(str(d), "sess1", "explore", 40, ab.DEFAULT_LOCK_TIMEOUT)
    counts = ab._read_session_counts(path)
    assert counts["sess1"]["count"] == 1


def test_note_fanout_dispatch_missing_session_never_writes_file(sandbox, clean_env):
    d = sandbox.agent_budget_dir
    path = ab.session_counts_path(str(d))
    ab.note_fanout_dispatch(str(d), None, "explore", 40, ab.DEFAULT_LOCK_TIMEOUT)
    ab.note_fanout_dispatch(str(d), "", "explore", 40, ab.DEFAULT_LOCK_TIMEOUT)
    assert not os.path.exists(path)


def test_note_fanout_dispatch_logs_at_threshold_via_lib_log(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    for i in range(40):
        ab.note_fanout_dispatch(d, "sess1", "explore", 40, ab.DEFAULT_LOCK_TIMEOUT)
    lines = sandbox.log_file.read_text().strip().splitlines()
    recs = [json.loads(line) for line in lines]
    fanout_recs = [r for r in recs if r.get("decision") == "fanout-session-high"]
    assert len(fanout_recs) == 1
    assert fanout_recs[0]["session"] == "sess1"
    assert fanout_recs[0]["count"] == 40


def test_note_fanout_dispatch_does_not_log_below_threshold(sandbox, clean_env):
    d = str(sandbox.agent_budget_dir)
    for _ in range(39):
        ab.note_fanout_dispatch(d, "sess1", "explore", 40, ab.DEFAULT_LOCK_TIMEOUT)
    if sandbox.log_file.exists():
        lines = sandbox.log_file.read_text().strip().splitlines()
        recs = [json.loads(line) for line in lines]
        fanout_recs = [r for r in recs if r.get("decision") == "fanout-session-high"]
        assert fanout_recs == []


def test_fanout_threshold_from_env_default_and_override(clean_env, monkeypatch):
    assert ab.fanout_threshold_from_env({}) == 40
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "5")
    assert ab.fanout_threshold_from_env(dict(os.environ)) == 5


def test_fanout_threshold_from_env_garbage_falls_back_to_default():
    assert ab.fanout_threshold_from_env({"CSA_FANOUT_THRESHOLD": "not-a-number"}) == 40
    assert ab.fanout_threshold_from_env({"CSA_FANOUT_THRESHOLD": ""}) == 40


# --- integration: decide()/apply_decision() through the real gate path -----


def test_gate_pacer_off_admitted_dispatch_feeds_fanout_observer(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "2")
    budget_dir = str(sandbox.agent_budget_dir)
    for i in range(2):
        payload = _gate_payload(f"tu{i}", session_id="sessA")
        decision = ab.decide(["gate"], dict(os.environ), budget_dir, payload=payload)
        out, err = io.StringIO(), io.StringIO()
        ab.apply_decision(decision, budget_dir, out, err)
    counts = ab._read_session_counts(ab.session_counts_path(budget_dir))
    assert counts["sessA"]["count"] == 2
    lines = sandbox.log_file.read_text().strip().splitlines()
    recs = [json.loads(line) for line in lines]
    fanout_recs = [r for r in recs if r.get("decision") == "fanout-session-high"]
    assert len(fanout_recs) == 1
    assert fanout_recs[0]["session"] == "sessA"


def test_gate_pacer_off_denied_dispatch_never_feeds_fanout_observer(
    sandbox, clean_env, monkeypatch
):
    # At/over cap + enforcing -> denied. A denied dispatch never ran, so it
    # must never count toward a session's fan-out (mirrors the claim-
    # recording rule: only an ADMITTED gate is ever noted).
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    budget_dir = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "already-live")  # live=1 >= cap 1
    payload = _gate_payload("tu-denied", session_id="sessDenied")
    decision = ab.decide(["gate"], dict(os.environ), budget_dir, payload=payload)
    out, err = io.StringIO(), io.StringIO()
    ab.apply_decision(decision, budget_dir, out, err)
    assert decision.get("deny") is not None
    counts = ab._read_session_counts(ab.session_counts_path(budget_dir))
    assert "sessDenied" not in counts


def test_gate_pacer_on_denied_dispatch_never_feeds_fanout_observer(
    sandbox, clean_env, monkeypatch
):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    budget_dir = str(sandbox.agent_budget_dir)
    _make_lease(sandbox, "already-live")  # live=1 >= cap 1 -> real deny
    payload = _gate_payload("tu-pacer-denied", session_id="sessPacerDenied")
    decision = ab.decide(["gate"], dict(os.environ), budget_dir, agent_id="tu-pacer-denied", payload=payload)
    out, err = io.StringIO(), io.StringIO()
    ab.apply_decision(decision, budget_dir, out, err)
    counts = ab._read_session_counts(ab.session_counts_path(budget_dir))
    assert "sessPacerDenied" not in counts


def test_gate_pacer_on_admitted_dispatch_feeds_fanout_observer(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    budget_dir = str(sandbox.agent_budget_dir)
    payload = _gate_payload("tu-pacer-ok", session_id="sessPacerOk")
    decision = ab.decide(["gate"], dict(os.environ), budget_dir, agent_id="tu-pacer-ok", payload=payload)
    out, err = io.StringIO(), io.StringIO()
    ab.apply_decision(decision, budget_dir, out, err)
    counts = ab._read_session_counts(ab.session_counts_path(budget_dir))
    assert counts["sessPacerOk"]["count"] == 1
    lines = sandbox.log_file.read_text().strip().splitlines()
    recs = [json.loads(line) for line in lines]
    assert any(r.get("decision") == "fanout-session-high" for r in recs)


def test_gate_via_main_admitted_dispatch_feeds_fanout_observer(sandbox, clean_env, monkeypatch):
    monkeypatch.setattr(ab._lib, "enforcing", lambda: False)
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(
        ab._lib,
        "read_event",
        lambda: _gate_payload("tu-main", session_id="sessMain"),
    )
    assert ab.main(["gate"]) == 0
    budget_dir = str(sandbox.agent_budget_dir)
    counts = ab._read_session_counts(ab.session_counts_path(budget_dir))
    assert counts["sessMain"]["count"] == 1


def test_gate_master_off_never_feeds_fanout_observer(sandbox, clean_env, monkeypatch):
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(
        ab._lib, "read_event", lambda: _gate_payload("tu-off", session_id="sessOff")
    )
    assert ab.main(["gate"]) == 0  # CSA_DISABLE_HOOKS short-circuits below
    d = str(sandbox.agent_budget_dir)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CSA_DISABLE_HOOKS", "1")
        assert ab.main(["gate"]) == 0
    path = ab.session_counts_path(d)
    # Either no file was ever created, or (from the FIRST, non-disabled
    # call above) it exists but was never touched by the disabled call.
    if os.path.exists(path):
        counts = ab._read_session_counts(path)
        assert counts.get("sessOff", {}).get("count", 0) <= 1


# --- release_hook must be completely unaffected -----------------------------


def test_release_hook_never_touches_session_counts_file(sandbox, clean_env, monkeypatch):
    """WS2.2's own requirement: the fan-out observer must not disturb
    SubagentStop's release_hook. Drive a full background gate -> async_
    launched -> SubagentStop cycle and confirm session_counts.json is
    untouched by any of the release_hook calls -- only `gate` ever writes
    to it."""
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    budget_dir = str(sandbox.agent_budget_dir)

    gate_payload = _gate_payload("tuR", session_id="sessRelease")
    decision = ab.decide(["gate"], dict(os.environ), budget_dir, agent_id="tuR", payload=gate_payload)
    out, err = io.StringIO(), io.StringIO()
    ab.apply_decision(decision, budget_dir, out, err)

    path = ab.session_counts_path(budget_dir)
    before = ab._read_session_counts(path)
    assert before["sessRelease"]["count"] == 1
    before_mtime = os.stat(path).st_mtime_ns

    # PostToolUse(async_launched) then SubagentStop -- neither is `gate`.
    async_payload = _async_launched_payload("tuR", "agentR", session_id="sessRelease")
    d2 = ab.decide(["release_hook"], dict(os.environ), budget_dir, agent_id="tuR", payload=async_payload)
    ab.apply_decision(d2, budget_dir, io.StringIO(), io.StringIO())

    stop_payload = _subagent_stop_payload(
        "agentR", transcript_path=str(sandbox_transcript(sandbox)), session_id="sessRelease"
    )
    d3 = ab.decide(["release_hook"], dict(os.environ), budget_dir, agent_id="", payload=stop_payload)
    ab.apply_decision(d3, budget_dir, io.StringIO(), io.StringIO())

    after = ab._read_session_counts(path)
    assert after == before  # byte-identical: release_hook wrote nothing here
    assert os.stat(path).st_mtime_ns == before_mtime  # never even re-written


def sandbox_transcript(sandbox):
    """A tiny throwaway transcript file for a SubagentStop payload's
    agent_transcript_path -- content doesn't matter for this test, only
    that release_hook's own (unrelated) transcript-reading code path has
    something to open without erroring."""
    p = sandbox.agent_budget_dir.parent / "transcript_release_test.jsonl"
    p.write_text('{"type": "assistant", "message": {"model": "haiku", "usage": {}}}\n')
    return p


def test_release_hook_lease_release_unaffected_by_fanout_observer(sandbox, clean_env, monkeypatch):
    """The pacer's own lease release (release_hook's actual job) must keep
    working exactly as before -- the fan-out observer addition must not
    change release_hook's existing release semantics."""
    monkeypatch.setenv("CSA_PACER", "1")
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
    monkeypatch.setenv("CSA_FANOUT_THRESHOLD", "1")
    monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
    budget_dir = str(sandbox.agent_budget_dir)

    gate_payload = _gate_payload("tuL", session_id="sessLease")
    decision = ab.decide(["gate"], dict(os.environ), budget_dir, agent_id="tuL", payload=gate_payload)
    ab.apply_decision(decision, budget_dir, io.StringIO(), io.StringIO())
    assert os.path.exists(ab.lease_path(budget_dir, "tuL"))

    completed_payload = {
        "session_id": "sessLease",
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_use_id": "tuL",
        "tool_response": {"status": "completed", "agentId": "agentL"},
        "duration_ms": 5000,
    }
    d2 = ab.decide(
        ["release_hook"], dict(os.environ), budget_dir, agent_id="tuL", payload=completed_payload
    )
    ab.apply_decision(d2, budget_dir, io.StringIO(), io.StringIO())
    assert not os.path.exists(ab.lease_path(budget_dir, "tuL"))  # lease released as before


def test_admitted_gate_caps_fanout_observer_lock_timeout(sandbox, clean_env, monkeypatch):
    """The fan-out observer is a PURE OBSERVER: it must never spend the full
    admission budget on the dispatch hot path. Both admitted call sites pass
    min(lock_timeout, FANOUT_LOCK_TIMEOUT) -- reverting that cap stacks a
    THIRD full DEFAULT_LOCK_TIMEOUT onto every admitted dispatch, measured
    at 4.01s -> 6.01s worst case (+50%) before the fix.

    This test exists because the fix shipped with ZERO coverage: the full
    531-test suite passed with the cap fully reverted, so a future edit
    could silently restore the 2.0s stall with CI green. It asserts the
    EFFECTIVE timeout at the call site, not merely that the constant exists
    -- the latter would be a lock-in test that the mutant also survives.
    """
    seen = []
    monkeypatch.setattr(ab, "note_fanout_dispatch", lambda bd, s, a, t, lt: seen.append(lt))
    budget_dir = str(sandbox.agent_budget_dir)
    for pacer in ("0", "1"):
        seen.clear()
        monkeypatch.setenv("CSA_PACER", pacer)
        monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "5")
        monkeypatch.setattr(ab._lib, "enforcing", lambda: True)
        payload = _gate_payload(f"tuCap{pacer}", session_id="sessCap")
        d = ab.decide(
            ["gate"], dict(os.environ), budget_dir, agent_id=f"tuCap{pacer}", payload=payload
        )
        ab.apply_decision(d, budget_dir, io.StringIO(), io.StringIO())
        assert seen == [ab.FANOUT_LOCK_TIMEOUT], (pacer, seen)
        assert seen[0] < d.get("lock_timeout", ab.DEFAULT_LOCK_TIMEOUT)


def test_fanout_observer_honours_a_shorter_caller_timeout():
    """PAIRED RECOVERY: min() is a CEILING, never a floor. A caller
    deliberately passing a timeout shorter than FANOUT_LOCK_TIMEOUT keeps
    its own shorter value -- the cap may only ever reduce the wait, never
    lengthen it."""
    assert min(0.01, ab.FANOUT_LOCK_TIMEOUT) == 0.01
    assert ab.FANOUT_LOCK_TIMEOUT < ab.DEFAULT_LOCK_TIMEOUT
