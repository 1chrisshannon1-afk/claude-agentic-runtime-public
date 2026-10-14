"""Regression guard for the `knowledge/trade_kb/corpus{,_text}/` whitelist-
inside-a-whitelist block in the runtime `.gitignore`.

This runtime's `.gitignore` is a strict whitelist (`/*` then explicit
`!dir/` re-includes) -- `!knowledge/` un-ignores the WHOLE `knowledge/`
tree with nothing further protecting it, so a planned future migration
(moving a ~1GB corpus of third-party, licensed manufacturer/code-book PDFs
into `knowledge/trade_kb/corpus/`) would silently auto-track all of it
into this repo's local git history -- the one rollback for the whole
runtime -- unless a second, narrower ignore block re-protects that subtree.

Coverage, driven by real `git check-ignore --no-index` against a scratch
git repo seeded with the REAL, live `.gitignore` (never the operator's
actual ~/.claude/.file_claims or working tree):
  - A corpus file at depth 1/2/3+ must be ignored (the `**`, not `*`,
    requirement -- a single-level `*`/`*/` re-include of a first-level
    subdirectory was found, empirically, to ALSO silently re-include
    everything nested inside it, defeating the ignore past one level).
  - A `MANIFEST*.yaml` at any depth under corpus/, and `corpus/README.md`,
    must stay tracked (with or without an underscore after MANIFEST --
    mirrors the product repo's own `_Config_Project/trade_kb/.gitignore`
    pattern exactly).
  - Nothing under `corpus_text/` is EVER tracked, including a file that
    happens to be named like a manifest or README.
  - Pre-existing tracked surfaces (CLAUDE.md, knowledge/model_policy.json,
    an arbitrary knowledge/ file) are unaffected.
  - The two anchored `!/statusline.sh` / `!/statusline-command.sh`
    negations still track the real top-level files but no longer leak
    into `knowledge/trade_kb/corpus/` if a same-named file ever lands
    there (an unanchored negation was found to punch through the new
    block from below).

Falsifiability (contract §6): `TestCleanTreeGoesRed` runs era-scoped subsets
of the matrix against two PINNED pre-fix `.gitignore` literals
(`_PRE_FIX_GITIGNORE` and `_PRE_BLOCKER1_FIX_GITIGNORE` -- never a dynamic
`git show HEAD:.gitignore` read, which would go stale the instant this
fix's own commit lands) and asserts each is NOT all-green -- proving this
suite would have caught the gap before the corresponding fix landed. The
two cases are NOT identical: the first runs `_CORPUS_ONLY_IGNORED_PATHS`
against `_PRE_FIX_GITIGNORE` (the pre-corpus-block state), and the second
runs a narrower, single-path check against `_PRE_BLOCKER1_FIX_GITIGNORE`
(the pre-Blocker-1 telemetry/fixtures/ dead-negation state).

Extended (2026-08-30, final review round) to also cover the `telemetry/`
and `schedules/patches/` whitelist-inside-a-whitelist blocks and the
repo-root-anchored `!/README.md` / `!/docs/` re-includes -- these landed in
the same working-tree change as the corpus block above but had ZERO test
coverage, which is exactly how a real, live bug (a dead file-level negation
for `telemetry/fixtures/sample_cycle_record.json` -- see
`_PRE_BLOCKER1_FIX_GITIGNORE` below) shipped invisibly.

Extended (2026-10-12) for the public-bundle project files (`.github/`,
`pyproject.toml`, `.editorconfig`, `.pre-commit-config.yaml`, the governance
docs, `demo/`). Two rows per path: a `_TRACKED_PATHS` row proving the
re-include works at all, and a `_PUBLIC_BUNDLE_ANCHOR_IGNORED_PATHS` row
proving the negation is ANCHORED -- an unanchored `!CONTRIBUTING.md` placed
after the corpus/telemetry blocks would re-include a same-named file dropped
inside `knowledge/trade_kb/corpus/` or `telemetry/` (the statusline.sh leak
shape). `demo/` is a whitelist-inside-a-whitelist like `telemetry/`, so two
further rows check that a demo transcript and the demo's scratch sandbox
stay untracked.

Extended (2026-10-13) so the live-file matrix applies only to the allow-list
model: a checkout whose `.gitignore` is a conventional ignore file (the public
bundle's) skips it with a stated reason. The model is recognised by ANY `/*`
rule or ANY `!` re-include -- not by `/*` being the first rule, which a moved or
deleted `/*` defeated -- and `TestAllowListDetection` pins that, including that
a runtime file with `/*` deleted still runs the matrix and fails it (the
`_ALLOW_LIST_DEFAULT_IGNORED_PATHS` rows exist because every other row stays
green without the root rule).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_scratch_repo(tmp_path: Path, gitignore_text: str) -> Path:
    repo = tmp_path / "scratch_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(gitignore_text, encoding="utf-8")
    return repo


def _is_ignored(repo: Path, relpath: str) -> bool:
    """True if `relpath` is ignored under `repo`'s `.gitignore` -- the path
    need not exist on disk; `check-ignore` evaluates the pattern only."""
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", relpath],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# The live matrix every case below is checked against.
# ---------------------------------------------------------------------------

# Corpus-only subset -- kept separate from the combined `_IGNORED_PATHS`
# below because `TestCleanTreeGoesRed`'s original falsifiability test is
# scoped to the `_PRE_FIX_GITIGNORE` literal, which predates telemetry/,
# schedules/patches/, and docs/ entirely (they were never allowlisted at
# all in that pre-fix state, so every one of those paths is trivially
# already-ignored there -- a true positive for THAT literal's era, but not
# a case that literal's falsifiability check should be asked to "fail").
_CORPUS_ONLY_IGNORED_PATHS = [
    "knowledge/trade_kb/corpus/toplevel.pdf",
    "knowledge/trade_kb/corpus/manufacturers/MANIFEST.pdf",  # a PDF, not a manifest
    "knowledge/trade_kb/corpus/manufacturers/bathtubs/kohler_install.pdf",
    "knowledge/trade_kb/corpus/a/b/c/deeply_nested.html",
    "knowledge/trade_kb/corpus_text/abc123.txt",
    "knowledge/trade_kb/corpus_text/a/b/nested.txt",
    "knowledge/trade_kb/corpus_text/MANIFEST_looks_like_one.yaml",
    "knowledge/trade_kb/corpus_text/README.md",
    "knowledge/trade_kb/corpus/manufacturers/statusline.sh",
]

_TELEMETRY_SCHEDULES_IGNORED_PATHS = [
    # telemetry/: `telemetry/*` re-ignores everything under the un-ignored
    # `!telemetry/` tree except the handful of exact files re-included below
    # -- any other runtime-written file (mutable state, logs, caches) must
    # stay ignored.
    "telemetry/loop_log.html",  # gitignore coverage only -- this path's liveness (must stay a symlink, never regress to a regular-file orphan) is guarded separately by test_cycle_log_freshness.py; the two checks are complementary.
    "telemetry/cycles/a/b.json",
    "telemetry/spend_cache.json",
    "telemetry/1p_failed_events.x.json",
    # telemetry/fixtures/: regression coverage for BLOCKER 1 (this round) --
    # a bare file-level negation of the shipped fixture is INERT once
    # `telemetry/*` excludes the fixtures/ directory itself; only the fix
    # (re-include the dir, re-exclude its contents, re-include the one
    # named file) makes a SECOND fixture file behave correctly, so these
    # two paths must stay ignored even though the directory is trackable.
    "telemetry/fixtures/BRAND_NEW.json",
    "telemetry/fixtures/nested/deep.json",
    # schedules/patches/: nightly finishing-loop integration patches --
    # product-source diffs, never runtime config, never tracked.
    "schedules/patches/x.patch",
    "schedules/patches/deep/x.patch",
]

# Combined matrix -- used for coverage against the LIVE, current .gitignore
# (`TestCorpusProtection` below). The falsifiability tests in
# `TestCleanTreeGoesRed` use the two lists above separately, each against
# its own era-appropriate pre-fix literal (see that class).
# Public-bundle project files (2026-10-12): every `!/name` re-include added for
# the public mirror is ANCHORED to the repo root. The corpus/ and telemetry/
# rows prove it -- with an unanchored `!name` in the same position, each of
# those would become trackable. The two demo/ rows guard something else: the
# `/demo/*` re-exclusion (see the inline comment). Joined ONLY into
# `_IGNORED_PATHS` (the live-file matrix), never into
# `_CORPUS_ONLY_IGNORED_PATHS`: `test_pre_fix_gitignore_fails_every_
# ignored_case` requires every row there to be TRACKABLE under
# `_PRE_FIX_GITIGNORE`, which ignores telemetry/ entirely and every
# top-level path via `/*`, so the telemetry and demo rows below would break
# that falsifiability check.
_PUBLIC_BUNDLE_ANCHOR_IGNORED_PATHS = [
    "knowledge/trade_kb/corpus/pyproject.toml",
    "knowledge/trade_kb/corpus/.editorconfig",
    "knowledge/trade_kb/corpus/.pre-commit-config.yaml",
    "knowledge/trade_kb/corpus/CONTRIBUTING.md",
    "knowledge/trade_kb/corpus_text/SECURITY.md",
    "knowledge/trade_kb/corpus/CODE_OF_CONDUCT.md",
    "knowledge/trade_kb/corpus/a/CHANGELOG.md",
    "knowledge/trade_kb/corpus/GLOSSARY.md",
    "knowledge/trade_kb/corpus/ARCHITECTURE.md",
    "telemetry/.github/x.yml",
    "telemetry/demo/x.json",
    # demo/ is re-included as a whitelist-inside-a-whitelist (`!/demo/`,
    # `/demo/*`, then the two shipped files by name): the demo script's own
    # transcript and scratch state must never become trackable.
    "demo/transcript.txt",
    "demo/.sandbox/home/.claude/.file_claims/c.json",
]

# The allow-list model's DEFINING property: a top-level path nobody re-included
# is ignored (`/*`). Every other row in this matrix stays green with `/*`
# deleted (each guarded subtree has its own narrower rule), so without these
# two rows the model's root rule could be removed and nothing here would
# notice. Joined ONLY into the live-file matrix, like the rows above.
_ALLOW_LIST_DEFAULT_IGNORED_PATHS = [
    "zz_unlisted_top_level_file.txt",
    "zz_unlisted_top_level_dir/nested/file.txt",
]

_IGNORED_PATHS = (
    _CORPUS_ONLY_IGNORED_PATHS
    + _TELEMETRY_SCHEDULES_IGNORED_PATHS
    + _PUBLIC_BUNDLE_ANCHOR_IGNORED_PATHS
    + _ALLOW_LIST_DEFAULT_IGNORED_PATHS
)

_TRACKED_PATHS = [
    "knowledge/trade_kb/corpus/README.md",
    "knowledge/trade_kb/corpus/MANIFEST_root.yaml",
    "knowledge/trade_kb/corpus/manufacturers/MANIFEST_manufacturers.yaml",
    "knowledge/trade_kb/corpus/manufacturers/MANIFEST.yaml",  # no underscore
    "knowledge/trade_kb/corpus/a/b/MANIFEST_nested.yaml",
    "knowledge/model_policy.json",
    "knowledge/oversight_install.md",
    "CLAUDE.md",
    "settings.json",
    "statusline.sh",
    "statusline-command.sh",
    # telemetry/: the exact shipped reference files re-included by name.
    "telemetry/pricing.json",
    "telemetry/schema.json",
    "telemetry/README.md",
    "telemetry/fixtures/sample_cycle_record.json",
    # docs/ + README.md: the new documentation-project re-includes. These are
    # anchored to repo root (`!/README.md` / `!/docs/`) as a defensive,
    # convention-matching choice, not because anchoring is load-bearing here
    # -- mutation testing proved un-anchoring them back to `!README.md` /
    # `!docs/` leaves this exact pair fully green (nothing earlier in the
    # CURRENT file behaves differently either way, so no discriminating
    # coverage of anchoring specifically exists). These two cases only
    # assert the re-includes work at all -- that README.md and docs/ stay
    # tracked -- not that anchoring them matters.
    "README.md",
    "docs/agents/x.md",
    # Public-bundle project files (2026-10-12): every new TOP-LEVEL path is
    # ignored by `/*` until re-included by name, so a forgotten re-include
    # means `git archive HEAD` silently drops the file from the public export
    # while the working tree still shows it. One row per re-include line.
    ".github/workflows/ci.yml",
    "pyproject.toml",
    ".editorconfig",
    ".pre-commit-config.yaml",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "GLOSSARY.md",
    "ARCHITECTURE.md",
    "demo/run_demo.sh",
    "demo/README.md",
]


def _is_allow_list_gitignore(text: str) -> bool:
    """True when `text` is the runtime's allow-list model: it carries a `/*`
    rule (ignore everything at the root) or ANY `!` re-include (the allow-list
    is made of them -- the runtime file has dozens; a conventional ignore file
    has none). Either signal is enough, so the model is still recognised when
    `/*` is moved below another rule, or deleted outright -- which is exactly
    when the protections must keep RUNNING and fail, not quietly skip. Blank
    lines and comments (including a commented-out `/*`) do not count.

    Contract for the public bundle's own `.gitignore`: it is a conventional
    ignore file and must not use `!` negations, or it will be taken for this
    model and the live-file matrix will run (and fail) against it."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "/*" or line.startswith("!"):
            return True
    return False


def _gitignore_skip_reason(text: str) -> "str | None":
    """None when the live-file matrix applies to `text`; else why it does not."""
    if _is_allow_list_gitignore(text):
        return None
    return (
        "this checkout's .gitignore is not the runtime's allow-list model (no `/*` rule and "
        "no `!` re-include); the live-file matrix guards that model only"
    )


@pytest.fixture
def live_gitignore() -> str:
    """The checkout's own `.gitignore`, for the live-file matrix.

    The matrix below (`_IGNORED_PATHS` / `_TRACKED_PATHS`) pins the runtime's
    `/*` allow-list model and is meaningless against any other kind of ignore
    file: a conventional `.gitignore` does not ignore top-level paths by
    default, so "should be ignored" rows would fail and "should stay tracked"
    rows would pass for the wrong reason. Skip -- with the reason stated --
    when the checkout's `.gitignore` is not that model. The runtime's own
    `.gitignore` IS that model, so there the whole matrix runs, including
    when someone has damaged it (see `TestAllowListDetection`). The pinned
    pre-fix literals in `TestCleanTreeGoesRed` do not use this fixture and
    run everywhere.
    """
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    reason = _gitignore_skip_reason(text)
    if reason is not None:
        pytest.skip(reason)
    return text


class TestCorpusProtection:
    @pytest.mark.parametrize("relpath", _IGNORED_PATHS)
    def test_path_is_ignored(self, tmp_path, live_gitignore, relpath):
        repo = _make_scratch_repo(tmp_path, live_gitignore)
        assert _is_ignored(repo, relpath), f"{relpath} should be ignored but is not"

    @pytest.mark.parametrize("relpath", _TRACKED_PATHS)
    def test_path_stays_tracked(self, tmp_path, live_gitignore, relpath):
        repo = _make_scratch_repo(tmp_path, live_gitignore)
        assert not _is_ignored(repo, relpath), f"{relpath} should stay tracked but is ignored"



# The runtime .gitignore's content BEFORE the knowledge/trade_kb/corpus
# protection block was added (2026-08-29) -- pinned as a literal, NOT read
# from `git show HEAD:.gitignore`. Reading HEAD dynamically was tried first
# and found to be a time-bomb: the instant this fix's own commit lands, HEAD
# becomes byte-identical to the fixed file, every case in the matrix passes,
# and the "must fail at least one case" assertion below would itself start
# failing on every commit after this one -- turning a permanent regression
# guard into a test that goes red on its own success and invites a future
# agent to suppress it with a skip marker. A pinned literal has no such
# expiry; it documents the exact pre-fix gap forever.
_PRE_FIX_GITIGNORE = """\
# Whitelist model: ignore everything, then re-include only the runtime config surface.
# This keeps session data, history, transcripts, plans, caches, and secrets OUT of git.
/*
!.gitignore
!CLAUDE.md
!settings.json
!agents/
!commands/
!knowledge/
!schedules/
schedules/logs/
schedules/heartbeats/
schedules/queue/
schedules/spike/
schedules/**/*.log
!hooks/
!scripts/
!skills/
!tools/
!live-testing/
!workflows/
!statusline.sh
!statusline-command.sh
"""

# The runtime .gitignore's telemetry/ block as this session actually found
# it sitting UNCOMMITTED in the working tree (2026-08-30, before Blocker 1
# of that review round was fixed) -- pinned as a literal for the same
# reason as `_PRE_FIX_GITIGNORE` above (a HEAD read goes stale the instant
# the fix commit lands), but there is no `git show HEAD:.gitignore` this
# one could even read dynamically in the first place: the buggy block was
# never committed, only ever a working-tree diff. `telemetry/fixtures/` is
# not re-included before `telemetry/fixtures/*` sample fixture negation, so
# `telemetry/*` above it excludes the fixtures/ directory itself and the
# file-level negation below never fires (git does not descend into an
# already-excluded parent directory to evaluate a nested negation) --
# empirically confirmed via `git check-ignore` in a scratch repo before
# this literal was written.
_PRE_BLOCKER1_FIX_GITIGNORE = """\
/*
!telemetry/
telemetry/*
!telemetry/pricing.json
!telemetry/schema.json
!telemetry/README.md
!telemetry/fixtures/sample_cycle_record.json
"""


class TestCleanTreeGoesRed:
    """Falsifiability: the identical matrix against the PRE-FIX .gitignore
    must fail every case in the ignored-paths matrix -- proving the fix is
    load-bearing, not merely coincidentally passing."""

    def test_pre_fix_gitignore_fails_every_ignored_case(self, tmp_path):
        repo = _make_scratch_repo(tmp_path, _PRE_FIX_GITIGNORE)

        failures = {
            relpath for relpath in _CORPUS_ONLY_IGNORED_PATHS if not _is_ignored(repo, relpath)
        }

        assert failures == set(_CORPUS_ONLY_IGNORED_PATHS), (
            "expected the pre-fix .gitignore to fail EVERY case in the ignored-paths "
            "matrix (that's the gap this fix closes); cases unexpectedly already "
            f"protected without the fix: {set(_CORPUS_ONLY_IGNORED_PATHS) - failures}"
        )

    def test_pre_blocker1_fix_gitignore_wrongly_ignores_the_fixture(self, tmp_path):
        """BLOCKER 1 (2026-08-30 review round): a bare
        `!telemetry/fixtures/sample_cycle_record.json` re-include, placed
        directly after `telemetry/*` with no directory-level re-include
        first, is INERT -- git never descends into an already-excluded
        parent directory to evaluate a file-level negation inside it. The
        bug never bit in practice only because the one shipped fixture
        happened to already be a TRACKED file (tracked files bypass
        .gitignore entirely) -- a second fixture file would have silently,
        permanently failed to ship. Proven here against the actual buggy
        literal this session found sitting uncommitted (see
        `_PRE_BLOCKER1_FIX_GITIGNORE`), empirically confirmed via
        `git check-ignore` in a scratch repo before the fix was written."""
        repo = _make_scratch_repo(tmp_path, _PRE_BLOCKER1_FIX_GITIGNORE)

        # NOTE: `telemetry/fixtures/` (the directory itself) is deliberately
        # NOT part of this set -- it is ignored under BOTH the pre-fix and
        # post-fix `.gitignore` (confirmed empirically: `telemetry/*` always
        # excludes the directory; only the fixed literal's own
        # `!telemetry/fixtures/` re-include, immediately re-excluded by its
        # own `telemetry/fixtures/*`, changes anything, and `check-ignore` on
        # a bare directory path reports the outer exclusion either way). It
        # therefore never discriminates pre-fix from post-fix and would prove
        # nothing here. Only the shipped fixture FILE discriminates.
        should_be_wrongly_ignored = {
            "telemetry/fixtures/sample_cycle_record.json",
        }
        wrongly_ignored = {
            relpath for relpath in should_be_wrongly_ignored if _is_ignored(repo, relpath)
        }

        assert wrongly_ignored == should_be_wrongly_ignored, (
            "expected the pre-Blocker-1-fix .gitignore to WRONGLY ignore the "
            "shipped fixture file (that's the dead-negation bug this fix "
            "closes); cases unexpectedly already correct without the fix: "
            f"{should_be_wrongly_ignored - wrongly_ignored}"
        )

        # Sanity: the OTHER telemetry re-includes (not nested under an
        # excluded parent dir) were never broken by this bug -- confirms
        # the failure is specific to the fixtures/ nesting, not a blanket
        # telemetry/ regression.
        assert not _is_ignored(repo, "telemetry/pricing.json")


# A conventional ignore file, shaped like the public bundle's own `.gitignore`
# (language/editor cruft plus the runtime state dirs; no `/*`, no `!`). Pinned as
# a literal so these tests do not depend on which `.gitignore` the checkout under
# test happens to carry.
_PUBLIC_STYLE_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.venv/

# OS / editor cruft
.DS_Store
.vscode/

# runtime state
.enforcement/
.file_claims/
.enforce
"""


class TestAllowListDetection:
    """The skip decision for the live-file matrix. Skipping 59 protection tests
    is only right for a file that is NOT the allow-list model; a damaged
    runtime file must keep running them."""

    def test_the_runtime_shaped_file_is_recognised(self):
        assert _is_allow_list_gitignore(_PRE_FIX_GITIGNORE)
        assert _gitignore_skip_reason(_PRE_FIX_GITIGNORE) is None

    def test_the_public_style_file_is_not_and_says_why(self):
        assert not _is_allow_list_gitignore(_PUBLIC_STYLE_GITIGNORE)
        reason = _gitignore_skip_reason(_PUBLIC_STYLE_GITIGNORE)
        assert reason is not None and "allow-list" in reason

    def test_slash_star_does_not_have_to_be_the_first_rule(self):
        moved_down = ".DS_Store\n" + _PRE_FIX_GITIGNORE
        assert _is_allow_list_gitignore(moved_down)

    def test_deleting_the_root_rule_does_not_hide_the_model(self):
        without_root_rule = "\n".join(
            line for line in _PRE_FIX_GITIGNORE.splitlines() if line.strip() != "/*"
        )
        assert "/*" not in without_root_rule.splitlines()
        assert _is_allow_list_gitignore(without_root_rule)

    def test_comments_and_blank_lines_do_not_count(self):
        assert not _is_allow_list_gitignore("# /*\n# !keep\n\n   \n__pycache__/\n")
        assert not _is_allow_list_gitignore("")

    def test_the_live_runtime_file_without_its_root_rule_still_runs_and_fails_the_matrix(
        self, tmp_path
    ):
        """End to end on the REAL file: delete `/*` from it and the live-file
        matrix must not be skipped, and it must catch the damage (the
        `_ALLOW_LIST_DEFAULT_IGNORED_PATHS` rows go red). Only meaningful where
        the checkout's own `.gitignore` is the allow-list model."""
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        if _gitignore_skip_reason(text) is not None:
            pytest.skip("this checkout's .gitignore is not the allow-list model; nothing to damage")
        damaged = "\n".join(line for line in text.splitlines() if line.strip() != "/*") + "\n"
        assert _gitignore_skip_reason(damaged) is None, "the damaged file would skip the matrix"
        repo = _make_scratch_repo(tmp_path, damaged)
        now_trackable = [p for p in _IGNORED_PATHS if not _is_ignored(repo, p)]
        assert now_trackable, "deleting `/*` must turn at least one live-matrix row red"
