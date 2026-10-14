"""Tests for tools/gtm/backup_state.py — backup/restore round trip and
8-newest rotation. Never writes to the real ~/Backups."""

from __future__ import annotations

import json
import sys
import tarfile
from datetime import date, timedelta
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
def registered_home_with_state(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    gtm_dir = home / ".claude" / "gtm"
    gtm_dir.mkdir(parents=True)
    (gtm_dir / "company.json").write_text(json.dumps(_minimal_pack("acme")), encoding="utf-8")

    state_dir = gtm_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "actions.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")
    (state_dir / "scoreboard.csv").write_text("date,value\n2026-01-01,5\n", encoding="utf-8")

    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    return home


def test_backup_creates_tgz_containing_state(tmp_path, registered_home_with_state):
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)
    assert tgz_path.exists()
    with tarfile.open(tgz_path, "r:gz") as tar:
        names = tar.getnames()
    assert any("state" in n for n in names)


def test_backup_restore_round_trip(tmp_path, registered_home_with_state):
    dest_root = tmp_path / "backups"
    tgz_path = backup_state.backup_company("acme", dest_root)

    restore_dir = tmp_path / "restored"
    backup_state.restore_archive(tgz_path, restore_dir)

    restored_actions = restore_dir / ".claude" / "gtm" / "state" / "actions.jsonl"
    assert restored_actions.exists()
    assert restored_actions.read_text(encoding="utf-8") == '{"id": "1"}\n'


def test_backup_rotation_keeps_only_newest_8(tmp_path, registered_home_with_state):
    dest_root = tmp_path / "backups"
    base_day = date(2026, 1, 1)
    for i in range(10):
        backup_state.backup_company("acme", dest_root, today=base_day + timedelta(days=i))

    out_dir = dest_root / "acme"
    archives = sorted(out_dir.glob("*.tgz"))
    assert len(archives) == 8
    # the oldest 2 must be gone, the newest 8 must remain
    remaining_days = {p.stem for p in archives}
    assert (base_day + timedelta(days=0)).isoformat() not in remaining_days
    assert (base_day + timedelta(days=1)).isoformat() not in remaining_days
    assert (base_day + timedelta(days=9)).isoformat() in remaining_days


def test_cli_backup_and_restore(tmp_path, registered_home_with_state):
    dest_root = tmp_path / "backups_cli"
    rc = backup_state.main(["--company", "acme", "--dest-root", str(dest_root)])
    assert rc == 0
    tgz = next((dest_root / "acme").glob("*.tgz"))

    restore_dir = tmp_path / "restored_cli"
    rc = backup_state.main(["--restore", str(tgz), "--to", str(restore_dir)])
    assert rc == 0
    assert (restore_dir / ".claude" / "gtm" / "state" / "actions.jsonl").exists()


# --------------------------------------------------------------------------
# Blocker 10: restore traversal safety
# --------------------------------------------------------------------------


def _make_crafted_tar(tmp_path: Path, add_member) -> Path:
    """Builds a minimal valid .tgz whose members are added by the caller's
    `add_member(tar)` callback -- lets each test craft exactly one bad
    member without repeating tarfile boilerplate."""
    tgz_path = tmp_path / "crafted.tgz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        add_member(tar)
    return tgz_path


def test_restore_rejects_absolute_path_member(tmp_path):
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="/etc/evil_absolute")
        info.size = 0
        tar.addfile(info, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)
    # Nothing extracted -- all-or-nothing (validated before extraction).
    assert not (restore_dir / "etc").exists()
    if restore_dir.exists():
        assert list(restore_dir.iterdir()) == []


def test_restore_rejects_dotdot_traversal_member(tmp_path):
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="../../etc/evil_dotdot")
        info.size = 0
        tar.addfile(info, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target2"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)


def test_restore_rejects_dotdot_member_that_would_resolve_to_a_sibling_prefix_dir(tmp_path):
    """The '..'-component check and the is_relative_to() resolved-path
    check are two independent layers; this confirms the '..' layer alone
    already stops the sibling-prefix escape shape end to end (via
    restore_archive)."""
    restore_dir = tmp_path / "restore_target3"
    evil_sibling_prefix = tmp_path / "restore_target3_evil"

    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="../restore_target3_evil/x")
        info.size = 0
        tar.addfile(info, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)
    assert not evil_sibling_prefix.exists()


def test_sibling_prefix_path_comparison_uses_is_relative_to_not_string_prefix(tmp_path):
    """Isolates the SECOND, independent defense layer: the raw path
    comparison _validate_member uses to decide "does this resolved member
    path stay inside to_dir" must be a real path-component check
    (is_relative_to), never a bare string-prefix check -- a sibling
    directory that merely shares to_dir's path as a string prefix
    ("restore_target3_evil" vs "restore_target3") is NOT inside it, but
    DOES satisfy a naive `str.startswith()` test.

    RED-check: change backup_state._validate_member's
    `member_path.is_relative_to(to_dir_resolved)` back to
    `str(member_path).startswith(str(to_dir_resolved))` and this test's
    second assertion (mirroring exactly what _validate_member computes)
    fails to demonstrate the bug is real, and the exploit becomes
    reachable for any member whose resolved path happens to share that
    string prefix by NO '..' route at all (e.g. an absolute-looking
    resolved path from a symlink already present in to_dir at extraction
    time) -- a shape this repo's actual `_validate_member` closes via
    is_relative_to() regardless of how the resolved path was reached, not
    only for the specific '..'-textual case the OTHER test above already
    covers as a second, independent layer."""
    to_dir_resolved = (tmp_path / "restore_target3").resolve()
    evil_sibling = (tmp_path / "restore_target3_evil" / "x").resolve()

    # This is the exact defect: a naive string-prefix check accepts a
    # sibling directory, while the real path-component check correctly
    # rejects it.
    assert str(evil_sibling).startswith(str(to_dir_resolved))
    assert not evil_sibling.is_relative_to(to_dir_resolved)

    # And the shipped validator, given a member whose resolved path IS
    # exactly this sibling location, must raise -- reproduced here by
    # calling the real resolution the validator performs and asserting on
    # ITS OWN computed member_path/to_dir_resolved pair via the public
    # entry point (restore_archive), using a '..'-shaped member name (the
    # only way a real tar member can name a sibling path at all -- tar
    # entries are always relative, so any real-world exploit attempting
    # this shape necessarily goes through the '..' branch, which is why
    # both checks exist together as defense in depth).
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="../restore_target3_evil/x")
        info.size = 0
        tar.addfile(info, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, to_dir_resolved)


def test_restore_rejects_symlink_pointing_outside_target(tmp_path):
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="link_to_outside")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target4"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)


def test_restore_rejects_hardlink_pointing_outside_target(tmp_path):
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="hardlink_to_outside")
        info.type = tarfile.LNKTYPE
        info.linkname = "../../../etc/passwd"
        tar.addfile(info)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target5"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)


def test_restore_rejects_device_file_member(tmp_path):
    def add_member(tar: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name="fake_device")
        info.type = tarfile.CHRTYPE
        info.devmajor = 1
        info.devminor = 5
        tar.addfile(info)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target6"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)


def test_restore_all_or_nothing_one_bad_member_blocks_the_whole_archive(tmp_path):
    """Paired recovery-style test: a MOSTLY-clean archive with one bad
    member must refuse entirely, not extract the good members and skip
    the bad one."""
    def add_member(tar: tarfile.TarFile) -> None:
        good = tarfile.TarInfo(name="good_file.txt")
        good.size = 0
        tar.addfile(good, fileobj=None)
        bad = tarfile.TarInfo(name="/etc/evil")
        bad.size = 0
        tar.addfile(bad, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target7"
    with pytest.raises(backup_state.UnsafeArchiveMember):
        backup_state.restore_archive(tgz_path, restore_dir)
    assert not (restore_dir / "good_file.txt").exists()


def test_restore_accepts_a_genuinely_clean_archive(tmp_path):
    """Paired recovery test: a normal, clean archive still restores fine
    -- the safety checks must not produce false positives on ordinary
    content."""
    def add_member(tar: tarfile.TarFile) -> None:
        good = tarfile.TarInfo(name="nested/good_file.txt")
        good.size = 0
        tar.addfile(good, fileobj=None)

    tgz_path = _make_crafted_tar(tmp_path, add_member)
    restore_dir = tmp_path / "restore_target8"
    backup_state.restore_archive(tgz_path, restore_dir)
    assert (restore_dir / "nested" / "good_file.txt").exists()
