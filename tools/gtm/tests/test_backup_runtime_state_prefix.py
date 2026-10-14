"""Minor 18: runtime .gtm_state entries (tickets/<slug>/, leases/<slug>.lock)
are archived under a `_gtm_state/<slug>/` prefix, and restore refuses to
place them anywhere but an explicit --runtime-state-to directory (never
into the company home root).
"""

from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backup_state  # noqa: E402


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
def registered_home_with_runtime_state(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    gtm_dir = home / ".claude" / "gtm"
    gtm_dir.mkdir(parents=True)
    (gtm_dir / "company.json").write_text(json.dumps(_minimal_pack("acme")), encoding="utf-8")

    state_dir = gtm_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "actions.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")

    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))

    # Populate the runtime cross-company .gtm_state entries backup_set now
    # includes (tickets/<slug>/, leases/<slug>.lock).
    gtm_state_root = claude_dir / ".gtm_state"
    tickets_dir = gtm_state_root / "tickets" / "acme"
    tickets_dir.mkdir(parents=True)
    (tickets_dir / "ticket_1.json").write_text('{"ticket": 1}', encoding="utf-8")
    leases_dir = gtm_state_root / "leases"
    leases_dir.mkdir(parents=True)
    (leases_dir / "acme.lock").write_text("", encoding="utf-8")

    return {"home": home, "claude_dir": claude_dir}


def test_runtime_state_archived_under_gtm_state_prefix(tmp_path, registered_home_with_runtime_state):
    """RED-check: revert backup_company's arcname computation to the old
    bare `p.name` fallback and this fails -- the ticket dir and lease file
    would both archive as indistinguishable bare names with no prefix."""
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)
    with tarfile.open(tgz_path, "r:gz") as tar:
        names = tar.getnames()
    assert any(n.startswith("_gtm_state/acme/tickets/acme/") for n in names), names
    assert any(n.startswith("_gtm_state/acme/leases/") for n in names), names


def test_restore_refuses_runtime_state_without_explicit_flag(tmp_path, registered_home_with_runtime_state):
    """RED-check: remove the RuntimeStateRestoreRefused check in
    restore_archive and this fails -- runtime-state members would
    silently land inside --to (the company home) instead of being refused."""
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)

    restore_dir = tmp_path / "restored_home"
    with pytest.raises(backup_state.RuntimeStateRestoreRefused):
        backup_state.restore_archive(tgz_path, restore_dir)

    # Home-scoped content is still NOT restored either, since restore is
    # refused before anything is extracted (all-or-nothing, consistent
    # with blocker 10's own discipline).
    assert not (restore_dir / ".claude" / "gtm" / "state" / "actions.jsonl").exists()


def test_restore_places_runtime_state_only_under_explicit_runtime_state_to(tmp_path, registered_home_with_runtime_state):
    """#22: the `_gtm_state/<slug>/` archive prefix is STRIPPED on
    restore, so --runtime-state-to <dir> reproduces each file's ORIGINAL
    path (tickets/<slug>/..., leases/<slug>.lock) directly under <dir> --
    e.g. --runtime-state-to ~/.claude/.gtm_state restores files to their
    real ~/.claude/.gtm_state/tickets/<slug>/... locations, not nested
    under an extra _gtm_state/<slug>/ layer that never existed on disk."""
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)

    restore_home = tmp_path / "restored_home"
    restore_runtime = tmp_path / "restored_runtime_state"
    backup_state.restore_archive(tgz_path, restore_home, runtime_state_to=restore_runtime)

    # Home content restored under --to.
    assert (restore_home / ".claude" / "gtm" / "state" / "actions.jsonl").exists()

    # Runtime-state content restored DIRECTLY under --runtime-state-to, at
    # its ORIGINAL (pre-backup) path -- no _gtm_state/<slug>/ prefix layer.
    assert (restore_runtime / "tickets" / "acme" / "ticket_1.json").exists()
    assert (restore_runtime / "leases" / "acme.lock").exists()
    assert not (restore_runtime / "_gtm_state").exists()
    assert not (restore_home / "_gtm_state").exists()
    assert not (restore_home / "tickets").exists()
    assert not (restore_home / "leases").exists()


def test_cli_restore_without_runtime_state_to_reports_error(tmp_path, registered_home_with_runtime_state):
    dest_root = tmp_path / "backups_cli"
    rc = backup_state.main(["--company", "acme", "--dest-root", str(dest_root)])
    assert rc == 0
    tgz = next((dest_root / "acme").glob("*.tgz"))

    restore_dir = tmp_path / "restored_cli"
    rc = backup_state.main(["--restore", str(tgz), "--to", str(restore_dir)])
    assert rc == 1


def test_cli_restore_with_runtime_state_to_succeeds(tmp_path, registered_home_with_runtime_state):
    dest_root = tmp_path / "backups_cli2"
    rc = backup_state.main(["--company", "acme", "--dest-root", str(dest_root)])
    assert rc == 0
    tgz = next((dest_root / "acme").glob("*.tgz"))

    restore_dir = tmp_path / "restored_cli2"
    runtime_dir = tmp_path / "restored_cli2_runtime"
    rc = backup_state.main([
        "--restore", str(tgz), "--to", str(restore_dir), "--runtime-state-to", str(runtime_dir),
    ])
    assert rc == 0
    assert (restore_dir / ".claude" / "gtm" / "state" / "actions.jsonl").exists()
    assert (runtime_dir / "leases" / "acme.lock").exists()


# --------------------------------------------------------------------------
# #22: validation runs AFTER prefix-stripping, against the path that will
# actually be extracted
# --------------------------------------------------------------------------


def _make_crafted_runtime_state_tar(tmp_path: Path, slug: str, bad_suffix: str) -> Path:
    tgz_path = tmp_path / "crafted_runtime.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        info = tarfile.TarInfo(name=f"_gtm_state/{slug}/{bad_suffix}")
        info.size = 0
        tar.addfile(info, fileobj=None)
    return tgz_path


def test_validation_runs_against_the_post_rename_path_not_the_original(tmp_path):
    """#22: validation must run against the path that will ACTUALLY be
    extracted (the post-rename, prefix-stripped name), not the original
    archive-internal name. This is order-sensitive specifically for a
    SYMLINK member: its relative linkname is resolved against the
    member's OWN location, which DIFFERS before vs after the prefix is
    stripped (a deeper `_gtm_state/<slug>/tickets/x` vs the shallower
    stripped `tickets/x`) -- a relative '../../etc/evil' that stays
    INSIDE runtime_state_to when resolved from the deep pre-rename
    location can resolve OUTSIDE it once resolved from the shallower
    post-rename location.

    RED-check: validate symlink members BEFORE renaming (against the
    original deep `_gtm_state/<slug>/...` location) instead of after, and
    this test's `pytest.raises` never fires -- the same relative linkname
    validates as safe at the deep pre-rename location but is genuinely
    unsafe once extracted at the shallower post-rename location."""
    slug = "acme"
    tgz_path = tmp_path / "crafted_symlink.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        # Pre-rename name: _gtm_state/acme/a/b/c/link (3 directories deep
        # under the prefix). Post-rename (stripped) name: a/b/c/link (3
        # directories deep under runtime_state_to). The relative linkname
        # "../../../outside/evil" resolves:
        #   - from the PRE-rename depth (_gtm_state/acme/a/b/c/ -- 5 dirs
        #     deep total under whatever conceptual root the archive name
        #     implies) as still-inside-ish depending on interpretation
        #   - from the POST-rename depth (a/b/c/ -- 3 dirs deep under
        #     runtime_state_to) as OUTSIDE runtime_state_to.
        # Validating against the wrong (pre-rename) depth would compute a
        # different, safe-looking resolution and miss the real escape.
        info = tarfile.TarInfo(name=f"_gtm_state/{slug}/a/b/c/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../../outside/evil"
        tar.addfile(info)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_home, runtime_state_to=restore_runtime, slug=slug)


# --------------------------------------------------------------------------
# nit: an explicit --company slug that matches none of the archive's real
# runtime-state members must refuse, not silently land un-stripped
# --------------------------------------------------------------------------


def test_restore_refuses_when_explicit_slug_matches_no_runtime_member(tmp_path, registered_home_with_runtime_state):
    """RED-check: remove the member_slugs-mismatch check in restore_archive
    and this fails -- passing slug='wrong_company' (which matches NONE of
    the archive's actual '_gtm_state/acme/...' members) would silently
    leave every runtime-state member un-stripped, landing nested under
    '<runtime-state-to>/_gtm_state/acme/...' with no error at all."""
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    with pytest.raises(backup_state.RuntimeStateRestoreRefused) as excinfo:
        backup_state.restore_archive(
            tgz_path, restore_home, runtime_state_to=restore_runtime, slug="wrong_company",
        )
    assert "wrong_company" in str(excinfo.value)
    assert "acme" in str(excinfo.value)
    # Nothing extracted -- refused before any extraction happened.
    assert not (restore_runtime / "_gtm_state").exists()
    assert not (restore_runtime / "tickets").exists()


def test_restore_refuses_mixed_slug_archive(tmp_path):
    """RED-check: revert the mismatch check back to `member_slugs and
    effective_slug not in member_slugs` (refuse only when effective_slug
    matches NONE of the members) and this fails -- a MIXED-slug archive
    (most members are 'acme', one is 'other_company') would pass the
    check silently: the 'acme' members get correctly stripped, and the
    'other_company' member is extracted UN-STRIPPED, nested under
    '<runtime-state-to>/_gtm_state/other_company/...', with no error at
    all -- exactly the wrong-company-data shape #22's own fix exists to
    prevent, just for a partial rather than total slug mismatch."""
    tgz_path = tmp_path / "mixed_slug.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        info_a = tarfile.TarInfo(name="_gtm_state/acme/tickets/acme/ticket_1.json")
        info_a.size = 0
        tar.addfile(info_a, fileobj=None)
        info_b = tarfile.TarInfo(name="_gtm_state/other_company/tickets/other_company/ticket_9.json")
        info_b.size = 0
        tar.addfile(info_b, fileobj=None)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    with pytest.raises(backup_state.RuntimeStateRestoreRefused) as excinfo:
        backup_state.restore_archive(
            tgz_path, restore_home, runtime_state_to=restore_runtime, slug="acme",
        )
    assert "other_company" in str(excinfo.value)
    # All-or-nothing: nothing extracted, including the 'acme'-slug member
    # that WOULD have matched cleanly.
    assert not (restore_runtime / "_gtm_state").exists()
    assert not (restore_runtime / "tickets").exists()


def test_restore_refuses_mixed_slug_archive_with_auto_detected_slug_names_it_correctly(tmp_path):
    """Nit fix #10: the mixed-slug refusal fires identically whether the
    slug came from an explicit --company or was auto-detected from the
    archive's own first runtime-state member (README's own prose already
    says "whether the slug is explicit or auto-detected") -- but the
    refusal MESSAGE itself used to always say "--company <slug> does not
    match...", even when the caller never passed --company at all and the
    slug was auto-detected. Passes NO `slug=` at all here, so
    `effective_slug` is auto-detected from the archive's first member.

    RED-check: revert the message to the unconditional
    `f"--company {effective_slug!r} does not match..."` (its pre-fix
    shape) and this test's `"--company" not in` assertion fails."""
    tgz_path = tmp_path / "mixed_slug_auto.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        info_a = tarfile.TarInfo(name="_gtm_state/acme/tickets/acme/ticket_1.json")
        info_a.size = 0
        tar.addfile(info_a, fileobj=None)
        info_b = tarfile.TarInfo(name="_gtm_state/other_company/tickets/other_company/ticket_9.json")
        info_b.size = 0
        tar.addfile(info_b, fileobj=None)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    with pytest.raises(backup_state.RuntimeStateRestoreRefused) as excinfo:
        backup_state.restore_archive(
            tgz_path, restore_home, runtime_state_to=restore_runtime,
        )
    message = str(excinfo.value)
    assert "auto-detected" in message
    assert "--company" not in message
    assert "acme" in message
    assert "other_company" in message


def test_restore_succeeds_when_explicit_slug_matches_runtime_member(tmp_path, registered_home_with_runtime_state):
    """Paired recovery test: the SAME slug the archive actually carries is
    still accepted -- the mismatch check must not become an overbroad
    refusal of every explicit --company pass."""
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    backup_state.restore_archive(tgz_path, restore_home, runtime_state_to=restore_runtime, slug="acme")
    assert (restore_runtime / "tickets" / "acme" / "ticket_1.json").exists()


# --------------------------------------------------------------------------
# nit: a hardlink inside a runtime-state member is refused outright
# --------------------------------------------------------------------------


def test_restore_refuses_hardlink_runtime_state_member(tmp_path):
    """RED-check: remove the islnk() refusal in restore_archive and this
    fails -- a hardlink member's linkname is archive-root-relative (unlike
    a symlink's, which is relative to the member's own directory), so
    stripping the '_gtm_state/<slug>/' prefix from member.name WITHOUT also
    rewriting the hardlink's linkname would leave it pointing at a
    non-existent (pre-rename) path, or worse, at whatever real path happens
    to already sit at that now-differently-resolved location post-rename."""
    slug = "acme"
    tgz_path = tmp_path / "crafted_hardlink.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        target_info = tarfile.TarInfo(name=f"_gtm_state/{slug}/tickets/{slug}/ticket_1.json")
        target_info.size = 0
        tar.addfile(target_info, fileobj=None)

        link_info = tarfile.TarInfo(name=f"_gtm_state/{slug}/tickets/{slug}/ticket_1_hardlink.json")
        link_info.type = tarfile.LNKTYPE
        link_info.linkname = f"_gtm_state/{slug}/tickets/{slug}/ticket_1.json"
        tar.addfile(link_info)

    restore_home = tmp_path / "restore_home"
    restore_runtime = tmp_path / "restore_runtime"
    with pytest.raises(backup_state.UnsafeArchiveMember) as excinfo:
        backup_state.restore_archive(tgz_path, restore_home, runtime_state_to=restore_runtime, slug=slug)
    assert "hardlink" in str(excinfo.value)
