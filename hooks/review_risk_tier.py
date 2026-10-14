#!/usr/bin/env python3
"""review_risk_tier — classify a pending change's review risk tier.

WHY THIS EXISTS
---------------
`~/.claude/CLAUDE.md` §10 used to CLAIM review was "cost-gated (default the
cheaper model; escalate to Opus for substantial diffs)" -- verified
2026-08-20 that this gate never existed anywhere in `hooks/` or
`agents/code-reviewer.md` (hard-pinned `opus`, unconditionally). Every
review, trivial or not, has been paying full adversarial-Opus cost. This
module is the missing piece: a pure, fast, deterministic classifier an
orchestrating agent consults BEFORE deciding which review tier to run.

THIS IS NOT A HOOK. It is not wired into pretooluse_bash.py's dispatcher and
it does not block anything. It CANNOT be a PreToolUse gate the way gate 3b
is: gate 3b checks "was a review recorded for this exact digest," which is
answerable from a `git commit` tool call alone. "Was the RIGHT TIER of
review used" is not answerable from a tool call -- it depends on which
agent/model actually did the reviewing, a fact that lives in the
conversation, not in anything a hook can observe. So this is deliberately a
CONSULTED HELPER: `~/.claude/CLAUDE.md` §10 tells an orchestrating agent to
run this before dispatching code-reviewer, and to skip full Opus review
only for a TRIVIAL verdict. Enforcement is by agent compliance with that
documented process, not by mechanical gate -- narrower and weaker than gate
3b, and explicitly known to be so. Mechanically enforcing tier compliance
(e.g. extending record_review.py's ledger to capture which model reviewed,
and having gate 3b require a real review for any HIGH-tier path) is a real,
larger follow-up, not built here.

TIERS
-----
  HIGH     -- touches a path this runtime treats as security/money/policy/
              enforcement-sensitive (see the pattern tables below). Full
              Opus adversarial review, unchanged from today. A single
              matching path anywhere in the change forces HIGH regardless
              of what else is trivial in the same change -- this only ever
              WIDENS toward more review, never narrows.
  TRIVIAL  -- every changed path is docs-only or a lock/generated file, AND
              none of them also match a HIGH pattern. Full Opus review MAY
              be replaced with a cheaper-model confirmatory pass PLUS the
              existing test suite/lint actually passing -- NEVER with zero
              review (see CLAUDE.md SS10; self-recording `--clean` with no
              review of any kind was blocker 5 of the round-2 audit that
              produced this module's current shape). Test-only changes are
              deliberately NOT eligible for TRIVIAL (see _is_test's
              docstring) -- they float to MODERATE instead, and neither is a
              path under a `tests/` subdirectory of hooks/ or agents/ (that
              only exempts it from ITS PARENT's HIGH status, it does not
              grant TRIVIAL).
  MODERATE -- everything else (the default), including test-only changes.
              Full Opus review, unchanged.

Never raises: classify() degrades to MODERATE (the safe middle default) on
any unexpected input rather than guessing TRIVIAL.

ROUND-2 REVIEW (2026-08-20) found the first version of this module
under-classified into TRIVIAL in four ways, all fixed here: (1) the
operating contract (`CLAUDE.md`) and every agent PROMPT except two hardcoded
filenames classified trivial, even though an agent prompt is executable
policy in this runtime; (2) `.txt`/bare `.html` treated dependency manifests
and app templates as docs; (3) test-only changes classified TRIVIAL,
including test infrastructure (`conftest.py`), and a diff that only DELETES
assertions or adds a skip decorator is exactly the shape §0/§6/§11 of the
contract say review exists to catch -- giving it the least scrutiny inverted
the contract; (4) no path normalization let a `..` segment defeat the
`hooks/` segment match.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HIGH = "high"
MODERATE = "moderate"
TRIVIAL = "trivial"

# Whole PATH-SEGMENT names that force HIGH -- matched against the NORMALIZED
# path split on "/", not by substring, so this fires identically for a
# relative pathspec ("hooks/foo.py", the common `git commit --` form) and an
# absolute one ("/repo/hooks/foo.py"), does NOT false-positive on an
# unrelated path that merely CONTAINS the word (e.g. "my_hooks_helper.py" is
# not "hooks/foo.py"), and cannot be defeated by a `hooks/tests/../foo.py`
# traversal (normalize_path collapses it before this ever runs).
# "agents": an agent's own PROMPT is executable policy in this runtime
# (browser-ops drives prod origins; any agent's instructions can be
# weakened by an edit) -- every file under agents/, not just the two
# reviewer prompts, belongs here.
# "schedules": a job PROMPT under schedules/prompts/ (and the plists beside
# it) drives an UNATTENDED launchd session that can dispatch agents and land
# reviewed commits with no human present -- at least as risk-sensitive as an
# agent prompt (2026-08-27: the finishing-loop prompt classified `moderate`
# while its safety preconditions were being rewritten).
_HIGH_RISK_DIR_SEGMENTS = frozenset({"hooks", "agents", ".github", "schedules"})

# Exact BASENAMES (matched case-insensitively against the final path
# component, any directory depth) that force HIGH.
_HIGH_RISK_BASENAMES = frozenset({
    "settings.json",
    "claude.md",  # the operating contract itself, in ANY repo this runs in
    "firestore.rules",
    "storage.rules",
    "allowlist.json",
})

# Free-text KEYWORDS (matched case-insensitively, substring against the
# normalized path) that force HIGH. Deliberately broad and substring-based
# -- under-matching here is the LEAK direction (a risky change gets a cheap
# review), so this errs toward flagging more than strictly necessary, never
# fewer -- the exact same asymmetry _matches_include_flag and
# _EXCUSABLE_VIA_REAL_CONTENT already apply elsewhere in this codebase.
# NOTE: keep entries long/specific enough to avoid incidental collisions
# with unrelated English words (dropped "iam" 2026-08-20 after review found
# it matches "diameter"; "auth"/"permission"/"credential"/"token"/"security"
# already cover identity/access without it) -- prefer a directory-segment or
# basename rule over a short keyword when the risk is directory-shaped.
#
# This is the BASE, repo-agnostic list -- runtime_bundle_repo_agnostic_plan.md
# WS4.5 (H8) removed "catalog" (a ExampleApp-specific product-catalog
# term that had no business being baked into a runtime-wide classifier).
# `classify()` UNIONS this with the calling repo's own
# `security.extra_risk_keywords` (`<repo>/.claude/oversight/manifest.json`,
# resolved from the CALLING PROCESS's cwd via `git rev-parse
# --show-toplevel` -- see `_repo_extra_keywords`) at classification time, so
# CSA's manifest carrying `"catalog"` restores the old behavior for CSA
# specifically without hardcoding it here for every other repo. No repo, no
# manifest, or no key -> this base list only, never a crash, never another
# repo's manifest.
_HIGH_RISK_KEYWORDS = (
    # Money.
    "pricing", "billing", "invoice", "payment", "stripe",
    "estimate", "markup", "cost", "opex",
    # Identity/access.
    "auth", "permission", "membership", "license", "seat", "session",
    "security", "secret", "credential", "token",
    # Data-shape changes that are hard to reverse once live.
    "migration", "schema", "firestore",
    # Deploy/infra -- a bad change here can take prod down, not just be wrong.
    "cloudbuild", "terraform", "deploy",
)

# A path counts as "docs" for TRIVIAL purposes only if it's ALSO not
# something that carries real logic or supply-chain weight. `.txt` was
# REMOVED (round-2 review): `requirements.txt`/`constraints.txt`/
# `CMakeLists.txt` all end in `.txt` and are not docs. `.html` is scoped
# to exclude a `templates/` directory (an app template, not documentation
# prose) via _is_doc's own check below, not by extension alone.
_DOC_EXTENSIONS = (".md", ".rst")
_DOC_HTML_EXTENSION = ".html"

# Manifest/build-config basenames that must never be treated as docs even
# though some (rarely) end in an extension that could look doc-adjacent.
_MANIFEST_BASENAMES = frozenset({
    "requirements.txt", "constraints.txt", "cmakelists.txt",
})

_TEST_PATTERNS = (
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"[^/]+_test\.py$"),
    re.compile(r"\.test\.[jt]sx?$"),
    re.compile(r"\.spec\.[jt]sx?$"),
)

# Generated/lock files: real diffs, but not hand-written logic a reviewer
# is meaningfully evaluating -- the tool that generated them is the thing
# that was reviewed, once, when it was introduced.
_LOCK_BASENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "cargo.lock", "gemfile.lock",
})


def _repo_root(cwd: str) -> str:
    """`git rev-parse --show-toplevel` at `cwd`, or "" on any failure.

    Same subprocess discipline as `check_staged_scope._repo_root` /
    `redact_browser_phi._repo_root` -- kept local to this module rather than
    imported cross-hook, per this module's existing single-file design.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or None,
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    try:
        return proc.stdout.decode("utf-8", "replace").strip()
    except Exception:  # pragma: no cover - decode with 'replace' cannot raise
        return ""


def _manifest_list(dotted_key: str, repo_root: str) -> list[str]:
    """Read a list-valued manifest key via `scripts/repo_manifest.py get`.

    Returns `[]` on ANY failure -- no repo, no manifest, no such key, a
    malformed manifest, a missing/unreadable `repo_manifest.py`, or a
    non-list value. Degrades open exactly like every other hook: a manifest
    read failure only ever narrows back to the base keyword list, it can
    never crash classify() or force an unrelated repo's keywords onto this
    one.
    """
    if not repo_root:
        return []
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "repo_manifest.py")
    try:
        proc = subprocess.run(
            [sys.executable, script, "get", dotted_key, "--repo", repo_root],
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        value = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return [v.lower() for v in value if isinstance(v, str) and v]


def _repo_extra_keywords(cwd: str | None = None) -> tuple[str, ...]:
    """The calling repo's own `security.extra_risk_keywords`, or `()`.

    `cwd` defaults to this process's own cwd -- the classifying CALLER's
    directory, per this module's design (`classify()` is a pure function of
    its `paths` argument alone; this helper is the one impure resolution
    step `main()` performs once per invocation before calling `classify()`
    with the resolved extra-keyword set threaded through -- see `main()`).
    Explicit `cwd` exists so tests/CLI callers can point this at an
    arbitrary directory without mutating the process's real cwd.
    """
    if cwd is None:
        try:
            cwd = os.getcwd()
        except OSError:
            # The process's cwd was deleted out from under it (routine in
            # this runtime: a worktree reap, a peer session removing a
            # directory a long-lived process is sitting in) -- degrade to
            # the base keyword list exactly like every other failure mode
            # this helper handles, never a crash. Restated as its own guard
            # rather than folded into `_repo_root`'s own try/except because
            # `os.getcwd()` runs BEFORE `_repo_root` is ever called.
            return ()
    repo_root = _repo_root(cwd)
    return tuple(_manifest_list("security.extra_risk_keywords", repo_root))


def _normalize(path: str) -> str:
    """Lowercased, `..`/`.`-collapsed, `/`-separated form used by every
    check below. All classification logic operates on THIS, never the raw
    input -- a single normalization point is what makes the segment/keyword/
    basename checks agree with each other and closes the `..`-traversal gap
    a round-2 review found (`hooks/tests/../pretooluse_bash.py` used to slip
    past the `hooks` segment rule because only the raw string was split).
    """
    # normpath on a POSIX-style relative pathspec; os.path handles this
    # correctly on macOS/Linux (the only platforms this hook runs on).
    return os.path.normpath(path).replace(os.sep, "/").lower()


def _is_high_risk(norm: str, extra_keywords: tuple[str, ...] = ()) -> bool:
    segments = norm.strip("/").split("/")
    basename = segments[-1] if segments else norm
    # A hooks/tests/ or agents/tests/ (or any high-risk-dir + a test-shaped
    # path) only ADDS verification -- it cannot weaken enforcement the way
    # editing the enforcement logic/prompt itself can, so it does not
    # inherit its parent directory's HIGH status from the segment rule
    # alone. It can still be forced HIGH by a keyword or basename hit below
    # (e.g. a test file about auth, or literally named CLAUDE.md). Calls
    # _is_test (round-2 review finding D: an earlier version duplicated this
    # as an inline "tests" not in segments check, which made _is_test dead
    # code -- editing _TEST_PATTERNS silently did nothing to this rule).
    dir_hit = any(seg in _HIGH_RISK_DIR_SEGMENTS for seg in segments)
    if dir_hit and not _is_test(norm):
        return True
    if basename in _HIGH_RISK_BASENAMES:
        return True
    if any(kw in norm for kw in _HIGH_RISK_KEYWORDS):
        return True
    # Repo-supplied additions (e.g. CSA's "catalog") -- unioned, never
    # substituted, and only ever WIDENS toward HIGH like every other rule
    # in this function.
    return any(kw in norm for kw in extra_keywords if kw)


def _is_doc(norm: str) -> bool:
    segments = norm.strip("/").split("/")
    basename = segments[-1] if segments else norm
    if basename in _MANIFEST_BASENAMES:
        return False
    if any(norm.endswith(ext) for ext in _DOC_EXTENSIONS):
        return True
    if norm.endswith(_DOC_HTML_EXTENSION):
        # An app TEMPLATE is not documentation prose, even though it ends in
        # .html -- round-2 review found ExampleApp's
        # marketing/website/templates/*.html (which carries pixel IDs/build
        # secrets per project memory) was classifying as docs.
        return "templates" not in segments
    return False


def _is_test(norm: str) -> bool:
    """True for a test-shaped path. NOT consulted by classify() to grant
    TRIVIAL (round-2 review: a diff that only deletes assertions or adds a
    skip is exactly what review exists to catch, so test-only floats to
    MODERATE, never lower) -- used only to EXEMPT a test path from
    inheriting its parent high-risk directory's status in _is_high_risk.
    """
    return any(pat.search(norm) for pat in _TEST_PATTERNS)


def _is_lock(norm: str) -> bool:
    basename = norm.rsplit("/", 1)[-1]
    return basename in _LOCK_BASENAMES


def classify(paths: list[str], extra_keywords: tuple[str, ...] = ()) -> tuple[str, str]:
    """(tier, reason) for the given pathspec. Never raises.

    An empty pathspec classifies MODERATE (the safe default) rather than
    TRIVIAL -- "nothing to classify" is not the same claim as "verified
    safe to skip review."

    `extra_keywords` -- the calling repo's own `security.extra_risk_keywords`
    (see `_repo_extra_keywords`), unioned into the HIGH keyword check.
    `classify()` itself stays a pure function of its two arguments; cwd/git/
    subprocess resolution happens once in `main()` (or the caller) and is
    threaded in here, never performed by `classify()` itself -- so this
    stays trivially unit-testable with no filesystem/git dependency, exactly
    as it was before this parameter existed.
    """
    try:
        clean = [p for p in (paths or []) if p]
        if not clean:
            return MODERATE, "empty pathspec -- default to moderate, not trivial"

        normalized = [(p, _normalize(p)) for p in clean]

        high_hits = [p for p, norm in normalized if _is_high_risk(norm, extra_keywords)]
        if high_hits:
            return HIGH, f"touches risk-sensitive path(s): {', '.join(high_hits[:5])}"

        # TRIVIAL requires EVERY path to be docs-only or a lock file.
        # Test-only paths (and everything else) fall through to MODERATE.
        non_trivial = [p for p, norm in normalized if not (_is_doc(norm) or _is_lock(norm))]
        if not non_trivial:
            return TRIVIAL, "every path is docs-only or a lock/generated file"

        return MODERATE, f"real change(s) needing full review: {', '.join(non_trivial[:5])}"
    except Exception:
        return MODERATE, "classification failed -- defaulting to moderate (safe direction)"


def main(argv: list[str] | None = None) -> int:
    """CLI: print `TIER  reason` for the given paths (argv, one per token).

    The repo whose `security.extra_risk_keywords` apply is decided by THIS
    PROCESS's cwd -- there is no `--repo` flag on this CLI by design: the
    classifier is always invoked from inside the repo whose change is being
    classified (exactly like `git commit` itself), so cwd is the intended
    signal, and never a caller-supplied path argument that could be spoofed
    to pull in a different repo's keyword list via THIS CLI's own interface.
    Running this from `/tmp` (no repo) resolves `()` extra keywords and
    classifies against the base list only.

    **cwd is NOT immune to an inherited `GIT_DIR`/`GIT_WORK_TREE` environment
    override, because `_repo_root` shells out to `git rev-parse
    --show-toplevel` with the process's full inherited environment (same
    pattern as `check_staged_scope._repo_root` -- a pre-existing, shared
    behavior, not unique to this module).** A caller whose environment sets
    `GIT_DIR` to a different repo's `.git` gets THAT repo's
    `extra_risk_keywords`, in either direction (can also silently NARROW
    away the actual calling repo's own extra keywords). This is a real,
    unresolved gap shared with every other cwd-resolving hook in this
    runtime, not something this module's design closes -- the "no `--repo`
    flag" decision above prevents ONE spoofing vector (an explicit CLI
    argument), not this one. Scrubbing `GIT_DIR`/`GIT_WORK_TREE`/
    `GIT_COMMON_DIR` from the subprocess environment before the `git
    rev-parse` call would close it here; doing so consistently across every
    `_repo_root`-shaped helper in the runtime is the real fix and is a
    tracked follow-up, not scoped to this change.

    Always exits 0 -- this is an advisory classifier, never a gate; a
    non-zero exit here must never look like a review deny to a caller
    scripting against this tool's output.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = _repo_extra_keywords()
    tier, reason = classify(argv, extra)
    print(f"{tier}\t{reason}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
