#!/usr/bin/env python3
"""workflow_model_gate — PreToolUse:Workflow guard: every agent() must name its model.

WHY THIS EXISTS (measured, 2026-09-23)
--------------------------------------
Workflow `agent()` calls with no `model:` option inherit the MAIN SESSION's model.
Nothing stopped that: the `PreToolUse:Task` chain (`model_pin_gate.py`) governs
`Task` dispatches only, and Workflow legs never reach it. They also never appear
in `.agent_budget/spend.jsonl`, so the pacer's ceiling and every after-the-fact
spend audit are blind to them.

Measured that day, from the workflow transcripts themselves:
  wf_27a8cea0-783   3,284 calls on claude-fable-5-1   <- exhausted an account mid-run
  wf_14ca2c33-11c     531 calls on claude-opus-5
  wf_9c410c92-605     370 calls on claude-opus-5
None of those scripts passed `model:` on any `agent()` call. None appeared in the
spend ledger. Fable is 2x Opus pricing; a 3,284-call Fable fan-out is the
single most expensive shape this runtime can produce. (At measurement time, fable
was sanctioned via two standing pins, `plan-reviewer` and `marketing-director`;
both are retired as of the 2026-09-24 operator directive repinning them to
opus, so fable is reachable today only through the single-use operator-grant
path — the cost-cliff risk this gate exists to prevent is unchanged either way.)

A memory entry already told agents to pass `model:` explicitly. It did not hold,
because memory is advice and this is a cost cliff — the same reason
`check_workflow_agent_purity.py` exists ("a prose-only rule on a Workflow script's
largest agent population is the known weak shape in this runtime"). This module is
that checker's rule, applied to EVERY Workflow call rather than only the saved
`issue-wheel-*.js` files.

PARSING IS DELEGATED, NOT REIMPLEMENTED (code-reviewer round 1, 2026-09-23)
--------------------------------------------------------------------------
The first cut of this module hand-rolled its own paren/quote scanner. An Opus
review measured it against the REAL scripts on disk and found it denied BOTH of
them — including `workflows/issue-wheel-triage.js`, which the nightly ISSUE WHEEL
runs unattended — with a 100% false-deny rate, while also false-ALLOWING a genuine
cost cliff. Four defects, all of which `check_workflow_agent_purity.py` had already
solved:

  1. No comment handling. An apostrophe in an ordinary `//` comment ("we don't
     want opus here") opened a phantom string literal that ran to EOF and swallowed
     the real `model:` key below it. This alone denied every real script.
  2. `agent(` appearing INSIDE a comment was counted as a call site.
  3. The `model:` search ran over the whole call text, so a nested schema property
     named `model` (`{schema: {properties: {model: ...}}}`) satisfied it — a false
     ALLOW on exactly the shape this gate exists to stop. That had already been
     caught and fixed once on the sibling, by a prior code-reviewer round.
  4. Options passed by variable or spread (`agent(opts)`, `agent({...base})`)
     were denied with a message telling the author to do what they had already done.

So this module now calls `check_workflow_agent_purity.find_agent_call_sites()`,
which strips comments before locating call sites, scans the ORIGINAL source for
balanced parens (string-aware), and extracts ONLY the trailing options object
before reading `model:` out of it. Defects 1-3 are structurally gone. Defect 4 is
handled here instead: a call site whose options could not be extracted as a literal
object is treated as UNKNOWN and allowed, never denied — see `_ALLOW_UNPARSEABLE`.

Do not reintroduce a local parser. If the scanning needs to change, change it in
`check_workflow_agent_purity.py` so both consumers get the fix.

WHAT IT DOES
------------
Parses the `script` (or reads `scriptPath`) out of the Workflow tool input and
DENIES when any `agent()` call site has no literal `model:` key in its own trailing
options object. The message names the offending call sites so the fix is mechanical.

DELIBERATELY NOT ENFORCED HERE: which model is chosen. `'opus'` on a judge stage is
legitimate; `'fable'` on a wide leg is not, but that is a judgement this gate does
not make — and it is why `_ALLOWED_MODELS` (the sibling's `{"sonnet"}`-only value
check) is NOT applied. Naming the model is the mechanical part, and it is what was
missing: an author who types `model:` has made a choice, which is the whole point.

SAFETY
------
Fails OPEN on any parse/IO error: a gate outage must never wedge a turn. Honors
CSA_DISABLE_HOOKS=1. Honors `_lib.enforcing()`.

NOTE ON "OBSERVER-FIRST": enforcement is GLOBALLY ON on this machine
(`~/.claude/.enforce` exists, `_lib.enforcing()` precedence step 3), so this gate
DENIES from the moment it lands — it does not get a log-only shakedown period. The
first cut's docstring claimed otherwise and was wrong; that false belief is what
made shipping a 100%-false-deny scanner feel safe. Every deny AND every log-only
would-deny is written to `~/.claude/.enforcement/log.jsonl` via `_lib.log`.
"""
from __future__ import annotations

import json
import os
import sys

_HOOKS = os.path.dirname(os.path.abspath(__file__))
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

HOOK_NAME = "workflow_model_gate"

# A call site whose trailing options object could not be extracted as a literal
# (options passed by variable, or spread from another object) is ALLOWED, not
# denied. `find_agent_call_sites` falls back to the whole call text in that case,
# so `model` stays None for `agent(opts)` even when `opts` genuinely sets it —
# and the author has no way to satisfy a literal-key check through an identifier.
# Denying there would block legitimate, compliant scripts with a message telling
# the author to add something they already added. The cost of this allowance is a
# narrow bypass; the cost of the alternative is false-denying real work.
_ALLOW_UNPARSEABLE = True


def _line_of(source: str, span_text: str, from_index: int) -> tuple[int, int]:
    """Return (1-based line number, index just past this span) for a call site.

    `AgentCallSite` carries its matched text but no offset, so locate each span
    in order, resuming past the previous one — this keeps repeated identical call
    texts from all reporting the first one's line.
    """
    idx = source.find(span_text, from_index)
    if idx < 0:
        return (0, from_index)
    return (source.count("\n", 0, idx) + 1, idx + 1)


def missing_model_lines(script: str) -> tuple[list[int], int]:
    """Return (lines lacking an explicit model, total call sites examined)."""
    from check_workflow_agent_purity import find_agent_call_sites  # type: ignore

    sites = find_agent_call_sites(script)
    missing: list[int] = []
    cursor = 0
    for site in sites:
        line, cursor = _line_of(script, site.span_text, cursor)
        if site.model:
            continue
        if _ALLOW_UNPARSEABLE and (
            "{" not in site.span_text  # agent(opts) — options are an identifier
            or "..." in site.span_text  # agent({...base}) — spread from elsewhere
        ):
            # The options are not a self-contained object literal, so `model`
            # may legitimately be set somewhere this check cannot see. Cannot be
            # judged; do not deny. See _ALLOW_UNPARSEABLE for why allowing beats
            # denying here.
            continue
        missing.append(line)
    return missing, len(sites)


def main() -> int:
    if os.environ.get("CSA_DISABLE_HOOKS", "0") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open

    if (payload.get("tool_name") or payload.get("tool") or "") != "Workflow":
        return 0

    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(ti, dict):
        return 0

    script = ti.get("script")
    if not script:
        path = ti.get("scriptPath")
        if path:
            try:
                with open(os.path.expanduser(path), encoding="utf-8") as fh:
                    script = fh.read()
            except Exception:
                return 0  # fail open
    if not script or not isinstance(script, str):
        return 0

    try:
        missing, total = missing_model_lines(script)
    except Exception:
        return 0  # fail open — a parser change upstream must never wedge a turn

    if not missing:
        return 0

    shown = ", ".join(f"line {ln}" for ln in missing[:8])
    if len(missing) > 8:
        shown += f", and {len(missing) - 8} more"
    msg = (
        f"{HOOK_NAME}: {len(missing)} of {total} agent() call(s) do not name a model "
        f"({shown}).\n"
        "A Workflow agent() with no `model:` INHERITS THE SESSION MODEL. Measured 2026-09-23: "
        "one such fan-out ran 3,284 calls on Fable (2x Opus pricing) and exhausted an account "
        "mid-run. Workflow legs bypass the Task model-pin gate AND never appear in the spend "
        "ledger, so nothing else catches this.\n"
        "Fix: pass an explicit model on every agent() call -- 'sonnet' for read/find/extract "
        "stages, 'opus' only for a judge/verify stage that genuinely needs it."
    )

    try:
        from _lib import enforcing  # type: ignore

        enforce = bool(enforcing())
    except Exception:
        enforce = False

    try:
        from _lib import log  # type: ignore

        log(
            HOOK_NAME,
            "deny" if enforce else "log-only",
            lines=missing,
            total_sites=total,
            would_deny=True,
        )
    except Exception:
        pass

    if not enforce:
        print(msg, file=sys.stderr)
        return 0

    try:
        from _lib import emit_pretooluse_deny  # type: ignore

        emit_pretooluse_deny(msg)
    except Exception:
        # Canonical shape, inlined only as a fallback if _lib is unavailable.
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": msg,
                    },
                    "systemMessage": msg,
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
