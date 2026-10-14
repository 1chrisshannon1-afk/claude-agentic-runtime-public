"""Hermetic tests for hooks/protected_board_guard.py (GH #5490).

Operator directive (verbatim, 2026-09-14): "make sure that only tickets from
the saas ticketing center go here. when a user files a ticket it goes here.
none of our agents should create issues here." — GitHub org project #5
("Example Support Tickets", node id `PVT_kwDOEXAMPLE00000`) is a CUSTOMER-ONLY
inbox; only the product's own support-ticket mirror may add items to it, no
agent ever. This suite covers the pure `decide()` function's full shape
matrix (a), (b), (c), (d) — every deny paired with a nearby allow — the
untokenizable-segment fail-closed path, the registry fail-open path, the
log-only-vs-enforce split, and an end-to-end proof that `bash_gate.sh`'s
fast-path actually reaches the python dispatcher for this gate.

FALSIFIABILITY (runtime CLAUDE.md §6): every deny-shaped test in this file
was proven RED against a neutered `decide()` (hardcoded to always return
`(False, "neutered-for-falsifiability-check")`) and GREEN against the real
module — see the task's own report for the exact counts. This file does not
re-run that neutering itself (that would require monkeypatching the module's
own top-level function identity mid-suite, which is a different and noisier
test shape than every sibling gate uses); the by-hand revert-and-rerun is the
same falsifiability discipline `test_block_gcloud_identity.py` documents.

Everything runs against the `sandbox` fixture ($HOME + _lib path constants
pointed into a tmp dir) so the operator's real ~/.claude registry/enforcement
state is never touched. No network, no real `gh` subprocess is ever invoked —
this module makes no subprocess calls of its own, only string/regex analysis
plus a static registry-file read.
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import _lib  # noqa: F401  (imported for parity / sys.path shim via conftest)
import protected_board_guard as guard
import pytest

# ===========================================================================
# Fixtures / helpers.
# ===========================================================================

_TEST_BOARD = {
    "owner": "example-org",
    "number": 5,
    "node_id": "PVT_kwDOEXAMPLE00000",
    "title": "Example Support Tickets",
    "reason": "Customer support inbox — only the SaaS support-ticket mirror may add items.",
    "tracker": "example-org/ExampleApp#5490",
}

_BOARDS = [_TEST_BOARD]


def _ev(command, tool_name="Bash", **extra):
    ev = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    ev.update(extra)
    return ev


def _run_main(monkeypatch, payload, capsys):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = guard.main()
    out = capsys.readouterr().out
    return rc, out


def _write_registry(path, boards):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"boards": boards}))


# ===========================================================================
# Registry loading.
# ===========================================================================


class TestLoadRegistry:
    def test_loads_real_registry_file(self, tmp_path):
        p = tmp_path / "protected_boards.json"
        _write_registry(p, _BOARDS)
        boards = guard.load_registry(str(p))
        assert len(boards) == 1
        assert boards[0]["number"] == 5
        assert boards[0]["node_id"] == "PVT_kwDOEXAMPLE00000"

    def test_missing_file_returns_empty(self, tmp_path):
        assert guard.load_registry(str(tmp_path / "nope.json")) == []

    def test_unparseable_json_returns_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        assert guard.load_registry(str(p)) == []

    def test_wrong_shape_boards_not_a_list_returns_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"boards": "nope"}))
        assert guard.load_registry(str(p)) == []

    def test_entries_missing_number_or_owner_are_dropped(self, tmp_path):
        p = tmp_path / "partial.json"
        _write_registry(
            p,
            [
                {"owner": "X"},  # no number
                {"number": 9},  # no owner
                dict(_TEST_BOARD),
            ],
        )
        boards = guard.load_registry(str(p))
        assert len(boards) == 1
        assert boards[0]["number"] == 5

    def test_registry_path_uses_lib_claude_dir(self, sandbox, tmp_path):
        # registry_path() must be sandbox-friendly (derived from _lib.CLAUDE_DIR
        # at call time, not a module-level constant computed at import time).
        p = guard.registry_path()
        assert str(sandbox.claude) in p
        assert p.endswith(os.path.join("knowledge", "protected_boards.json"))


# ===========================================================================
# _norm(): nit 6 -- None must normalize to "", never the string "none".
# ===========================================================================


class TestNorm:
    def test_norm_none_is_empty_string(self):
        assert guard._norm(None) == ""

    def test_norm_none_never_matches_a_board_titled_none(self):
        boards = [dict(_TEST_BOARD, title="None", number=99, owner="X")]
        assert guard.find_board_by_title_or_number(boards, None) is None


# ===========================================================================
# Shape (a): `gh project item-add|item-create <number> --owner <owner> ...`
# Every deny paired with a nearby allow.
# ===========================================================================


class TestShapeAItemAdd:
    def test_item_add_matching_number_and_owner_denied(self):
        block, reason = guard.decide(
            "gh project item-add 5 --owner example-org --url https://x", _BOARDS
        )
        assert block is True
        assert reason.startswith("protected-board-item-add")

    def test_item_create_matching_number_and_owner_denied(self):
        block, reason = guard.decide(
            "gh project item-create 5 --owner example-org --title 'x' --body 'y'",
            _BOARDS,
        )
        assert block is True
        assert reason.startswith("protected-board-item-add")

    def test_item_add_absent_owner_still_denied(self):
        # An absent --owner must not be read as "not the protected board" —
        # gh defaults to the authenticated org, which for this runtime's
        # product repos IS the protected board's owner.
        block, reason = guard.decide("gh project item-add 5 --url https://x", _BOARDS)
        assert block is True

    def test_item_add_different_number_allowed(self):
        block, reason = guard.decide(
            "gh project item-add 1 --owner example-org --url https://x", _BOARDS
        )
        assert block is False

    def test_item_add_same_number_different_explicit_owner_allowed(self):
        block, reason = guard.decide(
            "gh project item-add 5 --owner SomeoneElse --url https://x", _BOARDS
        )
        assert block is False

    def test_item_add_owner_flag_equals_form_denied(self):
        block, reason = guard.decide(
            "gh project item-add 5 --owner=example-org --url https://x", _BOARDS
        )
        assert block is True

    def test_item_add_owner_case_insensitive_denied(self):
        block, reason = guard.decide(
            "gh project item-add 5 --owner example-org --url https://x", _BOARDS
        )
        assert block is True


class TestShapeAReadsAndEditsAllowed:
    def test_project_view_allowed(self):
        block, reason = guard.decide(
            "gh project view 5 --owner example-org", _BOARDS
        )
        assert block is False

    def test_project_item_list_allowed(self):
        block, reason = guard.decide(
            "gh project item-list 5 --owner example-org", _BOARDS
        )
        assert block is False

    def test_project_field_list_allowed(self):
        block, reason = guard.decide(
            "gh project field-list 5 --owner example-org", _BOARDS
        )
        assert block is False

    def test_project_item_edit_allowed(self):
        # Triaging an EXISTING customer ticket (moving status, setting a
        # field) is legitimate steward work — only item CREATION is denied.
        block, reason = guard.decide(
            "gh project item-edit --project-id PVT_kwDOEXAMPLE00000 "
            "--id ITEM_ID --field-id FIELD_ID --text 'triaged'",
            _BOARDS,
        )
        assert block is False

    def test_project_item_delete_allowed(self):
        block, reason = guard.decide(
            "gh project item-delete 5 --owner example-org --id ITEM_ID", _BOARDS
        )
        assert block is False


# ===========================================================================
# Shape (b): `gh api graphql` add-item/draft-issue mutation + protected node_id.
# ===========================================================================


class TestShapeBGraphqlAdd:
    def test_add_item_mutation_with_node_id_denied(self):
        cmd = (
            "gh api graphql -f query='mutation { addProjectV2ItemById("
            "projectId: \"PVT_kwDOEXAMPLE00000\", contentId: \"ISSUE_ID\") "
            "{ item { id } } }'"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True
        assert reason.startswith("protected-board-graphql-add")

    def test_add_draft_issue_mutation_with_node_id_denied(self):
        cmd = (
            "gh api graphql -f query='mutation { addProjectV2DraftIssue("
            "projectId: \"PVT_kwDOEXAMPLE00000\", title: \"x\") { projectItem { id } } }'"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True

    def test_node_id_as_dash_f_variable_value_still_denied(self):
        # The node id appearing only as an -F/-f variable VALUE, not inline
        # in the query text, must still match (raw text scan, not a parse).
        cmd = (
            "gh api graphql -f query='mutation($p:ID!,$c:ID!){ "
            "addProjectV2ItemById(projectId:$p, contentId:$c){item{id}} }' "
            "-f p=PVT_kwDOEXAMPLE00000 -f c=ISSUE_ID"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True

    def test_add_item_mutation_with_unrelated_node_id_allowed(self):
        cmd = (
            "gh api graphql -f query='mutation { addProjectV2ItemById("
            "projectId: \"PVT_someOtherBoard\", contentId: \"ISSUE_ID\") "
            "{ item { id } } }'"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False

    def test_graphql_query_mentioning_node_id_with_no_add_mutation_allowed(self):
        cmd = (
            "gh api graphql -f query='query { node(id: \"PVT_kwDOEXAMPLE00000\") "
            "{ ... on ProjectV2 { title } } }'"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False


# ===========================================================================
# Shape (c): `gh issue create|edit` / `gh pr create` with
# --project/--add-project naming a protected board's title or number.
# ===========================================================================


class TestShapeCIssuePrProjectFlag:
    def test_issue_create_with_project_title_denied(self):
        block, reason = guard.decide(
            "gh issue create --title x --body y --project 'Example Support Tickets'",
            _BOARDS,
        )
        assert block is True
        assert reason.startswith("protected-board-project-flag")

    def test_issue_create_with_project_title_case_insensitive_denied(self):
        block, reason = guard.decide(
            "gh issue create --title x --body y --project 'example support tickets'",
            _BOARDS,
        )
        assert block is True

    def test_issue_edit_with_add_project_number_denied(self):
        block, reason = guard.decide("gh issue edit 42 --add-project 5", _BOARDS)
        assert block is True

    def test_pr_create_with_project_number_denied(self):
        block, reason = guard.decide(
            "gh pr create --title x --body y --project 5", _BOARDS
        )
        assert block is True

    def test_issue_create_with_different_project_title_allowed(self):
        block, reason = guard.decide(
            "gh issue create --title x --body y --project 'Some Other Board'",
            _BOARDS,
        )
        assert block is False

    def test_issue_create_with_no_project_flag_allowed(self):
        block, reason = guard.decide("gh issue create --title x --body y", _BOARDS)
        assert block is False

    # -- short `-p` flag (blocker 1: `gh issue create -p "<title>"`) --------

    def test_issue_create_short_p_flag_matching_title_denied(self):
        block, reason = guard.decide(
            'gh issue create --title x --body y -p "Example Support Tickets"',
            _BOARDS,
        )
        assert block is True
        assert reason.startswith("protected-board-project-flag")

    def test_issue_create_short_p_flag_different_title_allowed(self):
        block, reason = guard.decide(
            'gh issue create --title x --body y -p "Roadmap"', _BOARDS
        )
        assert block is False

    # -- `("pr", "edit")` verb pair (blocker 2) ------------------------------

    def test_pr_edit_with_add_project_title_denied(self):
        block, reason = guard.decide(
            "gh pr edit 7 --add-project 'Example Support Tickets'", _BOARDS
        )
        assert block is True
        assert reason.startswith("protected-board-project-flag")

    def test_pr_edit_with_different_project_allowed(self):
        block, reason = guard.decide("gh pr edit 7 --add-project 'Roadmap'", _BOARDS)
        assert block is False


class TestShapeCMultiValueAndRepeatedFlag:
    """Blocker 2: `_flag_value` used to return only the FIRST occurrence and
    compared the raw value whole — missing gh's comma-separated multi-values
    and repeated flags. Each deny paired with a nearby allow."""

    def test_comma_list_containing_protected_title_denied(self):
        block, reason = guard.decide(
            "gh pr edit 7 --add-project \"Roadmap,Example Support Tickets\"", _BOARDS
        )
        assert block is True
        assert reason.startswith("protected-board-project-flag")

    def test_repeated_flag_with_protected_title_second_denied(self):
        block, reason = guard.decide(
            "gh issue create --title x --body y --project Roadmap "
            "--project 'Example Support Tickets'",
            _BOARDS,
        )
        assert block is True
        assert reason.startswith("protected-board-project-flag")

    def test_comma_list_of_two_unrelated_titles_allowed(self):
        block, reason = guard.decide(
            "gh pr edit 7 --add-project \"Roadmap,Some Other Board\"", _BOARDS
        )
        assert block is False


# ===========================================================================
# Shape (d): `gh_issue.sh --project <number>` matching a protected board.
# ===========================================================================


class TestShapeDGhIssueSh:
    def test_gh_issue_sh_create_triage_project_matching_denied(self):
        cmd = (
            "gh_issue.sh create --title x --body-file f.md --triage Backlog "
            "--project 5 --owner example-org"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True
        assert reason.startswith("protected-board-gh-issue-sh")

    def test_gh_issue_sh_transition_project_matching_denied(self):
        cmd = (
            "gh_issue.sh transition 42 --status Ready --project 5 "
            "--owner example-org"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True

    def test_gh_issue_sh_absolute_path_still_matches_basename(self):
        cmd = (
            "~/.claude/scripts/gh_issue.sh create --title x --body-file f.md "
            "--project 5 --owner example-org"
        )
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True

    def test_gh_issue_sh_different_project_number_allowed(self):
        cmd = "gh_issue.sh create --title x --body-file f.md --project 1 --owner example-org"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False

    def test_gh_issue_sh_no_project_flag_allowed(self):
        cmd = "gh_issue.sh create --title x --body-file f.md"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False


# ===========================================================================
# Blocker 3: ENV=val prefix stripping / `env`/`command` invoker words / gh
# global-flag tolerance. Each deny paired with a nearby allow.
# ===========================================================================


class TestEnvPrefixAndGlobalFlagTolerance:
    def test_env_assignment_prefix_item_add_denied(self):
        block, reason = guard.decide(
            "GH_TOKEN=x gh project item-add 5 --owner example-org --url https://x",
            _BOARDS,
        )
        assert block is True
        assert reason.startswith("protected-board-item-add")

    def test_env_command_prefix_item_add_denied(self):
        block, reason = guard.decide(
            "env gh project item-add 5 --owner example-org --url https://x",
            _BOARDS,
        )
        assert block is True

    def test_command_invoker_prefix_item_add_denied(self):
        block, reason = guard.decide(
            "command gh project item-add 5 --owner example-org --url https://x",
            _BOARDS,
        )
        assert block is True

    def test_gh_global_repo_flag_item_add_denied(self):
        block, reason = guard.decide(
            "gh -R example-org/ExampleApp project item-add 5 "
            "--owner example-org --url https://x",
            _BOARDS,
        )
        assert block is True

    def test_env_assignment_prefix_project_view_allowed(self):
        # The paired allow: same ENV-prefix tolerance, but a genuine read.
        block, reason = guard.decide(
            "GH_TOKEN=x gh project view 5 --owner example-org", _BOARDS
        )
        assert block is False


# ===========================================================================
# Compound commands / untokenizable segments.
# ===========================================================================


class TestCompoundAndUntokenizable:
    def test_compound_command_second_segment_denied(self):
        cmd = "echo hi && gh project item-add 5 --owner example-org --url https://x"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True

    def test_compound_command_both_segments_safe_allowed(self):
        cmd = "echo hi && gh project view 5 --owner example-org"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False

    def test_untokenizable_segment_with_gh_and_item_add_shape_denied(self):
        # Unbalanced quote, but the raw text still carries a `gh`+`project`+
        # `item-add` shape -> fail closed.
        cmd = "gh project item-add 5 --owner example-org --title 'unterminated"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is True
        assert reason == "untokenizable-segment-with-protected-board-shape"

    def test_untokenizable_segment_with_protected_node_id_denied(self):
        cmd = "gh api graphql -f query='addProjectV2ItemById unterminated"
        block, reason = guard.decide(
            cmd + " " + _TEST_BOARD["node_id"], _BOARDS
        )
        assert block is True
        assert reason == "untokenizable-segment-with-protected-board-shape"

    def test_untokenizable_segment_with_gh_but_no_add_shape_allowed(self):
        cmd = "gh issue view 42 --comment 'unterminated"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False

    def test_untokenizable_segment_with_no_gh_mention_allowed(self):
        cmd = "echo 'unterminated"
        block, reason = guard.decide(cmd, _BOARDS)
        assert block is False


# ===========================================================================
# Registry fail-open, empty command, decision never raises.
# ===========================================================================


class TestFailOpenAndEdgeCases:
    def test_no_boards_configured_allows_everything(self):
        block, reason = guard.decide(
            "gh project item-add 5 --owner example-org --url https://x", []
        )
        assert block is False
        assert reason == "no-protected-boards-configured"

    def test_empty_command_allows(self):
        block, reason = guard.decide("", _BOARDS)
        assert block is False

    def test_whitespace_only_command_allows(self):
        block, reason = guard.decide("   \n  ", _BOARDS)
        assert block is False

    def test_none_boards_loads_real_registry_without_raising(self, sandbox):
        # No registry file exists in the sandbox -> load_registry() -> [] ->
        # fail open, never crash.
        block, reason = guard.decide(
            "gh project item-add 5 --owner example-org --url https://x"
        )
        assert block is False

    @pytest.mark.parametrize(
        "command",
        [
            None,
            123,
            "gh project item-add",  # no number token
            "gh project item-add --owner X",  # flag where number expected
            "gh api graphql",  # no query at all
            "a" * 5000 + " gh project item-add 5 --owner example-org",
        ],
    )
    def test_decide_never_raises_on_garbage(self, command):
        block, reason = guard.decide(command, _BOARDS)
        assert isinstance(block, bool)
        assert isinstance(reason, str)


# ===========================================================================
# message_for().
# ===========================================================================


class TestMessageFor:
    def test_message_names_board_title_and_tracker(self):
        msg = guard.message_for("protected-board-item-add:Example Support Tickets", _BOARDS)
        assert "Example Support Tickets" in msg
        assert "customer-only" in msg.lower() or "customer" in msg.lower()
        assert _TEST_BOARD["tracker"] in msg

    def test_message_for_untokenizable_reason_still_readable(self):
        msg = guard.message_for("untokenizable-segment-with-protected-board-shape", _BOARDS)
        assert "protected_board_guard" in msg


# ===========================================================================
# main(): log-only vs enforce, kill switch, non-Bash tools.
# ===========================================================================


class TestMainLogOnlyVsEnforce:
    def _registry_in_sandbox(self, sandbox):
        p = sandbox.claude / "knowledge" / "protected_boards.json"
        _write_registry(p, _BOARDS)
        return p

    def test_main_log_only_default(self, sandbox, monkeypatch, capsys):
        self._registry_in_sandbox(sandbox)
        rc, out = _run_main(
            monkeypatch,
            _ev("gh project item-add 5 --owner example-org --url https://x"),
            capsys,
        )
        assert rc == 0
        assert out == ""
        log_lines = sandbox.log_file.read_text().splitlines()
        assert any(
            '"would-deny"' in ln and "protected_board_guard" in ln for ln in log_lines
        )

    def test_main_enforce_emits_deny(self, sandbox, monkeypatch, capsys):
        self._registry_in_sandbox(sandbox)
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc, out = _run_main(
            monkeypatch,
            _ev("gh project item-add 5 --owner example-org --url https://x"),
            capsys,
        )
        assert rc == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected_board_guard" in payload["hookSpecificOutput"]["permissionDecisionReason"]
        assert "Example Support Tickets" in payload["hookSpecificOutput"]["permissionDecisionReason"]

    def test_main_enforce_allows_legitimate_pattern(self, sandbox, monkeypatch, capsys):
        self._registry_in_sandbox(sandbox)
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc, out = _run_main(
            monkeypatch,
            _ev("gh project item-add 1 --owner example-org --url https://x"),
            capsys,
        )
        assert rc == 0
        assert out == ""

    def test_kill_switch_short_circuits_before_anything(self, sandbox, monkeypatch, capsys):
        self._registry_in_sandbox(sandbox)
        monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc, out = _run_main(
            monkeypatch,
            _ev("gh project item-add 5 --owner example-org --url https://x"),
            capsys,
        )
        assert rc == 0
        assert out == ""
        assert not sandbox.log_file.exists()

    def test_non_bash_tool_never_blocks(self, sandbox, monkeypatch, capsys):
        self._registry_in_sandbox(sandbox)
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc, out = _run_main(
            monkeypatch,
            _ev(
                "gh project item-add 5 --owner example-org --url https://x",
                tool_name="Read",
            ),
            capsys,
        )
        assert rc == 0
        assert out == ""

    def test_missing_registry_in_sandbox_allows_and_never_crashes(self, sandbox, monkeypatch, capsys):
        # No registry file written -> fail open.
        monkeypatch.setenv("CSA_ENFORCE", "1")
        rc, out = _run_main(
            monkeypatch,
            _ev("gh project item-add 5 --owner example-org --url https://x"),
            capsys,
        )
        assert rc == 0
        assert out == ""


# ===========================================================================
# End-to-end proof through the REAL dispatch path: bash_gate.sh's own
# fast-path case statement -> pretooluse_bash.py -> protected_board_guard.
# Mirrors TestBashGateShEndToEnd in test_pretooluse_bash.py.
# ===========================================================================


class TestBashGateShEndToEnd:
    def _sandbox_home(self, tmp_path):
        import pretooluse_bash as ptb

        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        os.symlink(ptb._HOOKS_DIR, home / ".claude" / "hooks")
        (home / ".claude" / "knowledge").mkdir(parents=True, exist_ok=True)
        _write_registry(home / ".claude" / "knowledge" / "protected_boards.json", _BOARDS)
        return home, ptb

    def _run_bash_gate(self, payload, *, cwd, hooks_dir, env_extra=None):
        env = dict(os.environ)
        env.pop("CSA_DISABLE_HOOKS", None)
        env.pop("CSA_ENFORCE", None)
        if env_extra:
            env.update(env_extra)
        script = os.path.join(hooks_dir, "bash_gate.sh")
        return subprocess.run(
            ["bash", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(cwd),
            env=env,
        )

    def test_fast_path_dispatches_a_protected_board_item_add_and_denies_it(self, tmp_path):
        home, ptb = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "gh project item-add 5 --owner example-org --url https://x"
            },
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(
            payload, cwd=tmp_path, hooks_dir=ptb._HOOKS_DIR, env_extra={"HOME": str(home)}
        )
        assert proc.returncode == 0  # deny is JSON, never a nonzero exit
        obj = json.loads(proc.stdout)
        assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected_board_guard" in obj["systemMessage"]

    def test_fast_path_still_skips_unrelated_commands_no_python_spawn(self, tmp_path):
        home, ptb = self._sandbox_home(tmp_path)
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        proc = self._run_bash_gate(
            payload, cwd=tmp_path, hooks_dir=ptb._HOOKS_DIR, env_extra={"HOME": str(home)}
        )
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert not (home / ".claude" / ".enforcement" / "log.jsonl").exists()

    def test_fast_path_reads_allowed_through_dispatcher(self, tmp_path):
        home, ptb = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "gh project view 5 --owner example-org"},
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(
            payload, cwd=tmp_path, hooks_dir=ptb._HOOKS_DIR, env_extra={"HOME": str(home)}
        )
        assert proc.returncode == 0
        assert proc.stdout == ""

    def test_fast_path_dispatches_short_p_flag_issue_create_and_denies_it(self, tmp_path):
        # Blocker 1: `gh issue create -p "<title>"` must actually reach
        # python via bash_gate.sh's new `*gh*create*-p*` fast-path arm, not
        # just be denied by decide() in isolation (TestShapeCIssuePrProjectFlag
        # above already covers the pure decision; this proves the payload
        # actually gets dispatched end-to-end).
        home, ptb = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    'gh issue create --title x --body y -p "Example Support Tickets"'
                )
            },
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(
            payload, cwd=tmp_path, hooks_dir=ptb._HOOKS_DIR, env_extra={"HOME": str(home)}
        )
        assert proc.returncode == 0
        obj = json.loads(proc.stdout)
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected_board_guard" in obj["systemMessage"]

    def test_fast_path_dispatches_env_prefixed_item_add_and_denies_it(self, tmp_path):
        # Blocker 3: `GH_TOKEN=x gh project item-add ...` must reach python
        # via the existing `*gh*project*` fast-path arm (the ENV= prefix
        # doesn't change bash_gate.sh's substring match) and then actually be
        # denied by decide()'s new _strip_leading_invokers handling.
        home, ptb = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "GH_TOKEN=x gh project item-add 5 --owner example-org "
                    "--url https://github.com/example-org/ExampleApp/issues/1"
                )
            },
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(
            payload, cwd=tmp_path, hooks_dir=ptb._HOOKS_DIR, env_extra={"HOME": str(home)}
        )
        assert proc.returncode == 0
        obj = json.loads(proc.stdout)
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "protected_board_guard" in obj["systemMessage"]
