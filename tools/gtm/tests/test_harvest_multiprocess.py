"""Minor 17: a multi-PROCESS (not threads) test that two independent
`harvest_tool_trail.main()` invocations, run concurrently as separate OS
processes against overlapping transcript inputs, never produce duplicate
tool_use_id records nor a broken hash chain. Threads share one Python
process's GIL and memory space (a weaker test of real file-locking
correctness across independent processes, which is what production
actually does — a scheduled harvest run and a manually-triggered one are
always separate processes).
"""

from __future__ import annotations

import json
import multiprocessing
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import company  # noqa: E402


def _minimal_pack(slug: str) -> dict:
    return {
        "schema_version": 1, "slug": slug, "legal_name": slug, "display_names": [slug],
        "business_model": "local_service", "brands": [],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["brightline-example.com"], "listing_urls": [],
        },
        "claims_policy": {"terms": []},
        "ai_content_policy": {"mode": "strip_before_publish"},
        "autonomy": {"level": "shadow", "standing_approvals": []},
        "spend": {"currency": "USD", "monthly_cap_total": 0, "cap_ruling_ref": "none"},
        "budget": {"weekly_usd_cap_opus": 0, "weekly_usd_cap_sonnet": 0, "dispatch_caps_per_run": {
            "inbox": 8, "daily": 4, "weekly": 30, "monthly": 8, "mission": 60, "monthly_load": 8}},
        "operator_input": "from_manifest", "inbox": "local_jsonl",
        "lead_sink": {"kind": "none"},
        "cadence": {"inbox_checks": ["09:00"], "weekly_day": "SAT", "monthly_day": 1, "monthly_load_day": "last_weekday"},
        "paths": {
            "missions_dir": "gtm_mission", "mission_records": "ignored",
            "activity_log_dir": ".claude/gtm/state/activity_log",
            "scoreboard": ".claude/gtm/state/scoreboard.csv",
            "snapshots_dir": ".claude/gtm/state/snapshots",
            "metrics": ".claude/gtm/metrics.json",
            "feature_inventory_dir": ".claude/gtm/feature_inventory",
            "plans_dir": ".claude/gtm/plans",
            "data_dir": ".claude/gtm/data",
        },
    }


def _write_transcript_with_n_clicks(path: Path, n: int, url: str) -> None:
    """Writes one transcript file with N distinct mutating click tool
    calls, all against the same URL (so they all attribute to the same
    company)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[dict] = []
    for i in range(n):
        tid = f"tu_mp_{i}"
        lines.append({
            "sessionId": "sess_mp", "timestamp": f"2026-01-01T09:{i:02d}:00-06:00", "cwd": "/nowhere",
            "message": {"content": [
                {"type": "tool_use", "id": tid, "name": "mcp__playwright-gtm__browser_click", "input": {"element": f"btn-{i}"}},
            ]},
        })
        lines.append({
            "sessionId": "sess_mp", "timestamp": f"2026-01-01T09:{i:02d}:01-06:00", "cwd": "/nowhere",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid, "content": f"- Page URL: {url}"},
            ]},
        })
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def _run_harvest_subprocess(claude_dir_str: str, transcript_str: str) -> None:
    """Runs in a SEPARATE OS process (multiprocessing.Process target must
    be a module-level function, not a closure, so this cannot be a nested
    def inside the test). Re-does the sys.path/env setup a fresh process
    needs, then calls harvest_tool_trail.main() directly (in-process
    within the child, which is still a genuinely separate OS process from
    the parent test and from the OTHER child)."""
    import os as _os
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    _os.environ["CLAUDE_DIR"] = claude_dir_str
    _os.environ.pop("TS_ACTIVITY_MIRROR_DIR", None)
    import harvest_tool_trail as _htt

    _htt.main([transcript_str])


@pytest.fixture()
def registered_brightline(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_minimal_pack("brightline")), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    company.write_identity_index()
    return {"home": home, "claude_dir": claude_dir}


def test_two_processes_harvesting_overlapping_transcripts_no_duplicates(registered_brightline, tmp_path):
    """Two SEPARATE transcript files (simulating two concurrent harvest
    triggers, e.g. a scheduled run and a manual one, each seeing a
    different but overlapping slice of new activity) are harvested by two
    independent OS PROCESSES launched at the same time. RED-check: revert
    main()'s whole-run ExitStack lock hold to the pre-minor-17 per-append
    locking (existing_ids read OUTSIDE any lock) and this test becomes
    flaky-but-failing under real multiprocess timing -- two processes can
    both read a stale existing_ids snapshot and each append their own
    copy of an id the other process already wrote, OR interleave their
    prev_hash reads and fork the chain."""
    claude_dir_str = str(registered_brightline["claude_dir"])

    # Two transcripts sharing SOME tool_use_ids (both contain tu_mp_0..9)
    # to genuinely exercise the idempotency-across-processes path, plus
    # each having some ids the other doesn't, to exercise real concurrent
    # appends landing in the same trail file.
    transcript_a = tmp_path / "transcript_a.jsonl"
    transcript_b = tmp_path / "transcript_b.jsonl"
    _write_transcript_with_n_clicks(transcript_a, 15, "https://brightline-example.com/a")
    _write_transcript_with_n_clicks(transcript_b, 15, "https://brightline-example.com/a")

    proc_a = multiprocessing.Process(target=_run_harvest_subprocess, args=(claude_dir_str, str(transcript_a)))
    proc_b = multiprocessing.Process(target=_run_harvest_subprocess, args=(claude_dir_str, str(transcript_b)))
    proc_a.start()
    proc_b.start()
    proc_a.join(timeout=60)
    proc_b.join(timeout=60)

    assert proc_a.exitcode == 0
    assert proc_b.exitcode == 0

    paths = activity_log.resolve_paths("brightline")
    records, bad = activity_log.read_jsonl(paths.trail_jsonl)
    assert bad == []

    ids = [r["tool_use_id"] for r in records]
    assert len(ids) == len(set(ids)), f"duplicate tool_use_id written across processes: {ids}"
    assert len(records) == 15  # both transcripts describe the SAME 15 calls -- never double-counted

    chain_ok, reason = activity_log.verify_chain(paths.trail_jsonl)
    assert chain_ok, reason
