"""Tests for heartbeat_audit (mechanical, non-LLM heartbeat cross-check, #4400 AA-0003).

Falsifiability: one RED fixture per violation class (proving the check actually
fires without the corresponding fix), one clean fixture proving zero violations,
plus a live-tree smoke run against the real repo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import heartbeat_artifact_stamp as has  # noqa: E402
import heartbeat_audit as ha  # noqa: E402

# Three tests below run the audit against THIS machine's real scheduler: the
# real `launchctl list` output plus the real schedules/com.oversight.*.plist
# files (their bodies say so: "no synthetic fixture", "live-tree smoke run").
# A machine without launchctl (any Linux box) or without those plists (a fresh
# install -- the bundle ships only example plists) has no such scheduler to
# audit, so the three skip with this reason. It is a skip CONDITION, not the
# `live_machine` marker: that marker is deselected by the runtime's documented
# default run, which would silently drop these checks from the daily suite on
# the one machine where they are meaningful. No seeding: a seeded
# oversight_install.md alone would only move them to the launchctl failure.
_HAVE_LAUNCHCTL = shutil.which("launchctl") is not None
_HAVE_OVERSIGHT_PLISTS = any(Path(ha.DEFAULT_HEARTBEATS_DIR).parent.glob("com.oversight.*.plist"))
requires_live_oversight_machine = pytest.mark.skipif(
    not (_HAVE_LAUNCHCTL and _HAVE_OVERSIGHT_PLISTS),
    reason=(
        "needs a live oversight scheduler: `launchctl` on PATH "
        f"(found: {_HAVE_LAUNCHCTL}) and at least one schedules/com.oversight.*.plist "
        f"(found: {_HAVE_OVERSIGHT_PLISTS}); a fresh install has neither"
    ),
)

# most_recent_scheduled_fire's LOCAL-TIME CONTRACT (fixed 2026-08-31, see its
# own docstring): launchd interprets StartCalendarInterval in the system's
# local timezone, never UTC. Every test below that exercises it MUST run
# under a fixed, non-UTC, non-machine-default local zone (America/New_York --
# deliberately never UTC, and never left to whatever zone the test runner's
# own machine happens to be in, so the test is a real regression guard on any
# machine and would have failed red against the pre-fix UTC-framed code
# everywhere except a runner literally configured for UTC). `local_tz`
# monkeypatches TZ + calls time.tzset() so the whole process (not just this
# module) reads local time consistently, and restores the original zone
# after the test. `_local_epoch` builds a real epoch from LOCAL wall-clock
# fields via time.mktime(), the same frame most_recent_scheduled_fire's own
# candidates are built in -- never datetime(..., tzinfo=timezone.utc), which
# is exactly the construction that let the old UTC-framed bug pass silently.
_TEST_TZ = "America/New_York"


@pytest.fixture
def local_tz(monkeypatch):
    monkeypatch.setenv("TZ", _TEST_TZ)
    time.tzset()
    try:
        yield _TEST_TZ
    finally:
        time.tzset()  # monkeypatch restores TZ itself; re-sync the C lib


def _local_epoch(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> float:
    """A real epoch for the given LOCAL wall-clock fields (under whatever
    zone `time.tzset()` currently has active — always call this AFTER the
    `local_tz` fixture has run). Deliberately NOT built via
    datetime(..., tzinfo=timezone.utc).timestamp(), which would silently
    re-introduce the UTC framing this fixture exists to rule out."""
    return time.mktime((year, month, day, hour, minute, second, 0, 0, -1))


_TABLE_DOC = """# doc

## 2. The jobs (label · expected_state · cadence · repo · prompt file · does)

| label | expected_state | StartCalendarInterval | repo | prompt file | does |
|---|---|---|---|---|---|
| com.oversight.csa.daily | loaded | 05:10 daily | ExampleApp | `daily_sweep.txt` | thing |
| com.oversight.csa.steward | loaded | 06:10 Tue,Fri | ExampleApp | `steward_sweep.txt` | thing |

`agentic-systems-architect` — no scheduled job yet.
"""


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _daily_hb(**overrides: object) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "job": "com.oversight.csa.daily",
        "started_at": _iso(now - timedelta(minutes=2)),
        "finished_at": _iso(now),
        "exit": 0,
        "cadence": "daily",
        "summary": "ok",
        "last_rotation_dim": "health",
        "slot_ran": "health",
        "last_staging_revision": "csa-backend-staging-1",
        "pin_suspect": False,
    }
    base.update(overrides)
    return base


def _plain_hb(job: str = "com.oversight.csa.steward", **overrides: object) -> dict:
    now = datetime.now(timezone.utc)
    base = {
        "job": job,
        "started_at": _iso(now - timedelta(minutes=1)),
        "finished_at": _iso(now),
        "exit": 0,
        "cadence": "2x/week",
        "summary": "ok",
    }
    base.update(overrides)
    return base


def _started_hb(
    job: str = "com.oversight.csa.daily",
    started_at: datetime | None = None,
    cadence: str = "daily",
    **overrides: object,
) -> dict:
    """An in-flight START heartbeat: _preamble.txt's step 3 shape — finished_at
    null, summary the literal "STARTED ..." prefix.
    """
    now = datetime.now(timezone.utc)
    at = started_at if started_at is not None else now
    base = {
        "job": job,
        "started_at": _iso(at),
        "finished_at": None,
        "exit": 1,
        "cadence": cadence,
        "summary": f"STARTED {_iso(at)}",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# parse_job_table
# --------------------------------------------------------------------------


def test_parse_job_table_happy_path():
    rows = ha.parse_job_table(_TABLE_DOC)
    assert rows == [
        ("com.oversight.csa.daily", "loaded", "05:10 daily"),
        ("com.oversight.csa.steward", "loaded", "06:10 Tue,Fri"),
    ]


def test_parse_job_table_missing_header_raises():
    import pytest

    with pytest.raises(ValueError, match="header"):
        ha.parse_job_table("no table here at all\njust prose\n")


def test_parse_job_table_missing_separator_raises():
    import pytest

    doc = "| label | cadence |\nnot a separator row\n| x | y |\n"
    with pytest.raises(ValueError, match="separator"):
        ha.parse_job_table(doc)


def test_parse_job_table_zero_rows_raises():
    import pytest

    doc = "| label | cadence |\n|---|---|\n\nprose after, no rows\n"
    with pytest.raises(ValueError, match="zero data rows"):
        ha.parse_job_table(doc)


# --------------------------------------------------------------------------
# check() — clean fixture
# --------------------------------------------------------------------------


def test_clean_fixture_zero_violations():
    table_labels = ["com.oversight.csa.daily", "com.oversight.csa.steward"]
    heartbeats = {
        "com.oversight.csa.daily": _daily_hb(),
        "com.oversight.csa.steward": _plain_hb(),
    }
    v = ha.check(table_labels, None, heartbeats, {}, loaded_labels=set(table_labels))
    assert v == []


# --------------------------------------------------------------------------
# check() — in-flight START exemptions + stale-start (B2)
# --------------------------------------------------------------------------


def test_inflight_start_exempt_from_finished_at_format_and_daily_typed_keys():
    # No cadence/now_epoch supplied — isolates the exemption from stale-start.
    hb = _started_hb(job="com.oversight.csa.daily")
    v = ha.check(
        ["com.oversight.csa.daily"], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set()
    )
    assert not any(
        line.startswith("bad-timestamp-format") and "finished_at" in line for line in v
    )
    assert not any(line.startswith("missing-daily-keys") for line in v)
    assert not any(line.startswith("bad-value") for line in v)


def test_inflight_start_fresh_no_violation():
    now = datetime.now(timezone.utc)
    hb = _started_hb(job="com.oversight.csa.daily", started_at=now - timedelta(minutes=2))
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
        table_cadences={"com.oversight.csa.daily": "05:10 daily"},
        now_epoch=now.timestamp(),
    )
    assert v == []


def test_inflight_start_older_than_cadence_plus_grace_flagged_stale():
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=40)  # daily cadence(24h) + grace(6h) = 30h threshold
    hb = _started_hb(job="com.oversight.csa.daily", started_at=started)
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
        table_cadences={"com.oversight.csa.daily": "05:10 daily"},
        now_epoch=now.timestamp(),
    )
    hits = [line for line in v if line.startswith("stale-start")]
    assert len(hits) == 1 and "com.oversight.csa.daily" in hits[0]


def test_inflight_start_stale_check_skipped_when_cadence_unknown():
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=40)
    hb = _started_hb(job="com.oversight.csa.ghost", started_at=started, cadence="unknown")
    v = ha.check(
        [],
        None,
        {"com.oversight.csa.ghost": hb},
        {},
        loaded_labels=set(),
        now_epoch=now.timestamp(),
    )
    assert not any(line.startswith("stale-start") for line in v)


# --------------------------------------------------------------------------
# dangling-heartbeat (AUDIT FINDING 2, 2026-09-03): a HARD, unconditional
# finding for ANY finished_at:null heartbeat past its own cadence+grace,
# regardless of the summary field's shape -- the real gap: stale-start above
# only ever fires for the narrow "STARTED ..." in-flight summary shape, so a
# dead heartbeat whose summary reads like a completed run (steward's real
# incident: dead 2 days, daily sweep caught productqa but not steward)
# previously fell through to the generic, cadence-blind bad-timestamp-format
# line instead of a distinct, un-ignorable finding.
# --------------------------------------------------------------------------


def _dangling_hb(job: str, started_at: datetime, cadence: str = "daily", **overrides: object) -> dict:
    """A dead heartbeat that does NOT match the STARTED-prefix in-flight
    shape -- exactly the "reads like a completed run" case from the audit
    finding: finished_at is null, but summary is ordinary prose, not
    "STARTED ...". _is_inflight_start() returns False for this shape, so
    stale-start never even considers it.
    """
    base = {
        "job": job,
        "started_at": _iso(started_at),
        "finished_at": None,
        "exit": 1,
        "cadence": cadence,
        "summary": "ok",  # deliberately NOT "STARTED ..." -- the gap case
    }
    base.update(overrides)
    return base


def test_dangling_heartbeat_stale_flagged_with_days_dead():
    # steward's real incident, reproduced: dead well beyond its own
    # cadence+grace (Tue,Fri -> worst-case gap 4d + grace 6h = 4.25d), and
    # its summary does not match the STARTED-prefix shape stale-start
    # requires.
    now = datetime.now(timezone.utc)
    started = now - timedelta(days=6)
    hb = _dangling_hb("com.oversight.csa.steward", started, cadence="2x/week")
    v = ha.check(
        ["com.oversight.csa.steward"],
        None,
        {"com.oversight.csa.steward": hb},
        {},
        loaded_labels={"com.oversight.csa.steward"},
        table_cadences={"com.oversight.csa.steward": "06:10 Tue,Fri"},
        now_epoch=now.timestamp(),
    )
    hits = [line for line in v if line.startswith("dangling-heartbeat")]
    assert len(hits) == 1
    assert "com.oversight.csa.steward" in hits[0]
    # days-dead must be present and un-ignorable in the message itself.
    assert "d ago" in hits[0]
    # stale-start (the narrower, summary-shape-gated check) never fires here
    # -- proving this is genuinely a distinct code path, not a relabeling.
    assert not any(line.startswith("stale-start") for line in v)


def test_dangling_heartbeat_recent_within_cadence_not_flagged():
    # Same shape, but started only 30 minutes ago -- well within its own
    # cadence+grace window. A heartbeat mid-flight for a normal amount of
    # time must never be flagged as dead.
    now = datetime.now(timezone.utc)
    started = now - timedelta(minutes=30)
    hb = _dangling_hb("com.oversight.csa.steward", started, cadence="2x/week")
    v = ha.check(
        ["com.oversight.csa.steward"],
        None,
        {"com.oversight.csa.steward": hb},
        {},
        loaded_labels={"com.oversight.csa.steward"},
        table_cadences={"com.oversight.csa.steward": "06:10 Tue,Fri"},
        now_epoch=now.timestamp(),
    )
    assert not any(line.startswith("dangling-heartbeat") for line in v)


def test_dangling_heartbeat_never_fires_for_finished_run():
    # A normal, completed heartbeat (finished_at populated) must never be
    # flagged as dangling, no matter how old started_at is.
    now = datetime.now(timezone.utc)
    hb = _plain_hb(
        job="com.oversight.csa.steward",
        started_at=_iso(now - timedelta(days=10)),
        finished_at=_iso(now - timedelta(days=10) + timedelta(minutes=5)),
    )
    v = ha.check(
        ["com.oversight.csa.steward"],
        None,
        {"com.oversight.csa.steward": hb},
        {},
        loaded_labels={"com.oversight.csa.steward"},
        table_cadences={"com.oversight.csa.steward": "06:10 Tue,Fri"},
        now_epoch=now.timestamp(),
    )
    assert not any(line.startswith("dangling-heartbeat") for line in v)


def test_dangling_heartbeat_skipped_when_cadence_unknown():
    # "Cannot determine staleness" must degrade to skip, never a guess.
    now = datetime.now(timezone.utc)
    started = now - timedelta(days=10)
    hb = _dangling_hb("com.oversight.csa.ghost", started, cadence="unknown")
    v = ha.check(
        [],
        None,
        {"com.oversight.csa.ghost": hb},
        {},
        loaded_labels=set(),
        now_epoch=now.timestamp(),
    )
    assert not any(line.startswith("dangling-heartbeat") for line in v)


def test_dangling_heartbeat_synthetic_heartbeat_dir_healthy_recent_stale(tmp_path):
    # End-to-end via _gather()/main()'s own real IO path: a synthetic
    # heartbeats dir with one healthy job, one dangling-but-recent job (NOT
    # flagged -- within its own cadence+grace), and one dangling-stale job
    # (flagged). This is the exact scenario named in the audit finding: a
    # heartbeat that "reads like a completed run" (finished_at:null, plain
    # summary) must be caught mechanically, unconditionally, every run.
    import json as _json

    doc = tmp_path / "install.md"
    doc.write_text(_TABLE_DOC)  # declares com.oversight.csa.daily + .steward

    hb_dir = tmp_path / "heartbeats"
    hb_dir.mkdir()
    now = datetime.now(timezone.utc)

    # Healthy: a normal completed daily heartbeat.
    (hb_dir / "com.oversight.csa.daily.json").write_text(_json.dumps(_daily_hb()))

    # Dangling-recent: steward started 10 minutes ago, finished_at still
    # null, ordinary summary -- well within cadence(4d worst-case)+grace.
    # NOT flagged.
    recent_started = now - timedelta(minutes=10)
    (hb_dir / "com.oversight.csa.steward.json").write_text(
        _json.dumps(_dangling_hb("com.oversight.csa.steward", recent_started, cadence="2x/week"))
    )

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    launch_agents_dir = tmp_path / "LaunchAgents"  # absent -- hermetic

    (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        heartbeats,
        log_times,
        plist_epochs,
        plist_calendar_intervals,
        wheel_granted_tools,
        wheel_history_records,
    ) = ha._gather(str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir))
    assert table_error is None

    v = ha.check(
        table_labels,
        table_error,
        heartbeats,
        log_times,
        loaded_labels={"com.oversight.csa.daily", "com.oversight.csa.steward"},
        table_cadences=table_cadences,
        table_expected_states=table_expected_states,
        plist_install_epochs=plist_epochs,
        now_epoch=now.timestamp(),
        plist_calendar_intervals=plist_calendar_intervals,
    )
    assert not any(line.startswith("dangling-heartbeat") for line in v)

    # Now replace steward's heartbeat with a dangling-STALE one: started 2
    # days and 6 hours ago (well beyond its Tue,Fri cadence(4d worst-case
    # gap)+grace(6h) -- use a shorter-cadence job to keep the fixture tight:
    # re-declare steward's cadence as daily via table_cadences override so
    # 2d6h is unambiguously stale regardless of the worst-case weekly gap.
    stale_started = now - timedelta(days=2, hours=6)
    (hb_dir / "com.oversight.csa.steward.json").write_text(
        _json.dumps(_dangling_hb("com.oversight.csa.steward", stale_started, cadence="daily"))
    )
    (
        table_labels2,
        table_cadences2,
        table_expected_states2,
        table_error2,
        heartbeats2,
        log_times2,
        plist_epochs2,
        plist_calendar_intervals2,
        wheel_granted_tools2,
        wheel_history_records2,
    ) = ha._gather(str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir))
    table_cadences2["com.oversight.csa.steward"] = "06:10 daily"  # force an unambiguous daily cadence
    v2 = ha.check(
        table_labels2,
        table_error2,
        heartbeats2,
        log_times2,
        loaded_labels={"com.oversight.csa.daily", "com.oversight.csa.steward"},
        table_cadences=table_cadences2,
        plist_install_epochs=plist_epochs2,
        now_epoch=now.timestamp(),
        plist_calendar_intervals=plist_calendar_intervals2,
    )
    hits = [line for line in v2 if line.startswith("dangling-heartbeat")]
    assert len(hits) == 1
    assert "com.oversight.csa.steward" in hits[0]
    assert "d ago" in hits[0]
    # daily's own healthy heartbeat must never be flagged.
    assert not any(
        line.startswith("dangling-heartbeat") and "com.oversight.csa.daily" in line for line in v2
    )


# --------------------------------------------------------------------------
# check() — RED per violation class
# --------------------------------------------------------------------------


def test_missing_required_key_flagged():
    hb = _plain_hb()
    del hb["cadence"]
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("missing-keys")]
    assert len(hits) == 1 and "cadence" in hits[0]


def test_daily_missing_typed_keys_flagged():
    hb = _daily_hb()
    del hb["pin_suspect"]
    del hb["slot_ran"]
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
    )
    hits = [line for line in v if line.startswith("missing-daily-keys")]
    assert len(hits) == 1 and "pin_suspect" in hits[0] and "slot_ran" in hits[0]


def test_daily_bad_rotation_dim_value_flagged():
    hb = _daily_hb(last_rotation_dim="bogus")
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
    )
    assert any(line.startswith("bad-value") and "last_rotation_dim" in line for line in v)


def test_daily_bad_slot_ran_value_flagged():
    hb = _daily_hb(slot_ran="tuesday")
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
    )
    assert any(line.startswith("bad-value") and "slot_ran" in line for line in v)


def test_daily_last_staging_revision_wrong_type_flagged():
    hb = _daily_hb(last_staging_revision=123)
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"com.oversight.csa.daily": hb},
        {},
        loaded_labels=set(),
    )
    assert any(line.startswith("bad-type") and "last_staging_revision" in line for line in v)


def test_pin_suspect_wrong_type_flagged_on_any_job():
    hb = _plain_hb(job="com.oversight.csa.trustarch", pin_suspect="false")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("bad-type") and "pin_suspect" in line]
    assert len(hits) == 1


def test_bad_utc_timestamp_format_flagged():
    hb = _plain_hb(started_at="2026-08-25T05:10:00-06:00")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("bad-timestamp-format") and "started_at" in line]
    assert len(hits) == 1


def test_timestamp_divergence_flagged():
    now = datetime.now(timezone.utc)
    hb = _plain_hb(
        started_at=_iso(now - timedelta(minutes=1)),
        finished_at=_iso(now),
    )
    log_start = (now - timedelta(minutes=1)).timestamp() - 400  # 400s off, > 5min
    log_finish = now.timestamp()
    v = ha.check([], None, {"x": hb}, {"x": (log_start, log_finish)}, loaded_labels=set())
    hits = [line for line in v if line.startswith("timestamp-divergence") and "started_at" in line]
    assert len(hits) == 1


def test_timestamp_within_threshold_not_flagged():
    now = datetime.now(timezone.utc)
    hb = _plain_hb(started_at=_iso(now), finished_at=_iso(now))
    log_start = now.timestamp() - 60  # 1 min off, under threshold
    log_finish = now.timestamp() + 60
    v = ha.check([], None, {"x": hb}, {"x": (log_start, log_finish)}, loaded_labels=set())
    assert not any(line.startswith("timestamp-divergence") for line in v)


def test_heartbeat_older_than_log_labeled_distinctly_not_fabrication():
    # N14: the heartbeat's OWN claimed time is the OLDER of the two — most
    # plausibly a rotated/re-touched log file, not a fabricated timestamp —
    # so it gets its own distinct label, never "timestamp-divergence".
    now = datetime.now(timezone.utc)
    hb = _plain_hb(started_at=_iso(now - timedelta(minutes=10)), finished_at=_iso(now))
    log_start = now.timestamp()  # log evidence is NEWER than the claimed start
    log_finish = now.timestamp()
    v = ha.check([], None, {"x": hb}, {"x": (log_start, log_finish)}, loaded_labels=set())
    hits = [
        line for line in v if line.startswith("heartbeat-older-than-log") and "started_at" in line
    ]
    assert len(hits) == 1
    assert not any(line.startswith("timestamp-divergence") and "started_at" in line for line in v)


# --------------------------------------------------------------------------
# check() — relative-artifact-claim (#5055, 2026-09-07 launchdir
# false-alarm incident; REALITY-GATED per a same-day dual-Opus review B-1
# blocker — flags only a relative/"~" claim that ALSO resolves to a real,
# existing file via $HOME/.claude; shape alone (extract_path_claims) is
# never enough, so ordinary prose containing a slash is never flagged).
#
# `_fake_claude_dir` points heartbeat_artifact_stamp.DEFAULT_CLAUDE_DIR (the
# module heartbeat_audit.resolve_claim reads its $HOME/.claude fallback
# from) at a hermetic tmp dir for every test below — without this, a test
# using a real-looking relative path could pass or fail depending on
# whatever happens to exist under the REAL ~/.claude on the machine running
# the suite (measured live: "plans/csa_state_2026-09-07.html" resolves to a
# real file on this machine TODAY, which made an earlier, non-hermetic
# version of this test pass for the wrong reason — it would silently break
# again once that file ages out or the suite runs on a different machine).
# --------------------------------------------------------------------------


@pytest.fixture
def _fake_claude_dir(tmp_path, monkeypatch):
    fake = tmp_path / "fake_claude"
    fake.mkdir()
    monkeypatch.setattr(has, "DEFAULT_CLAUDE_DIR", str(fake))
    return fake


def test_relative_artifact_claim_flagged_when_it_resolves_to_a_real_file(_fake_claude_dir):
    (_fake_claude_dir / "plans").mkdir()
    (_fake_claude_dir / "plans" / "csa_state_2026-09-07.html").write_text("x", encoding="utf-8")

    hb = _plain_hb(summary="wrote plans/csa_state_2026-09-07.html to disk")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("relative-artifact-claim")]
    assert len(hits) == 1
    assert "plans/csa_state_2026-09-07.html" in hits[0]


def test_relative_claim_that_does_not_resolve_is_not_flagged_prose_safety(_fake_claude_dir):
    # B-1 review fix: a shape-matching but NON-resolving relative token
    # (nothing at plans/csa_state_2026-09-07.html in the fake $HOME/.claude)
    # must NOT be flagged -- this is the prose-safety property the reality
    # gate exists to provide (testarch's own "Clusters C/E" prose, tested
    # explicitly below).
    hb = _plain_hb(summary="wrote plans/csa_state_2026-09-07.html to disk")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_prose_slash_fragment_never_flagged(_fake_claude_dir):
    # testarch's own real-world "Clusters C/E" convention note (per the
    # module docstring) — ordinary prose containing a slash, shape-matches
    # extract_path_claims but resolves to nothing real, so it is never
    # flagged as a relative-artifact-claim.
    hb = _plain_hb(job="com.oversight.csa.testarch", summary="Clusters C/E flagged, dropped 2/5")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_absolute_artifact_claim_not_flagged(_fake_claude_dir):
    hb = _plain_hb(
        summary="wrote /Users/x/.claude/plans/csa_state_2026-09-07.html to disk"
    )
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_tilde_anchored_artifact_claim_that_resolves_not_flagged(monkeypatch, tmp_path, _fake_claude_dir):
    # A "~"-anchored claim that DOES resolve to a real file is a legitimate
    # already-anchored form (per _preamble.txt step 5's own wording) and
    # must not be flagged, same as a true-absolute claim.
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    (fake_home / "report.html").write_text("x", encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))

    hb = _plain_hb(summary="wrote ~/report.html to disk")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_wrapper_prefixed_summary_exempted_from_relative_artifact_claim(_fake_claude_dir):
    hb = _plain_hb(
        summary=(
            "WRAPPER: claude process exited without a truthful END heartbeat — "
            "see schedules/logs/x.out.log for the real cause."
        )
    )
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_inflight_start_exempted_from_relative_artifact_claim(_fake_claude_dir):
    # An in-flight START heartbeat legitimately hasn't written its real
    # artifact claim yet — mirrors every other finished-only check's own
    # in-flight exemption. Even a claim that WOULD resolve is exempt while
    # in flight.
    (_fake_claude_dir / "plans").mkdir()
    (_fake_claude_dir / "plans" / "not_yet_written.html").write_text("x", encoding="utf-8")
    hb = _started_hb(job="com.oversight.csa.daily")
    hb["summary"] = "STARTED " + hb["started_at"] + " plans/not_yet_written.html"
    v = ha.check(
        ["com.oversight.csa.daily"], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set()
    )
    assert not any(line.startswith("relative-artifact-claim") for line in v)


def test_relative_artifact_claim_clean_after_stamp_rewrite(_fake_claude_dir):
    # Once heartbeat_artifact_stamp.stamp() has rewritten a resolvable
    # relative claim to its absolute form in-place, the check finds nothing
    # left to flag -- no separate artifacts_verified-based exemption needed.
    hb = _plain_hb(
        summary="wrote /Users/x/.claude/plans/csa_state_2026-09-07.html to disk",
        artifacts_verified=[
            {
                "claimed": "plans/csa_state_2026-09-07.html",
                "resolved": "/Users/x/.claude/plans/csa_state_2026-09-07.html",
                "exists": True,
            }
        ],
    )
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("relative-artifact-claim") for line in v)


# --- B-3 positive fixtures (dual-Opus review): ------------------------------


def test_relative_artifact_claim_multi_claim_heartbeat_both_flagged(_fake_claude_dir):
    (_fake_claude_dir / "reports").mkdir()
    (_fake_claude_dir / "reports" / "a.html").write_text("x", encoding="utf-8")
    (_fake_claude_dir / "reports" / "b.html").write_text("x", encoding="utf-8")

    hb = _plain_hb(summary="wrote reports/a.html and reports/b.html to disk")
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("relative-artifact-claim")]
    assert len(hits) == 1
    assert "reports/a.html" in hits[0]
    assert "reports/b.html" in hits[0]


def test_relative_artifact_claim_resolves_and_exists_flagged(_fake_claude_dir):
    # The exact launchdir-incident shape: a claim that both RESOLVES (a
    # candidate path can be built) AND EXISTS (a real file sits there) is
    # flagged -- this is the positive case the whole check exists for.
    (_fake_claude_dir / "plans").mkdir()
    (_fake_claude_dir / "plans" / "csa_state_2026-09-07.html").write_text("x", encoding="utf-8")

    hb = _plain_hb(
        job="com.oversight.csa.launchdir", summary="wrote plans/csa_state_2026-09-07.html"
    )
    v = ha.check([], None, {"x": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("relative-artifact-claim")]
    assert len(hits) == 1


def test_unexpected_heartbeat_flagged():
    hb = _plain_hb(job="com.oversight.csa.ghost")
    v = ha.check(
        ["com.oversight.csa.daily"], None, {"com.oversight.csa.ghost": hb}, {}, loaded_labels=set()
    )
    assert any(line.startswith("unexpected-heartbeat") for line in v)


# --------------------------------------------------------------------------
# check() — lock-refused (H3, THE ISSUE WHEEL hardening plan, BLOCKER 2)
# --------------------------------------------------------------------------


def test_lock_refused_flagged_when_exit_75():
    # run_oversight_job.sh's concurrency guard writes exactly this shape on
    # a refused lock acquisition: exit 75, but a fresh, well-formed,
    # non-null finished_at -- the RED condition this check exists to close
    # (every OTHER check in this module reads that shape as a clean finish).
    hb = _plain_hb(exit=75, summary="WRAPPER: refused - held by pid 123")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("lock-refused")]
    assert len(hits) == 1
    assert "exit: 75" in hits[0]


def test_lock_refused_not_flagged_on_clean_exit_zero():
    hb = _plain_hb(exit=0, summary="ok")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("lock-refused") for line in v)


def test_lock_refused_not_flagged_on_other_nonzero_exit():
    # Distinguishes this check from a blanket "any failure" flag -- only the
    # specific EX_TEMPFAIL=75 lock-refusal shape is in scope; a genuinely
    # different failure exit (e.g. 142, the alarm hang-kill) is not this
    # check's business and must not be conflated with it.
    hb = _plain_hb(exit=142, summary="WRAPPER: claude process exited without a heartbeat")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("lock-refused") for line in v)


def test_lock_refused_exempt_when_inflight_start():
    # An in-flight START heartbeat's exit field is a placeholder (1, per
    # _started_hb's own fixture shape, mirroring _preamble.txt step 3) --
    # never a real refusal signal, since a run that hasn't finished yet was
    # never refused. Construct the narrow case where that placeholder value
    # would coincidentally equal 75 to prove the in-flight exemption itself
    # is what suppresses it, not the value happening to differ.
    hb = _started_hb(job="com.oversight.wheel.csa", exit=75)
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {"com.oversight.wheel.csa": hb},
        {},
        loaded_labels=set(),
    )
    assert not any(line.startswith("lock-refused") for line in v)


def test_lock_refused_missing_or_bad_type_exit_not_flagged():
    # Missing/non-int `exit` degrades to "cannot determine" here -- the
    # missing-keys/bad-type checks already cover that shape by name, so this
    # check must never guess.
    hb = _plain_hb(summary="ok")
    del hb["exit"]
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("lock-refused") for line in v)

    hb2 = _plain_hb(exit="75", summary="ok")  # string, not int
    v2 = ha.check([], None, {"com.oversight.wheel.csa": hb2}, {}, loaded_labels=set())
    assert not any(line.startswith("lock-refused") for line in v2)


def test_manual_prefixed_heartbeat_exempted_from_unexpected():
    hb = _plain_hb(job="manual-sweep", cadence="manual")
    v = ha.check(["com.oversight.csa.daily"], None, {"manual-sweep": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("unexpected-heartbeat") for line in v)


def test_loaded_overdue_daily_job_flagged_red():
    # B5/N12: daily job, plist installed 3 days ago, no heartbeat -> its
    # cadence(1 day) + grace(6h) is long elapsed -> genuinely overdue -> RED.
    now = datetime.now(timezone.utc).timestamp()
    installed = now - (3 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.daily"},
        table_cadences={"com.oversight.csa.daily": "05:10 daily"},
        plist_install_epochs={"com.oversight.csa.daily": installed},
        now_epoch=now,
    )
    assert any(line.startswith("loaded-never-fired") and "daily" in line for line in v)


def test_loaded_recently_not_yet_due_not_flagged():
    # B5/N12: monthly job, plist installed 2 days ago, no heartbeat -> not
    # yet due (its cadence period hasn't elapsed since install) -> NOT flagged.
    now = datetime.now(timezone.utc).timestamp()
    installed = now - (2 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        plist_install_epochs={"com.oversight.csa.testarch": installed},
        now_epoch=now,
    )
    assert not any(line.startswith("loaded-never-fired") for line in v)


def test_loaded_never_fired_flagged_when_cadence_data_unavailable():
    # Missing cadence/install-time data degrades to the old, conservative
    # behavior (flag immediately) rather than silently granting an exemption
    # it cannot actually prove.
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
    )
    assert any(line.startswith("loaded-never-fired") and "testarch" in line for line in v)


def test_table_expected_job_not_loaded_never_flagged_as_never_fired():
    # A table-expected job that is simply not loaded (e.g. loop, parked) must
    # never be reported as loaded-never-fired, regardless of cadence timing.
    v = ha.check(
        ["com.oversight.csa.loop"],
        None,
        {},
        {},
        loaded_labels=set(),
    )
    assert not any(line.startswith("loaded-never-fired") for line in v)


# --------------------------------------------------------------------------
# expected-but-unloaded (H1, THE ISSUE WHEEL hardening plan, commit c1).
#
# Falsifiability per the plan's own "Falsifiable test:" subsection for H1
# (luminous-napping-marble.md):
#   - Pair 1: RED against the REAL, current condition (both wheel plists
#     genuinely unloaded today, and the pre-fix code/table had no
#     expected_state column at all) -> no finding about either wheel job is
#     even possible. GREEN: after this commit, the SAME real unloaded state
#     (before the operator's own `launchctl load` step) emits
#     expected-but-unloaded for the labels whose real oversight_install.md
#     row now declares expected_state: loaded.
#   - Pair 4: the 3-tuple migration doesn't silently swap which index means
#     which field — table_cadences must never receive an expected_state
#     value, and vice versa.
# --------------------------------------------------------------------------


@requires_live_oversight_machine
def test_expected_but_unloaded_GREEN_real_unloaded_wheels_flagged_post_fix():
    """GREEN: the post-fix check(), run against the REAL current
    oversight_install.md table and the REAL live `launchctl list` output
    (both read via the actual _gather()/_launchctl_loaded_labels() IO
    path -- no synthetic fixture), emits expected-but-unloaded for every
    label whose real table row declares expected_state: loaded but that
    launchctl does not currently report as loaded.

    This is the plan's own accepted, expected, transient true-positive
    (H1's text: "between this commit landing and the operator's own
    separate launchctl load step, the watchdog's very first real run(s)
    will correctly fire expected-but-unloaded for both wheels"). If the
    operator has since run launchctl load for a given label, that label
    legitimately drops out of the diff -- so this test asserts the
    mechanism fires for whichever expected-but-currently-unloaded labels
    exist right now, deriving the expectation from the same real inputs
    the check itself consumes, rather than hardcoding today's snapshot.
    """
    (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        heartbeats,
        log_times,
        plist_epochs,
        plist_calendar_intervals,
        wheel_granted_tools,
        wheel_history_records,
    ) = ha._gather(ha.DEFAULT_INSTALL_DOC, ha.DEFAULT_HEARTBEATS_DIR, ha.DEFAULT_LOGS_DIR)
    assert table_error is None
    # The real table must actually declare at least one loaded-expected
    # label, or this test cannot prove anything about the real condition.
    loaded_expected_labels = {
        label for label in table_labels if table_expected_states.get(label) == "loaded"
    }
    assert loaded_expected_labels, (
        "expected the real oversight_install.md §2 table to declare at "
        "least one expected_state: loaded row"
    )

    loaded_labels = ha._launchctl_loaded_labels()
    assert loaded_labels is not None, "launchctl list must be readable on this machine to run this GREEN case"

    expected_to_fire = {label for label in loaded_expected_labels if label not in loaded_labels}

    violations = ha.check(
        table_labels,
        table_error,
        heartbeats,
        log_times,
        loaded_labels,
        table_cadences=table_cadences,
        table_expected_states=table_expected_states,
        plist_install_epochs=plist_epochs,
        now_epoch=time.time(),
        plist_calendar_intervals=plist_calendar_intervals,
    )
    fired_for = {
        line.split("expected-but-unloaded: ", 1)[1].split(" ", 1)[0]
        for line in violations
        if line.startswith("expected-but-unloaded:")
    }
    assert fired_for == expected_to_fire, (
        f"expected-but-unloaded fired for {sorted(fired_for)}, expected exactly "
        f"{sorted(expected_to_fire)} (loaded_expected_labels={sorted(loaded_expected_labels)}, "
        f"loaded_labels={sorted(loaded_labels)})"
    )
    # This plan's own accepted-transient case: at minimum, THE ISSUE WHEEL's
    # own two plists are declared expected_state: loaded in the real table
    # today and are not yet launchctl-loaded (per H1's own text) -- assert
    # this real, named case specifically, not just the set-equality above,
    # so a future accidental narrowing of the check (e.g. only ever firing
    # for ONE of the two) is caught even if some other label's real load
    # state happens to make the set-equality assertion above pass by luck.
    for wheel_label in ("com.oversight.wheel.csa", "com.oversight.wheel.agency"):
        if wheel_label in loaded_expected_labels and wheel_label not in loaded_labels:
            assert wheel_label in fired_for, (
                f"{wheel_label} is expected_state: loaded in the real table and not "
                f"currently loaded in launchctl, but expected-but-unloaded did not fire "
                f"for it (violations: {violations})"
            )


def test_expected_but_unloaded_not_flagged_when_already_loaded():
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.wheel.csa"},
        table_expected_states={"com.oversight.wheel.csa": "loaded"},
    )
    assert not any(line.startswith("expected-but-unloaded") for line in v)


def test_expected_but_unloaded_not_flagged_when_expected_state_not_loaded():
    # A label with a missing/other expected_state value degrades to "cannot
    # determine" -- never flagged -- same conservative direction as every
    # other check in this module (loaded-never-fired, silent-job).
    v = ha.check(
        ["com.oversight.wheel.agency"],
        None,
        {},
        {},
        loaded_labels=set(),
        table_expected_states={"com.oversight.wheel.agency": "symlinked-not-loaded"},
    )
    assert not any(line.startswith("expected-but-unloaded") for line in v)

    v2 = ha.check(
        ["com.oversight.wheel.agency"],
        None,
        {},
        {},
        loaded_labels=set(),
        table_expected_states={},  # missing entirely
    )
    assert not any(line.startswith("expected-but-unloaded") for line in v2)


def test_expected_but_unloaded_never_gated_on_now_epoch_or_cadence():
    # Per the plan: a pure set-difference, needs no now_epoch/cadence/
    # install-time data at all -- must fire even when every other
    # cadence-gated input is entirely absent.
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels=set(),
        table_expected_states={"com.oversight.wheel.csa": "loaded"},
        table_cadences=None,
        plist_install_epochs=None,
        now_epoch=None,
        plist_calendar_intervals=None,
    )
    assert any(
        line.startswith("expected-but-unloaded") and "com.oversight.wheel.csa" in line
        for line in v
    )


# --------------------------------------------------------------------------
# parse_job_table 3-tuple migration: field-order regression guard (H1
# falsifiable-test pair 4). A wrong-index mistake (fixing only the tuple
# arity, not which cell means which field) would NOT be caught by "the code
# runs without raising" -- parse_job_table's own call site wraps it in a
# bare except Exception that converts almost any downstream misuse into a
# quiet table_error/degraded state, so this must be asserted directly.
# --------------------------------------------------------------------------


def test_parse_job_table_field_order_expected_state_never_lands_in_cadence():
    doc = """# doc

| label | expected_state | StartCalendarInterval | repo | prompt file | does |
|---|---|---|---|---|---|
| com.oversight.wheel.csa | loaded | 22:10 Mon-Fri | ExampleApp | `issue_wheel.txt` | thing |
"""
    rows = ha.parse_job_table(doc)
    assert rows == [("com.oversight.wheel.csa", "loaded", "22:10 Mon-Fri")]
    label, expected_state, cadence = rows[0]
    # The case a field-order mistake would pass silently: expected_state
    # ("loaded"/"symlinked-not-loaded"/"removed") landing where cadence
    # should be, or vice versa.
    assert expected_state == "loaded"
    assert cadence == "22:10 Mon-Fri"
    assert expected_state not in ("22:10 Mon-Fri",)
    assert cadence not in ("loaded", "symlinked-not-loaded", "removed")
    # cadence must be a genuine, parseable cadence string -- not an
    # expected_state closed value, which cadence_seconds() would (correctly)
    # fail to parse, silently disabling the stale-start/loaded-never-fired
    # "not yet due" exemption for this row.
    assert ha.cadence_seconds(cadence) is not None


@requires_live_oversight_machine
def test_gather_table_cadences_never_receive_expected_state_values_real_table():
    """The same regression, exercised end-to-end through the real
    _gather() IO path against the real oversight_install.md — the exact
    call sites (table_labels, table_cadences in _gather()) the plan names
    as the two existing consumers that must be re-destructured correctly,
    not just parse_job_table() in isolation."""
    (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        _heartbeats,
        _log_times,
        _plist_epochs,
        _plist_calendar_intervals,
        _wheel_granted_tools,
        _wheel_history_records,
    ) = ha._gather(ha.DEFAULT_INSTALL_DOC, ha.DEFAULT_HEARTBEATS_DIR, ha.DEFAULT_LOGS_DIR)
    assert table_error is None
    _CLOSED_EXPECTED_STATE_VALUES = {"loaded", "symlinked-not-loaded", "removed"}
    for label in table_labels:
        cadence = table_cadences.get(label)
        assert cadence is not None, f"{label} missing from table_cadences"
        assert cadence not in _CLOSED_EXPECTED_STATE_VALUES, (
            f"{label}'s table_cadences value ({cadence!r}) looks like an "
            "expected_state closed value, not a genuine cadence string -- "
            "field-order regression (cells[1]/cells[2] swapped)"
        )
        assert ha.cadence_seconds(cadence) is not None, (
            f"{label}'s table_cadences value ({cadence!r}) is not a parseable "
            "cadence -- either a real data-quality bug or a field-order regression"
        )
    for label in table_labels:
        expected_state = table_expected_states.get(label)
        assert expected_state is not None, f"{label} missing from table_expected_states"
        # An expected_state value must never itself look like a cadence
        # string (the mirror-image swap).
        assert not ha._CADENCE_TIME_PREFIX_RE.match(expected_state), (
            f"{label}'s table_expected_states value ({expected_state!r}) looks like "
            "a cadence string, not an expected_state value -- field-order regression"
        )


# --------------------------------------------------------------------------
# silent-job (AA-0050): calendar-exact complement to loaded-never-fired.
# --------------------------------------------------------------------------


def test_silent_job_flagged_when_calendar_fire_window_passed_but_cadence_exemption_would_miss_it(local_tz):
    # AA-0050's real scenario: a monthly job (StartCalendarInterval Day=1)
    # installed 9 days ago. cadence_seconds()'s worst-case monthly
    # approximation (~31 days) would exempt it via loaded-never-fired's own
    # "not yet due" logic (elapsed 9d < threshold 31d + grace) -- exactly
    # the gap that let testarch/trustarch go silent for a week undetected.
    # The calendar-exact silent-job check reads the plist's own Day=1/Hour=6/
    # Minute=10 rule directly and correctly sees the fire window already
    # passed (well beyond GRACE_SECONDS), even though loaded-never-fired
    # stays silent on the very same inputs.
    #
    # LOCAL-TIME framed (America/New_York, EDT = UTC-4 in September): 'now'
    # is built from LOCAL wall-clock fields via _local_epoch, never a
    # UTC-tagged datetime -- this is the exact frame most_recent_scheduled_
    # fire computes in (its own docstring), and differs from what a
    # UTC-tagged construction of the same numbers would mean by the full
    # 4h offset (see test_silent_job_local_time_contract_differs_from_utc_
    # framing below for the direct, isolated proof of that divergence).
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    installed = now - (9 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        plist_install_epochs={"com.oversight.csa.testarch": installed},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
    )
    assert any(line.startswith("silent-job") and "testarch" in line for line in v)
    # loaded-never-fired's own coarser exemption is untouched by this fix —
    # it still stays silent on the same inputs (that IS the gap this new
    # check exists to close, named distinctly rather than replacing it).
    assert not any(line.startswith("loaded-never-fired") for line in v)


def test_silent_job_local_time_contract_differs_from_utc_framing(local_tz):
    # Direct, isolated falsifiability proof for the LOCAL-time fix: the SAME
    # now_epoch resolves to a DIFFERENT (and correct) fire time than a
    # UTC-framed computation would give, under a real non-UTC zone (EDT,
    # UTC-4 in September) with no DST edge case involved. This is the test
    # that fails RED against the pre-fix (tz=timezone.utc) module -- with
    # the bug, most_recent_scheduled_fire's candidates are built in UTC, so
    # a Day=1/Hour=6/Minute=10 rule matching UTC 06:10 resolves to a
    # timestamp that, read back in LOCAL time, is 06:10 MINUS the zone
    # offset (02:10 EDT) rather than the real local fire at 06:10 EDT.
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    fire = ha.most_recent_scheduled_fire({"Day": 1, "Hour": 6, "Minute": 10}, now)
    assert fire is not None
    fire_local = datetime.fromtimestamp(fire)
    assert fire_local == datetime(2026, 9, 1, 6, 10, 0)
    # The value a (buggy) UTC-framed computation would have produced for
    # this same now_epoch, if launchd's Hour=6/Minute=10 were (wrongly)
    # read as UTC 06:10 instead of LOCAL 06:10 -- must NOT equal the real
    # answer above, proving the two framings are observably different for
    # this scenario (never true in either frame -- the unfalsifiable
    # pattern the reviewer flagged in the prior UTC-tagged tests).
    utc_framed_wrong_answer = datetime(2026, 9, 1, 6, 10, 0, tzinfo=timezone.utc).timestamp()
    assert fire != utc_framed_wrong_answer


def test_silent_job_not_flagged_when_fire_window_still_within_grace(local_tz):
    # The same monthly job, but 'now' is only 50 minutes past its Day=1
    # 06:10 fire -- comfortably inside GRACE_SECONDS (6h). Not yet a
    # violation: a job that just fired hasn't had time to write its
    # heartbeat and shouldn't be flagged as silent.
    now = _local_epoch(2026, 9, 1, 7, 0, 0)
    installed = now - (8 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        plist_install_epochs={"com.oversight.csa.testarch": installed},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_not_flagged_when_heartbeat_exists(local_tz):
    # A job with a real heartbeat file is never "silent" regardless of what
    # its calendar rule says -- this check only ever fires on the ABSENCE
    # of a heartbeat, exactly like loaded-never-fired.
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    hb = _plain_hb(job="com.oversight.csa.testarch")
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {"com.oversight.csa.testarch": hb},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_not_flagged_when_calendar_interval_unknown(local_tz):
    # No plist_calendar_intervals entry for this label at all -- "cannot
    # determine the schedule" must never be treated as "overdue".
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        now_epoch=now,
        plist_calendar_intervals={},
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_not_flagged_when_now_epoch_unknown():
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
        now_epoch=None,
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_not_flagged_when_job_not_loaded(local_tz):
    # Expected per the table but not currently loaded (e.g. parked) -- never
    # a silent-job finding, mirroring loaded-never-fired's own scoping to
    # table_set & loaded_labels.
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels=set(),
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
        now_epoch=now,
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_not_flagged_when_most_recent_fire_predates_install(local_tz):
    # Real incident this closes (2026-09-07): trustarch (Day=15) and
    # agentarch (Day=8), both installed 2026-09-03, were flagged as
    # "scheduled to fire 560-728h ago" -- but most_recent_scheduled_fire()
    # walks backward from `now` with no floor, so for a job installed mid-
    # month it finds the calendar match from BEFORE the job even existed
    # (the prior month's Day=15/Day=8). loaded-never-fired already applies
    # this floor via elapsed-since-install (see its own "not yet due"
    # exemption above); silent-job, added later as its calendar-exact
    # complement, never inherited it. A monthly job that has not yet
    # reached its first post-install fire is not overdue -- it is simply
    # not due yet, mirroring the class-level lesson (a job installed two
    # days ago is not overdue) at the calendar-exact layer.
    #
    # Day=15 monthly, installed 2026-09-03 06:00 local, "now" = 2026-09-07
    # 12:00 local. most_recent_scheduled_fire walks back and finds
    # 2026-08-15 06:10 -- a real calendar match, well past GRACE_SECONDS,
    # but it predates the 2026-09-03 install. Must NOT be flagged.
    installed = _local_epoch(2026, 9, 3, 6, 0, 0)
    now = _local_epoch(2026, 9, 7, 12, 0, 0)
    v = ha.check(
        ["com.oversight.csa.trustarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.trustarch"},
        table_cadences={"com.oversight.csa.trustarch": "06:10 15th of month"},
        plist_install_epochs={"com.oversight.csa.trustarch": installed},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.trustarch": {"Day": 15, "Hour": 6, "Minute": 10}
        },
    )
    assert not any(line.startswith("silent-job") for line in v)


def test_silent_job_still_flagged_when_fire_after_install_is_missed(local_tz):
    # Paired positive control for the fix above: once a job's OWN first
    # post-install fire has genuinely passed with no heartbeat, silent-job
    # must still catch it -- the install-time floor narrows a false
    # positive, it must never blanket-suppress the real defect this check
    # exists to find.
    #
    # Same Day=15 monthly job, installed BEFORE its own fire date this time
    # (2026-08-20), with "now" well past the 2026-09-15 fire.
    installed = _local_epoch(2026, 8, 20, 6, 0, 0)
    now = _local_epoch(2026, 9, 20, 12, 0, 0)
    v = ha.check(
        ["com.oversight.csa.trustarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.trustarch"},
        table_cadences={"com.oversight.csa.trustarch": "06:10 15th of month"},
        plist_install_epochs={"com.oversight.csa.trustarch": installed},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.trustarch": {"Day": 15, "Hour": 6, "Minute": 10}
        },
    )
    assert any(line.startswith("silent-job") and "trustarch" in line for line in v)


def test_silent_job_flagged_when_install_epoch_unknown(local_tz):
    # No plist_install_epochs entry for this label -- "cannot determine
    # install time" degrades to the OLD, conservative behavior (flag it),
    # exactly like loaded-never-fired's own fallback when install/cadence
    # data is unavailable. This is what keeps a plist-install-epoch read
    # failure from silently exempting a genuinely-overdue job.
    now = _local_epoch(2026, 9, 2, 12, 0, 0)
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.testarch"},
        table_cadences={"com.oversight.csa.testarch": "06:10 1st of month"},
        plist_install_epochs={},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.testarch": {"Day": 1, "Hour": 6, "Minute": 10}
        },
    )
    assert any(line.startswith("silent-job") and "testarch" in line for line in v)


def test_silent_job_daily_job_flagged_when_hour_minute_only_rule_passed(local_tz):
    # A daily job (StartCalendarInterval carries only Hour/Minute -- see
    # com.oversight.csa.daily.plist) that's been silent for 3 days is
    # flagged, exercising the "no Day/Weekday key -> matches every day"
    # normalization path.
    now = _local_epoch(2026, 9, 4, 12, 0, 0)
    installed = now - (3 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.daily"},
        table_cadences={"com.oversight.csa.daily": "05:10 daily"},
        plist_install_epochs={"com.oversight.csa.daily": installed},
        now_epoch=now,
        plist_calendar_intervals={"com.oversight.csa.daily": {"Hour": 5, "Minute": 10}},
    )
    assert any(line.startswith("silent-job") and "daily" in line for line in v)


def test_silent_job_weekday_array_rule_matches_correct_weekday(local_tz):
    # An array of dicts (e.g. loop's five-weekday StartCalendarInterval) --
    # each dict is OR'd; a weekday-only rule must match the corresponding
    # ISO weekday and no other, exercising _normalize_calendar_rules' list
    # branch and _rule_matches' Weekday%7 normalization.
    # 2026-09-12 is a Saturday (isoweekday()==6); Weekday=1 in this repo's
    # plists means Monday (see com.oversight.csa.launchdir's "07:10 Mon").
    # No Mon-Fri rule matches Saturday itself, so the most recent match is
    # Friday's 22:10 fire (Weekday=5), well over 24h before 'now' -- well
    # past the 6h grace window.
    now = _local_epoch(2026, 9, 12, 23, 0, 0)
    installed = now - (10 * 24 * 3600)
    v = ha.check(
        ["com.oversight.csa.loop"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.csa.loop"},
        table_cadences={"com.oversight.csa.loop": "22:10 Mon–Fri"},
        plist_install_epochs={"com.oversight.csa.loop": installed},
        now_epoch=now,
        plist_calendar_intervals={
            "com.oversight.csa.loop": [
                {"Weekday": 1, "Hour": 22, "Minute": 10},
                {"Weekday": 2, "Hour": 22, "Minute": 10},
                {"Weekday": 3, "Hour": 22, "Minute": 10},
                {"Weekday": 4, "Hour": 22, "Minute": 10},
                {"Weekday": 5, "Hour": 22, "Minute": 10},
            ]
        },
    )
    assert any(line.startswith("silent-job") and "loop" in line for line in v)


# --------------------------------------------------------------------------
# most_recent_scheduled_fire / _normalize_calendar_rules / _rule_matches /
# _read_plist_calendar_interval — the pure calendar-exact primitives behind
# the silent-job check above.
# --------------------------------------------------------------------------


def test_normalize_calendar_rules_single_dict():
    assert ha._normalize_calendar_rules({"Day": 1}) == [{"Day": 1}]


def test_normalize_calendar_rules_list_of_dicts():
    rules = [{"Weekday": 1}, {"Weekday": 2}]
    assert ha._normalize_calendar_rules(rules) == rules


def test_normalize_calendar_rules_none_on_bad_shapes():
    assert ha._normalize_calendar_rules(None) is None
    assert ha._normalize_calendar_rules("nope") is None
    assert ha._normalize_calendar_rules([]) is None
    assert ha._normalize_calendar_rules([1, 2]) is None
    assert ha._normalize_calendar_rules(42) is None


def test_rule_matches_absent_fields_match_everything():
    dt = datetime(2026, 9, 1, 6, 10, tzinfo=timezone.utc)
    assert ha._rule_matches({}, dt) is True
    assert ha._rule_matches({"Hour": 6}, dt) is True
    assert ha._rule_matches({"Hour": 7}, dt) is False


def test_rule_matches_weekday_zero_and_seven_both_mean_sunday():
    # 2026-09-06 is a Sunday.
    dt = datetime(2026, 9, 6, 6, 10, tzinfo=timezone.utc)
    assert ha._rule_matches({"Weekday": 0}, dt) is True
    assert ha._rule_matches({"Weekday": 7}, dt) is True
    assert ha._rule_matches({"Weekday": 1}, dt) is False  # Monday, not this day


def test_rule_matches_day_of_month():
    dt = datetime(2026, 9, 15, 6, 10, tzinfo=timezone.utc)
    assert ha._rule_matches({"Day": 15}, dt) is True
    assert ha._rule_matches({"Day": 1}, dt) is False


def test_most_recent_scheduled_fire_hour_minute_only_finds_yesterday_or_today(local_tz):
    now = _local_epoch(2026, 9, 4, 3, 0, 0)  # before today's 05:10 LOCAL
    fire = ha.most_recent_scheduled_fire({"Hour": 5, "Minute": 10}, now)
    assert fire is not None
    fire_dt = datetime.fromtimestamp(fire)  # local, matching the function's own frame
    assert fire_dt == datetime(2026, 9, 3, 5, 10)  # yesterday's fire, LOCAL
    # Falsifiability: the UTC-framed (buggy) answer for this same now_epoch
    # would differ by the zone offset -- confirm the two are NOT equal.
    utc_framed_wrong_answer = datetime(2026, 9, 3, 5, 10, tzinfo=timezone.utc).timestamp()
    assert fire != utc_framed_wrong_answer


def test_most_recent_scheduled_fire_day_of_month_finds_last_months_fire(local_tz):
    now = _local_epoch(2026, 9, 15, 0, 0, 0)  # before Sept 1's window, LOCAL
    fire = ha.most_recent_scheduled_fire({"Day": 1, "Hour": 6, "Minute": 10}, now)
    assert fire is not None
    fire_dt = datetime.fromtimestamp(fire)
    assert fire_dt == datetime(2026, 9, 1, 6, 10)
    utc_framed_wrong_answer = datetime(2026, 9, 1, 6, 10, tzinfo=timezone.utc).timestamp()
    assert fire != utc_framed_wrong_answer


def test_most_recent_scheduled_fire_returns_none_on_bad_interval():
    now = datetime.now(timezone.utc).timestamp()
    assert ha.most_recent_scheduled_fire(None, now) is None
    assert ha.most_recent_scheduled_fire("nope", now) is None
    assert ha.most_recent_scheduled_fire([], now) is None


def test_most_recent_scheduled_fire_returns_none_on_bad_now_epoch():
    assert ha.most_recent_scheduled_fire({"Hour": 5, "Minute": 10}, None) is None
    assert ha.most_recent_scheduled_fire({"Hour": 5, "Minute": 10}, float("nan")) is None
    assert ha.most_recent_scheduled_fire({"Hour": 5, "Minute": 10}, "not a number") is None


def test_most_recent_scheduled_fire_dst_fall_back_ambiguous_hour_resolves_to_first_occurrence(
    local_tz,
):
    # 2026-11-01 America/New_York: DST ends at 2:00am EDT -> clocks fall
    # back to 1:00am EST, so LOCAL wall-clock 01:30 happens TWICE that day
    # (first at UTC-4/EDT, again an hour later at UTC-5/EST). A naive
    # datetime's own .timestamp() (what most_recent_scheduled_fire's
    # candidate.timestamp() call uses, per its own LOCAL-TIME CONTRACT
    # docstring) resolves an ambiguous naive time to fold=0 -- the FIRST
    # occurrence -- by Python's own documented default. Pinning that choice
    # deliberately here (rather than leaving it implicit) so a future
    # change to fold handling shows up as a failing test, not a silent
    # behavior change.
    now = _local_epoch(2026, 11, 1, 3, 0, 0)  # well after both occurrences
    fire = ha.most_recent_scheduled_fire({"Hour": 1, "Minute": 30}, now)
    assert fire is not None
    assert datetime.fromtimestamp(fire) == datetime(2026, 11, 1, 1, 30, 0)
    import zoneinfo

    tz = zoneinfo.ZoneInfo(local_tz)
    first_occurrence = datetime(2026, 11, 1, 1, 30, 0, tzinfo=tz, fold=0).timestamp()
    second_occurrence = datetime(2026, 11, 1, 1, 30, 0, tzinfo=tz, fold=1).timestamp()
    assert first_occurrence != second_occurrence  # sanity: this day IS ambiguous
    assert fire == first_occurrence  # pinned: fold=0, the EARLIER (EDT) instant
    assert fire != second_occurrence


def test_most_recent_scheduled_fire_dst_spring_forward_skipped_hour_normalizes_forward(local_tz):
    # 2026-03-08 America/New_York: DST begins at 2:00am EST -> clocks spring
    # forward to 3:00am EDT, so LOCAL wall-clock 02:30 never occurs that
    # day. The scan builds each day's candidates via naive-datetime
    # arithmetic (day.replace(...) + timedelta(minutes=N)) and matches
    # rule fields (Hour==2, Minute==30) against that NAIVE value directly
    # -- so a Hour=2/Minute=30 rule still "matches" the naive 02:30 value
    # even though it names a wall-clock instant that never really
    # occurred. Only AFTERWARD does `candidate.timestamp()` resolve that
    # naive value through the local zone, and for a skipped instant it
    # normalizes FORWARD to the equivalent real instant one hour later
    # (03:30) -- Python's own documented behavior for a non-existent naive
    # local time, never a raise. Pinned deliberately: the fire is found on
    # March 8 itself (not skipped/falling back to March 7), and reads back
    # as 03:30 local, not 02:30.
    now = _local_epoch(2026, 3, 8, 12, 0, 0)
    fire = ha.most_recent_scheduled_fire({"Hour": 2, "Minute": 30}, now)
    assert fire is not None
    assert datetime.fromtimestamp(fire) == datetime(2026, 3, 8, 3, 30, 0)


def test_read_plist_calendar_interval_reads_real_plist(tmp_path):
    import plistlib

    link_dir = tmp_path / "LaunchAgents"
    link_dir.mkdir()
    target = tmp_path / "real.plist"
    target.write_bytes(
        plistlib.dumps({"Label": "com.oversight.csa.daily", "StartCalendarInterval": {"Hour": 5, "Minute": 10}})
    )
    os.symlink(target, link_dir / "com.oversight.csa.daily.plist")
    interval = ha._read_plist_calendar_interval("com.oversight.csa.daily", str(link_dir))
    assert interval == {"Hour": 5, "Minute": 10}


def test_read_plist_calendar_interval_missing_file_returns_none(tmp_path):
    assert ha._read_plist_calendar_interval("com.oversight.csa.nope", str(tmp_path)) is None


def test_read_plist_calendar_interval_unparseable_returns_none(tmp_path):
    link_dir = tmp_path / "LaunchAgents"
    link_dir.mkdir()
    (link_dir / "com.oversight.csa.daily.plist").write_bytes(b"not a plist")
    assert ha._read_plist_calendar_interval("com.oversight.csa.daily", str(link_dir)) is None


def test_read_plist_calendar_interval_missing_key_returns_none(tmp_path):
    import plistlib

    link_dir = tmp_path / "LaunchAgents"
    link_dir.mkdir()
    target = tmp_path / "real.plist"
    target.write_bytes(plistlib.dumps({"Label": "com.oversight.csa.daily"}))
    os.symlink(target, link_dir / "com.oversight.csa.daily.plist")
    assert ha._read_plist_calendar_interval("com.oversight.csa.daily", str(link_dir)) is None


def test_launchctl_unavailable_flagged_and_skips_never_fired():
    v = ha.check(
        ["com.oversight.csa.testarch"],
        None,
        {},
        {},
        loaded_labels=None,
    )
    assert any(line.startswith("launchctl-unavailable") for line in v)
    assert not any(line.startswith("loaded-never-fired") for line in v)


def test_table_parse_error_skips_diffing_but_still_validates():
    hb = _plain_hb()
    del hb["cadence"]
    v = ha.check(
        None,
        "boom: no header",
        {"x": hb},
        {},
        loaded_labels={"com.oversight.csa.daily"},
    )
    assert any(line.startswith("table-parse-failed") for line in v)
    assert not any(line.startswith("unexpected-heartbeat") for line in v)
    assert not any(line.startswith("loaded-never-fired") for line in v)
    assert any(line.startswith("missing-keys") for line in v)


def test_heartbeats_dir_unreadable_short_circuits():
    v = ha.check(
        ["com.oversight.csa.daily"],
        None,
        {"__dir_error__": "cannot list /nope: PermissionError"},
        {},
        loaded_labels={"com.oversight.csa.daily"},
    )
    assert len(v) == 1
    assert v[0].startswith("heartbeats-dir-unreadable")


def test_heartbeat_unreadable_entry_flagged():
    v = ha.check([], None, {"broken": "ERROR: bad.json unparseable: JSONDecodeError"}, {}, set())
    assert any(line.startswith("heartbeat-unreadable") for line in v)


# --------------------------------------------------------------------------
# cadence_seconds (B5/N12)
# --------------------------------------------------------------------------


def test_cadence_seconds_daily():
    assert ha.cadence_seconds("05:10 daily") == ha.DAILY_CADENCE_SECONDS


def test_cadence_seconds_single_weekday_is_weekly():
    assert ha.cadence_seconds("07:10 Mon") == 7 * 24 * 3600.0
    assert ha.cadence_seconds("06:40 Wed") == 7 * 24 * 3600.0


def test_cadence_seconds_comma_list_worst_gap():
    # Fri -> Tue is the worst gap: Sat, Sun, Mon, Tue = 4 days.
    assert ha.cadence_seconds("06:10 Tue,Fri") == 4 * 24 * 3600.0


def test_cadence_seconds_weekday_range_worst_gap():
    # Fri -> Mon (the weekend) is the worst gap for a Mon-Fri job: 3 days.
    assert ha.cadence_seconds("22:10 Mon-Fri") == 3 * 24 * 3600.0
    assert ha.cadence_seconds("22:10 Mon–Fri") == 3 * 24 * 3600.0  # en dash


def test_cadence_seconds_of_month_is_monthly():
    assert ha.cadence_seconds("06:10 1st of month") == ha.MONTHLY_CADENCE_SECONDS
    assert ha.cadence_seconds("06:10 15th of month") == ha.MONTHLY_CADENCE_SECONDS


def test_cadence_seconds_unparseable_or_missing_returns_none():
    assert ha.cadence_seconds("whenever it feels like it") is None
    assert ha.cadence_seconds("") is None
    assert ha.cadence_seconds(None) is None
    assert ha.cadence_seconds("06:10 Tue,Someday") is None


# --------------------------------------------------------------------------
# _plist_install_epoch (B5/N12)
# --------------------------------------------------------------------------


def test_plist_install_epoch_reads_symlink_mtime(tmp_path):
    target = tmp_path / "real.plist"
    target.write_text("<plist/>")
    link_dir = tmp_path / "LaunchAgents"
    link_dir.mkdir()
    link = link_dir / "com.oversight.csa.daily.plist"
    os.symlink(target, link)
    epoch = ha._plist_install_epoch("com.oversight.csa.daily", str(link_dir))
    assert epoch == os.lstat(link).st_mtime


def test_plist_install_epoch_missing_returns_none(tmp_path):
    assert ha._plist_install_epoch("com.oversight.csa.nope", str(tmp_path)) is None


# --------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------


def test_read_heartbeats_skips_underscore_and_nonjson_files(tmp_path):
    (tmp_path / "real.json").write_text('{"job":"real"}')
    (tmp_path / "_install_probe.json").write_text('{"job":"probe"}')
    (tmp_path / "_disabled_window.jsonl").write_text("{}\n")
    (tmp_path / "notes.txt").write_text("hi")
    out = ha._read_heartbeats(str(tmp_path))
    assert set(out) == {"real"}


def test_read_heartbeats_dir_error():
    out = ha._read_heartbeats("/definitely/does/not/exist/anywhere")
    assert "__dir_error__" in out


def test_read_heartbeats_unparseable_file_reported_as_error(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    out = ha._read_heartbeats(str(tmp_path))
    assert isinstance(out["bad"], str) and out["bad"].startswith("ERROR:")


def test_log_times_uses_file_mtime_err_start_out_finish(tmp_path):
    import time

    logs = tmp_path
    err = logs / "mylabel.err.log"
    out = logs / "mylabel.out.log"
    err.write_text("")
    time.sleep(0.05)
    out.write_text("hi")
    start, finish = ha._log_times(str(logs), "mylabel")
    assert start == os.stat(err).st_mtime
    assert finish == os.stat(out).st_mtime
    assert start <= finish


def test_log_times_survives_a_stale_creation_time_via_mtime(tmp_path):
    # The exact live bug this fix closes: touching (rewriting) an old file
    # updates its mtime without changing its creation time. A log that has
    # persisted across many firings must still report a CURRENT start proxy.
    logs = tmp_path
    err = logs / "old.err.log"
    out = logs / "old.out.log"
    err.write_text("first firing, days ago")
    out.write_text("first firing, days ago")
    old_mtime = err.stat().st_mtime - 86400  # simulate a day-old first write
    os.utime(err, (old_mtime, old_mtime))
    os.utime(out, (old_mtime, old_mtime))
    # "today's" firing re-touches both files without recreating them.
    err.write_text("")
    out.write_text("today's run")
    start, finish = ha._log_times(str(logs), "old")
    assert start > old_mtime + 3600  # reflects TODAY's touch, not day-old creation
    assert finish > old_mtime + 3600


def test_log_times_falls_back_to_the_single_file_present(tmp_path):
    logs = tmp_path
    (logs / "onlyout.out.log").write_text("hi")
    start, finish = ha._log_times(str(logs), "onlyout")
    assert start is not None and start == finish

    (logs / "onlyerr.err.log").write_text("")
    start2, finish2 = ha._log_times(str(logs), "onlyerr")
    assert start2 is not None and start2 == finish2


def test_log_times_missing_files_returns_none_pair(tmp_path):
    start, finish = ha._log_times(str(tmp_path), "nope")
    assert (start, finish) == (None, None)


def test_launchctl_loaded_labels_parses_stdout(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "PID\tStatus\tLabel\n-\t0\tcom.oversight.csa.daily\n-\t0\tcom.apple.other\n"

    monkeypatch.setattr(ha.subprocess, "run", lambda *a, **k: FakeProc())
    labels = ha._launchctl_loaded_labels()
    assert labels == {"com.oversight.csa.daily"}


def test_launchctl_loaded_labels_none_on_exception(monkeypatch):
    def _boom(*a, **k):
        raise OSError("no launchctl")

    monkeypatch.setattr(ha.subprocess, "run", _boom)
    assert ha._launchctl_loaded_labels() is None


def test_launchctl_loaded_labels_none_on_nonzero_exit(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(ha.subprocess, "run", lambda *a, **k: FakeProc())
    assert ha._launchctl_loaded_labels() is None


def test_parse_epoch_handles_z_and_offset_and_garbage():
    assert ha._parse_epoch("2026-08-25T05:10:00Z") is not None
    assert ha._parse_epoch("2026-08-25T05:10:00-06:00") is not None
    assert ha._parse_epoch("not a timestamp") is None
    assert ha._parse_epoch(None) is None
    assert ha._parse_epoch("") is None


# --------------------------------------------------------------------------
# main() / _gather()
# --------------------------------------------------------------------------


def test_gather_reads_the_real_inputs(tmp_path):
    doc = tmp_path / "install.md"
    doc.write_text(_TABLE_DOC)
    hb_dir = tmp_path / "heartbeats"
    hb_dir.mkdir()
    (hb_dir / "com.oversight.csa.daily.json").write_text(
        __import__("json").dumps(_daily_hb())
    )
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    launch_agents_dir = tmp_path / "LaunchAgents"  # deliberately absent — hermetic
    (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        heartbeats,
        log_times,
        plist_epochs,
        plist_calendar_intervals,
        wheel_granted_tools,
        wheel_history_records,
    ) = ha._gather(str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir))
    assert table_error is None
    assert "com.oversight.csa.daily" in table_labels
    assert table_cadences["com.oversight.csa.daily"] == "05:10 daily"
    assert table_expected_states["com.oversight.csa.daily"] == "loaded"
    assert "com.oversight.csa.daily" in heartbeats
    assert "com.oversight.csa.daily" in log_times
    assert plist_epochs == {}  # no LaunchAgents dir present to stat
    assert plist_calendar_intervals == {}  # no LaunchAgents dir present to read


def test_main_prints_and_always_exits_zero(tmp_path, monkeypatch):
    doc = tmp_path / "install.md"
    doc.write_text(_TABLE_DOC)
    hb_dir = tmp_path / "heartbeats"
    hb_dir.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    launch_agents_dir = tmp_path / "LaunchAgents"
    monkeypatch.setattr(ha, "_launchctl_loaded_labels", lambda: None)
    rc = ha.main(
        [str(ha.__file__), str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir)]
    )
    assert rc == 0


def test_main_subprocess_exits_zero_even_on_bad_doc(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(ha.__file__)),
            str(tmp_path / "nope.md"),
            str(tmp_path),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "violation(s)" in proc.stdout


# --------------------------------------------------------------------------
# check() — job-failed (THE ISSUE WHEEL plan, WS1-B.1 / Phase B item 1)
# --------------------------------------------------------------------------


def test_job_failed_flagged_for_the_exact_agency_fixture():
    # The EXACT Agency heartbeat that motivated this check (plan F3): exit 0
    # and a FRESH finished_at (so every OTHER liveness check reads it as
    # healthy) while only the free-text summary says the session died
    # without a truthful END write. No `status` field at all (predates this
    # commit). This is the RED condition job-failed exists to close.
    hb = {
        "job": "com.oversight.wheel.agency",
        "started_at": "2026-09-19T04:40:02Z",
        "finished_at": "2026-09-19T04:40:36Z",
        "exit": 0,
        "cadence": "22:40 Mon-Fri",
        "summary": "WRAPPER: claude process exited (code=0) without a truthful END heartbeat",
    }
    v = ha.check([], None, {"com.oversight.wheel.agency": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("job-failed")]
    assert len(hits) == 1
    assert "com.oversight.wheel.agency" in hits[0]


def test_job_failed_paired_control_healthy_heartbeat_not_flagged():
    # PAIRED CONTROL for the Agency fixture above: a genuinely healthy
    # heartbeat (status: "ok", exit 0, no WRAPPER: prefix) must never flag.
    hb = _plain_hb(exit=0, summary="ok", status="ok")
    v = ha.check([], None, {"com.oversight.wheel.agency": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_flagged_when_status_is_failed():
    hb = _plain_hb(exit=0, summary="ok", status="failed")
    v = ha.check([], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set())
    assert any(line.startswith("job-failed") for line in v)


def test_job_failed_flagged_when_status_absent_and_exit_nonzero():
    hb = _plain_hb(exit=1, summary="something broke")
    assert "status" not in hb
    v = ha.check([], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set())
    assert any(line.startswith("job-failed") for line in v)


def test_job_failed_not_flagged_when_status_ok_even_with_nonzero_exit():
    # status is the authoritative signal once present -- a stray nonzero
    # exit alongside status: "ok" must not override it.
    hb = _plain_hb(exit=1, summary="ok", status="ok")
    v = ha.check([], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_not_flagged_when_status_skipped_quota():
    hb = _plain_hb(exit=70, summary="WRAPPER: skipped - quota", status="skipped-quota")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_not_flagged_when_status_skipped_disabled():
    # GH #4767: the wheel wrapper's kill-switch skip is a sanctioned non-failure outcome, like
    # skipped-quota, even though its summary starts with the wrapper's "WRAPPER:" prefix.
    hb = _plain_hb(job="com.oversight.wheel.csa", exit=0, status="skipped-disabled", hard_stop="1",
                   summary="WRAPPER: skipped — kill switch ~/.claude/schedules/DISABLED is present; "
                           "claude was not launched (wrapper-enforced, GH #4767).")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_refusal_heartbeat_is_flagged_job_failed():
    # GH #4767: a launch-context refusal (status failed, exit 79, typed hard_stop) IS a failure.
    hb = _plain_hb(job="com.oversight.wheel.csa", exit=79, status="failed", hard_stop="3-not-enforcing",
                   summary="WRAPPER: refused before launch — 3-not-enforcing: x; claude was not launched (GH #4767).")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert any(line.startswith("job-failed: com.oversight.wheel.csa.json") for line in v), v


def _skip_hb_and_logs(tmp_path, out_mtime_offset):
    label = "com.oversight.wheel.csa"
    t0 = time.time() - 60
    hb = _plain_hb(job=label, exit=0, status="skipped-disabled", hard_stop="1",
                   started_at=_iso(datetime.fromtimestamp(t0, timezone.utc)),
                   finished_at=_iso(datetime.fromtimestamp(t0 + 2, timezone.utc)),
                   summary="WRAPPER: skipped — kill switch present; claude was not launched.")
    err = tmp_path / f"{label}.err.log"
    out = tmp_path / f"{label}.out.log"
    err.write_text("WRAPPER: skipped-disabled (global)\n")
    out.write_text("WRAPPER: skipped-disabled (global)\n")
    os.utime(err, (t0, t0))
    os.utime(out, (t0 + 2 + out_mtime_offset, t0 + 2 + out_mtime_offset))
    times = ha._log_times(str(tmp_path), label)
    return ha.check([], None, {label: hb}, {label: times}, loaded_labels=set())


def test_wrapper_skip_no_divergence_when_out_log_touched_at_finish(tmp_path):
    # GH #4767 round-2 B2: the wrapper prints its WRAPPER: line to out.log as it stamps
    # finished_at, so the finish proxy agrees with the heartbeat.
    v = _skip_hb_and_logs(tmp_path, out_mtime_offset=0)
    assert not any(line.startswith("timestamp-divergence") for line in v), v
    assert not any(line.startswith("job-failed") for line in v), v


def test_wrapper_skip_divergence_flagged_when_out_log_stale(tmp_path):
    # The falsifiable pair: an early exit that leaves out.log a day stale is exactly the
    # "possible fabricated timestamp" false alarm the WRAPPER: line prevents.
    v = _skip_hb_and_logs(tmp_path, out_mtime_offset=-86400)
    assert any(line.startswith("timestamp-divergence") and "finished_at" in line for line in v), v


def test_job_failed_exempt_when_inflight_start():
    hb = _started_hb(job="com.oversight.wheel.csa", exit=1)
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {"com.oversight.wheel.csa": hb},
        {},
        loaded_labels=set(),
    )
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_not_flagged_for_clean_zero_exit_no_status_non_wrapper_summary():
    # A legacy/session-authored END heartbeat with exit: 0 and an ordinary
    # (non-WRAPPER:) summary, with no status field at all, must NOT flag --
    # this is the "session wrote a normal clean END heartbeat before this
    # field existed" shape, not a failure.
    hb = _plain_hb(exit=0, summary="ran fine, nothing to report")
    assert "status" not in hb
    v = ha.check([], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_not_flagged_for_lock_refused_exit_75_with_status_failed_absent():
    # exit 75 with no status (a pre-this-commit lock-refused heartbeat) is
    # a non-zero exit with no status -- job-failed DOES fire for it (any
    # non-zero exit with no status is in scope), same as lock-refused fires
    # separately by name. The two checks are not mutually exclusive.
    hb = _plain_hb(exit=75, summary="WRAPPER: refused - held by pid 123")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert any(line.startswith("job-failed") for line in v)
    assert any(line.startswith("lock-refused") for line in v)


def test_job_failed_skipped_quota_streak_of_three_flagged():
    hb = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - quota",
        status="skipped-quota",
        consecutive_quota_skips=3,
    )
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("job-failed")]
    assert len(hits) == 1
    assert "3 consecutive" in hits[0]


def test_job_failed_skipped_quota_streak_of_two_not_flagged():
    hb = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - quota",
        status="skipped-quota",
        consecutive_quota_skips=2,
    )
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_skipped_quota_streak_missing_or_bad_type_not_flagged():
    hb = _plain_hb(exit=70, summary="WRAPPER: skipped - quota", status="skipped-quota")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)

    hb2 = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - quota",
        status="skipped-quota",
        consecutive_quota_skips="3",  # string, not int
    )
    v2 = ha.check([], None, {"com.oversight.wheel.csa": hb2}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v2)


# --------------------------------------------------------------------------
# check() — job-failed, skipped-throttle streak (#5922 fix round, BLOCKER 1)
# --------------------------------------------------------------------------


def test_job_failed_skipped_throttle_streak_of_two_not_flagged():
    # #5922 fix round item 1's paired tests: "not flagged at 2".
    hb = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - throttle",
        status="skipped-throttle",
        consecutive_throttle_skips=2,
    )
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_skipped_throttle_streak_of_three_flagged():
    # #5922 fix round item 1's paired tests: "flagged at 3", with the reason string the
    # coordinator specified verbatim.
    hb = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - throttle",
        status="skipped-throttle",
        consecutive_throttle_skips=3,
    )
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    hits = [line for line in v if line.startswith("job-failed")]
    assert len(hits) == 1
    assert "3 consecutive" in hits[0]
    assert "skipped-throttle" in hits[0]
    assert "server-side throttle, not quota; check concurrent load" in hits[0]


def test_job_failed_skipped_throttle_streak_cleared_by_a_later_ok():
    # #5922 fix round item 1's paired tests: "cleared by a later ok" -- check #9 reads only the
    # CURRENT heartbeat's own streak field, so a fresh "ok" heartbeat (the streak having ended)
    # carries no `consecutive_throttle_skips` at all and must never be flagged, regardless of how
    # long the streak was before it.
    hb = _plain_hb(exit=0, summary="did the job", status="ok")
    assert "consecutive_throttle_skips" not in hb
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_skipped_throttle_streak_missing_or_bad_type_not_flagged():
    hb = _plain_hb(exit=70, summary="WRAPPER: skipped - throttle", status="skipped-throttle")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)

    hb2 = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - throttle",
        status="skipped-throttle",
        consecutive_throttle_skips="3",  # string, not int
    )
    v2 = ha.check([], None, {"com.oversight.wheel.csa": hb2}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v2)


def test_job_failed_skipped_throttle_never_flagged_by_status_alone():
    # Mirrors test_job_failed_not_flagged_when_status_skipped_quota: skipped-throttle alone (no
    # streak field at all) is a sanctioned non-failure status, never flagged by itself.
    hb = _plain_hb(exit=70, status="skipped-throttle", summary="WRAPPER: skipped - throttle")
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


def test_job_failed_quota_and_throttle_streaks_are_independent():
    # A skipped-quota heartbeat carrying a (nonsensical, but defensively-checked) throttle counter
    # alongside it must never trip the throttle check, and vice versa -- check #9's quota branch
    # and throttle branch are gated strictly on `status_val`, never on which counters happen to be
    # present on the dict.
    hb = _plain_hb(
        exit=70,
        summary="WRAPPER: skipped - quota",
        status="skipped-quota",
        consecutive_quota_skips=1,
        consecutive_throttle_skips=5,  # must be ignored: status is skipped-quota, not skipped-throttle
    )
    v = ha.check([], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set())
    assert not any(line.startswith("job-failed") for line in v)


# --------------------------------------------------------------------------
# check() — unexpected-loaded (THE ISSUE WHEEL plan, WS1-B.3 / Phase B item 3)
# --------------------------------------------------------------------------


def test_unexpected_loaded_flagged_for_loaded_label_whose_table_state_is_not_loaded():
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.wheel.csa"},
        table_expected_states={"com.oversight.wheel.csa": "unloaded"},
    )
    hits = [line for line in v if line.startswith("unexpected-loaded")]
    assert len(hits) == 1
    assert "com.oversight.wheel.csa" in hits[0]
    assert "'unloaded'" in hits[0]


def test_unexpected_loaded_not_flagged_when_expected_state_is_loaded():
    # The exact-match case (expected_state == "loaded" and it IS loaded) is
    # the normal healthy state -- must never flag either direction.
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.wheel.csa"},
        table_expected_states={"com.oversight.wheel.csa": "loaded"},
    )
    assert not any(line.startswith("unexpected-loaded") for line in v)


def test_unexpected_loaded_not_flagged_when_not_actually_loaded():
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels=set(),
        table_expected_states={"com.oversight.wheel.csa": "unloaded"},
    )
    assert not any(line.startswith("unexpected-loaded") for line in v)


def test_unexpected_loaded_not_flagged_when_expected_state_missing():
    v = ha.check(
        ["com.oversight.wheel.csa"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.wheel.csa"},
        table_expected_states={},  # missing entirely
    )
    assert not any(line.startswith("unexpected-loaded") for line in v)


def test_expected_but_unloaded_still_fires_in_its_own_direction_alongside_unexpected_loaded():
    # Regression guard: adding unexpected-loaded must not disturb
    # expected-but-unloaded's own, opposite-direction behavior. Two
    # different labels, two different (and non-overlapping) violations.
    v = ha.check(
        ["com.oversight.wheel.csa", "com.oversight.wheel.agency"],
        None,
        {},
        {},
        loaded_labels={"com.oversight.wheel.csa"},
        table_expected_states={
            "com.oversight.wheel.csa": "unloaded",  # loaded anyway -> unexpected-loaded
            "com.oversight.wheel.agency": "loaded",  # not loaded -> expected-but-unloaded
        },
    )
    assert any(
        line.startswith("unexpected-loaded") and "com.oversight.wheel.csa" in line
        for line in v
    )
    assert any(
        line.startswith("expected-but-unloaded") and "com.oversight.wheel.agency" in line
        for line in v
    )


# --------------------------------------------------------------------------
# live-tree smoke run
# --------------------------------------------------------------------------


@requires_live_oversight_machine
def test_live_tree_smoke_run_does_not_crash_and_table_parses():
    (
        table_labels,
        table_cadences,
        table_expected_states,
        table_error,
        heartbeats,
        log_times,
        plist_epochs,
        plist_calendar_intervals,
        wheel_granted_tools,
        wheel_history_records,
    ) = ha._gather(ha.DEFAULT_INSTALL_DOC, ha.DEFAULT_HEARTBEATS_DIR, ha.DEFAULT_LOGS_DIR)
    # The real oversight_install.md §2 table must parse cleanly today. Regression guard for the
    # round-4 blocker: a table row accidentally wrapped/hard-broken across physical lines makes
    # parse_job_table() stop at the first non-'|' continuation line, silently dropping every
    # subsequent job from the expected set (a genuinely dead job's missing heartbeat then goes
    # undetected). Asserting only ONE label's presence stayed green through exactly that break, so
    # assert the FULL expected label set here, derived from the real
    # schedules/com.oversight.*.plist files on disk rather than a hardcoded count.
    # Widened from "com.oversight.csa.*.plist" to "com.oversight.*.plist" (2026-09-07,
    # agency-lcw incident): the live tree now also carries
    # com.oversight.agency.lcw.plist, correctly listed in oversight_install.md's own
    # §2 table — the CSA-prefix-only glob predates multi-app schedules and made this
    # assertion fail on a real, correctly-configured job that simply isn't CSA's.
    assert table_error is None
    schedules_dir = Path(ha.DEFAULT_HEARTBEATS_DIR).parent
    plist_labels = {
        p.stem for p in schedules_dir.glob("com.oversight.*.plist")
    }
    assert plist_labels, "expected at least one com.oversight.*.plist on disk"
    table_label_set = set(table_labels)
    assert table_label_set == plist_labels, (
        f"oversight_install.md's job table must list exactly the jobs with a real plist: "
        f"table has {sorted(table_label_set)}, plists have {sorted(plist_labels)}"
    )
    # Regression guard: a mangled cadence cell (e.g. "22:10 M-F" instead of a parseable form) can
    # leave the label set intact while cadence_seconds() silently returns None for that job, which
    # makes heartbeat_audit.py skip the stale-start check for it with the label-set guard above
    # staying green. Every table label must have a parseable cadence.
    assert [label for label in table_labels if ha.cadence_seconds(table_cadences[label]) is None] == []
    assert table_labels and "com.oversight.csa.daily" in table_labels
    loaded_labels = ha._launchctl_loaded_labels()
    violations = ha.check(
        table_labels,
        table_error,
        heartbeats,
        log_times,
        loaded_labels,
        table_cadences=table_cadences,
        plist_install_epochs=plist_epochs,
        now_epoch=time.time(),
        plist_calendar_intervals=plist_calendar_intervals,
    )
    assert isinstance(violations, list)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("every 120s (`StartInterval`, not a calendar job)", 120.0),
        ("every 5 min", 300.0),
        ("every 2h", 7200.0),
        ("Every 30 seconds", 30.0),
        ("every 0s", None),
        ("every s", None),
    ],
)
def test_cadence_seconds_start_interval_jobs(text, expected):
    """A launchd StartInterval job's table cadence is a fixed period, and its
    worst-case gap is exactly that period. A non-positive or unit-less
    period is unclassifiable (None), never zero."""
    assert ha.cadence_seconds(text) == expected


def test_cadence_seconds_interval_grammar_leaves_calendar_cadences_unchanged():
    assert ha.cadence_seconds("05:10 daily") == ha.DAILY_CADENCE_SECONDS
    assert ha.cadence_seconds("everyday") is None


@pytest.mark.parametrize(
    "text", ["every 5 months", "every 5 ms", "every 1.5h", "every 120", "run every 120s", "every \u0661\u0662\u0660s"]
)
def test_cadence_seconds_interval_grammar_rejects_non_interval_text(text):
    """The `^` anchor, the `\\b` unit boundary and ASCII digits carry real
    weight: none of these is a StartInterval period."""
    assert ha.cadence_seconds(text) is None


# --------------------------------------------------------------------------
# check() \u2014 wheel-grant-contradiction (WS14-S1, item 1c, GH #4767)
# --------------------------------------------------------------------------

_WHEEL_TOOLS = {"bash", "read", "write", "workflow", "taskoutput", "taskstop", "pushnotification", "toolsearch"}


def test_wheel_grant_contradiction_flags_workflow_tool_unavailable_when_workflow_is_granted():
    hb = _plain_hb(job="com.oversight.wheel.csa", degraded_reason="workflow-tool-unavailable")
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
    )
    hits = [line for line in v if line.startswith("wheel-grant-contradiction")]
    assert len(hits) == 1
    assert "workflow" in hits[0].lower()


def test_wheel_grant_contradiction_not_flagged_for_an_ungranted_tool():
    # "carrier-tool-unavailable" names a tool that is NOT in wheel_launch_context.TOOLS -- a
    # genuine, real grant gap, not a contradiction; this must never be flagged.
    hb = _plain_hb(job="com.oversight.wheel.csa", degraded_reason="carrier-tool-unavailable")
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
    )
    assert not any(line.startswith("wheel-grant-contradiction") for line in v)


def test_wheel_grant_contradiction_not_flagged_for_non_wheel_label():
    # Same degraded_reason shape, but a non-wheel job label -- the check is wheel-labels-only.
    hb = _plain_hb(job="com.oversight.csa.daily", degraded_reason="workflow-tool-unavailable")
    v = ha.check(
        [], None, {"com.oversight.csa.daily": hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
    )
    assert not any(line.startswith("wheel-grant-contradiction") for line in v)


def test_wheel_grant_contradiction_skipped_when_grant_set_unreadable():
    # wheel_granted_tools=None (grant set unknown, e.g. wheel_launch_context.py import failed) --
    # "cannot determine" must never be treated as a contradiction.
    hb = _plain_hb(job="com.oversight.wheel.csa", degraded_reason="workflow-tool-unavailable")
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set(),
        wheel_granted_tools=None,
    )
    assert not any(line.startswith("wheel-grant-contradiction") for line in v)


def test_wheel_grant_contradiction_not_flagged_when_no_degraded_reason():
    hb = _plain_hb(job="com.oversight.wheel.csa")
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
    )
    assert not any(line.startswith("wheel-grant-contradiction") for line in v)


def test_wheel_grant_contradiction_found_in_history_line_after_live_heartbeat_overwritten():
    """The 03:30 retry slot overwrites the primary slot's own live heartbeat before the 05:10
    audit ever runs -- so a primary-slot contradiction must still be found via the last-48h
    HISTORY records, even when the CURRENT live heartbeat (a clean retry run) shows nothing
    wrong at all."""
    clean_retry_hb = _plain_hb(job="com.oversight.wheel.csa", status="ok")  # no degraded_reason
    history_record = {
        "job": "com.oversight.wheel.csa",
        "degraded_reason": "workflow-tool-unavailable",
        "finished_at": _iso(datetime.now(timezone.utc) - timedelta(hours=20)),
    }
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": clean_retry_hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
        wheel_history_records={"com.oversight.wheel.csa": [history_record]},
    )
    hits = [line for line in v if line.startswith("wheel-grant-contradiction")]
    assert len(hits) == 1
    assert "history" in hits[0]


def test_gather_reads_wheel_launch_context_tools_for_the_real_repo():
    """End-to-end via the real _gather() IO path: wheel_launch_context.py exists in this repo, so
    the real TOOLS constant must be read successfully (not None) -- proves the try/except in
    _wheel_launch_context_tools() does not accidentally swallow a genuinely successful read."""
    (
        _table_labels,
        _table_cadences,
        _table_expected_states,
        _table_error,
        _heartbeats,
        _log_times,
        _plist_epochs,
        _plist_calendar_intervals,
        wheel_granted_tools,
        _wheel_history_records,
    ) = ha._gather(ha.DEFAULT_INSTALL_DOC, ha.DEFAULT_HEARTBEATS_DIR, ha.DEFAULT_LOGS_DIR)
    assert wheel_granted_tools is not None
    assert "workflow" in wheel_granted_tools
    assert "bash" in wheel_granted_tools


# --------------------------------------------------------------------------
# check() / _gather() — fix round (WS14-S1 item 1c, GH #4767): items 3, 4, 5, 6
# --------------------------------------------------------------------------


def test_read_recent_history_records_48h_window_boundary(tmp_path):
    """Item 3: an IO-level test of the 48h window itself. A record 20h old is INSIDE the window
    (kept); a record 50h old is OUTSIDE it (dropped)."""
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    now = datetime.now(timezone.utc)
    recent = {
        "job": "com.oversight.wheel.csa",
        "finished_at": _iso(now - timedelta(hours=20)),
        "degraded_reason": "workflow-tool-unavailable",
    }
    old = {
        "job": "com.oversight.wheel.csa",
        "finished_at": _iso(now - timedelta(hours=50)),
        "degraded_reason": "workflow-tool-unavailable",
    }
    path = history_dir / "com.oversight.wheel.csa.jsonl"
    path.write_text(__import__("json").dumps(old) + "\n" + __import__("json").dumps(recent) + "\n")

    records = ha._read_recent_history_records(
        str(history_dir), "com.oversight.wheel.csa", now.timestamp(), ha.WHEEL_GRANT_CONTRADICTION_WINDOW_SECONDS
    )
    finished_ats = {r.get("finished_at") for r in records}
    assert recent["finished_at"] in finished_ats
    assert old["finished_at"] not in finished_ats
    assert len(records) == 1


def test_gather_survives_wheel_launch_context_import_shadowed_to_none(monkeypatch):
    """Item 4: `_gather` (via `_wheel_launch_context_tools`) must never raise when
    `sys.modules["wheel_launch_context"]` is shadowed to `None` (Python's own documented shape for
    "this import is forbidden/unavailable") -- degrades to `wheel_granted_tools is None`, never an
    exception escaping `_gather`."""
    import sys as _sys

    monkeypatch.setitem(_sys.modules, "wheel_launch_context", None)
    tools = ha._wheel_launch_context_tools()
    assert tools is None


def test_gather_survives_wheel_launch_context_shadowed_none_end_to_end(tmp_path, monkeypatch):
    """Same shadow, exercised through the full `_gather()` IO path -- no exception, and
    `wheel_granted_tools is None` in the returned tuple."""
    import sys as _sys

    monkeypatch.setitem(_sys.modules, "wheel_launch_context", None)
    doc = tmp_path / "install.md"
    doc.write_text(_TABLE_DOC)
    hb_dir = tmp_path / "heartbeats"
    hb_dir.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    launch_agents_dir = tmp_path / "LaunchAgents"
    launch_agents_dir.mkdir()
    result = ha._gather(str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir))
    wheel_granted_tools = result[8]
    assert wheel_granted_tools is None


def test_gather_defaults_history_dir_from_fixture_heartbeats_dir_not_the_real_default(tmp_path):
    """Item 5: `_gather()` must default `history_dir` to `os.path.join(heartbeats_dir, "history")`
    -- NEVER the module-level `DEFAULT_HISTORY_DIR` (the real machine's history directory) -- when
    a caller passes a fixture `heartbeats_dir` and omits `history_dir` entirely. Proven by planting
    a contradicting history record ONLY under the fixture's own `<heartbeats_dir>/history/` and
    confirming it is found -- if `_gather` fell back to the REAL DEFAULT_HISTORY_DIR, this fixture
    record would never be read (unless coincidentally sharing a real machine history file, which a
    fresh tmp_path never does)."""
    doc = tmp_path / "install.md"
    doc.write_text(_TABLE_DOC)
    hb_dir = tmp_path / "heartbeats"
    hb_dir.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    launch_agents_dir = tmp_path / "LaunchAgents"
    launch_agents_dir.mkdir()

    # A wheel label's history lives under hb_dir/history/<label>.jsonl -- the fixture's OWN
    # heartbeats_dir, never DEFAULT_HISTORY_DIR.
    history_dir = hb_dir / "history"
    history_dir.mkdir()
    now = datetime.now(timezone.utc)
    record = {
        "job": "com.oversight.wheel.csa",
        "degraded_reason": "workflow-tool-unavailable",
        "finished_at": _iso(now - timedelta(hours=1)),
        "started_at": _iso(now - timedelta(hours=1, minutes=5)),
    }
    (history_dir / "com.oversight.wheel.csa.jsonl").write_text(__import__("json").dumps(record) + "\n")
    # A table row is needed so _gather()'s all_labels set includes this wheel label even with zero
    # live heartbeats -- reuse _TABLE_DOC's own labels is not guaranteed to include the wheel label,
    # so write a heartbeat file too (the simpler, always-correct path to get the label into scope).
    (hb_dir / "com.oversight.wheel.csa.json").write_text(
        __import__("json").dumps(_plain_hb(job="com.oversight.wheel.csa", status="ok"))
    )

    result = ha._gather(str(doc), str(hb_dir), str(logs_dir), str(launch_agents_dir), now_epoch=now.timestamp())
    wheel_history_records = result[9]
    found = wheel_history_records.get("com.oversight.wheel.csa", [])
    assert len(found) == 1
    assert found[0]["degraded_reason"] == "workflow-tool-unavailable"


def test_wheel_grant_contradiction_dedup_same_started_at_reported_once():
    """Item 6: a contradiction appearing in BOTH the live heartbeat and that SAME run's own history
    line (identical `started_at`) is reported exactly ONCE, keyed on `started_at` -- 1b appends
    every wrapper exit, including the ordinary finish that also becomes the live heartbeat, so this
    is the expected, common shape, not an edge case."""
    started_at = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
    live_hb = _plain_hb(job="com.oversight.wheel.csa", started_at=started_at, degraded_reason="workflow-tool-unavailable")
    same_run_history_record = dict(live_hb)  # identical started_at -- the SAME run's own line
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": live_hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
        wheel_history_records={"com.oversight.wheel.csa": [same_run_history_record]},
    )
    hits = [line for line in v if line.startswith("wheel-grant-contradiction")]
    assert len(hits) == 1


def test_wheel_grant_contradiction_dedup_different_started_at_reported_separately():
    """Item 6 (negative case): a DIFFERENT run's history line (distinct `started_at`) is a
    genuinely separate contradiction and must NOT be suppressed by the dedup -- two real
    contradictions on two different nights both get reported."""
    live_started_at = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
    other_started_at = _iso(datetime.now(timezone.utc) - timedelta(hours=20))
    live_hb = _plain_hb(job="com.oversight.wheel.csa", started_at=live_started_at, degraded_reason="workflow-tool-unavailable")
    different_run_history_record = {
        "job": "com.oversight.wheel.csa",
        "started_at": other_started_at,
        "degraded_reason": "workflow-tool-unavailable",
    }
    v = ha.check(
        [], None, {"com.oversight.wheel.csa": live_hb}, {}, loaded_labels=set(),
        wheel_granted_tools=_WHEEL_TOOLS,
        wheel_history_records={"com.oversight.wheel.csa": [different_run_history_record]},
    )
    hits = [line for line in v if line.startswith("wheel-grant-contradiction")]
    assert len(hits) == 2
