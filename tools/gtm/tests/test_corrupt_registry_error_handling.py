"""Nit fixes: a corrupt/duplicate registry must never crash a CLI entry
point with a raw, uncaught traceback (harvest_tool_trail.py's `main`), and
`company.py index` must never silently drop a duplicate-registered slug
out of the written identity index with a clean exit 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402

_HERE = Path(__file__).resolve().parents[1]


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
def claude_env(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    return claude_dir


def _make_valid_home(tmp_path: Path, slug: str) -> Path:
    home = tmp_path / f"home_{slug}"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_minimal_pack(slug)), encoding="utf-8")
    return home


def _corrupt_gtm_registry(claude_env: Path) -> None:
    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text("{not valid json", encoding="utf-8")


# --------------------------------------------------------------------------
# harvest_tool_trail.py main(): a corrupt registry must exit non-zero with
# a clean reason, never crash with a raw traceback
# --------------------------------------------------------------------------


def test_harvest_main_reports_corrupt_registry_non_zero_never_crashes(tmp_path, claude_env, capsys):
    """RED-check: revert main()'s `homes = _registered_homes()` call back
    to no try/except and this fails -- a corrupt gtm_company_registry.json
    raises CompanyError from inside `_registered_homes` -> `registered_slugs`
    -> `_gtm_registry_companies`, uncaught, crashing `main` with a raw
    traceback instead of returning a clean non-zero exit code."""
    _corrupt_gtm_registry(claude_env)
    rc = htt.main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "unreadable" in err
    assert "gtm_company_registry.json" in err


def test_cli_harvest_reports_corrupt_registry_non_zero_never_crashes(tmp_path, claude_env):
    """Same property through the real subprocess CLI entry point -- a
    crash would show up as a non-empty stderr traceback and returncode 1
    from an unhandled exception (Python's default), which this test
    distinguishes from a CLEAN error message."""
    _corrupt_gtm_registry(claude_env)
    import os
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_env)
    result = subprocess.run(
        [sys.executable, str(_HERE / "harvest_tool_trail.py")],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "gtm_company_registry.json" in result.stderr


# --------------------------------------------------------------------------
# company.py index: a duplicate-registered slug must never be silently
# dropped from the written index with a clean exit 0
# --------------------------------------------------------------------------


def test_cmd_index_warns_and_fails_on_duplicate_slug(tmp_path, claude_env, capsys):
    """RED-check: remove the duplicate_slugs check in cmd_index and this
    fails -- a slug registered in BOTH registries is silently excluded
    from registered_slugs() (by design, at the resolve_home layer), so
    the written identity index and account_id index both drop it
    entirely, with cmd_index still printing "wrote ..." and exiting 0 as
    if nothing were wrong."""
    home_a = _make_valid_home(tmp_path, "acme")
    home_b = _make_valid_home(tmp_path, "acme_other")

    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["acme"] = {"root": str(home_b)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text(
        json.dumps({"schema_version": 1, "companies": {"acme": {"root": str(home_a)}}}), encoding="utf-8"
    )

    from argparse import Namespace
    rc = company.cmd_index(Namespace())
    assert rc != 0
    err = capsys.readouterr().err
    assert "acme" in err
    assert "BOTH" in err

    # And the written index genuinely excludes the duplicate slug --
    # confirming the warning corresponds to a real gap, not a spurious one.
    target = company.gtm_state_dir() / "identity_index.json"
    written = json.loads(target.read_text(encoding="utf-8"))
    assert "acme" not in written


def test_cmd_index_clean_exit_with_no_duplicates(tmp_path, claude_env, capsys):
    """Paired recovery test: a registry with no duplicate slugs still
    exits 0 with no warning -- the fix must not become an overbroad
    failure on the common, non-duplicated case."""
    home = _make_valid_home(tmp_path, "acme")
    company.register_gtm_company("acme", str(home))

    from argparse import Namespace
    rc = company.cmd_index(Namespace())
    assert rc == 0
    err = capsys.readouterr().err
    assert err == ""
