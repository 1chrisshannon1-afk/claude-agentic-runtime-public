"""Hermetic tests for hooks/pre_commit_ratchet.py.

Pure-function tests need no git at all. The main()-integration tests use the
shared `git_repo` fixture (a real, throwaway `git init`) and chdir into it, so
_find_repo_root's cwd-walk resolves to the sandbox repo, never the operator's
real ~/.claude.
"""

from __future__ import annotations

import json
import os

import pre_commit_ratchet as pcr
import sync_agent_rules as sar

GOOD_CONTRACT = """\
# Dev Runtime — Agent Operating Contract

Use the defined agents in `~/.claude/agents/` as written.

## 10. Review cadence
An Opus `plan-reviewer` reviews the plan. An Opus `code-reviewer` reviews the
diff.
"""


def _agent(name, model="sonnet", anchor=True):
    fm = f"---\nname: {name}\ndescription: does {name} things.\nmodel: {model}\n---\n"
    anchor_line = "You operate under `~/.claude/CLAUDE.md`.\n" if anchor else "No anchor.\n"
    return fm + anchor_line


def good_agents():
    return [
        # "opus" -- plan-reviewer's standing fable pin (card [87],
        # 2026-09-20) is RETIRED by operator directive 2026-09-24 ("change
        # all models pinned to fable to be pinned to opus (5.5)");
        # sync_agent_rules.FABLE_AGENTS is now empty, so "opus" is the
        # correct, clean pin -- exactly like every other OPUS_AGENTS member.
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", _agent("code-reviewer", model="opus", anchor=False)),  # baseline drift
        ("implement.md", _agent("implement", model="sonnet")),
    ]


# ===========================================================================
# check_settings_diff — pure.
# ===========================================================================


def test_missing_effort_level_blocks():
    blocking, warnings = pcr.check_settings_diff({}, {"model": "sonnet"})
    assert any("effortLevel' is absent" in b for b in blocking)


def test_xhigh_effort_blocks():
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"}, {"effortLevel": "xhigh", "model": "sonnet"}
    )
    assert any("xhigh" in b for b in blocking)


def test_high_effort_not_blocked():
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"}, {"effortLevel": "high", "model": "sonnet"}
    )
    assert blocking == []


def test_model_change_is_warning_not_blocking():
    blocking, warnings = pcr.check_settings_diff(
        {"model": "sonnet", "effortLevel": "high"},
        {"model": "opus", "effortLevel": "high"},
    )
    assert blocking == []
    assert any("'model' changed 'sonnet' -> 'opus'" in w for w in warnings)


def test_model_unchanged_no_warning():
    blocking, warnings = pcr.check_settings_diff(
        {"model": "sonnet", "effortLevel": "high"},
        {"model": "sonnet", "effortLevel": "high"},
    )
    assert warnings == []


def test_new_file_before_none_only_assesses_after():
    blocking, warnings = pcr.check_settings_diff(None, {"model": "sonnet", "effortLevel": "xhigh"})
    assert any("xhigh" in b for b in blocking)
    assert warnings == []  # no "before" to diff model against


def test_both_none_no_crash_no_findings():
    blocking, warnings = pcr.check_settings_diff(None, None)
    # after={} has no effortLevel -> the absent-key block still fires; this is
    # correct (an empty/unreadable settings.json is not silently accepted).
    assert isinstance(blocking, list) and isinstance(warnings, list)


# ---------------------------------------------------------------------------
# Nested modelSettings.<model>.effortLevel == "xhigh" -- the client-written
# form the top-level check above never sees (2026-09-20 plan, F6).
# ---------------------------------------------------------------------------


def test_nested_modelsettings_xhigh_one_model_blocks():
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {
            "effortLevel": "high",
            "modelSettings": {"claude-opus-5": {"effortLevel": "xhigh"}},
        },
    )
    assert any("xhigh" in b and "claude-opus-5" in b for b in blocking)


def test_nested_modelsettings_xhigh_two_models_names_both():
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {
            "effortLevel": "high",
            "modelSettings": {
                "claude-fable-5-1": {"effortLevel": "xhigh"},
                "claude-opus-5": {"effortLevel": "xhigh"},
            },
        },
    )
    assert len(blocking) == 1
    assert "claude-fable-5-1" in blocking[0]
    assert "claude-opus-5" in blocking[0]


def test_nested_modelsettings_high_not_blocked():
    # Paired recovery: the same shape, but "high" instead of "xhigh", must
    # commit cleanly -- this is the case a false-positive fix would break.
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {
            "effortLevel": "high",
            "modelSettings": {
                "claude-fable-5-1": {"effortLevel": "high"},
                "claude-opus-5": {"effortLevel": "medium"},
            },
        },
    )
    assert blocking == []


def test_nested_modelsettings_malformed_shapes_never_crash_or_false_flag():
    # A string value for modelSettings.
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {"effortLevel": "high", "modelSettings": "not-a-dict"},
    )
    assert blocking == []

    # A list value for modelSettings.
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {"effortLevel": "high", "modelSettings": ["claude-opus-5"]},
    )
    assert blocking == []

    # A per-model entry that is not itself a dict (e.g. a bare string).
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {
            "effortLevel": "high",
            "modelSettings": {"claude-opus-5": "xhigh"},
        },
    )
    assert blocking == []

    # modelSettings absent entirely -- the ordinary, common case.
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"}, {"effortLevel": "high"}
    )
    assert blocking == []


def test_nested_modelsettings_xhigh_does_not_affect_top_level_check():
    # The pre-existing top-level behavior (F13/plan F6 "same style") is
    # unchanged: a clean top-level effortLevel alongside a dirty nested one
    # still blocks (on the nested finding), and a dirty top-level alongside a
    # clean nested one still blocks (on the top-level finding) -- the two
    # checks are independent, not a replacement of one by the other.
    blocking, _ = pcr.check_settings_diff(
        {"effortLevel": "high"},
        {
            "effortLevel": "xhigh",
            "modelSettings": {"claude-opus-5": {"effortLevel": "high"}},
        },
    )
    assert len(blocking) == 1
    assert "'effortLevel' is 'xhigh'" in blocking[0]
    assert "modelSettings" not in blocking[0]


# ===========================================================================
# check_roster_diff — pure, delegates to sync_agent_rules.
# ===========================================================================


def test_roster_with_only_baseline_drift_is_clean():
    assert pcr.check_roster_diff(GOOD_CONTRACT, good_agents()) == []


def test_roster_new_worker_model_drift_is_caught():
    agents = good_agents() + [("rogue.md", _agent("rogue", model="opus"))]
    findings = pcr.check_roster_diff(GOOD_CONTRACT, agents)
    assert any("worker-model-drift" in f or "rogue.md" in f for f in findings)


def test_roster_baseline_drift_alone_does_not_double_count():
    # Sanity: the accepted baseline problem must match exactly what
    # sync_agent_rules actually emits for this fixture, or this test (and the
    # ratchet) would silently stop filtering it.
    problems = sar.check_consistency(GOOD_CONTRACT, good_agents())
    assert pcr._ACCEPTED_BASELINE_DRIFT in problems


# ===========================================================================
# main() — real git plumbing against a throwaway repo.
# ===========================================================================


def _init_good_repo(git_repo, monkeypatch):
    (git_repo / "CLAUDE.md").write_text(GOOD_CONTRACT)
    agents_dir = git_repo / "agents"
    agents_dir.mkdir()
    for name, text in good_agents():
        (agents_dir / name).write_text(text)
    settings = {"model": "sonnet", "effortLevel": "high"}
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    monkeypatch.chdir(git_repo)
    _git_commit_all(git_repo, "initial good state")
    return settings


def _git(git_repo, *args):
    import subprocess

    subprocess.run(["git", "-C", str(git_repo), *args], capture_output=True, text=True, check=True)


def _git_commit_all(git_repo, message):
    _git(git_repo, "add", "-A")
    _git(
        git_repo,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "commit",
        "-q",
        "-m",
        message,
    )


def test_main_clean_state_exits_zero(git_repo, monkeypatch, clean_env):
    _init_good_repo(git_repo, monkeypatch)
    assert pcr.main() == 0


def test_main_blocks_on_xhigh_regression(git_repo, monkeypatch, clean_env, capsys):
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["effortLevel"] = "xhigh"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    assert pcr.main() == 1
    err = capsys.readouterr().err
    assert "xhigh" in err


def test_main_escape_hatch_allows_xhigh(git_repo, monkeypatch, clean_env):
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["effortLevel"] = "xhigh"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    monkeypatch.setenv(pcr.ESCAPE_HATCH_VAR, "1")
    assert pcr.main() == 0


def test_main_disable_hooks_short_circuits(git_repo, monkeypatch, clean_env):
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["effortLevel"] = "xhigh"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    assert pcr.main() == 0


def test_main_blocks_on_new_unpinned_agent(git_repo, monkeypatch, clean_env, capsys):
    _init_good_repo(git_repo, monkeypatch)
    (git_repo / "agents" / "rogue.md").write_text(_agent("rogue", model="opus"))
    _git(git_repo, "add", "agents/rogue.md")
    assert pcr.main() == 1
    err = capsys.readouterr().err
    assert "rogue.md" in err


def test_main_model_change_warns_but_does_not_block(git_repo, monkeypatch, clean_env, capsys):
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["model"] = "opus"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    assert pcr.main() == 0
    err = capsys.readouterr().err
    assert "WARN" in err and "model" in err


def test_main_roster_checked_even_on_unrelated_commit(git_repo, monkeypatch, clean_env):
    # staged_agent_files() always includes every agents/*.md committed at HEAD
    # (falling back to the committed blob for ones this commit doesn't touch),
    # so roster consistency is a standing invariant checked on every commit,
    # not just ones that happen to touch agents/. A clean roster + an unrelated
    # staged file must still pass.
    _init_good_repo(git_repo, monkeypatch)
    (git_repo / "README.md").write_text("unrelated\n")
    _git(git_repo, "add", "README.md")
    assert pcr.main() == 0


def test_main_preexisting_drift_caught_via_unrelated_commit(git_repo, monkeypatch, clean_env, capsys):
    # Because the roster check always includes HEAD's committed agents/*.md,
    # introducing bad drift straight into HEAD (bypassing this hook, as if an
    # older commit predates the ratchet) is still caught on the NEXT commit,
    # even one that only touches an unrelated file.
    _init_good_repo(git_repo, monkeypatch)
    (git_repo / "agents" / "rogue.md").write_text(_agent("rogue", model="opus"))
    _git(git_repo, "add", "agents/rogue.md")
    _git(
        git_repo,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "commit",
        "-q",
        "-m",
        "bypassed the hook somehow",
    )
    (git_repo / "README.md").write_text("unrelated\n")
    _git(git_repo, "add", "README.md")
    assert pcr.main() == 1
    err = capsys.readouterr().err
    assert "rogue.md" in err


def test_main_outside_git_repo_is_noop(tmp_path, monkeypatch, clean_env):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    monkeypatch.chdir(not_a_repo)
    assert pcr.main() == 0


# ===========================================================================
# check_workflow_agent_purity — pure, delegates to
# check_workflow_agent_purity.check_file.
# ===========================================================================

_BAD_WORKFLOW_SOURCE = (
    "agent(`x`, { label: 'x', model: 'sonnet', agentType: 'explore' })\n"
    "// somewhere this file also calls record_review\n"
    "const x = record_review\n"
)

_GOOD_WORKFLOW_SOURCE = "agent(`x`, { label: 'x', model: 'sonnet', agentType: 'explore' })\n"


def test_check_workflow_agent_purity_pure_flags_bad_content():
    def fake_staged_blob(repo, path):
        return _BAD_WORKFLOW_SOURCE

    import pre_commit_ratchet as pcr_mod

    original = pcr_mod.staged_blob
    pcr_mod.staged_blob = fake_staged_blob
    try:
        failures = pcr.check_workflow_agent_purity("/fake/repo", ["workflows/issue-wheel-triage.js"])
    finally:
        pcr_mod.staged_blob = original
    assert any("record_review" in f for f in failures)


def test_check_workflow_agent_purity_pure_clean_content_is_clean():
    def fake_staged_blob(repo, path):
        return _GOOD_WORKFLOW_SOURCE

    import pre_commit_ratchet as pcr_mod

    original = pcr_mod.staged_blob
    pcr_mod.staged_blob = fake_staged_blob
    try:
        failures = pcr.check_workflow_agent_purity("/fake/repo", ["workflows/issue-wheel-triage.js"])
    finally:
        pcr_mod.staged_blob = original
    assert failures == []


def test_check_workflow_agent_purity_skips_unresolvable_staged_blob():
    def fake_staged_blob(repo, path):
        return None  # e.g. a staged deletion -- nothing to check

    import pre_commit_ratchet as pcr_mod

    original = pcr_mod.staged_blob
    pcr_mod.staged_blob = fake_staged_blob
    try:
        failures = pcr.check_workflow_agent_purity("/fake/repo", ["workflows/issue-wheel-triage.js"])
    finally:
        pcr_mod.staged_blob = original
    assert failures == []


# ===========================================================================
# main() — the ratchet's new third block, hermetically against a throwaway
# repo. Never touches the real ~/.claude tree.
# ===========================================================================


def _stage_workflow_file(git_repo, relative_path, content):
    workflows_dir = git_repo / os.path.dirname(relative_path)
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (git_repo / relative_path).write_text(content)
    _git(git_repo, "add", relative_path)


def test_main_blocks_on_wheel_workflow_forbidden_content(git_repo, monkeypatch, clean_env, capsys):
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    assert pcr.main() == 1
    err = capsys.readouterr().err
    assert "record_review" in err


def test_main_does_not_fire_on_non_wheel_workflow_file(git_repo, monkeypatch, clean_env):
    # A commit touching workflows/deliver.js alone must never reach
    # check_workflow_agent_purity -- the block's own filename-prefix filter
    # is the mechanism that guarantees this, proven here by construction: the
    # staged file contains exactly the same forbidden content the RED test
    # above uses, but under a name the filter does not match, so main() must
    # still exit clean.
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/deliver.js", _BAD_WORKFLOW_SOURCE)
    assert pcr.main() == 0


def test_main_wheel_workflow_prefilter_excludes_deliver_js_by_name():
    # Direct proof (not inference from main()'s exit code alone) that the
    # ratchet's own wheel_workflow_files filter -- reproduced here exactly as
    # it is written in main() -- excludes workflows/deliver.js from the list
    # of files ever passed to check_workflow_agent_purity.
    touched = "workflows/deliver.js\nworkflows/issue-wheel-triage.js\nagents/rogue.md\n"
    wheel_workflow_files = [
        line.strip() for line in touched.splitlines()
        if line.strip().startswith("workflows/issue-wheel-") and line.strip().endswith(".js")
    ]
    assert wheel_workflow_files == ["workflows/issue-wheel-triage.js"]
    assert "workflows/deliver.js" not in wheel_workflow_files


def test_main_wheel_workflow_general_escape_hatch_no_longer_waives_purity(
    git_repo, monkeypatch, clean_env
):
    # THE ISSUE WHEEL hardening plan, H5: the general ESCAPE_HATCH_VAR
    # (CSA_ALLOW_EXPENSIVE_DEFAULT) used to waive a purity finding too, since
    # `blocking` was one flat, undiscriminated list. Post-H5 it must NOT --
    # only the purity-specific door below can. This is the direct successor
    # of the old test_main_wheel_workflow_escape_hatch_allows_bad_content,
    # whose assertion (main() == 0 under the general hatch) is exactly the
    # behavior H5 revokes.
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    monkeypatch.setenv(pcr.ESCAPE_HATCH_VAR, "1")
    assert pcr.main() == 1


def test_main_wheel_workflow_disable_hooks_no_longer_waives_purity(git_repo, monkeypatch, clean_env):
    # H5: CSA_DISABLE_HOOKS=1 used to short-circuit BEFORE the purity check
    # ever ran, so it silently waived a purity finding as a side effect of
    # skipping everything else. Post-H5 the purity check runs regardless --
    # CSA_DISABLE_HOOKS still short-circuits every OTHER check unchanged
    # (proven separately by test_main_disable_hooks_short_circuits above).
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    assert pcr.main() == 1


def test_main_wheel_workflow_both_general_hatches_set_still_blocks(git_repo, monkeypatch, clean_env, capsys):
    # Chaos-gate row 5 / acceptance A4: an impure workflow is blocked
    # regardless of any single escape-hatch env var -- including BOTH of the
    # general ones set simultaneously, so long as the purity-specific door
    # is not.
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    monkeypatch.setenv(pcr.ESCAPE_HATCH_VAR, "1")
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    assert pcr.main() == 1
    err = capsys.readouterr().err
    assert "record_review" in err


def test_main_wheel_workflow_purity_specific_hatch_allows_bad_content(git_repo, monkeypatch, clean_env):
    # GREEN: the named, purity-specific door still exists for a genuine
    # emergency -- greppable and auditable, distinct from the general hatch.
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    monkeypatch.setenv(pcr.PURITY_ESCAPE_HATCH_VAR, "1")
    assert pcr.main() == 0


def test_main_wheel_workflow_purity_hatch_does_not_waive_unrelated_settings_block(
    git_repo, monkeypatch, clean_env
):
    # The purity-specific hatch is scoped narrowly too: it must not become a
    # new blanket waiver for an unrelated (non-purity) finding, mirroring the
    # scoping the general hatch already had before H5. A commit with both an
    # xhigh settings regression AND a clean workflow file must still block on
    # the settings finding even with the purity hatch set.
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["effortLevel"] = "xhigh"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    monkeypatch.setenv(pcr.PURITY_ESCAPE_HATCH_VAR, "1")
    assert pcr.main() == 1


def test_main_wheel_workflow_clean_content_passes(git_repo, monkeypatch, clean_env):
    _init_good_repo(git_repo, monkeypatch)
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _GOOD_WORKFLOW_SOURCE)
    assert pcr.main() == 0


def test_main_purity_hatch_does_not_waive_concurrent_settings_finding(
    git_repo, monkeypatch, clean_env, capsys
):
    # F3 (THE ISSUE WHEEL hardening plan, H5 review): the untested combination
    # -- a purity finding AND a non-purity (settings) finding BOTH present in
    # the same commit, with ONLY the purity-specific hatch set. The existing
    # test_main_wheel_workflow_purity_hatch_does_not_waive_unrelated_settings_block
    # above never actually stages a purity violation (its workflow content is
    # clean), so it never exercises this discrimination with both finding
    # classes live at once. This test does: both findings are genuinely
    # present, and only PURITY_ESCAPE_HATCH_VAR is set, so the commit must
    # still block -- on the settings finding, which the purity hatch was never
    # meant to touch.
    settings = _init_good_repo(git_repo, monkeypatch)
    settings["effortLevel"] = "xhigh"
    (git_repo / "settings.json").write_text(json.dumps(settings, indent=2))
    _git(git_repo, "add", "settings.json")
    _stage_workflow_file(git_repo, "workflows/issue-wheel-triage.js", _BAD_WORKFLOW_SOURCE)
    monkeypatch.setenv(pcr.PURITY_ESCAPE_HATCH_VAR, "1")
    assert pcr.main() == 1
    err = capsys.readouterr().err
    # Both findings are reported as blocking regardless of the purity hatch --
    # main() only prints the "allowed through anyway" messages once EVERY
    # blocking class is cleared (purity_cleared AND other_cleared); here
    # other_cleared is False (no ESCAPE_HATCH_VAR set), so neither
    # "set -- allowing" message fires and the commit blocks outright, citing
    # the still-unwaived settings finding.
    assert "record_review" in err  # the purity finding is still listed...
    assert "xhigh" in err  # ...alongside the settings finding, both blocking
    assert f"{pcr.PURITY_ESCAPE_HATCH_VAR}=1 set -- allowing" not in err
    assert f"{pcr.ESCAPE_HATCH_VAR}=1 set -- allowing" not in err
    # The printed remediation hint names the general hatch for the settings
    # finding, confirming it -- not the purity hatch -- is what's still needed.
    assert f"set {pcr.ESCAPE_HATCH_VAR}=1 for this one commit" in err
