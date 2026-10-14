"""Major 14: _project_dir_name must mirror Claude Code's ACTUAL project
directory naming (verified 2026-09-27 against real folders in
~/.claude/projects by cross-referencing transcripts' own `cwd` field, never
guessed): '/', '_', '.', and space all become '-'. Also: default globs
must include project dirs for subfolders/worktrees of a home (any
`~/.claude/projects/<prefix>*`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harvest_tool_trail as htt  # noqa: E402


# --------------------------------------------------------------------------
# _project_dir_name: verified against real ~/.claude/projects pairs
# --------------------------------------------------------------------------


def test_slash_becomes_dash():
    assert htt._project_dir_name(Path("/Users/x/Desktop/OtherApp")) == "-Users-x-Desktop-OtherApp"


def test_underscore_becomes_dash_maplewood_gtm():
    """RED-check: revert _project_dir_name to `str(home).replace('/', '-')`
    (the pre-major-14 version, '/' only) and this fails -- 'Maplewood_GTM'
    contains an underscore that must also become '-'."""
    assert htt._project_dir_name(Path("/Users/x/Desktop/Maplewood_GTM")) == "-Users-x-Desktop-Maplewood-GTM"


def test_underscore_becomes_dash_opswell_gtm():
    assert htt._project_dir_name(Path("/Users/x/Desktop/Opswell_GTM")) == "-Users-x-Desktop-Opswell-GTM"


def test_underscore_becomes_dash_google_ads_review_dir():
    """The real Brightline legacy working directory name."""
    assert (
        htt._project_dir_name(Path("/Users/x/Desktop/Brightline/Legacy_Workdir_2026_09_25"))
        == "-Users-x-Desktop-Brightline-Legacy-Workdir-2026-09-25"
    )


def test_dot_becomes_dash_worktree_path():
    """RED-check: without the '.' -> '-' mapping, a worktree cwd
    ".../BuildwiseAI/.claude/worktrees/x" would derive
    "...-BuildwiseAI-.claude-worktrees-x" (a single dash before
    'claude', with a literal dot preserved) instead of the real
    "...-BuildwiseAI--claude-worktrees-x" (double dash -- the dot
    ALSO became a dash). This is verified against a REAL pair from
    ~/.claude/projects: cwd .../BuildwiseAI/.claude/worktrees/agent-...
    -> dir -Users-x-Desktop-BuildwiseAI--claude-worktrees-agent-..."""
    result = htt._project_dir_name(Path("/Users/x/Desktop/BuildwiseAI/.claude/worktrees/x"))
    assert result == "-Users-x-Desktop-BuildwiseAI--claude-worktrees-x"
    assert "." not in result


def test_space_becomes_dash():
    """Verified against the real pair: cwd '.../Desktop/other project'
    -> dir '-Users-x-Desktop-other-project' (space -> dash)."""
    assert htt._project_dir_name(Path("/Users/x/Desktop/other project")) == "-Users-x-Desktop-other-project"


# --------------------------------------------------------------------------
# _matching_project_dirs: subfolder/worktree prefix matching
# --------------------------------------------------------------------------


def test_matching_project_dirs_includes_worktree_subfolder(tmp_path, monkeypatch):
    """RED-check: change _matching_project_dirs to only look for an EXACT
    name match (p.name == prefix_name) and this fails -- a worktree
    subfolder's derived dir name is a PREFIX match, not an exact one."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    exact_dir = projects_root / "-Users-x-Desktop-BuildwiseAI"
    exact_dir.mkdir()
    worktree_dir = projects_root / "-Users-x-Desktop-BuildwiseAI--claude-worktrees-agent-ab12cd34"
    worktree_dir.mkdir()
    unrelated_dir = projects_root / "-Users-x-Desktop-SomeOtherRepo"
    unrelated_dir.mkdir()

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    # _matching_project_dirs computes Path.home() / ".claude" / "projects",
    # so make tmp_path/.claude/projects the real location the function reads.
    real_claude_projects = tmp_path / ".claude" / "projects"
    real_claude_projects.mkdir(parents=True)
    for d in (exact_dir, worktree_dir, unrelated_dir):
        (real_claude_projects / d.name).mkdir()

    matches = htt._matching_project_dirs("-Users-x-Desktop-BuildwiseAI")
    match_names = {p.name for p in matches}
    assert "-Users-x-Desktop-BuildwiseAI" in match_names
    assert "-Users-x-Desktop-BuildwiseAI--claude-worktrees-agent-ab12cd34" in match_names
    assert "-Users-x-Desktop-SomeOtherRepo" not in match_names


def test_matching_project_dirs_falls_back_to_exact_when_nothing_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    matches = htt._matching_project_dirs("-Users-x-Desktop-NoSuchRepo")
    assert len(matches) == 1
    assert matches[0].name == "-Users-x-Desktop-NoSuchRepo"


# --------------------------------------------------------------------------
# #26: the directory-NAME prefix match is separator-bounded but otherwise
# permissive by design -- it is candidate DISCOVERY only. Real membership
# (excluding an unrelated same-prefix sibling) is decided later, per
# transcript, by _transcript_cwd_is_under_home -- see the fixture tests
# below this section.
# --------------------------------------------------------------------------


def test_matches_project_dir_prefix_unit_cases():
    assert htt._matches_project_dir_prefix("-Users-x-Desktop-Repo", "-Users-x-Desktop-Repo") is True
    assert htt._matches_project_dir_prefix("-Users-x-Desktop-Repo--claude-worktrees-x", "-Users-x-Desktop-Repo") is True
    # #26 (regression fix): a real subfolder session dir (e.g. a repo
    # subfolder or a human-dated one) is a separator-bounded prefix match
    # at the DIRECTORY-NAME level -- discovery is deliberately permissive
    # here; distinguishing a real subfolder from an unrelated sibling that
    # merely shares the same string prefix happens later, against the
    # transcript's own cwd (see test_matching_project_dirs_includes... /
    # test_transcript_cwd_under_home_... below).
    assert htt._matches_project_dir_prefix("-Users-x-Desktop-Repo-Sale-2026", "-Users-x-Desktop-Repo") is True
    assert htt._matches_project_dir_prefix("-Users-x-Desktop-RepoOther", "-Users-x-Desktop-Repo") is False
    # A prefix immediately followed by a bare trailing dash and nothing
    # else is not a real sub-component -- guarded by the length check.
    assert htt._matches_project_dir_prefix("-Users-x-Desktop-Repo-", "-Users-x-Desktop-Repo") is False


# --------------------------------------------------------------------------
# #26: real membership is settled on the transcript's OWN recorded cwd,
# never on the directory-name match alone
# --------------------------------------------------------------------------


def test_transcript_cwd_under_home_kept(tmp_path):
    """A transcript whose own recorded cwd is a real subfolder of `home`
    is kept."""
    home = tmp_path / "Desktop" / "BuildwiseAI"
    (home / "repo_tooling" / "demo_video").mkdir(parents=True)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps({"cwd": str(home / "repo_tooling" / "demo_video"), "sessionId": "s1"}) + "\n",
        encoding="utf-8",
    )
    assert htt._transcript_cwd_is_under_home(transcript, home) is True


def test_transcript_cwd_sibling_folder_excluded(tmp_path):
    """RED-check: remove the cwd-based filter entirely (or replace
    is_relative_to with a bare string-prefix check) and this fails -- a
    transcript whose cwd is a completely different, unrelated sibling
    folder that merely shares the home's own path as a STRING prefix
    (e.g. 'BuildwiseAI' vs 'BuildwiseAI-Sale-2026') must be
    excluded, even though its DERIVED project-dir name also shares that
    string prefix."""
    home = tmp_path / "Desktop" / "BuildwiseAI"
    home.mkdir(parents=True)
    sibling = tmp_path / "Desktop" / "BuildwiseAI-Sale-2026"
    sibling.mkdir(parents=True)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps({"cwd": str(sibling), "sessionId": "s1"}) + "\n",
        encoding="utf-8",
    )
    assert htt._transcript_cwd_is_under_home(transcript, home) is False


def test_resolve_transcript_paths_excludes_sibling_but_keeps_subfolder(tmp_path, monkeypatch):
    """End-to-end: resolve_transcript_paths keeps a real subfolder
    session's transcript and drops a same-prefix sibling's, using the
    actual glob + cwd-narrowing pipeline together."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    real_claude_projects = tmp_path / ".claude" / "projects"
    real_claude_projects.mkdir(parents=True)

    home = tmp_path / "Desktop" / "BuildwiseAI"
    home.mkdir(parents=True)
    subfolder = home / "repo_tooling" / "demo_video"
    subfolder.mkdir(parents=True)
    sibling = tmp_path / "Desktop" / "BuildwiseAI-Sale-2026"
    sibling.mkdir(parents=True)

    prefix = htt._project_dir_name(home)
    subfolder_dir_name = f"{prefix}-repo-tooling-demo-video"
    sibling_dir_name = htt._project_dir_name(sibling)

    subfolder_project_dir = real_claude_projects / subfolder_dir_name
    subfolder_project_dir.mkdir()
    (subfolder_project_dir / "transcript.jsonl").write_text(
        json.dumps({"cwd": str(subfolder), "sessionId": "s1"}) + "\n", encoding="utf-8",
    )

    sibling_project_dir = real_claude_projects / sibling_dir_name
    sibling_project_dir.mkdir()
    (sibling_project_dir / "transcript.jsonl").write_text(
        json.dumps({"cwd": str(sibling), "sessionId": "s2"}) + "\n", encoding="utf-8",
    )

    paths = htt.resolve_transcript_paths([], homes={"acme": home})
    path_strs = [str(p) for p in paths]

    assert any(subfolder_dir_name in p for p in path_strs)
    assert not any(sibling_dir_name in p for p in path_strs)


def test_resolve_transcript_paths_reads_each_transcripts_cwd_only_once(tmp_path, monkeypatch):
    """Nit fix: a transcript's `cwd` must be read ONCE by
    resolve_transcript_paths regardless of how many homes are registered --
    the prior version called `_transcript_cwd_is_under_home` once PER HOME
    (inside `any(... for home in all_homes)`), reopening and re-parsing the
    same file from scratch each time; a transcript matching none of them
    was opened `len(homes) + 1` times (once per home, plus the OSError
    early-open before any home check).

    RED-check: revert `resolve_transcript_paths`'s narrowing step to
    `[p for p in paths if any(_transcript_cwd_is_under_home(p, home) for
    home in all_homes)]` (its pre-fix shape) and this fails -- with 3
    registered homes, the one transcript (matching none of them) is opened
    3 times instead of 1."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    real_claude_projects = tmp_path / ".claude" / "projects"
    real_claude_projects.mkdir(parents=True)

    homes = {}
    for name in ("acme", "beta", "gamma"):
        home = tmp_path / "Desktop" / name
        home.mkdir(parents=True)
        homes[name] = home

    # One glob-discovered transcript whose recorded cwd matches NONE of
    # the three homes -- it sits in a project dir keyed off the FIRST
    # home's own prefix (so the glob still finds it) but its own cwd
    # points somewhere else entirely, so the narrowing step must check it
    # against all three homes before dropping it.
    acme_prefix = htt._project_dir_name(homes["acme"])
    project_dir = real_claude_projects / acme_prefix
    project_dir.mkdir()
    unrelated_cwd = tmp_path / "Desktop" / "unrelated-elsewhere"
    unrelated_cwd.mkdir(parents=True)
    transcript = project_dir / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"cwd": str(unrelated_cwd), "sessionId": "s1"}) + "\n", encoding="utf-8",
    )

    open_count = 0
    real_open = open

    def _counting_open(path, *args, **kwargs):
        nonlocal open_count
        if str(path) == str(transcript):
            open_count += 1
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _counting_open)

    paths = htt.resolve_transcript_paths([], homes=homes)

    assert not any(str(transcript) == str(p) for p in paths), (
        "the unrelated-cwd transcript must be narrowed out (it matches none of the 3 homes)"
    )
    assert open_count == 1, f"expected exactly 1 open() call for one transcript across 3 homes, got {open_count}"


def test_default_globs_for_homes_includes_worktree_subfolder_globs(tmp_path, monkeypatch):
    """End-to-end: default_globs_for_homes must emit glob patterns that
    would match a worktree subfolder's transcript files, not just the
    home's own exact project dir."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    real_claude_projects = tmp_path / ".claude" / "projects"
    real_claude_projects.mkdir(parents=True)

    home = tmp_path / "Desktop" / "SomeRepo"
    exact_name = htt._project_dir_name(home)
    worktree_name = f"{exact_name}--claude-worktrees-agent-deadbeef01"
    (real_claude_projects / exact_name).mkdir()
    (real_claude_projects / worktree_name).mkdir()

    globs = htt.default_globs_for_homes({"acme": home})
    assert any(worktree_name in g for g in globs)
    assert any(exact_name in g and worktree_name not in g for g in globs)
