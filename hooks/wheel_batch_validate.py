#!/usr/bin/env python3
"""wheel_batch_validate — pre-validates a P1 triage batch file before it
ever reaches `aggregate.py` (THE ISSUE WHEEL, commit 1 of the rollout;
`~/.claude/plans/issue_wheel_consolidation.md` §4 P2).

A P1 triage pass emits one record per issue, shaped as a
``{verdict, ...}`` dict headed for `aggregate.py`'s own
``_load_batch_file``/``parse_batch_record``. That loader is a BARE list
comprehension with no per-record try/except (see
``repo_tooling/scripts/backlog_groom/aggregate.py:_load_batch_file`` in any
product repo) — one record failing ``parse_batch_record``'s validation (a
missing ``cited_fix_sha``, a missing ``duplicate_of``, an uncheckable
``superseded_by``) raises and ABORTS THE WHOLE BATCH FILE, not just that one
record. On the common case — an ``already_done`` verdict with no hex sha
attached — that failure mode silently zeroes out an entire night's triage
batch while the job still reports a clean run. This module exists to close
that failure mode: it runs BEFORE `aggregate.py`, translating each raw
triage verdict into either (a) the ``groom Verdict`` string `aggregate.py`'s
``normalize_verdict`` actually accepts, or (b) a rewritten
``needs_more_info`` record that carries the SAME ``number``/``batch_id``/
every other original field, so the record survives into `aggregate.py`'s own
(separately re-verified) downgrade path instead of aborting the parse of
every other record in the file.

**P1's verdict strings are NOT `aggregate.py`-legal as-is** — this is the
core reason this module exists, not an incidental detail. Executed live
against `aggregate.py`'s real ``_CANONICAL_ALIASES`` (28 keys): neither
``already_done`` nor ``not_doing``'s P1 spelling has any alias entry as
such — ``already_done`` has NO alias at all (only ``already_fixed`` maps to
``Verdict.FIXED``) and would raise ``ValueError`` from
``normalize_verdict`` if handed through unchanged. So a valid P1 record must
have its ``verdict`` string TRANSLATED to `aggregate.py`'s own vocabulary,
per the table below (plan §4 P2) — this validator is the seam where that
translation happens, not a pass-through:

  ================  ============  =============================  ==========
  P1 verdict        groom verdict required fields                 on failure
  ================  ============  =============================  ==========
  already_done      fixed         cited_fix_sha (hex,              rewrite to
                                   ``^[0-9a-f]{7,40}$``),           needs_more_info
                                   non-empty rationale, batch_id
  duplicate         duplicate     duplicate_of, rationale,         rewrite to
                                   batch_id                        needs_more_info
  not_doing         superseded    superseded_by (a mechanically-   rewrite to
                                   checkable citation: an issue     needs_more_info
                                   ref like "#1234" or a doc
                                   path), rationale, batch_id
  unclear           needs_more_info  rationale, batch_id           (already valid)
  anything else     —             —                                rewrite to
  (needs_work,                                                     needs_more_info
   operator_only,                                                  (defensive —
   unrecognized)                                                   these are never
                                                                    written to a
                                                                    batch file by
                                                                    P1 in the
                                                                    first place)
  ================  ============  =============================  ==========

CRITICAL — every rewrite is FIELD-PRESERVING: a failing record has its
``verdict``/``rationale`` keys mutated IN PLACE on the SAME dict. ``number``,
``batch_id``, and any other original field survive completely unchanged.
This is not a style choice — a fresh, narrower dict that dropped ``number``
would make `aggregate.py`'s ``_load_batch_file`` raise ``ValueError``
immediately on that record (it reads ``raw["number"]`` first), reproducing
the exact whole-file-abort failure mode this validator exists to prevent.
The SAME in-place-mutation discipline applies to a SUCCESSFUL record's
verdict translation (``already_done`` -> ``fixed``, ``not_doing`` ->
``superseded``, ``unclear`` -> ``needs_more_info``): only ``verdict`` is
rewritten, every other field is left exactly as P1 wrote it.

**NARROW, NAMED AMENDMENT to field-preservation (closing a code-reviewer
round-2 finding), never a reversal of it:** EVERY record -- not only ones
this validator rejects -- has any of ``duplicate_of``/
``suggested_add_labels``/``suggested_remove_labels`` DROPPED if, and only
if, that field's own VALUE would make `aggregate.py`'s own UNCONDITIONAL
coercion of it raise (``int(duplicate_of)`` and ``tuple(raw.get(...) or
())`` both run regardless of verdict, per `parse_batch_record` -- so a
malformed value on those fields would abort the batch even on a record this
validator otherwise accepts unchanged, e.g. a genuinely valid ``unclear``
record carrying a garbage ``duplicate_of`` nobody asked for). This runs
UPFRONT in `validate_record`, before any verdict branching -- see
``_sanitize_unconditionally_coerced_fields``. Dropping the key loses
nothing real; the fields this contract actually promises to preserve —
``number``/``batch_id``/``rationale``/every OTHER field — are untouched,
and a field whose value WOULD coerce cleanly is never touched.

CLI
---
    python3 ~/.claude/hooks/wheel_batch_validate.py --in batch.json --out validated.json

``--in`` is a JSON array of raw record dicts; ``--out`` receives the
validated array. Every record that is at least SHAPED like a record (a
dict, however malformed otherwise) produces exactly one output record —
rewritten to ``needs_more_info`` if it fails validation, never silently
dropped. The one exception: a genuinely non-dict entry has no ``number`` to
preserve at all, so it is DROPPED rather than kept as a numberless shell
that would abort ``aggregate.py``'s parse of the whole batch just as badly
— ``main``'s own stdout reports the drop count explicitly, so this is never
a silent loss.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# EXACT copies of aggregate.py's own `_BARE_ISSUE_REF_RE`/
# `_EMBEDDED_ISSUE_REF_RE`/`_SHA_RE`/`_PATH_CITATION_RE` -- kept as
# independent copies here (not imported from `aggregate.py`) because this is
# a RUNTIME-level hook with no dependency on any product repo's package
# layout (see the module docstring's own "zero hardcoded product paths"
# framing and CLAUDE.md's boundary test: a rule/shape true in any repo
# belongs in the runtime, never imported cross-repo). code-reviewer round 1
# found the original "close enough" regex here diverged from aggregate.py's
# real contract in BOTH directions: `_ISSUE_REF_RE = r"#?(\d+)"` used with
# `.search()` treated ANY bare digit anywhere in free prose as a checkable
# issue ref (too permissive -- demonstrated to let a genuinely uncheckable
# citation like "superseded by the v3 rewrite in 2026" pass this validator
# only to abort `aggregate.py`'s `_load_batch_file` for the WHOLE batch, the
# exact failure mode this module exists to prevent), while having no sha
# branch at all made it reject a legitimate sha citation with no decimal
# digit in it (too strict -- silently destroyed a valid verdict). These are
# now copied VERBATIM (same patterns, same priority order via
# `_citation_component` below) rather than approximated, so "mirrors
# aggregate.py's own check" is actually true rather than merely claimed.
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_BARE_ISSUE_REF_RE = re.compile(r"^#?(\d+)$")
_EMBEDDED_ISSUE_REF_RE = re.compile(r"#(\d+)")
_KNOWN_CITATION_PATH_EXTENSIONS = (
    "py",
    "ts",
    "tsx",
    "js",
    "jsx",
    "md",
    "html",
    "htm",
    "json",
    "yaml",
    "yml",
    "txt",
    "css",
    "scss",
    "sql",
    "sh",
    "toml",
    "cfg",
    "ini",
    "rst",
)
_PATH_CITATION_RE = re.compile(
    r"^(?P<path>[A-Za-z0-9_][\w./-]*\.(?:"
    + "|".join(_KNOWN_CITATION_PATH_EXTENSIONS)
    + r"))(?::\d+)?$"
)

# Verdicts P1 triage is documented to ever emit into a batch file, mapped to
# the groom `Verdict` string `aggregate.py`'s `normalize_verdict` actually
# accepts (plan §4 P2's table). Anything outside this set (e.g.
# `needs_work`, `operator_only`) is treated defensively -- rewritten to
# `needs_more_info` -- since the plan states these are never written to a
# batch file in the first place; encountering one anyway means something
# upstream drifted from the documented contract, and this validator must not
# guess at what it means.
_VERDICT_TRANSLATION = {
    "already_done": "fixed",
    "duplicate": "duplicate",
    "not_doing": "superseded",
    "unclear": "needs_more_info",
}


def _has_checkable_superseded_by(citation: Any) -> bool:
    """True only when *citation* is a non-empty string carrying at least one
    mechanically-checkable component, checked in EXACTLY `aggregate.py`'s own
    `_citation_component` priority order (a bare issue ref wins over an
    embedded one, which wins over a sha-shaped read, which wins over a
    path-shaped read of the same text):
      1. a bare issue reference (the WHOLE string is just "#1234"/"1234"),
      2. an issue reference embedded in mixed text ("closed via #1234"),
      3. a raw hex commit sha (the same shape a `fixed` verdict's
         `cited_fix_sha` is required to have),
      4. a repo-relative-looking doc path with a known extension
         (optionally ":<line>").
    This is shape-checking only, never re-verified against ground truth here
    (that re-verification is `aggregate.py`'s own, independent job) -- this
    validator only needs to confirm the citation isn't free text with ZERO
    checkable component ("the operator said so", "n/a"), which `aggregate.py`
    would reject anyway, aborting the whole batch file in the process."""
    if not isinstance(citation, str):
        return False
    stripped = citation.strip()
    if not stripped:
        return False
    if _BARE_ISSUE_REF_RE.fullmatch(stripped):
        return True
    if _EMBEDDED_ISSUE_REF_RE.search(stripped):
        return True
    if _SHA_RE.fullmatch(stripped):
        return True
    return bool(_PATH_CITATION_RE.match(stripped))


def _is_valid_hex_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value))


def _has_non_empty_rationale(rec: dict[str, Any]) -> bool:
    rationale = rec.get("rationale")
    return isinstance(rationale, str) and bool(rationale.strip())


def _has_batch_id(rec: dict[str, Any]) -> bool:
    batch_id = rec.get("batch_id")
    return isinstance(batch_id, str) and bool(batch_id.strip())


def _is_int_coercible(value: Any) -> bool:
    """True only when *value* is genuinely a whole issue number -- mirrors
    `aggregate.py`'s own `int(duplicate_of)` call (`parse_batch_record`),
    which raises `ValueError` (aborting the whole batch file) on anything it
    can't coerce. `bool` is deliberately excluded even though
    ``isinstance(True, int)`` is true in Python -- a JSON `false`/`true`
    value for `duplicate_of` is a malformed record, not a real issue number,
    and letting it through as `int(False) == 0` would silently name issue #0
    as the duplicate target."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        try:
            int(value)
        except ValueError:
            return False
        return True
    return False


def _is_iterable_of_strings(value: Any) -> bool:
    """True when *value* is a list/tuple aggregate.py's `tuple(raw.get(...)
    or ())` call can safely consume. Mirrors the coercion at
    `parse_batch_record`'s `suggested_add_labels`/`suggested_remove_labels`
    fields, which raises `TypeError` on a non-iterable (e.g. a bare int)."""
    return isinstance(value, (list, tuple))


# Fields `aggregate.py`'s `parse_batch_record` coerces UNCONDITIONALLY --
# regardless of verdict or whether the record is otherwise valid -- and
# therefore must be sanitized on EVERY record, not just ones being rejected.
# code-reviewer round 2 demonstrated: a `duplicate_of` this validator would
# reject for one reason (e.g. missing on a `duplicate` verdict) can
# independently carry a non-int-coercible VALUE (`[]`, `["#12","#34"]`) that
# `parse_batch_record:355`'s bare `int(duplicate_of) if duplicate_of is not
# None else None` then raises TypeError/ValueError on. Round 3 found the
# gap was WIDER than that: a genuinely VALID record (e.g. `unclear`, which
# never calls `_rewrite_to_needs_more_info` at all) carrying a garbage
# `duplicate_of`/labels field nobody asked about was still unsanitized,
# because the original fix only ran this INSIDE the rejection helper. It now
# runs upfront in `validate_record`, on every record regardless of outcome
# -- see that function's own call to it. Same coercion class for
# `suggested_add_labels`/`suggested_remove_labels`, via a bare
# `tuple(raw.get(...) or ())`, which raises on a non-iterable (e.g. a bare
# int) or silently char-splats a bare string into a nonsense per-character
# tuple (`tuple("abc") == ("a","b","c")`) -- both shapes are dropped here,
# never coerced or left in place.
_UNCONDITIONALLY_COERCED_FIELDS: tuple[str, ...] = (
    "duplicate_of",
    "suggested_add_labels",
    "suggested_remove_labels",
)


def _sanitize_unconditionally_coerced_fields(rec: dict[str, Any]) -> None:
    """Drops any of `_UNCONDITIONALLY_COERCED_FIELDS` whose VALUE would make
    `aggregate.py`'s unconditional coercion raise. Called UPFRONT by
    `validate_record`, on EVERY record regardless of verdict or eventual
    outcome -- never only on records being rejected (that was round 2's
    fix, and round 3 found it missed every record that reaches a SUCCESS
    branch, e.g. a genuinely valid `unclear` record carrying a garbage
    `duplicate_of` nobody asked about). Dropping the key loses nothing real:
    `number`/`batch_id`/`rationale` -- the fields the field-preservation
    contract actually promises -- are untouched, and a value that WOULD
    coerce cleanly (a real int, an int-shaped string, an actual list) is
    left alone, so this never destroys a genuinely valid value."""
    if "duplicate_of" in rec and rec["duplicate_of"] is not None:
        if not _is_int_coercible(rec["duplicate_of"]):
            del rec["duplicate_of"]
    for labels_field in _UNCONDITIONALLY_COERCED_FIELDS[1:]:
        if labels_field in rec and rec[labels_field] is not None:
            if not _is_iterable_of_strings(rec[labels_field]):
                del rec[labels_field]


def _rewrite_to_needs_more_info(rec: dict[str, Any], reason: str) -> None:
    """Mutates *rec* IN PLACE — only ``verdict``/``rationale`` change here.
    ``number``, ``batch_id``, and every other original field survive
    unchanged. See the module docstring's CRITICAL section for why this must
    never be a fresh dict. (The unconditionally-coerced-field sanitization is
    NOT done here — `validate_record` runs it upfront, before any verdict
    branching, since `aggregate.py` coerces those fields on every record
    regardless of verdict, not only on ones this validator rejects.)"""
    rec["verdict"] = "needs_more_info"
    rec["rationale"] = f"wheel_batch_validate: {reason}"


def validate_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Validates/rewrites one raw batch record per the plan §4 P2 table.

    Mutates and returns *rec* — the SAME object, per the field-preservation
    contract above — for anything shaped like a record at all. Returns
    ``None`` for a genuinely malformed input that has no recoverable
    ``number`` to preserve: (a) not a dict at all, or (b) a dict whose
    ``number`` is missing or not int-coercible. Either way, wrapping it into
    a ``needs_more_info`` shell would NOT satisfy the whole-file-abort
    guarantee this module exists for, since `aggregate.py`'s
    ``_load_batch_file``/``parse_batch_record`` does ``int(raw["number"])``
    UNCONDITIONALLY, before ``verdict`` or anything else runs (code-reviewer
    round 3: the identical unconditional-coercion class as ``duplicate_of``
    below, but for the one field this validator cannot merely sanitize --
    there is no safe fallback value for a record's own identity the way
    there is for a duplicate target or a label list). Dropping it (never
    silently: the caller counts and reports drops) is the only way to keep
    every OTHER record in the batch alive, which is this module's actual job.
    """
    if not isinstance(rec, dict):
        return None

    if not _is_int_coercible(rec.get("number")):
        return None

    # Sanitized UNCONDITIONALLY, before any verdict branching -- aggregate.py's
    # `parse_batch_record` coerces `duplicate_of`/`suggested_add_labels`/
    # `suggested_remove_labels` on EVERY record regardless of verdict or
    # validity (`int(duplicate_of) if duplicate_of is not None else None` and
    # `tuple(raw.get(...) or ())` are both unconditional). A malformed value
    # on these fields would therefore abort the batch even on a record this
    # validator otherwise accepts unchanged (e.g. a valid `unclear` record
    # carrying a garbage `duplicate_of` nobody asked for) -- code-reviewer
    # round 2 demonstrated this exact gap: sanitizing only inside
    # `_rewrite_to_needs_more_info` missed every record that reaches a
    # SUCCESS branch (already_done/duplicate/not_doing's pass-through, and
    # unclear, which never calls the rewrite helper at all).
    _sanitize_unconditionally_coerced_fields(rec)

    raw_verdict = rec.get("verdict")
    verdict = raw_verdict.strip().lower() if isinstance(raw_verdict, str) else None

    if verdict not in _VERDICT_TRANSLATION:
        _rewrite_to_needs_more_info(
            rec,
            f"unrecognized or missing verdict {raw_verdict!r} -- never written to a batch "
            "file by P1 triage per the documented contract; rewritten defensively",
        )
        return rec

    if not _has_batch_id(rec):
        _rewrite_to_needs_more_info(rec, "missing or empty batch_id")
        return rec

    if not _has_non_empty_rationale(rec):
        _rewrite_to_needs_more_info(rec, "missing or empty rationale")
        return rec

    if verdict == "already_done":
        if not _is_valid_hex_sha(rec.get("cited_fix_sha")):
            _rewrite_to_needs_more_info(
                rec,
                "verdict=already_done requires a cited_fix_sha matching "
                "^[0-9a-f]{7,40}$ (hex only) -- none given or not hex-shaped",
            )
            return rec
        rec["verdict"] = _VERDICT_TRANSLATION["already_done"]
        return rec

    if verdict == "duplicate":
        if not _is_int_coercible(rec.get("duplicate_of")):
            _rewrite_to_needs_more_info(
                rec,
                "verdict=duplicate requires an int-coercible duplicate_of target -- "
                "none given or not a whole issue number",
            )
            return rec
        rec["verdict"] = _VERDICT_TRANSLATION["duplicate"]
        return rec

    if verdict == "not_doing":
        if not _has_checkable_superseded_by(rec.get("superseded_by")):
            _rewrite_to_needs_more_info(
                rec,
                "verdict=not_doing requires a mechanically-checkable superseded_by "
                "citation (an issue ref like #1234 or a doc path) -- none given or "
                "not checkable",
            )
            return rec
        rec["verdict"] = _VERDICT_TRANSLATION["not_doing"]
        return rec

    # verdict == "unclear": already valid, needs only rationale/batch_id,
    # both already confirmed present above. Still translated to
    # `aggregate.py`'s own spelling ("needs_more_info") for consistency --
    # `normalize_verdict` DOES alias "unclear" itself, so this translation
    # is not load-bearing the way already_done/not_doing's are, but keeping
    # it uniform means every record this validator lets through already
    # carries the exact string `aggregate.py` will report back, with no
    # silent alias resolution happening one layer downstream.
    rec["verdict"] = _VERDICT_TRANSLATION["unclear"]
    return rec


def validate_batch(records: list[Any]) -> list[dict[str, Any]]:
    """Validates every record in *records*, in order. Every record that has
    a recoverable identity (a dict with an int-coercible `number`) is kept --
    rewritten to `needs_more_info` if it fails validation otherwise, never
    dropped. The ONLY records dropped are ones with NO recoverable `number`
    at all -- not a dict, or a dict whose `number` is missing/uncoercible --
    which `validate_record` returns `None` for (see its own docstring: such
    a record would abort `aggregate.py`'s parse of the WHOLE batch just as
    badly whether kept in with a fake number or dropped quietly, so it is
    dropped, loudly, via `main`'s own reported drop count, never silently)."""
    return [result for rec in records if (result := validate_record(rec)) is not None]


def _is_kept(rec: Any) -> bool:
    """True iff *rec* is the kind of input `validate_record` will keep
    (return non-``None`` for) -- a dict with a recoverable `number`. Used by
    `main` to align `data`/`validated`/`original_verdicts` by the SAME
    predicate `validate_record` itself uses, rather than a narrower
    `isinstance(rec, dict)` check that would miss the bad-`number`-but-dict
    drop case and silently misalign the reject count (code-reviewer round 3)."""
    return isinstance(rec, dict) and _is_int_coercible(rec.get("number"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in",
        dest="in_path",
        required=True,
        type=Path,
        help="JSON array of raw P1-triage batch records",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
        type=Path,
        help="destination for the validated/rewritten JSON array",
    )
    args = parser.parse_args(argv)

    data = json.loads(args.in_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(
            f"[wheel_batch_validate] ERROR: {args.in_path} does not contain a JSON array "
            f"(got {type(data).__name__})",
            file=sys.stderr,
        )
        return 1

    # `validate_record` mutates each record IN PLACE (by design -- see the
    # module docstring's field-preservation contract), so `data[i]` and the
    # eventual `validated[i]` are the SAME object once validation has run --
    # comparing them after the fact would always read as "unchanged." The
    # original verdict is therefore snapshotted BEFORE validation runs, and
    # "rejected" is judged against the translation table's mapping, not
    # against object identity: a record is reported as rejected only when
    # its incoming verdict did NOT map to the result it actually got (a
    # successful `unclear` -> `needs_more_info` translation is not a
    # rejection, even though the strings differ).
    # `_is_kept` mirrors `validate_record`'s OWN drop predicate exactly (a
    # dict with a recoverable `number`) -- code-reviewer round 3: using a
    # narrower `isinstance(rec, dict)` check here missed the bad-`number`
    # drop case added this round, silently under-reporting `dropped` and
    # misaligning the reject count against the wrong record.
    dropped = sum(1 for rec in data if not _is_kept(rec))
    original_verdicts = [rec.get("verdict") if _is_kept(rec) else None for rec in data]
    validated = validate_batch(data)
    # `original_verdicts` still has one entry per INPUT record (including
    # dropped ones), but `validated` is shorter by `dropped` -- align by
    # filtering out the dropped positions before zipping, so a kept record's
    # own original verdict is compared against its own result, never against
    # the next record's result shifted into its slot.
    kept_original_verdicts = [
        v for rec, v in zip(data, original_verdicts) if _is_kept(rec)
    ]
    rejected = sum(
        1
        for orig_verdict, result in zip(kept_original_verdicts, validated)
        if _VERDICT_TRANSLATION.get(
            orig_verdict.strip().lower() if isinstance(orig_verdict, str) else None
        )
        != result.get("verdict")
    )

    args.out_path.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    dropped_suffix = (
        f", {dropped} dropped -- not a dict, or number missing/uncoercible"
        if dropped
        else ""
    )
    print(
        f"[wheel_batch_validate] wrote {len(validated)} record(s) to {args.out_path} "
        f"({rejected} rejected/rewritten to needs_more_info{dropped_suffix})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    raise SystemExit(main())
