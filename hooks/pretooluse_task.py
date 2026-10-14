#!/usr/bin/env python3
"""pretooluse_task — the PreToolUse:Task dispatcher, registered on the "Task"
matcher in ``settings.json`` in place of the previous direct
``agent_budget.py gate`` invocation.

GATE ORDER (first block wins, mirrors pretooluse_bash.py's own precedent for
gate 3b sitting before gate 4 — "a review-denied commit must not park the
per-repo commit mutex"):

  T1: model_pin_gate    — deny: pin-tier-mismatch | pin-inherit-drift |
                           unpinned-agent-type. See model_pin_gate.py's own
                           module docstring for the full decision tree.
  T2: agent_budget.py's existing `gate` subcommand — UNCHANGED, run ONLY if
                           T1 allows.

A T1 deny means T2's pacer lease / spend-ledger claim is NEVER taken — a
denied dispatch never ran, so it must never park a concurrency slot or record
spend. This mirrors precommit_review_gate.py being ordered before file_claims
in pretooluse_bash.py for the identical reason.

STDIN is read exactly ONCE, here, and threaded to BOTH gates — T2 no longer
reads its own stdin (agent_budget.main() would find it already consumed).
T1 and T2 are called via their pure ``decide()`` functions directly, not by
shelling out to a second process, exactly like pretooluse_bash.py calls its
sibling gate modules' decision functions in-process.

POLICY (identical to pretooluse_bash.py):
  * CSA_DISABLE_HOOKS=1  master OFF — no-op allow before anything else.
  * LOG-ONLY by default: a would-block from T1 is logged (and the dispatch
    proceeds to T2, i.e. allowed) unless _lib.enforcing() resolves ON, at
    which point the canonical PreToolUse deny is emitted and T2 never runs.
  * A deny is ALWAYS via the JSON object, NEVER via a nonzero exit code
    (exit 0 always) — matches every hook in this system.
  * T2's own internal policy (CSA_PACER, CSA_SPEND_LEDGER, CSA_ANTHROPIC_
    CEILING, ...) is entirely unchanged — this module does not alter or
    re-interpret any of it, it only supplies T2 with the already-read event.

Never raises out to the caller: a crashing dispatcher must never break a
dispatch, so every unexpected error degrades to ALLOW (exit 0, no deny) —
matches every other PreToolUse dispatcher in this hook system.
"""

from __future__ import annotations

import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirrors every sibling hook)
import agent_budget as ab  # noqa: E402
import churn_tracker as ct  # noqa: E402  (repo_root_of — same resolver pretooluse_bash uses)
import model_pin_gate as mpg  # noqa: E402

HOOK_NAME = "pretooluse_task"


def _log_fields(ev: dict, where: str, detail: dict | None = None) -> dict:
    """Identity fields MERGED UNDER `detail`, as ONE dict to splat into
    ``_lib.log(**...)`` — see pretooluse_bash._log_fields for the full
    reasoning.

    Short version: `**a, **b` in a call raises ``TypeError: got multiple
    values for keyword argument`` the moment the two dicts share a key, which
    CRASHES the dispatcher and, under enforcement, converts a would-be deny
    into an unguarded allow. `model_pin_gate.decide`'s detail happens not to
    collide today (it uses ``subagent_type``, not ``agent_type``), but the
    same class of crash bit the Bash side for real via gate 5's ``repo`` key,
    so this side is merged the same way rather than relying on two dicts
    staying disjoint forever. `detail` wins any collision: a gate's own field
    is authoritative for its row.
    """
    fields = _identity_safe(ev, where)
    try:
        if detail:
            fields.update(detail)
    except Exception:
        return dict(detail) if isinstance(detail, dict) else {}
    return fields


def _identity_safe(ev: dict, where: str) -> dict:
    """`_identity` behind an OUTER guard — see pretooluse_bash._identity_safe
    for the full reasoning. Short version: the identity dict is SPLATTED into
    ``_lib.log(**...)``, and the splat is evaluated before log() is entered,
    so an exception escaping `_identity` propagates past every guard inside
    log() and crashes the dispatcher — turning a telemetry failure into a
    changed dispatch outcome, which the plan forbids. Every identity call site
    MUST use this, never `_identity` directly.
    """
    try:
        return _identity(ev, where)
    except Exception:
        return {}


def _identity(ev: dict, where: str) -> dict:
    """Identity kwargs for this entry point's enforcement rows (telemetry plan
    §4.2 4a / §4.2a). Returns a dict to splat into ``_lib.log``.

    This is one of the TWO registered PreToolUse entry points that actually
    parse a payload, and it is the ONE that contributes all THREE fields — a
    ``Task`` payload IS a dispatch, so ``tool_input.subagent_type`` exists here
    (the payload asymmetry recorded in the plan: pretooluse_bash's Bash payload
    describes a shell command and has no agent type at all, so it never
    fabricates one).

      session     — ``_lib.session_id``; its "nosession" sentinel is dropped
                    by ``_lib._identity_fields`` itself, never written.
      agent_type  — ``_lib.subagent_type``, the same ``tool_input.subagent_type``
                    agent_budget.py:970 and model_pin_gate.py:623 read.
      repo        — the repo root containing the event's cwd, resolved with the
                    same ``churn_tracker.repo_root_of`` pretooluse_bash uses,
                    so a row from either entry point buckets identically.
                    Falls back to nothing (field omitted) outside a repo.

    FAIL-OPEN (plan §4.2, "all three inherit _lib.log()'s fail-open contract
    explicitly"): every failure degrades to {} — an identity failure costs the
    identity fields, never the log row, and above all never the dispatch. The
    kill-switch is honored here too so the repo-root subprocess is not even
    spawned when identity is turned off.
    """
    try:
        if not _lib.log_identity_enabled():
            return {}
        out = {
            "session": _lib.identity_or_none(_lib.session_id(ev)),
            "agent_type": _lib.identity_or_none(_lib.subagent_type(ev)),
        }
        try:
            out["repo"] = _lib.identity_or_none(ct.repo_root_of(where)) if where else None
        except Exception:
            out["repo"] = None
        return out
    except Exception:
        return {}


def apply_t1(ev: dict) -> bool:
    """Run gate T1 (model_pin_gate) and apply the SAME log-only-vs-enforcing
    policy every gate in pretooluse_bash.py already follows. Returns True iff
    the dispatch may proceed to T2 (allowed outright, OR would-block but not
    currently enforcing — the universal log-only default in this hook
    system). Never raises: any error inside decide() already degrades to
    ALLOW per its own contract; this wrapper adds no further failure surface
    beyond the logging/emission calls, which are themselves best-effort.
    """
    block, reason, detail = mpg.decide(ev)
    if not block:
        return True
    where = _lib.cwd(ev)
    enforce = _lib.enforcing(where)
    _lib.log(
        HOOK_NAME,
        "would-block",
        gate=mpg.HOOK_NAME,
        reason=reason,
        enforce=enforce,
        **_log_fields(ev, where, detail),
    )
    if enforce:
        _lib.emit_pretooluse_deny(mpg.message_for(reason, detail))
        return False
    # Log-only default: allow the dispatch through to T2, unchanged from
    # every other gate's log-only behavior in this hook system.
    return True


def apply_t2(ev: dict) -> int:
    """Run gate T2: agent_budget.py's existing `gate` subcommand, UNCHANGED.
    Calls its pure decide()/apply_decision() directly with the ALREADY-READ
    event (`ev`) as `payload`, rather than shelling out to a second process
    — agent_budget.main() reads its own stdin, which would be empty here
    since this dispatcher already consumed it.
    """
    environ = os.environ
    agent_id = ab._gate_agent_id(ev)
    decision = ab.decide(["gate"], environ, _lib.AGENT_BUDGET_DIR, agent_id, payload=ev)
    return ab.apply_decision(decision, _lib.AGENT_BUDGET_DIR, sys.stdout, sys.stderr)


def main() -> int:
    """Entry point. Reads stdin ONCE, runs T1 then (conditionally) T2,
    returns 0 always."""
    if _lib.disabled():
        return 0
    try:
        ev = _lib.read_event()
        if not apply_t1(ev):
            # T1 denied under enforcement — T2's lease/claim must never be
            # taken for a dispatch that was just refused.
            return 0
        return apply_t2(ev)
    except Exception:
        # Absolute last resort: a crashing dispatcher must never break a
        # dispatch (matches agent_budget.main()'s own outermost guard).
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
