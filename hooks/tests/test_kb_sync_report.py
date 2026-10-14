"""Tests for kb_sync_report.py (Plan C unit C9). Intended behavior per plan section C9 / C-7."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# kb_sync_report.py lives in scripts/ (the checkout root's sibling of hooks/); this
# test moved here from scripts/ so the one suite run (`hooks/tests`) covers it.
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import kb_sync_report as kb  # noqa: E402

UTC_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)  # heartbeat_audit._UTC_TS_RE
REQUIRED = ("job", "started_at", "finished_at", "exit", "cadence", "summary")


def git(root: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": "2026-10-01T12:00:00",
        "GIT_COMMITTER_DATE": "2026-10-01T12:00:00",
    }
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


def commit_file(root: Path, rel: str, content: str, date: str = "2026-10-01T12:00:00") -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    git(root, "add", rel)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
    }
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", f"edit {rel}"], check=True, env=env
    )
    return git(root, "rev-parse", "HEAD")


class FakePoster:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, Path]] = []

    def __call__(self, issue: int, body: str, cwd: Path) -> None:
        self.calls.append((issue, body, cwd))


def block(name: str, path: str, sha: str, rewritten: bool = False) -> str:
    rw = "- rewritten: yes (staged from original)\n" if rewritten else ""
    return (
        f"### {name}\n- runtime path: ~/.claude/{path}\n- runtime sha: {sha}\n{rw}"
        '- port date: 2026-10-07\n- frontmatter stripped: no\n- coverage:\n  - para L3 "x" | kept |\n\n'
    )


@pytest.fixture()
def world(tmp_path: Path) -> dict:
    rt = tmp_path / "rt"
    rt.mkdir()
    git(rt, "init", "-q")
    git(rt, "config", "commit.gpgsign", "false")
    sha_direct = commit_file(rt, "knowledge/marketing_kb/a.md", "a1")
    sha_rw = commit_file(rt, "knowledge/cost_primer.md", "c1")
    commit_file(rt, "knowledge/marketing_kb/compliance/hipaa.md", "h1")
    (rt / "knowledge" / "repo_registry.json").write_text(
        ""
    )  # untracked placeholder, replaced below
    ag = tmp_path / "agency"
    doc = ag / kb.DOCTRINE_REL
    (doc / "agnostic" / "seo").mkdir(parents=True)
    (doc / "agnostic" / "seo" / "PORT_SOURCES.md").write_text(
        "# Port sources: seo\n\n"
        + block("a.md", "knowledge/marketing_kb/a.md", sha_direct)
        + block("cost.md", "knowledge/cost_primer.md", sha_rw, rewritten=True)
    )
    (doc / "agnostic" / "measurement").mkdir(parents=True)
    (doc / "agnostic" / "measurement" / "PORT_SOURCES.md").write_text(
        "### ads-recon.md\n- repo path: departments/marketing/ads/rag/reconciliation.md (staged)\n"
        "- repo sha: c97eb86251898a2bb5716f60a64fd543c4bde7d7\n- port date: 2026-10-07\n"
    )
    (doc / "industry" / "dental" / "compliance").mkdir(parents=True)
    (doc / "industry" / "dental" / "compliance" / "SOURCES.md").write_text(
        "# Sources: dental compliance overlay (last read 2026-10-06 unless noted)\n\n"
        "- ~/.claude/knowledge/marketing_kb/compliance/hipaa.md (runtime file) - read 2026-10-06.\n"
        "- https://example.org/x (url)\n"
    )
    (rt / "schedules").mkdir()
    (rt / "knowledge").mkdir(exist_ok=True)
    (rt / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"repos": {"agency": {"root": str(ag)}}})
    )
    return {"rt": rt, "ag": ag, "sha_direct": sha_direct, "sha_rw": sha_rw}


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        + str(p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def hb(rt: Path) -> dict:
    return json.loads((rt / "schedules" / "heartbeats" / f"{kb.JOB}.json").read_text())


def test_no_change_posts_no_comment(world: dict) -> None:
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    assert poster.calls == []
    assert hb(world["rt"])["exit"] == 0


def test_changed_direct_source_is_reported_as_report(world: dict) -> None:
    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    assert len(poster.calls) == 1
    issue, body, _ = poster.calls[0]
    assert issue == 5496
    assert "re-port (1)" in body and "seo/a.md" in body
    assert "rewrite review needed" not in body


def test_changed_rewritten_source_is_rewrite_review_never_report(world: dict) -> None:
    commit_file(world["rt"], "knowledge/cost_primer.md", "c2", date="2026-10-05T12:00:00")
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    assert len(poster.calls) == 1
    body = poster.calls[0][1]
    assert "rewrite review needed (1)" in body and "seo/cost.md" in body
    assert "re-port (" not in body


def test_changed_overlay_citation_is_overlay_review(world: dict) -> None:
    commit_file(
        world["rt"], "knowledge/marketing_kb/compliance/hipaa.md", "h2", date="2026-10-08T12:00:00"
    )
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    body = poster.calls[0][1]
    assert "overlay review needed (1)" in body and "dental/compliance" in body
    assert "re-port (" not in body


def test_overlay_edit_before_read_date_is_not_flagged(world: dict) -> None:
    # hipaa.md was committed 2026-10-01, before the overlay's 2026-10-06 read.
    poster = FakePoster()
    kb.run(world["rt"], poster)
    assert poster.calls == []


def test_repo_sourced_block_skipped_and_reported_once_without_comment(world: dict, capsys) -> None:
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    assert poster.calls == []
    assert capsys.readouterr().out.count("repo-sourced, not tracked by this sync") == 1


def test_never_ported_listed_but_alone_does_not_comment(world: dict, capsys) -> None:
    poster = FakePoster()
    kb.run(world["rt"], poster)
    out = capsys.readouterr().out
    assert (
        "knowledge/marketing_kb/compliance/hipaa.md" in out
    )  # never ported (cited by overlay only)
    assert poster.calls == []


@pytest.mark.parametrize("name", ["DISABLED", "DISABLED.kbsync"])
def test_disabled_skips_run(world: dict, name: str) -> None:
    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    (world["rt"] / "schedules" / name).write_text("")
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 0
    assert poster.calls == []
    assert hb(world["rt"])["summary"] == "skipped-disabled"


def test_heartbeat_has_required_keys_and_utc_z_timestamps(world: dict) -> None:
    kb.run(world["rt"], FakePoster())
    data = hb(world["rt"])
    assert all(k in data for k in REQUIRED)
    assert UTC_TS_RE.match(data["started_at"]) and UTC_TS_RE.match(data["finished_at"])
    assert data["job"] == "com.oversight.agency.kbsync"


def test_start_stub_precedes_end_and_crash_is_not_success(world: dict) -> None:
    def boom(issue: int, body: str, cwd: Path) -> None:
        raise RuntimeError("boom")

    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    with pytest.raises(RuntimeError):
        kb.run(world["rt"], boom)
    data = hb(world["rt"])
    assert (
        data["exit"] == 1
        and data["finished_at"] is not None
        and data["summary"].startswith("FAILED")
    )


def test_gh_failure_exits_nonzero_with_heartbeat_exit(world: dict) -> None:
    def failing(issue: int, body: str, cwd: Path) -> None:
        raise kb.SyncError("gh down")

    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    assert kb.run(world["rt"], failing) == 1
    assert hb(world["rt"])["exit"] == 1


def test_unreachable_sha_is_cannot_compare_and_posts_nothing(world: dict, capsys) -> None:
    ps = world["ag"] / kb.DOCTRINE_REL / "agnostic" / "seo" / "PORT_SOURCES.md"
    ps.write_text(ps.read_text().replace(world["sha_direct"], "deadbeef" * 5))
    commit_file(world["rt"], "knowledge/cost_primer.md", "c2", date="2026-10-05T12:00:00")
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 1
    assert poster.calls == []
    assert "cannot compare" in capsys.readouterr().out
    assert hb(world["rt"])["exit"] == 1


def test_missing_registry_entry_fails_without_comment(world: dict) -> None:
    (world["rt"] / "knowledge" / "repo_registry.json").write_text("{}")
    poster = FakePoster()
    assert kb.run(world["rt"], poster) == 1
    assert poster.calls == []
    assert hb(world["rt"])["exit"] == 1


def test_no_agency_file_is_written(world: dict) -> None:
    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    commit_file(world["rt"], "knowledge/cost_primer.md", "c2", date="2026-10-05T12:00:00")
    before = snapshot(world["ag"])
    kb.run(world["rt"], FakePoster())
    assert snapshot(world["ag"]) == before


def test_runs_with_agency_made_read_only(world: dict) -> None:
    """Stronger than a snapshot: any write attempt under the Agency tree would raise."""
    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    paths = [p for p in world["ag"].rglob("*")]
    for p in paths:
        p.chmod(0o555 if p.is_dir() else 0o444)
    try:
        assert kb.run(world["rt"], FakePoster()) == 0
    finally:
        for p in paths:
            p.chmod(0o755 if p.is_dir() else 0o644)


def test_overlay_same_day_edit_not_flagged_next_day_edit_flagged(world: dict) -> None:
    """Cutoff is the END of the read date (2026-10-06): same-day edits are not flagged, the next day's are."""
    hip = "knowledge/marketing_kb/compliance/hipaa.md"
    commit_file(world["rt"], hip, "h-same-day", date="2026-10-06T20:00:00")
    poster = FakePoster()
    kb.run(world["rt"], poster)
    assert poster.calls == []
    commit_file(world["rt"], hip, "h-next-day", date="2026-10-07T01:00:00")
    kb.run(world["rt"], poster)
    assert len(poster.calls) == 1 and "overlay review needed" in poster.calls[0][1]


def test_start_stub_has_exit_1_null_finished_and_started_text(world: dict) -> None:
    seen: list[dict] = []

    def peek(issue: int, body: str, cwd: Path) -> None:
        seen.append(hb(world["rt"]))  # heartbeat as it stands while the work is in flight

    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    kb.run(world["rt"], peek)
    start = seen[0]
    assert (
        start["exit"] == 1
        and start["finished_at"] is None
        and start["summary"].startswith("STARTED")
    )
    assert UTC_TS_RE.match(start["started_at"])
    assert hb(world["rt"])["exit"] == 0


def test_gh_poster_argv_and_cwd_with_fake_subprocess(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    class Done:
        returncode = 0
        stderr = ""

    def fake_run(argv, **kw):
        captured["argv"], captured["cwd"] = argv, kw.get("cwd")
        captured["body"] = Path(argv[argv.index("--body-file") + 1]).read_text()
        return Done()

    monkeypatch.setattr(kb.subprocess, "run", fake_run)
    kb.gh_poster(5496, "hello", tmp_path)
    argv = captured["argv"]
    assert argv[:4] == ["gh", "issue", "comment", "5496"]
    assert argv[argv.index("--repo") + 1] == "example-org/agency"
    assert "--body-file" in argv and captured["body"] == "hello"
    assert captured["cwd"] == str(tmp_path)


def test_gh_poster_failure_raises_sync_error(monkeypatch, tmp_path: Path) -> None:
    class Bad:
        returncode = 1
        stderr = "nope"

    monkeypatch.setattr(kb.subprocess, "run", lambda *a, **k: Bad())
    with pytest.raises(kb.SyncError):
        kb.gh_poster(5496, "x", tmp_path)


def test_direct_and_rewritten_change_post_exactly_one_comment(world: dict) -> None:
    commit_file(world["rt"], "knowledge/marketing_kb/a.md", "a2", date="2026-10-05T12:00:00")
    commit_file(world["rt"], "knowledge/cost_primer.md", "c2", date="2026-10-05T12:00:00")
    poster = FakePoster()
    kb.run(world["rt"], poster)
    assert len(poster.calls) == 1
    body = poster.calls[0][1]
    assert "re-port (1)" in body and "rewrite review needed (1)" in body


def test_manual_run_writes_manual_heartbeat_and_leaves_scheduled_one_alone(world: dict) -> None:
    kb.run(world["rt"], FakePoster(), manual=True)
    hbdir = world["rt"] / "schedules" / "heartbeats"
    assert (hbdir / f"manual-{kb.JOB}.json").exists()
    assert not (hbdir / f"{kb.JOB}.json").exists()


def test_in_scope_primer_never_ported_is_listed(world: dict, capsys) -> None:
    commit_file(world["rt"], "knowledge/sentinel_primer.md", "s1")
    kb.run(world["rt"], FakePoster())
    assert "knowledge/sentinel_primer.md" in capsys.readouterr().out
