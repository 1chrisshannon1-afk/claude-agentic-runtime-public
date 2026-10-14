"""Hermetic tests for `runtime_mirror_sync.py --status` — the READ-ONLY
state reporter (OK / BLOCKED / DRIFTED / INERT).

Spec source: the module's own DESIGN point 6, the `status()` docstring's
four-state precedence contract, and the `STATUS_EXIT_CODES` comment — NOT a
snapshot of current output. The behaviour under test exists because point 5's
failure surfaces (`BLOCKED.md`, `last_error`, `sync.log`) are FILES that
nothing read: the live log carried 9 BLOCKED events against 2 successful
pushes, one block sitting unnoticed for over two hours, and it took a human
asking to discover the mirror was stale.

Two properties are load-bearing and therefore asserted rather than assumed:

  1. `--status` WRITES NOTHING — not a state file, not a lock, and not even
     a `sync.log` line. The trap is real and specific: `load_config()` logs
     `config: REJECTED (...)` on exactly the INERT path this mode has to
     report, so a status built on `load_config` would append to the operator's
     log on every poll. `TestReadOnly` snapshots the whole mirror directory
     (names + sizes + mtimes + content hashes) around each of the four states
     and proves the trap by showing `load_config()` DOES create the log that
     `status()` does not.
  2. `--status` MAKES NO NETWORK CALL. Every subprocess this mode spawns is
     recorded and asserted to be a read-only local git verb, and no spawn
     may carry `--sync` / `start_new_session=True` — the signature of the
     detached sync `maybe_trigger` launches. (`Popen` itself cannot be
     forbidden outright: `subprocess.run` drives its own Popen internally.)

Every git-touching test uses real, local, offline scratch repos under
`tmp_path`. The autouse `_isolated_mirror_paths` fixture repoints ALL SEVEN
of the module's import-time path constants -- and the `load_config()` default
argument, which is bound to the REAL config path at import and which the
constant patch cannot reach -- under a throwaway dir before each test, so no
test in this file can reach the operator's real `~/.claude/.mirror/`
(`TestConfigStatus.test_load_config_default_path_follows_the_sandbox` asserts it).

The BLOCKED-state tests deliberately do NOT hand-write a `BLOCKED.md`: one
end-to-end test drives a real `sync()` into a real gate hit and parses the
file the module itself produced, so a future change to the writer's format
breaks this suite instead of silently making `--status` report
"(unrecorded)" forever — which is the same "nobody reads it" failure class
this whole mode exists to end.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess

import pytest
import runtime_mirror_sync as rms

# ===========================================================================
# git plumbing (real, local, offline repos only)
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


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-c", "safe.bareRepository=all", "-C", str(cwd), *args],
        check=check,
        capture_output=True,
        text=True,
        timeout=20,
        env=_git_env(),
    )


def _have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


_requires_git = pytest.mark.skipif(not _have_git(), reason="git not available")


def _patch_mirror_paths(monkeypatch, mirror_dir):
    monkeypatch.setattr(rms, "MIRROR_DIR", str(mirror_dir))
    monkeypatch.setattr(rms, "CONFIG_PATH", os.path.join(str(mirror_dir), "config.json"))
    monkeypatch.setattr(rms, "STATE_PATH", os.path.join(str(mirror_dir), "last_synced_head"))
    monkeypatch.setattr(rms, "LOCK_PATH", os.path.join(str(mirror_dir), "sync.lock"))
    monkeypatch.setattr(rms, "LOG_PATH", os.path.join(str(mirror_dir), "sync.log"))
    monkeypatch.setattr(rms, "BLOCKED_PATH", os.path.join(str(mirror_dir), "BLOCKED.md"))
    monkeypatch.setattr(rms, "LAST_ERROR_PATH", os.path.join(str(mirror_dir), "last_error"))
    # `def load_config(path=CONFIG_PATH)` bound the REAL path at import; the
    # constant patch above cannot reach it, so repoint the default itself.
    monkeypatch.setattr(
        rms.load_config, "__defaults__", (os.path.join(str(mirror_dir), "config.json"),)
    )


@pytest.fixture(autouse=True)
def _isolated_mirror_paths(tmp_path, monkeypatch):
    """Whole-file hermeticity: every test gets all seven module path
    constants repointed under a throwaway dir BEFORE its body runs, so a test
    that forgets one cannot leak a write into the real sync.log. Tests need-
    ing a specific mirror dir re-call `_patch_mirror_paths`, which composes."""
    _patch_mirror_paths(monkeypatch, tmp_path / ".default-mirror")


# ===========================================================================
# fixtures — a scratch runtime repo + an isolated mirror dir
# ===========================================================================


def _valid_cfg(mirror_dir):
    return {
        "remote_url": "https://github.com/acme/mirror.git",
        "clone_dir": os.path.join(str(mirror_dir), "clone"),
        "branch": "main",
        "include": ["agents"],
    }


@pytest.fixture
def env(tmp_path, sandbox, monkeypatch):
    """A real scratch runtime repo at the sandboxed `_lib.CLAUDE_DIR`, plus an
    isolated `.mirror/` dir OUTSIDE it (so the read-only snapshot in
    `TestReadOnly` never has to reason about git internals)."""
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", "refs/heads/main")
    (src / "agents").mkdir(exist_ok=True)
    (src / "agents" / "a.md").write_text("hello\n")
    _git(src, "add", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = tmp_path / ".mirror"
    mirror_dir.mkdir()
    _patch_mirror_paths(monkeypatch, mirror_dir)

    class Env:
        def __init__(self):
            self.src = src
            self.mirror_dir = mirror_dir

        def head(self):
            return _git(self.src, "rev-parse", "HEAD").stdout.strip()

        def commit(self, rel="agents/a.md", content=None):
            full = self.src / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content or f"rev {rel}\n")
            _git(self.src, "add", rel)
            _git(self.src, "commit", "-q", "-m", f"update {rel}")
            return self.head()

        def write_config(self, cfg=None):
            body = _valid_cfg(self.mirror_dir) if cfg is None else cfg
            (self.mirror_dir / "config.json").write_text(json.dumps(body))

        def write_state(self, sha):
            (self.mirror_dir / "last_synced_head").write_text(sha + "\n")

        def write_blocked(self, body):
            (self.mirror_dir / "BLOCKED.md").write_text(body)

        def ok(self):
            """Put the mirror in the healthy state: valid config, state at
            HEAD, nothing blocked."""
            self.write_config()
            self.write_state(self.head())

    return Env()


def _run_status(capsys):
    """Drive the real CLI entry point, returning (exit_code, stdout)."""
    rc = rms.main(["--status"])
    return rc, capsys.readouterr().out


def _token(out):
    return out.splitlines()[0].split()[0]


# ===========================================================================
# exit-code contract
# ===========================================================================


class TestStatusExitCodes:
    """Per the STATUS_EXIT_CODES comment: a DISTINCT code per state so a
    watcher branches on WHICH failure without parsing prose."""

    def test_ok_is_zero_and_every_unhealthy_state_is_nonzero(self):
        assert rms.STATUS_EXIT_CODES["OK"] == 0
        for state in ("BLOCKED", "DRIFTED", "INERT"):
            assert rms.STATUS_EXIT_CODES[state] != 0

    def test_codes_are_mutually_distinct(self):
        codes = list(rms.STATUS_EXIT_CODES.values())
        assert len(codes) == len(set(codes))

    def test_no_state_reuses_the_generic_or_usage_code(self):
        """1 is `--check`'s flat "unhealthy" and 2 is main()'s usage no-op;
        reusing either would re-create the ambiguity this mode removes."""
        assert rms.main([]) == 2  # usage code, pinned here on purpose
        for state, code in rms.STATUS_EXIT_CODES.items():
            if state != "OK":
                assert code not in (1, 2), f"{state} collides with a reserved code"

    def test_all_four_states_are_covered(self):
        assert set(rms.STATUS_EXIT_CODES) == {"OK", "BLOCKED", "DRIFTED", "INERT"}


# ===========================================================================
# the four states
# ===========================================================================


@_requires_git
class TestOkState:
    def test_ok_when_config_valid_nothing_blocked_and_state_matches_head(
        self, env, capsys
    ):
        env.ok()

        rc, out = _run_status(capsys)

        assert _token(out) == "OK"
        assert rc == rms.STATUS_EXIT_CODES["OK"] == 0
        assert env.head() in out
        assert "blocked:       no" in out
        assert "last error:    none" in out

    def test_ok_reports_the_configured_branch_and_remote(self, env, capsys):
        env.ok()

        _, out = _run_status(capsys)

        assert "main" in out
        assert "https://github.com/acme/mirror.git" in out


@_requires_git
class TestBlockedState:
    def test_blocked_when_blocked_md_exists(self, env, capsys):
        env.ok()
        env.write_blocked(
            "# Mirror sync BLOCKED — the publish gate found problems\n"
            "\n"
            "Source HEAD: 1234567890abcdef1234567890abcdef12345678\n"
            "\n"
            "- `agents/a.md` matched `secretvendor`\n"
        )

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]

    def test_blocked_prints_the_recorded_source_head_and_hits_verbatim(
        self, env, capsys
    ):
        """A watcher's whole job is relaying WHICH path matched WHICH pattern;
        BLOCKED.md already names both, so both must survive to stdout."""
        env.ok()
        env.write_blocked(
            "# Mirror sync BLOCKED — the publish gate found problems\n"
            "\n"
            "Source HEAD: 1234567890abcdef1234567890abcdef12345678\n"
            "\n"
            "- `agents/a.md` matched `secretvendor`\n"
            "- `knowledge/x.md` matched `co-[0-9a-f]{20}`\n"
        )

        _, out = _run_status(capsys)

        assert "1234567890abcdef1234567890abcdef12345678" in out
        assert "- `agents/a.md` matched `secretvendor`" in out
        assert "- `knowledge/x.md` matched `co-[0-9a-f]{20}`" in out

    def test_blocked_beats_ok_even_when_state_is_current(self, env, capsys):
        """The state file says current, but a withheld push means the remote
        does NOT have that content — reporting OK here is the exact lie this
        mode exists to prevent."""
        env.ok()
        assert _token(_run_status(capsys)[1]) == "OK"
        env.write_blocked("Source HEAD: deadbeef\n\n- `a` matched `b`\n")

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]

    def test_blocked_beats_drifted(self, env, capsys):
        env.write_config()
        env.write_state(env.head())
        env.commit()  # state now behind HEAD
        env.write_blocked("Source HEAD: deadbeef\n\n- `a` matched `b`\n")

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]

    def test_unrecognised_blocked_body_is_printed_whole_not_silently_empty(
        self, env, capsys
    ):
        """Reporting a block with no detail would be a report nobody can act
        on — the failure class this mode ends. Fall back to the raw body."""
        env.ok()
        env.write_blocked("something a human typed by hand\n")

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]
        assert "something a human typed by hand" in out
        assert "(unrecorded)" in out

    def test_empty_blocked_file_is_still_blocked(self, env, capsys):
        env.ok()
        env.write_blocked("")

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]


@_requires_git
class TestDriftedState:
    def test_drifted_when_state_is_behind_head(self, env, capsys):
        env.write_config()
        synced = env.head()
        env.write_state(synced)
        env.commit("agents/b.md")
        env.commit("agents/c.md")
        current = env.commit("agents/d.md")

        rc, out = _run_status(capsys)

        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]
        assert synced in out and current in out  # BOTH shas, per the spec
        assert "3" in out.split("commits behind")[1].splitlines()[0]

    def test_drifted_when_no_sync_was_ever_recorded(self, env, capsys):
        env.write_config()  # no last_synced_head at all

        rc, out = _run_status(capsys)

        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]
        assert "(never)" in out

    def test_drifted_when_state_sha_is_unknown_to_the_repo(self, env, capsys):
        """A sync that died, or a rewritten history: the distance is
        uncomputable, but the two shas still have to be reported."""
        env.write_config()
        env.write_state("0" * 40)

        rc, out = _run_status(capsys)

        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]
        assert "0" * 40 in out
        assert env.head() in out

    def test_drifted_when_runtime_head_is_unresolvable(
        self, env, tmp_path, monkeypatch, capsys
    ):
        """Not a git repo (or git is broken): the mirror cannot be confirmed
        current, so it must not read as OK — and must not crash the caller."""
        import _lib

        not_a_repo = tmp_path / "not-a-repo"
        not_a_repo.mkdir()
        monkeypatch.setattr(_lib, "CLAUDE_DIR", str(not_a_repo))
        env.write_config()

        rc, out = _run_status(capsys)

        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]
        assert "(unresolvable)" in out

    def test_a_raising_git_never_crashes_the_reporter(self, env, monkeypatch, capsys):
        """A watcher must always get an answer; a missing git binary is a
        state to report, not a traceback to propagate."""
        env.ok()

        def boom(*a, **k):
            raise FileNotFoundError("git")

        monkeypatch.setattr(rms, "_run", boom)

        rc, out = _run_status(capsys)

        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]


# ===========================================================================
# INERT — the most dangerous state: an inert subsystem never even logs
# ===========================================================================

# One case per DISTINCT rejection reason validate_config() can produce, plus
# the two ways the file itself can fail to yield a config at all.
_INERT_CASES = [
    ("missing_file", None, "no config at"),
    ("unparseable_json", "{not json", "unreadable"),
    ("not_an_object", "[1, 2, 3]", "not an object"),
    ("missing_remote_url", {"_drop": "remote_url"}, "missing required key: remote_url"),
    ("missing_clone_dir", {"_drop": "clone_dir"}, "missing required key: clone_dir"),
    ("missing_branch", {"_drop": "branch"}, "missing required key: branch"),
    ("missing_include", {"_drop": "include"}, "missing required key: include"),
    ("bad_remote_url", {"remote_url": "https://evil.example/x.git"}, "well-formed GitHub"),
    ("clone_dir_escapes", {"clone_dir": "/tmp/elsewhere"}, "must resolve under"),
    ("bad_branch", {"branch": "main;rm -rf /"}, "branch contains disallowed characters"),
    ("include_not_a_list", {"include": "agents"}, "include must be a non-empty list"),
    ("unsafe_include", {"include": ["../escape"]}, "unsafe include entry"),
    ("unsafe_managed", {"mirror_managed": ["/etc/passwd"]}, "unsafe mirror_managed entry"),
]


def _write_inert_config(env, payload):
    """Materialise one _INERT_CASES payload onto disk."""
    if payload is None:
        return  # no config file at all
    if isinstance(payload, str):
        (env.mirror_dir / "config.json").write_text(payload)
        return
    cfg = _valid_cfg(env.mirror_dir)
    drop = payload.get("_drop")
    if drop:
        cfg.pop(drop)
    cfg.update({k: v for k, v in payload.items() if k != "_drop"})
    env.write_config(cfg)


@_requires_git
class TestInertState:
    @pytest.mark.parametrize(
        "name,payload,expected",
        _INERT_CASES,
        ids=[c[0] for c in _INERT_CASES],
    )
    def test_every_rejection_reason_reports_inert_with_its_reason(
        self, env, capsys, name, payload, expected
    ):
        env.write_state(env.head())  # otherwise-healthy: only the config is bad
        _write_inert_config(env, payload)

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]
        assert expected in out, out

    def test_empty_include_list_is_inert_and_names_include(self, env, capsys):
        """An empty manifest is rejected; the exact wording is validate_config's
        business, but the reason must name the offending key."""
        env.write_state(env.head())
        cfg = _valid_cfg(env.mirror_dir)
        cfg["include"] = []
        env.write_config(cfg)

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]
        assert "include" in out

    def test_inert_beats_blocked(self, env, capsys):
        """An inert subsystem never ran, so a BLOCKED.md is a leftover and its
        remediation (extend the replacement map) is the wrong instruction —
        the config is the root cause and must be what gets reported."""
        env.write_state(env.head())
        (env.mirror_dir / "config.json").write_text("{not json")
        env.write_blocked("Source HEAD: deadbeef\n\n- `a` matched `b`\n")

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]

    def test_inert_beats_drifted(self, env, capsys):
        env.commit("agents/b.md")  # state absent => would otherwise be DRIFTED
        (env.mirror_dir / "config.json").write_text("[]")

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]


# ===========================================================================
# THE load-bearing property: --status writes nothing, and calls no network
# ===========================================================================


def _snapshot(root):
    """Every file under `root`: rel path -> (size, mtime_ns, sha256)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            st = os.lstat(full)
            digest = ""
            if os.path.isfile(full):
                with open(full, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
            out[rel] = (st.st_size, st.st_mtime_ns, digest)
    return out


def _make_state(env, state):
    """Put the fixture into one of the four states."""
    if state == "OK":
        env.ok()
    elif state == "BLOCKED":
        env.ok()
        env.write_blocked("Source HEAD: deadbeef\n\n- `a` matched `b`\n")
    elif state == "DRIFTED":
        env.write_config()
        env.write_state(env.head())
        env.commit("agents/b.md")
    elif state == "INERT":
        (env.mirror_dir / "config.json").write_text("{not json")
    else:  # pragma: no cover - guards a typo in a parametrize id
        raise AssertionError(f"unknown state {state!r}")


@_requires_git
class TestReadOnly:
    """`--status` is meant to be run by any watcher, on any cadence, possibly
    while a real sync is running. That is only safe if it mutates nothing."""

    @pytest.mark.parametrize("state", ["OK", "BLOCKED", "DRIFTED", "INERT"])
    def test_status_writes_nothing_in_any_state(self, env, capsys, state):
        _make_state(env, state)
        before = _snapshot(env.mirror_dir)

        rc, out = _run_status(capsys)

        after = _snapshot(env.mirror_dir)
        assert _token(out) == state
        assert rc == rms.STATUS_EXIT_CODES[state]
        assert set(after) == set(before), "a file appeared or vanished"
        assert after == before, "a file's content or mtime changed"

    @pytest.mark.parametrize(
        "config_text,logged",
        [
            ("{not json", "unreadable"),
            (json.dumps({"remote_url": "https://github.com/acme/mirror.git"}), "REJECTED"),
        ],
        ids=["unparseable", "rejected"],
    )
    def test_status_never_creates_the_sync_log_on_the_inert_path(
        self, env, capsys, config_text, logged
    ):
        """The specific trap: `load_config()` LOGS on exactly the two ways a
        config makes the subsystem inert -- `config: unreadable (...)` for a
        file that does not parse, `config: REJECTED (...)` for one that parses
        but fails validation -- so a status built on it would append to the
        operator's real sync.log on every poll. Proven here by showing
        load_config does exactly that, on the SAME config, where status() did
        not."""
        (env.mirror_dir / "config.json").write_text(config_text)
        assert not os.path.exists(rms.LOG_PATH)

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]
        assert not os.path.exists(rms.LOG_PATH), "--status appended to sync.log"

        # Falsifiability: the write this test forbids is genuinely reachable.
        # The path is passed EXPLICITLY: `load_config`'s default argument is
        # bound to the import-time CONFIG_PATH (the real
        # ~/.claude/.mirror/config.json, or no file at all in a fresh HOME),
        # so a bare `load_config()` never reads this test's sandboxed config
        # and the self-check passed or failed on the machine, not the code.
        assert rms.load_config(rms.CONFIG_PATH) is None
        assert os.path.exists(rms.LOG_PATH)
        assert logged in open(rms.LOG_PATH, encoding="utf-8").read()

    def test_status_never_writes_state_lock_or_last_error(self, env, capsys):
        _make_state(env, "DRIFTED")

        rc, out = _run_status(capsys)

        # Pin that a REAL report was produced first: "wrote nothing" is
        # trivially true of a mode that does nothing at all.
        assert _token(out) == "DRIFTED"
        assert rc == rms.STATUS_EXIT_CODES["DRIFTED"]
        assert not os.path.exists(rms.LOCK_PATH)
        assert not os.path.exists(rms.LAST_ERROR_PATH)
        assert not os.path.exists(rms.LOG_PATH)

    def test_status_does_not_create_the_mirror_dir_when_it_is_absent(
        self, env, tmp_path, monkeypatch, capsys
    ):
        """A watcher polling an adopter's machine that never configured the
        mirror must not conjure `.mirror/` into existence."""
        absent = tmp_path / "no-such-mirror"
        _patch_mirror_paths(monkeypatch, absent)

        rc, out = _run_status(capsys)

        assert _token(out) == "INERT"
        assert rc == rms.STATUS_EXIT_CODES["INERT"]
        assert not absent.exists()

    @pytest.mark.parametrize("state", ["OK", "BLOCKED", "DRIFTED", "INERT"])
    def test_status_makes_no_network_and_no_mutating_subprocess_call(
        self, env, monkeypatch, capsys, state
    ):
        """Only read-only local git verbs may be spawned, and the detached
        `--sync` spawn must never be reached."""
        _make_state(env, state)

        seen_run = []
        seen_popen = []
        real_run = subprocess.run
        real_popen = subprocess.Popen

        def recording_run(args, **kwargs):
            seen_run.append(list(args))
            return real_run(args, **kwargs)

        def recording_popen(args, **kwargs):
            seen_popen.append((list(args), kwargs))
            return real_popen(args, **kwargs)

        monkeypatch.setattr(rms.subprocess, "run", recording_run)
        monkeypatch.setattr(rms.subprocess, "Popen", recording_popen)

        rc, out = _run_status(capsys)

        # A mode that ran nothing would satisfy every assertion below
        # vacuously, so pin the real report and at least one real git read.
        assert _token(out) == state
        assert rc == rms.STATUS_EXIT_CODES[state]
        assert seen_run, "status consulted git not at all"

        forbidden = {
            "push", "fetch", "clone", "pull", "ls-remote", "remote",
            "commit", "add", "checkout", "archive", "gc", "prune",
        }
        allowed = {"rev-parse", "rev-list"}
        for argv in seen_run:
            assert argv[0] == "git", f"non-git subprocess: {argv}"
            verbs = set(argv) & (forbidden | allowed)
            assert not (verbs & forbidden), f"mutating/network git call: {argv}"
            assert verbs & allowed, f"unrecognised git call: {argv}"

        # `subprocess.run` drives its own Popen internally, so "Popen was
        # called at all" is not the signal -- maybe_trigger's detached sync
        # spawn is, and it is unmistakable: `--sync` in argv with
        # start_new_session=True.
        for argv, kwargs in seen_popen:
            assert "--sync" not in argv, f"--status spawned a sync: {argv}"
            assert not kwargs.get("start_new_session"), f"detached spawn: {argv}"
            assert argv[0] == "git", f"non-git subprocess: {argv}"

    def test_status_leaves_the_runtime_repo_untouched(self, env, capsys):
        env.ok()
        head_before = env.head()
        status_before = _git(env.src, "status", "--porcelain").stdout

        rc, out = _run_status(capsys)

        assert _token(out) == "OK" and rc == 0  # a real report, not a no-op
        assert env.head() == head_before
        assert _git(env.src, "status", "--porcelain").stdout == status_before

    def test_repeated_polling_is_idempotent(self, env, capsys):
        """The point of a read-only probe: a watcher can hammer it."""
        _make_state(env, "BLOCKED")
        before = _snapshot(env.mirror_dir)

        codes = []
        for _ in range(5):
            rc, _out = _run_status(capsys)
            codes.append(rc)

        assert codes == [rms.STATUS_EXIT_CODES["BLOCKED"]] * 5
        assert _snapshot(env.mirror_dir) == before


# ===========================================================================
# config_status / parse_blocked — the two pure helpers
# ===========================================================================


class TestConfigStatus:
    def test_valid_config_returns_cfg_and_no_reason(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        (mirror_dir / "config.json").write_text(json.dumps(_valid_cfg(mirror_dir)))

        cfg, reason = rms.config_status()

        assert reason is None
        assert cfg is not None and cfg["branch"] == "main"

    def test_load_config_default_path_follows_the_sandbox(self, tmp_path):
        """A bare `load_config()` (what `_locked_sync()` and `maybe_trigger()`
        call) must read the sandboxed config, not the operator's real one."""
        root = str(tmp_path)
        assert rms.load_config.__defaults__ == (rms.CONFIG_PATH,)
        assert rms.CONFIG_PATH.startswith(root)
        assert rms.load_config.__defaults__[0].startswith(root)

    def test_it_does_not_rewrite_clone_dir(self, tmp_path, monkeypatch):
        """Unlike load_config, nothing on the status path acts on clone_dir,
        so it is reported as written rather than silently realpath'd."""
        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        raw = _valid_cfg(mirror_dir)
        (mirror_dir / "config.json").write_text(json.dumps(raw))

        cfg, _ = rms.config_status()

        assert cfg["clone_dir"] == raw["clone_dir"]

    def test_missing_file_is_a_reason_not_an_exception(self, tmp_path, monkeypatch):
        _patch_mirror_paths(monkeypatch, tmp_path / "nowhere")

        cfg, reason = rms.config_status()

        assert cfg is None
        assert "no config at" in reason

    def test_it_never_logs(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        (mirror_dir / "config.json").write_text("{not json")

        cfg, reason = rms.config_status()

        assert cfg is None and "unreadable" in reason
        assert not os.path.exists(rms.LOG_PATH)


class TestParseBlocked:
    def test_extracts_source_head_and_hits(self):
        head, hits = rms.parse_blocked(
            "# Mirror sync BLOCKED\n"
            "\n"
            "Source HEAD: abc123\n"
            "\n"
            "- `agents/a.md` matched `pat`\n"
            "- `hooks/b.py` matched `other`\n"
        )

        assert head == "abc123"
        assert hits == ["- `agents/a.md` matched `pat`", "- `hooks/b.py` matched `other`"]

    def test_unrecognised_body_yields_empty_head_and_hits(self):
        assert rms.parse_blocked("nothing structured here\n") == ("", [])

    def test_empty_body_is_safe(self):
        assert rms.parse_blocked("") == ("", [])

    def test_only_the_first_source_head_is_taken(self):
        head, _ = rms.parse_blocked("Source HEAD: aaa\nSource HEAD: bbb\n")

        assert head == "aaa"


# ===========================================================================
# end-to-end: a REAL BLOCKED.md, produced by sync() itself
# ===========================================================================


def _init_bare_remote(tmp_path, branch):
    """A bare repo seeded with one commit on `branch` — `git clone --branch`
    (what sync() does on its first run) cannot clone an empty one."""
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(bare)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    seed = tmp_path / "_seed"
    seed.mkdir()
    _git(seed, "init", "-q")
    _git(seed, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (seed / "README.md").write_text("seed\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(bare))
    _git(seed, "push", "-q", "origin", branch)
    return bare


@_requires_git
class TestAgainstARealBlockedFile:
    """The format contract, tested against the module's OWN writer rather than
    a hand-written fixture — so a change to sync()'s BLOCKED.md layout fails
    here instead of quietly degrading `--status` into "(unrecorded)"."""

    def test_status_reports_a_block_that_sync_actually_produced(
        self, tmp_path, sandbox, monkeypatch, capsys
    ):
        branch = "main"
        src = sandbox.claude
        _git(src, "init", "-q")
        _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
        (src / "agents").mkdir(exist_ok=True)
        (src / "agents" / "a.md").write_text("Internal: SecretVendor pricing.\n")
        _git(src, "add", "agents")
        _git(src, "commit", "-q", "-m", "initial")
        head = _git(src, "rev-parse", "HEAD").stdout.strip()

        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        bare = _init_bare_remote(tmp_path, branch)

        cfg = {
            "remote_url": str(bare),
            "clone_dir": str(tmp_path / "clone"),
            "branch": branch,
            "include": ["agents"],
            "replacements": [],
            "forbidden_patterns": ["secretvendor"],
        }
        assert rms.sync(cfg) == 1  # the gate fired for real
        assert os.path.exists(rms.BLOCKED_PATH)

        # A real sync leaves last_error behind too; --status must still lead
        # with BLOCKED (the actionable state), not bury it.
        (mirror_dir / "config.json").write_text(
            json.dumps(
                {
                    "remote_url": "https://github.com/acme/mirror.git",
                    "clone_dir": str(mirror_dir / "clone"),
                    "branch": branch,
                    "include": ["agents"],
                }
            )
        )

        rc, out = _run_status(capsys)

        assert _token(out) == "BLOCKED"
        assert rc == rms.STATUS_EXIT_CODES["BLOCKED"]
        assert head in out, "the source HEAD sync recorded must be relayed"
        assert "agents/a.md" in out, "the offending path must be relayed"
        assert "secretvendor" in out, "the matched pattern must be relayed"
        assert "(unrecorded)" not in out


# ===========================================================================
# main() dispatch
# ===========================================================================


@_requires_git
class TestMainDispatch:
    def test_status_flag_routes_to_status(self, env, monkeypatch):
        calls = []
        monkeypatch.setattr(rms, "status", lambda: calls.append(1) or 0)

        assert rms.main(["--status"]) == 0
        assert calls == [1]

    def test_status_never_reaches_sync(self, env, monkeypatch, capsys):
        env.ok()

        def boom(*a, **k):
            raise AssertionError("--status must never sync")

        monkeypatch.setattr(rms, "_locked_sync", boom)
        monkeypatch.setattr(rms, "sync", boom)

        rc, out = _run_status(capsys)

        assert _token(out) == "OK"
        assert rc == 0

    def test_status_wins_over_check_when_both_are_passed(
        self, env, monkeypatch, capsys
    ):
        """`--check` calls load_config (which logs). A caller asking for the
        read-only reporter must get it, not the writing probe."""
        _make_state(env, "INERT")
        monkeypatch.setattr(rms, "status", lambda: 99)

        assert rms.main(["--status", "--check"]) == 99
        assert rms.main(["--check", "--status"]) == 99


# ===========================================================================
# output shape — one-line-parseable AND human-readable
# ===========================================================================


@_requires_git
class TestOutputShape:
    @pytest.mark.parametrize("state", ["OK", "BLOCKED", "DRIFTED", "INERT"])
    def test_line_one_leads_with_the_bare_state_token(self, env, capsys, state):
        """`awk '{print $1}'` on line 1 must yield the state and nothing else."""
        _make_state(env, state)

        _, out = _run_status(capsys)

        first = out.splitlines()[0]
        assert first.split()[0] == state
        assert first != state, "the token needs a human-readable remainder"

    @pytest.mark.parametrize("state", ["OK", "BLOCKED", "DRIFTED", "INERT"])
    def test_every_state_reports_both_shas_for_a_human(self, env, capsys, state):
        _make_state(env, state)

        _, out = _run_status(capsys)

        assert "runtime HEAD:" in out
        assert "last mirrored:" in out
        assert "config:" in out
        assert "blocked:" in out

    def test_state_token_is_the_first_thing_on_stdout(self, env, capsys):
        """No banner, no blank line — a watcher reads line 1."""
        _make_state(env, "OK")

        _, out = _run_status(capsys)

        assert out.startswith("OK ")
