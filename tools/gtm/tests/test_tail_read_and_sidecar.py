"""Minor 17: _last_nonempty_line's tail-read correctness, and the sidecar
.ids index's rebuild-when-missing / stay-in-sync behavior.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402


# --------------------------------------------------------------------------
# _last_nonempty_line
# --------------------------------------------------------------------------


def test_last_nonempty_line_empty_file_returns_none(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert activity_log._last_nonempty_line(path) is None


def test_last_nonempty_line_missing_file_returns_none(tmp_path):
    assert activity_log._last_nonempty_line(tmp_path / "does_not_exist.jsonl") is None


def test_last_nonempty_line_single_line(tmp_path):
    path = tmp_path / "one.jsonl"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    assert activity_log._last_nonempty_line(path) == '{"a": 1}'


def test_last_nonempty_line_multiple_lines_returns_last(tmp_path):
    path = tmp_path / "many.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n', encoding="utf-8")
    assert activity_log._last_nonempty_line(path) == '{"a": 3}'


def test_last_nonempty_line_no_trailing_newline(tmp_path):
    path = tmp_path / "no_trailing.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}', encoding="utf-8")
    assert activity_log._last_nonempty_line(path) == '{"a": 2}'


def test_last_nonempty_line_forces_small_chunk_growth(tmp_path):
    """RED-check: hardcode chunk_size ridiculously small AND remove the
    growth loop and this fails to find the last line at all on a file
    bigger than one chunk. Uses a tiny chunk_size directly to force at
    least 2 growth iterations without needing an actual multi-MB fixture."""
    lines = [json.dumps({"n": i}) for i in range(50)]
    text = "\n".join(lines) + "\n"
    path = tmp_path / "grown.jsonl"
    path.write_text(text, encoding="utf-8")
    # chunk_size=8 is smaller than most individual lines, forcing the
    # while-loop to grow its read window multiple times before it can find
    # a full line boundary.
    assert activity_log._last_nonempty_line(path, chunk_size=8) == lines[-1]


def test_last_nonempty_line_matches_old_whole_file_read(tmp_path):
    """Parity check: the new tail-read must agree with the old
    _raw_lines(path)[-1] approach on real chained content."""
    path = tmp_path / "parity.jsonl"
    entries = [{"id": f"A{i:04d}", "v": i} for i in range(30)]
    with open(path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, sort_keys=True) + "\n")
    old_last = activity_log._raw_lines(path)[-1]
    new_last = activity_log._last_nonempty_line(path)
    assert new_last == old_last


# --------------------------------------------------------------------------
# sidecar .ids index
# --------------------------------------------------------------------------


def test_sidecar_missing_falls_back_to_full_scan_and_rebuilds(tmp_path):
    """RED-check: remove the _rebuild_ids_sidecar call in load_existing_ids
    and a pre-existing trail file (written before the sidecar mechanism
    existed) would be rescanned on EVERY future run instead of just once."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"
    trail_path.write_text(
        json.dumps({"tool_use_id": "tu_legacy_1"}) + "\n" + json.dumps({"tool_use_id": "tu_legacy_2"}) + "\n",
        encoding="utf-8",
    )
    sidecar = htt._ids_sidecar_path(trail_path)
    assert not sidecar.exists()

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_legacy_1", "tu_legacy_2"}
    assert sidecar.exists()
    # #20: the sidecar's first line is now a header ({"size":..., "lines":...});
    # the ids follow it.
    _header, sidecar_ids = htt._read_sidecar_header_and_ids(sidecar)
    assert sidecar_ids == {"tu_legacy_1", "tu_legacy_2"}


def test_sidecar_used_on_second_call_without_rescanning_jsonl_when_unchanged(tmp_path, monkeypatch):
    """A sidecar that still matches the trail's current (size, line count)
    is trusted WITHOUT a rescan -- proved here by OBSERVATION (monkeypatch
    the full-scan fallback to raise, and confirm load_existing_ids still
    succeeds from the sidecar alone on a genuinely unchanged trail), not by
    asserting a stale read as correct.

    Lock-in-test fix: the prior version of this test replaced the trail's
    content with a DIFFERENT id of the same (size, line count) shape and
    asserted load_existing_ids returned the STALE {'tu_1'} -- that made the
    drift check's known blind spot (a same-shape overwrite goes undetected,
    since the header only compares size+lines, never content) into asserted
    INTENDED behavior. If the drift check is later strengthened (e.g. a
    last-line hash), that fix would have broken this test even though it is
    an improvement. See _load_ids_from_sidecar's docstring for where that
    blind spot is now documented instead of locked in here."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"
    trail_path.write_text(json.dumps({"tool_use_id": "tu_1"}) + "\n", encoding="utf-8")
    htt.load_existing_ids([trail_path])  # builds the sidecar with a header

    def _boom(_path):
        raise AssertionError("the full JSONL scan fallback must never run when the sidecar is unchanged")

    monkeypatch.setattr(htt, "_scan_ids_from_jsonl", _boom)
    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_1"}  # answered from the sidecar alone -- the scan never ran


def test_sidecar_drift_triggers_rescan_on_size_mismatch(tmp_path):
    """#20's actual required test: blank the sidecar (or otherwise make it
    stale), then harvest again -- no duplicate tool_use_id, because drift
    is detected and the sidecar is rebuilt from a real scan rather than
    trusted blindly.

    RED-check: remove the header drift-check in _load_ids_from_sidecar
    (trust the sidecar unconditionally whenever it exists) and this fails
    -- the corrupted/blanked sidecar would report zero existing ids even
    though the trail file genuinely has one, and a subsequent harvest
    could re-append a duplicate."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"
    trail_path.write_text(json.dumps({"tool_use_id": "tu_1"}) + "\n", encoding="utf-8")
    htt.load_existing_ids([trail_path])  # builds a correct sidecar

    # Blank the sidecar (simulates a lagging sidecar / crash between the
    # two appends / an out-of-band overwrite).
    sidecar = htt._ids_sidecar_path(trail_path)
    sidecar.write_text("", encoding="utf-8")

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_1"}  # rebuilt from a real scan, not silently empty

    # The sidecar itself is now correctly rebuilt with a fresh header.
    header, sidecar_ids = htt._read_sidecar_header_and_ids(sidecar)
    assert header is not None
    assert sidecar_ids == {"tu_1"}


def test_sidecar_drift_via_out_of_band_trail_append_triggers_rescan(tmp_path):
    """#20's other named scenario: an out-of-band overwrite/append to
    TOOL_TRAIL.jsonl that never goes through _append_chained_trail (so the
    sidecar's header is now genuinely stale -- a real header exists, but
    its (size, lines) no longer matches the trail). RED-check: remove the
    `header.get("size") != current_size or header.get("lines") !=
    current_lines` comparison in _load_ids_from_sidecar (trust any header
    that merely EXISTS, regardless of whether it matches) and this test's
    assertion that "tu_2" is discovered fails -- the stale sidecar would
    report only {"tu_1"}, silently missing the out-of-band addition and
    risking a duplicate append of tu_2 on the next harvest."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"
    trail_path.write_text(json.dumps({"tool_use_id": "tu_1"}) + "\n", encoding="utf-8")
    htt.load_existing_ids([trail_path])  # builds a correct, matching sidecar

    # Out-of-band append -- goes straight to the JSONL, never through
    # _append_chained_trail, so the sidecar's header is now stale (real
    # header, wrong size/line count).
    with open(trail_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"tool_use_id": "tu_2"}) + "\n")

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_1", "tu_2"}  # rescanned, not silently stale at {"tu_1"}


def test_append_never_triggers_a_full_trail_rescan_via_trail_stats(tmp_path, monkeypatch):
    """#20 regression: the append path (_append_chained_trail ->
    _append_many_chained_trail_locked) must keep the sidecar header in
    step INCREMENTALLY, never by calling _trail_stats (a full read of the
    entire trail file counting every newline) on every single append --
    that call, made once per appended record, is what turned a single
    append against a 13.5 MB trail into an O(trail_size) operation
    (measured: 200 appends went from 0.03s to 3.59s, ~120x, all of it
    held under the company lock).

    RED-check: revert _append_many_chained_trail_locked's
    `header_trustworthy` branch to unconditionally call
    _rebuild_ids_sidecar (which calls _trail_stats) and this fails --
    _trail_stats is monkeypatched to raise, so any call to it on the
    append path blows up immediately."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    def _boom(_path):
        raise AssertionError("_trail_stats must never be called on the append fast path")

    # First append is allowed to build the sidecar from scratch (no prior
    # header exists yet -- that path legitimately needs one real scan).
    htt._append_chained_trail(trail_path, {"tool_use_id": "tu_a", "ts": "2026-01-01T00:00:00"})

    # From the SECOND append onward, a prior (matching) header exists, so
    # the fast incremental path must be taken -- _trail_stats must never
    # be reached. (load_existing_ids's own DRIFT-CHECK read is a separate,
    # pre-existing call path unrelated to this optimization and also
    # legitimately calls _trail_stats -- monkeypatching stays scoped to
    # just the append calls under test, not to reads made afterward.)
    monkeypatch.setattr(htt, "_trail_stats", _boom)
    htt._append_chained_trail(trail_path, {"tool_use_id": "tu_b", "ts": "2026-01-01T00:01:00"})
    htt._append_chained_trail(trail_path, {"tool_use_id": "tu_c", "ts": "2026-01-01T00:02:00"})

    _header, sidecar_ids = htt._read_sidecar_header_and_ids(htt._ids_sidecar_path(trail_path))
    assert sidecar_ids == {"tu_a", "tu_b", "tu_c"}

    monkeypatch.undo()
    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_a", "tu_b", "tu_c"}
    ok, reason = htt.verify_sidecar_matches_trail(trail_path)
    assert ok, reason


def test_sidecar_stays_in_sync_after_append(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_DIR", str(tmp_path / "claude_dir"))
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"

    htt._append_chained_trail(trail_path, {"tool_use_id": "tu_a", "ts": "2026-01-01T00:00:00"})
    htt._append_chained_trail(trail_path, {"tool_use_id": "tu_b", "ts": "2026-01-01T00:01:00"})

    sidecar = htt._ids_sidecar_path(trail_path)
    assert sidecar.exists()
    _header, sidecar_ids = htt._read_sidecar_header_and_ids(sidecar)
    assert sidecar_ids == {"tu_a", "tu_b"}

    # And the header must be accurate against the trail's ACTUAL final
    # stats (not stale from the first append).
    ok, reason = htt.verify_sidecar_matches_trail(trail_path)
    assert ok, reason

    ids = htt.load_existing_ids([trail_path])
    assert ids == {"tu_a", "tu_b"}
