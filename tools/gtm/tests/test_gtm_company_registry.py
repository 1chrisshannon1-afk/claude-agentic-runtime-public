"""GTM company registry: gtm_company_registry.json gives a home with no
GitHub remote (Brightline, Maplewood, Opswell) a place to register,
since scripts/repo_manifest.py is frozen and its own `register` refuses a
remote-less home. Resolution order: gtm_company_registry.json first, then
repo_registry.json for slugs not already there; a slug in BOTH is INVALID.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import company  # noqa: E402


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


def _make_home_with_facebook_page_id(tmp_path: Path, slug: str, facebook_page_id: str) -> Path:
    pack = _minimal_pack(slug)
    pack["identity_allowlist"]["facebook_page_ids"] = [facebook_page_id]
    home = tmp_path / f"home_{slug}"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    return home


def _make_home_with_accounts(tmp_path: Path, slug: str, accounts: list[dict]) -> Path:
    pack = _minimal_pack(slug)
    pack["accounts"] = accounts
    home = tmp_path / f"home_{slug}"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    return home


def _make_home_at(tmp_path: Path, dirname: str, pack_slug: str) -> Path:
    """Like _make_valid_home, but the on-disk directory name and the pack's
    own `slug` value are independent -- needed for tests that must register
    the SAME slug against TWO different roots (e.g. the different-root
    refusal guards) without the pack-slug-mismatch check in
    validate_company firing first and masking the guard actually under
    test."""
    home = tmp_path / dirname
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_minimal_pack(pack_slug)), encoding="utf-8")
    return home


# --------------------------------------------------------------------------
# register / unregister
# --------------------------------------------------------------------------


def test_register_writes_gtm_company_registry(tmp_path, claude_env):
    home = _make_valid_home(tmp_path, "brightline")
    target = company.register_gtm_company("brightline", str(home))
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["companies"]["brightline"]["root"] == str(home.resolve())


def test_cli_register_success_message_prints_resolved_root(tmp_path, claude_env, capsys, monkeypatch):
    """Nit fix #9: `cmd_register`'s success message must print the
    RESOLVED absolute root that was actually written to the registry, not
    `args.root` as typed. Uses a RELATIVE --root (via a cwd change) so the
    typed and resolved forms genuinely differ -- this is exactly the case
    the pre-fix code got wrong.

    RED-check: revert cmd_register to print `args.root` directly (its
    pre-fix shape) and this test's assertion fails -- the printed message
    shows the relative path instead of the resolved absolute one."""
    from argparse import Namespace

    home = _make_valid_home(tmp_path, "brightline")
    monkeypatch.chdir(tmp_path)
    relative_root = home.name  # e.g. "home_brightline" -- relative to tmp_path

    rc = company.cmd_register(Namespace(slug="brightline", root=relative_root))
    assert rc == 0

    out = capsys.readouterr().out.strip()
    printed_root = out.split(" -> ", 1)[1].split(" (in ", 1)[0]
    assert printed_root == str(home.resolve()), (
        f"expected the resolved absolute root {home.resolve()!r}, got {printed_root!r} "
        f"(the typed relative form was {relative_root!r})"
    )


@pytest.mark.parametrize(
    "bad_slug",
    [
        "../x",
        "a/b",
        "A",
        "",
        "a" * 40,
    ],
)
def test_register_refuses_malshaped_slug(tmp_path, claude_env, bad_slug):
    """Blocker fix: register_gtm_company must reject a slug that doesn't
    match SLUG_RE (`^[a-z][a-z0-9-]{1,31}$`, the same shape
    scripts/repo_manifest.py enforces for a repo_registry.json key) BEFORE
    ever taking the registry lock or touching the filesystem.

    Probe that motivated this fix: pre-fix, `register_gtm_company("../../evil",
    home)` succeeded when the pack's own slug was "../../evil" -- backup_set()
    then returned paths like `<CLAUDE_DIR>/.gtm_state/tickets/../../evil`
    that resolve OUTSIDE .gtm_state/, and backup_company()'s `dest_root /
    slug` escapes ~/Backups/gtm/ the same way. Packs are agent-authored
    (/gtm-onboard), so this is prompt-injection-reachable.

    RED-check: remove the `SLUG_RE.match(slug)` guard at the top of
    register_gtm_company and this fails for every case above -- with a
    genuinely valid pack on disk (so a missing-pack refusal can never mask
    the slug-shape one), 'A' (uppercase) and '' and the 40-char slug would
    all register successfully, and '../x' / 'a/b' would go on to build a
    pack file path with path-traversal components instead of being refused
    up front."""
    home = tmp_path / "home_malshaped"
    (home / ".claude" / "gtm").mkdir(parents=True)
    home_pack_slug = bad_slug if bad_slug else "acme"
    home_pack_slug = home_pack_slug if company.SLUG_RE.match(home_pack_slug) else "acme"
    (home / ".claude" / "gtm" / "company.json").write_text(
        json.dumps(_minimal_pack(home_pack_slug)), encoding="utf-8"
    )
    with pytest.raises(company.CompanyError):
        company.register_gtm_company(bad_slug, str(home))
    assert not company.gtm_registry_path().exists()


def test_register_malshaped_slug_never_escapes_gtm_state_via_backup_set(tmp_path, claude_env):
    """Direct probe for the escape this blocker closes: even if
    register_gtm_company's SLUG_RE guard were somehow bypassed,
    backup_set() must never be handed a slug that resolves outside
    .gtm_state/ -- this test asserts the guard actually stops the escape
    at the point of entry (register), which is the one and only place an
    agent-authored pack's slug becomes a registry key at all.

    RED-check: with the SLUG_RE guard removed from register_gtm_company,
    `register_gtm_company("../../evil", home)` succeeds and
    `company.backup_set("../../evil", pack)` (called after resolve_home
    resolves the escaped registry entry) returns tickets/leases paths
    containing '..' components that resolve outside .gtm_state/ -- this
    test's `pytest.raises` would then never fire, exposing that the
    write path was reachable at all."""
    home = tmp_path / "home_evil"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(
        json.dumps(_minimal_pack("../../evil")), encoding="utf-8"
    )
    with pytest.raises(company.CompanyError):
        company.register_gtm_company("../../evil", str(home))
    assert not company.gtm_registry_path().exists()


def test_register_valid_slug_still_registers_and_resolves(tmp_path, claude_env):
    """Recovery pair for test_register_refuses_malshaped_slug: a
    genuinely valid slug (lowercase, within length, no path separators)
    still registers cleanly and resolve_home finds it."""
    home = _make_valid_home(tmp_path, "valid-slug9")
    target = company.register_gtm_company("valid-slug9", str(home))
    assert target.exists()
    assert company.resolve_home("valid-slug9") == home.resolve()


def test_register_refuses_missing_pack(tmp_path, claude_env):
    """RED-check: remove the pack-existence check in register_gtm_company
    and this fails -- a slug pointing at a home with no company.json at
    all would register successfully."""
    home = tmp_path / "home_no_pack"
    home.mkdir()
    with pytest.raises(company.CompanyError):
        company.register_gtm_company("no_pack_co", str(home))
    assert not company.gtm_registry_path().exists()


def test_register_refuses_invalid_pack(tmp_path, claude_env):
    """RED-check: remove the validate_company() call in
    register_gtm_company and this fails -- a company.json missing every
    required key would register successfully."""
    home = tmp_path / "home_bad_pack"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps({"slug": "bad"}), encoding="utf-8")
    with pytest.raises(company.CompanyError):
        company.register_gtm_company("bad_co", str(home))


def test_register_refuses_slug_already_registered_to_different_root(tmp_path, claude_env):
    """Lock-in-test fix: home2's PACK must declare the SAME slug
    ("brightline") as home1's, at a different on-disk root -- registering
    the SAME slug under a different root is exactly the shape the
    different-root guard in _register_gtm_company_locked (the
    `if slug in gtm_companies:` branch) exists to refuse. The prior version
    of this test built home2 via `_make_valid_home(tmp_path, "brightline2")`,
    whose pack therefore declared `slug: "brightline2"` -- registering it as
    "brightline" ALSO trips validate_company's independent
    pack.slug-must-equal-registry-key check, so the test could never fail on
    the thing its name claims to protect.

    RED-check: comment out the `if existing_root != root_path: raise ...`
    block under `if slug in gtm_companies:` in _register_gtm_company_locked
    and this test fails (register succeeds silently for the second root)."""
    home1 = _make_home_at(tmp_path, "home1", "brightline")
    home2 = _make_home_at(tmp_path, "home2", "brightline")
    company.register_gtm_company("brightline", str(home1))
    with pytest.raises(company.CompanyError):
        company.register_gtm_company("brightline", str(home2))


def test_register_refuses_slug_already_in_repo_registry_same_root(tmp_path, claude_env):
    """The `if slug in repos:` branch's SAME-root case (line ~343-345 in
    _register_gtm_company_locked) had no test at all -- a slug already
    registered in repo_registry.json must be refused even when the
    requested root matches exactly (this tool never writes
    repo_registry.json, so it can never "idempotently" claim a slug that
    registry already owns).

    RED-check: remove the `if slug in repos:` branch entirely and this
    test fails (register would fall through and write
    gtm_company_registry.json for a slug repo_registry.json already owns,
    creating the BOTH-registries invalid state resolve_home refuses)."""
    home = _make_home_at(tmp_path, "home_repo_owned", "brightline")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["brightline"] = {"root": str(home.resolve())}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(company.CompanyError):
        company.register_gtm_company("brightline", str(home))
    # Registering must leave gtm_company_registry.json untouched -- no
    # BOTH-registries state was created.
    assert not company.gtm_registry_path().exists()


def test_register_refuses_slug_already_in_repo_registry_different_root(tmp_path, claude_env):
    """The `if slug in repos:` branch's DIFFERENT-root case (line ~340-343):
    a slug already owned by repo_registry.json at one root must be refused
    when a DIFFERENT root is requested too -- distinct from the same-root
    case above (a different message, and a different early-exit path)."""
    owned_home = _make_home_at(tmp_path, "home_owned", "brightline")
    other_home = _make_home_at(tmp_path, "home_other", "brightline")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["brightline"] = {"root": str(owned_home.resolve())}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(company.CompanyError):
        company.register_gtm_company("brightline", str(other_home))
    assert not company.gtm_registry_path().exists()


def test_register_succeeds_for_fresh_slug_not_in_either_registry(tmp_path, claude_env):
    """Recovery pair for the three refusal tests above: a genuinely fresh
    slug, present in NEITHER registry, still registers cleanly."""
    home = _make_home_at(tmp_path, "home_fresh", "freshco")
    target = company.register_gtm_company("freshco", str(home))
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["companies"]["freshco"]["root"] == str(home.resolve())


def test_register_idempotent_for_same_root(tmp_path, claude_env):
    home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(home))
    company.register_gtm_company("brightline", str(home))  # must not raise
    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert data["companies"]["brightline"]["root"] == str(home.resolve())


def test_unregister_removes_entry(tmp_path, claude_env):
    home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(home))
    company.unregister_gtm_company("brightline")
    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert "brightline" not in data["companies"]


def test_unregister_refuses_unknown_slug(tmp_path, claude_env):
    with pytest.raises(company.CompanyError):
        company.unregister_gtm_company("never_registered")


# --------------------------------------------------------------------------
# resolution order + duplicate detection
# --------------------------------------------------------------------------


def test_resolve_home_via_gtm_registry(tmp_path, claude_env):
    home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(home))
    assert company.resolve_home("brightline") == home.resolve()


def test_resolve_home_via_gtm_registry_with_no_repo_registry_json_at_all(tmp_path, claude_env):
    """Major finding #5 (regression fix): a GTM-only home (Brightline,
    Maplewood, Opswell) registers exclusively in
    gtm_company_registry.json and may have no repo_registry.json at all --
    resolving it must never depend on repo_registry.json's mere presence.

    RED-check: revert `_repo_registry_repos` to call `load_registry()`
    unconditionally (its pre-fix shape) and this fails with 'registry not
    found: .../repo_registry.json' even though the GTM registry genuinely
    has the entry -- a missing repo_registry.json silently made every
    GTM-only company unresolvable."""
    home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(home))

    reg_path = claude_env / "knowledge" / "repo_registry.json"
    assert reg_path.exists()
    reg_path.unlink()
    assert not reg_path.exists()

    assert company.resolve_home("brightline") == home.resolve()
    assert company.registered_slugs() == ["brightline"]


def test_resolve_home_via_repo_registry_still_works(tmp_path, claude_env):
    """CSA and Agency (repo_registry.json-registered) keep resolving there
    -- the new GTM registry is additive, never a replacement."""
    home = _make_valid_home(tmp_path, "buildwiseai")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["buildwiseai"] = {"root": str(home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    assert company.resolve_home("buildwiseai") == home.resolve()


def test_registered_slugs_includes_both_registries(tmp_path, claude_env):
    ts_home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(ts_home))

    csa_home = _make_valid_home(tmp_path, "buildwiseai")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["buildwiseai"] = {"root": str(csa_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    slugs = company.registered_slugs()
    assert "brightline" in slugs
    assert "buildwiseai" in slugs


def test_duplicate_slug_across_both_registries_is_invalid(tmp_path, claude_env):
    """RED-check: remove the in_gtm-and-in_repo_registry check in
    resolve_home and this fails -- resolve_home would silently pick one
    registry's root instead of refusing the ambiguous configuration."""
    ts_home = _make_valid_home(tmp_path, "brightline")
    other_home = _make_valid_home(tmp_path, "brightline_other")

    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["brightline"] = {"root": str(other_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text(
        json.dumps({"schema_version": 1, "companies": {"brightline": {"root": str(ts_home)}}}), encoding="utf-8"
    )

    with pytest.raises(company.CompanyError):
        company.resolve_home("brightline")


def test_duplicate_slug_excluded_from_registered_slugs_list(tmp_path, claude_env):
    ts_home = _make_valid_home(tmp_path, "brightline")
    other_home = _make_valid_home(tmp_path, "brightline_other")

    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["brightline"] = {"root": str(other_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text(
        json.dumps({"schema_version": 1, "companies": {"brightline": {"root": str(ts_home)}}}), encoding="utf-8"
    )

    assert "brightline" not in company.registered_slugs()


def test_cli_validate_all_reports_duplicate_as_invalid(tmp_path, claude_env):
    import subprocess

    ts_home = _make_valid_home(tmp_path, "brightline")
    other_home = _make_valid_home(tmp_path, "brightline_other")

    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["brightline"] = {"root": str(other_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text(
        json.dumps({"schema_version": 1, "companies": {"brightline": {"root": str(ts_home)}}}), encoding="utf-8"
    )

    import os
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_env)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "company.py"), "validate", "--all"],
        capture_output=True, text=True, env=env,
    )
    assert "INVALID brightline" in result.stdout
    assert result.returncode == 1


def test_claude_dir_override_never_touches_real_registry(tmp_path, claude_env):
    """The CLAUDE_DIR override must be what every gtm registry function
    reads from -- never the real ~/.claude/knowledge/gtm_company_registry.json."""
    assert str(claude_env) in str(company.gtm_registry_path())
    assert not company.gtm_registry_path().exists()


# --------------------------------------------------------------------------
# Major finding: an unreadable (present-but-corrupt) registry must RAISE,
# never be silently treated the same as "no registry / nothing registered".
# --------------------------------------------------------------------------


def _corrupt_gtm_registry(claude_env: Path) -> None:
    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text("{not valid json", encoding="utf-8")


def _corrupt_repo_registry(claude_env: Path) -> None:
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    reg_path.write_text("{not valid json", encoding="utf-8")


def test_resolve_home_raises_diagnosis_not_slug_not_registered_on_corrupt_gtm_registry(tmp_path, claude_env):
    """RED-check: revert _gtm_registry_companies to swallow CompanyError
    into {} and this fails -- resolve_home would say 'slug not registered:
    csa' instead of surfacing the real 'gtm_company_registry.json
    unreadable' diagnosis, losing the actual failure reason."""
    _corrupt_gtm_registry(claude_env)
    with pytest.raises(company.CompanyError) as excinfo:
        company.resolve_home("csa")
    assert "unreadable" in str(excinfo.value)
    assert "gtm_company_registry.json" in str(excinfo.value)


def test_resolve_home_raises_and_names_file_on_corrupt_repo_registry(tmp_path, claude_env):
    """Corrupt repo_registry.json (message names the file). RED-check:
    revert load_registry's error message back to the bare 'registry
    unreadable: {exc}' (no path) and this fails -- the finding's own
    required shape is a message that NAMES the file, not just says
    "a registry" was unreadable."""
    _corrupt_repo_registry(claude_env)
    with pytest.raises(company.CompanyError) as excinfo:
        company.resolve_home("buildwiseai")
    assert "unreadable" in str(excinfo.value)
    assert "repo_registry.json" in str(excinfo.value)


def test_register_refuses_duplicate_check_when_repo_registry_corrupt(tmp_path, claude_env):
    """RED-check: revert _repo_registry_repos to swallow errors into {} and
    this fails -- register_gtm_company would skip the duplicate-slug check
    against repo_registry.json entirely (treating a corrupt file as "no
    repos registered there") and register a slug that repo_registry.json
    may already claim under a DIFFERENT root, silently."""
    home = _make_valid_home(tmp_path, "brightline")
    _corrupt_repo_registry(claude_env)
    with pytest.raises(company.CompanyError) as excinfo:
        company.register_gtm_company("brightline", str(home))
    assert "unreadable" in str(excinfo.value)
    assert not company.gtm_registry_path().exists()


def test_registered_slugs_raises_on_corrupt_gtm_registry_even_with_duplicate_present(tmp_path, claude_env):
    """Corrupt-GTM-plus-duplicate-slug scenario: registered_slugs() must
    raise (never silently resolve to just the repo_registry side, which
    would hide that a duplicate might ALSO be sitting in the corrupt GTM
    registry)."""
    csa_home = _make_valid_home(tmp_path, "buildwiseai")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["buildwiseai"] = {"root": str(csa_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    _corrupt_gtm_registry(claude_env)

    with pytest.raises(company.CompanyError):
        company.registered_slugs()


def test_cli_validate_all_reports_corrupt_gtm_registry_non_zero_with_reason(tmp_path, claude_env):
    """`validate --all` with a corrupt GTM registry: non-zero exit, reason
    printed -- never an uncaught traceback, and never a silent 'no
    registered slugs found' as if the registry were merely empty."""
    import os
    import subprocess

    _corrupt_gtm_registry(claude_env)

    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_env)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "company.py"), "validate", "--all"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "unreadable" in result.stderr or "unreadable" in result.stdout
    assert "gtm_company_registry.json" in result.stderr or "gtm_company_registry.json" in result.stdout


# --------------------------------------------------------------------------
# Major finding: register_gtm_company must run the REAL cross-pack checks
# (identity_allowlist overlap, credential_ref reuse) against every OTHER
# currently registered pack, not siblings={}.
# --------------------------------------------------------------------------


def test_register_refuses_shared_facebook_page_id_with_already_registered_company(tmp_path, claude_env):
    """RED-check: revert register_gtm_company's validate_company call back
    to siblings={} and this fails -- registering 'maplewood' with the
    SAME facebook_page_id as the already-registered 'brightline' would
    silently succeed, exactly the never-cross-connect-businesses failure
    the operator's standing rule exists to catch at registration time."""
    shared_fb_page_id = "100000000000099"
    ts_home = _make_home_with_facebook_page_id(tmp_path, "brightline", shared_fb_page_id)
    company.register_gtm_company("brightline", str(ts_home))

    phi1_home = _make_home_with_facebook_page_id(tmp_path, "maplewood", shared_fb_page_id)
    with pytest.raises(company.CompanyError) as excinfo:
        company.register_gtm_company("maplewood", str(phi1_home))
    assert shared_fb_page_id in str(excinfo.value)

    # And the second company was never actually written to the registry --
    # a refused registration must not partially land.
    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert "maplewood" not in data["companies"]


def test_register_allows_distinct_facebook_page_ids_across_companies(tmp_path, claude_env):
    """Paired recovery test: two companies with genuinely DIFFERENT
    facebook_page_ids register cleanly -- the cross-pack check must not
    become an overbroad "any two companies with an FB page id" refusal."""
    ts_home = _make_home_with_facebook_page_id(tmp_path, "brightline", "100000000000099")
    company.register_gtm_company("brightline", str(ts_home))

    # Slug fix (SLUG_RE blocker): "buildwiseai_gtm" (underscore) does
    # not match SLUG_RE (`^[a-z][a-z0-9-]{1,31}$`, hyphen-only) -- renamed to
    # "buildwiseai-gtm", a test-local slug with no bearing on the
    # real registered "buildwiseai" company elsewhere.
    csa_home = _make_home_with_facebook_page_id(tmp_path, "buildwiseai-gtm", "11111111111111")
    company.register_gtm_company("buildwiseai-gtm", str(csa_home))  # must not raise

    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert "brightline" in data["companies"]
    assert "buildwiseai-gtm" in data["companies"]


# --------------------------------------------------------------------------
# Blocker finding: a `browser:<server>` credential_ref is a per-session
# Playwright server NAME, not a shared secret -- every company's browser
# accounts legitimately use the same server name (e.g.
# "browser:playwright-gtm", per plan §3.3/§3.4), so it must NEVER be treated
# as a credential that must be unique across packs. Only a `gsm:` ref is a
# real shared-secret reference.
# --------------------------------------------------------------------------


def test_register_allows_two_packs_sharing_the_same_browser_credential_ref(tmp_path, claude_env):
    """RED-check: revert `_credential_refs` back to excluding only the
    literal 'none' (treating every non-'none' credential_ref, browser:*
    included, as a unique-across-packs credential) and this fails --
    registering 'beta' after 'alpha' (both using
    credential_ref: "browser:playwright-gtm", the shape every browser
    account in the Brightline fixture uses) is refused with
    "credential_ref 'browser:playwright-gtm' is also used by pack 'alpha'",
    even though the registry's stated job is to hold Brightline, Maplewood,
    and Opswell side by side."""
    browser_accounts = [
        {"system": "facebook", "brand": "main", "account_id": "1", "access": "browser",
         "credential_ref": "browser:playwright-gtm"},
        {"system": "gbp", "brand": "main", "account_id": "2", "access": "browser",
         "credential_ref": "browser:playwright-gtm"},
    ]
    alpha_home = _make_home_with_accounts(tmp_path, "alpha", browser_accounts)
    company.register_gtm_company("alpha", str(alpha_home))

    beta_home = _make_home_with_accounts(tmp_path, "beta", browser_accounts)
    company.register_gtm_company("beta", str(beta_home))  # must not raise

    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert "alpha" in data["companies"]
    assert "beta" in data["companies"]

    # validate --all must also report both packs valid, not just register().
    ok_alpha, reasons_alpha = company.validate_company("alpha", company.load_pack("alpha"))
    assert ok_alpha, reasons_alpha
    ok_beta, reasons_beta = company.validate_company("beta", company.load_pack("beta"))
    assert ok_beta, reasons_beta


def test_register_still_refuses_two_packs_sharing_a_gsm_credential_ref(tmp_path, claude_env):
    """Paired recovery test: a genuine shared SECRET (a gsm: ref) must still
    be refused across packs -- the fix narrows what counts as a reusable
    credential, it does not disable the reuse check altogether."""
    shared_gsm_accounts = [
        {"system": "google_ads", "brand": "main", "account_id": "1", "access": "api",
         "credential_ref": "gsm:shared-ads-token"},
    ]
    alpha_home = _make_home_with_accounts(tmp_path, "alpha", shared_gsm_accounts)
    company.register_gtm_company("alpha", str(alpha_home))

    beta_home = _make_home_with_accounts(tmp_path, "beta", shared_gsm_accounts)
    with pytest.raises(company.CompanyError) as excinfo:
        company.register_gtm_company("beta", str(beta_home))
    assert "gsm:shared-ads-token" in str(excinfo.value)


# --------------------------------------------------------------------------
# Minor finding (never-cross-connect-businesses, plan §20.9a): a
# repo_registry.json entry registered for OTHER runtime tooling (e.g.
# Agency) must never be treated as a GTM candidate -- its root must never
# even be STAT'ED by GTM tooling, regardless of whether a pack happens to
# exist there.
# --------------------------------------------------------------------------


def test_agency_repo_registry_entry_is_never_a_gtm_candidate(tmp_path, claude_env, monkeypatch):
    """RED-check: revert `registered_slugs`/`resolve_home` to use the raw
    `_repo_registry_repos()` (no `_gtm_eligible_repo_registry_repos()`
    filtering) and this fails -- an 'agency' entry in repo_registry.json
    (exactly the shape the real ~/.claude/knowledge/repo_registry.json
    carries) is picked up by `registered_slugs()` and resolvable via
    `resolve_home('agency')`, making it a full GTM candidate: `_all_packs()`
    (run on every `register`/`validate --all`) would stat its
    .claude/gtm/company.json, and harvest_tool_trail.py's default globs
    (built from the same registered-homes set) would glob and open its
    session transcripts -- both forbidden outright by plan §20.9a."""
    agency_home = tmp_path / "home_agency"
    agency_home.mkdir(parents=True)
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["agency"] = {"root": str(agency_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    assert "agency" not in company.registered_slugs()
    with pytest.raises(company.CompanyError):
        company.resolve_home("agency")


def test_agency_root_is_never_stat_ed_by_all_packs(tmp_path, claude_env, monkeypatch):
    """RED-check: same revert as above -- `_all_packs()` (called by
    `register_gtm_company`'s cross-pack checks, and by `validate --all`)
    would call `Path.exists()`/stat the Agency root's company.json path,
    even though nothing ever reads its content in this test (no pack file
    is written there at all -- if `_all_packs` merely fails to find one and
    moves on, that already means it looked; instrumenting `Path.exists`
    proves the ROOT ITSELF was never even checked, which is the '...never
    opens, lists, greps, or files against ~/Desktop/OtherApp' standard
    §20.9a actually sets)."""
    agency_home = tmp_path / "home_agency"
    agency_home.mkdir(parents=True)
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["agency"] = {"root": str(agency_home)}
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    checked_paths: list[Path] = []
    real_exists = Path.exists

    def _tracking_exists(self):
        if agency_home in self.parents or self == agency_home:
            checked_paths.append(self)
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _tracking_exists)

    # A second, real GTM home so _all_packs() has at least one pack to
    # actually load -- proving the function runs its normal work, not that
    # it short-circuits on an empty registry.
    ts_home = _make_valid_home(tmp_path, "brightline")
    company.register_gtm_company("brightline", str(ts_home))

    assert not checked_paths, (
        f"Agency root path(s) were stat'ed by GTM tooling: {checked_paths} -- "
        "plan §20.9a forbids this unconditionally."
    )


# --------------------------------------------------------------------------
# Blocker finding: register_gtm_company must scan <home>/.claude/gtm/mcp.json
# for secret-shaped content on the FIRST registration, not just on a later
# `validate --all` run when the slug is already registered.
# --------------------------------------------------------------------------


def test_register_refuses_mcp_json_secret_on_first_registration(tmp_path, claude_env):
    """RED-check: revert validate_company's home= parameter / register's
    home=root_path argument and this fails -- register_gtm_company would
    resolve_home(slug) internally, get CompanyError (the slug isn't in any
    registry yet, since this call IS the registration), silently skip the
    mcp.json secret scan, and register successfully. A validate --all run
    immediately afterwards would then report INVALID for the same pack --
    the registry gate having let through exactly what it exists to refuse."""
    home = _make_valid_home(tmp_path, "brightline")
    (home / ".claude" / "gtm" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"x": {"env": {"API_TOKEN": "sk-live-abcdefghijklmnop"}}}}),
        encoding="utf-8",
    )
    with pytest.raises(company.CompanyError) as excinfo:
        company.register_gtm_company("brightline", str(home))
    assert "mcp.json" in str(excinfo.value)
    assert not company.gtm_registry_path().exists()


def test_register_allows_mcp_json_with_no_secret(tmp_path, claude_env):
    """Paired recovery test: an mcp.json with no secret-shaped content
    registers cleanly -- the fix must not become an overbroad refusal of
    every mcp.json."""
    home = _make_valid_home(tmp_path, "brightline")
    (home / ".claude" / "gtm" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"x": {"env": {"MODE": "prod"}}}}),
        encoding="utf-8",
    )
    company.register_gtm_company("brightline", str(home))  # must not raise
    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert "brightline" in data["companies"]


# --------------------------------------------------------------------------
# Nit finding: register_gtm_company edge cases -- a non-dict registry entry
# must raise CompanyError (never a raw AttributeError), and a missing/empty
# root must never resolve to the caller's cwd.
# --------------------------------------------------------------------------


def test_register_refuses_cleanly_on_non_dict_repo_registry_entry(tmp_path, claude_env):
    """RED-check: revert register_gtm_company / _entry_root_path back to
    calling `repos[slug].get(...)` directly and this fails -- a non-dict
    repo_registry.json entry raises a raw AttributeError instead of a
    clean CompanyError."""
    home = _make_valid_home(tmp_path, "acme")
    reg_path = claude_env / "knowledge" / "repo_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["repos"]["acme"] = "not-a-dict"
    reg_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(company.CompanyError):
        company.register_gtm_company("acme", str(home))


def test_register_refuses_missing_root_does_not_match_cwd(tmp_path, claude_env, monkeypatch):
    """RED-check: revert _entry_root_path to `Path(str(entry.get("root",
    ""))).expanduser().resolve()` (the old inline form) and this fails --
    a registry entry with NO 'root' key resolves `Path("").resolve()`,
    which is the process's cwd, so registering a NEW company FROM that
    same cwd would falsely compare equal to the missing root and be
    treated as "idempotent re-registration of the same root" (silently
    succeeding with no error) instead of refusing."""
    home = _make_valid_home(tmp_path, "acme")
    # chdir to the EXACT directory being registered, so Path("").resolve()
    # (what the old unguarded code computed for a missing 'root') equals
    # root_path exactly -- the precise false-match this fix closes.
    monkeypatch.chdir(home)

    gtm_reg_path = company.gtm_registry_path()
    gtm_reg_path.parent.mkdir(parents=True, exist_ok=True)
    gtm_reg_path.write_text(
        json.dumps({"schema_version": 1, "companies": {"acme": {}}}), encoding="utf-8"
    )

    with pytest.raises(company.CompanyError):
        company.register_gtm_company("acme", str(home))


def test_concurrent_register_calls_never_lose_an_update(tmp_path, claude_env):
    """RED-check: revert register_gtm_company to skip the
    `_gtm_registry_lock_path()` lock (read-modify-write with no lock held)
    and this test is flaky-to-reliably-failing -- two concurrent
    `register` calls for DIFFERENT slugs can each read the registry before
    the other writes, and the second write clobbers the first slug's
    entry out of the final file (lost update)."""
    import threading

    homes = {slug: _make_valid_home(tmp_path, slug) for slug in ("acme", "beta", "gamma", "delta")}

    errors: list[BaseException] = []

    def register_one(slug: str) -> None:
        try:
            company.register_gtm_company(slug, str(homes[slug]))
        except BaseException as exc:  # noqa: BLE001 - must capture every failure mode
            errors.append(exc)

    threads = [threading.Thread(target=register_one, args=(slug,)) for slug in homes]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not any(t.is_alive() for t in threads)
    assert not errors, errors

    data = json.loads(company.gtm_registry_path().read_text(encoding="utf-8"))
    assert set(data["companies"]) == set(homes), (
        f"lost update: expected all of {sorted(homes)}, got {sorted(data['companies'])}"
    )


def test_cli_index_reports_corrupt_gtm_registry_non_zero_with_reason(tmp_path, claude_env):
    """A corrupt GTM registry must fail the identity index build loudly --
    never silently drop every GTM-only company (Brightline/Maplewood) out
    of the written index with a clean 0 exit."""
    import os
    import subprocess

    _corrupt_gtm_registry(claude_env)

    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_env)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "company.py"), "index"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "unreadable" in result.stderr


# --------------------------------------------------------------------------
# Major finding #3: gtm_company_registry.json's lock file and mkstemp temp
# files must never be trackable in the real ~/.claude repo.
#
# The LOCK half is fixed HERE, in tools/gtm/ itself:
# `_gtm_registry_lock_path()` now returns a path under `gtm_state_dir()`
# (`~/.claude/.gtm_state/`), which the real .gitignore's whitelist-
# everything model never re-includes at all (unlike
# `knowledge/gtm_company_registry.json`, which is re-included by its
# EXACT filename only) -- so the lock file is covered regardless of name,
# with no .gitignore edit needed.
#
# The MKSTEMP STAGING FILE half remains a real, OUT-OF-SCOPE gap:
# `_atomic_write_json`'s tmp file must stay in `target.parent`
# (`knowledge/`) for `os.replace` to be a same-filesystem atomic rename --
# moving it to `.gtm_state/` would require a cross-directory rename
# instead. Closing this half needs a real repo-root `.gitignore` edit
# (widening `knowledge/gtm_company_registry.json` to
# `knowledge/gtm_company_registry.json*`), which this test module cannot
# make; it stays xfail, proven against the REAL, live ~/.claude/.gitignore
# (read-only: `git check-ignore` never writes) rather than papering over
# it with a synthetic fixture, so it stays honest about what is and isn't
# actually covered on this machine right now.
# --------------------------------------------------------------------------


def _real_claude_dir() -> Path:
    """The real runtime root -- NOT `claude_env`/`CLAUDE_DIR` overrides,
    which point at a throwaway tmp_path with no real .gitignore at all.
    This is the one place in this test module that deliberately reads the
    real ~/.claude tree, and only via a read-only `git check-ignore`."""
    import os

    override = os.environ.get("CLAUDE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".claude"


def _real_git_check_ignore(rel_path: str) -> bool:
    import subprocess

    claude_dir = _real_claude_dir()
    result = subprocess.run(
        ["git", "check-ignore", "-q", rel_path], cwd=str(claude_dir),
    )
    return result.returncode == 0


def test_gtm_registry_lock_file_is_gitignored():
    """Major finding #3, fixed: `_gtm_registry_lock_path()` now returns a
    path under `.gtm_state/` (never `knowledge/gtm_company_registry.json.lock`
    -- see that function's own docstring), which the real .gitignore's
    whitelist-everything model never re-includes at all, regardless of
    filename. A lock file that always exists after the first
    register/unregister call must never be trackable -- previously it
    lived right next to the registry it guards, covered by the
    .gitignore's exact-filename-only entry, and any crash-recovery
    inspection of the working tree would have seen it as an untracked
    file with no explanation.

    RED-check: revert `_gtm_registry_lock_path()` back to
    `gtm_registry_path().with_suffix(".json.lock")` (its pre-fix shape,
    landing the lock at `knowledge/gtm_company_registry.json.lock`) and
    this assertion fails against the real .gitignore."""
    lock_path = company._gtm_registry_lock_path()
    real_claude_dir = _real_claude_dir()
    rel_path = lock_path.relative_to(real_claude_dir) if lock_path.is_relative_to(real_claude_dir) else lock_path
    assert str(rel_path).startswith(".gtm_state" + os.sep), (
        f"_gtm_registry_lock_path() must live under .gtm_state/, got {lock_path}"
    )
    assert _real_git_check_ignore(str(rel_path)), (
        f"{rel_path} is NOT covered by ~/.claude/.gitignore -- "
        "it would be trackable in git, exposing the operator's private business paths on a crash."
    )


def test_gtm_registry_mkstemp_temp_file_is_gitignored():
    """`_atomic_write_json`'s mkstemp staging file
    (`knowledge/gtm_company_registry.json.<8 random chars>.tmp`) must stay in
    target.parent (knowledge/) for os.replace to be a same-filesystem atomic
    rename -- it cannot simply move to .gtm_state/ the way the lock file did
    (test_gtm_registry_lock_file_is_gitignored above). Fixed (major finding
    #3) by widening ~/.claude/.gitignore's exact-name-only entry to
    `knowledge/gtm_company_registry.json*`, which also covers this staging
    file.

    RED-check: revert the .gitignore entry back to the exact filename
    `knowledge/gtm_company_registry.json` (no trailing `*`) and this
    assertion fails -- the mkstemp staging file is uncovered."""
    assert _real_git_check_ignore("knowledge/gtm_company_registry.json.bloxwshh.tmp"), (
        "knowledge/gtm_company_registry.json.<random>.tmp is NOT covered by ~/.claude/.gitignore -- "
        "a crash mid-write would leave the full registry (private business paths) trackable. "
        "This is a real repo-root .gitignore edit, outside tools/gtm/'s own pathspec."
    )
