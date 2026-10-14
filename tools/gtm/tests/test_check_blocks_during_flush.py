"""Major finding #2 (regression fix): `activity_log.py check`'s sidecar-
drift verification (#20) reads the trail and its sidecar with no lock at
all. `_append_many_chained_trail_locked` (harvest_tool_trail.py) appends
every record of one flush to the trail FIRST and rewrites the sidecar ONCE
at the end -- so for the whole duration of a flush, the trail is
legitimately ahead of the sidecar. An unlocked `check` racing that window
used to report "sidecar drifted" even though nothing was actually wrong.

Uses the SAME event-handshake discipline as test_lock_scope_not_blocking.py
(never a wall-clock elapsed-time guess): a flush is patched to BLOCK,
mid-append (after writing trail records but before the sidecar rewrite),
on a threading.Event -- proving `check` genuinely waits for the flush to
finish (rather than observing the in-between state) by the fact that it
only ever reports success, never drift, no matter how long the flush's
own append phase takes.
"""

from __future__ import annotations

import json
import sys
import threading
from argparse import Namespace
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


def test_check_blocks_and_never_reports_drift_during_a_concurrent_flush(registered_home, monkeypatch):
    """RED-check: revert cmd_check to read the trail/sidecar with no lock
    at all (its shape before this fix) and this test's `check_results[0]
    == 0` assertion fails -- the unlocked check races right into the
    flush's genuine mid-append state (trail ahead of sidecar) and reports
    `rc != 0` with "sidecar drifted", even though the flush completes
    cleanly moments later.

    With the fix, `check` takes the SAME lock the flush holds, so it
    cannot even begin reading until the flush (and its lock) is released
    -- which means, deliberately, that `check`'s own read can never happen
    DURING the paused window at all; that is the fix working, not a test
    deadlock. So this test cannot synchronize on "check has read the
    trail" (with the fix, that event would never fire while the flush
    holds the lock, by design) -- instead it gives `check` a bounded
    window to ATTEMPT the race (a short, deliberately-generous sleep,
    the only place this test uses a time bound rather than an event, and
    only to prove an ATTEMPT was made, not to prove any particular
    outcome) before releasing the flush, then asserts on the terminal
    result: `check` must never have reported drift."""
    paths = activity_log.resolve_paths("acme")

    # Seed a FIRST record (and its matching sidecar) before the race --
    # verify_sidecar_matches_trail treats "no sidecar yet" as trivially OK
    # (nothing to be out of sync with), so the drift this finding
    # describes can only be observed once a real, previously-in-sync
    # sidecar exists to fall behind the trail during the second flush.
    seed_record = {
        "tool_use_id": "tu_seed_1", "ts": "2026-01-01T00:00:00", "session_id": "s0",
        "tool": "mcp__playwright-gtm__browser_navigate", "system": "google_ads",
    }
    htt._append_chained_trail(paths.trail_jsonl, seed_record)

    flush_paused = threading.Event()
    check_read_trail = threading.Event()

    real_append_many = htt._append_many_chained_trail_locked

    def blocking_append_many(path, records):
        # Write the (second) flush's record for real (this is what puts
        # the trail genuinely ahead of the ALREADY-EXISTING, previously
        # in-sync sidecar), then pause BEFORE the sidecar rewrite that
        # would normally happen at the end of this same call --
        # reproducing exactly the in-between state the finding describes,
        # deterministically, rather than hoping for a race.
        if records and path == paths.trail_jsonl:
            first, rest = records[0], records[1:]
            activity_log._append_chained(path, first)  # noqa: SLF001 - test, same module family
            flush_paused.set()
            # Wait (BOUNDED) for `check` to have genuinely read the trail
            # while it is still ahead of the sidecar. Pre-fix, `check`'s
            # unlocked read can and does race straight into this window,
            # so the signal fires and this returns quickly. Post-fix,
            # `check` is blocked on the very lock this call is running
            # under and can NEVER signal until this call returns -- so the
            # wait genuinely times out, and this thread proceeds to finish
            # the flush on its own; that timeout is the fix working, not
            # a hang (bounded at 3s so a real regression here costs the
            # suite seconds, never blocks it).
            # Nit fix: shortened from 3s -- this wait ALWAYS runs to its
            # full timeout on a green run (post-fix, `check` is blocked on
            # the lock this call holds and can never signal until this call
            # returns), so its length is pure fixed suite-time cost, not a
            # correctness bound. 0.5s is still generous enough for `check`
            # to have genuinely attempted (and been blocked on) its read
            # well within the window, on any machine this suite runs on.
            check_read_trail.wait(timeout=0.5)
            if rest:
                real_append_many(path, rest)
            else:
                # Still need the sidecar written for the single-record
                # case so the trail/sidecar pair ends up consistent.
                # `first` was already appended to the JSONL above (the
                # write this test's race targets); passing it to a
                # DIFFERENT trail path here would re-append it, so
                # instead rebuild the sidecar honestly from a real scan
                # of the trail -- the same ground-truth source
                # `_append_many_chained_trail_locked` itself falls back
                # to whenever its own prior header isn't trustworthy.
                activity_log._rebuild_ids_sidecar(path, activity_log._scan_ids_from_jsonl(path))
            return
        real_append_many(path, records)

    monkeypatch.setattr(htt, "_append_many_chained_trail_locked", blocking_append_many)

    real_read_jsonl = activity_log.read_jsonl

    def signaling_read_jsonl(path):
        if path == paths.trail_jsonl:
            check_read_trail.set()
        return real_read_jsonl(path)

    monkeypatch.setattr(activity_log, "read_jsonl", signaling_read_jsonl)

    check_results: list[int] = []

    def run_flush():
        record = {
            "tool_use_id": "tu_flush_1", "ts": "2026-01-01T00:00:01", "session_id": "s1",
            "tool": "mcp__playwright-gtm__browser_click", "system": "google_ads",
        }
        htt._flush_locked(paths.trail_jsonl, [record], [paths.trail_jsonl])

    flush_thread = threading.Thread(target=run_flush)
    flush_thread.start()

    entered = flush_paused.wait(timeout=10)
    assert entered, "flush thread never reached its paused mid-append state"

    def run_check():
        rc = activity_log.cmd_check(Namespace(company="acme"))
        check_results.append(rc)

    check_thread = threading.Thread(target=run_check)
    check_thread.start()

    flush_thread.join(timeout=15)
    assert not flush_thread.is_alive(), "flush thread never finished -- looks wedged"
    check_thread.join(timeout=10)
    assert not check_thread.is_alive(), "check thread never finished -- looks wedged"

    assert check_results, "check thread never recorded a result"
    assert check_results[0] == 0, "check must never report drift for a flush that completed cleanly"
