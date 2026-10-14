#!/usr/bin/env python3
"""Agent telemetry collector -- Phase 1 of the agent-telemetry dashboard plan.

Surfaces what the runtime ALREADY captures, with provenance attached to every
derived value. This module computes; it does not render and it does not gate.

Read `~/.claude/plans/agent_telemetry_dashboard_plan.md` §3 (Phase 1) for the
function surface this implements and §1 for the governing constraints.

=============================================================================
THE FOUR RULES THAT SHAPE EVERY FUNCTION HERE
=============================================================================

1. THE RELIABILITY PARTITION IS LOAD-BEARING (plan §1.1, R2).
   `join_state` is not a label, it is a perfect predictor of which columns
   exist on a row. Measured across the whole ledger with zero exceptions:

     joined      -- session, model, tool_use_id, duration_ms ALL present
     no-claim    -- those four ALL null, but ~94.6% still carry tokens
     claim-only  -- session/tool_use_id present, duration_ms null, NO tokens
     claim-consumed -- like joined, but no tokens

   Therefore any duration or per-model metric MUST be computed over the
   `joined` partition ONLY and MUST print its own denominator. A metric that
   silently averages duration across the whole ledger reports a number
   computed from half the data with no indication that it did so. Every
   metric this module returns carries an explicit `partition` and `n` field
   for exactly this reason. `no-claim` rows are NEVER dropped from token or
   cost metrics -- they are ~46% of all tokens, and discarding them "to be
   safe" would silently delete the larger half of real spend.

2. PROVENANCE IS NEVER LAUNDERED (plan §3.1).
   Every derived value is returned as a `Value` -- {value, provenance,
   source}. Provenance is one of:

     original       -- read first-party off the ledger row itself
     recovered      -- inferred from a sidecar (meta.json / workflow output /
                       sibling ledger rows); a real value, but INFERRED
     declared       -- asserted by configuration (e.g. a pricing table
                       version), not measured from data
     derived        -- computed from other values in this module
     unattributable -- the input genuinely does not exist on disk

   An `unattributable` value NEVER becomes a confident one by passing through
   a sum, a ratio, or a default. A count of unattributable inputs is always
   returned alongside the metric that excluded them.

3. `tokens_total` IS AN ANTI-METRIC (plan §1.3).
   ~97% of it is re-counted cache reads; the per-message sum re-counts the
   whole context window every turn, so it runs 27x-75x above true context and
   is wrong by ~50x if read as either cost or context size. It is NEVER a
   headline here. `token_buckets()` returns the four buckets separately and
   `assert_no_tokens_total_headline()` exists so a renderer can mechanically
   refuse to plot it (a rule with no backstop is the dead-check class).

4. SPEND IS COLLAPSED, NOT SUMMED (plan §1.4; `churn_report.dedup_spend_lines`
   is authoritative and is IMPORTED, never reimplemented).
   Two independent over-counts exist in the raw ledger and both must be
   handled:

     (a) tool_use_id duplicates -- one dispatch written twice. Collapsed by
         `churn_report.dedup_spend_lines()`. On the live ledger this alone
         removes ~1 row and 0 tokens: necessary but wildly insufficient.
     (b) agent_id duplicates -- the dominant shape, a `joined` claim/release
         row PLUS a later, larger cumulative `no-claim` reap OF THE SAME
         AGENT. Measured live: 341 duplicate agent_ids, 348 extra rows,
         inflating a naive token sum by ~42%.

   MEASURED SUBTLETY, and the reason this module returns TWO collapsed
   totals rather than one (verified 2026-09-05 on a 5,755-row snapshot):
   the two published collapse rules disagree on 336 of 341 duplicate groups,
   because they answer different questions.

     * `cycle_budget._collapse_duplicate_agent_id_rows()` picks the winner by
       computed DOLLAR value. In the dominant dup shape the bigger-token
       `no-claim` row has `model: None` and is therefore UNPRICEABLE, so the
       dollar rule correctly crowns the smaller, priceable `joined` row.
       This is the right rule for a COST question and yields ~76.8B tokens.
     * `spend_attribution._collapse_duplicate_agent_tokens()` picks the
       winner by largest token count, yielding ~97.4B tokens. This is the
       right rule for an ACTIVITY question, where the later cumulative reap
       is the more complete reading of that agent's work.

   Neither is "the" token total, so this module never presents one as such.
   `token_buckets()` reports the activity-basis collapse and `spend_usd()`
   reports the cost-basis collapse, each labeled with which rule produced it.
   Both honor the shared refinement that a group containing 2+ DISTINCT
   non-null `tool_use_id`s is left completely uncollapsed -- those are
   provably independent dispatches that merely share an agent_id, and
   collapsing them was a measured 2x UNDER-report. (That refinement is inert
   on today's data -- 0 such groups -- and is implemented anyway, because it
   is the difference between correct and 2x-under the moment one appears.)

5. PERCENTILES COME FROM RAW VALUES (plan §3.1, research §1.3).
   Never average pre-aggregated per-bucket percentiles. ClickHouse's
   documented case: averaged per-host p99s reported 550ms against a true
   1,000ms -- "not a worse p99, it is not a p99 at all." p99 is SUPPRESSED
   below n=100 ("one data point wearing a statistical costume").

=============================================================================
METRICS AND THEIR DENOMINATORS
=============================================================================

Every function returns a dict carrying `partition`, `n` (the denominator),
and per-value provenance. Stated denominators:

  dispatch_counts()      n = deduped spend rows. Denominator for everything
                         else. Partition: all. Counts by agent_type / model /
                         UTC day. `agent_type` is normalized for the three
                         coexisting "missing" spellings (None, "", case
                         variants) which are reported as an explicit
                         unattributable bucket, never folded into a real name.

  token_buckets()        n = rows surviving the ACTIVITY-basis agent_id
                         collapse that carry a tokens dict. Reports the four
                         buckets separately plus cache hit rate =
                         cache_read / (cache_read + cache_creation + input).
                         Partition: all (tokens survive loss of join).

  spend_usd()            n = rows surviving the COST-basis agent_id collapse
                         that are priceable. Unpriceable rows (null model,
                         unknown/unpublished family) are counted and reported
                         as an explicit unattributable bucket -- NEVER priced
                         at $0. Partition: all. Carries the price-table
                         version. (Fable/Mythos are priceable as of
                         2026-09-05 -- see cycle_budget.PRICING_USD_PER_MTOK.)

  latency_percentiles()  n = JOINED rows with a positive duration_ms. This is
                         the highest-risk metric in the plan: `no-claim` rows
                         have duration_ms null, and `agent_budget.py:1094`
                         warns their duration is an under-report even when
                         present. p50/p95 from raw sorted values; p99
                         suppressed below n=100.

  true_duration()        n = transcripts with >=2 parseable timestamps.
                         max(ts)-min(ts) per transcript. Repairs the duration
                         gap for unjoined rows WITHOUT touching the hook.
                         Wall-clock only -- machine sleep silently inflates,
                         so implausible outliers are flagged, not corrected.

  turns_per_dispatch()   n = transcripts read. Counts type=="assistant".

  tool_calls_per_dispatch()  n = transcripts read. Counts AND ORDERS
                         content[].type=="tool_use" -> .name. The ordered
                         list feeds loop_detection(); an aggregate count
                         cannot.

  loop_detection()       n = transcripts with >= 2*min_len tool calls.
                         Repeated identical tool-call subsequences. MAST
                         FM-1.3 Step Repetition is the largest single agent
                         failure mode at 15.7%.

  call_graph()           n = meta.json files indexed across BOTH tree depths.
                         parentAgentId + spawnDepth. Count parity between the
                         two depths is asserted by the caller's test, not
                         assumed -- a presence-only check passes under a
                         half-blind glob.

  session_metrics()      n = JOINED rows (session is null on every no-claim
                         row). Dispatches/session, session span, and the
                         concurrent-sessions-over-time series.

  cache_detail()         n = rows with a tokens dict, grouped by agent_type.
                         Per-agent-type hit rate -- a busted prefix is
                         usually one agent's prompt, which a fleet-wide rate
                         cannot localize.

  ledger_health()        n = all rows. join-state mix, unreleased, late,
                         tokens_error, pricing coverage, duplicate-agent_id
                         count, and the retention horizon. Feeds the
                         dashboard's ledger-confidence clause (plan R3).

RETENTION (plan §3.1). `spend.jsonl` rolls off at ~11 days, so any "vs prior
7d" comparison sits at the edge of the window. `ledger_health()` returns the
observed horizon so the dashboard can state the limit rather than silently
comparing against a truncated window.

WHAT THIS MODULE CANNOT DO (plan §1.7, stated so nothing here implies it can):
true success/failure has no field anywhere in the runtime; mid-flight
liveness is unavailable because hooks are edge-triggered; silent
under-capture has no denominator (a dispatch that ran with hooks disabled
writes no row and nothing records its absence).

CLI: `--json` emits every computed metric, including ones the v1 page defers.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, Iterator, Mapping, Sequence

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# Authoritative shared implementations. Per plan §1.4: EXTEND, NEVER FORK.
# `dedup_spend_lines` is cited by name as authoritative in two other modules'
# docstrings; `PRICING_USD_PER_MTOK`/`price_tokens_usd`/`normalize_model` are
# the single pricing table -- a second table that can drift is the exact bug
# this plan's decision 0.1 just fixed.
from churn_report import dedup_spend_lines  # noqa: E402
from cycle_budget import (  # noqa: E402
    PRICING_USD_PER_MTOK,
    normalize_model,
    price_tokens_usd,
)

# ccdash (~/.claude/usage-dashboard/ccdash) is a SEPARATE, complete parser +
# sqlite store over the SAME transcript tree this module already reads via
# `_iter_transcripts`. It exists because `spend.jsonl` is a severely degraded
# sample of that same underlying data (measured 2026-09-05: 52.5% of
# spend.jsonl rows carry model=null and are unpriceable; ccdash's
# usage_events table has zero rows missing a model, because it parses the
# transcript's own `message.usage` block directly rather than depending on a
# hook that can fail to fire). ccdash is a SIBLING data source, not a
# replacement for spend.jsonl -- see the module section below headed
# "ccdash-backed metrics" for exactly what moves to which source and why.
#
# Imported lazily-tolerant: another machine may have no usage-dashboard
# checkout, an empty/missing sqlite file, or a schema this module predates.
# Every ccdash-backed metric below degrades to an explicit `unattributable`/
# `error` result in that case -- NEVER a silent fallback to spend.jsonl
# wearing ccdash's label, and never a crash (constraint from the plan this
# module already lives under: a collector failure is that metric's own
# `error`, not a collection abort).
_USAGE_DASHBOARD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage-dashboard"
)
if _USAGE_DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _USAGE_DASHBOARD_DIR)

try:
    from ccdash import parser as ccdash_parser  # noqa: E402
    from ccdash import pricing as ccdash_pricing  # noqa: E402

    CCDASH_AVAILABLE = True
    CCDASH_IMPORT_ERROR: str | None = None
except Exception as _ccdash_exc:  # pragma: no cover - degradation path
    ccdash_parser = None  # type: ignore[assignment]
    ccdash_pricing = None  # type: ignore[assignment]
    CCDASH_AVAILABLE = False
    CCDASH_IMPORT_ERROR = f"{type(_ccdash_exc).__name__}: {_ccdash_exc}"

# `cycle_telemetry` (this same hooks/ directory) is the AUTHORITATIVE reader
# for the loop's cycle records -- `read_cycles()` already tolerates a missing
# `cycles/` directory (returns []) and a malformed file (`on_error="skip"`),
# and is imported here rather than re-globbing `~/.claude/telemetry/cycles/`
# a second time (plan §1.4: extend, never fork). Imported lazily-tolerant
# for the same reason as ccdash -- a `quality_outcomes()` call must degrade
# to an explicit error, never crash the collector, if this module is ever
# unavailable on a given machine.
try:
    import cycle_telemetry as _cycle_telemetry

    CYCLE_TELEMETRY_AVAILABLE = True
    CYCLE_TELEMETRY_IMPORT_ERROR: str | None = None
except Exception as _cycle_telemetry_exc:  # pragma: no cover - degradation path
    _cycle_telemetry = None  # type: ignore[assignment]
    CYCLE_TELEMETRY_AVAILABLE = False
    CYCLE_TELEMETRY_IMPORT_ERROR = f"{type(_cycle_telemetry_exc).__name__}: {_cycle_telemetry_exc}"

# ---------------------------------------------------------------------------
# Provenance vocabulary (plan §3.1). These are the ONLY legal values.
# ---------------------------------------------------------------------------

ORIGINAL = "original"
RECOVERED = "recovered"
DECLARED = "declared"
DERIVED = "derived"
UNATTRIBUTABLE = "unattributable"

PROVENANCES: frozenset[str] = frozenset(
    {ORIGINAL, RECOVERED, DECLARED, DERIVED, UNATTRIBUTABLE}
)

# The join states, and which fields each guarantees. Read by
# `partition_rows()` and asserted by the tests -- this table IS the rule from
# plan §1.1, not a restatement of it.
JOINED = "joined"
NO_CLAIM = "no-claim"
CLAIM_ONLY = "claim-only"
CLAIM_CONSUMED = "claim-consumed"

# Fields that exist ONLY on joined rows. Any metric reading one of these must
# declare partition=JOINED.
JOIN_DEPENDENT_FIELDS: tuple[str, ...] = (
    "session",
    "model",
    "tool_use_id",
    "duration_ms",
)

TOKEN_FIELDS: tuple[str, ...] = ("input", "output", "cache_read", "cache_creation")

# The anti-metric (plan §1.3). Named here so the structural guard can key on
# it rather than on a string literal scattered through a renderer.
ANTI_METRIC_FIELD = "tokens_total"

# Pricing table identity. `declared`, never `original`: it is configuration
# asserted by this runtime, not a fact measured from the ledger. Any dollar
# figure that renders without this attached is a plan R3 violation.
PRICE_TABLE_VERSION = "cycle_budget.PRICING_USD_PER_MTOK@2026-09-05"

# Collapse bases (see module docstring rule 4). These are not
# interchangeable and the label always travels with the number.
BASIS_COST = "cost"  # winner by computed dollar value
BASIS_ACTIVITY = "activity"  # winner by raw token count

_TS_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ")

# p99 is meaningless on a small sample -- "one data point wearing a
# statistical costume" (plan §1.8).
P99_MIN_SAMPLES = 100

# A dispatch whose wall-clock span exceeds this is flagged as implausible
# rather than silently averaged in: duration is wall-clock, so machine sleep
# inflates it (plan §1.7 -- there is no sleep-corrected clock available).
IMPLAUSIBLE_DURATION_SEC = 6 * 60 * 60


# ---------------------------------------------------------------------------
# Value -- the provenance-carrying container (plan §3.1).
# ---------------------------------------------------------------------------


class Value:
    """One derived value plus where it came from.

    `provenance` must be one of PROVENANCES; anything else raises, because a
    typo'd provenance string silently reads as "some other kind of confident"
    to a renderer. An `unattributable` Value carries `value=None` -- there is
    no such thing as an unattributable number, only an absent one.
    """

    __slots__ = ("value", "provenance", "source")

    def __init__(self, value: object, provenance: str, source: str) -> None:
        if provenance not in PROVENANCES:
            raise ValueError(
                f"unknown provenance {provenance!r}; legal values are {sorted(PROVENANCES)}"
            )
        if provenance == UNATTRIBUTABLE and value is not None:
            raise ValueError(
                "an unattributable Value must carry value=None -- laundering an "
                "unattributable input into a concrete number is the exact defect "
                "the provenance rule exists to prevent"
            )
        self.value = value
        self.provenance = provenance
        self.source = source

    def to_dict(self) -> dict[str, object]:
        return {"value": self.value, "provenance": self.provenance, "source": self.source}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Value):
            return NotImplemented
        return (
            self.value == other.value
            and self.provenance == other.provenance
            and self.source == other.source
        )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Value({self.value!r}, {self.provenance!r}, {self.source!r})"


def unattributable(source: str) -> Value:
    """A value that genuinely does not exist on disk."""
    return Value(None, UNATTRIBUTABLE, source)


def _jsonify(obj: object) -> object:
    """Recursively convert Values to their dict form for --json output."""
    if isinstance(obj, Value):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Reading -- snapshot semantics.
# ---------------------------------------------------------------------------


def default_ledger_path(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    override = env.get("CSA_SPEND_LEDGER") or env.get("CSA_CYCLE_LEDGER")
    if override:
        return override
    home = env.get("HOME") or os.path.expanduser("~")
    return os.path.join(home, ".claude", ".agent_budget", "spend.jsonl")


def default_projects_root(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    override = env.get("CSA_TELEMETRY_PROJECTS_ROOT")
    if override:
        return override
    home = env.get("HOME") or os.path.expanduser("~")
    return os.path.join(home, ".claude", "projects")


def read_ledger(path: str) -> tuple[list[dict], dict[str, object]]:
    """Snapshot-read the spend ledger.

    The ledger is LIVE-APPENDED while being read, so this reads the whole file
    ONCE into memory and every downstream metric works from that single
    snapshot. A collector that re-reads the path and compares two passes will
    disagree with itself for no reason (measured: 5742 rows, then 5743
    seconds later). Never assumes `ts` order -- the file is append-ordered by
    EVENT time while a `joined` row is stamped with its CLAIM time, so 1345 of
    5743 rows were measured out of order relative to their predecessor.

    Returns (rows, read_report). Unparseable lines are counted, never
    silently skipped and never fatal.
    """
    report: dict[str, object] = {
        "path": path,
        "exists": False,
        "lines_read": 0,
        "rows_parsed": 0,
        "unparseable_lines": 0,
        "error": None,
    }
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return [], report
    except OSError as exc:
        report["error"] = str(exc)
        return [], report

    report["exists"] = True
    rows: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        report["lines_read"] = int(report["lines_read"]) + 1
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            report["unparseable_lines"] = int(report["unparseable_lines"]) + 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            report["unparseable_lines"] = int(report["unparseable_lines"]) + 1
    report["rows_parsed"] = len(rows)
    return rows, report


def parse_ts(ts: object) -> datetime | None:
    """Parse a ledger/transcript timestamp. Never raises.

    Memoized per distinct string (2026-09-14): ``load_metrics`` re-parses the
    same timestamps across its ten call sites (``account_capacity`` alone runs
    three passes), and one hub render measured 4.27 million ``parse_ts`` calls
    over ~190k distinct strings -- 111 s, versus the ~11 s the product repo's
    hub generator measured when it memoized this panel (ExampleApp
    ``gen_operator_hub._agent_telemetry_panel``), once a heavy agent night grew
    the 7-day transcript window.
    ``datetime`` values are immutable, so sharing one object per string is safe.
    """
    if not isinstance(ts, str) or not ts:
        return None
    return _parse_ts_str(ts)


@lru_cache(maxsize=1_048_576)
def _parse_ts_str(ts: str) -> datetime | None:
    # ``fromisoformat`` (C-implemented) accepts every shape ``_TS_FORMATS``
    # does -- ``YYYY-MM-DDTHH:MM:SSZ`` and the ``.ffffffZ`` variant -- plus
    # the offset/space shapes transcripts use, and yields the same UTC
    # instant, so it goes FIRST: the old order paid two *failing* ``strptime``
    # attempts on every fractional-second transcript timestamp before
    # reaching it. ``strptime`` is kept as the fallback so any string the old
    # path accepted still parses identically.
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None:
        for fmt in _TS_FORMATS:
            try:
                return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def day_of(ts: object) -> str | None:
    parsed = parse_ts(ts)
    return parsed.strftime("%Y-%m-%d") if parsed else None


# ---------------------------------------------------------------------------
# The reliability partition (plan §1.1) -- rule 1.
# ---------------------------------------------------------------------------


def partition_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    """Split rows by `join_state`.

    A row with NO `join_state` key at all (measured: exactly 2 rows, the two
    oldest in the ledger, predating the field) lands in an explicit "absent"
    bucket rather than being guessed into one of the real states.
    """
    buckets: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        state = row.get("join_state")
        buckets["absent" if state is None else str(state)].append(row)
    return dict(buckets)


def joined_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Only rows whose join guarantees session/model/tool_use_id/duration_ms.

    Every duration and per-model metric filters through here (plan R2).
    """
    return [r for r in rows if r.get("join_state") == JOINED]


class PartitionError(RuntimeError):
    """Raised when a metric is asked to render without its denominator.

    Plan §3.2 requires that a partition-dependent panel REFUSE to render when
    its denominator is absent, rather than emitting a number computed from an
    unknown population.
    """


def require_denominator(n: int, metric: str, partition: str) -> None:
    if n <= 0:
        raise PartitionError(
            f"{metric}: refusing to render over partition {partition!r} with n={n} -- "
            "a metric with no denominator is not a measurement"
        )


# ---------------------------------------------------------------------------
# Collapse (rule 4). Both bases share the tool_use_id refinement.
# ---------------------------------------------------------------------------


def _group_by_agent_id(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            groups[agent_id].append(i)
    return dict(groups)


def _distinct_tool_use_ids(rows: Sequence[Mapping[str, object]], idxs: Iterable[int]) -> set[str]:
    ids: set[str] = set()
    for i in idxs:
        tid = rows[i].get("tool_use_id")
        if isinstance(tid, str) and tid:
            ids.add(tid)
    return ids


def row_price_usd(row: Mapping[str, object]) -> float | None:
    """Dollar value of one row, or None when it cannot be confidently priced.

    Delegates entirely to `cycle_budget.price_tokens_usd` -- which refuses on
    an unknown family, a missing/negative token field, an unrecognized token
    key, or a `tokens_total` that disagrees with the sum of its parts. A None
    return means UNKNOWN, never $0: "a key this function does not recognize
    is never assumed to be free."
    """
    family = normalize_model(row.get("model"))
    return price_tokens_usd(
        row.get("tokens"), family, PRICING_USD_PER_MTOK, row.get("tokens_total")
    )


def _row_tokens_total(row: Mapping[str, object]) -> int:
    value = row.get(ANTI_METRIC_FIELD)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def collapse_duplicate_agents(
    rows: Sequence[Mapping[str, object]],
    basis: str,
) -> tuple[list[Mapping[str, object]], dict[str, object]]:
    """Collapse same-`agent_id` duplicate readings to one row per agent.

    See module docstring rule 4 for WHY there are two bases and why they
    disagree on 336 of 341 live groups.

      basis=BASIS_COST     -- winner is the row with the largest computed
                              DOLLAR value; an unpriceable candidate always
                              sorts strictly below every priceable one, so it
                              can never be crowned merely by looking large.
                              Use for spend.
      basis=BASIS_ACTIVITY -- winner is the row with the largest token count.
                              Use for activity/volume.

    Both leave a group COMPLETELY uncollapsed when it holds 2+ distinct
    non-null `tool_use_id`s: those are provably independent dispatches that
    merely share an agent_id, and collapsing them was a measured 2x
    under-report. Rows are never merged -- only excluded from the surviving
    list -- so a caller can always still count the raw population.
    """
    if basis not in (BASIS_COST, BASIS_ACTIVITY):
        raise ValueError(f"unknown collapse basis {basis!r}")

    groups = _group_by_agent_id(rows)
    drop: set[int] = set()
    uncollapsed_multi_tid = 0
    unpriceable_dropped = 0

    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        if len(_distinct_tool_use_ids(rows, idxs)) >= 2:
            uncollapsed_multi_tid += 1
            continue
        if basis == BASIS_COST:
            prices = {i: row_price_usd(rows[i]) for i in idxs}
            winner = max(
                idxs,
                key=lambda i: (
                    prices[i] is not None,
                    prices[i] if prices[i] is not None else 0.0,
                    -i,
                ),
            )
            for i in idxs:
                if i != winner and prices[i] is None:
                    unpriceable_dropped += 1
        else:
            winner = max(idxs, key=lambda i: (_row_tokens_total(rows[i]), -i))
        drop.update(i for i in idxs if i != winner)

    kept = [row for i, row in enumerate(rows) if i not in drop]
    report = {
        "basis": basis,
        "rows_in": len(rows),
        "rows_kept": len(kept),
        "rows_dropped": len(drop),
        "duplicate_agent_groups": sum(1 for idxs in groups.values() if len(idxs) > 1),
        "groups_left_uncollapsed_multi_tool_use_id": uncollapsed_multi_tid,
        "unpriceable_rows_dropped": unpriceable_dropped,
    }
    return kept, report


def prepare_rows(
    rows: Sequence[Mapping[str, object]], basis: str
) -> tuple[list[Mapping[str, object]], dict[str, object]]:
    """Apply BOTH published dedup layers, in the documented order.

    1. `churn_report.dedup_spend_lines()` -- the authoritative tool_use_id
       collapse. Null tool_use_ids are NEVER deduplicated (each stands as its
       own record) and a non-str tool_use_id is malformed: dropped from both
       lists and counted, never silently miscounted.
    2. the agent_id collapse for the requested basis.

    Layer 1 alone is nearly inert on today's ledger (measured: 1 row, 0
    tokens) because 52% of rows carry a null tool_use_id and rule 2 refuses to
    touch them. Layer 2 is what actually catches the ~42% inflation. Both run.
    """
    deduped, null_tid_lines, malformed = dedup_spend_lines(list(rows))
    combined = deduped + null_tid_lines
    kept, collapse_report = collapse_duplicate_agents(combined, basis)
    report = {
        "tool_use_id_dedup": {
            "rows_in": len(rows),
            "deduped_with_tool_use_id": len(deduped),
            "null_tool_use_id_rows": len(null_tid_lines),
            "malformed_tool_use_id_rows": malformed,
        },
        "agent_id_collapse": collapse_report,
        "rows_final": len(kept),
    }
    return kept, report


# ---------------------------------------------------------------------------
# agent_type normalization -- the three coexisting "missing" spellings.
# ---------------------------------------------------------------------------

# `workflow-subagent` is non-null but semantically empty: it is the client's
# generic bucket for a dispatch made with no persona. Measured at ~17.6% of
# rows. It is NOT folded into the missing bucket (it is a real, distinct fact
# about how the dispatch was made) but it is flagged so a caller never reads
# it as a persona.
GENERIC_AGENT_TYPES: frozenset[str] = frozenset(
    {"workflow-subagent", "general-purpose", "execute", "dispatch", "ultracode"}
)

MISSING_AGENT_TYPE = "(missing)"


def normalize_agent_type(value: object) -> tuple[str, str]:
    """Return (normalized_name, provenance).

    Three distinct "missing" spellings coexist in the ledger and must be
    normalized TOGETHER: `None` (1 row), `""` (162 rows), and case variants
    that would otherwise split one agent across two keys (`explore` 232 vs
    `Explore` 8). Case is folded; a genuinely absent value becomes
    MISSING_AGENT_TYPE with UNATTRIBUTABLE provenance so it can never be
    counted as a real persona.
    """
    if not isinstance(value, str) or not value.strip():
        return MISSING_AGENT_TYPE, UNATTRIBUTABLE
    return value.strip().lower(), ORIGINAL


# ---------------------------------------------------------------------------
# METRIC: dispatch_counts
# ---------------------------------------------------------------------------


def dispatch_counts(
    rows: Sequence[Mapping[str, object]], basis: str = BASIS_ACTIVITY
) -> dict[str, object]:
    """Dispatch counts by agent_type / model / UTC day.

    Denominator: deduped+collapsed spend rows (`n`). Partition: ALL -- a
    dispatch is a dispatch regardless of whether its claim joined.

    `model` is a JOIN-DEPENDENT field (null on every no-claim row), so the
    by-model breakdown is reported over the JOINED partition ONLY, with its
    own separate denominator, and the count of rows excluded for having no
    model is reported explicitly. Mixing the two would be the exact silent
    cross-partition average plan R2 forbids.
    """
    kept, prep = prepare_rows(rows, basis)
    n = len(kept)
    require_denominator(n, "dispatch_counts", "all")

    by_type: Counter[str] = Counter()
    missing_type = 0
    generic_type = 0
    for row in kept:
        name, prov = normalize_agent_type(row.get("agent_type"))
        by_type[name] += 1
        if prov == UNATTRIBUTABLE:
            missing_type += 1
        elif name in GENERIC_AGENT_TYPES:
            generic_type += 1

    joined = [r for r in kept if r.get("join_state") == JOINED]
    by_model: Counter[str] = Counter()
    for row in joined:
        model = row.get("model")
        by_model[model if isinstance(model, str) and model else MISSING_AGENT_TYPE] += 1

    by_day: Counter[str] = Counter()
    undated = 0
    for row in kept:
        day = day_of(row.get("ts"))
        if day is None:
            undated += 1
        else:
            by_day[day] += 1

    return {
        "metric": "dispatch_counts",
        "partition": "all",
        "n": n,
        "basis": basis,
        "prep": prep,
        "by_agent_type": Value(dict(by_type.most_common()), DERIVED, "spend.jsonl:agent_type"),
        "agent_type_missing": Value(missing_type, DERIVED, "spend.jsonl:agent_type"),
        "agent_type_generic_bucket": Value(
            generic_type, DERIVED, "spend.jsonl:agent_type (non-null but not a persona)"
        ),
        "by_model": {
            "partition": JOINED,
            "n": len(joined),
            "counts": Value(dict(by_model.most_common()), DERIVED, "spend.jsonl:model"),
            "excluded_rows_without_model": Value(
                n - len(joined), DERIVED, "rows outside the joined partition"
            ),
        },
        "by_day": Value(dict(sorted(by_day.items())), DERIVED, "spend.jsonl:ts"),
        "rows_without_parseable_ts": Value(undated, DERIVED, "spend.jsonl:ts"),
    }


# ---------------------------------------------------------------------------
# METRIC: token_buckets
# ---------------------------------------------------------------------------


def token_buckets(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """The four token buckets, separately, plus cache hit rate.

    Denominator: rows surviving the ACTIVITY-basis collapse that carry a
    tokens dict (`n`). Partition: ALL -- tokens survive the loss of join
    (~94.6% of no-claim rows still carry them), and dropping no-claim rows
    would discard ~46% of real tokens.

    `tokens_total` is deliberately NOT a headline here (rule 3). It is
    returned only inside `anti_metric` with an explicit warning string, so a
    renderer that reaches for it has to reach past a label saying not to.

    cache hit rate = cache_read / (cache_read + cache_creation + input).
    """
    kept, prep = prepare_rows(rows, BASIS_ACTIVITY)
    with_tokens = [r for r in kept if isinstance(r.get("tokens"), dict)]
    n = len(with_tokens)
    require_denominator(n, "token_buckets", "all")

    buckets: dict[str, int] = {f: 0 for f in TOKEN_FIELDS}
    malformed = 0
    for row in with_tokens:
        tokens = row.get("tokens")
        assert isinstance(tokens, dict)
        ok = True
        for field in TOKEN_FIELDS:
            value = tokens.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                ok = False
                break
        if not ok:
            malformed += 1
            continue
        for field in TOKEN_FIELDS:
            buckets[field] += int(tokens[field])

    denom = buckets["cache_read"] + buckets["cache_creation"] + buckets["input"]
    if denom > 0:
        hit_rate = Value(
            buckets["cache_read"] / denom,
            DERIVED,
            "cache_read / (cache_read + cache_creation + input)",
        )
    else:
        hit_rate = unattributable("no cacheable tokens in window")

    return {
        "metric": "token_buckets",
        "partition": "all",
        "n": n,
        "basis": BASIS_ACTIVITY,
        "prep": prep,
        "buckets": {f: Value(buckets[f], DERIVED, f"spend.jsonl:tokens.{f}") for f in TOKEN_FIELDS},
        "malformed_token_dicts": Value(malformed, DERIVED, "spend.jsonl:tokens"),
        "rows_without_tokens": Value(len(kept) - n, DERIVED, "spend.jsonl:tokens is null"),
        "cache_hit_rate": hit_rate,
        "anti_metric": {
            "field": ANTI_METRIC_FIELD,
            "warning": (
                "NEVER a headline: ~97% is re-counted cache reads, wrong by ~50x as "
                "either cost or context. Plot dollars or per-bucket instead."
            ),
            "sum": Value(
                sum(_row_tokens_total(r) for r in with_tokens),
                DERIVED,
                "spend.jsonl:tokens_total (diagnostic only)",
            ),
        },
    }


def assert_no_tokens_total_headline(panels: Iterable[Mapping[str, object]]) -> None:
    """Structural backstop for rule 3 (plan §1.3).

    A renderer calls this with its panel descriptors before emitting. Raises
    if any panel declares `tokens_total` as its plotted source. Prose alone is
    the dead-check class -- a rule with no mechanical backstop never fires.
    """
    for panel in panels:
        source = panel.get("source")
        if isinstance(source, str) and ANTI_METRIC_FIELD in source:
            raise PartitionError(
                f"panel {panel.get('id', '<unnamed>')!r} plots {ANTI_METRIC_FIELD!r}, "
                "the named anti-metric (plan §1.3): ~97% re-counted cache reads, wrong "
                "by ~50x. Plot dollars or the four buckets separately."
            )


# ---------------------------------------------------------------------------
# METRIC: spend_usd
# ---------------------------------------------------------------------------


def spend_usd(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Dollar spend, priced through the single shared pricing table.

    Denominator: rows surviving the COST-basis collapse that are priceable
    (`n`). Partition: ALL. Unpriceable rows are counted and surfaced as an
    explicit bucket -- NEVER priced at $0, which would silently understate
    spend by the ~52% of rows that carry no model at all.

    Carries `price_table_version` with DECLARED provenance: a dollar figure
    that renders without a price-table version is a plan R3 violation, since
    recomputing history against a changed table rewrites what was actually
    paid.
    """
    kept, prep = prepare_rows(rows, BASIS_COST)
    require_denominator(len(kept), "spend_usd", "all")

    total = 0.0
    priced = 0
    unpriceable_rows = 0
    unpriceable_by_reason: Counter[str] = Counter()
    by_type: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)
    by_family: dict[str, float] = defaultdict(float)

    for row in kept:
        usd = row_price_usd(row)
        if usd is None:
            unpriceable_rows += 1
            family = normalize_model(row.get("model"))
            if row.get("model") is None:
                unpriceable_by_reason["no_model_on_row"] += 1
            elif family == "unknown":
                unpriceable_by_reason["model_not_in_pricing_table"] += 1
            else:
                unpriceable_by_reason["token_fields_unusable"] += 1
            continue
        priced += 1
        total += usd
        name, _ = normalize_agent_type(row.get("agent_type"))
        by_type[name] += usd
        day = day_of(row.get("ts"))
        if day:
            by_day[day] += usd
        by_family[normalize_model(row.get("model"))] += usd

    coverage = priced / len(kept) if kept else 0.0

    return {
        "metric": "spend_usd",
        "partition": "all",
        "n": priced,
        "basis": BASIS_COST,
        "prep": prep,
        "price_table_version": Value(PRICE_TABLE_VERSION, DECLARED, "cycle_budget.py"),
        "total_usd": Value(round(total, 4), DERIVED, "price_tokens_usd over collapsed rows"),
        "by_agent_type": Value(
            {k: round(v, 4) for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])},
            DERIVED,
            "priced rows grouped by agent_type",
        ),
        "by_day": Value(
            {k: round(v, 4) for k, v in sorted(by_day.items())}, DERIVED, "priced rows by UTC day"
        ),
        "by_model_family": Value(
            {k: round(v, 4) for k, v in sorted(by_family.items(), key=lambda kv: -kv[1])},
            DERIVED,
            "priced rows by normalized family",
        ),
        "unpriceable": {
            "rows": Value(unpriceable_rows, DERIVED, "rows price_tokens_usd refused"),
            "by_reason": Value(dict(unpriceable_by_reason), DERIVED, "refusal reason"),
            "note": (
                "These rows are EXCLUDED from total_usd, never priced at $0. Real "
                "spend is therefore HIGHER than total_usd by an unknown amount."
            ),
        },
        "pricing_coverage": Value(round(coverage, 4), DERIVED, "priced rows / collapsed rows"),
    }


# ---------------------------------------------------------------------------
# METRIC: latency_percentiles -- the highest-risk metric (plan R2).
# ---------------------------------------------------------------------------


def percentile(sorted_values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile from RAW sorted values.

    NEVER average pre-aggregated percentiles: ClickHouse's documented case had
    averaged per-host p99s report 550ms against a true 1,000ms -- "not a worse
    p99, it is not a p99 at all." Returns None on an empty sequence rather
    than 0.0, which would read as a real, very fast measurement.
    """
    if not sorted_values:
        return None
    if not 0.0 < q <= 1.0:
        raise ValueError(f"percentile q must be in (0, 1]; got {q}")
    rank = max(1, min(len(sorted_values), int(-(-q * len(sorted_values) // 1))))
    return float(sorted_values[rank - 1])


def latency_percentiles(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """p50/p95/p99 of dispatch duration.

    Denominator: JOINED rows carrying a positive numeric `duration_ms` (`n`).
    Partition: JOINED, mandatorily.

    This is plan R2's highest-risk metric. `duration_ms` is null on 100% of
    no-claim rows, and `agent_budget.py:1094-1096` warns that even where a
    no-claim duration exists it is an UNDER-report and consumers "should
    filter on join_state == 'no-claim' rather than trust duration_ms at face
    value." A whole-ledger average here silently mixes a fast, complete
    population with a slow, truncated one.

    p99 is suppressed below n=100 (plan §1.8). An average is deliberately NOT
    returned: it mixes fast-failing denials with real work, and denials LOWER
    the average as things get worse.
    """
    joined = joined_rows(rows)
    values: list[float] = []
    for row in joined:
        duration = row.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            continue
        if duration <= 0:
            continue
        values.append(float(duration))
    values.sort()
    n = len(values)
    require_denominator(n, "latency_percentiles", JOINED)

    p99: Value
    if n >= P99_MIN_SAMPLES:
        p99 = Value(percentile(values, 0.99), DERIVED, "raw sorted duration_ms")
    else:
        p99 = unattributable(f"p99 suppressed below n={P99_MIN_SAMPLES} (n={n})")

    return {
        "metric": "latency_percentiles",
        "partition": JOINED,
        "n": n,
        "excluded_non_joined_rows": Value(
            len(rows) - len(joined), DERIVED, "rows outside the joined partition"
        ),
        "excluded_joined_without_duration": Value(
            len(joined) - n, DERIVED, "joined rows with null/non-positive duration_ms"
        ),
        "p50_ms": Value(percentile(values, 0.50), DERIVED, "raw sorted duration_ms"),
        "p95_ms": Value(percentile(values, 0.95), DERIVED, "raw sorted duration_ms"),
        "p99_ms": p99,
        "note": (
            "Computed over the joined partition only. No-claim rows carry no "
            "duration at all and are not averaged in."
        ),
    }


# ---------------------------------------------------------------------------
# Transcript readers (plan §1.2 -- the TWO-DEPTH tree).
# ---------------------------------------------------------------------------


def iter_meta_paths(projects_root: str) -> Iterator[str]:
    """Every agent meta.json across BOTH legitimate depths.

    The tree has exactly two shapes and a glob that sees only one is
    half-blind:
        <root>/<project>/<session>/subagents/agent-*.meta.json            (flat)
        <root>/<project>/<session>/subagents/workflows/<wf>/agent-*.meta.json

    `**` with recursive=True covers both. The accompanying test asserts COUNT
    PARITY (total == flat + workflow), not mere presence -- a presence-only
    assertion passes under a half-blind glob, which is the defect this rule
    exists to catch.
    """
    pattern = os.path.join(projects_root, "**", "subagents", "**", "agent-*.meta.json")
    yield from glob.iglob(pattern, recursive=True)


def meta_depth_counts(projects_root: str) -> dict[str, int]:
    """Counts per depth, for the parity assertion."""
    flat = glob.glob(
        os.path.join(projects_root, "**", "subagents", "agent-*.meta.json"), recursive=True
    )
    workflow = glob.glob(
        os.path.join(projects_root, "**", "subagents", "workflows", "*", "agent-*.meta.json"),
        recursive=True,
    )
    total = list(iter_meta_paths(projects_root))
    return {"flat": len(flat), "workflow": len(workflow), "total": len(total)}


def agent_id_from_path(path: str) -> str | None:
    base = os.path.basename(path)
    for suffix in (".meta.json", ".jsonl"):
        if base.startswith("agent-") and base.endswith(suffix):
            return base[len("agent-") : -len(suffix)] or None
    return None


def transcript_path_for(meta_path: str) -> str:
    return meta_path[: -len(".meta.json")] + ".jsonl"


def read_transcript(path: str) -> tuple[list[dict], dict[str, object]]:
    """Read one agent transcript. Fail-open per file."""
    report: dict[str, object] = {"path": path, "exists": False, "unparseable_lines": 0}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except (FileNotFoundError, OSError):
        return [], report
    report["exists"] = True
    entries: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            report["unparseable_lines"] = int(report["unparseable_lines"]) + 1
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries, report


def _iter_transcripts(projects_root: str, limit: int | None) -> Iterator[tuple[str, list[dict]]]:
    count = 0
    for meta_path in iter_meta_paths(projects_root):
        if limit is not None and count >= limit:
            return
        agent_id = agent_id_from_path(meta_path)
        if not agent_id:
            continue
        entries, report = read_transcript(transcript_path_for(meta_path))
        if not report["exists"]:
            continue
        count += 1
        yield agent_id, entries


# ---------------------------------------------------------------------------
# METRIC: turns_per_dispatch / tool_calls_per_dispatch / loop_detection
# ---------------------------------------------------------------------------


def count_turns(entries: Sequence[Mapping[str, object]]) -> int:
    """Assistant turns in one transcript."""
    return sum(1 for e in entries if e.get("type") == "assistant")


def ordered_tool_calls(entries: Sequence[Mapping[str, object]]) -> list[str]:
    """Tool names in CALL ORDER (plan §3.1: ordered, not aggregate).

    Order is what makes loop detection possible; an aggregate Counter cannot
    tell a repeated Read->Bash->Read cycle from three unrelated calls.
    """
    names: list[str] = []
    for entry in entries:
        message = entry.get("message")
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, Mapping) and block.get("type") == "tool_use":
                name = block.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    return names


def turns_per_dispatch(projects_root: str, limit: int | None = None) -> dict[str, object]:
    """Turn-count distribution across transcripts.

    Denominator: transcripts successfully read (`n`). Partition: transcripts
    (independent of ledger join -- a transcript exists regardless).
    High turns at low yield is a looping agent.
    """
    counts = [count_turns(entries) for _, entries in _iter_transcripts(projects_root, limit)]
    n = len(counts)
    require_denominator(n, "turns_per_dispatch", "transcripts")
    ordered = sorted(float(c) for c in counts)
    return {
        "metric": "turns_per_dispatch",
        "partition": "transcripts",
        "n": n,
        "total_turns": Value(sum(counts), DERIVED, "transcript type==assistant"),
        "p50": Value(percentile(ordered, 0.50), DERIVED, "raw sorted turn counts"),
        "p95": Value(percentile(ordered, 0.95), DERIVED, "raw sorted turn counts"),
        "max": Value(max(counts), DERIVED, "raw turn counts"),
    }


def tool_calls_per_dispatch(projects_root: str, limit: int | None = None) -> dict[str, object]:
    """Tool-call volume and per-tool mix.

    Denominator: transcripts successfully read (`n`). Partition: transcripts.
    """
    per_dispatch: list[int] = []
    by_tool: Counter[str] = Counter()
    for _, entries in _iter_transcripts(projects_root, limit):
        names = ordered_tool_calls(entries)
        per_dispatch.append(len(names))
        by_tool.update(names)
    n = len(per_dispatch)
    require_denominator(n, "tool_calls_per_dispatch", "transcripts")
    ordered = sorted(float(c) for c in per_dispatch)
    return {
        "metric": "tool_calls_per_dispatch",
        "partition": "transcripts",
        "n": n,
        "total_tool_calls": Value(sum(per_dispatch), DERIVED, "content[].type==tool_use"),
        "by_tool": Value(dict(by_tool.most_common()), DERIVED, "content[].name"),
        "p50": Value(percentile(ordered, 0.50), DERIVED, "raw sorted per-dispatch counts"),
        "p95": Value(percentile(ordered, 0.95), DERIVED, "raw sorted per-dispatch counts"),
    }


def find_repeated_subsequences(
    names: Sequence[str], min_len: int = 2, min_repeats: int = 3
) -> list[dict[str, object]]:
    """Repeated identical CONSECUTIVE tool-call CYCLES in one dispatch.

    MAST FM-1.3 "Step Repetition" is the largest single agent failure mode at
    15.7%, and it is directly measurable from the ordered list we already
    build. Detects back-to-back repetition of a window occurring at least
    `min_repeats` times in a row.

    A repeated window whose entries are ALL THE SAME TOOL is NOT a finding.
    This is a real distinction, not a tuning nicety: measured 2026-09-05 on
    300 live transcripts, counting same-tool runs reported an 86.3% "loop
    rate" -- which is not a measurement of anything, because `Bash` fifteen
    times in a row is an agent using Bash a lot, not an agent stuck in a
    cycle. Step Repetition means repeating a STEP PATTERN (Read->Edit->Bash,
    Read->Edit->Bash, ...), so a window must contain at least two distinct
    tool names to count. Consecutive same-tool volume is still visible via
    `tool_calls_per_dispatch`, where it belongs.

    Windows are scanned shortest-first so the true cycle length is reported
    rather than a multiple of it (a Read,Bash cycle repeated 6 times is one
    finding of window=2/repeats=6, never window=4/repeats=3). Overlapping
    findings are suppressed: once a span is claimed, scanning resumes after
    it, so one long loop yields one finding rather than one per offset.
    """
    findings: list[dict[str, object]] = []
    total = len(names)
    i = 0
    while i < total:
        found: dict[str, object] | None = None
        max_window = (total - i) // min_repeats
        for window in range(min_len, max_window + 1):
            block = list(names[i : i + window])
            if len(set(block)) < 2:
                # A run of one tool is volume, not a cycle -- see docstring.
                continue
            repeats = 1
            j = i + window
            while j + window <= total and list(names[j : j + window]) == block:
                repeats += 1
                j += window
            if repeats >= min_repeats:
                found = {
                    "pattern": block,
                    "window": window,
                    "repeats": repeats,
                    "start": i,
                    "span": window * repeats,
                }
                break  # shortest genuine cycle wins
        if found is not None:
            findings.append(found)
            i = int(found["start"]) + int(found["span"])
        else:
            i += 1
    return findings


def loop_detection(
    projects_root: str,
    limit: int | None = None,
    min_len: int = 2,
    min_repeats: int = 3,
) -> dict[str, object]:
    """Dispatches showing repeated tool-call cycles.

    Denominator: transcripts with at least `min_len * min_repeats` tool calls
    (`n`) -- a transcript too short to contain the pattern is not evidence of
    its absence, so it is excluded from the denominator rather than counted as
    a clean pass. Partition: transcripts.
    """
    eligible = 0
    looping = 0
    examples: list[dict[str, object]] = []
    for agent_id, entries in _iter_transcripts(projects_root, limit):
        names = ordered_tool_calls(entries)
        if len(names) < min_len * min_repeats:
            continue
        eligible += 1
        findings = find_repeated_subsequences(names, min_len, min_repeats)
        if findings:
            looping += 1
            if len(examples) < 20:
                worst = max(findings, key=lambda f: int(f["span"]))
                examples.append({"agent_id": agent_id, "worst": worst})
    require_denominator(eligible, "loop_detection", "transcripts")
    return {
        "metric": "loop_detection",
        "partition": "transcripts",
        "n": eligible,
        "params": {"min_len": min_len, "min_repeats": min_repeats},
        "dispatches_with_loops": Value(looping, DERIVED, "repeated tool-call subsequences"),
        "rate": Value(round(looping / eligible, 4), DERIVED, "looping / eligible transcripts"),
        "examples": Value(examples, DERIVED, "worst repetition per looping dispatch"),
    }


# ---------------------------------------------------------------------------
# METRIC: true_duration
# ---------------------------------------------------------------------------


def transcript_span_seconds(entries: Sequence[Mapping[str, object]]) -> float | None:
    """max(timestamp) - min(timestamp) over one transcript, in seconds.

    Returns None when fewer than 2 parseable timestamps exist -- a single
    timestamp gives a span of 0, which would read as an instantaneous
    dispatch rather than an unmeasurable one.
    """
    stamps = [parse_ts(e.get("timestamp")) for e in entries]
    real = [s for s in stamps if s is not None]
    if len(real) < 2:
        return None
    return (max(real) - min(real)).total_seconds()


def true_duration(projects_root: str, limit: int | None = None) -> dict[str, object]:
    """Wall-clock dispatch span from transcripts, for ALL dispatches.

    Denominator: transcripts with >=2 parseable timestamps (`n`). Partition:
    transcripts -- this is the point of the metric, since it recovers a
    duration for the no-claim rows whose `duration_ms` is null, WITHOUT
    changing the hook.

    Wall-clock only: machine sleep inflates a span and there is no
    sleep-corrected clock available (plan §1.7). Spans above
    IMPLAUSIBLE_DURATION_SEC are counted and reported separately rather than
    being silently averaged in or silently dropped.
    """
    spans: list[float] = []
    unmeasurable = 0
    implausible = 0
    for _, entries in _iter_transcripts(projects_root, limit):
        span = transcript_span_seconds(entries)
        if span is None:
            unmeasurable += 1
            continue
        if span > IMPLAUSIBLE_DURATION_SEC:
            implausible += 1
            continue
        spans.append(span)
    n = len(spans)
    require_denominator(n, "true_duration", "transcripts")
    spans.sort()
    return {
        "metric": "true_duration",
        "partition": "transcripts",
        "n": n,
        "p50_sec": Value(percentile(spans, 0.50), DERIVED, "raw sorted transcript spans"),
        "p95_sec": Value(percentile(spans, 0.95), DERIVED, "raw sorted transcript spans"),
        "unmeasurable_transcripts": Value(
            unmeasurable, DERIVED, "fewer than 2 parseable timestamps"
        ),
        "implausible_spans_excluded": Value(
            implausible, DERIVED, f"span > {IMPLAUSIBLE_DURATION_SEC}s (wall-clock, sleep-inflated)"
        ),
    }


# ---------------------------------------------------------------------------
# METRIC: call_graph
# ---------------------------------------------------------------------------


def call_graph(projects_root: str) -> dict[str, object]:
    """Parent -> child dispatch tree from meta.json.

    Denominator: meta.json files indexed across both tree depths (`n`).
    Partition: meta tree.

    `parentAgentId` names the dispatching agent; `spawnDepth` gives the level.
    A parent id that does not resolve to an indexed agent is reported as an
    explicit `unresolved_parents` count -- never silently treated as a root,
    which would understate nesting.
    """
    index: dict[str, dict[str, object]] = {}
    for meta_path in iter_meta_paths(projects_root):
        agent_id = agent_id_from_path(meta_path)
        if not agent_id:
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict):
            index[agent_id] = meta

    n = len(index)
    require_denominator(n, "call_graph", "meta_tree")

    children: dict[str, list[str]] = defaultdict(list)
    depths: Counter[object] = Counter()
    with_parent = 0
    unresolved_parents = 0
    for agent_id, meta in index.items():
        depths[meta.get("spawnDepth")] += 1
        parent = meta.get("parentAgentId")
        if isinstance(parent, str) and parent:
            with_parent += 1
            children[parent].append(agent_id)
            if parent not in index:
                unresolved_parents += 1

    return {
        "metric": "call_graph",
        "partition": "meta_tree",
        "n": n,
        "depth_histogram": Value(
            {str(k): v for k, v in sorted(depths.items(), key=lambda kv: str(kv[0]))},
            DERIVED,
            "meta.json:spawnDepth",
        ),
        "rows_with_parent": Value(with_parent, ORIGINAL, "meta.json:parentAgentId"),
        "distinct_parents": Value(len(children), DERIVED, "meta.json:parentAgentId"),
        "unresolved_parents": Value(
            unresolved_parents, DERIVED, "parentAgentId not present in the meta index"
        ),
        "max_fanout": Value(
            max((len(v) for v in children.values()), default=0), DERIVED, "children per parent"
        ),
    }


# ---------------------------------------------------------------------------
# METRIC: session_metrics
# ---------------------------------------------------------------------------


def session_metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Per-session dispatch counts, spans, and concurrent-sessions-over-time.

    Denominator: JOINED rows (`n`). Partition: JOINED, mandatorily --
    `session` is null on 100% of no-claim rows, so a whole-ledger session
    metric would silently describe only the joined half while appearing to
    describe everything. The count of rows excluded for having no session is
    reported explicitly.

    The concurrency series is bucketed by UTC hour: distinct sessions with at
    least one dispatch in that hour. This is a lower bound on real
    concurrency (a session idle for an hour does not appear in it) and is
    labeled as such.
    """
    joined = joined_rows(rows)
    per_session: dict[str, list[datetime]] = defaultdict(list)
    dispatches: Counter[str] = Counter()
    undated = 0
    for row in joined:
        session = row.get("session")
        if not isinstance(session, str) or not session:
            continue
        dispatches[session] += 1
        stamp = parse_ts(row.get("ts"))
        if stamp is None:
            undated += 1
        else:
            per_session[session].append(stamp)

    n = len(dispatches)
    require_denominator(n, "session_metrics", JOINED)

    spans: list[float] = []
    for stamps in per_session.values():
        if len(stamps) >= 2:
            spans.append((max(stamps) - min(stamps)).total_seconds())
    spans.sort()

    hourly: dict[str, set[str]] = defaultdict(set)
    for session, stamps in per_session.items():
        for stamp in stamps:
            hourly[stamp.strftime("%Y-%m-%dT%H:00Z")].add(session)
    concurrency = {hour: len(sessions) for hour, sessions in sorted(hourly.items())}

    counts = sorted(float(c) for c in dispatches.values())
    return {
        "metric": "session_metrics",
        "partition": JOINED,
        "n": n,
        "excluded_rows_without_session": Value(
            len(rows) - len(joined), DERIVED, "rows outside the joined partition"
        ),
        "rows_without_parseable_ts": Value(undated, DERIVED, "spend.jsonl:ts"),
        "dispatches_per_session_p50": Value(
            percentile(counts, 0.50), DERIVED, "raw sorted per-session counts"
        ),
        "dispatches_per_session_p95": Value(
            percentile(counts, 0.95), DERIVED, "raw sorted per-session counts"
        ),
        "session_span_sec_p50": (
            Value(percentile(spans, 0.50), DERIVED, "raw sorted session spans")
            if spans
            else unattributable("no session had 2+ dated dispatches")
        ),
        "concurrent_sessions_by_hour": Value(
            concurrency, DERIVED, "distinct joined sessions per UTC hour"
        ),
        "peak_concurrent_sessions": Value(
            max(concurrency.values(), default=0), DERIVED, "max over the hourly series"
        ),
        "note": (
            "Concurrency is a LOWER BOUND: a session with no dispatch in an hour "
            "does not appear in that hour, even if it was running."
        ),
    }


# ---------------------------------------------------------------------------
# METRIC: cache_detail
# ---------------------------------------------------------------------------


def cache_detail(rows: Sequence[Mapping[str, object]], min_rows: int = 5) -> dict[str, object]:
    """Cache hit rate per agent_type.

    Denominator: rows carrying a tokens dict, after the activity collapse
    (`n`). Partition: ALL (tokens survive loss of join).

    Per-agent-type because a busted prefix is usually ONE agent's prompt
    change; a fleet-wide rate cannot localize it. Agent types with fewer than
    `min_rows` rows are reported in a separate `sparse` bucket rather than
    given a headline rate off a handful of samples.
    """
    kept, prep = prepare_rows(rows, BASIS_ACTIVITY)
    per_type: dict[str, dict[str, int]] = defaultdict(lambda: {"cache_read": 0, "denom": 0, "n": 0})
    for row in kept:
        tokens = row.get("tokens")
        if not isinstance(tokens, dict):
            continue
        vals = {}
        ok = True
        for field in ("cache_read", "cache_creation", "input"):
            value = tokens.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                ok = False
                break
            vals[field] = int(value)
        if not ok:
            continue
        name, _ = normalize_agent_type(row.get("agent_type"))
        bucket = per_type[name]
        bucket["cache_read"] += vals["cache_read"]
        bucket["denom"] += vals["cache_read"] + vals["cache_creation"] + vals["input"]
        bucket["n"] += 1

    n = sum(b["n"] for b in per_type.values())
    require_denominator(n, "cache_detail", "all")

    rates: dict[str, dict[str, object]] = {}
    sparse: dict[str, int] = {}
    for name, bucket in per_type.items():
        if bucket["n"] < min_rows:
            sparse[name] = bucket["n"]
            continue
        if bucket["denom"] <= 0:
            continue
        rates[name] = {"n": bucket["n"], "hit_rate": round(bucket["cache_read"] / bucket["denom"], 4)}

    return {
        "metric": "cache_detail",
        "partition": "all",
        "n": n,
        "basis": BASIS_ACTIVITY,
        "prep": prep,
        "min_rows_for_rate": min_rows,
        "by_agent_type": Value(
            dict(sorted(rates.items(), key=lambda kv: kv[1]["hit_rate"])),
            DERIVED,
            "cache_read / (cache_read + cache_creation + input) per agent_type",
        ),
        "sparse_agent_types": Value(
            dict(sorted(sparse.items())), DERIVED, f"fewer than {min_rows} rows -- no rate reported"
        ),
        "ttl_split": unattributable(
            "spend.jsonl collapses 5m and 1h cache writes into one cache_creation "
            "bucket -- this ledger alone cannot split them. ccdash CAN (see "
            "ccdash_cache_ttl_split() below): usage_events carries "
            "ephemeral_5m_tokens/ephemeral_1h_tokens as separate columns. This "
            "field stays unattributable because it is scoped to spend.jsonl "
            "specifically; it is not a claim that the split is unattributable "
            "fleet-wide."
        ),
    }


# ---------------------------------------------------------------------------
# ccdash-backed metrics (added 2026-09-05).
#
# WHY A SECOND SOURCE, AND WHAT EACH ONE OWNS:
#
#   money / tokens / model / cache  => ccdash (usage_events, 3.4M+ rows,
#                                       ZERO missing a model -- it parses
#                                       `message.usage` off the transcript
#                                       directly rather than depending on a
#                                       hook that can fail to fire)
#   agent_type (roster name)        => spend.jsonl ONLY. ccdash's
#                                       `agent_id` column has no matching
#                                       "which named agent was this" field
#                                       anywhere in a transcript record --
#                                       that attribution exists nowhere
#                                       except the hook-written ledger.
#
# The two are joined on `agent_id`, which is the SAME identifier space in
# both (verified 2026-09-05 by direct string comparison of live values, not
# assumed from column naming). See `ccdash_agent_type_join()` for the
# measured join rate and its honest reporting.
#
# Every function below returns `ccdash_available: False` with a plain-English
# reason -- never a crash, never a silent fallback to spend.jsonl wearing
# ccdash's label -- when ccdash is absent, empty, or its schema predates this
# module. `require_denominator` still applies once ccdash IS available: a
# ccdash metric with n=0 refuses exactly like a ledger metric does.
# ---------------------------------------------------------------------------

CCDASH_SOURCE = "ccdash:usage_events"

# `<synthetic>` is Claude Code's own internal marker for locally-injected
# messages that never hit the API (always 0 tokens). ccdash's own ingest
# already blocks it going forward (parser.py `_parse_usage_line`), but that
# filter never retroactively cleaned rows ingested before it existed, so it
# is excluded here too -- mirrors `aggregate.load_rows`'s own WHERE clause
# rather than re-deriving a different one.
_CCDASH_SYNTHETIC_MODEL = "<synthetic>"

# ONE BILLED API CALL, ONE ROW -- the fix for a 2.03x over-count (2026-09-05).
#
# Claude Code writes an assistant response to the transcript as ONE RECORD PER
# CONTENT BLOCK (thinking, text, tool_use, ...), and every one of those records
# repeats the SAME `message.usage` verbatim. ccdash ingests each record, so a
# naive `SUM(input_tokens)` over `usage_events` counts a single billed call
# once per block.
#
# Measured on the live store after a full re-parse: 1,348,569 usage rows but
# only 663,651 distinct `message_id` -- 2.032x. Verified mechanism on a live
# example: msg_011CeTpf... appears 3x in one file under ONE requestId, as
# thinking/text/tool_use, with byte-identical usage on all three.
#
# EVERY aggregate in this module therefore reads THIS subquery, never the raw
# table. `MIN(rowid)` picks exactly one representative row per API response;
# COALESCE falls back to `record_uuid` (then `rowid`) so a legacy row ingested
# before `message_id` existed forms its OWN group rather than collapsing every
# such row into one -- under-counting is not an acceptable cure for
# over-counting.
_CCDASH_DEDUPED = """(
    SELECT * FROM usage_events WHERE rowid IN (
        SELECT MIN(rowid) FROM usage_events
        GROUP BY COALESCE(message_id, record_uuid, CAST(rowid AS TEXT))
    )
)"""


_CCDASH_INGEST_DONE: dict[str, object] = {}


def _ccdash_ingest_once(conn: object) -> dict[str, object]:
    """Run ccdash's incremental scan AT MOST ONCE per process.

    `ccdash_status()` is called by every ccdash-backed metric (4 call sites),
    so an unguarded scan would run repeatedly within a single render. The
    result is memoized here and reused.

    A scan failure is NEVER fatal: it degrades to reading whatever is already
    stored, with the failure reported so a reader sees it rather than
    silently trusting stale data.
    """
    if _CCDASH_INGEST_DONE:
        return dict(_CCDASH_INGEST_DONE)  # type: ignore[arg-type]
    try:
        result = ccdash_parser.scan_and_ingest(conn) or {}
        out: dict[str, object] = {
            "ran": True,
            "reason": None,
            "records_ingested": result.get("records_ingested"),
            "files_with_new_data": result.get("files_with_new_data"),
        }
    except Exception as exc:  # noqa: BLE001 - staleness beats failure
        out = {"ran": False, "reason": f"{type(exc).__name__}: {exc}"}
    _CCDASH_INGEST_DONE.update(out)
    return dict(out)


def ccdash_status(ingest: bool = False) -> dict[str, object]:
    """Whether ccdash is usable right now, and why not when it isn't.

    Every ccdash-backed metric calls this first. A missing checkout, a
    missing/empty database file, or a query error are all reported here by
    plain-English reason rather than raised -- this is the one place that
    degradation is decided, so every metric below degrades identically.
    """
    if not CCDASH_AVAILABLE:
        return {
            "available": False,
            "reason": f"ccdash package not importable: {CCDASH_IMPORT_ERROR}",
        }
    try:
        db_path = ccdash_parser.DB_PATH
        if not os.path.exists(db_path):
            return {"available": False, "reason": f"no database file at {db_path}"}
        conn = ccdash_parser.get_connection()
        try:
            # FRESHNESS IS PART OF AVAILABILITY (2026-09-05).
            #
            # ccdash is an INCREMENTAL scanner: it only ingests when someone
            # runs it, and nothing on this machine runs it automatically.
            # Measured this date: its last scan was 2026-09-03, so the store
            # was missing 181,807 records -- 45% of the 7-day window. Every
            # dollar and every share computed from it was correspondingly
            # understated, and NOTHING said so, because a stale database
            # answers every query perfectly well. That is the exact failure
            # class this module exists to prevent: a plausible number with no
            # visible defect.
            #
            # So: ingest before reading. The scan is incremental and cheap
            # (12s for 2 days of backlog; a no-op scan is far faster), and a
            # scan failure is NEVER fatal -- it degrades to reading whatever
            # is already stored, with the staleness REPORTED rather than
            # hidden. The caller renders `scan` so a reader can see whether
            # they are looking at fresh data.
            scan: dict[str, object] = {"ran": False, "reason": "not requested"}
            if ingest:
                scan = _ccdash_ingest_once(conn)

            n = conn.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]
            last_scan = None
            try:
                row = conn.execute(
                    "SELECT value FROM scan_meta WHERE key = 'last_scan_at'"
                ).fetchone()
                last_scan = row[0] if row else None
            except Exception:  # noqa: BLE001 - scan_meta is advisory only
                last_scan = None
        finally:
            conn.close()
        if n == 0:
            return {"available": False, "reason": "usage_events table is empty"}
        return {
            "available": True,
            "reason": None,
            "row_count": n,
            "last_scan_at": last_scan,
            "scan": scan,
        }
    except Exception as exc:  # pragma: no cover - defensive, any sqlite/schema error
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


def _ccdash_connect() -> object:
    """A fresh connection. Callers are responsible for closing it."""
    return ccdash_parser.get_connection()


def _ccdash_window_clause(since_iso: str | None) -> tuple[str, list[object]]:
    if since_iso is None:
        return "", []
    return " AND timestamp_utc >= ?", [since_iso]


def ccdash_token_split(since_iso: str | None = None) -> dict[str, object]:
    """Subagent (sidechain) vs main-thread token split, from COMPLETE data.

    Denominator: ccdash usage_events rows in the window (`n`). Partition:
    all -- `is_sidechain` is populated on every row, unconditionally (it is
    read straight off the transcript record's own `isSidechain` field at
    parse time, not derived from a join that can fail).

    This is a headline-grade fact spend.jsonl could never show: spend.jsonl
    has no `is_sidechain`-equivalent field at all, and even if it did, 52.5%
    of its rows have no model to price against. Measured 2026-09-05 over a
    7-day window: 78% of tokens ran inside a dispatched sub-agent, not the
    main thread -- exactly the "who actually spends" question the ledger
    alone cannot answer.
    """
    status = ccdash_status()
    if not status["available"]:
        return {
            "metric": "ccdash_token_split",
            "ccdash_available": False,
            "reason": status["reason"],
        }
    where, params = _ccdash_window_clause(since_iso)
    conn = _ccdash_connect()
    try:
        rows = conn.execute(
            f"""
            SELECT is_sidechain, COUNT(*),
                   SUM(input_tokens), SUM(output_tokens),
                   SUM(cache_creation_input_tokens), SUM(cache_read_input_tokens)
            FROM {_CCDASH_DEDUPED}
            WHERE model != ?{where}
            GROUP BY is_sidechain
            """,
            [_CCDASH_SYNTHETIC_MODEL] + params,
        ).fetchall()
    finally:
        conn.close()

    by_flag: dict[int, dict[str, int]] = {}
    for is_sidechain, count, inp, out, cache_creation, cache_read in rows:
        tokens = (inp or 0) + (out or 0) + (cache_creation or 0) + (cache_read or 0)
        by_flag[int(is_sidechain)] = {"rows": int(count), "tokens": int(tokens)}

    subagent = by_flag.get(1, {"rows": 0, "tokens": 0})
    main = by_flag.get(0, {"rows": 0, "tokens": 0})
    total_rows = subagent["rows"] + main["rows"]
    total_tokens = subagent["tokens"] + main["tokens"]
    require_denominator(total_rows, "ccdash_token_split", "all")

    return {
        "metric": "ccdash_token_split",
        "ccdash_available": True,
        "partition": "all",
        "n": total_rows,
        "source": CCDASH_SOURCE,
        "subagent_rows": Value(subagent["rows"], ORIGINAL, CCDASH_SOURCE),
        "subagent_tokens": Value(subagent["tokens"], ORIGINAL, CCDASH_SOURCE),
        "main_thread_rows": Value(main["rows"], ORIGINAL, CCDASH_SOURCE),
        "main_thread_tokens": Value(main["tokens"], ORIGINAL, CCDASH_SOURCE),
        "subagent_token_share": (
            Value(round(subagent["tokens"] / total_tokens, 4), DERIVED, "subagent tokens / total tokens")
            if total_tokens > 0
            else unattributable("no tokens in window")
        ),
        "note": (
            "Every usage_events row carries is_sidechain unconditionally (parsed "
            "off the transcript's own isSidechain field), so this split has no "
            "excluded population the way a join-dependent ledger metric would."
        ),
    }


def ccdash_cache_ttl_split(since_iso: str | None = None) -> dict[str, object]:
    """Cache WRITE token split by TTL: 5-minute vs 1-hour.

    Denominator: ccdash usage_events rows in the window (`n`). Partition:
    all. `cache_detail()`'s ttl_split field (spend.jsonl-sourced) is
    UNATTRIBUTABLE because spend.jsonl collapses both TTLs into one
    `cache_creation` bucket -- ccdash does not have that limitation:
    `ephemeral_5m_tokens`/`ephemeral_1h_tokens` are separate columns, parsed
    directly off the transcript's `usage.cache_creation` block (see
    ccdash/parser.py `_parse_usage_line`). This function is what makes that
    split ORIGINAL provenance rather than unattributable.

    A read with no TTL breakdown reported by the API is treated as the
    default 5-minute TTL (ccdash's own ingest-time rule, not re-derived
    here) -- so `ephemeral_1h_tokens` is a genuine lower bound only where the
    API omits the breakdown, which `parser.py` already documents.
    """
    status = ccdash_status()
    if not status["available"]:
        return {
            "metric": "ccdash_cache_ttl_split",
            "ccdash_available": False,
            "reason": status["reason"],
        }
    where, params = _ccdash_window_clause(since_iso)
    conn = _ccdash_connect()
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(*), SUM(ephemeral_5m_tokens), SUM(ephemeral_1h_tokens),
                   SUM(cache_read_input_tokens)
            FROM {_CCDASH_DEDUPED}
            WHERE model != ?{where}
            """,
            [_CCDASH_SYNTHETIC_MODEL] + params,
        ).fetchone()
    finally:
        conn.close()

    n, writes_5m, writes_1h, reads = row
    n = int(n or 0)
    require_denominator(n, "ccdash_cache_ttl_split", "all")
    writes_5m = int(writes_5m or 0)
    writes_1h = int(writes_1h or 0)
    reads = int(reads or 0)
    total_writes = writes_5m + writes_1h

    return {
        "metric": "ccdash_cache_ttl_split",
        "ccdash_available": True,
        "partition": "all",
        "n": n,
        "source": CCDASH_SOURCE,
        "writes_5m_tokens": Value(writes_5m, ORIGINAL, "usage_events.ephemeral_5m_tokens"),
        "writes_1h_tokens": Value(writes_1h, ORIGINAL, "usage_events.ephemeral_1h_tokens"),
        "cache_read_tokens": Value(reads, ORIGINAL, "usage_events.cache_read_input_tokens"),
        "share_1h_of_writes": (
            Value(round(writes_1h / total_writes, 4), DERIVED, "1h writes / (5m writes + 1h writes)")
            if total_writes > 0
            else unattributable("no cache writes in window")
        ),
        "note": (
            "A read with no TTL breakdown in the API response is counted as 5m "
            "(the API's own default TTL, applied at ccdash ingest time -- see "
            "ccdash/parser.py), so writes_1h_tokens is a genuine figure, not "
            "estimated, wherever the API actually reports the breakdown."
        ),
    }


def ccdash_spend_by_model(since_iso: str | None = None) -> dict[str, object]:
    """Per-model-family USD spend from ccdash's COMPLETE token data.

    Denominator: ccdash usage_events rows in the window (`n`). Partition:
    all. Priced through `ccdash.pricing.compute_cost_usd` -- NOT a fourth
    pricing table. Unpriced rows (unknown model, or a model string ccdash's
    table has no entry for) are counted and excluded, never priced at $0,
    mirroring the exact discipline `spend_usd()` already applies to
    spend.jsonl.

    This is the metric that recovers Fable's real spend share: spend.jsonl
    can only ever show Fable rows the ledger hook actually wrote (measured
    2026-09-05: 15 rows, ~$388, 1.9% of a $20,316 total), because most of
    Fable's usage is subagent work the hook under-captures. ccdash reads the
    transcript directly and is not subject to that gap (measured the same
    day: 73,566 rows, ~$9,255, ~32% of a $28,820 total over the same 7-day
    window) -- this function is what surfaces the corrected figure.
    """
    status = ccdash_status()
    if not status["available"]:
        return {
            "metric": "ccdash_spend_by_model",
            "ccdash_available": False,
            "reason": status["reason"],
        }
    where, params = _ccdash_window_clause(since_iso)
    conn = _ccdash_connect()
    try:
        rows = conn.execute(
            f"""
            SELECT model, timestamp_utc, input_tokens, output_tokens,
                   ephemeral_5m_tokens, ephemeral_1h_tokens, cache_read_input_tokens
            FROM {_CCDASH_DEDUPED}
            WHERE model != ?{where}
            """,
            [_CCDASH_SYNTHETIC_MODEL] + params,
        ).fetchall()
    finally:
        conn.close()

    n = len(rows)
    require_denominator(n, "ccdash_spend_by_model", "all")

    by_model: dict[str, float] = defaultdict(float)
    unpriced_rows = 0
    unpriced_models: Counter[str] = Counter()
    total = 0.0
    priced = 0
    for model, ts, inp, out, cache_5m, cache_1h, cache_read in rows:
        when = parse_ts(ts) or datetime.now(timezone.utc)
        cost = ccdash_pricing.compute_cost_usd(
            model, when, inp or 0, out or 0, cache_5m or 0, cache_1h or 0, cache_read or 0
        )
        if cost is None:
            unpriced_rows += 1
            unpriced_models[model or "(no model)"] += 1
            continue
        priced += 1
        total += cost
        by_model[model] += cost

    coverage = priced / n if n else 0.0

    return {
        "metric": "ccdash_spend_by_model",
        "ccdash_available": True,
        "partition": "all",
        "n": priced,
        "rows_seen": n,
        "source": CCDASH_SOURCE,
        "total_usd": Value(round(total, 4), DERIVED, "ccdash.pricing.compute_cost_usd over usage_events"),
        "by_model": Value(
            {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
            DERIVED,
            "priced usage_events rows by model id",
        ),
        "unpriceable": {
            "rows": Value(unpriced_rows, DERIVED, "rows ccdash.pricing.compute_cost_usd refused"),
            "by_model": Value(dict(unpriced_models), DERIVED, "unpriced model id -> row count"),
            "note": (
                "Excluded from total_usd, never priced at $0 -- mirrors spend_usd()'s "
                "own discipline. Real spend is HIGHER than total_usd by an unknown "
                "amount when this is nonzero."
            ),
        },
        "pricing_coverage": Value(round(coverage, 4), DERIVED, "priced rows / rows_seen"),
    }


def ccdash_agent_type_join(
    rows: Sequence[Mapping[str, object]], since_iso: str | None = None
) -> dict[str, object]:
    """Per-agent-TYPE spend, from ccdash's COMPLETE token data joined to
    spend.jsonl's agent_type by `agent_id`.

    This is the single highest-value join available: ccdash has complete
    money/tokens but no agent_type field anywhere (a transcript record
    carries no "which named agent produced this" field); spend.jsonl has
    agent_type but only for the ~48% of rows a hook managed to price.
    Joining on `agent_id` (the SAME identifier space in both -- verified
    2026-09-05 by direct string comparison of live values) recovers
    per-agent-type spend at ccdash's completeness rather than the ledger's.

    THE JOIN RATE IS REPORTED, NEVER ASSUMED CLEAN (task constraint: measure
    honestly, fall back if poor). Measured 2026-09-05:
      - lifetime: only 11% of ccdash rows join to a ledger agent_id, because
        spend.jsonl rolls off at ~11 days while ccdash retains full history.
      - within a 7-day window (spend.jsonl's own retention horizon): 88% of
        ccdash rows in that window join to a ledger agent_id carrying a real
        agent_type.
    So this function is only meaningful WINDOWED to spend.jsonl's retention
    horizon, and the caller MUST pass `since_iso` -- an unwindowed call
    would silently report a technically-true but badly-misleading 11%
    figure as if it were the metric's normal operating point. Rows whose
    agent_id has no ledger match at all are counted separately from rows
    whose agent_id matches but whose agent_type is itself missing/generic --
    both are real populations and neither is folded into the other.
    """
    status = ccdash_status()
    if not status["available"]:
        return {
            "metric": "ccdash_agent_type_join",
            "ccdash_available": False,
            "reason": status["reason"],
        }
    if since_iso is None:
        return {
            "metric": "ccdash_agent_type_join",
            "ccdash_available": True,
            "error": (
                "since_iso is required: this join is only meaningful windowed to "
                "spend.jsonl's retention horizon (~11 days) -- see docstring."
            ),
            "renderable": False,
        }

    # Build the agent_id -> agent_type map from the SAME rows every other
    # ledger metric uses (no separate re-read), deduped identically via
    # prepare_rows so a duplicated ledger row cannot double-count in the map
    # (a map is keyed by agent_id anyway so duplicates simply overwrite, but
    # running through prepare_rows keeps this function reading the same
    # "kept" population every other metric on this module reports over).
    kept, prep = prepare_rows(rows, BASIS_ACTIVITY)
    agent_id_to_type: dict[str, str] = {}
    agent_id_has_real_type: dict[str, bool] = {}
    for row in kept:
        agent_id = row.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        name, prov = normalize_agent_type(row.get("agent_type"))
        agent_id_to_type[agent_id] = name
        agent_id_has_real_type[agent_id] = prov == ORIGINAL and name not in GENERIC_AGENT_TYPES

    typed_ids = [aid for aid, ok in agent_id_has_real_type.items() if ok]

    where, params = _ccdash_window_clause(since_iso)
    conn = _ccdash_connect()
    try:
        total_n = conn.execute(
            f"SELECT COUNT(*) FROM {_CCDASH_DEDUPED} WHERE model != ?{where}",
            [_CCDASH_SYNTHETIC_MODEL] + params,
        ).fetchone()[0]
        if typed_ids:
            placeholders = ",".join("?" * len(typed_ids))
            join_rows = conn.execute(
                f"""
                SELECT agent_id, model, timestamp_utc, input_tokens, output_tokens,
                       ephemeral_5m_tokens, ephemeral_1h_tokens, cache_read_input_tokens
                FROM {_CCDASH_DEDUPED}
                WHERE model != ?{where} AND agent_id IN ({placeholders})
                """,
                [_CCDASH_SYNTHETIC_MODEL] + params + typed_ids,
            ).fetchall()
        else:
            join_rows = []
    finally:
        conn.close()

    total_n = int(total_n or 0)
    require_denominator(total_n, "ccdash_agent_type_join", "all")

    joined_n = len(join_rows)
    join_rate = joined_n / total_n if total_n else 0.0

    by_type: dict[str, float] = defaultdict(float)
    # MODEL MIX PER AGENT TYPE (added 2026-09-05).
    #
    # `by_type` alone answers "what does each agent cost", which is only half
    # of the decision an operator actually makes. The real question is "which
    # agent should move to a cheaper model", and that needs the MODEL
    # dimension kept rather than summed away: an agent type costing $6k
    # entirely on opus is a candidate to re-pin; the same $6k spread across
    # sonnet at high volume is not. Keeping this costs one extra dict.
    by_type_model: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    calls_by_type: dict[str, int] = defaultdict(int)
    priced = 0
    unpriceable = 0
    for agent_id, model, ts, inp, out, cache_5m, cache_1h, cache_read in join_rows:
        when = parse_ts(ts) or datetime.now(timezone.utc)
        cost = ccdash_pricing.compute_cost_usd(
            model, when, inp or 0, out or 0, cache_5m or 0, cache_1h or 0, cache_read or 0
        )
        if cost is None:
            unpriceable += 1
            continue
        priced += 1
        _t = agent_id_to_type[agent_id]
        by_type[_t] += cost
        by_type_model[_t][model] += cost
        calls_by_type[_t] += 1

    # Falls back honestly rather than presenting a poor join as complete: a
    # join rate below this is reported as unreliable rather than hidden.
    # 50% is not a "declared threshold" claim of any deeper significance --
    # it is the same "more wrong than right" line every other partition
    # denominator check in this module already uses via require_denominator
    # (n<=0 refuses entirely; this is that same idea applied to a rate
    # rather than a count).
    reliable = join_rate >= 0.50

    return {
        "metric": "ccdash_agent_type_join",
        "ccdash_available": True,
        "partition": "all",
        "n": joined_n,
        "source": f"{CCDASH_SOURCE} JOIN spend.jsonl:agent_type ON agent_id",
        "window_start": since_iso,
        "total_ccdash_rows_in_window": Value(total_n, ORIGINAL, CCDASH_SOURCE),
        "joined_rows": Value(joined_n, DERIVED, "ccdash rows whose agent_id matched a ledger agent_type"),
        "join_rate": Value(round(join_rate, 4), DERIVED, "joined_rows / total_ccdash_rows_in_window"),
        "reliable": reliable,
        "by_agent_type_usd": Value(
            {k: round(v, 4) for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])},
            DERIVED,
            "priced+joined ccdash rows summed by ledger agent_type",
        ),
        "by_agent_type_model_usd": Value(
            {
                t: {m: round(v, 4) for m, v in sorted(mm.items(), key=lambda kv: -kv[1])}
                for t, mm in sorted(by_type_model.items(), key=lambda kv: -sum(kv[1].values()))
            },
            DERIVED,
            "priced+joined ccdash rows summed by (agent_type, model)",
        ),
        "calls_by_agent_type": Value(
            dict(sorted(calls_by_type.items(), key=lambda kv: -kv[1])),
            DERIVED,
            "priced+joined ccdash usage records per agent_type",
        ),
        "priced": Value(priced, DERIVED, "joined rows ccdash.pricing could price"),
        "unpriceable_joined_rows": Value(unpriceable, DERIVED, "rows joined but unpriceable"),
        "prep": prep,
        "note": (
            f"{'RELIABLE' if reliable else 'LOW CONFIDENCE'}: {round(100 * join_rate, 1)}% of "
            f"ccdash rows in this window matched a spend.jsonl agent_id carrying a "
            f"real agent_type. This join rate depends entirely on spend.jsonl's "
            f"~11-day retention overlapping the requested window -- it is NOT a "
            f"property of the join itself, and will read near-zero for any window "
            f"spend.jsonl no longer covers."
        ),
    }


# ---------------------------------------------------------------------------
# METRIC: account_capacity -- ADDED 2026-09-06 (operator finding).
#
# WHY THIS EXISTS: the operator pays six Claude Max seats at $200/mo each
# ($1,200/mo FIXED, not metered API billing) -- the console shows only
# "percent of quota used," no dollars, no credits. Marginal cost per call is
# therefore effectively ZERO, and the scarce resource is QUOTA per account,
# not dollars. The question this metric answers is "am I load-balancing
# across the capacity I already pay for," which no existing panel on this
# page could answer: `dispatch_counts()` has no account dimension at all
# (spend.jsonl never wrote one), and every dollar tile above is priced
# per-CALL, never per-ACCOUNT.
#
# SOURCE: ccdash's `session_accounts` table (session_id -> account email),
# joined to the SAME deduped `usage_events` subquery every other ccdash
# metric in this module reads (`_CCDASH_DEDUPED`), on
# `usage_events.top_session_id = session_accounts.session_id`. Measured
# 2026-09-06: 100% of usage_events rows in the last 7 days joined to a real
# account email (193,411 of 193,411) -- so unlike `ccdash_agent_type_join()`,
# this join needs no reliability floor; it is reported anyway, per row, so a
# future regression is visible rather than assumed away.
# ---------------------------------------------------------------------------

# The "quiet" threshold for the imbalance signal: an account holding less than
# this SHARE of the busiest account's usage IN THE WINDOW counts as quiet
# relative to it. Not a claim that 10% is a universal line -- it is the one
# used to COUNT quiet accounts, and the actual per-account shares are always
# returned alongside it so a reader can re-judge with a different threshold.
ACCOUNT_QUIET_RELATIVE_SHARE = 0.10

# Claude Max quota resets MONTHLY, so a capacity question has exactly one
# correct denominator: the billing period. This is not a tunable preference --
# reading a 7-day slice of a monthly quota cycle is not a smaller version of
# the same picture, it is a DIFFERENT and misleading one.
#
# Measured 2026-09-06, same query, same six accounts:
#     7 days:  82.0 / 8.6 / 4.2 / 2.0 / 1.7 / 1.5   -- looks catastrophically skewed
#    30 days:  34.9 / 18.7 / 15.2 / 11.8 / 10.4 / 9.0 -- genuinely balanced
# The operator confirmed they use all six accounts fully every month. Only the
# 30-day figure was true; the 7-day one nearly produced a recommendation to
# consolidate seats that are actively in use.
BILLING_PERIOD_DAYS = 30

# SCOPE LIMIT, stated once here and surfaced on the page: this metric sees only
# CLAUDE CODE transcripts on THIS machine. The Anthropic console's
# percent-of-quota also reflects claude.ai web and Desktop usage, which is
# invisible here. So these shares are "share of Claude Code work", NEVER
# "share of quota consumed", and they will not reconcile with the console.
ACCOUNT_SHARE_SCOPE_NOTE = (
    "share of Claude Code work on this machine -- NOT share of quota consumed; "
    "claude.ai web and Desktop usage also draw on the same quota and are "
    "invisible to this data, so these will not match the console's percentages"
)


def account_capacity(since_iso: str | None = None) -> dict[str, object]:
    """Per-account usage share, from the ccdash join to `session_accounts`.

    Denominator: ccdash usage_events rows in the window that join to a real
    account email (`n`). Partition: all -- unlike `ccdash_agent_type_join()`,
    this join has no measured reliability gap (see module note above), so no
    row is silently excluded from the denominator the way an unreliable join
    would need to disclose.

    Returns per-account: calls, tokens, api_equivalent_usd (priced through
    `ccdash.pricing.compute_cost_usd` -- the SAME table `ccdash_spend_by_
    model()` already uses, never a second one), share of total calls, and a
    DAILY calls series (UTC day) so a caller can plot a load-balance trend,
    not just a snapshot.

    `imbalance` states, with its own denominator: the share held by the
    busiest account, and the COUNT of accounts under
    `ACCOUNT_QUIET_RELATIVE_SHARE` of the busiest account's call volume --
    both numbers, never a bare verdict, because "imbalanced" alone is
    unfalsifiable the same way a bare percentage is (see this module's
    `pct()`-equivalent discipline in the renderer).

    WINDOWING CAUTION (added 2026-09-06, operator-verified correction): this
    function reports relative shares WITHIN whatever `since_iso` window the
    caller passes -- it takes no position on which window is the right one
    for a capacity decision, and a caller must pick deliberately. Claude Max
    quota resets MONTHLY, so a 30-day (billing-period) call and a 7-day call
    against the SAME accounts can disagree in DIRECTION, not just magnitude:
    measured live, a 7-day call showed one account at 82% with four flagged
    `idle_accounts`, while the 30-day call over the same six accounts showed
    a genuinely balanced 35/19/15/12/10/9 split with ZERO idle accounts. A
    caller that renders `imbalance.idle_accounts` off a short window as a
    capacity verdict is reproducing exactly that mistake -- see
    `~/.claude/scripts/render_agent_telemetry.py`'s `account_balance_tile()`
    for the corrected pattern (always compute and show both windows,
    never one alone). Also note: `email` here is scoped to Claude Code
    activity only (`session_accounts`, itself sourced from
    `~/.claude.json`'s active account at each Claude Code session start) --
    it has no visibility into claude.ai web or Desktop usage, so a share
    computed here is "share of Claude Code work," never "share of quota
    consumed" on the account's own console.
    """
    status = ccdash_status()
    if not status["available"]:
        return {
            "metric": "account_capacity",
            "ccdash_available": False,
            "reason": status["reason"],
        }
    where, params = _ccdash_window_clause(since_iso)
    conn = _ccdash_connect()
    try:
        # LEFT JOIN, never INNER: a usage row whose top_session_id has no
        # session_accounts match must be COUNTED as unattributed, not
        # silently dropped from the population this metric describes.
        # Column set mirrors `ccdash_spend_by_model()`'s own query exactly
        # (cache writes as ephemeral_5m/1h, never a redundant third
        # cache-creation column) so the two functions can never silently
        # price the same row two different ways.
        #
        # `session_accounts` is written by a SEPARATE hook
        # (usage-dashboard/hooks/session_account_snapshot.py), not by
        # ccdash_parser's own schema -- so a usage_events database that
        # genuinely has rows but has never had that hook run against it
        # (a fresh checkout, or any machine that ingested history before
        # the hook existed) is missing this table entirely. `ccdash_status()`
        # only checks `usage_events`, so that omission reaches this query
        # unguarded; degrade explicitly here rather than let a raw
        # OperationalError escape past this metric's own `ccdash_available`
        # contract.
        try:
            rows = conn.execute(
                f"""
                SELECT sa.email, u.timestamp_utc,
                       u.input_tokens, u.output_tokens,
                       u.ephemeral_5m_tokens, u.ephemeral_1h_tokens,
                       u.cache_read_input_tokens, u.model
                FROM {_CCDASH_DEDUPED} u
                LEFT JOIN session_accounts sa ON sa.session_id = u.top_session_id
                WHERE u.model != ?{where}
                """,
                [_CCDASH_SYNTHETIC_MODEL] + params,
            ).fetchall()
        except Exception as exc:  # noqa: BLE001 - missing session_accounts table
            return {
                "metric": "account_capacity",
                "ccdash_available": False,
                "reason": (
                    f"session_accounts join failed ({type(exc).__name__}: {exc}) -- this "
                    "table is written by a separate hook (session_account_snapshot.py) and "
                    "may not exist on a database that has never had it run"
                ),
            }
    finally:
        conn.close()

    total_rows = len(rows)
    require_denominator(total_rows, "account_capacity", "all")

    per_account: dict[str, dict[str, object]] = {}
    per_account_daily: dict[str, Counter[str]] = defaultdict(Counter)
    unattributed_rows = 0
    total_calls_attributed = 0

    for email, ts, inp, out, cache_5m, cache_1h, cache_read, model in rows:
        if not email:
            unattributed_rows += 1
            continue
        bucket = per_account.setdefault(
            email, {"calls": 0, "tokens": 0, "api_equivalent_usd": 0.0, "unpriced_calls": 0}
        )
        bucket["calls"] = int(bucket["calls"]) + 1
        total_calls_attributed += 1
        tokens = (inp or 0) + (out or 0) + (cache_5m or 0) + (cache_1h or 0) + (cache_read or 0)
        bucket["tokens"] = int(bucket["tokens"]) + int(tokens)
        day = day_of(ts)
        if day:
            per_account_daily[email][day] += 1
        when = parse_ts(ts) or datetime.now(timezone.utc)
        cost = ccdash_pricing.compute_cost_usd(
            model, when, inp or 0, out or 0, cache_5m or 0, cache_1h or 0, cache_read or 0
        )
        if cost is None:
            bucket["unpriced_calls"] = int(bucket["unpriced_calls"]) + 1
        else:
            bucket["api_equivalent_usd"] = round(float(bucket["api_equivalent_usd"]) + cost, 4)

    require_denominator(total_calls_attributed, "account_capacity", "attributed")

    accounts: dict[str, dict[str, object]] = {}
    for email, bucket in per_account.items():
        calls = int(bucket["calls"])
        accounts[email] = {
            "calls": Value(calls, ORIGINAL, "ccdash:usage_events JOIN session_accounts"),
            "tokens": Value(int(bucket["tokens"]), ORIGINAL, "ccdash:usage_events"),
            "api_equivalent_usd": Value(
                float(bucket["api_equivalent_usd"]), DERIVED, "ccdash.pricing.compute_cost_usd"
            ),
            "unpriced_calls": Value(int(bucket["unpriced_calls"]), DERIVED, "model unpriceable"),
            "share_of_attributed_calls": Value(
                round(calls / total_calls_attributed, 4),
                DERIVED,
                "account calls / total attributed calls",
            ),
            "daily_calls": Value(
                dict(sorted(per_account_daily[email].items())), DERIVED, "calls per UTC day"
            ),
        }

    # `require_denominator(total_calls_attributed, ...)` above already
    # refused when there were zero attributed accounts, so `ranked` is
    # guaranteed non-empty here -- no fallback branch is needed for an
    # empty-accounts case that cannot reach this line.
    # How many days this window actually covers -- needed to say whether the
    # shares below can be trusted for a CAPACITY judgement at all.
    window_days: int | None = None
    if since_iso:
        _start = parse_ts(since_iso)
        if _start is not None:
            window_days = max(1, (datetime.now(timezone.utc) - _start).days)

    ranked = sorted(accounts.items(), key=lambda kv: -int(kv[1]["calls"].value))
    busiest_email, busiest_share = ranked[0][0], float(ranked[0][1]["share_of_attributed_calls"].value)
    quiet_threshold = busiest_share * ACCOUNT_QUIET_RELATIVE_SHARE
    # NAMED "quiet", NOT "idle" -- the distinction is the whole finding.
    #
    # An earlier version called these accounts IDLE, which asserts a conclusion
    # this data cannot support and which turned out to be FALSE. Measured
    # 2026-09-06 over the identical query: across 7 days one account held 82%
    # and the other five looked abandoned; across 30 days the SAME six accounts
    # split 34.9 / 18.7 / 15.2 / 11.8 / 10.4 / 9.0 -- genuinely balanced. The
    # operator confirmed they use all six fully every month. The short window
    # manufactured the imbalance.
    #
    # "Quiet in this window" is what the numbers actually say. "Idle" is a
    # claim about the account, and it nearly drove a recommendation to
    # consolidate seats the operator actively uses.
    quiet_accounts = [
        email
        for email, acct in accounts.items()
        if email != busiest_email and float(acct["share_of_attributed_calls"].value) < quiet_threshold
    ]

    return {
        "metric": "account_capacity",
        "ccdash_available": True,
        "partition": "all",
        "n": total_calls_attributed,
        "source": "ccdash:usage_events JOIN session_accounts ON top_session_id",
        "accounts": accounts,
        "accounts_ranked": [(email, int(acct["calls"].value)) for email, acct in ranked],
        "unattributed_rows": Value(
            unattributed_rows, DERIVED, "usage_events row whose top_session_id has no session_accounts match"
        ),
        "total_rows_seen": total_rows,
        "imbalance": {
            "busiest_account": busiest_email,
            "busiest_share": Value(
                round(busiest_share, 4),
                DERIVED,
                "busiest account's calls / total attributed calls",
            ),
            "quiet_relative_share_threshold": ACCOUNT_QUIET_RELATIVE_SHARE,
            "quiet_accounts": Value(
                sorted(quiet_accounts),
                DERIVED,
                f"accounts under {ACCOUNT_QUIET_RELATIVE_SHARE:.0%} of the busiest "
                f"account's calls IN THIS WINDOW -- quiet here, never 'idle'",
            ),
            "quiet_account_count": Value(len(quiet_accounts), DERIVED, "len(quiet_accounts)"),
            "window_days": window_days,
            "window_covers_billing_period": (
                window_days is not None and window_days >= BILLING_PERIOD_DAYS
            ),
            "account_count": Value(len(accounts), DERIVED, "distinct attributed account emails"),
            "scope_note": ACCOUNT_SHARE_SCOPE_NOTE,
            "window_warning": (
                None
                if (window_days is not None and window_days >= BILLING_PERIOD_DAYS)
                else (
                    f"This window is {window_days or 'unbounded'} day(s); Claude Max quota "
                    f"resets every {BILLING_PERIOD_DAYS} days. A short window over a monthly "
                    f"quota cycle MISREADS as imbalance -- measured on this very data, 7 days "
                    f"showed 82% on one account while 30 days showed a balanced 35/19/15/12/10/9 "
                    f"across the same six. Use the {BILLING_PERIOD_DAYS}-day figure for any "
                    f"capacity decision; read a short window only as 'what is happening now'."
                )
            ),
            "note": (
                "Denominator for every share above is ATTRIBUTED calls "
                f"({total_calls_attributed:,} of {total_rows:,} rows seen); "
                f"{unattributed_rows:,} rows had no session_accounts match and are "
                "excluded from every account's share, never folded into one."
            ),
        },
    }


# ---------------------------------------------------------------------------
# METRIC: quality_outcomes -- ADDED 2026-09-06 (operator finding).
#
# WHY THIS EXISTS: dollars and dispatch counts describe VOLUME; they say
# nothing about whether the work produced was any GOOD. The estimate-engine
# self-correcting loop already records exactly that judgment on every trade
# dispatch (CONCUR/DISSENT verdicts) and every raised finding
# (consolidator_decision) -- this metric surfaces it rather than leaving it
# unread in ~/.claude/telemetry/cycles/.
#
# SOURCE: `cycle_telemetry.read_cycles()` (imported, never re-globbed -- see
# the module-level import note above). Reads EVERY system's cycle records
# (system=None), because the honesty/quality question this metric answers is
# not scoped to one system's name.
# ---------------------------------------------------------------------------

# A trade/agent dissent rate off too few verdicts is the same "one data point
# wearing a statistical costume" failure `P99_MIN_SAMPLES` already guards
# against for latency. Measured live: several dispatch_label prefixes carry
# only 3 or 9 verdicts total (see module docstring measurement) -- far too
# few to rate. This floor is deliberately much lower than P99_MIN_SAMPLES
# (100): a dissent RATE is a simple proportion computed from ALL of n, not a
# tail statistic that needs many samples to stabilize, so the failure mode
# this guards against is a rate off a literal handful of verdicts (n<10),
# not the percentile-specific "no data point represents the tail" problem.
# Round numbers that never existed, as opposed to rounds whose record is
# missing. Verified 2026-09-06 against the reviewed_scenarios ledger, whose
# full inventory is 1, 2, 4-8, 10-18, 18p -- no rows for 3 or 9 in ANY archive
# file, so nothing was lost and the early rounds were renumbered. Kept as a
# declared constant rather than inferred, because absence cannot distinguish
# "never ran" from "lost" without consulting the authoritative source.
KNOWN_NEVER_RAN_ROUNDS: frozenset[int] = frozenset({3, 9})

DISSENT_RATE_MIN_VERDICTS = 10

# `trade_round_N` is the only round-numbered cycle_id shape observed; other
# cycle_ids (`gcreview_demo_2026-09-05`, `B0-2026-08-28-blind`) carry no
# round number at all and are excluded from the per-round convergence
# series -- they still count toward every OTHER total on this metric.
_ROUND_ID_RE = re.compile(r"^trade_round_(\d+)$")


def _round_number(cycle_id: object) -> int | None:
    if not isinstance(cycle_id, str):
        return None
    m = _ROUND_ID_RE.match(cycle_id)
    return int(m.group(1)) if m else None


def quality_outcomes(cycles_dir: str | None = None) -> dict[str, object]:
    """Verdict/finding outcomes from the estimate-engine loop's own records.

    Denominator: total verdicts across every readable cycle record (`n`).
    Partition: all cycle records under `~/.claude/telemetry/cycles/` (or
    `cycles_dir` for tests), across every system -- reuses
    `cycle_telemetry.read_cycles()` rather than re-globbing the tree.

    Degrades HONESTLY, never silently, when the directory is missing/empty
    or `cycle_telemetry` itself is unavailable -- mirroring every ccdash
    metric's own `ccdash_available` discipline in this module.
    """
    if not CYCLE_TELEMETRY_AVAILABLE:
        return {
            "metric": "quality_outcomes",
            "cycle_telemetry_available": False,
            "reason": f"cycle_telemetry not importable: {CYCLE_TELEMETRY_IMPORT_ERROR}",
        }
    try:
        records = _cycle_telemetry.read_cycles(cycles_dir=cycles_dir, on_error="skip")
    except Exception as exc:  # pragma: no cover - defensive, mirrors ccdash's own degradation
        return {
            "metric": "quality_outcomes",
            "cycle_telemetry_available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if not records:
        return {
            "metric": "quality_outcomes",
            "cycle_telemetry_available": False,
            "reason": "no cycle records found (directory missing or empty)",
        }

    concur = dissent = 0
    other_verdicts: Counter[str] = Counter()
    by_trade: dict[str, Counter[str]] = defaultdict(Counter)  # trade -> {CONCUR/DISSENT: n}
    by_round: dict[int, Counter[str]] = defaultdict(Counter)  # round_n -> {CONCUR/DISSENT: n}
    rounds_seen_no_number = 0
    decisions: Counter[str] = Counter()
    finding_missing_decision = 0
    total_findings = 0

    for record in records:
        round_n = _round_number(record.get("cycle_id"))
        if round_n is None:
            rounds_seen_no_number += 1

        for v in record.get("verdicts") or []:
            if not isinstance(v, Mapping):
                continue
            verdict = v.get("verdict")
            if verdict == "CONCUR":
                concur += 1
            elif verdict == "DISSENT":
                dissent += 1
            else:
                other_verdicts[str(verdict)] += 1
                continue  # an unrecognized verdict cannot be attributed to a trade rate
            label = v.get("dispatch_label")
            trade = label.split(":", 1)[0].strip().lower() if isinstance(label, str) and ":" in label else None
            if trade:
                by_trade[trade][verdict] += 1
            if round_n is not None:
                by_round[round_n][verdict] += 1

        for f in record.get("findings") or []:
            if not isinstance(f, Mapping):
                continue
            total_findings += 1
            decision = f.get("consolidator_decision")
            if decision is None:
                finding_missing_decision += 1
            else:
                decisions[str(decision)] += 1

    total_verdicts = concur + dissent + sum(other_verdicts.values())
    require_denominator(total_verdicts, "quality_outcomes", "all")

    rated_trades: dict[str, dict[str, object]] = {}
    excluded_trades_thin: dict[str, int] = {}
    for trade, counts in by_trade.items():
        n = counts.get("CONCUR", 0) + counts.get("DISSENT", 0)
        if n < DISSENT_RATE_MIN_VERDICTS:
            excluded_trades_thin[trade] = n
            continue
        rated_trades[trade] = {
            "n": n,
            "dissent_rate": Value(
                round(counts.get("DISSENT", 0) / n, 4), DERIVED, "DISSENT / (CONCUR + DISSENT)"
            ),
        }

    # Ordered series for the convergence trend -- PARSE the round number
    # rather than string-sort (plan-equivalent rule for this task: a naive
    # sort puts round_10 before round_2). Rounds with zero CONCUR+DISSENT
    # verdicts (shouldn't occur, but a record could carry an empty verdicts
    # list) are excluded from the series rather than plotted as a fabricated
    # 0.0 rate.
    round_series: list[dict[str, object]] = []
    for round_n in sorted(by_round):
        counts = by_round[round_n]
        n = counts.get("CONCUR", 0) + counts.get("DISSENT", 0)
        if n <= 0:
            continue
        round_series.append(
            {
                "round": round_n,
                "n": n,
                "dissent_rate": round(counts.get("DISSENT", 0) / n, 4),
            }
        )

    dissent_rate_overall = dissent / (concur + dissent) if (concur + dissent) else None

    return {
        "metric": "quality_outcomes",
        "cycle_telemetry_available": True,
        "partition": "all",
        "n": total_verdicts,
        "source": "cycle_telemetry.read_cycles() over ~/.claude/telemetry/cycles/",
        "cycles_read": Value(len(records), ORIGINAL, "cycle_telemetry.read_cycles()"),
        "verdicts": {
            "total": total_verdicts,
            "concur": Value(concur, ORIGINAL, "verdicts[].verdict == CONCUR"),
            "dissent": Value(dissent, ORIGINAL, "verdicts[].verdict == DISSENT"),
            "other": Value(dict(other_verdicts), ORIGINAL, "verdicts[].verdict not in {CONCUR, DISSENT}"),
            "dissent_rate": (
                Value(round(dissent_rate_overall, 4), DERIVED, "dissent / (concur + dissent)")
                if dissent_rate_overall is not None
                else unattributable("no CONCUR/DISSENT verdicts recorded")
            ),
        },
        "dissent_rate_by_trade": Value(
            dict(sorted(rated_trades.items(), key=lambda kv: -kv[1]["dissent_rate"].value)),
            DERIVED,
            f"per-trade DISSENT / (CONCUR + DISSENT), trades with n>={DISSENT_RATE_MIN_VERDICTS} only",
        ),
        "dissent_rate_by_trade_excluded_thin": Value(
            dict(sorted(excluded_trades_thin.items())),
            DERIVED,
            f"fewer than {DISSENT_RATE_MIN_VERDICTS} verdicts -- no rate reported",
        ),
        "convergence_by_round": Value(
            round_series, DERIVED, "dissent rate per trade_round_N, N parsed and sorted numerically"
        ),
        # GAPS IN THE SERIES ARE REPORTED, NOT SMOOTHED OVER (2026-09-06).
        #
        # A convergence line drawn through a series with holes in it reads as a
        # continuous trend, and a reader cannot tell a round that IMPROVED from
        # a round that was never recorded. Measured here: rounds 3, 9 and the
        # prime round 18' are all absent -- 18' because the loop skipped its
        # self-log entirely that night (no live run dir), not because it did
        # not happen. Its ledger shows 28 dissents / 198 verdicts.
        #
        # This is also a SOURCE ordering statement. The estimate loop's own
        # reviewed_scenarios ledger is AUTHORITATIVE (review-gated commits,
        # schema-validated writer, and what the exit contract actually reads);
        # this cycle-log telemetry is DERIVED and can be missing rounds the
        # ledger has. Where the two disagree, re-derive from the ledger.
        # A ROUND NUMBER WITH NO RECORD IS TWO DIFFERENT THINGS (2026-09-06).
        #
        # `series_gaps` alone conflates them, and the difference is what a
        # reader actually needs:
        #   - a round that RAN but whose self-log did not fire (round 18' --
        #     the loop skipped its own record that night; the authoritative
        #     ledger HAS its 28/198). Real missing data.
        #   - a round number that NEVER EXISTED (rounds 3 and 9 -- verified
        #     against the ledger, which holds no rows for either; the full
        #     ledger inventory is 1,2,4-8,10-18,18p). Nothing is lost; the
        #     early rounds were simply renumbered.
        # Flagging the second class as "missing" overstates the problem and
        # trains a reader to ignore the field. Only this module's own source
        # can be checked here, so the classification is DECLARED from the
        # cross-checked ledger inventory rather than derived -- and it names
        # what a future reader must re-verify if the ledger grows.
        "series_gaps_never_ran": Value(
            sorted(KNOWN_NEVER_RAN_ROUNDS),
            DECLARED,
            "round numbers with no rows in the authoritative reviewed_scenarios "
            "ledger either -- renumbered, not lost (verified 2026-09-06; "
            "re-verify if the ledger's round inventory changes)",
        ),
        "series_gaps": Value(
            [n for n in range(min(r["round"] for r in round_series), max(r["round"] for r in round_series))
             if n not in {r["round"] for r in round_series}]
            if round_series else [],
            DERIVED,
            "round numbers absent from the cycle-log series between its first and last",
        ),
        "series_is_cycle_log_derived": Value(
            True,
            DECLARED,
            "counts come from cycle telemetry, NOT the authoritative reviewed_scenarios ledger; "
            "a round the loop failed to self-log is absent here but present there",
        ),
        "rounds_without_a_parseable_number": Value(
            rounds_seen_no_number, DERIVED, "cycle_id did not match trade_round_<N>"
        ),
        "findings": {
            "total": total_findings,
            "by_consolidator_decision": Value(
                dict(decisions.most_common()), ORIGINAL, "findings[].consolidator_decision"
            ),
            "missing_decision": Value(
                finding_missing_decision, DERIVED, "findings[].consolidator_decision is null"
            ),
        },
        "note": (
            "Trade name is the prefix of dispatch_label before ':' (e.g. "
            "'plumbing:bath_replace_std_01' -> 'plumbing'), lowercased -- case "
            "variants (e.g. 'GC' vs 'gc') are folded together, mirroring this "
            "module's own agent_type normalization."
        ),
    }


# ---------------------------------------------------------------------------
# METRIC: cost_vs_quality -- ADDED 2026-09-06 (operator finding).
#
# WHY THIS EXISTS: cost and quality render as two panels that share no axis.
# The dashboard can say what an agent type costs, and separately that dissent
# is falling fleet-wide, but never whether a GIVEN agent is expensive AND not
# earning it. That join is the highest-value thing missing, and this metric
# is exactly that join -- reusing `quality_outcomes()` for the quality side
# and `spend_usd()` for the cost side rather than re-globbing the cycles
# directory or re-implementing pricing (plan §1.4: extend, never fork).
#
# THE JOIN. Quality is keyed by TRADE NAME (`dispatch_label.split(':')[0]`,
# lowercased -- see `quality_outcomes()`). Cost is keyed by LEDGER
# `agent_type` (see `spend_usd()['by_agent_type']`, itself keyed through
# `normalize_agent_type()`). The two vocabularies are DERIVED into one
# another, never a hardcoded map of today's known trades: an agent_type
# equal to `"trade-<trade>"`, or ending with `<trade>` (covers a future
# renamed/prefixed variant), resolves the join -- with the GC's mapping
# ("gc" -> "general-contractor") as the one NAMED exception, because it is
# the one trade whose ledger name does not contain its own quality-side name
# at all. A hardcoded dict of today's 11 trades would silently drop the 12th
# trade the day someone adds one; deriving the match means a newly-added
# trade specialist joins automatically the moment its ledger agent_type
# exists, with no code change here.
#
# A trade that resolves to NO agent_type is reported anyway, with its real
# quality figures and an explicit UNJOINED cost -- never dropped, and never
# shown as $0 (mirrors `spend_usd()`'s own unpriceable-row discipline).
# ---------------------------------------------------------------------------

# The GC is the one trade whose dispatch_label prefix ("gc") shares no
# substring with its ledger agent_type ("general-contractor") -- every other
# trade's ledger agent_type is literally "trade-<trade>", which both the
# equals-check and the endswith-check already resolve without a table. This
# is therefore the ONLY named exception, not the first entry of a growing
# one: a second such mismatch is a sign the derivation rule itself needs
# rethinking, not a second entry bolted on here.
TRADE_AGENT_TYPE_EXCEPTIONS: dict[str, str] = {"gc": "general-contractor"}


def _resolve_trade_agent_type(trade: str, by_agent_type_usd: Mapping[str, object]) -> str | None:
    """Resolve a quality-side trade name to its ledger `agent_type` key.

    DERIVED, not a hardcoded roster: tries the named exception first, then
    an exact `trade-<trade>` match, then falls back to any agent_type whose
    name ENDS WITH the trade name (covers a future rename/reprefix without
    requiring a code change here). Returns None -- never a guessed name --
    when nothing in the cost-side population matches at all.
    """
    exception = TRADE_AGENT_TYPE_EXCEPTIONS.get(trade)
    if exception and exception in by_agent_type_usd:
        return exception
    prefixed = f"trade-{trade}"
    if prefixed in by_agent_type_usd:
        return prefixed
    for name in by_agent_type_usd:
        if isinstance(name, str) and name != MISSING_AGENT_TYPE and name.endswith(trade):
            return name
    return None


def cost_vs_quality(
    quality: Mapping[str, object], spend: Mapping[str, object]
) -> dict[str, object]:
    """Join the quality loop's per-trade dissent rate to the ledger's
    per-agent-type dollar spend, so a reader can see whether a trade is
    expensive AND not earning it, rather than reading cost and quality as
    two panels that share no axis.

    Denominator: rated trades (quality_outcomes()'s own
    DISSENT_RATE_MIN_VERDICTS floor -- reused, never a second floor). Two
    inputs, so THREE distinct unavailability reasons are possible and are
    reported as such, never collapsed into one generic "unavailable":
    quality unavailable, cost unavailable, or (the row-level case) a
    specific trade's cost is unjoined while its quality is fine.
    """
    if not quality.get("cycle_telemetry_available"):
        return {
            "metric": "cost_vs_quality",
            "renderable": False,
            "reason": f"quality unavailable: {quality.get('reason', 'unknown')}",
        }
    if spend.get("error"):
        return {
            "metric": "cost_vs_quality",
            "renderable": False,
            "reason": f"cost unavailable: {spend['error']}",
        }

    by_trade = vget_local(quality, "dissent_rate_by_trade") or {}
    if not by_trade:
        return {
            "metric": "cost_vs_quality",
            "renderable": False,
            "reason": "no trade carried enough verdicts to rate (see DISSENT_RATE_MIN_VERDICTS)",
        }
    by_agent_type_usd_wrapped = spend.get("by_agent_type")
    by_agent_type_usd: Mapping[str, object] = (
        by_agent_type_usd_wrapped.value
        if isinstance(by_agent_type_usd_wrapped, Value)
        else (by_agent_type_usd_wrapped or {})
    )

    rows: dict[str, dict[str, object]] = {}
    unjoined_trades: list[str] = []
    for trade, detail in by_trade.items():
        n = int(detail["n"])
        dissent_rate_value = detail["dissent_rate"]
        dissent_rate = (
            dissent_rate_value.value if isinstance(dissent_rate_value, Value) else dissent_rate_value
        )
        dissent_count = round(float(dissent_rate) * n)
        resolved = _resolve_trade_agent_type(trade, by_agent_type_usd)
        if resolved is None:
            unjoined_trades.append(trade)
            rows[trade] = {
                "verdicts": n,
                "dissent_count": dissent_count,
                "dissent_rate": Value(round(float(dissent_rate), 4), DERIVED, "quality_outcomes()"),
                "resolved_agent_type": unattributable(
                    f"no ledger agent_type equals 'trade-{trade}', ends with '{trade}', or "
                    "matches the named GC exception -- this trade's cost is genuinely unjoined, "
                    "not zero"
                ),
                "api_equivalent_usd": unattributable(
                    "cost is UNJOINED for this trade -- never priced at $0"
                ),
                "usd_per_verdict": unattributable("cost is UNJOINED for this trade"),
            }
            continue
        usd_total = float(by_agent_type_usd[resolved])
        usd_per_verdict = usd_total / n if n else None
        rows[trade] = {
            "verdicts": n,
            "dissent_count": dissent_count,
            "dissent_rate": Value(round(float(dissent_rate), 4), DERIVED, "quality_outcomes()"),
            "resolved_agent_type": Value(
                resolved, DERIVED, "trade name derived against spend_usd().by_agent_type"
            ),
            "api_equivalent_usd": Value(round(usd_total, 4), DERIVED, "spend_usd().by_agent_type"),
            "usd_per_verdict": (
                Value(round(usd_per_verdict, 4), DERIVED, "api_equivalent_usd / verdicts")
                if usd_per_verdict is not None
                else unattributable("zero verdicts")
            ),
        }

    return {
        "metric": "cost_vs_quality",
        "renderable": True,
        "n": len(rows),
        "rows": rows,
        "unjoined_trades": Value(
            sorted(unjoined_trades), DERIVED, "trade resolved to no ledger agent_type"
        ),
        "min_verdicts": DISSENT_RATE_MIN_VERDICTS,
        "windows": {
            "quality": "quality_outcomes() -- all recorded cycle files (a bounded, small corpus)",
            "cost": "spend_usd() -- whatever spend.jsonl currently retains (rolls off at ~11 days)",
            "note": (
                "These are TWO DIFFERENT WINDOWS, not one shared window. usd_per_verdict is "
                "NOT a rate over a single period -- it divides a lifetime-loop quality figure "
                "by a rolling ~11-day cost figure. Read it as 'recent cost per historical "
                "verdict', never as a per-period unit economic."
            ),
        },
        "note": (
            "Trade -> agent_type is DERIVED (exact 'trade-<name>' match, or an agent_type "
            "ending with the trade name), with the GC's mapping as the one named exception "
            "-- never a hardcoded roster that silently drops a newly added trade."
        ),
    }


def vget_local(container: Mapping[str, object], *path: str) -> object:
    """Unwrap a possibly-Value-wrapped nested field, same rule the renderer's
    own `vget()` uses -- duplicated narrowly here (not imported from the
    renderer) because this module is the one `scripts/render_agent_telemetry
    .py` imports FROM, and importing back the other way would create a
    cycle. Kept minimal: only the exact nesting `cost_vs_quality()` needs.
    """
    cur: object = container
    for key in path:
        if isinstance(cur, Value):
            cur = cur.to_dict()
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    if isinstance(cur, Value):
        return cur.value
    return cur


# ---------------------------------------------------------------------------
# METRIC: ledger_health -- feeds the dashboard's confidence clause (plan R3).
# ---------------------------------------------------------------------------


def ledger_health(
    rows: Sequence[Mapping[str, object]], read_report: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Trust gate for every other panel.

    Denominator: ALL rows as read (`n`), before any collapse -- this metric
    describes the ledger itself, so collapsing first would hide the very
    duplication it exists to report.
    """
    n = len(rows)
    require_denominator(n, "ledger_health", "all")

    states = Counter(
        "absent" if r.get("join_state") is None else str(r.get("join_state")) for r in rows
    )
    unreleased = sum(1 for r in rows if r.get("unreleased") is True)
    late = sum(1 for r in rows if r.get("late") is True)
    token_errors = Counter(
        str(r.get("tokens_error")) for r in rows if r.get("tokens_error") is not None
    )
    no_tokens = sum(1 for r in rows if not isinstance(r.get("tokens"), dict))
    priceable = sum(1 for r in rows if row_price_usd(r) is not None)

    agent_ids = Counter(
        r.get("agent_id") for r in rows if isinstance(r.get("agent_id"), str) and r.get("agent_id")
    )
    duplicate_groups = sum(1 for c in agent_ids.values() if c > 1)

    stamps = [parse_ts(r.get("ts")) for r in rows]
    real = [s for s in stamps if s is not None]
    if real:
        oldest, newest = min(real), max(real)
        horizon = Value(
            round((newest - oldest).total_seconds() / 86400.0, 2),
            DERIVED,
            "newest ts - oldest ts, in days",
        )
        window = Value(
            {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            ORIGINAL,
            "spend.jsonl:ts",
        )
    else:
        horizon = unattributable("no parseable timestamps in the ledger")
        window = unattributable("no parseable timestamps in the ledger")

    joined_n = states.get(JOINED, 0)
    return {
        "metric": "ledger_health",
        "partition": "all",
        "n": n,
        "read_report": dict(read_report) if read_report else None,
        "join_state_mix": Value(dict(states), ORIGINAL, "spend.jsonl:join_state"),
        "join_rate": Value(round(joined_n / n, 4), DERIVED, "joined rows / all rows"),
        "unreleased_rows": Value(unreleased, ORIGINAL, "spend.jsonl:unreleased"),
        "late_rows": Value(late, ORIGINAL, "spend.jsonl:late"),
        "tokens_error": Value(dict(token_errors), ORIGINAL, "spend.jsonl:tokens_error"),
        "rows_without_tokens": Value(no_tokens, DERIVED, "spend.jsonl:tokens is null"),
        "pricing_coverage_raw": Value(
            round(priceable / n, 4), DERIVED, "priceable rows / all rows (pre-collapse)"
        ),
        "duplicate_agent_id_groups": Value(
            duplicate_groups, DERIVED, "agent_ids appearing on more than one row"
        ),
        "retention_horizon_days": horizon,
        "window": window,
        "retention_warning": (
            "spend.jsonl rolls off at ~11 days. Any 'vs prior 7d' comparison sits at "
            "the edge of the window; state the horizon rather than comparing against "
            "a truncated one."
        ),
        "confidence_clause": Value(
            f"{joined_n} of {n} rows ({round(100.0 * joined_n / n, 1)}%) carry a full join; "
            "duration and per-model panels are computed over that partition only.",
            DERIVED,
            "plan R3",
        ),
    }


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def collect_all(
    ledger_path: str | None = None,
    projects_root: str | None = None,
    transcript_limit: int | None = None,
    include_transcripts: bool = True,
    ingest: bool = False,
) -> dict[str, object]:
    """Every Phase 1 metric, including ones the v1 page defers.

    Each metric is computed independently and a failure in one (including a
    PartitionError for an absent denominator) is recorded as that metric's
    own `error` rather than aborting the whole collection -- a dashboard that
    renders nothing because one panel has no data is worse than one that
    renders the panels it can and says which it cannot.

    `ingest=True` runs ccdash's incremental scan once before reading, so a
    real render is never served from a stale store (measured 2026-09-05: the
    store was 2 days behind and missing 45% of the 7-day window, with nothing
    saying so). It defaults to False so tests and read-only callers never
    mutate the database as a side effect of collecting metrics.
    """
    if ingest:
        # Once per process; failure degrades to stale-but-reported, never fatal.
        st = ccdash_status(ingest=True)
        if not st.get("available"):
            pass  # the per-metric ccdash_status() calls below report the reason
    ledger_path = ledger_path or default_ledger_path()
    projects_root = projects_root or default_projects_root()

    rows, read_report = read_ledger(ledger_path)
    out: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ledger_path": ledger_path,
        "projects_root": projects_root,
        "read_report": read_report,
        "price_table_version": Value(PRICE_TABLE_VERSION, DECLARED, "cycle_budget.py"),
    }

    # The ledger's own oldest timestamp is the retention horizon
    # `ccdash_agent_type_join()` must be windowed to (its docstring's own
    # constraint: unwindowed reads a near-zero, misleading rate because
    # ccdash retains full history while spend.jsonl rolls off at ~11 days).
    # Computed once here, from the SAME `rows` every other metric sees, so
    # the join and the rest of the page can never silently disagree about
    # what "the ledger's window" means.
    _stamps = [parse_ts(r.get("ts")) for r in rows]
    _real_stamps = [s for s in _stamps if s is not None]
    ledger_oldest_iso = (
        min(_real_stamps).strftime("%Y-%m-%dT%H:%M:%SZ") if _real_stamps else None
    )

    ledger_metrics = {
        "ledger_health": lambda: ledger_health(rows, read_report),
        "dispatch_counts": lambda: dispatch_counts(rows),
        "token_buckets": lambda: token_buckets(rows),
        "spend_usd": lambda: spend_usd(rows),
        "latency_percentiles": lambda: latency_percentiles(rows),
        "session_metrics": lambda: session_metrics(rows),
        "cache_detail": lambda: cache_detail(rows),
        "ccdash_token_split": lambda: ccdash_token_split(),
        "ccdash_cache_ttl_split": lambda: ccdash_cache_ttl_split(),
        "ccdash_spend_by_model": lambda: ccdash_spend_by_model(),
        "ccdash_agent_type_join": lambda: ccdash_agent_type_join(rows, ledger_oldest_iso),
        "account_capacity": lambda: account_capacity(),
        "quality_outcomes": lambda: quality_outcomes(),
    }
    transcript_metrics = {
        "call_graph": lambda: call_graph(projects_root),
        "turns_per_dispatch": lambda: turns_per_dispatch(projects_root, transcript_limit),
        "tool_calls_per_dispatch": lambda: tool_calls_per_dispatch(projects_root, transcript_limit),
        "true_duration": lambda: true_duration(projects_root, transcript_limit),
        "loop_detection": lambda: loop_detection(projects_root, transcript_limit),
    }
    tasks = dict(ledger_metrics)
    if include_transcripts:
        tasks.update(transcript_metrics)

    for name, fn in tasks.items():
        try:
            out[name] = fn()
        except PartitionError as exc:
            out[name] = {"metric": name, "error": str(exc), "renderable": False}
        except Exception as exc:  # pragma: no cover - defensive
            out[name] = {"metric": name, "error": f"{type(exc).__name__}: {exc}", "renderable": False}

    # `cost_vs_quality()` JOINS two metrics already computed above
    # (`quality_outcomes`, `spend_usd`) -- it runs AFTER the loop, reading
    # their results out of `out`, rather than recomputing either (plan
    # §1.4: extend, never fork; there must not be a second copy of the
    # cycles-directory read or the pricing pass).
    try:
        out["cost_vs_quality"] = cost_vs_quality(
            out.get("quality_outcomes", {}), out.get("spend_usd", {})
        )
    except PartitionError as exc:
        out["cost_vs_quality"] = {"metric": "cost_vs_quality", "error": str(exc), "renderable": False}
    except Exception as exc:  # pragma: no cover - defensive
        out["cost_vs_quality"] = {
            "metric": "cost_vs_quality",
            "error": f"{type(exc).__name__}: {exc}",
            "renderable": False,
        }
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _fmt_value(value: object) -> str:
    if isinstance(value, Value):
        if value.provenance == UNATTRIBUTABLE:
            return f"unattributable ({value.source})"
        return f"{value.value}  [{value.provenance}]"
    return str(value)


def render_text(payload: Mapping[str, object]) -> str:
    lines: list[str] = ["AGENT TELEMETRY (Phase 1)", "=" * 60]
    lines.append(f"generated: {payload.get('generated_at')}")
    lines.append(f"ledger:    {payload.get('ledger_path')}")
    lines.append("")
    for key, section in payload.items():
        if not isinstance(section, dict) or "metric" not in section:
            continue
        lines.append(f"--- {key} ---")
        if section.get("error"):
            lines.append(f"  NOT RENDERABLE: {section['error']}")
            lines.append("")
            continue
        lines.append(f"  partition={section.get('partition')}  n={section.get('n')}")
        for field, value in section.items():
            if field in ("metric", "partition", "n", "prep", "read_report"):
                continue
            if isinstance(value, Value):
                lines.append(f"  {field}: {_fmt_value(value)}")
        lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent_telemetry.py",
        description="Phase 1 agent-telemetry collector (computes; never gates, never renders HTML).",
    )
    parser.add_argument("--json", action="store_true", help="emit every computed metric as JSON")
    parser.add_argument("--ledger", default=None, help="path to spend.jsonl")
    parser.add_argument("--projects-root", default=None, help="path to ~/.claude/projects")
    parser.add_argument(
        "--transcript-limit",
        type=int,
        default=None,
        help="cap transcripts scanned (the full tree is ~11.7k files)",
    )
    parser.add_argument(
        "--no-transcripts",
        action="store_true",
        help="skip every transcript-derived metric (ledger-only, fast)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    payload = collect_all(
        ledger_path=args.ledger,
        projects_root=args.projects_root,
        transcript_limit=args.transcript_limit,
        include_transcripts=not args.no_transcripts,
    )
    if args.json:
        print(json.dumps(_jsonify(payload), indent=2, sort_keys=False, default=str))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
