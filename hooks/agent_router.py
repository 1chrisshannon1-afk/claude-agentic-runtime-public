#!/usr/bin/env python3
"""agent_router.py — bring the right agent in without the operator naming it.

Auto-invocation design (agentic-systems-architect, 2026-09-28), commit 2.
Operator, verbatim: "i want agents to be called on or initiated mechanically
when/where reasonable and possible."

Two modes, one rule file (knowledge/agent_triggers.json):

  (default)  UserPromptSubmit hook. Regex-matches the operator's prompt against
             `prompt_rules`; on a match prints one short advisory line as
             hookSpecificOutput.additionalContext ("Routing hint: … bring in
             `<agent>`"). No match -> prints nothing (zero tokens).
  --path     PostToolUse Write|Edit|MultiEdit hook. Matches the edited file
             against `path_rules`; on a match prints the rule's hint, and for
             `must: true` rules records an obligation in
             ~/.claude/.agent_obligations/<session>.jsonl, which
             hooks/agent_obligations.py checks at Stop.

Never calls a model, never dispatches anything, never writes an operator card.
Anti-nag: at most one hint per (session, agent); none when the prompt already
names the agent; none when spend.jsonl shows that agent already dispatched in
this session; at most one hint per prompt. Fails open: any error, a missing rule
file, CSA_DISABLE_HOOKS=1 or ~/.claude/.router_off -> exit 0 with no output.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time
from pathlib import Path

CLAUDE = Path(os.environ.get("CLAUDE_DIR") or (Path.home() / ".claude"))
RULES = CLAUDE / "knowledge" / "agent_triggers.json"
STATE_DIR = CLAUDE / ".agent_router_state"
OBLIG_DIR = CLAUDE / ".agent_obligations"
SPEND = CLAUDE / ".agent_budget" / "spend.jsonl"
SPEND_TAIL_BYTES = 2_000_000
MAX_PROMPT_CHARS = 2000
MACHINE_PREFIXES = (
    "This session is being continued from a previous conversation",
    "Read and obey ~/.claude/schedules/",
    "<",
)
SUFFIX = " (advisory; outward acts — push, publish, post, message, spend — still need the operator's go-ahead)"


def _off() -> bool:
    return os.environ.get("CSA_DISABLE_HOOKS") == "1" or (CLAUDE / ".router_off").exists()


def _load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def _state_path(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "nosession")[:80]
    return STATE_DIR / f"{safe}.json"


def _hinted(session: str) -> set[str]:
    try:
        return set(json.loads(_state_path(session).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _mark_hinted(session: str, agent: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    seen = _hinted(session) | {agent}
    _state_path(session).write_text(json.dumps(sorted(seen)), encoding="utf-8")


def dispatched_in_session(session: str, agent: str) -> bool:
    """True when spend.jsonl (tail) shows `agent` dispatched in `session`."""
    if not session:
        return False
    try:
        with open(SPEND, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - SPEND_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    needle_s, needle_a = f'"session": "{session}"', f'"agent_type": "{agent}"'
    return any(needle_s in ln and needle_a in ln for ln in tail.splitlines())


def match_prompt(prompt: str, rules: dict) -> dict | None:
    text = prompt or ""
    for rule in rules.get("prompt_rules", []):
        if any(re.search(p, text, re.I) for p in rule.get("not", [])):
            continue
        anys, alls = rule.get("any", []), rule.get("all", [])
        ok_any = (not anys) or any(re.search(p, text, re.I) for p in anys)
        ok_all = all(re.search(p, text, re.I) for p in alls)
        if (anys or alls) and ok_any and ok_all:
            return rule
    return None


def match_path(path: str, rules: dict) -> dict | None:
    p = os.path.abspath(os.path.expanduser(path or "")).lower()
    name = os.path.basename(p)
    for rule in rules.get("path_rules", []):
        if any(fnmatch.fnmatch(p, g.lower()) for g in rule.get("not_globs", [])):
            continue
        if "name_globs" in rule:
            in_dir = any(fnmatch.fnmatch(p, g.lower()) for g in rule.get("dir_globs", ["*"]))
            named = any(fnmatch.fnmatch(name, g.lower()) for g in rule["name_globs"])
            excluded = any(fnmatch.fnmatch(name, g.lower()) for g in rule.get("not_name_globs", []))
            if in_dir and named and not excluded:
                return rule
            continue
        if any(fnmatch.fnmatch(p, g.lower()) for g in rule.get("globs", [])):
            return rule
    return None


def _emit(event: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def _record_obligation(session: str, rule: dict, path: str) -> None:
    OBLIG_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "nosession")[:80]
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rule": rule["id"],
           "agent": rule["agent"], "path": os.path.abspath(os.path.expanduser(path)), "hint": rule["hint"]}
    with open(OBLIG_DIR / f"{safe}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def handle_prompt(payload: dict, rules: dict) -> str | None:
    session = str(payload.get("session_id") or "nosession")
    prompt = str(payload.get("prompt") or "")
    # Operator messages are short; compaction summaries, scheduled-job prompts and pasted
    # documents are machine text that would false-trigger (measured on the 30-day replay).
    if len(prompt) > MAX_PROMPT_CHARS or prompt.lstrip().startswith(MACHINE_PREFIXES):
        return None
    rule = match_prompt(prompt, rules)
    if not rule:
        return None
    agent = rule["agent"]
    if agent.lower() in prompt.lower() or agent in _hinted(session) or dispatched_in_session(session, agent):
        return None
    _mark_hinted(session, agent)
    return f"Routing hint: {rule['hint']}; bring in `{agent}`{SUFFIX}."


def handle_path(payload: dict, rules: dict) -> str | None:
    session = str(payload.get("session_id") or "nosession")
    tin = payload.get("tool_input") or {}
    path = tin.get("file_path") or tin.get("notebook_path") or ""
    rule = match_path(path, rules)
    if not rule:
        return None
    if rule.get("must"):
        _record_obligation(session, rule, path)
    # Same "already handled" rule as the Stop check: only a hint already given this
    # session suppresses it (an earlier, unrelated dispatch of the agent does not).
    key = f"path:{rule['id']}"
    if key in _hinted(session):
        return None
    _mark_hinted(session, key)
    return f"Routing hint: {rule['hint']} (`{rule['agent']}`){SUFFIX}."


def main(argv: list[str]) -> int:
    if _off():
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        rules = _load_rules()
        if "--path" in argv:
            out = handle_path(payload, rules)
            event = "PostToolUse"
        else:
            out = handle_prompt(payload, rules)
            event = "UserPromptSubmit"
        if out:
            _emit(event, out)
    except Exception:  # noqa: BLE001 — fail open, always
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
