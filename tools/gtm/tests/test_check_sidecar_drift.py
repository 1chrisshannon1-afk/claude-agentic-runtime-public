"""#20: `activity_log.py check` verifies the trail's sidecar `.ids` index
is not drifted from TOOL_TRAIL.jsonl -- independent of the harvester's own
silent self-healing (which rebuilds a drifted sidecar during a normal
harvest run without ever reporting that the drift happened).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
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
def registered_home(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_minimal_pack("acme")), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    return home


def _trail_record(tid: str, ts: str) -> dict:
    return {
        "tool_use_id": tid, "ts": ts, "session_id": "sess_1", "tool": "mcp__playwright-gtm__browser_click",
        "system": "google_ads",
    }


def test_check_passes_when_sidecar_matches(registered_home):
    paths = activity_log.resolve_paths("acme")
    htt._append_chained_trail(paths.trail_jsonl, _trail_record("tu_1", "2026-01-01T00:00:00"))

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0


def test_check_fails_when_sidecar_drifted(registered_home, capsys):
    """RED-check: remove the sidecar-verification block in cmd_check and
    this test's non-zero-exit + stderr-substring assertions both fail --
    a drifted sidecar (out-of-band trail edit) would go completely
    unreported by `check`."""
    paths = activity_log.resolve_paths("acme")
    htt._append_chained_trail(paths.trail_jsonl, _trail_record("tu_1", "2026-01-01T00:00:00"))

    # Out-of-band edit: append directly to the JSONL, bypassing the
    # sidecar-updating helper entirely, so the sidecar's header goes stale.
    with open(paths.trail_jsonl, "a", encoding="utf-8") as fh:
        record = _trail_record("tu_2", "2026-01-01T00:01:00")
        record["prev_hash"] = None
        fh.write(json.dumps(record) + "\n")

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc != 0
    err = capsys.readouterr().err
    assert "sidecar drifted" in err


def test_check_passes_when_no_sidecar_exists_yet(registered_home):
    """A trail with no sidecar at all (never harvested through the new
    tooling) is not itself a drift -- check must not fail merely because
    the optimization hasn't been exercised yet."""
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    paths.trail_jsonl.write_text(json.dumps(_trail_record("tu_1", "2026-01-01T00:00:00")) + "\n", encoding="utf-8")

    sidecar = htt._ids_sidecar_path(paths.trail_jsonl)
    assert not sidecar.exists()

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0
