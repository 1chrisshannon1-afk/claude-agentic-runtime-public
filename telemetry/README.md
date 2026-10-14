# cycle telemetry

Repo-agnostic telemetry for **self-correcting agent loops** — any loop, in any
repo, where finders raise findings, a consolidator dedups/rules on them, a
verifier checks them, and fixes land or don't. This directory holds the DATA
and its DOCUMENTATION; the library and CLI that read/write/validate/compute
over it live at `~/.claude/hooks/cycle_telemetry.py`.

Nothing here names a repo, a product, or a specific loop. `system` and `repo`
are opaque strings supplied by whoever emits a record — never hardcoded, never
branched on. A repo that doesn't exist yet can use this exactly as-is.

**Known `system` values in use (documentation only — never enforced as an
enum; a new one needs no schema change):** `estimate-loop` (the
self-correcting engine loop this doc mostly illustrates) and `wheel-<slug>`
(THE ISSUE WHEEL — see `~/.claude/schedules/prompts/issue_wheel.txt`; its
cycles are wave-scoped, one cycle per wave, `cycle_id` conventionally
`wave-<N>`). **Retired (THE ISSUE WHEEL rollout, commit 8c, 2026-09-09):**
`sdw` (the Standing Delivery Wheel — `hooks/sdw_queue.py` was renamed to
`hooks/issue_wheel_queue.py` at commit 2 and survives as THE ISSUE WHEEL's
own P4 QUEUE phase; `hooks/sdw_sweeper.py`/`hooks/sdw_state.py` are DELETED,
their responsibilities absorbed into THE ISSUE WHEEL's own LANE RECIPE and
heartbeat contract). SDW dispatches were the original reason
`dispatch.item_key` exists (v2, optional; the field name itself was renamed
from `wave_item` to `item_key` in the same commit that retired `sdw`, since
it is a general-purpose join key, not SDW-specific — see its own field
comment in `cycle_telemetry.py`): a free-string join key back to a work
item (a `wave_state.json` item for the retired SDW; an issue number for
THE ISSUE WHEEL's own lanes), so a wave's cost is attributable PER ITEM,
not only per cycle — `tool_use_id`/`agent_id`/`session` already let
`resolve_cost()` find the right ledger row; `item_key` is what then lets a
caller ask "how much did item #4901 cost" without re-deriving it from
dispatch order.

`dispatch.scenarios` (v2, optional, AA-0106, added 2026-09-07): a list of the
individual units of work (e.g. scenario ids) ONE REAL dispatch covered, for a
loop whose dispatch shape batches many scenarios into a single sub-agent
call (the `estimate-loop` GC/trade review round: one judge, one Task
call, many scenarios judged in that turn). **The contract this field
exists to enforce: exactly one `dispatches[]` entry per REAL Task
dispatch — never one entry per scenario.** AA-0106 found `cycle_log_emit.py`
doing exactly the latter (one synthetic entry per ledger row, i.e. per
scenario, with every synthetic entry echoing the SAME real `tool_use_id`) —
`resolve_cost()`'s step-4a 1:1 identity check correctly refused every one of
those cycles, because a declared identity count of N scenarios can never
correspond 1:1 to the single real ledger row that `tool_use_id` actually
has. `scenarios` is where the per-scenario detail belongs instead.

## Layout

```
~/.claude/telemetry/
  README.md            this file
  schema.json           formal (JSON-Schema-shaped) contract, for tooling
  pricing.json          operator-editable $/token table (see "Cost" below)
  fixtures/
    sample_cycle_record.json   a REAL first-run's numbers, clearly labelled
  cycles/
    <system>/<cycle_id>.json   real cycle records land here, one file per run
~/.claude/hooks/
  cycle_telemetry.py    the library + CLI (validate / summarize / metrics /
                         resolve-cost) — see its module docstring for the API
```

`cycles/` is populated at runtime by `write_cycle()` / the CLI; it is never
pre-seeded with fake data. `fixtures/` holds the one reference sample and is
never read by aggregate reporting (`read_cycles()` only ever looks under
`cycles/`), so the sample can never contaminate a real report.

## What a cycle record is

One JSON object per run of a loop:

```jsonc
{
  "schema_version": 1,
  "system": "<slug, e.g. estimate-loop>",   // which loop; data, not code
  "repo": "<repo name or null>",                // data, never a path
  "cycle_id": "<slug>",
  "started_at": "<ISO8601Z>", "ended_at": "<ISO8601Z or null>",
  "dispatches": [ {agent_type, label, model, tokens_total, cost_usd,
                    tool_calls, duration_ms, batch_size, batch_position} ],
  "calibration": {plant_id, planted_in, slot, caught_by: [], missed_by: []},
  "calibration_runs": [ {plant_id, trade, slot, batch_size, caught_by: [],
                          missed_by: [], false_alarm_finding_ids: []} ],  // v2, optional
  "findings": [ {finding_id, raised_by: [], claim_symptom, claim_cause,
                  consolidator_decision, verifier_verdict,
                  verifier_cause_upheld, already_tracked_as, fights_ruling,
                  fix_status} ],
  "cost": {source, total_tokens, total_usd, ...},
  "notes": []
}
```

Every level is a **closed shape**: an unknown key anywhere, a value of the
wrong type, an enum value outside the allowed set, or an integer too large to
survive a finite float conversion (e.g. a `tokens_total`/`cost_usd`/
`total_tokens`/`total_usd` of `10**309` — schema-valid JSON, but unusable by
every downstream `float(x)` call site) is a validation error — never a silent
pass-through. `schema.json` bounds every numeric field `validate_cycle()`
guards this way with a `maximum` of `sys.float_info.max` for exactly this
reason — as of round 18 that's ten fields (all seven `dispatches[]` numeric
fields, `cost.total_tokens`, `cost.total_usd`, `cost.window.tolerance_sec`),
enumerated in `test_cycle_telemetry.py`'s `NUMERIC_GUARDED_FIELDS`, plus
`verdict.confidence`'s separate semantic `maximum: 1` (deliberately a
hair stricter than the Python validator's real acceptance boundary, which
rounds `int(sys.float_info.max) + 1` down to a finite float and accepts it —
JSON Schema doesn't try to encode that rounding edge case, it just uses the
clean, well-known constant). `cycle_telemetry.validate_cycle(record)` returns
the list of problems (empty = valid); `write_cycle()` calls it and refuses to
persist anything invalid (`ValidationError`, never a silently-corrupt file on
disk). Full field-by-field rules live in `schema.json` plus the docstrings on
`_validate_dispatch` / `_validate_calibration` / `_validate_calibration_run` /
`_validate_finding` / `_validate_cost` in `cycle_telemetry.py` (a few
cross-field rules — e.g. `ended_at` can't precede `started_at`,
`caught_by`/`missed_by` must be empty when `plant_id` is null (both the
legacy `calibration` block and each `calibration_runs[]` row), a
`calibration_runs[]` row's `false_alarm_finding_ids` must be empty when
`plant_id` is NOT null, a cost of `unavailable` must carry a `reason` — are
easier to express precisely in Python than in JSON Schema, so that module is
the actual source of truth; `schema.json` documents the shape for tooling that
isn't Python — `test_schema_calibration_run_required_keys_match_code` fences
`calibration_run.required` against `REQUIRED_CALIBRATION_RUN_KEYS` so the two
can't silently drift apart).

Two intentional extensions beyond the base contract, both there so the record
can stay **honest** instead of guessing:
- `ended_at: null` is allowed — it means the cycle is still running.
- `cost.source` adds `"unavailable"` to the base `spend_ledger|reported` pair
  — see "Cost" below. A `cost` of source `unavailable` (or `spend_ledger` with
  a null `total_usd`) MUST carry a `reason` string; the validator enforces
  this, because "I don't know" without an explanation is not honest either.

## Schema v2 — the optional top-level keys (see `OPTIONAL_TOP_KEYS`), purely additive

v2 was built 2026-08-28 against a real, measured gap: the operator's own
standard is *"must know about every run. what error was found. who found it.
what was decided. what change was made as a result. architect review? cost.
literally everything. too much data is better than not enough."* Measured
against one real session, v1 captured roughly 40% of that. The full gap
analysis is `~/.claude/plans/cycle_log_schema_v2_gaps.md`; `cycle_telemetry.py`'s
own module docstring carries the authoritative per-array shape. **v2 is purely
additive: a v1 record with none of the arrays below still validates,
forever, unchanged.** Rendering is unchanged too, with ONE deliberate
exception: the no-calibration fallback line's own copy was reworded when
`calibration_runs[]` landed (it now also names that array), so a v1 record
with `calibration.plant_id` null renders a different (still accurate)
fallback sentence than before -- everything else about how a v1 record
renders is unaffected. Proven by `test_v1_record_with_zero_v2_fields_still_validates`
and `test_real_shipped_leaked_and_blind_records_still_validate` (library) /
`test_real_shipped_b0_records_still_render_without_the_grid_section` (renderer,
confirms the grid section stays absent and the legacy table unaffected for
those two records specifically -- they never reach the reworded fallback
line) in the test suite, which re-validate/re-render the two real records
under `cycles/estimate-loop/` on every run. The original nine arrays below all
landed together on 2026-08-28; `calibration_runs[]` (last row) was added
later, 2026-08-29 (GH #4648, W4s), under this same additive contract — not
part of the original nine-gap batch.

| array | closes | what it holds |
|---|---|---|
| `runs[]` | gap 1 — "every run" | EVERY agent run, not just the finder pass `dispatches[]` already models. A run that found nothing still happened and still cost money — `outcome` is a required non-empty string even when the honest content is "occurred; no further detail captured." |
| `reviews[]` | gap 2 — no review record at all | Reviewer, target, round, blocker count, per-finding severity/fixed, and whether the review upheld or overturned a prior decision. The operator asked for this **by name**. |
| `changes[]` | gap 3 — bare `fix_status` string | Commit SHA (`"uncommitted"` is a valid literal), files, +/- lines, `red_before_green` falsifiability evidence, tests added, golden-net drift, `reverted`. |
| `decisions[]` | gap 4 — no reasoning, no operator rulings | Who decided (`decided_by` is a free string — `"OPERATOR"` is data, never a special case), the **verbatim** `reasoning`, what it `supersedes`, the resulting `action`. |
| — (finding) `found_at_stage` | gap 5 — consolidation-only findings invisible | Accepts `"consolidation"` (also `"finder"`/`"verifier"`/`"review"`) so a finding a consolidator surfaced but that never reached a verifier is representable at all. |
| `issues_filed[]` + finding `issue_refs` | gap 6 — no issue linkage | Both directions: an issue references `related_findings`, a finding references `issue_refs`. |
| `evidence[]` | gap 7 — citations discarded | File/line/quote/repro-command per finding; at least one of the three is required. |
| `corrections[]` | gap 8 — retractions were free text | The loop's **own error record**: what was claimed, what was wrong, how it was found, what it invalidated. Arguably the most valuable series in the whole log. |
| `verdicts[]` | gap 10 — per-dispatch verdicts dropped | Raw per-scenario `CONCUR`/`DISSENT` + confidence + problem count, before consolidation collapses them into `findings[]`. |
| `stages[]` | gap 11 — no stage record | Which pipeline stages ran/were skipped/were blocked, and why (`blocked_reason` is required, non-empty, whenever `status` is `"blocked"`). |
| — (dispatch) `tokens_reported`/`tokens_source` | gap 9 — untrusted numbers deleted | The harness's own (possibly wrong) token figure, kept and LABELLED rather than nulled out. `tokens_source` is required whenever `tokens_reported` is set. |
| `calibration_runs[]` | added 2026-08-29, GH #4648 — the GRID form of `calibration`, above | Many plant AND clean-control rows in one record (a plants-x-trades grader-calibration grid), which the single `calibration` object cannot express: one plant per record, `caught_by`/`missed_by` forced empty whenever `plant_id` is null. A row with `plant_id` null is a CONTROL (`caught_by`/`missed_by` must stay empty, but `false_alarm_finding_ids` may carry the false-alarm signal); a row with `plant_id` set is a PLANT (the mirror rule: `false_alarm_finding_ids` must stay empty). Never replaces `calibration` — a sibling. See `plant_catch_by_trade`/`false_alarm_by_trade` below. |
| `undispatched_verdict_rows` (an OBJECT, not an array) | added 2026-09-07, round-25 structural-conflict fix — `{"count": int, "by_judge": {judge: int}}` | Honest accounting for a verdict row EXCLUDED from `dispatches[]` because it carries no real dispatch identity at all (e.g. a GC consolidation pass, which judges many scenarios within one already-open turn and is never its own separate Task dispatch — fabricating an identity for it is forbidden, GH #5051 tracks what a genuinely fabricated/misattributed identity looks like instead). `dispatches[]` holds real, identified dispatches only; an excluded row's verdict still appears in full in `verdicts[]`/`findings[]` — this object exists purely so nothing about a cycle's true verdict coverage is hidden by the exclusion. `by_judge` values must sum to exactly `count` (the one cross-field rule this shape has). Absent means "not computed" (e.g. a v1 record, or a producer that hasn't adopted this field), not "nothing excluded" — an all-identified cycle from a producer that HAS adopted it reports `{"count": 0, "by_judge": {}}` explicitly. |

Every one of these is **optional** at the top level (and the two per-item
extensions are optional per-item) for exactly one reason: a caller with only
partial v2 data (it knows the reviews but not the verdicts, say) must still be
able to write a valid record. "Too much data is better than not enough" does
not mean "all v2 fields or none" — populate whatever you actually know, leave
the rest absent, and the record still validates.

## Emitting a record (any repo, any loop)

There is no per-repo integration step. Build a dict matching the shape above
and call the library — from Python:

```python
import sys
sys.path.insert(0, "/absolute/path/to/.claude/hooks")  # wherever this runtime lives
import cycle_telemetry as ct

record = { ... }                 # your loop's own data, matching the schema
ct.write_cycle(record)           # validates, then writes cycles/<system>/<cycle_id>.json
```

or from the CLI, once you have a JSON file on disk:

```
python3 ~/.claude/hooks/cycle_telemetry.py validate my_cycle.json
```

A loop that wants to record an **in-progress** cycle can write it once with
`ended_at: null`, then `write_cycle(record, overwrite=True)` again when it
finishes with the real `ended_at` and the rest filled in.

## The derived metrics — and what each one MEANS

All of these are pure functions over one record (or, for `plant_catch_by_slot`
and `aggregate_metrics`, over a list of records) — no LLM, no network, fully
deterministic and unit-tested. Every one of them returns `None` rather than a
misleading `0` or `1` when there is nothing to compute from (e.g. zero
findings, or nothing verified yet) — a metric of `None` means "no data," not
"zero."

- **`symptom_precision`** — of the findings the verifier actually judged
  (excluding `UNVERIFIABLE` and not-yet-verified ones), what fraction had a
  REAL symptom (`CONFIRMED` / `PARTIALLY_CONFIRMED` / `ALREADY_TRACKED_ELSEWHERE`)?
  This answers: *"when a finder said something was wrong, was it actually
  wrong?"*

- **`cause_precision`** — of the findings where the verifier actually judged
  the stated root cause, what fraction had that cause UPHELD
  (`verifier_cause_upheld == true`)? This answers a different, harder
  question: *"when a finder said something was wrong AND explained why, was
  the explanation right?"*

  **This is the metric that matters most, and the reason this whole schema
  exists.** In the first real run of a loop like this, a human read nine
  finder reports by hand and found the finders right about the SYMPTOM 8
  times out of 9, but right about the ROOT CAUSE only 1 time out of 9 — a gap
  invisible to any metric that only checks "was something actually wrong."
  A wrong-cause fix is either a no-op (the real bug survives) or a new
  regression (the "fix" changes the wrong thing). `symptom_precision` alone
  would have reported this loop as roughly 89% accurate; `cause_precision`
  reports the true, much worse, 11%. Watch `cause_precision`, not
  `symptom_precision`, to know whether a loop's fixes can be trusted
  unreviewed.

- **`duplicate_rate`** — of ALL findings raised (not just judged ones), what
  fraction were re-hits on something already tracked
  (`already_tracked_as` set, or verdict `ALREADY_TRACKED_ELSEWHERE`)? High
  duplicate rate means the finder pass keeps re-discovering known issues
  instead of surfacing new ones.

- **`ruling_conflict_rate`** — of ALL findings raised, what fraction contradict
  an already-ratified ruling (`fights_ruling` truthy)? A ruling exists so a
  question doesn't get re-litigated every cycle; a nonzero rate here is a
  signal either the finder needs better grounding in the ruling corpus, or the
  ruling itself needs revisiting (it doesn't tell you which — a human decides).

- **`consolidation_ratio`** — average number of independent raisers collapsed
  into each final finding (`sum(len(raised_by)) / len(findings)`). `1.0` means
  no two finders ever converged on the same issue; higher means real
  deduplication is happening (multiple finders independently spotted the same
  real thing, and the consolidator correctly merged them into one record
  instead of double-counting).

- **`usd_per_confirmed_defect`** — `cost.total_usd / count(findings with
  verdict CONFIRMED or PARTIALLY_CONFIRMED)`. `None` whenever cost is unpriced
  (`total_usd` is null) or there are zero confirmed defects (never reported as
  an artificial infinity). This is the "was this pass worth what it cost"
  number — but it is only as trustworthy as `cost.source` (see below).

- **`plant_catch_by_slot`** — calibration catch/miss counts pooled by slot
  (typically a `dispatches[].batch_position`), across one record or many. A
  slot only appears here after being observed at least once. In the sample
  fixture, the calibration plant was caught at the first and last position in
  a 3-wide finder sub-batch and missed in the middle — one real observation of
  a possible position-in-batch effect, not (yet) enough data to call a
  pattern; more cycles feeding the same call (pass a list of records) is how
  that becomes a real rate instead of a single 0/1 anecdote.

- **`plant_catch_by_trade`** / **`false_alarm_by_trade`** — added 2026-08-29,
  GH #4648: the `calibration_runs[]` GRID siblings of `plant_catch_by_slot`,
  pooled by TRADE instead of by slot. `plant_catch_by_trade` reads PLANT rows
  (`plant_id` set) for catch/miss counts; `false_alarm_by_trade` reads CONTROL
  rows (`plant_id` null) for how many blocker/DISSENT findings landed on a
  clean package — the false-alarm signal C1's trust proposal ("≥2/3 plant
  catches AND 0 false alarms on controls") reads directly. Both mark a
  present-but-malformed field (`caught_by`/`missed_by`/
  `false_alarm_finding_ids` typed as something other than a list) as
  `unreadable` rather than silently reading it as `0` — a confident `0` there
  would be exactly the kind of fabricated-innocence number this whole schema
  exists to prevent (a real incident this array's own review round caught:
  the first implementation read a malformed `false_alarm_finding_ids` as "0
  false alarms," landing a trust-favorable but entirely wrong reading on
  precisely the metric a trust decision would be made from). **`rate` on
  `false_alarm_by_trade` is deliberately UNBOUNDED above `1.0`** — a single
  control that draws more than one finding (or several controls for the same
  trade each drawing one) both raise `false_alarms` faster than `controls`,
  and that is real signal, never clamped or treated as a data error. A row
  whose `plant_id`/`trade` discriminator itself can't be read is counted in
  **BOTH** functions' `unreadable` column for the same trade (neither
  function can rule out that the row belonged to it) — summing the two
  `unreadable` columns for one trade double-counts that row; they are each
  honest on their own, never a partition of one total.

- **`aggregate_metrics(records)`** — every ratio above, pooled by SUMMING raw
  counts across all records first and dividing once, never by averaging each
  cycle's own ratio. Averaging per-cycle ratios directly is vulnerable to
  Simpson's paradox when cycles have very different finding counts (a 1-finding
  cycle and a 50-finding cycle should not weigh equally). `usd_per_confirmed_defect`
  is pooled the same way, and only over cycles with a known cost — the
  `cost_known_cycles` / `cost_unknown_cycles` fields in its output say how many
  of each, so a partial-coverage ratio is never mistaken for a complete one.

## Cost — why `cost.source` matters, and how it's resolved

**A cost figure is only as good as where it came from, and this schema makes
you say which.** In the same first real run referenced above, the workflow
harness's own per-dispatch `tokens` field reported **4,284,888** tokens total
for the cycle. The real, billed figure — read from
`~/.claude/.agent_budget/spend.jsonl`'s `tokens_total` (of which roughly 90%
was `cache_read`) — was **~124,000,000 tokens, about 26x higher, ~$65**. The
harness field is a payload-ish accounting artifact, not billed spend; trusting
it once already produced a confidently wrong cost conclusion. That is why:

- `dispatches[].tokens_total` and `dispatches[].cost_usd` are per-dispatch,
  harness-reported bookkeeping — useful for shape (how many dispatches, what
  models, what batch structure), **never** trusted for a dollar figure.
- `cost.total_tokens` / `cost.total_usd` are the cycle-level, AUTHORITATIVE
  numbers, and `cost.source` records where they came from:
  - `"spend_ledger"` — resolved from real ledger rows (see below).
  - `"reported"` — a human or another system reported it directly (no ledger
    resolution attempted); use sparingly, since it's exactly as trustworthy as
    whoever reported it.
  - `"unavailable"` — the resolver looked and honestly could not attribute a
    cost; `reason` says why. **This is a correct, expected outcome, not a
    bug** — see "the correspondence trap" below.

### `resolve_cost()` — the ledger resolver

`cycle_telemetry.resolve_cost(cycle, ledger_path=None, pricing_path=None,
tolerance_sec=600.0)` reads `~/.claude/.agent_budget/spend.jsonl` (each row:
`ts`, `agent_type`, `model`, `tokens` `{input, output, cache_read,
cache_creation}`, `tokens_total`, ...) and attributes rows to `cycle` **only**
when FOUR signals all correspond, exactly — the fourth, identity, is
REQUIRED; correspondence never holds without it (round-3 redesign; the
earlier three-signal-only heuristic is deleted, not one of several paths):

1. **time window** — a row's `ts` must fall within
   `[started_at - tolerance, ended_at + tolerance]` (default tolerance ±10
   minutes, to absorb clock skew between when a dispatch's stop event is
   logged and when the orchestrator records `ended_at`).
2. **agent-type set** — a row's `agent_type` must be one the cycle's own
   `dispatches` actually used.
3. **per-type row count** — the number of matching rows for each `agent_type`
   must equal how many dispatches of that type the cycle recorded.
4. **identity** — at least one of `tool_use_id` / `agent_id` / `session` must
   be declared, as a non-empty string, on **every** dispatch in the cycle
   (uniform coverage; the most specific field present wins), and every one
   of those declared values must correspond 1:1 to matching ledger rows in
   the window. With no such uniformly-declared identity field,
   `resolve_cost()` refuses outright and unconditionally — window + agent-type
   + count alone can never prove true correspondence (a single foreign
   session is mathematically indistinguishable from a single own session
   under that heuristic), regardless of whether the candidate rows happen to
   span one session or many. A dispatch that declares an identity value the
   ledger cannot corroborate is also refused outright, even when a sibling
   dispatch in the same cycle declared no identity at all — a declared-but-
   unmatched identity is positive evidence of non-correspondence, never
   something a sibling's silence should override.

**The correspondence trap this exists to avoid:** it would be easy — and
wrong — to grab "whatever ledger rows happen to fall in roughly the right
window" and call that the cycle's cost. Two agents' cycles can overlap in
time; a cycle's own dispatches might not be in the ledger **at all** (a
real, expected case — the ledger's own release/reap mechanics can drop an
unjoined or stale record, and nothing guarantees every run gets logged).
`resolve_cost()` treats a wrong window, an unexpected agent type, a count
mismatch, or a missing/mismatched identity as a hard refusal — it returns
`{"source": "unavailable", "reason": "..."}`, never a best-effort guess.
**Returning "unknown" is the correct, successful outcome of a refused
correspondence check** — the alternative (silently attributing the wrong
rows) is exactly the failure mode that already produced one confidently
wrong 26x-off conclusion.

When correspondence DOES hold, the matched rows' `tokens_total` values are
summed for `cost.total_tokens`, and each row's `tokens` are priced against
`pricing.json` by `model` for `cost.total_usd`. Neither is unconditionally
populated just because correspondence held: if any matched row's
`tokens_total` is missing or non-numeric, `total_tokens` is withheld
(`null`); if any matched row's model has no entry in `pricing.json`, the
row carries no token data at all, **or a token bucket / pricing-table rate
that IS present is not actually a finite number** (a hand-edited ledger
row with a string token count, a single string-typo rate in
`pricing.json` — e.g. `"cache_read": "0.3"` instead of `0.3` — or an
explicit `"cache_read": null`), `total_usd`
is withheld (`null`) rather than silently under-reporting a partial total
— `unpriced_models` lists which model string(s) need a pricing entry (or a
fixed rate/bucket value), and `reason` explains the gap. Extend or correct
`pricing.json` and re-run `resolve-cost` to fill it in.

**A non-finite value is refused as unpriceable, never rendered as a
confident dollar figure.** Whether it's a bare NaN/Infinity/-Infinity JSON
constant on a ledger row, a numeric literal that overflows to infinity at
the JSON-parsing boundary itself (e.g. `1e999`), or a value that overflows
to infinity during `price_tokens()`'s own computation (e.g. an
extreme-but-individually-finite token count multiplied by a rate),
`resolve_cost()` treats it the same as an unpriced model — the row is added
to `unpriced_models` and `total_usd` is withheld (`null`). The pooled,
cross-record sum in `metrics --system`'s `usd_per_confirmed_defect` and the
per-row figure in `summarize` get the identical treatment — an accumulated
total or ratio that overflows renders as a clear "no data"/"invalid data"
placeholder, never a bare `inf`/`Infinity` — the same finiteness discipline
the CLI's `metrics`, `summarize`, and `validate` commands and
`render_cycle_log.py`'s own renderer apply everywhere else a cost/token
number is checked.

**This is the READ-path treatment; `write_cycle()` also refuses at WRITE
time, not only at read time.** Everything above (`resolve_cost`, the
`metrics`/`summarize` rollups, `render_cycle_log.py`) is what happens when a
non-finite or overflowing value is already sitting in a record on disk —
withheld and reported as unpriceable, never fabricated into a number.
Separately, `validate_cycle()` (called by `write_cycle()` before anything is
persisted) refuses outright to WRITE any of the ten `NUMERIC_GUARDED_FIELDS`
(see above — every `dispatches[]` numeric field, `cost.total_tokens`,
`cost.total_usd`, `cost.window.tolerance_sec`) as an integer too large to
survive a finite float conversion (e.g. `10**309`) — a `ValidationError`, not
a silently-written record that some later read-path call then has to treat
as unpriceable. The two are independent, deliberate layers: the write-time
guard stops a NEW record from ever carrying an unusable value in the first
place; the read-path treatment above still matters for records written
before that guard existed, or written directly to disk bypassing
`write_cycle()` entirely (`schema.json` bounds the same ten fields with a
`maximum` for exactly that non-Python-writer case — see above).

### Known permanently cost-unavailable historical cycles (estimate-loop rounds 17/18/19/21/22)

AA-0106 (2026-09-07) fixed a producer-side defect where `estimate-loop`'s
`dispatches[]` was multiplied one entry per scenario instead of one entry per
REAL dispatch (see `cycle_log_emit.py`'s own module docstring in the
ExampleApp repo for the full defect). That fix is a SHAPE correction
only — it does not, and structurally cannot, repair `cost.source` for these
five historical rounds, because a second, separate, still-open defect sits
underneath: the GC/trade round-driving procedure recorded a **fabricated or
misattributed dispatch identity** for at least one entry in each of them
(rounds 18/19/21/22: the GC's own self-review row carries a synthetic
placeholder `tool_use_id` — e.g. `"gc-self-round-21"`, `"gc-of-record-round-18"`
— that does not exist anywhere in the real spend ledger; round 17's defect is a
MISATTRIBUTION, not a synthetic id — a real `tool_use_id` recorded under
`general-contractor` that the ledger attributes to `trade-hvac`; round 22
additionally misattributes a real `tool_use_id` from `trade-demo`'s row to
what the ledger shows as `trade-plumbing`; round 19's values sit in the
`tool_use_id` field but are `agent_id`-SHAPED — a wrong-value defect, not a
wrong-field one). `resolve_cost()`'s
step-4a 1:1 correspondence check is REFUSING these correctly — a declared
identity the ledger cannot corroborate is exactly what that check exists to
catch, and it is working as designed here.

**These five rounds stay `cost.source: "unavailable"` permanently, until the
recording-side defect is fixed** — tracked on GH #5051 (ExampleApp).
Do not attempt to route around the refusal by dropping the offending
dispatch entry before calling `resolve_cost()`: an earlier attempt to do
exactly that for round 18 (discarding its GC entry to get the remaining
trades to resolve to a clean `$33.07`) was reviewed and WITHDRAWN — silently
narrowing the dispatch list to manufacture a resolvable number is the exact
fabricated-innocence this check is designed to prevent, not a legitimate
repair. A genuine re-derivation of any of these five is only honest once
#5051 lands and the round is re-recorded (or the historical ledger rows are
corrected) with real, ledger-corroborated identity on every dispatch.

**This does NOT contradict the round-25 structural-conflict fix (2026-09-07,
`undispatched_verdict_rows`, above) — the two are different defects with
different correct answers, distinguished by WHY a dispatch has no matching
identity, not by whether one was excluded:**

- The five rounds above are excluded because their producer recorded a
  **fabricated or misattributed** `tool_use_id` for the GC's row — a value
  that claims to be real ledger evidence and is wrong or invented.
  `resolve_cost()`'s 1:1 correspondence check catching this is EXACTLY the
  thing it exists to do; dropping that entry to dodge the refusal would hide
  a real recording defect, which is why it was withdrawn.
- Round 25's `undispatched_verdict_rows` fix applies to a GC row that never
  claimed any identity at all, real or fake — the GC's consolidation pass
  genuinely has none to report (it is not its own Task dispatch). Excluding
  a row that never made an identity claim is not "dropping evidence to
  manufacture a number" — there was no evidence to drop, and no claim to
  suppress. The row's verdict is not hidden either; it is fully present in
  `verdicts[]`/`findings[]`, same as before this fix — only its (honest,
  empty) participation in `dispatches[]`'s identity-uniformity check is
  removed, with the exclusion itself recorded, honestly, in
  `undispatched_verdict_rows`.

If a producer ever narrows `dispatches[]` to drop a row that DID declare an
identity (fabricated or otherwise) rather than a row with no identity at
all, that is the round-18-style bypass this whole section warns against,
not this fix — `undispatched_verdict_rows` only ever accounts for rows
`_resolved_identity()` found genuinely empty.

### `pricing.json` — pricing is DATA, never a number in code

`pricing.json` is a flat, operator-editable table: USD per 1,000,000 tokens,
per model, broken into the same four buckets the ledger records (`input`,
`output`, `cache_read`, `cache_creation`). `cycle_telemetry.py` contains no
hardcoded per-model price anywhere — `price_tokens()` looks the model up in
this table and returns `None` (never a guessed default) for anything not
listed. The shipped table's numbers are illustrative starting points based on
published Claude pricing conventions; **verify them against your actual
Anthropic console/invoice** and correct them in place — that file, not this
one, is the single source of truth an operator edits.

## Using the CLI

```
python3 ~/.claude/hooks/cycle_telemetry.py validate <path> [<path> ...]
python3 ~/.claude/hooks/cycle_telemetry.py validate --system SYSTEM
python3 ~/.claude/hooks/cycle_telemetry.py validate --all
python3 ~/.claude/hooks/cycle_telemetry.py summarize [--system SYSTEM] [--json]
python3 ~/.claude/hooks/cycle_telemetry.py metrics <path> [--json]
python3 ~/.claude/hooks/cycle_telemetry.py metrics --system SYSTEM [--json]
python3 ~/.claude/hooks/cycle_telemetry.py resolve-cost <path> [--write] [--json]
```

`validate` exits `0` only if every record checked is schema-valid (`1`
otherwise) — safe to use as a CI/harness gate over `telemetry/cycles/`.
`resolve-cost` exits `0` when a cost was actually resolved, `3` when it was
honestly `unavailable` (a real, distinguishable outcome — not a crash), and
`2` on a usage error; `--write` persists the resolved (or refused) result back
into the cycle file's `cost` field, re-validating before it writes.

## The sample fixture

`fixtures/sample_cycle_record.json` encodes the real first-run numbers
described throughout this doc — `system: "estimate-loop"`, 9 findings,
`symptom_precision = 8/9`, `cause_precision = 1/9`, 2 duplicates, 3 findings
fighting ratified rulings, the plant caught at the first and last position of
a 3-wide batch and missed in the middle, `dispatches[].tokens_total` summing
to the harness's own (wrong) 4,284,888-token figure, and
`cost.total_tokens ≈ 124M` / `cost.total_usd ≈ $65` as the separate,
ledger-resolved, authoritative figures. It is explicitly labelled a sample in
its own `notes` field and lives under `fixtures/`, never `cycles/`, so no
aggregate report (`read_cycles()` only walks `cycles/`) can ever pick it up by
accident. Regenerate or extend it by editing the record and re-validating with
`cycle_telemetry.validate_cycle()` — never hand-edit past a validation
failure.
