"""Hermetic tests for hooks/posttooluse_bash.py — the claim-release dispatcher.

Covers should_release()'s commit detection and main()'s release-on-commit
behavior: releases the tool_use_id-keyed claim after a `git commit`, leaves
other agents' claims untouched, no-ops for non-commit commands, no-ops when
tool_use_id is absent (the same documented tradeoff as agent_budget's
release_hook), and fails open on CSA_DISABLE_HOOKS / a broken payload.

CORRECTION (2026-09-05, closes the "leak on hook failure" bug — see
file_claims.py's module docstring for the full incident): this docstring
used to claim main() releases the claim "success or failure" of the commit.
That was FALSE in the one case that actually mattered: Claude Code's hook
lifecycle only fires the `PostToolUse` event when the Bash TOOL CALL itself
completes (regardless of the invoked command's own exit code — a normal
`git commit` rejected by a pre-commit hook, git exiting 1, still counts as
the tool call "succeeding"); a Bash tool call that itself errors, times out,
or is interrupted mid-run instead fires the DISTINCT `PostToolUseFailure`
event. `~/.claude/settings.json` used to wire this module's release logic
only to `PostToolUse`, so that second case leaked the claim under its old
tool_use_id — verified via a live repro (parallel same-session sub-agents
share `CLAUDE_PID`, so an earlier pid-based contest-time fix was REJECTED at
review for breaking the per-repo commit mutex/path contest between
concurrent same-session commits; see file_claims.py's module docstring).

THE FIX is entirely in settings.json, not in this module: `PostToolUseFailure`
is now ALSO wired to the same `post_bash_gate.sh` -> posttooluse_bash.py path,
with the same `"Bash"` matcher, verified against the actual running Claude
Code binary (2.1.261) to carry `executePostToolUseFailureHooks` as a real,
tool-name-matched dispatcher (`strings` on the native binary; also documented
in ~/.claude/cache/changelog.md since 2.1.119: "Hooks: PostToolUse and
PostToolUseFailure hook inputs now include duration_ms"). should_release()/
main() themselves are, and always were, EVENT-AGNOSTIC — they never read
`hook_event_name` at all, only the command's own shape and its tool_use_id —
so releasing on failure needed zero code changes here, only the missing
settings.json wiring. TestEventAgnosticRelease below pins that agnosticism
explicitly (the same payload releases identically whether it claims to be a
PostToolUse or a PostToolUseFailure event), and
test_settings_wiring.py::TestPostToolUseFailureWiring pins the wiring itself.
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import _lib  # noqa: F401  (sys.path shim via conftest)
import commit_authors as ca
import file_claims as fc
import posttooluse_bash as ptb
import pytest


def _payload(command, tool_name="Bash", tool_use_id=None, cwd=None, session_id=None, hook_event_name=None):
    ev: dict = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    if tool_use_id is not None:
        ev["tool_use_id"] = tool_use_id
    if cwd is not None:
        ev["cwd"] = cwd
    if session_id is not None:
        ev["session_id"] = session_id
    if hook_event_name is not None:
        ev["hook_event_name"] = hook_event_name
    return ev


def _run_main(monkeypatch, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    return ptb.main()


class TestShouldRelease:
    def test_commit_is_released(self):
        assert ptb.should_release(_payload('git commit -m "x"')) is True

    def test_dry_run_commit_is_not_released(self):
        assert ptb.should_release(_payload('git commit --dry-run -m "x"')) is False

    def test_non_commit_git_op_is_not_released(self):
        assert ptb.should_release(_payload("git status")) is False

    def test_non_bash_tool_is_not_released(self):
        assert ptb.should_release(_payload('git commit -m "x"', tool_name="Read")) is False


class TestMainReleasesClaim:
    def test_end_to_end_release_via_stdin(self, sandbox, monkeypatch):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu_123", ["a.py"], lock_timeout=1.0)
        fc.try_claim_paths(d, 300, "toolu_999", ["b.py"], lock_timeout=1.0)

        rc = _run_main(monkeypatch, _payload('git commit -m "x"', tool_use_id="toolu_123"))
        assert rc == 0
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300)}
        assert live == {"toolu_999"}  # only the matching claim released

    def test_non_commit_command_does_not_release(self, sandbox, monkeypatch):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu_123", ["a.py"], lock_timeout=1.0)
        _run_main(monkeypatch, _payload("git status", tool_use_id="toolu_123"))
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300)}
        assert live == {"toolu_123"}

    def test_missing_tool_use_id_is_a_noop(self, sandbox, monkeypatch):
        d = str(sandbox.file_claims_dir)
        fc._write_claim(d, "auto-abc123", ["a.py"], claimed_at=1000.0)
        rc = _run_main(monkeypatch, _payload('git commit -m "x"'))  # no tool_use_id
        assert rc == 0
        # The minted-id claim survives (no correlated release) — TTL-reaps instead.
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300, now=1001.0)}
        assert live == {"auto-abc123"}

    def test_release_of_untracked_id_is_harmless(self, sandbox, monkeypatch):
        rc = _run_main(monkeypatch, _payload('git commit -m "x"', tool_use_id="never-claimed"))
        assert rc == 0

    def test_disabled_short_circuits(self, sandbox, monkeypatch):
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu_123", ["a.py"], lock_timeout=1.0)
        monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
        rc = _run_main(monkeypatch, _payload('git commit -m "x"', tool_use_id="toolu_123"))
        assert rc == 0
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300)}
        assert live == {"toolu_123"}  # untouched — hooks were disabled

    def test_malformed_stdin_degrades_open(self, sandbox, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        rc = ptb.main()
        assert rc == 0

    def test_stdin_read_raising_degrades_open(self, sandbox, monkeypatch):
        class Boom:
            def read(self):
                raise OSError("no stdin")

        monkeypatch.setattr("sys.stdin", Boom())
        rc = ptb.main()
        assert rc == 0


# ===========================================================================
# REGRESSION — "leak on hook failure" (observed repeatedly 2026-09-04/05):
# should_release()/main() never read hook_event_name at all -- they always
# decide purely from the command's own shape and tool_use_id. This class
# pins that agnosticism explicitly: the identical payload releases
# identically whether it carries "PostToolUse" or "PostToolUseFailure" as
# its hook_event_name (or none at all, matching every pre-existing test
# above). The ACTUAL fix for the leak is settings.json wiring
# PostToolUseFailure to this same module (see test_settings_wiring.py) --
# this class proves that, once reached, the module-level logic already does
# the right thing with zero further code changes, for either event shape.
# ===========================================================================


class TestEventAgnosticRelease:
    @pytest.mark.parametrize("event_name", [None, "PostToolUse", "PostToolUseFailure", "SomeFutureEventName"])
    def test_should_release_ignores_hook_event_name(self, event_name):
        payload = _payload('git commit -m "x"', tool_use_id="toolu-1", hook_event_name=event_name)
        assert ptb.should_release(payload) is True

    @pytest.mark.parametrize("event_name", [None, "PostToolUse", "PostToolUseFailure"])
    def test_main_releases_the_claim_regardless_of_hook_event_name(self, sandbox, monkeypatch, event_name):
        """The exact scenario the leak fix depends on: a commit whose Bash
        tool call itself failed/timed out/was interrupted fires
        PostToolUseFailure rather than PostToolUse -- this proves main()
        releases the claim identically either way, so wiring
        PostToolUseFailure in settings.json (verified separately in
        test_settings_wiring.py) is sufficient on its own; no branch here
        needed to special-case the failure event.
        """
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu-1", ["a.py", "b.py"], lock_timeout=1.0, now=1000.0)

        payload = _payload(
            'git commit -m "x"', tool_use_id="toolu-1", hook_event_name=event_name
        )
        rc = _run_main(monkeypatch, payload)
        assert rc == 0

        live = fc.read_live_claims(d, 300, now=1001.0)
        assert live == []  # released regardless of which event delivered this call

    def test_retry_after_release_is_uncontested_the_real_end_to_end_fix(self, sandbox, monkeypatch):
        """The complete, real-world sequence this whole fix exists for:
        (1) gate 4 claims for toolu-1, (2) the commit's Bash tool call fails
        in a way that fires PostToolUseFailure, (3) that event (now wired to
        this module in settings.json) releases toolu-1's claim, (4) the SAME
        session retries under a FRESH tool_use_id (toolu-2) and is NOT
        contested -- no manual `file_claims.py release` needed.
        """
        d = str(sandbox.file_claims_dir)

        # (1) gate 4's PreToolUse claim for the first attempt.
        claimed_1, contest_1 = fc.try_claim_paths(d, 300, "toolu-1", ["a.py"], lock_timeout=1.0, now=1000.0)
        assert claimed_1 is True and contest_1 is None

        # (2)+(3): the Bash tool call fails -> PostToolUseFailure -> this
        # module releases toolu-1's claim (simulated here exactly as the
        # real dispatcher would deliver it once settings.json is wired).
        rc = _run_main(
            monkeypatch,
            _payload('git commit -m "x"', tool_use_id="toolu-1", hook_event_name="PostToolUseFailure"),
        )
        assert rc == 0

        # (4) the same session retries under a fresh tool_use_id.
        claimed_2, contest_2 = fc.try_claim_paths(d, 300, "toolu-2", ["a.py"], lock_timeout=1.0, now=1001.0)
        assert claimed_2 is True
        assert contest_2 is None


# ===========================================================================
# _record_commit_author — the combined %H%x00%ct call (item 1 of the gate
# optimization pass). Real, throwaway, offline git repos only (mirrors
# test_record_review.py's pattern) -- no network, never the shared tree.
# ===========================================================================


def _git_env():
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "T"
    env["GIT_AUTHOR_EMAIL"] = "t@example.invalid"
    env["GIT_COMMITTER_NAME"] = "T"
    env["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
    return env


def _run_git(repo, *args, extra_env=None):
    env = _git_env()
    if extra_env:
        env.update(extra_env)
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=15,
        env=env,
    )


def _git_out(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=_git_env(),
    )
    return proc.stdout.strip()


def _have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


_requires_git = pytest.mark.skipif(not _have_git(), reason="git not available")


def _committed_repo(tmp_path, name="repo", committer_date=None):
    """A throwaway repo with one real commit; returns its Path.

    `committer_date` (e.g. "700 seconds ago", or an ISO string) sets BOTH
    GIT_COMMITTER_DATE and GIT_AUTHOR_DATE on the commit, letting a test
    fabricate a stale HEAD without waiting real wall-clock time.
    """
    repo = tmp_path / name
    repo.mkdir()
    _run_git(repo, "init", "-q")
    (repo / "f.txt").write_text("x")
    _run_git(repo, "add", "f.txt")
    extra = {}
    if committer_date is not None:
        extra["GIT_COMMITTER_DATE"] = committer_date
        extra["GIT_AUTHOR_DATE"] = committer_date
    _run_git(repo, "commit", "-q", "-m", "initial", extra_env=extra)
    return repo


@_requires_git
class TestRecordCommitAuthor:
    def test_issues_exactly_two_subprocess_calls(self, sandbox, monkeypatch, tmp_path):
        """Was 3 (show-toplevel, rev-parse HEAD, log -1 --format=%ct); now 2
        (show-toplevel, combined log -1 --format=%H%x00%ct)."""
        repo = _committed_repo(tmp_path)
        real_run = subprocess.run
        calls = []

        def counting_run(*a, **k):
            calls.append((a, k))
            return real_run(*a, **k)

        monkeypatch.setattr(ptb.subprocess, "run", counting_run)
        ev = _payload("git commit -m x", cwd=str(repo), session_id="sess-count")
        ptb._record_commit_author(ev)
        assert len(calls) == 2
        # Identity, not just arity -- also pins the timeout kwarg and would
        # catch e.g. a %h-for-%H regression at the call-construction site
        # (test_combined_call_parses_same_pair_as_old_two_call_form catches
        # it too, downstream, via the author_of lookup -- this catches it
        # upstream, at the argv itself).
        # a[0] is the full argv list ["git", "-C", cwd, *args] (see _git()) --
        # skip the first 3 elements to compare just *args.
        argvs = [a[0][3:] for a, _ in calls]
        assert argvs == [
            ["rev-parse", "--show-toplevel"],
            ["log", "-1", "--format=%H%x00%ct"],
        ]
        assert all(k.get("timeout") == 15 for _, k in calls)

    def test_combined_call_parses_same_pair_as_old_two_call_form(self, sandbox, tmp_path):
        """The (sha, epoch_seconds) recovered from the single combined call
        must match exactly what the OLD `git rev-parse HEAD` +
        `git log -1 --format=%ct` two-call form would have produced."""
        repo = _committed_repo(tmp_path)
        expected_sha = _git_out(repo, "rev-parse", "HEAD")
        expected_ts = _git_out(repo, "log", "-1", "--format=%ct")
        assert len(expected_sha) == 40
        assert expected_ts.isdigit()

        ev = _payload("git commit -m x", cwd=str(repo), session_id="sess-pair")
        ptb._record_commit_author(ev)

        repo_root = _git_out(repo, "rev-parse", "--show-toplevel")
        recorded_session = ca.author_of(_lib.COMMIT_AUTHORS, repo_root, expected_sha)
        # record() only succeeds (and is only checked here) against the
        # EXACT sha the combined call resolved -- if the NUL-split recovered
        # a different sha than the old two-call form would have, this
        # lookup finds nothing and the assertion below fails.
        assert recorded_session == "sess-pair"

    def test_stale_head_still_skips_recording(self, sandbox, tmp_path, monkeypatch):
        """STALE_HEAD_SEC still fires off the epoch parsed from the combined
        call -- a HEAD older than the bound must NOT self-attribute."""
        repo = _committed_repo(tmp_path, committer_date="1000000000 +0000")  # ancient
        sha = _git_out(repo, "rev-parse", "HEAD")
        repo_root = _git_out(repo, "rev-parse", "--show-toplevel")

        ev = _payload("git commit -m x", cwd=str(repo), session_id="sess-stale")
        ptb._record_commit_author(ev)

        assert ca.author_of(_lib.COMMIT_AUTHORS, repo_root, sha) is None

    def test_fresh_head_within_bound_is_recorded(self, sandbox, tmp_path):
        """Complement of the staleness test: a HEAD well within
        STALE_HEAD_SEC (a real, just-made commit) IS recorded."""
        repo = _committed_repo(tmp_path)
        sha = _git_out(repo, "rev-parse", "HEAD")
        repo_root = _git_out(repo, "rev-parse", "--show-toplevel")

        ev = _payload("git commit -m x", cwd=str(repo), session_id="sess-fresh")
        ptb._record_commit_author(ev)

        assert ca.author_of(_lib.COMMIT_AUTHORS, repo_root, sha) == "sess-fresh"

    def test_release_claim_runs_when_combined_call_raises(self, sandbox, monkeypatch, tmp_path):
        """The combined call itself raising/timing out must not prevent
        main() from still releasing the file_claims claim. NOTE: this is
        guaranteed by _git()'s own `except Exception: return None` (a
        TimeoutExpired inside subprocess.run is swallowed there, so
        _record_commit_author sees a falsy `combined` and takes its normal
        early-return path) -- _record_commit_author's own swallow-all is
        never entered on this path. See
        test_release_claim_runs_when_record_itself_raises for the sibling
        case that actually exercises that outer handler."""
        repo = _committed_repo(tmp_path)
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu_flaky", ["a.py"], lock_timeout=1.0)

        real_run = subprocess.run
        state = {"n": 0}

        def flaky_run(*a, **k):
            state["n"] += 1
            if state["n"] == 2:  # the (now-combined) `git log` call
                raise subprocess.TimeoutExpired(cmd=a[0] if a else "git", timeout=15)
            return real_run(*a, **k)

        monkeypatch.setattr(ptb.subprocess, "run", flaky_run)
        payload = _payload(
            "git commit -m x", tool_use_id="toolu_flaky", cwd=str(repo), session_id="sess-flaky"
        )
        rc = _run_main(monkeypatch, payload)

        assert rc == 0
        assert state["n"] == 2  # both calls were attempted; the 2nd raised
        # No authorship recorded (the raising call never resolved a sha)...
        sha = _git_out(repo, "rev-parse", "HEAD")
        repo_root = _git_out(repo, "rev-parse", "--show-toplevel")
        assert ca.author_of(_lib.COMMIT_AUTHORS, repo_root, sha) is None
        # ...but the claim was still released despite the exception.
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300)}
        assert live == set()

    def test_release_claim_runs_when_record_itself_raises(self, sandbox, monkeypatch, tmp_path):
        """A different failure mode of the same guarantee: an exception
        raised deeper inside _record_commit_author (commit_authors.record
        itself) must also never block the claim release."""
        repo = _committed_repo(tmp_path)
        d = str(sandbox.file_claims_dir)
        fc.try_claim_paths(d, 300, "toolu_boom", ["a.py"], lock_timeout=1.0)

        def boom(*a, **k):
            raise RuntimeError("ledger unwritable")

        monkeypatch.setattr(ptb.commit_authors, "record", boom)
        payload = _payload(
            "git commit -m x", tool_use_id="toolu_boom", cwd=str(repo), session_id="sess-boom"
        )
        rc = _run_main(monkeypatch, payload)

        assert rc == 0
        live = {r["agent_id"] for r in fc.read_live_claims(d, 300)}
        assert live == set()


@_requires_git
class TestRecordCommitAuthorCdPrefixCrossRepo:
    """#5061 blast-radius item A-blast-radius / B4: `_record_commit_author`
    calls `_lib.effective_git_cwd(_lib.bash_command(ev), _lib.cwd(ev))`
    directly (see that function's own call site above) -- a cd-prefixed
    commit issued from one repo's session cwd that actually commits INTO a
    DIFFERENT repo must record authorship against the TARGET repo's ledger,
    not the session's own cwd. Today (pre-#5061) this hit the same bug
    class as the mutex/digest: authorship recorded against the wrong repo
    entirely, or against no repo at all if the session cwd wasn't even a
    git repository."""

    def test_cd_prefixed_commit_records_authorship_in_the_target_repo(
        self, sandbox, tmp_path
    ):
        session_cwd = tmp_path / "session-repo"
        session_cwd.mkdir()
        _run_git(session_cwd, "init", "-q")

        target_repo = _committed_repo(tmp_path, name="target-repo")
        sha = _git_out(target_repo, "rev-parse", "HEAD")
        target_root = _git_out(target_repo, "rev-parse", "--show-toplevel")

        cmd = f"cd {target_repo} && git commit -m x"
        ev = _payload(cmd, cwd=str(session_cwd), session_id="sess-cd-cross-repo")
        ptb._record_commit_author(ev)

        # Recorded against the TARGET repo's ledger, keyed to the TARGET's
        # own HEAD sha -- never against the session's own (unrelated) repo.
        assert ca.author_of(_lib.COMMIT_AUTHORS, target_root, sha) == "sess-cd-cross-repo"

    def test_cd_prefixed_commit_does_not_record_against_the_session_repo(
        self, sandbox, tmp_path
    ):
        """Paired negative: the session's OWN repo (a plausible pre-fix
        wrong target) must get no authorship entry at all for this commit."""
        session_repo = _committed_repo(tmp_path, name="session-repo-2")
        session_root = _git_out(session_repo, "rev-parse", "--show-toplevel")
        session_head = _git_out(session_repo, "rev-parse", "HEAD")

        target_repo = _committed_repo(tmp_path, name="target-repo-2")

        cmd = f"cd {target_repo} && git commit -m x"
        ev = _payload(cmd, cwd=str(session_repo), session_id="sess-cd-cross-repo-2")
        ptb._record_commit_author(ev)

        assert ca.author_of(_lib.COMMIT_AUTHORS, session_root, session_head) is None


class TestScriptEntryPoint:
    def test_module_runs_as_script(self, tmp_path, monkeypatch):
        import os
        import subprocess
        import sys

        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        env = dict(os.environ)
        env["HOME"] = str(home)
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.dirname(__file__)), "posttooluse_bash.py")],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}),
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0
        assert proc.stdout == ""
