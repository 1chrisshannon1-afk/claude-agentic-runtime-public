#!/usr/bin/env python3
"""Tests for workflow_model_gate — the PreToolUse:Workflow explicit-model gate.

Every case in `_ADVERSARIAL` below is a shape an Opus code review used to DEFEAT
the first version of this module (2026-09-23). That version hand-rolled its own
paren/quote scanner and, measured against the real scripts on disk, denied BOTH of
them — including `workflows/issue-wheel-triage.js`, which the nightly ISSUE WHEEL
runs unattended — while separately false-ALLOWING a genuine cost cliff.

The fix was to stop parsing JS here and delegate to
`check_workflow_agent_purity.find_agent_call_sites()`, which already handled all of
it. These tests exist so a future "simplification" back to a local parser fails
loudly instead of silently re-denying the wheel.

`test_real_workflow_scripts_are_allowed` is the single most important test in this
file: it runs the gate against whatever `.js` files actually live in
`~/.claude/workflows/`, so it fails the moment the gate would block real,
compliant, production work. The v1 scanner failed exactly this test.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

_HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

import workflow_model_gate as gate  # noqa: E402

_GATE_PATH = os.path.join(_HOOKS, "workflow_model_gate.py")
_WORKFLOWS_DIR = pathlib.Path.home() / ".claude" / "workflows"


# (label, script, expect_denied)
_ADVERSARIAL = [
    # --- v1 BLOCKER 1: no comment handling. An apostrophe in a // comment opened
    # a phantom string literal that ran to EOF and swallowed the real model: key.
    # This one defect alone false-denied every real script on disk.
    (
        "apostrophe in a line comment does not swallow the model key",
        "const a = await agent('p', {\n  // we don't want opus here\n  model: 'sonnet',\n});",
        False,
    ),
    (
        "apostrophe in a block comment",
        "/* don't do this */\nconst a = await agent('p', { model:'opus' });",
        False,
    ),
    # --- v1 BLOCKER 2: the model: search ran over the whole call text, so a
    # nested schema property named `model` satisfied it. A false ALLOW on exactly
    # the shape this gate exists to stop.
    (
        "a nested schema property named model does NOT satisfy the check",
        "const b = await agent('x', {\n"
        "  outputSchema: { type:'object', properties: { model: { type:'string' } } },\n"
        "});",
        True,
    ),
    # --- v1 BLOCKER 3: options passed by variable or spread were denied with a
    # message telling the author to do what they had already done.
    (
        "options passed by identifier are not judged",
        "const opts = { model: 'sonnet' };\nconst a = await agent(opts);",
        False,
    ),
    (
        "options spread from another object are not judged",
        "const base = { model: 'sonnet' };\nconst a = await agent('p', { ...base, label:'x' });",
        False,
    ),
    (
        "a spread with no model anywhere is the accepted bypass, not a deny",
        "const a = await agent('p', { ...base });",
        False,
    ),
    # --- v1: `agent(` inside a comment was counted as a real call site.
    (
        "agent( inside a comment is not a call site",
        "// const x = await agent('p', {});\nconst a = await agent('p', { model:'sonnet' });",
        False,
    ),
    # --- the check must still do its actual job.
    ("a genuine missing model denies", "const a = await agent('p', { label: 'x' });", True),
    (
        "model: mentioned only in prompt prose does not count",
        "const a = await agent('set model: opus please', { label:'x' });",
        True,
    ),
    (
        "one compliant call and one missing denies only the missing one",
        "await agent('a',{model:'sonnet'});\nawait agent('b',{label:'z'});",
        True,
    ),
    # --- general JS shapes that must not confuse the scanner.
    (
        "a regex literal containing an unbalanced paren",
        "const r = /^\\(foo/;\nconst a = await agent('p', { model:'sonnet' });",
        False,
    ),
    (
        "a paren inside a quoted prompt string",
        "const a = await agent('call foo(bar) now', { model:'sonnet' });",
        False,
    ),
    (
        "a template literal prompt with interpolation",
        "const a = await agent(`do ${x} now`, { model:'sonnet' });",
        False,
    ),
    (
        "an arrow function inside the options object",
        "const a = await agent('p', { model:'sonnet', then:(r)=>({...r}) });",
        False,
    ),
]


class TestMissingModelLines(unittest.TestCase):
    def test_adversarial_shapes(self):
        for label, script, expect_denied in _ADVERSARIAL:
            with self.subTest(label):
                missing, _total = gate.missing_model_lines(script)
                self.assertEqual(
                    bool(missing),
                    expect_denied,
                    f"{label}: expected {'DENY' if expect_denied else 'ALLOW'}, "
                    f"got {'DENY' if missing else 'ALLOW'} (lines={missing})",
                )

    def test_reports_the_line_of_the_offending_call(self):
        script = "await agent('a',{model:'sonnet'});\nawait agent('b',{label:'z'});"
        missing, total = gate.missing_model_lines(script)
        self.assertEqual(missing, [2])
        self.assertEqual(total, 2)

    def test_repeated_identical_calls_report_distinct_lines(self):
        """Call sites carry no offset, so the line lookup must resume past each
        match — otherwise every identical call reports the first one's line."""
        script = "await agent('x',{label:'a'});\nawait agent('x',{label:'a'});"
        missing, total = gate.missing_model_lines(script)
        self.assertEqual(total, 2)
        self.assertEqual(missing, [1, 2])

    def test_no_agent_calls_at_all(self):
        missing, total = gate.missing_model_lines("export const meta = {name:'x'};")
        self.assertEqual((missing, total), ([], 0))


class TestRealWorkflowScripts(unittest.TestCase):
    """The regression that actually mattered: v1 denied 2 of 2 real scripts."""

    def test_real_workflow_scripts_are_allowed(self):
        scripts = sorted(_WORKFLOWS_DIR.glob("*.js")) if _WORKFLOWS_DIR.is_dir() else []
        if not scripts:
            self.skipTest(f"no workflow scripts on disk at {_WORKFLOWS_DIR}")
        for path in scripts:
            with self.subTest(path.name):
                missing, total = gate.missing_model_lines(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    missing,
                    [],
                    f"{path.name} would be DENIED (sites={total}, lines={missing}). "
                    "A real, compliant workflow script must never be blocked — this is "
                    "the exact failure that made v1 unlandable.",
                )


def _run_gate(payload: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("CSA_DISABLE_HOOKS", None)
    # The hook prints its deny JSON only when enforcement is ON (_lib.enforcing:
    # CSA_DISABLE_HOOKS=1 -> off, else CSA_ENFORCE=1 or a global ~/.claude/.enforce
    # marker -> on). Without this line the deny tests passed only on a machine
    # that happens to carry the global marker (silent hook -> json.loads("")
    # elsewhere), and every "allows silently" test passed vacuously wherever
    # enforcement was off. Pin it so the subprocess behaves identically on any
    # machine; a test that wants the kill switch passes CSA_DISABLE_HOOKS via
    # env_extra (the master-off switch outranks CSA_ENFORCE).
    env["CSA_ENFORCE"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, _GATE_PATH],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )


class TestHookEntryPoint(unittest.TestCase):
    def test_denies_a_missing_model_with_the_canonical_shape(self):
        payload = json.dumps(
            {"tool_name": "Workflow", "tool_input": {"script": "await agent('p',{label:'x'});"}}
        )
        proc = _run_gate(payload)
        self.assertEqual(proc.returncode, 0)
        obj = json.loads(proc.stdout)
        hso = obj["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("do not name a model", hso["permissionDecisionReason"])
        # The agent-facing reason and the operator-facing message carry the same
        # text, per _lib.emit_pretooluse_deny's contract.
        self.assertEqual(hso["permissionDecisionReason"], obj["systemMessage"])

    def test_allows_a_compliant_script_silently(self):
        payload = json.dumps(
            {"tool_name": "Workflow", "tool_input": {"script": "await agent('p',{model:'sonnet'});"}}
        )
        proc = _run_gate(payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_ignores_a_non_workflow_tool(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        proc = _run_gate(payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_fails_open_on_malformed_stdin(self):
        proc = _run_gate("not json at all")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_fails_open_on_unreadable_script_path(self):
        payload = json.dumps(
            {"tool_name": "Workflow", "tool_input": {"scriptPath": "/nonexistent/nope.js"}}
        )
        proc = _run_gate(payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_kill_switch_short_circuits_before_any_parse(self):
        payload = json.dumps(
            {"tool_name": "Workflow", "tool_input": {"script": "await agent('p',{});"}}
        )
        proc = _run_gate(payload, {"CSA_DISABLE_HOOKS": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_reads_a_script_from_scriptPath(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write("await agent('p',{label:'x'});")
            tmp = fh.name
        try:
            payload = json.dumps({"tool_name": "Workflow", "tool_input": {"scriptPath": tmp}})
            proc = _run_gate(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("do not name a model", proc.stdout)
        finally:
            os.unlink(tmp)

    def test_the_live_payload_key_names_are_the_ones_we_parse(self):
        """Guard the reviewer's one UNVERIFIED item.

        Resolved 2026-09-23 against ~/.claude/.enforcement/workflow_probe.jsonl,
        a real captured PreToolUse:Workflow payload: tool_name == "Workflow" and
        tool_input carries "script". If the platform ever renames either key,
        this module silently no-ops (fail-open) and the gate is INERT while still
        passing every synthetic test — which is why this asserts on the real
        captured payload rather than a hand-built one.
        """
        probe = pathlib.Path.home() / ".claude" / ".enforcement" / "workflow_probe.jsonl"
        if not probe.is_file():
            self.skipTest("no captured Workflow payload on disk")
        seen = []
        for line in probe.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if (d.get("tool_name") or d.get("tool")) != "Workflow":
                continue
            ti = d.get("tool_input") or d.get("toolInput") or {}
            if isinstance(ti, dict):
                seen.extend(ti.keys())
        if not seen:
            self.skipTest("probe file holds no Workflow payloads")
        self.assertTrue(
            {"script", "scriptPath"} & set(seen),
            f"live payload carries none of the keys this gate reads: {sorted(set(seen))}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
