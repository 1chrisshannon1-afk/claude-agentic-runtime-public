"""Major finding (#21-regression): `_flush_locked` must never rebuild
ANOTHER company's sidecar without holding that trail's own lock. The prior
design took only `target`'s lock, then called `load_existing_ids` over
every trail unconditionally -- including one whose sidecar looked missing
or drifted, which `load_existing_ids` would then REBUILD via a full scan +
_rebuild_ids_sidecar, with no lock held on that trail at all. If a peer
process appends a new record to that trail between the scan and the
rebuild's own _trail_stats() call, the rebuilt sidecar's header matches
the trail's (now newer, post-peer-append) on-disk stats while its id set
is missing the id the peer just added -- a sidecar that LOOKS
non-drifted (header matches) while actually being wrong. The next harvest
re-appends that id as a duplicate, and `check`'s own drift detector can't
see the problem, because the header genuinely matches.

Deterministic reproduction (no real threads/timing): monkeypatch
`_scan_ids_from_jsonl` (the full-file fallback scan `load_existing_ids`
calls when a sidecar is missing/drifted) so that, for the OTHER company's
trail specifically, a peer's append to that trail's actual JSONL happens
*between* the scan returning and the rebuild computing the trail's stats
-- exactly the interleaving the finding describes.
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
def two_companies(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home_a = tmp_path / "home_acme"
    home_b = tmp_path / "home_beta"
    for home, slug in ((home_a, "acme"), (home_b, "beta")):
        (home / ".claude" / "gtm").mkdir(parents=True)
        (home / ".claude" / "gtm" / "company.json").write_text(
            json.dumps(_minimal_pack(slug)), encoding="utf-8"
        )
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({
            "schema_version": 1,
            "repos": {"acme": {"root": str(home_a)}, "beta": {"root": str(home_b)}},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    return {"acme": home_a, "beta": home_b}


def _trail_record(tid: str, ts: str) -> dict:
    return {
        "tool_use_id": tid, "ts": ts, "session_id": "sess_1",
        "tool": "mcp__playwright-gtm__browser_click", "system": "google_ads",
    }


def test_flush_locked_never_trusts_an_unlocked_rebuild_racing_a_peer_append(two_companies, monkeypatch):
    """RED-check: revert `_flush_locked` to take only `target`'s lock (and
    `load_existing_ids` to always rebuild unconditionally, with no
    `locked_paths` gating) and this test fails -- beta's sidecar ends up
    with a header that matches beta's trail post-peer-append stats while
    its id set is missing the id the peer just appended, i.e. a sidecar
    that looks clean but is wrong.

    The peer here is a REAL LockedFile user (activity_log.py's own lock
    primitive), attempted with a NON-BLOCKING flock from a separate
    process, exactly like a genuine concurrent `activity_log.py add` or a
    second harvest run would be. In the OLD design, beta's lock is never
    held during `_flush_locked`'s (unconditional) load_existing_ids call,
    so this peer's non-blocking lock attempt succeeds and it appends
    mid-scan, corrupting the rebuilt sidecar. In the FIXED design, beta's
    lock IS held for the whole flush, so the peer's non-blocking attempt
    fails outright (proving the two can never interleave) and the peer's
    append is deferred until after the flush releases the lock -- at
    which point beta's trail correctly shows as drifted again, never
    falsely "clean but wrong"."""
    paths_acme = activity_log.resolve_paths("acme")
    paths_beta = activity_log.resolve_paths("beta")

    # beta already has one real record on disk, with NO sidecar yet
    # (forces load_existing_ids down the scan+rebuild path for beta).
    htt._append_chained_trail(paths_beta.trail_jsonl, _trail_record("tu_beta_old", "2026-01-01T00:00:00"))
    sidecar_beta = htt._ids_sidecar_path(paths_beta.trail_jsonl)
    assert sidecar_beta.exists()
    sidecar_beta.unlink()  # simulate "missing sidecar" -- forces a rebuild

    import subprocess

    peer_record_line = json.dumps(dict(_trail_record("tu_beta_peer", "2026-01-01T00:00:01"), prev_hash=None))
    peer_script = f'''
import fcntl, sys
lock_path = {str(htt._lock_path_for_trail(paths_beta.trail_jsonl))!r}
trail_path = {str(paths_beta.trail_jsonl)!r}
fh = open(lock_path, "r+")
try:
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("BLOCKED")
    sys.exit(0)
try:
    with open(trail_path, "a", encoding="utf-8") as tf:
        tf.write({peer_record_line!r} + "\\n")
    print("APPENDED")
finally:
    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
'''

    real_scan = htt._scan_ids_from_jsonl
    peer_results: list[str] = []

    def scanning_with_peer_race(path):
        result = real_scan(path)
        if path.resolve() == paths_beta.trail_jsonl.resolve():
            # Fire the real peer process exactly at the point the OLD
            # design's unlocked rebuild would be most exposed -- right
            # after the scan, before _rebuild_ids_sidecar's own
            # _trail_stats() call.
            proc = subprocess.run([sys.executable, "-c", peer_script], capture_output=True, text=True)
            peer_results.append(proc.stdout.strip())
        return result

    monkeypatch.setattr(htt, "_scan_ids_from_jsonl", scanning_with_peer_race)

    all_trail_paths = [paths_acme.trail_jsonl, paths_beta.trail_jsonl]
    candidates = [dict(_trail_record("tu_acme_new", "2026-01-01T00:00:02"), tool_use_id="tu_acme_new")]
    appended = htt._flush_locked(paths_acme.trail_jsonl, candidates, all_trail_paths)
    assert appended == 1
    assert peer_results == ["BLOCKED"], (
        f"the peer must be unable to acquire beta's lock while this flush holds it, got {peer_results!r}"
    )

    # Because the peer was genuinely blocked (never appended), beta's
    # sidecar -- if written at all -- must be an accurate rebuild of
    # beta's trail as it stood the whole time: no wrongly-trusted "clean"
    # header, and no dropped id.
    header, ids = activity_log._read_sidecar_header_and_ids(sidecar_beta)
    if header is not None:
        current_size, current_lines = activity_log._trail_stats(paths_beta.trail_jsonl)
        assert header.get("size") == current_size
        assert header.get("lines") == current_lines
    assert ids == {"tu_beta_old"}

    # Now the peer actually runs (lock released) and its append is
    # correctly seen as new drift on the NEXT flush -- never silently
    # absorbed into a stale-but-trusted sidecar.
    proc = subprocess.run([sys.executable, "-c", peer_script], capture_output=True, text=True)
    assert proc.stdout.strip() == "APPENDED"

    monkeypatch.setattr(htt, "_scan_ids_from_jsonl", real_scan)
    appended_2 = htt._flush_locked(
        paths_beta.trail_jsonl,
        [dict(_trail_record("tu_beta_peer", "2026-01-01T00:00:01"), tool_use_id="tu_beta_peer")],
        all_trail_paths,
    )
    assert appended_2 == 0, "the peer's id is already on disk in beta's own trail -- never re-appended as a duplicate"
