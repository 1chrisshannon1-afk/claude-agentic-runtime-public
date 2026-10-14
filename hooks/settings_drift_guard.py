#!/usr/bin/env python3
"""settings_drift_guard — self-heals settings.json's model/effortLevel back to
their committed HEAD values at the start of every session.

WHY THIS EXISTS
---------------
Regressed 4 times (07-09, 07-19, 08-03, 08-20 -- see feedback_model_effort_defaults
in memory): `model`/`effortLevel` in ~/.claude/settings.json drift away from their
committed, deliberately-chosen values, WITHOUT any commit and WITHOUT any script
in this repo doing it. Confirmed mechanism (2026-08-01, re-confirmed live 08-20,
grepping the whole hooks/scripts tree found no write path here): an in-session
`/model` or `/effort` switch in ANY window writes directly to this GLOBAL, shared
file -- and every other Claude Code window/session on this machine reads the SAME
file. `pre_commit_ratchet.py` only catches this if someone commits it; it cannot
see a live, uncommitted drift, and the drift's whole danger is that it sits there
silently for hours or days between commits -- the 07-09 incident ran up an estimated
tens of thousands of dollars (list-price token usage) over two weeks before anyone
noticed.

This hook runs at SessionStart -- a checkpoint that already fires constantly
across this operator's many concurrent windows -- and self-heals: if the live
file's model/effortLevel differ from the last COMMITTED (HEAD) value, it restores
them and prints a loud note in the new session's own context, so whoever starts
that session sees it happened. This bounds the exposure window to (at most)
"until the next SessionStart fires anywhere" instead of "until someone notices."

WHAT THIS DOES NOT DO (round-2 review, finding 28: the original text overclaimed
certainty here -- softened to what is actually verified)
----------------------------------------------------------------------------------
* It touches ONLY `model`, `effortLevel`, and (added 2026-09-23) `modelSettings`,
  and ONLY by restoring each to HEAD's own committed state -- never a hardcoded
  literal. For `modelSettings` "committed state" is usually ABSENT: the client
  writes a `modelSettings: {"<model>": {"effortLevel": "xhigh"}}` block on its own
  (measured 7 times on 2026-09-23 alone, each time alongside a model bump), and
  that block is a per-model effort override that outlives the `model` restore --
  so it is healed by REMOVAL when HEAD has no such key, or restored to HEAD's
  object when it does (see _GUARDED_ABSENT_FIELDS). Commit a genuinely new
  default (e.g. the whole team moving to a better/cheaper model) and THAT becomes
  the new baseline this hook restores toward; it never fights a real, committed
  decision. Every OTHER top-level key that differs from HEAD is only REPORTED
  (logged), never touched -- see report_other_drift(). Deliberately narrow,
  matching pre_commit_ratchet.py's own reasoning against a broad hardcoded
  allowlist.
* Whether a DELIBERATE `/model` escalation in an already-running window survives
  is NOT independently verified by this module -- it depends on whether that
  client process re-reads settings.json only at its own startup or continuously.
  If it only reads at startup, this hook (SessionStart-scoped) cannot affect an
  already-running window at all. If it re-reads live, restoring the file from
  ANY window (including a fresh SessionStart elsewhere) could revert an active,
  wanted escalation before its task finishes. Either way, the exposure window
  this hook bounds is "until some session, somewhere, next starts" -- not a
  guaranteed same-window correction.
* It is NOT a substitute for `pre_commit_ratchet.py` -- that still blocks a
  regression from landing in a COMMIT; this only heals the live, uncommitted file
  between commits.

SAFETY OF THE WRITE ITSELF (round-2 review, findings 10 + 11)
---------------------------------------------------------------
* Atomic: writes to a temp file in the SAME directory, then `os.replace()` --
  a kill mid-write (client timeout, Ctrl-C, session abort) can never leave a
  truncated or half-written settings.json, which would be strictly worse than
  the drift being fixed (every hook registration and permission gone, not just
  two fields). Mirrors record_review.py's own `_update_entry` convention.
* The surgical text-replacement path (see _replace_field_value) is NOT trusted
  blindly: apply_fix VERIFIES the result re-parses to exactly the expected
  merged dict before writing it, and falls back to a full, safe JSON re-
  serialize if that check fails for ANY reason -- including a nested key with
  the same name appearing earlier in the file (the regex has no JSON nesting
  awareness on its own; the verification step is what actually guarantees
  correctness, not the regex's own care).
* No cross-process lock: two SessionStart hooks racing on the same file both
  restore toward the SAME committed value, so last-writer-wins is benign (see
  compute_drift's docstring). The one real race this does NOT close: the
  CLIENT itself may be writing this file around the same moment (that write is
  the entire subject of this module); the read-write window here is kept as
  short as possible, but a client write landing inside that window can still
  be silently overwritten. This is a known, accepted residual risk, not
  something this module can fully close without a lock the client itself also
  respects.

Enforcement-gating: this hook is INTENTIONALLY not gated by `_lib.enforcing()`
-- it restores drift the same way in LOG-ONLY mode as it does when explicitly
enforcing, because a "log-only self-healer" heals nothing; the risk it guards
against (silent cost/latency regression) is not something WARN-mode logging
alone has ever stopped (that is the four-incident history this module exists
to end). The master switch `CSA_DISABLE_HOOKS=1` and this module's own
`CSA_NO_SETTINGS_DRIFT_GUARD=1` lever (mirroring every sibling gate's per-
module escape hatch, see enforcement_doctor.sh) are the only ways to turn it
off.

Fails open, always: any read/parse/write failure is a silent no-op (changes
nothing) -- a bug in THIS hook must never block a session from starting, which
is the one thing a SessionStart hook can never do. Every outcome (restored,
no-drift, disabled, or a failure) is logged via `_lib.log` -- round-2 review
finding 12: the FIRST version of this module wrote to the exact file whose
unlogged mutation is the entire four-incident problem, with zero record in
`~/.claude/.enforcement/log.jsonl` that it had run at all.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest pre-seeds sys.path
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirrors sibling modules)

HOOK = "settings_drift_guard"

# Per-module rollback lever, mirroring every sibling gate's own escape hatch
# (CSA_NO_PRECOMMIT_REVIEW, CSA_NO_COMMIT_MUTEX, CSA_NO_REQUIRE_PATHSPEC --
# see enforcement_doctor.sh). Without one, the only way to stop a misfiring
# instance of THIS module is CSA_DISABLE_HOOKS=1, which also switches off
# every other hook in the chain.
DISABLE_VAR = "CSA_NO_SETTINGS_DRIFT_GUARD"

# Only these two fields are ever RESTORED. Deliberately narrow: this hook
# exists for a specific, 4-times-proven regression, not as a general
# settings.json integrity checker (see pre_commit_ratchet.py's own reasoning
# for why a broad hardcoded allowlist would go stale). Every OTHER top-level
# key is only reported when it drifts -- see report_other_drift().
_GUARDED_FIELDS = ("model", "effortLevel")

# Top-level keys the CLIENT writes on its own (never this repo) whose committed
# state is normally ABSENCE. Widened 2026-09-23 after `modelSettings` was found
# re-written into settings.json SEVEN times in one day (effort blocks such as
# {"claude-fable-5-1": {"effortLevel": "xhigh"}} and
# {"claude-sonnet-5": {"effortLevel": "xhigh"}}, the most expensive
# model/effort pairs available), each time after an agent had removed it and
# the operator had ruled on 2026-09-20 that it stay removed. report_other_drift
# saw every recurrence and, by design, only logged it. For these keys the rule
# is: absent at HEAD means it must be absent live (the whole object is
# removed); present at HEAD means it is restored to that committed value like
# any guarded field. A deliberate, committed modelSettings therefore still
# wins; only the uncommitted client rewrite is healed.
_GUARDED_ABSENT_FIELDS = ("modelSettings",)

# Unforgeable "this key is not present" marker used INSIDE drift tuples. It is
# deliberately not a string: apply_fix dispatches a DELETION on it, and a
# string sentinel would collide with a committed key whose legitimate value
# happened to be that same string (round-2 review of the modelSettings change:
# a committed `"model": "<absent>"` would have been deleted instead of
# restored). Only format_message ever renders it, as the text "<absent>".
_ABSENT = object()


def _disabled_by_operator(environ: dict | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get(DISABLE_VAR, "") == "1"


def _git_show(repo: str, ref_path: str) -> str | None:
    """`git show <ref_path>` output, or None on ANY failure. Never raises."""
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            ["git", "-C", repo, "show", ref_path],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse(text: str | None) -> dict | None:
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def compute_drift(committed: dict | None, live: dict | None) -> dict:
    """Pure: {field: (live_value, committed_value)} for every GUARDED field
    that differs between the two. Never raises.

    A field absent from `committed` is skipped -- there is no baseline to
    restore TO. A field absent from `live` but present in `committed` DOES
    count as drift: restoring an accidentally-deleted key matters exactly as
    much as restoring a changed one -- 07-09's failure mode was specifically
    an absent `effortLevel` key, not just a wrong value.
    """
    committed = committed or {}
    live = live or {}
    drift: dict = {}
    for field in _GUARDED_FIELDS:
        if field not in committed:
            continue
        committed_val = committed[field]
        live_val = live.get(field, _ABSENT)
        if live_val != committed_val:
            drift[field] = (live_val, committed_val)
    # Absence-guarded keys: here a key ABSENT from committed is not "no
    # baseline", it IS the baseline. Present live + absent committed -> drift
    # whose restored value is the unforgeable _ABSENT sentinel, which apply_fix
    # turns into a deletion. Present in both -> ordinary value drift.
    for field in _GUARDED_ABSENT_FIELDS:
        committed_val = committed.get(field, _ABSENT)
        live_val = live.get(field, _ABSENT)
        if live_val != committed_val:
            drift[field] = (live_val, committed_val)
    return drift


def report_other_drift(committed: dict | None, live: dict | None) -> list[str]:
    """Top-level keys OTHER than the guarded fields that differ between
    committed and live. Never restored, never printed loudly -- only logged
    (see main()), so this data can eventually inform whether the guarded set
    should grow (round-2 review finding 27). Never raises.
    """
    committed = committed or {}
    live = live or {}
    other: list[str] = []
    # Union of BOTH sides' keys, not just committed's -- round-2 review
    # finding F: iterating committed-only misses a key the CLIENT ADDS that
    # was never committed at all (e.g. ~/.claude.json's own
    # orgModelDefaultCache pattern, if the client ever wrote something
    # similar into settings.json itself), which is exactly the kind of
    # addition this reporting exists to surface.
    for key in sorted(set(committed) | set(live)):
        if key in _GUARDED_FIELDS or key in _GUARDED_ABSENT_FIELDS:
            # Both guarded sets are RESTORED, not reported: a key here would
            # be double-counted in the ledger (round-2 review of the
            # modelSettings change measured exactly that, `other-keys-drifted`
            # and `restored` on the same run), which corrupts the very signal
            # that decides whether the guarded set should grow.
            continue
        committed_val = committed.get(key, _ABSENT)
        live_val = live.get(key, _ABSENT)
        if live_val != committed_val:
            other.append(key)
    return sorted(other)


def _replace_field_value(text: str, field: str, new_value_json: str) -> str | None:
    """Surgically replace the FIRST `"field": <scalar>` occurrence in raw
    JSON TEXT, preserving every other byte (formatting, key order, comments-
    as-string-fields) untouched. Returns None if the field isn't found in
    this exact shape -- never raises, never guesses.

    NOT trusted on its own to be correct (see apply_fix's verification step):
    this regex has no notion of JSON nesting, so a NESTED key with the same
    name appearing earlier in the file could match instead of the intended
    top-level one. That correctness gap is closed by re-parsing and comparing
    the result, not by making this regex smarter.
    """
    pattern = (
        rf'("{re.escape(field)}"\s*:\s*)'
        r'("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|true|false|null)'
    )
    new_text, n = re.subn(pattern, lambda m: m.group(1) + new_value_json, text, count=1)
    if n != 1:
        return None
    return new_text


def _atomic_write(path: str, text: str) -> bool:
    """Write `text` to `path` atomically: temp file in the SAME directory,
    then `os.replace()`. A kill between these two steps leaves either the
    OLD file (replace never happened) or the NEW file (replace completed) --
    never a truncated/partial one. Mirrors record_review.py's own
    `_update_entry` convention for the same reason. Returns True on success,
    False on any failure (and best-effort removes the temp file on failure).
    Never raises.
    """
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False


def apply_fix(settings_path: str, live_text: str, live_dict: dict, drift: dict) -> bool:
    """Restore drifted fields to their committed value. Returns True on
    success, False on any failure. Never raises.

    Prefers a surgical text replacement (preserves every byte of formatting
    elsewhere in the file) for a field PRESENT in the live text with a
    different value -- but VERIFIES it before trusting it: the result is
    re-parsed and compared against the exact expected merged dict, and any
    mismatch (including the nested-duplicate-key case _replace_field_value's
    own docstring warns about) falls back to a full, always-correct JSON
    re-serialize instead. Correctness is guaranteed by this verification
    step, not by the regex being clever.
    """
    expected = dict(live_dict)
    for field, (_old, restored) in drift.items():
        if restored is _ABSENT:
            # A guarded-absent field (_GUARDED_ABSENT_FIELDS): HEAD has no such
            # key, so healing it means REMOVING it, never writing a value.
            expected.pop(field, None)
        else:
            expected[field] = restored

    text = live_text
    surgical_ok = True
    for field, (_old, restored) in drift.items():
        if (
            field not in live_dict
            or restored is _ABSENT
            or not isinstance(restored, (str, int, float, bool))
        ):
            # Surgical replacement handles only an in-place SCALAR swap. A key
            # deletion, or a non-scalar committed value (the client-written
            # `modelSettings` object), takes the verified re-serialize path.
            surgical_ok = False
            continue
        replaced = _replace_field_value(text, field, json.dumps(restored))
        if replaced is None:
            surgical_ok = False
            continue
        text = replaced

    if surgical_ok:
        verify = _parse(text)
        if verify != expected:
            surgical_ok = False

    if not surgical_ok:
        text = json.dumps(expected, indent=2) + "\n"

    return _atomic_write(settings_path, text)


def format_message(drift: dict) -> str:
    lines = [
        f"[settings_drift_guard] restored {len(drift)} field(s) in settings.json "
        "to their committed value:"
    ]
    for field, (old, restored) in sorted(drift.items()):
        shown_old = "<absent>" if old is _ABSENT else repr(old)
        if restored is _ABSENT:
            # A guarded-absent key the client wrote (e.g. `modelSettings`):
            # healed by removal, so say "removed", not "-> '<absent>'".
            lines.append(f"  {field}: removed (was {shown_old}; not present at HEAD)")
        else:
            lines.append(f"  {field}: {shown_old} -> {restored!r}")
    lines.append(
        "  (Regressed 4x before this hook existed -- see "
        "feedback_model_effort_defaults in memory. If you WANTED the drifted "
        "value for THIS session, re-set it now; this only restores at session "
        "start, not continuously.)"
    )
    return "\n".join(lines)


def main() -> int:
    """SessionStart entrypoint. Always exits 0 -- never blocks a session.

    Every exit path logs its outcome via _lib.log (round-2 review finding C:
    an earlier version left 4 of 8 exit paths silent, including the
    unparsable-live-file case -- exactly the state a client-corrupted
    settings.json would leave, which would then make this guard sit
    silently inert forever with zero trace, the "guard exists, guard never
    fires" failure mode check_safety_core_parity.py exists to catch
    elsewhere in this repo).
    """
    try:
        if _lib.disabled() or _disabled_by_operator():
            _lib.log(HOOK, "disabled")
            return 0

        home = os.environ.get("HOME") or os.path.expanduser("~")
        repo = os.path.join(home, ".claude")
        settings_path = os.path.join(repo, "settings.json")

        committed = _parse(_git_show(repo, "HEAD:settings.json"))
        if committed is None:
            _lib.log(HOOK, "no-committed-baseline")
            return 0  # no baseline to restore toward

        try:
            with open(settings_path, encoding="utf-8") as fh:
                live_text = fh.read()
        except Exception:
            _lib.log(HOOK, "live-file-unreadable")
            return 0
        live = _parse(live_text)
        if live is None:
            _lib.log(HOOK, "live-file-unparsable")
            return 0  # unparsable live file -- do not touch it blindly

        others = report_other_drift(committed, live)
        if others:
            _lib.log(HOOK, "other-keys-drifted", keys=others)

        drift = compute_drift(committed, live)
        if not drift:
            _lib.log(HOOK, "no-drift")
            return 0

        fields = sorted(drift.keys())
        if apply_fix(settings_path, live_text, live, drift):
            print(format_message(drift))
            _lib.log(HOOK, "restored", fields=fields)
        else:
            _lib.log(HOOK, "write-failed", fields=fields)
        return 0
    except Exception as exc:
        # _lib.log is itself best-effort/never-raises (see its own
        # docstring), so calling it from this handler is safe even if the
        # failure above was catastrophic.
        _lib.log(HOOK, "internal-error", error=str(exc))
        return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
