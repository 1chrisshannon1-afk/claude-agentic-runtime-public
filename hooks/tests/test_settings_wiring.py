"""Structural pin: ~/.claude/settings.json wires PostToolUseFailure to the
same claim-release path as PostToolUse.

This is the actual fix for the "leak on hook failure" bug (see
file_claims.py's and posttooluse_bash.py's own module docstrings for the
full incident and why the fix landed here, in settings.json, rather than as
contest-time logic in file_claims.py). should_release()/main() in
posttooluse_bash.py were always event-agnostic (see
test_posttooluse_bash.py::TestEventAgnosticRelease) -- the only thing
missing was this wiring, so THIS is the test that actually proves the fix is
live, not just that the release logic would work if reached.

Reads the REAL on-disk settings.json of THIS checkout (the file at the
repo root, two levels above hooks/tests/) rather than a synthetic fixture -- a
wiring pin that tests a fixture instead of the actual file it's supposed to
protect would be worthless the moment the two drift apart, which is exactly
the failure mode being guarded against here.

It deliberately does NOT read `~/.claude/settings.json`: when this suite runs
from a clone that is not the live runtime (a contributor's checkout, CI), the
home-directory file is some other machine's settings, so the pin would test
the wrong file. In the deployed layout (checkout == ~/.claude) the two paths
are the same file. The assertions below are this template's contract: a
checkout whose settings.json does not wire PostToolUseFailure to the
claim-release path fails here, by design.
"""

from __future__ import annotations

import json
from pathlib import Path

import _lib  # noqa: F401  (sys.path shim via conftest)

# hooks/tests/test_settings_wiring.py -> parents[2] is the checkout root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings_path() -> str:
    return str(_REPO_ROOT / "settings.json")


def _load_settings() -> dict:
    with open(_settings_path(), encoding="utf-8") as fh:
        return json.load(fh)


def _hooks_for_event(settings: dict, event_name: str) -> list:
    return settings.get("hooks", {}).get(event_name, [])


def _matcher_entries(entries: list, matcher: str) -> list:
    return [e for e in entries if e.get("matcher") == matcher]


class TestPostToolUseFailureWiring:
    def test_settings_json_parses(self):
        # Fails loudly (not silently) if the file is missing/malformed --
        # every assertion below depends on this succeeding.
        settings = _load_settings()
        assert isinstance(settings, dict)

    def test_post_tool_use_failure_key_exists(self):
        settings = _load_settings()
        assert "PostToolUseFailure" in settings.get("hooks", {})

    def test_post_tool_use_failure_has_a_bash_matcher_entry(self):
        settings = _load_settings()
        entries = _hooks_for_event(settings, "PostToolUseFailure")
        bash_entries = _matcher_entries(entries, "Bash")
        assert len(bash_entries) == 1

    def test_post_tool_use_failure_bash_entry_dispatches_post_bash_gate(self):
        """The wired command must actually reach post_bash_gate.sh -- the
        same fast-path wrapper PostToolUse's own Bash entry uses, which
        dispatches to posttooluse_bash.py for anything git-commit-shaped
        (see posttooluse_bash.py's should_release/main, which are
        event-agnostic by construction).
        """
        settings = _load_settings()
        entries = _matcher_entries(_hooks_for_event(settings, "PostToolUseFailure"), "Bash")
        assert len(entries) == 1
        commands = [h.get("command", "") for h in entries[0].get("hooks", [])]
        assert any("post_bash_gate.sh" in cmd for cmd in commands)

    def test_post_tool_use_failure_wiring_matches_post_tool_use_bash_wiring(self):
        """The two events' Bash-matcher commands should be IDENTICAL (modulo
        the disable-hooks guard prefix, which both already share) -- there is
        no reason for PostToolUseFailure to run a different release path than
        PostToolUse; both exist purely to release a claim after a commit
        attempt, success or failure alike (see the module-level docstrings
        for why the release SEMANTICS are already outcome-agnostic and only
        the EVENT REACHABILITY was the bug).
        """
        settings = _load_settings()
        post_entries = _matcher_entries(_hooks_for_event(settings, "PostToolUse"), "Bash")
        failure_entries = _matcher_entries(_hooks_for_event(settings, "PostToolUseFailure"), "Bash")
        assert len(post_entries) == 1 and len(failure_entries) == 1
        post_cmds = [h.get("command") for h in post_entries[0].get("hooks", [])]
        failure_cmds = [h.get("command") for h in failure_entries[0].get("hooks", [])]
        assert post_cmds == failure_cmds

    def test_disable_hooks_guard_present_on_the_failure_entry(self):
        """Every hook command in this runtime self-checks CSA_DISABLE_HOOKS
        before doing any work (see settings.json's own convention) -- the
        new entry must follow the same convention, not bypass the kill
        switch.
        """
        settings = _load_settings()
        entries = _matcher_entries(_hooks_for_event(settings, "PostToolUseFailure"), "Bash")
        commands = [h.get("command", "") for h in entries[0].get("hooks", [])]
        assert any("CSA_DISABLE_HOOKS" in cmd for cmd in commands)
