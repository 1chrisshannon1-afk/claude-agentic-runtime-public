#!/usr/bin/env python3
"""model_pin_parity — REPORT-ONLY check: runtime agent pins vs model_policy.json.

Part of the oversight system's token policy (#4400, CLAUDE.md §13 / plan §4b.2):
every agent file in the RUNTIME roster (~/.claude/agents/*.md) must declare an
explicit ``model:`` pin, and that pin must match ``agent_pins`` in
``~/.claude/knowledge/model_policy.json`` — the single machine-readable policy
source. An unpinned agent silently inherits the dispatching session's model
(the documented 2026-08-01 credit-burn failure mode); a mismatched pin means
the policy and reality have drifted.

Reads four inputs: the on-disk agent roster (~/.claude/agents/*.md), the
policy file above, and — only when the caller supplies them — CLAUDE.md's
own §13 oversight-roster table (``contract_path``) and the REAL spend
ledger (``spend_path``, ~/.claude/.agent_budget/spend.jsonl). The first is
the third input this module checks every sanctioned-Opus extension agent
against; a name missing from that table is reported as the
``contract-roster-drift`` violation class. The second (added 2026-09-01,
AA-0063 / gate-optimization plan waste-elimination P2) cross-references the
REAL, currently-dispatching agent_type population against the roster +
policy: ``unpinned-live-agent-type`` (a real dispatch with no governance
anywhere) and ``unsanctioned-fable-dispatch`` (a dispatch that ran on the
2x-Opus-priced ``claude-fable-5`` model, which nothing in this policy is
ever legitimately pinned to).

DELIBERATELY REPORT-ONLY — design constraints from the plan review:
  * This module NEVER calls ``emit_stop_block`` or ``emit_pretooluse_deny``.
    Extending check_safety_core_parity.py was explicitly rejected: that module
    Stop-blocks under enforcement, so a single unpinned file would wedge every
    session on the machine. A drift REPORT that sentinel's daily sweep (and
    ``enforcement_doctor.sh``) surfaces is the designed teeth.
  * Scope is the RUNTIME roster only. A runtime hook must never hardcode a
    product-repo path (contract preamble); per-repo rosters get their own
    repo-local checks, tracked separately.

Exit code: always 0 (report-only; consumers parse the output, never the code).
Output: one line per violation, then a summary line ``model_pin_parity: N
violation(s)`` — N==0 is the clean signal.

This module owns exactly two files:
  ~/.claude/hooks/model_pin_parity.py  (this file)
  ~/.claude/hooks/tests/test_model_pin_parity.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_HOME = os.path.expanduser("~")
DEFAULT_AGENTS_DIR = os.path.join(_HOME, ".claude", "agents")
DEFAULT_POLICY_PATH = os.path.join(_HOME, ".claude", "knowledge", "model_policy.json")
# daily_sweep.txt (and any other headless caller) invokes this script with no
# arguments, so the contract-roster-drift check (below) needs its own default
# rather than requiring a third positional CLI arg every caller must supply.
DEFAULT_CONTRACT_PATH = os.path.join(_HOME, ".claude", "CLAUDE.md")
# Same story for the spend-ledger cross-reference (AA-0063): main() always
# supplies this default; every tmp_path fixture test leaves spend_path=None
# (check()'s own default) and never touches the live ledger.
DEFAULT_SPEND_PATH = os.path.join(_HOME, ".claude", ".agent_budget", "spend.jsonl")
# Item 9 (2026-09-01 fix round): same hermeticity contract again for the
# repo-registry cross-reference (a live-dispatching product-domain agent
# type is sanctioned to be governed in its OWN repo until Phase 2
# migration, per CLAUDE.md's own preamble carve-out).
DEFAULT_REPO_REGISTRY_PATH = os.path.join(
    _HOME, ".claude", "knowledge", "repo_registry.json"
)

_MODEL_RE = re.compile(r"^model:\s*(\S+)\s*$", re.MULTILINE)
_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
_ROSTER_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")

# Ledger cross-reference window (AA-0063): "last 30 days of rows" per the
# recommendation's own metric definition.
LEDGER_WINDOW_DAYS = 30

# WS2.1 step 5 (plan_lane_control_adoption_master_2026_09_20.md §2.1 item 5,
# #5828): the date agent_budget.py's WS2.1 step 4 transcript-fallback
# model-recovery landed (see that module's own docstring). `pin_tier_mismatches`
# reports 18 violations TODAY (2026-09-20), every one of them a real,
# pre-existing mismatch recorded before this land date -- a "lookback
# artifact" the exit criterion explicitly excludes ("0 violations among
# rows dated after the land date"). Rows dated on/after this date are judged
# normally; rows dated before it are reported SEPARATELY as lookback, never
# silently dropped. A bare date string (matching `_row_within_window`'s own
# `%Y-%m-%dT%H:%M:%SZ` parse convention, compared as the date prefix) rather
# than a `datetime` object so it stays a trivially-greppable single line, the
# same convention this module already uses for every other constant.
MODEL_OBSERVED_SINCE = "2026-09-21"

# Catch-all agent_type labels this policy pins in `agent_pins` (AA-0063) that
# have, BY DESIGN, no `agents/<name>.md` file on disk: they are either the
# Claude Code client's own generic Task-dispatch bucket labels
# ("workflow-subagent", "general-purpose", "execute", "dispatch",
# "ultracode") or a built-in helper the client dispatches itself
# ("claude-code-guide") -- none of these is, or ever will be, an authored
# agent definition in this runtime's roster. Without this exemption, pinning
# them in agent_pins (the whole point of AA-0063) would immediately trip the
# pre-existing `phantom-policy-entry` check below, which exists to catch the
# OPPOSITE problem (a stale pin whose real agent file was deleted) -- these
# pins never had a file to begin with, and never will.
CATCHALL_TYPES_WITHOUT_FILES: frozenset[str] = frozenset(
    {
        "workflow-subagent",
        "general-purpose",
        "execute",
        "dispatch",
        "ultracode",
        "claude-code-guide",
    }
)

# The exception-token audit trail (record_model_exception.py's durable
# append-only grant log, item 6 of the model-pin-enforcement build) — a
# sibling of the ephemeral per-token store under the same directory.
DEFAULT_EXCEPTIONS_DIR = os.path.join(_HOME, ".claude", ".model_exceptions")

# Item 9 (2026-09-01 fix round; "claude" added Nit 4, 2026-09-01 fix round
# 2): the client's OWN built-in catch-all dispatch modes (CLAUDE.md §1's own
# framing: "Catch-all agent types (general-purpose, Plan, Explore, claude)
# have no model pin of their own" -- "there is no file to pin them with").
# Distinct from CATCHALL_TYPES_WITHOUT_FILES above (which covers types THIS
# runtime chose to pin anyway, e.g. general-purpose, now that AA-0063
# landed): these have no home to pin them in even in principle, on THIS
# client, so `unpinned-live-agent-type` must never flag them either — there
# is no fix a session in this repo could ever apply.
CLIENT_BUILTIN_CATCHALL_TYPES: frozenset[str] = frozenset({"Explore", "Plan", "claude"})

# The unsanctioned-fable-dispatch model PREFIX (AA-0063; Item 10, 2026-09-01
# fix round; comment corrected 2026-09-01 fix round 4, Doc Nit 3 — an
# earlier version of this comment claimed the live ledger carries
# context-window-suffixed FABLE variants; verified false, all 14 live
# claude-fable-5 rows are the bare literal). A prefix, not an exact
# literal, on the OPUS PRECEDENT: this same ledger's `model` field already
# carries context-window-suffixed variants for the model family that DOES
# have them today (`claude-opus-5[1m]`: 788 rows; `claude-opus-4-8[1m]`: 2
# rows, live-measured 2026-09-01) — an exact-literal match would silently
# miss a same-shaped future fable variant the moment one is dispatched, for
# the identical reason it already would for opus. Nothing in this policy
# is ever legitimately pinned to any fable variant -- see check()'s own
# docs for why that makes this check effectively "flag every fable
# dispatch", by design.
_FABLE_MODEL_PREFIX = "claude-fable"


def frontmatter_name(text: str) -> str | None:
    """The ``name:`` value from the frontmatter block, or None. The frontmatter
    name is the DISPATCH identity — the policy is keyed by it, with the
    filename stem as fallback only (reviewed finding R3-5). Never raises."""
    try:
        if not text.startswith("---"):
            return None
        end = text.find("\n---", 3)
        if end < 0:
            return None
        m = _NAME_RE.search(text[:end])
        return m.group(1) if m else None
    except Exception:
        return None


def frontmatter_model(text: str) -> str | None:
    """The ``model:`` value from an agent file's YAML frontmatter, or None.

    Only the frontmatter block (between the leading ``---`` fences) is
    consulted, so a ``model:`` string in the prose body can never satisfy or
    fake a pin. Never raises.
    """
    try:
        if not text.startswith("---"):
            return None
        end = text.find("\n---", 3)
        if end < 0:
            return None
        m = _MODEL_RE.search(text[:end])
        return m.group(1) if m else None
    except Exception:
        return None


def _extract_section_13(contract_text: str) -> str:
    """The `## 13.` heading through the next line that is exactly ``---``.

    Returns "" when no `## 13.` heading is present. Never raises.
    """
    lines = (contract_text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## 13."):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] == "---":
            end = i
            break
    return "\n".join(lines[start:end])


def _section_13_agent_names(section_text: str) -> set[str]:
    """Cell-1 agent names from every ``|``-prefixed data row.

    Skips the header row (``agent``) and the ``|---|---|---|`` separator row.
    Strips a trailing parenthetical (``launch-director (opus)`` -> ``launch-director``).
    Never raises.
    """
    names: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        first = cells[0]
        if first.lower() == "agent":
            continue
        if set(first) <= {"-"}:
            continue
        name = _ROSTER_PAREN_RE.sub("", first).strip()
        if name:
            names.add(name)
    return names


def contract_roster_drift(
    contract_text: str,
    opus_agents: set[str],
    contract_review_agents: set[str],
) -> list[str]:
    """Every sanctioned-Opus EXTENSION agent must appear in CLAUDE.md's §13 table.

    The extension set is ``opus_agents - contract_review_agents`` — the two §10
    review-boundary agents (``plan-reviewer``, ``code-reviewer``) are deliberately
    absent from the §13 oversight roster and must never be flagged here. Pure
    function (no IO); never raises.
    """
    extension = set(opus_agents) - set(contract_review_agents)
    table_names = _section_13_agent_names(_extract_section_13(contract_text))
    out: list[str] = []
    for name in sorted(extension):
        if name not in table_names:
            out.append(
                f"contract-roster-drift: '{name}' is a sanctioned-Opus extension "
                "agent (OPUS_AGENTS - CONTRACT_REVIEW_AGENTS) but is missing from "
                "CLAUDE.md's §13 table"
            )
    return out


def _extract_section_10(contract_text: str) -> str:
    """The `## 10.` heading through the next line starting with ``## ``.

    Unlike ``_extract_section_13`` (which stops at a literal ``---`` because
    §13 runs to the contract's closing separator), §10 is followed by further
    ``## N.`` sections, so the next real heading is the correct terminator.
    Returns "" when no `## 10.` heading is present. Never raises.
    """
    lines = (contract_text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## 10."):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def contract_section10_drift(
    contract_text: str,
    opus_agents: set[str],
    contract_review_agents: set[str],
) -> list[str]:
    """Every sanctioned-Opus EXTENSION agent must be NAMED (backticked) in §10.

    Added 2026-09-05 (ASA audit fix 2): ``marketing-director`` sat in
    ``OPUS_AGENTS`` and §13's table while absent from §10's sanctioned-Opus
    bullet — the human-readable authority for WHY the pin is sanctioned, whose
    own text says "that tuple and this bullet must move together" — and the
    table-only ``contract_roster_drift`` check passed throughout. This second
    half closes that gap.

    PREDICATE, stated honestly (the F1 lesson — never let the predicate be
    weaker than the name implies): this requires the literal backticked token
    ``` `<name>` ``` to appear ANYWHERE in §10's text. It does NOT parse the
    enumeration's grammar, so a §10 mention outside the sanctioning bullet
    would satisfy it — a deliberate trade for robustness against prose
    rewording; the §13 half still independently requires a real table row.
    A contract with no ``## 10.`` heading flags every extension agent
    (fail-loud, mirroring the missing-§13 behavior). Pure function; never
    raises.
    """
    extension = set(opus_agents) - set(contract_review_agents)
    section = _extract_section_10(contract_text)
    out: list[str] = []
    for name in sorted(extension):
        if f"`{name}`" not in section:
            out.append(
                f"contract-roster-drift: '{name}' is a sanctioned-Opus extension "
                "agent (OPUS_AGENTS - CONTRACT_REVIEW_AGENTS) but is not named in "
                "CLAUDE.md §10's sanctioned-Opus bullet — that bullet's own rule "
                "says the tuple and the bullet must move together"
            )
    return out


def _load_spend_rows(spend_path: str) -> list[dict]:
    """Best-effort JSONL read of the spend ledger. Never raises; a missing,
    unreadable, or malformed-line ledger degrades to an empty list (a
    malformed individual line is skipped, matching every other ledger
    reader in this runtime's hooks — never a crash over one bad line)."""
    rows: list[dict] = []
    try:
        with open(spend_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except Exception:
        return []
    return rows


def _row_within_window(row: Mapping[str, object], now: datetime, days: int) -> bool:
    ts = row.get("ts")
    if not isinstance(ts, str):
        return False
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (now - dt).total_seconds() <= days * 86400


_TS_SHAPE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _row_is_post_land(row: Mapping[str, object], since: str) -> bool:
    """WS2.1 step 5: True iff `row["ts"]` is a real ISO timestamp string
    dated on/after `since` (a bare `YYYY-MM-DD` date, compared as a string
    PREFIX — matching `agent_budget.py`'s own `_SINCE_RE` convention for a
    ledger `--since` filter: ISO-8601 timestamps sort lexicographically, so
    a plain string comparison is correct and avoids a second datetime
    parse). A row with no `ts` at all, a `ts` that isn't a string, or a
    `ts` that doesn't even shape-match `YYYY-MM-DD...` (fix round, N1:
    a malformed value like `"garbage"`, `"9999"`, or `"2026/09/21"` sorts
    ABOVE any real date under a bare `>=` string compare — `"garbage" >=
    "2026-09-21"` is True, and `"9999" >= "2026-09-21"` is also True,
    since both start with a byte that lexicographically outranks `"2"` —
    silently miscounting a malformed row as post-land, the OPPOSITE of
    this function's own documented conservative direction) is treated as
    NOT post-land — it falls to the lookback bucket instead, which is the
    conservative direction: an un-dated or malformed-dated row can never
    be PROVEN to postdate the fix, so it must never suppress a real
    violation by miscounting as filtered-by-window. NOTE (N2): a `ts` with
    a non-UTC offset (anything not literally ending in a bare `Z`) is
    still compared as a plain string prefix here, same as every other
    date-window check in this module (`_row_within_window`) — this is the
    conservative direction (a non-`Z` local-time value sorts either
    correctly or, at worst, borderline-early relative to its true UTC
    instant) and every real spend.jsonl row observed on this machine is
    `...Z`-suffixed, so it is not specially handled. Pure; never raises."""
    ts = row.get("ts")
    if not isinstance(ts, str) or not ts:
        return False
    if not _TS_SHAPE_RE.match(ts):
        return False
    return ts >= since


def live_agent_types(
    rows: Iterable[Mapping[str, object]], now: datetime, days: int = LEDGER_WINDOW_DAYS
) -> set[str]:
    """Real (non-placeholder) `agent_type` strings dispatched in `rows`
    within the last `days` days of `now`. A `None`/empty `agent_type` is
    EXCLUDED — it represents missing identity, not an actual dispatched type
    that could ever be pinned (mirrors spend_attribution.PLACEHOLDER_AGENT_
    TYPES' treatment of the same two values; "workflow-subagent" itself IS
    included here, since — unlike None/"" — it is a real, pinnable type
    name, exactly the one AA-0063 exists to get a policy entry). Pure
    function; never raises."""
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _row_within_window(row, now, days):
            continue
        agent_type = row.get("agent_type")
        if isinstance(agent_type, str) and agent_type:
            out.add(agent_type)
    return out


def _load_repo_registry(registry_path: str) -> dict[str, str]:
    """repo slug -> expanded, absolute root path, from repo_registry.json
    (the SAME registry `agentarch_metric_check.py`'s own `${REPO:<slug>}`
    resolution already trusts). Never raises; a missing/unparseable
    registry, or a repo entry with no real `root` string, degrades to
    skipping that entry rather than crashing the whole read."""
    out: dict[str, str] = {}
    try:
        with open(registry_path, encoding="utf-8") as fh:
            data = json.load(fh)
        repos = data.get("repos")
        if not isinstance(repos, dict):
            return {}
        for slug, entry in repos.items():
            if not isinstance(entry, dict):
                continue
            root = entry.get("root")
            if isinstance(root, str) and root:
                out[slug] = os.path.expanduser(root)
    except Exception:
        return {}
    return out


def registered_repo_agent_names(registry_path: str) -> set[str]:
    """Every agent NAME with a real `<repo_root>/.claude/agents/<name>.md`
    file, across every repo in repo_registry.json (Item 9, 2026-09-01 fix
    round): a product-domain roster is SANCTIONED to live in its own repo
    until Phase 2 migration (CLAUDE.md's own preamble carve-out), so
    `unpinned-live-agent-type`'s "has no agents/<name>.md file" claim is
    factually WRONG for these names — they ARE governed, just not by this
    runtime's own `~/.claude/agents/` roster. Reads the frontmatter `name:`
    when present (mirroring this module's own dispatch-identity convention
    for the runtime roster, `frontmatter_name`), falling back to the
    filename stem. A repo root that does not exist, or has no
    `.claude/agents/` directory, contributes nothing (never an error).
    Never raises."""
    names: set[str] = set()
    for root in _load_repo_registry(registry_path).values():
        agents_dir = os.path.join(root, ".claude", "agents")
        try:
            files = [
                f
                for f in os.listdir(agents_dir)
                if f.endswith(".md") and not f.startswith(".")
            ]
        except Exception:
            continue
        for fname in files:
            stem = fname[: -len(".md")]
            try:
                with open(os.path.join(agents_dir, fname), encoding="utf-8") as fh:
                    text = fh.read()
            except Exception:
                names.add(stem)
                continue
            names.add(frontmatter_name(text) or stem)
    return names


def unpinned_live_agent_types(
    live_types: Iterable[str],
    known_files: Iterable[str],
    pins: Mapping[str, str],
    exempt: Iterable[str] = (),
) -> list[str]:
    """`unpinned-live-agent-type` violations (AA-0063): a real, currently-
    dispatching `agent_type` with neither an on-disk `agents/<name>.md` file
    nor an `agent_pins` entry — no governance anywhere for real spend.
    `exempt` (Item 9, 2026-09-01 fix round) is the UNION of
    `registered_repo_agent_names()` (a product-domain roster sanctioned to
    live in its own repo) and `CLIENT_BUILTIN_CATCHALL_TYPES` (a client
    dispatch mode with no home to pin at all) — a name in `exempt` is
    factually governed elsewhere or unpinnable in principle, so the
    "has no ... file and no agent_pins entry" claim would be wrong for it.
    Pure function; never raises."""
    known = set(known_files)
    exempt_set = set(exempt)
    out: list[str] = []
    for name in sorted(set(live_types)):
        if name in known or name in pins or name in exempt_set:
            continue
        out.append(
            f"unpinned-live-agent-type: '{name}' appears in spend.jsonl (last "
            f"{LEDGER_WINDOW_DAYS} days) but has no agents/{name}.md file and no "
            "agent_pins entry"
        )
    return out


def unsanctioned_fable_dispatches(
    rows: Iterable[Mapping[str, object]],
    now: datetime,
    days: int,
    pins: Mapping[str, str],
) -> list[str]:
    """`unsanctioned-fable-dispatch` violations (AA-0063; Item 10, 2026-09-01
    fix round): a spend row whose `model` NORMALIZES to the fable family
    ($10/$50/MTok, 2x Opus 5) while its `agent_type`'s policy pin is not
    itself `"fable"`. Matched via `str.startswith(_FABLE_MODEL_PREFIX)`, NOT
    an exact-literal comparison against `"claude-fable-5"` — on the OPUS
    PRECEDENT (comment corrected 2026-09-01 fix round 4, Doc Nit 3; an
    earlier version of this docstring falsely claimed the live ledger
    already carries context-window-suffixed FABLE variants — verified
    false, all 14 live rows are the bare literal): this SAME ledger's
    `model` field already carries suffixed variants for the model family
    that DOES have them today (`"claude-opus-5[1m]"`, `"claude-opus-4-8[1m]"`
    — hundreds of live rows), so an exact-literal fable match would
    silently miss a same-shaped fable variant the moment one is ever
    dispatched, for the identical reason it already would for opus.
    `cycle_budget.normalize_model` was considered and rejected:
    it has no fable family registered at all (only opus/sonnet/haiku), so it
    normalizes every fable variant to "unknown" — no more useful here than
    the literal comparison it would replace. Grouped by agent_type (one line
    per type, with a count and the distinct model variant(s) actually seen)
    rather than one line per row, so a real population (AA-0063 measured 14
    general-purpose rows) reads as one finding, not fourteen — matching this
    module's existing per-name reporting convention for every other
    violation class. Pure function; never raises."""
    counts: dict[str, int] = {}
    variants: dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _row_within_window(row, now, days):
            continue
        model_val = row.get("model")
        if not (
            isinstance(model_val, str) and model_val.startswith(_FABLE_MODEL_PREFIX)
        ):
            continue
        agent_type = row.get("agent_type")
        name = agent_type if isinstance(agent_type, str) and agent_type else "(unknown)"
        if pins.get(name) == "fable":
            continue
        counts[name] = counts.get(name, 0) + 1
        variants.setdefault(name, set()).add(model_val)
    out: list[str] = []
    for name in sorted(counts):
        models = ", ".join(sorted(variants[name]))
        out.append(
            f"unsanctioned-fable-dispatch: '{name}' ran on {models} in "
            f"{counts[name]} spend row(s) in the last {days} days (pin is "
            f"{pins.get(name)!r}, not 'fable')"
        )
    return out


def _load_grants(exceptions_dir: str) -> set[tuple[str, str]]:
    """`(agent_type, model)` pairs — using the SHORT tier-name spelling
    record_model_exception.py's own `--model` argument carries (the same
    string ``model_pin_gate.decide()``'s decision 6 matches a token against,
    e.g. ``"sonnet"``, never a resolved literal like ``"claude-sonnet-5"``)
    — with at least one historical exception grant on record, from
    ``grants.jsonl`` (item 2's durable audit log; the ephemeral per-token
    files are consumed/deleted and never read here). Never raises; a
    missing/unreadable file or a malformed line degrades to an empty/partial
    set, matching every other ledger reader in this module."""
    path = os.path.join(exceptions_dir, "grants.jsonl")
    granted: set[tuple[str, str]] = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                agent_type = obj.get("agent_type")
                model = obj.get("model")
                if (
                    isinstance(agent_type, str)
                    and agent_type
                    and isinstance(model, str)
                    and model
                ):
                    granted.add((agent_type, model))
    except Exception:
        return set()
    return granted


def _normalize_model_family(model: object) -> str:
    """A real spend-ledger ``model`` string (e.g. ``"claude-sonnet-5"``,
    ``"claude-opus-5[1m]"``, ``"claude-fable-5"``) -> the short tier name
    used by ``agent_pins``/``model_pin_gate.TIER_ORDER`` (``"sonnet"`` /
    ``"opus"`` / ``"haiku"`` / ``"fable"``), or ``"unknown"``.

    Reuses ``cycle_budget.normalize_model`` for the opus/sonnet/haiku
    families — the SAME mapping this runtime's own cost tooling already
    trusts — and adds the fable family locally via ``_FABLE_MODEL_PREFIX``:
    ``cycle_budget.py`` has no fable pricing-family entry at all (see
    ``unsanctioned_fable_dispatches``'s own docstring for why), and widening
    that unrelated, cost-focused module for this report-only check is out of
    scope here. Never raises."""
    if isinstance(model, str) and model.startswith(_FABLE_MODEL_PREFIX):
        return "fable"
    try:
        import cycle_budget as cb
    except Exception:
        return "unknown"
    try:
        return cb.normalize_model(model)
    except Exception:
        return "unknown"


def pin_tier_mismatches(
    rows: Iterable[Mapping[str, object]],
    now: datetime,
    days: int,
    pins: Mapping[str, str],
    file_pins: Mapping[str, str | None],
    granted_pairs: set[tuple[str, str]],
    since: str | None = None,
) -> list[str]:
    """``pin-tier-mismatch`` violations (item 6 of the model-pin-enforcement
    build): a spend row whose real ``model`` NORMALIZES to a tier family
    that differs from its ``agent_type``'s RESOLVED pin, in EITHER direction
    (below-pin, e.g. a cheaper confirmatory pass, or above-pin, e.g. an
    escalation) — cross-referenced against ``grants.jsonl`` so a row a real,
    independently-verified exception actually covers is SUPPRESSED from the
    report entirely (this is an audit trail, not a second gate; the live
    gate is ``model_pin_gate.py``, built the same day as this extension).

    "Resolved pin" uses ``model_pin_gate.resolved_pin`` verbatim (imported
    here, never re-derived) so this report can never disagree with what the
    live gate actually enforces — the two would silently drift apart the
    moment a second, independent pin-resolution implementation existed.

    A row whose ``model`` does not normalize to any known tier family
    (``"unknown"``) is skipped — guessing a family for an unrecognized model
    string is exactly the kind of guess this runtime's own cost tooling
    (``cycle_budget.py``) already refuses to make, and this check inherits
    that same discipline rather than risking a false positive.

    Grouped by ``(agent_type, resolved_family, pin)`` — one line per
    distinct combination, naming every distinct raw model string seen and a
    total row count — matching ``unsanctioned_fable_dispatches``'s own
    reporting convention.

    ``since`` (WS2.1 step 5, ``MODEL_OBSERVED_SINCE``): when given, every
    matching row is additionally split on ``_row_is_post_land(row, since)``
    into its OWN independent grouping — a row dated on/after ``since`` is
    reported as ``pin-tier-mismatch:`` (a real, actionable violation, and
    what the exit criterion counts); a row dated before it is reported
    SEPARATELY as ``pin-tier-mismatch-lookback:`` (never silently dropped —
    a lookback artifact predates the WS2.1 step 4 model-observability fix
    and is not evidence of anything still wrong, but it is still real
    ledger history worth surfacing). The default ``None`` preserves the
    pre-WS2.1-step-5 behavior exactly: every matching row reported as
    ``pin-tier-mismatch:`` with no lookback split at all, so every existing
    caller/test of this function is unaffected by this parameter's
    addition. Pure function; never raises."""
    import model_pin_gate as mpg

    def _bucket(
        predicate,
    ) -> tuple[dict[tuple[str, str, str], int], dict[tuple[str, str, str], set[str]]]:
        counts: dict[tuple[str, str, str], int] = {}
        raw_models: dict[tuple[str, str, str], set[str]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not _row_within_window(row, now, days):
                continue
            if not predicate(row):
                continue
            agent_type = row.get("agent_type")
            raw_model = row.get("model")
            if not (
                isinstance(agent_type, str)
                and agent_type
                and isinstance(raw_model, str)
                and raw_model
            ):
                continue
            pin = mpg.resolved_pin(agent_type, dict(pins), dict(file_pins))
            if not pin:
                continue
            family = _normalize_model_family(raw_model)
            if family == "unknown" or family == pin:
                continue
            if (agent_type, family) in granted_pairs:
                continue
            key = (agent_type, family, pin)
            counts[key] = counts.get(key, 0) + 1
            raw_models.setdefault(key, set()).add(raw_model)
        return counts, raw_models

    def _render(
        counts: dict[tuple[str, str, str], int],
        raw_models: dict[tuple[str, str, str], set[str]],
        label: str,
    ) -> list[str]:
        lines: list[str] = []
        for key in sorted(counts):
            agent_type, family, pin = key
            family_rank = mpg.TIER_ORDER.get(family, -1)
            pin_rank = mpg.TIER_ORDER.get(pin, -1)
            direction = "above" if family_rank > pin_rank else "below"
            models_seen = ", ".join(sorted(raw_models[key]))
            lines.append(
                f"{label}: '{agent_type}' ran on {models_seen} ({direction} its "
                f"'{pin}' pin, resolved family '{family}') in {counts[key]} spend row(s) in "
                f"the last {days} days with no exception grant on record"
            )
        return lines

    if since is None:
        counts, raw_models = _bucket(lambda _row: True)
        return _render(counts, raw_models, "pin-tier-mismatch")

    post_counts, post_models = _bucket(lambda row: _row_is_post_land(row, since))
    lookback_counts, lookback_models = _bucket(lambda row: not _row_is_post_land(row, since))
    return _render(post_counts, post_models, "pin-tier-mismatch") + _render(
        lookback_counts, lookback_models, "pin-tier-mismatch-lookback"
    )


def check(
    agents_dir: str,
    policy_path: str,
    sanctioned_opus: set[str] | None = None,
    contract_path: str | None = None,
    spend_path: str | None = None,
    now: datetime | None = None,
    repo_registry_path: str | None = None,
    exceptions_dir: str | None = None,
    sanctioned_fable: set[str] | None = None,
) -> list[str]:
    """Reads five locations, each independently and only as needed.

    ``agents_dir`` and ``policy_path`` are always read. ``contract_path``,
    ``spend_path``, and ``repo_registry_path`` are each read ONLY when the
    caller passes a non-None value; with the default ``None`` the
    corresponding check below is skipped entirely — this is what keeps every
    hermetic (tmp_path-fixture) caller free of a dependency on the live
    ``$HOME/CLAUDE.md``, the live spend ledger, or the live repo registry.
    ``main()`` always supplies all three (default ``DEFAULT_CONTRACT_PATH``/
    ``DEFAULT_SPEND_PATH``/``DEFAULT_REPO_REGISTRY_PATH``), so the CLI/live-
    report path runs every check unchanged; the live contract path is
    separately covered by ``test_live_contract_roster_is_drift_clean``,
    which calls ``contract_roster_drift`` directly against the real files.
    ``repo_registry_path`` (Item 9, 2026-09-01 fix round) is consulted ONLY
    as part of the spend-ledger cross-reference (it has no effect unless
    ``spend_path`` is ALSO supplied) — a bare ``repo_registry_path`` with no
    ``spend_path`` is inert, matching every other check's own "only as
    needed" contract.

    Violation classes:
      * ``policy-unreadable``   — model_policy.json missing/unparseable (one
        violation; without the policy nothing else is checkable).
      * ``missing-pin``         — an agent file with no frontmatter model pin.
      * ``pin-mismatch``        — pin differs from agent_pins[name].
      * ``unlisted-agent``      — an on-disk agent absent from agent_pins (the
        policy must be the complete roster; additions update BOTH together).
      * ``phantom-policy-entry``— an agent_pins name with no on-disk file AND
        no entry in ``CATCHALL_TYPES_WITHOUT_FILES`` (stale policy; a
        catch-all pin like ``general-purpose`` never has a file to begin
        with and is exempted, see that constant's own docs).
      * ``sanction-drift``      — the policy's opus pins and
        ``sync_agent_rules.OPUS_AGENTS`` disagree on who is sanctioned Opus.
      * ``fable-sanction-drift`` — (added 2026-09-19, operator directive:
        "all planners on fable" permanently pinned fable for planner seats —
        `marketing-director` and, from 2026-09-20 (card [87]), `plan-reviewer`
        too. RETIRED 2026-09-24 by operator directive repinning both seats to
        opus; ``sync_agent_rules.FABLE_AGENTS`` is now empty, and this check
        stays wired for any FUTURE standing fable pin) flags when the
        policy's fable pins and ``sync_agent_rules.FABLE_AGENTS`` disagree on
        who is sanctioned for the standing fable tier — the identical
        two-machine-readable-copies discipline as ``sanction-drift`` above,
        narrowed to the fable subset. A fable pin on any seat NOT in
        ``FABLE_AGENTS`` is flagged here, never silently accepted as a
        second, parallel sanctioning mechanism.
      * ``contract-roster-drift`` — (only checked when ``contract_path`` is
        given) a sanctioned-Opus EXTENSION agent (OPUS_AGENTS minus the two
        §10 review-boundary agents) is missing from CLAUDE.md's §13 table.
      * ``unpinned-live-agent-type`` — (only checked when ``spend_path`` is
        given, AA-0063) a real ``agent_type`` dispatched in the spend ledger
        (last ``LEDGER_WINDOW_DAYS`` days) with neither an on-disk file nor
        an ``agent_pins`` entry.
      * ``unsanctioned-fable-dispatch`` — (only checked when ``spend_path``
        is given, AA-0063) a spend row that ran on ``claude-fable-5`` whose
        ``agent_type`` is not pinned ``"fable"`` — now that the two seats
        once permanently pinned that way (`marketing-director`,
        `plan-reviewer`, 2026-09-19/20) are RETIRED to opus (2026-09-24
        operator directive), no agent_type is legitimately pinned fable, so
        this effectively flags EVERY fable dispatch in the window.
      * ``pin-tier-mismatch`` — (only checked when BOTH ``spend_path`` AND
        ``exceptions_dir`` are given; item 6 of the model-pin-enforcement
        build) a real spend row whose ``model`` normalizes to a tier family
        different from its ``agent_type``'s RESOLVED pin (frontmatter,
        falling back to policy — the SAME resolution ``model_pin_gate.py``'s
        live gate uses), in EITHER direction, with no historical exception
        grant on record (``<exceptions_dir>/grants.jsonl``) covering that
        exact ``(agent_type, pin-family)`` pair. Report-only, exactly like
        every other check here — the gate itself is ``model_pin_gate.py``;
        this only audits its real-world spend footprint after the fact.
        ``exceptions_dir`` follows the identical "only as needed" hermeticity
        contract as ``contract_path``/``spend_path``/``repo_registry_path``:
        with the default ``None`` this check is skipped entirely, even when
        ``spend_path`` is supplied — ``main()`` always supplies
        ``DEFAULT_EXCEPTIONS_DIR``.

    ``sanctioned_fable`` mirrors ``sanctioned_opus``'s own test-injection
    contract exactly (same reasoning: hermetic tests must never depend on the
    live ``sync_agent_rules.FABLE_AGENTS`` value) — ``None`` (the default)
    resolves it from the real import; an explicit ``set()`` or populated set
    overrides it for a test fixture. ``main()`` never overrides it, so the
    live report always compares against the real constant.
    Returns human-readable violation lines. Never raises.
    """
    out: list[str] = []
    try:
        with open(policy_path, encoding="utf-8") as fh:
            pins = json.load(fh).get("agent_pins", {})
        if not isinstance(pins, dict) or not pins:
            return [f"policy-unreadable: no agent_pins mapping in {policy_path}"]
    except Exception as exc:
        return [f"policy-unreadable: {policy_path}: {exc.__class__.__name__}"]

    try:
        files = sorted(
            f
            for f in os.listdir(agents_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
    except Exception as exc:
        return [f"policy-unreadable: agents dir {agents_dir}: {exc.__class__.__name__}"]

    seen: set[str] = set()
    # Dispatch identity -> frontmatter model pin (None when the file carries
    # none), captured alongside `seen` so pin_tier_mismatches can resolve a
    # pin the SAME way model_pin_gate.resolved_pin does (frontmatter first,
    # falling back to the policy) without a second directory scan.
    file_pins: dict[str, str | None] = {}
    for fname in files:
        stem = fname[: -len(".md")]
        try:
            with open(os.path.join(agents_dir, fname), encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            seen.add(stem)
            out.append(f"missing-pin: {fname} (unreadable)")
            continue
        # Dispatch identity is the frontmatter name; stem is fallback only.
        name = frontmatter_name(text) or stem
        seen.add(name)
        if frontmatter_name(text) and frontmatter_name(text) != stem:
            out.append(
                f"name-mismatch: {fname} declares name '{name}' — filename and "
                "dispatch identity have diverged"
            )
        pin = frontmatter_model(text)
        file_pins[name] = pin
        if not pin:
            out.append(f"missing-pin: {fname} has no frontmatter model pin")
        elif name not in pins:
            out.append(f"unlisted-agent: {fname} (pin '{pin}') is not in agent_pins")
        elif pins[name] != pin:
            out.append(
                f"pin-mismatch: {fname} pins '{pin}' but policy says '{pins[name]}'"
            )
    for name in sorted(pins):
        if name not in seen and name not in CATCHALL_TYPES_WITHOUT_FILES:
            out.append(
                f"phantom-policy-entry: agent_pins['{name}'] has no on-disk agent file"
            )

    # sanction-drift + contract-roster-drift (below) both need
    # sync_agent_rules's OPUS_AGENTS/CONTRACT_REVIEW_AGENTS constants; the
    # import is done once here and shared (previously imported separately in
    # each block).
    try:
        import sync_agent_rules as sar
    except Exception:
        sar = None

    # sanction-drift (reviewed finding R3-6): the Opus sanction lives in THREE
    # places — the policy's opus pins, sync_agent_rules.OPUS_AGENTS, and the
    # contract's §10/§13 prose. This report-only check holds the two
    # machine-readable copies together; widening either alone is a violation.
    if sanctioned_opus is None:
        if sar is None:
            out.append("sanction-drift: sync_agent_rules unimportable — cannot compare")
        else:
            try:
                sanctioned_opus = set(sar.OPUS_AGENTS)
            except AttributeError:
                # A renamed constant is drift, not an import failure — name it.
                out.append(
                    "sanction-drift: sync_agent_rules constants missing — cannot compare"
                )
    if sanctioned_opus is not None:
        # FABLE_AGENTS is a NARROWING subset of OPUS_AGENTS (fable is
        # opus-tier-and-above, never a departure from the opus sanction —
        # see sync_agent_rules.FABLE_AGENTS' own docstring), so a name
        # pinned "fable" still counts as opus-sanctioned here. The dedicated
        # fable-sanction-drift check below is what actually verifies the
        # fable pin itself is sanctioned; this check must not ALSO flag it
        # as a departure from OPUS_AGENTS just because "fable" != "opus".
        policy_opus = {n for n, m in pins.items() if m in ("opus", "fable")}
        for name in sorted(policy_opus - sanctioned_opus):
            out.append(
                f"sanction-drift: agent_pins['{name}']='{pins.get(name)}' but "
                "sync_agent_rules.OPUS_AGENTS does not sanction it"
            )
        for name in sorted(sanctioned_opus - policy_opus):
            out.append(
                f"sanction-drift: sync_agent_rules.OPUS_AGENTS sanctions '{name}' "
                "but the policy does not pin it opus"
            )

    # fable-sanction-drift (added 2026-09-19, operator directive: permanent
    # fable pin for the two planner seats, RETIRED 2026-09-24 by operator
    # directive repinning both to opus — sync_agent_rules.FABLE_AGENTS is
    # now empty): the identical two-machine-
    # readable-copies discipline as sanction-drift above, narrowed to the
    # fable subset — ``agent_pins`` fable entries vs.
    # ``sync_agent_rules.FABLE_AGENTS``. Never special-cased around: a fable
    # pin on a seat NOT in FABLE_AGENTS is exactly the kind of silent
    # widening this check exists to catch, the same way sanction-drift
    # catches an ungoverned opus pin. Stays wired, empty-clean today, for
    # any FUTURE standing fable pin.
    if sanctioned_fable is None:
        if sar is None:
            out.append(
                "fable-sanction-drift: sync_agent_rules unimportable — cannot compare"
            )
        else:
            try:
                sanctioned_fable = set(sar.FABLE_AGENTS)
            except AttributeError:
                out.append(
                    "fable-sanction-drift: sync_agent_rules constants missing — "
                    "cannot compare"
                )
    if sanctioned_fable is not None:
        policy_fable = {n for n, m in pins.items() if m == "fable"}
        for name in sorted(policy_fable - sanctioned_fable):
            out.append(
                f"fable-sanction-drift: agent_pins['{name}']='fable' but "
                "sync_agent_rules.FABLE_AGENTS does not sanction it"
            )
        for name in sorted(sanctioned_fable - policy_fable):
            out.append(
                f"fable-sanction-drift: sync_agent_rules.FABLE_AGENTS sanctions "
                f"'{name}' but the policy does not pin it fable"
            )

    # contract-roster-drift: every sanctioned-Opus EXTENSION agent (OPUS_AGENTS
    # minus the two §10 review-boundary agents) must appear in CLAUDE.md's §13
    # table. Always computed from the REAL sync_agent_rules constants — this is
    # a fixed rule about the actual roster, never test-injectable the way
    # sanctioned_opus is for sanction-drift above. Only runs when a
    # contract_path is explicitly supplied (default None) — this is what keeps
    # every tmp_path fixture test hermetic, since it no longer reads the live
    # $HOME/CLAUDE.md by default. main() always supplies
    # DEFAULT_CONTRACT_PATH, and the live path is covered separately by
    # test_live_contract_roster_is_drift_clean.
    if contract_path is not None:
        if sar is None:
            out.append(
                "contract-roster-drift: sync_agent_rules unimportable — cannot compare"
            )
        else:
            # The attribute lookups sit OUTSIDE the file-read try: a renamed
            # constant is an AttributeError — exactly the drift this module
            # exists to detect — and must never be mislabeled "unreadable".
            try:
                opus_agents = set(sar.OPUS_AGENTS)
                review_agents = set(sar.CONTRACT_REVIEW_AGENTS)
            except AttributeError:
                out.append(
                    "contract-roster-drift: sync_agent_rules constants missing — "
                    "cannot compare"
                )
            else:
                try:
                    with open(contract_path, encoding="utf-8") as fh:
                        contract_text = fh.read()
                except (OSError, UnicodeDecodeError):
                    out.append(
                        "contract-roster-drift: CLAUDE.md unreadable — cannot compare"
                    )
                else:
                    out.extend(
                        contract_roster_drift(contract_text, opus_agents, review_agents)
                    )
                    out.extend(
                        contract_section10_drift(
                            contract_text, opus_agents, review_agents
                        )
                    )

    # unpinned-live-agent-type + unsanctioned-fable-dispatch (AA-0063): cross-
    # reference the REAL spend ledger against the on-disk roster + policy
    # pins, so a catch-all agent_type running real dispatches with no
    # governance anywhere surfaces automatically rather than waiting for a
    # manual audit — same "report reality, never invent" discipline as every
    # other check in this module. Only runs when spend_path is explicitly
    # supplied (default None), mirroring contract_path's hermeticity
    # contract above.
    if spend_path is not None:
        resolved_now = now or datetime.now(timezone.utc)
        spend_rows = _load_spend_rows(spend_path)
        types = live_agent_types(spend_rows, resolved_now, LEDGER_WINDOW_DAYS)
        exempt: set[str] = set(CLIENT_BUILTIN_CATCHALL_TYPES)
        if repo_registry_path is not None:
            exempt |= registered_repo_agent_names(repo_registry_path)
        out.extend(unpinned_live_agent_types(types, seen, pins, exempt=exempt))
        out.extend(
            unsanctioned_fable_dispatches(
                spend_rows, resolved_now, LEDGER_WINDOW_DAYS, pins
            )
        )
        # pin-tier-mismatch (item 6): follows the SAME "only as needed"
        # hermeticity contract as repo_registry_path above — a bare
        # exceptions_dir with no spend_path would be inert anyway (nothing
        # to cross-reference it against), so it is only ever consulted here,
        # inside the spend_path-gated block.
        if exceptions_dir is not None:
            granted_pairs = _load_grants(exceptions_dir)
            out.extend(
                pin_tier_mismatches(
                    spend_rows,
                    resolved_now,
                    LEDGER_WINDOW_DAYS,
                    pins,
                    file_pins,
                    granted_pairs,
                    # WS2.1 step 5: split real (post-land) violations from
                    # pre-fix lookback artifacts — the exit criterion is "0
                    # violations among rows dated after the land date," and
                    # this is the one caller that needs that split (every
                    # hermetic test calling pin_tier_mismatches directly
                    # still gets the pre-split, since=None behavior).
                    since=MODEL_OBSERVED_SINCE,
                )
            )
    return out


def main(argv: list[str] | None = None) -> int:
    """Report and exit 0 — ALWAYS 0; this module never blocks anything."""
    argv = list(sys.argv if argv is None else argv)
    agents_dir = argv[1] if len(argv) > 1 else DEFAULT_AGENTS_DIR
    policy_path = argv[2] if len(argv) > 2 else DEFAULT_POLICY_PATH
    contract_path = argv[3] if len(argv) > 3 else DEFAULT_CONTRACT_PATH
    spend_path = argv[4] if len(argv) > 4 else DEFAULT_SPEND_PATH
    repo_registry_path = argv[5] if len(argv) > 5 else DEFAULT_REPO_REGISTRY_PATH
    exceptions_dir = argv[6] if len(argv) > 6 else DEFAULT_EXCEPTIONS_DIR
    violations = check(
        agents_dir,
        policy_path,
        contract_path=contract_path,
        spend_path=spend_path,
        repo_registry_path=repo_registry_path,
        exceptions_dir=exceptions_dir,
    )
    for line in violations:
        print(line)
    # Fix round N3: the headline count is the POST-LAND (actionable) count,
    # never diluted by `pin-tier-mismatch-lookback:` lines (WS2.1 step 5's
    # own historical, never-drive-to-zero category) — those are surfaced
    # separately as a `(+<m> lookback)` suffix so the total is still fully
    # recoverable from this one line, but the number a reader acts on is
    # the real one. Confirmed (2026-09-20 fix round) that no consumer in
    # hooks/, scripts/, or schedules/ parses this summary line's shape.
    lookback_count = sum(1 for line in violations if line.startswith("pin-tier-mismatch-lookback:"))
    post_land_count = len(violations) - lookback_count
    suffix = f" (+{lookback_count} lookback)" if lookback_count else ""
    print(f"model_pin_parity: {post_land_count} violation(s){suffix}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
