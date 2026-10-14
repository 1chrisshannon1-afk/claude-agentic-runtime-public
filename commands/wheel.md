---
description: Run THE ISSUE WHEEL on demand for a repo, outside its nightly cadence
argument-hint: [a repo slug — a non-"_"-prefixed top-level key of ~/.claude/knowledge/wheel_repos.json]
model: sonnet
---

Run THE ISSUE WHEEL (`com.oversight.wheel.<slug>`'s own job, `issue_wheel.txt`) right now, for the
repo named by `$ARGUMENTS`, instead of waiting for its nightly cadence. This exists for the same
reason `/sweep` exists for the daily oversight sweep: an operator or orchestrating session
sometimes needs the wheel's triage/fix/close pass NOW, not at 22:10.

**Resolve `<slug>`:** `$ARGUMENTS` must be exactly a top-level key of
`~/.claude/knowledge/wheel_repos.json` that does NOT start with `_` (each such key corresponds to
a repo whose own `.claude/oversight/manifest.json` was registered via `repo_manifest.py
register`; a `_`-prefixed key like `_comment` is metadata, never a real repo slug, and must be
excluded here). Resolution is performed by THIS step reading the file directly — no
`repo_manifest.py` subcommand validates a slug against `wheel_repos.json` today. Any other value
(empty, misspelled, extra tokens, a `_`-prefixed key, or a slug with no matching key) is a hard
stop — do not guess which repo was meant; report the invalid argument and exit without running
anything.

**Procedure, in order:**

1. **Kill-switch check, BEFORE anything else.** If `~/.claude/schedules/DISABLED` exists, or
   `~/.claude/schedules/DISABLED.wheel.<slug>` exists (0 bytes), stop here and report which
   marker fired — do not proceed to any later step, and do not run the wrapper at all. This
   mirrors the job's own HARD STOPS 1/2; an on-demand run is not exempt from either kill switch.
   The wrapper also enforces both kill switches itself (GH #4767); this pre-check only saves a launch.

2. **Look up `<slug>`'s config** in `~/.claude/knowledge/wheel_repos.json` — if `<slug>` has no
   matching top-level key, stop and report "unknown slug" rather than inventing a config.

3. **Locate and read `<slug>`'s plist**, `~/.claude/schedules/com.oversight.wheel.<slug>.plist` —
   this is where `$WHEEL_REPO` and every other `WHEEL_*` var this command needs actually live
   (`wheel_repos.json` deliberately holds only what a prose dossier cannot express mechanically,
   not the repo path or project identifiers). **If the plist does not exist yet, STOP here and
   report "THE ISSUE WHEEL is not yet installed for `<slug>` — its plist has not landed."** This
   is a real, currently-reachable state, not a hypothetical: the plists themselves land in later
   commits of this same rollout, so `/wheel` is expected to be unrunnable for a time after this
   command itself ships — do not treat a missing plist as an unexplained mid-procedure failure.

4. **Export each of `<slug>`'s plist env vars individually**, reading them from the plist file
   located in step 3 — an explicit enumerated `export` list, never a black-box "env block" copy:
   `WHEEL_REPO`, `WHEEL_SLUG`, `WHEEL_GH_REPO`, `WHEEL_PROJECT`, `WHEEL_PROJECT_OWNER`,
   `WHEEL_LEDGER_REL`, `WHEEL_RANKED_GLOB`, `WHEEL_LANE_CAP`,
   `WHEEL_TRIAGE_SEED_CAP`, and `WHEEL_FIX_ENABLED` / `WHEEL_CLOSE_ENABLED` at exactly their
   plist values (do not force these to `1` on an on-demand run just because a human asked for it —
   Agency's plist ships both `0` until its own probes land, and this command must not silently
   override that gate). `WHEEL_TRACKER_REL` is RETIRED as of 2026-09-20 and is no longer in either
   plist — the tracker HTML it named was deleted 2026-09-16; never export or pass it. If the caller
   named an explicit lane cap or seed cap as part of invoking
   this command (not merely `<slug>` in `$ARGUMENTS`), export that value instead of the plist's —
   otherwise use the plist's value unchanged. THEN `cd $WHEEL_REPO` (now exported) — every
   subsequent step in this procedure runs with that repo as cwd.

5. **Debounce check (H3): refuse a too-soon repeat on-demand invocation for this slug.** Read
   `~/.claude/schedules/heartbeats/manual-wheel-<slug>.json` (this slug's own on-demand heartbeat —
   never the nightly `com.oversight.wheel.<slug>.json` file, which this check is not about) if it
   exists. If its `finished_at` parses as a real UTC timestamp less than **30 minutes** old, stop
   here and report the debounce refusal (name the prior run's `finished_at` and how long until the
   window clears) — do not proceed to step 6, and do not run the wrapper. This is separate from,
   and in addition to, `run_oversight_job.sh`'s own concurrency lock (step 6 below): the lock stops
   two runs racing each other; this stops a clean, already-finished run from being immediately
   re-triggered by a human re-invoking `/wheel <slug>` moments later. **Explicit override:**
   `CSA_WHEEL_FORCE_UNLOCK=1` (the same named escape hatch `run_oversight_job.sh` honors for its own
   lock — see that script) also bypasses this debounce check when set for this invocation, so an
   operator who genuinely wants to retry immediately has exactly one lever to reach for, not two
   differently-named ones. A missing or unparseable heartbeat file is treated as "no recent run" —
   never a refusal.

6. **Run, on one line, exactly:**
   ```
   WHEEL_ONDEMAND=1 bash ~/.claude/schedules/run_oversight_job.sh manual-wheel-<slug> ~/.claude/schedules/prompts/issue_wheel.txt "on-demand" 10800
   ```
   If the caller set `CSA_WHEEL_FORCE_UNLOCK=1` to clear step 5's debounce above, export that same
   `CSA_WHEEL_FORCE_UNLOCK=1` into this invocation's own environment too (prepend it to the line
   above exactly as `WHEEL_ONDEMAND=1` is prepended) — the wrapper's own concurrency lock honors the
   identical variable, and a caller who explicitly asked to bypass the wait should not be blocked a
   second time by the lock this command's own debounce is layered in front of. The job-label
   argument is **`manual-wheel-<slug>`**, never `com.oversight.wheel.<slug>` — this
   is load-bearing, not a naming preference: `run_oversight_job.sh` derives the heartbeat filename
   solely from this argument, and `heartbeat_audit._is_manual()` recognizes the `manual-` PREFIX
   specifically, so using the real job label here would silently overwrite the NIGHTLY heartbeat
   file and mask a genuinely dead nightly run until its next cadence window. Same wrapper, same
   prompt, same exported `WHEEL_*` env as the nightly run. `WHEEL_ONDEMAND=1` is read directly by
   `issue_wheel.txt` itself (see that prompt's REPO / ENV RESOLUTION section) — when set, and only
   when the caller did NOT already override `WHEEL_LANE_CAP` in step 4 above, the job treats
   `WHEEL_LANE_CAP` as 2 for this run regardless of the plist's own value. `issue_wheel.txt` has no
   "already ran today" idempotence guard of any kind (unlike the retired SDW queue keeper), so
   `WHEEL_ONDEMAND=1` changes exactly this one thing — do not assume it does anything beyond
   what `issue_wheel.txt` itself documents.

7. **Relay findings via board-steward's rules** — one issue per root-cause cluster, never one
   issue per individual finding; destructive dispositions this run made are already governed by
   the STANDING CLOSE AUTHORIZATION named in full at the top of `issue_wheel.txt`'s P3 section,
   gated on both `gh_issue.sh`'s guards and gate 5, exactly as the nightly run is.

8. **Write a heartbeat entry** confirming this on-demand invocation ran, via Bash heredoc, at
   `~/.claude/schedules/heartbeats/manual-wheel-<slug>.json` — step 6's wrapper already does this
   as part of the job itself (the wrapper writes START; the session writes END through `hooks/wheel_sink.py`), so this step is a NO-OP by
   construction; do not write a second, competing heartbeat file. Read the wrapper's own exit
   status and heartbeat summary back to the operator/session that invoked this command rather than
   re-deriving a summary by hand. The wrapper also appends this run's line to
   `~/.claude/schedules/heartbeats/history/manual-wheel-<slug>.jsonl` (WS14-S1 1b, GH #4767), a
   file of its own, so an on-demand run never counts toward the nightly green-night streak
   (`hooks/wheel_history.py green_nights()`/`streak` CLI, WS14-S1 1c — see
   `docs/subsystems/oversight-wheel.md`, "Green nights and the streak CLI").

**Never**: push, PR, merge, or deploy as a side effect of this command — THE ISSUE WHEEL commits
locally and closes issues per its own standing authorization; it never touches outward gates, and
neither does this command. Session and model discipline: this command itself stays on the pinned
`sonnet` model above; every substantive judgment inside the wheel's own run happens via its own
named `Agent` dispatches, whose pins govern independently.
