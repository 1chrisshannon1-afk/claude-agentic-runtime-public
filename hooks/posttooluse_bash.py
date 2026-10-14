#!/usr/bin/env python3
"""posttooluse_bash — PostToolUse:Bash dispatcher.

Three jobs. The third (runtime-mirror trigger) keys off a `git push` event;
the first two are both keyed off the SAME event (a writing `git commit` Bash
call):

  1. Release this call's file_claims claim (see file_claims.py,
     pretooluse_bash.py gate 4) once the commit has finished — success or
     failure, doesn't matter, the claim's purpose (protect the commit window)
     is over either way. Mirrors agent_budget.py's PostToolUse:Task
     `release_hook` action exactly: key on tool_use_id (the ONE id guaranteed
     shared between the Pre and Post events for the same call), best-effort,
     never raises. A commit whose PreToolUse minted a FALLBACK id
     (tool_use_id absent) has no correlated release here — the same
     documented tradeoff agent_budget accepts — and TTL-reaps instead
     (CSA_FILE_CLAIM_TTL_SEC, default 300s).
  2. Record commit authorship (see commit_authors.py): resolve the repo's
     fresh HEAD and attribute it to this event's session_id. While
     task_completion_gate.py was live (RETIRED 2026-08-20) this let its Stop
     gate scope its warn/block to the COMMITTING session only, instead of
     firing in every live session sharing the repo -- that consumer is gone,
     but the recording itself is kept (cheap, and a future revival of some
     Stop-boundary check would want this authorship data already flowing).
     Runs BEFORE the claim release (ordering is
     load-bearing: while our claim is held, the per-repo commit mutex the
     concurrently-developed pretooluse_bash.py gate 4 change adds guarantees
     no OTHER commit can land in this repo, so recording before release
     avoids attributing the wrong session's HEAD). Best-effort and
     independent of the release outcome: recording failing (or being
     skipped — a stale HEAD, a non-repo cwd, a missing git) never prevents
     the claim release from running.
  3. Runtime-mirror trigger (2026-08-30, operator directive; see
     runtime_mirror_sync.py): when this event's command contains a
     `git push` segment, spawn a DETACHED background sync of the runtime's
     committed content to its GitHub mirror. Config-gated (no
     ~/.claude/.mirror/config.json -> inert), best-effort, and detached so
     the operator's own push is never slowed by the mirror's.

Structured as its own small dispatcher, parallel to pretooluse_bash.py, so a
further PostToolUse:Bash concern can be added later without multiplying python
spawns (see post_bash_gate.sh's fast-path).

Fails OPEN like every other hook here: any error is swallowed, exit is always 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402
import check_staged_scope as css  # noqa: E402
import commit_authors  # noqa: E402
import file_claims as fc  # noqa: E402
import runtime_mirror_sync  # noqa: E402

# Freshness bound for authorship attribution: a HEAD whose committer timestamp
# is older than this many seconds is presumed to be a FAILED/no-op re-commit
# (the working tree didn't actually advance), so recording it would falsely
# attribute a stale HEAD to this session. Set generously (10 min, not 2) —
# this hook fires after the WHOLE Bash call, and a common real pattern is
# `git commit -- <paths> && <slow follow-on step>` (tests, a lint pass); a
# tight bound made those legitimate commits silently lose attribution
# (UNKNOWN_AUTHOR -> the Stop gate never surfaces that HEAD to anyone).
STALE_HEAD_SEC = 600


def should_release(ev: dict) -> bool:
    """True iff this PostToolUse event is a writing `git commit` Bash call.

    Reuses check_staged_scope's exact commit-detection so Pre/Post agree on
    what counts as "a commit" byte-for-byte. Never raises.
    """
    try:
        if _lib.tool_name(ev) != "Bash":
            return False
        return css.is_git_commit(_lib.bash_command(ev))
    except Exception:  # pragma: no cover - _lib/css helpers already fail-safe
        return False


def _git(cwd: str, *args: str) -> str | None:
    """Run `git -C cwd <args>` and return trimmed stdout, or None on failure.

    Hermetic (no system config, no terminal prompt) and bounded (15s timeout),
    matching task_completion_gate._git / record_review._git exactly. Never
    raises.
    """
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _record_commit_author(ev: dict) -> None:
    """Best-effort: attribute the repo's fresh HEAD to this event's session.

    Resolves the repo root from the event's cwd, then resolves HEAD's sha and
    committer timestamp in a SINGLE combined `git log` call
    (`--format=%H%x00%ct`, split on the NUL byte) rather than two separate
    `git rev-parse HEAD` / `git log -1 --format=%ct` spawns — same 15s
    per-call timeout, same (sha, epoch_seconds) pair, one fewer subprocess on
    the commit hot path (see module/plan history: item 1 of the gate
    optimization pass). Skips silently when the repo root or the combined
    output is unresolvable (not a repo, no commits, git missing, malformed
    output) or when HEAD's committer timestamp is older than STALE_HEAD_SEC
    (a failed/no-op re-commit must not self-attribute — see module
    docstring). Never raises; any failure here must not prevent the caller
    from still releasing the file_claims claim afterward.
    """
    try:
        where = _lib.effective_git_cwd(_lib.bash_command(ev), _lib.cwd(ev))
        repo_root = _git(where, "rev-parse", "--show-toplevel")
        if not repo_root:
            return
        combined = _git(repo_root, "log", "-1", "--format=%H%x00%ct")
        if not combined:
            return
        head, sep, committer_ts = combined.partition("\x00")
        if not sep or not head or not committer_ts:
            return
        age = time.time() - float(committer_ts)
        if age > STALE_HEAD_SEC:
            return
        commit_authors.record(_lib.COMMIT_AUTHORS, repo_root, head, _lib.session_id(ev))
    except Exception:
        return


def main() -> int:
    try:
        if _lib.disabled():
            return 0
        ev = _lib.read_event()
        # Third concern (2026-08-30, operator directive): any `git push` in
        # this event triggers a DETACHED runtime-mirror sync (see
        # runtime_mirror_sync.py). Best-effort and independent of the two
        # commit-keyed jobs below — an event can be both (e.g. `git commit
        # ... && git push`), so this runs unconditionally first and a
        # trigger failure must not affect claim release.
        runtime_mirror_sync.maybe_trigger(ev)
        if not should_release(ev):
            return 0
        # Record authorship BEFORE releasing the claim — see module docstring
        # ("ordering is load-bearing"). Best-effort: never blocks the release.
        _record_commit_author(ev)
        tid = _lib.tool_use_id(ev)
        if not tid:
            return 0  # nothing to correlate; a minted claim just TTL-reaps
        fc.release_claim(_lib.FILE_CLAIMS_DIR, tid)
        return 0
    except Exception:
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
