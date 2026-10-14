"""Tests for run_watchdog.sh's escalation regex (THE ISSUE WHEEL plan, WS1-B.2
/ Phase B item 2: `job-failed` and `unexpected-loaded` added to the three
pre-existing escalation classes).

These tests exercise the EXACT regex line lifted verbatim out of the real
script, run through the real `grep -E` binary — never launchd, never
`heartbeat_audit.py`, never `osascript` (per the task's own instruction: test
the regex line, not launchd). Extracting the pattern from the live script
(rather than hardcoding a duplicate string here) means a future edit to the
regex is caught by this test re-reading the real file, not silently drifted
from what actually ships.
"""

from __future__ import annotations

import os
import re
import subprocess

_WATCHDOG_SH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "schedules",
    "run_watchdog.sh",
)


def _extract_escalate_regex() -> str:
    """Pulls the `grep -E '<pattern>'` argument straight out of the real
    run_watchdog.sh's ESCALATE_LINES= line, so this test always exercises
    whatever pattern actually ships, never a hand-copied duplicate that can
    drift.
    """
    with open(_WATCHDOG_SH, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"grep -E '(\^\([^']+\):)'", text)
    assert m, "could not find the ESCALATE_LINES grep -E pattern in run_watchdog.sh"
    return m.group(1)


def _matches(line: str) -> bool:
    pattern = _extract_escalate_regex()
    proc = subprocess.run(
        ["grep", "-E", pattern],
        input=line + "\n",
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def test_escalate_regex_extracted_and_nonempty():
    pattern = _extract_escalate_regex()
    assert pattern.startswith("^(")
    assert pattern.endswith("):")


def test_job_failed_prefix_matches_escalation_regex():
    assert _matches("job-failed: com.oversight.wheel.agency has status: \"failed\"")


def test_unexpected_loaded_prefix_matches_escalation_regex():
    assert _matches(
        "unexpected-loaded: com.oversight.wheel.csa has expected_state 'unloaded' "
        "but IS currently loaded in launchctl"
    )


def test_pre_existing_three_classes_still_match():
    # Regression guard: adding the two new prefixes must not disturb the
    # three pre-existing escalation classes.
    assert _matches("silent-job: com.oversight.csa.testarch was scheduled 10.0h ago")
    assert _matches("loaded-never-fired: com.oversight.csa.daily is loaded but never fired")
    assert _matches(
        "expected-but-unloaded: com.oversight.wheel.csa has expected_state 'loaded' "
        "but is not currently loaded"
    )


def test_non_escalating_classes_do_not_match():
    # A finding class that stays visible in heartbeat_audit.py's own report
    # output but was never in scope for this watchdog's escalation (see the
    # script's own header comment) must not accidentally start matching.
    assert not _matches("unexpected-heartbeat: manual-foo.json is not in the table")
    assert not _matches("lock-refused: com.oversight.wheel.csa has exit: 75")
    assert not _matches("missing-keys: com.oversight.csa.daily missing required key(s): exit")


def test_prefix_must_anchor_at_start_of_line():
    # A finding class name appearing mid-line (e.g. inside a longer sentence)
    # must not falsely escalate -- the pattern is start-anchored.
    assert not _matches("something mentions job-failed later in the line")
