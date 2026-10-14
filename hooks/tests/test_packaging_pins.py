"""Packaging pins that must agree across files, and the format-exclude recipe's parser.

Prior art: ``hooks/tests/test_ci_layout.sh`` already asserts that
``scripts/ci_layout.sh``'s ``PACKAGES`` equals ``pyproject.toml``'s test + lint
extras. It cannot see ``.pre-commit-config.yaml``, which pins the same linter by
git tag, and it accepts any version spelling. These tests close that gap, and
guard the two things that replacing the root ``pytest.ini`` with
``pyproject.toml`` put at risk (the ``live_machine`` marker registration, and a
resurrected ``pytest.ini`` silently shadowing it).

All three tests read repository files, so they skip (with the reason) when the
suite runs from a hooks-only install that has no ``pyproject.toml`` beside it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
CI_LAYOUT = ROOT / "scripts" / "ci_layout.sh"
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"

# `ruff==0.15.18` as spelled in pyproject.toml and in the PACKAGES array.
_EXACT_RUFF_PIN = re.compile(r'"ruff==([0-9]+(?:\.[0-9]+)*)"')
# Seconds any single ruff invocation may take before the test fails instead of hanging.
_TIMEOUT = 60
# The rev of the ruff-pre-commit repo entry, `rev: v0.15.18`.
_PRE_COMMIT_RUFF_REV = re.compile(r"ruff-pre-commit[ \t]*\n[ \t]*rev:[ \t]*v?([0-9]+(?:\.[0-9]+)*)")


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.skip("not a full checkout of the repository ({} is missing)".format(path.name))
    return path.read_text(encoding="utf-8")


def _ruff_command() -> Optional[List[str]]:
    """The way to run ruff here: the interpreter's own module first, else the binary."""
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=_TIMEOUT,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "ruff"]
    binary = shutil.which("ruff")
    return [binary] if binary else None


def test_ruff_is_pinned_to_one_exact_version_in_all_three_places() -> None:
    """The format-exclude list is one ruff version's output, so the pin may not drift.

    pyproject.toml (lint extra), scripts/ci_layout.sh (PACKAGES) and
    .pre-commit-config.yaml (ruff-pre-commit rev) must name the same ruff, and
    the two package pins must be exact (``==``), not a range. pyproject.toml and
    the pre-commit rev are always compared; scripts/ci_layout.sh joins the
    comparison whenever it is present in the checkout.
    """
    pyproject_pin = _EXACT_RUFF_PIN.search(_read(PYPROJECT))
    hook_pin = _PRE_COMMIT_RUFF_REV.search(_read(PRE_COMMIT))

    assert pyproject_pin, 'pyproject.toml has no exact "ruff==X.Y.Z" pin in its lint extra'
    assert hook_pin, ".pre-commit-config.yaml has no ruff-pre-commit `rev: vX.Y.Z`"
    versions = {
        "pyproject.toml": pyproject_pin.group(1),
        ".pre-commit-config.yaml": hook_pin.group(1),
    }
    if CI_LAYOUT.is_file():
        layout_pin = _EXACT_RUFF_PIN.search(CI_LAYOUT.read_text(encoding="utf-8"))
        assert layout_pin, 'scripts/ci_layout.sh PACKAGES has no exact "ruff==X.Y.Z" pin'
        versions["scripts/ci_layout.sh"] = layout_pin.group(1)
    assert len(set(versions.values())) == 1, "ruff pins disagree: {}".format(versions)


def test_pytest_config_lives_in_pyproject_and_nothing_shadows_it() -> None:
    """pyproject.toml registers ``live_machine``; a root pytest.ini would silently win over it."""
    text = _read(PYPROJECT)
    assert "[tool.pytest.ini_options]" in text, "pyproject.toml lost its pytest section"
    section = text.split("[tool.pytest.ini_options]", 1)[1]
    assert re.search(r'^\s*"live_machine:', section, re.M), (
        "the live_machine marker is not registered in [tool.pytest.ini_options]; "
        "hooks/tests/ would warn on every run and error under --strict-markers"
    )
    assert not (ROOT / "pytest.ini").exists(), (
        "a root pytest.ini exists: pytest prefers it over pyproject.toml, so the "
        "[tool.pytest.ini_options] block is ignored. Delete pytest.ini."
    )


def test_format_exclude_recipe_parser_matches_the_installed_ruff(tmp_path: Path) -> None:
    """The recipe in pyproject.toml parses ``Would reformat: <path>``; prove that is still what ruff prints.

    The recipe pipes ``ruff format --check`` output (stdout and stderr) through
    ``sed -n 's/^Would reformat: //p'`` and fails when that yields nothing. If a
    ruff release changed the line, the recipe would fail loudly, and this test
    fails first and says why.
    """
    assert "sed -n 's/^Would reformat: //p'" in _read(PYPROJECT), (
        "the regeneration recipe in pyproject.toml no longer uses the parser this test validates"
    )
    pinned = _EXACT_RUFF_PIN.search(_read(PYPROJECT))
    assert pinned, 'pyproject.toml has no exact "ruff==X.Y.Z" pin in its lint extra'
    ruff = _ruff_command()
    if ruff is None:
        pytest.skip("ruff is not installed in this environment")
    installed = subprocess.run(
        ruff + ["--version"], capture_output=True, text=True, timeout=_TIMEOUT
    ).stdout.strip()
    if installed.split()[-1:] != [pinned.group(1)]:
        # The recipe is documented for the pinned ruff only; another version's
        # output format says nothing about the repo, so it must not turn the run red.
        pytest.skip(
            "the recipe requires ruff=={}, installed: {!r}".format(pinned.group(1), installed)
        )

    ugly = tmp_path / "needs_format.py"
    ugly.write_text("x = {  'a':1,'b' :2 }\n", encoding="utf-8")
    tidy = tmp_path / "already_formatted.py"
    tidy.write_text('x = {"a": 1}\n', encoding="utf-8")

    def check(path: Path) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            ruff + ["format", "--check", "--isolated", "--no-cache", str(path)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=_TIMEOUT,
        )

    version = installed
    flagged = check(ugly)
    merged = flagged.stdout + flagged.stderr
    assert flagged.returncode == 1, "{}: expected exit 1, got {}\n{}".format(
        version, flagged.returncode, merged
    )
    parsed = re.findall(r"^Would reformat: (.+)$", merged, re.M)
    assert parsed == [str(ugly)], "{}: no `Would reformat:` line:\n{}".format(version, merged)

    clean = check(tidy)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert not re.findall(r"^Would reformat: ", clean.stdout + clean.stderr, re.M)
