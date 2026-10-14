"""Tests for identity on enforcement rows — telemetry plan §4.2 item 4a and
§4.2a's `repo` field.

WHAT THE SPEC SAYS (agent_telemetry_dashboard_plan.md §4.2 4a / §4.2a, and
correction rows C2/C3/C4). These tests assert THAT, not whatever the code
currently emits:

  1. `_lib.log()` grows THREE explicit optional kwargs — `session`,
     `agent_type`, `repo` — rather than threading the event payload through
     all 93 existing call sites or parking it in a module-level global.
  2. Wiring happens at exactly TWO registered PreToolUse entry points that
     actually parse the payload: `pretooluse_bash.main` and
     `pretooluse_task.main`.
  3. PAYLOAD ASYMMETRY (round-3 R9): `agent_type` derives from
     `tool_input.subagent_type`, which exists ONLY on a Task payload. A Bash
     payload describes a shell command, not a dispatch — so pretooluse_bash
     contributes `session` + `repo` ONLY and must NEVER fabricate an
     agent_type.
  4. When `session_id()` returns the "nosession" sentinel, the field is
     OMITTED — never written.
  5. `file_claims.py` is a LIBRARY with zero `log()` calls; the change adds
     none (C3 — rev 2's wrong target list).
  6. The path is FAIL-OPEN: a telemetry failure degrades to "no field", never
     to a deny and never to a crash.
  7. Backward compatibility: a `log()` call passing none of the three behaves
     exactly as before, for all 93 existing call sites.

The falsifiability bar (CLAUDE.md §6): each test below is written to go RED
against the pre-change source. The ones that would pass either way are
labelled as regression guards in their own docstrings and say what they pin.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys

import pytest

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402
import pretooluse_bash as ptb  # noqa: E402
import pretooluse_task as ptt  # noqa: E402

# ===========================================================================
# Helpers.
# ===========================================================================


def _read_log(sandbox) -> list[dict]:
    """The parsed JSONL decision-log records (empty list if the file is absent)."""
    if not sandbox.log_file.exists():
        return []
    return [
        json.loads(line)
        for line in sandbox.log_file.read_text().strip().splitlines()
        if line
    ]


def _last(sandbox) -> dict:
    rows = _read_log(sandbox)
    assert rows, "expected at least one enforcement row"
    return rows[-1]


def _git_repo(tmp_path, name="repo"):
    """A real git repo with one commit, so `git rev-parse --show-toplevel`
    resolves. Uses a real repo rather than a monkeypatched resolver because
    the `repo` field's whole purpose (§4.2a) is that the row can be joined to
    a real repo — a faked resolver would not prove the wiring reaches one.
    """
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t.co",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t.co",
    }
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    (root / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "add", "seed.txt"], cwd=root, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=root, check=True, env=env
    )
    # macOS /tmp is a symlink to /private/tmp; git reports the resolved path.
    return os.path.realpath(str(root))


def _run_bash_main(monkeypatch, payload, *, env=None):
    """Feed a payload to pretooluse_bash.main() via stdin; return (rc, stdout)."""
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = ptb.main()
    return rc, buf.getvalue()


def _run_task_main(monkeypatch, payload, *, env=None):
    """Feed a payload to pretooluse_task.main() via stdin; return (rc, stdout)."""
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = ptt.main()
    return rc, buf.getvalue()


def _assert_no_sentinel_value(rec: dict) -> None:
    """No FIELD VALUE in the row equals the "nosession" sentinel.

    Deliberately a per-value check rather than a substring scan of the
    serialized row: pytest's tmp_path is derived from the test's own name, so
    a test named "...nosession..." puts that literal into the `repo` path and
    makes a `sentinel in json.dumps(rec)` assertion fail for a reason that has
    nothing to do with the behavior under test. Caught exactly that way while
    writing these tests.
    """
    for key, value in rec.items():
        assert value != _lib.NO_SESSION_SENTINEL, (
            f"field {key!r} carries the nosession sentinel"
        )


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


def _bash_ev(command, *, cwd=None, session_id=None, tool_name="Bash"):
    ev: dict = {"tool_name": tool_name, "tool_input": {"command": command}}
    if cwd is not None:
        ev["cwd"] = cwd
    if session_id is not None:
        ev["session_id"] = session_id
    return ev


# A gate-1 (block_branch_ops) trigger: always blocks, needs no repo state, and
# is NOT a `git commit`, so it exercises the UNGUARDED path where resolve_block
# deliberately resolves no repo root of its own.
BRANCH_OP = "git checkout -b feature"


# ===========================================================================
# _lib.subagent_type — the accessor the asymmetry rests on.
# ===========================================================================


class TestSubagentTypeAccessor:
    def test_reads_tool_input_subagent_type(self):
        assert _lib.subagent_type({"tool_input": {"subagent_type": "explore"}}) == "explore"

    def test_absent_on_a_bash_payload(self):
        """SPEC (R9): a Bash payload describes a shell command, not a dispatch.
        There is no agent type to read, and the accessor must say so with ""
        rather than inventing one."""
        assert _lib.subagent_type({"tool_input": {"command": "git status"}}) == ""

    @pytest.mark.parametrize(
        "ev",
        [
            {},
            {"tool_input": None},
            {"tool_input": "not-a-dict"},
            {"tool_input": {"subagent_type": 42}},
            {"tool_input": {"subagent_type": None}},
        ],
    )
    def test_degrades_to_empty_never_raises(self, ev):
        assert _lib.subagent_type(ev) == ""

    def test_never_raises_when_get_itself_raises(self):
        class Hostile(dict):
            def get(self, *a, **k):
                raise RuntimeError("boom")

        assert _lib.subagent_type(Hostile()) == ""


# ===========================================================================
# _lib.identity_or_none — the "" -> omitted normalization new callers use.
# ===========================================================================


class TestIdentityOrNone:
    def test_empty_string_becomes_none_so_the_field_is_omitted(self):
        assert _lib.identity_or_none("") is None

    def test_real_value_passes_through(self):
        assert _lib.identity_or_none("/repo") == "/repo"

    @pytest.mark.parametrize("bad", [None, 42, [], {}])
    def test_non_str_becomes_none(self, bad):
        assert _lib.identity_or_none(bad) is None


# ===========================================================================
# _lib.log — the three explicit kwargs (plan §4.2 4a, correction C2).
# ===========================================================================


class TestLogIdentityKwargs:
    def test_all_three_are_explicit_keyword_params_not_just_kwargs(self):
        """SPEC (C2 + 4a): the design is EXPLICIT optional kwargs on log(),
        chosen over threading `ev` through 93 call sites. A signature that
        merely swallowed these in **fields would satisfy the row-content
        tests below but not the design, and would leave the omission rules
        duplicated at every call site."""
        import inspect

        params = inspect.signature(_lib.log).parameters
        for name in ("session", "agent_type", "repo"):
            assert name in params, f"{name} must be an explicit parameter of log()"
            assert params[name].default is None
            assert params[name].kind is inspect.Parameter.KEYWORD_ONLY

    def test_writes_all_three_when_supplied(self, sandbox, clean_env):
        _lib.log("h", "would-block", session="sess-1", agent_type="explore", repo="/r")
        rec = _last(sandbox)
        assert rec["session"] == "sess-1"
        assert rec["agent_type"] == "explore"
        assert rec["repo"] == "/r"

    def test_nosession_sentinel_is_omitted_entirely(self, sandbox, clean_env):
        """SPEC (4a, verbatim): "When session_id returns the 'nosession'
        sentinel, OMIT the field — never write it." A written sentinel is
        indistinguishable from a real session id at read time and would
        silently corrupt every per-session aggregation the field exists for."""
        _lib.log("h", "would-block", session=_lib.NO_SESSION_SENTINEL, repo="/r")
        rec = _last(sandbox)
        assert "session" not in rec
        # The sentinel must not have leaked into a neighbouring field either.
        _assert_no_sentinel_value(rec)
        assert rec["repo"] == "/r"

    def test_a_real_session_id_is_still_written(self, sandbox, clean_env):
        """Companion negative case: guards against an over-eager omission rule
        that drops every session, which would pass the test above vacuously."""
        _lib.log("h", "would-block", session="sess-real")
        assert _last(sandbox)["session"] == "sess-real"

    def test_none_omits_each_field_independently(self, sandbox, clean_env):
        _lib.log("h", "would-block", session="s", agent_type=None, repo=None)
        rec = _last(sandbox)
        assert rec["session"] == "s"
        assert "agent_type" not in rec
        assert "repo" not in rec

    def test_identity_does_not_clobber_an_unrelated_caller_field(
        self, sandbox, clean_env
    ):
        """Identity is applied BEFORE **fields (log()'s ordering contract), so
        it can never overwrite what a caller supplied.

        NOTE on what is NOT asserted here: a direct collision — passing `repo`
        as both an identity kwarg and a **fields entry — is unreachable in
        Python (`TypeError: got multiple values for keyword argument 'repo'`),
        because the explicit parameter absorbs the name. So the collision case
        the ordering protects against cannot actually occur through the public
        signature, and claiming a test for it would be claiming a test of
        something untestable. What IS testable, and asserted: identity fields
        coexist with caller fields without either being lost."""
        _lib.log("h", "d", repo="/r", session="s", reason="mine", command="git x")
        rec = _last(sandbox)
        assert rec["repo"] == "/r"
        assert rec["session"] == "s"
        assert rec["reason"] == "mine"
        assert rec["command"] == "git x"


class TestLogBackwardCompatibility:
    """The 93 pre-existing call sites pass none of the three. Their rows must
    be byte-identical to what they were before this change."""

    def test_call_with_no_identity_kwargs_writes_no_identity_fields(
        self, sandbox, clean_env
    ):
        _lib.log("git_guard", "would-block", reason="state-verb:reset", command="git reset")
        rec = _last(sandbox)
        for name in ("session", "agent_type", "repo"):
            assert name not in rec
        # And everything the row carried before is untouched.
        assert rec["hook"] == "git_guard"
        assert rec["decision"] == "would-block"
        assert rec["reason"] == "state-verb:reset"
        assert rec["command"] == "git reset"
        assert rec["enforce"] is False
        assert "ts" in rec

    def test_record_key_set_is_exactly_the_legacy_set(self, sandbox, clean_env):
        """Stronger form: not just "no identity keys" but no NEW keys at all,
        so a future field can't be added to every row unnoticed."""
        _lib.log("git_guard", "would-block", reason="r")
        assert set(_last(sandbox)) == {"ts", "hook", "decision", "enforce", "reason"}

    def test_legacy_caller_passing_repo_still_lands_verbatim(self, sandbox, clean_env):
        """`repo=` now BINDS to the new explicit parameter instead of landing
        in **fields (pre-existing callers: record_review.py:2321,
        record_plan_review.py:209, pretooluse_bash.py:1228). That rebinding
        must be observationally inert."""
        _lib.log("record_review", "recorded", repo="/repo", head="abc", outcome="clean")
        rec = _last(sandbox)
        assert rec["repo"] == "/repo"
        assert rec["head"] == "abc"
        assert rec["outcome"] == "clean"

    def test_legacy_empty_repo_is_still_written_not_dropped(self, sandbox, clean_env):
        """The sharp edge of that rebinding. `record_review.Decision.repo_root`
        defaults to "" (record_review.py:311) and reaches log() on the
        not-a-dir/not-a-repo branches; record_plan_review.py:209's no-outcome
        branch fires exactly when its target is falsy. Both wrote `repo: ""`
        before this change, so both must still write it — the "" -> omitted
        rule belongs to `identity_or_none()`, which only NEW callers use."""
        _lib.log("record_review", "not-a-repo", target="/nope", repo="")
        rec = _last(sandbox)
        assert "repo" in rec
        assert rec["repo"] == ""

    def test_legacy_caller_passing_agent_type_still_lands(self, sandbox, clean_env):
        """record_model_exception.py:397 passes agent_type= and predates this
        change."""
        _lib.log("record_model_exception", "mint-escalation", agent_type="explore", model="sonnet")
        rec = _last(sandbox)
        assert rec["agent_type"] == "explore"
        assert rec["model"] == "sonnet"


class TestLogIdentityKillSwitch:
    def test_kill_switch_suppresses_only_the_identity_fields(self, sandbox, clean_env):
        clean_env.setenv(_lib.IDENTITY_KILL_SWITCH, "1")
        _lib.log("h", "would-block", session="s", agent_type="a", repo="/r", reason="x")
        rec = _last(sandbox)
        for name in ("session", "agent_type", "repo"):
            assert name not in rec
        # The row itself, and every other field, survive.
        assert rec["hook"] == "h"
        assert rec["decision"] == "would-block"
        assert rec["reason"] == "x"

    def test_default_is_identity_on(self, sandbox, clean_env):
        """Companion positive case, so the suppression test above cannot pass
        because identity is off by default."""
        assert _lib.log_identity_enabled() is True
        _lib.log("h", "would-block", session="s")
        assert _last(sandbox)["session"] == "s"

    def test_only_the_exact_value_1_disables(self, sandbox, clean_env):
        clean_env.setenv(_lib.IDENTITY_KILL_SWITCH, "0")
        assert _lib.log_identity_enabled() is True
        clean_env.setenv(_lib.IDENTITY_KILL_SWITCH, "true")
        assert _lib.log_identity_enabled() is True


class TestLogFailOpen:
    """SPEC (§4.2, verbatim): "All three inherit _lib.log()'s fail-open
    contract explicitly (any failure swallowed; logging must never break a
    hook)." A telemetry failure degrades to "no field", never to a crash."""

    def test_identity_failure_does_not_lose_the_row(
        self, sandbox, clean_env, monkeypatch
    ):
        def boom(*a, **k):
            raise RuntimeError("identity exploded")

        monkeypatch.setattr(_lib, "_identity_fields", boom)
        _lib.log("h", "would-block", session="s", reason="still-here")
        rec = _last(sandbox)
        assert rec["reason"] == "still-here"
        assert "session" not in rec

    def test_kill_switch_read_failure_does_not_lose_the_row(
        self, sandbox, clean_env, monkeypatch
    ):
        def boom(*a, **k):
            raise RuntimeError("env exploded")

        monkeypatch.setattr(_lib, "log_identity_enabled", boom)
        _lib.log("h", "would-block", session="s", reason="still-here")
        assert _last(sandbox)["reason"] == "still-here"

    def test_log_never_raises_with_identity_supplied(self, sandbox, clean_env, monkeypatch):
        """The pre-existing unwritable-dir guarantee still holds on the
        identity path."""
        def boom(*a, **k):
            raise OSError("nope")

        monkeypatch.setattr(_lib.os, "makedirs", boom)
        _lib.log("h", "d", session="s", agent_type="a", repo="/r")  # must not raise

    def test_unencodable_identity_value_does_not_lose_the_row(
        self, sandbox, clean_env
    ):
        class Weird:
            pass

        # default=str in log()'s json.dumps handles this; the row must survive.
        _lib.log("h", "would-block", repo=Weird(), reason="still-here")
        assert _last(sandbox)["reason"] == "still-here"


# ===========================================================================
# pretooluse_bash — contributes session + repo ONLY (never agent_type).
# ===========================================================================


class TestBashEntryPointIdentity:
    def test_block_row_carries_session_and_repo(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        rc, out = _run_bash_main(
            monkeypatch, _bash_ev(BRANCH_OP, cwd=repo, session_id="sess-bash")
        )
        assert rc == 0
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        assert rec["session"] == "sess-bash"
        assert rec["repo"] == repo

    def test_block_row_NEVER_carries_agent_type(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """SPEC (R9, the payload asymmetry): a PreToolUse:Bash payload
        describes a shell command, not a dispatch. `tool_input.subagent_type`
        does not exist on it, so this entry point must contribute NO
        agent_type — not "", not "unknown", not one inferred from anything.
        Fabricating one is the specific failure this pins.

        FALSIFIABILITY, stated honestly: this passes against the PRE-change
        source too, because pre-change no row carried ANY identity field. It
        is a forward regression guard, not a detector of this change — its
        value is that it fails the moment someone "completes" the symmetry by
        adding an agent_type here. Verified RED against a deliberately
        symmetric variant while writing it."""
        repo = _git_repo(tmp_path)
        _run_bash_main(monkeypatch, _bash_ev(BRANCH_OP, cwd=repo, session_id="s"))
        rec = _last(sandbox)
        assert "agent_type" not in rec

    def test_agent_type_is_not_smuggled_in_from_a_bash_payload(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """Adversarial: even if a Bash payload somehow carried a
        subagent_type key, this entry point must not read it — the field is
        meaningless there and would misattribute the denial.

        Same falsifiability note as the test above: a forward regression
        guard. Verified RED against a scratch build whose Bash-side identity
        fabricated an agent_type."""
        repo = _git_repo(tmp_path)
        ev = _bash_ev(BRANCH_OP, cwd=repo, session_id="s")
        ev["tool_input"]["subagent_type"] = "smuggled-agent"
        _run_bash_main(monkeypatch, ev)
        rec = _last(sandbox)
        assert "agent_type" not in rec
        assert "smuggled-agent" not in json.dumps(rec)

    def test_missing_session_id_omits_the_field(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """A payload with no session must produce NO session field, not the
        "nosession" sentinel (plan §4.2 4a)."""
        repo = _git_repo(tmp_path)
        _run_bash_main(monkeypatch, _bash_ev(BRANCH_OP, cwd=repo))
        rec = _last(sandbox)
        assert "session" not in rec
        _assert_no_sentinel_value(rec)
        # repo still lands — omission is per-field, not all-or-nothing.
        assert rec["repo"] == repo

    def test_non_repo_cwd_omits_repo_but_keeps_session(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """An unresolvable repo root is an ABSENCE, so the field is omitted
        rather than written as "" — a "" repo would pollute the §4.2a
        per-repo join with a bucket that means nothing."""
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        _run_bash_main(
            monkeypatch, _bash_ev(BRANCH_OP, cwd=str(outside), session_id="s-only")
        )
        rec = _last(sandbox)
        assert rec["session"] == "s-only"
        assert "repo" not in rec

    def test_repo_lands_on_a_commit_gate_denial(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """§4.2a's actual motivating case: the COMMIT-blocking denials (the
        friction ratio's numerator) are the rows that carried no repo and no
        cwd across all 2,234 historical file_claims rows. A bulk-pathspec
        denial is a guarded `git commit`, i.e. the path where resolve_block
        resolves a repo root of its own and hands it to _finish."""
        repo = _git_repo(tmp_path)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev('git commit -m "x" -- .', cwd=repo, session_id="sess-commit"),
        )
        assert rc == 0
        rows = [r for r in _read_log(sandbox) if r.get("decision") == "would-block"]
        assert rows, "expected a commit-gate would-block row"
        rec = rows[-1]
        assert rec["repo"] == repo
        assert rec["session"] == "sess-commit"
        assert "agent_type" not in rec

    def test_escape_allowed_row_also_carries_identity(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """The escape-hatch row is an enforcement row too; leaving it
        un-attributed would silently hide exactly the events most worth
        attributing."""
        repo = _git_repo(tmp_path)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev(BRANCH_OP, cwd=repo, session_id="sess-escape"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1"},
        )
        assert rc == 0
        rec = _last(sandbox)
        assert rec["decision"] == "escape-allowed"
        assert rec["session"] == "sess-escape"
        assert rec["repo"] == repo
        assert "agent_type" not in rec

    def test_allowed_command_still_logs_nothing(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """Regression guard (would pass pre-change too): identity must not
        cause a row to be written for a command no gate blocked. Pins that
        the new code sits strictly on the block path."""
        repo = _git_repo(tmp_path)
        rc, out = _run_bash_main(
            monkeypatch, _bash_ev("echo hello", cwd=repo, session_id="s")
        )
        assert rc == 0
        assert not _is_deny(out)
        assert _read_log(sandbox) == []

    def test_kill_switch_strips_identity_from_a_real_denial(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev(BRANCH_OP, cwd=repo, session_id="s"),
            env={_lib.IDENTITY_KILL_SWITCH: "1"},
        )
        assert rc == 0
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        assert rec["gate"] == "block_branch_ops"
        for name in ("session", "agent_type", "repo"):
            assert name not in rec


class TestBashEntryPointFailOpen:
    """SPEC: "This path is FAIL-OPEN by design. Your change must NEVER be able
    to deny or crash a command that would otherwise be allowed."

    The strong form of that guarantee is tested here by making the identity
    code itself explode and asserting the gate's decision is unchanged in BOTH
    directions — an allowed command stays allowed, and a denied command stays
    denied with its message intact."""

    @staticmethod
    def _explode(monkeypatch):
        """Break the INNER `_identity`, leaving `_identity_safe` in place.

        This is the honest shape of the guarantee. The identity dict is
        splatted into `_lib.log(**...)`, and a splat is evaluated BEFORE log()
        is entered — so an exception raised while building it escapes every
        guard inside log() and crashes the hook process. `_identity_safe`'s
        outer try/except is the only thing standing between a telemetry bug
        and a changed command outcome, and patching the inner function is what
        actually exercises it. (Patching `_identity_safe` itself would test
        nothing but the patch.)"""

        def boom(*a, **k):
            raise RuntimeError("identity exploded")

        monkeypatch.setattr(ptb, "_identity", boom)

    def test_allowed_command_stays_allowed_when_identity_explodes(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        self._explode(monkeypatch)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev("echo hello", cwd=repo, session_id="s"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert not _is_deny(out)

    def test_denied_command_stays_denied_when_identity_explodes(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """The other half of "never changes the decision": a failure in
        telemetry must not accidentally RESCUE a command the gate blocked."""
        repo = _git_repo(tmp_path)
        self._explode(monkeypatch)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev(BRANCH_OP, cwd=repo, session_id="s"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert _is_deny(out)
        assert "block_branch_ops" in out

    def test_repo_resolution_failure_degrades_to_no_field(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """A hanging/failing `git rev-parse` must cost the repo field only."""
        repo = _git_repo(tmp_path)

        def boom(*a, **k):
            raise RuntimeError("git exploded")

        monkeypatch.setattr(ptb.ct, "repo_root_of", boom)
        rc, out = _run_bash_main(
            monkeypatch,
            _bash_ev(BRANCH_OP, cwd=repo, session_id="s-survives"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0
        assert _is_deny(out)
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        assert rec["session"] == "s-survives"
        assert "repo" not in rec

    def test_session_resolution_failure_degrades_to_no_field(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)

        def boom(*a, **k):
            raise RuntimeError("session exploded")

        monkeypatch.setattr(ptb._lib, "session_id", boom)
        rc, out = _run_bash_main(
            monkeypatch, _bash_ev(BRANCH_OP, cwd=repo, session_id="s")
        )
        assert rc == 0
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        assert "session" not in rec
        assert rec["repo"] == repo

    def test_identity_never_denies_on_its_own(self, sandbox, clean_env, tmp_path, monkeypatch):
        """Regression guard: no combination of identity inputs may produce a
        deny for a command every gate allows."""
        repo = _git_repo(tmp_path)
        for sess in (None, "s", _lib.NO_SESSION_SENTINEL):
            rc, out = _run_bash_main(
                monkeypatch,
                _bash_ev("echo ok", cwd=repo, session_id=sess),
                env={"CSA_ENFORCE": "1"},
            )
            assert rc == 0
            assert not _is_deny(out)


class TestDetailKeyCollision:
    """A gate's `detail` dict can already contain a key the identity fields
    also use. Splatting two dicts into one call (`**identity, **detail`)
    raises `TypeError: got multiple values for keyword argument` on any shared
    key — which CRASHES the hook, and under enforcement converts a would-be
    DENY into an unguarded ALLOW. That is the exact fail-open violation the
    plan forbids, and it is not hypothetical: gate 5 (gh_issue_close_gate)
    puts a `repo` key in its detail (gh_issue_close_gate.py:686) holding a
    GitHub owner/name SLUG, a different thing from this module's filesystem
    repo ROOT. Found by the pre-existing suite, pinned here."""

    def test_gh_issue_close_detail_repo_does_not_crash_the_hook(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        block = ptb._Block("gh_issue_close_gate", "fabricated-resolution", "msg", git_state=False)
        # The detail shape _gh_issue_close_block ACTUALLY produces: gicg.decide's
        # own "command" key is stripped at pretooluse_bash.py:753 (an existing
        # precedent for this very collision class — _finish passes `command`
        # explicitly), while "repo" is NOT stripped and reaches _finish.
        detail = {"repo": "owner/name", "commits": []}
        rc = ptb._finish(
            block, detail, "gh issue close 1", repo, ev=_bash_ev("x", cwd=repo, session_id="s"),
            repo_root=repo,
        )
        assert rc == 0
        rec = _last(sandbox)
        # The GATE's own repo value wins — the row keeps its slug, unchanged.
        assert rec["repo"] == "owner/name"
        assert rec["session"] == "s"

    def test_detail_wins_every_collision(self, sandbox, clean_env, tmp_path):
        """Generalized: whatever a gate puts in detail is authoritative for its
        row, so this telemetry change can never alter a pre-existing field."""
        repo = _git_repo(tmp_path)
        merged = ptb._log_fields(
            _bash_ev("x", cwd=repo, session_id="s"), repo, repo,
            {"repo": "gate-value", "session": "gate-session"},
        )
        assert merged["repo"] == "gate-value"
        assert merged["session"] == "gate-session"

    def test_identity_survives_when_detail_does_not_collide(
        self, sandbox, clean_env, tmp_path
    ):
        """Companion positive case, so the collision rule above cannot pass by
        dropping identity wholesale."""
        repo = _git_repo(tmp_path)
        merged = ptb._log_fields(
            _bash_ev("x", cwd=repo, session_id="s"), repo, repo, {"gate": "g"}
        )
        assert merged["repo"] == repo
        assert merged["session"] == "s"
        assert merged["gate"] == "g"

    def test_task_side_detail_also_merges_without_crashing(
        self, sandbox, clean_env, tmp_path
    ):
        repo = _git_repo(tmp_path)
        merged = ptt._log_fields(
            _task_ev("code-reviewer", cwd=repo, session_id="s"),
            repo,
            {"agent_type": "from-gate", "pin": "opus"},
        )
        assert merged["agent_type"] == "from-gate"
        assert merged["pin"] == "opus"
        assert merged["repo"] == repo


class TestResolveBlockOutChannel:
    """`resolve_block`'s new `out` param is an out-CHANNEL only: it must never
    influence which gate blocks, and every pre-existing 3-arg caller must keep
    working unchanged."""

    def test_three_arg_call_still_works(self, sandbox, clean_env, tmp_path):
        repo = _git_repo(tmp_path)
        block, detail = ptb.resolve_block(_bash_ev(BRANCH_OP, cwd=repo), BRANCH_OP, repo)
        assert block is not None
        assert block.reason.startswith("state-verb")

    def test_out_receives_the_repo_root_for_a_guarded_commit(
        self, sandbox, clean_env, tmp_path
    ):
        repo = _git_repo(tmp_path)
        cmd = 'git commit -m "x" -- .'
        out: dict = {}
        ptb.resolve_block(_bash_ev(cmd, cwd=repo), cmd, repo, out)
        assert out.get("repo_root") == repo

    def test_out_does_not_change_the_decision(self, sandbox, clean_env, tmp_path):
        """Same event, with and without the out dict — identical verdict."""
        repo = _git_repo(tmp_path)
        cmd = 'git commit -m "x" -- .'
        ev = _bash_ev(cmd, cwd=repo)
        a_block, a_detail = ptb.resolve_block(ev, cmd, repo)
        b_block, b_detail = ptb.resolve_block(ev, cmd, repo, {})
        assert (a_block is None) == (b_block is None)
        if a_block is not None:
            assert a_block.reason == b_block.reason
            assert a_detail == b_detail

    def test_unguarded_event_leaves_out_without_a_repo_root(
        self, sandbox, clean_env, tmp_path
    ):
        """A non-commit command must not start paying for a repo-root
        subprocess inside resolve_block — the cost stays on the block path in
        _finish, which only runs when something actually blocked."""
        repo = _git_repo(tmp_path)
        out: dict = {}
        ptb.resolve_block(_bash_ev(BRANCH_OP, cwd=repo), BRANCH_OP, repo, out)
        assert out.get("repo_root") in (None, "")


class TestFinishSignatureBackCompat:
    def test_four_arg_finish_call_still_works(self, sandbox, clean_env):
        """Pre-existing callers/tests pass 4 positional args and no identity;
        that must keep producing a row (with no identity fields)."""
        block = ptb._Block("block_branch_ops", "state-verb:reset", "msg", git_state=False)
        rc = ptb._finish(block, {}, "git reset", "/nowhere")
        assert rc == 0
        rec = _last(sandbox)
        assert rec["reason"] == "state-verb:reset"
        for name in ("session", "agent_type", "repo"):
            assert name not in rec


# ===========================================================================
# pretooluse_task — contributes ALL THREE.
# ===========================================================================


def _task_ev(subagent_type, *, cwd, session_id=None, model=None, tool_use_id=None):
    ti: dict = {"subagent_type": subagent_type, "prompt": "do a thing"}
    if model is not None:
        ti["model"] = model
    ev: dict = {"tool_name": "Task", "tool_input": ti, "cwd": cwd}
    if session_id is not None:
        ev["session_id"] = session_id
    if tool_use_id is not None:
        ev["tool_use_id"] = tool_use_id
    return ev


class TestTaskEntryPointIdentity:
    """These drive `apply_t1` directly with a forced block, because reaching a
    real T1 denial through main() requires the agent-roster/policy fixtures
    that test_model_pin_gate.py owns. What is under test here is the identity
    wiring on the row, not model_pin_gate's own verdict logic."""

    @staticmethod
    def _force_block(monkeypatch):
        monkeypatch.setattr(
            ptt.mpg, "decide", lambda ev: (True, "pin-tier-mismatch", {"pin": "opus"})
        )
        monkeypatch.setattr(ptt.mpg, "message_for", lambda r, d: "denied: " + r)

    def test_row_carries_all_three_fields(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """SPEC (R9): pretooluse_task contributes session + agent_type + repo.
        A Task payload IS a dispatch, so `tool_input.subagent_type` exists."""
        repo = _git_repo(tmp_path)
        self._force_block(monkeypatch)
        ev = _task_ev("code-reviewer", cwd=repo, session_id="sess-task")
        assert ptt.apply_t1(ev) is True  # log-only default: still allowed
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        assert rec["session"] == "sess-task"
        assert rec["agent_type"] == "code-reviewer"
        assert rec["repo"] == repo
        # The gate's own detail survives alongside identity.
        assert rec["reason"] == "pin-tier-mismatch"
        assert rec["pin"] == "opus"

    def test_nosession_sentinel_omitted_on_the_task_side_too(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        self._force_block(monkeypatch)
        ptt.apply_t1(_task_ev("code-reviewer", cwd=repo))  # no session_id
        rec = _last(sandbox)
        assert "session" not in rec
        _assert_no_sentinel_value(rec)
        assert rec["agent_type"] == "code-reviewer"

    def test_missing_subagent_type_omits_agent_type(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """An absent agent type is omitted, never written as "" — the same
        absence rule the repo field follows."""
        repo = _git_repo(tmp_path)
        self._force_block(monkeypatch)
        ev = {"tool_name": "Task", "tool_input": {"prompt": "x"}, "cwd": repo,
              "session_id": "s"}
        ptt.apply_t1(ev)
        rec = _last(sandbox)
        assert "agent_type" not in rec
        assert rec["session"] == "s"

    def test_non_repo_cwd_omits_repo(self, sandbox, clean_env, tmp_path, monkeypatch):
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        self._force_block(monkeypatch)
        ptt.apply_t1(_task_ev("code-reviewer", cwd=str(outside), session_id="s"))
        rec = _last(sandbox)
        assert "repo" not in rec
        assert rec["agent_type"] == "code-reviewer"

    def test_kill_switch_strips_identity(self, sandbox, clean_env, tmp_path, monkeypatch):
        repo = _git_repo(tmp_path)
        clean_env.setenv(_lib.IDENTITY_KILL_SWITCH, "1")
        self._force_block(monkeypatch)
        ptt.apply_t1(_task_ev("code-reviewer", cwd=repo, session_id="s"))
        rec = _last(sandbox)
        assert rec["decision"] == "would-block"
        for name in ("session", "agent_type", "repo"):
            assert name not in rec

    def test_identity_failure_does_not_change_the_t1_verdict(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        """FAIL-OPEN on the Task side: identity exploding must not turn a
        would-block into an allow, nor an allow into a deny."""
        repo = _git_repo(tmp_path)
        self._force_block(monkeypatch)

        def boom(*a, **k):
            raise RuntimeError("identity exploded")

        # Break the INNER function; `_identity_safe`'s outer guard is what must
        # save the dispatch — see TestBashEntryPointFailOpen._explode.
        monkeypatch.setattr(ptt, "_identity", boom)
        monkeypatch.setenv("CSA_ENFORCE", "1")
        buf = io.StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        allowed = ptt.apply_t1(_task_ev("code-reviewer", cwd=repo, session_id="s"))
        assert allowed is False  # still denied under enforcement
        assert _is_deny(buf.getvalue())

    def test_allow_path_logs_nothing(self, sandbox, clean_env, tmp_path, monkeypatch):
        """Regression guard: an allowed dispatch writes no enforcement row, so
        identity cannot have introduced one."""
        repo = _git_repo(tmp_path)
        monkeypatch.setattr(ptt.mpg, "decide", lambda ev: (False, "", {}))
        assert ptt.apply_t1(_task_ev("explore", cwd=repo, session_id="s")) is True
        assert _read_log(sandbox) == []

    def test_repo_resolution_failure_degrades_to_no_field(
        self, sandbox, clean_env, tmp_path, monkeypatch
    ):
        repo = _git_repo(tmp_path)
        self._force_block(monkeypatch)

        def boom(*a, **k):
            raise RuntimeError("git exploded")

        monkeypatch.setattr(ptt.ct, "repo_root_of", boom)
        ptt.apply_t1(_task_ev("code-reviewer", cwd=repo, session_id="s"))
        rec = _last(sandbox)
        assert "repo" not in rec
        assert rec["session"] == "s"
        assert rec["agent_type"] == "code-reviewer"


# ===========================================================================
# C3 — file_claims.py is a LIBRARY; the change adds no log() call there.
# ===========================================================================


def test_file_claims_still_has_zero_log_calls():
    """SPEC (correction C3): rev 2's target list wrongly named file_claims
    among 8 modules to wire. It is a library with ZERO log() calls —
    pretooluse_bash gate 4 writes every contention row. This asserts the
    change did NOT add one, which is the specific mistake C3 corrects.

    Source-text assertion rather than behavioral, because "a call that should
    not exist" has no behavior to observe."""
    src = open(os.path.join(_HOOKS_DIR, "file_claims.py"), encoding="utf-8").read()
    assert "_lib.log(" not in src
    # Guard the unqualified spelling too (file_claims does not import _lib.log
    # by name today, and must not start).
    assert "\nlog(" not in src
