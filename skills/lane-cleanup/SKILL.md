---
name: lane-cleanup
description: "Close out a lane. Resolves the main tree, exits any worktree with ExitWorktree keep, and prints a read-only dry-run (lane.sh status, ledger branch, issue state, and the lane's own PRs: same-repo, head = the ledger branch, created since its last open). Then it acts on one cell of a PR-state x --abandon/--update matrix. A PR merged to lane.pr_target wins (fetch, verify, resolve with the merge sha, Done, lane.sh reap); one merged only elsewhere stops and cards. An open PR means In review: its mergeStateStatus then decides the next step -- CLEAN cards a merge; BEHIND with --update runs a merge-slot update then cards the push; BEHIND without --update, or any other status, reports and waits for a later run; --abandon over an open PR refuses and cards regardless of status. Without either flag, no PR or only closed-unmerged PRs report in progress (a stale In review goes back to In progress) or abandoned-not-reaped; a CLOSED issue adds a card. Abandon (lane.sh abandon, reap --abandoned, board reset) runs only with --abandon and no open or merged PR. A session launched in the lane stops before any mutation; other runs from P4 on end with lane_orphans.sh. Push, PR and merge are separate carded asks, none posted while a hold ruling stands on any lane repo's operator surface."
argument-hint: "<issue#> [--abandon | --update]"
---

# /lane-cleanup <issue#> [--abandon | --update]

Takes one lane to its end state. Specs: adoption plan
`~/.claude/plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md` §7.1, §7.4-§7.6; sprint rows L5.2
and L5.4 in `~/.claude/plans/otherapp_sprint_1_lane_control_and_floor.md`; the lane.sh contract in
`~/.claude/plans/otherapp_s1_L5_5_lane_repo_enablement.md`; hub card 53 (option a: lanes are exempt from the no-PR
hold of its day, and every push, PR and merge is its own carded ask), a mechanism that any later standing ruling
holding lane pushes or PRs suspends (section 6.0); runtime `~/.claude/CLAUDE.md` §2 case (d), §4, §8, §11.

**The dry-run comes first and is read-only.** Nothing is mutated until the dry-run report is printed (section 1).

## Conventions (apply to every step)

1. **Literal values.** P2 prints `<main>` and the manifest values. Paste them literally into every later command:
   `<main>`; `<r>` = `github.repo`; `<proj>` = `github.project_number`; `<owner>` = `github.project_owner`;
   `<base_ref>`; `<remote>` and `<base_branch>` = `<base_ref>` split at its first `/`; `<pr_target>`. Bash-tool shell
   variables do not survive between calls, and `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo ""`
   silently resolves from the cwd, so no command may depend on a variable set in an earlier call.
2. **Exact tool forms.**
   - Manifest: `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo <main>` (not on PATH).
   - Issue helper: `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh <sub> ...)`. It is a bash script
     with no `--repo` flag that resolves the repo (and verifies `resolve` shas) from its cwd. Never invoke it with
     python3, by bare name, or by a relative path.
   - `(cd <main> && bash ~/.claude/scripts/lane.sh ...)` and `(cd <main> && bash ~/.claude/scripts/lane_orphans.sh)`.
     Neither takes `--repo`; both resolve from the cwd. From inside a worktree `lane.sh` refuses `nested-lane` and
     `lane_orphans.sh` reports a false clean.
   - Every raw `gh issue ...` / `gh pr ...` / `gh run ...` call carries `--repo <r>`.
   - **Board moves are read-then-transition.** Read `<cur>`: `gh issue view <n> --repo <r> --json projectItems` and
     `gh project view <proj> --owner <owner> --format json --jq .title` (`<board_title>`); `<cur>` is the
     `status.name` of the `projectItems[]` entry whose `title` equals `<board_title>`, or `none`. If `<cur>` already
     equals the target `<S>`, make no call: the helper's `transition` posts a `Status → **<S>**` comment on every
     call, so an unconditional call would post it again on every re-run. Otherwise run
     `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh transition <n> --status "<S>" --project <proj> --owner <owner>)`.
     `<S>` is exactly one of `In progress`, `In review`, `Done`, `Backlog` (`Ready #1` is a queue status this
     skill's own steps read as a possible `<cur>`, never a status any step here sets as `<S>`). A failed read (which moves
     nothing) or a non-zero exit is a failed board move: report it, never absorb it. Without `--project` the helper
     only posts a comment.
3. **Branch source.** The ledger row's `branch`, never rebuilt from `lane.branch_prefix` plus a slug and never
   assumed to be `issue/...`. This skill does not read `lane.branch_prefix` (only `lane.sh open` needs it, and it is
   REQUIRED there, never defaulted).
4. **Ledger** (`~/.claude/.lanes/lanes.jsonl`, or `$LANE_DIR/lanes.jsonl` in a hermetic sandbox) is read-only here;
   only `lane.sh` appends. This skill never writes a `save` or `merged` row (those are #5833 follow-ups).
5. **Worktrees.** ExitWorktree is only ever called with action `"keep"`: never `"remove"`, never
   `discard_changes: true`. A lane worktree is removed ONLY by `lane.sh reap` or `lane.sh reap --abandoned`.
   `lane.sh abandon` is ledger-only and KEEPS the worktree.
6. **Never**: raw `git worktree add/remove/move`; `git branch` create, `-d` or `-D`; `git checkout`, `switch`,
   `stash`, `reset`, `rebase`, working-tree `restore` or `clean`; `--force`; `--no-verify`; any `SKIP_*` bypass env
   (`SKIP_BRANCH_CHECK`, `SKIP_LOCAL_CI`, `SKIP_AUTOFORMAT`, `SKIP_PRE_PUSH_STAGE`); killing a process. **`git merge`
   only as 6.4's `UPDATE`** (never elsewhere, never `git merge --abort` outside that same snippet).
7. **Bodies** of comments and cards carry no secrets, tokens, PII or PHI. Write each body to a `mktemp` file and
   `rm -f` it in the same call.
8. **Outward actions.** Push, PR creation, PR close and merge are each their own carded ask with the exact command
   (section 6). None is autonomous or chat-only. Card 53 set this per-action ask mechanism; it authorizes no
   individual action, and a later standing ruling that holds lane pushes or PRs suspends it (section 6.0 checks for
   one, on the operator surface of every lane-enabled repo, before any push, PR or merge card). This skill never
   closes a PR on its own.
9. **3-strike.** If the same step fails a third time, stop and report what failed and what was tried. No fourth
   workaround.
10. **PR set.** A PR is this lane's only when it is a same-repo PR whose head is the ledger branch AND whose
    `createdAt` is at or after the lane's last `open` (the LEDGER `opened_ts`). Branch names are reused: an issue
    re-picked after a reap gets the same branch again, and `gh pr list --head` returns every earlier lane's PRs too.
    Apply the rule only through PRSET; never judge it by eye and never compare the two timestamps as strings (the
    ledger writes a `%z` offset such as `-0600`, GitHub writes `Z`).

## Snippets

**MAIN** (prints `TOP` and either `MAIN <path>` or `STOP <reason>`):
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
`<main>` is `dirname` of the absolute common dir, never `git rev-parse --show-toplevel` (inside a lane that is the
worktree).

**LEDGER** (read-only; `<which>` is an issue number or `all`; prints the last row per issue for `<main>` plus
`owner` = `self` | `live-foreign` | `dead` | `unknown` | `released`, and `opened_ts` = the ts of its last `open` row;
`null` means no row). `released` means the last row is not `open`: an `abandoned` (or `reaped`) row releases the
lane, and its `pid` is the session that ran `lane.sh abandon`, never the lane's worker, so it is no ownership signal:
```bash
python3 - <main> <which> <<'PY'
import json, os, socket, sys
main, want = sys.argv[1], sys.argv[2]
led = os.path.join(os.environ.get("LANE_DIR") or os.path.expanduser("~/.claude/.lanes"), "lanes.jsonl")
last, opened = {}, {}
if os.path.exists(led):
    for line in open(led, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("repo") == main:
            last[r.get("issue")] = r
            if r.get("event") == "open":
                opened[r.get("issue")] = r.get("ts")
def owner(r):
    if r.get("event") != "open":
        return "released"
    pid = r.get("pid")
    if r.get("host") != socket.gethostname() or type(pid) is not int:
        return "unknown"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except OSError:
        pass
    return "self" if str(pid) == os.environ.get("CLAUDE_PID") else "live-foreign"
keys = [k for k, r in last.items() if r.get("event") in ("open", "abandoned")] if want == "all" else [int(want)]
for k in keys:
    r = last.get(k)
    print(json.dumps(r and {**r, "owner": owner(r), "opened_ts": opened.get(k)}))
PY
```

**PRSET** (read-only; one call; `<opened_ts>` is the LEDGER `opened_ts`). Lists every PR on the branch and applies
convention 10. Prints one `KEPT` or `IGNORED` line per PR and a final `COUNTS M= X= O= C=` line (section 1, P6). On
a failed or unparseable lookup, a possibly truncated list, or an unusable `opened_ts`, it prints `LOOKUP-FAILED ...`
or `STOP ...` and exits 1 (P5):
```bash
python3 - <r> <branch> <opened_ts> <pr_target> <<'PY'
import datetime, json, subprocess, sys
r, branch, opened, target = sys.argv[1:5]
def die(msg):
    print(msg)
    sys.exit(1)
ts = lambda s: datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
try:
    since = ts(opened)
except (TypeError, ValueError):
    die(f"STOP lane opened_ts {opened!r} is not a timestamp")
p = subprocess.run(["gh", "pr", "list", "--repo", r, "--head", branch, "--state", "all", "--limit", "200", "--json",
                    "number,state,createdAt,mergedAt,mergeCommit,baseRefName,headRefName,headRefOid,isCrossRepository,url"],
                   capture_output=True, text=True)
try:
    prs = json.loads(p.stdout) if p.returncode == 0 else None
except ValueError:
    prs = None
if not isinstance(prs, list):
    die(f"LOOKUP-FAILED gh rc={p.returncode} {(p.stderr.strip().splitlines() or [''])[0][:200]}")
if len(prs) >= 200:
    die("LOOKUP-FAILED 200 PRs returned; the list may be truncated")
n = {"M": 0, "X": 0, "O": 0, "C": 0}
for x in sorted(prs, key=lambda x: x.get("number") or 0):
    try:
        created, state, head, fork = ts(x["createdAt"]), x["state"], x["headRefName"], x["isCrossRepository"]
        assert state in ("OPEN", "CLOSED", "MERGED") and isinstance(fork, bool)
    except (KeyError, TypeError, ValueError, AssertionError):
        die(f"LOOKUP-FAILED unparseable PR entry #{x.get('number')}")
    why = ("fork head" if fork else f"head {head} is not {branch}" if head != branch else
           f"predates this lane (created {x['createdAt']}; lane opened {opened})" if created < since else "")
    if why:
        print(f"IGNORED #{x['number']} {state} {why}")
        continue
    k = {"OPEN": "O", "CLOSED": "C"}.get(state) or ("M" if x.get("baseRefName") == target else "X")
    n[k] += 1
    sha = (x.get("mergeCommit") or {}).get("oid") or "-"
    print(f"KEPT #{x['number']} {state} base={x.get('baseRefName')} created={x['createdAt']} head={x.get('headRefOid')}"
          + (f" merge={sha} mergedAt={x.get('mergedAt')}" if state == "MERGED" else ""))
print("COUNTS " + " ".join(f"{k}={v}" for k, v in n.items()))
PY
```

**SELF** (read-only; `<wt>` is the lane worktree; `"$$"` is this shell). Prints `CLI <pid> cwd <path> in-lane
<yes|no|unknown>` for this session's own CLI process (`$CLAUDE_PID`); `TASKS <dir|unknown>`, the directory of this
session's Bash-tool output files (read from this shell's own stdout); then one `HOLDER <pid> <class> <command name>`
line per process `lsof +D` finds under `<wt>` (the same check `lane.sh reap` uses for `lane-busy`). The classes:
- `self-cli`: the CLI itself.
- `self`: descended from the CLI or this shell (its MCP servers, a background tool call), or writing its stdout or
  stderr into `TASKS`. The second test is what catches the common `(cd <wt> && cmd &)` idiom: its subshell is
  reparented to pid 1 at once, so ancestry alone would call it foreign.
- `unattributed`: reparented to pid 1, every process in its chain started after this CLI, and not writing into
  `TASKS`, e.g. this session's own background job with its output redirected, or another young session's orphan.
  SELF cannot tell which; M8 says how it is judged.
- `foreign`: its chain runs through a live process that is older than this CLI and is not this session (another
  session, a terminal, an app).
- `gone`: it exited before it could be classified.

With `CLAUDE_PID` unset, only this shell's descendants and `TASKS` writers are attributable; the rest print as
`unattributed`. SELF prints no environment and no command arguments, only command names.
```bash
python3 - <wt> "$$" <<'PY'
import os, subprocess, sys
if not sys.argv[1]:
    sys.exit("SELF: empty <wt>")
wt, shell, cli = os.path.realpath(sys.argv[1]), sys.argv[2], os.environ.get("CLAUDE_PID", "")
def out(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
def names(pid, fds):
    return [l[1:] for l in out("lsof", "-a", "-p", pid, "-d", fds, "-Fn").splitlines() if l.startswith("n")]
def secs(e):
    d, _, t = e.rpartition("-")
    h, m, s = ([0, 0] + [int(x) for x in t.split(":")])[-3:]
    return int(d or 0) * 86400 + h * 3600 + m * 60 + s
ps = {}
for l in out("ps", "-A", "-o", "pid=,ppid=,etime=,comm=").splitlines():
    f = l.split(None, 3)
    try:
        ps[f[0]] = (f[1], secs(f[2]), os.path.basename(f[3]))
    except (IndexError, ValueError):
        pass
def chain(pid):
    up = []
    while pid in ps and pid != "1" and pid not in up:
        up.append(pid)
        pid = ps[pid][0]
    return up
inside = lambda p, d: p == d or p.startswith(d + os.sep)
tasks = next((os.path.dirname(p) for p in names(shell, "1")
              if p.endswith(".output") and os.path.basename(os.path.dirname(p)) == "tasks"), "")
age = ps.get(cli, (None, None))[1]
cwd = cli and next(iter(names(cli, "cwd")), "")
print("CLI", cli or "unknown", "cwd", cwd or "unknown", "in-lane",
      ("yes" if inside(os.path.realpath(cwd), wt) else "no") if cwd else "unknown")
print("TASKS", tasks or "unknown")
for pid in out("lsof", "-t", "+D", wt).split():
    up = chain(pid)
    if pid == cli:
        c = "self-cli"
    elif pid not in ps:
        c = "gone"
    elif cli in up or shell in up or (tasks and any(inside(p, tasks) for p in names(pid, "1,2"))):
        c = "self"
    elif age is None or all(ps[q][1] < age for q in up):
        c = "unattributed"
    else:
        c = "foreign"
    print("HOLDER", pid, c, ps[pid][2] if pid in ps else "?")
PY
```

## 1. Preconditions and dry-run (in order)

- **P1 Argument.** `<n>` is required and all digits; `--abandon` and `--update` are each optional, and mutually
  exclusive — both given: stop; nothing called. Anything else not matching `<n> [--abandon | --update]`: stop;
  nothing called. **`--update` is a named, one-at-a-time hand-out, never a self-serve flag:** the coordinator names
  exactly one lane per repo as the current merge-slot holder — recorded on the repo's own `lane.tracking_issue`
  (`python3 ~/.claude/scripts/repo_manifest.py get lane.tracking_issue --repo <main>`; read the same optional,
  absence-tolerant way as at section 5, never hardcoded to any one repo's issue number — a repo with no
  `lane.tracking_issue` configured records the hand-out on whatever surface the coordinator already uses for that
  repo's lane table) — and tells that lane's own worker session to run `/lane-cleanup <n> --update`; no other
  session runs `--update` for any other lane while that hand-out stands. `--update` acts only in the IN-REVIEW cell
  (R1-R6 below); every other cell ignores it and reports that it was ignored.
- **P2 Main tree, before anything else (including before leaving a worktree).** Run MAIN. A `STOP` line: stop and
  report it. Then read:
  ```bash
  for k in github.repo github.project_number github.project_owner lane.base_ref lane.pr_target lane.max_open lane.max_abandoned lane.pick_source operator_input.kind operator_input.path operator_input.regen_command operator_input.open_path; do printf '%s = ' "$k"; python3 ~/.claude/scripts/repo_manifest.py get "$k" --repo <main> 2>&1; done
  ```
  A `key-missing` on any `github.*` or `lane.*` key: stop, naming it. **Also stop, reporting `bad-manifest`, when
  `lane.max_open` or `lane.max_abandoned` prints anything that is not all-digits** (`lane.sh`'s own test,
  `''|*[!0-9]*` — empty or containing a non-digit both fail it; mirrors `/lane-start`'s identical stop). `lane.max_open`
  and `lane.max_abandoned` are read here, not left to surface first at M8 or A3: `lane.sh reap` and `lane.sh abandon`
  both require these keys internally (`load_lane_cfg`), so a bad key found only there would mean M6 already closed
  the issue (in the MERGED path) before the reap that depends on the same manifest fails. Reading them at P2
  catches it before any mutation. Missing `operator_input.*` keys are allowed. `lane.tracking_issue` is read separately, only when
  needed, at section 5 (optional — its absence is a card, never a stop here).
- **P3 Leave the worktree.** Call ExitWorktree with action `"keep"` (ToolSearch `select:ExitWorktree` if needed).
  It restores the session's working directory when this session entered a worktree with EnterWorktree, and
  otherwise reports that no worktree session is active and changes nothing. Then run `pwd`. If it is under `/.claude/worktrees/`, run
  `cd <main>` (a plain `cd`: this one deliberately moves the session's shell) and check `pwd` again. `lane.sh reap`'s
  busy check (`lsof +D`) counts any process whose cwd is inside the lane: this shell, and also this session's CLI
  process and the processes it launched. Neither ExitWorktree nor `cd` can move a CLI that was LAUNCHED inside the
  lane; P4b checks for that once `<wt>` is known.
- **Dry-run reads** (read-only):
  1. `(cd <main> && bash ~/.claude/scripts/lane.sh status)`. It prints `ISSUE STATE ONDISK WORKTREE BRANCH` (a
     lane.sh from before L5.5 D4 prints only the first four columns). Example row:
     `#42      open       present  /.../.claude/worktrees/issue-42-fix-the-thing  issues/42-fix-the-thing`.
  2. LEDGER for `<n>`: `<state>` (the row's `event`), `<wt>`, `<branch>`, `owner`, `opened_ts`. The ledger row is
     the branch source. If a `BRANCH` column is present and disagrees with it, stop and report.
- **P4 No lane.** If `status` shows no `open`/`abandoned` row for `<n>`: report "no lane (already reaped or never
  opened)". No GitHub writes. Run the orphan check (section 5), then stop.
- **P4b Launched inside the lane.** Run SELF with `<wt>`. If its `CLI` line says `in-lane yes`, this session's CLI
  process (and every process it launched) holds the lane as its cwd, and `lane.sh reap` would refuse `lane-busy` on
  it. Stop before the GitHub reads and before any mutation, and report "this session was launched inside the lane;
  re-run `/lane-cleanup <n>` from a session launched in `<main>`". No card, and no orphan check (the re-run does
  it). If it says `in-lane unknown` (`CLAUDE_PID` unset, or the CLI's cwd unreadable), stop the same way when P2's
  `TOP` was inside `<wt>` and P3's ExitWorktree reported no active worktree session; otherwise continue, and say in
  the report that self-detection covered only this shell's descendants and `TASKS` writers.
- **More dry-run reads:**
  3. `gh issue view <n> --repo <r> --json state; echo "rc=$?"`
  4. PRSET with `<branch>`, the LEDGER `opened_ts` and `<pr_target>`. It runs
     `gh pr list --repo <r> --head <branch> --state all` itself and applies convention 10.
- **P5 Lookup failure.** If read 3 exits non-zero or does not parse as JSON, or PRSET prints `LOOKUP-FAILED` or
  `STOP` (exit 1): stop. Never treat it as an empty PR set (that would route `--abandon` over an open PR). No
  mutation. Orphan check, then stop.
- **P6 Filter.** PRSET's `KEPT` lines are the PR set. Its `IGNORED` lines (a fork head, another head, or a PR created
  before this lane's last open, i.e. an earlier lane's PR on the same reused branch name) are listed in the dry-run
  and never counted. `COUNTS` gives `M` = MERGED with `baseRefName == <pr_target>`; `X` = MERGED to any other base;
  `O` = OPEN; `C` = CLOSED (unmerged). An earlier lane's PR that is still OPEN never selects this run's cell, but it
  blocks the push and PR asks (section 6.1).
- **Print the dry-run report now, before any mutation:**
  ```
  lane-cleanup dry-run #<n>   main=<main>   flag=<--abandon|--update|none>
  lane:    <state> <present|missing> <wt>
  branch:  <branch> (ledger)   owner: <self|live-foreign|dead|unknown|released>
  issue:   <OPEN|CLOSED>
  PRs:     #<p> <STATE> base=<baseRefName> created=<createdAt> head=<headRefOid> [merge <sha>]   (one per KEPT line)
  ignored: #<p> <STATE> <reason>   (one per IGNORED line, e.g. "predates this lane (created <ts>; lane opened <ts>)")
  counts:  M=<> X=<> O=<> C=<>
  cell:    row <k> / <no flag|--abandon|--update> -> <ACTION>   modifiers: <P7> <P8>
  ```
- **P7 Issue CLOSED and `M = X = 0`.** Without `--abandon`: card "issue #<n> is closed while its lane is un-reaped"
  (recommending `/lane-cleanup <n> --abandon`), run the orphan check, and stop. With `--abandon`: continue to the
  matrix. Its ABANDON path then skips the board reset (A4), and an OPEN PR still gets REFUSE+CARD.
- **P8 Already abandoned (`<state>` is `abandoned`).** The `abandoned` row released the lane (LEDGER prints `owner`
  `released`): its `pid` is whichever session ran `lane.sh abandon`, so any session may finish the cleanup. The
  ABANDON cells (rows 1 and 3 with `--abandon`) run A3 (`reap --abandoned`, whose ancestry, clean-tree and
  lane-busy checks guard anything left in the lane, and whose refusals are carded) and A5 (only when A3 reaped the
  lane in this run). They skip A1 (there is no owner to check) and A2 (`lane.sh abandon` again would append a
  duplicate `abandoned` row with rc 0). A4 (the board reset, a read-then-transition, so it makes a reset the
  abandoning run did not make and posts nothing when the board is already reset) runs too, UNLESS P7 also applies
  (the issue is CLOSED): A4 is skipped under P7 exactly as it is for any other row, so a CLOSED issue whose row is
  `abandoned` runs only A3 and A5, and the board is never moved. Any existing card is reused (section 4). Rows 1
  and 3 WITHOUT `--abandon` stay IN-PROGRESS, report-only: an abandoned lane is reaped only when the caller passes
  `--abandon`, because `reap --abandoned` removes the worktree with its ignored files. MERGED, IN-REVIEW,
  REFUSE+CARD and STOP+CARD cells are unchanged.

## 2. Dispatch matrix (the kept PR set x the flag)

Each run lands in exactly one row. The rows are mutually exclusive and cover every combination of counts. `--update`
acts only in rows 2 and 4 (IN-REVIEW); in every other row it is ignored exactly as the report says (P1's own
mutual-exclusion with `--abandon` means a row is never evaluated against both at once).

| Row | M (merged to `<pr_target>`) | X (merged elsewhere) | O (open) | C (closed unmerged) | no flag | `--abandon` | `--update` |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | IN-PROGRESS | ABANDON | ignored (report) |
| 2 | 0 | 0 | >=1 | 0 | IN-REVIEW (see R1-R6 below) | REFUSE+CARD | IN-REVIEW, R1-R6 |
| 3 | 0 | 0 | 0 | >=1 | IN-PROGRESS (names the closed PRs; with the lane `open`, a board at `In review` goes back to `In progress`) | ABANDON (reason cites the closed PR numbers) | ignored (report) |
| 4 | 0 | 0 | >=1 | >=1 | IN-REVIEW (the open PR governs; R1-R6) | REFUSE+CARD | IN-REVIEW, R1-R6 |
| 5 | >=1 | any | 0 | 0 | MERGED | MERGED (flag ignored; say so) | MERGED (flag ignored; say so) |
| 6 | >=1 | any | 0 | >=1 | MERGED | MERGED (flag ignored; say so) | MERGED (flag ignored; say so) |
| 7 | >=1 | any | >=1 | any | MERGED; its M4 check normally fails and stops with a card | same (flag ignored) | same (flag ignored) |
| 8 | 0 | >=1 | any | any | STOP+CARD | STOP+CARD | STOP+CARD (flag ignored) |

Invariants: a MERGED PR to `<pr_target>` always beats `--abandon` or `--update`. An OPEN PR is never closed as a
side effect. Abandon runs only when the caller passes `--abandon` and no OPEN or MERGED PR exists. A PR closed
unmerged never abandons a lane by itself: it is often closed for rework, and an abandoned lane can no longer be
pushed or re-opened.
Only this lane's PRs count (convention 10); an earlier lane's PR on the same branch name never selects a cell. Every
cell ends with the section 4 card check and the section 5 orphan check.

## 3. The paths

### IN-PROGRESS (rows 1 and 3 with no `--abandon`)
Report-only: no resolve, reap, abandon or card. This cell runs identically whether the caller passed no flag at all
OR passed `--update` (rows 1 and 3 have no open PR to update, per the dispatch matrix's own "ignored (report)"
cells, so `--update` here is simply reported as ignored and the cell proceeds exactly as it would without
`--abandon`). The one board write these cells make is in row 3 with the lane `open` (below): a board still reading
`In review` from the closed PR goes back to `In progress`. No other transition.
- Row 1, lane `open`: "still in progress (no PR)". When the work is committed and ready, its push is asked for with
  section 6.1 (after the 6.0 hold check).
- Row 3, lane `open`: "PR #<p>[, #<q>] closed unmerged; the lane is still open". Name the two ways on and take
  neither: (a) rework: commit the fix in the lane, then a push through 6.1 and a replacement PR through 6.2 (both
  after the 6.0 hold check; the 6.2 card names the closed PR); (b) `/lane-cleanup <n> --abandon`. Then the board:
  read `<cur>` (convention 2). If `<cur>` is `In review`, move the issue to `In progress` and say so in the report:
  nothing is under review once the PR is closed, and a board left at `In review` is stale (runtime CLAUDE.md §8).
  Any other `<cur>` is left alone, and a failed read is reported with nothing moved. `/lane-start`'s resume treats
  `In progress` and `In review` alike, and a replacement PR's 6.2 step sets `In review` again.
- Lane `abandoned` (P8), row 1 or row 3: "abandoned, not reaped" (naming any closed PR), with no board write.
  `/lane-cleanup <n> --abandon`, from any session, reaps it or cards the reap's refusal, and makes any board reset
  the abandoning run did not make (A4).

### IN-REVIEW
Move the issue to `In review` (convention 2: when the board already reads `In review` no call is made, so a re-run
posts no second status comment) first, unchanged from before. Then the cell is a decision, R1-R6 in order, never
just a stop:

- **R1.** More than one `KEPT` OPEN PR: report, no card (6.2 allows one).
- **R2.** `git -C <main> fetch <remote> <base_branch>; echo "rc=$?"` (a failure: report, no card), then
  `gh pr view <p> --repo <r> --json headRefOid,mergeStateStatus,statusCheckRollup,isDraft`. `<L>` =
  `git -C <main> rev-parse refs/heads/<branch>`; `<H>` = `headRefOid`.
- **R3.** `<L>` differs from `<H>` and `git -C <main> merge-base --is-ancestor <H> <L>` is non-zero: the lane and the
  PR diverged; report, no card.
- **R4.** With `--update`, `mergeStateStatus` = `BEHIND`, and
  `git -C <main> merge-base --is-ancestor <base_ref> <L>` rc 1: run 6.4 (Update). A re-run after an update that was
  not yet pushed skips it via 6.4's own `SKIP` (the base is already in `<L>`) ONLY as long as the base has not moved
  again in the meantime — so a failed or declined push never causes a SECOND merge of the SAME base, but a base that
  genuinely moves forward again between runs is merged again on the next `--update`, exactly as intended (this is
  not a one-time-ever guarantee, only a same-base-twice guard).
- **R5.** `<L>` differs from `<H>` now (unpushed commits: a CI fix, or 6.4's merge commit): card the push through
  6.1 (after 6.0). The card also names the CI the push re-starts on the open PR (TRIGGERS with `<lane_head>` =
  `refs/heads/<branch>` and `<event>` = `pull_request`, as 6.2 does) at one full `ci.yml` run per push; once
  `ci.yml` cancels superseded runs on `<pr_target>`, a push also cancels the superseded run.
- **R6.** `<L>` = `<H>`, by `mergeStateStatus`:
  - `CLEAN` → 6.3 (its CI and UAT preconditions still apply).
  - `BEHIND` without `--update` → report "BEHIND: waiting for the merge slot", no card.
  - `BEHIND` with `--update` while `<base_ref>` is already in `<L>` (R4 skipped: `main` moved between R2's fetch and
    `gh pr view`, or GitHub's state is stale after a push) → report "GitHub reads BEHIND but `<base_ref>` is already
    in the lane; re-run `/lane-cleanup <n> --update` later", no card (the re-run's R2 fetch picks up the newer base,
    and R4 then runs).
  - `BLOCKED` (required checks pending or failing), `DIRTY` (conflicts with the base), `DRAFT`, `UNSTABLE`,
    `HAS_HOOKS` or `UNKNOWN` (GitHub still computing; re-run later) → report the value and the non-success checks, no
    card. A red required check is fixed in the lane with a new commit, and the next run reaches R5. (Whether GitHub
    reports `BEHIND` or `BLOCKED` for a PR that is both behind and failing is UNVERIFIED; either way the slot
    holder's run after its fix push reaches R4 once the PR reads `BEHIND`.)

**R6 decision table** (every `mergeStateStatus` GitHub's API documents, crossed with the flag — so no combination is
left undefined; `<L>` = `<H>` is R6's own precondition, so this table is read only once R1-R5 have already passed):

| `mergeStateStatus` | no `--update` | `--update` |
|---|---|---|
| `CLEAN` | → 6.3 | → 6.3 (R4 never fires: its own condition requires `mergeStateStatus` = `BEHIND`, and status is not `BEHIND`) |
| `BEHIND` | report "BEHIND: waiting for the merge slot", no card | R4 fires (base not yet in `<L>`) → 6.4; OR, if the base is already in `<L>` (R4 skipped), report "GitHub reads BEHIND but the base is already in the lane; re-run later", no card |
| `BLOCKED` | report the value + non-success checks, no card | same (report; `--update` does not bypass a failing/pending required check) |
| `DIRTY` | report the value, no card | same |
| `DRAFT` | report the value, no card | same |
| `UNSTABLE` | report the value, no card | same |
| `HAS_HOOKS` | report the value, no card | same |
| `UNKNOWN` | report the value (GitHub still computing), no card | same |

The lane stays open through every R1-R6 outcome; no reap happens from this cell.

### REFUSE+CARD (an open PR plus `--abandon`)
Mutate nothing: no `abandoned` row, no board move, no PR close. Card the open PR number(s) and the choice:
- close it: `gh pr close <p> --repo <r> --comment "<reason>"`, run only on approval of this card, then re-run
  `/lane-cleanup <n> --abandon`;
- merge it: through its own merge card (section 6.3);
- leave the lane open.

### STOP+CARD (row 8)
The PR(s) merged to a base other than `<pr_target>`, so the lane's intended landing has not happened. Nothing is
resolved or reaped. Card it (PR numbers, bases, merge shas) and stop.

### MERGED
- **M1.** The PRs merged to `<pr_target>` are the `KEPT` ones counted in `M`. Their merge shas are all cited; `<pr>`
  is the one with the latest `mergedAt`. Report `X` PRs and, in row 7, the open PR(s).
- **M2.** `git -C <main> fetch <remote> <base_branch>; echo "rc=$?"`, FIRST. A GitHub merge commit is not local until
  fetched. If the fetch fails: stop and report; nothing resolved.
- **M3.** For each PR counted in `M`: `gh pr view <p> --repo <r> --json mergeCommit --jq .mergeCommit.oid` gives `<sha>`.
  Then `git -C <main> cat-file -e <sha>^{commit}; echo "rc=$?"` and
  `git -C <main> merge-base --is-ancestor <sha> <base_ref>; echo "rc=$?"`. Any non-zero: stop and report.
- **M4. Pre-resolve precondition (read-only):**
  `git -C <main> merge-base --is-ancestor refs/heads/<branch> <base_ref>; echo "rc=$?"`. If it fails (row 7's open PR
  carrying commits not on the base, a squash merge, extra lane commits, or a missing branch ref), stop BEFORE resolve
  and card it. The issue is never closed on a lane whose tip has not landed. In row 7 with rc 0 (a stray open PR to
  another base), continue and report the stray PR.
- **M5. Pilot metric (adoption §7.6(d)), read-only.** Lead time = `<pr>`'s `mergedAt` minus the ledger
  `opened_ts`, both parsed with `datetime.strptime(<ts>, "%Y-%m-%dT%H:%M:%S%z")`, never subtracted or compared as
  strings. When it cannot be measured it is written `UNKNOWN`, never 0 and never an estimate. Print it in the report
  and carry it into M6. The skill does not compute CI minutes; the report prints this line verbatim:
  `CI minutes: measured by hand in L5.4 lane 1 (not computed by the skill)`.
- **M6. Close the issue.** The body follows CLAUDE.md §8: **What** (the change), **Why** (the issue, cited as
  `#<n>`), **How** (PR `#<pr>`; merge sha(s) restated), **Status** (merged to `<pr_target>` at `mergedAt`; lead
  time, or `UNKNOWN`).
  - Issue OPEN: in one call, `f=$(mktemp) && cat > "$f" <<'EOF'` ... `EOF`, then
    `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh resolve <n> --commit <sha> --body-file "$f"); rc=$?; rm -f "$f"; echo "rc=$rc"`,
    with one `--commit` per merge sha. If it fails: stop; no Done, no reap.
  - Issue already CLOSED (a lane PR body says `Refs #<n>`, never a closing keyword, but a lane commit message
    carrying one, e.g. `Fixes #<n>`, still closes the issue at merge; or someone closed it by hand): do not
    re-close. If no comment from
    `gh issue view <n> --repo <r> --json comments` cites the merge sha, post the same body with the helper's
    `comment` form. Then continue.
- **M7.** Move the issue to `Done` (convention 2), after M6 succeeds. Some boards auto-move on close and some do
  not; where one did, the read finds `Done` and no call is made. A failed read or move is retried once, re-reading
  `<cur>` before the retry (never blindly re-running the same transition). M8 always runs next regardless of
  whether the retry succeeded (the reap does not depend on M7). If the retry still fails: when M8 goes on to reap
  the lane in THIS run, `lane.sh status` no longer carries this issue afterward and no LATER `/lane-cleanup` run
  can retry the board move itself (P4, "no lane," is all a later run would find) — so THIS run ends by printing
  a conditional open item in A4's read-then-transition shape (never a bare command), with a Done condition:
  "re-read `<cur>`, and if it is not `Done`, run: `gh_issue.sh transition <n> --status Done ...`". When M8 does NOT
  reap in this run (any refusal), the lane still shows in `lane.sh status`, so a later `/lane-cleanup <n>` run can
  retry M7 itself with a fresh `<cur>` read — nothing is printed as an open item in that case, because one isn't
  needed yet.
- **M8. Reap** (P3 already ran; check `pwd` again): `(cd <main> && bash ~/.claude/scripts/lane.sh reap <n>); echo "rc=$?"`.
  Refusals are reported verbatim and never forced:
  - `needs-manual-reap`, `dirty-tree` (uncommitted work that never landed), `status-unverifiable`, `no-branch`: card
    it in the same turn (CLAUDE.md §2 case (d)). The worktree and branch remain.
  - **rc != 0 AND no line of the full output contains `REFUSED (`** (test the whole output, never just the last
    line: a `WARNING fetch of <base_ref> failed` line can print before the actual result, so "the line" is
    ambiguous — the test is "does `REFUSED (` appear anywhere") is `lane.sh`'s non-refusal `die` path (e.g.
    `git worktree remove failed for <wt> (NOT retried with --force, which is forbidden)`): every guard check
    already passed (ancestry, clean tree, nobody standing in it), but the actual removal command itself failed.
    Card it the same way, naming the exact output; a non-zero rc with no `REFUSED (` anywhere is never treated as
    success.
  - `lane-busy`: report the PIDs; kill nothing. Run SELF with `<wt>` and read each `HOLDER` class. `self-cli`: report
    it as in P4b, with no card. `gone`: ignore it. `unattributed`: compare its command name with the background
    commands this session started inside `<wt>`; one it recognizes counts as `self`, any other as `foreign`, and the
    report says the attribution was by command name. `self` only: `cd <main>` and retry once; if a `self` holder
    remains (e.g. a background command this session started inside the lane), stop and report it with no card, and
    re-run once it has ended. Card only when a `foreign` holder remains after that retry, naming only those PIDs.

### ABANDON
- **A1. Ownership** (the LEDGER `owner`; skipped under P8, where it reads `released`). `live-foreign` (a pid live on
  this host that is not this session's `$CLAUDE_PID`): refuse and report; let that session finish or hand off.
  Nothing mutated. `self`, `dead`, or `unknown` (a null pid, or a row from another host): proceed, and name it in the
  report.
- **A2.** `(cd <main> && bash ~/.claude/scripts/lane.sh abandon <n>); echo "rc=$?"`. Skipped under P8. A non-zero rc
  is reported verbatim; stop.
- **A3.** Immediately after (check `pwd` first): `(cd <main> && bash ~/.claude/scripts/lane.sh reap --abandoned <n>); echo "rc=$?"`.
  `--abandoned` asserts the state (plain `reap` would also reap an abandoned lane). rc 0: reaped this run. A
  refusal (`needs-manual-reap`, `dirty-tree`, `status-unverifiable`, `no-branch`, or `lane-busy` with a `foreign`
  holder) is carded in the same turn, naming the issue, the worktree and the reason. So is rc != 0 with no line of
  the full output containing `REFUSED (` (`lane.sh`'s non-refusal `die` path, e.g. `git worktree remove failed`
  after every guard check already passed), tested and named exactly as M8 handles the same shape. That is the ONLY case where
  an abandoned worktree survives the run, apart from a `lane-busy` whose holders are all this session's own. That
  one is classified with SELF exactly as in M8 (`unattributed` holders judged by command name): retry once after
  `cd <main>`; if only this session's own holders remain, report them with no card and continue at A4 (a later
  `/lane-cleanup <n> --abandon`, from any session, reaps it under P8).
- **A4. Board reset**, whether or not the reap succeeded (skipped under P7, where the issue is closed; it runs under
  P8; when both apply, a CLOSED issue whose row is `abandoned`, P7 wins and the board is not moved). Read `<cur>`
  (convention 2). `In progress`, `In review` or `Done` means the lane was worked (those are the
  statuses `/lane-start` step 13 and this skill set on a lane's issue): move the issue to `Backlog`, for either
  pick-source kind. A `label` pick source keeps its label, because it IS the queue; de-queueing (removing the label)
  is a sprint decision to report, never to make here. Any other `<cur>` (`none`, `Backlog`, or a queue status such
  as `Ready #1`) means the lane was never entered or the board is already reset: leave it and report `<cur>`. The
  rule reads only the board, never the reason for the abandon, so a P8 re-run reaches the same end state as the first
  run: it makes a reset the first run did not make, and posts nothing once the board reads `Backlog`. A failed read
  or move is reported the SAME conditional way in every branch, never as a bare command to run later: "re-read
  `<cur>`, and if it is still `In progress`, `In review` or `Done`, run:
  `gh_issue.sh transition <n> --status Backlog ...`" — a stale `<cur>` could have moved on since this run's read,
  and a bare `transition` would push a never-entered lane's issue off a queue status such as `Ready #1`. While the
  lane is still un-reaped, a later `--abandon` run (P8) retries the whole A4 step itself (its own fresh `<cur>`
  read, not the printed open item), so the open item from THIS run is reported but nothing later executes it
  blindly. If A3 reaped the lane in THIS run, no later run will retry A4 at all (the ledger's last row is then
  `reaped`, which is P4), so this run retries the conditional move once itself, re-reading `<cur>` before that
  retry too, and, if it still fails, ends by printing the same conditional open item — never a bare command —
  as its one open item: whoever executes it later must read-then-transition, never transition blindly.
- **A5.** Comment with the helper's `comment` form: the abandon reason (row 3 cites the closed PR numbers) and the
  worktree outcome (reaped, or kept plus the card number). Under P8 comment only when A3 reaped the lane in this run
  (one line: reaped, with the date); a repeated refusal updates the existing card instead (section 8, dedupe).

## 4. Earlier cards

Before the orphan check, search the open cards for this issue's lane: a dirty-tree or reap card from an earlier
run, a diff-gap card (title `Lane diff-gap: #<n>`), or a MULTI-lane card naming `#<n>` alongside other lanes — a
prune card (title `Lane prune (abandoned-backlog): <repo>`) or a stuck-lane card (title `Lane stuck: <repo>`),
both from `/lane-start`'s card procedure. An orphan card (`Lane orphans: <repo>`) is left to section 5.

**Classify by the card's TITLE PREFIX, never by counting `refs` entries.** A `decisions_json` card's `refs` count
would distinguish single- from multi-lane, but `decisions_markdown` (the surface CSA uses) carries no `refs`
field at all — only `decisions_json` has one — so a `refs`-counting rule silently fails to classify anything on
that surface. The three fixed repo-level prefixes (`Lane prune (abandoned-backlog): <repo>`, `Lane stuck: <repo>`,
`Lane orphans: <repo>`) and the per-issue diff-gap title (`Lane diff-gap: #<n>`, matched as the WHOLE title, never as a prefix, so `#12`
never matches `#123`) are present on both surfaces
(the `decisions_markdown` branch's `### [N] <title>` heading carries the same prefix), so title-prefix matching
works everywhere `refs`-counting cannot.

- **Single-issue card** (no fixed repo-level prefix — a dirty-tree/reap/tip-not-landed/closed-while-un-reaped
  card from THIS skill's own card procedure, or `/lane-start`'s per-issue `Lane diff-gap: #<n>` card). If this
  run changed the condition it describes, update it with a
  dated note. If the condition no longer holds, resolve it with the Resolve command below (an honest non-verbatim note such as
  "resolved by agent action: reaped <date>"; the archive command moves it).
- **Multi-lane card** (title starts with one of the three fixed repo-level prefixes). This run resolving `#<n>`'s own condition
  (e.g. `/lane-cleanup <n> --abandon` reaping lane `<n>`) does NOT mean the card's overall condition no longer
  holds — `#<m>` and any other lane still on the card may hold unlanded work the operator still needs to decide
  on, even though the count that originally triggered the card has dropped. Never archive a multi-lane card just
  because ITS OWN triggering count (e.g. the abandoned-lane count, or the stuck-lane count) is now under the cap:
  a card exists to get a decision on each NAMED lane, not on a count. `Lane orphans: <repo>` cards are owned by
  section 5 alone: section 4 never removes lanes from them or resolves them. For prune and stuck cards, and only
  when THIS run reaped or resolved `#<n>`:
  1. `decisions_json`: remove `#<n>` from the card's `refs` and append a dated note recording what happened to it (the body's
     original lane list stays as history; the note is the record of the removal) (e.g. "`#<n>` reaped <date>, removed from this card"). Edit ONLY through `json.loads`/
     `json.dumps`, exactly matching `decisions_rules.md`'s byte contract (`indent=1`, `ensure_ascii=False` — this
     repo's live `decisions.json` contains at least one non-ASCII character today, so a plain `json.dumps(d,
     indent=1)` without `ensure_ascii=False` does not round-trip it and `_validate_json_formatting`
     hard-fails the regen and the pre-commit hook), never a raw-text edit:
     The generator has no subcommand for editing an existing card, so this hand edit follows `decisions_rules.md`'s
     "Hand-editors" paragraph: it takes the generator's `.hub.lock` flock and reads the files only AFTER taking it,
     VALIDATES the result with the generator's own `_validate_decisions_schema` before anything is written, and
     writes through the generator's `_write_json_atomic`. A body that breaks the Markdown rules leaves the file
     untouched and prints the validator's message instead; fix the text and re-run. The note goes in a QUOTED
     heredoc file, never a command-line or JSON string:
     ```bash
     u=$(mktemp) && cat > "$u" <<'EOF'
     Dated update: #<n> reaped <date>, removed from this card.
     EOF
     python3 - <path> <main> <existing card no> "$u" '#<n>' <<'PY'
     import fcntl, importlib.util, json, os, sys
     from pathlib import Path
     p, main, no, uf, remove_ref = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
     assert os.path.isabs(p) and os.path.isabs(main) and p.startswith(main + os.sep), "need the ABSOLUTE <path> inside <main>"
     hub = os.path.dirname(p)
     lk = open(os.path.join(hub, ".hub.lock"), "a"); fcntl.flock(lk, fcntl.LOCK_EX)  # the generator's lock; read only AFTER taking it
     spec = importlib.util.spec_from_file_location("gen_operator_hub", os.path.join(main, "scripts", "gen_operator_hub.py"))
     g = importlib.util.module_from_spec(spec); sys.modules["gen_operator_hub"] = g; spec.loader.exec_module(g)
     d = json.loads(open(p, encoding="utf-8").read())
     arch = json.loads(open(os.path.join(hub, "decisions_archive.json"), encoding="utf-8").read())
     card = next(c for c in d["open_cards"] if c["no"] == no)
     if remove_ref in card["refs"]:
         card["refs"].remove(remove_ref)
     card["body_md"] = card["body_md"].rstrip() + "\n\n" + open(uf, encoding="utf-8").read().strip()
     try:
         g._validate_decisions_schema(d, arch)
     except SystemExit as e:
         sys.exit(f"NOT WRITTEN, {p} untouched: {e}")
     g._write_json_atomic(Path(p), d)
     print(f"updated #{card['no']}, refs now {card['refs']}")
     PY
     rc=$?; rm -f "$u"; echo "edit rc=$rc"
     ```
     `decisions_markdown`: no `refs` exist. Just append the dated removal note to the `### [N]` entry's body, in
     place with the Edit tool, as `/lane-start`'s card procedure does for markdown.
  2. Archive the card only when NO named lane still needs it — i.e. after this removal, `refs` is empty (on
     markdown: the entry's lane list, minus the lanes its removal notes cover, is empty), or every
     remaining named lane has itself already been independently resolved and only has not yet been removed from
     the list. A card with even one lane still genuinely needing an operator decision stays open.
     **Resolve command** (`decisions_json` only. For `decisions_markdown`, the session edits
     the file itself per `/lane-start`'s card-procedure step 3 markdown rule). Archive the card with the
     generator's own `archive` command (`decisions_rules.md` Lifecycle step 2); never move a card between
     `decisions.json` and `decisions_archive.json` by hand. The command keeps the card's number, validates and
     writes both data files, and regenerates both `.md` files. **`archive` DROPS the open card's `body_md`** (its
     dated updates and removed-lane notes), keeping only title, dates, refs and the resolution text, so this
     skill carries the body forward: the resolution file is written with a QUOTED heredoc (so backticks and
     `$VAR` in the text stay literal and never execute), then the card's current body is appended to it under a
     bold **History** line before archiving. Run it from `<main>` (`<regen_command>` is root-relative:
     `python3 scripts/gen_operator_hub.py`); `--new-batch-label` mints the next batch number (`--batch N` joins
     an existing batch), and without `--verbatim` the resolution is recorded as a non-verbatim note. Pass free
     text ONLY through the `--resolution-file`; the batch label is built from fixed text and a number, so it goes in
     SINGLE quotes and never takes untrusted text. The History step and `archive` are chained: if the History step
     fails (card not open, file unreadable) `archive` does NOT run. The resolution file is deleted only after
     `archive` succeeds. **If `archive` exits non-zero the card is still open and `$r` still holds the text: fix
     the resolution text and re-run the whole block** (a new temp file is made; delete the old one). The History
     step takes a shared flock on `.hub.lock` while it reads the open card, so it never reads a half-written
     file; `archive` then takes its own exclusive lock:
     ```bash
     r=$(mktemp) && cat > "$r" <<'EOF'
     Dated resolution: resolved by agent action, ...
     EOF
     python3 - <path> <existing card no> "$r" <<'PY'
     import fcntl, json, os, sys
     p, no, rf = sys.argv[1], int(sys.argv[2]), sys.argv[3]
     assert os.path.isabs(p), "need the ABSOLUTE <path>"
     lk = open(os.path.join(os.path.dirname(p), ".hub.lock"), "a"); fcntl.flock(lk, fcntl.LOCK_SH)  # read the card only AFTER taking the lock
     card = next(c for c in json.loads(open(p, encoding="utf-8").read())["open_cards"] if c["no"] == no)
     with open(rf, "a", encoding="utf-8") as f:
         f.write("\n\n**History (the card's body when it was archived)**\n\n" + card["body_md"].strip() + "\n")
     PY
     if [ $? -eq 0 ]; then
       (cd <main> && <regen_command> archive <existing card no> --resolution-file "$r" \
         --new-batch-label '<YYYY-MM-DD>: /lane-cleanup resolved #<existing card no>') && rm -f "$r"; echo "archive rc=$?"
     else
       echo "History step failed: archive NOT run, the card is still open, resolution text kept in $r"
     fi
     ```
     The `archive` command regenerates itself. After the update snippet above, run
     `(cd <main> && <regen_command>); echo "regen rc=$?"`. Either way, `open <open_path>` (or
     `open <path>` if the manifest sets no `open_path`), exactly as `/lane-start`'s card procedure step 4 does.

Never leave a card stale either way.

## 5. Orphan check (always last)

`(cd <main> && bash ~/.claude/scripts/lane_orphans.sh); echo "rc=$?"`, in every matrix cell and after every
precondition stop from P4 on except P4b. Report the rc and every line verbatim.
- **rc 1:** ALWAYS card the findings (`orphan-worktree` and `dead-owner` are operator decisions per the script
  header — this is what actually reaches the operator, in the same turn, per runtime CLAUDE.md §11 and the
  repo's own operator-hub rule; a comment alone does not), using the `Lane orphans: <repo>` title prefix and
  dedupe rules from `/lane-start`'s card procedure (steps 2-4), naming every lane an actual finding cites in
  `refs` (never a lane the findings don't name). If an open `Lane orphans: <repo>` card already exists, REPLACE
  its findings list with this run's current findings using `/lane-start`'s card-procedure step 3 orphan replace
  snippet (never merge-only-add — a finding that no longer reproduces no longer belongs on the card); report its
  number. A new card here uses `/lane-start`'s template with `asked_by` `/lane-cleanup (<session>)`.
  ADDITIONALLY, only when this run created the card or changed its findings list, and when
  `python3 ~/.claude/scripts/repo_manifest.py get lane.tracking_issue --repo <main>` resolves to an integer, also
  comment the same findings on that issue — never instead of the card, never a hardcoded
  number, never a different repo's issue. If the key is absent (`key-missing`) or not an integer, the card alone
  is the findings' record.
- **rc 0** (clean): if an open `Lane orphans: <repo>` card exists, RESOLVE it with the Resolve command in section 4
  (an honest non-verbatim note, e.g. "resolved by agent action: `lane_orphans.sh` reports clean as of `<date>`"). No card
  exists: nothing to do.
- **rc 2:** report an environment error; no card action either way.

## 6. Ship asks: push, PR, merge

Each is its own card showing the exact command. The command runs only after the operator explicitly approves THAT
card (runtime CLAUDE.md §4, §11). An approval never carries over to the next push, PR or merge.

**6.0 Standing hold check (read-only), before carding 6.1, 6.2, 6.3, or before 6.4 runs.** Hub card 53 set the per-action ask; a later
operator ruling can suspend it, and carding a push or PR during a hold re-asks a question the operator has already
answered. Lane rulings are cross-repo: a ruling recorded on one repo's operator surface covers every lane-enabled
repo unless it scopes itself to one (card 53's own answer is recorded on one repo's hub and was taken to cover both
lane-enabled repos). So the search covers the operator surface of `<main>` and of every lane-enabled repo in the
machine's repo registry (`~/.claude/knowledge/repo_registry.json`, or `$CLAUDE_DIR/knowledge/repo_registry.json`),
open cards and archive alike. A repo is lane-enabled when its manifest has `lane.base_ref`; every manifest value is
read with `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo <root>`:
```bash
python3 - <main> <<'PY'
import json, os, re, subprocess, sys
main = os.path.realpath(sys.argv[1])
reg = os.path.join(os.environ.get("CLAUDE_DIR") or os.path.expanduser("~/.claude"), "knowledge", "repo_registry.json")
roots = [main]
try:
    for e in json.load(open(reg, encoding="utf-8"))["repos"].values():
        roots.append(os.path.realpath(os.path.expanduser(e["root"])))
except FileNotFoundError:
    print(f"REGISTRY absent ({reg}): only {main} is searched")
except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
    print(f"STOP registry {reg} unreadable ({type(e).__name__})")
    sys.exit(1)
def get(repo, key):
    p = subprocess.run(["python3", os.path.expanduser("~/.claude/scripts/repo_manifest.py"), "get", key, "--repo", repo],
                       capture_output=True, text=True)
    return (p.stdout.strip(), "") if p.returncode == 0 else ("", (p.stderr.strip().splitlines() or ["?"])[0][:200])
flat = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
def cards(kind, path, ap=None):
    out = []
    if kind == "decisions_json":
        # open cards live in decisions.json, closed cards in the sibling decisions_archive.json
        for st, f in (("open_cards", path), ("archived_cards", ap)):
            if not f:
                continue
            d = json.load(open(f, encoding="utf-8"))
            for c in d.get(st, []):
                out.append((c.get("no") or 0, st[:-6], " ".join(flat(c.get(k)) for k in
                            ("title", "summary_md", "body_md", "resolution_md") if c.get(k))))
    else:
        t = open(path, encoding="utf-8").read()
        arch = t.find("\n## Archived")
        for m in re.finditer(r"^### \[(\d+)\].*?(?=^### \[|^## |\Z)", t, re.M | re.S):
            out.append((int(m.group(1)), "archived" if -1 < arch < m.start() else "open", flat(m.group(0))))
    return out
lane = re.compile(r"\blanes?\b", re.I)
ship = re.compile(r"\b(push(es|ed)?|PRs?|pull requests?|merges?)\b", re.I)
hold = re.compile(r"\b(hold|held|pause[ds]?|freeze|frozen|halt(ed)?|suspend(ed)?|until)\b|\bno (lane )?(push|PR)", re.I)
rc = 0
for root in dict.fromkeys(roots):
    _, err = get(root, "lane.base_ref")
    if err:
        bad = not err.startswith(("key-missing", "manifest-missing"))
        print(f"{'UNREADABLE' if bad else 'SKIPPED'} {root}: {err}")
        rc = rc or int(bad)
        continue
    (kind, _), (path, _) = get(root, "operator_input.kind"), get(root, "operator_input.path")
    if kind not in ("decisions_json", "decisions_markdown") or not path:
        print(f"NO-SURFACE {root}: operator_input.kind={kind or 'missing'}")
        rc = rc or int(root == main)
        continue
    ap = None
    if kind == "decisions_json":
        arel, aerr = get(root, "operator_input.archive_path")
        if aerr and not aerr.startswith("key-missing"):
            print(f"UNREADABLE {root}: operator_input.archive_path: {aerr}")
            rc = 1
            continue
        ap = os.path.join(root, arel) if arel else os.path.join(os.path.dirname(path), "decisions_archive.json")
    try:
        cs = cards(kind, path, ap)
    except (OSError, ValueError, AttributeError) as e:
        print(f"UNREADABLE {root}: {path}{' + ' + ap if ap else ''} ({type(e).__name__})")
        rc = 1
        continue
    hits = [c for c in cs if lane.search(c[2]) and ship.search(c[2]) and hold.search(c[2])]
    for no, st, body in sorted(hits, key=lambda c: -c[0]):
        print(f"CANDIDATE {root} #{no} {st}: {body[:700]}")
    print(f"SEARCHED {root} ({kind} {path}{' + ' + ap if ap else ''}): {len(cs)} cards; {len(hits)} candidates")
sys.exit(rc)
PY
```
A `decisions_json` repo is searched across BOTH its open file and its archive file; if the archive file does not exist yet
the repo reports `UNREADABLE` (rc 1) until one exists, because a half-searched surface must never read as "no hold".
Read every `CANDIDATE`, newest first on each surface; the search is by keyword, so many are unrelated. A `CANDIDATE`
line shows only a card's first 700 characters: read the card itself whenever its scope or date may lie past that.
A hold STANDS when the most recent operator ruling that addresses lane pushes, PRs or merges,
on ANY searched surface, holds or suspends them and no later ruling lifts it. Order rulings by their own dates, never
by card number (numbers are per surface). A ruling binds this repo's lanes wherever it is recorded, unless its own
words scope it to another repo only. An open card still asking that question, on any surface, is not a ruling, but
it is the same question: refer to it instead of adding a card. In either case post no push, PR or merge card; report
`push/PR held by <repo> #<card>: <the ruling's own words>` (or `pending <repo> #<card>`), naming the surface the
binding hold came from, and go on to the rest of the run (the section 4 card check and the section 5 orphan check
still run). This is never assumed from a prior run or from memory: the search above runs fresh every time 6.1, 6.2
or 6.3 is about to card, because a hold can be lifted or a new one recorded between runs. Example of the shape a
`CANDIDATE` takes (not a claim about the CURRENT state, which the live search alone determines): Agency hub #57
(operator, verbatim: "hold on the pr for now"), opened 2026-09-24, reads as holding lane pushes and PRs in every
lane-enabled repo, since it names no repo, until the CI-efficiency work lands; a card like it, if still the newest
ruling found, means the run reports the hold and cards nothing. `SKIPPED` lines (a registry repo with no manifest or no `lane` block, so not lane-enabled) and a
`NO-SURFACE` line for another repo (nothing recorded there to search) are listed in the report and change nothing.
Exit 1 means the check could not be completed, and no push, PR or merge card is posted: `STOP` (the registry is
unreadable) or `UNREADABLE` (a lane-enabled repo's manifest or surface could not be read) is reported as such, and
`NO-SURFACE` for `<main>` itself means no card can be posted here at all, so list the ask as UNASKED (section 8).

**6.1 Push.** Read-only preconditions, checked before carding. If any fails, report it and post no push card:
- 6.0 finds no standing hold;
- the ledger row is `open`;
- `git -C <wt> status --porcelain; echo "rc=$?"` is empty with rc 0;
- `git -C <wt> rev-list --count <base_ref>..HEAD` is at least 1;
- `git -C <wt> rev-parse --abbrev-ref HEAD` equals `<branch>`;
- PRSET (this run's dry-run lines, or a fresh run) shows no `IGNORED` PR from an earlier lane that is still OPEN. A
  push to the reused branch name would feed that old PR, so card its close instead (REFUSE+CARD's close form, run
  only on approval of that card);
- `lane.prepush_check`, if the manifest carries the key at all, resolves to a VALID object (below). An invalid
  object fails this precondition closed: report it and post no push card, exactly like any other failed precondition.

**The pre-push check is optional and repo-specific — read from the manifest, never hardcoded.** A new OPTIONAL
manifest object, `lane.prepush_check`, names it; a repo without the key runs no pre-push check at all (this is
`/lane-cleanup`, a RUNTIME skill shared by every lane-enabled repo — its own local-CI/dependency-freshness tooling
is never baked into this file). Read it the same tolerant way `lane.sh` reads `lane.link_paths` — never via a helper
that refuses on a missing key, and never `2>&1` (which would fold a real error into stdout and be mistaken for a
value): capture stdout and the exit code separately, `2>/dev/null` discarding stderr:
```bash
raw=$(python3 ~/.claude/scripts/repo_manifest.py get lane.prepush_check --repo <main> --raw 2>/dev/null); rc=$?
```
`rc != 0` (a `key-missing`, or any other `repo_manifest.py` failure) means: skip the check entirely and report
"pre-push check: none configured" — never a stop, never a card. When `rc == 0`, `$raw` must be a JSON object with
exactly four non-empty STRING fields: `venv` (a repo-relative directory containing the two executables the check
invokes — a Python interpreter and the dependency-audit tool), `freshness_script` (a repo-relative path to the
dependency-freshness-check script, run through `<venv>`'s own interpreter, never on its own `PATH`), `lock_dir` (a
repo-relative directory to run the dependency-audit tool from) and `lock_file` (the lockfile name, relative to
`lock_dir`). One example, illustrative only, never assumed to be the value any given repo actually carries: a repo
whose local CI uses a project-local venv and a pinned lockfile might set `{"venv":
"<backend-dir>/.venv_ci", "freshness_script": "scripts/ci/check_venv_freshness.py", "lock_dir": "<backend-dir>",
"lock_file": "requirements.lock"}`.

**Validate `lane.prepush_check` the same way `lane.sh` validates a `lane.link_paths` entry (never trust it
unchecked, since it is manifest-authored, repo-specific data, not this skill's own literal text):** each of the four
fields must be present, a non-empty string, not absolute, contain no `..` segment, contain no glob character (`*
? [ ]`), not start with `#`, `!` or `-`, and contain no whitespace. **Additionally, `venv` must also appear, byte-
for-byte, as an entry in that same repo's `lane.link_paths` array** — the freshness/audit check is run from inside
`<wt>`'s own linked copy of `venv` (never a fresh clone of it), so if `lane.sh` was never told to link that path
into the lane in the first place, `<wt>/<venv>` does not exist and the check cannot run there at all; failing this
cross-check closed, rather than silently trying to run against a path that was never linked, is what surfaces a
manifest authoring mistake at read time instead of as an opaque "no such file" later. **Any of these validation
failures — a missing/non-string field, an unsafe path shape, or `venv` absent from `lane.link_paths` — fails CLOSED:
report exactly what failed and post NO push card**, the same as any other failed 6.1 precondition; never fall back
to running the push without the check, and never silently skip the check as if `lane.prepush_check` were absent
(absent and invalid are different conditions and are reported differently — "none configured" vs. the specific
validation failure). Read `lane.link_paths` for the cross-check the same tolerant way (`--raw 2>/dev/null` plus its
own exit code); a repo with a `lane.prepush_check` but no `lane.link_paths` at all fails this cross-check the same
way an absent `venv` entry would.

**Immediately before the pre-push check call (not before the whole precondition list — this is a live liveness
check, not a static validation, so it must be as fresh as possible), and only once `lane.prepush_check` has
validated:** confirm no other process is currently running local CI or pytest against `<main>`'s own venv, using a
pattern that also matches a LANE's linked copy of it (the linked path contains the main venv's path as a substring,
so anchoring the pattern on the shared suffix catches either): `pgrep -f "/<venv>/bin/python"` and `pgrep -f
"local_ci.sh"`. Either printing a pid means something is mid-run against that venv. This check exists because the
venv-freshness fix below (when it runs) edits `<main>`'s OWN venv, which the lane's `venv` is a symlink into —
racing a real test/CI run with that edit would corrupt what that run reads mid-flight. If either `pgrep` prints a
pid, wait for it to end; never proceed under it, and never skip the check because waiting is inconvenient.

**Immediately before the push call, after this card's own approval and on the SAME approval (never spending it
twice), and only when `lane.prepush_check` resolved to a valid object:** one read-only call, run from `<wt>` (the
lane's own linked venv, per `lane.link_paths` — quoting every value substituted into the shell, since these are
manifest-authored strings, not this skill's own literal text), as its own Bash call:
```bash
V="<wt>/<venv>/bin"
"$V/python3" "<wt>/<freshness_script>" --venv-python "$V/python3" && (cd "<wt>/<lock_dir>" && "$V/pip-audit" -r "<lock_file>" --disable-pip)
```
Neither the freshness-check script nor the dependency-audit tool is on `PATH` from `<wt>` — both must be invoked
through the lane's own linked venv's `bin/`, by absolute path, exactly as shown; there is no repo-root lockfile,
only the one under `<lock_dir>` — never assume either resolves bare. **Before running this call at all, check
whether the lane's own commits touch the dependency files themselves:** `git -C <main> diff --quiet HEAD <branch>
-- "<lock_dir>/"; echo "rc=$?"`. `rc == 0` means the lane changes nothing under `<lock_dir>` (the normal case) — the
check proceeds as below. `rc != 0` means the lane's own branch DOES change something under `<lock_dir>` — the
freshness/audit check is skipped, and so is any fix: report "lane changes dependencies; fix belongs on the train"
and card it (the shared venv is `<main>`'s own, so a lane that is deliberately editing dependencies must land that
change on the train first, never have this automated check silently override or fight it); no `pip install` runs in
that case. `rc` other than 0 or 1 (a `git diff` failure) is a precondition failure like any other: report it, no
card, no fix.

The dependency-freshness script has no auto-fix flag of its own (it is read-only; a venv-python argument is its only
input): on a FAIL it prints its OWN exact remediation command on stderr, naming the real requirements files for
this repo — never construct that command by hand or guess the paths; copy it VERBATIM from the FAIL output,
substituting only its interpreter argument for `<main>/<venv>/bin/python3` (never the lane's own linked venv — the
fix runs against `<main>`'s own venv, since the lane's is a symlink into it and fixing `<main>`'s venv fixes what
the lane sees too). Apply this fix ONLY when the `git diff --quiet` check above returned `rc == 0` (the lane changes
no dependency files); re-run the `pgrep` liveness check immediately before running the fix (it may have gone stale
during any wait), then run the copied fix command, then re-run both checks from `<wt>` before retrying the push —
still on this same approval. A dependency-audit finding goes to a named owner, same as card A's rule (the
dependency-audit tool has no analogous self-fixing command; a dependency-version bump is reviewed like any other
change). If the push itself still returns a local-CI failure whose blocking-failure list names ONLY the configured
venv-freshness check and/or the configured dependency-audit check, that failure also routes through this same fix
(gated by the same `git diff --quiet` check), never through a lane defect-fix cycle. When `lane.prepush_check` is
absent (not merely invalid — an invalid object already failed 6.1's precondition list above and never reaches this
point), this whole section is skipped and the report says so; nothing else about 6.1 changes.

The card's command is FOUR Bash calls when `lane.prepush_check` is absent, or FIVE when it is configured and
validates (the pre-push check above is its own separate call, drawn as its own step below — never folded into the
push call itself — run only in the configured case; the push-mechanics calls below run either way), by the session
that holds the card (the main session keeps its working directory between Bash calls; a delegated sub-agent does
NOT, so never hand the push to a sub-agent). The push itself runs with `run_in_background: true`, followed by a
`Monitor` until-loop that waits on it; `cd <main>` runs only after the Monitor loop ends (a repo's own pre-push
local CI can run tens of minutes, longer than a foreground Bash call's 10-minute cap). The push call is never
wrapped (no `/usr/bin/time`, no `git -C`), so the harness `ask` for `git push` still fires on it. While the push
runs, the lane cannot be reaped (`lane.sh reap` would refuse `lane-busy`), which is expected and not itself a fault
to fix. **Nothing else runs in this session's shell between the push call starting and the final `cd <main>`** — the
shell's working directory is mid-transition for that whole window, so a call issued in between would run from an
unpredictable cwd:
```
# (when lane.prepush_check validates) call 1, from <wt>, own Bash call:
V="<wt>/<venv>/bin"
"$V/python3" "<wt>/<freshness_script>" --venv-python "$V/python3" && (cd "<wt>/<lock_dir>" && "$V/pip-audit" -r "<lock_file>" --disable-pip)

# then, always, the push mechanics:
cd <wt>
git rev-parse --show-toplevel
git push -u <remote> <branch>      # run_in_background: true; Monitor until it ends
cd <main>                           # after the Monitor loop ends
```
- The `rev-parse` call must print exactly `<wt>`; if it prints anything else, do not push: `cd <main>` and card it.
- The push runs FROM the lane (`cd <wt>` first), so the shared pre-push hook resolves its repo root, its local-CI
  target and its branch-name gate to the lane's branch and tree, not the main tree's work branch.
- The push call itself starts with `git push`, so a repo's harness rule on `git push` (e.g. an
  `ask: Bash(git push:*)` permission, or a `--force` deny) applies to it. Never use `git -C <wt> push` or a compound
  `cd <wt> && git push ...`: those do not start with `git push` and could skip that rule.
- Always run the final `cd <main>`, even when the push fails, so later steps run from the main tree.
- No `--force`, no `--no-verify`, no `SKIP_*` env.
- The lane's branch gate rejects the branch: stop and card it; never bypass it.
- A pre-push failure that is not the configured-venv-check shape above: fix it in the lane (a new commit), then post
  a NEW push card. A fix-forward push is its own ask.
- **Reading the Monitor's result once it ends:** the push call's own exit code (0 = the push landed; non-zero =
  refused or failed) is the first signal. When non-zero, read the push's captured output for the pre-push hook's own
  failure banner and the lines beneath it naming exactly which check(s) failed (this is what the routing above
  matches against) — never guess the failure from the exit code alone. A push whose Monitor ends with exit 0 but
  whose output shows no confirmation line is treated as UNCONFIRMED, not success: compare `git -C <main> rev-parse
  refs/heads/<branch>` against `git ls-remote <remote> <branch>`'s sha (never `--abbrev-ref HEAD`, which names a
  branch, not a commit, and proves nothing about what the remote actually received) to verify the remote branch
  actually advanced to the lane's own tip before reporting the push as done.

This same push-call shape (background, Monitor, `cd <main>` after, the pre-push venv-freshness/dependency-audit
check immediately before when `lane.prepush_check` validates) applies to every push this skill cards, including
6.4's update-triggered push in R5.

**6.2 PR**, carded separately after the push succeeds, and only when 6.0 finds no standing hold. First re-run PRSET
(convention 10). Card 53 allows ONE PR per lane: a `KEPT` OPEN or MERGED PR means no new PR, and a `KEPT` CLOSED one
is named in the card before a replacement is asked for. An earlier lane's PR (`IGNORED ... predates this lane`) never
counts toward that one PR; one that is still OPEN blocks the card as in 6.1.

The card states the CI the PR will start (each run bills runner-minutes). First
`git -C <main> fetch <remote> <base_branch>; echo "rc=$?"` (a failure: stop and report, with no card). Then confirm
that `git -C <main> rev-parse refs/heads/<branch>` equals `git -C <main> rev-parse <remote>/<branch>` (the head just
pushed; if not, stop and report, with no card), and run TRIGGERS (section 6.3) with `<lane_head>` =
`refs/heads/<branch>` and `<event>` = `pull_request`. A `pull_request` run reads the workflow files of the PR's
merge ref, the merge of the PR head into the base, and TRIGGERS derives from exactly that merge. Name every line it
prints on the card. An `UNKNOWN` line, an `ERROR` line or any other non-zero exit: report it verbatim, with no card.

The body references the issue as `Refs #<n>` and carries no closing keyword for it, so the PR itself never closes the
issue; M6's resolve, which verifies the merge sha, normally does. Before carding, check the body file for the three
closing-reference forms GitHub accepts (`#<n>`, `<r>#<n>` and the issue's URL) with
`grep -niE '\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b:?[[:space:]]+(#<n>|<r>#<n>|https?://github\.com/<r>/issues/<n>)\b' <f>`:
it must print nothing (if it prints a line, rewrite the body). The issue can still close without M6: a lane commit
message carrying such a keyword (the runtime commit shape's `Fixes #<n>`, for example) closes it when the merge lands
on the repo's default branch (GitHub documents that for commits as well as PR bodies), and anyone can close it by
hand. Run the same `grep` on `git -C <wt> log --format=%B <base_ref>..HEAD`; if it matches and `<pr_target>` is the
default branch (`gh repo view <r> --json defaultBranchRef --jq .defaultBranchRef.name`), the card says the merge
will close #<n> itself. Either way M6's already-CLOSED branch then posts the completion comment. The command
(`--head` is mandatory):
```
gh pr create --repo <r> --base <pr_target> --head <branch> --title "<title>" --body-file <f>
```
Right after it succeeds, move the issue to `In review` (convention 2); do not wait for the next run.

**6.3 Merge**, carded only when 6.0 finds no standing hold and all of these hold:
- `mergeStateStatus` = `CLEAN`, read in the same `gh pr view` call as the CI check below. Never a merge card on any
  other value. R6's `CLEAN` branch is the normal entry point, so this precondition is usually already satisfied by
  the time 6.3 is reached; it is restated here because 6.3 has a SECOND entry point that never passes through R6 at
  all: REFUSE+CARD's own "merge it" option (an open PR plus `--abandon` — the flag is refused rather than routed
  through R6, and the card it posts instead offers a 6.3 merge card as one of the operator's choices). A fresh,
  unread run of 6.3 must therefore re-check `CLEAN` itself, never assume the earlier read still holds;
- CI is green: `gh pr view <pr> --repo <r> --json state,headRefOid,mergeStateStatus,statusCheckRollup` shows a
  non-empty `statusCheckRollup` in which every check run is `COMPLETED` with conclusion `SUCCESS`, `NEUTRAL` or
  `SKIPPED`, and every status context is `SUCCESS`;
- a UAT result is recorded on the issue (run by someone other than the author), or its `## UAT (or N/A + why)`
  section says N/A with a reason.

The deploy consequence is derived at card time from the workflows' `on.push` triggers, never hedged. First
`git -C <main> fetch <remote> <base_branch>; echo "rc=$?"` (a failure: stop and report, with no card). Then confirm
that `git -C <main> rev-parse refs/heads/<branch>` equals the PR's `headRefOid`, the one shown on the card (if not,
stop and report, with no card), and run TRIGGERS with `<lane_head>` = `refs/heads/<branch>` and `<event>` = `push`
(6.2 runs it with `pull_request`). A push runs the workflow definitions of the pushed commit, and after a merge that
is the merge commit, whose tree is the merge of the lane head into the base. TRIGGERS computes that merge with
`git merge-tree --write-tree <base_ref> <lane_head>` (it writes only loose objects: no ref, index or working-tree
change) and reads `.github/workflows/` from the resulting tree, so a workflow the lane edits and one the base changed
after the lane branched are both read as the merge commit carries them. The changed files come from
`git diff --no-renames --name-only <base_ref>...<lane_head>` (three dots: the lane's own changes, with no length
cap; `--no-renames` lists a moved file under its old path and its new one, as a delete and an add). For
`pull_request_target`, which GitHub runs from the base branch's copy, it reads `<base_ref>` instead. It prints a
`MERGE` line, then one line per workflow that has the trigger. It prints `UNKNOWN: ...` and exits 2 when the merge
has conflicts, when a filter pattern uses a token TRIGGERS does not model, or when more than 300 files changed (GitHub's paths filters read only the first 300). An `UNKNOWN`
line, an `ERROR` line or any other non-zero exit: report it verbatim, with no card.

**TRIGGERS** (it changes no ref, index or working tree; `<event>` is `push` or `pull_request`):
```bash
python3 - <main> <base_ref> <lane_head> <pr_target> <event> <<'PY'
import re, subprocess, sys, yaml
main, base, head, target, event = sys.argv[1:6]
def git(*a, ok=(0,)):
    p = subprocess.run(["git", "-C", main, *a], capture_output=True, text=True)
    if p.returncode not in ok:
        sys.exit(f"ERROR git {a[0]} rc={p.returncode}: {(p.stderr.strip().splitlines() or [''])[0][:200]}")
    return p
# GitHub-glob translator, NOT Python's fnmatch (see the known-gap note below for why
# fnmatch was wrong): '**/' -> zero-or-more path segments, '**' -> anything including
# '/', '*' -> anything except '/'. Patterns using ? + [ { or \ print UNKNOWN (exit 2). Longest-token-first
# order (**/  before **  before *) so '**/' is never mis-split into '**' + '/'.
def _gh_glob_re(pat):
    if any(c in pat for c in "?+[{\\"):
        print(f"UNKNOWN: pattern {pat!r} uses a token TRIGGERS does not model (? + [ {{ \\); read the workflow file directly")
        sys.exit(2)
    out, i, n = [], 0, len(pat)
    while i < n:
        if pat[i:i + 3] == "**/":
            out.append("(?:.*/)?"); i += 3
        elif pat[i:i + 2] == "**":
            out.append(".*"); i += 2
        elif pat[i] == "*":
            out.append("[^/]*"); i += 1
        else:
            out.append(re.escape(pat[i])); i += 1
    return re.compile("^" + "".join(out) + "$")
def _as_list(pats):
    # A string-form filter (`branches: main`, `types: opened`) is ONE pattern, not
    # characters to iterate -- wrap it in a list before matching.
    return [pats] if isinstance(pats, str) else list(pats or [])
def m(s, pats):
    # Ordered '!'-negation, GitHub's own semantics: patterns apply in LIST order,
    # each match (positive or negated) overwrites the running verdict, so the LAST
    # matching pattern wins. Starts unmatched.
    result = False
    for p in _as_list(pats):
        neg = p.startswith("!")
        if _gh_glob_re(p[1:] if neg else p).match(s):
            result = not neg
    return result
mt = git("merge-tree", "--write-tree", base, head, ok=(0, 1))
tree = mt.stdout.split("\n")[0]
if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", tree):
    sys.exit(f"ERROR git merge-tree rc={mt.returncode}: {(mt.stderr.strip().splitlines() or [''])[0][:200]}")
if mt.returncode == 1:
    print("UNKNOWN: merge has conflicts; CI consequence not derivable")
    sys.exit(2)
files = [f for f in git("diff", "-z", "--no-renames", "--name-only", f"{base}...{head}").stdout.split("\0") if f]
if len(files) > 300:
    print(f"UNKNOWN: {len(files)} changed files; GitHub's paths filters read only the first 300")
    sys.exit(2)
print(f"MERGE of {head} into {base}: tree {tree}, {len(files)} changed file(s)")
def fire(at, evs, note=""):
    for wf in git("ls-tree", "-z", "--name-only", at, ".github/workflows/").stdout.split("\0"):
        if not wf.endswith((".yml", ".yaml")):
            continue
        d = yaml.safe_load(git("cat-file", "blob", f"{at}:{wf}").stdout) or {}
        on = d.get(True, d.get("on"))
        on = {on: None} if isinstance(on, str) else ({k: None for k in on} if isinstance(on, list) else on)
        for ev in [e for e in evs if isinstance(on, dict) and e in on]:
            p = on[ev] or {}
            ref_kind = "a branch push" if ev == "push" else f"a {ev}"
            # Every workflow that HAS this trigger gets exactly one line below, FIRES or
            # "does not fire", naming the reason -- a filter mismatch is never silent.
            if ("tags" in p or "tags-ignore" in p) and "branches" not in p and "branches-ignore" not in p:
                # GitHub's documented gotcha: on.<ev> naming only tags/tags-ignore, with
                # neither branches nor branches-ignore present, means the trigger applies
                # ONLY to tag refs -- a branch-targeted event never matches it at all.
                print(f"does not fire {wf} on {ev} (on.{ev} names only tags/tags-ignore with no branches "
                      f"filter, so {ref_kind} to {target} never matches{note})")
                continue
            if "branches" in p and not m(target, p["branches"]):
                print(f"does not fire {wf} on {ev} (target {target} does not match its branches filter{note})")
                continue
            if m(target, p.get("branches-ignore") or []):
                print(f"does not fire {wf} on {ev} (target {target} matches its branches-ignore filter{note})")
                continue
            if ev != "push" and p.get("types") and not {"opened", "synchronize", "reopened"} & set(_as_list(p["types"])):
                print(f"does not fire {wf} on {ev} (its types filter excludes opened/synchronize/reopened{note})")
                continue
            if "paths" not in p and "paths-ignore" not in p:
                # No paths filter at all: every push/PR to a matching ref fires it, even
                # with zero changed files (a paths filter only ever narrows a match that
                # would otherwise happen; it is never the reason nothing matched here).
                print(f"FIRES {wf} on {ev} (every {ev} to {target}{note})")
                continue
            if not files:
                # A paths/paths-ignore filter IS present, but there is nothing to test it
                # against -- distinct from "changed files exist but none survived the
                # filter" below, and worth its own line rather than reusing that message.
                print(f"does not fire {wf} on {ev} (a paths filter is set but there are zero changed files to "
                      f"test it against{note})")
                continue
            hit = [f for f in files if ("paths" not in p or m(f, p["paths"])) and not m(f, p.get("paths-ignore") or [])]
            if not hit:
                if "paths" not in p:
                    # paths-ignore alone is EXCLUSIONARY (every file matches unless
                    # excluded), so "none matches its paths filter" would misdescribe an
                    # inclusion filter that was never there -- say what actually happened:
                    # every changed file got excluded.
                    print(f"does not fire {wf} on {ev} (all {len(files)} changed file(s) excluded by its "
                          f"paths-ignore filter{note})")
                else:
                    print(f"does not fire {wf} on {ev} ({len(files)} changed file(s), none matches its paths "
                          f"filter{note})")
            else:
                print(f"FIRES {wf} on {ev} (changed files matching its paths filter: {', '.join(hit)}{note})")
if event == "push":
    fire(tree, ["push"])
else:
    fire(tree, ["pull_request"])
    fire(base, ["pull_request_target"], f"; GitHub runs {base}'s copy of this workflow")
PY
```
**`m()` is a purpose-built GitHub-glob translator, not `fnmatch`.** An earlier version of TRIGGERS matched every
`branches`, `branches-ignore`, `tags`, `paths` and `paths-ignore` pattern with Python's `fnmatch.fnmatchcase`,
which does not implement GitHub's actual glob semantics: a bare `*` crosses `/` in `fnmatch` but never does on
GitHub (so `paths-ignore: ['*.md']` wrongly appeared to exclude `docs/x.md` under `fnmatch`, when GitHub actually
fires for that path), `**/` does not mean "zero or more path segments" to `fnmatch` the way it does to GitHub (so
`src/**/test/*.js` wrongly appeared not to match `src/test/z.js`), and `fnmatch` has no `!`-negation concept at
all (a `['**', '!main']` branches filter wrongly appeared to fire on `main`, the opposite of GitHub's answer). All
three were measured wrong by direct execution against `fnmatch`, then re-measured correct against `m()`'s
replacement translator. `_gh_glob_re()` now implements the documented GitHub token set directly: `**/` → zero or
more full path segments, `**` → any run of characters including `/`, `*` → any run of characters except `/`,
tokenized longest-match-first so `**/` is never mis-split into `**` followed by a
literal `/`. `m()` applies a pattern list (a bare string is wrapped to a one-item list first) in GitHub's own
ORDERED, last-match-wins way: each pattern that matches — positive or `!`-negated — overwrites the running verdict,
so `['**', '!main']` correctly ends unmatched for `main` (the negation is listed after, and last write wins) while
`['!main', '**']` would correctly end matched (the un-negated pattern listed last wins instead). **Not full GitHub parity, so unmodeled tokens refuse instead of guessing:** GitHub's filter cheat sheet gives
`?` as zero or one of the preceding character and `+` as one or more of it, it also supports `[...]` character
classes, and it allows escaping a special character with `\`. `_gh_glob_re()` models none of these. Any filter
pattern containing `?`, `+`, `[`, `{` or `\` makes TRIGGERS print `UNKNOWN: pattern ... uses a token TRIGGERS does not model` and exit 2, which is the
existing no-card path, so the workflow file is read directly. No live workflow in Agency or CSA used any of them
as of 2026-09-24. Case sensitivity, symlinks and minimatch trailing-slash edge cases are also not modeled.
**A separate caveat, not a gap in `m()`
itself:** whether GitHub actually fires a `paths`-filtered push/pull_request when the diff contains ZERO changed
files (an empty-diff push, e.g. an empty merge commit) is UNVERIFIED against GitHub's own live behavior — this
translator's "a paths filter is set but there are zero changed files to test it against" verdict (does not fire)
is TRIGGERS's own read of the documented semantics, not something confirmed against a real GitHub Actions run;
treat that specific line as unverified whenever it appears, and confirm against a real run if the card's decision
turns on it. For the patterns actually seen in this repo's and CSA's real workflows today (`agency/**`, literal
paths, plain branch names, no brace expansion, no `+`) `m()`'s answers match GitHub's documented behavior exactly,
verified by direct execution against synthetic workflows built the same way; state every TRIGGERS line on the
card regardless, so a misjudged edge case is still visible to whoever reads it, not silently trusted.
State every line in the card, naming the matching files. Example, as derived on 2026-09-24: a CSA merge
to `staging` fires `deploy-staging.yml` on every push; an Agency merge to `main` fires `deploy-staging.yml` when the
PR touches `agency/**` or `proposals/web-dev/otherapp/**`, and `post-merge-attest.yml` on every push. The merge
target and the deploy target are different things; the card names both. The card holds: what the merge does, the CI
evidence, the UAT result, the deploy consequence, and the command, with the `headRefOid` shown on the card:
```
gh pr merge <pr> --repo <r> --merge --match-head-commit <headRefOid>
```
Never `--squash` or `--rebase` (the reap's ancestry gate needs a merge commit), never `--admin` or `--auto`, and never
`--delete-branch` (it deletes the local branch, and `lane.sh reap` then refuses `no-branch`). After the merge, run
`/lane-cleanup <n>`, which takes the MERGED path.

**6.4 Update** (the lane half of the merge slot; reached only from R4). Preconditions (read-only; any failure:
report, nothing changed):
- 6.0 finds no standing hold (the update exists only to reach a merge card, so it waits with it);
- the ledger row is `open`;
- LEDGER `owner` is `self`, `dead` or `unknown` (A1's rule: `live-foreign` refuses, since another live session may be
  editing the lane);
- P4b did not stop.

Then one snippet, `UPDATE`, as one Bash call from the main tree with `git -C "$wt"` (never `cd <wt>`, never a
sub-agent). It stops before any change unless: the lane HEAD is `<branch>`; `git -C "$wt" status --porcelain` is
empty (a merge refuses to overwrite untracked files, and a clean tree makes `--abort` exact); no `MERGE_HEAD`; and
`git merge-tree --write-tree` of the base and the lane produces a real result tree (no conflict) — **exit code alone
does NOT discriminate a genuine conflict from an unrelated failure: `git merge-tree` returns rc 1 for BOTH a real
content conflict AND an unresolvable ref (verified by direct execution, 2026-09; TRIGGERS elsewhere in this same
file already applies the identical discrimination to the same command for exactly this reason). The real signal is
STDOUT: on success or on a genuine conflict, the first line is always a valid tree object id (40 or 64 hex chars);
on any other failure (a bad ref, an internal git error) stdout is EMPTY and the error text is on stderr instead.**
So the check is: rc 0 → clean (fall through to the merge); rc != 0 AND the first stdout line matches a tree id →
`CONFLICT`; rc != 0 and stdout does NOT match a tree id → `STOP merge-tree failed rc=<rc>`, never `CONFLICT` (which
would incorrectly tell the coordinator "two owners touched one file"):
```bash
# BEGIN lane-cleanup UPDATE
bash <<'SH'
main="<main>"; wt="<wt>"; br="<branch>"; base="<base_ref>"
[ "$(git -C "$wt" rev-parse --abbrev-ref HEAD)" = "$br" ] || { echo "STOP lane HEAD is not $br"; exit 1; }
[ -z "$(git -C "$wt" status --porcelain)" ] || { echo "STOP lane tree is not clean"; exit 1; }
if git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null; then echo "STOP a merge is already in progress in the lane"; exit 1; fi
if git -C "$main" merge-base --is-ancestor "$base" "refs/heads/$br"; then echo "SKIP $base is already in the lane"; exit 0; fi
out=$(git -C "$main" merge-tree --write-tree --name-only "$base" "refs/heads/$br"); mt_rc=$?
tree=$(printf '%s\n' "$out" | head -n1)
if [ "$mt_rc" -ne 0 ]; then
  case "$tree" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*)
      echo "CONFLICT (nothing changed):"; printf '%s\n' "$out" | sed -n '2,/^$/p'; exit 2 ;;
    *)
      echo "STOP merge-tree failed rc=$mt_rc"; printf '%s\n' "$out"; exit 1 ;;
  esac
fi
if ! git -C "$wt" merge --no-edit "$base"; then
  if ! git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null && [ -z "$(git -C "$wt" status --porcelain)" ]; then
    echo "STOP merge did not start; nothing changed"; exit 1
  fi
  if ! git -C "$wt" merge --abort; then echo "STOP abort failed"; exit 1; fi
  if git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null; then echo "STOP abort left MERGE_HEAD behind"; exit 1; fi
  if [ -n "$(git -C "$wt" status --porcelain)" ]; then echo "STOP abort left the tree dirty"; exit 1; fi
  echo "ABORTED: the merge stopped although merge-tree was clean"; exit 2
fi
if git -C "$wt" merge-base --is-ancestor "$base" HEAD && [ -z "$(git -C "$wt" status --porcelain)" ]; then echo "UPDATED $(git -C "$wt" rev-parse HEAD)"; else echo "STOP post-check failed"; exit 1; fi
SH
# END lane-cleanup UPDATE
```
The `case` pattern is a plain-glob 20-hex-digit prefix match (bash's `case`, not a regex — this shell has no
built-in ERE match operator without `[[ =~ ]]`, which is a bashism this snippet already avoids elsewhere), which is
sufficient to distinguish a real tree id (always 40 or 64 lowercase hex characters) from `merge-tree`'s own
plain-English error text on stdout, which never starts with 20 hex-looking characters in this shape. `CONFLICT`
means two owners touched one file (a disjoint-files failure): report it on the issue and on `lane.tracking_issue`;
no hand resolution in the pilot; the coordinator decides re-scope or abandon. **`git merge` itself can fail WITHOUT
ever starting a merge at all** (e.g. a stale `index.lock` in the lane's own git dir blocking the operation, or any
other pre-flight git error) — that shape is checked FIRST, before ever calling `merge --abort`: no `MERGE_HEAD` was
created AND the tree is still clean means nothing was touched, so `merge --abort` is never called (there is nothing
to abort, and calling it anyway on a lock-file-blocked repo would either no-op confusingly or itself fail for an
unrelated reason) and no abort-failure is ever carded for this shape — it reports plainly, `STOP merge did not
start; nothing changed`. Only once that check has ruled out "never started at all" does the snippet call `merge
--abort` and verify its own result. `STOP merge-tree failed rc=<rc>`, `STOP merge did not start; nothing changed`,
and `STOP abort failed`/`STOP abort left MERGE_HEAD behind`/`STOP abort left the tree dirty` are all distinct
git-tooling failures, never treated as a conflict; the lane is left exactly as `merge --abort` (or, for the
merge-tree and never-started cases, the untouched pre-merge state) leaves it, and the coordinator investigates
before retrying. After `UPDATED`, R5 cards
the push. **Every OTHER result — a precondition refusal (`STOP` from any of the checks above `SKIP`), `SKIP`,
`CONFLICT`, any `STOP` from the merge/abort block, or `ABORTED` — ends this cell with its own report and NEVER falls
through to R6**: R6 (the `mergeStateStatus`-driven `CLEAN`/`BEHIND`/etc. branch) is reached again only on a LATER
run of `/lane-cleanup <n>`, never within the same run that just ran 6.4. Gate and hook posture: `git merge` and
`git merge --abort` are in neither chain's blocked verbs (runtime `hooks/block_branch_ops.py` `STATE_VERBS`;
Agency's `.claude/hooks/block_branch_ops.py` has no `merge` rule); a merge is not a `git commit` (gates 3, 3b and 4
never see it); neither lane repo installs a hook git runs on a merge. It is sanctioned only
because it brings in content already reviewed and merged to the base.

## 7. Falsifiability

On an unmerged lane, `/lane-cleanup <n>` never reaches `lane.sh reap`: rows 1 and 3 report IN-PROGRESS, and rows 2
and 4 land in IN-REVIEW's R1-R6, none of which reaps (a `CLEAN` PR only cards a merge through 6.3; it is 6.3's own
merge-then-MERGED-path that eventually reaps, never this cell). If `lane.sh reap <n>` were invoked anyway, its
ancestry check refuses `needs-manual-reap` and the worktree and branch both remain. This skill never re-implements
or bypasses that check.

`hooks/tests/test_lane_cleanup_update.py` extracts the `UPDATE` snippet between this file's `# BEGIN lane-cleanup
UPDATE` and `# END lane-cleanup UPDATE` sentinels (so the test and this text cannot drift) and runs it in a hermetic
sandbox: a clean update prints `UPDATED`, leaves the tree clean, and leaves the base an ancestor of the lane tip; a
conflicting base prints `CONFLICT` with HEAD unchanged and no `MERGE_HEAD`; a second run against an already-updated
lane prints `SKIP`; a dirty lane prints `STOP`; a `git merge` that fails to start at all (e.g. a pre-existing
`index.lock` in the lane's own git dir) prints `STOP merge did not start; nothing changed` and never calls `merge
--abort`. With the `merge-tree` conflict guard removed, the conflict case goes RED (shown in the commit's Status);
with the never-started check removed, the `index.lock` case goes RED too (it would otherwise call `merge --abort`
against a repo that never started a merge).

## 8. Card procedure

Card only what genuinely needs the operator; anything an agent can do is agent work. A `lane-busy` caused by this
session is stop, report and retry, never a card.
1. Use P2's `operator_input.*` values. They were read with `--repo <main>`, so `.path` and `.open_path` are absolute.
   `.path` must start with `<main>/` and must not contain `/.claude/worktrees/`: cards go to the main tree's surface,
   never a lane's copy (a lane carrying the file would be dirtied, and its reap would refuse `dirty-tree`).
2. **Dedupe.** Search the open cards for the same issue and condition (`open_cards` whose `refs` or `title` carry
   `#<n>`; or `### [` entries under `## Open` that mention `#<n>`) — EXCLUDING any card whose title starts with
   one of the three fixed repo-level prefixes (`Lane prune (abandoned-backlog): <repo>`, `Lane stuck: <repo>`,
   `Lane orphans: <repo>`) or the per-issue `Lane diff-gap: #<n>` prefix. Those are `/lane-start`'s card family
   (card-procedure steps 2-4, and its own step 9 for diff-gap), never this section's — a card from that family
   naming `#<n>` in its `refs` is not a match for a dirty-tree/reap/REFUSE+CARD/STOP+CARD/closed-while-un-reaped
   card this skill is about to post, and merging the two would attach an unrelated note to the wrong card. If a
   genuine match exists (same issue, same condition, neither excluded prefix), add a dated update paragraph to
   it and report its number instead of adding a card. Running `--abandon` twice yields one card. Any edit of a
   `decisions_json` surface is followed by `open <open_path>`; a new card (`add-card`) and an archive (`archive`)
   regenerate the hub themselves (no separate regen), while an in-place update is followed by
   `(cd <main> && <regen_command>)`, as in step 3; a `decisions_markdown` surface is opened after any edit.
3. **By `operator_input.kind`:**
   - `decisions_json`: first read the surface's rules file, `decisions_rules.md` in the same directory as `.path`.
     `title` is plain text; `body_md` is Markdown (no level 1-3 heading, no raw HTML tag; the `*_html` fields are
     retired and a schema error). Create the card ONLY with the generator's locked `add-card` subcommand, never by
     hand-editing `decisions.json` (a hand edit races other sessions and can lose their cards); it takes the next
     permanent card number and appends the card in one locked step, validates both data files and regenerates both
     `.md` files. `<regen_command>` is root-relative (`python3 scripts/gen_operator_hub.py`), so it runs from
     `<main>`, and rc must be 0:
     ```bash
     b=$(mktemp) && cat > "$b" <<'EOF'
     <card body, Markdown>
     EOF
     tf=$(mktemp) && wf=$(mktemp) && cat > "$tf" <<'EOF'
     <plain text title>
     EOF
     cat > "$wf" <<'EOF'
     /lane-cleanup (<session>)
     EOF
     t=$(<"$tf"); w=$(<"$wf"); rm -f "$tf" "$wf"
     (cd <main> && <regen_command> add-card --title "$t" --body-file "$b" --asked-by "$w" \
       --ref '#<n>'); echo "add-card rc=$?"
     rm -f "$b"
     ```
     The title and `--asked-by` are single-line values read from QUOTED-heredoc temp files into variables (`$(<file)`; a heredoc inside `$(...)` breaks on an apostrophe in bash 3.2) and passed as
     `"$t"` / `"$w"` (a double-quoted expansion is never re-parsed, so an apostrophe, a backtick or `$HOME` in
     the text stays literal; single quotes would break on an apostrophe). Never splice untrusted text into the
     command line itself, and write any multi-line or free text to the quoted-heredoc `--body-file`. Keep `--ref` in the quoted `'#<n>'` form (a bare digit would be stored as an integer, and the card search for
     `#<n>` in `refs` would miss it). Then `open <open_path>` (or `open <path>` if the manifest sets no
     `open_path`). No separate regen is needed after `add-card`.
   - `decisions_markdown`: add a new entry at the top of `## Open` in `.path`. `N` is the max existing `[N]` + 1,
     and the `**Open:**` count goes up by one. Match an existing entry's shape: bold lead-in paragraphs, the exact
     commands, the default if unanswered, and a closing "Posted by session <label>, <date>." line. There is no
     regen step. After the write, run `open <open_path>` if the manifest sets one, otherwise `open <path>` (the
     queue file itself), as runtime CLAUDE.md §11 and the repo's own CLAUDE.md require whenever a card lands.
     ```bash
     b=$(mktemp) && cat > "$b" <<'EOF'
     <entry body>
     EOF
     python3 - <path> "$b" "<title>" <<'PY'
     import re, sys
     p, bf, title = sys.argv[1:4]
     t = open(p, encoding="utf-8").read()
     body = open(bf, encoding="utf-8").read().strip()
     assert "## Open\n\n" in t, "no '## Open' section"
     n = max([int(x) for x in re.findall(r"^### \[(\d+)\]", t, re.M)], default=0) + 1
     t = t.replace("## Open\n\n", f"## Open\n\n### [{n}] {title}\n\n{body}\n\n", 1)
     t = re.sub(r"^\*\*Open:\*\* (\d+)", lambda m: f"**Open:** {int(m.group(1)) + 1}", t, count=1, flags=re.M)
     open(p, "w", encoding="utf-8").write(t)
     print(f"carded [{n}]")
     PY
     rm -f "$b"
     ```
   - Any other kind, or no `operator_input`: say so in the report ("no operator-input surface"), invent no file,
     and list the ask as UNASKED.
4. **Body:** what is blocked, why only the operator can decide it, the exact command(s), what runs on approval, and
   the default if unanswered.
5. **Lifecycle.** A carded command runs only after the operator explicitly approves THAT card. A resolved card is
   archived with the operator's verbatim answer, or with an honest non-verbatim note, per the surface's lifecycle
   rules (`decisions_json`: moved into `decisions_archive.json` by `<regen_command> archive <no> ...`, never by hand; `decisions_markdown`: moved under
   `## Archived` with both counts updated).

## 9. Failure modes

| Stop | Mutated before stopping | Card |
|---|---|---|
| P1 bad argument (including both `--abandon` and `--update` given); P2 main unresolvable or key missing | nothing | none |
| P4 no lane | nothing | orphan findings only |
| P4b session launched inside the lane | nothing | none (no orphan check) |
| P5 issue or PR lookup fails or does not parse (PRSET `LOOKUP-FAILED` or `STOP`) | nothing | orphan findings only |
| P7 issue closed, without `--abandon` | nothing | "closed while un-reaped" card |
| IN-PROGRESS (rows 1 and 3, without `--abandon`; lane `open`, or `abandoned` and not reaped) | nothing, except row 3 with the lane `open`: board `In review` -> `In progress` | none |
| IN-REVIEW: R1 more than one `KEPT` OPEN PR | board -> In review (no call when it already reads In review) | none (report) |
| IN-REVIEW: R2 fetch or `gh pr view` fails | board -> In review | none (report) |
| IN-REVIEW: R3 lane and PR diverged | board -> In review | none (report) |
| IN-REVIEW: R6 `BEHIND` without `--update`, or with `--update` while the base is already in the lane, or `BLOCKED`/`DIRTY`/`DRAFT`/`UNSTABLE`/`HAS_HOOKS`/`UNKNOWN` | board -> In review | none (report; re-run later) |
| IN-REVIEW: R6 `CLEAN` | board -> In review | see 6.3 (its own card, once CI/UAT hold) |
| IN-REVIEW: R5 unpushed commits after R4 or a CI fix | board -> In review | see 6.1 (push card) |
| REFUSE+CARD | nothing | open-PR choice card |
| STOP+CARD (row 8) | nothing | merged-elsewhere card |
| MERGED: M2/M3 fetch or sha check fails | nothing | none (report) |
| MERGED: M4 lane tip not on base | nothing | tip-not-landed card |
| MERGED: M6 resolve fails | nothing | none (report) |
| MERGED: M7 fails twice, M8 THEN reaps in this run | issue resolved; board move still pending; lane reaped | none (reported as the one open item, in A4's conditional read-then-transition form, never a bare command — printed only because a later run can no longer retry M7 once the lane is reaped) |
| MERGED: M7 fails twice, M8 does NOT reap (any refusal) | issue resolved; board move still pending; lane not reaped | none from M7 itself (a later `/lane-cleanup <n>` run can retry M7 with a fresh `<cur>` read, since `lane.sh status` still carries the lane); M8's own refusal card still applies, per the row below |
| MERGED: M8 reap refused | issue resolved, board Done (or still pending if M7 failed twice) | refusal card (none for a `lane-busy` held only by this session's own processes) |
| ABANDON: A1 live foreign owner (A1 never runs under P8) | nothing | none (report) |
| ABANDON: A3 reap refused | `abandoned` row, board reset (when the board read a worked status, and P7 does not apply) and comment; under P8 only a board reset still pending, again skipped if P7 applies | refusal card, or a dated update to the existing one (none for a `lane-busy` held only by this session's own processes) |
| 6.0 a standing hold on lane pushes or PRs on any lane-enabled repo's surface (or an open card asking it) | nothing | none (report the ruling and its surface) |
| 6.0 exit 1: registry or a lane-enabled surface unreadable, or no surface for `<main>` | nothing | none (report; UNASKED when `<main>` has no surface) |
| 6.1 an earlier lane's PR on the same branch name is still OPEN | nothing | close-the-old-PR card |
| 6.2/6.3 fetch fails, the local lane head differs from the pushed or PR head, or TRIGGERS prints `UNKNOWN` (conflicts, an unmodeled filter token, over 300 files) or fails | nothing | none (report) |
| 6.4 Update: precondition fails (6.0 hold, ledger not `open`, `live-foreign` owner, P4b) | nothing | none (report) |
| 6.4 Update: `SKIP` (base already in the lane) | nothing | none (R6 reaches it on the next run) |
| 6.4 Update: `STOP` from a PRECONDITION (lane HEAD not `<branch>`, dirty tree, `MERGE_HEAD` already present, or `merge-tree` itself failing for a non-conflict reason) | nothing | none (report) |
| 6.4 Update: `STOP merge did not start; nothing changed` (`git merge` failed but never created `MERGE_HEAD` and left the tree clean, e.g. a stale `index.lock`) | nothing | none (report; `merge --abort` is never called for this shape — there is nothing to abort) |
| 6.4 Update: `STOP post-check failed` (the merge itself SUCCEEDED — a merge commit now exists in the lane — but the post-check found the base is still not an ancestor, or the tree is not clean) | a merge commit exists in the lane, unpushed | none (report; inspect the lane before any push — this is NOT the same as a precondition STOP, and no push card is posted until someone has looked at what the merge actually produced) |
| 6.4 Update: `STOP` from the abort path (`abort failed`, `abort left MERGE_HEAD behind`, `abort left the tree dirty`) | the merge attempt was made (`MERGE_HEAD` was created or the tree was dirtied) and `git merge --abort` either failed or left the tree in an unexpected state | refusal card (this is a git-tooling failure, not an ordinary conflict; a 3-strike candidate if it recurs) |
| 6.4 Update: `CONFLICT` | nothing (the merge is never attempted; `merge-tree` alone detects it) | issue + `lane.tracking_issue` comment |
| 6.4 Update: `ABORTED` (the merge itself failed although `merge-tree` was clean) | nothing (the merge is aborted before returning) | none (report; a 3-strike candidate if it recurs) |
| Same step fails a third time | as at that step | none; report (3-strike) |
