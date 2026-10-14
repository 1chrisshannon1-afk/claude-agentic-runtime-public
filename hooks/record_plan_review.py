#!/usr/bin/env python3
"""record_plan_review — log-only ledger of plan-review outcomes.

WHY THIS EXISTS
---------------
Pre-commit code review (record_review.py / precommit_review_gate.py) has an
outcome-aware ledger: every review's actual finding (clean vs N blockers) is
recorded, so its catch rate is measurable. Plan review has never had this --
zero log entries exist anywhere for it (verified 2026-08-20: no hook
registration, no logging integration, nothing in
~/.claude/.enforcement/log.jsonl), so "does plan review actually catch
things, or is it a rubber stamp" has been an unanswerable question since the
agent existed.

This module is the plan-review analog of record_review.py's outcome
recording, deliberately smaller in scope:
  * LOG-ONLY, always. There is no gate that reads this ledger and blocks
    anything -- unlike gate 3b, nothing currently enforces "a plan must have
    a recorded review before implementation starts." Building that
    enforcement (keyed to a plan-content digest, checked at an ExitPlanMode
    boundary) is a real, separate, larger decision that would add a new
    friction point -- this module only makes the DATA exist so that
    decision can eventually be made on evidence instead of a guess.
  * Append-only JSONL, one line per review. No idempotency/update logic
    (unlike last_reviewed's outcome-aware rewrite): a plan is reviewed once
    per revision in practice, and even a duplicate line costs nothing since
    nothing gates on this file's content -- it is pure audit trail.

Usage:
    python3 ~/.claude/hooks/record_plan_review.py <repo> --clean          --plan <path>
    python3 ~/.claude/hooks/record_plan_review.py <repo> --blockers <n>   --plan <path>

Ledger: ~/.claude/.review_state/plan_reviews.jsonl
Each line: {"ts": "...", "repo": "...", "plan": "...", "outcome": "clean"|"blockers",
            "blockers": <n>}

Never raises out to its caller: a crashing hook must not break the agent.
Every failure degrades to a silent (but printed) no-op, matching every
other module in this package. Recording is never a deny/block -- this
module emits no PreToolUse decision and no Stop block, only a log line.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

HOOK = "record_plan_review"


def _parse_int(raw: str) -> int | None:
    try:
        return int(raw)
    except Exception:
        return None


def parse_argv(argv: list[str]) -> tuple[str | None, str | None, int | None, str | None]:
    """Pure parse: (target, outcome, blockers, plan_path) from CLI argv (no argv[0]).

    `outcome` is "clean", "blockers", or None (neither flag given, or a
    malformed `--blockers` value -- the caller's error; main() records
    nothing rather than guessing an outcome). The first plain positional
    token (not a recognized flag or its value) is the target repo/dir,
    mirroring record_review.py's `${1:-$PWD}` convention.

    Mirrors record_review.py's `_outcome_from_argv` semantics EXACTLY (round-2
    review found the first version of this function did not, despite its
    docstring claiming it did): `--blockers 0` (or any n <= 0) is a CLEAN
    outcome -- zero unresolved blockers is clean, not a distinct "blockers"
    state with count 0. A malformed count (`--blockers not-a-number`) leaves
    the outcome UNSET, not "blockers" with blockers=None -- a caller cannot
    accidentally write an unusable-but-truthy-looking ledger entry; main()
    reports "nothing recorded" for that shape instead. Never raises.
    """
    target: str | None = None
    outcome: str | None = None
    blockers: int | None = None
    plan_path: str | None = None
    i = 0
    n = len(argv)
    while i < n:
        a = argv[i]
        if a == "--clean":
            outcome = "clean"
            i += 1
            continue
        if a == "--blockers" and i + 1 < n:
            parsed = _parse_int(argv[i + 1])
            if parsed is not None:
                blockers = parsed
                outcome = "clean" if parsed <= 0 else "blockers"
            i += 2
            continue
        if a.startswith("--blockers="):
            parsed = _parse_int(a[len("--blockers=") :])
            if parsed is not None:
                blockers = parsed
                outcome = "clean" if parsed <= 0 else "blockers"
            i += 1
            continue
        if a == "--plan" and i + 1 < n:
            plan_path = argv[i + 1]
            i += 2
            continue
        if a and not a.startswith("--") and target is None:
            target = a
            i += 1
            continue
        i += 1
    return target, outcome, blockers, plan_path


def plan_reviews_path() -> str:
    return os.path.join(_lib.REVIEW_STATE_DIR, "plan_reviews.jsonl")


def resolve_repo_root(target: str) -> str:
    """`target` resolved to its git toplevel, or `target` itself unchanged if
    that fails (not a repo, git missing, timeout). Never raises.

    Round-2 review: storing the raw CLI string let `.`/`~/x`/an absolute path
    all key the SAME repo under different strings, and a plan path passed
    positionally by mistake (`record_plan_review.py /plans/a.md --clean`)
    silently recorded `repo: "/plans/a.md"` — this ledger's only purpose is
    aggregation by repo, so an unnormalized key defeats it. A failure to
    resolve is not treated as an error (this ledger fails open, like every
    other module here); it just means the raw string is what gets recorded,
    same as before this function existed.
    """
    if not target:
        # An empty `-C` argument is not rejected by git -- it silently falls
        # back to THIS PROCESS's own cwd, which would resolve to some
        # unrelated repo instead of failing loudly. Guard explicitly rather
        # than rely on that git behavior.
        return target
    try:
        proc = subprocess.run(
            ["git", "-C", target, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return target
    if proc.returncode != 0:
        return target
    out = (proc.stdout or "").strip()
    return out or target


def record(target: str, outcome: str, blockers: int | None, plan_path: str | None) -> bool:
    """Append one ledger line. Returns True on success, False on any failure.

    Plain O_APPEND, no lock: unlike last_reviewed (which REWRITES a line in
    place on a changed outcome, per record_review.py's own documented reason
    for needing a lock), this ledger only ever appends -- unprotected
    O_APPEND is atomic enough on its own for that shape, matching how
    last_reviewed itself behaved before it grew the outcome-update feature.
    """
    try:
        os.makedirs(_lib.REVIEW_STATE_DIR, exist_ok=True)
    except Exception:
        return False
    try:
        os.chmod(_lib.REVIEW_STATE_DIR, 0o700)
    except Exception:
        pass
    entry = {
        "ts": _lib._now(),
        "repo": target,
        "plan": plan_path,
        "outcome": outcome,
        "blockers": blockers if outcome == "blockers" and blockers is not None else 0,
    }
    try:
        with open(plan_reviews_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    """Thin entrypoint: parse, record, log, print. Always returns 0.

    The master OFF switch CSA_DISABLE_HOOKS=1 makes this a clean no-op,
    matching every other module here.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    if _lib.disabled():
        return 0

    target, outcome, blockers, plan_path = parse_argv(argv)
    if not target or not outcome:
        print(
            "record_plan_review: needs a target repo/dir and --clean or a "
            "PARSEABLE --blockers <n>. Nothing recorded."
        )
        _lib.log(HOOK, "no-outcome", repo=target, plan=plan_path)
        return 0

    if not plan_path:
        print(
            "record_plan_review: WARNING -- no --plan <path> given; this "
            "entry will be unattributable to a specific plan. Recording "
            "anyway, but pass --plan next time."
        )

    target = resolve_repo_root(target)
    wrote = record(target, outcome, blockers, plan_path)
    if wrote:
        phrase = "clean" if outcome == "clean" else f"{blockers or 0} blocker(s)"
        print(f"record_plan_review: recorded plan review for {target} ({phrase}).")
    else:
        print(
            "record_plan_review: NOT recorded -- the ledger write failed. "
            "Nothing was written."
        )
    _lib.log(
        HOOK,
        "recorded" if wrote else "record-failed",
        repo=target,
        plan=plan_path,
        outcome=outcome,
        blockers=blockers or 0,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
