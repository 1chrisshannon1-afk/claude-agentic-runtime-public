# Review-gate and commit-boundary incident history (extracted from CLAUDE.md, 2026-09-08)

## 1. The 2026-08-28 multi-session worktree data-loss incident (from CLAUDE.md §2)

  **Why interactive sessions now get this too (2026-08-28):** three concurrent interactive sessions
  sharing one tree repeatedly clobbered each other's uncommitted work in a single night — once
  through an agent misjudging a peer's legitimate in-progress edit as unmarked foreign drift (a
  content-judgment failure no gate prevents), and once through a genuinely mechanical hole: `git
  commit`'s pre-commit hook stashes the ENTIRE working tree (not just the committer's own paths —
  verified against `pre_commit/staged_files_only.py`: `git diff-index ... --` with no pathspec, and
  the restore path's `git checkout -- .`, both from the repo toplevel) to run hooks, then restores
  it. A peer session's unrelated, unstaged edits sitting in that same window can be lost if the
  restore's `git apply` fails — which is exactly what happened: an entire session's uncommitted
  `adapter.py` diff vanished mid-session, recovered only because pre-commit retains every stash as a
  patch file under `~/.cache/pre-commit/` (agentic-systems-architect audit, 2026-08-28, ExampleApp
  incident — its findings are not yet written back into `~/.claude/knowledge/agentarch_recommendations.jsonl`
  as of this note; do not assume a specific AA-#### id for it without checking that ledger directly).
  Per-session worktrees fix this by construction: nothing of a peer's sits in the tree pre-commit's
  own session stashes, because each session's pre-commit run only ever touches its own checkout.
  Nothing about this bullet ENFORCES or defaults sessions into worktrees — it only sanctions the
  practice; a session that stays on the shared tree is unprotected by any of this, same as before. (Superseded 2026-09-10 — see the follow-on entry below: worktrees became the DEFAULT. This sentence describes the 08-28 posture only.)
  **Two prerequisite fixes landed the same night and must stay in place: `hooks/block_branch_ops.py`'s
  `STATE_VERBS` now includes `restore`/`clean` (both were unblocked and are functionally equivalent
  to the already-blocked `checkout --`; `restore --staged`/`-S` with no `--worktree`/`-W` flag stays
  allowed — it rewrites only the index, never the working tree, and is gate 3's own printed recovery
  instruction for unstaging a file), and each product repo's `pytest.ini` needs `.claude` added to
  `norecursedirs` (a bare `pytest .` run duplicate-collects every worktree's copy of the suite
  otherwise — measured 88 import-mismatch errors in ExampleApp with 5 worktrees on disk before
  the fix; treat that repo name as an example only, per this file's own preamble — apply the same
  `norecursedirs` addition in any product repo adopting per-session worktrees, at whatever file that
  repo's own pytest config actually lives in, since some repos sync a "canonical" copy from elsewhere
  and both copies need the fix or the next sync reverts it).**

**2026-09-10 follow-on — worktrees become the DEFAULT.** Measured that night in
ExampleApp: 76 dirty paths from 7 concurrent sessions in one shared tree, 19 gate denials in
2 hours, builder edits wiped by the pre-commit stash window twice (a background Workflow's whole
first attempt; a hub card reverted at least twice), and a reviewed, ready commit stalled over an
hour on a doc-check collision with a peer's unrelated in-flight edit. Operator directive (verbatim):
"we want each session in its own worktree... each commit should merge. they should commit once
work passes." The 08-28 sanction above became the default rule in §2, with one structural
decision forced by two Opus reviews of the first draft: the commit and the review record are made
ONCE in the integration tree by the integrator, never in the worktree — the ledger is keyed by
checkout toplevel, `--rekey` cannot bridge checkouts, and a double record trips
`audit_review_attribution`'s `reused` flag on every integration. Mechanics:
`knowledge/worktree_integration_flow.md`.

## 2. The retired post-commit Stop gate, and the fabricated-claim correction (from CLAUDE.md §10)

  - **DECIDED 2026-08-20: the old post-commit `Stop` gate is RETIRED, committed.**
    `~/.claude/hooks/task_completion_gate.py` was unregistered from `settings.json` on 2026-08-19
    (operator direction: review should run before the commit, not after) and the unregistration was
    finally committed on 08-20, closing a decision that had sat pending for two days. **Correction of a
    fabricated claim that stood in this file for those two days:** earlier text here asserted this
    module implemented 5 checks (Firestore task-completion-log, tests-updated, docs-updated, a
    signed-review artifact, GitHub-issue-referenced) and framed retirement as a tradeoff against losing
    4 of them. That was never true of THIS file — read in full on 2026-08-20, `task_completion_gate.py`
    has exactly one substantive check, always had: "was Opus review recorded for the current HEAD"
    (`~/.claude/.review_state/last_reviewed`). No Firestore call, no diff inspection, no issue check
    anywhere in it, confirmed by direct read plus grep — precisely: `task-completion-log` appears
    nowhere in `hooks/`; the only `firestore` hits are `review_risk_tier.py`'s unrelated
    path-classification keyword (plus its own tests) and this corrective note itself, NONE of them a
    real Firestore call and none inside `task_completion_gate.py`'s actual logic. (An earlier draft of
    this correction claimed "firestore/task-completion-log appear NOWHERE in hooks/" outright — false,
    caught by review, fixed here; the irony of a fabrication-correction needing its own correction is
    exactly why "confirmed by grep" still means re-running the grep, not trusting the sentence.) The
    earlier claim appears to have conflated this file with a DIFFERENT,
    same-named file in a separate product repo (`~/Desktop/OtherApp/.claude/hooks/task_completion_gate.py`,
    distinct content, still live and correctly documented THERE — not this runtime's concern, not
    touched by this decision) — a lesson in its own right: a prior agent described a file it had not
    actually read, and that description then gated a real decision for two days. The one check this
    module actually had is strictly dominated by gate 3b (content-digest-keyed, pre-commit, cannot race
    a moving HEAD the way a post-commit sha-keyed check could) — there was nothing to "port," this was
    never a real tradeoff. `CSA_SKIP_REVIEW=1` is now inert. The module and its tests are KEPT on disk
    (dormant, not deleted) in case a future incident argues for reviving some form of it — revisit with
    real data from `record_review.py`'s outcome ledger (built 08-20) rather than a hunch, since that
    ledger now makes "does a checkpoint like this actually catch anything" an answerable question.
  - **HISTORICAL — describes the RETIRED Stop gate's own internal design**, kept only to explain why
    `commit_authors.py` still exists (it now serves the posttooluse authorship ledger, not a review
    prompt) and to preserve the "never review a HEAD I didn't produce" lesson for any future revival.
    Session-scoped as of 2026-08-17: the Stop gate used to fire in *every* live session sharing a repo
    the instant *any one* of them advanced HEAD past the last-reviewed commit — distracting every
    parallel agent for one session's commit. It looked up who actually committed that HEAD (a ledger
    written by `posttooluse_bash.py` right after a successful `git commit`) and only warned/blocked the
    COMMITTING session; a HEAD authored by a different session, or with no recorded author (an operator
    terminal commit, a HEAD predating the ledger, or a missed write), was logged once and never
    surfaced as a warn/block — mechanizing `feedback_no_review_others_work` instead of leaving it as an
    unenforced norm.

## 3. Warm-round evidence, Item 7's rejection, and the audit_review_attribution interaction (from CLAUDE.md §10)

      Evidence, stated at its actual strength: in the one night measured
      (2026-08-30/31 — the review ledger has no warm/cold dimension, so this is re-derivable
      only from the session's sub-agent transcripts, recorded on #4686), warm full rounds surfaced
      fix-round-introduced blockers on 4 of the 5 boundaries continued (a rename inconsistency
      inside the fix itself, a stale registration row, a resource leak RELOCATED by the fix that
      claimed to remove it, and a parity guard whose documented coverage overstated its real
      coverage with a live divergence behind it); the same night's COLD round-1 reviews
      separately caught two execution-proven defects in newly built content (a set-u
      array-expansion fatal that would have wedged every push from that machine, and an infinite
      hang on a zero jobs-count). A confirm-only round scoped to the reported-fix list would
      have examined almost none of these. That is the whole of the sample. Item 7's rejection,
      recorded so no cosmetic variant can sail past: its path-narrowing dropped
      keyword-triggered escalation entirely outside a runtime-repo-shaped path list (measured in
      one product repo — example only — 4,523 of 10,143 files lost escalation, including every
      trust surface the proposal itself declared); its confirm-round mechanism was PHYSICALLY
      unimplementable as specified (the ledger key is a one-way digest that cannot be reversed
      into a diff, and no round-1 diff-retention mechanism exists) — the one objection no future
      cost argument can overcome; and the fix-round defect data above argues against
      confirm-only scope regardless. **The re-proposal bar, split by what the rejection actually
      established: (i) downgrading a full round's SCOPE (any confirm-only variant) requires NEW
      evidence contradicting the fix-round defect data recorded on #4686 — a restated cost
      argument is not new evidence; (ii) re-narrowing HIGH-tier escalation by path requires a
      measured per-repo path-coverage analysis demonstrating no declared trust surface loses
      escalation. This bar is deliberately asymmetric relative to the one-night sample behind
      it: the safe direction is more review, so the rule stands provisionally until the
      `--warm` ledger dimension makes its own catch rate measurable.** KNOWN INTERACTION (blocking
      follow-up, filed on #4686, required before
      `audit_review_attribution.py`'s `reused`/`unmatched` verdicts are relied on in any audit):
      that auditor treats a reviewer identity-pair cited twice as forgery-shaped (`reused`) AND
      time-windows its lease matching (default 1800s) — a warm chain re-cites round 1's pair BY
      CONSTRUCTION and may sit hours after round 1, so the exemption must cover BOTH halves
      (successive `round=` values on one `prev=`-linked chain for pair-reuse — NOT a repo+digest
      grouping, which can never chain because every fix round moves the digest — and the lease-time
      window for a re-cited round-1 identity); until then, a warm round's re-cited identity is
      the expected shape, not the forgery signal. SCOPE of that suspension, stated precisely so
      the unattended sweep is not disabled: Exempt ONLY (i) a `reused` or `unmatched` verdict on
      an entry that is a successive `round=` value on a `prev=`-linked chain, where — for
      `unmatched` — the cited (agent_id, tool_use_id) pair EXISTS somewhere in
      `~/.claude/.agent_budget/spend.jsonl` (window-ignored; a pair that appears NOWHERE is a
      real mismatch and is always relayed); and (ii) a `reused` or `unmatched` verdict on a warm-shaped entry whose ledger `ts=`
      predates 2026-08-31 (the field mandate's landing date) — a hard date, never "before the
      mandate existed". Everything else in the verdict classes STANDS and is relayed — a
      `no-identity` entry is NEVER exempt on this ground alone (this bullet's own RECORDING
      paragraph above already says so: an entry without the re-cited round-1 identity lands as
      `no-identity`, "a flagged shape the exemption never covers"), and the verdict class as a
      whole is never voided. Two scope clarifications for the warm rule itself: TARGETED rounds
      are out of scope for warm/cold entirely and never consume the warm cap (the cap counts full
      rounds only, and a COLD full round resets it); and bound (a) fires on a change in EITHER
      direction — a boundary that stops being trust-surface breaks the chain exactly as one that
      newly becomes it.

## 4. The 67% bare-ledger-entry measurement and its root cause (from CLAUDE.md §10)

**Measured 2026-08-20: 703 of 1,043 ledger
  entries (67%) are bare — but every one of them predates the 08-19 pre-commit reorder** (all 35
  `precommit:`-keyed entries from the current gate 3b era carry a real outcome; the bare entries are
  legacy sha-keyed ones from the retired post-commit era). Root cause of the historical 67%: the
  `reference_review_gate_record_review.md` memory doc's own canonical copy-paste example omitted
  `--clean`/`--blockers`; anyone following it produced an unauditable entry. Fixed in that doc
  2026-08-20 — if this number is still climbing, something else is copying the old pattern.
