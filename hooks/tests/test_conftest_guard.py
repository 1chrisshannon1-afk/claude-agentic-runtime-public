"""Tests for the foreign-root session guard in hooks/tests/conftest.py.

Spec (public-repo plan, section 1, "CI layout"): the suite tests the DEPLOYED
shape, so a session started from a checkout that is not `realpath($HOME/.claude)`
must abort up front with a pointer to `scripts/ci_layout.sh`, instead of failing
hundreds of tests with `~/.claude/scripts/<x>.sh: No such file`. The one escape
is the explicit opt-out `CSA_TESTS_ALLOW_FOREIGN_ROOT=1` (exactly `1`).

Two layers:
  * the pure rule, `_foreign_root_problem(checkout_root, home, environ)`, tested
    directly -- allowed iff the opt-out is exactly "1" or the realpaths match
    (so a symlinked `$HOME/.claude` pointing at the checkout is allowed);
  * the real pytest hook, tested through a subprocess that runs a scratch copy of
    `conftest.py` in a root OUTSIDE the sandboxed HOME: exit 2 with the message,
    exit 0 with the opt-out, and exit 0 when that same root IS `$HOME/.claude`.
    Each refusal is paired with its recovery, so the guard cannot pass by
    refusing everything.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = _TESTS_DIR.parent
_CONFTEST = _TESTS_DIR / "conftest.py"
_LIB = _HOOKS_DIR / "_lib.py"
_OPT_OUT = "CSA_TESTS_ALLOW_FOREIGN_ROOT"


@pytest.fixture(scope="module")
def guard():
    """conftest.py loaded as an ordinary module, to reach its pure rule."""
    spec = importlib.util.spec_from_file_location("_csa_conftest_under_test", _CONFTEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _home_and_clone(tmp_path: Path) -> "tuple[Path, Path]":
    home = tmp_path / "home"
    home.mkdir()
    clone = tmp_path / "clone"
    clone.mkdir()
    return home, clone


class TestForeignRootProblem:
    def test_checkout_that_is_home_dot_claude_is_allowed(self, guard, tmp_path):
        home = tmp_path / "home"
        checkout = home / ".claude"
        checkout.mkdir(parents=True)
        assert guard._foreign_root_problem(str(checkout), str(home), {}) is None

    def test_foreign_checkout_is_refused_with_a_pointer_to_ci_layout(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        (home / ".claude").mkdir()
        problem = guard._foreign_root_problem(str(clone), str(home), {})
        assert problem is not None
        assert "scripts/ci_layout.sh" in problem
        assert os.path.realpath(clone) in problem  # names the checkout it refused
        assert _OPT_OUT in problem  # and the explicit way out

    def test_missing_home_dot_claude_still_counts_as_foreign(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        assert guard._foreign_root_problem(str(clone), str(home), {}) is not None

    def test_symlinked_home_dot_claude_pointing_at_the_checkout_is_allowed(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        os.symlink(clone, home / ".claude")
        assert guard._foreign_root_problem(str(clone), str(home), {}) is None
        # and the same checkout reached through the link itself
        assert guard._foreign_root_problem(str(home / ".claude"), str(home), {}) is None

    def test_symlink_to_a_different_checkout_is_still_refused(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        other = tmp_path / "other"
        other.mkdir()
        os.symlink(other, home / ".claude")
        assert guard._foreign_root_problem(str(clone), str(home), {}) is not None

    def test_opt_out_of_exactly_one_allows_a_foreign_checkout(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        assert guard._foreign_root_problem(str(clone), str(home), {_OPT_OUT: "1"}) is None

    @pytest.mark.parametrize("value", ["0", "true", "", "yes", "2", " 1", "1 "])
    def test_any_other_opt_out_value_is_still_refused(self, guard, tmp_path, value):
        home, clone = _home_and_clone(tmp_path)
        assert guard._foreign_root_problem(str(clone), str(home), {_OPT_OUT: value}) is not None

    def test_an_unrelated_variable_is_not_an_opt_out(self, guard, tmp_path):
        home, clone = _home_and_clone(tmp_path)
        assert guard._foreign_root_problem(str(clone), str(home), {"CSA_ENFORCE": "1"}) is not None

    def test_the_guard_measures_this_repos_root(self, guard):
        """`_CHECKOUT_ROOT` must be the repo root (two levels above this file's
        directory), or every run -- including the deployed one -- would judge the
        wrong directory."""
        assert os.path.realpath(guard._CHECKOUT_ROOT) == os.path.realpath(_TESTS_DIR.parents[1])


# ---------------------------------------------------------------------------
# The real pytest hook, end to end.
# ---------------------------------------------------------------------------


def _stage_checkout(root: Path) -> None:
    """A minimal checkout around a scratch COPY of the conftest under test:
    `hooks/tests/conftest.py` (+ the `hooks/_lib.py` it imports) and one
    trivial passing test. The empty pytest.ini pins the rootdir here."""
    tests = root / "hooks" / "tests"
    tests.mkdir(parents=True)
    shutil.copy2(_CONFTEST, tests / "conftest.py")
    shutil.copy2(_LIB, root / "hooks" / "_lib.py")
    (tests / "test_trivial.py").write_text(
        "def test_trivial():\n    assert True\n", encoding="utf-8"
    )
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")


def _pytest_in(
    root: Path, home: Path, extra_env: "dict | None" = None
) -> subprocess.CompletedProcess:
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    env.update(extra_env or {})
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "hooks/tests/test_trivial.py",
        ],
        cwd=str(root),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestPytestHook:
    def test_session_from_a_foreign_root_aborts_with_exit_2_and_the_message(self, tmp_path):
        home = tmp_path / "sandbox_home"
        home.mkdir()
        foreign = tmp_path / "foreign_clone"
        _stage_checkout(foreign)
        proc = _pytest_in(foreign, home)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 2, out
        assert "scripts/ci_layout.sh" in out, out
        assert _OPT_OUT in out, out
        assert "1 passed" not in out, out  # it aborted; the trivial test never ran

    def test_the_opt_out_lets_the_same_foreign_root_run(self, tmp_path):
        home = tmp_path / "sandbox_home"
        home.mkdir()
        foreign = tmp_path / "foreign_clone"
        _stage_checkout(foreign)
        proc = _pytest_in(foreign, home, {_OPT_OUT: "1"})
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        assert "1 passed" in out, out

    def test_the_same_checkout_staged_as_home_dot_claude_runs_without_the_opt_out(self, tmp_path):
        home = tmp_path / "sandbox_home"
        home.mkdir()
        _stage_checkout(home / ".claude")
        proc = _pytest_in(home / ".claude", home)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        assert "1 passed" in out, out
