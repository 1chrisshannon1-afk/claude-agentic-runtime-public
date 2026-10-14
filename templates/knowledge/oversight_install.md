# Oversight System — install, schedules, and operations (SEED)

> **THIS IS A SEED FILE, per-INSTALL, not per-repo.** `init_repo.sh` copies this file to
> `~/.claude/knowledge/oversight_install.md` **only if that path is absent** — it never overwrites
> a machine that already has a real, populated copy. Once copied, this file is YOURS: edit its
> STATUS block, TRACKING line, and §2 job table to describe the jobs you actually install on this
> machine, in this repo. The portable mechanics this file used to also carry (heartbeat contract,
> kill-switch, install procedure, troubleshooting, lock notes) now live in
> `docs/subsystems/oversight-install.md`, which ships with the runtime bundle and never needs
> per-machine editing — read it there for how any of this actually works.

## 0. Status

> **TRACKING (per-repo, kept current — read this, not a hardcoded issue number in any prompt).**
> This repo's open oversight tracking issue is **__TRACKING_ISSUE__**. Every job prompt / agent
> definition that needs "the open oversight tracking issue" reads this line rather than hardcoding
> an issue number. **Maintenance contract:** whichever session next finds this issue closed with no
> living successor named must open a fresh one and update this line in the same change.

Replace this paragraph with your own install's status narrative: which jobs are committed vs.
loaded, any collision or rollout findings specific to this machine, and the date of the last
verified `launchctl list` sweep. Keep it current — this is the first thing a session reads before
trusting the job table below.

## 1. Permission precondition

**PERMISSION MODEL OF A HEADLESS JOB (load-bearing for every job; measured on the Claude Code CLI,
GH #4767).** A `claude -p --permission-mode acceptEdits` session loads three settings sources — the
user `~/.claude/settings.json`, the repo's `.claude/settings.json`, and the repo's
`.claude/settings.local.json` (the last only when its cwd is inside a git repo) — plus any CLI
flags. It can Read and Write/Edit its cwd, every `permissions.additionalDirectories` entry and every
`--add-dir`; run any Bash command an allow rule from any source matches; and use every MCP server
those sources enable. Anything not allowed is denied, never prompted; a deny from any source beats
an allow from any source. On top of that:
- **Any path under a directory named `.claude` is a "sensitive file", with two exceptions.** The
  Write/Edit tools, `>`/`>>`, `cp`, `mkdir`, `sed -i` and `rm` into it are refused even inside an
  `--add-dir` grant and regardless of allow rules. A settings grant (e.g. `Bash(*)`/`Write(*)` in
  `settings.local.json`) does NOT make heartbeat writes under `~/.claude/schedules/` work.
  - **The CLI's own auto-memory dir** (`~/.claude/projects/<cwd-slug>/memory/`, reported as
    `memory_paths.auto` in a session's `init` event) takes Write-tool and redirect writes with no
    grant at all. Every interactive session with the same cwd loads it, so a job that must not
    persist text into the operator's sessions needs a `//` Edit/Write deny covering `~/.claude/**`
    (or at least that dir).
  - **A Bash heredoc the analyzer bails on** (a JSON `{"` or `$(...)` body) gets through in a repo
    with a bare `Bash` allow, and it also gets past `//` Edit/Write denies. Do not rely on it, and
    do not count on a `//` deny to stop it.
- **At least these two write paths are outside the sensitive-file rule (this is the MEASURED set,
  never asserted complete — N6); each writes wherever its command is allowed.** A python3
  subprocess's own writes are never mediated, so `python3 <script>` writes anywhere once the
  `python3` command is allowed. `tee` into a `.claude` path is decided by allow rules alone: it
  writes wherever an allow rule covers it (a bare `Bash` allow included), and only a missing allow
  or a deny stops it; a `Bash(tee:*)` deny does not match an absolute `/usr/bin/tee`. Treat both as
  write paths when you scope a job's grants. **An installed job writes under `~/.claude` through a
  python3 channel** (the wheel's is `hooks/wheel_sink.py`); do not rely on heredocs or `tee`.
  **UNVERIFIED either way, not yet measured:** `/usr/bin/touch`, `bash -c` writing directly, other
  interpreters (`perl`, `ruby`, `node`, `osascript -e`), `dd`, and `git config --file` into a
  `.claude` path — do not assume any of these is closed or open until it is actually measured.
- **`git log`/`git show --output=<file>` write wherever those commands are allowed**; deny them with
  `Bash(git log *--output*)` / `Bash(git show *--output*)` where that matters.
- **Path-rule syntax:** absolute paths need `//` (`Edit(//abs/path/**)`); a single leading slash is
  resolved relative to the settings file and matches nothing. In a settings file only `Edit(...)`
  path rules affect writes (they cover the Write tool); `Write(...)` path rules there are inert.
  On the CLI, `//` Edit/Write denies stop the Write tool and plain redirects, but not a command's
  own file arguments and not the heredoc gap above.
- **A `//` deny is a FLOOR, not a ceiling — it closes only the path(s) it names, nothing wider.**
  A `Write(//<dir>/**)` deny over one directory does not narrow the Write tool's reach to "the
  same reach a bare `Bash` allow already has" or to any other implied ceiling; the Write tool
  still reaches every user-writable path that no `//` deny explicitly names (measured on a real
  job: #5902's wheel launcher denied Edit/Write over the whole of `$HOME`, and a live probe
  still found the Write tool creating and overwriting files under `$TMPDIR` and other paths
  outside `$HOME` that the deny set never named). Never write or repeat a containment claim wider
  than the specific paths a job's own deny list enumerates — state only what was actually denied
  and, separately, what was actually measured to still be reachable.
- **`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`** removes every MCP server; **`--tools
  <list>`** fixes the built-in tool set.

The install procedure therefore includes a one-off probe from the target repo (a git-initialised
throwaway copy of its `permissions` blocks, with the same blocks also passed through `--settings`:
an untrusted throwaway ignores its `.claude/settings.json` allow entries, and the real repo does
not) confirming the job's own write channel works before any real job is loaded. Also: `mkdir -p ~/.claude/schedules/logs ~/.claude/schedules/heartbeats
~/.claude/schedules/queue` is a mandatory install step — the three directories are gitignored, so a
fresh clone has none, and launchd will not start a job whose StandardOutPath directory is missing.

## 2. The jobs (label · expected_state · cadence · repo · prompt file)

Replace the single example row below with one row per job you actually install, following the
exact column contract `hooks/heartbeat_audit.py`'s `parse_job_table` expects: `label` in column 1,
`expected_state` in column 2, cadence text in column 3 — see `docs/subsystems/oversight-install.md`
§ *Liveness contract* for the full contract this table feeds.

| label | expected_state | StartCalendarInterval | repo (WorkingDirectory) | prompt file | does |
|---|---|---|---|---|---|
| com.oversight.example.daily | unloaded | 05:10 daily | __ABSOLUTE_PATH_TO_YOUR_REPO__ | `daily_sweep.txt` | SEED ROW — flip expected_state to `loaded` when you load this job; add one row per job you install |
