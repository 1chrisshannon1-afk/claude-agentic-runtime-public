"""Tests for scripts/repo_manifest.py (the per-repo `.claude/oversight/manifest.json`
CLI: get / validate / register / doctor).

Written from the CONTRACT given to the implementing agent, not from the
implementation (which is being built in parallel and may not exist yet). Every
assertion targets INTENDED behavior per that contract; a test that fails only
because the script does not yet exist is expected RED, not a defect in the
test.

Contract summary tested here:
  - runtime dir resolution (CLAUDE_DIR env override), repo resolution
    (--repo or git toplevel), manifest path = <repo>/.claude/oversight/manifest.json
  - `get <dotted.key>`: raw strings / json.dumps for non-strings, ~ expansion,
    ${slug} substitution in oversight.report_dir, exit codes 0/3/3/4
  - `validate`: required + optional-typed fields, `OK`/`INVALID ...` lines,
    exit 0/2
  - `register`: idempotent upsert into repo_registry.json + wheel_repos.json,
    alias-preserving, label step never fails the command
  - `doctor`: per-dossier findings (missing/placeholder/restates-manifest/
    template-outdated), OK-vs-N-findings summary, exit 0/1
  - unknown subcommand -> exit 64
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path.home() / ".claude" / "scripts" / "repo_manifest.py"
REAL_CLAUDE_DIR = Path.home() / ".claude"


def _skip_if_absent():
    if not SCRIPT.exists():
        pytest.skip(f"repo_manifest.py not yet present at {SCRIPT} (expected RED)")


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _git_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


def _fake_claude_dir(tmp_path: Path, gh_bin: Path | None = None) -> Path:
    """Build a CLAUDE_DIR fixture: agents/ (real dossier references,
    dev-runtime reference, ignored trading-strategist), knowledge/ (copies of
    the REAL repo_registry.json / wheel_repos.json, never the real files
    themselves)."""
    cdir = tmp_path / "fake_claude_dir"
    agents = cdir / "agents"
    agents.mkdir(parents=True)

    def _agent(name: str, body: str) -> None:
        (agents / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: x\nmodel: sonnet\ntools: Read\n---\n\n{body}\n"
        )

    _agent(
        "sentinel",
        "Read the repo-local dossier `.claude/oversight/sentinel.md` before judging.\n"
        "Also read `.claude/oversight/dev-runtime.md` for this repo's commands.",
    )
    _agent(
        "market-analyst",
        "Read `.claude/oversight/market-analyst.md` for this repo's grounding facts.",
    )
    _agent(
        "board-steward",
        "Read `.claude/oversight/board-steward.md`, plus `.claude/oversight/dev-runtime.md`.",
    )
    # ignored: no oversight/*.md reference of any kind in its body.
    _agent(
        "trading-strategist",
        "An advisory trading-domain specialist. Never reads any repo oversight dossier.",
    )

    knowledge = cdir / "knowledge"
    knowledge.mkdir(parents=True)
    real_registry = REAL_CLAUDE_DIR / "knowledge" / "repo_registry.json"
    real_wheel = REAL_CLAUDE_DIR / "knowledge" / "wheel_repos.json"
    if real_registry.exists():
        shutil.copyfile(real_registry, knowledge / "repo_registry.json")
    else:
        (knowledge / "repo_registry.json").write_text(
            json.dumps({"schema_version": 1, "repos": {}})
        )
    if real_wheel.exists():
        shutil.copyfile(real_wheel, knowledge / "wheel_repos.json")
    else:
        (knowledge / "wheel_repos.json").write_text(json.dumps({"_comment": "x"}))

    if gh_bin is not None:
        pass  # PATH is set by the caller via env, not stored on disk here.

    return cdir


def _run(args: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _base_env(claude_dir: Path, extra_path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_dir)
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
    return env


def _fake_gh(tmp_path: Path, log_path: Path) -> Path:
    """A fake `gh` on PATH that logs argv and exits 0, so `register`'s label
    step is testable without network. Simulates 'label does not exist yet' by
    default (list -> empty, create -> succeeds)."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{log_path}"\n'
        'if [ "$1" = "label" ] && [ "$2" = "list" ]; then\n'
        "  exit 0\n"  # empty stdout == label not found
        "fi\n"
        "exit 0\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return bindir


def _write_manifest(repo: Path, data: dict) -> Path:
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    manifest = oversight / "manifest.json"
    manifest.write_text(json.dumps(data, indent=2))
    return manifest


def _valid_manifest(repo: Path, extra: dict | None = None) -> dict:
    missions_dir = repo / "missions"
    missions_dir.mkdir(exist_ok=True)
    data = {
        "schema_version": 1,
        "product": {"name": "Widget Co", "slug": "widgetco"},
        "github": {"repo": "acme/widgetco"},
        "gtm": {"missions_dir": "missions", "inbox_label": "dept:marketing"},
        "oversight": {"tracking_issue": None, "report_dir": "reports/${slug}"},
    }
    if extra:
        data.update(extra)
    return data


# ---------------------------------------------------------------------------
# repo / runtime dir resolution
# ---------------------------------------------------------------------------


def test_no_manifest_get_exits_3_manifest_missing(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    proc = _run(["get", "product.name"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 3
    assert "manifest-missing" in proc.stderr
    assert str(repo / ".claude" / "oversight" / "manifest.json") in proc.stderr


def test_get_recovers_once_manifest_created(tmp_path):
    """Pairs with the missing-manifest gate above: create the manifest and the
    identical `get` call succeeds."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["get", "product.name"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Widget Co"


def test_not_a_repo_exits_3(tmp_path):
    _skip_if_absent()
    non_repo = tmp_path / "not_a_repo"
    non_repo.mkdir()
    cdir = _fake_claude_dir(tmp_path)
    proc = _run(["get", "product.name"], cwd=non_repo, env=_base_env(cdir))
    assert proc.returncode == 3
    assert "not-a-repo" in proc.stderr


def test_explicit_repo_flag_overrides_cwd_toplevel(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()
    proc = _run(
        ["get", "product.name", "--repo", str(repo)], cwd=other_cwd, env=_base_env(cdir)
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Widget Co"


def test_claude_dir_env_missing_falls_back_to_home_dot_claude(tmp_path):
    """Documents the CLAUDE_DIR-else-~/.claude fallback: without CLAUDE_DIR set,
    the script must resolve knowledge/agents paths under the real ~/.claude,
    not crash. We only assert it runs and produces a well-formed exit for a
    `get` against a manifest that exists (repo-side), independent of runtime
    dir, since CLAUDE_DIR only matters for register/doctor."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    env = dict(os.environ)
    env.pop("CLAUDE_DIR", None)
    proc = _run(["get", "product.name"], cwd=repo, env=env)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Widget Co"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_string_printed_raw_not_json_quoted(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["get", "product.slug"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "widgetco"  # not '"widgetco"'


def test_get_non_string_prints_json_dumps(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["github"]["project_number"] = 7
    _write_manifest(repo, manifest)
    proc = _run(["get", "github.project_number"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert json.loads(proc.stdout.strip()) == 7


def test_get_object_value_prints_json_dumps(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["get", "gtm"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    parsed = json.loads(proc.stdout.strip())
    assert parsed == {"missions_dir": "missions", "inbox_label": "dept:marketing"}


def test_get_tilde_expansion(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "~/somewhere/doc.md"
    _write_manifest(repo, manifest)
    proc = _run(["get", "tracker_doc"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == os.path.expanduser("~/somewhere/doc.md")
    assert "~" not in proc.stdout


def test_get_slug_substitution_in_report_dir(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["get", "oversight.report_dir"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "reports/widgetco"


# ---------------------------------------------------------------------------
# get: path-typed keys (tracker_doc, operator_input.path, operator_input.open_path,
# gtm.missions_dir, wheel.venv_python) are stored repo-relative but `get` prints
# them ANCHORED to the resolved repo root -- absolute -- since a repo-relative
# string otherwise resolves against the CALLER's cwd, wrong from any directory
# but the repo root. `--raw` opts back into the stored relative value.
# ---------------------------------------------------------------------------


def test_get_path_key_prints_absolute_path_when_cwd_is_a_subdirectory(tmp_path):
    """Run from a SUBDIRECTORY of the repo, no --repo flag: `get tracker_doc`
    must still print an absolute path anchored to the repo root, not a path
    that resolves (wrongly) against the subdirectory cwd."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    sub = repo / "sub"
    sub.mkdir()

    proc = _run(["get", "tracker_doc"], cwd=sub, env=_base_env(cdir))
    assert proc.returncode == 0
    expected = str((repo / "docs" / "launch_readiness_tracker.html").resolve())
    assert proc.stdout.strip() == expected
    assert os.path.isabs(proc.stdout.strip())


def test_get_raw_prints_stored_relative_value(tmp_path):
    """`get --raw <key>` opts out of the absolute-anchoring above and prints
    the manifest's stored (repo-relative) value verbatim."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    sub = repo / "sub"
    sub.mkdir()

    proc = _run(["get", "--raw", "tracker_doc"], cwd=sub, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "docs/launch_readiness_tracker.html"
    assert not os.path.isabs(proc.stdout.strip())


def test_get_path_key_already_absolute_value_returned_unchanged(tmp_path):
    """A manifest that already stores an ABSOLUTE path for a path-typed key
    is returned unchanged -- `get` never double-anchors an already-absolute
    value against the repo root."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    absolute_doc = tmp_path / "elsewhere_docs" / "tracker.html"
    absolute_doc.parent.mkdir(parents=True)
    absolute_doc.write_text("<html></html>")
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = str(absolute_doc)
    _write_manifest(repo, manifest)

    proc = _run(["get", "tracker_doc"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == str(absolute_doc)


def test_get_path_key_null_value_stays_null(tmp_path):
    """A path-typed key holding `null` (e.g. an optional field explicitly set
    to None) must still print `null`, never crash or get treated as a string
    to anchor against the repo root."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = None
    _write_manifest(repo, manifest)

    proc = _run(["get", "tracker_doc"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "null"


def test_get_non_path_key_unaffected_by_absolute_anchoring(tmp_path):
    """A non-path-typed key (gtm.inbox_label) is unaffected by the path-key
    anchoring behavior -- it prints its raw string value regardless of cwd or
    --raw."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    sub = repo / "sub"
    sub.mkdir()

    proc = _run(["get", "gtm.inbox_label"], cwd=sub, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "dept:marketing"

    proc_raw = _run(["get", "--raw", "gtm.inbox_label"], cwd=sub, env=_base_env(cdir))
    assert proc_raw.returncode == 0
    assert proc_raw.stdout.strip() == "dept:marketing"


def test_doctor_d1_still_flags_dossier_restating_relative_tracker_doc_value(tmp_path):
    """D1's restates-manifest comparison must use the RAW (repo-relative)
    tracker_doc value, not the absolute path `get` now prints -- a dossier
    that restates the relative literal is still flagged exactly as before
    this absolute-anchoring change."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(
        "The tracker lives at docs/launch_readiness_tracker.html, read it there.\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "sentinel.md\trestates-manifest:tracker_doc" in proc.stdout
    # never the absolute form -- proves D1 compares against the raw value
    assert str(repo) not in proc.stdout


def test_get_missing_key_exits_3(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["get", "nonexistent.key"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 3
    assert "key-missing: nonexistent.key" in proc.stderr


def test_get_recovers_once_correct_key_used(tmp_path):
    """Pairs with the missing-key gate: same manifest, correct key succeeds."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    bad = _run(["get", "nonexistent.key"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 3
    good = _run(["get", "product.name"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0
    assert good.stdout.strip() == "Widget Co"


def test_get_bad_json_exits_4_manifest_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True)
    (oversight / "manifest.json").write_text("{not valid json")
    proc = _run(["get", "product.name"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 4
    assert "manifest-invalid" in proc.stderr


def test_get_never_prints_a_default_for_absent_optional_key(tmp_path):
    """A manifest that omits an optional field (e.g. github.project_number)
    must never silently invent a default value on `get` -- it is key-missing,
    exit 3, per contract ('Never prints a default')."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))  # no github.project_number
    proc = _run(["get", "github.project_number"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 3
    assert "key-missing" in proc.stderr
    assert proc.stdout == ""


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_ok_on_fully_valid_manifest(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK"


def test_validate_missing_missions_dir_is_invalid_then_recovers(tmp_path):
    """Required pairing: INVALID for a missions_dir that does not exist on
    disk, then create the dir and get OK."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["gtm"]["missions_dir"] = "does_not_exist_yet"
    _write_manifest(repo, manifest)

    bad = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 2
    assert "INVALID gtm.missions_dir" in bad.stdout or "INVALID gtm.missions_dir" in bad.stderr

    (repo / "does_not_exist_yet").mkdir()
    good = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0
    assert good.stdout.strip() == "OK"


def test_validate_bad_slug_pattern_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["product"]["slug"] = "Not_Valid!"
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID product.slug" in combined


def test_validate_bad_github_repo_pattern_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["github"]["repo"] = "not-a-valid-repo-slug"
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID github.repo" in combined


def test_validate_missing_required_field_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    del manifest["gtm"]["inbox_label"]
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID gtm.inbox_label" in combined


def test_validate_wrong_schema_version_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["schema_version"] = 2
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID schema_version" in combined


def test_validate_tracker_doc_null_is_valid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = None
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK"


def test_validate_tracker_doc_nonexistent_file_invalid_then_recovers(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/does_not_exist.md"
    _write_manifest(repo, manifest)

    bad = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 2
    combined = bad.stdout + bad.stderr
    assert "INVALID tracker_doc" in combined

    (repo / "docs").mkdir()
    (repo / "docs" / "does_not_exist.md").write_text("x")
    good = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0


def test_validate_operator_input_object_requires_existing_path(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["operator_input"] = {"kind": "queue", "path": "docs/queue.html"}
    _write_manifest(repo, manifest)

    bad = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 2
    combined = bad.stdout + bad.stderr
    assert "INVALID operator_input" in combined

    (repo / "docs").mkdir()
    (repo / "docs" / "queue.html").write_text("<html></html>")
    good = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0


def test_validate_operator_input_null_is_valid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["operator_input"] = None
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0


def test_validate_wheel_venv_python_must_exist_relative_to_repo(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["wheel"] = {"venv_python": ".venv/bin/python"}
    _write_manifest(repo, manifest)

    bad = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 2
    combined = bad.stdout + bad.stderr
    assert "INVALID wheel" in combined

    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    good = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0


def test_validate_security_lists_must_be_lists_of_strings(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["security"] = {"auth_cookie_names": ["session_id", 42]}
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID security.auth_cookie_names" in combined


def test_validate_security_lists_valid_when_all_strings(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["security"] = {
        "auth_cookie_names": ["session_id", "refresh_token"],
        "extra_risk_keywords": ["billing", "licensing"],
    }
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0


def test_validate_oversight_tracking_issue_null_valid_int_valid_string_invalid(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)

    manifest = _valid_manifest(repo)
    manifest["oversight"]["tracking_issue"] = None
    _write_manifest(repo, manifest)
    assert _run(["validate"], cwd=repo, env=_base_env(cdir)).returncode == 0

    manifest["oversight"]["tracking_issue"] = 4900
    _write_manifest(repo, manifest)
    assert _run(["validate"], cwd=repo, env=_base_env(cdir)).returncode == 0

    manifest["oversight"]["tracking_issue"] = "4900"
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID oversight.tracking_issue" in combined


def test_validate_github_project_number_must_be_int(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["github"]["project_number"] = "one"
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID github.project_number" in combined


def test_validate_multiple_invalid_fields_all_reported(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["product"]["slug"] = "BAD SLUG"
    del manifest["gtm"]["inbox_label"]
    _write_manifest(repo, manifest)
    proc = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert "INVALID product.slug" in combined
    assert "INVALID gtm.inbox_label" in combined


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_creates_registry_entry_and_updates_message(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0
    assert "updated" in proc.stdout

    registry = json.loads((cdir / "knowledge" / "repo_registry.json").read_text())
    assert registry["repos"]["widgetco"]["root"] in (
        str(repo),
        str(repo).replace(str(Path.home()), "~", 1),
    )


def test_register_is_idempotent_second_run_unchanged(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    first = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert first.returncode == 0
    second = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert second.returncode == 0
    assert "unchanged" in second.stdout
    assert "updated" not in second.stdout


def test_register_preserves_root_sharing_alias(tmp_path):
    """Registering slug `csa` at a root that already has a DIFFERENT slug
    (`exampleapp`, mirroring the real registry's shape -- verified
    live above in test_register_creates_registry_entry_and_updates_message
    style fixtures) must KEEP the pre-existing slug at that same root, and
    print the registry-alias notice naming it. Fully hermetic: a throwaway
    git repo, never the real ExampleApp tree, so this never risks a
    concurrent-agent collision on the shared repo's own manifest.json."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="shared_root_repo")
    cdir = _fake_claude_dir(tmp_path)
    # Seed the FAKE registry copy with a pre-existing alias at this repo's own
    # root, mirroring the real registry's exampleapp/agency shape.
    registry_path = cdir / "knowledge" / "repo_registry.json"
    registry = json.loads(registry_path.read_text())
    registry.setdefault("repos", {})["exampleapp"] = {"root": str(repo)}
    registry_path.write_text(json.dumps(registry))

    manifest = _valid_manifest(repo)
    manifest["product"]["slug"] = "csa"
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0
    assert "registry-alias: exampleapp shares this root" in proc.stdout

    updated = json.loads(registry_path.read_text())
    assert "exampleapp" in updated["repos"]
    assert "csa" in updated["repos"]
    assert updated["repos"]["exampleapp"]["root"] == str(repo)
    assert updated["repos"]["csa"]["root"] == str(repo)


def test_register_upserts_wheel_repos_only_when_wheel_present(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    manifest["wheel"] = {
        "tier0_statuses": ["failed", "blocked"],
        "tier1_statuses": ["local"],
        "estimate_loop_exclusive_prefixes": [],
        "trust_surface_prefixes": [],
        "mandatory_registration_paths": [],
        "venv_python": ".venv/bin/python",
        "board_regen_command": None,
    }
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0

    wheel = json.loads((cdir / "knowledge" / "wheel_repos.json").read_text())
    assert wheel["widgetco"] == manifest["wheel"]
    assert "_comment" in wheel  # preserved


def test_register_without_wheel_leaves_wheel_repos_untouched(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))  # no "wheel" key
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    before = (cdir / "knowledge" / "wheel_repos.json").read_text()
    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0
    after = (cdir / "knowledge" / "wheel_repos.json").read_text()
    assert json.loads(before) == json.loads(after)
    assert "widgetco" not in json.loads(after)


def test_register_wheel_upsert_preserves_other_slugs_and_comment_semantically(tmp_path):
    """SEMANTIC (not byte) no-regression check: register the real csa wheel
    block via the manifest and confirm the resulting file's csa/agency entries
    are semantically identical (deep-equal JSON) to the real wheel_repos.json,
    after our widgetco upsert."""
    _skip_if_absent()
    real_wheel_path = REAL_CLAUDE_DIR / "knowledge" / "wheel_repos.json"
    if not real_wheel_path.exists():
        pytest.skip("no real wheel_repos.json fixture present on this machine")
    real_wheel = json.loads(real_wheel_path.read_text())
    if "csa" not in real_wheel:
        pytest.skip("real wheel_repos.json has no 'csa' entry to copy")

    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)  # already seeded with a copy of the real file
    manifest = _valid_manifest(repo)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    wheel_block = dict(real_wheel["csa"])
    wheel_block["venv_python"] = ".venv/bin/python"  # must exist relative to THIS repo
    manifest["wheel"] = wheel_block
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0

    new_wheel = json.loads((cdir / "knowledge" / "wheel_repos.json").read_text())
    old_wheel = json.loads((REAL_CLAUDE_DIR / "knowledge" / "wheel_repos.json").read_text())
    assert new_wheel["csa"] == old_wheel["csa"]
    assert new_wheel["agency"] == old_wheel["agency"]


def test_register_label_created_when_gh_reports_no_label(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    log_path = tmp_path / "gh_calls.log"
    gh_bin = _fake_gh(tmp_path, log_path)

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0
    assert "label-created" in proc.stdout or "label-exists" in proc.stdout
    assert log_path.exists()
    assert "label" in log_path.read_text()


def test_register_label_step_never_fails_command_when_gh_absent(tmp_path):
    """No `gh` on PATH at all: register must still exit 0, printing
    label-skipped with a reason -- never a nonzero exit for the label step."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))

    env = _base_env(cdir)
    # Strip any dir containing a real `gh` binary from PATH.
    stripped = os.pathsep.join(
        p
        for p in env.get("PATH", "").split(os.pathsep)
        if not (Path(p) / "gh").exists()
    )
    env["PATH"] = stripped

    proc = _run(["register"], cwd=repo, env=env)
    assert proc.returncode == 0
    assert "label-skipped" in proc.stdout


def test_register_recovers_to_label_created_once_gh_is_on_path(tmp_path):
    """Pairs with the gh-absent gate above: same manifest, gh now on PATH,
    register succeeds with a real label step outcome (not label-skipped)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0
    assert "label-skipped" not in proc.stdout


def test_register_fails_when_manifest_invalid_per_validate(tmp_path):
    """register runs validate first ('after validate' per contract): an
    invalid manifest must not be registered."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    del manifest["gtm"]["inbox_label"]
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode != 0
    registry = json.loads((cdir / "knowledge" / "repo_registry.json").read_text())
    assert "widgetco" not in registry.get("repos", {})


def test_register_recovers_once_manifest_fixed(tmp_path):
    """Pairs with the invalid-manifest gate: fix the field, register succeeds."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    del manifest["gtm"]["inbox_label"]
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    bad = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert bad.returncode != 0

    fixed = _valid_manifest(repo)
    _write_manifest(repo, fixed)
    good = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert good.returncode == 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_missing_manifest_reports_but_continues(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "manifest\tmissing" in proc.stdout


def test_doctor_flags_missing_dossier_for_referenced_agent(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # no sentinel.md, no board-steward.md, no dev-runtime.md written
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "sentinel\tmissing-dossier" in proc.stdout
    assert "board-steward\tmissing-dossier" in proc.stdout
    assert "dev-runtime\tmissing-dossier" in proc.stdout
    # trading-strategist references no oversight dossier -> never mentioned
    assert "trading-strategist" not in proc.stdout


def test_doctor_recovers_once_dossiers_present(tmp_path):
    """Pairs with the missing-dossier gate: write all referenced dossiers and
    doctor reports zero findings for those agents (may still report other
    findings if present; this test only asserts these specific lines are gone)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel\tmissing-dossier" not in proc.stdout
    assert "board-steward\tmissing-dossier" not in proc.stdout
    assert "dev-runtime\tmissing-dossier" not in proc.stdout


# ---------------------------------------------------------------------------
# dossier opt-out: an agent file whose text carries the literal opt-out
# phrase "No per-agent `.claude/oversight/<name>.md` dossier is expected in
# any repo" is NOT reported missing-dossier for its own per-agent dossier
# when that file is absent -- but a bare `oversight/dev-runtime.md`
# reference in the SAME agent file is unaffected by that opt-out and still
# gets `dev-runtime\tmissing-dossier` when dev-runtime.md is absent too.
# ---------------------------------------------------------------------------

_D1_OPT_OUT_PHRASE = (
    "No per-agent `.claude/oversight/{name}.md` dossier is expected in any repo"
)


def _claude_dir_with_single_agent(tmp_path: Path, name: str, body: str) -> Path:
    """A minimal CLAUDE_DIR fixture carrying exactly one agent file (plus the
    knowledge/ files doctor/register otherwise expect), isolated from
    `_fake_claude_dir`'s sentinel/board-steward/market-analyst agents so only
    the opt-out agent's own missing-dossier behavior is under test."""
    cdir = tmp_path / "fake_claude_dir_single_agent"
    agents = cdir / "agents"
    agents.mkdir(parents=True)
    (agents / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: x\nmodel: sonnet\ntools: Read\n---\n\n{body}\n"
    )
    knowledge = cdir / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "repo_registry.json").write_text(json.dumps({"schema_version": 1, "repos": {}}))
    (knowledge / "wheel_repos.json").write_text(json.dumps({"_comment": "x"}))
    return cdir


def test_doctor_d1_opted_out_agent_not_reported_missing_dossier(tmp_path):
    """The opt-out phrase, naming this agent's own dossier basename, suppresses
    the missing-dossier finding for `<name>.md` even though the dossier is
    genuinely absent."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    name = "cost-strategist"
    phrase = _D1_OPT_OUT_PHRASE.format(name=name)
    cdir = _claude_dir_with_single_agent(
        tmp_path,
        name,
        f"Read `.claude/oversight/{name}.md` for this repo's grounding facts.\n\n"
        f"{phrase}.\n",
    )
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # no cost-strategist.md written -- genuinely absent; this fixture also
    # never writes a manifest.json, so the ONLY finding a correctly-running
    # doctor can produce here is "manifest\tmissing" -- never the opted-out
    # agent's missing-dossier line.
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    # A crashed doctor (e.g. an uncaught exception exiting nonzero before
    # printing anything at all) would also satisfy a bare "not in
    # proc.stdout" check against empty output -- assert the actual expected
    # finding set too, so this test cannot pass against a doctor that never
    # actually ran.
    assert proc.returncode == 1
    assert proc.stdout.strip() == "manifest\tmissing\n1 findings"
    assert f"{name}\tmissing-dossier" not in proc.stdout


def test_doctor_d1_same_agent_without_opt_out_phrase_is_reported_missing_dossier(tmp_path):
    """Recovery/control twin: the identical agent, identical missing
    dossier, but WITHOUT the opt-out phrase in its text -> still reported
    missing-dossier -- proving the suppression above is driven by the phrase,
    not by anything else about this fixture."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    name = "cost-strategist"
    cdir = _claude_dir_with_single_agent(
        tmp_path,
        name,
        f"Read `.claude/oversight/{name}.md` for this repo's grounding facts.\n",
    )
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # no cost-strategist.md written -- genuinely absent, same as the opt-out test
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert f"{name}\tmissing-dossier" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_opted_out_agent_still_flags_missing_dev_runtime(tmp_path):
    """An agent that opts out of its OWN per-agent dossier but ALSO
    references `oversight/dev-runtime.md` still gets `dev-runtime
    missing-dossier` when dev-runtime.md is absent -- the opt-out phrase
    names only this agent's own dossier basename and must not blanket-
    suppress the separate dev-runtime check."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    name = "cost-strategist"
    phrase = _D1_OPT_OUT_PHRASE.format(name=name)
    cdir = _claude_dir_with_single_agent(
        tmp_path,
        name,
        f"Read `.claude/oversight/{name}.md` for this repo's grounding facts.\n"
        "Also read `.claude/oversight/dev-runtime.md` for this repo's commands.\n\n"
        f"{phrase}.\n",
    )
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # neither cost-strategist.md nor dev-runtime.md written
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert f"{name}\tmissing-dossier" not in proc.stdout
    assert "dev-runtime\tmissing-dossier" in proc.stdout
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# opt-out phrase regex tightened: an agent's text that merely mentions "No
# per-agent overrides are allowed" (an unrelated sentence about a different
# subject) somewhere near a bare `oversight/<name>.md` reference and the word
# "required" must NOT be mistaken for the real sanctioned opt-out sentence --
# only the genuine phrasing ("No per-agent `.claude/oversight/<name>.md`
# dossier is expected in any repo") suppresses the missing-dossier finding.
# ---------------------------------------------------------------------------


def test_doctor_d1_lookalike_opt_out_text_does_not_suppress_missing_dossier(tmp_path):
    """A false-positive-shaped lookalike -- 'No per-agent overrides are
    allowed' (about overrides, not about a dossier requirement) followed by
    a bare `.claude/oversight/z.md` reference and the word 'required' in an
    unrelated clause -- must still report missing-dossier: the tightened
    regex requires the real sanctioned sentence structure, not merely the
    co-occurrence of 'no per-agent', the dossier path, and 'required'
    somewhere nearby."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    name = "z"
    cdir = _claude_dir_with_single_agent(
        tmp_path,
        name,
        "No per-agent overrides are allowed. Read `.claude/oversight/z.md` "
        "-- it is required.\n",
    )
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # no z.md written -- genuinely absent
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert f"{name}\tmissing-dossier" in proc.stdout


def test_doctor_d1_real_opt_out_phrase_still_suppresses_missing_dossier(tmp_path):
    """Recovery/control twin: the GENUINE sanctioned opt-out sentence ('No
    per-agent `.claude/oversight/z.md` dossier is expected in any repo')
    still suppresses the missing-dossier finding -- proving the tightened
    regex in the lookalike test above is a narrowing, not a removal, of the
    real opt-out behavior."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    name = "z"
    cdir = _claude_dir_with_single_agent(
        tmp_path,
        name,
        "No per-agent `.claude/oversight/z.md` dossier is expected in any "
        "repo -- it is required only for agents that actually need one.\n",
    )
    (repo / ".claude" / "oversight").mkdir(parents=True, exist_ok=True)
    # no z.md written -- genuinely absent, same as the lookalike test
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert f"{name}\tmissing-dossier" not in proc.stdout


def test_doctor_flags_placeholder_tokens_in_dossier(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(
        "GCP project: __GCP_PROJECT_ID__\nRegion: __GCP_REGION__\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "sentinel\tplaceholder-left:2" in proc.stdout


def test_doctor_placeholder_recovers_once_filled_in(tmp_path):
    """Pairs with the placeholder gate: replace the placeholder tokens with
    real values and the placeholder-left finding disappears."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text("GCP project: __GCP_PROJECT_ID__\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    bad = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel\tplaceholder-left" in bad.stdout

    (oversight / "sentinel.md").write_text("GCP project: widgetco-prod-1234\n")
    good = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel\tplaceholder-left" not in good.stdout


def test_doctor_ignores_non_markdown_entries_in_oversight_dir(tmp_path):
    """A non-.md entry (e.g. a directory, mirroring the real repo's
    market-analyst/ directory alongside market-analyst.md) in oversight/ must
    never crash doctor or be treated as a dossier itself."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "market-analyst").mkdir()  # non-.md directory, must be ignored
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode in (0, 1)  # must not crash
    assert "Traceback" not in proc.stderr


def test_doctor_d1_restates_manifest_value_flagged(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    # dossier restates the literal tracker_doc value (len >= 8)
    (oversight / "sentinel.md").write_text(
        "The tracker lives at docs/launch_readiness_tracker.html, read it there.\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "sentinel.md\trestates-manifest:tracker_doc" in proc.stdout


def test_doctor_d1_recovers_once_restated_value_removed(tmp_path):
    """Pairs with the D1 gate: remove the restated literal from the dossier
    and the restates-manifest finding disappears."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(
        "The tracker lives at docs/launch_readiness_tracker.html, read it there.\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")
    bad = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:tracker_doc" in bad.stdout

    (oversight / "sentinel.md").write_text(
        "The tracker lives wherever the manifest says; read `manifest.json`'s "
        "tracker_doc key, never a hardcoded path.\n"
    )
    good = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:tracker_doc" not in good.stdout


# ---------------------------------------------------------------------------
# doctor D1 fenced-code / inline-backtick exemptions
#
# Contract (per the implementing agent's D1 rule): a manifest literal found in
# a dossier .md is a finding ONLY when it appears in prose. Two exemptions:
#   (1) inside a fenced code block (``` or ~~~)
#   (2) inside an inline backtick span whose content contains a runnable-
#       command token (grep/rg/gh/git/python3/python/ls/cat/jq/awk/sed/find/
#       wc/open/curl/head/tail/sort/diff, as a whitespace-separated word)
# A bare backticked path with no command token is NOT exempt.
#
# `test_doctor_d1_restates_manifest_value_flagged` above (plain prose) is the
# positive control for all of these; each "no finding" case below is that
# control's recovery twin by construction (same literal, same dossier
# skeleton, only the surrounding syntax differs) -- not duplicated again here.
# ---------------------------------------------------------------------------


def _d1_fixture(repo: Path, cdir: Path, sentinel_body: str):
    """Shared setup for the D1 exemption tests: a manifest with tracker_doc
    set to the exact literal under test, plus the other three referenced
    dossiers written plainly (so only sentinel.md's exemption behavior is
    under test)."""
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(sentinel_body)
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")


def test_doctor_d1_literal_in_fenced_code_block_is_exempt(tmp_path):
    """Exemption (1): the literal appears only inside a ``` fenced block ->
    no restates-manifest finding, and (since D1 is the only finding source
    here) the doctor summary is the clean OK line."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_fixture(
        repo,
        cdir,
        "Sentinel dossier body.\n\n"
        "```\n"
        "docs/launch_readiness_tracker.html\n"
        "```\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:tracker_doc" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_literal_in_command_backtick_span_is_exempt(tmp_path):
    """Exemption (2): the literal appears only inside an inline backtick span
    that also contains a runnable-command token (`grep`) -> no finding."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_fixture(
        repo,
        cdir,
        "Sentinel dossier body. Find it with "
        "`grep -c x docs/launch_readiness_tracker.html`.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:tracker_doc" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_bare_backticked_literal_alone_is_not_exempt(tmp_path):
    """A bare backticked path with NO command token in the span is NOT
    exempt -- it still counts as a finding."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_fixture(
        repo,
        cdir,
        "Sentinel dossier body. The tracker is `docs/launch_readiness_tracker.html`.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:tracker_doc" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_exempt_span_plus_prose_mention_yields_exactly_one_finding(tmp_path):
    """A dossier mixing an exempt command span AND a separate plain-prose
    mention of the same literal must report exactly ONE restates-manifest
    finding line for that dossier -- not two (no double-count across the two
    occurrences, and the exempt occurrence contributes nothing)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_fixture(
        repo,
        cdir,
        "Sentinel dossier body.\n\n"
        "Find it with `grep -c x docs/launch_readiness_tracker.html`.\n\n"
        "The tracker lives at docs/launch_readiness_tracker.html, read it there.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    matches = [
        line
        for line in proc.stdout.splitlines()
        if line == "sentinel.md\trestates-manifest:tracker_doc"
    ]
    assert len(matches) == 1
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# D1 new exemptions: a manifest literal inside a URL / markdown-link target,
# or inside an inline backtick span that is a shell variable ASSIGNMENT, is
# NOT a restatement finding. `test_doctor_d1_bare_backticked_literal_alone_is_not_exempt`
# above remains the control that a bare, non-command, non-assignment backtick
# span still flags -- this block adds the control that a bare backticked
# literal in the SAME dossier as the exempt spans below still flags exactly
# once, so the new exemptions cannot be mistaken for "nothing in this dossier
# is ever flagged."
# ---------------------------------------------------------------------------


def test_doctor_d1_literal_inside_url_is_exempt(tmp_path):
    """Exemption: the literal (github.repo, `org/repo`-shaped) appears only
    inside a bare `https://...` URL in prose -> no restates-manifest finding.
    A link is a citation to the value, not a restatement of it."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "org/repo"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        "See https://github.com/org/repo/issues/5 for the tracking issue.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.repo" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_literal_inside_markdown_link_target_is_exempt(tmp_path):
    """Exemption: the literal appears only inside a markdown link's URL
    TARGET (`[text](https://...)`), not the link text itself -> no finding.
    Prose naming the literal AGAIN, in plain text, follows on the same line
    immediately after the link's closing paren -- so this fixture can only
    pass if the URL match genuinely stops at the link's closing `)` rather
    than over-eating into (and thereby accidentally exempting) that trailing
    plain-prose mention too."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "org/repo"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        "Tracked in [#5](https://github.com/org/repo/issues/5) -- see org/repo "
        "on GitHub directly if the link ever breaks.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.repo" in proc.stdout
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# D1: the URL regex must TERMINATE at a markdown link's closing `)` -- a
# greedy `\S+`-style match that keeps consuming non-whitespace past the `)`
# would swallow whatever immediately follows the link on the same line (no
# space in between) into the "exempt URL" match, silently exempting a
# manifest literal that is actually sitting in plain prose right after the
# link, not inside it.
# ---------------------------------------------------------------------------


def test_doctor_d1_url_terminates_at_closing_paren_trailing_literal_still_flagged(tmp_path):
    """A markdown link immediately followed (no space) by a manifest literal
    on the same line -- `[link](https://x.io/a)docs/launch_readiness.html` --
    must still flag the trailing `tracker_doc` literal: the URL match has to
    stop at the link's closing `)`, not swallow the literal that follows it
    into the same (wrongly) exempted URL span."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(
        "[link](https://x.io/a)docs/launch_readiness.html\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:tracker_doc" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_literal_in_assignment_backtick_span_is_exempt(tmp_path):
    """Exemption: the literal appears only inside an inline backtick span
    that is a shell variable ASSIGNMENT (`^[A-Za-z_][A-Za-z0-9_]*=...`), the
    same re-derive idiom as a command span, just spelled as an assignment
    rather than an invocation -> no finding. Owner value is >= _D1_MIN_LEN
    (8) chars so it actually qualifies as a D1-tracked literal."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"  # 11 chars, >= _D1_MIN_LEN (8)
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        f"Set `GH_PROJECT_OWNER={owner}` before running gh project commands.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.project_owner" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_bare_backticked_literal_still_flagged_alongside_new_exemptions(tmp_path):
    """Control: a BARE backticked span (no command token, no `=`, and not a
    URL) carrying the same literal used by the new URL/assignment exemption
    tests above must still be flagged exactly once -- proving the new
    exemptions are narrow (URL / assignment-span only), not a blanket
    'nothing in backticks is ever a restatement' regression."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"  # same literal shape as the assignment-exempt test
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        f"This repo's project owner is `{owner}`.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    matches = [
        line
        for line in proc.stdout.splitlines()
        if line == "sentinel.md\trestates-manifest:github.project_owner"
    ]
    assert len(matches) == 1
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# D1: the assignment-span exemption is narrowed to SCREAMING_SNAKE_CASE
# variable names only (the real re-derive idiom, e.g. `GH_PROJECT_OWNER=`) --
# a lowercase (or mixed-case) `name=value` span, which is NOT a shell
# variable assignment idiom in this dossier convention, is NOT exempt and
# still flags as a restatement. `GH_PROJECT_OWNER=example-org` above remains
# the exempt control; this pair adds the narrowed-vs-still-exempt contrast.
# ---------------------------------------------------------------------------


def test_doctor_d1_lowercase_assignment_span_is_not_exempt(tmp_path):
    """A lowercase `name=value` backtick span (`tracker=docs/launch_
    readiness.html`) is NOT a SCREAMING_SNAKE shell-variable assignment --
    it must still flag as a restatement, unlike the real
    `GH_PROJECT_OWNER=...` idiom."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(
        "See `tracker=docs/launch_readiness.html` for the current value.\n"
    )
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:tracker_doc" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_screaming_snake_assignment_span_still_exempt(tmp_path):
    """Recovery/control twin for the narrowing above: the real
    SCREAMING_SNAKE assignment idiom (`GH_PROJECT_OWNER=example-org`) remains
    exempt -- the narrowing is specifically about casing, not a blanket
    removal of the assignment-span exemption."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"  # 11 chars, >= _D1_MIN_LEN (8)
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        f"Set `GH_PROJECT_OWNER={owner}` before running gh project commands.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.project_owner" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


# ---------------------------------------------------------------------------
# D1: an inline backtick span whose content line-wraps across a SINGLE
# embedded newline (CommonMark-legal -- rendered as a space) is still one
# span, exempt on the same terms as a single-line command/assignment span. A
# blank line still breaks a span (nothing spans one), and an unclosed
# backtick never matches at all (no runaway span swallowing the rest of the
# dossier).
# ---------------------------------------------------------------------------


def test_doctor_d1_line_wrapped_command_span_is_exempt(tmp_path):
    """The literal appears only inside a `gh ...` command span whose content
    wraps across one embedded newline in the source -> still one exempt
    command span, no restates-manifest finding."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"  # 11 chars, >= _D1_MIN_LEN (8)
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        "Run `gh project list --owner example-org\n--format json` to check.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.project_owner" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_prose_after_closed_line_wrapped_span_still_flagged(tmp_path):
    """A literal in plain prose on the line AFTER a CLOSED line-wrapped span
    is still a restatement -- the span's exemption does not leak past its own
    closing backtick."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        "Run `gh project list --owner example-org\n--format json` to check.\n"
        "The project owner is example-org, written here in plain prose.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.project_owner" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_unclosed_backtick_then_blank_line_and_literal_still_flagged(tmp_path):
    """An UNCLOSED backtick followed by a blank line and then the bare
    literal must still flag: a blank line breaks any inline span (per
    CommonMark), so the stray opening backtick never runs away and swallows
    the literal that follows into a phantom exempt span."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        "An unclosed span starts here: `gh project list --owner\n"
        "\n"
        "The project owner is example-org, written here in plain prose.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.project_owner" in proc.stdout
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# D1: an unclosed inline backtick must never run away past the NEXT list
# item and swallow a later, unrelated manifest literal into a phantom exempt
# span. `test_doctor_d1_unclosed_backtick_then_blank_line_and_literal_still_
# flagged` above already covers "unclosed backtick, then a BLANK line, then
# the literal in plain prose on its own line" -- this block adds the shape
# that actually broke: an unclosed backtick on one markdown list item, with
# NO intervening blank line, followed by MORE markdown list items (no blank
# line between list items is normal markdown, so the blank-line-breaks-a-
# span rule alone does not save this case) -- the span must still not run
# away across those list-item boundaries and eat a literal several lines
# later.
# ---------------------------------------------------------------------------


def test_doctor_d1_unclosed_backtick_does_not_run_away_across_list_items(tmp_path):
    """An unclosed backtick that opens on one bullet, with NO blank line
    before the next bullets, must not swallow a later bullet's manifest
    literal into a phantom exempt span -- even though a LATER, unrelated
    backtick (`` `jq .` ``) on a subsequent bullet exists that a naive
    non-greedy regex could wrongly treat as this span's closer."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "example-org/widgets"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        "- Run `gh project list --owner X to list projects\n"
        f"- The GH repo is {manifest_github_repo}.\n"
        "- Use `jq .` for parsing.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.repo" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_unclosed_backtick_run_away_recovers_once_span_is_closed(tmp_path):
    """Recovery twin: the identical text, but with the first bullet's
    backtick span properly CLOSED on its own line -- now a real, legitimate
    exempt command span, and the later bullet's literal is still flagged
    exactly as in the control above (closing the span must not newly exempt
    or newly swallow anything past its own close)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "example-org/widgets"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        "- Run `gh project list --owner X to list projects`\n"
        f"- The GH repo is {manifest_github_repo}.\n"
        "- Use `jq .` for parsing.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.repo" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_legitimate_three_line_wrapped_command_span_still_exempt(tmp_path):
    """Control: a GENUINE wrapped command span spanning three lines (no list
    marker on the continuation lines -- i.e. indented/plain continuation
    text, not new list items) containing the manifest literal is still
    treated as one exempt command span, same terms as the existing two-line
    wrap tests -- proving the run-away fix above is about list-item/blank-
    line boundaries, not about narrowing the wrap exemption to a single
    embedded newline."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "example-org"  # 11 chars, >= _D1_MIN_LEN (8)
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        "Run `gh project list\n  --owner example-org\n  --format json` to check.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.project_owner" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_d1_span_candidate_with_many_embedded_newlines_treated_as_prose(tmp_path):
    """A backtick-delimited span candidate whose content contains many (13)
    embedded newlines is NOT a legitimate line-wrapped inline span -- real
    Markdown inline code spans wrap across at most a couple of source lines
    in practice; a span this long is prose/a mis-typed backtick, not a
    command, and must be treated as such -- i.e. the manifest literal inside
    it is still a restatement and still flags."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "example-org/widgets"
    filler = "\n".join(f"filler line {i}" for i in range(13))
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        f"`gh project list --owner X\n{filler}\n{manifest_github_repo}`\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.repo" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d2_template_outdated(tmp_path):
    """D2 mechanics (as actually implemented): a `.bundle_version` FILE at
    `<repo>/.claude/oversight/.bundle_version` records the CLAUDE_DIR sha the
    repo last synced templates against; doctor diffs that sha against
    CLAUDE_DIR's current HEAD over `templates/oversight/`."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)

    # CLAUDE_DIR must itself be a git repo for D2's sha-diff to work.
    subprocess.run(["git", "init", "-q"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cdir, check=True)
    templates = cdir / "templates" / "oversight"
    templates.mkdir(parents=True)
    template_file = templates / "sentinel.md.tmpl"
    template_file.write_text("v1 template body\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed templates"], cwd=cdir, check=True)
    recorded_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cdir, check=True, capture_output=True, text=True
    ).stdout.strip()

    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / ".bundle_version").write_text(recorded_sha)
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    # Change the template after the recorded sha.
    template_file.write_text("v2 template body -- CHANGED\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "update template"], cwd=cdir, check=True)

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    assert "sentinel.md.tmpl\ttemplate-outdated" in proc.stdout


def test_doctor_d2_recovers_once_bundle_version_updated_to_head(tmp_path):
    """Pairs with the D2 gate: bumping `.bundle_version` to the new HEAD
    makes template-outdated disappear for that file."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cdir, check=True)
    templates = cdir / "templates" / "oversight"
    templates.mkdir(parents=True)
    template_file = templates / "sentinel.md.tmpl"
    template_file.write_text("v1 template body\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed templates"], cwd=cdir, check=True)
    recorded_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cdir, check=True, capture_output=True, text=True
    ).stdout.strip()

    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    bundle_version_path = oversight / ".bundle_version"
    bundle_version_path.write_text(recorded_sha)
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    template_file.write_text("v2 template body -- CHANGED\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "update template"], cwd=cdir, check=True)
    new_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cdir, check=True, capture_output=True, text=True
    ).stdout.strip()

    bad = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "template-outdated" in bad.stdout

    bundle_version_path.write_text(new_sha)
    good = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "template-outdated" not in good.stdout


def test_doctor_unreadable_bundle_version_sha_no_crash(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cdir, check=True)
    templates = cdir / "templates" / "oversight"
    templates.mkdir(parents=True)
    (templates / "sentinel.md.tmpl").write_text("v1\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=cdir, check=True)

    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / ".bundle_version").write_text("0000000000000000000000000000000000000000")
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "Traceback" not in proc.stderr
    assert "bundle_version\tunreadable" in proc.stdout


def test_doctor_fully_configured_repo_is_the_acceptance_oracle(tmp_path):
    """The acceptance oracle: a fully-configured repo (valid manifest, every
    referenced dossier present and clean, no template drift) must report OK:
    0 findings and exit 0."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text("Sentinel dossier body, fully written out.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body, fully written.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body, fully written.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body, fully written.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


def test_doctor_reports_n_findings_summary_line(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    # leave all dossiers missing -> at least 3 findings (sentinel, board-steward, dev-runtime)
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 1
    lines = [l for l in proc.stdout.splitlines() if l]
    summary = lines[-1]
    assert summary.endswith("findings")
    n = int(summary.split(":")[0].strip().split()[0])
    assert n >= 3
    assert summary != "OK: 0 findings"


# ---------------------------------------------------------------------------
# unknown subcommand
# ---------------------------------------------------------------------------


def test_unknown_subcommand_exits_64(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    proc = _run(["bogus-subcommand"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 64


def test_recovers_to_a_real_subcommand_after_unknown_one(tmp_path):
    """Pairs with the unknown-subcommand gate: an unknown subcommand followed
    by a real one against the same repo/env succeeds normally."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    bad = _run(["bogus-subcommand"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 64
    good = _run(["get", "product.name"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0


# ---------------------------------------------------------------------------
# --raw is a `get`-only flag: `validate`/`doctor` never accept it. Per usage,
# an unrecognized flag on those two commands is a usage error, same exit
# code (64) as an unknown subcommand -- not silently ignored.
# ---------------------------------------------------------------------------


def test_validate_with_raw_flag_exits_64(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["validate", "--raw"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 64


def test_doctor_with_raw_flag_exits_64(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    proc = _run(["doctor", "--raw"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 64


def test_recovers_to_validate_without_raw_flag_after_raw_rejection(tmp_path):
    """Pairs with the validate --raw gate: the identical manifest, same repo,
    validated WITHOUT --raw succeeds normally."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    bad = _run(["validate", "--raw"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 64
    good = _run(["validate"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0
    assert good.stdout.strip() == "OK"


def test_recovers_to_doctor_without_raw_flag_after_raw_rejection(tmp_path):
    """Pairs with the doctor --raw gate: the identical fully-configured repo,
    doctored WITHOUT --raw succeeds normally."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text("Sentinel dossier body, fully written out.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body, fully written.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body, fully written.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body, fully written.\n")

    bad = _run(["doctor", "--raw"], cwd=repo, env=_base_env(cdir))
    assert bad.returncode == 64
    good = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert good.returncode == 0
    assert good.stdout.strip() == "OK: 0 findings"


# ---------------------------------------------------------------------------
# D2 sha validation (security): a `.bundle_version` value that is not a real
# 40-hex sha must never be interpolated into the `git diff` argv in a way
# that lets it act as a flag/option -- it must be rejected up front as
# `bundle_version\tunreadable`, and doctor must never touch the filesystem
# on its behalf. Recovery twin: a genuinely valid sha continues to work
# (reusing the existing D2 fixtures, `test_doctor_d2_recovers_once_
# bundle_version_updated_to_head` already covers the plain-valid-sha path;
# this section adds the adversarial-value coverage the contract calls for).
# ---------------------------------------------------------------------------


def _d2_git_claude_dir(cdir: Path) -> str:
    """Turn `cdir` into a real git repo with a `templates/oversight/` tree,
    mirroring the shared D2 fixture setup already used above, and return
    HEAD's sha."""
    subprocess.run(["git", "init", "-q"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=cdir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=cdir, check=True)
    templates = cdir / "templates" / "oversight"
    templates.mkdir(parents=True)
    (templates / "sentinel.md.tmpl").write_text("v1 template body\n")
    subprocess.run(["git", "add", "-A"], cwd=cdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed templates"], cwd=cdir, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cdir, check=True, capture_output=True, text=True
    ).stdout.strip()


def _d2_repo_fixture(repo: Path, bundle_version_value: str) -> None:
    _write_manifest(repo, _valid_manifest(repo))
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / ".bundle_version").write_text(bundle_version_value)
    (oversight / "sentinel.md").write_text("Sentinel dossier body.\n")
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")


def test_doctor_d2_option_injection_sha_rejected_and_no_file_written(tmp_path):
    """A `.bundle_version` value crafted to look like a git-diff option
    (`--output=<path>`) must be rejected as `bundle_version\\tunreadable`
    and must NEVER cause `git diff` to actually write the named file."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d2_git_claude_dir(cdir)

    pwned = tmp_path / "PWNED.txt"
    _d2_repo_fixture(repo, f"--output={pwned}")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert proc.stdout.count("bundle_version\tunreadable") == 1
    lines = [l for l in proc.stdout.splitlines() if l]
    assert lines[0] == "bundle_version\tunreadable" or "bundle_version\tunreadable" in lines
    assert not pwned.exists()


def test_doctor_d2_option_injection_pager_flag_rejected_and_no_file_written(tmp_path):
    """A second option-injection shape (`-c core.pager=...`) is rejected the
    same way -- confirms the fix is a real validation, not a single-string
    denylist entry for `--output` alone."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d2_git_claude_dir(cdir)

    pwned = tmp_path / "PWNED2.txt"
    _d2_repo_fixture(repo, f"-c core.pager=x")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "bundle_version\tunreadable" in proc.stdout
    assert not pwned.exists()


def test_doctor_d2_too_short_value_rejected(tmp_path):
    """A value that is not a plausible 40-hex sha at all (too short) must
    also be rejected as unreadable, never passed to git."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d2_git_claude_dir(cdir)

    _d2_repo_fixture(repo, "abc")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "bundle_version\tunreadable" in proc.stdout


def test_doctor_d2_valid_sha_recovery_no_finding(tmp_path):
    """Recovery twin for all three rejection cases above: a genuine 40-hex
    sha equal to CLAUDE_DIR's own HEAD (no template drift since) produces
    NO `bundle_version` finding at all -- reusing the same fixture shape as
    the existing D2 tests, to show the fix does not regress the valid path."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    head_sha = _d2_git_claude_dir(cdir)

    _d2_repo_fixture(repo, head_sha)

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "bundle_version" not in proc.stdout


# ---------------------------------------------------------------------------
# register: atomic registry write
# ---------------------------------------------------------------------------


def test_register_leaves_no_tmp_file_in_knowledge_dir(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0

    leftover_tmp = list((cdir / "knowledge").glob("*.tmp"))
    assert leftover_tmp == []


def test_register_write_failure_never_corrupts_existing_registry_files(tmp_path):
    """Falsifiable atomicity check: make `knowledge/` read-only for NEW files
    (existing json files remain individually writable) so the atomic
    `.tmp` + os.replace write cannot land, and confirm the existing
    wheel_repos.json / repo_registry.json content is untouched -- still
    valid, still parseable to its PRIOR content -- even though `register`'s
    own write fails (a nonzero exit is acceptable; content corruption is
    not)."""
    _skip_if_absent()
    if hasattr(os, "getuid") and os.getuid() == 0:
        pytest.skip("running as root: chmod 0o555 does not block root's own writes")

    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    _write_manifest(repo, _valid_manifest(repo))
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    knowledge = cdir / "knowledge"
    registry_path = knowledge / "repo_registry.json"
    wheel_path = knowledge / "wheel_repos.json"
    before_registry = registry_path.read_text(encoding="utf-8")
    before_wheel = wheel_path.read_text(encoding="utf-8")

    original_mode = knowledge.stat().st_mode
    try:
        knowledge.chmod(0o555)  # r-xr-xr-x: no new file creation, dir entries unlisted-writable
        proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
        # The write is expected to fail; a nonzero exit is acceptable. What is
        # NOT acceptable is a truncated/corrupted existing file.
        after_registry = registry_path.read_text(encoding="utf-8")
        after_wheel = wheel_path.read_text(encoding="utf-8")
        assert json.loads(after_registry) == json.loads(before_registry)
        assert json.loads(after_wheel) == json.loads(before_wheel)
        # No .tmp debris left behind by a failed attempt either.
        assert list(knowledge.glob("*.tmp")) == []
    finally:
        knowledge.chmod(original_mode)


# ---------------------------------------------------------------------------
# register: ensure_ascii=False (non-ASCII content preserved literally)
# ---------------------------------------------------------------------------


def test_register_wheel_repos_write_preserves_non_ascii_literally(tmp_path):
    """The `_comment` field in the fixture wheel_repos.json is seeded with
    real non-ASCII characters (em dash, section sign); after `register`
    upserts a new slug into the same file, those characters must still be
    present as literal UTF-8 text in the raw file bytes -- never escaped to
    `\\u2014`/`\\u00a7` (which is what `ensure_ascii=True`, the json.dumps
    default, would produce)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    manifest["wheel"] = {
        "tier0_statuses": ["failed"],
        "tier1_statuses": ["local"],
        "estimate_loop_exclusive_prefixes": [],
        "trust_surface_prefixes": [],
        "mandatory_registration_paths": [],
        "venv_python": ".venv/bin/python",
        "board_regen_command": None,
    }
    _write_manifest(repo, manifest)

    wheel_path = cdir / "knowledge" / "wheel_repos.json"
    wheel_path.write_text(json.dumps({"_comment": "note — see §4 for details"}))

    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")
    proc = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert proc.returncode == 0

    raw = wheel_path.read_text(encoding="utf-8")
    assert "—" in raw
    assert "§" in raw
    assert "\\u2014" not in raw
    assert "\\u00a7" not in raw
    parsed = json.loads(raw)
    assert parsed["_comment"] == "note — see §4 for details"


# ---------------------------------------------------------------------------
# register: canonical multi-line indent=2 array style, and idempotence over it
# ---------------------------------------------------------------------------


def test_register_writes_multiline_indent2_array_style_and_stays_idempotent(tmp_path):
    """Extends the existing idempotence coverage (`test_register_is_idempotent_
    second_run_unchanged`) to also assert the canonical on-disk style: a JSON
    array value (e.g. `wheel.tier1_statuses`) is written as a genuine
    multi-line, indent=2 block -- not a single-line compact array -- and a
    second `register` run against that exact style still reports
    `unchanged` for both registry files (true idempotence over the
    canonical style itself, not just over some other compact style)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path, name="widgetco_repo")
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\n")
    manifest["wheel"] = {
        "tier0_statuses": ["failed", "blocked"],
        "tier1_statuses": ["local"],
        "estimate_loop_exclusive_prefixes": [],
        "trust_surface_prefixes": [],
        "mandatory_registration_paths": [],
        "venv_python": ".venv/bin/python",
        "board_regen_command": None,
    }
    _write_manifest(repo, manifest)
    gh_bin = _fake_gh(tmp_path, tmp_path / "gh_calls.log")

    first = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert first.returncode == 0
    assert "updated" in first.stdout

    wheel_text = (cdir / "knowledge" / "wheel_repos.json").read_text(encoding="utf-8")
    assert '"tier1_statuses": [\n' in wheel_text
    assert '"tier0_statuses": [\n' in wheel_text
    # not the single-line compact form
    assert '"tier1_statuses": ["local"]' not in wheel_text

    second = _run(["register"], cwd=repo, env=_base_env(cdir, extra_path=gh_bin))
    assert second.returncode == 0
    assert "unchanged" in second.stdout
    assert "updated" not in second.stdout


# ---------------------------------------------------------------------------
# D1 widened keys: github.repo / github.project_owner / gtm.inbox_label /
# EXPANDED oversight.report_dir now also flagged; product.name stays
# excluded (documented exclusion, not a bug); pointer-form phrasing recovers.
# ---------------------------------------------------------------------------


def _d1_widened_fixture(repo: Path, extra_manifest: dict, sentinel_body: str) -> None:
    manifest = _valid_manifest(repo)
    manifest.update(extra_manifest)
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "sentinel.md").write_text(sentinel_body)
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")


def test_doctor_d1_widened_flags_github_repo_restated_in_prose(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest_github_repo = "acme/widgetco"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": manifest_github_repo}},
        f"This app's GitHub repo is {manifest_github_repo}, use it for gh commands.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.repo" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_widened_flags_github_project_owner_restated_in_prose(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    owner = "WidgetCoOrgOwner"
    _d1_widened_fixture(
        repo,
        {"github": {"repo": "acme/widgetco", "project_owner": owner}},
        f"Pass --owner {owner} to gh project commands for this repo.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:github.project_owner" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_widened_flags_gtm_inbox_label_restated_in_prose(tmp_path):
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    label = "dept:marketing"
    _d1_widened_fixture(
        repo,
        {"gtm": {"missions_dir": "missions", "inbox_label": label}},
        f"File GTM findings with the {label} label on this repo.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:gtm.inbox_label" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_widened_flags_expanded_report_dir_restated_in_prose(tmp_path):
    """`oversight.report_dir` in the manifest holds the UNEXPANDED
    `${slug}` form; the dossier restatement to catch is the EXPANDED value
    (what `get oversight.report_dir` actually prints, e.g. `reports/
    widgetco`) since that is the literal an agent would actually paste."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    expanded = "reports/widgetco"  # slug is "widgetco" per _valid_manifest
    _d1_widened_fixture(
        repo,
        {"oversight": {"tracking_issue": None, "report_dir": "reports/${slug}"}},
        f"Weekly reports land in {expanded}, read them there.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "sentinel.md\trestates-manifest:oversight.report_dir" in proc.stdout
    assert proc.returncode == 1


def test_doctor_d1_product_name_in_prose_is_documented_exclusion_no_finding(tmp_path):
    """`product.name` is a DOCUMENTED exclusion from D1: a dossier that
    mentions the product's plain-English name in prose must never be
    flagged as restating the manifest (a product's own name necessarily
    appears all over prose describing it; that is not a hardcoded-fact
    restatement in the sense D1 exists to catch)."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_widened_fixture(
        repo,
        {},
        "Widget Co is the app this dossier grounds; read on for its facts.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:product.name" not in proc.stdout


def test_doctor_d1_widened_pointer_form_recovers_no_finding(tmp_path):
    """Recovery twin for the widened-keys gates above: phrasing the dossier
    as a POINTER to the manifest key, rather than restating the literal
    value, produces no finding for any of the newly-widened keys."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    _d1_widened_fixture(
        repo,
        {
            "github": {"repo": "acme/widgetco", "project_owner": "WidgetCoOrgOwner"},
            "gtm": {"missions_dir": "missions", "inbox_label": "dept:marketing"},
            "oversight": {"tracking_issue": None, "report_dir": "reports/${slug}"},
        },
        "See manifest.json -> github.repo, github.project_owner, "
        "gtm.inbox_label, and oversight.report_dir for this repo's current "
        "values; never hardcode them here.\n",
    )
    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:github.repo" not in proc.stdout
    assert "restates-manifest:github.project_owner" not in proc.stdout
    assert "restates-manifest:gtm.inbox_label" not in proc.stdout
    assert "restates-manifest:oversight.report_dir" not in proc.stdout


# ---------------------------------------------------------------------------
# D1: CRLF line endings inside a fenced code block must not defeat the
# fenced-block exemption.
# ---------------------------------------------------------------------------


def test_doctor_d1_crlf_fenced_block_is_still_exempt(tmp_path):
    """The exact same fenced-block exemption already covered by
    `test_doctor_d1_literal_in_fenced_code_block_is_exempt` above, but with
    the dossier file's fence and its content written using CRLF (\\r\\n)
    line endings throughout -- a real-world artifact of an editor or a
    Windows-authored dossier. The fence regex must still recognize the
    block and exempt the literal inside it."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["tracker_doc"] = "docs/launch_readiness_tracker.html"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "launch_readiness_tracker.html").write_text("<html></html>")
    _write_manifest(repo, manifest)
    oversight = repo / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    crlf_body = (
        "Sentinel dossier body.\r\n\r\n"
        "```\r\n"
        "docs/launch_readiness_tracker.html\r\n"
        "```\r\n"
    )
    with open(oversight / "sentinel.md", "wb") as fh:
        fh.write(crlf_body.encode("utf-8"))
    (oversight / "board-steward.md").write_text("Board steward dossier body.\n")
    (oversight / "market-analyst.md").write_text("Market analyst dossier body.\n")
    (oversight / "dev-runtime.md").write_text("Dev runtime dossier body.\n")

    proc = _run(["doctor"], cwd=repo, env=_base_env(cdir))
    assert "restates-manifest:tracker_doc" not in proc.stdout
    assert proc.returncode == 0
    assert proc.stdout.strip() == "OK: 0 findings"


# ---------------------------------------------------------------------------
# get: ${slug} expands in ANY string value, not only oversight.report_dir
# ---------------------------------------------------------------------------


def test_get_slug_substitution_expands_in_any_string_value(tmp_path):
    """The contract widens `${slug}` substitution to every string value
    returned by `get`, not just the hardcoded `oversight.report_dir` case
    already covered by `test_get_slug_substitution_in_report_dir`. Use an
    unrelated, NON-path-typed top-level key (`gtm.inbox_label`) to prove it
    is not special-cased to one dotted key -- `tracker_doc` is excluded here
    because it is one of `_PATH_KEYS` and is separately anchored absolute by
    `get` (covered by the get-path-key tests above), which would conflate
    that unrelated behavior with the ${slug}-expansion behavior this test
    exists to prove."""
    _skip_if_absent()
    repo = _git_repo(tmp_path)
    cdir = _fake_claude_dir(tmp_path)
    manifest = _valid_manifest(repo)
    manifest["gtm"]["inbox_label"] = "dept:${slug}"
    _write_manifest(repo, manifest)

    proc = _run(["get", "gtm.inbox_label"], cwd=repo, env=_base_env(cdir))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "dept:widgetco"
