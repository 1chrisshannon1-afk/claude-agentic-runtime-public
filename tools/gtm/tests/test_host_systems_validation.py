"""B2: host_systems is a documented, VALID pack key (was refused as
unknown). Tests validate_company acceptance/rejection and an end-to-end
scenario: a Brightline-shaped pack mapping business.google.com,
facebook.com, and example-remodeling.com to its own brand-specific
system names; harvest a click; an agent `add` on that system; `audit`
returns 0.
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


# --------------------------------------------------------------------------
# validate_company: host_systems is a valid key, not "unknown key"
# --------------------------------------------------------------------------


def test_host_systems_no_longer_refused_as_unknown_key():
    """RED-check: remove "host_systems" from OPTIONAL_TOP_KEYS and this
    fails -- the unknown-key check would fire."""
    pack = _minimal_pack("acme", host_systems={"ads.google.com": "google_ads"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_host_systems_value_must_be_in_pack_system_set():
    """RED-check: remove the `system not in valid_systems` check and this
    fails -- a bogus system name would validate clean."""
    pack = _minimal_pack("acme", host_systems={"ads.google.com": "totally_not_a_real_system"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems" in r and "totally_not_a_real_system" in r for r in reasons)


def test_host_systems_value_in_channels_in_scope_is_accepted():
    """A pack's own custom channel (declared in scope.channels_in_scope)
    is a valid host_systems target, not just the fixed base systems."""
    pack = _minimal_pack(
        "acme",
        scope={"local_seo": True, "channels_in_scope": ["youtube_shorts"], "channels_out_of_scope": []},
        host_systems={"youtube.com": "youtube_shorts"},
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_host_systems_must_be_an_object():
    pack = _minimal_pack("acme", host_systems=["ads.google.com"])
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems must be an object" in r for r in reasons)


def test_host_systems_empty_key_rejected():
    pack = _minimal_pack("acme", host_systems={"": "google_ads"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok


def test_host_systems_trailing_slash_empty_path_rejected():
    """RED-check: remove the trailing-slash/empty-path-part check and this
    fails -- 'facebook.com/' would validate clean, then silently never
    match any real URL (harvest_tool_trail partitions it into host
    'facebook.com' and an empty path prefix, which host_matches_prefix
    never matches against)."""
    pack = _minimal_pack("acme", host_systems={"facebook.com/": "google_ads"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems" in r and "trailing" in r for r in reasons)


def test_host_systems_empty_host_before_slash_rejected():
    """RED-check: remove the empty-host-part check and this fails --
    '/123' would validate clean despite having no host at all before the
    '/', which can never match any real URL's hostname."""
    pack = _minimal_pack("acme", host_systems={"/123": "google_ads"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("host_systems" in r and "empty host part" in r for r in reasons)


def test_host_systems_host_with_nonempty_path_prefix_still_accepted():
    """Paired recovery test: a genuinely well-formed '<host>/<path-prefix>'
    key (non-empty host AND non-empty path) is still accepted -- the fix
    must not become an overbroad refusal of every '/'-containing key."""
    pack = _minimal_pack("acme", host_systems={"facebook.com/business": "google_ads"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# End-to-end: Brightline pack with brand-specific host_systems overrides;
# harvest a click; agent `add`; `audit` returns 0.
# --------------------------------------------------------------------------


def _brightline_pack_with_host_systems() -> dict:
    return _minimal_pack(
        "brightline",
        legal_name="Brightline",
        display_names=["Brightline Remodeling"],
        scope={
            "local_seo": True,
            "channels_in_scope": ["gbp_remodeling", "facebook_remodeling", "website_remodeling"],
            "channels_out_of_scope": [],
        },
        identity_allowlist={
            "facebook_page_ids": ["100000000000001"], "instagram_ids": [], "gbp_location_ids": ["1000000000000000001"],
            "ads_customer_ids": ["100-200-3000"], "meta_ad_account_ids": [], "ga4_property_ids": ["100000004"],
            "gtm_container_ids": ["100000002"], "domains": ["example-remodeling.com"], "listing_urls": [],
        },
        host_systems={
            "business.google.com": "gbp_remodeling",
            "facebook.com": "facebook_remodeling",
            "example-remodeling.com": "website_remodeling",
        },
    )


@pytest.fixture()
def registered_brightline(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(
        json.dumps(_brightline_pack_with_host_systems()), encoding="utf-8"
    )
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    company.write_identity_index()
    return home


def _write_transcript(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def test_pack_validates_ok_with_host_systems(registered_brightline):
    ok, reasons = company.validate_company("brightline", _brightline_pack_with_host_systems(), siblings={})
    assert ok, reasons


def test_gbp_click_mapped_via_host_systems_override_audits_clean(registered_brightline, tmp_path):
    """RED-check: remove `_pack_host_systems`'s use in
    harvest_tool_trail.host_system_for_url (or make it check DEFAULT_HOST_
    SYSTEMS first) and this test would still pass for gbp (both map to a
    'gbp'-ish name) -- but the explicit assertion on the pack's OWN
    brand-specific name ("gbp_remodeling", not the generic default "gbp")
    would fail, proving the override -- not the default -- won."""
    transcript = tmp_path / "gbp_click.jsonl"
    lines = [
        {
            "sessionId": "sess_gbp", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_use", "id": "tu_gbp_click", "name": "mcp__playwright-gtm__browser_click",
                 "input": {"element": "Edit hours"}},
            ]},
        },
        {
            "sessionId": "sess_gbp", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_gbp_click", "content": "- Page URL: https://business.google.com/edit"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1
    assert records[0]["system"] == "gbp_remodeling"

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="brightline", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1  # not yet explained

    activity_log.cmd_add(Namespace(
        company="brightline", system="gbp_remodeling", action="update", object="updated business hours",
        before="9-5", after="8-6", why="seasonal hours change", actor="gtm-operator:ac06afdc5dc9de0f3",
        evidence=[], undo="revert hours", approval="R9", status="done", account=None,
        ts="2026-01-01T09:10:00-06:00", notes=None,
    ))

    rc = activity_log.cmd_audit(Namespace(company="brightline", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 0


def test_facebook_click_mapped_via_host_systems_override(registered_brightline, tmp_path):
    transcript = tmp_path / "fb_click.jsonl"
    lines = [
        {
            "sessionId": "sess_fb", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_use", "id": "tu_fb_click", "name": "mcp__playwright-gtm__browser_click",
                 "input": {"element": "Publish"}},
            ]},
        },
        {
            "sessionId": "sess_fb", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_fb_click", "content": "- Page URL: https://www.facebook.com/business/x"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)
    htt.main([str(transcript)])

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1
    assert records[0]["system"] == "facebook_remodeling"


def test_website_click_mapped_via_host_systems_override(registered_brightline, tmp_path):
    transcript = tmp_path / "web_click.jsonl"
    lines = [
        {
            "sessionId": "sess_web", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_use", "id": "tu_web_click", "name": "mcp__playwright-gtm__browser_click",
                 "input": {"element": "Update"}},
            ]},
        },
        {
            "sessionId": "sess_web", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": str(registered_brightline),
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_web_click", "content": "- Page URL: https://example-remodeling.com/wp-admin/edit.php"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)
    htt.main([str(transcript)])

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1
    assert records[0]["system"] == "website_remodeling"
