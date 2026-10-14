#!/usr/bin/env bash
# init_repo.sh — self-install the Claude Code runtime bundle into a product repo.
#
# WHY THIS EXISTS
# ----------------
# `runtime_bundle_repo_agnostic_plan.md` §WS3.2: a fresh clone of this runtime bundle needs one
# command that gets a NEW repo to the point where `repo_manifest.py doctor` has something to
# report against — oversight dossier skeletons copied in, a manifest.json to fill, and the
# worktree base-ref setting THE ISSUE WHEEL depends on. It is deliberately idempotent (never
# overwrites a file a human may have started editing) and deliberately non-mutating for its
# `--diff` mode (preview only, the "cruft diff" shape from §9's prior-art review — never a merge).
#
# USAGE
# -----
#   init_repo.sh <repo-root> [--update-version]
#   init_repo.sh --diff <repo-root>
#   init_repo.sh --help
#
# ENV
# ---
#   CLAUDE_DIR   runtime root this bundle lives in (default: $HOME/.claude)
#
# EXIT CODES
# ----------
#   0   success (init: even when validate/doctor report findings -- those are expected on a
#       fresh, unfilled manifest and are printed, never treated as init failure)
#   2   <repo-root> is not a git repo root; (--diff) .bundle_version is missing, unreadable, or
#       names a sha that is not a reachable revision in $CLAUDE_DIR; or (init) settings.json
#       exists but could not be safely updated -- not valid JSON, its top level is not an
#       object, or its "worktree" key is present but is not itself an object. On any of these
#       settings.json failures, init stops at that step: everything BEFORE it (dossiers,
#       manifest.json, the knowledge seeds) has already been written, settings.json itself is
#       left completely untouched (the write is atomic -- a temp file is written and renamed
#       over the original only on success, so a failure never leaves a truncated or partial
#       settings.json), and .bundle_version / validate / doctor never run.
#   64  bad usage (unknown flag, missing argument)
#
# Idempotency: running init a second time against the same repo-root prints "kept ..." for
# every step -- nothing is overwritten. Verify by running this script twice in a row.

set -u

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"

_USAGE="usage: init_repo.sh <repo-root> [--update-version]
       init_repo.sh --diff <repo-root>
       init_repo.sh --help

Self-installs the Claude Code runtime bundle's per-repo scaffolding into <repo-root>:
  - <repo-root>/.claude/oversight/          -- one dossier skeleton per template (kept if present)
  - <repo-root>/.claude/oversight/manifest.json   -- from templates/oversight/manifest.example.json
  - <repo-root>/.claude/settings.json       -- worktree.baseRef: \"head\" (added if absent)
  - <repo-root>/.claude/oversight/.bundle_version -- the ~/.claude commit sha these templates came from
  - seeds the three per-machine files this runtime needs into ~/.claude/knowledge/ if absent

Then runs 'repo_manifest.py validate' and 'doctor' against <repo-root> and prints their output.

  --update-version   overwrite .bundle_version with the runtime's current HEAD sha
  --diff <repo-root>  print a unified diff of every oversight template that changed at
                      ~/.claude HEAD since .bundle_version was recorded, against the repo's own
                      dossier -- preview only, never writes anything
  --help              print this message

env:
  CLAUDE_DIR   runtime root (default \$HOME/.claude)
"

_die_usage() {
  printf '%s' "$_USAGE" >&2
  exit 64
}

_require_git_repo_root() {
  # Prints nothing; sets $? via return. $1 = candidate repo root (already resolved to absolute).
  local root="$1" toplevel
  toplevel="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || return 1
  [[ "$toplevel" == "$root" ]]
}

_abspath() {
  # Resolve a possibly-relative path to an absolute one without requiring it to exist yet
  # (a repo root always exists, but keep this robust regardless).
  local p="$1"
  if [[ -d "$p" ]]; then
    (cd -- "$p" && pwd)
  else
    printf '%s\n' "$p"
  fi
}

cmd_diff() {
  local repo_root="$1"
  local bundle_version_path="$repo_root/.claude/oversight/.bundle_version"

  if ! _require_git_repo_root "$repo_root"; then
    echo "not-a-repo-root: $repo_root is not a git repository root" >&2
    exit 2
  fi

  if [[ ! -f "$bundle_version_path" ]]; then
    echo "bundle_version-unreadable: $bundle_version_path does not exist" >&2
    exit 2
  fi

  local sha
  sha="$(cat "$bundle_version_path" 2>/dev/null | tr -d '[:space:]')"
  if [[ ! "$sha" =~ ^[0-9a-f]{7,40}$ ]]; then
    echo "bundle_version-unreadable: $bundle_version_path does not contain a plain hex git sha" >&2
    exit 2
  fi

  local sha7="${sha:0:7}"
  local changed
  if ! changed="$(git -C "$CLAUDE_DIR" diff --name-only --end-of-options "${sha}..HEAD" -- templates/oversight/ 2>/dev/null)"; then
    echo "bundle_version-unreadable: $bundle_version_path records $sha7, which is not a revision in $CLAUDE_DIR" >&2
    exit 2
  fi
  if [[ -z "$changed" ]]; then
    echo "no template changes since $sha7"
    exit 0
  fi

  local rel name repo_file template_file
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    # $rel is repo-relative to $CLAUDE_DIR (e.g. "templates/oversight/foo.md"); strip only the
    # "templates/oversight/" prefix rather than basename-ing it, so a template that legitimately
    # lives in a subdirectory keeps its subpath instead of silently colliding on basename alone.
    name="${rel#templates/oversight/}"
    [[ "$name" == "PLACEHOLDERS.md" || "$name" == "manifest.example.json" ]] && continue
    template_file="$CLAUDE_DIR/$rel"
    repo_file="$repo_root/.claude/oversight/$name"
    echo "=== $name (template changed since $sha7) ==="
    if [[ ! -f "$template_file" ]]; then
      echo "template removed upstream: $name"
    elif [[ ! -f "$repo_file" ]]; then
      echo "dossier missing"
    else
      diff -u "$template_file" "$repo_file"
    fi
    echo
  done <<< "$changed"

  exit 0
}

_run_repo_manifest_step() {
  # $1 = subcommand (validate|doctor), $2 = repo root. Runs
  # `repo_manifest.py <subcommand> --repo <repo_root>`, prints its stdout as-is (the findings
  # output, exactly as before), and on a genuine interpreter-level failure -- detected by an
  # actual Python traceback in stderr, OR repo_manifest.py itself being absent (the interpreter
  # never gets far enough to raise a Python-level traceback for that case -- it's an OS-level
  # "can't open file" on stderr instead), never by exit code alone, since a clean findings exit
  # can share a numeric value with Python's default uncaught-exception exit -- prints one
  # `WARNING: <verb> could not run (exit N)` line instead of the raw error, and still returns 0
  # (init itself never fails because a downstream reporting step crashed or is missing).
  local verb="$1" repo_root="$2"
  local out err status stderr_tmp
  stderr_tmp="$(mktemp)"
  out="$(python3 "$CLAUDE_DIR/scripts/repo_manifest.py" "$verb" --repo "$repo_root" 2>"$stderr_tmp")"
  status=$?
  err="$(cat "$stderr_tmp" 2>/dev/null)"
  rm -f "$stderr_tmp"

  if [[ "$err" == *"Traceback (most recent call last)"* ]] || \
     [[ "$err" == *"can't open file"* && "$err" == *"repo_manifest.py"* ]]; then
    echo "WARNING: $verb could not run (exit $status)"
    return 0
  fi

  [[ -n "$out" ]] && printf '%s\n' "$out"
  [[ -n "$err" ]] && printf '%s\n' "$err" >&2
  return 0
}

cmd_init() {
  local repo_root="$1" update_version="$2"

  if ! _require_git_repo_root "$repo_root"; then
    echo "not-a-repo-root: $repo_root is not a git repository root" >&2
    exit 2
  fi

  local oversight_dir="$repo_root/.claude/oversight"
  mkdir -p "$oversight_dir"

  # (3) Copy every templates/oversight/*.md except PLACEHOLDERS.md, only if absent.
  local templates_dir="$CLAUDE_DIR/templates/oversight"
  if [[ ! -d "$templates_dir" ]]; then
    echo "templates-missing: $templates_dir does not exist -- an empty runtime install cannot" \
      "be reported as a successful init" >&2
    exit 2
  fi
  local tmpl name dest
  for tmpl in "$templates_dir"/*.md; do
    [[ -e "$tmpl" ]] || continue
    name="$(basename "$tmpl")"
    [[ "$name" == "PLACEHOLDERS.md" ]] && continue
    dest="$oversight_dir/$name"
    if [[ -f "$dest" ]]; then
      echo "kept $name"
    else
      cp "$tmpl" "$dest"
      echo "copied $name"
    fi
  done

  # (4) manifest.example.json -> manifest.json, only if absent.
  local manifest_dest="$oversight_dir/manifest.json"
  if [[ -f "$manifest_dest" ]]; then
    echo "kept manifest.json"
  else
    if [[ -f "$templates_dir/manifest.example.json" ]]; then
      cp "$templates_dir/manifest.example.json" "$manifest_dest"
      echo "copied manifest.json"
    fi
  fi

  # (5) Seed ~/.claude/knowledge/<name> from templates/knowledge/*, only if absent. Per-MACHINE,
  # not per-repo -- these land in $CLAUDE_DIR, never under <repo-root>.
  local knowledge_templates_dir="$CLAUDE_DIR/templates/knowledge"
  local knowledge_dir="$CLAUDE_DIR/knowledge"
  local seed seed_name seed_dest
  if [[ -d "$knowledge_templates_dir" ]]; then
    mkdir -p "$knowledge_dir"
    for seed in "$knowledge_templates_dir"/*; do
      [[ -e "$seed" ]] || continue
      [[ -f "$seed" ]] || continue
      seed_name="$(basename "$seed")"
      seed_dest="$knowledge_dir/$seed_name"
      if [[ -f "$seed_dest" ]]; then
        echo "kept $seed_name"
      else
        cp "$seed" "$seed_dest"
        echo "seeded $seed_name"
      fi
    done
  fi

  # (6) <repo-root>/.claude/settings.json: worktree.baseRef.
  local settings_path="$repo_root/.claude/settings.json"
  if [[ ! -f "$settings_path" ]]; then
    printf '{\n  "worktree": {\n    "baseRef": "head"\n  }\n}\n' > "$settings_path"
    echo "created settings.json with worktree.baseRef=head"
  else
    python3 - "$settings_path" <<'PYEOF'
import json
import os
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    text = fh.read()

try:
    data = json.loads(text) if text.strip() else {}
except json.JSONDecodeError:
    print(f"settings.json-unreadable: {path} is not valid JSON", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    print(f"settings.json-unreadable: {path} top level is not an object", file=sys.stderr)
    sys.exit(1)

worktree = data.get("worktree")
if isinstance(worktree, dict) and "baseRef" in worktree:
    print(f"kept worktree.baseRef={worktree['baseRef']}")
    sys.exit(0)

if worktree is not None and not isinstance(worktree, dict):
    print("settings.json-unreadable: worktree is not an object", file=sys.stderr)
    sys.exit(1)

worktree = {} if worktree is None else worktree
worktree["baseRef"] = "head"
data["worktree"] = worktree

new_text = json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
tmp_path = path + ".tmp"
with open(tmp_path, "w", encoding="utf-8") as fh:
    fh.write(new_text)
os.replace(tmp_path, path)
print("set worktree.baseRef=head")
PYEOF
    local py_status=$?
    if [[ $py_status -ne 0 ]]; then
      exit 2
    fi
  fi

  # (7) .bundle_version -- write only if absent, unless --update-version.
  local bundle_version_path="$oversight_dir/.bundle_version"
  local head_sha
  head_sha="$(git -C "$CLAUDE_DIR" rev-parse HEAD 2>/dev/null)"
  if [[ -z "$head_sha" ]]; then
    echo "bundle_version-unreadable: could not resolve $CLAUDE_DIR HEAD" >&2
  elif [[ ! -f "$bundle_version_path" || "$update_version" == "1" ]]; then
    printf '%s\n' "$head_sha" > "$bundle_version_path"
    if [[ "$update_version" == "1" ]]; then
      echo "updated .bundle_version to $head_sha"
    else
      echo "wrote .bundle_version=$head_sha"
    fi
  else
    echo "kept .bundle_version"
  fi

  # (8) validate + doctor. repo_manifest.py's own designed exit codes (0 = OK, non-zero =
  # findings it printed cleanly) are expected outcomes here, never init failure -- but an
  # interpreter-level failure (the interpreter itself can't run, or the module raises
  # uncaught) is a different thing: it produces no clean findings output, just a Python
  # traceback on stderr. Detect that case by its actual signature (a traceback marker in
  # stderr) rather than by exit code, since findings and a crash can share an exit code
  # (doctor's own findings exit is 1, the same value Python uses for an uncaught exception).
  echo
  echo "VALIDATE:"
  _run_repo_manifest_step validate "$repo_root"
  echo
  echo "NEXT: fill manifest.json"
  echo
  echo "DOCTOR:"
  _run_repo_manifest_step doctor "$repo_root"

  exit 0
}

main() {
  local update_version="0"
  local mode="init"
  local repo_arg=""

  if [[ $# -eq 0 ]]; then
    _die_usage
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h)
        printf '%s' "$_USAGE"
        exit 0
        ;;
      --diff)
        mode="diff"
        shift
        ;;
      --update-version)
        update_version="1"
        shift
        ;;
      --*)
        echo "unknown flag: $1" >&2
        _die_usage
        ;;
      *)
        if [[ -n "$repo_arg" ]]; then
          echo "unexpected extra argument: $1" >&2
          _die_usage
        fi
        repo_arg="$1"
        shift
        ;;
    esac
  done

  if [[ -z "$repo_arg" ]]; then
    _die_usage
  fi

  local repo_root
  repo_root="$(_abspath "$repo_arg")"

  if [[ "$mode" == "diff" ]]; then
    cmd_diff "$repo_root"
  else
    cmd_init "$repo_root" "$update_version"
  fi
}

main "$@"
