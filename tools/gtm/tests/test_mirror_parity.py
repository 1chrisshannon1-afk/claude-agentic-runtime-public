"""Parity test: the runtime's generalized activity_log.py mirror render
(HTML + MD) must reproduce the ORIGINAL Brightline log_action.py's mirror
render byte-for-byte, except the "Last updated" line (which legitimately
changes with wall-clock time / pack timezone).

Imports the original module READ-ONLY (never modified, never executed
against its own real files) and calls its pure render functions directly
with fixture data -- render_owner_markdown(log_records) and
render_owner_html(log_records, inventories) take their data as parameters
and never touch LOG_JSONL/FEATURE_INVENTORY_DIR/MIRROR_DIR globals, so this
test never reads or writes anything under the real
~/Desktop/Brightline/Legacy_Workdir_2026_09_25/ tree.

If the real Brightline checkout is not present on this machine (e.g. CI, a
different machine), the test skips itself rather than failing spuriously.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402

# The original script lives in a private company folder on the operator's
# machine, so its path is never written into this (published) runtime code:
# set GTM_PARITY_ORIGINAL to the original log_action.py to run this test.
_ORIGINAL_ENV = os.environ.get("GTM_PARITY_ORIGINAL", "")
_ORIGINAL_PATH = Path(_ORIGINAL_ENV).expanduser() if _ORIGINAL_ENV else None


def _load_original():
    """Imports the Brightline original as a standalone module, read-only --
    never via sys.path insertion into this package (its module name would
    collide with nothing here, but loading it explicitly by path keeps this
    test from ever accidentally shadowing/being shadowed by it).

    Registers the module in sys.modules BEFORE exec_module runs: the
    original uses `from __future__ import annotations` (string
    annotations) on its @dataclass classes, and dataclasses' own
    annotation resolution looks the module up via
    `sys.modules.get(cls.__module__)` -- a module loaded via
    module_from_spec is not yet in sys.modules until this is done
    explicitly, so without it @dataclass raises AttributeError on a
    None module lookup. This is a read-only import mechanic, not a
    modification of the original file."""
    module_name = "_ts_log_action_original"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, _ORIGINAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[module_name]
        raise
    return module


def _original_title(original) -> str:
    """The original's hardcoded page title, read from its own markdown
    render (first line "# <title>"), so this published test never spells a
    company name. Our pack sets mirror_title to exactly this value."""
    first = original.render_owner_markdown([]).splitlines()[0]
    assert first.startswith("# ")
    return first[2:]


pytestmark = pytest.mark.skipif(
    _ORIGINAL_PATH is None or not _ORIGINAL_PATH.exists(),
    reason=f"Brightline original not present on this machine: {_ORIGINAL_PATH}",
)


# A fixed set of fixture log records covering the fields the render
# functions branch on: multiple systems/actions/statuses, present and
# absent before/after/undo/notes/evidence/account, so a real formatting
# divergence has somewhere to show up.
_FIXTURE_RECORDS = [
    {
        "id": "A0001", "ts": "2026-01-05T09:15:00-06:00", "source": "manual",
        "system": "google_ads", "action": "update", "object": "raised budget",
        "before": "$50/day", "after": "$75/day", "why": "scaling a winning campaign",
        "actor": "agent:gtm-operator:abc123", "evidence": ["screenshot1.png", "screenshot2.png"],
        "undo": "revert to $50/day", "approval": "R9 standing", "status": "done",
        "account": "100-200-3000", "notes": "confirmed via day-after verify",
    },
    {
        "id": "A0002", "ts": "2026-01-04T14:00:00-06:00", "source": "manual",
        "system": "gbp_remodeling", "action": "publish", "object": "posted a project photo",
        "before": None, "after": None, "why": "weekly content cadence",
        "actor": "owner", "evidence": [], "undo": "delete the post",
        "approval": "C1 standing", "status": "done", "account": None, "notes": None,
    },
    {
        "id": "A0003", "ts": "2026-01-03T08:30:00-06:00", "source": "manual",
        "system": "facebook_remodeling", "action": "read_baseline", "object": "captured current follower count",
        "before": None, "after": "1,204 followers", "why": "monthly baseline",
        "actor": "agent:gtm-analyst:def456", "evidence": [], "undo": None,
        "approval": "n/a", "status": "done", "account": None, "notes": None,
    },
]

_FIXTURE_INVENTORIES = {
    "gbp": [
        {"feature": "Q&A", "status": "unused", "log_ids": "", "notes": "not yet tried", "source": "GBP help center"},
        {"feature": "Posts", "status": "used", "log_ids": "A0002", "notes": "", "source": ""},
    ],
    "facebook": [
        {"feature": "Events", "status": "planned", "log_ids": "", "notes": "consider for open house", "source": ""},
    ],
}

_LAST_UPDATED_LINE_RE = re.compile(r"^Last updated:.*$", re.MULTILINE)
_LAST_UPDATED_HTML_RE = re.compile(r"Last updated: [^&]*&middot;")


def _strip_last_updated_md(text: str) -> str:
    return _LAST_UPDATED_LINE_RE.sub("Last updated: <REDACTED>", text)


def _strip_last_updated_html(text: str) -> str:
    return _LAST_UPDATED_HTML_RE.sub("Last updated: <REDACTED> &middot;", text)


def test_markdown_mirror_entries_match_original_byte_for_byte_except_timestamp():
    """RED-check: change any field-formatting line in
    activity_log.render_owner_markdown (e.g. drop the 'before -> after'
    line, or reorder a field) and this test fails -- it compares the
    ENTIRE entries section, not just a substring."""
    original = _load_original()

    class _FakePaths:
        slug = "brightline"
        log_md = Path("/fixture/ACTIVITY_LOG.md")
        timezone = "America/Denver"
        mirror_title = _original_title(original)

    ours = activity_log.render_owner_markdown(_FIXTURE_RECORDS, _FakePaths())
    theirs = original.render_owner_markdown(_FIXTURE_RECORDS)

    ours_norm = _strip_last_updated_md(ours)
    theirs_norm = _strip_last_updated_md(theirs)

    # Blocker 8: the header line ("# Brightline Activity Log") now MUST
    # match exactly when mirror_title is set to the original's title --
    # no longer stripped/excluded from comparison. RED-check: revert
    # render_owner_markdown's header line to `f"# {paths.slug} Activity
    # Log"` (lowercase slug) and this line-1 assertion fails.
    assert ours_norm.splitlines()[0] == f"# {_original_title(original)}"
    assert theirs_norm.splitlines()[0] == ours_norm.splitlines()[0]

    # The intro paragraph (which file this mirrors FROM) still legitimately
    # differs -- ours cites paths.log_md, theirs a hardcoded relative path
    # -- so only the entries section (from the first "## A0001" heading
    # onward) is compared beyond the header line.
    def entries_only(text: str) -> str:
        idx = text.index("## A0001")
        return text[idx:]

    assert entries_only(ours_norm) == entries_only(theirs_norm)


def test_html_mirror_entries_table_matches_original_byte_for_byte_except_timestamp():
    """RED-check: change any <td> in activity_log.render_owner_html's entry
    row (e.g. drop the status-class CSS hook, or the evidence join
    separator) and this test fails."""
    original = _load_original()

    class _FakePaths:
        slug = "brightline"
        log_jsonl = Path("/fixture/ACTIVITY_LOG.jsonl")
        timezone = "America/Denver"
        mirror_title = _original_title(original)

    ours = activity_log.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES, _FakePaths())
    theirs = original.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES)

    ours_norm = _strip_last_updated_html(ours)
    theirs_norm = _strip_last_updated_html(theirs)

    # Blocker 8: <title> and <h1> must equal the original's "Brightline
    # Activity Log" exactly when mirror_title is set. RED-check: revert
    # render_owner_html's company_title to html_escape(paths.slug) (the
    # bare lowercase slug) and these two assertions fail.
    title = _original_title(original)
    assert f"<title>{title}</title>" in ours_norm
    assert f"<h1>{title}</h1>" in ours_norm
    assert f"<title>{title}</title>" in theirs_norm
    assert f"<h1>{title}</h1>" in theirs_norm

    def rows_block(text: str) -> str:
        start = text.index('<table id="entries-table">')
        end = text.index("<h2>Features not yet used</h2>")
        return text[start:end]

    assert rows_block(ours_norm) == rows_block(theirs_norm)


def test_html_mirror_feature_section_matches_original_byte_for_byte():
    """RED-check: change the feature-section table column order/labels in
    render_owner_html and this test fails -- the 'Features not yet used'
    section (built from feature_inventory/*.csv) must render identically."""
    original = _load_original()

    class _FakePaths:
        slug = "brightline"
        log_jsonl = Path("/fixture/ACTIVITY_LOG.jsonl")
        timezone = "America/Denver"
        mirror_title = _original_title(original)

    ours = activity_log.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES, _FakePaths())
    theirs = original.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES)

    def features_block(text: str) -> str:
        start = text.index("<h2>Features not yet used</h2>")
        end = text.index("<footer>")
        return text[start:end]

    assert features_block(ours) == features_block(theirs)


def test_html_mirror_actor_table_matches_original_byte_for_byte():
    original = _load_original()

    class _FakePaths:
        slug = "brightline"
        log_jsonl = Path("/fixture/ACTIVITY_LOG.jsonl")
        timezone = "America/Denver"
        mirror_title = _original_title(original)

    ours = activity_log.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES, _FakePaths())
    theirs = original.render_owner_html(_FIXTURE_RECORDS, _FIXTURE_INVENTORIES)

    def actor_block(text: str) -> str:
        start = text.index('<table class="actor-table">')
        end = text.index("<h2>Entries (newest first)</h2>")
        return text[start:end]

    assert actor_block(ours) == actor_block(theirs)


def test_full_render_all_writes_both_html_and_md_to_mirror_dir(tmp_path, monkeypatch):
    """End-to-end: activity_log.cmd_add on a fresh company with mirror_dir
    set writes both files, and the HTML file contains the entries table
    (proving render_mirrors -> render_owner_html is actually wired, not
    just unit-tested in isolation)."""
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    mirror_dir = tmp_path / "mirror_out"

    pack = {
        "schema_version": 1, "slug": "brightline", "legal_name": "Brightline", "display_names": ["Brightline"],
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
        "ai_content_policy": {"mode": "disclose_never_strip", "disclosure_caption_line": "AI-generated"},
        "autonomy": {"level": "shadow", "standing_approvals": []},
        "spend": {"currency": "USD", "monthly_cap_total": 1450, "cap_ruling_ref": "C4"},
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
        "mirror_dir": str(mirror_dir),
        "mirror_basename": "Brightline_Activity_Log",
    }
    import json
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(pack), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)

    from argparse import Namespace
    activity_log.cmd_add(Namespace(
        company="brightline", system="google_ads", action="update", object="raised budget",
        before="$50/day", after="$75/day", why="scaling", actor="gtm-operator:ac06afdc5dc9de0f3",
        evidence=[], undo="revert", approval="R9", status="done", account=None, ts=None, notes=None,
    ))

    html_path = mirror_dir / "Brightline_Activity_Log.html"
    md_path = mirror_dir / "Brightline_Activity_Log.md"
    assert html_path.exists()
    assert md_path.exists()
    assert "<table id=\"entries-table\">" in html_path.read_text(encoding="utf-8")
    assert "raised budget" in html_path.read_text(encoding="utf-8")
