"""Tests for agentarch_metric_check (Lane A, repo-agnostic AA-ledger metrics).

Falsifiability: a RED fixture proving the hardcoded-path check actually
fires on the exact pattern this module exists to catch, a GREEN fixture
proving the placeholder form is clean, plus a live-tree run against the
real (post-migration) ledger and registry.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agentarch_metric_check as chk  # noqa: E402

_HOME = str(Path.home())
_REAL_LEDGER = str(
    Path.home() / ".claude" / "knowledge" / "agentarch_recommendations.jsonl"
)
_REAL_REGISTRY = str(Path.home() / ".claude" / "knowledge" / "repo_registry.json")

# Probed, not assumed (round 7 review, 2026-08-28): the case-variant tests
# below only hold on a case-INSENSITIVE filesystem (this machine's default
# APFS volume, where `~/.claude/PROJECTS` and `~/.claude/projects` are the
# same inode) and the /tmp-alias tests only hold where `/private/tmp`
# exists at all (macOS's real symlink target for `/tmp`; absent on Linux).
# Neither probe is a security assumption — the guard itself stays correct
# either way — only a filesystem-behavior precondition these specific
# tests need to be meaningful; skip cleanly rather than fail for a
# non-security reason on a platform where it doesn't hold.
_CASE_INSENSITIVE_FS = os.path.exists(f"{_HOME}/.claude/PROJECTS")
_HAS_PRIVATE_TMP_ALIAS = os.path.exists("/private/tmp")


def _row(**overrides: object) -> dict:
    base = {
        "id": "AA-0001",
        "issued_at": "2026-08-25",
        "claim": "some claim",
        "metric": "some metric",
        "metric_command": f"grep -c foo {_HOME}/.claude/hooks/_lib.py",
        "baseline_value": 1,
        "target_direction": "up",
        "status": "open",
        "checked_at": None,
        "checked_value": None,
    }
    base.update(overrides)
    return base


def _write_ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _write_registry(tmp_path: Path, repos: dict[str, str]) -> Path:
    p = tmp_path / "repo_registry.json"
    p.write_text(json.dumps({"schema_version": 1, "repos": {k: {"root": v} for k, v in repos.items()}}))
    return p


def _make_registrable_repo(d: Path) -> Path:
    """Marks an existing directory as a real repo checkout (a `.git`
    entry) so `load_registry` actually accepts it — Blocker 4 (round 3
    review, 2026-08-28) requires a registered root to look like a real
    repo checkout, not an arbitrary directory.
    """
    (d / ".git").mkdir(exist_ok=True)
    return d


# --------------------------------------------------------------------------
# find_hardcoded_paths — RED per class + legal cases
# --------------------------------------------------------------------------


def test_runtime_only_path_is_never_flagged():
    assert chk.find_hardcoded_paths(f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py") == []


def test_tmp_path_is_never_flagged():
    assert chk.find_hardcoded_paths("cat /tmp/some/scratch/file.txt") == []


def test_bare_absolute_product_repo_path_is_flagged_RED():
    """The exact defect this module exists to catch: a literal absolute
    path outside ~/.claude/ and /tmp/, with no ${REPO:...} placeholder.
    """
    hits = chk.find_hardcoded_paths(
        f'grep -rl "Maximum 30 concurrent" {_HOME}/Desktop/OtherApp/.claude/agents'
    )
    assert hits == [f"{_HOME}/Desktop/OtherApp/.claude/agents"]


def test_placeholder_form_is_never_flagged_as_hardcoded_regardless_of_slug_validity():
    assert chk.find_hardcoded_paths("grep -c x ${REPO:exampleapp}/CLAUDE.md") == []
    # even an unregistered slug is not a "hardcoded path" finding — that is
    # unknown-repo-slug's job, a separate check, so the two never double-count
    assert chk.find_hardcoded_paths("grep -c x ${REPO:nonexistent}/CLAUDE.md") == []


def test_flags_do_not_trip_the_hardcoded_path_check():
    assert chk.find_hardcoded_paths(f"ls -1 {_HOME}/.claude/agents") == []


def test_a_brand_new_never_before_seen_repo_path_is_still_flagged():
    """Generality check: the module hardcodes NO product name anywhere —
    it only special-cases ~/.claude/ and /tmp/ — so it catches a repo that
    did not exist when this module was written.
    """
    hits = chk.find_hardcoded_paths(f"grep -c x {_HOME}/Desktop/SomeFutureApp/CLAUDE.md")
    assert hits == [f"{_HOME}/Desktop/SomeFutureApp/CLAUDE.md"]


# --------------------------------------------------------------------------
# find_hardcoded_paths — Finding 6 (round 8 review, 2026-08-30): a
# ${REPO:<slug>} token used to be skipped ENTIRELY, even when its REMAINDER
# (after the placeholder) is a `..`-shaped escape — measured false
# all-clear: `cat ${REPO:agency}/../../.ssh/id_rsa` reported 0 violations.
# --------------------------------------------------------------------------


def test_placeholder_traversal_escape_is_flagged_RED():
    hits = chk.find_hardcoded_paths("cat ${REPO:agency}/../../.ssh/id_rsa")
    assert hits == ["${REPO:agency}/../../.ssh/id_rsa"]


def test_placeholder_single_traversal_up_is_flagged():
    hits = chk.find_hardcoded_paths("cat ${REPO:agency}/..")
    assert hits == ["${REPO:agency}/.."]


def test_placeholder_internal_traversal_that_stays_inside_is_not_flagged():
    """A `..` that resolves back INSIDE the placeholder's own root (e.g.
    `sub/../file.txt`) is not a real escape and must not false-positive."""
    assert chk.find_hardcoded_paths("cat ${REPO:agency}/sub/../file.txt") == []


def test_placeholder_with_no_traversal_at_all_still_clean():
    # Regression guard: the sentinel-substitution mechanism must not
    # accidentally start flagging the ordinary, no-traversal placeholder
    # form this module has always treated as clean.
    assert chk.find_hardcoded_paths("grep -c needle ${REPO:myrepo}/haystack.txt") == []


# --------------------------------------------------------------------------
# classify_tokens / find_hardcoded_paths — Finding 7 (round 8 review,
# 2026-08-30): the first non-flag token after grep/rg was treated
# unconditionally as "the pattern" (exempt from scanning), even with NO
# separate file operand — hiding a real hardcoded path used as the SOLE
# argument (the shape `rg -l <path>` / `grep -l <path>` uses with no file
# target: the lone argument is a real search target, not prose).
# --------------------------------------------------------------------------


def test_sole_argument_after_flag_is_not_exempted_as_pattern_rg():
    hits = chk.find_hardcoded_paths(f"rg -l {_HOME}/Desktop/OtherApp/hardcoded_target.txt")
    assert hits == [f"{_HOME}/Desktop/OtherApp/hardcoded_target.txt"]


def test_sole_argument_after_flag_is_not_exempted_as_pattern_grep():
    hits = chk.find_hardcoded_paths(f"grep -l {_HOME}/Desktop/OtherApp/hardcoded_target.txt")
    assert hits == [f"{_HOME}/Desktop/OtherApp/hardcoded_target.txt"]


def test_pattern_still_exempted_when_a_second_non_flag_token_follows():
    # Regression guard: the ordinary `PATTERN FILE` shape (two non-flag
    # tokens) must still exempt the first one as a pattern, unaffected by
    # the sole-argument fix above.
    hits = chk.find_hardcoded_paths(
        f'grep -rl "root /Users/x/Desktop/OtherApp is hardcoded" {_HOME}/.claude/commands/sweep.md'
    )
    assert hits == []


# --------------------------------------------------------------------------
# M-1 (round-5 security review, 2026-08-30) — `find_hardcoded_paths` and
# `validate_agentarch_ledger.guard_check` used to consume DIFFERENT views
# of the same command: this function only ever called the positional-role
# piece of the shared grammar (`_pattern_arg_index`, removed this round),
# applying its exemption BEFORE any flag validation, while `guard_check`
# consulted the full flag/value/positional classification and applied
# exemptions AFTER flag validation. Verified real bypass:
# `find_hardcoded_paths('grep -ec /Users/x/Desktop/OtherApp/secret
# ~/.claude/CLAUDE.md')` returned `[]` — `-ec` (a real grep flag spelling,
# NOT a recognized `-e` occurrence under this grammar's exact-match rule)
# was not recognized as "the `-e` flag is present", so the old,
# independent positional-role scan still treated the FIRST non-flag token
# — the smuggled hardcoded path — as an exempt "pattern" and never scanned
# it. Now both functions consume the SAME `classify_command`/
# `classify_tokens` single left-to-right pass.
# --------------------------------------------------------------------------


def test_find_hardcoded_paths_catches_path_smuggled_via_unrecognized_dash_ec_M1():
    """THE task's own exact repro: `-ec` is not a recognized `-e` flag
    occurrence in this grammar, so the smuggled hardcoded path must now be
    reported — pre-fix this returned `[]`."""
    hits = chk.find_hardcoded_paths(
        f"grep -ec {_HOME}/Desktop/OtherApp/secret {_HOME}/.claude/CLAUDE.md"
    )
    assert hits == [f"{_HOME}/Desktop/OtherApp/secret"]


def test_find_hardcoded_paths_still_exempts_a_genuine_bare_pattern_after_M1():
    """Paired recovery case: an ordinary, non-path-shaped bare pattern (no
    real `-e` ambiguity involved at all) must stay exempt, unaffected by
    the M-1 fix — proves the fix targets the smuggled-path SHAPE, not
    positional-role exemption in general."""
    assert (
        chk.find_hardcoded_paths(f"grep -c somepattern {_HOME}/.claude/hooks/_lib.py")
        == []
    )


# --------------------------------------------------------------------------
# find_hardcoded_paths — Blocker F: three verified false-negative escapes
# --------------------------------------------------------------------------


def test_dotdot_traversal_out_of_a_safe_root_is_flagged():
    """A `..` traversal token starts with the literal prefix
    ``~/.claude/`` as a plain string, so a non-normalizing safe-root
    comparison wrongly treats it as staying inside the always-safe root.
    """
    hits = chk.find_hardcoded_paths(
        f"cat {_HOME}/.claude/../Desktop/OtherApp/CLAUDE.md"
    )
    assert hits == [f"{_HOME}/.claude/../Desktop/OtherApp/CLAUDE.md"]


def test_dash_flag_with_embedded_path_via_equals_is_flagged():
    """Every `-`-prefixed token used to be skipped outright, so a hardcoded
    path smuggled in after `=` (e.g. `--file=<path>`) was invisible.
    """
    hits = chk.find_hardcoded_paths(
        f"grep -c x --file={_HOME}/Desktop/OtherApp/CLAUDE.md"
    )
    assert hits == [f"--file={_HOME}/Desktop/OtherApp/CLAUDE.md"]


def test_dash_flag_with_embedded_safe_path_via_equals_is_not_flagged():
    assert chk.find_hardcoded_paths(f"grep -c x --file={_HOME}/.claude/hooks/_lib.py") == []


def test_quoted_compound_command_is_recursively_scanned():
    """A quoted sub-command (e.g. `bash -c "..."`) arrives from shlex.split
    as ONE token containing whitespace; it must be re-scanned as its own
    command string, not skipped as an opaque non-path token.
    """
    hits = chk.find_hardcoded_paths(
        f'bash -c "grep -c x {_HOME}/Desktop/OtherApp/CLAUDE.md"'
    )
    assert hits == [f"{_HOME}/Desktop/OtherApp/CLAUDE.md"]


def test_quoted_compound_command_with_only_safe_paths_is_clean():
    assert chk.find_hardcoded_paths(f'bash -c "grep -c x {_HOME}/.claude/hooks/_lib.py"') == []


# --------------------------------------------------------------------------
# find_hardcoded_paths — Blocker E: ~/.claude/projects/ is NEVER auto-safe
# --------------------------------------------------------------------------


def test_session_scoped_projects_path_is_flagged_even_though_it_is_under_claude_root():
    """A path under ~/.claude/projects/ (per-session transcripts, named
    after the session's own cwd) almost always encodes a real product
    repo's name, and is absent from every OTHER session — it must never be
    automatically safe just because it lives under ~/.claude/.
    """
    hits = chk.find_hardcoded_paths(
        'grep -rl "[stall] agent" '
        f"{_HOME}/.claude/projects/-Users-x-Desktop-ExampleApp/"
        "884000b8-293a-4be7-9ae6-85b2be304047/workflows"
    )
    assert hits == [
        f"{_HOME}/.claude/projects/-Users-x-Desktop-ExampleApp/"
        "884000b8-293a-4be7-9ae6-85b2be304047/workflows"
    ]


def test_other_claude_root_paths_remain_always_safe():
    assert chk.find_hardcoded_paths(f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py") == []


# --------------------------------------------------------------------------
# find_hardcoded_paths — Blocker 1 (round 6 review, 2026-08-28): a
# CASE-VARIANT spelling of the never-safe ~/.claude/projects/ root, which
# `str.startswith` cannot catch but a filesystem-identity test (this
# machine's default case-insensitive APFS: `~/.claude/PROJECTS` and
# `~/.claude/projects` are verified to be the SAME INODE) catches by
# construction, with no dedicated per-spelling patch.
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="requires a case-insensitive filesystem volume"
)
@pytest.mark.parametrize("spelling", ["PROJECTS", "Projects", "pRoJeCtS"])
def test_case_variant_spelling_of_never_safe_projects_root_is_flagged(spelling: str):
    hits = chk.find_hardcoded_paths(f"ls -1 {_HOME}/.claude/{spelling}")
    assert hits == [f"{_HOME}/.claude/{spelling}"], (spelling, hits)


@pytest.mark.skipif(
    not _CASE_INSENSITIVE_FS, reason="requires a case-insensitive filesystem volume"
)
def test_case_variant_never_safe_spelling_with_subpath_is_flagged():
    hits = chk.find_hardcoded_paths(
        f"grep -rl foo {_HOME}/.claude/PROJECTS/-Users-x-Desktop-App/workflows"
    )
    assert hits == [f"{_HOME}/.claude/PROJECTS/-Users-x-Desktop-App/workflows"]


# --------------------------------------------------------------------------
# find_hardcoded_paths — Regression 2 (round 6 review, 2026-08-28): the
# bare-directory-with-no-subpath hole a prior round fixed ONLY in
# validate_agentarch_ledger.py, never in this module — missing test
# coverage before this round.
# --------------------------------------------------------------------------


def test_bare_never_safe_directory_with_no_subpath_is_flagged():
    """`ls ~/.claude/projects` (the never-safe directory itself, no
    trailing separator, no subpath) must be flagged the same way a
    subpath under it is — this exact case previously returned `[]`."""
    hits = chk.find_hardcoded_paths(f"ls -1 {_HOME}/.claude/projects")
    assert hits == [f"{_HOME}/.claude/projects"]


def test_bare_never_safe_directory_trailing_slash_is_flagged():
    hits = chk.find_hardcoded_paths(f"ls -1 {_HOME}/.claude/projects/")
    assert hits == [f"{_HOME}/.claude/projects/"]


# --------------------------------------------------------------------------
# find_hardcoded_paths — Regression 3 (round 6 review, 2026-08-28): this
# module's own `/tmp` (no realpath) vs validate_agentarch_ledger's
# `/private/tmp` (realpath'd) disagreement used to make a legal `/tmp` scratch
# path spelled via its real macOS symlink target FALSE-POSITIVE as a
# hardcoded-repo-path violation.
# --------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_PRIVATE_TMP_ALIAS, reason="requires /private/tmp (macOS)")
def test_tmp_path_spelled_via_private_tmp_symlink_target_is_also_safe():
    assert chk.find_hardcoded_paths("cat /private/tmp/scratch/x.txt") == []


@pytest.mark.skipif(not _HAS_PRIVATE_TMP_ALIAS, reason="requires /private/tmp (macOS)")
def test_tmp_and_private_tmp_spellings_are_treated_identically():
    via_tmp = chk.find_hardcoded_paths("cat /tmp/scratch/x.txt")
    via_private_tmp = chk.find_hardcoded_paths("cat /private/tmp/scratch/x.txt")
    assert via_tmp == via_private_tmp == []


# --------------------------------------------------------------------------
# load_registry — Blocker G: a whitespace-containing root is rejected
# --------------------------------------------------------------------------


def test_load_registry_rejects_a_root_containing_whitespace(tmp_path: Path):
    """Substituting a whitespace-containing root into a command STRING and
    then `shlex.split`-ing it (the consumer's own parse step) would
    silently split the root into two arguments — reject it at load time
    instead, so it can never reach a substituted command string.

    Finding 2 (round-2 security review, 2026-08-30): the slug still never
    enters `registry` (unchanged — the mis-split-command hazard above is
    still fully guarded against), but the rejection is now ALSO reported
    via `rejections`, the same channel the other three rejection reasons
    (overbroad/nonexistent/no-`.git`) already use — see `load_registry`'s
    own docstring for why the prior "deliberately left out of rejections"
    framing left this codebase's own unqualified "never silently accepted"
    promise (repeated in `validate_agentarch_ledger.check_ledger`,
    `commands/sweep.md`, and `schedules/prompts/daily_sweep.txt`) false for
    exactly this one rejection reason.
    """
    clean_root = tmp_path / "CleanApp"
    clean_root.mkdir()
    _make_registrable_repo(clean_root)
    p = _write_registry(
        tmp_path,
        {"spacey": str(tmp_path / "My App"), "clean": str(clean_root)},
    )
    registry, rejections = chk.load_registry(str(p))
    assert "spacey" not in registry
    assert registry == {"clean": str(clean_root)}
    assert len(rejections) == 1
    assert rejections[0][0] == "spacey"
    assert "whitespace" in rejections[0][1]


def test_resolve_command_reports_unknown_slug_for_a_rejected_whitespace_root():
    # An empty registry stands in for "the whitespace root was rejected at
    # load time" — the referencing slug is simply absent either way.
    resolved, unknown = chk.resolve_command("grep -c x ${REPO:spacey}/CLAUDE.md", {})
    assert resolved is None
    assert unknown == ["spacey"]


# --------------------------------------------------------------------------
# resolve_command
# --------------------------------------------------------------------------


def test_resolve_command_substitutes_known_slug():
    registry = {"exampleapp": f"{_HOME}/Desktop/ExampleApp"}
    resolved, unknown = chk.resolve_command("grep -c seven ${REPO:exampleapp}/CLAUDE.md", registry)
    assert unknown == []
    assert resolved == f"grep -c seven {_HOME}/Desktop/ExampleApp/CLAUDE.md"


def test_resolve_command_reports_unknown_slug_and_returns_none():
    resolved, unknown = chk.resolve_command("grep -c x ${REPO:ghost}/CLAUDE.md", {})
    assert resolved is None
    assert unknown == ["ghost"]


def test_resolve_command_passthrough_with_no_placeholder():
    resolved, unknown = chk.resolve_command(f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py", {})
    assert unknown == []
    assert resolved == f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py"


def test_a_repo_added_later_needs_zero_code_change():
    """The registry is DATA: adding an entry the module has never seen
    before makes its metric resolve cleanly, with no code change at all.
    """
    registry = {"brandnewapp": f"{_HOME}/Desktop/BrandNewApp"}
    resolved, unknown = chk.resolve_command("grep -c x ${REPO:brandnewapp}/CLAUDE.md", registry)
    assert unknown == []
    assert resolved == f"grep -c x {_HOME}/Desktop/BrandNewApp/CLAUDE.md"


# --------------------------------------------------------------------------
# load_registry — never raises
# --------------------------------------------------------------------------


def test_load_registry_missing_file_returns_empty_dict(tmp_path: Path):
    registry, rejections = chk.load_registry(str(tmp_path / "does_not_exist.json"))
    assert registry == {}
    assert rejections == []


def test_load_registry_malformed_json_returns_empty_dict(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert rejections == []


@pytest.fixture
def home_repo_checkout():
    """A real repo-checkout-shaped directory (a `.git` entry) under
    $HOME/.cache, so `~`-expansion has a root that genuinely lives under $HOME.

    `~/.claude` used to play this part, but it only carries a `.git` entry in
    a git clone of the runtime: in a deployed checkout laid out without its
    history (an exported archive, a CI layout) `load_registry` correctly
    rejects it and the test saw `{}`. The root is created under $HOME, never
    pytest's tmp_path -- a tmp_path root cannot exercise `~`-expansion at
    all, and on Linux it sits under /tmp, an always-safe root. It lives in the
    user cache directory rather than the top of $HOME so a crashed run leaves
    nothing in the home directory itself.
    """
    cache = Path(_HOME) / ".cache"
    cache.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="agentarch-registry-fixture-", dir=str(cache)))
    try:
        _make_registrable_repo(root)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_load_registry_reads_and_expands_real_entries(tmp_path: Path, home_repo_checkout: Path):
    # Exercises `~`-expansion against an EXISTING repo checkout (Blocker 4
    # requires the root to actually look like one) that lives under $HOME.
    tilde_root = f"~/.cache/{home_repo_checkout.name}"
    p = _write_registry(tmp_path, {"myrepo": tilde_root})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {"myrepo": str(home_repo_checkout)}
    assert str(home_repo_checkout) == os.path.expanduser(tilde_root)
    assert rejections == []


# --------------------------------------------------------------------------
# load_registry — Blocker 4 (round 3 review, 2026-08-28): an unvalidated
# registry root can silently widen the live command-execution sandbox
# (validate_agentarch_ledger.run_metric_command, gated by guard_check's
# bounds check) to an operator's entire home directory or beyond.
# --------------------------------------------------------------------------


def test_load_registry_rejects_filesystem_root(tmp_path: Path):
    p = _write_registry(tmp_path, {"evil": "/"})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "evil"


def test_load_registry_rejects_home_directory_exactly(tmp_path: Path):
    p = _write_registry(tmp_path, {"evil": "~"})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "evil"


def test_load_registry_rejects_an_ancestor_of_home(tmp_path: Path):
    # An ancestor of $HOME (e.g. /Users on this machine) is exactly the
    # measured live exploit: registering it made
    # `guard_check('cat ~/.ssh/id_rsa', roots)` return legal.
    ancestor = str(Path.home().parent)
    p = _write_registry(tmp_path, {"evil": ancestor})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "evil"


def test_is_overbroad_root_rejects_double_slash_ancestor_spelling():
    """Blocker 4 (round 4 review, 2026-08-28): `_is_overbroad_root` used to
    take its input as already `abspath`-normalized, and `abspath` (unlike
    `realpath`) deliberately preserves a POSIX double leading slash — so
    `_is_overbroad_root("//Users")` returned False, only harmless today
    because `/Users/.git` happens not to exist (a coincidence, not a
    guarantee). Must reject regardless of caller normalization."""
    # Both spellings are built from this machine's real $HOME so the case
    # holds wherever HOME lives (the macOS or Linux home directory, a CI
    # runner's temp dir): prefixing one more "/" onto an absolute path yields
    # exactly the POSIX double-leading-slash spelling, once for an ancestor of
    # HOME and once for HOME itself.
    ancestor_spelling = "/" + str(Path.home().parent)
    home_spelling = "/" + str(Path.home())
    assert chk._is_overbroad_root(ancestor_spelling) is True
    assert chk._is_overbroad_root(home_spelling) is True


def test_load_registry_rejects_double_slash_ancestor_spelling(tmp_path: Path):
    """End-to-end: a `//`-spelled ancestor-of-home root must be rejected by
    the overbroad check itself, not merely by the unrelated, coincidental
    no-`.git`-in-/Users check one step later."""
    p = _write_registry(tmp_path, {"evil": "//Users"})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "evil"


def test_load_registry_rejects_home_subdir_typo_that_is_still_broad(tmp_path: Path):
    # A registered root that IS $HOME itself (e.g. a typo'd '~' where a real
    # repo subpath was intended) is rejected the same way as the bare '~'
    # case above, regardless of how the caller spelled it.
    p = _write_registry(tmp_path, {"evil": str(Path.home())})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "evil"


def test_load_registry_rejects_a_root_with_no_git_checkout(tmp_path: Path):
    # An existing, non-ancestor-of-home directory that is NOT a real repo
    # checkout (no .git) is still rejected — "existing directory" alone is
    # not enough; it must actually look like a repo.
    plain_dir = tmp_path / "NotARepo"
    plain_dir.mkdir()
    p = _write_registry(tmp_path, {"notarepo": str(plain_dir)})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "notarepo"
    assert ".git" in rejections[0][1]


def test_load_registry_rejects_a_nonexistent_root(tmp_path: Path):
    p = _write_registry(tmp_path, {"ghost": str(tmp_path / "does_not_exist_at_all")})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {}
    assert len(rejections) == 1 and rejections[0][0] == "ghost"


def test_load_registry_accepts_an_existing_real_repo_checkout(tmp_path: Path):
    real_repo = tmp_path / "RealApp"
    real_repo.mkdir()
    _make_registrable_repo(real_repo)
    p = _write_registry(tmp_path, {"realapp": str(real_repo)})
    registry, rejections = chk.load_registry(str(p))
    assert registry == {"realapp": str(real_repo)}
    assert rejections == []


# --------------------------------------------------------------------------
# root_is_acceptable — Finding 1 (round-2 security review, 2026-08-30): the
# ONE shared acceptance test both `load_registry` (above) and
# `validate_agentarch_ledger.py`'s CLI-extra-root path now call, so the two
# producers of the allowed-execution-roots set cannot drift apart on what
# counts as "a real repo checkout" the way they had (this module's own
# registry path required overbroad+isdir+`.git`; the CLI-extra-root path
# only checked overbroad+isdir, silently accepting e.g. `~/.ssh`).
# --------------------------------------------------------------------------


def test_root_is_acceptable_rejects_overbroad_root():
    ok, reason = chk.root_is_acceptable("~")
    assert not ok
    assert "overbroad" in reason


def test_root_is_acceptable_rejects_nonexistent_root(tmp_path: Path):
    ok, reason = chk.root_is_acceptable(str(tmp_path / "does_not_exist_at_all"))
    assert not ok
    assert "not an existing directory" in reason


def test_root_is_acceptable_rejects_a_directory_with_no_git_checkout(tmp_path: Path):
    plain_dir = tmp_path / "NotARepo"
    plain_dir.mkdir()
    ok, reason = chk.root_is_acceptable(str(plain_dir))
    assert not ok
    assert ".git" in reason


def test_root_is_acceptable_accepts_a_real_repo_checkout(tmp_path: Path):
    real_repo = tmp_path / "RealApp"
    real_repo.mkdir()
    _make_registrable_repo(real_repo)
    ok, result = chk.root_is_acceptable(str(real_repo))
    assert ok, result
    assert result == str(real_repo)


def test_root_is_acceptable_normalizes_a_tilde_relative_root(tmp_path: Path, monkeypatch):
    # Callers pass the RAW (possibly ~-relative) root; the helper expands
    # and realpaths it internally rather than requiring pre-normalization.
    # A retargeted $HOME (unrelated to this machine's real home) keeps the
    # overbroad check meaningless-but-harmless here: tmp_path/RealApp is
    # never an ancestor of the REAL $HOME `_is_overbroad_root` guards
    # against, regardless of what `~` expands to for this one call.
    monkeypatch.setenv("HOME", str(tmp_path))
    real_repo = tmp_path / "RealApp"
    real_repo.mkdir()
    _make_registrable_repo(real_repo)
    ok, result = chk.root_is_acceptable("~/RealApp")
    assert ok, result
    assert result == os.path.realpath(str(real_repo))


def test_check_ledger_overbroad_registry_root_never_reaches_guard_legal(tmp_path: Path):
    """The full, end-to-end falsifiability repro for Blocker 4: registering
    an over-broad root must never make an out-of-repo command guard-legal.
    Exercised via validate_agentarch_ledger.guard_check directly (the actual
    gate `run_metric_command`'s subprocess execution sits behind), since
    this module's own `check_ledger` never runs a command itself.
    """
    import validate_agentarch_ledger as val  # local import: sibling module under test

    for overbroad_root in ("~", str(Path.home().parent), str(Path.home())):
        p = _write_registry(tmp_path, {"evil": overbroad_root})
        registry, rejections = chk.load_registry(str(p))
        assert registry == {}, (overbroad_root, registry)
        assert len(rejections) == 1 and rejections[0][0] == "evil"
        ok, _reason = val.guard_check("cat ~/.ssh/id_rsa", repo_root=list(registry.values()) or None)
        assert not ok, overbroad_root


# --------------------------------------------------------------------------
# check_ledger — whole-file behavior, RED then GREEN
# --------------------------------------------------------------------------


def test_check_ledger_RED_on_hardcoded_path(tmp_path: Path):
    # Finding #4 (round 6 review, 2026-08-28): a synthetic, registrable
    # fixture repo under tmp_path — NEVER a real product-repo path that
    # merely happens to exist on THIS operator's machine (the previous
    # version of this test registered `~/Desktop/OtherApp` and passed only
    # because that specific directory is a real git checkout here; it would
    # fail on a fresh clone or a different machine).
    agency = tmp_path / "Agency"
    agency.mkdir()
    _make_registrable_repo(agency)
    ledger = _write_ledger(
        tmp_path,
        [_row(id="AA-0001", metric_command=f'grep -rl "x" {agency}/.claude/agents')],
    )
    registry = _write_registry(tmp_path, {"agency": str(agency)})
    violations = chk.check_ledger(str(ledger), str(registry))
    assert len(violations) == 1
    assert "hardcoded-repo-path" in violations[0]
    assert "AA-0001" in violations[0]


def test_check_ledger_GREEN_on_placeholder_form_with_matching_registry(tmp_path: Path):
    # Finding #4: see test_check_ledger_RED_on_hardcoded_path's comment —
    # this test's GREEN assertion depends on the registry actually
    # ACCEPTING the "agency" root (it must look like a real `.git` checkout,
    # per Blocker 4), so it needs the registrable-fixture helper, not a
    # real machine path.
    agency = tmp_path / "Agency"
    agency.mkdir()
    _make_registrable_repo(agency)
    ledger = _write_ledger(
        tmp_path,
        [_row(id="AA-0001", metric_command='grep -rl "x" ${REPO:agency}/.claude/agents')],
    )
    registry = _write_registry(tmp_path, {"agency": str(agency)})
    assert chk.check_ledger(str(ledger), str(registry)) == []


def test_check_ledger_flags_unknown_repo_slug(tmp_path: Path):
    # Finding #4: same fixture-based registration as its siblings above,
    # for consistency — never a real machine path.
    agency = tmp_path / "Agency"
    agency.mkdir()
    _make_registrable_repo(agency)
    ledger = _write_ledger(
        tmp_path,
        [_row(id="AA-0001", metric_command='grep -rl "x" ${REPO:ghost}/.claude/agents')],
    )
    registry = _write_registry(tmp_path, {"agency": str(agency)})
    violations = chk.check_ledger(str(ledger), str(registry))
    assert any("unknown-repo-slug" in v and "AA-0001" in v for v in violations)


def test_check_ledger_missing_registry_reports_one_unknown_slug_violation_per_row(tmp_path: Path):
    ledger = _write_ledger(
        tmp_path,
        [
            _row(id="AA-0001", metric_command="grep -c x ${REPO:agency}/CLAUDE.md"),
            _row(id="AA-0002", metric_command="grep -c y ${REPO:exampleapp}/CLAUDE.md"),
        ],
    )
    violations = chk.check_ledger(str(ledger), str(tmp_path / "no_such_registry.json"))
    assert len(violations) == 2
    assert all("unknown-repo-slug" in v for v in violations)


def test_check_ledger_missing_registry_is_fine_for_a_runtime_only_ledger(tmp_path: Path):
    """Required property: a runtime-only metric (no ${REPO:...} anywhere)
    must keep working with no repo, and therefore no registry, present at
    all — a missing registry file must never fail a ledger that never
    needed it.
    """
    ledger = _write_ledger(tmp_path, [_row(id="AA-0001")])  # no placeholder
    violations = chk.check_ledger(str(ledger), str(tmp_path / "no_such_registry.json"))
    assert violations == []


def test_check_ledger_ignores_blank_lines_and_bad_json(tmp_path: Path):
    p = tmp_path / "ledger.jsonl"
    p.write_text('\n{"not": "a full row"}\nnot even json\n')
    violations = chk.check_ledger(str(p), _REAL_REGISTRY)
    assert any("json-parse-error" in v for v in violations)


def test_main_exit_code_matches_violation_count(tmp_path: Path, capsys):
    clean_ledger = _write_ledger(tmp_path, [_row(id="AA-0001")])
    rc = chk.main([str(tmp_path), str(clean_ledger), _REAL_REGISTRY])
    assert rc == 0
    dirty_ledger = _write_ledger(
        tmp_path,
        [_row(id="AA-0001", metric_command=f"grep -c x {_HOME}/Desktop/OtherApp/CLAUDE.md")],
    )
    rc = chk.main([str(tmp_path), str(dirty_ledger), _REAL_REGISTRY])
    assert rc == 1
    out = capsys.readouterr().out
    assert "hardcoded-repo-path" in out


def test_main_never_raises_on_totally_missing_ledger():
    rc = chk.main(["x", "/no/such/ledger.jsonl", _REAL_REGISTRY])
    assert rc == 1


# --------------------------------------------------------------------------
# migrated-ledger PROPERTY: a correctly-migrated ledger (every metric_command
# expressed via ${REPO:<slug>} and registered) is clean (Blocker 1, round 8
# review, 2026-08-30)
# --------------------------------------------------------------------------
#
# This used to assert `chk.check_ledger(_REAL_LEDGER, _REAL_REGISTRY) == []`
# directly against the LIVE, in-progress ledger migration — a green that was
# only reproducible from a dirty working tree (the ledger's own migration to
# ${REPO:<slug>} form is a separate, larger, unrelated diff bundling
# status/claim/checked_at changes from a different workstream, not yet
# committed): against HEAD's actually-committed content, this exact call
# found 16 real hardcoded-repo-path violations. A unit test whose green
# depends on uncommitted working-tree state is not reproducible from the
# committed tree, which this suite's own falsifiability standard requires.
#
# "Is the REAL ledger currently clean" already has its enforcement home:
# schedules/prompts/daily_sweep.txt's daily job runs the standalone CLI
# directly and treats a non-zero exit as a finding — that is where a
# live-data check belongs, not here. This test instead proves the PROPERTY
# the module claims — a ledger whose every metric_command is correctly
# expressed via ${REPO:<slug>} and registered is clean — against a small,
# synthetic, fully self-contained fixture that is reproducible from any
# commit, on any machine, regardless of the real ledger's migration state.


def test_migrated_ledger_property_synthetic_fixture_is_clean(tmp_path: Path):
    repo = tmp_path / "SomeRepo"
    repo.mkdir()
    _make_registrable_repo(repo)
    (repo / "CLAUDE.md").write_text("hello world\n")
    registry = _write_registry(tmp_path, {"somerepo": str(repo)})
    ledger = _write_ledger(
        tmp_path,
        [
            _row(id="AA-0001", metric_command="grep -c hello ${REPO:somerepo}/CLAUDE.md"),
            _row(
                id="AA-0002",
                metric_command=f"grep -c HEARTBEAT {_HOME}/.claude/hooks/_lib.py",
            ),
        ],
    )
    assert chk.check_ledger(str(ledger), str(registry)) == []


# --------------------------------------------------------------------------
# BLOCKER 1 (round-7 security review, 2026-08-30) — the single left-to-right
# CONSUMING scan (`classify_tokens`) had ZERO falsifying test coverage of
# its own consumption mechanism. The reviewer's own confirmed mutation:
# `spec.arity >= 1 and i < n and (boundary is None or i < boundary)` gained
# an extra `and tokens[i] not in grammar.flags` clause — i.e. a value-consuming
# flag's OWN VALUE is no longer consumed when that value token happens to
# TEXTUALLY SPELL another recognized flag for the same form (e.g. the SECOND
# `-e` in `-e -e X`) — reverting to round-4's non-consuming, occurrence-blind
# design. All 258 tests in this suite and test_validate_agentarch_ledger.py
# still passed against that mutation, because every existing doubled-flag
# test uses a `..`-traversal payload, which is caught by a COMPLETELY
# DIFFERENT check (`flag_value_shape_needs_bounds_check`'s traversal clause)
# regardless of whether the consuming scan itself works. These tests use a
# PLAIN relative bare filename instead (no `..`, no leading `/`/`~`) — a
# shape that shape-based checks never catch — so ONLY a working consuming
# scan can classify it correctly.
#
# These are DIRECT, pure unit tests on `classify_tokens` itself (never
# touches the filesystem, never depends on cwd) — the precise mechanism
# under test, not a downstream consumer's derived legality. See
# test_validate_agentarch_ledger.py's own BLOCKER 1 section for the paired
# end-to-end `guard_check` falsifying tests (which DO need cwd — and,
# critically, an untrusted one that is NOT `tmp_path`; see that section's
# own comment for why).
# --------------------------------------------------------------------------


def test_classify_tokens_doubled_dash_e_flag_consumes_its_own_value_grep():
    """THE mutation-killing assertion: with the shipped consuming scan, the
    SECOND `-e` is `FLAG_VALUE` (the first `-e`'s own value) — never
    re-classified as its own `FLAG`. Under the described mutation (adding
    `tokens[i] not in grammar.flags` to the consumption condition), the
    second `-e` — which DOES spell a recognized flag — would stay
    unconsumed and get reclassified as `FLAG` on the next loop iteration,
    which is exactly what this assertion catches: it pins `roles[2].kind`
    to `"FLAG_VALUE"`, not `"FLAG"`.
    """
    roles = chk.classify_tokens("grep", ["-c", "-e", "-e", "secret.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]
    assert roles[2].is_path_designated is False


def test_classify_tokens_doubled_dash_e_flag_consumes_its_own_value_grep_cluster():
    """Same mutation-killing shape via the `-rl` cluster lead flag (the
    reviewer's own second demonstrated repro, `grep -rl -e -e secretdir`)."""
    roles = chk.classify_tokens("grep", ["-rl", "-e", "-e", "secretdir"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


def test_classify_tokens_doubled_dash_e_flag_consumes_its_own_value_rg():
    roles = chk.classify_tokens("rg", ["-c", "-e", "-e", "secret.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


def test_classify_tokens_doubled_dash_g_flag_consumes_its_own_value_rg():
    """rg's OWN value-consuming `-g GLOB` flag (a different letter than
    `-e`), proving the fix is general, not hardcoded to one flag."""
    roles = chk.classify_tokens("rg", ["-c", "-g", "-g", "secretfile.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


def test_classify_tokens_doubled_dash_r_flag_consumes_its_own_value_rg():
    roles = chk.classify_tokens("rg", ["-c", "-r", "-r", "secretfile.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


def test_classify_tokens_doubled_dash_E_flag_consumes_its_own_value_rg():
    roles = chk.classify_tokens("rg", ["-c", "-E", "-E", "secretfile.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


def test_classify_tokens_doubled_dash_n_flag_consumes_its_own_value_git():
    """git log's own value-consuming `-n COUNT` flag — git has no
    positional role at all, so this isolates the consuming-scan mechanism
    from the grep/rg pattern-role logic entirely."""
    roles = chk.classify_tokens("git", ["-n", "-n", "secretfile.txt"])
    assert [r.kind for r in roles] == ["FLAG", "FLAG_VALUE", "PATH_CANDIDATE"]


# --------------------------------------------------------------------------
# F3 (round-7 security review, 2026-08-30) — `find_hardcoded_paths`'s own
# docstring (escape 4) unconditionally promises every token carrying a
# `${REPO:<slug>}` placeholder is checked for a `..`-shaped remainder, but
# the `POSITIONAL_ROLE` branch used to `continue` (exempt) BEFORE that
# check could ever run, whenever the token didn't start with `/`/`~` — true
# of every placeholder token, since `${` is neither. Verified live, pre-fix:
# `grep -c ${REPO:agency}/../../.ssh/known_hosts ~/.claude/CLAUDE.md` (a
# grep PATTERN-position token) returned `[]` — the traversal-shaped
# placeholder token was silently exempted, never reaching the sentinel
# substitution/traversal check at all.
# --------------------------------------------------------------------------


def test_placeholder_traversal_in_positional_role_position_is_flagged_F3():
    hits = chk.find_hardcoded_paths(
        f"grep -c ${{REPO:agency}}/../../.ssh/known_hosts {_HOME}/.claude/CLAUDE.md"
    )
    assert hits == ["${REPO:agency}/../../.ssh/known_hosts"]


def test_placeholder_no_traversal_in_positional_role_position_stays_clean_F3():
    """Paired recovery case: the identical PATTERN-position placeholder
    shape with no `..` remainder must stay clean, unaffected by the F3 fix
    — proves the fix targets the traversal SHAPE, not every placeholder in
    positional-role position."""
    hits = chk.find_hardcoded_paths(
        f"grep -c ${{REPO:agency}}/foo/bar {_HOME}/.claude/CLAUDE.md"
    )
    assert hits == []
