#!/usr/bin/env python3
"""kb_sync_report.py - weekly report of runtime knowledge-base drift against Agency's doctrine corpus.

Plan C unit C9 (epic OtherApp #5496, finding C-7). Runs directly under launchd
(`schedules/com.oversight.agency.kbsync.plist`), not through `run_oversight_job.sh`
(that wrapper launches a `claude -p` prompt; this job needs no model).

What it reads (never writes) under the OtherApp repo's
`agency/backend/agents/knowledge/doctrine/`:
  * every `agnostic/<lane>/PORT_SOURCES.md` block that records `runtime path` +
    `runtime sha` (the origin recorded by `scripts/doctrine_port.py`);
  * every `industry/dental/<lane>/SOURCES.md` overlay that cites a runtime file
    (`~/.claude/...`) with a read date.

What it reports, from `git -C <runtime root> log --name-status <sha>..HEAD -- <path>`:
  * "re-port"               a direct port whose runtime original changed since its sha;
  * "rewrite review needed" a `rewritten: yes` source whose runtime original changed
                            (the rewrite is hand-reviewed, never re-ported);
  * "overlay review needed" a runtime file an overlay cites changed after the overlay's
                            read date (end of that day; same-day edits are not flagged);
  * "cannot compare"        a recorded sha is unreachable -> a failure, not a change;
  * never-ported files      include-list runtime files no PORT_SOURCES block mentions
                            (informational, never triggers a comment on its own);
  * repo-sourced blocks     Plan B blocks that record `repo path`/`repo sha` are skipped
                            and reported once as "repo-sourced, not tracked by this sync".

Posts ONE comment on OtherApp #5496 only when a re-port / rewrite / overlay item exists.
Writes no Agency file. Honors `schedules/DISABLED` and `schedules/DISABLED.kbsync`.
Writes its own heartbeat (six required keys, UTC `...Z`; `--manual` writes `manual-<job>.json` instead): a START stub first, the END
record last, so a crash is never read as a success.

Exit codes: 0 ok / skipped-disabled; 1 failure (missing registry entry, unreachable sha,
`gh` failure) - the heartbeat `exit` mirrors it and no comment is posted on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

JOB = "com.oversight.agency.kbsync"
CADENCE = "09:00 Mon"
ISSUE_NUMBER = 5496
DOCTRINE_REL = Path("agency/backend/agents/knowledge/doctrine")
# Runtime knowledge directories (relative to the runtime root) scanned for never-ported files.
INCLUDE_DIRS = (
    "knowledge/marketing_kb",
    "knowledge/hiring_kb",
    "knowledge/video_kb",
    "knowledge/venture_kb/recruiting",
)
# In-scope primers: the five agent primers C1 rewrites into the method lanes.
INCLUDE_FILES = (
    "knowledge/board_steward_primer.md",
    "knowledge/consistency_auditor_primer.md",
    "knowledge/cost_strategist_primer.md",
    "knowledge/launch_director_primer.md",
    "knowledge/sentinel_primer.md",
)
GH_REPO = "example-org/agency"
RUNTIME_PREFIX = "~/.claude/"

Poster = Callable[[int, str, Path], None]


class SyncError(Exception):
    """A failure that must exit non-zero with no comment posted."""


@dataclass
class Source:
    """One PORT_SOURCES block with a runtime origin."""

    lane: str
    name: str
    runtime_path: str
    runtime_sha: str
    rewritten: bool


@dataclass
class OverlayCitation:
    overlay: str
    runtime_path: str
    read_date: str  # YYYY-MM-DD


@dataclass
class Report:
    reports: list[str] = field(default_factory=list)  # "re-port: ..." lines
    rewrites: list[str] = field(default_factory=list)
    overlays: list[str] = field(default_factory=list)
    cannot_compare: list[str] = field(default_factory=list)
    never_ported: list[str] = field(default_factory=list)
    repo_sourced: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.reports or self.rewrites or self.overlays)

    def body(self) -> str:
        lines = ["Knowledge sync report (runtime knowledge vs doctrine PORT_SOURCES).", ""]
        sections = (
            ("re-port", self.reports),
            ("rewrite review needed", self.rewrites),
            ("overlay review needed", self.overlays),
            ("cannot compare", self.cannot_compare),
        )
        for title, items in sections:
            if items:
                lines.append(f"{title} ({len(items)}):")
                lines.extend(f"- {i}" for i in items)
                lines.append("")
        if self.never_ported:
            lines.append(f"never ported ({len(self.never_ported)}, informational):")
            lines.extend(f"- {i}" for i in self.never_ported)
            lines.append("")
        if self.repo_sourced:
            lines.append(
                f"repo-sourced, not tracked by this sync: {len(self.repo_sourced)} block(s): "
                + ", ".join(self.repo_sourced)
            )
            lines.append("")
        lines.append(
            "Port with scripts/doctrine_port.py in an interactive session and update PORT_SOURCES "
            "(the only sync state); rewritten sources and overlays are hand-applied after review."
        )
        return "\n".join(lines)

    def summary(self) -> str:
        return (
            f"re-port={len(self.reports)} rewrite-review={len(self.rewrites)} "
            f"overlay-review={len(self.overlays)} cannot-compare={len(self.cannot_compare)} "
            f"never-ported={len(self.never_ported)} repo-sourced={len(self.repo_sourced)}"
        )


# ---------------------------------------------------------------- heartbeat


def utc_now() -> str:
    """UTC ISO-8601 ending in a literal Z (heartbeat_audit._UTC_TS_RE)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_heartbeat(
    path: Path,
    started_at: str,
    finished_at: str | None,
    exit_code: int,
    summary: str,
) -> None:
    record = {
        "job": JOB,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit": exit_code,
        "cadence": CADENCE,
        "summary": summary,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- parsing


def resolve_runtime_path(raw: str, runtime_root: Path) -> Path:
    raw = raw.strip()
    if raw.startswith(RUNTIME_PREFIX):
        return runtime_root / raw[len(RUNTIME_PREFIX) :]
    return Path(raw).expanduser()


def parse_port_sources(text: str, lane: str) -> tuple[list[Source], list[str]]:
    """Return (runtime-origin sources, names of repo-sourced blocks)."""
    sources: list[Source] = []
    repo_blocks: list[str] = []
    blocks = re.split(r"^### ", text, flags=re.MULTILINE)[1:]
    for block in blocks:
        name, _, rest = block.partition("\n")
        fields: dict[str, str] = {}
        for line in rest.splitlines():
            m = re.match(r"^- ([a-z ]+): (.*)$", line)
            if m and m.group(1) not in fields:
                fields[m.group(1)] = m.group(2).strip()
        if "runtime path" in fields and "runtime sha" in fields:
            sources.append(
                Source(
                    lane=lane,
                    name=name.strip(),
                    runtime_path=fields["runtime path"],
                    runtime_sha=fields["runtime sha"],
                    rewritten=fields.get("rewritten", "").lower().startswith("yes"),
                )
            )
        elif "repo path" in fields:
            repo_blocks.append(f"{lane}/{name.strip()}")
    return sources, repo_blocks


_CITE_RE = re.compile(r"(~/\.claude/[^\s,;()]+?\.md)")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def parse_overlay_sources(text: str, overlay: str) -> list[OverlayCitation]:
    """Runtime files cited by an overlay SOURCES.md with the read date.

    The date is the one on the citing line ("read YYYY-MM-DD"), else the file's header
    "last read YYYY-MM-DD"; a citation with neither is skipped (nothing to compare against).
    """
    header = _DATE_RE.search(text.splitlines()[0]) if text.strip() else None
    default = header.group(1) if header else None
    cites: list[OverlayCitation] = []
    for line in text.splitlines()[1:]:
        m = _CITE_RE.search(line)
        if not m:
            continue
        dates = _DATE_RE.findall(line)
        date = dates[-1] if dates and "read" in line else default
        if date:
            cites.append(OverlayCitation(overlay, m.group(1), date))
    return cites


# ---------------------------------------------------------------- git


def git_changes(runtime_root: Path, since_sha: str, rel_path: str) -> list[str]:
    """`--name-status` lines for commits in sha..HEAD touching rel_path.

    Raises SyncError when the sha is unreachable.
    """
    proc = subprocess.run(
        ["git", "-C", str(runtime_root), "log", "--name-status", "--format=", f"{since_sha}..HEAD", "--", rel_path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SyncError(proc.stderr.strip() or "git log failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def git_changed_since_date(runtime_root: Path, date: str, rel_path: str) -> list[str]:
    """Commits touching rel_path after the end of `date` (local time)."""
    try:
        cutoff = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    except ValueError as exc:
        raise SyncError(f"bad overlay read date {date!r}") from exc
    proc = subprocess.run(
        ["git", "-C", str(runtime_root), "log", "--name-status", "--format=", f"--since={cutoff}", "--", rel_path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SyncError(proc.stderr.strip() or "git log failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def rel_to_root(path: Path, runtime_root: Path) -> str:
    try:
        return str(path.relative_to(runtime_root))
    except ValueError as exc:
        raise SyncError(f"{path} is outside the runtime repo {runtime_root}") from exc


# ---------------------------------------------------------------- core


def build_report(agency_root: Path, runtime_root: Path) -> Report:
    doctrine = agency_root / DOCTRINE_REL
    if not doctrine.is_dir():
        raise SyncError(f"doctrine corpus not found: {doctrine}")
    report = Report()
    known_runtime: set[str] = set()

    for ps in sorted(doctrine.glob("agnostic/*/PORT_SOURCES.md")):
        lane = ps.parent.name
        sources, repo_blocks = parse_port_sources(ps.read_text(encoding="utf-8"), lane)
        report.repo_sourced.extend(repo_blocks)
        for src in sources:
            abs_path = resolve_runtime_path(src.runtime_path, runtime_root)
            rel = rel_to_root(abs_path, runtime_root)
            known_runtime.add(rel)
            try:
                changes = git_changes(runtime_root, src.runtime_sha, rel)
            except SyncError as exc:
                report.cannot_compare.append(f"{lane}/{src.name} ({src.runtime_sha[:10]}): {exc}")
                continue
            if not changes:
                continue
            status = ", ".join(sorted({c.split("\t")[0] for c in changes}))
            line = f"{lane}/{src.name} <- {rel} (git status {status}, {len(changes)} change(s) since {src.runtime_sha[:10]})"
            (report.rewrites if src.rewritten else report.reports).append(line)

    for sp in sorted(doctrine.glob("industry/dental/*/SOURCES.md")):
        overlay = f"dental/{sp.parent.name}"
        for cite in parse_overlay_sources(sp.read_text(encoding="utf-8"), overlay):
            abs_path = resolve_runtime_path(cite.runtime_path, runtime_root)
            rel = rel_to_root(abs_path, runtime_root)
            try:
                changes = git_changed_since_date(runtime_root, cite.read_date, rel)
            except SyncError as exc:
                report.cannot_compare.append(f"{overlay} cites {rel}: {exc}")
                continue
            if changes:
                report.overlays.append(
                    f"{overlay} cites {rel} (read {cite.read_date}; {len(changes)} change(s) since)"
                )

    for inc_file in INCLUDE_FILES:
        f = runtime_root / inc_file
        if f.is_file() and inc_file not in known_runtime:
            report.never_ported.append(inc_file)

    for inc in INCLUDE_DIRS:
        base = runtime_root / inc
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.md")):
            rel = str(f.relative_to(runtime_root))
            if rel not in known_runtime:
                report.never_ported.append(rel)

    report.repo_sourced = sorted(set(report.repo_sourced))
    return report


def agency_root_from_registry(runtime_root: Path) -> Path:
    reg = runtime_root / "knowledge" / "repo_registry.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        root = data["repos"]["agency"]["root"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SyncError(f"repos.agency.root missing from {reg}: {exc}") from exc
    return Path(str(root)).expanduser()


def gh_poster(issue: int, body: str, cwd: Path) -> None:
    """Post `body` as one comment via `gh issue comment --body-file` (body file lives in a temp dir)."""
    with tempfile.TemporaryDirectory(prefix="kbsync-") as tmp:
        body_file = Path(tmp) / "body.md"
        body_file.write_text(body, encoding="utf-8")
        proc = subprocess.run(
            ["gh", "issue", "comment", str(issue), "--repo", GH_REPO, "--body-file", str(body_file)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0:
        raise SyncError(f"gh issue comment failed: {proc.stderr.strip()}")


def run(
    runtime_root: Path,
    poster: Poster = gh_poster,
    agency_root: Path | None = None,
    manual: bool = False,
) -> int:
    """Run one sync. Returns the process exit code; always leaves an END heartbeat."""
    # A manual run writes manual-<job>.json so it never refreshes the scheduled job's liveness.
    hb = runtime_root / "schedules" / "heartbeats" / (f"manual-{JOB}.json" if manual else f"{JOB}.json")
    started = utc_now()
    schedules = runtime_root / "schedules"
    if (schedules / "DISABLED").exists() or (schedules / "DISABLED.kbsync").exists():
        write_heartbeat(hb, started, utc_now(), 0, "skipped-disabled")
        return 0
    write_heartbeat(hb, started, None, 1, "STARTED kb sync")
    try:
        root = agency_root or agency_root_from_registry(runtime_root)
        report = build_report(root, runtime_root)
        print(report.body())
        if report.cannot_compare:
            raise SyncError(f"cannot compare {len(report.cannot_compare)} source(s); no comment posted")
        posted = False
        if report.changed:
            poster(ISSUE_NUMBER, report.body(), root)
            posted = True
        write_heartbeat(
            hb, started, utc_now(), 0, f"{'posted' if posted else 'no-change'}: {report.summary()}"
        )
        return 0
    except SyncError as exc:
        write_heartbeat(hb, started, utc_now(), 1, f"FAILED: {exc}"[:500])
        print(f"kb_sync_report: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # crash must never read as success
        write_heartbeat(hb, started, utc_now(), 1, f"FAILED: unexpected {type(exc).__name__}: {exc}"[:500])
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runtime-root", default=str(Path.home() / ".claude"))
    ap.add_argument("--manual", action="store_true", help="on-demand run: write manual-<job>.json heartbeat")
    args = ap.parse_args(argv)
    return run(Path(args.runtime_root).expanduser(), manual=args.manual)


if __name__ == "__main__":
    sys.exit(main())
