#!/usr/bin/env python3
"""daily_spend_rollup — append one day's spend.jsonl aggregate to an
append-only, long-retained rollup ledger.

WHY THIS EXISTS
----------------
Gate-optimization plan (~/.claude/plans/gate_optimization_plan.md), Item 10.
``~/.claude/.agent_budget/spend.jsonl`` retains only the last ~5-6 days of
dispatch rows (nothing in this runtime rotates it to a longer-retained
history — measured live 2026-08-30: the oldest row on disk was 5 days old),
so no genuine 30-day cost series is ever possible from that file alone —
undermining any "did our review-cost-cutting work" measurement (the plan's
own §7 "Cost" line names this exact gap: "spend.jsonl only retains ~5 days;
a genuine 30-day figure will not exist in 2 weeks either"). This module
closes it cheaply: once a day, the daily oversight sweep
(schedules/prompts/daily_sweep.txt, fixed pre-step D) aggregates the PRIOR
UTC calendar day's spend.jsonl rows by ``(agent_type, model)`` and appends
ONE JSON line to a NEW file, ``~/.claude/.agent_budget/daily_rollup.jsonl``
— APPEND-ONLY, never overwritten or rotated, so a real day-over-day series
accumulates even though spend.jsonl itself keeps rolling off.

DEDUP RULE — reuses ``churn_report.dedup_spend_lines`` verbatim (never
reimplemented): a ``tool_use_id`` group collapses to one dispatch (the last
non-``unreleased`` line, or the last line if every line in the group is
``unreleased: true``) so a reap placeholder plus its later real release is
counted once — matching every other spend-ledger consumer in this runtime
(``churn_report.py``'s own metrics 5/6). Filtering to the target day happens
BEFORE dedup, exactly as ``churn_report.build_report`` already does for its
own ``--days`` window: a ``tool_use_id`` group that happens to straddle a
UTC-midnight boundary dedupes independently per day it appears in — an
accepted pre-existing tradeoff (see ``churn_report.py``'s own SPEND DEDUP
RULE section), not a new behavior invented here.

DELIBERATE DIVERGENCE from ``churn_report.spend_summary`` — that function
folds ONLY the deduped (real-``tool_use_id``) rows into its by-agent/model/
day money totals and reports null-``tool_use_id`` ("stopped-unjoined" reap)
rows as a separate join-bug finding instead. This module does NOT follow
that convention for its own totals: verified live 2026-08-30, 816 of 2,042
rows (~40%) in the real ledger carry a null ``tool_use_id`` (a
"stopped-unjoined" reap — a join bug in ``agent_budget.py``, per its own
docstring, not a missing dispatch), and ``agent_budget.py``'s reap path
computes their ``tokens`` field from the dispatch's real transcript, i.e.
these are genuine, already-spent tokens, not placeholders. Excluding 40% of
real spend would defeat this module's entire purpose (a genuine cost
series).

**A null-``tool_use_id`` row is NOT unconditionally safe to fold in** —
correcting a prior version of this docstring that claimed it was "never
joinable to anything, by construction." ``dedup_spend_lines``'s own
docstring only promises a null-``tool_use_id`` row is never deduplicated
AS A DEDUP KEY (it is never grouped with another row by ``tool_use_id``,
since ``tool_use_id`` is exactly what's missing) — it says nothing about
``agent_id``, which every reap/release line also carries and which IS
joinable. Empirically measured live 2026-08-30 against the real ledger: 67
null-``tool_use_id`` rows ("stopped-unjoined" reap placeholders) share an
``agent_id`` with a real-``tool_use_id`` row already present in the
deduped set — the SAME dispatch counted twice: once via its real release
(joined on ``tool_use_id``) and once again via the stale reap placeholder
(joined on ``agent_id``) — a measured 36-45% inflation on real data when
folded in blindly. This module therefore joins null-``tool_use_id`` rows
against the deduped set's ``agent_id``s BEFORE folding them in: any
null-``tool_use_id`` row whose ``agent_id`` already appears among the
deduped real-``tool_use_id`` rows is dropped rather than counted a second
time (tallied in the output's ``joined_duplicate_lines`` field, never
silently discarded with no trace). Only a null-``tool_use_id`` row whose
``agent_id`` matches nothing already counted is a genuinely distinct,
otherwise-unrecorded dispatch, and that one gets folded in. Do not "fix"
this to match ``churn_report.py``'s exclude-all-null-``tool_use_id``
convention — that would reintroduce the undercount this module exists to
avoid; the correct fix for the double-count is the ``agent_id`` join
above, never blanket exclusion.

TOKENS TOTAL — computed as the sum of the four
``tokens.{input,output,cache_read,cache_creation}`` sub-fields, per row,
never read from the row's own precomputed ``tokens_total`` field (verified
live 2026-08-30 against 2,037 real rows: the two values were identical in
every single row, but this module computes independently rather than
trusting an externally-supplied total — the four sub-fields are the
ledger's actual source data). A missing/non-numeric sub-field contributes 0
and is counted in ``malformed_fields``, never silently miscounted with no
trace (mirrors ``churn_report._as_int``'s coercion contract exactly).

IDEMPOTENCY — appending is skipped (not an error) when ``daily_rollup.jsonl``
already carries a line for the target date: the daily sweep runs once a
day, but a retried/rerun session must never double-append the same day's
rollup into an append-only ledger that has no dedup-on-read anywhere
downstream.

ATTRIBUTION COMPACTION (F1, 2026-09-01 agentic-systems-architect audit)
------------------------------------------------------------------------
Every non-dry-run invocation also runs `run_attribution_compaction()`: a
best-effort, never-load-bearing pass that invokes `spend_attribution.py`'s
own documented `enrich --out <sidecar>` CLI recovery once, writing the
CURRENT spend.jsonl window's recovered agent_type/model identities to
`~/.claude/.agent_budget/spend_enriched.jsonl` (default; override with
`--enriched-path`) — never mutating spend.jsonl itself (see that module's
own PROVENANCE CONTRACT: `enrich_rows()` never mutates an input row). This
closes the "built-but-not-integrated" gap `spend_attribution.py`'s own
INTEGRATION STATUS docstring section names: no scheduled job had ever
called its recovery before this wiring. Opt out with
`--skip-attribution-compaction`.

Usage:
    python3 ~/.claude/hooks/daily_spend_rollup.py
        [--date YYYY-MM-DD] [--allow-partial-day]
        [--spend-path PATH] [--rollup-path PATH] [--dry-run] [--json]
        [--enriched-path PATH] [--skip-attribution-compaction]

Exit code: 0 on a successful append, a clean idempotent skip (already
recorded), or an honest "nothing to roll up yet" (spend.jsonl absent — e.g.
before it has ever been written). Exit 1 on a genuine failure to read an
existing spend.jsonl OR the rollup file itself, or to write the rollup
file — a read error on ``daily_rollup.jsonl`` (the idempotency check's own
source of truth) is never treated as "no dates recorded yet," which would
let a retried run silently re-append a date that is merely unreadable
right now. There is no "finding"/violation concept here (unlike the
report-only checks in daily_sweep.txt's step C) — only a written-or-not
outcome. ``--date`` is validated as a real calendar date (not just
digit-shape) and refused outright when it names today or a future UTC day
— unless ``--allow-partial-day`` overrides that refusal — because rolling
up an in-progress day would permanently record a partial day under a date
the idempotency check then blocks the correct full-day rollup from ever
using.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import churn_report as cr  # noqa: E402  (reuse dedup_spend_lines/read_jsonl verbatim)

_HOME = os.path.expanduser("~")
DEFAULT_SPEND_PATH = os.path.join(_HOME, ".claude", ".agent_budget", "spend.jsonl")
DEFAULT_ROLLUP_PATH = os.path.join(_HOME, ".claude", ".agent_budget", "daily_rollup.jsonl")
# F1/P5 (2026-09-01 agentic-systems-architect audit): the SIDECAR
# `spend_attribution.py enrich --out` already writes — never spend.jsonl
# itself, and never a destructive rewrite of any existing row (see
# `run_attribution_compaction`'s own docstring).
DEFAULT_ENRICHED_PATH = os.path.join(_HOME, ".claude", ".agent_budget", "spend_enriched.jsonl")

_TS_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}Z$")


def _day_of(ts: object) -> str | None:
    """UTC calendar-day prefix (``YYYY-MM-DD``) of a well-formed ``ts``
    string, or None. Deliberately local (not imported from ``churn_report``)
    — that module's ``_day_of`` is a private helper; this module only reuses
    ``churn_report``'s PUBLIC surface (``dedup_spend_lines``, ``read_jsonl``),
    matching the cross-module-import convention already established by
    ``cycle_budget.py``'s own use of ``spend_attribution``'s public API."""
    if not isinstance(ts, str):
        return None
    m = _TS_DAY_RE.match(ts)
    return m.group(1) if m else None


def _as_int(v: object) -> tuple[int, bool]:
    """Coerce a numeric spend sub-field to ``int``; returns ``(value,
    malformed)``. Mirrors ``churn_report._as_int``'s coercion contract
    exactly (a real ``int``, or an integral ``float``, coerce cleanly; a
    ``bool``, non-integral ``float``, string, or anything else is malformed
    and contributes 0, never a silently-wrong guess)."""
    if v is None:
        return 0, False
    if isinstance(v, bool):
        return 0, True
    if isinstance(v, int):
        return v, False
    if isinstance(v, float) and v.is_integer():
        return int(v), False
    return 0, True


def default_target_date(now: datetime | None = None) -> str:
    """The PRIOR UTC calendar day ("yesterday") — the daily sweep's default
    rollup target, matching the plan's "aggregate the prior day's rows"
    instruction. ``now`` is injectable for tests; defaults to the real
    current UTC time."""
    now = now or datetime.now(timezone.utc)
    return (now.date() - timedelta(days=1)).isoformat()


def _group_bucket() -> dict[str, int]:
    return {
        "dispatches": 0,
        "tokens_total": 0,
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_creation": 0,
    }


def compute_daily_rollup(rows: list[dict], target_date: str) -> dict:
    """Aggregate one UTC calendar day's worth of spend.jsonl rows by
    ``(agent_type, model)``. Pure function — no I/O, never raises.

    ``target_date`` is a ``"YYYY-MM-DD"`` UTC calendar-day string. Only rows
    whose own ``ts`` falls on that exact day are included; a row with a
    missing/unparseable ``ts`` is EXCLUDED (unlike ``churn_report.within_days``'s
    fail-open ``>=`` window filter, this is an equality match against one
    specific day — a row with no real day cannot honestly belong to it).

    Deduplication (via ``churn_report.dedup_spend_lines``) happens on the
    already-day-filtered subset, exactly as ``churn_report.build_report``
    does for its own recency window — see module docstring's DEDUP RULE.

    A missing ``agent_type``/``model`` (either ``None`` or an empty string)
    is bucketed under the literal string ``"unknown"``, matching
    ``churn_report.spend_summary``'s own convention for the same fields —
    one convention for "field absent" across every spend-ledger consumer in
    this runtime, not two.

    Returns::

        {
          "date": target_date,
          "dispatches": <int, deduped tool_use_id groups PLUS every
                         KEPT null-tool_use_id row (see
                         "joined_duplicate_lines" below), i.e. every real
                         dispatch for the day counted exactly once — see
                         module docstring's DELIBERATE DIVERGENCE note>,
          "tokens_total": <int, sum across every group, includes the KEPT
                           null-tool_use_id rows only>,
          "null_tool_use_id_lines": <int, informational — how many
                         null-tool_use_id rows ("stopped-unjoined" reaps)
                         were actually FOLDED IN to dispatches/tokens_total
                         above (i.e. excludes any dropped as a
                         joined_duplicate_line below) — not a separate/
                         excluded count, but also not a raw count of every
                         null-tool_use_id row seen>,
          "joined_duplicate_lines": <int, a null-tool_use_id row whose
                         agent_id matched a deduped real-tool_use_id row
                         already counted — the SAME dispatch re-described
                         as a stale reap placeholder — dropped rather than
                         double-counted; see module docstring's DELIBERATE
                         DIVERGENCE note>,
          "malformed_fields": {"<field>": <count>, ...},  # {} if none
          "by_agent_model": [
             {"agent_type": ..., "model": ..., "dispatches": N,
              "tokens_total": T, "input": ..., "output": ...,
              "cache_read": ..., "cache_creation": ...},
             ...
          ],  # sorted by tokens_total desc, then (agent_type, model) asc —
              # deterministic output, never insertion-order-dependent
        }
    """
    day_rows = [r for r in rows if isinstance(r, dict) and _day_of(r.get("ts")) == target_date]
    deduped, null_lines, malformed_tid = cr.dedup_spend_lines(day_rows)

    # BLOCKER 1 fix (2026-08-30 review): a null-tool_use_id row is only
    # unjoinable AS A DEDUP KEY, not unjoinable outright — it can still
    # re-describe a dispatch already counted via agent_id (see module
    # docstring). Drop any null-tid row whose agent_id already appears
    # among the deduped real-tid rows, before folding the rest in.
    deduped_agent_ids = {
        r.get("agent_id") for r in deduped if isinstance(r.get("agent_id"), str)
    }
    kept_null_lines: list[dict] = []
    joined_duplicate_lines = 0
    for row in null_lines:
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id in deduped_agent_ids:
            joined_duplicate_lines += 1
            continue
        kept_null_lines.append(row)

    all_dispatch_rows = deduped + kept_null_lines

    groups: dict[tuple[str, str], dict[str, int]] = {}
    malformed_fields: dict[str, int] = {}

    def _mark(field: str) -> None:
        malformed_fields[field] = malformed_fields.get(field, 0) + 1

    if malformed_tid:
        malformed_fields["tool_use_id"] = malformed_tid

    for row in all_dispatch_rows:
        agent = row.get("agent_type") or "unknown"
        model = row.get("model") or "unknown"
        if not isinstance(agent, str):
            _mark("agent_type")
            agent = "unknown"
        if not isinstance(model, str):
            _mark("model")
            model = "unknown"

        raw_tokens = row.get("tokens")
        if isinstance(raw_tokens, dict):
            tokens = raw_tokens
        else:
            tokens = {}
            if raw_tokens is not None:
                _mark("tokens")

        field_values: dict[str, int] = {}
        for field in ("input", "output", "cache_read", "cache_creation"):
            value, malformed = _as_int(tokens.get(field))
            if malformed:
                _mark(field)
            field_values[field] = value
        row_total = sum(field_values.values())

        bucket = groups.setdefault((agent, model), _group_bucket())
        bucket["dispatches"] += 1
        bucket["tokens_total"] += row_total
        bucket["input"] += field_values["input"]
        bucket["output"] += field_values["output"]
        bucket["cache_read"] += field_values["cache_read"]
        bucket["cache_creation"] += field_values["cache_creation"]

    by_agent_model = [
        {"agent_type": agent, "model": model, **bucket}
        for (agent, model), bucket in groups.items()
    ]
    by_agent_model.sort(key=lambda g: (-g["tokens_total"], g["agent_type"], g["model"]))

    return {
        "date": target_date,
        "dispatches": len(all_dispatch_rows),
        "tokens_total": sum(g["tokens_total"] for g in by_agent_model),
        "null_tool_use_id_lines": len(kept_null_lines),
        "joined_duplicate_lines": joined_duplicate_lines,
        "malformed_fields": malformed_fields,
        "by_agent_model": by_agent_model,
    }


def _append_line_durable(path: str, text: str) -> None:
    """Append ``text`` (already newline-terminated) to ``path`` via a raw
    ``O_APPEND`` file descriptor, looping ``os.write`` until every byte
    lands — mirrors ``agent_budget._append_jsonl``'s write strategy (see
    its docstring, "N11, 08-25 round 3") for the SAME reason it exists
    there: a plain buffered ``open(path, "a")`` + ``.write()`` is only
    reliably a SINGLE ``write()`` syscall while the encoded text stays
    under Python's ``io.TextIOWrapper`` default ~8KB buffer — a real
    rollup line does not (measured 8123 and 9808 bytes on real ledger
    data), so buffered append is guaranteed to issue multiple syscalls for
    a normal-sized line here. A mid-write kill (launchd sleep/logout) on
    this append-only, never-repaired-downstream file can then leave a
    permanently truncated line behind. ``os.open(..., O_APPEND)`` gives
    the same atomic-offset guarantee ``agent_budget.py`` relies on (two
    concurrent appenders can never land at the same offset and stomp on
    each other), and looping ``os.write()`` covers a single call returning
    a short count — POSIX permits this on any write, not only a
    full-disk/signal edge case.

    Unlike ``agent_budget._append_jsonl``, this does NOT swallow
    exceptions: that helper is a best-effort advisory-ledger writer by
    design (an internal hook write must never raise out of a hook this
    module doesn't own), but THIS module's own documented contract is
    "exit 1 on a genuine rollup-write failure" (see module docstring's
    Exit code section) — a failure here must propagate to the caller's
    ``except Exception`` in ``run()``, never be silently dropped.
    """
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        view = memoryview(text.encode("utf-8"))
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
    finally:
        os.close(fd)


def _existing_dates(rollup_path: str) -> tuple[set[str], str | None]:
    """The set of ``date`` values already recorded in ``rollup_path`` — used
    only for the idempotency skip — plus a ``read_error`` (``None`` on a
    clean or absent read). A malformed LINE is ignored (never crashes the
    read, matches ``read_jsonl``'s own per-line tolerance); a missing file
    yields ``(set(), None)``. A genuine read ERROR (e.g. permission denied
    partway through) is NOT silently treated as "no dates recorded" — that
    would let ``run()`` re-append a date that is actually already there but
    merely unreadable right now, corrupting the append-only ledger with a
    duplicate; the caller must surface this the same way a ``spend.jsonl``
    read error already is."""
    result = cr.read_jsonl(rollup_path)
    if result is None:
        return set(), None
    rows, errors = result
    dates = {r.get("date") for r in rows if isinstance(r.get("date"), str)}
    return dates, errors.get("read_error")


def run(
    target_date: str,
    spend_path: str = DEFAULT_SPEND_PATH,
    rollup_path: str = DEFAULT_ROLLUP_PATH,
    dry_run: bool = False,
    now: datetime | None = None,
) -> tuple[int, dict]:
    """Read ``spend_path``, compute the rollup for ``target_date``, and
    (unless ``dry_run``) append it to ``rollup_path`` — unless a line for
    that date is already recorded there.

    Returns ``(exit_code, status_payload)``. ``status_payload["outcome"]``
    is one of: ``"appended"``, ``"dry-run"``, ``"already-recorded"``,
    ``"spend-absent"`` (all exit 0), or ``"rollup-read-error"`` /
    ``"spend-read-error"`` / ``"rollup-write-error"`` (exit 1). Never
    raises.
    """
    existing_dates, rollup_read_error = _existing_dates(rollup_path)
    if rollup_read_error:
        return 1, {
            "outcome": "rollup-read-error",
            "date": target_date,
            "rollup_path": rollup_path,
            "read_error": rollup_read_error,
        }
    if target_date in existing_dates:
        return 0, {"outcome": "already-recorded", "date": target_date, "rollup_path": rollup_path}

    spend_result = cr.read_jsonl(spend_path)
    if spend_result is None:
        return 0, {"outcome": "spend-absent", "date": target_date, "spend_path": spend_path}
    rows, errors = spend_result
    if errors.get("read_error"):
        return 1, {
            "outcome": "spend-read-error",
            "date": target_date,
            "spend_path": spend_path,
            "read_error": errors["read_error"],
        }

    rollup = compute_daily_rollup(rows, target_date)
    now = now or datetime.now(timezone.utc)
    line = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spend_ledger": spend_path,
        "skipped_unparseable": errors["skipped_unparseable"],
        **rollup,
    }

    if dry_run:
        return 0, {"outcome": "dry-run", "line": line}

    try:
        os.makedirs(os.path.dirname(rollup_path) or ".", exist_ok=True)
        _append_line_durable(rollup_path, json.dumps(line, sort_keys=False) + "\n")
    except Exception as exc:
        return 1, {
            "outcome": "rollup-write-error",
            "date": target_date,
            "rollup_path": rollup_path,
            "error": repr(exc),
        }

    return 0, {"outcome": "appended", "line": line}


def run_attribution_compaction(
    spend_path: str = DEFAULT_SPEND_PATH,
    out_path: str = DEFAULT_ENRICHED_PATH,
    rebuild_index: bool = True,
    meta_roots: str | None = None,
    output_roots: str | None = None,
    cache_path: str | None = None,
) -> tuple[int, dict]:
    """F1/P5 (2026-09-01 agentic-systems-architect audit, finding F1):
    invoke ``spend_attribution.py``'s OWN documented recovery + CLI output
    path (``enrich --out <sidecar>``) once, closing the "built-but-not-
    integrated" gap that module's own INTEGRATION STATUS docstring section
    names verbatim — "no dispatcher, schedule, or job in this runtime
    actually calls this module's recovery on the hot path". This is the
    daily-sweep's fixed pre-step: compact TODAY's spend.jsonl population
    into a recovered-identity SIDECAR file, `out_path`, via
    ``spend_attribution.enrich_rows()`` — which, per that module's own
    PROVENANCE CONTRACT, NEVER mutates an input row (it returns brand-new
    dicts) and NEVER touches `spend_path` itself. This is the sidecar path
    that module's own CLI already prescribes (`enrich --out`), reused here
    verbatim rather than a new one invented for this wiring.

    `rebuild_index=True` (default) additionally passes `--rebuild-index`,
    refreshing the shared identity-index cache
    (`spend_attribution_cache.json`) once per call — the "operator or
    scheduled job ... running spend_attribution.py coverage --rebuild-index
    periodically" that module's own docstring names as the missing piece; a
    once-daily cadence matches its own CACHING section's guidance ("a
    background/on-demand concern ... never a latency risk on the
    synchronous spend gate"). `meta_roots`/`output_roots`/`cache_path`
    thread straight through to the SAME CLI flags `spend_attribution.py`
    already exposes, so a caller (test or operator) can point the scan at
    hermetic fixture roots without env-var indirection.

    Item 20 (2026-09-01 fix round): `out_path` is OVERWRITTEN each call, not
    appended — it reflects only the CURRENT spend.jsonl window (whatever is
    on disk right now), never accumulating a longer history of its own.
    This is DELIBERATE, not a gap: `spend.jsonl` itself already caps at
    ~5-6 days of retention, so an append-only sidecar would just accumulate
    stale, unrecoverable-context enrichments forever past that same
    ceiling for no benefit — a rolling CURRENT-window snapshot is the
    correct shape for a "best recovery of what's live right now" sidecar.
    Do not change this to append-only.

    Pure best-effort: degrades to a distinct ``outcome`` on ANY failure
    (module unimportable, unreadable ledger, unwritable sidecar) rather than
    raising — this is a nightly enrichment convenience, never load-bearing
    for the day's rollup append (see `main()`'s own wiring: a compaction
    failure never changes this CLI's exit code). Never raises.
    """
    try:
        import spend_attribution as sa
    except Exception as exc:
        return 1, {"outcome": "attribution-import-error", "error": repr(exc)}

    argv = ["enrich", "--ledger", spend_path, "--out", out_path]
    if rebuild_index:
        argv.append("--rebuild-index")
    if meta_roots is not None:
        argv += ["--meta-roots", meta_roots]
    if output_roots is not None:
        argv += ["--output-roots", output_roots]
    if cache_path is not None:
        argv += ["--cache-path", cache_path]

    try:
        exit_code, payload = sa.run(argv)
    except Exception as exc:
        return 1, {"outcome": "attribution-error", "error": repr(exc)}
    if exit_code != 0 or (isinstance(payload, dict) and "error" in payload):
        return 1, {"outcome": "attribution-error", "payload": payload}
    result: dict = {"outcome": "attribution-compacted", "out_path": out_path}
    if isinstance(payload, dict):
        result.update(payload)
    return 0, result


def _check_date_arg(target_date: str, allow_partial_day: bool, now: datetime) -> str | None:
    """Validate a ``--date`` argument as a REAL calendar date, and (unless
    ``allow_partial_day``) refuse a target date that is today or later
    (UTC). Returns an error message to print, or ``None`` when the date is
    acceptable.

    A bare ``YYYY-MM-DD`` SHAPE check (the previous ``_DATE_RE`` regex)
    accepts calendar-invalid strings like ``"2026-02-30"`` or
    ``"2026-13-01"`` — ``datetime.strptime`` is the real calendar
    validator and is what actually rejects those.

    Refusing today-or-later by default matters specifically because this
    ledger is idempotent-on-date (see ``_existing_dates``): a mid-day run
    for "today" would compute and permanently record a PARTIAL day's
    rollup, and the idempotency check would then block the correct
    full-day rollup for that same date forever, since a date already
    present in the file is always treated as done. The override flag
    exists for a deliberate, informed exception (e.g. a manual backfill
    where a partial day is explicitly acceptable), never for routine use.
    """
    try:
        parsed = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return f"invalid --date {target_date!r}, expected a real YYYY-MM-DD calendar date"
    if not allow_partial_day and parsed >= now.date():
        return (
            f"--date {target_date} is today or in the future (UTC) — refusing to "
            "record a partial day permanently (pass --allow-partial-day to override)"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--date",
        default=None,
        help="UTC calendar day YYYY-MM-DD to roll up; default is yesterday (UTC).",
    )
    parser.add_argument(
        "--allow-partial-day",
        action="store_true",
        help=(
            "Allow a --date that is today or in the future (UTC), which is refused by "
            "default because a mid-day run would permanently record a partial day and "
            "then block the correct full-day rollup for that date forever."
        ),
    )
    parser.add_argument("--spend-path", default=DEFAULT_SPEND_PATH)
    parser.add_argument("--rollup-path", default=DEFAULT_ROLLUP_PATH)
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute and print the line; never write it."
    )
    parser.add_argument("--json", action="store_true", help="Print the full status payload as JSON.")
    parser.add_argument(
        "--enriched-path",
        default=DEFAULT_ENRICHED_PATH,
        help="F1/P5: sidecar spend_attribution.py 'enrich --out' writes its "
        "recovered-identity rows to (never spend.jsonl itself).",
    )
    parser.add_argument(
        "--skip-attribution-compaction",
        action="store_true",
        help="F1/P5: skip the spend_attribution.py recovery pass (rollup append only).",
    )
    parser.add_argument(
        "--meta-roots",
        default=None,
        help="F1/P5: passthrough to spend_attribution.py's own --meta-roots "
        "(colon-separated; hermetic tests point this at an empty tmp dir).",
    )
    parser.add_argument(
        "--output-roots",
        default=None,
        help="F1/P5: passthrough to spend_attribution.py's own --output-roots.",
    )
    parser.add_argument(
        "--attribution-cache-path",
        default=None,
        help="F1/P5: passthrough to spend_attribution.py's own --cache-path.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    target_date = args.date or default_target_date()
    date_error = _check_date_arg(target_date, args.allow_partial_day, datetime.now(timezone.utc))
    if date_error:
        print(f"daily_spend_rollup: {date_error}")
        return 1

    exit_code, payload = run(
        target_date,
        spend_path=args.spend_path,
        rollup_path=args.rollup_path,
        dry_run=args.dry_run,
    )

    # F1/P5: best-effort, never load-bearing for `exit_code` above — a
    # compaction failure is reported but never turns a successful rollup
    # append into a failing CLI run (see run_attribution_compaction's own
    # docstring for why).
    compaction_payload: dict | None = None
    if not args.dry_run and not args.skip_attribution_compaction:
        comp_code, compaction_payload = run_attribution_compaction(
            spend_path=args.spend_path,
            out_path=args.enriched_path,
            meta_roots=args.meta_roots,
            output_roots=args.output_roots,
            cache_path=args.attribution_cache_path,
        )
        if not args.json:
            if comp_code == 0:
                print(f"daily_spend_rollup: attribution compaction -> {args.enriched_path}")
            else:
                print(f"daily_spend_rollup: attribution compaction FAILED: {compaction_payload}")

    if args.json:
        if compaction_payload is not None:
            payload = dict(payload)
            payload["attribution_compaction"] = compaction_payload
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        outcome = payload["outcome"]
        if outcome == "appended":
            line = payload["line"]
            print(
                f"daily_spend_rollup: appended {target_date} "
                f"({line['dispatches']} dispatches, {line['tokens_total']} tokens, "
                f"{len(line['by_agent_model'])} agent/model groups) -> {args.rollup_path}"
            )
        elif outcome == "dry-run":
            print(f"daily_spend_rollup: dry-run {target_date}\n{json.dumps(payload['line'], indent=2)}")
        elif outcome == "already-recorded":
            print(f"daily_spend_rollup: {target_date} already recorded in {args.rollup_path} — skipped")
        elif outcome == "spend-absent":
            print(f"daily_spend_rollup: {args.spend_path} does not exist yet — nothing to roll up")
        else:
            print(f"daily_spend_rollup: FAILED ({outcome}): {payload}")

    return exit_code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess/direct call in tests
    sys.exit(main())
