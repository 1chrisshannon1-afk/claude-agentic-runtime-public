#!/usr/bin/env python3
"""agent_obligations.py — Stop hook: the operator's "must" review rules, enforced once.

Auto-invocation design (agentic-systems-architect, 2026-09-28), commit 3.
hooks/agent_router.py --path records an obligation in
~/.claude/.agent_obligations/<session>.jsonl whenever a must-rule path is written:
  - an agent definition (*/.claude/agents/*.md) -> agentic-systems-architect review
    (operator rule 2026-09-28: every new or changed agent is ASA-reviewed + carded);
  - a plan file -> plan-reviewer (CLAUDE.md §10).

At Stop, an obligation is CLEARED when any of these holds:
  1. spend.jsonl (completed) or claims.jsonl (in flight) shows the required agent
     dispatched in this session at or after the FIRST edit's obligation timestamp (the
     first qualifying review clears the file for the session — deliberate anti-nag);
  2. the file is back to its HEAD content (tracked and `git diff --quiet HEAD`), or gone;
  3. (plan-reviewer only) ~/.claude/.review_state/plan_reviews.jsonl logged that plan
     at or after the obligation.
If any obligation is still open, the hook blocks the stop ONCE with a one-paragraph
reason naming each file and agent, then marks them reminded (never blocks twice for
the same obligation). `stop_hook_active` true -> allow. Registered on Stop only, never
SubagentStop (sub-agents cannot dispatch). Fails open on any error, on
CSA_DISABLE_HOOKS=1, or with ~/.claude/.router_off present.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CLAUDE = Path(os.environ.get("CLAUDE_DIR") or (Path.home() / ".claude"))
OBLIG_DIR = CLAUDE / ".agent_obligations"
SPEND = CLAUDE / ".agent_budget" / "spend.jsonl"
CLAIMS = CLAUDE / ".agent_budget" / "claims.jsonl"
PLAN_LEDGER = CLAUDE / ".review_state" / "plan_reviews.jsonl"
TAIL = 3_000_000


def _off() -> bool:
    return os.environ.get("CSA_DISABLE_HOOKS") == "1" or (CLAUDE / ".router_off").exists()


def _tail_lines(path: Path) -> list[str]:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL))
            return fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _rows(path: Path) -> list[dict]:
    out = []
    for ln in _tail_lines(path):
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def dispatched_since(session: str, agent: str, ts: str) -> bool:
    """A completed dispatch (spend.jsonl) or an in-flight one (claims.jsonl, written at
    claim time; background dispatches only reach spend.jsonl at SubagentStop)."""
    return any(r.get("session") == session and r.get("agent_type") == agent and str(r.get("ts", "")) >= ts
               for src in (SPEND, CLAIMS) for r in _rows(src))


def plan_reviewed_since(plan: str, ts: str) -> bool:
    plan = os.path.abspath(plan)

    def _abs(r: dict) -> str:
        raw = str(r.get("plan", ""))
        return os.path.abspath(raw if os.path.isabs(raw) else os.path.join(str(r.get("repo", "")), raw))

    return any(_abs(r) == plan and str(r.get("ts", "")) >= ts for r in _rows(PLAN_LEDGER))


def back_to_head(path: str) -> bool:
    p = Path(path)
    if not p.exists():
        return True
    try:
        top = subprocess.run(["git", "-C", str(p.parent), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if top.returncode != 0:
            return False
        tracked = subprocess.run(["git", "-C", top.stdout.strip(), "ls-files", "--error-unmatch", str(p)],
                                 capture_output=True, text=True, timeout=5)
        if tracked.returncode != 0:
            return False
        diff = subprocess.run(["git", "-C", top.stdout.strip(), "diff", "--quiet", "HEAD", "--", str(p)],
                              capture_output=True, timeout=5)
        return diff.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def open_obligations(session: str) -> tuple[list[dict], Path]:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "nosession")[:80]
    path = OBLIG_DIR / f"{safe}.jsonl"
    rows = _rows(path)
    reminded = {(r.get("rule"), r.get("path")) for r in rows if r.get("reminded")}
    seen, pending = set(), []
    for r in rows:
        if r.get("reminded"):
            continue
        key = (r.get("rule"), r.get("path"))
        if key in reminded or key in seen:
            continue
        seen.add(key)
        agent, ts, p = r.get("agent", ""), r.get("ts", ""), r.get("path", "")
        if dispatched_since(session, agent, ts) or back_to_head(p):
            continue
        if agent == "plan-reviewer" and plan_reviewed_since(p, ts):
            continue
        pending.append(r)
    return pending, path


def main() -> int:
    if _off():
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if payload.get("stop_hook_active"):
            return 0
        session = str(payload.get("session_id") or "nosession")
        pending, path = open_obligations(session)
        if not pending:
            return 0
        items = "; ".join(f"{os.path.basename(r['path'])} → `{r['agent']}`" for r in pending)
        reason = ("Before stopping: these changes still need their required review (operator standing "
                  f"rules): {items}. Unless it is already dispatched or in flight, dispatch the named agent now (agent files: also add or refresh the "
                  "card on ~/.claude/plans/agent_roster_tracker.html; plans: record_plan_review.py after). "
                  "If a file is not actually a plan or an agent definition, say so and stop. This reminder fires once.")
        with open(path, "a", encoding="utf-8") as fh:
            for r in pending:
                fh.write(json.dumps({"rule": r.get("rule"), "path": r.get("path"), "reminded": True}) + "\n")
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception:  # noqa: BLE001 — fail open, always
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
