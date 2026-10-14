#!/usr/bin/env python3
"""disk_pressure_check — SessionStart tripwire for the 2026-09-19 disk-full
incident. WARNS loudly when disk usage crosses 85%/92%; NEVER deletes
anything itself.

WHY THIS EXISTS
----------------
Disk hit 100% and blocked every session on the machine (see
`~/.claude/scripts/disk_janitor.sh`'s own header comment for the full
root-cause history: /private/tmp/claude-501/ grew to 332G, one repo's
.claude/worktrees/ grew to 102G with zero reaping mechanism anywhere). A
reaper alone is not a permanent control -- it only runs on its own schedule
(daily) or when someone remembers to invoke it by hand. This hook is the
early-warning half: it fires at the START of every session (a checkpoint
that already runs constantly across this operator's many concurrent
windows, exactly like `settings_drift_guard.py`), so a climbing disk gets
surfaced in-session, in context, well before it becomes an outage.

**This hook never deletes anything.** An earlier draft of this control
proposed auto-running the janitor at 92% usage; that was explicitly
REJECTED during review as unsafe -- an automatic deletion triggered from a
SessionStart hook, running with no operator watching and no dry-run step,
is exactly the kind of silent, high-blast-radius action this runtime's own
operating contract (~/.claude/CLAUDE.md) treats as needing human judgment.
This hook's entire job is: measure, decide whether to warn, print the
warning (with the exact command to run), and get out of the way. The
`disk_janitor.sh` command it prints ALSO defaults to dry-run -- so even a
human following this hook's own advice literally cannot accidentally
delete anything without a second, deliberate `--apply` step.

THE MOUNT-POINT TRAP (verified 2026-09-19 -- read before "simplifying" this)
-----------------------------------------------------------------------------
On this machine (and any modern macOS with the sealed-system-volume / Data-
volume split), `df /`'s own `Capacity` column reports usage against the
tiny, near-empty SYSTEM snapshot volume (18G, ~23% used) -- NOT the volume
that `/private/tmp`, `/Users`, and every repo on this machine actually live
on (`/System/Volumes/Data`, the volume genuinely under pressure, measured
94% used the same day `df /` read 23%). A check written against `df -h /`
alone would NEVER fire this tripwire, no matter how full the real,
user-data-bearing volume gets -- which is precisely the failure mode this
hook exists to close. `shutil.disk_usage(HOME)` (used below) is NOT
vulnerable to this: verified 2026-09-19 that Python's stdlib call resolves
to the underlying APFS CONTAINER's real block stats (93.62% used) even
when given the tiny system volume's own mountpoint, because `statvfs()`
reports container-level free space by construction on a shared-container
filesystem. Checking a real, always-present, non-root-owned path
(`HOME`, which is guaranteed to resolve onto the Data volume on this
machine) rather than bare `/` is a second, independent belt-and-suspenders
guard against ever silently checking the wrong volume again.

THRESHOLDS
----------
* >=85% used: WARN (loud but non-blocking) -- named "you're getting close,
  a good moment to run the janitor in dry-run and see what it would find."
* >=92% used: WARN, more urgent language, and explicitly suggests --apply.
  Still never runs anything itself -- see the rejected-auto-run note above.
* <85%: silent, no output at all (this hook is not a status dashboard; it
  is a tripwire, and a tripwire that chatters below its threshold trains
  the operator to ignore it).

FAILS OPEN, ALWAYS: any error resolving disk usage, HOME, or anything else
is a silent no-op -- a bug in THIS hook must never block a session from
starting, which is the one thing a SessionStart hook can never do. Every
outcome (warned-85, warned-92, ok, disabled, or a failure) is logged via
`_lib.log`, mirroring `settings_drift_guard.py`'s own logging discipline.
"""

from __future__ import annotations

import os
import shutil
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirrors sibling modules)

HOOK = "disk_pressure_check"

# Per-module rollback lever, mirroring every sibling SessionStart guard's own
# escape hatch (see settings_drift_guard.py's DISABLE_VAR). Without one, the
# only way to silence a misfiring instance of THIS module specifically is
# CSA_DISABLE_HOOKS=1, which also switches off every other hook in the chain.
DISABLE_VAR = "CSA_NO_DISK_PRESSURE_CHECK"

WARN_THRESHOLD_PCT = 85.0
URGENT_THRESHOLD_PCT = 92.0

JANITOR_SCRIPT = "~/.claude/scripts/disk_janitor.sh"


def _disabled_by_operator(environ: dict | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get(DISABLE_VAR, "") == "1"


def compute_usage_pct(path: str) -> float | None:
    """Pure-ish: percent used at `path`'s filesystem, or None on any
    failure. Never raises. See module docstring's "MOUNT-POINT TRAP"
    section for why `path` should be HOME (or another real, always-present
    user path) rather than bare "/" on this class of machine.
    """
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return None
    if usage.total <= 0:
        return None
    return (usage.used / usage.total) * 100.0


def classify(pct: float) -> str:
    """Pure: one of "ok" / "warn" / "urgent" for a given usage percentage.
    Boundary values (exactly 85.0 / 92.0) count as crossed (>=), matching
    the module docstring's own threshold language.
    """
    if pct >= URGENT_THRESHOLD_PCT:
        return "urgent"
    if pct >= WARN_THRESHOLD_PCT:
        return "warn"
    return "ok"


def format_message(pct: float, level: str, path: str) -> str:
    pct_str = f"{pct:.1f}%"
    if level == "urgent":
        lines = [
            f"[disk_pressure_check] URGENT: disk usage is {pct_str} at {path} "
            f"(>= {URGENT_THRESHOLD_PCT:.0f}% threshold).",
            "  This is the same danger zone that blocked every session on this",
            "  machine on 2026-09-19. This hook NEVER deletes anything itself --",
            "  run the reaper yourself:",
            f"    bash {JANITOR_SCRIPT}                 # dry run first -- see what it finds",
            f"    bash {JANITOR_SCRIPT} --apply          # then actually reclaim",
        ]
    else:
        lines = [
            f"[disk_pressure_check] WARNING: disk usage is {pct_str} at {path} "
            f"(>= {WARN_THRESHOLD_PCT:.0f}% threshold).",
            "  Worth a look before it becomes urgent. Dry-run the reaper to see",
            "  what it would reclaim (nothing is deleted until you pass --apply):",
            f"    bash {JANITOR_SCRIPT}",
        ]
    return "\n".join(lines)


def main() -> int:
    """SessionStart entrypoint. Always exits 0 -- never blocks a session."""
    try:
        if _lib.disabled() or _disabled_by_operator():
            _lib.log(HOOK, "disabled")
            return 0

        home = os.environ.get("HOME") or os.path.expanduser("~")
        if not home or not os.path.isdir(home):
            _lib.log(HOOK, "no-home-path")
            return 0

        pct = compute_usage_pct(home)
        if pct is None:
            _lib.log(HOOK, "usage-unresolvable", path=home)
            return 0

        level = classify(pct)
        if level == "ok":
            _lib.log(HOOK, "ok", pct=round(pct, 1))
            return 0

        print(format_message(pct, level, home))
        _lib.log(HOOK, f"warned-{level}", pct=round(pct, 1), path=home)
        return 0
    except Exception as exc:
        # _lib.log is itself best-effort/never-raises (see its own
        # docstring), so calling it from this handler is safe even if the
        # failure above was catastrophic.
        try:
            _lib.log(HOOK, "internal-error", error=str(exc))
        except Exception:
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
