#!/usr/bin/env python3
"""mint_prod_session — the SINGLE allowlisted gate for minting a prod live-test
secret/session from a named macOS Keychain item.

Ported faithfully from the proven bash wrapper:
    ~/.claude/scripts/get_test_secret.sh

SECURITY MODEL (unchanged from the bash source):
  The GLOBAL deny on  Bash(security find-generic-password:*)  and
  Bash(op item get:*)  STAYS. Only this wrapper is allowed to reach the keychain.
  It accepts exactly one Keychain item name and:
    * refuses any name containing shell/format-hostile characters,
    * refuses any name NOT matching an allowlisted prefix (csa-livetest-),
    * fetches  security find-generic-password -w -s "<name>"  ONLY for an
      allowlisted name,
    * emits the raw value to EXACTLY ONE destination (the "jar path": stdout),
      NEVER to the log, NEVER echoed with commentary,
    * NEVER logs, echoes, or persists the value on any error path.

The bash exit codes are the spec and are reproduced verbatim:
    0  ok        — value fetched; printed once to the jar path (stdout)
    2  usage     — no arg / empty name
    3  bad-name  — illegal characters, OR name not allowlisted (prefix miss)
    4  lookup    — keychain lookup failed (non-zero) or returned an empty value

STRUCTURE (per the hook-system contract):
  * decide(name) is a PURE function: name -> Decision(code, reason). It does the
    validation only (usage / illegal-chars / prefix). It never touches the
    keychain, never prints, never logs — trivially unit-testable.
  * fetch_secret(name) is the thin, side-effectful keychain call, isolated so the
    validation branches are tested WITHOUT invoking the real keychain (mock it).
  * main() wires stdin -> decide -> (fetch on OK) -> emit/log -> exit 0.

Like the rest of the hook system this module degrades OPEN: it is LOG-ONLY unless
enforcing(), honors the CSA_DISABLE_HOOKS master-off, and never raises out to the
caller. It always exits 0; a "deny" for this tool means: do NOT emit a value and
surface the reason via the canonical PreToolUse deny JSON (never via exit code).
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import NamedTuple, Optional

# Make `import _lib` work regardless of the pytest / invocation rootdir.
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already adds it under test
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after the sys.path shim)

HOOK = "mint_prod_session"

# The tool name this hook gates. The wrapper is surfaced to the agent as a
# dedicated tool/command; a PreToolUse event for anything else is a no-op.
TOOL_NAME = "mint_prod_session"

# Allowlisted item-name prefixes. Extend deliberately; keep tight. Mirrors the
# bash ALLOWED_PREFIXES=("csa-livetest-").
ALLOWED_PREFIXES = ("csa-livetest-",)

# The set of characters a keychain item name may contain. Anything else is
# rejected up front (defense in depth — we never interpolate the name into a
# shell string, but keep names clean anyway). Mirrors the bash
# case "$NAME" in *[!A-Za-z0-9._-]*) reject.
_ALLOWED_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")

# Exit-code / decision constants — the bash exit codes ARE the spec.
CODE_OK = 0
CODE_USAGE = 2
CODE_BAD_NAME = 3
CODE_LOOKUP = 4


class Decision(NamedTuple):
    """A pure validation verdict for a candidate keychain item name.

    code   — one of the CODE_* constants (mirrors the bash exit code).
    reason — a short, secret-free explanation (safe to log/emit).
    """

    code: int
    reason: str

    @property
    def ok(self) -> bool:
        return self.code == CODE_OK


# ---------------------------------------------------------------------------
# PURE decision function — validation only. No keychain, no I/O, no printing.
# ---------------------------------------------------------------------------


def _allowlisted(name: str) -> bool:
    """True iff `name` starts with one of the allowlisted prefixes."""
    return any(name.startswith(pre) for pre in ALLOWED_PREFIXES)


def decide(name: Optional[str]) -> Decision:
    """Validate a candidate Keychain item name. PURE — never touches the keychain.

    Reproduces get_test_secret.sh's guard order exactly:
      1. empty / missing name         -> CODE_USAGE   (bash exit 2)
      2. illegal characters in name   -> CODE_BAD_NAME (bash exit 3)
      3. name not allowlisted (prefix)-> CODE_BAD_NAME (bash exit 3)
      4. otherwise                    -> CODE_OK       (proceed to fetch)

    The char-check precedes the prefix-check, matching the bash `case` order (a
    name like "csa-livetest-x;y" is rejected as illegal-chars, not prefix).
    """
    if not name:
        return Decision(
            CODE_USAGE,
            "usage: mint_prod_session <keychain-item-name> "
            f"(name must start with one of: {' '.join(ALLOWED_PREFIXES)})",
        )
    if any(ch not in _ALLOWED_NAME_CHARS for ch in name):
        return Decision(CODE_BAD_NAME, "illegal characters in item name.")
    if not _allowlisted(name):
        return Decision(
            CODE_BAD_NAME,
            f"refused — '{name}' is not an allowlisted test secret. "
            f"Allowed prefixes: {' '.join(ALLOWED_PREFIXES)}",
        )
    return Decision(CODE_OK, "ok")


# ---------------------------------------------------------------------------
# Side-effectful keychain fetch — isolated so validation is tested without it.
# ---------------------------------------------------------------------------


class FetchResult(NamedTuple):
    """Outcome of a keychain lookup.

    ok    — True iff a non-empty value was retrieved.
    value — the secret value on success, else None. Callers MUST route this to
            the jar path (stdout) ONLY and never to the log.
    """

    ok: bool
    value: Optional[str]


def fetch_secret(name: str) -> FetchResult:
    """Run `security find-generic-password -w -s <name>` and capture the value.

    -w prints only the password value; -s selects by service name. We pass the
    name as an argv element (never string-interpolated into a shell), capture the
    output, and treat a non-zero return OR an empty value as a failure — matching
    the bash `[[ $_rc -ne 0 || -z "$VALUE" ]]` check.

    This is the ONLY function that shells out; every branch above it is pure.
    Never raises: any unexpected error is reported as a failed fetch.
    """
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", name],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return FetchResult(False, None)
    if proc.returncode != 0:
        return FetchResult(False, None)
    # -w emits the value plus a trailing newline; strip only the newline the tool
    # appends, so the jar receives exactly the stored value.
    value = proc.stdout
    if value.endswith("\n"):
        value = value[:-1]
    if not value:
        return FetchResult(False, None)
    return FetchResult(True, value)


# ---------------------------------------------------------------------------
# Value emission — the ONLY place a secret reaches an output, and only stdout.
# ---------------------------------------------------------------------------


def emit_value(value: str) -> None:
    """Write the raw secret to the jar path (stdout) EXACTLY once, no commentary.

    Mirrors the bash `printf '%s' "$VALUE"` — no trailing newline, nothing else.
    Consumers pipe this into a jar refresh. NEVER call log() with the value.
    """
    sys.stdout.write(value)


# ---------------------------------------------------------------------------
# Thin main() — read event, decide, (fetch on OK), emit/log, exit 0.
# ---------------------------------------------------------------------------


def _requested_name(ev: dict) -> Optional[str]:
    """Extract the requested keychain item name from the hook event.

    The wrapper is invoked with the item name as its single argument. We accept
    it from either tool_input.item / tool_input.name / tool_input.secret (the
    structured tool-call shapes) or, failing that, the bare Bash command's first
    non-flag token (so a `mint_prod_session <name>` command line also works).
    Returns None when no name is present.
    """
    try:
        ti = ev.get("tool_input", {})
    except Exception:
        return None
    if isinstance(ti, dict):
        for key in ("item", "name", "secret"):
            v = ti.get(key)
            if isinstance(v, str) and v:
                return v
    # Fall back to a bare command line: "<something> <name>".
    cmd = _lib.bash_command(ev)
    if cmd:
        parts = cmd.split()
        # Drop the leading program token; take the first following non-flag arg.
        for tok in parts[1:]:
            if not tok.startswith("-"):
                return tok
    return None


def _is_target(ev: dict) -> bool:
    """True iff this event is a mint_prod_session invocation we should gate.

    Matches on tool_name == TOOL_NAME, or a Bash command whose program token is
    the wrapper. Anything else is a no-op (the hook stays out of the way).
    """
    if _lib.tool_name(ev) == TOOL_NAME:
        return True
    cmd = _lib.bash_command(ev)
    if not cmd:
        return False
    first = cmd.split()[0] if cmd.split() else ""
    base = first.rsplit("/", 1)[-1]
    return base in (TOOL_NAME, "get_test_secret.sh", "mint_prod_session")


def main() -> int:
    """Entry point. Always returns 0 (deny is via JSON, never an exit code).

    Flow:
      * Master-off (CSA_DISABLE_HOOKS) -> do nothing, exit 0.
      * Not a mint_prod_session event  -> do nothing, exit 0.
      * decide(name):
          OK       -> fetch; on success emit the value to the jar path (stdout)
                      and log ONLY the decision + item name (never the value);
                      on fetch failure, log + (deny if enforcing).
          non-OK   -> log the (secret-free) reason and, when enforcing(), emit a
                      PreToolUse deny carrying the reason. LOG-ONLY otherwise.
    """
    if _lib.disabled():
        return 0

    ev = _lib.read_event()
    if not _is_target(ev):
        return 0

    where = _lib.cwd(ev)
    enforce = _lib.enforcing(where)
    name = _requested_name(ev)
    verdict = decide(name)

    # The item name is safe to log; the VALUE is never logged.
    item_field = name if name else ""

    if not verdict.ok:
        _lib.log(HOOK, "deny", code=verdict.code, reason=verdict.reason, item=item_field)
        if enforce:
            _lib.emit_pretooluse_deny(f"mint_prod_session: {verdict.reason}")
        return 0

    # Validation passed — attempt the keychain fetch.
    result = fetch_secret(name)  # name is a non-empty str here (verdict.ok).
    if not result.ok:
        _lib.log(HOOK, "lookup-failed", code=CODE_LOOKUP, item=item_field)
        if enforce:
            _lib.emit_pretooluse_deny(
                "mint_prod_session: keychain lookup failed for the requested item."
            )
        return 0

    # Success: route the value to the jar path (stdout) ONLY, log the decision
    # WITHOUT the value.
    emit_value(result.value)
    _lib.log(HOOK, "minted", code=CODE_OK, item=item_field)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess/tests
    sys.exit(main())
