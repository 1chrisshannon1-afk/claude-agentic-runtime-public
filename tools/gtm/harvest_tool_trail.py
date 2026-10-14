#!/usr/bin/env python3
"""harvest_tool_trail.py — the runtime, company-agnostic generalization of
Brightline's `tracking/activity_log/harvest_tool_trail.py` (plan §11 item 3).

Scans Claude Code transcript JSONL files (main-session and dispatched
sub-agent transcripts) and appends to each attributed company's
TOOL_TRAIL.jsonl every tool call that touched one of ITS identity hosts.
Idempotent by tool_use id: existing ids already recorded (across every
company's trail) are read first and never re-appended.

Company attribution precedence (plan §11.3):
    1. an identity-index host or account id appearing in the call
    2. server name `playwright-gtm` + the transcript record's `cwd` under a
       registered home
    3. `cwd` alone

Mutating calls on ANY playwright server whose URL/host is in the identity
index are captured (not just `playwright-gtm`). An unattributable mutating
call to an identity-index host is appended to
`~/.claude/.gtm_state/unattributed_trail.jsonl` instead of any company's
trail.

This is a pure capture tool — it never asks "why" a change was made (that is
`activity_log.py add`'s job); it only proves WHAT actually happened.

Usage
-----
    python3 harvest_tool_trail.py                     # default globs
    python3 harvest_tool_trail.py <path> [<path>...]  # explicit transcript files
"""

from __future__ import annotations

import contextlib
import glob
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import activity_log as activity_log_mod  # noqa: E402
import company as company_mod  # noqa: E402

# nit fix: the TOOL_TRAIL.jsonl.ids sidecar helpers now live in
# activity_log.py (see its own module docstring comment at their
# definition site) -- this removes the deferred-import + `noqa: PLC0415`
# cycle workaround activity_log.py's cmd_check used to need purely to
# reach verify_sidecar_matches_trail (a real circular-import shape, since
# THIS module imports activity_log at its own top level, so activity_log
# could never import harvest_tool_trail back at ITS top level). Every
# call site below keeps using the same bare names via these module-level
# aliases, so nothing else in this module needed to change.
_ids_sidecar_path = activity_log_mod._ids_sidecar_path
_trail_stats = activity_log_mod._trail_stats
_path_size = activity_log_mod._path_size
_read_sidecar_header_and_ids = activity_log_mod._read_sidecar_header_and_ids
_load_ids_from_sidecar = activity_log_mod._load_ids_from_sidecar
_scan_ids_from_jsonl = activity_log_mod._scan_ids_from_jsonl
_write_sidecar_with_header = activity_log_mod._write_sidecar_with_header
_rebuild_ids_sidecar = activity_log_mod._rebuild_ids_sidecar
verify_sidecar_matches_trail = activity_log_mod.verify_sidecar_matches_trail

DEFAULT_GLOBS_TEMPLATE = (
    str(Path.home() / ".claude" / "projects" / "*" / "*.jsonl"),
    str(Path.home() / ".claude" / "projects" / "*" / "*" / "subagents" / "**" / "agent-*.jsonl"),
)

# A company's pre-migration working directories (plan §14 P1): transcripts
# from sessions run there live under a project dir keyed to THAT path, not to
# the company's GTM home. Each pack lists them in its optional
# `legacy_workdirs` so those historical sessions are still found after the
# registered-homes-only narrowing below (major 7). Read from the private pack,
# never hardcoded here: this runtime code names no company.
def _legacy_workdirs(homes: dict[str, Path]) -> list[Path]:
    dirs: list[Path] = []
    for home in homes.values():
        pack_file = Path(home) / ".claude" / "gtm" / "company.json"
        try:
            pack = json.loads(pack_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        legacy = pack.get("legacy_workdirs") if isinstance(pack, dict) else None
        if not isinstance(legacy, list):
            continue
        for entry in legacy:
            if isinstance(entry, str) and entry and ".." not in Path(entry).parts:
                dirs.append(Path(entry).expanduser())
    return dirs


_PROJECT_DIR_NAME_UNSAFE_RE = re.compile(r"[/_. ]")


def _project_dir_name(home: Path) -> str:
    """Derives a Claude Code project directory name from a home path the
    same way Claude Code itself does. Major 14: verified 2026-09-27
    against real folders in ~/.claude/projects by cross-referencing
    transcripts' own `cwd` field (never guessed) — the mapping is not
    just '/' -> '-': four characters all become '-': '/', '_', '.', and
    space. Confirmed pairs, read directly from real transcript `cwd`
    fields matched to their real project directory name:
      cwd .../worktrees/wf_056c27ed-24a-3       -> ...-worktrees-wf-056c27ed-24a-3   ('_' -> '-')
      cwd .../Desktop/other project           -> ...-Desktop-other-project        (' ' -> '-')
      cwd .../scratchpad/dotclaude_sim          -> ...-scratchpad-dotclaude-sim       ('/' AND '_' -> '-')
      cwd .../BuildwiseAI/.claude/...     -> ...-BuildwiseAI--claude-...  ('.' -> '-', hence the double dash)
    """
    return _PROJECT_DIR_NAME_UNSAFE_RE.sub("-", str(home.resolve()))


# #26 (regression fix, major 14 follow-up): a home's own project dir name
# can legitimately be extended by ANY runtime-derived sub-path -- a real
# subfolder (repo_tooling/demo_video, modules/estimate_product_layer/
# frontend, _Config_Project/trade_kb/...) or a worktree
# (.claude/worktrees/<name>) -- not just the two markers Claude Code is
# KNOWN to generate itself. The prior version's allowlist
# (_KNOWN_PROJECT_DIR_SUB_COMPONENTS = ("--claude-worktrees-", "--claude-"))
# over-corrected: it silently EXCLUDED every real subfolder session dir
# that isn't a worktree (measured 2026-09-27 against this machine's real
# ~/.claude/projects/: 27 real dirs -> 23 after that allowlist landed,
# dropping repo-tooling-demo-video, repo-tooling-demo-video-scenes,
# modules-estimate-product-layer-frontend, and the trade-kb one).
#
# _matches_project_dir_prefix is now DELIBERATELY separator-bounded but
# otherwise UNRESTRICTED (exact equality, or prefix + "-" + at least one
# more character) -- candidate DISCOVERY is a superset by design. The
# false-positive this widening reopens (a genuinely unrelated sibling
# folder that merely shares the string prefix, e.g.
# '...-BuildwiseAI-Sale-2026') is closed at a DIFFERENT layer:
# _transcript_cwd_is_under_home checks each candidate transcript's own
# recorded `cwd` field against `home` via Path.is_relative_to() before it
# is scanned at all -- a sibling folder's transcripts always have a cwd
# OUTSIDE `home`, so they are dropped there regardless of how permissive
# the directory-name match is. Directory-name matching can never
# distinguish a real subfolder from a same-prefix sibling (the derived
# name is lossy -- '/', '_', '.', and ' ' all collapse to the same '-'),
# so pushing the real decision onto the transcript's own ground-truth cwd
# is the only sound fix, not a rule tuned further ad hoc.
def _matches_project_dir_prefix(dir_name: str, prefix_name: str) -> bool:
    """Separator-bounded prefix match for CANDIDATE DISCOVERY ONLY: exact
    equality, or `prefix_name` followed by '-' and at least one more
    character. Real membership is decided later, per-transcript, by
    _transcript_cwd_is_under_home -- this function only avoids a bare
    `str.startswith(prefix_name)` false-positive on an unrelated dir whose
    name merely starts with the same characters with no separator at all
    (e.g. prefix '...-Repo' bare-matching '...-RepoOther')."""
    if dir_name == prefix_name:
        return True
    candidate_prefix = prefix_name + "-"
    return dir_name.startswith(candidate_prefix) and len(dir_name) > len(candidate_prefix)


def _read_transcript_cwd(transcript_path: Path) -> Path | None:
    """Reads a transcript's own recorded `cwd` field once (from its first
    line that carries one), resolved to an absolute Path. Returns None when
    no line carries a readable `cwd` at all (an unreadable file, or one
    whose lines never set it) -- callers treat None as "unknown, fail
    open", never as "resolves nowhere".

    Nit fix: this used to be inlined inside `_transcript_cwd_is_under_home`
    and re-run (re-opening and re-parsing the file from scratch) once PER
    HOME being tested against -- a transcript under NO home was opened
    `len(homes) + 1` times. Reading the cwd once per file, then testing the
    single resolved value against every home, makes this an O(files) read
    regardless of how many homes are registered."""
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                cwd = obj.get("cwd")
                if isinstance(cwd, str) and cwd:
                    try:
                        return Path(cwd).resolve()
                    except (OSError, ValueError):
                        return None
    except OSError:
        return None
    return None


def _transcript_cwd_is_under_home(transcript_path: Path, home: Path) -> bool:
    """#26: settles real membership on the transcript's OWN recorded `cwd`
    field, never on the directory-name match alone -- a directory name is
    a lossy derivation ('/', '_', '.', ' ' all become '-') and cannot by
    itself distinguish a genuine subfolder/worktree of `home` from an
    unrelated sibling folder that happens to share the same string prefix.
    Returns True (keep) when the transcript's cwd resolves to `home` itself
    or anything under it; False when it resolves elsewhere; True (fail
    open, keep) when no cwd can be read at all -- an unreadable/cwd-less
    transcript is exactly the shape a fresh test environment's synthetic
    fixtures already produce, and this function is a NARROWING filter on
    top of the existing directory-glob discovery, not a replacement for
    it, so failing open here never widens what gets scanned beyond what
    the glob already found.

    Kept as a thin single-home wrapper around `_read_transcript_cwd` for
    any caller (and existing test) that only needs one home checked; the
    real multi-home scan in `resolve_transcript_paths` reads the cwd once
    per file via `_read_transcript_cwd` directly rather than calling this
    once per home."""
    cwd = _read_transcript_cwd(transcript_path)
    if cwd is None:
        return True
    try:
        return cwd.is_relative_to(home.resolve())
    except (OSError, ValueError):
        return True


def _matching_project_dirs(prefix_name: str) -> list[Path]:
    """Major 14: also includes project dirs for SUBFOLDERS and WORKTREES of
    a home — any `~/.claude/projects/<prefix_name>[-<sub-component>]`
    directory, not only the exact `<prefix_name>` match. A worktree's cwd
    is `<home>/.claude/worktrees/<name>`, whose derived project dir name
    is `<prefix_name>--claude-worktrees-<name>` — a real prefix-plus-
    separator match, not a bare string-prefix one (#26). Falls back to
    just the exact dir (even if it doesn't exist) when no prefix match is
    found on disk, so callers still glob against a deterministic path in
    a fresh test environment with no real ~/.claude/projects/ tree."""
    projects_root = Path.home() / ".claude" / "projects"
    exact = projects_root / prefix_name
    if not projects_root.is_dir():
        return [exact]
    matches = [
        p for p in projects_root.iterdir()
        if p.is_dir() and _matches_project_dir_prefix(p.name, prefix_name)
    ]
    return matches or [exact]


def default_globs_for_homes(homes: dict[str, Path]) -> tuple[str, ...]:
    """Major 7 (narrowed further by major 14): default transcript globs
    cover ONLY registered homes' project dirs (derived by
    _project_dir_name, including subfolder/worktree prefix matches) plus
    each pack's legacy_workdirs — never a blanket `~/.claude/projects/*/
    *.jsonl` across every project on the machine, which would scan
    transcripts for repos that have nothing to do with any registered GTM
    company."""
    project_dirs: list[Path] = []
    for home in homes.values():
        project_dirs.extend(_matching_project_dirs(_project_dir_name(home)))
    for legacy in _legacy_workdirs(homes):
        project_dirs.extend(_matching_project_dirs(_project_dir_name(legacy)))
    globs: list[str] = []
    for project_dir in project_dirs:
        globs.append(str(project_dir / "*.jsonl"))
        globs.append(str(project_dir / "*" / "subagents" / "**" / "agent-*.jsonl"))
    return tuple(globs)

MUTATING_BROWSER_ACTIONS = {
    "click",
    "type",
    "fill_form",
    "select_option",
    "press_key",
    "file_upload",
    "handle_dialog",
    "drag",
    "drop",
}
NONMUTATING_BROWSER_ACTIONS = {"navigate", "tabs", "hover", "navigate_back", "snapshot", "take_screenshot", "close"}

CODE_ACTION_VERB_RE = re.compile(
    r"\.click\(|\.fill\(|\.type\(|\.press\(|\.check\(|\.uncheck\(|\.selectOption\(|"
    r"setFiles|setInputFiles|mouse\.click|mouse\.down|mouse\.up|mouse\.dblclick|keyboard\.|"
    r"\.dragTo\(|\.dispatchEvent\(|\.tap\("
)


def code_is_mutating(code: str) -> bool:
    if not isinstance(code, str) or not code:
        return False
    return bool(CODE_ACTION_VERB_RE.search(code))


# Matches any playwright MCP server, not just playwright-gtm — plan §11.3:
# "mutating calls on ANY playwright server to an identity-index host are
# captured."
BROWSER_TOOL_RE = re.compile(
    r"^mcp__(?P<server>playwright[^_]*)__browser_(?P<action>navigate|click|type|fill_form|select_option|"
    r"press_key|run_code_unsafe|evaluate|file_upload|handle_dialog|drag|drop|hover|"
    r"navigate_back|tabs|snapshot|take_screenshot|close)$"
)

PAGE_URL_RE = re.compile(r"-\s*Page URL:\s*(\S+)")

REDACT_CREDENTIAL_MARKER = "<redacted: credential context>"


def redact_text(text: str) -> str:
    return re.sub(
        r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+",
        lambda m: f"{m.group(1)}=<redacted>",
        text,
        flags=re.IGNORECASE,
    )


def looks_like_credential_context(text: str) -> bool:
    low = text.lower()
    return "keeper" in low and "password" in low


def _extract_host(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host and "://" not in url:
        parsed = urlparse("https://" + url)
        host = parsed.hostname
    return (host or "").lower()


def _host_matches(host: str, rule_host: str) -> bool:
    rule_host = rule_host.lower()
    return host == rule_host or host.endswith("." + rule_host)


# --------------------------------------------------------------------------
# Host -> system mapping (blocker 2 — port of the Brightline original's
# HOST_RULES, generalized into pack data + runtime defaults)
# --------------------------------------------------------------------------

# Runtime defaults for the common platforms every company might touch.
# Ordered MOST-SPECIFIC-HOST FIRST for the same reason the Brightline
# original's HOST_RULES was ordered that way: several Google products share
# the "*.google.com" parent domain, and a generic fallback would otherwise
# swallow every one of them. A pack's own `host_systems` entries (checked
# FIRST, in insertion order) can override or extend this table per company.
DEFAULT_HOST_SYSTEMS: tuple[tuple[str, str], ...] = (
    ("ads.google.com", "google_ads"),
    ("tagmanager.google.com", "gtm"),
    ("analytics.google.com", "ga4"),
    ("search.google.com", "search_console"),
    ("business.google.com", "gbp"),
    ("localservices.google.com", "lsa"),
    ("facebook.com", "facebook"),
    ("business.facebook.com", "facebook"),
    ("instagram.com", "instagram"),
    ("yelp.com", "yelp"),
    ("angi.com", "angi"),
    ("homeadvisor.com", "angi"),
    ("thumbtack.com", "thumbtack"),
    ("houzz.com", "houzz"),
    ("nextdoor.com", "nextdoor"),
    ("bbb.org", "bbb"),
    ("businessconnect.apple.com", "apple_business"),
    ("bingplaces.com", "bing_places"),
)

# Minor 19: a PATH prefix on ads.google.com (not a separate host) that
# reclassifies the call as LSA (Local Services Ads) rather than the
# generic google_ads default for that host — checked BEFORE the
# DEFAULT_HOST_SYSTEMS host-only lookup so this path-specific rule wins on
# the shared ads.google.com host.
_ADS_LSA_PATH_RE = re.compile(r"^/localservices(?:/|$)")

# A path segment (not a host) that reclassifies a WordPress-hosted domain
# from "website_wordpress" is handled separately in host_system_for_url
# (the "wp-admin/wp-login on a pack domain" rule) since it depends on the
# pack's OWN declared domains, not a fixed public host. Minor 19 adds
# wp-login.php alongside wp-admin (also a WordPress-admin-surface path).
_WP_ADMIN_PATH_RE = re.compile(r"/wp-admin(?:/|$)|/wp-login\.php$")


def _id_matches_at_boundary(id_value: str, haystack: str) -> bool:
    """Nit fix (#27 path-scoped host_systems matching): matches `id_value`
    against `haystack` on a real token boundary -- not immediately
    preceded or followed by another alphanumeric character -- so a
    SHORTER numeric/alphanumeric id never spuriously matches INSIDE a
    LONGER one that merely happens to share the same digits (e.g. GBP
    location id "72655" bare-substring-matching inside an unrelated
    "9172655813" elsewhere in the URL). A boundary can be a path
    separator, a query delimiter, string start/end, or any other
    non-alphanumeric character."""
    pattern = r"(?<![0-9A-Za-z])" + re.escape(id_value) + r"(?![0-9A-Za-z])"
    return re.search(pattern, haystack) is not None


def _pack_host_systems(pack: dict[str, Any] | None) -> tuple[tuple[str, str | None, str], ...]:
    """Reads a pack's optional `host_systems` key: {host_glob: system}.
    A host_glob here is a plain host/domain string (suffix-matched exactly
    like DEFAULT_HOST_SYSTEMS, never a real glob syntax — 'glob' in the
    plan's own key name describes the matching behavior, not a fnmatch
    pattern). Insertion order is preserved (dict order), and pack entries
    are checked BEFORE the runtime defaults, so a pack can override a
    default mapping for its own domain.

    #27: `host_systems` is host-level only by default, so it cannot tell
    two brands apart on a SHARED host (e.g. two brands sharing one
    business.google.com/facebook.com account). A key MAY instead be
    `<host>/<path-prefix>` (e.g.
    "business.google.com/9000000000000000001", a GBP location id, or
    "facebook.com/100000000000001", a Facebook Page id, both appearing in
    the URL) -- these path-scoped entries are returned SEPARATELY from
    plain host-only entries (as a 3-tuple with a non-None path_prefix) and
    are always checked FIRST by the caller, so a more specific
    host+path-prefix rule always wins over a bare host rule for the same
    host. Returns (host, path_prefix_or_None, system) tuples."""
    if not isinstance(pack, dict):
        return ()
    raw = pack.get("host_systems")
    if not isinstance(raw, dict):
        return ()
    out: list[tuple[str, str | None, str]] = []
    for key, system in raw.items():
        if not isinstance(key, str) or not isinstance(system, str) or not key or not system:
            continue
        if "/" in key:
            host, _sep, path_prefix = key.partition("/")
            if host and path_prefix:
                out.append((host, path_prefix, system))
                continue
        out.append((key, None, system))
    return tuple(out)


def host_system_for_url(url: str, pack: dict[str, Any] | None) -> str:
    """Maps a URL to a system slug: the attributed company's own
    `host_systems` overrides first (path-scoped entries before plain
    host-only entries, per #27), then DEFAULT_HOST_SYSTEMS, then a
    pack-domain + wp-admin path special case, else the generic
    'gtm_browser' fallback (never an unknown/unmapped literal — the old
    defect this replaces was a HARDCODED 'gtm_browser' that could never be
    in SYSTEMS; 'gtm_browser' is now REGISTERED as a real fallback system
    in activity_log.py's SYSTEMS union, so `explain`/`audit` can always
    handle whatever this returns)."""
    host = _extract_host(url)
    if not host:
        return "gtm_browser"

    pack_host_systems = _pack_host_systems(pack)
    url_path = urlparse(url).path or ""

    # #27: path-scoped entries (host + path-prefix, e.g. a GBP location id
    # or Facebook Page id appearing anywhere in the URL) are checked
    # FIRST, before any plain host-only entry -- so a company with two
    # brands sharing one host (business.google.com, facebook.com) can
    # still disambiguate them by the id each brand's URLs actually carry.
    #
    # Nit fix: matched on `url` ALONE (never a haystack that redundantly
    # re-concatenates the URL with its own already-included path/query --
    # `url_path`/`url_query` are both substrings of `url` itself, so
    # appending them again could only ever change a match's OFFSET, never
    # whether a match exists), and on a BOUNDARY-anchored id, not a bare
    # substring -- a bare substring match lets a shorter numeric id
    # spuriously match inside a longer one sharing the same digits (e.g.
    # id "72655" would wrongly match inside a URL carrying "9172655813").
    # The boundary is "not immediately preceded/followed by another
    # alphanumeric character", so a match must sit on a real token edge
    # (path separator, query delimiter, string start/end, etc.).
    # Nit fix: matched against path+query ONLY (never the full `url`,
    # scheme and host included) -- the docs (this function's own docstring
    # chain and README/company_schema.json) describe a path-scoped entry
    # as matching "anywhere in the URL (path or query string)", but
    # matching the full url string let a path-prefix that happens to equal
    # a HOST label (e.g. a numeric id that also appears in the domain, or
    # a short prefix like "business") match every URL on that host
    # regardless of its actual path -- defeating the whole point of a
    # path-scoped entry, which exists specifically to disambiguate two
    # brands sharing one host.
    url_query = urlparse(url).query or ""
    path_and_query = url_path + (("?" + url_query) if url_query else "")
    for rule_host, path_prefix, system in pack_host_systems:
        if path_prefix is not None and _host_matches(host, rule_host) and _id_matches_at_boundary(path_prefix, path_and_query):
            return system

    for rule_host, path_prefix, system in pack_host_systems:
        if path_prefix is None and _host_matches(host, rule_host):
            return system

    # Minor 19: /localservices on ads.google.com is LSA, not the generic
    # google_ads default for that host -- checked before the plain
    # DEFAULT_HOST_SYSTEMS host lookup so this path-specific rule wins.
    if _host_matches(host, "ads.google.com") and _ADS_LSA_PATH_RE.search(url_path):
        return "lsa"

    for rule_host, system in DEFAULT_HOST_SYSTEMS:
        if _host_matches(host, rule_host):
            return system

    if isinstance(pack, dict):
        brands = pack.get("brands")
        pack_domains: list[str] = []
        if isinstance(brands, list):
            for brand in brands:
                if isinstance(brand, dict):
                    domains = brand.get("domains")
                    if isinstance(domains, list):
                        pack_domains.extend(d for d in domains if isinstance(d, str))
        for domain in pack_domains:
            if _host_matches(host, domain) and _WP_ADMIN_PATH_RE.search(url_path):
                return "website_wordpress"

    return "gtm_browser"


# --------------------------------------------------------------------------
# Identity index -> company attribution
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityIndex:
    """Maps identity values to the company slug that declared them. Built
    once per harvest run from TWO separate files: the broad
    ~/.claude/.gtm_state/identity_index.json (written by `company.py
    index`, includes NAP names/addresses/phones) for URL-hostname matching
    ONLY, and the narrow ~/.claude/.gtm_state/account_id_index.json
    (genuine platform account/object ids only) for free-text substring
    matching (major 15 — capture must never trigger on a brand name,
    address, or phone appearing as page TEXT, only on a real host or
    account-id match)."""

    value_to_company: dict[str, str]
    account_id_to_company: dict[str, str]

    def company_for_value(self, value: str) -> str | None:
        return self.value_to_company.get(value)

    def company_for_url(self, url: str) -> str | None:
        """Matches a URL's hostname against every declared identity value
        that looks like a domain/host (a proper suffix match, same
        discipline as the Brightline HostRule matcher — never a raw
        substring). Reads the BROAD index — a domain is host-shaped and
        this only ever parses a real URL's hostname, never scans page
        text, so including domains here is safe."""
        host = _extract_host(url)
        if not host:
            return None
        for value, slug in self.value_to_company.items():
            if "." not in value:
                continue  # not host-shaped (e.g. a bare account id)
            if _host_matches(host, value):
                return slug
        return None

    def account_id_for_text(self, text: str) -> str | None:
        """Major 15: matches a genuine platform account/object id (NEVER a
        brand name, address, or phone number) as a literal substring of
        `text`. Reads the NARROW account-id-only index — this is what
        replaces the old company_for_text, which read the broad index and
        could trigger on a NAP value (e.g. "Brightline Remodeling")
        appearing anywhere on an unrelated page."""
        if not text:
            return None
        for value, slug in self.account_id_to_company.items():
            if value and value in text:
                return slug
        return None

    def account_id_in_tool_input(self, tool_input: dict[str, Any]) -> str | None:
        """Major 15: matches a genuine platform account/object id appearing
        literally as (or within) a tool_input field value — e.g. an
        account id passed as a URL query param or form field — using the
        same narrow account-id-only index."""
        if not tool_input:
            return None
        haystack = " ".join(str(v) for v in tool_input.values() if isinstance(v, (str, int, float)))
        return self.account_id_for_text(haystack)


def _load_index_file(path: Path) -> dict[str, str]:
    value_to_company: dict[str, str] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            for company, values in data.items():
                if company == "other_businesses":
                    continue
                if isinstance(values, list):
                    for v in values:
                        if isinstance(v, str) and v:
                            value_to_company[v] = company
    return value_to_company


def load_identity_index() -> IdentityIndex:
    broad = _load_index_file(company_mod.gtm_state_dir() / "identity_index.json")
    account_ids = _load_index_file(company_mod.gtm_state_dir() / "account_id_index.json")
    return IdentityIndex(value_to_company=broad, account_id_to_company=account_ids)


def _registered_homes() -> dict[str, Path]:
    """slug -> resolved home path, for every registered slug with a
    resolvable root (registry entries without a GTM pack still resolve —
    attribution precedence 2/3 use the registry's `root`, not the pack)."""
    out: dict[str, Path] = {}
    for slug in company_mod.registered_slugs():
        try:
            out[slug] = company_mod.resolve_home(slug)
        except company_mod.CompanyError:
            continue
    return out


def attribute_company(
    *,
    url: str | None,
    tool_input: dict[str, Any] | None,
    server: str | None,
    cwd: str | None,
    identity_index: IdentityIndex,
    homes: dict[str, Path],
) -> str | None:
    """Plan §11.3 precedence, NARROWED by major 7 and major 15: (1)
    identity-index host match (URL hostname), or an account-id match in
    the URL text or tool_input (any server) — NEVER a match against page
    TEXT/result content, and NEVER against a NAP name/address/phone; (2)
    `playwright-gtm` server + cwd under a registered home. Rung 3 ("cwd
    alone", for a non-identity-host call on a non-playwright-gtm server) is
    REMOVED: it used to attribute purely by session cwd regardless of
    server, which both captured browser activity that had nothing to do
    with any company's GTM work (any playwright pool slot navigating
    anywhere, as long as the session's cwd happened to sit under a
    registered home) and mis-scoped the capture-eligibility decision in
    try_classify_call (see there for the mutating-only gate this
    function's callers now enforce)."""
    # (1) identity-index host or account id appearing in the call -- any
    # server. Major 15: text matching uses ONLY the narrow account-id
    # index (account_id_for_text), never the broad index that also holds
    # NAP names/addresses/phones, and never against page result_text/
    # content -- only the URL string itself (which can legitimately carry
    # an account id as a query param) and tool_input field values.
    if url:
        hit = identity_index.company_for_url(url)
        if hit:
            return hit
        hit = identity_index.account_id_for_text(url)
        if hit:
            return hit
    hit = identity_index.account_id_in_tool_input(tool_input or {})
    if hit:
        return hit

    # (2) playwright-gtm server + cwd under a registered home. This is the
    # ONLY remaining cwd-based rung, and it fires only for playwright-gtm.
    if server == "playwright-gtm" and cwd:
        cwd_path = Path(cwd).resolve()
        for slug, home in homes.items():
            try:
                cwd_path.relative_to(home)
                return slug
            except ValueError:
                continue

    return None


# --------------------------------------------------------------------------
# Transcript walking
# --------------------------------------------------------------------------


def result_text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def extract_page_url(result_text: str) -> str | None:
    m = PAGE_URL_RE.search(result_text)
    if m:
        return m.group(1)
    return None


# nit fix: the TOOL_TRAIL.jsonl.ids sidecar helpers (_ids_sidecar_path,
# _trail_stats, _read_sidecar_header_and_ids, _load_ids_from_sidecar,
# _scan_ids_from_jsonl, _write_sidecar_with_header, _rebuild_ids_sidecar,
# verify_sidecar_matches_trail) now live in activity_log.py and are
# reached here via the module-level aliases set up right after this
# module's own `import activity_log as activity_log_mod` line, near the
# top of the file -- see that alias block's comment for why.


def load_existing_ids(paths: list[Path], *, locked_paths: frozenset[Path] | None = None) -> set[str]:
    """Existing tool_use_ids across EVERY given trail file (every company's
    TOOL_TRAIL.jsonl plus the unattributed sink) — idempotency must hold
    globally, not per-file, since a call attributed differently on a re-run
    (e.g. after the identity index changes) must still never duplicate.

    Minor 17: reads each trail's SIDECAR `.ids` index file when present
    (fast, O(existing id count) rather than O(file size)) instead of
    re-parsing the whole JSONL every run. #20: the sidecar is trusted only
    when its header's (size, line count) matches the trail's CURRENT
    stats -- on any mismatch (a lagging sidecar, a crash between the
    JSONL append and the sidecar append, or an out-of-band overwrite of
    the trail file), it is rebuilt from a full scan of TOOL_TRAIL.jsonl
    before use, exactly as for a genuinely missing sidecar.

    Major finding #21-regression fix: `locked_paths`, when given, is the
    set of trail paths whose lock THIS caller currently holds (resolved,
    absolute paths). A trail NOT in that set is never rebuilt here even
    when its sidecar looks drifted -- rebuilding another company's sidecar
    without holding that trail's own lock races a concurrent writer that
    IS holding it: this function's own scan of the trail (to compute
    `scanned`) and that writer's append can interleave, so the freshly
    "rebuilt" sidecar can end up trusted (its header matches the trail's
    post-append stats, since the header is derived from a `_trail_stats`
    call taken AFTER the append) while still missing the id the writer
    just added -- the next harvest run then re-appends that id as a
    duplicate, and `check`'s own drift detector can't see the problem
    because the header genuinely matches. For an unlocked trail whose
    sidecar looks drifted or missing, this falls back to a full scan
    (still correct membership data for the caller's own filtering) but
    does NOT write a sidecar for it -- writing is deferred to whichever
    caller actually holds that trail's lock. `locked_paths=None` (the
    default) preserves the original all-paths-are-mine-to-rebuild
    behavior, for callers that already hold every path's lock themselves
    (or don't care, e.g. a read-only `check`/`index` pass over a single
    trail with no writer)."""
    ids: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        sidecar_ids = _load_ids_from_sidecar(path)
        if sidecar_ids is not None:
            ids.update(sidecar_ids)
            continue
        scanned = _scan_ids_from_jsonl(path)
        ids.update(scanned)
        if locked_paths is None or path.resolve() in locked_paths:
            _rebuild_ids_sidecar(path, scanned)
    return ids


def resolve_transcript_paths(explicit: list[str], homes: dict[str, Path] | None = None) -> list[Path]:
    """Explicit paths always win (test override, kept exactly as before).
    Otherwise, globs are derived from `homes` (major 7: registered homes'
    project dirs + the Brightline legacy dir) — never the old blanket
    `~/.claude/projects/*/*.jsonl` across every project on the machine.
    `homes=None` (e.g. a direct call with no registry available) falls
    back to an EMPTY default rather than silently reverting to the old
    blanket scan.

    #26: the glob-matched candidates are then NARROWED by each transcript's
    own recorded `cwd` -- _matches_project_dir_prefix (used by
    default_globs_for_homes -> _matching_project_dirs) is a deliberately
    permissive separator-bounded match at the DIRECTORY-NAME level, which
    can still admit an unrelated sibling directory whose name merely
    shares the same derived string prefix (directory-name derivation is
    lossy: '/', '_', '.', ' ' all collapse to '-', so no name-only rule can
    fully distinguish a real subfolder from a same-prefix sibling). Real
    membership is settled here against the transcript's own ground-truth
    `cwd` field, checked against the full set of homes this run cares
    about (every registered home plus the Brightline legacy dir) via
    Path.is_relative_to() -- exactly the same discipline blocker 10 uses
    for path containment elsewhere in this module.

    Nit fix: each candidate's `cwd` is now read ONCE (via
    `_read_transcript_cwd`), then tested against every home -- the prior
    version called `_transcript_cwd_is_under_home` once per home, which
    reopened and re-parsed the same transcript file from scratch on every
    call; a transcript under no home was opened `len(homes) + 1` times."""
    if explicit:
        return [Path(p) for p in explicit]
    patterns = default_globs_for_homes(homes) if homes else ()
    paths: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        for p in glob.glob(pattern, recursive=True):
            if p not in seen:
                seen.add(p)
                paths.append(Path(p))
    if homes:
        all_homes = [h.resolve() for h in homes.values()] + [d.resolve() for d in _legacy_workdirs(homes)]

        def _keep(p: Path) -> bool:
            cwd = _read_transcript_cwd(p)
            if cwd is None:
                return True
            try:
                return any(cwd.is_relative_to(home) for home in all_homes)
            except (OSError, ValueError):
                return True

        paths = [p for p in paths if _keep(p)]
    return sorted(paths)


def actor_label_for(agent_id: str | None) -> str:
    if agent_id:
        return f"agent:{agent_id}"
    return "main-session"


def harvest_transcript(
    path: Path,
    identity_index: IdentityIndex,
    homes: dict[str, Path],
    packs: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[str | None, dict[str, Any]]]:
    """Walks one transcript file, pairs tool_use with its tool_result, and
    returns a list of (company_slug_or_None, record) for every
    identity-relevant call found. company_slug is None for an unattributable
    mutating call (goes to the unattributed sink)."""
    out: list[tuple[str | None, dict[str, Any]]] = []
    is_subagent = "/subagents/" in str(path)
    agent_id = None
    if is_subagent:
        m = re.search(r"agent-([0-9a-fA-F]+)\.jsonl$", path.name)
        if m:
            agent_id = m.group(1)

    tool_uses: dict[str, dict[str, Any]] = {}
    tool_use_meta: dict[str, dict[str, Any]] = {}
    tool_results: dict[str, str] = {}

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        session_id = obj.get("sessionId")
        ts = obj.get("timestamp")
        cwd = obj.get("cwd")
        line_agent_id = obj.get("agentId") or agent_id
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            itype = item.get("type")
            if itype == "tool_use":
                tid = item.get("id")
                if not isinstance(tid, str):
                    continue
                tool_uses[tid] = item
                tool_use_meta[tid] = {
                    "session_id": session_id,
                    "ts": ts,
                    "agent_id": line_agent_id,
                    "cwd": cwd,
                }
            elif itype == "tool_result":
                tid = item.get("tool_use_id")
                if not isinstance(tid, str):
                    continue
                tool_results[tid] = result_text_of(item.get("content"))

    last_url_by_server: dict[str, str] = {}

    for tid, item in tool_uses.items():
        name = item.get("name", "")
        tool_input = item.get("input") if isinstance(item.get("input"), dict) else {}
        meta = tool_use_meta.get(tid, {})
        result_text = tool_results.get(tid, "")
        ts = meta.get("ts")
        session_id = meta.get("session_id")
        this_agent_id = meta.get("agent_id")
        cwd = meta.get("cwd")

        classified = try_classify_call(
            tid=tid,
            name=name,
            tool_input=tool_input,
            result_text=result_text,
            ts=ts,
            session_id=session_id,
            agent_id=this_agent_id,
            cwd=cwd,
            transcript_path=path,
            last_url_by_server=last_url_by_server,
            identity_index=identity_index,
            homes=homes,
            packs=packs or {},
        )
        if classified is not None:
            out.append(classified)

    return out


def try_classify_call(
    *,
    tid: str,
    name: str,
    tool_input: dict[str, Any],
    result_text: str,
    ts: Any,
    session_id: Any,
    agent_id: str | None,
    cwd: Any,
    transcript_path: Path,
    last_url_by_server: dict[str, str],
    identity_index: IdentityIndex,
    homes: dict[str, Path],
    packs: dict[str, dict[str, Any]] | None = None,
) -> tuple[str | None, dict[str, Any]] | None:
    packs = packs or {}
    actor_label = actor_label_for(agent_id)
    base = {
        "tool_use_id": tid,
        "ts": ts,
        "session_id": session_id,
        "agent_id": agent_id or "main",
        "actor_label": actor_label,
        "tool": name,
        "transcript": str(transcript_path),
    }

    browser_match = BROWSER_TOOL_RE.match(name)
    if browser_match:
        action = browser_match.group("action")
        server = browser_match.group("server")
        cache_key = f"{transcript_path}::{server}"

        url = extract_page_url(result_text)
        if url is None and action == "navigate" and isinstance(tool_input.get("url"), str):
            url = tool_input["url"]
        if url is None:
            url = last_url_by_server.get(cache_key)
        if url:
            last_url_by_server[cache_key] = url

        if not url:
            return None

        # Compute mutating status FIRST -- major 7's capture rule is now
        # "capture only MUTATING calls" via either path (a) any server to
        # an identity-index host, or (b) any call on playwright-gtm. A
        # non-mutating call (navigate, snapshot, hover, ...) is never
        # captured at all, regardless of server or cwd.
        detail: dict[str, Any] = {}
        if action in ("run_code_unsafe", "evaluate"):
            code = tool_input.get("code") or tool_input.get("function") or ""
            code = code if isinstance(code, str) else ""
            mutating = code_is_mutating(code)
            if code:
                detail["code"] = redact_text(code[:3000])
        else:
            mutating = action in MUTATING_BROWSER_ACTIONS
        if not mutating:
            return None

        # Major 15: capture triggers ONLY on a host match (URL) or an
        # account-id match in the URL string or tool_input -- NEVER on a
        # NAP name/address/phone appearing in page TEXT (result_text is
        # deliberately excluded here; a page can say "Brightline
        # Remodeling" anywhere without that alone making the call ours).
        identity_hit = (
            identity_index.company_for_url(url)
            or identity_index.account_id_for_text(url or "")
            or identity_index.account_id_in_tool_input(tool_input)
        )
        on_identity_host = identity_hit is not None
        on_gtm_server = server == "playwright-gtm"

        if not on_identity_host and not on_gtm_server:
            # Neither capture path (a) nor (b) applies -- not eligible at
            # all (blocker/major 7: cwd-only attribution for a non-GTM
            # server is REMOVED; this call is simply not ours to record).
            return None

        company = attribute_company(
            url=url,
            tool_input=tool_input,
            server=server,
            cwd=cwd if isinstance(cwd, str) else None,
            identity_index=identity_index,
            homes=homes,
        )

        if action in ("click", "type", "fill_form", "select_option", "press_key"):
            for key in ("element", "selector", "text", "value", "ref"):
                v = tool_input.get(key)
                if isinstance(v, str):
                    if "password" in key.lower() or "password" in str(tool_input.get("element", "")).lower():
                        detail[key] = "<redacted>"
                    else:
                        detail[key] = redact_text(v)

        excerpt = redact_text(result_text[:600])
        # host_system_for_url wants the attributed company's OWN pack (for
        # its host_systems overrides + brand domains) -- `company` is the
        # final attribution result (identity hit or playwright-gtm+cwd);
        # falling back to `identity_hit`'s pack when `company` differs
        # covers the unattributed-sink case (company is None but
        # identity_hit named a company whose pack we still have).
        pack_for_system = packs.get(company) or packs.get(identity_hit)
        system = host_system_for_url(url, pack_for_system)

        record = dict(base)
        record.update(
            {
                "url": url,
                "system": system,
                "mutating": mutating,
                "detail": detail,
                "result_excerpt": excerpt,
                "server": server,
            }
        )
        # gtm-offserver (finding 12): a mutating call on a NON-playwright-gtm
        # server that DID match an identity host (capture path (a)) still
        # gets attributed and captured -- but flagged, since this is
        # exactly the "browser off-server bypass" the plan's G-A §7.1
        # calls detect-after: the action happened outside the governed
        # playwright-gtm server/ticket system.
        if on_identity_host and not on_gtm_server:
            record["offserver"] = True
        record = finalize_record(record)

        if company is None:
            # Eligible for capture (matched path (a) or (b) above) but the
            # attribution precedence itself could not resolve to exactly
            # one company (e.g. an identity-index text-substring hit with
            # no URL-host match, and no playwright-gtm+cwd fallback) ->
            # the cross-company unattributed sink, never silently dropped
            # and never mis-filed under a guessed company.
            return (None, record)
        return (company, record)

    if name in ("Write", "Edit", "NotebookEdit"):
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not isinstance(file_path, str):
            return None
        company = None
        for slug, home in homes.items():
            try:
                Path(file_path).resolve().relative_to(home)
                company = slug
                break
            except ValueError:
                continue
        if company is None:
            return None
        record = dict(base)
        record.update(
            {
                "url": None,
                "system": "local_files",
                "mutating": True,
                "detail": {"file_path": file_path, "action": "create" if name == "Write" else "edit"},
                "result_excerpt": redact_text(result_text[:600]),
            }
        )
        return (company, finalize_record(record))

    if name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return None
        company = None
        for slug, home in homes.items():
            if str(home) in command:
                company = slug
                break
        if company is None:
            return None
        record = dict(base)
        record.update(
            {
                "url": None,
                "system": "local_files",
                "mutating": True,
                "detail": {"command": redact_text(command[:1500])},
                "result_excerpt": redact_text(result_text[:600]),
            }
        )
        return (company, finalize_record(record))

    if name == "Agent":
        prompt = tool_input.get("prompt")
        description = tool_input.get("description")
        haystack = f"{prompt or ''} {description or ''}".lower()
        company = None
        for slug in homes:
            if slug in haystack:
                company = slug
                break
        if company is None:
            return None
        record = dict(base)
        record.update(
            {
                "url": None,
                "system": "agent_dispatch",
                "mutating": True,
                "detail": {
                    "subagent_type": tool_input.get("subagent_type"),
                    "description": description,
                    "prompt_excerpt": redact_text((prompt or "")[:400]),
                },
                "result_excerpt": redact_text(result_text[:600]),
            }
        )
        return (company, finalize_record(record))

    return None


def finalize_record(record: dict[str, Any]) -> dict[str, Any]:
    detail = record.get("detail")
    detail_text = ""
    if isinstance(detail, dict):
        detail_text = " ".join(str(v) for v in detail.values())
    elif isinstance(detail, str):
        detail_text = detail
    result_excerpt = record.get("result_excerpt") or ""
    if looks_like_credential_context(detail_text) or looks_like_credential_context(result_excerpt):
        record["detail"] = REDACT_CREDENTIAL_MARKER
        record["result_excerpt"] = REDACT_CREDENTIAL_MARKER
    return record


def _trail_path_for_company(slug: str) -> Path:
    paths = activity_log_mod.resolve_paths(slug)
    return paths.trail_jsonl


def _lock_path_for_trail(path: Path) -> Path:
    """The lock guarding a trail file. For a company's own TOOL_TRAIL.jsonl
    this is the SAME lock activity_log.py uses for that company's
    ACTIVITY_LOG.jsonl (paths.lock_file lives in the same
    activity_log_dir) -- reusing it, rather than a second lock file next to
    the trail, means a concurrent `activity_log.py add` and a harvest run
    against the same company can never interleave their reads of "the
    current last line" either. For the cross-company unattributed sink
    (which has no CompanyPaths / no company), the lock lives next to the
    sink file itself."""
    return path.parent / ".activity_log.lock"


def _appended_line_byte_length(written_entry: dict[str, Any]) -> int:
    """#20: the exact byte length (including its trailing newline) of the
    JSONL line activity_log_mod._append_chained just wrote for
    `written_entry` -- reproduces its EXACT serialization
    (`json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\\n"`,
    UTF-8 encoded) so the byte count here is guaranteed identical to what
    was actually written to disk, never an approximation."""
    line = json.dumps(written_entry, ensure_ascii=False, sort_keys=True) + "\n"
    return len(line.encode("utf-8"))


def _append_chained_trail(path: Path, record: dict[str, Any]) -> None:
    """Major 6: appends under an exclusive flock spanning BOTH the
    read-last-line step (inside _append_chained) and the write -- without
    this, two concurrent harvesters (or a harvester racing an
    activity_log.py add) can both read the same "last line" and each
    compute prev_hash from it, producing two chained lines with the SAME
    prev_hash (a fork, not a chain) and silently corrupting the hash chain
    that verify_chain()/`check` depends on.

    Minor 17/#20: also appends the new record's tool_use_id to the trail's
    sidecar `.ids` index (under the SAME lock) and refreshes its header
    to match the trail's post-append stats, so the sidecar and the JSONL
    never drift out of sync with each other.

    Nit fix: delegates to `_append_many_chained_trail_locked` (a
    single-record list) rather than keeping its own separate per-record
    whole-sidecar-rewrite implementation (and drift fallback) duplicated
    and drifting out of sync with the batch path's own fix history --
    every trail write, single-record or batch, now goes through exactly
    one sidecar-maintenance code path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path_for_trail(path)
    with activity_log_mod.LockedFile(lock_path):
        _append_many_chained_trail_locked(path, [record])


def _append_chained_trail_locked(path: Path, record: dict[str, Any]) -> None:
    """Same write as _append_chained_trail, but WITHOUT taking its own
    lock -- for use inside a caller that already holds the relevant lock
    (e.g. per-record inside main()'s #21 narrowed lock hold). Kept as a
    separate function (rather than a lock-optional parameter on the
    original) so _append_chained_trail's own docstring/contract — "always
    self-locking" — stays true for every OTHER caller, including the
    concurrency test that calls it directly and relies on that guarantee.

    Nit fix: no production caller of this single-record path remains
    (`_flush_locked` uses `_append_many_chained_trail_locked` for every
    real harvest flush); this now delegates to that batch helper with a
    single-record list rather than keeping its own separate per-record
    whole-sidecar-rewrite implementation (and the drift fallback that
    used to live there) duplicated and drifting out of sync with the
    batch path's own fix history. Still kept as its own named function
    (rather than deleted outright) since tests use it directly to build
    up trail state one record at a time."""
    _append_many_chained_trail_locked(path, [record])


def _append_many_chained_trail_locked(path: Path, records: list[dict[str, Any]]) -> None:
    """Major finding (scalability): appends every record in `records` to
    `path` (via `activity_log_mod._append_chained`'s own per-line write, so
    the hash chain is built exactly as before, one line at a time, each
    depending on the previous line's hash) but updates `path`'s sidecar
    `.ids` index ONCE at the end, rather than once per record.

    Root cause this replaces: the pre-fix per-record append path read the
    WHOLE sidecar (`_read_sidecar_header_and_ids`) and rewrote the WHOLE
    sidecar (`_write_sidecar_with_header`) on every single record, so N
    appends in one flush cost O(N x sidecar_size) -- quadratic in the
    sidecar's total id count once it's large (measured: ~8ms per append
    at 20k existing ids, 116s to seed 20k records through
    _append_chained_trail). Reading the sidecar once, building the full
    new id set and header in memory, and writing it back once makes one
    flush's sidecar cost O(sidecar_size) total, independent of how many
    records this flush appends.

    Caller must already hold `path`'s lock (same contract as
    `_append_chained_trail_locked`, which now delegates here).

    Major finding (regression fix): when the prior header is untrustworthy
    (drifted or absent), `ids` must NOT be seeded from the drifted
    sidecar's own (already-wrong) id set -- doing so and then rebuilding
    with a header freshly computed from the trail's post-append stats
    produces a sidecar that matches the trail's shape exactly (so
    `check`'s drift detector reports clean) while the id set underneath
    it is still missing whatever the drift represented (e.g. a record
    written directly to the trail between two sidecar syncs, such as a
    crash mid-append) -- this function's `header_trustworthy` fallback
    to `_scan_ids_from_jsonl` (ground truth from the trail itself, never
    the drifted sidecar's own id set) closes that."""
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = _ids_sidecar_path(path)
    header, sidecar_ids = _read_sidecar_header_and_ids(sidecar)
    size = header.get("size") if header else None
    lines = header.get("lines") if header else None
    header_trustworthy = isinstance(size, int) and isinstance(lines, int)
    if header_trustworthy:
        # Nit (deliberately NOT "fixed" by also scanning for a line-count
        # match here): trusting the header on a SIZE match alone means a
        # header whose `lines` had drifted independently of `size` (an
        # arrangement that should never happen through this module's own
        # write paths, since every write updates both together, but could
        # follow an out-of-band trail edit) keeps its stale `lines` count
        # one more round-trip, which `check`'s drift detector can then
        # briefly re-report right after a clean harvest -- self-healing on
        # the very next load via `_read_sidecar_header_and_ids`'s own
        # rebuild. Actually confirming `lines` here would require a real
        # `_trail_stats` content scan on every trusted-header append, which
        # `test_append_never_triggers_a_full_trail_rescan_via_trail_stats`
        # holds this exact function to never doing (measured regression if
        # it did: 200 appends against a 13.5 MB trail went from 0.03s to
        # 3.59s, ~120x, all under the company lock) -- the O(1) fast path
        # is the deliberately-kept tradeoff, not an oversight.
        actual_size = _path_size(path)
        header_trustworthy = actual_size == size

    # Ground truth for the untrustworthy-header fallback is a real scan
    # of the trail itself, never the drifted sidecar's own id set --
    # `_trail_stats` already makes this branch O(trail size), so the scan
    # (taken BEFORE this batch's own appends below) does not change its
    # complexity class.
    ids = sidecar_ids if header_trustworthy else _scan_ids_from_jsonl(path)

    for record in records:
        written_entry = activity_log_mod._append_chained(path, record)  # noqa: SLF001 - same module family
        tid = record.get("tool_use_id")
        if isinstance(tid, str) and tid:
            ids.add(tid)
        if header_trustworthy:
            size += _appended_line_byte_length(written_entry)  # type: ignore[operator]
            lines += 1  # type: ignore[operator]

    if header_trustworthy:
        _write_sidecar_with_header(path, size, lines, ids)  # type: ignore[arg-type]
    else:
        _rebuild_ids_sidecar(path, ids)


def _sort_key(r: dict[str, Any]) -> str:
    ts = r.get("ts")
    return ts if isinstance(ts, str) else ""


def _flush_locked(
    target: Path,
    candidates: list[dict[str, Any]],
    all_trail_paths: list[Path],
    *,
    return_ids: bool = False,
) -> int | tuple[int, frozenset[str]]:
    """Major finding #21-regression fix: takes EVERY trail's lock in
    `all_trail_paths` (every registered company's TOOL_TRAIL.jsonl plus the
    cross-company unattributed sink), in sorted lock-path order --
    deadlock-free, since every caller (this function, called once per
    company/sink target within one `main()` run) acquires the same set of
    locks in the same total order, so two concurrent flushes can never
    each hold one lock while waiting on a lock the other already holds.
    Then reloads existing_ids FRESH from every trail -- so a call that
    gets attributed to a DIFFERENT company on a re-run (e.g. after the
    identity index changes) is still recognized as already-recorded and
    never duplicated into a second company's trail. Filters and appends
    `candidates` under `target`'s lock. Returns the count actually
    appended (after re-filtering -- some candidates may have been written
    by a concurrent process during the unlocked scan phase, or already
    exist under a different company's trail, and are now correctly
    skipped) -- or, when `return_ids=True`, a `(count, frozenset_of_
    appended_tool_use_ids)` pair (major finding #1: lets a caller like
    main()'s unattributed-sink flush tell exactly WHICH candidates were
    genuinely newly appended this run, race-free -- computed from the same
    locked re-filter that determines `fresh`, never a separate unlocked
    pre-read that could go stale between reading and the flush's own lock
    acquisition).

    Prior version (#21) took only `target`'s own lock and called
    `load_existing_ids` unconditionally, which could REBUILD another
    company's sidecar without holding that trail's lock -- racing a
    concurrent writer that IS holding it (see load_existing_ids's own
    `locked_paths` docstring for the exact interleaving that produced a
    sidecar TRUSTED while missing an id). Holding every trail's lock here
    closes that: `load_existing_ids(locked_paths=...)` is now free to
    rebuild every sidecar it reads, because every one of those trails is
    genuinely quiescent for the duration of this read."""
    if not candidates:
        return (0, frozenset()) if return_ids else 0
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_paths = sorted({_lock_path_for_trail(p) for p in all_trail_paths} | {_lock_path_for_trail(target)})
    for lp in lock_paths:
        lp.parent.mkdir(parents=True, exist_ok=True)
    appended = 0
    appended_ids: frozenset[str] = frozenset()
    with contextlib.ExitStack() as stack:
        for lp in lock_paths:
            stack.enter_context(activity_log_mod.LockedFile(lp))
        locked_paths = frozenset(p.resolve() for p in all_trail_paths) | {target.resolve()}
        existing_ids = load_existing_ids(all_trail_paths, locked_paths=locked_paths)
        fresh = [c for c in candidates if c["tool_use_id"] not in existing_ids]
        fresh.sort(key=_sort_key)
        # Scalability fix: one sidecar read + one sidecar write for this
        # whole flush's worth of appends, not one of each per record --
        # see _append_many_chained_trail_locked's own docstring.
        _append_many_chained_trail_locked(target, fresh)
        appended = len(fresh)
        if return_ids:
            appended_ids = frozenset(c["tool_use_id"] for c in fresh)
    return (appended, appended_ids) if return_ids else appended


def _flush_many_locked(
    flushes: list[tuple[Path, list[dict[str, Any]]]],
    all_trail_paths: list[Path],
) -> dict[Path, tuple[int, frozenset[str]]]:
    """Minor finding (scalability): the multi-target equivalent of
    `_flush_locked`, for a `main()` run that flushes several targets
    (each registered company plus the unattributed sink) against the SAME
    `all_trail_paths` idempotency set in one run. Takes every trail's lock
    ONCE (sorted, deadlock-free, exactly as `_flush_locked` does per call),
    loads `existing_ids` ONCE from that single locked read, then re-filters
    and appends each target's own candidates under that one lock hold --
    instead of `_flush_locked` being called once per target, each call
    independently re-taking every lock and re-running `load_existing_ids`
    over every trail from scratch.

    Root cause this replaces: `main()` used to call `_flush_locked` once
    per company plus once for the unattributed sink -- (companies + 1)
    calls, each re-scanning (or re-reading the sidecar of) every trail in
    `all_trail_paths`, an O((companies + 1) x trails) = O((companies + 1)^2)
    total read cost for one harvest run (measured: ~25 full trail reads,
    trails up to 14 MB, with 4 companies). Reading `existing_ids` once and
    reusing it for every target's re-filter makes one run's total read
    cost O(trails) -- independent of how many targets this run flushes.

    `flushes` may contain a target with an EMPTY candidate list (e.g. a
    company this run scanned but found nothing new for) -- exactly like
    `_flush_locked`, that target is skipped (no lock-hold work, `(0,
    frozenset())` returned for it) without needing every OTHER target's
    flush to also be skipped.

    Returns `{target: (appended_count, appended_tool_use_ids)}` for every
    target in `flushes`, in the same `(int, frozenset[str])` shape
    `_flush_locked(..., return_ids=True)` returns -- callers that don't
    need the ids can just take `[0]` of each value, exactly as before."""
    non_empty = [(target, candidates) for target, candidates in flushes if candidates]
    results: dict[Path, tuple[int, frozenset[str]]] = {
        target: (0, frozenset()) for target, _candidates in flushes
    }
    if not non_empty:
        return results

    for target, _candidates in non_empty:
        target.parent.mkdir(parents=True, exist_ok=True)

    lock_paths = sorted(
        {_lock_path_for_trail(p) for p in all_trail_paths}
        | {_lock_path_for_trail(target) for target, _candidates in non_empty}
    )
    for lp in lock_paths:
        lp.parent.mkdir(parents=True, exist_ok=True)

    with contextlib.ExitStack() as stack:
        for lp in lock_paths:
            stack.enter_context(activity_log_mod.LockedFile(lp))
        locked_paths = frozenset(p.resolve() for p in all_trail_paths) | {
            target.resolve() for target, _candidates in non_empty
        }
        # Loaded ONCE for every target this run flushes -- the whole point
        # of this function over calling _flush_locked per target.
        existing_ids = load_existing_ids(all_trail_paths, locked_paths=locked_paths)

        for target, candidates in non_empty:
            fresh = [c for c in candidates if c["tool_use_id"] not in existing_ids]
            fresh.sort(key=_sort_key)
            _append_many_chained_trail_locked(target, fresh)
            fresh_ids = frozenset(c["tool_use_id"] for c in fresh)
            results[target] = (len(fresh), fresh_ids)
            # A tool_use_id appended to THIS target must count as
            # already-existing for every subsequent target in this same
            # batch -- otherwise the same id appearing in two targets'
            # candidate lists (e.g. re-attributed between company and the
            # unattributed sink within one run) could be double-appended,
            # exactly the cross-trail idempotency `existing_ids` exists to
            # enforce. `_flush_locked` never had this hazard since it only
            # ever flushed ONE target per lock hold.
            existing_ids = existing_ids | fresh_ids

    return results


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    identity_index = load_identity_index()
    # Nit fix: `_registered_homes` calls `company_mod.registered_slugs()`,
    # which RAISES CompanyError (never swallows) on a present-but-corrupt
    # registry -- by design, so callers can tell "nothing registered" from
    # "a real registry failure" (see registered_slugs's own docstring).
    # `main` never caught it, so a corrupt gtm_company_registry.json or
    # repo_registry.json died here with a raw, uncaught traceback instead
    # of the same clean non-zero-exit-with-reason every other CLI entry
    # point in this module family gives for the identical failure.
    try:
        homes = _registered_homes()
    except company_mod.CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    transcript_paths = resolve_transcript_paths(argv, homes=homes)

    if not transcript_paths:
        print("no transcript files found (checked default globs and any explicit paths given)")
        return 0

    packs: dict[str, dict[str, Any]] = {}
    for slug in homes:
        try:
            packs[slug] = company_mod.load_pack(slug)
        except company_mod.CompanyError:
            continue

    company_trail_paths: dict[str, Path] = {}
    for slug in homes:
        try:
            company_trail_paths[slug] = _trail_path_for_company(slug)
        except Exception:
            continue
    unattributed_path = company_mod.gtm_state_dir() / "unattributed_trail.jsonl"

    # Major finding #1 (regression fix): `_registered_homes()` deliberately
    # includes every registered home with a resolvable root, even one with
    # NO GTM pack (README §3.1: a pack-less registered repo -- e.g. one
    # registered only in repo_registry.json for other tooling -- is not a
    # GTM company at all). Rung 2 of attribute_company ("playwright-gtm
    # server + cwd under a registered home") used the FULL `homes` dict,
    # so a playwright-gtm call whose cwd happened to sit under such a
    # pack-less home was attributed to that slug anyway -- a slug that
    # will NEVER have an entry in company_trail_paths, since there's no
    # pack to derive one from. That record was correctly rerouted to the
    # unattributed sink (never dropped), but `had_unresolvable_company`
    # below used to fire every single time this happened, even on a
    # completely healthy setup, keeping a scheduled harvest red forever.
    # Restrict rung-2 attribution to homes that actually have a loadable
    # pack (equivalently, a resolvable trail path) so this is no longer
    # treated as a configuration problem at all -- it's expected, and the
    # record is simply unattributed by design, exactly like any other
    # non-identity-host call with no registered-company cwd match.
    attribution_homes = {slug: home for slug, home in homes.items() if slug in company_trail_paths}

    # #21: transcripts are scanned WITHOUT holding any lock -- a scan over
    # many/large transcript files can take a while, and holding a
    # company's activity-log lock for that whole duration would block a
    # concurrent `activity_log.py add` (or another harvest run) for no
    # reason: nothing about reading transcript JSONL files touches the
    # trail file or its lock at all. This DOES mean the same tool_use_id
    # could, in principle, be produced by two concurrent scans; that is
    # resolved correctly below, where each trail's candidates are
    # re-filtered against a FRESH existing_ids read taken under that
    # trail's own lock, immediately before appending.
    new_by_company: dict[str, list[dict[str, Any]]] = {}
    new_unattributed: list[dict[str, Any]] = []

    for path in transcript_paths:
        if not path.exists():
            continue
        for company, record in harvest_transcript(path, identity_index, attribution_homes, packs=packs):
            if company is None:
                new_unattributed.append(record)
            else:
                new_by_company.setdefault(company, []).append(record)

    # Within one company's OWN candidate list, a transcript scan itself
    # can never produce the same tool_use_id twice (harvest_transcript
    # dedupes by tid within a single transcript file's tool_uses dict,
    # and different transcripts describing the SAME real tool call share
    # the same tid) -- but two DIFFERENT transcript files scanned in this
    # same run could each describe the same tool_use_id (e.g. the main
    # transcript and a re-synced copy); dedupe defensively before the
    # locked flush so _flush_locked's own existing_ids re-filter is the
    # only place duplicates are resolved against what's ALREADY on disk,
    # not against duplicates created by THIS run's own scan.
    def _dedupe_by_tid(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for r in records:
            tid = r["tool_use_id"]
            if tid in seen:
                continue
            seen.add(tid)
            out.append(r)
        return out

    # #21 (regression fix): the set of every trail idempotency must be
    # checked against -- every registered company's own trail plus the
    # cross-company unattributed sink -- computed ONCE and passed to every
    # _flush_locked call so a re-attributed call (same tool_use_id,
    # different company on this run than a previous one) is recognized no
    # matter which trail it previously landed in.
    all_trail_paths = list(company_trail_paths.values()) + [unattributed_path]

    # Regression fix (post-#21 lock-narrowing): new_by_company/
    # new_unattributed hold every CANDIDATE this run's scan produced,
    # including ones already on disk from a prior run -- _flush_locked's
    # own re-filter against existing_ids is what turns "candidates" into
    # "genuinely new appends", and its return value is the only place that
    # distinction is known. Track appended counts per company (and for the
    # unattributed sink) separately from new_by_company/new_unattributed,
    # so the summary reports what was actually WRITTEN this run, not what
    # was merely scanned -- re-running main() on an unchanged transcript
    # set must report zero per-company lines and "new records: 0", not the
    # full candidate counts every time.
    appended_by_company: dict[str, int] = {}
    appended_unattributed = 0

    total_new = 0
    unresolvable_companies: set[str] = set()
    # Major finding #1 (regression fix): a rerouted record's tool_use_id is
    # tracked separately from the ordinary (rung-1/rung-2-failed, `company
    # is None` from harvest_transcript itself) unattributed candidates, so
    # the exit code below can tell "this run's unattributed sink append
    # included at least one record that was rerouted because its company
    # had no resolvable trail" from "every unattributed candidate this run
    # was already-on-disk from a prior run" (in which case `_flush_locked`
    # appends nothing NEW at all, and there is nothing for an unattended
    # run to be surprised by).
    rerouted_tids: set[str] = set()
    # Scalability fix: every target's candidates are collected here and
    # flushed ONCE, together, via `_flush_many_locked` below -- rather than
    # calling `_flush_locked` once per company (plus once for the
    # unattributed sink), each call independently re-taking every trail's
    # lock and re-reading `existing_ids` from every trail in
    # `all_trail_paths` from scratch. See `_flush_many_locked`'s own
    # docstring for the O((companies+1)^2) -> O(trails) complexity this
    # closes.
    pending_flushes: dict[Path, list[dict[str, Any]]] = {}
    company_by_target: dict[Path, str] = {}
    for company, records in new_by_company.items():
        target = company_trail_paths.get(company)
        if target is None:
            # Major finding #1 (regression fix): at HEAD this used to be
            # `company_trail_paths[company]`, which raised KeyError -- loud
            # and unmissable. A slug attributed by harvest_transcript (via
            # the identity index or a registered home WITH a loadable pack
            # -- rung 2 is now scoped to attribution_homes, so a home with
            # no GTM pack at all can no longer reach this branch) but
            # absent from company_trail_paths happens when
            # identity_index.json is stale relative to the registry (e.g.
            # after `company.py unregister` with no re-index, or a
            # duplicate-registered slug excluded by registered_slugs()) or
            # when load_pack / _trail_path_for_company failed for that slug
            # in the loops above. Silently `continue`-ing here dropped
            # every such record on the floor -- never written to ANY
            # trail, including the unattributed sink -- and every later
            # run re-harvests and re-drops them, forever, with no warning.
            # The operator's standing rule is that every change is logged;
            # losing audit-trail records silently is exactly the failure
            # mode that rule forbids. Route them to the unattributed sink
            # instead (never lost) and warn loudly, naming the slug and
            # the count.
            print(
                f"warning: {len(records)} record(s) attributed to {company!r} but no trail path "
                "could be resolved for it (no GTM pack for that registered home, a stale "
                "identity_index.json, an unregistered/duplicate slug, or a load_pack/trail-path "
                "failure) -- routing to the unattributed sink instead of dropping them",
                file=sys.stderr,
            )
            new_unattributed.extend(records)
            unresolvable_companies.add(company)
            rerouted_tids.update(r["tool_use_id"] for r in records)
            continue
        pending_flushes.setdefault(target, []).extend(_dedupe_by_tid(records))
        company_by_target[target] = company

    # Major finding #1 (regression fix): a non-zero exit must reflect a
    # genuine problem an unattended run should surface, not merely "an
    # unresolvable company was SEEN this run" -- a slug can be unresolvable
    # on every run over the same already-harvested transcripts (nothing
    # new to append, since idempotency already recorded those tool_use_ids
    # in a prior run's unattributed-sink flush), and a scheduled harvest
    # must not stay permanently red for a condition that stopped producing
    # any new effect. `_flush_locked(..., return_ids=True)` is the only
    # race-free place "genuinely appended this run, not merely a
    # re-scanned candidate" is known, so exit non-zero only when at least
    # one of THIS run's actually-appended unattributed records came from
    # an unresolvable-company reroute (never merely because
    # unresolvable_companies is non-empty).
    had_unresolvable_company = False
    if new_unattributed:
        pending_flushes.setdefault(unattributed_path, []).extend(_dedupe_by_tid(new_unattributed))

    # Scalability fix: one combined lock-hold + one `existing_ids` read for
    # every target this run touches (every company with new records, plus
    # the unattributed sink), instead of one `_flush_locked` call -- and one
    # full re-read of every trail -- per target.
    flush_results = _flush_many_locked(
        [(target, records) for target, records in pending_flushes.items()], all_trail_paths
    )
    for target, (appended, _ids) in flush_results.items():
        company = company_by_target.get(target)
        if company is not None:
            appended_by_company[company] = appended_by_company.get(company, 0) + appended
            total_new += appended
    if unattributed_path in flush_results:
        appended_unattributed, newly_appended_tids = flush_results[unattributed_path]
        total_new += appended_unattributed
        if unresolvable_companies:
            had_unresolvable_company = bool(rerouted_tids & newly_appended_tids)

    print(f"scanned {len(transcript_paths)} transcript file(s)")
    print(f"new records: {total_new}")
    nonzero_by_company = {c: n for c, n in appended_by_company.items() if n > 0}
    if nonzero_by_company:
        print("by company:")
        for company in sorted(nonzero_by_company):
            print(f"  {company}: {nonzero_by_company[company]}")
    if appended_unattributed > 0:
        print(f"unattributed (mutating, identity-host, no company match): {appended_unattributed}")
    # Major finding #1: a slug with no resolvable trail path whose records
    # were GENUINELY, NEWLY rerouted this run is a real configuration
    # problem (a stale identity index, unregistered/duplicate slug, or a
    # load failure -- never merely "a registered home has no GTM pack",
    # which rung 2 no longer attributes to at all) -- exit non-zero so an
    # unattended run (a scheduled job) surfaces it instead of reporting a
    # clean 0-problems exit while it silently rerouted records to the
    # unattributed sink. A re-run over the same already-rerouted
    # transcripts, with nothing new to append, exits 0.
    return 1 if had_unresolvable_company else 0


if __name__ == "__main__":
    sys.exit(main())
