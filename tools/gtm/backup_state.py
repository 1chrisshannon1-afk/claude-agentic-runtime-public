#!/usr/bin/env python3
"""backup_state.py — tars a GTM company's ignored-class state (plan §3.2)
to `~/Backups/gtm/<slug>/<YYYY-MM-DD>.tgz`, keeping the newest 8.

The backup set is exactly `company.py backup-set <slug>`'s output — every
ignored-class path plus `.claude/gtm/state/`.

The destination root is overridable via `--dest-root` (or env
`GTM_BACKUP_DEST_ROOT`) so tests never write to the real `~/Backups`.

Subcommands (flag-based, no subparsers — this tool has exactly two modes)
---------------------------------------------------------------------------
    --company <slug>                     back up that company now
    --restore <tgz> --to <dir>           extract a backup archive to <dir>
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import company as company_mod  # noqa: E402

KEEP_NEWEST = 8


def dest_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("GTM_BACKUP_DEST_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / "Backups" / "gtm"


_RUNTIME_STATE_ARCNAME_PREFIX = "_gtm_state"


def backup_company(slug: str, dest_root_path: Path, today: date | None = None) -> Path:
    """Minor 18: a backup-set path that lives under the COMPANY HOME is
    archived at its home-relative path, as before. A backup-set path that
    lives OUTSIDE the home (the runtime's cross-company
    ~/.claude/.gtm_state/ entries — tickets/<slug>/, leases/<slug>.lock —
    added by company.backup_set's major-11 fix) is archived under an
    explicit `_gtm_state/<slug>/<relative-path-under-.gtm_state>` prefix
    instead of a bare `p.name` fallback. The old bare-name fallback lost
    all path structure (e.g. leases/brightline.lock and
    tickets/brightline/ would both have archived as indistinguishable
    bare names) and, more importantly, gave restore_archive no way to
    tell "this belongs in the home" from "this belongs in the runtime
    .gtm_state tree" -- the prefix is what restore_archive's
    --runtime-state-to gate (below) keys off of."""
    pack = company_mod.load_pack(slug)
    paths = company_mod.backup_set(slug, pack)
    day = (today or date.today()).isoformat()
    out_dir = dest_root_path / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    tgz_path = out_dir / f"{day}.tgz"

    home = company_mod.resolve_home(slug)
    gtm_state_root = company_mod.gtm_state_dir()
    with tarfile.open(tgz_path, "w:gz") as tar:
        for p in paths:
            if not p.exists():
                continue
            try:
                arcname = str(p.relative_to(home))
            except ValueError:
                try:
                    rel_to_state = p.relative_to(gtm_state_root)
                except ValueError:
                    # Neither under the home nor under the runtime
                    # .gtm_state tree -- an unexpected shape for a
                    # backup-set entry; archive it under the runtime
                    # prefix by absolute-path-derived name rather than
                    # silently losing structure via a bare p.name.
                    rel_to_state = Path(*p.parts[1:])
                arcname = str(Path(_RUNTIME_STATE_ARCNAME_PREFIX) / slug / rel_to_state)
            tar.add(p, arcname=arcname)

    _rotate(out_dir)
    return tgz_path


def _rotate(out_dir: Path) -> None:
    archives = sorted(out_dir.glob("*.tgz"))
    excess = len(archives) - KEEP_NEWEST
    if excess > 0:
        for old in archives[:excess]:
            old.unlink()


class UnsafeArchiveMember(Exception):
    """Raised when ANY member of a restore archive fails the safety check
    (blocker 10). Restore is all-or-nothing: this is raised BEFORE any
    member is extracted, never mid-extraction, so a crafted archive with
    one bad member and 99 good ones never leaves a partial, half-trusted
    restore on disk."""


def _validate_member(member: tarfile.TarInfo, to_dir_resolved: Path) -> None:
    """Validates one archive member against every known escape vector:
    absolute path, '..' component, a symlink/hardlink target that resolves
    outside to_dir (checked both by the link target text and, for a
    symlink whose target is itself inside to_dir but a SIBLING-prefix
    directory, by the resolved path prefix check below using an os.sep
    boundary rather than a bare string prefix), and any device/special
    file (char/block device, FIFO) which a normal backup archive never
    legitimately contains. Raises UnsafeArchiveMember on any violation;
    returns None on a clean member."""
    name = member.name
    if name.startswith("/") or name.startswith("~"):
        raise UnsafeArchiveMember(f"member has an absolute/home-relative path: {name!r}")
    if any(part == ".." for part in Path(name).parts):
        raise UnsafeArchiveMember(f"member path contains '..': {name!r}")

    member_path = (to_dir_resolved / name).resolve()
    # A bare string .startswith() prefix check (the original defect) is
    # fooled by a SIBLING directory that merely shares to_dir's path as a
    # string prefix -- e.g. to_dir="/tmp/restore" vs a crafted member
    # resolving to "/tmp/restore_evil/x" (that string DOES start with
    # "/tmp/restore"). is_relative_to() checks path COMPONENTS, so
    # "/tmp/restore_evil" is correctly judged NOT relative to "/tmp/restore".
    if not member_path.is_relative_to(to_dir_resolved):
        raise UnsafeArchiveMember(f"member resolves outside the restore target: {name!r} -> {member_path}")

    if member.issym() or member.islnk():
        link_target = member.linkname
        if link_target:
            if os.path.isabs(link_target):
                resolved_target = Path(link_target).resolve()
            else:
                resolved_target = (to_dir_resolved / name).parent.joinpath(link_target).resolve()
            if not resolved_target.is_relative_to(to_dir_resolved):
                raise UnsafeArchiveMember(
                    f"member is a symlink/hardlink pointing outside the restore target: {name!r} -> {link_target!r}"
                )

    if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
        raise UnsafeArchiveMember(f"member is a device/special file (never legitimate in a backup archive): {name!r}")


class RuntimeStateRestoreRefused(Exception):
    """Raised when an archive contains runtime-state members (the
    `_gtm_state/<slug>/...` prefix — minor 18) but the caller did not pass
    `--runtime-state-to <dir>`. These members are NEVER extracted into
    `to_dir` (the company home) — restoring a ticket/lease file into a
    home root would silently create nonsense paths there and is exactly
    the shape minor 18 exists to prevent. Also raised (nit) when EVERY
    runtime-state member's slug segment fails to match the effective
    slug — see _strip_runtime_state_prefix's docstring for why silently
    leaving them un-stripped and nested was the wrong failure mode."""


def _is_runtime_state_member(name: str) -> bool:
    return name == _RUNTIME_STATE_ARCNAME_PREFIX or name.startswith(_RUNTIME_STATE_ARCNAME_PREFIX + "/")


def _strip_runtime_state_prefix(name: str, slug: str) -> str:
    """#22: strips the `_gtm_state/<slug>/` prefix from a runtime-state
    member's archive name, so `--runtime-state-to ~/.claude/.gtm_state`
    restores each file to its ORIGINAL path (e.g. `tickets/<slug>/
    ticket_1.json`, `leases/<slug>.lock`) rather than nested under an
    extra `_gtm_state/<slug>/` layer that never existed on disk before the
    backup. Only strips the prefix for THIS slug -- a member for a
    different slug (shouldn't normally appear in one company's own
    archive, but defensively handled) is left with its slug segment
    intact rather than silently stripped wrong. Nit fix: the CALLER
    (restore_archive) now checks whether an explicit --company slug
    matches NONE of the archive's runtime-state members and refuses up
    front rather than silently letting them all land nested under
    `<runtime-state-to>/_gtm_state/<archive-slug>/...` with no error."""
    own_prefix = f"{_RUNTIME_STATE_ARCNAME_PREFIX}/{slug}/"
    if name.startswith(own_prefix):
        return name[len(own_prefix):]
    return name


def _runtime_member_slug(name: str) -> str | None:
    """The slug segment of a runtime-state member's archive name
    (`_gtm_state/<slug>/...`), or None if the name doesn't have one (a bare
    `_gtm_state` with no further path component)."""
    parts = name.split("/", 2)
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return None


def restore_archive(tgz_path: Path, to_dir: Path, runtime_state_to: Path | None = None, slug: str | None = None) -> None:
    """Extracts `tgz_path` into `to_dir`. Validates EVERY member before
    extracting ANY of them (blocker 10) — a crafted tar cannot get partial
    trust: absolute paths, '..' traversal, symlinks/hardlinks resolving
    outside to_dir (including the sibling-prefix-directory shape, e.g. a
    to_dir of "restore/" vs a crafted "restore_evil/" that a bare string
    prefix check would wrongly accept), and device/special files are all
    rejected by raising UnsafeArchiveMember.

    Minor 18: members archived under the `_gtm_state/<slug>/...` prefix
    (the runtime's cross-company ~/.claude/.gtm_state/ entries) are NEVER
    extracted into `to_dir` (the company home) — they are extracted into
    `runtime_state_to` instead, ONLY when that argument is explicitly
    given. If the archive contains any such member and `runtime_state_to`
    is None, this raises RuntimeStateRestoreRefused rather than silently
    dropping them OR silently placing them in the home root.

    #22: runtime-state members have their `_gtm_state/<slug>/` prefix
    STRIPPED before extraction (member.name is rewritten in place), so
    `--runtime-state-to ~/.claude/.gtm_state` restores files to their
    ORIGINAL paths (tickets/<slug>/..., leases/<slug>.lock), not nested
    under an extra `_gtm_state/<slug>/` layer. `slug` defaults to the
    archive's own directory-name convention when not given explicitly
    (every runtime-state member in one company's own backup shares the
    same slug segment, so it is auto-detected from the first such member
    when `slug` is omitted). Validation runs AFTER the rename, against
    the path that will actually be extracted -- validating the
    pre-rename name would miss a traversal introduced (or hidden) by the
    rename itself."""
    to_dir.mkdir(parents=True, exist_ok=True)
    to_dir_resolved = to_dir.resolve()
    runtime_state_resolved = runtime_state_to.resolve() if runtime_state_to is not None else None
    if runtime_state_resolved is not None:
        runtime_state_resolved.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tgz_path, "r:gz") as tar:
        members = tar.getmembers()
        home_members: list[tarfile.TarInfo] = []
        runtime_members: list[tarfile.TarInfo] = []
        for member in members:
            if _is_runtime_state_member(member.name):
                runtime_members.append(member)
            else:
                home_members.append(member)

        if runtime_members and runtime_state_resolved is None:
            raise RuntimeStateRestoreRefused(
                f"archive contains {len(runtime_members)} runtime-state member(s) under "
                f"'{_RUNTIME_STATE_ARCNAME_PREFIX}/' but --runtime-state-to was not given; "
                "refusing to restore them into the home directory"
            )

        # #22: auto-detect the slug from the archive itself when not given
        # explicitly -- every runtime-state member in a single company's
        # own backup shares the same `_gtm_state/<slug>/` prefix.
        effective_slug = slug
        if effective_slug is None and runtime_members:
            first_name = runtime_members[0].name
            parts = first_name.split("/", 2)
            if len(parts) >= 2:
                effective_slug = parts[1]

        # Nit fix (#22), WIDENED by a later finding: an explicit --company
        # slug that matches NONE of the archive's actual runtime-state
        # members used to silently leave every one of them un-stripped,
        # landing nested under `<runtime-state-to>/_gtm_state/<archive-slug>/...`
        # with no error at all -- refuse instead, since this is exactly the
        # shape of "the caller asked to restore the wrong company's runtime
        # state into this archive" and deserves a loud failure, not a
        # silently wrong extraction path.
        #
        # The original check only refused when effective_slug matched NONE
        # of the member slugs -- so a MIXED-slug archive (most members
        # belong to effective_slug, but at least one belongs to some OTHER
        # slug) passed the check silently: the matching members were
        # correctly stripped, and the non-matching ones were extracted
        # UN-STRIPPED, nested under `_gtm_state/<other-slug>/...`, with no
        # error at all -- the exact same wrong-company-data shape the
        # original fix was meant to close, just for a partial rather than
        # total mismatch. Refuse whenever ANY runtime-state member's slug
        # differs from effective_slug, not only when every one does.
        if effective_slug is not None and runtime_members:
            member_slugs = {_runtime_member_slug(m.name) for m in runtime_members}
            member_slugs.discard(None)
            other_slugs = member_slugs - {effective_slug}
            if other_slugs:
                # Nit fix #10 (README wording, plus the message itself was
                # inaccurate): this fires for an AUTO-DETECTED slug too, not
                # only an explicit --company (see #22's comment above:
                # effective_slug can come from either source) -- the error
                # message now says which case actually applies, instead of
                # always naming --company even when the caller never passed
                # one.
                slug_source = "--company" if slug is not None else "the slug auto-detected from the archive"
                raise RuntimeStateRestoreRefused(
                    f"{slug_source} {effective_slug!r} does not match every runtime-state member's "
                    f"slug in this archive (other slug(s) present: {sorted(other_slugs)!r}); refusing "
                    "to restore a mixed-slug archive -- some members would land un-stripped under the "
                    "wrong slug"
                )

        if effective_slug is not None:
            for member in runtime_members:
                member.name = _strip_runtime_state_prefix(member.name, effective_slug)

        for member in runtime_members:
            # Nit fix: a hardlink inside a runtime-state member is refused
            # outright rather than attempting to rewrite its linkname
            # alongside member.name. tarfile hardlinks are archive-root-
            # relative (unlike a symlink's target, which is relative to the
            # member's OWN directory), so a hardlink's linkname would need
            # the SAME `_gtm_state/<slug>/` prefix stripped for it to still
            # resolve post-rename -- and no runtime-state backup content
            # (tickets/leases, both always regular files) ever legitimately
            # contains one, so refusing is strictly safer than attempting a
            # rewrite of a shape that should never occur here.
            if member.islnk():
                raise UnsafeArchiveMember(
                    f"runtime-state member is a hardlink (never legitimate in this backup class): "
                    f"{member.name!r} -> {member.linkname!r}"
                )

        for member in home_members:
            _validate_member(member, to_dir_resolved)
        for member in runtime_members:
            # Validated AFTER the rename above -- against the path that
            # will actually be extracted, not the original archive path.
            # This matters specifically for a symlink member: its
            # relative linkname resolves against the member's OWN
            # location, which differs before vs after stripping the
            # prefix (see test_validation_runs_against_the_post_rename_
            # path_not_the_original for the concrete escape this closes).
            _validate_member(member, runtime_state_resolved)  # type: ignore[arg-type]

        # Explicit filter="data" (Python 3.12+) opts into the safer
        # extraction semantics now rather than waiting for the 3.14 default
        # change; on older Pythons without the `filter` kwarg support this
        # falls back to the unfiltered call, which _validate_member's
        # allowlist above already made path-traversal-safe.
        def _extract(target_dir: Path, target_members: list[tarfile.TarInfo]) -> None:
            if not target_members:
                return
            try:
                tar.extractall(target_dir, members=target_members, filter="data")
            except TypeError:
                tar.extractall(target_dir, members=target_members)

        _extract(to_dir, home_members)
        if runtime_state_resolved is not None:
            _extract(runtime_state_resolved, runtime_members)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backup_state.py", description=__doc__)
    p.add_argument("--company", default=None, help="company slug to back up")
    p.add_argument("--restore", default=None, help="path to a .tgz archive to restore")
    p.add_argument("--to", default=None, help="directory to restore into (required with --restore)")
    p.add_argument(
        "--runtime-state-to",
        default=None,
        help=(
            "directory to restore runtime .gtm_state entries into (minor 18) -- required "
            "if the archive contains any '_gtm_state/<slug>/...' member; these are NEVER "
            "restored into --to (the company home)"
        ),
    )
    p.add_argument("--dest-root", default=None, help="override the backup destination root (default ~/Backups/gtm)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.restore:
        if not args.to:
            print("error: --restore requires --to <dir>", file=sys.stderr)
            return 2
        tgz_path = Path(args.restore).expanduser().resolve()
        if not tgz_path.exists():
            print(f"error: archive not found: {tgz_path}", file=sys.stderr)
            return 1
        runtime_state_to = Path(args.runtime_state_to).expanduser().resolve() if args.runtime_state_to else None
        try:
            restore_archive(
                tgz_path, Path(args.to).expanduser().resolve(),
                runtime_state_to=runtime_state_to, slug=args.company,
            )
        except UnsafeArchiveMember as exc:
            print(f"error: refusing to restore unsafe archive: {exc}", file=sys.stderr)
            return 1
        except RuntimeStateRestoreRefused as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"restored {tgz_path} -> {args.to}" + (f" (runtime state -> {args.runtime_state_to})" if runtime_state_to else ""))
        return 0

    if not args.company:
        print("error: --company <slug> or --restore <tgz> --to <dir> is required", file=sys.stderr)
        return 2

    try:
        tgz_path = backup_company(args.company, dest_root(args.dest_root))
    except company_mod.CompanyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"backed up {args.company} -> {tgz_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
