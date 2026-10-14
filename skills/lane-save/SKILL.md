---
name: lane-save
description: Checkpoint a lane as a NEW `## Lane state` comment on its issue, never editing an earlier one. Without an argument the issue number comes only from the lane worktree the session is in, cross-checked against the lane ledger; anything else stops and asks for the number. LIVE only (no dry-run). No worktree exit, no lane.sh call, no ledger write, no push, no PR.
argument-hint: "[issue#]"
---

# /lane-save [issue#]

Leaves an honest, append-only record of where a lane stands, for a hand-off or before context runs low. Specs:
adoption plan `~/.claude/plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md` §7.4, §7.5; sprint
row L5.2 in `~/.claude/plans/otherapp_sprint_1_lane_control_and_floor.md`.

**LIVE only. There is no dry-run mode.** Every run posts a real, permanent comment. Exercise it only inside a scratch
issue's lane (open one with `/lane-start` on a scratch issue).

## Conventions

1. **Literal values.** Step 2 prints `<main>`, `<r>` (`github.repo`) and `<base_ref>` (`lane.base_ref`). Paste them
   literally into later commands. Bash-tool shell variables do not survive between calls, and
   `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo ""` silently resolves from the cwd.
2. **Exact tool forms.** Manifest: `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo <main>` (not on
   PATH). Posting: `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh comment <n> --body-file <f>)`. The
   helper is a bash script with no `--repo` flag that resolves the repo from its cwd; never invoke it with python3,
   by bare name, or by a relative path. Raw `gh issue ...` calls carry `--repo <r>`.
3. **Append-only.** Each save is a NEW comment. Never `gh issue comment --edit`; never edit, replace or delete an
   earlier comment, and never reuse its id.
4. **Ledger** (`~/.claude/.lanes/lanes.jsonl`, or `$LANE_DIR/lanes.jsonl` in a hermetic sandbox) is read-only here.
   This skill writes no ledger row and never claims one: `lane.sh` has no `save` event yet (#5833).
5. It does not leave the worktree, calls no `lane.sh` subcommand, never pushes and never opens a PR (runtime
   CLAUDE.md §4). It runs no mutating git form: no `git worktree`, `git branch` create/`-d`/`-D`, `checkout`,
   `switch`, `stash`, `reset`, `rebase`, working-tree `restore`, `clean`, `--force`, `--no-verify` or `SKIP_*` env.
6. The body carries no secrets, tokens, PII or PHI. It is written to a `mktemp` file removed in the same call.
7. **3-strike.** If the same step fails a third time, stop and report what failed and what was tried.
8. It posts no operator card. Its only question, the issue number, is an invocation argument, not an operator
   decision.

## Snippets

**MAIN** (prints `TOP` and either `MAIN <path>` or `STOP <reason>`; from inside a lane the common dir is the main
tree's `.git`, so `MAIN` is still the main tree):
```bash
bash <<'SH'
top=$(git rev-parse --show-toplevel 2>/dev/null)
echo "TOP ${top:-<not a repo>}"
c=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
m=$(dirname "${c:-/none/x}")
if [ -z "$c" ]; then echo "STOP not inside a git repository"
elif [ "$(basename "$c")" != .git ]; then echo "STOP common dir $c is not a .git directory"
elif [ "$(git -C "$m" rev-parse --show-toplevel 2>/dev/null)" != "$m" ]; then echo "STOP $m is not its own toplevel"
elif case "$m" in */.claude/worktrees/*) true;; *) false;; esac; then echo "STOP $m is under .claude/worktrees"
elif [ ! -f "$m/.claude/oversight/manifest.json" ]; then echo "STOP no manifest at $m/.claude/oversight/manifest.json"
else echo "MAIN $m"; fi
SH
```

**LEDGER** (read-only; prints the last row for `(<main>, <n>)`, or `null`):
```bash
python3 - <main> <n> <<'PY'
import json, os, sys
main, n = sys.argv[1], int(sys.argv[2])
led = os.path.join(os.environ.get("LANE_DIR") or os.path.expanduser("~/.claude/.lanes"), "lanes.jsonl")
last = None
if os.path.exists(led):
    for line in open(led, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("repo") == main and r.get("issue") == n:
            last = r
print(json.dumps(last))
PY
```

## Steps

1. **Argument.** Optional. If given, it must be all digits; otherwise stop.
2. **Main tree.** Run MAIN. A `STOP` line: stop and report it. Otherwise `<main>` is the `MAIN` path and `TOP` is the
   session's toplevel. Read `github.repo` and `lane.base_ref` with the manifest form.
3. **Which issue.**
   - **No argument: the only accepted form.**
     1. `TOP` must be `<main>/.claude/worktrees/<dir>` with `<dir>` matching `^issue-([0-9]+)-`; `<n>` is that number.
     2. LEDGER for `<n>` must return a row with `event == "open"`, `worktree == TOP`, and `branch` equal to
        `git -C <TOP> rev-parse --abbrev-ref HEAD`, which must not print `HEAD` (a detached HEAD).
     3. Any failure (running from the main tree, from a non-lane worktree, a missing or mismatched row, a detached
        HEAD): stop and ask for the issue number (`/lane-save <n>`). Nothing is posted.
     Never parse digits out of a branch name: a dated work branch such as `work/2026-07-13` (example) parses to
     #2026, a real, closed issue.
   - **Explicit `<n>`.** If `TOP` is a lane worktree `<main>/.claude/worktrees/issue-<m>-...` with `<m>` != `<n>`,
     stop and ask. If LEDGER for `<n>` has no row with `event` `open` or `abandoned`, stop and ask.
   - `<wt>` and `<branch>` are the ledger row's `worktree` and `branch`.
4. **Read the issue.** `gh issue view <n> --repo <r> --json state,comments`. If that fails, stop. If `state` is not
   `OPEN`, stop and ask (report the state). Read the earlier `## Lane state` comments so this one does not restate
   them.
5. **Facts, read-only, from the lane:**
   ```bash
   git -C <wt> rev-parse HEAD
   git -C <wt> status --porcelain; echo "status rc=$?"
   git -C <wt> diff --name-only <base_ref>...HEAD
   ```
   A non-zero status rc is reported as "tree state unverifiable", never as clean. A missing `<wt>` is reported as
   such.
6. **Body.** The first line is exactly `## Lane state`:
   ```
   ## Lane state

   **Progress:** <done since the last save>
   **Remaining:** <what is left>
   **Blockers:** <none | what>
   **Files touched:** <committed vs <base_ref>; uncommitted>
   **Tests run:** <exact command -> actual result, for tests run this session; "none run" otherwise>
   **Branch / HEAD:** <branch> @ <sha>
   **Tree:** clean | dirty (<count> paths) | unverifiable
   ```
   Report only tests actually run, with their real results. Never claim a test that did not run.
7. **Post.** `f=$(mktemp) && cat > "$f" <<'EOF'` ... `EOF`, then
   `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh comment <n> --body-file "$f"); rc=$?; rm -f "$f"; echo "rc=$rc"`.
8. **Report**: the issue and the comment posted. Nothing else changed. A later save posts a second, separate comment.

## Failure modes

- Bad argument; no-argument resolution fails; a different lane's issue; no ledger row; issue not OPEN: stop and ask.
  Nothing posted.
- Main tree unresolvable or issue read fails: stop and report. Nothing posted.
- The post fails (rc != 0): report it. Never fall back to editing an earlier comment. The run changed nothing else.
- Same step failing a third time: stop and report (3-strike).
