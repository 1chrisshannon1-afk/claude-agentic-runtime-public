#!/usr/bin/env python3
"""model_pin_gate — the FIRST real enforcement point for `knowledge/model_policy.json`'s
``agent_pins``.

WHY THIS EXISTS
---------------
``model_pin_parity.py`` has exactly one reader anywhere: itself, as a report-only
sweep. Nothing gates a dispatch at the moment it happens — an explicit
``tool_input.model`` override on a ``Task`` call always won client-side (per
``sdk-tools.d.ts``'s ``AgentInput.model`` taking precedence over agent-file
frontmatter), so a "pin" has never actually bound anything. All 18 historical
below-pin ``code-reviewer`` dispatches carried an explicit override; most
self-describe as CLAUDE.md §10's sanctioned "trivial-tier cheaper confirmatory
pass", but at least 4 verified are not (their real pathspecs classify
``moderate`` under ``review_risk_tier.py``). So this gate does not blanket-deny
an off-pin dispatch — it discriminates a SANCTIONED downgrade from a real
violation using the repo's own existing classifier (``review_risk_tier.py``),
never the caller's self-report, via a minted, single-use, TTL'd exception token
(see ``record_model_exception.py``).

DECISION TREE (implemented in this exact order — see ``decide()``):
  1. ``subagent_type == "fork"``                              -> ALLOW.
  2. ``model`` present and equals the resolved pin            -> ALLOW.
  3. ``model`` absent and the agent's OWN file has a pin      -> ALLOW.
  4. ``model`` absent and no agent file exists for this type  -> DENY pin-inherit-drift.
  5. type unpinned anywhere (no file, no policy entry)        -> ALLOW iff model
                                                                  explicit, else
                                                                  DENY unpinned-agent-type.
  6. ``model`` present and differs from the resolved pin      -> spend a valid,
                                                                  DISPATCH-BOUND
                                                                  exception token
                                                                  or an operator
                                                                  grant file, else
                                                                  DENY
                                                                  pin-tier-mismatch.
  7. an agent file exists but carries NO frontmatter pin      -> DENY
                                                                  missing-pin-in-file
                                                                  unless ``model``
                                                                  explicit.

"Resolved pin" prefers the agent's OWN ``agents/<name>.md`` frontmatter pin
(what the CLIENT will actually apply once ``model`` is absent — decision 3's
own rule: "frontmatter will win client-side") over the policy's ``agent_pins``
entry, falling back to the latter only when no agent file governs the type at
all. The agent-file source is now the UNION of this runtime's own
``~/.claude/agents/*.md`` roster AND the CURRENT REPO's own
``<repo_root>/.claude/agents/*.md`` roster (repo root resolved via
``git rev-parse --show-toplevel`` against the dispatch's own ``cwd``) — a
still-repo-local product-domain agent (e.g. ExampleApp's
``trade-tile``) is genuinely governed by ITS OWN frontmatter pin, exactly as
the real Claude Code client resolves it (project-level agent file wins over
the user-level one — CLAUDE.md's own preamble, "priority 3" in the docs), and
this gate must resolve the SAME pin the client will actually apply or it
denies a correct bare dispatch while permitting an incorrect explicit-model
one (the exact incident this fixes: a real ``trade-tile`` dispatch, pinned
``sonnet`` in its own repo-local file, was denied with ``pin: null`` on
2026-09-01T18:48:07Z because this gate only ever looked in
``~/.claude/agents/``). When both a runtime file and a repo-local file exist
for the same dispatch name, the repo-local one wins — mirroring the client's
own real precedence, not an arbitrary tie-break.

EXCEPTION TOKENS ARE NOW DISPATCH-BOUND, NOT JUST (agent_type, model)-BOUND.
A self-serve token minted by ``record_model_exception.py`` is minted against
the SHA-256 of the exact prompt text the caller is about to dispatch
(``--prompt-file``) and can only be spent by a ``Task`` call whose OWN
``tool_input.prompt`` hashes to that same digest — a token minted against one
dispatch's prompt (e.g. a README-only review) can no longer authorize a
DIFFERENT dispatch (e.g. a firestore.rules review) just because the
``(agent_type, model)`` pair happens to match. This closes B2 as tightly as
the real ``Task`` payload shape allows: see ``record_model_exception.py``'s
own module docstring for the residual limitation this does NOT close (the
``--paths`` argument used for the ``trivial-tier-confirmatory`` risk-tier
classification is still caller-asserted prose, not verified against what the
bound prompt text itself will actually touch).

``fable`` (2x Opus 5 pricing) can NEVER be authorized via a self-serve
exception token, for either reason (``trivial-tier-confirmatory`` or
``escalation-hard-debugging``) — enforced BOTH at mint time
(``record_model_exception.run()`` refuses outright) and, defense-in-depth, at
consumption time here (``find_and_consume_exception`` never even looks at the
token store when the target model is ``fable``). No agent_type is
resolved-pinned ``fable`` today (the standing pin below is retired) — the
ONLY path to any ``fable`` dispatch is the OPERATOR-GRANT file mechanism
below; nothing an agent's own Bash tool call can mint.

STANDING FABLE PIN — RETIRED (operator directive, 2026-09-24: "change all
models pinned to fable to be pinned to opus (5.5)"). From 2026-09-19 through
2026-09-24, ``marketing-director`` and ``plan-reviewer`` (the latter by
OPERATOR RULING 2026-09-20, ExampleApp OPERATOR_DECISIONS.md card
[87], ACCEPTED, after a same-day trust-architect narrowing back to opus,
BLOCKER B1) carried a genuine standing ``agent_pins`` pin of ``"fable"``. Both
seats are now pinned ``"opus"`` in ``agent_pins`` and in their own
frontmatter; ``sync_agent_rules.FABLE_AGENTS`` is empty. A ``model: "fable"``
dispatch of either seat today is an ORDINARY below-pin dispatch: it hits
decision 6 and is DENIED (``pin-tier-mismatch``/mismatch reason) unless the
operator mints a real operator-grant file for that specific dispatch —
exactly the same path every other never-fable agent_type has always used.
Nothing in this module's own code changed for this retirement — the standing
pin lived entirely in ``model_policy.json``'s ``agent_pins`` and the agents'
own frontmatter, and removing it there is what moved both seats back under
the ordinary decision tree; this paragraph is kept (rather than deleted) as
the historical record of why a bare or explicit-fable dispatch of either
seat was briefly an on-pin ALLOW, and to make clear that shape no longer
holds. ``launch-director`` was, and remains, excluded from ever carrying a
standing fable pin: it runs an UNATTENDED schedule, and
``model_policy.json``'s ``session_rules.no_unattended_opus_loops`` forbids a
fable default for an unattended loop a fortiori. That rule was never a bar
to a sanctioned Opus agent running unattended at the ordinary opus tier —
``launch-director`` itself runs unattended on ``opus`` with no override of
any kind — so plan-reviewer's return to ``opus`` needs no exception at all;
card [87]'s override was needed only for the fable tier, which sits above
what the rule already permits.

OPERATOR-GRANT FILES (closes B1). ``record_model_exception.py`` no longer has
an ``operator-directed`` reason at all — that reason read
``CSA_MODEL_EXCEPTION=1`` from the SAME process environment the invoking
agent's own Bash tool call controls, which is not a genuine human gate (the
``block_branch_ops.ESCAPE_VAR`` analogy it was modeled on is a PreToolUse
HOOK reading the session's own LAUNCH environment, which an agent's
individual Bash call cannot set; a CLI script reading whatever env that same
Bash call sets inline is not the same thing at all). The real operator-only
mechanism is ``~/.claude/scripts/grant_model_exception.sh`` — a standalone
script the OPERATOR runs directly in their own terminal (never referenced by
any agent-facing hook/denial message, never documented as agent-invokable),
which writes a short-TTL (default 30 min), single-use grant file into
``~/.claude/.model_exceptions/operator_grant_<agent>_<model>_<ts>.json``.
``find_and_consume_operator_grant`` (below) consumes it the same atomic,
single-use way the self-serve token store is consumed (B4) — the two stores
share the SAME atomic-claim helper, ``_consume_first_match``, differing only
in which files they scan and what they match against.

FAIL-OPEN CONTRACT (mirrors ``precommit_review_gate.py``'s "degrades open,
always" verbatim): an unreadable ``model_policy.json``, an unreadable
``agents/`` directory, an unparseable payload, or any other unanticipated
shape ALLOWS and logs a warning under this module's own hook name. A
governance-tooling outage must never wedge a dispatch — this gate blocks ONLY
on a confident, positive finding from data it could actually read. The
repo-local agents directory is treated DIFFERENTLY from the runtime one: its
absence (most repos have no ``.claude/agents/`` at all) is NOT a fail-open
trigger — it just means no repo-local pin is available, exactly like "this
repo has no local roster" is not itself a governance failure.

``decide()`` is a PURE function returning ``(block, reason, detail)``,
identical in shape to ``precommit_review_gate.decide()``, so
``pretooluse_task.py`` (gate T1) can wrap it into the same ``_Block`` idiom
``pretooluse_bash.py`` already uses for every other gate. Enforcement
(log-only vs. real deny) is applied by the CALLER via ``_lib.enforcing()``,
matching every other gate in this hook system — this module never decides
that for itself, and never emits anything on its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirrors every sibling hook)
import agent_budget as ab  # noqa: E402  (reuses admission_lock -- the SAME atomic-claim
# idiom file_claims.py already established for exactly this problem, see B4)
import model_pin_parity as mpp  # noqa: E402  (reuses frontmatter_name/frontmatter_model,
# and CLIENT_BUILTIN_CATCHALL_TYPES -- so the two modules' understanding of "which
# agent_type names have no home to pin in even in principle" can never drift apart)

HOOK_NAME = "model_pin_gate"

FORK_TYPE = "fork"

REASON_MISMATCH = "pin-tier-mismatch"
REASON_INHERIT_DRIFT = "pin-inherit-drift"
REASON_UNPINNED = "unpinned-agent-type"
# New, B3's "Also fix" bullet: a real on-disk agent file with NO frontmatter
# model pin at all used to fail OPEN (allow silently) -- literally "an agent
# not pinned to a specific model," the exact case CLAUDE.md's own governance
# language exists to catch. Now DENIES unless an explicit model is given.
REASON_MISSING_PIN_IN_FILE = "missing-pin-in-file"

DEFAULT_AGENTS_DIR = os.path.join(_lib.CLAUDE_DIR, "agents")
DEFAULT_POLICY_PATH = os.path.join(_lib.CLAUDE_DIR, "knowledge", "model_policy.json")
# The exception-token store record_model_exception.py mints into and this
# module consumes from. A sibling of .agent_budget/.file_claims/.review_state
# — same "dotdir under ~/.claude" convention every other hook ledger uses.
# ALSO holds the operator-grant files (OPERATOR_GRANT_PREFIX below) -- same
# directory, disjoint filename shapes, so both stores self-heal/expire via
# the identical consumption path (_consume_first_match).
DEFAULT_EXCEPTIONS_DIR = os.path.join(_lib.CLAUDE_DIR, ".model_exceptions")
GRANTS_LOG_NAME = "grants.jsonl"

# Single-use exception TTL — 15 minutes, per spec: long enough to mint then
# immediately dispatch, short enough that a stale, unconsumed token cannot
# quietly authorize an unrelated LATER dispatch of the same (agent, model) pair.
EXCEPTION_TTL_SECONDS = 15 * 60

# Filename prefix for an OPERATOR-minted grant file (B1) -- written ONLY by
# scripts/grant_model_exception.sh, run directly by the operator in their own
# terminal, never by any agent tool grant. Disjoint from the uuid4-hex
# filenames record_model_exception.py's mint_token() uses for self-serve
# tokens, so the two stores can share one directory and one consumption
# helper (_consume_first_match) without ever mismatching a file for the
# wrong store.
OPERATOR_GRANT_PREFIX = "operator_grant_"
OPERATOR_GRANT_DEFAULT_TTL_SECONDS = 30 * 60

# Bounded, non-blocking lock timeout for the atomic single-use consumption
# critical section (B4) -- same DEFAULT_LOCK_TIMEOUT class of value
# agent_budget.admission_lock's own callers use elsewhere in this hook
# system (file_claims.py's try_claim_paths, agent_budget's own admission
# path): short enough that a wedged/missing lock degrades to best-effort
# unsynchronized consumption (see _consume_first_match) rather than ever
# blocking a dispatch.
EXCEPTION_LOCK_TIMEOUT_SECONDS = 2.0

# The one model this policy is NEVER legitimately pinned to for a self-serve
# exception, regardless of reason or stated direction (B5) -- 2x Opus 5
# pricing, and model_pin_parity.py's own `unsanctioned-fable-dispatch` check
# flags every fable dispatch by design. A single source of truth so
# record_model_exception.py's mint-time refusal and this module's
# consumption-time refusal can never independently drift on what "fable"
# even means.
FABLE_MODEL = "fable"

# Relative cost/capability ordering used ONLY to verify an escalation-
# hard-debugging exception is genuinely upward (record_model_exception.py).
# "fable" sits above "opus" per model_pin_parity.py's own precedent comment
# (2x Opus 5 pricing) — kept here, not duplicated, so both modules agree.
TIER_ORDER: dict[str, int] = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def format_ts(dt: datetime) -> str:
    """UTC timestamp in this module's on-disk format — public because
    record_model_exception.py (which mints token records this module reads)
    must format its own ``minted_at``/``expires_at`` fields identically."""
    return dt.strftime(_TS_FMT)


def parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, _TS_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# Env var gating the (expensive -- full-transcript-read) parent-tier lookup
# for a fork dispatch's informational log line only (see decision 1 in
# decide()). Never gates the ALLOW itself -- forks always allow regardless.
VERBOSE_FORK_LOGGING_VAR = "CSA_MODEL_PIN_GATE_VERBOSE"


def _verbose_fork_logging_enabled() -> bool:
    return os.environ.get(VERBOSE_FORK_LOGGING_VAR, "") == "1"


# ---------------------------------------------------------------------------
# Pin resolution — pure, reused verbatim by record_model_exception.py so the
# gate and the minting tool can never disagree about what a type's pin is.
# ---------------------------------------------------------------------------


def load_pins(policy_path: str) -> dict[str, str] | None:
    """``agent_pins`` from ``model_policy.json``, or None if unreadable/
    malformed. None (never {}) is the fail-open signal — an empty-but-valid
    policy is never a realistic state this runtime is in, so it is treated
    the same as unreadable (matches model_pin_parity.check()'s own
    "policy-unreadable" verdict for an empty/missing mapping)."""
    try:
        with open(policy_path, encoding="utf-8") as fh:
            data = json.load(fh)
        pins = data.get("agent_pins")
        if not isinstance(pins, dict) or not pins:
            return None
        return {
            k: v for k, v in pins.items() if isinstance(k, str) and isinstance(v, str)
        }
    except Exception:
        return None


def scan_agent_pins(agents_dir: str) -> dict[str, str | None] | None:
    """dispatch-identity name -> frontmatter model pin (None when the file
    carries no pin) for every ``agents/*.md`` file. Returns None (never {})
    only when the directory itself cannot be listed — distinct from a real,
    empty roster, which is a valid (if strange) state. Dispatch identity is
    the frontmatter ``name:``, falling back to the filename stem — the exact
    convention ``model_pin_parity.check()`` already uses, reused via
    ``mpp.frontmatter_name``/``mpp.frontmatter_model`` rather than
    re-implementing the same regex a second time."""
    try:
        files = sorted(
            f
            for f in os.listdir(agents_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
    except Exception:
        return None
    out: dict[str, str | None] = {}
    for fname in files:
        try:
            with open(os.path.join(agents_dir, fname), encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            continue
        stem = fname[: -len(".md")]
        name = mpp.frontmatter_name(text) or stem
        out[name] = mpp.frontmatter_model(text)
    return out


def resolved_pin(
    subagent_type: str, pins: dict[str, str], agent_file_pins: dict[str, str | None]
) -> str | None:
    """The pin that actually governs ``subagent_type``: its own agent file's
    frontmatter pin when the file exists AND carries one (what the client
    actually applies — decision 3's rule), else the policy's ``agent_pins``
    entry, else None (genuinely unpinned anywhere). ``agent_file_pins`` is
    expected to already be the MERGED runtime+repo-local dict (see
    ``merged_agent_file_pins`` below) — this function itself is agnostic to
    where the dict came from, so the gate/mint tool can never disagree about
    what a type's pin is regardless of which roster(s) actually govern it."""
    if subagent_type in agent_file_pins:
        file_pin = agent_file_pins[subagent_type]
        if file_pin:
            return file_pin
    return pins.get(subagent_type)


# ---------------------------------------------------------------------------
# Repo-local agent roster (B3) — a still-repo-local product-domain agent
# (e.g. ExampleApp's `trade-tile`) is genuinely governed by its OWN
# `<repo_root>/.claude/agents/<name>.md` frontmatter pin, exactly as the real
# client resolves it. Without this, EVERY repo-local agent type was denied on
# a correct bare dispatch (decision 4: "no agent file exists anywhere") and
# permitted on ANY explicit model (decision 5: "genuinely ungoverned" ==
# "any model is fine") — confirmed in production 2026-09-01T18:48:07Z.
# ---------------------------------------------------------------------------

_GIT_TOPLEVEL_TIMEOUT_SEC = 5


def repo_root_for_cwd(cwd: str | None) -> str | None:
    """``git rev-parse --show-toplevel`` for ``cwd``, or None on ANY failure
    (no cwd, not a git repo, git unavailable, timeout). Never raises — mirrors
    ``precommit_review_gate._git``'s own subprocess idiom (bounded timeout,
    ``capture_output``, exit-code check) rather than inventing a new one."""
    if not cwd or not isinstance(cwd, str):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_GIT_TOPLEVEL_TIMEOUT_SEC,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return root or None


def merged_agent_file_pins(
    agents_dir: str, cwd: str | None
) -> dict[str, str | None] | None:
    """The runtime roster (``scan_agent_pins(agents_dir)``) UNIONED with the
    current repo's own ``<repo_root>/.claude/agents/*.md`` roster, when one
    can be resolved and exists — repo-local entries WIN on a name collision,
    mirroring the real client's own project-over-user precedence (CLAUDE.md's
    preamble, "priority 3").

    Returns None ONLY when the runtime roster itself is unreadable (the
    existing ``agents-dir-unreadable`` fail-open trigger, unchanged) — an
    absent/unreadable REPO-LOCAL directory is never a fail-open trigger; it
    just contributes nothing (most repos have no ``.claude/agents/`` at all,
    and that is not a governance failure). Never raises."""
    runtime_pins = scan_agent_pins(agents_dir)
    if runtime_pins is None:
        return None
    merged = dict(runtime_pins)
    repo_root = repo_root_for_cwd(cwd)
    if repo_root:
        repo_agents_dir = os.path.join(repo_root, ".claude", "agents")
        repo_pins = scan_agent_pins(repo_agents_dir)
        if repo_pins:
            merged.update(repo_pins)
    return merged


# ---------------------------------------------------------------------------
# Dispatch-prompt binding (B2) — the exact SHA-256 of the pending Task call's
# own `tool_input.prompt`, used to bind a self-serve exception token to the
# ONE dispatch it was minted for (see the module docstring's "EXCEPTION
# TOKENS ARE NOW DISPATCH-BOUND" section for what this does and does not
# close).
# ---------------------------------------------------------------------------


def dispatch_prompt_hash(tool_input: dict) -> str:
    """SHA-256 hex digest of ``tool_input["prompt"]`` (empty string when
    absent/non-string — a malformed/missing prompt hashes to a fixed,
    reproducible value that will simply never match a real minted token,
    the safe direction). Never raises."""
    prompt = tool_input.get("prompt") if isinstance(tool_input, dict) else None
    prompt = prompt if isinstance(prompt, str) else ""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Exception-token store — minted by record_model_exception.py, consumed here.
# Operator-grant store — minted by scripts/grant_model_exception.sh, consumed
# here too. Both share ONE atomic single-use consumption core (B4).
# ---------------------------------------------------------------------------


def _consume_first_match(
    exceptions_dir: str,
    now: datetime,
    *,
    name_ok: Callable[[str], bool],
    matches: Callable[[dict], bool],
) -> dict | None:
    """Shared atomic single-use consumption core for BOTH the self-serve
    exception-token store and the operator-grant store — identical shape,
    differing only in which files are scanned (``name_ok``) and what a
    candidate record must satisfy (``matches``).

    ATOMICITY (closes B4 — the pre-fix version had a read-then-remove TOCTOU:
    ``os.remove()``'s outcome was caught-and-discarded, so a LOSING racer
    still returned the token as consumed, measured at 4/30 double-spends
    under 2 concurrent consumers). Two layers, matching the established
    idiom this hook system already uses for exactly this class of problem
    (``file_claims.try_claim_paths``'s own ``ab.admission_lock`` critical
    section):
      1. The entire scan-match-remove pass runs inside
         ``ab.admission_lock(exceptions_dir)`` — a bounded, non-blocking
         ``flock`` critical section — so only one process at a time is even
         attempting a claim.
      2. Independently of (1) — belt-and-suspenders, since ``admission_lock``
         itself fails OPEN on an unacquirable lock (matching its own
         documented contract) — the ``os.remove()`` call on the matched
         file's own OUTCOME is now the actual single-use claim signal: on
         POSIX, concurrent ``unlink()`` calls on the same path are
         serialized by the kernel, so at most ONE caller's ``os.remove()``
         can ever succeed; every other caller gets ``FileNotFoundError`` and
         is treated as "lost the race, no match" — NOT as "consumed it
         anyway" (which is exactly the bug this replaces).

    Returns None when no unexpired, matching candidate is claimed by THIS
    call (including: the directory doesn't exist yet, is unreadable, every
    candidate is expired/malformed, or a match was found but lost the
    removal race to a concurrent caller). Never raises.

    Opportunistically prunes any EXPIRED file it scans past, matching every
    other ledger in this hook system's self-healing convention
    (``agent_budget.prune_and_count``).

    A missing/unreadable directory (or an unacquirable lock) is NOT a
    fail-open case: it degrades to "no match found", which leads the caller
    to DENY (the conservative direction) — never to ALLOW. Only a genuine
    policy/agents-dir read failure elsewhere in ``decide()`` fails open
    toward ALLOW.
    """
    with ab.admission_lock(exceptions_dir, timeout_s=EXCEPTION_LOCK_TIMEOUT_SECONDS):
        try:
            names = sorted(os.listdir(exceptions_dir))
        except Exception:
            return None
        for name in names:
            if not name_ok(name):
                continue
            path = os.path.join(exceptions_dir, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            expires_at = parse_ts(data.get("expires_at"))
            if expires_at is None or expires_at <= now:
                # Malformed or expired -- self-heal by removing it. Never a
                # candidate match either way (missing/garbage expiry is
                # treated as already-expired, the safe direction).
                try:
                    os.remove(path)
                except Exception:
                    pass
                continue
            if not matches(data):
                continue
            # THE atomic claim signal (see docstring point 2 above): only a
            # caller whose OWN os.remove() actually succeeds may treat this
            # as consumed. A losing racer's exception is NOT swallowed into
            # "still valid" -- it is treated as "someone else already spent
            # this", and the scan continues to the next candidate rather
            # than returning a token nobody actually holds anymore.
            try:
                os.remove(path)
            except FileNotFoundError:
                continue
            except Exception:
                continue
            return data
    return None


def find_and_consume_exception(
    exceptions_dir: str, subagent_type: str, model: str, prompt_hash: str, *,
    now: datetime | None = None,
) -> dict | None:
    """The first valid, unexpired SELF-SERVE token matching
    ``(subagent_type, model, prompt_hash)``, consumed (its file deleted) as
    an atomic, single-use side effect (see ``_consume_first_match``).

    ``prompt_hash`` (B2) is the SHA-256 of the PENDING dispatch's own
    ``tool_input.prompt`` (``dispatch_prompt_hash``) — a token now only
    matches the ONE dispatch it was minted against, not merely the same
    ``(agent_type, model)`` pair. This closes the incident that motivated
    B2: a token minted against a README-only review's prompt text is no
    longer usable to authorize a firestore.rules review that happens to
    share the same agent_type and model.

    ``model == FABLE_MODEL`` is a hard, unconditional refusal (B5,
    defense-in-depth): this store is NEVER even scanned for a fable target,
    regardless of what any token on disk might (illegitimately) claim —
    ``record_model_exception.run()`` already refuses to MINT one, but a
    gate-side check costs nothing and closes the gap for any token that
    somehow exists anyway (a hand-crafted file, a future minting bug).
    fable is reachable ONLY via ``find_and_consume_operator_grant`` below.
    """
    if model == FABLE_MODEL:
        return None
    now = now or datetime.now(timezone.utc)
    return _consume_first_match(
        exceptions_dir,
        now,
        name_ok=lambda n: n.endswith(".json") and not n.startswith(OPERATOR_GRANT_PREFIX),
        matches=lambda d: (
            d.get("agent_type") == subagent_type
            and d.get("model") == model
            and d.get("prompt_sha256") == prompt_hash
        ),
    )


def find_and_consume_operator_grant(
    exceptions_dir: str, subagent_type: str, model: str, *, now: datetime | None = None
) -> dict | None:
    """The first valid, unexpired OPERATOR-GRANT file matching
    ``(subagent_type, model)``, consumed atomically and single-use exactly
    like ``find_and_consume_exception`` (same ``_consume_first_match`` core).

    Deliberately NOT dispatch-prompt-bound (unlike the self-serve store):
    an operator grant is a trusted, out-of-band HUMAN decision made in their
    own terminal, not a caller self-report an agent could game — the TTL
    (default 30 min) plus single-use consumption is the bound, matching the
    trust level the operator's own action already carries. This is the ONLY
    path that can ever authorize a ``fable`` target (B1/B5) — no reason
    string, no direction check, nothing self-serve.
    """
    now = now or datetime.now(timezone.utc)
    return _consume_first_match(
        exceptions_dir,
        now,
        name_ok=lambda n: n.startswith(OPERATOR_GRANT_PREFIX) and n.endswith(".json"),
        matches=lambda d: d.get("agent_type") == subagent_type and d.get("model") == model,
    )


# ---------------------------------------------------------------------------
# Parent-tier lookup for the pin-inherit-drift message (decision 4).
# ---------------------------------------------------------------------------


def _parent_model_from_transcript(transcript_path: object) -> str | None:
    """The most recent assistant record's ``message.model`` in the parent
    session's transcript, or None on ANY failure (no path, unreadable file,
    no assistant record with a model). Mirrors
    ``agent_budget.sum_transcript_tokens``'s own full-file-read convention
    for transcript JSONL rather than a true reverse-seek tail — consistent
    with the one other place this hook system reads a transcript file.
    Never raises."""
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return None
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        message = obj.get("message")
        if isinstance(message, dict):
            model = message.get("model")
            if isinstance(model, str) and model:
                return model
    return None


# ---------------------------------------------------------------------------
# The gate itself.
# ---------------------------------------------------------------------------


def decide(
    ev: dict,
    *,
    agents_dir: str | None = None,
    policy_path: str | None = None,
    exceptions_dir: str | None = None,
    now: datetime | None = None,
) -> tuple[bool, str, dict]:
    """(block, reason, detail) for a pending ``Task``/``Agent`` dispatch.
    NEVER raises — every unexpected shape degrades to ALLOW (see the module
    docstring's fail-open contract).

    Defense in depth: this checks the global ``CSA_DISABLE_HOOKS=1`` kill
    switch itself (mirroring every other hook's master-off, even though the
    normal call path — ``pretooluse_task.py`` — already checks it before
    ever calling in) so a direct caller of ``decide()`` gets the same
    guarantee without needing to know that.
    """
    try:
        if _lib.disabled():
            return (False, "", {})

        agents_dir = agents_dir or DEFAULT_AGENTS_DIR
        policy_path = policy_path or DEFAULT_POLICY_PATH
        exceptions_dir = exceptions_dir or DEFAULT_EXCEPTIONS_DIR

        ti = ev.get("tool_input")
        ti = ti if isinstance(ti, dict) else {}
        subagent_type = ti.get("subagent_type")
        subagent_type = subagent_type if isinstance(subagent_type, str) else ""
        model = ti.get("model")
        model = model if isinstance(model, str) and model else None

        # Decision 1: forks ignore `model` entirely per the SDK -- documented
        # client behavior, not a loophole to close here; a fork ALWAYS
        # allows regardless of parent tier, so parent_model is never
        # decision-relevant here, only informational. "Also fix" (2026-09-01
        # fix round): the transcript read behind `parent_model` is a
        # full-file read of the WHOLE session transcript
        # (_parent_model_from_transcript), measured up to 87 MB on a real
        # long-running session -- doing that unconditionally on EVERY fork
        # dispatch just to log a non-decision-relevant field is wasted I/O.
        # Only pay for it when CSA_MODEL_PIN_GATE_VERBOSE=1 is explicitly
        # set; otherwise log the fork-allow with parent_model omitted.
        if subagent_type == FORK_TYPE:
            parent_model = None
            if _verbose_fork_logging_enabled():
                parent_model = _parent_model_from_transcript(ev.get("transcript_path"))
            _lib.log(
                HOOK_NAME,
                "fork-allow",
                subagent_type=subagent_type,
                parent_model=parent_model,
            )
            return (False, "", {})

        pins = load_pins(policy_path)
        if pins is None:
            _lib.log(
                HOOK_NAME,
                "fail-open",
                reason="policy-unreadable",
                policy_path=policy_path,
            )
            return (False, "", {})

        # B3: the runtime roster (~/.claude/agents/) UNIONED with the current
        # repo's own repo-local roster, when one resolves -- see
        # merged_agent_file_pins' own docstring. Only the RUNTIME side's
        # unreadability fails open; an absent/unreadable repo-local dir just
        # contributes nothing.
        agent_file_pins = merged_agent_file_pins(agents_dir, _lib.cwd(ev))
        if agent_file_pins is None:
            _lib.log(
                HOOK_NAME,
                "fail-open",
                reason="agents-dir-unreadable",
                agents_dir=agents_dir,
            )
            return (False, "", {})

        has_file = subagent_type in agent_file_pins
        file_pin = agent_file_pins.get(subagent_type) if has_file else None
        pin = resolved_pin(subagent_type, pins, agent_file_pins)

        # Decision 2: explicit model matches the resolved pin.
        if model and pin and model == pin:
            return (False, "", {})

        # Decision 3: model absent, and the agent's OWN file carries a pin --
        # frontmatter wins client-side, nothing to gate.
        if model is None and has_file and file_pin:
            return (False, "", {})

        # Decision 4: model absent, no agent file at all for this type (every
        # catch-all: general-purpose, execute, dispatch, ultracode,
        # workflow-subagent, claude-code-guide, Explore, Plan, claude).
        if model is None and not has_file:
            parent_model = _parent_model_from_transcript(ev.get("transcript_path"))
            return (
                True,
                REASON_INHERIT_DRIFT,
                {
                    "subagent_type": subagent_type,
                    "pin": pin,
                    "parent_model": parent_model,
                },
            )

        # Decision 5: genuinely ungoverned type (no file, no policy entry) --
        # the still-repo-local product-domain agents plus kb-verifier/"".
        # NOTE: the `model is None` half of this condition is unreachable in
        # practice (decision 4 already caught every "no file" + "model
        # absent" case above) -- kept anyway per the spec's own belt-and-
        # suspenders ordering, and it is exercised directly by unit tests
        # that call decide() with a hand-built partial state.
        if subagent_type not in pins and not has_file:
            if model:
                return (False, "", {})
            return (True, REASON_UNPINNED, {"subagent_type": subagent_type})

        # Decision 6: explicit model differs from the resolved pin -- spend a
        # valid, DISPATCH-BOUND (B2) self-serve exception token, or (for
        # anything a self-serve token can never cover, e.g. fable -- B5) a
        # single-use operator-grant file (B1), else deny.
        if model and pin and model != pin:
            prompt_hash = dispatch_prompt_hash(ti)
            exc = find_and_consume_exception(
                exceptions_dir, subagent_type, model, prompt_hash, now=now
            )
            if exc is not None:
                _lib.log(
                    HOOK_NAME,
                    "exception-consumed",
                    subagent_type=subagent_type,
                    model=model,
                    reason=exc.get("reason"),
                    paths=exc.get("paths"),
                    risk_tier_verdict=exc.get("risk_tier_verdict"),
                )
                return (False, "", {})
            grant = find_and_consume_operator_grant(
                exceptions_dir, subagent_type, model, now=now
            )
            if grant is not None:
                _lib.log(
                    HOOK_NAME,
                    "operator-grant-consumed",
                    subagent_type=subagent_type,
                    model=model,
                    granted_at=grant.get("granted_at"),
                )
                return (False, "", {})
            return (
                True,
                REASON_MISMATCH,
                {"subagent_type": subagent_type, "model": model, "pin": pin},
            )

        # Decision 7 (B3's "Also fix" bullet): an on-disk agent file exists
        # for this type but carries NO frontmatter model pin at all --
        # literally "an agent not pinned to a specific model." Previously
        # failed OPEN (allowed silently); now DENIES unless an explicit
        # model is given, mirroring decision 4's own "pass an explicit
        # model" remedy. `client_builtin` (reused from model_pin_parity's
        # own CLIENT_BUILTIN_CATCHALL_TYPES, never re-defined here) is
        # always False on this path in practice -- those three types never
        # have a file to begin with (they hit decision 4 instead) -- carried
        # anyway so the two modules' understanding of "which types have no
        # home to pin in even in principle" can never silently diverge.
        if has_file and not file_pin:
            if model:
                return (False, "", {})
            parent_model = _parent_model_from_transcript(ev.get("transcript_path"))
            return (
                True,
                REASON_MISSING_PIN_IN_FILE,
                {
                    "subagent_type": subagent_type,
                    "pin": pin,
                    "parent_model": parent_model,
                    "client_builtin": subagent_type in mpp.CLIENT_BUILTIN_CATCHALL_TYPES,
                },
            )

        # Fallthrough: a shape this tree genuinely didn't anticipate (every
        # named decision above is now exhaustive for the reachable
        # (has_file, file_pin, pin, model) combinations -- see the module
        # docstring's decision tree). A governance-tooling problem, not a
        # caller violation -- fail open, matching every other unreadable-
        # state branch above.
        _lib.log(
            HOOK_NAME,
            "fail-open",
            reason="undetermined",
            subagent_type=subagent_type,
            model=model,
            pin=pin,
        )
        return (False, "", {})
    except Exception:
        return (False, "", {})


def message_for(reason: str, detail: dict) -> str:
    """Operator/agent-facing denial text for a given (reason, detail)."""
    tail = " See ~/.claude/.enforcement/log.jsonl."
    if reason == REASON_MISMATCH:
        subagent_type = detail.get("subagent_type")
        model = detail.get("model")
        pin = detail.get("pin")
        fable_clause = (
            f" '{model}' can NEVER be minted self-serve (see below) — this requires an "
            "operator-run grant, not a token." if model == FABLE_MODEL else ""
        )
        return (
            f"{HOOK_NAME}: BLOCKED ({REASON_MISMATCH}) — dispatching '{subagent_type}' on "
            f"model '{model}' but its policy pin is '{pin}'.{fable_clause} Either drop the "
            "explicit model override (the pin applies automatically) or mint a governed, "
            "DISPATCH-BOUND exception first (write the exact prompt text you are about to "
            "dispatch to a scratch file, then):\n  python3 "
            "~/.claude/hooks/record_model_exception.py --agent "
            f"{subagent_type} --model {model} --reason "
            "<trivial-tier-confirmatory|escalation-hard-debugging> --paths <pathspec...> "
            "--prompt-file <path-to-the-exact-prompt-text>\nFor a target this cannot mint "
            "(fable, or an escalation whose source pin isn't sonnet), only the OPERATOR can "
            "authorize it, by running "
            "~/.claude/scripts/grant_model_exception.sh themselves in their own terminal — "
            "an agent's own Bash tool call cannot substitute for that." + tail
        )
    if reason == REASON_INHERIT_DRIFT:
        subagent_type = detail.get("subagent_type")
        pin = detail.get("pin")
        parent_model = detail.get("parent_model")
        tier_clause = f" (currently {parent_model})" if parent_model else ""
        if pin:
            body = (
                f"{subagent_type} has no agent file, so it inherits the parent session's "
                f'model{tier_clause}. Its policy pin is {pin}. Pass model: "{pin}" '
                "explicitly on the dispatch."
            )
        else:
            body = (
                f"{subagent_type} has no agent file and no policy pin on record, so it "
                f"inherits the parent session's model{tier_clause} with no governance at "
                "all. Pass an explicit, appropriately cheap model on the dispatch."
            )
        return f"{HOOK_NAME}: BLOCKED ({REASON_INHERIT_DRIFT}) — {body}" + tail
    if reason == REASON_UNPINNED:
        subagent_type = detail.get("subagent_type")
        return (
            f"{HOOK_NAME}: BLOCKED ({REASON_UNPINNED}) — '{subagent_type}' has no "
            "agents/*.md file and no agent_pins entry, and no explicit model was passed "
            "on the dispatch. Pass an explicit model." + tail
        )
    if reason == REASON_MISSING_PIN_IN_FILE:
        subagent_type = detail.get("subagent_type")
        pin = detail.get("pin")
        parent_model = detail.get("parent_model")
        tier_clause = f" (currently {parent_model})" if parent_model else ""
        pin_clause = (
            f" model_policy.json's own agent_pins says '{pin}' -- pass model: \"{pin}\" "
            "explicitly."
            if pin
            else " No policy pin exists for it either -- pass an explicit, appropriately "
            "cheap model."
        )
        return (
            f"{HOOK_NAME}: BLOCKED ({REASON_MISSING_PIN_IN_FILE}) — '{subagent_type}' has "
            f"an agents/*.md file on disk, but it carries NO frontmatter model: pin (already "
            "separately flagged by model_pin_parity.py's own 'missing-pin' verdict — fix the "
            f"file too, not just this dispatch), so it would silently inherit the parent "
            f"session's model{tier_clause} with no real governance.{pin_clause}" + tail
        )
    return f"{HOOK_NAME}: BLOCKED ({reason})." + tail


def main() -> int:
    """Manual/direct CLI entry point (reads a Task/Agent event from stdin).

    NOT the normal call path — pretooluse_task.py imports decide()/
    message_for() directly and applies its own enforcing()/logging exactly
    like pretooluse_bash.py does for its sibling gate modules. This exists
    for manual invocation/debugging, mirroring every sibling gate module's
    own `main()`. Always exits 0 — a deny is via the printed JSON object,
    never a nonzero exit.
    """
    if _lib.disabled():
        return 0
    ev = _lib.read_event()
    block, reason, detail = decide(ev)
    where = _lib.cwd(ev)
    enforce = _lib.enforcing(where)
    _lib.log(
        HOOK_NAME,
        "would-block" if block else "allow",
        reason=reason,
        enforce=enforce,
        **detail,
    )
    if block and enforce:
        _lib.emit_pretooluse_deny(message_for(reason, detail))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
