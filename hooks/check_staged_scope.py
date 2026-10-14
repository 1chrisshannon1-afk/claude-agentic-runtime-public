#!/usr/bin/env python3
"""check_staged_scope — PreToolUse:Bash hook.

Reinforces PATH-SCOPED commits by (a) requiring an explicit `git commit --
<pathspec>` on every writing commit segment, and (b) inspecting the ACTUAL git
index (not just the command string) for the narrow cases still allowed to omit
one. Where git_guard.sh blocks the bulk STAGERS (`git add -A/./-u`,
`git commit -a`) by reading the command tokens, this guard catches what they
cannot see: an index that was already polluted (an earlier bulk add, an IDE
"stage all", a stray edit) so the commit would sweep unrelated files or reach
outside the change's declared scope — and, since the "mandatory pathspec" plan
(CLAUDE.md §3), it ALSO closes the loophole a hand-staged index with no
pathspec at all used to leave open (gate 3 used to just judge the whole staged
index; a commit could dodge scoping entirely by never using `--`).

MANDATORY PATHSPEC (per writing `git commit` segment — see
writing_commit_segments):
  * NO explicit pathspec -> BLOCK "missing-pathspec", UNLESS:
      (i)   a merge/cherry-pick/revert/rebase is in progress (git itself
            refuses a partial/path-scoped commit mid-merge, so a
            pathspec-less commit here is legitimate recovery — see
            merge_in_progress), or
      (ii)  the segment is `--allow-empty` (commits nothing new), or
      (iii) env CSA_NO_REQUIRE_PATHSPEC=1 (operator rollback lever).
    Every exemption still falls through to the SAME staged-index scope/sweep
    check described below, unchanged — the exemption lifts ONLY the
    missing-pathspec block, never the scope/sweep guard itself.
  * A BULK pathspec (".", "./", "..", ":/", ":/.", "*", or an absolute path
    whose realpath equals the repo root's) -> BLOCK "bulk-pathspec".
    `git commit -- .` must never become the sanctioned workaround.
  * A real, non-bulk pathspec -> checked against SWEEP THRESHOLDS ONLY (too-
    many-files / too-many-top-dirs — see _sweep_decide), applied to the
    PATHSPEC SET instead of the staged index (no blanket allow — a directory
    pathspec entry counts as ONE path for MAX_FILES/MAX_DIRS purposes; that
    undercount is a documented, accepted residue, not a bug). The
    out-of-scope check is DELIBERATELY NOT applied to a named pathspec: a
    commit that explicitly names its own paths after `--` has already done
    the scoping — that's the entire point of "path-scoped commits" — so
    re-deriving a scope from the conventional-commit message prefix and
    blocking when a named path's directory doesn't literally contain that
    prefix is redundant AND wrong (the prefix is a topic label, e.g.
    "ai_agent", not a literal directory requirement; a normal commit pairing
    code with docs/tests in the same commit — CLAUDE.md-mandated — would
    otherwise false-positive-block; see _decide_with_pathspec's docstring).
  * A compound command is judged PER WRITING SEGMENT, first violation wins:
    `git commit -m a -- x && git commit -m b` blocks on the second segment.
    A `--dry-run` segment writes nothing and is skipped entirely — but, since
    it is simply excluded from the segment list rather than short-circuiting
    the whole command (the old, narrower behavior), it no longer suppresses
    guarding of a LATER real segment in the same compound command.

SCOPE/SWEEP DECISION (pure, testable — decide()):
  decide() itself is used ONLY for the STAGED-INDEX path — i.e. the narrow
  set of pathspec-less-commit exemptions above (merge-in-progress,
  --allow-empty, CSA_NO_REQUIRE_PATHSPEC=1), where there is no explicit
  pathspec to trust. Given that staged path set plus a declared SCOPE
  (conventional-commit prefix in the -m message, or the CSA_COMMIT_SCOPE env
  override), it blocks when the set would:
    * include paths OUTSIDE the declared scope, or
    * SWEEP unrelated files — too many files, or breadth across too many
      unrelated top-level directories (the accidental `add -A` signature).
  An explicit, non-bulk PATHSPEC (see MANDATORY PATHSPEC above) is judged by
  the sweep half only (_sweep_decide, shared with decide()) — never the
  scope half — via _decide_with_pathspec(), not decide().

CONTRACT (mirrors git_guard.sh / the shared-lib hooks):
  * Reads the hook payload as JSON from STDIN (via _lib.read_event).
  * Structured as PURE decision functions (`decide()`, plus the per-segment
    `_decide_missing_pathspec`/`_decide_with_pathspec`) + a thin `main()` that
    reads the event, gathers the staged index, decides, emits/logs, exits 0.
  * DENY is via the canonical PreToolUse JSON object, NEVER via exit code.
  * LOG-ONLY by default: logs the would-block and exits 0 (allow) unless
    enforcing() resolves ON (env CSA_ENFORCE=1 / ~/.claude/.enforce marker /
    per-project .claude/.csa-enforce).
  * CSA_DISABLE_HOOKS=1 is the master OFF switch (no-op allow, no logging).
  * CSA_STAGED_SCOPE_DRYRUN=print prints the decision word (ALLOW/BLOCK) to
    stdout and exits 0, regardless of enforce/log-only (test harness hook).
  * Never raises out to the caller: a crashing hook must never break the agent,
    so main() degrades OPEN (allow) on any unexpected error.

Config env:
  CSA_COMMIT_SCOPE          declared-scope override (see scope_from_message).
  CSA_NO_REQUIRE_PATHSPEC=1 operator rollback lever: a pathspec-less commit
                             falls straight through to the staged-index
                             scope/sweep check, exactly as before this
                             module's "mandatory pathspec" change.
  CSA_STAGED_SCOPE_DRYRUN=print   test-harness decision-word printer.
  CSA_DISABLE_HOOKS=1        master OFF.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already shims the path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

HOOK_NAME = "check_staged_scope"

# Sweep thresholds. A commit staging more than MAX_FILES paths, or spanning more
# than MAX_TOP_DIRS unrelated top-level directories, looks like an accidental
# bulk stage rather than a focused, path-scoped change.
DEFAULT_MAX_FILES = 30
DEFAULT_MAX_TOP_DIRS = 4

# Conventional-commit subject:  type(scope): summary   — the scope in parens is
# the declared blast-radius. We map it to a path segment to check the index.
_CONVENTIONAL_RE = re.compile(
    r"^\s*(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\(([^)]+)\))?[!]?:\s",
)


class Decision:
    """A pure, comparable result: action in {ALLOW, BLOCK}, plus a reason.

    `detail` carries the machine-readable specifics (offending paths, counts)
    that main() folds into the log record and the operator-facing message.
    """

    __slots__ = ("action", "reason", "detail")

    def __init__(self, action: str, reason: str, detail: dict | None = None):
        self.action = action
        self.reason = reason
        self.detail = detail or {}

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Decision)
            and self.action == other.action
            and self.reason == other.reason
            and self.detail == other.detail
        )

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Decision({self.action!r}, {self.reason!r}, {self.detail!r})"


def _allow(reason: str, detail: dict | None = None) -> Decision:
    return Decision("ALLOW", reason, detail)


def _block(reason: str, detail: dict | None = None) -> Decision:
    return Decision("BLOCK", reason, detail)


# ---------------------------------------------------------------------------
# Command inspection — is this a real `git commit` we should guard, and what
# does EACH writing segment carry (pathspec / message / amend / allow-empty)?
# ---------------------------------------------------------------------------


def _pathspec_from_args(args: list[str]) -> list[str]:
    """Explicit pathspec after a `--` in one commit segment's args, or []."""
    if "--" in args:
        idx = args.index("--")
        return [p for p in args[idx + 1 :] if p]
    return []


def _message_from_args(args: list[str]) -> str:
    """The -m / --message value in one commit segment's args, or "".

    Handles `-m msg` / `--message msg` / `--message=msg`. Combined short
    flags like `-am` are a git_guard concern (blocked upstream) — here we
    only look for the message value.
    """
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" or a == "--message":
            if i + 1 < len(args):
                return args[i + 1]
            return ""
        if a.startswith("--message="):
            return a[len("--message=") :]
        i += 1
    return ""


def writing_commit_segments(command: str) -> list[dict]:
    """Every `git commit` segment of `command` that WRITES (i.e. is not
    `--dry-run`), each as ``{"argv", "pathspec", "message", "amend",
    "allow_empty"}``.

    Reuses _lib.git_segments (the proven tokenizer) so compound/pipe/subshell
    forms are handled identically to git_guard.sh. `-n` is git commit's
    `--no-verify` short flag, NOT dry-run — only the LONG `--dry-run` token
    means "writes nothing" (mirrors the pre-existing is_git_commit check,
    which only ever tested for that literal token, never `-n`).

    Unlike a single first-match lookup, EVERY qualifying segment of a
    compound command is returned — a leading `--dry-run` commit must not
    suppress guarding of a LATER, real one in the same command (e.g.
    `git commit --dry-run && git commit -m x`).
    """
    segments: list[dict] = []
    for seg in _lib.git_segments(command):
        if len(seg) >= 2 and seg[0] == "git" and seg[1] == "commit":
            subargs = seg[2:]
            if "--dry-run" in subargs:
                continue
            segments.append(
                {
                    "argv": subargs,
                    "pathspec": _pathspec_from_args(subargs),
                    "message": _message_from_args(subargs),
                    "amend": "--amend" in subargs,
                    "allow_empty": "--allow-empty" in subargs,
                }
            )
    return segments


def is_git_commit(command: str) -> bool:
    """True iff ANY segment of `command` is a `git commit` that WRITES.

    See writing_commit_segments' docstring: this now checks the WHOLE
    (possibly compound) command, not just its first commit-shaped segment.
    """
    return bool(writing_commit_segments(command))


def commit_pathspec(command: str) -> list[str]:
    """Explicit pathspec on the FIRST `git commit` segment of `command`
    (regardless of --dry-run), or [].

    Kept for backward compatibility with callers that only care about "the"
    pathspec of a simple, single-segment commit. A gate that must consider
    EVERY writing segment (e.g. pretooluse_bash.py's target-path resolution)
    uses writing_commit_segments() directly instead.
    """
    for seg in _lib.git_segments(command):
        if len(seg) >= 2 and seg[0] == "git" and seg[1] == "commit":
            return _pathspec_from_args(seg[2:])
    return []


def commit_message(command: str) -> str:
    """The -m / --message argument of the FIRST `git commit` segment of
    `command` (regardless of --dry-run), or "" — same first-segment-only
    caveat as commit_pathspec().
    """
    for seg in _lib.git_segments(command):
        if len(seg) >= 2 and seg[0] == "git" and seg[1] == "commit":
            return _message_from_args(seg[2:])
    return ""


def scope_from_message(message: str) -> str | None:
    """The conventional-commit scope token, or None.

    `feat(voice): ...` -> "voice"; `fix: ...` (no scope) -> None; free-form
    subjects -> None. A slashed scope like `feat(api/routes): x` keeps the whole
    "api/routes" so it can match a nested path prefix.
    """
    if not message:
        return None
    m = _CONVENTIONAL_RE.match(message)
    if not m:
        return None
    scope = m.group(1)
    if not scope:
        return None
    scope = scope.strip()
    return scope or None


# ---------------------------------------------------------------------------
# Path helpers — pure.
# ---------------------------------------------------------------------------


def _normalize(path: str) -> str:
    """Strip a leading ./ and any surrounding whitespace from a staged path."""
    p = path.strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def top_dir(path: str) -> str:
    """The first path segment (top-level directory), or "" for a root file."""
    p = _normalize(path)
    if "/" not in p:
        return ""
    return p.split("/", 1)[0]


def _scope_matches(path: str, scope: str) -> bool:
    """True iff a staged `path` is within the declared `scope`.

    A path is in-scope when the scope token appears as a path segment: the top
    dir equals the scope, OR the scope (which may be slashed, e.g. "api/routes")
    is a path-segment-aligned substring of the path. Root-level files (no dir)
    are never bound to a directory scope and are handled by the caller.
    """
    p = _normalize(path)
    parts = p.split("/")
    # Whole-token match on any single segment (handles scope="voice").
    if scope in parts[:-1] or scope == parts[0]:
        return True
    # Slashed scope: match an aligned run of segments (scope="api/routes").
    if "/" in scope:
        seq = scope.split("/")
        for start in range(0, len(parts) - len(seq) + 1):
            if parts[start : start + len(seq)] == seq:
                return True
    return False


# ---------------------------------------------------------------------------
# PURE DECISION FUNCTION.
# ---------------------------------------------------------------------------


def _sweep_decide(
    paths: list[str],
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_top_dirs: int = DEFAULT_MAX_TOP_DIRS,
) -> Decision:
    """Sweep-only checks against an already-normalized, non-empty path set.

    Pure; has NO opinion on scope — it only catches the accidental-bulk-stage
    SHAPE of a path set (too many files, or breadth across too many unrelated
    top-level directories), never whether the paths belong to a declared
    scope. Shared by `decide()` (staged-index path: scope THEN sweep) and
    `_decide_with_pathspec()` (explicit-pathspec path: sweep ONLY — see that
    function's docstring for why scope is never checked there).

    Order of checks (first hit wins):
      1. too many files              -> BLOCK (sweep).
      2. too many unrelated top dirs -> BLOCK (breadth sweep).
      3. otherwise                   -> ALLOW.
    """
    if len(paths) > max_files:
        return _block(
            "too-many-files",
            {"count": len(paths), "max_files": max_files},
        )

    # Breadth: unrelated top-level directories. Root-level files (top == "")
    # count as their own "root" bucket so a scatter of loose files still trips.
    tops = {top_dir(p) or "<root>" for p in paths}
    if len(tops) > max_top_dirs:
        return _block(
            "too-many-top-dirs",
            {"top_dirs": sorted(tops), "count": len(paths), "max_top_dirs": max_top_dirs},
        )

    return _allow("in-scope", {"count": len(paths), "top_dirs": sorted(tops)})


def decide(
    staged_paths,
    *,
    scope: str | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    max_top_dirs: int = DEFAULT_MAX_TOP_DIRS,
) -> Decision:
    """Decide ALLOW/BLOCK for the STAGED INDEX given a path set and a scope.

    `staged_paths` is the git INDEX's staged paths for a pathspec-less commit
    that was exempted from the mandatory-pathspec requirement (see
    decision_for_event/_decide_missing_pathspec) — there is no explicit
    pathspec to trust in that case, so this is the only path in the module
    that still derives a scope from the commit message and checks it. An
    explicit `git commit -- <paths>` PATHSPEC set is judged separately by
    `_decide_with_pathspec()`, which deliberately does NOT call this function
    with the message-derived scope: a named pathspec has already been
    hand-scoped by the person/agent writing the commit, so re-deriving a
    scope from the conventional-commit prefix and blocking on a literal
    directory-prefix mismatch is both redundant and wrong (the prefix is a
    topic label, not a path).

    Args:
      staged_paths: the path set this decision checks.
      scope: the declared scope token (conventional-commit scope / env override)
             or None when the commit declares no scope.
      max_files: sweep threshold on the path-set's file count.
      max_top_dirs: sweep threshold on distinct top-level directories.

    Order of checks (first hit wins):
      1. empty path set                    -> ALLOW (git will no-op/abort).
      2. out-of-scope paths (scope given)   -> BLOCK.
      3. too many files                     -> BLOCK (sweep).
      4. too many unrelated top dirs        -> BLOCK (breadth sweep).
      5. otherwise                          -> ALLOW.
    """
    paths = [_normalize(p) for p in staged_paths if p and p.strip()]

    if not paths:
        return _allow("empty-index", {"count": 0})

    # Scope enforcement. Only when the commit DECLARES a scope do we check it;
    # an unscoped commit falls through to the sweep heuristics.
    if scope:
        out_of_scope = [p for p in paths if not _scope_matches(p, scope)]
        if out_of_scope:
            return _block(
                "out-of-scope",
                {
                    "scope": scope,
                    "out_of_scope": sorted(out_of_scope),
                    "count": len(paths),
                },
            )

    return _sweep_decide(paths, max_files=max_files, max_top_dirs=max_top_dirs)


# ---------------------------------------------------------------------------
# Bulk-pathspec detection — pure given an optional pre-resolved repo_root.
# ---------------------------------------------------------------------------

# Literal pathspec tokens git/agents use to spell "commit everything" — never
# a real, specific path.
_BULK_PATHSPEC_TOKENS = frozenset({".", "./", "..", ":/", ":/.", "*"})


def is_bulk_pathspec(pathspec, repo_root: str | None = None) -> bool:
    """True iff ANY entry of `pathspec` names "the whole tree" rather than a
    real, specific path: a literal whole-tree token (see
    _BULK_PATHSPEC_TOKENS), or an absolute path whose realpath equals the
    repo root's realpath (the same sweep, spelled as an absolute path).
    `git commit -- .` must never be the sanctioned workaround for the
    missing-pathspec requirement.

    `repo_root` is optional: the abs-realpath check is simply skipped (never
    a false negative on the cheap literal checks above) when it is not
    supplied or fails to resolve — the caller already degrades open in that
    case, matching every other check in this module. Pure given its inputs.
    """
    root_real = None
    if repo_root:
        try:
            root_real = os.path.realpath(repo_root)
        except Exception:
            root_real = None
    for raw in pathspec:
        entry = (raw or "").strip()
        if entry in _BULK_PATHSPEC_TOKENS:
            return True
        if root_real and os.path.isabs(entry):
            try:
                if os.path.realpath(entry) == root_real:
                    return True
            except Exception:
                pass
    return False


# ---------------------------------------------------------------------------
# Env config — pure.
# ---------------------------------------------------------------------------


def require_pathspec_from_env(environ: dict | None = None) -> bool:
    """False iff CSA_NO_REQUIRE_PATHSPEC=1 — the operator rollback lever that
    downgrades the mandatory-pathspec requirement back to the pre-existing
    staged-index-only scope/sweep check. True (pathspec REQUIRED) by default.
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_NO_REQUIRE_PATHSPEC", "") != "1"


# ---------------------------------------------------------------------------
# Index / repo-state readers — the only impure parts; isolated so decide()
# and the per-segment decision helpers below stay pure.
# ---------------------------------------------------------------------------


def read_staged_paths(cwd: str) -> list[str]:
    """Return the paths currently staged in the index at `cwd`, or [].

    Runs `git diff --cached --name-only -z` (NUL-delimited, so filenames with
    spaces/newlines survive). Never raises: a missing git, a non-repo cwd, or a
    timeout yields [] so the guard degrades OPEN. No network is ever touched.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "-z"],
            cwd=cwd or None,
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        raw = proc.stdout.decode("utf-8", "replace")
    except Exception:  # pragma: no cover - decode with 'replace' cannot raise
        return []
    return [p for p in raw.split("\x00") if p]


def _repo_root(cwd: str) -> str:
    """`git rev-parse --show-toplevel` at `cwd`, or "" on any failure.

    Isolated impure helper (mirrors read_staged_paths' subprocess discipline)
    used ONLY to resolve the repo root when a caller did not already have one
    to pass in. The common dispatcher path (pretooluse_bash.py) resolves this
    ONCE for several gates and threads it in instead — see resolve_block.
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


_MERGE_STATE_GIT_PATHS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")


def _git_path_exists(cwd: str, git_path: str) -> bool:
    """True iff `git -C <cwd> rev-parse --git-path <git_path>` resolves to an
    existing file/dir. Never raises; degrades to False on any failure (no
    git, non-repo cwd, timeout) — matching read_staged_paths' discipline.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd or ".", "rev-parse", "--git-path", git_path],
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    try:
        resolved = proc.stdout.decode("utf-8", "replace").strip()
    except Exception:  # pragma: no cover - decode with 'replace' cannot raise
        return False
    if not resolved:
        return False
    return os.path.exists(resolved)


def merge_in_progress(cwd: str) -> bool:
    """True iff a merge/cherry-pick/revert/rebase is currently in progress at
    `cwd`. Git itself refuses a partial/path-scoped commit mid-merge (`git
    commit -- <path>` errors out), so a pathspec-less commit here is
    legitimate recovery, not an agent skipping scoping — the mandatory-
    pathspec requirement exempts it (see _decide_missing_pathspec).

    Only ever invoked on the rare pathspec-less-commit path (see
    decision_for_event), so these extra git subprocess calls are never paid
    for the common, already-scoped case. Never raises.
    """
    return any(_git_path_exists(cwd, p) for p in _MERGE_STATE_GIT_PATHS)


# ---------------------------------------------------------------------------
# Event-level decision — isolated so both this module's main() AND the
# consolidated pretooluse_bash dispatcher can reuse the exact same
# scope-gathering + decide() logic without duplicating it.
# ---------------------------------------------------------------------------


def should_guard(ev: dict) -> bool:
    """True iff this event is a Bash `git commit` that WRITES (worth guarding).

    A non-Bash tool, a non-commit command, or a `--dry-run`-only commit is not
    guarded. Never raises: any error degrades to False (allow, unguarded).
    """
    try:
        if _lib.tool_name(ev) != "Bash":
            return False
        return is_git_commit(_lib.bash_command(ev))
    except Exception:  # pragma: no cover - _lib helpers already fail-safe
        return False


def _decide_missing_pathspec(
    seg: dict,
    staged_paths,
    *,
    scope: str | None,
    mid_merge: bool,
    require_pathspec: bool,
    max_files: int = DEFAULT_MAX_FILES,
    max_top_dirs: int = DEFAULT_MAX_TOP_DIRS,
) -> Decision:
    """Decide ONE writing commit segment that has NO explicit `-- <pathspec>`.

    Pathspec is MANDATORY by default -> BLOCK "missing-pathspec", UNLESS one
    of three exemptions applies:
      (i)   mid_merge — a merge/cherry-pick/revert/rebase is in progress (see
            merge_in_progress); git itself refuses a partial commit here, so
            requiring a pathspec would just break real recovery.
      (ii)  seg["allow_empty"] — an --allow-empty commit.
      (iii) not require_pathspec — the CSA_NO_REQUIRE_PATHSPEC=1 operator
            rollback lever.
    Every exemption still falls through to the SAME staged-index scope/sweep
    check decide() performs for any other path set — the exemption lifts
    ONLY the missing-pathspec block itself, never the scope/sweep guard
    (the resulting Decision carries a "pathspec_exempt" detail key naming
    which exemption applied, for operator-facing logging).

    Pure given its precomputed inputs (mid_merge/require_pathspec are
    resolved by the impure caller, decision_for_event).
    """
    exemption: str | None = None
    if mid_merge:
        exemption = "merge-in-progress"
    elif seg.get("allow_empty"):
        exemption = "allow-empty"
    elif not require_pathspec:
        exemption = "no-require-pathspec-env"

    if exemption is None:
        return _block(
            "missing-pathspec",
            {"hint": 'git commit -m "..." -- <path> [<path>...]'},
        )

    result = decide(staged_paths, scope=scope, max_files=max_files, max_top_dirs=max_top_dirs)
    detail = dict(result.detail)
    detail["pathspec_exempt"] = exemption
    return Decision(result.action, result.reason, detail)


def _decide_with_pathspec(
    pathspec: list[str],
    *,
    scope: str | None,
    repo_root: str | None,
    max_files: int = DEFAULT_MAX_FILES,
    max_top_dirs: int = DEFAULT_MAX_TOP_DIRS,
) -> Decision:
    """Decide ONE writing commit segment that DOES carry an explicit
    `-- <pathspec>`.

    A bulk/whole-tree pathspec (see is_bulk_pathspec) is BLOCKed outright.
    Otherwise the pathspec set is judged by SWEEP THRESHOLDS ONLY
    (too-many-files / too-many-top-dirs, via `_sweep_decide`) — deliberately
    NOT the scope check `decide()` applies to the staged-index path.

    Why no scope check here: a commit that names its own paths after `--` has
    ALREADY done the scoping — that is the entire point of "path-scoped
    commits". Re-deriving a scope from the conventional-commit prefix in the
    `-m` message and blocking when a named path's directory doesn't literally
    contain that prefix is both redundant (the pathspec IS the scope
    declaration) and wrong: the prefix is a topic label ("ai_agent"), not a
    literal directory requirement, so a completely normal commit pairing code
    with docs/tests in the same commit (CLAUDE.md-mandated) would otherwise
    false-positive-block. The `scope` parameter is accepted (and still
    threaded through by the caller) for signature symmetry with
    `_decide_missing_pathspec` / logging call-sites, but is intentionally
    unused for the decision itself. Sweep protection (accidental bulk-add)
    still fully applies. Pure given its precomputed `repo_root`.
    """
    del scope  # intentionally unused — see docstring: pathspec already scopes itself
    if is_bulk_pathspec(pathspec, repo_root):
        return _block("bulk-pathspec", {"pathspec": list(pathspec)})
    paths = [_normalize(p) for p in pathspec if p and p.strip()]
    if not paths:
        return _allow("empty-index", {"count": 0})
    return _sweep_decide(paths, max_files=max_files, max_top_dirs=max_top_dirs)


def decision_for_event(ev: dict, staged_paths: list[str], repo_root: str | None = None) -> Decision:
    """Decision for a commit event given its already-read staged index.

    Evaluates EVERY writing `git commit` segment of the event's command (see
    writing_commit_segments) — a compound command with more than one writing
    segment (`git commit -m a -- x && git commit -m b`) is judged segment by
    segment, FIRST violation wins, exactly like every other gate in this hook
    suite.

    `repo_root`, when the caller already resolved it (the common case: the
    pretooluse_bash.py dispatcher resolves it once for several gates — see
    resolve_block), is reused as-is; otherwise it is resolved lazily, at most
    once, ONLY when some segment actually needs it (a pathspec present that
    might be an absolute repo-root path) — the common relative-pathspec /
    no-pathspec case never pays for that subprocess call. `merge_in_progress`
    is likewise resolved lazily, at most once, only when some segment has no
    pathspec at all.

    The staged index itself is passed in by the caller (the ONLY impure step
    the caller must perform, via read_staged_paths) so this function's own
    control flow stays simple and unit-testable independent of a real repo.

    Never raises: any unexpected error degrades to an ALLOW so a crashing
    guard cannot break the agent.
    """
    try:
        command = _lib.bash_command(ev)
        where = _lib.cwd(ev)
        segments = writing_commit_segments(command)
        if not segments:
            return _allow("no-writing-commit-segment")

        env_scope = os.environ.get("CSA_COMMIT_SCOPE", "").strip() or None
        require_pathspec = require_pathspec_from_env()

        merge_state: dict = {}
        root_state: dict = {}

        def _mid_merge() -> bool:
            if "v" not in merge_state:
                merge_state["v"] = merge_in_progress(where)
            return merge_state["v"]

        def _resolved_root() -> str | None:
            if "v" not in root_state:
                root_state["v"] = repo_root or (_repo_root(where) or None)
            return root_state["v"]

        decision = _allow("no-writing-commit-segment")
        for seg in segments:
            seg_scope = env_scope if env_scope is not None else scope_from_message(seg["message"])
            pathspec = seg["pathspec"]
            if pathspec:
                decision = _decide_with_pathspec(pathspec, scope=seg_scope, repo_root=_resolved_root())
            else:
                decision = _decide_missing_pathspec(
                    seg,
                    staged_paths,
                    scope=seg_scope,
                    mid_merge=_mid_merge(),
                    require_pathspec=require_pathspec,
                )
            if decision.action == "BLOCK":
                return decision
        return decision
    except Exception:  # pragma: no cover - decide()+helpers are fail-safe
        return _allow("decision-error")


# ---------------------------------------------------------------------------
# Deny message — reason-aware, shared by this module's own main() AND the
# pretooluse_bash.py dispatcher's gate-3 wiring, so an operator sees the same
# prescriptive text regardless of which entry point emitted it.
# ---------------------------------------------------------------------------


def deny_message(decision: Decision) -> str:
    """The operator-facing PreToolUse deny message for a BLOCK Decision."""
    if decision.reason == "missing-pathspec":
        return (
            "check_staged_scope: blocked commit (missing-pathspec). "
            "Path-scoped commits are mandatory. Stage explicit paths and "
            'commit with: git commit -m "..." -- <path> [<path>...]. '
            "See ~/.claude/.enforcement/log.jsonl."
        )
    if decision.reason == "bulk-pathspec":
        return (
            "check_staged_scope: blocked commit (bulk-pathspec). "
            "'git commit -- .' (or another whole-tree pathspec) is never a "
            "substitute for real path scoping. Name the exact paths this "
            "commit is about. See ~/.claude/.enforcement/log.jsonl."
        )
    return (
        f"check_staged_scope: blocked commit ({decision.reason}). "
        "The index would sweep files outside this change's scope. "
        "Stage only the paths this commit is about "
        "(git restore --staged <unrelated>), then retry. "
        "See ~/.claude/.enforcement/log.jsonl."
    )


# ---------------------------------------------------------------------------
# THIN main().
# ---------------------------------------------------------------------------


def _dryrun_mode() -> bool:
    return os.environ.get("CSA_STAGED_SCOPE_DRYRUN", "") == "print"


def _emit_dry(action: str) -> None:
    print(action)


def main() -> int:
    """Read the event, decide, emit/log, exit 0. Deny is via JSON, never code."""
    try:
        # Master OFF switch. In dryrun, still report ALLOW so tests see the no-op.
        if _lib.disabled():
            if _dryrun_mode():
                _emit_dry("ALLOW")
            return 0

        ev = _lib.read_event()
        command = _lib.bash_command(ev)
        where = _lib.cwd(ev)

        # Only gate the Bash tool, and only a writing `git commit`.
        if not should_guard(ev):
            if _dryrun_mode():
                _emit_dry("ALLOW")
            return 0

        staged = read_staged_paths(where)
        decision = decision_for_event(ev, staged)

        if _dryrun_mode():
            _emit_dry(decision.action)
            return 0

        if decision.action == "BLOCK":
            enforce = _lib.enforcing(where)
            _lib.log(
                HOOK_NAME,
                "would-block",
                reason=decision.reason,
                command=command[:2000],
                enforce=enforce,
                **decision.detail,
            )
            if enforce:
                _lib.emit_pretooluse_deny(deny_message(decision))
            # log-only default: allow silently.
            return 0

        # ALLOW path — nothing to emit.
        return 0
    except Exception:
        # Degrade OPEN: a crashing guard must never break the agent.
        if _dryrun_mode():
            try:
                _emit_dry("ALLOW")
            except Exception:  # pragma: no cover - printing a constant cannot fail
                pass
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
