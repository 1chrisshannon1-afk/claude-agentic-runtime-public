"""spend_attribution -- recovers agent_type/model identity for unpriceable
~/.claude/.agent_budget/spend.jsonl rows from Claude Code's OWN
workflow-dispatch metadata (never from the ledger writer itself, which this
repo does not control -- it is emitted by the Claude Code client).

INTEGRATION STATUS (UPDATED 2026-09-01, F1/Item 13-14, AA-0064-adjacent fix
round): as of round 16 (2026-08-28 review finding #4), no dispatcher,
schedule, or job in this runtime called this module's recovery on the hot
path. THAT GAP IS NOW CLOSED: `hooks/daily_spend_rollup.py`'s
`run_attribution_compaction()` (invoked from every non-dry-run CLI call,
and wired as pre-step D of the daily oversight job,
`schedules/prompts/daily_sweep.txt`, and of `/sweep`,
`commands/sweep.md`) runs this module's own `enrich --out <sidecar>
--rebuild-index` CLI path once per day -- both refreshing the shared
identity-index cache (closing the staleness half of this module's own
contract) and writing the CURRENT spend.jsonl window's recovered
identities to a read-only sidecar,
`~/.claude/.agent_budget/spend_enriched.jsonl`, that never mutates
`spend.jsonl` itself. `cycle_budget.py`'s own synchronous gate is UNCHANGED
by this -- it still only ever calls `load_cached_index()` (never triggers a
rebuild inline, by design, to stay off the synchronous spend-gate's latency
path); the cache it reads is now kept fresh by the daily job above instead
of never at all.

THE PROBLEM (measured against the live ledger, 2026-08-28): a large, growing
fraction of spend.jsonl rows carry `model: null` and are therefore
unpriceable by `cycle_budget.py`'s `normalize_model()`/`price_tokens_usd()`
(and, for a sub-population, `agent_type` is only the client's generic
"workflow-subagent" bucket label rather than a real, specific type) --
AS-OF 2026-08-28 (`python3 spend_attribution.py coverage` against the live
ledger; no dedicated coverage-regression test exists for these figures --
re-run that command for a current reading rather than trusting this
comment to stay fresh): 92.24% of total tokens still carry their original
`agent_type` untouched, 0.12% were recovered, and 7.65% remain
unattributable; for `model`, only 52.62% of total tokens were priceable
BEFORE recovery, recovery lifts that to 98.09% priceable AFTER recovery,
and 1.91% remain genuinely `still_unpriceable`. Every one of these rows carries
`session: null` too (verified: zero exceptions in the live ledger), which is
WHY `cycle_budget.py`'s own fail-closed algorithm can never confidently
attribute them to a specific dispatching cycle by session alone -- but a
generic/missing `agent_type` also means such a row cannot even be
recognized as "possibly this cycle's own dispatch" (see `attribute_cycle_
spend()`'s AMBIGUOUS vs EXCLUDED buckets in cycle_budget.py) -- it is
silently treated as unrelated background noise instead, which is the exact
~26x-under-report failure mode #4498 measured and that module's own
docstring names as its "one bounded, documented risk".

THE RECOVERY: Claude Code's own workflow machinery records, for every
workflow-dispatched agent, an `agentId` that matches spend.jsonl's
`agent_id` field, alongside that agent's real `agentType`/`model`. Two
independent, DISCOVERABLE sources carry this join key -- proven against the
live tree 2026-08-28 (see the test suite's fixture-based equivalents for a
hermetic version of the same checks):

  1. `agent-<agentId>.meta.json` sidecar files, sitting next to that agent's
     own transcript (`agent-<agentId>.jsonl`) under
     `~/.claude/projects/<project>/<session>/subagents/` (and, for a
     workflow-dispatched agent specifically, under that same tree's
     `.../subagents/workflows/<workflow_run_id>/` subdirectory). DURABLE:
     this tree is never wiped the way a session-scoped temp dir is.
     Always carries `agentType` (proven: on the live tree, wherever BOTH
     this source and source 2 below reported a real, non-empty agentType
     for the same agentId, they agreed -- 0 mismatches across hundreds of
     overlapping ids). Sometimes ALSO carries `model`, but only as a
     coarse FAMILY string (e.g. "sonnet", "opus"), never the full model
     tag.
  2. `workflowProgress` array entries with `type == "workflow_agent"`
     inside `<taskid>.output` JSON files, under
     `<tempdir>/claude-*/<project>/<session>/tasks/`. EPHEMERAL: this tree
     is session-scoped and gets wiped. Carries `agentId`, `model` (the
     FULL model tag, e.g. "claude-sonnet-5" or "claude-opus-5[1m]" --
     matching the ledger's OWN `model` string format exactly, unlike
     source 1's family-only string), and sometimes `agentType` (a purely
     generic/no-persona dispatch inside a workflow phase can legitimately
     omit it even here -- source 1 is what fills that gap).

  BOTH sources are used, TOGETHER, never one in place of the other:
  source 1 (meta.json) is PREFERRED/AUTHORITATIVE for `agent_type`
  (durability + the proven zero-mismatch precision above); source 2
  (the ephemeral `.output` tree) is PREFERRED for `model` (it is the only
  source that ever carries the full, ledger-matching model tag; a
  family-only fallback from source 1 is used only when source 2 has
  nothing). See `_merge_identity()`.

PLACEHOLDER AGENT TYPES. `PLACEHOLDER_AGENT_TYPES = {None, "", "workflow-
subagent"}`. A ledger row already carrying one of these is NOT first-party
identity worth protecting from override: "workflow-subagent" is the
client's OWN generic bucket label for "no more specific identity was ever
resolved" -- it is, measured live 2026-08-28, the single largest
recoverable population this module exists to fix. Recovery is attempted for
any row whose CURRENT agent_type is a placeholder, and a recovered value
WINS over it -- but only when the recovered value is itself something more
than another placeholder (recovering "workflow-subagent" TO
"workflow-subagent" is not new information; it is correctly reported as
still `unattributable`, never laundered into a false "recovered"). A REAL,
specific `agent_type` already on a row (e.g. "implement", "code-reviewer")
is first-party data and is NEVER overridden by anything this module finds,
even though that has never been observed to disagree in practice --
overriding real ledger data is not this module's job under any
circumstance.

DOUBLE-COUNTING RULE (the exact ask; verified against real data 2026-08-28):
a workflow's `.output` file reports an aggregate `totalTokens` figure that
is precisely the SUM of each child agent's own `tokens` field inside that
same file's `workflowProgress` array (verified on a real 4-agent workflow:
142113 + 92558 + 137738 + 135386 == 507795 == the file's own `totalTokens`).
That reported figure is PAYLOAD-shaped, not BILLED spend: measured ~26x
smaller than the same agents' real `tokens_total` in the ledger for
identical work. Given that, THE RULE THIS MODULE ADOPTS is: workflow
metadata (both sources) is consulted SOLELY to look up `agent_type`/`model`
identity by `agent_id` -- a `tokens`/`totalTokens` value found there is
NEVER read into any spend total by this module. The only place a token
count is ever taken from, anywhere in this module, is a ledger row's own
`tokens`/`tokens_total` field, exactly as before this module existed. If a
workflow-reported token count is surfaced at all (purely for debugging), it
is placed under `attribution.reported_tokens_untrusted` and nowhere else --
never blended into a sum, never relabeled as spend.

Consequently: (a) each ledger row still contributes to any total EXACTLY
ONCE, via its own row -- this module never merges, drops, reorders, or
synthesizes ledger rows, and enrich_row()/enrich_rows() always return
exactly as many rows as they were given; (b) a workflow agent's real spend
is counted once (via its own ledger row) regardless of the fact that its
(untrusted, far smaller) token count ALSO appears nested inside its parent
workflow dispatch's `.output` aggregate, because that aggregate is never
read as a value to sum -- only as an identity index.

A SEPARATE, pre-existing phenomenon lives in `agent_budget.py`'s own
claim/stop join machinery, NOT this module's domain: the SAME `agent_id`
can occasionally appear as two independent spend.jsonl LINES -- one from a
normal claim/release, one a later `stopped-unjoined` reap with
`tool_use_id: null` (observed live, 2026-08-28: agent_id
"a0c1c8e46f867986d" has exactly this shape, tokens 14206442 and 17575769
respectively). `churn_report.py`'s OWN `dedup_spend_lines()` already
documents the authoritative rule for this: lines are deduplicated by
`tool_use_id`, and a `null` `tool_use_id` is NEVER deduplicated against
anything -- each such line stands as its own record. This module
deliberately mirrors that existing convention rather than inventing a
second, divergent one for ROWS: `enrich_row()`/`enrich_rows()` never merge,
drop, or synthesize a ledger row -- every row keeps its own independent
identity and its own place in the output, exactly as `churn_report.py`
already treats it (see the DOUBLE-COUNTING RULE section above).

CORRECTION (round 4, 2026-08-28): an earlier version of this paragraph
flatly stated this module "never joins or collapses ledger rows by
agent_id" at all -- that overstated the ROW-level guarantee above into a
FIELD-level one, and is false: `_widen_index_with_ledger_siblings()`
(THIRD IDENTITY SOURCE, below) deliberately joins facts ACROSS sibling
rows sharing an agent_id to recover a missing `agent_type`/`model`, and
`coverage_report()`'s own `_collapse_duplicate_agent_tokens()` deliberately
collapses a duplicate-agent_id group's TOKEN CONTRIBUTION to a sum down to
its single largest reading. Neither of those merges, drops, or reorders a
ROW -- `enrich_row()`/`enrich_rows()` still return exactly one output row
per input row, and `coverage_report()` still classifies every row --
which is the guarantee that actually holds; only the never-joins-anything
sentence above was wrong, and is fixed here.

PROVENANCE CONTRACT. `enrich_row()`/`enrich_rows()` never mutate the input
row (they return a new dict) and always attach a `row["attribution"]` block
naming, for each of `agent_type`/`model`, whether the value is:
  "original"       -- first-party, exactly as the ledger wrote it.
  "recovered"       -- filled in (or replaced a placeholder) by this
                        module, naming which source supplied it.
  "unattributable"  -- still unknown after an honest attempt (or no
                        attempt was possible -- no matching agent_id in the
                        index at all).
The row's own top-level `agent_type`/`model` keys are ALSO updated to the
effective (original-or-recovered) value, so a caller that does not know
about this contract still sees a normally-shaped row -- but such a caller
can never tell an "original" fact from a "recovered" inference without
reading `row["attribution"]`, so any caller for whom that distinction is
load-bearing (this module's own `cycle_budget.py` integration, notably)
reads that block explicitly rather than trusting the bare field --
`cycle_budget.attribute_cycle_spend()` does this concretely via
`_count_recovered_fields()`, surfacing `recovered_agent_type_rows`/
`recovered_model_rows` on every `CycleAttribution` it returns (added
2026-08-28, see that module's own docstring). A recovered value is
therefore never indistinguishable from a first-party one to a caller that
actually looks.

THIRD IDENTITY SOURCE -- ledger-internal sibling rows (added 2026-08-28).
`enrich_rows()`/`coverage_report()` (never bare `enrich_row()`, which only
ever sees one row and has no sibling to look at) additionally widen the
identity index with `_widen_index_with_ledger_siblings()`: for an agent_id
with no usable fact in either external metadata source, look for ANY OTHER
row in the SAME `rows` set sharing that `agent_id` which already carries a
real, non-placeholder `agent_type` and/or `model`, and borrow it. Measured
live 2026-08-28: 41 of 61 "unrecoverable" model rows (100% of that bucket's
tokens, 3.49B) share an agent_id with a priced sibling row already present
in the SAME ledger -- a fact the two external sources can never see, since
they know nothing about the ledger's own contents. This source is STRICTLY
lowest priority: it never overrides a meaningful value the external index
already resolved, only fills a field that source left missing/placeholder.

COVERAGE HONESTY (`coverage_report()`, tightened 2026-08-28):
  * `priceable_before_recovery`/`priceable_after_recovery` are now
    classified by whether a model value actually normalizes to a family
    `cycle_budget.PRICING_USD_PER_MTOK` can price (`_is_priced_model()`),
    NOT by mere presence of a model string -- a recovered (or even
    original) internal/unreleased model code name (e.g. "claude-imaginary-9",
    a genuinely unpublished model this table has no rate for; "claude-fable-5"
    was this example until 2026-09-05, when Fable 5's published rate was
    added to PRICING_USD_PER_MTOK and it became a real priceable family)
    IS present but prices to nothing, and previously counted as
    "priceable" purely for having a non-null string. Such rows are instead
    surfaced under the distinct `recovered_but_unpriced_family` bucket.
  * Every total/percentage in this report collapses same-`agent_id`
    duplicate ledger lines to only their largest `tokens_total` reading
    (`collapsed_duplicate_rows` discloses the count) -- see the
    DOUBLE-COUNTING RULE section above for the real, measured phenomenon
    this corrects (a `stopped-unjoined` reap that is a LATER, LARGER
    cumulative reading of the SAME agent, not independent spend). This is
    orthogonal to, and does not relax, the "never merge ledger ROWS"
    contract: `enrich_row()`/`enrich_rows()` still return exactly one
    output row per input row, unchanged; only a SUM's per-row contribution
    is deduplicated.

CACHING. Building the identity index requires walking both metadata trees.
Originally measured 2026-08-28 on this machine at ~2s (durable/meta.json
side) plus ~13s (ephemeral/`.output` side) -- STALE as of round 16
(2026-08-28 review): the `.output` side's cost does NOT hold at a fixed
~13s duration. It SCALES WITH THE SIZE OF THE SYSTEM TEMP ROOT, not with
the number of real `.output` files, because `_default_output_roots()`
resolves into the system temp directory, which only ever grows across
every session this machine ever runs (nothing prunes it). Re-measured
round 16: on a temp root that had grown to over 2 MILLION files, the
rebuild did not complete after 5+ minutes. `_iter_output_files()`'s
fixed-depth glob (round 16 fix, replacing an unbounded recursive `**`
walk) restores the cost to being proportional to the real number of
project/session directories rather than every file anywhere under the
temp root, but no fixed duration is safe to quote here again -- the right
mental model is "scales with temp-root size," not "~13s," and should be
re-measured on THIS machine before being relied on for latency planning.
Regardless of duration, this is still far too slow to redo on every call
inside a per-dispatch budget gate. `build_identity_index()` therefore
caches its result to a JSON file (default
`~/.claude/.agent_budget/spend_attribution_cache.json`, override via
`cache_path=`/`$CSA_SPEND_ATTRIBUTION_CACHE`), rebuilding only when the
cache is missing, corrupt, or older than `max_age_seconds` (default
`DEFAULT_INDEX_MAX_AGE_SECONDS` = 900s), or unconditionally when
`force_rebuild=True`. `load_cached_index()` is the OTHER half of this
split: it ONLY EVER reads whatever cache already exists on disk, however
old, and NEVER triggers the expensive scan inline -- `cycle_budget.py`'s
hot per-dispatch gate path uses this function specifically, so that
keeping the index fresh is a background/on-demand concern (an operator or
oversight job running `spend_attribution.py coverage --rebuild-index`
periodically) and never a latency risk on the synchronous spend gate. A
missing/corrupt/unreadable cache degrades to an EMPTY index (`{}`) from
both functions -- never raises. An empty or partial index can only ever
produce MORE `unattributable` results, never a false `recovered`/`known`
one -- recovery failing is always safe to this module's own contract, and
(per cycle_budget.py's integration) never weakens that module's fail-closed
spend-ceiling decision either; see its docstring for that half of the
contract.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------

# A ledger row already carrying one of these `agent_type` values is treated
# as NOT having a real identity -- see module docstring's PLACEHOLDER
# AGENT TYPES section. `None` is included so every call site can test
# `value in PLACEHOLDER_AGENT_TYPES` without a separate None check.
PLACEHOLDER_AGENT_TYPES: frozenset[str | None] = frozenset({None, "", "workflow-subagent"})

DEFAULT_INDEX_MAX_AGE_SECONDS: float = 900.0

_META_FILE_PATTERN = "agent-*.meta.json"
_META_PREFIX = "agent-"
_META_SUFFIX = ".meta.json"


# ---------------------------------------------------------------------------
# Path defaults -- computed at CALL time from a supplied environ mapping,
# never at import time (mirrors cycle_budget.py's `_default_ledger_path`
# convention deliberately, so tests never depend on this machine's real
# ~/.claude tree).
# ---------------------------------------------------------------------------


def _home(environ: Mapping[str, str]) -> str:
    return environ.get("HOME") or os.path.expanduser("~")


def _default_meta_roots(environ: Mapping[str, str]) -> list[str]:
    """Durable source roots: $CSA_WORKFLOW_META_ROOTS (colon-separated), else
    ~/.claude/projects."""
    override = environ.get("CSA_WORKFLOW_META_ROOTS")
    if override:
        return [p for p in override.split(":") if p]
    return [os.path.join(_home(environ), ".claude", "projects")]


def _default_output_roots(environ: Mapping[str, str]) -> list[str]:
    """Ephemeral source roots: $CSA_WORKFLOW_OUTPUT_ROOTS (colon-separated),
    else every `claude-*` directory Claude Code's own CLI creates directly
    under the system temp dir (its own documented convention: `<tempdir>/
    claude-<uid>/<project>/<session>/tasks/<taskid>.output`).

    Checks BOTH `tempfile.gettempdir()` (the per-process $TMPDIR, which on
    macOS is a user-specific `/var/folders/...` path -- NOT where Claude
    Code actually writes) AND the fixed `/tmp` path (which resolves through
    the standard `/tmp` -> `/private/tmp` symlink on macOS): Claude Code's
    own task-output convention was verified live (2026-08-28) to use the
    latter, unconditionally, regardless of this process's own $TMPDIR --
    `tempfile.gettempdir()` alone silently finds zero output files in a
    sandboxed shell whose $TMPDIR differs from `/tmp`. Both candidate roots
    are searched (not just the one that matches) so a caller running on a
    machine where Claude Code truly does honor $TMPDIR is still covered."""
    override = environ.get("CSA_WORKFLOW_OUTPUT_ROOTS")
    if override:
        return [p for p in override.split(":") if p]
    candidates = {tempfile.gettempdir(), "/tmp"}
    found: list[str] = []
    for base in sorted(candidates):
        found.extend(glob.glob(os.path.join(base, "claude-*")))
    return found or sorted(candidates)


def _default_cache_path(environ: Mapping[str, str]) -> str:
    override = environ.get("CSA_SPEND_ATTRIBUTION_CACHE")
    if override:
        return override
    return os.path.join(_home(environ), ".claude", ".agent_budget", "spend_attribution_cache.json")


def _default_ledger_path(environ: Mapping[str, str]) -> str:
    """Mirrors cycle_budget.py's `_default_ledger_path` deliberately -- this
    module is a standalone CLI/library and must not import a private
    function from a sibling module to get four lines of path logic."""
    override = environ.get("CSA_CYCLE_LEDGER")
    if override:
        return override
    return os.path.join(_home(environ), ".claude", ".agent_budget", "spend.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Result type.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveredIdentity:
    """One agent_id's recovered identity, merged from whichever of the two
    sources supplied each field. See module docstring for the preference
    rules `_merge_identity()` implements."""

    agent_type: str | None = None
    model: str | None = None
    label: str | None = None
    phase: str | None = None
    workflow_run_id: str | None = None
    reported_tokens: int | None = None  # UNTRUSTED -- see module docstring.
    agent_type_source: str | None = None  # "meta.json" | "workflow_output" | None
    model_source: str | None = None  # "meta.json" | "workflow_output" | None

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_type": self.agent_type,
            "model": self.model,
            "label": self.label,
            "phase": self.phase,
            "workflow_run_id": self.workflow_run_id,
            "reported_tokens": self.reported_tokens,
            "agent_type_source": self.agent_type_source,
            "model_source": self.model_source,
        }

    @staticmethod
    def from_dict(payload: Mapping[str, object]) -> RecoveredIdentity:
        def _s(key: str) -> str | None:
            value = payload.get(key)
            return value if isinstance(value, str) else None

        tokens = payload.get("reported_tokens")
        return RecoveredIdentity(
            agent_type=_s("agent_type"),
            model=_s("model"),
            label=_s("label"),
            phase=_s("phase"),
            workflow_run_id=_s("workflow_run_id"),
            reported_tokens=tokens if isinstance(tokens, int) and not isinstance(tokens, bool) else None,
            agent_type_source=_s("agent_type_source"),
            model_source=_s("model_source"),
        )


# ---------------------------------------------------------------------------
# Discovery -- reading the two metadata trees. Every function here is
# fail-open on individual-file problems (skip and continue); a missing or
# non-directory root is silently skipped, never an error.
# ---------------------------------------------------------------------------


def _iter_files(roots: Iterable[str], pattern: str) -> Iterator[str]:
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        yield from sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True))


def _iter_output_files(roots: Iterable[str]) -> Iterator[str]:
    """Fixed-depth counterpart to `_iter_files()`, scoped to the `.output`
    tree's own KNOWN, documented depth (`<root>/<project>/<session>/tasks/
    <taskid>.output` -- see `_default_output_roots()`'s own docstring)
    rather than an unbounded recursive `**` glob.

    Review finding #3 (round 16, 2026-08-28): `_iter_files()`'s
    `root/**/pattern` walk is O(every file anywhere under `root`), not
    O(the real number of `.output` files) -- measured live: a real
    `claude-*` root (each ROOT here is already one such directory, per
    `_default_output_roots()`) had grown to hold over 2 MILLION files
    (the system temp root is monotonically growing across sessions, never
    cleaned up), and the recursive glob did not complete after 5+ minutes
    of walking it looking for ~2000 real `.output` files. `.output` files
    live at a FIXED, KNOWN depth under each such root
    (`<project>/<session>/tasks/<taskid>.output`), so this walks exactly
    `len(projects) * len(sessions)` directories instead of every file
    anywhere under `root` -- cost scales with the number of real
    project/session directories, not with how large the temp root has
    grown around them. `_load_output_index()` is the sole caller;
    `_iter_files()` itself is unchanged and still used, unmodified, for
    the durable (meta.json) side, whose own real depth genuinely varies
    (a direct dispatch's meta.json sits one level shallower than a
    workflow dispatch's -- see `_workflow_run_id_from_meta_path()`)."""
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        yield from sorted(glob.glob(os.path.join(root, "*", "*", "tasks", "*.output")))


def _agent_id_from_meta_filename(path: str) -> str | None:
    name = os.path.basename(path)
    if name.startswith(_META_PREFIX) and name.endswith(_META_SUFFIX):
        agent_id = name[len(_META_PREFIX) : -len(_META_SUFFIX)]
        return agent_id or None
    return None


def _workflow_run_id_from_meta_path(path: str) -> str | None:
    """Durable-source workflow_run_id: the `<runid>` segment of a path like
    `.../subagents/workflows/<runid>/agent-<id>.meta.json`. A direct
    (non-workflow) Task dispatch's meta.json sits one level up, with no
    `workflows` segment at all, and correctly yields None here."""
    parts = path.split(os.sep)
    for i, part in enumerate(parts):
        if part == "workflows" and i + 1 < len(parts) and parts[i + 1]:
            return parts[i + 1]
    return None


def _load_meta_index(meta_roots: Iterable[str]) -> dict[str, dict[str, object]]:
    """agentId -> parsed agent-<id>.meta.json content, plus a derived
    `_workflow_run_id`. First-seen wins on a genuine duplicate (agentId is
    expected to be globally unique across this tree); sorted() iteration
    makes that deterministic regardless of filesystem walk order."""
    index: dict[str, dict[str, object]] = {}
    for path in _iter_files(meta_roots, _META_FILE_PATTERN):
        agent_id = _agent_id_from_meta_filename(path)
        if not agent_id or agent_id in index:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        entry = dict(data)
        entry["_workflow_run_id"] = _workflow_run_id_from_meta_path(path)
        index[agent_id] = entry
    return index


def _output_entry_score(entry: Mapping[str, object]) -> tuple[bool, bool, bool, int]:
    """Completeness score for a `workflow_agent` entry -- the SAME agentId
    can appear in several `.output` snapshots taken at different points in
    that agent's run (proven live, 2026-08-28: early snapshots show
    `agentType: null, model: "opus"`; later snapshots of the identical
    dispatch show `agentType: "ultracode", model: "claude-opus-5[1m]"` --
    not a collision, just varying completeness of the SAME fact). Higher
    tuples win via `max()`; a "full" model tag is one that looks like an
    actual model string ("claude-..." or containing a "-") rather than a
    bare family word."""
    model = entry.get("model")
    full_model = isinstance(model, str) and bool(model) and ("claude" in model.lower() or "-" in model)
    populated = sum(
        1
        for k in ("agentType", "model", "label", "phaseTitle", "tokens")
        if entry.get(k) not in (None, "")
    )
    return (entry.get("state") == "done", bool(entry.get("agentType")), bool(full_model), populated)


def _load_output_index(output_roots: Iterable[str]) -> dict[str, dict[str, object]]:
    """agentId -> the most-complete `workflow_agent` workflowProgress entry
    seen for it, plus a derived `_workflow_run_id` (the containing
    `.output` file's own task id). Any file that is not JSON, not a dict, or
    lacks a `workflowProgress` list is silently skipped -- real `.output`
    files also hold plain-text tool logs and raw JSONL transcripts (proven
    live: the large majority of files under this tree are NOT workflow
    dispatches at all)."""
    best: dict[str, tuple[tuple[bool, bool, bool, int], dict[str, object]]] = {}
    for path in _iter_output_files(output_roots):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        progress = data.get("workflowProgress")
        if not isinstance(progress, list):
            continue
        task_id = os.path.splitext(os.path.basename(path))[0]
        for entry in progress:
            if not isinstance(entry, dict) or entry.get("type") != "workflow_agent":
                continue
            agent_id = entry.get("agentId")
            if not isinstance(agent_id, str) or not agent_id:
                continue
            score = _output_entry_score(entry)
            prior = best.get(agent_id)
            if prior is None or score > prior[0]:
                merged = dict(entry)
                merged["_workflow_run_id"] = task_id
                best[agent_id] = (score, merged)
    return {agent_id: entry for agent_id, (_score, entry) in best.items()}


def _merge_identity(
    meta: Mapping[str, object] | None, out: Mapping[str, object] | None
) -> RecoveredIdentity:
    """Merge one agent_id's durable (`meta`) and ephemeral (`out`) records
    per the module docstring's preference rules: `meta` wins for
    `agent_type` (durability + proven precision), `out` wins for `model`
    (the only source with the full, ledger-matching model tag)."""
    agent_type: str | None = None
    agent_type_source: str | None = None
    meta_type = (meta or {}).get("agentType")
    out_type = (out or {}).get("agentType")
    if isinstance(meta_type, str) and meta_type:
        agent_type, agent_type_source = meta_type, "meta.json"
    elif isinstance(out_type, str) and out_type:
        agent_type, agent_type_source = out_type, "workflow_output"

    model: str | None = None
    model_source: str | None = None
    out_model = (out or {}).get("model")
    meta_model = (meta or {}).get("model")
    if isinstance(out_model, str) and out_model:
        model, model_source = out_model, "workflow_output"
    elif isinstance(meta_model, str) and meta_model:
        model, model_source = meta_model, "meta.json"

    label = (out or {}).get("label")
    phase = (out or {}).get("phaseTitle")
    reported_tokens = (out or {}).get("tokens")

    workflow_run_id: object = None
    if meta and meta.get("_workflow_run_id"):
        workflow_run_id = meta["_workflow_run_id"]
    elif out and out.get("_workflow_run_id"):
        workflow_run_id = out["_workflow_run_id"]

    return RecoveredIdentity(
        agent_type=agent_type,
        model=model,
        label=label if isinstance(label, str) and label else None,
        phase=phase if isinstance(phase, str) and phase else None,
        workflow_run_id=workflow_run_id if isinstance(workflow_run_id, str) else None,
        reported_tokens=(
            reported_tokens
            if isinstance(reported_tokens, int) and not isinstance(reported_tokens, bool)
            else None
        ),
        agent_type_source=agent_type_source,
        model_source=model_source,
    )


def build_identity_index_uncached(
    meta_roots: Iterable[str], output_roots: Iterable[str]
) -> dict[str, RecoveredIdentity]:
    """The expensive full-filesystem scan + merge. Never raises: every
    individual-file/root problem is absorbed by the loaders above. Prefer
    `build_identity_index()` (cached) or `load_cached_index()` (cache-only)
    over calling this directly outside of tests/an explicit rebuild."""
    meta_index = _load_meta_index(meta_roots)
    output_index = _load_output_index(output_roots)
    agent_ids = set(meta_index) | set(output_index)
    return {
        agent_id: _merge_identity(meta_index.get(agent_id), output_index.get(agent_id))
        for agent_id in agent_ids
    }


# ---------------------------------------------------------------------------
# Caching.
# ---------------------------------------------------------------------------


def _read_cache(cache_path: str, max_age_seconds: float | None) -> dict[str, RecoveredIdentity] | None:
    """Return the cached index if present and fresh enough, else None.
    `max_age_seconds=None` means "any age is acceptable" (used by
    `load_cached_index()`). Never raises."""
    try:
        if not os.path.isfile(cache_path):
            return None
        if max_age_seconds is not None:
            age = time.time() - os.path.getmtime(cache_path)
            if age > max_age_seconds:
                return None
        with open(cache_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        entries = payload.get("index")
        if not isinstance(entries, dict):
            return None
        return {
            agent_id: RecoveredIdentity.from_dict(v)
            for agent_id, v in entries.items()
            if isinstance(v, dict)
        }
    except Exception:
        return None


def _write_cache(cache_path: str, index: Mapping[str, RecoveredIdentity]) -> None:
    """Best-effort atomic write (temp file + os.replace). Never raises."""
    try:
        parent = os.path.dirname(cache_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp_path = f"{cache_path}.tmp.{os.getpid()}"
        payload = {
            "built_at": _now_iso(),
            "index": {agent_id: ident.to_dict() for agent_id, ident in index.items()},
        }
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, cache_path)
    except Exception:
        return


def build_identity_index(
    *,
    meta_roots: Iterable[str] | None = None,
    output_roots: Iterable[str] | None = None,
    environ: Mapping[str, str] | None = None,
    cache_path: str | None = None,
    max_age_seconds: float | None = DEFAULT_INDEX_MAX_AGE_SECONDS,
    force_rebuild: bool = False,
) -> dict[str, RecoveredIdentity]:
    """Cached entry point: reuse a fresh cache, else scan + persist. See
    module docstring's CACHING section. Never raises -- a scan/write failure
    still returns whatever `build_identity_index_uncached()` computed
    in-memory (or {} if even that raised, which it is documented not to)."""
    resolved_environ: Mapping[str, str] = environ if environ is not None else dict(os.environ)
    resolved_cache_path = cache_path or _default_cache_path(resolved_environ)
    if not force_rebuild:
        cached = _read_cache(resolved_cache_path, max_age_seconds)
        if cached is not None:
            return cached
    resolved_meta_roots = list(meta_roots) if meta_roots is not None else _default_meta_roots(resolved_environ)
    resolved_output_roots = (
        list(output_roots) if output_roots is not None else _default_output_roots(resolved_environ)
    )
    try:
        index = build_identity_index_uncached(resolved_meta_roots, resolved_output_roots)
    except Exception:
        return {}
    _write_cache(resolved_cache_path, index)
    return index


def load_cached_index(
    *, cache_path: str | None = None, environ: Mapping[str, str] | None = None
) -> dict[str, RecoveredIdentity]:
    """Read-only: NEVER scans the filesystem, NEVER writes anything.
    Returns `{}` if the cache is missing/corrupt/unreadable/stale-beyond-any
    limit-that-matters -- there is no staleness check here at all, by
    design (see module docstring: this is the function the per-dispatch
    gate path uses, and it must be O(one small file read), never O(a
    filesystem scan))."""
    resolved_environ: Mapping[str, str] = environ if environ is not None else dict(os.environ)
    resolved_cache_path = cache_path or _default_cache_path(resolved_environ)
    cached = _read_cache(resolved_cache_path, max_age_seconds=None)
    return cached if cached is not None else {}


# ---------------------------------------------------------------------------
# Enrichment -- the provenance contract. See module docstring.
# ---------------------------------------------------------------------------


def _is_missing(field: str, value: object) -> bool:
    if field == "agent_type":
        return value in PLACEHOLDER_AGENT_TYPES
    # `model` has no placeholder SET the way `agent_type` does, but an
    # empty string is just as useless as `None` here (normalize_model("")
    # is "unknown", exactly like normalize_model(None)) -- treat it as
    # missing/recoverable rather than locking it in as first-party data
    # that can never be overridden. See BLOCKER 7 (2026-08-28).
    return value is None or value == ""


def _is_meaningful(field: str, value: object) -> bool:
    if not value:
        return False
    if field == "agent_type":
        return value not in PLACEHOLDER_AGENT_TYPES
    return True


def _attribution_field(
    original_value: object,
    recovered: RecoveredIdentity | None,
    field: str,
    source_field: str,
) -> tuple[object, dict[str, object]]:
    """Resolve one field's (agent_type|model) effective value + provenance
    block. Real first-party data (`_is_missing` false) is NEVER overridden.
    A recovered value that is itself not meaningful (e.g. it only found
    "workflow-subagent" again) is correctly reported `unattributable`, not
    laundered into a false `recovered`."""
    if not _is_missing(field, original_value):
        return original_value, {
            "value": original_value,
            "provenance": "original",
            "source": None,
            "original_value": original_value,
        }

    recovered_value = getattr(recovered, field, None) if recovered is not None else None
    if _is_meaningful(field, recovered_value):
        recovered_source = getattr(recovered, source_field, None) if recovered is not None else None
        return recovered_value, {
            "value": recovered_value,
            "provenance": "recovered",
            "source": recovered_source,
            "original_value": original_value,
        }

    return original_value, {
        "value": original_value,
        "provenance": "unattributable",
        "source": None,
        "original_value": original_value,
    }


def _build_ledger_sibling_facts(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, str]]:
    """agent_id -> {"agent_type": ..., "model": ...} sourced from OTHER rows
    in the SAME ledger that already carry a real, non-placeholder value for
    that field. BLOCKER 2 (2026-08-28): measured live, 41 of 61
    "unrecoverable" model rows (100% of that bucket's tokens, 3.49B) share
    an agent_id with a priced sibling row already present in the SAME
    ledger file -- the two external workflow-metadata sources alone can
    never see this, because they know nothing about the ledger's own
    contents; this is a genuinely separate, third identity source.

    BLOCKER 4 (round 4, 2026-08-28): a field is only ever contributed when
    EVERY row in the duplicate-agent_id group that carries a real value for
    it agrees on that value. Round 3's "first real value seen per field
    wins" rule picked whichever value happened to appear FIRST in file
    order -- for a group with genuinely CONFLICTING facts (e.g. one row
    says sonnet, another says opus for the same agent_id), that produced a
    different, silently-confident dollar figure depending purely on file
    order, with `recovered_model_rows` reporting "inferred" in both cases
    with no disclosure that the inference was actually CONTESTED. A field
    with more than one distinct real value across the group now
    contributes NO fact at all for that field -- identical to the group
    having no real value anywhere -- so a contested fact can never be
    resolved by accident of ordering; it stays `unattributable` instead."""
    seen: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        agent_id = row.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        entry = seen.setdefault(agent_id, {"agent_type": set(), "model": set()})
        agent_type = row.get("agent_type")
        if isinstance(agent_type, str) and agent_type and agent_type not in PLACEHOLDER_AGENT_TYPES:
            entry["agent_type"].add(agent_type)
        model = row.get("model")
        if isinstance(model, str) and model:
            entry["model"].add(model)

    facts: dict[str, dict[str, str]] = {}
    for agent_id, values_by_field in seen.items():
        resolved: dict[str, str] = {}
        for field, values in values_by_field.items():
            if len(values) == 1:
                resolved[field] = next(iter(values))
            # len == 0: no real value anywhere in the group -- no fact.
            # len > 1: CONTESTED -- deliberately no fact either, see above.
        if resolved:
            facts[agent_id] = resolved
    return facts


def _widen_index_with_ledger_siblings(
    rows: Iterable[Mapping[str, object]], index: Mapping[str, RecoveredIdentity]
) -> dict[str, RecoveredIdentity]:
    """Merge `index` (the meta.json/workflow_output identity index) with the
    ledger-internal sibling-row source built by `_build_ledger_sibling_facts`.
    See BLOCKER 2. This is purely ADDITIVE and strictly lowest-priority: it
    NEVER overrides a field the external index already resolved to something
    meaningful -- it only fills a field that source left missing/placeholder
    (mirroring `_merge_identity()`'s own "only widen" contract for the two
    existing sources). An agent_id with no real fact anywhere (neither
    `index` nor the ledger itself) is left untouched."""
    sibling_facts = _build_ledger_sibling_facts(rows)
    if not sibling_facts:
        return dict(index)
    widened: dict[str, RecoveredIdentity] = dict(index)
    for agent_id, facts in sibling_facts.items():
        existing = widened.get(agent_id)
        agent_type = existing.agent_type if existing else None
        agent_type_source = existing.agent_type_source if existing else None
        if not _is_meaningful("agent_type", agent_type) and facts.get("agent_type"):
            agent_type, agent_type_source = facts["agent_type"], "ledger_sibling"
        model = existing.model if existing else None
        model_source = existing.model_source if existing else None
        if not _is_meaningful("model", model) and facts.get("model"):
            model, model_source = facts["model"], "ledger_sibling"
        if existing is None and agent_type is None and model is None:
            continue
        widened[agent_id] = RecoveredIdentity(
            agent_type=agent_type,
            model=model,
            label=existing.label if existing else None,
            phase=existing.phase if existing else None,
            workflow_run_id=existing.workflow_run_id if existing else None,
            reported_tokens=existing.reported_tokens if existing else None,
            agent_type_source=agent_type_source,
            model_source=model_source,
        )
    return widened


def enrich_row(row: Mapping[str, object], index: Mapping[str, RecoveredIdentity]) -> dict[str, object]:
    """Return a NEW dict: `row` plus recovered `agent_type`/`model` and an
    `attribution` provenance block. Never mutates `row`. See module
    docstring's PROVENANCE CONTRACT."""
    enriched = dict(row)
    agent_id = row.get("agent_id")
    recovered = index.get(agent_id) if isinstance(agent_id, str) else None

    agent_type_value, agent_type_block = _attribution_field(
        row.get("agent_type"), recovered, "agent_type", "agent_type_source"
    )
    model_value, model_block = _attribution_field(row.get("model"), recovered, "model", "model_source")

    enriched["agent_type"] = agent_type_value
    enriched["model"] = model_value
    attribution: dict[str, object] = {
        "agent_type": agent_type_block,
        "model": model_block,
    }
    if recovered is not None:
        attribution["label"] = recovered.label
        attribution["phase"] = recovered.phase
        attribution["workflow_run_id"] = recovered.workflow_run_id
        attribution["reported_tokens_untrusted"] = recovered.reported_tokens
    enriched["attribution"] = attribution
    return enriched


def enrich_rows(
    rows: Iterable[Mapping[str, object]], index: Mapping[str, RecoveredIdentity]
) -> list[dict[str, object]]:
    """Enrich every row independently. ALWAYS returns exactly one output
    row per input row (never merges, drops, or synthesizes rows -- see
    module docstring's DOUBLE-COUNTING RULE: a row is a row, regardless of
    whether its agent_id repeats elsewhere in `rows`). The identity `index`
    passed in is widened (BLOCKER 2, `_widen_index_with_ledger_siblings()`)
    with a same-ledger sibling-row join BEFORE any row is enriched, so an
    otherwise-unrecoverable row can borrow an already-known agent_type/model
    from another row sharing its `agent_id` in this same `rows` set --
    purely additive, never a relaxation of `enrich_row()`'s own
    never-override-real-data contract."""
    rows = list(rows)
    widened_index = _widen_index_with_ledger_siblings(rows, index)
    return [enrich_row(row, widened_index) for row in rows]


# ---------------------------------------------------------------------------
# Coverage reporting -- the headline honesty numbers.
# ---------------------------------------------------------------------------


def _is_null_tokens_total(row: Mapping[str, object]) -> bool:
    """True iff `_row_tokens_total(row)` would fall back to its 0.0
    default -- i.e. `tokens_total` is missing, JSON `null`, a bool, or any
    other non-numeric value. BLOCKER 5 (round 11 review finding, round 12
    fix, 2026-08-28): this is the exact population `coverage_report()` was
    silently absorbing into every denominator/bucket with zero visibility
    -- 48 real live-ledger rows measured with `tokens_total: null`. Kept as
    its own named predicate (rather than inlined at each call site) so
    `coverage_report()`'s disclosure counter and `_row_tokens_total()`'s
    own fallback can never drift apart."""
    tt = row.get("tokens_total")
    return isinstance(tt, bool) or not isinstance(tt, (int, float))


def _row_tokens_total(row: Mapping[str, object]) -> float:
    if _is_null_tokens_total(row):
        return 0.0
    return float(row.get("tokens_total"))


def _is_priced_model(model_value: object) -> bool:
    """True iff `model_value` normalizes to a pricing family cycle_budget.py
    can actually charge for -- the EXACT predicate its own pricing gate uses
    (`normalize_model(...) in PRICING_USD_PER_MTOK`), not mere presence of a
    model string. BLOCKER 4 (2026-08-28): a recovered (or even original)
    model value can be a coarse/internal code-name string (e.g., as of
    2026-08-28, "claude-fable-5" -- since priced, see PRICING_USD_PER_MTOK's
    2026-09-05 "RESOLVED" note; "claude-imaginary-9" is the current example
    of a genuinely unpublished model) that IS present -- and therefore
    counted "priceable" by a presence-only check -- yet cycle_budget.py
    cannot price a single token of it (measured live 2026-08-28: 40 rows /
    419.8M tokens, 2.05% of the whole ledger, all forcing
    `unpriced-model-in-window`). Imported LAZILY (never
    at module import time) to avoid load-order coupling -- cycle_budget.py
    itself only ever imports this module lazily inside a function body, see
    its own docstring. #7 (round 10, 2026-08-28): this used to degrade to a
    bare presence check (`bool(model_value)`) when `cycle_budget` could not
    be imported or its own call raised -- but a presence check is MORE
    OPTIMISTIC than the real predicate (a model string is almost always
    present; a priceable FAMILY match is the narrower, real question), so
    that degradation inverted this module's own conservative bias on the
    one path most likely to fail quietly (an environment where
    `cycle_budget` genuinely cannot be imported). Returns `False` on any
    failure instead -- this function's job is specifically to answer
    whether cycle_budget.py's OWN pricing gate would price this model; an
    environment where that gate cannot even be consulted must report
    'no, not confirmed priceable', never a guess in the generous direction."""
    try:
        import cycle_budget
    except Exception:
        return False
    try:
        return cycle_budget.normalize_model(model_value) in cycle_budget.PRICING_USD_PER_MTOK
    except Exception:
        return False


def _collapse_duplicate_agent_tokens(rows: list[Mapping[str, object]]) -> tuple[list[float], int]:
    """Per-row EFFECTIVE token contribution for any total/percentage in this
    report, plus how many rows were collapsed. BLOCKER 3 (2026-08-28):
    measured live, the SAME agent_id can appear as two independent ledger
    lines -- a normal claim/release plus a LATER, LARGER cumulative
    'stopped-unjoined' reap of the SAME agent's still-running spend (44
    duplicate-agent_id groups, 1.78B tokens / 8.72% of the whole ledger
    counted twice by naive summation). Only the row with the largest
    `tokens_total` per duplicate-agent_id group contributes tokens to any
    total computed here; every other same-agent_id row contributes 0 -- it
    remains a real, independently-attributed ROW (see `enrich_rows()`'s own
    never-merge contract: this function never drops or merges rows, it only
    changes what a row contributes to a SUM). A row with no/blank agent_id
    is never grouped, exactly as before this fix existed."""
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        agent_id = row.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            groups.setdefault(agent_id, []).append(i)
    effective = [_row_tokens_total(row) for row in rows]
    collapsed = 0
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        winner = max(idxs, key=lambda i: (effective[i], -i))
        for i in idxs:
            if i != winner:
                effective[i] = 0.0
                collapsed += 1
    return effective, collapsed


def coverage_report(
    rows: Iterable[Mapping[str, object]], index: Mapping[str, RecoveredIdentity]
) -> dict[str, object]:
    """How many rows/tokens are `original`, `recovered`, and STILL
    `unattributable`, for `agent_type` and `model` independently, plus a
    `model`-keyed headline (`priceable_before_recovery` /
    `priceable_after_recovery` / `recovered_but_unpriced_family` /
    `still_unpriceable`) matching the exact framing this module was
    commissioned against. `priceable_*` is classified by whether the model
    value actually normalizes to a family `cycle_budget.py` can price
    (`_is_priced_model()`, BLOCKER 4) -- NOT by mere presence of a model
    string, which would silently overstate coverage for a recovered-but-
    unrecognized internal model name. Every duplicate-agent_id ledger line
    (BLOCKER 3) has its token contribution to any total/bucket here
    collapsed to only the largest reading per agent_id; `identity_index` is
    additionally widened with a same-ledger sibling-row join (BLOCKER 2,
    `_widen_index_with_ledger_siblings()`) before anything is classified.
    The still-unattributable/still-unpriceable buckets are ALWAYS present
    in the output, even when their count is genuinely zero -- never omitted
    or silently rounded away. `null_tokens_total_rows` (BLOCKER 5, round
    12, 2026-08-28) discloses how many input rows had a missing/null/
    non-numeric `tokens_total` -- that population contributes 0.0 tokens to
    every bucket/total above via `_row_tokens_total()`'s own fallback, and
    this counter is what makes that silent contribution visible rather
    than absorbed with no trace."""
    rows = list(rows)
    widened_index = _widen_index_with_ledger_siblings(rows, index)
    effective_tokens, collapsed_duplicate_rows = _collapse_duplicate_agent_tokens(rows)

    total_rows = 0
    total_tokens = 0.0
    buckets: dict[str, dict[str, list[float]]] = {
        "agent_type": {"original": [0, 0.0], "recovered": [0, 0.0], "unattributable": [0, 0.0]},
        "model": {"original": [0, 0.0], "recovered": [0, 0.0], "unattributable": [0, 0.0]},
    }
    priceable_before_rows = 0
    priceable_before_tokens = 0.0
    priceable_after_rows = 0
    priceable_after_tokens = 0.0
    recovered_unpriced_rows = 0
    recovered_unpriced_tokens = 0.0
    null_tokens_total_rows = 0

    for i, row in enumerate(rows):
        enriched = enrich_row(row, widened_index)
        total_rows += 1
        tt = effective_tokens[i]
        total_tokens += tt
        if _is_null_tokens_total(row):
            # BLOCKER 5 (round 11 review finding, round 12 fix,
            # 2026-08-28): disclose this population instead of letting it
            # silently contribute 0.0 tokens to every bucket/denominator
            # above with no visibility -- mirrors the `collapsed_duplicate_
            # rows` disclosure right beside it in the result dict below.
            null_tokens_total_rows += 1
        for field in ("agent_type", "model"):
            provenance = enriched["attribution"][field]["provenance"]
            bucket = buckets[field][provenance]
            bucket[0] += 1
            bucket[1] += tt

        if _is_priced_model(row.get("model")):
            priceable_before_rows += 1
            priceable_before_tokens += tt

        if _is_priced_model(enriched["model"]):
            priceable_after_rows += 1
            priceable_after_tokens += tt
        elif enriched["attribution"]["model"]["provenance"] == "recovered":
            # BLOCKER 4: an identity WAS recovered (not unattributable) but
            # it still doesn't price -- kept visible on its own, never
            # silently folded into priceable_after_recovery.
            recovered_unpriced_rows += 1
            recovered_unpriced_tokens += tt

    def _pct(tokens: float) -> float:
        return round(100.0 * tokens / total_tokens, 2) if total_tokens else 0.0

    def _field_report(field: str) -> dict[str, object]:
        out: dict[str, object] = {}
        for provenance, (rcount, tcount) in buckets[field].items():
            out[provenance] = {
                "rows": int(rcount),
                "tokens": tcount,
                "pct_of_total_tokens": _pct(tcount),
            }
        return out

    result: dict[str, object] = {
        "total_rows": total_rows,
        "total_tokens": total_tokens,
        "collapsed_duplicate_rows": collapsed_duplicate_rows,
        "null_tokens_total_rows": null_tokens_total_rows,
        "agent_type": _field_report("agent_type"),
        "model": _field_report("model"),
    }

    result["priceable_before_recovery"] = {
        "rows": priceable_before_rows,
        "tokens": priceable_before_tokens,
        "pct_of_total_tokens": _pct(priceable_before_tokens),
    }
    result["priceable_after_recovery"] = {
        "rows": priceable_after_rows,
        "tokens": priceable_after_tokens,
        "pct_of_total_tokens": _pct(priceable_after_tokens),
    }
    result["recovered_but_unpriced_family"] = {
        "rows": recovered_unpriced_rows,
        "tokens": recovered_unpriced_tokens,
        "pct_of_total_tokens": _pct(recovered_unpriced_tokens),
        "reason": (
            "an identity WAS recovered for this row's model (it is not "
            "unattributable) but the recovered value does not normalize to "
            "a known pricing family in cycle_budget.PRICING_USD_PER_MTOK "
            "(e.g. an internal/unreleased model code name) -- counted here, "
            "NEVER silently folded into priceable_after_recovery."
        ),
    }
    result["still_unpriceable"] = {
        "rows": total_rows - priceable_after_rows,
        "tokens": total_tokens - priceable_after_tokens,
        "pct_of_total_tokens": _pct(total_tokens - priceable_after_tokens),
        "reason": (
            "model still could not be PRICED after full recovery (both "
            "external workflow-metadata sources, PLUS a ledger-internal "
            "sibling-row join for any agent_id with no surviving workflow "
            "metadata -- see _build_ledger_sibling_facts(), BLOCKER 2). "
            "What remains is three genuinely different buckets, all counted "
            "in this total: (a) no real model was EVER recorded for this "
            "agent_id anywhere -- ledger, meta.json tree, or task-output "
            "tree -- typically a direct, non-workflow Task dispatch reaped "
            "before any model was ever written down (the true structural "
            "gap, and by far the smallest of the three on the live ledger); "
            "(b) an identity WAS recovered but names an internal/unreleased "
            "model this pricing table does not yet know (see "
            "recovered_but_unpriced_family for that sub-bucket alone); or "
            "(c) the ORIGINAL ledger row already carried such an "
            "internal/unreleased model name directly (never went through "
            "recovery at all, so it is NOT in recovered_but_unpriced_family "
            "either) -- rare, but real."
        ),
    }
    return result


# ---------------------------------------------------------------------------
# Ledger I/O for the CLI only (a small, self-contained mirror of
# cycle_budget.py's own `_safe_load_ledger_rows` -- duplicated deliberately
# rather than importing a private function from a sibling module).
# ---------------------------------------------------------------------------


def _load_ledger_rows(ledger_path: str) -> tuple[list[dict[str, object]], int]:
    if not ledger_path or not os.path.isfile(ledger_path):
        return [], 0
    rows: list[dict[str, object]] = []
    malformed = 0
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    malformed += 1
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
                else:
                    malformed += 1
    except OSError:
        return [], 0
    return rows, malformed


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _add_common_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--ledger", dest="ledger_path", default=None, help="Override the spend ledger path.")
    sp.add_argument(
        "--meta-roots",
        dest="meta_roots",
        default=None,
        help="Colon-separated roots to search for agent-*.meta.json "
        "(default: $CSA_WORKFLOW_META_ROOTS or ~/.claude/projects).",
    )
    sp.add_argument(
        "--output-roots",
        dest="output_roots",
        default=None,
        help="Colon-separated roots to search for tasks/*.output (default: "
        "$CSA_WORKFLOW_OUTPUT_ROOTS or the temp dir's claude-* directories).",
    )
    sp.add_argument(
        "--cache-path", dest="cache_path", default=None, help="Override the identity-index cache file."
    )
    sp.add_argument(
        "--max-index-age",
        dest="max_index_age",
        type=float,
        default=DEFAULT_INDEX_MAX_AGE_SECONDS,
        help="Rebuild the cached index if older than this many seconds (default 900).",
    )
    sp.add_argument(
        "--rebuild-index",
        dest="rebuild_index",
        action="store_true",
        help="Force a fresh filesystem scan even if a fresh cache exists.",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spend_attribution.py",
        description="Recover agent_type/model identity for spend.jsonl rows "
        "the ledger itself could not price, from Claude Code's own "
        "workflow-dispatch metadata.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_coverage = sub.add_parser(
        "coverage", help="Report original/recovered/still-unattributable token coverage."
    )
    _add_common_args(p_coverage)

    p_enrich = sub.add_parser(
        "enrich", help="Emit every ledger row enriched with recovered identity + provenance."
    )
    _add_common_args(p_enrich)
    p_enrich.add_argument(
        "--out", dest="out_path", default=None, help="Write enriched rows (JSONL) here instead of stdout."
    )

    return parser


def run(argv: list[str], environ: dict[str, str] | None = None) -> tuple[int, object]:
    """Pure-ish core: parse argv, compute, return (exit_code, payload).
    Never prints -- `main()` is the thin I/O wrapper, matching
    cycle_budget.py's established split."""
    resolved_environ = environ if environ is not None else dict(os.environ)
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 2)
        return code, ({} if code == 0 else {"error": "argument-error"})

    ledger_path = args.ledger_path or _default_ledger_path(resolved_environ)
    meta_roots = args.meta_roots.split(":") if args.meta_roots else None
    output_roots = args.output_roots.split(":") if args.output_roots else None

    index = build_identity_index(
        meta_roots=meta_roots,
        output_roots=output_roots,
        environ=resolved_environ,
        cache_path=args.cache_path,
        max_age_seconds=args.max_index_age,
        force_rebuild=args.rebuild_index,
    )
    rows, malformed = _load_ledger_rows(ledger_path)

    if args.command == "coverage":
        report = coverage_report(rows, index)
        report["ledger_path"] = ledger_path
        report["malformed_lines"] = malformed
        report["identity_index_size"] = len(index)
        return 0, report

    # command == "enrich"
    enriched = enrich_rows(rows, index)
    out_path = getattr(args, "out_path", None)
    if out_path:
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                for row in enriched:
                    fh.write(json.dumps(row) + "\n")
        except OSError as exc:
            return 1, {"error": f"write-failed:{exc}"}
        return 0, {"written": len(enriched), "out_path": out_path}
    return 0, {"rows": enriched}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    exit_code, payload = run(argv)
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list) and "error" not in payload:
        for row in payload["rows"]:
            print(json.dumps(row))
    elif payload:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
