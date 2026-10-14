"""Hermetic tests for `runtime_mirror_sync.py --dry-run [--config PATH]`.

Spec source: the module's DESIGN point 7 and the `dry_run()` /
`_parse_dry_run_argv()` docstrings, plus the plan's D4 `--dry-run` bullet and
its rails (`plans/public_repo_grade_a_2026-10-12.md` §5 D4) -- NOT a snapshot
of current output. What the flag is FOR: the export gate is the only thing
standing between the runtime and the public mirror, and editing its redaction
map without a way to try it is editing blind. `--dry-run` runs the SAME
export -> redact -> gate stages as `--sync` into a throwaway temp dir and
reports; it publishes nothing and touches no mirror state.

The rails, each with its own test (a rail without a test is a promise):

  1. `--dry-run` and `--sync` are mutually exclusive (usage error, exit 2),
     decided before anything runs  -> TestArgumentRails
  2. `--config` is accepted ONLY together with `--dry-run`: the standing push
     authority stays bound to `.mirror/config.json`  -> TestArgumentRails
  3. the dry-run path never reaches the code that publishes  -> TestNeverPublishes
  4. it touches NO state (no last_synced_head, no sync.lock, no sync.log line,
     no BLOCKED.md / last_error, no clone mutation) and removes its temp dir
     -> TestTouchesNoState
  5. the report names forbidden hits by FILE and PATTERN only, replacements in
     quoted literals by file:line + count only -- never the matched text or a
     replacement value  -> TestReport / TestQuotedReplacements
  6. a dry run and a real `sync()` agree on what the gate blocks, because the
     stages are shared code, not a copy, and the dry run seeds its temp tree
     from the clone's INDEX (what `sync()` gates after its own
     `git checkout -- .` reset), never the working tree  -> TestParityWithSync
     / TestStagedFromIndex
  7. it never prints an exception's repr or message (they carry raw config
     bytes / the full unredacted text being written), only the type
     -> TestNoExceptionTextInReport
  8. it never says CLEAN about a gate that is not there (no/empty/misspelled
     `forbidden_patterns`) or about a stage that could not run
     -> TestGateMustExist / TestFailsClosed

`--status` / `--check` / `--sync` behaviour is unchanged: that is proven by the
neighbouring `test_mirror_sync_status.py` and `test_runtime_mirror_sync.py`
(which also exercise the shared `_export_and_redact` / `_gate` helpers through
`sync()`), not restated here.

Every git-touching test uses real, local, offline scratch repos under
`tmp_path`. Nothing here can reach the operator's real `~/.claude/.mirror/`:
the autouse `_isolated_mirror_paths` fixture repoints all seven of the module's
import-time path constants AND the `load_config()` default argument (a
function default is bound at import to the REAL config path, so a bare
`load_config()` -- which `_locked_sync()` makes -- would otherwise read the
operator's config whatever the constants say) under a throwaway dir, and
`TestHermeticity` asserts it.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
import time

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
    """Whole-file hermeticity: all seven path constants point under a
    throwaway dir BEFORE any test body runs (composes with the per-test
    `_patch_mirror_paths` call that picks the real fixture dir)."""
    _patch_mirror_paths(monkeypatch, tmp_path / ".default-mirror")


def _snapshot(root):
    """Every file under `root` (dotdirs and `.git` included): rel path ->
    (size, mtime_ns, sha256)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            st = os.lstat(full)
            digest = ""
            if os.path.isfile(full) and not os.path.islink(full):
                with open(full, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
            out[os.path.relpath(full, root)] = (st.st_size, st.st_mtime_ns, digest)
    return out


def _init_bare_remote(tmp_path, branch="main"):
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(bare)], check=True, capture_output=True, timeout=20
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


# ===========================================================================
# the world: a scratch runtime repo, a mirror dir, a real clone, a config
# ===========================================================================


class World:
    """A scratch runtime (git repo at the sandboxed `_lib.CLAUDE_DIR`), an
    isolated `.mirror/` dir, a real clone of a local bare "remote" under it,
    and config builders. `cfg_file()` writes GitHub-form remote URLs (what
    `validate_config` requires); `sync_cfg()` is the same config with the
    local bare path as remote, for driving a real `sync()` in parity tests."""

    def __init__(self, tmp_path, src, mirror_dir, bare, clone):
        self.tmp_path = tmp_path
        self.src = src
        self.mirror_dir = mirror_dir
        self.bare = bare
        self.clone = clone

    # -- runtime repo -------------------------------------------------------
    def head(self):
        return _git(self.src, "rev-parse", "HEAD").stdout.strip()

    def commit(self, rel, content):
        full = self.src / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            full.write_bytes(content)
        else:
            full.write_text(content)
        _git(self.src, "add", rel)
        _git(self.src, "commit", "-q", "-m", f"update {rel}")

    def stage_only(self, rel, content):
        full = self.src / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        _git(self.src, "add", rel)

    # -- clone --------------------------------------------------------------
    def commit_in_clone(self, rel, content):
        full = self.clone / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        _git(self.clone, "add", rel)
        _git(self.clone, "commit", "-q", "-m", f"clone {rel}")

    # -- config -------------------------------------------------------------
    def cfg(self, **overrides):
        base = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(self.clone),
            "branch": "main",
            "include": ["agents", "hooks", "README.md"],
            "mirror_managed": ["README.md"],
            "replacements": [["SecretCorp", "ExampleCo"]],
            "forbidden_patterns": ["secretcorp"],
        }
        base.update(overrides)
        return base

    def sync_cfg(self, **overrides):
        cfg = self.cfg(**overrides)
        cfg["remote_url"] = str(self.bare)
        return cfg

    def write_cfg(self, cfg=None, name="config.json", where=None):
        folder = self.mirror_dir if where is None else where
        path = folder / name
        path.write_text(json.dumps(self.cfg() if cfg is None else cfg))
        return str(path)

    # -- driving ------------------------------------------------------------
    def dry(self, capsys, *extra):
        rc = rms.main(["--dry-run", *extra])
        cap = capsys.readouterr()
        return rc, cap.out, cap.err


@pytest.fixture
def world(tmp_path, sandbox, monkeypatch):
    src = sandbox.claude
    _git(src, "init", "-q")
    _git(src, "symbolic-ref", "HEAD", "refs/heads/main")
    (src / "agents").mkdir(exist_ok=True)
    (src / "agents" / "a.md").write_text("Built for SecretCorp partners.\n")
    (src / "hooks").mkdir(exist_ok=True)
    (src / "hooks" / "h.txt").write_text("clean text file\n")
    _git(src, "add", "agents", "hooks")
    _git(src, "commit", "-q", "-m", "initial")

    mirror_dir = tmp_path / ".mirror"
    mirror_dir.mkdir()
    _patch_mirror_paths(monkeypatch, mirror_dir)

    bare = _init_bare_remote(tmp_path)
    clone = mirror_dir / "clone"
    _git(mirror_dir, "clone", "-q", "--branch", "main", str(bare), str(clone))

    w = World(tmp_path, src, mirror_dir, bare, clone)
    w.write_cfg()  # the standing .mirror/config.json
    return w


def _last_line(out):
    return out.strip().splitlines()[-1]


def _hits(out):
    """[(file, pattern)] from the 'forbidden-pattern hits' section."""
    lines = out.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("forbidden-pattern hits:"))
    found = []
    for ln in lines[start + 1:]:
        if not ln.startswith("  "):
            break
        if ln.startswith("  by pattern:") or ln.startswith("  ..."):
            continue
        rel, pat = ln.strip().split("  ", 1)
        found.append((rel, pat))
    return found


def _quoted(out):
    """{(file, line): count} from the 'quoted-string replacements' section."""
    found = {}
    for m in re.finditer(r"^  (\S+):(\d+)  x(\d+)  repl=(\S+)$", out, re.M):
        found[(m.group(1), int(m.group(2)))] = int(m.group(3))
    return found


def _blocked_hits(path):
    """[(file, pattern)] parsed from the module's own BLOCKED.md."""
    text = open(path, encoding="utf-8").read()
    return re.findall(r"^- `(.+?)` matched `(.+)`$", text, re.M)


# ===========================================================================
# rails 1 + 2: the argument rules, decided before anything runs
# ===========================================================================


@pytest.fixture
def tripwires(monkeypatch):
    """Every function that could do work or publish raises AND records the
    call, so a rail test can assert the usage error fired BEFORE any of it --
    recording matters because main() could otherwise swallow the raise."""
    calls = []

    def trip(name):
        def _t(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not run on a usage error")

        return _t

    for name in (
        "dry_run", "sync", "_locked_sync", "status", "load_config",
        "config_status", "_run", "_export_and_redact", "_gate",
    ):
        monkeypatch.setattr(rms, name, trip(name))
    monkeypatch.setattr(rms.subprocess, "Popen", trip("subprocess.Popen"))
    monkeypatch.setattr(tempfile, "mkdtemp", trip("tempfile.mkdtemp"))
    return calls


class TestArgumentRails:
    def _usage_error(self, capsys, argv):
        rc = rms.main(argv)
        cap = capsys.readouterr()
        return rc, cap.out, cap.err

    @pytest.mark.parametrize(
        "argv",
        [["--dry-run", "--sync"], ["--sync", "--dry-run"]],
        ids=["dry-run-first", "sync-first"],
    )
    def test_dry_run_and_sync_are_mutually_exclusive(self, tripwires, capsys, argv):
        """Rail 1: exit 2, in either order, with NOTHING having run -- not the
        sync, not the dry run, not a config read, not a git spawn."""
        rc, out, err = self._usage_error(capsys, argv)

        assert rc == 2
        # The exclusivity rule itself must fire -- exit 2 alone would also be
        # satisfied by the generic "unrecognised argument" fallback.
        assert "--dry-run cannot be combined with --sync" in err
        assert out == ""  # a usage error prints nothing on stdout
        assert tripwires == [], f"work ran before the usage error: {tripwires}"

    @pytest.mark.parametrize("flag", ["--status", "--check"])
    def test_dry_run_is_exclusive_with_every_other_mode(self, tripwires, capsys, flag):
        rc, _out, err = self._usage_error(capsys, ["--dry-run", flag])

        assert rc == 2
        assert f"--dry-run cannot be combined with {flag}" in err
        assert tripwires == []

    @pytest.mark.parametrize(
        "argv",
        [
            ["--config", "x.json"],
            ["--config=x.json"],
            ["--sync", "--config", "x.json"],
            ["--config", "x.json", "--sync"],
            ["--status", "--config", "x.json"],
            ["--check", "--config=x.json"],
        ],
    )
    def test_config_without_dry_run_is_a_usage_error(self, tripwires, capsys, argv):
        """Rail 2: the standing push authority is bound to .mirror/config.json
        -- `--config` must never reach --sync, --check or --status. The tripwire
        covers `_locked_sync` and `load_config`, the only things that could act
        on a re-pointed config."""
        rc, out, err = self._usage_error(capsys, argv)

        assert rc == 2
        assert "--config is accepted only together with --dry-run" in err
        assert out == ""
        assert tripwires == []

    @pytest.mark.parametrize(
        "argv,why",
        [
            (["--dry-run", "--config"], "needs a PATH"),
            (["--dry-run", "--config="], "needs a PATH"),
            (["--dry-run", "--config", "--dry-run"], "needs a PATH"),
            (["--dry-run", "--config", "a.json", "--config", "b.json"], "more than once"),
            (["--dry-run", "--config=a.json", "--config", "b.json"], "more than once"),
        ],
    )
    def test_malformed_config_flag_is_a_usage_error(self, tripwires, capsys, argv, why):
        rc, _out, err = self._usage_error(capsys, argv)

        assert rc == 2
        assert why in err
        assert tripwires == []

    @pytest.mark.parametrize(
        "argv", [["--dry-run", "bogus"], ["--dry-run", "--config", "a.json", "extra"]]
    )
    def test_unrecognised_argument_with_dry_run_is_a_usage_error(
        self, tripwires, capsys, argv
    ):
        rc, _out, err = self._usage_error(capsys, argv)

        assert rc == 2
        assert "unrecognised argument" in err
        assert tripwires == []

    # -- the paired recoveries: the right invocation works -------------------

    @_requires_git
    def test_plain_dry_run_is_accepted(self, world, capsys):
        rc, out, err = world.dry(capsys)

        assert (rc, err) == (0, "")
        assert _last_line(out) == "DRY-RUN CLEAN"

    @_requires_git
    @pytest.mark.parametrize("spelling", ["separate", "equals"])
    def test_dry_run_with_config_is_accepted_in_both_spellings(
        self, world, capsys, spelling
    ):
        cand = world.write_cfg(name="config.json.new")
        extra = ["--config", cand] if spelling == "separate" else [f"--config={cand}"]

        rc, out, err = world.dry(capsys, *extra)

        assert (rc, err) == (0, "")
        assert _last_line(out) == "DRY-RUN CLEAN"
        assert f"config:        {cand}" in out

    @_requires_git
    def test_after_a_usage_error_the_corrected_invocation_works_and_left_nothing(
        self, world, capsys, monkeypatch
    ):
        """Recoverability: a usage error leaves no residue behind it."""
        before = _snapshot(world.mirror_dir)
        reached = []

        def reached_sync(*args, **kwargs):
            reached.append("sync")
            raise AssertionError("--sync was reached from a usage error")

        with monkeypatch.context() as mp:  # scoped: the recovery step below needs the real ones
            mp.setattr(rms, "_locked_sync", reached_sync)
            mp.setattr(rms, "sync", reached_sync)
            assert rms.main(["--dry-run", "--sync"]) == 2
        capsys.readouterr()
        assert reached == []
        assert _snapshot(world.mirror_dir) == before

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"

    def test_usage_text_documents_the_new_flag(self, capsys):
        """`main([])` keeps its usage no-op (exit 2) and its text -- the module
        docstring -- now documents --dry-run and its --config rule."""
        assert rms.main([]) == 2
        shown = capsys.readouterr().out

        assert "--dry-run [--config PATH]" in shown
        assert "--config is valid only with --dry-run" in shown
        assert "--dry-run" in rms.__doc__ and "--config" in rms.__doc__

    @_requires_git
    def test_config_flag_never_repoints_the_standing_config_path(self, world, capsys):
        """The value of --config is read for this run only: the module's
        CONFIG_PATH (what --sync and the push trigger obey) is untouched, and
        the standing file is still what `load_config` returns afterwards."""
        standing = rms.CONFIG_PATH
        cand = world.write_cfg(world.cfg(include=["agents"]), name="cand.json")

        rc, _out, _err = world.dry(capsys, "--config", cand)

        assert rc == 0
        assert rms.CONFIG_PATH == standing
        assert rms.load_config(rms.CONFIG_PATH)["include"] == ["agents", "hooks", "README.md"]


# ===========================================================================
# rail 3: the dry-run path never reaches the code that publishes
# ===========================================================================


_PUBLISHERS = (
    "sync", "_locked_sync", "_write_state", "_clear_failure", "_fail", "_log",
    "_present_pathspecs",
)
_FORBIDDEN_GIT_VERBS = {
    "push", "fetch", "clone", "pull", "ls-remote", "remote", "commit", "add",
    "checkout", "reset", "restore", "stash", "gc", "prune", "init", "config",
    "branch", "merge", "rebase", "update-index", "rm", "mv",
}
_READ_ONLY_GIT_VERBS = {
    "ls-files", "rev-parse", "cat-file", "archive", "ls-tree", "checkout-index",
}


@_requires_git
class TestNeverPublishes:
    @pytest.fixture
    def publish_traps(self, monkeypatch):
        """Every function on the publish / state-write side of this module,
        recording AND raising. (There is no separately named publish function:
        the commit/push tail lives inside `sync()`, so `sync`, `_locked_sync`,
        and the helpers only the tail uses are the whole publish surface.)"""
        calls = []

        def trap(name):
            def _t(*args, **kwargs):
                calls.append(name)
                raise AssertionError(f"{name} reached from the dry-run path")

            return _t

        for name in _PUBLISHERS:
            monkeypatch.setattr(rms, name, trap(name))
        return calls

    def test_clean_dry_run_calls_no_publisher(self, world, capsys, publish_traps):
        rc, out, _err = world.dry(capsys)

        assert publish_traps == []
        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"

    def test_blocked_dry_run_calls_no_publisher(self, world, capsys, publish_traps):
        """A blocked REAL sync is where `_fail` / BLOCKED.md / last_error live;
        the dry run must reach none of them even when the gate hits."""
        world.commit("agents/b.md", "Internal: SecretVendor pricing.\n")
        cand = world.write_cfg(
            world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]), name="c.json"
        )

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert publish_traps == []
        assert rc == 1 and _last_line(out) == "DRY-RUN BLOCKED: 1 hit(s)"

    def test_failed_dry_run_calls_no_publisher(self, world, capsys, publish_traps, monkeypatch):
        monkeypatch.setattr(
            rms, "_export_and_redact", lambda *a, **k: ([], [], "git archive failed for agents")
        )

        rc, out, _err = world.dry(capsys)

        assert publish_traps == []
        assert rc == 1 and "DRY-RUN ERROR: git archive failed for agents" in out

    def test_only_read_only_git_and_a_temp_scoped_tar_are_spawned(
        self, world, capsys, monkeypatch
    ):
        """No git verb that writes, fetches or publishes is ever spawned, and
        the only `tar` extracts into the dry run's OWN temp dir -- never the
        clone, never the runtime."""
        spawned = []
        real_popen = subprocess.Popen
        made = []
        real_mkdtemp = tempfile.mkdtemp

        def rec_popen(args, **kwargs):
            spawned.append(list(args))
            return real_popen(args, **kwargs)

        def rec_mkdtemp(*a, **k):
            d = real_mkdtemp(*a, **k)
            made.append(os.path.realpath(d))
            return d

        monkeypatch.setattr(rms.subprocess, "Popen", rec_popen)
        monkeypatch.setattr(tempfile, "mkdtemp", rec_mkdtemp)

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert spawned and len(made) == 1
        saw_tar = False
        checkout_index_calls = []
        for argv in spawned:
            assert argv[0] in ("git", "tar"), f"unexpected spawn: {argv}"
            if argv[0] == "git":
                verbs = set(argv) & (_FORBIDDEN_GIT_VERBS | _READ_ONLY_GIT_VERBS)
                assert not (verbs & _FORBIDDEN_GIT_VERBS), f"writing git call: {argv}"
                assert verbs & _READ_ONLY_GIT_VERBS, f"unrecognised git call: {argv}"
                if "checkout-index" in argv:
                    checkout_index_calls.append(argv)
            else:
                saw_tar = True
                target = os.path.realpath(argv[argv.index("-C") + 1])
                assert target == made[0], f"tar extracted outside the temp dir: {argv}"
        assert saw_tar, "the export stage never ran"
        # `checkout-index` WRITES files -- it is read-only toward the clone only
        # because its --prefix points into the temp dir and it is not given -u
        # (refresh the index's stat data) or -f (overwrite).
        assert len(checkout_index_calls) == 1, spawned
        argv = checkout_index_calls[0]
        prefixes = [a for a in argv if a.startswith("--prefix=")]
        assert len(prefixes) == 1
        assert os.path.realpath(prefixes[0][len("--prefix="):]) == made[0]
        assert prefixes[0].endswith("/")
        assert not ({"-u", "--index", "-f", "--force"} & set(argv)), argv


# ===========================================================================
# rail 4: touches NO state
# ===========================================================================


def _set_state(world, kind):
    m = world.mirror_dir
    if kind == "never-synced":
        return
    if kind == "current":
        (m / "last_synced_head").write_text(world.head() + "\n")
    elif kind == "stale-with-error":
        (m / "last_synced_head").write_text("0" * 40 + "\n")
        (m / "last_error").write_text("2026-01-01T00:00:00Z earlier failure\n")
    elif kind == "blocked":
        (m / "BLOCKED.md").write_text("Source HEAD: deadbeef\n\n- `a` matched `b`\n")
    elif kind == "log-and-lock-present":
        (m / "sync.log").write_text("2026-01-01T00:00:00Z sync: earlier line\n")
        (m / "sync.lock").write_text("")
    else:  # pragma: no cover - guards a typo in a parametrize id
        raise AssertionError(kind)


@_requires_git
class TestTouchesNoState:
    @pytest.mark.parametrize(
        "kind",
        ["never-synced", "current", "stale-with-error", "blocked", "log-and-lock-present"],
    )
    @pytest.mark.parametrize("hit", [False, True], ids=["clean", "gate-hit"])
    def test_mirror_dir_and_clone_are_byte_and_mtime_identical_afterwards(
        self, world, capsys, kind, hit
    ):
        """Whole `.mirror/` -- the state files AND the clone including `.git`
        -- is identical (size, mtime, sha256) after, in every starting state,
        for a clean run and for one whose gate HITS (where a real sync would
        write BLOCKED.md and last_error)."""
        _set_state(world, kind)
        if hit:
            world.commit("agents/b.md", "Internal: SecretVendor pricing.\n")
            cfg = world.cfg(forbidden_patterns=["secretcorp", "secretvendor"])
            world.write_cfg(cfg)  # the standing config itself catches it
        before = _snapshot(world.mirror_dir)

        rc, out, _err = world.dry(capsys)

        assert rc == (1 if hit else 0)
        assert _last_line(out).startswith("DRY-RUN ")
        assert _snapshot(world.mirror_dir) == before

    def test_events_a_real_sync_would_log_are_not_logged(self, world, capsys):
        """The sync logs when it excludes a file, meets an include path absent
        at HEAD, or skips a malformed replacement entry. The dry run runs the
        same stages and hits all three -- and must still write no log line,
        and so must not conjure sync.log into existence."""
        world.commit("agents/logo.png", b"\x89PNG\x00\x01binary")
        world.write_cfg(
            world.cfg(
                include=["agents", "hooks", "README.md", "ghost"],
                replacements=[["SecretCorp", "ExampleCo"], ["malformed-entry"]],
            )
        )
        before = _snapshot(world.mirror_dir)

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        # all three sync-log events genuinely occurred, so the check below bites
        assert "agents/logo.png" in out and "1 malformed replacement entry" in out
        assert "\n  ghost\n" in out
        assert not os.path.exists(rms.LOG_PATH)
        assert _snapshot(world.mirror_dir) == before

    def test_a_gate_hit_writes_neither_blocked_md_nor_last_error_nor_log(
        self, world, capsys
    ):
        world.commit("agents/b.md", "Internal: SecretVendor pricing.\n")
        world.write_cfg(world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]))

        rc, _out, _err = world.dry(capsys)

        assert rc == 1
        for path in (
            rms.BLOCKED_PATH, rms.LAST_ERROR_PATH, rms.LOG_PATH, rms.LOCK_PATH, rms.STATE_PATH,
        ):
            assert not os.path.exists(path), f"dry run created {path}"

    def test_does_not_create_the_mirror_dir_when_it_is_absent(
        self, world, capsys, tmp_path, monkeypatch
    ):
        """A candidate config living OUTSIDE `.mirror/` whose clone_dir is
        under a `.mirror/` that does not exist: the run completes (without a
        clone) and conjures nothing."""
        absent = tmp_path / "no-such-mirror"
        _patch_mirror_paths(monkeypatch, absent)
        cand = world.write_cfg(
            world.cfg(clone_dir=str(absent / "clone")), name="cand.json", where=tmp_path
        )

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert not absent.exists()

    def test_runtime_repo_is_untouched(self, world, capsys):
        head, status = world.head(), _git(world.src, "status", "--porcelain").stdout

        rc, _out, _err = world.dry(capsys)

        assert rc == 0
        assert world.head() == head
        assert _git(world.src, "status", "--porcelain").stdout == status

    def test_clone_head_branch_and_worktree_are_untouched(self, world, capsys):
        world.commit_in_clone("extra/x.txt", "tracked outside the manifest\n")
        head = _git(world.clone, "rev-parse", "HEAD").stdout
        branch = _git(world.clone, "symbolic-ref", "--short", "HEAD").stdout
        before = _snapshot(world.clone)

        rc, _out, _err = world.dry(capsys)

        assert rc == 0
        assert _snapshot(world.clone) == before  # before any git call touches the index
        assert _git(world.clone, "rev-parse", "HEAD").stdout == head
        assert _git(world.clone, "symbolic-ref", "--short", "HEAD").stdout == branch
        assert _git(world.clone, "status", "--porcelain").stdout == ""

    # -- the temp dir is the only thing written, and it is always removed ----

    @pytest.fixture
    def made(self, monkeypatch):
        dirs = []
        real = tempfile.mkdtemp

        def rec(*a, **k):
            d = real(*a, **k)
            dirs.append(d)
            return d

        monkeypatch.setattr(tempfile, "mkdtemp", rec)
        return dirs

    def test_temp_dir_is_removed_after_a_clean_run(self, world, capsys, made):
        rc, _out, _err = world.dry(capsys)

        assert rc == 0 and len(made) == 1
        assert not os.path.exists(made[0])

    def test_temp_dir_is_removed_after_a_blocked_run(self, world, capsys, made):
        world.commit("agents/b.md", "Internal: SecretVendor pricing.\n")
        world.write_cfg(world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]))

        rc, _out, _err = world.dry(capsys)

        assert rc == 1 and len(made) == 1
        assert not os.path.exists(made[0])

    def test_temp_dir_is_removed_when_a_stage_crashes(self, world, capsys, made, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("stage exploded CRASH-MARKER-5150")

        monkeypatch.setattr(rms, "_gate", boom)

        rc, out, err = world.dry(capsys)

        assert rc == 1
        assert _last_line(out) == "DRY-RUN ERROR: crashed — RuntimeError"
        assert "CRASH-MARKER-5150" not in out + err  # type only, never the message
        assert "DRY-RUN CLEAN" not in out
        assert len(made) == 1 and not os.path.exists(made[0])

    def test_export_goes_to_the_temp_dir_not_the_clone(self, world, capsys, monkeypatch):
        seen = {}
        real = rms._export_and_redact

        def spy(src, dest, *a, **k):
            seen["dest"] = os.path.realpath(dest)
            return real(src, dest, *a, **k)

        monkeypatch.setattr(rms, "_export_and_redact", spy)

        rc, _out, _err = world.dry(capsys)

        assert rc == 0
        assert seen["dest"] != os.path.realpath(world.clone)
        assert not seen["dest"].startswith(os.path.realpath(world.clone) + os.sep)
        assert not (world.clone / "agents").exists()  # the export never reached the clone


# ===========================================================================
# fail-closed: a failed stage is never "clean"
# ===========================================================================


@_requires_git
class TestFailsClosed:
    @pytest.fixture
    def made(self, monkeypatch):
        dirs = []
        real = tempfile.mkdtemp

        def rec(*a, **k):
            d = real(*a, **k)
            dirs.append(d)
            return d

        monkeypatch.setattr(tempfile, "mkdtemp", rec)
        return dirs

    def test_missing_standing_config(self, world, capsys, made):
        os.remove(rms.CONFIG_PATH)

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert "DRY-RUN ERROR: config rejected — no config at" in out
        assert "DRY-RUN CLEAN" not in out
        assert made == []  # rejected before anything was staged

    def test_missing_candidate_config(self, world, capsys, made):
        rc, out, _err = world.dry(capsys, "--config", str(world.tmp_path / "nope.json"))

        assert rc == 1 and "no config at" in out and made == []

    @pytest.mark.parametrize(
        "override,reason",
        [
            ({"include": ["../escape"]}, "unsafe include entry"),
            ({"branch": "main;rm -rf /"}, "branch contains disallowed characters"),
            ({"remote_url": "ftp://example.com/x"}, "remote_url is not a well-formed"),
            ({"clone_dir": "/tmp/elsewhere"}, "clone_dir must resolve under"),
        ],
        ids=["include", "branch", "remote", "clone_dir"],
    )
    def test_invalid_candidate_config_is_rejected_by_the_same_validator(
        self, world, capsys, made, override, reason
    ):
        """`--config` does not widen what the module will act on: the candidate
        goes through the same `validate_config` (clone_dir still has to resolve
        under ~/.claude/.mirror/)."""
        cand = world.write_cfg(world.cfg(**override), name="bad.json")

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 1
        assert reason in out
        assert "DRY-RUN CLEAN" not in out
        assert made == []

    def test_unparseable_candidate_config(self, world, capsys):
        bad = world.mirror_dir / "bad.json"
        bad.write_text("{not json")

        rc, out, _err = world.dry(capsys, "--config", str(bad))

        assert rc == 1
        assert (
            "DRY-RUN ERROR: config rejected — config unreadable "
            "(JSONDecodeError at line 1 column 2)"
        ) in out

    def test_unresolvable_runtime_head(self, tmp_path, sandbox, monkeypatch, capsys, made):
        """A runtime that is not a git repo cannot be exported: error, not clean."""
        # keep git's upward repo discovery from escaping into a parent checkout
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        mirror_dir = tmp_path / ".mirror"
        mirror_dir.mkdir()
        _patch_mirror_paths(monkeypatch, mirror_dir)
        cfg = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(mirror_dir / "clone"),
            "branch": "main",
            "include": ["agents"],
            "forbidden_patterns": ["secretcorp"],
        }
        (mirror_dir / "config.json").write_text(json.dumps(cfg))

        rc = rms.main(["--dry-run"])
        out = capsys.readouterr().out

        assert rc == 1
        assert "DRY-RUN ERROR: cannot resolve ~/.claude HEAD" in out
        assert made == []

    def test_a_failing_export_stage_is_an_error(self, world, capsys, monkeypatch):
        monkeypatch.setattr(
            rms, "_export_and_redact", lambda *a, **k: ([], [], "tar extract failed for hooks")
        )

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert "DRY-RUN ERROR: tar extract failed for hooks" in out
        assert "DRY-RUN CLEAN" not in out

    def test_a_broken_clone_listing_is_an_error_not_a_silent_skip(
        self, world, capsys, monkeypatch
    ):
        monkeypatch.setattr(
            rms, "_tracked_paths", lambda clone: (set(), "git ls-files failed: boom")
        )

        rc, out, _err = world.dry(capsys)

        assert rc == 1 and "DRY-RUN ERROR: git ls-files failed: boom" in out


# ===========================================================================
# the report: hits by file + pattern only, verdict, exit code
# ===========================================================================


@_requires_git
class TestReport:
    def test_clean_report_shape_and_verdict(self, world, capsys):
        rc, out, _err = world.dry(capsys)

        lines = out.splitlines()
        assert rc == 0
        assert lines[0].startswith("DRY-RUN  runtime HEAD " + world.head()[:10])
        assert "nothing published" in lines[0]
        assert "forbidden-pattern hits: 0" in out
        assert "quoted-string replacements (.py/.sh/.mjs/.js/.cjs/.json): none" in out
        assert "include entries not in git ls-files: 0" in out
        assert lines[-1] == "DRY-RUN CLEAN"

    def test_export_summary_counts(self, world, capsys):
        rc, out, _err = world.dry(capsys)

        assert rc == 0
        assert "export:        2 publishable; vs clone: 2 new, 0 removed; 0 excluded" in out

    def test_forbidden_hit_is_named_by_file_and_pattern_and_blocks(self, world, capsys):
        world.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        world.write_cfg(world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]))

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert _hits(out) == [("agents/b.md", "secretvendor")]
        assert _last_line(out) == "DRY-RUN BLOCKED: 1 hit(s)"

    def test_matched_text_is_never_printed(self, world, capsys):
        """The pattern is lower-case, the text is not and is a longer sentence:
        neither the matched span nor its line may appear anywhere."""
        world.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        world.commit("agents/c.md", "id co-0123456789abcdef0123 leaked\n")
        world.write_cfg(
            world.cfg(forbidden_patterns=["secretcorp", "secretvendor", "co-[0-9a-f]{20}"])
        )

        rc, out, err = world.dry(capsys)

        assert rc == 1
        assert sorted(_hits(out)) == [
            ("agents/b.md", "secretvendor"),
            ("agents/c.md", "co-[0-9a-f]{20}"),
        ]
        for leaked in ("SecretVendor", "Internal use only", "0123456789abcdef0123", "pricing"):
            assert leaked not in out + err

    def test_replacement_values_and_old_text_are_never_printed(self, world, capsys):
        rc, out, err = world.dry(capsys)

        assert rc == 0
        assert "SecretCorp" not in out + err
        assert "ExampleCo" not in out + err

    def test_hit_count_is_the_number_of_violations(self, world, capsys):
        world.commit("agents/b.md", "SecretVendor one\n")
        world.commit("agents/c.md", "SecretVendor two\nand SecretOther\n")
        world.write_cfg(
            world.cfg(forbidden_patterns=["secretcorp", "secretvendor", "secretother"])
        )

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert sorted(_hits(out)) == [
            ("agents/b.md", "secretvendor"),
            ("agents/c.md", "secretother"),
            ("agents/c.md", "secretvendor"),
        ]
        assert _last_line(out) == "DRY-RUN BLOCKED: 3 hit(s)"
        assert "by pattern: secretvendor x2" in out

    def test_blocked_then_recovered_by_extending_the_replacement_map(self, world, capsys):
        """Paired recovery: the gate blocks an unredacted string, and the fix
        the report points at (extend the map) turns the SAME tree clean."""
        world.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        patterns = ["secretcorp", "secretvendor"]
        world.write_cfg(world.cfg(forbidden_patterns=patterns))
        rc, out, _err = world.dry(capsys)
        assert rc == 1 and _last_line(out) == "DRY-RUN BLOCKED: 1 hit(s)"

        world.write_cfg(
            world.cfg(
                forbidden_patterns=patterns,
                replacements=[["SecretCorp", "ExampleCo"], ["SecretVendor", "AcmeVendor"]],
            )
        )
        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert _hits(out) == []

    def test_candidate_config_is_judged_instead_of_the_standing_one(self, world, capsys):
        """`--config` is the whole point: try an edit before it replaces the
        standing file. Same tree, two configs, two verdicts."""
        world.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
        cand = world.write_cfg(
            world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]), name="cand.json"
        )

        rc_standing, out_standing, _ = world.dry(capsys)
        rc_cand, out_cand, _ = world.dry(capsys, "--config", cand)

        assert rc_standing == 0 and _last_line(out_standing) == "DRY-RUN CLEAN"
        assert rc_cand == 1 and _last_line(out_cand) == "DRY-RUN BLOCKED: 1 hit(s)"

    def test_mirror_managed_file_in_the_clone_is_gated(self, world, capsys):
        """Managed files publish too, so they are scanned (and, being managed,
        never redacted) -- exactly as `--sync` treats them."""
        world.commit_in_clone("README.md", "Maintained by SecretCorp.\n")

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert _hits(out) == [("README.md", "secretcorp")]

    def test_forbidden_allow_exempts_a_managed_file(self, world, capsys):
        world.commit_in_clone("README.md", "Maintained by SecretCorp.\n")
        world.write_cfg(world.cfg(forbidden_allow={"README.md": ["secretcorp"]}))

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"

    def test_file_tracked_in_the_clone_outside_the_manifest_is_gated(self, world, capsys):
        world.commit_in_clone("extra/x.txt", "SecretCorp left behind\n")

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert _hits(out) == [("extra/x.txt", "secretcorp")]

    def test_post_redaction_compile_break_is_a_hit(self, world, capsys):
        world.commit("agents/m.py", "value = SecretCorp\n")
        world.write_cfg(world.cfg(replacements=[["SecretCorp", ""]]))

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert _hits(out) == [("agents/m.py", "<post-redaction SyntaxError>")]

    def test_unscannable_files_are_excluded_and_listed_not_blocking(self, world, capsys):
        world.commit("agents/logo.png", b"\x89PNG\x00\x01binary")

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert "excluded from publish: 1" in out
        assert "  agents/logo.png  (binary/oversize)" in out

    def test_no_clone_is_a_visible_note_not_a_silent_gap(self, world, capsys):
        gone = world.mirror_dir / "other-clone"
        cand = world.write_cfg(world.cfg(clone_dir=str(gone)), name="cand.json")

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 0
        assert "note:" in out and "NOT scanned" in out
        assert not gone.exists()

    def test_malformed_replacement_entries_are_counted_never_printed(self, world, capsys):
        world.write_cfg(
            world.cfg(replacements=[["SecretCorp", "ExampleCo"], ["MALFORMED-MARKER-123"]])
        )

        rc, out, err = world.dry(capsys)

        assert rc == 0
        assert "1 malformed replacement entry skipped" in out
        assert "MALFORMED-MARKER-123" not in out + err

    # -- (c) include entries vs the runtime's git ls-files -------------------

    def test_include_entries_missing_from_git_ls_files_are_listed(self, world, capsys):
        world.write_cfg(world.cfg(include=["agents", "hooks", "README.md", "ghost", "ghost2/sub"]))

        rc, out, _err = world.dry(capsys)

        assert rc == 0  # a missing include path is a warning, not a gate hit
        assert "include entries not in git ls-files: 2" in out
        assert "\n  ghost\n" in out and "\n  ghost2/sub\n" in out

    def test_mirror_managed_entries_are_never_flagged_as_missing(self, world, capsys):
        """README.md is include + managed and is NOT tracked by the runtime
        (the mirror owns it): that is by design, so it is not reported."""
        rc, out, _err = world.dry(capsys)

        assert rc == 0
        assert "include entries not in git ls-files: 0" in out
        assert "README.md" not in out.split("include entries not in git ls-files")[1]

    def test_include_entry_staged_but_not_committed_is_called_out(self, world, capsys):
        """The export reads HEAD, so a staged-only include path silently
        exports nothing -- worth its own line."""
        world.stage_only("newdir/file.txt", "not committed yet\n")
        world.write_cfg(world.cfg(include=["agents", "hooks", "README.md", "newdir"]))

        rc, out, _err = world.dry(capsys)

        assert rc == 0
        assert "include entries not in git ls-files: 0" in out
        assert "tracked but absent at HEAD (the export skips them): 1" in out
        assert "\n  newdir\n" in out

    def test_a_present_include_entry_is_not_flagged(self, world, capsys):
        rc, out, _err = world.dry(capsys)

        assert "tracked but absent at HEAD (the export skips them): 0" in out
        assert rc == 0


# ===========================================================================
# (b): replacements that landed inside quoted string literals
# ===========================================================================

_Q_SH = """#!/bin/sh
A="/Users/real/x"
B='/Users/real/y'
C=/Users/real/z
# /Users/real/comment
echo "it's /Users/real and /Users/real/b"
echo ${#A} "/Users/real/q"
echo ok # "/Users/real/in-comment"
"""

_Q_PY = '''PATH = "/Users/real/a"
OTHER = '/Users/real/b'
# /Users/real/c
DOC = """first line
/Users/real/in-docstring
"""
BARE = 1  # /Users/real/e
RAW = f"{PATH}/Users/real"
'''

_Q_MJS = """const a = "/Users/real/a";
const b = `x ${a} /Users/real/b`;
// /Users/real/c
/* /Users/real/d */
const u = "http://example.com"; const p = "/Users/real/e";
const r = 1; // "/Users/real/f"
"""

_Q_JSON = '{"p": "/Users/real/a", "q": "/Users/real/b"}\n'

_Q_EXPECTED = {
    ("scripts/q.sh", 2): 1,
    ("scripts/q.sh", 3): 1,
    ("scripts/q.sh", 6): 2,
    ("scripts/q.sh", 7): 1,
    ("tools/q.py", 1): 1,
    ("tools/q.py", 2): 1,
    ("tools/q.py", 5): 1,
    ("tools/q.py", 8): 1,
    ("tools/q.mjs", 1): 1,
    ("tools/q.mjs", 2): 1,
    ("tools/q.mjs", 5): 1,
    ("tools/q.json", 1): 2,
}


@_requires_git
class TestQuotedReplacements:
    @pytest.fixture
    def quoted_world(self, world):
        world.commit("scripts/q.sh", _Q_SH)
        world.commit("tools/q.py", _Q_PY)
        world.commit("tools/q.mjs", _Q_MJS)
        world.commit("tools/q.json", _Q_JSON)
        world.commit("docs/q.md", "see /Users/real/md here\n")
        world.write_cfg(
            world.cfg(
                include=["agents", "hooks", "README.md", "scripts", "tools", "docs"],
                replacements=[["/Users/real", "~"], ["SecretCorp", "ExampleCo"]],
            )
        )
        return world

    def test_reports_exactly_the_replacements_inside_quoted_literals(
        self, quoted_world, capsys
    ):
        """Quoted (dq, sq, triple, template, JSON value) are reported with
        their line and count; bare words, `#` / `//` / `/* */` comments, a
        `${#x}` and an apostrophe inside a double-quoted string are handled as
        the shell/JS/Python grammar says; markdown is never scanned."""
        rc, out, _err = quoted_world.dry(capsys)

        assert _quoted(out) == _Q_EXPECTED
        assert "quoted-string replacements (.py/.sh/.mjs/.js/.cjs/.json): 14 in 4 file(s)" in out
        assert not any(rel.endswith(".md") for rel, _ in _quoted(out))
        assert rc == 0, out  # a warning is not a gate hit

    def test_each_line_names_the_replacement_index_not_its_text(self, quoted_world, capsys):
        _rc, out, _err = quoted_world.dry(capsys)

        assert "  scripts/q.sh:6  x2  repl=#0" in out

    def test_neither_the_old_text_nor_the_new_value_is_printed(self, quoted_world, capsys):
        _rc, out, err = quoted_world.dry(capsys)

        assert "/Users/real" not in out + err
        assert "in-docstring" not in out + err

    def test_two_pairs_on_one_line_are_both_indexed(self, world, capsys):
        world.commit("scripts/two.sh", 'X="/Users/aaa/p /Users/bbb/q"\n')
        world.write_cfg(
            world.cfg(
                include=["agents", "hooks", "README.md", "scripts"],
                replacements=[["/Users/aaa", "~"], ["/Users/bbb", "~"], ["SecretCorp", "ExampleCo"]],
            )
        )

        _rc, out, _err = world.dry(capsys)

        assert "  scripts/two.sh:1  x2  repl=#0,#1" in out

    def test_unquoted_replacement_in_a_script_is_not_reported(self, world, capsys):
        world.commit("scripts/bare.sh", "cd /Users/real/dir\n")
        world.write_cfg(
            world.cfg(
                include=["agents", "hooks", "README.md", "scripts"],
                replacements=[["/Users/real", "~"], ["SecretCorp", "ExampleCo"]],
            )
        )

        rc, out, _err = world.dry(capsys)

        assert rc == 0
        assert "quoted-string replacements (.py/.sh/.mjs/.js/.cjs/.json): none" in out


class TestQuotedSpanScanner:
    """The heuristic scanner behind (b), on its own. Advisory: it must never
    raise, whatever it is fed."""

    @staticmethod
    def _spans(text, lang):
        return [text[a:b] for a, b in rms._quoted_spans(text, lang)]

    def test_python_strings_escapes_comments_and_triple_quotes(self):
        text = 'x = "a\\"b" + \'c\'  # "not this"\nv = """a\nb"""\nw = 1\n'
        assert self._spans(text, "py") == ['"a\\"b"', "'c'", '"""a\nb"""']

    def test_python_unterminated_single_line_string_ends_with_its_line(self):
        assert self._spans('x = "abc\ny = "def"\n', "py") == ['"abc', '"def"']

    def test_python_quote_inside_a_comment_does_not_open_a_string(self):
        assert self._spans("# don't do this\ns = 'ok'\n", "py") == ["'ok'"]

    def test_shell_quotes_comments_and_dollar_hash(self):
        text = "echo \"it's\" 'a b' # 'ignored'\nx=${#y} \"z\"\nn=$#; echo \"q\"\n"
        assert self._spans(text, "sh") == ['"it\'s"', "'a b'", '"z"', '"q"']

    def test_shell_single_quotes_take_a_backslash_literally(self):
        assert self._spans("echo 'a\\' \"b\"\n", "sh") == ["'a\\'", '"b"']

    def test_javascript_url_in_string_is_not_a_comment(self):
        text = 'a = "http://x"; // "c"\nb = `t\nu`; /* "d" */ c = \'e\'\n'
        assert self._spans(text, "js") == ['"http://x"', "`t\nu`", "'e'"]

    def test_json_strings(self):
        assert self._spans('{"a": "b\\"c", "n": 1}', "json") == ['"a"', '"b\\"c"', '"n"']

    @pytest.mark.parametrize("lang", ["py", "sh", "js", "json"])
    @pytest.mark.parametrize(
        "text",
        [
            "",
            '"' * 50,
            "'" * 51,
            '"""' * 7,
            "'''" * 5,
            "`" * 9,
            "\\",
            '"\\',
            "/*",
            "//",
            "#",
            "a\n" * 200,
            '"unterminated\n' * 30,
            "$#" * 40,
            "\x00\x01\"\x02'\x03",
        ],
    )
    def test_never_raises_and_spans_are_ordered_disjoint_and_in_range(self, lang, text):
        spans = rms._quoted_spans(text, lang)

        last_end = 0
        for start, end in spans:
            assert last_end <= start < end <= len(text)
            last_end = end


# ===========================================================================
# apply_replacements: the two optional parameters the dry run needs
# ===========================================================================


class TestApplyReplacementsHooks:
    def test_on_apply_sees_the_text_before_each_pair_in_order(self):
        seen = []

        out = rms.apply_replacements(
            "aXb", [["X", "Y"], ["Y", "Z"]],
            on_apply=lambda i, old, new, text: seen.append((i, old, new, text)),
        )

        assert out == "aZb"
        assert seen == [(0, "X", "Y", "aXb"), (1, "Y", "Z", "aYb")]

    def test_malformed_entry_goes_to_the_injected_log_and_skips_on_apply(self):
        logged, seen = [], []

        out = rms.apply_replacements(
            "aXb", [["X"], ["X", "Y"]], log=logged.append,
            on_apply=lambda i, old, new, text: seen.append(i),
        )

        assert out == "aYb"
        assert len(logged) == 1 and "malformed replacement entry skipped" in logged[0]
        assert seen == [1]  # indexes are positions in the CONFIG list

    def test_injected_log_keeps_the_sync_log_untouched(self):
        rms.apply_replacements("a", [["bad"]], log=lambda m: None)

        assert not os.path.exists(rms.LOG_PATH)

    def test_default_still_logs_to_the_sync_log(self):
        rms.apply_replacements("a", [["bad"]])

        assert "malformed replacement entry skipped" in open(rms.LOG_PATH, encoding="utf-8").read()


# ===========================================================================
# rail 6: a dry run and a real sync agree (the stages are shared code)
# ===========================================================================


def _scn_clean(world):
    return {}


def _scn_survivor(world):
    world.commit("agents/b.md", "Internal use only: SecretVendor pricing.\n")
    return {"forbidden_patterns": ["secretcorp", "secretvendor"]}


def _scn_managed(world):
    world.commit_in_clone("README.md", "Maintained by SecretCorp.\n")
    return {}


def _scn_outside_manifest(world):
    world.commit_in_clone("extra/x.txt", "SecretCorp left behind\n")
    return {}


def _scn_compile_break(world):
    world.commit("agents/m.py", "value = SecretCorp\n")
    return {"replacements": [["SecretCorp", ""]]}


def _scn_binary_excluded(world):
    world.commit("agents/logo.png", b"\x89PNG\x00\x01binary")
    return {}


def _scn_allow_listed(world):
    world.commit_in_clone("README.md", "Maintained by SecretCorp.\n")
    return {"forbidden_allow": {"README.md": ["secretcorp"]}}


def _scn_dirty_worktree_edit(world):
    """A tracked file whose INDEX content is forbidden but whose working-tree
    copy was edited clean (uncommitted): `sync()` resets the working tree to
    the index first, so it blocks -- a dry run reading the working tree would
    say clean."""
    world.commit_in_clone("extra/x.txt", "SecretCorp left behind\n")
    (world.clone / "extra" / "x.txt").write_text("looks clean in the worktree\n")
    return {}


def _scn_tracked_file_deleted_from_worktree(world):
    world.commit_in_clone("extra/x.txt", "SecretCorp left behind\n")
    os.remove(world.clone / "extra" / "x.txt")
    return {}


def _scn_gitlink(world):
    """A gitlink (submodule) entry in the clone's index: `sync()` gates its
    path (an unreadable directory => blocked), so the dry run must too."""
    sha = world.head()
    _git(world.clone, "update-index", "--add", "--cacheinfo", f"160000,{sha},sub")
    _git(world.clone, "commit", "-q", "-m", "gitlink")
    return {}


@_requires_git
class TestParityWithSync:
    @pytest.mark.parametrize(
        "scenario",
        [
            _scn_clean, _scn_survivor, _scn_managed, _scn_outside_manifest,
            _scn_compile_break, _scn_binary_excluded, _scn_allow_listed,
            _scn_dirty_worktree_edit, _scn_tracked_file_deleted_from_worktree,
            _scn_gitlink,
        ],
        ids=lambda f: f.__name__[len("_scn_"):],
    )
    def test_dry_run_blocks_exactly_what_a_real_sync_blocks(self, world, capsys, scenario):
        """The same tree, judged twice: by `--dry-run` and by the real
        `sync()`. Same verdict, and the same (file, pattern) set as the
        BLOCKED.md the real sync writes -- which is only guaranteed because
        both run the one shared export/redact/gate implementation."""
        overrides = scenario(world)
        world.write_cfg(world.cfg(**overrides))

        rc, out, _err = world.dry(capsys)
        sync_rc = rms.sync(world.sync_cfg(**overrides))

        assert sync_rc == (1 if rc else 0)
        if rc:
            assert os.path.exists(rms.BLOCKED_PATH)
            assert sorted(_hits(out)) == sorted(_blocked_hits(rms.BLOCKED_PATH))
            assert f"DRY-RUN BLOCKED: {len(_hits(out))} hit(s)" == _last_line(out)
        else:
            assert not os.path.exists(rms.BLOCKED_PATH)
            assert _last_line(out) == "DRY-RUN CLEAN"

    def test_blocked_sync_then_manifest_shrink_matches_sync(self, world, capsys):
        """The divergence a working-tree dry run had: a BLOCKED sync leaves its
        export in the clone's working tree; shrinking `include` afterwards
        means that stale export is no longer overwritten. `sync()` resets the
        working tree to the index (the last PUBLISHED content) before gating,
        so it still sees what was published; the dry run must too."""
        world.commit("old/x.txt", "Contains SecretVendor\n")
        base = {
            "include": ["agents", "hooks", "old"],
            "mirror_managed": [],
            "replacements": [["SecretCorp", "ExampleCo"]],
            "forbidden_patterns": ["secretcorp"],
        }
        assert rms.sync(world.sync_cfg(**base)) == 0  # publishes old/x.txt with the vendor name

        world.commit("old/x.txt", "clean now\n")
        world.commit("agents/b.md", "SecretOther\n")
        blocking = dict(base, forbidden_patterns=["secretcorp", "secretother"])
        assert rms.sync(world.sync_cfg(**blocking)) == 1  # blocks on agents/b.md
        stale = (world.clone / "old" / "x.txt").read_text()
        assert stale == "clean now\n", "setup: the blocked sync must leave its export behind"

        shrunk = dict(
            base,
            include=["agents", "hooks"],  # `old` leaves the manifest
            replacements=[["SecretCorp", "ExampleCo"], ["SecretOther", "Fine"]],
            forbidden_patterns=["secretcorp", "secretother", "secretvendor"],
        )
        world.write_cfg(world.cfg(**shrunk))

        rc, out, _err = world.dry(capsys)
        os.remove(rms.BLOCKED_PATH)  # judge the second sync on its own
        sync_rc = rms.sync(world.sync_cfg(**shrunk))

        assert sync_rc == 1 and rc == 1
        assert _hits(out) == [("old/x.txt", "secretvendor")]
        assert sorted(_hits(out)) == sorted(_blocked_hits(rms.BLOCKED_PATH))
        assert _last_line(out) == "DRY-RUN BLOCKED: 1 hit(s)"

    def test_dry_run_leaves_a_state_where_a_real_sync_still_works(self, world, capsys):
        """Recoverability: a dry run does not poison the later real run -- the
        sync that follows publishes normally and records state."""
        rc, out, _err = world.dry(capsys)
        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"

        assert rms.sync(world.sync_cfg()) == 0

        assert open(rms.STATE_PATH, encoding="utf-8").read().strip() == world.head()
        tip = _git(world.bare, "show", "main:agents/a.md").stdout
        assert "ExampleCo" in tip and "SecretCorp" not in tip


@pytest.fixture
def made_dirs(monkeypatch):
    """Every directory `tempfile.mkdtemp` hands out during the test."""
    dirs = []
    real = tempfile.mkdtemp

    def rec(*a, **k):
        d = real(*a, **k)
        dirs.append(d)
        return d

    monkeypatch.setattr(tempfile, "mkdtemp", rec)
    return dirs


# ===========================================================================
# rail 7: no exception text in the report -- only the type
# ===========================================================================


@_requires_git
class TestNoExceptionTextInReport:
    """`repr(exc)` of a UnicodeDecodeError carries the raw bytes it choked on
    and of a UnicodeEncodeError the full text being encoded: for a config or a
    file mid-redaction that is replacement values / UNREDACTED text, and this
    report goes to a terminal and a model's context. Each test plants a unique
    marker where the exception would carry it."""

    def test_invalid_utf8_candidate_config_reports_the_type_only(self, world, capsys):
        marker = "CFG-MARKER-REPLACEMENT-VALUE-7731"
        body = json.dumps(world.cfg(replacements=[["SecretCorp", marker]])).encode()
        bad = world.mirror_dir / "bad.json"
        bad.write_bytes(body[:-1] + b"\xff}")  # one byte that is not UTF-8

        rc, out, err = world.dry(capsys, "--config", str(bad))

        assert rc == 1
        assert _last_line(out) == (
            "DRY-RUN ERROR: config rejected — config unreadable (UnicodeDecodeError)"
        )
        assert marker not in out + err

    def test_lone_surrogate_replacement_reports_the_type_only(self, world, capsys):
        """A replacement value that cannot be encoded fails the WRITE of the
        redacted file; the UnicodeEncodeError's repr is that file's full,
        unredacted-around-the-edges text."""
        marker = "UNREDACTED-MARKER-4242"
        world.commit("agents/a.md", f"Built for SecretCorp. {marker}\n")
        cand = world.write_cfg(
            world.cfg(replacements=[["SecretCorp", "X\ud800"]]), name="cand.json"
        )

        rc, out, err = world.dry(capsys, "--config", cand)

        assert rc == 1
        assert _last_line(out) == (
            "DRY-RUN ERROR: redaction failed for agents/a.md (UnicodeEncodeError)"
        )
        assert marker not in out + err

    def test_safe_errors_is_what_changes_the_message_and_sync_keeps_its_own(
        self, world, tmp_path
    ):
        """Paired: the flag turns repr into type-only, and its absence (what
        `sync()` passes) keeps `sync()`'s message exactly as it was."""
        world.commit("agents/a.md", "Built for SecretCorp.\n")
        pairs = [["SecretCorp", "X\ud800"]]

        def failure(safe, name):
            dest = tmp_path / name
            dest.mkdir()
            return rms._export_and_redact(
                str(world.src), str(dest), ["agents"], set(), pairs, safe_errors=safe
            )[2]

        assert failure(True, "safe") == "redaction failed for agents/a.md (UnicodeEncodeError)"
        unsafe = failure(False, "unsafe")
        assert unsafe.startswith("redaction failed for agents/a.md: UnicodeEncodeError(")

    def test_json_syntax_error_keeps_its_position_but_not_its_text(self, world, capsys):
        marker = "SYNTAX-MARKER-8802"
        bad = world.mirror_dir / "bad.json"
        bad.write_text('{"replacements": [["a", "' + marker + '"], oops')

        rc, out, err = world.dry(capsys, "--config", str(bad))

        assert rc == 1
        assert "config unreadable (JSONDecodeError at line 1 column" in out
        assert marker not in out + err

    def test_a_valid_config_is_still_read_normally(self, world, capsys):
        """Recoverability: the safe-error path only changes failures."""
        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"


# ===========================================================================
# rail 8: a gate that is not there is an error, never a clean
# ===========================================================================


@_requires_git
class TestGateMustExist:
    NO_GATE = "DRY-RUN ERROR: no forbidden_patterns configured"

    @staticmethod
    def _without(cfg, key):
        cfg = dict(cfg)
        cfg.pop(key)
        return cfg

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda w: TestGateMustExist._without(w.cfg(), "forbidden_patterns"),
            lambda w: w.cfg(forbidden_patterns=[]),
            lambda w: w.cfg(forbidden_patterns=None),
            lambda w: w.cfg(forbidden_patterns="secretcorp"),
            lambda w: w.cfg(forbidden_patterns={"secretcorp": 1}),
            lambda w: w.cfg(forbidden_patterns=["secretcorp", 7]),
        ],
        ids=["missing", "empty", "null", "bare-string", "object", "non-string-item"],
    )
    def test_missing_empty_or_malformed_patterns_exit_1_not_clean(
        self, world, capsys, made_dirs, mutate
    ):
        cand = world.write_cfg(mutate(world), name="cand.json")

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 1
        assert _last_line(out) == self.NO_GATE
        assert "DRY-RUN CLEAN" not in out
        assert made_dirs == []  # refused before anything was staged

    def test_misspelled_key_is_named(self, world, capsys):
        cfg = self._without(world.cfg(), "forbidden_patterns")
        cfg["forbiden_patterns"] = ["secretcorp"]  # the typo that disables the gate
        cand = world.write_cfg(cfg, name="cand.json")

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 1
        assert "unknown config key(s), ignored: 'forbiden_patterns'" in out
        assert _last_line(out) == self.NO_GATE

    def test_unknown_keys_are_listed_by_name_and_do_not_block_a_real_gate(
        self, world, capsys
    ):
        cand = world.write_cfg(
            world.cfg(replacments=[["a", "b"]], comment="x"), name="cand.json"
        )

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert "unknown config key(s), ignored: 'comment', 'replacments'" in out

    def test_a_known_key_set_produces_no_unknown_key_note(self, world, capsys):
        rc, out, _err = world.dry(capsys)

        assert rc == 0 and "unknown config key" not in out

    @pytest.mark.parametrize(
        "override,why",
        [
            ({"replacements": "SecretCorp"}, "replacements must be a list"),
            ({"forbidden_allow": ["README.md"]}, "forbidden_allow must be an object"),
        ],
        ids=["replacements", "forbidden_allow"],
    )
    def test_mistyped_companion_keys_are_errors_not_crashes(
        self, world, capsys, override, why
    ):
        cand = world.write_cfg(world.cfg(**override), name="cand.json")

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 1 and _last_line(out) == f"DRY-RUN ERROR: {why}"

    def test_gate_line_shows_what_is_actually_in_force(self, world, capsys):
        cand = world.write_cfg(
            world.cfg(
                forbidden_patterns=["secretcorp", "secretvendor", "co-[0-9a-f]{20}"],
                replacements=[["SecretCorp", "ExampleCo"], ["a", "b"], ["bad"]],
                forbidden_allow={"README.md": ["secretcorp"], "x.txt": ["secretvendor"]},
            ),
            name="cand.json",
        )

        rc, out, _err = world.dry(capsys, "--config", cand)

        assert rc == 0
        assert "gate:          3 patterns, 2 replacement pairs, 2 allow entries" in out
        assert "1 malformed replacement entry skipped" in out  # malformed != a pair

    def test_gate_line_for_the_default_world(self, world, capsys):
        rc, out, _err = world.dry(capsys)

        assert rc == 0
        assert "gate:          1 patterns, 1 replacement pairs, 0 allow entries" in out

    def test_recovery_fixing_the_key_turns_the_same_tree_clean(self, world, capsys):
        """Paired recovery: a real pattern list restores the normal verdict."""
        broken = world.write_cfg(world.cfg(forbidden_patterns=[]), name="broken.json")
        fixed = world.write_cfg(world.cfg(), name="fixed.json")

        rc_bad, out_bad, _ = world.dry(capsys, "--config", broken)
        rc_ok, out_ok, _ = world.dry(capsys, "--config", fixed)

        assert rc_bad == 1 and _last_line(out_bad) == self.NO_GATE
        assert rc_ok == 0 and _last_line(out_ok) == "DRY-RUN CLEAN"


# ===========================================================================
# finding 6 -- a stage that could not run is an error, never clean
# ===========================================================================


@_requires_git
class TestIncludeMembershipFailure:
    def test_unreadable_membership_listing_is_an_error_not_clean(self, world, capsys, monkeypatch):
        monkeypatch.setattr(rms, "_git_paths", lambda *a, **k: None)

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert "include entries not in git ls-files: UNAVAILABLE (git failed)" in out
        assert _last_line(out) == "DRY-RUN ERROR: include membership unavailable"
        assert "DRY-RUN CLEAN" not in out

    def test_one_of_the_two_listings_failing_is_enough(self, world, capsys, monkeypatch):
        real = rms._git_paths
        calls = []

        def flaky(src, *args):
            calls.append(args[0])
            return None if args[0] == "ls-tree" else real(src, *args)

        monkeypatch.setattr(rms, "_git_paths", flaky)

        rc, out, _err = world.dry(capsys)

        assert calls == ["ls-files", "ls-tree"]
        assert rc == 1 and _last_line(out) == "DRY-RUN ERROR: include membership unavailable"

    def test_the_error_does_not_hide_gate_hits_that_were_found(self, world, capsys, monkeypatch):
        world.commit("agents/b.md", "SecretVendor\n")
        world.write_cfg(world.cfg(forbidden_patterns=["secretcorp", "secretvendor"]))
        monkeypatch.setattr(rms, "_git_paths", lambda *a, **k: None)

        rc, out, _err = world.dry(capsys)

        assert rc == 1
        assert _hits(out) == [("agents/b.md", "secretvendor")]
        assert _last_line(out) == "DRY-RUN ERROR: include membership unavailable"

    def test_working_listings_keep_the_normal_verdict(self, world, capsys):
        """Paired recovery."""
        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"


# ===========================================================================
# finding 3 -- the temp tree is seeded from the clone's INDEX, never its worktree
# ===========================================================================


@_requires_git
class TestStagedFromIndex:
    def test_index_file_is_byte_and_mtime_identical_even_with_a_dirty_worktree(
        self, world, capsys
    ):
        """A command that refreshes stat data (`checkout-index -u`, `git
        status`) would rewrite `.git/index`; a dirty working tree is exactly
        when it would have something to refresh."""
        world.commit_in_clone("extra/x.txt", "tracked\n")
        world.commit_in_clone("extra/touched.txt", "same bytes\n")
        (world.clone / "extra" / "x.txt").write_text("edited after the commit\n")
        # identical content, fresh mtime: stat-dirty but not content-dirty, which
        # is precisely what makes `git status` / `update-index --refresh` REWRITE
        # the index -- so a dry run that refreshed it cannot pass unnoticed
        time.sleep(0.05)
        (world.clone / "extra" / "touched.txt").write_text("same bytes\n")
        os.remove(world.clone / "README.md")
        index = world.clone / ".git" / "index"
        before = (index.stat().st_mtime_ns, index.stat().st_size, index.read_bytes())

        rc, _out, _err = world.dry(capsys)

        after = (index.stat().st_mtime_ns, index.stat().st_size, index.read_bytes())
        assert rc == 0
        assert after == before

    def test_dirty_worktree_itself_is_left_exactly_as_found(self, world, capsys):
        world.commit_in_clone("extra/x.txt", "tracked\n")
        (world.clone / "extra" / "x.txt").write_text("edited after the commit\n")
        os.remove(world.clone / "README.md")
        status = _git(world.clone, "status", "--porcelain").stdout

        rc, _out, _err = world.dry(capsys)

        assert rc == 0
        assert _git(world.clone, "status", "--porcelain").stdout == status
        assert (world.clone / "extra" / "x.txt").read_text() == "edited after the commit\n"
        assert not (world.clone / "README.md").exists()

    def test_a_clean_index_with_a_forbidden_looking_worktree_is_judged_by_the_index(
        self, world, capsys
    ):
        """The mirror image of the hidden-hit case: forbidden text that exists
        only in the (to-be-reset) working tree is not what `sync()` publishes,
        so it must not be reported either."""
        (world.clone / "README.md").write_text("uncommitted SecretCorp scribble\n")

        rc, out, _err = world.dry(capsys)
        sync_rc = rms.sync(world.sync_cfg())

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert sync_rc == 0


# ===========================================================================
# finding 5 -- nothing new on the per-Bash-call import chain
# ===========================================================================


class TestImportTime:
    def test_importing_the_module_pulls_in_none_of_the_dry_run_only_stdlib(self, tmp_path):
        """`posttooluse_bash.py` imports this module on every Bash tool call, and
        the module's own rule is no import-time work for a feature that only
        `--dry-run` uses. `_lib` is imported first as the baseline, so only what
        THIS module adds is judged."""
        code = (
            "import sys\n"
            f"sys.path.insert(0, {os.path.dirname(rms.__file__)!r})\n"
            "import _lib\n"
            "before = set(sys.modules)\n"
            "import runtime_mirror_sync\n"
            "added = set(sys.modules) - before\n"
            "bad = sorted({'tempfile', 'bisect', 'typing'} & added)\n"
            "print(','.join(bad))\n"
        )
        env = dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")

        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
            env=env, cwd=str(tmp_path),
        )

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "", f"import pulled in: {proc.stdout.strip()}"

    @_requires_git
    def test_the_lazily_imported_pieces_still_work_when_dry_run_runs(self, world, capsys):
        """Paired: laziness must not break the feature that needs them."""
        world.commit("scripts/q.sh", 'A="/Users/real/x"\n')
        world.write_cfg(
            world.cfg(
                include=["agents", "hooks", "README.md", "scripts"],
                replacements=[["/Users/real", "~"], ["SecretCorp", "ExampleCo"]],
            )
        )

        rc, out, _err = world.dry(capsys)

        assert rc == 0 and _last_line(out) == "DRY-RUN CLEAN"
        assert _quoted(out) == {("scripts/q.sh", 1): 1}  # the lazy `bisect` path ran


# ===========================================================================
# finding 4 -- hermeticity: the "cannot reach the real ~/.claude/.mirror" claim
# ===========================================================================


class TestHermeticity:
    PATH_NAMES = (
        "MIRROR_DIR", "CONFIG_PATH", "STATE_PATH", "LOCK_PATH", "LOG_PATH",
        "BLOCKED_PATH", "LAST_ERROR_PATH",
    )

    def test_every_module_path_and_the_load_config_default_sit_inside_tmp(self, tmp_path):
        root = str(tmp_path)
        for name in self.PATH_NAMES:
            assert getattr(rms, name).startswith(root), f"{name} escapes the sandbox"
        defaults = rms.load_config.__defaults__
        assert defaults == (rms.CONFIG_PATH,)
        assert defaults[0].startswith(root), "load_config's default path is the REAL config"

    @_requires_git
    def test_a_bare_load_config_reads_the_fixture_config_not_the_real_one(self, world):
        """`_locked_sync()` calls `load_config()` bare. With the default still
        bound to the real config, a regression letting `--sync` through would
        have run a real sync against the operator's mirror."""
        cfg = rms.load_config()

        assert cfg is not None
        assert cfg["clone_dir"].startswith(os.path.realpath(str(world.tmp_path)))
        assert cfg["include"] == ["agents", "hooks", "README.md"]

    @_requires_git
    def test_the_runtime_dir_is_the_sandbox_for_world_tests(self, world, tmp_path):
        assert rms._lib.CLAUDE_DIR.startswith(str(tmp_path))
        assert str(world.src).startswith(str(tmp_path))

    @_requires_git
    def test_a_sync_reached_by_mistake_could_only_touch_the_sandbox(self, world, monkeypatch):
        """What the first two tests buy: even `_locked_sync()` itself, run
        against this fixture, reads the sandbox config and writes only under
        the sandbox's mirror dir -- the real `.mirror/` is out of reach."""
        # the account's real home, from the passwd database: $HOME is sandboxed
        real_mirror = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".claude", ".mirror")
        seen = []
        real_flock = rms.fcntl.flock

        def spy(lock, op):
            seen.append(lock.name)
            return real_flock(lock, op)

        monkeypatch.setattr(rms.fcntl, "flock", spy)
        monkeypatch.setattr(rms, "sync", lambda cfg: 0)

        assert rms._locked_sync() == 0

        assert seen and all(n.startswith(str(world.tmp_path)) for n in seen)
        assert not any(n.startswith(real_mirror) for n in seen)


# ===========================================================================
# the real CLI: argv -> __main__ -> exit code, in a fresh HOME
# ===========================================================================


def _cli(home, *argv):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for var in ("CSA_ENFORCE", "CSA_DISABLE_HOOKS", "CLAUDE_PID"):
        env.pop(var, None)
    return subprocess.run(
        [sys.executable, rms.__file__, *argv],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(home),
    )


class TestRealProcess:
    @pytest.mark.parametrize(
        "argv",
        [["--dry-run", "--sync"], ["--sync", "--dry-run"], ["--config", "x.json"],
         ["--sync", "--config", "x.json"]],
    )
    def test_usage_errors_exit_2_and_create_nothing_in_a_fresh_home(self, tmp_path, argv):
        home = tmp_path / "fresh-home"
        home.mkdir()

        proc = _cli(home, *argv)

        assert proc.returncode == 2, proc.stderr
        assert proc.stdout == ""
        assert "error:" in proc.stderr
        assert not (home / ".claude").exists()

    def test_dry_run_with_no_config_in_a_fresh_home_is_an_error(self, tmp_path):
        home = tmp_path / "fresh-home"
        (home / ".claude").mkdir(parents=True)

        proc = _cli(home, "--dry-run")

        assert proc.returncode == 1
        assert "DRY-RUN ERROR: config rejected" in proc.stdout
        assert not (home / ".claude" / ".mirror").exists()

    @_requires_git
    def test_full_dry_run_in_a_real_layout_exits_by_verdict_and_leaves_mirror_untouched(
        self, tmp_path
    ):
        home = tmp_path / "cli-home"
        claude = home / ".claude"
        claude.mkdir(parents=True)
        _git(claude, "init", "-q")
        _git(claude, "symbolic-ref", "HEAD", "refs/heads/main")
        (claude / "agents").mkdir()
        (claude / "agents" / "a.md").write_text("Built for SecretCorp partners.\n")
        _git(claude, "add", "agents")
        _git(claude, "commit", "-q", "-m", "initial")
        mirror = claude / ".mirror"
        mirror.mkdir()
        bare = _init_bare_remote(tmp_path)
        clone = mirror / "clone"
        _git(mirror, "clone", "-q", "--branch", "main", str(bare), str(clone))
        cfg = {
            "remote_url": "https://github.com/acme/mirror.git",
            "clone_dir": str(clone),
            "branch": "main",
            "include": ["agents", "README.md"],
            "mirror_managed": ["README.md"],
            "replacements": [["SecretCorp", "ExampleCo"]],
            "forbidden_patterns": ["secretcorp"],
        }
        (mirror / "config.json").write_text(json.dumps(cfg))
        blocked = dict(cfg, replacements=[])
        (mirror / "candidate.json").write_text(json.dumps(blocked))
        before = _snapshot(mirror)

        clean = _cli(home, "--dry-run")
        hit = _cli(home, "--dry-run", "--config", str(mirror / "candidate.json"))

        assert clean.returncode == 0, clean.stderr
        assert clean.stdout.strip().splitlines()[-1] == "DRY-RUN CLEAN"
        assert hit.returncode == 1, hit.stderr
        assert hit.stdout.strip().splitlines()[-1] == "DRY-RUN BLOCKED: 1 hit(s)"
        assert _hits(hit.stdout) == [("agents/a.md", "secretcorp")]
        assert "SecretCorp" not in clean.stdout + hit.stdout
        assert _snapshot(mirror) == before
