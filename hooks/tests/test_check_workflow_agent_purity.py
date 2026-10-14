"""Tests for hooks/check_workflow_agent_purity.py — RULE G2 mechanical checker
for THE ISSUE WHEEL (plan: issue_wheel_consolidation.md section 3).

Pure-function tests need no filesystem at all (check_source). CLI/discovery
tests use tmp_path so the real ~/.claude/workflows/ is never touched by a
test glob.
"""

from __future__ import annotations

import os

import check_workflow_agent_purity as cwap


def _agent_call(agent_type="explore", model="sonnet", label="x"):
    return (
        f"agent(`some prompt`, "
        f"{{ label: '{label}', phase: 'Triage', model: '{model}', agentType: '{agent_type}' }})"
    )


# ===========================================================================
# check_source — pure, forbidden substrings.
# ===========================================================================


def test_clean_source_no_failures():
    src = _agent_call()
    assert cwap.check_source(src) == []


def test_forbidden_substring_record_review_fails():
    src = _agent_call() + "\n// touches record_review somehow\nconst x = record_review\n"
    failures = cwap.check_source(src, label="workflows/issue-wheel-triage.js")
    assert any("record_review" in f for f in failures)


def test_all_eight_forbidden_substrings_detected():
    needles = [
        "record_review",
        "gh_issue.sh",
        "gh issue close",
        "file_claims",
        "git commit",
        "execSync",
        "spawnSync",
        "require('child_process')",
    ]
    for needle in needles:
        src = _agent_call() + f"\nconst danger = {needle!r}\n"
        failures = cwap.check_source(src)
        assert any(needle in f for f in failures), f"expected a failure mentioning {needle!r}, got {failures}"


def test_forbidden_substring_inside_comment_still_fails():
    # RULE G1(b) is a whole-file substring check, deliberately -- unlike the
    # agentType check below, a Workflow script can never legitimately
    # reference any of these strings at all, not even in a comment.
    src = _agent_call() + "\n// do not call git commit here\n"
    failures = cwap.check_source(src)
    assert any("git commit" in f for f in failures)


# ===========================================================================
# check_source — parsed agentType, never a raw substring match.
# ===========================================================================


def test_forbidden_agent_type_code_reviewer_fails():
    src = _agent_call(agent_type="code-reviewer")
    failures = cwap.check_source(src)
    assert any("code-reviewer" in f for f in failures)


def test_all_five_forbidden_agent_types_detected():
    for agent_type in ("code-reviewer", "trust-architect", "plan-reviewer", "implement", "test-writer"):
        src = _agent_call(agent_type=agent_type)
        failures = cwap.check_source(src)
        assert any(agent_type in f for f in failures), f"expected {agent_type!r} to be flagged, got {failures}"


def test_allowed_agent_type_explore_is_clean():
    src = _agent_call(agent_type="explore")
    assert cwap.check_source(src) == []


def test_agent_type_mentioned_in_comment_does_not_false_positive():
    # The plan is explicit: a raw substring match over the whole file would
    # false-positive on a comment or prompt string containing one of these
    # words. Only a PARSED call-site's agentType value counts.
    src = _agent_call(agent_type="explore") + "\n// never use agentType: 'implement' here\n"
    failures = cwap.check_source(src)
    assert failures == []


def test_agent_type_mentioned_in_prompt_string_does_not_false_positive():
    src = (
        "agent(`Never behave like a code-reviewer or an implement agent.`, "
        "{ label: 'x', model: 'sonnet', agentType: 'explore' })"
    )
    failures = cwap.check_source(src)
    assert failures == []


def test_agent_type_mentioned_in_prompt_string_does_not_mask_a_real_forbidden_agent_type():
    """code-reviewer blocker: the REVERSE direction of the two tests above --
    a prompt string mentioning a LEGITIMATE agentType (e.g. quoting the
    dispatch's own read-only role) must never mask a genuinely forbidden
    agentType sitting in the real options object. Reproduces the exact
    masking payload the review demonstrated: searching the whole call span
    finds the prompt's own mention of 'explore' first and never reaches the
    real options object's 'implement'."""
    src = (
        "agent(`YOUR ROLE THIS ROUND: triage a batch of issues.\n"
        "Do not behave like an implementer. Your dispatch uses agentType: 'explore'\n"
        "so you are read-only.`,\n"
        "  { label: 'triage', model: 'sonnet', agentType: 'implement' })"
    )
    failures = cwap.check_source(src)
    assert any("implement" in f for f in failures), (
        f"expected a forbidden-agentType failure naming 'implement', got: {failures}"
    )


def test_model_mentioned_in_prompt_string_does_not_mask_a_missing_real_model_key():
    """Same masking class, for the model-pin check: a prompt string
    mentioning 'model:' in prose must never satisfy the missing-model-key
    check when the REAL options object has no model key at all."""
    src = "agent(`use model: 'opus' maybe`, { agentType: 'explore' })"
    failures = cwap.check_source(src)
    assert any("model" in f for f in failures), (
        f"expected a missing-model failure, got: {failures}"
    )


def test_nested_object_literal_inside_options_does_not_mask_forbidden_agent_type():
    """code-reviewer round-2 blocker: the blocker-1 fix itself introduced a
    NEW false negative -- _extract_trailing_options_object's first pass
    tracked PAREN depth only, so a `{` nested inside an earlier top-level
    object (an inline `schema: {...}` argument, exactly how deliver.js and
    every generic Workflow example write these calls) was wrongly recorded
    as its own 'top-level' brace, and the extractor returned that INNER
    object instead of the real options object. Reproduces the review's
    exact false-negative payload: a genuinely forbidden agentType sitting
    right next to an inline schema object must still be caught."""
    src = "agent(`x`, { agentType: 'implement', schema: { model: 'sonnet' } })"
    failures = cwap.check_source(src)
    assert any("implement" in f for f in failures), (
        f"expected a forbidden-agentType failure naming 'implement', got: {failures}"
    )


def test_inline_schema_object_does_not_break_correct_parsing_of_model_and_agent_type():
    """Sibling of the test above, checking the POSITIVE case: an options
    object containing a nested `schema: {...}` literal must still parse its
    OWN model/agentType correctly (not just detect the violation -- a
    legitimate, compliant call using an inline schema must not be
    mis-flagged either)."""
    src = "agent(`x`, { model: 'sonnet', agentType: 'explore', schema: { type: 'object', properties: { a: { type: 'string' } } } })"
    failures = cwap.check_source(src)
    assert failures == [], f"expected a clean pass, got: {failures}"


# ===========================================================================
# check_source — missing model.
# ===========================================================================


def test_missing_model_key_fails():
    src = "agent(`prompt`, { label: 'x', agentType: 'explore' })"
    failures = cwap.check_source(src)
    assert any("model" in f for f in failures)


def test_empty_model_value_fails():
    src = "agent(`prompt`, { label: 'x', agentType: 'explore', model: '' })"
    failures = cwap.check_source(src)
    assert any("model" in f for f in failures)


def test_model_present_is_clean():
    src = _agent_call(model="sonnet")
    assert cwap.check_source(src) == []


# ===========================================================================
# check_source — model VALUE allowlist, not just presence (#5161a / H4a).
#
# Falsifiable test per the plan (issue_wheel_consolidation hardening plan,
# H4a): RED -- model:'opus' and model:'haiku' both pass check_source() today.
# GREEN -- both produce a finding; model:'sonnet' still passes clean
# (regression guard). Confirmed by direct execution against the pre-fix
# checked-in HEAD revision of check_workflow_agent_purity.py (via `git show
# HEAD:hooks/check_workflow_agent_purity.py`) that opus/haiku both returned
# [] there -- these tests reproduce that exact real prior gap, not a
# synthetic condition that was already caught.
# ===========================================================================


def test_model_opus_is_not_allowlisted():
    src = _agent_call(model="opus")
    failures = cwap.check_source(src)
    assert any("opus" in f for f in failures), (
        f"expected a failure naming the disallowed model 'opus', got: {failures}"
    )


def test_model_haiku_is_not_allowlisted():
    src = _agent_call(model="haiku")
    failures = cwap.check_source(src)
    assert any("haiku" in f for f in failures), (
        f"expected a failure naming the disallowed model 'haiku', got: {failures}"
    )


def test_model_sonnet_still_clean_regression_guard():
    # Regression guard named explicitly in the plan's GREEN spec: the value
    # allowlist must not collaterally break the one legitimate value.
    src = _agent_call(model="sonnet")
    assert cwap.check_source(src) == []


def test_disallowed_model_failure_is_distinct_from_missing_model_failure():
    # The missing-model-key finding and the wrong-model-value finding are
    # different failure reasons (per this module's own docstring/comments)
    # and must remain distinguishable -- a caller reading the failure text
    # can tell "no model:" apart from "model: set to something not allowed".
    missing = cwap.check_source("agent(`x`, { agentType: 'explore' })")
    wrong_value = cwap.check_source(_agent_call(model="opus"))
    assert any("no literal" in f for f in missing)
    assert not any("no literal" in f for f in wrong_value)
    assert any("opus" in f for f in wrong_value)


# ===========================================================================
# find_agent_call_sites — balanced parens + string-literal handling.
# ===========================================================================


def test_paren_inside_prompt_string_does_not_truncate_call():
    src = (
        "agent(`a prompt with a stray ) inside it`, "
        "{ label: 'x', model: 'sonnet', agentType: 'explore' })"
    )
    sites = cwap.find_agent_call_sites(src)
    assert len(sites) == 1
    assert sites[0].model == "sonnet"
    assert sites[0].agent_type == "explore"


def test_multiple_call_sites_all_found():
    src = "\n".join(_agent_call(label=f"call{i}") for i in range(3))
    sites = cwap.find_agent_call_sites(src)
    assert len(sites) == 3


def test_agent_word_in_comment_is_not_a_call_site():
    # Regression: `agent()` mentioned in a // comment (e.g. documentation
    # describing the primitive) must never be parsed as a real call site.
    src = "// this script fans out via the in-script agent() primitive\n" + _agent_call()
    sites = cwap.find_agent_call_sites(src)
    assert len(sites) == 1


def test_agent_word_in_block_comment_is_not_a_call_site():
    src = "/* the agent() primitive is bounded */\n" + _agent_call()
    sites = cwap.find_agent_call_sites(src)
    assert len(sites) == 1


def test_agent_budget_or_property_access_not_matched():
    src = "agent_budget.gate()\nsomething.agent(1)\n" + _agent_call()
    sites = cwap.find_agent_call_sites(src)
    assert len(sites) == 1


# ===========================================================================
# check_file / inventory_lines — labeled wrappers.
# ===========================================================================


def test_check_file_labels_failures_with_path():
    failures = cwap.check_file("workflows/issue-wheel-triage.js", "agent(`x`, {agentType:'implement', model:'sonnet'})")
    assert any("workflows/issue-wheel-triage.js" in f for f in failures)


def test_inventory_lines_reports_every_call_and_model():
    src = "\n".join(_agent_call(label=f"c{i}", model="sonnet") for i in range(2))
    lines = cwap.inventory_lines("x.js", src)
    joined = "\n".join(lines)
    assert "2 agent() call site(s)" in joined
    assert "model='sonnet'" in joined


def test_inventory_lines_no_calls_still_reports_something():
    lines = cwap.inventory_lines("x.js", "const x = 1;")
    assert lines and "no agent() call sites found" in lines[0]


# ===========================================================================
# discover_wheel_workflow_files — filename-pattern scoping, never the whole dir.
# ===========================================================================


def test_discover_only_matches_issue_wheel_pattern(tmp_path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "issue-wheel-triage.js").write_text(_agent_call())
    (workflows_dir / "deliver.js").write_text(_agent_call(agent_type="code-reviewer"))
    (workflows_dir / "issue-wheel-other.js").write_text(_agent_call())

    found = cwap.discover_wheel_workflow_files(str(workflows_dir))
    basenames = sorted(os.path.basename(p) for p in found)
    assert basenames == ["issue-wheel-other.js", "issue-wheel-triage.js"]
    assert "deliver.js" not in basenames


def test_discover_empty_dir_returns_empty(tmp_path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    assert cwap.discover_wheel_workflow_files(str(workflows_dir)) == []


# ===========================================================================
# main() — CLI shape: explicit paths vs. no-arg glob discovery.
# ===========================================================================


def test_main_explicit_path_clean_file_exits_zero(tmp_path, capsys):
    f = tmp_path / "issue-wheel-x.js"
    f.write_text(_agent_call())
    assert cwap.main([str(f)]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert "agentType='explore'" in out


def test_main_explicit_path_violating_file_exits_nonzero(tmp_path, capsys):
    f = tmp_path / "issue-wheel-x.js"
    f.write_text("agent(`x`, {agentType:'implement', model:'sonnet'})")
    assert cwap.main([str(f)]) == 1
    err = capsys.readouterr().err
    assert "implement" in err


def test_main_no_args_globs_real_wheel_workflow_dir():
    # No explicit args -> glob ~/.claude/workflows/issue-wheel-*.js on disk.
    # Just assert it runs and returns an int without raising; the real file's
    # own content is asserted clean by test_real_issue_wheel_triage_js_is_clean
    # below via an explicit path, which is the acceptance-assertion form.
    result = cwap.main([])
    assert isinstance(result, int)


def test_main_missing_file_reports_failure_not_crash(tmp_path, capsys):
    missing = tmp_path / "issue-wheel-does-not-exist.js"
    assert cwap.main([str(missing)]) == 1
    err = capsys.readouterr().err
    assert "could not read file" in err


# ===========================================================================
# Acceptance assertion 6 (plan section 4): the REAL shipped workflow file
# passes cleanly with a printed inventory.
# ===========================================================================


def test_real_issue_wheel_triage_js_is_clean(capsys):
    real_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "workflows",
        "issue-wheel-triage.js",
    )
    assert os.path.isfile(real_path), f"expected {real_path} to exist"
    assert cwap.main([real_path]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert "agent() call site(s)" in out


def test_real_deliver_js_is_never_touched_by_no_arg_discovery():
    # deliver.js legitimately uses code-reviewer/plan-reviewer/implement --
    # discover_wheel_workflow_files's filename-pattern glob must never surface
    # it, which is the actual protection (not this module choosing to be
    # lenient on that file).
    found = cwap.discover_wheel_workflow_files()
    basenames = [os.path.basename(p) for p in found]
    assert "deliver.js" not in basenames
