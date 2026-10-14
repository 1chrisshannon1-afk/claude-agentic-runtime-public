"""Tests for hooks/agent_router.py (auto-invocation design, commit 2).

Spec (agentic-systems-architect design 2026-09-28): a UserPromptSubmit hint names the
right agent for a matching prompt, stays silent for everyday product vocabulary, fires at
most once per (session, agent), never when the prompt already names the agent or the agent
was already dispatched this session, and fails open. Path mode hints on agent/plan/KB files
and records an obligation for must-rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_router as ar  # noqa: E402

RULES = json.loads((Path(__file__).resolve().parents[2] / "knowledge" / "agent_triggers.json").read_text())


@pytest.fixture(autouse=True)
def tmp_claude(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(ar, "OBLIG_DIR", tmp_path / "oblig")
    monkeypatch.setattr(ar, "SPEND", tmp_path / "spend.jsonl")
    monkeypatch.setattr(ar, "CLAUDE", tmp_path)
    return tmp_path


POSITIVE = [
    ("I want to sell the company within two years", "venture-director"),
    ("who are the likely acquirers and what is an exit plan", "venture-director"),
    ("help me find a co-founder for otherapp", "partner-recruiter"),
    ("I need to build a team for this app", "partner-recruiter"),
    ("we're hiring a carpenter, write the job posting", "hiring-specialist"),
    ("post a job on indeed for an office manager", "hiring-specialist"),
    ("fix the other-company google business profile and yelp listing", "marketing-director"),
    ("plan instagram content for othercompany", "marketing-director"),
    ("create a new agent for hiring", "agentic-systems-architect"),
    ("these workflows are burning my tokens", "agentic-systems-architect"),
    ("why is our gcp bill so high this month", "cost-strategist"),
]

NEGATIVE = [
    "show the Sales role in team management",
    "the estimate total is wrong for the shower job",
    "upsell the premium plan in the pricing page",
    "the contractor wants to hire a plumber for the job",
    "fix the login bug on staging",
    "add a sale price field to the catalog",
    "run the tests for the crm module",
    "why did the job fail in CI",
    "update the marketing site header",  # no company named -> no director hint
    "vendor cost for tile in the catalog",
    "change the subscription cost on the pricing page",
    "the job listing page is broken",
    "build a team management page",
    "show token usage on the admin portal",
    "write the agent prompt for iris",
    "csa landing page after login is blank",
    "/gtm improve other-company google ads",
    "we should sell the app to contractors via facebook ads",
]


@pytest.mark.parametrize("prompt,agent", POSITIVE)
def test_prompt_rules_route_to_the_right_agent(prompt, agent):
    rule = ar.match_prompt(prompt, RULES)
    assert rule is not None and rule["agent"] == agent, (prompt, rule)


@pytest.mark.parametrize("prompt", NEGATIVE)
def test_everyday_product_vocabulary_never_routes(prompt):
    assert ar.match_prompt(prompt, RULES) is None, prompt


def test_hint_once_per_session_and_agent():
    p = {"session_id": "s1", "prompt": "help me find a co-founder"}
    first = ar.handle_prompt(p, RULES)
    assert first and "partner-recruiter" in first and "operator" in first
    assert ar.handle_prompt(p, RULES) is None


def test_no_hint_when_prompt_names_the_agent():
    p = {"session_id": "s2", "prompt": "have partner-recruiter find a co-founder"}
    assert ar.handle_prompt(p, RULES) is None


def test_no_hint_when_agent_already_dispatched(tmp_claude):
    (tmp_claude / "spend.jsonl").write_text(json.dumps({"session": "s3", "agent_type": "partner-recruiter"}) + "\n")
    assert ar.handle_prompt({"session_id": "s3", "prompt": "find a co-founder"}, RULES) is None


def test_path_mode_agent_file_hints_and_records_obligation(tmp_claude):
    p = {"session_id": "s4", "tool_input": {"file_path": "/Users/x/.claude/agents/new-seat.md"}}
    out = ar.handle_path(p, RULES)
    assert out and "agentic-systems-architect" in out
    rows = (tmp_claude / "oblig" / "s4.jsonl").read_text().splitlines()
    assert json.loads(rows[0])["agent"] == "agentic-systems-architect"


def test_path_mode_plan_file_is_a_must_rule(tmp_claude):
    p = {"session_id": "s5", "tool_input": {"file_path": "/Users/x/.claude/plans/new_thing_plan.md"}}
    assert "plan-reviewer" in ar.handle_path(p, RULES)
    assert (tmp_claude / "oblig" / "s5.jsonl").exists()


def test_path_mode_kb_file_hints_without_obligation(tmp_claude):
    p = {"session_id": "s6", "tool_input": {"file_path": "/Users/x/.claude/knowledge/hiring_kb/posting/x.md"}}
    assert "claims verification" in ar.handle_path(p, RULES)
    assert not (tmp_claude / "oblig" / "s6.jsonl").exists()


def test_path_mode_ignores_ordinary_files():
    p = {"session_id": "s7", "tool_input": {"file_path": "/Users/x/Desktop/app/modules/crm/api.py"}}
    assert ar.handle_path(p, RULES) is None


def test_fails_open_on_bad_input(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": staticmethod(lambda: "{not json")})())
    assert ar.main([]) == 0
    assert capsys.readouterr().out == ""


def test_kill_switch(monkeypatch, capsys, tmp_claude):
    (tmp_claude / ".router_off").write_text("")
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": staticmethod(lambda: json.dumps({"prompt": "find a co-founder"}))})())
    assert ar.main([]) == 0
    assert capsys.readouterr().out == ""


def test_machine_text_never_routes():
    for text in ["This session is being continued from a previous conversation... find a co-founder",
                 "Read and obey ~/.claude/schedules/prompts/_preamble.txt first ... sell the company",
                 "x " * 1200 + " find a co-founder"]:
        assert ar.handle_prompt({"session_id": "m", "prompt": text}, RULES) is None


def test_plan_rule_skips_handoffs_and_reports(tmp_claude):
    for name in ["handoff_post_deploy_2026_09_09.md", "gate_verdict2.md", "weekly_report_plan.md", "gtm_pack_facts_x.md"]:
        p = {"session_id": "h", "tool_input": {"file_path": f"/Users/x/.claude/plans/{name}"}}
        assert ar.handle_path(p, RULES) is None, name
    assert not (tmp_claude / "oblig" / "h.jsonl").exists()


def test_plan_rule_is_case_insensitive(tmp_claude):
    p = {"session_id": "ci", "tool_input": {"file_path": "/Users/x/Desktop/Co/plans/v2/00_MASTER_PLAN.md"}}
    assert "plan-reviewer" in ar.handle_path(p, RULES)


def test_plan_rule_matches_real_plan_under_a_review_named_folder():
    p = {"session_id": "rv", "tool_input": {"file_path": "/Users/x/Desktop/Co/Google_Ads_Review_2026_09_25/plans/v2/00_MASTER_PLAN.md"}}
    assert "plan-reviewer" in ar.handle_path(p, RULES)


def test_plan_rule_ignores_findings_inside_a_plan_named_folder(tmp_claude):
    p = {"session_id": "pf", "tool_input": {"file_path": "/Users/x/.claude/plans/master_plan_v2_inputs/architecture_findings.md"}}
    assert ar.handle_path(p, RULES) is None


def test_plan_rule_accepts_review_in_plan_name():
    p = {"session_id": "rn", "tool_input": {"file_path": "/Users/x/.claude/plans/review_ladder_redesign_plan.md"}}
    assert "plan-reviewer" in ar.handle_path(p, RULES)


def test_bash_fast_path_is_case_insensitive(tmp_path):
    import subprocess
    sh = Path(__file__).resolve().parents[1] / "agent_router_path.sh"
    payload = json.dumps({"session_id": "b", "tool_input": {"file_path": "/Users/x/Agency/Plans/q4_plan.md"}})
    body = sh.read_text().replace('python3 "$HOME/.claude/hooks/agent_router.py" --path', "echo LAUNCHED")
    script = tmp_path / "shim.sh"
    script.write_text(body)
    out = subprocess.run(["bash", str(script)], input=payload, capture_output=True, text=True).stdout
    assert "LAUNCHED" in out


def test_plan_rule_matches_file_name_not_folder_name(tmp_claude):
    p = {"session_id": "fn", "tool_input": {"file_path": "/Users/x/.claude/plans/master_plan_v2_inputs/COVERAGE_TABLE.md"}}
    assert ar.handle_path(p, RULES) is None
