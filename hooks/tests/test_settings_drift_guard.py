"""Tests for settings_drift_guard — the SessionStart self-healer for
settings.json's model/effortLevel drift (regressed 4x: 07-09, 07-19, 08-03,
08-20). Covers the pure decision logic directly, the atomic-write and
verify-before-trust safety mechanisms round-2 review required, then an
end-to-end pass against a real throwaway git repo + settings.json on disk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import settings_drift_guard as sdg

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# compute_drift — pure logic
# ---------------------------------------------------------------------------


def test_no_drift_when_identical():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "sonnet", "effortLevel": "high"}
    assert sdg.compute_drift(committed, live) == {}


def test_model_drift_detected():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "opus[1m]", "effortLevel": "high"}
    drift = sdg.compute_drift(committed, live)
    assert drift == {"model": ("opus[1m]", "sonnet")}


def test_effort_drift_detected():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "sonnet", "effortLevel": "max"}
    drift = sdg.compute_drift(committed, live)
    assert drift == {"effortLevel": ("max", "high")}


def test_both_fields_drifted():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "opus[1m]", "effortLevel": "xhigh"}
    drift = sdg.compute_drift(committed, live)
    assert set(drift) == {"model", "effortLevel"}


def test_absent_live_field_counts_as_drift():
    """07-09's actual failure mode: the key went MISSING, not just wrong."""
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "sonnet"}  # effortLevel absent entirely
    drift = sdg.compute_drift(committed, live)
    assert drift == {"effortLevel": (sdg._ABSENT, "high")}


def test_field_absent_from_committed_is_never_restored():
    """No baseline to restore TO — must not invent one."""
    committed = {"model": "sonnet"}  # no effortLevel key at all in HEAD
    live = {"model": "sonnet", "effortLevel": "xhigh"}
    drift = sdg.compute_drift(committed, live)
    assert drift == {}


def test_unrelated_fields_never_flagged():
    committed = {"model": "sonnet", "effortLevel": "high", "theme": "dark"}
    live = {"model": "sonnet", "effortLevel": "high", "theme": "light"}
    assert sdg.compute_drift(committed, live) == {}


def test_none_inputs_do_not_raise():
    assert sdg.compute_drift(None, None) == {}
    assert sdg.compute_drift({"model": "sonnet"}, None) == {"model": (sdg._ABSENT, "sonnet")}
    assert sdg.compute_drift(None, {"model": "opus"}) == {}


# ---------------------------------------------------------------------------
# report_other_drift — round-2 finding 27
# ---------------------------------------------------------------------------


def test_report_other_drift_flags_unrelated_key_changes():
    committed = {"model": "sonnet", "theme": "dark", "tui": "fullscreen"}
    live = {"model": "sonnet", "theme": "light", "tui": "fullscreen"}
    assert sdg.report_other_drift(committed, live) == ["theme"]


def test_report_other_drift_never_includes_guarded_fields():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "opus", "effortLevel": "max"}
    # model/effortLevel drift too, but this function only reports OTHERS.
    assert sdg.report_other_drift(committed, live) == []


def test_report_other_drift_does_not_restore_anything():
    """This function must never be confused for apply_fix -- it is
    read-only by construction (returns a list, touches nothing)."""
    committed = {"model": "sonnet", "extra": 1}
    live = {"model": "sonnet", "extra": 2}
    result = sdg.report_other_drift(committed, live)
    assert result == ["extra"]
    assert live == {"model": "sonnet", "extra": 2}  # untouched


# ---------------------------------------------------------------------------
# _replace_field_value / apply_fix — surgical text replacement + verification
# ---------------------------------------------------------------------------


def test_replace_field_value_preserves_surrounding_text():
    text = '{\n  "foo": 1,\n  "model": "opus[1m]",\n  "bar": 2\n}\n'
    out = sdg._replace_field_value(text, "model", json.dumps("sonnet"))
    assert out == '{\n  "foo": 1,\n  "model": "sonnet",\n  "bar": 2\n}\n'


def test_replace_field_value_returns_none_when_field_absent():
    text = '{\n  "foo": 1\n}\n'
    assert sdg._replace_field_value(text, "model", '"sonnet"') is None


def test_apply_fix_surgical_path_preserves_formatting(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    live_text = '{\n  "a": 1,\n  "model": "opus[1m]",\n  "effortLevel": "max",\n  "z": true\n}\n'
    live_dict = json.loads(live_text)
    drift = {"model": ("opus[1m]", "sonnet"), "effortLevel": ("max", "high")}
    ok = sdg.apply_fix(settings_path, live_text, live_dict, drift)
    assert ok is True
    with open(settings_path, encoding="utf-8") as fh:
        result = fh.read()
    assert result == '{\n  "a": 1,\n  "model": "sonnet",\n  "effortLevel": "high",\n  "z": true\n}\n'
    assert json.loads(result) == {"a": 1, "model": "sonnet", "effortLevel": "high", "z": True}


def test_apply_fix_falls_back_to_full_rewrite_when_field_absent(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    live_text = '{\n  "model": "sonnet"\n}\n'  # effortLevel entirely missing
    live_dict = json.loads(live_text)
    drift = {"effortLevel": (sdg._ABSENT, "high")}
    ok = sdg.apply_fix(settings_path, live_text, live_dict, drift)
    assert ok is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    assert result == {"model": "sonnet", "effortLevel": "high"}


def test_apply_fix_falls_back_when_a_nested_duplicate_key_would_confuse_the_regex(tmp_path):
    """Round-2 finding 11: the regex is not JSON-nesting-aware, so a NESTED
    "model" key appearing before the top-level one could be surgically
    (and silently) rewritten instead of the real target. The verify-then-
    fallback step must catch this and produce a CORRECT result regardless."""
    settings_path = str(tmp_path / "settings.json")
    # A nested "model" (inside some other object) appears BEFORE the real
    # top-level "model" key in the raw text.
    live_text = (
        '{\n'
        '  "orgDefaults": {"model": "opus[1m]"},\n'
        '  "model": "opus[1m]",\n'
        '  "effortLevel": "high"\n'
        '}\n'
    )
    live_dict = json.loads(live_text)
    drift = {"model": ("opus[1m]", "sonnet")}
    ok = sdg.apply_fix(settings_path, live_text, live_dict, drift)
    assert ok is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    # The TOP-LEVEL model must be fixed; the nested one is a different field
    # entirely and must be left exactly as it was found.
    assert result["model"] == "sonnet"
    assert result["orgDefaults"]["model"] == "opus[1m]"


def test_apply_fix_write_failure_returns_false(tmp_path):
    # A directory in place of the target path makes the write fail.
    bad_path = str(tmp_path / "not_writable_dir")
    os.makedirs(bad_path)
    ok = sdg.apply_fix(bad_path, "{}", {}, {"model": ("x", "y")})
    assert ok is False


# ---------------------------------------------------------------------------
# _atomic_write — round-2 finding 10
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_no_temp_file_on_success(tmp_path):
    path = str(tmp_path / "settings.json")
    assert sdg._atomic_write(path, '{"a": 1}\n') is True
    entries = os.listdir(tmp_path)
    assert entries == ["settings.json"]  # no leftover .tmp.<pid> file


def test_atomic_write_never_leaves_a_truncated_file():
    """A failure partway through must never leave the TARGET path
    truncated -- the write always happens to a temp file first, and
    os.replace is what actually lands it. Simulated by pointing at a path
    whose directory does not exist (write fails before any replace)."""
    path = "/nonexistent_dir_xyz/settings.json"
    ok = sdg._atomic_write(path, '{"a": 1}\n')
    assert ok is False
    assert not os.path.exists(path)


def test_atomic_write_leaves_old_content_intact_when_replace_fails(tmp_path, monkeypatch):
    """THE actual falsifying test for atomicity (round-2 review, blocker B):
    the three tests above all pass even with atomicity REMOVED entirely
    (`tmp = path` instead of a real temp file) -- none of them exercise the
    one case atomicity actually exists for: os.replace itself failing AFTER
    the temp file was already written, with a REAL pre-existing file at the
    target path. Without a temp file, that shape is a direct truncating
    write -- old content gone -- and if os.replace then also fails, the
    "cleanup" line (`os.remove(tmp)`, where a de-atomicized `tmp == path`)
    deletes the target file outright. This test forces os.replace to fail
    and asserts the ORIGINAL content survives untouched — the actual
    guarantee atomic_write exists to provide, not just "no crash."
    """
    path = str(tmp_path / "settings.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"old": true}\n')

    monkeypatch.setattr(
        sdg.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("simulated replace failure"))
    )

    ok = sdg._atomic_write(path, '{"new": true}\n')
    assert ok is False
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == '{"old": true}\n'  # untouched, not truncated, not deleted


def test_atomic_write_cleans_up_temp_file_on_failure(tmp_path):
    # Directory in place of the real target makes os.replace fail; the temp
    # file it tried to create alongside must not be left behind.
    bad_path = str(tmp_path / "target_is_a_dir")
    os.makedirs(bad_path)
    sdg._atomic_write(bad_path, "content")
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith("target_is_a_dir.tmp.")]
    assert leftovers == []


# ---------------------------------------------------------------------------
# format_message
# ---------------------------------------------------------------------------


def test_format_message_names_every_drifted_field():
    msg = sdg.format_message({"model": ("opus[1m]", "sonnet"), "effortLevel": ("max", "high")})
    assert "model" in msg
    assert "opus[1m]" in msg
    assert "sonnet" in msg
    assert "effortLevel" in msg
    assert "restored 2 field(s)" in msg


# ---------------------------------------------------------------------------
# modelSettings, a guarded-ABSENT field (2026-09-23). The client writes a
# per-model `modelSettings: {"<model>": {"effortLevel": "xhigh"}}` block on its
# own, alongside each model bump (7 recurrences measured in one day). Restoring
# `model` alone leaves that block behind, so it is healed by REMOVAL when HEAD
# has no such key, or restored to HEAD's object when it does.
# ---------------------------------------------------------------------------

_CLIENT_BLOCK = {"claude-sonnet-5": {"effortLevel": "xhigh"}}


def test_model_settings_written_by_client_is_drift_when_head_has_none():
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "sonnet", "effortLevel": "high", "modelSettings": _CLIENT_BLOCK}
    assert sdg.compute_drift(committed, live) == {"modelSettings": (_CLIENT_BLOCK, sdg._ABSENT)}


def test_model_settings_absent_on_both_sides_is_not_drift():
    committed = {"model": "sonnet", "effortLevel": "high"}
    assert sdg.compute_drift(committed, dict(committed)) == {}


def test_model_settings_committed_object_is_restored_not_removed():
    head_block = {"claude-sonnet-5": {"effortLevel": "high"}}
    committed = {"model": "sonnet", "effortLevel": "high", "modelSettings": head_block}
    live = {"model": "sonnet", "effortLevel": "high", "modelSettings": _CLIENT_BLOCK}
    assert sdg.compute_drift(committed, live) == {"modelSettings": (_CLIENT_BLOCK, head_block)}
    # And identical objects are not drift.
    assert sdg.compute_drift(committed, {**live, "modelSettings": dict(head_block)}) == {}


def test_apply_fix_removes_a_guarded_absent_field(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    live_dict = {"model": "sonnet", "effortLevel": "high", "modelSettings": _CLIENT_BLOCK, "z": True}
    live_text = json.dumps(live_dict, indent=2) + "\n"
    drift = {"modelSettings": (_CLIENT_BLOCK, sdg._ABSENT)}
    assert sdg.apply_fix(settings_path, live_text, live_dict, drift) is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    assert "modelSettings" not in result
    assert result == {"model": "sonnet", "effortLevel": "high", "z": True}


def test_apply_fix_restores_a_committed_model_settings_object(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    head_block = {"claude-sonnet-5": {"effortLevel": "high"}}
    live_dict = {"model": "sonnet", "modelSettings": _CLIENT_BLOCK}
    live_text = json.dumps(live_dict, indent=2) + "\n"
    drift = {"modelSettings": (_CLIENT_BLOCK, head_block)}
    assert sdg.apply_fix(settings_path, live_text, live_dict, drift) is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    assert result == {"model": "sonnet", "modelSettings": head_block}


def test_apply_fix_heals_model_and_model_settings_together(tmp_path):
    """The real shape: the client bumps `model` AND writes the block in one go."""
    settings_path = str(tmp_path / "settings.json")
    live_dict = {"model": "opus[1m]", "effortLevel": "high", "modelSettings": _CLIENT_BLOCK}
    live_text = json.dumps(live_dict, indent=2) + "\n"
    drift = {"model": ("opus[1m]", "sonnet"), "modelSettings": (_CLIENT_BLOCK, sdg._ABSENT)}
    assert sdg.apply_fix(settings_path, live_text, live_dict, drift) is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    assert result == {"model": "sonnet", "effortLevel": "high"}


def test_format_message_says_removed_for_a_guarded_absent_field():
    msg = sdg.format_message({"modelSettings": (_CLIENT_BLOCK, sdg._ABSENT)})
    assert "modelSettings" in msg
    assert "removed" in msg
    assert "'<absent>'" not in msg


def test_report_other_drift_never_includes_a_guarded_absent_field():
    """modelSettings is RESTORED, so it must not also be REPORTED: a key in both
    ledgers ('other-keys-drifted' and 'restored' on one run) corrupts the signal
    that decides whether the guarded set should grow (review blocker 1)."""
    committed = {"model": "sonnet", "effortLevel": "high"}
    live = {"model": "sonnet", "effortLevel": "high", "modelSettings": _CLIENT_BLOCK, "zzz": 1}
    assert sdg.report_other_drift(committed, live) == ["zzz"]


def test_a_committed_literal_absent_string_is_restored_not_deleted(tmp_path):
    """The absence marker is an object, never the string "<absent>", so a
    committed value that happens to BE that string round-trips as a value
    (review regression 2: a string sentinel deleted `model` in this case)."""
    committed = {"model": "<absent>", "effortLevel": "high"}
    live = {"model": "opus", "effortLevel": "high"}
    drift = sdg.compute_drift(committed, live)
    assert drift == {"model": ("opus", "<absent>")}
    settings_path = str(tmp_path / "settings.json")
    live_text = json.dumps(live, indent=2) + "\n"
    assert sdg.apply_fix(settings_path, live_text, live, drift) is True
    with open(settings_path, encoding="utf-8") as fh:
        result = json.loads(fh.read())
    assert result == {"model": "<absent>", "effortLevel": "high"}
    # And the symmetric case: a client writing the literal string into a
    # guarded-absent key is drift, not a disguised absence.
    assert sdg.compute_drift({"model": "sonnet"}, {"model": "sonnet", "modelSettings": "<absent>"}) == {
        "modelSettings": ("<absent>", sdg._ABSENT)
    }


def test_end_to_end_removes_client_written_model_settings(fake_home):
    settings_path = fake_home / ".claude" / "settings.json"
    drifted = json.loads(settings_path.read_text())
    drifted["model"] = "opus[1m]"
    drifted["modelSettings"] = _CLIENT_BLOCK
    settings_path.write_text(json.dumps(drifted, indent=2) + "\n")

    proc = _run_main(fake_home)
    assert proc.returncode == 0
    assert "restored 2 field(s)" in proc.stdout
    assert "modelSettings" in proc.stdout

    healed = json.loads(settings_path.read_text())
    assert healed["model"] == "sonnet"
    assert "modelSettings" not in healed
    assert healed["other"] == "untouched"


# ---------------------------------------------------------------------------
# end-to-end: real throwaway repo + real settings.json on disk
# ---------------------------------------------------------------------------


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=True,
    )


@pytest.fixture
def fake_home(tmp_path):
    """A throwaway $HOME containing a git-committed ~/.claude/settings.json,
    mirroring the real layout main() walks: $HOME/.claude/settings.json,
    committed at HEAD with model=sonnet/effortLevel=high."""
    home = tmp_path / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True)
    _git(claude, "init", "-q", "-b", "main")
    _git(claude, "config", "user.email", "t@example.com")
    _git(claude, "config", "user.name", "t")
    settings = {"model": "sonnet", "effortLevel": "high", "other": "untouched"}
    (claude / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    _git(claude, "add", "settings.json")
    _git(claude, "commit", "-q", "-m", "base")
    return home


def _run_main(home, extra_env=None):
    env = {**os.environ, "HOME": str(home)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "settings_drift_guard.py")],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _log_lines(home):
    log_path = home / ".claude" / ".enforcement" / "log.jsonl"
    if not log_path.exists():
        return []
    return [json.loads(ln) for ln in log_path.read_text().splitlines() if ln.strip()]


def test_end_to_end_no_drift_logs_no_drift(fake_home):
    proc = _run_main(fake_home)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    decisions = [e["decision"] for e in _log_lines(fake_home) if e.get("hook") == sdg.HOOK]
    assert "no-drift" in decisions


def test_end_to_end_restores_live_drift(fake_home):
    settings_path = fake_home / ".claude" / "settings.json"
    drifted = json.loads(settings_path.read_text())
    drifted["model"] = "opus[1m]"
    drifted["effortLevel"] = "max"
    settings_path.write_text(json.dumps(drifted, indent=2) + "\n")

    proc = _run_main(fake_home)
    assert proc.returncode == 0
    assert "restored 2 field(s)" in proc.stdout

    restored = json.loads(settings_path.read_text())
    assert restored["model"] == "sonnet"
    assert restored["effortLevel"] == "high"
    assert restored["other"] == "untouched"  # unrelated field survives

    decisions = [e for e in _log_lines(fake_home) if e.get("hook") == sdg.HOOK]
    assert any(e["decision"] == "restored" for e in decisions)


def test_end_to_end_master_switch_disables_it(fake_home):
    settings_path = fake_home / ".claude" / "settings.json"
    drifted = json.loads(settings_path.read_text())
    drifted["model"] = "opus[1m]"
    settings_path.write_text(json.dumps(drifted, indent=2) + "\n")

    proc = _run_main(fake_home, extra_env={"CSA_DISABLE_HOOKS": "1"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    still_drifted = json.loads(settings_path.read_text())
    assert still_drifted["model"] == "opus[1m]"


def test_end_to_end_scoped_lever_disables_only_this_module(fake_home):
    """Round-2 finding 26: a per-module lever, not just the global one."""
    settings_path = fake_home / ".claude" / "settings.json"
    drifted = json.loads(settings_path.read_text())
    drifted["model"] = "opus[1m]"
    settings_path.write_text(json.dumps(drifted, indent=2) + "\n")

    proc = _run_main(fake_home, extra_env={"CSA_NO_SETTINGS_DRIFT_GUARD": "1"})
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    still_drifted = json.loads(settings_path.read_text())
    assert still_drifted["model"] == "opus[1m]"


def test_end_to_end_reports_other_drifted_keys_without_touching_them(fake_home):
    settings_path = fake_home / ".claude" / "settings.json"
    drifted = json.loads(settings_path.read_text())
    drifted["other"] = "changed"  # not a guarded field
    settings_path.write_text(json.dumps(drifted, indent=2) + "\n")

    proc = _run_main(fake_home)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # not restored, no loud message

    unchanged = json.loads(settings_path.read_text())
    assert unchanged["other"] == "changed"  # left alone

    decisions = [e for e in _log_lines(fake_home) if e.get("hook") == sdg.HOOK]
    assert any(e["decision"] == "other-keys-drifted" and "other" in e.get("keys", []) for e in decisions)


def test_end_to_end_no_git_repo_is_a_safe_noop(tmp_path):
    home = tmp_path / "home_no_git"
    claude = home / ".claude"
    claude.mkdir(parents=True)
    (claude / "settings.json").write_text('{"model": "opus[1m]"}')
    proc = _run_main(home)
    assert proc.returncode == 0
    # No HEAD to compare against -- must not touch the file.
    assert json.loads((claude / "settings.json").read_text())["model"] == "opus[1m]"


def test_end_to_end_malformed_live_json_is_a_safe_noop(fake_home):
    settings_path = fake_home / ".claude" / "settings.json"
    settings_path.write_text("{not valid json")
    proc = _run_main(fake_home)
    assert proc.returncode == 0
    assert settings_path.read_text() == "{not valid json"  # untouched, not "fixed" by guessing


def test_never_raises_on_missing_settings_file(tmp_path):
    home = tmp_path / "home_no_settings"
    claude = home / ".claude"
    claude.mkdir(parents=True)
    _git(claude, "init", "-q", "-b", "main")
    _git(claude, "config", "user.email", "t@example.com")
    _git(claude, "config", "user.name", "t")
    (claude / "placeholder.txt").write_text("x")
    _git(claude, "add", "placeholder.txt")
    _git(claude, "commit", "-q", "-m", "base, no settings.json at all")
    proc = _run_main(home)
    assert proc.returncode == 0
