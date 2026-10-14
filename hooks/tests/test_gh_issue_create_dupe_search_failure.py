"""Tests for gh_issue.sh `create`'s dedupe-search fail-CLOSED behavior
(#5827, 2026-09-20; round 2 same day: mktemp-optionality).

THE DEFECT: `_find_dupes()` ran the `gh issue list --search ...` dedupe query
and, on ANY failure of that command (network error, auth error, GitHub rate
limit — all three were observed on this machine the day this was filed),
swallowed the error and left `DUPES` empty -- indistinguishable from "searched
and found nothing." `create` then filed the issue with no duplicate check at
all. Measured cause of a 1,469-issue backlog: agents filing duplicates when
the dedupe search silently failed.

Spec (this is what these tests assert -- not whatever the code happened to do
before the fix):
  1. Dedupe search command exits non-zero, or its output is unparseable ->
     `create` REFUSES: non-zero exit, no `gh issue create` call reaches gh,
     stderr names gh's own error text, says to retry, and names the escape
     hatch `--force-new`.
  2. `--force-new` retains its EXISTING, pre-#5827 meaning exactly (fix-round
     2 correction, 2026-09-20): it SKIPS the dedupe search ENTIRELY -- `gh
     issue list` is never called at all under --force-new, so a search that
     would have failed (or matched) is never actually run to find out. This
     was deliberately restored after an earlier draft of this fix made
     --force-new run the search anyway just to detect+log a failure, which
     both changed the flag's documented meaning and cost a real GitHub
     GraphQL call on every forced create. The bypass is still logged
     unconditionally (stderr, the script's existing `gh_issue: ...`
     convention -- no new log file): "duplicate check SKIPPED (--force-new
     given)".
  3. A search that succeeds with no overlap creates, unchanged. A search that
     succeeds with overlap still refuses unless --force-new/--related,
     unchanged.
  4. The FAIL-CLOSED signal is the search command's real EXIT STATUS, never
     the availability of `mktemp` -- `mktemp` is optional plumbing used only
     to capture nicer error TEXT. `create` is a hot path unattended
     launchd/cron jobs run with a minimal PATH that can genuinely lack
     `mktemp`; a missing `mktemp` must never itself manufacture a false
     "search failed" for a search that actually succeeded (round-2 blocker:
     it did, inverting the whole fix -- a real duplicate went unreported and
     unattended jobs would file it anyway via the --force-new advice). This
     only applies on the non---force-new branch, since --force-new never
     reaches the search (or mktemp) at all per point 2.
  5. Captured gh stderr is truncated before landing in the refusal message
     (round-2 finding 6) -- an oversized error payload must not blow up the
     message shown to the caller.

Same conventions as test_gh_issue_dispose.py / test_gh_issue_evidence_repo.py:
the real script runs with a stubbed `gh` on PATH that records its argv to
$GH_LOG, so shapes are asserted without any network call. SCRIPT honors
GH_ISSUE_SCRIPT so this suite can be pointed at a scratch pre-fix copy to
prove the RED case actually fails without the fix (falsifiability).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = os.environ.get(
    "GH_ISSUE_SCRIPT", str(Path.home() / ".claude" / "scripts" / "gh_issue.sh")
)

# gh stub: any `issue list --search ...` (the dedupe query) fails outright,
# simulating a network/auth/rate-limit error. Any `issue create` call is
# logged, so a test can assert it was (or was NOT) reached.
_GH_STUB_SEARCH_FAILS = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  echo "error connecting to api.github.com: connection reset" >&2
  exit 1
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
  echo "https://github.com/o/r/issues/999"
  exit 0
fi
exit 0
"""

# gh stub: the dedupe query succeeds and returns zero matches (empty stdout).
_GH_STUB_SEARCH_EMPTY = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
  echo "https://github.com/o/r/issues/1000"
  exit 0
fi
exit 0
"""

# gh stub: the dedupe query succeeds and returns one overlapping OPEN issue.
_GH_STUB_SEARCH_MATCH = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  printf '123\\tExisting overlapping title\\thttps://github.com/o/r/issues/123\\n'
  exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
  echo "https://github.com/o/r/issues/1001"
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
    body.write_text("body text")
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_LOG"] = str(log)
    proc = subprocess.run(
        ["bash", SCRIPT, "create", "--title", *args, "--body-file", str(body)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc, log.read_text()


def test_search_failure_refuses_create(tmp_path):
    """(a) Forced gh search failure -> create refuses, non-zero, no `issue
    create` call reaches the fake gh, message names --force-new."""
    proc, log = _run(
        tmp_path, _GH_STUB_SEARCH_FAILS, "Some new bug about widgets breaking"
    )
    assert proc.returncode != 0, proc.stdout
    assert not any(
        line.startswith("issue create") for line in log.splitlines()
    ), "create must never be reached when the dedupe search failed and --force-new was not given"
    # Names gh's own error text, and the escape hatch.
    assert "connection reset" in proc.stderr
    assert "--force-new" in proc.stderr
    # Tells the caller to retry.
    assert "retry" in proc.stderr.lower()


def test_search_failure_with_force_new_creates_and_logs_bypass(tmp_path):
    """(b) PAIRED RECOVERY: the same call with --force-new succeeds and the
    bypass is logged to stderr -- CORRECTED design (coordinator fix-round 2,
    2026-09-20): --force-new's EXISTING meaning is preserved exactly -- it
    SKIPS the dedupe search entirely, it never calls `gh issue list` at all,
    regardless of whether that (never-run) search would have failed. The
    "search would fail" framing in this test's title describes the scenario
    the stub is built for (so this test doubles as the paired recovery for
    test_search_failure_refuses_create above); the search is never actually
    reached under --force-new to find out."""
    proc, log = _run(
        tmp_path,
        _GH_STUB_SEARCH_FAILS,
        "Some new bug about widgets breaking",
        "--force-new",
    )
    assert proc.returncode == 0, proc.stderr
    assert not any(
        line.startswith("issue list") for line in log.splitlines()
    ), "--force-new must SKIP the dedupe search entirely -- 'gh issue list' must never be called"
    assert any(
        line.startswith("issue create") for line in log.splitlines()
    ), "create should have been reached with --force-new"
    # The bypass itself must be visibly logged (script's own gh_issue: stderr
    # convention -- not a new log file) -- unconditionally, not contingent on
    # a search outcome that was never actually observed.
    assert "gh_issue:" in proc.stderr
    assert "--force-new" in proc.stderr
    assert "skip" in proc.stderr.lower() or "duplicate check" in proc.stderr.lower()


def test_search_succeeds_no_matches_creates(tmp_path):
    """(c) Search succeeds with zero matches -> creates (guards against
    over-refusing when the search genuinely works and finds nothing)."""
    proc, log = _run(
        tmp_path, _GH_STUB_SEARCH_EMPTY, "A totally unique title with no overlap"
    )
    assert proc.returncode == 0, proc.stderr
    assert any(line.startswith("issue create") for line in log.splitlines())


def test_search_succeeds_with_match_refuses_unchanged(tmp_path):
    """(d) Search succeeds with a match -> existing behavior unchanged: still
    refuses without --force-new/--related, and names the existing issue."""
    proc, log = _run(
        tmp_path, _GH_STUB_SEARCH_MATCH, "Existing overlapping title for real"
    )
    assert proc.returncode != 0
    assert not any(line.startswith("issue create") for line in log.splitlines())
    assert "#123" in proc.stderr or "123" in proc.stderr
    assert "--force-new" in proc.stderr


def test_search_succeeds_with_match_force_new_still_creates(tmp_path):
    """Companion: --force-new still overrides a genuine match exactly as
    before (unchanged existing behavior, not part of this fix) -- and, per
    the corrected design, it does so WITHOUT ever calling the search at all:
    the fake `gh` here would return a match if asked, but --force-new must
    never ask."""
    proc, log = _run(
        tmp_path,
        _GH_STUB_SEARCH_MATCH,
        "Existing overlapping title for real",
        "--force-new",
    )
    assert proc.returncode == 0, proc.stderr
    assert not any(
        line.startswith("issue list") for line in log.splitlines()
    ), "--force-new must SKIP the dedupe search entirely -- 'gh issue list' must never be called"
    assert any(line.startswith("issue create") for line in log.splitlines())


# ---------------------------------------------------------------------------
# Round 2 (#5827 fix-round, 2026-09-20 -- Opus blocker): mktemp must be
# OPTIONAL on the create hot path. These tests build a hermetic PATH dir
# (mirroring scripts/legacy/tests/test_gh_issue.sh's own _mkbin) containing
# only the specific tools gh_issue.sh needs, deliberately WITHOUT `mktemp` --
# exactly the shape a minimal launchd/cron PATH takes. `bash` is symlinked
# onto it too, since the stub `gh`'s `#!/usr/bin/env bash` shebang resolves
# "bash" via THIS restricted PATH once `env` is invoked under it.
# ---------------------------------------------------------------------------


_hermetic_call_counter = 0


def _mkbin_no_mktemp(bindir: Path) -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    for tool in ("git", "awk", "tr", "cat", "head", "bash", "env", "grep"):
        real = shutil.which(tool)
        assert real, f"test environment is missing {tool!r} on the real PATH"
        (bindir / tool).symlink_to(real)


def _hermetic_workdir(tmp_path: Path) -> Path:
    # Each call gets its OWN fresh subdirectory -- a test that calls the
    # hermetic runner twice (e.g. the search-fails-then---force-new-recovers
    # paired-recovery case) must not reuse one bindir, since symlink_to()
    # fails outright on an already-populated bindir from a prior call.
    global _hermetic_call_counter
    _hermetic_call_counter += 1
    d = tmp_path / f"call{_hermetic_call_counter}"
    d.mkdir()
    return d


def _run_hermetic(tmp_path: Path, stub: str, *args: str, with_mktemp: bool = False):
    work = _hermetic_workdir(tmp_path)
    bindir = work / "bin"
    _mkbin_no_mktemp(bindir)
    if with_mktemp:
        real_mktemp = shutil.which("mktemp")
        assert real_mktemp
        (bindir / "mktemp").symlink_to(real_mktemp)
    gh = bindir / "gh"
    gh.write_text(stub)
    gh.chmod(0o755)
    log = work / "gh.log"
    log.write_text("")
    body = work / "body.md"
    body.write_text("body text")
    env = {"PATH": str(bindir), "GH_LOG": str(log), "HOME": os.environ.get("HOME", "")}
    proc = subprocess.run(
        ["bash", SCRIPT, "create", "--title", *args, "--body-file", str(body)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc, log.read_text()


def _run_hermetic_related(tmp_path: Path, stub: str, related: str, *args: str):
    work = _hermetic_workdir(tmp_path)
    bindir = work / "bin"
    _mkbin_no_mktemp(bindir)
    gh = bindir / "gh"
    gh.write_text(stub)
    gh.chmod(0o755)
    log = work / "gh.log"
    log.write_text("")
    body = work / "body.md"
    body.write_text("body text")
    env = {"PATH": str(bindir), "GH_LOG": str(log), "HOME": os.environ.get("HOME", "")}
    proc = subprocess.run(
        [
            "bash",
            SCRIPT,
            "create",
            "--title",
            *args,
            "--body-file",
            str(body),
            "--related",
            related,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc, log.read_text()


def test_no_mktemp_search_match_refuses_naming_the_real_dupe(tmp_path):
    """(1) mktemp ABSENT from PATH + search returns a real match -> create
    refuses NAMING #123, and must NOT claim the search itself failed. This is
    the round-2 blocker's exact inversion: a missing mktemp must never turn a
    real successful match into a false "search failed"."""
    proc, log = _run_hermetic(
        tmp_path, _GH_STUB_SEARCH_MATCH, "Existing overlapping title for real"
    )
    assert proc.returncode != 0
    assert not any(line.startswith("issue create") for line in log.splitlines())
    assert "#123" in proc.stderr, proc.stderr
    assert "refusing to create a likely-duplicate issue" in proc.stderr
    assert "duplicate search failed" not in proc.stderr, proc.stderr
    # The real search must actually have been reached and found the match --
    # not silently skipped.
    assert any(line.startswith("issue list") for line in log.splitlines())


def test_no_mktemp_search_empty_creates(tmp_path):
    """(2) mktemp ABSENT + search returns nothing -> creates (mktemp's
    absence must not block a genuinely clean search either)."""
    proc, log = _run_hermetic(
        tmp_path, _GH_STUB_SEARCH_EMPTY, "A totally unique title with no overlap"
    )
    assert proc.returncode == 0, proc.stderr
    assert any(line.startswith("issue create") for line in log.splitlines())


def test_no_mktemp_search_fails_refuses_and_force_new_recovers(tmp_path):
    """(3) mktemp ABSENT + search genuinely exits non-zero -> refuses as a
    search failure (error text may be empty/generic, since there's no temp
    file to carry gh's stderr through without mktemp) -- and the paired
    recovery with --force-new creates and logs the bypass. Per the corrected
    design, --force-new never reaches the search at all (mktemp's presence or
    absence is moot on that branch), so the recovery half only asserts the
    SKIP behavior, not anything mktemp-specific."""
    proc, log = _run_hermetic(
        tmp_path, _GH_STUB_SEARCH_FAILS, "Some new bug about widgets breaking"
    )
    assert proc.returncode != 0, proc.stdout
    assert not any(line.startswith("issue create") for line in log.splitlines())
    assert "--force-new" in proc.stderr
    assert "retry" in proc.stderr.lower()

    # Paired recovery: --force-new skips the (never-run) search entirely.
    proc2, log2 = _run_hermetic(
        tmp_path,
        _GH_STUB_SEARCH_FAILS,
        "Some new bug about widgets breaking",
        "--force-new",
    )
    assert proc2.returncode == 0, proc2.stderr
    assert not any(
        line.startswith("issue list") for line in log2.splitlines()
    ), "--force-new must SKIP the dedupe search entirely -- 'gh issue list' must never be called"
    assert any(line.startswith("issue create") for line in log2.splitlines())
    assert "gh_issue:" in proc2.stderr
    assert "--force-new" in proc2.stderr
    assert "skip" in proc2.stderr.lower() or "duplicate check" in proc2.stderr.lower()


def test_related_short_circuits_before_dedupe_search_even_on_failure(tmp_path):
    """(4) --related <n> with a hard-failing search -> exits 0, posts the
    cross-reference comment, and NEVER calls `gh issue list` at all --
    --related creates no issue, so there is nothing to dedupe-check; this is
    CORRECT existing behavior, pinned here so it is never "fixed" into
    running the search it has no need for."""
    proc, log = _run_hermetic_related(
        tmp_path, _GH_STUB_SEARCH_FAILS, "42", "Any title, --related short-circuits"
    )
    assert proc.returncode == 0, proc.stderr
    assert not any(
        line.startswith("issue list") for line in log.splitlines()
    ), "--related must short-circuit BEFORE the dedupe search runs"
    assert any(line.startswith("issue comment 42") for line in log.splitlines())
    assert not any(line.startswith("issue create") for line in log.splitlines())


def test_oversized_gh_stderr_truncated_in_refusal_message(tmp_path):
    """(5) 200 KB of gh stderr on a genuine search failure -> the refusal
    message stays small (~1 KB), never echoing the payload verbatim."""
    huge_stub = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  yes "x" | head -c 200000 >&2
  exit 1
fi
exit 0
"""
    proc, log = _run_hermetic(
        tmp_path, huge_stub, "A title whose search blows up with huge stderr", with_mktemp=True
    )
    assert proc.returncode != 0
    assert not any(line.startswith("issue create") for line in log.splitlines())
    assert len(proc.stderr) < 2000, f"refusal message was {len(proc.stderr)} bytes, expected ~1KB or less"
