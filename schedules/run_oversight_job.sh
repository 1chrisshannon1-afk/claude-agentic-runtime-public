#!/bin/bash
# run_oversight_job.sh — shared launchd entry point for every com.oversight.csa.*
# job (GH #4825).
#
# PROBLEM this closes: each job's own prompt (_preamble.txt step 5) trusts the
# LLM session itself to write the END heartbeat as its last action. That is
# fine when the session exits cleanly, but two real incidents proved it is not
# a complete contract:
#   - #4825 (productqa, 2026-09-02): the session did all its real work, wrote
#     a *narrative* claiming "wrote the heartbeat, exit 0", and then the CLI
#     process itself was cut off by the account's session-limit window
#     ("You've hit your session limit ...") — most likely between narrating
#     the write and the Bash tool call actually executing it. The on-disk
#     heartbeat never left the START stub. Nothing outside the dead process
#     could tell the difference between "still legitimately running" and
#     "died claiming success" until heartbeat_audit.py's cadence+grace window
#     (up to 7 days for a weekly job) finally elapsed.
#   - #4791 (steward, 2026-09-01): a background network call ran past the
#     harness's 600s wait ceiling and was hard-killed mid-work, same dangling
#     END heartbeat shape.
#
# FIX: this wrapper — not the LLM inside the session — is the thing that
# guarantees a truthful heartbeat exists the moment the process exits, for
# ANY reason (clean finish, session-limit death, the alarm(2) hang-kill
# below, a crash). It never trusts the CLI's own stdout narrative; it checks
# the heartbeat FILE ON DISK against a timestamp recorded before the CLI was
# even started.
#
# Usage (from a plist's ProgramArguments):
#   /bin/bash "$HOME"/.claude/schedules/run_oversight_job.sh \
#     <job-label> <prompt-file> <cadence-text> [alarm-seconds]
#
# alarm-seconds defaults to 7200 (2h) to match the prior per-job inline
# one-liners; the `loop` job's own alarm was 10800 (3h) and MUST be passed
# explicitly to preserve that — do not silently normalize it to 7200.
#
# Exit code: 0 in the ordinary case — a launchd job's own exit code is not
# what downstream tooling reads (heartbeat_audit.py reads the heartbeat
# file, not `launchctl list`'s LastExitStatus). The true set of non-zero
# wrapper exits, all before the main CLI is invoked, all wheel-only:
#   - 75 (EX_TEMPFAIL, H3, CSA hardening plan): the concurrency guard below
#     refused or failed a wheel-slug lock acquisition. Load-bearing: launchd's
#     own crash/retry accounting is a live, if secondary, consumer of a
#     wrapper that never got far enough to run anything.
#   - 70: the quota pre-flight matched a session/weekly limit OR a server-side
#     throttle and skipped the main run this slot (heartbeat status
#     "skipped-quota" for the former, "skipped-throttle" for the latter --
#     #5922: these are two distinct outcomes with independent streak
#     counters, never one status covering both).
# Every OTHER exit path (CLI ran to completion, hang-kill, empty prompt file,
# kill switch, launch-context refusal, second-slot skip, etc.) exits 0 — the
# heartbeat file remains the single source of truth for THOSE outcomes.
#
# THE WHEEL LAUNCHER (GH #4767; wheel jobs only, i.e. WHEEL_SLUG set). A
# headless `claude -p` session cannot read ~/.claude without a grant, cannot
# read its own env in Agency, and has nearly every ordinary write under a
# `.claude` directory refused as a "sensitive file". The exceptions (the CLI's
# own auto-memory dir, which takes Write-tool and redirect writes with no
# grant; a heredoc the analyzer bails on under CSA's bare `Bash` allow;
# python3; tee) are listed in knowledge/oversight_install.md §1.
# So this wrapper owns everything decidable before launch:
#   - the kill switches (DISABLED, DISABLED.wheel.<slug>), checked with bash
#     `[ -e ]` before the lock, the pre-flight or any claude call; a hit writes
#     heartbeat status "skipped-disabled" (hard_stop "1" or "2"), exit 0;
#   - hooks/wheel_launch_context.py (python3: TCC-safe under launchd) runs
#     HARD STOPs 3/4/4b plus the settings and python3-precondition checks.
#     A failure writes heartbeat status "failed", `exit` 79 and a typed
#     `hard_stop` key; the wrapper exits 0 without launching claude. On
#     success it writes the WRAPPER CONTEXT + preamble prompt prefix and the
#     wheel's exact CLI flag tail (one scratch --add-dir, zero MCP servers,
#     8 built-in tools, a triage-half allow set, `//` Edit/Write denies over
#     ~/.claude, the repo and every other additionalDirectory, best-effort
#     Bash family denies). The ~/.claude deny is whole-tree on purpose: it is
#     the only thing closing the auto-memory dir, so never narrow it;
#   - the START heartbeat; the session writes END only through
#     hooks/wheel_sink.py, which stamps finished_at and `written_via`.
# Non-wheel jobs keep their argv, prompt and env exactly as before.
#
# `_wrapper_say` CONTRACT (GH #4767 round-2 B2): every wrapper-owned early
# exit prints ONE `WRAPPER: <reason>` line to stdout (the job's .out.log,
# heartbeat_audit.py's finish-time proxy) AND to stderr (.err.log, which
# daily_sweep.txt step A reads). It is never called after the main claude run.

set -u  # deliberately NOT -e: every step below must run even if a prior one
        # fails, so the fail-fast heartbeat write is never skipped.

# --- Per-night history appender path (WS14-S1 slice, item 1, paragraph 1b) ---
# Resolved from this script's OWN location (never a hardcoded ~/.claude path, which would miss
# the module under an isolated test $HOME), computed here in plain bash -- python3-based
# resolution (RUNTIME_DIR, below) runs too late for the earliest possible abort, before the EXIT
# trap is registered. `pwd -P` resolves the directory part only (never the wrapper's own symlink,
# matching os.path.abspath's own behavior); `${VAR:-}`-safe throughout under `set -u`.
WHEEL_HISTORY_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ]; then
    WHEEL_HISTORY_DIR=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../hooks" 2>/dev/null && pwd -P) || WHEEL_HISTORY_DIR=""
fi
if [ -n "$WHEEL_HISTORY_DIR" ]; then
    WHEEL_HISTORY_PY="${WHEEL_HISTORY_DIR}/wheel_history.py"
else
    WHEEL_HISTORY_PY=""
fi
# --- end per-night history appender path --------------------------------

# --- Unified EXIT trap (fix round, item 5) --------------------------------
# ONE trap function, registered ONCE, near the top of the script -- every
# later piece of state this script accumulates that needs cleanup-on-exit
# (the wheel lock directory, the quota pre-flight's own temp file, and --
# WS14-S1 slice, item 1, 1b -- the per-night history append) reads from a
# shell variable this function checks, rather than each site installing its
# own separate `trap ... EXIT` command. `trap` REPLACES any prior EXIT trap
# outright (it does not stack multiple registrations), so a second, later
# `trap ... EXIT` call anywhere in this script would silently delete an
# earlier one's cleanup -- exactly the bug this design avoids: the
# concurrency guard's lock-release logic, the pre-flight's temp-file
# cleanup, and the history append all need to run on ANY exit path,
# including a mid-script kill, and none may clobber another.
#
# Every variable this function reads defaults to empty/unset-safe under
# `set -u` (guarded with `${VAR:-}` throughout) so calling it before a given
# piece of state exists yet (e.g. exiting before the lock was ever
# attempted) is always a safe no-op for that piece.
_wrapper_exit_cleanup() {
    if [ -n "${PREFLIGHT_OUT_FILE:-}" ]; then
        rm -f "$PREFLIGHT_OUT_FILE" 2>/dev/null || true
    fi
    # The wheel launcher's private context dir and the run's scratch dir (GH
    # #4767). The basename patterns are the only thing ever removed here, so a
    # mis-set variable can never make this trap delete anything else.
    case "${CTX_DIR:-}" in
        */oversight_wheel_ctx.??????) rm -rf "$CTX_DIR" 2>/dev/null || true ;;
    esac
    case "${RUN_SCRATCH:-}" in
        */oversight_wheel.??????) rm -rf "$RUN_SCRATCH" 2>/dev/null || true ;;
    esac
    if [ -n "${LOCKDIR:-}" ] && [ "${WHEEL_LOCK_HELD:-0}" = "1" ]; then
        # WS14-S1 slice, item 1 (1b): the lock_force_reclaimed stamp now runs
        # BEFORE `rm -rf "$LOCKDIR"` (moved ahead of it, per the slice text).
        if [ "${LOCK_FORCE_RECLAIMED:-0}" = "1" ]; then
            python3 - "$HEARTBEAT_FILE" <<'PYEOF2' || true
import json, sys
path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["lock_force_reclaimed"] = True
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
except Exception:
    pass
PYEOF2
        fi
    fi
    # --- Per-night history append (WS14-S1 slice, item 1, paragraph 1b) ---
    # Runs UNCONDITIONALLY here, OUTSIDE the lock-held `if` above (so every
    # exit path gets a line, not only ones that ever held the lock) and
    # BEFORE the lock is released (the `rm -rf "$LOCKDIR"` release, below,
    # runs strictly AFTER this call returns) -- so no later run for this slug
    # can observe the lock as free and start writing its own heartbeat before
    # this append has already read the CURRENT run's file. This also means
    # the kill-switch, lock-refused, and wheel-slug-missing early exits get
    # their line: they all `exit` through this same unified trap, and none of
    # them ever acquired the lock in the first place (WHEEL_LOCK_HELD stays
    # unset/0 for them), so this call reaches them unconditionally too.
    #
    # Guarded on both HEARTBEAT_FILE and JOB_LABEL, and on WHEEL_HISTORY_PY
    # itself having resolved to a real, existing file -- the earliest
    # possible abort (the `${1:?}` guard for a missing <job-label> argument)
    # fires before JOB_LABEL is ever assigned, so this condition is false
    # there and nothing is appended (and no error is raised), exactly as the
    # slice requires ("the early ${1:?} abort writes nothing and must raise
    # no error"). `|| true` on the whole call: an append failure must never
    # change this script's own exit code, which is why WHEEL_HISTORY_PY's own
    # design (see wheel_history.py's module docstring) never raises either --
    # this is the second, independent layer of that same guarantee.
    if [ -n "${HEARTBEAT_FILE:-}" ] && [ -n "${JOB_LABEL:-}" ] && [ -n "${WHEEL_HISTORY_PY:-}" ] && [ -f "$WHEEL_HISTORY_PY" ]; then
        # Finding 9 (review round): bounded with the wrapper's own perl-alarm idiom (already used
        # for the quota pre-flight and the main CLI run, above/below) so a hung or runaway appender
        # can never block this trap indefinitely -- 10s (N2, WS14-S1 1c review nit: originally 20s,
        # which equalled launchd's own default SIGTERM-to-SIGKILL stop timeout; the dead-pid reclaim
        # covers the wrapper meanwhile, so 10s is plenty for a single JSON line append) --
        # and `|| true` still applies to the whole bounded call: a timeout (perl's own SIGALRM exit)
        # is just another append failure, never a wrapper failure.
        perl -e 'alarm shift; exec @ARGV' 10 python3 "$WHEEL_HISTORY_PY" append --heartbeat "$HEARTBEAT_FILE" --job "$JOB_LABEL" \
            --start-epoch "${WRAPPER_START_EPOCH:-}" --start-iso "${WRAPPER_START_ISO:-}" || true
    fi
    # --- end per-night history append --------------------------------------
    if [ -n "${LOCKDIR:-}" ] && [ "${WHEEL_LOCK_HELD:-0}" = "1" ]; then
        rm -rf "$LOCKDIR" 2>/dev/null || true
    fi
}
trap _wrapper_exit_cleanup EXIT
# --- end unified EXIT trap -------------------------------------------------

# Every wrapper-owned early exit states its reason on BOTH streams (GH #4767, round-2 B2).
# stdout is the job's .out.log, whose mtime heartbeat_audit.py uses as the finish proxy
# (_log_times); without this line a skip/refusal heartbeat's finished_at diverges from a stale
# out.log and the audit reports "timestamp-divergence ... possible fabricated timestamp".
# stderr is the .err.log that daily_sweep.txt step A reads to explain a non-zero exit.
# Never call this after the main claude run: a late stderr write would move .err.log's mtime,
# which is the audit's START proxy.
_wrapper_say() {
    printf 'WRAPPER: %s\n' "$1" 2>/dev/null || true
    printf 'WRAPPER: %s\n' "$1" >&2 2>/dev/null || true
}

# The legacy early exits (lock refusals, empty prompt, second-slot skip, quota
# skip) already write a `WRAPPER: ...` heartbeat summary; this states exactly
# that summary (minus its `WRAPPER: ` prefix) on both streams, falling back to
# the given text if the heartbeat cannot be read back.
_wrapper_say_heartbeat() {
    local _said
    _said=$(python3 - "$HEARTBEAT_FILE" <<'PYEOF' 2>/dev/null
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["summary"]
print(s[len("WRAPPER: "):] if s.startswith("WRAPPER: ") else s)
PYEOF
) || _said=""
    [ -n "$_said" ] || _said="$1"
    _wrapper_say "$_said"
}

JOB_LABEL="${1:?run_oversight_job.sh: missing <job-label>}"
PROMPT_FILE="${2:?run_oversight_job.sh: missing <prompt-file>}"
CADENCE_TEXT="${3:-unknown}"
ALARM_SECONDS="${4:-7200}"

HEARTBEAT_DIR="${HOME}/.claude/schedules/heartbeats"
HEARTBEAT_FILE="${HEARTBEAT_DIR}/${JOB_LABEL}.json"

# The claude CLI: PATH first. launchd hands a job a minimal PATH, so when the lookup comes up
# empty fall back to the host OS's usual install locations (Homebrew's on macOS, then the
# native installer's ~/.local/bin, then /usr/local/bin); if none exists return the historical macOS
# path on macOS and a bare `claude` elsewhere, so the launch failure names a concrete command
# and a non-macOS host never carries a macOS-only path. The assignment below stays ONE
# column-0 `CLAUDE_BIN=` line: the sandbox tests rewrite it by that name.
_resolve_claude_bin() {
    local _c _os
    _c="$(command -v claude 2>/dev/null)" && [ -n "$_c" ] && { printf '%s\n' "$_c"; return 0; }
    _os="$(uname -s 2>/dev/null)"
    for _c in /opt/homebrew/bin/claude "${HOME}/.local/bin/claude" /usr/local/bin/claude; do
        [ "$_c" = "/opt/homebrew/bin/claude" ] && [ "$_os" != "Darwin" ] && continue
        [ -x "$_c" ] && { printf '%s\n' "$_c"; return 0; }
    done
    if [ "$_os" = "Darwin" ]; then
        printf '%s\n' /opt/homebrew/bin/claude
    else
        printf '%s\n' claude
    fi
}
CLAUDE_BIN="$(_resolve_claude_bin)"

# IS_SCHEDULED_WHEEL_JOB (fix round, THE ISSUE WHEEL plan, BLOCKER 1 + 2):
# true ONLY for a genuinely SCHEDULED wheel job label (com.oversight.wheel.*)
# — never for a `manual-wheel-<slug>` on-demand /wheel invocation, even
# though both export WHEEL_SLUG and both hit the concurrency guard above.
# This is the guard the second-slot skip (BLOCKER 1's second half) uses:
# without it, once a scheduled run stamps status:"ok", an operator's SECOND
# manual `/wheel csa` later the same day would silently no-op, since a
# manual run's own label never has a retry slot to protect in the first
# place -- there is nothing to "skip a retry" FOR on a one-shot manual
# invocation.
case "$JOB_LABEL" in
    com.oversight.wheel.*) IS_SCHEDULED_WHEEL_JOB=1 ;;
    *) IS_SCHEDULED_WHEEL_JOB=0 ;;
esac

mkdir -p "$HEARTBEAT_DIR"

WRAPPER_START_EPOCH=$(python3 -c 'import time; print(time.time())')
WRAPPER_START_ISO=$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')

# --- Wheel-label guard, wrapper-enforced (BLOCKER B1, trust-architect fix round) -------------
# A job label that LOOKS like a wheel job (either plist naming convention) or that is launched
# with the wheel's own prompt file, but with WHEEL_SLUG unset or empty, previously took the
# non-wheel branch below: no wrapper kill switch, no lock, no launch-context flags at all, running
# claude with the wrapper's full, unrestricted surface while its prompt (issue_wheel.txt) still
# claims the wheel's restricted grants. Refuse before the lock, the pre-flight or any claude call.
_prompt_basename=$(basename "$PROMPT_FILE" 2>/dev/null || true)
case "$JOB_LABEL" in
    com.oversight.wheel.*|manual-wheel-*) _looks_like_wheel_job=1 ;;
    *) _looks_like_wheel_job=0 ;;
esac
if [ "$_prompt_basename" = "issue_wheel.txt" ]; then
    _looks_like_wheel_job=1
fi
if [ "$_looks_like_wheel_job" = "1" ] && [ -z "${WHEEL_SLUG:-}" ]; then
    python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, os, sys, datetime
hb_path, job, started, cadence = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data = {"job": job, "started_at": started, "finished_at": now, "exit": 79, "cadence": cadence,
        "status": "failed", "hard_stop": "wheel-slug-missing",
        "summary": "WRAPPER: refused before launch — wheel-slug-missing: job label or prompt file "
                   "looks like a wheel job but WHEEL_SLUG is unset or empty; claude was not "
                   "launched (fail closed, GH #4767)."}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
    _wrapper_say "refused before launch — wheel-slug-missing: job label or prompt file looks like a wheel job but WHEEL_SLUG is unset or empty; claude was not launched (fail closed, GH #4767)."
    exit 0
fi
# --- end wheel-label guard ---------------------------------------------------------------

# --- Kill switch, wrapper-enforced (GH #4767; wheel jobs only) ---------------
# The operator's absolute stop: checked FIRST, before the lock dir, the prompt
# load, the quota pre-flight API call or any claude call. Until this block the
# wheel's kill switch was enforced only by the LLM session reading files it
# often could not read. Plain bash `[ -e ]` is enough: this wrapper's bash already creates
# ~/.claude/schedules/heartbeats above, so ~/.claude is reachable under launchd (only ~/Desktop is not).
# The global switch keeps preamble step 1's `_disabled_window.jsonl` line
# (daily_sweep.txt consumes it); the per-job switch writes no window line
# (today's semantics). Non-wheel jobs still rely on their session (F7, #5913).
if [ -n "${WHEEL_SLUG:-}" ]; then
    KILL_MARKER=""
    # N5 (trust-architect, fix round): `[ -e X ] || [ -L X ]` instead of bare `[ -e X ]` -- a
    # DANGLING symlink at the marker's path (pointing at a target that no longer exists) makes
    # `[ -e ]` false, silently treating "the operator's kill-switch symlink is broken" the same as
    # "no kill switch present" and letting the run through. `[ -L ]` catches the symlink itself
    # regardless of what it points to (or fails to).
    if [ -e "${HOME}/.claude/schedules/DISABLED" ] || [ -L "${HOME}/.claude/schedules/DISABLED" ]; then
        KILL_MARKER="global"
    elif [ -e "${HOME}/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG}" ] || [ -L "${HOME}/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG}" ]; then
        KILL_MARKER="per-job"
    fi
    if [ -n "$KILL_MARKER" ]; then
        python3 - "$HEARTBEAT_FILE" "$HEARTBEAT_DIR" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$KILL_MARKER" "$WHEEL_SLUG" <<'PYEOF' || true
import datetime, json, os, sys
hb_path, hb_dir, job, started, cadence, marker, slug = sys.argv[1:8]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
if marker == "global":
    with open(os.path.join(hb_dir, "_disabled_window.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"job": job, "skipped_at": now}) + "\n")
    hard_stop, what = "1", "kill switch ~/.claude/schedules/DISABLED is present"
else:
    hard_stop, what = "2", f"per-job disabled (~/.claude/schedules/DISABLED.wheel.{slug} is present)"
data = {"job": job, "started_at": started, "finished_at": now, "exit": 0, "cadence": cadence,
        "status": "skipped-disabled", "hard_stop": hard_stop,
        "summary": f"WRAPPER: skipped — {what}; claude was not launched (wrapper-enforced, GH #4767)."}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
        if [ "$KILL_MARKER" = "global" ]; then
            _wrapper_say "skipped-disabled (global) — ~/.claude/schedules/DISABLED is present; claude was not launched (wrapper-enforced kill switch, GH #4767)."
        else
            _wrapper_say "skipped-disabled (per-job) — ~/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG} is present; claude was not launched (wrapper-enforced kill switch, GH #4767)."
        fi
        exit 0
    fi
fi
# --- end kill switch --------------------------------------------------------

# --- Concurrency guard (H3, CSA hardening plan): refuse-on-collision for the
# wheel's own repo-slug lock, a no-op for every other job sharing this
# wrapper. ---------------------------------------------------------------
#
# This wrapper is shared by all six (soon eight) live com.oversight.csa.*/
# com.oversight.wheel.* jobs, not just the wheel. Only the wheel's own
# plists (and /wheel's own on-demand invocation) are expected to export
# WHEEL_SLUG — every other job leaves it unset, and this guard is a
# complete no-op (no lockfile, no acquisition, no trap) for them, checked
# with the set -u-safe ${WHEEL_SLUG:-} form so this script never aborts a
# non-wheel job over an unset var.
#
# Scoped by repo SLUG, not job label: manual-wheel-<slug> (via /wheel) and
# com.oversight.wheel.<slug> (the nightly job) write the same repo, and a
# label-only lock would not stop an on-demand run racing a nightly one.
# launchd already prevents same-label concurrency for a single label, so
# that case needs no guard here.
LOCK_DIR="${HOME}/.claude/schedules/locks"
if [ -n "${WHEEL_SLUG:-}" ]; then
    if ! mkdir -p "$LOCK_DIR" 2>/dev/null; then
        # BLOCKER 3: an unchecked `mkdir -p` here would let every step below
        # continue against a lock dir that was never actually created —
        # unguarded and unlocked, indistinguishable from success. Refuse
        # instead: fail-fast heartbeat naming the cause, exit 75.
        python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$LOCK_DIR" <<'PYEOF' || true
import json, sys, datetime
path, job, started, cadence, lock_dir = sys.argv[1:6]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 75,
        "cadence": cadence,
        "status": "failed",
        "summary": (
            f"WRAPPER: refused — could not create lock directory {lock_dir!r} "
            "(mkdir -p failed, e.g. permission error or read-only filesystem) "
            "— continuing without a lock is unsafe, refusing instead (see H3)."
        ),
    }, fh)
PYEOF
        _wrapper_say_heartbeat "refused — could not create the lock directory (see H3)."
        exit 75
    fi
    # BLOCKER (round-2 review): the lock is now a DIRECTORY, not a file
    # (`${WHEEL_SLUG}.lock/`, containing an `owner.json` payload) — os.mkdir
    # is the sole atomic create-or-fail primitive this design depends on;
    # see try_acquire()'s own docstring below for why a file-based
    # write-then-link scheme (this guard's round-1 shape) could not be made
    # safe for the STALE-RECLAIM branch no matter how the unlink/retry was
    # sequenced.
    LOCKDIR="${LOCK_DIR}/${WHEEL_SLUG}.lock"

    # --- Atomic acquisition (round-2 fix: directory-based lock + exclusive
    # reclaim marker, replacing the round-1 file-based write-then-link
    # design). ------------------------------------------------------------
    #
    # ROUND-1 HISTORY, kept for context (the round-1 fix itself, further
    # up this comment's own git history, replaced a check-then-write TOCTOU
    # in the "no lock exists yet" case with an atomic write-then-link
    # test-and-set — that part was correct and stays conceptually the same
    # here, just re-expressed as os.mkdir). What round-1 did NOT close: its
    # STALE-RECLAIM branch was `try_acquire() raises FileExistsError ->
    # read_existing_lock() -> is_stale() -> os.unlink(lockfile)
    # UNCONDITIONALLY -> retry`. Staleness was decided against content read
    # BEFORE the unlink; the unlink then deleted whatever was AT THE NAME
    # NOW, which could be a different contender's freshly-acquired, valid,
    # live lock (acquired between this process's staleness check and its
    # own unlink) — an unlink-then-recreate pattern can never close this
    # class regardless of how the retry is sequenced, because the decision
    # (stale) and the destructive action (delete) are always separated by
    # at least one point where another process can act. Falsified by direct
    # execution during round-2's own fix work: 0/150 clean trials with 3
    # real, distinct-PID contenders (separate `fork`ed processes, not the
    # same $$ reused for every contender — a same-PID test is a false
    # negative here, since `is_stale()`'s own liveness check would then
    # always see "self", never a genuine peer).
    #
    # ROUND-2 FIX: os.mkdir(lockdir) is the ONLY primitive this design
    # trusts for exclusivity (atomic even across NFS, per POSIX). The
    # stale-reclaim branch no longer performs an unconditional
    # unlink-then-recreate at all. Instead:
    #   1. A contender that finds an existing, stale lock must first win a
    #      SEPARATE, exclusive "reclaiming" marker (`${LOCKDIR}.reclaiming`,
    #      itself created via the same os.mkdir test-and-set) before it may
    #      touch `lockdir` in any way. A contender that loses this mkdir
    #      race NEVER retries its own delete/rename against `lockdir` — it
    #      refuses (reports "someone else is handling reclaim"), exactly as
    #      the fix's own design brief specifies.
    #   2. Only the marker-winner re-verifies staleness (a peer's lock may
    #      have been cleanly released, or another contender may — in a
    #      structurally impossible-but-checked-anyway case — have already
    #      reclaimed it) and then performs os.rename(lockdir, quarantine) —
    #      atomic, and by construction the SOLE process that can ever be
    #      attempting THIS RENAME, since every other RECLAIMER is blocked
    #      behind the marker. This does NOT extend to the recreate that
    #      follows: a FRESH acquirer (never having contended for the marker
    #      at all, since it never needed to reclaim anything) can win the
    #      recreate's own try_acquire() the instant the name is free — a
    #      real, reproduced race, guarded by treating that FileExistsError
    #      as ordinary contention, not an error (see the recreate site).
    #   3. The marker itself carries its own owner pid, so a marker-holder
    #      that dies (SIGKILL) mid-reclaim doesn't leak a PERMANENT block on
    #      all future reclaims for this slug — a later contender that loses
    #      the marker's own mkdir race checks whether the marker's recorded
    #      owner is dead and, if so, reclaims the MARKER itself the same
    #      test-and-set way (a second, smaller instance of the identical
    #      pattern; its lifetime is bounded by "however long one reclaim
    #      sequence takes", never by the lock's own alarm_seconds).
    # Verified by direct execution (this round's own testing, 3 distinct-PID
    # contenders unless noted): 150/150 clean trials at N=3, 100/100 clean
    # at N=8, 30/30 clean at N=12 — exactly one "acquired" every time,
    # against a genuinely stale lock racing from cold.
    #
    # Prints exactly one of the following on stdout and exits 0 in every
    # case that isn't a real I/O failure (bash below branches on the
    # printed word, not a nonzero exit, since "another process holds the
    # lock" is an ordinary, expected outcome, not a script error):
    #   acquired            — this process now holds the lock; lockdir
    #                         written with this run's pid/timestamps.
    #   held:<pid>          — a live, non-stale lock is held by <pid>, OR
    #                         another contender is actively reclaiming this
    #                         slug's lock right now; this process acquired
    #                         nothing. <pid> is "unknown" only in the
    #                         microseconds-wide window where a peer's
    #                         owner.json write hasn't landed yet.
    #   force-reclaimed     — CSA_WHEEL_FORCE_UNLOCK=1 forced acquisition
    #                         regardless of PID-liveness or TTL.
    # A genuine I/O failure (permission error, read-only lock dir, disk
    # full, etc.) prints nothing meaningful and exits non-zero; bash checks
    # the exit status explicitly and refuses rather than silently
    # proceeding unlocked.
    ACQUIRE_OUT=$(python3 - "$LOCKDIR" "$$" "$WRAPPER_START_ISO" "$WRAPPER_START_EPOCH" "$ALARM_SECONDS" "${CSA_WHEEL_FORCE_UNLOCK:-}" <<'PYEOF'
import json, os, sys, time

lockdir_arg, pid_arg, started_iso, started_epoch_s, alarm_seconds_s, force_unlock_arg = sys.argv[1:7]

# MEDIUM (round-2 review): validate/convert every arg ONCE, up front, with a
# clear error path — round-1 let `int(pid)` inside write_lock_payload()
# raise an unhandled ValueError on a malformed pid argument deep inside the
# acquire attempt, which the bash caller's exception handling doesn't
# specifically catch (it fails safe via the exit-status check either way,
# but misreports the real cause as a generic "lock-write-error" rather than
# naming the actual malformed input).
try:
    lockdir = lockdir_arg
    pid = int(pid_arg)
    started_epoch = float(started_epoch_s)
    alarm_seconds = float(alarm_seconds_s)
    force_unlock = force_unlock_arg == "1"
except (TypeError, ValueError) as exc:
    print(f"lock-arg-error: {exc}", file=sys.stderr)
    sys.exit(1)

OWNER_FILE = "owner.json"


def _lock_payload_bytes(owner_pid):
    return json.dumps({
        "pid": owner_pid,
        "started_iso": started_iso,
        "started_epoch": started_epoch,
        "alarm_seconds": alarm_seconds,
    }).encode("utf-8")


def try_acquire(target_dir, owner_pid=None):
    """One atomic test-and-set attempt against `target_dir`'s NAME, via
    os.mkdir — the sole primitive this whole design trusts for exclusivity
    (atomic even across NFS, unlike file-creation edge cases). Raises
    FileExistsError if the name is already taken, lets any OTHER OSError
    (permission denied, ENOSPC, read-only fs, ...) propagate — that is a
    real I/O failure, not a contention outcome, and must not be swallowed.

    The payload file is written INSIDE the directory only AFTER the mkdir
    itself succeeds: only the mkdir's own atomicity is load-bearing for
    exclusivity, so a peer can never observe a name that exists but is
    still mid-write UNDER A DIFFERENT NAME the way the round-1 file-based
    design's write-then-link scheme could — here, the very fact that
    `target_dir` exists at all already proves its creator won the mkdir."""
    os.mkdir(target_dir, 0o755)
    fd = os.open(os.path.join(target_dir, OWNER_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(fd, _lock_payload_bytes(pid if owner_pid is None else owner_pid))
    finally:
        os.close(fd)
    return True


def read_owner(target_dir):
    try:
        with open(os.path.join(target_dir, OWNER_FILE), encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data["pid"]), float(data["started_epoch"]), float(data["alarm_seconds"])
    except Exception:
        return None  # unreadable/malformed/mid-write: caller treats as stale


def is_stale(existing):
    if existing is None:
        return True
    existing_pid, existing_started_epoch, existing_alarm_seconds = existing
    if force_unlock:
        return True
    try:
        os.kill(existing_pid, 0)
        pid_live = True
    except ProcessLookupError:
        pid_live = False
    except PermissionError:
        # Process exists but isn't ours to signal — treat as live
        # (conservative: never reclaim a lock we can't confirm is dead).
        pid_live = True
    if not pid_live:
        return True
    # PID is live, but a parent-process SIGKILL orphans its child (verified
    # live during this plan's own review) — "PID exists" alone is not proof
    # the holding run is still genuinely progressing. Bound staleness to the
    # LOCK'S OWN recorded alarm_seconds (never this invocation's own), so a
    # differently-alarmed caller can't compute a different staleness bound
    # than the run that actually holds it.
    age = started_epoch - existing_started_epoch
    return age > existing_alarm_seconds


def report_held():
    # A few quick re-reads resolve a winner's real pid across the
    # microseconds-wide window where its own owner.json write hasn't landed
    # yet — the lock itself is already exclusively held by exactly one
    # process either way; this loop only makes the reported pid accurate,
    # never "unknown" for what is a purely cosmetic timing gap.
    winner = None
    for _ in range(20):
        winner = read_owner(lockdir)
        if winner is not None:
            break
        time.sleep(0.01)
    winner_pid = winner[0] if winner is not None else "unknown"
    print(f"held:{winner_pid}")
    sys.exit(0)


try:
    try_acquire(lockdir)
    print("acquired")
    sys.exit(0)
except FileExistsError:
    pass  # contended — fall through to the stale/held decision below
except OSError as exc:
    print(f"lock-write-error: {exc}", file=sys.stderr)
    sys.exit(1)

existing = read_owner(lockdir)
if not is_stale(existing):
    print(f"held:{existing[0]}")
    sys.exit(0)

# --- Stale (or unreadable/force-targeted): contend for the EXCLUSIVE
# reclaim marker before touching `lockdir` at all. A loser here NEVER
# renames/unlinks `lockdir` itself — it refuses/reports held, exactly like
# refusing a live lock, per the fix's own required design. -----------------
reclaim_marker = f"{lockdir}.reclaiming"


def try_acquire_marker():
    try_acquire(reclaim_marker, owner_pid=pid)


def marker_owner_pid():
    owner = read_owner(reclaim_marker)
    return owner[0] if owner is not None else None


try:
    try_acquire_marker()
except FileExistsError:
    owner_pid = marker_owner_pid()
    owner_dead = False
    if owner_pid is not None:
        try:
            os.kill(owner_pid, 0)
        except ProcessLookupError:
            owner_dead = True
        except PermissionError:
            owner_dead = False
    if not owner_dead:
        # Someone else is live and actively reclaiming this slug's lock
        # right now. Refuse — never retry our own rename/mkdir against
        # `lockdir` while we don't hold the marker.
        report_held()
    # The marker's own owner is dead (SIGKILL mid-reclaim) — the marker
    # itself is now the stale thing, reclaimed via the identical
    # rename-quarantine-then-recreate sequence, one level down, so a dead
    # reclaimer can never leak a PERMANENT block on this slug.
    marker_quarantine = f"{reclaim_marker}.reclaimed.{os.getpid()}.{time.monotonic_ns()}"
    try:
        os.rename(reclaim_marker, marker_quarantine)
    except (FileNotFoundError, OSError):
        report_held()  # lost the marker-reclaim race too — refuse, do not touch
    try:
        os.unlink(os.path.join(marker_quarantine, OWNER_FILE))
    except FileNotFoundError:
        pass
    try:
        os.rmdir(marker_quarantine)
    except OSError:
        pass
    try:
        try_acquire_marker()
    except FileExistsError:
        report_held()  # someone else won the marker immediately after our reclaim
except OSError as exc:
    print(f"lock-write-error: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    # We hold the exclusive reclaim marker. Re-verify `lockdir`'s state —
    # the ORIGINAL stale lock may have been released cleanly (trap EXIT) in
    # between our first read and winning the marker.
    if not os.path.isdir(lockdir):
        # Cleanly released while we waited for the marker. Safe to acquire
        # fresh: nothing else can be racing this mkdir while we hold the
        # marker (a fresh acquirer only reaches its own initial
        # try_acquire() above, BEFORE ever contending for the marker).
        try:
            try_acquire(lockdir)
            print("acquired")
            sys.exit(0)
        except FileExistsError:
            report_held()  # structurally shouldn't happen; fail safe

    still_existing = read_owner(lockdir)
    if still_existing is None:
        # The directory exists but its payload is missing/unreadable — the
        # narrow write-in-progress window (a peer's try_acquire() has done
        # os.mkdir but not yet finished writing owner.json), NOT a cleanly-
        # released lock. We must NEVER touch/rename a directory whose
        # ownership we cannot currently confirm — refuse this attempt and
        # let a later attempt re-evaluate the (by-then fully-written) lock.
        print("held:unknown")
        sys.exit(0)
    if not is_stale(still_existing):
        # Someone legitimately re-acquired it fresh in the gap between our
        # first staleness decision and winning the marker. Refuse — do not
        # touch a lock that is provably no longer stale.
        print(f"held:{still_existing[0]}")
        sys.exit(0)

    # We are the sole, exclusive RECLAIMER, and `lockdir` is confirmed still
    # the stale generation we originally inspected. Rename-away is safe with
    # respect to every other RECLAIM attempt (all blocked behind the marker
    # we hold) -- but NOT with respect to a FRESH acquirer, whose initial
    # try_acquire() at the top of this script is deliberately ungated on the
    # marker (a fresh acquirer never needs to reclaim anything, so it never
    # contends for the marker at all). Once we rename `lockdir` away, the
    # name is free, and a fresh acquirer racing us can win the recreate
    # below before we do -- this is real, reproducible contention, not a
    # theoretical edge case (verified: ~1/6 trials at N=8 concurrent
    # contenders). Guard the recreate exactly like the sibling
    # `try_acquire(lockdir)` call above already does, or a lost race here is
    # misreported as a genuine I/O failure instead of ordinary, expected
    # contention.
    quarantine_path = f"{lockdir}.reclaimed.{os.getpid()}.{time.monotonic_ns()}"
    os.rename(lockdir, quarantine_path)
    try:
        os.unlink(os.path.join(quarantine_path, OWNER_FILE))
    except FileNotFoundError:
        pass
    try:
        os.rmdir(quarantine_path)
    except OSError:
        pass

    try:
        try_acquire(lockdir)
        print("force-reclaimed" if force_unlock else "acquired")
        sys.exit(0)
    except FileExistsError:
        # Lost the race to a fresh acquirer that won `os.mkdir` between our
        # rename-away and this recreate. This is ordinary contention, not a
        # real I/O error -- report it exactly like the sibling path does.
        report_held()
except OSError as exc:
    print(f"lock-write-error: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    # Release the reclaim marker on every path out of this block (success,
    # refusal, or a real I/O error) — os.rmdir requires an EMPTY directory,
    # so owner.json must be unlinked FIRST or rmdir always raises ENOTEMPTY
    # and gets silently swallowed by the bare except below, permanently
    # leaking the marker (found during this fix's own testing).
    try:
        os.unlink(os.path.join(reclaim_marker, OWNER_FILE))
    except FileNotFoundError:
        pass
    try:
        os.rmdir(reclaim_marker)
    except OSError:
        pass
PYEOF
)
    ACQUIRE_STATUS=$?

    if [ "$ACQUIRE_STATUS" -ne 0 ]; then
        # BLOCKER 3 (round 1): the acquisition script itself failed (a real
        # I/O error), not merely "someone else holds the lock". Continuing
        # here would run this job entirely unguarded with no lock and no
        # signal other than a buried stderr line. Refuse instead: fail-fast
        # heartbeat naming the cause, exit 75 — same convention as every
        # other refusal path in this guard.
        python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$LOCKDIR" "$ACQUIRE_OUT" <<'PYEOF' || true
import json, sys, datetime
path, job, started, cadence, lockdir, detail = sys.argv[1:7]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 75,
        "cadence": cadence,
        "status": "failed",
        "summary": (
            f"WRAPPER: refused — lock acquisition for {lockdir!r} failed with a "
            f"real I/O error rather than ordinary contention (detail: {detail!r}) "
            "— continuing unlocked would be unsafe, refusing instead (see H3)."
        ),
    }, fh)
PYEOF
        _wrapper_say_heartbeat "refused — lock acquisition failed with a real I/O error (see H3)."
        exit 75
    fi

    case "$ACQUIRE_OUT" in
        held:*)
            HOLDER_PID="${ACQUIRE_OUT#held:}"
            # Acquisition refused: another live, non-stale run holds this
            # slug's lock. Fail-fast heartbeat, exit 75 (EX_TEMPFAIL) —
            # explicit exit, never relying on set -u's own behavior, since
            # this script deliberately runs without -e.
            #
            # BLOCKER 2: this heartbeat's `finished_at` is a fresh, non-null
            # UTC timestamp — necessary, since REQUIRED_KEYS/timestamp-format
            # validation in heartbeat_audit.py demands a well-formed
            # finished_at on every heartbeat, in-flight START shapes
            # excepted. But every one of heartbeat_audit.py's liveness
            # checks (silent-job, loaded-never-fired, dangling-heartbeat)
            # key ONLY on finished_at being set/recent — none of them read
            # `exit` — so on its own this refused-run heartbeat is
            # indistinguishable from a clean, just-finished run and resets
            # the "last heartbeat" clock those checks use. That would let an
            # orphaned lock silently starve every future run of this slug
            # while heartbeat_audit.py keeps reporting it healthy.
            # heartbeat_audit.py's own check #8 (lock-refused) closes this:
            # it flags any label whose most recent heartbeat has exit == 75,
            # distinct by name from a clean finish, so this refusal is loud
            # rather than looking like success. See that module for the
            # check itself.
            python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$WHEEL_SLUG" "$HOLDER_PID" <<'PYEOF'
import json, sys, datetime
path, job, started, cadence, slug, holder_pid = sys.argv[1:7]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 75,
        "cadence": cadence,
        "status": "failed",
        "summary": (
            f"WRAPPER: refused — wheel lock for slug {slug!r} is already held "
            f"by live pid {holder_pid} — concurrent wheel run for this repo "
            "not permitted (refuse-don't-replace; see H3)."
        ),
    }, fh)
PYEOF
            _wrapper_say_heartbeat "refused — the wheel lock is already held by a live pid (see H3)."
            exit 75
            ;;
    esac

    # Acquired ("acquired" or "force-reclaimed"): the lock DIRECTORY itself
    # was already written atomically inside the Python attempt above (the
    # round-2 mkdir-based design) — there is no separate write step left to
    # race here. Set WHEEL_LOCK_HELD=1 in this SAME branch, immediately
    # after the case statement above falls through — never earlier (a
    # failed/refused acquisition must never delete another holder's lock on
    # this process's own exit) and never later (no window where the lock is
    # held with no release path). The unified _wrapper_exit_cleanup trap
    # (installed once, at the top of this script -- fix round, item 5) reads
    # this flag plus LOCKDIR/LOCK_FORCE_RECLAIMED to perform the actual
    # release + force-reclaim stamp on ANY exit path; this site only sets
    # the state, it never installs its own separate trap (a second `trap
    # ... EXIT` call anywhere in this script would silently REPLACE, not
    # stack with, an earlier one -- exactly the hazard a unified trap
    # avoids).
    WHEEL_LOCK_HELD=1
    LOCK_FORCE_RECLAIMED=0
    if [ "$ACQUIRE_OUT" = "force-reclaimed" ]; then
        LOCK_FORCE_RECLAIMED=1
    fi
fi
# --- end concurrency guard --------------------------------------------

P=$(cat "$PROMPT_FILE" 2>/dev/null || true)
if [ -z "$P" ]; then
    # Same convention the old inline one-liners used (exit 78 = EX_CONFIG):
    # an empty/missing prompt file is a config error, not a session death.
    # Still write a heartbeat so this doesn't silently read as "never ran".
    python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$PROMPT_FILE" <<'PYEOF'
import json, sys, datetime
path, job, started, cadence, prompt_file = sys.argv[1:6]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 78,
        "cadence": cadence,
        "status": "failed",
        "summary": f"WRAPPER: prompt file {prompt_file!r} was empty/unreadable — job never dispatched",
    }, fh)
PYEOF
    _wrapper_say_heartbeat "prompt file was empty/unreadable — job never dispatched"
    exit 0
fi

# --- Browser-pool pre-flight (card 44 / GH #5569) --------------------------
# A WEEKLY job cannot depend on a ~24h session cookie: the named constraint is
# the credential's TTL (~24h) versus this job's cadence (7d), so a hand-primed
# jar is dead on essentially every scheduled run. Re-prime immediately before
# the CLI starts — the CLI's MCP servers read the storage-state jar only at
# process start, so this wrapper IS the "restart Claude Code" step that
# prime_browser_pool.sh's header asks a human for. That step is free here, by
# construction, on every run.
#
# This is a launchd subprocess, NOT a Claude `Bash` tool call, so no settings
# permission rule (including the OtherApp repo's `gcloud secrets versions
# access` deny) is in this path. Nothing is widened and nothing is relied on.
#
# NAMED BLAST RADIUS — read before changing anything here. prime_browser_pool.sh
# merges into TWO jars, in a fixed order it enforces itself:
#   1. the AGENCY pool jar (~/.cache/agency/playwright-pool/merged-storage-state.json),
#      which that script's own comment says is SHARED with non-staging captures
#      (Google, Indeed, LinkedIn, DocuSign — ~60 domains, including the
#      operator's personal admin.google.com / console.cloud.google.com sessions);
#   2. only THEN the staging-only runtime jar this job actually uses.
# So this line makes an UNATTENDED weekly job rebuild that shared jar. That is
# an accepted, named property of this change, not an accident. It is safe by
# construction, not by assurance: step 1 is a PURE REBUILD from fixed on-disk
# sources (playwright_pool.py merge-state), mints NO new session for any of
# those domains, only DROPS expired cookies, writes 0600 — and the runtime pool
# productqa uses never mounts that jar at all (browser_pool.py:562-564 loads
# state/staging-merged.json only).
#
# ORDERING CONSEQUENCE, load-bearing for how prime_status must be READ:
# prime_browser_pool.sh runs `set -euo pipefail` and step 1 ends in `|| die`,
# so an AGENCY-jar failure exits 1 BEFORE step 2 ever runs. In that case the
# staging jar is simply untouched (possibly stale), NOT freshly broken, and
# staging auth may be perfectly healthy. prime_status="failed" therefore means
# exactly "the pre-flight did not complete" and NOTHING more specific — never
# read it as "staging auth is dead". prompts/daily_sweep.txt's consumer text is
# worded to match. Decoupling the two merges so an Agency-jar failure cannot
# block the staging jar is tracked as its own follow-up issue (see card 44 §7).
#
# NON-FATAL BY DESIGN: a priming failure must degrade the run to its
# non-browser work, never abort a job that has other tasks to do. Aborting
# would convert a degraded run into a dead one and put a human back into an
# automated path.
#
# OUTPUT IS DISCARDED deliberately. The script's no-secret-in-output contract
# already keeps the password out of stdout, but it DOES print the login email,
# and this wrapper's stdout is a persisted log file (the plist's
# StandardOutPath). Only the typed ok/failed/skipped status is ever recorded.
#
# OPT-IN via OVERSIGHT_PRIME_APP: only the productqa plist sets it. The other
# jobs do no browser walk; priming for them would spend a staging login per
# job per run at a non-constraint.
#
# RUN THROUGH python3, NOT bash/perl directly -- a TCC (macOS privacy)
# finding, verified by execution with throwaway launchd jobs on 2026-09-17:
# under launchd, `~/Desktop` is privacy-protected for `/bin/bash` and `perl`
# (`ls ~/Desktop` -> "Operation not permitted"; exec'ing this very
# prime_browser_pool.sh path failed rc 126 "Operation not permitted" even
# though `[ -x "$PRIME_SH" ]` passed), which is exactly why the live weekly
# run stamped prime_status=failed and never re-primed. `/opt/homebrew/bin/
# python3` DOES carry the Desktop grant under launchd (it listed ~/Desktop
# successfully), and -- decisive -- a bash child spawned BY python3 ran the
# same priming script to completion under launchd (rc 0, both jars rebuilt):
# macOS attributes a child process's filesystem access to its TCC-granted
# parent. So python3 must be the actual process that launches bash here, not
# just a helper invoked after the fact.
#
# BOUNDED via python's own subprocess timeout, replacing the prior
# `perl -e 'alarm shift; exec @ARGV'` idiom (that idiom cannot be reused as
# the outer process without reintroducing the TCC gap above; the CLI's own
# alarm backstop below is unaffected by this rewrite and still uses perl).
# Verified by execution: with no bound at all, a hung pre-flight (e.g. a
# network stall in the headless login) left the wrapper alive past the CLI's
# own alarm window with NO heartbeat written at all -- strictly worse than
# the stale-jar bug this pre-flight exists to fix, since a stale jar still
# yields a run with typed telemetry while a hung pre-flight yields nothing
# (no heartbeat, no prime_status, no log tail).
#
# ORPHAN FIX (a nit closed by this same rewrite): the prior perl-alarm form
# killed only the exec'd process itself, not any children it had spawned (a
# headless-chromium login flow forks browser processes) -- a killed alarm
# left those orphaned. The python wrapper below launches bash with
# `start_new_session=True` (its own new process group) and, on timeout, kills
# the WHOLE group with `os.killpg(child.pid, signal.SIGKILL)`, so nothing
# survives a bounded hang. Exit 142 on that path mirrors the old alarm-kill
# convention (128 + SIGALRM's 14) for continuity, though nothing downstream
# inspects the exact code -- only the ok/failed if/else below does.
#
# `/bin/bash "$PRIME_SH"` (never a bare exec of the script, and never relying
# on its shebang) is the form proven under launchd above, and it also
# resolves the old exec-failure-fidelity gap for free: bash interprets its
# own argument as a script regardless of any shebang line inside it, so a
# broken/missing interpreter in the target's shebang can no longer cause a
# silent false "ok" the way a direct `exec` of the file could. What DOES
# still fail here is a target that is not a script bash can run at all (e.g.
# a directory) or one that bash runs and which itself exits non-zero -- both
# surface honestly as that exit code, mapped to PRIME_STATUS=failed below. An
# OSError launching bash itself (e.g. `/bin/bash` missing) is caught and
# reported as exit 126, matching the shell convention for "found but could
# not execute". A missing `python3` on PATH makes this whole `if` fail
# (command not found), which also correctly yields PRIME_STATUS=failed --
# the same truthful non-fatal-by-design outcome as every other failure mode
# here, never a masked "ok".
#
# stdout/stderr are still discarded (>/dev/null 2>&1 on the whole python3
# invocation) for the same no-secret-in-log reason as before: the priming
# script's own output carries the login email, and this wrapper's stdout is
# a persisted log file.
#
# WHERE THE PRIMING SCRIPT IS: found through the runtime's repo registry
# (knowledge/repo_registry.json, `repos.<slug>.root`, stored `~`-relative), never at a
# path baked into this wrapper. `_resolve_prime_sh` takes the registered repo named by
# OVERSIGHT_PRIME_REPO (optional; a registry slug) or, when that is unset, the ONE
# registered repo that holds an executable scripts/prime_browser_pool.sh. Zero or more
# than one candidate, an unknown slug, or an unreadable registry resolves to nothing:
# the pre-flight is skipped (PRIME_STATUS=skipped, exactly as for a missing script).
# CONTRACT: every way a job that opted in (OVERSIGHT_PRIME_APP set) can skip prints
# exactly ONE `WRAPPER: prime pre-flight not run - <reason>` line to stderr (the job's
# .err.log), so "skipped" there always says why. The lookup's own failures (no match,
# several matches, an unknown slug, an unreadable registry) are worded by the lookup and
# exit 3; `python3` missing, or the lookup dying any other way (an uncaught exception,
# exit 1), is reported by the shell around it; and a path the lookup found but this
# shell's own `-x` test then rejects is reported by the branch below. The lookup runs in
# python3, the interpreter that carries the Desktop grant under launchd (see the TCC note
# above); bash never lists the registered roots. It runs only when OVERSIGHT_PRIME_APP is
# set, so every other job pays nothing. The PRIME_SH assignment below stays ONE column-0
# line (the sandbox tests rewrite it by that name).
_resolve_prime_sh() {
    local _rc
    [ -n "${OVERSIGHT_PRIME_APP:-}" ] || return 0
    if ! command -v python3 >/dev/null 2>&1; then
        echo "WRAPPER: prime pre-flight not run - python3 not found on PATH" >&2
        return 3
    fi
    python3 -I - "${HOME}/.claude/knowledge/repo_registry.json" "${HOME}" "${OVERSIGHT_PRIME_REPO:-}" <<'PYEOF'
import json
import os
import sys

registry, home, want = sys.argv[1], sys.argv[2], sys.argv[3]
REL = os.path.join("scripts", "prime_browser_pool.sh")


def fail(msg):
    # exit 3 = "the lookup has said why"; the shell reports any other nonzero exit itself
    print("WRAPPER: prime pre-flight not run - " + msg, file=sys.stderr)
    sys.exit(3)


try:
    with open(registry, encoding="utf-8") as fh:
        repos = json.load(fh).get("repos")
except (OSError, ValueError, AttributeError):
    fail("cannot read the repo registry " + registry)
if not isinstance(repos, dict):
    fail("the repo registry " + registry + " has no 'repos' object")


def root_of(slug):
    entry = repos.get(slug)
    root = entry.get("root") if isinstance(entry, dict) else None
    if not isinstance(root, str) or not root or "\x00" in root:
        return None
    if root == "~" or root.startswith("~/"):
        root = home + root[1:]
    return os.path.normpath(root) if os.path.isabs(root) else None


if want:
    root = root_of(want)
    if root is None:
        fail("OVERSIGHT_PRIME_REPO=" + want + " is not a repo with a root in " + registry)
    roots = [root]
else:
    roots = [r for r in (root_of(slug) for slug in repos) if r]
found = sorted(
    {
        os.path.join(r, REL)
        for r in roots
        if os.path.isfile(os.path.join(r, REL)) and os.access(os.path.join(r, REL), os.X_OK)
    }
)
if len(found) == 1:
    print(found[0])
elif not found:
    fail(
        "no "
        + ("repo " + want if want else "registered repo")
        + " has an executable "
        + REL
        + "; set OVERSIGHT_PRIME_REPO to the registry slug of the repo that owns it"
    )
else:
    fail(
        "more than one registered repo has "
        + REL
        + " ("
        + ", ".join(found)
        + "); set OVERSIGHT_PRIME_REPO to the registry slug of the one to use"
    )
PYEOF
    _rc=$?
    if [ "$_rc" -ne 0 ] && [ "$_rc" -ne 3 ]; then
        echo "WRAPPER: prime pre-flight not run - the registry lookup crashed (python3 exit ${_rc})" >&2
    fi
    return "$_rc"
}
PRIME_ALARM_SECONDS=600
PRIME_SH="$(_resolve_prime_sh)"
if [ -n "${OVERSIGHT_PRIME_APP:-}" ] && [ -x "$PRIME_SH" ]; then
    if python3 - "$PRIME_SH" "$OVERSIGHT_PRIME_APP" "$PRIME_ALARM_SECONDS" >/dev/null 2>&1 <<'PYEOF'
import os, signal, subprocess, sys
script, slug, budget = sys.argv[1], sys.argv[2], float(sys.argv[3])
try:
    child = subprocess.Popen(["/bin/bash", script, slug], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
except OSError:
    sys.exit(126)
try:
    sys.exit(child.wait(timeout=budget))
except subprocess.TimeoutExpired:
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except OSError:
        pass
    sys.exit(142)
PYEOF
    then
        PRIME_STATUS=ok
    else
        PRIME_STATUS=failed
    fi
else
    PRIME_STATUS=skipped
    # An opted-in job that skips says why (see the CONTRACT above). An EMPTY $PRIME_SH was
    # already explained on stderr by _resolve_prime_sh; the one case only this shell can see
    # is a path python3 found but our own `-x` test rejects.
    if [ -n "${OVERSIGHT_PRIME_APP:-}" ] && [ -n "$PRIME_SH" ]; then
        echo "WRAPPER: prime pre-flight not run - ${PRIME_SH} is not executable by the wrapper's shell" >&2
    fi
fi

# --- Second-slot skip (THE ISSUE WHEEL plan, WS1-C.1 / Phase C item 1):
# each wheel plist now carries a SECOND StartCalendarInterval slot (03:30,
# the following calendar night relative to the 22:10/22:40 primary slot) as
# a same-night retry for a quota-exhausted primary run. Running the retry
# slot when the primary already succeeded would waste a second CLI
# invocation (and, worse, a second pre-flight probe call) for no reason.
#
# GATED ON IS_SCHEDULED_WHEEL_JOB, NOT bare WHEEL_SLUG (fix round, BLOCKER 1):
# a `manual-wheel-<slug>` on-demand /wheel invocation also exports
# WHEEL_SLUG (for the concurrency guard above) but has no retry slot of its
# own to protect -- an operator's second manual /wheel run later the same
# day must never silently no-op just because an earlier scheduled run (or an
# earlier manual run, irrelevant either way) already stamped status:"ok".
#
# "Already succeeded tonight" is read directly off THIS label's own existing
# heartbeat file (no new state file — the heartbeat already carries
# everything needed): finished_at falls on the SAME UTC calendar date as
# this run's own start AND status == "ok". Never guessed from wall-clock
# slot math alone (a job's actual fire time can drift by minutes under
# launchd), and degrades to "do not skip" (proceed to the pre-flight/main
# run as normal) on any read/parse failure — a skip must never be inferred
# from data this wrapper cannot positively confirm.
#
# INVARIANT THIS COMPARISON DEPENDS ON (fix round, item 7 — read before
# ever changing either slot's time): finished_at[:10] == wrapper_start_iso[:10]
# is a UTC CALENDAR-DATE match, but launchd interprets StartCalendarInterval
# in LOCAL wall-clock time, never UTC (heartbeat_audit.py's own
# most_recent_scheduled_fire() docstring). That holds for today's schedule —
# 22:10/22:40 local -> 04:10/04:40Z, 03:30 local -> 09:30Z, same UTC date,
# including across the DST transition — but it is SILENTLY SCHEDULE-COUPLED:
# moving the primary slot's local hour (e.g. to 18:00 local) could put its
# UTC fire on a DIFFERENT calendar date than the 03:30-local retry slot in
# some timezones, quietly disabling this skip with no error anywhere.
# `hooks/tests/test_run_oversight_job.py::test_second_slot_utc_date_invariant_holds_for_live_plists`
# asserts this invariant directly against every INSTALLED wheel plist's own real
# slot times and against the shipped schedules/example.wheel.plist (the pinned
# schedules are judged in their US Mountain design zone with fixed -6/-7
# offsets, so the verdict does not depend on the runner's TZ) — re-run it (and
# re-derive its own hardcoded weekday/hour expectations, never just widen them)
# after touching any wheel plist's StartCalendarInterval.
if [ "$IS_SCHEDULED_WHEEL_JOB" = "1" ]; then
    ALREADY_OK_TONIGHT=$(python3 - "$HEARTBEAT_FILE" "$WRAPPER_START_ISO" <<'PYEOF'
import json, sys
hb_path, wrapper_start_iso = sys.argv[1:3]
try:
    with open(hb_path, encoding="utf-8") as fh:
        data = json.load(fh)
    finished_at = data.get("finished_at")
    status = data.get("status")
    if (
        isinstance(finished_at, str)
        and isinstance(wrapper_start_iso, str)
        and len(finished_at) >= 10
        and len(wrapper_start_iso) >= 10
        and finished_at[:10] == wrapper_start_iso[:10]
        and status == "ok"
    ):
        print("1")
    else:
        print("0")
except Exception:
    print("0")
PYEOF
)
    if [ "$ALREADY_OK_TONIGHT" = "1" ]; then
        python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, sys, datetime
path, job, started, cadence = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 0,
        "cadence": cadence,
        "status": "ok",
        "wrapper_skip": "second-slot",
        "summary": "WRAPPER: skipped — this label's earlier slot already finished status:ok tonight (same UTC date); no retry needed.",
    }, fh)
PYEOF
        _wrapper_say_heartbeat "skipped — this label's earlier slot already finished status:ok tonight (same UTC date); no retry needed."
        exit 0
    fi
fi
# --- end second-slot skip ------------------------------------------------

# --- Wheel launch context (GH #4767; wheel jobs only) ------------------------
# After the free, cannot-misfire second-slot skip and before the quota
# pre-flight (which costs an API call). hooks/wheel_launch_context.py runs the
# remaining pre-launch checks in python3 (TCC-safe under launchd, a8bcd86) and
# prints exactly one line: `launch` (it wrote CTX_DIR/context.txt and
# CTX_DIR/argv.txt), `refuse <code>: <detail>` (it wrote the refusal
# heartbeat), or anything else (crash/no output), which fails CLOSED here.
# RUNTIME_DIR is this script's own tree, realpath'd, because the sink's allow
# rule and the context's SINK= line must be the exact string the session
# types; data (heartbeats, settings, wheel_repos.json) comes from $HOME. In
# production the two are the same ~/.claude.
if [ -n "${WHEEL_SLUG:-}" ]; then
    RUNTIME_DIR=$(python3 -c 'import os,sys; print(os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "..")))' "${BASH_SOURCE[0]}" 2>/dev/null) || RUNTIME_DIR=""
    RUN_SCRATCH=""; CTX_DIR=""; LAUNCH_DECISION=""; LAUNCH_ERR=""
    _raw=$(mktemp -d "${TMPDIR:-/tmp}/oversight_wheel.XXXXXX" 2>/dev/null) || _raw=""
    if [ -n "$_raw" ]; then
        RUN_SCRATCH=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$_raw" 2>/dev/null) || RUN_SCRATCH=""
        [ -n "$RUN_SCRATCH" ] || RUN_SCRATCH="$_raw"   # the trap still reaps it; the helper then refuses scratch-unavailable
    fi
    CTX_DIR=$(mktemp -d "${TMPDIR:-/tmp}/oversight_wheel_ctx.XXXXXX" 2>/dev/null) || CTX_DIR=""
    if [ -z "$RUNTIME_DIR" ] || [ -z "$RUN_SCRATCH" ] || [ -z "$CTX_DIR" ]; then
        LAUNCH_ERR="could not resolve the runtime dir or create the run scratch/context dirs"
    else
        # helper stderr is NOT discarded: a traceback lands in .err.log for daily_sweep step A
        LAUNCH_DECISION=$(python3 "${RUNTIME_DIR}/hooks/wheel_launch_context.py" build \
            --job "$JOB_LABEL" --started-at "$WRAPPER_START_ISO" --cadence "$CADENCE_TEXT" \
            --heartbeat-file "$HEARTBEAT_FILE" --run-scratch "$RUN_SCRATCH" \
            --preamble "$(dirname "$PROMPT_FILE")/_preamble.txt" \
            --sink "${RUNTIME_DIR}/hooks/wheel_sink.py" --out-dir "$CTX_DIR")
    fi
    case "$LAUNCH_DECISION" in
        launch)
            if [ -s "$CTX_DIR/context.txt" ] && [ -s "$CTX_DIR/argv.txt" ]; then
                # BLOCKER B1 (trust-architect, fix round): read argv.txt into "$@" HERE, right
                # after the non-empty check, not just before the exec far below -- a TOCTOU gap
                # between this check and the later read let a since-deleted argv.txt silently
                # produce zero tokens, which ran claude with NONE of the launcher's restrictions
                # (no --tools/--allowedTools/--disallowedTools/--strict-mcp-config). Read and
                # validate the shape NOW, so a missing/emptied/malformed file fails closed via the
                # existing launch-context-error path below instead of reaching the exec unchecked.
                # bash 3.2 has no safe empty-array expansion under set -u, so "$@" carries the
                # parsed tokens forward to the exec site, which re-asserts the same shape.
                #
                # Non-blocking item (a) (trust re-review round 4): the shape check only required
                # $1 == --add-dir. A truncated argv.txt that kept its first two tokens but lost
                # everything after would pass this check and launch with no --tools and no
                # --disallowedTools at all. Require --disallowedTools to be present in the parsed
                # tokens too, at BOTH this site and the exec-site re-check below, so a truncated
                # file fails closed here instead of reaching claude unrestricted.
                set --
                while IFS= read -r _tok || [ -n "$_tok" ]; do set -- "$@" "$_tok"; done < "$CTX_DIR/argv.txt"
                _has_disallowed=0
                for _tok in "$@"; do
                    if [ "$_tok" = "--disallowedTools" ]; then _has_disallowed=1; break; fi
                done
                if [ "$#" -gt 0 ] && [ "$1" = "--add-dir" ] && [ "$_has_disallowed" -eq 1 ]; then
                    # Non-blocking item (d) (trust re-review round 4): `cat`'s exit code was never
                    # checked. A context.txt that vanishes after the [ -s ] check above (the same
                    # TOCTOU class B1 already guards argv.txt against) previously let this command
                    # substitution silently yield an empty string, launching with the restrictions
                    # intact but WITHOUT the authoritative nonce block the prompt's line 1 says
                    # sits above it. Capture cat's rc explicitly and fail closed on failure instead
                    # of proceeding on an empty/partial context.
                    if _ctx_content="$(cat "$CTX_DIR/context.txt")"; then
                        P="$_ctx_content"$'\n\n'"$P"
                    else
                        LAUNCH_DECISION=""
                        LAUNCH_ERR="context.txt existed at the [ -s ] check but could not be read (cat failed) before exec"
                    fi
                else
                    LAUNCH_DECISION=""
                    LAUNCH_ERR="argv.txt did not parse into a non-empty token list starting with --add-dir and including --disallowedTools (got \"$#\" tokens)"
                fi
            else
                LAUNCH_DECISION=""
                LAUNCH_ERR="the helper printed launch but context.txt or argv.txt is empty or unreadable"
            fi ;;
        "refuse "*)
            _wrapper_say "refused before launch — ${LAUNCH_DECISION#refuse }; claude was not launched (GH #4767)."
            exit 0 ;;
    esac
    if [ "$LAUNCH_DECISION" != "launch" ]; then
        [ -n "$LAUNCH_ERR" ] || LAUNCH_ERR="the launch-context helper crashed or printed no decision"
        python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$LAUNCH_ERR" <<'PYEOF' || true
import datetime, json, os, sys
hb_path, job, started, cadence, err = sys.argv[1:6]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data = {"job": job, "started_at": started, "finished_at": now, "exit": 79, "cadence": cadence,
        "status": "failed", "hard_stop": "launch-context-error",
        "summary": f"WRAPPER: refused before launch — launch-context-error: {err}; claude was not "
                   "launched (fail closed, GH #4767)."}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
        _wrapper_say "refused before launch — launch-context-error: ${LAUNCH_ERR}; claude was not launched (fail closed, GH #4767)."
        exit 0
    fi
fi
# --- end wheel launch context -------------------------------------------------

# --- Quota pre-flight (THE ISSUE WHEEL plan, WS1-C.1 / Phase C item 1): a
# minimal, bounded `claude -p` call using the SAME --model the main run
# below uses, BEFORE spending the main run's own alarm window. The log
# evidence motivating this (plan F2) shows three distinct quota-exhaustion
# messages — session-limit, weekly-limit, and a server-side rate message —
# so a fixed-time schedule move alone would not have closed this; this
# probe reads the account's ACTUAL live quota state at the moment it tries
# to run, not a guess from the clock.
#
# SCOPED TO WHEEL-SLUG INVOCATIONS ONLY (fix round, BLOCKER 2): this used to
# run unconditionally for ALL 8 scheduled jobs sharing this wrapper, but only
# the two wheel jobs have a same-night retry slot (the second-slot skip
# above) to make a spurious skip cheap. For a MONTHLY job (testarch/
# trustarch/agentarch) or the weekly/daily jobs, one transient quota window
# hitting the pre-flight would silently lose that job's entire audit for up
# to a month -- a single skipped-quota heartbeat is streak 1 and is
# deliberately never flagged by heartbeat_audit.py's job-failed check (see
# its own docstring: "a single skip, or two in a row, is ordinary and NOT
# flagged"). Gated on bare WHEEL_SLUG (not IS_SCHEDULED_WHEEL_JOB) -- a
# manual `/wheel` run DOES still get the pre-flight: it is cheap (60s bound,
# fails open, never blocks), and an operator watching a manual run benefits
# from an early, honest "quota exhausted" signal exactly as much as an
# unattended one does; there is no retry-slot reason to exempt it, only a
# cost-avoidance reason, and the cost here is bounded and fails open either
# way. Every non-wheel job (WHEEL_SLUG unset) behaves EXACTLY as it did
# before this whole change: PREFLIGHT_EXIT=0 unconditionally, QUOTA_HIT can
# never become 1, no exit-70 path is reachable.
#
# Skippable via CSA_WHEEL_SKIP_PREFLIGHT=1 (tests only — never a standing
# production posture; mirrors CSA_DISABLE_HOOKS's own escape-hatch shape).
#
# Bounded to 60s with the wrapper's OWN idiom (`perl -e 'alarm shift; exec
# @ARGV'`, already used below — `timeout`/`gtimeout` do not exist on this
# machine). The perl idiom exits 142 on its own SIGALRM kill; that is read
# here as "pre-flight timed out", folded into the FAIL-OPEN branch below,
# never treated as a limit-match. The 60s bound itself is overridable via
# CSA_WHEEL_PREFLIGHT_ALARM_SECONDS (tests only, same posture as
# CSA_WHEEL_SKIP_PREFLIGHT — never set in any real plist) so a test proving
# "a hung pre-flight proceeds after its bound" doesn't have to burn a real
# 60 seconds per run.
#
# FAIL OPEN, always: a pre-flight that itself errors, times out, or exits
# non-zero for any OTHER reason must never block the main run — this probe
# exists to catch a KNOWN quota-exhaustion message, not to become a second
# gate a flaky network can trip. Only an EXPLICIT limit-text match causes a
# skip; every other outcome (including "the probe itself failed") proceeds
# to the main run exactly as if this block did not exist.
PREFLIGHT_ALARM_SECONDS="${CSA_WHEEL_PREFLIGHT_ALARM_SECONDS:-60}"
if [ -n "${WHEEL_SLUG:-}" ] && [ "${CSA_WHEEL_SKIP_PREFLIGHT:-0}" != "1" ]; then
    # BUG FOUND DURING THIS COMMIT'S OWN FALSIFIABILITY TESTING (verified by
    # direct execution, 2026-09-20): capturing this call's output via
    # `$(...)` command substitution can hang FAR past PREFLIGHT_ALARM_SECONDS
    # when `$CLAUDE_BIN` forks a child before the alarm fires -- SIGALRM
    # kills the directly-exec'd process, but an already-forked grandchild is
    # ORPHANED and keeps running, inheriting the SAME stdout/stderr pipe
    # `$(...)` is reading from. Command substitution does not return until
    # EVERY process holding that pipe's write end closes it, so a single
    # surviving grandchild defeats the alarm entirely -- reproduced directly:
    # a `sleep 600` grandchild left the parent `$(...)` blocked for the
    # remainder of that sleep, not PREFLIGHT_ALARM_SECONDS. This is the exact
    # orphan class the browser-pool pre-flight above already documents
    # (`os.killpg` after `start_new_session=True`) -- the perl-alarm idiom
    # alone, uncomposed with process-group control, does not close it.
    # FIX: redirect to a REGULAR FILE instead of a pipe. A file write is
    # never blocked by a lingering descendant process the way a pipe read
    # is -- the alarm-killed process's own writes land, an orphaned
    # grandchild's writes (if any) also land or are simply ignored, and the
    # shell's own `$(perl ...)` here only ever waits on perl/bash's own real
    # exit status, never on a pipe's writers all closing.
    #
    # LEAK FIX (fix round, item 5): if the wrapper is killed between mktemp
    # and the rm -f below (e.g. the outer alarm/SIGTERM/operator kill -9 on
    # the WRAPPER process itself, not the perl-alarm's own inner kill), the
    # `rm -f` line is never reached and the temp file leaks. Setting
    # PREFLIGHT_OUT_FILE here is now sufficient on its own: the unified
    # `_wrapper_exit_cleanup` trap (installed ONCE at the top of this script)
    # already checks this exact variable and removes the file on ANY exit
    # path -- no separate `trap ... EXIT` call needed here (and none should
    # ever be added here again: a second `trap ... EXIT` anywhere in this
    # script REPLACES rather than stacks with the unified one, which is
    # exactly the hazard that motivated consolidating to a single trap).
    PREFLIGHT_OUT_FILE=$(mktemp "${TMPDIR:-/tmp}/csa_wheel_preflight.XXXXXX")
    # item 6: silence the "Alarm clock: N" line that lands in the job's own
    # error log on every pre-flight timeout. VERIFIED BY DIRECT EXECUTION
    # (fix round) that this line is BASH'S OWN job-control diagnostic about
    # a SIGALRM-terminated foreground job -- not something perl or the
    # exec'd CLI writes to any fd of its own -- so a trailing `2>...`
    # redirect on the perl invocation's OWN command line does nothing to it
    # (confirmed: `perl ... >"$FILE" 2>&1 2>/dev/null` still let the message
    # through in isolation testing). The line is suppressed only by wrapping
    # the WHOLE command as a brace-group and redirecting THAT group's stderr
    # -- bash attributes its own job-control notice to the brace group's
    # stderr, which `2>/dev/null` on the group then correctly discards.
    # `>"$PREFLIGHT_OUT_FILE" 2>&1` stays INSIDE the group, on the perl
    # invocation itself, exactly as before -- it captures the exec'd CLI's
    # real stdout/stderr for the limit-text match below, untouched by the
    # outer group-level redirect (bash resolves the innermost redirect for
    # fd 1/2 of the actual child process; only bash's OWN diagnostic, which
    # is emitted by the shell itself rather than inherited by the child, is
    # what the outer redirect reaches).
    # #5922 (F6 out-of-scope follow-up item): the pre-flight needs no
    # tools at all -- it exists solely to read the account's live quota state
    # from the CLI's own startup/response behavior, never to do work -- so it
    # is launched with the SAME least-privilege posture 1c9c5e5 gave the main
    # wheel run, taken to its logical floor: `--strict-mcp-config
    # --mcp-config '{"mcpServers":{}}'` (no MCP servers reachable at all,
    # same MCP_CONFIG_EMPTY literal wheel_launch_context.py uses) plus
    # `--tools ""`, which the CLI's own --help documents as disabling every
    # built-in tool outright -- stricter than the main run's explicit
    # allow/deny lists, and correct here because the pre-flight never needs
    # Bash/Read/Write/Workflow/anything: it only ever prints "OK" or a limit
    # message. Verified by direct execution (this change's own testing) that
    # `--tools ""` still yields a clean "OK" reply with no tool grants at
    # all. #5922 fix round (item 9): `--permission-mode` is now `default`,
    # not `acceptEdits` -- `acceptEdits` auto-accepts file-edit permission
    # prompts specifically, which is meaningless (and misleadingly permissive
    # to read) when `--tools ""` has already disabled every tool, edits
    # included; `default` is the CLI's own least-assuming posture and is
    # correct for a probe that does no work at all. Every other flag (model,
    # the alarm/output-file capture around it) is unchanged from before this
    # commit.
    { perl -e 'alarm shift; exec @ARGV' "$PREFLIGHT_ALARM_SECONDS" "$CLAUDE_BIN" -p "quota preflight — reply OK" --model sonnet --permission-mode default --strict-mcp-config --mcp-config '{"mcpServers":{}}' --tools "" >"$PREFLIGHT_OUT_FILE" 2>&1; } 2>/dev/null
    PREFLIGHT_EXIT=$?
    PREFLIGHT_OUT=$(cat "$PREFLIGHT_OUT_FILE" 2>/dev/null || true)
    rm -f "$PREFLIGHT_OUT_FILE"
    # OBSERVER-ONLY instrumentation (GH #4767, 2026-09-23). Log-only: it
    # changes no control flow, gates nothing, and cannot cause a skip or a
    # proceed. It exists because the pre-flight added in 711d600 has never
    # once produced a `skipped-quota` heartbeat (measured: `grep -c
    # "skipped — quota" logs/*.err.log` -> 0 across all 12 job logs) across
    # four wheel fires whose .out.log was 100% quota text -- so exactly one
    # of the two arms below is silently missing, and NOTHING on disk today
    # says which:
    #   (a) PREFLIGHT_EXIT lands outside the {0,142} inspection window at
    #       the `if` below, so the limit text is never even examined; or
    #   (b) PREFLIGHT_EXIT is in-window but the limit text never reaches
    #       $PREFLIGHT_OUT_FILE (different wording, or written to a stream
    #       the redirect above does not capture).
    # RESOLVED (F6, 2026-09-24): the data named arm (a), exit=1, and the
    # window below now includes exit 1. This diagnostic stays, log-only, so
    # a future change in the CLI's limit exit or wording is visible on disk.
    # History: this was deliberately NOT fixed blind: widening the {0,142} window without
    # this data would convert a flaky network into a silent skip, which is
    # precisely what the "FAIL OPEN, always" paragraph above this pre-flight
    # block forbids. The next
    # real quota night writes the discriminating evidence here; the fix
    # lands after that, keyed to whichever arm the data names.
    # Bounded, never fatal: `|| true` plus a 200-byte head cap, so a full
    # disk or an odd $PREFLIGHT_OUT can never abort the wrapper here.
    #
    # NO OUTER `{ ... } 2>/dev/null` WRAPPER, deliberately — an earlier draft
    # of this block had one, and it silently ATE the very diagnostic the
    # block exists to emit (the outer redirect discards fd 2, which is
    # exactly where `>&2` writes). Caught by direct execution, not by
    # reading: with the wrapper the block printed NOTHING for a synthetic
    # `exit=1 / "You've hit your weekly limit"` input, which would have
    # reproduced the original "no evidence on disk" bug one level down.
    # The diagnostic MUST reach fd 2 — that is the job's .err.log, which is
    # where the next quota night's evidence has to land to be readable.
    printf 'PREFLIGHT_DIAG exit=%s bytes=%s head=%s\n' \
        "$PREFLIGHT_EXIT" \
        "$(printf '%s' "$PREFLIGHT_OUT" | wc -c | tr -d ' ')" \
        "$(printf '%s' "$PREFLIGHT_OUT" | head -c 200 | tr '\n' ' ')" >&2 || true
else
    PREFLIGHT_OUT=""
    PREFLIGHT_EXIT=0
fi

QUOTA_HIT=0
THROTTLE_HIT=0
if [ "$PREFLIGHT_EXIT" -eq 0 ] || [ "$PREFLIGHT_EXIT" -eq 1 ] || [ "$PREFLIGHT_EXIT" -eq 142 ]; then
    # Inspect output on a clean exit, on exit 1, or on the alarm-kill exit
    # (142; the process may still have printed a partial limit message
    # before being killed). Exit 1 is the real CLI's exit on a session limit
    # (and, per the main-run logs, a weekly limit): F6, arm (a) of the
    # diagnostic above, measured on the 2026-09-24
    # 04:10Z and 04:40Z fires as `PREFLIGHT_DIAG exit=1 bytes=60 head=You've
    # hit your session limit`. Widening the window by exactly that code stays
    # fail-open: only an explicit limit-text match below causes a skip, so an
    # exit 1 from a network or auth error still proceeds to the main run.
    # Any OTHER exit code is treated as "probe itself failed", never
    # inspected for a limit match, per the fail-open contract above.
    #
    # #5922 (F6 follow-up): a session/weekly-limit match and a server-side
    # THROTTLE match (`API Error: Server is temporarily limiting requests (not
    # your usage limit)`) are now DISTINCT outcomes, checked as two separate
    # patterns rather than one combined regex. Both still exit 1 from the real
    # CLI and both still skip the main run this slot -- the two-way split only
    # changes which STATUS and which streak counter the skip is recorded
    # under. A throttle is not quota exhaustion: the account's own usage limit
    # is fine, the server is momentarily rate-limiting requests, so folding it
    # into `consecutive_quota_skips` made three throttled nights in a row trip
    # heartbeat_audit.py's check #9 ("quota exhaustion has outlasted...") and
    # send the operator to look at a quota that was never exhausted. A session
    # or weekly limit match takes priority when (in a pathological case) a
    # single probe's output somehow matched both patterns -- quota exhaustion
    # is the higher-signal, more actionable condition of the two.
    if printf '%s' "$PREFLIGHT_OUT" | grep -qiE 'hit your session limit|hit your weekly limit'; then
        QUOTA_HIT=1
    elif printf '%s' "$PREFLIGHT_OUT" | grep -qiE 'temporarily limiting requests'; then
        THROTTLE_HIT=1
    fi
fi

if [ "$QUOTA_HIT" -eq 1 ]; then
    # NEVER exit 75 — that is this wrapper's own EX_TEMPFAIL / lock-refused
    # convention (H3) and heartbeat_audit.py check #8 flags EVERY exit==75
    # heartbeat as lock-refused BY NAME. Reusing 75 here would report a
    # quota skip as a stuck lock nightly. 70 is unused elsewhere in this
    # script.
    #
    # consecutive_quota_skips (heartbeat_audit.py's job-failed check #9):
    # this module runs once per fire and has no standing daemon, so the
    # only place to accumulate "how many skips IN A ROW" is the heartbeat
    # file itself, read BEFORE it is overwritten by this same write. If the
    # PRIOR heartbeat for this label also carried status: "skipped-quota",
    # carry its counter forward +1; any other prior status (including a
    # missing/unreadable prior heartbeat, or a prior "skipped-throttle" —
    # #5922: a throttle night never extends the quota streak) resets the
    # streak to 1 — this run is the first skip of a fresh streak.
    python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, sys, datetime
path, job, started, cadence = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
prior_streak = 0
try:
    with open(path, encoding="utf-8") as fh:
        prior = json.load(fh)
    if prior.get("status") == "skipped-quota":
        raw = prior.get("consecutive_quota_skips")
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            prior_streak = raw
except Exception:
    prior_streak = 0
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 70,
        "cadence": cadence,
        "status": "skipped-quota",
        "consecutive_quota_skips": prior_streak + 1,
        "summary": "WRAPPER: skipped — quota pre-flight detected an active session/weekly limit; main run not dispatched this slot.",
    }, fh)
PYEOF
    _wrapper_say_heartbeat "skipped — quota pre-flight detected an active session/weekly limit; main run not dispatched this slot."
    exit 70
fi

if [ "$THROTTLE_HIT" -eq 1 ]; then
    # #5922: the server-throttle skip is its own status, `skipped-throttle`,
    # NEVER `skipped-quota` -- see the two-way split above. Exit 70 is shared
    # with the quota-skip path (both are "main run not dispatched this slot,
    # for a sanctioned reason" -- this script's own header comment documents
    # 70 as covering both a session/weekly-limit skip AND a throttle skip);
    # the `status` field, not the exit code, is what every downstream
    # consumer (heartbeat_audit.py, daily_sweep.txt) actually keys on.
    #
    # consecutive_throttle_skips: same carry-forward mechanics as
    # consecutive_quota_skips above, kept as an entirely separate counter so a
    # throttle streak can never be misread as a quota streak or vice versa.
    # #5922 fix round, BLOCKER 1: heartbeat_audit.py's check #9 DOES key
    # on this counter -- three or more consecutive "skipped-throttle" runs
    # flag job-failed, same threshold as the quota streak, with the reason
    # string "server-side throttle, not quota; check concurrent load
    # (runtime CLAUDE.md §9)" (a long, unbroken throttle streak is evidence
    # of sustained concurrent load against the account, not quota
    # exhaustion, and previously alerted nobody at any length).
    python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, sys, datetime
path, job, started, cadence = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
prior_streak = 0
try:
    with open(path, encoding="utf-8") as fh:
        prior = json.load(fh)
    if prior.get("status") == "skipped-throttle":
        raw = prior.get("consecutive_throttle_skips")
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            prior_streak = raw
except Exception:
    prior_streak = 0
with open(path, "w", encoding="utf-8") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": now,
        "exit": 70,
        "cadence": cadence,
        "status": "skipped-throttle",
        "consecutive_throttle_skips": prior_streak + 1,
        "summary": "WRAPPER: skipped — quota pre-flight detected a server-side rate limit (not the account's own usage limit); main run not dispatched this slot.",
    }, fh)
PYEOF
    _wrapper_say_heartbeat "skipped — quota pre-flight detected a server-side rate limit (not the account's own usage limit); main run not dispatched this slot."
    exit 70
fi
# --- end quota pre-flight --------------------------------------------------

# Hard hang backstop, unchanged from the prior inline plists: SIGALRM after
# ALARM_SECONDS kills a genuinely wedged CLI process. This wrapper's own
# after-the-fact heartbeat check (below) is what makes an alarm-kill
# distinguishable from a session-limit death or a clean finish — alarm(2)
# itself is unchanged.
#
# Wheel jobs (GH #4767): the wrapper writes the START heartbeat (preamble step
# 3's exact shape, so a death before END leaves exactly this on disk) and
# exports what hooks/wheel_sink.py needs; WHEEL_SLUG is already exported by
# the plist or /wheel. START is written after the quota pre-flight because the
# pre-flight's streak logic reads the PRIOR heartbeat.
if [ -n "${WHEEL_SLUG:-}" ]; then
    python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, os, sys
hb_path, job, started, cadence = sys.argv[1:5]
# preamble step 3's exact shape; a death before END leaves exactly this on disk
data = {"job": job, "started_at": started, "finished_at": None, "exit": 1, "cadence": cadence,
        "summary": f"STARTED {started}"}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
    export OVERSIGHT_JOB_LABEL="$JOB_LABEL" OVERSIGHT_WRAPPER_START_ISO="$WRAPPER_START_ISO" \
           OVERSIGHT_CADENCE="$CADENCE_TEXT" OVERSIGHT_RUN_SCRATCH="$RUN_SCRATCH"
fi
if [ -n "${WHEEL_SLUG:-}" ]; then
    # The wheel's flag tail was already parsed into "$@" above (wheel launch context section,
    # BLOCKER B1 fix), immediately after the helper printed `launch` and the [ -s ] non-empty
    # check passed -- not re-read here, so a file deleted or truncated in the window between that
    # check and this exec cannot silently substitute an empty flag tail: "$@" is the one and only
    # parse of argv.txt for this run. Positional params $1-$4 were copied into
    # JOB_LABEL/PROMPT_FILE/... at the top; nothing below reads them. Re-assert the same shape one
    # more time immediately before the exec (defense in depth against anything upstream that might
    # someday reset "$@" without going through the fail-closed path above): a violation here fails
    # closed rather than exec'ing claude with an unrestricted flag tail.
    #
    # Non-blocking item (a) (trust re-review round 4): also require --disallowedTools to still be
    # present in "$@" at this exec-site re-check -- the same truncated-argv.txt shape that the
    # earlier check now catches must be caught here too, since this is the re-check that guards
    # against "$@" being reset between there and here.
    _has_disallowed_exec=0
    for _tok in "$@"; do
        if [ "$_tok" = "--disallowedTools" ]; then _has_disallowed_exec=1; break; fi
    done
    if [ "$#" -eq 0 ] || [ "$1" != "--add-dir" ] || [ "$_has_disallowed_exec" -ne 1 ]; then
        python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF' || true
import json, os, sys, datetime
hb_path, job, started, cadence = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data = {"job": job, "started_at": started, "finished_at": now, "exit": 79, "cadence": cadence,
        "status": "failed", "hard_stop": "launch-context-error",
        "summary": "WRAPPER: refused before launch — launch-context-error: argv tail lost its "
                   "--add-dir/--disallowedTools shape before exec; claude was not launched (fail closed, GH #4767)."}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
        _wrapper_say "refused before launch — launch-context-error: argv tail lost its --add-dir/--disallowedTools shape before exec; claude was not launched (fail closed, GH #4767)."
        exit 0
    fi
    # N5 (trust-architect, fix round): both kill-switch markers are checked ONCE, before the lock,
    # the launch-context helper and a quota pre-flight of up to 60s -- WRAPPER CONTEXT then tells
    # the session "both switches were absent, do not check them". A DISABLED marker created in
    # that window (by the operator, mid-run) previously still got a full launch. Re-check both
    # markers with the same dangling-symlink-safe test (`[ -e X ] || [ -L X ]`, N5) immediately
    # before the exec and write skipped-disabled instead of launching if either now exists.
    _WHEEL_DISABLED_RECHECK=""
    if [ -e "${HOME}/.claude/schedules/DISABLED" ] || [ -L "${HOME}/.claude/schedules/DISABLED" ]; then
        _WHEEL_DISABLED_RECHECK="global"
    elif [ -e "${HOME}/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG}" ] || [ -L "${HOME}/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG}" ]; then
        _WHEEL_DISABLED_RECHECK="per-job"
    fi
    if [ -n "$_WHEEL_DISABLED_RECHECK" ]; then
        python3 - "$HEARTBEAT_FILE" "$HEARTBEAT_DIR" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" "$_WHEEL_DISABLED_RECHECK" "$WHEEL_SLUG" <<'PYEOF' || true
import datetime, json, os, sys
hb_path, hb_dir, job, started, cadence, marker, slug = sys.argv[1:8]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
if marker == "global":
    with open(os.path.join(hb_dir, "_disabled_window.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"job": job, "skipped_at": now}) + "\n")
    hard_stop, what = "1", "kill switch ~/.claude/schedules/DISABLED is present"
else:
    hard_stop, what = "2", f"per-job disabled (~/.claude/schedules/DISABLED.wheel.{slug} is present)"
data = {"job": job, "started_at": started, "finished_at": now, "exit": 0, "cadence": cadence,
        "status": "skipped-disabled", "hard_stop": hard_stop,
        "summary": f"WRAPPER: skipped — {what} (created after the initial check, caught by the "
                   "pre-exec re-check, N5); claude was not launched (wrapper-enforced, GH #4767)."}
tmp = f"{hb_path}.tmp.{os.getpid()}"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh)
os.replace(tmp, hb_path)
PYEOF
        if [ "$_WHEEL_DISABLED_RECHECK" = "global" ]; then
            _wrapper_say "skipped-disabled (global) — ~/.claude/schedules/DISABLED is present (created after the initial check, N5); claude was not launched (wrapper-enforced kill switch, GH #4767)."
        else
            _wrapper_say "skipped-disabled (per-job) — ~/.claude/schedules/DISABLED.wheel.${WHEEL_SLUG} is present (created after the initial check, N5); claude was not launched (wrapper-enforced kill switch, GH #4767)."
        fi
        exit 0
    fi
    perl -e 'alarm shift; exec @ARGV' "$ALARM_SECONDS" "$CLAUDE_BIN" -p "$P" --model sonnet --permission-mode acceptEdits "$@"
else
    perl -e 'alarm shift; exec @ARGV' "$ALARM_SECONDS" "$CLAUDE_BIN" -p "$P" --model sonnet --permission-mode acceptEdits
fi
CLI_EXIT=$?

# --- Fail-fast verification: did the session's OWN END heartbeat land? ---
# A truthful END write is one where finished_at is a real, parseable UTC
# timestamp strictly AT/AFTER this wrapper's own start time (never trust
# stdout narrative, never trust exit code alone — a clean `claude -p` exit
# with a stale/absent heartbeat is exactly the #4825 shape: exit looked fine
# from launchd's perspective while the real write silently never happened).
python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$WRAPPER_START_EPOCH" "$CADENCE_TEXT" "$CLI_EXIT" <<'PYEOF'
import json, os, sys, datetime

hb_path, job, wrapper_start_iso, wrapper_start_epoch_s, cadence, cli_exit = sys.argv[1:7]
wrapper_start_epoch = float(wrapper_start_epoch_s)


def parse_epoch(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        norm = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return datetime.datetime.fromisoformat(norm).timestamp()
    except Exception:
        return None


ok = False
reason = "no heartbeat file found after process exit"
# WRAPPER_START_ISO is truncated to whole-second UTC and recorded BEFORE the
# CLI is even invoked, so a legitimate END write can (rarely) land in the
# same wall-clock second as the wrapper's own recorded start due to
# sub-second rounding — never earlier in real terms, just equal after
# truncation. A small tolerance avoids misclassifying that as a stale prior
# heartbeat; anything actually stale is off by hours/days, not seconds.
STALENESS_TOLERANCE_SEC = 5.0
try:
    with open(hb_path, encoding="utf-8") as fh:
        data = json.load(fh)
    finished_at = data.get("finished_at")
    finished_epoch = parse_epoch(finished_at)
    if finished_epoch is None:
        reason = f"finished_at is {finished_at!r} (null or unparseable) — END heartbeat never written"
    elif finished_epoch < wrapper_start_epoch - STALENESS_TOLERANCE_SEC:
        age_h = (wrapper_start_epoch - finished_epoch) / 3600.0
        reason = (
            f"finished_at={finished_at} predates this run's own start "
            f"({wrapper_start_iso}) by {age_h:.1f}h — a STALE heartbeat from a "
            "prior run, not this run's own END write"
        )
    else:
        ok = True
except FileNotFoundError:
    pass
except Exception as exc:
    reason = f"heartbeat file unreadable/malformed: {exc.__class__.__name__}: {exc}"

if ok:
    # BLOCKER 1 fix (fix round, THE ISSUE WHEEL plan): a SUCCESSFUL run's END
    # heartbeat is written by the SESSION per _preamble.txt step 5, which
    # carries no `status` key at all -- only this wrapper's own failure exit
    # paths write `status`. Left unfixed, `status: "ok"` is a state
    # production can never produce, so the second-slot skip below (which
    # keys on it) can never fire and would re-run the full wheel every
    # weeknight even after a clean 22:10 success.
    #
    # STAMP `status: "ok"` HERE, in this wrapper's own post-CLI verification
    # step, mirroring the existing prime_status atomic read-modify-write
    # further down this file (never a plain truncating write — this heartbeat
    # is already the ONE genuinely-good artifact this whole script exists to
    # protect). Gated on the heartbeat's OWN `exit` field being exactly 0 --
    # NOT merely "the write was truthful" -- because a session can write a
    # perfectly truthful END heartbeat that still reports failure
    # (_preamble.txt step 5: "exit: 0 ONLY if every step completed;
    # otherwise non-zero"). Stamping "ok" on a truthful-but-failed run would
    # let the second-slot skip suppress the very retry it exists to run --
    # exactly the #4825/F3 shape (a session that "succeeded" at writing its
    # own heartbeat while the actual job failed). A session that ALREADY
    # wrote its own `status` key (a future job prompt that adopts one) is
    # never overwritten -- this stamp only fills an ABSENT status, exactly
    # like prime_status's own "never invent, only fill" convention.
    try:
        with open(hb_path, encoding="utf-8") as fh:
            hb_data = json.load(fh)
        if isinstance(hb_data, dict) and "status" not in hb_data:
            exit_val = hb_data.get("exit")
            if isinstance(exit_val, int) and not isinstance(exit_val, bool) and exit_val == 0:
                hb_data["status"] = "ok"
                directory = os.path.dirname(hb_path) or "."
                tmp_path = os.path.join(directory, f".{os.path.basename(hb_path)}.tmp.{os.getpid()}")
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(hb_data, fh)
                os.replace(tmp_path, hb_path)
    except Exception:
        # Never let this advisory stamp abort the wrapper's own successful-
        # exit path -- the heartbeat the session itself wrote is already
        # genuinely good; a stamping failure here just means status stays
        # absent, which is the same conservative "cannot determine" shape
        # every other check in this file already degrades to.
        pass
    sys.exit(0)

# The session died (or silently skipped its own contract) without a truthful
# END write. Write the fail-fast diagnostic heartbeat ourselves so this job's
# true state (dead, not done) is visible immediately — not after a cadence
# window elapses. exit is the CLI's own real exit code so a human/heartbeat_audit
# reader can distinguish 142 (SIGALRM hang-kill) from any other death.
now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
summary = (
    f"WRAPPER: claude process exited (code={cli_exit}) without a truthful END "
    f"heartbeat — {reason}. Likely causes: Anthropic session/usage-limit "
    "exhaustion mid-run (check the job's .out.log tail for 'session limit'), "
    "the 7200s hang-kill (exit 142), or a crash. See "
    f"{os.path.expanduser('~')}/.claude/schedules/logs/{job}.out.log and .err.log for the real cause."
)
with open(hb_path, "w", encoding="utf-8") as fh:
    json.dump(
        {
            "job": job,
            "started_at": wrapper_start_iso,
            "finished_at": now_iso,
            "exit": int(cli_exit) if str(cli_exit).lstrip("-").isdigit() else 1,
            "cadence": cadence,
            "status": "failed",
            "summary": summary,
        },
        fh,
    )
print(summary, file=sys.stderr)
PYEOF

# #5055: stamp any resolvable relative artifact-path claim in the
# heartbeat's own summary to its absolute form (heartbeat_artifact_stamp.py).
# Runs as its OWN separate python3 call, strictly AFTER the heredoc above has
# finished all its own reads/writes (that heredoc's own truthful-path
# sys.exit(0) only exits ITSELF, never this wrapper). Stamping
# is a pure enhancement -- `|| true` on top of the module's own internal
# always-exit-0/never-raise contract means a stamp failure can never abort
# this wrapper (set -u, deliberately no set -e -- see the top of this file).
# `${PWD:-}`, never bare `$PWD`: under launchd, macOS TCC can deny this job's bash access to the
# plist's WorkingDirectory (`getcwd: cannot access parent directories: Operation not permitted`),
# and bash then never sets PWD at all. Bare `$PWD` under the `set -u` at the top of this file
# aborts the wrapper HERE, which is AFTER the fail-fast diagnostic heartbeat is written (the
# heredoc above) but
# BEFORE the final `exit 0` -- so bash exits 127 instead, violating the exit-code contract this
# file documents in its header (75 lock and 70 quota skip are the only sanctioned non-zero
# exits), polluting launchd's
# crash/retry accounting, and skipping the artifact stamp itself. It also emits a red-herring
# error line directly beneath the WRAPPER diagnostic, which misdirects whoever reads the log.
# It does NOT cause the stale-heartbeat condition that diagnostic reports -- verified by log
# ordering, the WRAPPER line precedes this one in every non-truncated occurrence; that is a
# separate, pre-existing failure (usually Anthropic usage-limit exhaustion mid-run).
# Measured 2026-09-16: 23 occurrences across 9 of the 11 scheduled jobs (counts decay -- these
# are rotating logs; prefer the magnitude over any tally). Degraded behavior with an empty
# workdir is honest, not wrong: heartbeat_artifact_stamp.py's resolve_claim() falls back to
# $HOME/.claude, and a claim it cannot resolve is SKIPPED (left un-stamped), never mis-stamped.
# This was the file's ONLY bare-$PWD use; every other variable here is already assigned
# in-script, positional-guarded, or `:-`-guarded.
python3 "$HOME/.claude/hooks/heartbeat_artifact_stamp.py" "$HEARTBEAT_FILE" "${PWD:-}" || true

# --- PRIME_STATUS typed heartbeat key (card 44 / GH #5569) -----------------
# MUST run HERE, after the CLI has exited — never before it. The session's own
# step-5 END heartbeat OVERWRITES this file wholesale (prompts/_preamble.txt
# step 5: "OVERWRITE the same file (do not append)"), so a key written by this
# wrapper BEFORE the CLI starts is destroyed by the session's own write and
# would be permanently invisible. Stamping after the CLI is the only placement
# where the key survives, and it mirrors heartbeat_artifact_stamp.py directly
# above: a pure post-hoc enhancement, `|| true`-guarded, that can never abort
# this wrapper (set -u, deliberately no set -e — see the top of this file). It also works
# when the session never ran at all: the key rides the fail-fast diagnostic
# heartbeat written above (test T6).
#
# Consumer: prompts/daily_sweep.txt step A reads this key alongside
# t9_stamp_write. A key with no consumer is dead telemetry, which is exactly
# the silent-skip failure mode this whole change exists to end.
#
# ATOMIC WRITE, mirroring heartbeat_artifact_stamp.py exactly (temp file in
# the SAME directory + os.replace). Unlike that module's own no-op-on-failure
# create case, this site is a read-modify-write of an ALREADY-GOOD heartbeat
# -- including the fail-fast WRAPPER: diagnostic this whole file exists to
# guarantee (#4825/#4791) -- so a plain truncating `open(..., "w")` here can
# leave a zero-length or partial heartbeat if the process dies between the
# truncate and the flush, destroying the one artifact this wrapper protects
# in exchange for adding an advisory key. Temp-then-replace makes that
# window a no-op: either the old file survives untouched, or the new one
# lands whole.
python3 - "$HEARTBEAT_FILE" "${PRIME_STATUS:-skipped}" <<'PYEOF' || true
import json, os, sys

hb_path, prime_status = sys.argv[1:3]
if prime_status not in ("ok", "failed", "skipped"):
    prime_status = "skipped"
try:
    with open(hb_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("heartbeat is not a JSON object")
except Exception:
    # No readable heartbeat to stamp. Never CREATE one here: a heartbeat this
    # wrapper invents would be indistinguishable from a real END write and
    # would mask the very death the fail-fast heredoc above exists to report.
    sys.exit(0)
data["prime_status"] = prime_status
directory = os.path.dirname(hb_path) or "."
tmp_path = os.path.join(directory, f".{os.path.basename(hb_path)}.tmp.{os.getpid()}")
try:
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp_path, hb_path)
except Exception:
    # Leave the original heartbeat byte-identical on any failure -- never
    # half-write over it.
    try:
        os.remove(tmp_path)
    except Exception:
        pass
    sys.exit(0)
PYEOF

# H3's lock_force_reclaimed: true stamp (when CSA_WHEEL_FORCE_UNLOCK=1 forced
# this run's acquisition) is NOT done here -- it is folded into the unified
# `_wrapper_exit_cleanup` EXIT trap, registered ONCE near the top of this
# script (before any lock acquisition is ever attempted), so it fires on
# EVERY exit path this script has (including the empty/unreadable-prompt-file
# early exit, which returns long before this point in the script), not just
# this one. See that trap's own header comment near the top of the file.

exit 0
