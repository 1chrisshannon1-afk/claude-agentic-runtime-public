"""commit_authors — per-(repo, sha) commit-authorship ledger.

WHY THIS EXISTS: task_completion_gate.py's unreviewed-HEAD Stop gate used to
decide purely on (repo_root, HEAD) — with no concept of WHO committed — so it
fired once in EVERY live session sharing a repo the instant ANY one of them
advanced HEAD past the last reviewed commit. This ledger gives the gate that
missing concept: a small JSONL file mapping (repo, sha) -> the session_id that
authored it, written by posttooluse_bash.py right after a successful
`git commit`. While task_completion_gate.py was live (RETIRED 2026-08-20,
see that module) it consulted this ledger before it ever warned/blocked, so
only the COMMITTING session was ever prompted about its own commit
(mechanizing the house rule "never review a HEAD I didn't produce" —
memory: feedback_no_review_others_work). This ledger now serves only
posttooluse_bash.py's own authorship recording; it has no live consumer.

FAILURE MODE: this ledger is advisory and best-effort, matching the rest of
the hook system. A missed write (a crashed hook, a lost race, a HEAD that
predates this ledger, or an operator terminal commit that never runs through
Claude Code's hooks at all) degrades to "author unknown" for that HEAD, which
task_completion_gate.py (while it was live) treated as a quiet, NON-blocking
outcome — never a hard failure, and never a false attribution to the wrong
session. Every public
function here degrades to a safe no-op / None on any failure; nothing raises
out to a caller.

LEDGER SHAPE: one JSON object per line — {"ts": <epoch seconds>, "repo": <str>,
"sha": <str>, "session": <str>}. FIRST-WRITE-WINS: once a (repo, sha) pair has
a recorded line, later record() calls for the SAME pair are no-ops. This is
deliberate: a failed or retried commit attempt (or a re-fired hook) must never
steal attribution away from whichever session's commit actually produced that
sha. Two different repos never collide on a reused sha — the pair is always
compared together, never a bare sha.

CONCURRENCY: writes serialize on the SAME admission_lock primitive
record_review.py / file_claims.py / agent_budget.py already prove out, scoped
to the ledger's own parent directory (this ledger lives in
~/.claude/.review_state/ alongside last_reviewed, so it shares that
directory's admission.lock file with record_review.py's ledger — no separate
lock file needed). Pruning (bounding the ledger's growth) ALSO runs under that
same lock, and only there.

Unlike record_review.py's ledger mutators — which fail CLOSED (skip the write
entirely) when the lock is unavailable, because an unprotected read-modify-
write rewrite there risks silently discarding a concurrent session's line —
this ledger fails OPEN on a lock miss: record() still appends but SKIPS the
prune step. Losing a just-recorded commit's own attribution would be a worse
failure than a temporarily oversized file, so append-only was treated as
low-risk enough to do unprotected; a REWRITE (prune) is not, so it never runs
outside the lock.

That "append-only is low-risk even unprotected" framing understated a real
race, though: an unlocked appender (call it A) writing via plain O_APPEND can
still lose its line to a DIFFERENT, LOCK-HOLDING appender's (B's) concurrent
_prune() -> os.replace() swap. If B's replace lands between A's open() and
write(), A's line is written to the OLD, now-unlinked inode — invisible to
anyone reading via the path from that point on, since the path now resolves
to B's newly replaced file. That is a genuine lost-attribution bug: the
commit A was recording for silently has no author on record, forever (never a
crash, never an exception — just a quietly missing line), which (while
task_completion_gate.py was live) meant its Stop gate never attributed that
HEAD to anyone and a review gap went unflagged. record()'s unlocked path
closes this specific
window itself: after its append, it re-reads the ledger BY PATH and confirms
its own line actually landed (via author_of()); if it did not — i.e. it was
lost to exactly that race — it retries the append ONCE (best-effort, no
unbounded retry loop: a prune collision is rare and bounded in duration, so
one retry is enough in practice). This adds no blocking behavior — the retry
is just one more unlocked, non-blocking append attempt, same as the first.

This module depends on nothing beyond the stdlib plus this hook suite's own
agent_budget.admission_lock primitive.
"""

from __future__ import annotations

import json
import os
import sys
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import agent_budget as ab  # noqa: E402  (reuse the proven admission_lock primitive)

# Rewrite (prune) the ledger once it exceeds this many RAW lines (garbage lines
# count too — this is a cheap line-count check, not a parsed-record count).
PRUNE_THRESHOLD = 2000
PRUNE_KEEP_DAYS = 14  # keep every well-formed record newer than this
PRUNE_KEEP_MAX = 2000  # if still over after the age cutoff, keep only the newest N


# ---------------------------------------------------------------------------
# PURE helpers — parsing/serialization is isolated from filesystem I/O so
# tests can cover the ledger's line grammar without touching disk.
# ---------------------------------------------------------------------------


def lock_timeout_from_env(environ: dict | None = None) -> float:
    """Resolve CSA_LOCK_TIMEOUT_SEC — the same shared admission-lock bound
    every other ledger in this suite uses (default 2.0)."""
    env = os.environ if environ is None else environ
    return ab.lock_timeout_from_env(env)


def _parse_line(raw_line: str) -> dict | None:
    """Parse one ledger line into a well-formed {"ts","repo","sha","session"}
    record, or None for a blank/garbage/malformed line. Never raises.

    A well-formed record requires all four fields: repo/sha/session must be
    non-empty strings, ts must be numeric (or a numeric string). Anything
    else — invalid JSON, a non-dict payload, a missing/blank/wrong-typed
    field — is an unparseable line to be SKIPPED, never one that crashes a
    caller.
    """
    line = raw_line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    repo = data.get("repo")
    sha = data.get("sha")
    session = data.get("session")
    if not isinstance(repo, str) or not repo:
        return None
    if not isinstance(sha, str) or not sha:
        return None
    if not isinstance(session, str) or not session:
        return None
    try:
        ts = float(data.get("ts"))
    except Exception:
        return None
    return {"ts": ts, "repo": repo, "sha": sha, "session": session}


def _serialize(repo: str, sha: str, session: str, ts: float) -> str:
    return json.dumps({"ts": ts, "repo": repo, "sha": sha, "session": session})


def parse_ledger(text: str) -> list[dict]:
    """Parse a whole ledger's text into its well-formed records, in file
    order, skipping any unparseable line. Pure; never raises.

    Split out as its own public function specifically so tests can cover the
    parsing/pruning grammar without touching the filesystem at all.
    """
    try:
        return [rec for rec in (_parse_line(ln) for ln in text.splitlines()) if rec is not None]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Ledger I/O — the only impure layer.
# ---------------------------------------------------------------------------


def _read_records(ledger_path: str) -> list[dict]:
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return []
    return parse_ledger(text)


def author_of(ledger_path: str, repo: str, sha: str) -> str | None:
    """The session_id that recorded (repo, sha) FIRST, or None.

    None means: the ledger is missing/unreadable, or holds no record for this
    exact (repo, sha) pair — "author unknown" to every caller, always safe to
    treat as non-attributable. When several lines somehow match a pair (should
    not happen given first-write-wins, but a hand-edited or historically
    duplicated ledger is possible) the FIRST matching line wins, mirroring the
    write-time guarantee. Never raises.
    """
    if not ledger_path or not repo or not sha:
        return None
    try:
        for rec in _read_records(ledger_path):
            if rec["repo"] == repo and rec["sha"] == sha:
                return rec["session"]
    except Exception:
        return None
    return None


def _append_line(ledger_path: str, line: str) -> bool:
    """Create the ledger's parent dir and append `line` + newline.

    Returns True on success, False on any failure. Never raises.
    """
    try:
        parent = os.path.dirname(ledger_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(ledger_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True
    except Exception:
        return False


def _prune(ledger_path: str, now: float) -> None:
    """Rewrite the ledger (temp file in the SAME dir + os.replace) to bound
    its growth. MUST be called only from inside the caller's admission_lock
    (see record()) — this is a read-modify-write, and an unlocked instance of
    it racing a concurrent record()'s unlocked append is exactly the class of
    bug record_review.py's REGRESSION-5 fix (its _update_entry docstring)
    exists to avoid.

    Keeps every well-formed record newer than PRUNE_KEEP_DAYS; if that alone
    still exceeds PRUNE_KEEP_MAX, keeps only the newest PRUNE_KEEP_MAX of
    those (sorted by their own `ts`, so this is correct regardless of the
    ledger's on-disk line order). A garbage/unparseable line is dropped by the
    rewrite, same as any record older than the cutoff.

    No-op (returns without writing) when the file is at/under PRUNE_THRESHOLD
    lines, unreadable, or any step fails — pruning is a housekeeping nicety,
    never allowed to risk the data it exists to protect. Never raises.
    """
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return
    if len(lines) <= PRUNE_THRESHOLD:
        return
    try:
        records = parse_ledger("".join(lines))
        cutoff = now - PRUNE_KEEP_DAYS * 86400
        kept = [rec for rec in records if rec["ts"] >= cutoff]
        kept.sort(key=lambda r: r["ts"])
        if len(kept) > PRUNE_KEEP_MAX:
            kept = kept[-PRUNE_KEEP_MAX:]
        tmp = f"{ledger_path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in kept:
                fh.write(_serialize(rec["repo"], rec["sha"], rec["session"], rec["ts"]) + "\n")
        os.replace(tmp, ledger_path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def record(ledger_path: str, repo: str, sha: str, session: str, now: float | None = None) -> bool:
    """Append {"ts","repo","sha","session"} for (repo, sha) — FIRST-WRITE-WINS.

    Returns True iff THIS call's line was the one written (no prior record
    for this exact (repo, sha) pair existed yet); False when a record already
    existed (this call is intentionally a no-op — see module docstring) or on
    any failure (missing args, an unwritable ledger, ...). Never raises.

    Serializes on agent_budget.admission_lock, scoped to the ledger's own
    parent directory (see module docstring). When that lock cannot be
    acquired within its bounded timeout, this function still appends — it
    fails OPEN, never skipping the record entirely — but skips the prune
    step, which only ever runs from inside the lock.

    The unlocked (fail-open) path additionally guards against a real race: a
    concurrent LOCKED caller's _prune() can os.replace() a freshly pruned
    file over this same path between our own open() and write(), silently
    losing our just-appended line to the old, now-unlinked inode. After an
    unlocked append, this re-reads the ledger BY PATH to confirm the line
    actually landed and retries the append ONCE if it did not — see the
    module docstring.
    """
    if not ledger_path or not repo or not sha or not session:
        return False
    try:
        ts = time.time() if now is None else now
        line = _serialize(repo, sha, session, ts)
        lock_dir = os.path.dirname(ledger_path) or "."
        with ab.admission_lock(lock_dir, timeout_s=lock_timeout_from_env()) as locked:
            if author_of(ledger_path, repo, sha) is not None:
                return False  # first-write-wins: someone already recorded this sha
            wrote = _append_line(ledger_path, line)
            if not locked:
                # Fail-open path: nothing serializes us against a concurrent
                # LOCKED holder's _prune()/os.replace(). Verify our line
                # actually reached the (possibly just-replaced) path; retry
                # ONCE if a concurrent prune raced it away — see module
                # docstring.
                if wrote and author_of(ledger_path, repo, sha) != session:
                    wrote = _append_line(ledger_path, line)
                return wrote
            if wrote:
                _prune(ledger_path, ts)
            return wrote
    except Exception:
        return False
