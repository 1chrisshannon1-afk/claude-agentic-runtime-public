#!/usr/bin/env bash
# bash_gate.sh — pure-bash fast-path for the PreToolUse:Bash guard.
#
# The vast majority of Bash tool calls are NOT git/gcloud commands and have
# nothing to guard. Spawning python3 for every one of them costs ~45ms of
# interpreter start for a guaranteed allow. This gate reads the hook payload
# from stdin ONCE and, unless it could possibly be a git op or a gcloud
# identity mutation, exits 0 WITHOUT touching python — so an unrelated
# command costs ~0.
#
# Only when the payload contains 'git' (any git invocation), 'gcloud' (any
# gcloud invocation — #5310's block_gcloud_identity gate, which mutates
# the machine-wide ambient gcloud identity/ADC file exactly like git-state
# ops mutate the shared working tree), the literal 'CSA_ALLOW_GIT_STATE_OPS'
# (the inline-bypass tripwire every gate below must catch), looks like a
# `gh issue close ...` invocation (the gh_issue_close_gate fabricated-
# resolution / deploy-ancestry guard — orthogonal to the git/gcloud-focused
# gates, see pretooluse_bash.py), looks like a `gh issue create ...` or
# `gh_issue.sh create ...` invocation (issue_create_observer.py, #5827 — the
# PURE-OBSERVER issue-creation quality gate; never denies, but
# it must still actually SEE the command to log anything), or looks like it
# could ADD an item to a protected GitHub Projects (v2) board
# (protected_board_guard, gate 5b — see pretooluse_bash.py and
# protected_board_guard.py; operator directive 2026-09-14, GH #5490) do we
# pay for the single python3 spawn that runs pretooluse_bash.py — the ONE
# consolidated dispatcher for every Bash guard.
#
# Deny is expressed by the dispatcher via its JSON object; this wrapper only ever
# exits 0 (a nonzero exit would be read as a hook crash, not a decision).
#
# Deliberately NOT `set -euo pipefail`: this shim runs on EVERY Bash tool call
# machine-wide, and its only job is to reach the final `exit 0` / dispatch below.
# `-e` would turn an unreadable stdin or a failing interpreter spawn into a hook
# crash on every call; `-u` and `pipefail` add failure paths with nothing to gain on
# a control flow this short. The matched-command set is pinned by
# hooks/tests/test_bash_gate_patterns.sh, which also asserts this shim stays non-strict.

# Master OFF switch first: a global no-op, no stdin read, no python.
[ "${CSA_DISABLE_HOOKS:-0}" = "1" ] && exit 0

# Read the entire payload once (it is small — a single JSON object).
payload="$(cat)"

# Fast-path: nothing below matches anywhere in the payload -> nothing any
# guard could act on -> allow immediately, no python.
#   *git*                    — any git invocation (gates 1/1b/2/3/3b/3c/4/6).
#   *gcloud*                 — any gcloud invocation (gate 1c). A plain
#                              substring match, same posture as *git* —
#                              gcloud has no comparably common false-positive-
#                              prone substring the way "gh" alone would (see
#                              below), so a bare substring is proportionate.
#   *CSA_ALLOW_GIT_STATE_OPS*  — the inline-bypass tripwire every gate above
#                              must catch regardless of which gate it rides in on.
#   *gh*issue*close*         — a `gh ... issue ... close` shape (gate 5,
#                              gh_issue_close_gate). Intentionally narrow
#                              (requires all three tokens, in order) rather
#                              than a bare `*gh*` — that would spawn python
#                              for every ordinary command containing "gh" as
#                              a substring (e.g. "high", "though") and defeat
#                              this fast-path's purpose.
#   *gh*project*             — a `gh project ...` invocation — item-add,
#                              item-create, item-edit, view, etc. (gate 5b,
#                              shape (a); reads are let through to python too
#                              since the arm can't cheaply distinguish them,
#                              but pbg.decide() itself allows a read — this
#                              only costs one python spawn, never a false
#                              deny). Same "all tokens present, in order"
#                              narrowing as the issue*close arm above, for
#                              the identical "gh" substring reason.
#   *addProjectV2*           — the GraphQL add-item/draft-issue mutation
#                              names themselves (gate 5b, shape (b):
#                              `addProjectV2ItemById` / `addProjectV2DraftIssue`).
#                              Distinctive enough on its own (no plausible
#                              false-positive substring) to match without
#                              also requiring "gh" or "api".
#   *--add-project* | *--project=* | *"--project"*
#                             — the `--project`/`--add-project` flag shapes
#                              `gh issue|pr create/edit` and `gh_issue.sh`
#                              use to target a board (gate 5b, shapes (c)/(d)).
#                              Narrow flag-literal matches, not a bare *gh*,
#                              so an unrelated command mentioning "project" in
#                              prose text alone still needs the actual flag
#                              spelling to route to python.
#   *gh*create*-p* | *gh*edit*-p*
#                             — the SHORT `-p` spelling of `--project` that
#                              `gh issue create`/`gh issue edit`/`gh pr
#                              create`/`gh pr edit` also document (`-p,
#                              --project title`) — gate 5b shape (c). A bare
#                              `*-p*` alone would match nearly every payload
#                              (any word containing "p"), so this requires
#                              both `gh` AND `create`/`edit` to also appear,
#                              in that relative order, before it counts —
#                              same "all tokens present, in order" narrowing
#                              as the `*gh*issue*close*`/`*gh*project*` arms
#                              above, for the identical substring-collision
#                              reason.
#   *gh*issue*create*
#                             — a `gh ... issue ... create` shape. This also
#                              covers this runtime's own `gh_issue.sh create`
#                              helper under ANY path prefix (issue_create_
#                              observer.py, #5827): the filename `gh_issue.sh`
#                              itself holds `gh`, then `issue`, so a payload
#                              with `gh_issue.sh ... create` already satisfies
#                              "gh, then issue, then create, in order". An
#                              earlier explicit `*gh_issue.sh*create*` arm
#                              could therefore never match anything this arm
#                              missed (shellcheck SC2221/SC2222); it was
#                              removed with the matched set unchanged, which
#                              hooks/tests/test_bash_gate_patterns.sh pins.
#                              Same "all tokens present, in order" narrowing
#                              as the `*gh*issue*close*` arm above.
case "$payload" in
  *git* | *gcloud* | *CSA_ALLOW_GIT_STATE_OPS* | *gh*issue*close* | *gh*project* \
    | *addProjectV2* | *--add-project* | *--project=* | *"--project"* \
    | *gh*create*-p* | *gh*edit*-p* | *gh*issue*create*)
    # Possible git op, gcloud identity mutation, an inline-tripwire attempt,
    # a gh-issue-close, an issue-create (bare gh or the gh_issue.sh helper),
    # or a protected-board add attempt — hand the payload to the single
    # python dispatcher, which reads it on stdin and decides.
    printf '%s' "$payload" | python3 "$HOME/.claude/hooks/pretooluse_bash.py"
    ;;
  *)
    exit 0
    ;;
esac
