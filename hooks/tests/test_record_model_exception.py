"""Direct tests for hooks/record_model_exception.py, the CLI that mints the
single-use, 15-minute, dispatch-bound exception token model_pin_gate consumes
to let ONE off-pin dispatch through.

The spec is the module docstring (not its current output):

  * the reason vocabulary is closed to exactly two values; each is verified
    independently of the caller's word (``trivial-tier-confirmatory`` against
    review_risk_tier, ``escalation-hard-debugging`` against the agent's pin);
  * ``fable`` can NEVER be minted self-serve, whatever the reason;
  * every token is bound to the SHA-256 of the exact prompt text it authorizes
    and cannot be spent by a different dispatch;
  * a token is single-use and expires after 15 minutes;
  * every mint is appended to the durable ``grants.jsonl`` audit trail;
  * the CLI exits non-zero on refusal and mints nothing.

test_model_pin_gate.py covers the gate's decision tree and uses this module as
a fixture; this file pins the minting tool's own contract, so a regression in
rme alone is caught here even when the gate's tests still pass.

Hermetic: every directory is under tmp_path and the CLI subprocess runs with a
throwaway HOME. The real ~/.claude is never read or written.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import model_pin_gate as mpg
import pytest
import record_model_exception as rme

HOOKS_DIR = Path(__file__).resolve().parents[1]

PROMPT = "Review the pending diff for correctness."
OTHER_PROMPT = "Review the pending diff for correctness. Also read firestore.rules."
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

AGENT_FILES = {
    "code-reviewer": "opus",
    "explore": "sonnet",
    "legacy-opus": "opus",
    "scout": "haiku",
}
POLICY_PINS = {
    "code-reviewer": "opus",
    "explore": "sonnet",
    "scout": "haiku",
    # Disagrees with legacy-opus.md's own frontmatter (opus): the file wins.
    "legacy-opus": "sonnet",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def agents_dir(tmp_path: Path) -> str:
    d = tmp_path / "agents"
    d.mkdir()
    for name, model in AGENT_FILES.items():
        (d / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: fixture\nmodel: {model}\ntools: Read\n---\n\nbody\n"
        )
    return str(d)


@pytest.fixture
def policy_path(tmp_path: Path) -> str:
    p = tmp_path / "model_policy.json"
    p.write_text(json.dumps({"agent_pins": POLICY_PINS}))
    return str(p)


@pytest.fixture
def exceptions_dir(tmp_path: Path) -> str:
    # Deliberately not created: minting must create it.
    return str(tmp_path / ".model_exceptions")


@pytest.fixture
def prompt_file(tmp_path: Path):
    n = {"i": 0}

    def _make(text: str = PROMPT) -> str:
        n["i"] += 1
        p = tmp_path / f"prompt_{n['i']}.txt"
        p.write_text(text)
        return str(p)

    return _make


@pytest.fixture
def mint(agents_dir, policy_path, exceptions_dir, prompt_file):
    """mint(agent, model, reason, paths, ...) -> (code, message), via run()."""

    def _mint(agent, model, reason, paths=(), *, prompt=PROMPT, justification="", now=T0):
        return rme.run(
            agent,
            model,
            reason,
            list(paths),
            prompt_file(prompt),
            agents_dir=agents_dir,
            policy_path=policy_path,
            exceptions_dir=exceptions_dir,
            justification=justification,
            now=now,
        )

    return _mint


def _tokens(exceptions_dir: str) -> list:
    if not os.path.isdir(exceptions_dir):
        return []
    return sorted(f for f in os.listdir(exceptions_dir) if f.endswith(".json"))


def _grants(exceptions_dir: str) -> list:
    path = os.path.join(exceptions_dir, mpg.GRANTS_LOG_NAME)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _consume(exceptions_dir, agent, model, prompt, *, now):
    return mpg.find_and_consume_exception(exceptions_dir, agent, model, _sha(prompt), now=now)


# ---------------------------------------------------------------------------
# Mint -> consume
# ---------------------------------------------------------------------------


def test_trivial_mint_writes_a_complete_dispatch_bound_token(mint, exceptions_dir):
    code, message = mint(
        "code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/b.md", "docs/a.md", "docs/a.md"]
    )
    assert code == 0, message
    assert message.startswith("OK minted")

    files = _tokens(exceptions_dir)
    assert len(files) == 1
    with open(os.path.join(exceptions_dir, files[0]), encoding="utf-8") as fh:
        rec = json.load(fh)
    assert rec["agent_type"] == "code-reviewer"
    assert rec["model"] == "sonnet"
    assert rec["reason"] == "trivial-tier-confirmatory"
    assert rec["paths"] == ["docs/a.md", "docs/b.md"]  # sorted, de-duplicated
    assert rec["risk_tier_verdict"].startswith("trivial")
    assert rec["prompt_sha256"] == _sha(PROMPT)
    assert rec["minted_at"] == "2026-01-01T12:00:00Z"
    # Spec: 15-minute single-use TTL.
    assert rec["expires_at"] == "2026-01-01T12:15:00Z"
    # Written atomically: no temp file left behind.
    assert not [f for f in os.listdir(exceptions_dir) if ".tmp" in f]


def test_minted_token_is_consumed_exactly_once(mint, exceptions_dir):
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"])[0] == 0
    now = T0 + timedelta(seconds=30)

    rec = _consume(exceptions_dir, "code-reviewer", "sonnet", PROMPT, now=now)
    assert rec is not None and rec["agent_type"] == "code-reviewer"
    assert _tokens(exceptions_dir) == []  # the gate deletes it: single-use
    assert _consume(exceptions_dir, "code-reviewer", "sonnet", PROMPT, now=now) is None


def test_the_cli_mints_a_token_the_gate_can_consume(tmp_path):
    """End to end through the real entry point with a throwaway HOME: the CLI
    reads the roster and policy from $HOME/.claude, writes the token under
    $HOME/.claude/.model_exceptions, and the gate consumes it."""
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "agents").mkdir(parents=True)
    (claude / "knowledge").mkdir()
    (claude / "agents" / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: opus\ntools: Read\n---\nbody\n"
    )
    (claude / "knowledge" / "model_policy.json").write_text(
        json.dumps({"agent_pins": {"code-reviewer": "opus"}})
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(PROMPT)

    env = {k: v for k, v in os.environ.items() if not k.startswith(("CSA_", "CLAUDE_"))}
    env["HOME"] = str(home)

    def cli(*args):
        return subprocess.run(
            [sys.executable, str(HOOKS_DIR / "record_model_exception.py"), *args],
            cwd=str(tmp_path),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )

    ok = cli(
        "--agent", "code-reviewer", "--model", "sonnet",
        "--reason", "trivial-tier-confirmatory",
        "--paths", "docs/readme.md",
        "--prompt-file", str(prompt),
    )  # fmt: skip
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "OK minted" in ok.stdout

    exc_dir = str(claude / ".model_exceptions")
    assert len(_tokens(exc_dir)) == 1
    rec = mpg.find_and_consume_exception(exc_dir, "code-reviewer", "sonnet", _sha(PROMPT))
    assert rec is not None

    # A refusal exits non-zero (unlike a hook, which always exits 0), says why on
    # stderr, and mints nothing.
    bad = cli(
        "--agent", "code-reviewer", "--model", "sonnet",
        "--reason", "trivial-tier-confirmatory",
        "--paths", "modules/widget.py",
        "--prompt-file", str(prompt),
    )  # fmt: skip
    assert bad.returncode != 0
    assert "trivial" in bad.stderr
    assert _tokens(exc_dir) == []


# ---------------------------------------------------------------------------
# TTL
# ---------------------------------------------------------------------------


def test_token_is_honoured_up_to_its_expiry_and_dead_after(mint, exceptions_dir):
    """Recoverability pair: inside the 15-minute window the token works; at and
    after the expiry the same token does not, and is cleaned up."""
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"])[0] == 0
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/y.md"])[0] == 0
    first, second = _tokens(exceptions_dir)

    inside = T0 + timedelta(minutes=15) - timedelta(seconds=1)
    assert _consume(exceptions_dir, "code-reviewer", "sonnet", PROMPT, now=inside) is not None

    expired = T0 + timedelta(minutes=15)
    assert _consume(exceptions_dir, "code-reviewer", "sonnet", PROMPT, now=expired) is None
    assert _tokens(exceptions_dir) == []  # the stale second token was pruned, not kept
    assert first != second


def test_mint_token_honours_an_explicit_ttl(exceptions_dir):
    rec = rme.mint_token(
        exceptions_dir,
        "explore",
        "opus",
        rme.REASON_ESCALATION,
        [],
        None,
        _sha(PROMPT),
        justification="why",
        now=T0,
        ttl_seconds=60,
    )
    assert rec["expires_at"] == "2026-01-01T12:01:00Z"


# ---------------------------------------------------------------------------
# Dispatch binding
# ---------------------------------------------------------------------------


def test_token_cannot_be_spent_by_a_different_prompt(mint, exceptions_dir):
    """The incident this binding closes: a token minted for one review's prompt
    was spent authorizing a different review with the same agent and model."""
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"], prompt=PROMPT)[0] == 0
    now = T0 + timedelta(seconds=5)

    assert _consume(exceptions_dir, "code-reviewer", "sonnet", OTHER_PROMPT, now=now) is None
    assert len(_tokens(exceptions_dir)) == 1  # not spent by the wrong dispatch

    # Recovery: the dispatch it was minted for still gets it.
    assert _consume(exceptions_dir, "code-reviewer", "sonnet", PROMPT, now=now) is not None


def test_token_does_not_match_another_agent_or_model(mint, exceptions_dir):
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"])[0] == 0
    now = T0 + timedelta(seconds=5)
    assert _consume(exceptions_dir, "explore", "sonnet", PROMPT, now=now) is None
    assert _consume(exceptions_dir, "code-reviewer", "haiku", PROMPT, now=now) is None
    assert len(_tokens(exceptions_dir)) == 1


def test_prompt_hash_is_sha256_of_the_exact_file_bytes(prompt_file):
    text = "line one\nline two with unicode é\n"
    assert rme.read_prompt_hash(prompt_file(text)) == _sha(text)
    # Whitespace matters: this binds bytes, not meaning.
    assert rme.read_prompt_hash(prompt_file(text + " ")) != _sha(text)


def test_unreadable_prompt_file_refuses_and_mints_nothing(
    agents_dir, policy_path, exceptions_dir, tmp_path
):
    assert rme.read_prompt_hash(str(tmp_path / "missing.txt")) is None
    code, message = rme.run(
        "code-reviewer",
        "sonnet",
        rme.REASON_TRIVIAL,
        ["docs/x.md"],
        str(tmp_path / "missing.txt"),
        agents_dir=agents_dir,
        policy_path=policy_path,
        exceptions_dir=exceptions_dir,
    )
    assert code != 0 and "prompt" in message.lower()
    assert _tokens(exceptions_dir) == []
    assert _grants(exceptions_dir) == []


# ---------------------------------------------------------------------------
# fable: never self-serve
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason, agent, paths, justification",
    [
        (rme.REASON_ESCALATION, "explore", [], "genuinely hard problem"),
        (rme.REASON_TRIVIAL, "code-reviewer", ["docs/x.md"], ""),
    ],
)
def test_fable_is_refused_for_every_reason_and_nothing_is_written(
    mint, exceptions_dir, reason, agent, paths, justification
):
    code, message = mint(agent, "fable", reason, paths, justification=justification)
    assert code != 0
    assert "fable" in message and "grant_model_exception.sh" in message
    assert _tokens(exceptions_dir) == []
    assert _grants(exceptions_dir) == []


@pytest.mark.parametrize(
    "reason, agent, paths",
    [
        (rme.REASON_ESCALATION, "explore", []),
        (rme.REASON_TRIVIAL, "code-reviewer", ["docs/x.md"]),
    ],
)
def test_the_fable_refusal_does_not_depend_on_the_per_reason_verifiers(
    mint, exceptions_dir, monkeypatch, reason, agent, paths
):
    """Even if a per-reason verifier were wrong or permissive, run() must still
    refuse fable on its own, before any verifier is consulted. The verifiers are
    forced to accept using their real return shapes: verify_escalation returns
    (ok, message) and verify_trivial returns (ok, message, risk_tier_verdict)."""
    monkeypatch.setattr(rme, "verify_escalation", lambda model, pin: (True, "ok"))
    monkeypatch.setattr(rme, "verify_trivial", lambda paths: (True, "ok", "trivial: stubbed"))
    code, message = mint(
        agent, mpg.FABLE_MODEL, reason, paths, justification="genuinely hard problem"
    )
    assert code != 0
    assert "grant_model_exception.sh" in message
    assert _tokens(exceptions_dir) == []
    assert _grants(exceptions_dir) == []


def test_a_hand_crafted_fable_token_is_never_consumed_by_the_gate(exceptions_dir):
    """Defence in depth on the consuming side: even a token that should not exist
    is ignored (and left untouched) for a fable target."""
    rec = rme.mint_token(
        exceptions_dir,
        "explore",
        mpg.FABLE_MODEL,
        rme.REASON_ESCALATION,
        [],
        None,
        _sha(PROMPT),
        justification="forged",
        now=T0,
    )
    assert rec["model"] == "fable"
    now = T0 + timedelta(seconds=5)
    assert _consume(exceptions_dir, "explore", "fable", PROMPT, now=now) is None
    assert len(_tokens(exceptions_dir)) == 1


# ---------------------------------------------------------------------------
# Reason vocabulary and per-reason verification
# ---------------------------------------------------------------------------


def test_reason_vocabulary_is_closed_to_exactly_two_values(mint, exceptions_dir):
    assert set(rme.REASONS) == {"trivial-tier-confirmatory", "escalation-hard-debugging"}
    choices = next(a for a in rme.build_parser()._actions if a.dest == "reason").choices
    assert set(choices) == set(rme.REASONS)

    for bogus in ("operator-directed", "because-i-said-so", ""):
        code, message = mint("code-reviewer", "sonnet", bogus, ["docs/x.md"])
        assert code != 0 and "must be one of" in message
    assert _tokens(exceptions_dir) == []


def test_the_environment_cannot_authorize_a_mint(mint, exceptions_dir, monkeypatch):
    """The removed operator-directed reason trusted an env var the calling agent
    could set itself. No environment value may stand in for verification now."""
    monkeypatch.setenv("CSA_MODEL_EXCEPTION", "1")
    code, _ = mint("code-reviewer", "sonnet", "operator-directed", ["modules/widget.py"])
    assert code != 0
    code, _ = mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["modules/widget.py"])
    assert code != 0
    assert _tokens(exceptions_dir) == []


@pytest.mark.parametrize(
    "path",
    [
        "modules/some_widget.py",  # moderate: ordinary source
        "hooks/anything.py",  # high: a hooks/ path
        "settings.json",  # high
    ],
)
def test_trivial_reason_refuses_any_non_trivial_pathspec(mint, exceptions_dir, path):
    code, message = mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, [path])
    assert code != 0 and "trivial" in message
    assert _tokens(exceptions_dir) == []


def test_trivial_reason_refuses_when_one_path_in_the_set_is_risky(mint, exceptions_dir):
    """The whole pathspec is classified: a docs file cannot carry a hooks/ file."""
    code, _ = mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md", "hooks/y.py"])
    assert code != 0
    assert _tokens(exceptions_dir) == []


def test_trivial_reason_with_no_paths_does_not_mint(mint, exceptions_dir):
    code, _ = mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, [])
    assert code != 0
    assert _tokens(exceptions_dir) == []


def test_escalation_needs_a_non_blank_justification(mint, exceptions_dir):
    for blank in ("", "   ", "\n"):
        code, message = mint("explore", "opus", rme.REASON_ESCALATION, justification=blank)
        assert code != 0 and "justification" in message
    assert _tokens(exceptions_dir) == []


def test_escalation_mints_from_sonnet_to_opus_and_logs_the_justification(
    sandbox, mint, exceptions_dir
):
    code, message = mint(
        "explore", "opus", rme.REASON_ESCALATION, justification="sonnet failed twice on the race"
    )
    assert code == 0, message
    rec = _grants(exceptions_dir)[0]
    assert rec["reason"] == "escalation-hard-debugging"
    assert rec["justification"] == "sonnet failed twice on the race"
    assert rec["risk_tier_verdict"] is None  # no tier verification for this reason

    rows = [json.loads(line) for line in sandbox.log_file.read_text().splitlines() if line.strip()]
    logged = [r for r in rows if r.get("decision") == "mint-escalation"]
    assert len(logged) == 1
    assert logged[0]["justification"] == "sonnet failed twice on the race"
    assert logged[0]["agent_type"] == "explore"


@pytest.mark.parametrize(
    "agent, model",
    [
        ("code-reviewer", "opus"),  # already opus-pinned: cannot escalate further
        ("explore", "sonnet"),  # lateral, not upward
        ("explore", "haiku"),  # downward
        ("scout", "opus"),  # upward, but only a sonnet-pinned agent may escalate
        ("no-such-agent", "opus"),  # no known pin to verify direction against
    ],
)
def test_escalation_is_refused_unless_it_is_sonnet_to_a_higher_tier(
    mint, exceptions_dir, agent, model
):
    code, _ = mint(agent, model, rme.REASON_ESCALATION, justification="needed")
    assert code != 0
    assert _tokens(exceptions_dir) == []


def test_the_agent_files_own_pin_beats_the_policy_pin(mint, exceptions_dir):
    """legacy-opus.md says opus while the policy says sonnet. The pin the client
    actually applies is the file's, so escalation FROM it is refused."""
    code, _ = mint("legacy-opus", "opus", rme.REASON_ESCALATION, justification="needed")
    assert code != 0
    assert _tokens(exceptions_dir) == []


def test_unreadable_policy_or_roster_refuses_rather_than_minting(
    agents_dir, exceptions_dir, prompt_file, tmp_path
):
    common = dict(exceptions_dir=exceptions_dir)
    code, message = rme.run(
        "code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"], prompt_file(),
        agents_dir=agents_dir, policy_path=str(tmp_path / "missing.json"), **common,
    )  # fmt: skip
    assert code != 0 and "policy" in message

    good_policy = tmp_path / "ok.json"
    good_policy.write_text(json.dumps({"agent_pins": POLICY_PINS}))
    code, message = rme.run(
        "code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/x.md"], prompt_file(),
        agents_dir=str(tmp_path / "no-such-dir"), policy_path=str(good_policy), **common,
    )  # fmt: skip
    assert code != 0 and "agents dir" in message
    assert _tokens(exceptions_dir) == []


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_every_mint_is_appended_to_a_durable_grant_log(mint, exceptions_dir):
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/a.md"], prompt="one")[0] == 0
    assert mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["docs/b.md"], prompt="two")[0] == 0
    assert len(_grants(exceptions_dir)) == 2

    # Consuming the first token must not touch the audit trail.
    _consume(exceptions_dir, "code-reviewer", "sonnet", "one", now=T0 + timedelta(seconds=1))
    grants = _grants(exceptions_dir)
    assert [g["prompt_sha256"] for g in grants] == [_sha("one"), _sha("two")]
    assert [g["paths"] for g in grants] == [["docs/a.md"], ["docs/b.md"]]


def test_a_refused_mint_leaves_no_audit_row(mint, exceptions_dir):
    mint("code-reviewer", "sonnet", rme.REASON_TRIVIAL, ["modules/some_widget.py"])
    assert _grants(exceptions_dir) == []
