#!/usr/bin/env python3
"""agentarch_metric_check — repo-agnosticism regression guard for
knowledge/agentarch_recommendations.jsonl.

THE DEFECT THIS GUARDS AGAINST: a `metric_command` that hardcodes an
absolute product-repo path (e.g. `/Users/<x>/Desktop/ExampleApp/...`)
is silently unmeasurable outside the one machine layout it names, and is
UNVERIFIABLE from any session whose sandbox root is a different repo (two
real rows, AA-0030/AA-0033, came back UNVERIFIED for exactly this reason on
2026-08-27). It is also a runtime/product-repo boundary violation in its own
right: this file lives in the RUNTIME (~/.claude), which must stay usable by
any repo, including one that does not exist yet.

THE FIX this module enforces: a `metric_command` that needs to inspect "a
repo" expresses that as a symbolic placeholder, ``${REPO:<slug>}``, never a
literal path. ``<slug>`` is resolved at RUN time against a small DATA
registry — ``~/.claude/knowledge/repo_registry.json`` by default — that maps
a slug to that repo's root on this machine. Adding a new repo later is a
one-line edit to that JSON file; it never touches this module's code. A
metric with no placeholder at all needs no repo (it is runtime-only, e.g.
anything already scoped to ``~/.claude/`` or ``/tmp/``) and is untouched by
either check below.

Why the registry isn't a new ledger field: `agentarch_recommendations.jsonl`
has a FIXED ten-field schema, exact key set AND order, mechanically enforced
by `hooks/validate_agentarch_ledger.py`'s `CANONICAL_FIELDS`/field-order
check (also restated in `agents/agentic-systems-architect.md`'s Read-FIRST
#4). Adding an eleventh `repo_scope` key would itself be a schema violation.
The placeholder's slug already carries that declaration inline, inside the
existing `metric_command` string — ``${REPO:exampleapp}`` IS the
scope declaration, and this module's migration also appends a
human-readable ``[repo_scope: <slug>]`` tag to the row's `metric` text for
anyone reading the ledger by eye. No schema change, no new field.

What this module checks, per row of the ledger:
  1. hardcoded-repo-path — any token in `metric_command` that is a BARE
     absolute path (starts with ``/`` or ``~``, or expands to one) outside
     the two roots every metric may always name directly (``~/.claude/``
     and ``/tmp/``), and is not expressed via ``${REPO:<slug>}``. This is
     the direct regression guard the task requires: it fails on exactly the
     pattern this file exists to prevent, and it does so WITHOUT hardcoding
     any product-repo name in this module's own code — it only knows what
     is always-safe (the runtime and /tmp), never what is "one particular
     product".
  2. unknown-repo-slug — a ``${REPO:<slug>}`` reference whose ``<slug>`` has
     no entry in the repo registry. Catches a typo'd or stale slug before it
     becomes a silently-dead metric (the same failure mode a hardcoded path
     produces, one layer down).

This module also exposes `resolve_command`, a pure function that
substitutes every ``${REPO:<slug>}`` in a command string for the
registry's real root, for any caller (the architect agent's own re-score
pass, an interactive check, a future runner) that wants to actually
EXECUTE a repo-scoped metric_command. This module's own CLI does not
execute metric commands — running the resolved command, applying the
guard-legality allowlist, and re-scoring it live against the ledger's
stored `checked_value` is `validate_agentarch_ledger.py`'s job. This
module only statically guards against the hardcoded-path regression and
validates that every placeholder resolves.

Exit code: 0 when clean, 1 when any violation is found. Never raises out of
main(): a crash is caught and reported as one violation line, exit 1.

Standalone: `python3 agentarch_metric_check.py [ledger_path] [registry_path]`

This module owns exactly two files:
  ~/.claude/hooks/agentarch_metric_check.py       (this file)
  ~/.claude/hooks/tests/test_agentarch_metric_check.py

ACTUAL SHIPPED DIVISION OF LABOR with `hooks/validate_agentarch_ledger.py`
(a separate, pre-existing structural/guard-legality/live-rescore validator
for the same ledger, owned by a different lane — never edit that file from
here): this module is the static path-legality guard (`find_hardcoded_paths`,
`resolve_command`, `load_registry`) plus its own standalone CLI.
`validate_agentarch_ledger.py` CONSUMES both of those functions directly —
it imports this module, resolves every row's `${REPO:<slug>}` placeholder
via `resolve_command`/`load_registry` before its own guard-legality bounds
check and live command run, and separately calls `find_hardcoded_paths` on
each row's raw (unresolved) command as part of its own `check_ledger` — so
the daily validator catches the same hardcoded-path regression even if this
module's own CLI is never invoked on its own. `check_ledger` also consumes
`root_is_acceptable` directly (Finding 1, round-2 security review,
2026-08-30) to validate its own CLI `extra_repo_root` argument against the
exact same overbroad/isdir/`.git`-presence test `load_registry` applies to
every registry-sourced root, so the two producers of the allowed-execution-
roots set can never again drift apart on what counts as "a real repo
checkout." See `validate_agentarch_ledger.py`'s own module docstring for the
exact consumption points and ordering.

THE PER-FORM ARGUMENT-GRAMMAR TABLE (root-cause fix, round-4 security review,
2026-08-30): `FORM_GRAMMARS` below is the single, shared source of truth for
every recognized command form's flags -- arity (0/1/2), which half of a
two-token flag is a real filesystem target vs. a value never read from disk,
and which form has a positional "pattern"/"filter" role at all (and under
what condition, since the two differ: grep/rg's PATTERN role is satisfied
EITHER positionally or via `-e`, never both, while jq's FILTER role is
ALWAYS positional regardless of `--arg`/`--argjson`/`--slurpfile`/
`--rawfile`). Before this table existed, `validate_agentarch_ledger.py`'s
`guard_check` modeled each command form with a flag *allowlist* and no
argument *grammar*, while this module's own `_pattern_arg_index` modeled a
second, independent, partial grammar for grep/rg's pattern argument alone --
neither knew the other's rules, and four-plus rounds of security review each
patched one more grammar fact into one module or the other without ever
unifying them (the reviewer's own diagnosis, round-4 security review,
2026-08-30). `grep` and `rg` are separate forms (B2) because they are, in
real life: verified live against this machine's `/usr/bin/grep` (BSD grep
2.6.0-FreeBSD, GNU-compatible) -- grep has no `-g` flag at all. rg's own
arities (`-e`/`-g`/`-r`/`-E` all VALUE-consuming, unlike grep's own
boolean `-r`/`-E`) are sourced from ripgrep's own published documentation
(`rg --help`/`man rg`), not live-execution-verified IN THIS ENVIRONMENT
(round-5 security review, 2026-08-30, correcting an overclaim the round-4
comment made here and at `FORM_GRAMMARS`' own `"rg"` entry below: this
machine's interactive shell resolves a typed `rg` command through a Claude
Code wrapper shell function, not a real ripgrep binary reachable by
`subprocess.run`'s bare PATH lookup -- `shutil.which("rg")` returns `None`
here, confirmed live, meaning no `rg`-headed ledger row is actually
EXECUTABLE in this environment at all today; the arities themselves are
still correct for real ripgrep, just not re-verifiable by running one here).
Merging grep and rg under one flag table was itself a root cause of the
arity confusion the old design kept re-discovering one letter at a time.

THE SINGLE LEFT-TO-RIGHT CONSUMING SCANNER (root-cause fix, round-5 security
review, 2026-08-30, superseding round-4's own "unification"): round-4's fix
above replaced a flag *allowlist* with a flag *table*, but the three
functions that read that table (`flag_value_indices`,
`positional_role_exempt_index`, and `_not_positional_role_candidate_indices`,
all REMOVED by this round) each re-walked the token list independently, with
different filters -- the reviewer's own diagnosis of round-5's finding:
"Three independent walks over one token list cannot agree on what a token
*is* -- that is the same failure mode as the two-module divergence round-4
set out to fix, moved inside one module." Two composed defects followed
directly from that: (a) `_paths_in_bounds`' flag-value shape gate (M2, round-4)
ran BEFORE the `..`-traversal check, so a flag value that was a RELATIVE
path carrying `..` was never traversal-checked at all (the gate only ever
caught an ABSOLUTE/`~`-prefixed flag value); (b) `flag_value_indices` marked
a value-consuming flag's OWN OCCURRENCE-INDEPENDENT string match, not a real
left-to-right consumption, so `-e -e <path>` let the SECOND `-e` (which is
really the FIRST `-e`'s VALUE) get wrongly re-classified as ANOTHER flag
needing its own value, exempting `<path>` -- a working, reproduced exploit:
`grep -c -e -e ../../../etc/hosts` and `grep -rl -e -e ../../../etc/ssh`
were both guard-legal and actually executed, reading real filesystem
content. `classify_tokens` below is the fix: it walks a form's post-head
token slice EXACTLY ONCE, left-to-right, consuming each value-consuming
flag's value token(s) IMMEDIATELY as it encounters the flag (so a token
already consumed as one flag's value can never be reconsidered as a
different flag, a positional-role candidate, or any other role later in the
same pass), and returns one `TokenRole` per token. `classify_command`/
`flag_is_allowed`/`end_of_options_index` are unaffected by this round (they
were never part of the three-independent-walk defect -- see each one's own
docstring for why); `_paths_in_bounds` (execution-gating bounds check) and
`find_hardcoded_paths` (static hardcoded-path reporting) both now consume
`classify_tokens`' structural output as a LOOKUP -- reading which `kind` a
token was classified as -- rather than re-deriving it via their own
independent scan, though each still applies its OWN, documented, and
DIFFERENT policy for which classified kinds it treats as exempt from its own
check (a flag's positional PATTERN/FILTER role, for instance, is always
exempt from `_paths_in_bounds`' EXECUTION gate only when its own shape does
not already look like a real path, per M2 below -- but is unconditionally
exempt from `find_hardcoded_paths`' STATIC report only when it additionally
carries no whitespace, since a genuinely prose pattern is never itself "a
path", even one that happens to mention one in free text; see each
function's own docstring for its exact policy). Fail-closed by construction:
`classify_tokens` only ever assigns the `POSITIONAL_ROLE` kind to a token
for a form whose grammar declares that role at all, and only for the ONE
token that form's own real-world semantics actually assign it -- every OTHER
token, for every form, is `PATH_CANDIDATE` (or a flag/flag-value/pathspec
kind), never silently exempted by omission.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from typing import Literal

_HOME = os.path.expanduser("~")
_CLAUDE_ROOT = os.path.join(_HOME, ".claude") + os.sep
_TMP_ROOT = "/tmp" + os.sep
_ALWAYS_SAFE_ROOTS = (_CLAUDE_ROOT, _TMP_ROOT)
# Neither root constant above is realpath'd, and that is now DELIBERATE
# (round 6 review, 2026-08-28): `path_resolves_under_root` below never
# compares strings, so it makes no difference whether `_TMP_ROOT` is
# spelled `/tmp` or its macOS symlink target `/private/tmp` — `os.stat`
# resolves the symlink itself at comparison time either way. Do not
# "fix" this by adding a realpath call; it would be a no-op cargo-culted
# from the old string-comparison design these constants used to serve.
# ~/.claude/projects/ holds per-SESSION transcripts, named after the
# session's own cwd — a path under it almost always encodes a specific
# product repo's name (e.g. .../projects/-Users-x-Desktop-OtherApp/...)
# hidden inside what looks like a plain runtime path, AND is per-session
# (absent, not merely different, from every other session), so a
# metric_command that names one silently scores as "moved" from any other
# session's run. Carved OUT of the otherwise-blanket ~/.claude/ exemption
# (Blocker E, 2026-08-28) — never automatically safe just because it lives
# under ~/.claude/.
_NEVER_SAFE_ROOTS = (os.path.join(_CLAUDE_ROOT, "projects") + os.sep,)

DEFAULT_LEDGER_PATH = os.path.join(_HOME, ".claude", "knowledge", "agentarch_recommendations.jsonl")
DEFAULT_REGISTRY_PATH = os.path.join(_HOME, ".claude", "knowledge", "repo_registry.json")

_PLACEHOLDER_RE = re.compile(r"\$\{REPO:([A-Za-z0-9_.-]+)\}")


# --------------------------------------------------------------------------
# shared filesystem-IDENTITY containment test (Blocker 1, round 6 review,
# 2026-08-28) — THE canonical implementation both this module and
# `validate_agentarch_ledger.py` use for EVERY path-containment check
# (never-safe-roots, the CLAUDE_ROOT/registered-repo-root allow-list, and
# the TMP_ROOT check alike). `validate_agentarch_ledger.py` already imports
# this module (the reverse import would be a cycle), so it imports these
# functions directly rather than duplicating them — see that module's own
# comment at its point of use for the cross-reference.
# --------------------------------------------------------------------------


def _deepest_existing_ancestor(path: str) -> str:
    """Walks up from `path` (already absolute) to the first ancestor that
    actually exists on disk — `path` itself when it already exists (e.g. an
    `ls`/`cat` target that is really there), or a real directory some
    levels up when it is a file/directory not yet created (e.g. a `cat`
    destination about to be written, or several nested not-yet-existing
    directories). Falls back to the filesystem root (which always exists)
    rather than looping forever. Read-only — never creates, removes, or
    otherwise mutates anything, only stats/checks existence. Pure w.r.t.
    the filesystem's own contents.
    """
    current = path
    while not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:  # reached the filesystem root
            break
        current = parent
    return current


def _same_filesystem_entry(path_a: str, path_b: str) -> bool:
    """True when two EXISTING paths name the same underlying filesystem
    entry (same device+inode) via `os.stat` + `os.path.samestat` — an
    identity test, immune to case-folding (this machine's default
    case-insensitive APFS volume — verified live: ``~/.claude/projects``
    and ``~/.claude/PROJECTS`` are the SAME INODE), a hardlink under a
    different name, a `.`/`..` component, a `//` or trailing-slash
    spelling, or a symlink anywhere in either path (`os.stat` follows
    symlinks itself, transparently). A string/prefix comparison can be
    fooled by any of those, because it compares SPELLINGS; this cannot,
    because it never looks at spelling — only at what a path actually
    resolves to on disk.

    False (never raises) on any stat failure — a permission error, or a
    TOCTOU race where a path vanished between an existence check and this
    call — the fail-CLOSED direction for a check that gates real subprocess
    execution: a stat failure here means "not proven to be the same entry
    as a trusted root", never "assume it matches one".
    """
    try:
        return os.path.samestat(os.stat(path_a), os.stat(path_b))
    except OSError:
        return False


def path_resolves_under_root(candidate: str, root: str) -> bool:
    """True when `candidate` (an absolute, already ``~``-expanded path —
    NOT necessarily existing yet, e.g. a file about to be created by the
    command being guarded) IS `root` itself, or resolves, by FILESYSTEM
    IDENTITY, to somewhere underneath it. `root` may carry a trailing
    separator; it is stripped before comparison.

    THE ROOT-CAUSE FIX this function IS (Blocker 1, round 6 review,
    2026-08-28): every round from 3 through 5 patched one more STRING
    spelling that made a prefix/`startswith` comparison miss a real
    containment relationship it should have caught — a trailing separator,
    a `//` or `/./` segment, a bare directory name with no trailing
    separator, and (round 6) a case-VARIANT spelling on this machine's
    default case-insensitive APFS filesystem. Each prior fix closed exactly
    the one spelling it was written against and no other. The reviewer's
    own diagnosis: "str.startswith is being used as a path-containment
    predicate. That will keep producing one more finding per round until
    the comparison is replaced with a filesystem-identity test." This
    function is that replacement: once past the raw ``..``-token rejection
    that runs BEFORE either module ever calls this (a syntactic check on
    the un-expanded token, not this function's concern), it never compares
    strings at all — case, hardlinks, `//`/`/./`/trailing-slash spellings,
    a `/tmp` vs `/private/tmp` symlink alias, and any other spelling a
    future round would otherwise have to chase one at a time are all the
    same non-issue to an `os.stat`-identity test, because none of them
    changes which device+inode a path actually names.

    Algorithm: find `candidate`'s DEEPEST EXISTING ancestor
    (`_deepest_existing_ancestor` — `candidate` itself when it already
    exists; a real directory some levels up otherwise), resolve THAT
    through `os.path.realpath` (closing a symlink planted inside the
    ancestor's own path, e.g. `<trusted-root>/escape -> /elsewhere` — the
    realpath call must run on the anchor, not on `candidate` post-hoc,
    precisely so a symlinked path segment is replaced by its real target
    BEFORE the walk below ever re-derives a literal, unresolved ancestor
    string that would otherwise coincidentally re-spell the trusted root),
    then walk that resolved ancestor's own real parents up to the
    filesystem root, comparing each one's identity against `root`
    (`_same_filesystem_entry`) until a match is found or the walk is
    exhausted. Every step from the resolved anchor upward already exists (a
    path's parent directory always exists when the path itself does), so
    this never stats a path expected not to exist. The NOT-YET-EXISTING
    tail below the anchor, if any, is never inspected — nothing can plant a
    symlink escape in a path segment that does not exist yet, so it is safe
    to trust that tail unconditionally once the anchor itself is proven to
    be `root` or a real descendant of it.

    `root` itself must already exist — every root this is called with in
    practice (`~/.claude`, `/tmp`, and every registered repo root, which
    `load_registry` only accepts after an `os.path.isdir` check) is
    guaranteed to. A `root` that does not exist on this machine can never
    legitimately contain anything real, so this returns False immediately
    rather than attempting a stat that could only fail — the one documented
    exception is `~/.claude/projects/` on a machine that has never run a
    single Claude Code session yet (impossible for the session executing
    this very check, which necessarily already created it), never a gap
    this function silently trades away in the common case.
    """
    root_clean = root.rstrip(os.sep) or os.sep
    if not os.path.exists(root_clean):
        return False
    anchor = os.path.realpath(_deepest_existing_ancestor(candidate))
    current = anchor
    while True:
        if _same_filesystem_entry(current, root_clean):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def _is_overbroad_root(expanded_root: str) -> bool:
    """True when a registered root is broad enough to widen the live
    command-execution sandbox (`validate_agentarch_ledger.run_metric_command`,
    gated by its bounds check) to an operator's entire home directory or
    beyond (Blocker 4, round 3 review, 2026-08-28) — reproduced live:
    registering ``root: '~'``, ``root: '/Users'``, or
    ``root: '/Users/<user>'`` each made ``guard_check('cat ~/.ssh/id_rsa',
    roots)`` return legal, turning a single over-broad or typo'd JSON entry
    into an arbitrary-home-directory reader. Rejects: the filesystem root
    ``/`` itself; a root that equals ``$HOME`` exactly; and a root that is a
    strict ANCESTOR of ``$HOME`` — all three are exactly "does $HOME resolve
    under this candidate root", one `path_resolves_under_root` call (Blocker
    1, round 6 review, 2026-08-28 — this used to be three separate
    string-comparison branches, each its own spelling-bug surface; a
    filesystem-IDENTITY test needs only one branch because it does not care
    how either side is spelled).

    Takes ``os.path.realpath`` of its OWN input (not just relying on the
    caller having already normalized it) — Blocker 4, round 4 review,
    2026-08-28: the caller previously passed an `os.path.abspath`-only
    value, and `abspath` deliberately preserves a POSIX double leading
    slash (``//Users``) rather than collapsing it. `realpath` collapses
    that spelling AND resolves a symlinked root; `path_resolves_under_root`
    closes the rest (case, `/./`, trailing separators, and any future
    spelling) with no further normalization needed here at all. Pure —
    never touches the filesystem beyond a read-only resolve/stat.
    """
    candidate = os.path.realpath(os.path.expanduser(expanded_root))
    return path_resolves_under_root(_HOME, candidate)


def root_is_acceptable(root: str) -> tuple[bool, str]:
    """THE single acceptance test for a candidate command-execution-bounds
    root — shared by BOTH producers of `validate_agentarch_ledger.py`'s
    allowed-roots set: `load_registry` below (JSON-registered repo roots)
    and that module's own `check_ledger`'s CLI ``extra_repo_root`` argument
    (an operator-typed path). Factored out (Finding 1, round-2 security
    review, 2026-08-30) because the two producers had already drifted:
    `load_registry` has long required an accepted root to pass
    `_is_overbroad_root`, be an EXISTING directory, AND contain a `.git`
    entry — i.e. it actually looks like a real repo checkout, never an
    arbitrary broad directory that merely happens to exist — but
    `validate_agentarch_ledger.py`'s CLI-extra-root path only applied the
    first two, never the `.git` check. Reproduced live: passing
    ``extra_repo_root=os.path.expanduser("~/.ssh")`` was accepted as a legal
    bounds-check root, and a `cat .ssh/id_rsa`-shaped command against it ran
    with zero violations — the same unvalidated-producer class Blocker 2
    (round 8 review, 2026-08-30) already closed for the overbroad-root half.
    Both producers now call this ONE function so they cannot silently
    diverge again.

    Takes the RAW root — as stored in the registry JSON, or as typed on the
    CLI: ``~``-relative, a symlink, anything — and normalizes it internally
    (`os.path.expanduser` then `os.path.realpath`) before testing; callers
    never need to pre-normalize. Returns ``(True, normalized_root)`` when
    accepted — the second element is the canonical, expanded/realpath'd
    form the caller should actually register/use, not merely a message — or
    ``(False, reason)`` naming exactly why it was rejected, for the caller
    to fold into its own violation/rejection message. Rejects, in order: an
    overbroad root (`_is_overbroad_root` — the filesystem root ``/``,
    ``$HOME`` itself, or a strict ancestor of ``$HOME``); a root that is not
    an existing directory; and a root that does not contain a `.git` entry.
    Pure — read-only filesystem checks only (stat/realpath), never raises,
    never writes.
    """
    expanded_root = os.path.realpath(os.path.expanduser(root))
    if _is_overbroad_root(expanded_root):
        return False, (
            f"{root!r} is overbroad (it would widen the allowed command-execution "
            "bounds to the operator's home directory or beyond)"
        )
    if not os.path.isdir(expanded_root):
        return False, f"{root!r} is not an existing directory"
    if not os.path.exists(os.path.join(expanded_root, ".git")):
        return False, (
            f"{root!r} does not contain a .git entry (it does not look like a "
            "real repo checkout)"
        )
    return True, expanded_root


def load_registry(
    path: str = DEFAULT_REGISTRY_PATH,
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Returns ``(registry, rejections)``.

    ``registry`` maps slug -> absolute, ~-expanded root path. Empty dict on
    any load problem (missing file, bad JSON, wrong shape) — never raises.

    ``rejections`` is a list of ``(slug, reason)`` pairs, one per registry
    entry `root_is_acceptable` refused (overbroad, nonexistent, or no `.git`
    entry — the same three reasons that function itself documents), in
    registry-file order. THIS is the fix for a real reportability gap
    (Blocker 1, this fix round): before it existed, a rejected registry
    entry was silently dropped from `registry` with no channel to report
    it at all — the only way it ever surfaced was `unknown-repo-slug`, and
    only then if some ledger row happened to reference that exact slug; a
    registry containing an overbroad or non-repo root that NO row
    referenced produced zero violations, contradicting both
    `schedules/prompts/daily_sweep.txt` and `commands/sweep.md`'s own
    documented claim that such an entry "is dropped and reported as its
    own `extra-repo-root-rejected` violation, never silently accepted."
    `rejections` is what makes that claim actually true — see
    `validate_agentarch_ledger.check_ledger`, the caller that turns each
    pair into a real `extra-repo-root-rejected` violation line.

    A root containing whitespace is REJECTED — the slug is not added to
    `registry` — rather than registered: substituting it into a command
    STRING (`resolve_command`) followed by the consumer's own `shlex.split`
    would silently split it into two arguments (Blocker G, 2026-08-28) —
    e.g. `~/Desktop/My App` becomes tokens `.../My` and `App/...`. **It IS
    now also added to `rejections`** (Finding 2, round-2 security review,
    2026-08-30 — reversing the prior version of this docstring, which
    argued this was "a distinct, narrower validation concern...
    deliberately left alone" and kept it OUT of `rejections`): that framing
    left a real, unqualified promise false. Four places in this codebase —
    this docstring's own claim above, `validate_agentarch_ledger.
    check_ledger`'s comment at its point of use, `commands/sweep.md`, and
    `schedules/prompts/daily_sweep.txt` — state, with no qualifier, that a
    rejected root "is dropped and reported as its own
    `extra-repo-root-rejected` violation, never silently accepted." Before
    this fix, a whitespace-containing root was dropped but NEVER reported
    unless some ledger row happened to reference its exact slug (in which
    case it surfaced only as the unrelated `unknown-repo-slug`, never
    naming the real reason) — a whitespace root that no row referenced
    produced zero violations, silently contradicting that "never silently
    accepted" guarantee for this one rejection reason while it already held
    for the other three (overbroad/nonexistent/no-`.git`). This does NOT
    change the "not registered" half of the fix — the slug still never
    enters `registry` (a mis-split command string is exactly what this
    guards against, and remains guarded against) — it only makes the
    rejection ITSELF reportable, the same way the other three already are.
    A row that references the slug still additionally reports
    `unknown-repo-slug` on top of this — the two are not mutually
    exclusive, and both firing for the same row is correct: one names the
    slug is unusable at all (`unknown-repo-slug`), the other names WHY the
    registry entry itself was never usable (`extra-repo-root-rejected`).

    Every OTHER acceptance test (overbroad + isdir + `.git`-presence) is
    `root_is_acceptable` (above) — every value in this registry is fed
    straight into `validate_agentarch_ledger.py`'s bounds check that GATES
    REAL SUBPROCESS EXECUTION, so an over-broad or typo'd entry here
    silently widens the live command sandbox far past "a repo checkout"
    with none of the review friction a CLI-argument root would get
    (Blocker 4, round 3 review, 2026-08-28), and a root that is merely an
    existing directory but not an actual repo checkout gets none of that
    friction either (Finding 1, round-2 security review, 2026-08-30 — this
    module and `validate_agentarch_ledger.py`'s CLI-extra-root path now
    share the exact same test, so they cannot drift apart again). A
    rejection here is now reported via `rejections`, above — never a
    silent over-broad accept.
    """
    rejections: list[tuple[str, str]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}, []
    repos = data.get("repos") if isinstance(data, dict) else None
    if not isinstance(repos, dict):
        return {}, []
    out: dict[str, str] = {}
    for slug, entry in repos.items():
        root = entry.get("root") if isinstance(entry, dict) else None
        if not (isinstance(root, str) and root and isinstance(slug, str)):
            continue
        expanded_root = os.path.realpath(os.path.expanduser(root))
        if any(ch.isspace() for ch in expanded_root):
            # Quote BOTH the raw, as-configured `root` and the realpath'd
            # `expanded_root` the whitespace check actually ran on (NIT,
            # round-3 security review, 2026-08-30) — for a symlinked root
            # these can differ (a clean-looking configured path whose real
            # target contains whitespace, or vice versa); quoting only
            # `root` produced a misleading message that named a path with
            # no whitespace even though the check found it in the
            # realpath'd form.
            rejections.append(
                (
                    slug,
                    f"{root!r} (resolves to {expanded_root!r}) contains whitespace — "
                    "would mis-tokenize when substituted into a command string",
                )
            )
            continue
        accepted, reason_or_root = root_is_acceptable(root)
        if not accepted:
            rejections.append((slug, reason_or_root))
            continue
        out[slug] = expanded_root
    return out, rejections


def resolve_command(command: str, registry: dict[str, str]) -> tuple[str | None, list[str]]:
    """Substitutes every ``${REPO:slug}`` token in `command` with the
    registry's root for that slug.

    Returns ``(resolved_command, [])`` when every referenced slug is known,
    or ``(None, unknown_slugs)`` when at least one is not — a command is
    never PARTIALLY resolved; either every placeholder in it resolves, or
    none of it is returned as runnable. A command with no placeholder at
    all resolves to itself unchanged. Pure; never raises.
    """
    unknown = sorted({slug for slug in _PLACEHOLDER_RE.findall(command) if slug not in registry})
    if unknown:
        return None, unknown

    def _sub(match: "re.Match[str]") -> str:
        return registry[match.group(1)]

    return _PLACEHOLDER_RE.sub(_sub, command), []


# --------------------------------------------------------------------------
# per-form argument grammar (root-cause fix, round-4 security review,
# 2026-08-30, unified onto a single left-to-right consuming scanner,
# round-5 security review, 2026-08-30) — see this module's own docstring,
# "THE PER-FORM ARGUMENT-GRAMMAR TABLE" and "THE SINGLE LEFT-TO-RIGHT
# CONSUMING SCANNER", for the full rationale. THE canonical grammar both
# this module's `find_hardcoded_paths` (via `classify_command`/
# `classify_tokens`) and `validate_agentarch_ledger.guard_check` (via
# `_match_form`, a thin wrapper over `classify_command`, and
# `_paths_in_bounds`, which consumes `classify_tokens` directly) consult —
# no other module defines a competing notion of a form's flags, arity, or
# positional roles.
# --------------------------------------------------------------------------

_CHURN_SCRIPT = os.path.join(_HOME, ".claude", "hooks", "churn_report.py")


@dataclass(frozen=True)
class FlagSpec:
    """One flag's shape within one command FORM's grammar.

    ``arity`` is 0 (boolean — never consumes a following token, e.g.
    grep's ``-c``), 1 (consumes exactly one following VALUE token that is
    never itself a path candidate by position — grep/rg's ``-e PATTERN``,
    rg's ``-g GLOB``/``-r REPLACEMENT``/``-E ENCODING``, git's
    ``-n COUNT``), or 2 (consumes two following tokens — jq's
    ``--arg``/``--argjson``/``--slurpfile``/``--rawfile``, each
    ``NAME <second>``).

    ``second_token_is_path`` is meaningful ONLY when ``arity == 2``: does
    the SECOND consumed token name a real filesystem target
    `validate_agentarch_ledger.run_metric_command` actually reads (jq's
    ``--slurpfile``/``--rawfile`` FILE half — ``True``, stays fully
    bounds-checked, never exempted), or is it itself a value/JSON literal
    jq never reads from disk (jq's ``--arg``/``--argjson`` VALUE half —
    ``False``, exempt from bounds-checking exactly like the NAME half
    ahead of it)? The FIRST consumed token (the NAME half) of EVERY
    arity-2 flag is always exempt regardless of this field — a jq variable
    NAME is never itself a path in either case.
    """

    arity: int
    second_token_is_path: bool = False


@dataclass(frozen=True)
class FormGrammar:
    """One recognized command form's complete argument grammar.

    ``flags`` maps an exact flag token (``-c``, ``--arg``, …) to its
    `FlagSpec`. ``prefix_flags`` are ``--name=value``-shaped flags whose
    value is embedded in the SAME token (e.g. grep's ``--include=GLOB``) —
    unaffected by arity (the whole token is simply a legal, non-path
    `-`-prefixed token; nothing is ever bounds-checked out of it, matching
    this grammar's pre-existing, unchanged treatment of every other
    `-`-prefixed token).

    ``positional_role`` names the ONE positional-argument role this form's
    real-world semantics assign a non-flag token, if any: ``"grep_pattern"``
    (grep/rg's search PATTERN — satisfied EITHER positionally or via an
    ``-e`` flag, never both) or ``"jq_filter"`` (jq's FILTER expression —
    ALWAYS positional, unaffected by which value-consuming flags precede
    it, since ``-f``/``--from-file``, the one real jq flag that WOULD
    change this, is never in this grammar's allowed flag set). ``None``
    for every other form (`wc`, `ls`, `cat`, `git`, `churn_report`) — none
    of them takes a "pattern"/"filter" argument at all, so EVERY non-flag
    token for them is unambiguously a path operand; this is the FAIL-CLOSED
    default the task's own root-cause diagnosis requires, achieved simply
    by never registering a role for a form that has none.

    ``has_end_of_options_marker`` is ``True`` only for `git` (M1, round-4
    security review, 2026-08-30): a literal ``--`` token, once present,
    ends flag-parsing for every SUBSEQUENT token in that command — even one
    that looks like a flag (``git log -- -n secrets.txt``'s ``-n`` is a
    real pathspec there, not the ``-n COUNT`` flag) — because git itself
    defines ``--`` that way. No other form in this grammar recognizes an
    end-of-options marker at all.
    """

    flags: dict[str, FlagSpec]
    prefix_flags: tuple[str, ...] = ()
    positional_role: str | None = None
    has_end_of_options_marker: bool = False


FORM_GRAMMARS: dict[str, FormGrammar] = {
    # Real GNU/BSD grep — verified live against this machine's
    # `/usr/bin/grep` (BSD grep 2.6.0-FreeBSD, GNU-compatible): grep has NO
    # `-g` flag at all (confirmed: `grep -g foo x` → "invalid option -- g",
    # exit 2), and its `-r`/`-E` are BOOLEAN (recursive / extended-regexp),
    # unlike rg's own same-lettered, value-consuming flags below (B2).
    "grep": FormGrammar(
        flags={
            "-c": FlagSpec(arity=0),
            "-n": FlagSpec(arity=0),
            "-l": FlagSpec(arity=0),
            "-r": FlagSpec(arity=0),
            "-i": FlagSpec(arity=0),
            "-E": FlagSpec(arity=0),
            "-F": FlagSpec(arity=0),
            "-h": FlagSpec(arity=0),
            "-o": FlagSpec(arity=0),
            "--count": FlagSpec(arity=0),
            "-e": FlagSpec(arity=1),
        },
        prefix_flags=("--include=",),
        positional_role="grep_pattern",
    ),
    # Real ripgrep — arities sourced from ripgrep's own published
    # documentation (`rg --help` / `man rg`, ripgrep 14.1.1), NOT
    # live-execution-verified in this environment (corrected, round-5
    # security review, 2026-08-30 — the round-4 comment this replaces
    # overclaimed "verified live against this machine's `rg` 14.1.1"; in
    # fact `shutil.which("rg")` returns `None` here, since this machine's
    # interactive shell resolves a typed `rg` through a Claude Code wrapper
    # shell function rather than a real ripgrep binary on `subprocess.run`'s
    # bare PATH — no `rg`-headed ledger row is actually executable in this
    # environment at all, so this claim's own evidentiary basis could not be
    # re-checked here; see this module's own docstring, "THE PER-FORM
    # ARGUMENT-GRAMMAR TABLE", for the full correction). `-g GLOB`,
    # `-r REPLACEMENT`, `-E ENCODING` are all 1-arity VALUE-consuming flags
    # here, unlike grep's own same-lettered boolean/nonexistent flags above
    # (B2) — merging the two forms under one flag table (the pre-fix design)
    # was itself the root cause of the arity confusion four-plus rounds of
    # review kept re-discovering one letter at a time.
    "rg": FormGrammar(
        flags={
            "-c": FlagSpec(arity=0),
            "-n": FlagSpec(arity=0),
            "-l": FlagSpec(arity=0),
            "-i": FlagSpec(arity=0),
            "-F": FlagSpec(arity=0),
            "-h": FlagSpec(arity=0),
            "-o": FlagSpec(arity=0),
            "--count": FlagSpec(arity=0),
            "-e": FlagSpec(arity=1),
            "-g": FlagSpec(arity=1),
            "-r": FlagSpec(arity=1),
            "-E": FlagSpec(arity=1),
        },
        prefix_flags=("--glob=",),
        positional_role="grep_pattern",
    ),
    "wc": FormGrammar(
        flags={"-l": FlagSpec(arity=0), "-c": FlagSpec(arity=0), "-w": FlagSpec(arity=0)},
    ),
    "ls": FormGrammar(
        flags={
            "-l": FlagSpec(arity=0),
            "-a": FlagSpec(arity=0),
            "-1": FlagSpec(arity=0),
            "-t": FlagSpec(arity=0),
            "-S": FlagSpec(arity=0),
        },
    ),
    "cat": FormGrammar(flags={}),
    # jq's `--arg NAME VALUE`/`--argjson NAME VALUE` (B3): the VALUE half is
    # a literal string/JSON value jq binds to `$NAME` and NEVER reads from
    # disk — `second_token_is_path=False`, exempt from bounds-checking
    # exactly like the NAME half ahead of it. `--slurpfile NAME FILE`/
    # `--rawfile NAME FILE`: the FILE half IS a real filesystem target jq
    # actually opens and reads — `second_token_is_path=True`, stays fully
    # bounds-checked, never exempted (pre-existing, correct design, kept
    # unchanged by B3 — B3 only fixes `--arg`/`--argjson`, which this
    # grammar previously modeled with NO second-token concept at all).
    "jq": FormGrammar(
        flags={
            "-r": FlagSpec(arity=0),
            "-c": FlagSpec(arity=0),
            "-s": FlagSpec(arity=0),
            "-e": FlagSpec(arity=0),
            "--arg": FlagSpec(arity=2, second_token_is_path=False),
            "--argjson": FlagSpec(arity=2, second_token_is_path=False),
            "--slurpfile": FlagSpec(arity=2, second_token_is_path=True),
            "--rawfile": FlagSpec(arity=2, second_token_is_path=True),
        },
        positional_role="jq_filter",
    ),
    "git": FormGrammar(
        flags={
            "-n": FlagSpec(arity=1),
            "--oneline": FlagSpec(arity=0),
            "--stat": FlagSpec(arity=0),
            "--name-only": FlagSpec(arity=0),
        },
        # No entry here for the literal `--` end-of-options marker itself
        # (F5, round-7 review, 2026-08-30 — a prior entry,
        # `"--": FlagSpec(arity=0)`, was removed as dead/misleading): both
        # consumers of this table resolve a `--` token to `BOUNDARY`
        # (`classify_tokens`, via `end_of_options_index`) or `continue`
        # past it (`validate_agentarch_ledger.guard_check`'s own
        # `i >= boundary` skip) BEFORE a flag-table lookup on it ever runs,
        # so an entry here is unreachable by construction, not merely
        # unused today. Listing `--` as an ordinary arity-0 boolean flag
        # also reads backwards — it is the one token this grammar treats as
        # structurally special (`has_end_of_options_marker` below), not "a
        # normal flag that happens to be legal."
        prefix_flags=("--since=", "--until=", "--format=", "--pretty="),
        has_end_of_options_marker=True,
    ),
    "churn_report": FormGrammar(
        flags={"--days": FlagSpec(arity=1), "--json": FlagSpec(arity=0)},
    ),
}


def classify_command(tokens: list[str]) -> tuple[str | None, list[str]]:
    """(form_name, rest) for an already-`shlex.split` command's `tokens` —
    `rest` is `tokens` with the command HEAD stripped (one token for most
    forms; two for `git log`/`git show`, and for `python3
    ~/.claude/hooks/churn_report.py`). `form_name` is `None`, `rest` `[]`
    when no recognized form matches at all — the caller reports that as
    "unrecognized command form".

    THE single form-matching authority (root-cause fix, round-4 security
    review, 2026-08-30): both `validate_agentarch_ledger.guard_check` (via
    its own `_match_form`, a thin wrapper over this function) and this
    module's own `find_hardcoded_paths` consult this ONE function —
    replacing what used to be two independently drifting head-token
    dispatchers. Unaffected by round-5's `classify_tokens` rewrite (this
    function was never one of the three independently re-walking functions
    that round replaced — see `classify_tokens`' own docstring). Pure.
    """
    if not tokens:
        return None, []
    head = tokens[0]
    if head == "grep":
        return "grep", tokens[1:]
    if head == "rg":
        return "rg", tokens[1:]
    if head == "wc":
        return "wc", tokens[1:]
    if head == "ls":
        return "ls", tokens[1:]
    if head == "cat":
        return "cat", tokens[1:]
    if head == "jq":
        return "jq", tokens[1:]
    if head == "git" and len(tokens) > 1 and tokens[1] in ("log", "show"):
        return "git", tokens[2:]
    if head in ("python3", "python") and len(tokens) > 1:
        script = os.path.expanduser(tokens[1])
        if os.path.normpath(script) == os.path.normpath(_CHURN_SCRIPT):
            return "churn_report", tokens[2:]
    return None, []


def end_of_options_index(form: str | None, tokens: list[str]) -> int | None:
    """Index of the literal ``--`` end-of-options marker within `tokens` (a
    form's post-head "rest" slice), for a form whose grammar recognizes one
    (only `git`, currently) — or ``None`` when the form has no such marker,
    or `tokens` doesn't contain one. See `FormGrammar.has_end_of_options_marker`'s
    own docstring for the M1 rationale. Pure.
    """
    grammar = FORM_GRAMMARS.get(form or "")
    if grammar is None or not grammar.has_end_of_options_marker:
        return None
    try:
        return tokens.index("--")
    except ValueError:
        return None


def _recognize_flag(grammar: FormGrammar, tok: str) -> FlagSpec | Literal["prefix", "cluster"] | None:
    """THE single flag-recognition predicate BOTH `flag_is_allowed` and
    `classify_tokens` consult (F4, round-7 security review, 2026-08-30) —
    before this existed, the two independently re-implemented the exact-
    match / ``--prefix=value`` / arity-0 CLUSTER recognition rules inline,
    each its own copy — precisely the "two independent walks that must
    agree on what a token *is*" problem this module's round-5 rewrite (see
    the module docstring, "THE SINGLE LEFT-TO-RIGHT CONSUMING SCANNER")
    exists to eliminate, reintroduced here at smaller scale. One shared
    implementation now backs both.

    Returns, in priority order: the token's own `FlagSpec` for an EXACT
    match against ``grammar.flags`` (so a caller that needs the flag's
    arity — `classify_tokens`, to know how many value tokens to consume —
    gets it directly, with no second lookup); the literal string
    ``"prefix"`` for a recognized ``--name=value``-shaped flag
    (``grammar.prefix_flags``) — never arity-bearing, since its value is
    embedded in the same token; the literal string ``"cluster"`` for a
    combined single-dash CLUSTER (e.g. ``grep -rl`` == ``-r`` + ``-l``)
    whose EVERY constituent letter maps to an individually-allowed,
    ARITY-0 flag for this form (a value-consuming flag is NEVER
    cluster-eligible, even alongside boolean flags — combining it into a
    cluster would make its own value's position ambiguous, which this
    grammar never allows regardless of which specific letter is involved);
    or ``None`` when `tok` matches none of the three shapes. `grammar` is
    always a real `FormGrammar` here — both callers already resolve
    `form=None`/an unrecognized form to "illegal"/"no grammar" before ever
    reaching this function, so it never needs to handle a missing grammar
    itself. Pure.
    """
    if tok in grammar.flags:
        return grammar.flags[tok]
    if any(tok.startswith(p) for p in grammar.prefix_flags):
        return "prefix"
    if tok.startswith("-") and not tok.startswith("--") and len(tok) > 2 and all(
        f"-{c}" in grammar.flags and grammar.flags[f"-{c}"].arity == 0 for c in tok[1:]
    ):
        return "cluster"
    return None


def flag_is_allowed(form: str | None, tok: str) -> bool:
    """True when `-`-prefixed token `tok` is a legal flag for `form`, per
    the shared grammar table — an exact flag match, a recognized
    ``--prefix=value`` flag, or a combined single-dash CLUSTER (e.g.
    ``grep -rl`` == ``-r`` + ``-l``) whose EVERY constituent letter maps to
    an individually-allowed, ARITY-0 flag for this form. A value-consuming
    flag (arity 1 or 2) is NEVER cluster-eligible, even alongside boolean
    flags — combining it into a cluster would make its own value's
    position ambiguous, which this grammar never allows regardless of
    which specific letter is involved. `form=None` (no recognized command
    form at all) is always illegal. Pure. Delegates its actual recognition
    work to `_recognize_flag` (F4, round-7 security review, 2026-08-30) —
    see that function's own docstring for the shared rationale.
    """
    grammar = FORM_GRAMMARS.get(form or "")
    if grammar is None:
        return False
    return _recognize_flag(grammar, tok) is not None


@dataclass(frozen=True)
class TokenRole:
    """One token's structural role, as emitted by `classify_tokens`'s single
    left-to-right, exactly-once CONSUMING scan — see this module's own
    docstring, "THE SINGLE LEFT-TO-RIGHT CONSUMING SCANNER", for the full
    root-cause rationale (round-5 security review, 2026-08-30).

    ``kind`` is one of:
      "FLAG" — a `-`-prefixed token consumed AS a flag (an exact match, a
        recognized ``--prefix=value`` form, a legal boolean CLUSTER, or an
        UNRECOGNIZED flag-shaped token — `flag_recognized` distinguishes
        the last case; `guard_check`'s own separate, unchanged,
        per-token-text `flag_is_allowed` lookup is still what REFUSES to run
        a command carrying one — this field is purely descriptive here).
      "FLAG_VALUE" — the token consumed as a value-consuming flag's own
        value (grep/rg's `-e` PATTERN, rg's `-g`/`-r`/`-E`, git's `-n`
        COUNT, jq's `--arg`/`--argjson`/`--slurpfile`/`--rawfile` NAME
        and/or VALUE/FILE half) — `is_path_designated` says which.
      "POSITIONAL_ROLE" — the ONE token, if any, this form's grammar
        assigns its positional pattern/filter role to (grep/rg's PATTERN
        when no `-e` consumed one, jq's FILTER) — decided only AFTER the
        full left-to-right pass, over tokens the pass left otherwise
        unconsumed.
      "BOUNDARY" — git's own literal `--` end-of-options marker token
        itself (never itself a pathspec — it names no file).
      "POST_BOUNDARY_PATHSPEC" — any token strictly after a `BOUNDARY`
        token — a literal git pathspec, NEVER flag-parsed even when it
        looks flag-shaped.
      "PATH_CANDIDATE" — the default, fail-closed bucket: any token this
        pass did not consume as a flag/flag-value and did not, after the
        full pass, assign the form's one positional role to.

    ``flag_recognized`` is meaningful only for ``kind == "FLAG"``: True when
    the token is a legal flag spelling for this form (exact/prefix/cluster
    match against the shared grammar table), False for a `-`-prefixed token
    that matched none of those shapes.

    ``embedded_value`` is meaningful only for ``kind == "FLAG"``: the
    substring after the token's own first ``=`` when present (e.g.
    ``--include=*.py`` -> ``*.py``), else ``None``. Exists purely so
    `find_hardcoded_paths` can additionally scan a flag's own embedded value
    for a hardcoded path without a second independent walk — `guard_check`'s
    execution-gating bounds check never consults this field: none of this
    grammar's recognized ``--prefix=value`` flags (grep/rg's
    `--include=`/`--glob=`, git's `--since=`/`--until=`/`--format=`/
    `--pretty=`) is ever itself a filesystem target `run_metric_command`
    reads.

    ``is_path_designated`` is meaningful only for ``kind == "FLAG_VALUE"``:
    True for the ONE case this grammar defines where a flag's consumed
    value token IS a real filesystem target the command actually opens —
    jq's `--slurpfile`/`--rawfile` FILE half (B3) — False for every other
    flag value (a NAME, a COUNT, a PATTERN, a JSON VALUE), which is never
    itself read from disk BY DESIGN, though its own SHAPE can still route it
    into a full bounds check anyway (M2 below).
    """

    kind: str
    flag_recognized: bool | None = None
    embedded_value: str | None = None
    is_path_designated: bool = False


def flag_value_shape_needs_bounds_check(tok: str) -> bool:
    """M2's shape gate (round-4 security review, 2026-08-30; `..` clause
    added round-5, 2026-08-30) for a `FLAG_VALUE` token whose own FlagSpec
    does NOT already designate it as always-a-path (`is_path_designated`
    False — grep/rg's `-e` PATTERN, git's `-n` COUNT, jq's `--arg`/
    `--argjson` NAME and VALUE halves): True when the token's own SHAPE
    says it might really be a real filesystem path anyway — absolute
    (`/`-leading), `~`-prefixed, or carrying a literal `..` path component
    — because no legitimate value of this kind is EVER spelled that way.

    THE `..` clause is round-5's actual security fix: pre-fix, this gate
    only checked the leading character (`/` or `~`), so a RELATIVE
    traversal token in flag-value position — e.g. the second `-e` in
    `grep -c -e -e ../../../etc/hosts` — passed this gate (no leading
    `/`/`~`) and was skipped entirely, never reaching the traversal check
    at all. Folding the `..` test into THIS gate, so a caller's traversal
    check runs unconditionally on every token this gate does not exempt,
    closes that ordering bug by construction rather than by re-sequencing
    two still-independent checks. Pure.
    """
    if tok.startswith("/") or tok.startswith("~"):
        return True
    return ".." in tok.split("/")


def positional_role_shape_needs_bounds_check(tok: str) -> bool:
    """The equivalent shape gate for the ONE `POSITIONAL_ROLE` token a
    form's grammar exempts by role (grep/rg's PATTERN, jq's FILTER), and
    also `_paths_in_bounds`' own churn_report blanket bare-word exemption:
    True when the token itself already "looks like a path" — a BROADER
    test than `flag_value_shape_needs_bounds_check`'s leading-character-only
    check, preserved from this exemption's own pre-existing, narrower
    scope (any `/` ANYWHERE in the token, not just a leading one, in
    addition to a leading `/`/`~`, or a `..` component). A quoted,
    multi-word PROSE pattern (e.g. `"some search text"`) trips none of
    these (no slash, no `..`) and stays exempt from `_paths_in_bounds`'
    EXECUTION-gating check, as intended — `find_hardcoded_paths`' own,
    separate, DIFFERENT policy for the positional-role case is documented
    at its own point of use (a genuinely prose, whitespace-containing
    pattern is never itself "a path" there either, but for a different,
    static-reporting reason, not this shape gate). Pure.
    """
    if tok.startswith("/") or tok.startswith("~") or "/" in tok:
        return True
    return ".." in tok.split("/")


def _embedded_after_equals(tok: str) -> str | None:
    """The substring after `tok`'s own first ``=``, or ``None`` when it has
    none — e.g. ``--include=*.py`` -> ``*.py``. Pure.
    """
    if "=" not in tok:
        return None
    return tok.split("=", 1)[1]


def classify_tokens(form: str | None, tokens: list[str]) -> list[TokenRole]:
    """THE single left-to-right, exactly-once, CONSUMING scan over a form's
    post-head token slice `tokens` — see this module's own docstring, "THE
    SINGLE LEFT-TO-RIGHT CONSUMING SCANNER", for the full root-cause
    rationale (round-5 security review, 2026-08-30). Returns one
    `TokenRole` per token in `tokens`, in order — every downstream consumer
    (`validate_agentarch_ledger._paths_in_bounds`, this module's own
    `find_hardcoded_paths`) reads this as a LOOKUP, never re-derives any
    part of it.

    ``form=None`` (no recognized command form at all) is FAIL-CLOSED: every
    token, dash-prefixed or not, is classified `PATH_CANDIDATE` — there is
    no grammar to recognize a flag against, so nothing is ever exempted.
    (In practice `guard_check` never even reaches `_paths_in_bounds`, let
    alone this function, for a `form=None` command — it refuses at
    "unrecognized command form" first. **`find_hardcoded_paths` does NOT
    exercise this branch either (corrected, F6, round-7 review,
    2026-08-30):** `classify_command` returns `(None, [])` for an
    unrecognized form — an EMPTY `rest` slice, per its own docstring — so
    `find_hardcoded_paths` always calls `classify_tokens(None, [])`, which
    trivially returns `[]` because there are no tokens to classify, never
    actually running this function's own `form=None` per-token loop body on
    a real token. The real no-form fallback logic for an unrecognized
    command's tokens lives entirely in `find_hardcoded_paths` ITSELF, in its
    own independent `role is None` branches at its point of use — not here.)

    THE CONSUMPTION ITSELF (closes defect (b), the scanning bug): walking
    strictly left-to-right with a single cursor, a value-consuming flag's
    value token(s) are marked `FLAG_VALUE` and the cursor advances PAST
    them immediately, in the SAME step that recognizes the flag — so a
    token already consumed this way can never be re-examined as a flag, a
    positional-role candidate, or anything else later in the same pass,
    regardless of what it is textually spelled like. This is what makes
    `grep -c -e -e ../../../etc/hosts` classify correctly: the FIRST `-e`
    is `FLAG`; the SECOND `-e` (textually identical, but really the first
    `-e`'s OWN value) is consumed as its `FLAG_VALUE` and the cursor moves
    on; the traversal token is reached fresh, was never claimed by
    anything, and becomes a real `PATH_CANDIDATE` token — no longer wrongly
    re-marked as "a second `-e` flag's own value" the way an
    occurrence-independent, non-consuming scan (the round-4 design this
    replaces) did.

    THE `..`/SHAPE GATE (closes defect (a), the ordering bug): every
    `FLAG_VALUE` whose `is_path_designated` is False, and the one
    `POSITIONAL_ROLE` token a form's grammar may assign, are exempt from a
    caller's bounds check ONLY when `flag_value_shape_needs_bounds_check`/
    `positional_role_shape_needs_bounds_check` (above) say the token does
    NOT need one — there is no separate, later-stage traversal check a
    token can route around merely by having been classified as a value or a
    positional role first; a caller applies these gates directly against
    this function's own `kind` output, so the classification and the shape
    policy are never two independently-drifting steps again.

    Everything else — `POST_BOUNDARY_PATHSPEC`, a `FLAG_VALUE` with
    `is_path_designated=True` (jq's `--slurpfile`/`--rawfile` FILE half),
    and the default `PATH_CANDIDATE` bucket — is ALWAYS a caller's full
    bounds-check target, with no shape gate or role-based exemption at all.

    `"grep_pattern"` (B1, round-4 security review, 2026-08-30 — THE fix for
    the reviewer's own confirmed working exfiltration repro, preserved
    unchanged by this round's rewrite): when an `-e` flag is CONSUMED
    anywhere in this pass (not merely spelled the same way — see the
    consumption note above), real grep/rg semantics define NO positional
    pattern argument at all — every remaining non-flag token is a FILE.
    Only when no `-e` was consumed does the ordinary "first non-flag,
    non-flag-value token, but only when at least one FURTHER non-flag
    token also follows it" rule apply (the "sole argument" shape — e.g.
    `rg -l <path>`, no separate file operand — is a real search target,
    not prose, and is never exempted).

    `"jq_filter"`: jq's own filter expression is ALWAYS positional
    regardless of which value-consuming flags precede it (jq's real CLI
    syntax is `jq [OPTIONS] FILTER [FILES...]` — no option this grammar
    allows, including `--arg`/`--argjson`/`--slurpfile`/`--rawfile`,
    changes that) — the first token this pass left as `PATH_CANDIDATE`,
    unconditionally (no `-e`-style "no pattern at all" case exists for jq
    in this grammar, since `-f`/`--from-file`, the one real jq flag that
    WOULD change this, is never allowed).

    **M3, round-4 security review, 2026-08-30 — DELIBERATE, BOUNDED,
    ACCEPTED RESIDUAL, unaffected by this round's rewrite:** exempting jq's
    filter from path-bounds-checking necessarily re-opens jq's OWN filter
    language as an evaluation surface — e.g. `jq -n env` or `jq -n '$ENV'`
    reads this PROCESS's environment variables and prints them, with no
    file ever named or opened. This is NOT a filesystem-bounds bypass
    (nothing here lets a filter read a file outside the allowed roots — the
    file operand, if any, is still fully bounds-checked normally) — it is a
    narrower, DIFFERENT risk: jq's filter language is itself a small
    expression-evaluation surface, and exempting it from bounds-checking is
    exactly what a "PATTERN/FILTER is prose, not a path" design requires
    (the same trade-off `guard_check`'s forbidden-substring ban already
    accepts for grep/rg's own PATTERN). Treat this as a known, bounded
    residual to revisit with real usage data, never as "zero risk."

    Pure.
    """
    n = len(tokens)
    grammar = FORM_GRAMMARS.get(form or "")
    boundary = end_of_options_index(form, tokens)
    roles: list[TokenRole] = [TokenRole(kind="PATH_CANDIDATE") for _ in range(n)]
    positional_candidates: list[int] = []
    i = 0
    while i < n:
        if boundary is not None and i == boundary:
            roles[i] = TokenRole(kind="BOUNDARY")
            i += 1
            continue
        if boundary is not None and i > boundary:
            roles[i] = TokenRole(kind="POST_BOUNDARY_PATHSPEC")
            i += 1
            continue
        tok = tokens[i]
        if grammar is not None and tok.startswith("-"):
            # Recognition itself is `_recognize_flag` (F4, round-7 security
            # review, 2026-08-30) — the exact-match / `--prefix=value` /
            # arity-0 CLUSTER shapes are defined there ONCE, shared with
            # `flag_is_allowed`, rather than re-derived here independently.
            recognition = _recognize_flag(grammar, tok)
            if isinstance(recognition, FlagSpec):
                spec = recognition
                roles[i] = TokenRole(
                    kind="FLAG", flag_recognized=True, embedded_value=_embedded_after_equals(tok)
                )
                i += 1
                if spec.arity >= 1 and i < n and (boundary is None or i < boundary):
                    roles[i] = TokenRole(kind="FLAG_VALUE", is_path_designated=False)
                    i += 1
                if spec.arity == 2 and i < n and (boundary is None or i < boundary):
                    roles[i] = TokenRole(kind="FLAG_VALUE", is_path_designated=spec.second_token_is_path)
                    i += 1
                continue
            if recognition in ("prefix", "cluster"):
                roles[i] = TokenRole(
                    kind="FLAG", flag_recognized=True, embedded_value=_embedded_after_equals(tok)
                )
                i += 1
                continue
            # Unrecognized flag-shaped token: never itself path-checked (no
            # legitimate flag spelling names a real filesystem target by
            # being ILLEGAL) — `guard_check`'s own, separate, unchanged
            # `flag_is_allowed` lookup is what refuses to RUN a command
            # carrying one; this classification stays purely descriptive.
            roles[i] = TokenRole(
                kind="FLAG", flag_recognized=False, embedded_value=_embedded_after_equals(tok)
            )
            i += 1
            continue
        roles[i] = TokenRole(kind="PATH_CANDIDATE")
        positional_candidates.append(i)
        i += 1

    role_name = grammar.positional_role if grammar is not None else None
    if role_name == "grep_pattern":
        e_flag_consumed = any(
            r.kind == "FLAG" and r.flag_recognized and tokens[idx] == "-e" for idx, r in enumerate(roles)
        )
        if not e_flag_consumed and len(positional_candidates) >= 2:
            roles[positional_candidates[0]] = TokenRole(kind="POSITIONAL_ROLE")
    elif role_name == "jq_filter":
        if positional_candidates:
            roles[positional_candidates[0]] = TokenRole(kind="POSITIONAL_ROLE")

    return roles


# --------------------------------------------------------------------------
# check 1: hardcoded-repo-path
# --------------------------------------------------------------------------

# A neutral, absolute sentinel a ``${REPO:<slug>}`` placeholder is
# substituted for (Finding 6, round 8 review, 2026-08-30) — see
# `find_hardcoded_paths`'s own comment at its point of use for the full
# rationale. Deliberately a single, unmistakable path SEGMENT (never a real
# directory name) so a normalized result that no longer starts with it can
# only mean the token's own literal `..`/`.` shape walked OUT of wherever
# the real slug eventually resolves to — never a coincidental collision.
_PLACEHOLDER_SENTINEL = "/__REPO_PLACEHOLDER_SENTINEL__"


def _is_always_safe(expanded: str) -> bool:
    """True when an already-expanded, normalized absolute path is
    automatically safe regardless of the repo registry's contents.
    ``~/.claude/projects/`` is checked FIRST and, if matched, is never
    safe — see ``_NEVER_SAFE_ROOTS``'s docstring (Blocker E).

    Uses `path_resolves_under_root` — a filesystem-IDENTITY test, not a
    string comparison (Blocker 1, round 6 review, 2026-08-28) — for both
    checks, so a case-variant spelling (this machine's default
    case-insensitive APFS volume treats ``~/.claude/projects`` and
    ``~/.claude/PROJECTS`` as the SAME directory), a hardlink, or any
    future spelling trick is closed by construction, the same way it is
    for `validate_agentarch_ledger._paths_in_bounds`'s equivalent checks
    (both modules call this one shared function; see its own docstring for
    the full rationale — this is no longer two implementations to keep in
    sync, it is one). Pure (this function itself performs no mutation;
    `path_resolves_under_root` only reads/stats the filesystem).
    """
    if any(path_resolves_under_root(expanded, root) for root in _NEVER_SAFE_ROOTS):
        return False
    return any(path_resolves_under_root(expanded, root) for root in _ALWAYS_SAFE_ROOTS)


def find_hardcoded_paths(command: str) -> list[str]:
    """Every token in `command` that is a bare absolute path outside the
    always-safe roots (~/.claude/, /tmp/ — but NOT ~/.claude/projects/,
    see ``_NEVER_SAFE_ROOTS``) and not expressed as a ``${REPO:slug}``
    placeholder. Empty list when the command is clean or unparseable (an
    unparseable command is a different check's problem —
    `validate_agentarch_ledger.py`'s guard-legality — not this module's).

    UNIFIED ONTO `classify_tokens` (M-1, round-5 security review,
    2026-08-30): this function used to consult ONLY the positional-role
    piece (`_pattern_arg_index`, removed this round) of the shared grammar,
    applying its exemption BEFORE any flag validation, while
    `validate_agentarch_ledger.guard_check` consulted the full
    flag/value/positional classification and applied exemptions AFTER flag
    validation — the two functions disagreed on what a given token IS. This
    is now closed by construction: both consult `classify_command`/
    `classify_tokens`, the SAME single left-to-right pass, for every
    command. The two functions still apply DIFFERENT POLICIES on top of
    that shared classification, deliberately — this function's job is a
    STATIC, always-on report (it runs regardless of guard-legality, even on
    a row that would refuse to execute for an unrelated reason), while
    `guard_check`'s `_paths_in_bounds` gates real execution — see each
    token-kind branch below for the exact policy and why it differs from
    `_paths_in_bounds`' where it does.

    Reproduced, pre-fix (M-1): `find_hardcoded_paths('grep -ec
    /Users/x/Desktop/OtherApp/secret ~/.claude/CLAUDE.md')` returned `[]` —
    `-ec` (real grep for `-e` with the pattern's first character folded in,
    i.e. NOT a recognized `-e` flag occurrence by this grammar) was not
    recognized as "an `-e` flag is present", so the old, independent
    positional-role scan still treated the FIRST non-flag token as an
    exempt "pattern" and never scanned it — hiding the smuggled hardcoded
    path entirely. Fixed here in two ways at once: (1) a `POSITIONAL_ROLE`
    token that is itself bare (no whitespace) AND absolute/`~`-prefixed is
    no longer unconditionally exempt (see the `POSITIONAL_ROLE` branch
    below) — no legitimate grep/rg PATTERN is ever spelled that way, so
    this alone would have caught the exact repro even without fix (2); and
    (2) `flag_recognized` is checked (not merely "is `-e` the literal
    string this token happens to display"), so a real ambiguity in how a
    given form spells its flags cannot silently masquerade as "no `-e` was
    used" the way a purely textual `"-e" in tokens` check could.

    Escapes closed by earlier rounds (Blocker F, 2026-08-28; Finding 6,
    round 8 review, 2026-08-30), unaffected by this round's rewrite:
      1. `..` traversal (e.g. `~/.claude/../Desktop/OtherApp/...`) — closed by
         `os.path.normpath` before the safe-root comparison, so a traversal
         out of an always-safe root can no longer masquerade as staying
         inside it.
      2. A `-`-prefixed FLAG token with an embedded path via `=` (e.g.
         `--file=/Users/x/Desktop/OtherApp/...`) — every `FLAG`-kind token's
         substring after its first `=` (`TokenRole.embedded_value`) is
         checked as a candidate path, recognized or not.
      3. A quoted compound command (e.g. `bash -c "grep -c x
         /Users/x/Desktop/OtherApp/..."`) arrives as ONE token containing
         whitespace that `shlex.split` cannot see inside — such a token is
         recursively re-scanned as its own command string.
      4. A token CONTAINING a ``${REPO:<slug>}`` placeholder is checked for
         a `..`-shaped REMAINDER after it (e.g.
         ``${REPO:agency}/../../.ssh/id_rsa``), which unambiguously walks
         OUT of whatever root the slug eventually resolves to, regardless
         of what that root actually is (this module never resolves the
         slug itself — that is `resolve_command`'s job — but it can and
         must still catch this SHAPE). The placeholder segment is
         substituted for a neutral, absolute sentinel
         (`_PLACEHOLDER_SENTINEL`) and the existing normpath-based
         traversal check runs on the result. This holds UNCONDITIONALLY,
         including for a `POSITIONAL_ROLE` token (F3, round-7 review,
         2026-08-30): that role's own whitespace/leading-character
         exemption (see the `POSITIONAL_ROLE` branch below) is bypassed
         whenever the token carries a placeholder, specifically so a
         traversal smuggled through `${REPO:slug}/../../...` in PATTERN/
         FILTER position cannot skip this check merely because it does not
         start with `/` or `~` — a `${`-leading token never legitimately IS
         one anyway.

    Pure; never raises.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    form, rest = classify_command(tokens)
    roles = classify_tokens(form, rest)
    head_offset = len(tokens) - len(rest)
    hits: list[str] = []
    for i, tok in enumerate(tokens):
        rest_idx = i - head_offset
        role = roles[rest_idx] if 0 <= rest_idx < len(roles) else None

        if role is not None and role.kind == "POSITIONAL_ROLE":
            # grep/rg's PATTERN or jq's FILTER: prose/an expression the
            # operator wrote, not itself a filesystem target — UNLESS
            # (M-1 fix) it is a BARE (no whitespace) token that is already
            # absolute or `~`-prefixed, which no legitimate pattern/filter
            # is ever spelled as; that shape is scanned normally instead. A
            # genuinely prose pattern (any whitespace) or an ordinary bare,
            # non-path-shaped one (e.g. "somepattern", ".env", ".x") stays
            # exempt, unchanged from this check's pre-existing behavior —
            # deliberately DIFFERENT from `_paths_in_bounds`' own, narrower
            # M2 shape gate for the identical role: THIS function must
            # never mistake real prose for a smuggled path, while THAT one
            # (an execution gate, not a report) can afford to be stricter.
            #
            # A token carrying a ``${REPO:<slug>}`` placeholder is exempt
            # from BOTH of the checks above (F3, round-7 review,
            # 2026-08-30): neither the whitespace test nor the leading-
            # character test is meaningful for it (a placeholder token
            # starts with ``$``, never ``/``/``~``, so the leading-character
            # test would always wrongly exempt it), and this module's own
            # docstring above (escape 4) unconditionally promises every
            # placeholder-carrying token gets the `..`-remainder check
            # below — a promise the pre-fix code broke for exactly this
            # role by `continue`-ing before ever reaching it.
            if "${REPO:" not in tok:
                if any(ch.isspace() for ch in tok):
                    continue
                if not (tok.startswith("/") or tok.startswith("~")):
                    continue
            candidate = tok
        elif any(ch.isspace() for ch in tok):
            # A compound/quoted sub-command arrived as one token; shlex
            # already stripped its quoting, so re-split and re-scan it.
            hits.extend(find_hardcoded_paths(tok))
            continue
        elif role is not None and role.kind == "FLAG":
            embedded_value = role.embedded_value
            if embedded_value is None:
                continue
            candidate = embedded_value
        elif role is not None and role.kind == "BOUNDARY":
            continue
        elif role is None and tok.startswith("-"):
            # A head token (the command name, git's "log"/"show", or the
            # churn_report script path) or any token from an entirely
            # unrecognized command form — never part of the per-form
            # grammar table. Mirrors a `FLAG` token's own `=` handling
            # above for parity, since this is not itself classified.
            if "=" not in tok:
                continue
            candidate = tok.split("=", 1)[1]
        else:
            # FLAG_VALUE (regardless of is_path_designated),
            # POST_BOUNDARY_PATHSPEC, PATH_CANDIDATE, or a non-dash head
            # token / unrecognized-form token — always scanned like an
            # ordinary token. Deliberately NOT exempting a flag's own VALUE
            # merely for occupying "value position" the way
            # `_paths_in_bounds`' EXECUTION gate does (M2 there) — this
            # function's job is the broadest, most conservative STATIC
            # report of an apparent hardcoded product-repo path, run
            # regardless of whether the row would even be guard-legal.
            candidate = tok

        if "${REPO:" in candidate:
            sentinel_candidate = _PLACEHOLDER_RE.sub(_PLACEHOLDER_SENTINEL, candidate)
            if not sentinel_candidate.startswith(_PLACEHOLDER_SENTINEL):
                # The placeholder wasn't at the very start of the
                # candidate (e.g. a prefix glued on before it) — not the
                # shape this check targets; leave it be rather than guess.
                continue
            if not os.path.normpath(sentinel_candidate).startswith(_PLACEHOLDER_SENTINEL):
                hits.append(tok)
            continue
        looks_like_path = candidate.startswith("/") or candidate.startswith("~") or "/" in candidate
        if not looks_like_path:
            continue
        expanded = os.path.normpath(os.path.expanduser(candidate))
        if not os.path.isabs(expanded):
            continue
        if _is_always_safe(expanded):
            continue
        hits.append(tok)
    return hits


# --------------------------------------------------------------------------
# whole-ledger check
# --------------------------------------------------------------------------


def check_ledger(
    ledger_path: str = DEFAULT_LEDGER_PATH,
    registry_path: str = DEFAULT_REGISTRY_PATH,
) -> list[str]:
    """Reads the ledger and reports every hardcoded-repo-path and
    unknown-repo-slug violation. Never raises.
    """
    violations: list[str] = []
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        return [f"ledger-unreadable: {ledger_path}: {exc.__class__.__name__}: {exc}"]

    # A missing/empty/malformed registry is NOT reported on its own — a
    # ledger with no ${REPO:slug} reference at all (every runtime-only
    # metric) must keep working with no repo, and therefore no registry,
    # present at all — see `test_check_ledger_missing_registry_is_fine_for_a_runtime_only_ledger`
    # for this module's own falsifiability fixture proving the property.
    # When a row DOES reference a placeholder, `resolve_command` already
    # reports it below as `unknown-repo-slug`, naming the row and the slug
    # — an empty registry simply makes every referenced slug unknown, which
    # is exactly the right, specific, per-row signal.
    #
    # `_registry_rejections` (Blocker 1, this fix round) is deliberately
    # UNUSED here: this module's own CLI has no `extra-repo-root-rejected`
    # violation shape (that name, and the CLI-extra-root concept it also
    # covers, belongs to `validate_agentarch_ledger.check_ledger`, the
    # caller that actually reports each rejected registry entry by name —
    # see that function's own comment at its point of use). This CLI stays
    # a narrower static guard (hardcoded-repo-path / unknown-repo-slug
    # only); a rejected registry entry still surfaces here indirectly,
    # exactly as before, via `unknown-repo-slug` on any row that references
    # the rejected slug.
    registry, _registry_rejections = load_registry(registry_path)

    for i, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except Exception as exc:
            violations.append(f"line {i}: json-parse-error: {exc.__class__.__name__}")
            continue
        if not isinstance(row, dict):
            continue

        rid = row.get("id")
        command = row.get("metric_command")
        if not isinstance(command, str):
            continue

        for tok in find_hardcoded_paths(command):
            violations.append(
                f"line {i} (id={rid!r}): hardcoded-repo-path: {tok!r} in "
                "metric_command is a bare absolute path outside ~/.claude/ "
                "and /tmp/ — express it as ${REPO:<slug>} and register "
                f"<slug> in {registry_path}"
            )

        _, unknown_slugs = resolve_command(command, registry)
        for slug in unknown_slugs:
            violations.append(
                f"line {i} (id={rid!r}): unknown-repo-slug: "
                f"'${{REPO:{slug}}}' has no entry in {registry_path}"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    """Prints every violation, then a summary line; exit 1 iff any violation."""
    argv = list(sys.argv if argv is None else argv)
    ledger_path = argv[1] if len(argv) > 1 else DEFAULT_LEDGER_PATH
    registry_path = argv[2] if len(argv) > 2 else DEFAULT_REGISTRY_PATH
    try:
        violations = check_ledger(ledger_path, registry_path)
    except Exception as exc:
        violations = [f"checker-crashed: {exc.__class__.__name__}: {exc}"]
    for line in violations:
        print(line)
    print(f"agentarch_metric_check: {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
