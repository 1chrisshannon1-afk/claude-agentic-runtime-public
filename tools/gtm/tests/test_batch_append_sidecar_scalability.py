"""Major finding (scalability): a batch flush of N records into one trail
must read and write that trail's sidecar `.ids` index ONCE for the whole
batch, not once PER RECORD -- `_append_one_id_to_sidecar` (used by the old
one-record-at-a-time loop) reads and rewrites the ENTIRE sidecar on every
call, which is O(N x sidecar_size) for a batch of N.

Proven by call-count instrumentation (never a wall-clock threshold, which
flakes on a loaded machine): patch `_write_sidecar_with_header` to count
invocations and assert it is called exactly ONCE for a batch of many
records, plus a correctness check that every record landed and the
sidecar's final id set is exactly right.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402


def _record(tid: str, ts: str) -> dict:
    return {
        "tool_use_id": tid, "ts": ts, "session_id": "sess_1",
        "tool": "mcp__playwright-gtm__browser_click", "system": "google_ads",
    }


def test_batch_flush_writes_sidecar_once_not_once_per_record(tmp_path, monkeypatch):
    """RED-check: revert `_flush_locked` to loop calling
    `_append_chained_trail_locked` once per record (the pre-fix design)
    and this test fails -- `_write_sidecar_with_header` is called once
    PER RECORD (50 times for 50 records) instead of once for the whole
    batch."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    write_calls: list[int] = []
    real_write = activity_log._write_sidecar_with_header

    def counting_write(*args, **kwargs):
        write_calls.append(1)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(activity_log, "_write_sidecar_with_header", counting_write)
    monkeypatch.setattr(htt, "_write_sidecar_with_header", counting_write)

    n = 50
    records = [_record(f"tu_{i}", f"2026-01-01T00:{i:02d}:00") for i in range(n)]
    htt._append_many_chained_trail_locked(trail_path, records)

    assert len(write_calls) == 1, f"expected exactly 1 sidecar write for a {n}-record batch, got {len(write_calls)}"

    # Correctness: every record actually landed in the trail, and the
    # sidecar's id set is exactly right (not just "written once" -- a
    # fast-but-wrong implementation is still a regression).
    lines = trail_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == n

    sidecar = htt._ids_sidecar_path(trail_path)
    header, ids = activity_log._read_sidecar_header_and_ids(sidecar)
    assert header is not None
    current_size, current_lines = activity_log._trail_stats(trail_path)
    assert header.get("size") == current_size
    assert header.get("lines") == current_lines
    assert ids == {f"tu_{i}" for i in range(n)}


def test_batch_flush_via_flush_locked_writes_sidecar_once(tmp_path, monkeypatch):
    """Same property exercised through the real `_flush_locked` entry
    point (as a genuine harvest run would call it), including its
    idempotency re-filter against `all_trail_paths`."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    write_calls: list[int] = []
    real_write = activity_log._write_sidecar_with_header

    def counting_write(*args, **kwargs):
        write_calls.append(1)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(activity_log, "_write_sidecar_with_header", counting_write)
    monkeypatch.setattr(htt, "_write_sidecar_with_header", counting_write)

    n = 40
    candidates = [dict(_record(f"tu_{i}", f"2026-01-01T00:{i:02d}:00"), tool_use_id=f"tu_{i}") for i in range(n)]
    appended = htt._flush_locked(trail_path, candidates, [trail_path])
    assert appended == n
    assert len(write_calls) == 1, f"expected exactly 1 sidecar write, got {len(write_calls)}"


# --------------------------------------------------------------------------
# Major finding (regression fix): a drifted sidecar's fallback rebuild must
# scan the TRAIL for ground truth, never trust the drifted sidecar's own id
# set. Reproduces the exact crash sequence from the finding: append tu_a
# (sidecar in sync), write tu_b directly to the JSONL only (a crash between
# the trail append and the sidecar sync), then append tu_c (drift-triggered
# fallback). Before the fix, `_rebuild_ids_sidecar` was called with the
# drifted sidecar's OWN ids ({tu_a} at that point) plus tu_c -- silently
# dropping tu_b from the id set while writing a header that matches the
# trail's current (size, lines) exactly, so `check`'s drift detector could
# no longer see the problem either.
# --------------------------------------------------------------------------


def test_drifted_sidecar_fallback_scans_trail_not_the_drifted_sidecar_single(tmp_path):
    """Exercises the drift fallback through a SINGLE-record call site
    (`_append_chained_trail_locked`, the entry point tests/callers use to
    build up trail state one record at a time). `_append_chained_trail_locked`
    delegates to `_append_many_chained_trail_locked` (nit fix: the module
    no longer keeps a separate per-record sidecar-rewrite implementation
    with its own, independently-evolving drift fallback -- every trail
    write, single-record or batch, now goes through the ONE fallback this
    test and `..._batch` below both exercise), so this and the `..._batch`
    test below cover the same code path from two different call sites --
    kept as two tests because a regression that broke only one call
    site's way of reaching that path (e.g. a bad single-record wrapper)
    would otherwise go undetected.

    RED-check: revert `_append_many_chained_trail_locked`'s
    untrustworthy-header branch to seed `ids` from the drifted sidecar's
    own id set (`sidecar_ids`) instead of `_scan_ids_from_jsonl(path)` and
    this fails -- tu_b is missing from load_existing_ids, and
    verify_sidecar_matches_trail wrongly reports clean afterward."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    htt._append_chained_trail_locked(trail_path, _record("tu_a", "2026-01-01T00:00:00"))
    # Simulated crash: tu_b lands in the JSONL only, sidecar never synced.
    activity_log._append_chained(trail_path, _record("tu_b", "2026-01-01T00:01:00"))

    drifted_ok, _ = activity_log.verify_sidecar_matches_trail(trail_path)
    assert drifted_ok is False, "setup invariant: the sidecar must be genuinely drifted before the third append"

    # This append goes through the drift fallback (header no longer
    # matches the trail's actual on-disk size).
    htt._append_chained_trail_locked(trail_path, _record("tu_c", "2026-01-01T00:02:00"))

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_a", "tu_b", "tu_c"}, ids

    # `check`'s own drift detector must still be honest post-rebuild.
    ok, reason = activity_log.verify_sidecar_matches_trail(trail_path)
    assert ok is True, reason


def test_drifted_sidecar_fallback_scans_trail_not_the_drifted_sidecar_batch(tmp_path):
    """Same crash sequence through the batch append path
    (`_append_many_chained_trail_locked`, used by `_flush_locked`)."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    htt._append_chained_trail_locked(trail_path, _record("tu_a", "2026-01-01T00:00:00"))
    activity_log._append_chained(trail_path, _record("tu_b", "2026-01-01T00:01:00"))

    drifted_ok, _ = activity_log.verify_sidecar_matches_trail(trail_path)
    assert drifted_ok is False, "setup invariant: the sidecar must be genuinely drifted before the batch flush"

    htt._append_many_chained_trail_locked(
        trail_path,
        [_record("tu_c", "2026-01-01T00:02:00"), _record("tu_d", "2026-01-01T00:03:00")],
    )

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_a", "tu_b", "tu_c", "tu_d"}, ids

    ok, reason = activity_log.verify_sidecar_matches_trail(trail_path)
    assert ok is True, reason
