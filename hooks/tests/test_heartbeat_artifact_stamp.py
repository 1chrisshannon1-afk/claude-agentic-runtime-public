"""Tests for heartbeat_artifact_stamp.py (#5055 — heartbeat artifact-path
hardening, closing the 2026-09-07 launchdir false-alarm incident).

Covers: extract_path_claims (extraction shapes), resolve_claim (resolution
precedence: workdir before $HOME/.claude, ~-expansion, nonexistent-claim
honesty), stamp()'s in-place summary rewrite + artifacts_verified shape,
WRAPPER:-prefix no-op, missing-file no-op, atomicity (crash-injection on
os.replace leaves the original file byte-identical), and exception-leaves-
intact (unparseable JSON input).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import heartbeat_artifact_stamp as has  # noqa: E402


def _write_hb(path: Path, **overrides: object) -> None:
    base = {
        "job": "com.oversight.csa.launchdir",
        "started_at": "2026-09-07T05:10:00Z",
        "finished_at": "2026-09-07T05:12:00Z",
        "exit": 0,
        "cadence": "weekly",
        "summary": "ok",
    }
    base.update(overrides)
    path.write_text(json.dumps(base), encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_path_claims
# ---------------------------------------------------------------------------


def test_extract_relative_claim_found():
    claims = has.extract_path_claims("wrote plans/csa_state_2026-09-07.html to disk")
    assert claims == ["plans/csa_state_2026-09-07.html"]


def test_extract_absolute_claim_left_alone():
    claims = has.extract_path_claims("wrote /Users/x/.claude/plans/x.html")
    assert claims == ["/Users/x/.claude/plans/x.html"]


def test_extract_ignores_url():
    claims = has.extract_path_claims("see https://example.com/report for details")
    assert claims == []


def test_extract_ignores_bare_word():
    claims = has.extract_path_claims("dropped 2/12 items, verdict ok")
    # "2/12" contains a "/" and is a real path-shaped token by this module's
    # own narrow rule (no notion of "looks numeric") — deliberately included
    # at the EXTRACTION layer, not a bug there: extract_path_claims only
    # judges SHAPE. The safety property this module actually provides lives
    # one layer up, in stamp()'s reality gate (B-1 fix, 2026-09-07): "2/12"
    # may be EXTRACTED here, but stamp() never rewrites it and never records
    # it in artifacts_verified, because it never resolves to a real file —
    # see test_stamp_prose_corruption_corpus_left_untouched below for the
    # end-to-end proof. (An earlier version of this comment claimed
    # "resolve_claim is what later reports it as non-existent" as if that
    # alone made the shape safe — false: resolve_claim always returns a
    # non-None `resolved` for a relative claim, so gating on "resolved is
    # not None" instead of `exists` is exactly what corrupted prose like
    # "dropped 2/5" in executed testing before this fix.)
    # Assert the bare prose word "ok" is NOT picked up (no "/", no leading "~").
    assert "ok" not in claims


def test_extract_multiple_claims():
    claims = has.extract_path_claims(
        "wrote reports/a.html and also reports/b.html for the run"
    )
    assert claims == ["reports/a.html", "reports/b.html"]


def test_extract_tilde_anchored_claim():
    claims = has.extract_path_claims("see ~/.claude/plans/x.html for the report")
    assert claims == ["~/.claude/plans/x.html"]


def test_extract_strips_trailing_sentence_punctuation():
    claims = has.extract_path_claims("wrote reports/a.html.")
    assert claims == ["reports/a.html"]


def test_extract_non_string_or_empty_returns_empty():
    assert has.extract_path_claims(None) == []  # type: ignore[arg-type]
    assert has.extract_path_claims("") == []


def test_extract_bare_slash_and_tilde_ignored():
    claims = has.extract_path_claims("nothing found in / or ~ here")
    assert claims == []


# ---------------------------------------------------------------------------
# resolve_claim
# ---------------------------------------------------------------------------


def test_resolve_workdir_hit_wins_over_home_claude(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "report.html").write_text("x", encoding="utf-8")

    fake_home_claude = tmp_path / "fakehome" / ".claude"
    fake_home_claude.mkdir(parents=True)
    (fake_home_claude / "report.html").write_text("y", encoding="utf-8")
    monkeypatch.setattr(has, "DEFAULT_CLAUDE_DIR", str(fake_home_claude))

    resolved, exists = has.resolve_claim("report.html", str(workdir))
    assert resolved == str(workdir / "report.html")
    assert exists is True


def test_resolve_falls_back_to_home_claude_when_workdir_misses(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()  # exists, but no report.html inside it

    fake_home_claude = tmp_path / "fakehome" / ".claude"
    fake_home_claude.mkdir(parents=True)
    (fake_home_claude / "report.html").write_text("y", encoding="utf-8")
    monkeypatch.setattr(has, "DEFAULT_CLAUDE_DIR", str(fake_home_claude))

    resolved, exists = has.resolve_claim("report.html", str(workdir))
    assert resolved == str(fake_home_claude / "report.html")
    assert exists is True


def test_resolve_tilde_expansion(monkeypatch, tmp_path):
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    (fake_home / "x.html").write_text("z", encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))

    resolved, exists = has.resolve_claim("~/x.html", None)
    assert resolved == os.path.join(str(fake_home), "x.html")
    assert exists is True


def test_resolve_absolute_claim_returned_as_is(tmp_path):
    abs_path = tmp_path / "abs.html"
    abs_path.write_text("z", encoding="utf-8")
    resolved, exists = has.resolve_claim(str(abs_path), None)
    assert resolved == str(abs_path)
    assert exists is True


def test_resolve_nonexistent_claim_not_rewritten_exists_false(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    fake_home_claude = tmp_path / "fakehome" / ".claude"
    fake_home_claude.mkdir(parents=True)
    monkeypatch.setattr(has, "DEFAULT_CLAUDE_DIR", str(fake_home_claude))

    resolved, exists = has.resolve_claim("ghost/report.html", str(workdir))
    assert exists is False
    # Still returns a best-effort absolute form (workdir-preferred), honestly
    # marked as not existing — but the claim itself is never silently dropped.
    assert resolved == str(workdir / "ghost" / "report.html")


def test_resolve_malformed_claim_returns_none_false():
    assert has.resolve_claim("", None) == (None, False)
    assert has.resolve_claim(None, None) == (None, False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# stamp() — in-place rewrite + artifacts_verified shape
# ---------------------------------------------------------------------------


def test_stamp_rewrites_relative_claim_to_absolute_in_summary(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "plans").mkdir()
    (workdir / "plans" / "csa_state_2026-09-07.html").write_text("x", encoding="utf-8")

    hb_path = tmp_path / "com.oversight.csa.launchdir.json"
    _write_hb(hb_path, summary="wrote plans/csa_state_2026-09-07.html to disk")

    ok = has.stamp(str(hb_path), str(workdir))
    assert ok is True

    data = json.loads(hb_path.read_text(encoding="utf-8"))
    expected_abs = str(workdir / "plans" / "csa_state_2026-09-07.html")
    assert expected_abs in data["summary"]
    assert "plans/csa_state_2026-09-07.html to disk" not in data["summary"].replace(expected_abs, "")


def test_stamp_artifacts_verified_shape(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "reports").mkdir()
    (workdir / "reports" / "report.html").write_text("x", encoding="utf-8")

    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="wrote reports/report.html")

    assert has.stamp(str(hb_path), str(workdir)) is True
    data = json.loads(hb_path.read_text(encoding="utf-8"))

    assert "artifacts_verified" in data
    assert isinstance(data["artifacts_verified"], list)
    assert len(data["artifacts_verified"]) == 1
    entry = data["artifacts_verified"][0]
    assert entry["claimed"] == "reports/report.html"
    assert entry["resolved"] == str(workdir / "reports" / "report.html")
    assert entry["exists"] is True


def test_stamp_multiple_claims_each_verified(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "reports").mkdir()
    (workdir / "reports" / "a.html").write_text("x", encoding="utf-8")
    # reports/b.html deliberately absent -- exercises a mixed
    # resolved/unresolved summary in one stamp() call.

    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="wrote reports/a.html and reports/b.html")

    assert has.stamp(str(hb_path), str(workdir)) is True
    data = json.loads(hb_path.read_text(encoding="utf-8"))
    claimed = {e["claimed"]: e for e in data["artifacts_verified"]}
    assert claimed["reports/a.html"]["exists"] is True
    # B-1 reality gate: a relative claim that does NOT resolve to an
    # existing file is skipped entirely -- never recorded, never rewritten.
    # reports/b.html never touched anything real, so it must not appear.
    assert "reports/b.html" not in claimed
    assert str(workdir / "reports" / "a.html") in data["summary"]
    assert "reports/b.html" in data["summary"]  # left untouched, not corrupted


def test_stamp_absolute_claim_in_summary_left_alone(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    abs_target = tmp_path / "already_absolute.html"
    abs_target.write_text("x", encoding="utf-8")

    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary=f"wrote {abs_target} to disk")

    assert has.stamp(str(hb_path), str(workdir)) is True
    data = json.loads(hb_path.read_text(encoding="utf-8"))
    assert str(abs_target) in data["summary"]
    entry = data["artifacts_verified"][0]
    assert entry["claimed"] == str(abs_target)
    assert entry["resolved"] == str(abs_target)
    assert entry["exists"] is True


# ---------------------------------------------------------------------------
# stamp() — B-1 reality gate: the prose-corruption corpus (dual-Opus review,
# 2026-09-07). Executed against real heartbeats, the PRE-FIX stamp() (gating
# the rewrite on "resolved is not None" rather than "exists") corrupted every
# one of these: "dropped 2/5" -> "dropped /Users/.../2/5"; "Clusters C/E"
# corrupted; "carried from 2026/09/01" corrupted; "(test_quality/history.jsonl"
# rewritten with the paren embedded; "~8h" recorded in artifacts_verified as
# a fake artifact. None of these denote a real file, so none should survive
# contact with the reality gate.
# ---------------------------------------------------------------------------


def test_stamp_prose_corruption_corpus_left_untouched(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "reports").mkdir()
    real_artifact = workdir / "reports" / "real_report.html"
    real_artifact.write_text("x", encoding="utf-8")

    summary = (
        "dropped 2/5 items; Clusters C/E flagged; carried from 2026/09/01; "
        "and/or n/a; ran with -v/--verbose; see (test_quality/history.jsonl "
        "for detail; job took ~8h; wrote reports/real_report.html to disk"
    )
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary=summary)

    ok = has.stamp(str(hb_path), str(workdir))
    assert ok is True

    data = json.loads(hb_path.read_text(encoding="utf-8"))
    new_summary = data["summary"]

    # The ONE real claim was rewritten to its absolute form.
    expected_abs = str(real_artifact)
    assert expected_abs in new_summary

    # Byte-diff everything else: removing only the real claim's rewritten
    # span from the new summary must reproduce the ORIGINAL summary's
    # remaining text untouched -- i.e. nothing else in the sentence was
    # rewritten, truncated, or otherwise mutated.
    original_without_real_claim = summary.replace("reports/real_report.html", "")
    new_without_real_claim = new_summary.replace(expected_abs, "")
    assert new_without_real_claim == original_without_real_claim

    # None of the prose fragments were recorded as artifacts either -- the
    # ~8h case explicitly named in the review as a "fake artifact" finding.
    claimed = {e["claimed"] for e in data["artifacts_verified"]}
    for prose_fragment in (
        "2/5",
        "C/E",
        "2026/09/01",
        "and/or",
        "n/a",
        "-v/--verbose",
        "(test_quality/history.jsonl",
        "~8h",
    ):
        assert prose_fragment not in claimed, f"{prose_fragment!r} was falsely recorded as an artifact"

    # Exactly one real artifact recorded.
    assert len(data["artifacts_verified"]) == 1
    entry = data["artifacts_verified"][0]
    assert entry["claimed"] == "reports/real_report.html"
    assert entry["resolved"] == expected_abs
    assert entry["exists"] is True


def test_stamp_all_prose_no_real_artifact_is_full_noop(tmp_path):
    # No real artifact anywhere in the summary -- every token is prose that
    # fails the reality gate, so stamp() must be a true no-op (never writes
    # just to record what it could not verify).
    workdir = tmp_path / "work"
    workdir.mkdir()
    summary = "dropped 2/5 items; Clusters C/E flagged; ran with -v/--verbose; ~8h total"
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary=summary)
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(workdir))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# stamp() — no-op shapes
# ---------------------------------------------------------------------------


def test_stamp_wrapper_prefix_is_noop(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="WRAPPER: claude process exited without a truthful END heartbeat")
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


def test_stamp_missing_file_is_noop(tmp_path):
    hb_path = tmp_path / "does_not_exist.json"
    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert not hb_path.exists()


def test_stamp_no_claims_found_is_noop(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="ok, nothing to report")
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


def test_stamp_non_string_summary_is_noop(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary=None)
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


def test_stamp_non_dict_json_is_noop(tmp_path):
    hb_path = tmp_path / "hb.json"
    hb_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# stamp() — atomicity + exception-leaves-intact
# ---------------------------------------------------------------------------


def test_stamp_atomicity_original_file_byte_identical_when_replace_fails(tmp_path, monkeypatch):
    """THE falsifying atomicity test: force os.replace to fail AFTER the temp
    file would have been written, and assert the ORIGINAL heartbeat file is
    byte-for-byte untouched -- mirrors settings_drift_guard's own
    test_atomic_write_leaves_old_content_intact_when_replace_fails, the one
    case that actually proves atomicity (the earlier no-op tests above all
    pass even with atomicity removed entirely)."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "reports").mkdir()
    (workdir / "reports" / "report.html").write_text("x", encoding="utf-8")

    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="wrote reports/report.html")
    original_bytes = hb_path.read_bytes()

    monkeypatch.setattr(
        has.os,
        "replace",
        lambda *a, **k: (_ for _ in ()).throw(OSError("simulated replace failure")),
    )

    ok = has.stamp(str(hb_path), str(workdir))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes

    # No leftover temp file either.
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".hb.json.tmp.")]
    assert leftovers == []


def test_stamp_exception_leaves_file_intact_on_unparseable_json(tmp_path):
    hb_path = tmp_path / "hb.json"
    hb_path.write_text("{not valid json", encoding="utf-8")
    original_bytes = hb_path.read_bytes()

    ok = has.stamp(str(hb_path), str(tmp_path))
    assert ok is False
    assert hb_path.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# main() — CLI entry, always exit 0
# ---------------------------------------------------------------------------


def test_main_always_exits_zero_even_on_garbage_args():
    assert has.main(["heartbeat_artifact_stamp.py"]) == 0
    assert has.main(["heartbeat_artifact_stamp.py", "/nonexistent/hb.json", "/nonexistent/wd"]) == 0


def test_main_stamps_a_real_file(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "reports").mkdir()
    (workdir / "reports" / "report.html").write_text("x", encoding="utf-8")
    hb_path = tmp_path / "hb.json"
    _write_hb(hb_path, summary="wrote reports/report.html")

    rc = has.main(["heartbeat_artifact_stamp.py", str(hb_path), str(workdir)])
    assert rc == 0
    data = json.loads(hb_path.read_text(encoding="utf-8"))
    assert str(workdir / "reports" / "report.html") in data["summary"]
