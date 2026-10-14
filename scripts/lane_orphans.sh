#!/usr/bin/env bash
# lane_orphans.sh — READ-ONLY reconciliation of lane worktrees against the lane ledger.
#
# WHY THIS EXISTS
# ---------------
# Adoption master plan §7.4. `lane.sh` keeps the ledger honest for lanes it
# opens and reaps, but a session can die, a machine can reboot, and a worktree
# can be removed out from under its row. This reports the four divergence
# classes so an operator (never an unattended job) can decide what to do.
#
# THIS SCRIPT WRITES NOTHING, EVER. Not the ledger, not the worktrees, not a
# cache. That is the whole safety argument: a reconciler that can also remove
# things is one bug away from deleting unlanded work, which is precisely the
# failure `lane.sh reap`'s ancestry gate exists to prevent. `dead-owner` in
# particular is REPORTED, never auto-reaped -- a pid that is not live on this
# host says nothing about whether the worktree's CONTENT has landed.
#
# FINDING CLASSES
#   orphan-worktree  a `.claude/worktrees/issue-<n>-*` dir with no open/abandoned row
#   orphan-row       an open/abandoned row whose worktree is gone from disk
#   dead-owner       an open row whose owning pid is not live on this host
#   over-cap         more open (or abandoned) rows than the manifest's cap allows
#
# THE `^issue-[0-9]+-` ANCHOR IS LOAD-BEARING (§9 rule 3). CSA has 236 legacy,
# pre-lane checkouts under `.claude/worktrees/` with names like `wf_*` and
# `agent-*`. Matching loosely would report every one of them as an orphan and
# drown the real signal. Only a directory whose name is shaped like a lane, AND
# which the ledger fails to corroborate, is reported.
#
# EXIT: 0 = clean, 1 = findings, 2 = usage/environment error.
#
# ENV OVERRIDES (hermetic tests only)
#   LANE_DIR, CLAUDE_DIR — as in lane.sh

set -uo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
LANE_DIR="${LANE_DIR:-$CLAUDE_DIR/.lanes}"
LEDGER="$LANE_DIR/lanes.jsonl"
REPO_MANIFEST="${REPO_MANIFEST_PY:-$CLAUDE_DIR/scripts/repo_manifest.py}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  printf 'lane_orphans: not inside a git repository\n' >&2; exit 2; }

WT_DIR="$REPO_ROOT/.claude/worktrees"

max_open=""
max_abandoned=""
if [ -f "$REPO_ROOT/.claude/oversight/manifest.json" ]; then
  max_open="$(python3 "$REPO_MANIFEST" get lane.max_open --repo "$REPO_ROOT" --raw 2>/dev/null || true)"
  max_abandoned="$(python3 "$REPO_MANIFEST" get lane.max_abandoned --repo "$REPO_ROOT" --raw 2>/dev/null || true)"
fi

python3 - "$LEDGER" "$REPO_ROOT" "$WT_DIR" "${max_open:-}" "${max_abandoned:-}" <<'PY'
import json, os, re, sys

ledger, repo, wt_dir, max_open, max_abandoned = sys.argv[1:6]

# Last-event-wins over an append-only ledger, scoped to this repo.
last = {}
if os.path.exists(ledger):
    with open(ledger) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue  # a corrupt row is skipped, never fatal
            if row.get("repo") != repo:
                continue
            last[row.get("issue")] = row

live = {i: r for i, r in last.items() if r.get("event") in ("open", "abandoned")}

findings = []

# The anchor that keeps legacy non-lane checkouts out of the report.
LANE_DIR_RE = re.compile(r"^issue-([0-9]+)-")

on_disk = {}
if os.path.isdir(wt_dir):
    for name in sorted(os.listdir(wt_dir)):
        path = os.path.join(wt_dir, name)
        if not os.path.isdir(path):
            continue
        m = LANE_DIR_RE.match(name)
        if not m:
            continue  # legacy / non-lane checkout: not ours to judge
        on_disk[int(m.group(1))] = path

# orphan-worktree: lane-shaped dir, no corroborating row.
for issue, path in sorted(on_disk.items()):
    if issue not in live:
        findings.append(("orphan-worktree", f"#{issue} {path} has no open/abandoned ledger row"))

# orphan-row: row says it exists, disk says otherwise.
for issue, row in sorted(live.items(), key=lambda kv: (kv[0] is None, kv[0])):
    wt = row.get("worktree") or ""
    if not wt or not os.path.isdir(wt):
        findings.append(("orphan-row", f"#{issue} row says {wt or '<no path>'} but it is not on disk"))

# dead-owner: REPORTED ONLY. Never a reason to remove anything.
import socket
host = socket.gethostname()
for issue, row in sorted(live.items(), key=lambda kv: (kv[0] is None, kv[0])):
    if row.get("event") != "open":
        continue
    if row.get("host") != host:
        continue  # another machine's pid namespace; unknowable from here
    pid = row.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        # NULL pid = "liveness genuinely unknown" (lane.sh writes null whenever
        # CLAUDE_PID is unresolvable, rather than a knowably-dead fallback).
        # Fail OPEN: an unknown owner is never reported as a dead one.
        continue
    alive = True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        alive = False
    except PermissionError:
        alive = True  # exists, owned by someone else
    except Exception:
        alive = True  # unknowable -> assume alive, never report a false death
    if not alive:
        findings.append((
            "dead-owner",
            f"#{issue} owning pid {pid} is not live on {host}; "
            f"worktree {row.get('worktree')} is REPORTED, not reaped",
        ))

# over-cap.
def _int(v):
    try:
        return int(v)
    except Exception:
        return None

n_open = sum(1 for r in live.values() if r.get("event") == "open")
n_aband = sum(1 for r in live.values() if r.get("event") == "abandoned")
mo, ma = _int(max_open), _int(max_abandoned)
if mo is not None and n_open > mo:
    findings.append(("over-cap", f"{n_open} open lanes exceeds lane.max_open={mo}"))
if ma is not None and n_aband > ma:
    findings.append(("over-cap", f"{n_aband} abandoned lanes exceeds lane.max_abandoned={ma}"))

if not findings:
    print(f"lane_orphans: clean ({n_open} open, {n_aband} abandoned, {len(on_disk)} lane worktrees on disk)")
    sys.exit(0)

for kind, msg in findings:
    print(f"lane_orphans: {kind}: {msg}")
print(f"lane_orphans: {len(findings)} finding(s); this script changed nothing.")
sys.exit(1)
PY
