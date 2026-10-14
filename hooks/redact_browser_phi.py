#!/usr/bin/env python3
"""redact_browser_phi — PostToolUse scrubber for browser MCP tool results.

Ported faithfully from the proven bash implementation
``~/.claude/scripts/pii_scrub.sh``. That hook reads the tool RESULT text from
STDIN, redacts bearer credentials / PHI-adjacent secrets, and prints the
scrubbed text to STDOUT so it is persisted (transcript / JSONL) WITHOUT secrets.

Redacts:
  * JWTs              : ``eyJ<base64url>.eyJ<base64url>[.<sig>]``
  * Set-Cookie values : ``Set-Cookie: <value>``  -> value redacted
  * named token fields: ``session`` / ``refresh_token`` / ``auth_token`` (the
                        generic defaults) UNION the calling repo's own
                        ``security.auth_cookie_names`` from
                        ``<repo>/.claude/oversight/manifest.json`` (as JSON
                        keys, cookie names, header names) plus the whole value
                        under any ``authorization`` / ``set-cookie`` JSON key.
    Runtime_bundle_repo_agnostic_plan.md WS4.4 (H7): the cookie name used to be
    hardcoded to ExampleApp's own auth cookie
    (``app_auth_token``), which silently redacted nothing for
    any other repo's differently-named auth cookie. The repo is resolved from
    ``git rev-parse --show-toplevel`` of THIS PROCESS's cwd (the PostToolUse
    hook's cwd, i.e. the repo the browser session that produced the tool
    result is actually driving) -- never a hardcoded path, never another
    repo's manifest. No repo, no manifest, or no key -> the generic defaults
    only, same as before this change for every repo that has not yet filled a
    manifest; this can never raise or block (see ``_cookie_names``).

Design (mirrors the bash source):
  * ``scrub(text) -> text`` is a PURE function. It NEVER raises. When the input
    parses as JSON the output stays valid JSON (walk + redact); otherwise it is
    a raw text-level scrub of the input. A token can never pass through verbatim.
  * Idempotent placeholder: ``[REDACTED]``. Scrubbing already-scrubbed text is a
    no-op.
  * The cookie-name SET is resolved via ``_cookie_names()`` and the two
    regex/frozenset globals below (``COOKIEPAIR``, ``SENSITIVE_KEYS``) are
    built from it at import time (generic defaults only) then refreshed
    ONCE by ``main()``, before the first scrub of a real invocation --
    ``scrub_text``/``scrub`` themselves stay pure functions of their own
    input, consulting only these two already-resolved globals, never
    touching the filesystem or subprocess directly.

Hook wiring:
  * PostToolUse, matcher = browser MCP tools. The hook reshapes STDOUT only.
  * LOG-ONLY unless ``enforcing()``: when enforcement is OFF we still emit the
    ORIGINAL text unchanged (observation mode) and log what we WOULD have
    scrubbed. When enforcement is ON we emit the scrubbed text.
  * ``CSA_DISABLE_HOOKS=1`` master-OFF: pass the input straight through, no scrub,
    no log.
  * A deny is never expressed via exit code — this hook always exits 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402  (import after sys.path shim so `import _lib` resolves)

HOOK = "redact_browser_phi"
REDACTED = "[REDACTED]"

# --- text-level regexes (applied to every string value) --------------------
# JWT: two or three base64url segments, first two starting eyJ.
JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?")
# Set-Cookie header value: redact everything after the header name up to CRLF/EOL.
SETCOOKIE = re.compile(r"(?i)(set-cookie:\s*)([^\r\n]+)")

# Generic defaults, always redacted regardless of repo/manifest state.
_DEFAULT_COOKIE_NAMES = ("session", "refresh_token", "auth_token")

# JSON keys whose ENTIRE value is redacted, matched case-insensitively,
# regardless of repo/manifest state.
_STATIC_SENSITIVE_KEYS = frozenset({"set-cookie", "authorization"})


def _repo_root(cwd: str) -> str:
    """`git rev-parse --show-toplevel` at `cwd`, or "" on any failure.

    Mirrors `check_staged_scope._repo_root`'s subprocess discipline exactly
    (same tool, same flags) -- kept local to this module rather than
    imported cross-hook, per this module's existing single-file design.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or None,
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    try:
        return proc.stdout.decode("utf-8", "replace").strip()
    except Exception:  # pragma: no cover - decode with 'replace' cannot raise
        return ""


def _manifest_list(dotted_key: str, repo_root: str) -> list[str]:
    """Read a list-valued manifest key via `scripts/repo_manifest.py get`.

    Returns `[]` on ANY failure -- no repo, no manifest, no such key, a
    malformed manifest, a missing/unreadable `repo_manifest.py`, or a
    non-list value. This hook must degrade open exactly like every other
    hook in this chain (`_lib.py`'s own established pattern): a manifest
    read failure can never crash the scrub or leave a credential
    unredacted, it can only ever narrow back to the generic defaults.
    """
    if not repo_root:
        return []
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "repo_manifest.py")
    try:
        proc = subprocess.run(
            [sys.executable, script, "get", dotted_key, "--repo", repo_root],
            capture_output=True,
            timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    try:
        value = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v]


def _cookie_names(cwd: str | None = None) -> tuple[str, ...]:
    """Generic defaults UNION the cwd repo's `security.auth_cookie_names`.

    `cwd` defaults to this process's own cwd (the PostToolUse hook's cwd,
    i.e. the repo the browser session driving the tool call is actually
    in) when not given explicitly -- explicit `cwd` exists so tests/CLI
    callers can point this at an arbitrary directory without mutating the
    process's real working directory.
    """
    if cwd is None:
        try:
            cwd = os.getcwd()
        except OSError:
            # The process's cwd was deleted out from under it (routine in
            # this runtime: a worktree reap, a peer session removing a
            # directory a long-lived process is sitting in) -- degrade to
            # the generic defaults exactly like every other failure mode
            # this function handles, never a crash. This module's own
            # docstring promises "this hook always exits 0" / "can never
            # raise or block" -- an unguarded os.getcwd() here would violate
            # both, and unlike review_risk_tier.py's advisory classifier,
            # THIS hook is a named mitigation in the signed live-testing
            # compliance determination (docs/subsystems/live-testing.md),
            # so a crash here is not merely a bug, it's an unproven gap in
            # that mitigation's own contract.
            return _DEFAULT_COOKIE_NAMES
    repo_root = _repo_root(cwd)
    extra = _manifest_list("security.auth_cookie_names", repo_root)
    seen: list[str] = []
    for name in (*_DEFAULT_COOKIE_NAMES, *extra):
        if name and name not in seen:
            seen.append(name)
    return tuple(seen)


def _build_patterns(cookie_names: tuple[str, ...]) -> tuple[re.Pattern, frozenset[str]]:
    """Build the (COOKIEPAIR regex, SENSITIVE_KEYS frozenset) pair for a
    given cookie-name set. Pure; never raises given well-formed input.
    """
    alternation = "|".join(re.escape(n) for n in cookie_names) or r"(?!)"  # never-match if empty
    pattern = re.compile(r"(?i)(" + alternation + r")=([^;,\s\"]+)")
    keys = _STATIC_SENSITIVE_KEYS | {n.lower() for n in cookie_names}
    return pattern, keys


# Module-load-time defaults (generic only -- no filesystem/subprocess cost at
# import time). `main()` refreshes both globals from the real cwd's manifest
# before the first scrub of a real invocation; tests exercise `scrub`/`scrub_text`
# against whichever globals are currently set, which is exactly how a caller
# that wants a specific repo's cookie set is expected to drive this module.
COOKIEPAIR, SENSITIVE_KEYS = _build_patterns(_DEFAULT_COOKIE_NAMES)


def scrub_text(s: str) -> str:
    """Redact secrets inside a single string. Pure; never raises.

    Non-str inputs are returned unchanged so the JSON walker can call this on
    every leaf without type checks leaking through.
    """
    if not isinstance(s, str):
        return s
    s = JWT.sub(REDACTED, s)
    s = SETCOOKIE.sub(lambda m: m.group(1) + REDACTED, s)
    s = COOKIEPAIR.sub(lambda m: m.group(1) + "=" + REDACTED, s)
    return s


def _walk(o):
    """Recursively scrub a decoded-JSON value.

    * dict: values under a sensitive key (case-insensitive) are replaced
      wholesale with ``[REDACTED]``; other values are walked.
    * list: each element is walked.
    * str: text-scrubbed.
    * anything else: returned as-is.
    """
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                out[k] = REDACTED
            else:
                out[k] = _walk(v)
        return out
    if isinstance(o, list):
        return [_walk(x) for x in o]
    if isinstance(o, str):
        return scrub_text(o)
    return o


def scrub(text: str) -> str:
    """PURE scrubber: text in, scrubbed text out. Never raises.

    If ``text`` parses as a JSON value, the result is re-serialized JSON with
    secrets redacted (valid JSON in, valid JSON out). Otherwise the raw text is
    scrubbed line-agnostically. On ANY unexpected error we still return a
    best-effort text-scrub so a credential cannot pass through verbatim.
    """
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""
    try:
        data = json.loads(text)
    except Exception:
        # Not JSON — fall back to a raw text scrub of the payload.
        return scrub_text(text)
    try:
        return json.dumps(_walk(data))
    except Exception:  # pragma: no cover - json.dumps of walked data is total
        return scrub_text(text)


def decide(raw: str, enforce: bool) -> tuple[str, bool]:
    """PURE decision: given the raw stdin body, return (output, changed).

    * ``output`` is exactly what main() should print to STDOUT.
    * ``changed`` is True iff scrubbing altered the payload (i.e. a secret was
      present). It drives the log ``decision`` field regardless of enforcement.

    Enforcement semantics:
      * enforce=True  -> emit the SCRUBBED text.
      * enforce=False -> LOG-ONLY: emit the ORIGINAL text unchanged, but still
        report whether a scrub WOULD have fired.

    Never raises. ``raw`` is the literal stdin string (may itself be a JSON
    event envelope or a bare result body — the caller decides which to pass).
    """
    original = raw if isinstance(raw, str) else ""
    scrubbed = scrub(original)
    changed = scrubbed != original
    return (scrubbed if enforce else original), changed


def main() -> int:
    """Thin driver: read stdin, decide, emit to stdout, log, exit 0.

    Reads the raw STDIN body directly (the bash hook is fed the tool RESULT on
    stdin, not a structured event). If that body is a JSON hook envelope that
    carries a ``tool_response``/``tool_result``, the result text within it is
    scrubbed and the envelope re-emitted; otherwise the whole body is scrubbed.
    A deny is NEVER an exit code: this hook always returns 0.
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if not isinstance(raw, str):  # pragma: no cover - stdin.read() always returns str
        raw = ""

    # Master OFF: pass through untouched, do not scrub, do not log.
    if _lib.disabled():
        sys.stdout.write(raw)
        return 0

    enforce = _lib.enforcing()

    # Resolve the cookie-name set for the CALLING repo (this hook's own cwd —
    # the browser session's driving repo) before the first scrub. No repo, no
    # manifest, or no key -> the generic defaults only (see _cookie_names).
    global COOKIEPAIR, SENSITIVE_KEYS
    COOKIEPAIR, SENSITIVE_KEYS = _build_patterns(_cookie_names())

    # If stdin is a hook event envelope wrapping a tool result, scrub the result
    # in place and re-emit the envelope; otherwise scrub the raw body directly.
    payload, envelope, result_key = _extract_payload(raw)

    out, changed = decide(payload, enforce)

    if envelope is not None and result_key is not None:
        # Re-inject the (possibly scrubbed) result back into the envelope.
        try:
            envelope[result_key] = _reinject(envelope[result_key], out)
            emitted = json.dumps(envelope)
        except Exception:  # pragma: no cover - defensive; fall back to out
            emitted = out
    else:
        emitted = out

    sys.stdout.write(emitted)

    try:
        _lib.log(
            HOOK,
            "scrub" if changed else "clean",
            enforced=enforce,
            redacted=changed,
        )
    except Exception:  # pragma: no cover - log() already swallows its own errors
        pass
    return 0


def _extract_payload(raw: str):
    """Return (payload_text, envelope_or_None, result_key_or_None).

    If ``raw`` is a JSON object carrying a tool-result under a known key, return
    that inner text as the payload to scrub plus the envelope + key for
    re-injection. Otherwise the whole ``raw`` is the payload and there is no
    envelope. Never raises.
    """
    try:
        obj = json.loads(raw)
    except Exception:
        return raw, None, None
    if not isinstance(obj, dict):
        return raw, None, None
    for key in ("tool_response", "tool_result", "result"):
        if key in obj:
            v = obj[key]
            inner = v if isinstance(v, str) else _safe_dumps(v)
            return inner, obj, key
    # A JSON object with no result wrapper — scrub it wholesale as the payload.
    return raw, None, None


def _reinject(original_value, scrubbed_text: str):
    """Put ``scrubbed_text`` back where ``original_value`` came from.

    If the original result value was a string, keep it a string. If it was a
    structured value, try to parse the scrubbed text back to JSON so the
    envelope stays structurally faithful; fall back to the string form.
    """
    if isinstance(original_value, str):
        return scrubbed_text
    try:
        return json.loads(scrubbed_text)
    except Exception:  # pragma: no cover - scrubbed structured JSON re-parses
        return scrubbed_text


def _safe_dumps(v) -> str:
    """json.dumps that never raises; returns '' on failure."""
    try:
        return json.dumps(v)
    except Exception:  # pragma: no cover
        return ""


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    raise SystemExit(main())
