#!/usr/bin/env python3
"""check_guard_wiring - fail-closed CLI wrapper around the guard-wiring check.

``hooks/check_safety_core_parity.py`` already implements the self-consistency
check (every hook wired in ``settings.json`` points at a file that exists, the
live-testing allowlist parses and carries its required keys, and every on-disk
``hooks/*.py`` module that can emit a PreToolUse deny is reachable from
something ``settings.json`` wires). Its own ``main()`` is a Stop-event adapter
that ALWAYS exits 0 and reads the machine's real ``~/.claude``, so it cannot be
used as a CI step. This wrapper calls the module's pure ``check()`` directly:

  * against the checkout given by ``--repo`` (default: the repo this script
    lives in), never against whatever ``$HOME`` points at;
  * HOME-independent: the checker expands ``~/.claude/...`` references in
    ``settings.json`` using ``$HOME``, so the checkout's files are presented to
    it under that expansion, but every byte is read from ``--repo``;
  * prints how many guard modules were examined, so a check that looked at
    nothing is visible instead of silently green. Modules the checker declares
    standalone (``STANDALONE_GUARD_MODULES``: guards invoked some other way, so
    exempt from the wiring walk) are listed but NOT counted as examined;
  * exits 1 on ANY reported problem, and also when fewer than
    ``--min-modules`` (default 1, never negative) guard modules were examined,
    because a check that examined zero modules proves nothing.

The checker itself is deliberately loaded from the checkout THIS SCRIPT lives
in, never from ``--repo``: the verdict on a checkout must come from a checker
that checkout cannot have weakened (a doctored or stubbed
``hooks/check_safety_core_parity.py`` in the repo under examination is just
more data, not the judge). When ``--repo`` is omitted the two are the same
checkout. hooks/tests/test_check_guard_wiring.py pins this.

Exit codes: 0 clean, 1 problems (or too few modules examined), 2 usage error
(``--repo`` is not a directory).

Usage:
    python3 scripts/check_guard_wiring.py [--repo PATH] [--min-modules N]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOOKS_DIR = os.path.join(_REPO_ROOT, "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import check_safety_core_parity as cscp  # noqa: E402  (after the sys.path shim)

PROG = "check_guard_wiring"


def _virtual_claude_dir() -> str:
    """Where the checker believes ``~/.claude`` is (it expands ``~`` and
    ``$HOME`` through ``os.path.expanduser`` at call time)."""
    return os.path.join(os.path.expanduser("~"), ".claude")


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def collect(repo: str) -> Tuple[Set[str], Dict[str, str]]:
    """(existing_files, module_sources) for ``repo``, keyed by the path the
    checker will compute for each reference (``<expanded ~>/.claude/...``).

    Mirrors ``check_safety_core_parity._existing_script_files`` and
    ``_hook_module_sources`` (``scripts/*.sh``; ``hooks/*.py`` and
    ``hooks/*.sh``) but reads ``repo`` instead of the machine's real
    ``~/.claude``.
    """
    virtual = _virtual_claude_dir()
    files: Set[str] = set()
    sources: Dict[str, str] = {}

    scripts_dir = os.path.join(repo, "scripts")
    try:
        for name in os.listdir(scripts_dir):
            if name.endswith(".sh"):
                files.add(os.path.join(virtual, "scripts", name))
    except OSError:
        pass

    hooks_dir = os.path.join(repo, "hooks")
    try:
        names = os.listdir(hooks_dir)
    except OSError:
        names = []
    for name in names:
        if not name.endswith((".py", ".sh")):
            continue
        key = os.path.join(virtual, "hooks", name)
        files.add(key)
        text = _read_text(os.path.join(hooks_dir, name))
        if text is not None:
            sources[key] = text
    return files, sources


def guard_candidates(sources: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """(examined, standalone): basenames, sorted, of every hooks module the
    checker treats as a PreToolUse guard (its source calls the deny emitter),
    split into those whose wiring it verifies and those it declares standalone
    (exempt from the wiring walk, so they prove nothing about wiring)."""
    examined: List[str] = []
    standalone: List[str] = []
    for path, text in sources.items():
        base = os.path.basename(path)
        if not (path.endswith(".py") and cscp.looks_like_pretooluse_guard(base, text)):
            continue
        if base in cscp.STANDALONE_GUARD_MODULES:
            standalone.append(base)
        else:
            examined.append(base)
    return sorted(examined), sorted(standalone)


def run(repo: str, min_modules: int) -> Tuple[int, List[str]]:
    """(exit_code, output_lines) for ``repo``. Pure apart from reading it."""
    files, sources = collect(repo)
    settings = cscp._gather(
        os.path.join(repo, "settings.json"),
        os.path.join(repo, "live-testing", "allowlist.json"),
    )
    problems = cscp.check(settings, files, sources)
    examined, standalone = guard_candidates(sources)

    lines = [
        "%s: repo=%s" % (PROG, repo),
        "%s: guard modules examined: %d (declared standalone, not counted: %d)"
        % (PROG, len(examined), len(standalone)),
        "%s: problems: %d" % (PROG, len(problems)),
    ]
    for problem in problems:
        lines.append("  - %s" % problem)
    if any("allowlist.json is absent" in p for p in problems):
        lines.append(
            "  hint: seed it with `cp live-testing/allowlist.example.json "
            "live-testing/allowlist.json` (scripts/ci_layout.sh does this)."
        )

    code = 0
    if problems:
        code = 1
    if len(examined) < min_modules:
        lines.append(
            "%s: examined %d guard module(s), need at least %d -- refusing a vacuous pass"
            % (PROG, len(examined), min_modules)
        )
        code = 1
    return code, lines


def _non_negative_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not an integer" % raw)
    if value < 0:
        raise argparse.ArgumentTypeError("must be >= 0, got %d" % value)
    return value


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_guard_wiring.py",
        description="Fail-closed guard-wiring check for a checkout of the hook runtime.",
    )
    parser.add_argument(
        "--repo",
        default=_REPO_ROOT,
        help="checkout to examine (default: the repo this script lives in)",
    )
    parser.add_argument(
        "--min-modules",
        type=_non_negative_int,
        default=1,
        help="fail when fewer guard modules than this were examined (default: 1; "
        "modules declared standalone do not count)",
    )
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print("%s: --repo %s is not a directory" % (PROG, repo), file=sys.stderr)
        return 2

    code, lines = run(repo, args.min_modules)
    print("\n".join(lines))
    return code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
