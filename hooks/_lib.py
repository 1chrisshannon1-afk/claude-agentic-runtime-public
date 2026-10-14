"""Shared library for the Python hook system (~/.claude/hooks/).

All hook modules import from this file. It is deliberately small, dependency-free
(stdlib only), and 100%-testable. Every public function degrades OPEN: it never
raises out to a caller, because a crashing hook must never break the agent.

Ported faithfully from the proven bash implementations:
  * ~/.claude/scripts/git_guard.sh   — tokenizer, enforce resolver, deny emission
  * ~/.claude/scripts/review-gate.sh  — Stop block emission, enforce resolver
  * ~/.claude/scripts/agent_budget.sh — enforcement log path

SHARED LIB CONTRACT (see the spawning task):
  read_event() -> dict
  tool_name(ev) -> str
  bash_command(ev) -> str
  cwd(ev) -> str
  session_id(ev) -> str
  disabled() -> bool
  enforcing(cwd=None) -> bool
  emit_pretooluse_deny(msg) -> None
  emit_stop_block(reason) -> None
  log(hook, decision, **fields) -> None
  git_segments(command) -> list[list[str]]
  (+ enforcement path module constants)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Enforcement paths — module constants (mirror the bash scripts exactly).
# ---------------------------------------------------------------------------

HOME = os.path.expanduser("~")
CLAUDE_DIR = os.path.join(HOME, ".claude")

# Global master-OFF is an env var (CSA_DISABLE_HOOKS); global-ON is a marker file.
GLOBAL_ENFORCE_FILE = os.path.join(CLAUDE_DIR, ".enforce")
# Per-project opt-in marker, found by walking up from cwd to the repo root.
PROJECT_ENFORCE_MARKER = os.path.join(".claude", ".csa-enforce")

# Structured decision log (JSONL, append-only).
ENFORCEMENT_DIR = os.path.join(CLAUDE_DIR, ".enforcement")
LOG_FILE = os.path.join(ENFORCEMENT_DIR, "log.jsonl")

# Review-gate state (used by the review-gate hook module, path lives here so all
# modules share one source of truth).
REVIEW_STATE_DIR = os.path.join(CLAUDE_DIR, ".review_state")
LAST_REVIEWED = os.path.join(REVIEW_STATE_DIR, "last_reviewed")
# Commit-authorship ledger (see commit_authors.py): maps (repo, sha) -> the
# session_id that committed it. While task_completion_gate.py was live
# (RETIRED 2026-08-20) this let its Stop gate scope its warn/block to the
# COMMITTING session only; that consumer is gone, the recording is kept.
# Lives alongside last_reviewed so both ledgers share REVIEW_STATE_DIR's
# admission.lock.
COMMIT_AUTHORS = os.path.join(REVIEW_STATE_DIR, "commit_authors")

# Agent-budget lease ledger.
AGENT_BUDGET_DIR = os.path.join(CLAUDE_DIR, ".agent_budget")

# File-claim ledger (path-scoped commit contest tracking; see file_claims.py).
FILE_CLAIMS_DIR = os.path.join(CLAUDE_DIR, ".file_claims")

# Churn ledger (per-path commit-thrash observation; see churn_tracker.py).
CHURN_DIR = os.path.join(CLAUDE_DIR, ".churn")


def _now() -> str:
    """UTC timestamp, matching the bash `date -u +%Y-%m-%dT%H:%M:%SZ`."""
    try:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # pragma: no cover - clock failures are unreachable
        return "unknown"


# ---------------------------------------------------------------------------
# Event parsing — read_event never raises; returns {} on any error.
# ---------------------------------------------------------------------------


def read_event() -> dict:
    """Parse the hook JSON payload from stdin.

    Returns the decoded dict, or {} on ANY error (no stdin, garbage bytes,
    non-dict JSON, decode failure). Never raises — a broken payload must not
    crash the hook.
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    return _parse_event(raw)


def _parse_event(raw: str) -> dict:
    """Decode a raw JSON string into an event dict; {} on any failure.

    Split out from read_event() so tests can exercise the parser without
    monkeypatching stdin.
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def tool_name(ev: dict) -> str:
    """The tool_name field ("Bash", "Task", ...), or "" if absent/non-str."""
    try:
        v = ev.get("tool_name", "")
    except Exception:
        return ""
    return v if isinstance(v, str) else ""


def tool_use_id(ev: dict) -> str:
    """The tool_use_id of this tool invocation, or "" if absent/non-str.

    This id is unique PER tool call and (per the Claude Code hook contract) is
    carried by both PreToolUse and PostToolUse/SubagentStop for the same call, so
    it is the correlation key an admission controller uses to pair a claim at
    spawn with a release at finish. Unique-per-invocation is essential: two
    concurrent sub-agents of the SAME type must not collapse onto one lease.
    """
    try:
        v = ev.get("tool_use_id", "")
    except Exception:
        return ""
    return v if isinstance(v, str) else ""


def bash_command(ev: dict) -> str:
    """The Bash tool's command string, or "" if absent/non-str.

    Mirrors git_guard.sh: reads d["tool_input"]["command"].
    """
    try:
        ti = ev.get("tool_input", {})
    except Exception:
        return ""
    if not isinstance(ti, dict):
        return ""
    v = ti.get("command", "")
    return v if isinstance(v, str) else ""


def session_id(ev: dict) -> str:
    """The session id from a hook payload, or "nosession" when absent/blank.

    Checks "session_id" then "sessionId" (both spellings appear across the
    Claude Code hook payload shapes), matching
    task_completion_gate._session_id's exact semantics (that RETIRED module's
    own version is a thin alias for this one, dormant but unchanged) so every
    caller agrees on exactly the same session identity. A sub-agent's payload
    carries the SAME session_id as its parent session (no separate identity),
    so commit_authors.py naturally attributes a sub-agent's commit to the
    parent session. Never raises: a non-string value or a `.get()` that
    raises both degrade to "nosession".
    """
    try:
        v = ev.get("session_id") or ev.get("sessionId") or ""
    except Exception:
        return "nosession"
    return v if isinstance(v, str) and v else "nosession"


def cwd(ev: dict) -> str:
    """The working directory the hook fired in.

    Prefers the payload's "cwd" then "project_dir" (matching review-gate.sh),
    falling back to os.getcwd() when the payload carries neither.
    """
    try:
        v = ev.get("cwd") or ev.get("project_dir") or ""
    except Exception:
        v = ""
    if isinstance(v, str) and v:
        return v
    try:
        return os.getcwd()
    except Exception:  # pragma: no cover - getcwd failing is unreachable
        return ""


def subagent_type(ev: dict) -> str:
    """The dispatched agent type from a ``Task`` hook payload, or "" when absent.

    Reads ``tool_input.subagent_type``, the SAME field
    ``agent_budget._gate_spend_row`` and ``model_pin_gate.decide`` already
    read (agent_budget.py:970, model_pin_gate.py:623-624) — defined in one
    place here so every caller agrees on exactly the same agent identity.

    PAYLOAD ASYMMETRY (telemetry plan §4.2 4a, round-3 R9): this field exists
    ONLY on a ``Task`` payload. A ``PreToolUse:Bash`` payload describes a
    shell command, not a dispatch, so it has no agent type at all and callers
    on that side must never fabricate one. Never raises: a non-dict
    ``tool_input``, a non-string value, or a ``.get()`` that raises all
    degrade to "".
    """
    try:
        ti = ev.get("tool_input", {})
    except Exception:
        return ""
    if not isinstance(ti, dict):
        return ""
    v = ti.get("subagent_type", "")
    return v if isinstance(v, str) else ""


# ---------------------------------------------------------------------------
# Enforcement resolution.
# ---------------------------------------------------------------------------


def disabled() -> bool:
    """True when the master OFF switch CSA_DISABLE_HOOKS=1 is set."""
    return os.environ.get("CSA_DISABLE_HOOKS", "") == "1"


def enforcing(cwd: str | None = None) -> bool:
    """Resolve whether enforcement is ON.

    Precedence (ported from git_guard.sh / review-gate.sh `_enforce_on`):
      1. If disabled() (CSA_DISABLE_HOOKS=1) -> False  (master OFF wins).
      2. env CSA_ENFORCE=1                    -> True.
      3. global marker file ~/.claude/.enforce exists -> True.
      4. walking up from `cwd` (default: current dir): the first ancestor that
         is a repo (has a .git entry) that ALSO has a sibling
         .claude/.csa-enforce marker -> True. The walk stops at the first .git
         it finds (matching the bash `break`).
      5. otherwise -> False.
    """
    if disabled():
        return False
    if os.environ.get("CSA_ENFORCE", "") == "1":
        return True
    try:
        if os.path.isfile(GLOBAL_ENFORCE_FILE):
            return True
    except Exception:
        pass
    return _project_enforced(cwd)


def _project_enforced(start: str | None) -> bool:
    """Walk up from `start` looking for a repo root with the opt-in marker.

    Mirrors the bash loop: stop at the first ancestor containing a `.git`
    entry; enforcement is ON only if that same directory also has
    `.claude/.csa-enforce`.
    """
    d = start
    if not d:
        try:
            d = os.getcwd()
        except Exception:  # pragma: no cover
            return False
    try:
        d = os.path.abspath(d)
    except Exception:  # pragma: no cover
        return False
    while d and d != os.path.dirname(d):  # stop at filesystem root
        try:
            if os.path.exists(os.path.join(d, ".git")):
                marker = os.path.join(d, PROJECT_ENFORCE_MARKER)
                return os.path.isfile(marker)
        except Exception:  # pragma: no cover
            return False
        d = os.path.dirname(d)
    return False


# ---------------------------------------------------------------------------
# Canonical hook-output emitters.
# ---------------------------------------------------------------------------


def emit_pretooluse_deny(msg: str) -> None:
    """Print the canonical PreToolUse deny object (git_guard.sh `_emit_deny`).

    ``permissionDecisionReason`` carries the SAME text as ``systemMessage`` —
    deliberately. ``systemMessage`` is what the operator sees; the reason field
    is what the denied AGENT sees. Before 2026-08-27 only the former was set,
    so every gate routed through here surfaced to the agent as the generic
    "Hook PreToolUse:Bash denied this tool" — an unattended loop could not tell
    "gate 3b, go get a review" from "gate 4, another agent holds these paths,
    wait", and the leg-4b headless probe (#4415) recorded OTHER-GATE for a
    denial the hook itself had made. ``no_artifact.py`` always set both.
    """
    obj = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        },
        "systemMessage": msg,
    }
    print(json.dumps(obj))


def emit_stop_block(reason: str) -> None:
    """Print the canonical Stop-hook block object."""
    print(json.dumps({"decision": "block", "reason": reason}))


# ---------------------------------------------------------------------------
# Structured decision log — append one JSON line; never raises.
# ---------------------------------------------------------------------------

# Kill-switch for the identity fields ONLY (telemetry plan §4.2 4a). Set
# CSA_NO_LOG_IDENTITY=1 and log() writes exactly the rows it wrote before the
# identity change landed — every other field, and the row itself, is
# unaffected. Named and read the same way every other operator rollback lever
# in this hook system is (cf. file_claims.mutex_enabled's CSA_NO_COMMIT_MUTEX,
# precommit_review_gate's CSA_NO_PRECOMMIT_REVIEW): a bare env-var read,
# default OFF (identity ON).
IDENTITY_KILL_SWITCH = "CSA_NO_LOG_IDENTITY"

# The sentinel session_id() returns when a payload carries no session. Plan
# §4.2 4a: "When session_id returns the 'nosession' sentinel, OMIT the field —
# never write it." A sentinel written into the ledger would be indistinguishable
# from a real session id at read time and would silently corrupt any
# per-session aggregation.
NO_SESSION_SENTINEL = "nosession"


def log_identity_enabled(environ: dict | None = None) -> bool:
    """False iff CSA_NO_LOG_IDENTITY=1 — the operator rollback lever for the
    session/agent_type/repo identity fields on enforcement rows. True
    (identity ON) is the default. Pure w.r.t. everything else log() writes.
    """
    env = os.environ if environ is None else environ
    try:
        return env.get(IDENTITY_KILL_SWITCH, "") != "1"
    except Exception:  # pragma: no cover - a mapping whose .get raises
        return True


def _identity_fields(
    session: str | None, agent_type: str | None, repo: str | None
) -> dict:
    """The identity sub-record for one log row. PURE and total — never raises,
    so the fail-open contract of log() itself is preserved by construction
    (this is the only new logic on log()'s hot path).

    Omission rules, each deliberate:
      * None            -> omitted. This is the ONLY absence signal, and it is
                           why `identity_or_none()` exists: a caller that has
                           no such fact normalizes to None BEFORE calling, so
                           this function never has to guess whether a given ""
                           means "unresolved" or "the caller really wants an
                           empty string in the row".
      * "nosession"     -> omitted for `session` specifically (plan §4.2 4a).
                           The sentinel is not a session id; writing it would be
                           indistinguishable from a real one at read time.
      * anything else   -> written VERBATIM, including "". Backward
                           compatibility is why: several pre-existing call
                           sites already pass `repo=` (record_review.py:2321,
                           record_plan_review.py:209, pretooluse_bash.py:1228)
                           and `agent_type=` (record_model_exception.py:397),
                           and two of those can legitimately be "" —
                           `record_review.Decision.repo_root` defaults to ""
                           (record_review.py:311) and reaches log() on the
                           not-a-dir/not-a-repo branches, and
                           record_plan_review's `no-outcome` branch fires
                           exactly when its target is falsy. Those kwargs now
                           bind to this function's explicit parameters instead
                           of landing in **fields, so dropping "" here would
                           silently change rows that predate this change.
                           It does not.
    """
    out: dict = {}
    try:
        if session is not None and session != NO_SESSION_SENTINEL:
            out["session"] = session
        if agent_type is not None:
            out["agent_type"] = agent_type
        if repo is not None:
            out["repo"] = repo
    except Exception:  # pragma: no cover - the guards above cannot raise
        return {}
    return out


def identity_or_none(value: str) -> str | None:
    """Normalize an accessor's result for `log()`'s identity kwargs: "" (every
    accessor in this module's own absence signal — see `cwd`, `subagent_type`)
    becomes None so the field is OMITTED rather than written empty; a non-str
    also becomes None (defensive: write no field rather than a garbage one).

    Entry points call this; legacy call sites do not, which is exactly how an
    intentional `repo=""` from an older caller survives while an unresolved
    repo root from a new one is omitted. Never raises.
    """
    try:
        return value if isinstance(value, str) and value else None
    except Exception:  # pragma: no cover - the guard above cannot raise
        return None


def log(
    hook: str,
    decision: str,
    *,
    session: str | None = None,
    agent_type: str | None = None,
    repo: str | None = None,
    **fields,
) -> None:
    """Append one JSON line to ~/.claude/.enforcement/log.jsonl.

    Always mkdir -p first. Best-effort: any failure (unwritable dir, unencodable
    field) is swallowed — logging must never break a hook.

    IDENTITY (telemetry plan §4.2 4a / §4.2a, 2026-09-05). `session`,
    `agent_type` and `repo` are EXPLICIT optional kwargs rather than plain
    `**fields` entries so the two `PreToolUse` entry points that actually
    parse a payload (`pretooluse_bash.main`, `pretooluse_task.main`) have one
    named, typed contract to thread identity through — and so the omission
    rules below live in exactly one place instead of at each call site. The
    rejected alternatives are recorded in the plan: threading `ev` through all
    93 existing call sites, and a module-level context global (mutable state
    in a fail-open path).

    All three default to None and are OMITTED from the row when absent, so a
    call passing none of them produces a byte-identical record to the one it
    produced before this change — the backward-compatibility guarantee every
    existing call site relies on. `_identity_fields` documents each omission
    rule; the "nosession" one is required by the plan.

    Several pre-existing call sites already pass `repo=` / `agent_type=`
    (record_review.py, record_plan_review.py, record_model_exception.py, and
    pretooluse_bash.py's `churn-flagged` row). Those kwargs now bind to these
    explicit parameters instead of landing in `**fields`. That is
    OBSERVATIONALLY INERT by construction: `_identity_fields` omits only None
    and the session sentinel, so every value a legacy caller passes —
    including the "" that `record_review.Decision.repo_root` and
    `record_plan_review`'s no-outcome branch can genuinely produce — is
    written exactly as before. New callers normalize through
    `identity_or_none()` instead, which is what turns an UNRESOLVED fact into
    an omitted field.

    Identity is written BEFORE the caller's `**fields` are applied, so any
    same-named entry a future caller puts in `**fields` still wins.
    """
    try:
        os.makedirs(ENFORCEMENT_DIR, exist_ok=True)
    except Exception:
        return
    record = {
        "ts": _now(),
        "hook": hook,
        "decision": decision,
        # enforcing() is the single source of truth for whether a real deny
        # can happen (CSA_ENFORCE=1, the global ~/.claude/.enforce marker, OR
        # a per-project opt-in) -- this used to read raw CSA_ENFORCE only, so
        # every log line lied `enforce: false` under global/project-marker
        # enforcement while a real deny was actually happening elsewhere
        # (2026-08-25, churn_phase0_measure.md step 4). No cwd is available
        # in this function's own signature; enforcing()'s no-arg default
        # (os.getcwd()) is the same fallback the deny path at
        # pretooluse_bash.py's _finish (enforcing(where)) would reduce to
        # here, absent an event to read a real cwd from.
        "enforce": enforcing(),
    }
    # Identity (plan §4.2 4a). Applied BEFORE the caller's **fields so an
    # explicit same-named field in **fields would still win, and wrapped so a
    # telemetry failure can never cost the row itself — this whole block
    # degrading to "no identity fields" is the designed failure mode.
    try:
        if log_identity_enabled():
            record.update(_identity_fields(session, agent_type, repo))
    except Exception:
        pass
    # Caller-supplied fields override nothing structural but add detail.
    for k, v in fields.items():
        record[k] = v
    try:
        line = json.dumps(record, default=str)
    except Exception:
        # Last-resort minimal line — never fail because a field was unencodable.
        line = json.dumps({"ts": _now(), "hook": hook, "decision": decision})
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        return


# ---------------------------------------------------------------------------
# Git tokenizer — ported EXACTLY from git_guard.sh's python tokenizer.
#
# git_segments() returns the list of git argv segments found in a (possibly
# compound) shell command. Each returned entry is the git command's argv AFTER
# leading ENV=val stripping, starting at the argv0 whose basename == "git"
# (i.e. ["git", <subcommand>, ...]). Non-git segments are dropped. This is the
# shared primitive the git-guard hook module builds its BLOCK/ALLOW decision on;
# it reproduces the segmentation + prefix-strip the proven bash guard performs.
# ---------------------------------------------------------------------------


def _is_ascii_alpha(c: str) -> bool:
    """True iff `c` is exactly one ASCII letter (`A-Za-z`) — never Unicode-aware.

    Deliberately NOT `str.isalpha()`: that method is Unicode-aware (e.g.
    'é'.isalpha() is True in Python), which would treat a non-ASCII letter
    as part of a longer word and let a git-adjacent accented character slip
    the boundary check the mandated ASCII regex would have denied (e.g.
    "égit" — see `_raw_mentions_git`'s docstring). Matches the exact
    character class the ported regex `(^|[^A-Za-z])git([^A-Za-z]|$)` uses.
    """
    return ("A" <= c <= "Z") or ("a" <= c <= "z")


def _raw_mentions_git(raw: str) -> bool:
    """Whole-word 'git' detection in a raw string (no JSON/shell parse).

    Matches `(^|[^A-Za-z])git([^A-Za-z]|$)` — the bare token 'git' surrounded
    by non-ASCII-alpha characters (or the string's own edges), via
    `_is_ascii_alpha` above rather than `str.isalpha()` (which is
    Unicode-aware and would make this predicate diverge from the ASCII regex
    it claims to match — see that helper's own docstring). `isalpha`, not
    `isalnum`: '.git', '.git/config', '_git', 'git2' all match (their
    git-adjacent character is non-ASCII-alpha); '.gitignore', 'github',
    'legitimate', 'digit' do not (the character right after/before "git" is
    itself an ASCII letter, so it's part of a longer word, not the
    standalone token).

    This is the single shared implementation for every fail-closed "does
    this untokenizable text carry a real git invocation" check in the hook
    chain (ported here 2026-08-30, #4670 item 3b, from
    block_branch_ops.py, which now re-exports this exact function rather
    than duplicating it — see that module's own `_raw_mentions_git`).
    `git_segments()` below calls this directly on its own untokenizable-
    segment sentinel path so a substring match inside a longer word (e.g. a
    broken shell fragment that merely contains "digit") no longer trips the
    fail-closed sentinel the way the old bare-substring membership test
    (AA-0009, replaced 2026-08-30) used to.
    """
    if not raw:
        return False
    n = len(raw)
    idx = 0
    while True:
        pos = raw.find("git", idx)
        if pos == -1:
            return False
        before_ok = pos == 0 or not _is_ascii_alpha(raw[pos - 1])
        after = pos + 3
        after_ok = after >= n or not _is_ascii_alpha(raw[after])
        if before_ok and after_ok:
            return True
        idx = pos + 1


# Round-2 review NIT (2026-09-05): an UNQUOTED bare identifier after `<<`
# also matches a bitshift operator inside `$(( ... ))`/`(( ... ))`
# arithmetic (e.g. `$((x << y))`) -- confirmed exploitable: with no
# further guard, `echo $((x << y))\ngit checkout main` treats `y` as a
# heredoc delimiter and, since no line downstream is ever exactly `y`,
# consumes (and drops) EVERYTHING including the real trailing
# `git checkout main`, hiding it entirely. A real heredoc delimiter is
# never immediately followed by another expression character -- requiring
# whitespace, a quote, a control operator, or end-of-string right after
# the (optionally quoted) delimiter excludes the arithmetic-shift shape
# (`y))`, `y;`-inside-`(())`) while still matching every real heredoc form
# this module's own tests exercise (`<<EOF`, `<<'EOF'`, `<<-EOF ...`).
_HEREDOC_OPEN_RE = re.compile(
    r"<<-?\s*(?:(['\"])([A-Za-z_][A-Za-z0-9_]*)\1|([A-Za-z_][A-Za-z0-9_]*)(?=[\s;&|`\n]|$))"
)


def _split_segments(s: str) -> list[str]:
    """Split a shell command into segments on control operators, honoring quotes.

    Ported verbatim from git_guard.sh split_segments(): breaks on
    && || ; | & newline, and treats command-substitution / subshell /
    process-substitution openers ($(  `  <(  >(  (  ) ) as boundaries too, so a
    git state-verb hidden inside them becomes its own inspected segment.

    HEREDOC-AWARE (added 2026-09-05, workflow audit into gate-denial
    friction): a `<<'DELIM'`/`<<"DELIM"`/`<<DELIM` opener (outside quotes)
    starts a heredoc BODY that is DROPPED entirely -- never scanned for
    quotes or control operators, and never handed to `shlex.split` either
    -- through the line that is exactly DELIM (optionally tab-stripped for
    the `<<-` form). Without this, the body's own newlines were treated as
    ordinary segment boundaries, splitting a single heredoc into several
    fragments whose quote state no longer lines up -- confirmed to break
    the runtime's OWN recommended commit-message idiom (`git commit -F -
    <<'EOF' ... EOF`) the instant the message body contains an apostrophe
    (e.g. "contractor's bug"), which desyncs the artificial segment
    boundary and fails `shlex.split` -> `untokenizable-segment-with-git`,
    confirmed as this gate's single largest denial reason (measured
    2026-09-05: 214/786 denials, 7 days). A LITERAL body (quoted
    delimiter, `<<'EOF'`/`<<"EOF"`) is dropped outright: `shlex.split`
    has no concept of heredoc syntax at all, so even a correctly-scoped
    literal body handed to it would still fail to parse as flat argv --
    it is inert redirected INPUT, never part of any command's argv, so
    this gate never needed to see it either way. Only the heredoc's
    opener token stays in the segment, exactly where real shell argv-
    parsing would leave it -- surfacing as `<<EOF` after `shlex.split`
    strips the delimiter's own quotes (`<<-EOF` for the tab-stripping
    form), never the literal `<<'EOF'` text as originally written.

    An UNQUOTED delimiter (`<<EOF`) is a DIFFERENT case, corrected in
    round-3 review after this docstring's first version wrongly claimed a
    state verb "could not meaningfully hide inside a heredoc body either
    way" -- that is false for an unquoted delimiter: bash performs
    parameter/command/arithmetic expansion INSIDE such a body, so a
    `$(...)`/backtick/`${...}` there genuinely executes (confirmed live).
    A non-literal body is therefore never dropped -- it flows through
    this SAME character walk on the following pass, so a live
    substitution inside it still opens a real, inspected segment exactly
    as it would outside a heredoc. It also closes a related false-
    positive class the OLD (pre-this-module) code had in the OTHER
    direction: when a heredoc
    body happened to tokenize cleanly on its own (no unbalanced quotes),
    the old segmentation split it into its own real segment and
    `git_segments` would return any git-shaped TEXT inside that body
    (e.g. a body literally containing the line "git stash pop") as if it
    were a real, executable git invocation -- confirmed live: pre-fix,
    `block_branch_ops.decision()` denied `cat <<'EOF' > f\\ngit stash pop\\n
    EOF` as `state-verb:stash`, even though that text is redirected file
    content, never executed as a command.

    CORRECTNESS FIX (round-2 review, same day, BLOCKER): the FIRST version
    of this heredoc handling raw-appended the rest of the opener's own
    line -- and, on close, the whole closing-delimiter line -- WITHOUT
    running them through the normal control-operator/quote scan. That let
    a real state verb chained after `&&`/`;`/`|` on the opener's own line
    (`cat <<'EOF' > /tmp/x && git checkout main`) disappear into one
    unparseable segment, bypassing gate 1/2/3 entirely -- confirmed
    exploitable by direct pre/post execution. The heredoc opener is now
    detected DURING normal scanning (armed as a `pending_heredocs` queue,
    never by jumping the cursor ahead), so `&&`/`||`/`;`/`|`/backtick/
    parens on that SAME line still split segments exactly as they always
    did. Only the real newline that ends the opener's line triggers body
    consumption -- and only the body itself (never the opener's line, and
    never anything on/after the delimiter's own closing line) is dropped
    without scanning."""
    segs: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(s)
    q = None  # current quote char or None
    # Heredoc openers seen on the CURRENT line, queued in encounter order
    # (real shell supports multiple `<<A <<B` redirects on one line,
    # consumed body-first in that order) -- each is (delim, tab_strip,
    # literal). Armed during NORMAL scanning (so control operators/quotes
    # elsewhere on the same line are still scanned exactly as before --
    # round-2 review BLOCKER: an earlier draft raw-appended the rest of
    # the opener's line and the delimiter's trailing text without
    # scanning them, letting `cat <<'EOF' && git checkout main` or
    # `...\nEOF; git reset --hard` smuggle a real state verb past every
    # gate). Only ACTED ON when the walk reaches the newline that ends
    # the opener's line -- never by jumping ahead.
    #
    # LITERAL vs LIVE body (round-3 review BLOCKER, same day): a heredoc
    # body is only inert file content when its delimiter is QUOTED
    # (`<<'EOF'`/`<<"EOF"`). An UNQUOTED delimiter (`<<EOF`) makes bash
    # perform parameter/command/arithmetic expansion INSIDE the body --
    # `$(...)`/backticks/`${...}` there genuinely execute, confirmed live
    # (`cat <<EOF >/dev/null\n$(id -un >&2)\nEOF` prints the real
    # username to stderr). Dropping an unquoted body unscanned, as the
    # round-2 fix did, is therefore a real gate-1/2/3 bypass, not a safe
    # widening -- a LITERAL body may still be dropped outright (neither
    # `shlex` nor a state-verb check needs to see inert text), but a
    # non-literal one must flow through the SAME character walk as
    # everything else, so a `$(`/backtick/`${` inside it still opens a
    # real, inspected segment exactly as it would outside a heredoc.
    pending_heredocs: list[tuple[str, bool, bool]] = []
    while i < n:
        c = s[i]
        if q:
            buf.append(c)
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q = c
            buf.append(c)
            i += 1
            continue
        if c == "<" and s[i : i + 2] == "<<" and s[i : i + 3] != "<<<" and not (i > 0 and s[i - 1] == "<"):
            # `<<<word` is a HERE-STRING (a single-word literal piped in,
            # no body, no terminator line at all) -- a completely
            # different construct from a heredoc and must never be
            # treated as one. Cold-review BLOCKER (2026-09-05, round 4):
            # rejecting only `<<<` at THIS check is not enough on its
            # own -- when `_HEREDOC_OPEN_RE.match` correctly fails to
            # match `<<<word` (the regex itself already rejects it), the
            # outer walk falls through, appends one `<` character, and
            # advances by 1 -- so the NEXT iteration lands on the SECOND
            # `<` of the same `<<<`, where the remaining text is
            # `<<word`, a textbook heredoc opener that matches and arms.
            # Since a here-string has no body/terminator, the body-drop
            # loop then silently consumes the rest of the command,
            # hiding a real trailing git invocation entirely -- confirmed
            # exploitable end-to-end through the real gate chain
            # (`cat <<<word\ngit checkout main` denied pre-fix, ALLOWED
            # by the round-3 fix alone). The `not (i > 0 and s[i-1] ==
            # "<")` half above is what closes THIS retry path -- it
            # blocks the second `<`'s own attempt from ever re-arming.
            m = _HEREDOC_OPEN_RE.match(s, i)
            if m:
                delim = m.group(2) or m.group(3)
                literal = m.group(2) is not None
                pending_heredocs.append((delim, m.group(0).startswith("<<-"), literal))
                buf.append(s[i : m.end()])
                i = m.end()
                continue
        two = s[i : i + 2]
        if two in ("&&", "||", "$(", "<(", ">("):
            segs.append("".join(buf))
            buf = []
            i += 2
            continue
        if c == "\n" and pending_heredocs:
            # The opener's line has ended for real (scanned normally, not
            # jumped). A LITERAL body (every queued heredoc quoted) is
            # dropped outright, exactly as before: it is inert redirected
            # INPUT, never command argv, and `shlex.split` has no heredoc
            # concept to hand it to either way. A NON-LITERAL body (any
            # queued heredoc unquoted) is NEVER dropped -- fall through to
            # the normal walk instead, so a live `$(`/backtick/`${`
            # inside it still opens a real, inspected segment.
            #
            # KNOWN, DELIBERATELY UNFIXED IMPRECISION (round-4 cold
            # review nit, recorded so it is never mistaken for a fresh
            # bug): `all(...)` means TWO heredocs on one line
            # (`cat <<A <<'B'`) are judged together -- an unquoted `A`
            # forces BOTH bodies through the live-scan path even though
            # `B`'s own body (quoted) is genuinely inert in real bash.
            # This is a false POSITIVE (a quoted body's harmless text can
            # get surfaced as a segment, e.g. "git stash pop" typed in
            # B's inert body would now be wrongly flagged), never a false
            # negative -- it fails in the SAFE direction (more scanning,
            # never less), unlike every other bug this module has fixed
            # so far. Precise per-heredoc-in-order handling would need
            # real body consumption interleaved with re-entrant scanning,
            # which is more complexity than this rare multi-heredoc-per-
            # line shape has earned; left as a correctness footnote, not
            # a bug to chase.
            if all(literal for _delim, _tab_strip, literal in pending_heredocs):
                i += 1
                for delim, tab_strip, _literal in pending_heredocs:
                    while i < n:
                        line_end = s.find("\n", i)
                        line_end = n if line_end == -1 else line_end
                        line = s[i:line_end]
                        is_delim_line = line.strip("\t" if tab_strip else "") == delim
                        i = line_end + 1 if line_end < n else n
                        if is_delim_line:
                            break
                pending_heredocs = []
            else:
                # Non-literal: do NOT special-case the body at all --
                # clear the queue and let this newline (and every byte
                # after it, including the eventual delimiter line) fall
                # through to the plain-newline handling below, re-
                # entering the SAME outer walk one character at a time
                # like any other input. A live `$(`/backtick/`${` inside
                # the body is then caught by the identical control-
                # operator checks every other segment goes through; the
                # delimiter line itself just becomes its own harmless,
                # non-git segment (e.g. `['EOF']`) rather than being
                # specially recognized -- a real shell reader stops
                # heredoc mode there, but this gate doesn't need to
                # replicate that precisely, since text simply cannot be
                # both an inspected segment AND part of the surrounding
                # command's own argv here either way.
                pending_heredocs = []
                buf.append(c)
                i += 1
                continue
            # Whatever follows is a genuinely NEW statement in real shell
            # semantics (the newline right after the last closing
            # delimiter line is a real separator) -- close the segment
            # here rather than concatenating it onto the opener's own
            # tokens with no boundary (a real earlier bug: e.g.
            # `/tmp/notes.txtgit status` glued together with no
            # separator, which could hide a state verb in the FOLLOWING
            # statement rather than flag it).
            segs.append("".join(buf))
            buf = []
            continue
        if c in (";", "|", "&", "`", "(", ")"):
            segs.append("".join(buf))
            buf = []
            i += 1
            continue
        if c == "\n":
            segs.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    # Command ends mid-heredoc-opener-line (no newline at all after the
    # last `<<DELIM` -- e.g. the whole command IS just that one line) --
    # nothing left to drop; `buf` already holds everything real.
    segs.append("".join(buf))
    return [x for x in (seg.strip() for seg in segs) if x]


def _tokenize(seg: str):
    """shlex.split a segment; None signals an untokenizable (unbalanced) segment."""
    try:
        return shlex.split(seg)
    except Exception:
        return None


def _strip_prefix(tokens: list[str]) -> list[str]:
    """Drop leading ENV=val assignments (git_guard.sh strip_prefix()).

    A leading token is an assignment when it has no leading dash, contains '=',
    and its name part is an identifier (alphanumeric or underscore). GIT_DIR=x
    qualifies. The first non-assignment token ends the prefix.
    """
    idx = 0
    for t in tokens:
        if "=" in t and not t.startswith("-"):
            name = t.split("=", 1)[0]
            if name and all(ch.isalnum() or ch == "_" for ch in name):
                idx += 1
                continue
        break
    return tokens[idx:]


def _strip_git_globals(tokens: list[str]) -> list[str]:
    """Given tokens whose argv0 basename is 'git', drop the global option-args
    (-C DIR, -c k=v, --git-dir[=X], --work-tree[=X], --namespace[=X], and other
    leading global flags) and return ["git", <subcommand>, <subargs...>].

    Ported from git_guard.sh resolve_git_sub(), but returns the reconstructed
    git argv (with "git" at position 0 followed by subcommand + its args) so the
    public git_segments() contract yields a full git argv per segment. Returns
    an empty list when no subcommand token is found (bare `git`).
    """
    i = 1
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if t == "-C":
            i += 2
            continue
        if t == "-c":
            i += 2
            continue
        if t.startswith("--git-dir") or t.startswith("--work-tree") or t.startswith("--namespace"):
            if "=" in t:
                i += 1
            else:
                i += 2
            continue
        if t in (
            "--no-pager",
            "--paginate",
            "-p",
            "--bare",
            "--literal-pathspecs",
            "--no-optional-locks",
        ):
            i += 1
            continue
        if t.startswith("-c"):  # -ck=v form (rare)
            i += 1
            continue
        if t.startswith("-"):
            # unknown global flag; skip one token conservatively
            i += 1
            continue
        # tokens[i] is the subcommand; return git + subcommand + its args
        return ["git", t] + tokens[i + 1 :]
    return []


# Anchored on the RAW command text deliberately: _split_segments discards the
# joining operators ('cd /a && git…', 'cd /a; git…', 'cd /a || git…' and the
# subshell form all yield identical segment lists — verified by execution,
# 2026-09-07 plan review for #5061), so operator-aware cd detection CANNOT
# be built on the segment list. Only '&&' guarantees the cd succeeded before
# anything after it runs; every other join falls back to the event cwd.
_LEADING_CD_RE = re.compile(
    r'^\s*cd\s+((?:"[^"]*")|(?:\'[^\']*\')|(?:[^\s;|&<>]+))\s*&&\s*'
)


def _leading_cd_dir(command: str, cwd: str) -> str | None:
    """Directory established by leading `cd <dir> && ` prefix(es), or None.

    Consumes one or more leading `cd <literal> &&` prefixes from the RAW
    command text (multi-`cd`: last wins). Returns None — caller falls back to
    the event cwd, bit-for-bit today's behavior — whenever the prefix is
    absent or unsafe to interpret: a join other than `&&` (`;`, `||`, `&`),
    a leading subshell `(`, `cd -` (OLDPWD is unknowable here), or a dir
    token still containing `$` or a backtick after quote-stripping. `~` is
    expanded (deterministic for this process); a relative dir joins against
    `cwd`. A nonexistent dir is still returned: with `&&` the real shell runs
    nothing after the failed cd, and the caller's repo resolution then
    degrades to the no-repo path — an allow over a command that executes
    nothing (#5061, plan-reviewed 2026-09-07).
    """
    try:
        base = None
        rest = command
        while True:
            m = _LEADING_CD_RE.match(rest)
            if not m:
                break
            tok = m.group(1)
            if (tok.startswith('"') and tok.endswith('"')) or (
                tok.startswith("'") and tok.endswith("'")
            ):
                tok = tok[1:-1]
            if not tok or tok == "-" or "$" in tok or "`" in tok:
                return None
            tok = os.path.expanduser(tok)
            if not os.path.isabs(tok):
                tok = os.path.join(base or cwd or ".", tok)
            base = tok
            rest = rest[m.end():]
        # A-1 (dual-review regression): an UNCONSUMED `cd` after the last
        # `&&`-joined one means a mixed join follows (`cd /a && cd /b ; git…`)
        # — the real shell may end up in /b while `base` still says /a.
        # Returning the stale base would resolve a THIRD, wrong directory;
        # bail to the event-cwd fallback instead, keeping the docstring's
        # "non-&& joins fall back" promise true even mid-chain.
        if base is not None and re.match(r"\s*cd\s", rest):
            return None
        return base
    except Exception:
        return None


def effective_git_cwd(command: str, cwd: str) -> str:
    """The directory a `git` invocation in `command` actually targets.

    Two cross-repo shapes are honored, composing in this order:
    1. A leading `cd <dir> && ` prefix (see `_leading_cd_dir` — `&&`-joined
       literal dirs only; every unsafe shape falls back to `cwd`). Added for
       #5061: gates resolved the SESSION repo for cd-prefixed cross-repo
       commits, taking the wrong mutex/digest/authorship.
    2. `git -C <path>` on the FIRST git segment that carries it — a relative
       `-C` path resolves against the cd-prefix base (or `cwd`), and `-C`
       wins for the git segment when both are present.

    Falls back to the (possibly cd-adjusted) base on any git segment with no
    `-C`, no git segment at all, or any parse failure — never raises, never
    worse than the pre-existing behavior of always using `cwd` outright.
    """
    base = _leading_cd_dir(command, cwd)
    if base is None:
        base = cwd
    try:
        for seg in _split_segments(command):
            toks = _tokenize(seg)
            if not toks:
                continue
            toks = _strip_prefix(toks)
            if not toks:
                continue
            argv0 = toks[0]
            if argv0.rsplit("/", 1)[-1] != "git":
                continue
            i = 1
            while i < len(toks) - 1:
                if toks[i] == "-C":
                    path = toks[i + 1]
                    if not os.path.isabs(path):
                        path = os.path.join(base or ".", path)
                    return path
                i += 1
    except Exception:
        pass
    return base


def git_segments(command: str) -> list[list[str]]:
    """Tokenize a shell command into git argv segments.

    Returns a list of git argvs, one per segment of `command` that resolves to a
    git invocation. Each argv is ["git", <subcommand>, <subargs...>] with leading
    ENV=val assignments and git global options (-C, -c, --git-dir, ...) stripped,
    exactly as git_guard.sh does before it inspects the subcommand.

    Segments that are not git (argv0 basename != "git"), bare `git` with no
    subcommand, empty segments, or untokenizable segments that do NOT mention git
    as a whole word are omitted. An untokenizable segment that DOES mention git
    as a whole word (see `_raw_mentions_git` above — a boundary match, not a bare
    substring test) is surfaced as the sentinel ["git", "\\x00untokenizable"] so a
    caller enforcing fail-closed semantics can detect the ambiguity and block. A
    segment whose only "git"-like text is a substring
    inside a longer word (e.g. `echo 'legitimate value` — "git" only appears
    inside "legitimate") no longer trips the sentinel (fixed 2026-08-30, CSA
    #4670 item 3b; was a bare `"git" in seg` substring test before).

    Never raises: any unexpected error yields [].
    """
    if not command:
        return []
    try:
        result: list[list[str]] = []
        for seg in _split_segments(command):
            toks = _tokenize(seg)
            if toks is None:
                # Untokenizable segment. Only ambiguous if it mentions a real
                # git token — a whole-word match (see _raw_mentions_git
                # above), not a bare substring inside a longer word (e.g.
                # "digit", "legitimate").
                if _raw_mentions_git(seg):
                    result.append(["git", "\x00untokenizable"])
                continue
            if not toks:
                continue
            toks = _strip_prefix(toks)
            if not toks:
                continue
            argv0 = toks[0]
            base = argv0.rsplit("/", 1)[-1]  # basename of e.g. /usr/bin/git
            if base != "git":
                continue
            git_argv = _strip_git_globals(toks)
            if not git_argv:
                # bare `git` with no subcommand — nothing to inspect.
                continue
            result.append(git_argv)
        return result
    except Exception:
        return []
