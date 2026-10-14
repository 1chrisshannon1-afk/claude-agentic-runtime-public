#!/usr/bin/env python3
"""company.py — resolves and validates a GTM company pack (plan §3.1–§3.3).

A "company pack" is `<home>/.claude/gtm/company.json`; its presence, not any
registry flag, is what makes a registered repo a GTM company (plan §3.1: "A
pack's presence is what makes a registered repo a GTM company"). `<home>` is
resolved from `~/.claude/knowledge/repo_registry.json`'s `<slug>.root`
(entries created by `scripts/repo_manifest.py register` — this module never
writes the registry, only reads it).

The runtime root is overridable via env `CLAUDE_DIR` (default `~/.claude`) so
tests never touch the real `~/.claude` or a real company home.

Subcommands
-----------
    resolve <slug>              print the home path; non-zero if missing/invalid
    validate <slug>|--all       print OK / INVALID <reason> per pack
    index                       write ~/.claude/.gtm_state/identity_index.json
    gitignore <slug>            print the generated .gitignore block
    backup-set <slug>           print the absolute paths of every backed-up path

Validation is pure stdlib Python (no `jsonschema` dependency) — see
`validate_company()`. `company_schema.json` next to this file documents every
key for humans; it is not read by this validator.

Uses only Python's standard library. No network calls.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# Same shape scripts/repo_manifest.py enforces for a repo_registry.json slug
# (SLUG_RE there). A GTM company pack's slug becomes a filesystem path
# component (backup_set's tickets/<slug> and leases/<slug>.lock, env var
# CLAUDE_GTM_COMPANY, and the ticket/lease keys) -- an unvalidated slug like
# "../../evil" lets register_gtm_company/backup_set/backup_company escape
# their intended directories entirely. Packs are agent-authored (/gtm-onboard
# writes company.json), so this is a prompt-injection-reachable path; the
# fix enforces the same invariant repo_manifest.py already relies on for
# every registry key, for BOTH registries a slug can land in.
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")

# --------------------------------------------------------------------------
# Runtime root / registry resolution
# --------------------------------------------------------------------------


def claude_dir() -> Path:
    """The runtime root. Overridable via env CLAUDE_DIR so tests never touch
    the real ~/.claude."""
    override = os.environ.get("CLAUDE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".claude"


def registry_path() -> Path:
    return claude_dir() / "knowledge" / "repo_registry.json"


def gtm_registry_path() -> Path:
    """The GTM-only company registry (coordinator directive, this round):
    `scripts/repo_manifest.py` is frozen (parked uncommitted work
    elsewhere) and its `register` subcommand refuses a home with no
    GitHub remote — which Brightline, Maplewood, and Opswell all are
    (local-only git repos, no remote). This machine-local registry gives
    those homes a place to register without touching repo_registry.json
    or repo_manifest.py at all. Shape: {"schema_version": 1, "companies":
    {"<slug>": {"root": "<abs or ~ path>"}}}."""
    return claude_dir() / "knowledge" / "gtm_company_registry.json"


def gtm_state_dir() -> Path:
    return claude_dir() / ".gtm_state"


def _gtm_registry_lock_path() -> Path:
    """The lock guarding read-modify-write access to
    gtm_company_registry.json. Nit fix: register/unregister used to write
    with no lock at all, so two concurrent calls could each read the
    registry, each add/remove their own slug in memory, and one write
    could silently clobber the other's -- a real (if narrow) window,
    since both calls also each write via the SAME fixed tmp filename
    (`<target>.json.tmp`), which is itself its own separate race (see
    `_atomic_write_json`'s own fix).

    Major finding #3: lives under `gtm_state_dir()` (`~/.claude/.gtm_state/`),
    NOT next to gtm_company_registry.json under `knowledge/` -- that
    directory is covered by ~/.claude/.gitignore's whitelist-everything
    model via a glob pattern (`knowledge/gtm_company_registry.json*`,
    widened by major finding #3's own fix to also cover
    `_atomic_write_json`'s mkstemp staging file), but a lock file living
    right next to it (`knowledge/gtm_company_registry.json.lock`, which
    exists after the very first register/unregister call) is still a
    machine-written file with no business being tracked at all, sitting
    right beside the private-business-path registry it guards. `.gtm_state/`
    is never re-included by that whitelist at all, so anything under it is
    ignored regardless of name -- the cleaner, more defensive home."""
    return gtm_state_dir() / "gtm_company_registry.json.lock"


def _atomic_write_json(target: Path, data: dict[str, Any]) -> None:
    """Writes `data` as JSON to `target` atomically. Nit fix: uses
    `tempfile.mkstemp` for a UNIQUELY-named tmp file in the same
    directory, never a fixed `<target>.json.tmp` name -- a fixed name lets
    two concurrent writers race `os.replace` (one process's replace can
    consume the other's half-written tmp file, or raise FileNotFoundError
    when the other's replace already consumed it first)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class CompanyError(Exception):
    """Raised when a slug cannot be resolved to a home, or the pack file is
    missing/unreadable. Distinct from a *validation* failure (a resolvable,
    readable pack whose CONTENT is invalid) — validate_company() reports
    those as (False, reason) rather than raising, since `validate` must be
    able to report every pack's reasons rather than stopping at the first."""


def load_registry() -> dict[str, Any]:
    path = registry_path()
    if not path.exists():
        raise CompanyError(f"registry not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # Names the file explicitly (matching load_gtm_registry's own
        # message convention) -- an unreadable-registry diagnosis is only
        # useful if it says WHICH registry, especially now that this error
        # propagates all the way up through registered_slugs/resolve_home
        # instead of being silently swallowed into "nothing registered".
        raise CompanyError(f"{path} unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise CompanyError(f"{path} is not a JSON object")
    return data


def load_gtm_registry() -> dict[str, Any]:
    """Loads gtm_company_registry.json. A MISSING file is not an error
    (most repos never have one) -- returns an empty {"companies": {}}
    shape. A present-but-unparseable file IS an error (surfaced via
    CompanyError), same discipline as load_registry()."""
    path = gtm_registry_path()
    if not path.exists():
        return {"schema_version": 1, "companies": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompanyError(f"gtm_company_registry.json unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise CompanyError("gtm_company_registry.json is not a JSON object")
    return data


def _gtm_registry_companies() -> dict[str, Any]:
    """Loads gtm_company_registry.json's `companies` map. A MISSING file is
    empty (load_gtm_registry's own contract — most repos never have one).
    A PRESENT-but-unreadable file (bad JSON, I/O error, not an object) now
    PROPAGATES CompanyError rather than being swallowed into an empty dict
    -- major finding: silently treating "corrupt" the same as "empty" made
    a genuine registry failure indistinguishable from "nothing registered
    here", which (a) lost the real diagnosis (resolve_home used to say
    "slug not registered" instead of surfacing the actual unreadable-file
    error) and (b) let a corrupt GTM registry silently drop every GTM-only
    company (e.g. Brightline/Maplewood) out of registered_slugs(),
    `validate --all`, and the identity index with no error at all."""
    registry = load_gtm_registry()
    companies = registry.get("companies")
    return companies if isinstance(companies, dict) else {}


# Minor finding (never-cross-connect-businesses hard boundary, plan §20.9a
# verbatim: "I honestly need you to stop going into the agency repo. That is
# not yours. That's a totally different application. The only thing that
# these two applications ... share is the Claude code runtime."): a
# repo_registry.json entry is registered for OTHER runtime tooling
# (scripts/repo_manifest.py); its presence there never by itself should
# have made ~/Desktop/OtherApp specifically a GTM candidate. `_all_packs()`
# (run on every `register` and `validate --all`) used to stat
# `~/Desktop/OtherApp/.claude/gtm/company.json` for exactly this reason, and
# `harvest_tool_trail.py`'s default transcript globs (built from the SAME
# registered-homes set) globbed and opened Agency session transcripts --
# both forbidden outright by §20.9a, regardless of whether a pack file
# happens to exist there.
#
# Fixed as a NAMED denylist, deliberately, rather than requiring every
# repo_registry.json entry to opt in with a flag: an opt-in-flag design
# would have required retrofitting every one of this module's existing
# test fixtures (14+ files register a test-local company purely via a
# repo_registry.json entry, predating this finding, with no flag) merely
# to keep exercising code paths that have nothing to do with the real
# OtherApp repo -- exactly the "narrow matrix certifies the wrong thing"
# failure mode of solving a real-world single-entry problem by breaking a
# generic, widely-relied-on resolution contract. The one entry this plan
# forbids by NAME (`agency`, root `~/Desktop/OtherApp`) is excluded
# unconditionally, everywhere `_repo_registry_repos()` is used to
# discover/probe/glob GTM candidates; every other repo_registry.json slug
# (including any test's own arbitrary slug) is unaffected. Plan §3.1's "a
# pack's presence, not a registry flag, makes a registered repo a GTM
# company" is otherwise untouched -- this is a narrower, prior exclusion
# of one specific, by-name-forbidden repo, not a general eligibility gate.
_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS = frozenset({"agency"})


def _gtm_eligible_repo_registry_repos() -> dict[str, Any]:
    """`_repo_registry_repos()`, with `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS`
    excluded -- see that constant's own comment for why this exists and why
    an unconditional pass-through of every repo_registry.json entry is the
    bug."""
    repos = _repo_registry_repos()
    return {slug: entry for slug, entry in repos.items() if slug not in _GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS}


def _repo_registry_repos() -> dict[str, Any]:
    """Loads repo_registry.json's `repos` map.

    Major finding #5 (regression fix): a MISSING repo_registry.json is now
    treated as EMPTY, not an error -- matching `_gtm_registry_companies`'s
    own missing-file contract. `load_registry()` alone (used by CSA/Agency,
    which always HAVE a repo_registry.json) still raises CompanyError for
    a missing file; that contract stays correct for THOSE callers. But a
    GTM-only home (Brightline, Maplewood, Opswell) registers exclusively
    in gtm_company_registry.json and may have no repo_registry.json at all
    -- with the old unconditional `load_registry()` call here,
    `resolve_home`/`registered_slugs` for such a slug raised 'registry not
    found' even though the GTM registry genuinely had the entry, silently
    making every GTM-only company unresolvable whenever
    repo_registry.json happened to be absent. A PRESENT-but-corrupt
    repo_registry.json still propagates CompanyError, unchanged -- only
    the missing-file case is now non-fatal, exactly mirroring
    `load_gtm_registry`'s own missing-vs-corrupt distinction."""
    path = registry_path()
    if not path.exists():
        return {}
    registry = load_registry()
    repos = registry.get("repos")
    return repos if isinstance(repos, dict) else {}


def registered_slugs() -> list[str]:
    """Resolution order (coordinator directive): gtm_company_registry.json
    FIRST, then repo_registry.json for slugs not already in the GTM
    registry -- CSA keeps resolving via repo_registry.json, exactly as
    before (minor finding fix: excludes
    `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` -- the OtherApp repo is never a
    GTM candidate no matter what repo_registry.json says; see that
    constant's own comment). A slug present in BOTH
    registries is a duplicate and is EXCLUDED from this list entirely
    (resolve_home raises CompanyError for it instead of silently picking
    one) -- see resolve_home's own duplicate check for why silently
    preferring one registry over the other would be the wrong failure mode
    here.

    Raises CompanyError when either registry is PRESENT but unreadable --
    this function no longer silently treats a corrupt registry as "no
    companies registered" (see _gtm_registry_companies's docstring)."""
    gtm_companies = _gtm_registry_companies()
    repos = _gtm_eligible_repo_registry_repos()
    duplicate_slugs = set(gtm_companies) & set(repos)
    all_slugs = (set(gtm_companies) | set(repos)) - duplicate_slugs
    return sorted(all_slugs)


def resolve_home(slug: str) -> Path:
    """Resolves <slug> to its home directory. Resolution order:
    gtm_company_registry.json first; then repo_registry.json (excludes
    `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` -- minor finding fix, see that
    constant's own comment) for a slug not in the GTM registry. A slug
    present in BOTH registries is INVALID (raises CompanyError) --
    silently preferring one registry over the other would hide a real
    configuration mistake (the same company accidentally registered twice,
    potentially to two DIFFERENT roots). Does NOT check the pack exists —
    see pack_path() / validate_company() for that."""
    gtm_companies = _gtm_registry_companies()
    repos = _gtm_eligible_repo_registry_repos()

    in_gtm = slug in gtm_companies
    in_repo_registry = slug in repos
    if in_gtm and in_repo_registry:
        raise CompanyError(
            f"slug {slug!r} is registered in BOTH gtm_company_registry.json and repo_registry.json "
            "-- this is a configuration error, not a resolvable duplicate"
        )

    if in_gtm:
        entry = gtm_companies[slug]
        if not isinstance(entry, dict) or "root" not in entry:
            raise CompanyError(f"gtm_company_registry.json entry for {slug!r} has no 'root'")
        root = entry["root"]
        if not isinstance(root, str) or not root.strip():
            raise CompanyError(f"gtm_company_registry.json entry for {slug!r} has an empty 'root'")
        return Path(root).expanduser().resolve()

    if in_repo_registry:
        entry = repos[slug]
        if not isinstance(entry, dict) or "root" not in entry:
            raise CompanyError(f"registry entry for {slug!r} has no 'root'")
        root = entry["root"]
        if not isinstance(root, str) or not root.strip():
            raise CompanyError(f"registry entry for {slug!r} has an empty 'root'")
        return Path(root).expanduser().resolve()

    raise CompanyError(f"slug not registered: {slug!r}")


def _entry_root_path(entry: Any, slug: str, registry_name: str) -> Path:
    """Extracts and resolves an entry's `root` value, guarding against a
    non-dict entry (nit fix: `repos[slug].get(...)` raised AttributeError
    -- an uncaught traceback instead of a clean CompanyError -- when a
    registry entry was some other JSON type, e.g. a corrupt/hand-edited
    registry with `{"slug": "not-a-dict"}`) and against a missing/empty
    `root` silently resolving to the current working directory (nit fix:
    `Path("").resolve()` IS the cwd, so a missing root could previously
    compare equal to whatever the caller's cwd happened to be, a false
    "already registered to the same root" match)."""
    if not isinstance(entry, dict):
        raise CompanyError(f"{registry_name} entry for {slug!r} is not an object: {entry!r}")
    root = entry.get("root")
    if not isinstance(root, str) or not root.strip():
        raise CompanyError(f"{registry_name} entry for {slug!r} has no non-empty 'root'")
    return Path(root).expanduser().resolve()


def register_gtm_company(slug: str, root: str) -> Path:
    """#register: atomically writes `slug -> {"root": root}` into
    gtm_company_registry.json. Refuses when:
      - the slug does not match SLUG_RE (`^[a-z][a-z0-9-]{1,31}$`, the same
        shape scripts/repo_manifest.py enforces for every repo_registry.json
        key) -- an unvalidated slug becomes a filesystem path component in
        backup_set/backup_company/the ticket+lease keys, so e.g.
        "../../evil" would otherwise escape .gtm_state/ and ~/Backups/gtm/
        entirely (blocker fix: packs are agent-authored, so this is
        prompt-injection-reachable);
      - the slug is already registered to a DIFFERENT root in either
        registry (gtm_company_registry.json OR repo_registry.json) --
        re-registering the SAME root is idempotent and allowed;
      - <root>/.claude/gtm/company.json is missing or fails
        validate_company (a registry entry for a pack that doesn't even
        validate is worse than useless -- it would make `validate --all`
        report a confusing failure with no way to tell "never checked"
        from "checked and broken").
    Returns the path written to.

    Nit fix: the read-modify-write against gtm_company_registry.json is
    now done under `_gtm_registry_lock_path()`'s exclusive lock, spanning
    from the initial duplicate-slug read through the final write -- two
    concurrent `register`/`unregister` calls could previously each read
    the registry, each mutate their own in-memory copy, and one write
    could silently clobber the other's (lost update), since neither
    step took any lock at all."""
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise CompanyError(f"refusing to register {slug!r}: slug must match {SLUG_RE.pattern!r}")

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise CompanyError(f"refusing to register {slug!r}: root does not exist: {root_path}")

    lock_path = _gtm_registry_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            return _register_gtm_company_locked(slug, root_path)
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def _register_gtm_company_locked(slug: str, root_path: Path) -> Path:
    gtm_companies = _gtm_registry_companies()
    repos = _repo_registry_repos()

    if slug in repos:
        existing_root = _entry_root_path(repos[slug], slug, "repo_registry.json")
        if existing_root != root_path:
            raise CompanyError(
                f"slug {slug!r} is already registered in repo_registry.json with root {existing_root} "
                f"(!= requested {root_path})"
            )
        raise CompanyError(f"slug {slug!r} is already registered in repo_registry.json -- use that registry")

    if slug in gtm_companies:
        existing_root = _entry_root_path(gtm_companies[slug], slug, "gtm_company_registry.json")
        if existing_root != root_path:
            raise CompanyError(
                f"slug {slug!r} is already registered in gtm_company_registry.json with root {existing_root} "
                f"(!= requested {root_path})"
            )
        # Idempotent re-registration of the same root -- fall through to
        # re-validate and re-write (harmless, keeps the pack-validity
        # check live even on a repeat call).

    pack_file = root_path / ".claude" / "gtm" / "company.json"
    if not pack_file.exists():
        raise CompanyError(f"refusing to register {slug!r}: no company pack at {pack_file}")
    try:
        pack_data = json.loads(pack_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompanyError(f"refusing to register {slug!r}: company.json unreadable/invalid JSON: {exc}") from exc
    if not isinstance(pack_data, dict):
        raise CompanyError(f"refusing to register {slug!r}: company.json top level is not an object")

    # Major finding: siblings={} used to skip EVERY cross-pack check
    # (credential_ref reuse across packs, identity_allowlist overlap
    # between two companies) at registration time -- the README promises
    # register "refuses a home whose company.json ... fails
    # validate_company", but only the single-pack half of that check
    # actually ran. Building the real sibling set from every OTHER
    # currently registered, loadable pack (in EITHER registry) makes the
    # cross-pack checks genuinely run here, exactly as they do for
    # `validate --all` -- this is precisely the never-cross-connect-
    # businesses gate the operator's standing rule requires at the moment
    # a second company's identity is first declared, not only later when
    # someone happens to run `validate --all`.
    siblings = _all_packs(exclude_slug=slug)
    # Blocker fix: pass home=root_path explicitly. resolve_home(slug) would
    # raise here (the slug is not registered in any registry yet, since
    # this IS the registration call) and validate_company's own fallback
    # would silently skip the mcp.json secret scan -- exactly the case
    # this parameter exists for. See validate_company's docstring.
    ok, reasons = validate_company(slug, pack_data, siblings=siblings, home=root_path)
    if not ok:
        raise CompanyError(f"refusing to register {slug!r}: pack is INVALID: {'; '.join(reasons)}")

    registry_data = load_gtm_registry()
    companies = registry_data.setdefault("companies", {})
    if not isinstance(companies, dict):
        companies = {}
        registry_data["companies"] = companies
    companies[slug] = {"root": str(root_path)}
    registry_data.setdefault("schema_version", 1)

    target = gtm_registry_path()
    _atomic_write_json(target, registry_data)
    return target


def unregister_gtm_company(slug: str) -> Path:
    """Removes `slug` from gtm_company_registry.json. Refuses (raises
    CompanyError) if the slug isn't registered there at all -- including
    when it's registered only in repo_registry.json (this tool never
    touches that file).

    Nit fix: the read-modify-write is now done under the SAME lock
    `register_gtm_company` uses, for the same lost-update reason."""
    lock_path = _gtm_registry_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            registry_data = load_gtm_registry()
            companies = registry_data.get("companies")
            if not isinstance(companies, dict) or slug not in companies:
                raise CompanyError(f"slug {slug!r} is not registered in gtm_company_registry.json")
            del companies[slug]

            target = gtm_registry_path()
            _atomic_write_json(target, registry_data)
            return target
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def pack_path(slug: str) -> Path:
    return resolve_home(slug) / ".claude" / "gtm" / "company.json"


def load_pack(slug: str) -> dict[str, Any]:
    """Resolves <slug>'s home and loads+parses its company.json. Raises
    CompanyError if the home can't be resolved, the pack file is missing, or
    it isn't valid JSON / isn't an object. This is intentionally distinct
    from schema validation (validate_company): a pack that loads fine can
    still be schema-INVALID."""
    path = pack_path(slug)
    if not path.exists():
        raise CompanyError(f"no company pack at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompanyError(f"company.json unreadable/invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CompanyError("company.json top level is not an object")
    return data


# --------------------------------------------------------------------------
# Secret-shape detection (reused from log_action.py's REDACT_RE, widened —
# plan: "Reuse log_action.py's REDACT_RE plus common key shapes")
# --------------------------------------------------------------------------

REDACT_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*(\S+)",
    re.IGNORECASE,
)

# A key NAME matching this shape, holding a non-empty, non-reference literal
# value, is itself secret-shaped regardless of the value's own format — this
# is what catches an opaque vendor token that doesn't match any of our value
# patterns below (blocker 4). Scoped to firing everywhere in company.json/
# mcp.json (not just inside env/headers) because a secret can be typed under
# an innocuous-looking key at the top level too — the plan's own example
# shows credential_ref as a SAFE non-secret value under a key that doesn't
# match this pattern, so scoping wider than env/headers costs nothing there.
_SECRET_KEY_NAME_RE = re.compile(
    r"(?i)token|secret|password|passwd|credential|api[_-]?key|client[_-]?secret|refresh|authorization|bearer|"
    # #25: WordPress application-password key-naming conventions, plus a
    # general "_pass" / "pass_" fragment so any *_PASS-shaped key name is
    # caught even when it never spells out the full word "password"
    # (e.g. WP_APP_PASS, APP_PASSWORD, application_password already match
    # "password" above, but WP_APP_PASS on its own does not).
    r"app[_-]?password|application[_-]?password|wp[_-]?app[_-]?pass|[_-]pass(?:[_-]|$)|^pass(?:[_-]|$)|"
    # Nit fix: the underscore-boundary rule above misses a camelCase
    # "*Pass"-shaped key name with NO separator at all (appPass, dbPass)
    # -- "pass" is never preceded by a `[_-]` or by the string start in
    # those, so none of the alternatives above match. A camel-boundary
    # alternative catches "Pass" preceded by a lowercase letter (the
    # unambiguous camelCase shape) without widening to a blanket "contains
    # 'pass'" match: this is deliberately CASE-SENSITIVE (an explicit
    # inline case-sensitive group, overriding the leading (?i)), since
    # "passenger"/"bypass" have no capital P there at all.
    #
    # KNOWN GAP (documented, not fixed): an all-LOWERCASE fused name with
    # no camel boundary (e.g. "mypass") is indistinguishable BY SHAPE ALONE
    # from "bypass"/"passenger" -- both are `[a-z]+pass[a-z]*`, so no
    # regex boundary rule can separate "my" + "pass" from "by" + "pass"
    # without a dictionary of real English words, which this scan
    # deliberately doesn't carry. Left unflagged rather than widened to a
    # blanket substring match that would false-positive on every
    # "passenger"/"bypass"-shaped key name in the pack.
    #
    # Nit fix: the trailing boundary `(?:[A-Z_-]|$)` used to sit OUTSIDE
    # the `(?-i:...)` case-sensitive group, so the leading `(?i)` flag
    # (still in effect out there) made `[A-Z]` match a LOWERCASE letter
    # too -- "isPassenger" matched via "sPass" + the next lowercase "e"
    # (wrongly accepted as "[A-Z]" under (?i)), and "userPassport"
    # matched the same way via "rPass" + "p". The comment above already
    # says this alternative is "deliberately CASE-SENSITIVE", which the
    # boundary being outside the group silently defeated. Moving the
    # boundary INSIDE the case-sensitive group makes the whole match --
    # both the "[a-z]Pass" prefix and its boundary -- genuinely
    # case-sensitive, so "isPassenger"/"userPassport" (no real camelCase
    # boundary right after "Pass") no longer match.
    r"(?-i:[a-z]Pass(?:[A-Z_-]|$))",
)

# Values that are clearly NOT a real secret even if the key name matches:
# an env-var reference (${VAR} / $VAR), a GSM reference (gsm:...), the
# literal none/empty prose ("token: none"), or a bare 40-hex git sha (a git
# sha is exactly 40 lowercase hex chars with nothing else in the string --
# distinguishing it from a 40+ char UPPER/mixed-case or non-hex-shaped blob,
# which stays flagged).
_ENV_REF_RE = re.compile(r"^\$\{[^}]+\}$|^\$[A-Za-z_][A-Za-z0-9_]*$")
_GSM_REF_RE = re.compile(r"^gsm:", re.IGNORECASE)
# Nit fix: narrowed from a case-insensitive, mixed-case-server pattern to
# EXACTLY the pack schema's own credential_ref browser-shape
# (_CREDENTIAL_REF_SHAPE_RE's `browser:[a-z0-9-]+` alternative) --
# `_is_safe_literal` is the GENERIC safe-value check (used everywhere a
# value is scanned for secret-shapedness, mcp.json included, not just
# `$.accounts[i].credential_ref`), so widening this exemption case-
# insensitively/beyond the schema's own lowercase-only server-name shape
# would let a value like "Browser:MyServer" or "browser:MY_SERVER" pass as
# safe here even though it would fail validate_company's own
# credential_ref shape check -- an inconsistency between what this exempts
# and what the schema actually allows.
_BROWSER_REF_RE = re.compile(r"^browser:[a-z0-9-]+$")
_NONE_LITERAL_RE = re.compile(r"^(none|n/a|null|not[_ -]?set)$", re.IGNORECASE)
_BARE_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# B1/#23: the pack schema's own credential_ref value SPACE is exactly
# `gsm:<name>` | `browser:<server>` | `none` (§3.3) -- never anything else.
# Recognizing this shape lets `$.accounts[i].credential_ref` be exempted
# from the generic secret scan (see find_secret_shapes), rather than
# trying to make the generic scan permissive enough to cover it. #23
# narrows this from a case-insensitive, dot-permitting pattern to the
# reviewer's exact spec: lowercase-only server names, no '.' in the gsm
# secret name segment.
_CREDENTIAL_REF_SHAPE_RE = re.compile(r"^(gsm:[A-Za-z0-9_-]+|browser:[a-z0-9-]+|none)$")

# #23: the credential_ref exemption is scoped to this EXACT JSON path
# pattern within company.json only -- never any key literally named
# "credential_ref" anywhere in the structure (which would also exempt one
# accidentally nested inside mcp.json's env block, or inside some other
# unrelated dict in company.json). $.accounts[<any index>].credential_ref.
_CREDENTIAL_REF_EXACT_PATH_RE = re.compile(r"^\$\.accounts\[\d+\]\.credential_ref$")


def _is_safe_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if _ENV_REF_RE.match(stripped):
        return True
    if _GSM_REF_RE.match(stripped):
        return True
    if _BROWSER_REF_RE.match(stripped):
        return True
    if _NONE_LITERAL_RE.match(stripped):
        return True
    if _BARE_GIT_SHA_RE.match(stripped):
        return True
    return False


# B1: a Google Sheet id is a real, non-secret identifier — roughly 25-60
# alphanumeric/`-`/`_` characters. It is exempted from the secret scan
# ONLY at lead_sink.ref when lead_sink.kind == "google_sheet" (never as a
# blanket value-shape exemption, since a 25-60-char alphanumeric string
# could otherwise coincide with something that IS meant to be secret in a
# different field).
_GOOGLE_SHEET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{25,60}$")


# Common credential-shaped literal value patterns, independent of any
# surrounding "key: value" text or key name — these catch a bare secret
# sitting as a dict value with an innocuous key name.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^AIza[0-9A-Za-z_\-]{30,}$"),  # Google API key
    re.compile(r"^sk-[0-9A-Za-z]{16,}$"),  # OpenAI/Stripe-shaped secret key
    re.compile(r"^sk_live_[0-9A-Za-z]{8,}$"),  # Stripe live secret key
    re.compile(r"^sk_test_[0-9A-Za-z]{8,}$"),  # Stripe test secret key
    re.compile(r"^rk_live_[0-9A-Za-z]{8,}$"),  # Stripe restricted live key
    re.compile(r"^GOCSPX-[0-9A-Za-z_\-]{8,}$"),  # Google OAuth client secret
    re.compile(r"^gh[po]_[0-9A-Za-z]{20,}$"),  # GitHub personal access / OAuth token
    re.compile(r"^github_pat_[0-9A-Za-z_]{20,}$"),  # GitHub fine-grained PAT
    re.compile(r"^1//0[0-9A-Za-z_\-]{10,}$"),  # Google OAuth refresh token
    re.compile(r"^xox[bp]-[0-9A-Za-z\-]{10,}$"),  # Slack bot/user token
    re.compile(r"^ya29\.[0-9A-Za-z_\-]{20,}$"),  # Google OAuth access token
    re.compile(r"^EAA[0-9A-Za-z]{20,}$"),  # Meta access token
    re.compile(r"^[0-9A-Za-z+/]{40,}={0,2}$"),  # 40+ char base64 blob
    re.compile(r"^[0-9a-fA-F]{40,}$"),  # 40+ char hex blob (bare 40-hex git sha excluded above)
)


def _looks_like_secret_value(value: str) -> bool:
    if not value or len(value) < 20:
        return False
    if _is_safe_literal(value):
        return False
    # A bare 40-char lowercase hex string is excluded as a git sha ABOVE
    # this check's own callers (find_secret_shapes checks _is_safe_literal
    # first), but the 40+-hex pattern here still must not double-flag it --
    # _is_safe_literal already returned True for it, so this function never
    # even reaches the pattern loop for that case.
    return any(p.match(value) for p in _SECRET_VALUE_PATTERNS)


def find_secret_shapes(obj: Any, path: str = "$", key_name: str | None = None, is_company_json: bool = False) -> list[str]:
    """Recursively scans a JSON-like structure for secret-shaped content:
    (a) any string matching REDACT_RE (a 'key: value'-shaped secret
    mention within the string's own text, e.g. "token: none" is exempted by
    _is_safe_literal but "token: abc123xyz789" still matches REDACT_RE
    directly since REDACT_RE operates on the string's CONTENT, not on
    key_name), (b) any leaf string value whose shape alone (independent of
    its key name) matches a known credential pattern, (c) any NON-EMPTY,
    non-safe-literal value sitting under a key whose NAME matches
    _SECRET_KEY_NAME_RE, anywhere in the structure (blocker 4 — this is
    what catches a real vendor token typed under a plausible key name that
    doesn't itself match any of the value-shape patterns in (b)).
    Returns a list of JSON-pointer-ish paths where something was found
    (empty = clean).

    #23: the two exemptions below (credential_ref, lead_sink.ref) are
    scoped to an EXACT JSON PATH within company.json only -- never a bare
    key-name/kind match anywhere in the structure. `is_company_json` gates
    both exemptions entirely.

    nit: the default is `False` (the SAFE default) -- a caller that omits
    this flag gets NO exemption at all, which is what any future scan of
    "some other file" should get by default without needing to remember to
    pass it. The ONE call site that scans an actual company.json pack
    (inside validate_company) passes `is_company_json=True` explicitly to
    opt in; callers scanning mcp.json (or anything else) either pass
    `is_company_json=False` explicitly (for clarity) or simply rely on the
    default -- either way, a `credential_ref` key inside mcp.json's `env`
    block, or a `kind: "google_sheet"` dict anywhere outside company.json's
    own top-level `lead_sink`, gets NO exemption at all."""
    hits: list[str] = []
    if isinstance(obj, str):
        # #23: credential_ref's exemption now requires an EXACT path match
        # ($.accounts[<i>].credential_ref) AND is_company_json -- a key
        # literally named "credential_ref" sitting anywhere else (a
        # different top-level structure in company.json, or inside
        # mcp.json's env block) gets no exemption at all.
        if is_company_json and _CREDENTIAL_REF_EXACT_PATH_RE.match(path):
            return hits
        # Every "key: value"-shaped match's own captured VALUE (group 2) is
        # checked against _is_safe_literal, not the whole string -- this is
        # what keeps "token: none" clean while "token: sk-abc123xyz789..."
        # still flags: the former's captured value is the safe literal
        # "none", the latter's is not.
        redact_matches = list(REDACT_RE.finditer(obj))
        if redact_matches:
            # This string already carries its own "key: value" shape
            # in-text (e.g. "token: none" or "token: sk-abc123..."); that
            # match's own captured value is the authoritative signal --
            # branch (c) below is for a DIFFERENT shape (the *containing*
            # key's name looks secret-ish and the ENTIRE value is the
            # secret, e.g. {"token": "sk-abc123..."}), and re-applying it
            # to a string that already parsed as "key: value" prose would
            # re-flag "token: none" via the containing key name alone.
            if any(not _is_safe_literal(m.group(2)) for m in redact_matches):
                hits.append(path)
        elif _looks_like_secret_value(obj):
            hits.append(path)
        elif (
            key_name is not None
            and _SECRET_KEY_NAME_RE.search(key_name)
            and obj.strip()
            and not _is_safe_literal(obj)
        ):
            hits.append(path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hits.extend(find_secret_shapes(item, f"{path}[{i}]", key_name=key_name, is_company_json=is_company_json))
    elif isinstance(obj, dict):
        # #23: lead_sink.ref is exempted from the secret scan ONLY at the
        # EXACT path $.lead_sink.ref, when THIS dict's own path is exactly
        # "$.lead_sink" and its kind == "google_sheet" -- never any other
        # dict anywhere in the structure that happens to also carry a
        # `kind: "google_sheet"` key (e.g. a nested object elsewhere named
        # something else but shaped the same way).
        is_the_lead_sink_object = is_company_json and path == "$.lead_sink" and obj.get("kind") == "google_sheet"
        for k, v in obj.items():
            if (
                is_the_lead_sink_object
                and k == "ref"
                and isinstance(v, str)
                and _GOOGLE_SHEET_ID_RE.match(v)
            ):
                continue
            hits.extend(find_secret_shapes(v, f"{path}.{k}", key_name=k, is_company_json=is_company_json))
    return hits


# --------------------------------------------------------------------------
# Schema keys (mirrors company_schema.json's top-level shape for the
# "unknown key" / "missing required key" checks)
# --------------------------------------------------------------------------

REQUIRED_TOP_KEYS = (
    "schema_version",
    "slug",
    "legal_name",
    "display_names",
    "business_model",
    "brands",
    "persona_file",
    "timezone",
    "goals",
    "scope",
    "accounts",
    "identity_allowlist",
    "claims_policy",
    "ai_content_policy",
    "autonomy",
    "spend",
    "budget",
    "operator_input",
    "inbox",
    "lead_sink",
    "cadence",
    "paths",
)

OPTIONAL_TOP_KEYS = (
    "quiet_hours",
    "shared_identifiers",
    "class_o_batches",
    "mirror_dir",
    "mirror_basename",
    "mirror_title",
    "regulated",
    "co_managing_systems",
    "host_systems",
    "legacy_workdirs",
)

ALL_TOP_KEYS = set(REQUIRED_TOP_KEYS) | set(OPTIONAL_TOP_KEYS)

VALID_BUSINESS_MODELS = {"local_service", "b2b_saas", "ecommerce", "other"}
VALID_AI_MODES = {"disclose_never_strip", "strip_before_publish", "forbid"}
VALID_AUTONOMY_LEVELS = {"shadow", "autonomous"}
VALID_CLAIM_RULES = {"no_new", "forbid_any"}
VALID_INBOX_KINDS = {"github_label", "local_jsonl"}
VALID_MISSION_RECORDS = {"tracked", "ignored"}
VALID_REGULATED = {"hipaa"}
VALID_CO_MANAGING_MODES = {"read_only"}
REQUIRED_PATHS_KEYS = (
    "missions_dir",
    "mission_records",
    "activity_log_dir",
    "scoreboard",
    "snapshots_dir",
    "metrics",
    "feature_inventory_dir",
    "plans_dir",
    "data_dir",
)
REQUIRED_BUDGET_DISPATCH_CAPS = (
    "inbox",
    "daily",
    "weekly",
    "monthly",
    "mission",
    "monthly_load",
)


def _all_packs(exclude_slug: str | None = None) -> dict[str, dict[str, Any]]:
    """Loads every registered pack (slug -> parsed company.json), skipping
    any slug with no pack file or an unparseable one (those are the target
    pack's own INVALID reasons when checked directly; for cross-pack checks
    a sibling that can't be loaded contributes nothing, which is safe: it
    can never falsely clear a real collision)."""
    out: dict[str, dict[str, Any]] = {}
    for slug in registered_slugs():
        if slug == exclude_slug:
            continue
        try:
            out[slug] = load_pack(slug)
        except CompanyError:
            continue
    return out


def _other_businesses() -> dict[str, Any]:
    path = gtm_state_dir() / "other_businesses.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _identity_values(pack: dict[str, Any]) -> set[str]:
    """Every identity value declared by a pack: identity_allowlist.* lists,
    brands[].domains, brands[].phones, brands[].nap.* (plan §3.3). This is
    the BROAD set, used for cross-pack collision detection (a NAP or phone
    number colliding with another company IS a real thing to catch there)
    — never use this for free-text page-content matching (see
    _identity_account_ids below, which is the narrow set major 15
    requires for that)."""
    values: set[str] = set()
    allowlist = pack.get("identity_allowlist")
    if isinstance(allowlist, dict):
        for v in allowlist.values():
            if isinstance(v, list):
                values.update(x for x in v if isinstance(x, str) and x)
    brands = pack.get("brands")
    if isinstance(brands, list):
        for brand in brands:
            if not isinstance(brand, dict):
                continue
            for key in ("domains", "phones"):
                v = brand.get(key)
                if isinstance(v, list):
                    values.update(x for x in v if isinstance(x, str) and x)
            nap = brand.get("nap")
            if isinstance(nap, dict):
                values.update(x for x in nap.values() if isinstance(x, str) and x)
    return values


# identity_allowlist keys that are ACCOUNT-ID-shaped (a platform's own
# opaque numeric/alphanumeric object id) as opposed to HOST-shaped
# (domains/listing_urls, matched via a URL's hostname, never via a
# free-text substring search) or NAP-shaped (brands[].nap.*/phones, never
# eligible for identity-based capture triggering at all — major 15).
_ACCOUNT_ID_ALLOWLIST_KEYS = (
    "facebook_page_ids",
    "instagram_ids",
    "gbp_location_ids",
    "ads_customer_ids",
    "meta_ad_account_ids",
    "ga4_property_ids",
    "gtm_container_ids",
)


def _identity_account_ids(pack: dict[str, Any]) -> set[str]:
    """The NARROW subset of a pack's identity values that are genuine
    platform account/object ids (major 15) — never a brand name, address,
    or phone number. This is what a text-substring match against page
    content is allowed to trigger on; domains/listing_urls are host-shaped
    (matched via URL hostname only, in company_for_url) and are
    deliberately excluded here too, since a domain appearing as bare text
    on an unrelated page is exactly the kind of coincidental match this
    function must not produce (a real domain visit is caught by
    company_for_url instead, which parses an actual URL hostname)."""
    values: set[str] = set()
    allowlist = pack.get("identity_allowlist")
    if isinstance(allowlist, dict):
        for key in _ACCOUNT_ID_ALLOWLIST_KEYS:
            v = allowlist.get(key)
            if isinstance(v, list):
                values.update(x for x in v if isinstance(x, str) and x)
    return values


def _credential_refs(pack: dict[str, Any]) -> set[str]:
    """The set of this pack's `gsm:<name>` credential references -- the ONLY
    credential_ref shape that is actually a shared secret. A `browser:<server>`
    value (per §3.3/§3.4) is a per-session Playwright server NAME, not a
    credential: every company's browser accounts share the same handful of
    server names (e.g. `browser:playwright-gtm`) by design, with per-company
    isolation coming from the profile/lease (§3.4), never from the server
    name being unique. Blocker fix: this used to leave out only the literal
    'none', so every pack sharing `browser:playwright-gtm` (which is all of
    them, per the Brightline fixture's 7 browser accounts) collided in the
    cross-pack reuse check below -- refusing every second company's
    registration outright. `none` is still excluded (it is a real "no
    credential" marker, never a value that can collide)."""
    refs: set[str] = set()
    accounts = pack.get("accounts")
    if isinstance(accounts, list):
        for acct in accounts:
            if not isinstance(acct, dict):
                continue
            ref = acct.get("credential_ref")
            if isinstance(ref, str) and ref and _GSM_REF_RE.match(ref):
                refs.add(ref)
    return refs


def _shared_identifier_records(pack: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Returns (value, with_slug, relationship, ruling_ref) tuples from
    shared_identifiers[]."""
    out: list[tuple[str, str, str, str]] = []
    shared = pack.get("shared_identifiers")
    if isinstance(shared, list):
        for item in shared:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            with_slug = item.get("with")
            relationship = item.get("relationship")
            ruling_ref = item.get("ruling_ref")
            if all(isinstance(x, str) for x in (value, with_slug, relationship, ruling_ref)):
                out.append((value, with_slug, relationship, ruling_ref))  # type: ignore[arg-type]
    return out


def _pack_system_set(pack: dict[str, Any]) -> set[str]:
    """B2: the valid `system` value space for THIS pack — its own
    `scope.channels_in_scope` union the runtime's fixed extras (the same
    union activity_log.py's SYSTEMS computes, per company, in
    resolve_paths()). Deferred import of activity_log to avoid a circular
    top-level import (activity_log imports company at module load time;
    company can only reach back into activity_log lazily, inside a
    function body, once both modules are already loaded). Resolves its own
    directory explicitly rather than relying on ambient sys.path state, so
    this works even when company.py is imported directly as a script by
    something that never added tools/gtm/ to sys.path itself."""
    this_dir = str(Path(__file__).resolve().parent)
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)
    import activity_log as activity_log_mod  # noqa: PLC0415 - deliberate deferred import, see docstring

    scope = pack.get("scope") if isinstance(pack.get("scope"), dict) else {}
    channels_in_scope = scope.get("channels_in_scope") if isinstance(scope.get("channels_in_scope"), list) else []
    return set(activity_log_mod._ORIGINAL_SYSTEMS) | set(activity_log_mod._ADDED_SYSTEMS) | {
        c for c in channels_in_scope if isinstance(c, str)
    }


def validate_company(
    slug: str,
    pack: dict[str, Any],
    siblings: dict[str, dict[str, Any]] | None = None,
    *,
    home: Path | None = None,
) -> tuple[bool, list[str]]:
    """Validates one pack's content. `siblings` = every OTHER registered
    pack's parsed content (slug -> dict), for the cross-pack checks
    (credential_ref reuse, identity collisions). When siblings is None, this
    function loads them itself via _all_packs (excluding `slug`) — tests
    that want to control the sibling set precisely should pass it
    explicitly.

    `home`, when given, is used in place of `resolve_home(slug)` for the
    mcp.json secret scan below. This exists for the moment a company is
    first registering: `slug` is not in any registry yet, so
    `resolve_home(slug)` would raise and silently skip the mcp.json scan
    (the register-time blocker this parameter closes). Callers that already
    know the home on disk (register_gtm_company) must pass it explicitly
    rather than relying on registry resolution.

    Returns (ok, reasons). ok is True iff reasons is empty."""
    reasons: list[str] = []

    if not isinstance(pack, dict):
        return False, ["company.json top level is not an object"]

    # --- unknown / missing keys -------------------------------------
    unknown = sorted(set(pack.keys()) - ALL_TOP_KEYS)
    for key in unknown:
        reasons.append(f"unknown key: {key!r}")
    missing = [k for k in REQUIRED_TOP_KEYS if k not in pack]
    for key in missing:
        reasons.append(f"missing required key: {key!r}")

    # --- slug must equal the registry key it was resolved by ---------
    if "slug" in pack and pack.get("slug") != slug:
        reasons.append(f"pack.slug {pack.get('slug')!r} does not match the registry key {slug!r} it was resolved by")

    # --- slug shape (blocker fix): both the registry key this pack was
    # resolved by AND pack["slug"] itself must match SLUG_RE, the same
    # shape scripts/repo_manifest.py enforces for a repo_registry.json key.
    # A pack that arrives via `validate --all` is keyed by whatever is
    # already in a registry (register_gtm_company enforces SLUG_RE on
    # write, but repo_registry.json entries come from a different writer,
    # and a hand-edited/corrupt registry could carry an unshaped key
    # either way) -- checking both here means neither registry can hand
    # validate_company a slug that later becomes an unvalidated filesystem
    # path component in backup_set/backup_company/the ticket+lease keys.
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        reasons.append(f"registry key {slug!r} does not match {SLUG_RE.pattern!r}")
    if "slug" in pack:
        pack_slug = pack.get("slug")
        if not isinstance(pack_slug, str) or not SLUG_RE.match(pack_slug):
            reasons.append(f"pack.slug {pack_slug!r} does not match {SLUG_RE.pattern!r}")

    # --- scalar enum checks (only when the key IS present, to avoid
    # duplicating the "missing" reason above with a confusing second one) --
    if "business_model" in pack and pack.get("business_model") not in VALID_BUSINESS_MODELS:
        reasons.append(f"business_model must be one of {sorted(VALID_BUSINESS_MODELS)}, got {pack.get('business_model')!r}")

    if "ai_content_policy" in pack:
        aip = pack.get("ai_content_policy")
        if not isinstance(aip, dict):
            reasons.append("ai_content_policy must be an object")
        else:
            mode = aip.get("mode")
            if mode not in VALID_AI_MODES:
                reasons.append(f"ai_content_policy.mode must be one of {sorted(VALID_AI_MODES)}, got {mode!r}")
            if mode == "disclose_never_strip" and not aip.get("disclosure_caption_line"):
                reasons.append("ai_content_policy.disclosure_caption_line is required when mode == disclose_never_strip")

    if "autonomy" in pack:
        autonomy = pack.get("autonomy")
        if not isinstance(autonomy, dict):
            reasons.append("autonomy must be an object")
        else:
            level = autonomy.get("level")
            if level not in VALID_AUTONOMY_LEVELS:
                reasons.append(f"autonomy.level must be one of {sorted(VALID_AUTONOMY_LEVELS)}, got {level!r}")
            approvals = autonomy.get("standing_approvals")
            if isinstance(approvals, list):
                for i, approval in enumerate(approvals):
                    if not isinstance(approval, dict):
                        reasons.append(f"autonomy.standing_approvals[{i}] must be an object")
                        continue
                    approval_label = approval.get("id", f"[{i}]")
                    for req_field in ("id", "verbatim", "ts"):
                        val = approval.get(req_field)
                        if not isinstance(val, str) or not val.strip():
                            reasons.append(
                                f"autonomy.standing_approvals[{approval_label!r}].{req_field} is required and must be a non-empty string"
                            )
                    rows = approval.get("rows")
                    if not isinstance(rows, list) or not rows:
                        reasons.append(
                            f"autonomy.standing_approvals[{approval_label!r}].rows must be a non-empty list of strings"
                        )
                        continue
                    for row_id in rows:
                        # Every bypass shape rejected explicitly: a bare "*"
                        # string, "gbp.*", "*.publish", and a value with
                        # surrounding whitespace (" *", "gbp.hours_edit ")
                        # that could otherwise slip past an exact "== '*'"
                        # check. A wildcard is ANY '*' character ANYWHERE in
                        # the row id, not just the bare string "*" — that is
                        # the bypass this rewrite closes.
                        if not isinstance(row_id, str):
                            reasons.append(
                                f"autonomy.standing_approvals[{approval_label!r}].rows contains a non-string row id: {row_id!r}"
                            )
                            continue
                        if "*" in row_id:
                            reasons.append(
                                f"autonomy.standing_approvals[{approval_label!r}].rows contains a wildcard-shaped row id {row_id!r} (never allowed)"
                            )
                        elif row_id != row_id.strip():
                            reasons.append(
                                f"autonomy.standing_approvals[{approval_label!r}].rows row id {row_id!r} has leading/trailing whitespace (never allowed)"
                            )
                        elif not row_id:
                            reasons.append(
                                f"autonomy.standing_approvals[{approval_label!r}].rows contains an empty row id"
                            )

    if "inbox" in pack and pack.get("inbox") not in VALID_INBOX_KINDS:
        reasons.append(f"inbox must be one of {sorted(VALID_INBOX_KINDS)}, got {pack.get('inbox')!r}")

    if "claims_policy" in pack:
        cp = pack.get("claims_policy")
        if not isinstance(cp, dict):
            reasons.append("claims_policy must be an object")
        else:
            terms = cp.get("terms")
            if isinstance(terms, list):
                for i, term in enumerate(terms):
                    if not isinstance(term, dict):
                        reasons.append(f"claims_policy.terms[{i}] must be an object")
                        continue
                    rule = term.get("rule")
                    if rule not in VALID_CLAIM_RULES:
                        reasons.append(
                            f"claims_policy.terms[{i}].rule must be one of {sorted(VALID_CLAIM_RULES)}, got {rule!r}"
                        )

    if "regulated" in pack:
        regulated = pack.get("regulated")
        if not isinstance(regulated, list):
            reasons.append("regulated must be a list")
        else:
            for value in regulated:
                if value not in VALID_REGULATED:
                    reasons.append(f"regulated value must be one of {sorted(VALID_REGULATED)}, got {value!r}")

    if "legacy_workdirs" in pack:
        legacy = pack.get("legacy_workdirs")
        if not isinstance(legacy, list):
            reasons.append("legacy_workdirs must be a list")
        else:
            for i, entry in enumerate(legacy):
                if not isinstance(entry, str) or not (entry.startswith("/") or entry.startswith("~/")):
                    reasons.append(f"legacy_workdirs[{i}] must be an absolute or ~/ path string, got {entry!r}")
                elif ".." in Path(entry).parts:
                    reasons.append(f"legacy_workdirs[{i}] must not contain '..', got {entry!r}")

    if "co_managing_systems" in pack:
        co_managing = pack.get("co_managing_systems")
        if not isinstance(co_managing, list):
            reasons.append("co_managing_systems must be a list")
        else:
            for i, entry in enumerate(co_managing):
                if not isinstance(entry, dict):
                    reasons.append(f"co_managing_systems[{i}] must be an object")
                    continue
                for req_field in ("system", "identity", "interface", "ruling_ref"):
                    val = entry.get(req_field)
                    if not isinstance(val, str) or not val.strip():
                        reasons.append(f"co_managing_systems[{i}].{req_field} is required and must be a non-empty string")
                mode = entry.get("mode")
                if mode not in VALID_CO_MANAGING_MODES:
                    reasons.append(
                        f"co_managing_systems[{i}].mode must be one of {sorted(VALID_CO_MANAGING_MODES)}, got {mode!r}"
                    )

    if "host_systems" in pack:
        host_systems = pack.get("host_systems")
        if not isinstance(host_systems, dict):
            reasons.append("host_systems must be an object ({host_glob: system})")
        else:
            valid_systems = _pack_system_set(pack)
            for host, system in host_systems.items():
                if not isinstance(host, str) or not host.strip():
                    reasons.append(f"host_systems key {host!r} must be a non-empty string")
                else:
                    # Nit fix: reject a key whose HOST part carries a
                    # scheme or ':' -- e.g. "https://facebook.com/x" would
                    # otherwise silently partition (via harvest_tool_trail's
                    # own key.partition("/")) into host "https:" and path
                    # prefix "/facebook.com/x", which never matches any
                    # real URL's hostname and so the rule silently never
                    # fires at all. A bare host is never allowed to
                    # contain '://' or a bare ':' (a port-shaped host is
                    # also rejected here -- DEFAULT_HOST_SYSTEMS/
                    # _host_matches never expect one either).
                    host_part, sep, path_part = host.partition("/")
                    if "://" in host_part or ":" in host_part:
                        reasons.append(
                            f"host_systems key {host!r} has a host part {host_part!r} that looks like it "
                            "carries a URL scheme or port -- host_systems keys are bare host/domain "
                            "strings (optionally '<host>/<path-prefix>'), never a full URL"
                        )
                    elif not host_part:
                        reasons.append(
                            f"host_systems key {host!r} has an empty host part -- "
                            "'/<path>' with no host before the '/' can never match any real URL"
                        )
                    elif sep and not path_part:
                        reasons.append(
                            f"host_systems key {host!r} has a trailing '/' with an empty path prefix -- "
                            "harvest_tool_trail matches this key's path-prefix segment literally, so an "
                            "empty path prefix after the '/' can never match any real URL and the rule "
                            "silently never fires"
                        )
                if not isinstance(system, str) or not system.strip():
                    reasons.append(f"host_systems[{host!r}] value must be a non-empty string")
                elif system not in valid_systems:
                    reasons.append(
                        f"host_systems[{host!r}] = {system!r} is not in this pack's system set "
                        f"(channels_in_scope ∪ runtime extras): {sorted(valid_systems)}"
                    )

    if "accounts" in pack:
        accounts = pack.get("accounts")
        if not isinstance(accounts, list):
            reasons.append("accounts must be a list")
        else:
            for i, acct in enumerate(accounts):
                if not isinstance(acct, dict):
                    reasons.append(f"accounts[{i}] must be an object")
                    continue
                # B1: credential_ref's shape is validated HERE, explicitly
                # -- gsm:<name> | browser:<server> | none only -- since
                # find_secret_shapes() now exempts this key from the generic
                # secret scan ONLY at its exact path
                # ($.accounts[i].credential_ref, is_company_json=True --
                # see _CREDENTIAL_REF_EXACT_PATH_RE), never everywhere the
                # key name appears (its value space is a known, non-secret
                # enum-like shape at that one path, not free text to
                # pattern-match -- but a same-named key elsewhere, e.g.
                # inside mcp.json's env block, gets no exemption at all).
                ref = acct.get("credential_ref")
                if not isinstance(ref, str) or not _CREDENTIAL_REF_SHAPE_RE.match(ref):
                    reasons.append(
                        f"accounts[{i}].credential_ref must match gsm:<name> | browser:<server> | none, got {ref!r}"
                    )

    if "paths" in pack:
        paths = pack.get("paths")
        if not isinstance(paths, dict):
            reasons.append("paths must be an object")
        else:
            for key in REQUIRED_PATHS_KEYS:
                if key not in paths:
                    reasons.append(f"paths.{key} is required")
            mission_records = paths.get("mission_records")
            if "mission_records" in paths and mission_records not in VALID_MISSION_RECORDS:
                reasons.append(
                    f"paths.mission_records must be one of {sorted(VALID_MISSION_RECORDS)}, got {mission_records!r}"
                )
            # Every paths.* value must be home-RELATIVE: no leading '/', no
            # leading '~', and no '..' component anywhere (a pack pointing
            # outside its own home is exactly the shape that let a pack
            # write/ignore arbitrary filesystem paths -- e.g. data_dir:
            # "/etc" or "../x" escaping the home entirely). mission_records
            # is the one non-path string value in this dict and is skipped.
            for key, value in paths.items():
                if key == "mission_records":
                    continue
                if not isinstance(value, str):
                    continue
                if value.startswith("/") or value.startswith("~"):
                    reasons.append(f"paths.{key} must be a relative path (no leading '/' or '~'), got {value!r}")
                elif any(part == ".." for part in Path(value).parts):
                    reasons.append(f"paths.{key} must not contain '..' (must stay inside the company home), got {value!r}")

    if "budget" in pack:
        budget = pack.get("budget")
        if not isinstance(budget, dict):
            reasons.append("budget must be an object")
        else:
            caps = budget.get("dispatch_caps_per_run")
            if not isinstance(caps, dict):
                reasons.append("budget.dispatch_caps_per_run must be an object")
            else:
                for key in REQUIRED_BUDGET_DISPATCH_CAPS:
                    if key not in caps:
                        reasons.append(f"budget.dispatch_caps_per_run.{key} is required")

    # --- secret-shaped content in company.json -----------------------
    # nit: is_company_json defaults to False (safe default) -- this is the
    # ONE call site scanning an actual company.json pack, so it passes
    # is_company_json=True explicitly to enable the credential_ref/
    # lead_sink.ref exact-path exemptions for THIS scan only.
    for hit in find_secret_shapes(pack, is_company_json=True):
        reasons.append(f"secret-shaped value found at {hit}")

    # --- secret-shaped content in <home>/.claude/gtm/mcp.json ---------
    if home is None:
        try:
            home = resolve_home(slug)
        except CompanyError:
            home = None
    if home is not None:
        mcp_path = home / ".claude" / "gtm" / "mcp.json"
        if mcp_path.exists():
            try:
                mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reasons.append(f"mcp.json unreadable/invalid JSON: {exc}")
            else:
                # #23: mcp.json is scanned with is_company_json=False --
                # neither the credential_ref nor the lead_sink.ref
                # exemption applies here, since those are exact-path
                # exemptions scoped to company.json's own top-level shape
                # (a credential_ref-named key inside mcp.json's env block
                # is a completely different, unvalidated shape and must
                # never get a free pass).
                for hit in find_secret_shapes(mcp_data, is_company_json=False):
                    reasons.append(f"secret-shaped value found in mcp.json at {hit}")

    # --- cross-pack checks (need sibling packs) -----------------------
    if siblings is None:
        siblings = _all_packs(exclude_slug=slug)

    my_refs = _credential_refs(pack)
    for other_slug, other_pack in siblings.items():
        other_refs = _credential_refs(other_pack)
        for shared_ref in my_refs & other_refs:
            reasons.append(f"credential_ref {shared_ref!r} is also used by pack {other_slug!r}")

    my_shared = {(v, w): (rel, ruling) for v, w, rel, ruling in _shared_identifier_records(pack)}
    my_identity_values = _identity_values(pack)
    other_businesses = _other_businesses()
    other_biz_values: set[str] = set()
    for v in other_businesses.values():
        if isinstance(v, list):
            other_biz_values.update(x for x in v if isinstance(x, str))
        elif isinstance(v, str):
            other_biz_values.add(v)

    for value in my_identity_values:
        if value in other_biz_values:
            declared = my_shared.get((value, "other_businesses"))
            if declared is None:
                reasons.append(
                    f"identity value {value!r} appears in other_businesses.json and is not declared in shared_identifiers"
                )
        for other_slug, other_pack in siblings.items():
            if value in _identity_values(other_pack):
                mine = my_shared.get((value, other_slug))
                theirs = {
                    (v2, w2): (rel2, ruling2)
                    for v2, w2, rel2, ruling2 in _shared_identifier_records(other_pack)
                }.get((value, slug))
                if mine is None or theirs is None or mine != theirs:
                    reasons.append(
                        f"identity value {value!r} is shared with pack {other_slug!r} "
                        "but not declared identically in both packs' shared_identifiers "
                        "(same value, relationship, and ruling_ref required in both)"
                    )

    return (len(reasons) == 0, reasons)


# --------------------------------------------------------------------------
# .gitignore generation (plan §3.2)
# --------------------------------------------------------------------------


def generate_gitignore(pack: dict[str, Any]) -> str:
    """Generates the .gitignore block for a pack's ignored-class paths, from
    the pack's OWN `paths.*` values (never a hardcoded literal like
    ".claude/gtm/state/" for a CONFIGURABLE path — a pack may configure any
    layout, e.g. the Brightline migration's `tracking/activity_log`).

    B3 rewrite (2026-09-27) — three real defects fixed, each verified with
    real `git check-ignore`:
    1. The DEFAULT layout's fixed `.claude/gtm/state/` and
       `.claude/gtm/data/` subtrees are runtime-owned and ALWAYS ignored
       outright (plain `dir/` — no `.md` negation at all): `state/reports/
       *.md` and `state/cycles/*.md` are cycle-generated reports, not
       tracked docs, and were wrongly kept trackable by a blanket `.md`
       negation under state/. The `.md`-negation form is reserved for
       `snapshots_dir` ONLY when it is NOT itself under `.claude/gtm/
       state/` (a pack may point snapshots_dir outside state/, e.g.
       Brightline's `tracking/snapshots`, where its own governing *.md
       reports legitimately need to stay tracked).
    2. `.claude/gtm/data/` (the fixed runtime location) stays ignored even
       when a pack's `paths.data_dir` points elsewhere entirely — the two
       are independent: data_dir is additionally ignored at ITS OWN
       location, never as a substitute for the fixed one.
    3. activity_log_dir ignores ONLY its known machine-written files by
       EXACT name (ACTIVITY_LOG.jsonl, TOOL_TRAIL.jsonl, ACTIVITY_LOG.md,
       .activity_log.lock) — never a `*.md` glob, which wrongly swallowed
       a genuine `README.md` sitting in that directory (the Brightline
       migration keeps one there). `feature_inventory/` is still never
       ignored even when nested under activity_log_dir.

    NEVER ignored: paths.metrics (§3.2: tracked), feature_inventory_dir,
    plans_dir, missions_dir when mission_records == "tracked", and any
    other file in activity_log_dir not in the exact machine-written list
    above (e.g. README.md).
    """
    paths = pack.get("paths") if isinstance(pack.get("paths"), dict) else {}

    def _rel(value: Any) -> str | None:
        if not value:
            return None
        return str(value).rstrip("/")

    activity_log_dir = _rel(paths.get("activity_log_dir"))
    feature_inventory_dir = _rel(paths.get("feature_inventory_dir"))
    data_dir = _rel(paths.get("data_dir"))
    build_dir = _rel(paths.get("build_dir"))
    snapshots_dir = _rel(paths.get("snapshots_dir"))
    missions_dir = _rel(paths.get("missions_dir"))
    mission_records = paths.get("mission_records")

    _STATE_DIR = ".claude/gtm/state"
    _DATA_DIR = ".claude/gtm/data"

    lines: list[str] = [
        "# Generated by tools/gtm/company.py gitignore — do not hand-edit.",
        "",
        # B3 fix 1: plain, unconditional ignore -- no .md negation. This
        # runtime-owned subtree holds only generated state (actions,
        # cycles, reports, activity-log renders when the default layout is
        # used) -- never hand-authored docs a pack needs tracked.
        f"{_STATE_DIR}/",
        # B3 fix 2: the fixed runtime data location is ALWAYS ignored,
        # independent of wherever paths.data_dir itself points.
        f"{_DATA_DIR}/",
        ".playwright-mcp/",
    ]

    if activity_log_dir:
        lines.append("")
        # B3 fix 3: exact machine-written filenames only -- never a `*.md`
        # glob, which would also swallow a genuine README.md.
        lines.append(f"{activity_log_dir}/ACTIVITY_LOG.jsonl")
        lines.append(f"{activity_log_dir}/TOOL_TRAIL.jsonl")
        lines.append(f"{activity_log_dir}/ACTIVITY_LOG.md")
        lines.append(f"{activity_log_dir}/.activity_log.lock")
        # #24: the trail's sidecar membership index (minor 17/#20) and its
        # atomic-write staging file -- machine-written, never tracked,
        # exactly like the trail file it shadows.
        #
        # Regression fix: `_write_sidecar_with_header` (activity_log.py)
        # writes its staging file via `tempfile.mkstemp(prefix=sidecar.name
        # + ".", suffix=".tmp", ...)`, so the REAL temp file on disk is
        # named `TOOL_TRAIL.jsonl.ids.<8 random chars>.tmp` (e.g.
        # `TOOL_TRAIL.jsonl.ids.bloxwshh.tmp`), never the fixed literal
        # `TOOL_TRAIL.jsonl.ids.tmp` this line used to emit alone -- that
        # fixed name never matches any real mkstemp output, so a temp file
        # left behind by a crash (containing the sidecar's tool_use_id
        # contents, not itself sensitive, but still machine-written churn
        # that was never meant to be tracked) was trackable. The glob
        # `TOOL_TRAIL.jsonl.ids.*.tmp` matches the real shape; the fixed
        # name is kept alongside it in case a future write path ever uses
        # it literally.
        lines.append(f"{activity_log_dir}/TOOL_TRAIL.jsonl.ids")
        lines.append(f"{activity_log_dir}/TOOL_TRAIL.jsonl.ids.tmp")
        lines.append(f"{activity_log_dir}/TOOL_TRAIL.jsonl.ids.*.tmp")
        # feature_inventory_dir is never ignored, even when nested beneath
        # activity_log_dir -- with fix 3's move to exact filenames this is
        # now automatic (a CSV never matches any of the four exact names
        # above), but the explicit negation is kept for defense in depth
        # against a future exact-name list that might include a glob again.
        if feature_inventory_dir:
            try:
                nested = Path(feature_inventory_dir).is_relative_to(Path(activity_log_dir))
            except (ValueError, TypeError):
                nested = False
            if nested:
                lines.append(f"!{feature_inventory_dir}/")
                lines.append(f"!{feature_inventory_dir}/**")

    # data_dir is ignored at its OWN location too, in addition to (never
    # instead of) the fixed .claude/gtm/data/ above -- the two are
    # independent when a pack points data_dir elsewhere (e.g. a top-level
    # "data/" in the Brightline migration layout).
    if data_dir and data_dir != _DATA_DIR:
        lines.append("")
        lines.append(f"{data_dir}/**")

    if build_dir:
        lines.append("")
        lines.append(f"{build_dir}/**")

    if snapshots_dir:
        lines.append("")
        try:
            snapshots_under_state = Path(snapshots_dir).is_relative_to(Path(_STATE_DIR))
        except (ValueError, TypeError):
            snapshots_under_state = False
        if snapshots_under_state:
            # Already covered by the plain, unconditional state/ ignore
            # above (fix 1) -- no separate .md-negation block for a
            # snapshots_dir living inside the runtime-owned state subtree,
            # since that subtree holds no tracked docs by definition.
            pass
        else:
            # A snapshots_dir OUTSIDE state/ (e.g. Brightline's
            # tracking/snapshots) legitimately carries its own governing
            # *.md reports that must stay tracked -- keep the negation form.
            lines.append(f"{snapshots_dir}/**")
            lines.append(f"!{snapshots_dir}/**/")
            lines.append(f"!{snapshots_dir}/**/*.md")

    if missions_dir and mission_records == "ignored":
        lines.append("")
        lines.append(f"{missions_dir}/**")
        lines.append(f"!{missions_dir}/**/")
        lines.append(f"!{missions_dir}/**/*.md")

    scoreboard = _rel(paths.get("scoreboard"))
    if scoreboard and not scoreboard.endswith(".md"):
        lines.append("")
        lines.append(scoreboard)

    # paths.metrics is NEVER ignored (§3.2: metrics.json/METRICS.md are
    # tracked config) -- deliberately absent from this generator. A test
    # asserts this by name (test_gitignore_never_ignores_metrics).

    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# backup-set (plan §3.2)
# --------------------------------------------------------------------------


def backup_set(slug: str, pack: dict[str, Any]) -> list[Path]:
    """Every ignored-class path plus .claude/gtm/state/, plus this
    company's own entries under the RUNTIME's cross-company
    ~/.claude/.gtm_state/ tree — the backup target set for
    tools/gtm/backup_state.py. Returns absolute paths.

    §3.2's ignored-class list includes mission records when
    `paths.mission_records == "ignored"` (major 11) — those are backed up
    here even though they are NOT under `.claude/gtm/state/`.

    Runtime cross-company state (major 11): tickets and lease locks are
    named BY SLUG under known, separable sibling directories
    (`~/.claude/.gtm_state/tickets/<slug>/`,
    `~/.claude/.gtm_state/leases/<slug>.lock` — plan §6.7/§3.4), so those
    two are included individually, by name. Approval/cancel records
    (`~/.claude/.gtm_state/approval_nonces.jsonl`, `~/.claude/.gtm_state/
    cancels/`) are NOT yet separable per-company on disk (they are not
    slug-keyed the same way) — until that changes, this function does NOT
    include them; a company's backup restore is missing that piece,
    documented here and in the module docstring/README rather than
    silently assumed covered."""
    home = resolve_home(slug)
    paths = pack.get("paths") if isinstance(pack.get("paths"), dict) else {}
    out: list[Path] = [home / ".claude" / "gtm" / "state"]

    data_dir = paths.get("data_dir")
    if data_dir:
        out.append(home / data_dir)

    build_dir = paths.get("build_dir")
    if build_dir:
        out.append(home / build_dir)

    scoreboard = paths.get("scoreboard")
    if scoreboard:
        out.append(home / scoreboard)

    snapshots_dir = paths.get("snapshots_dir")
    if snapshots_dir:
        out.append(home / snapshots_dir)

    activity_log_dir = paths.get("activity_log_dir")
    if activity_log_dir:
        out.append(home / activity_log_dir)

    missions_dir = paths.get("missions_dir")
    if missions_dir and paths.get("mission_records") == "ignored":
        out.append(home / missions_dir)

    # Cross-company runtime state for THIS company only, by name.
    state_root = gtm_state_dir()
    out.append(state_root / "tickets" / slug)
    out.append(state_root / "leases" / f"{slug}.lock")

    # dedupe while preserving order
    seen: set[str] = set()
    deduped: list[Path] = []
    for p in out:
        key = str(p)
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


# --------------------------------------------------------------------------
# index (plan §7.6)
# --------------------------------------------------------------------------


def build_identity_index() -> dict[str, list[str]]:
    """company -> every identity value it declares (identity_allowlist.*,
    brands[].domains/phones/nap), from every registered pack plus
    other_businesses.json (recorded under key "other_businesses")."""
    index: dict[str, list[str]] = {}
    for slug in registered_slugs():
        try:
            pack = load_pack(slug)
        except CompanyError:
            continue
        index[slug] = sorted(_identity_values(pack))
    other = _other_businesses()
    other_values: set[str] = set()
    for v in other.values():
        if isinstance(v, list):
            other_values.update(x for x in v if isinstance(x, str))
        elif isinstance(v, str):
            other_values.add(v)
    if other_values:
        index["other_businesses"] = sorted(other_values)
    return index


def build_account_id_index() -> dict[str, list[str]]:
    """company -> only its genuine platform account/object ids (major 15
    — NEVER a brand name, address, or phone number, and never a bare
    domain/listing_url either). This is the index
    harvest_tool_trail.py's text-substring matching path must read,
    instead of the broad identity_index.json (which still includes NAP
    values for the cross-pack collision checks in validate_company)."""
    index: dict[str, list[str]] = {}
    for slug in registered_slugs():
        try:
            pack = load_pack(slug)
        except CompanyError:
            continue
        ids = sorted(_identity_account_ids(pack))
        if ids:
            index[slug] = ids
    return index


def write_identity_index() -> Path:
    state_dir = gtm_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / "identity_index.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(build_identity_index(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, target)

    account_id_target = state_dir / "account_id_index.json"
    account_id_tmp = account_id_target.with_suffix(".json.tmp")
    account_id_tmp.write_text(json.dumps(build_account_id_index(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(account_id_tmp, account_id_target)

    return target


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def cmd_resolve(args: argparse.Namespace) -> int:
    try:
        home = resolve_home(args.slug)
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    path = pack_path(args.slug)
    if not path.exists():
        print(f"error: no company pack at {path}", file=sys.stderr)
        return 1
    print(str(home))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    exit_code = 0

    if args.all:
        # A present-but-unreadable registry now RAISES (see
        # _gtm_registry_companies/_repo_registry_repos) rather than being
        # silently treated as empty -- `validate --all` must report that
        # failure explicitly (non-zero exit, reason naming the file) and
        # stop, rather than letting an uncaught CompanyError crash the CLI
        # or, worse, silently proceeding as if nothing were registered.
        try:
            duplicate_slugs = sorted(set(_gtm_registry_companies()) & set(_repo_registry_repos()))
        except CompanyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        for dup in duplicate_slugs:
            print(f"INVALID {dup}: registered in BOTH gtm_company_registry.json and repo_registry.json")
            exit_code = 1
        try:
            slugs = registered_slugs()
        except CompanyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    else:
        slugs = [args.slug]

    if not slugs and not (args.all and exit_code):
        print("no registered slugs found", file=sys.stderr)
        return 1

    all_packs: dict[str, dict[str, Any]] = {}
    for slug in slugs:
        try:
            all_packs[slug] = load_pack(slug)
        except CompanyError:
            pass

    for slug in slugs:
        try:
            pack = load_pack(slug)
        except CompanyError as exc:
            print(f"INVALID {slug}: {exc}")
            exit_code = 1
            continue
        try:
            siblings = {s: p for s, p in _all_packs(exclude_slug=slug).items()}
        except CompanyError as exc:
            # A single-slug `validate <slug>` still needs to name THIS
            # slug's own INVALID reason even when a sibling lookup fails
            # because some OTHER registry is corrupt -- rather than
            # crashing the whole command uncaught, report it as one more
            # reason this slug's validation could not complete cleanly.
            print(f"INVALID {slug}: cross-pack sibling lookup failed: {exc}")
            exit_code = 1
            continue
        ok, reasons = validate_company(slug, pack, siblings=siblings)
        if ok:
            print(f"OK {slug}")
        else:
            for reason in reasons:
                print(f"INVALID {slug}: {reason}")
            exit_code = 1
    return exit_code


def cmd_index(args: argparse.Namespace) -> int:
    # Nit fix: a slug registered in BOTH gtm_company_registry.json and
    # repo_registry.json is silently EXCLUDED from registered_slugs()
    # (resolve_home's own duplicate-detection contract -- see its
    # docstring), which build_identity_index/build_account_id_index both
    # call. `validate --all` already surfaces this loudly as an INVALID
    # line; `index` used to just drop the duplicate slug out of both
    # written index files with a clean exit 0 and no warning at all --
    # exactly the "wrote a wrong-but-plausible-looking file" shape that
    # should never exit clean.
    try:
        duplicate_slugs = sorted(set(_gtm_registry_companies()) & set(_repo_registry_repos()))
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        target = write_identity_index()
    except CompanyError as exc:
        # A corrupt registry must fail loud here too -- this is exactly
        # the identity index the major finding calls out: a silently-
        # swallowed corrupt GTM registry used to drop every GTM-only
        # company (Brightline/Maplewood) out of this index with no error
        # at all, which then mis-attributes or drops their harvested
        # activity downstream with nothing to explain why.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    exit_code = 0
    for dup in duplicate_slugs:
        print(
            f"warning: {dup!r} is registered in BOTH gtm_company_registry.json and "
            "repo_registry.json -- excluded from the written index entirely",
            file=sys.stderr,
        )
        exit_code = 1
    print(f"wrote {target}")
    return exit_code


def cmd_gitignore(args: argparse.Namespace) -> int:
    try:
        pack = load_pack(args.slug)
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(generate_gitignore(pack), end="")
    return 0


def cmd_backup_set(args: argparse.Namespace) -> int:
    try:
        pack = load_pack(args.slug)
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for p in backup_set(args.slug, pack):
        print(str(p))
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    try:
        target = register_gtm_company(args.slug, args.root)
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    # Nit fix #9: prints the RESOLVED absolute path that was actually
    # written to the registry (the same resolution register_gtm_company
    # itself performs internally via Path(root).expanduser().resolve()),
    # never args.root as typed -- a relative or ~-prefixed --root would
    # otherwise print a path that doesn't match what's actually in
    # gtm_company_registry.json.
    resolved_root = Path(args.root).expanduser().resolve()
    print(f"registered {args.slug} -> {resolved_root} (in {target})")
    return 0


def cmd_unregister(args: argparse.Namespace) -> int:
    try:
        target = unregister_gtm_company(args.slug)
    except CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"unregistered {args.slug} (from {target})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="company.py", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    resolve_p = sub.add_parser("resolve", help="print the home path for a company slug")
    resolve_p.add_argument("slug")
    resolve_p.set_defaults(func=cmd_resolve)

    validate_p = sub.add_parser("validate", help="validate one or all company packs")
    validate_group = validate_p.add_mutually_exclusive_group(required=True)
    validate_group.add_argument("slug", nargs="?")
    validate_group.add_argument("--all", action="store_true")
    validate_p.set_defaults(func=cmd_validate)

    index_p = sub.add_parser("index", help="write the cross-company identity index")
    index_p.set_defaults(func=cmd_index)

    gitignore_p = sub.add_parser("gitignore", help="print the generated .gitignore block for a pack")
    gitignore_p.add_argument("slug")
    gitignore_p.set_defaults(func=cmd_gitignore)

    backup_p = sub.add_parser("backup-set", help="print every path backup_state.py should archive")
    backup_p.add_argument("slug")
    backup_p.set_defaults(func=cmd_backup_set)

    register_p = sub.add_parser(
        "register",
        help="register a company home in gtm_company_registry.json (for a home with no GitHub remote)",
    )
    register_p.add_argument("slug")
    register_p.add_argument("--root", required=True, help="the company home's absolute or ~-relative path")
    register_p.set_defaults(func=cmd_register)

    unregister_p = sub.add_parser("unregister", help="remove a company from gtm_company_registry.json")
    unregister_p.add_argument("slug")
    unregister_p.set_defaults(func=cmd_unregister)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
