"""Tests for doc_citation_check — the file:line citation drift sensor.

Spec source: the module's own docstring and #5843. The
behaviour asserted here is INTENDED behaviour, not a snapshot of what the
module currently prints: each test states the defect it would catch.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import doc_citation_check as dcc  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_index():
    """The bare-name index is a module-level cache; a test that builds it
    against one tmp root must not leak into the next."""
    dcc._BARE_NAME_INDEX = None
    yield
    dcc._BARE_NAME_INDEX = None


def _mkroot(tmp_path, docs: dict[str, str], sources: dict[str, str] | None = None):
    for rel, body in (sources or {}).items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    for rel, body in docs.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(tmp_path)


def test_a_citation_past_end_of_file_is_out_of_range(tmp_path):
    """THE CORE CASE. review-ladder.md cited record_review.py:840-881 when
    the function had moved to 1688; had the file been shorter than 840 this
    is the rule that would have caught it."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:500` for the detail\n"},
        sources={"mod.py": "\n".join(f"line{i}" for i in range(1, 11))},
    )
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["out-of-range"], findings
    assert "has 10 lines" in findings[0]["detail"]


def test_a_citation_within_range_is_not_a_finding(tmp_path):
    """PAIRED RECOVERY for the case above: a citation that still resolves
    must stay silent, or the sensor cries wolf on every healthy doc."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:3` for the detail\n"},
        sources={"mod.py": "\n".join(f"line{i}" for i in range(1, 11))},
    )
    assert dcc.check(root) == []


def test_a_citation_to_a_blank_line_is_empty_target(tmp_path):
    """Drift usually lands a citation in whitespace between functions. A real
    anchor is code or prose; blank means the target moved."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:2`\n"},
        sources={"mod.py": "def f():\n\n    return 1\n"},
    )
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["empty-target"], findings


def test_a_range_with_any_real_content_is_not_empty_target(tmp_path):
    """PAIRED RECOVERY: only an ENTIRELY blank range is drift. A range that
    spans a blank line plus real code is a normal, correct citation."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:1-3`\n"},
        sources={"mod.py": "def f():\n\n    return 1\n"},
    )
    assert dcc.check(root) == []


def test_a_missing_cited_file_is_reported(tmp_path):
    root = _mkroot(tmp_path, docs={"docs/a.md": "see `nope.py:3`\n"})
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["missing-file"], findings


def test_a_foreign_repo_path_is_never_reported(tmp_path):
    """A runtime doc citing a PRODUCT repo file is unverifiable here, not
    broken. Reporting it would be a false accusation and would bury the real
    findings — which is exactly what the first run of this module did."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `modules/estimate_engine_v3/generator.py:97`\n"},
    )
    assert dcc.check(root) == []


def test_archival_logs_are_not_scanned(tmp_path):
    """A point-in-time audit report cites the tree as it was on its own date.
    Its citations going stale is the record working, not a defect."""
    root = _mkroot(
        tmp_path,
        docs={"schedules/logs/audit_2026-09-01.md": "see `mod.py:500`\n"},
        sources={"mod.py": "one\n"},
    )
    assert dcc.check(root) == []


def test_an_explicit_path_overrides_the_archival_skip(tmp_path):
    """--paths means 'check exactly this'. A caller naming a log file has
    asked for it deliberately and must not be silently given nothing."""
    root = _mkroot(
        tmp_path,
        docs={"schedules/logs/audit_2026-09-01.md": "see `mod.py:500`\n"},
        sources={"mod.py": "one\n"},
    )
    doc = os.path.join(root, "schedules/logs/audit_2026-09-01.md")
    findings = dcc.check(root, [doc])
    assert [f["rule"] for f in findings] == ["out-of-range"], findings


def test_a_bare_filename_resolves_by_unique_basename(tmp_path):
    """Docs cite bare names constantly ('`daily_sweep.txt:13`'). Without this
    the sensor reported 139 false missing-file findings on its first run."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `target.txt:500`\n"},
        sources={"schedules/prompts/target.txt": "one\n"},
    )
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["out-of-range"], findings


def test_an_ambiguous_bare_filename_is_not_guessed_at(tmp_path):
    """Two files share the name -> resolving to one would make the line
    verdict meaningless. Report unresolvable instead of picking."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `dup.md:500`\n"},
        sources={"one/dup.md": "x\n", "two/dup.md": "y\n"},
    )
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["missing-file"], findings
    # The DETAIL must not claim the file "does not exist" — it plainly does,
    # twice over. A sensor that makes a false statement in its own output
    # teaches its reader to discount everything else it says.
    assert "2 files share the name dup.md" in findings[0]["detail"], findings


def test_an_unbackticked_citation_is_ignored(tmp_path):
    """Bare foo.py:12 in prose is too often a quoted log line or a shell
    snippet. Only a backticked citation is a citation."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "the traceback said mod.py:500 which is noise\n"},
        sources={"mod.py": "one\n"},
    )
    assert dcc.check(root) == []


def test_check_never_raises_on_an_unreadable_target(tmp_path):
    """This is a sensor. It must degrade to silence, never take down its
    caller — the daily sweep runs it unattended."""
    root = _mkroot(tmp_path, docs={"docs/a.md": "see `sub:3`\n"})
    (tmp_path / "sub").mkdir()
    assert dcc.check(root) == []


def test_strict_flag_controls_exit_code(tmp_path, capsys):
    """Report-only by default: a stale citation must never block a commit
    that may be entirely unrelated to it. --strict is opt-in."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:500`\n"},
        sources={"mod.py": "one\n"},
    )
    assert dcc.main(["--root", root]) == 0
    dcc._BARE_NAME_INDEX = None
    assert dcc.main(["--root", root, "--strict"]) == 1
    dcc._BARE_NAME_INDEX = None
    clean = _mkroot(tmp_path / "clean", docs={"docs/a.md": "no citations here\n"})
    assert dcc.main(["--root", clean, "--strict"]) == 0


def test_a_foreign_file_cited_by_shorthand_is_not_reported(tmp_path):
    """A doc that introduces `src/pkg/mod.py:10` and thereafter cites bare
    `mod.py:47` is citing the SAME foreign file. Reporting the shorthand as
    missing-file buried 43 of 46 live findings in one doc on the first run —
    85% of the sensor's total output, which is how a sensor becomes
    ignorable."""
    root = _mkroot(tmp_path, docs={"docs/a.md": "`src/pkg/mod.py:10` then `mod.py:47`\n"})
    assert dcc.check(root) == []


def test_shorthand_suppression_is_scoped_to_the_declaring_doc(tmp_path):
    """PAIRED RECOVERY / anti-over-reach: the suppression must NOT leak
    across files. A doc that never declared `mod.py` foreign still gets its
    unresolvable citation reported — otherwise one foreign doc could blind
    the sensor to a genuine rotted citation anywhere else."""
    root = _mkroot(
        tmp_path,
        docs={
            "docs/declares.md": "`src/pkg/mod.py:10`\n",
            "docs/other.md": "`mod.py:47`\n",
        },
    )
    findings = dcc.check(root)
    assert [(f["rule"], f["doc"]) for f in findings] == [("missing-file", "docs/other.md")], findings


def test_line_zero_is_out_of_range(tmp_path):
    """No file has a line 0. Before this it was silently a non-finding:
    `lines[-1:0]` is empty so the blankness rule missed it, and `0 > total`
    is False so the range rule missed it too."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:0`\n"},
        sources={"mod.py": "one\ntwo\n"},
    )
    findings = dcc.check(root)
    assert [f["rule"] for f in findings] == ["out-of-range"], findings


def test_line_one_is_not_out_of_range(tmp_path):
    """PAIRED RECOVERY for the case above."""
    root = _mkroot(
        tmp_path,
        docs={"docs/a.md": "see `mod.py:1`\n"},
        sources={"mod.py": "one\ntwo\n"},
    )
    assert dcc.check(root) == []
