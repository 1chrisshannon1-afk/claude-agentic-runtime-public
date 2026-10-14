#!/usr/bin/env python3
"""gh_issue_close_gate — PreToolUse gate for closing a GitHub issue.

Ported from the proven bash guard ~/.claude/scripts/gh_issue.sh (the `resolve`
subcommand's fabricated-resolution guard). The bash guard REFUSES to close an
issue unless every referenced ``--commit <sha>`` resolves to a real commit in
the current repo:

    for sha in "${COMMITS[@]}"; do
      git cat-file -e "${sha}^{commit}" 2>/dev/null \
        || _die "commit '$sha' not found in this repo — refusing to close ..."
    done

That guards against an agent posting a fabricated "Resolution" comment and
closing an issue with no real fix behind it. This hook reproduces the guard at
the Claude Code PreToolUse boundary: when the agent runs a Bash command that
CLOSES a GitHub issue (``gh issue close ...``) while ALSO asserting resolving
commits (via ``--commit <sha>`` flags on a gh_issue.sh invocation, or ``Fixes
#N (<sha>)`` / ``closes #N <sha>`` style references, or ``Closes: <sha>`` in a
close-comment body), every referenced sha must resolve in-repo or the close is
DENIED.

2026-08-03 extension -- deploy-ancestry guard. "A commit exists somewhere in
this repo" is a materially weaker guarantee than "this reached where the
close's own claim says it did": that gap is what let 34 QA-matrix rows get
marked "verified" (staging-only, not actually prod ancestors, mass-retracted
in one audit) and let two GitHub issues get closed-as-completed then reopened
because their code had never reached any remote. When the close's own text
(comment/body) makes a deploy-status claim using this project's status-
taxonomy vocabulary (``qa_coverage_matrix.html`` / ``path_to_launch.html``:
"deployed" / "in prod" / "IN-PROD" implying PRODUCTION, vs "on staging" /
"ON-STAGING" implying at least STAGING), every cited commit must ALSO verify
as a real ancestor of that claim's target ref -- ``git merge-base
--is-ancestor <sha> <target-ref>``, the same pattern already proven in this
repo's own ``_Config_Project/docs/domain/tests/test_qa_coverage_matrix_status.py``
and ``repo_tooling/scripts/backlog_groom/aggregate.py`` -- not merely exist as
a commit somewhere, possibly on an unmerged branch. A close whose text makes
NO deploy claim at all keeps the original commit-exists-only behavior
unchanged; the ancestry check is strictly additive, firing only when the close
itself asserts a deploy state. Target refs are configurable per repo via
``CSA_PROD_REF`` / ``CSA_STAGING_REF`` env vars -- this hook is product-
agnostic (used across repos, not just ExampleApp) and must never
hardcode one repo's branch names -- and default to ``origin/main`` / ``HEAD``
when unset, so a repo with no such convention degrades gracefully rather than
crashing or false-blocking.

Design contract (shared across all hook modules, see the spawning task):
  * A PURE decision function ``decide(event, resolver, enforce)`` +
    ``needs_block(commits, repo)`` that does no I/O beyond the injected
    ``resolver`` — trivially coverable.
  * A thin ``main()`` that reads the event, decides, emits/logs, exits 0.
    A deny is expressed as JSON (emit_pretooluse_deny), NEVER via exit code.
  * LOG-ONLY unless enforcing(): outside enforcement we log "would-deny" but
    do not emit the deny object, so the tool is allowed to proceed.
  * CSA_DISABLE_HOOKS master-off is honored transitively through
    _lib.enforcing() (disabled() short-circuits it to False).

This module owns exactly two files:
  ~/.claude/hooks/gh_issue_close_gate.py  (this file)
  ~/.claude/hooks/tests/test_gh_issue_close_gate.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Callable, Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402  (import after sys.path shim, mirrors sibling modules)

HOOK_NAME = "gh_issue_close_gate"

# The gh_issue.sh helper cites resolving commits with repeated --commit <sha>.
_COMMIT_FLAG_RE = re.compile(r"--commit[=\s]+([^\s'\"]+)")

# Free-form close references that BIND a resolution keyword directly to a sha,
# e.g.  "Fixes #42 in 1a2b3c4d",  "Closes: 1a2b3c4d5e",  "resolved by 0badc0de".
# The keyword must sit immediately before the sha (only small filler tokens like
# ``#42``, ``in``, ``by``, ``at``, ``via``, ``:`` allowed between) so the bare
# ``close`` verb baked into every ``gh issue close`` command can't, on its own,
# turn an unrelated hex token in the comment into a phantom "resolving commit".
# Only the sha is captured (group 1).
_RESOLUTION_SHA_RE = re.compile(
    r"(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b"  # a resolution keyword
    r"(?:[\s:]+(?:#\d+|in|by|at|via|commit))*"  # optional filler tokens
    r"[\s:]+"  # separator
    r"([0-9a-fA-F]{7,64})\b",  # the captured sha
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Command classification (pure).
# ---------------------------------------------------------------------------


def _is_gh(argv: list[str]) -> bool:
    """True if an argv's program is the `gh` CLI (basename match, like _lib)."""
    if not argv:
        return False
    return argv[0].rsplit("/", 1)[-1] == "gh"


def gh_close_segments(command: str) -> list[list[str]]:
    """Return the argv of every ``gh issue close ...`` segment in `command`.

    Reuses _lib's shell segmentation/tokenization (the same primitive git_guard
    uses) so compound commands, quotes, and command-substitution boundaries are
    honored identically. A segment counts as an issue-close when its argv is
    ``gh ... issue ... close``  (``gh issue close`` possibly with global flags
    between; we scan tokens rather than assuming fixed positions).

    Never raises: any unexpected error yields [].
    """
    if not command:
        return []
    try:
        out: list[list[str]] = []
        for seg in _lib._split_segments(command):
            toks = _lib._tokenize(seg)
            if not toks:
                continue
            toks = _lib._strip_prefix(toks)
            if not _is_gh(toks):
                continue
            # Look for the `issue` ... `close` verb pair anywhere in the argv.
            lowered = [t.lower() for t in toks]
            if "issue" in lowered and "close" in lowered:
                if lowered.index("issue") < lowered.index("close"):
                    out.append(toks)
        return out
    except Exception:
        return []


def gh_close_segments_with_raw(command: str) -> list[tuple[str, list[str]]]:
    """Like :func:`gh_close_segments` but pairs each close segment's RAW text
    with its argv. The raw text is required by the sanctioned not-planned path
    (2026-08-23): its marker/reason/claim tests are regexes over the segment's
    own text, so they must never see a sibling segment's content (marker
    leakage across ``&&`` was the reviewed failure mode). Never raises.
    """
    if not command:
        return []
    try:
        out: list[tuple[str, list[str]]] = []
        for seg in _lib._split_segments(command):
            toks = _lib._tokenize(seg)
            if not toks:
                continue
            toks = _lib._strip_prefix(toks)
            if not _is_gh(toks):
                continue
            lowered = [t.lower() for t in toks]
            if "issue" in lowered and "close" in lowered:
                if lowered.index("issue") < lowered.index("close"):
                    out.append((seg, toks))
        return out
    except Exception:
        return []


def is_issue_close(command: str) -> bool:
    """True iff the command contains at least one ``gh issue close`` segment."""
    return len(gh_close_segments(command)) > 0


# ---------------------------------------------------------------------------
# Sanctioned NOT-PLANNED close path (2026-08-23, oversight system #4400).
# SCOPE NOTE: this gate sees only a BARE `gh issue close` typed as the Bash
# command itself — it does NOT see the `gh issue close` that scripts/gh_issue.sh
# `dispose` runs internally (the segment's program is the helper, not gh). The
# helper carries its own validation, and the standing operator-approval rule on
# every not-planned batch is the actual control on that path.
# A close segment may close WITHOUT a resolving commit iff, in ITS OWN text:
#   (i)   it cites zero resolving commits,
#   (ii)  it makes no deploy-status claim,
#   (iii) it carries --reason/-r "not planned",
#   (iv)  it carries a structured Disposition marker.
# Anything else falls through to the existing guards unchanged. A
# ``duplicate-of #N`` disposition additionally checks that issue N exists —
# fail-OPEN with a logged note on an indeterminate answer (network/timeout),
# because every not-planned close batch is operator-approved anyway (plan §2b);
# a DEFINITIVELY absent issue number denies the exemption.
# ---------------------------------------------------------------------------

_DISPOSITION_RE = re.compile(
    r"Disposition:\s*(duplicate-of\s*#(\d+)|stale-superseded|wont-fix)\b",
    re.IGNORECASE,
)


def _argv_has_not_planned_reason(argv: list[str]) -> bool:
    """Condition (iii), evaluated against the segment's TOKENIZED argv — never
    raw text. The reviewed bypass: a ``--comment`` body QUOTING the words
    ``--reason 'not planned'`` must not count; only a real flag token whose
    VALUE token is exactly "not planned" does. Never raises."""
    try:
        n = len(argv)
        for i, tok in enumerate(argv):
            tl = tok.lower()
            if tl in ("--reason", "-r") and i + 1 < n:
                if argv[i + 1].strip().lower() == "not planned":
                    return True
            elif tl.startswith("--reason="):
                if tok[len("--reason=") :].strip().strip("'\"").lower() == "not planned":
                    return True
        return False
    except Exception:
        return False


def issue_exists(number: str, repo: str) -> bool | None:
    """Whether issue #number exists, per ``gh issue view`` from `repo`.

    True = exists; False = gh answered definitively that it does not
    (nonzero exit with output mentioning 'not found'/'Could not resolve');
    None = indeterminate (timeout, no network, gh missing) — the caller
    degrades OPEN with a logged note. Never raises.
    """
    if not number:
        return None
    if not repo:
        # No resolved repo cwd: running gh from an arbitrary directory could
        # resolve a DIFFERENT repository's issue #N — fail-open (None) instead
        # of guessing (reviewed finding R3-13).
        return None
    try:
        proc = subprocess.run(
            ["gh", "issue", "view", number, "--json", "number"],
            cwd=repo,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        return None
    if proc.returncode == 0:
        return True
    err = (proc.stderr or b"").decode("utf-8", "replace").lower()
    if "not found" in err or "could not resolve" in err or "no issue" in err:
        return False
    return None


def segment_not_planned_exempt(
    raw_segment: str,
    argv: list[str],
    repo: str,
    issue_resolver: Callable[[str, str], bool | None] | None = None,
) -> tuple[bool, str]:
    """Whether ONE close segment qualifies for the sanctioned not-planned path.

    All four conditions are evaluated against the segment's OWN content — a
    marker or reason flag in a sibling segment can never exempt this one.
    Conditions (i)/(ii)/(iv) read the raw text (the marker legitimately lives
    in the ``--comment`` body); condition (iii) reads the tokenized ARGV, so
    body text quoting the flag can never impersonate it (the reviewed bypass).
    Returns ``(exempt, note)``; ``note`` is non-empty only for the logged
    fail-open case (indeterminate duplicate-of target). Never raises.
    """
    try:
        if extract_commit_refs(raw_segment):
            return (False, "")  # (i) cites a commit -> normal guards apply
        if detect_deploy_claim(raw_segment) is not None:
            return (False, "")  # (ii) deploy claim -> ancestry guard must run
        if not _argv_has_not_planned_reason(argv):
            return (False, "")  # (iii) real --reason/-r flag token required
        m = _DISPOSITION_RE.search(raw_segment)
        if not m:
            return (False, "")  # (iv)
        dup_number = m.group(2)
        if dup_number:
            resolve = issue_resolver if issue_resolver is not None else issue_exists
            try:
                exists = resolve(dup_number, repo)
            except Exception:
                exists = None
            if exists is False:
                return (False, "")  # duplicate-of a nonexistent issue: no exemption
            if exists is None:
                return (
                    True,
                    f"duplicate-of #{dup_number} unresolvable (offline/timeout) — "
                    "exemption granted fail-open; batch is operator-approved.",
                )
        return (True, "")
    except Exception:
        return (False, "")


def extract_commit_refs(command: str) -> list[str]:
    """Harvest every commit-ish referenced as a *resolution* in `command`.

    Two sources, matching how the resolution is asserted in practice:
      1. Explicit ``--commit <sha>`` flags (the gh_issue.sh contract). These are
         ALWAYS treated as resolving commits — that is their sole purpose.
      2. Hex shas BOUND to a fix/close/resolve keyword in free-form
         ``--body``/``--comment`` text (``Fixes ... <sha>``, ``Closes: <sha>``).
         An unbound hex run — e.g. a build id or the ``close`` verb that is baked
         into every ``gh issue close`` command — is ignored, so it can't become a
         phantom "commit" that then fails the guard and blocks a legitimate
         close.

    De-duplicated, order-preserving. Never raises: returns [] on error.
    """
    try:
        refs: list[str] = []
        seen: set[str] = set()

        def _add(sha: str) -> None:
            if sha and sha not in seen and not sha.isdigit():
                seen.add(sha)
                refs.append(sha)

        # (1) explicit --commit <sha> flags.
        for m in _COMMIT_FLAG_RE.finditer(command):
            _add(m.group(1))

        # (2) shas bound to a resolution keyword.
        for m in _RESOLUTION_SHA_RE.finditer(command):
            _add(m.group(1))
        return refs
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Deploy-target claim detection (pure). Vocabulary mirrors this project's own
# status taxonomy (qa_coverage_matrix.html / path_to_launch.html: "IN-PROD" /
# "deployed" / "in prod" vs "ON-STAGING" / "on staging"), generalized to
# plain-English phrasing because this hook is product-agnostic and cannot
# assume any one repo's exact tag markup.
# ---------------------------------------------------------------------------

# Staging-destination phrasing.
_STAGING_CLAIM_RE = re.compile(
    r"\bon[-\s]staging\b|\bto\s+staging\b|\bin[-\s]staging\b|\bstaging[-\s]only\b",
    re.IGNORECASE,
)
# Production-destination phrasing, including the bare "deployed" the QA matrix
# uses unqualified to mean "reached prod" (see #3860/#3865/qa-matrix context).
_PROD_CLAIM_RE = re.compile(
    r"\bin[-\s]prod(?:uction)?\b|\bto\s+prod(?:uction)?\b"
    r"|\blive\s+in\s+prod(?:uction)?\b|\bdeployed\b",
    re.IGNORECASE,
)
# "(auto-)?deployed to/on/in staging" is the STAGING claim's OWN verb, not an
# independent prod signal -- stripped as a single unit before the bare
# `\bdeployed\b` alternative of _PROD_CLAIM_RE is tested (see
# detect_deploy_claim), so "deployed to staging" can never masquerade as a
# separate prod claim on the very word that names staging as the destination.
# A genuinely distinct prod phrase elsewhere in the SAME text (e.g. "Deployed
# to production. Also verified on staging.") is untouched by this strip.
_DEPLOYED_TO_STAGING_RE = re.compile(
    r"\b(?:auto-)?deployed\s+(?:to\s+staging|on[-\s]staging|in[-\s]staging)\b",
    re.IGNORECASE,
)
# A prod claim's bare "deployed" must be a POSITIVE assertion, never part of a
# negation ("not deployed yet", "this was never deployed", "isn't deployed") --
# an honest statement that something is NOT deployed must never be misread as
# a claim that it IS. Stripped before the bare-word alternative is tested, same
# technique as _DEPLOYED_TO_STAGING_RE above.
_NEGATED_DEPLOY_RE = re.compile(
    r"\b(?:not|never|isn't|isnt|wasn't|wasnt|hasn't|hasnt|no)\s+"
    r"(?:\w+\s+)?deployed\b",
    re.IGNORECASE,
)

_DEFAULT_PROD_REF = "origin/main"


def detect_deploy_claim(text: str) -> str | None:
    """Classify the deploy-target claim (if any) made by a close's own text.

    Returns ``"staging"``, ``"prod"``, or ``None`` (no deploy-status claim at
    all -- the original commit-exists-only guard applies unchanged; this
    function is the trigger for the ADDITIONAL ancestry check, never a
    replacement for the existence check).

    PROD wins whenever BOTH a prod signal and a staging signal are present in
    the SAME text (e.g. "Deployed to production. Also verified on staging.")
    -- the stronger/riskier claim wins, not whichever regex happens to run
    first. Before the prod signal is tested, two false-positive sources are
    stripped from a scratch copy of the text (the ORIGINAL text is still used
    for the staging check, untouched):
      * "(auto-)?deployed to/on/in staging" -- that occurrence of "deployed"
        IS the staging claim, not a separate prod claim (see
        _DEPLOYED_TO_STAGING_RE).
      * a NEGATED "deployed" ("not deployed", "never deployed", ...) -- an
        honest non-deployment statement must never register as a prod claim
        (see _NEGATED_DEPLOY_RE).
    Never raises: any regex error is treated as "no claim detected" (fail-open
    -- an unparseable claim must never demand ancestry proof it can't have
    asked for).
    """
    if not text:
        return None
    try:
        staging_match = bool(_STAGING_CLAIM_RE.search(text))
        residual = _DEPLOYED_TO_STAGING_RE.sub(" ", text)
        residual = _NEGATED_DEPLOY_RE.sub(" ", residual)
        prod_match = bool(_PROD_CLAIM_RE.search(residual))
    except Exception:
        return None
    if prod_match:
        return "prod"
    if staging_match:
        return "staging"
    return None


def target_ref_for_claim(claim: str) -> str | None:
    """Resolve the configured target ref for a detected deploy claim, or
    ``None`` when no USABLE ref is configured for it.

    This hook is product-agnostic (dev runtime, used across repos, not just
    ExampleApp) so it never hardcodes a repo's actual branch names.
    ``CSA_PROD_REF`` / ``CSA_STAGING_REF`` let each repo declare its own
    convention.

    PROD: unset (or "") falls back to ``origin/main`` -- a real, meaningful,
    near-universal convention -- so the hook degrades gracefully in a repo
    with no explicit override instead of crashing or false-blocking.

    STAGING: unset (or "") returns ``None`` -- there is NO safe generic
    default. Unlike prod, no branch name is universal enough to assume, and a
    "HEAD" fallback would make the ancestry check vacuously true for any
    commit already on the current branch (``git merge-base --is-ancestor
    <any-local-commit> HEAD`` is always true there) -- silently turning a
    staging claim into an always-passing check. The caller (:func:`decide`)
    treats a ``None`` target_ref as "this claim isn't actually checkable" and
    degrades to no-claim-detected, exactly like a text with no deploy claim at
    all, rather than vacuously validating against a meaningless default.
    """
    try:
        if claim == "staging":
            return os.environ.get("CSA_STAGING_REF", "") or None
        return os.environ.get("CSA_PROD_REF", "") or _DEFAULT_PROD_REF
    except Exception:
        return None if claim == "staging" else _DEFAULT_PROD_REF


# ---------------------------------------------------------------------------
# The fabricated-resolution guard (pure, given an injected resolver).
# ---------------------------------------------------------------------------


def needs_block(
    commits: Iterable[str],
    repo: str,
    resolver: Callable[[str, str], bool] | None = None,
) -> tuple[bool, str]:
    """Decide whether an issue-close must be BLOCKED (fabricated-resolution).

    Ports gh_issue.sh's ``resolve`` guard as a pure function:

      * With NO commits at all -> BLOCK. The bash guard refuses to close without
        at least one ``--commit`` ("no close without a real fix"). An issue-close
        that asserts zero resolving commits is exactly the fabricated case.
      * Otherwise, EVERY referenced sha must resolve to a real commit in `repo`
        (``git cat-file -e "<sha>^{commit}"``). If ANY sha fails to resolve,
        BLOCK naming the first offender (matching the bash ``_die`` on the first
        missing commit).
      * All shas resolve -> ALLOW.

    ``resolver(sha, repo) -> bool`` is injected so the decision is pure and the
    tests need no real git. In production ``main()`` passes
    :func:`commit_resolves`. A None resolver defaults to :func:`commit_resolves`.

    Returns ``(block: bool, reason: str)``. ``reason`` is "" when not blocking.
    """
    resolve = resolver if resolver is not None else commit_resolves
    commit_list = [c for c in commits if c]
    if not commit_list:
        return (
            True,
            "refusing to close: no resolving commit referenced "
            "(fabricated-resolution guard — cite the fix's commit sha).",
        )
    for sha in commit_list:
        try:
            ok = resolve(sha, repo)
        except Exception:
            ok = False
        if not ok:
            return (
                True,
                f"commit '{sha}' not found in this repo — refusing to close "
                "(fabricated-resolution guard).",
            )
    return (False, "")


# ---------------------------------------------------------------------------
# The deploy-ancestry guard (pure, given an injected ancestry resolver).
# Runs ONLY after needs_block() above has already passed (every cited commit
# exists) and ONLY when the close's own text made a deploy claim.
# ---------------------------------------------------------------------------


def needs_block_for_ancestry(
    commits: Iterable[str],
    repo: str,
    claim: str,
    target_ref: str,
    ancestry_resolver: Callable[[str, str, str], bool | None] | None = None,
) -> tuple[bool, str]:
    """Decide whether a close claiming `claim` deploy status must be BLOCKED
    because a cited commit is proven NOT an ancestor of `target_ref`.

    For every cited commit, ``ancestry_resolver(sha, target_ref, repo)`` (in
    production :func:`commit_is_ancestor`) returns:

      * ``True``  -- sha verified as an ancestor of target_ref -> keep checking.
      * ``False`` -- target_ref resolved fine and sha is DEFINITELY not an
        ancestor of it -> BLOCK, naming the offending sha and ref (matching
        needs_block's "block on the first offender" shape).
      * ``None``  -- indeterminate (target_ref itself doesn't resolve, git is
        unusable, timeout, ...) -> degrade OPEN for that commit; a misconfigured
        or missing ref convention must never false-block a legitimate close.

    An empty commit list is not this function's concern (needs_block already
    blocks a close with zero cited commits before this ever runs) -> ALLOW.

    Returns ``(block: bool, reason: str)``. ``reason`` is "" when not blocking.
    """
    resolve = ancestry_resolver if ancestry_resolver is not None else commit_is_ancestor
    commit_list = [c for c in commits if c]
    if not commit_list:
        return (False, "")
    for sha in commit_list:
        try:
            ok = resolve(sha, target_ref, repo)
        except Exception:
            ok = None
        if ok is False:
            return (
                True,
                f"commit '{sha}' is not an ancestor of '{target_ref}' — the close "
                f"claims {claim} status but this commit has not actually reached "
                f"{target_ref} (deploy-ancestry guard). Cite a commit that has "
                "really reached that ref, or correct the claimed status.",
            )
    return (False, "")


# ---------------------------------------------------------------------------
# The real resolvers — the ONLY functions that shell out to git.
# ---------------------------------------------------------------------------


def commit_resolves(sha: str, repo: str) -> bool:
    """True iff ``sha`` resolves to a real commit object in the git repo `repo`.

    Mirrors the bash guard exactly: ``git cat-file -e "<sha>^{commit}"`` run
    with the repo as cwd, success (exit 0) means the commit exists. Any failure
    — bad sha, tree/blob peeled to a commit, not a repo, git missing, timeout —
    is treated as "does not resolve" (fail-closed). Never raises.
    """
    if not sha:
        return False
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=repo or None,
            capture_output=True,
            timeout=15,
        )
        return proc.returncode == 0
    except Exception:
        return False


def commit_is_ancestor(sha: str, target_ref: str, repo: str) -> bool | None:
    """True iff `sha` is a real ancestor of `target_ref` in the git repo `repo`.

    Ports the proven pattern already used in this repo (``git merge-base
    --is-ancestor`` in ``_Config_Project/docs/domain/tests/
    test_qa_coverage_matrix_status.py`` and ``repo_tooling/scripts/
    backlog_groom/aggregate.py``), rather than inventing new ancestry-check
    code. Per git's own documented exit-code contract for this subcommand:

      * exit 0 -> `sha` IS an ancestor of `target_ref`               -> True
      * exit 1 -> both refs resolved fine; `sha` is NOT an ancestor  -> False
      * any OTHER exit (unresolvable ref/sha, not a repo, ...), a raised
        exception, or a timeout -> git could not answer at all       -> None

    ``None`` is deliberately distinct from ``False``: a target ref that does
    not exist (e.g. a misconfigured ``CSA_PROD_REF``, or a repo with no
    staging-branch convention at all) is an environment/config gap, not
    evidence the close is fabricated, so the caller must degrade OPEN on
    ``None`` rather than blocking. Never raises.
    """
    if not sha or not target_ref:
        return None
    try:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, target_ref],
            cwd=repo or None,
            capture_output=True,
            timeout=15,
        )
    except Exception:
        return None
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


# ---------------------------------------------------------------------------
# Pure top-level decision — no I/O beyond the injected resolvers.
# ---------------------------------------------------------------------------


def decide(
    event: dict,
    resolver: Callable[[str, str], bool] | None = None,
    ancestry_resolver: Callable[[str, str, str], bool | None] | None = None,
    issue_resolver: Callable[[str, str], bool | None] | None = None,
) -> tuple[bool, str, dict]:
    """Pure decision for one hook event.

    Returns ``(block, reason, detail)`` where ``detail`` carries the fields to
    log. This function does NO logging, printing, or enforcement gating — that
    is the thin ``main()``'s job — so it is exhaustively unit-testable.

      * Non-Bash tools -> never block (nothing to gate).
      * A Bash command with no ``gh issue close`` segment -> never block.
      * A ``gh issue close`` command -> harvest its resolving commit refs and
        run :func:`needs_block` against the event's cwd (the repo) first — the
        fabricated-resolution guard is primary and unconditional.
      * Only once that passes: if the close's own text makes a deploy claim
        (:func:`detect_deploy_claim`), resolve its target ref
        (:func:`target_ref_for_claim`) and run :func:`needs_block_for_ancestry`
        as an ADDITIONAL check. No claim -> behavior is identical to before
        this check existed. A claim with NO usable target ref configured
        (e.g. "staging" with ``CSA_STAGING_REF`` unset/empty) degrades to the
        SAME "no claim" behavior -- see :func:`target_ref_for_claim` -- rather
        than vacuously checking against a meaningless default.
    """
    if _lib.tool_name(event) != "Bash":
        return (False, "", {"reason": "not-bash"})
    command = _lib.bash_command(event)
    if not is_issue_close(command):
        return (False, "", {"reason": "not-issue-close"})

    repo = _lib.cwd(event)

    # Sanctioned not-planned path (2026-08-23): evaluated per SEGMENT, against
    # each close segment's OWN text only. When EVERY close segment in the
    # command qualifies, the close is allowed (with any fail-open notes logged
    # in detail). When ANY segment does not qualify, the ORIGINAL whole-command
    # guards below run unchanged — strictly narrower than before, never wider.
    seg_pairs = gh_close_segments_with_raw(command)
    if seg_pairs:
        notes: list[str] = []
        all_exempt = True
        for raw_seg, seg_argv in seg_pairs:
            exempt, note = segment_not_planned_exempt(
                raw_seg, seg_argv, repo, issue_resolver=issue_resolver
            )
            if note:
                notes.append(note)
            if not exempt:
                all_exempt = False
                break
        if all_exempt:
            return (
                False,
                "",
                {
                    "reason": "not-planned-exempt",
                    "command": command,
                    "repo": repo,
                    "notes": notes,
                },
            )

    commits = extract_commit_refs(command)
    detail: dict = {"command": command, "repo": repo, "commits": commits}

    block, reason = needs_block(commits, repo, resolver=resolver)
    if block:
        return (block, reason, detail)

    claim = detect_deploy_claim(command)
    target_ref = target_ref_for_claim(claim) if claim is not None else None
    if claim is not None and target_ref is None:
        # Claim detected but not actually checkable (no usable target ref
        # configured for it) -- degrade to "no claim" rather than vacuously
        # defaulting.
        claim = None
    detail["deploy_claim"] = claim
    if claim is not None:
        detail["target_ref"] = target_ref
        block, reason = needs_block_for_ancestry(
            commits, repo, claim, target_ref, ancestry_resolver=ancestry_resolver
        )
        if block:
            return (block, reason, detail)

    return (False, "", detail)


# ---------------------------------------------------------------------------
# Thin main() — read event, decide, emit/log, exit 0.
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point. Always exits 0; a deny is emitted as JSON, never as status.

    Flow:
      1. Master OFF (CSA_DISABLE_HOOKS) -> do nothing at all, allow.
      2. Decide (pure). Not-blocking -> allow silently.
      3. Blocking:
           * enforcing() -> emit the PreToolUse deny + log "deny".
           * otherwise    -> log "would-deny" only (LOG-ONLY), allow to proceed.
    """
    if _lib.disabled():
        return 0

    event = _lib.read_event()
    block, reason, detail = decide(event)
    if not block:
        # The sanctioned not-planned exemption is a BYPASS of the fabricated-
        # resolution guard — every use is logged (incl. any fail-open notes) so
        # ~/.claude/.enforcement/log.jsonl can answer "how often did the gate
        # wave a close through, and why" (reviewed finding R3-3).
        if detail.get("reason") == "not-planned-exempt":
            _lib.log(HOOK_NAME, "not-planned-exempt-allow", **detail)
        return 0

    enforce = _lib.enforcing(detail.get("repo"))
    if enforce:
        _lib.emit_pretooluse_deny(f"gh_issue_close_gate: {reason}")
        _lib.log(HOOK_NAME, "deny", reason=reason, enforce=enforce, **detail)
    else:
        _lib.log(HOOK_NAME, "would-deny", reason=reason, enforce=enforce, **detail)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
