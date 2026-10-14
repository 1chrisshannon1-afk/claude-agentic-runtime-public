"""Contract tests for hooks/pretooluse_task.py, the PreToolUse:Task dispatcher.

The module docstring is the spec. It chains two gates, first block wins:

  T1  model_pin_gate  - may refuse a dispatch (pin-tier-mismatch, ...)
  T2  agent_budget.py's pacer/spend gate - runs ONLY if T1 allows

and promises:

  * a T1 deny means T2 is never entered, so a refused dispatch never takes a
    pacer lease or a spend-ledger claim;
  * stdin is read exactly once and the SAME event is handed to both gates;
  * log-only by default (a T1 would-block is logged and the dispatch proceeds),
    a real deny only under enforcement, and a deny is JSON on stdout with exit
    code 0, never a non-zero exit;
  * CSA_DISABLE_HOOKS=1 is a no-op allow before anything is read or run;
  * a crashing dispatcher or an unreadable policy/roster degrades to ALLOW, it
    never breaks a dispatch.

test_model_pin_gate.py exercises the gate's decision tree through this entry
point; this file pins the dispatcher's own ordering and fail-open contract with
recorders in place of the gates, so a regression in the chaining is visible
here even when the gate's verdicts are unchanged. Nothing here reads or writes
the real ~/.claude: the `sandbox` fixture points HOME and every _lib path at
tmp_path, and the subprocess case runs with a throwaway HOME.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import agent_budget as ab
import model_pin_gate as mpg
import pretooluse_task as ptt
import pytest

HOOK = Path(__file__).resolve().parents[1] / "pretooluse_task.py"

ROSTER = {"code-reviewer": "opus", "explore": "sonnet"}
PROMPT = "Review the pending diff for correctness."


def _payload(agent: str, model: str | None = None, **extra) -> dict:
    """The PreToolUse:Task event shape (tool_input.subagent_type/model/prompt)."""
    ti = {"subagent_type": agent, "prompt": PROMPT}
    if model is not None:
        ti["model"] = model
    ev = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Task",
        "tool_input": ti,
        "session_id": "sess-1",
        "tool_use_id": "toolu_" + agent.replace("-", "_"),
    }
    ev.update(extra)
    return ev


def _write_roster(claude: Path) -> None:
    (claude / "agents").mkdir(parents=True, exist_ok=True)
    (claude / "knowledge").mkdir(parents=True, exist_ok=True)
    for name, model in ROSTER.items():
        (claude / "agents" / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: fixture\nmodel: {model}\ntools: Read\n---\n\nbody\n"
        )
    (claude / "knowledge" / "model_policy.json").write_text(json.dumps({"agent_pins": ROSTER}))


@pytest.fixture
def roster(sandbox, monkeypatch, tmp_path):
    """A hermetic roster and policy wired into the gate's defaults. Non-git cwd."""
    _write_roster(sandbox.claude)
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", str(sandbox.claude / "agents"))
    monkeypatch.setattr(
        mpg, "DEFAULT_POLICY_PATH", str(sandbox.claude / "knowledge" / "model_policy.json")
    )
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", str(sandbox.claude / ".model_exceptions"))
    return sandbox


def _run_main(monkeypatch, payload, *, env=None):
    """Feed `payload` (dict or raw str) to ptt.main() on stdin; return
    (exit_code, stdout)."""
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = ptt.main()
    return rc, buf.getvalue()


def _deny(stdout: str):
    """The parsed PreToolUse deny object, or None when stdout is not one."""
    if not stdout.strip():
        return None
    try:
        obj = json.loads(stdout)
    except ValueError:
        return None
    hso = obj.get("hookSpecificOutput", {})
    if hso.get("hookEventName") == "PreToolUse" and hso.get("permissionDecision") == "deny":
        return hso
    return None


def _rows(sandbox) -> list:
    if not sandbox.log_file.exists():
        return []
    return [json.loads(x) for x in sandbox.log_file.read_text().splitlines() if x.strip()]


class Recorder:
    """Stands in for a gate. Records calls instead of asserting inside the call:
    ptt.main() swallows every exception, so an assertion raised from a gate
    would be silently turned into an allow and the test would pass."""

    def __init__(self, result):
        self.result = result
        self.calls: list = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


# ---------------------------------------------------------------------------
# T1 deny short-circuits T2
# ---------------------------------------------------------------------------


def test_enforced_t1_deny_emits_json_deny_with_exit_zero_and_never_enters_t2(roster, monkeypatch):
    t2 = Recorder(0)
    monkeypatch.setattr(ptt, "apply_t2", t2)

    rc, out = _run_main(monkeypatch, _payload("code-reviewer", "sonnet"), env={"CSA_ENFORCE": "1"})

    assert rc == 0  # a deny is JSON, never a non-zero exit
    hso = _deny(out)
    assert hso is not None, out
    assert "pin-tier-mismatch" in hso["permissionDecisionReason"]
    assert t2.calls == []


def test_a_denied_dispatch_holds_no_pacer_lease_and_no_spend_claim(roster, monkeypatch):
    """With the pacer ON a T2 pass would take a lease and a claim; after a T1
    deny the budget dir must hold nothing. The next test is the positive control
    proving this emptiness is not vacuous."""
    rc, out = _run_main(
        monkeypatch,
        _payload("code-reviewer", "sonnet"),
        env={"CSA_ENFORCE": "1", "CSA_PACER": "1"},
    )
    assert rc == 0 and _deny(out) is not None
    budget = str(roster.agent_budget_dir)
    assert not os.path.exists(ab.claims_path(budget))
    assert not (
        os.path.isdir(budget) and any(f.startswith(ab.LEASE_PREFIX) for f in os.listdir(budget))
    )


def test_an_allowed_dispatch_does_take_a_pacer_lease_and_a_spend_claim(roster, monkeypatch):
    """Positive control for the test above: same environment, T1 allows."""
    rc, out = _run_main(
        monkeypatch,
        _payload("explore", "sonnet"),
        env={"CSA_ENFORCE": "1", "CSA_PACER": "1"},
    )
    assert rc == 0 and _deny(out) is None, out
    budget = str(roster.agent_budget_dir)
    assert any(f.startswith(ab.LEASE_PREFIX) for f in os.listdir(budget))
    assert os.path.exists(ab.claims_path(budget))


def test_log_only_t1_would_block_is_logged_and_the_dispatch_proceeds_to_t2(roster, monkeypatch):
    t2 = Recorder(0)
    monkeypatch.setattr(ptt, "apply_t2", t2)

    rc, out = _run_main(monkeypatch, _payload("code-reviewer", "sonnet"))  # no CSA_ENFORCE

    assert rc == 0 and out == ""
    assert len(t2.calls) == 1
    rows = [r for r in _rows(roster) if r["hook"] == "pretooluse_task"]
    assert len(rows) == 1
    assert rows[0]["decision"] == "would-block"
    assert rows[0]["gate"] == "model_pin_gate"
    assert rows[0]["reason"] == "pin-tier-mismatch"
    assert rows[0]["enforce"] is False


def test_the_would_block_row_carries_dispatch_identity(roster, monkeypatch):
    _run_main(monkeypatch, _payload("code-reviewer", "sonnet"), env={"CSA_ENFORCE": "1"})
    (row,) = [r for r in _rows(roster) if r["hook"] == "pretooluse_task"]
    assert row["enforce"] is True
    assert row["agent_type"] == "code-reviewer"
    assert row["session"] == "sess-1"


# ---------------------------------------------------------------------------
# T1 allow reaches T2
# ---------------------------------------------------------------------------


def test_t1_allow_hands_the_same_event_to_t2(roster, monkeypatch):
    seen = {}
    real_t1 = ptt.apply_t1

    def spy_t1(ev):
        seen["t1"] = ev
        return real_t1(ev)

    t2 = Recorder(0)
    monkeypatch.setattr(ptt, "apply_t1", spy_t1)
    monkeypatch.setattr(ptt, "apply_t2", t2)

    payload = _payload("explore", "sonnet")
    rc, out = _run_main(monkeypatch, payload, env={"CSA_ENFORCE": "1"})

    assert rc == 0 and out == ""
    assert len(t2.calls) == 1
    (ev_to_t2,), _ = t2.calls[0]
    assert ev_to_t2 is seen["t1"]  # one parse, threaded to both gates
    assert ev_to_t2 == payload


def test_stdin_is_read_exactly_once(roster, monkeypatch):
    reads = []
    real = ptt._lib.read_event

    def counting_read():
        reads.append(1)
        return real()

    monkeypatch.setattr(ptt._lib, "read_event", counting_read)
    rc, _ = _run_main(monkeypatch, _payload("explore", "sonnet"), env={"CSA_ENFORCE": "1"})
    assert rc == 0
    assert len(reads) == 1


def test_a_t2_deny_passes_through_when_t1_allows_and_clears_when_a_slot_frees(roster, monkeypatch):
    """The documented enforcing path: with the pacer ON and enforcement ON, a
    dispatch refused at the concurrency cap is denied through the dispatcher, and
    (recovery pair) the same dispatch is admitted once the slot is free. The
    pacer-off gate is advisory, so this deliberately does not pin that path."""
    monkeypatch.setenv("CSA_ANTHROPIC_CEILING", "1")
    monkeypatch.setenv("CSA_ADMIT_MAX_WAIT_SEC", "0")  # do not wait out a slot
    env = {"CSA_ENFORCE": "1", "CSA_PACER": "1"}
    budget = str(roster.agent_budget_dir)
    ab.write_lease(budget, "someone-else")

    rc, out = _run_main(monkeypatch, _payload("explore", "sonnet"), env=env)
    hso = _deny(out)
    assert rc == 0 and hso is not None, out
    assert "concurrency cap" in hso["permissionDecisionReason"]

    os.remove(ab.lease_path(budget, "someone-else"))
    rc, out = _run_main(monkeypatch, _payload("explore", "sonnet"), env=env)
    assert rc == 0 and _deny(out) is None, out
    assert any(f.startswith(ab.LEASE_PREFIX) for f in os.listdir(budget))


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


def test_unreadable_policy_allows_with_a_logged_fail_open_row_and_still_reaches_t2(
    roster, monkeypatch
):
    os.remove(roster.claude / "knowledge" / "model_policy.json")
    t2 = Recorder(0)
    monkeypatch.setattr(ptt, "apply_t2", t2)

    rc, out = _run_main(monkeypatch, _payload("code-reviewer", "sonnet"), env={"CSA_ENFORCE": "1"})

    assert rc == 0 and out == ""  # even under enforcement: the gate has no policy to apply
    assert len(t2.calls) == 1
    rows = [
        r for r in _rows(roster) if r["hook"] == "model_pin_gate" and r["decision"] == "fail-open"
    ]
    assert [r["reason"] for r in rows] == ["policy-unreadable"]


def test_unreadable_roster_allows_with_a_logged_fail_open_row(roster, monkeypatch):
    for f in (roster.claude / "agents").iterdir():
        f.unlink()
    (roster.claude / "agents").rmdir()

    rc, out = _run_main(monkeypatch, _payload("code-reviewer", "sonnet"), env={"CSA_ENFORCE": "1"})

    assert rc == 0 and _deny(out) is None
    rows = [
        r for r in _rows(roster) if r["hook"] == "model_pin_gate" and r["decision"] == "fail-open"
    ]
    assert [r["reason"] for r in rows] == ["agents-dir-unreadable"]


@pytest.mark.parametrize("which", ["apply_t1", "apply_t2"])
def test_a_crashing_gate_never_breaks_the_dispatch(roster, monkeypatch, which):
    def boom(*_a, **_k):
        raise RuntimeError("simulated gate crash")

    monkeypatch.setattr(ptt, which, boom)
    rc, out = _run_main(monkeypatch, _payload("explore", "sonnet"), env={"CSA_ENFORCE": "1"})
    assert rc == 0
    assert _deny(out) is None


# Payloads that carry no tool_input dict at all: stdin that is empty, not JSON, or JSON
# that is not an object all reach the gate as {}, and a bare {"tool_name": "Task"} is
# the same shape.
NO_TOOL_INPUT = ["", "not json at all", "[1, 2, 3]", "null", '{"tool_name": "Task"}']


@pytest.mark.parametrize("raw", NO_TOOL_INPUT)
def test_an_event_without_tool_input_never_crashes_or_exits_nonzero(roster, monkeypatch, raw):
    rc, out = _run_main(monkeypatch, raw, env={"CSA_ENFORCE": "1"})
    assert rc == 0
    if out.strip():
        json.loads(out)  # anything printed is a single well-formed hook object


@pytest.mark.xfail(
    strict=True,
    reason=(
        "model_pin_gate's FAIL-OPEN CONTRACT says an unparseable payload ALLOWS. Today "
        "unparseable stdin reaches the gate as {} and is denied pin-inherit-drift under "
        "enforcement. The fix is that the gate must fail open when the event has no "
        "tool_input dict; it must NOT start allowing a real Task event whose tool_input "
        "merely lacks subagent_type (the client permits that and the gate rightly denies "
        "it; see test_a_task_with_no_subagent_type_and_no_model_is_denied_as_inherit_drift). "
        "Gate fix is outside lane A3; remove this marker when it lands."
    ),
)
@pytest.mark.parametrize("raw", NO_TOOL_INPUT)
def test_an_event_without_tool_input_is_allowed_under_enforcement(roster, monkeypatch, raw):
    rc, out = _run_main(monkeypatch, raw, env={"CSA_ENFORCE": "1"})
    assert rc == 0
    assert _deny(out) is None


def test_a_task_with_no_subagent_type_and_no_model_is_denied_as_inherit_drift(roster, monkeypatch):
    """The other half of the contract above. subagent_type is optional in the client's
    Task input, and a dispatch that names neither an agent nor a model inherits the
    parent session's model with no governance: the gate is right to deny it. A fix for
    the unparseable-payload defect must not loosen this."""
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Task",
        "tool_input": {"prompt": PROMPT, "description": "do a thing"},
        "session_id": "sess-1",
        "tool_use_id": "toolu_nameless",
    }
    rc, out = _run_main(monkeypatch, event, env={"CSA_ENFORCE": "1"})
    hso = _deny(out)
    assert rc == 0 and hso is not None, out
    assert "pin-inherit-drift" in hso["permissionDecisionReason"]


def test_a_task_naming_a_pinned_agent_without_a_model_is_allowed(roster, monkeypatch):
    """Recovery pair for the denial above: name an agent whose own file carries the
    pin and the same minimal dispatch goes through."""
    event = _payload("explore")  # subagent_type only, no model
    assert "model" not in event["tool_input"]
    rc, out = _run_main(monkeypatch, event, env={"CSA_ENFORCE": "1"})
    assert rc == 0 and _deny(out) is None, out


def test_a_failing_identity_lookup_cannot_turn_a_deny_into_an_allow(roster, monkeypatch):
    """Telemetry must never change a dispatch outcome: if building the log row's
    identity fields raises, the deny is still emitted."""

    def boom(*_a, **_k):
        raise RuntimeError("identity lookup failed")

    monkeypatch.setattr(ptt, "_identity", boom)
    rc, out = _run_main(monkeypatch, _payload("code-reviewer", "sonnet"), env={"CSA_ENFORCE": "1"})
    assert rc == 0
    assert _deny(out) is not None, "a deny was swallowed by a telemetry failure"


# ---------------------------------------------------------------------------
# Master kill switch
# ---------------------------------------------------------------------------


def test_disable_hooks_runs_neither_gate_and_reads_nothing_but_enforcement_denies_without_it(
    roster, monkeypatch
):
    t1 = Recorder((True, "pin-tier-mismatch", {"subagent_type": "x", "model": "y", "pin": "z"}))
    t2 = Recorder(0)
    reads = Recorder({})
    monkeypatch.setattr(ptt.mpg, "decide", t1)
    monkeypatch.setattr(ptt, "apply_t2", t2)
    monkeypatch.setattr(ptt._lib, "read_event", reads)

    rc, out = _run_main(
        monkeypatch,
        _payload("code-reviewer", "sonnet"),
        env={"CSA_ENFORCE": "1", "CSA_DISABLE_HOOKS": "1"},
    )
    assert rc == 0 and out == ""
    assert t1.calls == [] and t2.calls == [] and reads.calls == []

    # Recovery pair: the same stubs, kill switch off, are reached and the deny
    # stands, so the silence above came from the switch and not from a no-op hook.
    monkeypatch.delenv("CSA_DISABLE_HOOKS")
    reads.result = _payload("code-reviewer", "sonnet")
    rc, out = _run_main(monkeypatch, "{}", env={"CSA_ENFORCE": "1"})
    assert rc == 0 and _deny(out) is not None
    assert len(t1.calls) == 1 and t2.calls == []


# ---------------------------------------------------------------------------
# Real entry point
# ---------------------------------------------------------------------------


def _spawn(sandbox, tmp_path, stdin, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CSA_", "CLAUDE_"))}
    env["HOME"] = str(sandbox.home)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=str(tmp_path),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_script_entry_point_denies_in_json_and_exits_zero(sandbox, tmp_path):
    _write_roster(sandbox.claude)
    refused = json.dumps(_payload("code-reviewer", "sonnet", cwd=str(tmp_path)))
    allowed = json.dumps(_payload("code-reviewer", "opus", cwd=str(tmp_path)))

    proc = _spawn(sandbox, tmp_path, refused, {"CSA_ENFORCE": "1"})
    assert proc.returncode == 0, proc.stderr
    hso = _deny(proc.stdout)
    assert hso is not None, proc.stdout
    assert "pin-tier-mismatch" in hso["permissionDecisionReason"]

    # Recovery: the compliant dispatch of the same agent is allowed.
    proc = _spawn(sandbox, tmp_path, allowed, {"CSA_ENFORCE": "1"})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""

    # Log-only default and the kill switch both let the refused dispatch through.
    for extra in ({}, {"CSA_ENFORCE": "1", "CSA_DISABLE_HOOKS": "1"}):
        proc = _spawn(sandbox, tmp_path, refused, extra)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""

    # Empty stdin (no event at all) is not a crash: exit 0 whatever is printed.
    proc = _spawn(sandbox, tmp_path, "", {"CSA_ENFORCE": "1"})
    assert proc.returncode == 0, proc.stderr
