#!/usr/bin/env python3
"""check_workflow_agent_purity — RULE G2 mechanical checker for THE ISSUE WHEEL.

A prose-only rule on a Workflow script's largest agent population is the known
weak shape in this runtime (that is exactly why check_safety_core_parity.py
exists: a guard shipped fully unwired for a session and nothing caught it).
RULE G1 (plan: issue_wheel_consolidation.md section 3) states what a Workflow
script may contain: only bounded, schema-shaped, READ-AND-REPORT `agent()`
fan-out with an explicit `model: 'sonnet'` in its own options -- never a
reviewer, never a writer, never anything that shells out. This module proves
that mechanically, for exactly the files the plan names.

SCOPE, narrow and deliberate: this parses ONLY files matching
`~/.claude/workflows/issue-wheel-*.js` -- never the whole `workflows/`
directory. `~/.claude/workflows/deliver.js` is a pre-existing, unrelated,
legitimate saved workflow that dispatches `plan-reviewer`/`implement`/
`code-reviewer` via `agentType:` exactly as a whole-directory predicate would
flag -- it is explicitly out of scope here and untouched by this checker, by
construction of the filename-pattern scoping below (see the plan's own
correction, section 3, closing plan-review round-2 blocker 3).

Three checks, all against parsed structure where the plan requires it (never a
raw substring match over agentType, which would false-positive on a comment or
a prompt string containing one of the flagged words):
  1. File-wide substring FAIL on any of eight literal strings a Workflow script
     can never legitimately reference (RULE G1(b): no shell/fs access).
  2. Per-`agent(` -call-site FAIL if the parsed `agentType:` value is one of the
     five reviewer/write-capable agent types.
  3. Per-`agent(`-call-site FAIL if there is no literal `model:` key at all, OR
     its parsed value is not in the sonnet-only allowlist (RULE G1's own
     stated requirement; #5161a -- presence alone is not enough, `model:
     'opus'` must fail exactly like a missing key).

On a clean pass: exit 0 and print a human-readable inventory of every
`agent(` call found and its `model` value, so a clean pass is *evidence*, not
silence (RULE G2's own explicit requirement).

Structure mirrors this directory's other checkers: pure functions (parsing +
deciding, no IO beyond the string/paths they are given) plus a thin CLI-style
`main()`. `check_file(path, source)` and `check_source(source)` are the
importable core, reused both by this module's own CLI and by
`pre_commit_ratchet.py`'s wiring (which reads STAGED git blob content, never
the on-disk file, so the ratchet judges what is about to be committed).
"""

from __future__ import annotations

import glob
import os
import re
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - shim runs before tests import
    sys.path.insert(0, _HOOKS_DIR)

# RULE G1(b): a Workflow script has no shell/fs access. Any of these appearing
# ANYWHERE in the file is a violation -- a whole-file substring check is
# correct here (unlike the agentType check below), since none of these strings
# can ever legitimately appear in a compliant workflow file at all, not even
# inside a comment describing what NOT to do (if a future editor needs to
# document the constraint, they should name these without the exact literal,
# e.g. "no shelling out to git" rather than the literal string "git commit").
_FORBIDDEN_SUBSTRINGS = (
    "record_review",
    "gh_issue.sh",
    "gh issue close",
    "file_claims",
    "git commit",
    "execSync",
    "spawnSync",
    "require('child_process')",
)

# RULE G1(a): never a reviewer, never a writer. Checked against the PARSED
# call-site value of agentType, never a raw substring over the whole file.
_FORBIDDEN_AGENT_TYPES = frozenset(
    {"code-reviewer", "trust-architect", "plan-reviewer", "implement", "test-writer"}
)

# RULE G1's own stated sonnet-only requirement (#5161a). Checked against the
# PARSED call-site value of `model:`, never mere presence -- `model:'opus'`
# must fail exactly like a missing `model:` key does.
_ALLOWED_MODELS = frozenset({"sonnet"})

_WORKFLOWS_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "workflows")
_FILENAME_GLOB_PATTERN = "issue-wheel-*.js"

_AGENTTYPE_RE = re.compile(r"agentType\s*:\s*(['\"])([^'\"]*)\1")
_MODEL_RE = re.compile(r"model\s*:\s*(['\"])([^'\"]*)\1")


class AgentCallSite:
    """One parsed `agent(...)` call site's relevant option values."""

    def __init__(self, index: int, agent_type: str | None, model: str | None, span_text: str):
        self.index = index
        self.agent_type = agent_type
        self.model = model
        self.span_text = span_text


def _strip_comments(source: str) -> str:
    """Blank out `//` line comments and `/* */` block comments, respecting
    string/template literals (so a `//` or `/*` inside a quoted string is
    never mistaken for a comment start). Replaces stripped comment bodies with
    spaces (never deletes characters) so every other character's index in the
    returned string still lines up with the original -- callers that slice
    `source[start:end]` for a call site's real (un-stripped) text still work
    correctly against the original source, only the SCAN for `agent(` sites
    ignores commented-out matches.
    """
    out = list(source)
    in_string: str | None = None
    escaped = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            else:
                out[i] = " " if ch != "\n" else ch
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and i + 1 < n and source[i + 1] == "/":
                out[i] = " "
                out[i + 1] = " "
                in_block_comment = False
                i += 2
                continue
            out[i] = " " if ch != "\n" else ch
            i += 1
            continue
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            in_line_comment = True
            out[i] = " "
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            in_block_comment = True
            out[i] = " "
            i += 1
            continue
        i += 1
    return "".join(out)


def find_agent_call_sites(source: str) -> list[AgentCallSite]:
    """Find every `agent(` call site and extract its options object literal.

    Not a full JS parser -- workflow scripts are `agent(prompt, {label, phase,
    schema, model, agentType})`-shaped calls, so a regex that finds `agent(`
    (scanning a comment-stripped copy of the source, so a `agent(...)` mention
    inside a `//` or `/* */` comment is never mistaken for a real call site)
    then scans the ORIGINAL source forward for BALANCED parens (respecting
    string literals, so a `)` inside a quoted prompt string never terminates
    the scan early) is sufficient. Deliberately does NOT match `agent_budget`,
    `.agent(`-as-a-property-access, or similar -- only a bare `agent(` call.
    """
    sites: list[AgentCallSite] = []
    scan_source = _strip_comments(source)
    call_re = re.compile(r"(?<![\w.])agent\s*\(")
    for m in call_re.finditer(scan_source):
        start = m.end() - 1  # index of the opening '('
        span = _scan_balanced_parens(source, start)
        if span is None:
            continue
        call_text = source[m.start():span + 1]
        # code-reviewer blocker: searching `call_text` as a whole lets a
        # PROMPT STRING mask the real option value -- a prompt merely
        # mentioning "agentType: 'explore'" or "model: 'opus'" in prose was
        # found (first match wins in call_text, which starts with the
        # prompt argument, not the trailing options object) to make a
        # genuinely dangerous `agentType: 'implement'` in the REAL options
        # object invisible to this check. `agent(prompt, {options})` always
        # carries its governance-relevant keys in the trailing object
        # literal, never the prompt argument -- so extract JUST that
        # object (the last top-level `{...}` in the argument list, string/
        # comment-aware) and search only within it. If no options object is
        # found at all, fall back to the full call_text (the safe/wider
        # direction per this checker's own stated principle: widening a
        # scan can only find MORE forbidden content, never hide it) so a
        # malformed/unusual call site is never silently skipped.
        options_text = _extract_trailing_options_object(source, start, span) or call_text
        agent_type_match = _AGENTTYPE_RE.search(options_text)
        model_match = _MODEL_RE.search(options_text)
        sites.append(
            AgentCallSite(
                index=len(sites),
                agent_type=agent_type_match.group(2) if agent_type_match else None,
                model=model_match.group(2) if model_match else None,
                span_text=call_text,
            )
        )
    return sites


def _extract_trailing_options_object(source: str, open_paren_index: int, close_paren_index: int) -> str | None:
    """Return the text of the LAST top-level `{...}` object literal inside
    an `agent(...)` call's argument list (the `open_paren_index`/
    `close_paren_index` bracket this call's own parens), or `None` if no
    top-level `{` is found between them.

    "Top-level" means at paren-depth 1 (immediately inside the call's own
    parens, not nested inside a template-literal `${...}` or another
    object) -- this is a plain string/comment-aware scan for the final `{`
    at that depth, then a balanced-brace scan from there to its matching
    `}`. `agent(prompt, {label, phase, schema, model, agentType})` always
    has its options object as the LAST top-level argument, so taking the
    last (not first) top-level `{` is deliberate -- a schema object
    literal earlier in the argument list must never be mistaken for the
    options object.
    """
    # code-reviewer round-2 blocker: this scan previously tracked PAREN depth
    # only, so a `{` NESTED inside an earlier top-level object (e.g. an
    # inline `schema: { model: 'sonnet' }` argument, which stays at
    # paren-depth 1 throughout) was wrongly recorded as its own "top-level"
    # candidate -- the scan kept overwriting `last_open_brace` with every
    # `{` it saw at paren-depth 1, including ones nested inside a brace it
    # had already opened, so it could end up pointing at an INNER brace
    # rather than the real trailing options object. Fixed by tracking BRACE
    # depth as well: once a top-level `{` is found, its own matching `}` is
    # located and the scan resumes AFTER it, so a `{` nested inside that
    # object is never independently considered a new top-level candidate --
    # only a `{` that starts a genuinely NEW, sibling object literal (at
    # paren-depth 1, brace-depth 0) can become the new `last_open_brace`.
    depth = 0
    in_string: str | None = None
    escaped = False
    last_open_brace: int | None = None
    i = open_paren_index
    n = len(source)
    while i <= close_paren_index and i < n:
        ch = source[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth -= 1
            i += 1
            continue
        if ch == "{" and depth == 1:
            last_open_brace = i
            # Skip over this object literal's own body (string/comment-
            # unaware here is fine -- we only need to find ITS matching `}`
            # so the outer scan resumes past it; the real extraction pass
            # below re-scans this exact span properly string-aware).
            brace_depth = 1
            j = i + 1
            j_in_string: str | None = None
            j_escaped = False
            while j < n and brace_depth > 0:
                jch = source[j]
                if j_in_string is not None:
                    if j_escaped:
                        j_escaped = False
                    elif jch == "\\":
                        j_escaped = True
                    elif jch == j_in_string:
                        j_in_string = None
                elif jch in ("'", '"', "`"):
                    j_in_string = jch
                elif jch == "{":
                    brace_depth += 1
                elif jch == "}":
                    brace_depth -= 1
                j += 1
            i = j
            continue
        i += 1

    if last_open_brace is None:
        return None

    brace_depth = 0
    in_string = None
    escaped = False
    i = last_open_brace
    while i <= close_paren_index and i < n:
        ch = source[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                return source[last_open_brace:i + 1]
        i += 1
    return None


def _scan_balanced_parens(source: str, open_paren_index: int) -> int | None:
    """Return the index of the matching close-paren, or None if unbalanced.

    Tracks string literals (', ", `) so a `)` inside a prompt string never
    prematurely closes the call. Does not attempt to handle nested template
    literal `${...}` interpolation specially -- a `)` inside one is rare in
    practice for these call sites and, worst case, only widens the scanned
    span (never narrows it below the real call), which is the safe direction
    for a purity CHECKER (a wider span can only find MORE forbidden content,
    never hide it).
    """
    depth = 0
    in_string: str | None = None
    escaped = False
    i = open_paren_index
    n = len(source)
    while i < n:
        ch = source[i]
        if in_string is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def check_source(source: str, label: str = "<source>") -> list[str]:
    """Return a list of failure-reason strings for one file's already-read
    source text. Empty list means clean. Pure -- no IO."""
    failures: list[str] = []

    for needle in _FORBIDDEN_SUBSTRINGS:
        if needle in source:
            failures.append(
                f"{label}: contains forbidden substring {needle!r} -- a Workflow "
                f"script has no shell/fs access (RULE G1(b))."
            )

    sites = find_agent_call_sites(source)
    for site in sites:
        if site.agent_type is not None and site.agent_type in _FORBIDDEN_AGENT_TYPES:
            failures.append(
                f"{label}: agent() call #{site.index + 1} uses forbidden "
                f"agentType {site.agent_type!r} -- never a reviewer, never a "
                f"writer inside a Workflow script (RULE G1(a))."
            )
        if not site.model:
            failures.append(
                f"{label}: agent() call #{site.index + 1} has no literal "
                f"'model:' key in its options -- every agent() call must pin "
                f"an explicit model (RULE G1(a))."
            )
        elif site.model not in _ALLOWED_MODELS:
            failures.append(
                f"{label}: agent() call #{site.index + 1} pins model "
                f"{site.model!r}, not one of {sorted(_ALLOWED_MODELS)!r} -- RULE "
                f"G1's own stated sonnet-only requirement (RULE G1(a))."
            )

    return failures


def check_file(path: str, source: str) -> list[str]:
    """Same as check_source, labeled with the file path for readable output."""
    return check_source(source, label=path)


def inventory_lines(path: str, source: str) -> list[str]:
    """Human-readable inventory of every agent() call found and its model --
    printed on a clean pass so success is evidence, not silence."""
    sites = find_agent_call_sites(source)
    if not sites:
        return [f"  {path}: no agent() call sites found."]
    lines = [f"  {path}: {len(sites)} agent() call site(s):"]
    for site in sites:
        lines.append(
            f"    #{site.index + 1}: agentType={site.agent_type!r} model={site.model!r}"
        )
    return lines


def discover_wheel_workflow_files(workflows_dir: str = _WORKFLOWS_DIR) -> list[str]:
    """Glob ONLY `issue-wheel-*.js` under workflows_dir -- never the whole
    directory. This is the exact scoping that keeps `deliver.js` untouched."""
    pattern = os.path.join(workflows_dir, _FILENAME_GLOB_PATTERN)
    return sorted(glob.glob(pattern))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv:
        paths = list(argv)
    else:
        paths = discover_wheel_workflow_files()

    if not paths:
        print("[check_workflow_agent_purity] no issue-wheel-*.js files found; nothing to check.")
        return 0

    all_failures: list[str] = []
    inventory: list[str] = []

    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        except OSError as exc:
            all_failures.append(f"{path}: could not read file ({exc})")
            continue
        all_failures.extend(check_file(path, source))
        inventory.extend(inventory_lines(path, source))

    if all_failures:
        print("[check_workflow_agent_purity] FAIL:", file=sys.stderr)
        for f in all_failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("[check_workflow_agent_purity] PASS. Inventory:")
    for line in inventory:
        print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
