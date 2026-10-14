#!/usr/bin/env python3
"""validate_agentarch_ledger — validates knowledge/agentarch_recommendations.jsonl
(#4400, #4436; item 7 of the AA-ledger telemetry-gap closeout).

The standing recommendation ledger written by `agentic-systems-architect` is
free-text-adjacent (a shell string stored per row, re-run on every audit) and
had zero mechanical validation: a malformed row, a duplicate/out-of-sequence
id, a `metric_command` that violates the agent definition's own flag-allowlist
guard, or a `checked_value` nobody ever re-verified against the live command
could all sit in the file indefinitely. This module is that mechanical check.

What it validates, per line:
  * field SET and ORDER — the exact ten canonical keys, in the exact order
    the agent definition's Read-FIRST #4 documents.
  * `id` format (``AA-<4-digit>``) AND sequence — line N must carry
    ``AA-<N zero-padded to 4>``; a duplicate id is also flagged.
  * `issued_at` / `checked_at` — ISO-8601 date or (checked_at only) null.
  * `status` domain — ``open|moved|withdrawn`` ONLY. ``no-change`` is a
    REPORT-TABLE-only outcome (item 8 of this closeout) and is explicitly
    rejected as a STORED status with its own message, never silently lumped
    in with a generic domain violation.
  * `target_direction` domain — ``up|down``.
  * `baseline_value` / `checked_value` — numeric or null (a JSON bool is
    explicitly rejected even though Python's ``bool`` is an ``int`` subclass).
  * `checked_at`/`checked_value` PAIRING — both null or both set; one set
    without the other is a stored-state inconsistency.
  * `metric_command` HARDCODED-REPO-PATH — regardless of `status`, and
    checked FIRST, before repo-placeholder resolution below (Finding 4,
    round 8 review, 2026-08-30 — a row carrying BOTH an unknown slug and a
    separate hardcoded path must report both, not just the first one an
    early `continue` happens to reach): the RAW (pre-resolution) command is
    scanned via `agentarch_metric_check.find_hardcoded_paths`: a bare
    absolute path outside the always-safe roots (``~/.claude/``, ``/tmp/``
    — but NOT ``~/.claude/projects/``, per-session transcripts that almost
    always encode a specific product repo's name) and not expressed via
    ``${REPO:<slug>}`` is its own `hardcoded-repo-path` violation. This is
    the same regression guard `agentarch_metric_check.py`'s own CLI
    enforces, wired in here too so the daily validator run itself catches
    it even if that separate script is never invoked. A row carrying this
    violation is NEVER executed — regardless of what guard-legality below
    would otherwise say about it (Finding 5, round 8 review, 2026-08-30: a
    literal hardcoded path can coincidentally ALSO be guard-legal, e.g.
    when it happens to sit under an already-registered repo's own root;
    "flagged" and "executed" must never both be true for the same row).
  * `metric_command` REPO-PLACEHOLDER RESOLUTION — a ``${REPO:<slug>}``
    token (the repo-agnostic form `agentarch_metric_check.py` enforces) is
    resolved against ``knowledge/repo_registry.json`` BEFORE both the
    guard-legality check below and the live command run, via
    `agentarch_metric_check.resolve_command`/`load_registry`. An unknown
    slug is its own `metric-command-unknown-repo-slug` violation and the
    row is skipped — never run, never silently passed. A row with no
    placeholder is unaffected. Every registered repo's root is always an
    allowed bounds-check root for the check below — and an `extra_repo_root`
    (CLI trailing arg) is now run through `agentarch_metric_check.
    root_is_acceptable` before being trusted (Blocker 2, round 8 review,
    2026-08-30, extended by Finding 1, round-2 security review, 2026-08-30
    to also require the `.git`-presence check `load_registry` already
    applied, closing the last gap between the two producers of this set) —
    an overbroad, nonexistent, or `.git`-less extra root is dropped and
    reported (`extra-repo-root-rejected`), never silently accepted. A
    REGISTRY entry rejected by that same `root_is_acceptable` test inside
    `load_registry` is reported the identical way (Blocker 1, this fix
    round): `load_registry` now returns its rejections alongside the
    accepted registry dict, and this function turns each one into its own
    `extra-repo-root-rejected` violation naming the registry slug — before
    this fix, a rejected registry entry that no ledger row happened to
    reference produced zero violations, contradicting this module's own
    documented guarantee. A REGISTRY entry (never a CLI `extra_repo_root` —
    that path never reaches this check) may also be rejected for a FOURTH
    reason, checked separately and BEFORE `root_is_acceptable` even runs: a
    root containing whitespace (Finding 2, round-2 security review,
    2026-08-30 — see `agentarch_metric_check.load_registry`'s own docstring)
    would silently mis-tokenize once substituted into a command string, so
    it is dropped and reported the identical `extra-repo-root-rejected` way
    rather than ever being registered.
  * `metric_command` GUARD-LEGALITY — reimplements, field for field, the
    agent definition's own closed allowlist test (Read-FIRST #4): a shlex
    parse failure, an unrecognized command form, an unlisted flag, a
    forbidden substring (shell metacharacters, even quoted), an outright
    forbidden command (``-c`` code execution, ``eval``, ``xargs``,
    ``find -exec``), or a path token outside ``~/.claude/`` (EXCLUDING
    ``~/.claude/projects/`` — see `_NEVER_SAFE_ROOTS`, Blocker 5, round 3
    review, 2026-08-28: this exclusion is enforced here, in the actual
    bounds check that gates execution, not only reported as a separate
    hardcoded-repo-path finding while the command still runs), the audited
    repo(s) (from `extra_repo_root` and/or the repo registry), or ``/tmp``
    are all guard-illegal and reported by name. A guard-illegal command is
    REFUSED — never executed — even when `checked_at` is set.
  * LIVE RE-SCORE — for every row with a non-null `checked_at` whose command
    passes the guard, the command is actually run (read-only forms only) and
    its live value compared against the stored `checked_value` — DIRECTIONALLY,
    against `target_direction`, not by raw inequality: a live value that moved
    against direction (or fell back past `baseline_value`) is reported as
    needing re-score; equal-or-better-in-direction movement (e.g. a
    live-appending counter simply growing further on an `up` metric) is
    silently accepted as still-true progress, never flagged as drift.

Exit code: 0 when clean, 1 when any violation is found — unlike the
report-only hooks (model_pin_parity, heartbeat_audit), this module's whole
purpose is a validator a scheduled job or the operator can gate on.
Never raises out of main(): a crash is caught and reported as one violation
line, exit 1 — a broken ledger must still be visible, not silently green.

This module owns exactly two files:
  ~/.claude/hooks/validate_agentarch_ledger.py  (this file)
  ~/.claude/hooks/tests/test_validate_agentarch_ledger.py
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Sequence
from datetime import date

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import agentarch_metric_check  # noqa: E402  (import after sys.path shim, mirroring the other hooks)

_HOME = os.path.expanduser("~")
# NEITHER root constant below is realpath'd, and that is now DELIBERATE
# (Blocker 1, round 6 review, 2026-08-28 — superseding the round-4 comment
# this replaces, which is now stale: see the corrected historical note in
# `_paths_in_bounds`'s own docstring for exactly what was wrong with it).
# The prior implementation applied NO normalization at all for an absolute
# token; that round's fix reached for `os.path.realpath` on both sides of a
# STRING comparison as the patch. This round replaces the comparison
# itself: `agentarch_metric_check.path_resolves_under_root` is a
# filesystem-IDENTITY test (`os.stat` + `os.path.samestat`), so it needs no
# string normalization on either side to begin with — it makes no
# difference whether `_TMP_ROOT` is spelled `/tmp` or its macOS symlink
# target `/private/tmp`, because `os.stat` itself resolves that symlink at
# comparison time regardless of which spelling is on disk. Do not
# reintroduce a realpath call here as a "fix" for anything; it would be a
# no-op inherited from a comparison strategy this module no longer uses.
_CLAUDE_ROOT = os.path.join(_HOME, ".claude") + os.sep
_TMP_ROOT = "/tmp" + os.sep
# ~/.claude/projects/ holds per-SESSION transcripts, named after the
# session's own cwd — a path under it almost always encodes a specific
# product repo's name, and is absent (not merely different) from every
# other session — see agentarch_metric_check._NEVER_SAFE_ROOTS's own
# docstring for the full rationale (Blocker E, 2026-08-28) and
# agents/agentic-systems-architect.md's Read-FIRST #4, which states this
# exclusion as part of the guard-legality spec this module reimplements.
# Carved OUT of `_paths_in_bounds`'s otherwise-blanket ~/.claude/ allowance
# (Blocker 5, round 3 review, 2026-08-28) — before this, a metric_command
# naming a path under here was reported as `hardcoded-repo-path` but was
# STILL guard-legal and STILL actually executed, contradicting this
# agent definition's own documented guarantee.
_NEVER_SAFE_ROOTS = (os.path.join(_CLAUDE_ROOT, "projects") + os.sep,)

DEFAULT_LEDGER_PATH = os.path.join(_HOME, ".claude", "knowledge", "agentarch_recommendations.jsonl")
# The registry (schema {"repos": {"<slug>": {"root": "..."}}}) is the single
# source of truth for which repo roots a `${REPO:<slug>}` metric_command may
# resolve against — see agentarch_metric_check.py, which owns load_registry/
# resolve_command and this same default path.
DEFAULT_REGISTRY_PATH = agentarch_metric_check.DEFAULT_REGISTRY_PATH
# Every registered app's root is ALWAYS an allowed bounds-check root (see
# check_ledger below, which derives it fresh from the registry on every
# call) — never a baked-in product path here. This constant is deliberately
# None: there is no default product repo in the runtime, and there must
# never be one (a repo that does not exist yet must work unmodified). Pass
# an EXTRA root here, or via main()'s trailing CLI args, only for a genuine
# one-off root not worth registering; a durable new app belongs in
# knowledge/repo_registry.json instead, never in a hardcoded list here.
DEFAULT_EXTRA_REPO_ROOT: str | Sequence[str] | None = None

# Score-or-withdraw (AA-0039): an `open` row whose checked_at is still null
# this many days after issued_at is a violation. Before this existed the
# validator silently skipped every never-scored row, so the newest and
# least-vetted claims were the only ones exempt from checking while every
# closed row was re-run daily forever. The grace is sized to the SCORER's
# cadence — the agentic-systems-architect re-scores monthly — not to this
# validator's daily run; a shorter grace fires every day for weeks between
# audits and drowns the daily digest.
NEVER_SCORED_GRACE_DAYS = 35


def _as_roots(repo_root: str | Sequence[str] | None) -> list[str]:
    """One root, several, or none — always a list; empty entries dropped."""
    if not repo_root:
        return []
    if isinstance(repo_root, str):
        return [repo_root]
    return [r for r in repo_root if r]


def _safe_getcwd() -> str | None:
    """``os.getcwd()``, or ``None`` when the current working directory no
    longer exists (``FileNotFoundError`` — e.g. a deleted directory, or a
    directory removed out from under a long-lived process). ``guard_check``
    is documented as never raising; a bare ``os.getcwd()`` call violated
    that contract for the one caller (`_paths_in_bounds`, resolving a
    relative path token) that needs the cwd at all. Never raises.
    """
    try:
        return os.getcwd()
    except FileNotFoundError:
        return None


def _days_between(issued_at: object, today: str) -> int | None:
    """Whole days from issued_at to today; None when either is not an ISO date."""
    try:
        return (date.fromisoformat(today) - date.fromisoformat(str(issued_at))).days
    except (TypeError, ValueError):
        return None


CANONICAL_FIELDS = (
    "id",
    "issued_at",
    "claim",
    "metric",
    "metric_command",
    "baseline_value",
    "target_direction",
    "status",
    "checked_at",
    "checked_value",
)
# no-change is deliberately absent: item 8 of this closeout makes it a
# REPORT-table-only outcome, never a stored status (see status-domain below).
STATUS_DOMAIN = {"open", "moved", "withdrawn"}
DIRECTION_DOMAIN = {"up", "down"}
_ID_RE = re.compile(r"^AA-(\d{4})$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_FORBIDDEN_SUBSTRINGS = (">", "<", "|", ";", "&", "`", "$(")
_FORBIDDEN_LEADING = {"eval", "xargs"}
_DASH_C_SHELLS = {"python3", "python", "bash", "sh"}

# --------------------------------------------------------------------------
# guard-legality (Read-FIRST #4's closed test, reimplemented) — root-cause
# rebuild, round-4 security review, 2026-08-30, superseded by a single
# left-to-right CONSUMING scanner, round-5 security review, 2026-08-30:
# form-matching stays in ONE shared per-form grammar table,
# `agentarch_metric_check.FORM_GRAMMARS`, and per-token ROLE classification
# (flag / flag-value / positional-role / post-boundary-pathspec / default
# path-candidate) is now computed by ONE function, `agentarch_metric_check.
# classify_tokens`, consulted by both this module and
# `agentarch_metric_check.find_hardcoded_paths` — replacing round-4's own
# three independently re-walking functions (`flag_value_indices`,
# `positional_role_exempt_index`, `_not_positional_role_candidate_indices`,
# all REMOVED this round), which the round-5 reviewer diagnosed as the same
# failure mode round-4 itself was built to fix, moved inside one module:
# "Three independent walks over one token list cannot agree on what a token
# *is*." See that module's own docstring, "THE SINGLE LEFT-TO-RIGHT
# CONSUMING SCANNER", for the full design; this module's functions below
# are now thin, form-scoped call-throughs to that shared table's public API
# (`classify_command`/`flag_is_allowed`/`classify_tokens`/
# `end_of_options_index`).
# --------------------------------------------------------------------------


def _match_form(tokens: list[str]) -> tuple[str | None, list[str]]:
    """(form_name, tokens-after-the-command-head) — thin wrapper over
    `agentarch_metric_check.classify_command`, the shared grammar's single
    form-matching authority. `form_name` is `None` when the command's head
    token(s) match none of the eight recognized forms — the caller reports
    that as "unrecognized command form". `grep` and `rg` are now SEPARATE
    form names (B2, round-4 security review, 2026-08-30 — the old version
    of this function collapsed both under one `"grep"` name and one shared
    flag table, which was itself a root cause: real grep and real rg
    define different arities for the same letters — see
    `agentarch_metric_check.FORM_GRAMMARS`'s own per-form comments, which
    also carry a correction of an earlier overclaim that rg's own arities
    were "verified live" on this machine; they are documentation-sourced).
    """
    return agentarch_metric_check.classify_command(tokens)


def _paths_in_bounds(
    tokens: list[str],
    repo_root: str | Sequence[str] | None,
    form: str | None = None,
) -> tuple[bool, str]:
    """Every path-shaped, non-flag token must resolve under an allowed root.

    ``repo_root`` is one extra root or a sequence of them (one per audited
    app) on top of the always-allowed ``~/.claude/`` and ``/tmp/``. ``form``
    is the recognized command-form name `_match_form` already computed
    (``"grep"``, ``"rg"``, ``"wc"``, ``"ls"``, ``"cat"``, ``"jq"``,
    ``"git"``, or ``"churn_report"``), defaulting to ``None`` for a caller
    (a test, most often) that has no form context to supply — which simply
    means `agentarch_metric_check.classify_tokens` has no grammar to
    recognize anything against, so EVERY token is classified
    `PATH_CANDIDATE` and fully bounds-checked, the fail-CLOSED direction.

    ROOT-CAUSE REBUILD (round-5 security review, 2026-08-30, superseding
    round-4's own "unification," which the round-5 reviewer found was never
    actually finished — see `agentarch_metric_check.classify_tokens`'s own
    docstring, "THE SINGLE LEFT-TO-RIGHT CONSUMING SCANNER", for the full
    account): this function now calls `agentarch_metric_check.
    classify_tokens(form, tokens)` ONCE and reads its per-token `TokenRole`
    output as a LOOKUP for every decision below — it no longer re-derives
    flag-value or positional-role membership itself. Two composed defects
    in the round-4 design this replaces, both closed by construction here
    rather than by patching either symptom in isolation:

      (a) THE ORDERING BUG — the round-4 version's flag-value shape check
          (M2) ran BEFORE the `..`-traversal check, so a flag value that
          was a RELATIVE path carrying `..` (no leading `/`/`~`) was never
          traversal-checked at all — the shape check only ever caught an
          ABSOLUTE or `~`-prefixed flag value, and any RELATIVE one, once
          classified "exempt by position", short-circuited straight past
          the traversal check that followed it. Closed here by folding the
          `..` test directly INTO the shape gate itself
          (`agentarch_metric_check.flag_value_shape_needs_bounds_check`/
          `positional_role_shape_needs_bounds_check`) — there is no
          later-stage traversal check for a token to route around merely
          by having been classified as a flag value or positional role
          first; the classification and the shape policy are decided
          together, once, in `classify_tokens` and its two shape helpers.
      (b) THE SCANNING BUG — the round-4 version's `flag_value_indices`
          scanned for occurrences of value-consuming flag STRINGS via
          independent, position-blind string matching rather than real
          left-to-right consumption, so in `-e -e X` BOTH `-e` occurrences
          were treated as "a flag needing a value": the FIRST correctly
          marked the SECOND as its value, but the SECOND (which IS the
          first `-e`'s value, not a real flag) was then ALSO treated as
          "a flag", wrongly marking `X` — the real FILE operand in true
          grep/rg semantics once `-e` supplies the pattern — as exempt.
          Closed here because `classify_tokens` consumes each flag's
          value token(s) the INSTANT it recognizes the flag, advancing a
          single cursor past them — a token already consumed this way can
          never be re-examined as a different flag later in the same pass.

      TOGETHER these closed a working, reproduced arbitrary-file-read
      exploit: ``grep -c -e -e ../../../etc/hosts`` and ``grep -rl -e -e
      ../../../etc/ssh`` were both guard-legal and actually executed by
      `run_metric_command`, reading real filesystem content, before this
      fix — see `agentarch_metric_check.classify_tokens`'s own docstring
      for the full trace of exactly how the two defects composed.

    PER-KIND POLICY this function applies to `classify_tokens`' output
    (every kind not listed here — `POST_BOUNDARY_PATHSPEC`, a `FLAG_VALUE`
    with `is_path_designated=True`, i.e. jq's `--slurpfile`/`--rawfile`
    FILE half, and the default `PATH_CANDIDATE` — is ALWAYS a full
    bounds-check target, no exemption at all):
      - ``"FLAG"``/``"BOUNDARY"`` — never itself a path; skipped entirely.
      - ``"FLAG_VALUE"`` with `is_path_designated=False` (grep/rg's `-e`
        PATTERN, git's `-n` COUNT, jq's `--arg`/`--argjson` NAME/VALUE) —
        exempt UNLESS `flag_value_shape_needs_bounds_check` says the token
        itself already looks like a real path (absolute, `~`-prefixed, or
        carrying `..`) — reproduced live, pre-fix: ``grep -c -e
        ~/.ssh/id_rsa <file>``, ``git log -n /Users/x/.ssh/id_rsa``, and
        ``jq --arg /Users/x/.ssh/id_rsa v <f>`` were all guard-legal with
        an absolute/`~` path sitting in flag-value position (M2, round-4).
      - ``"POSITIONAL_ROLE"`` (grep/rg's PATTERN when no `-e` was consumed
        anywhere, or jq's FILTER — ALWAYS positional for jq, unaffected by
        which value-consuming flags precede it) — exempt UNLESS
        `positional_role_shape_needs_bounds_check` says the token already
        looks like a real path (the SAME three conditions as the
        flag-value gate, PLUS any `/` anywhere in the token, a broader
        test preserved from this exemption's own pre-existing scope).
        `agentarch_metric_check.classify_tokens` only ever assigns this
        role when an `-e` flag was NOT consumed anywhere in the pass (B1,
        round-4 — real grep/rg semantics: with `-e`, every remaining
        non-flag token is a FILE) and, for grep/rg specifically, only when
        at least one FURTHER non-flag token also follows it (the "sole
        argument" shape — e.g. ``rg -l <path>``, no separate file operand
        — is a real search target, not prose, and is never exempted).
      - ``"PATH_CANDIDATE"`` when `form == "churn_report"` — exempt
        UNLESS `positional_role_shape_needs_bounds_check` says the token
        looks like a path. This form's own closed flag spec (the agent
        definition's Read-FIRST #4: ``--days N``, ``--json`` only) never
        defines a path-shaped positional argument at all — its one legal
        value token (`--days`'s own NUMERIC value) is already exempt via
        the `FLAG_VALUE` rule above; this blanket carve-out additionally
        covers any OTHER stray bare token this form's grammar has no role
        for, since there is no path this form can ever smuggle regardless
        of which token carries it.

    A path under ``~/.claude/projects/`` is NEVER in bounds regardless of
    ``repo_root`` — see ``_NEVER_SAFE_ROOTS``'s docstring (Blocker 5, round
    3 review, 2026-08-28). A RELATIVE path token (e.g. ``some/dir/file``, or
    a checked bare word like ``secrets.txt``) is resolved against this
    process's own current working directory — the same directory
    `run_metric_command`'s bare ``subprocess.run`` actually resolves it
    against at execution time — and then bounds-checked exactly like an
    absolute path.

    GIT'S ``--`` END-OF-OPTIONS MARKER (M1, round-4 security review,
    2026-08-30): once `agentarch_metric_check.end_of_options_index(form,
    tokens)` finds a literal ``--`` token for a form whose grammar
    recognizes one (only `git`), every token AFTER that index is a
    pathspec (`classify_tokens` assigns it `POST_BOUNDARY_PATHSPEC`), NEVER
    given the ordinary "starts with `-` ⇒ skip" free pass that would
    otherwise apply to any flag-shaped token — ``git log -- -n
    /etc/passwd`` treats BOTH ``-n`` and ``/etc/passwd`` as literal
    pathspecs (git itself defines ``--`` that way), and both are now
    bounds-checked accordingly; the ``--`` marker token itself
    (`classify_tokens` assigns it `BOUNDARY`) is still never bounds-checked
    (it names no file).

    THE CONTAINMENT TEST ITSELF (Blocker 1, round 6 review, 2026-08-28):
    both the never-safe-roots check and the ``roots`` allow-list check call
    `agentarch_metric_check.path_resolves_under_root` — a filesystem-
    IDENTITY test (`os.stat` + `os.path.samestat` on the deepest existing
    ancestor), never a string comparison. This is the shared canonical
    implementation both this module and `agentarch_metric_check.py` use
    (this module already imports that one; see its own docstring for the
    full algorithm and rationale) — replacing what, through rounds 3-5, was
    a `str.startswith`-based prefix comparison that needed a fresh patch
    every time a new SPELLING of the same real directory slipped past it: a
    trailing separator, a ``//`` or ``/./`` segment, a bare directory name
    with no trailing separator, and (round 6) a case-VARIANT spelling —
    verified live on this machine's default case-insensitive APFS volume:
    ``~/.claude/projects`` and ``~/.claude/PROJECTS`` are the SAME INODE, so
    a `startswith` test comparing the literal strings never matched, even
    though they name the identical directory. `path_resolves_under_root`
    closes that whole CLASS of bypass at once, because it never looks at
    spelling in the first place — see its own docstring for exactly how.

    HISTORICAL NOTE, corrected (round 6, 2026-08-28): earlier text here
    (and at this module's root-constant definitions) claimed a bare
    ``os.path.abspath`` "preserves a POSIX double leading slash (``//``)
    and a ``/./`` segment untouched" as the reason those spellings were
    once guard-legal. That claim was factually WRONG — `abspath` (which is
    `normpath(join(cwd, p))`) DOES collapse a mid-path `//` and `/./`; only
    a LEADING `//` is POSIX-special-cased and left alone. The real
    historical reason those spellings were legal at an earlier HEAD is that
    the OLD `_paths_in_bounds` applied NO normalization at all to an
    absolute token before comparing it — not that `abspath` was
    insufficient. This fix needs no correction to that claim beyond noting
    it: the current approach (filesystem-identity comparison) requires no
    reliance on string normalization of any kind, so the question of which
    normalizing function is "enough" no longer arises.
    """
    roots = [_CLAUDE_ROOT, _TMP_ROOT]
    for extra in _as_roots(repo_root):
        roots.append(os.path.expanduser(extra))
    roles = agentarch_metric_check.classify_tokens(form, tokens)
    for idx, tok in enumerate(tokens):
        role = roles[idx]
        if role.kind in ("FLAG", "BOUNDARY"):
            continue
        if role.kind == "FLAG_VALUE" and not role.is_path_designated:
            if not agentarch_metric_check.flag_value_shape_needs_bounds_check(tok):
                continue
        elif role.kind == "POSITIONAL_ROLE":
            if not agentarch_metric_check.positional_role_shape_needs_bounds_check(tok):
                continue
        elif (
            role.kind == "PATH_CANDIDATE"
            and form == "churn_report"
            and not agentarch_metric_check.positional_role_shape_needs_bounds_check(tok)
        ):
            continue
        # Everything that reaches this point — POST_BOUNDARY_PATHSPEC, a
        # FLAG_VALUE with is_path_designated=True, a default PATH_CANDIDATE,
        # or a FLAG_VALUE/POSITIONAL_ROLE/churn_report-PATH_CANDIDATE token
        # whose own SHAPE just failed its exemption gate above — is now an
        # UNCONDITIONAL bounds-check target: the `..`-traversal test runs
        # FIRST, on every such token, with no exemption able to bypass it
        # (root-cause fix, round-5 security review, 2026-08-30 — see this
        # function's own docstring, defect (a), for why this ordering
        # itself is the actual security fix, not merely a refactor).
        if ".." in tok.split("/"):
            return False, f"path traversal token {tok!r}"
        expanded = os.path.expanduser(tok)
        if os.path.isabs(expanded):
            candidate = expanded
        else:
            cwd = _safe_getcwd()
            if cwd is None:
                return False, (
                    f"relative path token {tok!r} cannot be resolved: this process's "
                    "current working directory no longer exists"
                )
            candidate = os.path.join(cwd, expanded)
        if any(agentarch_metric_check.path_resolves_under_root(candidate, root) for root in _NEVER_SAFE_ROOTS):
            return False, f"path {tok!r} resolves under the never-safe ~/.claude/projects/ root"
        if not any(agentarch_metric_check.path_resolves_under_root(candidate, root) for root in roots):
            return False, f"path {tok!r} resolves outside allowed roots"
    return True, ""


def guard_check(
    command: str, repo_root: str | Sequence[str] | None = None
) -> tuple[bool, str]:
    """Reimplements the agent definition's Read-FIRST #4 metric_command guard.

    ``repo_root`` may be one allowed repo root or several (see _paths_in_bounds).
    Returns ``(True, "")`` when legal to run; ``(False, reason)`` otherwise —
    including an unparseable command, which is illegal (never run), not a
    crash. Never raises.
    """
    for seq in _FORBIDDEN_SUBSTRINGS:
        if seq in command:
            return False, f"forbidden substring {seq!r} in command"
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return False, f"unparseable (shlex): {exc}"
    if not tokens:
        return False, "empty command"

    head = tokens[0]
    if head in _FORBIDDEN_LEADING:
        return False, f"forbidden command '{head}'"
    if head in _DASH_C_SHELLS and "-c" in tokens:
        return False, f"forbidden '-c' code execution via '{head}'"
    if head == "find" and "-exec" in tokens:
        return False, "forbidden 'find -exec'"

    form, rest = _match_form(tokens)
    if form is None:
        return False, f"unrecognized command form (head={head!r})"

    # M1 (round-4 security review, 2026-08-30): a token AT or AFTER a
    # form's own end-of-options marker (only `git`'s literal `--`) is
    # never flag-parsed at all, even when it looks flag-shaped — git
    # itself treats everything after `--` as a literal pathspec, so
    # `-n` there is a real FILENAME, never the `-n COUNT` flag.
    boundary = agentarch_metric_check.end_of_options_index(form, rest)
    for i, tok in enumerate(rest):
        if boundary is not None and i >= boundary:
            continue
        if tok.startswith("-"):
            if agentarch_metric_check.flag_is_allowed(form, tok):
                continue
            return False, f"unlisted flag {tok!r} for '{form}'"

    ok, reason = _paths_in_bounds(rest, repo_root, form)
    if not ok:
        return False, reason
    return True, ""


# Command heads whose exit code 1 is a legitimate, successful "zero-ish"
# result rather than a real failure. `grep`/`rg` always use exit 1 for "no
# match found" (a real, successful zero-count result, not an error) — this
# is the ONLY command form with that convention unconditionally. `jq`
# shares the same shape but only when invoked with ``-e``/``--exit-status``:
# jq's own docs define exit 1 there as "the last output value was false or
# null", a legitimate result, not a processing error — a plain `jq` (no
# ``-e``) invocation's exit 1 is a genuine usage/filter error and must NOT
# be tolerated. No other recognized form (`ls`, `cat`, `wc`, `git`,
# `churn_report.py`, a `python3 <allowlisted script>` invocation) has any
# "no match" convention on exit 1 at all — for every one of them exit 1 is
# a real failure (e.g. `ls`: "No such file or directory", `cat`: "No such
# file or directory", `wc`: "No such file or directory") and must surface
# as `metric-command-run-failed`, never a silent clean `0`.
_GREP_FAMILY_HEADS = ("grep", "rg")


def _exit_1_is_tolerated(tokens: list[str]) -> bool:
    """True when `tokens`' command head has a legitimate "no match"/
    "false-or-null" convention on exit code 1 — see the module-level
    comment above for the per-form rationale. Dispatches by command head,
    mirroring the same by-head dispatch `_match_form` (guard-legality) and
    `agentarch_metric_check.classify_command` (form-matching for
    pattern-vs-path classification) already use for their own separate
    purposes. Pure; never raises.
    """
    if not tokens:
        return False
    head = tokens[0]
    if head in _GREP_FAMILY_HEADS:
        return True
    if head == "jq":
        return "-e" in tokens or "--exit-status" in tokens
    return False


def run_metric_command(tokens: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    """Actually runs an already-guard-cleared command. IMPURE (subprocess).

    Exit code 0 is always success. Exit code 1 is success ONLY for the
    command forms `_exit_1_is_tolerated` recognizes as having a legitimate
    "no match"/"false-or-null" convention on that code (grep/rg always;
    jq only with ``-e``) — every other form's exit 1 is a real failure and
    is reported as such. Returns (True, stdout) or (False, reason).

    Fixes a real, exploitable defect (round 7 review, 2026-08-28): the
    prior version tolerated exit 1 for EVERY command form, not just
    grep/rg — so `ls`/`cat`/`wc`/`git` against a missing/renamed target
    (e.g. a stale `${REPO:<slug>}` path, or the round-6 unexpanded-``~``
    case this function already guards below) silently scored a clean,
    successful empty result (`0`/no lines) instead of surfacing as a run
    failure. A `target_direction: "down"` metric treats `0` as the BEST
    possible value, so a renamed/removed/never-checked-out measurement
    target reported "target fully achieved, forever, with no error" in a
    validator whose entire job is catching exactly this kind of
    unverifiable metric — this was the actual mechanism behind the round-6
    ``~``-expansion finding (that fix closed only one of the many ways a
    path can fail to exist; this is the real, general root cause).

    Every token is passed through `os.path.expanduser` first (finding #5,
    round 6 review, 2026-08-28): `_paths_in_bounds` above explicitly
    accepts a ``~``-prefixed path token as legal — the agent definition
    documents `~/.claude/hooks/churn_report.py` as the canonical spelling
    for that one form, and `_paths_in_bounds` resolves ``~`` before its own
    bounds check — but this function's `subprocess.run` call runs with NO
    shell and previously never expanded ``~`` itself, so a legal, guard-
    cleared ``ls ~/.claude/hooks`` token arrived at the real filesystem call
    as the LITERAL four-character string ``~/.claude/hooks``, which almost
    never exists. `os.path.expanduser` is a no-op on a token that carries
    no leading ``~`` at all, so every existing absolute-path row is
    unaffected.
    """
    tokens = [os.path.expanduser(tok) for tok in tokens]
    try:
        proc = subprocess.run(tokens, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    if proc.returncode == 0:
        return True, proc.stdout
    if proc.returncode == 1 and _exit_1_is_tolerated(tokens):
        return True, proc.stdout
    return False, f"exit {proc.returncode}: {proc.stderr.strip()[:200]}"


# Directories every list-style path result is filtered against before being
# counted (below) — the SAME conventional exclusions ~/.claude/.gitignore
# applies (verified: __pycache__/, .pytest_cache/, .ruff_cache/ are all
# git-ignored there) and that Claude Code's own Bash-tool `grep` wrapper
# applies via `--ignore-files --exclude-dir=.git` on every INTERACTIVE re-run
# a human or the dispatching agent does by hand. Without this filter,
# `run_metric_command`'s raw `subprocess.run` (which never goes through that
# shell-level wrapper) silently over-counts bytecode/cache artifacts that
# were never what a "count of files implementing X" metric meant — measured
# live: AA-0003's `grep -rl heartbeat ~/.claude/hooks` returned 11 raw hits
# (4 real source files + 7 __pycache__/.pytest_cache/.ruff_cache artifacts)
# the same day this filter was added.
_NOISE_DIR_MARKERS = (
    "/__pycache__/",
    "/.pytest_cache/",
    "/.ruff_cache/",
    "/.git/",
    "/node_modules/",
    "/.venv/",
    "/htmlcov/",
)


def _drop_noise_paths(lines: list[str]) -> list[str]:
    """Filters conventional VCS/cache-noise paths out of a list-style result.

    A defensible, deterministic stand-in for full `.gitignore` evaluation
    (which needs repo context this module doesn't reliably have for an
    arbitrary stored path) — not a general-purpose ignore engine. Pure;
    never raises.
    """
    return [ln for ln in lines if not any(marker in f"/{ln}" for marker in _NOISE_DIR_MARKERS)]


def _interpret_output(tokens: list[str], stdout: str) -> str:
    """Best-effort scalar reading of a metric_command's stdout, matching the
    ledger's own value convention (its `metric` descriptions state it
    explicitly for the list-style commands): `grep`/`rg -c` and `wc` are a
    literal count already; every other recognized form's comparable value is
    the count of non-empty, non-noise output lines ("value = count of paths
    printed" — see `_drop_noise_paths`). Returned as a string so a JSON int
    and this always compare consistently.
    """
    head = tokens[0] if tokens else ""
    is_count_mode = head == "wc" or (head in ("grep", "rg") and "-c" in tokens)
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not is_count_mode:
        lines = _drop_noise_paths(lines)
    if is_count_mode:
        if lines and lines[0].split():
            return lines[0].split()[0]
        return "0"
    return str(len(lines))


def _numeric(val: object) -> float | None:
    """val as a float when it is a JSON int/float (never a bool — a bool is
    an int subclass and would silently pass an `isinstance(x, (int, float))`
    check), else None.
    """
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _is_float_str(val: object) -> bool:
    """True when `val` (the interpreter's own string output) parses as a
    plain float — guards the `float()` call below from raising on a
    non-numeric interpreted value.
    """
    try:
        float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


def _regressed_against_direction(
    live_value: str,
    checked_value: object,
    baseline_value: object,
    direction: object,
) -> tuple[bool, str]:
    """True + a detail suffix only when a live re-score value is a REAL
    regression: it moved AGAINST `target_direction` relative to the stored
    `checked_value`, or fell back past the original `baseline_value` even
    while not (yet) behind the last checked value. Equal-or-better-in-
    direction movement — including a live-appending counter simply growing
    further on an `up` metric — is silently accepted as still-true progress,
    never flagged as "needs re-score" the way a raw inequality would.

    Falls back to the plain inequality (any change at all is reported) when
    the values can't be compared numerically/directionally at all — a stored
    non-numeric checked_value, a missing/unrecognized target_direction, or a
    live_value the interpreter didn't return as a plain number. That
    degraded case still surfaces a real change, never silently swallows it.
    """
    live_num = float(live_value) if _is_float_str(live_value) else None
    checked_num = _numeric(checked_value)
    if live_num is None or checked_num is None or direction not in DIRECTION_DOMAIN:
        if str(checked_value) != live_value:
            return True, ""
        return False, ""

    baseline_num = _numeric(baseline_value)
    if direction == "up":
        if live_num < checked_num:
            detail = f" (regressed against target_direction=up: {live_num:g} < {checked_num:g})"
            return True, detail
        if baseline_num is not None and live_num < baseline_num:
            return True, f" (fell back past baseline_value={baseline_num:g})"
    else:  # direction == "down"
        if live_num > checked_num:
            detail = f" (regressed against target_direction=down: {live_num:g} > {checked_num:g})"
            return True, detail
        if baseline_num is not None and live_num > baseline_num:
            return True, f" (rose back past baseline_value={baseline_num:g})"
    return False, ""


# --------------------------------------------------------------------------
# per-row structural validation
# --------------------------------------------------------------------------


def validate_row(row: object, line_no: int) -> list[str]:
    """Structural checks needing no IO. Pure. Never raises."""
    out: list[str] = []
    prefix = f"line {line_no}"
    if not isinstance(row, dict):
        return [f"{prefix}: not a JSON object"]

    fields = list(row.keys())
    field_set = set(fields)
    canonical_set = set(CANONICAL_FIELDS)
    if field_set != canonical_set:
        missing = sorted(canonical_set - field_set)
        extra = sorted(field_set - canonical_set)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"extra {extra}")
        out.append(f"{prefix}: field-set: " + "; ".join(detail))
    elif fields != list(CANONICAL_FIELDS):
        out.append(f"{prefix}: field-order: got {fields}, expected {list(CANONICAL_FIELDS)}")

    rid = row.get("id")
    m = _ID_RE.match(rid) if isinstance(rid, str) else None
    if m is None:
        out.append(f"{prefix}: id-format: {rid!r} does not match 'AA-<4-digit>'")
    else:
        expected = f"AA-{line_no:04d}"
        if rid != expected:
            out.append(f"{prefix}: id-sequence: id {rid!r} != expected {expected!r} for this line")

    issued = row.get("issued_at")
    if not isinstance(issued, str) or not _DATE_RE.match(issued):
        out.append(f"{prefix}: date-format: issued_at={issued!r} is not YYYY-MM-DD")

    checked_at = row.get("checked_at")
    if checked_at is not None and (
        not isinstance(checked_at, str) or not _DATE_RE.match(checked_at)
    ):
        out.append(f"{prefix}: date-format: checked_at={checked_at!r} is not null or YYYY-MM-DD")

    status = row.get("status")
    if status not in STATUS_DOMAIN:
        if status == "no-change":
            out.append(
                f"{prefix}: status-domain: status='no-change' is a REPORT-TABLE-only "
                "outcome and must never be a STORED status (open|moved|withdrawn)"
            )
        else:
            out.append(
                f"{prefix}: status-domain: status={status!r} not one of open|moved|withdrawn"
            )

    direction = row.get("target_direction")
    if direction not in DIRECTION_DOMAIN:
        out.append(f"{prefix}: direction-domain: target_direction={direction!r} not one of up|down")

    for key in ("baseline_value", "checked_value"):
        val = row.get(key)
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float))):
            out.append(f"{prefix}: value-type: {key}={val!r} is not numeric or null")

    checked_value = row.get("checked_value")
    if (checked_at is None) != (checked_value is None):
        out.append(
            f"{prefix}: checked-pairing: checked_at={checked_at!r} but "
            f"checked_value={checked_value!r} (both must be null together or set together)"
        )

    return out


# --------------------------------------------------------------------------
# whole-ledger orchestration
# --------------------------------------------------------------------------


def check_ledger(
    path: str,
    extra_repo_root: str | Sequence[str] | None = DEFAULT_EXTRA_REPO_ROOT,
    run_live: bool = True,
    today: str | None = None,
    registry_path: str = DEFAULT_REGISTRY_PATH,
) -> list[str]:
    """Reads the ledger, validates every row, and (when run_live) re-scores
    every checked, guard-legal row against its command's live output, and
    flags every `open` row still unscored past NEVER_SCORED_GRACE_DAYS
    (needs ``today`` to age a row; without it that check is skipped).

    Every ``${REPO:<slug>}`` placeholder in a row's `metric_command` is
    resolved against ``registry_path`` (knowledge/repo_registry.json,
    schema ``{"repos": {"<slug>": {"root": "..."}}}``, via
    `agentarch_metric_check.resolve_command`/`load_registry`) BEFORE both
    the guard-legality bounds check and the live command run. A row whose
    placeholder names an unregistered slug is reported as its own
    `metric-command-unknown-repo-slug` violation and skipped — never run,
    never silently passed. A row with no placeholder at all is unaffected
    (`resolve_command` passes it through unchanged, and a missing/empty
    registry never fails it). Every registered repo's root is always an
    additional allowed bounds-check root, on top of any ``extra_repo_root``
    the caller supplies and the always-allowed ``~/.claude/``/``/tmp/``.
    """
    out: list[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        return [f"ledger-unreadable: {path}: {exc.__class__.__name__}"]

    registry, registry_rejections = agentarch_metric_check.load_registry(registry_path)
    # `registry.values()` is already bounds-validated (`load_registry` runs
    # every entry through `root_is_acceptable` — overbroad + isdir + `.git`
    # check — before it is ever returned) — but `extra_repo_root` is the
    # OTHER producer of this same allowed-execution-roots set, and until
    # Blocker 2 (round 8 review, 2026-08-30) it reached `guard_check` with no
    # equivalent validation at all: a CLI trailing arg of `~`, `$HOME`, an
    # ancestor of `$HOME`, or `/` all reached guard_check as a LEGAL
    # bounds-check root, defeating the whole point of validating the
    # registry side. Blocker 2 only ported the overbroad+isdir half, though
    # — `load_registry` also requires an accepted root to contain a `.git`
    # entry (an actual repo checkout, never an arbitrary broad directory
    # that merely happens to exist), and until Finding 1 (round-2 security
    # review, 2026-08-30) the CLI-extra-root path lacked that check too:
    # `extra_repo_root=os.path.expanduser("~/.ssh")` was accepted as a legal
    # bounds-check root and a `cat`-shaped command against it ran with zero
    # violations. Both gaps are now closed the same way, permanently: this
    # loop calls `agentarch_metric_check.root_is_acceptable` — the exact
    # same overbroad+isdir+`.git` test `load_registry` applies — rather than
    # reimplementing any part of it, so the two producers cannot drift apart
    # again. A rejected root is DROPPED and REPORTED, never silently
    # accepted.
    #
    # A REGISTRY entry `load_registry` itself rejected is reported here too
    # (Blocker 1, this fix round) — before this, a rejected registry entry
    # was structurally unreportable: `load_registry` returned a bare dict
    # with no channel to name what it dropped, so an overbroad/nonexistent/
    # non-repo/whitespace-containing (a fourth reason, checked separately
    # and BEFORE `root_is_acceptable` even runs — see that function's own
    # and `load_registry`'s own docstrings) registry entry that no ledger
    # row happened to reference produced ZERO violations, contradicting
    # `schedules/prompts/daily_sweep.txt`'s and `commands/sweep.md`'s own
    # documented claim that such an entry "is dropped and reported as its
    # own `extra-repo-root-rejected` violation, never silently accepted."
    # Reused verbatim, same violation name and message shape as the
    # CLI-root rejection loop below, just naming the registry slug instead
    # of a bare path.
    for rejected_slug, rejected_reason in registry_rejections:
        out.append(
            f"extra-repo-root-rejected: registry entry {rejected_slug!r}: {rejected_reason} "
            "and was dropped rather than accepted as a bounds-check root"
        )

    extra_roots: list[str] = []
    for raw_root in _as_roots(extra_repo_root):
        accepted, result = agentarch_metric_check.root_is_acceptable(raw_root)
        if not accepted:
            out.append(
                f"extra-repo-root-rejected: {result} and was dropped rather than "
                "accepted as a bounds-check root"
            )
            continue
        extra_roots.append(result)
    all_allowed_roots = extra_roots + sorted(set(registry.values()))

    ids_seen: dict[str, int] = {}
    for i, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except Exception as exc:
            out.append(f"line {i}: json-parse-error: {exc.__class__.__name__}")
            continue

        out.extend(validate_row(row, i))

        rid = row.get("id") if isinstance(row, dict) else None
        if isinstance(rid, str):
            if rid in ids_seen:
                out.append(f"line {i}: id-duplicate: {rid!r} already used on line {ids_seen[rid]}")
            else:
                ids_seen[rid] = i

        if not isinstance(row, dict):
            continue
        command = row.get("metric_command")
        if not isinstance(command, str):
            out.append(f"line {i}: metric-command-missing: metric_command is not a string")
            continue

        # Regardless of status, and BEFORE the unknown-slug early-continue
        # below (Finding 4, round 8 review, 2026-08-30): a `metric_command`
        # that hardcodes a bare absolute product-repo path (never expressed
        # via ${REPO:<slug>}) is the exact regression `agentarch_metric_check`
        # exists to prevent (Blocker D, 2026-08-28) — this validator must
        # catch it too, not rely solely on that module's own, separately-
        # invoked CLI. Scanned on the RAW `command` (still carrying its
        # ${REPO:<slug>} markers), never on `resolved` — a legitimate
        # placeholder's substituted-in root (e.g. a pytest tmp_path in this
        # module's own tests, or any registered repo whose root sits outside
        # ~/.claude/ and /tmp/) would otherwise be indistinguishable from a
        # genuinely hardcoded path once already substituted in. Running this
        # scan BEFORE the unknown-slug check (rather than after, behind a
        # `continue`) means a row carrying BOTH an unknown slug AND a
        # separate hardcoded path is reported for both, matching what
        # `agentarch_metric_check.check_ledger` already reports for the
        # identical row — the two modules had silently diverged on this
        # exact case (this module's own docstring claims they never do).
        hardcoded_hits = agentarch_metric_check.find_hardcoded_paths(command)
        for tok in hardcoded_hits:
            out.append(
                f"line {i} (id={row.get('id')!r}): hardcoded-repo-path: {tok!r} in "
                "metric_command is a bare absolute path outside the always-safe "
                "roots (~/.claude/, /tmp/ — excluding ~/.claude/projects/) — "
                f"express it as ${{REPO:<slug>}} and register <slug> in {registry_path}"
            )

        resolved, unknown_slugs = agentarch_metric_check.resolve_command(command, registry)
        if unknown_slugs:
            for slug in unknown_slugs:
                out.append(
                    f"line {i} (id={row.get('id')!r}): metric-command-unknown-repo-slug: "
                    f"'${{REPO:{slug}}}' has no entry in the repo registry ({registry_path})"
                )
            continue
        if resolved is None:
            # Unreachable when unknown_slugs is empty (resolve_command's own
            # contract), but checked explicitly rather than asserted (NIT,
            # round 8 review, 2026-08-30): a bare `assert` is stripped under
            # `python -O`, which would otherwise pass a real `None` into
            # `shlex.split` below and raise unexpectedly, violating this
            # function's own "never raises" contract.
            continue

        if hardcoded_hits:
            # Finding 5 (round 8 review, 2026-08-30) — the most serious of
            # this round's findings: a `metric_command` already CLASSIFIED
            # as a hardcoded-repo-path violation was still being EXECUTED
            # whenever it happened to ALSO be guard-legal (e.g. a literal
            # path that coincides with an already-registered repo's own
            # root) — directly contradicting this module's own docstring,
            # which claims execution is gated by the SAME bounds check, not
            # merely reported separately. Skip execution entirely for this
            # row, mirroring how an unknown-repo-slug violation already
            # skips it above — a row is either safe to run, or it is
            # reported and never run; there is no third state where it is
            # both flagged AND executed.
            continue

        legal, reason = guard_check(resolved, all_allowed_roots)
        if not legal:
            out.append(f"line {i} (id={row.get('id')!r}): metric-command-illegal: {reason}")
            continue

        if not run_live:
            continue
        checked_at = row.get("checked_at")
        checked_value = row.get("checked_value")
        if checked_at is None or checked_value is None:
            # Score-or-withdraw (AA-0039). Only an OPEN row can be stale-unscored;
            # moved/withdrawn rows carry their own outcome. A half-null pair —
            # EITHER orientation — is a pairing defect validate_row already
            # reports, not "never scored". Report the live value so the scorer
            # records it without re-running anything.
            if (
                row.get("status") != "open"
                or not today
                or checked_at is not None
                or checked_value is not None
            ):
                continue
            age = _days_between(row.get("issued_at"), today)
            if age is None or age <= NEVER_SCORED_GRACE_DAYS:
                continue
            tokens = shlex.split(resolved)
            ok, output_or_err = run_metric_command(tokens)
            live = str(_interpret_output(tokens, output_or_err)).strip() if ok else "UNAVAILABLE"
            out.append(
                f"line {i} (id={row.get('id')!r}): never-scored: open {age} days "
                f"(grace {NEVER_SCORED_GRACE_DAYS}) with checked_at null; live value now "
                f"{live} — record checked_at/checked_value or withdraw"
            )
            continue

        tokens = shlex.split(resolved)
        ok, output_or_err = run_metric_command(tokens)
        if not ok:
            out.append(
                f"line {i} (id={row.get('id')!r}): metric-command-run-failed: {output_or_err}"
            )
            continue
        live_value = _interpret_output(tokens, output_or_err)
        regressed, detail = _regressed_against_direction(
            live_value, checked_value, row.get("baseline_value"), row.get("target_direction")
        )
        if regressed:
            suffix = f", as of {today}" if today else ""
            out.append(
                f"line {i} (id={row.get('id')!r}): checked-value-mismatch: stored "
                f"checked_value={checked_value!r} but live command now returns "
                f"{live_value!r}{detail} (re-score needed{suffix})"
            )

    return out


def main(argv: list[str] | None = None) -> int:
    """Prints every violation, then a summary line; exit 1 iff any violation."""
    argv = list(sys.argv if argv is None else argv)
    path = argv[1] if len(argv) > 1 else DEFAULT_LEDGER_PATH
    # Every registered repo (knowledge/repo_registry.json) is ALWAYS an
    # allowed bounds-check root — see DEFAULT_EXTRA_REPO_ROOT above. A
    # trailing argv here is only for a one-off EXTRA root not yet worth
    # registering; the common case (no trailing args at all) needs none.
    extra_roots = list(argv[2:]) if len(argv) > 2 else DEFAULT_EXTRA_REPO_ROOT
    try:
        violations = check_ledger(path, extra_roots, run_live=True, today=date.today().isoformat())
    except Exception as exc:
        violations = [f"validator-crashed: {exc.__class__.__name__}: {exc}"]
    for line in violations:
        print(line)
    print(f"validate_agentarch_ledger: {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
