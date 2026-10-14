"""Tests for blocker 2 — harvest_tool_trail.py's host->system mapping
(host_system_for_url, DEFAULT_HOST_SYSTEMS, and the pack-level
`host_systems` override key), including the required end-to-end scenario:
harvest a fixture transcript with a click on ads.google.com -> `add` an
agent-actor explanation on `google_ads` within 15 min -> `audit` returns 0,
and `explain` works on a harvested cluster.
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


def _minimal_pack(slug: str, **overrides) -> dict:
    pack = {
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
    pack.update(overrides)
    return pack


@pytest.fixture()
def registered_brightline(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    pack = _minimal_pack(
        "brightline",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": ["100-200-3000"], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": [], "listing_urls": [],
        },
    )
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    company.write_identity_index()
    return home


# --------------------------------------------------------------------------
# host_system_for_url direct unit tests
# --------------------------------------------------------------------------


def test_default_host_systems_cover_every_named_platform():
    cases = {
        "https://ads.google.com/aw/campaigns": "google_ads",
        "https://analytics.google.com/analytics/web/": "ga4",
        "https://tagmanager.google.com/#/container": "gtm",
        "https://business.google.com/edit": "gbp",
        "https://www.facebook.com/business/x": "facebook",
        "https://business.facebook.com/x": "facebook",
        "https://www.instagram.com/x": "instagram",
        "https://www.yelp.com/biz/x": "yelp",
        "https://www.angi.com/x": "angi",
        "https://www.homeadvisor.com/x": "angi",
        "https://www.thumbtack.com/x": "thumbtack",
        "https://www.houzz.com/x": "houzz",
        "https://nextdoor.com/x": "nextdoor",
        "https://search.google.com/search-console/x": "search_console",
    }
    for url, expected in cases.items():
        assert htt.host_system_for_url(url, None) == expected, url


def test_wp_admin_on_pack_domain_maps_to_website_wordpress():
    pack = {"brands": [{"id": "remodeling", "domains": ["example-remodeling.com"]}]}
    assert htt.host_system_for_url("https://example-remodeling.com/wp-admin/edit.php", pack) == "website_wordpress"
    # A non-wp-admin path on the same domain must NOT be reclassified.
    assert htt.host_system_for_url("https://example-remodeling.com/about", pack) != "website_wordpress"


def test_pack_host_systems_override_wins_over_default():
    """RED-check: remove the pack-first loop in host_system_for_url (or
    reorder it after DEFAULT_HOST_SYSTEMS) and this fails -- ads.google.com
    would resolve to the DEFAULT 'google_ads' instead of the pack's
    override."""
    pack = {"host_systems": {"ads.google.com": "google_ads_custom_override"}}
    assert htt.host_system_for_url("https://ads.google.com/x", pack) == "google_ads_custom_override"


def test_unmapped_host_falls_back_to_gtm_browser_never_crashes_audit():
    """RED-check: revert to the old hardcoded 'gtm_browser' literal that
    was never registered in activity_log.SYSTEMS -- this test alone
    wouldn't catch that regression (the string is identical), but
    test_gtm_browser_is_a_registered_system below does."""
    assert htt.host_system_for_url("https://totally-unknown-platform.example.net/x", None) == "gtm_browser"


def test_gtm_browser_is_a_registered_system(registered_brightline):
    """RED-check: remove 'gtm_browser' from activity_log._ADDED_SYSTEMS and
    this fails -- proving the fallback system name is actually valid input
    to activity_log.py add/audit/explain, not just a string constant."""
    paths = activity_log.resolve_paths("brightline")
    assert "gtm_browser" in paths.systems


# --------------------------------------------------------------------------
# End-to-end: harvest a click on ads.google.com -> explain via agent actor
# within 15 min -> audit returns 0. Then: explain works on a harvested
# cluster directly.
# --------------------------------------------------------------------------


def _write_transcript(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def test_google_ads_click_explained_by_agent_actor_audits_clean(registered_brightline, tmp_path):
    transcript = tmp_path / "ads_click.jsonl"
    lines = [
        {
            "sessionId": "sess_ads", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_use", "id": "tu_ads_click", "name": "mcp__playwright-gtm__browser_click",
                 "input": {"element": "Increase budget"}},
            ]},
        },
        {
            "sessionId": "sess_ads", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_ads_click", "content": "- Page URL: https://ads.google.com/aw/campaigns"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1
    assert records[0]["system"] == "google_ads"  # blocker 2: never the old hardcoded "gtm_browser" here

    from argparse import Namespace
    # Not yet explained.
    rc = activity_log.cmd_audit(Namespace(company="brightline", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1

    activity_log.cmd_add(Namespace(
        company="brightline", system="google_ads", action="update", object="raised campaign budget",
        before="$50/day", after="$75/day", why="scaling", actor="gtm-operator:ac06afdc5dc9de0f3",
        evidence=[], undo="revert to $50/day", approval="R9", status="done", account=None,
        ts="2026-01-01T09:10:00-06:00", notes=None,
    ))

    rc = activity_log.cmd_audit(Namespace(company="brightline", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 0


def test_explain_works_on_a_harvested_cluster(registered_brightline, tmp_path):
    """`explain` (the cluster-closing convenience wrapper around `add`)
    must work directly on a cluster built from a REAL harvested record,
    not just a hand-written trail fixture."""
    transcript = tmp_path / "ads_click2.jsonl"
    lines = [
        {
            "sessionId": "sess_ads2", "timestamp": "2026-01-02T09:00:00-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_use", "id": "tu_ads_click2", "name": "mcp__playwright-gtm__browser_click",
                 "input": {"element": "Save"}},
            ]},
        },
        {
            "sessionId": "sess_ads2", "timestamp": "2026-01-02T09:00:01-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_ads_click2", "content": "- Page URL: https://ads.google.com/aw/campaigns"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)
    htt.main([str(transcript)])

    paths = activity_log.resolve_paths("brightline")
    trail_records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    clusters = activity_log.build_clusters(trail_records)
    assert len(clusters) == 1
    cluster_id = clusters[0].cluster_id

    from argparse import Namespace
    rc = activity_log.cmd_explain(Namespace(
        company="brightline", cluster=cluster_id, why="scaling a winning campaign",
        object="raised campaign budget", action="update", before="$50/day", after="$75/day",
        actor="gtm-operator:ac06afdc5dc9de0f3", evidence=[], undo="revert to $50/day",
        approval="R9", status="done", account=None, notes=None, include_local=False,
    ))
    assert rc == 0

    log_records, _ = activity_log.read_jsonl(paths.log_jsonl)
    assert any(r["object"] == "raised campaign budget" for r in log_records)

    rc = activity_log.cmd_audit(Namespace(company="brightline", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 0
