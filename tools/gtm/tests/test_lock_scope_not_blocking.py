"""#21: transcript scanning must happen WITHOUT holding the trail lock, so
a concurrent `activity_log.py add` issued DURING a long scan is not
blocked for the scan's duration. Uses a fake transcript iterator
(harvest_transcript patched to BLOCK on an Event) running in a background
thread, proved via an event handshake against the main thread's
`activity_log.py add` call (nit fix: not a wall-clock elapsed-time
threshold, which can flake on a loaded machine).
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402


def _minimal_pack(slug: str) -> dict:
    return {
        "schema_version": 1, "slug": slug, "legal_name": slug, "display_names": [slug],
        "business_model": "local_service", "brands": [],
        "persona_file": "x.md", "timezone": "America/Denver",
        "goals": {"north_star_metric": "leads", "guardrail_metrics": []},
        "scope": {"local_seo": True, "channels_in_scope": [], "channels_out_of_scope": []},
        "accounts": [],
        "identity_allowlist": {
            "facebook_page_ids": [], "instagram_ids": [], "gbp_location_ids": [],
            "ads_customer_ids": [], "meta_ad_account_ids": [], "ga4_property_ids": [],
            "gtm_container_ids": [], "domains": ["brightline-example.com"], "listing_urls": [],
        },
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
def registered_brightline(tmp_path, monkeypatch):
    claude_dir = tmp_path / "claude_dir"
    (claude_dir / "knowledge").mkdir(parents=True)
    home = tmp_path / "home_brightline"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text(json.dumps(_minimal_pack("brightline")), encoding="utf-8")
    (claude_dir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {"brightline": {"root": str(home)}}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DIR", str(claude_dir))
    monkeypatch.delenv("TS_ACTIVITY_MIRROR_DIR", raising=False)
    company.write_identity_index()
    return home


def _write_transcript(path: Path, url: str, tid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "sessionId": "sess_slow", "timestamp": "2026-01-01T09:00:00-06:00", "cwd": "/nowhere",
            "message": {"content": [
                {"type": "tool_use", "id": tid, "name": "mcp__playwright-gtm__browser_click", "input": {"element": "btn"}},
            ]},
        },
        {
            "sessionId": "sess_slow", "timestamp": "2026-01-01T09:00:01-06:00", "cwd": "/nowhere",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid, "content": f"- Page URL: {url}"},
            ]},
        },
    ]
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")


def test_add_not_blocked_during_a_slow_scan(registered_brightline, tmp_path, monkeypatch):
    """RED-check: revert main() to the pre-#21 design (acquire every
    relevant lock BEFORE scanning transcripts, hold it through the whole
    scan) and this test HANGS until its own timeout fires -- `add` would
    have to wait for the scan's own blocking wait (below) to be released,
    which only happens once `add` itself has already run, a real deadlock
    the old design could never resolve.

    nit fix: uses an EVENT HANDSHAKE instead of a wall-clock elapsed-time
    threshold (the prior version asserted `add_elapsed <
    SCAN_DELAY_SECONDS / 2`, which can flake on a loaded machine under
    real scheduling jitter). The scan is patched to BLOCK on an
    `threading.Event` (never a `time.sleep` guess) until `add` has
    genuinely completed and itself sets a SEPARATE "add is done" event --
    so the assertion is a real happens-before relationship (add finished
    strictly before the scan's block was ever released), not a timing
    guess. A timeout on the final `.wait()` calls is the only place any
    time bound appears, and it exists purely so a genuine regression fails
    the test instead of hanging the suite forever."""
    transcript = tmp_path / "slow.jsonl"
    _write_transcript(transcript, "https://brightline-example.com/x", "tu_slow_1")

    scan_entered = threading.Event()
    add_done = threading.Event()
    scan_thread_error: list[BaseException] = []

    real_harvest_transcript = htt.harvest_transcript

    def blocking_harvest_transcript(*args, **kwargs):
        # Signal that the (unlocked) scan phase has genuinely started,
        # then BLOCK until `add` (on the main thread, below) has actually
        # completed -- if the scan were holding a lock `add` also needs,
        # `add` could never complete, `add_done` would never be set, and
        # this `.wait()` would time out. Its own AssertionError is
        # recorded in `scan_thread_error` (never left to a background
        # thread's default exception handling, which pytest surfaces only
        # as a non-failing WARNING by default -- exactly the kind of
        # silent pass a regression here must never get) so the MAIN
        # thread can assert on it directly, below.
        scan_entered.set()
        add_finished_in_time = add_done.wait(timeout=10)
        if not add_finished_in_time:
            scan_thread_error.append(
                AssertionError("add never completed while the scan was blocked -- looks like a lock cycle")
            )
            return []
        return real_harvest_transcript(*args, **kwargs)

    monkeypatch.setattr(htt, "harvest_transcript", blocking_harvest_transcript)

    def run_harvest():
        htt.main([str(transcript)])

    harvest_thread = threading.Thread(target=run_harvest)
    harvest_thread.start()

    # Wait for the harvest thread to genuinely enter its (blocked) scan
    # phase before racing `add` against it -- a real synchronization
    # point, not a sleep-and-hope guess.
    entered_in_time = scan_entered.wait(timeout=10)
    assert entered_in_time, "harvest never reached its scan phase"

    from argparse import Namespace
    rc = activity_log.cmd_add(Namespace(
        company="brightline", system="google_ads", action="update", object="concurrent add during scan",
        before=None, after=None, why="testing lock scope", actor="main-session",
        evidence=[], undo="revert", approval="none", status="done", account=None, ts=None, notes=None,
    ))
    assert rc == 0
    # `add` completing here is itself the proof it was never blocked by a
    # lock the scan holds -- the scan is still parked on add_done.wait()
    # at this exact point, so if `add` needed the SAME lock the scan held,
    # this line would never be reached at all (a genuine hang, not a slow
    # pass).
    add_done.set()

    harvest_thread.join(timeout=10)
    assert not harvest_thread.is_alive(), "harvest thread never finished"
    # Surfaced explicitly on the MAIN thread -- a background thread's own
    # exception must never be left to pytest's default (warning-only,
    # non-failing) handling for a check this load-bearing.
    assert not scan_thread_error, scan_thread_error[0] if scan_thread_error else None
