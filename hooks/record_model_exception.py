#!/usr/bin/env python3
"""record_model_exception — mint the single-use, TTL'd, DISPATCH-BOUND token
that ``model_pin_gate.py``'s decision 6 consumes to let ONE off-pin dispatch
through.

Run BEFORE the dispatch it authorizes, with the EXACT prompt text you are
about to hand to the ``Task`` call saved to a scratch file first:

    python3 record_model_exception.py --agent <subagent_type> \\
        --model <cheaper-or-more-expensive-model> --reason <reason> \\
        --paths <pathspec...> --prompt-file <path-to-the-exact-prompt-text>

REASON VOCABULARY IS CLOSED — exactly TWO values (``operator-directed`` was
REMOVED 2026-09-01 fix round, see B1 below), each independently VERIFIED
before minting (never trusted from the caller's own word):

  * ``trivial-tier-confirmatory`` — mints ONLY when
    ``review_risk_tier.classify(paths)`` returns literally ``"trivial"`` for
    the given pathspec (CLAUDE.md §10's sanctioned cheaper-confirmatory-pass
    downgrade). Any other tier (including ``moderate``) refuses to mint.
  * ``escalation-hard-debugging`` — upward-only, and NARROWLY sonnet->opus
    only (B5): mints ONLY when the agent's resolved policy pin is literally
    ``"sonnet"`` AND the target model is a HIGHER tier
    (``model_pin_gate.TIER_ORDER``) than that pin. An agent already pinned
    ``opus`` (or higher) escalating "further" is refused outright — this
    reason authorizes "sonnet couldn't crack a genuinely hard debugging
    problem, try opus," not "make an already-expensive agent more
    expensive." Requires a non-empty ``--justification`` (logged prominently
    via ``_lib.log`` to ``~/.claude/.enforcement/log.jsonl``, in addition to
    the durable ``grants.jsonl`` audit trail below, so a real human reason
    is always attached and auditable, never a blank checkbox).

NEITHER REASON CAN EVER TARGET ``fable`` (B5) — refused UNCONDITIONALLY,
before any reason-specific verification runs, regardless of the stated
direction or justification. fable is 2x Opus 5 pricing and
``model_pin_parity.py``'s own ``unsanctioned-fable-dispatch`` check flags
every fable dispatch by design; nothing self-serve may ever mint one. The
ONLY path to a fable dispatch is the operator-grant mechanism below.

REMOVED: ``operator-directed`` (B1). The old version of this reason checked
``CSA_MODEL_EXCEPTION=1`` in THIS process's OWN environment — but this
script is a CLI an AGENT invokes via its own Bash tool call, so the agent
could simply write ``CSA_MODEL_EXCEPTION=1 python3 record_model_exception.py
...`` itself. The ``block_branch_ops.ESCAPE_VAR`` analogy it was modeled on
does not hold: that is a PreToolUse HOOK reading the SESSION's own launch
environment (which an individual Bash call cannot set), not a CLI script
reading whatever env that SAME Bash call sets inline. There was never a real
human gate here. The genuine operator-only mechanism now lives entirely
outside this script, at ``~/.claude/scripts/grant_model_exception.sh`` — run
by the OPERATOR directly in their own terminal (never referenced by any
agent-facing hook/denial message, never invoked by this script, never
something any agent tool grant lets an agent substitute for) — see that
script's own header and ``model_pin_gate.find_and_consume_operator_grant``.

TOKEN
-----
Single-use, 15-minute TTL (``model_pin_gate.EXCEPTION_TTL_SECONDS``), written
atomically to ``~/.claude/.model_exceptions/<random-id>.json`` carrying
``{agent_type, model, reason, paths, risk_tier_verdict, prompt_sha256,
justification, minted_at, expires_at}``.
``model_pin_gate.find_and_consume_exception`` looks it up by
``(agent_type, model, prompt_sha256)`` and deletes it (atomically, single-use
— B4) on a match — this module never deletes its own token; consumption is
the GATE's job, minting is this module's.

``prompt_sha256`` (B2) is the SHA-256 of the ``--prompt-file`` contents —
REQUIRED for both remaining reasons. This binds the minted token to the
EXACT dispatch it was minted for: the token cannot be replayed against a
DIFFERENT prompt even when ``(agent_type, model)`` match (the real incident
this closes: a token minted against a README-only review's prompt text was
spent authorizing a firestore.rules review, because the pre-fix token only
checked ``(agent_type, model)``). RESIDUAL LIMITATION, stated honestly
rather than oversold: this binds the exact literal prompt BYTES, not
"semantic intent" — it does NOT verify that ``--paths`` (the argument
``verify_trivial`` actually classifies) truthfully describes what the bound
prompt text will do; that would require parsing the prompt's own content for
path references, which is not reliably achievable and is out of scope here.
What IS closed: accidental or opportunistic reuse of a stale/leftover token
across a semantically different dispatch. What is NOT closed: an agent that
deliberately mints against a trivial pathspec while intending (and binding)
a prompt that does something else entirely — that would require an active
falsification at mint time, a materially higher bar than "reuse an old
token," and is not something byte-exact prompt binding can further narrow.

AUDIT TRAIL
-----------
Every successful mint is ALSO appended, append-only, to
``~/.claude/.model_exceptions/grants.jsonl`` — durable even after the
ephemeral per-token file is consumed/deleted, so ``model_pin_parity.py``'s
report-only ``pin-tier-mismatch`` cross-reference (item 6 of this build) can
suppress a spend-ledger row that a real, verified exception actually covered.
An ``escalation-hard-debugging`` mint is ALSO logged via ``_lib.log`` (so it
surfaces in the normal ``~/.claude/.enforcement/log.jsonl`` telemetry stream,
not only the exceptions directory) carrying the full ``--justification``
text.

STRUCTURE (per the hook-system contract): every verification function below
is PURE (no I/O beyond the one classify()/file read it explicitly
documents); ``mint_token`` and ``_append_grant_log`` are the only
side-effectful writes, isolated so the verification logic is testable
without touching disk twice. This is a CLI tool run directly by an
agent/operator, not a PreToolUse hook — it exits non-zero on refusal (unlike
every hook in this system, which always exits 0 and denies via JSON): there
is no tool call to deny here, only a mint request to accept or refuse, and a
caller scripting against this needs a real exit code to detect refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirrors every sibling hook --
# used here ONLY for its audit-trail log() call on an escalation mint, see B5)
import model_pin_gate as mpg  # noqa: E402
import review_risk_tier as rrt  # noqa: E402

REASON_TRIVIAL = "trivial-tier-confirmatory"
REASON_ESCALATION = "escalation-hard-debugging"
# REASON_OPERATOR ("operator-directed") REMOVED 2026-09-01 fix round (B1) --
# it was agent-self-serve in practice (CSA_MODEL_EXCEPTION=1 was readable
# from the SAME Bash call that invokes this CLI), never a genuine human
# gate. The real operator-only mechanism is now
# ~/.claude/scripts/grant_model_exception.sh, entirely outside this module.
REASONS = (REASON_ESCALATION, REASON_TRIVIAL)

# The escalation reason's ONLY sanctioned source pin (B5) -- see
# verify_escalation's own docstring for why "any upward direction" was too
# permissive (it let an already-opus-pinned agent self-mint further up,
# including — before the FABLE_MODEL guard below — all the way to fable).
_ESCALATION_SOURCE_PIN = "sonnet"


# ---------------------------------------------------------------------------
# PURE verification — one function per reason, each independently checked.
# ---------------------------------------------------------------------------


def verify_trivial(paths: list[str]) -> tuple[bool, str, str]:
    """(ok, message, risk_tier_verdict). Mints ONLY on a literal
    ``review_risk_tier.TRIVIAL`` verdict for the exact pathspec supplied.

    Deliberately calls ``classify(paths)`` with NO ``extra_keywords`` (unlike
    ``record_review.py``'s tier-telemetry call, which threads the calling
    repo's ``security.extra_risk_keywords`` through explicitly) -- this is
    safe, not an oversight: `extra_keywords` only ever WIDENS a verdict
    toward HIGH, never narrows it, so omitting it here can only make this
    gate MORE conservative (a path that would classify HIGH with extra
    keywords still classifies at least as risky without them) -- it can
    never cause a false TRIVIAL mint. Do not "fix" this into a semantic
    change without re-deriving that widen-only invariant first.
    """
    tier, reason = rrt.classify(paths)
    verdict = f"{tier}: {reason}"
    if tier != rrt.TRIVIAL:
        return (
            False,
            f"refused: --reason {REASON_TRIVIAL} requires review_risk_tier.classify() to "
            f"return 'trivial' for these paths; got '{tier}' ({reason}). Run a full Opus "
            "review instead, or pass a genuinely trivial (docs-only/lock-file) pathspec.",
            verdict,
        )
    return True, "ok", verdict


def verify_escalation(model: str, pin: str | None) -> tuple[bool, str]:
    """(ok, message). Mints ONLY when ALL of: (B5) the target is never
    ``fable`` (checked by the caller, ``run()``, before this is even called
    — see its own docstring), the agent's resolved pin is LITERALLY
    ``"sonnet"`` (escalating FROM sonnet for genuine hard-debugging is what
    this reason authorizes; an agent already pinned ``opus`` or higher
    escalating "further" is not — the pre-fix version had no such
    restriction, so ANY pinned agent could self-mint an upward hop), and
    ``model`` ranks strictly above the pin in TIER_ORDER. Refuses a
    downgrade, refuses a lateral "escalation", and refuses when the pin
    itself is unknown (nothing to verify direction against)."""
    if not pin:
        return (
            False,
            f"refused: --reason {REASON_ESCALATION} requires a known policy pin for this "
            "agent to verify direction against; none found in agent_pins or the agent's "
            "own frontmatter.",
        )
    if pin != _ESCALATION_SOURCE_PIN:
        return (
            False,
            f"refused: --reason {REASON_ESCALATION} requires the agent's resolved pin to be "
            f"'{_ESCALATION_SOURCE_PIN}' (escalating FROM {_ESCALATION_SOURCE_PIN} to a "
            f"harder tier for genuine hard-debugging); '{pin}' is not eligible -- an "
            "already-opus-(or-higher)-pinned agent escalating further is not what this "
            "reason authorizes.",
        )
    pin_rank = mpg.TIER_ORDER.get(pin)
    model_rank = mpg.TIER_ORDER.get(model)
    if pin_rank is None or model_rank is None:
        return (
            False,
            f"refused: --reason {REASON_ESCALATION} cannot rank pin '{pin}' vs. model "
            f"'{model}' (one or both is not a recognized tier name: "
            f"{sorted(mpg.TIER_ORDER)}).",
        )
    if model_rank <= pin_rank:
        return (
            False,
            f"refused: --reason {REASON_ESCALATION} requires the target model to be a "
            f"HIGHER tier than the pin ('{pin}'); '{model}' is not an upward escalation.",
        )
    return True, "ok"


# ---------------------------------------------------------------------------
# Dispatch-prompt binding (B2) — the caller must supply the EXACT prompt text
# it is about to hand to the Task call, saved to a scratch file; this module
# hashes that file's contents the SAME way model_pin_gate.dispatch_prompt_hash
# hashes the live tool_input.prompt at consumption time, so a mismatch (a
# different dispatch, even with the same agent_type/model) can never spend
# this token.
# ---------------------------------------------------------------------------


def read_prompt_hash(prompt_file: str) -> str | None:
    """SHA-256 hex digest of ``prompt_file``'s exact contents, or None if the
    file cannot be read (caller treats None as a refusal — never silently
    mints an unbound token)."""
    try:
        with open(prompt_file, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Side-effectful minting — isolated so verification is tested without disk IO.
# ---------------------------------------------------------------------------


def mint_token(
    exceptions_dir: str,
    agent_type: str,
    model: str,
    reason: str,
    paths: list[str],
    risk_tier_verdict: str | None,
    prompt_sha256: str,
    *,
    justification: str = "",
    now: datetime | None = None,
    ttl_seconds: int = mpg.EXCEPTION_TTL_SECONDS,
) -> dict:
    """Write the token file atomically (temp file + os.replace, mirroring
    every other small-table writer in this hook system — e.g.
    agent_budget._write_table) and append the durable grant-log line.
    Returns the minted record (never raises; a write failure propagates as
    whatever exception the caller's own try/except around main() handles —
    minting is the whole point of this call, so silently swallowing a write
    failure here would report success for a token that was never actually
    written).

    ``prompt_sha256`` (B2) is REQUIRED (not optional) — every token minted by
    this module is dispatch-bound; there is no "unbound" token shape a
    caller can request."""
    now = now or datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    record = {
        "agent_type": agent_type,
        "model": model,
        "reason": reason,
        "paths": sorted(set(p for p in paths if p)),
        "risk_tier_verdict": risk_tier_verdict,
        "prompt_sha256": prompt_sha256,
        "justification": justification,
        "minted_at": mpg.format_ts(now),
        "expires_at": mpg.format_ts(expires),
    }
    os.makedirs(exceptions_dir, exist_ok=True)
    token_id = uuid.uuid4().hex
    path = os.path.join(exceptions_dir, f"{token_id}.json")
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    os.replace(tmp, path)
    _append_grant_log(exceptions_dir, record)
    return record


def _append_grant_log(exceptions_dir: str, record: dict) -> None:
    """Best-effort append to grants.jsonl — the durable audit trail
    model_pin_parity.py's pin-tier-mismatch cross-reference reads. A failure
    here must never undo an already-written, already-successful mint (the
    token itself is the thing that actually authorizes a dispatch); it is
    swallowed, matching every other append-only log in this hook system
    (_lib.log's own contract)."""
    path = os.path.join(exceptions_dir, mpg.GRANTS_LOG_NAME)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except Exception:
        return


# ---------------------------------------------------------------------------
# Orchestration — pure w.r.t. paths/env (all resolved by the caller), so this
# is directly unit-testable without patching module-level constants.
# ---------------------------------------------------------------------------


def run(
    agent_type: str,
    model: str,
    reason: str,
    paths: list[str],
    prompt_file: str,
    *,
    agents_dir: str,
    policy_path: str,
    exceptions_dir: str,
    justification: str = "",
    now: datetime | None = None,
) -> tuple[int, str]:
    """(exit_code, message). 0 + a confirmation on success; nonzero + the
    refusal reason otherwise. Never raises out — any unexpected failure
    (e.g. an unreadable policy) is reported as a refusal, never a silent
    mint.

    ``environ`` was REMOVED (B1) along with ``REASON_OPERATOR`` — nothing in
    this module reads process environment to authorize a mint anymore."""
    try:
        if reason not in REASONS:
            return 2, f"refused: --reason must be one of {REASONS}, got {reason!r}."

        # B5, defense-in-depth (mirrors model_pin_gate.find_and_consume_
        # exception's own hard refusal): NO self-serve reason may ever mint
        # an exception targeting fable, checked BEFORE any reason-specific
        # verification runs, regardless of stated direction/justification.
        if model == mpg.FABLE_MODEL:
            return (
                1,
                f"refused: no self-serve --reason may mint an exception targeting "
                f"'{mpg.FABLE_MODEL}' -- this requires the operator to run "
                "~/.claude/scripts/grant_model_exception.sh themselves, in their own "
                "terminal.",
            )

        # B2: every token this module mints is dispatch-bound. No reason may
        # skip this -- there is no "unbound" token shape.
        prompt_hash = read_prompt_hash(prompt_file)
        if prompt_hash is None:
            return (
                1,
                f"refused: --prompt-file {prompt_file!r} is unreadable -- every minted "
                "token must be bound to the exact prompt text of the dispatch it "
                "authorizes.",
            )

        pins = mpg.load_pins(policy_path)
        if pins is None:
            return (
                1,
                "refused: model_policy.json is unreadable or has no agent_pins mapping — "
                "cannot verify anything against an unknown policy.",
            )
        agent_file_pins = mpg.scan_agent_pins(agents_dir)
        if agent_file_pins is None:
            return 1, f"refused: agents dir {agents_dir!r} is unreadable."
        pin = mpg.resolved_pin(agent_type, pins, agent_file_pins)

        verdict: str | None = None
        if reason == REASON_TRIVIAL:
            ok, msg, verdict = verify_trivial(paths)
        else:  # REASON_ESCALATION
            if not justification.strip():
                return (
                    1,
                    f"refused: --reason {REASON_ESCALATION} requires a non-empty "
                    "--justification (logged prominently and auditably -- never a blank "
                    "checkbox).",
                )
            ok, msg = verify_escalation(model, pin)

        if not ok:
            return 1, msg

        record = mint_token(
            exceptions_dir,
            agent_type,
            model,
            reason,
            paths,
            verdict,
            prompt_hash,
            justification=justification,
            now=now,
        )
        if reason == REASON_ESCALATION:
            _lib.log(
                "record_model_exception",
                "mint-escalation",
                agent_type=agent_type,
                model=model,
                pin=pin,
                justification=justification,
                expires_at=record["expires_at"],
            )
        return (
            0,
            f"OK minted model exception for agent={agent_type} model={model} "
            f"reason={reason} expires_at={record['expires_at']}",
        )
    except Exception as exc:
        return (
            1,
            f"refused: unexpected error minting exception: {exc.__class__.__name__}: {exc}",
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="record_model_exception.py",
        description="Mint a single-use, TTL'd, dispatch-bound exception for one off-pin "
        "Task dispatch.",
    )
    p.add_argument(
        "--agent", required=True, dest="agent_type", help="the subagent_type"
    )
    p.add_argument("--model", required=True, help="the target model of the dispatch")
    p.add_argument("--reason", required=True, choices=sorted(REASONS))
    p.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="pathspec (required for trivial-tier-confirmatory)",
    )
    p.add_argument(
        "--prompt-file",
        required=True,
        dest="prompt_file",
        help="path to a scratch file holding the EXACT prompt text of the dispatch this "
        "token will authorize (B2) -- the minted token binds to its SHA-256",
    )
    p.add_argument(
        "--justification",
        default="",
        help="required, non-empty for --reason escalation-hard-debugging -- logged "
        "prominently to ~/.claude/.enforcement/log.jsonl",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    code, message = run(
        args.agent_type,
        args.model,
        args.reason,
        args.paths,
        args.prompt_file,
        agents_dir=mpg.DEFAULT_AGENTS_DIR,
        policy_path=mpg.DEFAULT_POLICY_PATH,
        exceptions_dir=mpg.DEFAULT_EXCEPTIONS_DIR,
        justification=args.justification,
    )
    stream = sys.stdout if code == 0 else sys.stderr
    print(f"record_model_exception: {message}", file=stream)
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
