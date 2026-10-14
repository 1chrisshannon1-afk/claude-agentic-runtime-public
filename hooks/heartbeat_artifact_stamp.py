#!/usr/bin/env python3
"""heartbeat_artifact_stamp — resolve and rewrite relative artifact-path
claims inside a heartbeat's own `summary` string to their absolute form
(#5055, closing the 2026-09-07 launchdir false-alarm incident).

WHY THIS EXISTS: the launchdir weekly job's own executed recon found its
write instruction (`weekly_report.txt:3`) names an absolute artifact path
(`/Users/x/.claude/plans/csa_state_<date>.html`), but its summary
instruction (`weekly_report.txt:10`, pre-fix) never asked the session to
NAME that path in the heartbeat summary at all — and the live heartbeat on
disk that day carried a bare, relative-looking claim instead. A human (or
another tool) reading only the heartbeat summary had no way to resolve that
claim back to the real file without already knowing the write instruction
by heart — which is exactly what produced a false "the report is missing"
alarm against a report that was sitting on disk the whole time, just not
nameable from the heartbeat alone.

This module is the mechanical, pure-Python complement: given a heartbeat
JSON file and the job's own working directory, it finds every path-shaped
token in the summary, resolves it against (in order) the job's
WorkingDirectory and `$HOME/.claude`, and — for every claim that resolves to
a REAL, EXISTING file — rewrites the summary text in place to the absolute
form and records a typed `artifacts_verified` list so a consumer never has
to re-derive the resolution logic itself. `heartbeat_audit.py`'s own
`relative-artifact-claim` check imports `extract_path_claims` from this
module (never reimplements it) so the two can never drift on what counts as
a path-shaped token.

REALITY-GATED, DELIBERATELY (fixed 2026-09-07, dual-Opus review B-1 blocker):
`extract_path_claims` is SHAPE-only — it has no notion of "is this actually
an artifact reference" versus ordinary prose that merely contains a slash
(a dropped-item tally "dropped 2/5", a cluster label "Clusters C/E", a date
written "2026/09/01", "and/or", "n/a", a CLI flag "-v/--verbose", a
parenthesized fragment "(test_quality/history.jsonl", a duration "~8h").
Every one of those is SHAPE-indistinguishable from a genuine relative
artifact claim by extract_path_claims alone. The reality gate is what
separates them: a real artifact claim resolves to a file that ACTUALLY
EXISTS on disk (workdir or $HOME/.claude); prose never does, because none of
those tokens denote a real path in the job's own filesystem. So both the
in-place rewrite AND the `artifacts_verified` recording below are gated on
`exists is True` — an earlier version of this module gated only on
"resolved is not None", which is always true for a relative claim (the
workdir/HOME join always produces SOME string), and that version corrupted
every one of the prose examples above in executed testing. Skipping
unresolvable prose ENTIRELY (never even recording it in
`artifacts_verified`) also closes the "~8h read back as a fake artifact"
finding from the same review round.

Stamping is an ENHANCEMENT, never a correctness signal — a heartbeat write
still succeeds/fails on its own terms regardless of what this module does
to it afterward. Every public entry point degrades to a silent no-op
(exit 0, file byte-for-byte untouched) on:
  * a summary starting with the literal "WRAPPER:" prefix (the wrapper's own
    fail-fast diagnostic write, see run_oversight_job.sh) — LOAD-BEARING,
    not a convenience: even after B4 (run_oversight_job.sh's own fallback
    diagnostic path uses an absolute log path), the wrapper's boilerplate
    summary text still contains relative-shaped prose fragments of its own
    (e.g. "session/usage-limit" inside "Anthropic session/usage-limit
    exhaustion mid-run") that this exemption is what protects from being
    treated as artifact claims — do NOT remove this exemption on the
    reasoning that "B4 made it unnecessary"; the two are unrelated: B4 fixed
    a DIFFERENT relative path (the diagnostic's own `schedules/logs/...`
    citation), not this one;
  * a missing or unparseable heartbeat file;
  * zero claims found in the summary, or zero claims that pass the reality
    gate above (a summary that is ALL prose, no real artifact, is a no-op —
    never rewritten just to record what it could not verify);
  * ANY exception anywhere in the read/mutate/write path (a crashing
    enhancement must never turn into a job-failure signal).

CLI:
    python3 heartbeat_artifact_stamp.py <hb_path> <workdir>

Always exits 0 — this is invoked as a fire-and-forget step from
run_oversight_job.sh (`... || true`, belt-and-suspenders on top of the
always-0 contract already guaranteed internally).

This module owns exactly two files:
  ~/.claude/hooks/heartbeat_artifact_stamp.py  (this file)
  ~/.claude/hooks/tests/test_heartbeat_artifact_stamp.py
"""

from __future__ import annotations

import json
import os
import re
import sys

_HOME = os.path.expanduser("~")
DEFAULT_CLAUDE_DIR = os.path.join(_HOME, ".claude")

_WRAPPER_PREFIX = "WRAPPER:"

# A path-shaped token: contains a "/" (so a bare word like "ok" or "daily"
# never matches) or starts with "~" (home-relative). Bounded by whitespace on
# either side so it can be lifted out of free-form summary prose. Punctuation
# immediately trailing the token (a sentence-ending period, a comma, a
# closing paren) is stripped separately below rather than folded into the
# character class, so "report.html." in "...the report.html." doesn't lose
# its own extension.
_TOKEN_RE = re.compile(r"(?<!\S)(~[^\s]*|[^\s]*/[^\s]*)(?!\S)")

_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")

# Trailing punctuation a token might pick up from being embedded in a
# sentence — stripped before path handling, never treated as part of the
# path itself. Kept narrow (no stripping of characters that are legitimate
# in a path, e.g. no bare "-" or "_").
_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?)\]}'\"]+$")


def _strip_trailing_punct(token: str) -> str:
    return _TRAILING_PUNCT_RE.sub("", token)


def extract_path_claims(summary: str) -> list[str]:
    """Every path-shaped token in `summary`: contains a "/" or starts with
    "~", is not a URL (has no `scheme://` prefix), and is not a bare "/" or
    "~" with nothing after it. Order preserved, duplicates preserved (a
    caller that wants uniqueness dedupes itself) — this is a pure extraction
    step, not a resolution step. Returns [] for a non-string or empty input,
    never raises.
    """
    if not isinstance(summary, str) or not summary:
        return []
    claims: list[str] = []
    for match in _TOKEN_RE.finditer(summary):
        token = _strip_trailing_punct(match.group(1))
        if not token:
            continue
        if _URL_RE.match(token):
            continue
        if token in ("/", "~"):
            continue
        if "/" not in token and not token.startswith("~"):
            continue
        claims.append(token)
    return claims


def resolve_claim(claim: str, workdir: str | None) -> tuple[str | None, bool]:
    """Resolve one path claim to (resolved_absolute_path_or_None, exists).

    Precedence:
      * already absolute (starts with "/") -> returned as-is (no rewrite
        needed — the claim is already in the form this whole module exists
        to produce).
      * "~"-anchored -> `os.path.expanduser` (never treated as "relative").
      * otherwise relative -> tried first against `workdir` (when given and
        truthy), then against `$HOME/.claude`; the first candidate that
        actually EXISTS on disk wins. Neither exists -> the WORKDIR-joined
        candidate is still returned as `resolved` (a best-effort absolute
        form worth rewriting the summary to) with `exists=False` — so a
        legitimate claim that just hasn't landed on disk yet at stamp-time
        still resolves to a stable, later-checkable absolute path, but a
        genuinely bogus claim reads back honestly as "does not exist"
        rather than silently disappearing.

    Returns (None, False) only for a malformed/empty claim (not a string, or
    empty) — an absolute or `~`-anchored claim always returns its own
    resolved form (never None), even when that path does not exist on disk.
    For a genuinely RELATIVE claim, `resolved` is likewise NEVER None (the
    workdir/HOME join always produces some candidate string) — callers that
    want to distinguish "a real artifact" from "prose that merely looked
    path-shaped" MUST gate on the `exists` flag, never on `resolved is not
    None` (see `stamp`'s own module-docstring note on the B-1 review finding
    this fixes: gating on `resolved is not None` alone corrupted ordinary
    prose like "dropped 2/5" or "Clusters C/E", neither of which denotes a
    real file). Never raises.
    """
    if not isinstance(claim, str) or not claim:
        return (None, False)

    if claim.startswith("~"):
        expanded = os.path.expanduser(claim)
        return (expanded, os.path.exists(expanded))

    if claim.startswith("/"):
        return (claim, os.path.exists(claim))

    # Relative: try workdir first, then $HOME/.claude.
    candidates: list[str] = []
    if workdir:
        candidates.append(os.path.join(workdir, claim))
    candidates.append(os.path.join(DEFAULT_CLAUDE_DIR, claim))

    for candidate in candidates:
        if os.path.exists(candidate):
            return (candidate, True)

    # Nothing existed — return the first (workdir-preferred) candidate as a
    # best-effort absolute form, honestly marked as not-yet-existing.
    return (candidates[0], False)


def _is_true_absolute(claim: str) -> bool:
    """True iff `claim` is genuinely `/`-anchored — the ONLY shape the B-1
    reality gate treats as unconditionally real regardless of `exists`.

    Deliberately narrower than "not relative": a `~`-anchored token is NOT
    treated as true-absolute here, even though `resolve_claim` handles both
    the same way structurally. `os.path.expanduser` only expands a `~` it
    recognizes as a real (bare or `~user`) home-directory reference — for
    anything else (a duration written "~8h", a fuzzy-match marker "~3
    items") it silently returns the token UNCHANGED, so `~8h` reads back as
    "resolved='~8h', exists=False" exactly like an ordinary failed relative
    resolution, not like a confirmed real path. Treating every `~`-prefixed
    token as automatically real (the pre-fix behavior) recorded "~8h" in
    artifacts_verified as a fake artifact — a live B-1 review finding.
    A `~`-anchored claim is therefore gated on `exists` exactly like a
    relative claim; only a real `/`-anchored claim is exempt from that gate.
    """
    return isinstance(claim, str) and claim.startswith("/")


def stamp(hb_path: str, workdir: str | None) -> bool:
    """Read the heartbeat JSON at `hb_path`, resolve every path-shaped token
    in its `summary` string against `workdir`, and — for every claim that is
    EITHER already absolute OR a relative claim that resolves to a file that
    ACTUALLY EXISTS on disk (the reality gate; see the module docstring's
    B-1 note) — rewrite the summary text in place to the resolved absolute
    form and record it in a top-level `artifacts_verified` list (`{"claimed":
    <original token>, "resolved": <absolute path>, "exists": <bool>}`).
    A relative claim that does NOT resolve to an existing file (ordinary
    prose that merely contains a slash — "dropped 2/5", "Clusters C/E",
    "2026/09/01", "and/or", "n/a", "-v/--verbose", "~8h") is SKIPPED
    entirely: never rewritten, never recorded in `artifacts_verified` — it
    is not a real artifact claim, so there is nothing to stamp. Writes the
    result back atomically (temp file in the SAME directory + os.replace —
    mirrors every other atomic-write helper in this hooks/ directory, e.g.
    settings_drift_guard._atomic_write / file_claims._write_claim).

    Returns True iff the file was rewritten; False for every no-op case
    below (file untouched in every False case):
      * `hb_path` missing or unreadable/unparseable JSON;
      * the heartbeat is not a JSON object;
      * its `summary` is not a string, or starts with "WRAPPER:" (the
        wrapper's own fail-fast diagnostic — LOAD-BEARING exemption, see
        module docstring — never stamped);
      * zero path-shaped tokens found in the summary, or none of them pass
        the reality gate (an all-prose summary is a no-op);
      * ANY exception anywhere in this function (stamping is an
        enhancement, never a job-failure signal — the ORIGINAL file must
        never be left partially written or corrupted by a failed stamp
        attempt).

    Never raises.
    """
    try:
        with open(hb_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return False

    if not isinstance(data, dict):
        return False

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary:
        return False
    if summary.startswith(_WRAPPER_PREFIX):
        return False

    claims = extract_path_claims(summary)
    if not claims:
        return False

    try:
        artifacts_verified: list[dict] = []
        new_summary = summary
        # Dedup claims for resolution work (a repeated identical claim only
        # needs resolving once), but keep artifacts_verified in FIRST-SEEN
        # order matching how a reader encounters them in the summary text.
        seen: dict[str, tuple[str | None, bool]] = {}
        for claim in claims:
            if claim not in seen:
                seen[claim] = resolve_claim(claim, workdir)
            resolved, exists = seen[claim]

            # REALITY GATE (B-1 fix): a TRUE-absolute ("/"-anchored) claim is
            # always kept as-is (it is already in the target form, regardless
            # of whether the path exists — an absolute claim naming a
            # not-yet-written file is still a real, unambiguous artifact
            # REFERENCE, just not one this run can confirm on disk yet).
            # EVERYTHING ELSE — a plain relative claim OR a "~"-anchored one —
            # is kept ONLY when it resolved to a file that actually exists.
            # "~" is deliberately NOT treated as automatically real here (see
            # _is_true_absolute's own docstring): os.path.expanduser silently
            # returns an unrecognized "~token" (a duration "~8h", a fuzzy-
            # match marker) UNCHANGED rather than failing, so without this
            # gate it would read back exactly like a confirmed real path.
            # This is the one signal that distinguishes a genuine artifact
            # claim (the launchdir incident class) from prose that merely
            # contains a slash or a leading tilde. Anything that fails the
            # gate is skipped entirely: not rewritten, not recorded.
            is_true_absolute = _is_true_absolute(claim)
            if not is_true_absolute and not exists:
                continue
            if resolved is None:
                continue

            artifacts_verified.append(
                {"claimed": claim, "resolved": resolved, "exists": exists}
            )
            if not is_true_absolute:
                # Whole-token replacement only — never a substring match
                # that could clobber an unrelated occurrence of the same
                # text elsewhere in the sentence. re.escape + a boundary
                # anchor matching how it was extracted (surrounded by
                # non-\S or string edges).
                new_summary = re.sub(
                    r"(?<!\S)" + re.escape(claim) + r"(?!\S)",
                    resolved.replace("\\", "\\\\"),
                    new_summary,
                )

        if not artifacts_verified:
            # Every extracted token was either malformed or failed the
            # reality gate (all prose, no real artifact) -- a true no-op,
            # never worth a write.
            return False

        data["summary"] = new_summary
        data["artifacts_verified"] = artifacts_verified

        directory = os.path.dirname(hb_path) or "."
        tmp_path = os.path.join(directory, f".{os.path.basename(hb_path)}.tmp.{os.getpid()}")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp_path, hb_path)
        return True
    except Exception:
        try:
            os.remove(tmp_path)  # type: ignore[possibly-undefined]
        except Exception:
            pass
        return False


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Always returns 0 — stamping is fire-and-forget."""
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 3:
        return 0
    hb_path, workdir = argv[1], argv[2]
    try:
        stamp(hb_path, workdir or None)
    except Exception:
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
