"""Hermetic tests for hooks/runtime_mirror_sync.py — the runtime-mirror sync
module (config validation/loading, push detection, the PostToolUse trigger,
and the export/redact/gate/push `sync()` pipeline) — plus the
posttooluse_bash.py wiring that calls `maybe_trigger(ev)` on every Bash event.

Spec source: the module's own docstring/comments (OPERATOR DIRECTIVE,
standing-authorization paragraph, and DESIGN points 1-5) and
posttooluse_bash.py's "job 3" docstring — NOT a snapshot of current output.
Every git-based `sync()` test uses real, local, offline scratch repos under
`tmp_path` (a throwaway bare repo standing in for the GitHub mirror) — no
network, and the real `~/.claude/.mirror/` and `~/.claude` are never touched.
This is MECHANICALLY ENFORCED, not just a convention: `_isolated_mirror_paths`
below is an autouse fixture that repoints ALL SEVEN of runtime_mirror_sync's
module-level path constants (MIRROR_DIR/CONFIG_PATH/STATE_PATH/LOCK_PATH/
LOG_PATH/BLOCKED_PATH/LAST_ERROR_PATH — computed once at import time from the
REAL `_lib.CLAUDE_DIR` and otherwise immune to a later `_lib.CLAUDE_DIR`
monkeypatch) under a throwaway tmp dir for EVERY test in this file by
default, before that test body runs — a test that patches only `MIRROR_DIR`
by hand and forgets `LOG_PATH` can no longer leak a `_log()` call (e.g. from
`load_config`'s own REJECTED path) into the operator's real sync.log, because
the autouse fixture already patched it first. A test needing a specific
mirror_dir (the sync() harness, `--check`, etc.) simply calls
`_patch_mirror_paths(monkeypatch, that_dir)` again, which composes fine.

NOTE on `validate_config`'s GitHub-only remote_url rule: `sync()` itself never
calls `validate_config` (it trusts its caller already did) — the intended
seam for a `sync()` end-to-end test is to build a `cfg` dict directly and call
`rms.sync(cfg)`, which is why these tests use local bare-repo paths as
`remote_url` there. `load_config`/`validate_config` are tested separately
against the real GitHub-URL/clone_dir-under-`.mirror`/branch/include rules.

A previous revision of this file recorded a genuine defect in
`command_has_push()` (it inspected `seg[0]` instead of `seg[1]` of each
`_lib.git_segments()` argv, so it never returned True for any real command).
That defect has since been FIXED in `runtime_mirror_sync.py`; this revision
tests the corrected behavior directly and no longer carries the old
defect-documentation scaffolding.
"""

from __future__ import annotations

import io
import json
import os
import subprocess

import _lib  # noqa: F401  (sys.path shim via conftest)
import pytest
import runtime_mirror_sync as rms

# ===========================================================================
# git plumbing helpers (real, local, offline repos only)
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
        # safe.bareRepository=all: modern git refuses to operate directly on
        # a bare repo (as our scratch "remote" is) outside an explicit
        # allowlist by default; this is a test-harness concern only, real
        # `sync()` never runs `git -C <bare-repo> ...` itself (it clones and
        # operates on the resulting non-bare clone_dir).
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


def _init_bare_remote(tmp_path, branch, seed_files=None, seed_bytes=None, name="remote.git"):
    """A bare repo seeded with one commit on `branch`.

    `git clone --branch <branch>` (what sync() does on its first run) fails
    against a totally empty bare repo, so the mirror's remote needs a real
    initial commit on the target branch before any sync can clone it — the
    operating assumption is a pre-existing mirror repo, not a from-scratch one.

    `seed_bytes` (rel -> bytes) seeds binary content the plain `seed_files`
    (rel -> str) form can't carry; when only `seed_bytes` is given the
    default `README.md` text seed is skipped rather than forced alongside it.
    """
    bare = tmp_path / name
    subprocess.run(
        ["git", "init", "--bare", "-q", str(bare)], check=True, capture_output=True, timeout=20
    )
    seed = tmp_path / f"_seed_{name}"
    seed.mkdir()
    _git(seed, "init", "-q")
    _git(seed, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    if seed_files is None and seed_bytes is None:
        seed_files = {"README.md": "seed\n"}
    for rel, content in (seed_files or {}).items():
        full = seed / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        _git(seed, "add", rel)
    for rel, data in (seed_bytes or {}).items():
        full = seed / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        _git(seed, "add", rel)
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(bare))
    _git(seed, "push", "-q", "origin", branch)
    return bare


def _bare_tip(bare, branch):
    return _git(bare, "rev-parse", branch).stdout.strip()


def _bare_file_at(bare, branch, rel):
    """Read a file's content at the bare remote's branch tip, or None if the
    path doesn't exist there. Reads the blob directly (no checkout needed)."""
    proc = subprocess.run(
        [
            "git",
            "-c",
            "safe.bareRepository=all",
            "--git-dir",
            str(bare),
            "show",
            f"{branch}:{rel}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _bare_path_exists_at(bare, branch, rel):
    """True iff `rel` exists in the tree at the bare remote's branch tip.
    Presence-only check (unlike `_bare_file_at`) so it's safe for binary
    content that `text=True` decoding could mangle or choke on."""
    proc = subprocess.run(
        [
            "git",
            "-c",
            "safe.bareRepository=all",
            "--git-dir",
            str(bare),
            "cat-file",
            "-e",
            f"{branch}:{rel}",
        ],
        capture_output=True,
        timeout=20,
    )
    return proc.returncode == 0


def _patch_mirror_paths(monkeypatch, mirror_dir):
    monkeypatch.setattr(rms, "MIRROR_DIR", str(mirror_dir))
    monkeypatch.setattr(rms, "CONFIG_PATH", os.path.join(str(mirror_dir), "config.json"))
    monkeypatch.setattr(rms, "STATE_PATH", os.path.join(str(mirror_dir), "last_synced_head"))
    monkeypatch.setattr(rms, "LOCK_PATH", os.path.join(str(mirror_dir), "sync.lock"))
    monkeypatch.setattr(rms, "LOG_PATH", os.path.join(str(mirror_dir), "sync.log"))
    monkeypatch.setattr(rms, "BLOCKED_PATH", os.path.join(str(mirror_dir), "BLOCKED.md"))
    monkeypatch.setattr(rms, "LAST_ERROR_PATH", os.path.join(str(mirror_dir), "last_error"))


@pytest.fixture(autouse=True)
def _isolated_mirror_paths(tmp_path, monkeypatch):
    """Autouse, whole-file hermeticity guarantee (review MAJOR, fixed here):
    every test in this module gets ALL SEVEN of runtime_mirror_sync's path
    constants repointed under a throwaway default dir before it runs, so a
    test that only patches MIRROR_DIR by hand and forgets LOG_PATH can no
    longer leak a `_log()` call into the real `~/.claude/.mirror/sync.log`
    (measured growth from exactly this gap before the fix: `load_config`'s
    own REJECTED-config path calls `_log`, and several TestValidateConfig/
    TestLoadConfig tests patched only MIRROR_DIR). Tests that need a
    SPECIFIC mirror_dir (the sync() harness, `--check`, etc.) call
    `_patch_mirror_paths(monkeypatch, that_dir)` again afterward, which
    composes fine — monkeypatch just remembers every setattr and reverts all
    of them at teardown, regardless of how many times a name was repatched.
    """
    _patch_mirror_paths(monkeypatch, tmp_path / ".default-mirror")


# ===========================================================================
# validate_config
# ===========================================================================


class TestValidateConfig:
    def _valid(self, mirror_dir):
        return {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(mirror_dir / "clone"),
            "branch": "main",
            "include": ["agents", "hooks"],
        }

    def test_accepts_a_clean_config(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        assert rms.validate_config(self._valid(mirror_dir)) is None

    def test_non_dict_is_rejected(self):
        assert rms.validate_config(["not", "a", "dict"]) == "config is not an object"

    def test_rejects_clone_dir_outside_mirror_dir(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["clone_dir"] = str(tmp_path / "elsewhere" / "clone")
        reason = rms.validate_config(cfg)
        assert reason is not None
        assert "clone_dir" in reason

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://gitlab.com/acme/mirror.git",  # not github
            "not a url at all",  # malformed
            "-rf /",  # dash-leading
            "git@github.com:acme",  # missing "/repo" segment
            "https://github.com/acme/mirror.git; rm -rf /",  # trailing junk
            "https://github.com/acme/../mirror.git",  # path-traversal "/../"
            "https://github.com/acme/./mirror.git",  # "/./"
            "https://github.com/acme/mirror.git/..",  # trailing "/.."
        ],
    )
    def test_rejects_bad_remote_url(self, tmp_path, monkeypatch, bad_url):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["remote_url"] = bad_url
        reason = rms.validate_config(cfg)
        assert reason is not None
        assert "remote_url" in reason

    @pytest.mark.parametrize("bad_branch", ["-main", "main withspace", "semi;colon"])
    def test_rejects_bad_branch_chars(self, tmp_path, monkeypatch, bad_branch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["branch"] = bad_branch
        assert rms.validate_config(cfg) is not None

    @pytest.mark.parametrize("bad_entry", ["/abs/path", "../escape", "-flag", "~/home"])
    def test_rejects_unsafe_include_entry(self, tmp_path, monkeypatch, bad_entry):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["include"] = ["agents", bad_entry]
        reason = rms.validate_config(cfg)
        assert reason is not None
        assert "include" in reason

    def test_rejects_include_that_is_not_a_list(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["include"] = "agents"  # a bare string, not a list of entries
        reason = rms.validate_config(cfg)
        assert reason is not None
        assert "include" in reason

    def test_rejects_unsafe_mirror_managed_entry(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = self._valid(mirror_dir)
        cfg["mirror_managed"] = ["../escape"]
        reason = rms.validate_config(cfg)
        assert reason is not None
        assert "mirror_managed" in reason


# ===========================================================================
# load_config
# ===========================================================================


class TestLoadConfig:
    def test_missing_file_returns_none(self, tmp_path):
        assert rms.load_config(str(tmp_path / "nope.json")) is None

    def test_invalid_json_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        assert rms.load_config(str(p)) is None

    def test_non_dict_returns_none(self, tmp_path):
        p = tmp_path / "list.json"
        p.write_text(json.dumps(["a", "b"]))
        assert rms.load_config(str(p)) is None

    @pytest.mark.parametrize("missing_key", ["remote_url", "clone_dir", "branch", "include"])
    def test_missing_required_key_returns_none(self, tmp_path, monkeypatch, missing_key):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(mirror_dir / "clone"),
            "branch": "main",
            "include": ["agents"],
        }
        del cfg[missing_key]
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps(cfg))
        assert rms.load_config(str(p)) is None

    def test_valid_config_returns_dict(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(mirror_dir / "clone"),
            "branch": "main",
            "include": ["agents"],
        }
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps(cfg))

        loaded = rms.load_config(str(p))

        # clone_dir comes back REALPATH-resolved (see
        # test_load_config_resolves_clone_dir_to_realpath below for the
        # dedicated symlink case) -- compare it separately from the rest.
        assert loaded is not None
        expected = dict(cfg)
        expected["clone_dir"] = os.path.realpath(cfg["clone_dir"])
        assert loaded == expected

    def test_syntactically_valid_json_failing_validation_returns_none(
        self, tmp_path, monkeypatch
    ):
        """A config that parses fine as JSON but fails validate_config's
        rules (here: a non-GitHub remote_url) is still inert."""
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = {
            "remote_url": "https://gitlab.com/acme/mirror.git",
            "clone_dir": str(mirror_dir / "clone"),
            "branch": "main",
            "include": ["agents"],
        }
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps(cfg))
        assert rms.load_config(str(p)) is None

    def test_resolves_clone_dir_to_realpath(self, tmp_path, monkeypatch):
        """DESIGN/TOCTOU note in load_config: the validated realpath is what
        every consumer gets, not the possibly-symlinked spelling in the
        config file."""
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        real_target = mirror_dir / "real-clone"
        real_target.mkdir(parents=True)
        link = mirror_dir / "clone-link"
        os.symlink(str(real_target), str(link))

        cfg = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(link),
            "branch": "main",
            "include": ["agents"],
        }
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps(cfg))

        loaded = rms.load_config(str(p))

        assert loaded is not None
        assert loaded["clone_dir"] == os.path.realpath(str(link))
        assert loaded["clone_dir"] == str(real_target.resolve())
        assert loaded["clone_dir"] != str(link)  # the symlink spelling itself


# ===========================================================================
# command_has_push
# ===========================================================================


class TestCommandHasPush:
    @pytest.mark.parametrize(
        "command",
        [
            "git push",
            "git push origin master",
            "cd /x && git push",
            "GIT_TRACE=1 git -C /repo push",
        ],
    )
    def test_true_for_a_push(self, command):
        assert rms.command_has_push(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m x -- a.py',
            "echo push",
            "git pushup",
            "",
        ],
    )
    def test_false_for_a_non_push(self, command):
        assert rms.command_has_push(command) is False

    def test_untokenizable_but_git_mentioning_segment_is_not_a_push(self):
        """_lib.git_segments surfaces an untokenizable-but-git-mentioning
        segment as the sentinel ["git", "\\x00untokenizable"] rather than a
        real argv (an unterminated quote here) -- command_has_push must
        treat that as "not push", per its own docstring's quiet-on-the-
        closed-side design (a compound/quoted push just misses this push
        and catches up on the next clean one)."""
        assert rms.command_has_push("git commit -m 'unterminated") is False


# ===========================================================================
# apply_replacements
# ===========================================================================


class TestApplyReplacements:
    def test_pairs_applied_in_list_order(self):
        # alpha->beta first (all "alpha" become "beta"), THEN beta->gamma
        # turns every "beta" (old ones AND the ones just produced) to gamma.
        data = "alpha beta"
        replacements = [["alpha", "beta"], ["beta", "gamma"]]
        assert rms.apply_replacements(data, replacements) == "gamma gamma"

    def test_empty_replacements_is_identity(self):
        assert rms.apply_replacements("unchanged", []) == "unchanged"

    def test_malformed_entries_are_skipped_and_logged(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        data = "keep SecretCorp"
        replacements = [
            ["SecretCorp"],  # wrong length
            "not-a-pair",  # not a list
            None,  # not a list
            [1, 2, 3],  # wrong length
            ["SecretCorp", "ExampleCo"],  # the only valid entry
        ]

        result = rms.apply_replacements(data, replacements)

        assert result == "keep ExampleCo"
        log_text = open(rms.LOG_PATH, encoding="utf-8").read()
        assert log_text.count("malformed replacement entry skipped") == 4


# ===========================================================================
# _compile_gate — post-redaction sanity for exported .py/.json (unit-level,
# cheaper than exercising it through a full sync())
# ===========================================================================


class TestCompileGate:
    def test_valid_py_passes(self, tmp_path):
        (tmp_path / "ok.py").write_text("x = 1\n")
        assert rms._compile_gate(str(tmp_path), ["ok.py"]) == []

    def test_broken_py_fails(self, tmp_path):
        (tmp_path / "bad.py").write_text("def f(:\n")
        bad = rms._compile_gate(str(tmp_path), ["bad.py"])
        assert len(bad) == 1
        assert bad[0][0] == "bad.py"
        assert "post-redaction" in bad[0][1]

    def test_valid_json_passes(self, tmp_path):
        (tmp_path / "ok.json").write_text('{"a": 1}')
        assert rms._compile_gate(str(tmp_path), ["ok.json"]) == []

    def test_broken_json_fails(self, tmp_path):
        (tmp_path / "bad.json").write_text('{"a": }')
        bad = rms._compile_gate(str(tmp_path), ["bad.json"])
        assert len(bad) == 1
        assert bad[0][0] == "bad.json"

    def test_other_extensions_are_ignored(self, tmp_path):
        (tmp_path / "note.md").write_text("whatever ) ( broken\n")
        assert rms._compile_gate(str(tmp_path), ["note.md"]) == []


# ===========================================================================
# _remove_under
# ===========================================================================


class TestRemoveUnder:
    def test_refuses_to_delete_outside_clone(self, tmp_path):
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        with pytest.raises(ValueError):
            rms._remove_under(str(clone_dir), "../outside.txt")

    def test_removes_a_file_inside_clone(self, tmp_path):
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        (clone_dir / "a.txt").write_text("x")
        rms._remove_under(str(clone_dir), "a.txt")
        assert not (clone_dir / "a.txt").exists()

    def test_removes_a_directory_inside_clone(self, tmp_path):
        clone_dir = tmp_path / "clone"
        (clone_dir / "sub").mkdir(parents=True)
        (clone_dir / "sub" / "f.txt").write_text("x")
        rms._remove_under(str(clone_dir), "sub")
        assert not (clone_dir / "sub").exists()


# ===========================================================================
# scan_forbidden
# ===========================================================================


class TestScanForbidden:
    def test_detects_case_insensitive_hit(self, tmp_path):
        (tmp_path / "a.md").write_text("Built for SECRETCORP partners.\n")
        violations = rms.scan_forbidden(str(tmp_path), ["a.md"], ["secretcorp"], {})
        assert violations == [("a.md", "secretcorp")]

    def test_forbidden_allow_exempts_a_specific_file(self, tmp_path):
        (tmp_path / "LICENSE").write_text("Copyright SecretCorp\n")
        violations = rms.scan_forbidden(
            str(tmp_path), ["LICENSE"], ["secretcorp"], {"LICENSE": ["secretcorp"]}
        )
        assert violations == []

    def test_allow_is_per_file_not_global(self, tmp_path):
        (tmp_path / "LICENSE").write_text("Copyright SecretCorp\n")
        (tmp_path / "other.md").write_text("Refers to SecretCorp too\n")
        violations = rms.scan_forbidden(
            str(tmp_path),
            ["LICENSE", "other.md"],
            ["secretcorp"],
            {"LICENSE": ["secretcorp"]},
        )
        assert violations == [("other.md", "secretcorp")]

    def test_unreadable_file_is_reported_as_a_violation(self, tmp_path):
        # Path never created -> unreadable -> fail-closed.
        violations = rms.scan_forbidden(str(tmp_path), ["missing.md"], ["secretcorp"], {})
        assert violations == [("missing.md", "<unreadable>")]

    def test_binary_file_is_reported_as_unscannable_violation(self, tmp_path):
        """Replaces the old "skipped, not a violation" behavior: a caller
        must EXCLUDE a binary/oversize file from publish itself (see the
        sync()-level test below) — scan_forbidden alone treats it as
        fail-closed unscannable, never a silent pass."""
        (tmp_path / "bin.dat").write_bytes(b"\x00\x01SECRETCORP")
        violations = rms.scan_forbidden(str(tmp_path), ["bin.dat"], ["secretcorp"], {})
        assert violations == [("bin.dat", "<unscannable: binary or oversize>")]

    def test_clean_file_has_no_violation(self, tmp_path):
        (tmp_path / "clean.md").write_text("nothing to see here\n")
        violations = rms.scan_forbidden(str(tmp_path), ["clean.md"], ["secretcorp"], {})
        assert violations == []


# ===========================================================================
# maybe_trigger
# ===========================================================================


@pytest.fixture
def mt_paths(tmp_path, monkeypatch):
    """Isolated MIRROR_DIR/LOG_PATH for maybe_trigger (which opens LOG_PATH
    directly, with no _log()-style os.makedirs of its own)."""
    mirror_dir = tmp_path / ".mirror"
    mirror_dir.mkdir()
    _patch_mirror_paths(monkeypatch, mirror_dir)
    return mirror_dir


def _cfg(**over):
    cfg = {
        "remote_url": "https://github.com/acme/mirror.git",
        "clone_dir": "/x",
        "branch": "main",
        "include": ["a"],
    }
    cfg.update(over)
    return cfg


class TestMaybeTrigger:
    def test_non_bash_tool_never_spawns(self, mt_paths, monkeypatch):
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(rms, "load_config", lambda: _cfg())
        ev = {"tool_name": "Read", "tool_input": {"command": "git push"}}
        assert rms.maybe_trigger(ev) is False
        assert calls == []

    def test_no_push_in_command_never_spawns(self, mt_paths, monkeypatch):
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(rms, "load_config", lambda: _cfg())
        ev = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        assert rms.maybe_trigger(ev) is False
        assert calls == []

    def test_push_with_config_spawns_detached_sync(self, mt_paths, monkeypatch, tmp_path):
        calls = []

        def fake_popen(argv, **kwargs):
            calls.append((argv, kwargs))
            return object()

        monkeypatch.setattr(rms.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            rms, "load_config", lambda: _cfg(clone_dir=str(tmp_path / "clone"))
        )
        elsewhere = tmp_path / "somewhere-else"
        elsewhere.mkdir()
        ev = {"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": str(elsewhere)}

        assert rms.maybe_trigger(ev) is True

        assert len(calls) == 1
        argv, kwargs = calls[0]
        assert "--sync" in argv
        assert kwargs.get("start_new_session") is True

    def test_push_via_compound_command_spawns(self, mt_paths, monkeypatch, tmp_path):
        """The real tokenizer must find `push` inside a compound command,
        not just a bare `git push`."""
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(
            rms, "load_config", lambda: _cfg(clone_dir=str(tmp_path / "clone"))
        )
        ev = {"tool_name": "Bash", "tool_input": {"command": "cd /x && git push origin main"}}

        assert rms.maybe_trigger(ev) is True
        assert len(calls) == 1

    def test_missing_config_never_spawns(self, mt_paths, monkeypatch):
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(rms, "load_config", lambda: None)
        ev = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
        assert rms.maybe_trigger(ev) is False
        assert calls == []

    def test_self_trigger_suppressed_when_cwd_inside_clone_dir(
        self, mt_paths, monkeypatch, tmp_path
    ):
        clone_dir = tmp_path / "clone"
        (clone_dir / "sub").mkdir(parents=True)
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(rms, "load_config", lambda: _cfg(clone_dir=str(clone_dir)))
        ev = {
            "tool_name": "Bash",
            "tool_input": {"command": "git push"},
            "cwd": str(clone_dir / "sub"),
        }
        assert rms.maybe_trigger(ev) is False
        assert calls == []

    def test_self_trigger_suppressed_exactly_at_clone_dir_root(
        self, mt_paths, monkeypatch, tmp_path
    ):
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        calls = []
        monkeypatch.setattr(rms.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(rms, "load_config", lambda: _cfg(clone_dir=str(clone_dir)))
        ev = {
            "tool_name": "Bash",
            "tool_input": {"command": "git push"},
            "cwd": str(clone_dir),
        }
        assert rms.maybe_trigger(ev) is False
        assert calls == []

    def test_exception_inside_never_propagates(self, mt_paths, monkeypatch, tmp_path):
        def boom(*a, **k):
            raise RuntimeError("spawn failed")

        monkeypatch.setattr(rms.subprocess, "Popen", boom)
        monkeypatch.setattr(
            rms, "load_config", lambda: _cfg(clone_dir=str(tmp_path / "clone"))
        )
        ev = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
        assert rms.maybe_trigger(ev) is False  # must never raise


# ===========================================================================
# sync() end-to-end — real, local, offline scratch git repos
# ===========================================================================


@pytest.fixture
def mirror_harness(tmp_path, sandbox, monkeypatch):
    """A fake runtime repo (rooted at the sandboxed `_lib.CLAUDE_DIR`) plus a
    bare "remote" repo standing in for the GitHub mirror. Returns a small
    helper object; see its methods below."""
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "agents").mkdir(exist_ok=True)
    (src / "agents" / "a.md").write_text("Built for SecretCorp partners.\n")
    (src / "hooks").mkdir(exist_ok=True)
    (src / "hooks" / "h.txt").write_text("clean text file\n")
    _git(src, "add", "agents", "hooks")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    bare = _init_bare_remote(tmp_path, branch=branch)

    class Harness:
        def __init__(self):
            self.tmp_path = tmp_path
            self.src = src
            self.bare = bare
            self.branch = branch
            self.mirror_dir = mirror_dir
            self.cfg = {
                "remote_url": str(bare),
                "clone_dir": str(tmp_path / "clone"),
                "branch": branch,
                "include": ["agents", "hooks"],
                "replacements": [["SecretCorp", "ExampleCo"]],
                "forbidden_patterns": ["secretcorp"],
            }

        def commit(self, rel, content):
            full = self.src / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)
            _git(self.src, "add", rel)
            _git(self.src, "commit", "-q", "-m", f"update {rel}")

        def commit_bytes(self, rel, data: bytes):
            full = self.src / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(data)
            _git(self.src, "add", rel)
            _git(self.src, "commit", "-q", "-m", f"update {rel}")

        def rm_commit(self, rel):
            _git(self.src, "rm", "-q", rel)
            _git(self.src, "commit", "-q", "-m", f"remove {rel}")

        def commit_many(self, dir_rel, count, prefix="file"):
            """Write `count` small distinct files under dir_rel in ONE
            commit; returns their dir_rel-relative paths."""
            base = self.src / dir_rel
            base.mkdir(parents=True, exist_ok=True)
            rels = []
            for i in range(count):
                name = f"{prefix}{i:03d}.md"
                (base / name).write_text(f"bulk file {i}\n")
                rels.append(f"{dir_rel}/{name}")
            _git(self.src, "add", dir_rel)
            _git(self.src, "commit", "-q", "-m", f"add {count} files under {dir_rel}")
            return rels

        def rm_many(self, rels):
            _git(self.src, "rm", "-q", "--", *rels)
            _git(self.src, "commit", "-q", "-m", f"remove {len(rels)} files")

        def head(self):
            return _git(self.src, "rev-parse", "HEAD").stdout.strip()

        def tip(self):
            return _bare_tip(self.bare, self.branch)

        def tip_file(self, rel):
            return _bare_file_at(self.bare, self.branch, rel)

        def state(self):
            try:
                return open(rms.STATE_PATH, encoding="utf-8").read().strip()
            except OSError:
                return None

        def blocked_exists(self):
            return os.path.exists(rms.BLOCKED_PATH)

        def blocked_text(self):
            return open(rms.BLOCKED_PATH, encoding="utf-8").read()

        def last_error_exists(self):
            return os.path.exists(rms.LAST_ERROR_PATH)

        def last_error_text(self):
            return open(rms.LAST_ERROR_PATH, encoding="utf-8").read()

        def sync(self):
            return rms.sync(dict(self.cfg))

    return Harness()


@_requires_git
class TestSyncEndToEnd:
    def test_happy_path_redacts_and_pushes(self, mirror_harness):
        h = mirror_harness
        tip_before = h.tip()
        rc = h.sync()
        assert rc == 0
        # The mirror is its own git history (different tree/parents than the
        # runtime repo), so a real new commit landed there -- assert the tip
        # ADVANCED, not that its sha matches the runtime's own HEAD sha.
        assert h.tip() != tip_before
        content = h.tip_file("agents/a.md")
        assert content is not None
        assert "ExampleCo" in content
        assert "SecretCorp" not in content
        assert h.state() == h.head()

    def test_noop_second_run_does_not_create_a_new_commit(self, mirror_harness):
        h = mirror_harness
        assert h.sync() == 0
        tip1 = h.tip()
        assert h.sync() == 0
        assert h.tip() == tip1

    def test_blocked_when_forbidden_pattern_survives_redaction(self, mirror_harness):
        h = mirror_harness
        assert h.sync() == 0
        baseline_tip = h.tip()

        h.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        h.cfg["forbidden_patterns"] = ["secretcorp", "secretvendor"]
        rc = h.sync()

        assert rc == 1
        assert h.blocked_exists()
        text = h.blocked_text()
        assert "agents/b.md" in text
        assert "secretvendor" in text
        assert h.tip() == baseline_tip  # nothing leaked to the remote
        # Every failing path surfaces durably via .mirror/last_error.
        assert h.last_error_exists()
        assert "BLOCKED" in h.last_error_text()

    def test_recovery_after_extending_replacements(self, mirror_harness):
        """Required pairing for the blocked-path test above: the operator can
        extend the replacement map and reach a working, published state, and
        the surfaced failure clears on that success."""
        h = mirror_harness
        assert h.sync() == 0

        h.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        h.cfg["forbidden_patterns"] = ["secretcorp", "secretvendor"]
        assert h.sync() == 1
        assert h.blocked_exists()
        assert h.last_error_exists()

        blocked_tip = h.tip()
        h.cfg["replacements"] = h.cfg["replacements"] + [["SecretVendor", "ExampleVendor"]]
        rc = h.sync()

        assert rc == 0
        assert not h.blocked_exists()
        assert not h.last_error_exists()  # cleared on success
        assert h.tip() != blocked_tip  # the remote advanced past the blocked state
        assert h.state() == h.head()
        content = h.tip_file("agents/b.md")
        assert content is not None
        assert "ExampleVendor" in content
        assert "SecretVendor" not in content

    def test_deletion_propagates_and_third_sync_does_not_wedge(self, mirror_harness):
        h = mirror_harness
        h.cfg["include"] = h.cfg["include"] + ["standalone.md"]

        h.commit("agents/gone.md", "temporary\n")
        h.commit("standalone.md", "temporary top-level file\n")
        assert h.sync() == 0
        assert h.tip_file("agents/gone.md") is not None
        assert h.tip_file("standalone.md") is not None

        h.rm_commit("agents/gone.md")
        h.rm_commit("standalone.md")
        assert h.sync() == 0
        assert h.tip_file("agents/gone.md") is None
        assert h.tip_file("standalone.md") is None

        # THIRD sync, with an unrelated new upstream change. "standalone.md"
        # is now a vanished top-level pathspec (absent from BOTH the
        # worktree and the git index); this must not make git add/commit
        # fatal — exactly the wedge _present_pathspecs exists to prevent.
        h.commit("agents/a.md", "Built for SecretCorp partners, v2.\n")
        rc = h.sync()

        assert rc == 0
        content = h.tip_file("agents/a.md")
        assert content is not None and "v2" in content

    def test_stray_untracked_file_at_clone_root_does_not_cause_failure(self, mirror_harness):
        """A stray file living directly in the clone (e.g. a macOS
        `.DS_Store`) that is outside every include path must not be treated
        as a diff -- git status/add are now scoped to the include pathspecs,
        not the whole clone."""
        h = mirror_harness
        assert h.sync() == 0

        # An upstream change entirely OUTSIDE the include manifest -- HEAD
        # advances, but nothing under "agents"/"hooks" actually changes.
        (h.src / "OUTSIDE.md").write_text("not part of the manifest\n")
        _git(h.src, "add", "OUTSIDE.md")
        _git(h.src, "commit", "-q", "-m", "unrelated top-level change")

        stray = os.path.join(h.cfg["clone_dir"], ".DS_Store")
        with open(stray, "wb") as fh:
            fh.write(b"\x00\x01stray")

        rc = h.sync()

        assert rc == 0
        assert h.tip_file(".DS_Store") is None  # never published
        assert os.path.exists(stray)  # left alone, not swept up

    def test_binary_file_excluded_from_publish_not_blocked(self, mirror_harness):
        h = mirror_harness
        h.commit_bytes("agents/logo.png", b"\x89PNG\x00\x01\x02binarydata")

        rc = h.sync()

        assert rc == 0
        assert h.tip_file("agents/logo.png") is None  # excluded, never published
        assert h.tip_file("agents/a.md") is not None  # the rest still published

    def test_compile_gate_blocks_py_broken_by_replacement(self, mirror_harness):
        h = mirror_harness
        h.commit("hooks/tool.py", "print('clean')\n")
        baseline_tip = h.tip()
        h.cfg["replacements"] = h.cfg["replacements"] + [["(", ""]]  # breaks hooks/tool.py

        rc = h.sync()

        assert rc == 1
        assert h.blocked_exists()
        text = h.blocked_text()
        assert "hooks/tool.py" in text
        assert "post-redaction" in text
        assert h.tip() == baseline_tip  # nothing published

    def test_compile_gate_passes_a_valid_untouched_py_file(self, mirror_harness):
        """A healthy .py file that no replacement ever touches must publish
        normally -- the post-redaction gate exists to catch a replacement
        BREAKING source (DESIGN point 3), not to block .py files outright."""
        h = mirror_harness
        h.commit("hooks/tool.py", "print('clean')\n")

        rc = h.sync()

        assert rc == 0
        assert h.tip_file("hooks/tool.py") == "print('clean')\n"

    def test_recovery_after_fixing_compile_breaking_replacement(self, mirror_harness):
        h = mirror_harness
        h.commit("hooks/tool.py", "print('clean')\n")
        baseline_tip = h.tip()
        h.cfg["replacements"] = h.cfg["replacements"] + [["(", ""]]
        assert h.sync() == 1
        assert h.blocked_exists()

        h.cfg["replacements"] = [["SecretCorp", "ExampleCo"]]  # drop the breaking pair
        rc = h.sync()

        assert rc == 0
        assert not h.blocked_exists()
        assert h.tip() != baseline_tip
        assert h.tip_file("hooks/tool.py") == "print('clean')\n"

    def test_origin_mismatch_refuses_to_publish(self, mirror_harness):
        h = mirror_harness
        assert h.sync() == 0
        baseline_tip = h.tip()

        h.commit("agents/a.md", "Built for SecretCorp partners, v2.\n")
        h.cfg["remote_url"] = str(h.bare) + "-not-the-configured-one"

        rc = h.sync()

        assert rc == 1
        assert h.tip() == baseline_tip  # nothing pushed

    def test_clone_on_wrong_branch_refuses_before_mutating(self, mirror_harness):
        """Branch identity, checked alongside origin identity, BEFORE the
        cleanup checkout/pull mutates anything."""
        h = mirror_harness
        assert h.sync() == 0
        baseline_tip = h.tip()

        _git(h.cfg["clone_dir"], "checkout", "-q", "-b", "rogue")

        h.commit("agents/a.md", "Built for SecretCorp partners, v2.\n")
        rc = h.sync()

        assert rc == 1
        assert h.tip() == baseline_tip  # refused before any mutation reached the remote

    def test_symlink_in_include_path_excluded_from_publish(self, mirror_harness):
        """DESIGN point 3 / the export loop's own comment: a symlink under
        an include path is excluded from publish by unlinking the symlink
        ENTRY, never touching whatever it points at -- its target (here a
        sibling file in the same tree) still publishes normally.

        (History: an earlier `_remove_under` realpath'd the full path,
        following the link and deleting the TARGET instead; this test found
        that and the fix now realpaths only the parent directory.)"""
        h = mirror_harness
        target = h.src / "agents" / "target.md"
        target.write_text("target content\n")
        link = h.src / "agents" / "link.md"
        os.symlink("target.md", str(link))
        _git(h.src, "add", "agents")
        _git(h.src, "commit", "-q", "-m", "add symlink")

        rc = h.sync()

        assert rc == 0
        assert h.tip_file("agents/link.md") is None  # excluded, never published
        assert h.tip_file("agents/target.md") is not None

    def test_non_utf8_file_excluded_from_publish(self, mirror_harness):
        """A latin-1-encoded file with no NUL bytes still reads as "text" by
        the NUL-byte check, but must fail a STRICT utf-8 decode and be
        excluded -- replaces the old surrogateescape round-trip branch."""
        h = mirror_harness
        data = "café".encode("latin-1")
        assert b"\x00" not in data
        with pytest.raises(UnicodeDecodeError):
            data.decode("utf-8")
        h.commit_bytes("agents/latin1.md", data)

        rc = h.sync()

        assert rc == 0
        assert h.tip_file("agents/latin1.md") is None
        assert h.tip_file("agents/a.md") is not None

    def test_oversize_file_excluded_from_publish(self, mirror_harness):
        h = mirror_harness
        data = b"a" * (rms.MAX_TEXT_BYTES + 1024)
        h.commit_bytes("agents/big.md", data)

        rc = h.sync()

        assert rc == 0
        assert h.tip_file("agents/big.md") is None
        assert h.tip_file("agents/a.md") is not None

    def test_mass_deletion_guard_blocks_then_allows_with_env_override(
        self, mirror_harness, monkeypatch
    ):
        h = mirror_harness
        rels = h.commit_many("agents/bulk", 50)
        assert h.sync() == 0
        baseline_tip = h.tip()

        to_delete = rels[:45]
        h.rm_many(to_delete)

        monkeypatch.delenv("CSA_MIRROR_ALLOW_MASS_DELETE", raising=False)
        rc = h.sync()

        assert rc == 1
        assert h.last_error_exists()
        assert "CSA_MIRROR_ALLOW_MASS_DELETE" in h.last_error_text()
        assert h.tip() == baseline_tip  # refused, nothing published
        for rel in to_delete:
            assert h.tip_file(rel) is not None  # still present -- refused, not partial

        monkeypatch.setenv("CSA_MIRROR_ALLOW_MASS_DELETE", "1")
        rc2 = h.sync()

        assert rc2 == 0
        assert h.tip() != baseline_tip
        for rel in to_delete:
            assert h.tip_file(rel) is None

    def test_failed_push_stays_failed_until_remote_repaired(self, mirror_harness):
        """Round-2 review blocker: success must be verified against the
        REMOTE, never inferred from "no local diff" -- a prior run's
        committed-but-unpushed work must not be forgotten just because a
        later sync's export reproduces no NEW diff.

        Simulates a real push failure by making the bare remote's directory
        (and its objects/refs subdirs) unwritable -- verified independently
        of this module in a bare shell: this makes `git push` fail
        ("unpacker error") while `git pull --ff-only` (read-only) still
        succeeds as a no-op, exactly matching what a real transient
        remote-side failure (e.g. a GitHub outage) would look like from the
        clone's perspective.
        """
        h = mirror_harness

        def _lock_remote(mode):
            os.chmod(str(h.bare), mode)
            for sub in ("objects", "refs"):
                p = os.path.join(str(h.bare), sub)
                if os.path.isdir(p):
                    os.chmod(p, mode)

        baseline_tip = h.tip()
        _lock_remote(0o500)
        try:
            rc1 = h.sync()
            assert rc1 == 1
            assert h.last_error_exists()
            assert h.tip() == baseline_tip  # nothing reached the remote
            assert h.state() != h.head()  # state not advanced

            # Retry with the remote STILL broken -- must not silently
            # "succeed" just because the clone's local tree already matches
            # the (locally-committed-but-unpushed) HEAD.
            rc2 = h.sync()
            assert rc2 == 1
            assert h.last_error_exists()
            assert h.tip() == baseline_tip
            assert h.state() != h.head()
        finally:
            _lock_remote(0o700)

        rc3 = h.sync()

        assert rc3 == 0
        assert h.tip() != baseline_tip
        assert h.state() == h.head()
        assert not h.last_error_exists()

    # NOTE (untested, flagged rather than forced): DESIGN's "transient
    # archive failure != absence" distinction (`git cat-file -e HEAD:<top>`
    # before wiping, so a `git archive` that errors on a path known to exist
    # aborts instead of publishing a false deletion) has no cheap way to
    # simulate here -- it requires making `git archive` fail on a path that
    # `git cat-file -e` still reports present, which means corrupting the
    # runtime repo's own object store mid-sync. The absence-vs-archive-error
    # branches are covered separately: absence by
    # test_deletion_propagates_and_third_sync_does_not_wedge (a genuinely
    # deleted path), existence by every other passing sync in this file
    # (archive never errors on a path cat-file confirms).


@_requires_git
def test_mirror_managed_paths_left_untouched(tmp_path, sandbox, monkeypatch):
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "CLAUDE.md").write_text("RUNTIME VERSION\n")
    (src / "agents").mkdir()
    (src / "agents" / "a.md").write_text("clean\n")
    _git(src, "add", "CLAUDE.md", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    bare = _init_bare_remote(
        tmp_path, branch=branch, seed_files={"CLAUDE.md": "MIRROR VERSION\n"}
    )

    cfg = {
        "remote_url": str(bare),
        "clone_dir": str(tmp_path / "clone"),
        "branch": branch,
        "include": ["agents", "CLAUDE.md"],
        "mirror_managed": ["CLAUDE.md"],
        "replacements": [],
        "forbidden_patterns": [],
    }
    rc = rms.sync(cfg)

    assert rc == 0
    assert _bare_file_at(bare, branch, "CLAUDE.md") == "MIRROR VERSION\n"
    # the non-managed path DID export normally, proving sync actually ran
    assert _bare_file_at(bare, branch, "agents/a.md") == "clean\n"


@_requires_git
def test_mirror_managed_file_with_forbidden_string_is_blocked(tmp_path, sandbox, monkeypatch):
    """DESIGN point 4: mirror-managed files are never overwritten, but they
    still publish, so they still get scanned."""
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "CLAUDE.md").write_text("RUNTIME VERSION\n")
    (src / "agents").mkdir()
    (src / "agents" / "a.md").write_text("clean\n")
    _git(src, "add", "CLAUDE.md", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    bare = _init_bare_remote(
        tmp_path,
        branch=branch,
        seed_files={"CLAUDE.md": "Mirror maintained by SecretCorp Ops.\n"},
    )
    cfg = {
        "remote_url": str(bare),
        "clone_dir": str(tmp_path / "clone"),
        "branch": branch,
        "include": ["agents", "CLAUDE.md"],
        "mirror_managed": ["CLAUDE.md"],
        "replacements": [],
        "forbidden_patterns": ["secretcorp"],
    }

    rc = rms.sync(cfg)

    assert rc == 1
    assert os.path.exists(rms.BLOCKED_PATH)
    assert "CLAUDE.md" in open(rms.BLOCKED_PATH, encoding="utf-8").read()


@_requires_git
def test_mirror_managed_file_with_forbidden_allow_publishes(tmp_path, sandbox, monkeypatch):
    """Paired recovery for the test above: a `forbidden_allow` entry for the
    managed file lets that same content through, unmodified."""
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "CLAUDE.md").write_text("RUNTIME VERSION\n")
    (src / "agents").mkdir()
    (src / "agents" / "a.md").write_text("clean\n")
    _git(src, "add", "CLAUDE.md", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    seeded_content = "Mirror maintained by SecretCorp Ops.\n"
    bare = _init_bare_remote(
        tmp_path, branch=branch, seed_files={"CLAUDE.md": seeded_content}
    )
    cfg = {
        "remote_url": str(bare),
        "clone_dir": str(tmp_path / "clone"),
        "branch": branch,
        "include": ["agents", "CLAUDE.md"],
        "mirror_managed": ["CLAUDE.md"],
        "replacements": [],
        "forbidden_patterns": ["secretcorp"],
        "forbidden_allow": {"CLAUDE.md": ["secretcorp"]},
    }

    rc = rms.sync(cfg)

    assert rc == 0
    assert not os.path.exists(rms.BLOCKED_PATH)
    # managed content publishes VERBATIM -- never redacted, per DESIGN pt 4.
    assert _bare_file_at(bare, branch, "CLAUDE.md") == seeded_content


@_requires_git
def test_tracked_file_outside_manifest_is_still_scanned(tmp_path, sandbox, monkeypatch):
    """The scan set is `git ls-files` UNION publishable -- a file tracked in
    the clone but entirely outside the include manifest (e.g. committed to
    GitHub by hand, or left behind by a shrunken manifest) still publishes,
    so it still has to pass the gate."""
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "agents").mkdir()
    (src / "agents" / "a.md").write_text("clean\n")
    _git(src, "add", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    bare = _init_bare_remote(
        tmp_path,
        branch=branch,
        seed_files={
            "README.md": "seed\n",
            "leftover.md": "Old notes mentioning SecretCorp internals.\n",
            # Non-ASCII filename: git's core.quotePath C-quotes this in
            # plain `ls-files` output, so only the `-z` NUL-delimited form
            # yields a spelling that exists on disk — this seed is what
            # keeps the `-z` fix falsifiable (reverting it drops this file
            # from the scan set and the test goes red).
            "leftover-café.md": "More SecretCorp notes, non-ASCII name.\n",
        },
    )
    cfg = {
        "remote_url": str(bare),
        "clone_dir": str(tmp_path / "clone"),
        "branch": branch,
        "include": ["agents"],  # neither leftover file is in the manifest
        "replacements": [],
        "forbidden_patterns": ["secretcorp"],
    }

    rc = rms.sync(cfg)

    assert rc == 1
    assert os.path.exists(rms.BLOCKED_PATH)
    blocked = open(rms.BLOCKED_PATH, encoding="utf-8").read()
    assert "leftover.md" in blocked
    assert "leftover-café.md" in blocked


@_requires_git
def test_mirror_managed_binary_file_is_blocked_then_allowed(tmp_path, sandbox, monkeypatch):
    """Managed x binary interaction: a mirror-managed binary can't be
    excluded from publish the way an exported one is (DESIGN point 4 says
    its content is never touched), so it needs an explicit "<unscannable>"
    forbidden_allow entry to publish at all."""
    branch = "main"
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    (src / "agents").mkdir()
    (src / "agents" / "a.md").write_text("clean\n")
    _git(src, "add", "agents")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = os.path.join(str(src), ".mirror")
    _patch_mirror_paths(monkeypatch, mirror_dir)

    logo_bytes = b"\x89PNG\x00\x01logo-bytes"
    bare = _init_bare_remote(tmp_path, branch=branch, seed_bytes={"logo.png": logo_bytes})

    base_cfg = {
        "remote_url": str(bare),
        "clone_dir": str(tmp_path / "clone"),
        "branch": branch,
        "include": ["agents", "logo.png"],
        "mirror_managed": ["logo.png"],
        "replacements": [],
        "forbidden_patterns": ["secretcorp"],
    }

    rc = rms.sync(dict(base_cfg))
    assert rc == 1
    assert os.path.exists(rms.BLOCKED_PATH)
    assert "logo.png" in open(rms.BLOCKED_PATH, encoding="utf-8").read()

    cfg2 = dict(base_cfg)
    cfg2["forbidden_allow"] = {"logo.png": ["<unscannable>"]}
    rc2 = rms.sync(cfg2)

    assert rc2 == 0
    assert not os.path.exists(rms.BLOCKED_PATH)
    assert _bare_path_exists_at(bare, branch, "logo.png")


# ===========================================================================
# --check / _locked_sync / main dispatch
# ===========================================================================


@_requires_git
class TestMainCheck:
    """--check is a health probe (module's own comment: "so a sweep/heartbeat
    can consume this without parsing the text"): rc 0 iff config valid AND
    mirror current AND no last_error AND not blocked; rc 1 otherwise."""

    def test_missing_config_is_unhealthy(self, tmp_path, sandbox, monkeypatch, capsys):
        _git(sandbox.claude, "init", "-q")
        (sandbox.claude / "f.txt").write_text("x")
        _git(sandbox.claude, "add", "f.txt")
        _git(sandbox.claude, "commit", "-q", "-m", "c")

        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        monkeypatch.setattr(rms, "load_config", lambda: None)

        rc = rms.main(["--check"])
        out = capsys.readouterr().out

        assert rc == 1
        assert "MISSING or invalid" in out
        assert "BEHIND runtime HEAD" in out
        assert "last error: none" in out
        assert "blocked: no" in out

    def test_valid_config_but_blocked_and_errored_is_unhealthy(
        self, tmp_path, sandbox, monkeypatch, capsys
    ):
        _git(sandbox.claude, "init", "-q")
        (sandbox.claude / "f.txt").write_text("x")
        _git(sandbox.claude, "add", "f.txt")
        _git(sandbox.claude, "commit", "-q", "-m", "c")
        head = _git(sandbox.claude, "rev-parse", "HEAD").stdout.strip()

        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        (mirror_dir / "last_synced_head").write_text(head + "\n")
        (mirror_dir / "last_error").write_text("2026-01-01T00:00:00Z boom\n")
        (mirror_dir / "BLOCKED.md").write_text("blocked\n")
        monkeypatch.setattr(rms, "load_config", lambda: _cfg())

        rc = rms.main(["--check"])
        out = capsys.readouterr().out

        # config valid AND current, but last_error/blocked still make this
        # UNHEALTHY -- a wedged mirror must never look healthy (DESIGN pt 5).
        assert rc == 1
        assert "config: valid" in out
        assert "[current]" in out
        assert "boom" in out
        assert "blocked: YES" in out

    def test_valid_config_current_no_error_not_blocked_is_healthy(
        self, tmp_path, sandbox, monkeypatch, capsys
    ):
        _git(sandbox.claude, "init", "-q")
        (sandbox.claude / "f.txt").write_text("x")
        _git(sandbox.claude, "add", "f.txt")
        _git(sandbox.claude, "commit", "-q", "-m", "c")
        head = _git(sandbox.claude, "rev-parse", "HEAD").stdout.strip()

        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        (mirror_dir / "last_synced_head").write_text(head + "\n")
        monkeypatch.setattr(rms, "load_config", lambda: _cfg())

        rc = rms.main(["--check"])
        out = capsys.readouterr().out

        assert rc == 0
        assert "config: valid" in out
        assert "[current]" in out
        assert "last error: none" in out
        assert "blocked: no" in out


class TestLockedSync:
    def test_skips_when_lock_already_held(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        monkeypatch.setattr(rms, "load_config", lambda: _cfg())
        sync_calls = []
        monkeypatch.setattr(rms, "sync", lambda cfg: sync_calls.append(cfg) or 0)

        import fcntl as _fcntl

        holder = open(rms.LOCK_PATH, "a+")
        _fcntl.flock(holder, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        try:
            rc = rms._locked_sync()
        finally:
            holder.close()

        assert rc == 0
        assert sync_calls == []  # never actually ran sync while contested

    def test_no_valid_config_is_a_noop(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)
        monkeypatch.setattr(rms, "load_config", lambda: None)
        sync_calls = []
        monkeypatch.setattr(rms, "sync", lambda cfg: sync_calls.append(cfg) or 0)

        assert rms._locked_sync() == 0
        assert sync_calls == []


class TestMainDispatch:
    def test_no_args_returns_2(self):
        assert rms.main([]) == 2

    def test_sync_flag_dispatches_to_locked_sync(self, monkeypatch):
        monkeypatch.setattr(rms, "_locked_sync", lambda: 0)
        assert rms.main(["--sync"]) == 0

    def test_sync_crash_surfaces_via_fail(self, tmp_path, monkeypatch):
        mirror_dir = tmp_path / ".mirror"
        _patch_mirror_paths(monkeypatch, mirror_dir)

        def boom():
            raise RuntimeError("kaboom")

        monkeypatch.setattr(rms, "_locked_sync", boom)

        rc = rms.main(["--sync"])

        assert rc == 1
        assert os.path.exists(rms.LAST_ERROR_PATH)


# ===========================================================================
# posttooluse_bash.py wiring — job 3 calls maybe_trigger(ev) unconditionally
# ===========================================================================


class TestPosttooluseWiring:
    def test_main_calls_maybe_trigger_with_the_event(self, sandbox, monkeypatch):
        import posttooluse_bash as ptb

        calls = []
        monkeypatch.setattr(
            ptb.runtime_mirror_sync, "maybe_trigger", lambda ev: calls.append(ev) or True
        )
        payload = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

        rc = ptb.main()

        assert rc == 0
        assert len(calls) == 1
        assert _lib.tool_name(calls[0]) == "Bash"
        assert _lib.bash_command(calls[0]) == "git push"

    def test_maybe_trigger_raising_does_not_prevent_main_returning_0(self, sandbox, monkeypatch):
        import posttooluse_bash as ptb

        def boom(ev):
            raise RuntimeError("sync trigger exploded")

        monkeypatch.setattr(ptb.runtime_mirror_sync, "maybe_trigger", boom)
        payload = {"tool_name": "Bash", "tool_input": {"command": "git push"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

        rc = ptb.main()

        assert rc == 0

    def test_maybe_trigger_runs_before_the_commit_keyed_logic(self, sandbox, monkeypatch):
        """Ordering per posttooluse_bash's own module docstring ("job 3" is
        listed, and read_event/maybe_trigger sit in main() right before the
        commit-keyed jobs 1-2): maybe_trigger fires first, should_release
        (which gates jobs 1-2) is consulted after -- for a push-only event
        (not also a commit) should_release still runs and correctly returns
        False on its own merits, so job order is observed via a shared
        call-order list rather than by forbidding should_release outright."""
        import posttooluse_bash as ptb

        order = []
        monkeypatch.setattr(
            ptb.runtime_mirror_sync,
            "maybe_trigger",
            lambda ev: order.append("maybe_trigger") or False,
        )
        real_should_release = ptb.should_release

        def spy_should_release(ev):
            order.append("should_release")
            return real_should_release(ev)

        monkeypatch.setattr(ptb, "should_release", spy_should_release)
        payload = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

        rc = ptb.main()

        assert rc == 0
        assert order == ["maybe_trigger", "should_release"]
