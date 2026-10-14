#!/usr/bin/env python3
"""activity_log.py — the runtime, company-agnostic generalization of
Brightline's `tracking/activity_log/log_action.py` (plan §11 item 2, §14 P1).

The ONLY way semantic (manual) entries enter a company's activity log.
Requires `--company <slug>` on every subcommand; paths are resolved from
that company's pack (`company.py load_pack`) via `paths.activity_log_dir`
(default `.claude/gtm/state/activity_log`), never hardcoded.

Subcommands
-----------
    add                 append one manual entry
    render              regenerate ACTIVITY_LOG.md from both JSONL files
    check               validate every line of both JSONL files + hash chain
    backfill-changelog  one-time import of an existing markdown changelog
    audit               list unexplained mutating-change CLUSTERS
    explain             write a manual entry that closes one audit cluster

Never rewrites an existing line. Never silently drops or coerces a bad
record on write — validation failures exit non-zero with a clear message.
Missing is never rendered as zero; an empty section says so explicitly.

Hash chain (new vs. the Brightline original): every NEW line written by this
module carries `prev_hash` = sha256 of the previous line's raw bytes (hex
digest). A genesis line (first line ever written by this tool for a company)
carries `prev_hash: null`. Legacy lines with no `prev_hash` key are accepted
as an UNCHAINED PREFIX — the chain only needs to be unbroken from the first
chained line onward. `check` verifies the chain and reports a break
(non-zero exit) — see `verify_chain()`.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - stdlib on py3.9+, always present in practice
    ZoneInfo = None  # type: ignore[assignment,misc]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import company as company_mod  # noqa: E402  (import after sys.path shim)

DENVER_TZ_NAME = "America/Denver"

# Base systems every company shares (plan §11.2: "SYSTEMS = the pack's
# scope.channels_in_scope ∪ {youtube, meta_ads, call_tracking, linkedin,
# website_static, csa_scout, other} ∪ the original list"). "the original
# list" = the full Brightline SYSTEMS tuple, preserved so every legacy
# Brightline log line's `system` value stays valid post-migration.
_ORIGINAL_SYSTEMS = (
    "google_ads",
    "lsa",
    "gbp_remodeling",
    "gbp_restoration",
    "facebook_remodeling",
    "facebook_restoration",
    "instagram",
    "website_remodeling",
    "website_restoration",
    "gtm",
    "ga4",
    "search_console",
    "csa_scout",
    "angi",
    "thumbtack",
    "yelp",
    "bbb",
    "houzz",
    "nextdoor",
    "apple_business",
    "bing_places",
    "mailchimp",
    "email",
    "drive",
    "crm_tracker",
    "other",
)
_ADDED_SYSTEMS = (
    "youtube",
    "meta_ads",
    "call_tracking",
    "linkedin",
    "website_static",
    "csa_scout",
    "other",
    "local_files",
    "agent_dispatch",
    # Generic (non-brand-specific) systems the runtime host->system mapping
    # (harvest_tool_trail.py's DEFAULT_HOST_SYSTEMS, blocker 2) can produce
    # for a company that hasn't declared per-brand system names the way
    # Brightline's migrated pack does (gbp_remodeling/gbp_restoration etc):
    "gbp",
    "facebook",
    "website_wordpress",
    # The registered fallback for a browser call whose host maps to no
    # known system at all (was a hardcoded, unregistered literal before
    # blocker 2's fix — now a real, always-valid system so audit/explain
    # never choke on it).
    "gtm_browser",
)

ACTIONS = (
    "create",
    "update",
    "delete",
    "remove_association",
    "disable",
    "enable",
    "upload",
    "import",
    "export",
    "read_baseline",
    "draft",
    "schedule",
    "publish",
    "test",
    "config",
    "decision",
)

STATUSES = ("done", "failed", "partial", "planned")

# Actions for which --undo is NOT required (nothing to reverse, or the
# action is itself a read/record of something that already happened
# elsewhere).
UNDO_OPTIONAL_ACTIONS = {"read_baseline", "export", "decision"}

REDACT_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)

REQUIRED_ADD_FIELDS = ("system", "action", "object", "why", "actor")

FEATURE_STATUSES = {"used", "partial", "unused", "planned", "not_applicable"}
FEATURE_COLUMNS = ("feature", "status", "log_ids", "notes", "source")

REQUIRED_LOG_FIELDS = ("id", "ts", "system", "action", "object", "why", "actor", "source", "status", "approval")
REQUIRED_TRAIL_FIELDS = ("tool_use_id", "ts", "session_id", "tool", "system")

# audit clustering constants (unchanged from the Brightline original)
DEFAULT_AUDIT_EXCLUDED_SYSTEMS = {"local_files", "agent_dispatch"}
CLUSTER_GAP_MINUTES = 10
CLUSTER_EXPLAIN_WINDOW_MINUTES = 15


class ValidationError(Exception):
    pass


# --------------------------------------------------------------------------
# Per-company paths
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CompanyPaths:
    slug: str
    home: Path
    log_jsonl: Path
    log_md: Path
    trail_jsonl: Path
    feature_inventory_dir: Path
    lock_file: Path
    mirror_dir: Path | None
    mirror_basename: str
    mirror_title: str
    timezone: str
    systems: tuple[str, ...]


def _default_mirror_basename(slug: str, pack: dict[str, Any]) -> str:
    """<DisplayName>_Activity_Log, title-cased with spaces -> underscores.
    Brightline's pack sets mirror_basename explicitly to 'Brightline_Activity_Log'
    (matching the file the operator already uses); this default only applies
    when a pack doesn't set one."""
    label = pack.get("legal_name") or slug
    words = re.split(r"[\s_-]+", str(label).strip())
    title = "".join(w[:1].upper() + w[1:] if w else "" for w in words)
    return f"{title}_Activity_Log"


def _default_mirror_title(slug: str, pack: dict[str, Any]) -> str:
    """The mirror's page/header title (blocker 8): display_names[0] (e.g.
    'Brightline Remodeling'), falling back to legal_name, NEVER the
    lowercase slug -- the previous version used paths.slug directly, which
    rendered a lowercase, un-Title-Cased company name in the operator-
    facing <title>/<h1>. This default only applies when a pack doesn't set
    mirror_title explicitly (Brightline's pack sets it to its exact
    pre-migration title, 'Brightline Activity Log')."""
    display_names = pack.get("display_names")
    if isinstance(display_names, list) and display_names and isinstance(display_names[0], str) and display_names[0].strip():
        label = display_names[0]
    else:
        label = pack.get("legal_name") or slug
    return f"{label} Activity Log"


def resolve_paths(slug: str) -> CompanyPaths:
    """Resolves every path this module writes/reads for `slug`, from its
    pack's `paths.activity_log_dir` (default `.claude/gtm/state/activity_log`)
    and `mirror_dir` (only written when the pack sets it — plan §11.2). Env
    override `TS_ACTIVITY_MIRROR_DIR` still works, for tests, and takes
    precedence over the pack's own `mirror_dir` when set (test isolation)."""
    home = company_mod.resolve_home(slug)
    pack = company_mod.load_pack(slug)
    paths_cfg = pack.get("paths") if isinstance(pack.get("paths"), dict) else {}
    activity_dir_rel = paths_cfg.get("activity_log_dir") or ".claude/gtm/state/activity_log"
    activity_dir = home / activity_dir_rel

    mirror_dir: Path | None = None
    env_mirror = os.environ.get("TS_ACTIVITY_MIRROR_DIR")
    if env_mirror:
        mirror_dir = Path(env_mirror)
    elif pack.get("mirror_dir"):
        mirror_dir = Path(str(pack["mirror_dir"])).expanduser()

    mirror_basename = pack.get("mirror_basename") or _default_mirror_basename(slug, pack)
    mirror_title = pack.get("mirror_title") or _default_mirror_title(slug, pack)

    scope = pack.get("scope") if isinstance(pack.get("scope"), dict) else {}
    channels_in_scope = scope.get("channels_in_scope") if isinstance(scope.get("channels_in_scope"), list) else []
    systems = tuple(
        sorted(
            set(_ORIGINAL_SYSTEMS)
            | set(_ADDED_SYSTEMS)
            | {c for c in channels_in_scope if isinstance(c, str)}
        )
    )

    return CompanyPaths(
        slug=slug,
        home=home,
        log_jsonl=activity_dir / "ACTIVITY_LOG.jsonl",
        log_md=activity_dir / "ACTIVITY_LOG.md",
        trail_jsonl=activity_dir / "TOOL_TRAIL.jsonl",
        feature_inventory_dir=home / (paths_cfg.get("feature_inventory_dir") or ".claude/gtm/state/feature_inventory"),
        lock_file=activity_dir / ".activity_log.lock",
        mirror_dir=mirror_dir,
        mirror_basename=str(mirror_basename),
        mirror_title=str(mirror_title),
        timezone=str(pack.get("timezone") or DENVER_TZ_NAME),
        systems=systems,
    )


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------


def now_denver_iso() -> str:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(DENVER_TZ_NAME)).isoformat()
        except Exception:
            pass
    return datetime.now().isoformat()


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return REDACT_RE.sub(lambda m: f"{m.group(1)}=<redacted>", value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


@dataclass
class LockedFile:
    path: Path
    _fh: Any = field(default=None, init=False, repr=False)

    def __enter__(self) -> "LockedFile":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._fh = open(self.path, "r+")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[tuple[int, str, str]]]:
    """Returns (records, bad_lines) where bad_lines is [(line_no, raw, reason)]."""
    records: list[dict[str, Any]] = []
    bad: list[tuple[int, str, str]] = []
    if not path.exists():
        return records, bad
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                bad.append((i, stripped, f"invalid JSON: {exc}"))
                continue
            if not isinstance(obj, dict):
                bad.append((i, stripped, "top-level value is not an object"))
                continue
            records.append(obj)
    return records, bad


def _raw_lines(path: Path) -> list[str]:
    """Raw (stripped) non-empty lines, in file order — used for hash-chain
    verification, which must hash the exact bytes each line was written
    with, not a re-serialization of the parsed object."""
    if not path.exists():
        return []
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                out.append(stripped)
    return out


def _sha256_line(raw_line: str) -> str:
    return hashlib.sha256(raw_line.encode("utf-8")).hexdigest()


def _last_nonempty_line(path: Path, chunk_size: int = 65536) -> str | None:
    """Minor 17: reads ONLY the tail of `path` to find its last non-empty
    line, instead of reading the entire file (which does not scale to a
    14 MB TOOL_TRAIL.jsonl re-read on every single append). Seeks backward
    from EOF in `chunk_size`-byte chunks, growing the read window each
    iteration until at least one full line boundary is found (or the
    whole file has been consumed for a file smaller than one chunk).
    Returns None for an empty/missing file."""
    if not path.exists():
        return None
    file_size = path.stat().st_size
    if file_size == 0:
        return None
    with open(path, "rb") as fh:
        read_size = min(chunk_size, file_size)
        while True:
            fh.seek(file_size - read_size)
            data = fh.read(read_size)
            # Strip exactly one trailing newline (the file's own final
            # line terminator) before splitting, so a well-formed file
            # ending in "...}\n" doesn't produce a spurious empty last
            # element.
            stripped_tail = data.rstrip(b"\n")
            lines = stripped_tail.split(b"\n")
            # If we have more than one line, OR we've already read the
            # entire file, the first (or only) surviving line is complete
            # -- take the LAST non-empty one.
            if len(lines) > 1 or read_size >= file_size:
                for candidate in reversed(lines):
                    text = candidate.decode("utf-8", errors="replace").strip()
                    if text:
                        return text
                return None
            # Only one (possibly partial) line found and more file remains
            # -- grow the read window and try again.
            read_size = min(read_size * 2, file_size)


# --------------------------------------------------------------------------
# TOOL_TRAIL.jsonl.ids sidecar (minor 17/#20)
#
# nit fix: this whole block used to live in harvest_tool_trail.py, and
# `cmd_check` below needed a DEFERRED import of that module (with a PLC0415
# suppression comment on the import line) purely to reach
# verify_sidecar_matches_trail — a real circular-import workaround, since
# harvest_tool_trail.py imports THIS module at its own top level. Moving
# the sidecar helpers here (a module harvest_tool_trail.py already
# imports unconditionally) removes the cycle and the noqa entirely:
# harvest_tool_trail.py now reaches every one of these names via its own
# `activity_log_mod.<name>` aliases (module-level, right after its
# `import activity_log as activity_log_mod`), so no behavior changes for
# any existing caller in either module.
# --------------------------------------------------------------------------


def _ids_sidecar_path(trail_path: Path) -> Path:
    """Minor 17: the sidecar membership index for `trail_path` -- a header
    line (#20: `{"size": <trail byte size>, "lines": <trail line count>}`
    at the time the sidecar was last synced) followed by one tool_use_id
    per line, kept in sync with every _append_chained_trail call (see
    harvest_tool_trail.py). Reading this file for membership avoids
    re-parsing the entire (potentially 14 MB) trail JSONL on every harvest
    run."""
    return trail_path.with_suffix(trail_path.suffix + ".ids")


def _trail_stats(path: Path) -> tuple[int, int]:
    """#20: (byte size, line count) of a trail JSONL file, used to detect
    sidecar drift.

    Nit fix (docstring correction + real optimization): this used to claim
    "the common, fast path (sidecar present and matching) never calls
    this" -- FALSE, and had been false since #20 landed: every
    `_load_ids_from_sidecar` call (the sidecar-membership READ path,
    called on every harvest run and every `_flush_locked` reload)
    unconditionally calls this to get `current_size, current_lines` for
    its drift comparison, which is a full read of the whole trail
    counting every newline, not the O(1) stat() the docstring implied.
    The README's "O(existing id count)" framing for that read path
    overstated the saving the same way.

    What actually IS true, and is what this function is now optimized
    for: the common case is a MATCHING header (no drift), where only the
    byte SIZE needs to agree -- comparing `path.stat().st_size` (a single
    O(1) syscall) against the sidecar's own recorded size first, and only
    reading the file to count lines when sizes already match (needed to
    also confirm the line count, since two different files can share a
    byte size) or when a real rescan is unavoidable (drift, or building
    the sidecar for the first time), is what actually earns "fast path"
    for the read side, rather than merely asserting it in prose. See
    `_size_matches` below, which every caller of this size-then-lines
    shape should prefer over calling this function directly when it
    already has a size to compare against."""
    if not path.exists():
        return (0, 0)
    size = path.stat().st_size
    lines = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            lines += chunk.count(b"\n")
    return (size, lines)


def _path_size(path: Path) -> int:
    """O(1) byte size via a single stat() syscall -- never a content read.
    `0` for a missing file, matching `_trail_stats`'s own convention."""
    return path.stat().st_size if path.exists() else 0


def _read_sidecar_header_and_ids(sidecar: Path) -> tuple[dict[str, Any] | None, set[str]]:
    """Returns (header_dict_or_None, ids). The header is the sidecar's
    FIRST line, parsed as JSON if it looks like a header object (has
    both "size" and "lines" keys); any line that isn't a header-shaped
    JSON object is treated as an id line instead -- this keeps a
    pre-#20 sidecar (bare ids, no header at all) readable as "ids only,
    no header" rather than corrupting its first id into a parse
    failure."""
    if not sidecar.exists():
        return None, set()
    header: dict[str, Any] | None = None
    ids: set[str] = set()
    with open(sidecar, "r", encoding="utf-8") as fh:
        first = True
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if first:
                first = False
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict) and "size" in obj and "lines" in obj:
                    header = obj
                    continue
                # Not a header line -- legacy sidecar format, this line IS
                # an id.
            ids.add(line)
    return header, ids


def _load_ids_from_sidecar(trail_path: Path) -> set[str] | None:
    """Returns the sidecar's id set, or None if the sidecar doesn't exist
    yet, OR if it exists but has DRIFTED from the real trail file (#20:
    a lagging sidecar, a crash between the two appends, or an
    out-of-band overwrite of TOOL_TRAIL.jsonl) -- either way, the caller
    falls back to a full JSONL scan + sidecar rebuild, exactly as it does
    for a genuinely missing sidecar. A sidecar with no header at all
    (pre-#20 format) is treated as drifted unconditionally, since there is
    nothing to compare against -- it gets rebuilt with a header on this
    run.

    KNOWN BLIND SPOT (documented, not asserted as correct): drift is
    detected by comparing (byte size, line count) only -- an out-of-band
    overwrite that replaces the trail's content with something of the
    EXACT same size and line count (e.g. a fixed-width record edited
    in-place) is indistinguishable from "unchanged" and is silently
    trusted, stale. Strengthening this (e.g. adding a hash of the last
    line, or of the whole file) is a real future improvement; if made, it
    should never be treated as breaking a test that asserts today's
    same-shape-overwrite behavior as INTENDED -- no such test exists here,
    deliberately (see test_sidecar_used_on_second_call_without_rescanning_
    jsonl_when_unchanged for how the fast path is proved instead: by
    observation that the full-scan fallback never runs on a genuinely
    unchanged trail, not by asserting a stale read as correct)."""
    sidecar = _ids_sidecar_path(trail_path)
    header, ids = _read_sidecar_header_and_ids(sidecar)
    if header is None:
        return None
    # Nit fix: check the O(1) byte size FIRST -- on any mismatch the
    # sidecar is drifted regardless of line count, so there is no reason
    # to pay for a full-file line-count read at all. Only when the size
    # already matches (the common, truly-fast case) is `_trail_stats`
    # called to also confirm the line count (two different files can
    # coincidentally share a byte size, so size alone is not sufficient
    # proof of a match).
    if header.get("size") != _path_size(trail_path):
        return None
    current_size, current_lines = _trail_stats(trail_path)
    if header.get("size") != current_size or header.get("lines") != current_lines:
        return None
    return ids


def _scan_ids_from_jsonl(path: Path) -> set[str]:
    """The full-file fallback scan (only used to build a sidecar the first
    time, or as a correctness fallback if the sidecar is ever missing or
    drifted)."""
    ids: set[str] = set()
    if not path.exists():
        return ids
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = obj.get("tool_use_id")
            if isinstance(tid, str):
                ids.add(tid)
    return ids


def _write_sidecar_with_header(trail_path: Path, size: int, lines: int, ids: set[str]) -> None:
    """Writes the sidecar's header line (EXACTLY `size`/`lines` as given --
    never recomputed here) followed by every id. Split out from
    _rebuild_ids_sidecar (which computes size/lines itself via a full
    _trail_stats scan, correct for the "we don't already know the trail's
    current shape" case) so a caller that already knows the trail's exact
    post-write shape (#20 — harvest_tool_trail.py's
    _append_many_chained_trail_locked, which knows exactly how many bytes
    each line it just wrote added) never pays for a redundant full-file
    line-count scan."""
    sidecar = _ids_sidecar_path(trail_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    header = json.dumps({"size": size, "lines": lines}, sort_keys=True)
    body = "\n".join(sorted(ids))
    content = header + "\n" + body + ("\n" if ids else "")
    # Major finding #21-regression fix: a FIXED tmp filename
    # (sidecar.tmp) lets two concurrent writers race os.replace -- one
    # writer's write() can land after the other's, and one process's
    # os.replace can raise FileNotFoundError if the other's os.replace
    # already consumed the same tmp path. mkstemp gives each writer its
    # own uniquely-named tmp file in the same directory (so os.replace
    # stays an atomic same-filesystem rename), eliminating the race
    # entirely rather than papering over one symptom of it.
    fd, tmp_name = tempfile.mkstemp(
        prefix=sidecar.name + ".", suffix=".tmp", dir=str(sidecar.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, sidecar)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _rebuild_ids_sidecar(trail_path: Path, ids: set[str]) -> None:
    """#20: writes the header line (current trail size + line count,
    computed via a full _trail_stats scan) FIRST, then every id -- so the
    sidecar is self-describing and the next run's drift check has
    something to compare against. This is the CORRECTNESS-FALLBACK path
    (a genuinely missing/drifted sidecar, or the first time it's ever
    built) where the caller does NOT already know the trail's current
    (size, lines) shape and a real scan is unavoidable -- see
    _write_sidecar_with_header for the fast, no-rescan path used by a
    single known-shape append."""
    size, lines = _trail_stats(trail_path)
    _write_sidecar_with_header(trail_path, size, lines, ids)


def verify_sidecar_matches_trail(trail_path: Path) -> tuple[bool, str | None]:
    """#20: used by `check` (below) to verify a trail's sidecar is NOT
    drifted, independent of the harvester's own self-healing (which
    silently rebuilds on drift during a normal harvest run and would never
    surface the fact that a drift happened). Returns (ok, reason)."""
    sidecar = _ids_sidecar_path(trail_path)
    if not sidecar.exists():
        return True, None  # no sidecar yet -- nothing to be out of sync
    header, _ids = _read_sidecar_header_and_ids(sidecar)
    if header is None:
        return False, f"{sidecar.name} has no header (pre-#20 format or corrupted)"
    current_size, current_lines = _trail_stats(trail_path)
    if header.get("size") != current_size:
        return False, f"{sidecar.name} size {header.get('size')} != trail size {current_size}"
    if header.get("lines") != current_lines:
        return False, f"{sidecar.name} line count {header.get('lines')} != trail line count {current_lines}"
    return True, None


def next_id_locked(log_jsonl: Path) -> str:
    records, _ = read_jsonl(log_jsonl)
    max_n = 0
    for r in records:
        rid = r.get("id")
        if isinstance(rid, str) and rid.startswith("A") and rid[1:].isdigit():
            max_n = max(max_n, int(rid[1:]))
    return f"A{max_n + 1:04d}"


def _append_chained(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Appends `entry` to `path`, adding `prev_hash` computed from the
    current LAST raw line in the file (None if the file is empty — genesis
    line). Caller must hold the lock. Returns the entry actually written
    (with prev_hash set) so tests/callers can assert on it.

    Minor 17: uses _last_nonempty_line's tail-read instead of _raw_lines'
    whole-file read — a single append against a large (e.g. 14 MB)
    TOOL_TRAIL.jsonl no longer re-reads the entire file just to find its
    last line."""
    last_line = _last_nonempty_line(path)
    prev_hash = _sha256_line(last_line) if last_line is not None else None
    entry = dict(entry)
    entry["prev_hash"] = prev_hash
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return entry


def verify_chain(path: Path) -> tuple[bool, str | None]:
    """Verifies the hash chain of `path`. Legacy lines with no `prev_hash`
    key are an accepted UNCHAINED PREFIX; once a line carries a `prev_hash`,
    every subsequent line must carry one and it must equal sha256 of the
    exact previous raw line. Returns (ok, reason). ok=True means either no
    chained lines exist yet, or the chain from the first chained line
    onward is unbroken."""
    lines = _raw_lines(path)
    if not lines:
        return True, None
    seen_chained = False
    for i, raw in enumerate(lines):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # Malformed lines are reported by read_jsonl's bad_lines path,
            # not here — skip for chain purposes (can't verify a hash over
            # something we can't even parse a prev_hash field out of, but
            # since we hash the RAW line text, still attempt it below).
            obj = None
        has_prev_hash = isinstance(obj, dict) and "prev_hash" in obj
        if not seen_chained:
            if has_prev_hash:
                seen_chained = True
            else:
                continue  # unchained prefix
        else:
            if not has_prev_hash:
                return False, f"line {i + 1}: missing prev_hash after chain had started"
        if seen_chained and isinstance(obj, dict):
            expected_prev = _sha256_line(lines[i - 1]) if i > 0 else None
            if obj.get("prev_hash") != expected_prev:
                return False, f"line {i + 1}: prev_hash mismatch (chain broken or line tampered)"
    return True, None


# --------------------------------------------------------------------------
# `add`
# --------------------------------------------------------------------------


def validate_add_fields(fields: dict[str, Any], systems: tuple[str, ...]) -> None:
    system = fields.get("system")
    if system not in systems:
        raise ValidationError(f"--system must be one of {systems}, got {system!r}")
    action = fields.get("action")
    if action not in ACTIONS:
        raise ValidationError(f"--action must be one of {ACTIONS}, got {action!r}")
    status = fields.get("status")
    if status not in STATUSES:
        raise ValidationError(f"--status must be one of {STATUSES}, got {status!r}")
    for req in REQUIRED_ADD_FIELDS:
        val = fields.get(req)
        if not isinstance(val, str) or not val.strip():
            raise ValidationError(f"--{req} is required and must be non-empty")
    # Minor 16: a NEW entry's actor must be an unambiguous shape -- a known
    # agent shape (<seat>:<agent_id>, main-session, ...) or an explicit
    # non-agent (owner..., outside:<who>). Legacy lines are unaffected
    # (this check runs only here, on write, never on read).
    actor = fields.get("actor")
    if not is_valid_new_actor_shape(actor):
        raise ValidationError(
            f"--actor {actor!r} is ambiguous: it must be either an agent shape "
            "(<seat>:<agent_id> where agent_id looks like a[0-9a-f]{8,}, 'main-session', "
            "'agent', or anything starting with 'main-session') or an explicit non-agent "
            "('owner' or 'owner ...', or 'outside:<who>')"
        )
    undo = fields.get("undo")
    if action not in UNDO_OPTIONAL_ACTIONS:
        if not isinstance(undo, str) or not undo.strip():
            raise ValidationError(
                f"--undo is required for action={action!r} "
                f"(optional only for {sorted(UNDO_OPTIONAL_ACTIONS)})"
            )


def build_entry(args: argparse.Namespace, systems: tuple[str, ...]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "system": args.system,
        "action": args.action,
        "object": args.object,
        "before": args.before,
        "after": args.after,
        "why": args.why,
        "actor": args.actor,
        "evidence": list(args.evidence) if args.evidence else [],
        "undo": args.undo,
        "approval": args.approval,
        "status": args.status,
        "account": args.account,
        "notes": args.notes,
    }
    validate_add_fields(fields, systems)
    ts = args.ts if args.ts else now_denver_iso()
    entry = {
        "ts": ts,
        "source": "manual",
        **fields,
    }
    return redact(entry)


def cmd_add(args: argparse.Namespace) -> int:
    paths = resolve_paths(args.company)
    try:
        entry = build_entry(args, paths.systems)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    with LockedFile(paths.lock_file):
        entry["id"] = next_id_locked(paths.log_jsonl)
        entry = _append_chained(paths.log_jsonl, entry)
    print(f"logged {entry['id']}: {entry['system']}/{entry['action']} {entry['object']!r}")
    render_all(paths)
    return 0


# --------------------------------------------------------------------------
# `check`
# --------------------------------------------------------------------------


def cmd_check(args: argparse.Namespace) -> int:
    # Major finding #2 (regression fix): `check` now fails whenever the
    # sidecar has drifted (#20), but it used to read the trail and the
    # sidecar with no lock at all. `_append_many_chained_trail_locked`
    # (harvest_tool_trail.py) appends every record of a flush to the
    # trail FIRST and rewrites the sidecar ONCE at the end -- so while a
    # harvest flush is running, the trail is LEGITIMATELY ahead of the
    # sidecar for the whole span of that flush, and an unlocked concurrent
    # `check` (a scheduled audit, or another agent) could read the trail
    # mid-flush and report "sidecar drifted" even though nothing is
    # actually wrong. Taking the company's own activity-log lock (the SAME
    # lock `add` and every harvest flush already take) for the whole
    # read+verify pass makes `check` wait for a flush in progress to
    # finish, rather than observe a real momentary state as a false
    # positive.
    #
    # Nit fix: `check` is a READ-ONLY verification, but `LockedFile.
    # __enter__` unconditionally creates the lock file's parent directory
    # and touches the lock file itself -- so running `check` against a
    # home that was never initialized (or a mistyped slug/layout) used to
    # CREATE `.claude/gtm/state/activity_log/` and its lock file there,
    # purely as a side effect of verifying nothing exists yet. When the
    # lock file's parent directory doesn't exist, there is no concurrent
    # flush that could possibly be racing this read (a flush always
    # creates that directory before it ever touches the lock), so the
    # lock is skipped entirely -- `_cmd_check_locked` itself already
    # handles a missing trail/log file cleanly via `read_jsonl`'s own
    # missing-file contract (returns empty, not an error).
    paths = resolve_paths(args.company)
    if not paths.lock_file.parent.exists():
        return _cmd_check_locked(paths)
    with LockedFile(paths.lock_file):
        return _cmd_check_locked(paths)


def _cmd_check_locked(paths: CompanyPaths) -> int:
    exit_code = 0

    log_records, log_bad = read_jsonl(paths.log_jsonl)
    trail_records, trail_bad = read_jsonl(paths.trail_jsonl)

    for lineno, raw, reason in log_bad:
        print(f"ACTIVITY_LOG.jsonl:{lineno}: {reason}", file=sys.stderr)
        exit_code = 1
    for lineno, raw, reason in trail_bad:
        print(f"TOOL_TRAIL.jsonl:{lineno}: {reason}", file=sys.stderr)
        exit_code = 1

    for i, r in enumerate(log_records, start=1):
        missing = [f for f in REQUIRED_LOG_FIELDS if not r.get(f)]
        if missing:
            print(f"ACTIVITY_LOG.jsonl record #{i} (id={r.get('id')!r}) missing fields: {missing}", file=sys.stderr)
            exit_code = 1
        if r.get("system") not in paths.systems:
            print(f"ACTIVITY_LOG.jsonl record #{i} (id={r.get('id')!r}) has unknown system {r.get('system')!r}", file=sys.stderr)
            exit_code = 1
        if r.get("action") not in ACTIONS:
            print(f"ACTIVITY_LOG.jsonl record #{i} (id={r.get('id')!r}) has unknown action {r.get('action')!r}", file=sys.stderr)
            exit_code = 1

    for i, r in enumerate(trail_records, start=1):
        missing = [f for f in REQUIRED_TRAIL_FIELDS if not r.get(f)]
        if missing:
            print(f"TOOL_TRAIL.jsonl record #{i} (tool_use_id={r.get('tool_use_id')!r}) missing fields: {missing}", file=sys.stderr)
            exit_code = 1

    log_chain_ok, log_chain_reason = verify_chain(paths.log_jsonl)
    if not log_chain_ok:
        print(f"ACTIVITY_LOG.jsonl: hash chain broken: {log_chain_reason}", file=sys.stderr)
        exit_code = 1
    trail_chain_ok, trail_chain_reason = verify_chain(paths.trail_jsonl)
    if not trail_chain_ok:
        print(f"TOOL_TRAIL.jsonl: hash chain broken: {trail_chain_reason}", file=sys.stderr)
        exit_code = 1

    # #20: also verifies the trail's sidecar `.ids` index (if any) is not
    # DRIFTED from the trail file itself -- independent of the harvester's
    # own self-healing (which silently rebuilds on drift during a normal
    # harvest run and would never surface that a drift happened at all).
    # nit fix: verify_sidecar_matches_trail is defined in THIS module now
    # (moved from harvest_tool_trail.py, which imports activity_log at its
    # own top level -- the reverse import used to need a deferred,
    # PLC0415-suppressed import right here to avoid a real circular
    # import; that workaround is gone along with the cycle it worked
    # around).
    sidecar_ok, sidecar_reason = verify_sidecar_matches_trail(paths.trail_jsonl)
    if not sidecar_ok:
        print(f"TOOL_TRAIL.jsonl: sidecar drifted: {sidecar_reason}", file=sys.stderr)
        exit_code = 1

    print(f"ACTIVITY_LOG.jsonl: {len(log_records)} valid record(s), {len(log_bad)} bad line(s)")
    print(f"TOOL_TRAIL.jsonl: {len(trail_records)} valid record(s), {len(trail_bad)} bad line(s)")
    return exit_code


# --------------------------------------------------------------------------
# `render`
# --------------------------------------------------------------------------


def _parse_ts(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _date_key(ts: Any) -> str:
    dt = _parse_ts(ts)
    if dt is None:
        return "(unknown date)"
    return dt.date().isoformat()


def render_log_section(log_records: list[dict[str, Any]], company_label: str) -> list[str]:
    lines: list[str] = []
    lines.append(f"# {company_label} Activity Log")
    lines.append("")
    lines.append(
        "This file is GENERATED by `activity_log.py render` — do not hand-edit it. "
        "The source of truth is `ACTIVITY_LOG.jsonl` (manual entries) plus "
        "`TOOL_TRAIL.jsonl` (mechanical capture)."
    )
    lines.append("")

    by_system: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for r in log_records:
        by_system[r.get("system", "?")] = by_system.get(r.get("system", "?"), 0) + 1
        by_action[r.get("action", "?")] = by_action.get(r.get("action", "?"), 0) + 1

    lines.append("## Summary")
    lines.append("")
    lines.append(f"Total manual entries: {len(log_records)}")
    lines.append("")
    if not log_records:
        lines.append("No manual entries recorded yet.")
    else:
        lines.append("**By system:**")
        for system in sorted(by_system):
            lines.append(f"- {system}: {by_system[system]}")
        lines.append("")
        lines.append("**By action:**")
        for action in sorted(by_action):
            lines.append(f"- {action}: {by_action[action]}")
    lines.append("")

    lines.append("## Entries (newest first, grouped by date)")
    lines.append("")
    if not log_records:
        lines.append("No manual entries recorded yet.")
        lines.append("")
        return lines

    def sort_key(r: dict[str, Any]) -> tuple[str, str]:
        ts = r.get("ts") if isinstance(r.get("ts"), str) else ""
        rid = r.get("id") if isinstance(r.get("id"), str) else ""
        return (ts, rid)

    ordered = sorted(log_records, key=sort_key, reverse=True)

    groups: dict[str, list[dict[str, Any]]] = {}
    for r in ordered:
        groups.setdefault(_date_key(r.get("ts")), []).append(r)

    for date_key in sorted(groups.keys(), reverse=True):
        lines.append(f"### {date_key}")
        lines.append("")
        for r in groups[date_key]:
            time_part = ""
            dt = _parse_ts(r.get("ts"))
            if dt is not None:
                time_part = dt.strftime("%H:%M")
            evidence = r.get("evidence") or []
            evidence_str = "; ".join(evidence) if evidence else "(none)"
            before = r.get("before") if r.get("before") not in (None, "") else "(n/a)"
            after = r.get("after") if r.get("after") not in (None, "") else "(n/a)"
            undo = r.get("undo") if r.get("undo") not in (None, "") else "(n/a)"
            account = f" [{r.get('account')}]" if r.get("account") else ""
            lines.append(
                f"- **{r.get('id')}** · {time_part} · `{r.get('system')}`{account} · "
                f"**{r.get('action')}** · {r.get('object')}"
            )
            lines.append(f"  before → after: {before} → {after}")
            lines.append(f"  why: {r.get('why')}")
            lines.append(f"  actor: {r.get('actor')} · approval: {r.get('approval')} · status: {r.get('status')}")
            lines.append(f"  evidence: {evidence_str}")
            lines.append(f"  undo: {undo}")
            if r.get("notes"):
                lines.append(f"  notes: {r.get('notes')}")
            lines.append("")
    return lines


def render_trail_section(trail_records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    lines.append("## Mechanical trail")
    lines.append("")
    lines.append(
        f"Total captured tool-trail record(s): {len(trail_records)} "
        "(written by `harvest_tool_trail.py` — every tool call found in the "
        "Claude Code transcripts that touched this company's identity hosts)."
    )
    lines.append("")
    if not trail_records:
        lines.append("No mechanical trail records captured yet.")
        lines.append("")
        return lines

    counts: dict[tuple[str, str, str], int] = {}
    for r in trail_records:
        day = _date_key(r.get("ts"))
        system = r.get("system", "?")
        actor = r.get("actor_label", "?")
        key = (day, system, actor)
        counts[key] = counts.get(key, 0) + 1

    lines.append("### Counts per day x system x actor")
    lines.append("")
    lines.append("| Date | System | Actor | Count |")
    lines.append("|---|---|---|---|")
    for key in sorted(counts.keys(), reverse=True):
        day, system, actor = key
        lines.append(f"| {day} | {system} | {actor} | {counts[key]} |")
    lines.append("")

    def sort_key(r: dict[str, Any]) -> str:
        return r.get("ts") if isinstance(r.get("ts"), str) else ""

    ordered = sorted(trail_records, key=sort_key, reverse=True)
    mutating_ordered = [r for r in ordered if r.get("mutating")]
    recent = ordered[:200]

    lines.append(f"### 200 most recent mutating interactions ({len(mutating_ordered)} total mutating record(s))")
    lines.append("")
    recent_mutating = [r for r in recent if r.get("mutating")][:200]
    if not recent_mutating:
        lines.append("No mutating trail records in the most recent 200 interactions.")
    else:
        for r in recent_mutating:
            dt = _parse_ts(r.get("ts"))
            ts_str = dt.strftime("%Y-%m-%d %H:%M") if dt else "(unknown time)"
            detail = r.get("detail")
            detail_str = ""
            if isinstance(detail, dict):
                detail_str = "; ".join(f"{k}={v}" for k, v in detail.items() if v)
            elif isinstance(detail, str):
                detail_str = detail
            detail_str = (detail_str[:160] + "…") if len(detail_str) > 160 else detail_str
            lines.append(
                f"- {ts_str} · `{r.get('system')}` · {r.get('actor_label', '?')} · "
                f"`{r.get('tool')}` · {r.get('url') or '(no url)'} · {detail_str}"
            )
    lines.append("")
    return lines


def load_feature_inventories(feature_inventory_dir: Path) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    if not feature_inventory_dir.is_dir():
        return out
    for csv_path in sorted(feature_inventory_dir.glob("*.csv")):
        rows: list[dict[str, str]] = []
        try:
            with open(csv_path, "r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    rows.append({k: (v or "") for k, v in row.items()})
        except OSError:
            rows = []
        out[csv_path.stem] = rows
    return out


def render_feature_section(inventories: dict[str, list[dict[str, str]]]) -> list[str]:
    lines: list[str] = []
    lines.append("## Feature utilization")
    lines.append("")
    lines.append(
        "Built from every `feature_inventory/*.csv`. Each platform's inventory is "
        "authored by the owning GTM specialist and updated whenever a feature's "
        "status changes."
    )
    lines.append("")
    if not inventories:
        lines.append("No feature_inventory/*.csv files found.")
        lines.append("")
        return lines

    for system in sorted(inventories.keys()):
        rows = inventories[system]
        lines.append(f"### {system}")
        lines.append("")
        if not rows:
            lines.append("No rows recorded yet.")
            lines.append("")
            continue
        status_counts: dict[str, int] = {}
        for row in rows:
            status = row.get("status", "") or "(blank)"
            status_counts[status] = status_counts.get(status, 0) + 1
        lines.append("Counts by status: " + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
        lines.append("")
        not_used = [row for row in rows if row.get("status") in ("unused", "partial", "planned")]
        if not_used:
            lines.append("| Feature | Status | Log IDs | Notes | Source |")
            lines.append("|---|---|---|---|---|")
            for row in not_used:
                lines.append(
                    f"| {row.get('feature','')} | {row.get('status','')} | "
                    f"{row.get('log_ids','')} | {row.get('notes','')} | {row.get('source','')} |"
                )
        else:
            lines.append("No unused/partial/planned features recorded.")
        lines.append("")
    return lines


def cmd_render(paths: CompanyPaths) -> int:
    log_records, log_bad = read_jsonl(paths.log_jsonl)
    trail_records, trail_bad = read_jsonl(paths.trail_jsonl)
    if log_bad:
        print(f"warning: {len(log_bad)} bad line(s) in ACTIVITY_LOG.jsonl skipped from render", file=sys.stderr)
    if trail_bad:
        print(f"warning: {len(trail_bad)} bad line(s) in TOOL_TRAIL.jsonl skipped from render", file=sys.stderr)

    lines: list[str] = []
    lines.extend(render_log_section(log_records, paths.slug))
    lines.extend(render_trail_section(trail_records))
    inventories = load_feature_inventories(paths.feature_inventory_dir)
    lines.extend(render_feature_section(inventories))

    paths.log_md.parent.mkdir(parents=True, exist_ok=True)
    paths.log_md.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"rendered {paths.log_md}")
    return 0


def render_mirrors(paths: CompanyPaths) -> None:
    """Writes owner-facing mirrors into paths.mirror_dir — but ONLY when the
    pack (or the test env override) sets one (plan §11.2: "Mirrors are
    written only when the pack sets mirror_dir"). Writes BOTH the markdown
    mirror and the HTML mirror (ported from the Brightline original's
    render_owner_html — the operator uses the HTML mirror directly, e.g.
    ~/Desktop/Brightline/Brightline_Activity_Log.html, so it must be kept,
    not just the .md)."""
    if paths.mirror_dir is None:
        return
    log_records, _ = read_jsonl(paths.log_jsonl)
    inventories = load_feature_inventories(paths.feature_inventory_dir)
    paths.mirror_dir.mkdir(parents=True, exist_ok=True)
    (paths.mirror_dir / f"{paths.mirror_basename}.md").write_text(
        render_owner_markdown(log_records, paths), encoding="utf-8"
    )
    (paths.mirror_dir / f"{paths.mirror_basename}.html").write_text(
        render_owner_html(log_records, inventories, paths), encoding="utf-8"
    )


def _mirror_last_updated(paths: CompanyPaths) -> str:
    """Human-readable 'last updated' timestamp in the PACK's own timezone
    (not a hardcoded Denver — the Brightline original hardcoded Denver
    because Brightline was its only company; this generalization reads
    paths.timezone, which resolve_paths() populates from company.json's
    timezone, defaulting to Denver only when a pack doesn't set one)."""
    if ZoneInfo is not None:
        try:
            dt = datetime.now(ZoneInfo(paths.timezone))
            return dt.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d %H:%M (local time, tz unavailable)")


def render_owner_markdown(log_records: list[dict[str, Any]], paths: CompanyPaths) -> str:
    """The owner-facing markdown mirror: manual entries only, newest first,
    no tool-trail noise (that stays in the full ACTIVITY_LOG.md next to the
    tool). Ported verbatim (format-wise) from the Brightline original's
    render_owner_markdown."""
    lines: list[str] = []
    lines.append(f"# {paths.mirror_title}")
    lines.append("")
    lines.append(f"Last updated: {_mirror_last_updated(paths)}")
    lines.append(f"Total manual entries: {len(log_records)}")
    lines.append("")
    lines.append(
        "This is a mirror of the manual activity-log entries only. The full "
        "log (including the mechanical tool-trail and feature-utilization "
        "sections) lives at the source: "
        f"`{paths.log_md}`."
    )
    lines.append("")

    if not log_records:
        lines.append("No manual entries recorded yet.")
        lines.append("")
        return "\n".join(lines).rstrip("\n") + "\n"

    def sort_key(r: dict[str, Any]) -> tuple[str, str]:
        ts = r.get("ts") if isinstance(r.get("ts"), str) else ""
        rid = r.get("id") if isinstance(r.get("id"), str) else ""
        return (ts, rid)

    ordered = sorted(log_records, key=sort_key, reverse=True)

    for r in ordered:
        dt = _parse_ts(r.get("ts"))
        time_part = dt.strftime("%Y-%m-%d %H:%M MT") if dt is not None else "(unknown time)"
        evidence = r.get("evidence") or []
        evidence_str = "; ".join(evidence) if evidence else "(none)"
        before = r.get("before") if r.get("before") not in (None, "") else "(n/a)"
        after = r.get("after") if r.get("after") not in (None, "") else "(n/a)"
        undo = r.get("undo") if r.get("undo") not in (None, "") else "(n/a)"
        account = f" [{r.get('account')}]" if r.get("account") else ""
        lines.append(
            f"## {r.get('id')} · {time_part} · `{r.get('system')}`{account} · "
            f"**{r.get('action')}**"
        )
        lines.append("")
        lines.append(f"- what changed: {r.get('object')}")
        lines.append(f"- before → after: {before} → {after}")
        lines.append(f"- why: {r.get('why')}")
        lines.append(f"- who: {r.get('actor')}")
        lines.append(f"- approval: {r.get('approval')}")
        lines.append(f"- status: {r.get('status')}")
        lines.append(f"- undo: {undo}")
        lines.append(f"- evidence: {evidence_str}")
        if r.get("notes"):
            lines.append(f"- notes: {r.get('notes')}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def html_escape(value: Any) -> str:
    """Escapes a value for safe inclusion in HTML text/attribute context.
    Never trusts a field's content (redaction already strips secrets
    upstream; this is the separate, mandatory XSS-safety escape). Ported
    verbatim from the Brightline original."""
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{company_title} Activity Log</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
          margin: 0; padding: 24px; background: #f7f7f8; color: #1a1a1a; }}
  h1 {{ margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 0.9em; margin-bottom: 20px; }}
  .meta code {{ background: #eee; padding: 1px 5px; border-radius: 3px; }}
  .summary {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 24px; }}
  .summary .card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px;
                     padding: 12px 18px; min-width: 140px; }}
  .summary .card .n {{ font-size: 1.6em; font-weight: 600; display: block; }}
  .summary .card .label {{ color: #666; font-size: 0.85em; }}
  h2 {{ margin-top: 36px; border-bottom: 2px solid #ddd; padding-bottom: 6px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; margin-bottom: 12px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; vertical-align: top;
            font-size: 0.92em; }}
  th {{ background: #eef0f3; position: sticky; top: 0; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .filters {{ margin: 10px 0 16px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .filters input {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9em; }}
  .status-done {{ color: #1a7a1a; }}
  .status-failed {{ color: #b00020; }}
  .status-partial {{ color: #b06a00; }}
  .status-planned {{ color: #555; }}
  .actor-table {{ max-width: 480px; }}
  .row-hidden {{ display: none; }}
  footer {{ margin-top: 40px; color: #888; font-size: 0.8em; }}
  noscript p {{ color: #b06a00; }}
</style>
</head>
<body>
<h1>{company_title} Activity Log</h1>
<div class="meta">
  Last updated: {last_updated} &middot;
  Source JSONL: <code>{source_path}</code>
</div>
<noscript><p>JavaScript is disabled: filtering is unavailable, but every entry below is still shown in full.</p></noscript>

<div class="summary">
  <div class="card"><span class="n">{total_entries}</span><span class="label">manual entries</span></div>
  <div class="card"><span class="n">{total_actors}</span><span class="label">actors</span></div>
  <div class="card"><span class="n">{total_systems}</span><span class="label">systems touched</span></div>
</div>

<h2>Who did the work</h2>
<table class="actor-table">
  <thead><tr><th>Actor</th><th>Count</th></tr></thead>
  <tbody>
{actor_rows}
  </tbody>
</table>

<h2>Entries (newest first)</h2>
<div class="filters">
  <input type="text" id="filter-system" placeholder="Filter: system">
  <input type="text" id="filter-actor" placeholder="Filter: actor">
  <input type="text" id="filter-text" placeholder="Filter: any text">
</div>
<table id="entries-table">
  <thead>
    <tr>
      <th>ID</th><th>Time (MT)</th><th>System</th><th>Action</th><th>What changed</th>
      <th>Before &rarr; After</th><th>Why</th><th>Who</th><th>Approval</th><th>Status</th>
      <th>Undo</th><th>Evidence</th>
    </tr>
  </thead>
  <tbody>
{entry_rows}
  </tbody>
</table>

<h2>Features not yet used</h2>
{feature_sections}

<footer>Generated by <code>activity_log.py</code>. This file is regenerated on every render — do not hand-edit it.</footer>

<script>
(function () {{
  var sysBox = document.getElementById('filter-system');
  var actorBox = document.getElementById('filter-actor');
  var textBox = document.getElementById('filter-text');
  var table = document.getElementById('entries-table');
  if (!table) return;
  var rows = Array.prototype.slice.call(table.tBodies[0].rows);

  function apply() {{
    var sys = (sysBox.value || '').toLowerCase();
    var actor = (actorBox.value || '').toLowerCase();
    var text = (textBox.value || '').toLowerCase();
    rows.forEach(function (row) {{
      var rowSys = (row.getAttribute('data-system') || '').toLowerCase();
      var rowActor = (row.getAttribute('data-actor') || '').toLowerCase();
      var rowText = (row.textContent || '').toLowerCase();
      var visible = rowSys.indexOf(sys) !== -1 &&
                    rowActor.indexOf(actor) !== -1 &&
                    rowText.indexOf(text) !== -1;
      row.classList.toggle('row-hidden', !visible);
    }});
  }}

  [sysBox, actorBox, textBox].forEach(function (el) {{
    el.addEventListener('input', apply);
  }});
}})();
</script>
</body>
</html>
"""


def render_owner_html(
    log_records: list[dict[str, Any]],
    inventories: dict[str, list[dict[str, str]]],
    paths: CompanyPaths,
) -> str:
    """The owner-facing, self-contained HTML mirror. All CSS/JS is inline
    (no external hosts/CDNs/fonts). The entries table is plain static HTML
    -- the inline <script> only adds client-side filtering on top of it, so
    the page renders correctly with JS disabled (see the <noscript> notice
    and the fact that no row is ever server-side omitted). Ported verbatim
    (format-wise) from the Brightline original's render_owner_html, with
    the title parameterized by company (was a hardcoded 'Brightline')."""

    def sort_key(r: dict[str, Any]) -> tuple[str, str]:
        ts = r.get("ts") if isinstance(r.get("ts"), str) else ""
        rid = r.get("id") if isinstance(r.get("id"), str) else ""
        return (ts, rid)

    ordered = sorted(log_records, key=sort_key, reverse=True)

    actor_counts: dict[str, int] = {}
    system_set: set[str] = set()
    for r in log_records:
        actor = r.get("actor") or "(unknown)"
        actor_counts[actor] = actor_counts.get(actor, 0) + 1
        system_set.add(r.get("system") or "(unknown)")

    actor_rows = "\n".join(
        f"    <tr><td>{html_escape(actor)}</td><td>{count}</td></tr>"
        for actor, count in sorted(actor_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ) or "    <tr><td colspan=\"2\">No manual entries recorded yet.</td></tr>"

    entry_row_parts: list[str] = []
    for r in ordered:
        dt = _parse_ts(r.get("ts"))
        time_str = dt.strftime("%Y-%m-%d %H:%M") if dt is not None else "(unknown time)"
        evidence = r.get("evidence") or []
        evidence_str = "; ".join(evidence) if evidence else "(none)"
        before = r.get("before") if r.get("before") not in (None, "") else "(n/a)"
        after = r.get("after") if r.get("after") not in (None, "") else "(n/a)"
        undo = r.get("undo") if r.get("undo") not in (None, "") else "(n/a)"
        status = r.get("status") or ""
        system = r.get("system") or ""
        actor = r.get("actor") or ""
        entry_row_parts.append(
            "    <tr data-system=\"{system_attr}\" data-actor=\"{actor_attr}\">"
            "<td>{id}</td><td>{time}</td><td>{system}</td><td>{action}</td>"
            "<td>{obj}</td><td>{before} &rarr; {after}</td><td>{why}</td>"
            "<td>{actor}</td><td>{approval}</td>"
            "<td class=\"status-{status_class}\">{status}</td>"
            "<td>{undo}</td><td>{evidence}</td></tr>".format(
                system_attr=html_escape(system),
                actor_attr=html_escape(actor),
                id=html_escape(r.get("id")),
                time=html_escape(time_str),
                system=html_escape(system),
                action=html_escape(r.get("action")),
                obj=html_escape(r.get("object")),
                before=html_escape(before),
                after=html_escape(after),
                why=html_escape(r.get("why")),
                actor=html_escape(actor),
                approval=html_escape(r.get("approval")),
                status_class=html_escape(status).lower() or "planned",
                status=html_escape(status),
                undo=html_escape(undo),
                evidence=html_escape(evidence_str),
            )
        )
    entry_rows = "\n".join(entry_row_parts) or (
        "    <tr><td colspan=\"12\">No manual entries recorded yet.</td></tr>"
    )

    feature_section_parts: list[str] = []
    if not inventories:
        feature_section_parts.append("<p>No feature_inventory/*.csv files found.</p>")
    else:
        for platform in sorted(inventories.keys()):
            rows = inventories[platform]
            not_used = [row for row in rows if row.get("status") in ("unused", "partial", "planned")]
            feature_section_parts.append(f"<h3>{html_escape(platform)}</h3>")
            if not not_used:
                feature_section_parts.append("<p>No unused/partial/planned features recorded.</p>")
                continue
            feature_section_parts.append("<table>")
            feature_section_parts.append(
                "<thead><tr><th>Feature</th><th>Status</th><th>Log IDs</th>"
                "<th>Notes</th><th>Source</th></tr></thead><tbody>"
            )
            for row in not_used:
                feature_section_parts.append(
                    "<tr><td>{feature}</td><td>{status}</td><td>{log_ids}</td>"
                    "<td>{notes}</td><td>{source}</td></tr>".format(
                        feature=html_escape(row.get("feature", "")),
                        status=html_escape(row.get("status", "")),
                        log_ids=html_escape(row.get("log_ids", "")),
                        notes=html_escape(row.get("notes", "")),
                        source=html_escape(row.get("source", "")),
                    )
                )
            feature_section_parts.append("</tbody></table>")
    feature_sections = "\n".join(feature_section_parts)

    return _HTML_TEMPLATE.format(
        company_title=html_escape(paths.mirror_title.removesuffix(" Activity Log")),
        last_updated=html_escape(_mirror_last_updated(paths)),
        source_path=html_escape(str(paths.log_jsonl)),
        total_entries=len(log_records),
        total_actors=len(actor_counts),
        total_systems=len(system_set),
        actor_rows=actor_rows,
        entry_rows=entry_rows,
        feature_sections=feature_sections,
    )


def render_all(paths: CompanyPaths) -> None:
    """Regenerates ACTIVITY_LOG.md plus any owner-facing mirror. Never
    raises: a rendering failure must never break or roll back a logging
    operation that already committed its entry to the JSONL."""
    try:
        cmd_render(paths)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all
        print(f"warning: render (ACTIVITY_LOG.md) failed after logging the entry: {exc}", file=sys.stderr)
    try:
        render_mirrors(paths)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all
        print(f"warning: owner mirror render failed after logging the entry: {exc}", file=sys.stderr)


def cmd_render_cli(args: argparse.Namespace) -> int:
    paths = resolve_paths(args.company)
    rc = cmd_render(paths)
    try:
        render_mirrors(paths)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: owner mirror render failed: {exc}", file=sys.stderr)
    return rc


# --------------------------------------------------------------------------
# `backfill-changelog` (unchanged logic from the Brightline original, made
# company-parametric)
# --------------------------------------------------------------------------

CHANGELOG_ROW_RE = re.compile(
    r"^\|\s*(?P<when>[^|]+?)\s*\|\s*(?P<system>[^|]+?)\s*\|\s*(?P<change>[^|]+?)\s*\|"
    r"\s*(?P<before_after>[^|]+?)\s*\|\s*(?P<by>[^|]+?)\s*\|\s*(?P<evidence>[^|]*?)\s*\|\s*$"
)
STRUCTURED_BULLET_RE = re.compile(
    r"^-\s*(?P<when>\d{4}-\d{2}-\d{2}[^·]*?)\s*·\s*"
    r"(?P<system>[a-z_]+)\s*·\s*(?P<action>[a-z_]+)\s*·\s*(?P<rest>.*)$"
)
CREATE_WORDS = ("created", "create ", "added", "add ")
REMOVE_WORDS = ("removed", "remove ", "deleted", "delete ")
EXPORT_WORDS = ("exported", "export ")
CHANGELOG_WHEN_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[ T](?P<time>\d{2}:\d{2})(?::(?P<sec>\d{2}))?\s*(?P<tz>[A-Za-z]{2,4})?\s*$"
)
_TZ_OFFSETS = {"MT": "-06:00", "MDT": "-06:00", "MST": "-07:00"}


def infer_changelog_system(system_text: str, change_text: str, systems: tuple[str, ...]) -> str:
    haystack = f"{system_text} {change_text}".lower()
    for system in systems:
        token = system.replace("_", " ")
        if token and token in haystack:
            return system
    return "other" if "other" in systems else systems[-1]


def infer_changelog_action(change_text: str) -> str:
    low = change_text.lower()
    if any(w in low for w in EXPORT_WORDS):
        return "export"
    if any(w in low for w in REMOVE_WORDS):
        return "delete"
    if any(w in low for w in CREATE_WORDS):
        return "create"
    return "update"


def parse_changelog_lines(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("|---") or line.lower().startswith("| when"):
            continue
        m = CHANGELOG_ROW_RE.match(line)
        if m:
            gd = m.groupdict()
            out.append(
                {
                    "raw": line,
                    "when": gd["when"],
                    "system_text": gd["system"],
                    "change": gd["change"],
                    "before_after": gd["before_after"],
                    "by": gd["by"],
                    "evidence": gd["evidence"],
                }
            )
            continue
        sm = STRUCTURED_BULLET_RE.match(line)
        if sm:
            gd = sm.groupdict()
            out.append(
                {
                    "raw": line,
                    "when": gd["when"].strip(),
                    "system_text": "",
                    "change": gd["rest"].strip(),
                    "before_after": "",
                    "by": "",
                    "evidence": "",
                    "explicit_system": gd["system"].strip(),
                    "explicit_action": gd["action"].strip(),
                }
            )
            continue
        if line.startswith("- ") or re.match(r"^\d{4}-\d{2}-\d{2}", line):
            body = line[2:].strip() if line.startswith("- ") else line
            out.append(
                {
                    "raw": line,
                    "when": "",
                    "system_text": "",
                    "change": body,
                    "before_after": "",
                    "by": "",
                    "evidence": "",
                }
            )
    return out


def normalize_changelog_ts(when_text: str) -> str | None:
    when_text = when_text.strip()
    if not when_text:
        return None
    m = CHANGELOG_WHEN_RE.match(when_text)
    if not m:
        return None
    gd = m.groupdict()
    sec = gd["sec"] or "00"
    tz = (gd["tz"] or "").upper()
    offset = _TZ_OFFSETS.get(tz, "")
    iso = f"{gd['date']}T{gd['time']}:{sec}{offset}"
    if _parse_ts(iso) is None:
        return None
    return iso


def cmd_backfill_changelog(args: argparse.Namespace) -> int:
    paths = resolve_paths(args.company)
    path = Path(args.path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        print(f"error: changelog file not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    parsed = parse_changelog_lines(text)
    if not parsed:
        print(f"no changelog lines recognized in {path}")
        return 0

    existing_records, _ = read_jsonl(paths.log_jsonl)
    existing_backfill_objects = {
        r.get("object") for r in existing_records if r.get("source") == "changelog-backfill"
    }

    added = 0
    skipped = 0
    with LockedFile(paths.lock_file):
        for item in parsed:
            object_text = item["change"] or item["raw"]
            if object_text in existing_backfill_objects:
                skipped += 1
                continue
            explicit_system = item.get("explicit_system")
            explicit_action = item.get("explicit_action")
            if explicit_system in paths.systems:
                system = explicit_system
            else:
                system = infer_changelog_system(item["system_text"], item["change"], paths.systems)
            if explicit_action in ACTIONS:
                action = explicit_action
            else:
                action = infer_changelog_action(item["change"])
            before_after = item["before_after"]
            before = None
            after = None
            if "→" in before_after:
                parts = before_after.split("→", 1)
                before, after = parts[0].strip(), parts[1].strip()
            elif "->" in before_after:
                parts = before_after.split("->", 1)
                before, after = parts[0].strip(), parts[1].strip()
            evidence = [e.strip() for e in item["evidence"].split(",") if e.strip()] if item["evidence"] else []
            actor = item["by"].strip() or "unknown (backfill)"
            when_raw = item["when"].strip()
            ts = normalize_changelog_ts(when_raw) or (when_raw or None)
            entry = {
                "id": next_id_locked(paths.log_jsonl),
                "ts": ts if ts else now_denver_iso(),
                "source": "changelog-backfill",
                "system": system,
                "action": action,
                "object": object_text,
                "before": before,
                "after": after,
                "why": f"backfilled from {path.name}",
                "actor": actor,
                "evidence": evidence,
                "undo": None if action in UNDO_OPTIONAL_ACTIONS else "see original changelog entry for reversal context",
                "approval": "n/a (historical backfill)",
                "status": "done",
                "account": None,
                "notes": f"original changelog text: {item['raw']}",
            }
            entry = redact(entry)
            _append_chained(paths.log_jsonl, entry)
            existing_backfill_objects.add(object_text)
            added += 1
    print(f"backfill complete: {added} added, {skipped} skipped (already backfilled)")
    render_all(paths)
    return 0


# --------------------------------------------------------------------------
# `audit` / `explain` (clustering logic unchanged from the Brightline
# original)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Cluster:
    cluster_id: str
    session_id: str
    system: str
    start: datetime
    end: datetime
    records: tuple[dict[str, Any], ...]

    @property
    def n_records(self) -> int:
        return len(self.records)

    def sample_detail(self) -> str:
        last = self.records[-1]
        detail = last.get("detail")
        if isinstance(detail, dict):
            text = "; ".join(f"{k}={v}" for k, v in detail.items() if v)
        elif isinstance(detail, str):
            text = detail
        else:
            text = ""
        if not text:
            text = last.get("result_excerpt") or last.get("url") or "(no detail)"
        return (text[:160] + "…") if len(text) > 160 else text


def _tz_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def build_clusters(trail_records: list[dict[str, Any]]) -> list[Cluster]:
    by_key: dict[tuple[str, str], list[tuple[datetime, dict[str, Any]]]] = {}
    for r in trail_records:
        if not r.get("mutating"):
            continue
        dt = _parse_ts(r.get("ts"))
        if dt is None:
            continue
        dt = _tz_aware(dt)
        session_id = r.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            session_id = "(unknown session)"
        system = r.get("system") or "?"
        by_key.setdefault((session_id, system), []).append((dt, r))

    clusters: list[Cluster] = []
    gap = timedelta(minutes=CLUSTER_GAP_MINUTES)
    for (session_id, system), items in by_key.items():
        items.sort(key=lambda pair: pair[0])
        current: list[tuple[datetime, dict[str, Any]]] = []
        for dt, r in items:
            if current and (dt - current[-1][0]) > gap:
                clusters.append(_make_cluster(session_id, system, current))
                current = []
            current.append((dt, r))
        if current:
            clusters.append(_make_cluster(session_id, system, current))

    clusters.sort(key=lambda c: (c.start, c.session_id, c.system))
    return clusters


def _make_cluster(session_id: str, system: str, items: list[tuple[datetime, dict[str, Any]]]) -> Cluster:
    start = items[0][0]
    end = items[-1][0]
    records = tuple(r for _, r in items)
    cluster_id = f"{start.strftime('%Y%m%dT%H%M%S')}_{session_id[:8]}_{system}"
    return Cluster(cluster_id=cluster_id, session_id=session_id, system=system, start=start, end=end, records=records)


def cluster_is_explained(cluster: Cluster, manual_by_system: dict[str, list[datetime]]) -> bool:
    """A cluster is explained by a manual entry within its window — but ONLY
    when that entry's actor is an agent-actor (plan §11.3: 'actor=owner /
    outside-actor entries never explain an agent trail record'). See
    is_agent_actor() below for the convention."""
    window = timedelta(minutes=CLUSTER_EXPLAIN_WINDOW_MINUTES)
    lo = cluster.start - window
    hi = cluster.end + window
    for dt in manual_by_system.get(cluster.system, []):
        if lo <= dt <= hi:
            return True
    return False


_AGENT_ID_SHAPE_RE = re.compile(r"^a[0-9a-f]{8,}$")
_SEAT_AGENT_ID_RE = re.compile(r"^[^:\s]+:a[0-9a-f]{8,}$")


def is_agent_actor(actor: Any) -> bool:
    """§11.3: 'audit counts only agent-actor entries as explaining an agent
    trail record. Entries whose actor is owner or an outside actor never
    explain one.'

    INVERTED (major 5): the previous version defaulted to "agent" and
    excluded only 'owner'/'outside:' — which wrongly counted every other
    free-text actor (including real Brightline shapes like
    "owner (via main session)" and "unknown (backfill)") as an agent. This
    now defaults to NON-agent and admits only known agent shapes:
      - `<seat>:<agent_id>` where the agent id looks like `a[0-9a-f]{8,}`
        (the real transcript agent-id shape, e.g. "ac06afdc5dc9de0f3")
      - exactly `main-session` or `agent`
      - anything STARTING WITH `main-session` (e.g.
        "main-session (executing paid-acquisition-strategist ruling)",
        a real Brightline shape)
    Everything else — including anything starting with `owner` (e.g.
    "owner (via main session)") or `outside:`, and anything starting with
    `unknown` (e.g. "unknown (backfill)") — is non-agent."""
    if not isinstance(actor, str) or not actor.strip():
        return False
    if actor.startswith("owner"):
        return False
    if actor.startswith("outside:"):
        return False
    if actor.startswith("unknown"):
        return False
    if actor in ("main-session", "agent"):
        return True
    if actor.startswith("main-session"):
        return True
    if _SEAT_AGENT_ID_RE.match(actor):
        return True
    return False


_OUTSIDE_ACTOR_RE = re.compile(r"^outside:\S+")


def is_valid_new_actor_shape(actor: Any) -> bool:
    """Minor 16: for a NEW entry (add/explain), `actor` must be either a
    known AGENT shape (is_agent_actor's own positive set: `<seat>:<agent_id>`,
    `main-session`, anything starting with `main-session`, or exactly
    `agent`) or an explicit NON-agent shape (`owner...` or
    `outside:<who>`, where <who> is non-empty). Anything else — a bare
    free-text specialist name like "brand-architect", or "unknown..." — is
    AMBIGUOUS and rejected for new entries: it is exactly the shape that
    made major 5's audit bug possible in the first place (a free-text
    actor silently miscounted as agent-or-not), so refusing it at write
    time closes the same hole going forward. This check is NEVER applied
    to legacy/existing lines (read_jsonl, is_agent_actor, audit) — only
    to a brand-new `add`/`explain` entry, so historical rows with
    free-text actors stay fully readable."""
    if not isinstance(actor, str) or not actor.strip():
        return False
    if is_agent_actor(actor):
        return True
    if actor.startswith("owner"):
        return True
    if _OUTSIDE_ACTOR_RE.match(actor):
        return True
    return False


def earliest_manual_ts(log_records: list[dict[str, Any]]) -> datetime | None:
    parsed = [_tz_aware(dt) for dt in (_parse_ts(r.get("ts")) for r in log_records) if dt is not None]
    return min(parsed) if parsed else None


def cmd_audit(args: argparse.Namespace) -> int:
    paths = resolve_paths(args.company)
    log_records, _ = read_jsonl(paths.log_jsonl)
    trail_records, _ = read_jsonl(paths.trail_jsonl)

    window_days = args.days
    now = datetime.now().astimezone()
    days_cutoff = now - timedelta(days=window_days)

    since_dt: datetime | None
    if args.since:
        since_dt = _parse_ts(args.since)
        if since_dt is None:
            print(f"error: --since value {args.since!r} is not a parseable ISO8601 timestamp", file=sys.stderr)
            return 2
        since_dt = _tz_aware(since_dt)
    else:
        since_dt = earliest_manual_ts(log_records)

    cutoff = days_cutoff if since_dt is None else max(days_cutoff, since_dt)

    excluded_systems: set[str] = set() if args.include_local else set(DEFAULT_AUDIT_EXCLUDED_SYSTEMS)

    manual_by_system: dict[str, list[datetime]] = {}
    for r in log_records:
        if not is_agent_actor(r.get("actor")):
            continue
        dt = _parse_ts(r.get("ts"))
        if dt is None:
            continue
        manual_by_system.setdefault(r.get("system", "?"), []).append(_tz_aware(dt))

    scoped_trail = [r for r in trail_records if r.get("system") not in excluded_systems]
    clusters = build_clusters(scoped_trail)
    clusters = [c for c in clusters if c.end >= cutoff]

    unexplained = [c for c in clusters if not cluster_is_explained(c, manual_by_system)]

    # gtm-offserver rows (finding 12 / plan §7.1 "detect-after"): every
    # mutating trail record flagged offserver=True within the audit window,
    # reported unconditionally -- independent of whether its cluster is
    # otherwise explained, since the point is to surface that the action
    # ran outside the governed playwright-gtm server/ticket system at all,
    # not merely whether someone later logged a reason for it.
    offserver_records = [
        r
        for r in scoped_trail
        if r.get("offserver") and r.get("mutating")
        and (dt := _parse_ts(r.get("ts"))) is not None
        and _tz_aware(dt) >= cutoff
    ]

    exit_code = 0

    if not unexplained:
        print(
            f"audit clean: no unexplained mutating clusters since "
            f"{cutoff.isoformat()} (excluded systems: {sorted(excluded_systems) or 'none'})"
        )
    else:
        exit_code = 1
        print(
            f"audit found {len(unexplained)} unexplained cluster(s) since {cutoff.isoformat()} "
            f"(excluded systems: {sorted(excluded_systems) or 'none'}):"
        )
        for c in sorted(unexplained, key=lambda x: x.start):
            print(
                f"  - [{c.cluster_id}] {c.start.isoformat()} → {c.end.isoformat()} · "
                f"`{c.system}` · session={c.session_id} · {c.n_records} record(s) · {c.sample_detail()}"
            )

    if offserver_records:
        exit_code = 1
        print(f"audit found {len(offserver_records)} gtm-offserver record(s) since {cutoff.isoformat()}:")
        for r in sorted(offserver_records, key=lambda x: x.get("ts") or ""):
            print(
                f"  - offserver: {r.get('ts')} · `{r.get('system')}` · server={r.get('server')} · "
                f"tool_use_id={r.get('tool_use_id')} · {r.get('url') or '(no url)'}"
            )

    return exit_code


def cmd_explain(args: argparse.Namespace) -> int:
    paths = resolve_paths(args.company)
    trail_records, _ = read_jsonl(paths.trail_jsonl)
    excluded_systems: set[str] = set() if args.include_local else set(DEFAULT_AUDIT_EXCLUDED_SYSTEMS)
    scoped_trail = [r for r in trail_records if r.get("system") not in excluded_systems]
    clusters = build_clusters(scoped_trail)
    match = next((c for c in clusters if c.cluster_id == args.cluster), None)
    if match is None:
        print(f"error: no cluster with id {args.cluster!r} found (re-run `audit` to see current cluster ids)", file=sys.stderr)
        return 2

    fields: dict[str, Any] = {
        "system": match.system,
        "action": args.action,
        "object": args.object,
        "before": args.before,
        "after": args.after,
        "why": args.why,
        "actor": args.actor,
        "evidence": list(args.evidence) if args.evidence else [],
        "undo": args.undo,
        "approval": args.approval,
        "status": args.status,
        "account": args.account,
        "notes": args.notes,
    }
    try:
        validate_add_fields(fields, paths.systems)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    entry = {
        "ts": match.end.isoformat(),
        "source": "manual",
        **fields,
    }
    entry = redact(entry)

    with LockedFile(paths.lock_file):
        entry["id"] = next_id_locked(paths.log_jsonl)
        entry = _append_chained(paths.log_jsonl, entry)
    print(f"logged {entry['id']} closing cluster {match.cluster_id}: {entry['system']}/{entry['action']} {entry['object']!r}")
    render_all(paths)
    return 0


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------


def _add_company_arg(sub_p: argparse.ArgumentParser) -> None:
    sub_p.add_argument("--company", required=True, help="registered GTM company slug")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="activity_log.py", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="append one manual activity-log entry")
    _add_company_arg(add_p)
    add_p.add_argument("--system", required=True)
    add_p.add_argument("--action", required=True, choices=ACTIONS)
    add_p.add_argument("--object", required=True)
    add_p.add_argument("--before", default=None)
    add_p.add_argument("--after", default=None)
    add_p.add_argument("--why", required=True)
    add_p.add_argument("--actor", required=True)
    add_p.add_argument("--evidence", action="append", default=[])
    add_p.add_argument("--undo", default=None)
    add_p.add_argument("--approval", default="standing")
    add_p.add_argument("--status", default="done", choices=STATUSES)
    add_p.add_argument("--account", default=None)
    add_p.add_argument("--ts", default=None)
    add_p.add_argument("--notes", default=None)
    add_p.set_defaults(func=cmd_add)

    render_p = sub.add_parser("render", help="regenerate ACTIVITY_LOG.md and any owner-facing mirror")
    _add_company_arg(render_p)
    render_p.set_defaults(func=cmd_render_cli)

    check_p = sub.add_parser("check", help="validate both JSONL files + hash chain")
    _add_company_arg(check_p)
    check_p.set_defaults(func=cmd_check)

    backfill_p = sub.add_parser("backfill-changelog", help="import an existing markdown changelog")
    _add_company_arg(backfill_p)
    backfill_p.add_argument("path")
    backfill_p.set_defaults(func=cmd_backfill_changelog)

    audit_p = sub.add_parser("audit", help="list unexplained mutating-change clusters")
    _add_company_arg(audit_p)
    audit_p.add_argument("--days", type=int, default=7)
    audit_p.add_argument("--since", default=None)
    audit_p.add_argument("--include-local", action="store_true")
    audit_p.set_defaults(func=cmd_audit)

    explain_p = sub.add_parser("explain", help="write a manual entry closing an audit cluster")
    _add_company_arg(explain_p)
    explain_p.add_argument("--cluster", required=True)
    explain_p.add_argument("--why", required=True)
    explain_p.add_argument("--object", required=True)
    explain_p.add_argument("--action", default="update", choices=ACTIONS)
    explain_p.add_argument("--before", default=None)
    explain_p.add_argument("--after", default=None)
    explain_p.add_argument("--actor", default="main-session")
    explain_p.add_argument("--evidence", action="append", default=[])
    explain_p.add_argument("--undo", required=True)
    explain_p.add_argument("--approval", default="standing")
    explain_p.add_argument("--status", default="done", choices=STATUSES)
    explain_p.add_argument("--account", default=None)
    explain_p.add_argument("--notes", default=None)
    explain_p.add_argument("--include-local", action="store_true")
    explain_p.set_defaults(func=cmd_explain)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
