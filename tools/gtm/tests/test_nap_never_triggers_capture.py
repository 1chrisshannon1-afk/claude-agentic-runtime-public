"""Major 15: capture must trigger ONLY on a host match (URL) or an
account-id match in the URL or tool input -- NEVER on a NAP name, address,
or phone appearing in page text. A click on an unrelated site whose page
happens to mention "Brightline Remodeling" must not be captured or
attributed.
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


def _brightline_pack() -> dict:
    return {
        "schema_version": 1, "slug": "brightline", "legal_name": "Brightline", "display_names": ["Brightline Remodeling"],
        "business_model": "local_service",
        "brands": [
            {
                "id": "remodeling",
                "display_name": "Brightline Remodeling",
                "domains": ["example-remodeling.com"],
                "phones": ["(555) 010-1001"],
                "nap": {"name": "Brightline Remodeling", "address": "100 Example St, Suite 100, Example City, CO 80900", "phone": "(555) 010-1001"},
            }
        ],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": ["100-200-3000"], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["example-remodeling.com"], "listing_urls": [],
        },
        "claims_policy": {"terms": []},
        "ai_content_policy": {"mode": "disclose_never_strip", "disclosure_caption_line": "AI-generated"},
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
def registered_brightline(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_brightline_pack()), encoding="utf-8")
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


def test_nap_name_in_page_text_never_triggers_capture(registered_brightline, tmp_path):
    """RED-check: revert attribute_company/try_classify_call's eligibility
    check to use identity_index.company_for_text (the BROAD index, which
    includes NAP values) against result_text, instead of
    account_id_for_text against only the URL/tool_input, and this test's
    zero-records assertion fails -- the page text alone would wrongly
    make the click eligible and attributed to brightline."""
    transcript = tmp_path / "nap_click.jsonl"
    lines = [
        {
            "sessionId": "sess_nap", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {"type": "tool_use", "id": "tu_nap_click", "name": "mcp__playwright-adhoc__browser_click",
                 "input": {"element": "Read more"}},
            ]},
        },
        {
            "sessionId": "sess_nap", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {
                    "type": "tool_result", "tool_use_id": "tu_nap_click",
                    "content": (
                        "- Page URL: https://totally-unrelated-directory.example.net/reviews\n"
                        "Featured review: \"We hired Brightline Remodeling for our bathroom and loved it! "
                        "Call (555) 010-1001 or visit them at 100 Example St, Suite 100, Example City, CO 80900.\""
                    ),
                },
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 0

    unattributed_path = company.gtm_state_dir() / "unattributed_trail.jsonl"
    records, _ = activity_log.read_jsonl(unattributed_path)
    assert len(records) == 0


def test_account_id_in_url_still_triggers_capture(registered_brightline, tmp_path):
    """Paired recovery test: a genuine account-id match in the URL text
    itself still legitimately triggers capture and attribution -- the
    fix narrows what counts as a match, it does not disable account-id
    matching altogether."""
    transcript = tmp_path / "acct_click.jsonl"
    lines = [
        {
            "sessionId": "sess_acct", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {"type": "tool_use", "id": "tu_acct_click", "name": "mcp__playwright-adhoc__browser_click",
                 "input": {"element": "Save"}},
            ]},
        },
        {
            "sessionId": "sess_acct", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_acct_click",
                 "content": "- Page URL: https://some-ads-dashboard.example.net/account/100-200-3000/campaigns"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1


def test_account_id_in_tool_input_still_triggers_capture(registered_brightline, tmp_path):
    """An account id appearing in tool_input (not just the URL) also
    legitimately triggers capture, per major 15's "URL or tool input"
    wording."""
    transcript = tmp_path / "acct_input_click.jsonl"
    lines = [
        {
            "sessionId": "sess_acct2", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {"type": "tool_use", "id": "tu_acct2_click", "name": "mcp__playwright-adhoc__browser_click",
                 "input": {"element": "Save", "value": "100-200-3000"}},
            ]},
        },
        {
            "sessionId": "sess_acct2", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": "/unregistered/random/path",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tu_acct2_click",
                 "content": "- Page URL: https://some-ads-dashboard.example.net/x"},
            ]},
        },
    ]
    _write_transcript(transcript, lines)

    rc = htt.main([str(transcript)])
    assert rc == 0

    paths = activity_log.resolve_paths("brightline")
    records, _ = activity_log.read_jsonl(paths.trail_jsonl)
    assert len(records) == 1


def test_broad_identity_index_still_includes_nap_for_validator_use(registered_brightline):
    """Regression guard: the BROAD identity_index.json must still include
    NAP values (for validate_company's cross-pack collision checks) --
    major 15 narrows what the HARVESTER matches text against, it does not
    remove NAP data from the identity index file itself."""
    index_path = company.gtm_state_dir() / "identity_index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert "Brightline Remodeling" in data["brightline"]
    assert "(555) 010-1001" in data["brightline"]


def test_account_id_index_excludes_nap_and_domains():
    """The narrow account_id_index.json must contain ONLY genuine
    account/object ids -- never NAP values, never domains."""
    pack = _brightline_pack()
    ids = company._identity_account_ids(pack)
    assert "100-200-3000" in ids
    assert "Brightline Remodeling" not in ids
    assert "(555) 010-1001" not in ids
    assert "example-remodeling.com" not in ids
