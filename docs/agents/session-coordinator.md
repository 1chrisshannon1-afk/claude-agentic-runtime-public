# session-coordinator

`session-coordinator` is the integration-lane role for a multi-worktree effort: it coordinates and
merges, and does no product work (`agents/session-coordinator.md`, "Role, in the operator's own
words"). Its charter is an operator quote: coordinate active sessions and merge branches, with each
session in its own worktree communicating when it is ready to merge back, and merging relatively
frequently. It exists because when several sessions each work in an isolated worktree, someone has
to land their already-reviewed diffs into the main tree one at a time, with the review record and
announcements intact. Worktree isolation is now opt-in rather than the default (CLAUDE.md §2), so
this role is rare.

## Model & tools

- **Model:** `sonnet` (`agents/session-coordinator.md:4`). The work is procedural integration, not
  open-ended judgment.
- **Tools:** `Bash, Read, Write, Glob, Grep`. `Write` exists so it can author a commit-message file.
  It holds no peer-messaging capability (see the next section).

## Cadence / trigger

There is no schedule. The agent file's description scopes it to a live session designated
integration-lane coordinator for a multi-worktree effort, and states it is not for ordinary product
work in the main tree and not reliably `Task`-dispatchable for its own duty. Coordinator
identification is by convention, not a mechanical marker: a session that needs a merge asks live
peers which session holds the integration lane; if none answers, it announces it is taking the lane,
waits briefly for objection, and integrates itself.

## A runbook, not a self-sufficient sub-agent

The agent file's central point is a capability boundary: the cross-session messaging tools
(`ListAgents`, `SendMessage`) are not tools a dispatched sub-agent can hold, verified against the
client's tool definitions on 2026-09-10. A `Task`-dispatched instance therefore cannot announce a
commit train beforehand or announce the clear afterward. The file is accordingly a runbook whose
primary consumer is a live interactive session already holding those tools. If it is dispatched
anyway, it refuses the announce steps, states that it has no peer-messaging capability, may still
prepare the patch, apply check, staging, digest comparison, review record and message file, and
returns the prepared state (or the exact reason it is not ready) so the live coordinator can run the
commit inside the announce bracket. It does not silently skip announcements, because an integration
commit landing without them violates the announce-before-commit-train rule in CLAUDE.md §3.

## What it does

- **Receives MERGE CARDs.** A card has six rows: worktree path, branch, exact pathspec, review-time
  key, reviewer identity (reviewer type, agent id, tool-use id, round, warm-streak), and commit
  subject plus issue. A card missing any field, or any of the five reviewer-identity values, is
  refused rather than guessed at. A card whose warm-streak exceeds 2 is also refused; this is the
  only place that cap is enforced for this flow, because the review recorder's own mechanical cap
  cannot see across the worktree-to-main-tree hand-off.
- **Runs the integrator steps** from `knowledge/worktree_integration_flow.md` (announce, cut the
  patch, stage by name, three-way apply and check the real exit status, compare the pending key to
  the card's key for exact equality, record the review once citing the card's identity, commit with
  a path-scoped message-file commit, announce clear). It never merges, pulls, cherry-picks, applies
  mailbox patches to, or reverts a worktree branch, since none of those pass through the commit
  gates.
- **Records the review with four silent-failure constraints** inlined in the agent file: pass the
  repo root as an explicit argument, redirect stdin from the null device, pass the three reviewer
  identity fields as separate flags copied from the card, and never pass the chain-linking flags.
- **Sizes trains conservatively.** A deny for too many files or top-level directories means the train
  is too big and should be split, not that the pathspec is wrong; the gate ceilings (30 paths, 4
  top-level directories, with root-level files sharing one bucket) are never targets, and the
  agent file says to aim for about ten paths where the change is separable.

## Conflict handling

It never hand-resolves a conflict and never re-reviews inside the integration tree. On a clean apply
with equal keys it proceeds with no extra review. On a real conflict it reverses the apply, refuses
the card, and sends it back for a fresh worktree from current HEAD with re-review there. On a clean
apply with a key mismatch it diagnoses in order: an incomplete patch (a new file left unstaged;
re-cut with no re-review), a worktree that changed after review (reverse, refuse, re-review in the
same worktree), or a main tree that already carried an unrelated peer's edit (reverse, refuse, fresh
worktree). An unexplained mismatch is a refusal, never a wave-through. A dispatched instance reports
the mismatch and diagnosis and stops, since only the live coordinator can notify the originating
session.

## Serialization

One integration commit is in flight per repo at a time. This is the session-layer analogue of the
per-repo commit mutex in the git gate chain: while mid-integration on one card, from announcing the
train through announcing clear, it does not start a second card in the same repo, and queues
incoming cards. The announcements are the signal peers use to know the lane is occupied.

## Grounding

`knowledge/worktree_integration_flow.md` is the authoritative mechanics reference (the rule, why the
commit lands in the integration tree, the session-side recipe, the MERGE CARD schema, the
integrator steps, and coordinator identification), read fresh each time. The agent file adds only
the role framing, the capability boundary, and the carve-outs. Its commit and review mechanics sit
under CLAUDE.md §3 and §10.

## Boundaries — what it will NOT do

Never does product or feature work. Never acts as reviewer of record; the card's reviewer is always
a separately dispatched `code-reviewer` or `trust-architect`, and a re-review after a mismatch
happens in the peer's fresh worktree. Never pushes, opens a PR, merges in the GitHub sense, or
deploys. Never uses the hard-blocked git state verbs (checkout, switch, stash, reset, rebase,
working-tree restore, clean). Never applies a card with incomplete fields. Never records a review
twice for one card. Never assumes peer-messaging capability it has not verified in the current
invocation context.

## How it fits with other agents

The reviewer identity on a card comes from the review step upstream (`code-reviewer`, or
`trust-architect` on trust-surface commits, per CLAUDE.md §10). Peer sessions do the product work in
their worktrees and send cards. Operator-hand-picked lane worktrees are a separate mechanism with their
own wrapper script and do not use the MERGE CARD flow; the flow doc says so explicitly.

## Example invocation

A designated coordinator session receives a card from a peer. All six fields are present and the
warm-streak is 1. The coordinator announces the train, applies the peer's patch with a three-way
apply, sees no conflict markers, and finds the recomputed pending key equals the card's key. It
records the review once with the card's reviewer identity, commits with the card's path list and
message file, and announces clear with the commit and patch path. Had the keys differed, it would
have reversed the apply and sent the card back with the diagnosis instead.
