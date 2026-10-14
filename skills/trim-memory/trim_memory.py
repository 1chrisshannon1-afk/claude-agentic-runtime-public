#!/usr/bin/env python3
"""
trim_memory.py — five pure-function reapers for operator MEMORY.md hygiene.

Usage:
    python3 trim_memory.py [--dry-run | --apply] [--reaper <name>] [--memory-path <path>]

Reapers:
    stale-dated       entries with Set YYYY-MM-DD >180d AND file mtime >180d AND no cross-refs
    resolved-project  project_* files containing RESOLVED/DONE/SHIPPED/fixed 20 AND mtime >60d
    superseded-ref    bidirectional cross-references between memory files (flag only, no archive)
    dead-path         any absolute path under $HOME (any project, not one hardcoded repo)
                      referenced in memory text that doesn't exist on disk
    line-length       MEMORY.md index lines >250 chars (warn only, no archive)

Output:
    trim_report.json in <memory-path>/  (or /tmp/ if memory-path not writable)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_FILENAME = "MEMORY.md"
ARCHIVE_SUBDIR = "archive"
LINE_LENGTH_LIMIT = 250
STALE_DAYS = 180
RESOLVED_PROJECT_DAYS = 60
RESOLVED_PATTERNS = re.compile(
    r"^(RESOLVED|DONE|SHIPPED|fixed 20\d\d)",
    re.MULTILINE | re.IGNORECASE,
)
SET_DATE_PATTERN = re.compile(r"Set (\d{4}-\d{2}-\d{2})")
# Runtime skill: must work for any project under any operator's $HOME, never
# one hardcoded product repo — a repo that does not exist yet must work
# unmodified. HOME_DIR is a per-machine value derived from the environment
# (like every other HOME-derived constant in this runtime), not a literal
# baked into source.
HOME_DIR = Path.home()
HOME_PATH_PATTERN = re.compile(re.escape(str(HOME_DIR)) + r"/([^\s\)\"']+)")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


def make_archive_proposal(filename: str, reaper: str, reason: str) -> dict[str, Any]:
    return {"filename": filename, "reaper": reaper, "reason": reason, "action": "archive"}


def make_flag(filename: str, reaper: str, reason: str) -> dict[str, Any]:
    return {"filename": filename, "reaper": reaper, "reason": reason, "action": "flag"}


def make_line_warning(line_no: int, char_count: int, preview: str) -> dict[str, Any]:
    return {"line_no": line_no, "char_count": char_count, "preview": preview}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def days_since_mtime(path: Path) -> float:
    """Return the number of days since the file was last modified."""
    mtime = path.stat().st_mtime
    age_seconds = datetime.now(tz=timezone.utc).timestamp() - mtime
    return age_seconds / 86400.0


def parse_set_date(text: str) -> date | None:
    """Extract the most recent 'Set YYYY-MM-DD' date from text."""
    matches = SET_DATE_PATTERN.findall(text)
    if not matches:
        return None
    parsed = []
    for m in matches:
        try:
            parsed.append(date.fromisoformat(m))
        except ValueError:
            pass
    return max(parsed) if parsed else None


def build_cross_ref_index(memory_dir: Path) -> dict[str, set[str]]:
    """
    Build a map of {filename: set_of_referenced_filenames} by scanning every
    .md file in memory_dir for links that look like other .md filenames in the
    same directory.
    """
    md_files = {f.name for f in memory_dir.glob("*.md") if f.name != MEMORY_FILENAME}
    ref_index: dict[str, set[str]] = {name: set() for name in md_files}

    for md_file in memory_dir.glob("*.md"):
        text = md_file.read_text(errors="replace")
        for candidate in md_files:
            stem = candidate.replace(".md", "")
            if stem in text and candidate != md_file.name:
                ref_index.setdefault(md_file.name, set()).add(candidate)

    return ref_index


# ---------------------------------------------------------------------------
# Reaper 1: stale-dated
# ---------------------------------------------------------------------------


def reap_stale_dated(
    memory_dir: Path, cross_ref_index: dict[str, set[str]]
) -> list[dict[str, Any]]:
    """
    Flag entries where:
    - Body contains 'Set YYYY-MM-DD' >180 days ago
    - File mtime >180 days old
    - Not cross-referenced from any other memory file
    """
    proposals: list[dict[str, Any]] = []
    today = date.today()
    cutoff_days = STALE_DAYS

    for md_file in memory_dir.glob("*.md"):
        if md_file.name == MEMORY_FILENAME:
            continue
        if md_file.name.startswith("archive"):
            continue

        text = md_file.read_text(errors="replace")
        set_date = parse_set_date(text)
        if set_date is None:
            continue

        age_days = (today - set_date).days
        if age_days <= cutoff_days:
            continue

        file_age_days = days_since_mtime(md_file)
        if file_age_days <= cutoff_days:
            continue

        # Check not cross-referenced from any other file
        is_referenced = any(
            md_file.name in refs
            for fname, refs in cross_ref_index.items()
            if fname != md_file.name
        )
        if is_referenced:
            continue

        proposals.append(
            make_archive_proposal(
                md_file.name,
                "stale-dated",
                f"Set {set_date} ({age_days}d ago); file mtime {file_age_days:.0f}d old; no cross-refs",
            )
        )

    return proposals


# ---------------------------------------------------------------------------
# Reaper 2: resolved-project
# ---------------------------------------------------------------------------


def reap_resolved_project(memory_dir: Path) -> list[dict[str, Any]]:
    """
    Flag project_* files where body contains RESOLVED|DONE|SHIPPED|'fixed 20'
    AND file mtime >60 days.
    """
    proposals: list[dict[str, Any]] = []

    for md_file in memory_dir.glob("project_*.md"):
        text = md_file.read_text(errors="replace")
        match = RESOLVED_PATTERNS.search(text)
        if not match:
            continue

        file_age_days = days_since_mtime(md_file)
        if file_age_days <= RESOLVED_PROJECT_DAYS:
            continue

        proposals.append(
            make_archive_proposal(
                md_file.name,
                "resolved-project",
                f"Contains '{match.group(0).strip()}'; mtime {file_age_days:.0f}d old",
            )
        )

    return proposals


# ---------------------------------------------------------------------------
# Reaper 3: superseded-ref
# ---------------------------------------------------------------------------


def reap_superseded_ref(
    _memory_dir: Path, cross_ref_index: dict[str, set[str]]
) -> list[dict[str, Any]]:
    """
    Find pairs (A, B) where A references B AND B references A.
    Flag both for human review — do NOT auto-archive.
    """
    flags: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[str]] = set()

    for fname, refs in cross_ref_index.items():
        for other in refs:
            if other in cross_ref_index and fname in cross_ref_index[other]:
                pair = frozenset({fname, other})
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    flags.append(
                        make_flag(
                            fname,
                            "superseded-ref",
                            f"Bidirectional reference with {other} — human review needed",
                        )
                    )
                    flags.append(
                        make_flag(
                            other,
                            "superseded-ref",
                            f"Bidirectional reference with {fname} — human review needed",
                        )
                    )

    return flags


# ---------------------------------------------------------------------------
# Reaper 4: dead-path
# ---------------------------------------------------------------------------


def reap_dead_path(memory_dir: Path) -> list[dict[str, Any]]:
    """
    Scan every memory file for an absolute path under the operator's $HOME
    (any project, not one hardcoded repo — this is a runtime skill and must
    work for a repo that does not exist yet). Flag files that reference
    paths that don't exist.
    """
    flags: list[dict[str, Any]] = []

    for md_file in memory_dir.glob("*.md"):
        if md_file.name == MEMORY_FILENAME:
            continue

        text = md_file.read_text(errors="replace")
        matches = HOME_PATH_PATTERN.findall(text)
        if not matches:
            continue

        dead_paths: list[str] = []
        for relative_path in matches:
            full_path = HOME_DIR / relative_path
            if not full_path.exists():
                dead_paths.append(str(full_path))

        if dead_paths:
            flags.append(
                make_flag(
                    md_file.name,
                    "dead-path",
                    f"References {len(dead_paths)} non-existent path(s): {', '.join(dead_paths[:3])}{'...' if len(dead_paths) > 3 else ''}",
                )
            )

    return flags


# ---------------------------------------------------------------------------
# Reaper 5: line-length
# ---------------------------------------------------------------------------


def reap_line_length(memory_dir: Path) -> list[dict[str, Any]]:
    """
    Warn on any MEMORY.md index line exceeding LINE_LENGTH_LIMIT chars.
    Does NOT modify files.
    """
    warnings: list[dict[str, Any]] = []
    memory_file = memory_dir / MEMORY_FILENAME

    if not memory_file.exists():
        return warnings

    for line_no, line in enumerate(memory_file.read_text(errors="replace").splitlines(), start=1):
        stripped = line.rstrip("\n")
        if len(stripped) > LINE_LENGTH_LIMIT:
            warnings.append(
                make_line_warning(
                    line_no,
                    len(stripped),
                    stripped[:80] + "...",
                )
            )

    return warnings


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_archives(
    memory_dir: Path,
    proposed_archives: list[dict[str, Any]],
    archive_date: str,
) -> list[str]:
    """
    Move proposed archive files to memory/archive/<date>/.
    Update MEMORY.md index lines with [archived YYYY-MM-DD] suffix.
    Returns list of moved filenames.
    """
    archive_dir = memory_dir / ARCHIVE_SUBDIR / archive_date
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    filenames_to_archive = {item["filename"] for item in proposed_archives}

    for filename in filenames_to_archive:
        src = memory_dir / filename
        if not src.exists():
            continue
        dst = archive_dir / filename
        shutil.move(str(src), str(dst))
        moved.append(filename)

    if moved:
        _update_memory_index(memory_dir, set(moved), archive_date)

    return moved


def _update_memory_index(
    memory_dir: Path, archived_filenames: set[str], archive_date: str
) -> None:
    """
    Append [archived YYYY-MM-DD] to index lines in MEMORY.md that reference
    any of the archived filenames. Does NOT delete the index lines.
    """
    memory_file = memory_dir / MEMORY_FILENAME
    if not memory_file.exists():
        return

    lines = memory_file.read_text(errors="replace").splitlines(keepends=True)
    updated_lines: list[str] = []

    for line in lines:
        for fname in archived_filenames:
            stem = fname.replace(".md", "")
            if stem in line and "[archived" not in line:
                line = line.rstrip("\n") + f" [archived {archive_date}]\n"
                break
        updated_lines.append(line)

    memory_file.write_text("".join(updated_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_report(
    memory_dir: Path,
    proposed_archives: list[dict[str, Any]],
    flags: list[dict[str, Any]],
    line_length_warnings: list[dict[str, Any]],
    dry_run: bool,
    applied_files: list[str] | None = None,
) -> Path:
    """Write trim_report.json and return its path."""
    report: dict[str, Any] = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "dry_run": dry_run,
        "applied": applied_files is not None,
        "memory_dir": str(memory_dir),
        "proposed_archives": proposed_archives,
        "flags": flags,
        "line_length_warnings": line_length_warnings,
        "summary": {
            "proposed_archive_count": len(proposed_archives),
            "flag_count": len(flags),
            "line_length_warning_count": len(line_length_warnings),
        },
    }
    if applied_files is not None:
        report["applied_files"] = applied_files

    report_path = memory_dir / "trim_report.json"
    try:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        report_path = Path("/tmp/trim_report.json")
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report_path


def print_report(
    proposed_archives: list[dict[str, Any]],
    flags: list[dict[str, Any]],
    line_length_warnings: list[dict[str, Any]],
    dry_run: bool,
) -> None:
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\n=== trim_memory [{mode}] ===\n")

    if proposed_archives:
        print(f"PROPOSED ARCHIVES ({len(proposed_archives)}):")
        for item in proposed_archives:
            print(f"  [{item['reaper']}] {item['filename']}")
            print(f"    reason: {item['reason']}")
    else:
        print("PROPOSED ARCHIVES: none")

    print()

    if flags:
        print(f"FLAGS — HUMAN REVIEW REQUIRED ({len(flags)}):")
        for item in flags:
            print(f"  [{item['reaper']}] {item['filename']}")
            print(f"    reason: {item['reason']}")
    else:
        print("FLAGS: none")

    print()

    if line_length_warnings:
        print(f"LINE-LENGTH WARNINGS ({len(line_length_warnings)}) — lines >{LINE_LENGTH_LIMIT} chars:")
        for w in line_length_warnings:
            print(f"  line {w['line_no']:4d} ({w['char_count']} chars): {w['preview']}")
    else:
        print("LINE-LENGTH WARNINGS: none")

    print()
    print(
        f"Summary: {len(proposed_archives)} proposed archives, "
        f"{len(flags)} flags, "
        f"{len(line_length_warnings)} line-length warnings"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def detect_memory_dir() -> Path | None:
    """Auto-detect the most recently modified MEMORY.md under ~/.claude/projects/."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None
    candidates = list(base.rglob("memory/MEMORY.md"))
    if not candidates:
        return None
    # Pick most recently modified
    return max(candidates, key=lambda p: p.stat().st_mtime).parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trim operator MEMORY.md — five pure-function reapers."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", default=True, help="Print proposals only (default)")
    mode_group.add_argument("--apply", action="store_true", help="Archive proposed files and update MEMORY.md")
    parser.add_argument(
        "--reaper",
        choices=["stale-dated", "resolved-project", "superseded-ref", "dead-path", "line-length"],
        help="Run only this reaper",
    )
    parser.add_argument("--memory-path", type=Path, help="Path to memory directory")
    args = parser.parse_args()

    dry_run = not args.apply

    # Resolve memory dir
    memory_dir = args.memory_path
    if memory_dir is None:
        memory_dir = detect_memory_dir()
    if memory_dir is None:
        print("ERROR: Could not locate memory directory. Pass --memory-path.", file=sys.stderr)
        return 1

    memory_dir = memory_dir.expanduser().resolve()
    if not memory_dir.exists():
        print(f"ERROR: memory directory not found: {memory_dir}", file=sys.stderr)
        return 1

    if not (memory_dir / MEMORY_FILENAME).exists():
        print(f"ERROR: {MEMORY_FILENAME} not found in {memory_dir}", file=sys.stderr)
        return 1

    print(f"Memory dir: {memory_dir}")
    memory_file = memory_dir / MEMORY_FILENAME
    size_bytes = memory_file.stat().st_size
    print(f"MEMORY.md: {size_bytes} bytes ({size_bytes/1024:.1f} KB)")
    if size_bytes > 24400:
        print(f"  WARNING: exceeds 24.4 KB load limit ({size_bytes - 24400} bytes over)")

    # Build cross-ref index (used by multiple reapers)
    cross_ref_index = build_cross_ref_index(memory_dir)

    # Run reapers
    proposed_archives: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    line_length_warnings: list[dict[str, Any]] = []

    run_all = args.reaper is None

    if run_all or args.reaper == "stale-dated":
        result = reap_stale_dated(memory_dir, cross_ref_index)
        proposed_archives.extend(result)
        print(f"  stale-dated: {len(result)} proposals")

    if run_all or args.reaper == "resolved-project":
        result = reap_resolved_project(memory_dir)
        proposed_archives.extend(result)
        print(f"  resolved-project: {len(result)} proposals")

    if run_all or args.reaper == "superseded-ref":
        result = reap_superseded_ref(memory_dir, cross_ref_index)
        flags.extend(result)
        print(f"  superseded-ref: {len(result)} flags")

    if run_all or args.reaper == "dead-path":
        result = reap_dead_path(memory_dir)
        flags.extend(result)
        print(f"  dead-path: {len(result)} flags")

    if run_all or args.reaper == "line-length":
        result = reap_line_length(memory_dir)
        line_length_warnings.extend(result)
        print(f"  line-length: {len(result)} warnings")

    # Print results
    print_report(proposed_archives, flags, line_length_warnings, dry_run)

    # Apply if requested
    applied_files: list[str] | None = None
    if not dry_run and proposed_archives:
        archive_date = date.today().isoformat()
        print(f"\nApplying {len(proposed_archives)} archive proposals...")
        applied_files = apply_archives(memory_dir, proposed_archives, archive_date)
        print(f"Moved {len(applied_files)} files to {memory_dir / ARCHIVE_SUBDIR / archive_date}")
        print("Updated MEMORY.md index entries with [archived] suffix.")

        # Report new size
        new_size = memory_file.stat().st_size
        print(f"MEMORY.md after: {new_size} bytes ({new_size/1024:.1f} KB)")
    elif not dry_run and not proposed_archives:
        print("Nothing to apply.")

    # Write report
    report_path = write_report(
        memory_dir,
        proposed_archives,
        flags,
        line_length_warnings,
        dry_run,
        applied_files,
    )
    print(f"\nReport written: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
