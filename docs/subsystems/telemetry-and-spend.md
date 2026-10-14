# Telemetry & Spend

*Summary/orienting doc. The canonical, detailed reference is
[`~/.claude/telemetry/README.md`](../../telemetry/README.md) — read that in full for the record
schema, cost-resolution algorithm, and CLI. This page orients and points there.*

## What `telemetry/` tracks

`~/.claude/telemetry/` holds repo-agnostic data for **self-correcting agent loops** — any pipeline
where finders raise findings, a consolidator dedups/rules on them, a verifier checks them, and fixes
land or don't. It is data + documentation only; the library and CLI that read/write/validate it live
at `~/.claude/hooks/cycle_telemetry.py`.

```
~/.claude/telemetry/
  README.md              full schema + algorithm doc
  schema.json             formal JSON-Schema contract, for non-Python tooling
  pricing.json             operator-editable $/token table, per model, per bucket
  cycle_log.html           the real, generated dashboard (render_cycle_log.py's DEFAULT_OUTPUT;
                           git-ignored via `telemetry/*` — not source, regenerated from cycle
                           records; not committed)
  loop_log.html            compatibility symlink -> cycle_log.html (not a second generated file)
  fixtures/
    sample_cycle_record.json   one labelled reference sample (never read by aggregate reports)
  cycles/
    <system>/<cycle_id>.json   real cycle records, one file per run — populated at runtime only
```

One **cycle record** is one JSON object per loop run: `dispatches[]` (per-agent bookkeeping),
`calibration` (planted-defect catch/miss tracking), `findings[]` (each with `claim_symptom`,
`claim_cause`, `consolidator_decision`, `verifier_verdict`), `cost`, and — as of schema v2 — ten
optional top-level arrays: nine built 2026-08-28 (`runs[]`, `reviews[]`, `changes[]`,
`decisions[]`, `issues_filed[]`, `evidence[]`, `corrections[]`, `verdicts[]`, `stages[]`) that
close specific gaps a real operator audit found (e.g. "no review record at all," "retractions were
free text"), plus a tenth, `calibration_runs[]` — the GRID form of `calibration` (many plant AND
clean-control rows in one record), added a day later (2026-08-29, GH #4648) under the same
purely-additive contract. Every level is a closed shape — an unknown key, wrong type, or non-finite number is a
validation error, never silently accepted. The single most important derived metric is
`cause_precision` (of findings the verifier judged, what fraction had the *stated root cause* upheld,
not just the symptom) — in the first real run measured this way, finders were right about the
symptom 8/9 times but right about the root cause only 1/9, a gap invisible to any metric checking
only "was something actually wrong." Full metric definitions and the cost-resolution algorithm
(`resolve_cost()`'s four-signal correspondence check against `~/.claude/.agent_budget/spend.jsonl`)
are in the README, not repeated here.

## What `churn_report.py` answers

`~/.claude/hooks/churn_report.py` is the **"is this system healthy" oracle** — a pure reader (no LLM
call, no ledger write, no side effect) that renders seven metrics from the runtime's own ledgers:

1. **Plan-review rounds per plan, with plateau detection** (lifetime — never windowed by `--days`).
2. **Real denials per day, by reason** — filtered to actual `would-block` decisions from an
   allowlisted set of gate hooks, not a naive count of every log line (a naive count was found to be
   ~13x too high on one real day: 1,040 log lines, 81 real denials).
3. **Churn-flagged and contested-paths per day.**
4. **Code-review catch rate**, split by era — the current pre-commit-gate (`precommit:`-keyed)
   ledger entries as the headline number, legacy sha-keyed entries shown separately beneath (lifetime
   metric, same reasoning as #1: a review either happened or it didn't).
5–6. **Spend by agent/model/day**, and join-bug/reap findings — derived purely by reading
   `spend.jsonl`'s own `reaped`/`unreleased`/`late` fields (a non-zero `stopped-unjoined` count
   means a `SubagentStop` record never found a matching claim). The three-event join those fields
   are the byproduct of (`claims.jsonl` ↔ `stops.jsonl` ↔ `spend.jsonl`) happens upstream, in
   `agent_budget.py` (verify: `grep -n "claims.jsonl" hooks/churn_report.py` → no hits;
   `hooks/agent_budget.py` owns it, e.g. its `CLAIMS_NAME`/`STOPS_NAME` constants and
   `reap_stale()`/`handle_completed()`) — `churn_report.py` never reads `claims.jsonl` or
   `stops.jsonl` itself, only the already-joined `spend.jsonl`.
7. **Review-round convergence** — reads `round=`/`prev=`/`warm=` telemetry `record_review.py` already
   writes onto `last_reviewed` entries: a rounds-per-boundary histogram (max `round=` per
   `prev=`-linked chain, chain identity scoped by `(repo, key)` — never key alone, since the same
   digest key can legitimately recur across different repos), a warm-round distribution plus the
   count of chains that hit the 2-consecutive-warm cap and were followed by a cold round, and a count
   of `warm-cap-exceeded` refusals (`record_review.py`'s own refusal branch, logged to the same
   enforcement ledger metrics 2/3 read). Below 20 warm rows in the window it renders raw counts with
   an explicit `"n=<x>, not yet interpretable"` marker, never a percentage.

A missing ledger reports `ABSENT` for the metrics it feeds (never a false zero); a ledger that exists
but couldn't be fully read reports `DEGRADED`. Run it as:

```
python3 ~/.claude/hooks/churn_report.py --days 7 [--json]
```

This is the module `agentic-systems-architect` treats as its spend/churn oracle during a monthly
audit — it answers "is the review discipline actually catching things, and what is all this
review/enforcement machinery costing," from real ledger data rather than impression.

## `daily_spend_rollup.py`, `spend_attribution.py`, and `cycle_budget.py`

Three more `hooks/` modules read/extend the spend ledger, distinct from the two documented above:

- **`hooks/daily_spend_rollup.py`** (landed `01cd8cd`) closes a retention gap: `spend.jsonl` itself
  only retains ~5-6 days of rows (nothing rotates it to a longer history), so no genuine 30-day
  cost series is otherwise possible. Wired as **pre-step D of the daily oversight job**
  (`schedules/prompts/daily_sweep.txt`) and of `/sweep` (`commands/sweep.md`): once a day it
  aggregates the PRIOR UTC calendar day's `spend.jsonl` rows by `(agent_type, model)` (dispatch
  count + total tokens each, deduped via the same `tool_use_id`-group rule `churn_report.py`
  uses) and appends exactly one JSON line to a separate, append-only, never-rotated file,
  `~/.claude/.agent_budget/daily_rollup.jsonl` — the series accumulates day over day even as
  `spend.jsonl` keeps rolling off. Idempotent (a rerun for an already-recorded date is a clean
  no-op, `already-recorded`); a non-zero exit is a genuine read/write failure, never
  `spend.jsonl` simply not existing yet. **Since 2026-09-01 (F1, agentic-systems-architect audit)
  every non-dry-run invocation ALSO runs `spend_attribution.py`'s recovery** (see below) via
  `run_attribution_compaction()` — this is the scheduled job that closes spend_attribution.py's
  own "built but not wired" gap; a compaction failure is reported but never fails the rollup
  append's own exit code (best-effort, never load-bearing).
- **`hooks/spend_attribution.py`** resolves `agent_type`/`model` identity for `spend.jsonl` rows
  that would otherwise be unpriceable (`model: null`, or a generic `agent_type` like
  `"workflow-subagent"`), by cross-referencing Claude Code's own workflow-dispatch `.output`
  metadata (matched on `agent_id`). **As of 2026-09-01 it IS wired into a scheduled job's hot
  path**: `daily_spend_rollup.py`'s daily invocation (pre-step D above) runs its `enrich --out
  <sidecar> --rebuild-index` CLI path once per day, both refreshing its own identity-index cache
  (closing the staleness gap its own module docstring used to call out) and writing the CURRENT
  spend.jsonl window's recovered identities to `~/.claude/.agent_budget/spend_enriched.jsonl` —
  a read-only sidecar, never a mutation of `spend.jsonl` itself (see `enrich_rows()`'s own
  PROVENANCE CONTRACT: it always returns new dicts). The sidecar reflects only the CURRENT
  spend.jsonl window (whatever's on disk when the daily job runs) — it is deliberately NOT
  append-only itself; `spend.jsonl`'s own ~5-6 day retention already sets the ceiling on how much
  history is ever recoverable, and the sidecar tracking that same ceiling (rather than
  accumulating a longer independent history) is the intended behavior, not a gap to close later.
- **`hooks/cycle_budget.py`** is the **synchronous, in-cycle spend guard** for an unattended agent
  loop (built after the loop's first real cycle, #4498, burned budget with no mechanical
  brake): a pure consumer of `spend.jsonl` that has the shape a dispatcher *would* call before
  every additional spawn, in-process, to stop a runaway cycle before it exhausts its budget —
  built, tested, and correct, but not yet wired into any live caller (`hooks/cycle_budget.py:17-22`)
  — distinct from `churn_report.py`'s after-the-fact trend reporting, which can only notice an
  overrun the next day.

## `audit_review_attribution.py`

`~/.claude/hooks/audit_review_attribution.py` is a **pure reader** (no LLM call, no ledger write, no
side effect of any kind — the same contract as `churn_report.py`) that joins the review ledger
(`~/.claude/.review_state/last_reviewed`) against the dispatch-lease ledger
(`~/.claude/.agent_budget/spend.jsonl`) to answer: "for every `clean` review entry that carries a
compound `reviewer=<type>#<agent_id>#<tool_use_id>` identity, does a real, reviewer-typed
(`code-reviewer`/`trust-architect`) `spend.jsonl` row corroborate it within `--window-seconds`
(default 1800s)?" A `clean` entry is flagged:

- `no-identity` — carries no compound identity at all (legacy entries, or a `--clean` call that
  never supplied `--reviewer-agent-id`/`--reviewer-tool-use-id`).
- `unmatched` — carries an identity, but no corroborating `spend.jsonl` row was found in the window.
- `reused` — its `(agent_id, tool_use_id)` pair is also cited by at least one OTHER LIVE entry. A
  real review dispatch is used exactly once, so a repeated citation is the cheapest possible forgery
  (copy one real reviewer row's identity into a second `clean` entry); this overrides whatever
  `matched`/`unmatched` verdict the join produced for every entry sharing the pair. **CAVEAT (added
  2026-09-09, #5133 Blocker 1(a) — "the reused bucket catches the cheapest forgery" is no
  longer unconditionally true without the qualifier below):** a `superseded` entry's pair is
  EXCLUDED from this check only when it is byte-identical to its successor's own pair (see
  `superseded` below) — a `--correct-identity` correction that moves an entry's pair to a SECOND
  real, corroborable pair keeps the ORIGINAL pair bound to this check specifically so a forger
  cannot free a genuinely-reviewed pair by "correcting" it away and then citing the freed pair in
  an unrelated, never-reviewed boundary. The released pair itself gets reclassified from
  `superseded` to `reused` the moment anything else cites it.
- `superseded` — added 2026-09-09, #5133: a `clean` entry that is NOT the last entry on record
  for its exact `(repo, key)` pair (a `--correct-identity` correction, or any other later
  recording for the same key, appended a newer line afterward). NOT flagged by default — it is
  dead history no real ledger consumer (`precommit_review_gate.decide()`, `head_review_reviewer_identity`,
  `find_clean_precommit_entry_for_paths`) ever reads again, not a permanent, forgery-shaped
  anomaly — UNLESS its own `(agent_id, tool_use_id)` pair differs from its successor's (the pair
  was genuinely RELEASED, not merely re-typed byte-identically), in which case it is reclassified
  to `reused` per the caveat above the moment that pair is cited elsewhere.

An entry with a matching row whose identity is cited by exactly one `clean` entry is `matched` and
not flagged. Run it as:

```
python3 ~/.claude/hooks/audit_review_attribution.py [--window-seconds N] [--only unmatched|reused|no-identity|superseded] [--json]
```

`--only superseded` is a genuinely different shape from the other three categories: since a
`superseded` entry is by design never a member of `flagged`, this option enumerates the full
`results` list's superseded rows instead of narrowing `flagged` (which would always yield an empty
list) — the mechanism #5133's own review flagged as "invisible-by-construction" before this
fix (`corrects_from=`/`corrected_at=` were parsed but rendered nowhere, and `--only superseded`
simply exited 2 as an unrecognized value).

The text table caps at 10 flagged entries (mirroring `churn_report.py`'s own render caps); `--only`
narrows the table (and the `--json` output) to one flagged category so the actionable
`unmatched`/`reused` signal is not buried under legacy `no-identity` noise. Wired as **pre-step E of
the daily oversight job** (`schedules/prompts/daily_sweep.txt`) and of `/sweep` (`commands/sweep.md`)
— report-only, same posture as `churn_report.py`/`model_pin_parity.py`: it never blocks and a
non-zero exit means only a malformed CLI invocation, never a finding count.

**Two limitations, both load-bearing, neither solved by this module (2026-08-30 trust-architect
review):**

1. **Circularity.** Both `agent_id` and `tool_use_id` are self-reported by whoever calls
   `record_review.py`, and the only place in this codebase that exposes a real, obtainable pair to
   cite is `spend.jsonl` itself — the exact ledger this audit joins against (no env var or other
   surface exposes an orchestrator's own dispatch identity anywhere in this codebase). A session with
   ordinary read access to `spend.jsonl` (every session has this) can copy any real reviewer row's
   identity into a `--clean` recording it never earned, and that recording shows `matched` — proven
   directly by forging two such entries. So a `matched` verdict proves a *citable* dispatch existed,
   not that it reviewed *this* diff. This closes the audit gap only against casual/accidental
   mismatches, never against a deliberate forger with ordinary ledger read access. The `reused`
   bucket catches the cheapest version of that forgery (reusing the same identity twice); a forger
   who copies a *different* real row's identity into each fabricated entry defeats it too.

   **Correction-mode caveat (added 2026-09-09, #5133 Blocker 1(a)):** the `reused` bucket's own
   coverage depends on a `superseded` entry's identity pair staying counted when it should. A
   `--correct-identity` correction that moves an entry's `reviewer=` pair to a SECOND real,
   corroborable pair (not a typo of the same pair — a genuinely different one) used to free the
   ORIGINAL pair from the `reused` check entirely, since every `superseded` entry was unconditionally
   excluded: a forger could exploit this by correcting a genuinely-reviewed entry's identity away,
   then citing the now-freed pair in an unrelated, never-reviewed boundary, and the audit would read
   fully clean. The fix keeps a superseded entry's pair bound to the `reused` check specifically when
   its own pair DIFFERS from its successor's (the pair was genuinely released, not merely re-typed
   byte-identically) — the released pair is then reclassified from `superseded` to `reused` the
   moment anything else cites it. The SANCTIONED use case (a warm-chain round correcting a typo'd
   entry back to the SAME pair another live entry already cites) is unaffected: an unreleased pair
   (byte-identical to its successor's) still never contributes to this check, matching the original
   exemption's own intent.
2. **Retention window ceiling.** `spend.jsonl` only retains ~5-6 days of rows, and
   `daily_spend_rollup.py`'s aggregation destroys `agent_id`/`tool_use_id` permanently at roll-off
   (it aggregates by `(agent_type, model)` only). A `clean` entry older than ~5-6 days is therefore
   permanently, indistinguishably `unmatched` — the same verdict a genuine forgery gets, because the
   row it could have matched against no longer exists to check. This audit must run inside that
   window (see pre-step E above) or its findings for anything older are structurally unusable.

Building real enforcement (e.g. gate 3b refusing an unattributed `clean` entry) is explicitly out of
scope for this module — see its own docstring.

## What `agent_budget.py` does

`~/.claude/hooks/agent_budget.py` is the **machine-wide concurrency ceiling and pacer** for parallel
sub-agent fan-out. Leases are files under `~/.claude/.agent_budget/`, keyed by a sanitized agent id.
It is a cooperative, advisory ledger: fails open on any unreadable/corrupt state, self-heals stale or
malformed leases, and never blocks a tool call via exit code — a deny is only ever a JSON object on
stdout.

Key subcommands:
- `status` — cores, 1-min load, the ceiling (`CSA_ANTHROPIC_CEILING`, default 8), live lease count,
  and a recommended-additional-slots figure. This is what every scheduled job and `/sweep` run as a
  pre-flight, logged but never a hard gate.
- `claim <id>` / `release <id>` — idempotent lease create/refresh and removal.
- `gate` — the `PreToolUse:Task` admission gate. With the pacer on (`CSA_PACER=1`) it claims a lease
  under an admission lock and can deny over cap (only when enforcing); without it, it's the legacy
  read-only advisory count.
- `spend --by agent|model|day` — a quick human-facing glance at the spend ledger (the rigorous,
  dedup-aware version of the same data is `churn_report.py`'s job, not this one).
- `browser_pool` — the `PreToolUse:mcp__playwright*` advisory pool check (log-only, never blocks).

The pacer (`CSA_PACER=1`, plus a token-bucket launch rate/burst) exists specifically to stop a
synchronized burst of many large-context dispatches from tripping Anthropic's per-minute input-token
rate limit — the actual binding constraint on fan-out width, not CPU cores and not the 5-hour/weekly
account budget (`~/.claude/CLAUDE.md` §9).

## Observed-model recovery (WS2.1 step 4/5, landed 2026-09-20)

**Context:** master plan `~/.claude/plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md`,
section "### 2.1 Model pins" items 4-5 (tracking issue example-org/#5828).
The Workflow-event probe above (and the model-pin gate's own scope, `Task`-matcher only) established
that a Workflow-tool leg's `SubagentStop` is the FIRST and ONLY event `agent_budget.py` ever sees for
it — no `PreToolUse:Task` claim is ever taken, so `model` came back null on all 2,009 September
`workflow-subagent` rows (and any other dispatch whose model-carrying payload field, for whatever
reason, never arrived). This closes that gap by deriving the model from the one place that ALWAYS
has it: the agent's own transcript.

**What is derived, and from where.** `hooks/agent_budget.py`'s `model_from_transcript(path,
max_bytes)` reads the transcript named by the event's own `agent_transcript_path` field and returns
the LAST `type == "assistant"` line's `message.model` string seen within the read window — verified
directly against real transcripts on this machine (both `~/.claude/projects/*/subagents/*.jsonl` for
an ordinary sub-agent dispatch and `.../subagents/workflows/<run>/agent-*.jsonl` for a Workflow leg;
every sample checked carried exactly one model string across every assistant line in the file).
"Last seen" is the documented rule for the theoretical case where that ever isn't true (a mid-dispatch
model change would make the tail — the model that produced the dispatch's actual final output — the
more representative single value), not "most common," though the two coincide in every case observed.

**Where it's applied.** `_resolve_model_and_source(existing_model, transcript_path)` is the shared
gate: an already-real `model` (from the normal dispatch-time path — `model_requested`/
`resolvedModel`) is returned untouched, with no `model_source` key added at all. Only when `model` is
still null/missing does it consult `model_from_transcript`, and it is wired into every SubagentStop-
adjacent join site that already reads `agent_transcript_path`: `_release_line_from_join` (the
background immediate-join path), `_release_line_from_completed_join` (the "gate -> completed -> stop"
deferred join), and `reap_stale`'s `stopped-unjoined` stage (AFTER, never instead of, the pre-existing
AA-0053 live-claims recovery — `_model_from_claims_by_agent_id`, an I/O-free lookup tried first; the
transcript read is the last resort, reached only when that also comes up empty). A row this fills
carries `"model_source": "transcript"`; a row that already had a real model, or genuinely has nothing
recoverable anywhere (no transcript path, or the transcript itself carries no model), is either left
alone or carries `"model_source": "unavailable"` — the identical AA-0053 convention already in place,
extended rather than replaced.

**Byte cap.** `MODEL_TRANSCRIPT_MAX_BYTES = 2_000_000` (2MB), and **regular files only** — a
non-regular path (a FIFO, a character/block device, a directory, a socket) is refused via
`os.stat`/`stat.S_ISREG` BEFORE any `open()` call, returning `(None, "NotARegularFile")` immediately.
This is a fix-round correction (2026-09-20 trust-architect review, BLOCKER, executed): `os.path.getsize`
returns `0` for a character device, which silently defeated the original seek-decision logic — a
symlink to `/dev/zero` made the read genuinely unbounded (measured: multiple GB of RSS growth within
one second, on a trajectory toward the reviewer's own executed 8.8GB/13s OOM-kill), and a FIFO with no
writer blocks forever inside `open()`, a hang `except Exception` structurally cannot catch. Because
this runs under the caller's `admission_lock`, that hang would have held the shared ledger lock
indefinitely and stalled every concurrent `release_hook` on the machine. For a genuine regular file
(every real case — an agent transcript is always a plain file), `model_from_transcript` never reads
more than the last `max_bytes` of the file (a plain `seek()` from the end, plus a belt-and-braces
bounded `fh.read(max_bytes)`), never the whole thing — reading from the tail is also the
cheapest-correct strategy given the "last assistant line wins" rule (the answer is almost always near
the end). The first, likely-partial line inside the read window is discarded when a seek occurred; if
every line in the window is unparseable or non-assistant, `model` is `None` with no error (a genuinely
unrecoverable-within-budget case, not a failure). No path-confinement to `~/.claude/projects/` was
added on top of this — the reviewer ruled `S_ISREG` is the correct and sufficient boundary.

**Exception posture.** Exception-wrapped end to end, per the plan's own rollback note ("on the stop
path — exception-wrapped"): `model_from_transcript` itself never raises (any file-level failure, or a
non-regular-file refusal, degrades to `(None, <exception class name>)` or `(None, "NotARegularFile")`,
logged once via `_lib.log("agent_budget", "model_from_transcript_error", ...)`), and
`_resolve_model_and_source` wraps its own body in a second `try/except` as defense in depth. This can
never break the stop path or the pacer lease release it shares a hook invocation with — proved
directly by
`hooks/tests/test_agent_budget.py::test_release_hook_lease_still_released_when_model_from_transcript_raises`
(a monkeypatched internal failure), plus the fix-round's own
`test_model_from_transcript_fifo_refused_never_blocks_in_open` and
`test_model_from_transcript_symlink_to_dev_zero_refused_never_unbounded_read` (each asserting a < 1s
wall-clock return, the real falsifiability signal for a hang/unbounded-read class of bug).

**`model_pin_parity.py`'s lookback split (item 5).** `pin_tier_mismatches` reported 18 real
`pin-tier-mismatch` violations on 2026-09-20, every one of them a genuine mismatch recorded BEFORE
this fix landed — a "lookback artifact," not evidence the fix is incomplete. `MODEL_OBSERVED_SINCE =
"2026-09-21"` is the one constant that draws the line — deliberately the day AFTER the land date, not
the land date itself: the land day's own rows are an unavoidable pre/post MIX (rows written before the
fix deployed and rows written after it, both dated `2026-09-20`, are indistinguishable by date alone),
so the boundary is set to the first FULL day guaranteed to be entirely post-fix. A row dated on/after
it is judged normally and reported as `pin-tier-mismatch:`; a row dated before it is reported
separately as `pin-tier-mismatch-lookback:` (never silently dropped — still real ledger history, just
not evidence of anything still wrong). `check()`'s own live call passes `since=MODEL_OBSERVED_SINCE`;
every existing/hermetic test of `pin_tier_mismatches` calls it with the default `since=None`, which
preserves the pre-split behavior exactly (no test needed updating for the signature change itself —
only `check()`'s own wiring test, whose fixture predates the land date and therefore needed a
post-land `ts` to keep asserting a real, non-lookback violation). **N1 fix (same round):**
`_row_is_post_land` now requires `ts` to shape-match `^\d{4}-\d{2}-\d{2}` before the string comparison
— a raw compare alone let a malformed value (`"garbage"`, `"9999"`, `"2026/09/21"`) sort LEXICALLY
above a real date and wrongly count as post-land, the opposite of the function's documented
conservative direction. A non-UTC-offset `ts` (anything not literally `Z`-suffixed) is still compared
as a plain string prefix, same as every other date-window check in this module — every real
`spend.jsonl` row observed on this machine is `...Z`-suffixed.

**Report tally (N3, same round).** `model_pin_parity.py`'s own CLI summary line is now
`model_pin_parity: <n> violation(s) (+<m> lookback)` — the headline `<n>` is the POST-LAND
(actionable) count only, with `pin-tier-mismatch-lookback:` lines excluded and instead surfaced as the
`(+<m> lookback)` suffix (omitted entirely when `m` is 0), so the number a reader acts on is never
diluted by historical artifacts. Confirmed no consumer in `hooks/`, `scripts/`, or `schedules/` parses
this line's shape.

**Exit criterion:** ≥95% of rows dated after the land date carry a real (non-null) `model`, measured
14 days after landing (2026-10-05) via `hooks/agent_budget.py spend --by model` or
`churn_report.py`'s spend metrics over that window. `model_pin_parity.py`'s own exit is 0
`pin-tier-mismatch:` (non-lookback) violations among post-land rows — the 18 seen on 2026-09-20 are
expected to remain in the report as `pin-tier-mismatch-lookback:` lines indefinitely (they are
history, not a target to drive to zero).

## 2026-09-20/21 — Workflow-event probe: RESULT (ran, answered its question, removed)

**Context:** master plan `~/.claude/plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md`,
section "### 2.1 Model pins" item 2 (tracking issue example-org/#5828). Every
`Agent`/`Task` dispatch is governed by the model-pin gate (`hooks/pretooluse_task.py` ->
`hooks/model_pin_gate.py`), which is registered only on the `Task` matcher — sub-agents launched via
the `Workflow` tool bypass it entirely (all 2,009 September `workflow-subagent` rows in
`~/.claude/.agent_budget/spend.jsonl` are `join_state:"no-claim"`). Before deciding how, or whether,
to govern Workflow legs, the plan called for directly observing the raw hook event: does a
`PreToolUse` matcher named `Workflow` fire once per Workflow call, once per leg, or never?

**What ran.** `hooks/workflow_probe.py`, a LOG-ONLY, stdlib-only module registered on a temporary
`{"matcher": "Workflow"}` object in `settings.json`'s `hooks.PreToolUse` (commit `b9570fb`), live
from 2026-09-20 16:31 local — the working-file edit, six minutes BEFORE that commit landed at 16:37
— through removal on 2026-09-21. It logged one JSONL line per fired event
to `~/.claude/.enforcement/workflow_probe.jsonl`.

**Result.** 12 lines captured, spanning `2026-09-20T22:31:44Z` -> `2026-09-21T01:46:32Z`. Every line
carries `hook_event_name: "PreToolUse"` and `tool_name: "Workflow"` — no other value of either field
appeared. Two real Workflow calls observed by the dispatching session spawned 6 and 9 legs
respectively, and produced exactly 2 log lines (one per call). **Conclusion: the `Workflow` matcher
fires exactly once per Workflow tool CALL, and never per leg.** A `PreToolUse:Workflow` hook
therefore cannot see, and cannot govern, individual `agent()` legs at dispatch time — whatever a
Workflow call ultimately spawns is invisible to a per-call gate. Workflow-leg governance instead has
to be a post-hoc, transcript-derived model (the approach that landed in `8656bf9`), not an
extension of the model-pin gate's per-dispatch shape.

**Side finding (UNVERIFIED as a general claim):** one already-running session picked up the newly
appended `Workflow` matcher without restarting. This is a single observation from the session that
happened to fire it, not a tested behavior of the client — do not rely on it; assume a session
restart is required for a hook-registration change until it is verified deliberately.

**Evidence preserved:** the full 12-line log is archived at
`~/.claude/.board_state/workflow_probe_evidence_2026-09-21.jsonl` (untracked runtime state, not the
repo) for anyone who needs the raw records later. The probe's `--sentinel` line — its mechanism for
telling "the matcher never fired" apart from "the hook crashed" — was never written, and did not
need to be: 12 positive firings prove the matcher fired, which is what the sentinel existed to
establish in its absence.

**Removed 2026-09-21:** the `{"matcher": "Workflow"}` object is deleted from `settings.json`'s
`hooks.PreToolUse` (matcher count back to 4: `Artifact`, `Bash`, `Task`, `mcp__playwright.*`);
`hooks/workflow_probe.py` and `hooks/tests/test_workflow_probe.py` are deleted. Nothing else ever
referenced this module — no other hook, agent definition, or doc depended on it.

---

For the full record schema, the cost-resolution algorithm and its "correspondence trap," schema v2's
optional top-level keys (the `OPTIONAL_TOP_KEYS` set), and the CLI reference, see
[`telemetry/README.md`](../../telemetry/README.md).
