#!/usr/bin/env python3
"""block_head_overwrite — PreToolUse:Bash hook.

Blocks a destructive `git show <ref>:<path> > <path>` (or `git cat-file -p
<ref>:<path> > <path>`) self-overwrite: a plain shell redirect that writes a
historical git blob straight over the SAME path in the working tree.

WHY THIS EXISTS (GH #4387, plans/incidents/2026-08-21-payer-analysis-panel-
data-loss.md): this is a real, already-happened Sev-1 data-loss incident. An agent
ran `git show HEAD:agency/src/.../PayerAnalysisPanel.jsx > agency/src/.../
PayerAnalysisPanel.jsx` to "restore formatting sanity" without first checking
whether the working tree differed from HEAD for a reason other than its own
edits. It did — genuine, never-committed, never-staged feature work sat in
that file. The redirect overwrote it instantly and unrecoverably: it was
never in git's object database (unstaged content leaves no blob), so
`git fsck --unreachable --dangling` found nothing, no sibling branch/worktree
had it, and it was gone.

NO EXISTING GATE catches this. `block_branch_ops.py`'s STATE_VERBS
(checkout/switch/stash/reset/rebase/worktree/restore/clean) only inspects
`git` SUBCOMMANDS — `git show`/`git cat-file` are ordinary read-only git
operations and are correctly never in that set. The actual destructive act
here is a plain SHELL REDIRECT (`>`), which is not a git operation at all —
it is the shell overwriting a file, using git only as the content SOURCE.
This is the same class of gap `block_branch_ops.py`'s own module docstring
already flags as open ("git rm -f, checkout-index -f, ... remain
unblocked") — this hook closes the specific self-overwrite-via-redirect
shape, not that whole class.

DETECTS, via a dedicated raw-text scan (see the ROUND 3 note below
`_ESCAPE_VAR` for why this does NOT reuse `_lib.git_segments()`, the shared
tokenizer every OTHER gate in this chain uses for genuine git-subcommand
parsing):
  git show <ref>:<path>            > <dest>       (also >>, >|, N>, N>|)
  git cat-file -p <ref>:<path>     > <dest>       (also >>, >|, N>, N>|)
including multiple redirect operators after one invocation (each
destination checked independently) and multiple git show/cat-file
invocations in one compound command (each checked against only the text up
to the next real separator). <dest> resolves to the SAME path as <path>
(compared via a normalized, directory-agnostic match — see `_same_target` —
since <dest> may be relative, absolute, or `./`-prefixed while <path> is
almost always repo-relative). A bare `N>&M` fd-duplication (no file
destination) is correctly never read as a destination.

Deliberately narrow: a redirect to a DIFFERENT path (`git show HEAD:foo.py >
foo.py.bak`) is a legitimate, common pattern (diffing, scratch inspection,
extracting an old version under a new name) and is NOT blocked. Widening
this to "any git show/cat-file with any redirect" would block that
legitimate use and train agents to route around the gate rather than heed
it — see CLAUDE.md's own guidance that a gate should target the specific
proven-dangerous shape, not everything adjacent to it.

CONTRACT (matching every other gate in this chain):
  * PURE decision function `decide(event) -> Decision`. No I/O, no env reads.
  * Thin `main()`: read event, decide, log always on a would-block, emit the
    canonical PreToolUse deny only when enforcing(). Always exits 0.
  * CSA_DISABLE_HOOKS=1 master-OFF: no-op allow before anything else.
  * Escape hatch: CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env lets
    a would-block through (same var block_branch_ops.py already reserves for
    git-state escapes — this is the same class of operator override). Any
    command STRING containing that literal is DENIED (agents must never
    smuggle it inline) — same tripwire, same reasoning, as every sibling gate.
  * Parse-ambiguity fails OPEN here (unlike block_branch_ops' fail-CLOSED for
    state-verbs): an untokenizable segment cannot be proven to be this exact
    dangerous shape, and this hook's blast radius (a narrow, rare pattern) does
    not justify blocking on ambiguity the way branch-state mutation does.
  * Only the Bash tool is gated; every other tool is allowed.

OUT OF SCOPE, BY DESIGN (code-reviewer round-4 recommendation, so a future
round does not relitigate these as oversights): this hook matches against
STATIC command text only, never executes or emulates a shell. The
following are destructive in a real shell but UNDECIDABLE from static
text, and are NOT caught here:
  * Dynamic expansion of the destination or ref:path — `$VAR`,
    `${VAR}`, `$(...)` command substitution, backticks, brace expansion.
  * `eval`/`source`-wrapped commands, where the actual git invocation is
    inside a string this hook cannot see as executable text.
  * `exec`-scoped redirects (`exec > foo.py; git show HEAD:foo.py`) that
    redirect a WHOLE script's stdout ahead of an unrelated-looking later
    command.
  * Pipe-to-writer tools (`git show HEAD:foo.py | tee foo.py`, `| dd
    of=foo.py`, `| sponge foo.py`) — matching on "any git show/cat-file
    piped to anything" would over-block the equally common, safe
    `| less`/`| head`/`| grep` inspection patterns.
Widening detection to cover these would require either real shell
parsing/emulation (a categorically different, much larger undertaking) or
blocking every git show/cat-file with ANY redirect/pipe regardless of
destination — which reopens the over-blocking problem the "Deliberately
narrow" paragraph above already rejects. This hook's job is the common,
statically-detectable shapes; it is one layer of defense, not a complete
shell-semantics sandbox.

The module never raises out to the caller: a crashing hook must never break
the agent. Every unexpected error degrades to ALLOW.
"""

from __future__ import annotations

import os
import re
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirroring the other hooks)

HOOK_NAME = "block_head_overwrite"

# Reused from block_branch_ops.py — the same operator-only escape hatch, not a
# new var, so an operator does not need to remember two different names.
_ESCAPE_VAR = "CSA_ALLOW_GIT_STATE_OPS"

# ---------------------------------------------------------------------------
# ROUND 3 (trust-architect / code-reviewer, 2026-09-05): rounds 1 and 2 both
# tried to detect this shape by reusing `_lib.git_segments()` — the shared
# tokenizer every state-verb gate in this chain uses — and patching its
# mismatches with the redirect grammar one enumerated case at a time
# (spaced, then glued, then fd-qualified...). That tokenizer is fundamentally
# the WRONG tool for this: `_lib._split_segments()` treats bare `|` and `&`
# as command SEPARATORS (correct for its own job — finding independent git
# state-verb invocations in a compound command), but `|` and `&` are also
# REDIRECT-OPERATOR CHARACTERS in specific adjacent positions (`>|` the
# noclobber-override form, `2>&1` an fd-duplication) — so `_split_segments`
# tears exactly those redirects in half BEFORE this module ever sees them,
# no matter how the glued-token regex here is tuned. Round 2's reviewer
# proved 5 more real, shell-confirmed bypasses on this basis alone.
#
# The fix is to stop tokenizing at all for this hook's one narrow purpose.
# Detection now runs directly against the RAW command string via two
# independent regexes: `_GIT_SHOW_INVOKE_RE` finds a `git show`/`git
# cat-file` invocation and its `<ref>:<path>` spec wherever it appears
# (handling `git -C <dir>`/`-c k=v` global options and a leading ENV=val
# prefix inline, since there is no longer a shared tokenizer doing that
# stripping for us); `_REDIRECT_OP_RE` then scans the text immediately
# following that invocation, bounded only by a REAL separator (`;`, `&&`,
# `||`, newline — deliberately NOT bare `|`/`&`, which is exactly the
# grammar this rewrite exists to stop mis-treating as separators), for every
# redirect operator in that span — including multiple operators in one
# command, `>|`, and fd-duplication forms (`N>&M`, which is skipped: it has
# no file destination at all). Every operator's destination is checked
# against the ref:path spec independently, so `git show HEAD:a/b.py
# >/tmp/x>a/b.py` (two operators, one destination is a decoy) still blocks
# on its second, real destination.
# ---------------------------------------------------------------------------

# A `git show`/`git cat-file` invocation and its `<ref>:<path>` spec,
# anywhere in the raw command text. Handles a leading ENV=val prefix, `git`
# global options (`-C <dir>`, `-c k=v`, `--long-opt` or `--long-opt=value`
# glued with no space, or `-x [value]`), and `cat-file`'s `-p`/other flag
# OR its bare format word (`blob`/`tree`/`commit`/`size`/`type` — ROUND 4
# finding: `git cat-file blob HEAD:foo.py > foo.py` previously matched
# nothing at all, since only flag-shaped tokens were skipped). The ref
# itself is intentionally unconstrained (any non-colon, non-whitespace,
# non-separator text) — HEAD, a branch, a tag, a full SHA, or a relative
# form like HEAD~2 are all equally dangerous sources for this pattern.
# `[^\s;&|>]+:[^\s;&|>]+` requires at least one path-like character on each
# side of the colon and never crosses a real separator, a bare pipe/
# background character, OR a redirect operator -- the `>` exclusion is
# load-bearing: without it, a GLUED redirect with no space before it
# (`HEAD:foo.py>foo.py`) is swallowed whole into the refpath capture
# itself, hiding the operator from the destination scan entirely (a real
# bypass this exact shape reproduced before the exclusion was added). A
# colon-bearing option value belonging to a DIFFERENT, later command can
# likewise never be swept in.
#
# ROUND 5 (code-reviewer cold review, 2026-09-05): the leading boundary was
# an ENUMERATED alternation of separator/grouping characters (`;&|(){}`,
# `&&`, `||`, `$(`) — round 4 added `(){}`/`$(` to this same enumeration to
# close the subshell/brace-group gap, and round 5's reviewer proved that
# approach does not generalize: ANY word-plus-space preceding `git` (a
# shell keyword -- `if ... ; then git ...`, `for ... ; do git ...`,
# `while`/`until`/`else`/`elif` bodies -- or a command prefix -- `nohup`,
# `time`, `exec`, `command`, `stdbuf -o0`, a bare `!` negation) makes `git`
# invisible to an enumerated-opener match, and 15 such live-shell-confirmed
# destructive variants bypassed the gate. Replaced the whole enumeration
# with a real WORD-BOUNDARY check: `(?<![\w./-])` requires the character
# immediately before `git` to be either start-of-string or something that
# is NOT a word character, `.`, `/`, or `-` -- so `git` matches after ANY
# separator, keyword, prefix, or grouping construct (nothing to enumerate),
# while still correctly rejecting `mygit`, `./git`, and `my-git` as false
# positives (a git invocation is never glued onto a longer identifier or a
# relative-path prefix this way).
_GIT_SHOW_INVOKE_RE = re.compile(
    r"(?<![\w./-])"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*"
    r"git\s+"
    r"(?:(?:-C|-c)\s+\S+\s+|--[A-Za-z][\w-]*(?:=\S+)?\s+|-[A-Za-z](?:\s+\S+)?\s+)*"
    r"(?P<sub>show|cat-file)\s+"
    r"(?:-p\s+|--[A-Za-z][\w-]*(?:=\S+)?\s+|-[A-Za-z]\s+|(?:blob|tree|commit|size|type)\s+)*"
    r"(?P<refpath>[^\s;&|>]+:[^\s;&|>]+)"
)

# Splits a matched `<ref>:<path>` blob at its FIRST colon into (ref, path).
# Requires at least one path-like character after the colon so a bare
# "HEAD:" (which git itself rejects) never matches.
_REF_PATH_RE = re.compile(r"^[^:\s]+:(.+)$")

# A real command separator: only these end the region this hook scans for a
# redirect following a matched git invocation. Deliberately EXCLUDES bare
# `|` and `&` — see the ROUND 3 note above for why those are NOT reliable
# separators in this context (they are also redirect-operator characters).
# Scanning a few extra characters past a genuine pipe/background use is
# harmless: it can only widen a match onto text that happens to look like a
# same-path redirect, which is exactly the same conservative direction this
# hook already accepts for its narrow, rare pattern (see CONTRACT above).
#
# The newline alternative EXCLUDES a backslash-escaped newline (`(?<!\\)`)
# — ROUND 4 finding: a trailing `\` before a real shell line continuation
# is the SAME logical command as the next line, not a separator.
# `git show HEAD:foo.py \` + newline + `> foo.py` destroyed real content
# while this hook's redirect scan was truncated at the (falsely-treated-as-
# separator) newline, before ever reaching the `>` on the next line.
_REAL_SEPARATOR_RE = re.compile(r";|&&|\|\||(?<!\\)\n")

# Every redirect-out operator, including the noclobber form (`>|`) and an
# optional leading fd-number qualifier (`1>`, `2>`). Deliberately does NOT
# match `<` (input redirection, irrelevant here) or `>>` on its own without
# also matching plain `>` — `>>` matches first via alternation order.
_REDIRECT_OP_RE = re.compile(r"\d*(?:>>|>\|)|\d*>(?!\|)")

# An fd-duplication target immediately after an operator (`2>&1`) — this has
# NO file destination at all and must never be read as one. Requires a
# DIGIT after the `&` -- `&1`/`&2` are duplications, but a bare `&` with NO
# following digit is NOT a duplication: it is the leading character of
# bash's `>&` ("redirect both stdout and stderr") operator spelling, whose
# destination follows immediately after (see ROUND 4 finding below).
_FD_DUP_RE = re.compile(r"^\s*&\d+")

# The `>&` / `N>&` "both streams" redirect form (bash-specific, e.g. `>&
# foo.py`, distinct from `N>&M` fd-duplication, which `_FD_DUP_RE` already
# owns): an operator followed by a bare `&` with NO following digit. Matched
# separately so the destination scan can consume the `&` as part of the
# operator spelling rather than stopping on it as a stray separator
# character — ROUND 4 finding: `git show HEAD:foo.py >& foo.py` destroyed
# real content in both bash and zsh while this hook reported no match,
# because the destination-scan stop-set already included `&`, so scanning
# began and immediately terminated at the very next character.
_AMP_NO_DIGIT_RE = re.compile(r"^\s*&(?!\d)")


def _redirect_destinations(text: str) -> list[str]:
    """Return every redirect-out destination found in `text`, in order.

    For each `>`/`>>`/`>|` (optionally fd-qualified) operator: skip it
    entirely if immediately followed by an fd-duplication (`&N`, no file
    destination); otherwise, if immediately followed by a bare `&` (bash's
    `>&`/`N>&` "both streams" form — a genuine file destination, NOT a
    duplication, since there's no digit), consume that `&` before scanning;
    then capture the next whitespace/operator/separator-bounded word as a
    destination. Multiple operators in one string (e.g. `>/tmp/x>a/b.py`)
    each contribute their own destination — a caller checks ALL of them,
    not just the last, since shell evaluates every redirect and each one is
    independently a real write.

    Never raises: a malformed trailing operator with nothing after it
    contributes no destination, not an error; a non-string `text` (this
    function makes no assumption about its caller) returns an empty list
    rather than raising out of `re.finditer`.
    """
    try:
        dests: list[str] = []
        for m in _REDIRECT_OP_RE.finditer(text):
            after = text[m.end() :]
            if _FD_DUP_RE.match(after):
                continue
            amp_match = _AMP_NO_DIGIT_RE.match(after)
            if amp_match:
                after = after[amp_match.end() :]
            stripped = after.lstrip(" \t")
            end = 0
            # ROUND 6 (code-reviewer cold review, 2026-09-05), BLOCKER 1:
            # this stop-set must contain every character that can OPEN a
            # `git show`/`cat-file` invocation per `_GIT_SHOW_INVOKE_RE`'s
            # boundary (round 5's `(?<![\w./-])` lookbehind is open-ended,
            # not an enumeration -- it admits a backtick as an opener) --
            # otherwise a destination immediately followed by such a
            # character is captured WITH it glued on and never compares
            # equal to the bare ref path. `)`/`(`/`{`/`}` were added here in
            # ROUND 4 for exactly this reason; round 5 widened the OPENER
            # side to an open-ended lookbehind without re-widening this
            # CLOSER side to match, and backtick (`` ` ``, command
            # substitution: `` `git show HEAD:foo.py > foo.py` ``) leaked
            # through -- live-confirmed destructive in bash. The invariant:
            # every character this hook treats as able to precede `git` must
            # also be a destination stop character, or the two boundaries
            # silently drift apart again.
            while end < len(stripped) and stripped[end] not in " \t>;&|(){}`\n":
                end += 1
            dest = stripped[:end]
            if dest:
                dests.append(dest)
        return dests
    except Exception:
        return []


class Decision:
    """A pure decision result. `block` is the verdict; `reason` is the audit tag."""

    __slots__ = ("block", "reason")

    def __init__(self, block: bool, reason: str):
        self.block = block
        self.reason = reason

    def __eq__(self, other):
        return (
            isinstance(other, Decision)
            and self.block == other.block
            and self.reason == other.reason
        )

    def __repr__(self):  # pragma: no cover - debug aid only
        verb = "BLOCK" if self.block else "ALLOW"
        return f"Decision({verb}, {self.reason!r})"


def _unquote_dquote_body(word: str, start: int, n: int) -> tuple[str, int]:
    """Scan a double-quote-STYLE body starting at `start` (the character
    right after the opening `"` -- caller has already consumed any leading
    `$`) up to and including its closing `"`. Shared by `_shell_unquote`'s
    plain `"..."` and `$"..."` (bash locale-translation string) branches,
    since both close on `"` and process the identical backslash-escape set
    (`\\"`, `\\\\`, `\\$`, `` \\` ``) -- ROUND 6, see `_shell_unquote`'s
    own docstring for why `$"..."` needs this at all.

    Returns `(unescaped_body, index_just_past_the_closing_quote)`. If the
    quote is never closed, returns `(word[start:], n)` -- the unterminated
    remainder verbatim, same conservative degrade every other span in this
    module uses, never a guess at a close that was never written.
    """
    j = start
    buf: list[str] = []
    while j < n and word[j] != '"':
        if word[j] == "\\" and j + 1 < n and word[j + 1] in ('"', "\\", "$", "`"):
            buf.append(word[j + 1])
            j += 2
        else:
            buf.append(word[j])
            j += 1
    if j >= n:
        return word[start:], n
    return "".join(buf), j + 1


def _shell_unquote(word: str) -> str:
    """Remove shell quoting/escaping from `word`, the way a real shell's
    word-splitting would present it to the underlying command.

    ROUND 5 (code-reviewer cold review, 2026-09-05): a prior version of
    this module's quote-handling (in `_normalize_path`) stripped only a
    single, FULLY-MATCHED pair of surrounding quotes -- `"foo.py"` ->
    `foo.py`. A real shell removes quoting/escaping PER-CHARACTER, anywhere
    in the word, not just as one surrounding pair: `fo'o'.py`, `"foo".py`,
    `foo\\.py`, and `$'foo.py'` (ANSI-C quoting) are all real, live-shell-
    confirmed-destructive spellings of the plain word `foo.py`, and the
    surrounding-pair-only strip left every one of them unrecognized as the
    same path. This function handles, left to right:
      - a single-quoted span (`'...'`) -- everything inside is literal,
        no escape processing;
      - a double-quoted span (`"..."`) -- backslash escapes `\\"`, `\\\\`,
        `\\$`, `` \\` `` inside are unescaped, everything else literal;
      - a `$"..."` LOCALE-TRANSLATED string (ROUND 6, code-reviewer cold
        review, 2026-09-05: live-confirmed destructive bypass -- the `$`
        only triggered on a following `'`, so `$"foo.py"` fell through to
        the bare-character path and never unquoted at all) -- shares the
        SAME closing-quote character (`"`) and the SAME backslash-escape
        set as plain double-quoting; the leading `$` only adds locale
        translation, which is irrelevant to path identity, so this reuses
        the identical inner-scan logic via `_unquote_dquote_body`;
      - an ANSI-C quoted span (`$'...'`) -- a minimal set of backslash
        escapes (`\\n`, `\\t`, `\\'`, `\\\\`) are processed;
      - a bare backslash-escaped character outside any quote (`\\.` -> `.`).
    Never raises: any malformed/unterminated quote span is treated
    conservatively (the remainder of the word is appended literally rather
    than guessing at a close that was never written).
    """
    out: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        c = word[i]
        if c == "'":
            j = word.find("'", i + 1)
            if j == -1:
                out.append(word[i:])
                break
            out.append(word[i + 1 : j])
            i = j + 1
            continue
        if c == '"':
            body, j = _unquote_dquote_body(word, i + 1, n)
            out.append(body)
            i = j
            continue
        if c == "$" and i + 1 < n and word[i + 1] == '"':
            body, j = _unquote_dquote_body(word, i + 2, n)
            out.append(body)
            i = j
            continue
        if c == "$" and i + 1 < n and word[i + 1] == "'":
            j = word.find("'", i + 2)
            if j == -1:
                out.append(word[i:])
                break
            inner = word[i + 2 : j]
            inner = (
                inner.replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\'", "'")
                .replace("\\\\", "\\")
            )
            out.append(inner)
            i = j + 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(word[i + 1])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _normalize_path(p: str) -> str:
    """Normalize a path token for same-target comparison.

    Applies `_shell_unquote` (a real, common, equally-destructive shell
    spelling: `_redirect_destinations` captures the raw text between
    whitespace/operator boundaries, which does not itself strip quoting the
    way a real shell's word-splitting would, so `> "foo".py` or `>
    fo'o'.py` would otherwise silently ALLOW against a bare `foo.py` ref
    path), then strips a leading "./", and collapses "//" via
    os.path.normpath. Lowercases nothing (paths are case-sensitive on the
    filesystems this runs on). Never resolves against a real cwd or the
    filesystem — this is a pure string comparison, deliberately
    conservative: it only ever widens FALSE NEGATIVES (an oddly-spelled-but-
    equal path might not match, e.g. a symlink alias), never false
    positives, which matches this gate's narrow-by-design posture.
    """
    p = _shell_unquote(p.strip())
    if p.startswith("./"):
        p = p[2:]
    # normpath collapses "a//b", "a/./b", trailing slashes, etc. It does NOT
    # resolve ".." against a real cwd in a way that could be wrong here, since
    # both sides of the comparison go through the same normalization.
    return os.path.normpath(p) if p else p


def _same_target(ref_path: str, dest: str) -> bool:
    """True iff `dest` (the redirect target) resolves to the same path as
    `ref_path` (the path half of a <ref>:<path> spec).

    Two comparisons, either sufficient:
      1. Exact match after normalization (handles "./foo.py" vs "foo.py").
      2. `dest` is an ABSOLUTE path whose normalized tail equals the
         normalized `ref_path` — covers the exact GH #4387 shape, where the
         destination was the full absolute repo path
         (/Users/.../agency/src/.../PayerAnalysisPanel.jsx) while the <ref>:
         <path> spec used the repo-relative form. This is a suffix match on
         path SEGMENTS (never a bare string suffix), so
         "components/dental_analytics/PayerAnalysisPanel.jsx" does not
         false-positive-match a destination merely ending in the same
         filename with a different parent (e.g. some other Foo.jsx under an
         unrelated components/ tree one level up) unless the FULL relative
         path matches as a segment-aligned suffix. REQUIRES ref_path to have
         AT LEAST TWO segments (a directory plus a filename) for this
         heuristic to apply at all — a bare single-segment ref_path (just
         "Foo.jsx", no directory) would trivially suffix-match ANY absolute
         path ending in that filename regardless of its real parent
         directory, which is too weak a signal to treat as the same target;
         that case falls through to a plain ALLOW (no match) instead.
    """
    norm_ref = _normalize_path(ref_path)
    norm_dest = _normalize_path(dest)
    if not norm_ref or not norm_dest:
        return False
    if norm_ref == norm_dest:
        return True
    if os.path.isabs(norm_dest):
        ref_parts = norm_ref.split(os.sep)
        dest_parts = norm_dest.split(os.sep)
        if (
            len(ref_parts) >= 2
            and len(ref_parts) <= len(dest_parts)
            and dest_parts[-len(ref_parts) :] == ref_parts
        ):
            return True
    return False


def _find_redirect_overwrite(command: str) -> str | None:
    """Scan the RAW command string for a `git show`/`git cat-file` invocation
    whose output is redirected onto the SAME path its `<ref>:<path>` spec
    reads, anywhere in the command. Returns a reason string on a match, else
    None.

    ROUND 3 rewrite (see the module-level note above `_GIT_SHOW_INVOKE_RE`):
    operates directly on `command` text via regex, never through
    `_lib.git_segments()` — that tokenizer's `|`/`&` command-separator
    handling is fundamentally incompatible with redirect-operator grammar
    (`>|`, `N>&M`) and cannot be patched into correctness one enumerated
    case at a time (rounds 1 and 2 both tried; both were proven bypassable).

    Handles MULTIPLE independent git-show/cat-file invocations in one
    compound command (each `_GIT_SHOW_INVOKE_RE` match is checked against
    ONLY the text up to the next real separator) and MULTIPLE redirect
    operators following a single invocation (each destination is checked
    independently — shell evaluates every redirect, so a decoy destination
    before the real one must not hide it).

    The single `try/except` is the ONLY degrade-to-allow mechanism — any
    unexpected shape returns None (no match), never an exception.
    """
    try:
        for inv in _GIT_SHOW_INVOKE_RE.finditer(command):
            sub = inv.group("sub")
            ref_path_spec = inv.group("refpath")
            # A quoted (fully or PARTIALLY -- ROUND 5, see `_shell_unquote`)
            # ref:path spec (`git show "HEAD:foo.py" > foo.py`,
            # `git show HEAD:foo'.py' > foo.py`) is an equally real, equally
            # destructive shell spelling -- unquote it BEFORE splitting on
            # the colon, or a stray quote ends up glued onto the path half
            # and never compares equal to an unquoted destination.
            ref_path_spec = _shell_unquote(ref_path_spec)
            # The ref:path spec is `<ref>:<path>` — split on the FIRST colon
            # only, so a Windows-style drive-letter-free ref containing a
            # colon in the ref itself (rare, but SHA-like refs never do)
            # still yields the correct path half. `_REF_PATH_RE` reused
            # verbatim from earlier rounds -- no change to this piece.
            m = _REF_PATH_RE.match(ref_path_spec)
            if not m:
                continue
            ref_path = m.group(1)

            # Bound the redirect scan to the text between this invocation's
            # end and the next REAL separator (never a bare `|`/`&`, which
            # is exactly the grammar this rewrite exists to stop
            # mis-treating as a boundary here).
            sep_match = _REAL_SEPARATOR_RE.search(command, inv.end())
            scan_end = sep_match.start() if sep_match else len(command)
            tail = command[inv.end() : scan_end]

            for dest in _redirect_destinations(tail):
                if _same_target(ref_path, dest):
                    return f"{sub}-redirect-self-overwrite"
        return None
    except Exception:
        return None


def decide(event: dict) -> Decision:
    """PURE decision: does this event's Bash command redirect a git-show/
    cat-file read of <ref>:<path> back onto that SAME <path>?

    Precedence:
      1. Non-Bash tool                         -> ALLOW (not-bash-tool).
      2. Empty / whitespace-only command       -> ALLOW (empty-command).
      3. Command string carries the escape var literally -> BLOCK
         (inline-escape-var-forbidden) — agents must never smuggle it inline.
      4. Any git show/cat-file invocation anywhere in the raw command is
         redirected onto its own source path -> BLOCK (<sub>-redirect-
         self-overwrite).
      5. otherwise                             -> ALLOW (no-self-overwrite).

    ROUND 3 (see the module-level note above `_GIT_SHOW_INVOKE_RE`):
    detection now runs directly against the raw command TEXT
    (`_find_redirect_overwrite`), never through `_lib.git_segments()` — that
    shared tokenizer's `|`/`&` command-separator handling is fundamentally
    incompatible with the redirect grammar this hook must recognize
    (`>|`, `N>&M`). There is therefore no "untokenizable segment" concept
    left in THIS hook's own detection path (unlike block_branch_ops.py,
    which still needs it for genuine git-subcommand parsing) — a malformed
    or unparseable command simply matches no `_GIT_SHOW_INVOKE_RE`
    occurrence and falls through to ALLOW, which is the same fail-open
    posture this hook has always taken for ambiguity (see CONTRACT above).

    Never raises: any unexpected error degrades to a conservative allow.
    """
    try:
        if _lib.tool_name(event) != "Bash":
            return Decision(False, "not-bash-tool")

        command = _lib.bash_command(event)
        if not command or not command.strip():
            return Decision(False, "empty-command")

        if _ESCAPE_VAR in command:
            return Decision(True, "inline-escape-var-forbidden")

        reason = _find_redirect_overwrite(command)
        if reason:
            return Decision(True, reason)

        return Decision(False, "no-self-overwrite")
    except Exception:
        return Decision(False, "guard-error")


def _dryrun_mode() -> bool:
    """CSA_GUARD_DRYRUN=print — the test-harness hook that prints ALLOW/BLOCK."""
    return os.environ.get("CSA_GUARD_DRYRUN", "") == "print"


def _escape_hatch_active() -> bool:
    """CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env.

    Only meaningful once decide() has NOT already blocked on the inline
    tripwire — a command STRING containing the var is always blocked
    (inline-escape-var-forbidden) regardless of this env check, exactly as
    block_branch_ops.py already does.
    """
    return os.environ.get(_ESCAPE_VAR, "") == "1"


def main() -> int:
    """Entry point. Reads stdin, decides, emits/logs, returns exit code 0."""
    if _lib.disabled():
        return 0

    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    ev = _lib._parse_event(raw)
    if not ev:
        return 0

    d = decide(ev)

    if _dryrun_mode():
        print("BLOCK" if d.block else "ALLOW")
        return 0

    if not d.block:
        return 0

    command = _lib.bash_command(ev)

    if d.reason != "inline-escape-var-forbidden" and _escape_hatch_active():
        _lib.log(HOOK_NAME, "escape-allowed", reason=d.reason, command=command)
        return 0

    enforce = _lib.enforcing(_lib.cwd(ev))
    _lib.log(
        HOOK_NAME, "would-block", reason=d.reason, command=command, enforce=enforce
    )

    if enforce:
        _lib.emit_pretooluse_deny(
            "block_head_overwrite: blocked a git show/cat-file read of a path "
            "redirected back onto that SAME path (" + d.reason + "). This "
            "overwrites the working tree with historical content and "
            "PERMANENTLY DESTROYS any uncommitted/unstaged changes at that "
            "path with no git-recoverable trace (see GH #4387). If you need "
            "to inspect an old version, redirect to a DIFFERENT path (e.g. "
            "`git show HEAD:path/to/file > /tmp/file.bak`) or use "
            "`git diff -- <path>` to compare without overwriting anything. "
            "See ~/.claude/.enforcement/log.jsonl."
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
