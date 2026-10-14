---
name: trim-memory
description: Operator MEMORY.md hygiene — five pure-function reapers trim stale, resolved, dead, and oversized entries. Dry-run by default; --apply moves files to archive. Meta-skill that operates on ~/.claude/projects/ only.
user-invocable: true
argument-hint: "[--dry-run | --apply] [--reaper <name>] [--memory-path <path>]"
meta-skill: true
---

# /trim-memory

**Meta-skill.** Operates on `~/.claude/projects/*/memory/MEMORY.md` and its sibling `.md` files. Does NOT load company context, does NOT call `scripts/agency.py`, does NOT touch Firestore or any company-specific data. Exempt from canonical context-and-memory block and `--caller` flag.

**URGENT trigger:** run this when MEMORY.md exceeds 24.4 KB (the load-limit). Current baseline: 25.1 KB as of 2026-05-19.

## Arguments

- `--dry-run` (default) — print proposed changes; write `trim_report.json`; do NOT move files.
- `--apply` — execute moves: archive files to `memory/archive/<YYYY-MM-DD>/`; update MEMORY.md index entries with `[archived YYYY-MM-DD]` suffix.
- `--reaper <name>` — run only one reaper: `stale-dated`, `resolved-project`, `superseded-ref`, `dead-path`, `line-length`.
- `--memory-path <path>` — override default memory dir (default: auto-detected from `~/.claude/projects/`).

## Step 1 — Locate memory directory

```bash
python3 ~/.claude/skills/trim-memory/trim_memory.py --dry-run --memory-path \
  ~/.claude/projects/-Users-x-Desktop-OtherApp/memory
```

If the path is unknown, enumerate:

```bash
find ~/.claude/projects -name "MEMORY.md" 2>/dev/null
```

## Step 2 — Inspect current size

```bash
wc -c ~/.claude/projects/-Users-x-Desktop-OtherApp/memory/MEMORY.md
wc -l ~/.claude/projects/-Users-x-Desktop-OtherApp/memory/MEMORY.md
```

Alert threshold: >24400 bytes. Hard-stop threshold: >26000 bytes (context will be truncated mid-index).

## Step 3 — Run dry-run (all reapers)

```bash
python3 ~/.claude/skills/trim-memory/trim_memory.py \
  --dry-run \
  --memory-path ~/.claude/projects/-Users-x-Desktop-OtherApp/memory \
  2>&1 | tee /tmp/trim_memory_dry_run.txt
```

Review output. The script emits `trim_report.json` in the memory directory. Inspect it:

```bash
python3 -c "
import json, pathlib
report = json.loads(pathlib.Path(
    '/tmp/trim_report.json'
).read_text() if pathlib.Path('/tmp/trim_report.json').exists() else
    pathlib.Path('~/.claude/projects/-Users-x-Desktop-OtherApp/memory/trim_report.json')
    .expanduser().read_text()
)
print(f'Proposed archives: {len(report[\"proposed_archives\"])}')
print(f'Flags (human review): {len(report[\"flags\"])}')
print(f'Line-length warnings: {len(report[\"line_length_warnings\"])}')
for item in report['proposed_archives']:
    print(f'  ARCHIVE [{item[\"reaper\"]}] {item[\"filename\"]} — {item[\"reason\"]}')
for item in report['flags']:
    print(f'  FLAG [{item[\"reaper\"]}] {item[\"filename\"]} — {item[\"reason\"]}')
"
```

## Step 4 — Human review of proposed archives

For each proposed archive, verify:
- Is the entry truly resolved/stale/dead?
- Would losing it from active context cause a regression in any ongoing work?
- For `dead-path`: is the file actually gone, or just moved?

Do NOT auto-approve all. Spot-check at least 20% of proposals.

## Step 5 — Run individual reapers selectively (optional)

To scope to just one reaper before applying:

```bash
python3 ~/.claude/skills/trim-memory/trim_memory.py \
  --dry-run \
  --reaper stale-dated \
  --memory-path ~/.claude/projects/-Users-x-Desktop-OtherApp/memory
```

Available reaper names: `stale-dated`, `resolved-project`, `superseded-ref`, `dead-path`, `line-length`.

## Step 6 — Apply approved archives

After operator review of `trim_report.json`:

```bash
python3 ~/.claude/skills/trim-memory/trim_memory.py \
  --apply \
  --memory-path ~/.claude/projects/-Users-x-Desktop-OtherApp/memory \
  2>&1 | tee /tmp/trim_memory_apply.txt
```

This:
1. Creates `memory/archive/<YYYY-MM-DD>/` directory.
2. Moves approved files into it (files in `proposed_archives` only; flagged files are NOT moved).
3. Updates MEMORY.md: appends `[archived YYYY-MM-DD]` to the index line for each archived file. Does NOT delete the index line.
4. Writes final `trim_report.json` with `applied: true` field and list of moved files.

## Step 7 — Verify size reduction

```bash
wc -c ~/.claude/projects/-Users-x-Desktop-OtherApp/memory/MEMORY.md
```

Target: <22000 bytes after archiving. If still over 24400, run again focusing on `line-length` entries (shorten verbose index lines to <250 chars).

## Step 8 — Commit operator-local files (no repo commit needed)

The operator-local memory directory is NOT in a git repo. No commit required. The `trim_report.json` serves as the audit log.

If operator wants a git record, they can manually copy `trim_report.json` to `plans/operator-tooling/trim_reports/<date>.json` in the OtherApp repo and commit it.

## Step 9 — Run line-length fixer on MEMORY.md index (if needed)

The `line-length` reaper only WARNS; it does not modify. To actually shorten verbose lines:

```bash
python3 ~/.claude/skills/trim-memory/trim_memory.py \
  --reaper line-length \
  --dry-run \
  --memory-path ~/.claude/projects/-Users-x-Desktop-OtherApp/memory
```

Then manually edit MEMORY.md lines that exceed 250 chars, trimming to the essential facts. Move detail to the linked topic file.

## Step 10 — Periodic maintenance cadence

Run `/trim-memory --dry-run` monthly or when MEMORY.md exceeds 20 KB. Schedule:
- Monthly: dry-run + flag review.
- Quarterly: apply + verify.
- Immediate: any time MEMORY.md exceeds 24.4 KB (load limit).

---

## The Five Reapers

### 1. stale-dated
Finds entries with `Set YYYY-MM-DD` pattern in their body where the date is >180 days ago AND the linked `.md` file's mtime is also >180 days old AND the filename is not cross-referenced from any other memory file. Proposes archive.

### 2. resolved-project
Finds entries whose filename starts with `project_*` where the linked file contains any of `RESOLVED`, `DONE`, `SHIPPED`, or `fixed 20` in a header or first paragraph AND the file mtime is >60 days. Proposes archive.

### 3. superseded-ref
Scans every memory file for sibling filename references (links to other `.md` files in the same directory). If two files reference each other bidirectionally, flags both for human review. Does NOT auto-archive. Human must decide which is canonical.

### 4. dead-path
Scans entry text for paths matching `/Users/x/Desktop/OtherApp/<path>`. Calls `os.path.exists()` on each path found. If the path does not exist in the filesystem, flags the entry. Does NOT auto-archive (paths may be intentionally archived or on a different machine).

### 5. line-length
Warns on any MEMORY.md index line exceeding 250 characters. Does not modify files. Output lists line number, character count, and first 80 chars for context.

---

## Script location

```
~/.claude/skills/trim-memory/trim_memory.py
```

Copy to OtherApp repo for shared review:
```
scripts/operator/trim_memory.py
```

Documentation:
```
plans/operator-tooling/trim-memory.md  (OtherApp repo)
```
