"""Pytest fixtures for a hermetic hook-system sandbox.

Every test runs against a throwaway $HOME so the real ~/.claude (the operator's
live enforcement state, review state, budget ledger, and decision log) is NEVER
touched. Tests must not spawn network or shell out to anything privileged.

The key trick: _lib.py computes its path constants at import time from
os.path.expanduser("~"). Rather than re-import the module per test (fragile), the
`sandbox` fixture monkeypatches the already-imported module's HOME-derived path
constants to point inside a tmp dir, and also sets $HOME so any code that
re-expands ~ lands in the sandbox too. A clean env baseline is established so a
stray CSA_* var in the real shell can't leak into a test.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from typing import Mapping, Optional

import pytest

# Make the hooks dir importable as `import _lib` regardless of the pytest rootdir.
_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

# ---------------------------------------------------------------------------
# Session guard: this suite tests the DEPLOYED shape.
#
# Hooks resolve each other through `$HOME/.claude` (`_lib.CLAUDE_DIR`,
# `bash_gate.sh`, every `settings.json` command), and many test files read
# `Path.home()/".claude"` by design. Run from a clone that is not that
# directory, hundreds of tests fail with `~/.claude/scripts/<x>.sh: No such
# file` -- noise that reads as product bugs and has already led to a
# misdiagnosis. So the session aborts up front, with a pointer to the supported
# way to test a foreign checkout (`scripts/ci_layout.sh`, which stages the
# checkout AS `$HOME/.claude` inside a throwaway HOME).
#
# Opt-out: `CSA_TESTS_ALLOW_FOREIGN_ROOT=1`, for the few legitimate runs
# outside the deployed directory that know what they are doing (a lane
# worktree of this repo; `hooks/tests/precommit_review_mutation_battery.py`,
# which runs a copy of the hooks tree). Expect failures from the
# deployed-shape tests there; the opt-out removes the abort, not that coupling.
# ---------------------------------------------------------------------------

_ALLOW_FOREIGN_ROOT_ENV = "CSA_TESTS_ALLOW_FOREIGN_ROOT"
# hooks/tests/conftest.py -> hooks/ -> the checkout root.
_CHECKOUT_ROOT = os.path.dirname(_HOOKS_DIR)


def _foreign_root_problem(
    checkout_root: str, home: str, environ: Mapping[str, str]
) -> Optional[str]:
    """Explain why this session must abort, or return None when it may run.

    Pure (no pytest, no process state) so the rule is checkable on its own:
    allowed iff the opt-out env var is "1", or `realpath(checkout_root)` equals
    `realpath(home/.claude)`.
    """
    if environ.get(_ALLOW_FOREIGN_ROOT_ENV) == "1":
        return None
    deployed = os.path.realpath(os.path.join(home, ".claude"))
    checkout = os.path.realpath(checkout_root)
    if checkout == deployed:
        return None
    return (
        f"hooks/tests must run from the deployed shape, but this checkout is\n"
        f"  {checkout}\n"
        f"while $HOME/.claude is\n"
        f"  {deployed}\n"
        "Hooks and many tests resolve paths through $HOME/.claude, so a "
        "clone anywhere else fails hundreds of tests for that one reason.\n"
        "To test a foreign checkout, stage it as $HOME/.claude in a throwaway HOME: "
        "run scripts/ci_layout.sh.\n"
        f"If you really mean to run here (a lane worktree, the mutation battery), "
        f"set {_ALLOW_FOREIGN_ROOT_ENV}=1; expect deployed-shape failures."
    )


def pytest_configure(config: "pytest.Config") -> None:
    problem = _foreign_root_problem(_CHECKOUT_ROOT, os.path.expanduser("~"), os.environ)
    if problem is not None:
        pytest.exit(problem, returncode=2)


# The CSA_* env vars every test wants controlled. Cleared to a known baseline so
# the operator's real shell state can never bleed into an assertion.
_CSA_ENV_VARS = (
    "CSA_DISABLE_HOOKS",
    "CSA_ENFORCE",
    "CSA_ALLOW_GIT_STATE_OPS",
    "CSA_SKIP_REVIEW",
    "CSA_GUARD_DRYRUN",
    "CSA_ANTHROPIC_CEILING",
    "CSA_FANOUT_THRESHOLD",
    "CSA_LEASE_TTL_SEC",
    # N14 (08-25 round 4): the agent_budget pacer/spend-ledger knobs -- an
    # operator shell exporting CSA_PACER=1 per agent_pacer.md's own
    # recommended one-time-enable recipe leaked into every test that didn't
    # explicitly stub it, measured as 4 failures + a 90s runtime under
    # `CSA_PACER=1 pytest`.
    "CSA_PACER",
    "CSA_SPEND_LEDGER",
    "CSA_CLAIM_TTL_SEC",
    "CSA_LAUNCH_RATE",
    "CSA_LAUNCH_BURST",
    "CSA_LOCK_TIMEOUT_SEC",
    "CSA_ADMIT_MAX_WAIT_SEC",
    "CSA_ADMIT_POLL_SEC",
    "CSA_FILE_CLAIM_TTL_SEC",
    "CSA_COMMIT_CLAIM_MAX_WAIT_SEC",
    "CSA_COMMIT_CLAIM_POLL_SEC",
    "CSA_CHURN_WINDOW_SEC",
    "CSA_CHURN_THRESHOLD",
    "CSA_NO_COMMIT_MUTEX",
    "CSA_COMMIT_MUTEX_TTL_SEC",
    "CSA_NO_REQUIRE_PATHSPEC",
    # Without this, a stray CSA_NO_PRECOMMIT_REVIEW=1 in the operator's
    # shell would leak into every test and make the whole gate suite pass
    # vacuously -- the exact failure class the gate exists to prevent.
    "CSA_NO_PRECOMMIT_REVIEW",
    # #4670 (2026-08-30, Opus review round 3, FINDING 6): the reviewer
    # PROVED these two levers, left in the ambient shell env, made the gate
    # 3c exemption tests and the dead-pid self-heal tests pass for the WRONG
    # reason (the gate/clamp silently disabled rather than the exemption/
    # clamp logic actually firing) -- the exact vacuous-pass failure class
    # CSA_NO_PRECOMMIT_REVIEW's own comment above already warns about, now
    # proven to also apply here.
    "CSA_NO_DIRTY_CONFIG_GATE",
    "CSA_DEAD_PID_TTL_SEC",
    # Telemetry plan §4.2 4a's identity kill-switch. Same vacuous-pass risk
    # the two vars above document: left set in the ambient shell, every
    # assertion that an identity field IS written would pass for the wrong
    # reason (the field silently disabled rather than the omission/emission
    # logic actually being exercised).
    "CSA_NO_LOG_IDENTITY",
    # Not a CSA_* var, but the same class of ambient-leak risk: every REAL
    # Claude Code session sets CLAUDE_PID in its own environment (see
    # file_claims._owner_pid()), and it is inherited by any subprocess the
    # test suite itself spawns. A test running inside an actual session (as
    # opposed to a bare CI shell) would otherwise see a real, live CLAUDE_PID
    # leak into _owner_pid()'s resolution for any test that doesn't
    # explicitly set/clear it itself — most of this file's dead-pid tests
    # already guard themselves per-test (see TestOwnerPid,
    # TestWriteClaimRecordsOwnerPid), but clearing it here too keeps the
    # baseline honest for anything added later that reads it.
    "CLAUDE_PID",
)


@pytest.fixture
def clean_env(monkeypatch):
    """Delete all CSA_* vars so each test starts from a known-empty baseline."""
    for var in _CSA_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def sandbox(tmp_path, monkeypatch, clean_env):
    """A hermetic ~/.claude rooted under tmp_path.

    Yields an object exposing the sandboxed paths. Repoints:
      * $HOME (so any expanduser("~") lands in the sandbox)
      * every _lib path constant derived from HOME

    so ~/.claude/.enforce, ~/.claude/.enforcement/, ~/.claude/.review_state/,
    and the agent-budget ledger are all isolated per test.
    """
    home = tmp_path / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True)

    # Point $HOME at the sandbox for anything that re-expands ~.
    monkeypatch.setenv("HOME", str(home))

    # R5 (08-25): _project_enforced()'s marker walk starts at the REAL
    # process cwd when no cwd is threaded through, not at anything this
    # fixture patches above — running the suite from a repo that itself has
    # `.claude/.csa-enforce` (any product repo with that marker) made that
    # walk find a REAL project marker and turn enforcement on for tests that
    # never asked for it. chdir into the (marker-free) tmp_path so the walk
    # always starts from a clean, throwaway directory regardless of where
    # pytest itself was invoked from.
    monkeypatch.chdir(tmp_path)

    # Repoint _lib's import-time path constants (they were computed against the
    # real HOME when the module was first imported).
    enforcement_dir = claude / ".enforcement"
    review_state_dir = claude / ".review_state"
    agent_budget_dir = claude / ".agent_budget"
    file_claims_dir = claude / ".file_claims"
    churn_dir = claude / ".churn"

    monkeypatch.setattr(_lib, "HOME", str(home))
    monkeypatch.setattr(_lib, "CLAUDE_DIR", str(claude))
    monkeypatch.setattr(_lib, "GLOBAL_ENFORCE_FILE", str(claude / ".enforce"))
    monkeypatch.setattr(_lib, "ENFORCEMENT_DIR", str(enforcement_dir))
    monkeypatch.setattr(_lib, "LOG_FILE", str(enforcement_dir / "log.jsonl"))
    monkeypatch.setattr(_lib, "REVIEW_STATE_DIR", str(review_state_dir))
    monkeypatch.setattr(_lib, "LAST_REVIEWED", str(review_state_dir / "last_reviewed"))
    monkeypatch.setattr(_lib, "AGENT_BUDGET_DIR", str(agent_budget_dir))
    monkeypatch.setattr(_lib, "FILE_CLAIMS_DIR", str(file_claims_dir))
    monkeypatch.setattr(_lib, "CHURN_DIR", str(churn_dir))
    monkeypatch.setattr(_lib, "COMMIT_AUTHORS", str(review_state_dir / "commit_authors"))

    class Sandbox:
        def __init__(self):
            self.home = home
            self.claude = claude
            self.enforce_file = claude / ".enforce"
            self.enforcement_dir = enforcement_dir
            self.log_file = enforcement_dir / "log.jsonl"
            self.review_state_dir = review_state_dir
            self.last_reviewed = review_state_dir / "last_reviewed"
            self.commit_authors = review_state_dir / "commit_authors"
            self.agent_budget_dir = agent_budget_dir
            self.file_claims_dir = file_claims_dir
            self.churn_dir = churn_dir

    return Sandbox()


@pytest.fixture
def git_repo(tmp_path):
    """Create a throwaway git repo and return its Path.

    Uses a real (local, offline) `git init` if git is available; otherwise
    fabricates the minimal `.git` directory the enforce-resolver walk needs
    (it only checks for a `.git` entry, not a valid repo). No network.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(repo),
            check=True,
            capture_output=True,
            timeout=15,
            env=env,
        )
    except Exception:
        # Fallback: just create the .git marker the walk-up looks for.
        (repo / ".git").mkdir(exist_ok=True)
    return repo


@pytest.fixture
def enforce_marker():
    """Helper to drop the per-project .claude/.csa-enforce opt-in in a repo.

    Returns a callable: enforce_marker(repo_path) -> Path to the marker.
    """

    def _mark(repo_path):
        marker_dir = os.path.join(str(repo_path), ".claude")
        os.makedirs(marker_dir, exist_ok=True)
        marker = os.path.join(marker_dir, ".csa-enforce")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("")
        return marker

    return _mark


@pytest.fixture
def make_payload():
    """Build a hook-stdin payload dict.

    Usage:
        make_payload(tool_name="Bash", command="git add -A")
        make_payload(tool_name="Stop", cwd="/x", session_id="s1")

    Returns a plain dict (tests JSON-encode it when they need a stdin string;
    _lib._parse_event consumes the string form, read_event consumes stdin).
    """

    def _build(
        tool_name="Bash", command=None, cwd=None, project_dir=None, session_id=None, **extra
    ):
        ev: dict = {}
        if tool_name is not None:
            ev["tool_name"] = tool_name
        if command is not None:
            ev["tool_input"] = {"command": command}
        if cwd is not None:
            ev["cwd"] = cwd
        if project_dir is not None:
            ev["project_dir"] = project_dir
        if session_id is not None:
            ev["session_id"] = session_id
        ev.update(extra)
        return ev

    return _build


@pytest.fixture(autouse=True)
def _reload_lib_paths_guard():
    """Safety net: after each test, re-import _lib fresh so any monkeypatched
    module constant that leaked (it shouldn't — monkeypatch auto-reverts) is
    reset to the real values for the next test's baseline.

    This is belt-and-suspenders; monkeypatch.setattr already reverts on teardown.
    """
    yield
    importlib.reload(_lib)
