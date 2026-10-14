#!/usr/bin/env python3
"""delivery_report — a read-only DORA-lite delivery-speed snapshot.

WHY THIS EXISTS
----------------
2026-09-03 agentic-systems-architect audit, Part 2 #1: nothing in this
runtime measures delivery SPEED. `churn_report.py` measures review/gate
*friction*; nothing turns the ledgers that already exist into a "how fast is
work actually moving" signal. This module closes that gap the same way
`churn_report.py` closed its own: derive everything from ledgers the system
ALREADY writes, add zero new instrumentation, zero writes, zero side effects.

Four metrics, each sourced from exactly one existing ledger/command:

  1. commits/day, per registered repo — ``git log`` over each repo named in
     ``knowledge/repo_registry.json`` (the SAME registry
     `agentarch_metric_check.py`'s own ``${REPO:<slug>}`` resolution and
     `churn_report.py`'s sibling modules already trust as the source of
     truth for "which repos does this runtime track"). A repo whose root
     does not exist, or is not a real git checkout, is reported as its own
     ``repo_errors`` entry, never silently dropped from the table.
  2. review rounds per boundary — ``~/.claude/.review_state/last_reviewed``
     (the SAME file `churn_report.py` metric 1 reads), grouped by
     ``(repo_root, round-1 key)`` via the ``round=``/``prev=`` chain fields
     `record_review.py` writes (CLAUDE.md §10's warm-review-chain fields).
     Reports the mean and max rounds-per-boundary seen in the window.
  3. gate-denial trend — ``~/.claude/.enforcement/log.jsonl``, the same
     ``_GATE_HOOKS`` allowlist and ``would-block``/``deny`` decision values
     `churn_report.py` metric 2 already established as "a real denial",
     reused here (imported, never re-derived) so the two reports can never
     silently disagree on what counts as a denial. Reported as a per-day
     count so a caller can eyeball whether denials are trending up or down.
  4. dispatch volume — ``~/.claude/.agent_budget/spend.jsonl`` (recent, ~5-6
     day retention) UNIONED with ``~/.claude/.agent_budget/daily_rollup.jsonl``
     (the append-only longer history `daily_spend_rollup.py` already writes
     once a day) so the reported window is not silently truncated to
     whatever happens to still be in spend.jsonl. A day present in both is
     counted from the rollup only (it is the authoritative daily total;
     spend.jsonl for that day may already be a mid-rotation partial view).

Every top-level metric section carries ``status: "ok"|"degraded"|"absent"``
so a caller never mistakes "no ledger yet" for "zero delivery activity" --
identical convention to `churn_report.py`, deliberately, so the two reports
read the same way. This module is a PURE READER: no LLM call, no mutation of
any ledger, no network beyond the local, read-only ``git log`` subprocess
against each registered repo's own on-disk checkout.

``--days N`` (default 14) windows metrics 2, 3, and 4. Metric 1 (commits/day)
always reports its OWN window (the ``git log --since`` the same ``--days``
value drives) since a commit-count average only makes sense over a bounded
recency window -- there is no "lifetime commits/day" reading that means
anything.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import _lib
import churn_report as cr

DEFAULT_DAYS = 14

REPO_REGISTRY_PATH = os.path.join(_lib.CLAUDE_DIR, "knowledge", "repo_registry.json")
LEDGER_LAST_REVIEWED = _lib.LAST_REVIEWED
LEDGER_ENFORCEMENT_LOG = _lib.LOG_FILE
LEDGER_SPEND = os.path.join(_lib.AGENT_BUDGET_DIR, "spend.jsonl")
LEDGER_DAILY_ROLLUP = os.path.join(_lib.AGENT_BUDGET_DIR, "daily_rollup.jsonl")

# Reused verbatim from churn_report so the two reports can never silently
# disagree on "what counts as a real gate denial" (module docstring, metric 3).
_GATE_HOOKS = cr._GATE_HOOKS
_REAL_DENIAL_DECISIONS = frozenset({"would-block", "deny"})


class ArgError(ValueError):
    """Raised by :func:`parse_args` on a bad CLI argument. Caught by main()."""


# ---------------------------------------------------------------------------
# Repo registry (same source `agentarch_metric_check.py` trusts).
# ---------------------------------------------------------------------------


def load_repo_registry(registry_path: str) -> dict[str, str]:
    """repo slug -> expanded, absolute root path, from repo_registry.json.

    Never raises; a missing/unparseable registry, or a repo entry with no
    real ``root`` string, degrades to skipping that entry rather than
    crashing the whole read -- identical contract to
    `model_pin_parity._load_repo_registry`, reimplemented here rather than
    imported since that function is private (`_`-prefixed) to its module.
    """
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


# ---------------------------------------------------------------------------
# Metric 1: commits/day per registered repo.
# ---------------------------------------------------------------------------


def _git_commit_dates(repo_root: str, days: int, now: datetime) -> list[str] | None:
    """Return one ``YYYY-MM-DD`` string per commit on HEAD in the last
    ``days`` days, or None if the root is not a readable git checkout.

    Read-only, local-only plumbing (``git log``); network is never invoked.
    Never raises.
    """
    if not os.path.isdir(repo_root):
        return None
    try:
        env = dict(os.environ)
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        since = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        proc = subprocess.run(
            ["git", "-C", repo_root, "log", f"--since={since}", "--date=short", "--pretty=%ad"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def commits_per_day(
    registry: dict[str, str],
    days: int,
    now: datetime,
    git_log_fn=None,
) -> dict:
    """Per-repo commit counts + a mean commits/day, over the last `days`.

    `git_log_fn(repo_root, days, now) -> list[str] | None` is injectable so
    tests never shell out to a real git checkout (mirrors `record_review._git`
    being wrapped rather than called directly in this module's callers).
    Defaults to `_git_commit_dates`.
    """
    if git_log_fn is None:
        git_log_fn = _git_commit_dates
    by_repo: dict[str, dict] = {}
    repo_errors: dict[str, str] = {}
    for slug, root in sorted(registry.items()):
        dates = git_log_fn(root, days, now)
        if dates is None:
            repo_errors[slug] = f"not a readable git checkout: {root}"
            continue
        commits = len(dates)
        by_repo[slug] = {
            "root": root,
            "commits": commits,
            "commits_per_day": round(commits / days, 2) if days else 0.0,
        }
    total_commits = sum(v["commits"] for v in by_repo.values())
    return {
        "window_days": days,
        "by_repo": by_repo,
        "repo_errors": repo_errors,
        "total_commits": total_commits,
        "total_commits_per_day": round(total_commits / days, 2) if days else 0.0,
    }


# ---------------------------------------------------------------------------
# Metric 2: review rounds per boundary.
# ---------------------------------------------------------------------------


def _parse_last_reviewed_line(line: str) -> dict | None:
    """Parse one `last_reviewed` line into its structural fields, or None if
    the line has no recognizable `<repo_root> <key> ...` shape. Reuses
    `record_review.parse_ledger_fields`-equivalent k=v parsing inline (that
    function needs the raw outcome-token substring, which this module derives
    differently -- see below) rather than importing record_review, keeping
    this reader's only real dependency on churn_report (for `_GATE_HOOKS`).
    """
    parts = line.split()
    if len(parts) < 2:
        return None
    repo_root, key = parts[0], parts[1]
    fields: dict[str, str] = {}
    for tok in parts[2:]:
        if "=" in tok:
            k, _, v = tok.partition("=")
            if k:
                fields[k] = v
    return {"repo_root": repo_root, "key": key, "fields": fields}


def review_rounds_per_boundary(lines: list[str], days: int, now: datetime) -> dict:
    """Group `last_reviewed` entries into boundary chains via the `round=`/
    `prev=` fields `record_review.py` writes (CLAUDE.md §10), and report the
    mean/max rounds observed per boundary within the window.

    A "boundary chain" here is identified by its ROOT: an entry with no
    `prev=` starts a new chain (round 1, or a chain whose earlier rounds
    predate the `round=`/`prev=` field mandate and are unrecoverable -- both
    read as chain length 1 from this entry alone, which is the correct,
    non-fabricating floor). An entry WITH `prev=` extends whichever chain the
    entry's own `round=` is highest for that (repo_root, key)'s traceable
    root; since a `prev=` value is itself a `key` from an earlier line, the
    chain's max observed `round=` is what is reported per root -- there is no
    need to actually walk the `prev=` pointers to compute a max, since
    `record_review.py` always increments `round=` monotonically per chain.
    """
    # Only entries within the window (by ts= when present; entries with no
    # ts= are ALWAYS included -- fails open toward inclusion, exactly like
    # churn_report.within_days, so a pre-ts=-mandate entry is never dropped).
    parsed: list[dict] = []
    for line in lines:
        row = _parse_last_reviewed_line(line)
        if row is None:
            continue
        ts = row["fields"].get("ts")
        if not cr.within_days(ts, days, now):
            continue
        parsed.append(row)

    # Chain root = the entry's own key if it has no prev=, else walk prev=
    # pointers (bounded, since chains are short and monotonic) to the first
    # entry in THIS parsed set with no prev= for that repo_root; if the
    # chain's earlier rounds fell outside the window (or predate the field
    # mandate), the walk simply stops at the earliest entry it can see,
    # which is the correct non-fabricating floor described above.
    by_key: dict[tuple[str, str], dict] = {(r["repo_root"], r["key"]): r for r in parsed}
    chain_root: dict[tuple[str, str], tuple[str, str]] = {}

    def _root_of(repo_root: str, key: str, _seen: set | None = None) -> tuple[str, str]:
        ident = (repo_root, key)
        if ident in chain_root:
            return chain_root[ident]
        if _seen is None:
            _seen = set()
        if ident in _seen:
            return ident  # cycle guard -- never infinite-loop on bad data
        _seen.add(ident)
        row = by_key.get(ident)
        prev = row["fields"].get("prev") if row else None
        if not prev:
            chain_root[ident] = ident
            return ident
        root = _root_of(repo_root, prev, _seen)
        chain_root[ident] = root
        return root

    max_round_per_root: dict[tuple[str, str], int] = {}
    for repo_root, key in by_key:
        root = _root_of(repo_root, key)
        row = by_key[(repo_root, key)]
        try:
            round_n = int(row["fields"].get("round", "1"))
        except Exception:
            round_n = 1
        max_round_per_root[root] = max(max_round_per_root.get(root, 1), round_n)

    counts = list(max_round_per_root.values())
    return {
        "window_days": days,
        "boundaries": len(counts),
        "mean_rounds": round(sum(counts) / len(counts), 2) if counts else None,
        "max_rounds": max(counts) if counts else None,
    }


# ---------------------------------------------------------------------------
# Metric 3: gate-denial trend, per day.
# ---------------------------------------------------------------------------


def gate_denials_by_day(rows: list[dict], days: int, now: datetime) -> dict:
    """Per-day count of real gate denials (`_GATE_HOOKS`-allowlisted,
    `would-block`/`deny` decisions ONLY -- identical filter to
    `churn_report.denials_by_day_reason`, reused by import for the allowlist
    itself so the two reports can never silently disagree)."""
    by_day: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("decision") not in _REAL_DENIAL_DECISIONS:
            continue
        if row.get("hook") not in _GATE_HOOKS:
            continue
        ts = row.get("ts")
        if not cr.within_days(ts, days, now):
            continue
        day = cr._day_of(ts)
        if day is None:
            day = "unknown"
        by_day[day] = by_day.get(day, 0) + 1
    total = sum(by_day.values())
    return {
        "window_days": days,
        "by_day": dict(sorted(by_day.items())),
        "total_denials": total,
        "mean_per_day": round(total / days, 2) if days else 0.0,
    }


# ---------------------------------------------------------------------------
# Metric 4: dispatch volume, spend.jsonl unioned with daily_rollup.jsonl.
# ---------------------------------------------------------------------------


def dispatch_volume(
    spend_rows: list[dict],
    rollup_rows: list[dict],
    days: int,
    now: datetime,
) -> dict:
    """Per-day dispatch counts, preferring the rollup's authoritative daily
    total over a same-day spend.jsonl count (module docstring, metric 4)."""
    from_rollup: dict[str, int] = {}
    for row in rollup_rows:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        dispatches = row.get("dispatches")
        if not isinstance(date, str) or not isinstance(dispatches, int):
            continue
        if not cr.within_days(date + "T00:00:00Z", days, now):
            continue
        from_rollup[date] = dispatches

    from_spend: dict[str, int] = {}
    for row in spend_rows:
        if not isinstance(row, dict):
            continue
        ts = row.get("ts")
        if not cr.within_days(ts, days, now):
            continue
        day = cr._day_of(ts)
        if day is None:
            continue
        from_spend[day] = from_spend.get(day, 0) + 1

    by_day: dict[str, int] = dict(from_spend)
    by_day.update(from_rollup)  # rollup wins on overlap -- see docstring
    total = sum(by_day.values())
    return {
        "window_days": days,
        "by_day": dict(sorted(by_day.items())),
        "total_dispatches": total,
        "mean_per_day": round(total / days, 2) if days else 0.0,
        "days_from_rollup": sorted(from_rollup.keys()),
        "days_from_spend_only": sorted(set(from_spend) - set(from_rollup)),
    }


# ---------------------------------------------------------------------------
# Report assembly.
# ---------------------------------------------------------------------------


def _status_for(errors: dict) -> str:
    return "degraded" if errors.get("read_error") else "ok"


def _absent_section(path: str, extra: dict | None = None) -> dict:
    section = {"status": "absent", "ledger": path}
    if extra:
        section.update(extra)
    return section


def build_report(
    days: int,
    now: datetime | None = None,
    registry_path: str | None = None,
    last_reviewed_path: str | None = None,
    enforcement_log_path: str | None = None,
    spend_path: str | None = None,
    daily_rollup_path: str | None = None,
    git_log_fn=None,
) -> dict:
    """Build the full, JSON-serializable delivery report. Pure given its
    file inputs (all paths are parameters so tests never touch the real
    ~/.claude ledgers or a real git checkout). Every metric section carries
    `status: "ok"|"degraded"|"absent"`, mirroring `churn_report.build_report`.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if registry_path is None:
        registry_path = REPO_REGISTRY_PATH
    if last_reviewed_path is None:
        last_reviewed_path = LEDGER_LAST_REVIEWED
    if enforcement_log_path is None:
        enforcement_log_path = LEDGER_ENFORCEMENT_LOG
    if spend_path is None:
        spend_path = LEDGER_SPEND
    if daily_rollup_path is None:
        daily_rollup_path = LEDGER_DAILY_ROLLUP

    report: dict = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
    }

    # --- Metric 1: commits/day -------------------------------------------
    registry = load_repo_registry(registry_path)
    if not registry:
        report["commits_per_day"] = _absent_section(
            registry_path, {"note": "no repos registered or registry unreadable"}
        )
    else:
        commits = commits_per_day(registry, days, now, git_log_fn=git_log_fn)
        commits["status"] = "degraded" if commits["repo_errors"] else "ok"
        commits["ledger"] = registry_path
        report["commits_per_day"] = commits

    # --- Metric 2: review rounds per boundary -----------------------------
    lr_result = cr.read_lines(last_reviewed_path)
    if lr_result is None:
        report["review_rounds"] = _absent_section(last_reviewed_path)
    else:
        lr_lines, lr_errors = lr_result
        rounds = review_rounds_per_boundary(lr_lines, days, now)
        rounds["status"] = _status_for(lr_errors)
        rounds["ledger"] = last_reviewed_path
        rounds["read_error"] = lr_errors["read_error"]
        report["review_rounds"] = rounds

    # --- Metric 3: gate-denial trend ---------------------------------------
    log_result = cr.read_jsonl(enforcement_log_path)
    if log_result is None:
        report["gate_denials"] = _absent_section(enforcement_log_path)
    else:
        log_rows, log_errors = log_result
        denials = gate_denials_by_day(log_rows, days, now)
        denials["status"] = _status_for(log_errors)
        denials["ledger"] = enforcement_log_path
        denials["read_error"] = log_errors["read_error"]
        denials["skipped_unparseable"] = log_errors["skipped_unparseable"]
        report["gate_denials"] = denials

    # --- Metric 4: dispatch volume ------------------------------------------
    spend_result = cr.read_jsonl(spend_path)
    rollup_result = cr.read_jsonl(daily_rollup_path)
    if spend_result is None and rollup_result is None:
        report["dispatch_volume"] = _absent_section(f"{spend_path} + {daily_rollup_path}")
    else:
        spend_rows, spend_errors = spend_result if spend_result is not None else ([], {"read_error": None, "skipped_unparseable": 0})
        rollup_rows, rollup_errors = rollup_result if rollup_result is not None else ([], {"read_error": None, "skipped_unparseable": 0})
        volume = dispatch_volume(spend_rows, rollup_rows, days, now)
        volume["status"] = "degraded" if (spend_errors["read_error"] or rollup_errors["read_error"]) else "ok"
        volume["spend_ledger"] = spend_path
        volume["rollup_ledger"] = daily_rollup_path
        report["dispatch_volume"] = volume

    return report


# ---------------------------------------------------------------------------
# Text rendering.
# ---------------------------------------------------------------------------


def render_table(report: dict) -> str:
    lines: list[str] = []
    lines.append(f"delivery_report  generated_at={report['generated_at']}  days={report['days']}")
    lines.append("")

    cpd = report.get("commits_per_day", {})
    lines.append(f"-- commits/day [{cpd.get('status', 'absent')}] --")
    if cpd.get("status") == "absent":
        lines.append(f"  ABSENT ({cpd.get('ledger')}) {cpd.get('note', '')}".rstrip())
    else:
        for slug, info in sorted(cpd.get("by_repo", {}).items()):
            lines.append(f"  {slug:<24} {info['commits']:>5} commits  ({info['commits_per_day']}/day)")
        for slug, err in sorted(cpd.get("repo_errors", {}).items()):
            lines.append(f"  {slug:<24} ERROR: {err}")
        lines.append(f"  {'TOTAL':<24} {cpd.get('total_commits', 0):>5} commits  ({cpd.get('total_commits_per_day', 0)}/day)")
    lines.append("")

    rr = report.get("review_rounds", {})
    lines.append(f"-- review rounds/boundary [{rr.get('status', 'absent')}] --")
    if rr.get("status") == "absent":
        lines.append(f"  ABSENT ({rr.get('ledger')})")
    else:
        lines.append(f"  boundaries={rr.get('boundaries')}  mean_rounds={rr.get('mean_rounds')}  max_rounds={rr.get('max_rounds')}")
    lines.append("")

    gd = report.get("gate_denials", {})
    lines.append(f"-- gate denials/day [{gd.get('status', 'absent')}] --")
    if gd.get("status") == "absent":
        lines.append(f"  ABSENT ({gd.get('ledger')})")
    else:
        for day, count in gd.get("by_day", {}).items():
            lines.append(f"  {day}  {count}")
        lines.append(f"  total={gd.get('total_denials')}  mean/day={gd.get('mean_per_day')}")
    lines.append("")

    dv = report.get("dispatch_volume", {})
    lines.append(f"-- dispatch volume/day [{dv.get('status', 'absent')}] --")
    if dv.get("status") == "absent":
        lines.append(f"  ABSENT ({dv.get('ledger')})")
    else:
        for day, count in dv.get("by_day", {}).items():
            lines.append(f"  {day}  {count}")
        lines.append(f"  total={dv.get('total_dispatches')}  mean/day={dv.get('mean_per_day')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

_HELP_TEXT = """Usage: python3 ~/.claude/hooks/delivery_report.py [--days N] [--json] [--help]

  --days N   Recency window (days) applied to all four metrics
             (default: 14).
  --json     Emit the full report as JSON instead of a text table.
  --help     Show this message and exit.

Read-only. Never writes any ledger. See the module docstring for exactly
which four existing ledgers/commands each metric is derived from.
"""


def _parse_days_value(raw: str) -> int:
    try:
        value = int(raw)
    except Exception as exc:
        raise ArgError(f"--days needs an integer, got {raw!r}") from exc
    if value <= 0:
        raise ArgError(f"--days must be a positive integer, got {value}")
    return value


def parse_args(argv: list[str]) -> tuple[int, bool]:
    days = DEFAULT_DAYS
    as_json = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--days":
            i += 1
            if i >= len(argv):
                raise ArgError("--days needs a value")
            days = _parse_days_value(argv[i])
        elif arg.startswith("--days="):
            days = _parse_days_value(arg.split("=", 1)[1])
        elif arg == "--json":
            as_json = True
        else:
            raise ArgError(f"unknown argument {arg!r}")
        i += 1
    return days, as_json


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in raw_argv or "-h" in raw_argv:
        print(_HELP_TEXT)
        return 0
    try:
        days, as_json = parse_args(raw_argv)
    except ArgError as exc:
        print(f"delivery_report: {exc}", file=sys.stderr)
        return 2
    report = build_report(days)
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_table(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI entry
    sys.exit(main())
