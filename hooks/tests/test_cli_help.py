"""`--help` smoke test for every argparse-based CLI module under hooks/.

Spec: each of these modules is a command-line tool, and `--help` is the one
invocation a stranger runs first. It must exit 0 and print a `usage:` line, on
every supported Python. The class of defect this pins is the one that shipped
in `cycle_budget.py`: an unescaped `%` in an argparse help string is accepted by
older Pythons but rejected by 3.14 at `add_argument` time, so `--help` crashed
with `ValueError: badly formed help string` and the tool's own 19 tests failed
for a reason unrelated to what they test.

Scope, deliberately narrow:
  * only modules that BUILD an `argparse.ArgumentParser` (list below, fixed and
    explicit); the many hook modules whose `__main__` reads stdin or `sys.argv`
    by hand are excluded -- running `--help` on them would execute real hook
    logic, which this test must never do;
  * a completeness test fails when a new argparse-based module appears under
    hooks/ without being added here, so the list cannot silently go stale.

Hermetic: each run gets a throwaway HOME (which is also its cwd), a minimal
environment with no CSA_* / CLAUDE_* variables, stdin from /dev/null and a 10s
timeout. Nothing is read from or written to the real `~/.claude`.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[1]
_TIMEOUT_SEC = 10

# Every hooks/*.py that builds (or subclasses) an argparse.ArgumentParser, found
# by scanning for it (see `test_the_cli_list_is_complete`). Listed explicitly so
# a reader sees exactly which tools are covered, with the argv that reaches the
# argparse parser: `--help` for all but one.
#
# `issue_wheel_queue.py` is the exception. Its `main()` is a fail-open
# dispatcher (`run` | `status`) that must always exit 0 for the hook that calls
# it, so a bare `--help` falls through to a hand-written one-line `usage:` on
# STDERR and never touches argparse; the real argparse parser lives behind the
# `run` subcommand, so that is the surface worth exercising.
_ARGPARSE_CLIS = {
    "agent_telemetry": ("--help",),
    "claude_md_rule_net": ("--help",),
    "cycle_budget": ("--help",),
    "daily_spend_rollup": ("--help",),
    "doc_citation_check": ("--help",),
    "issue_wheel_queue": ("run", "--help"),
    "record_model_exception": ("--help",),
    "spend_attribution": ("--help",),
    "wheel_batch_validate": ("--help",),
    "wheel_history": ("--help",),
    "wheel_launch_context": ("--help",),
    "wheel_sink": ("--help",),
}


def _is_argument_parser_ref(expr: ast.expr) -> bool:
    """`argparse.ArgumentParser` (attribute) or a bare imported `ArgumentParser`."""
    if isinstance(expr, ast.Attribute):
        return expr.attr == "ArgumentParser"
    return isinstance(expr, ast.Name) and expr.id == "ArgumentParser"


def _builds_argument_parser(source_path: Path) -> bool:
    """True when the module's AST calls `ArgumentParser(...)` or defines a class
    deriving from it (`class _Parser(argparse.ArgumentParser)`). A comment or a
    docstring that merely mentions argparse does not count."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_argument_parser_ref(node.func):
            return True
        if isinstance(node, ast.ClassDef) and any(_is_argument_parser_ref(b) for b in node.bases):
            return True
    return False


@pytest.mark.parametrize("module,argv", sorted(_ARGPARSE_CLIS.items()), ids=sorted(_ARGPARSE_CLIS))
def test_help_exits_zero_and_prints_usage(module, argv, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        # Help text may carry non-ASCII punctuation; do not let a C/POSIX locale
        # turn a perfectly good --help into a UnicodeEncodeError.
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.run(
        [sys.executable, str(_HOOKS_DIR / f"{module}.py"), *argv],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SEC,
        cwd=str(home),
        env=env,
    )
    shown = " ".join([f"{module}.py", *argv])
    assert proc.returncode == 0, (
        f"`{shown}` exited {proc.returncode} under "
        f"Python {sys.version_info.major}.{sys.version_info.minor}; "
        f"stderr tail:\n{proc.stderr[-1500:]}"
    )
    # argparse's OWN rendering, not just any text containing "usage:" (a hand-written
    # usage line, as issue_wheel_queue prints for a bare `--help`, would satisfy that):
    # the usage line, plus the `-h, --help` option with the help string argparse adds
    # to every parser that keeps add_help on.
    for expected in ("usage:", "-h, --help", "show this help message and exit"):
        assert expected in proc.stdout, (
            f"`{shown}` did not print argparse's help text (missing {expected!r}) on stdout:\n"
            f"{proc.stdout[:500]}"
        )


def test_the_cli_list_is_complete():
    """PAIRED COMPLETENESS CHECK: the list above is the contract, so a module
    that builds an ArgumentParser but is missing from it would never have its
    `--help` exercised -- the exact blind spot this file exists to close."""
    found = sorted(p.stem for p in _HOOKS_DIR.glob("*.py") if _builds_argument_parser(p))
    assert found == sorted(_ARGPARSE_CLIS), (
        "hooks/*.py modules that build an argparse.ArgumentParser differ from the list in "
        f"test_cli_help.py.\n  on disk: {found}\n  listed:  {sorted(_ARGPARSE_CLIS)}\n"
        "Add a new CLI to the list (it must then pass `--help`); a module that no longer "
        "uses argparse comes off it."
    )
