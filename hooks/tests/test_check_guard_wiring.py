"""Tests for scripts/check_guard_wiring.py, the fail-closed CLI wrapper around
hooks/check_safety_core_parity.py's pure check().

Spec (the script's docstring and the grade-A plan's acceptance #2): the wrapper
examines a given checkout (``--repo``), prints how many guard modules it
examined, exits 1 on ANY reported problem, and is independent of ``$HOME``.
``check_safety_core_parity.main()`` always exits 0, which is exactly why this
wrapper exists, so each test below asserts on the exit code and the printed
count, never on the module's own return value.

Every case builds a scratch checkout under tmp_path and runs the script in a
subprocess with a throwaway HOME, so the real ~/.claude is never read.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_guard_wiring.py"

GUARD_SOURCE = "import _lib\n\n\ndef main():\n    _lib.emit_pretooluse_deny('no')\n"
ALLOWLIST = {
    "allowed_origins": [],
    "allowed_company_tenants": [],
    "test_recipients": [],
    "denied_action_patterns": [],
}


def _settings(*commands: str) -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": c} for c in commands],
                }
            ]
        }
    }


def _make_repo(
    root: Path,
    *,
    settings: dict,
    hooks: dict,
    allowlist: object = ALLOWLIST,
    scripts: tuple = (),
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.json").write_text(json.dumps(settings))
    (root / "hooks").mkdir(exist_ok=True)
    for name, text in hooks.items():
        (root / "hooks" / name).write_text(text)
    if scripts:
        (root / "scripts").mkdir(exist_ok=True)
        for name in scripts:
            (root / "scripts" / name).write_text("#!/bin/sh\n")
    if allowlist is not None:
        (root / "live-testing").mkdir(exist_ok=True)
        (root / "live-testing" / "allowlist.json").write_text(json.dumps(allowlist))
    return root


def _run(*args: str, home: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CSA_", "CLAUDE_"))}
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _examined(out: str) -> int:
    m = re.search(r"guard modules examined: (\d+)", out)
    assert m, "the wrapper must print how many guard modules it examined; got:\n" + out
    return int(m.group(1))


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "fakehome"
    h.mkdir()
    return h


@pytest.fixture
def wired_repo(tmp_path: Path) -> Path:
    """One dispatcher wired from settings.json that imports one guard."""
    return _make_repo(
        tmp_path / "repo",
        settings=_settings("python3 ~/.claude/hooks/dispatcher.py"),
        hooks={"dispatcher.py": "import wired_guard\n", "wired_guard.py": GUARD_SOURCE},
    )


def test_clean_checkout_exits_zero_and_reports_the_module_count(wired_repo, home, tmp_path):
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 1
    assert "problems: 0" in proc.stdout


def test_unwired_guard_exits_one_and_names_the_module(wired_repo, home, tmp_path):
    (wired_repo / "hooks" / "orphan_guard.py").write_text(GUARD_SOURCE)
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "orphan_guard.py" in proc.stdout
    assert _examined(proc.stdout) == 2


def test_wiring_the_orphan_recovers(wired_repo, home, tmp_path):
    """Pairing for the unwired-guard denial: importing it from the wired
    dispatcher makes the same checkout pass again."""
    (wired_repo / "hooks" / "orphan_guard.py").write_text(GUARD_SOURCE)
    assert _run("--repo", str(wired_repo), home=home, cwd=tmp_path).returncode == 1
    (wired_repo / "hooks" / "dispatcher.py").write_text("import wired_guard\nimport orphan_guard\n")
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 2


def test_guard_reached_through_a_shell_dispatcher_body_counts_as_wired(home, tmp_path):
    """settings.json -> gate.sh -> python3 "$HOME/.claude/hooks/x.py": the
    $HOME spelling inside a .sh body must resolve to the checkout's own file,
    wherever HOME points."""
    repo = _make_repo(
        tmp_path / "repo",
        settings=_settings("bash ~/.claude/hooks/gate.sh"),
        hooks={
            "gate.sh": '#!/bin/bash\nexec python3 "$HOME/.claude/hooks/wired_guard.py"\n',
            "wired_guard.py": GUARD_SOURCE,
        },
    )
    proc = _run("--repo", str(repo), home=home, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 1


def test_wired_command_naming_a_missing_script_exits_one(home, tmp_path):
    repo = _make_repo(
        tmp_path / "repo",
        settings=_settings("python3 ~/.claude/hooks/ghost.py", "python3 ~/.claude/hooks/real.py"),
        hooks={"real.py": GUARD_SOURCE},
    )
    proc = _run("--repo", str(repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "missing script" in proc.stdout and "ghost.py" in proc.stdout


@pytest.mark.parametrize(
    "allowlist, needle",
    [
        (None, "allowlist.json is absent"),
        ({"allowed_origins": []}, "missing required key"),
    ],
)
def test_allowlist_problems_exit_one(wired_repo, home, tmp_path, allowlist, needle):
    path = wired_repo / "live-testing" / "allowlist.json"
    if allowlist is None:
        path.unlink()
    else:
        path.write_text(json.dumps(allowlist))
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert needle in proc.stdout


def test_missing_settings_json_exits_one(wired_repo, home, tmp_path):
    (wired_repo / "settings.json").unlink()
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_declared_standalone_guard_is_not_reported_and_not_counted(wired_repo, home, tmp_path):
    """A guard the checker declares standalone is exempt from the wiring walk, so
    it proves nothing about wiring and must not inflate the examined count."""
    (wired_repo / "hooks" / "mint_prod_session.py").write_text(GUARD_SOURCE)
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 1
    assert "declared standalone, not counted: 1" in proc.stdout


def test_a_checkout_whose_only_guard_is_standalone_is_a_vacuous_pass(home, tmp_path):
    repo = _make_repo(
        tmp_path / "repo",
        settings=_settings("python3 ~/.claude/hooks/plain.py"),
        hooks={"plain.py": "print('x')\n", "mint_prod_session.py": GUARD_SOURCE},
    )
    proc = _run("--repo", str(repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 0
    assert "vacuous" in proc.stdout
    assert _run("--repo", str(repo), "--min-modules", "0", home=home, cwd=tmp_path).returncode == 0


@pytest.mark.parametrize("bad", ["-1", "-100", "abc", "1.5"])
def test_min_modules_must_be_a_non_negative_integer(wired_repo, home, tmp_path, bad):
    """A negative minimum would turn the vacuous-pass guard off by arithmetic."""
    proc = _run("--repo", str(wired_repo), "--min-modules", bad, home=home, cwd=tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "--min-modules" in proc.stderr


def test_the_checker_is_this_checkouts_own_never_the_one_in_the_repo_under_examination(
    wired_repo, home, tmp_path
):
    """The verdict on a checkout comes from a checker that checkout cannot have
    weakened: a stubbed hooks/check_safety_core_parity.py inside --repo, which would
    report no problems for anything, must not be what judges it."""
    (wired_repo / "hooks" / "orphan_guard.py").write_text(GUARD_SOURCE)
    (wired_repo / "hooks" / "check_safety_core_parity.py").write_text(
        "STANDALONE_GUARD_MODULES = frozenset()\n"
        "def check(*args, **kwargs):\n    return []\n"
        "def looks_like_pretooluse_guard(*args, **kwargs):\n    return False\n"
        "def _gather(*args, **kwargs):\n    return {}\n"
    )
    proc = _run("--repo", str(wired_repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "orphan_guard.py" in proc.stdout


def test_zero_guard_modules_is_a_failure_unless_explicitly_allowed(home, tmp_path):
    """A check that examined nothing proves nothing: it must not exit 0 by
    default, and the escape hatch must be explicit."""
    repo = _make_repo(
        tmp_path / "repo",
        settings=_settings("python3 ~/.claude/hooks/plain.py"),
        hooks={"plain.py": "print('not a guard')\n"},
    )
    proc = _run("--repo", str(repo), home=home, cwd=tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert _examined(proc.stdout) == 0
    assert _run("--repo", str(repo), "--min-modules", "0", home=home, cwd=tmp_path).returncode == 0


def test_result_does_not_depend_on_home(wired_repo, tmp_path):
    """HOME-independence: the same checkout gives the same verdict whether HOME
    is a fresh directory, a path that does not exist, or the checkout itself."""
    (wired_repo / "hooks" / "orphan_guard.py").write_text(GUARD_SOURCE)
    homes = [tmp_path / "h1", tmp_path / "does" / "not" / "exist", wired_repo]
    (tmp_path / "h1").mkdir()
    verdicts = {_run("--repo", str(wired_repo), home=h, cwd=tmp_path).returncode for h in homes}
    assert verdicts == {1}
    (wired_repo / "hooks" / "orphan_guard.py").unlink()
    verdicts = {_run("--repo", str(wired_repo), home=h, cwd=tmp_path).returncode for h in homes}
    assert verdicts == {0}


def test_repo_that_is_not_a_directory_is_a_usage_error(home, tmp_path):
    proc = _run("--repo", str(tmp_path / "nope"), home=home, cwd=tmp_path)
    assert proc.returncode == 2
    assert "not a directory" in proc.stderr


def test_default_repo_is_the_checkout_the_script_lives_in(home, tmp_path):
    """Run against the real checkout (no --repo): whatever it reports today,
    the exit code must agree with the printed problem count, and at least one
    guard module must have been examined."""
    proc = _run(home=home, cwd=tmp_path)
    out = proc.stdout
    m_repo = re.search(r"repo=(.+)", out)
    assert m_repo and os.path.realpath(m_repo.group(1).strip()) == os.path.realpath(str(REPO)), out
    assert _examined(out) >= 1
    m = re.search(r"problems: (\d+)", out)
    assert m, out
    assert proc.returncode == (1 if int(m.group(1)) else 0), out + proc.stderr
