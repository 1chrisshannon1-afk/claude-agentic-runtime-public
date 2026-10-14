# Worktree integration flow (optional path)

**2026-09-16 (operator ruling): this is no longer the default.** Mandatory per-unit-of-work
worktree isolation (operator directive 2026-09-10, described below) was retired for speed —
sessions and sub-agents now work directly in the main tree by default. The mechanics in this file
apply ONLY when a worktree is opted into for one of the narrowed cases in `~/.claude/CLAUDE.md`
§2 (a wave of concurrent writing sub-agents, an abortable unit of work, or an unattended job's
verification lane) — they are not retired, just no longer standing default behavior.

Companion to `~/.claude/CLAUDE.md` §2's worktree bullet. That bullet states the rule; this file
holds the mechanics, the MERGE CARD schema, the integrator recipe, the reasons, and the known
gap. Every claim here was verified by execution on 2026-09-10 unless marked UNVERIFIED.

## Lane worktrees are a separate mechanism — see `lane.sh`, not this flow

A lane is CLAUDE.md §2 case (d): one operator-hand-picked issue in its own worktree and branch, opened and reaped
ONLY through `~/.claude/scripts/lane.sh`. It is a different object from the MERGE-CARD worktrees this file describes,
and none of this file's mechanics apply to it (adoption master plan §7.1, §7.4-§7.6; sprint rows L5.2, L5.4, L5.5).

- **Ledgered.** Every `open`, `abandoned` and `reaped` transition appends one row to `~/.claude/.lanes/lanes.jsonl`;
  only `lane.sh` writes it. `~/.claude/scripts/lane_orphans.sh` reconciles the ledger against disk, read-only.
  Both scripts resolve the repo from their cwd, so they run from the main tree, never from inside a lane.
- **Integrates only through a GitHub PR merge to the repo's `lane.pr_target`, as a merge commit.** Never squash, never
  rebase, and never the patch-based MERGE CARD round-trip below. A lane commits on its own branch and holds those
  commits until its PR merges. Each push, PR and merge is its own carded operator ask (runtime CLAUDE.md §4; hub card
  53, option a, set that mechanism). A lane PR references its issue as `Refs #<n>`, never with a closing keyword (the
  PR card checks the body for all three closing-reference forms), so the PR itself does not close the issue;
  `/lane-cleanup`'s MERGED path normally closes it with `gh_issue.sh resolve`, which verifies the merge sha. The issue
  can also close another way: a closing keyword in a lane commit message closes it when the merge lands on the default
  branch (the PR card checks the lane's commit messages and names such a commit), and anyone can close it by hand. The
  MERGED path then does not re-close it; it posts the completion comment citing the merge sha. A later standing
  operator ruling that holds lane pushes or PRs suspends those asks. Lane rulings are cross-repo: one recorded on any
  lane-enabled repo's operator surface binds every lane-enabled repo unless it scopes itself to another, so
  `/lane-cleanup` searches the surface of every lane-enabled repo in the repo registry
  (`knowledge/repo_registry.json`, each repo's surface read from its manifest) before carding any. As of 2026-09-24,
  Agency hub #57 holds lane pushes and PRs in every lane-enabled repo until the CI-efficiency work lands, after which
  one PR per lane resumes. The PR card's CI and the merge card's deploy consequence are derived, after a fetch, from
  the workflow triggers in the actual merge result (`git merge-tree --write-tree <base_ref> <lane head>`, the tree
  that GitHub's PR merge ref and the merge commit carry), with the changed files from a local
  `git diff --no-renames --name-only <base_ref>...<lane head>`. `pull_request_target` uses the base branch's copy. A
  merge with conflicts, or over 300 changed files (GitHub's paths filters read only the first 300), prints `UNKNOWN`
  and posts no card.
- **Reap gate: ancestry, a clean tree, and nobody standing in it.** `lane.sh reap` refuses unless
  `git merge-base --is-ancestor <lane tip> <lane.base_ref>` holds, `git status --porcelain` is empty with exit 0,
  and no process has files open under the worktree. A squash-merged lane fails the ancestry check and is
  `needs-manual-reap`. Never `--force`, never `discard_changes: true`.
- **Exit and removal.** A lane is always left with `ExitWorktree` action `"keep"`. It is removed only by
  `lane.sh reap` or `lane.sh reap --abandoned`. `lane.sh abandon` is ledger-only and deliberately KEEPS the
  worktree. An abandoned lane holding unmerged work, or one `lane.sh` reports as `needs-manual-reap`, goes to the
  operator (CLAUDE.md §2 case (d)).
- **Extra lane links (`lane.link_paths`, optional).** `lane.sh open` symlinks each repo-relative path the
  manifest lists into the new lane, the same way it links `node_modules`, and writes a bare exclude line for each
  (a symlink is not a directory to git, so a `dir/` ignore pattern does not match it). Agency lists its CI venv
  (`agency/backend/.venv_py313_ci`) and the two gitignored PII lists, which a lane otherwise runs without: no
  pre-push PREFLIGHT tools, and a PII scan with no operator denylist. The key is read without `cfg()`, so a repo
  with no key (CSA today), an empty list or a malformed value opens exactly as before — `lane.link_paths` and the
  push-check key below (`lane.prepush_check`) are the two named, deliberate exceptions to "a missing `lane.*` key is
  a refusal": both are read tolerantly, never via `cfg()`. Each entry is normalized (a leading `./` and a trailing
  `/` are stripped) before validation, and refused per-entry, never repo-wide, when it is absolute, contains a `..`
  segment, resolves outside the repo root, contains a glob character (`* ? [ ]`), starts with `#`, `!` or `-`, or
  contains whitespace; a path missing from the main tree is skipped with a warning. An entry already present at the
  lane's destination is recorded (and excluded) ONLY when it is a symlink whose target matches this entry's own
  source — a freshly-created link, or an already-correct one from a prior `open` on the same lane; real content
  (tracked or untracked) already sitting at that path, or a symlink to a DIFFERENT target, is warned about and left
  alone, never recorded and never given an exclude line (recording it would silently hide future untracked content
  at that path from the main tree's own `.git/info/exclude`). Links are never copies: never `pip install` inside a
  lane, which would write through the link into the main tree's venv. `reap` and `abandon` need no extra teardown;
  removing the worktree removes the links without following them.
- **Pre-push check (`lane.prepush_check`, optional, read by `/lane-cleanup` — never by `lane.sh` itself).** Names a
  venv, a freshness-check script and a lockfile location so `/lane-cleanup`'s 6.1 push card can run a
  venv-freshness check and `pip-audit` from the lane's own linked venv immediately before pushing, with no
  repo-specific path ever hardcoded into the runtime skill. A repo with no key configured (CSA today) runs no
  pre-push check at all; `lane.sh` never reads this key and has no code path that touches it.
- **The three lane skills own the lifecycle:** `/lane-start` (AC/UAT draft, diff-gap pre-flight, `lane.sh open`,
  orphan check, enter, In progress; re-run on an open lane, it resumes or re-enters it), `/lane-save` (a new
  `## Lane state` comment per save), and `/lane-cleanup` (read-only dry-run, then one cell of a PR-state x
  `--abandon`/`--update` matrix, ending with `lane_orphans.sh`), in `~/.claude/skills/lane-start/SKILL.md`,
  `lane-save/SKILL.md` and `lane-cleanup/SKILL.md`. An open lane PR's cell is itself a decision on `mergeStateStatus`:
  `CLEAN` cards a merge, `BEHIND` with `--update` runs a merge-slot update (a guarded `git merge` of the base into
  the lane, the one sanctioned `git merge` call in either skill) before carding a push, `BEHIND` without `--update`
  reports and waits for the merge slot, and any other status reports and waits for a later run. A PR counts as a lane's only when it was created at or after the lane's last open: an issue
  re-picked after a reap reuses its branch name, and an earlier lane's PRs on that name are ignored. A PR closed
  unmerged never abandons a lane by itself: `/lane-cleanup <n>` WITHOUT `--abandon`, run against only-closed PRs
  and the lane still `open`, stays on the IN-PROGRESS path — the lane is not abandoned, and this is where a board
  left at `In review` by the closed PR goes back to `In progress` (never a board move `--abandon` makes). Running
  `/lane-cleanup <n> --abandon` in that same state instead takes the ABANDON path, whose own board reset (below)
  sends a worked lane's issue to `Backlog`, not `In progress`. Every board move reads the board first and calls
  `gh_issue.sh transition` only when the status differs, because the helper posts a status comment on every call. The
  abandon's board reset reads the board, not the reason: a worked lane's issue (`In progress`, `In review` or `Done`)
  goes to `Backlog`, and a never-entered lane's board is left alone. **Exception: when the issue is CLOSED (the
  cell's P7 precondition) — without `--abandon`: carded "closed while un-reaped", nothing else; with `--abandon`:
  takes the ABANDON path (A3's reap attempted, any refusal carded; an open PR still gets REFUSE+CARD), board
  never moved.** Only the board-reset sub-step is skipped on the `--abandon` path; the
  reap is still attempted and the ledger's `abandoned` row still written. An abandoned lane has no owner: any session's
  `/lane-cleanup <n> --abandon` reaps it, guarded by the reap's ancestry, clean-tree and busy checks, and makes any
  board reset the abandoning run did not make. A session LAUNCHED inside a lane worktree cannot reap it: its own CLI
  process holds the lane as its cwd, which the reap's busy check counts, and neither `ExitWorktree` nor a shell `cd`
  moves it. Clean up from a session launched in the main checkout.

Both mechanisms share the runtime worktree rules (nested at `<repo>/.claude/worktrees/`, never
`discard_changes: true`, exit `keep` while unintegrated) and both are opt-in narrowed cases under CLAUDE.md §2. Do
not mix their recipes: inside a lane worktree, follow the lane skills, not the MERGE CARD protocol below.

## The rule in one paragraph (as it applied during the 2026-09-10–2026-09-16 mandatory-default period; still the mechanics for opt-in use)

Every session and every WRITING sub-agent does each unit of work in its own nested worktree
(`<repo>/.claude/worktrees/<name>/`, branched from local HEAD via `worktree.baseRef: "head"`).
Reviewer dispatches stay non-isolated foreground dispatches. Nobody commits in a worktree and
nobody records a review there. When the work passes (tests green, review clean), the session
freezes the reviewed paths, pins the review-time digest, and hands a MERGE CARD to the live
coordinator session, which integrates it into the main tree with ONE review record and ONE
path-scoped commit, then announces CLEAR. The session reverse-applies the patch in its worktree
and removes the worktree. The main tree is the integration tree, not a workbench. The only
main-tree work is a train that needs an installed `node_modules` (a worktree carries none).

## Why the commit is made in the integration tree, not the worktree

1. **Ledger keying.** `record_review.py` writes `<git rev-parse --show-toplevel> precommit:<digest>
   …`, and gate 3b (`precommit_review_gate.decide` → `record_review.head_review_outcome`) looks the
   entry up under the committing checkout's toplevel. A worktree-recorded review is therefore
   invisible from the main tree (executed: `precommit:3a46d62ce8c8c67e` — worktree root →
   `('clean', 0)`, main root → `None`; 12 such worktree-only keys in the live ledger).
   The digest itself (`sha256` of `git diff HEAD -- <paths>` text plus untracked material) is
   staging-invariant for tracked paths and staging-SENSITIVE for untracked ones (an untracked
   file contributes `--- untracked <path> size=…` grammar; once staged it contributes a real `A`
   diff — executed 2026-09-10), which is why BOTH sides pin/compare with new files staged. It is
   identical for identical content in both checkouts (live ledger: `precommit:da2d57c377323553`
   under both the main root and `.claude/worktrees/dedupe-commit`).
2. **`--rekey` cannot bridge two checkouts.** It resolves the prior entry under the CURRENT
   toplevel (`record_review.py` ~L2388) and refuses `rekey-no-prior-entry`; it is also gated on
   an untracked→staged transition that most integrations never have.
3. **Double-recording is the forgery shape.** `audit_review_attribution._find_reused_pairs` is
   repo-blind: two `clean` entries citing one `(agent_id, tool_use_id)` pair — one per checkout —
   both land `reused` (executed 2026-09-10: `matched: 0, reused: 2`). A cross-repo `rekey=` field
   does not exempt them (`_root_star_groups` is a same-repo lookup). So a worktree record PLUS a
   main-tree record would flag 100% of integrations and drown the audit's real signal.
4. **Reapability.** `ExitWorktree action: "remove"` refuses when the worktree still holds
   uncommitted files or unmerged commits (rule (2)'s wording; UNVERIFIED by execution — from
   the tool's own description), and `discard_changes: true` is forbidden. A
   worktree that committed locally is un-reapable forever (its sha is never an ancestor of the
   main branch, because integration is a path-scoped `git apply` + fresh commit). A worktree that
   never committed is returned to clean by `git apply -R <patch>` and removed normally.

Hence: ONE record, ONE commit, both in the integration tree, made by the integrator after proving
digest equality; the worktree carries no commit and is always reapable.

## Session side (in the worktree)

1. `EnterWorktree name=<session>-<topic>`; `source <repo>/.venv/bin/activate`.
2. Edit; tests green; dispatch the reviewer of record (`code-reviewer`, or `trust-architect` on a
   trust surface) as a plain foreground dispatch — from inside the worktree it reads the worktree.
   Fix-round ladder per §10 applies unchanged.
3. When the review is clean: STOP editing the reviewed paths. **`git add -- <paths>` first** — `git diff HEAD` omits untracked files, so an unstaged NEW file never enters the patch while `pending_key` does fold it in; staging first is what makes the patch and the key describe the same bytes. Then pin the review-time content:

   ```
   python3 -c "import sys,os;sys.path.insert(0,os.path.expanduser('~/.claude/hooks'));import precommit_review_gate as g;r=os.popen('git rev-parse --show-toplevel').read().strip();print(g.pending_key(r,os.getcwd(),sys.argv[1:]))" <paths>
   ```

   prints `precommit:<digest>` (or `None` if nothing is pending, or `__unresolvable__`). It passes
   the REAL cwd exactly as gate 3b does (`decide` → `pending_key(repo_root, cwd, paths)`), so
   relative pathspec tokens resolve identically — **run it from the repo root with the same
   literal tokens the integrator will pass to `git commit`** (executed 2026-09-10: the same two
   files gave `None` from the root and a real key from a subdirectory when the tokens were
   subdirectory-relative).
4. Send the coordinator the MERGE CARD (below). Do not commit. Do not record.
5. On `CLEAR <sha> <patch>`: `git apply -R --index <patch>` in the worktree (`--index` is
   required — bare `-R` reverses the working tree but leaves the index, so `git status` shows
   `AD`/`MM` and `remove` refuses; verified by execution 2026-09-10), confirm `git status` is
   clean (delete scratch files you made), `ExitWorktree action: "remove"`. Open a fresh worktree
   from the new HEAD for the next unit.

## MERGE CARD — six rows, all required; the reviewer-identity row carries five values (type, agent id, tool_use id, round, warm-streak), all required; a card missing any is refused, not guessed at

| field | example |
|---|---|
| worktree path | `/…/ExampleApp/.claude/worktrees/5f-round-36` |
| branch | `worktree-5f-round-36` |
| exact pathspec | `modules/x/a.py modules/x/tests/test_a.py _Config_Project/docs/…md` |
| review-time key | `precommit:23be94181b2bf6b0` |
| reviewer identity | `code-reviewer · agent a1e5…253 · tool_use toolu_017Q… · round 2 · warm-streak 1` |
| commit subject + issue | `fix(engine): … (#5217)` |

`round` is the fix-round number; `warm-streak` is how many CONSECUTIVE warm rounds ended the
chain (0 for a cold final round). The integrator REFUSES a card whose warm-streak exceeds 2 —
see "warm-round cap" under Known gaps.

## Integrator side (in the main tree)

1. Announce the train to every live peer (§3) — paths, rough duration.
2. `git -C <wt> diff HEAD --binary --find-renames -- <paths> > <patch>`; refuse if the worktree's
   `git diff --name-only HEAD` touches any path outside the declared pathspec, and refuse if
   `git -C <wt> status --porcelain -- <paths>` shows any `??` entry (an untracked new file would
   be silently omitted from the patch).
3. **First `git add -- <every unstaged tracked path THE PATCH TOUCHES>`** — `git apply --3way`
   refuses a path whose working tree differs from the index (`error: <path>: does not match
   index`, executed 2026-09-10; a dirty path the patch does NOT touch applies fine — also
   executed). Then, separately and for a different reason, `git add` every OTHER currently-
   unstaged tracked path by name to empty the pre-commit stash set (ADD only, never unstage a
   peer's staged path). Then `git apply --3way --check <patch>` — ADVISORY ONLY: executed
   2026-09-10, it returns 0 for a patch that then applies WITH CONFLICTS — then
   `git apply --3way <patch>` and CHECK ITS EXIT STATUS: nonzero, or any `U` path in
   `git status --porcelain`, means the merge conflicted — do NOT `git add` (staging a `U` path
   silently commits `<<<<<<< ours` markers; a path-scoped commit accepts them, executed and
   confirmed). Apply is not a git state verb (gate 1 allows it).
   A conflict — and equally a CLEAN 3-way merge that absorbed a peer's same-file change
   (executed 2026-09-10: correct merged content, keys differ; an unrelated-file peer commit
   leaves key equality intact) — means the card's key can no longer match: the integrated bytes
   are legitimately not the reviewed bytes. Do not resolve or wave through; reverse and send the
   card back for a fresh worktree from the current HEAD + re-review there.
4. `git add -- <paths>` (new files need it, and the card's key was pinned with them STAGED — see
   step 3 on the session side — so main must stage them too before comparing).
5. Compute the main-tree pending key for the identical pathspec (same one-liner, from the repo
   root, same literal tokens). It MUST equal the card's key. Equal ⇒ the integrated bytes are the reviewed bytes. Not equal has two causes,
   checked in this order: (i) the patch is incomplete — a NEW file was left unstaged in the
   worktree so `git diff HEAD` omitted it (proven end-to-end 2026-09-10: `apply --3way` reports
   success and the file is simply absent); confirm with `git status --porcelain` there, `git add`
   it, re-cut the patch — NO re-review, the content never changed; (ii) the worktree genuinely
   changed after review: `git apply -R --index <patch>`, `git restore --staged -- <paths>`,
   refuse, send back for re-review; (iii) main already carried a peer edit on a shared path and
   `--3way` merged reviewed bytes with unreviewed ones (confirm with `git diff HEAD -- <paths>`
   showing hunks the patch never carried) — same reversal, but the session goes to a FRESH
   worktree from the current HEAD, re-applies its own patch with `--3way`, resolves, re-reviews
   there. (`git apply -R --index <patch>` alone returns index and working tree to the pre-apply
   state — executed: status empty afterwards; `git restore --staged` is only needed for OTHER
   paths you staged in step 4, and exits 1 as a no-op otherwise.) An unexplained mismatch is a
   refusal, never a wave-through. Never re-review in the
   integration tree to resolve a mismatch — that re-creates the two-record `reused` shape.
6. Record ONCE, in the main tree, citing the card's identity verbatim (never invented, never
   omitted — an omitted identity lands `no-identity`, also flagged):
   `python3 ~/.claude/hooks/record_review.py <repo-root-abs-path> --pre-commit --clean --paths
   <paths> --reviewer <type> --reviewer-agent-id <id> --reviewer-tool-use-id <id> [--round <n>]
   < /dev/null` as its OWN tool call (never chained with the commit; stdin redirected or it
   hangs). The repo root is an EXPLICIT positional — with none, it records against the cwd, and
   a shell sitting inside a worktree would write the invisible worktree-keyed entry. The three
   identity fields are three separate flags, never hand-joined (`parse_reviewer_value` splits on
   `#`; a malformed compound degrades SILENTLY to `no-identity`, flagged); copy them from the
   pacer's `~/.claude/.agent_budget/spend.jsonl` dispatch row, never retype. Pass `--round <n>`
   from the card; do NOT pass `--prev`/`--warm` — both require a prior ledger entry under the
   committing toplevel, and this flow never records one (rounds happen in the worktree,
   unrecorded), so the entry legitimately carries `round=N` with no `prev=`.
7. Write the message file with the Write tool; bare single-line
   `git commit -F <msgfile> -- <literal paths>` with **nothing after the pathspec**. A trailing
   REDIRECT (`2> file`, `> file`) is absorbed as a pathspec token (executed 2026-09-10) and can
   make gate 3b mis-key and FAIL OPEN — an unreviewed commit landing silently, per CLAUDE.md
   §3(iii). A pipe is a segment boundary and is not absorbed, but keep the line bare regardless.
   A `too-many-files` (>30 paths) or `too-many-top-dirs` (>4 top-level dirs) deny is a SWEEP
   threshold that applies to an explicit pathspec exactly as it does to a staged index (executed
   2026-09-10: `_decide_with_pathspec` routes both through `_sweep_decide`) — it means the TRAIN
   IS TOO BIG, not that your pathspec went missing; split it. Only when the deny lists paths or
   dirs you did NOT name did the gate judge the staged index instead (missing-pathspec branch) —
   then re-issue with a pathspec. ≤4 top-level dirs and ≤30 paths per train.
8. Announce `CLEAR <sha> <patch path>` to the session and every peer.

Never `git merge` / `pull` / `cherry-pick` / `am` / `revert` a worktree branch: none is a `git
commit`, so gates 3/3b/4 never see them (tracked P1, unchanged).

## Coordinator identification

There is no mechanical coordinator marker. A session that needs a merge runs `ListAgents` and
asks by `SendMessage` which live session holds the integration lane for this repo; the session
that answers "coordinator" is it. If none answers, the session announces it is taking the lane,
waits briefly for objection, and integrates itself with the recipe above. The coordinator itself
works in the main tree (it owns integration) — the one standing carve-out from "every session in
its own worktree".

## Known gaps (tracked)

- Ledger keyed by toplevel, not `git rev-parse --git-common-dir` — the same re-keying
  `file_claims.mutex_token()` awaits. A cross-checkout carry-forward (`carried_from=<key>`) with
  an `audit_review_attribution` exemption would let a worktree self-record; until then the
  single-record-in-main flow above is the honest path.
- No CLI prints the pending key; the one-liner above is the interface (cwd-sensitive — always
  from the repo root).
- **Corroboration window vs hand-off latency.** `audit_review_attribution.DEFAULT_WINDOW_SECONDS`
  is 1800s from the reviewer's dispatch row to the record's `ts=`; this flow inserts a
  coordinator queue between them, so a train that waits >30 min lands `unmatched` despite being
  legitimate (executed 2026-09-10: 29 min → `matched`, 35 min → `unmatched`). Run the audit with
  `--window-seconds` widened to the observed hand-off p95, or raise the default — tracked on
  #5261; do not read this flow's `unmatched` counts as findings until then.
- Whether `EnterWorktree` re-resolves `CLAUDE.md`/settings for a session is UNVERIFIED (§2 note
  of 2026-08-28). The PreToolUse chain is global (`~/.claude/.enforce`) and `core.hooksPath` is
  absolute, so gates fire regardless; only rule loading is in question.
- No gate checks whether a session is in a worktree; the rule is prose-enforced.
- **The warm-round cap is not enforceable across the hand-off.** `record_review.py`'s
  `_consecutive_warm_round_count` walks `prev=` links under the COMMITTING toplevel; since no
  round is recorded in the worktree, the walk returns 0 (executed 2026-09-10) and
  `_MAX_CONSECUTIVE_WARM_ROUNDS` never fires, and `churn_report.py` metric 7's `warm=` field stays
  empty for these boundaries. Until a cross-checkout carry-forward exists (#5261), the reviewing
  SESSION counts its own warm rounds in-conversation and refuses a third itself; the card's
  `warm-streak` field carries the count; the integrator refuses a card with warm-streak > 2.
