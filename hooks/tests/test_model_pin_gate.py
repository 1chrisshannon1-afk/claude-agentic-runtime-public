"""Tests for model_pin_gate — the first real enforcement point for
`knowledge/model_policy.json`'s `agent_pins`, plus its two collaborators:
record_model_exception.py (mints the single-use, dispatch-bound exception
token this gate's decision 6 consumes) and pretooluse_task.py (the
PreToolUse:Task dispatcher that chains this gate (T1) before agent_budget.py's
existing gate (T2)).

Every verdict the gate can reach has a test that PRODUCES it, including the
allow paths — a suite that only proved the gate can say "blocked" would not
be able to tell a working gate from one that blocks unconditionally.

2026-09-01 fix round: this file was rewritten alongside model_pin_gate.py /
record_model_exception.py to close six trust-architect blockers (B1-B6) from
an adversarial review of the original build:
  B1 — the self-serve "operator-directed" exception reason is REMOVED
       entirely; the real operator-only mechanism is now
       scripts/grant_model_exception.sh, tested at the end of this file.
  B2 — exception tokens are now bound to the SHA-256 of the exact dispatch
       prompt they were minted for, not just (agent_type, model).
  B3 — pin resolution now ALSO scans the current repo's own
       `.claude/agents/*.md` roster, reproducing the real production
       incident (trade-tile, ExampleApp, 2026-09-01T18:48:07Z).
  B4 — single-use token consumption is now atomic (admission_lock +
       os.remove()-outcome-is-the-claim-signal), re-proving the 30-trial
       concurrency race the reviewer used.
  B5 — upward escalation can never target fable, and is narrowed to
       sonnet-source only.
  B6 — (documentation only, see CLAUDE.md — not testable here).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import agent_budget as ab  # noqa: E402
import model_pin_gate as mpg  # noqa: E402
import model_pin_parity as mpp  # noqa: E402
import pretooluse_task as ptt  # noqa: E402
import record_model_exception as rme  # noqa: E402
import review_risk_tier as rrt  # noqa: E402

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

CODE_REVIEWER_FRONTMATTER = """---
name: code-reviewer
description: test fixture
model: opus
tools: Read
---

body
"""

EXPLORE_FRONTMATTER = """---
name: explore
description: test fixture
model: sonnet
tools: Read
---

body
"""

# An agent file that exists on disk but carries NO frontmatter model pin at
# all — the genuinely-malformed case decide() now DENIES (missing-pin-in-file)
# rather than failing open (B3's "Also fix" bullet).
MALFORMED_FRONTMATTER = """---
name: malformed-agent
description: test fixture with no model pin
tools: Read
---

body
"""

TRADE_TILE_FRONTMATTER = """---
name: trade-tile
description: repo-local product-domain agent fixture, mirrors the real
  ExampleApp trade-tile.md that was incorrectly denied in production
model: sonnet
tools: Read
---

body
"""


@pytest.fixture
def agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    (d / "code-reviewer.md").write_text(CODE_REVIEWER_FRONTMATTER)
    (d / "explore.md").write_text(EXPLORE_FRONTMATTER)
    (d / "malformed-agent.md").write_text(MALFORMED_FRONTMATTER)
    return str(d)


@pytest.fixture
def policy_path(tmp_path):
    p = tmp_path / "model_policy.json"
    p.write_text(
        json.dumps(
            {
                "agent_pins": {
                    "code-reviewer": "opus",
                    "explore": "sonnet",
                    "general-purpose": "sonnet",
                }
            }
        )
    )
    return str(p)


@pytest.fixture
def exceptions_dir(tmp_path):
    # Deliberately NOT created — find_and_consume_exception / mint_token must
    # both handle a not-yet-existing directory correctly.
    return str(tmp_path / ".model_exceptions")


@pytest.fixture
def prompt_file(tmp_path):
    """Factory: prompt_file(text) -> path to a scratch file holding `text`,
    the shape record_model_exception.py's --prompt-file / mpg.decide()'s
    dispatch_prompt_hash both hash identically (B2)."""
    counter = {"n": 0}

    def _make(text: str) -> str:
        counter["n"] += 1
        p = tmp_path / f"prompt_{counter['n']}.txt"
        p.write_text(text)
        return str(p)

    return _make


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


DEFAULT_PROMPT_TEXT = "Review the pending diff for correctness."


def _ev(
    subagent_type,
    model=None,
    transcript_path=None,
    cwd="/tmp",
    tool_use_id=None,
    session_id=None,
    prompt=DEFAULT_PROMPT_TEXT,
):
    ti = {"subagent_type": subagent_type}
    if model is not None:
        ti["model"] = model
    if prompt is not None:
        ti["prompt"] = prompt
    ev = {"tool_input": ti, "cwd": cwd}
    if transcript_path is not None:
        ev["transcript_path"] = transcript_path
    if tool_use_id is not None:
        ev["tool_use_id"] = tool_use_id
    if session_id is not None:
        ev["session_id"] = session_id
    return ev


def _mint(
    agent_type,
    model,
    reason,
    paths,
    prompt_text,
    *,
    agents_dir,
    policy_path,
    exceptions_dir,
    prompt_file_factory,
    justification="",
):
    """Convenience wrapper: mint via rme.run() using a real --prompt-file
    built from `prompt_text`, returning (code, message)."""
    pf = prompt_file_factory(prompt_text)
    return rme.run(
        agent_type,
        model,
        reason,
        paths,
        pf,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        justification=justification,
    )


# ===========================================================================
# The four originally-mandated falsifiability cases (updated for B2's
# dispatch-bound tokens — the dispatch's own prompt must match what was
# minted against).
# ===========================================================================


def test_case_a_below_pin_dispatch_actually_denied_without_exception(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    """(a) code-reviewer dispatched on sonnet, no exception token -> DENIED,
    with the deny decision/reason asserted directly (not just "ran")."""
    ev = _ev("code-reviewer", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    assert detail["subagent_type"] == "code-reviewer"
    assert detail["model"] == "sonnet"
    assert detail["pin"] == "opus"


def test_case_b_valid_exception_against_real_trivial_pathspec_allows(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    """(b) the SAME dispatch SUCCEEDS after record_model_exception.py mints
    a valid, dispatch-bound token against a real trivial-classified pathspec
    AND the dispatch's own prompt matches what was minted."""
    trivial_path = "docs/some_doc.md"
    tier, reason_text = rrt.classify([trivial_path])
    assert tier == rrt.TRIVIAL, (
        f"fixture path must classify trivial, got {tier} ({reason_text})"
    )

    code, message = _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        [trivial_path],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code == 0, message
    assert os.path.isdir(exceptions_dir)
    minted_files = [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]
    assert len(minted_files) == 1

    ev = _ev("code-reviewer", model="sonnet", prompt=DEFAULT_PROMPT_TEXT)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""
    assert detail == {}
    # The token is single-use -- it must be gone after being consumed.
    assert not [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]


def test_case_c_mint_refuses_against_real_moderate_pathspec(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    """(c) record_model_exception.py REFUSES to mint against a real
    moderate-classified pathspec."""
    # NOT under hooks/agents/.github/schedules (those force HIGH per
    # review_risk_tier's own _HIGH_RISK_DIR_SEGMENTS) -- an ordinary,
    # non-doc, non-lock, keyword-free source path is a genuine MODERATE.
    moderate_path = "modules/some_widget.py"
    tier, reason_text = rrt.classify([moderate_path])
    assert tier == rrt.MODERATE, (
        f"fixture path must classify moderate, got {tier} ({reason_text})"
    )

    code, message = _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        [moderate_path],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code != 0
    assert "trivial" in message.lower()
    assert not os.path.isdir(exceptions_dir) or not any(
        f.endswith(".json") for f in os.listdir(exceptions_dir)
    )

    # The refused mint must never have granted a usable exception.
    ev = _ev("code-reviewer", model="sonnet")
    block, reason, _detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH


def test_case_d_catchall_no_model_denied_with_parent_tier_named(
    sandbox, tmp_path, agents_dir, policy_path, exceptions_dir
):
    """(d) a general-purpose dispatch with no `model` field is DENIED with
    the parent tier correctly named in the reason (fixture transcript with a
    known message.model, verified read and included)."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user"}})
        + "\n"
        + json.dumps(
            {"type": "assistant", "message": {"model": "claude-opus-5-20260101"}}
        )
        + "\n"
    )
    ev = _ev("general-purpose", model=None, transcript_path=str(transcript))
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_INHERIT_DRIFT
    assert detail["subagent_type"] == "general-purpose"
    assert detail["pin"] == "sonnet"
    assert detail["parent_model"] == "claude-opus-5-20260101"

    message = mpg.message_for(reason, detail)
    assert "claude-opus-5-20260101" in message
    assert "general-purpose" in message
    assert '"sonnet"' in message


# ===========================================================================
# "Plus:" required cases.
# ===========================================================================


def test_fork_always_allows_regardless_of_model(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    ev = _ev("fork", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""
    assert detail == {}


def test_fork_allows_even_against_unreadable_policy(sandbox, agents_dir):
    ev = _ev("fork")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path="/definitely/does/not/exist.json",
        exceptions_dir="/definitely/does/not/exist",
    )
    assert block is False


def test_fork_does_not_read_transcript_by_default(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir, tmp_path
):
    """"Also fix": an unconditional full-transcript read on every fork
    dispatch just to log a non-decision-relevant field is wasted I/O
    (measured up to 87 MB). Default (no CSA_MODEL_PIN_GATE_VERBOSE) must
    never call the transcript reader at all."""
    calls = []
    real = mpg._parent_model_from_transcript

    def _spy(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(mpg, "_parent_model_from_transcript", _spy)
    transcript = tmp_path / "big_transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n"
    )
    ev = _ev("fork", transcript_path=str(transcript))
    mpg.decide(
        ev, agents_dir=agents_dir, policy_path=policy_path, exceptions_dir=exceptions_dir
    )
    assert calls == []


def test_fork_reads_transcript_when_verbose_flag_set(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir, tmp_path
):
    monkeypatch.setenv(mpg.VERBOSE_FORK_LOGGING_VAR, "1")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n"
    )
    calls = []
    real = mpg._parent_model_from_transcript

    def _spy(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(mpg, "_parent_model_from_transcript", _spy)
    ev = _ev("fork", transcript_path=str(transcript))
    mpg.decide(
        ev, agents_dir=agents_dir, policy_path=policy_path, exceptions_dir=exceptions_dir
    )
    assert calls == [str(transcript)]


def test_frontmatter_pinned_type_with_no_explicit_model_always_allows(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    ev = _ev("explore", model=None)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""


def test_fail_open_on_unreadable_policy_file(
    sandbox, agents_dir, tmp_path, exceptions_dir
):
    ev = _ev("code-reviewer", model="sonnet")  # would otherwise mismatch
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=str(tmp_path / "does_not_exist.json"),
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""


def test_fail_open_on_unreadable_agents_dir(
    sandbox, policy_path, exceptions_dir, tmp_path
):
    ev = _ev("code-reviewer", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=str(tmp_path / "no_such_agents_dir"),
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False


def test_csa_disable_hooks_always_allows(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    ev = _ev("code-reviewer", model="sonnet")  # would otherwise mismatch
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""


def test_token_ttl_expiry_causes_a_recheck_to_deny_again(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    now = datetime.now(timezone.utc)
    rme.mint_token(
        exceptions_dir,
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        "trivial: ok",
        _sha(DEFAULT_PROMPT_TEXT),
        now=now,
        ttl_seconds=60,
    )
    later = now + timedelta(seconds=61)
    ev = _ev("code-reviewer", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=later,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    # Expired token must have been self-healed off disk, not left dangling.
    assert not any(f.endswith(".json") for f in os.listdir(exceptions_dir))


def test_token_is_single_use(sandbox, agents_dir, policy_path, exceptions_dir):
    now = datetime.now(timezone.utc)
    rme.mint_token(
        exceptions_dir,
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        "trivial: ok",
        _sha(DEFAULT_PROMPT_TEXT),
        now=now,
    )
    ev = _ev("code-reviewer", model="sonnet")
    block1, reason1, _ = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block1 is False

    block2, reason2, detail2 = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block2 is True
    assert reason2 == mpg.REASON_MISMATCH
    assert detail2["pin"] == "opus"


# ===========================================================================
# Every other decision branch (allow paths matter as much as deny paths).
# ===========================================================================


def test_decision2_explicit_model_matches_pin_allows(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    ev = _ev("code-reviewer", model="opus")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False


def test_decision5_ungoverned_type_allows_with_explicit_model(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    ev = _ev("kb-verifier", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False


def test_decision5_ungoverned_type_with_no_model_denies_unpinned(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    """kb-verifier has neither an agents/*.md file nor a policy pin, so a
    model-absent dispatch is the (structurally unreachable via decision 4's
    own ordering, but still directly exercisable) unpinned-agent-type path."""
    # Decision 4 already fires for "no file, model absent" ahead of decision
    # 5's own explicit clause -- confirm THAT is what actually fires here,
    # and that its detail still makes sense for a type with no policy pin at
    # all (pin=None).
    ev = _ev("kb-verifier", model=None)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_INHERIT_DRIFT
    assert detail["pin"] is None


def test_exception_wrong_agent_type_does_not_match(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    now = datetime.now(timezone.utc)
    rme.mint_token(
        exceptions_dir,
        "explore",
        "opus",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        "trivial: ok",
        _sha(DEFAULT_PROMPT_TEXT),
        now=now,
    )
    ev = _ev("code-reviewer", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH


# ===========================================================================
# B7 / "Also fix": a real on-disk agent file with NO frontmatter model pin
# now DENIES (missing-pin-in-file) unless an explicit model is given --
# replacing the pre-fix fail-open.
# ===========================================================================


def test_missing_pin_in_file_denies_without_explicit_model(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    ev = _ev("malformed-agent", model=None)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISSING_PIN_IN_FILE
    assert detail["subagent_type"] == "malformed-agent"
    assert detail["client_builtin"] is False
    message = mpg.message_for(reason, detail)
    assert "missing-pin-in-file" in message
    assert "malformed-agent" in message


def test_missing_pin_in_file_allows_with_explicit_model(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    """"unless explicit model given" -- an agent whose OWN file has no pin
    can still be dispatched by naming the model explicitly."""
    ev = _ev("malformed-agent", model="haiku")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False


def test_client_builtin_catchall_types_reused_not_redefined():
    """model_pin_gate.py must reuse model_pin_parity.CLIENT_BUILTIN_CATCHALL_
    TYPES rather than maintaining its own parallel list (the two modules
    would otherwise silently drift apart)."""
    assert mpg.mpp is mpp
    assert mpp.CLIENT_BUILTIN_CATCHALL_TYPES == frozenset({"Explore", "Plan", "claude"})


# ===========================================================================
# B3 — repo-local agent pin resolution. Reproduces the real production
# incident: a repo-local `.claude/agents/trade-tile.md` (pinned sonnet)
# dispatched bare was denied with pin: null on 2026-09-01T18:48:07Z because
# this gate only ever scanned ~/.claude/agents/.
# ===========================================================================


def test_repo_local_agent_bare_dispatch_resolves_pin_and_allows(
    sandbox, git_repo, agents_dir, policy_path, exceptions_dir
):
    repo_agents = git_repo / ".claude" / "agents"
    repo_agents.mkdir(parents=True)
    (repo_agents / "trade-tile.md").write_text(TRADE_TILE_FRONTMATTER)

    ev = _ev("trade-tile", model=None, cwd=str(git_repo))
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False, f"expected ALLOW, got deny: {reason} {detail}"


def test_repo_local_agent_explicit_disagreeing_model_denies(
    sandbox, git_repo, agents_dir, policy_path, exceptions_dir
):
    """Proving this isn't just "found a file, allow anything": an explicit
    model that DISAGREES with the repo-local pin is still denied
    (pin-tier-mismatch)."""
    repo_agents = git_repo / ".claude" / "agents"
    repo_agents.mkdir(parents=True)
    (repo_agents / "trade-tile.md").write_text(TRADE_TILE_FRONTMATTER)

    ev = _ev("trade-tile", model="opus", cwd=str(git_repo))
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    assert detail["pin"] == "sonnet"


def test_repo_local_agent_correct_explicit_model_allows(
    sandbox, git_repo, agents_dir, policy_path, exceptions_dir
):
    repo_agents = git_repo / ".claude" / "agents"
    repo_agents.mkdir(parents=True)
    (repo_agents / "trade-tile.md").write_text(TRADE_TILE_FRONTMATTER)

    ev = _ev("trade-tile", model="sonnet", cwd=str(git_repo))
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False


def test_repo_local_agent_absent_repo_agents_dir_is_not_fail_open(
    sandbox, git_repo, agents_dir, policy_path, exceptions_dir
):
    """A repo with NO .claude/agents/ at all (the overwhelmingly common
    case) must behave exactly as if no repo-local roster were consulted --
    NOT as a fail-open trigger."""
    ev = _ev("code-reviewer", model="sonnet", cwd=str(git_repo))  # still a real mismatch
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH


def test_repo_root_for_cwd_returns_none_outside_a_repo(sandbox, tmp_path):
    assert mpg.repo_root_for_cwd(str(tmp_path)) is None
    assert mpg.repo_root_for_cwd(None) is None
    assert mpg.repo_root_for_cwd("") is None


def test_repo_root_for_cwd_resolves_real_toplevel(git_repo):
    root = mpg.repo_root_for_cwd(str(git_repo))
    assert root is not None
    assert os.path.realpath(root) == os.path.realpath(str(git_repo))


# ===========================================================================
# B2 — dispatch-bound exception tokens: a token minted against ONE prompt's
# text cannot authorize a dispatch bound to a DIFFERENT prompt, even with
# the identical (agent_type, model) pair. Reproduces the reviewer's exact
# scenario: minted against README.md, spent against firestore.rules.
# ===========================================================================


def test_token_bound_to_prompt_cannot_be_spent_by_a_different_prompt(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    readme_prompt = "Review README.md for typos and broken links."
    firestore_prompt = "Review firestore.rules for a tenant-isolation regression."

    code, message = _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["README.md"],
        readme_prompt,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code == 0, message

    # The SAME (agent_type, model) pair, but a DIFFERENT dispatch prompt --
    # this must be denied. This is the exact incident B2 exists to close.
    ev = _ev("code-reviewer", model="sonnet", prompt=firestore_prompt)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH

    # The token must still be sitting there, unconsumed, because the
    # firestore.rules dispatch never actually matched it.
    remaining = [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]
    assert len(remaining) == 1

    # And the ORIGINAL bound dispatch (matching prompt) still works.
    ev_ok = _ev("code-reviewer", model="sonnet", prompt=readme_prompt)
    block_ok, reason_ok, _ = mpg.decide(
        ev_ok,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block_ok is False


def test_dispatch_prompt_hash_matches_record_model_exception_hashing(prompt_file):
    """The gate's own hashing (over the live tool_input.prompt) and
    record_model_exception's (over --prompt-file contents) MUST agree bit
    for bit, or every token would be permanently unspendable."""
    text = "identical prompt text"
    pf = prompt_file(text)
    assert rme.read_prompt_hash(pf) == mpg.dispatch_prompt_hash({"prompt": text})


def test_dispatch_prompt_hash_missing_prompt_never_matches_a_real_token(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    code, message = _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code == 0, message
    # A dispatch payload with NO prompt field at all.
    ev = _ev("code-reviewer", model="sonnet", prompt=None)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH


# ===========================================================================
# B4 — atomic single-use token consumption. Re-proves the reviewer's own
# 30-trial, 2-concurrent-consumer race with 0/30 double-spend.
# ===========================================================================


def test_find_and_consume_exception_atomic_two_concurrent_consumers_30_trials(
    sandbox, exceptions_dir
):
    """Mirrors the reviewer's measurement exactly (2 concurrent consumers,
    30 trials, pre-fix: 4/30 double-spend). Post-fix: 0/30."""
    os.makedirs(exceptions_dir, exist_ok=True)
    trials = 30
    double_spends = 0
    now = datetime.now(timezone.utc)
    prompt_hash = _sha(DEFAULT_PROMPT_TEXT)

    for i in range(trials):
        rme.mint_token(
            exceptions_dir,
            "code-reviewer",
            "sonnet",
            rme.REASON_TRIVIAL,
            ["docs/x.md"],
            "trivial: ok",
            prompt_hash,
            now=now,
        )
        results: list[dict | None] = [None, None]

        def _consume(idx):
            results[idx] = mpg.find_and_consume_exception(
                exceptions_dir, "code-reviewer", "sonnet", prompt_hash, now=now
            )

        t1 = threading.Thread(target=_consume, args=(0,))
        t2 = threading.Thread(target=_consume, args=(1,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        successes = sum(1 for r in results if r is not None)
        if successes > 1:
            double_spends += 1
        assert successes >= 1, f"trial {i}: token was lost, neither consumer won it"
        # No leftover file from this trial should remain (exactly one
        # consumer claimed it, and it must actually be gone).
        leftover = [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]
        assert leftover == [], f"trial {i}: leftover token file(s): {leftover}"

    assert double_spends == 0, f"{double_spends}/{trials} trials double-spent"


def test_consume_first_match_losing_racer_gets_none_not_the_token(
    sandbox, exceptions_dir, monkeypatch
):
    """Directly proves the TOCTOU fix: force os.remove() to raise
    FileNotFoundError (simulating "someone else already unlinked it") and
    confirm the caller gets None, not the token data."""
    os.makedirs(exceptions_dir, exist_ok=True)
    now = datetime.now(timezone.utc)
    prompt_hash = _sha(DEFAULT_PROMPT_TEXT)
    rme.mint_token(
        exceptions_dir,
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        "trivial: ok",
        prompt_hash,
        now=now,
    )
    real_remove = os.remove

    def _losing_remove(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "remove", _losing_remove)
    try:
        result = mpg.find_and_consume_exception(
            exceptions_dir, "code-reviewer", "sonnet", prompt_hash, now=now
        )
    finally:
        monkeypatch.setattr(os, "remove", real_remove)
    assert result is None


# ===========================================================================
# B5 — fable is never self-serve-mintable, and escalation is narrowed to
# sonnet-source only.
# ===========================================================================


def test_verify_escalation_alone_would_accept_fable_by_tier_order(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    """verify_escalation() itself has NO fable special-case (fable ranks
    above sonnet in TIER_ORDER, so its own directional check alone would
    pass) -- the hard, unconditional refusal lives in run(), BEFORE
    verify_escalation is ever called (see the module docstring's B5
    section). Documenting this here so it's explicit that the real
    enforcement point is run(), verified end-to-end by
    test_run_refuses_fable_target_regardless_of_reason below -- never rely
    on verify_escalation alone to stop a fable target."""
    ok, _message = rme.verify_escalation(mpg.FABLE_MODEL, "sonnet")
    assert ok is True
    # And yet the real, callable entry point still refuses it outright:
    code, message = _mint(
        "explore",
        mpg.FABLE_MODEL,
        rme.REASON_ESCALATION,
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
        justification="a real, well-formed justification",
    )
    assert code != 0
    assert "fable" in message.lower()


def test_run_refuses_fable_target_regardless_of_reason(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    for reason, paths in (
        (rme.REASON_ESCALATION, []),
        (rme.REASON_TRIVIAL, ["docs/x.md"]),
    ):
        code, message = _mint(
            "code-reviewer",
            mpg.FABLE_MODEL,
            reason,
            paths,
            DEFAULT_PROMPT_TEXT,
            agents_dir=agents_dir,
            policy_path=policy_path,
            exceptions_dir=exceptions_dir,
            prompt_file_factory=prompt_file,
            justification="I really need it",
        )
        assert code != 0, f"reason={reason} must never mint fable"
        assert "fable" in message.lower()
        assert "grant_model_exception.sh" in message


def test_decide_never_allows_fable_via_a_hand_crafted_self_serve_token(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    """Defense-in-depth: even if a fable-targeted token somehow exists on
    disk (hand-crafted, or a hypothetical future minting bug), the GATE
    itself must still refuse to consult the self-serve store for a fable
    target."""
    now = datetime.now(timezone.utc)
    rme.mint_token(
        exceptions_dir,
        "code-reviewer",
        mpg.FABLE_MODEL,
        rme.REASON_ESCALATION,
        [],
        None,
        _sha(DEFAULT_PROMPT_TEXT),
        justification="hand-crafted bypass attempt",
        now=now,
    )
    ev = _ev("code-reviewer", model=mpg.FABLE_MODEL)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    # The hand-crafted token must still be sitting there, untouched -- the
    # gate never even looked at the self-serve store for a fable target.
    remaining = [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]
    assert len(remaining) == 1


# ===========================================================================
# Standing fable pin (2026-09-19, operator directive, PERMANENT -- RETIRED
# 2026-09-24 by a further operator directive repinning every seat that ever
# carried it to opus). Historically, exactly TWO agent_types --
# marketing-director and plan-reviewer -- carried
# agent_pins["<name>"] == "fable" and needed NO grant at all for an on-pin
# dispatch. plan-reviewer was standing-pinned fable on 2026-09-19, narrowed
# back out the same day (trust-architect fix round, BLOCKER B1, on the
# grounds that it is dispatched bare by THE ISSUE WHEEL's own unattended
# nightly schedule), and RESTORED by operator ruling 2026-09-20
# (ExampleApp OPERATOR_DECISIONS.md card [87], ACCEPTED) — the
# operator accepted that unattended spend knowingly, until the 2026-09-24
# directive retired it back to opus. This fixture block exercises the
# MECHANISM generically (fable resolved via a synthetic policy/agents dir,
# never the live roster) using marketing-director as its example label;
# plan-reviewer behaved identically while it carried the pin, because
# decisions 2/3 are agent-type-agnostic. The mechanism these tests prove
# still works today for any FUTURE standing fable pin. Every OTHER
# agent_type's fable handling is unchanged (proven by the tests above,
# which still use "code-reviewer"/"explore" -- neither was ever
# fable-pinned).
# ===========================================================================


@pytest.fixture
def fable_agents_dir(tmp_path):
    """A second, disjoint agents dir carrying a real fable-pinned seat
    (marketing-director) alongside an ordinary opus-pinned one
    (code-reviewer) -- kept separate from `agents_dir` above so none of the
    pre-existing tests need to change shape."""
    d = tmp_path / "fable_agents"
    d.mkdir()
    (d / "code-reviewer.md").write_text(CODE_REVIEWER_FRONTMATTER)
    (d / "marketing-director.md").write_text(
        "---\n"
        "name: marketing-director\n"
        "description: test fixture\n"
        "model: fable\n"
        "tools: Read\n"
        "---\n\nbody\n"
    )
    return str(d)


@pytest.fixture
def fable_policy_path(tmp_path):
    p = tmp_path / "fable_model_policy.json"
    p.write_text(
        json.dumps(
            {
                "agent_pins": {
                    "code-reviewer": "opus",
                    "marketing-director": "fable",
                }
            }
        )
    )
    return str(p)


def test_fable_pinned_seat_bare_dispatch_allows_no_grant_consumed(
    sandbox, fable_agents_dir, fable_policy_path, exceptions_dir
):
    """(a) a bare dispatch of the fable-pinned seat (no explicit model)
    resolves its pin as fable and ALLOWS via decision 3 -- no grant file
    involved, none consumed, nothing minted."""
    ev = _ev("marketing-director", model=None)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""
    assert detail == {}
    # No grant/token directory was even touched.
    assert not os.path.isdir(exceptions_dir)


def test_fable_pinned_seat_explicit_fable_model_allows_no_grant_consumed(
    sandbox, fable_agents_dir, fable_policy_path, exceptions_dir
):
    """(a-variant) an EXPLICIT model: "fable" on the fable-pinned seat also
    allows -- via decision 2 (matches the resolved pin), an ordinary on-pin
    allow, logged the same as any other on-pin dispatch."""
    ev = _ev("marketing-director", model="fable")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False
    assert reason == ""
    assert detail == {}
    assert not os.path.isdir(exceptions_dir)


def test_non_pinned_seat_fable_request_with_no_grant_still_denied(
    sandbox, fable_agents_dir, fable_policy_path, exceptions_dir
):
    """(b) a fable request for a seat NOT in FABLE_AGENTS (code-reviewer,
    pinned opus in this fixture) is denied exactly as before -- the standing
    pin for marketing-director changes NOTHING about any other
    agent_type's fable handling."""
    ev = _ev("code-reviewer", model=mpg.FABLE_MODEL)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    assert detail["subagent_type"] == "code-reviewer"
    assert detail["model"] == mpg.FABLE_MODEL
    assert detail["pin"] == "opus"


def test_non_pinned_seat_fable_request_with_valid_operator_grant_allows(
    sandbox, fable_agents_dir, fable_policy_path, exceptions_dir
):
    """(c) the pre-existing operator-grant path for a NON-fable-pinned seat
    is unchanged and still green: a real operator grant for code-reviewer/
    fable allows and is consumed (single-use)."""
    now = datetime.now(timezone.utc)
    os.makedirs(exceptions_dir, exist_ok=True)
    grant_path = os.path.join(
        exceptions_dir, "operator_grant_code-reviewer_fable_20260919T000000Z.json"
    )
    with open(grant_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "agent_type": "code-reviewer",
                "model": mpg.FABLE_MODEL,
                "granted_at": mpg.format_ts(now),
                "expires_at": mpg.format_ts(now + timedelta(minutes=30)),
            },
            fh,
        )
    ev = _ev("code-reviewer", model=mpg.FABLE_MODEL)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block is False
    # Single-use: the grant file is gone, a second identical dispatch denies.
    block2, reason2, _ = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block2 is True
    assert reason2 == mpg.REASON_MISMATCH


def test_fable_pinned_seat_downgrade_request_is_ordinary_below_pin_dispatch(
    sandbox, fable_agents_dir, fable_policy_path, exceptions_dir, prompt_file
):
    """A NON-fable request for the fable-pinned seat (a downgrade, e.g.
    dispatching marketing-director on sonnet) is an ORDINARY below-pin dispatch
    under decision 6 -- denied without an exception, then allowed once a
    normal (non-fable-targeted) exception token is minted and consumed. The
    requested MODEL here is "sonnet", never "fable", so
    find_and_consume_exception's fable hard-refusal never triggers -- this
    proves the standing pin does not smuggle any special-cased leniency into
    the downgrade direction."""
    ev = _ev("marketing-director", model="sonnet")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is True
    assert reason == mpg.REASON_MISMATCH
    assert detail["pin"] == "fable"

    code, message = _mint(
        "marketing-director",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/some_doc.md"],
        DEFAULT_PROMPT_TEXT,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code == 0, message

    ev_ok = _ev("marketing-director", model="sonnet", prompt=DEFAULT_PROMPT_TEXT)
    block_ok, reason_ok, _ = mpg.decide(
        ev_ok,
        agents_dir=fable_agents_dir,
        policy_path=fable_policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block_ok is False


def test_verify_escalation_requires_sonnet_source_pin():
    """Pre-fix: ANY upward direction was accepted, so an already-opus-pinned
    agent could self-mint further up. Post-fix: only sonnet-source escalates."""
    ok, message = rme.verify_escalation("opus", "haiku")
    assert ok is False
    assert "sonnet" in message.lower()


def test_verify_escalation_sonnet_to_opus_still_allowed():
    ok, message = rme.verify_escalation("opus", "sonnet")
    assert ok is True, message


def test_verify_escalation_downward_refused():
    ok, message = rme.verify_escalation("haiku", "sonnet")
    assert ok is False


def test_verify_escalation_lateral_refused():
    ok, message = rme.verify_escalation("sonnet", "sonnet")
    assert ok is False


def test_verify_escalation_unknown_pin_refused():
    ok, message = rme.verify_escalation("opus", None)
    assert ok is False
    assert "known policy pin" in message


def test_run_refuses_escalation_without_justification(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    code, message = _mint(
        "explore",
        "opus",
        rme.REASON_ESCALATION,
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
        justification="",
    )
    assert code != 0
    assert "justification" in message.lower()


def test_run_mints_via_escalation_reason_with_justification_logged(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    # code-reviewer's pin is already "opus", so "opus"->"opus" would be
    # lateral, not an escalation, AND its pin isn't sonnet anyway -- use
    # explore (pinned sonnet) escalating to opus, the genuine allowed case.
    code2, message2 = _mint(
        "explore",
        "opus",
        rme.REASON_ESCALATION,
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
        justification="sonnet failed twice on a genuine race-condition repro; escalating.",
    )
    assert code2 == 0, message2
    ev = _ev("explore", model="opus")
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert block is False

    grants_path = os.path.join(exceptions_dir, mpg.GRANTS_LOG_NAME)
    with open(grants_path, encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert any(
        row.get("justification", "").startswith("sonnet failed twice") for row in lines
    )


# ===========================================================================
# B1 — "operator-directed" is REMOVED; the only operator-only path is the
# standalone script, never a self-serve env var.
# ===========================================================================


def test_operator_directed_reason_no_longer_exists():
    assert not hasattr(rme, "REASON_OPERATOR")
    assert not hasattr(rme, "verify_operator_directed")
    assert not hasattr(rme, "OPERATOR_ESCAPE_VAR")
    assert "operator-directed" not in rme.REASONS


def test_run_refuses_operator_directed_reason_string(
    agents_dir, policy_path, exceptions_dir, prompt_file
):
    code, message = _mint(
        "code-reviewer",
        "haiku",
        "operator-directed",
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code != 0
    assert "must be one of" in message


def test_env_var_alone_can_no_longer_mint_anything(
    monkeypatch, agents_dir, policy_path, exceptions_dir, prompt_file
):
    """The core B1 falsification: an agent's own Bash call setting
    CSA_MODEL_EXCEPTION=1 inline must have ZERO effect now -- there is no
    verification function left anywhere in this module that reads it."""
    monkeypatch.setenv("CSA_MODEL_EXCEPTION", "1")
    # Even the (now-invalid) reason string is refused identically whether or
    # not the old escape-hatch var is set -- proving the var is simply never
    # consulted.
    code, message = _mint(
        "code-reviewer",
        "haiku",
        "operator-directed",
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code != 0
    assert "must be one of" in message
    # And nothing was minted onto disk as a side effect either way.
    assert not os.path.isdir(exceptions_dir) or not any(
        f.endswith(".json") for f in os.listdir(exceptions_dir)
    )


def test_run_run_source_never_reads_os_environ():
    """Static falsification, not just a behavioral one: record_model_
    exception.run()'s own signature no longer even ACCEPTS an environ
    argument -- there is no parameter left to smuggle a self-serve grant
    through."""
    import inspect

    sig = inspect.signature(rme.run)
    assert "environ" not in sig.parameters


def test_grant_model_exception_script_mints_a_consumable_grant_file(sandbox):
    """End-to-end proof of the ONLY remaining path: a real invocation of
    scripts/grant_model_exception.sh (as the OPERATOR would run it, in
    THEIR OWN terminal) writes a file model_pin_gate.py's
    find_and_consume_operator_grant() can atomically consume -- and this is
    genuinely the only surviving mechanism for a fable target.

    The script writes to $HOME/.claude/.model_exceptions/ (its own
    documented, hardcoded location) -- HOME is pointed at the sandbox, and
    the REAL resulting path (not the generic exceptions_dir fixture, which
    is a differently-rooted tmp path) is what gets consumed."""
    script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "scripts",
        "grant_model_exception.sh",
    )
    script = os.path.abspath(script)
    assert os.path.isfile(script), script
    assert os.access(script, os.X_OK), "grant_model_exception.sh must be executable"

    env = dict(os.environ)
    env["HOME"] = str(sandbox.home)
    proc = subprocess.run(
        ["bash", script, "code-reviewer", mpg.FABLE_MODEL, "1800"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr

    real_exceptions_dir = os.path.join(str(sandbox.home), ".claude", ".model_exceptions")
    assert os.path.isdir(real_exceptions_dir)

    result = mpg.find_and_consume_operator_grant(
        real_exceptions_dir, "code-reviewer", mpg.FABLE_MODEL
    )
    assert result is not None
    assert result["agent_type"] == "code-reviewer"
    assert result["model"] == mpg.FABLE_MODEL

    # Single-use: a second consumption attempt finds nothing.
    result2 = mpg.find_and_consume_operator_grant(
        real_exceptions_dir, "code-reviewer", mpg.FABLE_MODEL
    )
    assert result2 is None


def test_decide_allows_fable_via_operator_grant_end_to_end(
    sandbox, agents_dir, policy_path, exceptions_dir
):
    """The full path: an operator grant file lets decide() ALLOW a fable
    dispatch that a self-serve token could never have authorized."""
    now = datetime.now(timezone.utc)
    # Write the grant file directly (equivalent to what the shell script
    # writes) to keep this test hermetic/fast; the script itself is
    # end-to-end tested separately above.
    os.makedirs(exceptions_dir, exist_ok=True)
    grant_path = os.path.join(
        exceptions_dir, "operator_grant_code-reviewer_fable_20260901T000000Z.json"
    )
    with open(grant_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "agent_type": "code-reviewer",
                "model": mpg.FABLE_MODEL,
                "granted_at": mpg.format_ts(now),
                "expires_at": mpg.format_ts(now + timedelta(minutes=30)),
            },
            fh,
        )

    ev = _ev("code-reviewer", model=mpg.FABLE_MODEL)
    block, reason, detail = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block is False

    # Single-use: repeating the SAME dispatch a second time is denied again.
    block2, reason2, _ = mpg.decide(
        ev,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        now=now,
    )
    assert block2 is True
    assert reason2 == mpg.REASON_MISMATCH


def test_operator_grant_expiry_is_enforced(sandbox, agents_dir, policy_path, exceptions_dir):
    now = datetime.now(timezone.utc)
    os.makedirs(exceptions_dir, exist_ok=True)
    grant_path = os.path.join(
        exceptions_dir, "operator_grant_code-reviewer_haiku_20260901T000000Z.json"
    )
    with open(grant_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "agent_type": "code-reviewer",
                "model": "haiku",
                "granted_at": mpg.format_ts(now - timedelta(minutes=40)),
                "expires_at": mpg.format_ts(now - timedelta(minutes=10)),
            },
            fh,
        )
    result = mpg.find_and_consume_operator_grant(
        exceptions_dir, "code-reviewer", "haiku", now=now
    )
    assert result is None
    # Self-healed off disk (the admission_lock's own lock file is expected
    # to remain -- it is not part of the token/grant store's contents).
    assert not [f for f in os.listdir(exceptions_dir) if f.endswith(".json")]


def test_grants_jsonl_still_appended_and_durable(
    sandbox, agents_dir, policy_path, exceptions_dir, prompt_file
):
    _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/a.md"],
        "prompt a",
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    _mint(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/b.md"],
        "prompt b",
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    grants_path = os.path.join(exceptions_dir, mpg.GRANTS_LOG_NAME)
    assert os.path.isfile(grants_path)
    with open(grants_path, encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert len(lines) == 2
    # The grant log survives even after the ephemeral tokens are consumed.
    ev_a = _ev("code-reviewer", model="sonnet", prompt="prompt a")
    ev_b = _ev("code-reviewer", model="sonnet", prompt="prompt b")
    mpg.decide(
        ev_a, agents_dir=agents_dir, policy_path=policy_path, exceptions_dir=exceptions_dir
    )
    mpg.decide(
        ev_b, agents_dir=agents_dir, policy_path=policy_path, exceptions_dir=exceptions_dir
    )
    with open(grants_path, encoding="utf-8") as fh:
        lines_after = [json.loads(line) for line in fh if line.strip()]
    assert len(lines_after) == 2


def test_run_refuses_unknown_reason(agents_dir, policy_path, exceptions_dir, prompt_file):
    code, message = _mint(
        "code-reviewer",
        "sonnet",
        "not-a-real-reason",
        [],
        DEFAULT_PROMPT_TEXT,
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
        prompt_file_factory=prompt_file,
    )
    assert code != 0
    assert "must be one of" in message


def test_run_refuses_unreadable_prompt_file(agents_dir, policy_path, exceptions_dir):
    code, message = rme.run(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        "/definitely/does/not/exist_prompt.txt",
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert code != 0
    assert "prompt-file" in message.lower() or "prompt_file" in message.lower()


# ===========================================================================
# pretooluse_task.py — T1 (model_pin_gate) then T2 (agent_budget gate).
# ===========================================================================


def _run_main(monkeypatch, payload, *, env=None):
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = ptt.main()
    return rc, buf.getvalue()


def _is_deny(stdout: str) -> bool:
    if not stdout.strip():
        return False
    try:
        obj = json.loads(stdout)
    except Exception:
        return False
    hso = obj.get("hookSpecificOutput", {})
    return (
        hso.get("hookEventName") == "PreToolUse"
        and hso.get("permissionDecision") == "deny"
    )


def test_t1_deny_under_enforcement_skips_t2_claim(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(mpg, "DEFAULT_POLICY_PATH", policy_path)
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", exceptions_dir)

    payload = _ev("code-reviewer", model="sonnet", tool_use_id="toolu_denytest")
    rc, out = _run_main(monkeypatch, payload, env={"CSA_ENFORCE": "1"})

    assert rc == 0
    assert _is_deny(out)
    assert "pin-tier-mismatch" in out
    claims_path = ab.claims_path(str(sandbox.agent_budget_dir))
    assert not os.path.exists(claims_path)


def test_t1_deny_log_only_still_lets_t2_run(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    """Without CSA_ENFORCE, T1's would-block is log-only (matching every
    other gate's default) -- the dispatch still proceeds to T2."""
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(mpg, "DEFAULT_POLICY_PATH", policy_path)
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", exceptions_dir)

    payload = _ev(
        "code-reviewer", model="sonnet", tool_use_id="toolu_logonly", session_id="s1"
    )
    rc, out = _run_main(monkeypatch, payload)

    assert rc == 0
    assert not _is_deny(out)
    claims_path = ab.claims_path(str(sandbox.agent_budget_dir))
    assert os.path.exists(claims_path)
    with open(claims_path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert any(r.get("tool_use_id") == "toolu_logonly" for r in rows)


def test_t1_allow_lets_t2_run_and_record_a_claim(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(mpg, "DEFAULT_POLICY_PATH", policy_path)
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", exceptions_dir)

    payload = _ev(
        "explore", model="sonnet", tool_use_id="toolu_allowtest", session_id="s2"
    )
    rc, out = _run_main(monkeypatch, payload, env={"CSA_ENFORCE": "1"})

    assert rc == 0
    assert not _is_deny(out)
    claims_path = ab.claims_path(str(sandbox.agent_budget_dir))
    assert os.path.exists(claims_path)
    with open(claims_path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert any(r.get("tool_use_id") == "toolu_allowtest" for r in rows)


def test_csa_disable_hooks_short_circuits_pretooluse_task(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(mpg, "DEFAULT_POLICY_PATH", policy_path)
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", exceptions_dir)

    payload = _ev("code-reviewer", model="sonnet", tool_use_id="toolu_disabled")
    rc, out = _run_main(
        monkeypatch, payload, env={"CSA_ENFORCE": "1", "CSA_DISABLE_HOOKS": "1"}
    )
    assert rc == 0
    assert out == ""
    claims_path = ab.claims_path(str(sandbox.agent_budget_dir))
    assert not os.path.exists(claims_path)


def test_fork_dispatch_reaches_t2_unimpeded(
    sandbox, monkeypatch, agents_dir, policy_path, exceptions_dir
):
    monkeypatch.setattr(mpg, "DEFAULT_AGENTS_DIR", agents_dir)
    monkeypatch.setattr(mpg, "DEFAULT_POLICY_PATH", policy_path)
    monkeypatch.setattr(mpg, "DEFAULT_EXCEPTIONS_DIR", exceptions_dir)

    payload = _ev("fork", tool_use_id="toolu_forktest", session_id="s3")
    rc, out = _run_main(monkeypatch, payload, env={"CSA_ENFORCE": "1"})
    assert rc == 0
    assert not _is_deny(out)


# ===========================================================================
# churn_report.py / .gitignore — cheap "Also fix" items, sanity-checked here
# so a future edit can't silently regress them.
# ===========================================================================


def test_churn_report_gate_hooks_include_model_pin_gate_and_pretooluse_task():
    import churn_report as cr

    assert "pretooluse_task" in cr._GATE_HOOKS
    assert "model_pin_gate" in cr._GATE_HOOKS


def test_gitignore_covers_model_exceptions_dir():
    gitignore_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".gitignore",
    )
    with open(gitignore_path, encoding="utf-8") as fh:
        text = fh.read()
    assert ".model_exceptions/" in text
