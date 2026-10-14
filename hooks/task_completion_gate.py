#!/usr/bin/env python3
"""task_completion_gate — RETIRED 2026-08-20. Stop hook (Python port of
review-gate.sh), unregistered from settings.json on 2026-08-19 (operator
direction: review runs BEFORE the commit, not after — see
~/.claude/hooks/precommit_review_gate.py, gate 3b, which strictly dominates
the one check this module ever did) and formally retired/committed 08-20.
Kept on disk, dormant, not deleted -- revisit only with real data from
record_review.py's outcome ledger, not a hunch. This file has ALWAYS
implemented exactly the review-recorded check described below and nothing
else (no Firestore log, no diff/tests/docs inspection, no issue check --
CLAUDE.md briefly and incorrectly claimed otherwise for two days in August
2026, conflating this file with an unrelated, differently-scoped file of the
same name in a separate product repo; corrected 08-20). The rest of this
docstring describes its historical behavior while it was live, unchanged.

Ported faithfully from ~/.claude/scripts/review-gate.sh. Warns / blocks at the
end of a turn when a git project has advanced past the last-reviewed commit and
no Opus review is on record for the current HEAD.

CONTRACT (from review-gate.sh + the spawning task):
  * Read the Stop payload from stdin (cwd / session_id, via _lib.read_event()).
  * NO-OP when ANY of:
      - CSA_DISABLE_HOOKS=1                (master kill-switch; _lib.disabled())
      - cwd is not an existing directory
      - cwd is not inside a git repo
      - the repo root lacks the .claude/.csa-enforce opt-in marker
      - HEAD sha cannot be resolved
  * CSA_SKIP_REVIEW=1 one-shot: consume a per-(repo,session) sentinel and end the
    turn once; on the second turn fall through to normal evaluation.
  * Look up "<repo_root> <sha>" in ~/.claude/.review_state/last_reviewed:
      - present  -> reviewed. OUTCOME-AWARE (see record_review.py): consult the
        SAME ledger's recorded outcome for this exact HEAD via
        record_review.head_review_outcome(). When that review reported
        unresolved BLOCKER-severity findings, the decision is
        REVIEWED_WITH_BLOCKERS — a DISTINCT, more informative signal than a
        bare "ok" ("HEAD X was reviewed but the review found N unresolved
        blocker(s) — fix them, not just re-run record_review"). This is a
        stepping stone (better signal), NEVER a new hard-blocking path:
        REVIEWED_WITH_BLOCKERS is still always non-blocking (`.block` is
        False). AUTHORSHIP-SCOPED (see below): only the session that actually
        committed this HEAD ever sees REVIEWED_WITH_BLOCKERS; every other/
        unknown session sees a plain OK instead. "Outcome unknown" (no
        outcome info ever recorded) behaves exactly as before: plain OK.
      - absent   -> tracked source changed past the review boundary.
  * AUTHORSHIP SCOPING (see commit_authors.py): the unreviewed-HEAD path below
    is scoped to the session that actually produced this HEAD via `git
    commit`, looked up via `author_fn(commit_authors_path, repo_root, head)`
    (default: commit_authors.author_of, ledger default: _lib.COMMIT_AUTHORS).
      - author == this session          -> unchanged: WOULD_WARN / BLOCK.
      - author is a DIFFERENT session   -> FOREIGN — logged once (same
        re-fire sentinel as below), NEVER blocks. Mechanizes "never review a
        HEAD I didn't produce" (memory: feedback_no_review_others_work).
      - author is None (unknown)        -> UNKNOWN_AUTHOR — an operator
        terminal commit, a HEAD that predates this ledger, or a missed ledger
        write all degrade to this quiet, NEVER-blocking outcome, same
        re-fire dedup. Trade-off accepted deliberately: a missed ledger write
        silences the prompt for that HEAD rather than risk prompting the
        wrong (or no) session — degrade-open is the house style; boundary
        reviews remain the orchestrator's own obligation regardless, this
        gate is only ever a backstop.
  * Re-fire loop guard: a per-(repo,session,head) sentinel means we already
    surfaced this exact HEAD in this session -> stay quiet. Authorship is
    resolved FIRST, THEN the sentinel is touched — never the other way
    around, so a transient author_fn failure can't permanently silence a
    HEAD this session genuinely needs to see. UNKNOWN_AUTHOR uses its OWN
    sentinel (a ".unknown-author" suffix), separate from the own-session/
    FOREIGN one: an uncertain "no author on record" result must not shadow
    a LATER retry that successfully resolves this session as the real
    author (which needs to reach WOULD_WARN/BLOCK, not stay silenced).
  * When the change is new, unreviewed, AND authored by this session:
      - LOG-ONLY by default (decision "would-warn"): never blocks, degrades open,
        matching the bash script that always exits 0.
      - ONLY when enforcing() is true do we emit a real Stop block.
  * DEGRADE OPEN on ANY internal error (the pure function returns a benign no-op
    decision; main() swallows everything and exits 0).

STRUCTURE: a pure decision function `decide()` (no I/O beyond filesystem reads it
is given explicit paths for) + a thin `main()` that reads the event, decides,
emits/logs, and exits 0. Deny/blocks are via JSON on stdout, never via exit code.
"""

from __future__ import annotations

import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - shim runs before tests import
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import commit_authors as ca  # noqa: E402  (shared per-(repo,sha) authorship ledger)
import record_review as rr  # noqa: E402  (shared outcome-aware ledger read)

# ---------------------------------------------------------------------------
# Decision outcomes. `decide()` returns one of these + a (reason, detail) pair.
# main() maps them onto emit/log; only BLOCK ever reaches emit_stop_block, and
# only then when enforcing() is true.
# ---------------------------------------------------------------------------

NOOP = "noop"  # silent pass (not opted-in / not a repo / etc.)
OK = "ok"  # HEAD already reviewed (outcome unknown/clean)
REVIEWED_WITH_BLOCKERS = "reviewed-with-blockers"  # HEAD reviewed, but that
# review recorded unresolved blocker-severity findings. NEVER a block — see
# the module docstring. A distinguishable, more actionable signal than a bare
# OK; `.block` is still always False for this outcome.
SKIP_CONSUMED = "skip-consumed"  # CSA_SKIP_REVIEW one-shot burned
SILENCED = "silenced"  # already fired for this HEAD+session this turn
WOULD_WARN = "would-warn"  # new unreviewed HEAD, authored by THIS session (log-only path)
BLOCK = "block"  # new unreviewed HEAD, authored by THIS session, AND enforcing()
FOREIGN = "foreign-head"  # new unreviewed HEAD authored by a DIFFERENT session.
# Logged once (dedup via the same fired sentinel as WOULD_WARN/BLOCK) but
# NEVER blocks — mechanizes "never review a HEAD I didn't produce" (memory:
# feedback_no_review_others_work). See module docstring CONTRACT.
UNKNOWN_AUTHOR = "unknown-author-head"  # new unreviewed HEAD with NO recorded
# author (operator terminal commit, pre-ledger HEAD, or a missed ledger
# write). Same dedup, NEVER blocks. See module docstring CONTRACT.


class Decision:
    """A hook decision: an outcome tag plus a human reason and a detail string.

    Kept as a tiny value object (not a dataclass) so the module stays stdlib-only
    and trivially importable. `block` is True only for the BLOCK outcome.
    """

    __slots__ = ("outcome", "reason", "detail")

    def __init__(self, outcome: str, reason: str = "", detail: str = ""):
        self.outcome = outcome
        self.reason = reason
        self.detail = detail

    @property
    def block(self) -> bool:
        return self.outcome == BLOCK

    def __eq__(self, other) -> bool:  # pragma: no cover - convenience for tests
        return (
            isinstance(other, Decision)
            and self.outcome == other.outcome
            and self.reason == other.reason
            and self.detail == other.detail
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Decision({self.outcome!r}, {self.reason!r}, {self.detail!r})"


# ---------------------------------------------------------------------------
# Git helpers — thin wrappers over `git`, each degrading to None/"" on error so
# the decision path can no-op cleanly. Kept out of decide() so tests can inject
# fakes and never shell out except against a throwaway repo.
# ---------------------------------------------------------------------------


def _git(cwd: str, *args: str) -> str | None:
    """Run `git -C cwd <args>` and return trimmed stdout, or None on any failure.

    Hermetic-friendly: disables system config and terminal prompts so a real git
    can't reach the network or the operator's global config.
    """
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def repo_root_of(cwd: str) -> str | None:
    """The git top-level for `cwd`, or None when `cwd` is not inside a repo."""
    root = _git(cwd, "rev-parse", "--show-toplevel")
    return root or None


def head_sha_of(repo_root: str) -> str | None:
    """The HEAD commit sha for `repo_root`, or None (e.g. an empty repo)."""
    head = _git(repo_root, "rev-parse", "HEAD")
    return head or None


# ---------------------------------------------------------------------------
# State helpers — sentinels + the last_reviewed ledger. Pure filesystem, all
# best-effort (never raise); they mirror the bash script's file layout exactly.
# ---------------------------------------------------------------------------


def _repo_key(repo_root: str) -> str:
    """Stable filename-safe key for a repo root (bash: tr '/ ' '__')."""
    return repo_root.replace("/", "_").replace(" ", "_")


def fired_sentinel(state_dir: str, repo_root: str, session: str, head: str) -> str:
    """Path of the per-(repo,session,head) re-fire guard sentinel."""
    return os.path.join(state_dir, f".fired-{_repo_key(repo_root)}-{session}-{head}")


def skip_sentinel(state_dir: str, repo_root: str, session: str) -> str:
    """Path of the per-(repo,session) CSA_SKIP_REVIEW one-shot sentinel."""
    return os.path.join(state_dir, f".skip-{_repo_key(repo_root)}-{session}")


def _touch(path: str) -> None:
    """Best-effort `: > path` — create/truncate an empty sentinel; swallow errors."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8"):
            pass
    except Exception:
        return


def head_reviewed(last_reviewed_path: str, repo_root: str, head: str) -> bool:
    """True iff last_reviewed contains the exact "<repo_root> <sha>" line.

    Mirrors the bash `grep -Fq -- "$repo_root $head"`: a fixed-string match on a
    whole needle (which may appear anywhere on a line). Missing file -> False.
    """
    needle = f"{repo_root} {head}"
    try:
        with open(last_reviewed_path, encoding="utf-8") as fh:
            for line in fh:
                if needle in line:
                    return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# PURE decision function.
#
# All external state is passed in explicitly (paths, env flags, and small
# git-lookup callables) so the whole branch space is coverable without touching
# the real ~/.claude or shelling out. main() wires the real dependencies.
# ---------------------------------------------------------------------------


def decide(
    ev: dict,
    *,
    state_dir: str,
    last_reviewed_path: str,
    commit_authors_path: str,
    enforce_marker_rel: str,
    disabled: bool,
    skip_review: bool,
    enforcing: bool,
    repo_root_fn=repo_root_of,
    head_sha_fn=head_sha_of,
    outcome_fn=rr.head_review_outcome,
    author_fn=ca.author_of,
) -> Decision:
    """Decide the Stop-hook outcome for `ev`. Never raises — degrades OPEN.

    Args:
      ev: the parsed hook event dict.
      state_dir: ~/.claude/.review_state (where sentinels live).
      last_reviewed_path: ~/.claude/.review_state/last_reviewed ledger.
      commit_authors_path: ~/.claude/.review_state/commit_authors ledger (see
        commit_authors.py) — maps (repo, sha) -> the session_id that
        committed it.
      enforce_marker_rel: relative opt-in marker path (".claude/.csa-enforce").
      disabled: _lib.disabled() — the master kill-switch (CSA_DISABLE_HOOKS=1).
      skip_review: CSA_SKIP_REVIEW=1 one-shot request.
      enforcing: _lib.enforcing(cwd) — gate that turns a warn into a real block.
      repo_root_fn / head_sha_fn: injectable git lookups (default: real git).
      outcome_fn: injectable outcome-aware ledger read (default:
        record_review.head_review_outcome) — returns (status, blocker_count)
        or None for a HEAD with no ledger entry. Only consulted once we already
        know the HEAD IS reviewed (head_reviewed() is True), to decide between
        OK and REVIEWED_WITH_BLOCKERS.
      author_fn: injectable commit-authorship lookup (default:
        commit_authors.author_of) — returns the session_id that committed
        (repo_root, head), or None when unknown. Consulted for the
        unreviewed-HEAD path (own-session/FOREIGN/UNKNOWN_AUTHOR) and to scope
        REVIEWED_WITH_BLOCKERS to the author session — see module docstring
        CONTRACT.

    Returns a Decision; the caller emits/logs based on outcome + `.block`.
    """
    try:
        return _decide_inner(
            ev,
            state_dir=state_dir,
            last_reviewed_path=last_reviewed_path,
            commit_authors_path=commit_authors_path,
            enforce_marker_rel=enforce_marker_rel,
            disabled=disabled,
            skip_review=skip_review,
            enforcing=enforcing,
            repo_root_fn=repo_root_fn,
            head_sha_fn=head_sha_fn,
            outcome_fn=outcome_fn,
            author_fn=author_fn,
        )
    except Exception:
        # Degrade OPEN: any unexpected failure ends the turn silently.
        return Decision(NOOP, "internal-error")


def _decide_inner(
    ev,
    *,
    state_dir,
    last_reviewed_path,
    commit_authors_path,
    enforce_marker_rel,
    disabled,
    skip_review,
    enforcing,
    repo_root_fn,
    head_sha_fn,
    outcome_fn,
    author_fn,
) -> Decision:
    # 1. Master kill-switch wins over everything.
    if disabled:
        return Decision(NOOP, "disabled")

    # 2. Resolve cwd; it must be an existing directory.
    where = _lib.cwd(ev)
    if not where or not os.path.isdir(where):
        return Decision(NOOP, "no-cwd")

    # 3. Must be inside a git repo.
    repo_root = repo_root_fn(where)
    if not repo_root:
        return Decision(NOOP, "not-a-git-repo")

    # 4. Must be opted-in for this project.
    marker = os.path.join(repo_root, enforce_marker_rel)
    if not os.path.isfile(marker):
        return Decision(NOOP, "not-opted-in")

    # 5. Resolve HEAD.
    head = head_sha_fn(repo_root)
    if not head:
        return Decision(NOOP, "no-head")

    short = head[:12]
    detail = f"{repo_root}@{head}"
    short_detail = f"{repo_root}@{short}"
    session = _session_id(ev)

    # 6. CSA_SKIP_REVIEW=1 one-shot: burn a sentinel, end the turn once.
    if skip_review:
        skip_path = skip_sentinel(state_dir, repo_root, session)
        if not os.path.isfile(skip_path):
            _touch(skip_path)
            return Decision(SKIP_CONSUMED, "csa-skip-review-one-shot", detail)
        # Already consumed once -> fall through to normal evaluation.

    # 7. Has this HEAD already been reviewed? If so, is that review's OUTCOME
    #    (see record_review.py) an unresolved-blockers finding? That's a
    #    strictly better signal than a bare OK — but NEVER a block (this is a
    #    stepping stone, not new hard-blocking behavior; see module docstring).
    #    AUTHORSHIP-SCOPED: only the session that actually committed this HEAD
    #    ever sees REVIEWED_WITH_BLOCKERS; a different/unknown session sees a
    #    plain OK instead (see module docstring CONTRACT).
    if head_reviewed(last_reviewed_path, repo_root, head):
        try:
            outcome = outcome_fn(last_reviewed_path, repo_root, head)
        except Exception:
            outcome = None
        status, n = outcome if outcome is not None else (rr.OUTCOME_UNKNOWN, 0)
        if status == rr.OUTCOME_BLOCKERS:
            try:
                author = author_fn(commit_authors_path, repo_root, head)
            except Exception:
                author = None
            if author == session:
                reason = (
                    f"review-gate: HEAD {short} in {repo_root} was reviewed but the "
                    f"review found {n} unresolved blocker(s) — fix them, not just "
                    "re-run record_review."
                )
                return Decision(REVIEWED_WITH_BLOCKERS, reason, detail)
        return Decision(OK, "head-already-reviewed", detail)

    # 8. Authorship scoping FIRST: who actually committed this unreviewed
    #    HEAD? See module docstring CONTRACT for the full rationale. Resolved
    #    BEFORE the re-fire sentinel is touched — a transient author_fn
    #    failure (ledger momentarily unreadable) must never permanently
    #    silence a HEAD this session actually needs to see WOULD_WARN/BLOCK
    #    for, just because it happened to degrade to UNKNOWN_AUTHOR once.
    try:
        author = author_fn(commit_authors_path, repo_root, head)
    except Exception:
        author = None

    # 8b. Re-fire loop guard: only surface a given HEAD+session once per
    #     session. UNKNOWN_AUTHOR gets its OWN sentinel, separate from the
    #     own-session/FOREIGN one: a transient/genuine "no author on record"
    #     result must not shadow a LATER retry that successfully resolves
    #     this session as the real author (which needs to reach WOULD_WARN/
    #     BLOCK, not stay silenced by an earlier UNKNOWN_AUTHOR).
    if author is None:
        unknown_path = fired_sentinel(state_dir, repo_root, session, head) + ".unknown-author"
        if os.path.isfile(unknown_path):
            return Decision(SILENCED, "already-fired-this-head", detail)
        _touch(unknown_path)
        reason = (
            f"review-gate: HEAD {short} in {repo_root} has no recorded commit "
            "author (operator terminal commit, a HEAD predating this ledger, "
            "or a missed ledger write) — not surfacing it here."
        )
        return Decision(UNKNOWN_AUTHOR, reason, short_detail)

    fired_path = fired_sentinel(state_dir, repo_root, session, head)
    if os.path.isfile(fired_path):
        return Decision(SILENCED, "already-fired-this-head", detail)
    _touch(fired_path)

    if author != session:
        reason = (
            f"review-gate: HEAD {short} in {repo_root} was committed by a "
            "different session — not surfacing it here (see "
            "feedback_no_review_others_work)."
        )
        return Decision(FOREIGN, reason, short_detail)

    # 9. New, unreviewed HEAD, authored by THIS session. LOG-ONLY by default;
    #    a real block ONLY when enforcing() is true (degrade-open otherwise,
    #    exactly like the bash).
    if enforcing:
        reason = (
            f"review-gate: HEAD {short} in {repo_root} has no Opus review on "
            "record. Run the code-reviewer, or set CSA_SKIP_REVIEW=1 to end this "
            "turn once."
        )
        return Decision(BLOCK, reason, short_detail)
    return Decision(WOULD_WARN, "head-not-reviewed", short_detail)


def _session_id(ev: dict) -> str:
    """The session id from the payload, or 'nosession' (bash default).

    A thin alias for _lib.session_id — the implementation now lives there so
    commit_authors.py's recording side and this gate's reading side always
    agree on exactly the same session identity. Kept here (rather than
    inlined at call sites) so existing direct callers/tests of
    `task_completion_gate._session_id` keep working unchanged.
    """
    return _lib.session_id(ev)


# ---------------------------------------------------------------------------
# Thin main(): read event -> decide -> emit/log -> exit 0.
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point. Always returns 0 — blocks are surfaced via JSON, not exit."""
    try:
        ev = _lib.read_event()
        where = _lib.cwd(ev)
        decision = decide(
            ev,
            state_dir=_lib.REVIEW_STATE_DIR,
            last_reviewed_path=_lib.LAST_REVIEWED,
            commit_authors_path=_lib.COMMIT_AUTHORS,
            enforce_marker_rel=_lib.PROJECT_ENFORCE_MARKER,
            disabled=_lib.disabled(),
            skip_review=os.environ.get("CSA_SKIP_REVIEW", "") == "1",
            enforcing=_lib.enforcing(where),
        )

        # Silent no-ops never touch stdout or the log (match the bash return 0s).
        if decision.outcome in (NOOP, SILENCED):
            return 0

        _lib.log(
            "review_gate",
            decision.outcome,
            reason=decision.reason,
            detail=decision.detail,
        )

        if decision.block:
            _lib.emit_stop_block(decision.reason)
    except Exception:
        # Degrade OPEN: never let a hook failure break the agent.
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
