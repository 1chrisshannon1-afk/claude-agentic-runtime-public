"""Tests for review_risk_tier — the advisory review-cost classifier.

Pure-function module, no filesystem/git/sandbox needed: classify() only
looks at path STRINGS. Every assertion here is about the tier a given
pathspec resolves to, and the asymmetry that governs it (HIGH always wins;
under-classifying toward TRIVIAL is the failure mode this suite exists to
catch — round-2 review found four real instances of exactly that).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import review_risk_tier as rrt

_HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_HOOKS_DIR, "review_risk_tier.py")


def test_docs_only_is_trivial():
    tier, _ = rrt.classify(["docs/README.md", "docs/notes.rst"])
    assert tier == rrt.TRIVIAL


def test_lockfile_only_is_trivial():
    tier, _ = rrt.classify(["frontend/package-lock.json"])
    assert tier == rrt.TRIVIAL


def test_mixed_docs_and_lock_is_trivial():
    tier, _ = rrt.classify(["docs/README.md", "package-lock.json"])
    assert tier == rrt.TRIVIAL


def test_a_single_real_source_file_is_moderate():
    tier, _ = rrt.classify(["src/app/routes.py"])
    assert tier == rrt.MODERATE


def test_mixed_docs_and_real_code_is_moderate_not_trivial():
    tier, _ = rrt.classify(["docs/README.md", "src/app/routes.py"])
    assert tier == rrt.MODERATE


# ---------------------------------------------------------------------------
# Test-only changes: MODERATE, never TRIVIAL (round-2 finding 3 — a diff that
# only deletes assertions or adds a skip is exactly what review exists to
# catch; the first version of this module gave that shape the LEAST scrutiny).
# ---------------------------------------------------------------------------


def test_tests_only_is_moderate_not_trivial():
    tier, _ = rrt.classify(["src/tests/bar_test.py"])
    assert tier == rrt.MODERATE


def test_conftest_is_moderate_not_trivial():
    """conftest.py is test INFRASTRUCTURE -- weakening it can make an
    entire suite vacuous. Explicitly not eligible for a cheap pass (it is
    under hooks/tests/, which is exempt from the hooks/ HIGH rule, so this
    lands at MODERATE -- the point is it does NOT land at TRIVIAL)."""
    tier, _ = rrt.classify(["hooks/tests/conftest.py"])
    assert tier == rrt.MODERATE


def test_mixed_docs_and_tests_is_moderate_not_trivial():
    tier, _ = rrt.classify(["docs/README.md", "src/tests/test_foo.py"])
    assert tier == rrt.MODERATE


# ---------------------------------------------------------------------------
# HIGH: directory segments
# ---------------------------------------------------------------------------


def test_hooks_directory_is_high():
    tier, reason = rrt.classify(["hooks/precommit_review_gate.py"])
    assert tier == rrt.HIGH
    assert "hooks" in reason.lower()


def test_hooks_tests_subdirectory_is_moderate_not_high_when_test_shaped():
    """A test file UNDER hooks/tests/ only adds verification -- it does not
    inherit hooks/'s HIGH status from the directory-segment rule alone."""
    tier, _ = rrt.classify(["hooks/tests/test_foo.py"])
    assert tier == rrt.MODERATE


def test_agents_directory_is_high():
    """Round-2 finding 1: every agent PROMPT is executable policy in this
    runtime (browser-ops drives prod origins), not just the two reviewer
    files that were hardcoded before."""
    tier, reason = rrt.classify(["agents/browser-ops.md"])
    assert tier == rrt.HIGH
    assert "agents" in reason.lower()


def test_agents_implement_is_also_high():
    tier, _ = rrt.classify(["agents/implement.md"])
    assert tier == rrt.HIGH


def test_schedules_prompts_is_high():
    """A job prompt drives an UNATTENDED launchd session that dispatches agents
    and lands reviewed commits with nobody present -- executable policy, like
    an agent prompt. RED without the `schedules` segment (was `moderate`)."""
    tier, _ = rrt.classify(["schedules/prompts/issue_wheel.txt"])
    assert tier == rrt.HIGH
    # The reason string only echoes the input path, so assert the RULE
    # directly rather than the echo (an echo assertion would also pass for a
    # keyword or basename hit on a path that merely contains the word).
    assert "schedules" in rrt._HIGH_RISK_DIR_SEGMENTS


def test_schedules_plist_is_high():
    tier, _ = rrt.classify(["schedules/com.oversight.wheel.csa.plist"])
    assert tier == rrt.HIGH


def test_real_job_prompt_named_test_audit_is_high_not_a_test():
    """`schedules/prompts/test_audit.txt` is a REAL monthly job prompt whose
    name starts with `test_`. It is HIGH today only because the test-shaped
    pattern requires a `.py` suffix; pin it so a future broadening of
    `_TEST_PATTERNS` cannot silently demote a live prompt to MODERATE."""
    tier, _ = rrt.classify(["schedules/prompts/test_audit.txt"])
    assert tier == rrt.HIGH


def test_word_containing_schedules_is_not_high():
    """The segment rule is a whole-path-segment match, never a substring one —
    the module's central documented property, previously untested for every
    directory segment."""
    tier, _ = rrt.classify(["src/schedules_helper.py"])
    assert tier == rrt.MODERATE
    tier, _ = rrt.classify(["notes/my_schedules_notes.md"])
    assert tier == rrt.TRIVIAL


# ---------------------------------------------------------------------------
# HIGH: basenames
# ---------------------------------------------------------------------------


def test_settings_json_bare_relative_path_is_high():
    """Round-2 finding 13: the exact pathspec used to commit from ~/.claude's
    own root ('settings.json', no directory prefix) must match, not just the
    '.claude/settings.json' suffix form."""
    tier, _ = rrt.classify(["settings.json"])
    assert tier == rrt.HIGH


def test_settings_json_absolute_path_is_high():
    tier, _ = rrt.classify(["/Users/x/.claude/settings.json"])
    assert tier == rrt.HIGH


def test_claude_md_is_high():
    """Round-2 finding 1: the operating contract itself defines the review
    rules -- it must never be the thing a trivial-tier skip weakens."""
    tier, reason = rrt.classify(["CLAUDE.md"])
    assert tier == rrt.HIGH
    assert "claude.md" in reason.lower() or "risk-sensitive" in reason.lower()


def test_claude_md_case_insensitive():
    tier, _ = rrt.classify(["claude.md"])
    assert tier == rrt.HIGH


def test_firestore_rules_is_high():
    tier, _ = rrt.classify(["firestore.rules"])
    assert tier == rrt.HIGH


def test_allowlist_json_is_high():
    tier, _ = rrt.classify(["live-testing/allowlist.json"])
    assert tier == rrt.HIGH


# ---------------------------------------------------------------------------
# HIGH: keywords
# ---------------------------------------------------------------------------


def test_pricing_keyword_is_high():
    tier, _ = rrt.classify(["backend/estimate_pricing/markup.py"])
    assert tier == rrt.HIGH


def test_auth_keyword_is_high():
    tier, _ = rrt.classify(["backend/auth/middleware.py"])
    assert tier == rrt.HIGH


def test_migration_keyword_is_high():
    tier, _ = rrt.classify(["backend/migrations/0042_add_column.sql"])
    assert tier == rrt.HIGH


def test_iam_is_no_longer_a_keyword_false_positive():
    """Round-2 finding 32: bare 'iam' as a substring matched 'diameter'.
    Removed; identity/access is still covered by auth/permission/credential/
    token/security."""
    tier, _ = rrt.classify(["backend/geometry/diameter_calc.py"])
    assert tier != rrt.HIGH


def test_high_wins_even_mixed_with_trivial_paths():
    """A single risky path must force HIGH regardless of how many trivial
    paths ride along in the same change -- under-classifying is the LEAK
    direction here."""
    tier, _ = rrt.classify(["docs/README.md", "package-lock.json", "hooks/pretooluse_bash.py"])
    assert tier == rrt.HIGH


# ---------------------------------------------------------------------------
# Doc-extension carve-out fixes (round-2 finding 2)
# ---------------------------------------------------------------------------


def test_requirements_txt_is_not_trivial():
    tier, _ = rrt.classify(["requirements.txt"])
    assert tier == rrt.MODERATE


def test_constraints_txt_is_not_trivial():
    tier, _ = rrt.classify(["constraints.txt"])
    assert tier == rrt.MODERATE


def test_cmakelists_txt_is_not_trivial():
    tier, _ = rrt.classify(["CMakeLists.txt"])
    assert tier == rrt.MODERATE


def test_plain_txt_doc_is_not_trivial_either():
    """`.txt` was dropped from the doc-extension list entirely -- a plain
    prose .txt file now floats to MODERATE too. Conservative on purpose:
    the manifest false-negative was the actual danger, and a stray .txt
    getting one extra review is a low-cost false positive by comparison."""
    tier, _ = rrt.classify(["notes/todo.txt"])
    assert tier == rrt.MODERATE


def test_html_template_is_not_trivial():
    tier, _ = rrt.classify(["marketing/website/templates/index.html"])
    assert tier == rrt.MODERATE


def test_html_outside_templates_is_still_trivial():
    tier, _ = rrt.classify(["docs/guide.html"])
    assert tier == rrt.TRIVIAL


# ---------------------------------------------------------------------------
# Path-traversal / normalization (round-2 finding 4)
# ---------------------------------------------------------------------------


def test_dotdot_traversal_cannot_defeat_the_hooks_segment_rule():
    tier, _ = rrt.classify(["hooks/tests/../pretooluse_bash.py"])
    assert tier == rrt.HIGH


def test_case_insensitivity_for_doc_and_lock_checks():
    """Round-2 finding 31: _is_doc/_is_lock did not lowercase, so
    'DOCS/README.MD' and 'SRC/Tests/Foo.py' escaped their intended buckets."""
    tier, _ = rrt.classify(["DOCS/README.MD"])
    assert tier == rrt.TRIVIAL


# ---------------------------------------------------------------------------
# Empty / garbage input
# ---------------------------------------------------------------------------


def test_empty_pathspec_is_moderate_not_trivial():
    tier, reason = rrt.classify([])
    assert tier == rrt.MODERATE
    assert "empty" in reason.lower()


def test_none_entries_filtered_without_raising():
    tier, _ = rrt.classify(["", None, "docs/x.md"])  # type: ignore[list-item]
    assert tier == rrt.TRIVIAL


def test_never_raises_on_garbage_input():
    assert rrt.classify(None)[0] == rrt.MODERATE  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Manifest-driven extra risk keywords (runtime_bundle_repo_agnostic_plan.md
# WS4.5, H8): the BASE `_HIGH_RISK_KEYWORDS` list is runtime-wide and must
# never bake in a single product's own vocabulary (`catalog` was
# ExampleApp-specific and has been removed from it). `classify()`
# instead UNIONS the base list with the calling repo's own
# `security.extra_risk_keywords` (`<repo>/.claude/oversight/manifest.json`),
# resolved from the CLASSIFYING PROCESS's cwd via `git rev-parse
# --show-toplevel` -- never a hardcoded/repo-agnostic keyword, and never
# another repo's manifest. No repo, no manifest, or an empty/absent key must
# all degrade to the base list only -- never a crash (fail-open, like every
# other hook in this chain).
#
# Driven via subprocess with `cwd=` set to the fixture repo, matching how
# the existing `test_cli_prints_tier_and_reason` below already invokes this
# module's CLI -- `main()` (not `classify()` directly) is what performs the
# repo-cwd resolution (`_repo_extra_keywords()`), so a black-box subprocess
# call is the only way to exercise that resolution end to end.
# ---------------------------------------------------------------------------


def _git_repo(tmp_path, name: str = "repo") -> str:
    repo = Path(tmp_path) / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return str(repo)


def _write_manifest(repo: str, extra_risk_keywords) -> None:
    oversight = Path(repo) / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    manifest_path = oversight / "manifest.json"
    data = {
        "schema_version": 1,
        "product": {"name": "Widget Co", "slug": "widgetco"},
        "github": {"repo": "acme/widgetco"},
        "gtm": {"missions_dir": ".", "inbox_label": "dept:marketing"},
    }
    if extra_risk_keywords is not None:
        data["security"] = {"extra_risk_keywords": extra_risk_keywords}
    manifest_path.write_text(json.dumps(data))


def _run_cli(cwd: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _SCRIPT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_catalog_is_no_longer_a_hardcoded_base_keyword():
    """RED today (pre-WS4.5): the base list still hardcodes 'catalog', so
    this path classifies HIGH with NO manifest involved at all -- proving the
    keyword is baked in rather than repo-supplied. Once WS4.5 lands, the base
    list alone (empty extra_keywords) must NOT classify this HIGH."""
    tier, _ = rrt.classify(["data/catalog_prices.csv"], ())
    assert tier != rrt.HIGH


def test_manifest_extra_keyword_novel_classifies_high(tmp_path):
    """The actual mechanism claim, proven with a keyword that was NEVER in
    the base list (unlike "catalog" below, which was hardcoded pre-diff
    and so passes identically whether or not the manifest-extension
    mechanism works at all -- see test_manifest_extra_keyword_catalog_
    classifies_high's own docstring). This is the test that genuinely
    falsifies against pre-fix source."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, ["zzqqnovel"])
    proc = _run_cli(repo, ["data/zzqqnovel_prices.csv"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.HIGH


def test_manifest_extra_keyword_catalog_classifies_high(tmp_path):
    """CSA's specific regression case: a repo whose manifest declares
    `security.extra_risk_keywords: ["catalog"]` restores HIGH for a path
    containing that word -- CSA's own restore-path for the keyword this
    module's base list no longer hardcodes. NOTE: because "catalog" was
    itself in the base list before this diff, this test alone cannot
    distinguish "the manifest mechanism works" from "the base list still
    has it" -- see test_manifest_extra_keyword_novel_classifies_high above
    for the test that actually proves the mechanism."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, ["catalog"])
    proc = _run_cli(repo, ["data/catalog_prices.csv"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.HIGH


def test_manifest_empty_extra_keywords_is_moderate_not_high():
    """Required pairing / recovery for the gate above: the SAME path, in a
    repo whose manifest explicitly lists NO extra keywords, must NOT
    classify HIGH -- RED today because 'catalog' is hardcoded into the
    base list regardless of any manifest."""
    tier, _ = rrt.classify(["data/catalog_prices.csv"], ())
    assert tier == rrt.MODERATE


def test_manifest_empty_extra_keywords_cli_is_moderate_not_high(tmp_path):
    """Same recovery assertion, driven end to end through the real CLI (cwd
    resolution + manifest read), not just the pure `classify()` call above."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, [])
    proc = _run_cli(repo, ["data/catalog_prices.csv"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.MODERATE


def test_base_keyword_is_high_regardless_of_manifest_state():
    """A path matching a BASE keyword (e.g. `billing`) must classify HIGH
    whether or not any extra keywords are supplied -- the manifest only ever
    WIDENS the HIGH set, it can never narrow the base list."""
    tier_no_extra, _ = rrt.classify(["billing/x.py"], ())
    tier_with_extra, _ = rrt.classify(["billing/x.py"], ("catalog",))
    assert tier_no_extra == rrt.HIGH
    assert tier_with_extra == rrt.HIGH


def test_base_keyword_is_high_via_cli_with_empty_manifest_list(tmp_path):
    """End-to-end version of the base-keyword-always-high guarantee: a repo
    whose manifest declares zero extra keywords still classifies a base
    keyword path HIGH."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, [])
    proc = _run_cli(repo, ["billing/x.py"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.HIGH


def test_base_keyword_is_high_via_cli_with_manifest_extra_keyword(tmp_path):
    """Paired with the manifest-catalog gate above: adding a repo-specific
    extra keyword must never displace or weaken the base keyword set in the
    SAME repo/manifest."""
    repo = _git_repo(tmp_path)
    _write_manifest(repo, ["catalog"])
    proc = _run_cli(repo, ["billing/x.py"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.HIGH


def test_no_repo_catalog_path_classifies_moderate_base_list_only(tmp_path):
    """Outside any git repo: no manifest can be resolved, so a manifest-only
    keyword (`catalog`) must NOT classify HIGH -- the classifier degrades
    to the base list only, never a crash."""
    outside = tmp_path / "not_a_repo"
    outside.mkdir()
    proc = _run_cli(str(outside), ["data/catalog_prices.csv"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.MODERATE


def test_no_repo_recovery_base_keyword_still_classifies_high(tmp_path):
    """Required recovery pairing for the no-repo gate above: even with no
    repo/manifest resolvable at all, a BASE keyword path still classifies
    HIGH -- the no-repo path degrades to a working (if narrower) classifier,
    it never silently stops classifying anything as risky."""
    outside = tmp_path / "not_a_repo"
    outside.mkdir()
    proc = _run_cli(str(outside), ["billing/x.py"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.HIGH


def test_malformed_manifest_degrades_to_base_list_no_traceback(tmp_path):
    """A manifest that fails to parse must never crash the classifier --
    it degrades to the base list only (no extra keywords), and the process
    must not print a Python traceback to stderr."""
    repo = _git_repo(tmp_path)
    oversight = Path(repo) / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "manifest.json").write_text("{not valid json,,,")
    proc = _run_cli(repo, ["data/catalog_prices.csv"])
    assert proc.returncode == 0
    tier = proc.stdout.split("\t", 1)[0]
    assert tier == rrt.MODERATE
    assert "Traceback" not in proc.stderr


def test_malformed_manifest_recovery_fix_then_extra_keyword_applies(tmp_path):
    """Recovery pairing for the malformed-manifest gate above: fixing the
    SAME repo's manifest to a valid one naming the extra keyword makes it
    apply -- proving the malformed-manifest path is a genuine degrade, not
    a permanent wedge."""
    repo = _git_repo(tmp_path)
    oversight = Path(repo) / ".claude" / "oversight"
    oversight.mkdir(parents=True, exist_ok=True)
    (oversight / "manifest.json").write_text("{not valid json,,,")
    broken = _run_cli(repo, ["data/catalog_prices.csv"])
    assert broken.returncode == 0
    assert broken.stdout.split("\t", 1)[0] == rrt.MODERATE

    _write_manifest(repo, ["catalog"])
    fixed = _run_cli(repo, ["data/catalog_prices.csv"])
    assert fixed.returncode == 0
    assert fixed.stdout.split("\t", 1)[0] == rrt.HIGH


def test_extra_keywords_never_touch_real_csa_or_knowledge():
    """Documents the isolation guarantee for this whole section: every test
    above drives `classify()`/the CLI against a throwaway `tmp_path` git
    repo with its own fabricated manifest, or with a hardcoded literal
    tuple -- never `~/.claude/knowledge` or the real ExampleApp repo.
    This test asserts the constant this section relies on stays true: the
    module's BASE list contains no throwaway-fixture-specific term, so a
    fixture repo's manifest is the only source of `catalog` anywhere in
    this suite's classification path."""
    assert "catalog" not in rrt._HIGH_RISK_KEYWORDS


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_prints_tier_and_reason(tmp_path):
    # Explicit non-repo cwd -- without this the CLI's own `_repo_extra_keywords()`
    # resolves against the ACTUAL test-runner cwd (this repo), silently making
    # this test non-hermetic: a future `~/.claude` manifest carrying an
    # extra_risk_keyword like "readme" would flip this from trivial to high
    # with no change to the test itself.
    proc = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "review_risk_tier.py"), "docs/README.md"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("trivial\t")


def test_cli_with_no_args_is_moderate_exit_zero(tmp_path):
    # Explicit non-repo cwd -- see test_cli_prints_tier_and_reason above.
    proc = subprocess.run(
        [sys.executable, os.path.join(_HOOKS_DIR, "review_risk_tier.py")],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("moderate\t")
