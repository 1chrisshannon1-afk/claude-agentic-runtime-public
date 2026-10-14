"""churn_tracker — informational commit-churn / thrashing observer.

Flags (never blocks — this is PURELY informational, LOG-ONLY always, with NO
`enforcing()`-gated hard-block path at all in v1) when the same file has been
touched by 3+ commits in a short window (configurable, default 2 hours)
WITHOUT an intervening review outcome recorded as clean for that repo.

ARCHITECTURE mirrors file_claims.py exactly:
  * This module is git-agnostic — it knows nothing about `git commit` syntax.
    All commit/path-scope detection (is this event a real `git commit`? which
    paths does it target?) lives in pretooluse_bash.py's gate-5 wiring, which
    reuses check_staged_scope.py's is_git_commit/commit_pathspec/
    read_staged_paths helpers — precisely how file_claims.py's gate 4 already
    works (file_claims.py itself has no git knowledge either).
  * PURE decision helpers (grouping, counting, threshold-checking) + a thin
    impure I/O layer (atomic temp-file + os.replace writes, TTL-pruned reads)
    + a CLI `main()` for operator debugging (status/doctor/reset), exactly
    like file_claims.py.

LEDGER SHAPE: one JSON file per OBSERVATION (repo_root, sha, a per-call unique
nonce — see `_commit_file`/`record_commit`) under ~/.claude/.churn/, recording
``{"repo_root":, "sha":, "timestamp":, "paths": [...] }`` — the sha is whatever
`git rev-parse HEAD` resolves to AT OBSERVATION TIME. Re-observing the SAME
(repo_root, sha) — e.g. a retried commit attempt that never actually lands —
adds a NEW file rather than overwriting the earlier one; collapsing those
would silently under-count the exact "same fix attempted repeatedly without a
new commit landing" pattern this module exists to catch (CORRECTNESS 21).

DESIGN NOTE — why "sha" is the commit's PARENT, and why that's fine here:
this module is observed ONLY from a PreToolUse hook (see pretooluse_bash.py
gate 5), which fires BEFORE `git commit` runs. The resulting commit's own
hash cannot be known at that point — git computes it from the tree, parent,
message, and author/committer identity+timestamp, none of which are cheaply
reproducible in a lightweight hook. So the sha recorded for a commit-in-flight
is necessarily the CURRENT HEAD (that commit's parent), not its own resulting
hash. This does not defeat the "clean review resets the count" heuristic: a
review always targets the LATEST HEAD, so the commit attempt immediately
FOLLOWING a clean review observes current HEAD == the exact reviewed sha,
which is precisely the sha this module needs to see in its OWN ledger to
recognize the reset boundary (see `clean_reviewed_shas` / `_clean_reset_
timestamp`). This is a deliberate, documented, best-effort approximation —
matching the spawning task's explicit allowance ("a straightforward
sha-in-ledger-with-a-later-timestamp check is fine, this doesn't need to be a
full graph traversal"), not a full ancestor/graph walk.

Subcommands (operator CLI):
  status    every repo with a currently-flagged path (>= threshold commits
            since the last clean review, within the window). Emits JSON.
  reset     clear stale/malformed commit records.
  doctor    ledger health.

Config env:
  CSA_CHURN_WINDOW_SEC   the churn window in seconds (default 7200 = 2h). Also
                         doubles as the self-heal TTL for pruning commit
                         records on read — anything older than the window is,
                         by definition, irrelevant to churn counting.
  CSA_CHURN_THRESHOLD    commits-without-a-clean-review threshold (default 3).
  CSA_LOCK_TIMEOUT_SEC   shared with agent_budget/file_claims (unused directly
                         by this module today — no lock-protected critical
                         section exists yet — kept for parity/future use).
  CSA_DISABLE_HOOKS=1    master OFF.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)
import agent_budget as ab  # noqa: E402  (reuse proven config/ledger primitives)
import record_review as rr  # noqa: E402  (shared outcome-aware ledger read)

HOOK_NAME = "churn_tracker"

DEFAULT_WINDOW_SEC = 2 * 60 * 60  # 2 hours
DEFAULT_THRESHOLD = 3

COMMIT_PREFIX = "commit-"


# ---------------------------------------------------------------------------
# Env config — PURE.
# ---------------------------------------------------------------------------


def window_from_env(environ: dict | None = None) -> int:
    env = os.environ if environ is None else environ
    return ab.parse_int_config(env.get("CSA_CHURN_WINDOW_SEC"), DEFAULT_WINDOW_SEC)


def threshold_from_env(environ: dict | None = None) -> int:
    env = os.environ if environ is None else environ
    return ab.parse_int_config(env.get("CSA_CHURN_THRESHOLD"), DEFAULT_THRESHOLD)


def lock_timeout_from_env(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    return ab.lock_timeout_from_env(env)


# ---------------------------------------------------------------------------
# PURE helpers.
# ---------------------------------------------------------------------------


def normalize_path(p: str) -> str:
    """Strip a leading ./ and trailing / so the same file always compares
    equal — mirrors file_claims.normalize_path exactly (shared convention)."""
    p = (p or "").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _commit_file(churn_dir: str, repo_root: str, sha: str, nonce: str) -> str:
    """Filename keyed by (repo, sha, nonce): EVERY observation gets its own
    file, even when re-observing the SAME (repo, sha).

    CORRECTNESS 21 fix: this used to be keyed by (repo, sha) alone, so
    re-observing an UNCHANGED HEAD — e.g. a retried commit attempt that never
    actually lands, or a duplicate hook fire — silently OVERWROTE the earlier
    observation instead of adding to it. That under-counted the exact pattern
    this module exists to catch: "same fix attempted repeatedly without a new
    commit landing." `nonce` (a short unique token; see :func:`record_commit`)
    is what makes each call distinct on disk. The ledger is still bounded: the
    read path (:func:`read_live_commits`) TTL-prunes anything older than the
    churn window on every read, so extra per-attempt files never accumulate
    past that window.
    """
    return os.path.join(
        churn_dir,
        f"{COMMIT_PREFIX}{ab.safe_id(repo_root)}-{ab.safe_id(sha)}-{ab.safe_id(nonce)}.json",
    )


def path_commit_counts(records: list, repo_root: str) -> dict:
    """Group live commit records touching `repo_root`, by path, each entry
    carrying its (sha, timestamp) — sorted oldest-first. Pure.
    """
    by_path: dict[str, list[dict]] = {}
    for rec in records:
        if rec.get("repo_root") != repo_root:
            continue
        for p in rec.get("paths", []):
            by_path.setdefault(p, []).append({"sha": rec["sha"], "timestamp": rec["timestamp"]})
    for entries in by_path.values():
        entries.sort(key=lambda e: e["timestamp"])
    return by_path


def _clean_reset_timestamp(commits: list, clean_shas: set, window_start: float) -> float | None:
    """The timestamp of the LATEST commit in `commits` whose sha both (a) has
    a clean review recorded (its sha is in `clean_shas`) and (b) postdates
    `window_start`. Commits AFTER this timestamp count toward churn; this one
    and everything before it are considered "resolved" by that clean review.
    None when no such commit exists. Pure; O(n).
    """
    latest: float | None = None
    for c in commits:
        if c["sha"] in clean_shas and c["timestamp"] >= window_start:
            if latest is None or c["timestamp"] > latest:
                latest = c["timestamp"]
    return latest


def count_since_clean_review(commits: list, clean_shas: set, window_start: float) -> int:
    """The number of commits in `commits` that count toward churn: every
    commit within the window, EXCLUDING any at/before the latest
    clean-reviewed commit — a clean review resets the count. Pure.
    """
    in_window = [c for c in commits if c["timestamp"] >= window_start]
    reset_at = _clean_reset_timestamp(commits, clean_shas, window_start)
    if reset_at is None:
        return len(in_window)
    return len([c for c in in_window if c["timestamp"] > reset_at])


def flagged_paths(
    records: list,
    repo_root: str,
    clean_shas: set,
    threshold: int,
    window_start: float,
) -> dict:
    """{path: count} for every path whose post-reset commit count within the
    window is AT/OVER `threshold`. Pure — the single source of truth both the
    gate-5 observer and the CLI `status` view build on.
    """
    by_path = path_commit_counts(records, repo_root)
    out: dict[str, int] = {}
    for path, commits in by_path.items():
        n = count_since_clean_review(commits, clean_shas, window_start)
        if n >= threshold:
            out[path] = n
    return out


# ---------------------------------------------------------------------------
# Ledger I/O — the only impure layer (besides the git plumbing below).
# ---------------------------------------------------------------------------


def _parse_commit_record(raw: str) -> dict | None:
    """Parse one commit record file's JSON body, or None. Split out from
    _read_commit so parsing is unit-testable without touching the filesystem.
    """
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    try:
        repo_root = data["repo_root"]
        sha = data["sha"]
        timestamp = float(data["timestamp"])
        paths = data["paths"]
    except Exception:
        return None
    if not isinstance(repo_root, str) or not repo_root:
        return None
    if not isinstance(sha, str) or not sha:
        return None
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return None
    return {
        "repo_root": repo_root,
        "sha": sha,
        "timestamp": timestamp,
        "paths": sorted({normalize_path(p) for p in paths if p and p.strip()}),
    }


def _read_commit(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception:
        return None
    return _parse_commit_record(raw)


def read_live_commits(churn_dir: str, ttl: int, now: float | None = None) -> list:
    """Prune stale/malformed commit records; return the well-formed, live
    ones. Mirrors file_claims.read_live_claims's self-heal-on-read shape. A
    record is stale when unparsable or older than `ttl`. Never raises; a
    missing or unreadable churn_dir fails open (returns []).
    """
    if now is None:
        now = ab._now_epoch()
    try:
        if not os.path.isdir(churn_dir) or not os.access(churn_dir, os.R_OK):
            return []
        entries = os.listdir(churn_dir)
    except Exception:
        return []
    live = []
    for name in entries:
        if not name.startswith(COMMIT_PREFIX):
            continue
        path = os.path.join(churn_dir, name)
        if not os.path.exists(path):
            continue
        rec = _read_commit(path)
        if rec is None:
            ab._remove(path)  # malformed -> self-heal
            continue
        age = now - rec["timestamp"]
        if age > ttl:
            ab._remove(path)  # stale -> self-heal
            continue
        live.append(rec)
    return live


def _write_commit(
    churn_dir: str, repo_root: str, sha: str, paths: list, timestamp: float, nonce: str
) -> None:
    """Atomically persist a commit record (temp file in the SAME dir +
    os.replace) — mirrors file_claims._write_claim exactly."""
    ab._ensure_dir(churn_dir)
    path = _commit_file(churn_dir, repo_root, sha, nonce)
    tmp = f"{path}.tmp.{os.getpid()}"
    body = {"repo_root": repo_root, "sha": sha, "timestamp": timestamp, "paths": paths}
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def record_commit(
    churn_dir: str,
    repo_root: str,
    sha: str,
    paths,
    now: float | None = None,
    nonce: str | None = None,
) -> None:
    """Record one commit event touching `paths` for `repo_root`+`sha`.
    Best-effort; never raises. A blank repo_root/sha, or an empty (post-
    normalization) path set, is a no-op — nothing to track.

    `nonce` defaults to a fresh random token per call (via ``uuid.uuid4``) so
    re-observing an UNCHANGED (repo_root, sha) — the exact "same fix retried,
    no new commit landed" pattern this module exists to catch — ADDS a new
    record rather than silently overwriting the earlier one (CORRECTNESS 21).
    A caller may pass an explicit `nonce` to force a deterministic/idempotent
    overwrite in the rare case that's actually wanted; nothing in this
    codebase currently does.
    """
    if now is None:
        now = ab._now_epoch()
    normalized = sorted({normalize_path(p) for p in paths if p and p.strip()})
    if not repo_root or not sha or not normalized:
        return
    if not nonce:
        nonce = uuid.uuid4().hex[:12]
    _write_commit(churn_dir, repo_root, sha, normalized, now, nonce)


def reset_ledger(churn_dir: str, ttl: int, now: float | None = None) -> int:
    """Remove every stale/malformed commit record; return the count removed."""
    if now is None:
        now = ab._now_epoch()
    removed = 0
    try:
        if not os.path.isdir(churn_dir):
            return 0
        entries = os.listdir(churn_dir)
    except Exception:
        return 0
    for name in entries:
        if not name.startswith(COMMIT_PREFIX):
            continue
        path = os.path.join(churn_dir, name)
        if not os.path.exists(path):
            continue
        rec = _read_commit(path)
        stale = rec is None or (now - rec["timestamp"]) > ttl
        if stale and ab._remove(path):
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# record_review.py cross-reference — "an intervening CLEAN review" lookup.
# ---------------------------------------------------------------------------


def clean_reviewed_shas(records: list, repo_root: str, last_reviewed_path: str) -> set:
    """The set of shas (drawn ONLY from our OWN churn ledger for `repo_root`)
    that have a CLEAN outcome recorded in record_review.py's ledger.

    Best-effort per the module docstring's design note: this checks only shas
    THIS module has itself already observed committed (never a full repo
    history / graph walk) — sufficient because the churn window only ever
    needs to reason about recently-observed shas anyway. Never raises; any
    lookup failure for a given sha is treated as "not clean" (fail toward
    still counting churn, the conservative/safe direction for a purely
    informational nudge).
    """
    shas = {rec["sha"] for rec in records if rec.get("repo_root") == repo_root}
    clean: set[str] = set()
    for sha in shas:
        try:
            outcome = rr.head_review_outcome(last_reviewed_path, repo_root, sha)
        except Exception:
            outcome = None
        if outcome is not None and outcome[0] == rr.OUTCOME_CLEAN:
            clean.add(sha)
    return clean


# ---------------------------------------------------------------------------
# Git plumbing — the only OTHER impure layer, isolated so the pure functions
# above stay trivially testable. Each degrades to "" on any failure.
# ---------------------------------------------------------------------------


def _git(where: str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", where, *args],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def repo_root_of(where: str) -> str:
    """`git rev-parse --show-toplevel` at `where`, or "" on any failure."""
    return _git(where, "rev-parse", "--show-toplevel")


def _current_head(repo_root: str) -> str:
    """`git rev-parse HEAD` at `repo_root`, or "" on any failure (no repo, no
    HEAD yet, git missing). See the module docstring's design note: this is
    necessarily the commit-in-flight's PARENT, not its own resulting hash —
    the earliest sha a PreToolUse-time observer can possibly know.
    """
    return _git(repo_root, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# The observer entry point — what pretooluse_bash's gate 5 (and tests) drive.
# ---------------------------------------------------------------------------


def observe_commit(
    churn_dir: str,
    last_reviewed_path: str,
    repo_root: str,
    sha: str,
    paths,
    window: int,
    threshold: int,
    now: float | None = None,
) -> dict:
    """Record one commit event for repo_root+sha touching `paths`, then report
    which of THOSE paths JUST crossed the churn threshold on THIS observation
    — i.e. this is the exact commit whose count first reached `threshold`,
    not merely "still at or over it" (CORRECTNESS 9). Since each call to this
    function adds AT MOST one new commit record for a given path (one call =
    one observed commit), a path's post-reset count can only increase by 1 per
    call, so "count == threshold" on the call that just wrote a record IS
    "just crossed" — a path already past threshold before this call keeps
    climbing (threshold+1, +2, ...) and is correctly NOT re-reported on every
    later touch; that would just be re-flagging the same crossing over and
    over, which is what this filter exists to prevent (matches the docstring
    "per path that just crossed the threshold" for real, not just in name).

    This is a PURE OBSERVER: its only side effect is the ledger write; it
    NEVER blocks and NEVER raises — any internal error degrades to an empty
    report (a missed observation is harmless; this module is purely
    informational). Returns ``{"newly_flagged": {path: count}}``.
    """
    if now is None:
        now = ab._now_epoch()
    try:
        normalized_paths = sorted({normalize_path(p) for p in paths if p and p.strip()})
        if not repo_root or not sha or not normalized_paths:
            return {"newly_flagged": {}}
        record_commit(churn_dir, repo_root, sha, normalized_paths, now)
        records = read_live_commits(churn_dir, window, now)
        clean = clean_reviewed_shas(records, repo_root, last_reviewed_path)
        window_start = now - window
        flagged = flagged_paths(records, repo_root, clean, threshold, window_start)
        this_set = set(normalized_paths)
        return {
            "newly_flagged": {
                p: n for p, n in flagged.items() if p in this_set and n == threshold
            }
        }
    except Exception:
        return {"newly_flagged": {}}


def observe_commit_for_event(
    churn_dir: str,
    last_reviewed_path: str,
    repo_root: str,
    paths,
    window: int,
    threshold: int,
) -> dict:
    """Thin wrapper: resolve the current HEAD for `repo_root` via git, then
    observe_commit(). Returns an empty report (no ledger write) when HEAD
    cannot be resolved (e.g. a brand-new repo with no commits yet). Never
    raises.
    """
    try:
        sha = _current_head(repo_root)
    except Exception:
        sha = ""
    if not sha:
        return {"newly_flagged": {}}
    return observe_commit(churn_dir, last_reviewed_path, repo_root, sha, paths, window, threshold)


# ---------------------------------------------------------------------------
# Status / operator-facing views.
# ---------------------------------------------------------------------------


def status_payload(
    churn_dir: str,
    last_reviewed_path: str,
    window: int,
    threshold: int,
    now: float | None = None,
) -> dict:
    if now is None:
        now = ab._now_epoch()
    records = read_live_commits(churn_dir, window, now)
    window_start = now - window
    repos = sorted({rec["repo_root"] for rec in records})
    flagged: dict[str, dict[str, int]] = {}
    for repo in repos:
        clean = clean_reviewed_shas(records, repo, last_reviewed_path)
        f = flagged_paths(records, repo, clean, threshold, window_start)
        if f:
            flagged[repo] = f
    return {
        "window_sec": window,
        "threshold": threshold,
        "tracked_commits": len(records),
        "flagged": flagged,
    }


# ---------------------------------------------------------------------------
# Thin CLI — operator debugging (status/doctor/reset).
# ---------------------------------------------------------------------------


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        if _lib.disabled():
            return 0
        sub = argv[0] if argv else "status"
        window = window_from_env()
        threshold = threshold_from_env()

        if sub == "status":
            payload = status_payload(_lib.CHURN_DIR, _lib.LAST_REVIEWED, window, threshold)
            print(json.dumps(payload, indent=2))
            return 0

        if sub == "reset":
            removed = reset_ledger(_lib.CHURN_DIR, window)
            print(f"OK reset (removed {removed} stale/corrupt commit record(s))")
            return 0

        if sub == "doctor":
            live = read_live_commits(_lib.CHURN_DIR, window)
            writable = os.path.isdir(_lib.CHURN_DIR) and os.access(_lib.CHURN_DIR, os.W_OK)
            lines = [
                "churn_tracker doctor",
                f"  churn_dir       : {_lib.CHURN_DIR} (writable={'yes' if writable else 'no'})",
                f"  window_sec      : {window} (CSA_CHURN_WINDOW_SEC)",
                f"  threshold       : {threshold} (CSA_CHURN_THRESHOLD)",
                f"  tracked_commits : {len(live)}",
                "  mode            : INFORMATIONAL ONLY — never blocks, no enforcing() hard path",
                "  fail_mode       : OPEN (advisory ledger; corrupt state self-heals)",
            ]
            print("\n".join(lines))
            return 0

        print("usage: churn_tracker.py {status|reset|doctor}", file=sys.stderr)
        return 0
    except Exception:
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
