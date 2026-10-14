"""pre_commit_ratchet — a real `git commit` gate for ~/.claude, not a Claude-Code
harness hook. It runs on every `git commit` to this repo (yours, an agent's, any
session's), so it cannot be silently skipped just because a Claude Code session
disabled its own hooks -- that is the point.

WHY THIS EXISTS (2026-08-01): the runtime's model/effort default regressed
TWICE with no mechanical guard -- once as an uncommitted working-tree fix that
evaporated, once as an expensive default folded silently into an unrelated
commit (07-19, c09d6b0: "block Artifacts->HTML" also added `model: opus[1m]`).
A CI job cannot catch this class of bug: GitHub Actions runs in a clean cloud
container that never sees this laptop's ~/.claude/settings.json. The only
place that can actually observe "is this commit about to reintroduce the
regression" is a local git hook on the commit that touches the file, which is
what this module is.

Three independent checks, the first two diff-aware (compare the committed
BEFORE against the about-to-be-committed AFTER, not just the after in
isolation, so a commit's *change* is what's judged):

  1. settings.json sanity (`check_settings_diff`) -- BLOCKS on effortLevel
     regressing to "xhigh" or going missing entirely (both proven regressions);
     also BLOCKS on the nested per-model form the Claude Code client itself
     writes -- `modelSettings.<model>.effortLevel == "xhigh"` (found live and
     uncommitted 2026-09-20; the top-level check alone never saw it, since it
     is a different key entirely) -- naming every offending model key in the
     one message. WARNS (does not block) on any `model` change, so a future
     accidental bundle is at least loudly visible in the commit output instead
     of silent. Does NOT hardcode a "these models are cheap" allowlist -- new
     models get priced and named over time and a stale allowlist would either
     false-block a legitimate choice or false-pass a bad one; the operator
     reads the WARN. An explicit CSA_ALLOW_EXPENSIVE_DEFAULT=1 escape hatch
     authorizes exactly one commit past either effortLevel block (top-level or
     nested), mirroring this repo's existing single-purpose CSA_* escape-hatch
     pattern (CSA_SKIP_REVIEW, etc.).

  2. agent-roster consistency (`check_roster_diff`) -- reuses
     sync_agent_rules.check_consistency() against the STAGED content of
     CLAUDE.md + agents/*.md (not the working tree -- a pre-commit hook must
     judge what is about to be committed), and blocks if it finds any problem
     beyond the one pre-existing accepted baseline drift (code-reviewer.md's
     missing contract anchor, tracked separately). This is what makes the
     08-01 worker-model-drift check (§10: no unpinned/opus-pinned workers)
     durable -- it cannot regress via any future commit to this repo without
     the hook catching it at commit time, not weeks later in a cost audit.

  3. workflow agent purity (`check_workflow_agent_purity`, RULE G2 of THE
     ISSUE WHEEL plan) -- for any staged `workflows/issue-wheel-*.js` file
     (never the whole `workflows/` directory -- `workflows/deliver.js` is a
     pre-existing, unrelated saved workflow and stays out of scope), blocks
     if the STAGED content violates the Workflow/Agent governance rule: no
     shell/fs access, no reviewer/writer agentType, every agent() call pinned
     to an explicit model. Delegates its actual parsing/decision logic to
     hooks/check_workflow_agent_purity.py's check_file(), so the ratchet and
     that module's own standalone CLI can never disagree about what counts as
     a violation.

PURITY FINDINGS ARE UNWAIVABLE (THE ISSUE WHEEL hardening plan, H5): a purity
violation is not just another blocking reason -- it is tagged with the check
name "workflow_agent_purity" specifically so it can be scoped OUT of the
general ESCAPE_HATCH_VAR waiver (CSA_ALLOW_EXPENSIVE_DEFAULT is for the
settings.json effortLevel regression this module was originally built for; it
must never double as a blanket waiver for an impure Workflow script landing
unattended-commit authority). `main()`'s `blocking` list is therefore
`(check_name, message)` tuples, not flat strings, so the escape-hatch
resolution at the bottom of `main()` can tell the two classes apart. A
purity-specific, separately-named door, CSA_ALLOW_WHEEL_WORKFLOW_IMPURITY=1,
exists for a genuine emergency -- greppable and auditable, never silent or
shared with the general hatch. The purity check also runs even when
CSA_DISABLE_HOOKS=1 is set, so that variable cannot be used to land an impure
Workflow script either -- CSA_DISABLE_HOOKS still short-circuits every OTHER
check in this module unchanged.

This guarantee has a load-bearing dependency OUTSIDE this file and outside git
tracking: the installed shim at ~/.claude/.git/hooks/pre-commit (git hooks are
never versioned by git itself) must actually invoke this module's main() in
every case, including CSA_DISABLE_HOOKS=1 -- a shim with its own unconditional
`[ "$CSA_DISABLE_HOOKS" = 1 ] && exit 0` would short-circuit before Python (and
therefore this purity check) ever runs, silently defeating the guarantee above
regardless of how correct the discrimination logic in main() is. Verify the
live shim has no such shell-level short-circuit if this guarantee is ever in
doubt; there is currently no install/template script that regenerates that
file, so it must be checked and fixed directly on disk.

Structure mirrors every other hook in this directory: pure decision functions
(no IO beyond the values they're given) + a thin main() that gathers real git
state, decides, prints, and sets the exit code. Unlike the Stop/PreToolUse
harness hooks elsewhere in hooks/ (which intentionally degrade OPEN on any
internal error, per this repo's established philosophy of "a hook must never
wedge an agent turn"), THIS hook fails CLOSED on a detected violation -- that is
the entire point of a ratchet the operator explicitly asked for after two
silent regressions. It still degrades open (exit 0, printing the error) on a
genuinely unexpected internal crash (e.g. git plumbing itself failing) rather
than wedging every future commit on a bug in this script.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - shim runs before tests import
    sys.path.insert(0, _HOOKS_DIR)

import sync_agent_rules as sar  # noqa: E402  (import after sys.path shim)
from check_workflow_agent_purity import check_file as _check_workflow_agent_purity_file  # noqa: E402

# The one drift the live roster carries today that is NOT this ratchet's job to
# fix (code-reviewer.md's missing contract anchor) -- kept in sync with the
# pinned expectation in tests/test_sync_agent_rules.py. Any OTHER problem is new
# and blocks the commit.
_ACCEPTED_BASELINE_DRIFT = sar.Problem(
    "missing-contract-anchor",
    "agent 'code-reviewer.md' does not reference the contract (~/.claude/CLAUDE.md)",
)

# The one proven-bad effort value. Anything else (including a value this script
# has never seen before) is not second-guessed here -- only the specific thing
# that regressed twice is blocked.
_BLOCKED_EFFORT_LEVEL = "xhigh"

ESCAPE_HATCH_VAR = "CSA_ALLOW_EXPENSIVE_DEFAULT"

# THE ISSUE WHEEL hardening plan, H5: a purity finding is tagged with this
# check name so it can be scoped out of ESCAPE_HATCH_VAR's general waiver --
# it is never waivable by CSA_ALLOW_EXPENSIVE_DEFAULT=1, and not waivable by
# CSA_DISABLE_HOOKS=1 either (the purity check runs regardless of that
# short-circuit). Only PURITY_ESCAPE_HATCH_VAR below can waive it.
PURITY_CHECK_NAME = "workflow_agent_purity"

# Named, purity-specific escape hatch (THE ISSUE WHEEL hardening plan, H5) --
# a genuine emergency gets a greppable, auditable door of its own, never the
# general ESCAPE_HATCH_VAR and never CSA_DISABLE_HOOKS.
PURITY_ESCAPE_HATCH_VAR = "CSA_ALLOW_WHEEL_WORKFLOW_IMPURITY"


# ---------------------------------------------------------------------------
# Pure decision functions.
# ---------------------------------------------------------------------------


def check_settings_diff(before: dict | None, after: dict | None) -> tuple[list[str], list[str]]:
    """Return (blocking_reasons, warnings) for a settings.json before/after pair.

    `before`/`after` are parsed JSON dicts (or None if the file didn't exist /
    didn't parse on that side). Never raises: a None or malformed side just
    means "nothing to compare on that side", not a crash.
    """
    blocking: list[str] = []
    warnings: list[str] = []

    after = after or {}
    before = before or {}

    effort = after.get("effortLevel")
    if effort is None:
        blocking.append(
            "settings.json: 'effortLevel' is absent. Set it explicitly (this is "
            "exactly how the 07-09 fix evaporated -- an implicit/absent value "
            "instead of a committed one)."
        )
    elif effort == _BLOCKED_EFFORT_LEVEL:
        blocking.append(
            f"settings.json: 'effortLevel' is '{_BLOCKED_EFFORT_LEVEL}' -- this exact "
            f"value has caused two separate credit-burn regressions (06-30 through "
            f"07-19+). If this is genuinely deliberate, re-run with "
            f"{ESCAPE_HATCH_VAR}=1 for this one commit."
        )

    # Nested per-model form: the Claude Code client itself writes
    # `modelSettings.<model>.effortLevel`, a different key entirely from the
    # top-level `effortLevel` checked above -- found live and uncommitted
    # 2026-09-20, multiplying the cost of the two most expensive pinned models
    # (2026-09-20 plan, F6). `modelSettings` is attacker/tool-written JSON, so
    # every shape assumption is defensive: an absent key, a non-dict value, or
    # a non-dict per-model entry is skipped rather than raising.
    model_settings = after.get("modelSettings")
    if isinstance(model_settings, dict):
        xhigh_models = sorted(
            model
            for model, entry in model_settings.items()
            if isinstance(entry, dict) and entry.get("effortLevel") == _BLOCKED_EFFORT_LEVEL
        )
        if xhigh_models:
            names = ", ".join(xhigh_models)
            blocking.append(
                f"settings.json: 'modelSettings' sets effortLevel to "
                f"'{_BLOCKED_EFFORT_LEVEL}' for: {names} -- this exact value has "
                f"caused two separate credit-burn regressions (06-30 through "
                f"07-19+), and this nested per-model form multiplies the cost of "
                f"whichever model(s) it names. If this is genuinely deliberate, "
                f"re-run with {ESCAPE_HATCH_VAR}=1 for this one commit."
            )

    before_model = before.get("model")
    after_model = after.get("model")
    if before_model is not None and after_model is not None and before_model != after_model:
        warnings.append(
            f"settings.json: 'model' changed '{before_model}' -> '{after_model}'. "
            f"Not blocked (no hardcoded cheap-model allowlist here -- it would go "
            f"stale), but this is the exact class of change that got silently "
            f"folded into an unrelated commit (07-19, c09d6b0) last time. Make sure "
            f"the commit message says so."
        )

    return blocking, warnings


def check_workflow_agent_purity(repo: str, relative_paths: list[str]) -> list[str]:
    """Return failure-reason strings for THE ISSUE WHEEL's Workflow-purity rule
    (RULE G2, plan: issue_wheel_consolidation.md section 3).

    `relative_paths` are already filtered by the caller to
    `workflows/issue-wheel-*.js` files touched by this commit. Each path's
    content is read from the STAGED INDEX via staged_blob (never from disk),
    matching this module's own existing convention for the settings.json/
    CLAUDE.md checks above -- the ratchet judges what is about to be
    committed, not what happens to be on disk right now. A staged path that
    resolves to no blob (e.g. a staged deletion) is skipped rather than
    treated as a failure -- there is no content left to check.
    """
    failures: list[str] = []
    for path in relative_paths:
        text = staged_blob(repo, path)
        if text is None:
            continue
        failures.extend(_check_workflow_agent_purity_file(path, text))
    return failures


def check_roster_diff(contract_text: str, agents: list[tuple[str, str]]) -> list[str]:
    """Return new-problem descriptions beyond the one accepted baseline drift.

    Delegates to sync_agent_rules.check_consistency (already unit-tested) so
    this ratchet and the Stop-hook advisory check can never disagree about what
    counts as drift. `agents` should be the STAGED content, not the working
    tree, when called from a pre-commit context.
    """
    problems = sar.check_consistency(contract_text, agents)
    new_problems = [p for p in problems if p != _ACCEPTED_BASELINE_DRIFT]
    return [p.format() for p in new_problems]


# ---------------------------------------------------------------------------
# Git plumbing -- read STAGED content (the index), never the working tree.
# Every helper degrades to None/[] on any failure; the caller decides what an
# absence means.
# ---------------------------------------------------------------------------


def _git(repo: str, *args: str) -> str | None:
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def staged_blob(repo: str, path: str) -> str | None:
    """Content of `path` as staged in the index right now, or None if the path
    isn't staged / doesn't exist there (deleted, never added, etc.)."""
    return _git(repo, "show", f":{path}")


def head_blob(repo: str, path: str) -> str | None:
    """Content of `path` at HEAD, or None if it doesn't exist there (new file)."""
    return _git(repo, "show", f"HEAD:{path}")


def staged_agent_files(repo: str) -> list[tuple[str, str]]:
    """(basename, staged_text) for every staged agents/*.md path."""
    listing = _git(repo, "diff", "--cached", "--name-only") or ""
    out: list[tuple[str, str]] = []
    for line in listing.splitlines():
        line = line.strip()
        if line.startswith("agents/") and line.endswith(".md"):
            text = staged_blob(repo, line)
            if text is not None:
                out.append((os.path.basename(line), text))
    # Agent files NOT touched by this commit still exist in HEAD and must be
    # included too, or the roster check would only ever see the changed subset.
    listing_head = _git(repo, "ls-tree", "-r", "--name-only", "HEAD") or ""
    seen = {n for n, _ in out}
    for line in listing_head.splitlines():
        line = line.strip()
        if line.startswith("agents/") and line.endswith(".md"):
            base = os.path.basename(line)
            if base in seen:
                continue
            # Prefer the staged version if this commit touches it a second way
            # (rename etc.); otherwise fall back to HEAD's committed content.
            text = staged_blob(repo, line)
            if text is None:
                text = head_blob(repo, line)
            if text is not None:
                out.append((base, text))
                seen.add(base)
    return out


def _parse_json(text: str | None) -> dict | None:
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Thin main(): gather real git state, decide, print, set exit code.
# ---------------------------------------------------------------------------


def _find_repo_root(start: str) -> str:
    """Walk up from `start` looking for a `.git` entry. Empty string if none."""
    repo = start
    while repo and not os.path.isdir(os.path.join(repo, ".git")):
        parent = os.path.dirname(repo)
        if parent == repo:
            return ""
        repo = parent
    return repo


def main() -> int:
    try:
        # git invokes pre-commit with cwd at the repo root; walking up from cwd
        # (rather than this script's own on-disk location) is both the correct
        # git-hook convention and what makes this hermetically testable against
        # a throwaway repo instead of always resolving to the real ~/.claude.
        repo = _find_repo_root(os.getcwd())
        if not repo:
            return 0  # not inside a git repo somehow -- nothing to ratchet

        # `blocking` entries are (check_name, message) tuples, not flat
        # strings (THE ISSUE WHEEL hardening plan, H5) -- the escape-hatch
        # resolution below needs to tell a workflow-purity finding apart from
        # every other kind, since only the former is exempt from the general
        # ESCAPE_HATCH_VAR waiver.
        blocking: list[tuple[str, str]] = []
        warnings: list[str] = []

        # --- workflow agent purity (THE ISSUE WHEEL) -- deliberately BEFORE
        # the CSA_DISABLE_HOOKS short-circuit below, so that variable cannot
        # be used to land an impure Workflow script (H5, chaos-gate row 5:
        # blocked regardless of any single escape-hatch env var being set).
        touched = _git(repo, "diff", "--cached", "--name-only") or ""
        wheel_workflow_files = [
            line.strip() for line in touched.splitlines()
            if line.strip().startswith("workflows/issue-wheel-") and line.strip().endswith(".js")
        ]
        if wheel_workflow_files:
            blocking.extend(
                (PURITY_CHECK_NAME, msg)
                for msg in check_workflow_agent_purity(repo, wheel_workflow_files)
            )

        if os.environ.get("CSA_DISABLE_HOOKS", "") != "1":
            # --- settings.json ---
            before_settings = _parse_json(head_blob(repo, "settings.json"))
            after_settings = _parse_json(staged_blob(repo, "settings.json"))
            if after_settings is not None or before_settings is not None:
                b, w = check_settings_diff(before_settings, after_settings)
                blocking.extend(("settings", msg) for msg in b)
                warnings.extend(w)

            # --- agent roster ---
            contract_text = staged_blob(repo, "CLAUDE.md")
            if contract_text is None:
                contract_text = head_blob(repo, "CLAUDE.md") or ""
            agents = staged_agent_files(repo)
            if agents:
                blocking.extend(("roster", msg) for msg in check_roster_diff(contract_text, agents))

        for w in warnings:
            print(f"[pre-commit-ratchet WARN] {w}", file=sys.stderr)

        if blocking:
            purity_blocking = [(name, msg) for name, msg in blocking if name == PURITY_CHECK_NAME]
            other_blocking = [(name, msg) for name, msg in blocking if name != PURITY_CHECK_NAME]

            general_escape = os.environ.get(ESCAPE_HATCH_VAR, "") == "1"
            purity_escape = os.environ.get(PURITY_ESCAPE_HATCH_VAR, "") == "1"

            print("[pre-commit-ratchet] BLOCKED:", file=sys.stderr)
            for _name, b in blocking:
                print(f"  - {b}", file=sys.stderr)

            # A purity finding is NEVER waivable by the general ESCAPE_HATCH_VAR
            # -- only PURITY_ESCAPE_HATCH_VAR clears it. Both env hatches set
            # still blocks if either class of finding lacks its own matching
            # waiver (H5, chaos-gate row 5).
            purity_cleared = (not purity_blocking) or purity_escape
            other_cleared = (not other_blocking) or general_escape

            if purity_cleared and other_cleared:
                if purity_blocking:
                    print(
                        f"[pre-commit-ratchet] {PURITY_ESCAPE_HATCH_VAR}=1 set -- "
                        f"allowing this one commit's workflow-purity finding(s) through "
                        f"anyway.",
                        file=sys.stderr,
                    )
                if other_blocking:
                    print(
                        f"[pre-commit-ratchet] {ESCAPE_HATCH_VAR}=1 set -- allowing this "
                        f"one commit through anyway.",
                        file=sys.stderr,
                    )
                return 0

            if purity_blocking and not purity_escape:
                print(
                    f"[pre-commit-ratchet] workflow-purity findings are not waivable by "
                    f"{ESCAPE_HATCH_VAR} or CSA_DISABLE_HOOKS. Fix the above, or set "
                    f"{PURITY_ESCAPE_HATCH_VAR}=1 for this one commit if it's genuinely "
                    f"an emergency.",
                    file=sys.stderr,
                )
            if other_blocking and not general_escape:
                print(
                    f"[pre-commit-ratchet] Fix the above, or set {ESCAPE_HATCH_VAR}=1 for "
                    f"this one commit if it's genuinely deliberate.",
                    file=sys.stderr,
                )
            return 1

        return 0
    except Exception as exc:  # pragma: no cover - defensive only
        # Degrade open on a genuinely unexpected internal crash (git plumbing
        # itself failing, etc.) -- a bug in this script must not wedge every
        # future commit. A detected VIOLATION above is a different code path
        # and does not hit this except.
        print(f"[pre-commit-ratchet] internal error, allowing commit: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
