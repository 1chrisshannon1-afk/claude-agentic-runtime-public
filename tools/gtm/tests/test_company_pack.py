"""Tests for tools/gtm/company.py — pack resolution, validation, .gitignore
generation, identity index, and backup-set. Every test builds its own tmp
`CLAUDE_DIR` + registry + pack; NEVER reads or writes the real ~/.claude,
real packs, or the real registry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _minimal_pack(slug: str, **overrides) -> dict:
    pack = {
        "schema_version": 1,
        "slug": slug,
        "legal_name": f"{slug} Legal Name",
        "display_names": [slug],
        "business_model": "local_service",
        "brands": [],
        "persona_file": "knowledge/marketing_kb/shared/x.md",
        "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": [], "listing_urls": [],
        },
        "claims_policy": {"terms": []},
        "ai_content_policy": {"mode": "strip_before_publish"},
        "autonomy": {"level": "shadow", "standing_approvals": []},
        "spend": {"currency": "USD", "monthly_cap_total": 0, "cap_ruling_ref": "none"},
        "budget": {
            "weekly_usd_cap_opus": 0, "weekly_usd_cap_sonnet": 0,
            "dispatch_caps_per_run": {
                "inbox": 8, "daily": 4, "weekly": 30, "monthly": 8, "mission": 60, "monthly_load": 8,
            },
        },
        "operator_input": "from_manifest",
        "inbox": "local_jsonl",
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


def _make_home(tmp_path: Path, slug: str, pack: dict) -> Path:
    home = tmp_path / f"home_{slug}"
    gtm_dir = home / ".claude" / "gtm"
    gtm_dir.mkdir(parents=True)
    (gtm_dir / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    return home


def _make_registry(tmp_path: Path, slugs_to_homes: dict[str, Path]) -> Path:
    claude_dir = tmp_path / "claude_dir"
    knowledge = claude_dir / "knowledge"
    knowledge.mkdir(parents=True)
    registry = {"schema_version": 1, "repos": {slug: {"root": str(home)} for slug, home in slugs_to_homes.items()}}
    (knowledge / "repo_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return claude_dir


@pytest.fixture()
def claude_env(tmp_path, monkeypatch):
    """Sets CLAUDE_DIR to a tmp dir with an empty registry. Tests add
    packs/homes and re-register via _register()."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    return claude_dir


def _register(claude_dir: Path, slug: str, home: Path) -> None:
    reg_path = claude_dir / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"][slug] = {"root": str(home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")


# --------------------------------------------------------------------------
# resolve
# --------------------------------------------------------------------------


def test_resolve_returns_home_for_registered_valid_pack(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    _register(claude_env, "acme", home)
    assert company.resolve_home("acme") == home.resolve()


def test_resolve_raises_for_unregistered_slug(tmp_path, claude_env):
    # RED-check: remove this assertion (or the `unregistered` slug lookup
    # entirely) and the test passes on nothing -- it must exercise a slug
    # that was never registered.
    with pytest.raises(company.CompanyError):
        company.resolve_home("nonexistent-slug")


# --------------------------------------------------------------------------
# validate: unknown key
# --------------------------------------------------------------------------


def test_validate_ok_for_a_clean_pack(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    _register(claude_env, "acme", home)
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_validate_rejects_unknown_key(tmp_path, claude_env):
    # RED-check: remove the `unknown = sorted(...)` loop in
    # validate_company() and this goes green on garbage input.
    pack = _minimal_pack("acme")
    pack["totally_made_up_key"] = "surprise"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("totally_made_up_key" in r for r in reasons)


# --------------------------------------------------------------------------
# validate: missing required key
# --------------------------------------------------------------------------


def test_validate_rejects_missing_required_key(tmp_path, claude_env):
    # RED-check: remove the `missing = [...]` loop and this passes wrongly.
    pack = _minimal_pack("acme")
    del pack["timezone"]
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("timezone" in r for r in reasons)


# --------------------------------------------------------------------------
# validate: slug shape (blocker fix -- both the registry key AND pack.slug
# must match SLUG_RE, since either can reach validate_company via `validate
# --all` iterating whatever a registry (or a hand-edited/corrupt one)
# happens to hold, not only via register_gtm_company's own write-time guard)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad_slug", ["../x", "a/b", "A", "", "a" * 40])
def test_validate_rejects_malshaped_registry_key(tmp_path, claude_env, bad_slug):
    """RED-check: remove the `SLUG_RE.match(slug)` check on the registry-key
    argument in validate_company and this fails -- a pack resolved by a
    malshaped registry key (e.g. one written directly to
    gtm_company_registry.json by hand, bypassing register_gtm_company's own
    guard) would validate OK despite the key being unsafe to use as a
    filesystem path component in backup_set/backup_company."""
    pack = _minimal_pack(bad_slug if bad_slug else "acme")
    pack["slug"] = bad_slug if bad_slug else "acme"
    ok, reasons = company.validate_company(bad_slug, pack, siblings={})
    assert not ok
    assert any(repr(bad_slug) in r for r in reasons)


@pytest.mark.parametrize("bad_slug", ["../x", "a/b", "A", "", "a" * 40])
def test_validate_rejects_malshaped_pack_slug(tmp_path, claude_env, bad_slug):
    """RED-check: remove the `SLUG_RE.match(pack_slug)` check on pack["slug"]
    in validate_company and this fails -- a pack whose OWN declared slug is
    malshaped (even when resolved by a validly-shaped registry key) would
    validate OK. This is the more directly prompt-injection-reachable half:
    an agent authoring company.json controls pack["slug"] directly."""
    pack = _minimal_pack("acme")
    pack["slug"] = bad_slug
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any(repr(bad_slug) in r for r in reasons)


def test_validate_ok_for_valid_slug_shapes(tmp_path, claude_env):
    """Recovery pair: a validly-shaped registry key + matching pack.slug
    still validates OK (no new false-positive from the SLUG_RE checks)."""
    pack = _minimal_pack("valid-slug9")
    ok, reasons = company.validate_company("valid-slug9", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# validate: shared credential_ref
# --------------------------------------------------------------------------


def test_validate_ok_when_credential_ref_is_unique(tmp_path, claude_env):
    pack_a = _minimal_pack("acme", accounts=[{"system": "google_ads", "brand": "x", "account_id": "1", "access": "api", "credential_ref": "gsm:acme-ads"}])
    pack_b = _minimal_pack("beta", accounts=[{"system": "google_ads", "brand": "x", "account_id": "2", "access": "api", "credential_ref": "gsm:beta-ads"}])
    ok, reasons = company.validate_company("acme", pack_a, siblings={"beta": pack_b})
    assert ok, reasons


def test_validate_rejects_shared_credential_ref(tmp_path, claude_env):
    # RED-check: remove the `my_refs & other_refs` intersection check and
    # this passes on a real collision.
    pack_a = _minimal_pack("acme", accounts=[{"system": "google_ads", "brand": "x", "account_id": "1", "access": "api", "credential_ref": "gsm:shared-secret"}])
    pack_b = _minimal_pack("beta", accounts=[{"system": "google_ads", "brand": "x", "account_id": "2", "access": "api", "credential_ref": "gsm:shared-secret"}])
    ok, reasons = company.validate_company("acme", pack_a, siblings={"beta": pack_b})
    assert not ok
    assert any("shared-secret" in r for r in reasons)


# --------------------------------------------------------------------------
# validate: identity value shared without shared_identifiers declaration
# --------------------------------------------------------------------------


def test_validate_ok_when_shared_identity_is_declared_identically(tmp_path, claude_env):
    pack_a = _minimal_pack(
        "acme",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["shared-vendor.example.com"], "listing_urls": [],
        },
        shared_identifiers=[{"value": "shared-vendor.example.com", "with": "beta", "relationship": "vendor", "ruling_ref": "R5", "source": "operator"}],
    )
    pack_b = _minimal_pack(
        "beta",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["shared-vendor.example.com"], "listing_urls": [],
        },
        shared_identifiers=[{"value": "shared-vendor.example.com", "with": "acme", "relationship": "vendor", "ruling_ref": "R5", "source": "operator"}],
    )
    ok, reasons = company.validate_company("acme", pack_a, siblings={"beta": pack_b})
    assert ok, reasons


def test_validate_rejects_shared_identity_not_declared(tmp_path, claude_env):
    # RED-check: remove the shared_identifiers reconciliation block in
    # validate_company() and this passes despite a real undeclared
    # cross-company identity collision.
    pack_a = _minimal_pack(
        "acme",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["cross-connected.example.com"], "listing_urls": [],
        },
    )
    pack_b = _minimal_pack(
        "beta",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["cross-connected.example.com"], "listing_urls": [],
        },
    )
    ok, reasons = company.validate_company("acme", pack_a, siblings={"beta": pack_b})
    assert not ok
    assert any("cross-connected.example.com" in r for r in reasons)


def test_validate_rejects_identity_in_other_businesses(tmp_path, claude_env):
    (claude_env / ".gtm_state").mkdir(parents=True, exist_ok=True)
    (claude_env / ".gtm_state" / "other_businesses.json").write_text(
        json.dumps({"maplewood": ["4100-example.example.com"]}), encoding="utf-8"
    )
    pack_a = _minimal_pack(
        "acme",
        identity_allowlist={
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["4100-example.example.com"], "listing_urls": [],
        },
    )
    ok, reasons = company.validate_company("acme", pack_a, siblings={})
    assert not ok
    assert any("other_businesses" in r for r in reasons)


# --------------------------------------------------------------------------
# validate: secret-shaped value
# --------------------------------------------------------------------------


def test_validate_rejects_secret_shaped_value_in_company_json(tmp_path, claude_env):
    # RED-check: remove the find_secret_shapes(pack) loop and this passes on
    # an embedded raw API key.
    pack = _minimal_pack("acme", lead_sink={"kind": "none", "ref": "AIzaSyD-abcdefghijklmnopqrstuvwxyz0123456"})
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("secret-shaped" in r for r in reasons)


def test_validate_rejects_secret_shaped_value_in_mcp_json(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    (home / ".claude" / "gtm" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"x": {"env": {"TOKEN": "password: sk-abcdefghijklmnop"}}}}), encoding="utf-8"
    )
    _register(claude_env, "acme", home)
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("mcp.json" in r for r in reasons)


def test_validate_ok_with_no_secret_shaped_values(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    (home / ".claude" / "gtm" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"x": {"command": "bash", "args": ["launch.sh"]}}}), encoding="utf-8"
    )
    _register(claude_env, "acme", home)
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# validate: wildcard in standing_approvals rows
# --------------------------------------------------------------------------


def test_validate_rejects_wildcard_standing_approval(tmp_path, claude_env):
    # RED-check: remove the `"*" in rows` check and this passes on a
    # wildcard standing approval, which the plan explicitly forbids (§3.3).
    pack = _minimal_pack(
        "acme",
        autonomy={"level": "shadow", "standing_approvals": [{"id": "R9", "verbatim": "x", "ts": "2026-01-01", "rows": ["*"]}]},
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("wildcard" in r for r in reasons)


def test_validate_ok_with_explicit_row_ids(tmp_path, claude_env):
    pack = _minimal_pack(
        "acme",
        autonomy={"level": "shadow", "standing_approvals": [{"id": "R9", "verbatim": "x", "ts": "2026-01-01", "rows": ["gbp.hours_edit"]}]},
    )
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# validate: regulated values
# --------------------------------------------------------------------------


def test_validate_rejects_bad_regulated_value(tmp_path, claude_env):
    pack = _minimal_pack("acme", regulated=["not_a_real_regulation"])
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("regulated" in r for r in reasons)


def test_validate_ok_with_hipaa_regulated(tmp_path, claude_env):
    pack = _minimal_pack("acme", regulated=["hipaa"])
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


# --------------------------------------------------------------------------
# validate: paths.mission_records enum
# --------------------------------------------------------------------------


def test_validate_rejects_bad_mission_records_value(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    pack["paths"]["mission_records"] = "sometimes"
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    assert any("mission_records" in r for r in reasons)


# --------------------------------------------------------------------------
# validate --all via CLI (subprocess, exit code)
# --------------------------------------------------------------------------


def test_cli_validate_all_reports_ok_and_invalid_separately(tmp_path, claude_env):
    good_pack = _minimal_pack("good")
    bad_pack = _minimal_pack("bad")
    del bad_pack["timezone"]
    good_home = _make_home(tmp_path, "good", good_pack)
    bad_home = _make_home(tmp_path, "bad", bad_pack)
    _register(claude_env, "good", good_home)
    _register(claude_env, "bad", bad_home)

    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_env)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "company.py"), "validate", "--all"],
        capture_output=True, text=True, env=env,
    )
    assert "OK good" in result.stdout
    assert "INVALID bad" in result.stdout
    assert result.returncode == 1


# --------------------------------------------------------------------------
# gitignore generation
# --------------------------------------------------------------------------


def test_gitignore_uses_negation_forms_never_bare_dir(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    text = company.generate_gitignore(pack)
    assert "gtm_mission/**" in text
    assert "!gtm_mission/**/" in text
    assert "!gtm_mission/**/*.md" in text
    # never a bare "gtm_mission/" line (which would make the negation
    # impossible per plan §3.2)
    for line in text.splitlines():
        assert line.strip() != "gtm_mission/"


def test_gitignore_tracked_mission_records_omits_mission_ignore_block(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    pack["paths"]["mission_records"] = "tracked"
    text = company.generate_gitignore(pack)
    assert "gtm_mission/**" not in text


def test_gitignore_always_includes_fixed_dirs(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    text = company.generate_gitignore(pack)
    assert ".claude/gtm/state/" in text
    assert ".claude/gtm/data/" in text
    assert ".playwright-mcp/" in text


def test_gitignore_md_negation_actually_reincludes_a_file(tmp_path, claude_env):
    """The one test that proves the generated .gitignore's negation forms
    actually work against real git, not just that the right strings are
    present in the output (a string-only test could pass a broken pattern
    order)."""
    pack = _minimal_pack("acme")
    text = company.generate_gitignore(pack)

    repo = tmp_path / "gitrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(text, encoding="utf-8")

    mission_dir = repo / "gtm_mission"
    mission_dir.mkdir()
    (mission_dir / "gtm_reviewed.jsonl").write_text("{}\n", encoding="utf-8")
    (mission_dir / "impl_seo.md").write_text("# doc\n", encoding="utf-8")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "gtm_mission/gtm_reviewed.jsonl"], cwd=repo,
    ).returncode
    tracked_md = subprocess.run(
        ["git", "check-ignore", "-q", "gtm_mission/impl_seo.md"], cwd=repo,
    ).returncode

    assert ignored == 0  # the .jsonl IS ignored
    assert tracked_md == 1  # the .md is NOT ignored (negation re-included it)


def test_cli_gitignore_snapshots_under_state_has_no_md_negation(tmp_path, claude_env):
    """B3: a snapshots_dir living UNDER .claude/gtm/state/ is covered by
    the plain, unconditional state/ ignore -- no separate .md-negation
    block (that form is reserved for a snapshots_dir OUTSIDE state/, which
    can legitimately carry tracked governing reports)."""
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    _register(claude_env, "acme", home)
    text = company.generate_gitignore(pack)
    assert ".claude/gtm/state/snapshots/**" not in text
    assert "!.claude/gtm/state/snapshots/**/*.md" not in text
    assert ".claude/gtm/state/" in text


# --------------------------------------------------------------------------
# index
# --------------------------------------------------------------------------


def test_index_contains_every_pack_identity_value(tmp_path, claude_env):
    pack_a = _minimal_pack(
        "acme",
        identity_allowlist={
            "facebook_page_ids": ["fb-1"], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["acme.example.com"], "listing_urls": [],
        },
    )
    home_a = _make_home(tmp_path, "acme", pack_a)
    _register(claude_env, "acme", home_a)

    (claude_env / ".gtm_state").mkdir(parents=True, exist_ok=True)
    (claude_env / ".gtm_state" / "other_businesses.json").write_text(
        json.dumps({"maplewood": ["phi1.example.com"]}), encoding="utf-8"
    )

    target = company.write_identity_index()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "fb-1" in data["acme"]
    assert "acme.example.com" in data["acme"]
    assert "phi1.example.com" in data["other_businesses"]


# --------------------------------------------------------------------------
# backup-set
# --------------------------------------------------------------------------


def test_backup_set_includes_state_dir_and_ignored_paths(tmp_path, claude_env):
    pack = _minimal_pack("acme")
    home = _make_home(tmp_path, "acme", pack)
    _register(claude_env, "acme", home)
    paths = company.backup_set("acme", pack)
    path_strs = {str(p) for p in paths}
    assert str(home / ".claude" / "gtm" / "state") in path_strs
    assert str(home / ".claude" / "gtm" / "data") in path_strs
    assert str(home / ".claude" / "gtm" / "state" / "scoreboard.csv") in path_strs
