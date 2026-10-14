"""Playwright pool / lease manager CLI — runtime edition.

VENDORED copy of ExampleApp/repo_tooling/scripts/playwright_pool.py.
Adaptations from the original:
  1. Pool home default changed to ~/.claude/.browser_pool (product-neutral).
  2. Per-slot MCP origin flags are GENERATED from allowlist.json:
       --allowed-origins  from allowed_origins (positive allowlist for prod slot)
       --blocked-origins  from denied_action_patterns (comms/billing providers)
     instead of the hardcoded '--blocked-origins ...example.com'.
  3. Corrupt-registry self-heal: if the registry JSON is unreadable and no
     slot has a live owner (verified via ps), the registry is rebuilt from
     scratch (fail-open). The rebuild is logged to stderr.
  4. ENV var renamed: CLAUDE_POOL_HOME (was CSA_POOL_HOME) to avoid coupling
     to the SaaS product. CSA_POOL_HOME is still honoured as a fallback.

Storage layout (pool_home()):
  registry.json          -- numbered-slot lease registry (mode 0600)
  registry.lock          -- flock target (created, never written)
  auth.json              -- single auth-slot lease (mode 0600)
  auth.lock              -- flock target
  state/merged.json      -- merged storage-state jar (mode 0600)
  state/captures/<s>.json -- per-service captures (mode 0600)
  cache/<slot>/          -- ephemeral scratch

Exit codes:
  0  OK
  2  E_USAGE   (bad args / unknown slot)
  3  E_NO_CAPACITY
  4  E_NOT_OWNER
  5  E_AUTH_HELD
  6  E_LOCK_TIMEOUT

Usage:
    python ~/.claude/live-testing/browser_pool.py --help
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

E_OK = 0
E_USAGE = 2
E_NO_CAPACITY = 3
E_NOT_OWNER = 4
E_AUTH_HELD = 5
E_LOCK_TIMEOUT = 6

# ---------------------------------------------------------------------------
# Storage location — product-neutral default
# ---------------------------------------------------------------------------

_DEFAULT_POOL_HOME = Path.home() / ".claude" / ".browser_pool"

# Staging-only storage-state jar loaded by every numbered slot when present.
# Written by prime_browser_pool.sh from the app registry; deliberately separate
# from the legacy merged.json, which contains production cookies.
STAGING_JAR_NAME = "staging-merged.json"

AUTH_SLOT = "playwright-auth"


def pool_home() -> Path:
    """Return pool home: $CLAUDE_POOL_HOME, $CSA_POOL_HOME (legacy), or default."""
    env = os.environ.get("CLAUDE_POOL_HOME") or os.environ.get("CSA_POOL_HOME")
    if env:
        return Path(env)
    return _DEFAULT_POOL_HOME


# ---------------------------------------------------------------------------
# Allowlist loader — the single policy source
# ---------------------------------------------------------------------------

_ALLOWLIST_PATH = Path(__file__).parent / "allowlist.json"


def _load_allowlist() -> dict:
    """Load allowlist.json; return empty dict on parse error (fail-open)."""
    try:
        return json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] Could not load allowlist.json: {exc}", file=sys.stderr)
        return {}


def _build_allowed_origins_flag(allowlist: dict) -> str:
    """Build semicolon-joined --allowed-origins value from allowlist."""
    origins = allowlist.get("allowed_origins", [])
    # Expand localhost wildcard for common local ports (MCP doesn't support glob)
    expanded: list[str] = []
    for o in origins:
        if o == "http://localhost:*":
            expanded += [f"http://localhost:{p}" for p in range(3000, 3010)]
            expanded += ["http://localhost:5173", "http://localhost:8080", "http://localhost:8000"]
        elif o == "http://127.0.0.1:*":
            expanded += [f"http://127.0.0.1:{p}" for p in range(3000, 3010)]
            expanded += ["http://127.0.0.1:5173", "http://127.0.0.1:8080", "http://127.0.0.1:8000"]
        else:
            expanded.append(o)
    return ";".join(expanded) if expanded else ""


def _build_blocked_origins_flag(allowlist: dict) -> str:
    """Build semicolon-joined --blocked-origins value from denied_action_patterns.

    MCP --blocked-origins takes URL prefixes/globs, not full path patterns.
    We extract the scheme+host portion from each denied pattern.

    Handles:
      https://*.stripe.com/*   -> https://*.stripe.com  (wildcard subdomain)
      https://api.twilio.com/* -> https://api.twilio.com
      */admin/*                -> skipped (path-only, no origin)
    """
    import re as _re

    patterns = allowlist.get("denied_action_patterns", [])
    blocked: list[str] = []
    for p in patterns:
        # path-only pattern like */admin/* — not an origin block, skip
        if p.startswith("*/"):
            continue
        # Must start with a scheme to be an origin pattern
        if not (p.startswith("http://") or p.startswith("https://")):
            continue
        # Extract scheme + host (strip any path component starting with /)
        # Pattern: scheme://[*.]host[/...]
        m = _re.match(r"(https?://[^/]+)", p)
        if m:
            origin_part = m.group(1)
            if origin_part not in blocked:
                blocked.append(origin_part)
    return ";".join(blocked) if blocked else ""


# ---------------------------------------------------------------------------
# Slot naming
# ---------------------------------------------------------------------------


def slot_name(n: int) -> str:
    """Return zero-padded slot name, e.g. 'playwright-07'."""
    return f"playwright-{n:02d}"


def all_slot_names(pool_size: int) -> list[str]:
    return [slot_name(i) for i in range(1, pool_size + 1)]


# ---------------------------------------------------------------------------
# Registry schema helpers
# ---------------------------------------------------------------------------


def _free_record(slot: str) -> dict:
    return {
        "slot": slot,
        "status": "free",
        "owner_pid": None,
        "owner_fingerprint": None,
        "owner_label": None,
        "claimed_at": None,
        "renewed_at": None,
        "expires_at": None,
        "ttl_seconds": None,
        "renew_count": 0,
    }


def _fresh_registry(pool_size: int) -> dict:
    return {
        "version": 1,
        "pool_size": pool_size,
        "slots": {s: _free_record(s) for s in all_slot_names(pool_size)},
    }


def _fresh_auth() -> dict:
    return _free_record(AUTH_SLOT)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, data: object) -> None:
    """Write *data* as JSON to *path* atomically (mode 0600)."""
    tmp = Path(str(path) + f".tmp.{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(tmp), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            os.unlink(str(tmp))
        except OSError:
            pass
        raise
    os.replace(str(tmp), str(path))


def _read_json_or_none(path: Path) -> dict | None:
    """Read JSON from path; return None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_json(path: Path) -> dict:
    data = _read_json_or_none(path)
    if data is None:
        raise json.JSONDecodeError(f"Could not read {path}", "", 0)
    return data


class LockTimeout(Exception):
    pass


@contextlib.contextmanager
def locked_registry(lock_path: Path, timeout: float = 10.0) -> Generator[None, None, None]:
    """Acquire an exclusive flock on *lock_path*, release on exit."""
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"Could not acquire lock {lock_path} within {timeout}s")
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ---------------------------------------------------------------------------
# Process liveness / fingerprinting
# ---------------------------------------------------------------------------


def ps_fingerprint(pid: int) -> str | None:
    """Return the lstart string for *pid*, or None on failure/race."""
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = result.stdout.strip()
        return out if out else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pure reaping decision (unchanged from original)
# ---------------------------------------------------------------------------


@dataclass
class ReapDecision:
    should_reap: bool
    reason: str
    stale_but_alive: bool = False


def reap_decision(
    record: dict,
    now: float,
    ps_fn: Callable[[int], str | None] = ps_fingerprint,
) -> ReapDecision:
    """Pure function: decide whether to reap a LEASED record.

    Rules:
    1. dead (ProcessLookupError) → REAP
    2. PermissionError → ALIVE, do NOT reap
    3. alive but fingerprint differs (PID recycled) → REAP
    4. alive, fingerprint matches → NEVER reap, even if past TTL
    5. alive, ps returns None (race) → treat alive, do NOT reap
    """
    if record.get("status") != "leased":
        return ReapDecision(should_reap=False, reason="not_leased")

    pid: int | None = record.get("owner_pid")
    if pid is None:
        return ReapDecision(should_reap=True, reason="null_pid")

    dead = False
    permission_denied = False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        dead = True
    except PermissionError:
        permission_denied = True

    if dead:
        return ReapDecision(should_reap=True, reason="dead_pid")

    if permission_denied:
        expires_at = record.get("expires_at")
        stale = expires_at is not None and now > expires_at
        return ReapDecision(should_reap=False, reason="alive_no_permission", stale_but_alive=stale)

    stored_fp: str | None = record.get("owner_fingerprint")
    current_fp = ps_fn(pid)

    if current_fp is None:
        expires_at = record.get("expires_at")
        stale = expires_at is not None and now > expires_at
        return ReapDecision(should_reap=False, reason="alive_fp_race", stale_but_alive=stale)

    if stored_fp is not None and current_fp != stored_fp:
        return ReapDecision(should_reap=True, reason="pid_recycled")

    expires_at = record.get("expires_at")
    stale = expires_at is not None and now > expires_at
    return ReapDecision(should_reap=False, reason="alive_matching_fp", stale_but_alive=stale)


# ---------------------------------------------------------------------------
# Storage-state merge (unchanged from original)
# ---------------------------------------------------------------------------


@dataclass
class MergeStats:
    cookies_in: int = 0
    cookies_out: int = 0
    dropped_expired: int = 0
    dropped_session: int = 0


def merge_states(captures: list[dict], now: float) -> tuple[dict, MergeStats]:
    """Merge a list of Playwright storage-state dicts into one.

    Args:
        captures: list of storage-state dicts, in SORTED filename order
                  (later index wins on tie).
        now: current epoch seconds for expiry evaluation.

    Returns:
        (merged_dict, stats)
    """
    from collections import defaultdict

    stats = MergeStats()

    for cap in captures:
        stats.cookies_in += len(cap.get("cookies", []))

    groups: dict[tuple[str, str, str], list[tuple[int, dict]]] = defaultdict(list)
    for idx, cap in enumerate(captures):
        for cookie in cap.get("cookies", []):
            key = (
                cookie.get("domain", ""),
                cookie.get("path", ""),
                cookie.get("name", ""),
            )
            groups[key].append((idx, cookie))

    merged_cookies: list[dict] = []
    for key, candidates in groups.items():
        live: list[tuple[int, dict]] = []
        for idx, c in candidates:
            expires = c.get("expires")
            if isinstance(expires, (int, float)) and expires > 0 and expires <= now:
                stats.dropped_expired += 1
            else:
                live.append((idx, c))

        if not live:
            continue

        persistent = [
            (i, c)
            for i, c in live
            if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0
        ]
        session = [
            (i, c)
            for i, c in live
            if not (isinstance(c.get("expires"), (int, float)) and c["expires"] > 0)
        ]

        if persistent:
            stats.dropped_session += len(session)
            best = max(persistent, key=lambda x: (x[1]["expires"], x[0]))
            merged_cookies.append(best[1])
        else:
            stats.dropped_session += len(session) - 1
            merged_cookies.append(session[-1][1])

    stats.cookies_out = len(merged_cookies)

    origins_map: dict[str, dict] = {}
    for cap in captures:
        for origin in cap.get("origins", []):
            origins_map[origin.get("origin", "")] = origin

    return (
        {"cookies": merged_cookies, "origins": list(origins_map.values())},
        stats,
    )


# ---------------------------------------------------------------------------
# Corrupt-registry self-heal
# ---------------------------------------------------------------------------


def _has_any_live_owner(slots: dict, now: float) -> bool:
    """Return True if any leased slot has a verifiably live owner."""
    for rec in slots.values():
        if rec.get("status") == "leased":
            decision = reap_decision(rec, now)
            if not decision.should_reap:
                return True
    return False


def _safe_read_registry(reg_path: Path, lock_path: Path, pool_size: int, now: float) -> dict:
    """Read registry, self-healing corrupt JSON if no live owners exist.

    If the file is unreadable/corrupt AND no slot has a live owner (verified
    by probing each PID), the registry is rebuilt from scratch and the old
    file replaced. This is fail-open: we only rebuild when we're certain no
    real session is running. If any live owner is found, the corrupt file
    error propagates.
    """
    raw = _read_json_or_none(reg_path)
    if raw is not None:
        return raw

    # Registry is corrupt or missing. Try to determine if it's safe to rebuild.
    print(
        f"[warn] Registry at {reg_path} is missing or corrupt. Attempting self-heal.",
        file=sys.stderr,
    )

    # If the file doesn't exist at all, just rebuild.
    if not reg_path.exists():
        fresh = _fresh_registry(pool_size)
        atomic_write_json(reg_path, fresh)
        print("[info] Registry rebuilt (was missing).", file=sys.stderr)
        return fresh

    # File exists but unparseable — check if any PID in the raw bytes looks live.
    # As a heuristic, try to extract any integer that could be a PID from the raw text.
    import re

    try:
        raw_text = reg_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raw_text = ""

    pid_candidates = [int(m) for m in re.findall(r'"owner_pid":\s*(\d+)', raw_text)]
    any_live = False
    for pid in pid_candidates:
        try:
            os.kill(pid, 0)
            any_live = True
            break
        except ProcessLookupError:
            pass
        except PermissionError:
            # alive but no permission to signal — treat as live
            any_live = True
            break

    if any_live:
        raise RuntimeError(
            f"Registry at {reg_path} is corrupt but live PIDs detected. "
            "Manual intervention required; do NOT auto-rebuild."
        )

    # No live owners found — safe to rebuild
    fresh = _fresh_registry(pool_size)
    atomic_write_json(reg_path, fresh)
    print("[info] Registry rebuilt (was corrupt, no live owners detected).", file=sys.stderr)
    return fresh


# ---------------------------------------------------------------------------
# gen-config helpers
# ---------------------------------------------------------------------------

_DEFAULT_MCP_VERSION = "0.0.76"
_DEFAULT_POOL_SIZE = 12
_OWNED_PREFIX_PATTERN = "playwright-"


def _server_entry_numbered(slot: str, ph: Path, ver: str, allowlist: dict) -> dict:
    """Build MCP server entry for a numbered slot.

    Origin flags come from allowlist.json:
    - --allowed-origins: positive allowlist (prod + staging + local)
    - --blocked-origins: denied billing/comms provider patterns
    """
    # Operator override (2026-07-24): headed real Chrome, fresh login each
    # session, and NO origin allowlist. Rationale:
    #  - headed real Chrome (--browser chrome) → the operator sees every window
    #    and can solve reCAPTCHA; real-Chrome stealth clears it far better than
    #    headless Chromium.
    #  - no --allowed-origins/--blocked-origins: drive any site on request.
    # allowed/blocked are still computed (helpers kept for tests) but not applied.
    #
    # STAGING JAR (2026-09-06, operator-directed): slots now load
    # state/staging-merged.json when it exists, so a session in ANY repo starts
    # pre-authenticated to every app registered in live-testing/apps.json and no
    # agent ever handles a credential. This does NOT reverse the #2001 finding
    # it replaces -- that finding is about PRODUCTION (prod uses an in-memory
    # token, so a jar cannot re-auth it; prod logins stay fresh-every-session
    # per the live-testing skill). It is also deliberately NOT the legacy
    # state/merged.json, which holds real PRODUCTION cookies from old attended
    # prod logins; mounting those into all 12 slots is exactly what loading no
    # jar was avoiding. staging-merged.json is written only by
    # prime_browser_pool.sh, which filters every cookie against the registry's
    # staging_hosts. If it is absent the flag is omitted entirely and behavior
    # is byte-identical to before.
    allowed = _build_allowed_origins_flag(allowlist)
    blocked = _build_blocked_origins_flag(allowlist)
    _ = (allowed, blocked)

    args = [
        "-y",
        f"@playwright/mcp@{ver}",
        "--isolated",
        "--browser",
        "chrome",
        "--output-dir",
        str(ph / "cache" / slot),
    ]

    staging_jar = ph / "state" / STAGING_JAR_NAME
    if staging_jar.exists():
        args += ["--storage-state", str(staging_jar)]

    return {"command": "npx", "args": args}


def _server_entry_auth(ph: Path, ver: str) -> dict:
    return {
        "command": "npx",
        "args": [
            "-y",
            f"@playwright/mcp@{ver}",
            "--isolated",
            "--save-session",
            "--output-dir",
            str(ph / "state" / "captures"),
        ],
    }


def _server_entry_adhoc(ver: str) -> dict:
    return {
        "command": "npx",
        "args": [
            "-y",
            f"@playwright/mcp@{ver}",
            "--isolated",
            "--browser",
            "chrome",
        ],
    }


ADMIN_CSA_SLOT = "playwright-admin-csa"
_ADMIN_CSA_WRAPPER = "csa_admin_iap_token.sh"


def _server_entry_admin_csa() -> dict:
    """ExampleApp admin-portal slot: IAP-gated via a bearer token minted
    fresh on every launch (browser.contextOptions.extraHTTPHeaders, not a
    cookie) by csa_admin_iap_token.sh, which lives alongside this module
    (Path(__file__).parent — NOT the pool home / cache dir, which is a
    different directory). The token authenticates as
    csa-admin-automation@example-org.iam.gserviceaccount.com
    (roles/iap.httpsResourceAccessor only — see
    ExampleApp/_Config_Project/docs/runbooks/admin_iap_access.md §5).
    Never baked into this generated config: the wrapper fetches the SA key
    from GSM and mints a new identity token on each process start, so a
    stale/expired token just means re-launching the slot, not editing a file.
    Added 2026-09-10 for headed-browser admin-portal review work."""
    return {
        "command": str(Path(__file__).parent / _ADMIN_CSA_WRAPPER),
        "args": [],
    }


def _build_servers(pool_size: int, ph: Path, ver: str, allowlist: dict) -> dict[str, dict]:
    """Build the ordered server map this tool owns."""
    servers: dict[str, dict] = {}
    for n in range(1, pool_size + 1):
        s = slot_name(n)
        servers[s] = _server_entry_numbered(s, ph, ver, allowlist)
    servers[AUTH_SLOT] = _server_entry_auth(ph, ver)
    servers["playwright-adhoc"] = _server_entry_adhoc(ver)
    servers[ADMIN_CSA_SLOT] = _server_entry_admin_csa()
    return servers


def _is_owned_key(k: str, pool_size: int) -> bool:
    """Return True if key is one this tool manages."""
    if k == "playwright-adhoc" or k == AUTH_SLOT or k == "playwright" or k == ADMIN_CSA_SLOT:
        return True
    for n in range(1, pool_size + 1):
        if k == slot_name(n):
            return True
    return False


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_gen_config(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    ver = args.mcp_version
    pool_size = args.pool_size
    allowlist = _load_allowlist()

    if args.agent_tools is not None:
        slots = [slot_name(n) for n in range(1, pool_size + 1)]
        parts = ["Read", "Bash"]
        for s in slots:
            parts.append(f"mcp__{s}__*")
        csv = ", ".join(parts)
        print(json.dumps({"action": "gen-config", "agent_tools": csv}))
        return E_OK

    servers = _build_servers(pool_size, ph, ver, allowlist)

    if args.write:
        out_path = Path(args.out) if args.out else Path.home() / ".claude" / ".mcp.json"
        existing: dict = {}
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}

        existing_servers: dict = existing.get("mcpServers", {})
        kept = {k: v for k, v in existing_servers.items() if not _is_owned_key(k, pool_size)}
        new_servers = {**kept, **servers}
        new_doc = {**existing, "mcpServers": new_servers}

        candidate = json.dumps(new_doc, indent=2, sort_keys=True) + "\n"
        current = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
        try:
            current_norm = json.dumps(json.loads(current), indent=2, sort_keys=True) + "\n"
        except (json.JSONDecodeError, ValueError):
            current_norm = ""

        wrote = candidate != current_norm
        if wrote:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(candidate, encoding="utf-8")

        print(
            json.dumps(
                {
                    "action": "gen-config",
                    "wrote": wrote,
                    "servers": list(new_servers.keys()),
                }
            )
        )
        return E_OK

    print(
        json.dumps(
            {
                "action": "gen-config",
                "wrote": False,
                "servers": list(servers.keys()),
                "mcpServers": servers,
            }
        )
    )
    return E_OK


def cmd_merge_state(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    captures_dir = ph / "state" / "captures"
    merged_path = ph / "state" / "merged.json"

    sources: list[str] = []
    raw_captures: list[dict] = []

    if captures_dir.exists():
        for p in sorted(captures_dir.glob("*.json")):
            try:
                data = _read_json(p)
                raw_captures.append(data)
                sources.append(str(p))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[warn] could not parse {p}: {exc}", file=sys.stderr)

    merged, stats = merge_states(raw_captures, now)

    wrote = False
    if not args.dry_run:
        (ph / "state").mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write_json(merged_path, merged)
        wrote = True

    print(
        json.dumps(
            {
                "action": "merge-state",
                "sources": sources,
                "cookies_in": stats.cookies_in,
                "cookies_out": stats.cookies_out,
                "dropped_expired": stats.dropped_expired,
                "dropped_session": stats.dropped_session,
                "wrote": wrote,
                "path": str(merged_path),
            }
        )
    )
    return E_OK


def cmd_init(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    reg_path = ph / "registry.json"
    lock_path = ph / "registry.lock"
    auth_path = ph / "auth.json"

    pool_size = getattr(args, "pool_size", _DEFAULT_POOL_SIZE)

    if reg_path.exists() and not args.force:
        raw = _read_json_or_none(reg_path)
        if raw is not None:
            for slot_rec in raw.get("slots", {}).values():
                if slot_rec.get("status") == "leased":
                    pid = slot_rec.get("owner_pid")
                    if pid is not None:
                        decision = reap_decision(slot_rec, now)
                        if not decision.should_reap:
                            _emit_error(
                                "init",
                                "E_USAGE",
                                E_USAGE,
                                f"Slot {slot_rec['slot']} has live owner pid={pid}. "
                                "Use --force to reinitialise.",
                            )
                            return E_USAGE

    for d in [ph, ph / "state", ph / "state" / "captures", ph / "cache"]:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)

    lock_path.touch(mode=0o600, exist_ok=True)
    with locked_registry(lock_path):
        registry = _fresh_registry(pool_size)
        atomic_write_json(reg_path, registry)

    auth_lock = ph / "auth.lock"
    auth_lock.touch(mode=0o600, exist_ok=True)
    atomic_write_json(auth_path, _fresh_auth())

    print(
        json.dumps(
            {
                "action": "init",
                "pool_home": str(ph),
                "slots": pool_size,
                "created": True,
            }
        )
    )
    return E_OK


def _get_fingerprint(pid: int) -> str | None:
    return ps_fingerprint(pid)


def cmd_claim(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    reg_path = ph / "registry.json"
    lock_path = ph / "registry.lock"

    pid: int = args.pid if args.pid is not None else os.getppid()
    ttl: int = args.ttl
    label: str | None = args.label
    fingerprint = _get_fingerprint(pid)

    pool_size = getattr(args, "pool_size", _DEFAULT_POOL_SIZE)

    try:
        with locked_registry(lock_path):
            reg = _safe_read_registry(reg_path, lock_path, pool_size, now)
            slots: dict = reg["slots"]

            chosen: str | None = None
            for slot_key in sorted(slots.keys()):
                rec = slots[slot_key]
                if rec["status"] == "free":
                    chosen = slot_key
                    break
                if rec["status"] == "leased":
                    decision = reap_decision(rec, now)
                    if decision.should_reap:
                        chosen = slot_key
                        break

            if chosen is None:
                _emit_error("claim", "E_NO_CAPACITY", E_NO_CAPACITY, "No free slots available")
                return E_NO_CAPACITY

            expires_at = now + ttl
            slots[chosen] = {
                **slots[chosen],
                "status": "leased",
                "owner_pid": pid,
                "owner_fingerprint": fingerprint,
                "owner_label": label,
                "claimed_at": now,
                "renewed_at": now,
                "expires_at": expires_at,
                "ttl_seconds": ttl,
                "renew_count": 0,
            }
            atomic_write_json(reg_path, reg)
    except LockTimeout:
        _emit_error("claim", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire registry lock")
        return E_LOCK_TIMEOUT

    print(
        json.dumps(
            {
                "action": "claim",
                "slot": chosen,
                "expires_at": expires_at,
                "ttl_seconds": ttl,
            }
        )
    )
    return E_OK


def cmd_claim_auth(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    auth_path = ph / "auth.json"
    auth_lock = ph / "auth.lock"

    pid: int = args.pid if args.pid is not None else os.getppid()
    ttl: int = args.ttl
    label: str | None = args.label
    fingerprint = _get_fingerprint(pid)

    try:
        with locked_registry(auth_lock):
            raw = _read_json_or_none(auth_path)
            if raw is None:
                # auth.json missing — create fresh
                raw = _fresh_auth()

            if raw.get("status") == "leased":
                decision = reap_decision(raw, now)
                if not decision.should_reap:
                    _emit_error(
                        "claim-auth",
                        "E_AUTH_HELD",
                        E_AUTH_HELD,
                        f"Auth slot held by live owner pid={raw.get('owner_pid')}",
                    )
                    return E_AUTH_HELD

            expires_at = now + ttl
            new_rec = {
                **raw,
                "status": "leased",
                "owner_pid": pid,
                "owner_fingerprint": fingerprint,
                "owner_label": label,
                "claimed_at": now,
                "renewed_at": now,
                "expires_at": expires_at,
                "ttl_seconds": ttl,
                "renew_count": 0,
            }
            atomic_write_json(auth_path, new_rec)
    except LockTimeout:
        _emit_error("claim-auth", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire auth lock")
        return E_LOCK_TIMEOUT

    print(
        json.dumps(
            {
                "action": "claim-auth",
                "slot": AUTH_SLOT,
                "expires_at": expires_at,
                "ttl_seconds": ttl,
            }
        )
    )
    return E_OK


def cmd_renew(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    slot_id: str = args.slot
    pid: int = args.pid if args.pid is not None else os.getppid()

    lock_path = ph / "registry.lock"
    reg_path = ph / "registry.json"
    pool_size = getattr(args, "pool_size", _DEFAULT_POOL_SIZE)

    try:
        with locked_registry(lock_path):
            reg = _safe_read_registry(reg_path, lock_path, pool_size, now)
            slots: dict = reg.get("slots", {})
            if slot_id not in slots:
                _emit_error("renew", "E_USAGE", E_USAGE, f"Unknown slot: {slot_id}")
                return E_USAGE

            rec = slots[slot_id]
            if rec.get("status") != "leased" or rec.get("owner_pid") != pid:
                _emit_error("renew", "E_NOT_OWNER", E_NOT_OWNER, f"Not the owner of slot {slot_id}")
                return E_NOT_OWNER

            stored_fp = rec.get("owner_fingerprint")
            current_fp = _get_fingerprint(pid)
            if stored_fp is not None and current_fp is not None and stored_fp != current_fp:
                _emit_error(
                    "renew",
                    "E_NOT_OWNER",
                    E_NOT_OWNER,
                    f"Fingerprint mismatch for slot {slot_id}",
                )
                return E_NOT_OWNER

            ttl = args.ttl if args.ttl is not None else rec.get("ttl_seconds", 900)
            expires_at = now + ttl
            rec["renewed_at"] = now
            rec["expires_at"] = expires_at
            rec["renew_count"] = rec.get("renew_count", 0) + 1
            if args.ttl is not None:
                rec["ttl_seconds"] = ttl
            atomic_write_json(reg_path, reg)
    except LockTimeout:
        _emit_error("renew", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire registry lock")
        return E_LOCK_TIMEOUT

    print(
        json.dumps(
            {
                "action": "renew",
                "slot": slot_id,
                "expires_at": expires_at,
                "renew_count": rec["renew_count"],
            }
        )
    )
    return E_OK


def _clear_slot_host_best_effort(slot_id: str) -> None:
    """Clear R5's recorded last-navigated-host entry for *slot_id*, if any.

    R5 (``hooks/block_prod_mutations.py``) fail-closed-denies an interaction-
    class Playwright tool when no host is recorded for its slot; without this
    clear, a freshly (re)claimed slot would silently inherit whatever host the
    PRIOR lease-holder last navigated to, letting a new session's first
    interaction sail through as if it were still on that (possibly
    read-only) host. Imports ``block_prod_mutations`` by path — this module
    lives in ``live-testing/``, that one in ``hooks/`` — and is deliberately
    best-effort: an import failure or any error while clearing must never
    break a real ``release`` (the slot still frees normally either way; the
    worst case is a stale host record that R5's own 4h TTL still bounds).
    """
    try:
        hooks_dir = str(Path(__file__).resolve().parent.parent / "hooks")
        if hooks_dir not in sys.path:
            sys.path.insert(0, hooks_dir)
        import block_prod_mutations as _bpm  # noqa: PLC0415

        _bpm.clear_slot_host(slot_id)
    except Exception:
        pass


def cmd_release(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    slot_id: str = args.slot
    pid: int = args.pid if args.pid is not None else os.getppid()

    lock_path = ph / "registry.lock"
    reg_path = ph / "registry.json"
    pool_size = getattr(args, "pool_size", _DEFAULT_POOL_SIZE)

    try:
        with locked_registry(lock_path):
            reg = _safe_read_registry(reg_path, lock_path, pool_size, now)
            slots: dict = reg.get("slots", {})
            if slot_id not in slots:
                _emit_error("release", "E_USAGE", E_USAGE, f"Unknown slot: {slot_id}")
                return E_USAGE

            rec = slots[slot_id]
            if rec.get("status") != "leased" or rec.get("owner_pid") != pid:
                _emit_error(
                    "release",
                    "E_NOT_OWNER",
                    E_NOT_OWNER,
                    f"Not the owner of slot {slot_id}",
                )
                return E_NOT_OWNER

            slots[slot_id] = _free_record(slot_id)
            atomic_write_json(reg_path, reg)
    except LockTimeout:
        _emit_error("release", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire registry lock")
        return E_LOCK_TIMEOUT

    _clear_slot_host_best_effort(slot_id)

    print(json.dumps({"action": "release", "slot": slot_id, "status": "free"}))
    return E_OK


def cmd_release_auth(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    pid: int = args.pid if args.pid is not None else os.getppid()
    auth_path = ph / "auth.json"
    auth_lock = ph / "auth.lock"

    try:
        with locked_registry(auth_lock):
            raw = _read_json_or_none(auth_path)
            if raw is None or raw.get("status") != "leased" or raw.get("owner_pid") != pid:
                _emit_error(
                    "release-auth",
                    "E_NOT_OWNER",
                    E_NOT_OWNER,
                    "Not the owner of auth slot",
                )
                return E_NOT_OWNER
            atomic_write_json(auth_path, _free_record(AUTH_SLOT))
    except LockTimeout:
        _emit_error("release-auth", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire auth lock")
        return E_LOCK_TIMEOUT

    print(json.dumps({"action": "release-auth", "slot": AUTH_SLOT, "status": "free"}))
    return E_OK


def cmd_reap(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    lock_path = ph / "registry.lock"
    reg_path = ph / "registry.json"
    auth_lock = ph / "auth.lock"
    auth_path = ph / "auth.json"

    reaped: list[str] = []
    skipped_alive: list[str] = []
    dry_run: bool = args.dry_run
    pool_size = getattr(args, "pool_size", _DEFAULT_POOL_SIZE)

    try:
        with locked_registry(lock_path):
            reg = _safe_read_registry(reg_path, lock_path, pool_size, now)
            slots: dict = reg.get("slots", {})
            changed = False
            for slot_key, rec in slots.items():
                if rec.get("status") != "leased":
                    continue
                decision = reap_decision(rec, now)
                if decision.should_reap:
                    reaped.append(slot_key)
                    if not dry_run:
                        slots[slot_key] = _free_record(slot_key)
                        changed = True
                else:
                    skipped_alive.append(slot_key)
            if changed:
                atomic_write_json(reg_path, reg)
    except LockTimeout:
        _emit_error("reap", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire registry lock")
        return E_LOCK_TIMEOUT

    try:
        with locked_registry(auth_lock):
            raw = _read_json_or_none(auth_path)
            if raw is not None and raw.get("status") == "leased":
                decision = reap_decision(raw, now)
                if decision.should_reap:
                    reaped.append(AUTH_SLOT)
                    if not dry_run:
                        atomic_write_json(auth_path, _free_record(AUTH_SLOT))
                else:
                    skipped_alive.append(AUTH_SLOT)
    except LockTimeout:
        _emit_error("reap", "E_LOCK_TIMEOUT", E_LOCK_TIMEOUT, "Could not acquire auth lock")
        return E_LOCK_TIMEOUT

    print(
        json.dumps(
            {
                "action": "reap",
                "reaped": reaped,
                "skipped_alive": skipped_alive,
                "dry_run": dry_run,
            }
        )
    )
    return E_OK


def cmd_status(args: argparse.Namespace, now: float) -> int:
    ph = pool_home()
    reg_path = ph / "registry.json"

    if not reg_path.exists():
        _emit_error("status", "E_USAGE", E_USAGE, "Pool not initialised; run init first")
        return E_USAGE

    pool_size = _DEFAULT_POOL_SIZE
    raw = _read_json_or_none(reg_path)
    if raw is None:
        # corrupt — report that
        print(
            json.dumps(
                {
                    "action": "status",
                    "error": "corrupt_registry",
                    "message": "registry.json is unreadable; run 'reap' or 'init --force' to recover",
                }
            )
        )
        return E_USAGE

    slots: dict = raw.get("slots", {})
    pool_size = raw.get("pool_size", len(slots))
    filter_slot: str | None = getattr(args, "slot", None)

    result: list[dict] = []
    free_count = 0
    leased_count = 0

    for slot_key in sorted(slots.keys()):
        if filter_slot and slot_key != filter_slot:
            continue
        rec = dict(slots[slot_key])
        if rec.get("status") == "free":
            free_count += 1
            rec["owner_alive"] = None
            rec["stale_but_alive"] = False
            rec["ttl_remaining"] = None
        else:
            leased_count += 1
            decision = reap_decision(rec, now)
            rec["owner_alive"] = not decision.should_reap
            rec["stale_but_alive"] = decision.stale_but_alive
            expires_at = rec.get("expires_at")
            rec["ttl_remaining"] = max(0.0, expires_at - now) if expires_at is not None else None
        result.append(rec)

    print(
        json.dumps(
            {
                "action": "status",
                "pool_size": pool_size,
                "free": free_count,
                "leased": leased_count,
                "slots": result,
            }
        )
    )
    return E_OK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(action: str, error: str, code: int, message: str) -> None:
    print(json.dumps({"action": action, "error": error, "code": code, "message": message}))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Playwright pool / lease manager CLI (runtime edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pool-home", type=Path, default=None, help="Override pool home path")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-JSON output")
    parser.add_argument(
        "--now",
        type=float,
        default=None,
        help=argparse.SUPPRESS,  # test hook
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # gen-config
    p_gc = sub.add_parser("gen-config", help="Generate MCP config for pool slots")
    p_gc.add_argument("--write", action="store_true", help="Write to .mcp.json")
    p_gc.add_argument(
        "--agent-tools",
        nargs="?",
        const="glob",
        default=None,
        metavar="glob|explicit",
        help="Print comma-separated tools CSV",
    )
    p_gc.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)
    p_gc.add_argument("--mcp-version", default=_DEFAULT_MCP_VERSION)
    p_gc.add_argument("--out", default=None, help="Target .mcp.json path (with --write)")

    # merge-state
    p_ms = sub.add_parser("merge-state", help="Merge auth captures into state/merged.json")
    p_ms.add_argument("--dry-run", action="store_true")

    # init
    p_init = sub.add_parser("init", help="Initialise pool directory tree")
    p_init.add_argument("--force", action="store_true", help="Reinitialise even if leases exist")
    p_init.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)

    # claim
    p_claim = sub.add_parser("claim", help="Claim a pool slot")
    p_claim.add_argument("--ttl", type=int, default=900, help="TTL in seconds (default: 900)")
    p_claim.add_argument("--label", default=None)
    p_claim.add_argument("--pid", type=int, default=None)
    p_claim.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)

    # claim-auth
    p_ca = sub.add_parser("claim-auth", help="Claim the auth slot")
    p_ca.add_argument("--ttl", type=int, default=600)
    p_ca.add_argument("--label", default=None)
    p_ca.add_argument("--pid", type=int, default=None)

    # renew
    p_renew = sub.add_parser("renew", help="Renew a slot lease")
    p_renew.add_argument("--slot", required=True)
    p_renew.add_argument("--pid", type=int, default=None)
    p_renew.add_argument("--ttl", type=int, default=None)
    p_renew.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)

    # release
    p_rel = sub.add_parser("release", help="Release a slot lease")
    p_rel.add_argument("--slot", required=True)
    p_rel.add_argument("--pid", type=int, default=None)
    p_rel.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)

    # release-auth
    p_ra = sub.add_parser("release-auth", help="Release the auth slot")
    p_ra.add_argument("--pid", type=int, default=None)

    # reap
    p_reap = sub.add_parser("reap", help="Reap dead-owner leases")
    p_reap.add_argument("--dry-run", action="store_true")
    p_reap.add_argument("--pool-size", type=int, default=_DEFAULT_POOL_SIZE)

    # status
    p_status = sub.add_parser("status", help="Show pool status")
    p_status.add_argument("--slot", default=None, help="Filter to a specific slot")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.pool_home is not None:
        os.environ["CLAUDE_POOL_HOME"] = str(args.pool_home)

    now = args.now if args.now is not None else time.time()

    dispatch = {
        "gen-config": cmd_gen_config,
        "merge-state": cmd_merge_state,
        "init": cmd_init,
        "claim": cmd_claim,
        "claim-auth": cmd_claim_auth,
        "renew": cmd_renew,
        "release": cmd_release,
        "release-auth": cmd_release_auth,
        "reap": cmd_reap,
        "status": cmd_status,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        return E_USAGE

    return fn(args, now)


if __name__ == "__main__":
    sys.exit(main())
