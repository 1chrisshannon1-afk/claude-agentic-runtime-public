#!/usr/bin/env python3
"""doc_citation_check — catch rotted ``<file>:<line>`` citations in the
runtime's own prose.

THE DEFECT THIS GUARDS AGAINST: a doc that cites source by LINE NUMBER
("``record_review.py:840-881``") goes silently wrong the moment anything is
inserted above that line. Nothing fails, nothing warns, and the reader who
follows the citation lands in unrelated code with no signal that the
citation -- rather than their own understanding -- is what is broken.

This is not hypothetical. Three instances were found on 2026-09-21 alone,
every one by a human-equivalent read rather than by any mechanism:

  1. A ten-line insertion into ``agents/code-reviewer.md`` invalidated EIGHT
     citations in two other files, caught only during the commit that caused
     them.
  2. ``docs/subsystems/review-ladder.md`` carried NINE citations into
     ``record_review.py`` and every one was wrong: ``_append_entry`` cited at
     840-881 actually lived at 1688-1729, ``decide()`` cited at 699-839
     actually at 1526-1687, ``ArgvError`` cited at 122 actually at 178.
  3. Two loose citations in ``docs/agents/trust-architect.md``, noticed and
     left unfixed for want of a mechanism.

WHAT THIS CHECKS, and deliberately what it does NOT. A line number cannot be
validated for *correctness* -- only the author knows which line they meant.
What IS mechanically checkable is whether the citation is even resolvable:

  * ``missing-file``    -- the cited path cannot be resolved: absent, or an
                           AMBIGUOUS bare name that several files share (the
                           detail says which).
  * ``out-of-range``    -- the cited line is past the end of the file.
  * ``empty-target``    -- the cited line (or every line of a cited range)
                           is blank. A citation pointing at whitespace is
                           drift with near-certainty; a real anchor is code
                           or prose.

Anything subtler than that -- a citation that resolves to a REAL but WRONG
line -- is out of reach here and stated plainly rather than implied away. It
is why the real remedy is the one this module's own header recommends:

  **PREFER A SYMBOL OVER A LINE NUMBER.** ``_append_entry`` in
  ``record_review.py`` survives every insertion above it, is greppable, and
  cannot rot. ``record_review.py:1688`` is correct for exactly as long as
  nobody edits the file. Where a doc can name a function, class or constant,
  it should; this checker exists for the citations that remain.

REPORT-ONLY by design: it prints findings and exits 0 unless ``--strict`` is
passed. It is a drift sensor for the daily sweep, not a commit gate -- a
stale citation is a documentation defect, never a reason to block a commit
that may be entirely unrelated to it.

Usage:
    python3 ~/.claude/hooks/doc_citation_check.py            # report, exit 0
    python3 ~/.claude/hooks/doc_citation_check.py --strict   # exit 1 on any finding
    python3 ~/.claude/hooks/doc_citation_check.py --json
    python3 ~/.claude/hooks/doc_citation_check.py --root <dir>
    python3 ~/.claude/hooks/doc_citation_check.py --paths a.md b.md

Tracked on #5843.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# A citation is only recognised inside backticks. Bare `foo.py:12` in running
# prose is too easily a false positive (a log line being quoted, a shell
# snippet, a URL fragment), and this module's whole value is that its findings
# are worth acting on rather than triaging.
_CITATION = re.compile(
    r"`(?P<path>[A-Za-z0-9_][A-Za-z0-9_/.\-]*\.(?:py|sh|mjs|js|json|md|txt|yaml|yml|toml))"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?`"
)

# Where docs live. Deliberately NOT the whole runtime: a citation inside a
# .py module's own comments points at code the author can see, and those are
# checked by the reader who is already in that file.
_DEFAULT_DOC_DIRS = ("docs", "knowledge", "agents", "commands", "schedules", "templates")
_DEFAULT_DOC_FILES = ("CLAUDE.md",)
_DOC_SUFFIXES = (".md", ".txt")

# Directories never scanned: generated, vendored, or archival-by-definition.
_SKIP_DIR_PARTS = (
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
    os.sep + "worktrees" + os.sep,
    os.sep + "trade_kb" + os.sep,  # licensed corpus, not our prose
    os.sep + ".mirror" + os.sep,  # the GitHub mirror CLONE: a second copy of
    # every runtime file. Without this exclusion EVERY bare-name citation is
    # "ambiguous" (2 hits: the real file and its mirrored twin) and resolves
    # to None -- which is how the first run reported 139 false missing-file
    # findings. The mirror is generated, never authored; nothing in it is a
    # citation source or target.
)


def _is_doc(path: str) -> bool:
    return path.endswith(_DOC_SUFFIXES)


def _skip(path: str) -> bool:
    return any(part in path for part in _SKIP_DIR_PARTS)


def iter_docs(root: str) -> list[str]:
    """Every doc file under the runtime root that could carry a citation."""
    out: list[str] = []
    for name in _DEFAULT_DOC_FILES:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            out.append(p)
    for d in _DEFAULT_DOC_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in (".git", "node_modules", "worktrees")]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                if _is_doc(p) and not _skip(p):
                    out.append(p)
    return sorted(set(out))


# Docs routinely cite a BARE filename ("`daily_sweep.txt:13`") and expect the
# reader to know where it lives. Resolving only root-relative and
# doc-relative paths reported 139 such citations as missing-file on the first
# run -- noise that would have made the whole sensor ignorable. A bare name is
# therefore also searched for, uniquely, under the runtime root.
_BARE_NAME_INDEX: dict[str, list[str]] | None = None


def _bare_name_index(root: str) -> dict[str, list[str]]:
    """basename -> every path under root carrying it. Built once, lazily."""
    global _BARE_NAME_INDEX
    if _BARE_NAME_INDEX is not None:
        return _BARE_NAME_INDEX
    idx: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            x for x in dirnames if x not in (".git", "node_modules", "worktrees", ".venv", ".mirror")
        ]
        if _skip(dirpath + os.sep):
            continue
        for fn in filenames:
            idx.setdefault(fn, []).append(os.path.join(dirpath, fn))
    _BARE_NAME_INDEX = idx
    return idx


def _resolve(cited: str, doc_path: str, root: str) -> str | None:
    """Resolve a cited path the way a READER would: relative to the runtime
    root first (that is how every runtime doc spells a path), then relative to
    the citing doc's own directory, then -- for a BARE filename only -- by
    unique basename anywhere under the root. Returns None when none resolve.

    An AMBIGUOUS bare name (two files share it) resolves to None and is
    reported as unresolvable rather than guessed at: picking one would make
    the line/range verdict meaningless."""
    candidates = [
        os.path.join(root, cited),
        os.path.join(os.path.dirname(doc_path), cited),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    if os.sep not in cited and "/" not in cited:
        hits = _bare_name_index(root).get(cited, [])
        if len(hits) == 1:
            return hits[0]
    return None


def _line_count_and_blankness(path: str, start: int, end: int) -> tuple[int, bool]:
    """(total lines, whether every line in [start,end] is blank).

    Reads defensively: an unreadable or binary target is treated as
    unverifiable rather than as a finding -- this module must never invent a
    defect out of its own inability to read something."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return (-1, False)
    total = len(lines)
    if start > total:
        return (total, False)
    window = lines[start - 1 : min(end, total)]
    return (total, bool(window) and all(not ln.strip() for ln in window))


# A runtime doc may legitimately cite a file in ANOTHER repo (a product repo,
# a sibling project). This checker can only see the runtime, so such a
# citation is UNVERIFIABLE here, not broken -- reporting it as missing-file
# would be a false accusation and would bury the real findings. Recognised by
# a leading path segment that belongs to a known non-runtime tree.
_FOREIGN_PREFIXES = (
    "modules/", "shared/", "repo_tooling/", "_Config_Project/", "marketing/",
    "agency/", "src/", "api/", "app/", "frontend/", "backend/",
)

# Point-in-time audit reports. They cite the tree AS IT WAS on their own date
# and are archival by definition -- a citation going stale in one is the
# record working, not a defect. Never scanned.
_ARCHIVAL_DOC_PARTS = (os.sep + "logs" + os.sep,)


def _is_foreign(cited: str) -> bool:
    return cited.startswith(_FOREIGN_PREFIXES)


def check(root: str, paths: list[str] | None = None) -> list[dict]:
    """Every resolvable-citation finding under root. Never raises."""
    docs = paths if paths else iter_docs(root)
    findings: list[dict] = []
    for doc in docs:
        if not paths and any(part in doc for part in _ARCHIVAL_DOC_PARTS):
            continue
        try:
            with open(doc, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        # A doc that documents ANOTHER repo introduces a file once by its full
        # foreign path and thereafter cites it by bare name. `_is_foreign`
        # only sees the citation string, so the shorthand was reported as
        # missing-file: 43 of 46 findings in one doc on the first real run,
        # 85% of the sensor's total output. Collect every basename THIS doc
        # has already declared foreign and treat its shorthand the same way.
        # Scoped per-document deliberately: it can only ever suppress a name
        # the same file already showed to live in another repo, so it cannot
        # hide a genuine runtime citation.
        foreign_basenames = {
            os.path.basename(m.group("path"))
            for m in _CITATION.finditer(text)
            if _is_foreign(m.group("path"))
        } | {
            os.path.basename(q)
            for q in re.findall(r"`([A-Za-z0-9_][A-Za-z0-9_/.\-]*\.[A-Za-z0-9]+)`", text)
            if _is_foreign(q)
        }

        for lineno, line in enumerate(text.splitlines(), 1):
            for m in _CITATION.finditer(line):
                cited = m.group("path")
                start = int(m.group("start"))
                end = int(m.group("end") or start)
                target = _resolve(cited, doc, root)
                rel_doc = os.path.relpath(doc, root)
                if target is None and (
                    _is_foreign(cited) or os.path.basename(cited) in foreign_basenames
                ):
                    continue  # another repo's file: unverifiable here, not broken
                if target is None:
                    # An AMBIGUOUS bare name resolves to None too, and the
                    # file in that case plainly DOES exist -- saying it does
                    # not would be a false statement in the sensor's own
                    # output (live example: `git-ops.md`, which exists at
                    # both agents/ and docs/agents/). Report what is true:
                    # the citation cannot be resolved, and why.
                    n_hits = 0
                    if os.sep not in cited and "/" not in cited:
                        n_hits = len(_bare_name_index(root).get(cited, []))
                    detail = (
                        f"cited path is unresolvable — {n_hits} files share the name {cited}"
                        if n_hits > 1
                        else f"cited file does not exist: {cited}"
                    )
                    findings.append(
                        {
                            "rule": "missing-file",
                            "doc": rel_doc,
                            "doc_line": lineno,
                            "citation": m.group(0).strip("`"),
                            "detail": detail,
                        }
                    )
                    continue
                total, all_blank = _line_count_and_blankness(target, start, end)
                if total < 0:
                    continue  # unreadable: unverifiable, not a finding
                if start < 1:
                    # No file has a line 0. Silently a non-finding before this
                    # guard: `lines[-1:0]` is empty so the blankness rule
                    # missed it, and `0 > total` is False so the range rule
                    # missed it too.
                    findings.append(
                        {
                            "rule": "out-of-range",
                            "doc": rel_doc,
                            "doc_line": lineno,
                            "citation": m.group(0).strip("`"),
                            "detail": f"citation starts at line {start}; no file has a line below 1",
                        }
                    )
                    continue
                if start > total:
                    findings.append(
                        {
                            "rule": "out-of-range",
                            "doc": rel_doc,
                            "doc_line": lineno,
                            "citation": m.group(0).strip("`"),
                            "detail": f"{cited} has {total} lines; citation starts at {start}",
                        }
                    )
                    continue
                if all_blank:
                    findings.append(
                        {
                            "rule": "empty-target",
                            "doc": rel_doc,
                            "doc_line": lineno,
                            "citation": m.group(0).strip("`"),
                            "detail": f"every cited line in {cited} is blank — almost certainly drift",
                        }
                    )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--paths", nargs="*", default=None, help="check only these doc files")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any finding is reported")
    args = ap.parse_args(argv)

    try:
        findings = check(args.root, args.paths)
    except Exception as exc:  # never let a sensor take down its caller
        print(f"doc_citation_check: skipped ({exc.__class__.__name__}: {exc})", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['rule']}\t{f['doc']}:{f['doc_line']}\t{f['citation']}\t{f['detail']}")
        n = len(findings)
        print(f"doc_citation_check: {n} finding(s)")
        if n:
            print(
                "Prefer a SYMBOL over a line number — `_append_entry` in `record_review.py` "
                "cannot rot; `record_review.py:1688` is correct only until someone edits above it.",
                file=sys.stderr,
            )
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
