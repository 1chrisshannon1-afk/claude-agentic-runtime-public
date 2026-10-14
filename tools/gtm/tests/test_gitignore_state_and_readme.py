"""B3: .gitignore generator fixes, verified with real `git check-ignore`:
1. Default layout: state/reports/*.md and state/cycles/*.md are always
   ignored (the .md negation is reserved for a snapshots_dir NOT under
   state).
2. .claude/gtm/data/ stays ignored even when data_dir is elsewhere.
3. activity_log_dir ignores its exact machine-written filenames only --
   never README.md or feature_inventory/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


def _make_repo_with_gitignore(tmp_path: Path, gitignore_text: str) -> Path:
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(gitignore_text, encoding="utf-8")
    return repo


def _touch(repo: Path, rel_path: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")


def _is_ignored(repo: Path, rel_path: str) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", rel_path], cwd=repo)
    return result.returncode == 0


def _default_layout_pack(**overrides) -> dict:
    paths = {
        "missions_dir": "gtm_mission",
        "mission_records": "tracked",
        "activity_log_dir": ".claude/gtm/state/activity_log",
        "scoreboard": ".claude/gtm/state/scoreboard.csv",
        "snapshots_dir": ".claude/gtm/state/snapshots",
        "metrics": ".claude/gtm/metrics.json",
        "feature_inventory_dir": ".claude/gtm/feature_inventory",
        "plans_dir": ".claude/gtm/plans",
        "data_dir": ".claude/gtm/data",
    }
    paths.update(overrides)
    return {"paths": paths}


# --------------------------------------------------------------------------
# 1. state/reports/*.md and state/cycles/*.md always ignored
# --------------------------------------------------------------------------


def test_state_reports_md_always_ignored(tmp_path):
    """RED-check: revert the plain `.claude/gtm/state/` line to the old
    `.claude/gtm/state/**` + `!.claude/gtm/state/**/*.md` negation form and
    this fails -- state/reports/weekly.md would be wrongly re-included."""
    pack = _default_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, ".claude/gtm/state/reports/weekly.md")
    assert _is_ignored(repo, ".claude/gtm/state/reports/weekly.md")


def test_state_cycles_md_always_ignored(tmp_path):
    pack = _default_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, ".claude/gtm/state/cycles/cyc_brightline_weekly_2026_09_27.md")
    assert _is_ignored(repo, ".claude/gtm/state/cycles/cyc_brightline_weekly_2026_09_27.md")


def test_snapshots_outside_state_keeps_md_negation(tmp_path):
    """Paired recovery test: a snapshots_dir OUTSIDE state/ (the Brightline
    layout) still keeps its .md negation -- this rule change is scoped to
    UNDER-state snapshots only."""
    pack = _default_layout_pack(snapshots_dir="tracking/snapshots")
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/snapshots/2026-01-01/DEEP_DIVE.md")
    _touch(repo, "tracking/snapshots/2026-01-01/raw_page.html")
    assert not _is_ignored(repo, "tracking/snapshots/2026-01-01/DEEP_DIVE.md")
    assert _is_ignored(repo, "tracking/snapshots/2026-01-01/raw_page.html")


# --------------------------------------------------------------------------
# 2. .claude/gtm/data/ stays ignored even when data_dir is elsewhere
# --------------------------------------------------------------------------


def test_fixed_runtime_data_dir_ignored_even_when_data_dir_elsewhere(tmp_path):
    """RED-check: this only works because generate_gitignore ALWAYS emits
    a plain `.claude/gtm/data/` line regardless of paths.data_dir -- change
    it to emit that fixed line ONLY when data_dir == the fixed default and
    this fails when data_dir points elsewhere (e.g. a top-level "data")."""
    pack = _default_layout_pack(data_dir="data")
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, ".claude/gtm/data/leftover_from_default_layout.jsonl")
    _touch(repo, "data/leads.jsonl")
    assert _is_ignored(repo, ".claude/gtm/data/leftover_from_default_layout.jsonl")
    assert _is_ignored(repo, "data/leads.jsonl")


def test_no_duplicate_data_dir_line_when_data_dir_is_the_default(tmp_path):
    """When data_dir IS the fixed default location, the generator must not
    emit the same ignore line twice."""
    pack = _default_layout_pack(data_dir=".claude/gtm/data")
    text = company.generate_gitignore(pack)
    assert text.count(".claude/gtm/data/") == 1


# --------------------------------------------------------------------------
# 3. activity_log_dir: exact filenames only -- never README.md or
#    feature_inventory/
# --------------------------------------------------------------------------


def test_activity_log_dir_ignores_exact_machine_written_names(tmp_path):
    pack = _default_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    for name in ("ACTIVITY_LOG.jsonl", "TOOL_TRAIL.jsonl", "ACTIVITY_LOG.md", ".activity_log.lock"):
        _touch(repo, f".claude/gtm/state/activity_log/{name}")
        assert _is_ignored(repo, f".claude/gtm/state/activity_log/{name}"), name


def test_activity_log_dir_never_ignores_readme(tmp_path):
    """RED-check: revert to the old `{activity_log_dir}/*.md` glob (instead
    of the exact `ACTIVITY_LOG.md` filename) and this fails -- a real
    README.md sitting in activity_log_dir (as the Brightline migration's
    does) would be wrongly ignored too."""
    pack = _default_layout_pack(activity_log_dir="tracking/activity_log")
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/activity_log/README.md")
    assert not _is_ignored(repo, "tracking/activity_log/README.md")


def test_activity_log_dir_never_ignores_feature_inventory(tmp_path):
    pack = _default_layout_pack(
        activity_log_dir="tracking/activity_log",
        feature_inventory_dir="tracking/activity_log/feature_inventory",
    )
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/activity_log/feature_inventory/gbp.csv")
    assert not _is_ignored(repo, "tracking/activity_log/feature_inventory/gbp.csv")


# --------------------------------------------------------------------------
# #24: TOOL_TRAIL.jsonl.ids (and its .tmp staging file) ignored in every
# layout, by exact name, same as the trail file it shadows.
# --------------------------------------------------------------------------


def test_default_layout_ignores_trail_sidecar(tmp_path):
    """RED-check: remove the TOOL_TRAIL.jsonl.ids line(s) from
    generate_gitignore and this fails -- the sidecar membership index
    (minor 17/#20) would be trackable, exactly the class of file the
    trail's own *.jsonl exact-name ignore rule exists to keep untracked."""
    pack = _default_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, ".claude/gtm/state/activity_log/TOOL_TRAIL.jsonl.ids")
    assert _is_ignored(repo, ".claude/gtm/state/activity_log/TOOL_TRAIL.jsonl.ids")


def test_default_layout_ignores_trail_sidecar_tmp_staging_file(tmp_path):
    """RED-check against the REAL temp-name shape, in the Brightline layout
    (activity_log_dir outside state/, where the blanket state/ ignore can't
    accidentally cover it): `_write_sidecar_with_header` (activity_log.py)
    writes its staging file via `tempfile.mkstemp(prefix=sidecar.name +
    ".", suffix=".tmp", ...)`, so the file that actually lands on disk is
    named like `TOOL_TRAIL.jsonl.ids.bloxwshh.tmp` -- never the fixed
    literal `TOOL_TRAIL.jsonl.ids.tmp` the old version of this test
    asserted against (a name the code never writes, so the old assertion
    passed without proving the intended behavior at all). Revert
    generate_gitignore's `TOOL_TRAIL.jsonl.ids.*.tmp` glob line and this
    fails."""
    pack = _default_layout_pack(activity_log_dir="tracking/activity_log")
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/activity_log/TOOL_TRAIL.jsonl.ids.bloxwshh.tmp")
    assert _is_ignored(repo, "tracking/activity_log/TOOL_TRAIL.jsonl.ids.bloxwshh.tmp")


def test_brightline_layout_ignores_trail_sidecar(tmp_path):
    """Same coverage against the Brightline-style migration layout
    (activity_log_dir outside .claude/gtm/state/) -- the sidecar-ignore
    rule must not be an accident of the default layout's blanket state/
    ignore; activity_log_dir's own exact-name rules must cover it too."""
    pack = _default_layout_pack(activity_log_dir="tracking/activity_log")
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/activity_log/TOOL_TRAIL.jsonl.ids")
    assert _is_ignored(repo, "tracking/activity_log/TOOL_TRAIL.jsonl.ids")
