"""Minor finding (scalability): `main()`'s per-target flush must read
`existing_ids` from every trail ONCE per run, not once PER TARGET (each
registered company plus the unattributed sink) -- the old design called
`_flush_locked` once per target, each call independently re-taking every
trail's lock and re-running `load_existing_ids` over every trail in
`all_trail_paths` from scratch, an O((companies + 1) x trails) =
O((companies + 1)^2) total read cost for one harvest run.

Proven by call-count instrumentation (never a wall-clock threshold, which
flakes on a loaded machine): patch `load_existing_ids` to count invocations
and assert it is called exactly ONCE for a run that flushes N companies'
worth of new records, regardless of N -- plus a correctness check that
every record landed in its own company's trail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402


def _minimal_pack(slug: str) -> dict:
    return {
        "schema_version": 1, "slug": slug, "legal_name": slug, "display_names": [slug],
        "business_model": "local_service", "brands": [],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {k: [] for k in (
            "facebook_page_ids", "instagram_ids", "gbp_location_ids", "ads_customer_ids",
            "meta_ad_account_ids", "ga4_property_ids", "gtm_container_ids", "domains", "listing_urls",
        )},
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


@pytest.fixture()
def four_companies(tmp_path, monkeypatch):
    """Four registered companies, none declaring an identity host -- every
    call attributes purely by cwd (rung 2: playwright-gtm server + cwd
    under a registered home), so each company's own transcript needs
    nothing beyond a distinct cwd."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)

    slugs = ["alpha", "beta", "gamma", "delta"]
    homes: dict[str, Path] = {}
    repos: dict[str, dict] = {}
    for slug in slugs:
        home = tmp_path / f"home_{slug}"
        (home / ".claude" / "gtm").mkdir(parents=True)
        (home / ".claude" / "gtm" / "company.json").write_text(
            json.dumps(_minimal_pack(slug)), encoding="utf-8"
        )
        homes[slug] = home
        repos[slug] = {"root": str(home)}

    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": repos}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    company.write_identity_index()
    return homes


def _write_transcript(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def _navigate_and_click_lines(session_id: str, cwd: str, tid_prefix: str) -> list[dict]:
    url = "https://unrelated-generic-site.example.org/page"
    return [
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:00-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_use", "id": f"{tid_prefix}_nav", "name": "mcp__playwright-gtm__browser_navigate", "input": {"url": url}},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:01-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"{tid_prefix}_nav", "content": f"- Page URL: {url}"},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:02-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_use", "id": f"{tid_prefix}_click", "name": "mcp__playwright-gtm__browser_click", "input": {"element": "Save button"}},
            ]},
        },
        {
            "sessionId": session_id, "timestamp": "2026-01-01T10:00:03-06:00", "cwd": cwd,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"{tid_prefix}_click", "content": f"- Page URL: {url}"},
            ]},
        },
    ]


def test_flush_across_four_companies_reads_existing_ids_exactly_once(four_companies, tmp_path, monkeypatch):
    """RED-check: revert `main()` to call `_flush_locked` once per company
    (plus once for the unattributed sink) instead of collecting every
    target's candidates and calling `_flush_many_locked` once, and this
    fails -- `load_existing_ids` is called once per target (5 times: 4
    companies + the empty unattributed flush skipped, or more once the
    unattributed sink also has records) instead of once for the whole run."""
    call_count = {"n": 0}
    real_load = htt.load_existing_ids

    def _counting_load(paths, **kwargs):
        call_count["n"] += 1
        return real_load(paths, **kwargs)

    monkeypatch.setattr(htt, "load_existing_ids", _counting_load)

    transcript = tmp_path / "multi_company.jsonl"
    lines: list[dict] = []
    for i, slug in enumerate(["alpha", "beta", "gamma", "delta"]):
        lines.extend(
            _navigate_and_click_lines(
                session_id=f"sess_{slug}", cwd=str(four_companies[slug]), tid_prefix=f"tu{i}",
            )
        )
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    assert call_count["n"] == 1, (
        f"load_existing_ids was called {call_count['n']} times for a 4-company run -- "
        "expected exactly 1 (one combined read for the whole run), not one per target."
    )

    # Correctness: every company's own click landed in ITS OWN trail, and
    # only the click (not the navigate) counts as a mutating capture.
    for slug in ["alpha", "beta", "gamma", "delta"]:
        paths = activity_log.resolve_paths(slug)
        records, _ = activity_log.read_jsonl(paths.trail_jsonl)
        assert len(records) == 1, f"{slug} trail has {len(records)} records, expected 1"


def test_flush_many_locked_still_dedupes_reattribution_within_one_run(tmp_path, monkeypatch):
    """Paired recovery test: batching every target's flush into one
    `_flush_many_locked` call must not reopen the cross-company duplicate
    hazard `_flush_locked` was built to close -- the SAME tool_use_id
    appearing as a candidate for two different targets in one run (e.g. a
    company whose trail path fails to resolve gets its records rerouted to
    the unattributed sink) must land in exactly one of them, never both."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import harvest_tool_trail as htt_mod  # noqa: E402

    trail_a = tmp_path / "a" / "TOOL_TRAIL.jsonl"
    trail_b = tmp_path / "b" / "TOOL_TRAIL.jsonl"
    all_paths = [trail_a, trail_b]

    record = {
        "tool_use_id": "tu_shared", "ts": "2026-01-01T09:00:00-06:00", "session_id": "sess_1",
        "tool": "mcp__playwright-gtm__browser_click", "system": "google_ads",
    }

    results = htt_mod._flush_many_locked(
        [(trail_a, [record]), (trail_b, [record])], all_paths
    )
    assert results[trail_a][0] == 1
    # The second target must see the id as already-appended (from the
    # first target within this SAME batch) and append nothing.
    assert results[trail_b][0] == 0

    records_a, _ = activity_log.read_jsonl(trail_a)
    records_b, _ = activity_log.read_jsonl(trail_b)
    assert len(records_a) == 1
    assert len(records_b) == 0
