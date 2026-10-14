"""Tests for scripts/init_repo.sh (the per-repo runtime-bundle installer/updater).

Written from the CONTRACT given to the implementing agent, not from the
implementation (which is being built in parallel and may not exist yet).
Every assertion targets INTENDED behavior per that contract; a test that
fails only because the script does not yet exist is expected RED, not a
defect in the test.

Contract summary tested here (see the dispatching orchestrator's CONTRACT
text for the authoritative wording):
  - `init_repo.sh <repo-root>` honors env CLAUDE_DIR (default ~/.claude).
  - Not a git repo root -> exit 2, `not-a-repo-root`.
  - First run: copies every `templates/oversight/*.md` file except
    PLACEHOLDERS.md into `<repo>/.claude/oversight/` (never overwriting an
    existing dossier), creates `.claude/oversight/manifest.json` from
    `manifest.example.json` if absent, seeds the 3 knowledge template files
    into `<CLAUDE_DIR>/knowledge/` if absent, creates/merges
    `<repo>/.claude/settings.json` with `worktree.baseRef == "head"`
    (never overwriting an existing non-default baseRef), writes
    `<repo>/.claude/oversight/.bundle_version` = the scratch CLAUDE_DIR's
    own HEAD sha, prints a `DOCTOR:` block, exits 0.
  - Second run is fully idempotent (`kept ...` for everything, byte-identical
    files, exit 0).
  - `--diff <root>`: no template change since `.bundle_version` -> a single
    `no template changes since <sha7>` line, exit 0, writes nothing to the
    target repo. A template change -> a `=== <file> (template changed
    since ...` header + unified diff per changed file, exit 0, target repo
    untouched.
  - An unreadable `.bundle_version` (fails to parse as a plain sha, e.g.
    contains an option-injection string) -> exit 2, `bundle_version-unreadable`,
    no file created for the operation that needed it.
  - `--update-version <root>` overwrites `.bundle_version` to the current
    runtime HEAD sha.
  - Unknown flag -> exit 64.

Every gate is paired with a recovery test showing the user can reach the
intended state once the blocking condition is fixed. This suite never
touches the real `~/.claude/knowledge` or `~/.claude/templates` -- every
fixture builds its own scratch CLAUDE_DIR under `tmp_path` and points the
script at it via the CLAUDE_DIR env var. No `git` state-verbs are run
against the real runtime repo; the only git repos ever created here are
throwaway repos under `tmp_path`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path.home() / ".claude" / "scripts" / "init_repo.sh"
REAL_REPO_MANIFEST = Path.home() / ".claude" / "scripts" / "repo_manifest.py"

# A missing/renamed script must FAIL the whole suite (collection error, non-zero exit) --
# never 23 silent skips reporting a false all-clear at exit 0. This is a module-level assert,
# not a per-test skip guard: it fires once, at collection time, for every test in this file.
assert SCRIPT.exists(), f"init_repo.sh not found at {SCRIPT} -- the suite cannot run without it"


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _git_repo(tmp_path: Path, name: str = "target_repo") -> Path:
    """A throwaway git repo standing in for the product repo init_repo.sh is
    run against. Never the real product tree."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


_TEMPLATE_DOSSIERS = {
    "a.md": "# Agent A dossier\n\nGCP project: __PLACEHOLDER__\n",
    "b.md": "# Agent B dossier\n\nRegion: __PLACEHOLDER__\n",
}

_PLACEHOLDERS_MD = "# Template placeholder tokens\n\n| token | meaning |\n|---|---|\n"

_MANIFEST_EXAMPLE = {
    "schema_version": 1,
    "product": {"name": "ExampleApp", "slug": "exampleapp"},
    "github": {"repo": "your-org/your-repo"},
    "oversight": {"tracking_issue": None, "report_dir": "~/.claude/plans/wheel/${slug}"},
    "tracker_doc": None,
    "operator_input": None,
    "gtm": {"missions_dir": "docs/gtm_missions", "inbox_label": "dept:marketing"},
}

_KNOWLEDGE_TEMPLATES = {
    "agentarch_recommendations.jsonl": "",
    "research_ledger.jsonl": "",
    "oversight_install.md": "# Oversight install\n\nSeed narrative.\n",
}


def _claude_dir(tmp_path: Path, name: str = "fake_claude_dir") -> Path:
    """Build a scratch CLAUDE_DIR holding exactly the fixtures the contract
    names: templates/oversight/{a.md,b.md,PLACEHOLDERS.md,manifest.example.json},
    templates/knowledge/{3 files}, a real COPY of repo_manifest.py, and an
    empty knowledge/ dir -- then make the whole thing a git repo with one
    commit so `git -C <cdir> rev-parse HEAD` succeeds, exactly as the real
    ~/.claude is a git repo. Never the real ~/.claude/knowledge or
    ~/.claude/templates -- this is a fully separate scratch tree."""
    cdir = tmp_path / name
    oversight_tpl = cdir / "templates" / "oversight"
    knowledge_tpl = cdir / "templates" / "knowledge"
    oversight_tpl.mkdir(parents=True)
    knowledge_tpl.mkdir(parents=True)

    for fname, body in _TEMPLATE_DOSSIERS.items():
        (oversight_tpl / fname).write_text(body)
    (oversight_tpl / "PLACEHOLDERS.md").write_text(_PLACEHOLDERS_MD)
    (oversight_tpl / "manifest.example.json").write_text(json.dumps(_MANIFEST_EXAMPLE, indent=2))

    for fname, body in _KNOWLEDGE_TEMPLATES.items():
        (knowledge_tpl / fname).write_text(body)

    scripts_dir = cdir / "scripts"
    scripts_dir.mkdir(parents=True)
    if REAL_REPO_MANIFEST.exists():
        shutil.copyfile(REAL_REPO_MANIFEST, scripts_dir / "repo_manifest.py")
    else:
        # Fallback stub so init_repo.sh's doctor/validate shell-outs never
        # explode this suite if repo_manifest.py is itself absent on this
        # machine -- always exits 0 printing "OK: 0 findings" / "OK".
        (scripts_dir / "repo_manifest.py").write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('OK: 0 findings' if sys.argv[1:2] == ['doctor'] else 'OK')\n"
            "sys.exit(0)\n"
        )

    (cdir / "knowledge").mkdir(parents=True)

    subprocess.run(["git", "init", "-q"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cdir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed bundle"], cwd=cdir, check=True)
    return cdir


def _head_sha(cdir: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(cdir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit_all(cdir: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=cdir, check=True)


def _run(args: list[str], *, env: dict[str, str], cwd: Path | None = None, timeout: int = 30):
    return subprocess.run(
        ["/bin/bash", str(SCRIPT), *args],
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _base_env(cdir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(cdir)
    return env


def _hash_tree(root: Path, *, exclude_git: bool = True) -> dict[str, str]:
    """A content fingerprint of every regular file under root, keyed by
    repo-relative path -- used to prove a run wrote nothing / changed
    nothing (byte-identical check) without diffing directory listings by
    hand. Excludes `.git/` by default: git's own internals (index, reflogs,
    packed-refs) can legitimately churn from unrelated bookkeeping (e.g. the
    scratch fixtures' own `git rev-parse`/`git diff` calls touching
    `.git/index.lock` transiently) and are not what a "wrote nothing to the
    target repo" assertion is about -- that assertion is about the repo's
    actual tracked/working content, never git's own internal bookkeeping."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if exclude_git and ".git" in p.relative_to(root).parts:
            continue
        out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------------------------------------
# gate: not a repo root
# ---------------------------------------------------------------------------


def test_not_a_repo_root_exits_2(tmp_path):
    cdir = _claude_dir(tmp_path)
    non_repo = tmp_path / "not_a_repo"
    non_repo.mkdir()
    proc = _run([str(non_repo)], env=_base_env(cdir))
    assert proc.returncode == 2
    assert "not-a-repo-root" in (proc.stdout + proc.stderr)
    # never created the oversight dir when the gate fired
    assert not (non_repo / ".claude" / "oversight").exists()


def test_not_a_repo_root_recovers_once_it_is_a_repo(tmp_path):
    """Pairs with the gate above: the identical path, now a real git repo
    with a commit, succeeds."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert (repo / ".claude" / "oversight" / "manifest.json").is_file()


# ---------------------------------------------------------------------------
# first run
# ---------------------------------------------------------------------------


def test_first_run_copies_every_template_except_placeholders(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    oversight = repo / ".claude" / "oversight"
    assert (oversight / "a.md").read_text() == _TEMPLATE_DOSSIERS["a.md"]
    assert (oversight / "b.md").read_text() == _TEMPLATE_DOSSIERS["b.md"]
    assert not (oversight / "PLACEHOLDERS.md").exists()
    assert not (oversight / "manifest.example.json").exists()

    combined = proc.stdout + proc.stderr
    assert "copied a.md" in combined
    assert "copied b.md" in combined
    assert "PLACEHOLDERS.md" not in combined.replace("copied PLACEHOLDERS.md", "")


def test_first_run_creates_manifest_from_example(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    manifest_path = repo / ".claude" / "oversight" / "manifest.json"
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text()) == _MANIFEST_EXAMPLE


def test_first_run_seeds_knowledge_files_into_claude_dir(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    knowledge = cdir / "knowledge"
    for fname in _KNOWLEDGE_TEMPLATES:
        assert not (knowledge / fname).exists()

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    for fname, body in _KNOWLEDGE_TEMPLATES.items():
        seeded = knowledge / fname
        assert seeded.is_file(), f"{fname} was not seeded"
        assert seeded.read_text() == body

    combined = proc.stdout + proc.stderr
    for fname in _KNOWLEDGE_TEMPLATES:
        assert f"seeded {fname}" in combined or "seeded " + fname in combined


def test_first_run_seeding_never_touches_real_claude_knowledge(tmp_path):
    """Never touch the real ~/.claude/knowledge -- explicit negative check
    that the real oversight_install.md's mtime/content is untouched by a
    scratch-CLAUDE_DIR run."""
    real_install_doc = Path.home() / ".claude" / "knowledge" / "oversight_install.md"
    before = real_install_doc.read_bytes() if real_install_doc.exists() else None

    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    after = real_install_doc.read_bytes() if real_install_doc.exists() else None
    assert before == after


def test_first_run_creates_settings_json_with_worktree_base_ref_head(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    settings_path = repo / ".claude" / "settings.json"
    assert settings_path.is_file()
    settings = json.loads(settings_path.read_text())
    assert settings["worktree"]["baseRef"] == "head"


def test_first_run_writes_bundle_version_matching_claude_dir_head(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    expected_sha = _head_sha(cdir)

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    bundle_version_path = repo / ".claude" / "oversight" / ".bundle_version"
    assert bundle_version_path.is_file()
    assert bundle_version_path.read_text().strip() == expected_sha


def test_first_run_prints_doctor_block_and_exits_0(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert "DOCTOR:" in proc.stdout


# ---------------------------------------------------------------------------
# second run: idempotent
# ---------------------------------------------------------------------------


def test_second_run_is_idempotent_kept_lines_and_byte_identical(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)

    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0
    before_hashes = _hash_tree(repo / ".claude")

    second = _run([str(repo)], env=_base_env(cdir))
    assert second.returncode == 0
    after_hashes = _hash_tree(repo / ".claude")

    assert before_hashes == after_hashes

    combined = second.stdout + second.stderr
    assert "kept" in combined
    # never claims to have copied/created/seeded anything the second time
    assert "copied" not in combined
    assert "created" not in combined
    assert "seeded" not in combined


# ---------------------------------------------------------------------------
# existing dossier never overwritten
# ---------------------------------------------------------------------------


def test_existing_dossier_is_never_overwritten(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    custom_content = "# Custom, already-filled-in dossier\n\nGCP project: real-project-123\n"
    (oversight / "a.md").write_text(custom_content)

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert (oversight / "a.md").read_text() == custom_content

    combined = proc.stdout + proc.stderr
    assert "kept a.md" in combined
    assert "copied a.md" not in combined


def test_existing_dossier_kept_recovers_alongside_a_missing_sibling(tmp_path):
    """Pairs with the never-overwrite gate: the pre-existing a.md is kept
    while the sibling b.md (never customized) is still installed for the
    first time in the same run -- proving the never-overwrite rule doesn't
    block genuinely new templates from landing."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    custom_content = "# Custom dossier, keep me\n"
    (oversight / "a.md").write_text(custom_content)

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert (oversight / "a.md").read_text() == custom_content
    assert (oversight / "b.md").read_text() == _TEMPLATE_DOSSIERS["b.md"]


# ---------------------------------------------------------------------------
# settings.json merge behavior
# ---------------------------------------------------------------------------


def test_existing_settings_json_other_keys_preserved_and_gains_base_ref(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    existing = {"env": {"SOME_FLAG": "1"}, "permissions": {"allow": ["Bash(ls:*)"]}}
    (claude_settings_dir / "settings.json").write_text(json.dumps(existing, indent=2))

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    settings = json.loads((claude_settings_dir / "settings.json").read_text())
    assert settings["env"] == {"SOME_FLAG": "1"}
    assert settings["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert settings["worktree"]["baseRef"] == "head"


def test_existing_worktree_base_ref_fresh_is_left_alone_and_reported(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    existing = {"worktree": {"baseRef": "fresh"}}
    (claude_settings_dir / "settings.json").write_text(json.dumps(existing, indent=2))

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    settings = json.loads((claude_settings_dir / "settings.json").read_text())
    assert settings["worktree"]["baseRef"] == "fresh"

    combined = proc.stdout + proc.stderr
    assert "kept worktree.baseRef=fresh" in combined


def test_existing_worktree_base_ref_fresh_recovers_once_operator_switches_it(tmp_path):
    """Pairs with the leave-alone gate: an operator who manually flips the
    setting to "head" afterward sees a subsequent run report it kept, not
    fought or reverted."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    (claude_settings_dir / "settings.json").write_text(
        json.dumps({"worktree": {"baseRef": "fresh"}}, indent=2)
    )
    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0

    settings_path = claude_settings_dir / "settings.json"
    settings = json.loads(settings_path.read_text())
    settings["worktree"]["baseRef"] = "head"
    settings_path.write_text(json.dumps(settings, indent=2))

    second = _run([str(repo)], env=_base_env(cdir))
    assert second.returncode == 0
    final = json.loads(settings_path.read_text())
    assert final["worktree"]["baseRef"] == "head"


def test_existing_settings_json_worktree_not_an_object_exits_2_unchanged(tmp_path):
    """A `worktree` key that is present but is NOT itself an object (a bare
    string here, standing in for any non-dict value) must never be silently
    coerced/overwritten -- init cannot safely decide what the operator meant
    by it, so it stops with a clear error and leaves the file byte-identical,
    rather than discarding whatever `"worktree": "nope"` was supposed to mean
    and quietly replacing it with `{"baseRef": "head"}`."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    settings_path = claude_settings_dir / "settings.json"
    settings_path.write_text(json.dumps({"worktree": "nope"}, indent=2))
    before = settings_path.read_bytes()

    proc = _run([str(repo)], env=_base_env(cdir))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "settings.json-unreadable" in combined

    after = settings_path.read_bytes()
    assert before == after


def test_existing_settings_json_worktree_not_an_object_recovers_once_fixed(tmp_path):
    """Pairs with the malformed-worktree gate above: once the operator (or a
    prior tool) fixes the value to a real object, the identical repo/run
    succeeds, baseRef gets set, and any other sibling key on settings.json
    is preserved."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    settings_path = claude_settings_dir / "settings.json"
    settings_path.write_text(json.dumps({"worktree": "nope"}, indent=2))

    bad = _run([str(repo)], env=_base_env(cdir))
    assert bad.returncode == 2

    settings_path.write_text(
        json.dumps({"worktree": {}, "env": {"SOME_FLAG": "1"}}, indent=2)
    )

    good = _run([str(repo)], env=_base_env(cdir))
    assert good.returncode == 0

    settings = json.loads(settings_path.read_text())
    assert settings["worktree"]["baseRef"] == "head"
    assert settings["env"] == {"SOME_FLAG": "1"}


# ---------------------------------------------------------------------------
# settings.json write is atomic (temp file + rename, no leftover .tmp)
# ---------------------------------------------------------------------------


def test_settings_json_write_leaves_no_tmp_file_behind(tmp_path):
    """The settings.json update path writes via a temp file then renames it
    over the original (never a partial in-place write) -- after a normal
    successful run, no `settings.json.tmp` (or any other stray `.tmp` sibling)
    should remain in `.claude/`."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    existing = {"env": {"SOME_FLAG": "1"}}
    (claude_settings_dir / "settings.json").write_text(json.dumps(existing, indent=2))

    proc = _run([str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0

    tmp_leftovers = list(claude_settings_dir.glob("settings.json.tmp")) + list(
        claude_settings_dir.glob("*.tmp")
    )
    assert tmp_leftovers == [], f"leftover temp file(s) after a successful run: {tmp_leftovers}"

    settings = json.loads((claude_settings_dir / "settings.json").read_text())
    assert settings["worktree"]["baseRef"] == "head"


def test_read_only_claude_dir_fails_without_corrupting_settings_json(tmp_path):
    """A `.claude/` directory the process cannot write into (permissions
    0o555) must make init fail loudly (non-zero exit) rather than silently
    doing nothing or half-writing settings.json -- and the original
    settings.json content must be provably unchanged (byte hash) once
    permissions are restored. Skipped when running as root, since root
    ignores directory write permission bits entirely and the scenario this
    test targets cannot occur."""
    if os.geteuid() == 0:
        pytest.skip("running as root -- directory permission bits do not apply")

    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    claude_settings_dir = repo / ".claude"
    claude_settings_dir.mkdir(parents=True)
    existing = {"env": {"SOME_FLAG": "1"}}
    settings_path = claude_settings_dir / "settings.json"
    settings_path.write_text(json.dumps(existing, indent=2))
    before_hash = hashlib.sha256(settings_path.read_bytes()).hexdigest()

    claude_settings_dir.chmod(0o555)
    try:
        proc = _run([str(repo)], env=_base_env(cdir))
        assert proc.returncode != 0
    finally:
        claude_settings_dir.chmod(0o755)

    after_hash = hashlib.sha256(settings_path.read_bytes()).hexdigest()
    assert before_hash == after_hash


# ---------------------------------------------------------------------------
# --diff
# ---------------------------------------------------------------------------


def test_diff_with_no_template_change_reports_none_and_writes_nothing(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0
    # Whole target repo (excluding .git), not just .claude/ -- --diff must never write
    # ANYWHERE in the repo, not merely leave the oversight dossiers alone.
    before_repo_hashes = _hash_tree(repo)
    # The scratch CLAUDE_DIR itself must also come out untouched -- --diff reads the
    # runtime bundle, it never mutates it.
    before_cdir_hashes = _hash_tree(cdir)
    sha7 = _head_sha(cdir)[:7]

    proc = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert f"no template changes since {sha7}" in (proc.stdout + proc.stderr)

    after_repo_hashes = _hash_tree(repo)
    after_cdir_hashes = _hash_tree(cdir)
    assert before_repo_hashes == after_repo_hashes
    assert before_cdir_hashes == after_cdir_hashes


def test_diff_after_template_change_prints_header_and_unified_diff(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0
    # Whole target repo (excluding .git), not just .claude/, plus the scratch CLAUDE_DIR
    # itself -- --diff reads the (now-changed) template and must still write nowhere.
    before_repo_hashes = _hash_tree(repo)

    a_template = cdir / "templates" / "oversight" / "a.md"
    a_template.write_text(_TEMPLATE_DOSSIERS["a.md"] + "\nNew section added upstream.\n")
    _commit_all(cdir, "update a.md template")
    before_cdir_hashes = _hash_tree(cdir)

    proc = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert "=== a.md (template changed since" in proc.stdout
    assert "New section added upstream." in proc.stdout
    # unified diff hunk marker
    assert "@@" in proc.stdout

    after_repo_hashes = _hash_tree(repo)
    after_cdir_hashes = _hash_tree(cdir)
    assert before_repo_hashes == after_repo_hashes, "--diff must never write to the target repo"
    assert before_cdir_hashes == after_cdir_hashes, "--diff must never write to CLAUDE_DIR"


def test_diff_recovers_to_no_changes_once_bundle_version_updated(tmp_path):
    """Pairs with the changed-template diff test above: once the operator
    runs --update-version to accept the new template baseline, an
    immediately following --diff reports no changes again."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0

    a_template = cdir / "templates" / "oversight" / "a.md"
    a_template.write_text(_TEMPLATE_DOSSIERS["a.md"] + "\nNew section added upstream.\n")
    _commit_all(cdir, "update a.md template")

    changed = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert "=== a.md (template changed since" in changed.stdout

    update = _run(["--update-version", str(repo)], env=_base_env(cdir))
    assert update.returncode == 0

    new_sha7 = _head_sha(cdir)[:7]
    settled = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert settled.returncode == 0
    assert f"no template changes since {new_sha7}" in (settled.stdout + settled.stderr)


# ---------------------------------------------------------------------------
# unreadable .bundle_version
# ---------------------------------------------------------------------------


def test_unreadable_bundle_version_exits_2_no_file_created(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    bundle_version_path = oversight / ".bundle_version"
    bundle_version_path.write_text("--output=x\n")
    # Whole target repo (excluding .git) plus the scratch CLAUDE_DIR itself -- a failed
    # --diff must write NOTHING anywhere, not merely fail to produce one specific,
    # never-otherwise-created filename (a check against a name the script never writes
    # under any outcome proves nothing about this failure path specifically).
    before_repo_hashes = _hash_tree(repo)
    before_cdir_hashes = _hash_tree(cdir)

    proc = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert proc.returncode == 2
    assert "bundle_version-unreadable" in (proc.stdout + proc.stderr)

    after_repo_hashes = _hash_tree(repo)
    after_cdir_hashes = _hash_tree(cdir)
    assert before_repo_hashes == after_repo_hashes
    assert before_cdir_hashes == after_cdir_hashes
    # the malformed value itself is left untouched by the failed read, never
    # silently "fixed" out from under the operator
    assert bundle_version_path.read_text() == "--output=x\n"


def test_unreadable_bundle_version_recovers_once_update_version_runs(tmp_path):
    """Pairs with the unreadable gate: --update-version overwrites the bad
    value with a real sha, after which --diff works again."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    (oversight / ".bundle_version").write_text("--output=x\n")

    bad = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert bad.returncode == 2

    fix = _run(["--update-version", str(repo)], env=_base_env(cdir))
    assert fix.returncode == 0

    expected_sha = _head_sha(cdir)
    assert (oversight / ".bundle_version").read_text().strip() == expected_sha

    good = _run(["--diff", str(repo)], env=_base_env(cdir))
    assert good.returncode == 0
    assert "bundle_version-unreadable" not in (good.stdout + good.stderr)


def test_diff_bundle_version_is_well_formed_but_unreachable_sha_exits_2(tmp_path):
    """A `.bundle_version` that IS a plain 40-hex-char string (passes the
    regex/shape check) but names a sha that is not actually a reachable
    revision in CLAUDE_DIR (e.g. corrupted, copy-pasted from a different
    clone, or a deliberately-crafted 40 'f' characters) must be treated
    exactly like any other unreadable bundle_version: exit 2,
    `bundle_version-unreadable` on stderr, and it must NEVER be reported as
    if there were simply no template changes -- that would be a false
    all-clear telling the operator their oversight dossiers are current
    when the tool actually could not compare anything at all."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    bundle_version_path = oversight / ".bundle_version"
    unreachable_sha = "f" * 40
    bundle_version_path.write_text(unreachable_sha + "\n")

    proc = _run(["--diff", str(repo)], env=_base_env(cdir))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "bundle_version-unreadable" in combined
    assert "no template changes" not in proc.stdout


def test_diff_unreachable_sha_recovers_with_a_valid_head_sha(tmp_path):
    """Pairs with the unreachable-sha gate above: the identical shape (a
    well-formed 40-hex-char string) that DOES name a real, reachable
    revision -- the scratch CLAUDE_DIR's own current HEAD -- succeeds and
    reports no template changes, proving the gate above fires on
    reachability specifically, not merely on the string's length/shape."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    valid_sha = _head_sha(cdir)
    assert len(valid_sha) == 40
    (oversight / ".bundle_version").write_text(valid_sha + "\n")

    proc = _run(["--diff", str(repo)], env=_base_env(cdir))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0
    assert "bundle_version-unreadable" not in combined
    assert f"no template changes since {valid_sha[:7]}" in combined


# ---------------------------------------------------------------------------
# --update-version
# ---------------------------------------------------------------------------


def test_update_version_overwrites_bundle_version_to_new_head(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    first = _run([str(repo)], env=_base_env(cdir))
    assert first.returncode == 0
    old_sha = _head_sha(cdir)
    bundle_version_path = repo / ".claude" / "oversight" / ".bundle_version"
    assert bundle_version_path.read_text().strip() == old_sha

    # advance the scratch CLAUDE_DIR's HEAD
    (cdir / "templates" / "oversight" / "a.md").write_text("# Agent A dossier v2\n")
    _commit_all(cdir, "bump a.md")
    new_sha = _head_sha(cdir)
    assert new_sha != old_sha

    proc = _run(["--update-version", str(repo)], env=_base_env(cdir))
    assert proc.returncode == 0
    assert bundle_version_path.read_text().strip() == new_sha


# ---------------------------------------------------------------------------
# unknown flag
# ---------------------------------------------------------------------------


def test_unknown_flag_exits_64(tmp_path):
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    proc = _run(["--not-a-real-flag", str(repo)], env=_base_env(cdir))
    assert proc.returncode == 64


def test_unknown_flag_recovers_once_flag_dropped(tmp_path):
    """Pairs with the unknown-flag gate: dropping the bad flag and re-running
    the otherwise-identical invocation succeeds."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    bad = _run(["--not-a-real-flag", str(repo)], env=_base_env(cdir))
    assert bad.returncode == 64

    good = _run([str(repo)], env=_base_env(cdir))
    assert good.returncode == 0


# ---------------------------------------------------------------------------
# exit-code contract: every path is 0 / 2 / 64, never a bare 1
# ---------------------------------------------------------------------------


def test_templates_oversight_missing_from_claude_dir_exits_2(tmp_path):
    """`templates/oversight/` is the source of every dossier skeleton init
    installs; an install run against a CLAUDE_DIR whose templates directory
    doesn't exist at all cannot possibly do its job, and must never be
    reported as a successful (exit 0) no-op init -- that would silently
    hand the operator an empty `.claude/oversight/` and call it done."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    shutil.rmtree(cdir / "templates" / "oversight")

    proc = _run([str(repo)], env=_base_env(cdir))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "templates-missing" in combined
    assert not (repo / ".claude" / "oversight" / "manifest.json").exists()


def test_templates_oversight_missing_recovers_once_restored(tmp_path):
    """Pairs with the templates-missing gate above: once templates/oversight/
    exists again (e.g. the operator re-clones/repairs CLAUDE_DIR), the
    identical repo/run succeeds normally."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    oversight_tpl = cdir / "templates" / "oversight"
    saved = {p.name: p.read_text() for p in oversight_tpl.iterdir() if p.is_file()}
    shutil.rmtree(oversight_tpl)

    bad = _run([str(repo)], env=_base_env(cdir))
    assert bad.returncode == 2

    oversight_tpl.mkdir(parents=True)
    for name, body in saved.items():
        (oversight_tpl / name).write_text(body)

    good = _run([str(repo)], env=_base_env(cdir))
    assert good.returncode == 0
    assert (repo / ".claude" / "oversight" / "manifest.json").is_file()


def test_repo_manifest_py_absent_still_exits_0_with_warning(tmp_path):
    """`repo_manifest.py` is a reporting step (validate/doctor), not part of
    the scaffolding init itself installs -- if it's missing from CLAUDE_DIR's
    scripts/ dir, init must still complete and report a WARNING that
    validate/doctor could not run, never fail the whole init over a
    downstream reporting tool being absent."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    (cdir / "scripts" / "repo_manifest.py").unlink()

    proc = _run([str(repo)], env=_base_env(cdir))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0
    assert "WARNING: validate could not run" in combined
    # the scaffolding steps before the reporting step still ran normally
    assert (repo / ".claude" / "oversight" / "manifest.json").is_file()


def test_repo_manifest_py_absent_recovers_once_restored(tmp_path):
    """Pairs with the repo_manifest.py-absent gate above: once the reporting
    script is back in place, the identical repo/run reports real
    validate/doctor output again instead of the WARNING fallback."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    repo_manifest_path = cdir / "scripts" / "repo_manifest.py"
    saved_body = repo_manifest_path.read_text()
    repo_manifest_path.unlink()

    degraded = _run([str(repo)], env=_base_env(cdir))
    assert degraded.returncode == 0
    assert "WARNING: validate could not run" in (degraded.stdout + degraded.stderr)

    repo_manifest_path.write_text(saved_body)

    restored = _run([str(repo)], env=_base_env(cdir))
    assert restored.returncode == 0
    assert "WARNING: validate could not run" not in (restored.stdout + restored.stderr)


@pytest.mark.parametrize(
    "args_builder",
    [
        lambda repo: ["not_a_repo_root_placeholder"],
        lambda repo: [str(repo)],
        lambda repo: [str(repo)],
        lambda repo: ["--diff", str(repo)],
        lambda repo: ["--update-version", str(repo)],
        lambda repo: ["--not-a-real-flag", str(repo)],
        lambda repo: [],
    ],
)
def test_every_exit_code_across_the_whole_surface_is_0_2_or_64_never_1(tmp_path, args_builder):
    """Cross-cutting contract check: no invocation shape this suite exercises
    may ever return exit code 1. The script's own documented EXIT CODES
    section names exactly 0, 2, and 64 -- a bare 1 (Python's generic
    uncaught-exception default, or a naive early `sys.exit(1)`) is never a
    sanctioned outcome anywhere in this tool, gate or happy path alike."""
    cdir = _claude_dir(tmp_path)
    repo = _git_repo(tmp_path)
    args = args_builder(repo)
    proc = _run(args, env=_base_env(cdir))
    assert proc.returncode in (0, 2, 64), (
        f"exit code {proc.returncode} is outside the sanctioned {{0,2,64}} set "
        f"for args={args!r}; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )

    good = _run([str(repo)], env=_base_env(cdir))
    assert good.returncode == 0
