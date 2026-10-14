"""Tests for gh_issue.sh resolve's --evidence-repo flag (#5066, 2026-09-07).

An issue on this board whose fix lands in a DIFFERENT local repo (the runtime,
per the §13 filing convention) was un-closable: resolve's fabricated-resolution
guard verified the cited sha against the CWD repo only (#5055 was live proof).
--evidence-repo <path> redirects WHICH repo's git graph the guard consults —
never weakening it — and stamps an explicit "Evidence repo:" trailer into the
posted close comment so the record names where the commits live.

Same conventions as test_gh_issue_dispose.py: the real script runs with a
stubbed `gh` on PATH recording argv, so shapes are asserted without network.
The script path honors GH_ISSUE_SCRIPT so the suite can run against a scratch
copy pre-install; default is the live helper.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = os.environ.get(
    "GH_ISSUE_SCRIPT", str(Path.home() / ".claude" / "scripts" / "gh_issue.sh")
)

_GH_STUB_OK = """#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "issue" ] && [ "$2" = "comment" ]; then
  # capture the body file's content so trailer assertions see it
  while [ $# -gt 0 ]; do
    if [ "$1" = "--body-file" ]; then cat "$2" >> "$GH_BODY_LOG"; fi
    shift
  done
fi
exit 0
"""


def _mkrepo(path: Path) -> str:
    """A throwaway git repo with one commit; returns the commit sha."""
    path.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    # Content includes the repo path: two same-second genesis commits with
    # identical trees/messages/authors hash IDENTICALLY across repos, which
    # made the foreign-sha baseline test vacuous (the "foreign" sha existed
    # in both graphs). Distinct content per repo keeps every sha repo-local.
    (path / "f.txt").write_text(f"x {path}\n")
    subprocess.run(["git", "-C", str(path), "add", "f.txt"], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "genesis"], check=True, env=env
    )
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return out.stdout.strip()


def _run(tmp_path: Path, cwd: Path, *args: str):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "gh"
    stub.write_text(_GH_STUB_OK)
    stub.chmod(0o755)
    gh_log = tmp_path / "gh.log"
    body_log = tmp_path / "gh_body.log"
    gh_log.touch()
    body_log.touch()
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GH_LOG": str(gh_log),
        "GH_BODY_LOG": str(body_log),
    }
    proc = subprocess.run(
        ["bash", SCRIPT, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc, gh_log.read_text(), body_log.read_text()


def _body(tmp_path: Path) -> Path:
    f = tmp_path / "resolution.md"
    f.write_text("**What:** fixed.\n")
    return f


class TestEvidenceRepoGuard:
    def test_default_guard_unchanged_rejects_foreign_sha(self, tmp_path):
        """Baseline: without the flag, a sha from ANOTHER repo still refuses."""
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        other_sha = _mkrepo(other)
        proc, gh_log, _ = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", other_sha,
            "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode != 0
        assert "not found in this repo" in proc.stderr
        assert "close" not in gh_log

    def test_evidence_repo_verifies_sha_there_and_closes(self, tmp_path):
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        other_sha = _mkrepo(other)
        proc, gh_log, body = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", other_sha,
            "--evidence-repo", str(other), "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode == 0, proc.stderr
        assert "issue comment 1" in gh_log
        assert "issue close 1" in gh_log
        assert "evidence repo" in proc.stdout

    def test_evidence_repo_still_rejects_a_fabricated_sha(self, tmp_path):
        """The flag redirects the guard; it never weakens it."""
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        _mkrepo(other)
        proc, gh_log, _ = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", "deadbeef1234567",
            "--evidence-repo", str(other), "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode != 0
        assert "not found in evidence repo" in proc.stderr
        assert "close" not in gh_log

    def test_evidence_repo_must_be_a_git_repo(self, tmp_path):
        cwd_repo = tmp_path / "board"
        notrepo = tmp_path / "plain"
        _mkrepo(cwd_repo)
        notrepo.mkdir()
        sha = "0" * 40
        proc, gh_log, _ = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", sha,
            "--evidence-repo", str(notrepo), "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode != 0
        assert "not a git repository" in proc.stderr
        assert "close" not in gh_log

    def test_close_comment_carries_evidence_repo_trailer(self, tmp_path):
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        other_sha = _mkrepo(other)
        proc, _, body = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", other_sha,
            "--evidence-repo", str(other), "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode == 0, proc.stderr
        assert "**What:** fixed." in body
        assert "Evidence repo:" in body
        assert "verified against THAT repo" in body


    def test_temp_body_file_cleaned_up_after_resolve(self, tmp_path):
        """Review blocker: the mktemp'd augmented body leaked on every path.
        A unique marker rides the body; after a successful --evidence-repo
        resolve, no recent file in the REAL temp dir may contain it (macOS
        mktemp ignores TMPDIR, so we sweep the actual location by marker)."""
        import glob
        import tempfile
        import uuid

        marker = f"CLEANUP-MARKER-{uuid.uuid4()}"
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        other_sha = _mkrepo(other)
        body = tmp_path / "resolution.md"
        body.write_text(f"**What:** fixed. {marker}\n")
        proc, _, captured = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", other_sha,
            "--evidence-repo", str(other), "--body-file", str(body),
        )
        assert proc.returncode == 0, proc.stderr
        assert marker in captured  # the augmented body genuinely carried it
        real_tmp = os.path.realpath(tempfile.gettempdir())
        leaked = []
        for cand in glob.glob(os.path.join(real_tmp, "tmp.*")):
            try:
                with open(cand, "r", errors="ignore") as fh:
                    if marker in fh.read():
                        leaked.append(cand)
            except OSError:
                continue
        assert leaked == [], f"augmented body file leaked: {leaked}"

    def test_evidence_repo_dot_git_path_no_raw_fatal_on_stderr(self, tmp_path):
        """Review nit 2: pointing at <repo>/.git used to leak a bare git
        'fatal:' to stderr while still closing. The toplevel resolution is
        now stderr-suppressed; the fallback trailer path still fires."""
        cwd_repo = tmp_path / "board"
        other = tmp_path / "other"
        _mkrepo(cwd_repo)
        other_sha = _mkrepo(other)
        proc, _, body = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", other_sha,
            "--evidence-repo", str(other / ".git"), "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode == 0, proc.stderr
        assert "fatal:" not in proc.stderr
        assert "Evidence repo:" in body

    def test_no_flag_no_trailer(self, tmp_path):
        cwd_repo = tmp_path / "board"
        sha = _mkrepo(cwd_repo)
        proc, _, body = _run(
            tmp_path, cwd_repo, "resolve", "1", "--commit", sha,
            "--body-file", str(_body(tmp_path)),
        )
        assert proc.returncode == 0, proc.stderr
        assert "**What:** fixed." in body
        assert "Evidence repo:" not in body
