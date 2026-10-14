"""Blocker 1: company.py gitignore generator, tested against the REAL
Brightline migration layout from plan §14 P1's path map (paths pointing at
tracking/activity_log, tracking/snapshots, gtm_mission, data, build) using
real `git check-ignore`, plus the default layout.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


def _brightline_layout_pack() -> dict:
    return {
        "paths": {
            "missions_dir": "gtm_mission",
            "mission_records": "ignored",
            "activity_log_dir": "tracking/activity_log",
            "scoreboard": "tracking/scoreboard.csv",
            "snapshots_dir": "tracking/snapshots",
            "metrics": "tracking/METRICS.md",
            "feature_inventory_dir": "tracking/activity_log/feature_inventory",
            "plans_dir": "plans",
            "data_dir": "data",
            "build_dir": "build",
        }
    }


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


def test_brightline_layout_every_named_path(tmp_path):
    pack = _brightline_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)

    cases = {
        "tracking/activity_log/ACTIVITY_LOG.jsonl": True,
        "tracking/activity_log/TOOL_TRAIL.jsonl": True,
        "tracking/activity_log/ACTIVITY_LOG.md": True,
        "tracking/activity_log/feature_inventory/gbp.csv": False,
        "tracking/METRICS.md": False,
        "tracking/snapshots/2026-01-01/report.md": False,
        "tracking/snapshots/2026-01-01/raw_page.html": True,
        "data/leads.jsonl": True,
        "build/web/index.html": True,
        "gtm_mission/gtm_reviewed.jsonl": True,
        "gtm_mission/impl_seo.md": False,
    }
    for rel_path, expect_ignored in cases.items():
        _touch(repo, rel_path)
        ignored = _is_ignored(repo, rel_path)
        assert ignored == expect_ignored, f"{rel_path}: expected ignored={expect_ignored}, got {ignored}"


def test_brightline_layout_metrics_json_also_tracked(tmp_path):
    """metrics.json (not just METRICS.md) must also stay tracked -- §3.2's
    tracked-config class covers both forms of the metrics file."""
    pack = _brightline_layout_pack()
    pack["paths"]["metrics"] = "tracking/metrics.json"
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/metrics.json")
    assert not _is_ignored(repo, "tracking/metrics.json")


def test_brightline_layout_scoreboard_ignored(tmp_path):
    pack = _brightline_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/scoreboard.csv")
    assert _is_ignored(repo, "tracking/scoreboard.csv")


def test_brightline_layout_feature_inventory_never_ignored_even_nested_in_activity_log_dir(tmp_path):
    """RED-check: remove the feature_inventory_dir negation block in
    generate_gitignore (the `nested` check) and this fails -- because
    feature_inventory_dir here (tracking/activity_log/feature_inventory)
    IS nested inside activity_log_dir (tracking/activity_log), the bare
    activity_log_dir/*.jsonl and *.md rules alone would not ignore CSVs,
    but a broader accidental "ignore everything under activity_log_dir"
    rule would -- this test guards against that regression specifically at
    the nested-path shape the Brightline layout actually uses."""
    pack = _brightline_layout_pack()
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)
    _touch(repo, "tracking/activity_log/feature_inventory/gbp.csv")
    _touch(repo, "tracking/activity_log/feature_inventory/yelp.csv")
    assert not _is_ignored(repo, "tracking/activity_log/feature_inventory/gbp.csv")
    assert not _is_ignored(repo, "tracking/activity_log/feature_inventory/yelp.csv")


def test_default_layout_every_named_path(tmp_path):
    """Same assertions against the DEFAULT layout (.claude/gtm/state/...),
    not just the Brightline migration layout."""
    pack = {
        "paths": {
            "missions_dir": "gtm_mission",
            "mission_records": "ignored",
            "activity_log_dir": ".claude/gtm/state/activity_log",
            "scoreboard": ".claude/gtm/state/scoreboard.csv",
            "snapshots_dir": ".claude/gtm/state/snapshots",
            "metrics": ".claude/gtm/metrics.json",
            "feature_inventory_dir": ".claude/gtm/feature_inventory",
            "plans_dir": ".claude/gtm/plans",
            "data_dir": ".claude/gtm/data",
        }
    }
    text = company.generate_gitignore(pack)
    repo = _make_repo_with_gitignore(tmp_path, text)

    cases = {
        ".claude/gtm/state/activity_log/ACTIVITY_LOG.jsonl": True,
        ".claude/gtm/state/activity_log/TOOL_TRAIL.jsonl": True,
        ".claude/gtm/state/activity_log/ACTIVITY_LOG.md": True,
        ".claude/gtm/feature_inventory/gbp.csv": False,
        ".claude/gtm/metrics.json": False,
        # B3: a snapshots_dir living UNDER .claude/gtm/state/ has no .md
        # negation -- it is fully covered by the plain, unconditional
        # state/ ignore (the negation form is reserved for a snapshots_dir
        # OUTSIDE state/, see the Brightline-layout test above).
        ".claude/gtm/state/snapshots/2026-01-01/report.md": True,
        ".claude/gtm/state/snapshots/2026-01-01/raw.html": True,
        ".claude/gtm/data/leads.jsonl": True,
        "gtm_mission/gtm_reviewed.jsonl": True,
        "gtm_mission/impl_seo.md": False,
        # runtime cross-session state under .claude/gtm/state/ itself
        ".claude/gtm/state/actions.jsonl": True,
        ".claude/gtm/state/inbox.jsonl": True,
    }
    for rel_path, expect_ignored in cases.items():
        _touch(repo, rel_path)
        ignored = _is_ignored(repo, rel_path)
        assert ignored == expect_ignored, f"{rel_path}: expected ignored={expect_ignored}, got {ignored}"


def test_default_layout_no_build_dir_means_no_build_ignore_lines(tmp_path):
    pack = {
        "paths": {
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
    }
    text = company.generate_gitignore(pack)
    assert "build" not in text
