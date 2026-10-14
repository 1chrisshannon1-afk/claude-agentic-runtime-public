"""A realistic Brightline-shaped company.json pack fixture, modeled on
~/.claude/plans/gtm_pack_facts_brightline_2026_09_27.md's ## Accounts and
## Brands sections, with credential_ref: "browser:playwright-gtm" accounts
(per B1 — these must validate clean, not be flagged as secret-shaped).
Covers: both brand phone numbers and NAP blocks; a Google Ads account id,
ocid, and conversion labels; a GTM account and container; a GA4 account and
property; both GBP location ids and a Restoration store code; a Facebook
Page id and asset id; a Meta pixel id; and #27's path-scoped host_systems
entries disambiguating the two brands on their shared
business.google.com/facebook.com hosts. Asserts the pack validates OK end
to end through validate_company. Does NOT cover every fact in the source
file (e.g. owner cards, standing-approval nuance beyond R9/C1, or the
freeze-scope file list) — those are plan/process facts, not company.json
pack content.

Major finding #4 (data exposure): every account/object id and phone number
below is a SYNTHETIC value of the same shape as the real Brightline
identifier it stands in for (same digit count / character class / format),
never the real value itself. `tools/gtm` is in the runtime mirror's publish
set (`.mirror/config.json`'s `include`), and the mirror's redaction only
has patterns for company NAMES (e.g. "brightline"), not for these
platform-specific ids or phone numbers -- so a real id or phone number
committed here would, once the pack-name-shaped SyntaxError block on this
file's own redacted form is ever resolved, publish to the mirror and tie
the runtime repo to the operator's real Brightline accounts. The tests
below check SHAPE and disambiguation behavior, never the real values, so
synthetic stand-ins exercise exactly the same code paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


def _brightline_full_pack() -> dict:
    """Every identifier below is a SYNTHETIC value with the same shape
    (digit count / character class / format) as the real identifier named
    in gtm_pack_facts_brightline_2026_09_27.md's ## Accounts / ## Brands
    sections -- never the real value itself (major finding #4)."""
    return {
        "schema_version": 1,
        "slug": "brightline",
        "legal_name": "Brightline",
        "display_names": ["Brightline Remodeling", "Brightline - Water Damage Restoration"],
        "business_model": "local_service",
        "brands": [
            {
                "id": "remodeling",
                "display_name": "Brightline Remodeling",
                "domains": ["example-remodeling-ts.com"],
                "phones": ["(555) 010-1001"],
                "booking_url": "https://example-remodeling-ts.com/contact",
                "nap": {
                    "name": "Brightline Remodeling",
                    "address": "100 Example St, Suite 100, Example City, CO 80900",
                    "phone": "(555) 010-1001",
                },
            },
            {
                "id": "restoration",
                "display_name": "Brightline - Water Damage Restoration",
                "domains": ["example-restoration-ts.com"],
                "phones": ["(555) 010-1002"],
                "booking_url": "https://example-restoration-ts.com/contact",
                "nap": {
                    "name": "Brightline - Water Damage Restoration",
                    "address": "100 Example St, Suite 100, Example City, CO 80900",
                    "phone": "(555) 010-1002",
                },
            },
        ],
        "persona_file": "knowledge/marketing_kb/shared/homeowner-buyer-psychology.md",
        "timezone": "America/Denver",
        "quiet_hours": {"start": "20:00", "end": "07:00"},
        "goals": {
            "north_star_metric": "crm_leads_logged_last_7d",
            "guardrail_metrics": ["cost_per_booked_job_whole_engine"],
        },
        "scope": {
            "local_seo": True,
            "channels_in_scope": [
                "google_ads", "gtm", "ga4", "gbp_remodeling", "gbp_restoration",
                "facebook_remodeling", "instagram", "website_remodeling", "website_restoration",
                "lsa",
            ],
            "channels_out_of_scope": [],
        },
        "accounts": [
            # Synthetic Google Ads customer id (shape: NNN-NNN-NNNN), ocid,
            # conversion id, and two conversion labels (shape:
            # 20-char mixed-case alphanumeric + underscore).
            {
                "system": "google_ads", "brand": "remodeling", "account_id": "100-200-3000",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
                "ocid": "100000001",
                "conversion_id": "200000002",
                "conversion_labels": ["AbCdEfG_1hIjKlMnOpQr", "StUvWxY_2zAbCdEfGhIj"],
                # "call from website" conversion tracking number -- a
                # dash-formatted number, distinct literal value from the
                # brand's own "(555) 010-1001" NAP phone above, even
                # though (in the real pack) both are the same underlying
                # number.
                "call_conversion_number": "555-010-1001",
            },
            # Synthetic GTM account/container ids (shape: 10-digit account
            # id, 9-digit container id, GTM-XXXXXXXX public id).
            {
                "system": "gtm", "brand": "remodeling", "account_id": "GTM-ABCD1234",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
                "gtm_account_id": "1000000001", "gtm_container_id": "100000002",
            },
            # Synthetic GA4 account/property ids (shape: 9-digit account
            # id, 9-digit property id, G-XXXXXXXXXX measurement id).
            {
                "system": "ga4", "brand": "remodeling", "account_id": "G-ABCD123456",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
                "ga4_account_id": "100000003", "ga4_property_id": "100000004",
            },
            # Synthetic GBP Remodeling location id (shape: 19-digit numeric).
            {
                "system": "gbp", "brand": "remodeling", "account_id": "1000000000000000001",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
            },
            # Synthetic GBP Restoration location id + store code (shape:
            # 19-digit location id, 20-digit store code).
            {
                "system": "gbp", "brand": "restoration", "account_id": "1000000000000000002",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
                "store_code": "10000000000000000001",
            },
            # Synthetic Facebook Page id + asset id (shape: 15-digit page
            # id, 15-digit asset id).
            {
                "system": "facebook", "brand": "remodeling", "account_id": "100000000000001",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
                "asset_id": "100000000000002",
            },
            # Synthetic Meta pixel id (shape: 16-digit numeric).
            {
                "system": "meta_pixel", "brand": "remodeling", "account_id": "1000000000000003",
                "access": "browser", "credential_ref": "browser:playwright-gtm",
            },
        ],
        "identity_allowlist": {
            "facebook_page_ids": ["100000000000001"],
            "instagram_ids": [],
            "gbp_location_ids": ["1000000000000000001", "1000000000000000002"],
            "ads_customer_ids": [
                "100-200-3000",
                # ocid, conversion id, both conversion labels, and campaign
                # ids -- all SYNTHETIC identifiers, shape-matched to the
                # real facts file, never secrets.
                "100000001", "200000002", "300000003", "400000004",
                "AbCdEfG_1hIjKlMnOpQr", "StUvWxY_2zAbCdEfGhIj",
                "500000005", "500000006", "500000007", "500000008", "500000009",
            ],
            "meta_ad_account_ids": [],  # other-business meta ad account ids NEVER go here -- see shared_identifiers/other_businesses note below.
            # Major finding #6: property/container ids only -- the GA4
            # ACCOUNT id (100000003) and GTM ACCOUNT id (1000000001) are
            # NOT property/container ids and never belong in these lists
            # (they are still available for attribution via each
            # account's own ga4_account_id/gtm_account_id field above).
            "ga4_property_ids": ["100000004"],
            "gtm_container_ids": ["100000002"],
            "domains": ["example-remodeling-ts.com", "example-restoration-ts.com"],
            "listing_urls": [],
        },
        "claims_policy": {
            "terms": [
                {"regex": "licens|insured", "rule": "no_new", "ruling_ref": "R4 amended 2026-09-26 (existing wording kept)"},
                {"regex": "general contractor|\\bGC\\b", "rule": "no_new", "ruling_ref": "R4"},
                {"regex": "bonded|permit", "rule": "forbid_any", "ruling_ref": "R4 (remove where found)"},
            ],
            "never_claim_file": "knowledge/never_claim_brightline.md",
        },
        "shared_identifiers": [
            {
                "value": "app.buildwiseai.com",
                "with": "buildwiseai",
                "relationship": "vendor",
                "ruling_ref": "R5 (CSA is Brightline's Scout vendor)",
                "source": "operator",
            },
        ],
        "ai_content_policy": {
            "mode": "disclose_never_strip",
            "surfaces_forbidden": ["website", "gbp", "ads", "email", "print"],
            "disclosure_caption_line": "This is an AI-generated illustration, not a photo of a real job.",
            "caps": {"feed_28d_max": 2},
        },
        "autonomy": {
            "level": "shadow",
            "standing_approvals": [
                {
                    "id": "R9", "verbatim": "build paused, $0 changes", "ts": "2026-09-27",
                    "rows": ["gbp.hours_edit", "gbp.description_edit"],
                },
                {
                    "id": "C1", "verbatim": "posts publish after the three reviews", "ts": "2026-09-27",
                    "rows": ["gbp.post_publish", "facebook.post_publish"],
                },
            ],
        },
        "spend": {
            "currency": "USD",
            "monthly_cap_total": 1450,
            "per_channel_monthly_cap": {},
            "max_weekly_realloc_pct": 0,
            "cap_ruling_ref": "C4 option A: October Google Ads plan ~$1,450",
        },
        "budget": {
            "weekly_usd_cap_opus": 0,
            "weekly_usd_cap_sonnet": 0,
            "dispatch_caps_per_run": {
                "inbox": 8, "daily": 4, "weekly": 30, "monthly": 8, "mission": 60, "monthly_load": 8,
            },
        },
        "operator_input": "from_manifest",
        "inbox": "local_jsonl",
        # Synthetic Google Sheet id -- shape-matched (44-char base64-ish),
        # never the real sheet id.
        "lead_sink": {"kind": "google_sheet", "ref": "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
        "cadence": {
            "inbox_checks": ["09:00", "15:00"],
            "weekly_day": "SAT",
            "monthly_day": 1,
            "monthly_load_day": "last_weekday",
        },
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
        },
        "class_o_batches": ["C", "D"],
        "mirror_dir": "~/Desktop/Brightline",
        "mirror_basename": "Brightline_Activity_Log",
        "mirror_title": "Brightline Activity Log",
        "host_systems": {
            # #27: path-scoped entries disambiguate the two brands sharing
            # business.google.com and facebook.com -- checked before the
            # plain host-only fallback below. Synthetic ids, matching the
            # ones declared above.
            "business.google.com/1000000000000000001": "gbp_remodeling",
            "business.google.com/1000000000000000002": "gbp_restoration",
            "facebook.com/100000000000001": "facebook_remodeling",
            "business.google.com": "gbp_remodeling",  # fallback when no location id appears in the URL
            "facebook.com": "facebook_remodeling",  # fallback when no page id appears in the URL
            "example-remodeling-ts.com": "website_remodeling",
            "example-restoration-ts.com": "website_restoration",
        },
        "co_managing_systems": [
            {
                "system": "google_ads",
                "identity": "operator-google-login",
                "interface": "web_ui",
                "mode": "read_only",
                "ruling_ref": "Opswell: Agency platform_finance/service.py:244 counts Brightline as a Opswell customer",
            },
        ],
    }


def test_brightline_full_pack_validates_ok_end_to_end():
    """RED-check: any B1/B2/B3-class regression in company.py's validator
    would break this fixture -- e.g. reverting B1's credential_ref
    exemption would flag all 7 accounts' browser:playwright-gtm refs,
    reverting B2 would flag the host_systems key as unknown, and a bad
    lead_sink.ref exemption would flag the Google Sheet id."""
    pack = _brightline_full_pack()
    ok, reasons = company.validate_company("brightline", pack, siblings={})
    assert ok, reasons


def test_brightline_pack_credential_refs_all_browser_shape():
    """Confirms every account in the fixture genuinely uses the
    browser:playwright-gtm credential_ref shape B1 exists to un-break."""
    pack = _brightline_full_pack()
    refs = {acct["credential_ref"] for acct in pack["accounts"]}
    assert refs == {"browser:playwright-gtm"}


def test_brightline_pack_lead_sink_is_a_real_google_sheet_id():
    pack = _brightline_full_pack()
    assert pack["lead_sink"]["kind"] == "google_sheet"
    assert len(pack["lead_sink"]["ref"]) >= 25


def test_brightline_pack_host_systems_present_and_valid():
    pack = _brightline_full_pack()
    assert "host_systems" in pack
    ok, reasons = company.validate_company("brightline", pack, siblings={})
    host_systems_reasons = [r for r in reasons if "host_systems" in r]
    assert host_systems_reasons == []


def test_brightline_pack_host_systems_disambiguates_both_brands_end_to_end():
    """#27 end-to-end against this fixture: both (synthetic, shape-matched)
    GBP location ids and the Facebook Page id correctly disambiguate the
    two brands sharing business.google.com/facebook.com."""
    import harvest_tool_trail as htt

    pack = _brightline_full_pack()
    remodeling_url = "https://business.google.com/locations/1000000000000000001/edit"
    restoration_url = "https://business.google.com/locations/1000000000000000002/edit"
    fb_url = "https://www.facebook.com/100000000000001/settings"

    assert htt.host_system_for_url(remodeling_url, pack) == "gbp_remodeling"
    assert htt.host_system_for_url(restoration_url, pack) == "gbp_restoration"
    assert htt.host_system_for_url(fb_url, pack) == "facebook_remodeling"


def test_brightline_pack_google_ads_full_identifiers_present():
    pack = _brightline_full_pack()
    ads_account = next(a for a in pack["accounts"] if a["system"] == "google_ads")
    assert ads_account["ocid"] == "100000001"
    assert ads_account["conversion_id"] == "200000002"
    assert set(ads_account["conversion_labels"]) == {"AbCdEfG_1hIjKlMnOpQr", "StUvWxY_2zAbCdEfGhIj"}
    assert ads_account["call_conversion_number"] == "555-010-1001"


def test_brightline_pack_gtm_account_and_container_present():
    pack = _brightline_full_pack()
    gtm_account = next(a for a in pack["accounts"] if a["system"] == "gtm")
    assert gtm_account["gtm_account_id"] == "1000000001"
    assert gtm_account["gtm_container_id"] == "100000002"
    assert gtm_account["account_id"] == "GTM-ABCD1234"


def test_brightline_pack_ga4_account_and_property_present():
    pack = _brightline_full_pack()
    ga4_account = next(a for a in pack["accounts"] if a["system"] == "ga4")
    assert ga4_account["ga4_account_id"] == "100000003"
    assert ga4_account["ga4_property_id"] == "100000004"
    assert ga4_account["account_id"] == "G-ABCD123456"


def test_brightline_pack_identity_allowlist_keeps_each_id_class_separate():
    """Major finding #6: `ga4_property_ids`/`gtm_container_ids` must hold
    ONLY property/container ids, never the platform's ACCOUNT id for that
    same system -- an account id and a property/container id are
    different objects even though both may appear in the same account
    entry. RED-check: put the account's own gtm_account_id/ga4_account_id
    back into these lists (this fixture's own pre-fix shape) and this
    test's disjointness assertions fail."""
    pack = _brightline_full_pack()
    gtm_account = next(a for a in pack["accounts"] if a["system"] == "gtm")
    ga4_account = next(a for a in pack["accounts"] if a["system"] == "ga4")

    assert gtm_account["gtm_account_id"] not in pack["identity_allowlist"]["gtm_container_ids"], (
        "gtm_container_ids must never include the GTM ACCOUNT id -- it is not a container id"
    )
    assert gtm_account["gtm_container_id"] in pack["identity_allowlist"]["gtm_container_ids"]

    assert ga4_account["ga4_account_id"] not in pack["identity_allowlist"]["ga4_property_ids"], (
        "ga4_property_ids must never include the GA4 ACCOUNT id -- it is not a property id"
    )
    assert ga4_account["ga4_property_id"] in pack["identity_allowlist"]["ga4_property_ids"]


def test_brightline_pack_gbp_restoration_store_code_present():
    pack = _brightline_full_pack()
    restoration_gbp = next(a for a in pack["accounts"] if a["system"] == "gbp" and a["brand"] == "restoration")
    assert restoration_gbp["store_code"] == "10000000000000000001"


def test_brightline_pack_facebook_asset_id_present():
    pack = _brightline_full_pack()
    fb_account = next(a for a in pack["accounts"] if a["system"] == "facebook")
    assert fb_account["asset_id"] == "100000000000002"


def test_brightline_pack_both_brand_phone_formats_present():
    pack = _brightline_full_pack()
    remodeling_brand = next(b for b in pack["brands"] if b["id"] == "remodeling")
    restoration_brand = next(b for b in pack["brands"] if b["id"] == "restoration")
    assert remodeling_brand["phones"] == ["(555) 010-1001"]
    assert restoration_brand["phones"] == ["(555) 010-1002"]
    ads_account = next(a for a in pack["accounts"] if a["system"] == "google_ads")
    assert ads_account["call_conversion_number"] == "555-010-1001"  # dash format, distinct literal


# Real identifiers (the company's real domains and account ids) must never
# appear in this fixture: test_no_real_company_identifiers.py scans every
# tools/gtm file for them by SHA-256 fingerprint.
