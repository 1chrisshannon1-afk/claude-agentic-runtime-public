"""Dashboard-staleness guard for scripts/render_cycle_log.py's output (P4,
#4872, missions_observability_adoption_plan.md §4).

Two independent regressions this file exists to catch mechanically, neither
of which any prior test covers:

1. `~/.claude/telemetry/cycle_log.html` silently drifting stale -- a cycle
   record lands under `~/.claude/telemetry/cycles/*/*.json` but nobody ever
   re-runs the renderer, so the operator-facing dashboard keeps showing old
   data with no visible warning. This test asserts freshness: the rendered
   file's mtime must not lag the newest cycle record's mtime by more than a
   tunable grace window (module constant GRACE_SECONDS, default 24h) --
   mirroring hooks/heartbeat_audit.py's own GRACE_SECONDS convention for
   "cadence + grace, never a bare comparison."

2. `~/.claude/telemetry/loop_log.html` regressing from a symlink (its P0.1
   fixed state -- see hooks/tests/test_gitignore_corpus_protection.py:111's
   sibling comment) back into a real, hand-copied regular file -- the
   loop_status_duplication failure mode this repo has hit before in HTML
   form (AA-0084). This is a REGULAR-FILE guard, not a "must exist" guard:
   an absent loop_log.html (never created) is fine; a symlink is fine; only
   a real file at that path is a regression.

Falsifiability structure (CLAUDE.md §6): the freshness assertion and the
regular-file guard are both exercised against tmp_path-synthetic scenarios
that are proven RED without the guard logic and GREEN with it -- never by
mutating the operator's real ~/.claude/telemetry. The REAL directory is
covered too, but only as an additional pass/skip case: a machine with no
telemetry dir at all must skip cleanly rather than fail, since telemetry
data is machine-local and may legitimately be absent (mirrors
hooks/tests/test_cycle_telemetry.py's own `pytest.skip(f"... not present in
this $HOME: {path}")` pattern).

This file lives in hooks/tests/ (this repo's one test root) even though the
module under test lives in scripts/ -- both dirs are added to sys.path below,
the same shim hooks/tests/test_render_cycle_log.py already uses for the same
reason (scripts/ is not a package pytest can import by dotted name).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import render_cycle_log as r  # noqa: E402  (import after sys.path shim)

# Tunable grace window: how far cycle_log.html's mtime may lag the newest
# cycle record's mtime before the dashboard is considered stale. 24h matches
# this repo's other "cadence + grace" constants (e.g.
# hooks/heartbeat_audit.py's own GRACE_SECONDS) in spirit -- generous enough
# that a normal round-close render cadence never trips it, tight enough that
# a genuinely abandoned dashboard is caught within a day.
GRACE_SECONDS = 24 * 3600.0

_STALE_REMEDY = "stale — run python3 ~/.claude/scripts/render_cycle_log.py"

# Deliberately a SEPARATE constant from _STALE_REMEDY: re-running the
# renderer cannot fix a regular-file loop_log.html -- render_cycle_log.py
# never touches loop_log.html at all (verified by executing the remedy
# against a regressed regular file: it leaves the regular file in place).
# This is a duplication regression, not staleness, so the message
# deliberately avoids the word "stale."
_DUPLICATE_REGRESSED_REMEDY = (
    "duplicate dashboard regressed — replace with a symlink: "
    "ln -sf cycle_log.html ~/.claude/telemetry/loop_log.html"
)


def _touch(path: Path, mtime_epoch: float, content: str = "x") -> None:
    """Write `path` with real content, then force its mtime to an exact
    epoch value -- write_text() alone stamps "now," which can never produce
    a controlled stale/fresh gap for the RED/GREEN cases below."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime_epoch, mtime_epoch))


def assert_cycle_log_fresh(cycles_dir: Path, rendered_html: Path, grace_seconds: float = GRACE_SECONDS) -> None:
    """The freshness assertion under test, extracted as a standalone
    function so both the RED (pre-fix behavior) and GREEN (post-fix
    behavior) cases can exercise the identical logic a real pytest test
    would run -- this IS the guard `test_cycle_log_freshness_*` below calls;
    it is not a separate reimplementation.

    Raises AssertionError, embedding the literal remedy text, when the
    rendered HTML does not exist at all (nothing was ever rendered despite
    live cycle data) or its mtime lags the newest *.json record under
    cycles_dir by more than grace_seconds. A cycles_dir with no records at
    all is vacuously fresh -- there is nothing to render yet.
    """
    newest_record_mtime: float | None = None
    if cycles_dir.exists():
        # `*/*.json` deliberately mirrors render_cycle_log.py's own record
        # discovery (:424-436, `iterdir()` + `entry.glob("*.json")`) -- one
        # system-dir level deep, non-recursive. Must move in lockstep if the
        # renderer's discovery depth/pattern ever changes.
        for path in cycles_dir.glob("*/*.json"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if newest_record_mtime is None or mtime > newest_record_mtime:
                newest_record_mtime = mtime

    if newest_record_mtime is None:
        return  # no cycle data at all -- nothing to be stale against

    if not rendered_html.exists():
        raise AssertionError(f"{rendered_html} does not exist — {_STALE_REMEDY}")

    rendered_mtime = rendered_html.stat().st_mtime
    lag = newest_record_mtime - rendered_mtime
    if lag > grace_seconds:
        raise AssertionError(
            f"{rendered_html} is {lag:.0f}s older than the newest cycle record "
            f"(grace window {grace_seconds:.0f}s) — {_STALE_REMEDY}"
        )


def assert_loop_log_is_never_a_regular_file(loop_log_path: Path) -> None:
    """The regular-file regression guard. A missing loop_log.html is fine
    (never created). A symlink is fine (P0.1's fixed state, whatever it
    resolves to). Only a REAL regular file at this exact path is the
    regression (the pre-P0.1 hand-copied-duplicate orphan)."""
    if not loop_log_path.exists() and not loop_log_path.is_symlink():
        return  # absent entirely -- fine
    if loop_log_path.is_symlink():
        return  # symlink -- the fixed, sanctioned state
    if loop_log_path.is_file():
        raise AssertionError(
            f"{loop_log_path} is a regular file, not a symlink — {_DUPLICATE_REGRESSED_REMEDY}"
        )


# ---------------------------------------------------------------------------
# Falsifiability: freshness assertion, driven entirely by tmp_path so the RED
# case never touches the operator's real dashboard.
# ---------------------------------------------------------------------------


def test_freshness_assertion_is_red_when_html_is_older_than_the_newest_record(tmp_path: Path) -> None:
    """RED case: cycle_log.html was rendered, then a newer cycle record
    landed well outside the grace window with no re-render -- exactly the
    silent-drift failure this test exists to catch."""
    cycles_dir = tmp_path / "cycles"
    rendered_html = tmp_path / "cycle_log.html"

    now = time.time()
    _touch(rendered_html, now - (48 * 3600))  # rendered 48h ago
    _touch(cycles_dir / "sys" / "c1.json", now - (1 * 3600))  # a record only 1h old

    with pytest.raises(AssertionError) as excinfo:
        assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)
    assert _STALE_REMEDY in str(excinfo.value)


def test_freshness_assertion_is_red_when_rendered_html_is_entirely_missing(tmp_path: Path) -> None:
    """RED case: real cycle data exists but the dashboard was never
    rendered at all."""
    cycles_dir = tmp_path / "cycles"
    rendered_html = tmp_path / "cycle_log.html"  # never created
    _touch(cycles_dir / "sys" / "c1.json", time.time())

    with pytest.raises(AssertionError) as excinfo:
        assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)
    assert _STALE_REMEDY in str(excinfo.value)


def test_freshness_assertion_is_green_when_html_is_newer_than_every_record(tmp_path: Path) -> None:
    """GREEN case: the dashboard was rendered after the newest cycle record
    -- the normal, healthy state."""
    cycles_dir = tmp_path / "cycles"
    rendered_html = tmp_path / "cycle_log.html"

    now = time.time()
    _touch(cycles_dir / "sys" / "c1.json", now - (2 * 3600))
    _touch(rendered_html, now)  # rendered after the record

    assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)  # must not raise


def test_freshness_assertion_is_green_within_the_grace_window(tmp_path: Path) -> None:
    """GREEN case: html is older than the newest record, but the gap is
    inside the tunable grace window -- must not false-positive on a
    perfectly normal render cadence."""
    cycles_dir = tmp_path / "cycles"
    rendered_html = tmp_path / "cycle_log.html"

    now = time.time()
    _touch(rendered_html, now - (2 * 3600))  # rendered 2h ago
    _touch(cycles_dir / "sys" / "c1.json", now - (1 * 3600))  # record 1h ago -- 1h lag

    assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)  # must not raise


def test_freshness_assertion_grace_window_is_tunable(tmp_path: Path) -> None:
    """The grace window is a caller-supplied parameter (backed by the
    module constant GRACE_SECONDS as the default), not hardcoded -- a
    smaller window turns the SAME lag from GREEN to RED."""
    cycles_dir = tmp_path / "cycles"
    rendered_html = tmp_path / "cycle_log.html"

    now = time.time()
    _touch(rendered_html, now - (2 * 3600))
    _touch(cycles_dir / "sys" / "c1.json", now - (1 * 3600))  # 1h lag

    assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=24 * 3600.0)  # 1h lag, 24h grace -- fine

    with pytest.raises(AssertionError):
        assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=30 * 60.0)  # 1h lag, 30min grace -- stale


def test_freshness_assertion_is_vacuously_green_with_no_cycle_records_at_all(tmp_path: Path) -> None:
    """An empty (or nonexistent) cycles_dir has nothing to be stale against
    -- must not fail just because cycle_log.html happens to be old or
    absent when there is no live data driving it."""
    cycles_dir = tmp_path / "cycles"  # never created
    rendered_html = tmp_path / "cycle_log.html"  # never created either

    assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)  # must not raise


# ---------------------------------------------------------------------------
# Falsifiability: loop_log.html regular-file regression guard, driven
# entirely by tmp_path.
# ---------------------------------------------------------------------------


def test_regular_file_guard_is_red_against_a_real_regular_file(tmp_path: Path) -> None:
    """RED case: the exact pre-P0.1 orphan shape -- a real, hand-copied
    regular file sitting at the loop_log.html path instead of a symlink."""
    loop_log_path = tmp_path / "loop_log.html"
    loop_log_path.write_text("<html>a stale hand-copied duplicate</html>", encoding="utf-8")

    with pytest.raises(AssertionError) as excinfo:
        assert_loop_log_is_never_a_regular_file(loop_log_path)
    assert _DUPLICATE_REGRESSED_REMEDY in str(excinfo.value)


def test_regular_file_guard_is_green_for_a_symlink(tmp_path: Path) -> None:
    """GREEN case: a symlink (P0.1's fixed state) must never be flagged,
    regardless of what it resolves to."""
    target = tmp_path / "cycle_log.html"
    target.write_text("<html>real dashboard</html>", encoding="utf-8")
    loop_log_path = tmp_path / "loop_log.html"
    loop_log_path.symlink_to(target)

    assert_loop_log_is_never_a_regular_file(loop_log_path)  # must not raise


def test_regular_file_guard_is_green_when_the_path_is_entirely_absent(tmp_path: Path) -> None:
    """GREEN case: loop_log.html was never created at all -- absence is not
    the regression; only a REAL regular file is."""
    loop_log_path = tmp_path / "loop_log.html"  # never created

    assert_loop_log_is_never_a_regular_file(loop_log_path)  # must not raise


# ---------------------------------------------------------------------------
# The real ~/.claude/telemetry directory -- covered as an additional
# pass/skip case, never as the sole source of RED/GREEN evidence above.
# Machine-local telemetry data may legitimately be absent (mirrors
# hooks/tests/test_cycle_telemetry.py's real-fixture skip pattern).
# ---------------------------------------------------------------------------


def test_real_dashboard_is_fresh_against_the_real_cycles_directory() -> None:
    cycles_dir = r.DEFAULT_CYCLES_DIR
    rendered_html = r.DEFAULT_OUTPUT
    if not cycles_dir.exists():
        pytest.skip(f"real telemetry cycles dir not present in this $HOME: {cycles_dir}")
    if not any(cycles_dir.glob("*/*.json")):
        pytest.skip(f"real telemetry cycles dir has no records in this $HOME: {cycles_dir}")

    assert_cycle_log_fresh(cycles_dir, rendered_html, grace_seconds=GRACE_SECONDS)


def test_real_loop_log_html_is_a_symlink_not_a_regular_file() -> None:
    loop_log_path = r.DEFAULT_OUTPUT.parent / "loop_log.html"
    if not loop_log_path.parent.exists():
        pytest.skip(f"real telemetry dir not present in this $HOME: {loop_log_path.parent}")

    assert_loop_log_is_never_a_regular_file(loop_log_path)
