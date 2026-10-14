#!/usr/bin/env bash
# install_codex_config.sh — copy tools/codex/{config.toml,AGENTS.md,
# review-instructions.md,review_schema.json} into $HOME/.codex/.
#
# Plan: plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md
# §5 (WS4) §4.2. Read that section before changing this script.
#
# Idempotent: re-running with no local drift is a no-op (exit 0, nothing
# written). Never touches an auth file (auth.json / any file whose name
# matches *auth*, *token*, *credential* is explicitly skipped even if such a
# file somehow existed under tools/codex/ — defense in depth; today none does).
#
# Drift detection: after each successful install of a file, this script
# records that file's sha256 into $HOME/.codex/.install_manifest.json. On the
# next run, if the file ALREADY on disk at $HOME/.codex/<name> does not match
# the last hash THIS SCRIPT installed (i.e. something else changed it since —
# a Codex upgrade rewriting config.toml, or a hand edit), the script REFUSES
# to overwrite it and reports the mismatch, unless --force is given. A file
# that does not exist yet, or that exactly matches what this script last
# installed, is written/overwritten freely (that's just re-syncing tools/
# forward, not clobbering someone else's change).
#
# --dry-run prints what would happen (install / skip-unchanged / refuse-drift
# / would-force-overwrite) without writing anything, including the manifest.
#
# Usage:
#   install_codex_config.sh [--dry-run] [--force] [--codex-home DIR]
#
# --codex-home DIR overrides $HOME/.codex — used by tests to point this
# script at a throwaway directory instead of the operator's real ~/.codex.
# Never pass this to install into the real ~/.codex from an automated test.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$CLAUDE_DIR/tools/codex"

DRY_RUN=0
FORCE=0
CODEX_HOME="${HOME:-}/.codex"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --codex-home)
      [ $# -ge 2 ] || { echo "install_codex_config: --codex-home requires a value" >&2; exit 2; }
      CODEX_HOME="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *)
      echo "install_codex_config: unknown argument: $1" >&2
      exit 2 ;;
  esac
done

MANIFEST="$CODEX_HOME/.install_manifest.json"

# Files this script installs. Never includes anything auth/credential-shaped
# even by name match -- defense in depth (rule: "never touches an auth
# file"). If tools/codex/ ever grows a file matching this pattern, refuse
# outright rather than silently install it.
FILES=(config.toml AGENTS.md review-instructions.md review_schema.json)

_is_forbidden_name() {
  # Case-insensitive match against auth/token/credential-shaped filenames.
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    *auth*|*token*|*credential*|*secret*) return 0 ;;
    *) return 1 ;;
  esac
}

_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

# Minimal JSON manifest reader/writer (no jq dependency assumed). One line
# per file: "<name>":"<sha256>". Written as a flat, sorted, single-object
# JSON file so it stays diffable and trivially parseable.
_manifest_get() {
  # $1 = filename key. Prints its recorded sha256, or empty if absent/no manifest.
  [ -f "$MANIFEST" ] || return 0
  python3 - "$MANIFEST" "$1" <<'PY'
import json, sys
path, key = sys.argv[1], sys.argv[2]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    sys.exit(0)
val = data.get(key, "")
if val:
    print(val)
PY
}

_manifest_set() {
  # $1 = filename key, $2 = sha256 value. Rewrites the manifest with this
  # key updated (creating the manifest/dir if needed). No-op under --dry-run
  # (callers must not invoke this when DRY_RUN=1).
  mkdir -p "$CODEX_HOME"
  python3 - "$MANIFEST" "$1" "$2" <<'PY'
import json, sys
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    data = {}
data[key] = value
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
}

echo "install_codex_config: source=$SOURCE_DIR target=$CODEX_HOME dry_run=$DRY_RUN force=$FORCE"

# Fix round 1, non-blocking finding 8: refuse if the target codex home is
# itself a symlink, unless --force -- installing through a symlink can
# silently write into a location outside ~/.codex entirely (e.g. an
# attacker-controlled path), which none of this script's other checks are
# designed to detect.
if [ -L "$CODEX_HOME" ]; then
  if [ "$FORCE" -eq 0 ]; then
    echo "install_codex_config: REFUSING: $CODEX_HOME is a symlink. Re-run with --force to install through it anyway (not recommended)." >&2
    exit 5
  else
    echo "install_codex_config: WARNING: $CODEX_HOME is a symlink; proceeding because --force was given." >&2
  fi
fi

# Plan §4.8a item 1: chmod 700 on ~/.codex and chmod 600 on any auth file,
# as the FIRST step, re-asserted on EVERY run (a fresh `codex login` may
# reset the mode). Never reads or prints the auth file's contents -- mode
# bits only. Auth-file discovery is by common Codex CLI naming (auth.json /
# *auth*.json); if a future Codex version uses a different name, this loop
# still tightens ~/.codex itself, and a missing auth file today is expected
# (plan state: "Not logged in").
if [ -d "$CODEX_HOME" ]; then
  if [ "$DRY_RUN" -eq 0 ]; then
    chmod 700 "$CODEX_HOME"
  else
    echo "would chmod 700 $CODEX_HOME"
  fi
  while IFS= read -r -d '' authfile; do
    if [ "$DRY_RUN" -eq 0 ]; then
      chmod 600 "$authfile"
      echo "hardened: $(basename "$authfile") -> 600"
    else
      echo "would chmod 600 $(basename "$authfile")"
    fi
  done < <(find "$CODEX_HOME" -maxdepth 1 -type f -iname "*auth*" -print0 2>/dev/null)
fi

installed=0
skipped=0
refused=0

for name in "${FILES[@]}"; do
  src="$SOURCE_DIR/$name"
  dst="$CODEX_HOME/$name"

  if _is_forbidden_name "$name"; then
    echo "install_codex_config: REFUSING auth/credential-shaped filename: $name" >&2
    exit 3
  fi

  if [ ! -f "$src" ]; then
    echo "install_codex_config: ERROR: missing source file $src" >&2
    exit 1
  fi

  src_sha="$(_sha256 "$src")"

  if [ ! -f "$dst" ]; then
    echo "install: $name (new)"
    if [ "$DRY_RUN" -eq 0 ]; then
      mkdir -p "$CODEX_HOME"
      chmod 700 "$CODEX_HOME"
      cp "$src" "$dst"
      chmod 644 "$dst"
      _manifest_set "$name" "$src_sha"
    fi
    installed=$((installed + 1))
    continue
  fi

  dst_sha="$(_sha256 "$dst")"

  if [ "$dst_sha" = "$src_sha" ]; then
    echo "skip: $name (unchanged)"
    skipped=$((skipped + 1))
    continue
  fi

  last_installed_sha="$(_manifest_get "$name")"

  if [ -n "$last_installed_sha" ] && [ "$dst_sha" != "$last_installed_sha" ] && [ "$FORCE" -eq 0 ]; then
    # The file on disk was changed by something OTHER than this script since
    # the last install (a Codex upgrade rewriting it, or a hand edit) --
    # refuse rather than clobber, per the plan's explicit requirement.
    echo "REFUSE: $name has drifted from what this script last installed (recorded=$last_installed_sha, on-disk=$dst_sha, source=$src_sha)." >&2
    echo "  Re-run with --force to overwrite the on-disk file with the tracked source version." >&2
    refused=$((refused + 1))
    continue
  fi

  if [ "$FORCE" -eq 1 ] && [ -n "$last_installed_sha" ] && [ "$dst_sha" != "$last_installed_sha" ]; then
    echo "force-overwrite: $name (was drifted; recorded=$last_installed_sha on-disk=$dst_sha)"
  else
    echo "update: $name (source changed)"
  fi

  if [ "$DRY_RUN" -eq 0 ]; then
    cp "$src" "$dst"
    chmod 644 "$dst"
    _manifest_set "$name" "$src_sha"
  fi
  installed=$((installed + 1))
done

echo "install_codex_config: installed=$installed skipped=$skipped refused=$refused"

if [ "$refused" -gt 0 ]; then
  exit 4
fi
exit 0
