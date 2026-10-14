"""Major 9 — validator additions: pack.slug must equal the registry key,
every paths.* must be relative, co_managing_systems entries are validated.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


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
# slug must equal the registry key
# --------------------------------------------------------------------------


def test_slug_mismatch_rejected():
    """RED-check: remove the `pack.get("slug") != slug` check and this
    passes wrongly on a pack resolved under one registry key but declaring
    a different slug internally."""
    pack = _minimal_pack("wrong_internal_slug")
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("does not match the registry key" in r for r in reasons)


def test_slug_match_ok():
    pack = _minimal_pack("acme")
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# paths.* must be relative
# --------------------------------------------------------------------------


def test_data_dir_absolute_path_rejected():
    """RED-check: remove the leading-'/' check in the paths.* relative-path
    loop and this passes wrongly on data_dir: "/etc"."""
    pack = _minimal_pack("acme")
    pack["paths"]["data_dir"] = "/etc"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("paths.data_dir must be a relative path" in r for r in reasons)


def test_data_dir_parent_traversal_rejected():
    """RED-check: remove the '..' component check and this passes wrongly
    on data_dir: "../x"."""
    pack = _minimal_pack("acme")
    pack["paths"]["data_dir"] = "../x"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("must not contain '..'" in r for r in reasons)


def test_data_dir_home_relative_tilde_rejected():
    pack = _minimal_pack("acme")
    pack["paths"]["data_dir"] = "~/escape"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("paths.data_dir must be a relative path" in r for r in reasons)


def test_relative_paths_ok():
    pack = _minimal_pack("acme")
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_build_dir_absolute_also_rejected():
    """The relative-path rule applies to build_dir too (not just the
    always-required keys)."""
    pack = _minimal_pack("acme")
    pack["paths"]["build_dir"] = "/tmp/evil"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("paths.build_dir must be a relative path" in r for r in reasons)


# --------------------------------------------------------------------------
# co_managing_systems validation
# --------------------------------------------------------------------------


def test_co_managing_systems_clean_entry_ok():
    pack = _minimal_pack(
        "acme",
        co_managing_systems=[
            {"system": "agency", "identity": "operator-google-login", "interface": "api", "mode": "read_only", "ruling_ref": "§20.9"}
        ],
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_co_managing_systems_missing_interface_rejected():
    pack = _minimal_pack(
        "acme",
        co_managing_systems=[
            {"system": "agency", "identity": "operator-google-login", "mode": "read_only", "ruling_ref": "§20.9"}
        ],
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("interface" in r for r in reasons)


def test_co_managing_systems_write_mode_rejected():
    """mode must be read_only -- §20.9's Model A decision means a
    co-managing identity is NEVER a writer."""
    pack = _minimal_pack(
        "acme",
        co_managing_systems=[
            {"system": "agency", "identity": "x", "interface": "api", "mode": "write", "ruling_ref": "§20.9"}
        ],
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("mode" in r for r in reasons)


def test_co_managing_systems_not_a_list_rejected():
    pack = _minimal_pack("acme", co_managing_systems={"system": "agency"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("co_managing_systems must be a list" in r for r in reasons)
