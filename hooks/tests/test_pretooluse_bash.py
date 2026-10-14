"""Hermetic tests for hooks/pretooluse_bash.py — the consolidated dispatcher.

pretooluse_bash runs the three formerly-separate Bash guards (block_branch_ops,
block_unscoped_commit, check_staged_scope) in one python spawn, first-block-wins.
These tests drive its PURE gate resolver AND its thin main() end to end, asserting:

  * each of the three gates blocks the command it owns (branch-op, bulk-add, a
    staged-scope violation),
  * safe path-scoped add/commit and read-only/non-git commands pass,
  * CSA_DISABLE_HOOKS=1 neutralizes everything,
  * enforcing() ON emits the canonical PreToolUse deny (log-only otherwise),
  * first-block-wins ordering (branch-ops before the others),
  * the OWN-env escape hatch and the inline tripwire,
  * parse-error fail-closed with a git token.

Everything runs under the `sandbox` fixture ($HOME + _lib path constants pointed
into a tmp dir) so the operator's real ~/.claude is never touched. The only git
run is inside throwaway repos from the `git_repo` fixture (offline, no network).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time

import _lib  # noqa: F401  (ensures the hooks dir is on sys.path via conftest)
import check_staged_scope as css
import pretooluse_bash as ptb
import pytest


def _write_claim_with_pid(claims_dir: str, agent_id: str, paths: list, claimed_at: float, pid) -> None:
    """Write a file_claims claim file directly with an EXPLICIT "pid" field
    (bypassing file_claims._write_claim's own _owner_pid() resolution, which
    always reads the live CLAUDE_PID/os.getpid() of the test process — never
    a dead one) so the dead-pid honesty tests below can pin a known-dead pid.
    """
    os.makedirs(claims_dir, exist_ok=True)
    path = ptb.fc.claim_path(claims_dir, agent_id)
    body = {"agent_id": agent_id, "pid": pid, "claimed_at": claimed_at, "paths": paths}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)


def _dead_pid() -> int:
    """Spawn a trivial subprocess, wait for it to exit, and return its
    (now-guaranteed-dead) pid.

    NIT (Opus review, 2026-08-30): a theoretical flake window exists between
    `proc.wait()` returning and this pid being asserted "dead" a few lines
    later in the calling test — the OS is free to reuse a just-freed pid for
    an unrelated new process in that gap. Not treated as worth guarding
    against here — see test_file_claims.py's own `_dead_pid()` for the full
    reasoning (this is the same helper, duplicated per test module rather
    than shared, matching this suite's existing convention of not cross-
    importing between test files).
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=5)
    return proc.pid

# ===========================================================================
# Helpers.
# ===========================================================================


def _run_main(monkeypatch, payload, *, env=None):
    """Feed a JSON payload (dict or raw str) to main() via stdin; capture stdout.

    Returns (exit_code, stdout_str). Any env dict is applied with monkeypatch.
    """
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    rc = ptb.main()
    return rc, buf.getvalue()


def _is_deny(stdout: str) -> bool:
    """True iff stdout is the canonical PreToolUse deny object."""
    if not stdout.strip():
        return False
    try:
        obj = json.loads(stdout)
    except Exception:
        return False
    hso = obj.get("hookSpecificOutput", {})
    return hso.get("hookEventName") == "PreToolUse" and hso.get("permissionDecision") == "deny"


def _read_log(sandbox):
    """Return the parsed JSONL decision-log records (empty list if none)."""
    if not sandbox.log_file.exists():
        return []
    return [json.loads(line) for line in sandbox.log_file.read_text().strip().splitlines() if line]


def _payload(command, tool_name="Bash", cwd=None):
    ev: dict = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    if cwd is not None:
        ev["cwd"] = cwd
    return ev


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_AUTHOR_NAME", "t")
    env.setdefault("GIT_AUTHOR_EMAIL", "t@t")
    env.setdefault("GIT_COMMITTER_NAME", "t")
    env.setdefault("GIT_COMMITTER_EMAIL", "t@t")
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, timeout=15, env=env)


def _has_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10)
        return True
    except Exception:  # pragma: no cover - git present in CI/dev
        return False


requires_git = pytest.mark.skipif(not _has_git(), reason="git not available")


# ===========================================================================
# Gate 1 — block_branch_ops: a git state-mutation blocks.
# ===========================================================================


class TestGateBranchOps:
    def test_state_verb_log_only(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload("git reset --hard"))
        assert rc == 0 and out == ""  # log-only default
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "would-block"
        assert rec["gate"] == "block_branch_ops"
        assert rec["reason"] == "state-verb:reset"

    def test_state_verb_enforce_emits_deny(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("git checkout main"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert "state-verb:checkout" in obj["systemMessage"]
        assert obj["systemMessage"].startswith("block_branch_ops")
        # #4415: the denied AGENT reads permissionDecisionReason, the operator
        # reads systemMessage — the dispatcher must surface the gate to both,
        # end to end, or an unattended loop cannot tell gate 1 from gate 3b.
        assert obj["hookSpecificOutput"]["permissionDecisionReason"] == obj["systemMessage"]

    def test_branch_delete_blocks(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("git branch -D feat"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)


# ===========================================================================
# Gate 1b — block_head_overwrite: a self-overwrite redirect blocks, and gate
# ordering (1 before 1b before 2) is preserved (GH #4387).
# ===========================================================================


class TestGateHeadOverwrite:
    def test_self_overwrite_log_only(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload("git show HEAD:foo.py > foo.py"))
        assert rc == 0 and out == ""  # log-only default
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "would-block"
        assert rec["gate"] == "block_head_overwrite"
        assert rec["reason"] == "show-redirect-self-overwrite"

    def test_self_overwrite_enforce_emits_deny(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("git show HEAD:foo.py > foo.py"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("block_head_overwrite")
        assert obj["hookSpecificOutput"]["permissionDecisionReason"] == obj["systemMessage"]

    def test_redirect_to_different_path_never_blocks(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("git show HEAD:foo.py > foo.py.bak"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and out == ""

    def test_gate_1_wins_over_gate_1b_when_both_could_match(self, sandbox, monkeypatch):
        """A real git-state-verb command (gate 1's own domain) must never
        fall through to gate 1b's block_head_overwrite check -- gate 1 is
        checked FIRST in the dispatcher, and a `git checkout` is not a
        show/cat-file redirect shape at all, so this is really asserting
        gate 1 still wins the more general "does anything block" race."""
        rc, out = _run_main(
            monkeypatch, _payload("git checkout main"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("block_branch_ops")

    def test_gate_1b_does_not_interfere_with_gate_2(self, sandbox, monkeypatch):
        """A bulk-add command (gate 2's domain) is unaffected by gate 1b's
        new check existing earlier in the chain."""
        rc, out = _run_main(
            monkeypatch, _payload("git add -A"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "block_unscoped_commit" in obj["systemMessage"] or "bulk-add" in obj["systemMessage"]


# ===========================================================================
# Gate 1c — block_gcloud_identity: a machine-wide gcloud identity mutation
# blocks; the sanctioned per-invocation scoping forms (--account=,
# --impersonate-service-account=, CLOUDSDK_CORE_ACCOUNT=) and read-only verbs
# pass. #5310.
# ===========================================================================


class TestGateGcloudIdentity:
    # ---- the exact incident-shaped commands from the task, RED without the
    # gate (proven via test_block_gcloud_identity.py's own revert-and-rerun;
    # see this suite's own falsifiability note in that file) -------------

    def test_config_set_account_log_only(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("gcloud config set account other@example.com")
        )
        assert rc == 0 and out == ""  # log-only default
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "would-block"
        assert rec["gate"] == "block_gcloud_identity"
        assert rec["reason"] == "config-set-account"

    def test_config_set_core_account_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config set core/account other@example.com"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("block_gcloud_identity")
        assert "config-set-account" in obj["systemMessage"]
        assert obj["hookSpecificOutput"]["permissionDecisionReason"] == obj["systemMessage"]

    def test_config_configurations_activate_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config configurations activate other-config"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert "config-configurations-activate" in obj["systemMessage"]

    def test_auth_activate_service_account_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload(
                "gcloud auth activate-service-account sa@x.iam.gserviceaccount.com "
                "--key-file=/tmp/k.json"
            ),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert "auth-activate-service-account" in obj["systemMessage"]
        assert "--impersonate-service-account" in obj["systemMessage"]

    def test_auth_activate_service_account_blocks_even_with_account_flag(
        self, sandbox, monkeypatch
    ):
        """No scoping flag suppresses activation for this verb (gcloud's own
        docs: activation is unconditional) -- an --account flag riding along
        must not be mistaken for the sanctioned per-invocation override."""
        rc, out = _run_main(
            monkeypatch,
            _payload(
                "gcloud auth activate-service-account sa@x.iam.gserviceaccount.com "
                "--key-file=/tmp/k.json --account=sa@x.iam.gserviceaccount.com"
            ),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        assert "auth-activate-service-account" in json.loads(out)["systemMessage"]

    def test_auth_application_default_login_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud auth application-default login"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-application-default-login" in json.loads(out)["systemMessage"]

    def test_auth_login_without_no_activate_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("gcloud auth login"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-login-without-no-activate" in json.loads(out)["systemMessage"]

    def test_auth_login_with_account_arg_still_blocks(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud auth login someone@example.com"),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)

    def test_config_unset_account_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config unset account"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "config-unset-account" in json.loads(out)["systemMessage"]

    def test_config_unset_core_account_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config unset core/account"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "config-unset-account" in json.loads(out)["systemMessage"]

    def test_auth_revoke_no_account_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("gcloud auth revoke"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-revoke" in json.loads(out)["systemMessage"]

    def test_auth_revoke_all_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("gcloud auth revoke --all"), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-revoke" in json.loads(out)["systemMessage"]

    def test_auth_revoke_explicit_account_blocks_under_enforce(
        self, sandbox, monkeypatch
    ):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud auth revoke other@example.com"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-revoke" in json.loads(out)["systemMessage"]

    def test_auth_application_default_revoke_blocks_under_enforce(
        self, sandbox, monkeypatch
    ):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud auth application-default revoke"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "auth-application-default-revoke" in json.loads(out)["systemMessage"]

    def test_adc_redirect_write_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload(
                "cat /tmp/key.json > "
                "~/.config/gcloud/application_default_credentials.json"
            ),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "adc-file-redirect-write" in json.loads(out)["systemMessage"]

    def test_adc_cp_write_blocks_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload(
                "cp /tmp/key.json "
                "~/.config/gcloud/application_default_credentials.json"
            ),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and _is_deny(out)
        assert "adc-file-cp-mv-tee-write" in json.loads(out)["systemMessage"]

    # ---- the sanctioned per-invocation scoping forms ALLOW, per-command --

    @pytest.mark.parametrize(
        "command",
        [
            "gcloud --account=svc@example.com config list",
            "gcloud config list --account=svc@example.com",
            "gcloud --impersonate-service-account=sa@x.iam.gserviceaccount.com projects list",
            "CLOUDSDK_CORE_ACCOUNT=svc@example.com gcloud config list",
            "gcloud auth login --no-activate",
            "gcloud auth list",
            "gcloud config get-value account",
            "gcloud projects list",
        ],
    )
    def test_scoped_and_readonly_forms_allow(self, sandbox, monkeypatch, command):
        rc, out = _run_main(monkeypatch, _payload(command), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    # ---- ordering / escape hatch / tripwire -------------------------------

    def test_gate_1_still_wins_over_gate_1c_for_a_real_git_state_verb(
        self, sandbox, monkeypatch
    ):
        rc, out = _run_main(
            monkeypatch, _payload("git checkout main"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        assert json.loads(out)["systemMessage"].startswith("block_branch_ops")

    def test_gate_1c_does_not_interfere_with_gate_2(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("git add -A"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "block_unscoped_commit" in obj["systemMessage"] or "bulk-add" in obj["systemMessage"]

    def test_escape_hatch_allows_gcloud_identity_block(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config set account other@example.com"),
            env={"CSA_ENFORCE": "1", "CSA_ALLOW_GIT_STATE_OPS": "1"},
        )
        assert rc == 0 and out == ""
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "escape-allowed"
        assert rec["gate"] == "block_gcloud_identity"

    def test_inline_tripwire_never_escapable(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config set account $CSA_ALLOW_GIT_STATE_OPS"),
            env={"CSA_ENFORCE": "1", "CSA_ALLOW_GIT_STATE_OPS": "1"},
        )
        assert _is_deny(out)
        assert "inline-escape-var-forbidden" in json.loads(out)["systemMessage"]

    def test_master_off_neutralizes_gcloud_identity_gate(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("gcloud config set account other@example.com"),
            env={"CSA_DISABLE_HOOKS": "1", "CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []


# ===========================================================================
# #4670 item 3 — gate-1 remediation message, corrected target file.
#
# AA-0051's original target (block_branch_ops.py) is dead code: settings.json
# wires only bash_gate.sh -> pretooluse_bash.py, and the message every agent
# actually sees is built by THIS module's own `_branch_ops_block()`. The
# remediation line is added ONLY for reason == "untokenizable-segment-with-
# git" -- every other blocked reason must NOT gain it. RED fixture verified
# live against block_branch_ops.decision() during plan review: an unmatched
# single quote spanning a backslash line continuation.
# ===========================================================================


class TestGateBranchOpsUntokenizableRemediation:
    FIXTURE = "cd /tmp\ngit add \\\n  a'b.py"

    def test_fixture_is_untokenizable_segment_with_git(self):
        # Sanity check on the fixture itself before asserting anything about
        # a message built on top of it.
        assert ptb.bbo.decision(self.FIXTURE) == (True, "untokenizable-segment-with-git")

    def test_branch_ops_block_message_carries_remediation(self):
        block = ptb._branch_ops_block(self.FIXTURE)
        assert block is not None
        assert block.reason == "untokenizable-segment-with-git"
        assert "REMEDIATION" in block.message
        assert "unmatched quote" in block.message.lower()
        # MINOR 1 (#4670 round-4 review): the shipped message names BOTH
        # causes -- an unmatched quote AND a trailing backslash line-
        # continuation -- but the original test only asserted the first
        # half, so a regression dropping the second half went undetected.
        assert "backslash line-continuation" in block.message.lower()

    def test_other_blocked_reasons_do_not_gain_remediation(self):
        # Negative: no other reason picks up the remediation phrase -- it
        # would be noise on the ~3,700 other denials/30d that have nothing
        # to do with parsing.
        for command in (
            "git reset --hard",  # state-verb:reset
            "git branch -D feat",  # branch-delete
            "git add -A",  # bulk-add
            'git commit -a -m "x"',  # commit-all
            "CSA_ALLOW_GIT_STATE_OPS=1 git status",  # inline-escape-var-forbidden
        ):
            block = ptb._branch_ops_block(command)
            assert block is not None, command
            assert "REMEDIATION" not in block.message, command

    def test_end_to_end_deny_message_carries_remediation(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload(self.FIXTURE), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and _is_deny(out)
        obj = json.loads(out)
        assert "REMEDIATION" in obj["systemMessage"]
        assert obj["systemMessage"].startswith("block_branch_ops")
        assert obj["hookSpecificOutput"]["permissionDecisionReason"] == obj["systemMessage"]

    def test_end_to_end_log_only_reason_unchanged(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload(self.FIXTURE))
        assert rc == 0 and out == ""
        rec = _read_log(sandbox)[0]
        assert rec["reason"] == "untokenizable-segment-with-git"
        assert rec["gate"] == "block_branch_ops"


# ===========================================================================
# Gate 2 — block_unscoped_commit: a bulk add blocks. (Note: bulk-add is also a
# gate-1 block, so gate 1 wins; the distinct gate-2 message shows on a form gate 1
# does NOT catch is not possible here since gate 1 already owns add/commit bulk.
# We assert the resolved block for a bulk add is a git-state block that denies.)
# ===========================================================================


class TestGateUnscopedCommit:
    def test_bulk_add_blocks(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload("git add -A"), env={"CSA_ENFORCE": "1"})
        assert _is_deny(out)
        # First-block-wins: block_branch_ops owns bulk-add too and is gate 1.
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "block_branch_ops"
        assert rec["reason"] == "bulk-add"

    def test_unscoped_commit_gate_reached_when_branch_ops_passes(self, sandbox, monkeypatch):
        # Force gate 1 to abstain so gate 2 is the one that resolves the block,
        # proving the dispatcher consults block_unscoped_commit and surfaces ITS
        # message. (bulk-add is gate-1 territory; neutralizing gate 1 isolates gate 2.)
        monkeypatch.setattr(ptb.bbo, "decision", lambda _c: (False, "no-git-state-verb"))
        rc, out = _run_main(monkeypatch, _payload("git add -A"), env={"CSA_ENFORCE": "1"})
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("block_unscoped_commit")
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "block_unscoped_commit"
        assert rec["reason"] == "bulk-add"


# ===========================================================================
# Gate 3 — check_staged_scope: an index that sweeps out of scope blocks.
# ===========================================================================


class TestGateStagedScope:
    # None of these commands carry a `-- <pathspec>` — they exist to isolate
    # gate 3's scope/sweep logic against the staged index, not the (separate,
    # separately-tested-below) mandatory-pathspec feature — so each sets
    # CSA_NO_REQUIRE_PATHSPEC=1 to reach that path deliberately.

    def test_out_of_scope_index_blocks_via_real_index(self, sandbox, monkeypatch, git_repo):
        # Stage a file OUTSIDE the declared feat(voice) scope, then a scoped commit.
        (git_repo / "modules").mkdir()
        (git_repo / "modules" / "billing.py").write_text("x\n")
        if _has_git():
            _git(git_repo, "add", "modules/billing.py")
        else:  # pragma: no cover - git present in CI/dev
            pytest.skip("git not available")
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): add"', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("check_staged_scope")
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "check_staged_scope"
        assert rec["reason"] == "out-of-scope"

    def test_staged_scope_block_via_stubbed_index(self, sandbox, monkeypatch):
        # Isolate gate 3 without a real repo: stub the index reader to return a
        # sprawl of unrelated files (too-many-top-dirs) for a scoped-less commit.
        monkeypatch.setattr(
            ptb.css,
            "read_staged_paths",
            lambda _w: [f"dir{i}/f.py" for i in range(10)],
        )
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "wip"'),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert _is_deny(out)
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "check_staged_scope"
        assert rec["reason"] == "too-many-top-dirs"
        # The sweep detail is folded into the log record.
        assert rec["max_top_dirs"] == css.DEFAULT_MAX_TOP_DIRS

    def test_staged_scope_log_only_default(self, sandbox, monkeypatch):
        monkeypatch.setattr(
            ptb.css,
            "read_staged_paths",
            lambda _w: [f"dir{i}/f.py" for i in range(10)],
        )
        rc, out = _run_main(
            monkeypatch, _payload('git commit -m "wip"'), env={"CSA_NO_REQUIRE_PATHSPEC": "1"}
        )
        assert rc == 0 and out == ""  # log-only
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "check_staged_scope"
        assert rec["reason"] == "too-many-top-dirs"

    def test_staged_scope_clean_index_allows(self, sandbox, monkeypatch):
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_missing_pathspec_blocks_by_default_reason_aware_message(self, sandbox, monkeypatch):
        """The mandatory-pathspec feature itself, exercised through the full
        pretooluse_bash dispatcher (gate 3's own message-wiring): a
        pathspec-less commit is BLOCKED with a reason-aware deny, using
        check_staged_scope.deny_message()'s exact text — NOT the old generic
        scope-sweep message."""
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch, _payload('git commit -m "feat(voice): x"'), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "missing-pathspec" in obj["systemMessage"]
        assert 'git commit -m "..." -- <path>' in obj["systemMessage"]
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == "check_staged_scope"
        assert rec["reason"] == "missing-pathspec"

    def test_pathspec_commit_still_allows(self, sandbox, monkeypatch):
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["should-not-matter.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x" -- modules/voice/a.py'),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""


# ===========================================================================
# Gate 4 — file_claims: contested paths (another agent's in-flight commit).
# ===========================================================================


class TestGateFileClaims:
    # Most of these commands carry no `-- <pathspec>` and are here to isolate
    # gate 4's contest logic — not the mandatory-pathspec feature — so they
    # set CSA_NO_REQUIRE_PATHSPEC=1 to reach gate 4 at all (gate 3 short-
    # circuits resolve_block before gate 4 otherwise). They also pass
    # repo_root=None-equivalent (no cwd) so no commit-mutex token is claimed
    # here — the mutex has its own dedicated section below.

    def test_clean_ledger_allows_silently_even_under_enforce(self, sandbox, monkeypatch):
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_log_only_contest_allows_but_logs_would_wait(self, sandbox, monkeypatch):
        # Another agent already holds modules/voice/a.py.
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["modules/voice/a.py"], lock_timeout=1.0
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={"CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert rc == 0 and out == ""  # log-only NEVER blocks or delays
        rec = _read_log(sandbox)[0]
        assert rec["hook"] == ptb.fc.HOOK_NAME
        assert rec["decision"] == "would-wait"
        assert rec["contested_by"] == "other-agent"
        assert "modules/voice/a.py" in rec["paths"]

    def test_enforce_contest_that_never_clears_is_denied_after_bounded_wait(self, sandbox, monkeypatch):
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["modules/voice/a.py"], lock_timeout=1.0
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={
                "CSA_ENFORCE": "1",
                "CSA_NO_REQUIRE_PATHSPEC": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("file_claims")
        assert "other-agent" in obj["systemMessage"]
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == ptb.fc.HOOK_NAME
        assert rec["reason"] == "contested-paths"
        assert rec["contested_by"] == "other-agent"
        assert rec["overlap_paths"] == ["modules/voice/a.py"]

    def test_enforce_contest_never_partially_claims_on_denial(self, sandbox, monkeypatch):
        # The whole point: a denied/contested committer must hold NOTHING
        # afterward, not even the paths it didn't collide on.
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py"], lock_timeout=1.0
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py", "b.py"])
        _run_main(
            monkeypatch,
            _payload('git commit -m "wip"'),
            env={
                "CSA_ENFORCE": "1",
                "CSA_NO_REQUIRE_PATHSPEC": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        live = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert {r["agent_id"] for r in live} == {"other-agent"}

    def test_disjoint_paths_not_contested_even_under_enforce(self, sandbox, monkeypatch):
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["unrelated.py"], lock_timeout=1.0
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_explicit_pathspec_is_the_claimed_scope_not_the_full_index(self, sandbox, monkeypatch, tmp_path):
        # A commit scoped with `-- <path>` should claim/contest THAT path, not
        # whatever else happens to be sitting in the staged index. Run from a
        # cwd that resolves NO real repo toplevel (tmp_path, not a git repo)
        # so no commit-mutex token is also claimed here — that's covered by
        # the dedicated commit-mutex section below.
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["should-not-be-claimed.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- modules/voice/a.py', cwd=str(tmp_path)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""
        live = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert live[0]["paths"] == ["modules/voice/a.py"]

    def test_heredoc_redirect_token_is_not_claimed_as_a_path(self, sandbox, monkeypatch, tmp_path):
        # Regression: `git commit -F - -- <paths> <<'EOF' ... EOF` shlex-splits
        # its own heredoc opener into the pathspec as a literal "<<EOF" token
        # (the tokenizer has no concept of shell redirection). Self-observed
        # live: this poisoned a claim and spuriously self-contested a retry.
        command = 'git commit -F - -- modules/voice/a.py <<\'EOF\'\nsome message\nEOF'
        rc, out = _run_main(
            monkeypatch, _payload(command, cwd=str(tmp_path)), env={"CSA_ENFORCE": "1"}
        )
        assert rc == 0 and out == ""
        live = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert live[0]["paths"] == ["modules/voice/a.py"]  # never "<<EOF"

    def test_not_guarded_for_non_commit_no_claim_attempted(self, sandbox, monkeypatch):
        def boom(*_a, **_k):
            raise AssertionError("must not attempt a claim for a non-commit command")

        monkeypatch.setattr(ptb.fc, "try_claim_paths", boom)
        block, detail = ptb._file_claim_block(_payload("git status"), "git status", "")
        assert block is None and detail == {}

    def test_empty_target_paths_no_claim_attempted(self, sandbox, monkeypatch):
        def boom(*_a, **_k):
            raise AssertionError("must not attempt a claim for an empty index")

        monkeypatch.setattr(ptb.fc, "try_claim_paths", boom)
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: [])
        block, detail = ptb._file_claim_block(
            _payload('git commit -m "wip"'), 'git commit -m "wip"', ""
        )
        assert block is None and detail == {}


# ===========================================================================
# Gate 4 (continued) — the per-repo commit mutex: "only one commit in flight
# per repo at a time", claimed ALONGSIDE a commit's real target paths.
# ===========================================================================


class TestCommitMutex:
    def test_disjoint_path_concurrent_commit_same_repo_denied_via_mutex(
        self, sandbox, monkeypatch, git_repo
    ):
        """The mutex's whole point: two commits in the SAME repo touching
        DISJOINT files still contest each other, and the deny message names
        it plainly rather than dumping the raw mutex token."""
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        # Another agent already holds a commit claim + mutex on this repo,
        # scoped to an UNRELATED path.
        mutex = ptb.fc.mutex_token(str(git_repo))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py", mutex], lock_timeout=1.0
        )

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={
                "CSA_ENFORCE": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "commit-in-flight" in obj["systemMessage"]
        assert "other-agent" in obj["systemMessage"]
        assert "//commit-mutex::" not in obj["systemMessage"]  # never a raw token dump
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == ptb.fc.HOOK_NAME
        assert rec["reason"] == "commit-in-flight"

    def test_after_release_the_same_commit_succeeds(self, sandbox, monkeypatch, git_repo):
        """Recovery pairing (§6): a mutex-denied commit is not a dead end —
        once the holder releases, the exact same commit goes through."""
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        mutex = ptb.fc.mutex_token(str(git_repo))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py", mutex], lock_timeout=1.0
        )
        ptb.fc.release_claim(str(sandbox.file_claims_dir), "other-agent")

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""  # no deny — the mutex is free now

    def test_different_repos_never_contest_each_other(self, sandbox, monkeypatch, git_repo, tmp_path):
        """Two DIFFERENT repos never share a mutex, regardless of what paths
        they touch."""
        other_repo = tmp_path / "other-repo"
        other_repo.mkdir()
        _git(other_repo, "init", "-q")

        mutex = ptb.fc.mutex_token(str(other_repo))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["x.py", mutex], lock_timeout=1.0
        )

        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / "a.py").write_text("1\n")
        _git(git_repo, "add", "a.py")

        # This test is about the MUTEX, not about review. Satisfy the
        # pre-commit review gate (gate 3b, added 2026-08-19) for this exact
        # content so its deny cannot masquerade as a mutex contest below —
        # the assertion must keep measuring what its name says it measures.
        import record_review as rr

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(["record_review.py", str(git_repo), "--pre-commit", "--clean", "--paths", "a.py"])

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""  # a different repo -> no contest

    def test_csa_no_commit_mutex_disables_it(self, sandbox, monkeypatch, git_repo):
        """CSA_NO_COMMIT_MUTEX=1 is the operator rollback lever: two disjoint-
        path commits in the same repo no longer contest via the mutex (real
        path-scoped claims are unaffected)."""
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        mutex = ptb.fc.mutex_token(str(git_repo))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py", mutex], lock_timeout=1.0
        )

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1", "CSA_NO_COMMIT_MUTEX": "1"},
        )
        assert rc == 0 and out == ""  # mutex disabled -> disjoint paths don't contest

    def test_non_repo_cwd_claims_no_mutex(self, sandbox, monkeypatch, tmp_path):
        """A cwd that resolves no real repo toplevel claims real paths only —
        never a fabricated mutex for a made-up fallback path."""
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(tmp_path)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""
        live = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert live[0]["paths"] == ["a.py"]  # no "//commit-mutex::..." entry

    def test_real_path_contest_message_excludes_mutex_token_from_overlap(
        self, sandbox, monkeypatch, git_repo
    ):
        """When the SAME real path is also contested (not just the mutex),
        the deny message still reports the real overlap, not the mutex
        token, and uses the ordinary contested-paths reason."""
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        mutex = ptb.fc.mutex_token(str(git_repo))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py", mutex], lock_timeout=1.0
        )

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(git_repo)),
            env={
                "CSA_ENFORCE": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "contested-paths" in obj["systemMessage"]
        assert "a.py" in obj["systemMessage"]
        assert "//commit-mutex::" not in obj["systemMessage"]
        rec = _read_log(sandbox)[0]
        assert rec["overlap_paths"] == ["a.py"]


# ===========================================================================
# Gate 4 honesty fix (#4670 item 2): a contest whose claim owner is
# confirmed dead gets an honest "LEAKED claim" message naming the exact
# standalone release command, never "another agent has uncommitted work".
# ===========================================================================


class TestGateFileClaimsDeadPidHonesty:
    def test_leaked_real_path_claim_message_is_honest(self, sandbox, monkeypatch):
        dead = _dead_pid()
        _write_claim_with_pid(
            str(sandbox.file_claims_dir),
            "crashed-agent",
            ["modules/voice/a.py"],
            claimed_at=time.time(),
            pid=dead,
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={
                "CSA_ENFORCE": "1",
                "CSA_NO_REQUIRE_PATHSPEC": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        msg = obj["systemMessage"]
        assert "contested-paths" in msg
        assert "LEAKED claim" in msg
        assert "python3 ~/.claude/hooks/file_claims.py release crashed-agent" in msg
        assert "another agent has uncommitted" not in msg.lower()
        rec = _read_log(sandbox)[0]
        assert rec["reason"] == "contested-paths"
        assert rec["contested_by"] == "crashed-agent"
        assert rec["holder_pid"] == dead
        assert rec["holder_alive"] is False

    def test_live_real_path_claim_message_unchanged(self, sandbox, monkeypatch):
        """Regression pairing: a genuinely LIVE holder still gets the
        original "another agent has uncommitted work" message, never the
        leaked-claim text."""
        _write_claim_with_pid(
            str(sandbox.file_claims_dir),
            "live-agent",
            ["modules/voice/a.py"],
            claimed_at=time.time(),
            pid=os.getpid(),
        )
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): x"'),
            env={
                "CSA_ENFORCE": "1",
                "CSA_NO_REQUIRE_PATHSPEC": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        msg = obj["systemMessage"]
        assert "another agent has uncommitted work" in msg.lower()
        assert "LEAKED claim" not in msg
        rec = _read_log(sandbox)[0]
        assert rec["holder_alive"] is True

    def test_leaked_mutex_only_claim_message_is_honest(self, sandbox, monkeypatch, git_repo):
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        dead = _dead_pid()
        mutex = ptb.fc.mutex_token(str(git_repo))
        _write_claim_with_pid(
            str(sandbox.file_claims_dir),
            "crashed-agent",
            ["a.py", mutex],
            claimed_at=time.time(),
            pid=dead,
        )

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={
                "CSA_ENFORCE": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        msg = obj["systemMessage"]
        assert "commit-in-flight" in msg
        assert "LEAKED claim" in msg
        assert "python3 ~/.claude/hooks/file_claims.py release crashed-agent" in msg
        rec = _read_log(sandbox)[0]
        assert rec["reason"] == "commit-in-flight"
        assert rec["holder_alive"] is False
        assert rec["holder_pid"] == dead


# ===========================================================================
# Gate 3c — dirty_precommit_config (#4670 item 3): a PATHSPEC commit is
# denied fast when this repo's own .pre-commit-config.yaml has uncommitted
# changes, BEFORE gate 4 ever takes a claim for it.
# ===========================================================================


class TestPrecommitConfigDirtyPure:
    def test_clean_committed_config_is_not_dirty(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        assert ptb._precommit_config_dirty(str(git_repo)) is False

    def test_unstaged_edit_is_dirty(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")
        assert ptb._precommit_config_dirty(str(git_repo)) is True

    def test_staged_but_uncommitted_edit_is_still_dirty(self, git_repo):
        """The exact #4670 hazard: staging the config in the real index
        does nothing — a pathspec commit's temp index never sees it."""
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        assert ptb._precommit_config_dirty(str(git_repo)) is True

    def test_no_config_file_ever_is_not_dirty(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        assert ptb._precommit_config_dirty(str(git_repo)) is False

    def test_no_head_yet_fails_open_not_dirty(self, git_repo):
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        assert ptb._precommit_config_dirty(str(git_repo)) is False

    def test_nonexistent_repo_root_fails_open(self, tmp_path):
        assert ptb._precommit_config_dirty(str(tmp_path / "does-not-exist")) is False


class TestDirtyPrecommitConfigBlockUnit:
    """None of these use the `sandbox`/`clean_env` fixture (they call the
    gate function directly, not through main()) — an autouse fixture clears
    CSA_NO_DIRTY_CONFIG_GATE for the whole class so an ambient-set lever can
    neither make an ALLOW/None assertion pass for the WRONG reason (the gate
    globally disabled, not genuinely exempt/clean) NOR make a real-deny
    assertion spuriously fail (FINDING 6, round-3 review — measured: with
    CSA_NO_DIRTY_CONFIG_GATE=1 actually set ambiently,
    test_dirty_config_with_pathspec_blocks failed outright before this
    fixture existed). _CSA_ENV_VARS in conftest.py now also covers this
    lever for any test that DOES use sandbox/clean_env.
    """

    @pytest.fixture(autouse=True)
    def _no_ambient_lever(self, monkeypatch):
        monkeypatch.delenv("CSA_NO_DIRTY_CONFIG_GATE", raising=False)

    def test_none_repo_root_no_block(self):
        assert ptb._dirty_precommit_config_block('git commit -m "x" -- a.py', "", None) is None

    def test_pathspec_less_command_no_block(self, git_repo):
        # Even with no commits/config at all, a pathspec-less command must
        # short-circuit on the pathspec check before any git call.
        assert ptb._dirty_precommit_config_block('git commit -m "x"', str(git_repo), str(git_repo)) is None

    def test_dirty_config_with_pathspec_blocks(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")

        block = ptb._dirty_precommit_config_block(
            'git commit -m "x" -- a.py', str(git_repo), str(git_repo)
        )
        assert block is not None
        assert block.reason == "dirty-precommit-config"
        assert block.hook == ptb.DIRTY_CONFIG_HOOK_NAME  # FINDING 3
        assert "uncommitted changes" in block.message
        assert block.git_state is False
        # FINDING 5 + BLOCKER 1 (round-3 correction): the message must name
        # the REAL 3-step recovery, not the old "land or revert" pair
        # (BLOCKER 1 proved both dead-end) NOR a single bare config-only
        # commit (round-3 BLOCKER 1 proved even THAT is denied by gate 3b
        # for want of a review). This is a structural check on all three
        # steps being present; TestGateDirtyPrecommitConfigRecoveryEndToEnd
        # below is what actually PROVES the chain works, not just reads
        # plausible.
        assert "record_review.py" in block.message
        assert "--pre-commit" in block.message
        assert "--clean" in block.message
        assert 'git commit -m "chore: sync pre-commit config" -- .pre-commit-config.yaml' in block.message

    def test_clean_config_with_pathspec_no_block(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")

        assert (
            ptb._dirty_precommit_config_block('git commit -m "x" -- a.py', str(git_repo), str(git_repo))
            is None
        )

    def test_rollback_lever_disables_this_gate_only(self, git_repo, monkeypatch):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")

        monkeypatch.setenv("CSA_NO_DIRTY_CONFIG_GATE", "1")
        assert (
            ptb._dirty_precommit_config_block('git commit -m "x" -- a.py', str(git_repo), str(git_repo))
            is None
        )


class TestGateDirtyPrecommitConfigRecoveryEndToEnd:
    """BLOCKER 1 + 1b (Opus review round 3, 2026-08-30). The round-2 message
    told the operator to land the config in its own bare commit — but that
    commit is ITSELF denied by gate 3b (a dirty config's own diff has, by
    definition of why gate 3c just fired, no recorded review yet). This
    class proves the CORRECTED 3-step chain actually clears the gate: it
    extracts the recovery from a REAL deny message (not a hardcoded copy —
    if the message and the real chain ever drift apart, this is what
    catches it) and executes exactly those steps back through main(),
    asserting the retry is genuinely allowed at the end. This REPLACES the
    old lock-in assertion ('git commit -m' in message) that only proved the
    words appeared, never that they worked.
    """

    def test_printed_recovery_chain_actually_clears_the_gate(self, sandbox, monkeypatch, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")  # dirty

        monkeypatch.setenv("CSA_ENFORCE", "1")

        # Step 0: the ORIGINAL commit is denied by gate 3c.
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        message = json.loads(out)["systemMessage"]
        assert "dirty_precommit_config" in message

        # Extract/confirm the recovery FROM the real printed message.
        assert "record_review.py" in message
        assert "--pre-commit" in message
        assert "--clean" in message
        assert "--paths .pre-commit-config.yaml" in message
        assert 'git commit -m "chore: sync pre-commit config" -- .pre-commit-config.yaml' in message

        # Step 1: review the config diff and record it (sandboxed ledger via
        # the `sandbox` fixture — same mechanism every other review-gate
        # test in this suite already relies on).
        import record_review as rr

        rr.main(
            [
                "record_review.py",
                str(git_repo),
                "--pre-commit",
                "--clean",
                "--paths",
                ".pre-commit-config.yaml",
            ]
        )

        # Step 2: land the config in its own commit — for REAL (the hook
        # only ever DECIDES; it never runs git itself, so this must be a
        # genuine `git commit` for step 3's re-check to see a clean config).
        proc = _git(
            git_repo,
            "commit",
            "-q",
            "-m",
            "chore: sync pre-commit config",
            "--",
            ".pre-commit-config.yaml",
        )
        assert proc.returncode == 0, proc.stderr

        # Step 3: retry the ORIGINAL commit — must now be allowed outright.
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""


# ===========================================================================
# BLOCKER 1 (Opus review, 2026-08-30): a commit whose OWN pathspec already
# names .pre-commit-config.yaml is EXEMPT — its temp index would carry the
# config's fresh content, so pre-commit would actually succeed, and denying
# it left NO sanctioned recovery.
# ===========================================================================


class TestPathspecIncludesPrecommitConfig:
    """No `sandbox`/`clean_env` here (calls the gate function directly) — an
    autouse fixture clears CSA_NO_DIRTY_CONFIG_GATE for the whole class so
    an ambient-set lever can never make an `is None` (exempt) assertion pass
    for the WRONG reason (FINDING 6, round-3 review)."""

    @pytest.fixture(autouse=True)
    def _no_ambient_lever(self, monkeypatch):
        monkeypatch.delenv("CSA_NO_DIRTY_CONFIG_GATE", raising=False)

    def _setup_dirty_config_repo(self, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")

    def test_config_dirty_and_in_own_pathspec_is_exempt(self, git_repo):
        """Combination test 6, primary case: config_dirty AND has_pathspec
        AND config IS the (only) named path -> allow (None), not denied."""
        self._setup_dirty_config_repo(git_repo)
        block = ptb._dirty_precommit_config_block(
            'git commit -m "chore: sync config" -- .pre-commit-config.yaml',
            str(git_repo),
            str(git_repo),
        )
        assert block is None

    def test_mixed_pathspec_including_config_is_exempt(self, git_repo):
        """Combination test 6, mixed case: `-- .pre-commit-config.yaml a.py`
        -- the whole normalized set is checked, not just a lone token."""
        self._setup_dirty_config_repo(git_repo)
        block = ptb._dirty_precommit_config_block(
            'git commit -m "x" -- .pre-commit-config.yaml a.py',
            str(git_repo),
            str(git_repo),
        )
        assert block is None

    def test_dot_slash_spelling_is_exempt(self, git_repo):
        """Combination test 6, normalized spelling: `./.pre-commit-config.yaml`
        must collapse to the same repo-root-relative path as the bare form —
        a bare string compare would miss this."""
        self._setup_dirty_config_repo(git_repo)
        block = ptb._dirty_precommit_config_block(
            'git commit -m "x" -- ./.pre-commit-config.yaml',
            str(git_repo),
            str(git_repo),
        )
        assert block is None

    def test_absolute_path_spelling_is_exempt(self, git_repo):
        """Combination test 6, absolute-path spelling — the other normalized
        form a bare string compare would miss."""
        self._setup_dirty_config_repo(git_repo)
        abs_config = str(git_repo / ".pre-commit-config.yaml")
        block = ptb._dirty_precommit_config_block(
            f'git commit -m "x" -- {abs_config}', str(git_repo), str(git_repo)
        )
        assert block is None

    def test_config_dirty_but_not_in_pathspec_still_blocks(self, git_repo):
        """Regression pairing: the exemption is scoped to the config actually
        being named -- an unrelated pathspec must still be denied."""
        self._setup_dirty_config_repo(git_repo)
        block = ptb._dirty_precommit_config_block(
            'git commit -m "x" -- a.py', str(git_repo), str(git_repo)
        )
        assert block is not None
        assert block.reason == "dirty-precommit-config"

    def test_helper_false_for_pathspec_less_command(self, git_repo):
        assert ptb._pathspec_includes_precommit_config('git commit -m "x"', str(git_repo), str(git_repo)) is False

    def test_helper_true_for_normalized_config_path(self, git_repo):
        assert ptb._pathspec_includes_precommit_config(
            'git commit -m "x" -- ./.pre-commit-config.yaml', str(git_repo), str(git_repo)
        ) is True


class TestGateDirtyPrecommitConfigExemptionEndToEnd:
    """Same exemption, driven through the full dispatcher (main()/resolve_block)
    rather than the unit-level function -- proves the wiring, not just the
    helper. This is the exact scenario BLOCKER 1's own repro used:
    `git commit -m x -- .pre-commit-config.yaml`."""

    def test_config_only_pathspec_commit_is_allowed(self, sandbox, monkeypatch, git_repo):
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")  # dirty

        import record_review as rr

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(
            [
                "record_review.py",
                str(git_repo),
                "--pre-commit",
                "--clean",
                "--paths",
                ".pre-commit-config.yaml",
            ]
        )

        rc, out = _run_main(
            monkeypatch,
            _payload(
                'git commit -m "chore: sync config" -- .pre-commit-config.yaml',
                cwd=str(git_repo),
            ),
            env={"CSA_ENFORCE": "1"},
        )
        for rec in _read_log(sandbox):
            assert rec.get("reason") != "dirty-precommit-config"
        assert rc == 0 and out == ""


class TestGateDirtyPrecommitConfig:
    """End-to-end through main()/resolve_block."""

    def test_dirty_unstaged_config_blocks_pathspec_commit(self, sandbox, monkeypatch, git_repo):
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")  # dirty, unstaged
        # b.py itself is left EXACTLY as committed (no real diff vs HEAD) so
        # gate 3b (precommit_review_gate) auto-passes with "nothing pending"
        # rather than needing its own recorded review — isolates gate 3c.

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "dirty-precommit-config" in obj["systemMessage"]
        assert "the pre-commit config has uncommitted changes" in obj["systemMessage"]
        rec = _read_log(sandbox)[0]
        # FINDING 3 (round 3): this gate logs under its OWN hook label, not
        # the dispatcher's — matching every sibling gate's convention.
        assert rec["gate"] == ptb.DIRTY_CONFIG_HOOK_NAME
        assert rec["gate"] != ptb.HOOK_NAME
        assert rec["reason"] == "dirty-precommit-config"
        # The whole point of the ordering: no claim was EVER taken for this
        # doomed attempt — nothing left to leak.
        assert ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300) == []

    def test_dirty_staged_but_uncommitted_config_still_blocks(self, sandbox, monkeypatch, git_repo):
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")  # staged, NOT committed

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        assert "dirty-precommit-config" in json.loads(out)["systemMessage"]

    def test_clean_config_does_not_block(self, sandbox, monkeypatch, git_repo):
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / "b.py").write_text("1\n")

        # Satisfy the pre-commit review gate for this exact content so it
        # can't masquerade as a dirty-config block below.
        import record_review as rr

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(["record_review.py", str(git_repo), "--pre-commit", "--clean", "--paths", "b.py"])

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""

    def test_no_config_file_at_all_does_not_block(self, sandbox, monkeypatch, git_repo):
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / "b.py").write_text("1\n")

        import record_review as rr

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(["record_review.py", str(git_repo), "--pre-commit", "--clean", "--paths", "b.py"])

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- b.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""

    def test_pathspec_less_commit_not_scoped_by_this_gate(self, sandbox, monkeypatch, git_repo):
        """A pathspec-LESS commit is a DIFFERENT hazard (#4091's stash
        cycle, not the temp-index one) — gate 3c must never fire for it,
        dirty config or not."""
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        _git(git_repo, "add", ".pre-commit-config.yaml")
        _git(git_repo, "commit", "-q", "-m", "config")
        (git_repo / ".pre-commit-config.yaml").write_text("repos: [1]\n")

        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["b.py"])
        _run_main(
            monkeypatch,
            _payload('git commit -m "wip"', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        for rec in _read_log(sandbox):
            assert rec.get("reason") != "dirty-precommit-config"

    def test_non_repo_cwd_no_block(self, sandbox, monkeypatch, tmp_path):
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "fix: x" -- a.py', cwd=str(tmp_path)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""  # no repo -> nothing to check


# ===========================================================================
# Gate 5 — churn_tracker: PURE OBSERVER, never blocks, reached only after
# gates 1-4 resolve with no block.
# ===========================================================================


class TestGateChurnObserver:
    def test_churn_observe_never_returns_anything_blocklike(self, sandbox, monkeypatch):
        """_churn_observe's own return type is None — structurally incapable
        of contributing a _Block — across a spread of inputs, including ones
        that make its internals raise."""
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        commands = [
            "git status",
            'git commit -m "wip"',
            'git commit -m "wip" -- a.py',
            "git reset --hard",  # not even a commit
            "",
        ]
        for command in commands:
            assert ptb._churn_observe(_payload(command), command, "") is None

    def test_resolve_block_never_blocks_due_to_churn_even_when_ct_raises(self, sandbox, monkeypatch):
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        monkeypatch.setattr(
            ptb.ct, "observe_commit_for_event", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        block, detail = ptb.resolve_block(_payload('git commit -m "wip"'), 'git commit -m "wip"', "")
        assert block is None and detail == {}

    def test_not_a_commit_no_observation_attempted(self, sandbox, monkeypatch):
        def boom(*_a, **_k):
            raise AssertionError("must not observe a non-commit command")

        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", boom)
        block, detail = ptb.resolve_block(_payload("git status"), "git status", "")
        assert block is None and detail == {}

    def test_empty_target_paths_no_observation_attempted(self, sandbox, monkeypatch):
        def boom(*_a, **_k):
            raise AssertionError("must not observe an empty index")

        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: [])
        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", boom)
        block, detail = ptb.resolve_block(_payload('git commit -m "wip"'), 'git commit -m "wip"', "")
        assert block is None and detail == {}

    @requires_git
    def test_gate5_not_reached_when_an_earlier_gate_blocks(self, sandbox, monkeypatch, git_repo):
        """A commit an earlier gate blocks is never observed as churn —
        recording a commit that a real deny actually prevented would be wrong.
        Asserted via the SIDE EFFECT (no ledger write), not an exception, since
        _churn_observe's own defensive try/except would otherwise swallow an
        "unexpectedly called" probe silently.
        """
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        # An out-of-scope staged file trips gate 3 (check_staged_scope).
        (git_repo / "modules").mkdir()
        (git_repo / "modules" / "billing.py").write_text("x\n")
        _git(git_repo, "add", "modules/billing.py")

        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(voice): add"', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)  # gate 3 blocked it
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("check_staged_scope")
        assert ptb.ct.read_live_commits(str(sandbox.churn_dir), 7200) == []

    @requires_git
    def test_third_touch_without_clean_review_logs_churn_flagged(self, sandbox, monkeypatch, git_repo):
        """End-to-end through REAL git: the same path touched by 3 successive
        commits (via 3 separate PreToolUse observations) with an ACTUAL
        advancing HEAD between each -> the 3rd fires a churn-flagged log line."""
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])

        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        for i in range(3):
            _run_main(monkeypatch, _payload(f'git commit -m "wip{i}"', cwd=str(git_repo)))
            (git_repo / "a.py").write_text(f"{i + 1}\n")
            _git(git_repo, "add", "a.py")
            _git(git_repo, "commit", "-q", "-m", f"c{i}")

        # One more observation: HEAD is now the 3rd real commit's sha, and the
        # ledger holds 3 prior observations for a.py -> flagged.
        _run_main(monkeypatch, _payload('git commit -m "wip-final"', cwd=str(git_repo)))

        logs = _read_log(sandbox)
        flagged = [r for r in logs if r.get("hook") == ptb.ct.HOOK_NAME and r.get("decision") == "churn-flagged"]
        assert flagged, f"expected a churn-flagged log entry, got: {logs}"
        assert flagged[0]["path"] == "a.py"
        assert flagged[0]["count"] >= 3

    @requires_git
    def test_repo_root_resolved_via_real_git_not_just_cwd(self, sandbox, monkeypatch, git_repo):
        """The commit is recorded under the resolved repo TOPLEVEL, not an
        arbitrary subdirectory cwd."""
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        nested = git_repo / "sub"
        nested.mkdir()

        _run_main(monkeypatch, _payload('git commit -m "wip"', cwd=str(nested)))

        live = ptb.ct.read_live_commits(str(sandbox.churn_dir), 7200)
        assert len(live) == 1
        assert os.path.samefile(live[0]["repo_root"], str(git_repo))

    def test_never_emits_deny_or_block_purely_from_churn(self, sandbox, monkeypatch):
        """Even a heavily-flagged path never produces a PreToolUse deny by
        itself — churn_tracker has no enforcing()-gated hard-block path."""
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        monkeypatch.setattr(
            ptb.ct,
            "observe_commit_for_event",
            lambda *a, **k: {"newly_flagged": {"a.py": 99}},
        )
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "wip"'),
            env={"CSA_ENFORCE": "1", "CSA_NO_REQUIRE_PATHSPEC": "1"},
        )
        assert rc == 0 and out == ""  # no deny, regardless of enforcing()
        logs = _read_log(sandbox)
        flagged = [r for r in logs if r.get("hook") == ptb.ct.HOOK_NAME]
        assert flagged and flagged[0]["decision"] == "churn-flagged"
        assert flagged[0]["count"] == 99

    def test_strip_redirects_pure_examples(self):
        """Pure unit coverage of the raw-string stripper itself, independent
        of the git tokenizer's own shlex-split behavior. Whitespace is
        normalized via .split() since _strip_redirects replaces a match with
        a single space rather than collapsing runs — the exact spacing left
        behind is not part of the contract, only which real tokens survive."""
        assert ptb._strip_redirects("a.py 2>/dev/null").split() == ["a.py"]
        assert ptb._strip_redirects("a.py > out.log").split() == ["a.py"]
        assert ptb._strip_redirects("a.py 2>&1").split() == ["a.py"]
        assert ptb._strip_redirects("a.py < in.txt").split() == ["a.py"]
        assert ptb._strip_redirects("a.py &> all.log").split() == ["a.py"]
        assert ptb._strip_redirects("a.py >&-").split() == ["a.py"]
        assert ptb._strip_redirects("a.py b.py").split() == ["a.py", "b.py"]  # untouched
        assert ptb._strip_redirects("") == ""

    @pytest.mark.parametrize(
        "command,expected",
        [
            # Attached, no space (shlex fuses operator+target into ONE
            # token — the retired _filter_redirect_tokens could never see
            # this as two tokens to filter). Was: ['a.py', '2>/dev/null'].
            ("git commit -m x -- a.py 2>/dev/null", ["a.py"]),
            # Detached stdout redirect + a SELF-CONTAINED dup form (2>&1)
            # that consumes no separate target. Was: ['a.py', '/dev/null'].
            ("git commit -m x -- a.py > /dev/null 2>&1", ["a.py"]),
            # Input redirection. Was: ['a.py', 'in.txt'].
            ("git commit -m x -- a.py < in.txt", ["a.py"]),
            # Chained: a self-contained `2>&1` ahead of a SECOND, real git
            # commit. _lib.git_segments' own tokenizer treats a bare `&` as
            # a control-operator boundary, so the retired filter's resolved-
            # list approach amputated the chain BEFORE any list existed and
            # then swallowed the second commit's own pathspec (`b.py`) as if
            # it were the dead operator's target. Was: ['a.py'] (b.py
            # destroyed entirely) — this is the case that actually corrupted
            # a DIFFERENT commit's recorded scope, not just added noise.
            ("git commit -m x -- a.py 2>&1 && git commit -m y -- b.py", ["a.py", "b.py"]),
            # The one shape the OLD filter already handled correctly
            # (detached, with a space) — must keep working after the fix.
            ("git commit -m x -- a.py 2> /dev/null", ["a.py"]),
        ],
    )
    def test_churn_observe_strips_redirects_before_recording(
        self, sandbox, monkeypatch, command, expected
    ):
        """08-25 fix round (B3): the retired _filter_redirect_tokens filtered
        the caller's already-RESOLVED path list, which cannot be made correct
        (see _REDIRECT_INLINE_RE's module comment for why). Fixed by
        stripping redirects out of the RAW command string before any
        tokenization/path resolution — asserted here via the exact list
        ct.observe_commit_for_event receives for each shape."""
        captured = {}

        def spy(_dir, _last, _repo, paths, _win, _thr):
            captured["paths"] = list(paths)
            return {"newly_flagged": {}}

        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", spy)
        ptb._churn_observe(_payload(command), command, "")
        assert captured["paths"] == expected

    def test_churn_observe_strip_destroyed_pathspec_falls_back_to_raw(
        self, sandbox, monkeypatch
    ):
        """08-25 round-4 blocker: an embedded literal '"' in the message body
        desyncs the quote walk, so stripping eats "blockers:<n>"/"<noreply@…>"
        runs THROUGH the `--` boundary — the cleaned string still parses to a
        writing commit segment but its pathspec is gone. The net must fall
        back to the RAW command (recording exactly the commit's own pathspec),
        never fall through to _commit_target_paths' whole-staged-index
        default. Message minimized from this repo's own history (the commit
        that added the churn tracker)."""
        message = (
            'optional third field ("clean" / "blockers:<n>"), fully '
            "backward-compatible\n"
            "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
        )
        command = f'git commit -m "{message}" -- a.py'
        # Precondition: cleaned still parses but lost the pathspec — if this
        # ever stops holding, the fixture no longer exercises the third net
        # condition and must be re-minimized, not deleted.
        cleaned = ptb._strip_redirects(command)
        assert ptb.css.writing_commit_segments(cleaned)
        assert ptb._declared_pathspec(command)[1]
        assert not ptb._declared_pathspec(cleaned)[1]
        captured = {}

        def spy(_dir, _last, _repo, paths, _win, _thr):
            captured["paths"] = list(paths)
            return {"newly_flagged": {}}

        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", spy)
        ptb._churn_observe(_payload(command), command, "")
        assert captured.get("paths") == ["a.py"]

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "Co-Authored-By: Claude <noreply@anthropic.com>" -- a.py',
            'git commit -m "A -> B" -- a.py',
            'git commit -m "bump n>=3" -- a.py',
            'git commit -m "retry: 2>1" -- a.py',
            "git commit -m 'see <file>' -- a.py",
            'git commit -m "wip" -- a.py >| out.log',
            'git commit -m "wip" -- a.py <<< "msg"',
        ],
        ids=[
            "co-authored-by-trailer",
            "arrow-in-message",
            "gte-in-message",
            "fd-redirect-shaped-in-message",
            "angle-bracket-in-message",
            "real-clobber-redirect",
            "real-here-string",
        ],
    )
    def test_churn_observe_message_row_shapes_record_exact_pathspec_never_staged(
        self, sandbox, monkeypatch, command
    ):
        """BLOCKER 1 message-row regression (08-25 round 3): a quoted commit
        message containing a redirect-SHAPED substring (an arrow, a `>=`
        comparison, a fd-style `2>1`, an angle-bracketed placeholder, or the
        mandated Co-Authored-By trailer) must never be torn apart by
        _strip_redirects, and a REAL unquoted redirect appended after the
        pathspec (`>| out.log`, `<<< "msg"`) must never leak its own target
        into the recorded set. staged=["other.py"] stands in for another
        agent's in-flight staged file: if quote-awareness ever regressed back
        to the naive stripper, the resulting parse failure would trip the
        defensive net's OWN fallback (see _churn_observe's docstring) and
        record the WHOLE staged index (["other.py"]) instead of this
        commit's own declared pathspec (["a.py"]) — asserting the exact list
        catches either failure mode, not just "no crash"."""
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["other.py"])
        captured = {}

        def spy(_dir, _last, _repo, paths, _win, _thr):
            captured["paths"] = list(paths)
            return {"newly_flagged": {}}

        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", spy)
        ptb._churn_observe(_payload(command), command, "")
        assert captured["paths"] == ["a.py"]

    @pytest.mark.parametrize(
        "message",
        [
            "Co-Authored-By: Claude <noreply@anthropic.com>",
            "Fixes #123",
            "a -> b",
            "## Status\nblocked > unblocked, see #45",
            "fix(hooks): tighten gate\n\n## What\nrename a -> b\n\n## Why\nFixes #4400\n\n"
            "## How\nrenamed\n\n## Status\ndone, verified > shipped\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>",
            "type(scope): summary\n\nbump n>=3, retry: 2>1",
            "see <file> for details",
            "A -> B migration",
            "chore: cleanup\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>",
            "revert 'A -> B' (partial)",
            "## Why\nFixes #4423 (2>1 retries observed)",
            "docs: note `>=` operator support",
        ],
        ids=[
            "co-authored-by-trailer",
            "fixes-nnn",
            "arrow-rename-note",
            "status-line-with-gt",
            "full-claude-md-shaped-body",
            "type-scope-summary-with-ops",
            "angle-bracket-placeholder",
            "arrow-migration",
            "chore-with-trailer",
            "revert-with-arrow",
            "why-line-with-fd-redirect-shape",
            "docs-backtick-gte",
        ],
    )
    def test_corpus_representative_message_shapes_never_corrupt_target_paths(
        self, sandbox, monkeypatch, message
    ):
        """Item 2 (08-25 round 3): ~12 message SHAPES drawn from this repo's
        own real commit corpus (a Co-Authored-By trailer, a `Fixes #NNN`
        line, an `a -> b` rename note, a `## Status` line containing `>`,
        and combinations of the same inside a full multi-line CLAUDE.md-
        shaped body) must never corrupt the recorded target path. This is a
        durable fixture regression test; the corpus MEASUREMENT itself (55
        real ~/.claude + 60 real ExampleApp commit messages run
        through this exact pipeline) is reported separately in the task
        report rather than asserted here, since real repo history changes
        commit-to-commit and would make this test non-hermetic."""
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["other.py"])
        command = f'git commit -m "{message}" -- hooks/agent_budget.py'
        captured = {}

        def spy(_dir, _last, _repo, paths, _win, _thr):
            captured["paths"] = list(paths)
            return {"newly_flagged": {}}

        monkeypatch.setattr(ptb.ct, "observe_commit_for_event", spy)
        ptb._churn_observe(_payload(command), command, "")
        assert captured.get("paths") == ["hooks/agent_budget.py"]

    @requires_git
    def test_churn_observe_e2e_message_row_never_records_other_agents_staged_file(
        self, sandbox, monkeypatch, git_repo
    ):
        """Item 1 e2e (08-25 round 3): same regression as the unit-level
        parametrize above, but driven through the REAL resolve_block
        dispatch (the `sandbox` fixture already repoints HOME into a tmp
        dir) with gate 3b disabled via CSA_NO_PRECOMMIT_REVIEW=1 so this
        purely isolates gate 6's own recording, matching the pattern the
        other end-to-end redirect tests in this class already use. Proves
        another agent's in-flight staged file (other.py) is never swept into
        THIS commit's recorded scope just because its own commit message
        happens to carry the mandated Co-Authored-By trailer."""
        monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", "1")
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "other.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "other.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        # Another agent's in-flight staged change on a DIFFERENT file.
        (git_repo / "other.py").write_text("1\n")
        _git(git_repo, "add", "other.py")

        command = 'git commit -m "Co-Authored-By: Claude <noreply@anthropic.com>" -- a.py'
        block, _detail = ptb.resolve_block(
            _payload(command, cwd=str(git_repo)), command, str(git_repo)
        )
        assert block is None

        live = ptb.ct.read_live_commits(str(sandbox.churn_dir), 7200)
        assert len(live) == 1
        assert live[0]["paths"] == ["a.py"]  # never other.py

    @requires_git
    def test_churn_observe_end_to_end_redirect_command_records_only_real_path(
        self, sandbox, monkeypatch, git_repo
    ):
        """Same command shape driven through REAL git via resolve_block, so
        the fix is proven at the actual ledger, not just the mocked call.
        No further staged change after genesis: an EXPLICIT pathspec makes
        _commit_target_paths return the command's own tokens regardless of
        actual git state. Gate 3b is disabled via its own documented
        kill-switch for this test: since the #4933 fix, `2> /dev/null`'s
        outside-repo token correctly DENIES at 3b (the old behavior this
        test used to lean on — "clean tree keeps 3b a no-op fail-open" —
        was the exact bypass #4933 closed), and this test's subject is gate
        6's OWN token filtering, not 3b. The 3b deny itself is covered by
        TestTokensOutsideRepo4933."""
        monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", "1")
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        command = 'git commit -m x -- a.py 2> /dev/null'
        ptb.resolve_block(_payload(command, cwd=str(git_repo)), command, str(git_repo))

        live = ptb.ct.read_live_commits(str(sandbox.churn_dir), 7200)
        assert len(live) == 1
        assert live[0]["paths"] == ["a.py"]  # never "2>" or "/dev/null"

    @requires_git
    def test_churn_observe_end_to_end_chained_command_records_both_commits(
        self, sandbox, monkeypatch, git_repo
    ):
        """End-to-end regression for the worst old failure mode: a chained
        command whose FIRST commit carries a self-contained `2>&1` must not
        destroy the SECOND commit's own real pathspec."""
        (git_repo / "a.py").write_text("0\n")
        (git_repo / "b.py").write_text("0\n")
        _git(git_repo, "add", "a.py", "b.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")

        command = 'git commit -m x -- a.py 2>&1 && git commit -m y -- b.py'
        ptb.resolve_block(_payload(command, cwd=str(git_repo)), command, str(git_repo))

        live = ptb.ct.read_live_commits(str(sandbox.churn_dir), 7200)
        assert len(live) == 1
        assert live[0]["paths"] == ["a.py", "b.py"]


# ===========================================================================
# NIT 25 — resolve_block computes `staged`/`targets`/`repo_root` ONCE and
# threads them into gates 3/4/6, instead of each gate independently
# re-deriving the same data via its own subprocess call.
# ===========================================================================


class TestNit25SharedTargetsRepoRoot:
    def test_read_staged_paths_called_at_most_once_per_guarded_commit(self, sandbox, monkeypatch):
        calls = []

        def spy(where):
            calls.append(where)
            return ["a.py"]

        monkeypatch.setattr(ptb.css, "read_staged_paths", spy)
        # Before the fix: gate 3 (via _staged_scope_block), gate 4 (via
        # _commit_target_paths' fallback), and gate 6 (same fallback) each
        # called this independently -> 3 calls for one event. After: 1.
        ptb.resolve_block(_payload('git commit -m "wip"'), 'git commit -m "wip"', "")
        assert len(calls) == 1

    def test_repo_root_of_called_at_most_once_per_guarded_commit(self, sandbox, monkeypatch):
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        calls = []

        def spy(where):
            calls.append(where)
            return "/resolved/repo"

        monkeypatch.setattr(ptb.ct, "repo_root_of", spy)
        ptb.resolve_block(_payload('git commit -m "wip"'), 'git commit -m "wip"', "")
        assert len(calls) == 1

    def test_not_guarded_event_computes_neither(self, sandbox, monkeypatch):
        def boom_staged(_w):
            raise AssertionError("must not read the index for a non-commit")

        def boom_root(_w):
            raise AssertionError("must not resolve repo root for a non-commit")

        monkeypatch.setattr(ptb.css, "read_staged_paths", boom_staged)
        monkeypatch.setattr(ptb.ct, "repo_root_of", boom_root)
        block, detail = ptb.resolve_block(_payload("git status"), "git status", "")
        assert block is None and detail == {}

    def test_gate3_and_gate4_and_gate6_see_the_same_targets(self, sandbox, monkeypatch, tmp_path):
        # The SAME staged index feeds gate 3's out-of-scope check, gate 4's
        # claim, and gate 6's churn observation for one event -- prove it by
        # asserting the claim ledger and the churn ledger both recorded
        # exactly the index _staged_scope_block was fed too (no drift between
        # independently-derived values). cwd is a non-repo tmp_path so no
        # commit-mutex token is ALSO claimed (that has its own test section).
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        block, _detail = ptb.resolve_block(
            _payload('git commit -m "feat(voice): x"', cwd=str(tmp_path)),
            'git commit -m "feat(voice): x"',
            str(tmp_path),
        )
        assert block is None
        live_claims = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert live_claims[0]["paths"] == ["modules/voice/a.py"]

    @requires_git
    def test_end_to_end_via_real_git_repo_still_flags_churn(self, sandbox, monkeypatch, git_repo):
        # Full end-to-end regression through a REAL repo: the shared
        # staged/targets/repo_root plumbing doesn't break the existing
        # 3rd-touch churn-flagged behavior.
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["a.py"])
        (git_repo / "a.py").write_text("0\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        for i in range(3):
            _run_main(monkeypatch, _payload(f'git commit -m "wip{i}"', cwd=str(git_repo)))
            (git_repo / "a.py").write_text(f"{i + 1}\n")
            _git(git_repo, "add", "a.py")
            _git(git_repo, "commit", "-q", "-m", f"c{i}")
        _run_main(monkeypatch, _payload('git commit -m "wip-final"', cwd=str(git_repo)))
        logs = _read_log(sandbox)
        flagged = [r for r in logs if r.get("hook") == ptb.ct.HOOK_NAME and r.get("decision") == "churn-flagged"]
        assert flagged and flagged[0]["path"] == "a.py"


# ===========================================================================
# Gate 5 — gh_issue_close_gate: BLOCKER 1. Wired via pretooluse_bash's own
# gate chain AND reachable through the real dispatch path (bash_gate.sh's
# fast-path -> pretooluse_bash.py), not merely importable in isolation.
# ===========================================================================

FAKE_SHA = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"


class TestGateGhIssueClose:
    def test_fabricated_sha_close_log_only(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload(f"gh issue close 5 --comment 'Fixes {FAKE_SHA}'"),
        )
        assert rc == 0 and out == ""  # log-only default
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == ptb.gicg.HOOK_NAME
        assert FAKE_SHA in rec["reason"]

    def test_fabricated_sha_close_enforce_emits_deny(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload(f"gh issue close 5 --comment 'Fixes {FAKE_SHA}'"),
            env={"CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("gh_issue_close_gate")
        assert FAKE_SHA in obj["systemMessage"]
        rec = _read_log(sandbox)[0]
        assert rec["gate"] == ptb.gicg.HOOK_NAME

    def test_no_commit_close_blocks_when_enforcing(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("gh issue close 5"), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        assert "no resolving commit" in json.loads(out)["systemMessage"]

    @requires_git
    def test_real_sha_close_allowed_when_enforcing(self, sandbox, monkeypatch, git_repo):
        (git_repo / "a.py").write_text("x\n")
        _git(git_repo, "add", "a.py")
        _git(git_repo, "commit", "-q", "-m", "genesis")
        real_sha = _git(git_repo, "rev-parse", "HEAD").stdout.decode().strip()
        rc, out = _run_main(
            monkeypatch,
            _payload(f"gh issue close 5 --comment 'Fixes {real_sha}'", cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""  # allowed: real commit
        assert _read_log(sandbox) == []

    def test_not_an_issue_close_never_reaches_this_gate(self, sandbox, monkeypatch):
        def boom(_ev):
            raise AssertionError("gh_issue_close_gate must not run for a non-close command")

        monkeypatch.setattr(ptb.gicg, "decide", boom)
        block, detail = ptb._gh_issue_close_block(_payload("git status"), "git status")
        assert block is None and detail == {}

    def test_orthogonal_to_branch_ops_gate_a_git_reset_never_trips_it(self, sandbox, monkeypatch):
        # A pure git-state command must never even reach gh_issue_close_gate's
        # decide() in a way that could block it -- is_issue_close's own
        # pre-check no-ops for non-`gh issue close` commands, proven directly.
        block, detail = ptb._gh_issue_close_block(_payload("git reset --hard"), "git reset --hard")
        assert block is None and detail == {}

    def test_resolve_block_reaches_gate5_after_gates1_4_pass(self, sandbox, monkeypatch):
        # An ordinary read-only command reaches (and is allowed by) every gate
        # up to and including gate 5, proving the chain actually wires it in
        # rather than dead-ending before it.
        block, detail = ptb.resolve_block(_payload("gh issue close 9"), "gh issue close 9", "")
        assert block is not None
        assert block.hook == ptb.gicg.HOOK_NAME


# ===========================================================================
# BLOCKER 1 — end-to-end proof through the REAL dispatch path: bash_gate.sh's
# own fast-path case statement -> pretooluse_bash.py. Not gate.decide() called
# directly, and not pretooluse_bash.py invoked directly either — this is the
# actual settings.json-wired entry point (`bash ~/.claude/hooks/bash_gate.sh`).
# ===========================================================================


class TestBashGateShEndToEnd:
    """Drives the REAL, unmodified bash_gate.sh -> pretooluse_bash.py -> the
    real gate modules, with $HOME repointed at a throwaway sandbox so the
    operator's real ~/.claude enforcement/review/claims state is never
    touched. Only `.claude/hooks` itself is symlinked back to the REAL hooks
    directory (so bash_gate.sh's own literal `$HOME/.claude/hooks/
    pretooluse_bash.py` path resolves to the actual dispatcher under test,
    not a copy) -- every STATE directory `_lib` writes to (`.enforce`,
    `.enforcement/`, `.review_state/`, `.file_claims/`, `.churn/`) lives
    directly under the sandboxed `$HOME/.claude/`, outside that symlink, so
    it is fully isolated.
    """

    def _sandbox_home(self, tmp_path) -> "os.PathLike[str]":
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        os.symlink(ptb._HOOKS_DIR, home / ".claude" / "hooks")
        return home

    def _run_bash_gate(self, payload: dict, *, cwd, env_extra=None):
        env = dict(os.environ)
        env.pop("CSA_DISABLE_HOOKS", None)
        env.pop("CSA_ENFORCE", None)
        if env_extra:
            env.update(env_extra)
        script = os.path.join(ptb._HOOKS_DIR, "bash_gate.sh")
        return subprocess.run(
            ["bash", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(cwd),
            env=env,
        )

    def test_fast_path_previously_skipped_gh_issue_close_now_dispatches(self, tmp_path):
        """Before the fix, bash_gate.sh's case pattern only matched a payload
        containing 'git' or the escape-var literal -- a `gh issue close ...`
        payload (no 'git' token) fell through the `*)` arm and exited 0
        WITHOUT ever invoking python3/pretooluse_bash.py, so gh_issue_close_gate
        could never fire no matter what it cited. This drives the REAL script,
        with a fabricated (non-ancestor) commit sha AND a prod-deploy claim, and
        proves it now actually reaches the dispatcher and is DENIED under
        enforcement.
        """
        home = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f"gh issue close 42 --comment 'Fixes {FAKE_SHA}. "
                    "Deployed to production. Also verified on staging.'"
                )
            },
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0  # deny is JSON, never a nonzero exit
        obj = json.loads(proc.stdout)
        assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "gh_issue_close_gate" in obj["systemMessage"]
        assert FAKE_SHA in obj["systemMessage"]

    def test_fast_path_still_skips_unrelated_commands_no_python_spawn(self, tmp_path):
        # A command containing neither 'git' nor the gh-issue-close shape still
        # exits 0 with empty stdout straight from the bash arm (no python spawn,
        # no log write) -- the fast-path's whole point is preserved.
        home = self._sandbox_home(tmp_path)
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert not (home / ".claude" / ".enforcement" / "log.jsonl").exists()

    def test_fast_path_log_only_default_would_deny(self, tmp_path):
        # No CSA_ENFORCE / no global .enforce marker -> LOG-ONLY: reached and
        # logged, but not emitted/blocked.
        home = self._sandbox_home(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": f"gh issue close 42 --comment 'Fixes {FAKE_SHA}'"},
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0
        assert proc.stdout == ""
        log = home / ".claude" / ".enforcement" / "log.jsonl"
        assert log.exists()
        rec = json.loads(log.read_text().strip().splitlines()[-1])
        assert rec["gate"] == "gh_issue_close_gate"
        assert rec["decision"] == "would-block"

    def test_fast_path_dispatches_a_gcloud_identity_mutation_and_denies_it(self, tmp_path):
        """#5310: before adding `*gcloud*` to bash_gate.sh's case pattern,
        a payload mentioning ONLY 'gcloud' (no 'git' token) would fall through
        the `*)` arm and exit 0 WITHOUT ever invoking python3/
        pretooluse_bash.py -- block_gcloud_identity could never fire no
        matter what identity-mutating command it named. Drives the REAL
        script end to end and proves it now reaches the dispatcher and is
        DENIED under enforcement."""
        home = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "gcloud config set account other@example.com"},
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0  # deny is JSON, never a nonzero exit
        obj = json.loads(proc.stdout)
        assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "block_gcloud_identity" in obj["systemMessage"]
        assert "config-set-account" in obj["systemMessage"]

    def test_fast_path_dispatches_bare_gh_issue_create_to_observer(self, tmp_path):
        """#5827: before adding `*gh*issue*create*` to
        bash_gate.sh's case pattern, a bare `gh issue create ...` payload
        (no 'git' token, no 'close') would fall through the `*)` arm and
        exit 0 WITHOUT ever invoking python3/pretooluse_bash.py --
        issue_create_observer could never fire. Drives the REAL script end
        to end and proves the observer logs `bare-issue-create` AND the
        command is still ALLOWED (never a deny — this observer never
        blocks, even under enforcement)."""
        home = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'gh issue create --title "x" --body "y"'},
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0
        assert proc.stdout == ""  # never a deny -- pure observer, always allowed
        log = home / ".claude" / ".enforcement" / "log.jsonl"
        assert log.exists()
        rec = json.loads(log.read_text().strip().splitlines()[-1])
        assert rec["hook"] == "issue_create_observer"
        assert rec["decision"] == "bare-issue-create"

    def test_fast_path_dispatches_gh_issue_sh_create_to_observer(self, tmp_path):
        """The gh_issue.sh helper-path shape (no bare 'gh issue' tokens
        adjacent) must ALSO reach the dispatcher via the `*gh_issue.sh*
        create*` fast-path arm, and a create missing --priority/labels logs
        `create-missing-triage-would-deny` while still being ALLOWED."""
        home = self._sandbox_home(tmp_path)
        (home / ".claude" / ".enforce").write_text("")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "~/.claude/scripts/gh_issue.sh create --title x --body-file b.md"
            },
            "cwd": str(tmp_path),
        }
        proc = self._run_bash_gate(payload, cwd=tmp_path, env_extra={"HOME": str(home)})
        assert proc.returncode == 0
        assert proc.stdout == ""
        log = home / ".claude" / ".enforcement" / "log.jsonl"
        assert log.exists()
        rec = json.loads(log.read_text().strip().splitlines()[-1])
        assert rec["hook"] == "issue_create_observer"
        assert rec["decision"] == "create-missing-triage-would-deny"
        assert set(rec["missing"]) == {
            "priority",
            "type-label",
            "area-label",
            "difficulty-label",
        }


# ===========================================================================
# SAFE commands — path-scoped add/commit, read-only git, non-git all pass.
# ===========================================================================


class TestSafeCommandsAllow:
    @pytest.mark.parametrize(
        "command",
        [
            "git add ./modules/voice/x.py",
            'git add file.py && git commit -m "feat(voice): x" -- modules/voice/x.py',
            "git status",
            "git diff",
            "git log --oneline",
            "git push origin HEAD",
            "ls -la",
            "rm -rf build",
        ],
    )
    def test_safe_command_allows_no_log(self, sandbox, monkeypatch, command):
        # Stub the index reader so any commit segment sees a clean, in-scope index.
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/x.py"])
        rc, out = _run_main(monkeypatch, _payload(command), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_non_bash_tool_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("git reset --hard", tool_name="Read"),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_empty_command_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, _payload("   "), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []


# ===========================================================================
# MASTER OFF — CSA_DISABLE_HOOKS=1 neutralizes everything.
# ===========================================================================


class TestMasterOff:
    def test_disable_neutralizes_state_verb_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("git reset --hard"),
            env={"CSA_ENFORCE": "1", "CSA_DISABLE_HOOKS": "1"},
        )
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []  # disabled -> no evaluation, no log

    def test_disable_overrides_global_marker(self, sandbox, monkeypatch):
        sandbox.enforce_file.write_text("")
        rc, out = _run_main(
            monkeypatch, _payload("git reset --hard"), env={"CSA_DISABLE_HOOKS": "1"}
        )
        assert out == ""


# ===========================================================================
# FIRST-BLOCK-WINS ordering — gate 1 (branch-ops) precedes gate 2/3.
# ===========================================================================


class TestFirstBlockWins:
    def test_branch_ops_wins_over_later_gates(self, sandbox, monkeypatch):
        # `git commit -a` is BOTH a gate-1 block (commit-all) and a gate-2 block
        # (commit-all). Gate 1 must win: the logged gate is block_branch_ops and
        # the emitted message is its message, never gate 2/3's.
        rc, out = _run_main(
            monkeypatch, _payload('git commit -a -m "x"'), env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert obj["systemMessage"].startswith("block_branch_ops")
        recs = _read_log(sandbox)
        assert len(recs) == 1  # exactly one block logged (first wins, stop)
        assert recs[0]["gate"] == "block_branch_ops"
        assert recs[0]["reason"] == "commit-all"

    def test_resolve_block_short_circuits_on_first(self, sandbox, monkeypatch):
        # resolve_block must NOT consult gate 2/3 once gate 1 blocks. We prove it by
        # making gate 2 explode; a short-circuit means it is never called.
        def boom(_ev):
            raise AssertionError("gate 2 must not run after gate 1 blocks")

        monkeypatch.setattr(ptb.buc, "decide", boom)
        block, detail = ptb.resolve_block(
            _payload("git reset --hard"), "git reset --hard", ""
        )
        assert block is not None
        assert block.hook == "block_branch_ops"


# ===========================================================================
# ESCAPE HATCH (OWN env) + inline tripwire.
# ===========================================================================


class TestEscapeHatch:
    def test_own_env_escape_allows_state_verb(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1", "CSA_ENFORCE": "1"},
        )
        assert rc == 0 and out == ""  # escaped -> no deny even under enforce
        rec = _read_log(sandbox)[0]
        assert rec["decision"] == "escape-allowed"
        assert rec["gate"] == "block_branch_ops"
        assert rec["reason"] == "state-verb:reset"

    def test_inline_tripwire_not_escapable(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("CSA_ALLOW_GIT_STATE_OPS=1 git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1", "CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "inline-escape-var-forbidden" in obj["systemMessage"]

    def test_inline_tripwire_log_only_default(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, _payload("CSA_ALLOW_GIT_STATE_OPS=1 git reset")
        )
        assert out == ""  # log-only default
        assert _read_log(sandbox)[0]["reason"] == "inline-escape-var-forbidden"

    def test_escape_hatch_does_not_rescue_staged_scope_block(self, sandbox, monkeypatch):
        # The index-scope gate has NO escape hatch: CSA_ALLOW_GIT_STATE_OPS must not
        # rescue a gate-3 block (git_state=False).
        monkeypatch.setattr(
            ptb.css,
            "read_staged_paths",
            lambda _w: [f"dir{i}/f.py" for i in range(10)],
        )
        rc, out = _run_main(
            monkeypatch,
            _payload('git commit -m "wip"'),
            env={"CSA_ALLOW_GIT_STATE_OPS": "1", "CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)  # not escaped
        assert _read_log(sandbox)[0]["decision"] == "would-block"

    def test_escape_var_non_1_does_not_escape(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch,
            _payload("git reset --hard"),
            env={"CSA_ALLOW_GIT_STATE_OPS": "0", "CSA_ENFORCE": "1"},
        )
        assert _is_deny(out)


# ===========================================================================
# PARSE-ERROR fail-closed — a malformed payload that mentions git blocks.
# ===========================================================================


class TestParseError:
    def test_malformed_json_with_git_fails_closed_under_enforce(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, "not json at all git reset --hard", env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)
        rec = _read_log(sandbox)[0]
        assert rec["reason"] == "parse-error-with-git-token"
        assert rec["gate"] == "block_branch_ops"

    def test_malformed_json_with_git_log_only(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "not json at all git reset --hard")
        assert out == ""  # log-only
        assert _read_log(sandbox)[0]["reason"] == "parse-error-with-git-token"

    def test_malformed_json_no_git_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "total garbage not json here")
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_empty_stdin_allows(self, sandbox, monkeypatch):
        rc, out = _run_main(monkeypatch, "")
        assert rc == 0 and out == ""
        assert _read_log(sandbox) == []

    def test_non_dict_json_with_git_token_fails_closed(self, sandbox, monkeypatch):
        rc, out = _run_main(
            monkeypatch, '["git", "reset", "--hard"]', env={"CSA_ENFORCE": "1"}
        )
        assert _is_deny(out)

    def test_stdin_read_raises_treated_as_no_git(self, sandbox, monkeypatch):
        class Boom:
            def read(self):
                raise OSError("no stdin")

        monkeypatch.setattr("sys.stdin", Boom())
        buf = io.StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        rc = ptb.main()
        assert rc == 0 and buf.getvalue() == ""


# ===========================================================================
# resolve_block / _finish direct coverage of the remaining branches.
# ===========================================================================


class TestResolveAndFinishDirect:
    def test_resolve_block_no_block_returns_none(self, sandbox, monkeypatch):
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: [])
        block, detail = ptb.resolve_block(_payload("git status"), "git status", "")
        assert block is None and detail == {}

    def test_resolve_block_swallows_internal_error(self, sandbox, monkeypatch):
        # A gate raising unexpectedly -> resolve_block degrades to no-block.
        def boom(_c):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(ptb.bbo, "decision", boom)
        block, detail = ptb.resolve_block(_payload("git reset"), "git reset", "")
        assert block is None and detail == {}

    def test_staged_scope_gate_not_guarded_for_non_commit(self, sandbox, monkeypatch):
        # should_guard False (a non-commit git op) -> gate 3 returns no block and
        # never reads the index.
        def boom(_w):
            raise AssertionError("index must not be read for a non-commit")

        monkeypatch.setattr(ptb.css, "read_staged_paths", boom)
        block, detail = ptb._staged_scope_block(_payload("git status"), "")
        assert block is None and detail == {}

    def test_staged_scope_block_reads_the_index_itself_when_staged_not_passed(self, sandbox, monkeypatch):
        # Direct call with NO precomputed `staged` (the NIT 25 default-None
        # fallback path) -- must read the index itself, exactly as before
        # resolve_block started passing it down. No pathspec on the command,
        # so CSA_NO_REQUIRE_PATHSPEC=1 reaches the staged-index path this
        # test is actually about.
        monkeypatch.setenv("CSA_NO_REQUIRE_PATHSPEC", "1")
        monkeypatch.setattr(ptb.css, "read_staged_paths", lambda _w: ["modules/voice/a.py"])
        block, detail = ptb._staged_scope_block(_payload('git commit -m "feat(voice): x"'), "")
        assert block is None and detail == {}

    def test_finish_none_is_noop(self, sandbox, clean_env):
        assert ptb._finish(None, {}, "ls", "") == 0
        assert _read_log(sandbox) == []

    def test_finish_git_state_block_log_only(self, sandbox, clean_env):
        block = ptb._Block("block_branch_ops", "state-verb:reset", "msg", git_state=True)
        rc = ptb._finish(block, {}, "git reset", "")
        assert rc == 0
        assert _read_log(sandbox)[0]["decision"] == "would-block"

    def test_finish_would_block_enforce_field_uses_event_cwd_not_process_default(
        self, sandbox, clean_env, monkeypatch
    ):
        """R6 (08-25 fix round): _finish must pass its OWN `enforcing(where)`
        into log() as an explicit `enforce=` kwarg, rather than letting
        log()'s bare internal enforcing() call fall back to os.getcwd() (the
        PROCESS cwd, which can genuinely differ from the EVENT's own cwd).
        Proven by making the two resolve to DIFFERENT values: a fake
        enforcing() that is True ONLY for the event's cwd sentinel string —
        if _finish ever calls log() without the override, log()'s own bare
        `enforcing()` call (no arg) hits this fake with cwd=None and reads
        False, so the logged field would mismatch the real deny that
        actually fired."""

        def fake_enforcing(cwd=None):
            return cwd == "the-real-event-cwd"

        monkeypatch.setattr(ptb._lib, "enforcing", fake_enforcing)
        block = ptb._Block("gate", "reason", "msg", git_state=False)
        rc = ptb._finish(block, {}, "git reset", "the-real-event-cwd")
        assert rc == 0
        rec = _read_log(sandbox)[-1]
        assert rec["decision"] == "would-block"
        assert rec["enforce"] is True  # matches the deny that ACTUALLY fired

    def test_finish_git_state_block_enforce_emits(self, sandbox, clean_env, monkeypatch, capsys):
        monkeypatch.setenv("CSA_ENFORCE", "1")
        block = ptb._Block("block_branch_ops", "state-verb:reset", "MESSAGE", git_state=True)
        ptb._finish(block, {}, "git reset", "")
        out = capsys.readouterr().out
        assert _is_deny(out)
        assert json.loads(out)["systemMessage"] == "MESSAGE"

    def test_finish_escape_hatch_logs_escape_allowed(self, sandbox, clean_env, monkeypatch):
        monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
        monkeypatch.setenv("CSA_ENFORCE", "1")
        block = ptb._Block("block_branch_ops", "state-verb:reset", "msg", git_state=True)
        rc = ptb._finish(block, {}, "git reset", "")
        assert rc == 0
        assert _read_log(sandbox)[0]["decision"] == "escape-allowed"

    def test_finish_tripwire_not_escapable_direct(self, sandbox, clean_env, monkeypatch, capsys):
        monkeypatch.setenv("CSA_ALLOW_GIT_STATE_OPS", "1")
        monkeypatch.setenv("CSA_ENFORCE", "1")
        block = ptb._Block(
            "block_branch_ops", "inline-escape-var-forbidden", "TRIP", git_state=True
        )
        ptb._finish(block, {}, "x", "")
        assert _is_deny(capsys.readouterr().out)


# ===========================================================================
# Entry point — cover the __main__ guard via a real (sandboxed) subprocess.
# ===========================================================================


class TestScriptEntryPoint:
    def test_module_runs_as_script_enforce_deny(self, tmp_path):
        """Invoke the module as `python pretooluse_bash.py` with a sandbox HOME.

        Exercises `if __name__ == "__main__": sys.exit(main())`. HOME points into
        tmp_path so no real ~/.claude is touched; enforcement is ON via a global
        .enforce marker so a state verb emits the canonical deny. No network.
        """
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / ".enforce").write_text("")
        module_path = os.path.join(ptb._HOOKS_DIR, "pretooluse_bash.py")
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}})
        env = dict(os.environ)
        env["HOME"] = str(home)
        for var in ("CSA_ENFORCE", "CSA_DISABLE_HOOKS", "CSA_ALLOW_GIT_STATE_OPS"):
            env.pop(var, None)
        proc = subprocess.run(
            [sys.executable, module_path],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert proc.returncode == 0
        assert _is_deny(proc.stdout)


# ===========================================================================
# Import-time sys.path shim — exercise the insert-when-missing branch.
# ===========================================================================


def test_import_inserts_hooks_dir_when_missing(monkeypatch):
    import os as _os
    import sys as _sys

    hooks_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    src = _os.path.join(hooks_dir, "pretooluse_bash.py")
    with open(src, encoding="utf-8") as fh:
        code = fh.read()

    monkeypatch.setattr(_sys, "path", [p for p in _sys.path if p != hooks_dir])
    ns = {"__file__": src, "__name__": "pretooluse_bash_reimport"}
    exec(compile(code, src, "exec"), ns)  # noqa: S102 - deliberate re-exec of our own module

    assert hooks_dir in _sys.path  # the guard inserted it back
    assert ns["HOOK_NAME"] == "pretooluse_bash"
    block, _detail = ns["resolve_block"](
        {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}},
        "git reset --hard",
        "",
    )
    assert block is not None and block.hook == "block_branch_ops"


# ===========================================================================
# #5061: `cd <dir> && git ...` cross-repo resolution.
#
# The gate chain used to resolve the SESSION's own cwd for a cd-prefixed
# commit into a DIFFERENT repo, taking the wrong mutex/digest/authorship for
# the repo actually being committed to. `effective_git_cwd` (via
# `_leading_cd_dir`, see test_lib.py) fixes this at the shared resolution
# point every one of these gates reads from.
# ===========================================================================


class TestCdPrefixCrossRepoResolution:
    def test_cd_prefixed_commit_resolves_the_target_repo_not_the_session_cwd(
        self, sandbox, monkeypatch, git_repo, tmp_path
    ):
        """The strongest single observable this dispatcher exposes: the
        `out["repo_root"]` channel `resolve_block` fills for `_finish`'s own
        enforcement-log `repo` field (see resolve_block's own docstring,
        telemetry plan §4.2a). A cd-prefixed commit issued from repoA's own
        session cwd must resolve repoB -- the cd TARGET -- not repoA."""
        import record_review as rr

        repoA = tmp_path / "repoA-session-cwd"
        repoA.mkdir()
        _git(repoA, "init", "-q")

        repoB = git_repo
        (repoB / "a.py").write_text("0\n")
        _git(repoB, "add", "a.py")
        _git(repoB, "commit", "-q", "-m", "genesis")
        (repoB / "a.py").write_text("1\n")

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(
            ["record_review.py", str(repoB), "--pre-commit", "--clean", "--paths", "a.py"]
        )

        cmd = f'cd {repoB} && git commit -m "fix: x" -- a.py'
        ev = _payload(cmd, cwd=str(repoA))
        out: dict = {}
        block, _detail = ptb.resolve_block(ev, cmd, str(repoA), out)
        assert block is None  # reviewed content, real repo -> nothing blocks
        assert out.get("repo_root") == str(repoB)

    def test_cd_prefixed_commit_claims_the_target_repos_real_paths(
        self, sandbox, monkeypatch, git_repo, tmp_path
    ):
        """A second, independent observable: the file_claims ledger itself
        records the cd-TARGET repo's paths, not anything scoped to the
        session's own cwd (file_claims claims carry no repo dimension of
        their own -- see CLAUDE.md's own note on this -- so this is proven
        via the actual claimed path list plus the commit succeeding without
        contest against repoA)."""
        import record_review as rr

        repoA = tmp_path / "repoA-session-cwd-2"
        repoA.mkdir()
        _git(repoA, "init", "-q")

        repoB = git_repo
        (repoB / "b.py").write_text("0\n")
        _git(repoB, "add", "b.py")
        _git(repoB, "commit", "-q", "-m", "genesis")
        (repoB / "b.py").write_text("1\n")

        monkeypatch.setenv("CSA_ENFORCE", "1")
        rr.main(
            ["record_review.py", str(repoB), "--pre-commit", "--clean", "--paths", "b.py"]
        )
        monkeypatch.delenv("CSA_ENFORCE", raising=False)

        cmd = f'cd {repoB} && git commit -m "fix: x" -- b.py'
        rc, out = _run_main(monkeypatch, _payload(cmd, cwd=str(repoA)), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and out == ""
        live = ptb.fc.read_live_claims(str(sandbox.file_claims_dir), 300)
        assert live
        claimed_paths = set(live[0]["paths"])
        # The real path claimed is repoB's own "b.py" (never re-based onto
        # repoA, the session's own cwd), and the synthetic commit-mutex
        # token claimed alongside it is keyed to repoB's toplevel -- the
        # exact cross-repo resolution this issue exists to fix, proven via
        # the mutex_token() helper's OWN computation for repoB specifically.
        assert "b.py" in claimed_paths
        assert ptb.fc.mutex_token(str(repoB)) in claimed_paths

    def test_cd_prefixed_commits_to_the_same_target_repo_contest_via_the_mutex(
        self, sandbox, monkeypatch, git_repo, tmp_path
    ):
        """THE cross-repo mutex regression this issue exists to fix: TWO
        cd-prefixed commits, issued from TWO DIFFERENT session cwds, that
        both cd into the SAME repoB must contest each other via the
        per-repo commit mutex -- the pre-fix behavior computed a DIFFERENT
        (wrong, session-cwd-keyed) mutex token for each, so they never
        contested at all."""
        repoA1 = tmp_path / "repoA1"
        repoA1.mkdir()
        _git(repoA1, "init", "-q")
        repoA2 = tmp_path / "repoA2"
        repoA2.mkdir()
        _git(repoA2, "init", "-q")

        repoB = git_repo
        (repoB / "a.py").write_text("0\n")
        (repoB / "b.py").write_text("0\n")
        _git(repoB, "add", "a.py", "b.py")
        _git(repoB, "commit", "-q", "-m", "genesis")
        # No pending edit to b.py: nothing pending for gate 3b to review,
        # so this test isolates the MUTEX behavior specifically (matches
        # TestCommitMutex's own established convention above).

        mutex = ptb.fc.mutex_token(str(repoB))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["a.py", mutex], lock_timeout=1.0
        )

        cmd = f'cd {repoB} && git commit -m "fix: x" -- b.py'
        rc, out = _run_main(
            monkeypatch,
            _payload(cmd, cwd=str(repoA2)),
            env={
                "CSA_ENFORCE": "1",
                "CSA_COMMIT_CLAIM_MAX_WAIT_SEC": "0.1",
                "CSA_COMMIT_CLAIM_POLL_SEC": "0.05",
            },
        )
        assert _is_deny(out)
        obj = json.loads(out)
        assert "commit-in-flight" in obj["systemMessage"]

    def test_cd_prefixed_commit_to_a_different_repo_does_not_contest(
        self, sandbox, monkeypatch, git_repo, tmp_path
    ):
        """Paired negative control: a cd-prefixed commit into a DIFFERENT
        target repo than the one already claimed must NOT contest -- proves
        the mutex is keyed to the cd TARGET, not merely "any cd-prefixed
        command contests everything"."""
        repoA = tmp_path / "repoA-negative"
        repoA.mkdir()
        _git(repoA, "init", "-q")
        repoC = tmp_path / "repoC-unrelated"
        repoC.mkdir()
        _git(repoC, "init", "-q")

        repoB = git_repo
        (repoB / "a.py").write_text("0\n")
        _git(repoB, "add", "a.py")
        _git(repoB, "commit", "-q", "-m", "genesis")
        # No pending edit -> nothing for gate 3b to review; isolates mutex.

        mutex = ptb.fc.mutex_token(str(repoC))
        ptb.fc.try_claim_paths(
            str(sandbox.file_claims_dir), 300, "other-agent", ["x.py", mutex], lock_timeout=1.0
        )

        cmd = f'cd {repoB} && git commit -m "fix: x" -- a.py'
        rc, out = _run_main(monkeypatch, _payload(cmd, cwd=str(repoA)), env={"CSA_ENFORCE": "1"})
        assert rc == 0 and out == ""  # a DIFFERENT target repo -> no contest


# ===========================================================================
# Fix-round 1, finding 4: issue_create_observer import is DEFENSIVE — a
# missing/broken observer module must never fail this whole dispatcher open.
# ===========================================================================


class TestIssueCreateObserverImportGuard:
    """`ico` is None when the top-level `try: import issue_create_observer
    ... except Exception: ico = None` guard caught the module being absent
    or itself raising on import. Proves TWO things: (a) `_issue_create_
    observe` no-ops cleanly when `ico is None` rather than raising, and
    (b) — the actual finding-4 claim — a REPRESENTATIVE 35-command corpus
    (every shape every OTHER gate class in this file already tests: git
    state-mutations, bulk add/commit, path-scoped commits missing/present
    review+claims, gh issue close (fabricated + real sha), protected-board
    adds, gh issue/gh_issue.sh create shapes, and ordinary unrelated
    commands) makes the IDENTICAL allow/deny decision whether `ico` is the
    real module or None — i.e. removing/breaking this one observer can
    never change what any OTHER gate in this dispatcher decides.
    """

    # 35 representative commands spanning every gate class in this dispatcher.
    _CORPUS = [
        # gate 1 — block_branch_ops state verbs
        "git checkout main",
        "git switch main",
        "git stash",
        "git reset --hard HEAD~1",
        "git rebase main",
        "git restore file.py",
        "git clean -fd",
        "git branch -D old",
        "git worktree add ../x",
        # gate 1 carve-outs — allowed
        "git worktree list",
        "git restore --staged file.py",
        # gate 1b — head-overwrite
        "git show HEAD:a.py > a.py",
        # gate 1c — gcloud identity
        "gcloud config set account other@example.com",
        "gcloud auth list",
        # gate 2 — bulk add/commit
        "git add -A",
        "git add .",
        'git commit -am "wip"',
        # gate 3/3b/4 — path-scoped commit shapes (no repo, so these resolve
        # via the no-repo-root/no-HEAD fail-open paths rather than a real
        # review/claim cycle — still real gate territory, just the
        # already-established "no repo" branch every sibling test in this
        # file also exercises for these commands)
        'git commit -m "wip" -- a.py',
        'git commit -m "wip"',
        "git commit --amend",
        # gate 5 — gh issue close
        'gh issue close 42 --comment "Fixes deadbeefcafefeedfacefeed0123456789abcdef"',
        "gh issue close 42",
        # gate 5b — protected board
        "gh project item-add 5 --owner example-org --url https://x",
        "gh project item-list 5 --owner example-org",
        # gate 6 — churn (reached only on a clean, non-blocked commit; still
        # exercised via the no-repo-root path like the gate 3/3b/4 rows)
        'git commit -m "chore: x" -- b.py',
        # the observer's OWN territory — bare gh issue create
        'gh issue create --title "x" --body "y"',
        "gh issue create --title x",
        # the observer's OWN territory — gh_issue.sh create (helper path)
        "~/.claude/scripts/gh_issue.sh create --title x --body-file b.md",
        "gh_issue.sh create --title x --priority P2 --label bug",
        # other gh_issue.sh / gh subcommands — NOT the observer's territory
        "gh_issue.sh comment 5 --body-file b.md",
        "gh_issue.sh transition 5 --status Backlog --project 1 --owner O",
        "gh issue edit 5 --add-label bug",
        "gh issue list --state open",
        # unrelated commands — nothing here should ever route to any gate
        "ls -la",
        "echo hello",
        "python3 -m pytest",
        "npm test",
    ]

    def test_corpus_has_at_least_35_commands(self):
        # Pin the corpus size so this test class's own claim ("35 corpus
        # commands") stays true as a structural fact, not just a docstring
        # assertion nobody re-checks.
        assert len(self._CORPUS) >= 35, len(self._CORPUS)

    @pytest.mark.parametrize("command", _CORPUS)
    def test_decision_identical_with_and_without_observer_module(
        self, sandbox, monkeypatch, command
    ):
        # Run 1: the REAL ico module present (normal operation).
        rc_with, out_with = _run_main(
            monkeypatch, _payload(command), env={"CSA_ENFORCE": "1"}
        )
        log_with = _read_log(sandbox)

        # Reset the sandbox's log file AND any file_claims claim written by
        # run 1 between the two runs. Without the claims wipe, a
        # commit-shaped command in the corpus (gate 4 territory) that
        # resolves a REAL repo toplevel takes a real claim in run 1 that run
        # 2 then self-contests against, polling the real ~45s
        # CSA_COMMIT_CLAIM_MAX_WAIT_SEC bound before denying -- a genuine
        # slow-fail/hang this test hit and fixed during fix-round 1's own
        # falsifiability pass, not a product defect (see the sibling
        # test_resolve_block_unaffected_by_missing_observer_for_unrelated_
        # command's own docstring for the same root cause, hit there via a
        # real git_repo fixture instead of an ambient toplevel).
        if sandbox.log_file.exists():
            sandbox.log_file.unlink()
        for name in os.listdir(sandbox.file_claims_dir) if sandbox.file_claims_dir.exists() else []:
            (sandbox.file_claims_dir / name).unlink()

        # Run 2: simulate the observer module being absent/broken -- exactly
        # what the top-level try/except import guard produces.
        monkeypatch.setattr(ptb, "ico", None)
        rc_without, out_without = _run_main(
            monkeypatch, _payload(command), env={"CSA_ENFORCE": "1"}
        )
        log_without = _read_log(sandbox)

        assert rc_with == rc_without, (command, rc_with, rc_without)
        assert out_with == out_without, (command, out_with, out_without)
        # Every OTHER gate's decision must appear identically in both logs
        # (ignoring any issue_create_observer rows, which by definition only
        # exist in the "with" run and are exactly what finding 4 says must
        # never influence any other gate's own decision). "ts" is excluded
        # from the comparison -- it is a real UTC wall-clock timestamp
        # written by _lib.log at call time, so a run whose two _run_main
        # calls straddle a real second boundary produces a GENUINELY
        # different (and irrelevant) "ts" value between them; comparing
        # every OTHER field is what actually proves "identical decision".
        def _without_ts(rows):
            return [{k: v for k, v in r.items() if k != "ts"} for r in rows]

        non_observer_with = _without_ts(
            [r for r in log_with if r.get("hook") != "issue_create_observer"]
        )
        non_observer_without = _without_ts(
            [r for r in log_without if r.get("hook") != "issue_create_observer"]
        )
        assert non_observer_with == non_observer_without, (
            command,
            non_observer_with,
            non_observer_without,
        )

    def test_issue_create_observe_noop_when_ico_is_none(self, monkeypatch):
        """Direct unit check of the no-op branch itself (finding 4's other
        half): _issue_create_observe must return cleanly, logging nothing,
        when ico is None -- never raise, never touch the None reference."""
        monkeypatch.setattr(ptb, "ico", None)
        # Must not raise.
        ptb._issue_create_observe('gh issue create --title "x"', "/tmp")

    def test_resolve_block_unaffected_by_missing_observer_for_unrelated_command(
        self, sandbox, monkeypatch, git_repo
    ):
        """A focused non-parametrized check on real repo territory (gate
        3/3b/4's actual review+claim cycle, not just the no-repo fail-open
        path the corpus above exercises for path-scoped commits): a clean,
        reviewed, path-scoped commit resolves identically whether the
        observer module is present or absent.

        Uses TWO SEPARATE repos with DIFFERENT relative filenames (rather
        than two calls against the same repo/path) so the first call's
        real file_claims claim can never contest the second. Different
        REPOS alone is not enough: file_claims' own real-path claims are
        plain relative pathspecs with NO repo dimension in the comparison
        (a documented, pre-existing gap — CLAUDE.md §2's own "claims can
        still false-positive-contest identically-pathed files across two
        UNRELATED repos" note, and `oversight_install.md`'s Agency-wheel
        row cites the identical mechanism) — two repos both committing a
        file literally named `a.py` would STILL contest each other on that
        shared relative path alone. Different filenames sidesteps it
        entirely. Confirmed by execution during fix-round 1's own
        falsifiability pass: the same-filename version of this test
        deadlocked on gate 4's real ~45s CSA_COMMIT_CLAIM_MAX_WAIT_SEC poll
        before denying — a genuine slow-fail this test hit, not a product
        defect (the mutex-token half of that same gap is already the
        established, accepted, documented behavior; this test must not
        accidentally re-discover it as if it were new)."""
        import shutil

        repo_without = git_repo.parent / "repo_without_ico"
        shutil.copytree(git_repo, repo_without)

        (git_repo / "a.py").write_text("1\n")
        (repo_without / "a_without_ico.py").write_text("1\n")
        monkeypatch.setattr(
            css,
            "read_staged_paths",
            lambda w: ["a.py"] if w == str(git_repo) else ["a_without_ico.py"],
        )

        rc_with, out_with = _run_main(
            monkeypatch,
            _payload('git commit -m "feat(x): y" -- a.py', cwd=str(git_repo)),
            env={"CSA_ENFORCE": "1"},
        )
        monkeypatch.setattr(ptb, "ico", None)
        rc_without, out_without = _run_main(
            monkeypatch,
            _payload(
                'git commit -m "feat(x): y" -- a_without_ico.py', cwd=str(repo_without)
            ),
            env={"CSA_ENFORCE": "1"},
        )
        assert rc_with == rc_without
        # The two outputs necessarily differ in their literal pathspec text
        # (a.py vs a_without_ico.py) when either run actually blocks on
        # something naming the path — so this asserts on the DECISION
        # shape (present/absent + permissionDecision), not byte-identical
        # text, unlike the corpus test above (which uses the SAME command
        # both times and can assert byte-identical output).
        assert _is_deny(out_with) == _is_deny(out_without)
        if _is_deny(out_with):
            obj_with = json.loads(out_with)
            obj_without = json.loads(out_without)
            assert (
                obj_with["hookSpecificOutput"]["permissionDecision"]
                == obj_without["hookSpecificOutput"]["permissionDecision"]
            )
