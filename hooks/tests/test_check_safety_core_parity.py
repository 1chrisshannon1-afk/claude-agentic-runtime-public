"""Hermetic tests for hooks/check_safety_core_parity.py.

The bash source ~/.claude/scripts/enforcement_doctor.sh is a read-only reporter;
its *test vectors* are the shapes it iterates over and the four allowlist keys it
summarizes. We reproduce those as the spec baseline (a GOOD, fully-wired runtime
plus DRIFTED variants) and then expand to cover every branch of the pure
check() and the thin main() adapter.

Every test runs against the `sandbox` fixture ($HOME + _lib path constants
pointed into a tmp dir). No network, no real ~/.claude, no real git.
"""

from __future__ import annotations

import io
import json
import os

import _lib
import check_safety_core_parity as mod
import pytest

# ===========================================================================
# Fixtures that materialize a realistic on-disk runtime under the sandbox.
# ===========================================================================


# The four scripts the shipped settings.json actually wires (matching the real
# enforcement_doctor.sh runtime this module validates).
_WIRED_SCRIPTS = (
    "git_guard.sh",
    "agent_budget.sh",
    "pii_scrub.sh",
    "review-gate.sh",
)


def _kill(cmd: str) -> str:
    """Prefix a command with the settings.json kill-switch guard, verbatim."""
    return '[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0; ' + cmd


def _good_settings() -> dict:
    """A well-formed settings.json mirroring the shipped hooks block shape."""
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _kill("bash ~/.claude/scripts/git_guard.sh"),
                        }
                    ],
                },
                {
                    "matcher": "Task",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _kill("bash ~/.claude/scripts/agent_budget.sh gate"),
                        }
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "mcp__playwright.*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _kill("bash ~/.claude/scripts/pii_scrub.sh"),
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": _kill("bash ~/.claude/scripts/review-gate.sh"),
                        }
                    ]
                }
            ],
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": _kill("printf 'banner\\n'"),
                        }
                    ]
                }
            ],
        }
    }


def _good_allowlist() -> dict:
    return {
        "allowed_origins": ["http://localhost:*"],
        "allowed_company_tenants": ["<SANDBOX_COMPANY_ID>"],
        "test_recipients": {"emails": [], "phones": []},
        "denied_action_patterns": ["https://*.stripe.com/*"],
    }


@pytest.fixture
def runtime(sandbox):
    """Materialize a GOOD runtime on disk: scripts, hooks modules, settings,
    allowlist. Returns an object with the paths + writers so a test can DRIFT it.
    """
    scripts = sandbox.claude / "scripts"
    scripts.mkdir(parents=True)
    for name in _WIRED_SCRIPTS:
        (scripts / name).write_text("#!/usr/bin/env bash\nexit 0\n")

    hooks = sandbox.claude / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "_lib.py").write_text("# stub\n")
    (hooks / "check_safety_core_parity.py").write_text("# stub\n")

    live = sandbox.claude / "live-testing"
    live.mkdir(parents=True)

    settings_path = sandbox.claude / "settings.json"
    allowlist_path = live / "allowlist.json"

    class RT:
        def __init__(self):
            self.claude = sandbox.claude
            self.scripts = scripts
            self.hooks = hooks
            self.settings_path = settings_path
            self.allowlist_path = allowlist_path

        def write_settings(self, obj):
            settings_path.write_text(json.dumps(obj))

        def write_settings_raw(self, text):
            settings_path.write_text(text)

        def write_allowlist(self, obj):
            allowlist_path.write_text(json.dumps(obj))

        def write_allowlist_raw(self, text):
            allowlist_path.write_text(text)

    rt = RT()
    rt.write_settings(_good_settings())
    rt.write_allowlist(_good_allowlist())
    return rt


def _feed_stdin(monkeypatch, payload: dict):
    """Point sys.stdin at a JSON payload so main()->read_event consumes it."""
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(_lib.sys, "stdin", io.StringIO(json.dumps(payload)))


# ===========================================================================
# extract_script_refs — pull wired script paths out of a command string.
# ===========================================================================


def test_extract_single_bash_ref():
    home = os.path.expanduser("~")
    refs = mod.extract_script_refs("bash ~/.claude/scripts/git_guard.sh")
    assert refs == [os.path.join(home, ".claude/scripts/git_guard.sh")]


def test_extract_with_killswitch_prefix():
    # The real wired form: guard `; bash <script>` — only the script is a ref.
    home = os.path.expanduser("~")
    cmd = _kill("bash ~/.claude/scripts/agent_budget.sh gate")
    refs = mod.extract_script_refs(cmd)
    assert refs == [os.path.join(home, ".claude/scripts/agent_budget.sh")]


def test_extract_python_hook_module_ref():
    home = os.path.expanduser("~")
    cmd = "python3 ~/.claude/hooks/git_guard.py"
    refs = mod.extract_script_refs(cmd)
    assert refs == [os.path.join(home, ".claude/hooks/git_guard.py")]


def test_extract_bare_hook_module_ref():
    home = os.path.expanduser("~")
    refs = mod.extract_script_refs("~/.claude/hooks/check_safety_core_parity.py")
    assert refs == [os.path.join(home, ".claude/hooks/check_safety_core_parity.py")]


def test_extract_absolute_path_ref():
    # Absolute (already-expanded) path also matches; no ~ to expand.
    refs = mod.extract_script_refs("bash /home/x/.claude/scripts/pii_scrub.sh")
    assert refs == ["/home/x/.claude/scripts/pii_scrub.sh"]


def test_extract_no_script_ref_returns_empty():
    # A pure banner printf references no script.
    assert mod.extract_script_refs(_kill("printf 'banner\\n'")) == []


def test_extract_ignores_non_claude_scripts():
    # A script outside .claude/{scripts,hooks} is not existence-checked here.
    assert mod.extract_script_refs("bash /usr/local/bin/other.sh") == []


def test_extract_non_string_and_empty():
    assert mod.extract_script_refs("") == []
    assert mod.extract_script_refs(None) == []
    assert mod.extract_script_refs(123) == []


def test_extract_multiple_refs_in_one_command():
    # A (contrived) chain naming two scripts yields both, in order.
    home = os.path.expanduser("~")
    cmd = "bash ~/.claude/scripts/git_guard.sh; bash ~/.claude/scripts/pii_scrub.sh"
    refs = mod.extract_script_refs(cmd)
    assert refs == [
        os.path.join(home, ".claude/scripts/git_guard.sh"),
        os.path.join(home, ".claude/scripts/pii_scrub.sh"),
    ]


def test_extract_home_prefixed_quoted_ref():
    # bash_gate.sh's own real body: `python3 "$HOME/.claude/hooks/x.py"` --
    # $HOME (not ~), double-quoted. Regression for the guard-wiring closure,
    # which needs to walk exactly this shape out of a wired .sh dispatcher.
    home = os.path.expanduser("~")
    cmd = 'printf \'%s\' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"'
    refs = mod.extract_script_refs(cmd)
    assert refs == [os.path.join(home, ".claude/hooks/pretooluse_bash.py")]


def test_extract_home_prefixed_unquoted_ref():
    home = os.path.expanduser("~")
    refs = mod.extract_script_refs("python3 $HOME/.claude/hooks/agent_budget.py gate")
    assert refs == [os.path.join(home, ".claude/hooks/agent_budget.py")]


def test_extract_tilde_ref_still_quoted_form():
    # A quoted ~-form path (less common, but the optional leading quote must
    # not break the pre-existing ~-expansion path either).
    home = os.path.expanduser("~")
    refs = mod.extract_script_refs('bash "~/.claude/scripts/git_guard.sh"')
    assert refs == [os.path.join(home, ".claude/scripts/git_guard.sh")]


# ===========================================================================
# check() — the PURE decision. SPEC baseline: good config -> no problems.
# ===========================================================================


def _files_for(*paths):
    return set(paths)


def test_check_good_config_no_problems():
    home = os.path.expanduser("~")
    settings = _good_settings()
    settings["__allowlist__"] = _good_allowlist()
    files = {os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS}
    assert mod.check(settings, files) == []


def test_check_dangling_script_reference():
    # DRIFT: remove git_guard.sh from the existence oracle -> one dangling ref.
    home = os.path.expanduser("~")
    settings = _good_settings()
    settings["__allowlist__"] = _good_allowlist()
    files = {
        os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS if n != "git_guard.sh"
    }
    problems = mod.check(settings, files)
    assert len(problems) == 1
    assert "git_guard.sh" in problems[0]
    assert "PreToolUse" in problems[0]


def test_check_all_scripts_missing():
    # DRIFT: nothing on disk -> every wired *script* reference dangles (4).
    settings = _good_settings()
    settings["__allowlist__"] = _good_allowlist()
    problems = mod.check(settings, set())
    dangling = [p for p in problems if "references missing script" in p]
    assert len(dangling) == len(_WIRED_SCRIPTS)


@pytest.mark.parametrize("missing_key", list(mod.REQUIRED_ALLOWLIST_KEYS))
def test_check_allowlist_missing_required_key(missing_key):
    home = os.path.expanduser("~")
    settings = _good_settings()
    allow = _good_allowlist()
    del allow[missing_key]
    settings["__allowlist__"] = allow
    files = {os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS}
    problems = mod.check(settings, files)
    assert problems == ["allowlist.json missing required key: %s" % missing_key]


def test_check_allowlist_absent():
    home = os.path.expanduser("~")
    settings = _good_settings()
    settings["__allowlist__"] = None
    files = {os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS}
    problems = mod.check(settings, files)
    assert problems == ["allowlist.json is absent"]


def test_check_allowlist_parse_error():
    home = os.path.expanduser("~")
    settings = _good_settings()
    settings["__allowlist__"] = {"__parse_error__": "Expecting value: line 1"}
    files = {os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS}
    problems = mod.check(settings, files)
    assert len(problems) == 1
    assert problems[0].startswith("allowlist.json failed to parse")


def test_check_allowlist_not_an_object():
    home = os.path.expanduser("~")
    settings = _good_settings()
    settings["__allowlist__"] = ["not", "a", "dict"]
    files = {os.path.join(home, ".claude/scripts", n) for n in _WIRED_SCRIPTS}
    problems = mod.check(settings, files)
    assert problems == ["allowlist.json did not parse as a JSON object"]


# --- settings-shape drift ---------------------------------------------------


def test_check_settings_not_a_dict():
    assert mod.check(["nope"], set()) == ["settings.json did not parse as a JSON object"]


def test_check_settings_parse_error_sentinel():
    problems = mod.check({"__parse_error__": "boom"}, set())
    assert len(problems) == 1
    assert problems[0].startswith("settings.json failed to parse")


def test_check_hooks_not_an_object():
    problems = mod.check({"hooks": "nope", "__allowlist__": _good_allowlist()}, set())
    assert problems == ["settings.json 'hooks' is not an object"]


def test_check_no_hooks_block_is_ok():
    # No hooks block at all: nothing to dangle; allowlist still validated.
    problems = mod.check({"__allowlist__": _good_allowlist()}, set())
    assert problems == []


def test_check_event_matchers_not_a_list():
    settings = {
        "hooks": {"PreToolUse": {"bad": "shape"}},
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse is not a list of matcher objects"]


def test_check_matcher_not_an_object():
    settings = {
        "hooks": {"PreToolUse": ["not-an-object"]},
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse[0] is not an object"]


def test_check_matcher_hooks_not_a_list():
    settings = {
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": "nope"}]},
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse[0].hooks is not a list"]


def test_check_hook_entry_not_an_object():
    settings = {
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": ["nope"]}]},
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse[0].hooks[0] is not an object"]


def test_check_hook_entry_missing_command():
    settings = {
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command"}]}]},
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse[0].hooks[0] has no command string"]


def test_check_hook_entry_empty_command():
    settings = {
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": ""}]}]
        },
        "__allowlist__": _good_allowlist(),
    }
    problems = mod.check(settings, set())
    assert problems == ["hooks.PreToolUse[0].hooks[0] has no command string"]


def test_check_matcher_with_no_hooks_list_is_ok():
    # A matcher lacking a `hooks` key defaults to [] -> nothing to check.
    settings = {
        "hooks": {"PreToolUse": [{"matcher": "Bash"}]},
        "__allowlist__": _good_allowlist(),
    }
    assert mod.check(settings, set()) == []


def test_check_banner_command_references_no_script():
    # SessionStart printf banner: no script ref -> no dangling problem.
    settings = {
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "printf 'hi\\n'"}]}]},
        "__allowlist__": _good_allowlist(),
    }
    assert mod.check(settings, set()) == []


def test_check_files_none_treated_as_empty():
    # files=None -> nothing exists; wired scripts all dangle.
    settings = _good_settings()
    settings["__allowlist__"] = _good_allowlist()
    problems = mod.check(settings, None)
    assert any("references missing script" in p for p in problems)


def test_check_files_non_iterable_degrades_to_empty():
    settings = {"__allowlist__": _good_allowlist()}

    class NotIterable:
        def __iter__(self):
            raise RuntimeError("nope")

    # set(files) raises -> treated as empty; only allowlist checked (which is ok).
    assert mod.check(settings, NotIterable()) == []


def test_check_problem_ordering_is_deterministic():
    # A dangling script AND a missing allowlist key: script problem comes first.
    home = os.path.expanduser("~")
    settings = _good_settings()
    allow = _good_allowlist()
    del allow["allowed_origins"]
    settings["__allowlist__"] = allow
    files = {
        os.path.join(home, ".claude/scripts", n)
        for n in _WIRED_SCRIPTS
        if n != "review-scriptxyz.sh"  # keep all
    }
    files.discard(os.path.join(home, ".claude/scripts/git_guard.sh"))
    problems = mod.check(settings, files)
    assert "references missing script" in problems[0]
    assert problems[-1] == "allowlist.json missing required key: allowed_origins"


# ===========================================================================
# GUARD WIRING (spec item 4) — BLOCKER 1: "guard exists, guard never fires"
# must be a detectable self-consistency problem, not a silent gap.
# ===========================================================================


def _dispatcher_settings(root_command: str) -> dict:
    """A minimal settings.json with ONE PreToolUse:Bash command wired."""
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": root_command}]}]}}


class TestLocalPythonImports:
    def test_finds_plain_import(self):
        assert mod.local_python_imports("import block_branch_ops as bbo\n", {"block_branch_ops"}) == {
            "block_branch_ops"
        }

    def test_finds_from_import(self):
        src = "from gh_issue_close_gate import decide\n"
        assert mod.local_python_imports(src, {"gh_issue_close_gate"}) == {"gh_issue_close_gate"}

    def test_ignores_stdlib_and_third_party(self):
        # os/sys/pytest are never in the on-disk hooks-module name set a real
        # caller supplies -- membership (not a hardcoded stdlib blocklist) is
        # what filters them out.
        src = "import os\nimport sys\nimport pytest\nfrom typing import Callable\n"
        assert mod.local_python_imports(src, {"block_branch_ops", "churn_tracker"}) == set()
        assert mod.local_python_imports(src, set()) == set()

    def test_multiple_imports_collected(self):
        src = "import block_branch_ops as bbo\nimport churn_tracker as ct\nimport os\n"
        found = mod.local_python_imports(src, {"block_branch_ops", "churn_tracker"})
        assert found == {"block_branch_ops", "churn_tracker"}

    def test_indented_import_inside_function_still_found(self):
        src = "def f():\n    import agent_budget as ab\n    return ab\n"
        assert mod.local_python_imports(src, {"agent_budget"}) == {"agent_budget"}

    def test_empty_source_is_empty(self):
        assert mod.local_python_imports("", {"x"}) == set()
        assert mod.local_python_imports(None, {"x"}) == set()

    def test_none_local_names_is_empty(self):
        assert mod.local_python_imports("import os\n", None) == set()

    def test_swallows_regex_exception(self, monkeypatch):
        class BoomRe:
            def finditer(self, _s):
                raise RuntimeError("boom")

        monkeypatch.setattr(mod, "_IMPORT_RE", BoomRe())
        assert mod.local_python_imports("import os\n", {"os"}) == set()


class TestWiredModulePaths:
    def test_direct_root_is_wired(self):
        sources = {"/h/no_artifact.py": "x = 1\n"}
        wired = mod.wired_module_paths(["/h/no_artifact.py"], sources)
        assert wired == {"/h/no_artifact.py"}

    def test_sh_dispatcher_body_reaches_referenced_py(self):
        # Mirrors bash_gate.sh -> pretooluse_bash.py exactly (the BLOCKER 1
        # closure hop): the root is the .sh; its OWN body names the .py via a
        # $HOME-prefixed, quoted path. extract_script_refs (which this walk
        # reuses) only recognizes a REAL ~/.claude/{scripts,hooks}/-shaped
        # path, so the fixture paths must be realistic, not arbitrary.
        home = os.path.expanduser("~")
        bash_gate = os.path.join(home, ".claude/hooks/bash_gate.sh")
        pretooluse = os.path.join(home, ".claude/hooks/pretooluse_bash.py")
        sources = {
            bash_gate: 'python3 "$HOME/.claude/hooks/pretooluse_bash.py"\n',
            pretooluse: "x = 1\n",
        }
        wired = mod.wired_module_paths([bash_gate], sources)
        assert wired == {bash_gate, pretooluse}

    def test_py_import_reaches_sibling_module(self):
        home = os.path.expanduser("~")
        pretooluse = os.path.join(home, ".claude/hooks/pretooluse_bash.py")
        gicg = os.path.join(home, ".claude/hooks/gh_issue_close_gate.py")
        sources = {
            pretooluse: "import gh_issue_close_gate as gicg\n",
            gicg: "x = 1\n",
        }
        wired = mod.wired_module_paths([pretooluse], sources)
        assert wired == {pretooluse, gicg}

    def test_full_chain_sh_to_py_to_py(self):
        # settings.json -> bash_gate.sh -> pretooluse_bash.py -> gh_issue_close_gate.py
        home = os.path.expanduser("~")
        bash_gate = os.path.join(home, ".claude/hooks/bash_gate.sh")
        pretooluse = os.path.join(home, ".claude/hooks/pretooluse_bash.py")
        gicg = os.path.join(home, ".claude/hooks/gh_issue_close_gate.py")
        sources = {
            bash_gate: 'python3 "$HOME/.claude/hooks/pretooluse_bash.py"\n',
            pretooluse: "import gh_issue_close_gate as gicg\n",
            gicg: "x = 1\n",
        }
        wired = mod.wired_module_paths([bash_gate], sources)
        assert wired == {bash_gate, pretooluse, gicg}

    def test_unreachable_module_is_not_in_closure(self):
        home = os.path.expanduser("~")
        bash_gate = os.path.join(home, ".claude/hooks/bash_gate.sh")
        orphan = os.path.join(home, ".claude/hooks/orphan.py")
        sources = {bash_gate: "python3 x\n", orphan: "x = 1\n"}
        wired = mod.wired_module_paths([bash_gate], sources)
        assert orphan not in wired

    def test_no_infinite_loop_on_import_cycle(self):
        home = os.path.expanduser("~")
        a = os.path.join(home, ".claude/hooks/a.py")
        b = os.path.join(home, ".claude/hooks/b.py")
        sources = {a: "import b\n", b: "import a\n"}
        wired = mod.wired_module_paths([a], sources)
        assert wired == {a, b}  # terminates, both reached

    def test_empty_roots_is_empty(self):
        assert mod.wired_module_paths([], {"/h/x.py": "x=1"}) == set()

    def test_none_roots_is_empty(self):
        assert mod.wired_module_paths(None, {"/h/x.py": "x=1"}) == set()

    def test_dead_end_for_path_with_no_source(self):
        # A root with NO entry in module_sources (e.g. a script outside the
        # hooks dir this checker doesn't read) is still marked reached but
        # cannot be walked further -- no crash.
        wired = mod.wired_module_paths(["/elsewhere/foo.sh"], {})
        assert wired == {"/elsewhere/foo.sh"}

    def test_swallows_internal_exception(self, monkeypatch):
        def boom(_s):
            raise RuntimeError("boom")

        monkeypatch.setattr(mod, "extract_script_refs", boom)
        wired = mod.wired_module_paths(["/h/x.sh"], {"/h/x.sh": "y"})
        assert wired == set()


class TestLooksLikePretooluseGuard:
    def test_positive_signal(self):
        src = 'def main():\n    _lib.emit_pretooluse_deny("x")\n'
        assert mod.looks_like_pretooluse_guard("some_guard.py", src) is True

    def test_no_signal(self):
        src = "def main():\n    return 0\n"
        assert mod.looks_like_pretooluse_guard("some_guard.py", src) is False

    def test_lib_py_excluded_even_with_signal(self):
        # _lib.py DEFINES the function; even a contrived source containing the
        # literal call-shaped text must not self-flag.
        src = 'def emit_pretooluse_deny(msg):\n    pass\n# _lib.emit_pretooluse_deny("example")\n'
        assert mod.looks_like_pretooluse_guard("_lib.py", src) is False

    def test_self_module_excluded_even_with_signal(self):
        # check_safety_core_parity.py's OWN docstrings/messages literally spell
        # out the target substring in prose -- must never self-flag (this is
        # the exact false positive discovered while building this feature).
        src = "# see _lib.emit_pretooluse_deny( for details\n"
        assert mod.looks_like_pretooluse_guard("check_safety_core_parity.py", src) is False

    def test_empty_source_is_false(self):
        assert mod.looks_like_pretooluse_guard("x.py", "") is False
        assert mod.looks_like_pretooluse_guard("x.py", None) is False

    def test_swallows_regex_exception(self, monkeypatch):
        class BoomRe:
            def search(self, _s):
                raise RuntimeError("boom")

        monkeypatch.setattr(mod, "_GUARD_SIGNAL_RE", BoomRe())
        assert mod.looks_like_pretooluse_guard("x.py", "_lib.emit_pretooluse_deny(") is False


class TestGuardWiringProblems:
    def test_unwired_guard_is_flagged(self):
        sources = {"/h/orphan_guard.py": '_lib.emit_pretooluse_deny("x")\n'}
        problems = mod.guard_wiring_problems(sources, wired=set())
        assert len(problems) == 1
        assert "orphan_guard.py" in problems[0]
        assert "never wired into any dispatcher" in problems[0]

    def test_wired_guard_is_not_flagged(self):
        sources = {"/h/g.py": '_lib.emit_pretooluse_deny("x")\n'}
        assert mod.guard_wiring_problems(sources, wired={"/h/g.py"}) == []

    def test_non_guard_module_never_flagged_even_if_unwired(self):
        sources = {"/h/utility.py": "def helper():\n    return 1\n"}
        assert mod.guard_wiring_problems(sources, wired=set()) == []

    def test_standalone_declared_module_not_flagged(self):
        sources = {"/h/mint_prod_session.py": '_lib.emit_pretooluse_deny("x")\n'}
        assert mod.guard_wiring_problems(sources, wired=set()) == []

    def test_standalone_param_overrides_default(self):
        sources = {"/h/custom.py": '_lib.emit_pretooluse_deny("x")\n'}
        assert mod.guard_wiring_problems(sources, wired=set(), standalone={"custom.py"}) == []
        # ... but WITHOUT that override, it IS flagged:
        assert len(mod.guard_wiring_problems(sources, wired=set(), standalone=set())) == 1

    def test_non_py_files_ignored(self):
        sources = {"/h/bash_gate.sh": '_lib.emit_pretooluse_deny("x")\n'}
        assert mod.guard_wiring_problems(sources, wired=set()) == []

    def test_multiple_unwired_guards_sorted_deterministic(self):
        sources = {
            "/h/zzz_guard.py": '_lib.emit_pretooluse_deny("x")\n',
            "/h/aaa_guard.py": '_lib.emit_pretooluse_deny("x")\n',
        }
        problems = mod.guard_wiring_problems(sources, wired=set())
        assert len(problems) == 2
        assert "aaa_guard.py" in problems[0]
        assert "zzz_guard.py" in problems[1]

    def test_swallows_internal_exception(self, monkeypatch):
        def boom(_b, _s):
            raise RuntimeError("boom")

        monkeypatch.setattr(mod, "looks_like_pretooluse_guard", boom)
        sources = {"/h/g.py": '_lib.emit_pretooluse_deny("x")\n'}
        assert mod.guard_wiring_problems(sources, wired=set()) == []


class TestCheckGuardWiringIntegration:
    def test_module_sources_none_skips_guard_wiring_entirely(self):
        # Backward compatibility: every pre-existing 2-arg call site (all the
        # tests above this section) must see IDENTICAL behavior -- no new
        # problems just because this feature now exists.
        settings = _dispatcher_settings("bash ~/.claude/hooks/orphan_guard.sh")
        settings["__allowlist__"] = _good_allowlist()
        home = os.path.expanduser("~")
        files = {os.path.join(home, ".claude/hooks/orphan_guard.sh")}
        assert mod.check(settings, files) == []

    def test_blocker1_repro_gh_issue_close_gate_unwired_is_caught(self):
        # The EXACT shape of BLOCKER 1: a dispatcher chain (settings.json ->
        # bash_gate.sh -> pretooluse_bash.py) that does NOT import
        # gh_issue_close_gate.py at all -- must be reported.
        home = os.path.expanduser("~")
        bash_gate = os.path.join(home, ".claude/hooks/bash_gate.sh")
        pretooluse = os.path.join(home, ".claude/hooks/pretooluse_bash.py")
        gicg = os.path.join(home, ".claude/hooks/gh_issue_close_gate.py")
        settings = _dispatcher_settings(f"bash {bash_gate}")
        settings["__allowlist__"] = _good_allowlist()
        module_sources = {
            bash_gate: 'python3 "$HOME/.claude/hooks/pretooluse_bash.py"\n',
            pretooluse: "import block_branch_ops as bbo\n",  # gh_issue_close_gate NOT imported
            gicg: '_lib.emit_pretooluse_deny("x")\n',
        }
        files = {bash_gate, pretooluse, gicg}
        problems = mod.check(settings, files, module_sources)
        assert any("gh_issue_close_gate.py" in p and "never wired" in p for p in problems)

    def test_blocker1_fix_gh_issue_close_gate_wired_is_clean(self):
        # Same shape, but pretooluse_bash.py DOES import it (the actual fix)
        # -> no guard-wiring problem.
        home = os.path.expanduser("~")
        bash_gate = os.path.join(home, ".claude/hooks/bash_gate.sh")
        pretooluse = os.path.join(home, ".claude/hooks/pretooluse_bash.py")
        gicg = os.path.join(home, ".claude/hooks/gh_issue_close_gate.py")
        settings = _dispatcher_settings(f"bash {bash_gate}")
        settings["__allowlist__"] = _good_allowlist()
        module_sources = {
            bash_gate: 'python3 "$HOME/.claude/hooks/pretooluse_bash.py"\n',
            pretooluse: "import gh_issue_close_gate as gicg\n",
            gicg: '_lib.emit_pretooluse_deny("x")\n',
        }
        files = {bash_gate, pretooluse, gicg}
        problems = mod.check(settings, files, module_sources)
        assert problems == []

    def test_non_dict_module_sources_skips_guard_wiring(self):
        settings = _dispatcher_settings("printf hi")
        settings["__allowlist__"] = _good_allowlist()
        assert mod.check(settings, set(), module_sources="not-a-dict") == []

    def test_real_runtime_has_no_guard_wiring_problems(self):
        """Live regression proof: run the check against the ACTUAL on-disk
        ~/.claude/hooks/*.py|*.sh content (not synthetic fixtures) and the
        REAL settings.json. This is the exact end state BLOCKER 1's fix
        produces -- if a future change ever ships a new guard-shaped module
        without wiring it in (or declaring it standalone), this test fails.

        UPDATED (2026-09-03, safety-gate-gap fix round): block_prod_mutations.py
        -- the last remaining KNOWN pre-existing gap this test used to carve out
        -- is now wired: settings.json's PreToolUse `mcp__playwright.*` matcher
        runs it as a second hook entry alongside `agent_budget.py browser_pool
        status` (it inspects `tool_input.url/method/body`, the exact shape a
        `browser_navigate`-style call carries; the pool-status hook never reads
        those fields, so the two do not conflict). pretooluse_task.py and
        model_pin_gate.py were wired the same round: settings.json's PreToolUse
        `Task` matcher now runs `pretooluse_task.py` (T1 model_pin_gate, T2 the
        unchanged agent_budget.py `gate`) in place of the previous direct
        `agent_budget.py gate` call. No carve-out remains -- the full guard
        closure must be clean.
        """
        settings = mod._load_json(mod._settings_path())
        if not isinstance(settings, dict):
            pytest.skip("no real ~/.claude/settings.json in this environment")
        allowlist = mod._load_json(mod._allowlist_path())
        settings = dict(settings)
        settings["__allowlist__"] = allowlist
        files = mod._existing_script_files()
        module_sources = mod._hook_module_sources()
        problems = mod.check(settings, files, module_sources)
        guard_wiring_problems = [p for p in problems if "never wired into any dispatcher" in p]
        assert guard_wiring_problems == [], f"unexpected unwired guard(s): {guard_wiring_problems}"
        dangling = [p for p in problems if "references missing script" in p]
        assert dangling == [], f"unexpected dangling script ref(s): {dangling}"

    def test_block_branch_ops_is_genuinely_reachable_in_the_real_wired_closure(self):
        """#4670 fix-round, Blocker 2: block_branch_ops.py implements
        gate 1 (the most load-bearing guard: state-verb/branch-op blocking)
        and is genuinely reachable -- settings.json wires bash_gate.sh ->
        pretooluse_bash.py, and pretooluse_bash.py `import`s block_branch_ops
        for its `decision()`/`_raw_mentions_git()`. An earlier round of this
        fix wrongly registered it in STANDALONE_GUARD_MODULES (declaring it
        "deliberately unreachable"), which would have permanently blinded
        this checker's "guard exists but is never wired" detection for gate 1
        specifically -- exactly the class of bug this feature exists to catch
        (see BLOCKER 1 / gh_issue_close_gate.py above). That registration was
        reverted; this test is the positive-reachability proof that makes the
        revert safe: it walks the REAL settings.json -> script -> python
        `import` closure this module actually computes (the same closure
        `check()` uses internally) and asserts block_branch_ops.py's own path
        is IN it -- strictly stronger than the removed exemption test, which
        only asserted a static declaration, never real reachability. If gate
        1 is ever accidentally unwired (e.g. pretooluse_bash.py's own import
        of block_branch_ops is removed or the bash_gate.sh -> pretooluse_bash
        chain breaks), this test fails loudly.
        """
        settings = mod._load_json(mod._settings_path())
        if not isinstance(settings, dict):
            pytest.skip("no real ~/.claude/settings.json in this environment")
        module_sources = mod._hook_module_sources()
        command_script_refs: list[str] = []
        for matchers in settings.get("hooks", {}).values():
            if not isinstance(matchers, list):
                continue
            for matcher in matchers:
                if not isinstance(matcher, dict):
                    continue
                for entry in matcher.get("hooks", []):
                    if not isinstance(entry, dict):
                        continue
                    command_script_refs.extend(mod.extract_script_refs(entry.get("command", "")))
        wired = mod.wired_module_paths(command_script_refs, module_sources)
        assert any(p.endswith("block_branch_ops.py") for p in wired), (
            "block_branch_ops.py is not reachable from the real settings.json "
            "dispatcher closure -- gate 1 would be unwired: " + repr(sorted(wired))
        )


# ===========================================================================
# IO adapters — _load_json / _gather / _existing_script_files.
# ===========================================================================


def test_load_json_absent_returns_none(sandbox):
    assert mod._load_json(str(sandbox.claude / "nope.json")) is None


def test_load_json_parses_object(runtime):
    obj = mod._load_json(str(runtime.settings_path))
    assert isinstance(obj, dict) and "hooks" in obj


def test_load_json_malformed_returns_sentinel(runtime):
    runtime.write_settings_raw("{ this is not json ")
    obj = mod._load_json(str(runtime.settings_path))
    assert isinstance(obj, dict) and "__parse_error__" in obj


def test_load_json_isfile_raises_returns_none(sandbox, monkeypatch):
    def boom(path):
        raise OSError("stat failed")

    monkeypatch.setattr(mod.os.path, "isfile", boom)
    assert mod._load_json(str(sandbox.claude / "settings.json")) is None


def test_existing_script_files_enumerates(runtime):
    found = mod._existing_script_files()
    for n in _WIRED_SCRIPTS:
        assert str(runtime.scripts / n) in found
    # hooks/*.py are included too.
    assert str(runtime.hooks / "check_safety_core_parity.py") in found


def test_existing_script_files_includes_hooks_sh_files(runtime):
    # Regression: hooks/*.sh (bash_gate.sh, post_bash_gate.sh in the real
    # runtime) were previously OMITTED from this oracle, which made
    # check_safety_core_parity flag its own real, existing wired scripts as
    # "missing" on every actual run (proven live before this fix: 2 false
    # positives for bash_gate.sh/post_bash_gate.sh under the shipped
    # settings.json). hooks/*.sh must be enumerated exactly like scripts/*.sh.
    (runtime.hooks / "bash_gate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    found = mod._existing_script_files()
    assert str(runtime.hooks / "bash_gate.sh") in found


def test_existing_script_files_missing_dirs_degrade(sandbox):
    # No scripts/ or hooks/ dirs created -> empty set, no raise.
    assert mod._existing_script_files() == set()


# ===========================================================================
# _hook_module_sources — the raw material for wired_module_paths / the
# guard-wiring check (spec item 4).
# ===========================================================================


def test_hook_module_sources_reads_py_and_sh(runtime):
    (runtime.hooks / "bash_gate.sh").write_text("echo hi\n")
    sources = mod._hook_module_sources()
    assert sources[str(runtime.hooks / "check_safety_core_parity.py")] == "# stub\n"
    assert sources[str(runtime.hooks / "bash_gate.sh")] == "echo hi\n"


def test_hook_module_sources_ignores_other_extensions(runtime):
    (runtime.hooks / "notes.md").write_text("not a hook\n")
    sources = mod._hook_module_sources()
    assert not any(p.endswith("notes.md") for p in sources)


def test_hook_module_sources_missing_dir_is_empty(sandbox):
    assert mod._hook_module_sources() == {}


def test_hook_module_sources_unreadable_file_is_skipped(runtime, monkeypatch):
    real_open = open

    def boom_open(path, *a, **k):
        if str(path).endswith("check_safety_core_parity.py"):
            raise OSError("permission denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", boom_open)
    sources = mod._hook_module_sources()
    assert not any(p.endswith("check_safety_core_parity.py") for p in sources)
    # the OTHER file is still readable and present:
    assert any(p.endswith("_lib.py") for p in sources)


def test_gather_merges_allowlist_under_reserved_key(runtime):
    merged = mod._gather(str(runtime.settings_path), str(runtime.allowlist_path))
    assert "hooks" in merged
    assert merged["__allowlist__"] == _good_allowlist()


def test_gather_settings_absent(sandbox):
    merged = mod._gather(str(sandbox.claude / "nope.json"), str(sandbox.claude / "nope2.json"))
    assert merged["__parse_error__"] == "settings.json absent"
    assert merged["__allowlist__"] is None


def test_gather_settings_parse_error_passthrough(runtime):
    runtime.write_settings_raw("{ broken ")
    merged = mod._gather(str(runtime.settings_path), str(runtime.allowlist_path))
    assert "__parse_error__" in merged


def test_gather_settings_non_dict_wrapped(runtime):
    runtime.write_settings_raw("[1, 2, 3]")  # valid JSON, but a list
    merged = mod._gather(str(runtime.settings_path), str(runtime.allowlist_path))
    assert merged["__parse_error__"] == "settings.json is not an object"
    assert merged["__allowlist__"] == _good_allowlist()


def test_summary_formats_problem_list():
    s = mod._summary(["problem A", "problem B"])
    assert "2 self-consistency problem(s)" in s
    assert "  - problem A" in s
    assert "  - problem B" in s


# ===========================================================================
# main() — thin adapter. LOG-ONLY unless enforcing; block via JSON; exit 0.
# ===========================================================================


def test_main_good_runtime_logs_ok_no_output(runtime, clean_env, monkeypatch, capsys):
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    assert capsys.readouterr().out == ""  # no block emitted
    rec = json.loads(
        runtime.settings_path.parent.joinpath(".enforcement", "log.jsonl")
        .read_text()
        .strip()
        .splitlines()[-1]
    )
    assert rec["hook"] == mod.HOOK_NAME
    assert rec["decision"] == "ok"


def test_main_drift_log_only_by_default(runtime, clean_env, monkeypatch, capsys, sandbox):
    # DRIFT: delete a wired script. Default (log-only) mode: log would-block, no
    # JSON block on stdout, exit 0.
    (runtime.scripts / "git_guard.sh").unlink()
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    assert capsys.readouterr().out == ""
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-block"
    assert rec["problem_count"] >= 1
    assert any("git_guard.sh" in p for p in rec["problems"])


def test_main_drift_enforce_emits_stop_block(runtime, clean_env, monkeypatch, capsys, sandbox):
    (runtime.scripts / "git_guard.sh").unlink()
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    out = capsys.readouterr().out
    obj = json.loads(out)
    assert obj["decision"] == "block"
    assert "git_guard.sh" in obj["reason"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "block"


def test_main_disabled_master_off_short_circuits(runtime, clean_env, monkeypatch, capsys, sandbox):
    # CSA_DISABLE_HOOKS=1: even with drift AND enforce, main no-ops (no log, no block).
    (runtime.scripts / "git_guard.sh").unlink()
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    assert capsys.readouterr().out == ""
    assert not sandbox.log_file.exists()


def test_main_allowlist_drift_enforce_blocks(runtime, clean_env, monkeypatch, capsys):
    # Remove a required allowlist key; enforce -> block names the key.
    allow = _good_allowlist()
    del allow["denied_action_patterns"]
    runtime.write_allowlist(allow)
    clean_env.setenv("CSA_ENFORCE", "1")
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["decision"] == "block"
    assert "denied_action_patterns" in obj["reason"]


def test_main_missing_allowlist_file_is_a_problem(runtime, clean_env, monkeypatch, sandbox):
    # Delete allowlist.json entirely: log-only would-block naming its absence.
    runtime.allowlist_path.unlink()
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-block"
    assert any("allowlist.json is absent" in p for p in rec["problems"])


def test_main_empty_stdin_uses_getcwd(runtime, clean_env, monkeypatch, sandbox):
    # No payload: read_event -> {} ; cwd falls back to getcwd. Good runtime -> ok.
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(_lib.sys, "stdin", io.StringIO(""))
    monkeypatch.chdir(runtime.claude)
    rc = mod.main()
    assert rc == 0
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "ok"


def test_main_degrades_open_on_internal_error(runtime, clean_env, monkeypatch, sandbox):
    # Force check() to raise; main must swallow, log an 'error' decision, exit 0.
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(mod, "check", boom)
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    rc = mod.main()
    assert rc == 0
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "error"


def test_main_error_path_swallows_log_failure(runtime, clean_env, monkeypatch):
    # Both check() AND the error-log raise: main still returns 0 (no crash out).
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(mod, "check", boom)
    monkeypatch.setattr(mod._lib, "log", boom)
    _feed_stdin(monkeypatch, {"tool_name": "Stop", "cwd": str(runtime.claude)})
    assert mod.main() == 0
