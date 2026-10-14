"""Tests for the optional pack field `legacy_workdirs` (company_schema.json):
a company's pre-migration working directories, read from its own private pack
so harvest_tool_trail never hardcodes a company path in runtime code.

Spec: company_schema.json `legacy_workdirs`: absolute or ~/ path strings, no
'..'; harvest_tool_trail adds their Claude Code project dirs to its default
transcript search. Every test uses tmp homes; never the real ~/.claude.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import company  # noqa: E402
import harvest_tool_trail as htt  # noqa: E402
from test_company_pack import _make_home, _minimal_pack  # noqa: E402


def test_legacy_workdirs_absolute_paths_validate(tmp_path):
    pack = _minimal_pack("acme", legacy_workdirs=[str(tmp_path / "old work"), "~/Desktop/Acme/old"])
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert ok, reasons


def test_legacy_workdirs_rejects_relative_and_dotdot_paths():
    pack = _minimal_pack("acme", legacy_workdirs=["relative/dir", "/abs/../escape", 7])
    ok, reasons = company.validate_company("acme", pack, siblings={})
    assert not ok
    joined = "\n".join(reasons)
    assert "legacy_workdirs[0]" in joined
    assert "legacy_workdirs[1]" in joined
    assert "legacy_workdirs[2]" in joined


def test_legacy_workdirs_must_be_a_list():
    ok, reasons = company.validate_company("acme", _minimal_pack("acme", legacy_workdirs="/abs"), siblings={})
    assert not ok and any("legacy_workdirs must be a list" in r for r in reasons)


def test_default_globs_include_each_packs_legacy_workdir(tmp_path):
    legacy = tmp_path / "old_work dir"
    legacy.mkdir()
    home = _make_home(tmp_path, "acme", _minimal_pack("acme", legacy_workdirs=[str(legacy)]))
    globs = htt.default_globs_for_homes({"acme": home})
    legacy_name = htt._project_dir_name(legacy)
    assert any(legacy_name in g for g in globs), globs


def test_default_globs_without_legacy_workdirs_cover_only_the_home(tmp_path):
    legacy = tmp_path / "old_work dir"
    legacy.mkdir()
    home = _make_home(tmp_path, "acme", _minimal_pack("acme"))
    globs = htt.default_globs_for_homes({"acme": home})
    assert not any(htt._project_dir_name(legacy) in g for g in globs)
    assert any(htt._project_dir_name(home) in g for g in globs)


def test_unreadable_pack_contributes_no_legacy_dirs(tmp_path):
    home = tmp_path / "home_broken"
    (home / ".claude" / "gtm").mkdir(parents=True)
    (home / ".claude" / "gtm" / "company.json").write_text("{not json", encoding="utf-8")
    assert htt._legacy_workdirs({"broken": home}) == []


def test_harvest_source_names_no_company():
    # The runtime mirror's publish gate blocks any tools/gtm file naming one of
    # the operator's companies; the legacy path must come from the pack.
    src = Path(htt.__file__).read_text(encoding="utf-8").lower()
    assert "google_ads_review_2026_09_25" not in src
