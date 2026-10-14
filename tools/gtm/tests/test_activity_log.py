"""Tests for tools/gtm/activity_log.py — the generalized, company-parametric
log_action.py. Ports the intent of Brightline's original test_activity_log.py
plus the new hash-chain and agent-actor-audit behavior (plan §11.2/§11.3).
Every test uses a tmp CLAUDE_DIR + registry + pack; never touches the real
~/.claude or ~/Desktop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402


def _minimal_pack(slug: str, mirror_dir: str | None = None) -> dict:
    pack = {
        "schema_version": 1, "slug": slug, "legal_name": slug, "display_names": [slug],
        "business_model": "local_service", "brands": [],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": ["youtube_shorts"], "channels_out_of_scope": []},
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
    if mirror_dir:
        pack["mirror_dir"] = mirror_dir
    return pack


@pytest.fixture()
def registered_home(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    (home / ".claude" / "gtm").mkdir(parents=True)
    pack = _minimal_pack("acme")
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    return home


def _add_args(**kwargs):
    from argparse import Namespace
    defaults = dict(
        company="acme", system="google_ads", action="update", object="thing",
        before=None, after=None, why="testing", actor="gtm-operator:ac06afdc5dc9de0f3",
        evidence=[], undo="revert it", approval="R9", status="done", account=None,
        ts=None, notes=None,
    )
    defaults.update(kwargs)
    return Namespace(**defaults)


# --------------------------------------------------------------------------
# add / validation (ported Brightline intent)
# --------------------------------------------------------------------------


def test_add_requires_undo_unless_action_is_undo_optional(registered_home):
    args = _add_args(action="update", undo=None)
    rc = activity_log.cmd_add(args)
    assert rc == 2  # missing --undo for a non-undo-optional action


def test_add_allows_missing_undo_for_read_baseline(registered_home):
    args = _add_args(action="read_baseline", undo=None)
    rc = activity_log.cmd_add(args)
    assert rc == 0


def test_add_rejects_unknown_system(registered_home):
    args = _add_args(system="not_a_real_system")
    rc = activity_log.cmd_add(args)
    assert rc == 2


def test_add_accepts_channel_in_scope_system(registered_home):
    """systems = pack.scope.channels_in_scope ∪ base set (plan §11.2)."""
    args = _add_args(system="youtube_shorts")
    rc = activity_log.cmd_add(args)
    assert rc == 0


def test_add_redacts_secret_shaped_object_text(registered_home):
    args = _add_args(object="password: sekrit123 in the field")
    activity_log.cmd_add(args)
    paths = activity_log.resolve_paths("acme")
    records, _ = activity_log.read_jsonl(paths.log_jsonl)
    assert "sekrit123" not in json.dumps(records)
    assert "<redacted>" in json.dumps(records)


def test_add_assigns_sequential_ids(registered_home):
    activity_log.cmd_add(_add_args(object="first"))
    activity_log.cmd_add(_add_args(object="second"))
    paths = activity_log.resolve_paths("acme")
    records, _ = activity_log.read_jsonl(paths.log_jsonl)
    ids = sorted(r["id"] for r in records)
    assert ids == ["A0001", "A0002"]


# --------------------------------------------------------------------------
# hash chain
# --------------------------------------------------------------------------


def test_check_passes_after_normal_appends(registered_home):
    activity_log.cmd_add(_add_args(object="one"))
    activity_log.cmd_add(_add_args(object="two"))
    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0


def test_check_fails_when_a_line_is_tampered(registered_home):
    """RED-check: this is the falsifiability test for the hash chain itself
    -- if prev_hash were never written/verified, tampering a byte would
    never be detected and this test would fail to fail."""
    activity_log.cmd_add(_add_args(object="one"))
    activity_log.cmd_add(_add_args(object="two"))
    paths = activity_log.resolve_paths("acme")
    lines = paths.log_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    tampered = json.loads(lines[0])
    tampered["object"] = "TAMPERED"
    lines[0] = json.dumps(tampered, sort_keys=True)
    paths.log_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc != 0


def test_check_accepts_legacy_unchained_prefix(registered_home):
    """A migrated Brightline log has real lines with no prev_hash key at
    all. Those must be accepted as an unchained prefix, and new appends
    after them must chain starting from the last legacy line."""
    paths = activity_log.resolve_paths("acme")
    paths.log_jsonl.parent.mkdir(parents=True, exist_ok=True)
    legacy_entry = {
        "id": "A0001", "ts": "2026-01-01T00:00:00", "source": "manual",
        "system": "google_ads", "action": "update", "object": "legacy row",
        "before": None, "after": None, "why": "historical", "actor": "agent:legacy",
        "evidence": [], "undo": "n/a", "approval": "n/a", "status": "done",
        "account": None, "notes": None,
    }
    paths.log_jsonl.write_text(json.dumps(legacy_entry, sort_keys=True) + "\n", encoding="utf-8")

    activity_log.cmd_add(_add_args(object="new chained row"))

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0

    lines = paths.log_jsonl.read_text(encoding="utf-8").splitlines()
    assert "prev_hash" not in lines[0]
    second = json.loads(lines[1])
    assert second["prev_hash"] == activity_log._sha256_line(lines[0])


def test_check_fails_when_a_chained_line_loses_its_prev_hash(registered_home):
    """Once the chain has started, a later line missing prev_hash entirely
    (not just a wrong value) must also be detected -- this exercises the
    'chain had started but this line has none' branch distinctly from a
    tampered-value mismatch."""
    activity_log.cmd_add(_add_args(object="one"))
    activity_log.cmd_add(_add_args(object="two"))
    paths = activity_log.resolve_paths("acme")
    lines = paths.log_jsonl.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    del second["prev_hash"]
    lines[1] = json.dumps(second, sort_keys=True)
    paths.log_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc != 0


def test_check_on_never_initialized_home_creates_no_lock_directory(registered_home):
    """Nit fix: `check` is read-only verification; it must never CREATE
    `.claude/gtm/state/activity_log/` (or the lock file inside it) as a
    side effect of checking a home that has never logged anything at all --
    that directory's mere existence would misleadingly suggest the company
    has activity-log history when it has none.

    RED-check: revert cmd_check to always take the lock unconditionally
    (drop the `if not paths.lock_file.parent.exists()` early return) and
    this fails -- the activity_log directory (and its lock file) get
    created by LockedFile.__enter__'s own mkdir+touch, purely from running
    `check` against a home with nothing on disk yet."""
    paths = activity_log.resolve_paths("acme")
    assert not paths.lock_file.parent.exists(), "test setup: activity_log dir must not exist yet"

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0
    assert not paths.lock_file.parent.exists(), (
        "cmd_check must not create the activity_log directory when nothing has ever been logged"
    )


def test_check_still_takes_the_lock_once_the_trail_exists(registered_home):
    """Recovery pair: once the activity-log directory genuinely exists
    (real history on disk), `check` still takes the lock as before -- the
    skip above applies ONLY to the never-initialized case, never as a
    general bypass of the concurrency guard #2 exists for."""
    activity_log.cmd_add(_add_args(object="one"))
    paths = activity_log.resolve_paths("acme")
    assert paths.lock_file.parent.exists()

    from argparse import Namespace
    rc = activity_log.cmd_check(Namespace(company="acme"))
    assert rc == 0
    assert paths.lock_file.exists()


# --------------------------------------------------------------------------
# audit: owner-actor rule (§11.3)
# --------------------------------------------------------------------------


def _write_trail_record(paths, **overrides):
    record = {
        "tool_use_id": "tu_1", "ts": "2026-01-01T10:00:00-06:00", "session_id": "sess_1",
        "agent_id": "abc", "actor_label": "agent:abc", "tool": "mcp__playwright-gtm__browser_click",
        "transcript": "t.jsonl", "url": "https://ads.google.com/x", "system": "google_ads",
        "mutating": True, "detail": {}, "result_excerpt": "",
    }
    record.update(overrides)
    activity_log._append_chained(paths.trail_jsonl, record)


def test_audit_owner_entry_never_explains_a_mutating_cluster(registered_home):
    """RED-check: remove the is_agent_actor() filter in cmd_audit's
    manual_by_system build and this test goes green wrongly (an owner entry
    would incorrectly explain the cluster)."""
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_1", ts="2026-01-01T10:00:00-06:00")

    # An "owner" actor entry at the same time, on the same system -- must
    # NOT explain the cluster.
    activity_log.cmd_add(_add_args(
        object="owner did something", actor="owner", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1  # unexplained


def test_audit_agent_entry_explains_a_mutating_cluster(registered_home):
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_2", ts="2026-01-01T10:00:00-06:00")

    activity_log.cmd_add(_add_args(
        object="agent explained it", actor="gtm-operator:ac06afdc5dc9de0f3", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 0  # explained


def test_audit_outside_actor_never_explains(registered_home):
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_3", ts="2026-01-01T10:00:00-06:00")

    activity_log.cmd_add(_add_args(
        object="outside actor did it", actor="outside:vendor", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1


def test_is_agent_actor_real_brightline_shapes(registered_home):
    """Major 5: is_agent_actor must default to NON-agent and only admit
    known agent shapes. RED-check: revert to the old
    'default True, exclude only owner/outside:' version and this fails --
    both of these are REAL free-text actor values found in the Brightline
    ACTIVITY_LOG.jsonl, and neither is a known agent shape."""
    assert activity_log.is_agent_actor("owner (via main session)") is False
    assert activity_log.is_agent_actor("unknown (backfill)") is False
    # A few more real Brightline free-text specialist actors -- none of
    # these are agent-id-shaped or main-session-shaped, so all must be
    # non-agent under the new rule (the OLD rule wrongly counted them).
    assert activity_log.is_agent_actor("brand-architect") is False
    assert activity_log.is_agent_actor("implement agent") is False
    # Known agent shapes that MUST still count as agent.
    assert activity_log.is_agent_actor("main-session") is True
    assert activity_log.is_agent_actor("main-session (executing paid-acquisition-strategist ruling)") is True
    assert activity_log.is_agent_actor("agent") is True
    assert activity_log.is_agent_actor("gtm-operator:ac06afdc5dc9de0f3") is True


def test_audit_brightline_owner_via_main_session_shape_never_explains(registered_home):
    """The exact real Brightline free-text shape "owner (via main session)"
    must never explain a mutating cluster -- it starts with neither
    'main-session' nor a seat:agent_id pattern; it happens to CONTAIN
    "main session" as a substring, which is exactly the kind of loose match
    a naive fix could wrongly accept. RED-check: change the `actor.startswith`
    checks to `in`/substring checks and this goes green wrongly."""
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_4", ts="2026-01-01T10:00:00-06:00")

    activity_log.cmd_add(_add_args(
        object="owner via main session did it", actor="owner (via main session)",
        ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1  # unexplained


def test_audit_brightline_unknown_backfill_shape_never_explains(registered_home):
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_5", ts="2026-01-01T10:00:00-06:00")

    activity_log.cmd_add(_add_args(
        object="backfilled row", actor="unknown (backfill)", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1  # unexplained


def test_audit_reports_offserver_records(registered_home, capsys):
    """Finding 12: audit must report gtm-offserver rows (a mutating call
    on a non-playwright-gtm server to an identity host, flagged by
    harvest_tool_trail.py) unconditionally, even if the same cluster IS
    otherwise explained by a manual entry -- offserver is about HOW the
    action ran (outside the governed server), not whether someone later
    logged a reason. RED-check: remove the offserver_records block in
    cmd_audit and this test's non-zero-exit + output-substring assertions
    both fail even though the manual entry below explains the cluster."""
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(
        paths, tool_use_id="tu_offserver_1", ts="2026-01-01T10:00:00-06:00",
        server="playwright-adhoc", offserver=True,
    )
    # Explain the cluster anyway -- offserver reporting must still fire.
    activity_log.cmd_add(_add_args(
        object="explained", actor="gtm-operator:ac06afdc5dc9de0f3", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 1
    out = capsys.readouterr().out
    assert "gtm-offserver" in out
    assert "tu_offserver_1" in out


def test_audit_does_not_report_offserver_when_none_flagged(registered_home, capsys):
    """Paired recovery test for the rule above: a normal (non-offserver)
    explained cluster stays clean -- offserver reporting must not fire on
    ordinary records."""
    paths = activity_log.resolve_paths("acme")
    paths.trail_jsonl.parent.mkdir(parents=True, exist_ok=True)
    _write_trail_record(paths, tool_use_id="tu_normal_1", ts="2026-01-01T10:00:00-06:00")
    activity_log.cmd_add(_add_args(
        object="explained", actor="gtm-operator:ac06afdc5dc9de0f3", ts="2026-01-01T10:05:00-06:00",
    ))

    from argparse import Namespace
    rc = activity_log.cmd_audit(Namespace(company="acme", days=365, since="2026-01-01T00:00:00-06:00", include_local=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "gtm-offserver" not in out


# --------------------------------------------------------------------------
# mirrors: written only when the pack sets mirror_dir
# --------------------------------------------------------------------------


def test_mirror_not_written_when_pack_has_no_mirror_dir(registered_home):
    activity_log.cmd_add(_add_args(object="one"))
    paths = activity_log.resolve_paths("acme")
    assert paths.mirror_dir is None


def test_mirror_written_when_pack_sets_mirror_dir(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    (home / ".claude" / "gtm").mkdir(parents=True)
    mirror_dir = tmp_path / "mirror_out"
    pack = _minimal_pack("acme", mirror_dir=str(mirror_dir))
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    activity_log.cmd_add(_add_args(object="one"))
    # default mirror_basename = titlecased legal_name + "_Activity_Log"
    # ("acme" -> "Acme_Activity_Log") -- both .md AND .html must be written.
    assert (mirror_dir / "Acme_Activity_Log.md").exists()
    assert (mirror_dir / "Acme_Activity_Log.html").exists()
    html_text = (mirror_dir / "Acme_Activity_Log.html").read_text(encoding="utf-8")
    assert "<title>acme Activity Log</title>" in html_text
    assert "one" in html_text  # the entry's object text made it into the table


def test_mirror_title_uses_display_names_not_legal_name_or_slug(tmp_path, monkeypatch):
    """Blocker 8: mirror title must use display_names[0], falling back to
    legal_name, NEVER the lowercase slug. RED-check: change
    _default_mirror_title to return f"{slug} Activity Log" (the old
    behavior) and this fails -- legal_name and slug are both deliberately
    set to something OTHER than display_names[0] here so any of the three
    wrong fallbacks would produce a different, distinguishable title."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_ts"
    (home / ".claude" / "gtm").mkdir(parents=True)
    mirror_dir = tmp_path / "mirror_out"
    pack = _minimal_pack("brightline_internal_slug", mirror_dir=str(mirror_dir))
    pack["legal_name"] = "Brightline Holdings LLC"
    pack["display_names"] = ["Brightline Remodeling", "Brightline Restoration"]
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline_internal_slug": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    from argparse import Namespace
    activity_log.cmd_add(Namespace(
        company="brightline_internal_slug", system="google_ads", action="update", object="x",
        before=None, after=None, why="y", actor="main-session", evidence=[], undo="z",
        approval="a", status="done", account=None, ts=None, notes=None,
    ))
    paths = activity_log.resolve_paths("brightline_internal_slug")
    html_text = (mirror_dir / f"{paths.mirror_basename}.html").read_text(encoding="utf-8")
    assert "<title>Brightline Remodeling Activity Log</title>" in html_text
    assert "Brightline Holdings LLC" not in html_text.split("<title>")[1].split("</title>")[0]
    assert "brightline_internal_slug" not in html_text.split("<h1>")[1].split("</h1>")[0]


def test_mirror_title_override_matches_brightline_exact_pre_migration_title(tmp_path, monkeypatch):
    """A pack can pin mirror_title exactly, for the Brightline migration's
    real requirement: the operator's existing file's title must stay
    literally "Brightline Activity Log", not "Brightline Remodeling Activity
    Log" (its display_names[0])."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_ts2"
    (home / ".claude" / "gtm").mkdir(parents=True)
    mirror_dir = tmp_path / "mirror_out2"
    pack = _minimal_pack("brightline", mirror_dir=str(mirror_dir))
    pack["display_names"] = ["Brightline Remodeling", "Brightline Restoration"]
    pack["mirror_title"] = "Brightline Activity Log"
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    activity_log.cmd_add(_add_args(company="brightline", object="one"))
    paths = activity_log.resolve_paths("brightline")
    html_text = (mirror_dir / f"{paths.mirror_basename}.html").read_text(encoding="utf-8")
    assert "<title>Brightline Activity Log</title>" in html_text


def test_mirror_basename_override_matches_brightline_convention(tmp_path, monkeypatch):
    """RED-check: remove the `pack.get("mirror_basename") or ...` fallback
    in resolve_paths() (make it always use the default) and this fails --
    it exists specifically so a pack can pin the exact pre-existing
    filename the operator already uses (Brightline_Activity_Log)."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    mirror_dir = tmp_path / "mirror_out"
    pack = _minimal_pack("brightline", mirror_dir=str(mirror_dir))
    pack["mirror_basename"] = "Brightline_Activity_Log"
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    activity_log.cmd_add(_add_args(company="brightline", object="one"))
    assert (mirror_dir / "Brightline_Activity_Log.md").exists()
    assert (mirror_dir / "Brightline_Activity_Log.html").exists()


def test_mirror_write_failure_warns_but_never_fails_the_add(tmp_path, monkeypatch, capsys):
    """The rule from the original: a mirror-write failure warns to stderr
    but the logging operation itself (cmd_add) must still return 0.
    RED-check: remove render_all()'s try/except around render_mirrors() and
    this test's rc==0 assertion fails once mirror_dir is made unwritable."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_acme"
    (home / ".claude" / "gtm").mkdir(parents=True)
    # mirror_dir points at a path that can never be created: a FILE (not a
    # directory) sits where the mirror dir needs to be, so mkdir(parents=True)
    # raises FileExistsError/NotADirectoryError inside render_mirrors().
    blocking_file = tmp_path / "blocked_mirror_target"
    blocking_file.write_text("not a directory", encoding="utf-8")
    pack = _minimal_pack("acme", mirror_dir=str(blocking_file / "nested"))
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"acme": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    rc = activity_log.cmd_add(_add_args(object="one"))
    assert rc == 0
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
