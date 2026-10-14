"""Tests for hooks/issue_create_observer.py — the PURE-OBSERVER issue-creation
quality gate (#5827, master plan WS1 Phase D, observer-first).

Falsifiability (runtime CLAUDE.md §6): the "never blocks" and "logs the right
decision" claims are proven by RUNNING the module (unit calls to observe(),
plus a real subprocess invocation of main() with an injected exception) rather
than by reading the code — see TestNeverBlocks below, and the RED-before-GREEN
evidence recorded in the session report (a scratch copy of this module with
the fail-open guards removed IS expected to raise / behave differently; that
revert-and-rerun was performed by hand outside this file, per CLAUDE.md §6's
"do the revert-and-rerun by hand in a scratch copy" — see the report).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import issue_create_observer as ico  # noqa: E402


# ---------------------------------------------------------------------------
# Layer 2 — pure observe() core.
# ---------------------------------------------------------------------------


class TestClassifyLabels:
    def test_all_three_classes_present(self):
        classes = ico.classify_labels(["bug", "area: backend", "difficulty: easy"])
        assert classes == {"type": True, "area": True, "difficulty": True}

    def test_no_labels(self):
        assert ico.classify_labels([]) == {
            "type": False,
            "area": False,
            "difficulty": False,
        }

    def test_case_and_whitespace_insensitive(self):
        classes = ico.classify_labels(["BUG", "Area:Backend", "DIFFICULTY:  Hard"])
        assert classes == {"type": True, "area": True, "difficulty": True}

    def test_unrelated_labels_ignored(self):
        classes = ico.classify_labels(["needs-human-review", "run-e2e"])
        assert classes == {"type": False, "area": False, "difficulty": False}


class TestMissingPieces:
    def test_fully_compliant_is_empty(self):
        missing = ico.missing_pieces(
            "P2", ["bug", "area: backend", "difficulty: easy"]
        )
        assert missing == []

    def test_missing_priority_only(self):
        missing = ico.missing_pieces(
            None, ["bug", "area: backend", "difficulty: easy"]
        )
        assert missing == ["priority"]

    def test_invalid_priority_value_counts_as_missing(self):
        missing = ico.missing_pieces(
            "P9", ["bug", "area: backend", "difficulty: easy"]
        )
        assert missing == ["priority"]

    def test_missing_area_label_only(self):
        missing = ico.missing_pieces("P1", ["bug", "difficulty: hard"])
        assert missing == ["area-label"]

    def test_missing_everything(self):
        missing = ico.missing_pieces(None, [])
        assert missing == ["priority", "type-label", "area-label", "difficulty-label"]


class TestObserveBareIssueCreate:
    def test_bare_gh_issue_create_flagged(self):
        result = ico.observe('gh issue create --title "x" --body "y"')
        assert len(result) == 1
        decision, detail = result[0]
        assert decision == "bare-issue-create"
        assert "gh_issue.sh create" in detail["redirect"]
        assert "--priority" in detail["redirect"]

    def test_bare_gh_issue_create_with_leading_env_assignment(self):
        result = ico.observe('GH_TOKEN=x gh issue create --title "x"')
        assert len(result) == 1
        assert result[0][0] == "bare-issue-create"

    def test_gh_issue_edit_is_not_flagged(self):
        # Only `create` is in scope for this observer -- edit/close/etc. are
        # untouched by Phase D.
        assert ico.observe('gh issue edit 5 --add-label bug') == []

    def test_gh_issue_list_is_not_flagged(self):
        assert ico.observe('gh issue list --state open') == []

    def test_gh_pr_create_is_not_flagged(self):
        # A DIFFERENT gh noun (`pr`, not `issue`) must never match.
        assert ico.observe('gh pr create --title "x"') == []


class TestObserveHelperCreate:
    def test_missing_priority_and_labels_flagged(self):
        result = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --body-file b.md'
        )
        assert len(result) == 1
        decision, detail = result[0]
        assert decision == "create-missing-triage-would-deny"
        assert set(detail["missing"]) == {
            "priority",
            "type-label",
            "area-label",
            "difficulty-label",
        }

    def test_missing_priority_only_flagged(self):
        result = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --body-file b.md '
            '--label bug --label "area: backend" --label "difficulty: easy"'
        )
        assert len(result) == 1
        decision, detail = result[0]
        assert decision == "create-missing-triage-would-deny"
        assert detail["missing"] == ["priority"]

    def test_missing_area_label_only_flagged(self):
        result = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --body-file b.md '
            '--priority P2 --label bug --label "difficulty: easy"'
        )
        assert len(result) == 1
        assert result[0][1]["missing"] == ["area-label"]

    def test_fully_compliant_create_logs_nothing(self):
        result = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --body-file b.md '
            '--priority P2 --label bug --label "area: backend" '
            '--label "difficulty: easy"'
        )
        assert result == []

    def test_bare_basename_gh_issue_sh_also_recognized(self):
        # No path prefix -- basename match, mirroring protected_board_guard's
        # own _is_gh_issue_sh convention.
        result = ico.observe('gh_issue.sh create --title "x"')
        assert len(result) == 1
        assert result[0][0] == "create-missing-triage-would-deny"

    def test_priority_equals_form_classified_exactly_as_absent(self):
        """Fix-round 2, non-blocking finding 4: `~/.claude/scripts/
        gh_issue.sh` itself only accepts `--priority P2` (space form) --
        `--priority=P2` is REFUSED by the real helper (its flag-parsing
        loop dies on an unrecognized `-*` flag). This observer must
        classify `--priority=P2` EXACTLY as if --priority were absent
        entirely, never as a present-and-valid priority -- the two layers
        must agree on what the helper actually does with that token."""
        result_equals = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --priority=P2 '
            '--label bug --label "area: backend" --label "difficulty: easy"'
        )
        result_absent = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" '
            '--label bug --label "area: backend" --label "difficulty: easy"'
        )
        # Compare the DECISION shape (missing/priority fields), not the raw
        # `command` text -- the two calls are necessarily different command
        # strings, but must classify identically.
        assert [d for d, _ in result_equals] == [d for d, _ in result_absent]
        assert [
            {k: v for k, v in detail.items() if k != "command"} for _, detail in result_equals
        ] == [
            {k: v for k, v in detail.items() if k != "command"} for _, detail in result_absent
        ]
        assert len(result_equals) == 1
        assert result_equals[0][0] == "create-missing-triage-would-deny"
        assert result_equals[0][1]["missing"] == ["priority"]

    def test_label_equals_form_also_never_recognized(self):
        """Same fix, the --label side: gh_issue.sh's --label flag is ALSO
        space-form-only, so a --label=bug token must be classified as if
        no labels were given at all, not as a recognized 'bug' label."""
        result = ico.observe(
            '~/.claude/scripts/gh_issue.sh create --title "x" --priority P2 '
            '--label=bug --label="area: backend" --label="difficulty: easy"'
        )
        assert len(result) == 1
        decision, detail = result[0]
        assert decision == "create-missing-triage-would-deny"
        assert set(detail["missing"]) == {
            "type-label",
            "area-label",
            "difficulty-label",
        }

    def test_transition_subcommand_not_flagged(self):
        # A non-`create` gh_issue.sh subcommand must never trip this observer.
        assert (
            ico.observe(
                'gh_issue.sh transition 5 --status Backlog --project 1 --owner O'
            )
            == []
        )

    def test_comment_subcommand_not_flagged(self):
        assert ico.observe('gh_issue.sh comment 5 --body-file b.md') == []

    def test_resolve_subcommand_not_flagged(self):
        assert (
            ico.observe('gh_issue.sh resolve 5 --commit abc123 --body-file b.md')
            == []
        )


class TestObserveCompoundCommands:
    def test_each_writing_segment_inspected_independently(self):
        cmd = (
            'gh issue create --title "a" && '
            '~/.claude/scripts/gh_issue.sh create --title "b" --priority P1 '
            '--label bug --label "area: backend" --label "difficulty: easy"'
        )
        result = ico.observe(cmd)
        decisions = sorted(d for d, _ in result)
        assert decisions == ["bare-issue-create"]

    def test_unrelated_command_yields_nothing(self):
        assert ico.observe('ls -la /tmp') == []
        assert ico.observe('git status') == []


class TestObserveAmbiguousSegment:
    def test_untokenizable_create_shaped_segment_logged_ambiguous_never_blocks(self):
        # Unbalanced quote -- shlex.split raises ValueError.
        result = ico.observe('gh issue create --title "unterminated')
        assert len(result) == 1
        assert result[0][0] == "create-observer-ambiguous"

    def test_untokenizable_unrelated_segment_yields_nothing(self):
        result = ico.observe('echo "unterminated')
        assert result == []

    def test_untokenizable_gh_issue_sh_create_shaped_segment_flagged(self):
        result = ico.observe('gh_issue.sh create --title "unterminated')
        assert len(result) == 1
        assert result[0][0] == "create-observer-ambiguous"


class TestObserveEdgeCases:
    def test_empty_command(self):
        assert ico.observe("") == []

    def test_whitespace_only_command(self):
        assert ico.observe("   \n  ") == []

    def test_none_command_never_raises(self):
        assert ico.observe(None) == []

    def test_non_string_command_never_raises(self):
        assert ico.observe(12345) == []


# ---------------------------------------------------------------------------
# Layer 2 — "never blocks" is the core falsifiable claim of this module.
# Proven three ways: (a) observe() has no block-shaped return value at all
# (structural — there is no _Block class in this module, unlike every
# blocking gate); (b) main() never calls _lib.emit_pretooluse_deny even when
# observe() itself raises; (c) a real subprocess invocation of main() always
# exits 0 and never prints a deny-shaped JSON object.
# ---------------------------------------------------------------------------


class TestNeverBlocks:
    def test_module_defines_no_block_class_or_emit_deny_call(self):
        # Structural guarantee check_safety_core_parity.py itself relies on:
        # this module's source must never call `_lib.emit_pretooluse_deny(`
        # -- the EXACT signal check_safety_core_parity.looks_like_pretooluse_
        # guard scans for (_GUARD_SIGNAL_RE) -- or the guard-wiring self-check
        # will demand it be reachable/wired as a real guard rather than an
        # observer. A prose MENTION of the function name (this module's own
        # docstring explains why it never calls it) is fine; only the actual
        # call shape `_lib.emit_pretooluse_deny(` is forbidden.
        sys.path.insert(0, str(HOOKS_DIR))
        import check_safety_core_parity as cscp

        src = Path(ico.__file__).read_text()
        assert not cscp.looks_like_pretooluse_guard("issue_create_observer.py", src)

    def test_observe_raising_still_lets_main_exit_0(self, monkeypatch):
        """The plan's own mandated test: an observer that raises internally
        must never affect the command's outcome."""

        def _boom(_command):
            raise RuntimeError("observer exploded")

        monkeypatch.setattr(ico, "observe", _boom)
        # main() calls observe() inside its own try/except -- but observe()
        # is looked up as ico.observe inside main's body via direct call,
        # so patching the module attribute takes effect for the same-process
        # call below.
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh issue create --title "x"'},
                "cwd": "/tmp",
            }
        )
        monkeypatch.setattr(sys, "stdin", _FakeStdin(payload))
        rc = ico.main()
        assert rc == 0

    def test_main_subprocess_never_blocks_and_exits_0(self, tmp_path):
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh issue create --title "x" --body "y"'},
                "cwd": str(tmp_path),
            }
        )
        env = dict(os.environ)
        env["CSA_CLAUDE_HOME"] = str(Path.home() / ".claude")
        proc = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "issue_create_observer.py")],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0
        # Never emits the canonical PreToolUse deny JSON shape.
        assert "permissionDecision" not in proc.stdout
        assert "deny" not in proc.stdout.lower()

    def test_main_subprocess_non_bash_tool_is_noop(self, tmp_path):
        payload = json.dumps({"tool_name": "Read", "tool_input": {}})
        proc = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "issue_create_observer.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0
        assert proc.stdout == ""

    def test_main_subprocess_master_off_switch_is_noop(self, tmp_path):
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {"command": 'gh issue create --title "x"'},
                "cwd": str(tmp_path),
            }
        )
        env = dict(os.environ)
        env["CSA_DISABLE_HOOKS"] = "1"
        proc = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "issue_create_observer.py")],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0
        assert proc.stdout == ""

    def test_main_subprocess_malformed_json_stdin_never_crashes(self):
        proc = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "issue_create_observer.py")],
            input="not json at all {{{",
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0


class _FakeStdin:
    def __init__(self, data: str):
        self._data = data

    def read(self) -> str:
        return self._data


# ---------------------------------------------------------------------------
# Layer 2 — logging behavior via main(), using a real log file (never the
# real ~/.claude/.enforcement/ ledger -- monkeypatched to a tmp path).
# ---------------------------------------------------------------------------


class TestMainLogging:
    def _run_main_capturing_log(self, monkeypatch, tmp_path, command, cwd=None):
        log_file = tmp_path / "log.jsonl"
        import _lib

        monkeypatch.setattr(_lib, "LOG_FILE", str(log_file))
        monkeypatch.setattr(_lib, "ENFORCEMENT_DIR", str(tmp_path))
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": cwd or str(tmp_path),
        }
        monkeypatch.setattr(sys, "stdin", _FakeStdin(json.dumps(payload)))
        rc = ico.main()
        lines = []
        if log_file.exists():
            lines = [json.loads(ln) for ln in log_file.read_text().splitlines() if ln.strip()]
        return rc, lines

    def test_bare_create_logs_one_line(self, monkeypatch, tmp_path):
        rc, lines = self._run_main_capturing_log(
            monkeypatch, tmp_path, 'gh issue create --title "x"'
        )
        assert rc == 0
        assert len(lines) == 1
        assert lines[0]["hook"] == "issue_create_observer"
        assert lines[0]["decision"] == "bare-issue-create"

    def test_compliant_helper_create_logs_nothing(self, monkeypatch, tmp_path):
        rc, lines = self._run_main_capturing_log(
            monkeypatch,
            tmp_path,
            '~/.claude/scripts/gh_issue.sh create --title "x" --priority P2 '
            '--label bug --label "area: backend" --label "difficulty: easy"',
        )
        assert rc == 0
        assert lines == []

    def test_missing_triage_helper_create_logs_one_line(self, monkeypatch, tmp_path):
        rc, lines = self._run_main_capturing_log(
            monkeypatch, tmp_path, '~/.claude/scripts/gh_issue.sh create --title "x"'
        )
        assert rc == 0
        assert len(lines) == 1
        assert lines[0]["decision"] == "create-missing-triage-would-deny"
        assert set(lines[0]["missing"]) == {
            "priority",
            "type-label",
            "area-label",
            "difficulty-label",
        }
