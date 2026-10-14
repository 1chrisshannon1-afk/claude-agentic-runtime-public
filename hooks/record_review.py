#!/usr/bin/env python3
"""record_review — record that the current git HEAD of the cwd repo has been
covered by an Opus code-review, so the review/task-completion gate stops flagging
it.

Ported faithfully from the proven bash implementation
``~/.claude/scripts/mark_reviewed.sh``, then extended to be OUTCOME-AWARE: the
ledger now optionally carries whether that review found unresolved
BLOCKER-severity findings, not just the bare fact that *a* review happened.

Behavior (spec):
  * Resolve the repo root and HEAD sha of the target working directory.
  * Append a line to ``~/.claude/.review_state/last_reviewed``:
      - ``"<repo_root> <sha>"``                 — outcome unspecified/unknown
        (the ORIGINAL two-field format; every pre-existing line on disk, and
        every caller that doesn't pass outcome info, stays exactly this shape —
        byte-for-byte backward compatible).
      - ``"<repo_root> <sha> clean"``            — the review found NO
        unresolved blockers.
      - ``"<repo_root> <sha> blockers:<n>"``     — the review found `n`
        unresolved blocker-severity findings.
    The review/task-completion gate's existing ``"<repo_root> <sha>"``
    substring match still finds ALL three shapes (the needle is always a
    prefix), so nothing that only cares about "was this HEAD reviewed at all"
    needs to change.
  * Outcome is supplied by the caller, NEVER guessed:
      - CLI flags ``--clean`` / ``--blockers <n>`` / ``--blockers=<n>``, or
      - the SAME piped-JSON stdin payload already used to supply ``cwd`` in the
        documented invocation (``echo '{"cwd":"...", "blockers": 2}' |
        record_review.py`` / ``{"cwd":"...", "clean": true}``) — this mirrors
        how this script is actually invoked in practice today (see
        ``~/.claude/scripts/enforcement_doctor.sh`` and the operator runbook),
        so a caller need not learn a new flag on top of the existing
        `echo '{"cwd":...}' | record_review.py` convention.
    CLI flags win when both are present. Passing NEITHER means "outcome
    unknown" — this is the default and is NEVER silently upgraded to "clean".
  * Idempotent AND outcome-aware: recording the SAME outcome twice for the same
    HEAD is a no-op (``already``). Recording a DIFFERENT outcome for a HEAD
    already on record (e.g. a re-review after fixes now reports clean, or a
    plain unspecified call following a known outcome) UPDATES the ledger's
    entry for that HEAD in place rather than duplicating it or silently no-op'ing
    — EXCEPT an unspecified (unknown) outcome never overwrites an existing
    KNOWN outcome (clean/blockers), so a naive re-run can't downgrade a good
    signal to "unknown".
  * Create the state dir with ``mkdir -p`` and ``chmod 0700``.
  * LOG-ONLY (enforcement OFF: none of ``CSA_ENFORCE=1``, ``~/.claude/.enforce`` or a
    per-repo ``.claude/.csa-enforce`` marker): nothing is written, so any request that
    would write prints ``record_review: NOT recorded (log-only mode: set CSA_ENFORCE=1 or
    create ~/.claude/.enforce)`` to stderr and exits 1, never the "recorded review of
    HEAD ..." confirmation. The wording is ``NOT updated`` for an in-place outcome update
    and ``NOT corrected`` for ``--correct-identity``; ``--battery`` uses ``NOT recorded``.
    The decision is still logged (``would-record`` / ``would-update`` /
    ``battery-would-record`` / ``would-correct-identity``) and the ledger is untouched.
    An already-recorded HEAD (``already``) and the no-op statuses below skipped no
    write and still exit 0.
  * No-op (message, exit 0) when the target is not a directory, not a git repo,
    or has no HEAD commit yet.

  * ``--rekey <prior-precommit-key>`` (AA-0064, 2026-09-01, gate-optimization
    plan waste-elimination P3): carries a PRIOR review's CLEAN outcome
    forward to the CURRENT pending digest, but ONLY when the current pending
    content for ``--paths`` reproduces the prior key's exact byte content —
    proven via SHA256 equality against a reconstruction that treats every
    currently-newly-added path as if it were still untracked (see
    ``precommit_review_gate.rekey_digest_if_only_untracked_became_staged``,
    reused verbatim, never forked). This is the mechanical fix for gate 3b
    re-firing after an already-clean review purely because staging a
    previously-untracked file moved the digest (see
    ``reference_precommit_digest_after_staging.md``) — a workaround that
    existed only as manual prose before this flag. Refuses loudly (nothing
    recorded) on ANY of: the prior key is not `precommit:<16-hex>`-shaped,
    no `--paths` supplied, the prior key has no review on record at all, the
    prior review's outcome was not clean, or the reconstruction does not
    reproduce the prior digest exactly (a real content difference). Requires
    ``--paths``; mutually exclusive with ``--pre-commit`` and with
    ``--clean``/``--blockers`` (Item 18, 2026-09-01 fix round — --rekey
    always carries forward the PRIOR review's clean outcome by construction,
    never a caller-declared one). Refuses (Item 5) when the prior entry's
    outcome is UNKNOWN (bare, no --clean/--blockers ever recorded) — only a
    prior CLEAN carries forward. Refuses (BLOCKER 1, 2026-09-01 fix round)
    when the TARGET digest already has ANY existing entry on record — a
    rekey is only meaningful for a digest with no record at all; without
    this, a target digest already carrying, say, an unresolved
    ``blockers:3`` would be silently overwritten by ``decide()``'s own
    STATUS_UPDATE path. Refuses (BLOCKER 2, 2026-09-01 fix round) when any
    newly-staged path's git file mode is not a plain regular file
    (``100644``) — an executable bit or a symlink is a real content
    difference the byte-only reconstruction cannot see (see
    ``precommit_review_gate._added_path_new_modes``). Carries the prior
    entry's ``reviewer=``/``model=`` identity forward (Item 8) unless the
    caller explicitly supplies its own, and always adds a ``rekey=<prior-
    key>`` provenance field so an audit (``audit_review_attribution.py``)
    can tell a sanctioned mechanical carry-forward apart from an
    unattributed clean.

    **DIRECTORY, GLOB, AND PATHSPEC-MAGIC ENTRIES RECONSTRUCT CORRECTLY
    (GH #5886, fixed across four review rounds).** An earlier version of this
    note called the file-pathspec-only behavior a deliberate, unfixed
    limitation; that was never a design choice — it was real defects, fixed
    across rounds 1-2 in
    ``precommit_review_gate.reconstruct_pending_diff_assuming_untracked``:
    membership for BOTH the tracked-diff exclusion and the untracked-re-add
    half is decided entirely by GIT's own pathspec matching (``git diff HEAD
    -- ... :(exclude,literal)<path>`` for the exclusion, ``git ls-files
    --others``/``diff --name-status`` for the re-add), never a Python
    approximation of either. A ``--paths`` entry naming a DIRECTORY, a git
    glob (``src/*.py``), or pathspec magic (``:(top)file.py``) all
    reconstruct correctly now, exactly like a plain file path.

    **THE BYTE-IDENTICAL SHA256 CHECK ALONE IS NOT THE SAFETY BOUNDARY (fix
    round 3, sharpened round 4) — an earlier version of this docstring
    called it that, and that was inaccurate even at the time it was
    written.** The actual safety boundary is FIVE things together: the
    SHA256 byte-identity equality, the plain-regular-file (``100644``) mode
    check, a LOSSLESS-MATERIAL check
    (``precommit_review_gate.rekey_digest_if_only_untracked_became_staged``'s
    ``lossy_sink`` mechanism) that refuses outright when the untracked-
    material formatter hit invalid UTF-8, a per-file/aggregate read cap, the
    file-count cap, or an unreadable name — regardless of whether the raw
    digest happens to match — a CONTROL-CHARACTER-SAFE RENDERING
    (``precommit_review_gate._digest_safe_name``, R6-B1, see below) that
    makes a name containing a control character digest UNAMBIGUOUSLY, and a
    DIGEST-FORMAT VERSION CHECK (the ledger's ``dg=`` field, R7-B1, see
    below). **Corrected 2026-09-24 (fix-round-4, R7-B2): an earlier version
    of this paragraph said a control-character name was one of the things
    the ``lossy_sink`` mechanism "refuses outright" on. That is FALSE — a
    control-character name is never added to ``lossy_sink`` at all. It is
    ESCAPED (rendered as a ``\0``-prefixed JSON string via
    ``_digest_safe_name``) instead, which is what removes the ambiguity in
    the first place; nothing about an escaped name is refused on its own.**
    A digest match against LOSSY or AMBIGUOUS material proves nothing on its
    own; fix-round-4 (R6-B1, cold trust-architect review) live-reproduced a
    filename containing its own literal newline plus a fabricated
    ``--- untracked <name>`` fragment reconstructing byte-for-byte
    identically to two separate, genuinely different real files, one of
    them carrying a smuggled shell payload, landed via --rekey and gate 3b —
    the ``_digest_safe_name`` fix closed this for any digest computed AFTER
    it landed; fix-round-4 (R7-B1, cold trust-architect review) then found a
    review recorded BEFORE it existed could still be --rekey'd onto the
    identical exploit, closed by the ``dg=2`` check below.

    **A REKEY CHAIN ROOT MUST CARRY A CURRENT-FORMAT DIGEST (fix round 4,
    R7-B1, cold trust-architect review).** The control-character-safe
    rendering fix above only changes digests computed AFTER it landed — a
    review recorded BEFORE it existed used the OLD, vulnerable rendering,
    and --rekey could still be pointed at that old digest and exploited the
    identical way (live-reproduced end to end: a single oddly-named
    reviewed directory entry, rekeyed onto two ordinary staged files, one
    smuggling a shell payload). Every NEW ``--pre-commit``/``--rekey``
    ledger entry now stamps a digest-format version field, ``dg=2``
    (``_DIGEST_FORMAT_VERSION``); ``--rekey`` refuses outright unless the
    chain's ROOT entry (the true root, after the one-hop resolution above)
    already carries ``dg=2`` — an entry with no ``dg=`` field at all (every
    entry recorded before this fix existed, by construction) refuses,
    fail-closed, exactly like the lossy-material refusals above. See
    ``_entry_suffix``'s own docstring for the field's full contract.

    Individual file paths remain the RECOMMENDED shape for both the original
    review and any later --rekey attempt, because a directory (or glob)
    commonly sweeps in files beyond the ones reviewed together, which makes
    a --rekey attempt refuse for an unrelated reason far more often than a
    single-file pathspec would — a usability preference now, not a
    structural limitation. Gate 3b's own hint (``precommit_review_gate.
    decide``) still does not suggest --rekey when any current path resolves
    to a directory, for exactly that usability reason (not because the
    command cannot succeed).

    **--PRE-COMMIT AND --REKEY BOTH REFUSE WHEN A GIT_*_PATHSPECS ENV VAR IS
    SET (fix round 4, R6-B2 — replacing a fix-round-3 attempt that STRIPPED
    these vars from the gate's own git calls, which a cold review found was
    a REGRESSION against HEAD, live-reproduced with an ambient var making
    HEAD deny a commit the stripped version wrongly allowed).** Before
    computing or reconstructing anything, both modes check
    ``precommit_review_gate.pathspec_env_vars_present()`` and refuse loudly
    (nothing recorded) the moment any of GIT_LITERAL_PATHSPECS/
    GIT_GLOB_PATHSPECS/GIT_NOGLOB_PATHSPECS/GIT_ICASE_PATHSPECS is present —
    each changes how git itself interprets a pathspec, so neither this
    module's own git calls nor the real ``git commit`` can be trusted to
    agree on what "this content" means while one is set. Not closed by this
    check, tracked on #5892: any var the gated command
    itself sets (an inline ``VAR=value`` prefix, or an
    ``export``/``env``/``set -a`` in the same or an earlier Bash-tool
    shell) -- it reaches the real git invocation without ever appearing in
    this process's own environment, the git CLI's own
    ``--literal-pathspecs``/``--glob-pathspecs``/``--noglob-pathspecs``/
    ``--icase-pathspecs`` options, or ``--work-tree``/``--git-dir``
    redirecting which repository the real commit acts on.

Design contract (shared with the rest of the hook system):
  * A PURE decision function, :func:`decide`, does all reasoning and returns a
    :class:`Decision`. It performs the read-only git resolution AND the
    read-only ledger lookup but NO writes and NO logging, so it is trivial to
    cover.
  * A thin :func:`main` reads the event, resolves the outcome (CLI > event
    payload > unspecified), calls :func:`decide`, performs the side effect
    (writing/updating the ledger) only when :func:`_lib.enforcing` is ON
    (LOG-ONLY otherwise), logs the decision, and exits 0 -- EXCEPT that a write
    request (record, update, ``--pre-commit``/``--rekey``, ``--battery``,
    ``--correct-identity``) skipped because LOG-ONLY exits 1 with a ``NOT recorded``
    (``NOT updated`` / ``NOT corrected``) line on stderr: nothing was written, so the
    caller must not be told "recorded". The gate will deny this content once
    enforcement is on, or wherever the gate runs enforcing.
  * The master OFF switch ``CSA_DISABLE_HOOKS=1`` short-circuits to a clean no-op.
  * Recording is never a deny/block: this module never emits a PreToolUse deny or
    a Stop block. It only records and logs.

This module never raises out to its caller: a crashing hook must not break the
agent. Every failure degrades to a clean exit 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import NamedTuple

# Import the shared hook library. When run as a hook (cwd arbitrary) the hooks
# dir must be importable; add it to sys.path before importing.
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import agent_budget as ab  # noqa: E402  (reuse the proven admission_lock primitive)
import review_risk_tier as rrt  # noqa: E402  (pure classifier, no import-cycle risk)

HOOK = "record_review"

# Tail of the stderr line main() prints (with exit 1) when a write was requested
# but enforcement is OFF, so nothing was written. Without it the tool printed
# "recorded review of HEAD ..." although nothing had been recorded, and a stranger
# could not tell why the gate would deny this content once enforcement is on (or
# wherever the gate runs enforcing).
_LOG_ONLY_HINT = "(log-only mode: set CSA_ENFORCE=1 or create ~/.claude/.enforce)"

# Decision status codes returned by decide(). RECORD/UPDATE carry a writable
# ledger line; ALREADY and the no-op statuses do not.
STATUS_RECORD = "record"  # a fresh HEAD to append to last_reviewed
STATUS_ALREADY = "already"  # HEAD already recorded with this SAME outcome (idempotent no-op)
STATUS_UPDATE = "update"  # HEAD already recorded, but with a DIFFERENT outcome -> update in place
STATUS_NOT_DIR = "not-a-dir"  # target is not a directory
STATUS_NOT_REPO = "not-a-repo"  # target is not inside a git repo
STATUS_NO_HEAD = "no-head"  # repo has no HEAD commit yet

# Review OUTCOME — what a recorded review found, independent of the STATUS_*
# ledger-write outcome above. OUTCOME_UNKNOWN is the default for every caller
# that supplies no outcome info (old callers, or a fresh call with no --clean /
# --blockers / event field) and is NEVER upgraded to "clean" implicitly.
OUTCOME_CLEAN = "clean"  # no unresolved blocker-severity findings
OUTCOME_BLOCKERS = "blockers"  # N unresolved blocker-severity findings on record
OUTCOME_UNKNOWN = "unknown"  # no outcome info was ever supplied for this HEAD

# TIER_UNKNOWN mirrors OUTCOME_UNKNOWN's precedent for the NEW ledger fields
# added 2026-08-30 (gate-optimization plan, Item 6): a field simply absent
# from a ledger line (every pre-existing line, and any new line a caller
# chose not to supply this field for) reads as UNKNOWN, never silently
# defaulted to a real value like "moderate" -- see field_tier /
# parse_ledger_fields below.
TIER_UNKNOWN = "unknown"

# GH #5886 fix-round-4, R7-B1: the digest-format VERSION stamped (as `` dg=``,
# see `_entry_suffix`) on every NEW `--pre-commit`/`--rekey` ledger entry.
# "2" names `precommit_review_gate._digest_safe_name`'s control-character-safe
# untracked-material rendering (R6-B1) -- the CURRENT format. Bumping this
# constant is how any FUTURE digest-format change (one that alters what bytes
# go into the SHA256, the way R6-B1 did) makes itself visible to `--rekey`'s
# own "is this chain root safe to build on" check without a second bespoke
# marker field being invented each time. There is no "1" written anywhere
# on purpose -- a pre-R6-B1 entry simply has no `dg=` field at all, which
# `main()`'s `--rekey` branch treats identically to "not the current format,
# refuse" (see that branch's own comments).
#
# GH #5923 changed the digest bytes for two input classes without a bump:
# non-UTF-8 content (now followed by a raw-byte digest marker) and untracked
# names text mode used to mangle (CR- or non-UTF-8-bearing, now read as bytes).
# This is NOT an addition-only change: a crafted pre-#5923 entry for one of
# those inputs can still collide with a post-#5923 key for different content
# (demonstrated in the #5923 trust review). The version stays "2" because
# `--rekey` refuses exactly those inputs via `lossy_sink`, and the old
# renderings of them were already lossy and never proved byte identity -- not
# because a collision is impossible. The gate's main lookup never reads `dg=`,
# so a bump would not narrow that residual either.
_DIGEST_FORMAT_VERSION = "2"

# Synthetic ledger-line namespace for mutation-battery run results (Item 6,
# gate-optimization plan §2/§7). Deliberately NOT "precommit:" -- this line
# carries no repo_root/digest key at all (it isn't gating a specific
# commit), so it must never collide with, or be misparsed as, a precommit:
# entry. A real repo_root is always an absolute filesystem path and can
# never equal this literal string, so precommit_review_gate.decide()'s
# needle-based lookup (``"<repo_root> <head>"``) structurally never matches
# a battery: line -- proven directly in hooks/tests/test_record_review.py.
BATTERY_PREFIX = "battery:"


class ArgvError(Exception):
    """A loudly-rejected CLI argv shape (2026-08-30, gate-optimization plan
    Item 6, PART A root-cause fix): an unrecognized ``--``-prefixed flag, an
    implausible positional target, or a recognized flag whose VALUE fails
    validation (--model, --round, --vf, --battery's --mut/--stale).

    Before this existed, ``_positional_target`` silently resolved any of
    these shapes to a bogus "target directory", ``decide()`` correctly
    rejected it as STATUS_NOT_DIR, and the whole call quietly recorded
    nothing while exiting 0 — indistinguishable, from the calling agent's
    side, from a real success. This was already happening live (114 calls
    in the enforcement log: 106 ``--help``, 3 other unrecognized flags, 5
    sha/path-shaped mistargets — every one recording nothing). This is
    raised LOUDLY for every one of those shapes instead, and caught in
    exactly one place, ``main()`` — the module's long-standing "never
    raises out to its caller" contract still holds; this exception never
    escapes ``main()``.
    """


# The SINGLE source of truth for every CLI flag this script recognizes --
# reused by BOTH _positional_target's unrecognized-flag rejection AND its
# own value-skipping logic. A flag registered in one but not the other is
# exactly how the original silent-no-op bug happened: a token this module
# doesn't know how to skip gets mistaken for the positional target. Arity:
#   0          -- a bare switch, no value.
#   1          -- exactly one value, "--flag value" or "--flag=value" form.
#   "variadic" -- swallows every following token up to the next recognized
#                 flag (only --paths today).
_ARITY_ZERO = 0
_ARITY_ONE = 1
_ARITY_VARIADIC = "variadic"

_RECOGNIZED_FLAGS: dict[str, object] = {
    "--clean": _ARITY_ZERO,
    "--pre-commit": _ARITY_ZERO,
    "--battery": _ARITY_ZERO,
    "--warm": _ARITY_ZERO,
    "--blockers": _ARITY_ONE,
    "--item": _ARITY_ONE,
    "--tier": _ARITY_ONE,
    "--model": _ARITY_ONE,
    "--reviewer": _ARITY_ONE,
    "--reviewer-agent-id": _ARITY_ONE,
    "--reviewer-tool-use-id": _ARITY_ONE,
    "--round": _ARITY_ONE,
    "--prev": _ARITY_ONE,
    "--vf": _ARITY_ONE,
    "--mut": _ARITY_ONE,
    "--stale": _ARITY_ONE,
    "--rekey": _ARITY_ONE,
    "--correct-identity": _ARITY_ONE,
    "--paths": _ARITY_VARIADIC,
}

# model= must be one of the runtime's three sanctioned model tiers
# (model_policy.json's own vocabulary) -- never a free-text value a future
# ledger reader would have to normalize or guess at.
_VALID_MODELS = frozenset({"opus", "sonnet", "haiku"})

# vf='s exact verdict-token set (verify_fix.py's contract, item 6c) --
# never paraphrased, never widened ad hoc.
_VALID_VF_TOKENS = frozenset({
    "PROVEN",
    "PARTIAL",
    "FALSE_ALLCLEAR",
    "CLAIM_FALSE",
    "ERROR",
    "NOTHING_TO_FALSIFY",
    "STALE_BUNDLE",
})

# --prev's closed shape (2026-08-31, build-wave Lane B / AA-0049; digest
# width fixed in the same-day fix round after the reviewer reproduced
# "precommit:29" passing the original, too-loose `[0-9a-f]+` shape
# end-to-end): a chain predecessor is EITHER a pre-commit content digest
# ("precommit:<16-hex-digit>" -- FIXED WIDTH, matching
# precommit_review_gate._DIGEST_LEN/digest_of, the only thing
# --pre-commit's own head_override ever produces) or a legacy plain-HEAD
# sha-keyed entry ("sha:<7-40-hex-digit>", a git abbreviated-to-full sha) --
# never free text and never an off-width hex run. Before this existed
# record_review accepted ANY string as --prev (only rejecting one that
# LOOKED like a flag name), so a truncated/malformed value -- the REAL live
# ledger corruption AA-0049 found is `prev=precommit:29` and
# `prev=precommit:0a` (2-hex-digit truncations of a real 16-digit digest;
# an earlier draft of this comment cited "ommit:29", a `grep -o` artifact
# that dropped the "precommit:" prefix outright -- corrected here to the
# actual stored value) -- was written verbatim and could never match a
# real chain link again. A width-UNBOUNDED `[0-9a-f]+` (this constant's
# original shape) still accepted `precommit:29` outright, since "29" is
# itself valid (if short) hex -- reproduced live by the round-2 reviewer;
# the fix is the WIDTH constraint, not merely "is it hex".
_PREV_RE = re.compile(r"^(precommit:[0-9a-f]{16}|sha:[0-9a-f]{7,40})$")

# --rekey's closed shape (AA-0064, 2026-09-01 waste-elimination P3): a
# rekey source is ALWAYS a pre-commit content-keyed entry, never a legacy
# plain-HEAD sha (a sha-keyed entry has no "content this exact diff would
# land" digest to reconstruct against at all -- see precommit_review_gate's
# `rekey_digest_if_only_untracked_became_staged`, which operates purely on
# the 16-hex digest half of a `precommit:` key). Fixed width, mirroring
# `_PREV_RE`'s own AA-0049 fix (a truncated digest must never validate).
_REKEY_RE = re.compile(r"^precommit:[0-9a-f]{16}$")

# Consecutive-warm-round cap (CLAUDE.md §10's warm-round paragraph): a full
# review round may be continued warm for at most TWO consecutive rounds on
# one prev=-linked chain before the NEXT full round must be a COLD dispatch
# (reviewer independence backstop). "2 consecutive warm" caps at the THIRD
# would-be-warm round in a row -- i.e. the walk below refuses once it finds
# 2 PRIOR consecutive warm=1 entries in the prev= chain leading to this one.
_MAX_CONSECUTIVE_WARM_ROUNDS = 2

# ---------------------------------------------------------------------------
# WS2.3 (master plan §2.3, "Review-round ceiling + clock") -- REVIEW-ROUND
# CEILING, LOG-ONLY (2026-09-21).
#
# What the operator remembered as "three rounds" is the 3-strike rule
# (CLAUDE.md §11). This is the mechanical review-round ceiling that rule was
# never actually backed by: nothing anywhere counted, or capped, how many
# times one boundary's fix-and-re-review loop could run before this landed.
#
# THIS LANDING IS LOG-ONLY. The master plan's own §2.3 mandates a 7-day
# would-refuse observation window before any enforcement: every call this
# module makes below to `derive_review_round()` / the tripwire-boundary
# check below WRITES its normal ledger entry exactly as before and ONLY
# LOGS what a future enforcing version would have refused
# (`round-tripwire`/`round-cap-would-refuse` -- see `main()`'s pre-commit
# branch). Nothing is ever denied by this constant. Refusal is a SEPARATE,
# LATER commit, gated on a human hand-check of that window's log lines
# (master plan §2.3: "enforcement lands only if >=90% are true same-boundary
# chains AND none arose solely from a shared hot file").
#
# THE ROUND IS DERIVED, NOT DECLARED (see `derive_review_round()` below): a
# caller's own `--round` binds almost nothing -- a self-declared round=/prev=
# pair on an otherwise-independent CLI invocation cannot be trusted any more
# than a self-declared `--tier`/`--model` could (this mirrors those two
# fields' own "always computed, caller value is audit-only" precedent
# exactly). The recorder walks repo R's OWN ledger history for entries whose
# `paths=` OVERLAP this call's `--paths` (via `file_claims.paths_overlap`,
# reused verbatim -- never a second comparison), stopping at the latest
# `--clean` covering them; `derived_round = (count of --blockers entries
# found in that walk) + 1`. THE DERIVED VALUE ALWAYS GOVERNS -- a declared
# `--round` that disagrees is logged (`round-mismatch`) but never trusted
# over the walk, and NO record is ever refused merely for a missing
# `--round` (round= was on only ~37% of real ledger lines when this was
# written, and no documented recipe passes it for round 1 -- requiring it
# would deny most commits, which is not what this change does).
_ROUND_TRIPWIRE = 3  # round >= this: a --strategy-change would eventually be required
_MAX_TOTAL_ROUNDS = 5  # round > this (i.e. round 6+): a total-round-cap refusal would eventually fire

# KNOWN, ACCEPTED GAP (stated here per the task's own requirement, never
# left silent -- mirrored in docs/subsystems/review-ladder.md): this v1 does
# NOT follow a rename across the chain via `git diff --find-renames`. The
# walk below matches ledger entries purely on their own `paths=` telemetry
# field (the literal path strings a PRIOR recording call was invoked with),
# never on file content or a renamed path's post-rename identity. A file
# renamed mid-chain (e.g. reviewed at round 2 as `old_name.py`, blockers
# found, the fix renames it to `new_name.py`, then re-reviewed at
# `new_name.py`) breaks the `paths=` overlap the walk relies on to find its
# predecessor entries, so the chain is NOT continued across the rename --
# the round count UNDERCOUNTS (a rename mid-chain silently starts what this
# function sees as a fresh chain at round 1, even though it is really a
# continuation). This is a deliberate, accepted v1 limitation, not an
# oversight: implementing real rename-following would require re-deriving
# path history via `git diff --find-renames` against every historical
# ledger entry's own commit context, which this ledger's flat, digest-keyed
# text format does not carry. Follow-up, not built here.


class Decision(NamedTuple):
    """The pure outcome of evaluating a target directory (+ optional outcome).

    Attributes:
        status: one of the STATUS_* constants.
        message: the human-facing confirmation / no-op line (mirrors the bash
            ``printf`` output, verbatim in spirit).
        repo_root: resolved repo toplevel, or "" when unresolved.
        head: full HEAD sha, or "" when unresolved.
        entry: the exact ledger line to write when status is STATUS_RECORD or
            STATUS_UPDATE (``"<repo_root> <sha>"`` when the outcome is
            unspecified, else with a trailing `` clean``/`` blockers:<n>``
            suffix); the bare ``"<repo_root> <sha>"`` needle (no write implied)
            for every other status.
        outcome: the raw outcome TOKEN now on record for this HEAD ("" for
            unspecified/unknown, else "clean" or "blockers:<n>") — what a
            caller like churn_tracker should treat as "the latest known
            outcome" after this decision resolves (task_completion_gate was
            once such a caller too; RETIRED 2026-08-20, no longer invoked).
    """

    status: str
    message: str
    repo_root: str = ""
    head: str = ""
    entry: str = ""
    outcome: str = ""


def lock_timeout_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_LOCK_TIMEOUT_SEC (admission-lock max wait, default 2.0) —
    mirrors file_claims.lock_timeout_from_env / churn_tracker.lock_timeout_from_env
    exactly (the same shared env var, same wrapper-per-module convention)."""
    env = os.environ if environ is None else environ
    return ab.lock_timeout_from_env(env)


def _git(target: str, *args: str) -> str:
    """Run ``git -C target <args>`` read-only and return trimmed stdout.

    Returns "" on ANY failure (non-repo, missing git, non-zero exit, timeout).
    Never raises. Network is impossible: only local plumbing verbs are used, and
    the environment disables any credential/terminal prompt.
    """
    try:
        env = dict(os.environ)
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        proc = subprocess.run(
            ["git", "-C", target, *args],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _existing_outcome_token(last_reviewed_path: str, repo_root: str, head: str) -> str | None:
    """The raw outcome suffix already on record for repo_root+head, or None.

    Returns:
      None — this exact HEAD has NO ledger entry at all yet.
      ""   — an entry exists in the OLD bare ``"<repo_root> <sha>"`` form (no
             outcome info: a legacy line, or a prior call with no outcome).
      str  — the raw token text after the entry (e.g. "clean", "blockers:3",
             or any other trailing text a future/foreign writer left there —
             parse_outcome_token() treats anything it doesn't recognize as
             OUTCOME_UNKNOWN, so this never crashes on unexpected content).

    A line counts as "for repo_root+head" when it is EXACTLY the needle
    ``"<repo_root> <sha>"``, or starts with the needle followed by a single
    space (the outcome-suffix grammar this module writes). This is at least as
    strict as the original whole-line-exact-match idempotency guard it
    replaces, plus the new suffixed form. When several lines match (a legacy
    ledger could have duplicates from before this module de-duplicated by
    updating in place), the LAST matching line wins — "last recorded" wins,
    matching decide()'s own idempotency semantics. Never raises: any read
    failure degrades to None (fail toward re-recording, harmless).
    """
    needle = f"{repo_root} {head}"
    found: str | None = None
    try:
        if not os.path.isfile(last_reviewed_path):
            return None
        with open(last_reviewed_path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                if line == needle:
                    found = ""
                elif line.startswith(needle + " "):
                    found = line[len(needle) + 1 :]
    except Exception:
        return None
    return found


def parse_outcome_token(token: str | None) -> tuple[str, int]:
    """Parse a raw ledger outcome token into (status, blocker_count).

    status is one of OUTCOME_CLEAN / OUTCOME_BLOCKERS / OUTCOME_UNKNOWN. None,
    the empty string (the legacy/unspecified line shape), or any unrecognized
    token all map to (OUTCOME_UNKNOWN, 0) rather than raising or guessing.
    """
    if not token:
        return (OUTCOME_UNKNOWN, 0)
    # 2026-08-23 (#4400): entries may carry appended telemetry fields after the
    # outcome token ("clean ts=... item=..."). The outcome is ALWAYS the first
    # whitespace token; trailing fields are ignored here so legacy readers and
    # gate 3b keep resolving outcomes identically for old and new lines. A
    # whitespace-only suffix must degrade to UNKNOWN, never raise (this feeds
    # gate 3b — a crash here would fail that gate silently open).
    parts = token.split()
    token = parts[0] if parts else ""
    if not token:
        return (OUTCOME_UNKNOWN, 0)
    if token == "clean":
        return (OUTCOME_CLEAN, 0)
    if token.startswith("blockers:"):
        try:
            n = int(token[len("blockers:") :])
        except Exception:
            return (OUTCOME_UNKNOWN, 0)
        return (OUTCOME_BLOCKERS, n) if n > 0 else (OUTCOME_UNKNOWN, 0)
    return (OUTCOME_UNKNOWN, 0)


def head_review_outcome(last_reviewed_path: str, repo_root: str, head: str) -> tuple[str, int] | None:
    """The LAST recorded review outcome for repo_root+head, or None.

    None means this exact HEAD has no ledger entry at all (never reviewed /
    recorded). Otherwise returns (OUTCOME_CLEAN|OUTCOME_BLOCKERS|OUTCOME_UNKNOWN,
    blocker_count). This is the SHARED outcome-aware read other hook modules
    build on: churn_tracker uses it to detect a clean review that resets a
    path's churn count (task_completion_gate once used it to differentiate
    its Stop-gate message from a bare "reviewed"; RETIRED 2026-08-20, no
    longer a live caller). Never raises.
    """
    token = _existing_outcome_token(last_reviewed_path, repo_root, head)
    if token is None:
        return None
    return parse_outcome_token(token if token else None)


def parse_ledger_fields(raw_token: str | None) -> dict[str, str]:
    """Parse the trailing ``k=v`` telemetry fields off a raw ledger outcome
    token -- the SAME string `_existing_outcome_token` returns, e.g.
    ``"clean ts=... tier=high reviewer=trust-architect"``.

    The outcome token itself (`parts[0]`, e.g. "clean"/"blockers:2") is
    intentionally EXCLUDED from the returned dict -- callers wanting the
    outcome use `parse_outcome_token`/`head_review_outcome`, exactly as
    before this function existed. Missing/empty/malformed input -> {} (an
    empty dict), NEVER a fabricated key: read a field with
    ``.get("tier", TIER_UNKNOWN)`` (or the field's own UNKNOWN-style
    sentinel) so an ABSENT field always resolves to an explicit "unknown",
    matching `parse_outcome_token`'s own `OUTCOME_UNKNOWN` precedent --
    never silently defaulted to a guessed real value (e.g. a missing tier=
    must never read as "moderate"). Never raises.
    """
    fields: dict[str, str] = {}
    if not raw_token:
        return fields
    try:
        parts = raw_token.split()
        for tok in parts[1:]:  # parts[0] is the outcome token; skip it
            if "=" in tok:
                k, _, v = tok.partition("=")
                if k:
                    fields[k] = v
    except Exception:
        return {}
    return fields


def _rebuild_corrected_token(
    raw_token: str | None,
    new_reviewer_encoded: str,
    corrects_from_encoded: str,
    corrected_at: str | None = None,
    *,
    model_replacements: dict[str, str | None] | None = None,
) -> str:
    """Rebuild a corrected ledger outcome+telemetry token from `raw_token`
    (the EXACT string `_existing_outcome_token` returned for the entry being
    corrected), swapping ONLY the `reviewer=<...>` field's value and
    setting `corrects_from=<...>` (+ `corrected_at=<...>` when supplied) --
    every other token (the outcome word itself, `ts=`, `tier=`,
    `paths=`/`paths_n=`, `round=`, `prev=`, `vf=`, `warm=`, `rekey=`,
    `item=`, any future field this function does not know about) is carried
    forward BYTE-FOR-BYTE, split/rejoined on whitespace only -- never
    re-derived through any field's own writer (`_paths_field`,
    `_entry_suffix`, etc.), which could silently change a value that
    round-trips through re-parsing (e.g. `paths_n=` recomputed from a
    `paths=` field already truncated at `_MAX_PATHS_IN_FIELD` would silently
    drop the original overflow count). This is what guarantees
    `--correct-identity` NEVER touches outcome/paths/digest/round/prev/vf/
    tier/warm/rekey/**ts=** -- #5133 requirement (b) -- at the byte
    level, not just "as far as this module's own field parsers understand
    the value." `ts=` in particular is NEVER touched even when
    `corrected_at` is supplied -- see that parameter's own note below for
    why a correction needs a SIBLING field rather than mutating `ts=`.

    `new_reviewer_encoded`/`corrects_from_encoded` are assumed ALREADY
    sanitized by the caller (mirrors every other call site in this module --
    sanitization happens once, at the point a caller-supplied value first
    enters the ledger). A pre-existing `reviewer=` token is replaced in
    place (preserving its original position in the field order); when none
    existed, `reviewer=` is appended at the end, matching `_entry_suffix`'s
    own append-only field-ordering convention for a field that was absent
    before.

    `corrects_from=`/`corrected_at=` are each replaced IN PLACE when a
    token of that name already exists on `raw_token` (F5, 2026-09-09 fix
    round: correcting an ALREADY-corrected line used to blindly append a
    SECOND `corrects_from=` token, and `parse_ledger_fields`'s last-wins
    parsing then silently dropped the first from every consumer's view --
    not lost from the RAW line, which still carries it for anyone reading
    byte-for-byte, but invisible to every structured reader, defeating the
    whole point of an auditable trail). Replacing in place instead means
    the ledger only ever shows the IMMEDIATELY PRIOR reviewer= value as
    `corrects_from=` -- the full multi-hop chain stays reconstructable by
    walking the ledger's own successive lines for this key (each earlier
    line is still ON DISK, just not the `corrects_from=` value of the
    LATEST line), exactly how `superseded`/last-wins already works for
    every other field. When no `corrects_from=`/`corrected_at=` token
    existed yet (the first correction of a line), both are appended at the
    end, matching `_entry_suffix`'s own append-only ordering convention for
    a field introduced for the first time.

    `model_replacements` (2026-09-20, master plan WS2.4 step 1): an OPTIONAL
    dict of `{"model": ..., "model_source": ..., "model_id": ...,
    "model_declared": ...}` (any subset; a key mapped to None REMOVES that
    field from the corrected line rather than leaving a stale value behind)
    -- when a `--correct-identity` call supplies a corrected
    `--reviewer-tool-use-id`, the model= field is genuinely a DIFFERENT
    dispatch's data now (a different tool_use_id can legitimately join to a
    different model), so it must be RE-DERIVED and REPLACED, not carried
    forward byte-for-byte like every other field this function otherwise
    protects. `model_declared=` is ALWAYS cleared (mapped to None) by
    BOTH branches of `main()`'s `--correct-identity` re-derivation block --
    `--model` is already refused outright alongside `--correct-identity`
    (see `_CORRECT_IDENTITY_INERT_FLAGS`), so a correction never carries a
    fresh caller declaration, and the OLD entry's `model_declared=` (from
    whatever the ORIGINAL review happened to declare) is never still-true
    of the corrected identity either -- REGRESSION (finding 2, 2026-09-20
    fix round): leaving it untouched let a bare-`--reviewer`-type
    correction show a stale `model_declared=` as its only model signal, and
    let a correction whose re-derived model happened to equal the old
    declaration write `model=X model_declared=X`, violating this field's
    own "only when it disagreed" invariant. `model=` is deliberately NOT in
    the byte-fidelity list above (#5133 requirement (b) protects
    outcome/paths/digest/round/prev/vf/tier/warm/rekey/ts= -- reviewer-
    identity-adjacent fields, model=/model_declared= included, are exactly
    what a correction exists to fix). None (the default) means "leave
    model=/model_source=/model_id=/model_declared= exactly as they were" --
    every pre-existing call site of this function passes nothing here and
    is completely unaffected.

    `corrected_at` (BLOCKER 2, 2026-09-09 fix round) is the UTC ISO8601
    timestamp of THIS correction, as a field SIBLING to `corrects_from=` --
    never a mutation of `ts=`. Before this parameter existed, a correction
    silently inherited the ORIGINAL entry's `ts=` byte-for-byte (the
    byte-for-byte-fidelity guarantee above, applied a little too literally
    by the original implementation): nothing on the ledger recorded WHEN a
    correction actually happened, so `audit_review_attribution.py`'s own
    `--window-seconds` join (and any other `ts=`-keyed consumer) evaluated
    a corrected entry against the ORIGINAL dispatch's timestamp -- e.g. a
    day-8 correction citing a day-1 review's `ts=` would join against
    spend.jsonl rows from day 1, not day 8, silently matching or missing
    against the wrong window. `corrected_at` is OPTIONAL (defaults to None
    -- omitted from the token) so every non-`--correct-identity` call site
    of this function's own byte-preservation contract is completely
    unaffected; the ONLY caller that ever passes it is `main()`'s
    `--correct-identity` branch.

    The outcome WORD itself (`parts[0]` -- `parse_outcome_token`/
    `parse_ledger_fields`'s own boundary between "the outcome" and "the
    trailing fields") is handled explicitly and NEVER folded into a blind
    `.split()`/rejoin of the whole raw token: a truly bare legacy entry
    (`raw_token == ""`, no outcome suffix at all -- see
    `_existing_outcome_token`'s own docstring for this exact shape) has NO
    outcome word to preserve a position for, and blindly `.split()`ing an
    empty string then appending `reviewer=`/`corrects_from=` would put
    `reviewer=...` in POSITION 0 -- exactly where `parse_ledger_fields`
    unconditionally treats `parts[0]` as the outcome token and DISCARDS it
    (it is never scanned for `k=v` fields), silently losing the corrected
    identity for this one shape. Explicitly preserving an EMPTY outcome
    word as its own leading token (rejoined as a literal leading space,
    matching `main()`'s own bare-legacy-line grammar) keeps `parts[0]`
    correctly empty and every trailing field at `parts[1:]`, exactly as a
    real bare line already parses. Never raises: any failure falls back to
    just appending the new fields to the raw token as-is, never silently
    drops the correction (this fallback shares the same theoretical
    position-0 risk, but only for a raw_token shape unexpected enough to
    have thrown in the first place).
    """
    try:
        raw = raw_token or ""
        outcome_word, sep, rest = raw.partition(" ")
        field_parts = rest.split() if sep else []

        def _replace_or_append(prefix: str, new_tok: str) -> None:
            for i, tok in enumerate(field_parts):
                if tok.startswith(prefix):
                    field_parts[i] = new_tok
                    return
            field_parts.append(new_tok)

        def _remove(prefix: str) -> None:
            field_parts[:] = [t for t in field_parts if not t.startswith(prefix)]

        _replace_or_append("reviewer=", f"reviewer={new_reviewer_encoded}")
        _replace_or_append("corrects_from=", f"corrects_from={corrects_from_encoded}")
        if corrected_at:
            _replace_or_append("corrected_at=", f"corrected_at={corrected_at}")
        if model_replacements:
            for field_name in ("model", "model_source", "model_id", "model_declared"):
                if field_name not in model_replacements:
                    continue
                new_val = model_replacements[field_name]
                if new_val:
                    _replace_or_append(f"{field_name}=", f"{field_name}={new_val}")
                else:
                    _remove(f"{field_name}=")
        return outcome_word + " " + " ".join(field_parts)
    except Exception:
        fallback = (
            f"{raw_token or ''} reviewer={new_reviewer_encoded} "
            f"corrects_from={corrects_from_encoded}"
        )
        if corrected_at:
            fallback += f" corrected_at={corrected_at}"
        return fallback


def field_tier(raw_token: str | None) -> str:
    """The `tier=` field for a raw ledger outcome token, or TIER_UNKNOWN
    when absent -- NEVER defaulted to a real tier value. Every ledger line
    written before 2026-08-30 (and any line recorded without --paths, which
    is the only input tier= is ever computed from) has no tier= field at
    all and must read as unknown here, not "moderate".

    KNOWN LIMITATION (FINDING 6, 2026-08-30 review; still applicable
    2026-09-08 under THE ISSUE WHEEL, which absorbed the former nightly
    finishing loop's mechanics verbatim): the unattended THE ISSUE WHEEL
    job's canonical `record_review.py --pre-commit` invocation
    (`issue_wheel.txt`, LANE RECIPE step (e).8) always appends
    `.secrets.baseline` to its `--paths` list -- and "secret" is a HIGH-tier
    keyword in `review_risk_tier.py`'s classifier. So `tier=` reads "high"
    for essentially every wheel-recorded entry regardless of what the item
    actually changed, undercutting this field's own point for THAT
    population of ledger lines. Recorded here as a known limitation, not
    architecturally fixed."""
    return parse_ledger_fields(raw_token).get("tier", TIER_UNKNOWN)


def head_review_fields(last_reviewed_path: str, repo_root: str, head: str) -> dict[str, str]:
    """The trailing k=v telemetry fields LAST recorded for repo_root+head,
    or {} when never recorded, or recorded in the legacy bare/outcome-only
    shape with no trailing fields at all. Mirrors `head_review_outcome`'s
    own repo_root+head lookup (built on the SAME `_existing_outcome_token`
    read) but for the NEW fields instead of the outcome. A field simply
    absent from the returned dict means unknown for THIS head -- read with
    ``.get("tier", TIER_UNKNOWN)``, never treat a missing key as a real
    value. Never raises."""
    token = _existing_outcome_token(last_reviewed_path, repo_root, head)
    return parse_ledger_fields(token)


def head_review_reviewer_identity(last_reviewed_path: str, repo_root: str, head: str) -> dict:
    """The parsed `reviewer=` identity LAST recorded for repo_root+head --
    see `parse_reviewer_value` (2026-08-30, gate-optimization plan Item 6b).
    ``{"type": None, "agent_id": None, "tool_use_id": None}`` when never
    recorded, or recorded with no `reviewer=` field at all. Never raises."""
    fields = head_review_fields(last_reviewed_path, repo_root, head)
    return parse_reviewer_value(fields.get("reviewer"))


def _outcome_token(outcome: str | None, blockers: int | None) -> str | None:
    """Serialize a caller-supplied (outcome, blockers) pair into the ledger's
    outcome suffix token, or None when unspecified/unrecognized — in which
    case the legacy bare ``"<repo_root> <sha>"`` line is written, never a
    guessed outcome. A non-positive `blockers` count under OUTCOME_BLOCKERS
    still needs *some* positive count to be meaningful; it defaults to 1
    rather than being silently dropped (the caller explicitly said "blockers",
    just without a usable count).
    """
    if outcome == OUTCOME_CLEAN:
        return "clean"
    if outcome == OUTCOME_BLOCKERS:
        n = blockers if isinstance(blockers, int) and blockers > 0 else 1
        return f"blockers:{n}"
    return None


def _outcome_phrase(token: str) -> str:
    """A short human phrase for a raw outcome token, used in confirmation lines."""
    status, n = parse_outcome_token(token)
    if status == OUTCOME_CLEAN:
        return "clean — no unresolved blockers"
    if status == OUTCOME_BLOCKERS:
        return f"{n} unresolved blocker(s)"
    return "outcome unknown"


# Safe charset shared by every short scalar telemetry field (item=/
# tier_declared=/reviewer=/prev=) -- mirrors the ORIGINAL item= sanitizer
# exactly (2026-08-23, #4400), just factored out so every new field gets
# the identical guarantee: whatever the caller supplies can never fracture
# the space-separated k=v line grammar (no raw whitespace survives this).
_SAFE_FIELD_RE = re.compile(r"[^A-Za-z0-9_.:#/-]")

# Individual PATH components use a NARROWER charset than the general field
# sanitizer above: "#" is deliberately EXCLUDED here even though the
# general sanitizer allows it, because "#" is the join separator for
# paths= (below) -- a path containing a literal "#" could otherwise fake an
# extra boundary and desynchronize paths_n= from what a reader splits out.
_SAFE_PATH_RE = re.compile(r"[^A-Za-z0-9_.:/-]")

_MAX_PATHS_IN_FIELD = 12

# --- Reviewer identity encoding (2026-08-30, gate-optimization plan Item 6b)
# -----------------------------------------------------------------------
# `reviewer=`'s value is EITHER a bare reviewer-of-record TYPE string (e.g.
# "trust-architect" -- Item 6's original shape, still exactly what every
# caller supplying only ``--reviewer`` produces) OR, when the caller ALSO
# supplies BOTH ``--reviewer-agent-id`` and ``--reviewer-tool-use-id``, a
# compound ``"<type>#<agent_id>#<tool_use_id>"`` value joining the reviewer
# TYPE to the exact dispatch-lease identity that
# ``~/.claude/.agent_budget/spend.jsonl`` already records per sub-agent
# invocation (``agent_id``/``tool_use_id``, both unique per real Task
# dispatch -- see ``_build_claim_record``/``classify_release_event`` in
# ``agent_budget.py``).
#
# THIS CLOSES THE AUDIT GAP ONLY, NOT THE ENFORCEMENT GAP: nothing here (or
# anywhere in this module) blocks a caller from recording ``--clean`` with
# no identity at all -- gate 3b still only checks that SOME review is on
# record, exactly as before. What this adds is a durable join key an
# OFFLINE audit (``hooks/audit_review_attribution.py``) can later use to
# assert a `clean` entry actually corresponds to a real sub-agent dispatch
# rather than the orchestrator self-recording its own clearance.
#
# Session-id stamping alone was considered and rejected as insufficient:
# ``_lib.session_id``'s own docstring states plainly that "a sub-agent's
# payload carries the SAME session_id as its parent session (no separate
# identity)" -- verified directly against real `~/.claude/.agent_budget/
# spend.jsonl` rows for this exact session, where every sub-agent dispatch
# this session made (agent_type in {implement, code-reviewer, ...}) carries
# `session` identical to the orchestrating session's own id. A session-id
# join could therefore never distinguish "the orchestrator recorded this
# itself" from "a real code-reviewer sub-agent produced this outcome" --
# precisely the threat model this mechanism exists to detect. `agent_id`/
# `tool_use_id`, by contrast, are minted PER DISPATCH (unique to one Task
# invocation), which is exactly the granularity self-clearing vs. real
# review needs to be told apart at.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_REVIEWER_IDENTITY_SEP = "#"

# FINDING 7 (2026-08-30 review, minor): `_entry_suffix`'s reviewer= branch
# used to sanitize via the GENERAL `_safe_field` default of maxlen=80 --
# fine for a bare TYPE string (already capped to 80 by `_safe_reviewer_type`
# above), but a COMPOUND identity is up to three components joined by "#":
# a type (<=80, `_safe_reviewer_type`) + an agent_id (<=80, `_SAFE_ID_RE`'s
# ``[A-Za-z0-9][A-Za-z0-9_-]{0,79}`` = 1+79) + a tool_use_id (<=80, same
# regex) + 2 separator chars = 242 chars worst case. Truncating that to 80
# silently destroys the compound structure (most often slicing straight
# through tool_use_id, sometimes through the second "#" itself), and
# `parse_reviewer_value` then degrades the mangled remainder to "the whole
# value is the type" -- the identity is lost with no error at all. This is
# the EXACT, PROVABLE worst case (every component's own sanitizer already
# bounds it), not a heuristic guess at "probably long enough" -- so raising
# the cap to this value eliminates the truncation risk entirely rather than
# just reducing its likelihood.
_MAX_REVIEWER_FIELD_LEN = 80 + 1 + 80 + 1 + 80  # type + "#" + agent_id + "#" + tool_use_id


def _safe_reviewer_type(value: str) -> str:
    """Sanitize a reviewer TYPE string for inclusion in a compound
    ``reviewer=`` identity value: the same charset as `_safe_field`, minus
    the compound join char `#` -- mirrors `_safe_path_component`'s own
    "exclude the join char" precedent for `paths=`, so the 3-way split in
    `parse_reviewer_value` is never ambiguous. Never raises."""
    try:
        cleaned = _SAFE_FIELD_RE.sub("_", value)
        return cleaned.replace(_REVIEWER_IDENTITY_SEP, "_")[:80]
    except Exception:
        return ""


def compose_reviewer_field(
    reviewer_type: str | None, agent_id: str | None, tool_use_id: str | None
) -> str | None:
    """Build the `reviewer=` ledger value.

    Bare TYPE string (Item 6's original, unchanged shape) when `agent_id`/
    `tool_use_id` are not BOTH present. The compound
    ``"<type>#<agent_id>#<tool_use_id>"`` (Item 6b) when both are present --
    `main()`'s own argv validation (`_parse_new_fields`) guarantees
    both-or-neither before this is ever called, so a lone `agent_id` or
    `tool_use_id` never reaches here. `reviewer_type` defaults to
    ``"unknown"`` when the identity is present but no `--reviewer` type was
    supplied, so the identity is never silently dropped for lack of a type.
    Returns `reviewer_type` unchanged (possibly None) when there is no
    identity to attach. Never raises."""
    try:
        if agent_id and tool_use_id:
            type_part = _safe_reviewer_type(reviewer_type) if reviewer_type else ""
            type_part = type_part or "unknown"
            return (
                f"{type_part}{_REVIEWER_IDENTITY_SEP}{agent_id}"
                f"{_REVIEWER_IDENTITY_SEP}{tool_use_id}"
            )
        return reviewer_type
    except Exception:
        return reviewer_type


def parse_reviewer_value(value: str | None) -> dict:
    """Parse a `reviewer=` ledger value into
    ``{"type", "agent_id", "tool_use_id"}`` -- ALL three keys always
    present. A bare (non-compound) value, or None/empty, yields
    ``{"type": value or None, "agent_id": None, "tool_use_id": None}``
    (Item 6's original shape, and every entry recorded before Item 6b
    shipped). A well-formed 3-part `#`-joined compound (Item 6b) yields all
    three fields populated. A malformed compound (wrong part count, or an
    empty part) degrades to treating the WHOLE raw value as the type,
    exactly like the bare case -- never raises, never guesses a partial
    identity out of a malformed value."""
    if not value:
        return {"type": None, "agent_id": None, "tool_use_id": None}
    try:
        parts = value.split(_REVIEWER_IDENTITY_SEP)
        if len(parts) == 3 and all(parts):
            return {"type": parts[0], "agent_id": parts[1], "tool_use_id": parts[2]}
    except Exception:
        pass
    return {"type": value, "agent_id": None, "tool_use_id": None}


def _safe_field(value: str, maxlen: int = 80) -> str:
    """Sanitize an arbitrary caller-supplied short string into the ledger's
    safe charset (the original item= sanitizer, unchanged). Never raises."""
    try:
        return _SAFE_FIELD_RE.sub("_", value)[:maxlen]
    except Exception:
        return ""


def _safe_path_component(value: str, maxlen: int = 200) -> str:
    """Sanitize ONE path for inclusion in the paths= field -- same idea as
    _safe_field, but excludes "#" (see _SAFE_PATH_RE) and allows a longer
    cap (80 chars is too short for a real repo path -- the gate-optimization
    plan's Item 6 explicitly corrected an earlier draft that tried to reuse
    the 80-char item= truncation for this). Never raises."""
    try:
        return _SAFE_PATH_RE.sub("_", value)[:maxlen]
    except Exception:
        return ""


def _paths_field(paths: list[str] | None) -> tuple[str, int]:
    """(joined, total) for the ledger's paths=/paths_n= fields.

    Joins up to `_MAX_PATHS_IN_FIELD` sanitized paths with "#" (a separator
    that IS in the safe charset -- a comma is NOT, see module notes) and
    ALWAYS returns the true total count separately, so overflow beyond the
    cap is visible on the ledger line itself rather than silently truncated
    mid-path. `joined` is "" (and `total` 0) for an empty/None input -- the
    caller decides whether to emit the fields at all based on that. Never
    raises.

    GH #5886 fix-round-4 (non-blocking, cold review): `total` is now the
    count of DISTINCT SANITIZED path strings, not the raw input length. A
    caller's `--paths` can carry a literal duplicate, or two different raw
    strings that collide after `_safe_path_component`'s sanitization (a
    narrower charset than the ledger's general field sanitizer) -- either
    way, the SET a `--rekey` call's own paths-mismatch check later compares
    against (built the identical way: sanitize, then dedupe into a set) is
    the deduped-sanitized set, never the raw list. Recording `paths_n` from
    the raw count made an honest 13-distinct-path review with one literal
    duplicate in its `--paths` record `paths_n=14`, which a later honest
    13-distinct-path `--rekey` call could never match -- a false refusal,
    not a safety gap (the byte-identity check still would have refused any
    REAL smuggled content), but a usability bug this fixes by construction.
    """
    try:
        clean = [p for p in (paths or []) if p]
        if not clean:
            return "", 0
        # Dedupe on the SANITIZED value (what a later --rekey comparison
        # actually compares), preserving first-seen order so the stored,
        # possibly-truncated `paths=` set is unaffected for the common
        # (already-unique) case.
        seen: dict[str, None] = {}
        for p in clean:
            seen.setdefault(_safe_path_component(p), None)
        sanitized_unique = list(seen)
        capped = sanitized_unique[:_MAX_PATHS_IN_FIELD]
        joined = "#".join(capped)
        return joined, len(sanitized_unique)
    except Exception:
        return "", 0


# Hardcoded literal, deliberately -- matches `_PREV_RE`/`_REKEY_RE`'s own
# existing convention of encoding the "precommit:" shape directly rather
# than importing `precommit_review_gate.PRECOMMIT_PREFIX` (that module
# already imports THIS one; a top-level import back would be a cycle, and
# every other precommit-shape constant in this file is already a literal
# for the same reason).
_PRECOMMIT_KEY_PREFIX = "precommit:"


# ---------------------------------------------------------------------------
# Derived reviewing model (master plan WS2.4 step 1, 2026-09-20): the
# ledger's model= field is now DERIVED from the dispatch-lease ledger
# (~/.claude/.agent_budget/spend.jsonl), never trusted from a caller's
# self-reported --model -- the identical "derived value governs, declared
# value is audit-only" pattern `tier=`/`tier_declared=` already established
# (decide()'s own docs, review_risk_tier.classify()). A caller's --model, if
# supplied, is validated as before (_VALID_MODELS, a 3-way opus/sonnet/haiku
# set unchanged by this feature -- it is a distinct, narrower vocabulary
# than the derived tier word below, which can also be "fable") but is now
# written to the ledger ONLY as an audit-only model_declared= field, and
# ONLY when it actually disagrees with a successfully-derived value; the
# real model= field is always the ledger-derived word (or entirely absent
# when nothing could be derived -- never a guess).
# ---------------------------------------------------------------------------

# The derived model tier vocabulary -- a SUPERSET of _VALID_MODELS (adds
# "fable", a real tier per CLAUDE.md §7/§10 that a caller's --model flag
# does not accept as a DECLARATION). No seat carries a standing fable pin
# (operator directive 2026-09-24 retired them; plan-reviewer and
# marketing-director are opus), so fable is reachable ONLY through a
# single-use operator grant -- but the ledger MUST still be able to
# represent it, since an operator-granted dispatch really does run at fable
# and a derived value must never be silently dropped just because it falls
# outside --model's own, narrower, caller-facing validation set.
_DERIVED_MODEL_TIERS = frozenset({"opus", "sonnet", "haiku", "fable"})

# Bounded scan depth for the spend.jsonl join (task spec, WS2.4 step 1): the
# ledger is a large, real, ever-growing append-only log shared by every
# session on the machine (measured 2026-09-20: hundreds of thousands of
# lines over the ledger's lifetime) -- a real dispatch's own recording
# happens within moments of the dispatch itself, so the row this join wants
# is always near the END of the file. Scanning the WHOLE file on every
# `record_review.py --pre-commit` call (the hot path gate 3b sits in front
# of) would make every commit's review-recording cost grow with the
# ledger's entire lifetime rather than with recent activity. Bounded to the
# last _SPEND_JOIN_SCAN_LINES lines: a hit within that window is found; a
# hit beyond it is treated as unjoinable -- the SAME "unjoinable" reason
# code as a row that genuinely doesn't exist at all (never a false negative
# silently reported as "not present" with no reason at all; this module
# does not distinguish WHY a row wasn't found within the scan, only that it
# wasn't -- see `derive_reviewing_model`'s own `reason` return).
_SPEND_JOIN_SCAN_LINES = 20000


def normalize_model_tier(model: object) -> str | None:
    """A raw spend.jsonl `model` (or `model_requested`) string -- e.g.
    ``"claude-sonnet-5"``, ``"claude-opus-5[1m]"``, ``"claude-fable-5-1"``,
    a bare ``"opus"`` -- into the ledger's short tier word (one of
    `_DERIVED_MODEL_TIERS`), or None when unrecognized.

    Deliberately reuses `cycle_budget.normalize_model` (this runtime's own
    cost-accounting normalizer, already trusted for pricing) rather than
    re-deriving a second family-matching table that could silently drift
    out of step with it -- imported lazily (module-scope would risk a
    cycle if `cycle_budget` ever grows a reverse import; every other
    cross-module import in this file already follows this lazy convention
    for the same reason). `cycle_budget.normalize_model` already returns
    "unknown" for anything unrecognized (never raises) -- translated to
    None here, matching every other "absent means None, never a guessed
    real value" convention in this module. Never raises.
    """
    try:
        import cycle_budget as cb
    except Exception:
        return None
    try:
        family = cb.normalize_model(model)
    except Exception:
        return None
    return family if family in _DERIVED_MODEL_TIERS else None


class ModelDerivation(NamedTuple):
    """The pure outcome of trying to derive a reviewing model from
    spend.jsonl for one (--reviewer-agent-id, --reviewer-tool-use-id) pair.

    Attributes:
        model: the derived tier word (one of `_DERIVED_MODEL_TIERS`), or
            None when nothing could be derived.
        model_id: the raw ledger `model`/`model_requested` string the tier
            word was normalized from (e.g. "claude-opus-5[1m]"), or None.
        reason: "" when `model` is populated (a real join succeeded);
            otherwise one of "no-identity" (no --reviewer-tool-use-id was
            supplied at all), "ledger-unreadable" (spend.jsonl is missing
            or could not be read), "unjoinable" (a bounded scan found no
            matching row -- wrong tool_use_id, agent_id mismatch when one
            was supplied, or the row exists but outside the scan window),
            or "unrecognized-model" (a row matched but its own model
            string normalized to nothing this ledger's vocabulary knows).
    """

    model: str | None
    model_id: str | None
    reason: str


def derive_reviewing_model(
    budget_dir: str,
    tool_use_id: str | None,
    agent_id: str | None,
    *,
    scan_lines: int = _SPEND_JOIN_SCAN_LINES,
) -> ModelDerivation:
    """Join `tool_use_id` (+ optionally `agent_id`) to a real dispatch row
    in `budget_dir`/spend.jsonl and derive the model that actually reviewed.

    Scans the file from the END, bounded to the last `scan_lines` raw
    lines, and stops at the FIRST matching row (most-recent-first is
    exactly right here: a `tool_use_id` is unique per real Task dispatch --
    see `agent_budget._build_claim_record`/`classify_release_event` -- so
    there is only ever supposed to be one matching row at all; scanning
    from the end just means a real, recent dispatch is found cheaply
    without reading the ledger's entire history). When `agent_id` is ALSO
    supplied, a candidate row's own `agent_id` must equal it -- a
    `tool_use_id` match with a DISAGREEING `agent_id` is treated as no
    match at all (never a partial/best-effort join): the two fields
    together identify one dispatch, per Item 6b's own compound-identity
    contract, and disagreeing on one is a stronger signal that something is
    wrong (a copy-paste error, or a deliberate forgery attempt) than "close
    enough."

    A matched row's model is read from `model`, falling back to
    `model_requested` when `model` is absent (mirrors
    `agent_budget.py`'s own `row.get("model") or row.get("model_requested")`
    fallback for a reaped/foreground claim whose own `model` never got
    filled in directly) -- then normalized via `normalize_model_tier`.

    Never raises: any I/O or parsing failure degrades to a `ModelDerivation`
    with `model=None` and a stated `reason`, exactly like every other
    read-only helper in this module.
    """
    if not tool_use_id:
        return ModelDerivation(None, None, "no-identity")

    spend_path = os.path.join(budget_dir, "spend.jsonl")
    try:
        if not os.path.isfile(spend_path):
            return ModelDerivation(None, None, "ledger-unreadable")
        with open(spend_path, encoding="utf-8", errors="replace") as fh:
            # A plain deque(fh, maxlen=scan_lines) reads the WHOLE file to
            # populate a bounded window (deque discards from the front as
            # it fills, but every line still passes through the file
            # iterator first) -- for a real multi-hundred-thousand-line
            # ledger that is exactly the unbounded-cost shape this bound
            # exists to avoid. Seek-from-the-end instead: read the last
            # ~scan_lines worth of bytes directly, using a generous
            # per-line byte estimate, so the read cost scales with the
            # bound, not with the ledger's lifetime.
            # 2026-09-20 fix round, nit 8: measured against the real
            # ~/.claude/.agent_budget/spend.jsonl (15,443 rows) -- mean row
            # size 438B, p99 472B, max 480B. The original 400B estimate was
            # BELOW the measured mean, so a "last 20,000 lines" bound
            # actually covered only ~18,250 real lines (20000*400/438).
            # 512B clears the measured p99 with headroom, so the byte
            # window genuinely covers _SPEND_JOIN_SCAN_LINES real lines,
            # not an undercount of it.
            _AVG_LINE_BYTES = 512
            fh.seek(0, os.SEEK_END)
            file_size = fh.tell()
            read_size = min(file_size, scan_lines * _AVG_LINE_BYTES)
            fh.seek(max(0, file_size - read_size))
            chunk = fh.read()
        raw_lines = chunk.splitlines()
        # The seek-from-the-end may have landed mid-line; the first
        # fragment in `raw_lines` is potentially a partial line (missing
        # its opening bytes) unless the seek landed exactly at byte 0 or a
        # newline boundary. A partial line fails JSON parsing harmlessly
        # (json.loads raises, caught below) rather than silently
        # misparsing -- never worth a byte-exact boundary check for a
        # bounded, best-effort scan.
        window = raw_lines[-scan_lines:] if len(raw_lines) > scan_lines else raw_lines
    except Exception:
        return ModelDerivation(None, None, "ledger-unreadable")

    # Scan most-recent-first (the window is in on-disk order, oldest to
    # newest; reversed() walks newest-first) so the first match found is
    # the most recent dispatch, matching this ledger's own "last wins"
    # precedent everywhere else (`_existing_outcome_token`).
    for raw in reversed(window):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("tool_use_id") != tool_use_id:
            continue
        if agent_id and row.get("agent_id") != agent_id:
            # A tool_use_id match with a disagreeing agent_id is NOT a
            # match -- keep scanning in case an (unlikely, but possible)
            # older/foreign row happens to share the same tool_use_id
            # string; if nothing else matches, this call correctly reports
            # unjoinable below.
            continue
        raw_model = row.get("model") or row.get("model_requested")
        tier = normalize_model_tier(raw_model)
        if tier is None:
            return ModelDerivation(None, None, "unrecognized-model")
        return ModelDerivation(tier, raw_model if isinstance(raw_model, str) else None, "")

    return ModelDerivation(None, None, "unjoinable")


def find_clean_precommit_entry_for_paths(
    last_reviewed_path: str, repo_root: str, raw_paths: list[str]
) -> str | None:
    """The MOST RECENT `precommit:<digest>` ledger key, for `repo_root`,
    recorded CLEAN whose own `paths=` telemetry field (`_paths_field`)
    sanitizes to the EXACT SAME SET as `raw_paths` — a HINT ONLY for
    precommit_review_gate.py's unreviewed-commit denial message (AA-0064):
    when a prior review of these same paths already exists clean at a
    DIFFERENT digest, printing the exact `--rekey <that key>` command lets a
    caller try the cheap, mechanically-verified reconstruction
    (`precommit_review_gate.rekey_digest_if_only_untracked_became_staged`)
    before paying for a full re-review that may turn out unnecessary.

    This function NEVER decides anything on its own — the gate's block/allow
    logic is completely unchanged; the caller surfaces this purely as a
    suggestion. `raw_paths` is compared in the SAME (raw, un-repo-root-
    normalized) form `--paths` telemetry is written in — see `_paths_field`
    — using a SET comparison (order-independent: the CLI does not sort
    `--paths` before writing `paths=`) sanitized via the same
    `_safe_path_component` the ledger write itself uses, so a caller who
    types the exact same paths for both the original review and the current
    commit gets a match regardless of argv order. A paths= field written
    before this feature existed (no paths= at all), or truncated at
    `_MAX_PATHS_IN_FIELD`/per-path `maxlen=200`, is compared as-is — a
    legacy/truncated entry that happens not to match exactly simply yields
    no hint, never a false one. Returns None on any read failure, an empty
    `raw_paths`, or no matching entry. Never raises.
    """
    if not raw_paths or not repo_root:
        return None
    try:
        wanted = frozenset(_safe_path_component(p) for p in raw_paths if p)
        if not wanted:
            return None
        prefix = f"{repo_root} {_PRECOMMIT_KEY_PREFIX}"
        best: str | None = None
        if not os.path.isfile(last_reviewed_path):
            return None
        with open(last_reviewed_path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                if not line.startswith(prefix):
                    continue
                rest = line[len(repo_root) + 1 :]
                key, _, token = rest.partition(" ")
                if not token:
                    continue
                status, _n = parse_outcome_token(token)
                if status != OUTCOME_CLEAN:
                    continue
                fields = parse_ledger_fields(token)
                paths_raw = fields.get("paths")
                if not paths_raw:
                    continue
                if frozenset(paths_raw.split("#")) == wanted:
                    best = key  # last (most recent) match wins
        return best
    except Exception:
        return None


class RoundDerivation(NamedTuple):
    """The pure outcome of deriving a review round for a `--pre-commit`
    recording on `repo_root`+`raw_paths` (WS2.3, master plan §2.3).

    Attributes:
        derived_round: the round number the recorder computed --
            `(count of --blockers entries found walking backward through
            this repo's OWN ledger history for entries whose paths=
            OVERLAP raw_paths, stopping at the latest --clean covering
            them) + 1`. Always >= 1 (a chain with no prior history at all
            derives round 1).
        blockers_found: the raw count of unresolved-blockers entries the
            walk found before it stopped -- `derived_round - 1`, exposed
            separately so a caller/test can assert on the walk's own
            evidence rather than just the +1'd total.
        stopped_at_clean: True iff the walk's OWN terminating condition was
            finding a prior --clean entry covering these paths (rather than
            simply running out of ledger history) -- informational only,
            never load-bearing for derived_round itself.
    """

    derived_round: int
    blockers_found: int
    stopped_at_clean: bool


def derive_review_round(
    last_reviewed_path: str, repo_root: str, raw_paths: list[str]
) -> RoundDerivation:
    """Derive this review's round number from repo R's OWN ledger history --
    NEVER trusted from a caller's self-declared ``--round`` (WS2.3, master
    plan §2.3, mirroring `tier=`/`model=`'s own "always computed" precedent
    exactly: a self-reported round binds almost nothing, since nothing
    stops any caller from typing any number at all).

    Walks EVERY `precommit:`-keyed ledger line for `repo_root`, in the
    ledger's own on-disk (chronological, append-only) order, testing each
    one's own `paths=` telemetry field for OVERLAP against `raw_paths` --
    via `file_claims.paths_overlap` (imported lazily, mirroring every other
    lazy cross-module import in this file to avoid a load-time cycle risk;
    `file_claims` itself only imports `_lib`/`agent_budget` at module scope,
    so there is no real cycle, just this module's own established
    convention for a sibling-hooks import), never a second, independently-
    written comparison -- the task's own explicit requirement, and the
    same "one predicate, every caller shares it" discipline `paths_overlap`
    already establishes for the commit-contest ledger.

    "Overlap" here is deliberately NOT exact-set equality (contrast
    `find_clean_precommit_entry_for_paths`, which DOES want exact-set
    equality for its own narrower "same review, staging moved the digest"
    purpose): a fix round very often touches a NARROWER or WIDER pathspec
    than the round before it (a round-2 fix might touch only 2 of the
    round-1 dispatch's 5 files, or add a new file the fix required) --
    `paths_overlap`'s prefix-aware, directory/file-safe semantics are
    exactly what "is this the same boundary's chain" should mean, matching
    `file_claims.py`'s own contest predicate for "does this commit touch a
    path someone else is mid-commit on."

    Chain semantics: walking OLDEST-to-newest (the ledger's own on-disk
    order for a single-writer-at-a-time file), `derived_round` starts at 1
    and increments once for every `--blockers` (unresolved) entry found
    that overlaps `raw_paths`, and the walk STOPS (resets the count to 0
    blockers-found-so-far, i.e. restarts the chain at round 1) the moment
    it passes a `--clean` entry that ALSO overlaps `raw_paths` -- a clean
    review closes that boundary's chain; anything after it is either a
    brand-new chain on the same paths, or unrelated to this call's true
    boundary at all (paths that were reviewed clean and never touched
    again do not artificially inflate a LATER, unrelated commit's round on
    a merely-overlapping path). Two DIFFERENT chains on genuinely disjoint
    paths never interact at all -- `paths_overlap` is what enforces that
    (see the task's own required test: "paths that do not overlap are a
    DIFFERENT chain").

    KNOWN, ACCEPTED GAP (stated at both call sites this module and
    `docs/subsystems/review-ladder.md` document it -- never left silent,
    per the task's own requirement): this v1 does NOT follow a rename
    across the chain. `paths=` telemetry is a set of literal path STRINGS
    a prior recording call happened to be invoked with -- there is no
    mechanism here (or realistically available from this flat, digest-
    keyed ledger format) to recognize that `new_name.py` in this call's
    `raw_paths` is the renamed continuation of `old_name.py` in an earlier
    entry's `paths=`. A rename mid-chain therefore UNDERCOUNTS the derived
    round (the walk simply finds no overlapping predecessor and starts a
    fresh round 1) rather than crashing -- a safe failure direction for
    THAT gap specifically, but a real, accepted limitation.

    OVERCOUNT IS ALSO REACHABLE, and an earlier version of this docstring
    denied it. Corrected rather than deleted, because it was stated here
    confidently: `paths_overlap` is UNION semantics (a call overlaps an
    entry if ANY path matches), so INDEPENDENT chains that merely share one
    path are walked as one chain. Reproduced: five unrelated features each
    with one blockers round, each touching `README.md`; a brand-new sixth
    feature's FIRST review derives round 6 and logs
    `total-round-cap-would-refuse`. True round: 1. Reachable via a shared
    file, a directory-scoped pathspec, or a multi-path commit spanning two
    open chains; a live-ledger replay found 19 tripwire and 1 cap crossing.
    This is a primary reason the feature stays LOG-ONLY, and it MUST be
    resolved before enforcement -- enforcement is gated on an observation
    window this corrupts by construction. See
    `docs/subsystems/review-ladder.md`; tracked on #5828.

    Read-only; never raises (any I/O or parsing failure degrades to
    `RoundDerivation(1, 0, False)` -- "derive round 1", the same safe-
    failure direction as the rename gap above: an unreadable ledger must
    never itself manufacture a false round-4+ tripwire log).
    """
    try:
        import file_claims as fc  # noqa: PLC0415 (lazy: matches this module's

        # own established sibling-hooks import convention; file_claims has
        # no import of record_review, so there is no real cycle either way,
        # this just mirrors every other lazy import in this file)

        # BOTH sanitize AND normalize, in that order -- they are not
        # alternatives and an earlier cut of this code treated them as such.
        # `_safe_path_component` matches how the ledger's own paths= field is
        # written (see `_paths_field`), so it must come first or a path
        # containing a character that sanitizer maps to "_" would falsely
        # miss. But it is a CHARSET sanitizer, not a path normalizer: it
        # leaves `./` and a trailing `/` intact. `paths_overlap` is a pure
        # string-prefix predicate, so those spellings silently break the
        # chain -- measured against the real ledger, `hooks/record_review.py`
        # derived round 2 while `./hooks/record_review.py` and `hooks/`
        # derived round 1, the same boundary giving three answers. That is a
        # silent WRONG round, and it would have corrupted by construction
        # the very observation window that gates enforcement. Every other
        # `paths_overlap` caller in the runtime normalizes first
        # (`file_claims`'s own two call sites do); this one now does too.
        wanted = frozenset(
            fc.normalize_path(_safe_path_component(p))
            for p in (raw_paths or [])
            if p and p.strip()
        )
        if not wanted or not repo_root or not os.path.isfile(last_reviewed_path):
            return RoundDerivation(1, 0, False)

        prefix = f"{repo_root} {_PRECOMMIT_KEY_PREFIX}"
        blockers_count = 0
        stopped_at_clean = False
        with open(last_reviewed_path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")
                if not line.startswith(prefix):
                    continue
                rest = line[len(repo_root) + 1 :]
                _key, _, token = rest.partition(" ")
                if not token:
                    continue
                status, _n = parse_outcome_token(token)
                if status not in (OUTCOME_CLEAN, OUTCOME_BLOCKERS):
                    continue
                fields = parse_ledger_fields(token)
                paths_raw = fields.get("paths")
                if not paths_raw:
                    continue
                # Normalize the LEDGER side too. Normalizing only the
                # caller's paths left the fix HALF-APPLIED: an entry written
                # by a caller who typed `./hooks/a.py` stores that spelling
                # verbatim (`_paths_field` sanitizes but does not normalize),
                # so it was unmatchable even by an IDENTICALLY-spelled later
                # call. Measured before this line: ledger `./hooks/a.py` vs
                # call `['./hooks/a.py']` derived 1, not 2.
                entry_paths = frozenset(
                    fc.normalize_path(x) for x in paths_raw.split("#") if x
                )
                if not fc.paths_overlap(wanted, entry_paths):
                    continue
                if status == OUTCOME_CLEAN:
                    # A clean review of an overlapping pathspec closes that
                    # boundary's chain -- anything found AFTER this point
                    # (further down in the file, i.e. later in time) starts
                    # a fresh chain, so the count-so-far is discarded.
                    blockers_count = 0
                    stopped_at_clean = True
                    continue
                # status == OUTCOME_BLOCKERS: an unresolved ROUND on this
                # same boundary. The master plan's own formula is
                # "derived_round = (count of --blockers ENTRIES found) + 1"
                # -- this counts ENTRIES (one review round == one ledger
                # line), never the per-entry `n` (the number of individual
                # findings THAT round reported), which `n` here is
                # deliberately unused for beyond having already been
                # validated non-negative by parse_outcome_token. A round
                # that found 5 blocker findings and a round that found 1
                # are both still exactly one review ROUND each. This
                # overlapping entry also means the chain is NOT (yet)
                # closed, so a LATER clean would still correctly reset it.
                blockers_count += 1
                stopped_at_clean = False
        return RoundDerivation(blockers_count + 1, blockers_count, stopped_at_clean)
    except Exception:
        return RoundDerivation(1, 0, False)


def _entry_suffix(
    item: str | None = None,
    *,
    tier: str | None = None,
    tier_declared: str | None = None,
    reviewer: str | None = None,
    model: str | None = None,
    model_source: str | None = None,
    model_id: str | None = None,
    model_declared: str | None = None,
    round_: int | None = None,
    paths: list[str] | None = None,
    prev: str | None = None,
    vf: str | None = None,
    warm: bool = False,
    rekey: str | None = None,
    corrects_from: str | None = None,
    dg: str | None = None,
) -> str:
    """Telemetry fields appended AFTER the outcome token.

    Original shape (2026-08-23, #4400): `` ts=<utc-iso>`` and optionally
    `` item=<key>``. EXTENDED 2026-08-30 (gate-optimization plan, Item 6)
    with `` tier=``/`` tier_declared=``/`` reviewer=``/`` model=``/
    `` round=``/`` paths=``+`` paths_n=``/`` prev=``/`` vf=`` -- every one
    of these is OPTIONAL and appended ONLY when the caller actually
    supplied (or, for `tier`, `decide()` computed) it, in the SAME
    append-only, never-insert, never-reorder spirit as the original two
    fields, so every legacy AND already-new-shape reader keeps resolving
    correctly. EXTENDED again 2026-08-31 (build-wave Lane B, CLAUDE.md §10's
    warm-round paragraph) with `` warm=1`` -- appended ONLY when the caller
    passed ``--warm`` for this recording; absent means "not warm" (a cold
    round, or any pre-2026-08-31 line), never a guessed value, matching
    every other optional field's own absent-means-unknown/false convention.
    EXTENDED again 2026-09-01 (AA-0064 fix round, Item 8) with `` rekey=``
    -- appended ONLY when `record_review.py --rekey` is what produced this
    line, carrying the PRIOR `precommit:<digest>` key it carried the clean
    outcome forward from. This is the audit-visible distinction between a
    sanctioned mechanical carry-forward (this field present) and a genuinely
    fresh review (absent) -- `audit_review_attribution.py` needs it to stop
    treating a --rekey entry's carried-forward reviewer= identity as an
    unattributed/self-cleared clean. EXTENDED again 2026-09-09 (#5133)
    with `` corrects_from=`` -- appended ONLY when `record_review.py
    --correct-identity <key>` is what produced this line, carrying the OLD
    (mistyped/wrong) `reviewer=` value it is superseding. This is the
    audit-visible trail a correction exists for in the first place: the
    corrected entry is APPENDED (never rewrites the original line in
    place), so both the old and new identity stay on record, and
    `corrects_from=` makes the relationship between them explicit rather
    than leaving a future reader to infer "two entries, same key" means a
    correction happened. See `main()`'s `--correct-identity` branch for the
    full contract (refuses when no prior entry exists for the exact key,
    refuses to touch outcome/paths/digest -- identity fields only).

    EXTENDED again 2026-09-24 (GH #5886 fix-round-4, R7-B1, cold
    trust-architect review) with `` dg=`` -- a digest-format VERSION marker,
    appended ONLY by `main()`'s `--pre-commit` and `--rekey` write paths (a
    plain unspecified/legacy recording never carries it, matching every
    other optional field's own absent-means-unknown convention). `dg=2`
    marks a content-keyed (`precommit:<digest>`) entry whose digest was
    computed using `precommit_review_gate._digest_safe_name`'s
    control-character-safe rendering (R6-B1, fix-round-4) -- i.e. a digest
    that is safe to treat as a `--rekey` CHAIN ROOT. An entry recorded
    before this fix existed (or by any code path that predates R6-B1) has
    NO `dg=` field at all, which `main()`'s `--rekey` branch now reads as
    "this digest may have been computed under the pre-R6-B1 rendering" and
    refuses to build on top of -- closing the R7-B1 hole where `--rekey`
    trusted an old (pre-fix) digest as proof of byte-identical content, when
    that old digest could not actually distinguish a single oddly-named
    reviewed entry from two separate fabricated files (see `main()`'s
    `--rekey` branch and CLAUDE.md's falsifiability discipline). This is a
    VERSION marker, not a content field: it says nothing about a *specific*
    digest's value, only which rendering rule computed it, so a reader
    never needs to re-derive it -- it is read straight off the ledger line
    exactly like `warm=`/`rekey=` above.

    `tier` here is ALWAYS the value `review_risk_tier.classify()` computed
    for this recording -- NEVER a caller-declared value (see decide()'s own
    docs and the gate-optimization plan's Item 6). `tier_declared` is a
    SEPARATE, audit-only field: populated by the caller ONLY when a
    `--tier` flag it passed disagreed with the computed value -- a
    disagreement is itself a signal, never something silently trusted or
    silently dropped.

    item/tier_declared/reviewer/prev are sanitized via `_safe_field`
    (never raw); paths via `_safe_path_component` + "#"-joining
    (`_paths_field`). `model` and `vf` are written verbatim because both
    are validated against a closed token set by the CALLER
    (`record_review.main`'s `_parse_new_fields`) before this is ever
    reached -- revalidating here would just duplicate that check. `round_`
    is written via `int()` defensively (never a caller-controlled string
    landing unescaped in the line). Never raises: any failure degrades
    this whole suffix to "" (matching the original function's own
    degrade-to-empty contract) rather than half-writing a corrupt line.

    EXTENDED 2026-09-20 (master plan WS2.4 step 1) with `` model_source=``/
    `` model_id=``/`` model_declared=`` -- the derived-reviewing-model
    fields. `model` above is now ALWAYS the value
    `derive_reviewing_model()` joined from spend.jsonl (never a caller's
    raw `--model`, mirroring `tier`'s own "always computed" contract);
    `model_source` is written verbatim as ``"ledger"`` whenever `model` was
    populated from a successful join, so a reader can tell a derived
    `model=` apart from the small number of pre-2026-09-20 lines that
    carried a self-reported one. `model_id` carries the RAW spend.jsonl
    model string (e.g. ``"claude-opus-5[1m]"``) the tier word was
    normalized from, sanitized the same way as `reviewer`/`corrects_from`
    since a raw model id can itself carry the compound-identity-length
    ballpark (e.g. a long fine-tuned-model spelling). `model_declared` is
    the audit-only field: populated ONLY when a caller's own `--model`
    flag disagreed with the derived value (or when nothing could be
    derived at all but a caller still declared one) -- exactly the same
    "disagreement is a signal, never silently trusted or silently dropped"
    contract `tier_declared` already established.
    """
    try:
        import datetime as _dt

        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = f" ts={ts}"
        if item:
            safe = _safe_field(item)
            if safe:
                out += f" item={safe}"
        if tier:
            out += f" tier={tier}"
        if tier_declared:
            safe = _safe_field(tier_declared)
            if safe:
                out += f" tier_declared={safe}"
        if reviewer:
            # FINDING 7 (minor): a compound identity can legitimately run up
            # to _MAX_REVIEWER_FIELD_LEN chars -- the general _safe_field
            # default of 80 would silently truncate straight through it.
            safe = _safe_field(reviewer, maxlen=_MAX_REVIEWER_FIELD_LEN)
            if safe:
                out += f" reviewer={safe}"
        if model:
            out += f" model={model}"
        if model_source:
            safe = _safe_field(model_source)
            if safe:
                out += f" model_source={safe}"
        if model_id:
            safe = _safe_field(model_id, maxlen=_MAX_REVIEWER_FIELD_LEN)
            if safe:
                out += f" model_id={safe}"
        if model_declared:
            safe = _safe_field(model_declared)
            if safe:
                out += f" model_declared={safe}"
        if round_ is not None:
            out += f" round={int(round_)}"
        if paths:
            joined, total = _paths_field(paths)
            if joined:
                out += f" paths={joined} paths_n={total}"
        if prev:
            safe = _safe_field(prev)
            if safe:
                out += f" prev={safe}"
        if vf:
            out += f" vf={vf}"
        if warm:
            out += " warm=1"
        if rekey:
            safe = _safe_field(rekey)
            if safe:
                out += f" rekey={safe}"
        if corrects_from:
            # Same maxlen rationale as `reviewer` above: the OLD value being
            # superseded can itself be a full compound identity.
            safe = _safe_field(corrects_from, maxlen=_MAX_REVIEWER_FIELD_LEN)
            if safe:
                out += f" corrects_from={safe}"
        if dg:
            # R7-B1: written verbatim -- `dg` is a small closed-vocabulary
            # version token (`_DIGEST_FORMAT_VERSION`, currently "2"),
            # never caller-supplied free text, so no sanitization is needed
            # (matching `warm=1`'s own verbatim-literal convention, not
            # reviewer='s free-text one).
            out += f" dg={dg}"
        return out
    except Exception:
        return ""


def decide(
    target: str,
    outcome: str | None = None,
    blockers: int | None = None,
    head_override: str | None = None,
    item: str | None = None,
    *,
    tier: str | None = None,
    tier_declared: str | None = None,
    reviewer: str | None = None,
    model: str | None = None,
    model_source: str | None = None,
    model_id: str | None = None,
    model_declared: str | None = None,
    round_: int | None = None,
    paths: list[str] | None = None,
    prev: str | None = None,
    vf: str | None = None,
    warm: bool = False,
    rekey: str | None = None,
    dg: str | None = None,
) -> Decision:
    """Pure decision: what should recording `target`'s HEAD (+ outcome) do?

    Resolves the repo root and HEAD via read-only git plumbing, consults the
    outcome-aware ledger, and returns a :class:`Decision`. Performs NO writes
    and NO logging (it DOES read the ledger — a read, not a write). Never
    raises.

    `outcome` is OUTCOME_CLEAN / OUTCOME_BLOCKERS / None (unspecified — the
    caller passed no outcome info at all). `blockers` is the finding count,
    used only when outcome == OUTCOME_BLOCKERS.

    `tier`/`tier_declared`/`reviewer`/`model`/`round_`/`paths`/`prev`/`vf`/
    `warm`/`rekey`/`dg` (2026-08-30, gate-optimization plan Item 6, Part B;
    `warm` added 2026-08-31, build-wave Lane B; `rekey` added 2026-09-01,
    AA-0064 fix round Item 8; `dg` added 2026-09-24, GH #5886 fix-round-4
    R7-B1) are the NEW trailing ledger fields —
    every one OPTIONAL and KEYWORD-ONLY (FINDING 8, 2026-08-30 review:
    matching `_entry_suffix`'s own `*`-guarded convention, so a
    future 9th field can be inserted without silently reordering any
    existing positional call), threaded straight through to
    `_entry_suffix` unchanged (this function does no validation of them;
    validation lives in `main()`'s `_parse_new_fields`/tier-computation/the
    warm-cap walk, so `decide()` stays a pure function of whatever it is
    handed, exactly as
    before). Like `item`, none of these appear at all on the legacy
    unspecified-outcome line (see the STATUS_RECORD branch below) — they
    only ever ride along on an outcome-bearing line (--clean/--blockers).

    `model_source`/`model_id`/`model_declared` (2026-09-20, master plan
    WS2.4 step 1) mirror `model`'s own extension: `model` itself is now
    ALWAYS the value `main()` derived from spend.jsonl (see
    `derive_reviewing_model`) before ever calling this function -- `decide()`
    still performs no derivation or validation of its own, exactly like it
    never validated `tier` (computed by the CALLER, `main()`, and handed in
    already-final).

    Ordering:
      1. target not a directory                        → STATUS_NOT_DIR
      2. target not a git repo                          → STATUS_NOT_REPO
      3. repo has no HEAD commit yet                     → STATUS_NO_HEAD
      4. HEAD has NO ledger entry yet                     → STATUS_RECORD
      5. HEAD on record, outcome unspecified OR IDENTICAL
         to what's already on record                      → STATUS_ALREADY
         (an unspecified call never overwrites a KNOWN
         existing outcome — no downgrade to "unknown")
      6. HEAD on record with a DIFFERENT known outcome     → STATUS_UPDATE
         (e.g. blockers found, then fixed and re-reviewed clean)
    """
    try:
        if not target or not os.path.isdir(target):
            return Decision(
                STATUS_NOT_DIR,
                f"record_review: not a directory: {target} (no-op)",
            )

        repo_root = _git(target, "rev-parse", "--show-toplevel")
        if not repo_root:
            return Decision(
                STATUS_NOT_REPO,
                f"record_review: {target} is not a git repo — nothing to record (no-op)",
            )

        # head_override carries a PRE-COMMIT content key ("precommit:<digest>")
        # instead of a sha — the whole record/update/already machinery below is
        # sha-agnostic, so a pre-commit review reuses it verbatim rather than
        # growing a parallel ledger that could drift out of step with this one.
        head = head_override or _git(repo_root, "rev-parse", "HEAD")
        if not head:
            return Decision(
                STATUS_NO_HEAD,
                f"record_review: {repo_root} has no HEAD commit yet — nothing to record (no-op)",
                repo_root=repo_root,
            )

        entry = f"{repo_root} {head}"
        short = head[:12]
        outcome_token = _outcome_token(outcome, blockers)  # None -> unspecified/unknown
        existing_token = _existing_outcome_token(_lib.LAST_REVIEWED, repo_root, head)
        suffix_kwargs = dict(
            tier=tier,
            tier_declared=tier_declared,
            reviewer=reviewer,
            model=model,
            model_source=model_source,
            model_id=model_id,
            model_declared=model_declared,
            round_=round_,
            paths=paths,
            prev=prev,
            vf=vf,
            warm=warm,
            rekey=rekey,
            dg=dg,
        )

        if existing_token is None:
            # A brand-new HEAD: write it, with the outcome suffix if we have one
            # (+ appended telemetry fields — outcome-bearing lines only).
            new_line = (
                entry
                if outcome_token is None
                else f"{entry} {outcome_token}{_entry_suffix(item, **suffix_kwargs)}"
            )
            phrase = f" ({_outcome_phrase(outcome_token)})" if outcome_token else ""
            return Decision(
                STATUS_RECORD,
                f"record_review: recorded review of HEAD {short} in {repo_root}{phrase}.",
                repo_root=repo_root,
                head=head,
                entry=new_line,
                outcome=outcome_token or "",
            )

        existing_first = (existing_token.split() or [""])[0] if existing_token else existing_token
        if outcome_token is None or outcome_token == existing_first:
            # Nothing new/better to record: an unspecified call never overwrites
            # a KNOWN existing outcome, and an identical outcome is a true no-op.
            existing_phrase = f" ({_outcome_phrase(existing_first)})" if existing_first else ""
            return Decision(
                STATUS_ALREADY,
                f"record_review: HEAD {short} in {repo_root} already recorded as reviewed{existing_phrase}.",
                repo_root=repo_root,
                head=head,
                entry=entry,
                outcome=existing_first or "",
            )

        # A DIFFERENT, KNOWN outcome for a HEAD already on record -> update in place.
        new_line = f"{entry} {outcome_token}{_entry_suffix(item, **suffix_kwargs)}"
        return Decision(
            STATUS_UPDATE,
            f"record_review: updated review outcome for HEAD {short} in {repo_root} "
            f"to {_outcome_phrase(outcome_token)}.",
            repo_root=repo_root,
            head=head,
            entry=new_line,
            outcome=outcome_token,
        )
    except Exception:
        # Degrade open: any unexpected failure becomes a clean no-op.
        return Decision(STATUS_NOT_REPO, "record_review: internal error (no-op)")


def _append_entry(entry: str) -> bool:
    """Create the state dir (0700) and append `entry` as a line to last_reviewed.

    Takes the SAME admission_lock primitive :func:`_update_entry` uses (see
    its docstring for why the ledger needs one at all). A lock around only
    `_update_entry`'s read-then-replace window would NOT fully close the
    race: `_update_entry` replaces the whole file with a snapshot taken at
    its OWN read time, so an unlocked, plain O_APPEND write from THIS
    function landing in between that read and that os.replace would still be
    silently discarded (it lands on the OLD inode, which the replace then
    swaps away). Both mutators of this ledger must therefore serialize on the
    same lock, not just the one with the obviously-dangerous read-modify-
    write shape. Fails CLOSED on an unavailable lock (returns False, skipping
    the write) rather than file_claims' "fail open" convention: unlike a
    spuriously-logged contest, an unprotected append here risks the exact
    DATA LOSS this lock exists to prevent, so a skipped-but-retryable append
    is the safer failure mode.

    Returns True on success, False on any failure. Never raises: matches the
    bash's best-effort ``mkdir -p`` / ``chmod 0700`` / ``>>`` with ``2>/dev/null``
    swallowing. The dir is chmod'd 0700 to keep the review ledger private.
    """
    try:
        os.makedirs(_lib.REVIEW_STATE_DIR, exist_ok=True)
    except Exception:
        return False
    try:
        os.chmod(_lib.REVIEW_STATE_DIR, 0o700)
    except Exception:
        # chmod is best-effort in the bash too; keep going.
        pass
    with ab.admission_lock(_lib.REVIEW_STATE_DIR, timeout_s=lock_timeout_from_env()) as locked:
        if not locked:
            return False  # fail CLOSED on the lock — see docstring
        try:
            with open(_lib.LAST_REVIEWED, "a", encoding="utf-8") as fh:
                fh.write(entry + "\n")
        except Exception:
            return False
        return True


def _update_entry(repo_root: str, head: str, new_line: str) -> bool:
    """Atomically REPLACE the ledger's existing line(s) for repo_root+head with
    `new_line`, preserving every other repo/HEAD's lines (and their order); the
    updated line is appended at the end. Used only for STATUS_UPDATE (a
    DIFFERENT outcome recorded for a HEAD already on record).

    REGRESSION 5 fix: this read-then-replace was an UNLOCKED read-modify-
    write on a ledger multiple concurrent sessions share — a concurrent
    session's `_append_entry` landing between this function's read and its
    `os.replace` was silently lost (that append reaches the OLD inode; the
    replace swaps in a NEW inode built purely from THIS read, discarding it).
    This ledger was append-only (and therefore lock-free-safe: a plain
    O_APPEND write is atomic on its own) before the outcome-aware feature
    added this rewrite; the fix takes the SAME admission_lock primitive
    file_claims.py/agent_budget.py already prove out, scoped to THIS ledger's
    own state dir (mirrors how file_claims/agent_budget each scope their own
    lock file to their own ledger dir — the lock file lives at
    REVIEW_STATE_DIR/admission.lock). `_append_entry` takes the SAME lock
    (see its docstring) so no interleaving between the two mutators is
    possible at all, not just within this function's own window.

    Creates the state dir (0700) as needed. Writes via a temp file in the SAME
    dir + os.replace so a crash mid-write can never corrupt/truncate the
    ledger — mirrors file_claims.py's atomic-write convention. Fails CLOSED
    on an unavailable lock (returns False — the update is skipped, not raced
    unprotected; a skipped-but-retryable update is recoverable, a lost
    concurrent write is not). Returns True on success, False on any failure
    (never raises).
    """
    needle = f"{repo_root} {head}"
    try:
        os.makedirs(_lib.REVIEW_STATE_DIR, exist_ok=True)
    except Exception:
        return False
    try:
        os.chmod(_lib.REVIEW_STATE_DIR, 0o700)
    except Exception:
        pass
    path = _lib.LAST_REVIEWED
    tmp = f"{path}.tmp.{os.getpid()}"
    with ab.admission_lock(_lib.REVIEW_STATE_DIR, timeout_s=lock_timeout_from_env()) as locked:
        if not locked:
            return False  # fail CLOSED on the lock — see docstring
        try:
            lines: list[str] = []
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    lines = [ln.rstrip("\n") for ln in fh]
            kept = [ln for ln in lines if not (ln == needle or ln.startswith(needle + " "))]
            kept.append(new_line)
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(kept) + "\n")
            os.replace(tmp, path)
            return True
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass
            return False


def _outcome_from_argv(args: list[str]) -> tuple[str | None, int | None]:
    """Parse ``--clean`` / ``--blockers <n>`` / ``--blockers=<n>`` out of a CLI
    arg list (already WITHOUT the script-name argv[0]).

    Returns (outcome, blockers): outcome is OUTCOME_CLEAN, OUTCOME_BLOCKERS, or
    None when `args` carries no recognized outcome flag. ``--blockers 0`` (or
    any non-positive count) IS itself a clean outcome — zero unresolved
    blockers is clean. A malformed ``--blockers`` value is ignored (that token
    is skipped; parsing continues). Never raises.
    """
    outcome: str | None = None
    blockers: int | None = None
    i = 0
    n_args = len(args)
    while i < n_args:
        a = args[i]
        if a == "--clean":
            outcome = OUTCOME_CLEAN
            i += 1
            continue
        if a == "--blockers" and i + 1 < n_args:
            n = _parse_int(args[i + 1])
            if n is not None:
                blockers = n
                outcome = OUTCOME_CLEAN if n <= 0 else OUTCOME_BLOCKERS
            i += 2
            continue
        if a.startswith("--blockers="):
            n = _parse_int(a[len("--blockers=") :])
            if n is not None:
                blockers = n
                outcome = OUTCOME_CLEAN if n <= 0 else OUTCOME_BLOCKERS
            i += 1
            continue
        i += 1
    return outcome, blockers


def _parse_int(raw: str) -> int | None:
    try:
        return int(raw)
    except Exception:
        return None


def _outcome_from_event(ev: dict) -> tuple[str | None, int | None]:
    """Parse an outcome from the JSON event payload — the SAME stdin already
    piped for `cwd` in the documented invocation (e.g.
    ``echo '{"cwd":"...", "blockers": 2}' | record_review.py`` or
    ``{"cwd":"...", "clean": true}``). Returns (None, None) when the payload
    carries neither recognized field. Never raises.
    """
    try:
        if ev.get("clean") is True:
            return OUTCOME_CLEAN, None
        if "blockers" in ev:
            n = int(ev["blockers"])
            return (OUTCOME_CLEAN if n <= 0 else OUTCOME_BLOCKERS), n
    except Exception:
        pass
    return None, None


def _resolve_outcome(argv: list[str], ev: dict) -> tuple[str | None, int | None]:
    """CLI flags win over the event payload; if the CLI carries no recognized
    outcome flag at all, fall back to the event payload; if NEITHER supplies
    one, the outcome is unspecified (None, None) — "outcome unknown".
    """
    outcome, blockers = _outcome_from_argv(argv[1:] if len(argv) > 1 else [])
    if outcome is not None:
        return outcome, blockers
    return _outcome_from_event(ev)


def _looks_like_plausible_target(candidate: str) -> bool:
    """True iff `candidate` is a real directory, or is at least SHAPED like
    a filesystem path that could plausibly be a not-yet-created directory --
    as opposed to a bare token (a sha, a stray flag value, an entire
    multi-word ledger line pasted by mistake) that leaked into the
    positional slot through an argv-parsing mistake.

    Deliberately a BASIC check, not exhaustive: `decide()` still performs
    the real, authoritative `os.path.isdir()` check right after target
    resolution -- this only decides whether a bad value gets a clear, loud
    `_positional_target` rejection (naming the likely-intended flags)
    INSTEAD of silently falling through to `decide()`'s far more generic
    "not a directory: X" message. Checked against the live enforcement
    log's actual failure shapes (2026-08-30): a bare 40-hex sha, a short
    sha prefix, and an entire accidentally-pasted ledger line
    (``"<repo> <sha> blockers:0"``, which DOES contain a "/" in its first
    path segment but also contains raw spaces) all correctly fail this
    check. Never raises.
    """
    if not candidate:
        return False
    try:
        if os.path.isdir(candidate):
            return True
        if candidate != candidate.strip() or " " in candidate:
            # A raw space is a strong signal of a parsing accident (e.g. an
            # entire ledger line landing in one argv token) -- a real
            # directory WITH a space in its name is still caught by the
            # isdir() check above, so this only ever rejects a
            # NON-existent, space-containing value.
            return False
        expanded = os.path.expanduser(candidate)
        return "/" in expanded or expanded in (".", "..")
    except Exception:
        return False


def _positional_target(argv: list[str]) -> str | None:
    """The first CLI token that is a plain positional (the target dir).

    Mirrors the bash ``${1:-$PWD}`` convention while tolerating every
    recognized flag (see `_RECOGNIZED_FLAGS`) anywhere after argv[0].
    Returns None when no positional token is present (an empty string is
    not a positional either — it must not win over the event cwd).

    ROOT-CAUSE FIX (2026-08-30, gate-optimization plan Item 6, PART A):
    this used to return the first token it did not recognize as a flag —
    including an unrecognized ``--``-prefixed flag itself, or an
    implausible non-flag value (a sha, a stray flag value that leaked
    through a parsing mistake) — silently handing either back as "the
    target directory". `decide()` then correctly rejected it as
    STATUS_NOT_DIR, but the caller saw exit 0 and a generic message,
    indistinguishable from success — already happening live: 114 calls in
    the enforcement log (106 ``--help``, 3 other unrecognized flags, 5
    sha/path-shaped mistargets), every one recording nothing. This now
    raises :class:`ArgvError` LOUDLY for BOTH failure shapes instead,
    caught in exactly one place (`main()`).
    """
    # Pass 1: every "--"-prefixed token ANYWHERE in argv must be a
    # RECOGNIZED flag NAME (the part before "="). Scanned over the whole
    # argv up front (not just up to the first positional) so an
    # unrecognized flag is caught even when a valid positional happens to
    # appear earlier in the token list.
    for tok in argv[1:]:
        if tok.startswith("--"):
            name = tok.split("=", 1)[0]
            if name not in _RECOGNIZED_FLAGS:
                raise ArgvError(
                    f"record_review: unrecognized flag {tok!r}. Did you mean "
                    "--tier / --model / --reviewer / --reviewer-agent-id / "
                    "--reviewer-tool-use-id / --round / --paths / "
                    "--prev / --vf / --clean / --blockers / --item / "
                    "--pre-commit / --battery / --warm / --rekey / "
                    "--correct-identity? Nothing recorded."
                )

    # Pass 2: walk again, skipping every recognized flag (and its value(s))
    # per its registered arity, to find the first genuine positional token.
    i = 1
    n_args = len(argv)
    while i < n_args:
        a = argv[i]
        if a.startswith("--"):
            name = a.split("=", 1)[0]
            arity = _RECOGNIZED_FLAGS[name]  # guaranteed present after pass 1
            if arity == _ARITY_ZERO:
                i += 1
            elif arity == _ARITY_ONE:
                i += 1 if "=" in a else 2
            else:  # _ARITY_VARIADIC — currently only --paths
                i += 1
                while i < n_args and not argv[i].startswith("--"):
                    i += 1
            continue
        if a:
            if not _looks_like_plausible_target(a):
                raise ArgvError(
                    f"record_review: not a directory: {a!r}, and it does not "
                    "look like a real (or plausible not-yet-created) path -- "
                    "did you mean --tier / --model / --paths? Nothing recorded."
                )
            return a
        i += 1
    return None


def _looks_like_a_flag_name(value: str) -> bool:
    """True iff `value` is ITSELF a recognized `_RECOGNIZED_FLAGS` name (the
    part before "="), rather than a genuine value.

    FINDING 7 (2026-08-30 review): `--reviewer`/`--prev`/`--item` used to
    swallow a FOLLOWING recognized flag as their own value whenever the
    caller forgot to actually supply one (e.g. ``--reviewer --clean``
    silently recorded ``reviewer="--clean"``), while `--model`/`--round`/
    `--vf` already rejected this loudly -- not by design, but as a side
    effect of THEIR OWN closed-value-set validation (``"--clean"`` happens
    to be neither a valid model, an integer, nor a vf token). This helper
    gives `--reviewer`/`--prev`/`--item` -- which have no closed value set
    of their own -- the equivalent loud rejection, for consistency. Never
    raises."""
    if not value or not value.startswith("--"):
        return False
    name = value.split("=", 1)[0]
    return name in _RECOGNIZED_FLAGS


def _item_from_argv(argv: list[str]) -> str | None:
    """The optional ``--item <key>`` / ``--item=<key>`` work-item tag (#4400
    churn telemetry). None when absent or valueless.

    Raises :class:`ArgvError` when the captured value is itself a
    recognized flag name (FINDING 7) -- the caller (`main`) is expected to
    invoke this from inside its existing argv-validation `try`/`except
    ArgvError` block, matching `_parse_new_fields`.
    """
    n_args = len(argv)
    value: str | None = None
    for i, a in enumerate(argv):
        if a == "--item" and i + 1 < n_args and argv[i + 1]:
            value = argv[i + 1]
            break
        if a.startswith("--item="):
            value = a[len("--item=") :] or None
            break
    if value is not None and _looks_like_a_flag_name(value):
        raise ArgvError(
            f"record_review: --item {value!r} looks like a flag name, not a "
            "value -- did you forget --item's own value? Nothing recorded."
        )
    return value


def _paths_from_argv(argv: list[str]) -> list[str]:
    """The variadic `--paths a b c` list, or [] when absent."""
    out: list[str] = []
    i = 1
    n_args = len(argv)
    while i < n_args:
        if argv[i] == "--paths":
            i += 1
            while i < n_args and not argv[i].startswith("--"):
                if argv[i]:
                    out.append(argv[i])
                i += 1
            continue
        i += 1
    return out


def _value_from_argv(argv: list[str], flag: str) -> str | None:
    """The value of a recognized ONE-arg CLI flag (space or "=" form), or
    None when absent or valueless. Assumes `flag` is already a legal
    `_RECOGNIZED_FLAGS` name -- this is a pure value extractor, not a
    flag-legality check (that happens in `_positional_target`'s pass 1).
    Never raises."""
    n_args = len(argv)
    prefix = flag + "="
    for i, a in enumerate(argv):
        if a == flag and i + 1 < n_args:
            return argv[i + 1]
        if a.startswith(prefix):
            return a[len(prefix):] or None
    return None


def _parse_new_fields(argv: list[str]) -> dict:
    """Parse + VALIDATE every new trailing-field CLI flag (Item 6, Part B):
    --reviewer, --model, --round, --prev, --vf, and the --tier DECLARATION
    (never the recorded tier= itself -- see `decide()`'s own docs for why
    that is always computed, never trusted from this flag).

    Raises :class:`ArgvError` on any recognized-but-INVALID value (--model
    not one of opus/sonnet/haiku, --round not an integer >= 1, --vf not one
    of the 7 verify_fix.py verdict tokens) -- these are never silently
    dropped or coerced into something plausible-looking; an invalid value
    here means NOTHING is recorded for this call, matching Part A's "loud,
    not silent" standard for the whole module. Never returns a
    partially-validated result: either every field present in `argv`
    validates, or this raises before `decide()` is ever reached.
    """
    fields: dict = {}

    reviewer = _value_from_argv(argv, "--reviewer")
    if reviewer:
        if _looks_like_a_flag_name(reviewer):
            # FINDING 7 (2026-08-30 review): --reviewer has no closed value
            # set of its own (unlike --model/--round/--vf below), so it
            # never got their INCIDENTAL loud rejection of a swallowed
            # following flag -- give it the same rejection explicitly.
            raise ArgvError(
                f"record_review: --reviewer {reviewer!r} looks like a flag "
                "name, not a value -- did you forget --reviewer's own "
                "value? Nothing recorded."
            )
        # BLOCKER 3 (2026-08-30 review): this bare --reviewer path had no
        # closed charset of its own, unlike --reviewer-agent-id/
        # --reviewer-tool-use-id below (_SAFE_ID_RE excludes "#") -- a value
        # like "a#b#c" reached the ledger's reviewer= field verbatim (that
        # field's own sanitizer, `_safe_field` in `_entry_suffix`, allows
        # "#" through, since "#" is the compound form's OWN separator and
        # must survive sanitization for a REAL compound value) and
        # `parse_reviewer_value` would then misparse it as a fabricated
        # 3-part compound identity that was never actually claimed. Routed
        # through the SAME safe-character validation used for the type
        # component of a real compound identity (`_safe_reviewer_type`,
        # which excludes "#" -- see that function's own docstring for the
        # identical "#" desync reasoning `_SAFE_PATH_RE` documents for
        # paths=) so a stray "#" here is sanitized to "_" rather than
        # silently faking an extra identity boundary downstream.
        fields["reviewer"] = _safe_reviewer_type(reviewer)

    # Item 6b (2026-08-30, gate-optimization plan): the dispatch-lease
    # identity that joins this reviewer= entry to a real
    # ~/.claude/.agent_budget/spend.jsonl row. Both-or-neither: a lone
    # --reviewer-agent-id or --reviewer-tool-use-id is a caller mistake
    # (the two together identify exactly ONE sub-agent dispatch; either
    # alone is not a usable join key) and is rejected loudly, matching this
    # module's "loud, not silent" standard rather than silently recording a
    # useless partial identity.
    reviewer_agent_id = _value_from_argv(argv, "--reviewer-agent-id")
    reviewer_tool_use_id = _value_from_argv(argv, "--reviewer-tool-use-id")
    if reviewer_agent_id is not None or reviewer_tool_use_id is not None:
        if not (reviewer_agent_id and reviewer_tool_use_id):
            raise ArgvError(
                "record_review: --reviewer-agent-id and "
                "--reviewer-tool-use-id must be supplied TOGETHER (both "
                "identify the SAME sub-agent dispatch in spend.jsonl) -- "
                "got only one. Nothing recorded."
            )
        for flag_name, val in (
            ("--reviewer-agent-id", reviewer_agent_id),
            ("--reviewer-tool-use-id", reviewer_tool_use_id),
        ):
            if _looks_like_a_flag_name(val) or not _SAFE_ID_RE.match(val):
                raise ArgvError(
                    f"record_review: {flag_name} {val!r} does not look like "
                    "a real spend.jsonl id (expected letters/digits/"
                    "underscore/hyphen, starting with a letter or digit). "
                    "Nothing recorded."
                )
        fields["reviewer"] = compose_reviewer_field(
            fields.get("reviewer"), reviewer_agent_id, reviewer_tool_use_id
        )

    model = _value_from_argv(argv, "--model")
    if model is not None:
        if model not in _VALID_MODELS:
            raise ArgvError(
                f"record_review: --model {model!r} is not one of "
                f"{sorted(_VALID_MODELS)}. Nothing recorded."
            )
        fields["model"] = model

    round_raw = _value_from_argv(argv, "--round")
    if round_raw is not None:
        n = _parse_int(round_raw)
        if n is None or n < 1:
            raise ArgvError(
                f"record_review: --round {round_raw!r} must be an integer "
                ">= 1. Nothing recorded."
            )
        fields["round"] = n

    prev = _value_from_argv(argv, "--prev")
    if prev:
        if _looks_like_a_flag_name(prev):
            # FINDING 7: same rationale as --reviewer above.
            raise ArgvError(
                f"record_review: --prev {prev!r} looks like a flag name, "
                "not a value -- did you forget --prev's own value? "
                "Nothing recorded."
            )
        # AA-0049 (2026-08-31, build-wave Lane B): --prev had NO shape
        # validation at all -- any string was written verbatim, which is
        # exactly how a truncated value (the REAL live corruption is
        # `prev=precommit:29` / `prev=precommit:0a` -- 2-hex-digit
        # truncations of a real 16-digit digest; an earlier draft of this
        # comment cited "ommit:29", a `grep -o` artifact that dropped the
        # "precommit:" prefix, corrected here) and a self-referential chain
        # (prev= equal to the entry's OWN digest) both reached the live
        # ledger with no error. A chain predecessor is always either a
        # FIXED-WIDTH pre-commit content digest or a legacy plain-HEAD sha,
        # never free text and never an off-width hex run -- reject anything
        # else loudly rather than writing it.
        if not _PREV_RE.match(prev):
            raise ArgvError(
                f"record_review: --prev {prev!r} does not match "
                "'precommit:<16-hex-digit digest>' or 'sha:<7-40-hex-digit "
                "sha>' -- a chain predecessor must be a real, correctly-"
                "sized ledger key, not free text or a truncated digest. "
                "Nothing recorded."
            )
        # A --prev with no --round is meaningless as a chain link: every
        # existing prev=-carrying ledger entry also carries round= (see the
        # CLAUDE.md §10 warm-round recording paragraph this shape mirrors),
        # and the warm-cap walk below needs round= to reconstruct chain
        # order. Required NOW, not silently defaulted.
        if "round" not in fields:
            raise ArgvError(
                "record_review: --prev requires --round (a chain link needs "
                "its own round number to reconstruct order). Nothing recorded."
            )
        fields["prev"] = prev

    # REGRESSION 3 (round-2 review, 2026-08-31): --warm with no --prev
    # bypassed the whole cap -- _consecutive_warm_round_count needs a
    # prev_key to walk FROM, and main()'s "if prev_value: ... if warm: ..."
    # structure never even attempts the walk when prev_value is falsy, so a
    # bare `--warm` (no --prev) silently wrote warm=1 with zero enforcement.
    # Symmetric with --prev-requires---round above: --warm requires BOTH
    # --round and --prev (which itself already requires --round, so this
    # is really "requires --prev"; --round is named too so the message is
    # unambiguous even if a future edit ever decouples the two checks).
    if "--warm" in argv:
        if "prev" not in fields or "round" not in fields:
            raise ArgvError(
                "record_review: --warm requires --prev and --round (a warm "
                "round only means something as a link in a prev=-tracked "
                "chain -- without --prev the consecutive-warm-round cap "
                "cannot be enforced at all). Nothing recorded."
            )

    vf = _value_from_argv(argv, "--vf")
    if vf is not None:
        if vf not in _VALID_VF_TOKENS:
            raise ArgvError(
                f"record_review: --vf {vf!r} is not one of "
                f"{sorted(_VALID_VF_TOKENS)}. Nothing recorded."
            )
        fields["vf"] = vf

    tier_declared_raw = _value_from_argv(argv, "--tier")
    if tier_declared_raw:
        if _looks_like_a_flag_name(tier_declared_raw):
            # F1 (2026-08-30 round-3 review): --tier was left out of the
            # FINDING 7 pass above -- it's the fourth one-arg flag with no
            # closed value set (like --reviewer/--prev), and the one whose
            # entire purpose is to be an audit signal, so a swallowed flag
            # here is the worst place for it to happen silently. Same
            # rejection as --reviewer/--prev.
            raise ArgvError(
                f"record_review: --tier {tier_declared_raw!r} looks like a "
                "flag name, not a value -- did you forget --tier's own "
                "value? Nothing recorded."
            )
        fields["tier_declared_raw"] = tier_declared_raw

    return fields


_MUT_RE = re.compile(r"^(\d+)/(\d+)$")


def _battery_entry(caught_total: str | None, stale: str | None) -> str | None:
    """Build the ``battery:<ts> mut=<caught>/<total> stale=<n>`` ledger line
    for a mutation-battery run result, or None when the inputs don't
    validate (never write a malformed battery entry -- the same "loud, not
    silent" standard as everything else new in this module; the caller
    prints an explicit refusal rather than writing garbage)."""
    m = _MUT_RE.match(caught_total or "")
    if not m:
        return None
    stale_n = _parse_int(stale or "")
    if stale_n is None or stale_n < 0:
        return None
    import datetime as _dt

    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{BATTERY_PREFIX}{ts} mut={m.group(1)}/{m.group(2)} stale={stale_n}"


def _current_digest_key(target: str, head_override: str | None) -> str | None:
    """The ledger key THIS recording call would write for repo_root+HEAD,
    in the same ``(precommit|sha):<hex>`` shape `--prev` is validated
    against -- used only to catch a self-referential ``--prev`` (AA-0049: a
    chain cannot be its own predecessor). `head_override` is already
    ``precommit:<digest>`` when `--pre-commit` was used (see
    `_target_from_event`'s caller in `main`); otherwise this resolves the
    plain HEAD sha itself and prefixes it ``sha:`` to match `_PREV_RE`'s
    legacy-form spelling. Read-only; returns None on any git failure
    (self-reference simply can't be checked, never a false positive).
    Never raises.
    """
    if head_override:
        return head_override
    try:
        repo_root = _git(target, "rev-parse", "--show-toplevel")
        if not repo_root:
            return None
        head = _git(repo_root, "rev-parse", "HEAD")
        if not head:
            return None
        return f"sha:{head}"
    except Exception:
        return None


def _ledger_lookup_key(key: str) -> str:
    """`prev_key` (always ``(precommit|sha):<hex>``, per `_PREV_RE`) as the
    literal `head` token the ledger actually stores for that entry.

    A ``precommit:<digest>`` key is used VERBATIM: `decide()`'s
    `head_override` path writes ``f"{repo_root} {head}"`` with `head`
    already equal to the full ``precommit:<digest>`` string (see
    `_current_digest_key`'s own docs) -- the on-ledger key and the
    ``--prev`` spelling are identical for this form.

    A ``sha:<hex>`` key is NOT stored that way, though (REGRESSION 2,
    round-2 review, 2026-08-31): a plain (non-``--pre-commit``) recording's
    `decide()` writes the BARE sha with no prefix at all
    (``entry = f"{repo_root} {head}"``, `head` = a raw ``git rev-parse
    HEAD`` output) -- only `_current_digest_key`'s OWN synthesized
    ``--prev``-comparison spelling adds the ``sha:`` prefix, purely so
    `_PREV_RE` has one consistent two-form grammar to validate against.
    Passing a ``sha:``-prefixed key straight into `_existing_outcome_token`
    therefore NEVER matched any real entry, silently no-op'ing the entire
    warm-cap walk for every sha-chained round -- reproduced live by the
    round-2 reviewer. Stripping the prefix here (and ONLY here, at the
    ledger-lookup boundary -- the accepted `--prev`/stored `prev=` SPELLING
    stays ``sha:<hex>`` throughout the rest of this module) fixes the
    lookup without touching the validated/recorded shape at all.
    """
    if key.startswith("sha:"):
        return key[len("sha:") :]
    return key


def _consecutive_warm_round_count(
    last_reviewed_path: str, repo_root: str, prev_key: str
) -> int:
    """Walks BACKWARD from `prev_key` through the ledger's `prev=`-linked
    chain, counting consecutive entries recorded with `warm=1`, stopping at
    the first non-warm (cold) entry, an entry with no further `prev=` link,
    or an entry this walk cannot find (a dangling/foreign `prev=`, treated
    as chain-end -- never an infinite loop, never a crash). `repo_root`
    scopes the lookup exactly like `_existing_outcome_token` (a bare digest
    key is meaningless without its repo). Read-only; never raises; returns
    0 when `prev_key` itself is not found (nothing to count).

    Every `key` in the walk (the initial `prev_key`, and every subsequent
    `prev=` pulled off a found entry) is passed through
    `_ledger_lookup_key` before the actual ledger lookup, so a
    ``sha:``-prefixed chain link resolves against the BARE sha the ledger
    really stores for a plain-HEAD recording (REGRESSION 2) -- `seen` still
    tracks the ORIGINAL (possibly ``sha:``-prefixed) key exactly as read
    from `prev=`, so a chain mixing precommit and sha-keyed links can never
    false-loop on the lookup-only transformation.

    This is `decide()`-external and DELIBERATELY pure-read (no ledger
    write, no interaction with the admission lock) -- `main()` calls it
    BEFORE deciding whether to proceed to `decide()`/the actual write, so a
    refused call never touches the lock at all, matching every other
    argv-validation refusal in this module (loud, nothing recorded, no
    side effect beyond the printed message).
    """
    count = 0
    key = prev_key
    seen: set[str] = set()
    while key and key not in seen:
        seen.add(key)
        token = _existing_outcome_token(last_reviewed_path, repo_root, _ledger_lookup_key(key))
        if token is None:
            break
        fields = parse_ledger_fields(token)
        if fields.get("warm") != "1":
            break
        count += 1
        key = fields.get("prev")
    return count


def _target_from_event(ev: dict, argv: list[str]) -> str:
    """Resolve the directory to record.

    Precedence mirrors ``mark_reviewed.sh [dir]`` extended for hook use:
      1. an explicit CLI positional arg (skipping any outcome flags) — the
         bash's ``${1:-$PWD}``,
      2. the event's cwd / project_dir (via _lib.cwd, which falls back to
         os.getcwd() when the payload carries neither).
    """
    pos = _positional_target(argv)
    if pos:
        return pos
    return _lib.cwd(ev)


def main(argv: list[str] | None = None) -> int:
    """Thin entrypoint: read event, decide, (maybe) write, log; exit 0, or 1 when
    LOG-ONLY skipped a write the caller requested.

    Side effects (writing the last_reviewed ledger) happen only when
    :func:`_lib.enforcing` is ON for the target; otherwise the run is LOG-ONLY
    (it records a ``would-record`` decision without touching the ledger). The
    master OFF switch ``CSA_DISABLE_HOOKS=1`` makes the whole thing a clean no-op.

    Returns 0, except 1 when a write (record, update, ``--battery``,
    ``--correct-identity``) was requested while LOG-ONLY (see ``_LOG_ONLY_HINT``):
    nothing was written, and saying so on stderr with a non-zero exit is what
    keeps a caller from believing the review is on record. An already-recorded
    HEAD and the informational no-op statuses skipped no write and return 0.
    Recording is never a deny/block, so this emits neither a PreToolUse deny
    nor a Stop block.

    Outcome resolution (CLI > event payload > unspecified) happens BEFORE
    :func:`decide` so a passed-but-unenforced outcome still shows up correctly
    in the "would-record"/"would-update" LOG-ONLY log line — the outcome is
    part of the DECISION, not an enforcement-time detail.

    ROOT-CAUSE FIX + Part B (2026-08-30, gate-optimization plan Item 6):
    argv-shape validation (unrecognized flags, an implausible positional
    target, an invalid --model/--round/--vf value) now happens FIRST, via
    :class:`ArgvError`, before anything touches git or the ledger — a bad
    call is refused loudly with nothing recorded, never a silent no-op. A
    ``--battery`` call is a wholly separate write path (no repo_root/HEAD
    at all) handled in its own branch, short-circuiting before outcome
    resolution. tier= is always COMPUTED from `review_risk_tier.classify()`
    on the same normalized pathspec `--pre-commit` digests, never trusted
    from a caller-declared ``--tier``.

    EXTENDED 2026-08-31 (build-wave Lane B, AA-0048/AA-0049, CLAUDE.md §10's
    warm-round paragraph) with three more loud, nothing-recorded refusals,
    all checked AFTER argv-shape validation and `head_override` resolution
    but BEFORE `decide()`/any write: (1) ``--prev`` must match
    ``(precommit|sha):<hex>`` (`_parse_new_fields`, via `_PREV_RE`) and (2)
    ``--prev`` requires ``--round`` alongside it (also `_parse_new_fields`)
    — both are argv-shape checks, so they raise :class:`ArgvError` exactly
    like the pre-existing ones; (3) ``--prev`` may not equal this
    recording's OWN computed digest (`_current_digest_key`) — a
    self-referential chain — and, when ``--warm`` is also passed, the
    THIRD consecutive warm full round on one ``prev=``-linked chain is
    refused (`_consecutive_warm_round_count`), printing the cold-dispatch
    instruction. (3) is not an argv-shape defect (it depends on git/ledger
    state), so it is checked directly in this function rather than raising
    ArgvError, but follows the identical contract: nothing is recorded, and
    the refusal is `_lib.log`ged for visibility.
    """
    argv = list(sys.argv if argv is None else argv)

    # Master OFF: do nothing at all (not even log), matching the bash kill switch.
    if _lib.disabled():
        return 0

    try:
        ev = _lib.read_event()
    except Exception:
        ev = {}

    try:
        target = _target_from_event(ev, argv)
        new_fields = _parse_new_fields(argv)
        # Parsed here (not at its original call site further down) so a
        # FINDING 7 rejection (--item swallowing a following recognized
        # flag as its own value) is caught by this SAME argv-validation
        # block, exactly like --reviewer/--model/--round/--prev/--vf/--tier
        # above -- one place, one "loud, not silent" boundary.
        item = _item_from_argv(argv)
    except ArgvError as exc:
        print(str(exc))
        _lib.log(HOOK, "argv-error", detail=str(exc)[:300])
        return 0

    # --battery: records a mutation-battery run result under its OWN
    # "battery:<ts>" namespace (never "precommit:") -- no repo_root/HEAD/
    # digest at all, so it never touches decide(). Short-circuits here,
    # before outcome resolution (a battery run carries no clean/blockers
    # outcome in that sense).
    if "--battery" in argv:
        mut_raw = _value_from_argv(argv, "--mut")
        stale_raw = _value_from_argv(argv, "--stale")
        line = _battery_entry(mut_raw, stale_raw)
        if line is None:
            print(
                "record_review: --battery needs --mut <caught>/<total> and "
                "--stale <n> (both required, non-negative integers). "
                "Nothing recorded."
            )
            _lib.log(HOOK, "battery-invalid", mut=mut_raw, stale=stale_raw)
            return 0
        on = _lib.enforcing(target)
        if on:
            wrote = _append_entry(line)
            if wrote:
                print(f"record_review: recorded mutation-battery result: {line}")
            else:
                print(
                    "record_review: NOT recorded — the ledger lock was "
                    "unavailable (another agent is writing). Nothing was "
                    "written; re-run this command."
                )
            _lib.log(
                HOOK, "battery-recorded" if wrote else "battery-record-failed", line=line
            )
        else:
            print(f"record_review: (LOG-ONLY) would record mutation-battery result: {line}")
            _lib.log(HOOK, "battery-would-record", line=line)
            # Same contract as the HEAD/--pre-commit record path below: a write
            # the caller asked for that LOG-ONLY skipped exits non-zero.
            print(f"record_review: NOT recorded {_LOG_ONLY_HINT}", file=sys.stderr)
            return 1
        return 0

    # --correct-identity (#5133): corrects ONLY the reviewer-identity
    # fields (reviewer=/its agent_id+tool_use_id components, and prev=) on
    # an EXISTING ledger entry for an EXACT key the caller names -- never
    # the outcome, paths, or digest. A mistyped --reviewer-tool-use-id used
    # to be permanent: re-recording the same digest was refused
    # ("already recorded" -- decide()'s STATUS_ALREADY), so a typo was
    # indistinguishable from a genuine forged identity to any later audit
    # forever. This is its own write path (like --battery/--rekey), never
    # touching decide() -- decide()'s RECORD/UPDATE/ALREADY machinery exists
    # to decide whether a NEW outcome should be recorded for a HEAD; a
    # correction is orthogonal to that (it targets a key that MUST already
    # have an entry, and never changes the outcome), so reusing it would
    # only add irrelevant branches to reason about.
    #
    # Storage: APPENDS a new ledger line at the SAME repo_root+key as the
    # original (never rewrites/removes the miscorrected line) -- this
    # mirrors the ledger's own pre-existing append-only convention
    # (`_append_entry`, and every reader's "last matching line wins"
    # semantics -- see `_existing_outcome_token`'s own docstring). Every
    # consumer of this ledger (`precommit_review_gate.decide` via
    # `rr.head_review_outcome`/`_existing_outcome_token`,
    # `head_review_reviewer_identity`, `find_clean_precommit_entry_for_paths`)
    # already resolves "the LAST line for this key" — an appended correction
    # is therefore picked up automatically by every existing reader with
    # ZERO parser changes, exactly as a --rekey/STATUS_UPDATE line already
    # is. The ORIGINAL (wrong) line stays on disk, readable in full — the
    # correction is auditable (who corrected what, when, what the prior
    # value was), never a silent overwrite (a silent overwrite would make
    # forgery EASIER: a forger could "correct" a fabricated identity into a
    # copied real one with no trace at all).
    correct_key = _value_from_argv(argv, "--correct-identity")
    if correct_key is not None:
        if not _PREV_RE.match(correct_key):
            print(
                f"record_review: --correct-identity {correct_key!r} does not match "
                "'precommit:<16-hex-digit digest>' or 'sha:<7-40-hex-digit sha>' -- "
                "a correction target must be a real, correctly-sized ledger key, "
                "not free text or a truncated digest. Nothing recorded."
            )
            _lib.log(HOOK, "correct-identity-invalid-key", target=target, key=correct_key)
            return 0
        if "--pre-commit" in argv or "--rekey" in argv or "--battery" in argv:
            print(
                "record_review: --correct-identity is mutually exclusive with "
                "--pre-commit / --rekey / --battery -- it targets an EXISTING "
                "entry by its exact key, never a freshly-computed one. "
                "Nothing recorded."
            )
            _lib.log(HOOK, "correct-identity-conflicting-mode", target=target)
            return 0
        # F4 (2026-09-09 fix round, #5133): --warm/--round/--prev/
        # --paths/--model used to be accepted SILENTLY alongside
        # --correct-identity, with zero effect -- a caller passing any of
        # them (e.g. copy-pasting a warm-round recording command and
        # swapping in --correct-identity) would reasonably believe they
        # were carried into the correction, when in truth
        # `_rebuild_corrected_token` never even looks at them (it only ever
        # touches reviewer=/corrects_from=/corrected_at=, per its own
        # docstring's byte-fidelity contract). Silent-no-effect is exactly
        # the "loud, not silent" standard this module holds everywhere else
        # (Part A of the 2026-08-30 gate-optimization pass) -- refuse each
        # one explicitly, naming that correction mode changes reviewer
        # identity ONLY, rather than let a caller believe something happened
        # that didn't.
        _CORRECT_IDENTITY_INERT_FLAGS = ("--warm", "--round", "--prev", "--paths", "--model")
        for inert_flag in _CORRECT_IDENTITY_INERT_FLAGS:
            if any(a == inert_flag or a.startswith(inert_flag + "=") for a in argv):
                # 2026-09-20 (WS2.4 step 1): model= is the one exception to
                # "carried forward untouched" -- it is RE-DERIVED from the
                # corrected identity (see the re-derivation block below),
                # never carried forward AND never accepted as a caller
                # declaration here either way -- a --model flag alongside
                # --correct-identity is refused for the same reason it was
                # always refused: this mode changes IDENTITY, and the
                # correct model= for that identity is derived, not typed.
                print(
                    f"record_review: --correct-identity is mutually exclusive with "
                    f"{inert_flag} -- correction mode changes the recorded "
                    "reviewer IDENTITY only (warm/round/prev/paths are carried "
                    "forward untouched from the existing entry; model= is "
                    "RE-DERIVED from the corrected identity, never carried "
                    f"forward and never caller-declared) regardless of what you "
                    f"pass here. Drop {inert_flag}. Nothing recorded."
                )
                _lib.log(
                    HOOK,
                    "correct-identity-inert-flag",
                    target=target,
                    key=correct_key,
                    flag=inert_flag,
                )
                return 0
        if "--clean" in argv or any(
            a == "--blockers" or a.startswith("--blockers=") for a in argv
        ):
            print(
                "record_review: --correct-identity never changes the recorded "
                "OUTCOME -- it carries the existing entry's outcome forward "
                "unchanged. Drop --clean/--blockers (get a fresh review instead "
                "if the outcome itself is wrong). Nothing recorded."
            )
            _lib.log(HOOK, "correct-identity-outcome-flag-conflict", target=target)
            return 0

        new_reviewer = new_fields.get("reviewer")
        if not new_reviewer:
            print(
                "record_review: --correct-identity needs the CORRECTED identity: "
                "--reviewer <type> --reviewer-agent-id <id> --reviewer-tool-use-id "
                "<id> (or at minimum --reviewer <type>). Nothing recorded."
            )
            _lib.log(HOOK, "correct-identity-no-new-reviewer", target=target, key=correct_key)
            return 0

        # NOTE: `--correct-identity` needs no `--paths` at all (it targets an
        # existing key directly), so this branch runs BEFORE `paths`/
        # `repo_root_for_fields` are computed further down -- resolved fresh
        # here rather than depending on that later state.
        repo_root_for_correction = _git(target, "rev-parse", "--show-toplevel")
        if not repo_root_for_correction:
            print(f"record_review: {target} is not a git repo — nothing to correct (no-op)")
            _lib.log(HOOK, "correct-identity-not-a-repo", target=target)
            return 0

        # `correct_key` is validated above against `_PREV_RE`'s two accepted
        # SPELLINGS (`precommit:<digest>` or `sha:<hex>`) -- but a legacy
        # plain-HEAD recording's `decide()` stores the BARE sha with no
        # `sha:` prefix at all (REGRESSION 2, see `_ledger_lookup_key`'s own
        # docstring for the full history: only the --prev/--rekey COMPARISON
        # spelling adds the prefix, purely so `_PREV_RE` has one grammar to
        # validate against). Resolved here via the SAME helper the warm-cap
        # chain walk already uses for this exact translation, so a
        # `--correct-identity sha:<hex>` call actually finds the real
        # on-disk legacy entry instead of silently matching nothing.
        lookup_key = _ledger_lookup_key(correct_key)
        existing_token = _existing_outcome_token(
            _lib.LAST_REVIEWED, repo_root_for_correction, lookup_key
        )
        if existing_token is None:
            print(
                f"record_review: --correct-identity {correct_key!r} has no review "
                "on record at all for this repo -- there is nothing to correct. "
                "Nothing recorded."
            )
            _lib.log(
                HOOK, "correct-identity-no-prior-entry", target=target, key=correct_key
            )
            return 0

        # A truly bare/legacy entry (no outcome suffix at all, or an
        # outcome-bearing line recorded before the reviewer= field existed
        # -- either way, no `k=v` telemetry of ANY kind on record) has no
        # position for a reviewer= field under this ledger's own grammar
        # (`parse_ledger_fields` always treats the FIRST token as the
        # outcome word, never a field -- see `_rebuild_corrected_token`'s
        # own docstring for why this is structural, not a gap this fix
        # could paper over). Nothing to correct: refused loudly rather than
        # writing a line whose reviewer= would round-trip back to lost.
        if not existing_token or " " not in existing_token:
            print(
                f"record_review: --correct-identity {correct_key!r} has no "
                "reviewer= identity on record at all (a bare/legacy entry with "
                "no telemetry fields) -- there is nothing to correct. Nothing "
                "recorded."
            )
            _lib.log(
                HOOK, "correct-identity-no-identity-field", target=target, key=correct_key
            )
            return 0

        existing_fields = parse_ledger_fields(existing_token)
        old_reviewer = existing_fields.get("reviewer")

        if old_reviewer == new_reviewer:
            print(
                f"record_review: --correct-identity: the corrected reviewer= value "
                f"is IDENTICAL to what is already on record for {correct_key!r} -- "
                "nothing to correct (idempotent). Nothing recorded."
            )
            _lib.log(
                HOOK, "correct-identity-no-change", target=target, key=correct_key
            )
            return 0

        # Rebuild the corrected line by copying the ENTIRE existing token
        # (outcome word + every trailing k=v field: ts=/tier=/paths=+
        # paths_n=/round=/prev=/vf=/warm=/rekey=/item=) BYTE-FOR-BYTE,
        # substituting ONLY the reviewer= value in place -- see
        # `_rebuild_corrected_token`'s own docstring for why this is a raw
        # token-swap rather than a re-derivation through any field's own
        # writer (a re-derivation could silently normalize/truncate a value
        # differently than how it was originally written, e.g. paths_n=
        # recomputed from an already-capped paths= list). This is what
        # guarantees outcome/paths/digest/round/prev/vf/tier/warm/rekey/ts=
        # are NEVER touched by a correction -- #5133 requirement (b).
        #
        # `corrected_at=` (BLOCKER 2, 2026-09-09 fix round) is stamped HERE,
        # at the moment this correction is actually decided/written --
        # never derived from `existing_token`'s own `ts=` (that field stays
        # the ORIGINAL review's timestamp, untouched, per the byte-fidelity
        # guarantee above). Without a field recording WHEN the correction
        # happened, `audit_review_attribution.py`'s own `--window-seconds`
        # join (or any other `ts=`-keyed consumer) evaluates the corrected
        # line against the ORIGINAL dispatch's timestamp -- a day-8
        # correction would join against spend.jsonl rows from day 1.
        new_reviewer_encoded = _safe_field(new_reviewer, maxlen=_MAX_REVIEWER_FIELD_LEN)
        corrects_from_encoded = _safe_field(
            old_reviewer or "(none)", maxlen=_MAX_REVIEWER_FIELD_LEN
        )
        import datetime as _dt

        corrected_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2026-09-20 (master plan WS2.4 step 1, item 4): a corrected
        # identity re-derives model= -- the new --reviewer-tool-use-id
        # names a DIFFERENT real dispatch than the one the original entry's
        # model= was joined from (that's the whole point of the
        # correction), so carrying the OLD model= byte-for-byte forward
        # would leave a stale, now-wrong tier attached to the corrected
        # identity. The re-derivation uses the SAME bounded spend.jsonl
        # join `--pre-commit` uses (`derive_reviewing_model`) against the
        # NEW identity's (agent_id, tool_use_id) -- parsed back out of
        # `new_reviewer` (already validated both-or-neither by
        # `_parse_new_fields` above). A bare --reviewer type with no
        # identity pair (agent_id/tool_use_id both None) cannot be
        # re-derived at all -- model_replacements={} (an empty dict, not
        # None) then REMOVES the stale model=/model_source=/model_id=
        # fields entirely rather than leaving a now-unverifiable value
        # attached to an identity that no longer names a joinable dispatch.
        new_identity = parse_reviewer_value(new_reviewer)
        if new_identity["agent_id"] and new_identity["tool_use_id"]:
            _derivation = derive_reviewing_model(
                _lib.AGENT_BUDGET_DIR,
                new_identity["tool_use_id"],
                new_identity["agent_id"],
            )
            model_replacements: dict[str, str | None] = {
                "model": _derivation.model,
                "model_source": "ledger" if _derivation.model else None,
                "model_id": (
                    _safe_field(_derivation.model_id, maxlen=_MAX_REVIEWER_FIELD_LEN)
                    if _derivation.model_id
                    else None
                ),
                # REGRESSION fix (finding 2, 2026-09-20 fix round): a
                # correction never carries a caller declaration forward --
                # --model is already refused outright alongside
                # --correct-identity, and the OLD entry's model_declared=
                # (from whatever the ORIGINAL review happened to declare)
                # is not necessarily still true of the corrected identity's
                # own derived model. Always cleared, in both branches.
                "model_declared": None,
            }
            if _derivation.model is None:
                _lib.log(
                    HOOK,
                    "missing-reviewer-identity",
                    target=target,
                    repo=repo_root_for_correction,
                    key=lookup_key,
                    reviewer=new_identity["type"] or "",
                    reason=_derivation.reason,
                )
        else:
            model_replacements = {
                "model": None,
                "model_source": None,
                "model_id": None,
                "model_declared": None,  # see the sibling branch's comment above
            }
            _lib.log(
                HOOK,
                "missing-reviewer-identity",
                target=target,
                repo=repo_root_for_correction,
                key=lookup_key,
                reviewer=new_identity["type"] or "",
                reason="no-identity",
            )

        corrected_token = _rebuild_corrected_token(
            existing_token,
            new_reviewer_encoded,
            corrects_from_encoded,
            corrected_at,
            model_replacements=model_replacements,
        )
        # Written at `lookup_key` (the REAL on-disk key spelling), never
        # `correct_key` (the caller's --prev-style spelling) -- for a
        # precommit: key the two are identical (see `_ledger_lookup_key`'s
        # own docs), but for a legacy sha: key writing the prefixed spelling
        # would create a SECOND, never-matched key that no consumer ever
        # looks up (precommit_review_gate/decide() always resolve a plain
        # HEAD sha unprefixed), silently failing to correct anything.
        corrected_line = f"{repo_root_for_correction} {lookup_key} {corrected_token}"

        on = _lib.enforcing(repo_root_for_correction)
        if on:
            wrote = _append_entry(corrected_line)
            if wrote:
                print(
                    f"record_review: corrected reviewer identity for {correct_key!r} "
                    f"in {repo_root_for_correction} -- was {old_reviewer or '(none)'!r}, "
                    f"now {new_reviewer!r}. Original entry preserved on record; this "
                    "correction is appended, not overwritten."
                )
            else:
                print(
                    "record_review: NOT corrected — the ledger lock was unavailable "
                    "(another agent is writing). Nothing was written; re-run this "
                    "command."
                )
            _lib.log(
                HOOK,
                "corrected-identity" if wrote else "correct-identity-failed",
                repo=repo_root_for_correction,
                key=correct_key,
                old_reviewer=old_reviewer or "",
                new_reviewer=new_reviewer,
            )
        else:
            print(
                f"record_review: (LOG-ONLY) would correct reviewer identity for "
                f"{correct_key!r} in {repo_root_for_correction} -- was "
                f"{old_reviewer or '(none)'!r}, now {new_reviewer!r}."
            )
            _lib.log(
                HOOK,
                "would-correct-identity",
                repo=repo_root_for_correction,
                key=correct_key,
                old_reviewer=old_reviewer or "",
                new_reviewer=new_reviewer,
            )
            # Same contract as the HEAD/--pre-commit record path below: a write
            # the caller asked for that LOG-ONLY skipped exits non-zero.
            print(f"record_review: NOT corrected {_LOG_ONLY_HINT}", file=sys.stderr)
            return 1
        return 0

    outcome, blockers = _resolve_outcome(argv, ev)

    paths = _paths_from_argv(argv)
    repo_root_for_fields: str | None = None
    if paths:
        repo_root_for_fields = _git(target, "rev-parse", "--show-toplevel") or None

    # tier= is COMPUTED here, from classify(), never trusted from a
    # caller-declared --tier — see decide()'s and _entry_suffix's own docs.
    # A disagreeing --tier is an audit signal (tier_declared=) -- but the
    # LOG line for it is deliberately NOT emitted here (FINDING 5, 2026-08-30
    # review): several early-abort branches below (precommit-no-paths /
    # -unresolvable / -empty-diff) `return 0` before `decide()` is ever
    # called, and `decide()` itself can resolve to STATUS_ALREADY (nothing
    # NEW recorded). Logging the mismatch at THIS point would count a
    # declaration that never produced a real ledger entry. `_tier_mismatch`
    # carries (declared, computed) forward; the actual `_lib.log` call sits
    # just after `decide()` returns, gated on the decision actually being
    # one that records something (STATUS_RECORD/STATUS_UPDATE).
    tier: str | None = None
    tier_declared: str | None = None
    _tier_mismatch: tuple[str, str] | None = None
    declared_raw = new_fields.get("tier_declared_raw")
    if paths and repo_root_for_fields:
        # BLOCKER 3 (2026-08-30 review): this module's own documented
        # contract is "never raises out to its caller" -- a crashing hook
        # must not break the agent, and every failure degrades to a clean
        # exit 0. The lazy `precommit_review_gate` import + `classify()`
        # call below were NOT actually covered by that contract before this
        # try/except: a raising classifier (or a broken import) propagated
        # straight out of `main()` as a real, uncaught exception -- proven
        # live by the reviewer, and most dangerous for the unattended
        # nightly finishing loop, where an uncaught traceback here becomes a
        # job FAILURE instead of the designed graceful no-op. ANY exception
        # here degrades to `tier = None` (TIER_UNKNOWN downstream, per
        # `field_tier`'s own doc), never half-computed state, and the rest
        # of this call still proceeds to record normally -- tier telemetry
        # is a nice-to-have, never load-bearing for whether the review
        # itself gets recorded.
        try:
            # Imported HERE, not at module scope: precommit_review_gate imports
            # THIS module for its outcome-aware ledger read, so a top-level
            # import either way round would be a cycle.
            import precommit_review_gate as prg

            normalized_for_tier = prg.normalize_paths(repo_root_for_fields, target, paths)
            # Thread the calling repo's `security.extra_risk_keywords` through
            # explicitly (never rely on `classify()`'s own default `()`) --
            # `tier=` is documented as ALWAYS matching what the orchestrator's
            # own `review_risk_tier.py` CLI printed, and that CLI resolves
            # extra keywords from cwd via `_repo_extra_keywords()`. Omitting
            # this here silently disagreed with the CLI on any repo carrying
            # extra keywords (verified: CSA's `catalog` -- moderate here,
            # high from the CLI -- a false `tier-mismatch` on exactly the
            # paths this feature exists to keep HIGH), which is the fix.
            extra_kw = rrt._repo_extra_keywords(repo_root_for_fields)
            tier, _tier_reason = rrt.classify(normalized_for_tier, extra_kw)
            if declared_raw and declared_raw != tier:
                tier_declared = declared_raw
                _tier_mismatch = (declared_raw, tier)
        except Exception:
            tier = None
            tier_declared = None
            _tier_mismatch = None
    elif declared_raw:
        # FINDING 4 (2026-08-30 review): --tier with no usable --paths (no
        # --paths at all, or a --paths whose repo root failed to resolve)
        # used to be silently accepted and discarded -- no tier=, no
        # tier_declared=, no log line at all. Loud, not silent, matching
        # this module's own Part A standard for the rest of its argv
        # handling: a visible log entry, even though this never blocks or
        # errors this call (a bare --tier with no --paths is a caller
        # mistake worth recording, not something worth refusing over).
        _lib.log(HOOK, "tier-declared-no-paths", target=target, declared=declared_raw)

    rekey_value = _value_from_argv(argv, "--rekey")
    # Finding 1 root-cause fix (2026-09-01 fix round 3): the value actually
    # WRITTEN into the new entry's rekey= field. Starts equal to rekey_value
    # (the CLI-cited prior key) and is reassigned to the chain's ROOT key
    # below when the cited prior entry is itself a rekey entry — see the
    # root-resolution block. Threaded into decide()'s own rekey= kwarg at
    # the bottom of this function unconditionally (None for every non-rekey
    # call, exactly like rekey_value was before this variable existed).
    rekey_to_record = rekey_value
    # GH #5886 fix-round-4, R7-B1: the `dg=` value to write on THIS call's
    # own new entry, if any. Set to `_DIGEST_FORMAT_VERSION` for a
    # `--pre-commit` recording below (its digest is always computed via the
    # current, R6-B1-fixed rendering — see `prg.pending_key`) and, for
    # `--rekey`, only after the chain-root `dg=2` check below passes (a
    # rekey's OWN new entry is safe to stamp `dg=2` because its digest was
    # produced by `prg.rekey_digest_if_only_untracked_became_staged`, which
    # uses that same current rendering for its reconstruction — but ONLY
    # once we've confirmed the chain it's built on is itself trustworthy).
    # Stays None (no field written) for every other call shape, exactly like
    # `rekey_to_record` above.
    dg_to_record: str | None = None
    if "--pre-commit" in argv and rekey_value is not None:
        print("record_review: --pre-commit and --rekey are mutually exclusive. Nothing recorded.")
        _lib.log(HOOK, "rekey-and-precommit-conflict", target=target)
        return 0
    if rekey_value is not None and (
        "--clean" in argv or any(a == "--blockers" or a.startswith("--blockers=") for a in argv)
    ):
        # Item 18 (2026-09-01 fix round): --rekey ALWAYS carries forward the
        # PRIOR review's clean outcome by construction (see BLOCKER 1/Item 8
        # above) -- a caller-declared --clean/--blockers alongside it is
        # never meaningful and is refused loudly, mirroring the --pre-commit
        # conflict check immediately above rather than silently ignored.
        print(
            "record_review: --rekey and --clean/--blockers are mutually exclusive "
            "-- --rekey always carries forward the PRIOR review's clean outcome by "
            "construction, never a caller-declared one. Nothing recorded."
        )
        _lib.log(HOOK, "rekey-and-outcome-flag-conflict", target=target)
        return 0

    head_override: str | None = None
    if "--pre-commit" in argv or rekey_value is not None:
        # GH #5886 fix-round-4 (R6-B2, replacing a fix-round-3 attempt that
        # STRIPPED these vars from this module's OWN git calls instead —
        # see precommit_review_gate.REASON_PATHSPEC_ENV_SET's own comment for
        # why stripping was a regression against HEAD, live-reproduced with
        # an ambient GIT_LITERAL_PATHSPECS=1 making HEAD deny a commit that
        # the stripped version wrongly allowed). Checked before EITHER mode
        # computes a digest: this module and the eventual `git commit` both
        # inherit the SAME ambient environment, so if one of these vars is
        # set, this module cannot trust its own git calls to mean the same
        # thing the real commit will do, and refuses outright rather than
        # silently compute a digest under a DIFFERENT (default) semantics.
        import precommit_review_gate as prg

        env_hits = prg.pathspec_env_vars_present()
        if env_hits:
            mode = "--rekey" if rekey_value is not None else "--pre-commit"
            print(
                f"record_review: {mode} REFUSED — {', '.join(env_hits)} is set in "
                "the environment. Each of GIT_LITERAL_PATHSPECS/GIT_GLOB_PATHSPECS/"
                "GIT_NOGLOB_PATHSPECS/GIT_ICASE_PATHSPECS changes how git itself "
                "interprets a pathspec, so this command cannot compute a digest it "
                "can trust to mean the same thing the real commit will do. Unset "
                "the variable and re-issue. Nothing recorded."
            )
            _lib.log(HOOK, "pathspec-env-set", target=target, env_vars=env_hits)
            return 0

    if "--pre-commit" in argv:
        if not paths:
            print(
                "record_review: --pre-commit needs --paths <the exact paths you are "
                "about to commit> (the review is keyed to that content). Nothing recorded."
            )
            _lib.log(HOOK, "precommit-no-paths", target=target)
            return 0
        repo_root_for_key = repo_root_for_fields or target
        # `target` is the cwd the paths were typed relative to; the gate uses
        # the commit's own cwd. Both sides normalize to repo-root-relative
        # inside pending_key, so the two digests agree from any directory.
        head_override = prg.pending_key(repo_root_for_key, target, paths)
        if head_override == prg.UNRESOLVABLE:
            print(
                "record_review: those paths could not be resolved to real content "
                "(shell-expanded token, or they match nothing). Use literal paths. "
                "Nothing recorded."
            )
            _lib.log(HOOK, "precommit-unresolvable", target=target, paths=paths[:20])
            return 0
        if head_override is None:
            print(
                "record_review: those paths have no pending change vs HEAD, so there "
                "is nothing to review. Nothing recorded."
            )
            _lib.log(HOOK, "precommit-empty-diff", target=target, paths=paths[:20])
            return 0
        # R7-B1: a --pre-commit digest is ALWAYS computed by prg.pending_key
        # under THIS module's current (R6-B1-fixed) rendering -- safe to
        # stamp as the current digest format outright, unconditionally.
        dg_to_record = _DIGEST_FORMAT_VERSION

        # GH #5886 checklist item 3: warn (never refuse -- this is advisory
        # only) when a --paths entry is a DIRECTORY that currently contains
        # untracked files. Staging those files later moves the digest exactly
        # like any other untracked-to-staged transition (AA-0064), and the
        # caller will need `record_review.py --rekey` to carry this review
        # forward without a second full review -- flagging it NOW, while the
        # reviewer's context is still fresh, is cheaper than discovering it
        # at the gate 3b denial. Uses `os.path.isdir` directly (mirrors
        # `prg._any_path_is_a_directory`) rather than importing that private
        # helper, since the check here is directory-plus-untracked-content,
        # a strictly narrower condition that function doesn't compute.
        #
        # NIT 5 (2026-09-23 round-2 review): `_p` is checked for `isdir`
        # relative to `target` (the cwd the caller's `--paths` are typed
        # relative to), but `ls-files` must ALSO run from `target` with that
        # same relative `_p` -- running it from `repo_root_for_key` instead
        # silently missed every case where the two differ (any commit issued
        # from a subdirectory of the repo, exactly the same coordinate-frame
        # hazard `normalize_paths`/`pending_key` already guard against
        # elsewhere in this pipeline). Both the isdir check and the ls-files
        # call now consistently use `target` as their working directory.
        for _p in paths:
            _candidate = _p if os.path.isabs(_p) else os.path.join(target, _p)
            if not os.path.isdir(_candidate):
                continue
            _untracked = _git(
                target,
                "-c",
                "core.quotePath=false",
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                _p,
            )
            if _untracked:
                print(
                    f"record_review: NOTE -- {_p!r} is a directory containing untracked "
                    "file(s). If any of them are later `git add`-ed, this review's digest "
                    "will change (staging an untracked file always moves it -- AA-0064). "
                    "You will not need a second full review for that alone: "
                    "`record_review.py --rekey <this-key> --paths ...` carries this clean "
                    "outcome forward when the content is otherwise byte-identical and "
                    "lossless. This is a note, not a refusal -- nothing is blocked."
                )
                _lib.log(
                    HOOK, "precommit-directory-has-untracked", target=target, path=_p
                )

        # WS2.3 (master plan §2.3, "Review-round ceiling + clock") --
        # REVIEW-ROUND CEILING, LOG-ONLY. The round is DERIVED from this
        # repo's own ledger history (`derive_review_round`), never trusted
        # from a caller's self-declared --round -- see that function's own
        # docstring and the _ROUND_TRIPWIRE/_MAX_TOTAL_ROUNDS constants'
        # module-level comment for the full contract. This block ALWAYS
        # runs for a --pre-commit call (never gated on `_lib.enforcing()`,
        # a wholly separate axis governing only whether the ledger WRITE
        # itself happens) -- deriving and logging is pure observation, and
        # per the master plan's own 7-day-window mandate, LOG-ONLY here
        # means what it says: nothing below this point ever causes a
        # `return 0` / refusal. `--round` stays OPTIONAL; when the caller
        # supplied one and it disagrees with the derived value, that
        # disagreement is logged (`round-mismatch`) exactly like
        # `tier_declared`/`model_declared`'s own "audit signal, never
        # trusted over the derived value" precedent -- the DERIVED value is
        # what gets passed to decide()'s round_= below, regardless.
        repo_root_for_round = repo_root_for_key
        _round_derivation = derive_review_round(_lib.LAST_REVIEWED, repo_root_for_round, paths)
        derived_round = _round_derivation.derived_round
        declared_round = new_fields.get("round")
        if declared_round is not None and declared_round != derived_round:
            _lib.log(
                HOOK,
                "round-mismatch",
                target=target,
                repo=repo_root_for_round,
                declared=declared_round,
                derived=derived_round,
                paths=paths[:20],
            )
        # The DERIVED value always governs what actually gets recorded --
        # overwrite whatever --round the caller declared (if any) with the
        # value derive_review_round() actually computed. A caller that
        # passed no --round at all sees this same field populated with the
        # derived value too (master plan §2.3: "when absent the recorder
        # writes the derived value").
        new_fields["round"] = derived_round

        if derived_round >= _ROUND_TRIPWIRE:
            # A would-eventually-require-escalation boundary. Never
            # refused in this LOG-ONLY landing -- logged so the 7-day
            # observation window (master plan §2.3) has real data to
            # hand-check before any enforcing version ships.
            _would_refuse_reason = (
                "total-round-cap-would-refuse"
                if derived_round > _MAX_TOTAL_ROUNDS
                else "round-tripwire-would-refuse"
            )
            _lib.log(
                HOOK,
                _would_refuse_reason,
                target=target,
                repo=repo_root_for_round,
                derived_round=derived_round,
                blockers_found=_round_derivation.blockers_found,
                paths=paths[:20],
            )
    elif rekey_value is not None:
        # --rekey (AA-0064, 2026-09-01 waste-elimination P3): carries a
        # PRIOR clean review's outcome forward to the CURRENT pending
        # digest, but ONLY when precommit_review_gate's reconstruction
        # PROVES the current content is byte-identical to what produced the
        # prior digest, modulo an untracked file having since been staged.
        # This is its own write path (like --battery), forcing outcome=CLEAN
        # regardless of any --clean/--blockers the caller also passed —
        # --rekey never carries a blockers outcome forward (see decide()'s
        # own docs: only a CLEAN prior entry is ever eligible).
        if not _REKEY_RE.match(rekey_value):
            print(
                f"record_review: --rekey {rekey_value!r} does not match "
                "'precommit:<16-hex-digit digest>' -- only a pre-commit "
                "content-keyed entry can be carried forward. Nothing recorded."
            )
            _lib.log(HOOK, "rekey-invalid-key", target=target, rekey=rekey_value)
            return 0
        if not paths:
            print(
                "record_review: --rekey needs --paths <the exact paths you are "
                "about to commit> (the reconstruction is keyed to that content). "
                "Nothing recorded."
            )
            _lib.log(HOOK, "rekey-no-paths", target=target)
            return 0

        import precommit_review_gate as prg

        repo_root_for_rekey = repo_root_for_fields or _git(target, "rev-parse", "--show-toplevel")
        if not repo_root_for_rekey:
            print(f"record_review: {target} is not a git repo — nothing to rekey (no-op)")
            _lib.log(HOOK, "rekey-not-a-repo", target=target)
            return 0

        existing = _existing_outcome_token(_lib.LAST_REVIEWED, repo_root_for_rekey, rekey_value)
        if existing is None:
            print(
                f"record_review: --rekey {rekey_value!r} has no review on record at "
                "all for this repo — a real review is needed. Nothing recorded."
            )
            _lib.log(HOOK, "rekey-no-prior-entry", target=target, rekey=rekey_value)
            return 0
        prior_status, _prior_n = parse_outcome_token(existing)
        if prior_status != OUTCOME_CLEAN:
            print(
                f"record_review: --rekey {rekey_value!r}'s prior review was not "
                f"recorded clean ({_outcome_phrase(existing)}) -- --rekey only "
                "carries forward a CLEAN outcome. Get a fresh review instead. "
                "Nothing recorded."
            )
            _lib.log(HOOK, "rekey-prior-not-clean", target=target, rekey=rekey_value)
            return 0

        # Finding 1 root-cause fix (2026-09-01 fix round 3): chains form
        # because the unreviewed-commit hint (precommit_review_gate.decide)
        # and find_clean_precommit_entry_for_paths both point a SECOND
        # --rekey at the MOST RECENT clean entry for the same paths — which,
        # after one rekey, is itself a rekey entry. Resolve to the chain's
        # ROOT here, at the WRITER, so every entry's own rekey= always names
        # a TRUE root (an entry that never itself carries rekey=) — turning
        # a chain into a star (every non-root entry points directly at the
        # same root) rather than letting it grow multiple hops deep. Only
        # ONE hop is ever followed, never a general transitive walk: a root
        # never carries rekey= BY CONSTRUCTION of this very resolution, so a
        # second hop existing at all means the chain is broken (ledger
        # corruption, or a legacy entry written before this fix existed) —
        # refused with a clear message rather than silently walked further.
        prior_fields = parse_ledger_fields(existing)
        if prior_fields.get("rekey"):
            root_key = prior_fields["rekey"]
            root_existing = _existing_outcome_token(_lib.LAST_REVIEWED, repo_root_for_rekey, root_key)
            if root_existing is None:
                print(
                    f"record_review: --rekey chain broken — {rekey_value!r}'s own "
                    f"rekey= names {root_key!r}, which has no review on record at all. "
                    "Nothing recorded."
                )
                _lib.log(
                    HOOK, "rekey-chain-broken", target=target, rekey=rekey_value, root=root_key
                )
                return 0
            root_status, _root_n = parse_outcome_token(root_existing)
            if root_status != OUTCOME_CLEAN:
                print(
                    f"record_review: --rekey chain broken — {rekey_value!r}'s own "
                    f"rekey= names {root_key!r}, which is not recorded clean "
                    f"({_outcome_phrase(root_existing)}). Nothing recorded."
                )
                _lib.log(
                    HOOK, "rekey-chain-broken", target=target, rekey=rekey_value, root=root_key
                )
                return 0
            root_fields = parse_ledger_fields(root_existing)
            if root_fields.get("rekey"):
                print(
                    f"record_review: --rekey chain broken — {rekey_value!r}'s own "
                    f"rekey= names {root_key!r}, which is ITSELF a rekey entry (a chain "
                    "deeper than one hop). Only one hop is ever resolved — get a fresh "
                    "review instead. Nothing recorded."
                )
                _lib.log(
                    HOOK, "rekey-chain-broken", target=target, rekey=rekey_value, root=root_key
                )
                return 0
            prior_fields = root_fields  # the ROOT's own reviewer=/model= carry forward
            rekey_to_record = root_key

        # GH #5886 fix-round-4, R7-B1 (cold trust-architect review): the
        # chain ROOT (`prior_fields` above is always the root's own fields
        # by this point, whether `existing` was itself the root or one hop
        # was resolved) must carry `dg=2` -- proof its digest was computed
        # under `precommit_review_gate._digest_safe_name`'s control-
        # character-safe rendering (R6-B1). Without this, a review recorded
        # BEFORE R6-B1 existed (or under any pre-fix code path) can be
        # rekeyed onto fabricated content that reconstructs byte-identically
        # to the OLD (vulnerable) digest but not to what a fresh review of
        # the actual pending content would see -- exactly R7-B1's e25.py
        # repro (a single oddly-named reviewed directory entry, rekeyed onto
        # two ordinary staged files, one smuggling a payload). A root with
        # no `dg=` field at all (every entry recorded before this fix
        # existed, by definition) refuses here -- there is no way to
        # retroactively know its digest is safe, so it is treated as unsafe,
        # matching this module's fail-closed posture everywhere else lossy/
        # ambiguous material is involved (see `rekey-lossy-material` below).
        # The refusal path is a fresh full review, exactly like every other
        # rekey refusal in this function -- never a silent downgrade or a
        # second, weaker verification path.
        if prior_fields.get("dg") != _DIGEST_FORMAT_VERSION:
            print(
                f"record_review: --rekey REFUSED — {rekey_value!r}'s chain root was "
                "recorded before the current digest format (no dg=2 on record). An "
                "old-format digest cannot be trusted to distinguish a single "
                "oddly-named reviewed entry from fabricated content that happens to "
                "reconstruct identically under the OLD rendering. A fresh full "
                "review is needed:\n  " + prg.record_command(paths, repo_root_for_rekey)
            )
            _lib.log(
                HOOK,
                "rekey-root-digest-format-stale",
                target=target,
                rekey=rekey_value,
                root_dg=prior_fields.get("dg"),
            )
            return 0
        # The root's dg=2 just proved safe above -- this rekey's OWN new
        # entry is likewise a current-format digest (its content was
        # reconstructed via prg.rekey_digest_if_only_untracked_became_staged
        # using the SAME current rendering `--pre-commit` uses), so it is
        # itself a safe future chain root. Threaded to decide() below.
        dg_to_record = _DIGEST_FORMAT_VERSION

        # GH #5886 fix-round-3/4 BLOCKER B2 (cold review): defense in depth
        # against an outright path-set MISUSE, checked before the
        # reconstruction is even attempted. When the prior entry recorded
        # its OWN `paths=`/`paths_n=` telemetry, refuse a --rekey whose
        # CURRENT --paths set (sanitized + deduped the SAME way the ledger
        # write itself does, order-independent) disagrees with it. The
        # byte-identical SHA256 reconstruction below is what actually proves
        # safety, and it already refuses on any real content difference —
        # this check adds nothing to that proof — but it catches an
        # outright MISUSE (citing one review's key while typing a different
        # --paths set) with a clear, specific message instead of relying
        # solely on the reconstruction to fail for an unrelated-looking
        # reason.
        #
        # The ledger's own `paths=` field keeps at most `_MAX_PATHS_IN_FIELD`
        # (12) entries — `_paths_field` truncates it there and records the
        # TRUE distinct count separately as `paths_n=`. Comparing the
        # (truncated-to-12) stored set against the FULL current set for
        # EXACT equality would refuse every honest rekey of 13+ distinct
        # paths outright, since a truncated historical record can never
        # equal a complete current one. So: when the prior entry's own
        # `paths_n` exceeds the 12-entry cap (proof the stored `paths=` is
        # itself an incomplete record), this check instead requires (a) the
        # stored (truncated) set to be a SUBSET of the current (sanitized,
        # deduped) set — re-verifying every path the ledger managed to
        # store — and (b) the current set's size to exactly equal the
        # recorded `paths_n`. Both halves are necessary: a subset check
        # alone would silently accept a current --paths set that adds one
        # extra, never-reviewed path on top of the honest truncated 12.
        # When `paths_n` is absent, unparsable, or does not exceed the cap,
        # exact-set equality against the (complete) stored set applies,
        # unchanged from before this fix existed. An entry with no `paths=`
        # field at all (an older, pre-telemetry ledger line) is NOT checked
        # — there is nothing on record to compare against.
        prior_paths_raw = prior_fields.get("paths")
        if prior_paths_raw:
            prior_path_set = frozenset(prior_paths_raw.split("#"))
            # Sanitize THEN dedupe, mirroring _paths_field's own writer-side
            # dedupe — two raw --paths entries that sanitize to the same
            # string (or an outright literal duplicate) must count once,
            # matching what the ORIGINAL review's own paths_n= counted.
            current_path_set = frozenset(_safe_path_component(p) for p in paths if p)
            try:
                prior_paths_n = int(prior_fields.get("paths_n", ""))
            except (TypeError, ValueError):
                prior_paths_n = None
            truncated = prior_paths_n is not None and prior_paths_n > _MAX_PATHS_IN_FIELD
            if truncated:
                mismatch = not prior_path_set.issubset(current_path_set) or (
                    len(current_path_set) != prior_paths_n
                )
            else:
                mismatch = prior_path_set != current_path_set
            if mismatch:
                if truncated:
                    print(
                        f"record_review: --rekey REFUSED — {rekey_value!r}'s own recorded "
                        f"paths (a truncated record of {prior_paths_n} total distinct paths; "
                        f"{sorted(prior_path_set)} stored) are not all present in, or the "
                        "distinct count does not match, the --paths given here "
                        f"({sorted(current_path_set)}, n={len(current_path_set)}). --rekey "
                        "only carries forward a review onto the SAME paths it originally "
                        "covered. Nothing recorded."
                    )
                else:
                    print(
                        f"record_review: --rekey REFUSED — {rekey_value!r}'s own recorded "
                        f"paths ({sorted(prior_path_set)}) do not match the --paths given "
                        f"here ({sorted(current_path_set)}). --rekey only carries forward a "
                        "review onto the SAME paths it originally covered. Nothing recorded."
                    )
                _lib.log(
                    HOOK,
                    "rekey-paths-mismatch",
                    target=target,
                    rekey=rekey_value,
                    prior_paths=sorted(prior_path_set)[:20],
                    current_paths=sorted(current_path_set)[:20],
                    prior_paths_n=prior_paths_n,
                    truncated=truncated,
                )
                return 0

        prior_digest_hex = rekey_value[len(prg.PRECOMMIT_PREFIX):]
        lossy_reasons: list[str] = []
        new_key = prg.rekey_digest_if_only_untracked_became_staged(
            repo_root_for_rekey, target, paths, prior_digest_hex, lossy_sink=lossy_reasons
        )
        if new_key is None:
            # GH #5886 fix-round-4 (non-blocking, cold review; message text
            # corrected fix-round-4 R7-B2): a refusal caused by LOSSY/
            # AMBIGUOUS reconstruction material is a materially different
            # situation from an ordinary content mismatch — the caller
            # cannot fix it by reviewing "the same content" again, because
            # THIS material can never be safely verified byte-for-byte
            # through this mechanism AT ALL. Distinct reason + an honest
            # message instead of silently folding it into the generic "does
            # not reproduce" wording. Corrected to (a) name every lossy
            # class this mechanism actually reports (`_format_untracked_
            # entries`'s own `lossy_sink.append` call sites: an UNREADABLE
            # file and the FILE-COUNT/aggregate-size cap were both missing
            # from the prior wording, which named only "large, binary, or
            # non-UTF-8"), and (b) never claim the lossy material "can never
            # be safely carried forward" as if it were necessarily part of
            # the commit itself — the lossy file is untracked material
            # `--paths` swept in (e.g. a directory pathspec's untracked
            # contents), not necessarily a file that will actually be
            # staged/committed; what can never be safely carried forward is
            # the REKEY, not the file's own eventual fate.
            if lossy_reasons:
                print(
                    "record_review: --rekey REFUSED — the reconstruction for these "
                    "paths could not be trusted (a file past the per-file or aggregate "
                    "read cap, a file past the readable-file-count cap (roughly 1000 "
                    "readable files), a non-UTF-8 file of any size, or an unreadable "
                    "file — any of these makes the untracked material this mechanism "
                    "relies on lossy or ambiguous, whether or "
                    "not that specific file is what ends up staged). This is not an "
                    "ordinary content mismatch — this --rekey can never be safely "
                    "verified through this mechanism. A fresh full review is needed:\n  "
                    + prg.record_command(paths, repo_root_for_rekey)
                )
                _lib.log(
                    HOOK,
                    "rekey-lossy-material",
                    target=target,
                    rekey=rekey_value,
                    paths=paths[:20],
                    lossy=lossy_reasons[:20],
                )
                return 0
            print(
                "record_review: --rekey REFUSED — the current pending content for "
                "these paths does not reproduce the prior review's content "
                "byte-for-byte (beyond an untracked file having since been staged; "
                "any newly-staged file must also still be a plain regular file — "
                "an executable bit, a symlink, or a submodule gitlink refuses too). "
                "A real review is needed:\n  "
                + prg.record_command(paths, repo_root_for_rekey)
            )
            _lib.log(
                HOOK, "rekey-content-changed", target=target, rekey=rekey_value, paths=paths[:20]
            )
            return 0

        # BLOCKER 1 (2026-09-01 fix round, cold HIGH review): a rekey is only
        # meaningful for a TARGET digest with NO existing record. Without
        # this check, a target digest that already carries a real review
        # outcome (most dangerously: unresolved BLOCKERS) would be silently
        # overwritten by decide()'s own STATUS_UPDATE path the moment this
        # call proceeds to CLEAN — reproduced live: a blockers:3 entry
        # rewritten to clean, gate 3b flipping from deny to allow over 3
        # known blockers. Checked BEFORE any write, refused loudly, nothing
        # recorded — the safest form: --rekey never writes over ANY existing
        # entry at its target key, clean or not.
        # Nit 6 (2026-09-01 fix round 4): this read and the eventual write
        # inside decide()/_append_entry are NOT one atomic operation — a
        # narrow TOCTOU window exists between this check and the lock
        # `_append_entry` takes, in which a concurrent recording onto the
        # SAME target key could land first; accepted as-is (unrestructured)
        # for this fix round, matching this ledger's existing best-effort
        # concurrency posture elsewhere.
        existing_at_target = _existing_outcome_token(_lib.LAST_REVIEWED, repo_root_for_rekey, new_key)
        if existing_at_target is not None:
            target_status, _target_n = parse_outcome_token(existing_at_target)
            if target_status == OUTCOME_CLEAN:
                # NIT 2 (2026-09-01 fix round 2): re-running an already-
                # successful --rekey (a retried/duplicate call, or the
                # target digest simply already independently clean) is a
                # true no-op, not a refusal — the target already carries
                # the EXACT outcome this call would have written. An
                # idempotent-success message, mirroring decide()'s own
                # STATUS_ALREADY phrasing for the identical shape, rather
                # than the alarming "REFUSED" wording that belongs only to
                # the genuine blockers/unknown-outcome cases below.
                print(
                    f"record_review: --rekey: {new_key} is already recorded clean "
                    "— nothing to do (idempotent)."
                )
                _lib.log(
                    HOOK, "rekey-target-already-clean",
                    target=target, rekey=rekey_value, new_key=new_key,
                )
                return 0
            reason = (
                "rekey-target-has-blockers"
                if target_status == OUTCOME_BLOCKERS
                else "rekey-target-already-recorded"
            )
            print(
                f"record_review: --rekey REFUSED — the target digest {new_key!r} "
                f"already has a review on record ({_outcome_phrase(existing_at_target)}). "
                "A rekey only ever carries forward onto a digest with NO existing "
                "record; overwriting an existing entry here — especially unresolved "
                "blockers — would be silently destructive. Nothing recorded."
            )
            _lib.log(
                HOOK, reason, target=target, rekey=rekey_value, new_key=new_key,
                existing=existing_at_target[:120],
            )
            return 0

        # Item 8 (2026-09-01 fix round): carry the ROOT entry's (see the
        # root-resolution block above — `prior_fields` already reflects the
        # ROOT when this call resolved a chain, or the cited prior itself
        # when it was already a root) reviewer identity forward too, plus
        # the rekey= provenance field itself (always the ROOT's key, never
        # an intermediate — `rekey_to_record`), so audit_review_attribution.py
        # can tell a sanctioned mechanical carry-forward apart from an
        # unattributed/self-cleared clean (which is otherwise exactly what a
        # bare rekey entry would look like).
        head_override = new_key
        outcome = OUTCOME_CLEAN
        blockers = None
        if prior_fields.get("reviewer") is not None:
            new_fields.setdefault("reviewer", prior_fields["reviewer"])
        if prior_fields.get("model") is not None:
            # Carry the ROOT entry's already-DERIVED model= forward
            # byte-for-byte, same as reviewer= above (2026-09-20, WS2.4 step
            # 1) -- a --rekey never re-derives (it has no --reviewer-
            # tool-use-id of its own to join with; it is reconstructing a
            # PRIOR review's content, not recording a new dispatch), so
            # model_source=/model_id= travel along with model= too, or a
            # rekeyed entry would show a derived-looking model= with no
            # model_source=ledger provenance, indistinguishable from a
            # pre-2026-09-20 self-reported value.
            new_fields.setdefault("model", prior_fields["model"])
            if prior_fields.get("model_source") is not None:
                new_fields.setdefault("model_source", prior_fields["model_source"])
            if prior_fields.get("model_id") is not None:
                new_fields.setdefault("model_id", prior_fields["model_id"])

    prev_value = new_fields.get("prev")
    warm = "--warm" in argv

    if prev_value:
        # AA-0049 (2026-08-31): --prev equal to THIS recording's own
        # computed digest is a self-reference -- a chain cannot be its own
        # predecessor. Checked here, after head_override is resolved (so a
        # --pre-commit call compares against its real content digest, not a
        # guess), and BEFORE decide()/any write -- refused loudly, nothing
        # recorded, matching every other argv-validation refusal above.
        current_key = _current_digest_key(target, head_override)
        if current_key is not None and prev_value == current_key:
            print(
                f"record_review: --prev {prev_value!r} equals this recording's own "
                "digest -- a chain cannot be its own predecessor. Nothing recorded."
            )
            _lib.log(HOOK, "prev-self-reference", target=target, prev=prev_value)
            return 0

        if warm:
            # CLAUDE.md §10's warm-round paragraph: at most TWO consecutive
            # warm full rounds on one prev=-linked chain before the NEXT
            # full round must be a COLD dispatch (reviewer-independence
            # backstop). repo_root is needed to scope the ledger lookup
            # (the same repo_root `_existing_outcome_token` keys on
            # everywhere else) -- resolved fresh here since decide() hasn't
            # run yet.
            repo_root_for_chain = repo_root_for_fields or _git(
                target, "rev-parse", "--show-toplevel"
            )
            if repo_root_for_chain:
                prior_warm = _consecutive_warm_round_count(
                    _lib.LAST_REVIEWED, repo_root_for_chain, prev_value
                )
                if prior_warm >= _MAX_CONSECUTIVE_WARM_ROUNDS:
                    # NIT (round-2 review, 2026-08-31): the prior wording
                    # ("this would be the {n}rd consecutive...") hardcoded
                    # an ordinal suffix that is only ever correct for n=3 --
                    # plain cardinal phrasing needs no ordinal-grammar logic
                    # at all and is correct for any cap value.
                    print(
                        "record_review: REFUSED -- this would be consecutive "
                        f"warm full review round {prior_warm + 1} on this "
                        "prev=-linked chain (cap: "
                        f"{_MAX_CONSECUTIVE_WARM_ROUNDS} consecutive warm rounds, "
                        "per CLAUDE.md §10's warm-round paragraph). Dispatch a "
                        "COLD full review instead (the independence backstop), "
                        "then record that round normally. Nothing recorded."
                    )
                    _lib.log(
                        HOOK,
                        "warm-cap-exceeded",
                        target=target,
                        prev=prev_value,
                        prior_warm=prior_warm,
                    )
                    return 0

    # 2026-09-20 (master plan WS2.4 step 1, tracking issue #5828): the
    # REVIEWING MODEL is derived from spend.jsonl, never trusted from a
    # caller's self-reported --model -- scoped to `--pre-commit` recordings
    # ONLY (the task's own scope: a plain non---pre-commit recording, and
    # --rekey's carry-forward above, are unaffected). `--model`'s CLI
    # validation (_VALID_MODELS, 3-way opus/sonnet/haiku) is untouched --
    # only what gets WRITTEN to the ledger's `model=` field changes: it is
    # now ALWAYS the derived tier word (or entirely absent, never a guess),
    # and a caller's --model is downgraded to an audit-only
    # `model_declared=` field, written ONLY when it disagreed with the
    # derived value.
    #
    # `--rekey`'s own carry-forward (above) already populated
    # new_fields["model"]/["model_source"]/["model_id"] directly when a
    # prior root entry had them -- this block does not run for a --rekey
    # call at all (mutually exclusive with --pre-commit, checked earlier),
    # so `derived_model`/`derived_model_id` default to whatever --rekey
    # already carried forward and are never overwritten below.
    # LOGGING IS DEFERRED, exactly like `_tier_mismatch` above (FINDING 5's
    # own precedent): a `--pre-commit` call can still abort AFTER this block
    # (none do today between here and `decide()`, but a --pre-commit call
    # already aborted via precommit-no-paths/-unresolvable/-empty-diff
    # LONG before reaching this point), and `decide()` itself can resolve
    # to STATUS_ALREADY (nothing NEW recorded). Logging a mismatch/missing-
    # identity signal for a call that never actually records anything new
    # would count a declaration that produced no ledger entry -- so both
    # `_model_mismatch`/`_missing_identity` are captured here and logged
    # only once `decision.status` is known, right alongside the existing
    # tier-mismatch log call below.
    derived_model: str | None = new_fields.get("model")
    derived_model_id: str | None = new_fields.get("model_id")
    derived_model_source: str | None = new_fields.get("model_source")
    model_declared_field: str | None = None
    _model_mismatch: tuple[str, str] | None = None
    _missing_identity: tuple[str, str, str] | None = None  # (repo, key, reason)
    if "--pre-commit" in argv:
        reviewer_identity = parse_reviewer_value(new_fields.get("reviewer"))
        repo_root_for_model = repo_root_for_fields or _git(
            target, "rev-parse", "--show-toplevel"
        )
        derivation = ModelDerivation(None, None, "ledger-unreadable")
        if repo_root_for_model:
            derivation = derive_reviewing_model(
                _lib.AGENT_BUDGET_DIR,
                reviewer_identity["tool_use_id"],
                reviewer_identity["agent_id"],
            )
        declared_model = new_fields.get("model")  # the caller's own --model, if any
        if derivation.model is not None:
            derived_model = derivation.model
            derived_model_source = "ledger"
            derived_model_id = derivation.model_id
            if declared_model is not None and declared_model != derivation.model:
                # An audit-only signal, mirroring tier_declared's own
                # contract exactly: the DERIVED value still governs and is
                # what gets written as model=; the caller's disagreeing
                # declaration is preserved separately, never silently
                # dropped and never trusted over the ledger.
                model_declared_field = declared_model
                _model_mismatch = (declared_model, derivation.model)
        else:
            # No derivable value at all: model= is left entirely absent
            # (never a guess). A caller's --model, if supplied, is written
            # ONLY as model_declared= (audit-only) -- never as model=, per
            # the task spec's own item (2).
            derived_model = None
            derived_model_source = None
            derived_model_id = None
            if declared_model is not None:
                model_declared_field = declared_model
            # Step 1 (14-day warn-only window, master plan §2.4): a
            # --pre-commit record whose identity is missing OR unjoinable
            # logs ONE missing-reviewer-identity line -- the record is
            # still written exactly as before (WARN ONLY; refusals are
            # step 2, a later commit). repo_root_for_model can itself be
            # falsy (an unresolvable target) -- logged as
            # "ledger-unreadable" via the pre-seeded `derivation` default
            # above in that case, never silently skipped.
            _missing_identity = (
                repo_root_for_model or "",
                head_override or "",
                derivation.reason,
            )

    decision = decide(
        target,
        outcome=outcome,
        blockers=blockers,
        head_override=head_override,
        item=item,
        tier=tier,
        tier_declared=tier_declared,
        reviewer=new_fields.get("reviewer"),
        model=derived_model,
        model_source=derived_model_source,
        model_id=derived_model_id,
        model_declared=model_declared_field,
        round_=new_fields.get("round"),
        paths=paths,
        prev=prev_value,
        vf=new_fields.get("vf"),
        warm=warm,
        rekey=rekey_to_record,
        dg=dg_to_record,
    )

    if _tier_mismatch is not None and decision.status in (STATUS_RECORD, STATUS_UPDATE):
        # FINDING 5: only NOW, once we know this call actually proceeds to
        # record something, do we log the mismatch -- never for a call that
        # aborted early above (precommit-no-paths/-unresolvable/-empty-diff,
        # all of which `return 0` before ever reaching this point) and never
        # for STATUS_ALREADY (decide() reached, but nothing NEW recorded).
        _declared, _computed = _tier_mismatch
        _lib.log(
            HOOK,
            "tier-mismatch",
            declared=_declared,
            computed=_computed,
            paths=paths[:20],
        )

    # WS2.4 step 1: the SAME "only once this call actually records
    # something new" gating as `_tier_mismatch` above, for the identical
    # reason -- a STATUS_ALREADY call (e.g. an idempotent retry of an
    # already-recorded --clean) never logs a second missing-identity/
    # mismatch line for a HEAD that was already fully handled the first
    # time it was genuinely recorded.
    if _model_mismatch is not None and decision.status in (STATUS_RECORD, STATUS_UPDATE):
        _declared_model, _derived_model = _model_mismatch
        _lib.log(
            HOOK,
            "model-mismatch",
            target=target,
            # nit 7 (2026-09-20 fix round): repo/key, matching the sibling
            # missing-reviewer-identity row below -- decision.repo_root/
            # .head are the authoritative post-decide() values (the SAME
            # key this recording call actually lands under).
            repo=decision.repo_root,
            key=decision.head,
            declared=_declared_model,
            derived=_derived_model,
        )
    if _missing_identity is not None and decision.status in (STATUS_RECORD, STATUS_UPDATE):
        _missing_repo, _missing_key, _missing_reason = _missing_identity
        _lib.log(
            HOOK,
            "missing-reviewer-identity",
            target=target,
            repo=_missing_repo,
            key=_missing_key,
            reviewer=parse_reviewer_value(new_fields.get("reviewer"))["type"] or "",
            reason=_missing_reason,
        )

    # Print the confirmation / no-op line for the human running the tool. This is
    # the bash's stdout; it is NOT a hook-protocol JSON object.
    #
    # For the two WRITING statuses the print is deferred until after the write
    # actually lands: `_append_entry`/`_update_entry` fail CLOSED when the
    # admission lock is unavailable (realistic under parallel agents), and
    # announcing "recorded" before that could return False told the caller the
    # review was on record when it was not — indistinguishable, from the
    # agent's side, from the gate malfunctioning.
    if decision.message and decision.status not in (STATUS_RECORD, STATUS_UPDATE):
        print(decision.message)

    on = _lib.enforcing(decision.repo_root or target)
    exit_code = 0

    if decision.status == STATUS_RECORD:
        if on:
            wrote = _append_entry(decision.entry)
            if wrote:
                print(decision.message)
            else:
                print(
                    "record_review: NOT recorded — the ledger lock was unavailable "
                    "(another agent is writing). Nothing was written; re-run this "
                    "command. The commit gate will keep denying until it succeeds."
                )
            _lib.log(
                HOOK,
                "recorded" if wrote else "record-failed",
                repo=decision.repo_root,
                head=decision.head,
                outcome=decision.outcome or OUTCOME_UNKNOWN,
            )
        else:
            # LOG-ONLY: enforcement OFF, so we do not mutate the ledger. The
            # "recorded review of HEAD ..." confirmation is deliberately NOT
            # printed -- nothing was recorded, so the gate will deny this content
            # once enforcement is on (or wherever the gate runs enforcing); say so
            # on stderr and exit non-zero instead.
            _lib.log(
                HOOK,
                "would-record",
                repo=decision.repo_root,
                head=decision.head,
                outcome=decision.outcome or OUTCOME_UNKNOWN,
            )
            print(f"record_review: NOT recorded {_LOG_ONLY_HINT}", file=sys.stderr)
            exit_code = 1
    elif decision.status == STATUS_UPDATE:
        if on:
            wrote = _update_entry(decision.repo_root, decision.head, decision.entry)
            if wrote:
                print(decision.message)
            else:
                print(
                    "record_review: NOT updated — the ledger lock was unavailable "
                    "(another agent is writing). Nothing was written; re-run this "
                    "command. The commit gate will keep denying until it succeeds."
                )
            _lib.log(
                HOOK,
                "updated" if wrote else "update-failed",
                repo=decision.repo_root,
                head=decision.head,
                outcome=decision.outcome,
            )
        else:
            # LOG-ONLY: enforcement OFF, so we do not mutate the ledger. Same
            # reasoning as the "would-record" branch above: never print the
            # "updated review outcome" confirmation for a write that did not happen.
            _lib.log(
                HOOK,
                "would-update",
                repo=decision.repo_root,
                head=decision.head,
                outcome=decision.outcome,
            )
            print(f"record_review: NOT updated {_LOG_ONLY_HINT}", file=sys.stderr)
            exit_code = 1
    elif decision.status == STATUS_ALREADY:
        _lib.log(
            HOOK,
            "already",
            repo=decision.repo_root,
            head=decision.head,
            outcome=decision.outcome or OUTCOME_UNKNOWN,
        )
    else:
        # not-a-dir / not-a-repo / no-head → informational no-op.
        _lib.log(HOOK, decision.status, target=target, repo=decision.repo_root)

    return exit_code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
