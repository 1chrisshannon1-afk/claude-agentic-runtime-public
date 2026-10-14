"""Tests for gh_issue.sh's `dispose` subcommand (#4400, 2026-08-23).

Runs the real script with a stubbed `gh` on PATH that records its argv, so the
emitted close command's shape (reason + Disposition marker in the SAME
invocation) is asserted without any network.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = str(Path.home() / ".claude" / "scripts" / "gh_issue.sh")

_GH_STUB_OK = """#!/bin/bash
echo "$@" >> "$GH_LOG"
exit 0
"""

_GH_STUB_VIEW_NOT_FOUND = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "GraphQL: Could not resolve to an issue (not found)" >&2
  exit 1
fi
exit 0
"""

_GH_STUB_VIEW_CLOSED = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "CLOSED"
  exit 0
fi
exit 0
"""

_GH_STUB_VIEW_OPEN = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "OPEN"
  exit 0
fi
exit 0
"""

_GH_STUB_VIEW_CLOSED_WITH_UPDATE_NOTICE = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "gh: A new release of gh is available: 2.88.1 -> 2.89.0" >&2
  echo "CLOSED"
  exit 0
fi
exit 0
"""


def _run(tmp_path: Path, stub: str, *args: str):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(stub)
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    body = tmp_path / "body.md"
    body.write_text("no longer relevant; superseded by the oversight wheel")
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_LOG"] = str(log)
    proc = subprocess.run(
        ["bash", SCRIPT, *args, "--body-file", str(body)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc, log.read_text()


def test_dispose_emits_reason_and_marker_in_one_close(tmp_path):
    proc, log = _run(tmp_path, _GH_STUB_OK, "dispose", "42", "--disposition", "stale-superseded")
    assert proc.returncode == 0, proc.stderr
    assert "OK disposed #42" in proc.stdout
    close_lines = [line for line in log.splitlines() if line.startswith("issue close")]
    assert len(close_lines) == 1
    line = close_lines[0]
    assert "not planned" in line
    assert "Disposition: stale-superseded" in line  # marker in the SAME command


def test_dispose_wont_fix_allowed(tmp_path):
    proc, log = _run(tmp_path, _GH_STUB_OK, "dispose", "43", "--disposition", "wont-fix")
    assert proc.returncode == 0, proc.stderr
    assert "Disposition: wont-fix" in log


def test_dispose_duplicate_of_checks_target(tmp_path):
    proc, log = _run(tmp_path, _GH_STUB_OK, "dispose", "44", "--disposition", "duplicate-of #123")
    assert proc.returncode == 0, proc.stderr
    assert any(line.startswith("issue view 123") for line in log.splitlines())
    assert "Disposition: duplicate-of #123" in log


def test_dispose_duplicate_of_nonexistent_refused(tmp_path):
    proc, log = _run(
        tmp_path, _GH_STUB_VIEW_NOT_FOUND, "dispose", "44", "--disposition", "duplicate-of #999"
    )
    assert proc.returncode != 0
    assert "does not exist" in proc.stderr
    assert not any(line.startswith("issue close") for line in log.splitlines())


def test_dispose_malformed_disposition_refused(tmp_path):
    proc, _log = _run(tmp_path, _GH_STUB_OK, "dispose", "45", "--disposition", "because-reasons")
    assert proc.returncode != 0
    assert "unknown disposition" in proc.stderr


def test_dispose_requires_body_file(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(_GH_STUB_OK)
    (bindir / "gh").chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_LOG"] = str(tmp_path / "gh.log")
    proc = subprocess.run(
        ["bash", SCRIPT, "dispose", "46", "--disposition", "wont-fix"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode != 0
    assert "body-file" in proc.stderr


_GH_STUB_VIEW_FLAKY = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "error connecting to api.github.com: connection reset" >&2
  exit 1
fi
exit 0
"""


def test_dispose_duplicate_of_indeterminate_fails_open_with_warning(tmp_path):
    # The security-relevant branch: gh errored for a NON-not-found reason
    # (offline/auth/rate-limit) -> proceed fail-open, but say so loudly.
    proc, log = _run(
        tmp_path, _GH_STUB_VIEW_FLAKY, "dispose", "47", "--disposition", "duplicate-of #500"
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" in proc.stderr and "fail-open" in proc.stderr
    assert any(line.startswith("issue close 47") for line in log.splitlines())
    assert "Disposition: duplicate-of #500" in log


def test_dispose_duplicate_of_closed_target_refused(tmp_path):
    # Regression for the agentic-systems-architect audit finding (2026-09-07):
    # the old check was existence-only (--json number), so a duplicate-of
    # pointing at an ALREADY-CLOSED issue passed silently. A resolvable-but-
    # CLOSED target must now be refused outright, not merely warned about.
    proc, log = _run(
        tmp_path, _GH_STUB_VIEW_CLOSED, "dispose", "48", "--disposition", "duplicate-of #600"
    )
    assert proc.returncode != 0
    assert "CLOSED" in proc.stderr
    assert not any(line.startswith("issue close") for line in log.splitlines())


def test_dispose_duplicate_of_open_target_allowed(tmp_path):
    # Companion positive case: a genuinely OPEN duplicate target still closes
    # cleanly through the new state-aware check.
    proc, log = _run(
        tmp_path, _GH_STUB_VIEW_OPEN, "dispose", "49", "--disposition", "duplicate-of #700"
    )
    assert proc.returncode == 0, proc.stderr
    assert any(line.startswith("issue close 49") for line in log.splitlines())
    assert "Disposition: duplicate-of #700" in log


def test_dispose_duplicate_of_closed_target_stderr_noise_still_refused(tmp_path):
    # Regression for a fix-round defect (code-reviewer, 2026-09-07): the
    # first cut of the state check merged stderr into the data channel
    # (`2>&1`). gh's own update-notifier writes to stderr on ANY command,
    # exit 0, so a genuinely CLOSED target with a stray notifier line no
    # longer matched the `CLOSED)` case arm and fell through to the fail-open
    # `*)` branch -- silently reintroducing the original bug. stdout and
    # stderr must be captured separately so notifier noise never touches the
    # state comparison.
    proc, log = _run(
        tmp_path,
        _GH_STUB_VIEW_CLOSED_WITH_UPDATE_NOTICE,
        "dispose",
        "50",
        "--disposition",
        "duplicate-of #800",
    )
    assert proc.returncode != 0
    assert "CLOSED" in proc.stderr
    assert "unexpected state" not in proc.stderr  # must hit the real CLOSED arm, not the catch-all
    assert not any(line.startswith("issue close") for line in log.splitlines())
