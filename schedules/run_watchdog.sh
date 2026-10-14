#!/bin/bash
# run_watchdog.sh — THE ISSUE WHEEL hardening plan, commit #1 (H1): an
# external liveness supervisor for the oversight wheel's own scheduled jobs.
#
# WHY THIS EXISTS (the plan's own organizing sentence): "The wheel may run
# unattended when a run that dies, degrades, or is rate-limited produces a
# signal that reaches the operator without any wheel-owned process being
# alive to send it." Before this script existed, `heartbeat_audit.py` ran
# only as an embedded pre-step inside a session that was already firing
# (the daily job's pre-step C, or `/sweep`'s fixed pre-steps) — so if EVERY
# launchd job silently failed to fire at all, no session would ever run the
# audit in the first place, and nothing would notice. This script is the
# thing outside that failure domain: a pure Python/shell process, no `claude`
# CLI invocation anywhere in it, no LLM session in the loop at all — a
# watchdog that itself depended on a live session would not be outside the
# thing it's supervising (see the plan's D-5).
#
# KILL-SWITCH: checked FIRST, before anything else — mirrors every other
# oversight job's own `_preamble.txt` step 1 convention exactly. If
# `~/.claude/schedules/DISABLED` exists, this script appends one shared-
# marker line to `heartbeats/_disabled_window.jsonl` (never a per-job
# heartbeat of its own for that run) and exits 0 without running
# heartbeat_audit.py or escalating.
#
# WHAT IT DOES: runs heartbeat_audit.py (the mechanical, non-LLM liveness
# cross-check already used by the daily job and /sweep) and escalates on
# the five finding classes that are actually about "is a job alive":
#   - silent-job            (a loaded job's own calendar rule says it was
#                             due, and it never wrote a heartbeat)
#   - loaded-never-fired    (the coarser, cadence-text-based sibling of the
#                             same class)
#   - expected-but-unloaded (H1's own new check: a table row whose
#                             expected_state is "loaded" but the label is
#                             absent from `launchctl list` entirely — the
#                             case neither of the other two can see, since
#                             both require the job to already BE loaded)
#   - job-failed            (THE ISSUE WHEEL plan, WS1-B.2: a job that RAN
#                             and reported failure — structurally distinct
#                             from "never fired"; see heartbeat_audit.py's
#                             own check #9 docstring)
#   - unexpected-loaded     (THE ISSUE WHEEL plan, WS1-B.2: the mirror of
#                             expected-but-unloaded — a table row whose
#                             expected_state is NOT "loaded" but the label
#                             IS present in `launchctl list` anyway)
# — PLUS a sixth, distinct class: heartbeat_audit.py itself failing to run
# to completion (AUDIT_EXIT != 0 — its own main() never raises and always
# returns 0, so a non-zero exit here means something failed OUTSIDE that
# try/except: the script is missing, python3 itself is broken, a
# module-load error fired before main() ran). That is a liveness failure
# of the watchdog's own audit step, and reading it as "0 findings" (the
# pre-fix behavior) would silently defeat the one job this script exists
# to do — so it escalates too, under a distinct "watchdog-audit-failed"
# reason, never folded into the clean branch.
# The other finding classes heartbeat_audit.py reports (unexpected-
# heartbeat, missing-keys/bad-type/bad-value/bad-timestamp-format,
# timestamp-divergence/heartbeat-older-than-log, relative-artifact-claim,
# wheel-grant-contradiction — WS14-S1 item 1c, GH #4767: a genuinely
# granted wheel tool reporting itself "unavailable" — report-only, since it
# names a session-side bug worth a human's later look, not a job that
# stopped running)
# stay visible in its own report output (still read by the daily job's own
# pre-step, unchanged) but never trigger THIS script's own notify — a
# watchdog that escalated on "any finding" would alarm on day one from
# pre-existing noise the operator has no reason to act on, which is exactly
# how a real alarm gets ignored.
#
# NOTIFICATION: a local macOS alert via `osascript` (see the plan's D-5 —
# `PushNotification` is an agent-tool with no LLM-free call path, so it is
# not available to this pure-supervisor process; osascript is the chosen
# baseline for the initial rung-2 landing — zero new integration surface,
# zero new failure mode to harden, at the real, stated cost that it only
# fires while the operator's Mac is awake and logged in nearby).
#
# HEARTBEAT: this script writes its OWN heartbeat
# (schedules/heartbeats/com.oversight.watchdog.json), START then END,
# mirroring every other oversight job's own contract (_preamble.txt step 5)
# even though this script has no LLM session — a heartbeat is what lets
# heartbeat_audit.py's OWN checks (stale-start, dangling-heartbeat, the
# unexpected-heartbeat check to keep the watchdog from alarming on itself)
# see the watchdog exactly like any other job. oversight_install.md's §2
# table carries this job's own row (expected_state: loaded) for that reason.
#
# PROCESS exit code: always 0 — same convention as heartbeat_audit.py and
# run_oversight_job.sh. A launchd job's own exit code has no consumer here.
# The HEARTBEAT's own `exit` field is different and IS meaningful (fixed
# by this commit, B1): it carries 1 on either an escalated liveness finding
# or a watchdog-audit-failed total failure, 0 on a genuinely clean run — so
# the daily job's own heartbeat audit (§3's "non-zero exit in any heartbeat"
# contract) can see a failed watchdog run even if the osascript alert never
# reached anyone (Mac asleep, no desktop session).
#
# Escape hatch: CSA_WATCHDOG_SKIP_NOTIFY=1 suppresses the osascript call
# (still writes the heartbeat, still prints findings) — for local testing
# / a machine with no active desktop session, never a standing production
# posture.

set -u  # deliberately NOT -e — see run_oversight_job.sh's own rationale:
        # every step below must run even if a prior one fails, so the
        # heartbeat write is never skipped.

JOB_LABEL="com.oversight.watchdog"
HEARTBEAT_DIR="${HOME}/.claude/schedules/heartbeats"
HEARTBEAT_FILE="${HEARTBEAT_DIR}/${JOB_LABEL}.json"
DISABLED_MARKER="${HOME}/.claude/schedules/DISABLED"
DISABLED_WINDOW_LOG="${HEARTBEAT_DIR}/_disabled_window.jsonl"
CADENCE_TEXT="08:10 daily"
HEARTBEAT_AUDIT_PY="${HOME}/.claude/hooks/heartbeat_audit.py"

mkdir -p "$HEARTBEAT_DIR"

# KILL-SWITCH — mirrors _preamble.txt step 1's own convention exactly (every
# other oversight job's shell-adjacent gate): if the wheel-wide DISABLED
# marker exists, append one shared-marker line (never a per-job heartbeat —
# heartbeat_audit.py's *.json glob ignores a leading-underscore file) and
# exit clean, WITHOUT running heartbeat_audit.py or escalating. Without this
# check the watchdog silently falsified oversight_install.md §4's own claim
# that "every job checks it first and exits silently" (B2).
if [ -e "$DISABLED_MARKER" ]; then
    SKIP_ISO=$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')
    python3 - "$DISABLED_WINDOW_LOG" "$JOB_LABEL" "$SKIP_ISO" <<'PYEOF'
import json, sys
path, job, skipped_at = sys.argv[1:4]
with open(path, "a") as fh:
    fh.write(json.dumps({"job": job, "skipped_at": skipped_at}) + "\n")
PYEOF
    exit 0
fi

WRAPPER_START_ISO=$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')

# START heartbeat — mirrors _preamble.txt step 3's own shape (finished_at
# null, summary "STARTED ...") so heartbeat_audit.py's in-flight exemptions
# (and its own stale-start check, should this script itself ever hang) apply
# to the watchdog exactly like any other job.
python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$CADENCE_TEXT" <<'PYEOF'
import json, sys
path, job, started, cadence = sys.argv[1:5]
with open(path, "w") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": None,
        "exit": 1,
        "cadence": cadence,
        "summary": f"STARTED {started}",
    }, fh)
PYEOF

# Run heartbeat_audit.py and capture its full stdout — one violation per
# line, plus a trailing "heartbeat_audit: N violation(s)" summary line
# (heartbeat_audit.py's own main(), never raises, always exits 0 — its
# in-body try/except catches everything it can throw and reports a
# "heartbeat-audit-crashed: ..." violation LINE instead of a non-zero exit).
# A non-zero AUDIT_EXIT therefore means something OUTSIDE that try/except
# failed entirely — the file is missing, python3 itself is broken, a
# module-load-time error fired before main() ever ran — i.e. the audit did
# not run at all, not that it ran and found nothing. Treating that as "0
# findings" would silently defeat the one job this script exists to do
# (B1) — so it is its own escalation class below, never folded into the
# clean branch.
AUDIT_OUTPUT=$(python3 "$HEARTBEAT_AUDIT_PY" 2>&1)
AUDIT_EXIT=$?

# Scope escalation to exactly the five liveness-class finding prefixes —
# never "any finding" (see this file's own header comment for why) — plus
# a total AUDIT_EXIT failure, which is a liveness failure of the watchdog's
# own audit step and must escalate regardless of what (if anything) got
# printed to stdout/stderr before the failure. `job-failed` and
# `unexpected-loaded` (THE ISSUE WHEEL plan, WS1-B.2 / Phase B item 2) added
# alongside the original three: `job-failed` is a job that RAN and reported
# failure (structurally distinct from "never fired" — see
# heartbeat_audit.py's own check #9 docstring for the exact fixture this
# closes, F3); `unexpected-loaded` is the mirror of `expected-but-unloaded`
# in the opposite direction (a label the table says should NOT be loaded
# that launchctl shows loaded anyway).
ESCALATE_LINES=$(printf '%s\n' "$AUDIT_OUTPUT" | grep -E '^(silent-job|loaded-never-fired|expected-but-unloaded|job-failed|unexpected-loaded):' || true)

NOW_ISO=$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')

if [ "$AUDIT_EXIT" -ne 0 ]; then
    WATCHDOG_EXIT=1
    SUMMARY="WATCHDOG: watchdog-audit-failed — heartbeat_audit.py exited ${AUDIT_EXIT} (did not run to completion); output: $(printf '%s' "$AUDIT_OUTPUT" | tr '\n' ' ' | cut -c1-300)"

    if [ "${CSA_WATCHDOG_SKIP_NOTIFY:-0}" != "1" ]; then
        NOTIFY_TEXT=$(printf '%s' "$AUDIT_OUTPUT" | tr '\n' ' ' | cut -c1-500)
        osascript -e "display notification \"${NOTIFY_TEXT//\"/\\\"}\" with title \"THE ISSUE WHEEL watchdog\" subtitle \"heartbeat_audit.py failed (exit ${AUDIT_EXIT})\"" >/dev/null 2>&1 || true
    fi
elif [ -n "$ESCALATE_LINES" ]; then
    WATCHDOG_EXIT=1
    ESCALATE_COUNT=$(printf '%s\n' "$ESCALATE_LINES" | grep -c . || true)
    SUMMARY="WATCHDOG: ${ESCALATE_COUNT} liveness finding(s) — $(printf '%s' "$ESCALATE_LINES" | head -1)"

    if [ "${CSA_WATCHDOG_SKIP_NOTIFY:-0}" != "1" ]; then
        NOTIFY_TEXT=$(printf '%s' "$ESCALATE_LINES" | head -3 | tr '\n' ' ' | cut -c1-500)
        osascript -e "display notification \"${NOTIFY_TEXT//\"/\\\"}\" with title \"THE ISSUE WHEEL watchdog\" subtitle \"${ESCALATE_COUNT} liveness finding(s)\"" >/dev/null 2>&1 || true
    fi
else
    WATCHDOG_EXIT=0
    SUMMARY="WATCHDOG: 0 liveness findings (heartbeat_audit reported ${AUDIT_EXIT} exit, full output logged)"
fi

# END heartbeat — overwrites the START write above, same file, same
# convention as every other oversight job. `exit` carries WATCHDOG_EXIT
# (1 for either an escalated liveness finding OR a total heartbeat_audit.py
# failure, 0 for a genuinely clean run) rather than a hardcoded 0, so the
# heartbeat itself — not just the osascript alert — truthfully reflects a
# failed run; a stale/absent osascript delivery (Mac asleep, no desktop
# session) still leaves the daily job's own heartbeat audit able to see a
# non-zero exit here and read the log tail for why (§3's "non-zero exit in
# any heartbeat" contract, same as every other oversight job).
python3 - "$HEARTBEAT_FILE" "$JOB_LABEL" "$WRAPPER_START_ISO" "$NOW_ISO" "$CADENCE_TEXT" "$SUMMARY" "$WATCHDOG_EXIT" <<'PYEOF'
import json, sys
path, job, started, finished, cadence, summary, exit_code = sys.argv[1:8]
with open(path, "w") as fh:
    json.dump({
        "job": job,
        "started_at": started,
        "finished_at": finished,
        "exit": int(exit_code),
        "cadence": cadence,
        "summary": summary,
    }, fh)
PYEOF

printf '%s\n' "$AUDIT_OUTPUT"
printf '%s\n' "$SUMMARY"

# The launchd job's own exit code still has no consumer (see header comment)
# — the heartbeat's `exit` field above is the real signal now, not this
# process's exit status, so this stays 0 deliberately (a non-zero exit here
# would just make launchd log a spurious "job failed" with no reader).
exit 0
