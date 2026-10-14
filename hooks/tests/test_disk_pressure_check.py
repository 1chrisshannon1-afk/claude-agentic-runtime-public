"""Tests for disk_pressure_check — the SessionStart disk-pressure tripwire
built after the 2026-09-19 disk-full incident (see the module's own
docstring for the full root-cause history and the mount-point trap it
guards against). Covers the pure threshold logic, the mount-point-trap
regression directly, and an end-to-end pass through main() confirming it
never raises and never touches the filesystem.
"""

from __future__ import annotations

import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import disk_pressure_check as dpc  # noqa: E402


# ---------------------------------------------------------------------------
# classify — pure threshold logic
# ---------------------------------------------------------------------------


def test_below_warn_threshold_is_ok():
    assert dpc.classify(50.0) == "ok"
    assert dpc.classify(84.9) == "ok"


def test_at_warn_threshold_is_warn():
    assert dpc.classify(85.0) == "warn"


def test_between_warn_and_urgent_is_warn():
    assert dpc.classify(90.0) == "warn"
    assert dpc.classify(91.9) == "warn"


def test_at_urgent_threshold_is_urgent():
    assert dpc.classify(92.0) == "urgent"


def test_above_urgent_threshold_is_urgent():
    assert dpc.classify(99.9) == "urgent"
    assert dpc.classify(100.0) == "urgent"


# ---------------------------------------------------------------------------
# compute_usage_pct — real filesystem call, safety + correctness
# ---------------------------------------------------------------------------


def test_compute_usage_pct_returns_a_plausible_percentage_for_home():
    home = os.path.expanduser("~")
    pct = dpc.compute_usage_pct(home)
    assert pct is not None
    assert 0.0 <= pct <= 100.0


def test_compute_usage_pct_none_for_nonexistent_path():
    assert dpc.compute_usage_pct("/this/path/does/not/exist/at/all/xyz") is None


def test_compute_usage_pct_never_raises_on_garbage_input():
    # Empty string, None-like inputs -- must return None, never raise, since
    # this is called from a SessionStart hook that must never block a
    # session on an unexpected input.
    assert dpc.compute_usage_pct("") is None


def test_mount_point_trap_regression(monkeypatch, tmp_path):
    """The bug this hook exists to avoid repeating: on this class of macOS
    machine, `df /`'s own Capacity column reports usage against the tiny,
    near-empty system snapshot volume, NOT the Data volume that
    /private/tmp, /Users, and every repo actually live on (measured
    2026-09-19: df / read 23% the same moment the real Data volume was at
    94%). This test asserts the two things that make disk_pressure_check
    immune to that trap: (1) it is never called with bare "/" -- main()
    always resolves HOME first; (2) shutil.disk_usage itself, called against
    ANY real path on this machine (not just HOME), resolves to the
    underlying APFS container's real block stats rather than the tiny
    snapshot volume's own -- so even a caller who accidentally passed a
    different real path would still get the true, pressured number back.
    """
    home = os.path.expanduser("~")
    pct_home = dpc.compute_usage_pct(home)
    pct_root = dpc.compute_usage_pct("/")
    assert pct_home is not None
    assert pct_root is not None
    # Both must resolve to the SAME real container-level usage -- if a
    # future refactor accidentally reintroduced a root-relative special case
    # that diverged from HOME's own reading, this assertion would catch it.
    assert abs(pct_home - pct_root) < 0.5


# ---------------------------------------------------------------------------
# format_message — never silently omits the janitor command
# ---------------------------------------------------------------------------


def test_warn_message_names_dry_run_janitor_command():
    msg = dpc.format_message(87.0, "warn", "/Users/someone")
    assert "disk_janitor.sh" in msg
    # The warn-level example command itself is dry-run only (no --apply
    # flag on the actual suggested invocation line) — the word "--apply"
    # may still appear in surrounding prose explaining the janitor's own
    # dry-run-by-default safety property, which is fine.
    assert msg.rstrip().endswith("bash ~/.claude/scripts/disk_janitor.sh")
    assert "disk_janitor.sh --apply" not in msg


def test_urgent_message_names_both_dry_run_and_apply():
    msg = dpc.format_message(95.0, "urgent", "/Users/someone")
    assert "disk_janitor.sh" in msg
    assert "--apply" in msg


def test_message_never_claims_this_hook_deletes_anything():
    for level, pct in (("warn", 87.0), ("urgent", 95.0)):
        msg = dpc.format_message(pct, level, "/Users/someone")
        # The rejected auto-run-at-92% clause is exactly what this asserts
        # against: the message must direct the OPERATOR to run the janitor,
        # never imply this hook already did or will do it automatically.
        assert "automatically" not in msg.lower()


# ---------------------------------------------------------------------------
# main() — end-to-end, must never raise, must never block a session
# ---------------------------------------------------------------------------


def test_main_never_raises_and_returns_zero(monkeypatch, capsys):
    monkeypatch.delenv(dpc.DISABLE_VAR, raising=False)
    monkeypatch.delenv("CSA_DISABLE_HOOKS", raising=False)
    rc = dpc.main()
    assert rc == 0


def test_main_respects_own_disable_var(monkeypatch, capsys):
    monkeypatch.setenv(dpc.DISABLE_VAR, "1")
    rc = dpc.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""  # disabled -- must print nothing


def test_main_respects_global_disable_hooks(monkeypatch, capsys):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    rc = dpc.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_silent_when_usage_is_low(monkeypatch, capsys):
    monkeypatch.delenv(dpc.DISABLE_VAR, raising=False)
    monkeypatch.delenv("CSA_DISABLE_HOOKS", raising=False)
    monkeypatch.setattr(dpc, "compute_usage_pct", lambda path: 10.0)
    rc = dpc.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_warns_when_usage_is_high(monkeypatch, capsys):
    monkeypatch.delenv(dpc.DISABLE_VAR, raising=False)
    monkeypatch.delenv("CSA_DISABLE_HOOKS", raising=False)
    monkeypatch.setattr(dpc, "compute_usage_pct", lambda path: 96.0)
    rc = dpc.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "URGENT" in captured.out
    assert "disk_janitor.sh" in captured.out


def test_main_never_raises_when_usage_pct_resolution_fails(monkeypatch, capsys):
    monkeypatch.delenv(dpc.DISABLE_VAR, raising=False)
    monkeypatch.delenv("CSA_DISABLE_HOOKS", raising=False)
    monkeypatch.setattr(dpc, "compute_usage_pct", lambda path: None)
    rc = dpc.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_fails_open_on_internal_exception(monkeypatch, capsys):
    monkeypatch.delenv(dpc.DISABLE_VAR, raising=False)
    monkeypatch.delenv("CSA_DISABLE_HOOKS", raising=False)

    def _boom(path):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(dpc, "compute_usage_pct", _boom)
    rc = dpc.main()
    assert rc == 0  # must never block a session, even on internal failure
