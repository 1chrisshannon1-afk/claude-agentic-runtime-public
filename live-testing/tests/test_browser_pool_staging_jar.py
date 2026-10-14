"""Regression tests for the staging-jar flag on numbered pool slots.

Covers the 2026-09-06 change that lets a session in ANY repo start
pre-authenticated: `_server_entry_numbered` appends
`--storage-state <pool home>/state/staging-merged.json` when that jar exists.

Two properties matter and neither was covered before:

  1. The flag appears IF AND ONLY IF the jar exists. With no jar the launch
     args must be byte-identical to the pre-change behavior, so a machine that
     has never primed is completely unaffected.
  2. The jar is the STAGING-ONLY one. It must never be the sibling
     `state/merged.json`, which holds real PRODUCTION cookies from old attended
     prod logins -- mounting those into all 12 slots is exactly what loading no
     jar at all was avoiding.

Self-contained: no browser, no network, no pool registry. Builds server entries
directly against a temp pool home.

Run:
    pytest ~/.claude/live-testing/tests/test_browser_pool_staging_jar.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Load browser_pool.py by path -- live-testing/ is not a package, so a plain
# `import browser_pool` is not reliable under pytest. Registering it in
# sys.modules BEFORE exec_module mirrors test_prod_proxy.py and is what keeps
# pytest's assertion rewriting from tripping over a half-initialised module.
_MODULE = Path(__file__).resolve().parent.parent / "browser_pool.py"
_spec = importlib.util.spec_from_file_location("browser_pool", _MODULE)
assert _spec is not None and _spec.loader is not None
bp = importlib.util.module_from_spec(_spec)
sys.modules["browser_pool"] = bp
_spec.loader.exec_module(bp)


def _entry(pool_home: Path) -> dict:
    return bp._server_entry_numbered("playwright-01", pool_home, "0.0.76", {})


def _write_jar(pool_home: Path, name: str) -> Path:
    state = pool_home / "state"
    state.mkdir(parents=True, exist_ok=True)
    jar = state / name
    jar.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
    return jar


def test_no_jar_means_no_flag(tmp_path):
    """The absent-jar path must be byte-identical to the pre-change launch."""
    args = _entry(tmp_path)["args"]
    assert "--storage-state" not in args
    assert args == [
        "-y",
        "@playwright/mcp@0.0.76",
        "--isolated",
        "--browser",
        "chrome",
        "--output-dir",
        str(tmp_path / "cache" / "playwright-01"),
    ]


def test_staging_jar_is_loaded_when_present(tmp_path):
    jar = _write_jar(tmp_path, bp.STAGING_JAR_NAME)
    args = _entry(tmp_path)["args"]
    assert args[-2:] == ["--storage-state", str(jar)]


def test_flag_is_appended_without_disturbing_the_existing_args(tmp_path):
    before = _entry(tmp_path)["args"]
    _write_jar(tmp_path, bp.STAGING_JAR_NAME)
    after = _entry(tmp_path)["args"]
    assert after[: len(before)] == before


def test_legacy_prod_jar_is_never_loaded(tmp_path):
    """state/merged.json holds PRODUCTION cookies. Its presence alone must not
    cause a slot to mount it -- only the staging jar counts."""
    legacy = _write_jar(tmp_path, "merged.json")
    args = _entry(tmp_path)["args"]
    assert "--storage-state" not in args
    assert str(legacy) not in args


def test_staging_jar_name_is_not_the_legacy_jar():
    assert bp.STAGING_JAR_NAME == "staging-merged.json"
    assert bp.STAGING_JAR_NAME != "merged.json"


@pytest.mark.parametrize("slot", ["playwright-01", "playwright-07", "playwright-12"])
def test_every_numbered_slot_gets_the_same_jar(tmp_path, slot):
    jar = _write_jar(tmp_path, bp.STAGING_JAR_NAME)
    args = bp._server_entry_numbered(slot, tmp_path, "0.0.76", {})["args"]
    assert args[-1] == str(jar)
    # Each slot keeps its own scratch dir.
    assert str(tmp_path / "cache" / slot) in args
