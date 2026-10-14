"""file_claims — path-scoped commit contest ledger for concurrent agents.

Enforces the mechanical half of CLAUDE.md §2/§3: "agents only commit their own
files or their own sub-agent's files" and "contested file -> yield and poll."
Before this ledger existed, that was pure prose (an agent had to *remember* to
check). This module makes it a real, cheap, file-based check: right before a
`git commit`, its target paths are checked against every OTHER agent's live
claim in ~/.claude/.file_claims/; overlap means contested.

DEADLOCK ANALYSIS — why this design cannot deadlock, only (bounded) livelock:

Classic (Coffman) deadlock needs all four of: mutual exclusion, hold-and-wait,
no preemption, circular wait. This ledger removes hold-and-wait BY CONSTRUCTION:
an agent never holds a partial claim while asking for more. try_claim_paths()
acquires an agent's ENTIRE target path set in one atomic, lock-protected step
(admission_lock, reused from agent_budget.py) — either every path is free and
it claims all of them at once, or it claims NOTHING and reports contested. There
is therefore no reachable state where agent A holds path X and waits on path Y
held by agent B while B holds Y and waits on X — the precondition for circular
wait cannot arise, for any number of agents or paths. (Contrast: if claiming
were incremental — grab X, then try to grab Y — two agents committing [X, Y]
and [Y, X] respectively could deadlock exactly that way. All-or-nothing
acquisition is the standard prevention technique for this class of problem, and
it is why gate 4 in pretooluse_bash.py claims the WHOLE commit pathspec in one
try_claim_paths() call, never path-by-path.)

What remains, structurally, is livelock (repeated failed attempts) rather than
true deadlock, handled by three independent backstops:
  * TTL self-heal — a claim from a crashed/killed agent expires
    (CSA_FILE_CLAIM_TTL_SEC) and is pruned on the next read, so a dead holder
    can never wedge anyone forever.
  * Jittered backoff between retries (poll_claim_paths) desyncs two agents that
    would otherwise wake and retry in lockstep forever.
  * A bounded max-wait (CSA_COMMIT_CLAIM_MAX_WAIT_SEC) after which the caller
    stops polling and reports "contested" rather than spinning — mirroring
    CLAUDE.md §2's existing rule: "never force through it... return control
    rather than spinning; come back when the file is free."

Everything fails OPEN, matching the rest of this hook suite: an unreadable
ledger, an unacquirable lock, or any unexpected error all resolve to "claim
succeeded, untracked" rather than wedging a commit. A missed claim only means a
rare unflagged race; a wedged commit would be a much worse failure mode.

PER-REPO COMMIT MUTEX ("only one agent committing at a time"): as well as the
path-scoped contest above, pretooluse_bash.py gate 4 also claims a synthetic
per-repo token (MUTEX_PREFIX + the repo's realpath'd toplevel — see
mutex_token()) ALONGSIDE a commit's real target paths, so every commit in the
same repo contests every OTHER concurrent commit's claim regardless of real
path overlap. This still piggybacks on the exact same all-or-nothing ledger
(ONE claim record/file per agent, written in a single atomic step) and
therefore inherits its deadlock-freedom and its poll/max-wait backstops
unchanged — no new claim-acquisition mechanism, just one more synthetic
"path" bundled into the one claimed set.

TTL self-heal, however, is DELIBERATELY per-path-type rather than uniform
(see mutex_ttl_from_env() / read_live_claims()):
  * A real claimed path stays live for the FULL CSA_FILE_CLAIM_TTL_SEC
    (default 300s) — unchanged from before the mutex existed.
  * A commit-mutex token bundled into the SAME claim record self-heals at its
    own, much shorter CSA_COMMIT_MUTEX_TTL_SEC (default 60s) instead. A real
    `git commit` completes in seconds, not minutes, so a leaked mutex claim
    (an interrupted turn, a crashed hook process) should stop wedging OTHER
    commits in that repo within about a minute — not up to 5 minutes, which
    was the original (buggy) behavior of reusing the real-path TTL for the
    mutex too: a leaked mutex claim wedged EVERY commit in that entire repo,
    not just a path-overlapping one, for the full CSA_FILE_CLAIM_TTL_SEC.
  * Because both live in ONE claim record, this is a READ-time distinction,
    not a second claim/lock: all-or-nothing acquisition is preserved exactly
    as before (still only ever one atomic try_claim_paths() attempt per
    commit, never two separate acquisitions that could reopen the
    partial-hold deadlock risk the analysis above rules out).
    read_live_claims() filters a record's OWN "paths" list down to whichever
    entries are still live for THEIR type (mutex token vs. real path) before
    that record is used for contest-checking or handed to a caller — a
    record whose mutex token has aged past CSA_COMMIT_MUTEX_TTL_SEC simply
    stops contesting on the mutex (even while any real paths it also holds
    are still fully live), and the underlying claim FILE is only actually
    removed once EVERY path it holds has expired (age > max(
    CSA_FILE_CLAIM_TTL_SEC, CSA_COMMIT_MUTEX_TTL_SEC)) — never pruned out
    from under a still-live real-path holder just because its mutex token
    happened to expire first.

DEAD-PID SELF-HEAL (#4670 item 1, 2026-08-30): a claim's "pid" field
records the OWNING PROCESS — deliberately NOT the one-shot pretooluse_bash.py
hook subprocess that WROTE the claim. That subprocess always exits within
milliseconds of writing it, well before the real `git commit`/pre-commit run
the claim exists to protect even starts, so its own os.getpid() would already
read "dead" almost immediately for every claim, live or not — useless as a
liveness signal. The field instead records CLAUDE_PID: the Claude Code CLI's
own long-lived process for the session that made the claim, set in that
process's environment and inherited by every hook subprocess it spawns
(verified empirically 2026-08-30 against a live hook invocation). CLAUDE_PID
persists for the session's entire lifetime and dies exactly when the session
does (crash, kill, window close) — precisely the condition under which a
claim can NEVER be released through the normal PostToolUse path (see
posttooluse_bash.py): that release only ever fires as part of the SAME
session's own Bash tool-call lifecycle, so once the session is gone, nothing
is left alive to run it. See _owner_pid(). Verified 2026-08-30 only against
an interactive hook invocation — whether a launchd-spawned `claude -p`
session (the nightly finishing loop, which commits unattended) inherits
CLAUDE_PID at all is UNVERIFIED; _owner_pid() records NO pid at all (never
a fallback to the writer's own knowably-dead os.getpid()) whenever
CLAUDE_PID cannot be resolved, precisely so that gap degrades to "liveness
unknown" (pid_alive(None) fails open as alive) rather than to a false
"confirmed dead" that would wrongly shorten every such record's TTL.

read_live_claims() (and, threaded through the same code path,
try_claim_paths/poll_claim_paths/status_payload/reset_ledger) calls
pid_alive(rec["pid"]) for every record and, ONLY when it is confirmed dead
(os.kill(pid, 0) -> ProcessLookupError — a missing/unparseable pid, or one
belonging to some other live process entirely, both fail OPEN as "alive" per
this module's usual discipline), shortens that ONE record's effective TTL to
CSA_DEAD_PID_TTL_SEC (default 15s) for BOTH its real-path and commit-mutex
entries — min(ttl, dead_pid_ttl) and min(mutex_ttl, dead_pid_ttl)
respectively — so this can only ever SHORTEN a record's lifetime, never
lengthen it, and a record with a live (or undetermined) owner is completely
unaffected. This closes the "5-minute landmine" a whole-session crash used to
leave behind (#4670: "a dead-pid claim blocking with a misleading
'another agent has uncommitted work' message") — see pretooluse_bash.py gate
4's own honesty fix for the matching deny-message change.

This is a DIFFERENT, narrower problem than the "same session's own retry
blocks on its own leaked claim" scenario #4670 also measured (8 burned
commit attempts one night): there, CLAUDE_PID is still alive throughout (it
is the same live session retrying), so this self-heal correctly does NOT
fire. What actually stops THAT leak is #4670 item 3 (pretooluse_bash.py's
new dirty-`.pre-commit-config.yaml` pre-gate), which denies a doomed pathspec
commit BEFORE gate 4 ever takes a claim for it, so there is nothing left for
that specific, entirely predictable failure to leak in the first place. This
self-heal is the backstop for every OTHER way a claim can outlive its owner,
not a fix for that one root cause.

#4091 — WHAT THE COMMIT MUTEX FIXES, AND WHAT IT STRUCTURALLY CANNOT
(analysis added 2026-08-30, alongside the #4670 fixes above): #4091
recorded TWO distinct pre-commit hazards under real multi-agent concurrency.

  Mechanism 1 — pre-commit's own unstaged-stash cycle silently DISCARDING a
  concurrent agent's uncommitted work — requires TWO pre-commit invocations
  racing in the SAME repo (on the same stash slot / ~/.cache/pre-commit/).
  The per-repo commit mutex above ALREADY serializes commits per repo under
  enforcing() — a second commit's gate-4 claim polls/blocks until the first's
  mutex clears, which structurally rules out two CONCURRENT pre-commit runs
  in that repo, PROVIDED the mutex claim never leaks past a legitimate run's
  own duration. That "provided" is exactly what #4670 items 1 and 3
  (above, and pretooluse_bash.py gate 3c) close: item 1 stops a crashed
  session's claim from wedging the mutex for the full TTL, and item 3 stops
  the single most common, entirely preventable leak (a doomed dirty-config
  retry) from ever taking the mutex at all. So this analysis, not new code
  here, is what closes mechanism 1 — TRANSITIVELY, through the leak fixes
  above — for any repo running with enforcing() ON. Two residual gaps are
  NOT touched by any of this and remain open:
    (a) under LOG-ONLY mode (no enforcing()), gate 4 never actually BLOCKS
        on a contest — see the "LOG-ONLY (not enforcing())" note on
        pretooluse_bash.py's _file_claim_block — so two pre-commit runs can
        still race concurrently there; this repo runs enforcing() globally
        (~/.claude/.enforce) so it is not exposed, but any repo without that
        marker/CSA_ENFORCE is.
    (b) even under enforcing(), a single compound Bash call that legitimately
        outlives CSA_COMMIT_MUTEX_TTL_SEC (default 60s — e.g. a genuinely
        slow pre-commit hook chain) can lose the mutex mid-flight to a SECOND
        commit while the first's pre-commit run is still going — an
        already-documented, pre-existing race (see "Two bounds are still
        worth documenting" below), unrelated to and unchanged by this work.

  Mechanism 2 — a pathspec commit silently ABSORBING a concurrent agent's
  uncommitted edit to a NAMED path (proven empirically 2026-08-30: `git add
  b.py` with content "v1", then edit b.py to "v2" in the working tree, then
  `git commit -- b.py` commits "v2", not the staged "v1" — a pathspec commit
  always reads CURRENT WORKING-TREE content for each named path, regardless
  of what was separately staged) — is NOT mechanically fixable at this
  layer, and this is a considered conclusion, not an unexplored gap. The
  only local, checkable signal — "does this path's working-tree content
  differ from what's in the real git index" (`git status --porcelain`'s
  worktree-modified column) — CANNOT distinguish "a concurrent agent's edit
  got swept in" from "this is simply the agent's OWN, entirely normal,
  never-pre-staged edit", because this runtime's own path-scoped-commit
  convention (`git commit -m "..." -- <path>`, CLAUDE.md §3) almost never
  involves a prior `git add` at all — the pathspec itself does the staging.
  Flagging "worktree differs from index" would therefore false-positive on
  the overwhelming majority of ordinary, hazard-free commits made under this
  very runtime's own mandated convention, not just the rare genuinely-
  hazardous ones. check_staged_scope.py's gate 3 already covers the
  ADJACENT-but-different failure mode of a commit sweeping in UNNAMED paths
  beyond its declared pathspec (see that module's own docstring, "SCOPE/SWEEP
  DECISION") — that is a real, different protection, not a partial fix for
  this one: mechanism 2's hazard is about content PROVENANCE within a
  correctly, narrowly-named path, which is invisible to any check built from
  git's own index/worktree state. Gate 4's real-path claim ALSO only narrows
  this hazard's exposure, never closes it: it protects a path during another
  agent's own ACTIVE commit attempt (a live claim on that exact path), never
  during a plain, pre-commit EDITING window (an agent holds no claim while
  merely mid-editing a file it hasn't yet tried to commit) — precisely the
  gap #4091's three confirmed instances exploited. The operator's own #4091
  comment already named the one change that WOULD close this — committing a
  pre-staged INDEX with no pathspec (`git add <paths>` then `git commit`,
  no `--`) instead of a pathspec — and explicitly declined to adopt it
  unilaterally: it is "a change to the house rule's mechanics, not just
  tooling," i.e. an operator policy decision, not something a hook can
  silently impose. Nothing in this change makes that decision.

Two bounds are still worth documenting explicitly for operators:
  * a claim leaked by a crashed/killed holder stops contesting THAT REPO's
    commit mutex (not any other repo's, and not any real path bundled in the
    same claim) within CSA_COMMIT_MUTEX_TTL_SEC (default 60s) — the deny
    message in that window names the holder so an operator sees exactly
    who/what to check rather than a bare timeout.
  * a single compound Bash call that legitimately runs long (e.g. a slow
    pre-commit hook chain) can outlive the mutex TTL and lose the mutex
    mid-flight, at which point ANOTHER agent's commit may claim it — a
    documented, narrow race window, not a correctness bug in the ledger
    itself (see the plan's v2 "Honesty fix": the mutex serializes commit-vs-
    commit; a concurrent unstaged-edit clobber during that window is a
    separate, undocumented-here risk). CSA_NO_COMMIT_MUTEX=1 is the operator
    rollback lever if this proves disruptive in practice — see
    mutex_enabled().

Subcommands (operator CLI; the PreToolUse/PostToolUse gates call the Python
functions directly, in-process, for speed — see pretooluse_bash.py gate 4 and
posttooluse_bash.py):
  status                  live claims (agent_id, paths, commit_mutex, age).
                          Emits JSON.
  claim-check <id> <paths...>   one non-blocking check-and-claim attempt.
  release <id>             remove that agent's claim.
  reset                    clear stale/malformed claim files.
  doctor                   ledger health.

Config env:
  CSA_FILE_CLAIM_TTL_SEC         claim staleness threshold in seconds (default
                                 300 — long enough to outlast a slow pre-commit
                                 run, short enough that a crashed holder heals
                                 fast; much shorter than agent_budget's 3600s
                                 task lease because a commit is a much shorter
                                 unit of work than an agent task). Governs a
                                 REAL claimed path's own liveness. The
                                 per-repo commit-mutex token bundled into the
                                 same claim record/file uses its own, much
                                 shorter CSA_COMMIT_MUTEX_TTL_SEC instead —
                                 see the "PER-REPO COMMIT MUTEX" section above.
  CSA_COMMIT_MUTEX_TTL_SEC       per-repo commit-mutex self-heal threshold in
                                 seconds (default 60 — a real `git commit`
                                 completes in seconds, not minutes, so a
                                 leaked mutex claim should stop wedging OTHER
                                 commits in that repo far sooner than a real
                                 path claim's own longer TTL warrants). Read
                                 via mutex_ttl_from_env(); mirrors
                                 ttl_from_env()'s own parsing.
  CSA_COMMIT_CLAIM_MAX_WAIT_SEC  bounded poll budget before giving up (default
                                 45 — kept comfortably under the 60s PreToolUse
                                 hook timeout, raised from an earlier 20s so a
                                 real commit-mutex wait — now common, since
                                 every commit in a repo contests every other —
                                 has real room to clear before giving up;
                                 mirrors agent_budget's own "keep well under
                                 the hook timeout" discipline).
  CSA_COMMIT_CLAIM_POLL_SEC      poll interval while contested (default 2.0).
  CSA_DEAD_PID_TTL_SEC           dead-pid self-heal threshold in seconds
                                 (default 15 — see the "DEAD-PID SELF-HEAL"
                                 section above). Applied ONLY to a record
                                 whose owning CLAUDE_PID is confirmed no
                                 longer running; a live (or undetermined)
                                 owner is governed by CSA_FILE_CLAIM_TTL_SEC /
                                 CSA_COMMIT_MUTEX_TTL_SEC exactly as before.
                                 Read via dead_pid_ttl_from_env().
  CSA_LOCK_TIMEOUT_SEC           shared with agent_budget: admission-lock bound
                                 (default 2.0).
  CSA_NO_COMMIT_MUTEX=1          operator rollback lever: disables the
                                 per-repo commit mutex entirely (real
                                 path-scoped claims are unaffected). See
                                 mutex_enabled().
  CSA_DISABLE_HOOKS=1            master OFF.
"""

from __future__ import annotations

import json
import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import agent_budget as ab  # noqa: E402  (reuse the proven flock/backoff primitives)

HOOK_NAME = "file_claims"

DEFAULT_TTL = 300
DEFAULT_MUTEX_TTL = 60
DEFAULT_DEAD_PID_TTL = 15
DEFAULT_MAX_WAIT = 45.0
DEFAULT_POLL = 2.0

CLAIM_PREFIX = "claim-"

# Synthetic per-repo "path" claimed alongside a commit's real target paths so
# every commit in the same repo contests every other one (see the module
# docstring's "PER-REPO COMMIT MUTEX" section). "//" can never appear at the
# start of a normalize_path()'d real relative pathspec (normalize_path only
# ever strips a leading "./", never introduces a leading "/"), so this prefix
# can never collide with a real claimed path.
MUTEX_PREFIX = "//commit-mutex::"


# ---------------------------------------------------------------------------
# PURE helpers.
# ---------------------------------------------------------------------------


def ttl_from_env(environ: dict | None = None) -> int:
    env = os.environ if environ is None else environ
    return ab.parse_int_config(env.get("CSA_FILE_CLAIM_TTL_SEC"), DEFAULT_TTL)


def mutex_ttl_from_env(environ: dict | None = None) -> int:
    """CSA_COMMIT_MUTEX_TTL_SEC — the per-repo commit-mutex's OWN, shorter
    self-heal threshold (default 60s). Mirrors ttl_from_env() exactly, but
    for the mutex token specifically rather than a real claimed path — see
    the module docstring's "PER-REPO COMMIT MUTEX" section for why these two
    TTLs are deliberately different.
    """
    env = os.environ if environ is None else environ
    return ab.parse_int_config(env.get("CSA_COMMIT_MUTEX_TTL_SEC"), DEFAULT_MUTEX_TTL)


def dead_pid_ttl_from_env(environ: dict | None = None) -> int:
    """CSA_DEAD_PID_TTL_SEC — the dead-pid self-heal grace period (default
    15s). Applied ONLY to a record whose owning CLAUDE_PID is confirmed no
    longer running (see the module docstring's "DEAD-PID SELF-HEAL" section
    and pid_alive()) — a live or undetermined owner is unaffected. Mirrors
    ttl_from_env()/mutex_ttl_from_env()'s own parsing.
    """
    env = os.environ if environ is None else environ
    return ab.parse_int_config(env.get("CSA_DEAD_PID_TTL_SEC"), DEFAULT_DEAD_PID_TTL)


def max_wait_from_env(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    return ab.parse_float_config(env.get("CSA_COMMIT_CLAIM_MAX_WAIT_SEC"), DEFAULT_MAX_WAIT)


def poll_from_env(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    return ab.parse_float_config(env.get("CSA_COMMIT_CLAIM_POLL_SEC"), DEFAULT_POLL)


def lock_timeout_from_env(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    return ab.lock_timeout_from_env(env)


def safe_id(agent_id: str) -> str:
    """Sanitize an agent_id into a safe filename token. Mirrors agent_budget.safe_id."""
    return ab.safe_id(agent_id)


def pid_alive(pid) -> bool:
    """True iff `pid` names a currently-running process, OR its liveness
    cannot be determined — this check fails OPEN (treats "unknown" as
    "alive"), matching this module's fail-open discipline everywhere else:
    an unproven liveness must never masquerade as "definitely dead" and
    force an early release of a claim that might still be perfectly valid.

    `os.kill(pid, 0)` sends no signal — it only probes existence/permission:
      * ProcessLookupError -> no such pid exists -> dead (the ONLY case that
        returns False).
      * PermissionError -> the pid exists but is owned by another user ->
        alive.
      * Any other exception, or a non-positive/non-int `pid` (a malformed or
        missing claim field — see _parse_claim_record, where "pid" is
        optional) -> liveness unknown -> alive.

    See the module docstring's "DEAD-PID SELF-HEAL" section for what pid
    actually gets recorded (_owner_pid — CLAUDE_PID, not the writing hook
    subprocess's own os.getpid()) and why that distinction is load-bearing.
    """
    if not isinstance(pid, int) or pid <= 0:
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def _owner_pid() -> int | None:
    """The pid recorded on a NEW claim — see the module docstring's
    "DEAD-PID SELF-HEAL" section for the full reasoning; summary: this is
    deliberately CLAUDE_PID (the Claude Code CLI's own long-lived pid for
    this session, inherited by every hook subprocess it spawns), never
    os.getpid() (the one-shot hook subprocess itself, which is always
    already dead by the time a dead-pid check could matter).

    Returns None — deliberately NOT os.getpid() — when CLAUDE_PID is absent
    or unparseable (Opus review BLOCKER 2, 2026-08-30: an earlier version of
    this function fell back to os.getpid() here, which is a KNOWABLY-DEAD
    pid the instant it is written — recording it silently collapsed that
    record's self-heal window from the full ttl/mutex_ttl down to
    CSA_DEAD_PID_TTL_SEC (15s) wherever CLAUDE_PID happens to be unset,
    reopening #4091 mechanism 1 in precisely the context this whole
    fix claims to close it for: whether a launchd-spawned `claude -p`
    session (the nightly finishing loop, which commits unattended) inherits
    CLAUDE_PID at all is UNVERIFIED, so that fallback was a live, unproven
    correctness risk in the exact caller that matters most. pid_alive(None)
    already fails OPEN as "alive" (see its own docstring and
    test_unknown_pid_field_treated_as_alive_not_dead) — that IS the correct
    behavior for "liveness genuinely unknown", which is what a missing
    CLAUDE_PID actually means. Recording os.getpid() instead converted an
    honest "unknown" into a confident, WRONG "dead" — the exact inversion of
    this module's fail-open discipline everywhere else. Leaving the field
    unpopulated (None -> JSON null -> _parse_claim_record's
    data.get("pid")) is correct here, not "less meaningful" — a real,
    checkable-but-already-dead pid is worse than no pid at all, not merely
    less useful, because it MASQUERADES as a liveness signal instead of
    honestly having none.
    """
    raw = os.environ.get("CLAUDE_PID")
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            pass
    return None


def claim_path(claims_dir: str, agent_id: str) -> str:
    return os.path.join(claims_dir, CLAIM_PREFIX + safe_id(agent_id))


def normalize_path(p: str) -> str:
    """Strip a leading ./ and trailing / so the same file always compares equal.

    A mutex token (see MUTEX_PREFIX/mutex_token) always survives this intact:
    it starts with "//" (never "./", the only prefix stripped) and its
    realpath suffix never ends in "/" (os.path.realpath never returns a
    trailing slash for a real, existing repo directory).
    """
    p = (p or "").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def mutex_token(repo_root: str) -> str:
    """The synthetic claim "path" representing this repo's whole commit slot.

    Claimed ALONGSIDE a commit's real target paths (see pretooluse_bash.py
    gate 4) so every commit in the same repo contests every OTHER concurrent
    commit's claim too, regardless of real path overlap — this is what makes
    "only one commit in flight per repo at a time" mechanical. Realpath'd so
    two different spellings of the same repo (a symlink, a relative vs.
    absolute cwd) always collapse onto the same token.
    """
    return MUTEX_PREFIX + os.path.realpath(repo_root)


def is_mutex_token(p: str) -> bool:
    """True iff `p` is a commit-mutex token rather than a real claimed path."""
    return isinstance(p, str) and p.startswith(MUTEX_PREFIX)


def mutex_enabled(environ: dict | None = None) -> bool:
    """False iff CSA_NO_COMMIT_MUTEX=1 — the operator rollback lever for the
    per-repo commit mutex (real path-scoped claims are unaffected either way).
    True (mutex ON) is the default.
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_NO_COMMIT_MUTEX", "") != "1"


def paths_overlap(a: set, b: set) -> bool:
    """True iff the two path sets share a member, OR one entry is a directory
    prefix of another (e.g. "modules" and "modules/x.py" overlap). Pure.

    Prefix-aware so a directory-scoped claim correctly overlaps a file inside
    it. This intentionally also makes two commit-mutex tokens (see
    MUTEX_PREFIX) contest each other whenever one repo's realpath is nested
    inside another's — an accepted, documented side effect of reusing the
    same overlap rule for synthetic mutex "paths", not a bug: a commit in a
    nested repo genuinely does touch a subtree of the outer repo's mutex
    scope.
    """
    for x in a:
        for y in b:
            if x == y or x.startswith(y + "/") or y.startswith(x + "/"):
                return True
    return False


def find_contest(target_paths: set, live_claims: list, self_agent_id: str) -> dict | None:
    """First OTHER agent's live claim overlapping target_paths, or None. Pure."""
    for rec in live_claims:
        if rec.get("agent_id") == self_agent_id:
            continue
        if paths_overlap(target_paths, set(rec.get("paths", []))):
            return rec
    return None


# ---------------------------------------------------------------------------
# Ledger I/O — the only impure layer.
# ---------------------------------------------------------------------------


def _parse_claim_record(raw: str) -> dict | None:
    """Parse one claim file's JSON body into a well-formed record, or None.

    Split out from _read_claim so the parsing logic itself is unit-testable
    without touching the filesystem.
    """
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        agent_id = data["agent_id"]
        paths = data["paths"]
        claimed_at = float(data["claimed_at"])
    except Exception:
        return None
    if not isinstance(agent_id, str) or not agent_id:
        return None
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return None
    return {
        "agent_id": agent_id,
        "pid": data.get("pid"),
        "claimed_at": claimed_at,
        "paths": sorted({normalize_path(p) for p in paths if p and p.strip()}),
    }


def _read_claim(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception:
        return None
    return _parse_claim_record(raw)


def read_live_claims(
    claims_dir: str,
    ttl: int,
    now: float | None = None,
    mutex_ttl: int | None = None,
    dead_pid_ttl: int | None = None,
) -> list:
    """Prune stale/malformed claim files; return the well-formed, live ones.

    Staleness is PER-PATH-TYPE, not uniform, because a commit-mutex token
    (see MUTEX_PREFIX) bundled into a record alongside real claimed paths
    must self-heal at its own, much shorter `mutex_ttl`
    (CSA_COMMIT_MUTEX_TTL_SEC) while any real paths in that SAME record still
    honor the full `ttl` (CSA_FILE_CLAIM_TTL_SEC) — see the module
    docstring's "PER-REPO COMMIT MUTEX" section. Concretely, for a
    well-formed record of age `age = now - claimed_at`:
      * the record's underlying FILE is removed (self-heal) entirely once
        `age > max(eff_ttl, eff_mutex_ttl)` — every path type it could hold
        has expired by then, so there is nothing left worth keeping on disk.
      * short of that, the record SURVIVES but its returned "paths" list is
        filtered down to only the entries still live for their own type
        (mutex tokens dropped once `age > eff_mutex_ttl`, real paths dropped
        once `age > eff_ttl`) — a record left with an empty filtered path list
        (e.g. `mutex_ttl < ttl` and the record holds ONLY a mutex token) is
        omitted from the returned list (nothing left to contest on) without
        removing its file early; the next claim attempt for that same
        agent_id overwrites it via _write_claim, or it eventually crosses
        the full self-heal threshold above.
    `eff_ttl`/`eff_mutex_ttl` are `ttl`/`mutex_ttl` themselves UNLESS this
    record's owning pid (pid_alive(rec["pid"])) is confirmed dead, in which
    case each is additionally clamped to `dead_pid_ttl`
    (CSA_DEAD_PID_TTL_SEC, default 15s — see the module docstring's
    "DEAD-PID SELF-HEAL" section) — this can only ever SHORTEN a record's
    effective lifetime, never lengthen it, and is computed once per record
    (a single owning pid governs every path — real or mutex — that record
    holds).
    A malformed/unparseable file is always removed outright, regardless of
    age. Mirrors agent_budget.prune_and_count's self-heal shape. Never
    raises; a missing or unreadable claims_dir fails open (returns []).
    """
    if now is None:
        now = ab._now_epoch()
    if mutex_ttl is None:
        mutex_ttl = mutex_ttl_from_env()
    if dead_pid_ttl is None:
        dead_pid_ttl = dead_pid_ttl_from_env()
    try:
        if not os.path.isdir(claims_dir) or not os.access(claims_dir, os.R_OK):
            return []
        entries = os.listdir(claims_dir)
    except Exception:
        return []
    live = []
    for name in entries:
        if not name.startswith(CLAIM_PREFIX):
            continue
        path = os.path.join(claims_dir, name)
        if not os.path.exists(path):
            continue
        rec = _read_claim(path)
        if rec is None:
            ab._remove(path)  # malformed -> self-heal
            continue
        eff_ttl, eff_mutex_ttl = ttl, mutex_ttl
        if not pid_alive(rec.get("pid")):
            eff_ttl = min(ttl, dead_pid_ttl)
            eff_mutex_ttl = min(mutex_ttl, dead_pid_ttl)
        full_ttl = max(eff_ttl, eff_mutex_ttl)
        age = now - rec["claimed_at"]
        if age > full_ttl:
            ab._remove(path)  # every path type expired -> self-heal
            continue
        live_paths = [p for p in rec["paths"] if age <= (eff_mutex_ttl if is_mutex_token(p) else eff_ttl)]
        if not live_paths:
            continue  # nothing left of this record is still live to contest on
        if live_paths != rec["paths"]:
            rec = dict(rec, paths=live_paths)
        live.append(rec)
    return live


def _write_claim(claims_dir: str, agent_id: str, paths: list, claimed_at: float) -> None:
    """Atomically persist a claim (temp file in the SAME dir + os.replace).

    The "pid" field is _owner_pid() — CLAUDE_PID, not this writer's own
    os.getpid() — see pid_alive()'s docstring and the module docstring's
    "DEAD-PID SELF-HEAL" section for why that distinction is load-bearing.
    May be None when CLAUDE_PID is unavailable (never os.getpid() as a
    fallback — see _owner_pid()'s own docstring) — pid_alive(None) fails
    open as "alive", exactly like any other unresolvable pid.
    """
    ab._ensure_dir(claims_dir)
    path = claim_path(claims_dir, agent_id)
    tmp = f"{path}.tmp.{os.getpid()}"
    body = {"agent_id": agent_id, "pid": _owner_pid(), "claimed_at": claimed_at, "paths": paths}
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def release_claim(claims_dir: str, agent_id: str) -> None:
    """Remove agent_id's claim, if any. Best-effort; never raises."""
    ab._remove(claim_path(claims_dir, agent_id))


# ---------------------------------------------------------------------------
# The atomic all-or-nothing claim attempt — the deadlock-proofing core.
# ---------------------------------------------------------------------------


def try_claim_paths(
    claims_dir: str,
    ttl: int,
    agent_id: str,
    paths,
    lock_timeout: float,
    now: float | None = None,
    mutex_ttl: int | None = None,
    dead_pid_ttl: int | None = None,
) -> tuple:
    """One atomic check-and-claim attempt. Returns (claimed, contesting_claim).

    On success, ALL of `paths` are now claimed by agent_id under ONE claim file
    (never partial). On contest, NOTHING is claimed. This all-or-nothing shape
    is what makes the ledger deadlock-proof — see the module docstring.

    `mutex_ttl` (default: mutex_ttl_from_env() when None) is threaded into
    read_live_claims() so a commit-mutex token bundled into `paths` is judged
    for contest purposes against its own, shorter TTL rather than `ttl` — see
    the module docstring's "PER-REPO COMMIT MUTEX" section. Callers that never
    claim a mutex token (no MUTEX_PREFIX entry in `paths`) are unaffected by
    this parameter either way. `dead_pid_ttl` (default: dead_pid_ttl_from_env()
    when None) is threaded the same way for the "DEAD-PID SELF-HEAL" section.

    Fails OPEN: an unacquirable lock claims through untracked (True, None)
    rather than wedging the committer. An empty/blank path set is a no-op
    success (nothing to protect, matching check_staged_scope's "empty-index").
    """
    if now is None:
        now = ab._now_epoch()
    if mutex_ttl is None:
        mutex_ttl = mutex_ttl_from_env()
    if dead_pid_ttl is None:
        dead_pid_ttl = dead_pid_ttl_from_env()
    target = {normalize_path(p) for p in paths if p and p.strip()}
    if not target:
        return True, None
    with ab.admission_lock(claims_dir, timeout_s=lock_timeout) as locked:
        if not locked:
            return True, None  # fail open — never wedge on an unavailable lock
        live = read_live_claims(claims_dir, ttl, now, mutex_ttl, dead_pid_ttl)
        contest = find_contest(target, live, agent_id)
        if contest is not None:
            return False, contest
        _write_claim(claims_dir, agent_id, sorted(target), now)
        return True, None


def poll_claim_paths(
    claims_dir: str,
    ttl: int,
    agent_id: str,
    paths,
    lock_timeout: float,
    max_wait: float,
    poll: float,
    *,
    wall_now=None,
    mono_now=None,
    sleep_fn=None,
    jitter_fn=None,
    mutex_ttl: int | None = None,
    dead_pid_ttl: int | None = None,
) -> dict:
    """Retry try_claim_paths, jittered, until claimed or max_wait elapses.

    Each attempt is a FRESH atomic all-or-nothing try — never a partial hold
    between attempts (see module docstring: this is what rules out deadlock,
    leaving only bounded livelock, which this bound terminates).

    `mutex_ttl`/`dead_pid_ttl` (default: resolved once per try_claim_paths
    call via mutex_ttl_from_env()/dead_pid_ttl_from_env() when None) are
    threaded through unchanged on every attempt — see try_claim_paths' own
    docstring.

    Returns {"claimed": bool, "contest": dict|None, "waited": float}.
    """
    wall_now = ab._now_epoch if wall_now is None else wall_now
    mono_now = ab._mono if mono_now is None else mono_now
    sleep_fn = ab._sleep if sleep_fn is None else sleep_fn
    jitter_fn = ab._jitter if jitter_fn is None else jitter_fn

    start = mono_now()
    deadline = start + (max_wait if max_wait > 0 else 0.0)
    last_contest = None
    while True:
        claimed, contest = try_claim_paths(
            claims_dir,
            ttl,
            agent_id,
            paths,
            lock_timeout,
            now=wall_now(),
            mutex_ttl=mutex_ttl,
            dead_pid_ttl=dead_pid_ttl,
        )
        if claimed:
            return {"claimed": True, "contest": None, "waited": mono_now() - start}
        last_contest = contest
        remaining = deadline - mono_now()
        if remaining <= 0:
            return {"claimed": False, "contest": last_contest, "waited": mono_now() - start}
        sleep_fn(min(jitter_fn(poll), remaining))


# ---------------------------------------------------------------------------
# Status / operator-facing views.
# ---------------------------------------------------------------------------


def split_mutex_paths(paths) -> tuple[list, list]:
    """Split a raw path/claim-target list into (real_paths, mutex_repos).

    `real_paths` holds every entry that is NOT a commit-mutex token, in the
    input's given order. `mutex_repos` holds the repo each mutex token
    represents (MUTEX_PREFIX stripped, so it reads as a plain repo path).
    Non-string entries are skipped rather than raising (matching this
    module's fail-open discipline elsewhere). Pure; never raises.

    Factored out of status_payload() (which used to do this splitting
    inline) so any OTHER caller — e.g. pretooluse_bash.py's LOG-ONLY
    "would-wait" log line, which otherwise dumps the raw
    "//commit-mutex::..." token inline in its `paths=` field, contradicting
    status_payload's own stated intent of never surfacing that raw token to
    an operator — can reuse the exact same split logic without duplicating
    it.
    """
    real_paths: list = []
    mutex_repos: list = []
    for p in paths or []:
        if not isinstance(p, str):
            continue
        if is_mutex_token(p):
            mutex_repos.append(p[len(MUTEX_PREFIX) :])
        else:
            real_paths.append(p)
    return real_paths, mutex_repos


def status_payload(
    claims_dir: str,
    ttl: int,
    now: float | None = None,
    mutex_ttl: int | None = None,
    dead_pid_ttl: int | None = None,
) -> dict:
    """Operator-facing live-claims view. Splits any commit-mutex token out of
    a claim's "paths" into its own "commit_mutex" list via split_mutex_paths()
    — showing the raw "//commit-mutex::..." token inline with real paths only
    confuses debugging (status/doctor CLI, contest logs).

    `mutex_ttl`/`dead_pid_ttl` (default: mutex_ttl_from_env()/
    dead_pid_ttl_from_env() when None) are threaded into read_live_claims()
    so an expired mutex token, or a dead-pid record past its shorter grace
    period, never shows up here as still "live" — see that function's
    docstring. Each entry also reports "pid_alive" (pid_alive(rec["pid"])) so
    an operator can see AT A GLANCE, without a separate `ps` call, whether a
    still-live entry is a genuinely in-flight commit or one riding out its
    dead-pid grace period.
    """
    if now is None:
        now = ab._now_epoch()
    if mutex_ttl is None:
        mutex_ttl = mutex_ttl_from_env()
    if dead_pid_ttl is None:
        dead_pid_ttl = dead_pid_ttl_from_env()
    live = read_live_claims(claims_dir, ttl, now, mutex_ttl, dead_pid_ttl)
    entries = []
    for rec in live:
        paths, commit_mutex = split_mutex_paths(rec["paths"])
        entries.append(
            {
                "agent_id": rec["agent_id"],
                "pid": rec.get("pid"),
                "pid_alive": pid_alive(rec.get("pid")),
                "age_sec": round(now - rec["claimed_at"], 1),
                "paths": paths,
                "commit_mutex": commit_mutex,
            }
        )
    return {"ttl_sec": ttl, "live_claims": entries}


def reset_ledger(
    claims_dir: str,
    ttl: int,
    now: float | None = None,
    mutex_ttl: int | None = None,
    dead_pid_ttl: int | None = None,
) -> int:
    """Remove every stale/malformed claim; return the count removed.

    A record is stale (fully removed) once EVERY path type it could hold has
    expired — `age > max(eff_ttl, eff_mutex_ttl)`, mirroring read_live_claims'
    own full-removal threshold exactly, INCLUDING its dead-pid clamp: a
    record whose owning pid is confirmed dead (pid_alive) is judged against
    `min(ttl, dead_pid_ttl)`/`min(mutex_ttl, dead_pid_ttl)` instead of the
    plain `ttl`/`mutex_ttl` — see read_live_claims() and the module
    docstring's "DEAD-PID SELF-HEAL" section. A record whose real paths are
    still within its (possibly dead-pid-clamped) `eff_ttl` is NOT removed
    here just because its bundled mutex token (if any) has already aged past
    the shorter `eff_mutex_ttl`.
    """
    if now is None:
        now = ab._now_epoch()
    if mutex_ttl is None:
        mutex_ttl = mutex_ttl_from_env()
    if dead_pid_ttl is None:
        dead_pid_ttl = dead_pid_ttl_from_env()
    removed = 0
    try:
        if not os.path.isdir(claims_dir):
            return 0
        entries = os.listdir(claims_dir)
    except Exception:
        return 0
    for name in entries:
        if not name.startswith(CLAIM_PREFIX):
            continue
        path = os.path.join(claims_dir, name)
        if not os.path.exists(path):
            continue
        rec = _read_claim(path)
        if rec is None:
            stale = True
        else:
            eff_ttl, eff_mutex_ttl = ttl, mutex_ttl
            if not pid_alive(rec.get("pid")):
                eff_ttl = min(ttl, dead_pid_ttl)
                eff_mutex_ttl = min(mutex_ttl, dead_pid_ttl)
            stale = (now - rec["claimed_at"]) > max(eff_ttl, eff_mutex_ttl)
        if stale and ab._remove(path):
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Thin CLI — operator debugging (status/doctor/reset/release) and a
# non-blocking claim-check entry point usable outside the hook process.
# ---------------------------------------------------------------------------


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        if _lib.disabled():
            return 0
        sub = argv[0] if argv else "status"
        ttl = ttl_from_env()
        mutex_ttl = mutex_ttl_from_env()
        dead_pid_ttl = dead_pid_ttl_from_env()
        lock_timeout = lock_timeout_from_env()

        if sub == "status":
            print(
                json.dumps(
                    status_payload(_lib.FILE_CLAIMS_DIR, ttl, mutex_ttl=mutex_ttl, dead_pid_ttl=dead_pid_ttl),
                    indent=2,
                )
            )
            return 0

        if sub == "claim-check":
            rest = argv[1:]
            if len(rest) < 2:
                print("usage: file_claims.py claim-check <agent_id> <path> [<path>...]", file=sys.stderr)
                return 2
            agent_id, paths = rest[0], rest[1:]
            claimed, contest = try_claim_paths(
                _lib.FILE_CLAIMS_DIR,
                ttl,
                agent_id,
                paths,
                lock_timeout,
                mutex_ttl=mutex_ttl,
                dead_pid_ttl=dead_pid_ttl,
            )
            if claimed:
                print(f"OK claimed {len(paths)} path(s) for {agent_id}")
                return 0
            print(f"CONTESTED by {contest.get('agent_id')} (paths={contest.get('paths')})")
            return 1

        if sub == "release":
            rest = argv[1:]
            if not rest:
                print("usage: file_claims.py release <agent_id>", file=sys.stderr)
                return 2
            release_claim(_lib.FILE_CLAIMS_DIR, rest[0])
            print(f"OK released {rest[0]}")
            return 0

        if sub == "reset":
            removed = reset_ledger(_lib.FILE_CLAIMS_DIR, ttl, mutex_ttl=mutex_ttl, dead_pid_ttl=dead_pid_ttl)
            print(f"OK reset (removed {removed} stale/corrupt claim(s))")
            return 0

        if sub == "doctor":
            live = read_live_claims(_lib.FILE_CLAIMS_DIR, ttl, mutex_ttl=mutex_ttl, dead_pid_ttl=dead_pid_ttl)
            writable = os.path.isdir(_lib.FILE_CLAIMS_DIR) and os.access(_lib.FILE_CLAIMS_DIR, os.W_OK)
            lines = [
                "file_claims doctor",
                f"  claims_dir     : {_lib.FILE_CLAIMS_DIR} (writable={'yes' if writable else 'no'})",
                f"  ttl_sec        : {ttl} (CSA_FILE_CLAIM_TTL_SEC)",
                f"  mutex_ttl_sec  : {mutex_ttl} (CSA_COMMIT_MUTEX_TTL_SEC)",
                f"  dead_pid_ttl_sec: {dead_pid_ttl} (CSA_DEAD_PID_TTL_SEC)",
                f"  max_wait_sec   : {max_wait_from_env()} (CSA_COMMIT_CLAIM_MAX_WAIT_SEC)",
                f"  poll_sec       : {poll_from_env()} (CSA_COMMIT_CLAIM_POLL_SEC)",
                f"  live_claims    : {len(live)}",
                "  fail_mode      : OPEN (advisory ledger; corrupt state self-heals)",
            ]
            print("\n".join(lines))
            return 0

        print(
            "usage: file_claims.py {status|claim-check <id> <paths...>|release <id>|reset|doctor}",
            file=sys.stderr,
        )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
