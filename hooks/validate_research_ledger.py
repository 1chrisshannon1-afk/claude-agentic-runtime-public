#!/usr/bin/env python3
"""validate_research_ledger — validates knowledge/research_ledger.jsonl
(#4731, follow-up from the research-scout/market-analyst build, #4729;
build-wave 2026-08-31, Lane B).

The research findings ledger written by the research-scout/market-analyst
seat is free-text-adjacent (a JSON line per inspected OSS repo, re-checked
on every audit) and had zero mechanical validation: a malformed row, an
out-of-sequence/duplicate id, an out-of-domain verdict/target_repo, an
oversized mechanism/brief, or — the load-bearing one — a `COPY` verdict on
a row whose license can never legally support copying, could all sit in the
file indefinitely. This module is that mechanical check, modeled directly
on `validate_agentarch_ledger.py` (the in-repo precedent this follows) but
scoped to exactly what #4731 asks for: no metric_command, no guard-legality
reimplementation, no live command re-scoring — this ledger carries no
executable command at all, so none of that machinery applies here.

What it validates, per line:
  * field SET and ORDER — the exact ten canonical keys, in the exact order
    #4731 specifies: id, ts, last_checked_at, target_repo, oss_repo,
    source_url, license, verdict, mechanism, brief.
  * `id` format (``RS-<4-digit>``) AND sequence — line N must carry
    ``RS-<N zero-padded to 4>``; a duplicate id is also flagged (mirrors
    validate_agentarch_ledger's id-sequence/id-duplicate checks exactly).
  * `ts` / `last_checked_at` — ISO-8601 date (YYYY-MM-DD); neither is
    nullable in this ledger's schema (every row is a completed inspection,
    unlike agentarch's checked_at, which is legitimately null for an
    unscored row) — a missing/malformed date on either field is a
    violation.
  * `target_repo` domain — ``exampleapp|agency|trading|runtime``.
  * `verdict` domain — ``COPY|LEARN-FROM|AVOID``.
  * `oss_repo` / `source_url` / `license` — non-empty strings (a blank
    value on any of these means the row documents nothing checkable).
  * `mechanism` <= 300 chars / `brief` <= 500 chars (#4731's caps).
  * LICENSE-CEILING INVARIANT (the load-bearing check, #4731's own words):
    no row whose `license` is AGPL*, GPL*, LGPL*, SSPL*, NOASSERTION, or
    unknown/blank may carry ``verdict: COPY``. Matched case-insensitively
    and by PREFIX for the versioned families (AGPL-3.0, GPL-2.0-only,
    LGPL-2.1, SSPL-1.0, ...) — a version suffix must never be a loophole.
    RS-0024 (karpathy/autoresearch) is the proof case this invariant exists
    for: its README claims MIT but the real license is NOASSERTION, and the
    ledger correctly records verdict LEARN-FROM, never COPY, for it.
  * STALENESS — report-only, NEVER a blocking violation (#4731's own
    wording): a row whose `last_checked_at` is older than
    `STALE_MONTHS` (default 6, per target_repo — a repo-agnostic default;
    no per-repo cadence is specified anywhere this validator can read, so
    one uniform threshold is used for all four target_repo values) is
    reported on a SEPARATE channel (`check_ledger`'s second return value)
    that `main()` prints but never factors into its exit code.

Exit code: 0 when clean of BLOCKING violations (staleness reports may still
be printed), 1 when any blocking violation is found — matching
validate_agentarch_ledger's contract. Never raises out of main(): a crash
is caught and reported as one violation line, exit 1.

This module owns exactly two files:
  ~/.claude/hooks/validate_research_ledger.py  (this file)
  ~/.claude/hooks/tests/test_validate_research_ledger.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date

_HOME = os.path.expanduser("~")

DEFAULT_LEDGER_PATH = os.path.join(_HOME, ".claude", "knowledge", "research_ledger.jsonl")

CANONICAL_FIELDS = (
    "id",
    "ts",
    "last_checked_at",
    "target_repo",
    "oss_repo",
    "source_url",
    "license",
    "verdict",
    "mechanism",
    "brief",
)

TARGET_REPO_DOMAIN = {"exampleapp", "agency", "trading", "runtime"}
VERDICT_DOMAIN = {"COPY", "LEARN-FROM", "AVOID"}

_ID_RE = re.compile(r"^RS-(\d{4})$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MECHANISM_MAX_LEN = 300
BRIEF_MAX_LEN = 500

# Staleness report-only threshold (#4731: "report (never block) rows whose
# last_checked_at is older than N months, per target"). No per-target_repo
# cadence is documented anywhere this validator can read, so one uniform N
# is applied to every target_repo -- revisit with a real per-target cadence
# if one is ever specified.
STALE_MONTHS = 6

# --------------------------------------------------------------------------
# license-ceiling invariant
# --------------------------------------------------------------------------

# License FAMILIES that can never support a COPY verdict, matched by
# case-insensitive PREFIX so a version suffix (AGPL-3.0, GPL-2.0-only,
# LGPL-2.1-or-later, SSPL-1.0, ...) is never a loophole. NOASSERTION is
# SPDX's own "no license info found" sentinel (RS-0005's invoiceninja row
# is exactly this shape) -- an absent finding is not a permissive one.
_COPY_FORBIDDEN_LICENSE_PREFIXES = ("AGPL", "GPL", "LGPL", "SSPL", "NOASSERTION")


def _license_is_copy_ceiling_violation(license_value: object) -> bool:
    """True when `license_value` can never legally support a COPY verdict:
    a known copyleft/source-available family (by case-insensitive prefix),
    NOASSERTION, or "unknown"/blank/non-string (an absent or unrecognized
    license is treated as UNKNOWN, the most conservative reading -- never
    silently passed as permissive). Never raises.
    """
    if not isinstance(license_value, str) or not license_value.strip():
        return True
    normalized = license_value.strip().upper()
    if normalized == "UNKNOWN":
        return True
    return any(normalized.startswith(prefix) for prefix in _COPY_FORBIDDEN_LICENSE_PREFIXES)


# --------------------------------------------------------------------------
# per-row structural validation
# --------------------------------------------------------------------------


def validate_row(row: object, line_no: int) -> list[str]:
    """Structural + license-ceiling checks needing no IO. Pure. Never raises."""
    out: list[str] = []
    prefix = f"line {line_no}"
    if not isinstance(row, dict):
        return [f"{prefix}: not a JSON object"]

    fields = list(row.keys())
    field_set = set(fields)
    canonical_set = set(CANONICAL_FIELDS)
    if field_set != canonical_set:
        missing = sorted(canonical_set - field_set)
        extra = sorted(field_set - canonical_set)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"extra {extra}")
        out.append(f"{prefix}: field-set: " + "; ".join(detail))
    elif fields != list(CANONICAL_FIELDS):
        out.append(f"{prefix}: field-order: got {fields}, expected {list(CANONICAL_FIELDS)}")

    rid = row.get("id")
    m = _ID_RE.match(rid) if isinstance(rid, str) else None
    if m is None:
        out.append(f"{prefix}: id-format: {rid!r} does not match 'RS-<4-digit>'")
    else:
        expected = f"RS-{line_no:04d}"
        if rid != expected:
            out.append(f"{prefix}: id-sequence: id {rid!r} != expected {expected!r} for this line")

    for date_field in ("ts", "last_checked_at"):
        val = row.get(date_field)
        if not isinstance(val, str) or not _DATE_RE.match(val):
            out.append(f"{prefix}: date-format: {date_field}={val!r} is not YYYY-MM-DD")

    target_repo = row.get("target_repo")
    if target_repo not in TARGET_REPO_DOMAIN:
        out.append(
            f"{prefix}: target-repo-domain: target_repo={target_repo!r} not one of "
            f"{sorted(TARGET_REPO_DOMAIN)}"
        )

    verdict = row.get("verdict")
    if verdict not in VERDICT_DOMAIN:
        out.append(f"{prefix}: verdict-domain: verdict={verdict!r} not one of {sorted(VERDICT_DOMAIN)}")

    for str_field in ("oss_repo", "source_url", "license"):
        val = row.get(str_field)
        if not isinstance(val, str) or not val.strip():
            out.append(f"{prefix}: empty-field: {str_field}={val!r} must be a non-empty string")

    mechanism = row.get("mechanism")
    if isinstance(mechanism, str) and len(mechanism) > MECHANISM_MAX_LEN:
        out.append(
            f"{prefix}: mechanism-too-long: {len(mechanism)} chars "
            f"(max {MECHANISM_MAX_LEN})"
        )

    brief = row.get("brief")
    if isinstance(brief, str) and len(brief) > BRIEF_MAX_LEN:
        out.append(f"{prefix}: brief-too-long: {len(brief)} chars (max {BRIEF_MAX_LEN})")

    # License-ceiling invariant: checked whenever verdict is (or claims to
    # be) COPY, regardless of whether verdict/license already failed their
    # own domain/empty-field checks above -- a row can violate BOTH its own
    # domain check AND the ceiling invariant at once, and both must be
    # reported (mirrors validate_agentarch_ledger's own "report every
    # applicable violation, never short-circuit on the first" convention).
    if verdict == "COPY" and _license_is_copy_ceiling_violation(row.get("license")):
        out.append(
            f"{prefix}: license-ceiling-violation: license={row.get('license')!r} "
            "can never support verdict=COPY (AGPL*/GPL*/LGPL*/SSPL*/NOASSERTION/"
            "unknown licenses cap at LEARN-FROM or AVOID)"
        )

    return out


# --------------------------------------------------------------------------
# staleness — report-only, never a blocking violation
# --------------------------------------------------------------------------


def _months_between(last_checked_at: object, today: str) -> float | None:
    """Whole-ish months from last_checked_at to today (365.25/12-day months);
    None when either date is not a real ISO date. Pure; never raises."""
    try:
        d0 = date.fromisoformat(str(last_checked_at))
        d1 = date.fromisoformat(today)
    except (TypeError, ValueError):
        return None
    return (d1 - d0).days / (365.25 / 12)


def stale_report_line(row: dict, line_no: int, today: str) -> str | None:
    """A report-only staleness line for `row`, or None when it isn't stale
    (or its last_checked_at can't be parsed -- validate_row already reports
    a malformed date as a real, blocking violation; staleness has nothing
    further useful to say about an unparseable date). Pure; never raises.
    """
    age_months = _months_between(row.get("last_checked_at"), today)
    if age_months is None or age_months <= STALE_MONTHS:
        return None
    return (
        f"line {line_no} (id={row.get('id')!r}): stale: last_checked_at="
        f"{row.get('last_checked_at')!r} is {age_months:.1f} months old "
        f"(threshold {STALE_MONTHS}) for target_repo={row.get('target_repo')!r} "
        "-- report-only, re-check when convenient"
    )


# --------------------------------------------------------------------------
# whole-ledger orchestration
# --------------------------------------------------------------------------


def check_ledger(path: str, today: str | None = None) -> tuple[list[str], list[str]]:
    """Reads the ledger and validates every row.

    Returns (violations, staleness_reports) — TWO separate lists, never one:
    `violations` is what `main()` exits 1 on; `staleness_reports` is
    printed but NEVER affects the exit code (#4731's own "report, never
    block" requirement for this dimension — the one place this validator's
    contract genuinely differs from validate_agentarch_ledger's, where a
    never-scored row DOES land in the single blocking list). Staleness is
    only computed when `today` is supplied (mirrors
    validate_agentarch_ledger's own `today`-gated never-scored check) —
    without it staleness is skipped entirely, not defaulted to "not stale".
    """
    violations: list[str] = []
    staleness: list[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as exc:
        return ([f"ledger-unreadable: {path}: {exc.__class__.__name__}"], [])

    ids_seen: dict[str, int] = {}
    for i, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except Exception as exc:
            violations.append(f"line {i}: json-parse-error: {exc.__class__.__name__}")
            continue

        violations.extend(validate_row(row, i))

        rid = row.get("id") if isinstance(row, dict) else None
        if isinstance(rid, str):
            if rid in ids_seen:
                violations.append(f"line {i}: id-duplicate: {rid!r} already used on line {ids_seen[rid]}")
            else:
                ids_seen[rid] = i

        if isinstance(row, dict) and today:
            report = stale_report_line(row, i, today)
            if report:
                staleness.append(report)

    return violations, staleness


def main(argv: list[str] | None = None) -> int:
    """Prints every violation, then every staleness report, then a summary
    line; exit 1 iff any BLOCKING violation (staleness never affects exit).
    """
    argv = list(sys.argv if argv is None else argv)
    path = argv[1] if len(argv) > 1 else DEFAULT_LEDGER_PATH
    try:
        violations, staleness = check_ledger(path, today=date.today().isoformat())
    except Exception as exc:
        violations, staleness = [f"validator-crashed: {exc.__class__.__name__}: {exc}"], []
    for line in violations:
        print(line)
    for line in staleness:
        print(line)
    print(
        f"validate_research_ledger: {len(violations)} violation(s), "
        f"{len(staleness)} staleness report(s)"
    )
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
