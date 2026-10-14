"""Tests for hooks/agent_obligations.py (auto-invocation design, commit 3).

Spec: at Stop, an open must-rule obligation (agent file -> agentic-systems-architect;
plan file -> plan-reviewer) blocks once with a reason naming file and agent; it clears
when the agent was dispatched in the session after the obligation, the file is back to
HEAD or gone, or (plans) the plan-review ledger logged it; stop_hook_active allows;
never blocks twice; fails open.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_obligations as ao  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(ao, "CLAUDE", tmp_path)
    monkeypatch.setattr(ao, "OBLIG_DIR", tmp_path / "oblig")
    monkeypatch.setattr(ao, "SPEND", tmp_path / "spend.jsonl")
    monkeypatch.setattr(ao, "PLAN_LEDGER", tmp_path / "plan_reviews.jsonl")
    monkeypatch.setattr(ao, "CLAIMS", tmp_path / "claims.jsonl")
    (tmp_path / "oblig").mkdir()
    return tmp_path


def _oblig(env, session, agent, path, rule="agent-file", ts="2026-09-28T10:00:00Z"):
    with open(env / "oblig" / f"{session}.jsonl", "a") as fh:
        fh.write(json.dumps({"ts": ts, "rule": rule, "agent": agent, "path": str(path), "hint": "x"}) + "\n")


def _run(monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": staticmethod(lambda: json.dumps(payload))})())
    assert ao.main() == 0
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def _untracked_file(env, name="new-seat.md"):
    f = env / name
    f.write_text("x")
    return f


def test_open_obligation_blocks_once(env, monkeypatch, capsys):
    f = _untracked_file(env)
    _oblig(env, "s1", "agentic-systems-architect", f)
    first = _run(monkeypatch, capsys, {"session_id": "s1"})
    assert first["decision"] == "block" and "agentic-systems-architect" in first["reason"] and "new-seat.md" in first["reason"]
    assert _run(monkeypatch, capsys, {"session_id": "s1"}) is None


def test_cleared_by_dispatch_after_obligation(env, monkeypatch, capsys):
    f = _untracked_file(env)
    _oblig(env, "s2", "agentic-systems-architect", f)
    (env / "spend.jsonl").write_text(json.dumps({"ts": "2026-09-28T10:05:00Z", "session": "s2", "agent_type": "agentic-systems-architect"}) + "\n")
    assert _run(monkeypatch, capsys, {"session_id": "s2"}) is None


def test_dispatch_before_obligation_does_not_clear(env, monkeypatch, capsys):
    f = _untracked_file(env)
    _oblig(env, "s3", "agentic-systems-architect", f)
    (env / "spend.jsonl").write_text(json.dumps({"ts": "2026-09-28T09:00:00Z", "session": "s3", "agent_type": "agentic-systems-architect"}) + "\n")
    assert _run(monkeypatch, capsys, {"session_id": "s3"})["decision"] == "block"


def test_cleared_by_plan_ledger(env, monkeypatch, capsys):
    f = _untracked_file(env, "x_plan.md")
    _oblig(env, "s4", "plan-reviewer", f, rule="plan-file")
    (env / "plan_reviews.jsonl").write_text(json.dumps({"ts": "2026-09-28T11:00:00Z", "plan": str(f), "outcome": "clean"}) + "\n")
    assert _run(monkeypatch, capsys, {"session_id": "s4"}) is None


def test_cleared_when_file_deleted(env, monkeypatch, capsys):
    _oblig(env, "s5", "agentic-systems-architect", env / "gone.md")
    assert _run(monkeypatch, capsys, {"session_id": "s5"}) is None


def test_cleared_when_file_back_to_head(env, monkeypatch, capsys):
    repo = env / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    f = repo / "a.md"
    f.write_text("same")
    subprocess.run(["git", "-C", str(repo), "add", "a.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], check=True)
    _oblig(env, "s6", "agentic-systems-architect", f)
    assert _run(monkeypatch, capsys, {"session_id": "s6"}) is None


def test_stop_hook_active_allows(env, monkeypatch, capsys):
    f = _untracked_file(env)
    _oblig(env, "s7", "agentic-systems-architect", f)
    assert _run(monkeypatch, capsys, {"session_id": "s7", "stop_hook_active": True}) is None


def test_no_obligations_no_output(env, monkeypatch, capsys):
    assert _run(monkeypatch, capsys, {"session_id": "none"}) is None


def test_fails_open_on_bad_json(env, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": staticmethod(lambda: "{bad")})())
    assert ao.main() == 0 and capsys.readouterr().out == ""


def test_in_flight_claim_clears(env, monkeypatch, capsys):
    f = _untracked_file(env)
    _oblig(env, "c1", "plan-reviewer", f, rule="plan-file")
    (env / "claims.jsonl").write_text(json.dumps({"ts": "2026-09-28T10:01:00Z", "session": "c1", "agent_type": "plan-reviewer"}) + "\n")
    assert _run(monkeypatch, capsys, {"session_id": "c1"}) is None


def test_tracked_file_with_uncommitted_change_still_blocks(env, monkeypatch, capsys):
    repo = env / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    f = repo / "a.md"
    f.write_text("v1")
    subprocess.run(["git", "-C", str(repo), "add", "a.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], check=True)
    f.write_text("v2")
    _oblig(env, "c2", "agentic-systems-architect", f)
    assert _run(monkeypatch, capsys, {"session_id": "c2"})["decision"] == "block"


def test_relative_plan_path_in_ledger_resolves_against_repo(env, monkeypatch, capsys):
    repo = env / "r"
    (repo / "plans").mkdir(parents=True)
    f = repo / "plans" / "x_plan.md"
    f.write_text("p")
    _oblig(env, "c3", "plan-reviewer", f, rule="plan-file")
    (env / "plan_reviews.jsonl").write_text(json.dumps({"ts": "2026-09-28T11:00:00Z", "repo": str(repo), "plan": "plans/x_plan.md"}) + "\n")
    assert _run(monkeypatch, capsys, {"session_id": "c3"}) is None
