"""Hermetic tests for hooks/sync_agent_rules.py.

The PORT-FROM source is the operating contract itself (~/.claude/CLAUDE.md): the
contract IS the spec, so its invariants are the test vectors. We reproduce each
contract/agent consistency invariant as a case (a CONSISTENT fixture pair yields
no problems; each way an agent can DRIFT from the contract yields exactly the
right problem code), then expand to the frontmatter parser, the IO loader, and
the full main() decision matrix (clean / would-block / block / disabled / error).

Every test runs against the `sandbox` fixture ($HOME + _lib path constants
pointed into a tmp dir) so the real ~/.claude, its agents, and its enforcement
log are never touched. No network, no real git.
"""

from __future__ import annotations

import io
import json
import os

import _lib
import pytest
import sync_agent_rules as sar

# ===========================================================================
# Realistic fixtures mirroring the live runtime — the CONSISTENT baseline.
# ===========================================================================

# A minimal but faithful contract: names the two Opus review agents in backticks,
# declares the CSA_* switch names, and references the scripts/*.sh helpers — the
# exact facts the validator cross-checks the agents against.
GOOD_CONTRACT = """\
# Dev Runtime — Agent Operating Contract

Use the defined agents in `~/.claude/agents/` as written.

## 7. Git discipline
`~/.claude/scripts/git_guard.sh` is the enforcer. `CSA_ENFORCE=1` turns real
blocking on; `CSA_DISABLE_HOOKS=1` is the master kill-switch.

## 8. Issues
Use `~/.claude/scripts/gh_issue.sh` with create / transition / resolve.

## 9. Concurrency
Consult `~/.claude/scripts/agent_budget.sh` before a large fan-out.

## 10. Review cadence
An Opus `plan-reviewer` reviews the plan. An Opus `code-reviewer` reviews the
diff. `CSA_SKIP_REVIEW=1` lets one turn end without a re-fire.
"""


def _agent(name, model="sonnet", anchor=True, body="Standard body.", extra_frontmatter=""):
    """Build a well-formed agent-def markdown string."""
    fm = f"---\nname: {name}\ndescription: does {name} things.\nmodel: {model}\n"
    if extra_frontmatter:
        fm += extra_frontmatter.rstrip("\n") + "\n"
    fm += "---\n"
    anchor_line = "You operate under `~/.claude/CLAUDE.md`.\n" if anchor else "No anchor here.\n"
    return fm + "\n" + anchor_line + body + "\n"


def good_agents():
    """A consistent roster: both Opus review agents present + anchored, plus a
    couple of sonnet workers. Mirrors the real agents/ layout.

    plan-reviewer was pinned "fable" from 2026-09-20 (card [87]) until the
    operator directive of 2026-09-24 ("change all models pinned to fable to
    be pinned to opus (5.5)") retired every standing fable pin, including
    this one. FABLE_AGENTS is now empty, so "opus" is the correct, clean pin
    for plan-reviewer -- exactly like every other OPUS_AGENTS member.
    """
    return [
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", _agent("code-reviewer", model="opus")),
        ("implement.md", _agent("implement", model="sonnet")),
        ("git-ops.md", _agent("git-ops", model="sonnet")),
    ]


# ===========================================================================
# THE SPEC VECTOR: a consistent contract + roster has ZERO problems.
# ===========================================================================


def test_consistent_contract_and_agents_no_problems():
    assert sar.check_consistency(GOOD_CONTRACT, good_agents()) == []


def test_empty_agents_only_flags_missing_review_agents():
    # With no agent files at all, the only problems are the two required review
    # agents the contract hard-depends on being absent.
    problems = sar.check_consistency(GOOD_CONTRACT, [])
    kinds = sorted(p.kind for p in problems)
    assert kinds == ["referenced-agent-missing", "referenced-agent-missing"]
    details = " ".join(p.detail for p in problems)
    assert "plan-reviewer" in details and "code-reviewer" in details


# ===========================================================================
# CHECK 1 — referenced-agent-missing.
# ===========================================================================


def test_missing_referenced_review_agent_flagged():
    # Drop code-reviewer.md; the contract still references `code-reviewer`.
    agents = [a for a in good_agents() if a[0] != "code-reviewer.md"]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    missing = [p for p in problems if p.kind == "referenced-agent-missing"]
    assert len(missing) == 1
    assert "code-reviewer" in missing[0].detail


def test_backticked_nonagent_token_not_flagged_as_missing():
    # The contract backticks non-agent hyphenated tokens (e.g. `stash-pop`,
    # `read-only`); those must NOT be reported as missing agents.
    contract = GOOD_CONTRACT + "\nNever `stash-pop`; stay `read-only`.\n"
    problems = sar.check_consistency(contract, good_agents())
    assert [p for p in problems if p.kind == "referenced-agent-missing"] == []


def test_non_review_referenced_agent_missing_is_not_hard_error():
    # A backticked role that isn't one of the hard-required review agents and has
    # no file is tolerated (only plan/code-reviewer are must-exist).
    contract = GOOD_CONTRACT + "\nThe `browser-ops` agent drives slots.\n"
    problems = sar.check_consistency(contract, good_agents())  # no browser-ops.md
    assert [p for p in problems if p.kind == "referenced-agent-missing"] == []


# ===========================================================================
# CHECK 2 — malformed-frontmatter.
# ===========================================================================


def test_agent_without_frontmatter_flagged():
    agents = good_agents() + [("stray.md", "No frontmatter, just prose.\n")]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    bad = [p for p in problems if p.kind == "malformed-frontmatter"]
    assert len(bad) == 1
    assert "stray.md" in bad[0].detail


def test_agent_unclosed_frontmatter_flagged():
    # Opening --- but never closing it -> not a valid frontmatter block.
    text = "---\nname: broken\nmodel: sonnet\nYou operate under `~/.claude/CLAUDE.md`.\n"
    agents = good_agents() + [("broken.md", text)]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert any(p.kind == "malformed-frontmatter" and "broken.md" in p.detail for p in problems)


def test_agent_empty_name_value_flagged():
    text = _agent("").replace("name: \n", "name:\n")
    agents = good_agents() + [("empty.md", text)]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert any(p.kind == "malformed-frontmatter" and "empty.md" in p.detail for p in problems)


# ===========================================================================
# CHECK 3 — name-mismatch (frontmatter name != filename stem).
# ===========================================================================


def test_name_mismatch_flagged():
    # File named worker.md but frontmatter says name: something-else.
    agents = good_agents() + [("worker.md", _agent("something-else", model="sonnet"))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    mm = [p for p in problems if p.kind == "name-mismatch"]
    assert len(mm) == 1
    assert "worker.md" in mm[0].detail and "something-else" in mm[0].detail


def test_matching_name_not_flagged():
    agents = good_agents() + [("worker.md", _agent("worker", model="sonnet"))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "name-mismatch"] == []


# ===========================================================================
# CHECK 4 — missing-contract-anchor.
# ===========================================================================


def test_agent_missing_contract_anchor_flagged():
    agents = good_agents() + [("loose.md", _agent("loose", model="sonnet", anchor=False))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    anchor = [p for p in problems if p.kind == "missing-contract-anchor"]
    assert len(anchor) == 1
    assert "loose.md" in anchor[0].detail


def test_all_good_agents_have_anchor():
    problems = sar.check_consistency(GOOD_CONTRACT, good_agents())
    assert [p for p in problems if p.kind == "missing-contract-anchor"] == []


# ===========================================================================
# CHECK 5 — model-drift (contract-declared Opus agents must be `opus`).
# ===========================================================================


def test_review_agent_wrong_model_is_drift():
    # plan-reviewer downgraded to sonnet contradicts the contract's §10 "Opus".
    agents = [
        ("plan-reviewer.md", _agent("plan-reviewer", model="sonnet")),
        ("code-reviewer.md", _agent("code-reviewer", model="opus")),
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "model-drift"]
    assert len(drift) == 1
    assert "plan-reviewer" in drift[0].detail and "sonnet" in drift[0].detail


def test_review_agent_unset_model_is_drift():
    text = (
        "---\nname: code-reviewer\ndescription: x\n---\nYou operate under `~/.claude/CLAUDE.md`.\n"
    )
    agents = [
        # "opus" -- FABLE_AGENTS is empty (standing fable pins retired,
        # operator directive 2026-09-24), so plan-reviewer's correct pin is
        # "opus" like every other OPUS_AGENTS member; this agent is here
        # only as a correctly-pinned filler, not the subject of this test.
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", text),
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "model-drift"]
    assert len(drift) == 1
    assert "<unset>" in drift[0].detail


def test_non_review_agent_sonnet_is_not_drift():
    # A worker agent on sonnet is correct — model-drift only applies to the
    # contract-declared Opus roster.
    problems = sar.check_consistency(GOOD_CONTRACT, good_agents())
    assert [p for p in problems if p.kind == "model-drift"] == []


# ===========================================================================
# CHECK 8 — worker-model-drift (non-review agent: no pin, or pinned opus).
# ===========================================================================


def test_worker_agent_missing_model_is_drift():
    text = "---\nname: nomodel\ndescription: x\n---\nYou operate under `~/.claude/CLAUDE.md`.\n"
    agents = good_agents() + [("nomodel.md", text)]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "worker-model-drift"]
    assert len(drift) == 1
    assert "nomodel.md" in drift[0].detail and "no model pin" in drift[0].detail


def test_worker_agent_opus_pin_is_drift():
    agents = good_agents() + [("rogue-opus.md", _agent("rogue-opus", model="opus"))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "worker-model-drift"]
    assert len(drift) == 1
    assert "rogue-opus.md" in drift[0].detail
    assert "plan-reviewer" in drift[0].detail and "code-reviewer" in drift[0].detail


def test_worker_agent_fable_pin_is_drift():
    # A worker pinned "fable" (2x Opus 5 pricing) is exactly as much a
    # departure from the "opus reserved for the two review boundaries"
    # invariant as a bare "opus" pin -- fable is opus-tier-and-above, never
    # a way to dodge the worker-model-drift check. Before this check widened
    # to `elif model in ("opus", "fable")`, a worker mutated to `model:
    # fable` produced ZERO sync problems (trust-architect finding, 2026-09-19
    # fix round H2).
    agents = good_agents() + [("rogue-fable.md", _agent("rogue-fable", model="fable"))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "worker-model-drift"]
    assert len(drift) == 1
    assert "rogue-fable.md" in drift[0].detail
    assert "plan-reviewer" in drift[0].detail and "code-reviewer" in drift[0].detail


def test_worker_agent_sonnet_or_haiku_not_flagged():
    agents = good_agents() + [
        ("cheap1.md", _agent("cheap1", model="sonnet")),
        ("cheap2.md", _agent("cheap2", model="haiku")),
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "worker-model-drift"] == []


def test_fable_agents_member_requires_literal_fable_not_opus(monkeypatch):
    """The FABLE_AGENTS mechanism itself, exercised generically (no live
    roster involved): with a fixture FABLE_AGENTS = ("alpha",), a contract
    that declares both "alpha" and "beta" as OPUS_AGENTS members --

      * "alpha" pinned "fable" is CLEAN (check 5's `required` resolves to
        "fable" for a FABLE_AGENTS member) -- no model-drift for alpha.
      * "beta" pinned "opus" is also clean (not a FABLE_AGENTS member, so
        `required` is plain "opus").

    This is the generic mechanism proof Item 5 of the fable->opus repin fix
    round asks for: FABLE_AGENTS stays a live, working narrowing-subset
    switch even though it is empty in the real runtime today (both former
    standing pins, marketing-director and plan-reviewer, were retired to
    opus by operator directive 2026-09-24). Never asserts anything about the
    live roster -- OPUS_AGENTS/FABLE_AGENTS are monkeypatched to a disjoint
    fixture pair so this test cannot collide with real agent names.
    """
    monkeypatch.setattr(sar, "OPUS_AGENTS", ("alpha", "beta"))
    monkeypatch.setattr(sar, "FABLE_AGENTS", ("alpha",))
    contract = (
        "# Fixture Contract\n\nUse the defined agents in `~/.claude/agents/` as written.\n"
    )
    agents = [
        ("alpha.md", _agent("alpha", model="fable")),
        ("beta.md", _agent("beta", model="opus")),
    ]
    problems = sar.check_consistency(contract, agents)
    assert [p for p in problems if p.kind == "model-drift"] == []


def test_fable_agents_member_pinned_opus_is_model_drift(monkeypatch):
    """The falsifiability companion to the test above: with the SAME fixture
    FABLE_AGENTS = ("alpha",), pinning "alpha" to "opus" instead of "fable"
    MUST be flagged model-drift -- proving the check actually requires the
    literal "fable" string for a FABLE_AGENTS member, not just "any
    OPUS_AGENTS-sanctioned tier". This is the case that goes RED if
    sync_agent_rules.py's `required = "fable" if stem in FABLE_AGENTS else
    "opus"` line is ever collapsed to a bare `required = "opus"` -- verified
    by hand in a scratch copy (see the fix-round report for the exact
    command and output)."""
    monkeypatch.setattr(sar, "OPUS_AGENTS", ("alpha", "beta"))
    monkeypatch.setattr(sar, "FABLE_AGENTS", ("alpha",))
    contract = (
        "# Fixture Contract\n\nUse the defined agents in `~/.claude/agents/` as written.\n"
    )
    agents = [
        ("alpha.md", _agent("alpha", model="opus")),  # wrong -- must be "fable"
        ("beta.md", _agent("beta", model="opus")),
    ]
    problems = sar.check_consistency(contract, agents)
    drift = [p for p in problems if p.kind == "model-drift"]
    assert len(drift) == 1
    assert "alpha" in drift[0].detail and "Fable" in drift[0].detail


def test_review_agents_exempt_from_worker_check_even_when_unset():
    # An unset model on a review agent is model-drift (check 5), not ALSO
    # worker-model-drift (check 8) -- the two checks must not double-count.
    text = "---\nname: code-reviewer\ndescription: x\n---\nYou operate under `~/.claude/CLAUDE.md`.\n"
    agents = [
        # "opus" -- correctly-pinned filler, not this test's
        # subject (see test_review_agent_unset_model_is_drift above).
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", text),
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "worker-model-drift"] == []
    assert len([p for p in problems if p.kind == "model-drift"]) == 1


def test_all_good_agents_have_no_worker_model_drift():
    problems = sar.check_consistency(GOOD_CONTRACT, good_agents())
    assert [p for p in problems if p.kind == "worker-model-drift"] == []


# ===========================================================================
# CHECK 6 — env-var-drift (CSA_* the contract does not define).
# ===========================================================================


def test_agent_unknown_csa_var_is_drift():
    body = "Set `CSA_TURBO_MODE=1` to go fast."  # not in the contract
    agents = good_agents() + [("rogue.md", _agent("rogue", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "env-var-drift"]
    assert len(drift) == 1
    assert "CSA_TURBO_MODE" in drift[0].detail and "rogue.md" in drift[0].detail


def test_agent_known_csa_var_not_flagged():
    body = "Respect `CSA_ENFORCE=1` and `CSA_DISABLE_HOOKS=1`."  # both in contract
    agents = good_agents() + [("ok.md", _agent("ok", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "env-var-drift"] == []


def test_repeated_unknown_csa_var_reported_once_per_agent():
    body = "`CSA_TURBO_MODE=1` ... again `CSA_TURBO_MODE` ... and once more CSA_TURBO_MODE"
    agents = [("rogue.md", _agent("rogue", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "env-var-drift"]
    assert len(drift) == 1  # deduped per agent


# ===========================================================================
# CHECK 7 — script-path-drift (scripts/*.sh the contract does not name).
# ===========================================================================


def test_deferred_pool_tools_without_toolsearch_is_drift():
    # #4452: mcp__playwright-NN__* tools are DEFERRED; without ToolSearch the
    # agent can load none of them. RED without check (9).
    agents = good_agents() + [
        (
            "browser-ops.md",
            _agent(
                "browser-ops",
                extra_frontmatter="tools: Read, Bash, mcp__playwright-01__browser_navigate",
            ),
        )
    ]
    kinds = [p.kind for p in sar.check_consistency(GOOD_CONTRACT, agents)]
    assert "deferred-tools-without-toolsearch" in kinds


def test_deferred_pool_tools_with_toolsearch_is_clean():
    agents = good_agents() + [
        (
            "browser-ops.md",
            _agent(
                "browser-ops",
                extra_frontmatter=(
                    "tools: Read, Bash, ToolSearch, mcp__playwright-01__browser_navigate"
                ),
            ),
        )
    ]
    kinds = [p.kind for p in sar.check_consistency(GOOD_CONTRACT, agents)]
    assert "deferred-tools-without-toolsearch" not in kinds


def test_bare_unpooled_playwright_grant_does_not_need_toolsearch():
    # #4452: the bare, unpooled `mcp__playwright__` server loads its tools
    # EAGERLY — it is not one of the deferred pool-slot servers, so granting
    # it alone (no numbered/adhoc/auth slot present) must NOT trip check (9).
    # Check (10) still fires separately for the bare-server grant itself.
    agents = good_agents() + [
        ("browser-ops.md", _agent("browser-ops", extra_frontmatter="tools: Read, mcp__playwright__*"))
    ]
    kinds = [p.kind for p in sar.check_consistency(GOOD_CONTRACT, agents)]
    assert "deferred-tools-without-toolsearch" not in kinds
    assert "browser-grant-not-least-privilege" in kinds


def test_no_mcp_grant_does_not_require_toolsearch():
    agents = good_agents() + [
        ("lint-check.md", _agent("lint-check", extra_frontmatter="tools: Bash, Read, Glob, Grep"))
    ]
    kinds = [p.kind for p in sar.check_consistency(GOOD_CONTRACT, agents)]
    assert "deferred-tools-without-toolsearch" not in kinds


def _browser_agent(tools: str):
    return good_agents() + [("browser-ops.md", _agent("browser-ops", extra_frontmatter=f"tools: {tools}"))]


def _kinds(agents):
    return [p.kind for p in sar.check_consistency(GOOD_CONTRACT, agents)]


# --- check 9 combination coverage: every anchor branch of the regexes ---------


def test_toolsearch_at_start_of_list_is_accepted():
    assert "deferred-tools-without-toolsearch" not in _kinds(
        _browser_agent("ToolSearch, Read, mcp__playwright-03__browser_navigate")
    )


def test_toolsearch_at_end_of_list_is_accepted():
    assert "deferred-tools-without-toolsearch" not in _kinds(
        _browser_agent("Read, mcp__playwright-03__browser_navigate, ToolSearch")
    )


def test_adhoc_server_grant_is_deferred_too():
    assert "deferred-tools-without-toolsearch" in _kinds(
        _browser_agent("Read, mcp__playwright-adhoc__browser_navigate")
    )


def test_non_playwright_mcp_grant_is_out_of_scope():
    # The check is deliberately scoped to the playwright family.
    assert "deferred-tools-without-toolsearch" not in _kinds(_browser_agent("Read, mcp__stripe__*"))


# --- check 10: least-privilege browser grant (RED without check 10) -----------


def test_playwright_wildcard_grant_is_not_least_privilege():
    assert "browser-grant-not-least-privilege" in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright-01__*")
    )


def test_browser_evaluate_grant_is_not_least_privilege():
    assert "browser-grant-not-least-privilege" in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright-01__browser_evaluate")
    )


def test_run_code_unsafe_grant_is_not_least_privilege():
    assert "browser-grant-not-least-privilege" in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright__browser_run_code_unsafe")
    )


def test_adhoc_server_grant_is_not_least_privilege():
    assert "browser-grant-not-least-privilege" in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright-adhoc__browser_navigate")
    )


def test_enumerated_safe_browser_grant_is_clean():
    assert "browser-grant-not-least-privilege" not in _kinds(
        _browser_agent(
            "Read, Bash, ToolSearch, mcp__playwright-01__browser_navigate, "
            "mcp__playwright-01__browser_snapshot, mcp__playwright-01__browser_click"
        )
    )


def test_least_privilege_check_does_not_fire_without_a_browser_grant():
    assert "browser-grant-not-least-privilege" not in _kinds(_browser_agent("Read, mcp__stripe__*"))


def test_bare_unpooled_playwright_grant_is_not_least_privilege():
    # mcp__playwright__ (two underscores, no -NN slot suffix) is a DIFFERENT,
    # unpooled MCP server: no isolation/origin flags, and never a leasable
    # pool slot — it lives in ~/.claude.json, which browser_pool.py never
    # generates or prunes. Granting it must be flagged the same
    # way as a wildcard/adhoc grant, regardless of which tool is named.
    assert "browser-grant-not-least-privilege" in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright__browser_navigate")
    )


def test_enumerated_slot_grant_not_flagged_as_bare():
    # The mirror case: a real numbered slot must NOT be mistaken for the bare
    # server — mcp__playwright-07__... never contains the literal substring
    # "playwright__" (there's a hyphenated slot id in between).
    assert "browser-grant-not-least-privilege" not in _kinds(
        _browser_agent("Read, ToolSearch, mcp__playwright-07__browser_navigate")
    )


def test_bare_unpooled_grant_reason_names_bare_unpooled_server():
    problems = sar.check_consistency(
        GOOD_CONTRACT,
        _browser_agent("Read, ToolSearch, mcp__playwright__browser_navigate"),
    )
    detail = " ".join(p.detail for p in problems if p.kind == "browser-grant-not-least-privilege")
    assert "bare-unpooled-server" in detail


def test_wildcard_and_bare_unpooled_grants_together_join_both_reasons():
    # Combination coverage: a deferred (playwright) grant that ALSO holds both
    # an unsafe wildcard/JS-eval/adhoc tool AND a bare-unpooled-server tool at
    # once must report exactly one Problem, whose detail names both the
    # offending tool and the bare-unpooled server — not just whichever one
    # the regex happens to match first. Assertions are stable-token (the
    # offending tool name, the literal bare-server substring), not coupled to
    # exact prose wording.
    problems = sar.check_consistency(
        GOOD_CONTRACT,
        _browser_agent(
            "Read, ToolSearch, mcp__playwright-01__browser_evaluate, "
            "mcp__playwright__browser_navigate"
        ),
    )
    grant_problems = [p for p in problems if p.kind == "browser-grant-not-least-privilege"]
    assert len(grant_problems) == 1
    detail = grant_problems[0].detail
    assert "mcp__playwright-01__browser_evaluate" in detail
    assert "mcp__playwright__" in detail


def test_agent_unknown_script_path_is_drift():
    body = "Run `~/.claude/scripts/phantom_helper.sh` first."  # not in contract
    agents = good_agents() + [("scripter.md", _agent("scripter", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "script-path-drift"]
    assert len(drift) == 1
    assert "phantom_helper.sh" in drift[0].detail


def test_agent_known_script_path_not_flagged():
    body = "Commit via `~/.claude/scripts/git_guard.sh` and `~/.claude/scripts/gh_issue.sh`."
    agents = good_agents() + [("scripter.md", _agent("scripter", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "script-path-drift"] == []


def test_a_product_repo_script_path_is_not_runtime_drift():
    """A runtime agent citing PRODUCT tooling is correct, not drift.

    The rule's regex had no path boundary, so `repo_tooling/scripts/
    local_ci.sh` matched on its inner `scripts/` segment and came back as
    `local_ci.sh` -- which the RUNTIME contract naturally does not name,
    because it is a product-repo helper. Three agents (ci-monitor, git-ops,
    test-runner) were flagged for correctly telling an agent to run the
    product's own CI. #5848.
    """
    body = "Run `bash repo_tooling/scripts/local_ci.sh --mode=ci-parity` before pushing."
    agents = good_agents() + [("scripter.md", _agent("scripter", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "script-path-drift"] == []


def test_a_foreign_prefix_never_smuggles_a_runtime_script_past_the_check():
    """PAIRED RECOVERY for the case above -- the anchor must not become a
    blind spot. A GENUINELY unknown runtime helper is still drift, and a
    foreign prefix must not be usable to hide one: both forms are asserted
    so the fix cannot be 'stop checking anything with a slash in it'.
    """
    body = "Run `~/.claude/scripts/phantom_helper.sh` and `scripts/other_phantom.sh`."
    agents = good_agents() + [("scripter.md", _agent("scripter", model="sonnet", body=body))]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    flagged = sorted(
        p.detail.split("'scripts/")[1].split("'")[0]
        for p in problems if p.kind == "script-path-drift"
    )
    assert flagged == ["other_phantom.sh", "phantom_helper.sh"], flagged


@pytest.mark.parametrize(
    "form",
    [
        "**scripts/phantom_helper.sh**",      # bold
        "./scripts/phantom_helper.sh",        # dot-slash
        "CMD=scripts/phantom_helper.sh",      # after '='
        "run,scripts/phantom_helper.sh",      # after ','
        "- scripts/phantom_helper.sh",        # markdown list item
        "[link](scripts/phantom_helper.sh)",  # markdown link
        "`scripts/phantom_helper.sh`",        # backticked
        "~/.claude/scripts/phantom_helper.sh",
        ".claude/scripts/phantom_helper.sh",
    ],
)
def test_no_punctuation_form_lets_an_unknown_runtime_script_escape(form):
    """The anchor must not become a BLIND SPOT -- the dangerous direction.

    A first attempt anchored on an ALLOWLIST of preceding characters and
    leaked on every form below except the list item, link and backtick: it
    silently stopped flagging `**scripts/x.sh**`, `./scripts/x.sh`,
    `CMD=scripts/x.sh` and `run,scripts/x.sh`. Trading a false positive for
    false negatives is strictly worse for a drift check, so the rule rejects
    a FOREIGN PREFIX instead of guessing which characters may precede a path.
    """
    agents = good_agents() + [
        ("scripter.md", _agent("scripter", model="sonnet", body=f"Run {form} now."))
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    drift = [p for p in problems if p.kind == "script-path-drift"]
    assert len(drift) == 1, f"{form!r} escaped the check entirely"
    assert "phantom_helper.sh" in drift[0].detail


@pytest.mark.parametrize(
    "form",
    [
        "repo_tooling/scripts/local_ci.sh",
        "modules/a/scripts/local_ci.sh",
        "foo.claude/scripts/local_ci.sh",   # NOT a .claude path -- boundary required
        "${REPO}/scripts/local_ci.sh",      # the CONTRACT'S OWN mandated form
        "${REPO:csa}/scripts/local_ci.sh",  # ...with a slug, as the preamble writes it
        "<repo>/scripts/local_ci.sh",       # CLAUDE.md's placeholder idiom
        "$REPO/scripts/local_ci.sh",        # unbraced env var
    ],
)
def test_a_foreign_prefix_is_never_read_as_a_runtime_helper(form):
    """PAIRED RECOVERY: the rejection must key on a real path boundary, so
    a lookalike like `foo.claude/` cannot smuggle itself in as `.claude/`."""
    agents = good_agents() + [
        ("scripter.md", _agent("scripter", model="sonnet", body=f"Run {form} first."))
    ]
    problems = sar.check_consistency(GOOD_CONTRACT, agents)
    assert [p for p in problems if p.kind == "script-path-drift"] == []


# ===========================================================================
# Cross-cutting: multiple drifts accumulate; output is stable-ordered.
# ===========================================================================


def test_multiple_problems_accumulate_and_are_stable():
    agents = [
        # opus review agents both present & correct
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", _agent("code-reviewer", model="sonnet")),  # model-drift
        ("loose.md", _agent("loose", model="sonnet", anchor=False)),  # anchor
        ("mismatch.md", _agent("other", model="sonnet")),  # name-mismatch
    ]
    p1 = sar.check_consistency(GOOD_CONTRACT, agents)
    p2 = sar.check_consistency(GOOD_CONTRACT, agents)
    assert p1 == p2  # deterministic
    kinds = {p.kind for p in p1}
    assert "model-drift" in kinds
    assert "missing-contract-anchor" in kinds
    assert "name-mismatch" in kinds


def test_none_and_empty_inputs_do_not_raise():
    assert isinstance(sar.check_consistency("", []), list)
    assert isinstance(sar.check_consistency(None, []), list)  # type: ignore[arg-type]
    # An agent with None text is treated as empty (malformed frontmatter).
    problems = sar.check_consistency(GOOD_CONTRACT, [("x.md", None)])  # type: ignore[list-item]
    assert any(p.kind == "malformed-frontmatter" for p in problems)


# ===========================================================================
# parse_frontmatter — unit coverage.
# ===========================================================================


def test_parse_frontmatter_basic():
    fm = sar.parse_frontmatter("---\nname: foo\nmodel: opus\n---\nbody\n")
    assert fm == {"name": "foo", "model": "opus"}


def test_parse_frontmatter_no_leading_delimiter():
    assert sar.parse_frontmatter("name: foo\n---\n") == {}


def test_parse_frontmatter_unclosed_returns_empty():
    assert sar.parse_frontmatter("---\nname: foo\nmodel: opus\n") == {}


def test_parse_frontmatter_empty_string():
    assert sar.parse_frontmatter("") == {}


def test_parse_frontmatter_ignores_comment_and_valueless_lines():
    fm = sar.parse_frontmatter(
        "---\n# a comment\nname: foo\njust-a-line-no-colon\nmodel: sonnet\n---\n"
    )
    assert fm == {"name": "foo", "model": "sonnet"}


def test_parse_frontmatter_value_with_colon_kept():
    # A description containing a colon keeps everything after the first colon.
    fm = sar.parse_frontmatter("---\nname: foo\ndescription: does x: and y\n---\n")
    assert fm["description"] == "does x: and y"


def test_agent_stem_helper():
    assert sar._agent_stem("plan-reviewer.md") == "plan-reviewer"
    assert sar._agent_stem("/a/b/code-reviewer.md") == "code-reviewer"
    assert sar._agent_stem("noext") == "noext"


# ===========================================================================
# Problem value object.
# ===========================================================================


def test_problem_equality_hash_and_format():
    a = sar.Problem("k", "d")
    b = sar.Problem("k", "d")
    c = sar.Problem("k", "other")
    assert a == b and hash(a) == hash(b)
    assert a != c and a != "not a problem"
    assert a.format() == "[k] d"
    assert len({a, b, c}) == 2


# ===========================================================================
# load_docs — the IO loader against a sandboxed ~/.claude.
# ===========================================================================


def _write_runtime(sandbox, contract=GOOD_CONTRACT, agents=None):
    """Materialize a CLAUDE.md + agents/*.md tree under the sandbox ~/.claude."""
    if contract is not None:
        (sandbox.claude / "CLAUDE.md").write_text(contract)
    agents_dir = sandbox.claude / "agents"
    agents_dir.mkdir(exist_ok=True)
    for name, text in agents or good_agents():
        (agents_dir / name).write_text(text)
    return sandbox.claude


def test_load_docs_reads_contract_and_agents(sandbox):
    _write_runtime(sandbox)
    contract_text, agents = sar.load_docs(str(sandbox.claude))
    assert "Operating Contract" in contract_text
    names = sorted(n for n, _ in agents)
    assert names == ["code-reviewer.md", "git-ops.md", "implement.md", "plan-reviewer.md"]


def test_load_docs_missing_contract_returns_empty_string(sandbox):
    (sandbox.claude / "agents").mkdir()
    contract_text, agents = sar.load_docs(str(sandbox.claude))
    assert contract_text == ""
    assert agents == []


def test_load_docs_missing_agents_dir(sandbox):
    (sandbox.claude / "CLAUDE.md").write_text(GOOD_CONTRACT)
    contract_text, agents = sar.load_docs(str(sandbox.claude))
    assert "Contract" in contract_text
    assert agents == []


def test_load_docs_skips_non_md_and_subdirs(sandbox):
    _write_runtime(sandbox)
    agents_dir = sandbox.claude / "agents"
    (agents_dir / "README.txt").write_text("not an agent")
    (agents_dir / "notes.md.bak").write_text("backup")
    (agents_dir / "subdir.md").mkdir()  # a directory ending in .md must be skipped
    _, agents = sar.load_docs(str(sandbox.claude))
    names = [n for n, _ in agents]
    assert "README.txt" not in names
    assert "subdir.md" not in names
    assert "plan-reviewer.md" in names


def test_read_text_unreadable_returns_empty(sandbox):
    assert sar._read_text(str(sandbox.claude / "does-not-exist.md")) == ""


# ===========================================================================
# main() — the decision matrix. Deny via JSON only; always exits 0.
# ===========================================================================


def _run_main(monkeypatch, payload_dict):
    """Feed a JSON payload on stdin and run main(); return (rc, stdout)."""
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload_dict)))
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sar.main()
    return rc, buf.getvalue()


def test_main_clean_runtime_logs_clean_no_block(sandbox, clean_env, make_payload):
    _write_runtime(sandbox)  # consistent contract + roster
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    assert out.strip() == ""  # no block emitted
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["hook"] == "sync_agent_rules"
    assert rec["decision"] == "clean"
    assert rec["agents"] == 4


def test_main_drift_log_only_when_not_enforcing(sandbox, clean_env, make_payload):
    # Introduce drift (code-reviewer on sonnet); enforcement OFF -> would-block,
    # NO block object emitted.
    agents = [
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", _agent("code-reviewer", model="sonnet")),
    ]
    _write_runtime(sandbox, agents=agents)
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    assert out.strip() == ""  # LOG-ONLY: nothing surfaced
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "would-block"
    assert "model-drift" in rec["kinds"]


def test_main_drift_blocks_when_enforcing(sandbox, clean_env, make_payload):
    agents = [
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
        ("code-reviewer.md", _agent("code-reviewer", model="sonnet")),
    ]
    _write_runtime(sandbox, agents=agents)
    clean_env.setenv("CSA_ENFORCE", "1")  # enforcement ON
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    obj = json.loads(out)
    assert obj["decision"] == "block"
    assert "consistency problem" in obj["reason"]
    assert "model-drift" in obj["reason"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "block"


def test_main_disabled_is_master_off(sandbox, clean_env, make_payload):
    # Even with drift AND enforcement, CSA_DISABLE_HOOKS=1 short-circuits:
    # no block, no log line at all.
    agents = [("code-reviewer.md", _agent("code-reviewer", model="sonnet"))]
    _write_runtime(sandbox, agents=agents)
    clean_env.setenv("CSA_ENFORCE", "1")
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    assert out.strip() == ""
    assert not sandbox.log_file.exists()


def test_main_clean_when_disabled_still_no_log(sandbox, clean_env, make_payload):
    _write_runtime(sandbox)
    clean_env.setenv("CSA_DISABLE_HOOKS", "1")
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop"))
    assert rc == 0
    assert out.strip() == ""
    assert not sandbox.log_file.exists()


def test_main_block_via_project_marker_enforcement(
    sandbox, clean_env, make_payload, git_repo, enforce_marker
):
    # Enforcement resolved from a project opt-in marker (not the env var): a repo
    # cwd carrying .claude/.csa-enforce makes enforcing() True, so drift blocks.
    agents = [
        ("code-reviewer.md", _agent("code-reviewer", model="sonnet")),
        ("plan-reviewer.md", _agent("plan-reviewer", model="opus")),
    ]
    _write_runtime(sandbox, agents=agents)
    enforce_marker(git_repo)
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(git_repo)))
    assert rc == 0
    assert json.loads(out)["decision"] == "block"


def test_main_degrades_open_on_internal_error(sandbox, clean_env, make_payload, monkeypatch):
    # If check_consistency blows up, main() must swallow it, log 'error', exit 0.
    _write_runtime(sandbox)

    def boom(*a, **k):
        raise RuntimeError("validator exploded")

    monkeypatch.setattr(sar, "check_consistency", boom)
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    assert out.strip() == ""
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "error"


def test_main_error_path_swallows_log_failure(sandbox, clean_env, make_payload, monkeypatch):
    # Both check_consistency AND the error-path log() raising must not surface.
    _write_runtime(sandbox)

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(sar, "check_consistency", boom)
    monkeypatch.setattr(_lib, "log", boom)  # even logging the error fails
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop"))
    assert rc == 0
    assert out.strip() == ""


def test_main_empty_stdin_no_crash(sandbox, clean_env, monkeypatch):
    # Empty/garbage stdin -> {} event; validator still runs against the runtime.
    _write_runtime(sandbox)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sar.main()
    assert rc == 0
    # clean runtime -> clean log, no block.
    assert buf.getvalue().strip() == ""


# ===========================================================================
# _block_reason — formatting.
# ===========================================================================


def test_block_reason_enumerates_problems():
    problems = [sar.Problem("model-drift", "x is sonnet"), sar.Problem("name-mismatch", "y != z")]
    reason = sar._block_reason(problems)
    assert "2 contract/agent consistency problem(s)" in reason
    assert "[model-drift] x is sonnet" in reason
    assert "[name-mismatch] y != z" in reason


# ===========================================================================
# AUDIT FINDING 3 (2026-09-03, #4744) — worktree-agent-twin detection.
#
# A repo's .claude/worktrees/<name>/.claude/agents/<stem>.md whose stem
# collides with a name in the RUNTIME roster silently REPLACES the runtime
# definition (last-write-wins name resolution) for any session running
# inside that worktree. No existing checker scanned worktrees before this
# fix (430 shadow files measured live, up from 287 a week earlier).
# ===========================================================================


def _write_registry(path, repos: dict):
    """Write a repo_registry.json mapping slug -> root path string."""
    path.write_text(json.dumps({"schema_version": 1, "repos": repos}))


def _write_worktree_agent(repo_root, worktree_name, agent_filename, text="stub body\n"):
    """Materialize <repo_root>/.claude/worktrees/<worktree_name>/.claude/agents/<agent_filename>."""
    agents_dir = (
        repo_root / ".claude" / "worktrees" / worktree_name / ".claude" / "agents"
    )
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / agent_filename).write_text(text)


def test_worktree_twin_of_runtime_agent_is_flagged(tmp_path):
    # RED without the fix: a worktree carries a same-named twin of a real
    # runtime agent ("implement") -> must be flagged as worktree-agent-twin,
    # naming the worktree path and the runtime agent it shadows.
    repo_root = tmp_path / "SomeProduct"
    repo_root.mkdir()
    _write_worktree_agent(repo_root, "agent-abc123", "implement.md")

    registry = tmp_path / "repo_registry.json"
    _write_registry(registry, {"someproduct": {"root": str(repo_root)}})

    runtime_names = {"implement", "git-ops", "plan-reviewer", "code-reviewer"}
    problems = sar.find_worktree_agent_twins(runtime_names, str(registry))

    twins = [p for p in problems if p.kind == "worktree-agent-twin"]
    assert len(twins) == 1
    assert "implement" in twins[0].detail
    assert "agent-abc123" in twins[0].detail
    assert str(repo_root) in twins[0].detail


def test_worktree_agent_with_non_colliding_name_not_flagged(tmp_path):
    # A worktree agent whose name has never lived in the runtime roster (a
    # genuine product-domain specialist) is NOT a twin — only a name
    # collision with the runtime roster is the defect.
    repo_root = tmp_path / "SomeProduct"
    repo_root.mkdir()
    _write_worktree_agent(repo_root, "agent-abc123", "engine-architect.md")

    registry = tmp_path / "repo_registry.json"
    _write_registry(registry, {"someproduct": {"root": str(repo_root)}})

    runtime_names = {"implement", "git-ops", "plan-reviewer", "code-reviewer"}
    problems = sar.find_worktree_agent_twins(runtime_names, str(registry))

    assert [p for p in problems if p.kind == "worktree-agent-twin"] == []


def test_multiple_worktrees_and_repos_all_scanned(tmp_path):
    repo_a = tmp_path / "RepoA"
    repo_a.mkdir()
    repo_b = tmp_path / "RepoB"
    repo_b.mkdir()
    _write_worktree_agent(repo_a, "wt1", "git-ops.md")
    _write_worktree_agent(repo_a, "wt2", "code-reviewer.md")
    _write_worktree_agent(repo_b, "wt1", "test-writer.md")
    _write_worktree_agent(repo_b, "wt1", "unrelated-specialist.md")  # not a collision

    registry = tmp_path / "repo_registry.json"
    _write_registry(
        registry, {"repoa": {"root": str(repo_a)}, "repob": {"root": str(repo_b)}}
    )

    runtime_names = {"git-ops", "code-reviewer", "test-writer", "implement"}
    problems = sar.find_worktree_agent_twins(runtime_names, str(registry))
    twins = [p for p in problems if p.kind == "worktree-agent-twin"]
    assert len(twins) == 3
    detail_blob = " ".join(p.detail for p in twins)
    assert "git-ops" in detail_blob
    assert "code-reviewer" in detail_blob
    assert "test-writer" in detail_blob
    assert "unrelated-specialist" not in detail_blob


def test_repo_with_no_worktrees_dir_contributes_nothing(tmp_path):
    repo_root = tmp_path / "NoWorktrees"
    repo_root.mkdir()  # no .claude/worktrees at all

    registry = tmp_path / "repo_registry.json"
    _write_registry(registry, {"noworktrees": {"root": str(repo_root)}})

    problems = sar.find_worktree_agent_twins({"implement"}, str(registry))
    assert problems == []


def test_missing_repo_registry_degrades_to_no_problems(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    problems = sar.find_worktree_agent_twins({"implement"}, str(missing))
    assert problems == []


def test_malformed_repo_registry_json_degrades_to_no_problems(tmp_path):
    registry = tmp_path / "repo_registry.json"
    registry.write_text("{ not valid json ")
    problems = sar.find_worktree_agent_twins({"implement"}, str(registry))
    assert problems == []


def test_worktree_agent_non_md_and_directory_entries_are_skipped(tmp_path):
    repo_root = tmp_path / "SomeProduct"
    repo_root.mkdir()
    agents_dir = repo_root / ".claude" / "worktrees" / "wt1" / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "README.txt").write_text("not an agent")
    (agents_dir / "subdir.md").mkdir()  # a directory ending in .md — must be skipped
    (agents_dir / "implement.md").write_text("real twin")

    registry = tmp_path / "repo_registry.json"
    _write_registry(registry, {"someproduct": {"root": str(repo_root)}})

    problems = sar.find_worktree_agent_twins({"implement"}, str(registry))
    twins = [p for p in problems if p.kind == "worktree-agent-twin"]
    assert len(twins) == 1
    assert "implement" in twins[0].detail


def test_load_repo_registry_helper(tmp_path):
    registry = tmp_path / "repo_registry.json"
    _write_registry(
        registry,
        {"a": {"root": "~/Desktop/A"}, "bad": "not-a-dict", "b": {"no_root": True}},
    )
    result = sar._load_repo_registry(str(registry))
    assert result == {"a": os.path.expanduser("~/Desktop/A")}


def test_load_repo_registry_missing_file_returns_empty(tmp_path):
    assert sar._load_repo_registry(str(tmp_path / "nope.json")) == {}


# --- main() integration: worktree twins surface through the same decision path ---


def test_main_flags_worktree_twin_via_repo_registry(sandbox, clean_env, make_payload):
    # End-to-end: a consistent contract+roster (no drift from check_consistency)
    # but a registered repo's worktree carries a twin of a runtime agent ->
    # main() must still report the worktree-agent-twin problem.
    _write_runtime(sandbox)  # consistent GOOD_CONTRACT + good_agents()

    repo_root = sandbox.home / "Desktop" / "SomeProduct"
    repo_root.mkdir(parents=True)
    _write_worktree_agent(repo_root, "agent-xyz", "implement.md")

    knowledge_dir = sandbox.claude / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    _write_registry(knowledge_dir / "repo_registry.json", {"someproduct": {"root": str(repo_root)}})

    clean_env.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    obj = json.loads(out)
    assert obj["decision"] == "block"
    assert "worktree-agent-twin" in obj["reason"]
    assert "implement" in obj["reason"]
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert "worktree-agent-twin" in rec["kinds"]


def test_main_clean_when_no_worktree_twins_present(sandbox, clean_env, make_payload):
    # Consistent contract+roster AND a registered repo with a non-colliding
    # worktree agent name -> still clean, no block.
    _write_runtime(sandbox)

    repo_root = sandbox.home / "Desktop" / "SomeProduct"
    repo_root.mkdir(parents=True)
    _write_worktree_agent(repo_root, "agent-xyz", "engine-architect.md")

    knowledge_dir = sandbox.claude / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    _write_registry(knowledge_dir / "repo_registry.json", {"someproduct": {"root": str(repo_root)}})

    rc, out = _run_main(clean_env, make_payload(tool_name="Stop", cwd=str(sandbox.home)))
    assert rc == 0
    assert out.strip() == ""
    rec = json.loads(sandbox.log_file.read_text().strip().splitlines()[-1])
    assert rec["decision"] == "clean"


# ===========================================================================
# Regression against the LIVE runtime docs (read-only; runs the validator on the
# operator's real CLAUDE.md + agents/*.md, NEVER rewriting them).
#
# History: until 2026-08-25 this test PINNED one known live drift — code-reviewer.md
# was the only agent def with no ~/.claude/CLAUDE.md anchor — because this module
# owns only its two files and could not fix the doc. The anchor was added on
# 2026-08-25 (same commit as the agentic-systems-architect roster addition), so the
# pin is gone and the intended state is asserted directly: the live roster has NO
# consistency problems. A new drift anywhere in agents/*.md or CLAUDE.md fails
# this loudly with the offending problem(s) named.
# ===========================================================================


def test_live_runtime_docs_have_no_drift():
    import os

    real_claude = os.path.join(os.path.expanduser("~"), ".claude")
    contract_path = os.path.join(real_claude, "CLAUDE.md")
    if not os.path.isfile(contract_path):
        pytest.skip("no live CLAUDE.md to validate")
    contract_text, agents = sar.load_docs(real_claude)
    if not agents:
        pytest.skip("no live agents/ to validate")
    # The public bundle ships a THIN CLAUDE.md (the long-form contract is
    # OPERATING_CONTRACT.md); it names none of the helper scripts the agent
    # definitions cite, so every cited helper reads as `script-path-drift` -- a
    # structural gap, not drift. The thin file is detected by its OWN marker
    # heading, nothing else: this check has nothing to do with any particular
    # section, so a full contract that lost or renamed one must still reach the
    # assertion (and go RED), never skip. A skip CONDITION, not the
    # `live_machine` marker: that marker is deselected by the runtime's default
    # run and would silently drop this drift pin from the daily suite.
    # Follow-up: have sync_agent_rules.py read OPERATING_CONTRACT.md when
    # CLAUDE.md is the thin file.
    thin_marker = "# Operating Contract (thin)"
    if any(line.startswith(thin_marker) for line in contract_text.splitlines()):
        pytest.skip(
            f"{contract_path} is the thin public contract (it carries {thin_marker!r}), "
            "so there is no full contract to check the agent definitions against. "
            "Follow-up: sync_agent_rules.py falls back to OPERATING_CONTRACT.md for "
            "a thin CLAUDE.md."
        )
    problems = sar.check_consistency(contract_text, agents)
    assert problems == [], "live runtime docs drifted:\n" + "\n".join(
        p.format() for p in problems
    )
