---
name: lane-start
description: "Open a lane for one OPEN issue. Resolves the main tree, reads the issue, drafts any missing AC/UAT section as one comment, runs the diff-gap pre-flight and posts its result, runs `lane.sh open`, the orphan check and EnterWorktree, then moves the issue to In progress. Re-running it on an existing open lane resumes it: an unentered lane (e.g. one opened under an unreachable-GitHub warning) gets its pick-source eligibility re-checked; an already-entered lane is re-entered as it is, and its board status is never moved back. LIVE only (no dry-run): exercise it on a scratch issue. Never pushes or opens a PR."
argument-hint: "<issue#>"
---

# /lane-start <issue#>

Opens one ledgered lane: one issue, one worktree, one branch. The mechanism is `~/.claude/scripts/lane.sh open`; its
header holds the refusal contract. Specs: adoption plan
`~/.claude/plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md` §6.1, §6.3, §7.1, §7.3-§7.5;
sprint rows L5.2 and L5.4 in `~/.claude/plans/otherapp_sprint_1_lane_control_and_floor.md`; the lane.sh contract in
`~/.claude/plans/otherapp_s1_L5_5_lane_repo_enablement.md`; runtime `~/.claude/CLAUDE.md` §2 case (d), §4, §8, §11.

**LIVE only. There is no dry-run mode.** Every run posts real comments, opens a real lane that counts against
`lane.max_open`, and moves a real board card. Exercise it only on a scratch issue made for the purpose (step 2 gives
the values; the body file comes from `mktemp` and holds no AC/UAT sections):
- `label` pick source: `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh create --title "scratch: lane skill check" --body-file <f> --label "<ps_label>" --force-new --triage Backlog --project <proj> --owner <owner>)`
- `project_status` pick source: the same without `--label`, with `--triage "<ps_status>"`, and with
  `--project <ps_project> --owner <ps_owner>` in place of `--project <proj> --owner <owner>` — the pick-source's own
  project/owner from `lane.pick_source`, which may differ from `github.project_number`/`github.project_owner`; the
  scratch issue must land on the board `lane.sh open`'s R4 membership check actually reads.
Disposing of the scratch issue afterwards (`(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh dispose ...)`)
is itself an operator ask: card it and run it only on approval.

## Conventions (apply to every step)

1. **Literal values.** Step 2 prints `<main>` and the manifest values. Paste them literally into every later command:
   `<main>`; `<r>` = `github.repo`; `<proj>` = `github.project_number`; `<owner>` = `github.project_owner`;
   `<base_ref>`; `<remote>` and `<base_branch>` = `<base_ref>` split at its first `/`; `<pr_target>`; `<kind>`,
   `<ps_status>`, `<ps_label>`, `<ps_project>`, `<ps_owner>` from `lane.pick_source`. Bash-tool shell variables do
   not survive between calls, and `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo ""` silently resolves
   from the cwd, so no command may depend on a variable set in an earlier call. Variables used within ONE call are
   fine.
2. **Exact tool forms.**
   - Manifest: `python3 ~/.claude/scripts/repo_manifest.py get <key> --repo <main>` (not on PATH).
   - Issue helper: `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh <sub> ...)`. It is a bash script
     with no `--repo` flag; it resolves the repo from its cwd, so it always runs from `<main>` with `GH_REPO`
     pinned. Never invoke it with python3, by bare name, or by a relative path.
   - `(cd <main> && bash ~/.claude/scripts/lane.sh ...)` and `(cd <main> && bash ~/.claude/scripts/lane_orphans.sh)`.
     Neither takes `--repo`; both resolve from the cwd. From inside a worktree `lane.sh` refuses `nested-lane` and
     `lane_orphans.sh` reports a false clean. The parentheses leave the session's own shell where it is.
   - Every raw `gh issue ...` / `gh pr ...` call carries `--repo <r>`.
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
3. **Branch source.** The lane branch is the `branch ` line of `lane.sh open`'s output, or the `branch` of the ledger
   row. It is never rebuilt from `lane.branch_prefix` plus a slug and never assumed to be `issue/...`.
   `lane.branch_prefix` is REQUIRED and never defaulted.
4. **Ledger.** `~/.claude/.lanes/lanes.jsonl` (or `$LANE_DIR/lanes.jsonl` in a hermetic sandbox) is read-only here;
   only `lane.sh` appends to it. Read it only with the LEDGER snippet; an absent file means "no lane".
5. **Never**: raw `git worktree add/remove/move`; `git branch` create, `-d` or `-D`; `git checkout`, `switch`,
   `stash`, `reset`, `rebase`, working-tree `restore` or `clean`; `--force`; `--no-verify`; any `SKIP_*` bypass env
   (`SKIP_BRANCH_CHECK`, `SKIP_LOCAL_CI`, `SKIP_AUTOFORMAT`, `SKIP_PRE_PUSH_STAGE`); `npm install`/`npm ci` inside
   a lane. A lane is left only with ExitWorktree action `"keep"` and removed only by `lane.sh reap` or
   `lane.sh reap --abandoned` (via `/lane-cleanup`).
6. **Bodies** of comments and cards carry no secrets, tokens, PII or PHI. Write each body to a `mktemp` file and
   `rm -f` it in the same call.
7. **3-strike.** If the same step fails a third time, stop and report what failed and what was tried. No fourth
   workaround.
8. This skill never pushes and never opens a PR (runtime CLAUDE.md §4). Those are `/lane-cleanup`'s carded asks,
   which it posts only while no standing operator ruling holds lane pushes or PRs. It searches the operator surface
   of every lane-enabled repo for one, because a lane ruling recorded in one repo binds every lane-enabled repo
   unless it scopes itself to another.
9. **PR set.** A PR is a lane's only when it is a same-repo PR whose head is the lane's ledger branch AND whose
   `createdAt` is at or after that lane's last `open` (its LEDGER `opened_ts`). Branch names are reused: an issue
   re-picked after a reap gets the same branch again, and `gh pr list --head` returns every earlier lane's PRs too.
   Apply the rule only through PRSET; never compare the two timestamps as strings (the ledger writes a `%z` offset,
   GitHub writes `Z`).

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
`<main>` is `dirname` of the absolute common dir. It is never `git rev-parse --show-toplevel`, which returns the
worktree from inside a lane.

**LEDGER** (read-only; `<which>` is an issue number or `all`; prints the last row per issue for `<main>` plus
`owner` = `self` | `live-foreign` | `dead` | `unknown` | `released`, and `opened_ts`; `null` means no row).
`released` means the last row is not `open`: an `abandoned` or `reaped` lane has no owner, and the `pid` on an
`abandoned` row is the session that ran `lane.sh abandon`, not the lane's worker:
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
convention 9. Prints one `KEPT` or `IGNORED` line per PR and a final `COUNTS M= X= O= C=` line: `M` merged to
`<pr_target>`, `X` merged elsewhere, `O` open, `C` closed unmerged. On a failed or unparseable lookup, a possibly
truncated list, or an unusable `opened_ts`, it prints `LOOKUP-FAILED ...` or `STOP ...` and exits 1:
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

## Steps

Order: argument, main tree, resume check, cap precheck, read issue, state, AC/UAT, lane files, diff-gap A then B,
`lane.sh open`, orphan check, EnterWorktree, In progress. A failed step stops every later step.

1. **Argument.** `<n>` is required and all digits. Anything else: stop; nothing is called.
2. **Main tree and manifest.** Run MAIN.
   - `TOP` under `/.claude/worktrees/`: the session is inside a worktree. Stop before any read or write. No comment,
     no card, no ledger change. Report "inside a worktree: leave it with ExitWorktree action `"keep"`, then re-run".
     If ExitWorktree reports that no worktree session is active, the session was launched inside that worktree or
     only its shell `cd`'d there. When `lsof -a -p $CLAUDE_PID -d cwd -Fn` shows the CLI's own cwd under
     `/.claude/worktrees/`, report "launched inside a worktree: re-run `/lane-start <n>` from a session launched in
     `<main>`" (no tool moves a CLI's launch directory). Otherwise `cd <main>` and re-run.
   - A `STOP` line: stop and report it.
   - Otherwise `<main>` is the `MAIN` path. Read the manifest:
     ```bash
     for k in github.repo github.project_number github.project_owner lane.base_ref lane.pr_target lane.branch_prefix lane.pick_source lane.max_open lane.max_abandoned operator_input.kind operator_input.path operator_input.regen_command operator_input.open_path; do printf '%s = ' "$k"; python3 ~/.claude/scripts/repo_manifest.py get "$k" --repo <main> 2>&1; done
     ```
     Stop, naming the missing key, when any `github.*` or `lane.*` key prints `key-missing`. **Also stop, reporting
     `bad-manifest`, when `lane.max_open` or `lane.max_abandoned` prints anything that is not all-digits** (test it
     with `lane.sh`'s own pattern, `''|*[!0-9]*` — empty or containing a non-digit both fail it): these two keys are
     checked here, not left to surface first at step 10 (`lane.sh open`), because reading them only there would let
     steps 7 (AC/UAT draft) and 9 (diff-gap comment) post real, permanent comments on an issue that step 10 then
     refuses to open a lane for on a manifest defect that was knowable up front. For `lane.branch_prefix`, report
     that `lane.sh open` refuses it as `REFUSED (manifest-key-missing)`: the key is REQUIRED and never defaulted.
     (Step 4's cap precheck is the nearer backstop for the CAP COUNTS specifically, once the keys are known-good;
     this manifest-read stop is what catches a missing or malformed key before step 4 can even use it.)
     Also stop when `lane.pick_source.kind` is neither `project_status` (which needs a positive integer `project`
     and non-empty `owner` and `status` strings) nor `label` (which needs a non-empty `label` string); `lane.sh
     open` refuses those shapes `bad-manifest`. Missing `operator_input.*` keys are allowed; the card procedure
     (its own numbered list, below — see card-procedure step 4's `operator_input.kind` branches) handles them.
3. **Resume check.** Run LEDGER for `<n>`. A row with `event` `open` means this lane already exists, entered or not:
   go to **Resume** and never re-run `lane.sh open`, and never run step 4's cap precheck (an existing lane already
   counts toward the cap; re-checking it here would wrongly block a legitimate resume — `lane.sh open` is never
   called on the resume path anyway, so there is nothing left for the precheck to protect). `abandoned`: stop and
   report that `/lane-cleanup <n> --abandon` handles it, per whichever cell of its PR-state x `--abandon` matrix
   this lane actually lands in (`--abandon` never overrides a cell the PR state already decided):
   - **No open or merged PR (rows 1/3):** it reaps the lane, or cards `lane.sh reap --abandoned`'s own refusal.
   - **A merged PR to `<pr_target>` (rows 5-7):** `--abandon` is IGNORED — the MERGED path runs regardless of the
     flag. Rows 5-6 resolve the issue and reap via a plain `lane.sh reap`, never `reap --abandoned`. **Row 7 is an
     exception, not a third case of the same outcome:** it additionally carries a stray OPEN PR, and its M4
     pre-resolve check (does the lane's tip land on the base?) normally FAILS in that shape — a stray open PR to
     another base still holds commits, so the branch is usually not fully landed — which stops the MERGED path
     BEFORE resolve or reap, carding a tip-not-landed finding instead. Row 7 reaches "resolve and reap" only in
     the rarer case where M4 passes despite the stray open PR.
   - **An open PR (rows 2/4):** REFUSES outright and cards the open-PR choice, without ever calling `lane.sh reap`
     (its REFUSE+CARD path; `--abandon` does not reap over an open PR).
   - **A PR merged only to another base, no merge to `<pr_target>` (row 8):** STOP+CARD — nothing is resolved or
     reaped; it cards the merged-elsewhere finding and stops, flag or no flag.

   `null` or `reaped`: continue to step 4 — this is the only path that reaches it, because only a genuinely new
   lane (never opened, or opened and already reaped) can still hit `lane.sh open`'s own caps.
4. **Cap precheck.** `(cd <main> && bash ~/.claude/scripts/lane.sh status)`. Count the rows whose `STATE` column is
   `open` and the rows whose `STATE` column is `abandoned`. Check BOTH caps, independently, before stopping — never
   an `if`/`elif` that only ever runs one:
   - If the open count is already `>= lane.max_open`, run section B (`cap-reached`) now: it needs only the
     LEDGER/PRSET snippets and the manifest values already read at step 2, and it ends by carding any stuck lane
     it finds (or reporting `cap-reached` with no card if none is stuck).
   - If the abandoned count is already `>= lane.max_abandoned`, run section A (`abandoned-backlog`) now, the same
     way — REGARDLESS of whether section B above already ran: when both caps are hit at once, run BOTH sections in
     this same turn, not only one of them.
   - Stop after running whichever of A and B applied (one or both), before step 5 reads the issue and before any
     AC/UAT or diff-gap comment is posted, so the prune or stuck card is what `lane.sh open`'s own refusal text
     ("post the operator prune card in THIS turn") actually asks for, in this same turn, rather than only in chat.

   This is a read-only precheck against the same counts `lane.sh open`'s own R5/R6 checks make; it exists only to
   stop and card before steps 7 and 9 post, not to replace `lane.sh open`'s own refusal (which still runs, and
   still governs, at step 10, for the rare case where the count changes between this precheck and that call).
5. **Read the issue.** `gh issue view <n> --repo <r> --json title,body,state,comments`. If it fails for any reason
   (unreachable, auth, not found), stop. Nothing has been written.
6. **State.** If `state` is not `OPEN`, stop. Write nothing (no draft, no diff-gap comment, no card, no `lane.sh open`) and
   report that `lane.sh open` would refuse `issue-closed`. One exception: if an open card titled exactly
   `Lane diff-gap: #<n>` exists, resolve it with a dated "issue closed" note (the Resolve command in `/lane-cleanup`
   section 4, or a direct edit on markdown). Nothing else would ever reach that card once the issue is closed.
7. **AC/UAT (adoption §6.3).** A section is present when a line reads exactly `## Acceptance criteria` or
   `## UAT (or N/A + why)` (trailing whitespace ignored) in the body or in any comment, including an earlier
   `AC/UAT draft — unconfirmed` comment. If both are present, skip this step.
   Otherwise draft ONLY the missing section(s), as ONE comment whose first line is exactly `AC/UAT draft — unconfirmed`
   (U+2014 em dash, byte-identical to adoption §6.3):
   ```
   AC/UAT draft — unconfirmed

   ## Acceptance criteria
   - <one observable outcome per line; the verb is the bar; checkable by a non-author; met before the PR>

   ## UAT (or N/A + why)
   - [local|staging] <a user's step in a user's words> -> <expected result>
   ```
   - Label each UAT step with the LOWEST environment it can run in, `local` or `staging`. Production is never
     labelled by an agent (adoption §6.1). "N/A + why" is allowed, and is a finding.
   - Post it: `f=$(mktemp) && cat > "$f" <<'EOF'` ... `EOF`, then
     `(cd <main> && GH_REPO=<r> bash ~/.claude/scripts/gh_issue.sh comment <n> --body-file "$f"); rc=$?; rm -f "$f"; echo "rc=$rc"`.
     A non-zero rc stops the run.
   - Never edit the issue body (the helper has no body-edit path) and never route the draft to the operator. A
     revision may sharpen or complete the issue's intent, never narrow it.
8. **Lane files.** Derive from the issue, and the code it concerns, the explicit NON-EMPTY list of repo-relative
   paths the lane will touch (`<files>`, each quoted). If you cannot name at least one path, stop and report
   "lane files undetermined". Never run a pathspec with nothing after `--`: that diffs the whole tree.
   - **Frontend rule.** A frontend-scoped path is repo-neutral and decided by TOOLCHAIN, never by directory
     ancestry alone: a `package.json` existing somewhere above a path in the tree does NOT make every path under
     it frontend-scoped — Agency's own `agency/package.json` sits above both `agency/src/**` (React/JS, genuinely
     frontend) AND `agency/backend/**` (Python/Flask, genuinely not), so an ancestor-`package.json` test alone
     would wrongly stop a Python-only lane. A path is frontend-scoped when EITHER: (a) it has a JS/TS/JSX/TSX/CSS/
     SCSS file extension (`.js`, `.jsx`, `.ts`, `.tsx`, `.css`, `.scss`, `.mjs`, `.cjs`), or it is a `package.json`, a
     package lockfile (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`), or an `.html` file inside a frontend app's
     source tree (dependency and entry-point changes are frontend tooling and stay in the main tree), OR (b) it is explicitly
     named or globbed by a script in the nearest ancestor `package.json`'s `scripts` block that lints, tests, or
     builds (read `<main>/package.json` and any nested `package.json` under `<files>`'s leading directories to
     check this live, e.g. Agency's `agency/package.json` scripts `lint`, `lint:css`, `test`, `test:e2e*`,
     `build`, `storybook`; never a hardcoded per-repo path list). A path that is neither — a `.py` file even
     under `agency/backend/**`, a shell script, a markdown doc — is NOT frontend-scoped regardless of what
     `package.json` sits above it in the tree. If `<files>` includes any path that IS frontend-scoped by this
     test, stop here, before step 9 or `lane.sh open`: frontend work inside a lane waits on
     probe (g) (sprint row L5.4: frontend tooling through lane.sh's symlinked `node_modules`). The stop lifts the
     moment the sprint plan's L5.4 row (`~/.claude/plans/otherapp_sprint_1_lane_control_and_floor.md`) records
     probe (g) as PASS — read that row live before stopping, never assume it is still pending from memory or from
     an earlier run in this same session. Until it records PASS, frontend work stays in the main tree, never a
     lane, and dependency installs (`npm install`, `npm ci`) never run inside a lane either way, even after PASS
     (CLAUDE.md §2 case (d)). This check belongs here, not in step 7, because step 7 runs before `<files>` is even
     known — a frontend-scoped lane must be caught at the moment its files are chosen, not left to the AC/UAT
     step's own generic reminder.
9. **Diff-gap pre-flight (sprint row L5.4), before `lane.sh open`, from `<main>`.**
   ```bash
   git -C <main> fetch <remote> <base_branch>; echo "fetch rc=$?"
   git -C <main> rev-parse --abbrev-ref HEAD
   ```
   A failed fetch, or `HEAD` printed (a detached HEAD), means stop and report. Otherwise `<work>` is that branch,
   resolved live every run (a dated work branch today; never hardcode one).
   - **Step A:** `git -C <main> status --porcelain -- <files>; echo "rc=$?"`. Non-zero rc: stop and report. Any
     output means peer edits are uncommitted in the main tree (a §2 contested file): stop, report the lines, retry
     later. No card, no comment, no lane.
   - **Step B:** `git -C <main> diff --name-only <base_ref>...<work> -- <files>; echo "rc=$?"` (three dots, from the
     merge base). Non-zero rc: stop and report. Otherwise post the result on the issue with the step 7 posting
     form, on every run that reaches this step, clean runs included:
     ```
     ## Diff-gap check (pre-open)
     Lane files: <files>
     Command: git diff --name-only <base_ref>...<work> -- <files>
     Result: clean | NOT clean: <paths>
     ```
     Clean: if an open card titled exactly `Lane diff-gap: #<n>` exists, resolve it (the Resolve command in
     `/lane-cleanup` section 4; for `decisions_markdown`, the markdown rule in card-procedure step 3) before
     continuing, so the hub no longer asks for a train release the lane doesn't need.
     Not clean: card it (the work branch carries unreleased changes to the lane's files, so the lane needs a train
     release first or a different scope) and stop BEFORE open. **This card is single-issue, unlike sections A/B's
     and the orphan card's repo-level, multi-lane cards** — it is scoped to `<n>` alone: title is EXACTLY
     `Lane diff-gap: #<n>` (matched as the whole title, never as a prefix, so `#12` never matches `#123`), and `refs` is exactly `["#<n>"]`, never a repo-level prefix and never another lane's
     issue. Dedupe on this card's exact title PLUS `#<n>` in `refs` (never the bare `#<n>` search used for a
     single-issue reap/dirty-tree card from `/lane-cleanup`, which carries no fixed prefix at all and is a
     different card family): a second `/lane-start <n>` run that still finds the diff-gap not clean updates THIS
     card with a dated note rather than posting a new one every re-run.
10. **Open.** `(cd <main> && bash ~/.claude/scripts/lane.sh open <n>); echo "lane.sh rc=$?"`. Decide by the rc,
    never by line order:
    - **rc != 0** is a refusal, `lane: REFUSED (<code>) <msg>`, and nothing was created, even if a
      `github-unreachable` warning printed first (it prints before the caps and collision checks). Report it
      verbatim and stop: no workaround, no hand-typed git. The AC/UAT draft and diff-gap comment already posted
      stay, and the report says so. Codes: `bad-issue`, `not-a-repo`, `nested-lane`, `no-manifest`,
      `manifest-key-missing`, `bad-manifest`, `no-such-issue`, `issue-closed`, `not-in-pick-source`,
      `cap-reached`, `abandoned-backlog`, `lane-exists`, `no-base-ref`. `cap-reached` and `abandoned-backlog`
      should already have been caught by step 4's precheck; a fresh one here means the count changed between
      that precheck and this call (another session opened or abandoned a lane in between) — re-run step 4's precheck
      now (both counts), and run section A and/or B exactly as step 4 would have. An rc != 0 without `REFUSED` (e.g. `git worktree add failed`) is
      reported verbatim with `(cd <main> && bash ~/.claude/scripts/lane.sh status)`.
    - **rc 0**: take `<wt>` and `<branch>` from the output lines whose trimmed text starts with `worktree ` and
      `branch `, never by position. If the output carries `WARNING github-unreachable` or
      `WARNING pick-source-unreachable`, the lane EXISTS but its eligibility is unconfirmed: stop before entering or
      transitioning and report "lane exists, unentered" with `<wt>` and `<branch>`. Re-running `/lane-start <n>`
      later resumes it.
    - `WARNING fetch of <base_ref> failed` (the lane may branch from a stale base) and `could not link <rel>` are
      reported verbatim. Neither is a stop by itself.
11. **Orphan check**, right after the open and BEFORE entering:
    `(cd <main> && bash ~/.claude/scripts/lane_orphans.sh); echo "rc=$?"`. Report the rc and every line verbatim.
    - **rc 1** is a result: ALWAYS card the findings (except Resume step 5's own `dead-owner` finding) (`orphan-worktree` and `dead-owner` are operator decisions
      per the script header — this is what actually reaches the operator, in the same turn, per runtime
      CLAUDE.md §11 and the repo's own operator-hub rule; a comment alone does not), using the
      `Lane orphans: <repo>` title prefix and card-procedure step 3's dedupe. If an open `Lane orphans: <repo>`
      card already exists, REPLACE its findings list and `refs` with this run's current findings using card-procedure
      step 3's orphan replace snippet (never merge-only-add: a
      finding that no longer reproduces is a finding that no longer belongs on the card, and an ever-growing list
      of stale entries is as useless as no card at all) and append a dated note recording the replacement; report
      its number. `refs` names only the lanes a finding actually cites (`#<n>` goes in `refs` ONLY when a finding
      names `#<n>` specifically — this run's own lane is not automatically one of them, and is never added just
      because this run opened it). ADDITIONALLY, only when this run created the card or changed its findings list, and when
      `python3 ~/.claude/scripts/repo_manifest.py get lane.tracking_issue --repo <main>` resolves to an integer,
      also comment the same findings on that issue — never instead of the card, and never a hardcoded number or a
      different repo's issue. If the key is absent (`key-missing`) or not an integer, the card alone is the
      findings' record; still never comment to a guessed issue.
    - **rc 0** (clean): if an open `Lane orphans: <repo>` card exists, RESOLVE it with `/lane-cleanup`'s section 4 Resolve command (an honest
      non-verbatim note, e.g. "resolved by agent action: `lane_orphans.sh` reports clean as of `<date>`") — a
      clean run means every finding that card described no longer holds. No card exists: nothing to do.
    - Either way, continue. **rc 2** is an environment error: stop (lane exists, unentered); no card action either
      way, since the check itself did not run to completion.
12. **Enter.** Load the tool if needed (ToolSearch `select:EnterWorktree`), then `EnterWorktree(path="<wt>")`
    (adoption §7.3 probe (e)). On failure, do not re-run open: report the error. The lane exists unentered;
    re-run `/lane-start <n>` to resume, or `/lane-cleanup <n> --abandon`.
13. **In progress.** Move the issue to `In progress` (convention 2), using the literal `<main>`, `<proj>` and
    `<owner>` from step 2. That works from inside the lane even though the lane's base carries no manifest. On a
    resume, Resume step 2's read is the read.
14. **Report**: `<wt>`, `<branch>`, the comments and cards posted, the orphan result, entered (or resumed, and
    whether it was already entered), board status. Next:
    work and commit inside `<wt>`, checkpoint with `/lane-save`, ship and close with `/lane-cleanup <n>`.

## A. `abandoned-backlog`

1. LEDGER `all`; take the rows with `event` `abandoned`. For each (branch `<b>` and worktree `<w>` from the row):
   `git -C <main> merge-base --is-ancestor refs/heads/<b> <base_ref>; echo "rc=$?"` and
   `git -C <w> status --porcelain; echo "rc=$?"`.
2. In the SAME turn, post ONE prune card (dedupe first). List each abandoned lane: issue, worktree, branch, whether
   its tip is on the base, and whether its tree is clean, dirty or unverifiable. A clean lane whose tip is on the
   base is reaped by `/lane-cleanup <m> --abandon`, from any session (an abandoned lane has no owner). Any other lane
   holds unlanded work, and removing it is the operator's decision (CLAUDE.md §2 case (d)).
3. Stop. `/lane-start` never reaps.

## B. `cap-reached`: read-only stuck-lane check

1. LEDGER `all`; take the rows with `event` `open`. Branch `<b>` and `opened_ts` from the row. For each:
   `git -C <main> merge-base --is-ancestor refs/heads/<b> <base_ref>; echo "rc=$?"`, and PRSET with `<b>`, that
   row's `opened_ts` and `<pr_target>`. Only its `KEPT` PRs are the lane's; an earlier lane's PR on the same reused
   branch name is `IGNORED` and never makes a fresh lane look stuck.
2. A lane is STUCK only when its `COUNTS` show a MERGED PR (`M` or `X` >= 1), or a CLOSED one and no OPEN one
   (`C` >= 1 and `O` = 0); or when its tip is an ancestor of the base AND its row's `owner` is `dead` (a pid provably
   dead on this host). Ancestry alone never counts: a freshly opened lane with no commits is an ancestor too. A lane
   whose PRSET printed `LOOKUP-FAILED` or `STOP` is reported as unknown, not stuck.
3. Stuck lanes: one card (dedupe) naming each with its evidence and the command that moves it: a PR merged to
   `<pr_target>` (`M` >= 1) -> `/lane-cleanup <m>` (its MERGED path); a PR merged only to another base (`X` >= 1,
   `M` = 0) -> `/lane-cleanup <m>` too, which stops and cards it as merged elsewhere; only CLOSED PRs, or a dead
   owner with the tip on the base ->
   `/lane-cleanup <m> --abandon` (without the flag it only reports), unless the lane's work is being reworked for a
   replacement PR. Then report `cap-reached` and stop, or go on to section A when step 4 found both caps hit. No
   stuck lane: report; then go on to section A when step 4 found both caps hit, otherwise stop, with no card. Never
   `lane.sh reap` or `reap --abandoned` here.

## Resume (step 3 routes here)

Never re-run `lane.sh open`; it refuses `lane-exists`. `<wt>`, `<branch>` and `owner` come from the ledger row.
Resume covers two different lanes, told apart in Resume step 4: an UNENTERED one (the open stopped before
EnterWorktree, e.g. under an unreachable-GitHub warning) and an ALREADY-ENTERED one (a session worked in it and left,
e.g. through `/lane-cleanup`'s exit, or its owner died and this session is the hand-off successor).
1. **Owner.** `live-foreign` (a pid live on this host that is not this session's `$CLAUDE_PID`): another live
   session owns the lane; stop and report. `self`, `dead` or `unknown`: continue, and name it in the report.
2. **Read.** `gh issue view <n> --repo <r> --json state,labels,projectItems`;
   `gh project view <proj> --owner <owner> --format json --jq .title` gives `<board_title>`; for `project_status`,
   `gh project view <ps_project> --owner <ps_owner> --format json --jq .title` gives `<ps_title>` (the same value
   when the number and owner match). Any failure (unreachable, auth, a GraphQL rate limit): stop and report.
3. **Issue state.** Not `OPEN`: stop and report the state, recommending `/lane-cleanup <n> --abandon` (a merged PR
   still takes the MERGED path; the flag is then ignored). Do not run it.
4. **Entered or not.** `<cur>` is the `status.name` of the `projectItems[]` entry whose `title` equals
   `<board_title>`, or `none`. Those three statuses are the ones step 13 (`In progress`) and `/lane-cleanup`
   (`In review`, `Done`) set on a lane's issue. If `<kind>` is `project_status` and `<ps_status>` is itself one of
   the three, this test cannot tell the cases apart: stop and report.
   - **Already entered** (`<cur>` is `In progress`, `In review` or `Done`): pick-source eligibility is NOT
     re-checked. An entered lane has left its pick-source status by design, and its label may have moved on to the
     next sprint. Continue at step 11 (orphan check) and step 12 (enter), and skip step 13: the board already
     records the lane, and `In review` or later is never moved back to `In progress`.
   - **Unentered** (any other `<cur>`, including `none`, `Backlog` and the pick-source status). Eligible means:
     - `project_status`: the `projectItems[]` entry whose `title` equals `<ps_title>` has `status.name` equal to
       `<ps_status>`.
     - `label`: some `labels[].name` equals `<ps_label>` exactly (case-sensitive).

     Eligible: continue at steps 11, 12 and 13 (step 13 then moves the pick-source status, `none` or `Backlog` to
     `In progress`, never a later status). Ineligible: stop and report what was seen (`state`, `<cur>`, the
     pick-source status or the labels) and that the lane is ineligible; recommend `/lane-cleanup <n> --abandon`.
     Do not run it: abandoning a lane is the caller's decision, never a side effect of `/lane-start`.
5. **Successor note.** When `owner` is `dead`, step 11 reports a `dead-owner` finding for `#<n>` itself: the ledger
   has no hand-off event yet (#5833). Report it verbatim; do not card that one finding, because this session is
   the successor it asks about. Card any other finding as step 11 says. When that is the ONLY finding, treat
   the run as rc 0 for card purposes (an existing `Lane orphans: <repo>` card is resolved, not replaced).

## Card procedure (steps 4, 9B and 11, sections A and B)

Card only what genuinely needs the operator; anything an agent can do is agent work. Uncommitted peer edits (step 9's Step A)
and a `lane-busy` caused by this session are stop, report and retry later, never a card.
1. Use main step 2's `operator_input.*` values (the manifest read there, not this card procedure's own numbering).
   They were read with `--repo <main>`, so `.path` and `.open_path` are
   absolute. `.path` must start with `<main>/` and must not contain `/.claude/worktrees/`: cards go to the main
   tree's surface, never a lane's copy (a lane carrying the file would be dirtied, and its reap would refuse
   `dirty-tree`).
2. **Multi-lane cards (sections A and B, and the step 11 orphan card).** These cards can name MULTIPLE lanes at
   once (the prune card lists every abandoned lane; the stuck card lists every stuck lane; `lane_orphans.sh` can
   report more than one `orphan-worktree` or `dead-owner` finding across different lanes in one run) and carry a
   FIXED title prefix per condition, so the condition can be matched mechanically rather than by re-parsing prose:
   - `abandoned-backlog` (section A): title starts exactly `Lane prune (abandoned-backlog): <repo>` (`<repo>` is
     `github.repo` from main step 2).
   - `cap-reached` (section B): title starts exactly `Lane stuck: <repo>`.
   - orphan findings (step 11, and `/lane-cleanup` section 5): title starts exactly `Lane orphans: <repo>`.

   These three are REPO-LEVEL prefixes (`<repo>`, not an issue number) precisely because they are multi-lane.
   **Step 9's diff-gap card is the one exception in this file: it is PER-ISSUE, not repo-level.** Its title EQUALS
   `Lane diff-gap: #<n>` exactly (an issue number, never `<repo>`; matched as the whole title, never as a prefix), its `refs` is always exactly `["#<n>"]`, and it never
   names another lane. Do not fold it into this multi-lane bullet's `refs` guidance below, which governs only the
   three repo-level cards; step 9 states its own dedupe (exact title + `#<n>` in `refs`) independently.

   `refs` holds ONLY the issue numbers of the lanes actually named on the card (e.g. `["#12", "#37", "#41"]`) —
   never the issue that triggered this run unless that issue is itself one of the named lanes. For sections A and B
   the triggering run's own issue is normally not a named lane (the lane that hit the cap is a NEW issue, not yet a
   lane at all). For an orphan card, `<n>` goes in `refs` ONLY when an actual `lane_orphans.sh` finding names
   `#<n>` — never automatically, and never for Resume step 5's own `dead-owner` finding about `<n>` itself, which
   is reported verbatim and never carded at all (Resume step 5). `refs` names every OTHER lane the findings cover
   alongside `<n>` when `<n>` does qualify. `/lane-cleanup <m>` for any one of
   these named lanes finds the card only by searching for `#<m>` in `refs`, so a lane missing from `refs` is a card
   that lane's own cleanup can never find or resolve.
3. **Dedupe (at most one open card of each kind per repo — the three REPO-LEVEL cards only; step 9's diff-gap card
   is per-issue and states its own dedupe there, not here).** Search the open cards for one whose title starts
   with this condition's exact prefix (card-procedure step 2's `Lane prune (abandoned-backlog): <repo>`,
   `Lane stuck: <repo>` or `Lane orphans: <repo>`) —
   there is at most one such open card per repo per condition, by construction, because every run that would post a
   second one instead finds and updates the first. If one exists:
   - **Exception, `Lane orphans: <repo>`: REPLACE, not merge.** The orphan card mirrors the latest
     `lane_orphans.sh` run, so step 11 (and `/lane-cleanup` section 5) replaces its `refs` and findings list with
     the current ones, using the orphan replace snippet below. The merge rule that follows applies only to the
     prune and stuck cards.
   - **Any lane overlap, or none (prune and stuck cards).** Whether or not this run's named lanes overlap the existing card's `refs`, this
     IS the card for this condition in this repo: never post a second one. Merge this run's named lanes into the
     existing card's `refs` and body (add any lane not already listed; leave any already-listed lane's existing
     entry alone unless this run has new evidence for it), append a dated update paragraph describing what changed,
     and report the existing card's number instead of adding a card.
   - **Update snippet** (`decisions_json`; the generator has no subcommand for editing an existing card, so this
     hand edit follows `decisions_rules.md`'s "Hand-editors" paragraph: it takes the generator's `.hub.lock` flock
     and reads the files only AFTER taking it, edits only through `json.loads`, VALIDATES the result with the
     generator's own `_validate_decisions_schema` before anything is written, and writes through the generator's
     `_write_json_atomic` (canonical bytes, unique temp file + `os.replace`). A body that breaks the Markdown
     rules leaves the file untouched and prints the validator's message instead; fix the text and re-run. The
     update text goes in a QUOTED heredoc file, never a command-line or JSON string):
     ```bash
     u=$(mktemp) && cat > "$u" <<'EOF'
     Dated update: ...
     EOF
     python3 - <path> <main> <existing card no> "$u" '#<m>' '#<p>' <<'PY'
     import fcntl, importlib.util, json, os, sys
     from pathlib import Path
     p, main, no, uf, add_refs = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
     assert os.path.isabs(p) and os.path.isabs(main) and p.startswith(main + os.sep), "need the ABSOLUTE <path> inside <main>"
     hub = os.path.dirname(p)
     lk = open(os.path.join(hub, ".hub.lock"), "a"); fcntl.flock(lk, fcntl.LOCK_EX)  # the generator's lock; read only AFTER taking it
     spec = importlib.util.spec_from_file_location("gen_operator_hub", os.path.join(main, "scripts", "gen_operator_hub.py"))
     g = importlib.util.module_from_spec(spec); sys.modules["gen_operator_hub"] = g; spec.loader.exec_module(g)
     d = json.loads(open(p, encoding="utf-8").read())
     arch = json.loads(open(os.path.join(hub, "decisions_archive.json"), encoding="utf-8").read())
     card = next(c for c in d["open_cards"] if c["no"] == no)
     for ref in add_refs:
         if ref not in card["refs"]:
             card["refs"].append(ref)
     card["body_md"] = card["body_md"].rstrip() + "\n\n" + open(uf, encoding="utf-8").read().strip()
     try:
         g._validate_decisions_schema(d, arch)
     except SystemExit as e:
         sys.exit(f"NOT WRITTEN, {p} untouched: {e}")
     g._write_json_atomic(Path(p), d)
     print(f"updated #{card['no']}")
     PY
     rc=$?; rm -f "$u"; echo "edit rc=$rc"
     ```
   - **Orphan replace snippet** (`decisions_json`; same locking, validation and file-input contract; the `refs`
     are passed as the trailing arguments and REPLACE the card's refs):
     ```bash
     o=$(mktemp) && cat > "$o" <<'EOF'
     The full card-procedure step 5 body for the CURRENT findings (the ask, the commands, the default)...

     Dated update <date>: findings list replaced by this run.
     EOF
     python3 - <path> <main> <existing card no> "$o" '#<m>' ... <<'PY'
     import fcntl, importlib.util, json, os, sys
     from pathlib import Path
     p, main, no, of, refs = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
     assert os.path.isabs(p) and os.path.isabs(main) and p.startswith(main + os.sep), "need the ABSOLUTE <path> inside <main>"
     hub = os.path.dirname(p)
     lk = open(os.path.join(hub, ".hub.lock"), "a"); fcntl.flock(lk, fcntl.LOCK_EX)  # the generator's lock; read only AFTER taking it
     spec = importlib.util.spec_from_file_location("gen_operator_hub", os.path.join(main, "scripts", "gen_operator_hub.py"))
     g = importlib.util.module_from_spec(spec); sys.modules["gen_operator_hub"] = g; spec.loader.exec_module(g)
     d = json.loads(open(p, encoding="utf-8").read())
     arch = json.loads(open(os.path.join(hub, "decisions_archive.json"), encoding="utf-8").read())
     card = next(c for c in d["open_cards"] if c["no"] == no)
     card["refs"] = refs
     card["body_md"] = open(of, encoding="utf-8").read().strip()
     try:
         g._validate_decisions_schema(d, arch)
     except SystemExit as e:
         sys.exit(f"NOT WRITTEN, {p} untouched: {e}")
     g._write_json_atomic(Path(p), d)
     print(f"replaced #{card['no']}, refs now {card['refs']}")
     PY
     rc=$?; rm -f "$o"; echo "edit rc=$rc"
     ```
     For `decisions_markdown`, prune and stuck cards only: edit the existing `### [N]` entry's body in place (append
     the dated update paragraph and, if the surface tracks a lane list inline, add the new lane there too); there is
     no separate regen step for that surface.
   - **`decisions_markdown` surfaces (CSA): create uses card-procedure step 4's snippet; everything else is a direct
     edit.** Appending an update, replacing an orphan card's findings, and resolving a card are done by this
     session with the Edit tool, directly in the file. To resolve, move the `### [N]` block to the TOP of
     `## Archived` (newest first), append a dated resolution paragraph, and update both counts. After any edit, `open` the file. This is agent work, never an operator task. The edit
     becomes an open item in the report only if it fails, and then it names the entry and the exact text.
   - A card for the SAME repo under a DIFFERENT condition (e.g. an existing dirty-tree refusal card from
     `/lane-cleanup`, which carries neither fixed prefix) is a different card, never matched by this dedupe.
   - After a `decisions_json` edit: a new card (`add-card`) and an archive (`archive`) regenerate the hub
     themselves, so run no separate regen; an in-place update or orphan replace is followed by
     `(cd <main> && <regen_command>); echo "regen rc=$?"`. Every `decisions_json` edit is followed by
     `open <open_path>`, as in card-procedure step 4; a `decisions_markdown` surface is opened after any edit.
4. **By `operator_input.kind`** (new card only — no existing card matched card-procedure step 3's dedupe, or
   step 9's dedupe for the diff-gap card, whose title is exactly `Lane diff-gap: #<n>` and whose `refs` is
   `["#<n>"]`):
   - `decisions_json`: first read the surface's rules file, `decisions_rules.md` in the same directory as `.path`.
     `title` is plain text and starts with card-procedure step 2's fixed prefix; `body_md` is Markdown (no
     level 1-3 heading, no raw HTML tag; the `*_html` fields are retired and a schema error). `refs` carries every named lane's issue (card-procedure step 2), never
     the triggering issue unless it is itself a named lane. Create the card ONLY with the generator's locked
     `add-card` subcommand, never by hand-editing `decisions.json` (a hand edit races other sessions and can lose
     their cards); it takes the next permanent card number and appends the card in one locked step, validates both
     data files and regenerates both `.md` files. `<regen_command>` is root-relative (`python3
     scripts/gen_operator_hub.py`), so it runs from `<main>`, and rc must be 0:
     ```bash
     b=$(mktemp) && cat > "$b" <<'EOF'
     <card body, Markdown>
     EOF
     tf=$(mktemp) && wf=$(mktemp) && cat > "$tf" <<'EOF'
     <the exact title prefix of the condition per card-procedure step 2, which already ends in the repo; or, for step 9, exactly Lane diff-gap: #<n>>
     EOF
     cat > "$wf" <<'EOF'
     /lane-start (<session>)
     EOF
     t=$(<"$tf"); w=$(<"$wf"); rm -f "$tf" "$wf"
     (cd <main> && <regen_command> add-card --title "$t" --body-file "$b" --asked-by "$w" \
       --ref '#<m>' --ref '#<p>' ...); echo "add-card rc=$?"
     rm -f "$b"
     ```
     The title and `--asked-by` are single-line values read from QUOTED-heredoc temp files into variables (`$(<file)`; a heredoc inside `$(...)` breaks on an apostrophe in bash 3.2) and passed as
     `"$t"` / `"$w"` (a double-quoted expansion is never re-parsed, so an apostrophe, a backtick or `$HOME` in
     the text stays literal; single quotes would break on an apostrophe). Never splice untrusted text into the
     command line itself, and write any multi-line or free text to the quoted-heredoc `--body-file`. Keep each `--ref` in the `'#<m>'` form, so `/lane-cleanup`'s search for `#<m>` in `refs` finds the card
     (a bare digit would be stored as an integer). Then `open <open_path>` (or `open <path>` if the manifest sets no
     `open_path`). No separate regen is needed after `add-card`.
   - `decisions_markdown`: add a new entry at the top of `## Open` in `.path`, `<title>` starting with
     card-procedure step 2's fixed prefix exactly as in the `decisions_json` branch above (the same
     mechanical-match reasoning applies: a `### [N] Lane prune (abandoned-backlog): <repo>` heading is what
     card-procedure step 3's dedupe searches for on this surface). `N` is the max existing `[N]` + 1, and the
     `**Open:**` count goes up by one. Match an existing
     entry's shape: bold lead-in paragraphs, the exact commands, the default if unanswered, and a closing
     "Posted by session <label>, <date>." line. There is no regen step. After the write, run `open <open_path>` if
     the manifest sets one, otherwise `open <path>` (the queue file itself), as runtime CLAUDE.md §11 and the
     repo's own CLAUDE.md require whenever a card lands.
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
5. **Body:** what is blocked, why only the operator can decide it, the exact command(s), what runs on approval, and
   the default if unanswered.
6. **Approval.** A carded command runs only after the operator explicitly approves THAT card. An approval never
   carries over to a later push, PR or merge (runtime CLAUDE.md §4, §11). A resolved card is archived with the
   operator's verbatim answer, or with an honest non-verbatim note, per the surface's lifecycle rules.

## Failure modes: where each stop leaves things

| Stop | Lane opened | Comments posted | Card |
|---|---|---|---|
| 1 bad argument; 2 inside a worktree, main unresolvable, manifest key or pick-source shape bad | no | none | none |
| 3 lane already abandoned | no new lane | none | none |
| 4 cap precheck hits `lane.max_open`, `lane.max_abandoned`, or both at once | no | none | stuck card if any (`cap-reached`, section B) AND/OR prune card (`abandoned-backlog`, section A) — both run and both card in the same turn when both caps are hit |
| 5 issue read fails; 6 issue not OPEN | no | none | none (6: a stale `Lane diff-gap: #<n>` card is resolved) |
| 7 draft post fails | no | none | none |
| 8 lane files undetermined; 8 frontend-scoped lane files (frontend rule) | no | AC/UAT draft if posted | none |
| 9 fetch fails, detached HEAD, git error, Step A output | no | AC/UAT draft if posted | none |
| 9 Step B not clean | no | AC/UAT draft if posted; diff-gap result | diff-gap card |
| 10 rc != 0 refusal | no | AC/UAT draft if posted; diff-gap result | prune card (`abandoned-backlog`); stuck card if any (`cap-reached`) — expected only when the count changed since step 4's precheck |
| 10 rc 0 plus an unreachable warning | yes, unentered | as above | none |
| 11 orphan rc 2 | yes, unentered | as above | none |
| 12 EnterWorktree fails | yes, unentered | as above | orphan card if rc 1 |
| 13 board move fails | yes, entered | as above | orphan card if rc 1 |
| Resume 1-4: foreign owner, a read fails, issue not OPEN, unentered and ineligible | yes (existing), not entered | none new | none |
| Resume, then step 11, 12 or 13 fails | yes (existing) | none new | as rows 11-13 (an entered lane skips 13) |
