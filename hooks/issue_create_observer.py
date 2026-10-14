#!/usr/bin/env python3
"""issue_create_observer — PreToolUse OBSERVER for issue-CREATION quality
(#5827, master plan WS1 Phase D — "Creation quality gate +
promotion budget (observer-first)").

Modeled on `churn_tracker.py`'s PURE-OBSERVER shape (see that module's own
docstring and `pretooluse_bash.py`'s gate 6): this module is wired into the
`PreToolUse:Bash` gate chain but can **never** return a block and has **no**
`enforcing()`-gated hard-block path at all in this commit. It exists purely
to make "how often does an issue get created without a Priority value or the
three label classes, and how often does an agent bypass the helper entirely"
a measurable, logged fact — the observer-first half of Phase D — never to
refuse a creation. A LATER, separate commit is what turns any of this into a
real deny, gated on board-steward's 30-event false-positive audit (plan
§"Phase D", "Bar").

MEASURED CAUSE (plan §1, "Measured baseline"): 1,469 open issues, 56.6
filed/day vs 18.8 closed; 985 open issues have no priority label; a September
burst of 53 issues bypassed the helper with zero labels. This module is the
mechanical instrument for "would a creation-quality gate actually have caught
that" before any refusal is ever turned on.

TWO SHAPES OBSERVED, per Bash segment (compound commands: every segment is
inspected independently — this differs from every BLOCKING gate in this
chain, which stops at the first violation; an observer has no reason to
short-circuit, since it never affects the command's outcome):

  (a) BARE `gh issue create ...` — any `gh issue create` invocation that did
      NOT go through this runtime's own `~/.claude/scripts/gh_issue.sh`
      helper. Logged as `bare-issue-create`, carrying the would-be redirect
      message pointing at the helper and its `--priority`/label flags.

  (b) `gh_issue.sh create ...` (any path prefix; basename match, mirroring
      every sibling gate's `_is_gh_issue_sh`-style convention) — inspected
      for `--priority` and the three label classes (one `type` label, at
      least one `area:` label, one `difficulty:` label — see
      :data:`_TYPE_LABELS` / `_AREA_PREFIX` / `_DIFFICULTY_PREFIX`, matching
      the taxonomy `.claude/oversight/board-steward.md` §2 records for the
      ExampleApp AI board). Missing `--priority` OR any label class is
      logged as `create-missing-triage-would-deny`, naming exactly which
      piece(s) are absent. A fully-compliant `gh_issue.sh create` logs
      NOTHING (silence is the expected, common case — this observer is not
      meant to produce a line for every create, only for the ones that would
      eventually be denied).

Every OTHER `gh`/`gh_issue.sh` invocation (comment/transition/resolve/
dispose, or a `create` this module cannot classify) is a no-op: nothing to
observe.

DETECTION BLIND SPOTS (fix-round 2, finding 5 — named explicitly, not left
implicit, because board-steward's 30-event false-positive audit needs its
denominator understood: this observer's silence on a real bypass is a
FALSE NEGATIVE for that audit, not evidence the bypass didn't happen).
Executed and confirmed by the reviewer, 2026-09-21: each of these yields
ZERO observations from this module, even though the underlying `gh issue
create`/`gh_issue.sh create` genuinely runs:
  * `bash -c "gh issue create ..."` — the create command is embedded inside
    a STRING argument to `bash -c`, never a literal token this module's own
    segment/argv tokenizer ever sees as `gh`/`gh_issue.sh` in argv[0].
  * `sudo gh issue create ...` — `sudo` is not in `_LEADING_INVOKER_WORDS`
    (only `env`/`command` are stripped), so argv[0] reads as `sudo`, never
    `gh`.
  * `xargs gh issue create ...` (piped args) — the actual `--title`/
    `--label`/`--priority` VALUES never appear as literal tokens in the
    Bash command string this hook receives at all; they arrive on stdin via
    the pipe, invisible to a command-string-only observer.
  * A `for` loop whose body invokes `gh_issue.sh create` — depending on
    shell quoting, the loop's OWN control-flow tokens (`for`/`do`/`done`)
    can desync this module's segment splitter from where the real
    `gh_issue.sh create` invocation actually starts, and a loop-variable-
    interpolated flag value is never resolved by this static, non-executing
    reader.
  * See `docs/subsystems/gate-chain.md`'s own `issue_create_observer`
    section for the same list restated for a non-code-reading audience.
  Under-detection (a false negative — missing a real bypass) is the SAFE
  direction for a pure observer that can never deny anything; the opposite
  (a false positive — flagging a compliant create as non-compliant) is what
  the 30-event audit actually screens for. Both directions matter to that
  audit's denominator, which is why both are named here rather than only
  the safe one.

A `priority:` LABEL is deliberately NOT recognized as satisfying the
Priority FIELD requirement (fix-round 2, finding 6): this repo's own board
dossier (`.claude/oversight/board-steward.md` §2) rules fields are truth,
not labels — a `priority:` label exists on this board only as a LEGACY,
being-retired convention. A `create` carrying `--label "priority: P1"` and
no `--priority` flag is therefore flagged (`missing: ["priority"]`) ON
PURPOSE, not by an oversight that treats label text as a substitute for the
field — the audit must classify this class of create as genuinely missing
its Priority FIELD, exactly as the board's own truth model requires.

FAIL-OPEN / FAIL-AMBIGUOUS CONTRACT (deliberately NOT the same posture as a
blocking gate's parse-ambiguity handling, e.g. gate 1's
`untokenizable-segment-with-git`): those gates fail CLOSED on ambiguity
because an unparseable wrapper around a dangerous shape is a real bypass
vector THEY must not let through. This module can never deny anything in
this commit, so there is no bypass to close — an untokenizable segment that
still carries the textual shape of a `gh`/`gh_issue.sh` issue-create
invocation is logged as `create-observer-ambiguous` (once per such segment)
rather than silently dropped, so the eventual false-positive audit can see
how often ambiguity itself would be the deciding factor — but it is ALWAYS
just a log line, never a deny, never a reason to alter the command's
outcome. Any internal exception degrades to a complete no-op (nothing
logged, nothing raised) — an observer's own bug must never surface to the
agent whose command it is merely watching.

CONTRACT (matching every sibling gate in this chain):
  * PURE core: :func:`observe(command) -> list[tuple[str, dict]]` — a list of
    (decision, detail) pairs to log, given the raw command string. No I/O.
  * Thin `main()`: read the event, call `observe`, log every entry via
    `_lib.log`. Always exits 0 — this module has nothing to emit as a deny
    (it never calls `_lib.emit_pretooluse_deny`, which is precisely what
    keeps `check_safety_core_parity.py`'s guard-wiring check from
    classifying it as a PreToolUse guard that must be reachable — see that
    module's own `_GUARD_SIGNAL_RE`).
  * `CSA_DISABLE_HOOKS=1` master-OFF: no-op before anything else.
  * Only the Bash tool is gated; every other tool is a no-op.

WIRING: called from `pretooluse_bash.py`'s `resolve_block()` as its own
observer step (mirroring gate 6's `_churn_observe` call site) — reached
unconditionally (it is never itself capable of blocking, so there is no
"only when nothing else blocked" short-circuit reason to place it after the
gates the way gate 6's placement is deliberate for; it is invoked
independently of whether a `git commit`-shaped or `gh issue close`-shaped
gate blocked this same command, since a `gh issue create` command can never
BE any of those other shapes in the same segment).

This module owns exactly two files:
  ~/.claude/hooks/issue_create_observer.py         (this file)
  ~/.claude/hooks/tests/test_issue_create_observer.py
"""

from __future__ import annotations

import os
import re
import shlex
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirroring every sibling hook)

HOOK_NAME = "issue_create_observer"

# ---------------------------------------------------------------------------
# Label taxonomy (PURE data) — mirrors `.claude/oversight/board-steward.md`
# §2's RE-DERIVED-LIVE taxonomy for the ExampleApp AI board (2026-08-23):
# "Type" labels are UNPREFIXED (no `type:` convention exists on this board),
# `area:`/`difficulty:` ARE prefixed. Kept here as data, not hardcoded into
# any decision branch, so a different repo's roster can be recognized without
# a code change if this ever needs to become configurable — not built out
# now (observer-first; no second repo has asked for it), but the shape
# leaves that door open cheaply.
# ---------------------------------------------------------------------------

TYPE_LABELS = frozenset(
    {"bug", "enhancement", "feature", "chore", "epic", "documentation"}
)
AREA_PREFIX = "area:"
DIFFICULTY_PREFIX = "difficulty:"

_VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})


def _norm_label(label: str) -> str:
    """Lowercase + collapse internal whitespace after a prefix's colon, so
    `area: backend`, `area:backend`, and `Area:  Backend` all compare equal.
    Never raises."""
    try:
        s = label.strip().lower()
        if ":" in s:
            prefix, _, rest = s.partition(":")
            return f"{prefix.strip()}: {rest.strip()}"
        return s
    except Exception:
        return label or ""


def classify_labels(labels: list[str]) -> dict:
    """Which of the three label classes are present in `labels`. Pure.

    Returns {"type": bool, "area": bool, "difficulty": bool}.
    """
    has_type = False
    has_area = False
    has_difficulty = False
    for raw in labels or []:
        norm = _norm_label(raw)
        if norm in TYPE_LABELS:
            has_type = True
        if norm.startswith(AREA_PREFIX):
            has_area = True
        if norm.startswith(DIFFICULTY_PREFIX):
            has_difficulty = True
    return {"type": has_type, "area": has_area, "difficulty": has_difficulty}


def missing_pieces(priority: str | None, labels: list[str]) -> list[str]:
    """The list of missing quality-gate pieces for a `create` invocation:
    any subset of ``["priority", "type-label", "area-label",
    "difficulty-label"]``. Empty list means fully compliant. Pure.
    """
    out: list[str] = []
    if not priority or priority.strip() not in _VALID_PRIORITIES:
        out.append("priority")
    classes = classify_labels(labels)
    if not classes["type"]:
        out.append("type-label")
    if not classes["area"]:
        out.append("area-label")
    if not classes["difficulty"]:
        out.append("difficulty-label")
    return out


# ---------------------------------------------------------------------------
# Command classification — pure, tokenized argv per segment.
# ---------------------------------------------------------------------------

# Leading bare invoker words to strip before inspecting argv[0], and an
# ENV=val prefix — same convention as protected_board_guard._strip_leading_
# invokers / _lib._strip_prefix, duplicated locally (each gate module keeps
# its own copy of this tiny helper rather than sharing one; see
# protected_board_guard.py's identical duplication of the same idea for
# precedent — no shared-invoker-stripping helper exists in _lib today).
_LEADING_INVOKER_WORDS = ("env", "command")


def _strip_leading_invokers(argv: list[str]) -> list[str]:
    try:
        out = list(argv)
        changed = True
        while changed and out:
            changed = False
            if out[0] in _LEADING_INVOKER_WORDS:
                out = out[1:]
                changed = True
            out = _lib._strip_prefix(out)
        return out
    except Exception:
        return argv


def _is_gh(argv: list[str]) -> bool:
    if not argv:
        return False
    try:
        return argv[0].rsplit("/", 1)[-1] == "gh"
    except Exception:
        return False


def _is_gh_issue_sh(argv: list[str]) -> bool:
    if not argv:
        return False
    try:
        return argv[0].rsplit("/", 1)[-1] == "gh_issue.sh"
    except Exception:
        return False


# gh's own global flags that can appear BEFORE the subcommand/verb tokens —
# same shape as protected_board_guard._skip_gh_globals, duplicated locally
# for the same "each gate module owns its own copy" reason as the invoker
# stripper above.
_GH_GLOBAL_FLAGS_WITH_VALUE = {"--repo": True, "-R": True, "--hostname": True}


def _skip_gh_globals(argv: list[str]) -> list[str]:
    try:
        if not argv:
            return argv
        out = [argv[0]]
        i = 1
        n = len(argv)
        while i < n:
            tok = argv[i]
            takes_value = _GH_GLOBAL_FLAGS_WITH_VALUE.get(tok)
            if takes_value is None:
                for name in ("--repo=", "--hostname="):
                    if tok.startswith(name):
                        takes_value = "inline"
                        break
            if takes_value is True:
                i += 2
                continue
            if takes_value == "inline":
                i += 1
                continue
            break
        out.extend(argv[i:])
        return out
    except Exception:
        return argv


def _flag_values(argv: list[str], name: str) -> list[str]:
    """Every value of `--name value` in argv, in order — the SPACE FORM
    ONLY (fix-round 2, non-blocking finding 4). `~/.claude/scripts/
    gh_issue.sh` itself accepts `--priority`/`--label` ONLY as `--name
    value` (its flag-parsing loop is `--priority) PRIORITY="${2:-}"; shift
    2 ;;` / `--label) LABELS+=("${2:-}"); shift 2 ;;` — an `--name=value`
    token falls into its `-*) _die "unknown flag: $1"` catch-all and
    refuses the whole command). This observer used to ALSO recognize the
    `--name=value` form, which the two layers disagreeing about is itself
    a defect: a `gh_issue.sh create --priority=P2 ...` command is REFUSED
    by the real helper (nothing filed) but this observer would have
    classified it as a compliant, `--priority`-present create — the
    OPPOSITE of what actually happened. Narrowed to match the helper's own
    parser exactly, rather than widening the helper's arg loop to accept
    the `=` form (the smaller, more conservative fix — this module reads
    the shell command, it does not decide the helper's own contract).
    Never raises.
    """
    out: list[str] = []
    long_flag = "--" + name
    try:
        n = len(argv)
        i = 0
        while i < n:
            tok = argv[i]
            if tok == long_flag and i + 1 < n:
                out.append(argv[i + 1])
                i += 2
                continue
            i += 1
        return out
    except Exception:
        return out


def _flag_value(argv: list[str], name: str) -> str | None:
    vals = _flag_values(argv, name)
    return vals[0] if vals else None


def _is_gh_issue_create(argv: list[str]) -> bool:
    """True iff `argv` (already global-flag-skipped, gh-confirmed) is
    `gh issue create ...`."""
    return len(argv) >= 3 and argv[1] == "issue" and argv[2] == "create"


def _is_gh_issue_sh_create(argv: list[str]) -> bool:
    """True iff `argv` (gh_issue.sh-confirmed) is `gh_issue.sh create ...`."""
    return len(argv) >= 2 and argv[1] == "create"


# Redirect-target message for a bare `gh issue create` bypass (shape (a)) —
# built once as data so main()/observe() and tests share identical text.
_BARE_CREATE_REDIRECT_MSG = (
    "use `~/.claude/scripts/gh_issue.sh create --title ... --priority "
    "P0|P1|P2|P3 --label <type> --label 'area: <x>' --label 'difficulty: "
    "<x>' ...` instead of a bare `gh issue create` — it dedupe-checks, "
    "triages, and (per #5827) tracks the Priority + "
    "type/area/difficulty label classes this observer watches for."
)


def _evaluate_segment(seg_text: str) -> list[tuple[str, dict]]:
    """Evaluate ONE shell segment (raw text). Returns a list of (decision,
    detail) pairs to log — zero, one, or (in principle) more. Never raises;
    an untokenizable segment is handled by the caller (observe()), not here.
    """
    try:
        argv = shlex.split(seg_text)
    except ValueError:
        return []
    if not argv:
        return []
    argv = _strip_leading_invokers(argv)
    if not argv:
        return []

    if _is_gh(argv):
        skipped = _skip_gh_globals(argv)
        if _is_gh_issue_create(skipped):
            return [
                (
                    "bare-issue-create",
                    {"command": seg_text[:500], "redirect": _BARE_CREATE_REDIRECT_MSG},
                )
            ]
        return []

    if _is_gh_issue_sh(argv):
        if _is_gh_issue_sh_create(argv):
            priority = _flag_value(argv, "priority")
            labels = _flag_values(argv, "label")
            missing = missing_pieces(priority, labels)
            if missing:
                return [
                    (
                        "create-missing-triage-would-deny",
                        {
                            "command": seg_text[:500],
                            "missing": missing,
                            "priority": priority,
                        },
                    )
                ]
        return []

    return []


# Heuristic hint for an UNTOKENIZABLE segment that still carries the textual
# shape of a `gh issue create` or `gh_issue.sh create` invocation — mirrors
# protected_board_guard._looks_like_add_shape's own raw-text fallback, but
# (per this module's fail-AMBIGUOUS, never fail-CLOSED, contract) this is
# ONLY ever used to decide whether to log `create-observer-ambiguous`, never
# to deny anything.
_AMBIGUOUS_HINT_RE = re.compile(
    r"\bgh\b.*\bissue\b.*\bcreate\b|\bgh_issue\.sh\b.*\bcreate\b",
    re.IGNORECASE | re.DOTALL,
)


def _looks_like_create_shape(seg_text: str) -> bool:
    try:
        return bool(_AMBIGUOUS_HINT_RE.search(seg_text))
    except Exception:
        return False


def observe(command: str) -> list[tuple[str, dict]]:
    """PURE core: given a raw Bash command string, return the list of
    (decision, detail) pairs this observer would log. Never blocks (there is
    no block return shape at all), never raises (any internal error
    degrades to an empty list — a missed observation is harmless; this
    module is purely informational, matching churn_tracker's own contract).
    """
    try:
        if not command or not command.strip():
            return []
        out: list[tuple[str, dict]] = []
        for seg in _lib._split_segments(command):
            if not seg.strip():
                continue
            try:
                shlex.split(seg)
            except ValueError:
                if _looks_like_create_shape(seg):
                    out.append(
                        ("create-observer-ambiguous", {"command": seg[:500]})
                    )
                continue
            out.extend(_evaluate_segment(seg))
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Thin main() — read event, observe, log every entry, exit 0. Never emits a
# PreToolUse deny (see module docstring: this is what keeps
# check_safety_core_parity.py from classifying this as an unwired guard).
# ---------------------------------------------------------------------------


def main() -> int:
    if _lib.disabled():
        return 0
    try:
        ev = _lib.read_event()
        if _lib.tool_name(ev) != "Bash":
            return 0
        command = _lib.bash_command(ev)
        where = _lib.cwd(ev)
        enforce = _lib.enforcing(where)
        for decision, detail in observe(command):
            _lib.log(HOOK_NAME, decision, enforce=enforce, **detail)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
